#ifndef X2D_MONO_PREVIEW_RUNTIME_H
#define X2D_MONO_PREVIEW_RUNTIME_H

#include "cfv_mono_display.h"

/* Exact first-generation 4.2.0 libdcam_disp_wayland.so entry point.
 * The x2 argument is the stock display LUT, never private video memory.
 * Configure before camera-service starts presenting frames. */
#define X2D_MONO_LV_HANDLE_BUF_SYMBOL \
    "_ZN16WaylandControlLV9handleBufEPvRKNSt3__110shared_ptrI10MemCapsuleEE14RecommendationRK9RectangleP17duss_frame_buffer"

typedef struct {
    cfv_mono_display_ops display;
    /* Returns 1 only after the exact loaded vendor ABI, independently owned
     * video object/VMem, and Wayland release callback have been attested on
     * the target. Offline fixture success is insufficient. */
    int (*attest_target_route)(void *user);
    /* Clears per-thread submit context after stock handleBuf returns. */
    void (*after_dispatch)(void *user, int result);
} x2d_mono_preview_vendor;

/* A null stock pointer requests RTLD_NEXT resolution in the hook. A vendor
 * module may be bound once before the first frame. Binding does not claim
 * readiness; it requires an attestation callback from the target adapter. */
void x2d_mono_preview_bind(cfv_mono_display_stock stock,
                           const x2d_mono_preview_vendor *vendor,
                           void *user);

/* Explicit forwarding entry useful for tests and an exact-symbol trampoline. */
int x2d_mono_preview_handle_buf(void *wayland_control, void *stock_video_object,
                                 const void *stock_lut_capsule_ref,
                                 uint32_t recommendation,
                                 const void *rectangle, void *overlay_frame);

#endif
