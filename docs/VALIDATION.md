# Validation boundaries — 0.4.9

## Unreleased camera integrity checks and desktop guidance

The source suite runs 195 tests: 167 pass and 28 skip because exact generated payload bytes are absent. Eleven new tests exercise read-only preflight with substituted factory USB/file responses. A modified stock GUI, changed focus/display binaries or startup configuration, orphan extension targets, altered installed payloads despite a ready service/menu receipt, missing files, symlinks, duplicate ledgers and unknown transaction state all stop without ADB setup, upload, restoration or reboot. A stock fixture passes, and a recognized current-install fixture passes exact file checks. Existing interrupted recovery and transaction rollback checks remain separate.

The shared backend is used by both desktop platforms. It checks the pinned GUI, camera-service, camera-system, libaaa, librcam and camera-service startup file, then the applicable GUI/display startup configurations and the installation's exact known files. The camera-service startup digest was checked against the locally extracted stock 4.2.0 configuration. A service response or menu receipt alone no longer establishes installation integrity. A GUI hash mismatch now produces explicit non-stock recovery guidance instead of a generic USB error.

These checks establish the specified files' compatibility, not that every firmware file or every byte of live process memory is stock. They do not inspect the physical display or infer the current AF mode from a screenshot. Arbitrary runtime injection and modifications outside the checked files are not covered. A read-only device status attempt did not complete factory communication; the connected camera's state remains unverified. No camera files or settings were changed, and no camera was restarted.

Mac ARM64 source compilation passes. The orange acceleration description is inside the feature row in both desktop sources; Windows shared-layout checks cover its bounds and color. Native Windows rendering and the expanded checks on X2D/CFV hardware still require validation. Feature-selection installation remains a separate proposed UI change; these checks do not claim that the selectable demo is an implemented installer. Published 0.4.9 packages have not been rebuilt or replaced.

源码离线测试共 195 项：167 项通过、28 项因缺少精确载荷跳过。新增 11 项检查使用模拟的 USB／文件响应，验证非原厂文件、残留扩展、被改动的已安装文件、缺失文件、符号链接、重复记录及未知事务状态会在写入前被拦截。当前仅核验上述指定文件，不能据此证明整个固件或全部运行内存均为原厂，也不能代替相机屏幕与当前对焦模式检查。只读实机检查未完成通信，当前相机状态尚未核实；没有安装、恢复、改变相机设置或重启。Mac 源码编译通过，Windows 原生显示及新增检查的实机验证仍待完成，已发布安装包不变。

## Focus popup and liveview mode icons (0.4.9)

184 offline tests pass with the locally generated payload. The real native preload transaction is run against substituted memory and Qt resource APIs: success, each of seven partial-write rollbacks, stock mismatch, disable/retry markers, missing resource APIs, resource registration failure and memory-open failure are covered. Unknown file opens fail the harness. Public manifest tests reject policy files, vendor/raw partition targets and stock GUI replacement in the base payload and both language overlays, before payload file access and without USB access. Exact published 0.4.8 manifests and all per-language bytes remain recognized and recoverable.

Qt 6.4.1 registers and verifies all 18 private icon aliases and loads the actual compiled popup through its cache hook while the resource source is empty. Simplified Chinese, Traditional Chinese and English checks cover headings/captions, two/three-mode switching, the reviewed frame geometry, retaining the selected mode when enabling, refusing disable while AF-C is selected and emitting the MF selection signal. An image provider and camera services are substituted; pixels are not rendered. The liveview unit and icon bytes match the separately accepted GUI candidate.

Clean source passes 155 tests and skips 29 requiring excluded generated inputs. The Mac universal package passes 76 Mach-O audits and the Windows x64 package passes 38 PE audits. Archive checks verify all 32 current payload variants, the exact 59-file recovery byte catalog and the absence of extra native-package files. A Mac ZIP extraction roundtrip passes strict deep signature verification, embedded Python/USB runtime loading and packaged 0.4.8 recovery recognition in all three languages. These are package checks, not camera installation tests.

Public packages retain the old startup preload approach and do not replace the stock GUI executable. No camera was accessed for this App change. The direct-GUI installation was accepted separately on an X2D, but the new App preload route, native SVG provider, cold boot, hardware rendering, AF-C backend and CFV behavior still need device checks.

The stock GUI hash gate remains enforced. A camera with the separate research GUI installed is rejected; this App does not overwrite that GUI or restore its vendor partition.

## Traditional Chinese desktop and camera menus (0.4.7)

The third desktop language is backed by a static Traditional Chinese catalog in both Mac and Windows packages. Offline checks cover persisted selection, translated diagnostics, target-language reinstall confirmation, and Traditional camera QML overlays. The overlay files have recorded SHA-256 hashes and retain the same install targets as the base files. Both 0.4.6 Simplified Chinese and English manifests remain recognized by the 0.4.7 restore/upgrade path; the camera-side functional binaries have identical hashes. The complete local-payload suite passes 171 tests; clean source passes 146 and skips 25 requiring excluded payloads. Both desktop archives include the new catalog and overlays, and the Windows PE and Mac dependency audits pass. No camera or Windows host was accessed for this change; native Traditional Chinese layout and physical camera behavior remain pending.

## Windows ADB listen address (0.4.6)

User feedback from 0.4.5 reports private ADB startup failure before camera installation. The [official ADB socket implementation](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/socket_spec.cpp) accepts an empty host or literal `localhost` for an IPv4 loopback listener; it rejects the numeric `127.0.0.1` listen host with “listening on specified hostname currently unsupported.” The bundled Windows binary contains that same diagnostic. The fix uses `tcp:localhost:<private port>` for the server and all clients, while the direct readiness probe connects to `127.0.0.1`. Foreground ownership, job-object cleanup and the camera checks are retained.

The complete offline suite passes 169 tests with local inputs; a clean source copy passes 143 and skips 26. New regressions verify the literal supported launch address, endpoint propagation, numeric readiness probing and distinct sanitized diagnostics for unsupported host, access denial and port conflict. These use process/Win32 substitutes. Mac universal dependency checks and 38 Windows PE audits pass; archive checks verify unchanged camera payloads and updated application sources. Native Windows ADB startup and camera install/restore remain pending. No real ADB server, camera or driver was accessed; published 0.4.5 archives are unchanged.

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

0.4.9 新版 UI 采用 App 原有预载流程。带本地载荷的 184 项离线测试通过，覆盖七次内存写入的部分失败回滚、私有资源注册失败、公开版写入范围及 0.4.8 各语言恢复识别。Qt 6.4.1 检查实际编译弹窗的空源码加载、18 个图标、三种语言和两项/三项切换；图像提供器和相机服务使用替身，未渲染相机像素。本次 App 开发未访问相机，新的预载路径和硬件行为仍待实机验证，此前直接 GUI 替换的验收不能替代这项检查。

纯源码为 155 项通过、29 项因缺少私有输入跳过；Mac 的 76 个 Mach-O 与 Windows 的 38 个 PE 文件检查通过。两份压缩包核对全部 32 个当前语言载荷及 59 份恢复字节；Mac 解压后的签名、内置运行库和三种语言旧版识别通过。原厂 GUI 哈希门槛保留，研究直写版不能叠加安装；App 不会替换研究 GUI。

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

## Focus acceleration guidance (0.4.8)

The desktop guidance, Chinese switch name and a stock-style description below that switch were updated in three languages. Only PlayPage text/layout changes in the current camera payload; native libraries, service scripts, acceleration parameters and brightness behavior are unchanged. Exact published 0.4.7 manifests and old bytes in all three languages are retained for recognized upgrade and interrupted restoration; altered hashes and a tampered catalog are rejected.

173 offline tests pass with generated inputs; clean source passes 146 and skips 27 requiring excluded inputs. Qt 6.4.1 checks the actual packaged page using stock widgets and substitute camera services in nine language/width cases: description typography/opacity match stock, wrapping does not clip, real clicks toggle and master-off blocks writes. Mac native preview checks cover all three languages without camera/update operations; Windows previews use the shared layout with host font fallback. Windows native rendering, camera loading and lens behavior still need device/native validation. Removing the old warning does not constitute a lens hot-swap hardware test. The 0.4.8 release archives contain this guidance and the old recovery catalog; the published 0.4.7 archives remain unchanged.
