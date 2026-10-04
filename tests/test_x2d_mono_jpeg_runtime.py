"""Host contract test for the first-generation X2D JPEG interposer."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class X2DMonoJpegRuntimeTests(unittest.TestCase):
    def test_hook(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "jpeg-runtime"
            cmd = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-DX2D_MONO_JPEG_HOST_TEST", "-pthread", "-I", str(ROOT / "src/mono")]
            cmd += [str(ROOT / "src/mono" / name) for name in
                    ("cfv_mono.c", "cfv_mono_jpeg.c", "cfv_mono_vmem.c",
                     "cfv_mono_jpeg_bridge.c", "x2d_mono_jpeg_runtime.c")]
            cmd += [str(ROOT / "tests/x2d_mono_jpeg_runtime_test.c"), "-o", str(binary)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

if __name__ == "__main__":
    unittest.main()
