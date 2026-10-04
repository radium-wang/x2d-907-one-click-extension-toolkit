# Validation boundaries — 0.4.5

## Windows exit fix (0.4.5)

The window can cancel a read-only update check without waiting for a network timeout. Camera/driver work and desktop update installation retain exit protection. Regression checks run the actual window callback with Win32 substitutes while a real child process is blocked, close the window, and verify that child exits. They also cover close-before-launch and close-during-launch races, camera/update-install protection, private ADB endpoint propagation, startup/assignment failure and timeout cleanup, CLI failure cleanup, and the Windows x64 job structure/kill-on-close flags.

The complete offline suite passes 166 tests with locally generated inputs; clean source passes 140 and skips 26 requiring excluded inputs. The Windows 0.4.5 package includes `windows_processes.py` and passes 38 PE and archive checks; the Mac universal package passes its dependency and archive checks. Both retain the exact 0.4.4 camera payload; existing 0.4.3/0.4.4 camera installations do not need reinstallation. Mac behavior is unchanged. The private foreground ADB server and its ownership are tested with ADB/Win32 substitutes; no real ADB server, USB device or Windows driver was used. Folder movement in a portable child-process test is not evidence of Windows directory-handle behavior. Native Windows window closure, post-install/restore cleanup, directory movement and abnormal-owner exit still need Windows validation. Published 0.4.4 archives are unchanged.

## Windows interface (0.4.4)

The Windows UI now shares Mac's visual hierarchy while retaining native BUTTON, EDIT and COMBOBOX controls. The complete offline suite passes 153 tests with generated inputs; clean source passes 127 and explicitly skips 26 requiring excluded inputs. Checks exercise GDI drawing state, pressed/disabled styles, progress and checkbox state, callback/resource lifetime, frozen confirmation language, per-window fonts/DPI, scrolling and focus reveal. Existing connection, camera-write and update gates are exercised with the new skin attached. Six Chinese/English main/short-window/Settings previews use the native skin's layout, palette and icon geometry and pass text-fit checks. The 0.4.4 release packages include the new Windows skin module where applicable, retain the exact 0.4.3 camera payload and pass the universal Mac, 38-file Windows PE and archive audits.

Previews render with desktop Qt and host font fallback; they are not evidence of native Windows rendering or accessibility verification. Native execution still requires confirmation on Windows 10/11, including 100%/125%/150%/200% scaling, keyboard navigation, Settings and reinstall dialogs. The Mac interface is unchanged; only its release version is advanced to 0.4.4. No camera was connected or modified, and the published 0.4.3 assets remain unchanged. Existing 0.4.3 camera extensions do not need reinstallation for this desktop UI update.

| Evidence | Result | Limits |
| --- | --- | --- |
| 0.4.4 offline Python suite | 153 passed with local inputs; clean source: 127 passed, 26 explicitly skipped | Win32 and device APIs are substitutes; native Windows rendering and camera checks remain pending |
| 0.4.3 offline Python suite with locally generated camera inputs | 144 passed; clean source: 118 passed, 26 explicitly skipped | USB / Windows APIs and device shell are substituted; excluded build inputs cause clean-source skips; no camera is accessed |
| 0.4.2 offline Python suite | 134 passed with local inputs; clean source: 109 passed, 25 explicitly skipped | Historical evidence for the published 0.4.2 version |
| 0.4.3 brightness widgets and descriptions | Actual packaged delegates/stock widgets pass toggle, drag, saved-ceiling/fill and bilingual wrap checks under Qt 6.4.1 | Native model, sensor, service and SVG provider are substitutes |
| 0.4.3 native Mac overview | Full Chinese/English windows with the new brightness row fit without clipping; README images updated | Offline UI mode disables camera and updater operations; Windows native layout is pending |
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

## Auto brightness integration (0.4.3)

Only the independent brightness runtime, policy and controller were adapted from the donor. The optional feature is enabled in Tweaks with a gray hint to Display → Brightness. The Display page controls Auto independently and retains stock brightness as a ceiling; output moves the fill without moving the knob. Stock firmware/resource hash checks and AArch64 import checks apply. No camera was connected or modified.

144 offline Python tests passed with generated inputs. A separate source-only copy passed 118 tests and explicitly skipped 26 that require excluded inputs. Actual C callbacks exercise ceiling edits without cancelling Auto or flashing the manual value, sensor fallback, idle/EVF guards, wake synchronization, master gating, durable feature/Auto commands, save failures and evenly spaced dimming output. Transaction tests cover failures in both startup configurations and exact recognition of published 0.4.2 plus both earlier local brightness builds, in both menu languages.

Qt 6.4.1 tests check the actual Tweaks page/controller and the packaged, stock-derived Display delegate with original stock widgets. Changing reported output moves only the white fill; lowering the ceiling keeps the fill left of the knob. Touch toggles retain menu availability. Real continuous drags match the stock slider in both directions and retain Auto. Bootstrap's actual route function targets Display only. Native model/types/API and SVG image provider are substitutes, so this does not prove the camera's Android/Qt lifecycle.

The hint now uses the actual stock SettingDescription component and switch-description spacing. Qt 6.4.1 checks cover Chinese and English at widths 1024, 768 and 620 with matching stock font/opacity; the narrow English description wraps to two lines and its row grows without clipping. The native Mac feature card was rendered and inspected in both languages using a test harness with camera and update operations disabled. The Windows overview passes translation/callback checks; its native rendering still needs Windows validation.

Mac universal and Windows x64 archives are rebuilt for 0.4.3. Archive audits verify the current payload hashes, both earlier local brightness recovery catalogs, published 0.4.2 recovery, the project license and the unchanged donor MIT notice. The license was updated in a separate commit before this release; existing older release assets remain unchanged. Native Windows GUI execution and all camera checks remain pending. Physical rear-display smoothness, Android/Qt loading and permissions, X2D/CFV cold boot and restoration need device validation. The integer-percent stock API still limits output granularity; evenly paced transitions reduce the filter's long tail but do not promise an imperceptible hardware transition. Generated evidence stays in ignored outputs.
