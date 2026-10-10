#include "x2d_mono_preview_pool_adapter.h"
#include "x2d_mono_runtime.h"
#include <dlfcn.h>
#include <string.h>

static x2d_mono_preview_pool_adapter *bound_adapter;
static _Thread_local x2d_mono_preview_pool_adapter *active_adapter;
static _Thread_local int active_slot = -1;
static _Thread_local void *active_video;

static void fault(x2d_mono_preview_pool_adapter *adapter) {
    x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 0);
    if (adapter->ops.route_fault) adapter->ops.route_fault(adapter->user);
}
static int slot_index(x2d_mono_preview_pool_adapter *adapter,
                      const void *lease) {
    for (unsigned i = 0; i < X2D_MONO_WAYLAND_POOL_MAX; ++i)
        if (lease == &adapter->pool.slots[i]) return (int)i;
    return -1;
}
static int prepare(void *user, const void *stock_video,
                   const void *stock_lut,
                   cfv_mono_display_candidate *candidate) {
    (void)stock_lut;
    x2d_mono_preview_pool_adapter *adapter = user;
    int index = x2d_mono_wayland_pool_reserve(&adapter->pool);
    if (index < 0) return CFV_MONO_DISPLAY_BUSY;
    candidate->lease = &adapter->pool.slots[index];
    candidate->private_video_frame = adapter->slots[index].private_video_object;
    candidate->private_frame = adapter->slots[index].frame;
    if (adapter->ops.map_source(adapter->user, stock_video,
                                &candidate->source) != 0)
        return -1;
    return 0;
}
static int verify(void *user, const cfv_mono_display_candidate *candidate) {
    x2d_mono_preview_pool_adapter *adapter = user;
    int index = slot_index(adapter, candidate->lease);
    if (index < 0 || !candidate->private_video_frame ||
        candidate->private_video_frame != adapter->slots[index].private_video_object ||
        candidate->private_frame.owner != adapter->pool.slots[index].stable_vmem)
        return -1;
    return adapter->ops.verify_private(adapter->user, candidate);
}
static int sync_display(void *user, cfv_mono_display_candidate *candidate) {
    x2d_mono_preview_pool_adapter *adapter = user;
    return adapter->ops.sync_private(adapter->user, &candidate->private_frame);
}
static int retain(void *user, cfv_mono_display_candidate *candidate) {
    x2d_mono_preview_pool_adapter *adapter = user;
    int index = slot_index(adapter, candidate->lease);
    if (index < 0 || active_adapter) return -1;
    /* A stable handle may already have a cached wl_buffer. Mark it busy
     * before the stock call so a synchronous release is never missed. */
    if (adapter->pool.slots[index].wl_buffer &&
        x2d_mono_wayland_pool_submit_begin(&adapter->pool, index) != 0)
        return -1;
    active_adapter = adapter;
    active_slot = index;
    active_video = candidate->private_video_frame;
    return 0;
}
static void discard(void *user, cfv_mono_display_candidate *candidate) {
    x2d_mono_preview_pool_adapter *adapter = user;
    int index = slot_index(adapter, candidate->lease);
    if (index >= 0)
        (void)x2d_mono_wayland_pool_abort_unsubmitted(&adapter->pool, index);
}
static void route_fault(void *user) { fault(user); }
static int attest(void *user) {
    x2d_mono_preview_pool_adapter *adapter = user;
    return !atomic_load(&adapter->retired) &&
           adapter->ops.attest_target(adapter->user) &&
           x2d_mono_wayland_pool_live(&adapter->pool) > 0;
}
static void after_dispatch(void *user, int result) {
    x2d_mono_preview_pool_adapter *adapter = user;
    if (active_adapter != adapter) return;
    int index = active_slot;
    active_adapter = NULL;
    active_slot = -1;
    active_video = NULL;
    /* If stock returned without obtaining/using the private wl_buffer,
     * ownership is ambiguous. Quarantine this reserved slot and fail closed. */
    if (!result ||
        x2d_mono_wayland_pool_state_of(&adapter->pool, index) ==
            X2D_MONO_POOL_RESERVED)
        fault(adapter);
}
static void observed_release(void *user, void *wl_buffer) {
    x2d_mono_preview_pool_adapter *adapter = user;
    (void)x2d_mono_wayland_pool_compositor_released(&adapter->pool, wl_buffer);
}
static void observed_destroy(void *user, void *wl_buffer) {
    x2d_mono_preview_pool_adapter *adapter = user;
    (void)x2d_mono_wayland_pool_proxy_destroyed(&adapter->pool, wl_buffer);
}
int x2d_mono_preview_pool_adapter_init(
    x2d_mono_preview_pool_adapter *adapter,
    const x2d_mono_preview_pool_vendor_ops *ops, void *user) {
    if (!adapter || !ops || !ops->map_source || !ops->verify_private ||
        !ops->sync_private || !ops->attest_target || !ops->route_fault)
        return -1;
    memset(adapter, 0, sizeof *adapter);
    atomic_init(&adapter->retired, 0);
    adapter->ops = *ops;
    adapter->user = user;
    return x2d_mono_wayland_pool_init(&adapter->pool);
}
int x2d_mono_preview_pool_adapter_add_slot(
    x2d_mono_preview_pool_adapter *adapter, void *private_video_object,
    const cfv_mono_preview_private *frame, void *lease,
    x2d_mono_wayland_pool_free_fn free_lease, void *lease_user) {
    if (!adapter || atomic_load(&adapter->retired) ||
        !private_video_object || !frame || !frame->owner ||
        !frame->y || !frame->uv || !lease || !free_lease)
        return -1;
    int index = x2d_mono_wayland_pool_add(&adapter->pool, frame->owner,
                                          lease, free_lease, lease_user);
    if (index >= 0)
        adapter->slots[index] = (x2d_mono_preview_pool_slot){
            private_video_object, *frame};
    return index;
}
int x2d_mono_preview_pool_adapter_bind(
    x2d_mono_preview_pool_adapter *adapter,
    cfv_mono_display_stock stock_handle_buf,
    x2d_mono_wayland_alloc_stock stock_alloc,
    void (*stock_buffer_release)(void *, void *),
    void (*stock_proxy_destroy)(void *)) {
    if (!adapter || atomic_load(&adapter->retired) ||
        x2d_mono_wayland_pool_live(&adapter->pool) == 0)
        return -1;
    bound_adapter = adapter;
    adapter->stock_alloc = stock_alloc;
    x2d_mono_wayland_proxy_hooks_bind(&(x2d_mono_wayland_proxy_hooks){
        stock_buffer_release, stock_proxy_destroy,
        observed_release, observed_destroy, adapter});
    x2d_mono_preview_bind(stock_handle_buf, &(x2d_mono_preview_vendor){
        .display = {prepare, verify, sync_display, retain, discard, route_fault},
        .attest_target_route = attest,
        .after_dispatch = after_dispatch
    }, adapter);
    return 0;
}
void x2d_mono_preview_pool_adapter_retire(
    x2d_mono_preview_pool_adapter *adapter) {
    if (!adapter) return;
    atomic_store(&adapter->retired, 1);
    x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 0);
    x2d_mono_wayland_pool_retire(&adapter->pool);
}
static x2d_mono_wayland_alloc_stock resolve_alloc(void) {
    if (bound_adapter && bound_adapter->stock_alloc)
        return bound_adapter->stock_alloc;
    void *symbol = dlsym(RTLD_NEXT,
        "_ZN14WaylandControl16allocProtBuffersERK17duss_frame_buffer14Recommendation");
    x2d_mono_wayland_alloc_stock stock = NULL;
    memcpy(&stock, &symbol, sizeof stock);
    return stock;
}
x2d_mono_wayland_buffer_pair x2d_mono_wayland_alloc_interpose(
    void *control, const void *frame, uint32_t recommendation) {
    x2d_mono_wayland_alloc_stock stock = resolve_alloc();
    x2d_mono_wayland_buffer_pair result = {0};
    if (!stock) return result;
    result = stock(control, frame, recommendation);
    if (!active_adapter || frame != active_video) return result;
    if (!result.wl_buffer ||
        x2d_mono_wayland_pool_bind_buffer(&active_adapter->pool,
                                          active_slot, result.wl_buffer) != 0 ||
        x2d_mono_wayland_pool_submit_begin(&active_adapter->pool,
                                           active_slot) != 0)
        fault(active_adapter);
    return result;
}
