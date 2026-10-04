"""Host-only loopback transport contract; never starts on a camera."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MonoControlServerTest(unittest.TestCase):
    def test_transport_and_fail_closed_routes(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-server-") as temp:
            binary = Path(temp) / "transport-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "src/mono"),
                *[str(ROOT / "src/mono" / name) for name in (
                    "cfv_mono_pref.c", "cfv_mono_control.c",
                    "cfv_mono_control_server.c")],
                str(ROOT / "tests/mono_control_server_test.c"),
                "-o", str(binary),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(binary), str(Path(temp) / "available"),
                            str(Path(temp) / "enabled")],
                           check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
