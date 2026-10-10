#include "cfv_mono_heif_format.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t word(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static void write_word(unsigned char *p, uint32_t w) {
    for (int i = 0; i < 4; ++i) p[i] = (unsigned char)(w >> (i * 8));
}
static uint32_t pack(uint16_t a, uint16_t b, uint16_t c, unsigned shift,
                     uint32_t spare) {
    return spare | ((uint32_t)a << shift) |
           ((uint32_t)b << (shift + 10)) |
           ((uint32_t)c << (shift + 20));
}

static void exercise(cfv_heif_packing packing) {
    unsigned char y[2][12], uv[12], private_y[2][12], private_uv[12];
    memset(y, 0xa5, sizeof y);
    memset(private_y, 0xc9, sizeof private_y);
    memset(private_uv, 0xc9, sizeof private_uv);
    const unsigned shift = packing == CFV_HEIF_PACKING_SPARE_LSB ? 2 : 0;
    const uint32_t spare = shift ? 3u : 0xc0000000u;
    /* Fixed vectors keep the test independent of the pack() helper below. */
    write_word(uv, shift ? UINT32_C(0x4b38402b) : UINT32_C(0xd2ce100a));
    write_word(uv + 4, pack(44, 66, 88, shift, spare));
    uv[8] = uv[9] = uv[10] = uv[11] = 0xd1;
    unsigned char stock_before[sizeof uv];
    memcpy(stock_before, uv, sizeof uv);
    cfv_heif_neutralize_request r = {
        .src_y = &y[0][0], .src_uv = uv,
        .dst_y = &private_y[0][0], .dst_uv = private_uv,
        .width = 4, .height = 2,
        .src_y_stride = 12, .src_uv_stride = 12,
        .dst_y_stride = 12, .dst_uv_stride = 12,
        .src_y_size = sizeof y, .src_uv_size = sizeof uv,
        .dst_y_size = sizeof private_y, .dst_uv_size = sizeof private_uv,
        .packing = packing, .independently_attested = 1
    };
    assert(cfv_mono_heif_1003_neutralize(&r) == CFV_HEIF_NEUTRAL_OK);
    assert(!memcmp(stock_before, uv, sizeof uv));
    assert(!memcmp(y[0], private_y[0], 8));
    assert(!memcmp(y[1], private_y[1], 8));
    assert(private_y[0][8] == 0xa5 && private_y[1][11] == 0xa5);
    assert(word(private_uv) ==
           (shift ? UINT32_C(0x80200803) : UINT32_C(0xe0080200)));
    assert(word(private_uv + 4) == pack(512, 66, 88, shift, spare));
    assert(private_uv[8] == 0xd1);

    memset(private_y, 0xc9, sizeof private_y);
    memset(private_uv, 0xc9, sizeof private_uv);
    r.independently_attested = 0;
    assert(cfv_mono_heif_1003_neutralize(&r) == CFV_HEIF_NEUTRAL_UNVERIFIED);
    assert(private_y[0][0] == 0xc9 && private_uv[0] == 0xc9);
    r.independently_attested = 1;
    r.packing = (cfv_heif_packing)99;
    assert(cfv_mono_heif_1003_neutralize(&r) == CFV_HEIF_NEUTRAL_BAD_LAYOUT);
    assert(private_y[0][0] == 0xc9 && private_uv[0] == 0xc9);
    r.packing = packing;
    r.dst_uv_size = 7;
    assert(cfv_mono_heif_1003_neutralize(&r) == CFV_HEIF_NEUTRAL_BAD_SPAN);
    assert(private_y[0][0] == 0xc9 && private_uv[0] == 0xc9);
    r.dst_uv_size = sizeof private_uv;
    r.dst_uv = uv;
    assert(cfv_mono_heif_1003_neutralize(&r) == CFV_HEIF_NEUTRAL_OVERLAP);
    assert(private_y[0][0] == 0xc9);
}

int main(void) {
    exercise(CFV_HEIF_PACKING_SPARE_MSB);
    exercise(CFV_HEIF_PACKING_SPARE_LSB);
    puts("mono HEIF format-1003 neutralizer: OK (conditional layouts)");
    return 0;
}
