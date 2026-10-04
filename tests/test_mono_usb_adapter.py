"""Offline-only checks for Shuaqi monochrome USB transaction generation."""
import hashlib
import os
import shutil
import tempfile
import json
import subprocess
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "mono"))
import mono_usb_adapter as usbmono
import mono_transaction as tx

STOCK = (b"service camera-service /system/bin/camera-service\n"
         b"    setenv XDG_RUNTIME_DIR /tmp\n"
         b"    class core\n"
         b"    user root\n"
         b"    group root\n")
def synthetic_probe_elf():
    names = b"\0duss_hal_ienc_encfrm\0duss_hal_heifenc_encfrm\0"
    data = bytearray(328 + len(names))
    data[:6] = b"\x7fELF\x02\x01"
    data[16:20] = b"\x03\x00\xb7\x00"
    struct.pack_into("<Q", data, 40, 64)     # e_shoff
    struct.pack_into("<HH", data, 58, 64, 3) # e_shentsize, e_shnum
    struct.pack_into("<I", data, 64 + 64 + 4, 11)    # SHT_DYNSYM
    struct.pack_into("<QQ", data, 64 + 64 + 24, 256, 72)
    struct.pack_into("<I", data, 64 + 64 + 40, 2)    # .dynstr section
    struct.pack_into("<Q", data, 64 + 64 + 56, 24)
    struct.pack_into("<I", data, 64 + 128 + 4, 3)   # SHT_STRTAB
    struct.pack_into("<QQ", data, 64 + 128 + 24, 328, len(names))
    struct.pack_into("<I", data, 256 + 24, 1)
    struct.pack_into("<H", data, 256 + 24 + 6, 1)
    struct.pack_into("<I", data, 256 + 48, 1 + len(b"duss_hal_ienc_encfrm") + 1)
    struct.pack_into("<H", data, 256 + 48 + 6, 1)
    data[328:] = names
    return bytes(data)


MODULE = synthetic_probe_elf()
MODULE_SHA = hashlib.sha256(MODULE).hexdigest()


class FakeTransport:
    """Records calls and emulates only the transaction's final state."""
    def __init__(self, model="X2D 100C"):
        self.model = model
        self.files = {tx.SERVICE_RC: STOCK}
        self.calls = []
        self.stage = {}
        self.target_ok = True
        self.script_calls = []

    def verify_target(self):
        self.calls.append("verify_target")
        if not self.target_ok:
            raise RuntimeError("wrong firmware")

    def camera_model(self):
        self.calls.append("camera_model")
        return self.model

    def shell(self, command):
        self.calls.append(("shell", command))
        if command.startswith("test -e "):
            path = command[len("test -e "):].split(" && ", 1)[0]
            return "YES" if path in self.files else "NO"
        if command.startswith("sha256sum "):
            return usbmono.sha(self.files[command[len("sha256sum "):]]) + "  file"
        if command.startswith("test ! -L "):
            return "SAFE"
        if command == f"sh {usbmono.STAGE}/monoinstall":
            self.script_calls.append(command)
            self.files[tx.BACKUP] = STOCK
            self.files[tx.MODULE] = MODULE
            self.files[tx.PREF] = b"0\n"
            candidate = tx.candidate_rc(STOCK)
            self.files[tx.SERVICE_RC] = candidate
            self.files[tx.STATE] = usbmono.journal("HOOKED", MODULE_SHA, usbmono.sha(candidate))
            self.files[tx.ROOT] = b"directory"
            return "MONO_PREPARED"
        if command == f"sh {usbmono.STAGE}/monorestore":
            self.script_calls.append(command)
            self.files = {tx.SERVICE_RC: STOCK}
            return "MONO_RESTORED"
        if command == f"sh {usbmono.STAGE}/monoorphan":
            self.script_calls.append(command)
            self.files = {tx.SERVICE_RC: STOCK}
            return "MONO_ORPHAN_CLEANED"
        raise AssertionError(command)

    def read_bytes(self, path):
        self.calls.append(("read", path))
        return self.files[path]

    def ensure_adb(self):
        self.calls.append("ensure_adb")

    def upload(self, name, data):
        self.calls.append(("upload", name))
        self.stage[name] = data

    def validate_script(self, script):
        p = subprocess.run(["sh", "-n"], input=script, text=True, capture_output=True)
        if p.returncode:
            raise AssertionError(p.stderr)


class MonoUsbTests(unittest.TestCase):
    def test_module_identity_and_hash(self):
        usbmono.verify_module(MODULE, MODULE_SHA)
        with self.assertRaises(usbmono.MonoUsbError):
            usbmono.verify_module(MODULE, "0" * 64)
        with self.assertRaises(usbmono.MonoUsbError):
            usbmono.verify_module(b"not an elf", usbmono.sha(b"not an elf"))
        missing = bytearray(MODULE)
        struct.pack_into("<H", missing, 256 + 48 + 6, 0)
        with self.assertRaisesRegex(usbmono.MonoUsbError, "HAL exports"):
            usbmono.verify_module(bytes(missing), usbmono.sha(missing))
        writable_executable = bytearray(MODULE)
        offset = len(writable_executable)
        writable_executable.extend(b"\\0" * 56)
        struct.pack_into("<Q", writable_executable, 32, offset)
        struct.pack_into("<HH", writable_executable, 54, 56, 1)
        struct.pack_into("<II", writable_executable, offset, 1, 7)
        with self.assertRaisesRegex(usbmono.MonoUsbError, "writable executable"):
            usbmono.verify_module(bytes(writable_executable), usbmono.sha(writable_executable))

    def test_exact_model_gate_prevents_upload(self):
        t = FakeTransport("907X & CFV 100C")
        with self.assertRaises(usbmono.MonoUsbError):
            usbmono.MonoUsbAdapter(t, "X2D 100C").install(MODULE, MODULE_SHA)
        self.assertFalse(any(isinstance(call, tuple) and call[0] == "upload" for call in t.calls))

    def test_stock_hash_gate_prevents_upload(self):
        t = FakeTransport()
        t.files[tx.SERVICE_RC] += b"# changed\n"
        with self.assertRaises(RuntimeError):
            usbmono.MonoUsbAdapter(t, "X2D 100C").install(MODULE, MODULE_SHA)
        self.assertFalse(t.stage)

    def test_x2d_probe_transaction_is_dormant_and_restorable(self):
        t = FakeTransport()
        a = usbmono.MonoUsbAdapter(t, "X2D 100C")
        self.assertEqual(a.install(MODULE, MODULE_SHA), "HOOKED_DISABLED_RESTART_REQUIRED")
        self.assertNotIn(tx.FEATURE, t.files)
        self.assertEqual(t.files[tx.PREF], b"0\n")
        self.assertEqual(usbmono.parse_journal(t.files[tx.STATE])["phase"], "HOOKED")
        self.assertEqual(a.restore(), "STOCK_RESTART_REQUIRED")
        self.assertEqual(t.files, {tx.SERVICE_RC: STOCK})
        self.assertEqual(a.restore(), "ALREADY_STOCK")

    def test_cfv_has_independent_gate(self):
        t = FakeTransport("907X & CFV 100C")
        a = usbmono.MonoUsbAdapter(t, "907X & CFV 100C")
        self.assertEqual(a.install(MODULE, MODULE_SHA), "HOOKED_DISABLED_RESTART_REQUIRED")
        self.assertEqual(a.restore(), "STOCK_RESTART_REQUIRED")

    def test_restore_requires_matching_journal_and_module(self):
        t = FakeTransport()
        a = usbmono.MonoUsbAdapter(t, "X2D 100C")
        a.install(MODULE, MODULE_SHA)
        t.files[tx.MODULE] = b"tampered"
        with self.assertRaises(usbmono.MonoUsbError):
            a.restore()
        self.assertNotIn(f"sh {usbmono.STAGE}/monorestore", t.script_calls)

    def test_restore_without_journal_refuses_orphans(self):
        t = FakeTransport()
        t.files[tx.MODULE] = MODULE
        with self.assertRaises(usbmono.MonoUsbError):
            usbmono.MonoUsbAdapter(t, "X2D 100C").restore()

    def test_power_cut_before_first_journal_cleans_only_stock_orphan(self):
        t = FakeTransport()
        t.files[tx.ROOT] = b"directory"
        t.files[tx.BACKUP] = STOCK
        a = usbmono.MonoUsbAdapter(t, "X2D 100C")
        self.assertEqual(a.restore(), "STOCK_ORPHAN_CLEANED")
        self.assertEqual(t.files, {tx.SERVICE_RC: STOCK})
        self.assertIn("monoorphan", t.stage)

    def test_mono_install_requires_explicit_system_write_confirmation(self):
        import x2d_play_software as app
        from unittest.mock import patch
        with patch.object(app, "mono_package") as package, patch.object(app, "verify_target") as target:
            with self.assertRaisesRegex(RuntimeError, "confirm-probe-system-write"):
                app.mono_install(False, False)
        package.assert_not_called()
        target.assert_not_called()

    def test_install_and_restore_scripts_execute_in_local_fixture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in ("system/etc/init", "system/lib64",
                        "blackbox/.x2d-play-software/stage"):
                (root / rel).mkdir(parents=True)
            (root / "system/etc/init/camera-service.rc").write_bytes(STOCK)
            stage = root / "blackbox/.x2d-play-software/stage"
            candidate = tx.candidate_rc(STOCK)
            for name, data in (("monostock", STOCK), ("monorc", candidate),
                               ("monomod", MODULE)):
                (stage / name).write_bytes(data)

            def run(script):
                script = script.replace("/system", str(root / "system"))
                script = script.replace("/blackbox", str(root / "blackbox"))
                if sys.platform == "darwin" or shutil.which("sha256sum") is None:
                    script = script.replace("sha256sum", "shasum -a 256")
                lines = script.splitlines()
                lines[2] = "export PATH=/usr/bin:/bin TMPDIR=/tmp"
                lines[4] = "state() { echo '/dev/block/mmcblk0p16 ext4 ro,fixture'; }"
                lines.insert(3, "mount() { return 0; }")
                p = subprocess.run(["sh"], input="\n".join(lines) + "\n",
                                   text=True, capture_output=True)
                self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
                return p.stdout

            output = run(usbmono.install_script(MODULE_SHA, usbmono.sha(candidate)))
            self.assertIn("MONO_PREPARED", output)
            self.assertEqual((root / "system/etc/init/camera-service.rc").read_bytes(), candidate)
            self.assertEqual((root / "blackbox/x2d-play-mono.enabled").read_bytes(), b"0\n")
            self.assertFalse((root / "blackbox/x2d-play-mono.available").exists())
            output = run(usbmono.restore_script(MODULE_SHA, usbmono.sha(candidate),
                                                usbmono.sha(candidate), True))
            self.assertIn("MONO_RESTORED", output)
            self.assertEqual((root / "system/etc/init/camera-service.rc").read_bytes(), STOCK)
            self.assertFalse((root / "system/lib64/libcfv_mono.so").exists())
            self.assertFalse((root / "blackbox/.x2d-play-software/mono").exists())

    def test_scripts_require_stock_backup_and_remove_availability_first(self):
        install = usbmono.install_script(MODULE_SHA, usbmono.sha(tx.candidate_rc(STOCK)))
        restore = usbmono.restore_script(MODULE_SHA, usbmono.sha(tx.candidate_rc(STOCK)),
                                         usbmono.sha(tx.candidate_rc(STOCK)), True)
        for text in (install, restore):
            self.assertEqual(subprocess.run(["sh", "-n"], input=text, text=True).returncode, 0)
            self.assertIn("mount -o remount,ro /system", text)
        self.assertLess(restore.index("rm -f " + tx.FEATURE), restore.index("mount -o remount,rw /system"))
        self.assertIn("hashok " + tx.BACKUP + " " + tx.STOCK_RC_SHA256, restore)
        self.assertNotIn("start camera-gui", restore)


if __name__ == "__main__":
    unittest.main()


class ShuaqiIntegrationTests(unittest.TestCase):
    def setUp(self):
        import x2d_play_software as app
        self.app = app

    def test_probe_manifest_requires_model_and_contract(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            spec = {
                "format": 1, "variant": "probe",
                "probeContract": "observation-only-no-output-mutation-v1",
                "source": "libcfv_mono.so", "sha256": MODULE_SHA,
                "stockServiceRcSha256": tx.STOCK_RC_SHA256,
                "targetModels": ["X2D 100C"], "readyForDeviceTest": True
            }
            (root / "libcfv_mono.so").write_bytes(MODULE)
            (root / "mono-module.json").write_text(json.dumps(spec))
            with patch.object(self.app, "O", root):
                self.assertEqual(self.app.mono_package()[0]["variant"], "probe")
                spec["variant"] = "runtime"
                (root / "mono-module.json").write_text(json.dumps(spec))
                with self.assertRaises(RuntimeError):
                    self.app.mono_package()
                spec["variant"] = "probe"
                spec["targetModels"] = ["907X & CFV 100C"]
                (root / "mono-module.json").write_text(json.dumps(spec))
                with self.assertRaises(RuntimeError):
                    self.app.mono_package()
                spec["targetModels"] = ["X2D 100C"]
                spec["probeContract"] = "unknown"
                (root / "mono-module.json").write_text(json.dumps(spec))
                with self.assertRaises(RuntimeError):
                    self.app.mono_package()

    def test_normal_restore_with_mono_only_runs_independent_usb_first(self):
        from unittest.mock import patch
        app = self.app
        events = []
        with patch.object(app, "verify_target"), \
             patch.object(app, "camera_model", return_value="X2D 100C"), \
             patch.object(app, "MonoUsbAdapter") as mono, \
             patch.object(app, "shell", side_effect=[
                 "NO", app.STOCK_RC + " file"
             ]), patch.object(app, "prepare", return_value={}), \
             patch.object(app, "mono_reboot_verify") as reboot, \
             patch.object(app, "event", side_effect=lambda kind, **v: events.append(kind)):
            mono.return_value.restore.return_value = "STOCK_RESTART_REQUIRED"
            app.restore(True)
        mono.return_value.restore.assert_called_once()
        reboot.assert_called_once_with(tx.STOCK_RC_SHA256)
        self.assertIn("result", events)
