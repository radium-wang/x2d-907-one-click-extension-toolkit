"""Target-language copy and a fail-closed desktop/backend confirmation protocol."""

CONTINUE = 'CONFIRM_REINSTALL\n'
CANCEL = 'CANCEL_REINSTALL\n'


def prompt(language):
    if language == 'en':
        return dict(language='en', title='Restore and reinstall the extension?',
                    body='The current extension will be removed and this toolkit\'s changes restored, '
                         'then the English camera menu will be installed. Feature switches will be '
                         'turned off and the camera will restart during restoration and installation. '
                         'Keep the camera powered and USB connected until completion, then re-enable '
                         'the features you need.',
                    cancel='Cancel', proceed='Continue Installation')
    if language == 'zh':
        return dict(language='zh', title='恢复并重新安装扩展？',
                    body='将先撤回当前扩展并恢复本工具的修改，再安装中文相机菜单。'
                         '功能开关将关闭，相机会在恢复和安装过程中重启。'
                         '请保持相机供电和 USB 连接，完成后重新开启所需功能。',
                    cancel='取消', proceed='继续安装')
    if language == 'zh-Hant':
        return dict(language='zh-Hant', title='還原並重新安裝擴充功能？',
                    body='將先移除目前的擴充功能並還原本工具的修改，再安裝繁體中文相機選單。'
                         '功能開關將關閉，相機會在還原和安裝過程中重新啟動。'
                         '請保持相機供電和 USB 連線，完成後重新開啟所需功能。',
                    cancel='取消', proceed='繼續安裝')
    raise ValueError('Unsupported target language')
