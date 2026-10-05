from payload_support import requires_payloads
"""Offline: language persistence, complete diagnostics, and unchanged operation gates."""
import ast,json,re,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from localization import CATALOG, TRADITIONAL, Localizer, translate
from camera_ui_strings import LABELS, PRANK_BODY_EN, PRANK_BODY_ZH, english_qml, traditional_qml
import windows_app
import x2d_play_software as backend
import windows_factory_usb as factory
import windows_connection as driver
D=Path(__file__).resolve().parents[1]/'src'
CHINESE=re.compile('[\u3400-\u9fff]')
CAMERA_SOURCES=('Bootstrap.qml','PlayMenuModel.qml','PlayPage.qml','AfcMenuController.qml','PrankIbisPage.qml')

class LanguageTests(unittest.TestCase):
    def assert_english(self,text): self.assertFalse(CHINESE.search(text),text)

    def test_all_own_executable_chinese_literals_translate(self):
        for filename in ('windows_app.py','windows_factory_usb.py','windows_connection.py','x2d_play_software.py'):
            tree=ast.parse((D/filename).read_text())
            docs={id(node.body[0].value) for node in ast.walk(tree) if isinstance(node,(ast.Module,ast.FunctionDef,ast.ClassDef)) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str)}
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and id(node) not in docs and CHINESE.search(node.value) and node.value not in ('中文','简体中文','繁體中文','语言 / Language'):
                    with self.subTest(file=filename,text=node.value): self.assert_english(translate(node.value,'en'))
        for match in re.finditer(r'"(?:[^"\\]|\\.)*"',(D/'MacApp.swift').read_text()):
            try: text=json.loads(match.group())
            except ValueError: continue
            if CHINESE.search(text) and text not in ('中文','简体中文','繁體中文','系統','语言 / Language'): self.assert_english(translate(text,'en'))

    def test_chinese_messages_unchanged_and_english_no_mixed_language(self):
        for text in CATALOG:
            self.assertEqual(translate(text,'zh'),text)
            if text not in ('中文','语言 / Language'): self.assert_english(translate(text,'en'))

    def test_traditional_catalog_covers_desktop_and_diagnostic_copy(self):
        self.assertEqual(set(CATALOG)-set(TRADITIONAL),set())
        for source,expected in [('一键安装','一鍵安裝'),('连续自动对焦','連續自動對焦'),
                                ('后屏自动亮度','後屏自動亮度')]:
            self.assertEqual(translate(source,'zh-Hant'),expected)
        self.assertIn('USB 錯誤碼 -3',translate('工厂接口访问被拒绝（USB 错误码 -3）','zh-Hant'))

    def test_diagnostic_codes_paths_and_markers_preserved(self):
        for step in ('信息读取','打开','描述符读取','端点读取','发送','接收'):
            for code in (5,32,121,1167,87):
                text=str(factory.WinUsbError(step,code));english=translate(text,'en')
                self.assert_english(english);self.assertIn(str(code),english)
        messages=[
            'ADB 已识别，但工厂接口校验未完成：工厂接口访问被拒绝（USB 错误码 -3）；请反馈这条完整提示。传输尚未开始',
            '重启后未能完成校验：菜单扩展未通过启动校验：MENU_PENDING。请保持连接并使用恢复原状。',
            'ADB 已连接，正在等待工厂接口完成校验；请保持数据线连接',
            '已开始安装。请保持相机供电和数据线连接，等待 App 提示完成后再拔线。',
            'Windows 工厂接口标识读取被拒绝（系统错误码 5），请反馈此提示',
            'USB 路径 /system/bin/camera-gui']
        for text in messages[:-1]: self.assert_english(translate(text,'en'))
        self.assertIn('MENU_PENDING',translate(messages[1],'en'))
        self.assertIn('-3',translate(messages[0],'en'))
        self.assertEqual(translate('/system/bin/camera-gui SHA256 aabbcc USB 2756:000A MI_03','en'),'/system/bin/camera-gui SHA256 aabbcc USB 2756:000A MI_03')

    def test_driver_errors_translate_for_every_known_and_unknown_code(self):
        for code in (11,12,13,15,16,103,104,106,107,109,114,115,117,118,119,999): self.assert_english(translate(driver.driver_error(code),'en'))

    def test_language_persists_and_invalid_preferences_fall_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'language.json'
            for invalid in (None,'{','[]','{"language":"xx"}'):
                if invalid is not None: path.write_text(invalid)
                self.assertEqual(Localizer(path).language,'zh')
            instance=Localizer(path);instance.select('en')
            self.assertEqual(Localizer(path).text('一键安装'),'Install')
            self.assertEqual(json.loads(path.read_text()),{'language':'en'})
            instance.select('zh');self.assertEqual(Localizer(path).text('一键安装'),'一键安装')
            instance.select('zh-Hant');self.assertEqual(Localizer(path).text('一键安装'),'一鍵安裝')
            self.assertEqual(json.loads(path.read_text()),{'language':'zh-Hant'})
            with self.assertRaises(ValueError): instance.select('other')

    def test_switch_during_operation_never_changes_gates_or_event_data(self):
        with tempfile.TemporaryDirectory() as folder:
            lang=Localizer(Path(folder)/'language.json');session=windows_app.Session()
            self.assertTrue(session.start('status'))
            raw=dict(type='progress',message='正在检查相机与安装包',percent=5)
            original=json.dumps(raw,ensure_ascii=False)
            for language in ('en','zh','en'):
                lang.select(language);lang.text(raw['message'])
                self.assertTrue(session.busy);self.assertFalse(session.verified)
                self.assertFalse(session.start('install'));self.assertFalse(session.start('restore'))
                self.assertEqual(json.dumps(raw,ensure_ascii=False),original)
            session.consume(dict(type='error',message='未检测到相机'));session.finish(1)
            lang.select('zh');self.assertFalse(session.start('install'))

    def test_camera_menu_labels_replace_only_quoted_visible_strings(self):
        sources={name:(D/name).read_text(encoding='utf-8') for name in CAMERA_SOURCES}
        joined=''.join(sources.values())
        expected={chinese:1 for chinese,_ in LABELS if chinese not in ('自动亮度','显示屏最高亮度')}
        expected['耍起功能']=4
        for chinese,count in expected.items():
            self.assertEqual(joined.count(f'"{chinese}"'),count,chinese)
        english={name:english_qml(text) for name,text in sources.items()}
        for name,text in english.items():
            with self.subTest(file=name):
                for chinese,label in LABELS:
                    self.assertNotIn(f'"{chinese}"',text)
                    if f'"{chinese}"' in sources[name]:
                        self.assertIn(f'"{label}"',text)
                for sentence in ('耍起功能已关闭','对焦加速 buff 控制器尚未就绪','对焦加速 buff 条件未满足，暂不可用',
                                 '请先切换到 AF-S 或 MF，再关闭耍起功能'):
                    if f'"{sentence}"' in sources[name]:
                        self.assertIn(f'"{sentence}"',text)
        self.assertEqual(english['AfcMenuController.qml'].count('"AF-C"'),1)
        self.assertIn('"IBIS"',english['PlayMenuModel.qml'])
        self.assertIn(f'"{PRANK_BODY_EN}"',english['PrankIbisPage.qml'])
        self.assertNotIn('你被骗了',english['PrankIbisPage.qml'])
        self.assertIn(f'"{PRANK_BODY_ZH}"',sources['PrankIbisPage.qml'])
        self.assertIn('"耍起功能"',sources['PlayPage.qml'])

    def test_traditional_camera_copy_preserves_qml_logic(self):
        for path in D.glob('*.qml'):
            source=path.read_text(encoding='utf-8')
            translated=traditional_qml(source)
            if source == translated: continue
            with self.subTest(file=path.name):
                self.assertEqual(source.count('"'),translated.count('"'))
                self.assertNotIn('"连续自动对焦"',translated)
        self.assertIn('"耍起功能"', (D/'PlayPage.qml').read_text())
        self.assertEqual(english_qml('"耍起功能已关闭"'),'"耍起功能已关闭"')
        self.assertIn('"耍起功能已關閉"',traditional_qml('"耍起功能已关闭"'))

    def test_camera_ui_language_overlay_keeps_targets_and_rejects_mixed_hashes(self):
        chinese=[dict(source='X2dPlayPage.qml',target='/system/etc/X2dPlayPage.qml',sha256='aa',bytes=1),
                 dict(source='libx2d_native_menu.so',target='/system/lib64/libx2d_native_menu.so',sha256='bb',bytes=2)]
        english=[dict(source='X2dPlayPage.en.qml',target='/system/etc/X2dPlayPage.qml',sha256='cc',bytes=3)]
        traditional=[dict(source='X2dPlayPage.zh-Hant.qml',target='/system/etc/X2dPlayPage.qml',sha256='dd',bytes=4)]
        package=dict(format=3,guiSha256=backend.STOCK_GUI,files=chinese,uiLanguages={'en':english,'zh-Hant':traditional})
        self.assertIs(backend.apply_ui_language(package,'zh'),package)
        selected=backend.apply_ui_language(package,'en')
        self.assertEqual(selected['files'][0],english[0])
        self.assertEqual(selected['files'][1],chinese[1])
        self.assertEqual([entry['target'] for entry in selected['files']],[entry['target'] for entry in chinese])
        self.assertTrue(backend.same_release_files(chinese,package))
        self.assertTrue(backend.same_release_files(selected['files'],package))
        self.assertTrue(backend.same_release_files(backend.apply_ui_language(package,'zh-Hant')['files'],package))
        mixed=[dict(english[0],sha256='dead'),chinese[1]]
        self.assertFalse(backend.same_release_files(mixed,package))
        with self.assertRaises(RuntimeError): backend.apply_ui_language(package,'fr')

    @requires_payloads
    def test_translation_never_changes_camera_payload_hashes(self):
        before=backend.prepare()['files']
        for text in ('正在安装菜单和功能服务','正在恢复原厂启动配置'): translate(text,'en')
        self.assertEqual(before,backend.prepare()['files'])
        english=backend.apply_ui_language(backend.prepare(),'en')['files']
        traditional=backend.apply_ui_language(backend.prepare(),'zh-Hant')['files']
        self.assertNotEqual(before,english)
        self.assertNotEqual(before,traditional)
        self.assertEqual([entry['target'] for entry in before],[entry['target'] for entry in english])
        self.assertEqual([entry['target'] for entry in before],[entry['target'] for entry in traditional])

if __name__=='__main__':unittest.main()
