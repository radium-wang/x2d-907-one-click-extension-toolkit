#include "x2d_mono_jpeg_runtime.h"
#include "x2d_mono_runtime.h"
#include "cfv_mono_jpeg_bridge.h"
#include <dlfcn.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>

static pthread_once_t stock_once = PTHREAD_ONCE_INIT;
static cfv_mono_hal_encfrm stock;
static cfv_mono_vmem_ops owned_ops;
static cfv_mono_vmem_context vmem;
static cfv_mono_jpeg_bridge bridge;
static int (*quiescent)(void *);
static void *quiescence_user;
static atomic_int bound;

static void resolve_stock(void) {
#ifdef X2D_MONO_JPEG_HOST_TEST
    extern int x2d_mono_jpeg_host_stock(void *, const void *);
    stock = x2d_mono_jpeg_host_stock;
#else
    void *provider = dlopen("libduml_vcodec.so", RTLD_NOW | RTLD_LOCAL);
    void *symbol = provider ? dlsym(provider, "duss_hal_ienc_encfrm") : NULL;
    memcpy(&stock, &symbol, sizeof stock);
#endif
}

static cfv_mono_hal_encfrm original(void) {
    pthread_once(&stock_once, resolve_stock);
    return stock;
}

int x2d_mono_jpeg_bind(const x2d_mono_jpeg_contract *contract) {
    cfv_mono_hal_encfrm vendor = original();
    if (!contract || !vendor || atomic_load(&bound) ||
        !contract->private_descriptor ||
        contract->descriptor_size < 0x90 ||
        contract->descriptor_size > 4096 ||
        contract->allocation_flags <= 0 ||
        contract->source_read_sync_mode <= 0 ||
        contract->encoder_sync_mode <= 0 ||
        contract->success_means_completed != 1 ||
        !contract->encoder_quiescent ||
        !contract->ops.deep_copy || !contract->ops.map ||
        !contract->ops.get_size || !contract->ops.sync ||
        !contract->ops.free_frame) return -1;

    owned_ops = contract->ops;
    memset(&vmem, 0, sizeof vmem);
    vmem.descriptor = contract->private_descriptor;
    vmem.descriptor_size = contract->descriptor_size;
    vmem.allocation_flags = contract->allocation_flags;
    vmem.source_read_sync_mode = contract->source_read_sync_mode;
    vmem.encoder_sync_mode = contract->encoder_sync_mode;
    vmem.ops = &owned_ops;
    vmem.user = contract->vendor_user;
    quiescent = contract->encoder_quiescent;
    quiescence_user = contract->quiescence_user;
    cfv_mono_jpeg_bridge_init(&bridge, vendor, &vmem);
    atomic_store(&bound, 1);
    /* The reviewed bind contract, rather than a color test exposure,
     * unlocks selection. The bridge validates the first real frame. */
    x2d_mono_runtime_ready(CFV_MONO_READY_JPEG, 1);
    return 0;
}

int x2d_mono_jpeg_ready(void) {
    return atomic_load(&bound) && cfv_mono_jpeg_bridge_ready(&bridge);
}

int x2d_mono_jpeg_recover(void) {
    if (!atomic_load(&bound) || !quiescent) return -1;
    int result = cfv_mono_jpeg_bridge_resolve_quarantine(&bridge,
                                     quiescent(quiescence_user) == 1);
    if (result < 0) x2d_mono_runtime_ready(CFV_MONO_READY_JPEG, 0);
    return result;
}

int duss_hal_ienc_encfrm(void *engine, const void *params) {
    cfv_mono_hal_encfrm vendor = original();
    if (!vendor) return CFV_MONO_BRIDGE_REJECTED;

    /* No contract means the mode cannot be active. Preserve normal capture
     * while disabled; if it ever becomes active, refuse color fallback. */
    int requested = x2d_mono_runtime_requested();
    if (!atomic_load(&bound)) {
        x2d_mono_runtime_ready(CFV_MONO_READY_JPEG, 0);
        return requested ? CFV_MONO_BRIDGE_REJECTED : vendor(engine, params);
    }
    /* A failed sibling route must not silently turn a requested monochrome
     * exposure into a color file. Keep the stock path only when deselected. */
    if (requested && !x2d_mono_runtime_enabled())
        return CFV_MONO_BRIDGE_REJECTED;
    int result = cfv_mono_jpeg_bridge_encfrm(&bridge, engine, params,
                                             requested != 0);
    int ready = result == 0 && x2d_mono_jpeg_ready() &&
                bridge.last_preparation == CFV_MONO_OK;
    x2d_mono_runtime_ready(CFV_MONO_READY_JPEG, ready);
    return result;
}
