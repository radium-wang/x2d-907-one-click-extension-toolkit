"""Read-only probe metadata contract on synthetic host descriptors."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MonoVendorProbeTest(unittest.TestCase):
    def test_metadata_only_parser(self):
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="cfv-mono-probe-") as temp:
            binary = Path(temp) / "probe-test"
            subprocess.run([
                compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DCFV_MONO_PROBE_HOST_TEST", "-I", str(ROOT / "src/mono"),
                str(ROOT / "src/mono/cfv_mono_vendor_probe.c"),
                str(ROOT / "tests/mono_vendor_probe_test.c"),
                "-o", str(binary),
            ], check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True,
                           text=True)


if __name__ == "__main__":
    unittest.main()
