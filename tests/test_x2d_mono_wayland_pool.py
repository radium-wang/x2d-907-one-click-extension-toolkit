"""Stable VMem pool occupancy and compositor release ordering."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class X2dMonoWaylandPoolTests(unittest.TestCase):
    def test_reuse_and_safe_retirement(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="x2d-wayland-pool-") as tmp:
            exe = Path(tmp) / "pool-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-pthread", "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/x2d_mono_wayland_pool.c"),
                str(ROOT / "tests/x2d_mono_wayland_pool_test.c"),
                "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
