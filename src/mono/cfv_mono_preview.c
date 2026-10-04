#include "cfv_mono_preview.h"
#include <stdint.h>
#include <string.h>

static int fits(size_t bytes, size_t rows, size_t stride, size_t size) {
    if (!rows || stride < bytes || rows - 1 > (SIZE_MAX - bytes) / stride)
        return 0;
    return (rows - 1) * stride + bytes <= size;
}
static int overlaps(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (an > UINTPTR_MAX - x || bn > UINTPTR_MAX - y) return 1;
    return x < y + bn && y < x + an;
}
cfv_mono_preview_result cfv_mono_preview_convert(
    const cfv_mono_preview_source *s, const cfv_mono_preview_private *d) {
    if (!s || !d || !s->y || !s->uv || !d->y || !d->uv ||
        !s->width || !s->height || (s->width & 1) || (s->height & 1) ||
        s->width != d->width || s->height != d->height)
        return CFV_MONO_PREVIEW_BAD_FRAME;
    if (!fits(s->width, s->height, s->y_stride, s->y_size) ||
        !fits(s->width, s->height / 2, s->uv_stride, s->uv_size) ||
        !fits(d->width, d->height, d->y_stride, d->y_size) ||
        !fits(d->width, d->height / 2, d->uv_stride, d->uv_size))
        return CFV_MONO_PREVIEW_TOO_SMALL;
    if (overlaps(s->y, s->y_size, s->uv, s->uv_size) ||
        overlaps(d->y, d->y_size, d->uv, d->uv_size) ||
        overlaps(s->y, s->y_size, d->y, d->y_size) ||
        overlaps(s->y, s->y_size, d->uv, d->uv_size) ||
        overlaps(s->uv, s->uv_size, d->y, d->y_size) ||
        overlaps(s->uv, s->uv_size, d->uv, d->uv_size))
        return CFV_MONO_PREVIEW_ALIAS;
    for (size_t row = 0; row < s->height; ++row)
        memcpy(d->y + row * d->y_stride, s->y + row * s->y_stride, s->width);
    for (size_t row = 0; row < s->height / 2; ++row)
        memset(d->uv + row * d->uv_stride, 0x80, s->width);
    return CFV_MONO_PREVIEW_OK;
}
cfv_mono_preview_result cfv_mono_preview_process(
    int enabled, const cfv_mono_preview_source *source,
    const cfv_mono_preview_ops *ops, void *user) {
    if (!enabled) return CFV_MONO_PREVIEW_OFF;
    /* The configured 4.2.0 still_4x3 liveview geometry, not a universal ABI. */
    if (!source || source->width != 1944 || source->height != 1248 ||
        !source->owner || !ops || !ops->acquire_private ||
        !ops->verify_private || !ops->sync_private ||
        !ops->present_private || !ops->release_private)
        return CFV_MONO_PREVIEW_BAD_FRAME;
    if (!source->y || !source->uv ||
        !fits(source->width, source->height, source->y_stride, source->y_size) ||
        !fits(source->width, source->height / 2,
              source->uv_stride, source->uv_size))
        return CFV_MONO_PREVIEW_TOO_SMALL;
    if (overlaps(source->y, source->y_size, source->uv, source->uv_size))
        return CFV_MONO_PREVIEW_ALIAS;
    cfv_mono_preview_private private_frame = {0};
    if (ops->acquire_private(user, source, &private_frame) != 0)
        return CFV_MONO_PREVIEW_PRIVATE_FAILED;
    if (!private_frame.owner || private_frame.owner == source->owner ||
        ops->verify_private(user, source, &private_frame) != 0) {
        ops->release_private(user, &private_frame);
        return CFV_MONO_PREVIEW_ALIAS;
    }
    cfv_mono_preview_result result = cfv_mono_preview_convert(source, &private_frame);
    if (result != CFV_MONO_PREVIEW_OK) {
        ops->release_private(user, &private_frame);
        return result;
    }
    if (ops->sync_private(user, &private_frame) != 0) {
        ops->release_private(user, &private_frame);
        return CFV_MONO_PREVIEW_SYNC_FAILED;
    }
    if (ops->present_private(user, &private_frame) != 0) {
        ops->release_private(user, &private_frame);
        return CFV_MONO_PREVIEW_PRESENT_FAILED;
    }
    return CFV_MONO_PREVIEW_OK;
}
