import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app_settings import UpdatePreferences
from localization import Localizer


class SettingsTests(unittest.TestCase):
    def test_default_on_disable_restart_enable_and_language_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            language=Localizer(root/'language.json');language.select('en')
            settings=UpdatePreferences(root/'settings.json')
            self.assertTrue(settings.auto_check)
            self.assertTrue(settings.set_auto_check(False))
            self.assertFalse(UpdatePreferences(root/'settings.json').auto_check)
            self.assertEqual(Localizer(root/'language.json').language,'en')
            self.assertTrue(settings.set_auto_check(True))
            self.assertTrue(UpdatePreferences(root/'settings.json').auto_check)
            self.assertFalse((root/'settings.tmp').exists())

    def test_invalid_preferences_do_not_treat_string_false_as_a_boolean(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for content in ('not json','null','[]',json.dumps({'autoCheckUpdates':'false'})):
                path.write_text(content)
                self.assertTrue(UpdatePreferences(path).auto_check)

    def test_save_failure_keeps_session_choice_and_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            settings=UpdatePreferences(path);settings.set_auto_check(True)
            with patch('app_settings.os.replace',side_effect=OSError):
                self.assertFalse(settings.set_auto_check(False))
            self.assertFalse(settings.auto_check)
            self.assertTrue(UpdatePreferences(path).auto_check)


if __name__=='__main__':unittest.main()
