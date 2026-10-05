"""No camera I/O: confirmation must precede any restore/upload/reboot."""
import io
import json
import re
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import x2d_play_software as app
from reinstall_confirmation import CONTINUE, CANCEL, prompt


class ReinstallConfirmationTests(unittest.TestCase):
    def package(self):
        zh = dict(source='page.qml', target='/system/etc/page.qml', sha256='zh', bytes=1)
        en = dict(source='page.en.qml', target=zh['target'], sha256='en', bytes=2)
        hant = dict(source='page.zh-Hant.qml', target=zh['target'], sha256='hant', bytes=3)
        return dict(format=3, guiSha256=app.STOCK_GUI, files=[zh], uiLanguages={'en':[en],'zh-Hant':[hant]})

    def install_case(self, response, language='en', known=True, initial=False, same=False):
        package = self.package()
        installed = app.apply_ui_language(package, language if same else ('zh' if language == 'en' else 'en'))
        with ExitStack() as stack:
            stack.enter_context(patch.object(app, 'prepare', return_value=package))
            stack.enter_context(patch.object(app, 'verify_target'))
            stack.enter_context(patch.object(app, 'INTERACTIVE_CONFIRMATION', True))
            stack.enter_context(patch.object(app, 'REINSTALL_CONFIRMED', False))
            stack.enter_context(patch.object(app.sys, 'stdin', io.StringIO(response)))
            stack.enter_context(patch.object(app, 'shell', side_effect=['NO'] if initial else ['YES','MENU_ENTRY_READY_12']))
            stack.enter_context(patch.object(app, 'read_bytes', side_effect=[b'INSTALLED', json.dumps(installed).encode()]))
            stack.enter_context(patch.object(app, 'recognized_bundle', return_value=known))
            stack.enter_context(patch.object(app, 'backend', return_value=dict(ready=True, prankIbis=False)))
            event = stack.enter_context(patch.object(app, 'event'))
            restore = stack.enter_context(patch.object(app, 'restore'))
            upload = stack.enter_context(patch.object(app, 'upload'))
            adb = stack.enter_context(patch.object(app, 'ensure_adb'))
            reboot = stack.enter_context(patch.object(app, 'reboot_and_verify'))
            entry = app.install
            recursive = stack.enter_context(patch.object(app, 'install'))
            sequence = Mock()
            sequence.attach_mock(event, 'event')
            sequence.attach_mock(restore, 'restore')
            sequence.attach_mock(recursive, 'install')
            if not known:
                with self.assertRaisesRegex(RuntimeError, '其他版本'): entry(language=language)
            elif initial:
                # Reaching the stock-config read proves the confirmation branch was bypassed.
                stack.enter_context(patch.object(app, 'init_config', side_effect=RuntimeError('FIRST_INSTALL_PATH')))
                with self.assertRaisesRegex(RuntimeError, 'FIRST_INSTALL_PATH'): entry(language=language)
            else:
                entry(language=language)
            upload.assert_not_called(); adb.assert_not_called(); reboot.assert_not_called()
            event.sequence = sequence.mock_calls
            return event, restore, recursive

    def test_cancel_eof_and_malformed_response_never_restore(self):
        for response in (CANCEL, '', 'yes\n', 'CONFIRM_REINSTALL'):
            with self.subTest(response=response):
                event, restore, install = self.install_case(response)
                restore.assert_not_called(); install.assert_not_called()
                self.assertEqual(event.call_args.args[0], 'cancelled')

    def test_confirmed_restore_precedes_reinstall_and_keeps_target_language(self):
        for language in ('en','zh','zh-Hant'):
            event, restore, install = self.install_case(CONTINUE, language)
            restore.assert_called_once_with(True, report_result=False)
            install.assert_called_once_with(True, False, language)
            confirmation = next(c for c in event.call_args_list if c.args[0] == 'confirmation')
            self.assertEqual(confirmation.kwargs, prompt(language))
            actions = [c.args[0] if c[0] == 'event' else c[0] for c in event.sequence]
            self.assertLess(actions.index('confirmation'),actions.index('restore'))
            self.assertLess(actions.index('restore'),actions.index('install'))

    def test_first_install_same_configuration_and_unknown_files_never_prompt(self):
        for kwargs in (dict(initial=True),dict(same=True),dict(known=False)):
            event, restore, _ = self.install_case(CONTINUE, **kwargs)
            self.assertFalse(any(c.args[0] == 'confirmation' for c in event.call_args_list))
            restore.assert_not_called()

    def test_no_interactive_mode_requires_explicit_cli_confirmation(self):
        with patch.object(app,'INTERACTIVE_CONFIRMATION',False), patch.object(app,'REINSTALL_CONFIRMED',False):
            with self.assertRaisesRegex(RuntimeError, '--confirm-reinstall'): app.confirm_reinstall('en')
        with patch.object(app,'REINSTALL_CONFIRMED',True), patch.object(app,'event') as event:
            self.assertTrue(app.confirm_reinstall('en')); event.assert_not_called()

    def test_popup_copy_and_buttons_follow_target_language(self):
        en, zh, hant = prompt('en'), prompt('zh'), prompt('zh-Hant')
        self.assertIsNone(re.search('[\u3400-\u9fff]', ''.join(en.values())))
        self.assertIn('English camera menu',en['body']); self.assertIn('中文相机菜单',zh['body'])
        self.assertEqual(en['cancel'],'Cancel'); self.assertEqual(zh['cancel'],'取消')
        self.assertIn('繁體中文相機選單',hant['body'])
        self.assertEqual(hant['proceed'],'繼續安裝')
        with self.assertRaises(ValueError): prompt('fr')


if __name__ == '__main__': unittest.main()
