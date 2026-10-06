"""Read-only stock debug flag diagnostics; unknown replies never mean disabled."""
import unittest
from unittest.mock import MagicMock, patch
import x2d_play_software as app
from localization import translate


class EyeDebugTests(unittest.TestCase):
    def reply(self, raw):
        connection = MagicMock()
        connection.__enter__.return_value.factory_shell.return_value = raw
        with patch.object(app, 'reader', return_value=connection) as reader:
            result = app.eye_debug_status()
        reader.assert_called_once_with(timeout=5000)
        connection.__enter__.return_value.factory_shell.assert_called_once_with(app.EYE_DEBUG_READ, capture_ms=5000)
        return result

    def test_current_eye_bit_and_master_are_both_required(self):
        for enabled in ('true', 'false', '0', '1'):
            for mask in (0, 1, 2, 3, 127):
                raw = 'DEBUG_MODE\nsystem.debug_mode = ' + enabled + '\nDEBUG_OPTIONS\nsystem.debug_options = E_DebugOption_Multiple(' + str(mask) + ')\n'
                state = self.reply(raw)
                self.assertTrue(state['ready'])
                self.assertEqual(state['debugOptions'], mask)
                self.assertEqual(state['eyeDebug'], enabled in ('true', '1') and bool(mask & 1))

    def test_numeric_mask_formats_are_supported(self):
        for token in ('3', '0x3', 'E_DebugOption_EyeDetection | E_DebugOption_FaceDetection(3)'):
            state = self.reply('DEBUG_MODE\nsystem.debug_mode = true\nDEBUG_OPTIONS\nsystem.debug_options = ' + token + '\n')
            self.assertEqual(state, dict(ready=True, debugMode=True, debugOptions=3, eyeDebug=True))

    def test_missing_invalid_duplicate_and_transport_failures_remain_unknown(self):
        replies = ('', 'DEBUG_MODE\nfalse\nDEBUG_OPTIONS\n0',
                   'DEBUG_MODE\nsystem.debug_mode = true\nDEBUG_OPTIONS\nerror',
                   'DEBUG_MODE\nsystem.debug_mode = true\nDEBUG_OPTIONS\nsystem.debug_options = 128',
                   'DEBUG_MODE\nsystem.debug_mode = true\nsystem.debug_mode = false\nDEBUG_OPTIONS\nsystem.debug_options = 0')
        for raw in replies:
            self.assertEqual(self.reply(raw), dict(ready=False))
        with patch.object(app, 'reader', side_effect=RuntimeError('unavailable')):
            self.assertEqual(app.eye_debug_status(), dict(ready=False))

    def test_diagnostic_is_fixed_read_only_and_translated_without_claiming_origin(self):
        self.assertLessEqual(len(app.EYE_DEBUG_READ.encode('ascii')), 231)
        self.assertNotIn(' -- ', app.EYE_DEBUG_READ)
        self.assertNotIn('setprop', app.EYE_DEBUG_READ)
        with patch.object(app, 'verify_target', side_effect=RuntimeError('unknown firmware')), patch.object(app, 'report_eye_debug') as report:
            with self.assertRaises(RuntimeError): app.status(eye_debug=True)
            report.assert_not_called()
        for state in (dict(ready=False), dict(ready=True, eyeDebug=True), dict(ready=True, eyeDebug=False)):
            with patch.object(app, 'eye_debug_status', return_value=state), patch.object(app, 'event') as event:
                app.report_eye_debug()
            message = event.call_args.kwargs['message']
            self.assertEqual(event.call_args.kwargs['eyeDebugStatus'], state)
            self.assertNotIn('残留', message)
            self.assertNotEqual(translate(message, 'en'), message)
            self.assertNotEqual(translate(message, 'zh-Hant'), message)


if __name__ == '__main__':
    unittest.main()
