"""Host-only contract tests for the CFV 4.2.0 JPEG HAL parameter bridge."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MonoJpegBridgeTests(unittest.TestCase):
    def test_bridge(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("A C compiler is unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-bridge-") as temp:
            executable = Path(temp) / "mono-jpeg-bridge-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono.c"),
                str(ROOT / "src/mono/cfv_mono_jpeg.c"),
                str(ROOT / "src/mono/cfv_mono_vmem.c"),
                str(ROOT / "src/mono/cfv_mono_jpeg_bridge.c"),
                str(ROOT / "tests/mono_jpeg_bridge_test.c"),
                "-o", str(executable),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
