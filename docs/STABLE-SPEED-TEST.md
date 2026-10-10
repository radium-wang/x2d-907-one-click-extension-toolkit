# Public stable release — 0.4.17 validation

Start from original v0.4.12 (e3b283c995822b3bbb8736b67906f69c2ed14ade), with the public repository's documentation changes. Add only the approved three-level speed controls: Low 1.5/1.5/1.5; Medium (default) 2.5/2/1.5; High 3/3/2 for Type 0/1/2. Keep the native vertical picker, orange highlight and gray disabled row while boost is OFF. Saved choice survives disabling and reboot; Restore removes its saved/staging files after withdrawing runtime.

AF-C, Focus Speed Boost and Auto Brightness remain the three independent stable desktop choices. The original native GUI preload, focus-mode popup, stock dynamic corrections, brightness runtime and firmware/transaction gates are retained. Eye and AFT are private-beta features and are absent here. The original 0.4.12 recovery catalog is byte-pinned for safe upgrades.

Update behavior: the public updater uses numeric version comparison. Published 0.4.12 detects the 0.4.17 stable release; 0.5.0 ignores 0.4.17. Beta source, packages and private update address are unchanged.

Local checks use actual stock Qt 6.4.1 widgets/shaders, with native hardware/constants and loopback backend proxied. AArch64 instruction checks use substituted hardware getters. These checks do not establish Windows physical execution, camera touch/GPU or optical autofocus performance. Do not install, restore or reboot a camera as part of building/checking packages.

The Windows and Mac release ZIPs are generated in ignored output directories. Extract the complete ZIP before use. If the camera has a 0.5.0 beta installed, first restore it using its matching beta app, then use this stable release. The stable app cannot overwrite unknown/private-beta camera modifications.

0.4.17 公开稳定包仅在原始 0.4.12 上增加低／中／高三档速度；保持原有三项功能，不包含内测眼部识别／AFT。0.4.17 低于 0.5.0，内测用户不会收到此更新。相机若装有 0.5.0，请先用对应内测 App 恢复原状，再试装稳定包。

Validation: 215 full offline tests without skips, 4,206 exact machine-code cases, 14 executed Restore scenarios (all seven masks for original and new stable bundles), native stock-widget checks in three languages, eight real Mac desktop selections, and 15 final copy/update regressions. Hardware/backend inputs are substituted; Windows/CFV device and optical validation remain pending.

Release: [v0.4.17](https://github.com/radium-wang/x2d-907-one-click-extension-toolkit/releases/tag/v0.4.17). The published applications and payloads are byte-identical to the locally tested `stable-speed-test-1` build; its internal build label is retained for traceability. Only the ZIP instructions are updated for publication. Original local archive hashes remain in `test-builds/0.4.17-stable-speed-test-1.json`; public archive hashes and unchanged-member checks are in `releases/0.4.17.json`.

A clean public source export runs all 215 discovered tests: 174 pass and 41 explicitly skip private firmware/generated-payload inputs. Full local inputs run all 215 without skips. Both release archives pass the actual updater extraction/identity checks; the extracted Mac app passes strict signature verification.
