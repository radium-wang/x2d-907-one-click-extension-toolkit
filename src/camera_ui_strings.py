"""Quote-exact camera menu labels. Desktop localization stays separate."""

# Visible menu labels only. Status sentences that contain the same words are left alone
# because replacement matches the full quoted string, including the closing quote.
LABELS = (
    ('耍起功能', 'Tweaks'),
    ('开启 AF-C', 'Enable AF-C'),
    ('对焦加速 buff', 'Focus Speed Boost'),
    ('连续自动对焦', 'AF-C'),
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
