"""Exact-symbol Wayland release and proxy-destroy observers."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class X2dMonoWaylandProxyHookTests(unittest.TestCase):
    def test_release_after_stock_and_tracked_destroy(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        nm = shutil.which("nm")
        if not compiler or not nm:
            self.skipTest("C toolchain unavailable")
        with tempfile.TemporaryDirectory(prefix="x2d-wayland-hook-") as tmp:
            exe = Path(tmp) / "hook-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-pthread", "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/x2d_mono_wayland_pool.c"),
                str(ROOT / "src/mono/x2d_mono_wayland_proxy_hook.c"),
                str(ROOT / "tests/x2d_mono_wayland_proxy_hook_test.c"),
                "-ldl", "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)
            symbols = subprocess.run([nm, str(exe)], check=True,
                                     capture_output=True, text=True).stdout
            self.assertIn("_ZN14WaylandControl13bufferReleaseEP9wl_buffer", symbols)
            self.assertIn("wl_proxy_destroy", symbols)


if __name__ == "__main__":
    unittest.main()
