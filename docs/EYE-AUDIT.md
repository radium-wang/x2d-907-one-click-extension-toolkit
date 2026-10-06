# Optional stock EyeDetection switch in 0.4.15

Version 0.4.15 adds **Eye Recognition** as the fourth selectable installation feature. The original three features remain selected by default; Eye Recognition is optional and installation does not enable it. When selected, its switch appears in **Tweaks**. Pixel Shift and Face Tracking Autofocus are disabled **Coming soon** entries in the desktop app and install no functionality.

The implementation uses the existing first-generation 4.2.0 `system.debug_mode` and `system.debug_options` properties. EyeDetection is bit 1. It does not install a detection engine or add tracking autofocus. The stock liveview overlay also requires face detection to be enabled in the original camera menu; the toolkit does not change that setting. Eye boxes alone establish neither face-tracking nor eye-tracking AF. The new switch has firmware analysis and offline tests, but has not been tested on a physical camera.

The stock `debug_options` getter returns zero while DebugMode is off, even when other debug flags are saved. The worker therefore reads the fixed `/data/config/system.ini` `[Default]` values before its first change and checks the effective property replies. The stored mask accepts the verified enum serialization or numeric values from 0 to 127; malformed, duplicated or unknown values stop Eye operations. Missing debug keys use the stock defaults, false and zero. Configuration is written only through the stock property setters, never by editing the INI file.

- With DebugMode originally off, ON saves the complete hidden mask, sets the mask to EyeDetection only, verifies it, then enables DebugMode. OFF verifies DebugMode is off before restoring the saved mask, so hidden Recalibrate, Touch or other flags are not activated.
- With DebugMode originally on, ON adds EyeDetection and OFF removes it while preserving the other current flags. If EyeDetection was already on, turning the feature off really disables it; turning off Tweaks or restoring the software later returns its original Eye bit.
- Turning off Tweaks restores settings still owned by the toolkit, clears its saved choice and releases the baseline after successful readback. Software restoration does the same before removing the extension. Later user changes are not restored from an old released snapshot. Other flags changed while DebugMode was originally on are retained. If external changes conflict with restoration of an originally hidden mask or debug master, the operation stops and retains its recovery records instead of overwriting them.
- A persistent transaction record identifies recoverable partial writes. Each setter is checked before the next step, including a setter that returns success without applying the change. Unknown baselines, orphaned preferences and mismatched records are rejected. An unreadable state remains unknown and does not display as a confirmed OFF state.

The worker pins the original `camera-system`, `odindb-send` and `toybox` binaries before these operations. The loopback service accepts only fixed feature actions. These are offline implementation safeguards, not evidence that the new feature works on a camera.

# Historical eye boxes reported with 0.4.8

The report describes eye boxes without tracking autofocus, similar to the stock DebugMode eye-detection option. It does not establish working eye-tracking AF. The reporting camera's debug flags have not been read, so its specific cause is still unconfirmed.

The audit checked the `v0.4.8` sources and every preserved 0.4.8 payload variant against the pinned manifest: 32 exact file/language variants. The packaged AF-C controller, speed controller, brightness controller and worker match their tagged sources. These camera text payloads contain no eye-detection/debug option writer. The native menu, AF-C controller, speed worker and loopback service are unchanged between 0.4.7 and 0.4.8; 0.4.8 changed feature descriptions, not the AF-C runtime.

The 0.4.8 preload changes the main-menu cache, stock control-screen cache pointer, focus popup cache and the `CameraUI.canChangeAfc` gate. Its stock control-screen content remains unchanged. It does not replace liveview face/eye overlays, install a donor detection engine, or write `system.debug_mode` / `system.debug_options`. The AF-C worker does select the existing `camera.focus_mode` when the user enables AF-C; effects of that stock mode on detection need a camera comparison and cannot be ruled out by the absence of debug writes alone.

The pinned original 4.2.0 GUI already contains left/right eye landmark fields, eye ROI types and eye-symbol rendering. Its face-detection availability comes from the camera's stock capability fields, separately from `canChangeAfc`. The original camera service also handles the EyeDetection bit (1) and FaceDetection bit (2) in its debug-options path. Those flags are diagnostic settings, not proof of tracking autofocus. Audit baselines:

- camera-gui SHA-256: `16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0`
- camera-service SHA-256: `fbcf828f73bca13f0c8b95e7dd0b95ac483ae36954ec06179098c8a1a65f9f82`
- Preserved 0.4.8 manifest SHA-256: `70048064578e9cda6aed02934157769991ff8e1b2a353bfd54ca6310c9ee4a70`

In 0.4.14, **Connected** reads the current stock `system.debug_mode` and `system.debug_options` through the factory transport, without enabling ADB or setting either property for this diagnostic. Both desktop apps report enabled, disabled or unreadable. DebugMode must be on and bit 1 set for the reported eye-debug flag to be active. An unreadable response remains unknown; it does not count as disabled. That version neither enables nor clears these settings during installation/restoration, so a prior active setting can remain active. The diagnostic remains read-only in 0.4.15; writes require the optional installed Eye switch or restoration of its recorded changes.

If the reporting camera has the active EyeDetection bit, that confirms the stock diagnostic option is active and makes earlier debug configuration a supported explanation. It still does not prove when it was enabled. If the bit is off, do not attribute the boxes to that option: compare stock AF-S and AF-C under the same scene, lens and face-detection setting, recording ROI state and focus behavior. That device comparison is pending; no camera settings, reboot or capture were performed in this audit.

# 0.4.15 可选原厂人眼识别开关

0.4.15 将“人眼识别”作为第四项可选安装功能；默认仍选择 AF-C、对焦加速和后屏自动亮度三项，人眼识别默认不勾选。勾选安装后，耍起功能中出现对应开关，安装本身不启用它。“像素位移”和“人脸追踪对焦”在电脑端显示为灰色“即将到来”，不能勾选，不安装相关功能。

人眼识别使用原厂 4.2.0 已有的 DebugMode / EyeDetection 位，不加入检测引擎或跟随对焦。还需在原厂菜单开启人脸检测，工具不改动该设置；眼部框不代表人脸或人眼跟随对焦。此开关已完成固件分析和离线检查，尚未实机测试。

首次修改前，工具从固定的 `/data/config/system.ini` 的 `[Default]` 节读取原始设置，并与原厂属性回读核对；关闭 DebugMode 时返回零的有效掩码不能当作保存值。只通过原厂属性接口写入，不直接改写配置文件。原 DebugMode 关闭时，开启只激活 EyeDetection，关闭先确认 DebugMode 已关闭，再恢复保存的隐藏位；原 DebugMode 开启时，只添加或移除 Eye 位，保留其他当前位。

人眼开关关闭时真正停止该选项；总开关关闭或恢复软件时，恢复本工具仍持有的原始设置，包括此前已经开启的原厂 Eye 位。确认恢复后释放记录，后续用户设置不再受旧快照影响。原 DebugMode 开启期间新增的其他位保留；若外部改动与原隐藏设置或总开关恢复冲突，则停止操作、保留恢复记录，提示先将其他调试选项恢复到开启人眼识别时的状态。每一步写入均回读，中断仅按已记录的合法事务状态恢复；未知或缺失记录不会被当作可恢复设置。

# 0.4.8 人眼框反馈历史核查

反馈是“有人眼框但无法跟随对焦”，与原厂 DebugMode 人眼选项的表现相似。已核对 0.4.8 标签源码及 32 个原样保存的载荷/语言文件：没有开启人眼调试的写入，也没有新增人眼检测或跟随对焦运行库。0.4.8 的 AF-C 原生菜单、控制器、服务和速度代码与 0.4.7 相同。

原厂 4.2.0 已有眼部位置、眼部 ROI、眼部框绘制和人眼调试选项。0.4.8 不会清除用户原有调试设置，所以旧设置可能保留；但 AF-C 会使用原厂对焦模式，仍需排除它对检测状态的间接影响。尚未读取反馈相机的 DebugMode/EyeDetection，不能仅凭眼框判定残留，更不能宣称已实现人眼跟随对焦。0.4.15 新增可选写入，不改变这项历史核查结论。

0.4.14 的“已连接”会只读检查并在三语言日志中显示该选项当前是否开启；读取失败明确显示无法判断。实际来源需结合这台相机的状态和同场景对比确认。
