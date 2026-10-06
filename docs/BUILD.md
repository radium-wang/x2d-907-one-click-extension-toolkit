# Build and test

Commands below run from the repository root. Python 3.9+ and `requirements-dev.txt` are needed for development; desktop distributions embed Python 3.13.15. No command below connects to a camera unless the explicit runtime actions at the end are used.

## Source map

- `src/MacApp.swift`: Cocoa interface, Settings, language selection and operation gates.
- `src/windows_app.py`: native Win32 interface, Settings and equivalent gates.
- `src/windows_ui.py`: Mac-aligned Windows layout and GDI skin; native controls retain input and accessibility. No added UI runtime dependency.
- `src/windows_processes.py`: cancellable read-only update checks and owned private Windows ADB server lifetime, including crash cleanup through a Windows job object.
- `src/app_settings.py`: persisted Windows startup update-check preference; Mac uses UserDefaults.
- `src/x2d_play_software.py`: validated installation, reboot verification and restoration.
- `src/transport/collect_x2d_af_usb.py`: factory USB protocol implementation.
- `src/windows_factory_usb.py`: native Windows factory interface transport.
- `src/windows_connection.py`, `windows_driver_*`: constrained factory WinUSB preparation.
- `src/*.qml`: stock-style extension, optional Easter egg and camera-side controllers.
- `src/native_menu_preload.c`, `speed-buff-server.c`, shell sources: guarded runtime components.
- `tests/`: offline regressions, API substitutes and transaction failure cases.

## Offline Python checks

```sh
python3 -m pip install -r requirements-dev.txt
PYTHONPATH=src python3 -B -m unittest discover -s tests
```

Payload-dependent tests skip when private generated inputs are absent. To execute the complete suite, provide the complete locally generated, exact-version package directory:

```sh
PYTHONPATH=src X2D_PAYLOAD_DIR=/absolute/path/to/native-package \
  python3 -B -m unittest discover -s tests
```

Do not point this at an arbitrary firmware bundle. The application requires its fixed manifest and per-file SHA-256 checks, including known older restoration manifests and payload bytes.

## Camera payload inputs

This repository deliberately does not redistribute camera firmware or vendor-derived compiled QML. Camera payload construction requires locally extracted stock 4.2.0 material and reviewed offline tools from the research project. [The research repository](https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions) explains the firmware-analysis boundaries; its public tree does not supply a ready-to-install payload.

The native menu builder needs `X2D_BUILD_SUPPORT` (a local tool directory containing `inspect_menu_resources.py` and its documented `firmware_image` dependencies), `X2D_SYSTEM_ROOT`, `X2D_QML_UNIT_DIR` and `X2D_FOCUS_UI_DIR`. The original unit directory must contain `main-screen-bootstrap-device.bin`, `control-stock.bin` and `popover-stock.bin` generated against the pinned GUI. AArch64 clang + lld or Zig is needed. `src/brightness/build.py` builds only the independent display runtime, using the pinned stock camera-system, camera-gui, libc, libdl and libm from `X2D_SYSTEM_ROOT`. It regenerates display trampolines locally; none are committed. `build_speed_bundle.py` invokes it and additionally needs the independently verified `speed-original` and `speed-candidate` instruction ranges and older restoration inputs. These are missing external build inputs, not downloadable attachments here.

For the focus UI, `src/prepare_focus_ui.py --verified-port /absolute/path/to/reviewed-port --stock-gui /absolute/path/to/stock-camera-gui --output /absolute/path/to/private-focus-inputs` verifies the accepted port and stock GUI hashes and prepares 18 private resource aliases and the reviewed popup source. Compile the prepared popup with the reviewed research project's `check_x2d2_focus_port_host.py --resources /absolute/path/to/private-focus-inputs` in its Qt 6.4.1 environment. Set `X2D_FOCUS_UI_DIR` to the resulting directory containing `focus-popup.qt64.bin`, `liveview-stock.bin`, `focus.tree`, `focus.names`, `focus.data` and `ported-source/app/qml/popups/PopoverFocusMode.qml`. The builder verifies the source and compiled reference hashes; it packages the popup as a private QML file rather than replacing the stock popup cache. These vendor-derived inputs remain private and ignored.

Run `tests/check_focus_ui_qml.py --inputs /absolute/path/to/private-focus-inputs --stock-sources /absolute/path/to/private-stock-sources --payload /absolute/path/to/native-package --output /absolute/path/to/new-evidence-directory` in Qt 6.4.1. Extract the seven pinned stock QML sources named in that test from the verified GUI into the private stock source directory. The test uses the original popup and indicator sources, a substituted image provider and hardware proxies, and the actual master/AF-C synchronization function. It checks three languages, stock OFF behavior, enabled modes and disabled icons, repeat switching, original binding restoration and popup selection/close signals. It does not establish physical camera behavior.

```sh
python3 -B src/build_native_preload.py
python3 -B src/build_speed_bundle.py
```

Stock GUI SHA-256: `16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0`.

The public installer checks an exact extension target allowlist, including every language overlay and the private focus popup. Vendor/raw partitions and replacement GUI executables are excluded. The native module registers its private icon bank using the stock Qt resource API and changes only the process-local main-menu cache pointer and AF-C capability field, reversing both writes on failure. All original focus cache pointers and AOT callbacks remain intact. QML loads the private focus popup and applies reversible visual bindings only while both camera switches are enabled. The module retains the disable marker and once-per-boot retry guard.

## Desktop packaging

Run builder `--help` for arguments. Package construction is offline and requires the complete verified camera payload directory through `X2D_PAYLOAD_DIR` or `src/native-package`.

Mac inputs: Xcode command-line tools; official Python 3.13.15 universal framework payload; macOS 13-compatible universal libusb 1.0.30; PyUSB 1.3.1; official Android platform-tools ADB; associated license texts. The builder audits each bundled Mach-O and signs the result ad hoc. It does not notarize.

Windows inputs: official Python 3.13.15 x64 embed ZIP, libusb 1.0.30 binary input, Android platform-tools, LLVM/lld, and the pinned libwdi preparation inputs. `build_windows_driver.py` documents and checks the libwdi 1.5.1 source and llvm-mingw 20260922 hashes, builds its restricted helper and includes modified libwdi source + license texts in the package. It does not install a driver on the build computer. The launcher requests administrator elevation; the helper only accepts the camera's supported composite factory interface, never a storage or parent device. ADB driver setup is separate.

Mac test builds can also pass `--output` to keep generated test apps separate from published packages. Windows UI test builds can pass `--output src/outputs/windows-ui-test` to keep them separate from published packages. With the optional desktop PySide6 test environment, `tests/preview_windows_ui.py --output src/outputs/windows-ui-preview` renders Chinese/English previews using the same layout, colors and vector geometry as native GDI. Those images verify layout only; they are not screenshots from a Windows execution.

## Device actions

`src/x2d_play_software.py status` accesses the camera through factory USB for read-only checking. `install`, `restore`, feature switches and the desktop Install / Restore buttons change camera state; installation/restoration can upload files, update startup configuration and reboot. These are not offline test commands. Installation with `--prank-ibis` is rejected unless the stock model identifiers match the CFV 100C.

Desktop installations use `--interactive-confirmation` and a private stdin pipe: if a known existing extension needs restoration before reinstalling, the backend waits for the target-language dialog's explicit approval before calling restore. Cancellation and EOF leave the camera unchanged. CLI users must explicitly add `--confirm-reinstall` to authorize that restoration; a first installation does not require it.

# 构建与测试

先执行上面的无设备测试命令。未提供本地相机载荷时，依赖载荷的用例会跳过；提供经过固定版本校验的 `X2D_PAYLOAD_DIR` 后可执行完整用例。源码不包含原厂固件、提取的编译 QML 或完整构建输入，因此单凭本库无法生成相机载荷。桌面打包所需运行库和许可文本也需单独准备。

构建器不连接相机。运行安装、恢复和功能切换入口会修改相机文件或状态；不要把这些当成测试命令执行。

## Optional QML model check

`python3 -B tests/check_menu_qml.py` executes the source model and route with Qt service substitutes, without camera access. It needs PySide 6.4.1 and its `rcc` executable. On the tested macOS 27 host, Qt 6.4.1 ARM builds abort during CPU-feature initialization; use a separate Intel Python 3.11 / Intel PySide 6.4.1 environment under Rosetta for this exact-version test. This dependency is optional and is not part of the native Mac application.

## Desktop Settings

Startup update checks default to enabled and never download or install without the separate user action. Mac persists `AutoCheckUpdates` with UserDefaults; Windows persists the boolean `autoCheckUpdates` in its application settings JSON, independently of language preferences. Invalid Windows preference contents use the default. Turning automatic checks off does not disable manual checking. Settings do not perform camera operations.

## Independent auto brightness (0.4.3)

`AutoBrightnessController.qml` controls menu availability from Tweaks and Auto from Display → Brightness, using camera loopback port 18765. `brightness/menu_patch.py` derives three QML files from the exact stock resource image at build time; vendor sources stay outside the repository. The Bootstrap routes only Display settings through the derived SettingsGeneric; all other delegates and stock models remain intact. No donor focus runtime is included.

The display runtime loads into camera-system, samples CM32181 at 5 Hz and updates the rear display on its Qt owner thread at 50 Hz. Hardware display/idle checks and the Tweaks master marker gate output. The stock saved brightness is the automatic ceiling and manual fallback. Slider writes update this ceiling without disabling Auto or briefly applying the ceiling while Auto is active. The knob remains bound to the stock setting, while the fill follows reported actual output at 5 Hz with UI interpolation, capped at the knob. Output transitions brighten at up to 80 percentage points per second and dim at up to 24, avoiding the previous exponential tail. The stock API retains 1% quantization; physical smoothness is not yet verified.

The installation ledger retains both stock startup configurations. Both writes roll back on failure. Restore stops camera-system and waits for its exit before removing the display library. The published 0.4.2 and two earlier local auto-brightness manifests and exact old payload bytes are retained for interrupted old installations; desktop builders include all three manifests and the previous-payloads catalog.

`tests/check_brightness_qml.py` checks the Tweaks switch and its controller with a local service substitute. `tests/check_display_brightness_qml.py --stock-qml /absolute/path/to/extracted/qml --payload /absolute/path/to/generated/package` checks the packaged Display delegate and original stock widgets, including real drags and separate knob/fill updates. Both use desktop Qt 6.4.1 and loopback-only HTTP fixtures; no camera is accessed.

## Focus acceleration guidance

`tests/check_focus_guidance_qml.py --payload /absolute/path/to/generated/package` checks the packaged Simplified/Traditional Chinese and English switch descriptions with Qt 6.4.1 and stock-style fixtures. It checks stock typography/opacity, wrapping at 1024/768/620 widths, real switch clicks and master-off gating. It also checks the free-project notice's exact translated message/button, fitting layout, blocked background input, repeated menu entry and real button dismissal. `tests/check_menu_qml.py` checks Escape/Back dismissal of the notice before leaving the menu and the resident page across 100 entries. These are desktop fixtures, not camera screenshots. Preserve the 0.4.7 through 0.4.12 manifests and old per-file bytes for recognized upgrades/restoration; both builders include the catalog.

## Focus popup and liveview icons

The Qt command and pinned stock-source inputs are described under Camera payload inputs above. It loads the original stock popup while disabled and the packaged private popup while enabled, using the stock Loader lifecycle. `tests/test_native_focus_ui.py` exercises the real native transaction with substituted memory/Qt APIs, including both partial-write rollback positions and preservation of every stock focus cache/AOT field. `tests/test_public_payload_scope.py` checks that policy, raw partition and GUI write targets are rejected without camera access.

Both desktop builders must include the pinned 0.4.8, 0.4.9 and 0.4.11 manifests and their exact language bytes in `previous-payloads`. The 0.4.11 selection records are recognized for all seven feature masks and all three languages. Direct GUI installation and policy experiments are not public App build inputs or device validation of this preload route.
