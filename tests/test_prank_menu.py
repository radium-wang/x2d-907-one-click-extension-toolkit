from payload_support import requires_payloads
"""Read-only model matching and fail-closed optional menu configuration."""
import json,unittest
from unittest.mock import patch
import x2d_play_software as app
from windows_app import Session

class PrankTests(unittest.TestCase):
    def test_exact_stock_model_pairs(self):
        for value,expected in [('0x0009\nX2D 100C','X2D 100C'),('0x000A\nCFV 100C','907X & CFV 100C')]:
            with patch.object(app,'shell',return_value=value):self.assertEqual(app.camera_model(),expected)
        for value in ['0x0009\nCFV 100C','0x000A\nX2D 100C','907X','0x000B\nCFV 100C','']:
            with patch.object(app,'shell',return_value=value),self.assertRaises(RuntimeError):app.camera_model()

    @requires_payloads
    def test_optional_install_rejects_x2d_before_upload(self):
        with patch.object(app,'verify_target'),patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'upload') as upload,patch.object(app,'event'):
            with self.assertRaisesRegex(RuntimeError,'仅适用'):app.install(prank_ibis=True)
            upload.assert_not_called()

    @requires_payloads
    def test_checkbox_choice_upgrade_retained(self):
        current=app.prepare();current['prankIbis']=False
        real_install=app.install
        with patch.object(app,'verify_target'),patch.object(app,'verify_installed_integrity'),patch.object(app,'camera_model',return_value='907X & CFV 100C'),patch.object(app,'shell',return_value='YES'),patch.object(app,'read_bytes',side_effect=[b'INSTALLED',json.dumps(current).encode()]),patch.object(app,'event'),patch.object(app,'confirm_reinstall',return_value=True),patch.object(app,'restore') as restore,patch.object(app,'install') as install:
            real_install(prank_ibis=True)
            restore.assert_called_once_with(True,report_result=False);install.assert_called_once_with(True,True,'zh')

    def test_reboot_never_accepts_eleven_tiles_when_joke_requested(self):
        for marker in ['MENU_ENTRY_READY_11','MENU_ENTRY_READY_12']:
            values=['REBOOT_DISPATCHED','running','running','MENU_AND_AFC_SWITCHABLE_READY',marker]
            with patch.object(app,'verify_target'),patch.object(app,'event') as event,patch.object(app,'shell',side_effect=values),patch.object(app,'backend',return_value={'ready':True,'prankIbis':True}),patch.object(app.time,'sleep'),patch.object(app.time,'monotonic',side_effect=[0,1,72]):
                if marker.endswith('11'):
                    with self.assertRaisesRegex(RuntimeError,'彩蛋菜单'):app.reboot_and_verify(True,prank_ibis=True)
                    self.assertFalse(any(c.args[0]=='result' for c in event.call_args_list))
                else:
                    app.reboot_and_verify(True,prank_ibis=True);self.assertTrue(event.call_args.kwargs['success'])

    def test_windows_model_is_revoked_on_error_and_recheck(self):
        for action in ['error','recheck']:
            session=Session();session.consume({'type':'status','connected':True,'firmware':'4.2.0','model':'907X & CFV 100C'})
            self.assertEqual(session.model,'907X & CFV 100C')
            if action=='error':session.consume({'type':'error'})
            else:session.start('status')
            self.assertEqual(session.model,'');self.assertFalse(session.verified)

    @requires_payloads
    def test_known_032_manifest_and_previous_payloads_remain_exact(self):
        raw=(app.O/'previous-bundle-0.3.2.json').read_bytes();self.assertEqual(app.sha(raw),app.PREVIOUS_032_SHA)
        manifest=json.loads(raw);self.assertTrue(app.recognized_bundle(manifest))
        for f in manifest['files']:
            self.assertEqual(app.sha((app.O/'previous-payloads'/f['sha256']).read_bytes()),f['sha256'])

if __name__=='__main__':unittest.main()
