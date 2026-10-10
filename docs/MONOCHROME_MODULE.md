# Proposed monochrome pixel unit for CFV 100C

This source-only contribution is for review against Shuaqi's first-generation
907X/CFV 100C firmware 4.2.0 target. It is not included in `speed-bundle.json`
and the current installer does not upload, activate or restore it. It never
contacts a camera. The intended behavior is monochrome live view and rendered
JPEG/HEIF while a simultaneous `.3FR` remains color.

## Power-off persistence contract

The user's selected state must survive a full camera power-off and restart,
along with the menu entry. The proposed `src/mono/cfv_mono_pref.c` uses two
separate records on the camera's persistent `/blackbox` data area, matching
Shuaqi's existing auto-brightness pattern: `x2d-play-mono.available` marks an
installed feature and `x2d-play-mono.enabled` stores the selected state. An
initial installation defaults to off. Once switched on, each new GUI and
camera-service process must read both records before showing or applying the
mode. A missing, malformed or unreadable record disables the mode. The
preference write uses a temporary file, file sync, rename and directory sync.
Restore removes availability first, then the preference, so an interrupted
restore cannot leave the mode active. These functions are source-only and are
not yet called by Shuaqi's installer or camera services.

The offline test starts a fresh host process for each read/write, simulating
service restart and verifying that the user's choice survives process exit,
that a broken record fails closed, and that Restore removes both records. This
does not establish that `/blackbox` is persistent on FX's powered-off CFV;
that requires a real off/on test after reviewed integration. The installation
record and startup hook must also survive a power cycle, while an official
firmware update must be revalidated before reinstalling the extension.

## What the patch implements

`src/mono/cfv_mono.c` accepts format 103 (8-bit semiplanar YUV 4:2:2). It copies
the active luma bytes to a separately owned destination, sets active chroma to
neutral `0x80`, respects strides, rejects undersized buffers and overlapping
source/destination regions, and rejects format 1003 before any output write.
`tests/mono_native_test.c` checks these properties. This is a pixel operation,
not a renderer or a camera integration.

`src/mono/cfv_mono_jpeg.c` adds a one-shot encoder boundary. When the mode is
off it passes the stock frame handle to the encoder. When on it prepares a
separate pixel buffer and passes only the caller-supplied private handle. A
format, size or ownership failure returns before the encoder call; it does not
silently produce a color JPEG. The native test checks both paths and confirms
that the source chroma remains unchanged. The code cross-compiles for Android
ARM64. A camera frame adapter is described below, but no service startup hook
is supplied.
The owned-buffer API has a `begin`/`end` ticket: a private frame stays alive
until the device adapter calls `end` on the actual encoder-completion event.
This supports asynchronous consumption. A further read of
`lib_vc_encoder.so` shows that `JpegEncEncode` (`0x26b20`) invokes
`JpegEncEncodeRun`, then calls `JpegEncEncodeWait` (`0x26930`) on the normal
start path. That wait enters `EncJpegCodeFrameWait` (`0x24ae0`), which calls
`EWLWaitHwRdy` and releases the hardware on terminal paths. Thus a verified
normal completion from this exact JPEG route is a candidate `end` point.
The adapter still does not release a frame on an ambiguous error or timeout.
The VMem adapter calls a source-read cache sync before its deep copy, then
synchronizes the private destination for encoder reading through
`sync_for_encoder`. Both directions are supplied explicitly by its caller.
If that synchronization fails, the private frame is released and no encoder
handle is selected.

The actual firmware graph puts `camera-service` in its own process, while the
current Shuaqi native menu is preloaded into `camera-gui`. Version 0.4.3 also
preloads a separate brightness component into `camera-system`; neither existing
hook intercepts JPEG/HEIF frames in `camera-service`. A QML switch therefore
cannot reach the encoder buffers by itself. Any camera-side renderer requires
a reviewed hook in the service process, a separate versioned payload, and an
installation/restoration transaction that covers its startup configuration and
every installed file. Do not add this converter to the existing manifest on
the strength of an offline C test.

The CFV 4.2.0 JPEG plugin constructs its encoder parameter block in
`_hw_imgtec_ienc_eng_enc` and calls `duss_hal_ienc_encfrm` at plugin offset
`0x193c`. The HAL forwards to `vsi_ienc_encfrm`, which maps input and output
memory handles and calls `JpegEncEncode` at `libduml_vcodec.so` offset
`0x131d4`. This is a narrow candidate for a JPEG-only integration review,
not a validated interposition ABI. The existing `pre_ienc` forwarding path
does not make a private pixel copy. The local QEMU profile launches synthetic
camera services and the GUI, not the stock `camera-service`, so its monochrome
page test cannot validate this encoder route.

The stock frame passed to the JPEG HAL holds its VMem handle at offset `0x20`.
In `libduml_hal.so`, `duss_hal_mem_alloc` (`0x18d70`) accepts a memory manager
as its first argument; `duss_hal_mem_free`, `get_size` and `map` recover that
manager from the handle's first pointer. The stock `frame_buffer_cp` in
`libdcam_base.so` (`0x204f0`) provides a more specific route: it frees any
prior destination VMem, copies frame metadata, allocates new VMem through
`vmem_alloc_dbg`, maps both handles and copies source bytes. The corresponding
`frame_buffer_free_vmem` is at `0x1f4f0`.
`src/mono/cfv_mono_vmem.c` now models this route with injected vendor calls.
It checks the observed format/plane offsets, requires a distinct destination
handle, bounds-checks both mapped allocations, and holds the clone through
the JPEG ticket. Failure frees the clone; failed free poisons the context so
it cannot silently reuse an unknown handle. Host tests exercise successful
conversion, concurrency refusal and error cleanup.

The stock `libdcam_frwk.so` histogram path calls `duss_hal_mem_sync(handle, 1)`
before mapping a CPU-readable buffer (`0x38b90–0x38bac`); the Wayland LUT
path uses mode 2 after CPU writes. These are directional clues, not proof
that the JPEG source has the same cache contract. The actual allocation
flags, JPEG cache-sync contract and full frame descriptor size are **not
established** by the
disassembly. The normal JPEG wait path is identified, but its return codes
and error cleanup must be verified at the hook. The adapter requires these
values from an integration
review; it supplies no defaults and is not called by the installer. The host
test values are synthetic, not recommendations for the CFV.
For comparison, the stock Wayland display path copies its private LUT VMem and
then calls `duss_hal_mem_sync(handle, 2)` at `libdcam_disp_wayland.so` offset
`0x15db0–0x15db8` before display consumption. This is evidence for that LUT
buffer only; the JPEG adapter must validate its own synchronization contract.

An additional search for an existing monochrome switch found `black_white`
and `bw_enable` in `libdcam_pp.so`. Their direct use at `rltm_param_dump`
(`0x1815ec–0x181648`) only reads and reports two bytes from the local tone
mapping parameter block; it does not establish a photographic grayscale mode.
They are therefore not wired into this proposal.

## Integration work to complete with upstream review

1. Identify a *private* rendered frame after the color RAW branch and before
   the JPEG encoder, with format, plane sizes, strides, synchronization and
   ownership proved for the target camera. Supply an equally private output
   and pass its valid lifetime to the encoder. Never mutate an upstream frame
   or a forwarding descriptor in place.
2. Confirm the active format 103 layout on a captured frame. Run a same-shot
   RAW+JPEG comparison: decoded JPEG grayscale, `.3FR` still develops in color.
3. Add a live-view-only transform before the video plane's display LUT, with
   AF overlays, warnings and factory calibration unaffected. The stock
   `3dlut=lcd,0,709` resolves to display usage index 3 and mode index 1; `lcd`
   is a selector, not an `/etc` table filename. The Wayland display plugin
   does not import `dcam_adj_update_userlut`; another, unused display plugin
   does. A file swap is not a valid shortcut for this target.
4. Determine the sample packing, UV order and neutral value of format 1003
   (packed 10-bit YUV 4:2:0) before implementing HEIF. The current function
   explicitly rejects it.
5. Only after those routes work, activate the proposed camera-side UI and add
   a versioned install/upgrade/restore manifest. The current source page has
   a disabled, readiness-gated monochrome row. Restore must not depend on the
   experimental page starting successfully. Revalidate against each future
   official firmware before reinstalling the extension.
   Both the menu entry and selected on/off state must survive a full power-off;
   test that once enabled and once disabled, then confirm Restore removes both.

The immediate useful review question is the owned pre-encoder frame hook in
`camera-service`. If Radium can identify its ABI and completion callback, this
source unit can be adapted into a narrowly scoped JPEG proof on the owner's
camera before implementing the other output paths.

## Extended review components

The companion [integration handoff](MONOCHROME_HANDOFF_TO_RADIUM.md) lists the
new JPEG and HEIF HAL bridges, the independent live-view frame converter, the
loopback menu controller, and a source-only install/restore transaction. They
are host-tested but have no vendor hook, target-side readiness attestation or
factory-USB adapter. HEIF conversion is explicitly disabled until its packed
10-bit sample layout is verified. The UI refuses enabling the mode until all
three image routes and the installation verifier report readiness. None of
these additions turns the repository into a camera-installable monochrome
release by itself.
