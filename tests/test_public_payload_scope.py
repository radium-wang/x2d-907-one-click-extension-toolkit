"""Public installation must reject policy, raw partition and GUI disk writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import x2d_play_software as app


class PublicPayloadScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='public-payload-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        data = b'public QML fixture'
        for name in ('ui.qml', 'ui.en.qml', 'ui.zh-Hant.qml'):
            (self.root / name).write_bytes(data)
        entry = dict(source='ui.qml', target='/system/etc/X2dNativeMenuBootstrap.qml',
                     sha256=app.sha(data))
        self.manifest = dict(format=3, guiSha256=app.STOCK_GUI, files=[entry],
                             uiLanguages={language: [dict(entry, source=source)]
                                          for language, source in
                                          (('en', 'ui.en.qml'), ('zh-Hant', 'ui.zh-Hant.qml'))},
                             focusUi=dict(diskGuiChanged=False))

    def prepare(self, manifest):
        (self.root / 'speed-bundle.json').write_text(json.dumps(manifest))
        with patch.object(app, 'O', self.root), patch.object(app, 'reader') as reader:
            try:
                return app.prepare()
            finally:
                reader.assert_not_called()

    def test_stock_policy_preload_package_is_accepted(self):
        self.assertEqual(self.prepare(self.manifest), self.manifest)

    def test_forbidden_targets_rejected_in_every_language_before_file_access(self):
        for target in ('/vendor/etc/selinux/precompiled_sepolicy', '/system/etc/sepolicy.dbg',
                       '/system/bin/camera-gui', '/system/etc/x2d-camera-gui',
                       '/dev/block/mmcblk0p18'):
            for language in ('zh', 'en', 'zh-Hant'):
                with self.subTest(target=target, language=language):
                    manifest = copy.deepcopy(self.manifest)
                    entries = manifest['files'] if language == 'zh' else manifest['uiLanguages'][language]
                    entries[0].update(target=target, source='missing.qml')
                    with self.assertRaisesRegex(RuntimeError, '不允许的写入路径'):
                        self.prepare(manifest)

    def test_gui_replacement_declaration_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['focusUi']['diskGuiChanged'] = True
        with self.assertRaisesRegex(RuntimeError, '包含不允许的修改'):
            self.prepare(manifest)

    def test_overlay_cannot_add_an_uninstalled_target(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['uiLanguages']['en'][0]['target'] = '/system/etc/X2dPlayPage.qml'
        with self.assertRaisesRegex(RuntimeError, '不允许的写入路径'):
            self.prepare(manifest)

    def test_unsafe_source_path_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['files'][0]['source'] = '../ui.qml'
        with self.assertRaisesRegex(RuntimeError, '文件清单不匹配'):
            self.prepare(manifest)


if __name__ == '__main__':
    unittest.main()
