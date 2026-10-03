from payload_support import requires_payloads
"""无设备检查：Windows 写入门控、USB ADB 选择与共用固件门禁。"""
import unittest
from unittest.mock import MagicMock, patch
import windows_app
import x2d_play_software as app

class DesktopTests(unittest.TestCase):
    def test_connection_is_required_and_busy_rejects_duplicate_actions(self):
        session = windows_app.Session()
        self.assertFalse(session.start('install'))
        self.assertTrue(session.start('status'))
        self.assertFalse(session.start('status'))
        session.consume(dict(type='status', connected=True, firmware='4.2.0'))
        self.assertTrue(session.finish(0))
        self.assertTrue(session.start('install'))

    def test_unknown_firmware_and_failed_check_never_enable_writes(self):
        for event in [dict(type='status', connected=True, firmware='4.1.0'),
                      dict(type='status', connected=False, firmware='4.2.0'),
                      dict(type='error', message='连接失败')]:
            session = windows_app.Session(); session.start('status'); session.consume(event)
            session.finish(0)
            self.assertFalse(session.start('restore'))

    def test_rechecking_revokes_existing_connection_and_incomplete_process_fails(self):
        session = windows_app.Session(); session.verified = True
        session.start('status'); self.assertFalse(session.verified)
        self.assertFalse(session.finish(0))
        self.assertFalse(session.start('install'))

    def test_windows_adb_omits_usb_path_but_network_and_wrong_model_are_rejected(self):
        output = '\n'.join(['usb-camera device product:eagle2 device:eagle2_ec1706_native',
            '192.0.2.1:5555 device device:eagle2_ec1706_native',
            'other-camera device usb:1 device:other-model',
            'bad-camera unauthorized device:eagle2_ec1706_native'])
        with patch.object(app.os, 'name', 'nt'):
            self.assertEqual(app.physical_adb_candidates(output), ['usb-camera'])
        with patch.object(app.os, 'name', 'posix'):
            self.assertEqual(app.physical_adb_candidates(output), [])

    def test_same_gui_with_different_focus_library_is_rejected(self):
        with patch.object(app, 'reader', return_value=MagicMock()), \
             patch.object(app.usb, 'validate_factory_gui_target'), \
             patch.object(app, 'shell', return_value='0'*64+' /system/lib64/libaaa.so'):
            with self.assertRaisesRegex(RuntimeError, '关键文件'):
                app.verify_target()

    @requires_payloads
    def test_candidate_lists_both_models_with_separate_evidence(self):
        manifest = app.prepare()
        self.assertIn('907X & CFV 100C', manifest['compatibleModels'])
        self.assertIn('awaiting-device-test', manifest['validation']['907X & CFV 100C'])

    def test_windows_still_checks_uploaded_script_on_camera(self):
        data = b'#!/system/bin/sh\nset -eu\necho SAFE\n'
        responses = ['SAFE', app.sha(data)+' file', 'SYNTAX_OK']
        with patch.object(app, 'shell', side_effect=responses) as shell, \
             patch.object(app, 'adb_call', return_value=MagicMock(returncode=0)):
            app.upload('install', data)
        self.assertIn('sh -n ', shell.call_args.args[0])

    def test_explicit_error_survives_failed_worker_exit(self):
        session = windows_app.Session(); session.start('status')
        session.consume(dict(type='error', message='USB 工厂接口无法打开'))
        self.assertFalse(session.finish(1))
        self.assertTrue(session.error_received)
        self.assertFalse(session.verified)

    def test_usb_runtime_failure_is_structured_without_opening_camera(self):
        with patch.object(app.os, 'name', 'posix'), patch.object(app, 'USB_RUNTIME_ERROR', True), patch.object(app.usb, 'FactoryUsbReader') as transport:
            with self.assertRaises(app.usb.UsbFactoryError) as error: app.reader()
            self.assertIn('运行库加载失败', app.user_error(error.exception))
            transport.assert_not_called()

    def test_factory_access_error_reports_numeric_cause_and_no_private_text(self):
        cause = RuntimeError('private-device-information')
        cause.backend_error_code = -12
        error = app.usb.UsbFactoryError('could not claim factory USB interface: private-device-information')
        error.__cause__ = cause
        with patch.object(app.os, 'name', 'nt'):
            message = app.user_error(error)
            self.assertIn('错误码 -12', message)
            self.assertIn('驱动不支持', message)
            self.assertNotIn('private-device-information', message)

if __name__ == '__main__': unittest.main()
