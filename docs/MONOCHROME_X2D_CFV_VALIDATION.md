# Monochrome module: X2D first, CFV second

This source contribution targets current public Shuaqi main (0.4.12 stable baseline) and the first-generation X2D 100C / 907X + CFV 100C firmware 4.2.0 family. It is not a firmware image. The objective is one switch that persists across power cycles and produces monochrome live view plus monochrome JPEG/HEIF, with the corresponding `.3FR` retaining color. The same control and private-frame architecture can later host additional Recipes; no Recipe other than monochrome is asserted here.

## What is implemented in source

- A menu switch and persistent preference, with a separate availability marker. Missing or malformed state disables the mode.
- Pixel conversion on separately owned buffers for JPEG format 103 and the 1944×1248 live-view format. The input frame is not modified. A Wayland dispatch core retains the AF/UI overlay input unchanged.
- A HEIF format 1003 neutralizer for both candidate three-sample/32-bit arrangements. It has no default arrangement and refuses to run until the packing is independently attested.
- Host-tested JPEG/HEIF routing contracts and a reversible transaction model. Neither publishes a ready state merely because files exist.
- An ARM64 observation-only module for the X2D encoder boundary, with a local source build helper. By default this module logs only which JPEG/HEIF call was reached and forwards it to the named stock provider. It does not transform pixels. Descriptor reads require an explicit metadata opt-in and separate review.
- An optional factory-USB X2D diagnostic install/restore path. It checks the stock startup file hash, the target model, the ARM64 module, exported symbols and a manifest. This path remounts `/system` to change the camera-service startup preload and is therefore a device experiment with a real failure risk, despite the module being observation-only. It is separate from the normal Shuaqi install and is not enabled for CFV.

## Test separation

1. **Offline:** run the whole Shuaqi test suite, the host memory tests, and the Android ARM64 build. This verifies source behavior and package shape only.
2. **Radium's test X2D 100C, firmware 4.2.0:** after confirming an independent factory-USB recovery route, run only the observation module first. Confirm JPEG and HEIF calls are reached, normal photo output remains unchanged, a full power cycle still boots, and USB Restore works even if the camera GUI cannot open. Report only redacted format/geometry and binary/restore outcomes; no photos, serial numbers or private logs are needed. Do not enable metadata reads until the first stage works.
3. **X2D image routes:** after the observed ABI is checked, connect the supplied private-buffer JPEG, display and HEIF cores. Verify one exposure's JPEG/HEIF is grayscale while its `.3FR` develops in color; AF overlays remain colored and usable. Test power-off/on with the switch both on and off, then Restore.
4. **FX's 907X + CFV 100C:** repeat independent model, startup-file, ABI and recovery gates. An X2D result does not authorize or prove the same operation on the CFV. No CFV diagnostic install is included in the current manifest.

The non-observation image routes still need the target's buffer-ownership, cache-sync and completion contracts. Their host tests alone do not make a device build safe. The proposed exchange with Radium is to have him **test and report** the source candidate on his X2D while we continue the integration code, not to ask him to implement the monochrome mode for us.

## 给 Radium 的简要说明

我们把黑白功能直接做进了基于当前公开 Shuaqi 主线（稳定基线 0.4.12） 的源码分支：菜单和断电后保存的开关、JPEG/取景的独立缓冲区处理、HEIF 的受验证门控处理、以及 USB 恢复事务都附有离线测试。目标是黑白取景、黑白 JPEG/HEIF，同时同次曝光的 `.3FR` RAW 保留彩色；以后这套架构可以扩展成 Recipes。

我们还写好了一个 **仅观察、不改照片** 的 X2D 100C 4.2.0 诊断模块及构建工具。它默认只记录 JPEG/HEIF 调用是否到达，并转发给原厂函数；要读取描述符，必须单独明确开启。其可选安装会改动 `/system` 启动配置，所以只有在独立 USB 恢复路径验证后，才适合在测试机上尝试。当前明确只允许 X2D；你的 X2D 结果不能直接推断 FX 的 907X + CFV 100C。

希望你帮忙**测试和反馈** X2D 上的调用是否到达、原厂拍摄是否保持正常、完全断电后是否能启动、以及 GUI 失效时 USB Restore 能否独立完成。我们继续负责功能代码和后续整合，不需要你替我们开发黑白模式。确认这些边界后再逐路验证 JPEG、取景、HEIF，最后单独验证 CFV。

## First-generation X2D 4.2.0 native-mode check (4 October 2026)

A firmware string search found `MonoOnly` in `camera-gui`, but its neighboring
`ColorMode_Mask`, `ColorOnly` and dither values are Qt `QImage` conversion flags,
not a Hasselblad photo mode. `grayscale_convert` appears with `jccolor.c` and
other generic libjpeg internals. `camera-service` references
`DCAM_STATUS_COLOR_MODE` as capture/reprocess metadata tag `0x460` in
`DCAMCaptureEnginePrivate::setRequiredReprocessTags` at `0x209878–0x209990`;
if the tag is absent it inserts the default integer zero. This observation
does not identify a switch that desaturates live view or JPEG/HEIF. The
`black_white`/`bw_enable` strings in `libdcam_pp.so` are tone-mapping parameter
dump fields, likewise not evidence of a built-in monochrome photo route.

The three proposed interposition points are reached through PLT calls in the
pinned 4.2.0 binaries: JPEG plugin `duss_hal_ienc_encfrm@plt` at `0x193c`,
HEIF plugin `duss_hal_heifenc_encfrm@plt` at `0x138c`, and Wayland LV plugin
`WaylandControlLV::handleBuf@plt` at `0x1a420`. This makes preload
interposition plausible; it does not prove the loaded Android linker namespace
or buffer contracts on an X2D body. For Wayland the `x1` argument is the video
object, `x2` is a stock display LUT capsule, and `x5` is the graphic overlay.
The overlay and LUT must remain stock. The video VMem is shared with Wayland
and cached by handle after presentation; a private video frame cannot be
freed merely when the hooked method returns.

## Native runtime source review (4 October 2026)

The separate `build_x2d_runtime_candidate.py` compiles the JPEG, HEIF and
Wayland hook sources together for Android AArch64 and checks exact official
4.2.0 library hashes and exported symbols. This is a **source-review binary**,
not a Shuaqi installation package. The generated manifest deliberately says
`deviceInstallable: false`. No camera was contacted for this review.

The route controller now distinguishes a saved monochrome request from a
fully ready pipeline. Once monochrome is selected, loss of a JPEG or HEIF
route refuses that capture instead of silently forwarding a color photo.
A verified vendor contract would mark each encoder route ready at bind, while
live view marks ready only after target-specific object attestation. No
production bootstrap supplies those contracts today; the menu remains
disabled on a camera.

The pinned 4.2.0 firmware gives these narrower facts:

- `libduml_vcodec.so` exports both named stock HAL encoder entry points; the
  JPEG success path waits for the encoder. The exact private descriptor
  storage, VMem allocation flags and input cache synchronization still lack
  a validated target contract.
- HEIF format 1003 uses two common frame planes: Y at `+0x40`, UV at
  `+0x50`, plane count at `+0x80`, and packed row bytes
  `ceil(width/3)*4`. This fixes the mock fixture's previous HEVC-structure
  offsets. The encoder's semaphore-wait error can be logged and then
  overwritten before HAL returns zero, so HAL return alone does not prove
  the private input is released. Bit packing, chroma neutral value and a
  completion callback remain unverified.
- Wayland's `0x2d2e` LUT travels with the video plane while the graphical
  overlay uses a distinct path. The official image contains LCD calibration
  arrays, but not the selected runtime LUT's identified 32-bit word layout.
  A guessed grayscale table could corrupt the preview or color calibration.
  The separate private-video-object path also needs the real C++ ownership
  and release contract; a copied descriptor prefix is insufficient.

Host tests and cross-compilation prove only local contracts and build shape.
An actual monochrome X2D test requires these missing vendor contracts, then
a separately reviewed full-runtime install/restore manifest and an
independent recovery check. The present optional factory-USB installation
path accepts the **observation probe only**. It must not be pointed at the
full runtime candidate.
