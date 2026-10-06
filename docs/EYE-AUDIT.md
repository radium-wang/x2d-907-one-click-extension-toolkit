# Eye boxes reported with 0.4.8

The report describes eye boxes without tracking autofocus, similar to the stock DebugMode eye-detection option. It does not establish working eye-tracking AF. The reporting camera's debug flags have not been read, so its specific cause is still unconfirmed.

The audit checked the `v0.4.8` sources and every preserved 0.4.8 payload variant against the pinned manifest: 32 exact file/language variants. The packaged AF-C controller, speed controller, brightness controller and worker match their tagged sources. These camera text payloads contain no eye-detection/debug option writer. The native menu, AF-C controller, speed worker and loopback service are unchanged between 0.4.7 and 0.4.8; 0.4.8 changed feature descriptions, not the AF-C runtime.

The 0.4.8 preload changes the main-menu cache, stock control-screen cache pointer, focus popup cache and the `CameraUI.canChangeAfc` gate. Its stock control-screen content remains unchanged. It does not replace liveview face/eye overlays, install a donor detection engine, or write `system.debug_mode` / `system.debug_options`. The AF-C worker does select the existing `camera.focus_mode` when the user enables AF-C; effects of that stock mode on detection need a camera comparison and cannot be ruled out by the absence of debug writes alone.

The pinned original 4.2.0 GUI already contains left/right eye landmark fields, eye ROI types and eye-symbol rendering. Its face-detection availability comes from the camera's stock capability fields, separately from `canChangeAfc`. The original camera service also handles the EyeDetection bit (1) and FaceDetection bit (2) in its debug-options path. Those flags are diagnostic settings, not proof of tracking autofocus. Audit baselines:

- camera-gui SHA-256: `16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0`
- camera-service SHA-256: `fbcf828f73bca13f0c8b95e7dd0b95ac483ae36954ec06179098c8a1a65f9f82`
- Preserved 0.4.8 manifest SHA-256: `70048064578e9cda6aed02934157769991ff8e1b2a353bfd54ca6310c9ee4a70`

In 0.4.14, **Connected** reads the current stock `system.debug_mode` and `system.debug_options` through the factory transport, without enabling ADB or setting either property for this diagnostic. Both desktop apps report enabled, disabled or unreadable. DebugMode must be on and bit 1 set for the reported eye-debug flag to be active. An unreadable response remains unknown; it does not count as disabled. The toolkit neither enables nor clears these settings during installation/restoration. A prior active setting can therefore remain active.

If the reporting camera has the active EyeDetection bit, that confirms the stock diagnostic option is active and makes earlier debug configuration a supported explanation. It still does not prove when it was enabled. If the bit is off, do not attribute the boxes to that option: compare stock AF-S and AF-C under the same scene, lens and face-detection setting, recording ROI state and focus behavior. That device comparison is pending; no camera settings, reboot or capture were performed in this audit.

# 0.4.8 人眼框反馈核查

反馈是“有人眼框但无法跟随对焦”，与原厂 DebugMode 人眼选项的表现相似。已核对 0.4.8 标签源码及 32 个原样保存的载荷/语言文件：没有开启人眼调试的写入，也没有新增人眼检测或跟随对焦运行库。0.4.8 的 AF-C 原生菜单、控制器、服务和速度代码与 0.4.7 相同。

原厂 4.2.0 已有眼部位置、眼部 ROI、眼部框绘制和人眼调试选项。工具不会清除用户原有调试设置，所以旧设置可能保留；但 AF-C 会使用原厂对焦模式，仍需排除它对检测状态的间接影响。尚未读取反馈相机的 DebugMode/EyeDetection，不能仅凭眼框判定残留，更不能宣称已实现人眼跟随对焦。

0.4.14 的“已连接”会只读检查并在三语言日志中显示该选项当前是否开启；读取失败明确显示无法判断。实际来源需结合这台相机的状态和同场景对比确认。
