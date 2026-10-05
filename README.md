# X2D/907 One-Click Extension Toolkit

**X2D/907 One-Click Extension Toolkit (x2d/907一键扩展功能-工具包)** is an experimental macOS and Windows utility for the first-generation **X2D 100C** and **907X & CFV 100C**, targeting stock firmware **4.2.0**.

Camera menu text follows the app language at install time: English installs **Tweaks**; Simplified and Traditional Chinese install **耍起功能** with their respective feature labels and messages.

[中文说明](#中文说明) · [Changelog / 更新日志](CHANGELOG.md) · [Build and test](docs/BUILD.md) · [Validation](docs/VALIDATION.md)

## Features

- **AF-C continuous autofocus:** adds a camera-side availability switch. The stock AF-S / MF layout returns when disabled.
- **Focus speed buff:** faster focus scans, with stock speed restored when disabled.
- **Auto Brightness (0.4.3):** enable “Add Auto Brightness to Menu” in Tweaks, then control Auto in Display → Brightness. The rear slider sets the maximum; the knob stays there while its white fill tracks current output. The master switch controls availability; default off.
- **Install / Restore original:** checks the camera and package, saves the original startup configuration, then restarts and verifies the result.
- **Settings and updates:** in Settings, startup checks default to on and can be disabled; the choice is remembered. Manual checking remains available when automatic checks are off. A separate Download and Install Update action fetches the latest stable GitHub Release for your platform, verifies its SHA-256 digest, then installs and relaunches the app. Camera operations and app updates cannot run together. The previous app is retained beside the installation. Updates change the desktop app; updating an installed camera extension still requires **Connected → Install**.
- **Simplified Chinese / Traditional Chinese / English (0.4.7):** switch the desktop interface and logs in Settings; the preference survives app restarts. **Install** writes matching camera menu text. Changing the camera language requires another install.
- **Windows connection and exit fixes (0.4.6):** correct the private ADB listener address that prevented installation in 0.4.5. Closing during a read-only update check cancels the check. Camera install/restore uses an owned private ADB process that is cleaned up afterward; camera/driver work and update installation retain exit protection.
- **Windows interface (0.4.4):** Mac-aligned feature cards, rounded buttons and Settings, with bilingual typography, per-monitor DPI scaling and scrolling on short displays. The camera payload is unchanged from 0.4.3, so existing 0.4.3 camera installations do not need reinstallation.
- **907 IBIS entry (Easter egg):** available after a verified 907 connection; its menu label follows the installed language.

**Do not remove the lens while the focus buff is enabled. Disable it before changing lenses.**

## Getting started

1. Extract the complete application package. macOS requires 13 or later (Apple silicon / Intel); Windows requires 64-bit Windows 10 / 11.
2. Turn on the camera and connect a USB data cable. Tap **Skip** if shown on the camera. A camera-side **Mass storage** selection can also retain the factory connection.
3. Click **Connected**. Install and Restore remain disabled until connection and firmware checks pass. Windows requests administrator access and attempts to prepare the supported camera factory interface automatically; the ADB interface is separate.
4. Optionally select the 907 IBIS entry (Easter egg), then click **Install**. Keep the camera powered and connected through restart and verification.
5. Disconnect only when the app reports completion. Open **Tweaks** (English install) or **耍起功能** (Chinese install) at the end of the camera menu, enable its master switch, then choose AF-C or the focus buff. Select Traditional Chinese in Settings before installing to get Traditional Chinese camera text.
6. To remove the extension, reconnect, click **Connected**, then **Restore original**. This reverses this application's changes; it is not a complete firmware recovery tool.

X2D uses tile **12**. The 907 uses tile **11** normally, or **12** with the optional Easter egg installed. Changing the Easter egg choice or the camera menu language requires another installation; recognized older packages are restored before upgrade.

When an existing extension must be restored before reinstallation, the app asks for confirmation in the **target camera menu language**. The dialog explains restoration, disabled feature switches and restarts. Cancel leaves the camera unchanged. A first installation or an unchanged installation does not need this dialog.

The repository contains application source, tests and screenshots. Vendor firmware, extracted compiled QML, runtime libraries, generated camera payloads and desktop installation archives are excluded. Desktop packages are available from [GitHub Releases](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/latest). Updates require a writable application folder; if needed, move the complete app to a folder you own. The Mac build uses an ad-hoc signature and is not notarized; the Windows launcher is unsigned.

## Screenshot — English

Native macOS 0.4.3 window rendered in an offline UI check with a disconnected state. The 907 checkbox is intentionally disabled until identification succeeds.

<img src="docs/images/app-en.jpg" alt="X2D/907 One-Click Extension Toolkit 0.4.3 English macOS interface" width="580">

<img src="docs/images/settings-en.jpg" alt="English Settings window" width="450">

## Verification status

Earlier X2D installations, menu behavior and restoration have device/user evidence. Version 0.4.7 passed 171 offline tests with local payloads. Traditional Chinese desktop text, confirmation and camera overlays have offline checks; native Windows display and physical camera installation in Traditional Chinese remain unverified. The 0.4.3 camera functionality has Qt menu/brightness checks and native Mac layout evidence. Native Windows ADB startup, shutdown/directory release, rendering and accessibility, auto brightness on the physical display, X2D/CFV boot and restoration, the 907 menu/Easter egg, AF-S retention across power cycles and automatic Windows driver preparation still require native/device validation. A desktop test is not a camera test. See [the evidence boundaries](docs/VALIDATION.md).

This is an independent project, not an official Hasselblad product. Eye recognition is not included. Other camera generations and firmware versions are unsupported.

## License

New versions carrying the [X2D/907 Noncommercial Distribution License 1.0](LICENSE) allow use, study, modification and free redistribution. **Professional photography, including paid shoots and selling photographs, is allowed. Selling the software or modified versions, charging for software access, and paid installation/setup services require separate written permission.** Truly voluntary donations are allowed; access, features or installation must not depend on payment.

This is a **source-available** project with restrictions on software commercialization; the license is not OSI-approved open source. Previously released MIT versions keep their original permissions. Third-party components keep their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Existing published 0.4.2 archives are unchanged by this repository license update.

## Support development

If this toolkit helps you, you can support its development via [PayPal](https://paypal.me/RadiumWang) or Alipay. Donations are voluntary. Thank you for supporting ongoing development and maintenance!

**Alipay:** scan the QR code below with Alipay, or save the image and open it in Alipay's scanner.

<img src="docs/images/alipay-donation.png" alt="Alipay donation QR code" width="280">

---

## 中文说明

**x2d/907一键扩展功能-工具包** 是面向第一代 **X2D 100C** 和 **907X & CFV 100C** 的实验性 Mac / Windows 工具，仅适配经过校验的原厂 **4.2.0** 固件。

相机菜单文案随安装时的 App 语言：简体、繁体中文安装为“耍起功能”（功能名称与提示使用所选字形），英文安装为 Tweaks。

### 当前功能

- **AF-C 连续自动对焦**：在相机上控制连续对焦入口；关闭后恢复原厂 AF-S / 手动对焦布局。
- **对焦加速 buff**：加快对焦扫描，关闭后恢复原厂速度。
- **后屏自动亮度（0.4.3）**：在耍起功能中开启“在亮度菜单中加入自动亮度”，之后在显示 → 亮度中控制自动模式。滑块圆球设置最高亮度，白线跟随当前输出；受总开关控制、默认关闭。
- **一键安装 / 一键恢复原状**：检查连接与文件，保存原厂启动配置，并在重启后校验结果。
- **设置与更新**：在设置页选择语言、关闭或开启启动自动检查更新（默认开启并保存选择）；关闭后仍能手动检查。下载安装需另行点击，从 GitHub Release 获取对应系统的稳定版，校验 SHA-256 后安装并重新打开；保留上一版 App，更新与相机操作互斥。更新只替换电脑端软件；相机上的扩展需再点击 **已连接 → 一键安装** 更新。
- **简体中文／繁體中文／English（0.4.7）**：在设置中选择语言，桌面界面、操作提示和日志随语言切换，重启 App 后保留选择；**一键安装** 会写入对应语言的相机菜单文案，更换相机语言需重新安装。
- **Windows 连接与退出修复（0.4.6）**：修正 0.4.5 导致安装无法开始的独立 ADB 监听地址；普通检查更新期间可关闭窗口并取消检查。相机安装/恢复使用本软件管理的独立 ADB 进程，操作结束后回收；相机/驱动操作及更新安装期间仍保留退出保护。
- **Windows 界面（0.4.4）**：功能卡片、圆角按钮和设置页对齐 Mac，适配中英文字体、显示器 DPI 缩放及小屏幕滚动。相机载荷与 0.4.3 相同，已有 0.4.3 相机安装无需重装。
- **907 防抖入口（彩蛋）**：识别到 907 后可选择添加；入口名称随安装语言变化。

**开启对焦 buff 后切勿取下镜头。更换镜头前，请先关闭对焦加速 buff。**

### 使用方法

1. 完整解压软件。Mac 支持 macOS 13 及以上、Apple 芯片与 Intel；Windows 支持 64 位 Windows 10 / 11。
2. 开机并插入 USB 数据线；相机出现“跳过”时点击“跳过”。在相机屏幕选择“大容量存储”也可能保留工厂通信连接。
3. 点击 **已连接**。检查通过后才启用安装和恢复按钮。Windows 会请求管理员权限，并尝试自动准备支持的相机工厂接口驱动；ADB 是另一个独立接口。
4. 907 用户可选勾防抖入口（彩蛋），然后点击 **一键安装**。重启及校验期间保持供电和连接。
5. App 提示完成后才拔线。在相机主菜单末尾进入 **耍起功能**，先开启主开关，再选择 AF-C 或对焦加速 buff。若希望相机使用繁体中文，请在安装前到设置页选“繁體中文”。
6. 需要撤回时重新连接，点击 **已连接 → 一键恢复原状**。恢复仅撤回本软件的改动，不是整机固件救援。

X2D 的功能入口在第 **12** 格；907 默认第 **11** 格，勾选彩蛋后移到第 **12** 格。改变彩蛋选项或相机菜单语言后需重新安装；已识别旧版会先恢复再升级。

需要先恢复再安装时，App 会按 **目标相机菜单语言** 弹出确认，说明恢复、功能开关关闭和重启流程。取消后不修改相机。首次安装或现有安装配置未变化时不弹此确认。

### 软件截图 — 中文

这是通过离线界面检查渲染的 macOS 0.4.3 原生窗口，展示未连接状态，因此 907 勾选项和写入按钮处于禁用状态。

<img src="docs/images/app-zh.jpg" alt="x2d/907一键扩展功能-工具包 0.4.3 中文 macOS 界面" width="580">

<img src="docs/images/settings-zh.jpg" alt="中文设置页" width="450">

### 验证与源码范围

早期 X2D 安装、菜单和恢复已有实机或用户反馈；0.4.7 通过 171 项带本地载荷的离线测试。繁体桌面文案、确认弹窗和相机菜单文件已离线校验；Windows 原生繁体显示与相机实装仍待验证。0.4.3 相机功能另有 Qt 菜单/亮度检查和 Mac 原生布局证据。**Windows 原生 ADB 启动、退出与目录释放、显示与可访问性、实际后屏自动亮度、X2D/CFV 启动与恢复、907 菜单/彩蛋、关机后保留 AF-S，以及 Windows 自动驱动准备仍待原生或实机验证。** 具体范围见 [验证说明](docs/VALIDATION.md)。

本库只收录应用源码、测试和软件截图，不包含原厂固件、提取的编译 QML、运行库、生成的相机载荷或桌面安装压缩包。桌面安装包见 [GitHub Releases](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/latest)。更新需要应用目录可写；如提示权限不足，请将完整 App 移到自己的可写目录后重试。Mac 使用临时签名、未经公证；Windows 启动器未经代码签名。构建输入见 [构建说明](docs/BUILD.md)。

本项目为独立研究工具，非哈苏官方软件。目前不含眼部识别；不适配其他代机型或固件。

### 许可

后续携带 [X2D/907 非商业分发许可证 1.0](LICENSE) 的版本允许使用、研究、修改和免费分享。**允许用于收费拍摄、摄影工作室及出售摄影作品；出售软件或改版、收费提供软件访问，以及收费安装、设置服务须另获作者书面授权。** 允许自愿赞助，但不得把付款作为获取软件、使用功能或获得安装服务的条件。

这是限制软件商业化的**源码公开（source-available）**项目，许可证不属于 OSI 认可的开源许可证。此前已按 MIT 发布的版本仍保留原许可；第三方组件沿用各自许可，见 [第三方说明](THIRD_PARTY_NOTICES.md)。本次仓库许可更新不修改已发布的 0.4.2 安装包。

### 支持开发

如果这个工具对你有帮助，欢迎通过 [PayPal](https://paypal.me/RadiumWang) 或支付宝自愿赞助，支持后续开发与维护。感谢支持！

**支付宝：**打开支付宝扫一扫，扫描下方收款码；也可以保存图片，在扫一扫中从相册选择。

<img src="docs/images/alipay-donation.png" alt="支付宝自愿赞助收款码" width="280">
