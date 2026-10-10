#ifndef CFV_MONO_HEIF_BRIDGE_H
#define CFV_MONO_HEIF_BRIDGE_H

#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>

/* CFV 4.2.0 libdcam_ienc_hevc.so, _hevc_ienc_eng_enc +0x130..0x14c:
 * the argument to duss_hal_heifenc_encfrm is two 64-bit frame pointers.
 * This is NOT a pixel-layout description. */
typedef struct {
    const void *input_frame;
    void *output_frame;
} cfv_mono_heif_params;

typedef int (*cfv_mono_heif_hal_encfrm)(void *engine, const void *params);

enum { CFV_MONO_HEIF_REJECTED = -22001 };

/* acquire must make a separately allocated, deep-copied input frame. The
 * mapped spans are supplied so the bridge can independently reject aliasing.
 * No implementation of acquire or of format-1003 neutralization is provided
 * here: that packing and the VMem flags remain unverified on the CFV. */
typedef struct {
    void *frame;
    const uint8_t *stock_pixels;
    size_t stock_size;
    uint8_t *private_pixels;
    size_t private_size;
} cfv_mono_heif_owned;

typedef struct {
    /* Must attest the observed format-1003 packing, chroma range, sample
     * order, VMem sync modes and allocation/lifetime contract. */
    int (*contract_verified)(void *user);
    int (*acquire)(void *user, const void *stock_frame,
                   cfv_mono_heif_owned *owned);
    /* Acts only on owned.private_pixels, preserving luma and changing chroma
     * according to the independently verified packing. */
    int (*neutralize_verified)(void *user, cfv_mono_heif_owned *owned);
    int (*sync_for_encoder)(void *user, cfv_mono_heif_owned *owned);
    /* Zero return means the vendor HAL has stopped retaining the frame. */
    int (*completion_confirmed)(void *user);
    int (*release)(void *user, cfv_mono_heif_owned *owned);
} cfv_mono_heif_ops;

typedef struct {
    cfv_mono_heif_hal_encfrm original;
    const cfv_mono_heif_ops *ops;
    void *user;
    atomic_int busy;
    atomic_int observed;
    atomic_int quarantined;
    atomic_int poisoned;
    cfv_mono_heif_owned owned;
    cfv_mono_heif_params live_params;
    int last_vendor_result;
} cfv_mono_heif_bridge;

void cfv_mono_heif_bridge_init(cfv_mono_heif_bridge *bridge,
                               cfv_mono_heif_hal_encfrm original,
                               const cfv_mono_heif_ops *ops, void *user);

/* Off forwards the original call unchanged. On refuses to call the vendor
 * encoder unless an independently verified private-frame converter succeeds.
 * A failed/ambiguous vendor call quarantines the private frame. */
int cfv_mono_heif_bridge_encfrm(cfv_mono_heif_bridge *bridge, void *engine,
                                const void *params, int monochrome_enabled);

/* This is a local precondition indicator, never proof of a successful HEIF
 * capture. The UI also needs explicit device and decoded-file attestation. */
int cfv_mono_heif_bridge_available(const cfv_mono_heif_bridge *bridge);

/* Releases a quarantined frame only after external proof that the encoder is
 * quiescent. Returns 1 if released, 0 if none, -1 if not safely releasable. */
int cfv_mono_heif_bridge_resolve_quarantine(cfv_mono_heif_bridge *bridge,
                                            int encoder_quiescent_confirmed);

#endif
