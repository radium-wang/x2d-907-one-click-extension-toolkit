"""Bounded Wayland lease and two-event release contract."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class X2dMonoWaylandLeaseTests(unittest.TestCase):
    def test_no_premature_free_and_capacity(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="x2d-wayland-lease-") as tmp:
            exe = Path(tmp) / "lease-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-pthread", "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/x2d_mono_wayland_lease.c"),
                str(ROOT / "tests/x2d_mono_wayland_lease_test.c"),
                "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
