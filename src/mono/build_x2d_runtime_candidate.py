"""Build a first-generation X2D monochrome runtime for offline review only.

This never contacts a camera. The generated manifest is not accepted by the
Shuaqi USB installer and does not claim that the image routes are attested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE_NAMES = (
    'cfv_mono.c', 'cfv_mono_control.c', 'cfv_mono_control_server.c',
    'cfv_mono_display.c', 'cfv_mono_heif_bridge.c',
    'cfv_mono_heif_format.c', 'cfv_mono_jpeg.c', 'cfv_mono_jpeg_bridge.c',
    'cfv_mono_pref.c', 'cfv_mono_preview.c', 'cfv_mono_vmem.c',
    'x2d_mono_runtime.c', 'x2d_mono_preview_runtime.c',
    'x2d_mono_preview_pool_adapter.c',
    'x2d_mono_wayland_lease.c', 'x2d_mono_wayland_pool.c',
    'x2d_mono_wayland_proxy_hook.c',
    'x2d_mono_jpeg_runtime.c', 'x2d_mono_heif_runtime.c',
)
PINNED_FIRMWARE_SHA256 = {
    'bin/camera-service': 'fbcf828f73bca13f0c8b95e7dd0b95ac483ae36954ec06179098c8a1a65f9f82',
    'lib64/camera/plugins/disp/libdcam_disp_wayland.so': 'd8b4efa285a53287c29823b1310e3ca1d078b5b6c1c30ad5e2f2d2375516dc89',
    'lib64/camera/plugins/ienc/libdcam_ienc_jpeg.so': '8c03657d6175b6d13e382341816f2c039d04dec8162c4a52026946fc44c9eab2',
    'lib64/camera/plugins/ienc/libdcam_ienc_hevc.so': '683a5bfc844944ad93e6e0f421872bbf4ba90a639d6a804e838546cca251da58',
    'lib64/libduml_hal.so': '77875f6f47a2137e5461c61789d44fdd8537e7359c8d7b43ec7ee4737fd15bb3',
    'lib64/libduml_vcodec.so': '4c31d196cf52cff60bbb4aba7e38878d8de2f2f873592883e6ba27eaf3ddbebc',
    'lib64/libdcam_base.so': 'b6e33f0ee76e4d056e519574a0a2f3860935252010fec676be320e304a7ff81c',
}
REQUIRED_EXPORTS = (
    'duss_hal_ienc_encfrm',
    'duss_hal_heifenc_encfrm',
    'wl_proxy_destroy',
    '_ZN14WaylandControl13bufferReleaseEP9wl_buffer',
    '_ZN16WaylandControlLV9handleBufEPvRKNSt3__110shared_ptrI10MemCapsuleEE14RecommendationRK9RectangleP17duss_frame_buffer',
)


def build(clang: Path, output: Path, firmware_system: Path) -> dict:
    for name, expected in PINNED_FIRMWARE_SHA256.items():
        path = firmware_system / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('firmware 4.2.0 fingerprint mismatch: ' + name)
    sources = [ROOT / 'src' / 'mono' / name for name in SOURCE_NAMES]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError('runtime sources missing: ' + ', '.join(missing))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='x2d-mono-build-') as temp:
        elf = Path(temp) / 'libcfv_mono.so'
        subprocess.run([str(clang), '-std=c11', '-O2', '-Wall', '-Wextra',
                        '-Werror', '-fPIC', '-shared', *map(str, sources),
                        '-ldl', '-llog', '-pthread', '-o', str(elf)],
                       cwd=ROOT, check=True)
        data = elf.read_bytes()
        if len(data) < 64 or data[:5] != b'\x7fELF\x02' or data[18:20] != b'\xb7\x00':
            raise RuntimeError('compiler did not emit Android AArch64 ELF64')
        nm = clang.parent / 'llvm-nm'
        exported = subprocess.run([str(nm), '-D', '--defined-only', str(elf)],
                                  capture_output=True, text=True,
                                  check=True).stdout
        absent = [symbol for symbol in REQUIRED_EXPORTS if symbol not in exported]
        if absent:
            raise RuntimeError('runtime hook exports absent: ' + ', '.join(absent))
        manifest = {
            'format': 1,
            'variant': 'x2d-monochrome-runtime-candidate',
            'target': 'X2D 100C firmware 4.2.0',
            'module': 'libcfv_mono.so',
            'sha256': hashlib.sha256(data).hexdigest(),
            'sourceSha256': {
                name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in zip(SOURCE_NAMES, sources)
            },
            'hookExports': list(REQUIRED_EXPORTS),
            'firmwareSha256': PINNED_FIRMWARE_SHA256,
            'deviceInstallable': False,
            'reason': 'Vendor buffer ABI, lifetime, and live-view/HEIF route attestations are pending',
        }
        (output / 'libcfv_mono.so').write_bytes(data)
        (output / 'x2d-mono-runtime-candidate.json').write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--firmware-system', required=True, type=Path,
                        help='locally extracted official 4.2.0 system tree')
    args = parser.parse_args()
    print(json.dumps(build(args.clang, args.output, args.firmware_system),
                     ensure_ascii=False, indent=2))
