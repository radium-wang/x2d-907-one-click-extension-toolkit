# CFV 100C 4.2.0 monochrome integration handoff

This is an **unreleased source contribution for engineering review**, rebased
on the current public Shuaqi main branch (0.4.12 stable baseline). It
continues the closed PR #3. See [the X2D-first validation plan](MONOCHROME_X2D_CFV_VALIDATION.md).
The proposed X2D observation module and USB transaction are supplied in source;
Radium is asked to test and report, not to implement the monochrome algorithm. Its target behavior is black-and-white live view and
JPEG/HEIF from the selected exposure while the simultaneous `.3FR` RAW keeps
its color data. The menu choice should survive a full power cycle. Restore
must be possible through the desktop factory-USB path if the experimental GUI
cannot start. No proprietary firmware, extracted QML, camera log or personal
photo is included in this contribution.

## Implemented and checked offline

| Surface | Source | Contract exercised by host tests |
| --- | --- | --- |
| JPEG format 103 | `src/mono/cfv_mono.c`, `cfv_mono_vmem.c`, `cfv_mono_jpeg*.c` | Separate VMem frame; original frame unchanged; fail closed on bad format/size/alias; hold private frame through success; quarantine ambiguous failure. |
| Live view | `src/mono/cfv_mono_preview.c` | Separate 1944×1248 YUV8 SP420 frame, neutral chroma, cache/presenter callbacks, distinct ownership; stock frame untouched. |
| HEIF format 1003 | `src/mono/cfv_mono_heif_bridge.c`, `cfv_mono_heif_format.c` | 16-byte HAL parameter block and private ownership contract; both candidate packed-10-bit neutralizers are implemented, with no default packing and no write before independent attestation. |
| Menu and state | `src/MonoController.qml`, `src/PlayPage.qml`, `src/mono/cfv_mono_control*.c`, `cfv_mono_pref.c` | Source-level Shuaqi page integration; fixed loopback protocol; requires all three image routes; persistent choice; disable after route failure. |
| Install/Restore transaction | `src/mono/mono_transaction.py`, `mono_usb_adapter.py` | Exact stock `camera-service.rc` SHA gate, own backup/journal, dormant X2D probe preload, factory-USB restore independent of the camera GUI; simulated interruption tests. No full monochrome runtime install is enabled. |

The repository test suite passes locally with `PYTHONPATH=src python3 -B -m
unittest discover -s tests -p 'test_*.py'` (240 run, 30 skipped on macOS).
Tests which need excluded
proprietary build inputs skip as the upstream suite does. These are **host
tests**; they do not attest a photographed result or safe target-side loading.

## Integration gates for the device maintainer

1. Build an ARM64 `camera-service` module against exact CFV 4.2.0 vendor
   dependencies. Resolve the real hook points and verify that the process PID
   and loaded module hash match the reviewed manifest. No readiness bit may be
   set merely because a library was uploaded.
2. For JPEG, verify complete frame-descriptor size, allocation flags, source
   and destination cache-sync directions, and that successful
   `duss_hal_ienc_encfrm` return means the encoder has stopped reading the
   private frame. Confirm the plugin/HAL ABI against the target binary. Only
   then connect the supplied bridge and set `CFV_MONO_READY_JPEG`.
3. For live view, identify the `duss_object` construction/reference/release
   rules and the Wayland display ownership path. `FrameData` retains the
   original object; a copied pixel descriptor alone is not a safe substitute.
   A valid independently owned object and verified release callback are needed
   before setting `CFV_MONO_READY_PREVIEW`.
4. For HEIF, attest which of the two implemented format-1003 packings is
   used, plus real plane pointers/strides and memory ownership. Supply the
   private VMem and encoder-completion callbacks. Only then set
   `CFV_MONO_READY_HEIF`.
5. Review and test the supplied target-side persistence and factory-USB
   X2D probe install/restore adapter. It modifies `/system` startup despite
   being observation-only; its recovery must be tested on X2D before use.
   Extend it to the image runtime only after the image ABI is attested. Start the module as
   **unavailable/off**, run an independent verifier, then publish
   `/blackbox/x2d-play-mono.available`. Test an interrupted install and a
   broken GUI before claiming recovery. Revalidate every firmware update;
   automatic stacking has not been established.
6. On the camera, capture RAW+JPEG and RAW+HEIF pairs with the mode on and off.
   Verify decoded luma/chroma, `.3FR` color, live preview, AF overlays, full
   power-off/power-on persistence, then Restore and stock behavior. Do not
   perform the first integration on a production camera without a verified
   independent recovery route.

The current source **does not** install or activate a monochrome feature on a
CFV. `PlayPage.qml` contains a switch, but the control remains unavailable
until the three target routes and installation verifier report success. This
is intentional: an enabled-looking menu with color photo output would be a
false result.

## 给 Radium 的简要说明

这是基于当前公开 Shuaqi 主线（稳定基线 0.4.12） 的源码级黑白功能提案，不是可直接安装的相机版本。目标是同一张照片的实时取景、JPEG/HEIF 为黑白，而 `.3FR` RAW 保持彩色；开关在完全关机后仍保持选择，并可通过独立 USB 恢复流程撤回。我们已实现并在电脑上测试私有帧转换、JPEG/HEIF 桥接边界、取景帧处理、菜单控制及可逆事务；没有提交原厂固件或提取的相机文件。

请协助验证三个厂商接口：JPEG 的完整帧结构、VMem 参数和编码结束时机；Wayland 取景对象的引用与释放规则；HEIF 格式 1003 的 10 位打包方式和中性 UV 值。在三路均实际运行且独立恢复可用之前，菜单不会允许开启黑白模式。欢迎直接在这些源码文件上修改和测试，我们会按你的实际结果补齐下一版。
