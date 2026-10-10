#include "cfv_mono_heif_format.h"
#include <stdint.h>
#include <string.h>

static int row_span(size_t stride, size_t rows, size_t used, size_t size) {
    return rows && stride >= used &&
           rows - 1 <= (SIZE_MAX - used) / stride &&
           (rows - 1) * stride + used <= size;
}

static int disjoint(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (!a || !b || !an || !bn || an > UINTPTR_MAX - x ||
        bn > UINTPTR_MAX - y) return 0;
    return x + an <= y || y + bn <= x;
}

static uint32_t get_word(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void put_word(uint8_t *p, uint32_t w) {
    p[0] = (uint8_t)w;
    p[1] = (uint8_t)(w >> 8);
    p[2] = (uint8_t)(w >> 16);
    p[3] = (uint8_t)(w >> 24);
}

cfv_heif_neutral_result cfv_mono_heif_1003_neutralize(
    const cfv_heif_neutralize_request *r) {
    if (!r || !r->independently_attested ||
        r->packing == CFV_HEIF_PACKING_UNVERIFIED)
        return CFV_HEIF_NEUTRAL_UNVERIFIED;
    if (r->packing != CFV_HEIF_PACKING_SPARE_MSB &&
        r->packing != CFV_HEIF_PACKING_SPARE_LSB)
        return CFV_HEIF_NEUTRAL_BAD_LAYOUT;
    if (!r->width || !r->height || (r->width & 1) || (r->height & 1) ||
        r->width > SIZE_MAX - 2 || (r->width + 2) / 3 > SIZE_MAX / 4)
        return CFV_HEIF_NEUTRAL_BAD_SPAN;

    const size_t used = ((r->width + 2) / 3) * 4;
    const size_t chroma_rows = r->height / 2;
    if (r->src_y_stride != r->dst_y_stride ||
        r->src_uv_stride != r->dst_uv_stride ||
        !row_span(r->src_y_stride, r->height, r->src_y_stride, r->src_y_size) ||
        !row_span(r->src_uv_stride, chroma_rows, r->src_uv_stride, r->src_uv_size) ||
        !row_span(r->dst_y_stride, r->height, r->dst_y_stride, r->dst_y_size) ||
        !row_span(r->dst_uv_stride, chroma_rows, r->dst_uv_stride, r->dst_uv_size) ||
        r->src_y_stride < used || r->src_uv_stride < used)
        return CFV_HEIF_NEUTRAL_BAD_SPAN;

    if (!disjoint(r->src_y, r->src_y_size, r->src_uv, r->src_uv_size) ||
        !disjoint(r->src_y, r->src_y_size, r->dst_y, r->dst_y_size) ||
        !disjoint(r->src_y, r->src_y_size, r->dst_uv, r->dst_uv_size) ||
        !disjoint(r->src_uv, r->src_uv_size, r->dst_y, r->dst_y_size) ||
        !disjoint(r->src_uv, r->src_uv_size, r->dst_uv, r->dst_uv_size) ||
        !disjoint(r->dst_y, r->dst_y_size, r->dst_uv, r->dst_uv_size))
        return CFV_HEIF_NEUTRAL_OVERLAP;

    for (size_t row = 0; row < r->height; ++row)
        memcpy(r->dst_y + row * r->dst_y_stride,
               r->src_y + row * r->src_y_stride, r->src_y_stride);

    const unsigned base_shift = r->packing == CFV_HEIF_PACKING_SPARE_LSB ? 2 : 0;
    for (size_t row = 0; row < chroma_rows; ++row) {
        const uint8_t *src = r->src_uv + row * r->src_uv_stride;
        uint8_t *dst = r->dst_uv + row * r->dst_uv_stride;
        memcpy(dst, src, r->src_uv_stride);
        for (size_t group = 0; group < used / 4; ++group) {
            uint32_t word = get_word(src + group * 4);
            size_t active = r->width - group * 3;
            if (active > 3) active = 3;
            for (size_t slot = 0; slot < active; ++slot) {
                unsigned shift = base_shift + (unsigned)slot * 10;
                word = (word & ~(UINT32_C(0x3ff) << shift)) |
                       (UINT32_C(512) << shift);
            }
            put_word(dst + group * 4, word);
        }
    }
    return CFV_HEIF_NEUTRAL_OK;
}
