"""Offline HEIF runtime contract tests with a simulated X2D provider."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class X2DMonoHeifRuntimeTests(unittest.TestCase):
    def test_private_frame_and_hook(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "heif-runtime"
            subprocess.run([
                "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-pedantic", "-DX2D_MONO_HEIF_HOST_TEST", "-Isrc/mono",
                "src/mono/x2d_mono_heif_runtime.c",
                "src/mono/cfv_mono_heif_bridge.c",
                "src/mono/cfv_mono_heif_format.c",
                "tests/x2d_mono_heif_runtime_test.c", "-o", str(binary),
            ], cwd=ROOT, check=True)
            subprocess.run([str(binary)], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
