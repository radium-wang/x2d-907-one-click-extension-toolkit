# Changelog

## [0.4.16](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.16) — 2026-10-06

- Address user-reported restoration timeouts in the latest app, with reported success using 0.4.12. Long recovery/restoration steps now use the verified, serial-bound ADB channel with a 180-second budget instead of the factory RPC's 15-second capture. Preserve exact backup/payload gates, actual-state verification and strict completion receipts; failures, disconnects and unexpected output cannot report success. Camera payloads are unchanged; update the desktop app before restoring. The affected user's physical result remains pending.
- Remove obsolete installer/checksum release assets, retaining only the latest packages with the free-project notice. Preserve historical release entries, tags and changelogs.
- Publish Mac universal and Windows x64 packages. All 263 offline tests pass with local payloads; clean source passes 227 and skips 36. Seven restoration transport regressions cover a real 16-second shell task, unavailable factory RPC, script failure, symlink/FIFO logs, unverified targets, disconnection/timeout/bad receipts and private ADB timeout overrides. Mac native launch, 76 Mach-O / 38 PE dependency audits, all 33 current variants / 95 previous-byte catalog entries and both updater extraction checks pass. Camera payload bytes are identical to 0.4.15. The reported camera's new restoration path and native Windows execution remain pending.

## [0.4.15](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.15) — 2026-10-06

- Add optional stock EyeDetection to the desktop feature selection and camera Tweaks menu, with three-language controls. Verify DebugMode/bit 1 against firmware 4.2.0; read back each write, retain other debug options and recover the original state on master disable or restoration. Eye boxes require stock face detection and do not establish tracking autofocus. Physical camera behavior remains pending.
- Add disabled Pixel Shift and Face Tracking AF entries marked Coming soon; use the supplied Pixel Shift artwork and keep Mac/Windows layouts aligned.
- Preserve the verified 907 Easter egg choice during connection checks and upgrades; default it on for a stock 907 while retaining an explicit installed opt-out. Confirm its receipt separately from the main extension menu.
- Preserve the exact 0.4.14 manifest and all language bytes for recognized upgrade/restoration, coordinating legacy workers before recovery.
- Publish Mac universal and Windows x64 packages. All 256 offline tests pass with local payloads; clean source passes 220 and skips 36. Nineteen real-worker/C Eye checks, twelve generated-shell recovery checks, three-language Qt touch/XHR and first-use notice checks, native AppKit selection/907 checks and nine Windows layout previews pass. Mac native launch, 76 Mach-O / 38 PE dependency audits, all 33 current variants / 95 previous-byte catalog entries and both updater extraction checks pass. Physical camera Eye behavior and native Windows execution remain pending.

## [0.4.14](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.14) — 2026-10-06

- Show the free-project notice only until its first acknowledgement. Store the fixed camera preference independently of feature switches and retain it across GUI/camera restart and routine upgrades; keep all three languages and block settings until the initial preference read completes.
- Add a read-only stock DebugMode/EyeDetection diagnostic to Connected on Mac and Windows. Audit 0.4.8 source and exact saved payloads: no eye/debug option writes or new eye-tracking runtime. The reporting camera’s cause remains unconfirmed without its current flags and a stock-mode comparison.
- Preserve the exact 0.4.13 manifest and all language bytes for upgrade/restoration of every feature selection.
- Publish Mac universal and Windows x64 packages. All 212 offline tests pass with local payloads; clean source passes 180 and skips 32. Nine Qt notice layouts and three-language real-XHR/C-marker checks pass, including delayed reads, failed-write retry, fresh-engine persistence and 100 entries per language. Menu/brightness checks, native Mac launch, 76 Mach-O / 38 PE audits, archive/recovery hashes and updater extraction checks pass. Camera installation/restart behavior and native Windows execution remain pending.

## [0.4.13](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.13) — 2026-10-06

- Show the free-project notice every time the Tweaks menu opens. The confirmation button dismisses the notice and keeps the menu open; the notice blocks underlying settings input. Include Simplified Chinese, Traditional Chinese and English copy.
- Forward unhandled camera keys to the stock route. Preserve the exact 0.4.12 manifest and all language bytes for every feature selection's upgrade/restoration. Focus, speed and brightness native runtimes are unchanged.
- Publish Mac universal and Windows x64 packages. All 203 offline tests pass with local payloads; clean source passes 172 and skips 31. Nine Qt 6.4.1 notice layouts verify translated copy, wrapping, background input blocking, repeat entry and button dismissal; menu routing/Back/Escape checks pass across 100 resident-page entries. Mac native launch, 76 Mach-O / 38 PE audits, package/recovery hashes and updater extraction checks pass. Camera installation/visual behavior and native Windows execution remain pending.

## [0.4.12](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.12) — 2026-10-06

- Keep the original focus popup, model objects, liveview indicator and control-screen badge while the master or AF-C switch is off. Stop replacing stock focus compiled caches/AOT tables at GUI startup. Load the private three-mode popup and reversible icon bindings only when both switches are on; update AF-S/AF-C/MF and disabled icons together, and restore the original dynamic bindings when disabled.
- Preserve the exact 0.4.11 manifest and all language bytes for recognized upgrade/restoration of every feature selection. Add only the private focus popup to the exact extension target allowlist.
- Publish Mac universal and Windows x64 packages. All 202 offline tests pass with local payloads; clean source passes 172 and skips 30. Qt 6.4.1 checks verify three languages, the actual two-switch gate, original stock popup/indicator sources, repeated switching, all mode/disabled icons and restored dynamic bindings. Mac native launch, 76 Mach-O and 38 PE dependency audits, package/recovery-byte checks and updater extraction checks pass. Camera installation/visual behavior and native Windows execution remain pending.

## [0.4.11](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.11) — 2026-10-06

- Implement the confirmed desktop design on Mac and Windows: a log card on the left, independently selectable feature rows with dividers, a selection count, a gray installation summary and matching rounded controls. Both use a shared layout/color specification; Settings retains rounded language selection.
- Carry selected AF-C, focus acceleration and rear brightness through the installation manifest and boot configuration. Hide unselected camera rows, reject unavailable worker commands, omit the brightness runtime when unselected, and leave stock focus caches/resources untouched when AF-C is unselected. Preserve the exact 0.4.9/0.4.10 recovery manifest and language bytes.
- Address user-reported `FOCUS_RESOURCE_API_MISSING`: the pinned stock GUI's Qt resource functions are local static symbols absent from its dynamic symbol table. Verify their exact code prefixes and use the pinned addresses when dynamic lookup fails. A fingerprint mismatch still stops loading. The reported device failure is not a successful install; the corrected preload remains pending physical camera validation.
- Publish Mac universal and Windows x64 packages. 201 tests pass with local payloads; a clean source copy passes 172 and skips 29. Native Mac selection/Settings checks, nine Windows shared-layout previews, three-language/seven-mask Qt page checks, package/dependency/recovery audits and updater extraction checks pass. Native Windows execution and camera installation/restart/menu loading remain pending.


## [0.4.10](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.10) — 2026-10-06

- Strengthen the shared Mac/Windows preflight: verify stock focus/display binaries and the camera-service startup configuration, check both stock startup configurations and orphan extension targets before a first install, and verify a recognized installation's backup/configuration hashes, file ledger and actual payload hashes before accepting its service or menu receipt. Unknown modifications stop before ADB setup, upload or reboot.
- Report a modified camera GUI as a non-stock configuration with instructions to restore using the original modification tool, rather than a generic USB communication error. The toolkit does not overwrite or restore unknown modifications.
- Move the orange focus-acceleration guidance into its feature row on Mac and Windows: the feature can be installed, but older-lens users are advised not to enable it in the camera. Center the existing feature icons vertically and retain all three desktop languages.
- Publish Mac universal and Windows x64 packages. All 195 tests pass with local exact payloads; clean source passes 167 and skips 28. Three native Mac language previews, nine Windows shared-layout previews, 76 Mac Mach-O audits, 38 Windows PE audits, payload/recovery-byte audits and update ZIP extraction checks pass. Camera installation/restoration and native Windows execution remain unverified. Camera payloads are unchanged from 0.4.9; selectable installation is not included.

## Documentation update — 2026-10-06

- Highlight latest toolkit downloads and voluntary PayPal / Alipay support at the top of the README, matching the research repository. Preserve platform download links, setup instructions and validation limits. Published application archives are unchanged.
- 在 README 顶部突出最新版下载及 PayPal／支付宝自愿赞助入口，与研究仓库保持一致。保留平台下载链接、使用说明和验证范围，已发布安装包不变。


## [0.4.9](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.9) — 2026-10-06

- Port the reviewed focus popup and liveview mode icons into the existing App preload route. Use the second-generation focus icons, popup frame size and spacing while retaining first-generation fonts and borders. The popup adapts to AF-S/MF or AF-S/AF-C/MF according to the AF-C availability switch; installing or enabling the extension does not select AF-C.
- Preserve Simplified Chinese, Traditional Chinese and English headings and mode captions. Retain the accepted AF badge appearance in liveview, including the S without an extra white background.
- Keep public installation within the existing extension file targets and startup configuration changes. Reject vendor/raw partition targets and stock GUI replacement. Keep the exact 0.4.8 manifests and all language bytes for recognized upgrade/restoration.
- Publish Mac universal and Windows x64 packages. 184 tests pass with private payloads; clean source passes 155 and skips 29. Qt 6.4.1 checks load the new compiled popup from an empty-source resource and verify three languages, 18 private icon aliases, two/three-mode switching and mode-selection guards. Both packages pass dependency and archive audits; the Mac ZIP extraction also passes signature/runtime checks. The new App preload route has not been tested on a physical camera; the separately accepted direct-GUI installation does not establish that result.

## [0.4.8](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.8) — 2026-10-05

- Replace the desktop lens-change warning with guidance that focus acceleration works by tripling lens motor speed and is not recommended for older lenses. Update both bundled instructions and the README in Simplified Chinese, Traditional Chinese and English.
- Rename the Chinese focus-speed label to 对焦加速 / 對焦加速; keep the English names unchanged. Add the same guidance below the camera switch using the stock SettingDescription font, gray appearance and wrapping layout.
- Retain the exact published 0.4.7 manifest and all language payloads for recognized upgrade and interrupted restoration. Focus acceleration code and parameters are unchanged. After updating the desktop app to 0.4.8, use Connected → Install to update camera text. A recognized older install is restored first after confirmation.

- Publish Mac universal and Windows x64 packages. 173 offline tests passed; clean source: 146 passed, 27 skipped. Nine camera description layouts/touch checks, three native Mac language previews, nine Windows layout previews and package audits passed; native Windows and camera/lens behavior still need validation.

## Documentation update — 2026-10-05

- Put direct Windows and macOS 0.4.7 installer downloads at the top of the README and release notes, with platform requirements and extraction guidance. Published application archives are unchanged.

## [0.4.7](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.7) — 2026-10-05

- Add Traditional Chinese as a third language in Mac and Windows Settings. Desktop buttons, guidance, status, logs and remembered language follow the selection.
- Install hashed Traditional Chinese camera menu overlays, including feature labels and camera-side messages. Existing Simplified Chinese and English installs remain recognizable for upgrade and restoration. Switching camera language requires Connected → Install and, for a different existing installation, restore/reinstall confirmation in the selected language.
- Package the new catalog and camera overlays in both desktop distributions. Offline tests pass with local payloads; native Windows rendering and installation on a physical camera still require validation.

## [0.4.6](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.6) — 2026-10-04

- Fix Windows private ADB startup: use the supported `tcp:localhost:<port>` listener while probing IPv4 loopback directly. The numeric listen-host form used in 0.4.5 was rejected by ADB before camera installation started.
- Distinguish unsupported listen parameters, Windows access refusal and port conflicts instead of classifying every smart-socket failure as a network permission issue. Keep private-server ownership and cleanup.
- Publish Windows x64 and Mac universal packages at 0.4.6. The camera payload is unchanged; existing camera extensions do not need reinstallation. Native Windows startup and camera operations still need user/device validation.
- 169 offline tests passed with local inputs; clean source: 143 passed, 26 skipped. Mac dependency, 38 Windows PE and archive checks passed; see [validation details](docs/VALIDATION.md).
- Add an Alipay donation QR code alongside PayPal in the English/Chinese README and link the donation section from the repository Sponsor button. Documentation only; published application packages are unchanged.

## [0.4.5](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.5) — 2026-10-04

- Allow the Windows window to close during automatic or manual update checks. Cancel and reap only the owned read-only check process, including checks that have not started yet; retain exit protection during camera/driver operations and update installation.
- Use a foreground Windows ADB server on a private loopback socket for camera install/restore. Reap it at operation completion or failure, with Windows job-object cleanup if the owner crashes. Other applications' ADB servers are not stopped.
- Publish Mac universal and Windows x64 packages at 0.4.5; the camera payload is unchanged from 0.4.3/0.4.4, so existing camera extensions do not need reinstallation. Mac behavior is unchanged.
- 166 offline tests passed with local inputs; clean source: 140 passed, 26 skipped. Package audits passed. Native Windows shutdown, directory movement and abnormal-owner cleanup still need Windows validation.
- If an older version already left its ADB process running, close the app and finish camera work before ending only `adb.exe` whose executable location is inside that old toolkit folder, or restart Windows before upgrading.

## [0.4.4](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.4) — 2026-10-04

- Align the Windows interface with Mac: a white layout, rounded feature card with vector icons, gray descriptions, blue primary action, rounded controls and consistent typography. Restyle Settings and reinstall confirmation while retaining native input/accessibility and operation gates.
- Scale fonts and layout for each monitor, scroll the main page on short displays and reveal controls reached by keyboard.
- Publish Windows x64 and Mac universal packages at 0.4.4. The Mac interface and camera payload are unchanged from 0.4.3; an existing 0.4.3 camera extension does not need reinstallation.
- 153 offline tests passed with local inputs; source-only: 127 passed, 26 skipped. Six bilingual layout previews and package audits passed. Native Windows rendering, accessibility and monitor scaling still require Windows validation; see [validation details](docs/VALIDATION.md).

## [0.4.3](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.3) — 2026-10-04

- Replace the project license for subsequent versions with X2D/907 Noncommercial Distribution License 1.0: allow professional photography and free sharing/modification, prohibit software sales and paid installation without separate permission, and retain prior MIT and third-party permissions. Include the project license and third-party notices in newly built desktop packages; published archives remain unchanged.
- Add Auto Rear Screen Brightness to the Mac/Windows feature overview in both languages. Match the camera hint to the stock switch-description font, opacity and spacing, with wrapping for English.
- Add an optional Auto Brightness entry to Display → Brightness through Tweaks, with a smaller gray navigation hint. Enabling the feature also enables Auto; the Display switch then controls Auto independently. The rear slider sets the saved maximum while its white fill follows actual output and its knob stays at the maximum.
- Use evenly paced brightness transitions to reduce isolated dimming steps near the target. Stock output still has integer-percent precision.
- Extend both desktop builders and guarded install/restore to include the display library, back up camera-system startup configuration, roll back both configurations on failure, and retain published 0.4.2 and earlier local auto-brightness recovery records.
- Local/offline validation only; physical display, boot and restoration checks remain pending on X2D and CFV 100C.

### Upgrade and validation

- Upgrade the desktop app through Settings → Check for Updates or download the complete package. Then click Connected → Install to update the camera extension; a recognized older installation is restored first after confirmation.
- 144 offline tests passed with local inputs; source-only: 118 passed, 26 skipped. Qt 6.4.1 brightness/menu and bilingual native Mac layout checks passed. Package audits cover universal Mac dependencies, 38 Windows PE files, payload hashes and recovery catalogs. Windows native rendering and camera checks remain pending; see [validation details](docs/VALIDATION.md).

English first; [中文更新日志](#中文更新日志) follows below. Versions are listed newest first. Documentation-only changes do not imply a new application package.

## [0.4.2](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.2) — 2026-10-04

### Added

- Add a Settings window on Mac and Windows containing language selection, a remembered startup update-check switch, manual update checking, and a separate Download and Install Update button. Startup checks default to on; downloads and installation remain manual.
- Install Chinese or English camera menu labels from the app language. The camera QML stays literal text; Install selects the matching hashed files. Changing language requires another install.
- Confirm restoration before reinstalling an existing extension, with a Mac/Windows dialog in the target camera menu language. Cancel, closing the dialog or an invalid response leaves the camera unchanged. First and unchanged installs do not prompt. CLI reinstallation requires explicit `--confirm-reinstall`.

### Upgrade and validation

- Users on 0.4.1 can use Check for Updates; earlier versions need a manual desktop upgrade. Camera menus require Connected → Install after the app update.
- 134 offline tests passed with local inputs; clean source: 109 passed, 25 skipped. Native Mac Settings and bilingual confirmation were checked. Native Windows and camera reinstallation remain pending; see [validation details](docs/VALIDATION.md).

### Documentation

- Describe the optional 907 feature as **IBIS entry (Easter egg)** without revealing its contents. The optional entry label follows the installed language, page text is not quoted here.
- Add this changelog and links from the README. Future releases will record changes here.
- Add a PayPal support link to the repository Sponsor button and the English/Chinese README.

## [0.4.1](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.1) — 2026-10-03

### Fixed

- Refresh the camera menu receipt every five seconds while the entry is present, so a service restart can recover a lost receipt. Remove the receipt when the entry disappears.
- Distinguish installed files with a pending menu receipt from a verified installation. Explain when to tap **Skip**, open the camera main menu, and click **Connected** again; retain recovery access after camera checks pass.
- Recognize exact 0.3.3 files for upgrade and interrupted recovery while continuing to reject unknown file contents.
- Use ASCII download filenames to avoid GitHub renaming ZIP assets and breaking update package selection.

### Upgrade and validation

- Install 0.4.1 manually when upgrading from 0.3.3 or 0.4.0. Future desktop updates can use the update button. Updating the camera extension still requires **Connected → Install**.
- 122 offline tests passed with local inputs; a clean source checkout passes 97 and skips 25 tests requiring excluded inputs. Mac package replacement, backup and relaunch were checked. Windows self-update and the camera-side receipt fix still require device/user confirmation. See [validation details](docs/VALIDATION.md).

## [0.4.0](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.0) — 2026-10-03

### Added

- **Check for Updates → Download and Install Update** on Mac and Windows, using stable GitHub Releases, SHA-256 verification, package identity checks, a retained previous app, and relaunch after replacement.
- Prevent desktop updates and camera operations from running together.

### Changed

- Rename the desktop app to **X2D/907 One-Click Extension Toolkit** and update bilingual documentation and software screenshots.

### Known issue

- GitHub renamed the original ZIP filenames, preventing automatic package selection. This version is marked as a prerelease; use 0.4.1 instead.

## 0.3.3 — 2026-10-03

### Initial repository baseline

- Publish the Mac/Windows application source, offline tests and software screenshots.
- Include AF-C availability, focus speed buff, connection checks, installation, original-state restoration, and Chinese/English interface and logs.
- Include 907 menu adaptation, the optional **IBIS entry (Easter egg)**, and automatic Windows factory-interface driver preparation.
- Remove startup forcing of AF-C so the stock AF-S/MF selection can be retained. Power-cycle behavior, 907 changes and automatic driver installation still require device validation.

---

# 中文更新日志

## [0.4.16](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.16) — 2026-10-06

- 针对用户反馈最新版恢复通信超时、0.4.12 恢复成功的问题，将耗时撤回／恢复步骤改走已校验并绑定相机的 ADB 通道，等待上限 180 秒，避免旧工厂通信 15 秒限制。保留精确备份／载荷核验、实际状态回读及严格完成回执，失败、断线或异常输出不报告成功。相机载荷不变，先更新桌面 App 再恢复即可；受影响用户的实际结果仍待确认。
- 下架旧版本安装包及校验附件，仅保留带免费项目提示的最新版本下载；保留历史发布页、标签和更新日志。
- 发布 Mac 通用及 Windows x64 安装包。263 项带本地载荷的离线测试通过；纯源码通过 227 项、跳过 36 项。七项恢复通信回归覆盖真实 16 秒 shell 任务、工厂接口不可用、脚本失败、符号链接／FIFO 日志、未校验目标、断线／超时／异常回执及独立 ADB 等待参数。Mac 原生启动、76 个 Mach-O／38 个 PE 依赖审计、33 个当前载荷版本／95 个旧字节条目及两平台更新解压检查通过。相机载荷字节与 0.4.15 完全一致；反馈相机的新恢复流程及 Windows 原生运行仍待验证。

## [0.4.15](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.15) — 2026-10-06

- 新增可选人眼识别，桌面安装勾选及相机“耍起功能”开关支持三种语言。核验原厂 4.2.0 的 DebugMode／bit 1，每次写入均回读，保留其他调试选项，总关闭及恢复时还原原始状态。眼框需开启原厂人脸检测，不代表跟随对焦，实机行为仍待验证。
- 新增灰色不可选的像素位移及人脸追踪对焦，标注“即将到来”；使用用户提供的像素位移图标，Mac／Windows 布局同步。
- 连接检查与升级时保留已核验的 907 彩蛋选择；原厂 907 首次安装默认勾选，已安装明确取消时继续保留取消，独立核验彩蛋菜单回执。
- 保留 0.4.14 精确清单及三种语言字节，支持已知升级与恢复；撤回功能前先协调旧版服务及 worker。
- 发布 Mac 通用及 Windows x64 安装包。256 项带本地载荷的离线测试通过；纯源码通过 220 项、跳过 36 项。19 项真实 worker／C 人眼检查、12 项实际生成 shell 恢复检查、三语言 Qt 点击／XHR 及首次提示、原生 AppKit 功能选择／907 检查、九种 Windows 布局预览通过。Mac 原生启动、76 个 Mach-O／38 个 PE 依赖审计、33 个当前载荷版本／95 个旧字节条目及两平台更新解压检查通过。人眼实机行为与 Windows 原生运行仍待验证。

## [0.4.14](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.14) — 2026-10-06

- 免费提示改为首次确认后不再显示，记录保存在相机端，与功能开关独立；重启及常规更新后保留，三种语言同步更新，首次读取记录期间阻止设置操作。
- Mac、Windows 的“已连接”增加原厂 DebugMode／EyeDetection 只读检查。核对 0.4.8 源码及已保存的精确载荷，没有人眼调试写入或新增人眼跟随对焦运行库；用户眼框来源仍需反馈相机的状态和原厂模式对比确认。
- 保留 0.4.13 精确清单及三种语言旧字节，支持全部功能选择的升级与恢复。
- 发布 Mac 通用及 Windows x64 安装包。212 项带本地载荷的离线测试通过；纯源码通过 180 项、跳过 32 项。九种 Qt 弹窗布局及三语言真实 XHR／C 记录检查通过，覆盖延迟读取、写入失败重试、重建界面后的持久记录和每种语言 100 次重进；菜单／亮度检查、Mac 原生启动、76 个 Mach-O／38 个 PE 审计、安装包／恢复字节及更新解压检查通过。相机安装重启行为与 Windows 原生运行仍待验证。

## [0.4.13](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.13) — 2026-10-06

- 每次进入“耍起功能”菜单时显示免费项目提示，点击“好的，我没被骗”关闭弹窗并留在菜单；弹窗显示期间阻挡底下的设置操作。补齐简体中文、繁体中文和英文。
- 未处理的相机按键继续交给原厂路由；保留 0.4.12 精确清单及三语言字节，支持所有功能组合的升级与恢复。对焦、加速和亮度的原生运行库不变。
- 发布 Mac 通用和 Windows x64 安装包。完整离线测试 203 项通过；干净源码 172 项通过、31 项跳过。九组 Qt 6.4.1 弹窗检查验证翻译、换行、底层输入阻挡、重复进入和按钮关闭；菜单路由、返回及 Escape 检查通过 100 次常驻页面进出。Mac 原生启动、76 个 Mach-O／38 个 PE 审计、安装包及恢复哈希、更新解压检查通过。相机安装及视觉行为、Windows 原生运行仍待验证。

## [0.4.12](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.12) — 2026-10-06

- 当“耍起功能”或 AF-C 开关关闭时，保留原厂对焦弹窗、列表对象、实时取景指示和主页图标。启动时不再替换原厂对焦缓存；仅在两个开关都开启时加载三模式弹窗并同步 AF-S／AF-C／MF 及灰色图标，关闭后恢复原厂动态绑定。
- 保留 0.4.11 的精确清单和三种语言字节，支持所有已选功能组合的升级与恢复；安装白名单仅新增私有对焦弹窗。
- 发布 Mac 通用和 Windows x64 安装包。完整离线测试 202 项通过；干净源码 172 项通过、30 项跳过。Qt 6.4.1 验证三种语言、实际双开关逻辑、原厂弹窗与取景控件源文件、反复切换、全部模式及灰色图标、动态绑定恢复。Mac 原生启动、76 个 Mach-O／38 个 PE 依赖审计、安装包与恢复字节、更新解压检查通过。相机安装及视觉行为、Windows 原生运行仍待验证。

## [0.4.11](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.11) — 2026-10-06

- Mac 与 Windows 正式采用已确认的界面：左侧日志卡片、可独立勾选的功能行与分隔线、选择数量、浅灰安装摘要和统一圆角按钮。两端共用尺寸与配色配置，设置里的语言选择保持圆角。
- 选择结果进入安装记录及开机配置；未选择的相机功能行隐藏，服务拒绝开启未安装功能。不选择自动亮度时不安装亮度运行库；不选择 AF-C 时保留原厂对焦缓存及资源。保留 0.4.9／0.4.10 的精确恢复记录和三种语言字节。
- 针对用户反馈的 `FOCUS_RESOURCE_API_MISSING` 补上原厂 Qt 本地静态函数定位及代码指纹核验。指纹不匹配继续停止加载。用户反馈的失败安装不能视为成功，新预载修复仍待实机验证。
- 发布 Mac 通用与 Windows x64 包。201 项本地载荷测试通过，纯源码 172 项通过、29 项跳过。Mac 原生勾选与设置、Windows 九份共用布局、三种语言七种掩码的 Qt 功能行、安装包依赖／恢复文件／更新解压检查通过；Windows 原生运行与相机安装、重启和实际菜单仍待验证。

## [0.4.10](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.10) — 2026-10-06

- 加强 Mac／Windows 共用的安装前检查：核验原厂对焦、显示程序与 camera-service 启动配置；首次安装前检查两份原厂启动配置及残留扩展文件；已有安装在接受服务与菜单回执前，核验已识别版本的备份、启动配置、文件记录和实际文件哈希。未知修改会在启用 ADB、上传或重启前停止操作。
- 修改过的相机 GUI 改为明确提示非原厂状态，并提示先用原修改工具恢复，不再笼统显示 USB 通信错误。本应用不会覆盖或恢复未知修改。
- Mac 与 Windows 的橙色对焦加速说明移入对应功能行，明确“可安装，但不建议老镜头用户在相机内开启该功能”；原有图标按行垂直居中，保留三种桌面语言。
- 发布 Mac 通用与 Windows x64 安装包。带精确本地载荷的 195 项测试全部通过；纯源码 167 项通过、28 项跳过。三种语言的 Mac 原生预览、九份 Windows 共用布局预览、76 个 Mac Mach-O、38 个 Windows PE、载荷／恢复字节及更新 ZIP 解压检查通过。实机安装／恢复和 Windows 原生运行仍待验证。相机载荷与 0.4.9 相同，选择安装功能尚未接入。

## 未发布 — 0.4.9 候选

- 将已验收的对焦弹窗和实时取景模式图标接入 App 原有预载流程。采用二代对焦图标、弹窗底框尺寸和间距，保留一代字体和边框。AF-C 功能开关控制 AF-S/MF 两项与 AF-S/AF-C/MF 三项切换；安装或开启扩展不会自动选择 AF-C。
- 保留简体中文、繁体中文和英文标题、模式说明。实时取景沿用已验收的 AF 底框样式，S 后没有额外白底。
- 公开版只允许现有扩展文件和启动配置的修改，拒绝 vendor/原始分区及原厂 GUI 替换。保留 0.4.8 精确清单与全部语言字节，用于识别旧版、升级及恢复。
- 发布 Mac 通用版和 Windows x64 安装包。带本地载荷的 184 项测试通过；纯源码为 155 项通过、29 项跳过。Qt 6.4.1 从空源码资源加载新编译弹窗，检查三种语言、18 个私有图标、两项/三项切换及模式选择保护。两份安装包的依赖及包内文件检查通过，Mac 解压后的签名和运行库检查也通过。新的 App 预载路径尚未在相机上验证；此前直接替换 GUI 的实机验收不能替代这项验证。

## [0.4.8](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.8) — 2026-10-05

- 删除电脑端换镜头警告，改为“对焦加速通过将镜头转速提高三倍实现，不建议老镜头用户开启。”；同步简体、繁体、英文、包内说明及 README。
- 中文名称改为“对焦加速 / 對焦加速”，英文名称不变；相机开关下方加入同样的提示，使用原厂说明字号、灰度和自动换行布局。
- 保留已发布 0.4.7 的精确清单及所有语言载荷，支持识别旧安装、升级和中断恢复。加速实现和参数未改动；电脑端升级到 0.4.8 后，点击“已连接 → 一键安装”更新相机文案；识别到旧安装时，经确认先恢复再安装。

- 发布 Mac 通用与 Windows x64 安装包。173 项完整离线测试通过；纯源码为 146 项通过、27 项跳过。九份相机说明布局/触控检查、三种语言的 Mac 原生预览、九份 Windows 布局预览和安装包校验通过；Windows 原生及相机/镜头行为仍待验证。

## 文档更新 — 2026-10-05

- 在 README 与发布说明开头提供 Windows 和 Mac 0.4.7 安装包直达链接，写明系统要求及完整解压提示；已发布的软件压缩包保持不变。

## [0.4.7](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.7) — 2026-10-05

- Mac 与 Windows 设置页新增“繁體中文”，界面按钮、引导、状态、日志和保存的语言选择会一起切换。
- 安装时写入经过哈希校验的繁体相机菜单文件，覆盖功能名称和相机内提示。已安装的简体中文、英文版本仍可识别并恢复。改变相机语言需点击“已连接 → 一键安装”；若当前已安装其他语言，会先按目标语言提示恢复和重新安装。
- 双平台安装包包含新翻译表与相机文件；带本地载荷的离线测试已通过。Windows 原生显示和相机实装仍待验证。

## [0.4.6](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.6) — 2026-10-04

- 修复 Windows 独立 ADB 启动：监听参数使用 ADB 支持的 `tcp:localhost:<端口>`，就绪检查仍直连本机 IPv4。0.4.5 使用的数字监听地址被 ADB 拒绝，此时相机安装尚未开始。
- 区分监听参数不兼容、Windows 拒绝访问和端口冲突，不再把所有 smart-socket 错误误报为网络权限问题；保留独立进程及退出清理。
- 发布 0.4.6 Windows x64 与 Mac 通用安装包。相机载荷保持不变，已有相机扩展无需重装；Windows 原生启动及相机操作仍待用户或实机验证。
- 完整离线测试 169 项通过；纯源码为 143 项通过、26 项跳过；Mac 依赖、38 份 Windows PE 和安装包检查通过，详见 [验证说明](docs/VALIDATION.md)。
- 在中英文 README 的 PayPal 赞助链接旁加入支付宝收款码，并从仓库赞助按钮链接到捐赠说明。仅修改文档，已发布安装包保持不变。

## [0.4.5](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.5) — 2026-10-04

- Windows 自动或手动检查更新期间允许关闭窗口，取消并回收本次只读检查进程，也覆盖关闭时检查尚未启动的情况；相机/驱动操作及软件更新安装期间仍保留退出保护。
- Windows 相机安装/恢复改用独立本机端口上的前台 ADB 服务，操作完成或失败后回收；所属进程异常退出时由 Windows Job Object 清理，不结束其他软件的 ADB 服务。
- 发布 0.4.5 Mac 通用与 Windows x64 安装包；相机载荷与 0.4.3/0.4.4 相同，已有相机扩展无需重新安装，Mac 行为不变。
- 完整离线测试 166 项通过；纯源码为 140 项通过、26 项跳过，安装包校验通过；Windows 原生退出、目录移动及异常退出清理仍待 Windows 验证。
- 若旧版已经残留 ADB，先关闭窗口并等待相机操作完成，再在任务管理器确认文件位置后仅结束该旧软件目录下的 `adb.exe`，或重启 Windows 后升级。

## [0.4.4](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.4) — 2026-10-04

- Windows 界面对齐 Mac：白色布局、带图标的圆角功能卡片、灰色说明、蓝色主按钮及统一字体间距；设置页和重新安装确认也同步调整，保留原生输入、可访问性及操作门控。
- 按每个显示器的 DPI 缩放字体和布局，小屏幕可滚动并自动显示键盘导航选中的控件。
- 发布 0.4.4 Windows x64 与 Mac 通用安装包。Mac 界面及相机载荷与 0.4.3 相同，已安装 0.4.3 相机扩展无需重新安装。
- 完整离线测试 153 项通过；纯源码为 127 项通过、26 项跳过。六份中英文布局预览和安装包校验通过；Windows 原生显示、可访问性和显示器缩放仍待 Windows 验证，详见 [验证说明](docs/VALIDATION.md)。

## [0.4.3](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.3) — 2026-10-04

- 后续版本改用 X2D/907 非商业分发许可证 1.0：允许职业摄影、修改和免费分享；出售软件、改版及收费安装须另获授权。保留历史 MIT 和第三方许可，新构建的桌面包附带项目许可与第三方说明，已发布包保持不变。
- Mac/Windows 中英文功能介绍新增后屏自动亮度；相机引导文字复用原厂开关说明的字号、灰度和间距，英文自动换行。
- 在耍起功能中加入“在亮度菜单中加入自动亮度”及灰色小字引导；开启时同时启用自动亮度，之后在显示 → 亮度中独立开关。滑块圆球设定最高亮度，白线跟随当前输出，自动亮度变化不移动圆球。
- 减光改为均匀的小步推进，减少临近目标时逐格停顿变长的现象；原厂接口仍按整数百分比输出。
- 安装与恢复增加屏幕配置备份、双配置回滚，保留已发布 0.4.2 和前两份本地自动亮度测试版的恢复记录；Mac/Windows 构建同步支持。
- 只做本地与离线验证；X2D/CFV 100C 的屏幕、启动和恢复仍待实机验证。

### 升级与验证

- 在设置 → 检查更新中升级电脑端 App，或下载完整安装包。之后点击已连接 → 一键安装更新相机扩展；识别到旧版时，会经确认先恢复再安装。
- 完整离线测试 144 项通过；纯源码为 118 项通过、26 项跳过。Qt 6.4.1 亮度/菜单检查与 Mac 原生中英文布局检查通过。安装包已校验 Mac 通用依赖、38 份 Windows PE 文件、载荷哈希和恢复记录；Windows 原生显示及相机实机检查仍待完成，详见 [验证说明](docs/VALIDATION.md)。

版本按从新到旧排列。仅修改文档不代表发布了新安装包。

## [0.4.2](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.2) — 2026-10-04

### 新增

- Mac / Windows 新增设置页，集中提供语言选择、可记忆的启动自动检查更新开关、手动检查更新和独立的下载安装按钮。自动检查默认开启，只查找新版，下载安装仍由用户点击。
- 安装时按 App 语言写入中文或英文相机菜单文案。相机端 QML 仍为字面字符串；安装选择对应哈希文件。更换语言需重新安装。
- Mac / Windows 在恢复并重新安装现有扩展前，按目标相机菜单语言弹出确认。取消、关闭弹窗或无效回复均不修改相机；首次安装和配置未变化时不弹窗。命令行重新安装需显式使用 `--confirm-reinstall`。

### 升级与验证

- 0.4.1 用户可点击检查更新；更早版本需手动升级电脑端软件。更新相机菜单需在 App 升级后再点击已连接 → 一键安装。
- 含本地输入的离线测试 134 项通过；纯源码为 109 项通过、25 项跳过。Mac 原生设置页与中英文确认弹窗已检查；Windows 原生操作和相机重新安装仍待验证，详见 [验证说明](docs/VALIDATION.md)。

### 文档

- 907 选项统一称为 **防抖入口（彩蛋）**，说明不再透露彩蛋内容；入口名称随安装语言变化，此处不引用页面原文。
- 新增本更新日志及 README 入口，后续版本在此记录改动。
- 在仓库赞助按钮及中英文 README 中加入 PayPal 赞助链接。

## [0.4.1](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.1) — 2026-10-03

### 修复

- 菜单入口存在时每 5 秒刷新回执，修复功能服务重启后回执丢失的问题；入口消失时仍撤回回执。
- 区分“功能文件已安装、菜单回执待刷新”和“安装已核验”，提示用户点击相机上的 **跳过**、打开主菜单，再点击 App 的 **已连接**；相机检查通过后保留恢复入口。
- 支持精确识别 0.3.3 文件以完成升级和中断恢复，继续拒绝覆盖未知内容。
- 下载附件改用英文文件名，避免 GitHub 自动改名导致更新包匹配失败。

### 升级与验证

- 从 0.3.3 或 0.4.0 升级时，先手动安装 0.4.1；后续电脑端更新可使用更新按钮。相机扩展仍需点击 **已连接 → 一键安装** 更新。
- 含本地输入的离线测试 122 项通过；纯源码环境为 97 项通过、25 项因缺少私有输入跳过。Mac 应用替换、备份及重开已验证；Windows 软件自动更新和相机菜单回执修复仍待实机或用户确认。详见 [验证说明](docs/VALIDATION.md)。

## [0.4.0](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.0) — 2026-10-03

### 新增

- Mac 和 Windows 加入 **检查更新 → 下载并安装更新**，通过 GitHub 稳定版发布获取安装包，校验 SHA-256 与应用身份，保留上一版并在替换后重新打开。
- 软件更新与相机操作互斥。

### 调整

- 桌面软件更名为 **x2d/907一键扩展功能-工具包**，更新中英文说明和软件截图。

### 已知问题

- GitHub 自动改名原下载附件，导致更新包无法匹配。本版已标记为预发布，请使用 0.4.1。

## 0.3.3 — 2026-10-03

### 首次入库版本

- 收录 Mac / Windows 应用源码、离线测试及软件截图。
- 包含 AF-C 入口、对焦加速 buff、连接检查、一键安装、一键恢复原状，以及中英文界面和日志。
- 包含 907 菜单适配、可选 **防抖入口（彩蛋）**，以及 Windows 工厂接口驱动自动准备。
- 移除开机强制切回 AF-C 的逻辑，保留原厂 AF-S / MF 选择；关机再开机行为、907 改动及自动驱动安装仍待实机验证。
