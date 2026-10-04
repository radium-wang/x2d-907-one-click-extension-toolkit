"""Host-only HEIF ABI/lifetime tests; deliberately no format-1003 converter."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MonoHeifBridgeTests(unittest.TestCase):
    def test_bridge(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("A C compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-heif-") as temp:
            executable = Path(temp) / "mono-heif-bridge-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_heif_bridge.c"),
                str(ROOT / "tests/mono_heif_bridge_test.c"),
                "-o", str(executable),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True,
                           capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
