# Validation boundaries — 0.4.1

| Evidence | Result | Limits |
| --- | --- | --- |
| Full offline Python suite with locally generated camera inputs | 122 tests passed with local inputs; clean source checkout: 97 passed, 25 explicitly skipped | USB / Windows APIs and device shell are substituted; no camera is accessed |
| Qt 6.4.1 desktop menu model | 907 optional row at 11, Shuaqi at 12; removal, stock routes and repeated returns passed | Source model and graphics are substitutes |
| Stock four-column grid + packaged Bootstrap QML | Actual mouse clicks, highlight, Easter egg page, return, status-driven insertion/removal and menu acknowledgements passed | Outer camera services are substituted; no 907 device validation |
| Native Mac 0.4.0 / 0.4.1 windows | Chinese / English switch, translated checkbox, disabled writes when disconnected and layout checked | Host macOS 27; this does not verify all supported macOS versions |
| Desktop archives | Universal Mach-O dependencies and 38 Windows PE files audited | Windows cross-build; no native 0.4.1 Windows GUI/device run |
| Earlier X2D releases | Camera menu and restoration device evidence; Windows installation + reboot user feedback | Does not validate every change in 0.4.1 |
| AF-S selected while AF-C remains available | Startup forcing removed in source | Power-cycle device confirmation pending |
| 907X & CFV 100C | Prior connection / service installation user feedback | Original missing menu entry led to layout fix; corrected menu + optional Easter egg still need device confirmation |
| Windows automatic factory driver preparation | Fixed supported hardware IDs, rejection cases, helper integrity and cross-build checked | Real driver installation still needs Windows testing; ADB interface is independent |


Screenshots in this repository show the actual Mac application, not a Windows mockup or camera validation result. No camera was accessed while preparing this source push.

# 验证边界

0.4.1 已通过 122 项完整离线 Python 用例、Qt 桌面菜单与原厂网格路由测试，并实际检查 Mac 中英文窗口。桌面替身成功不等于实机成功。907 彩蛋与菜单、AF-S 关机后保持、Windows 自动驱动安装仍待用户实机确认；本次未连接或修改相机。

## App updates (0.4.1)

GitHub version/asset selection, checksum and archive path checks, app identity/version gates, replacement and rollback are exercised with offline fixtures. No camera operations are performed by the updater. Windows self-replacement and relaunch require testing on Windows; cross-compilation is not a Windows execution test. The native Mac update-check button and packaged HTTPS connection to GitHub have passed on macOS 27. The detached installer is tested separately; this does not validate every supported OS.

On macOS 27, a real packaged ZIP was extracted and signature-checked, then a detached copied runtime replaced a disposable app copy, retained the previous signed app, and successfully issued the relaunch. The sandboxed relaunch initially failed and the old app was restored; the normal host launch passed. No camera was accessed.

## Menu receipt recovery (0.4.1)

A service restart deletes the volatile menu receipt, while the original UI reported only when its menu changed. Bootstrap now refreshes a verified receipt every five seconds and still revokes it when the button disappears. The actual JavaScript function passed in Qt 6.4.1 with a simulated receipt loss/service restart. Connection checking now distinguishes installed files from an acknowledged menu and keeps recovery available. The affected X2D user reported that the menu existed and restoration succeeded on 0.3.3; the new behavior awaits that user’s device confirmation. Known 0.3.3 manifests and exact interrupted-write recovery bytes are retained. GitHub archive names use ASCII to avoid upload-time renaming.
