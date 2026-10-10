"""Offline transaction tests: no device or network access."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

MODULE_FILE = Path(__file__).resolve().parents[1] / "src" / "mono" / "mono_transaction.py"
spec = importlib.util.spec_from_file_location("mono_transaction", MODULE_FILE)
mono = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mono
spec.loader.exec_module(mono)

STOCK = (b"service camera-service /system/bin/camera-service\n"
         b"    setenv XDG_RUNTIME_DIR /tmp\n"
         b"    class core\n"
         b"    user root\n"
         b"    group root\n")
PAYLOAD = b"synthetic host-test library, never a camera payload"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


class PowerLoss(BaseException):
    pass


class FakeDurableStore:
    """Atomic, persistent file map with a cut after a mutation."""
    def __init__(self, files=None):
        self.files = dict(files or {mono.SERVICE_RC: STOCK})
        self.mutations = 0
        self.fail_after = None

    def read(self, path):
        return self.files[path]

    def exists(self, path):
        return path in self.files

    def _cut(self):
        self.mutations += 1
        if self.fail_after == self.mutations:
            self.fail_after = None
            raise PowerLoss()

    def put(self, path, data):
        self.files[path] = bytes(data)
        self._cut()

    def remove(self, path):
        self.files.pop(path, None)
        self._cut()

    def power_cycle(self):
        """Discard in-memory transaction objects, retain durable files."""
        return FakeDurableStore(self.files)


class MonoTransactionTests(unittest.TestCase):
    def test_stock_hash_and_exact_patch(self):
        self.assertEqual(mono.digest(STOCK), mono.STOCK_RC_SHA256)
        patch = mono.candidate_rc(STOCK)
        self.assertIn(b"setenv LD_PRELOAD /system/lib64/libcfv_mono.so\n", patch)
        self.assertEqual(patch.count(b"LD_PRELOAD"), 1)
        with self.assertRaises(mono.TransactionError):
            mono.candidate_rc(STOCK + b"\n# modified")

    def test_availability_only_after_runtime_check_and_preference_persists(self):
        store = FakeDurableStore()
        tx = mono.MonoTransaction(store)
        self.assertEqual(tx.install(PAYLOAD, PAYLOAD_SHA).phase, "HOOKED")
        self.assertFalse(store.exists(mono.FEATURE))
        self.assertEqual(store.read(mono.PREF), b"0\n")
        with self.assertRaises(mono.TransactionError):
            tx.activate(lambda: False)
        self.assertFalse(store.exists(mono.FEATURE))
        self.assertEqual(tx.activate(lambda: True).phase, "ACTIVE")
        self.assertFalse(tx.is_enabled())
        store.put(mono.PREF, b"1\n")
        self.assertTrue(mono.MonoTransaction(store.power_cycle()).is_enabled())
        self.assertEqual(store.read(mono.PREF), b"1\n")
        result = mono.MonoTransaction(store).restore()
        self.assertTrue(result.requires_service_restart)
        self.assertEqual(store.files, {mono.SERVICE_RC: STOCK})
        self.assertEqual(mono.MonoTransaction(store).restore().phase, "STOCK")

    def test_revalidation_failure_withdraws_previous_availability(self):
        store = FakeDurableStore()
        tx = mono.MonoTransaction(store)
        tx.install(PAYLOAD, PAYLOAD_SHA)
        tx.activate(lambda: True)
        store.put(mono.PREF, b"1\n")
        self.assertTrue(tx.is_enabled())
        with self.assertRaises(mono.TransactionError):
            tx.activate(lambda: False)
        self.assertFalse(tx.is_enabled())
        self.assertFalse(store.exists(mono.FEATURE))
        self.assertEqual(store.read(mono.PREF), b"1\n")
        tx.restore()
        self.assertEqual(store.files, {mono.SERVICE_RC: STOCK})

    def test_bad_manifest_or_tampered_startup_refused(self):
        store = FakeDurableStore()
        tx = mono.MonoTransaction(store)
        with self.assertRaises(mono.TransactionError):
            tx.install(PAYLOAD, "0" * 64)
        self.assertEqual(store.files, {mono.SERVICE_RC: STOCK})
        tx.install(PAYLOAD, PAYLOAD_SHA)
        tx.activate(lambda: True)
        store.files[mono.SERVICE_RC] = b"unrelated config\n"
        with self.assertRaises(mono.TransactionError):
            tx.restore()
        self.assertFalse(store.exists(mono.FEATURE))
        self.assertEqual(store.read(mono.SERVICE_RC), b"unrelated config\n")

    def test_install_power_cut_at_each_durable_mutation(self):
        # Backup, journal, module, preference, startup config, committed journal.
        for cut in range(1, 7):
            with self.subTest(cut=cut):
                store = FakeDurableStore()
                store.fail_after = cut
                with self.assertRaises(PowerLoss):
                    mono.MonoTransaction(store).install(PAYLOAD, PAYLOAD_SHA)
                rebooted = store.power_cycle()
                mono.MonoTransaction(rebooted).restore()
                self.assertEqual(rebooted.files, {mono.SERVICE_RC: STOCK})

    def test_activate_power_cut_never_enables_without_marker(self):
        for cut in (1, 2):
            with self.subTest(cut=cut):
                store = FakeDurableStore()
                mono.MonoTransaction(store).install(PAYLOAD, PAYLOAD_SHA)
                store.fail_after = store.mutations + cut
                with self.assertRaises(PowerLoss):
                    mono.MonoTransaction(store).activate(lambda: True)
                rebooted = store.power_cycle()
                if cut == 1:
                    self.assertFalse(mono.MonoTransaction(rebooted).is_enabled())
                mono.MonoTransaction(rebooted).restore()
                self.assertEqual(rebooted.files, {mono.SERVICE_RC: STOCK})

    def test_restore_power_cut_at_each_durable_mutation(self):
        # Marker, journal, preference, stock startup, module, journal, backup.
        for cut in range(1, 8):
            with self.subTest(cut=cut):
                store = FakeDurableStore()
                tx = mono.MonoTransaction(store)
                tx.install(PAYLOAD, PAYLOAD_SHA)
                tx.activate(lambda: True)
                store.put(mono.PREF, b"1\n")
                store.fail_after = store.mutations + cut
                with self.assertRaises(PowerLoss):
                    tx.restore()
                rebooted = store.power_cycle()
                self.assertFalse(mono.MonoTransaction(rebooted).is_enabled())
                mono.MonoTransaction(rebooted).restore()
                self.assertEqual(rebooted.files, {mono.SERVICE_RC: STOCK})

    def test_unknown_module_blocks_restore_after_disabling_feature(self):
        store = FakeDurableStore()
        tx = mono.MonoTransaction(store)
        tx.install(PAYLOAD, PAYLOAD_SHA)
        tx.activate(lambda: True)
        store.files[mono.MODULE] = b"unknown library"
        with self.assertRaises(mono.TransactionError):
            tx.restore()
        self.assertFalse(store.exists(mono.FEATURE))
        self.assertNotEqual(store.read(mono.SERVICE_RC), STOCK)


if __name__ == "__main__":
    unittest.main()
