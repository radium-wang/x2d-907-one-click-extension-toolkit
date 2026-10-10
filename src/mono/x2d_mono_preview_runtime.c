#include "x2d_mono_preview_runtime.h"
#include "x2d_mono_runtime.h"
#include <dlfcn.h>
#include <stdatomic.h>
#include <string.h>

static cfv_mono_display_stock stock_handle_buf;
static x2d_mono_preview_vendor vendor_ops;
static void *vendor_user;
static int vendor_bound;
static atomic_int route_faulted;

static void route_fault(void *user) {
    atomic_store(&route_faulted, 1);
    x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 0);
    if (vendor_ops.display.route_fault)
        vendor_ops.display.route_fault(user);
}

void x2d_mono_preview_bind(cfv_mono_display_stock stock,
                           const x2d_mono_preview_vendor *vendor,
                           void *user) {
    stock_handle_buf = stock;
    vendor_user = user;
    vendor_bound = 0;
    atomic_store(&route_faulted, 0);
    memset(&vendor_ops, 0, sizeof vendor_ops);
    x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 0);
    if (!vendor || !vendor->attest_target_route ||
        !vendor->display.prepare || !vendor->display.verify ||
        !vendor->display.sync_for_display ||
        !vendor->display.retain_before_submit || !vendor->display.discard ||
        !vendor->display.route_fault)
        return;
    vendor_ops = *vendor;
    vendor_bound = 1;
}

static cfv_mono_display_stock resolve_stock(void) {
    if (stock_handle_buf) return stock_handle_buf;
    void *symbol = dlsym(RTLD_NEXT, X2D_MONO_LV_HANDLE_BUF_SYMBOL);
    cfv_mono_display_stock resolved = NULL;
    /* dlsym returns a code pointer on the target Android ARM64 ABI. */
    memcpy(&resolved, &symbol, sizeof resolved);
    return resolved;
}

int x2d_mono_preview_handle_buf(void *wayland_control, void *stock_video_object,
                                 const void *stock_lut_capsule_ref,
                                 uint32_t recommendation,
                                 const void *rectangle, void *overlay_frame) {
    cfv_mono_display_stock stock = resolve_stock();
    if (!stock) return 0;
    /* The graphics argument is essential in this LV path. Forward it as-is. */
    if (!vendor_bound || atomic_load(&route_faulted) ||
        !vendor_ops.attest_target_route(vendor_user)) {
        x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 0);
        return stock(wayland_control, stock_video_object,
                     stock_lut_capsule_ref, recommendation, rectangle,
                     overlay_frame);
    }
    /* A target adapter may attest only after verifying a real private VMem,
     * object ownership and release callback. The readiness bit is then
     * available for the camera menu on its next status request. */
    x2d_mono_runtime_ready(CFV_MONO_READY_PREVIEW, 1);
    cfv_mono_display_ops dispatch_ops = vendor_ops.display;
    dispatch_ops.route_fault = route_fault;
    int result = cfv_mono_display_dispatch(x2d_mono_runtime_enabled(), stock,
                                           wayland_control, stock_video_object,
                                           stock_lut_capsule_ref, recommendation,
                                           rectangle, overlay_frame,
                                           &dispatch_ops, vendor_user);
    if (vendor_ops.after_dispatch)
        vendor_ops.after_dispatch(vendor_user, result);
    return result;
}

/* The ELF symbol must match the vendor C++ method, while the implementation
 * is C and keeps all vendor objects opaque. */
int x2d_mono_lv_interpose(void *wayland_control, void *stock_video_object,
                          const void *stock_lut_capsule_ref,
                          uint32_t recommendation, const void *rectangle,
                          void *overlay_frame)
    __asm__(X2D_MONO_LV_HANDLE_BUF_SYMBOL);
int x2d_mono_lv_interpose(void *wayland_control, void *stock_video_object,
                          const void *stock_lut_capsule_ref,
                          uint32_t recommendation, const void *rectangle,
                          void *overlay_frame) {
    return x2d_mono_preview_handle_buf(wayland_control, stock_video_object,
                                       stock_lut_capsule_ref, recommendation,
                                       rectangle, overlay_frame);
}
