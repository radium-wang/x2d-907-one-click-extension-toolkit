"""Execute every generated stable Restore script against a local camera tree."""
import json,unittest
from unittest.mock import patch
import x2d_play_software as app
import test_auto_brightness as brightness
import test_play_software as software
from payload_support import requires_payloads
class StableRestore(unittest.TestCase):
    @requires_payloads
    def test_complete_generated_restore_executes_for_all_7_masks(self):
        manifest=app.prepare()
        for previous in (False,'previous-bundle-0.4.12.json'):
            for mask in range(1,8):
                with self.subTest(mask=mask,previous=previous):
                    fixture=brightness.BrightnessTests('test_restore_stops_display_process_and_restores_both_configs')
                    fixture.setUp()
                    try:
                        features=[name for i,name in enumerate(app.FEATURES) if mask&(1<<i)]
                        source=json.loads((app.O/previous).read_bytes()) if previous else manifest
                        selected=app.select_features(source,features)
                        generator=software.SoftwareTests('test_normal_restore_verifies_and_removes_all_known_files')
                        try:
                            # Bytes were verified before the fixture substitutes
                            # stock-config hashes; preserve that verified manifest.
                            with patch.object(app,'prepare',return_value=manifest):
                                script=generator.restore_case(features=features,previous=previous)
                        finally:generator.doCleanups()
                        root=fixture.folder/'camera';install=root/'blackbox/.x2d-play-software'
                        install.mkdir(parents=True)
                        (install/'stockrc').write_bytes(brightness.GUI)
                        (install/'stockdisplayrc').write_bytes(brightness.DISPLAY)
                        (install/'installed').write_text('INSTALLED\n')
                        for path in app.SPEED_LEVEL_FILES:
                            target=root/path.lstrip('/');target.write_text('owned fixture\n')
                        for entry in selected['files']:
                            target=root/entry['target'].lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
                            payload=app.O/'previous-payloads'/entry['sha256'] if previous else app.O/entry['source']
                            raw=payload.read_bytes();self.assertEqual(app.sha(raw),entry['sha256'])
                            target.write_bytes(raw)
                        (root/'system/etc/init').mkdir(parents=True)
                        script=script.replace(app.sha(app.init_config(brightness.GUI,mask)),app.sha(brightness.GUI))
                        display_after=brightness.DISPLAY+b'    setenv X2D_DISPLAY_RUNTIME 1\n    setenv LD_PRELOAD /system/lib64/libx2d_play_brightness.so\n'
                        script=script.replace(app.sha(display_after),app.sha(brightness.DISPLAY))
                        root,result=fixture.execute(script.replace('sleep 1','true'))
                        self.assertEqual(result.returncode,0,result.stderr)
                        self.assertIn('PLAY_SOFTWARE_RESTORED',result.stdout)
                        self.assertEqual((root/'system/etc/init/camera-gui.rc').read_bytes(),brightness.GUI)
                        self.assertEqual((root/'system/etc/init/camera-system.rc').read_bytes(),brightness.DISPLAY)
                        for path in app.SPEED_LEVEL_FILES+(app.ROOT+'/installed',):
                            self.assertFalse((root/path.lstrip('/')).exists(),(mask,path))
                        for entry in selected['files']:
                            self.assertFalse((root/entry['target'].lstrip('/')).exists(),(mask,entry['target']))
                    finally:fixture.doCleanups()
