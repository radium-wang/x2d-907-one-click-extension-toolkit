"""Host-only contract tests for the narrow CFV Wayland display dispatch."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MonoDisplayTests(unittest.TestCase):
    def test_display_dispatch(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-display-") as tmp:
            exe = Path(tmp) / "display-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_preview.c"),
                str(ROOT / "src/mono/cfv_mono_display.c"),
                str(ROOT / "tests/mono_display_test.c"),
                "-o", str(exe),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
