#ifndef CFV_MONO_DISPLAY_H
#define CFV_MONO_DISPLAY_H

#include "cfv_mono_preview.h"
#include <stdint.h>

/* ABI of WaylandControlLV::handleBuf in the pinned 4.2.0 Wayland plugin.
 * x1 is the VIDEO object; x2 is the separate display-LUT MemCapsule
 * shared_ptr reference. The LUT must be passed through unchanged.
 * x5 is a separate graphics/overlay frame and must be preserved. A null x5
 * returns early in the stock LV implementation, without video presentation.
 * All vendor objects stay opaque: no duss_object or libc++ layout guessed. */
typedef int (*cfv_mono_display_stock)(void *wayland_control,
                                      void *video_frame,
                                      const void *capsule_shared_ptr_ref,
                                      uint32_t recommendation,
                                      const void *rectangle,
                                      void *overlay_frame);

typedef struct {
    cfv_mono_preview_source source;
    cfv_mono_preview_private private_frame;
    void *private_video_frame;
    void *lease;
} cfv_mono_display_candidate;

/* No released private slot for this frame: forward stock without a route fault. */
#define CFV_MONO_DISPLAY_BUSY 1

typedef struct {
    /* Return zero only after mapping a separate, owned source/destination.
     * CFV_MONO_DISPLAY_BUSY allows a transient stock frame while all private
     * slots are held by the compositor.
     * The private video object must own new pixel VMem. The LUT capsule in
     * x2 is independent and remains the stock argument.
     * Include the correct CPU-read synchronization of the source. */
    int (*prepare)(void *user, const void *stock_video_frame,
                   const void *stock_capsule_ref,
                   cfv_mono_display_candidate *candidate);
    /* Attest physical disjointness and video-object/VMem consistency. */
    int (*verify)(void *user, const cfv_mono_display_candidate *candidate);
    int (*sync_for_display)(void *user, cfv_mono_display_candidate *candidate);
    /* Take the lease BEFORE invoking Wayland, since a release callback could
     * occur synchronously. On an ambiguous submission result, quarantine
     * until release instead of risking a use-after-free. */
    int (*retain_before_submit)(void *user, cfv_mono_display_candidate *candidate);
    /* Release a prepared candidate which was never handed to Wayland. */
    void (*discard)(void *user, cfv_mono_display_candidate *candidate);
    /* Clear display readiness and selected state on a conversion failure. */
    void (*route_fault)(void *user);
} cfv_mono_display_ops;

/* Narrow dispatch core for the exported WaylandControlLV::handleBuf symbol.
 * Does not patch vendor binaries or register an interposer. The caller
 * supplies a previously resolved stock function. Off mode is pass-through.
 * On preparation fault it forwards the stock video and reports route fault. */
int cfv_mono_display_dispatch(int enabled,
                              cfv_mono_display_stock stock,
                              void *wayland_control, void *stock_video_frame,
                              const void *stock_capsule_ref,
                              uint32_t recommendation,
                              const void *rectangle,
                              void *overlay_frame,
                              const cfv_mono_display_ops *ops,
                              void *user);

#endif
