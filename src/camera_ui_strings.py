"""Quote-exact camera menu labels. Desktop localization stays separate."""
from localization import TRADITIONAL

# Visible menu labels only. Status sentences that contain the same words are left alone
# because replacement matches the full quoted string, including the closing quote.
LABELS = (
    ('耍起功能', 'Tweaks'),
    ('开启 AF-C', 'Enable AF-C'),
    ('人眼识别', 'Eye Recognition'),
    ('需在原厂菜单开启人脸检测；眼部框不代表跟随对焦。',
     'Enable face detection in the stock menu. Eye boxes do not establish tracking autofocus.'),
    ('调试选项另有改动，请先将其他调试选项恢复到开启人眼识别时的状态，再关闭或恢复。',
     'Other debug options have changed. Restore them to their state when Eye Recognition was enabled before turning it off or restoring the camera.'),
    ('人眼识别状态无法确认，请检查原厂调试设置。',
     'Eye Recognition state could not be confirmed. Check the stock debug settings.'),
    ('人眼识别操作未完成，请关闭总开关或恢复软件。',
     'The Eye Recognition operation is incomplete. Turn off Tweaks or restore the software.'),
    ('对焦加速', 'Focus Speed Boost'),
    ('对焦加速通过将镜头转速提高三倍实现，可安装，但不建议老镜头用户在相机内开启该功能。',
     'Focus acceleration triples lens motor speed. It can be installed, but users of older lenses are advised not to enable this feature in the camera.'),
    ('在亮度菜单中加入自动亮度', 'Add Auto Brightness to Menu'),
    ('请前往显示 → 亮度设置自动亮度', 'Configure auto brightness in Display → Brightness'),
    ('自动亮度', 'Auto Brightness'),
    ('显示屏最高亮度', 'Maximum Screen Brightness'),
    ('连续自动对焦', 'AF-C'),
    ('对焦模式', 'Focus Mode'),
    ('单次自动对焦', 'Single Autofocus'),
    ('手动对焦', 'Manual Focus'),
    ('本项目完全免费，如果有人收你钱了，那你纯是被骗了',
     'This project is completely free. If someone charged you for it, you were scammed.'),
    ('好的，我没被骗', "Okay, I wasn't scammed"),
    ('防抖', 'IBIS'),
)

# QML source keeps a literal backslash-n escape inside the quoted string.
PRANK_BODY_ZH = '你被骗了，这里啥也没有\\nYou\u2019ve been fooled. There\u2019s nothing here.'
PRANK_BODY_EN = 'You\u2019ve been fooled. There\u2019s nothing here.'


def english_qml(text):
    result = text
    for chinese, english in LABELS:
        result = result.replace(f'"{chinese}"', f'"{english}"')
    return result.replace(f'"{PRANK_BODY_ZH}"', f'"{PRANK_BODY_EN}"')


def traditional_qml(text):
    # Only source-language, quoted camera copy is replaced. QML identifiers and
    # non-Chinese protocol strings remain byte-for-byte identical.
    result = text
    translations = dict(TRADITIONAL, **{'对焦模式': '對焦模式',
                        '单次自动对焦': '單次自動對焦', '连续自动对焦': '連續自動對焦',
                        '手动对焦': '手動對焦',
                        '人眼识别': '人眼識別',
                        '需在原厂菜单开启人脸检测；眼部框不代表跟随对焦。':
                            '需在原廠菜單開啟人臉檢測；眼部框不代表跟隨對焦。',
                        '调试选项另有改动，请先将其他调试选项恢复到开启人眼识别时的状态，再关闭或恢复。':
                            '調試選項另有改動，請先將其他調試選項恢復到開啟人眼識別時的狀態，再關閉或恢復。',
                        '人眼识别状态无法确认，请检查原厂调试设置。':
                            '人眼識別狀態無法確認，請檢查原廠調試設定。',
                        '人眼识别操作未完成，请关闭总开关或恢复软件。':
                            '人眼識別操作未完成，請關閉總開關或恢復軟體。',
                        '本项目完全免费，如果有人收你钱了，那你纯是被骗了':
                            '本項目完全免費，如果有人收你錢了，那你純是被騙了',
                        '好的，我没被骗': '好的，我沒被騙'})
    for chinese, traditional in translations.items():
        if chinese != traditional:
            result = result.replace(f'"{chinese}"', f'"{traditional}"')
    return result
