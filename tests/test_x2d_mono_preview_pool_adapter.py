"""Host integration of stable private VMem, Wayland hooks and preview dispatch."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class X2dMonoPreviewPoolAdapterTests(unittest.TestCase):
    def test_repeated_monochrome_frames_keep_overlay_and_lut(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="x2d-preview-adapter-") as tmp:
            exe = Path(tmp) / "adapter-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-pthread", "-I", str(ROOT / "src/mono"),
                *[str(ROOT / "src/mono" / name) for name in (
                    "cfv_mono_preview.c", "cfv_mono_display.c",
                    "x2d_mono_preview_runtime.c", "x2d_mono_wayland_pool.c",
                    "x2d_mono_wayland_proxy_hook.c",
                    "x2d_mono_preview_pool_adapter.c")],
                str(ROOT / "tests/x2d_mono_preview_pool_adapter_test.c"),
                "-ldl", "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
