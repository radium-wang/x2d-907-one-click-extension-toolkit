#include "cfv_mono_heif_bridge.h"
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(void *) == 8, "CFV HEIF bridge needs 64-bit pointers");
_Static_assert(offsetof(cfv_mono_heif_params, input_frame) == 0, "input ABI");
_Static_assert(offsetof(cfv_mono_heif_params, output_frame) == 8, "output ABI");
_Static_assert(sizeof(cfv_mono_heif_params) == 16, "HEIF parameter ABI");

static uint32_t u32(const void *base, size_t offset) {
    uint32_t value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static void *pointer_at(const void *base, size_t offset) {
    void *value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static int disjoint(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (!a || !b || !an || !bn || an > UINTPTR_MAX - x ||
        bn > UINTPTR_MAX - y) return 0;
    return x + an <= y || y + bn <= x;
}

static int ops_complete(const cfv_mono_heif_bridge *bridge) {
    const cfv_mono_heif_ops *ops = bridge ? bridge->ops : NULL;
    return bridge && bridge->original && ops && ops->contract_verified &&
           ops->acquire && ops->neutralize_verified &&
           ops->sync_for_encoder && ops->completion_confirmed &&
           ops->release;
}

void cfv_mono_heif_bridge_init(cfv_mono_heif_bridge *bridge,
                               cfv_mono_heif_hal_encfrm original,
                               const cfv_mono_heif_ops *ops, void *user) {
    if (!bridge) return;
    memset(bridge, 0, sizeof *bridge);
    bridge->original = original;
    bridge->ops = ops;
    bridge->user = user;
    bridge->last_vendor_result = CFV_MONO_HEIF_REJECTED;
    atomic_init(&bridge->busy, 0);
    atomic_init(&bridge->observed, 0);
    atomic_init(&bridge->quarantined, 0);
    atomic_init(&bridge->poisoned, 0);
}

int cfv_mono_heif_bridge_available(const cfv_mono_heif_bridge *bridge) {
    return ops_complete(bridge) && atomic_load(&bridge->observed) &&
           !atomic_load(&bridge->busy) &&
           !atomic_load(&bridge->quarantined) &&
           !atomic_load(&bridge->poisoned) &&
           bridge->ops->contract_verified(bridge->user);
}

static int release_owned(cfv_mono_heif_bridge *bridge) {
    if (bridge->ops->release(bridge->user, &bridge->owned) != 0) {
        atomic_store(&bridge->poisoned, 1);
        return -1;
    }
    memset(&bridge->owned, 0, sizeof bridge->owned);
    memset(&bridge->live_params, 0, sizeof bridge->live_params);
    return 0;
}

int cfv_mono_heif_bridge_encfrm(cfv_mono_heif_bridge *bridge, void *engine,
                                const void *params, int monochrome_enabled) {
    if (!bridge || !bridge->original || !engine || !params)
        return CFV_MONO_HEIF_REJECTED;
    if (atomic_exchange(&bridge->busy, 1)) return CFV_MONO_HEIF_REJECTED;
    int result = CFV_MONO_HEIF_REJECTED;
    if (atomic_load(&bridge->quarantined) || atomic_load(&bridge->poisoned))
        goto out;
    atomic_store(&bridge->observed, 1);
    if (!monochrome_enabled) {
        result = bridge->original(engine, params);
        bridge->last_vendor_result = result;
        goto out;
    }
    if (!ops_complete(bridge) ||
        !bridge->ops->contract_verified(bridge->user)) goto out;

    cfv_mono_heif_params stock;
    memcpy(&stock, params, sizeof stock);
    if (!stock.input_frame || !stock.output_frame ||
        stock.input_frame == stock.output_frame ||
        u32(stock.input_frame, 0x28) != 1003 ||
        u32(stock.output_frame, 0x28) != 2 ||
        !u32(stock.input_frame, 0x38) ||
        !u32(stock.input_frame, 0x3c) ||
        u32(stock.input_frame, 0x38) != u32(stock.output_frame, 0x30) ||
        u32(stock.input_frame, 0x3c) != u32(stock.output_frame, 0x34) ||
        !pointer_at(stock.input_frame, 0x20)) goto out;

    memset(&bridge->owned, 0, sizeof bridge->owned);
    if (bridge->ops->acquire(bridge->user, stock.input_frame,
                             &bridge->owned) != 0) {
        /* acquire owns cleanup for a partial allocation. */
        memset(&bridge->owned, 0, sizeof bridge->owned);
        goto out;
    }

    const cfv_mono_heif_owned *owned = &bridge->owned;
    if (!owned->frame || owned->frame == stock.input_frame ||
        owned->frame == stock.output_frame ||
        !disjoint(owned->stock_pixels, owned->stock_size,
                  owned->private_pixels, owned->private_size) ||
        !pointer_at(owned->frame, 0x20) ||
        pointer_at(owned->frame, 0x20) ==
            pointer_at(stock.input_frame, 0x20) ||
        u32(owned->frame, 0x28) != 1003 ||
        u32(owned->frame, 0x38) != u32(stock.input_frame, 0x38) ||
        u32(owned->frame, 0x3c) != u32(stock.input_frame, 0x3c) ||
        bridge->ops->neutralize_verified(bridge->user, &bridge->owned) != 0 ||
        bridge->ops->sync_for_encoder(bridge->user, &bridge->owned) != 0) {
        (void)release_owned(bridge);
        goto out;
    }

    bridge->live_params = stock;
    bridge->live_params.input_frame = bridge->owned.frame;
    result = bridge->original(engine, &bridge->live_params);
    bridge->last_vendor_result = result;
    if (result == 0 &&
        bridge->ops->completion_confirmed(bridge->user) == 0) {
        if (release_owned(bridge) != 0) result = CFV_MONO_HEIF_REJECTED;
    } else {
        /* A HAL return alone does not prove the encoder released its input. */
        atomic_store(&bridge->quarantined, 1);
    }

out:
    atomic_store(&bridge->busy, 0);
    return result;
}

int cfv_mono_heif_bridge_resolve_quarantine(cfv_mono_heif_bridge *bridge,
                                            int encoder_quiescent_confirmed) {
    if (!bridge || !ops_complete(bridge)) return -1;
    if (atomic_exchange(&bridge->busy, 1)) return -1;
    int result = 0;
    if (atomic_load(&bridge->quarantined)) {
        if (!encoder_quiescent_confirmed || release_owned(bridge) != 0)
            result = -1;
        else {
            atomic_store(&bridge->quarantined, 0);
            result = 1;
        }
    }
    atomic_store(&bridge->busy, 0);
    return result;
}
