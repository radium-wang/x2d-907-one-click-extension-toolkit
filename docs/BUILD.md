# Build and test

Commands below run from the repository root. Python 3.9+ and `requirements-dev.txt` are needed for development; desktop distributions embed Python 3.13.15. No command below connects to a camera unless the explicit runtime actions at the end are used.

## Source map

- `src/MacApp.swift`: Cocoa interface, Settings, language selection and operation gates.
- `src/windows_app.py`: native Win32 interface, Settings and equivalent gates.
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

The native menu builder needs `X2D_BUILD_SUPPORT` (a local tool directory containing `inspect_menu_resources.py` and its documented `firmware_image` dependencies), `X2D_SYSTEM_ROOT`, and `X2D_QML_UNIT_DIR`. The latter must contain `main-screen-bootstrap-device.bin`, `control-stock.bin`, `control-afc.bin`, `popover-stock.bin`, and `popover-afc.bin` generated against the pinned GUI. AArch64 clang + lld or Zig is needed. `src/brightness/build.py` builds only the independent display runtime, using the pinned stock camera-system, camera-gui, libc, libdl and libm from `X2D_SYSTEM_ROOT`. It regenerates display trampolines locally; none are committed. `build_speed_bundle.py` invokes it and additionally needs the independently verified `speed-original` and `speed-candidate` instruction ranges and older restoration inputs. These are missing external build inputs, not downloadable attachments here.

```sh
python3 -B src/build_native_preload.py
python3 -B src/build_speed_bundle.py
```

Stock GUI SHA-256: `16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0`.

## Desktop packaging

Run builder `--help` for arguments. Package construction is offline and requires the complete verified camera payload directory through `X2D_PAYLOAD_DIR` or `src/native-package`.

Mac inputs: Xcode command-line tools; official Python 3.13.15 universal framework payload; macOS 13-compatible universal libusb 1.0.30; PyUSB 1.3.1; official Android platform-tools ADB; associated license texts. The builder audits each bundled Mach-O and signs the result ad hoc. It does not notarize.

Windows inputs: official Python 3.13.15 x64 embed ZIP, libusb 1.0.30 binary input, Android platform-tools, LLVM/lld, and the pinned libwdi preparation inputs. `build_windows_driver.py` documents and checks the libwdi 1.5.1 source and llvm-mingw 20260922 hashes, builds its restricted helper and includes modified libwdi source + license texts in the package. It does not install a driver on the build computer. The launcher requests administrator elevation; the helper only accepts the camera's supported composite factory interface, never a storage or parent device. ADB driver setup is separate.

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
