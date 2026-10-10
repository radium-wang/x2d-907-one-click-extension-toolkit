"""Build the X2D observation probe locally; never contacts a camera.

The generated ELF/manifest are deliberately ignored by git.  This is an
observation-only first-stage diagnostic, not a monochrome rendering module.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
STOCK_RC_SHA256 = "2aa2c06efcc2d7fac690f7fe5db324e12f02748fb7d368ee5f726c3d5b24f2a9"


def build(clang: Path, output: Path):
    source = ROOT / "src/mono/cfv_mono_vendor_probe.c"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "tests/test_mono_vendor_probe.py")],
                   check=True, cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix="cfv-mono-probe-") as temp:
        temporary = Path(temp) / "libcfv_mono.so"
        subprocess.run([str(clang), "-std=c11", "-O2", "-Wall", "-Wextra",
                        "-Werror", "-fPIC", "-shared", str(source), "-ldl",
                        "-llog", "-o", str(temporary)], check=True, cwd=ROOT)
        data = temporary.read_bytes()
        if len(data) < 64 or data[:5] != b"\x7fELF\x02" or data[18:20] != b"\xb7\x00":
            raise RuntimeError("compiler did not emit AArch64 ELF64")
        manifest = {
            "format": 1,
            "variant": "probe",
            "probeContract": "observation-only-no-output-mutation-v1",
            "source": "libcfv_mono.so",
            "sha256": hashlib.sha256(data).hexdigest(),
            "stockServiceRcSha256": STOCK_RC_SHA256,
            "targetModels": ["X2D 100C"],
            "readyForDeviceTest": True,
        }
        (output / "libcfv_mono.so").write_bytes(data)
        (output / "mono-module.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clang", required=True, type=Path,
                        help="reviewed Android NDK AArch64 clang")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "src/native-package")
    args = parser.parse_args()
    print(json.dumps(build(args.clang, args.output), indent=2))
