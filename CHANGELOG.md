# Changelog

English first; [中文更新日志](#中文更新日志) follows below. Versions are listed newest first. Documentation-only changes do not imply a new application package.

## Unreleased

### Documentation

- Describe the optional 907 feature as **IBIS entry (Easter egg)** without revealing its contents. Camera-side content is unchanged.
- Add this changelog and links from the README. Future releases will record changes here.

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

版本按从新到旧排列。仅修改文档不代表发布了新安装包。

## 尚未发布

### 文档

- 907 选项统一称为 **防抖入口（彩蛋）**，说明不再透露彩蛋内容；相机里的内容保持原样。
- 新增本更新日志及 README 入口，后续版本在此记录改动。

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
