from payload_support import requires_payloads
"""Offline checks: version gates, immutable payloads and interrupted restore paths."""
import json, unittest
from unittest.mock import patch
import x2d_play_software as app

RAW=b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n    class core\n'

class SoftwareTests(unittest.TestCase):
    @requires_payloads
    def test_bundle_verifies_four_installable_features(self):
        manifest=app.prepare()
        self.assertEqual(manifest['features'],['afc','speed-buff','auto-rear-brightness','eye-detection'])
        self.assertEqual(manifest['entryIndex'],11)
        self.assertFalse(manifest['lensRestriction'])

    def test_init_rejects_unrecognized_firmware(self):
        with self.assertRaises(RuntimeError): app.init_config(b'unknown')

    def test_boot_uses_trusted_entry_and_both_preloads(self):
        with patch.object(app,'STOCK_RC',app.sha(RAW)):
            rc=app.init_config(RAW)
            self.assertIn(b'service x2d-speed-buff /system/bin/camera-gui --x2d-speed-server',rc)
            self.assertIn(b'LD_PRELOAD /system/lib64/libx2d_native_menu.so',rc)
            self.assertIn(b'LD_PRELOAD /system/lib64/libx2d_speed_server.so',rc)
            self.assertNotIn(b'eye',rc)

    def test_stock_connection_check_rejects_unknown_init(self):
        with patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'verify_target'),patch.object(app,'shell',side_effect=['NO','unknown hash']),patch.object(app,'event'):
            with self.assertRaisesRegex(RuntimeError,'非原厂'):
                app.status()

    def test_broken_service_does_not_block_usb_recovery(self):
        with patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'verify_target') as verify,patch.object(app,'shell',return_value='YES'),patch.object(app,'read_bytes',return_value=b'INSTALLED'),patch.object(app,'verify_installed_integrity'),patch.object(app,'backend',side_effect=RuntimeError('unavailable')),patch.object(app,'event') as event:
            app.status()
            self.assertEqual(verify.call_count,2)
            args=event.call_args.kwargs
            self.assertTrue(args['connected']);self.assertTrue(args['recovery'])
            self.assertEqual(args['firmware'],'4.2.0')

    def test_unknown_actions_never_reach_transport(self):
        with patch.object(app,'shell') as transport:
            with self.assertRaises(RuntimeError): app.backend('enable;reboot')
            transport.assert_not_called()

    def test_failed_worker_never_reports_old_state(self):
        with patch.object(app,'verify_installed_integrity',return_value={'featureMask':7}),patch.object(app,'shell',return_value=''),patch.object(app,'read_bytes') as read:
            with self.assertRaises(RuntimeError): app.backend('master_off')
            read.assert_not_called()

    def restore_case(self,phase='INSTALLED',ledger=None,rc=None,active=False,previous=False,partial=None,features=None,state_extra=None,recovery_ok=True):
        m=json.loads((app.O/(previous if isinstance(previous,str) else 'previous-bundle.json')).read_bytes()) if previous else app.prepare()
        if features is not None:m=app.select_features(m,features)
        targets=[f['target'] for f in m['files']]
        ledger=targets if ledger is None else ledger
        uploads={}
        self.last_restore_uploads=uploads
        with patch.object(app,'STOCK_RC',app.sha(RAW)):
            modified=app.init_config(RAW,m.get('featureMask'))
            m.update(initBefore=app.sha(RAW),initAfter=app.sha(modified))
            data={app.ROOT+'/manifest':json.dumps(m).encode(),app.ROOT+'/stockrc':RAW,
                  app.ROOT+'/installed':phase.encode(),app.ROOT+'/created':' '.join(ledger).encode(),
                  app.RC:modified if rc is None else rc,
                  '/tmp/x2d-speed-buff/ui.json':json.dumps(dict(ready=True,active=active,afc=False,master=False,**(state_extra or {}))).encode()}
            if m.get('autoBrightness'):
                display_raw=b'service camera-system /system/bin/camera-system\n    class core\n'
                display_rc=display_raw+b'    setenv X2D_DISPLAY_RUNTIME 1\n    setenv LD_PRELOAD /system/lib64/libx2d_play_brightness.so\n'
                display_patch=patch.object(app,'init_display_config',return_value=display_rc);display_patch.start();self.addCleanup(display_patch.stop)
                m.update(displayInitBefore=app.DISPLAY_STOCK_RC,displayInitAfter=app.sha(display_rc))
                data[app.ROOT+'/manifest']=json.dumps(m).encode()
                data[app.ROOT+'/stockdisplayrc']=display_raw;data[app.DISPLAY_RC]=display_rc
            data.update(partial or {})
            def shell(command):
                if command.startswith('test -e '):
                    return 'YES' if '/installed' in command or any(path in command for path in (partial or {})) else 'NO'
                if command=='sh '+app.STAGE+'/recover && echo ACTION_FINISHED || echo RECOVERY_FAILED':
                    return 'ACTION_FINISHED' if recovery_ok else 'RECOVERY_FAILED'
                if command=='sh '+app.STAGE+'/restore': return 'PLAY_SOFTWARE_RESTORED'
                raise AssertionError(command)
            with patch.object(app,'verify_target'),patch.object(app,'ensure_adb'),patch.object(app,'shell',side_effect=shell),patch.object(app,'read_bytes',side_effect=lambda p:data[p]),patch.object(app,'upload',side_effect=lambda n,b:uploads.update({n:b})),patch.object(app,'event'),patch.object(app,'reboot_and_verify') as reboot:
                app.restore()
                if m.get('autoBrightness'): reboot.assert_called_once_with(False,auto_brightness=True)
                else: reboot.assert_called_once_with(False)
        return uploads['restore'].decode()

    @requires_payloads
    def test_033_normal_and_partial_restore_keep_exact_old_hashes(self):
        old=json.loads((app.O/'previous-bundle-0.3.3.json').read_bytes())
        script=self.restore_case(previous='previous-bundle-0.3.3.json')
        for entry in old['files']:self.assertIn('hashok '+entry['target']+' '+entry['sha256'],script)
        for entry in old['files']:
            if entry['source'] not in ('X2dNativeMenuBootstrap.qml','libx2d_speed_server.so','libx2d_native_menu.so'):continue
            raw=(app.O/'previous-payloads'/entry['sha256']).read_bytes()
            self.assertEqual(app.sha(raw),entry['sha256'])
            part=raw[:min(5000,len(raw)//2)]
            script=self.restore_case('PREPARED',[entry['target']],RAW,previous='previous-bundle-0.3.3.json',partial={entry['target']:part})
            self.assertIn('hashok '+entry['target']+' '+app.sha(part),script)

    @requires_payloads
    def test_normal_restore_verifies_and_removes_all_known_files(self):
        script=self.restore_case()
        self.assertIn('echo RESTORING',script)
        self.assertIn('rm -f '+app.prepare()['files'][0]['target'],script)
        self.assertIn('mount -o remount,ro',script)

    @requires_payloads
    def test_partial_install_can_restore_only_created_paths(self):
        script=self.restore_case('PREPARED',[app.prepare()['files'][0]['target']],RAW)
        self.assertIn('rm -f '+app.prepare()['files'][0]['target'],script)
        self.assertNotIn('rm -f /system/etc/x2d-speed-buff/worker',script)

    @requires_payloads
    def test_interrupted_restore_accepts_original_prefix(self):
        self.restore_case('RESTORING',[app.prepare()['files'][0]['target']],RAW[:10])

    @requires_payloads
    def test_foreign_ledger_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'恢复路径清单'):
            self.restore_case('PREPARED',['/system/bin/camera-service'])

    @requires_payloads
    def test_foreign_init_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'启动配置不是'):
            self.restore_case('PREPARED',[app.prepare()['files'][0]['target']],b'foreign')

    @requires_payloads
    def test_active_patch_prevents_file_removal(self):
        with self.assertRaisesRegex(RuntimeError,'功能撤回'):
            self.restore_case(active=True)

    @requires_payloads
    def test_eye_restoration_must_be_confirmed_before_files_can_be_removed(self):
        for state in ({},dict(eyeRestored=False,eyeEnabled=False),dict(eyeRestored=True,eyeEnabled=True)):
            with self.subTest(state=state),self.assertRaisesRegex(RuntimeError,'人眼识别设置撤回尚未确认'):
                self.restore_case(features=['eye-detection'],state_extra=state)
            self.assertNotIn('restore',self.last_restore_uploads)

    @requires_payloads
    def test_failed_eye_recovery_cannot_approve_uninstall_using_an_old_ready_state(self):
        with self.assertRaisesRegex(RuntimeError,'功能撤回未完成'):
            self.restore_case(features=['eye-detection'],state_extra=dict(eyeRestored=True,eyeEnabled=False),recovery_ok=False)
        self.assertNotIn('restore',self.last_restore_uploads)

    @requires_payloads
    def test_eye_restore_uses_verified_recovery_worker_and_selected_mask(self):
        self.restore_case(features=['eye-detection'],state_extra=dict(eyeRestored=True,eyeEnabled=False))
        control=self.last_restore_uploads['recover'].decode()
        self.assertIn('export X2D_FEATURE_MASK=8\n',control)
        self.assertIn('/recovery eye_restore\n',control)
        self.assertEqual(self.last_restore_uploads['recovery'],(app.O/'speed-worker').read_bytes())

    @requires_payloads
    def test_previous_bundle_restores_using_its_exact_installed_hash(self):
        previous=json.loads((app.O/'previous-bundle.json').read_bytes())
        self.assertLessEqual({f['target'] for f in previous['files']},{f['target'] for f in app.prepare()['files']})
        script=self.restore_case(previous=True)
        old=next(f for f in previous['files'] if f['source']=='libx2d_speed_server.so')
        self.assertIn('hashok '+old['target']+' '+old['sha256'],script)

    @requires_payloads
    def test_previous_bundle_metadata_must_match_pinned_hash(self):
        previous=json.loads((app.O/'previous-bundle.json').read_bytes())
        with patch.object(app,'PREVIOUS_BUNDLE_SHA','0'*64):
            with self.assertRaisesRegex(RuntimeError,'已知旧版清单校验失败'): app.recognized_bundle(previous)

    @requires_payloads
    def test_foreign_previous_manifest_is_rejected(self):
        previous=json.loads((app.O/'previous-bundle.json').read_bytes())
        previous['files'][0]['target']='/system/bin/camera-service'
        self.assertFalse(app.recognized_bundle(previous))

    @requires_payloads
    def test_known_upgrade_finishes_guarded_restore_before_reinstall(self):
        entry=app.install;previous=json.loads((app.O/'previous-bundle.json').read_bytes())
        data=[b'INSTALLED',json.dumps(previous).encode()]
        calls=unittest.mock.Mock()
        with patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'verify_target'),patch.object(app,'shell',return_value='YES'), \
             patch.object(app,'read_bytes',side_effect=data),patch.object(app,'event') as events, \
             patch.object(app,'verify_installed_integrity'),patch.object(app,'confirm_reinstall',return_value=True),patch.object(app,'restore') as restore,patch.object(app,'install') as install:
            calls.attach_mock(restore,'restore');calls.attach_mock(install,'install')
            entry()
            self.assertEqual(calls.mock_calls,[unittest.mock.call.restore(True,report_result=False),unittest.mock.call.install(True,False,'zh')])
            self.assertFalse(any(call.args[0]=='result' for call in events.call_args_list))

    @requires_payloads
    def test_failed_upgrade_restore_never_reaches_install(self):
        entry=app.install;previous=json.loads((app.O/'previous-bundle.json').read_bytes())
        with patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'verify_target'),patch.object(app,'shell',return_value='YES'), \
             patch.object(app,'read_bytes',side_effect=[b'INSTALLED',json.dumps(previous).encode()]), \
             patch.object(app,'event'),patch.object(app,'verify_installed_integrity'),patch.object(app,'confirm_reinstall',return_value=True),patch.object(app,'restore',side_effect=RuntimeError('恢复未完成')), \
             patch.object(app,'install') as install:
            with self.assertRaisesRegex(RuntimeError,'恢复未完成'): entry()
            install.assert_not_called()

    def test_internal_restore_never_reports_completion_to_desktop(self):
        with patch.object(app,'camera_model',return_value='X2D 100C'),patch.object(app,'verify_target'),patch.object(app,'verify_stock_installation'),patch.object(app,'prepare',return_value={'autoBrightness':True}),patch.object(app,'shell',side_effect=['NO',app.STOCK_RC+' file',app.DISPLAY_STOCK_RC+' file']), \
             patch.object(app,'event') as events:
            app.restore(report_result=False)
        self.assertFalse(any(call.args[0]=='result' for call in events.call_args_list))

    @requires_payloads
    def test_previous_partial_boot_service_restores_with_original_version_prefix(self):
        target='/system/lib64/libx2d_speed_server.so'
        partial=(app.O/'previous-speed-server.so').read_bytes()[:5000]
        script=self.restore_case('PREPARED',[target],RAW,previous=True,partial={target:partial})
        self.assertIn('hashok '+target+' '+app.sha(partial),script)

    @requires_payloads
    def test_foreign_partial_boot_service_is_rejected(self):
        target='/system/lib64/libx2d_speed_server.so'
        with self.assertRaisesRegex(RuntimeError,'中断文件内容不是'):
            self.restore_case('PREPARED',[target],RAW,previous=True,partial={target:b'foreign'})

if __name__=='__main__': unittest.main()
