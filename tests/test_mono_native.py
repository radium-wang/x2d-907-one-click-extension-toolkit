"""Offline checks for the proposed CFV JPEG monochrome pixel unit."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MonoNativeTests(unittest.TestCase):
    def test_preference_survives_process_restart_and_restore(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("A C compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-pref-") as temp:
            directory = Path(temp)
            executable = directory / "pref-test"
            feature = directory / "mono.available"
            preference = directory / "mono.enabled"
            command = [
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_pref.c"),
                str(ROOT / "tests/mono_pref_cli.c"), "-o", str(executable),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)

            def run(action):
                return subprocess.run(
                    [str(executable), action, str(feature), str(preference)],
                    capture_output=True, text=True).returncode

            self.assertEqual(run("read"), 1)  # Fresh installation: off.
            feature.write_text("1\n")
            self.assertEqual(run("read"), 1)
            self.assertEqual(run("on"), 0)
            self.assertEqual(run("read"), 0)  # Fresh process: selection kept.
            self.assertEqual(preference.read_text(), "1\n")
            self.assertEqual(run("off"), 0)
            self.assertEqual(run("read"), 1)
            self.assertEqual(run("on"), 0)
            preference.write_text("1\ncorrupt")
            self.assertEqual(run("read"), 1)  # Fail closed.
            self.assertEqual(run("on"), 0)
            feature.unlink()  # Interrupted restore: stale on-state cannot reactivate.
            self.assertEqual(run("read"), 1)
            feature.write_text("1\n")
            self.assertEqual(run("restore"), 0)
            self.assertFalse(feature.exists())
            self.assertFalse(preference.exists())
            self.assertEqual(run("read"), 1)

    def test_converter_contract(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("A C compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-test-") as temp:
            executable = Path(temp) / "mono-test"
            command = [
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono.c"),
                str(ROOT / "src/mono/cfv_mono_jpeg.c"),
                str(ROOT / "src/mono/cfv_mono_vmem.c"),
                str(ROOT / "tests/mono_native_test.c"),
                "-o", str(executable),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
