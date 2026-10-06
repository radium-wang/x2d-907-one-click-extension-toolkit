"""Known 0.4.8 language variants remain restorable after the focus UI update."""
import json
import unittest
from unittest.mock import patch
import x2d_play_software as app
from payload_support import requires_payloads


@requires_payloads
class FocusUIUpgradeTests(unittest.TestCase):
    def test_previous_release_all_languages_recognized_and_full_bytes_retained(self):
        raw=(app.O/'previous-bundle-0.4.8.json').read_bytes()
        self.assertEqual(app.sha(raw),app.PREVIOUS_048_SHA)
        previous=json.loads(raw)
        for language in ('zh','en','zh-Hant'):
            with self.subTest(language=language):
                selected=app.apply_ui_language(previous,language)
                self.assertTrue(app.recognized_bundle(selected))
                for entry in selected['files']:
                    self.assertEqual(app.sha((app.O/'previous-payloads'/entry['sha256']).read_bytes()),entry['sha256'])
        self.assertNotEqual(previous['files'],app.prepare()['files'])

    def test_tampered_preceding_release_manifest_is_rejected(self):
        previous=json.loads((app.O/'previous-bundle-0.4.8.json').read_bytes())
        with patch.object(app,'PREVIOUS_048_SHA','0'*64):
            with self.assertRaisesRegex(RuntimeError,'安装包校验失败'):
                app.recognized_bundle(previous)
