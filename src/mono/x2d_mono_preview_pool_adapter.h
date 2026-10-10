#ifndef X2D_MONO_PREVIEW_POOL_ADAPTER_H
#define X2D_MONO_PREVIEW_POOL_ADAPTER_H

#include "x2d_mono_preview_runtime.h"
#include "x2d_mono_wayland_pool.h"
#include "x2d_mono_wayland_proxy_hook.h"
#include <stdatomic.h>

typedef struct {
    /* Must synchronize stock source for CPU read and expose real video Y/UV. */
    int (*map_source)(void *user, const void *stock_video_object,
                      cfv_mono_preview_source *source);
    /* Attest source/private physical disjointness and that private_video_object
     * owns exactly the stable VMem supplied for the selected slot. */
    int (*verify_private)(void *user, const cfv_mono_display_candidate *candidate);
    int (*sync_private)(void *user, cfv_mono_preview_private *private_frame);
    /* Only target-side evidence for the exact loaded 4.2.0 plugin and
     * verified vendor object/VMem/lifetime ABI may return 1. */
    int (*attest_target)(void *user);
    void (*route_fault)(void *user);
} x2d_mono_preview_pool_vendor_ops;

typedef struct {
    void *private_video_object;
    cfv_mono_preview_private frame;
} x2d_mono_preview_pool_slot;

typedef struct {
    void *wl_buffer;
    void *eagle_buffer;
} x2d_mono_wayland_buffer_pair;
typedef x2d_mono_wayland_buffer_pair (*x2d_mono_wayland_alloc_stock)(
    void *control, const void *frame, uint32_t recommendation);

typedef struct {
    x2d_mono_wayland_pool pool;
    atomic_int retired;
    x2d_mono_preview_pool_slot slots[X2D_MONO_WAYLAND_POOL_MAX];
    x2d_mono_preview_pool_vendor_ops ops;
    void *user;
    x2d_mono_wayland_alloc_stock stock_alloc;
} x2d_mono_preview_pool_adapter;

int x2d_mono_preview_pool_adapter_init(
    x2d_mono_preview_pool_adapter *adapter,
    const x2d_mono_preview_pool_vendor_ops *ops, void *user);
/* Caller supplies stable, independently owned private video objects and VMem.
 * No vendor object layout is fabricated by this source unit. In the pinned
 * 4.2.0 base WaylandControl::handleBuf, x1 is passed to a duss_object unref
 * routine at 0x1ea88 (mutex at +0x8, refcount at +0x0, callback at +0x10).
 * A stack-only frame_buffer descriptor proxy is therefore unsafe. */
int x2d_mono_preview_pool_adapter_add_slot(
    x2d_mono_preview_pool_adapter *adapter, void *private_video_object,
    const cfv_mono_preview_private *frame, void *lease,
    x2d_mono_wayland_pool_free_fn free_lease, void *lease_user);
/* Startup-only binding after at least one owned private slot is installed.
 * No constructor binds this adapter automatically: without target-side vendor
 * object creation and explicit binding, the exported hook stays stock.
 * Returns -1 and leaves the hook dormant when the pool is empty. */
int x2d_mono_preview_pool_adapter_bind(
    x2d_mono_preview_pool_adapter *adapter,
    cfv_mono_display_stock stock_handle_buf,
    x2d_mono_wayland_alloc_stock stock_alloc,
    void (*stock_buffer_release)(void *, void *),
    void (*stock_proxy_destroy)(void *));
void x2d_mono_preview_pool_adapter_retire(
    x2d_mono_preview_pool_adapter *adapter);

/* Interposes only the exported allocProtBuffers method. The x5 graphics
 * path remains stock; the active private video object is matched by address. */
x2d_mono_wayland_buffer_pair x2d_mono_wayland_alloc_interpose(
    void *control, const void *frame, uint32_t recommendation)
    __asm__("_ZN14WaylandControl16allocProtBuffersERK17duss_frame_buffer14Recommendation");

#endif
