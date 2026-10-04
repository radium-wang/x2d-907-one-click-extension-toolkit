#include "cfv_mono_jpeg_bridge.h"
#include <stddef.h>
#include <string.h>

_Static_assert(sizeof(void *) == 8, "CFV JPEG bridge requires 64-bit pointers");
_Static_assert(offsetof(cfv_mono_ienc_params, input_frame) == 0, "input ABI");
_Static_assert(offsetof(cfv_mono_ienc_params, output_frame) == 8, "output ABI");
_Static_assert(offsetof(cfv_mono_ienc_params, quality) == 16, "quality ABI");
_Static_assert(sizeof(cfv_mono_ienc_params) == 24, "parameter ABI");

static uint32_t frame_format(const void *frame) {
    uint32_t format;
    memcpy(&format, (const unsigned char *)frame + 0x28, sizeof format);
    return format;
}

static int memory_ready(const cfv_mono_vmem_context *vmem) {
    return vmem && vmem->descriptor && vmem->descriptor_size >= 0x90 &&
           vmem->allocation_flags > 0 && vmem->source_read_sync_mode > 0 &&
           vmem->encoder_sync_mode > 0 && !vmem->in_flight && !vmem->poisoned &&
           vmem->ops && vmem->ops->deep_copy && vmem->ops->map &&
           vmem->ops->get_size && vmem->ops->sync && vmem->ops->free_frame;
}

void cfv_mono_jpeg_bridge_init(cfv_mono_jpeg_bridge *bridge,
                               cfv_mono_hal_encfrm original,
                               cfv_mono_vmem_context *vmem) {
    if (!bridge) return;
    memset(bridge, 0, sizeof *bridge);
    bridge->original = original;
    bridge->vmem = vmem;
    bridge->last_preparation = CFV_MONO_BAD_ARGUMENT;
    atomic_init(&bridge->busy, 0);
    atomic_init(&bridge->active_seen, 0);
    atomic_init(&bridge->quarantined, 0);
    atomic_init(&bridge->ready_flag, 0);
}

int cfv_mono_jpeg_bridge_ready(const cfv_mono_jpeg_bridge *bridge) {
    return bridge && atomic_load(&bridge->ready_flag) &&
           !atomic_load(&bridge->busy);
}

int cfv_mono_jpeg_bridge_encfrm(cfv_mono_jpeg_bridge *bridge,
                                void *engine, const void *params,
                                int monochrome_enabled) {
    if (!bridge || !bridge->original || !engine || !params)
        return CFV_MONO_BRIDGE_REJECTED;
    if (atomic_exchange(&bridge->busy, 1))
        return CFV_MONO_BRIDGE_REJECTED;

    atomic_store(&bridge->ready_flag, 0);
    atomic_store(&bridge->active_seen, 1);
    bridge->last_preparation = CFV_MONO_BAD_ARGUMENT;
    bridge->last_vendor_result = CFV_MONO_BRIDGE_REJECTED;
    int result = CFV_MONO_BRIDGE_REJECTED;

    if (atomic_load(&bridge->quarantined)) goto out;
    if (!monochrome_enabled) {
        bridge->last_preparation = CFV_MONO_OK;
        result = bridge->original(engine, params);
        bridge->last_vendor_result = result;
        goto out;
    }

    if (!memory_ready(bridge->vmem)) goto out;
    cfv_mono_ienc_params original_params;
    memcpy(&original_params, params, sizeof original_params);
    if (!original_params.input_frame || !original_params.output_frame ||
        original_params.input_frame == original_params.output_frame ||
        bridge->vmem->descriptor == original_params.output_frame ||
        original_params.quality < 1 || original_params.quality > 100 ||
        original_params.reserved != 0 ||
        frame_format(original_params.input_frame) != 103 ||
        frame_format(original_params.output_frame) != 8)
        goto out;

    cfv_mono_jpeg_ticket ticket;
    bridge->last_preparation = cfv_mono_jpeg_begin(
        original_params.input_frame, 1, cfv_mono_vmem_memory(),
        bridge->vmem, &ticket);
    if (bridge->last_preparation != CFV_MONO_OK) goto out;

    /* The HAL may still retain this argument on an ambiguous error. Keep its
     * storage alongside the quarantined frame instead of using call stack. */
    bridge->live_params = original_params;
    bridge->live_params.input_frame = ticket.encoder_frame;
    result = bridge->original(engine, &bridge->live_params);
    bridge->last_vendor_result = result;
    if (result == 0) {
        /* The observed JPEG HAL returns only after its synchronous wait. */
        cfv_mono_jpeg_end(&ticket);
    } else {
        /* A failed wait does not prove the hardware stopped using the frame. */
        bridge->quarantine_ticket = ticket;
        atomic_store(&bridge->quarantined, 1);
    }

out:
    if (!atomic_load(&bridge->quarantined) && memory_ready(bridge->vmem))
        atomic_store(&bridge->ready_flag, 1);
    atomic_store(&bridge->busy, 0);
    return result;
}

int cfv_mono_jpeg_bridge_resolve_quarantine(cfv_mono_jpeg_bridge *bridge,
                                            int encoder_quiescent_confirmed) {
    if (!bridge) return -1;
    if (atomic_exchange(&bridge->busy, 1)) return -1;
    atomic_store(&bridge->ready_flag, 0);
    int result = 0;
    if (atomic_load(&bridge->quarantined)) {
        if (!encoder_quiescent_confirmed) {
            result = -1;
        } else {
            cfv_mono_jpeg_end(&bridge->quarantine_ticket);
            memset(&bridge->live_params, 0, sizeof bridge->live_params);
            atomic_store(&bridge->quarantined, 0);
            result = 1;
        }
    }
    if (atomic_load(&bridge->active_seen) &&
        !atomic_load(&bridge->quarantined) && memory_ready(bridge->vmem))
        atomic_store(&bridge->ready_flag, 1);
    atomic_store(&bridge->busy, 0);
    return result;
}
