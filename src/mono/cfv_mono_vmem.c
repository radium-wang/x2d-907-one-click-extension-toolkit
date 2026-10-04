#include "cfv_mono_vmem.h"
#include <stdint.h>
#include <string.h>

enum {
    FRAME_VMEM = 0x20, FRAME_FORMAT = 0x28, FRAME_WIDTH = 0x38,
    FRAME_HEIGHT = 0x3c, FRAME_PLANE0 = 0x40, FRAME_PLANE1 = 0x50,
    FRAME_PLANE_COUNT = 0x80, FRAME_MIN_SIZE = 0x90
};

static uint32_t u32(const void *base, size_t offset) {
    uint32_t value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static void *ptr(const void *base, size_t offset) {
    void *value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static void put_ptr(void *base, size_t offset, void *value) {
    memcpy((uint8_t *)base + offset, &value, sizeof value);
}

static int plane(const void *descriptor, uint8_t *mapped, size_t mapped_size,
                 size_t field, size_t width, size_t height,
                 uint8_t **address, size_t *available, size_t *stride) {
    const size_t pitch = u32(descriptor, field);
    const size_t offset = u32(descriptor, field + 4);
    const size_t rows = u32(descriptor, field + 8);
    if (rows < height || pitch < width || offset > mapped_size ||
        height == 0 || height - 1 > (SIZE_MAX - width) / pitch ||
        (height - 1) * pitch + width > mapped_size - offset)
        return -1;
    *address = mapped + offset;
    /* Expose only this plane's declared storage. Returning the remainder of
     * the allocation would make the Y span appear to overlap the UV span. */
    if (rows > SIZE_MAX / pitch) return -1;
    const size_t declared = rows * pitch;
    *available = declared < mapped_size - offset ? declared : mapped_size - offset;
    *stride = pitch;
    return 0;
}

static void discard(cfv_mono_vmem_context *context) {
    if (ptr(context->descriptor, FRAME_VMEM) &&
        context->ops->free_frame(context->user, context->descriptor) != 0) {
        /* The ownership state is unknown. Never reuse the descriptor. */
        context->poisoned = 1;
        context->in_flight = 0;
        return;
    }
    put_ptr(context->descriptor, FRAME_VMEM, NULL);
    context->in_flight = 0;
}

static int acquire(void *opaque, const void *stock,
                   cfv_mono_owned_jpeg_frame *owned) {
    cfv_mono_vmem_context *context = opaque;
    if (!context || !stock || !owned || !context->descriptor ||
        context->descriptor_size < FRAME_MIN_SIZE ||
        context->allocation_flags <= 0 ||
        context->source_read_sync_mode <= 0 ||
        context->encoder_sync_mode <= 0 || context->in_flight ||
        context->poisoned ||
        context->descriptor == stock || !context->ops ||
        !context->ops->deep_copy || !context->ops->map ||
        !context->ops->get_size || !context->ops->sync ||
        !context->ops->free_frame || u32(stock, FRAME_FORMAT) != 103 ||
        u32(stock, FRAME_PLANE_COUNT) != 2 || !ptr(stock, FRAME_VMEM))
        return -1;

    const size_t width = u32(stock, FRAME_WIDTH);
    const size_t height = u32(stock, FRAME_HEIGHT);
    if (!width || !height || width > 20000 || height > 20000 || (width & 1))
        return -1;

    /* frame_buffer_cp maps and reads the source. Synchronize it first. */
    if (context->ops->sync(context->user, ptr(stock, FRAME_VMEM),
                           context->source_read_sync_mode) != 0)
        return -1;

    memcpy(context->descriptor, stock, context->descriptor_size);
    put_ptr(context->descriptor, FRAME_VMEM, NULL);
    if (context->ops->deep_copy(context->user, context->descriptor, stock,
                                context->allocation_flags) != 0) {
        discard(context);
        return -1;
    }
    void *source_handle = ptr(stock, FRAME_VMEM);
    void *private_handle = ptr(context->descriptor, FRAME_VMEM);
    if (!private_handle || private_handle == source_handle ||
        u32(context->descriptor, FRAME_FORMAT) != 103 ||
        u32(context->descriptor, FRAME_PLANE_COUNT) != 2 ||
        u32(context->descriptor, FRAME_WIDTH) != width ||
        u32(context->descriptor, FRAME_HEIGHT) != height) {
        discard(context);
        return -1;
    }

    uint8_t *source = NULL, *destination = NULL;
    uint32_t source_size = 0, destination_size = 0;
    if (context->ops->get_size(context->user, source_handle, &source_size) ||
        context->ops->get_size(context->user, private_handle, &destination_size) ||
        context->ops->map(context->user, source_handle, (void **)&source) ||
        context->ops->map(context->user, private_handle, (void **)&destination) ||
        !source || !destination || source == destination) {
        discard(context);
        return -1;
    }

    cfv_mono_frame *frame = &owned->planes;
    memset(frame, 0, sizeof *frame);
    frame->width = width;
    frame->height = height;
    frame->pixel_format_id = 103;
    uint8_t *source_y = NULL, *source_uv = NULL;
    if (plane(stock, source, source_size, FRAME_PLANE0, width, height,
              &source_y, &frame->src_y_size,
              &frame->src_y_stride) ||
        plane(stock, source, source_size, FRAME_PLANE1, width, height,
              &source_uv, &frame->src_uv_size,
              &frame->src_uv_stride) ||
        plane(context->descriptor, destination, destination_size,
              FRAME_PLANE0, width, height, &frame->dst_y,
              &frame->dst_y_size, &frame->dst_y_stride) ||
        plane(context->descriptor, destination, destination_size,
              FRAME_PLANE1, width, height, &frame->dst_uv,
              &frame->dst_uv_size, &frame->dst_uv_stride)) {
        discard(context);
        return -1;
    }

    frame->src_y = source_y;
    frame->src_uv = source_uv;

    owned->encoder_frame = context->descriptor;
    context->in_flight = 1;
    return 0;
}

static int sync_for_encoder(void *opaque, cfv_mono_owned_jpeg_frame *owned) {
    cfv_mono_vmem_context *context = opaque;
    if (!context || !owned || !context->in_flight ||
        owned->encoder_frame != context->descriptor)
        return -1;
    return context->ops->sync(context->user,
                              ptr(context->descriptor, FRAME_VMEM),
                              context->encoder_sync_mode);
}

static void release(void *opaque, cfv_mono_owned_jpeg_frame *owned) {
    cfv_mono_vmem_context *context = opaque;
    if (!context || !context->in_flight || !owned ||
        owned->encoder_frame != context->descriptor)
        return;
    discard(context);
    owned->encoder_frame = NULL;
}

const cfv_mono_jpeg_memory *cfv_mono_vmem_memory(void) {
    static const cfv_mono_jpeg_memory memory = {
        acquire, sync_for_encoder, release
    };
    return &memory;
}
