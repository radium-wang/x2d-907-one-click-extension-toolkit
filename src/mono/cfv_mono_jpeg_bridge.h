#ifndef CFV_MONO_JPEG_BRIDGE_H
#define CFV_MONO_JPEG_BRIDGE_H

#include "cfv_mono_vmem.h"
#include <stdatomic.h>
#include <stdint.h>

/* Observed at libdcam_ienc_jpeg.so:_hw_imgtec_ienc_eng_enc+0x18c..0x1c8
 * on CFV 100C 4.2.0: the first 24 bytes passed to duss_hal_ienc_encfrm.
 * The fourth field is the zero high half of the 64-bit quality slot. */
typedef struct {
    const void *input_frame;  /* +0 */
    void *output_frame;       /* +8 */
    uint32_t quality;         /* +16 */
    uint32_t reserved;        /* +20 */
} cfv_mono_ienc_params;

typedef int (*cfv_mono_hal_encfrm)(void *engine, const void *params);

enum { CFV_MONO_BRIDGE_REJECTED = -21001 };

/* Single bridge per JPEG encoder instance. Initialise to zero before use.
 * The caller supplies the original HAL entry point and an already configured
 * VMem adapter. No implicit symbol lookup, hook installation, or file I/O. */
typedef struct {
    cfv_mono_hal_encfrm original;
    cfv_mono_vmem_context *vmem;
    atomic_int busy;
    atomic_int active_seen;
    atomic_int quarantined;
    atomic_int ready_flag;
    cfv_mono_jpeg_ticket quarantine_ticket;
    cfv_mono_ienc_params live_params;
    cfv_mono_result last_preparation;
    int last_vendor_result;
} cfv_mono_jpeg_bridge;

void cfv_mono_jpeg_bridge_init(cfv_mono_jpeg_bridge *bridge,
                               cfv_mono_hal_encfrm original,
                               cfv_mono_vmem_context *vmem);

/* Call at the actual duss_hal_ienc_encfrm boundary, with the original two
 * arguments. Off forwards them unchanged. On requires an observed format-103
 * input and format-8 output, makes a private input frame, and calls original
 * with a private 24-byte parameter block. It never falls back to color. */
int cfv_mono_jpeg_bridge_encfrm(cfv_mono_jpeg_bridge *bridge,
                                void *engine,
                                const void *params,
                                int monochrome_enabled);

/* True only after this boundary has actually been invoked, all VMem
 * prerequisites are configured, and no call or ambiguous failure is active.
 * A UI/installer must additionally attest the target PID and loaded binary
 * identity before publishing any cross-process readiness marker. */
int cfv_mono_jpeg_bridge_ready(const cfv_mono_jpeg_bridge *bridge);

/* A nonzero vendor return may leave asynchronous use of the input uncertain.
 * Release a quarantined frame only after the caller has independently proven
 * that the encoder is quiescent. Returns 1 if released, 0 if none, -1 if not
 * confirmed or another call is in progress. */
int cfv_mono_jpeg_bridge_resolve_quarantine(cfv_mono_jpeg_bridge *bridge,
                                            int encoder_quiescent_confirmed);

#endif
