"""Host-only contract tests for the unbound CFV live-view monochrome bridge."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class MonoPreviewTests(unittest.TestCase):
    def test_preview_contract(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-preview-") as tmp:
            exe = Path(tmp) / "preview-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_preview.c"),
                str(ROOT / "tests/mono_preview_test.c"),
                "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)

if __name__ == "__main__":
    unittest.main()
