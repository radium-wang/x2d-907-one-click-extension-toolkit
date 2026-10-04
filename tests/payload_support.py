"""Explicit skips for private generated inputs absent from the source tree."""
import json
import unittest
import x2d_play_software as app

def payloads_ready():
    if not (app.O / 'libx2d_native_menu.so').is_file():
        return False
    try:
        manifest = json.loads((app.O / 'speed-bundle.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return bool((manifest.get('uiLanguages') or {}).get('en'))

requires_payloads = unittest.skipUnless(payloads_ready(),
    'Exact-version generated camera inputs not supplied; set X2D_PAYLOAD_DIR to run this test')