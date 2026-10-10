"""Host contract for the exact-symbol X2D Wayland interposer."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class X2dMonoPreviewRuntimeTests(unittest.TestCase):
    def test_interposer_contract(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        nm = shutil.which("nm")
        if not compiler or not nm:
            self.skipTest("C toolchain unavailable")
        with tempfile.TemporaryDirectory(prefix="x2d-mono-preview-") as tmp:
            exe = Path(tmp) / "preview-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_preview.c"),
                str(ROOT / "src/mono/cfv_mono_display.c"),
                str(ROOT / "src/mono/x2d_mono_preview_runtime.c"),
                str(ROOT / "tests/x2d_mono_preview_runtime_test.c"),
                "-ldl", "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)
            symbols = subprocess.run([nm, str(exe)], check=True,
                                     capture_output=True, text=True).stdout
            self.assertIn("_ZN16WaylandControlLV9handleBufEPvRKNSt3__110shared_ptrI10MemCapsuleEE14RecommendationRK9RectangleP17duss_frame_buffer", symbols)


if __name__ == "__main__":
    unittest.main()
