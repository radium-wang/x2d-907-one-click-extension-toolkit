# Validation boundaries — 0.4.2

| Evidence | Result | Limits |
| --- | --- | --- |
| Full offline Python suite with locally generated camera inputs | 134 tests passed with local inputs; clean source checkout: 109 passed, 25 explicitly skipped | USB / Windows APIs and device shell are substituted; no camera is accessed |
| Qt 6.4.1 desktop menu model | 907 optional row at 11, Shuaqi at 12; removal, stock routes and repeated returns passed | Source model and graphics are substitutes |
| Stock four-column grid + packaged Bootstrap QML | Actual mouse clicks, highlight, Easter egg page, return, status-driven insertion/removal and menu acknowledgements passed | Outer camera services are substituted; no 907 device validation |
| Native Mac 0.4.2 windows | Settings, Chinese / English switch, saved startup update-check switch, manual checking with automatic checks off, and disabled writes when disconnected checked | Host macOS 27; this does not verify all supported macOS versions |
| Desktop archives | Universal Mach-O dependencies and 38 Windows PE files audited | Windows cross-build; no native 0.4.2 Windows GUI/device run |
| Earlier X2D releases | Camera menu and restoration device evidence; Windows installation + reboot user feedback | Does not validate every change in 0.4.2 |
| AF-S selected while AF-C remains available | Startup forcing removed in source | Power-cycle device confirmation pending |
| 907X & CFV 100C | Prior connection / service installation user feedback | Original missing menu entry led to layout fix; corrected menu + optional Easter egg still need device confirmation |
| Windows automatic factory driver preparation | Fixed supported hardware IDs, rejection cases, helper integrity and cross-build checked | Real driver installation still needs Windows testing; ADB interface is independent |


Screenshots in this repository show the actual Mac application, not a Windows mockup or camera validation result. No camera was accessed while preparing this source push.

# 验证边界

0.4.2 已通过 134 项完整离线 Python 用例、Qt 桌面菜单与原厂网格路由测试，并实际检查 Mac 中英文窗口。桌面替身成功不等于实机成功。907 彩蛋与菜单、AF-S 关机后保持、Windows 自动驱动安装仍待用户实机确认；本次未连接或修改相机。

## App updates (0.4.1)

GitHub version/asset selection, checksum and archive path checks, app identity/version gates, replacement and rollback are exercised with offline fixtures. No camera operations are performed by the updater. Windows self-replacement and relaunch require testing on Windows; cross-compilation is not a Windows execution test. The native Mac update-check button and packaged HTTPS connection to GitHub have passed on macOS 27. The detached installer is tested separately; this does not validate every supported OS.

On macOS 27, a real packaged ZIP was extracted and signature-checked, then a detached copied runtime replaced a disposable app copy, retained the previous signed app, and successfully issued the relaunch. The sandboxed relaunch initially failed and the old app was restored; the normal host launch passed. No camera was accessed.

## English camera menus and target-language reinstall confirmation (0.4.2)

The English camera menu PR plus the confirmation changes pass 134 offline Python tests with local payload inputs (clean source: 109 passed, 25 skipped). The five generated English QML files match the PR's recorded hashes. Apple silicon and Intel Swift checks passed. The actual Mac window displayed Chinese and English confirmation sheets using a backend fixture with no USB imports; the Continue button returned the explicit approval token. Windows callback tests exercise target-language selection frozen before a desktop language change, Cancel as the default, confirmation/cancellation responses, and closing the dialog without quitting the app. These Win32 APIs are substitutes; the Windows dialog and camera restoration/reinstallation still need native/device checks. No camera was accessed. These changes are included in 0.4.2; the published 0.4.1 packages remain unchanged.

英文相机菜单 PR 与确认弹窗改动通过 134 项完整离线测试；纯源码环境为 109 项通过、25 项跳过。五份英文 QML 与 PR 哈希一致，Mac 双架构 Swift 检查通过。使用不含 USB 操作的模拟后端检查了 Mac 原生中英文弹窗和继续按钮的确认回复。Windows 窗口回调测试覆盖目标语言固定、默认取消、按钮回复及关闭弹窗；仍需 Windows 原生窗口和相机实机验证。本次未操作相机，改动包含在 0.4.2 中，已发布的 0.4.1 安装包不变。

## Menu receipt recovery (0.4.1)

A service restart deletes the volatile menu receipt, while the original UI reported only when its menu changed. Bootstrap now refreshes a verified receipt every five seconds and still revokes it when the button disappears. The actual JavaScript function passed in Qt 6.4.1 with a simulated receipt loss/service restart. Connection checking now distinguishes installed files from an acknowledged menu and keeps recovery available. The affected X2D user reported that the menu existed and restoration succeeded on 0.3.3; the new behavior awaits that user’s device confirmation. Known 0.3.3 manifests and exact interrupted-write recovery bytes are retained. GitHub archive names use ASCII to avoid upload-time renaming.

## Settings (0.4.2)

On macOS 27, the packaged app showed the English and Chinese Settings windows. Disabling startup checks survived an app restart and prevented the startup update query; manual checking still connected to GitHub and returned normally. The original language and automatic-check preference were restored after testing. Windows callback tests cover startup on/off, persisted preferences, manual checks and the separate download action; native Windows execution remains pending. No camera operation was started.

在 macOS 27 中检查了打包 App 的中英文设置页。关闭自动检查后重开 App，选择保留且不再启动查询；手动检查仍正常连接 GitHub。测试结束恢复原语言和自动检查偏好。Windows 使用替代 API 测试启动开关、持久化、手动检查及独立下载按钮，原生 Windows 验证仍待完成。本次未操作相机。

## Published update packages (0.4.2)

After publishing 0.4.2 as the latest stable release, the Mac and Windows updater code from the packaged 0.4.1 distributions both detected 0.4.2, downloaded their corresponding GitHub ZIP, verified SHA-256, safely extracted it, and validated the new application identity/version. Both checks ran on Mac with the packaged runtime; this does not verify Windows replacement/relaunch. No installed application or camera was modified by these download checks.

0.4.2 发布为最新稳定版后，使用 0.4.1 安装包内的 Mac / Windows 更新器代码，分别完成新版识别、GitHub 实际下载、SHA-256 校验、安全解压及应用身份与版本检查。两组检查都在 Mac 的内置运行库中执行，不代表 Windows 替换及重开已验证；下载检查未修改已安装应用或相机。
