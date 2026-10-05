"""Three-language guidance and exact old-install restoration; no device access."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from localization import translate
from camera_ui_strings import english_qml,traditional_qml
from payload_support import requires_payloads
import x2d_play_software as app

D=Path(__file__).resolve().parents[1]/'src'
HINT='对焦加速通过将镜头转速提高三倍实现，不建议老镜头用户开启。'


class FocusGuidance(unittest.TestCase):
    def test_three_language_guidance_preserves_english_feature_names(self):
        self.assertEqual(translate('对焦加速','en'),'Focus speed buff')
        self.assertEqual(translate('对焦加速','zh-Hant'),'對焦加速')
        self.assertEqual(english_qml('text: "对焦加速"'),'text: "Focus Speed Boost"')
        self.assertEqual(traditional_qml('text: "对焦加速"'),'text: "對焦加速"')
        self.assertIn('tripling',translate(HINT,'en'))
        self.assertIn('older lenses',translate(HINT,'en'))
        self.assertIn('老鏡頭',translate(HINT,'zh-Hant'))
        self.assertIn(translate(HINT,'en'),english_qml('text: "'+HINT+'"'))
        self.assertIn(translate(HINT,'zh-Hant'),traditional_qml('text: "'+HINT+'"'))

    @requires_payloads
    def test_published_047_all_languages_remain_recognized_and_old_bytes_available(self):
        old=json.loads((app.O/'previous-bundle-0.4.7.json').read_bytes())
        for language in ('zh','zh-Hant','en'):
            selected=app.apply_ui_language(old,language)
            self.assertTrue(app.recognized_bundle(selected),language)
            for entry in selected['files']:
                saved=(app.O/'previous-payloads'/entry['sha256']).read_bytes()
                self.assertEqual(app.sha(saved),entry['sha256'])
            mixed=copy.deepcopy(selected)
            page=next(f for f in mixed['files'] if f['target']=='/system/etc/X2dPlayPage.qml')
            page['sha256']='0'*64
            self.assertFalse(app.recognized_bundle(mixed),language)
        with patch.object(app,'PREVIOUS_047_SHA','0'*64):
            with self.assertRaisesRegex(RuntimeError,'安装包校验失败'): app.recognized_bundle(old)


if __name__=='__main__':unittest.main()
