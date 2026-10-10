#include "cfv_mono_display.h"
#include <string.h>

int cfv_mono_display_dispatch(int enabled,
                              cfv_mono_display_stock stock,
                              void *wayland_control, void *stock_video_frame,
                              const void *stock_capsule_ref,
                              uint32_t recommendation,
                              const void *rectangle,
                              void *overlay_frame,
                              const cfv_mono_display_ops *ops,
                              void *user) {
    if (!stock) return 0;
    /* The pinned LV implementation returns early when x5 is null. Such a
     * frame never reaches video presentation; keep it entirely stock. */
    if (!enabled || !overlay_frame)
        return stock(wayland_control, stock_video_frame, stock_capsule_ref,
                     recommendation, rectangle, overlay_frame);

    cfv_mono_display_candidate candidate;
    memset(&candidate, 0, sizeof(candidate));
    if (!ops || !ops->prepare || !ops->verify || !ops->sync_for_display ||
        !ops->retain_before_submit || !ops->discard || !ops->route_fault ||
        !stock_video_frame || !stock_capsule_ref)
        goto fallback;
    int prepared = ops->prepare(user, stock_video_frame, stock_capsule_ref,
                                &candidate);
    if (prepared == CFV_MONO_DISPLAY_BUSY)
        return stock(wayland_control, stock_video_frame, stock_capsule_ref,
                     recommendation, rectangle, overlay_frame);
    if (prepared != 0) {
        ops->discard(user, &candidate);
        goto fallback;
    }
    if (!candidate.private_video_frame || !candidate.lease ||
        !candidate.source.owner || !candidate.private_frame.owner ||
        candidate.source.owner == candidate.private_frame.owner ||
        candidate.source.width != 1944 || candidate.source.height != 1248 ||
        ops->verify(user, &candidate) != 0 ||
        cfv_mono_preview_convert(&candidate.source,
                                 &candidate.private_frame) != CFV_MONO_PREVIEW_OK ||
        ops->sync_for_display(user, &candidate) != 0) {
        ops->discard(user, &candidate);
        goto fallback;
    }
    if (ops->retain_before_submit(user, &candidate) != 0) {
        ops->discard(user, &candidate);
        goto fallback;
    }

    int result = stock(wayland_control, candidate.private_video_frame,
                       stock_capsule_ref,
                       recommendation, rectangle, overlay_frame);
    if (!result) {
        /* The stock call may already have captured a reference. The lease
         * stays retained after an ambiguous return; never free it here. */
        ops->route_fault(user);
    }
    return result;

fallback:
    if (ops && ops->route_fault) ops->route_fault(user);
    return stock(wayland_control, stock_video_frame, stock_capsule_ref,
                 recommendation, rectangle, overlay_frame);
}
