"""Selected capabilities survive boot config, recognition and worker guards."""
import copy
import json
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

    def test_all_fifteen_combinations_are_recognized_and_tampering_is_rejected(self):
        with patch.object(app, 'prepare', return_value=self.manifest):
            for mask in range(1, 16):
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
            for choice in ('true',1,None):
                self.assertFalse(app.recognized_bundle(dict(selected,prankIbis=choice)))

    def test_gui_and_service_receive_the_same_validated_mask(self):
        stock = b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n'
        with patch.object(app, 'STOCK_RC', app.sha(stock)):
            for mask in range(1, 16):
                self.assertEqual(app.init_config(stock, mask).count(f'setenv X2D_FEATURE_MASK {mask}\n'.encode()), 2)
            self.assertNotIn(b'FEATURE_MASK', app.init_config(stock))
            for mask in (0, 16, True, '3'):
                with self.assertRaises(RuntimeError): app.init_config(stock, mask)

    def test_uninstalled_worker_actions_stop_before_touching_camera_paths(self):
        worker = Path(__file__).resolve().parents[1] / 'src/speed-buff-worker.sh'
        for mask, action in [('1', 'enable'), ('4', 'enable'), ('6', 'afc_on'), ('0', 'status'), ('16', 'status'),('7','eye_on')]:
            result = subprocess.run(['sh', str(worker), action], env=dict(os.environ, X2D_FEATURE_MASK=mask), capture_output=True)
            self.assertEqual(result.returncode, 38, result.stderr)
            self.assertEqual(result.stdout + result.stderr, b'')

    def test_desktop_eye_actions_require_installed_feature_and_confirmed_readback(self):
        with patch.object(app, 'verify_installed_integrity', return_value={'featureMask':7}), patch.object(app,'shell') as command:
            with self.assertRaisesRegex(RuntimeError,'安装包不包含所选功能'):
                app.backend('eye_on')
            command.assert_not_called()
        for action,wanted in [('eye_on',True),('eye_off',False)]:
            for state in [{'eyeReady':False,'eyeActive':wanted}, {'eyeReady':True,'eyeActive':not wanted}, {'eyeReady':True,'eyeActive':wanted}]:
                with self.subTest(action=action,state=state), patch.object(app,'verify_installed_integrity',return_value={'featureMask':8}), patch.object(app,'shell',return_value='ACTION_FINISHED') as command, patch.object(app,'read_bytes',return_value=json.dumps(state).encode()):
                    if state['eyeReady'] and state['eyeActive']==wanted:
                        self.assertEqual(app.backend(action),state)
                    else:
                        with self.assertRaisesRegex(RuntimeError,'未通过回读'):app.backend(action)
                    command.assert_called_once_with('X2D_FEATURE_MASK=8 sh /system/etc/x2d-speed-buff/worker '+action+' && echo ACTION_FINISHED')

    def test_legacy_master_disable_passes_its_original_three_feature_mask(self):
        with patch.object(app,'verify_installed_integrity',return_value={}), patch.object(app,'shell',return_value='ACTION_FINISHED') as command, patch.object(app,'read_bytes',return_value=b'{}'):
            app.backend('master_off')
        command.assert_called_once_with('X2D_FEATURE_MASK=7 sh /system/etc/x2d-speed-buff/worker master_off && echo ACTION_FINISHED')
