"""Read-only preflight: modified cameras never reach ADB, upload or reboot."""
import copy
import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import x2d_play_software as app
import windows_app

GUI_RC = b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n    class core\n'
DISPLAY_RC = b'service camera-system /system/bin/camera-system\n    class core\n'


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(app, 'STOCK_RC', app.sha(GUI_RC)))
        self.stack.enter_context(patch.object(app, 'DISPLAY_STOCK_RC', app.sha(DISPLAY_RC)))
        self.gui_rc = app.init_config(GUI_RC)
        self.display_rc = app.init_display_config(DISPLAY_RC)
        self.target = '/system/etc/X2dAfcMenuController.qml'
        self.files = {self.target: b'known controller'}
        self.manifest = dict(format=3, guiSha256=app.STOCK_GUI,
                             files=[dict(source='controller.qml', target=self.target,
                                         sha256=app.sha(self.files[self.target]))],
                             initBefore=app.STOCK_RC, initAfter=app.sha(self.gui_rc))
        self.data = {app.ROOT + '/installed': b'INSTALLED',
                     app.ROOT + '/manifest': json.dumps(self.manifest).encode(),
                     app.ROOT + '/stockrc': GUI_RC,
                     app.ROOT + '/created': self.target.encode(),
                     app.RC: self.gui_rc, app.DISPLAY_RC: DISPLAY_RC, **self.files}
        self.installed = True
        self.symlinks = set()
        self.stack.enter_context(patch.object(app, 'prepare', side_effect=lambda: copy.deepcopy(self.manifest)))
        self.stack.enter_context(patch.object(app, 'read_bytes', side_effect=lambda path: self.data[path]))
        self.stack.enter_context(patch.object(app, 'shell', side_effect=self.shell))
        self.events = self.stack.enter_context(patch.object(app, 'event'))
        self.adb = self.stack.enter_context(patch.object(app, 'ensure_adb'))
        self.upload = self.stack.enter_context(patch.object(app, 'upload'))
        self.reboot = self.stack.enter_context(patch.object(app, 'reboot_and_verify'))
        self.restore = self.stack.enter_context(patch.object(app, 'restore'))

    def shell(self, command):
        if command.startswith('test ! -L ') and ' && sha256sum ' in command:
            path = command.split(' && sha256sum ')[1].split(' || ')[0]
            return 'INTEGRITY_MISMATCH' if path in self.symlinks or path not in self.data else app.sha(self.data[path])+' '+path
        if command.startswith('if [ -e '):
            path = command.split()[3]
            return 'PRESENT' if path in self.data or path in self.symlinks else 'ABSENT'
        if command == f'test -e {app.ROOT}/installed && echo YES || echo NO':
            return 'YES' if self.installed else 'NO'
        if command.startswith('cat /tmp/x2d-native-menu-ui.ready'):
            return 'MENU_ENTRY_READY_11'
        raise AssertionError(command)

    def assert_no_writes(self):
        for operation in (self.adb, self.upload, self.reboot, self.restore):
            operation.assert_not_called()

    def make_stock(self):
        self.installed = False
        self.data[app.RC] = GUI_RC
        self.data.pop(self.target)

    def test_exact_own_install_is_recognized_but_tampered_controller_is_rejected(self):
        self.assertEqual(app.verify_installed_integrity(), self.manifest)
        self.data[self.target] = b'foreign AF-C controller'
        with self.assertRaisesRegex(RuntimeError, '非原厂'):
            app.verify_installed_integrity()
        self.assert_no_writes()

    def test_modified_gui_error_names_recovery_instead_of_usb_failure(self):
        reader = MagicMock()
        reader.factory_shell.side_effect = [app.usb.EXPECTED_X2D_DEVICE, '0'*64+' /system/bin/camera-gui']
        with self.assertRaises(app.usb.UsbFactoryError) as failure:
            app.usb.validate_factory_gui_target(reader)
        message = app.user_error(failure.exception)
        self.assertIn('camera-gui', message)
        self.assertIn('恢复原厂', message)
        self.assertNotIn('USB 通信', message)
        self.assert_no_writes()

    def test_current_version_with_changed_files_cannot_report_already_installed(self):
        self.data[self.target] = b'foreign'
        with patch.object(app, 'verify_target'), patch.object(app, 'backend') as backend:
            with self.assertRaisesRegex(RuntimeError, '非原厂'):
                app.install()
            backend.assert_not_called()
        self.assertFalse(any(call.args[0] == 'result' for call in self.events.call_args_list))
        self.assert_no_writes()

    def test_receipt_and_ready_service_cannot_hide_file_tampering(self):
        self.data[self.target] = b'foreign'
        with patch.object(app, 'verify_target'), patch.object(app, 'camera_model', return_value='X2D 100C'), patch.object(app, 'backend', return_value={'ready': True}) as backend:
            with self.assertRaisesRegex(RuntimeError, '非原厂'):
                app.status()
            backend.assert_not_called()
        self.assertFalse(any(call.args[0] == 'status' for call in self.events.call_args_list))
        self.assert_no_writes()

    def test_display_startup_modification_blocks_first_install_before_adb(self):
        self.make_stock()
        self.data[app.DISPLAY_RC] += b'    setenv LD_PRELOAD /system/lib64/foreign.so\n'
        with patch.object(app, 'verify_target'):
            with self.assertRaisesRegex(RuntimeError, 'camera-system.rc'):
                app.install()
        self.assert_no_writes()

    def test_orphan_afc_payload_blocks_first_install_before_adb(self):
        self.make_stock()
        self.data[self.target] = b'foreign AF-C'
        with patch.object(app, 'verify_target'):
            with self.assertRaisesRegex(RuntimeError, '非原厂'):
                app.install()
        self.assert_no_writes()

    def test_clean_stock_status_passes_without_any_camera_write(self):
        self.make_stock()
        with patch.object(app, 'verify_target'), patch.object(app, 'camera_model', return_value='X2D 100C'):
            app.status()
        self.assertEqual(self.events.call_args.args[0], 'status')
        self.assertFalse(self.events.call_args.kwargs['installed'])
        self.assert_no_writes()

    def test_missing_files_symlinks_and_duplicate_ledger_fail_closed(self):
        for case in ('missing', 'symlink', 'ledger'):
            with self.subTest(case=case):
                self.data[self.target] = self.files[self.target]
                self.data[app.ROOT+'/created'] = self.target.encode()
                self.symlinks.clear()
                if case == 'missing': self.data.pop(self.target)
                if case == 'symlink': self.symlinks.add(self.target)
                if case == 'ledger': self.data[app.ROOT+'/created'] += b' '+self.target.encode()
                with self.assertRaisesRegex(RuntimeError, '非原厂'):
                    app.verify_installed_integrity()
        self.assert_no_writes()

    def test_unknown_manifest_and_transaction_do_not_offer_own_recovery(self):
        self.data[app.ROOT+'/installed'] = b'FOREIGN'
        with patch.object(app, 'verify_target'), patch.object(app, 'camera_model', return_value='X2D 100C'):
            with self.assertRaisesRegex(RuntimeError, '非原厂'):
                app.status()
        self.assertFalse(any(call.args[0] == 'status' for call in self.events.call_args_list))
        self.assert_no_writes()

    def test_every_core_guard_rejects_unknown_bytes_before_status_or_upload(self):
        expected = {'/system/lib64/libaaa.so': 'feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7',
                    '/system/bin/camera-service': 'fbcf828f73bca13f0c8b95e7dd0b95ac483ae36954ec06179098c8a1a65f9f82',
                    '/system/lib64/librcam.so': '72ebc8deebce4a29047c475e77ab4edbf2860abb1f572fea45260fe17ad0bda5',
                    '/system/bin/camera-system': app.DISPLAY_SYSTEM_SHA,
                    '/system/etc/init/camera-service.rc': app.STOCK_SERVICE_RC}
        for failed in expected:
            def output(command):
                path = command.split(' && sha256sum ')[1].split(' || ')[0]
                return ('0'*64 if path == failed else expected[path])+' '+path
            with self.subTest(path=failed), patch.object(app, 'reader'), patch.object(app.usb, 'validate_factory_gui_target'), patch.object(app, 'shell', side_effect=output):
                with self.assertRaisesRegex(RuntimeError, '非原厂'):
                    app.verify_target()
        self.assert_no_writes()

    def test_windows_error_revokes_install_and_restore_gates(self):
        session = windows_app.Session()
        session.start('status')
        session.consume(dict(type='status', connected=True, firmware='4.2.0', model='X2D 100C'))
        session.finish(0)
        session.start('status')
        session.consume(dict(type='error', message=app.NONSTOCK_GUIDANCE))
        session.finish(1)
        self.assertFalse(session.start('install'))
        self.assertFalse(session.start('restore'))


if __name__ == '__main__':
    unittest.main()
