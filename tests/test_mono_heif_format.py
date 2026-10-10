"""Host-only packed-10-bit HEIF neutralizer tests; no CFV layout attestation."""
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HeifFormatTests(unittest.TestCase):
    def test_both_conditional_layouts(self):
        with tempfile.TemporaryDirectory() as folder:
            binary = Path(folder) / "mono_heif_format_test"
            subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                 "-Isrc/mono", "src/mono/cfv_mono_heif_format.c",
                 "tests/mono_heif_format_test.c", "-o", str(binary)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            result = subprocess.run([str(binary)], cwd=ROOT, check=True,
                                    capture_output=True, text=True)
            self.assertIn("conditional layouts", result.stdout)


if __name__ == "__main__":
    unittest.main()
