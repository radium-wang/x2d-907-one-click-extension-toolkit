"""Host simulation of the camera-service monochrome control contract."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MonoControlTest(unittest.TestCase):
    def test_control_gates_each_image_route_and_restores(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-control-") as temp:
            output = Path(temp) / "control-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_pref.c"),
                str(ROOT / "src/mono/cfv_mono_control.c"),
                str(ROOT / "tests/mono_control_test.c"),
                "-o", str(output),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(output), str(Path(temp) / "mono.available"),
                            str(Path(temp) / "mono.enabled")],
                           check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
