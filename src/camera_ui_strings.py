"""Quote-exact camera menu labels. Desktop localization stays separate."""
from localization import TRADITIONAL

# Visible menu labels only. Status sentences that contain the same words are left alone
# because replacement matches the full quoted string, including the closing quote.
LABELS = (
    ('耍起功能', 'Tweaks'),
    ('开启 AF-C', 'Enable AF-C'),
    ('对焦加速', 'Focus Speed Boost'),
    ('对焦加速通过将镜头转速提高三倍实现，不建议老镜头用户开启。',
     'Focus acceleration works by tripling lens motor speed. Not recommended for older lenses.'),
    ('在亮度菜单中加入自动亮度', 'Add Auto Brightness to Menu'),
    ('请前往显示 → 亮度设置自动亮度', 'Configure auto brightness in Display → Brightness'),
    ('自动亮度', 'Auto Brightness'),
    ('黑白拍摄', 'Monochrome Capture'),
    ('显示屏最高亮度', 'Maximum Screen Brightness'),
    ('连续自动对焦', 'AF-C'),
    ('对焦模式', 'Focus Mode'),
    ('单次自动对焦', 'Single Autofocus'),
    ('手动对焦', 'Manual Focus'),
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
                        '手动对焦': '手動對焦'})
    for chinese, traditional in translations.items():
        if chinese != traditional:
            result = result.replace(f'"{chinese}"', f'"{traditional}"')
    return result
