#include "cfv_mono.h"
#include <stdint.h>
#include <string.h>

static int span_fits(size_t width_bytes, size_t rows, size_t stride,
                     size_t declared_size) {
    if (rows == 0 || stride < width_bytes) return 0;
    if (rows - 1 > (SIZE_MAX - width_bytes) / stride) return 0;
    return (rows - 1) * stride + width_bytes <= declared_size;
}

static int overlaps(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (an > UINTPTR_MAX - x || bn > UINTPTR_MAX - y) return 1;
    return x < y + bn && y < x + an;
}

static cfv_mono_result validate(const cfv_mono_frame *f, size_t bytes_per_y,
                                size_t chroma_rows) {
    if (!f || !f->src_y || !f->src_uv || !f->dst_y || !f->dst_uv ||
        f->width == 0 || f->height == 0 || (f->width & 1) ||
        bytes_per_y == 0 || f->width > SIZE_MAX / bytes_per_y)
        return CFV_MONO_BAD_ARGUMENT;
    const size_t row_bytes = f->width * bytes_per_y;
    if (!span_fits(row_bytes, f->height, f->src_y_stride, f->src_y_size) ||
        !span_fits(row_bytes, f->height, f->dst_y_stride, f->dst_y_size) ||
        !span_fits(row_bytes, chroma_rows, f->src_uv_stride, f->src_uv_size) ||
        !span_fits(row_bytes, chroma_rows, f->dst_uv_stride, f->dst_uv_size))
        return CFV_MONO_BUFFER_TOO_SMALL;
    if (overlaps(f->src_y, f->src_y_size, f->dst_y, f->dst_y_size) ||
        overlaps(f->src_y, f->src_y_size, f->dst_uv, f->dst_uv_size) ||
        overlaps(f->src_uv, f->src_uv_size, f->dst_y, f->dst_y_size) ||
        overlaps(f->src_uv, f->src_uv_size, f->dst_uv, f->dst_uv_size) ||
        overlaps(f->dst_y, f->dst_y_size, f->dst_uv, f->dst_uv_size))
        return CFV_MONO_OVERLAP;
    return CFV_MONO_OK;
}

static void copy_y(const cfv_mono_frame *f, size_t row_bytes) {
    for (size_t row = 0; row < f->height; ++row)
        memcpy(f->dst_y + row * f->dst_y_stride,
               f->src_y + row * f->src_y_stride, row_bytes);
}

cfv_mono_result cfv_mono_yuv8_sp422(const cfv_mono_frame *f) {
    if (!f || f->pixel_format_id != 103) return CFV_MONO_BAD_ARGUMENT;
    cfv_mono_result result = validate(f, 1, f ? f->height : 0);
    if (result != CFV_MONO_OK) return result;
    copy_y(f, f->width);
    for (size_t row = 0; row < f->height; ++row)
        memset(f->dst_uv + row * f->dst_uv_stride, 0x80, f->width);
    return CFV_MONO_OK;
}
