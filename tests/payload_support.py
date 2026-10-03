"""Explicit skips for private generated inputs absent from the source tree."""
import unittest
import x2d_play_software as app
requires_payloads = unittest.skipUnless((app.O/'libx2d_native_menu.so').is_file(),
    'Exact-version generated camera inputs not supplied; set X2D_PAYLOAD_DIR to run this test')
