"""Selected capabilities survive boot config, recognition and worker guards."""
import copy
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import x2d_play_software as app


class FeatureSelectionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = dict(format=3, guiSha256=app.STOCK_GUI, files=[dict(source='brightness.so', target='/system/lib64/libx2d_play_brightness.so', sha256='brightness'),
                                    dict(source='worker', target='/system/etc/x2d-speed-buff/worker', sha256='worker')],
                             autoBrightness={'default': 'off'})

        self.manifest['uiLanguages'] = {language: copy.deepcopy(self.manifest['files']) for language in ('en','zh-Hant')}

    def test_all_seven_combinations_are_recognized_and_tampering_is_rejected(self):
        with patch.object(app, 'prepare', return_value=self.manifest):
            for mask in range(1, 8):
                features = [f for i, f in enumerate(app.FEATURES) if mask & (1 << i)]
                selected = app.select_features(self.manifest, features)
                self.assertEqual(selected['featureMask'], mask)
                self.assertEqual('autoBrightness' in selected, bool(mask & 4))
                self.assertEqual(len(selected['files']), 2 if mask & 4 else 1)
                self.assertTrue(app.recognized_bundle(selected))
                changed = copy.deepcopy(selected); changed['featureMask'] = mask ^ 1
                self.assertFalse(app.recognized_bundle(changed))
                changed = copy.deepcopy(selected); changed['files'][0]['sha256'] = 'foreign'
                self.assertFalse(app.recognized_bundle(changed))
        self.assertNotIn('featureMask', self.manifest)
        for features in ([], ['afc', 'afc'], ['foreign']):
            with self.assertRaises(RuntimeError): app.select_features(self.manifest, features)
        with patch.object(app,'prepare',return_value=self.manifest):
            selected=app.select_features(self.manifest,['afc'])
            for mask,features in [(True,['afc']),(0,['afc']),(1,[]),(1,['afc','afc']),(1,[None])]:
                altered=dict(selected,featureMask=mask,selectedFeatures=features)
                self.assertFalse(app.recognized_bundle(altered))

    def test_gui_and_service_receive_the_same_validated_mask(self):
        stock = b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n'
        with patch.object(app, 'STOCK_RC', app.sha(stock)):
            for mask in range(1, 8):
                self.assertEqual(app.init_config(stock, mask).count(f'setenv X2D_FEATURE_MASK {mask}\n'.encode()), 2)
            self.assertNotIn(b'FEATURE_MASK', app.init_config(stock))
            for mask in (0, 8, True, '3'):
                with self.assertRaises(RuntimeError): app.init_config(stock, mask)

    def test_uninstalled_worker_actions_stop_before_touching_camera_paths(self):
        worker = Path(__file__).resolve().parents[1] / 'src/speed-buff-worker.sh'
        for mask, action in [('1', 'enable'), ('4', 'enable'), ('6', 'afc_on'), ('0', 'status'), ('8', 'status')]:
            result = subprocess.run(['sh', str(worker), action], env=dict(os.environ, X2D_FEATURE_MASK=mask), capture_output=True)
            self.assertEqual(result.returncode, 38, result.stderr)
            self.assertEqual(result.stdout + result.stderr, b'')
