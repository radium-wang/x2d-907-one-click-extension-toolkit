#include "x2d_mono_heif_runtime.h"
#include "cfv_mono_control.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint8_t stock[768], private_pixels[768], frame[0x90], output[0x90];
static uint8_t private_frame[0x90];
static int encoder_calls, releases, stock_calls, mode_enabled, requested, ready_clears, ready_sets;
int x2d_mono_runtime_enabled(void) { return mode_enabled; }
int x2d_mono_runtime_requested(void) { return requested; }
void x2d_mono_runtime_ready(unsigned route, int ready) {
    assert(route == CFV_MONO_READY_HEIF);
    if (ready) ++ready_sets;
    else ++ready_clears;
}

static void set32(uint8_t *p, size_t offset, uint32_t v) {
    memcpy(p + offset, &v, 4);
}
static void setptr(uint8_t *p, size_t offset, void *v) {
    memcpy(p + offset, &v, sizeof v);
}
static uint32_t packed(uint32_t a, uint32_t b, uint32_t c) {
    return a | b << 10 | c << 20;
}
static void source_pattern(int ambiguous) {
    memset(stock, 0, sizeof stock);
    for (size_t r = 0; r < 2; ++r)
        for (size_t i = 0; i < 32; ++i) {
            uint32_t v = ambiguous ? 0 : packed((uint32_t)(i+1), 400, 700);
            memcpy(stock + 512 + r*128 + i*4, &v, 4);
        }
}
static int deep_copy(void *u, void *destination, const void *source, int flags) {
    (void)u; (void)source;
    assert(flags == 7);
    memcpy(private_pixels, stock, sizeof stock);
    setptr(destination, 0x20, private_pixels);
    return 0;
}
static int map(void *u, void *h, void **p) {
    (void)u; *p = h; return 0;
}
static int size(void *u, void *h, uint32_t *n) {
    (void)u;
    if (h != stock && h != private_pixels) return -1;
    *n = 768; return 0;
}
static int sync_mem(void *u, void *h, int mode) {
    (void)u;
    return (h == stock || h == private_pixels) && (mode == 3 || mode == 4)
        ? 0 : -1;
}
static int free_frame(void *u, void *f) {
    (void)u; assert(f == private_frame); ++releases; return 0;
}
static int complete(void *u) { (void)u; return 0; }
static int vendor(void *engine, const void *params) {
    (void)engine;
    const cfv_mono_heif_params *p = params;
    assert(p->input_frame == private_frame);
    assert(p->output_frame == output);
    ++encoder_calls;
    for (size_t row = 0; row < 2; ++row)
        for (size_t group = 0; group < 32; ++group) {
            uint32_t v;
            memcpy(&v, private_pixels + 512 + row*128 + group*4, 4);
            assert((v & 0x3fffffff) == packed(512, 512, 512));
        }
    return 0;
}
int x2d_mono_heif_test_stock(void *engine, const void *params) {
    const cfv_mono_heif_params *p = params;
    if (!mode_enabled) {
        assert(p->input_frame == frame);
        ++stock_calls; return 0;
    }
    return vendor(engine, params);
}
static void setup(void) {
    memset(frame, 0, sizeof frame);
    memset(private_frame, 0, sizeof private_frame);
    memset(output, 0, sizeof output);
    setptr(frame, 0x20, stock);
    set32(frame, 0x28, 1003);
    set32(frame, 0x38, 96);
    set32(frame, 0x3c, 4);
    set32(frame, 0x80, 2);
    set32(frame, 0x40, 128); set32(frame, 0x44, 0); set32(frame, 0x48, 4);
    set32(frame, 0x50, 128); set32(frame, 0x54, 512); set32(frame, 0x58, 2);
    set32(output, 0x28, 2);
    set32(output, 0x30, 96);
    set32(output, 0x34, 4);
}
int main(void) {
    setup(); source_pattern(0);
    uint8_t original[768]; memcpy(original, stock, sizeof stock);
    x2d_mono_heif_memory_ops mem = {
        deep_copy, map, size, sync_mem, free_frame, complete
    };
    x2d_mono_heif_runtime runtime = {0};
    runtime.memory = &mem;
    runtime.private_descriptor = private_frame;
    runtime.contract = (x2d_mono_heif_contract){
        .descriptor_size=sizeof frame, .vmem_offset=0x20,
        .format_offset=0x28, .width_offset=0x38, .height_offset=0x3c,
        .plane_count_offset=0x80, .y_plane_offset=0x40,
        .uv_plane_offset=0x50, .allocation_flags=7,
        .source_read_sync_mode=3, .encoder_sync_mode=4,
        .abi_attested=1, .neutral_512_attested=1,
        .completion_attested=1
    };
    assert(x2d_mono_heif_bind(&runtime) == 0);
    assert(ready_sets == 1);
    cfv_mono_heif_params params = {frame, output};
    assert(duss_hal_heifenc_encfrm(frame, &params) == 0);
    assert(stock_calls == 1 && encoder_calls == 0);
    requested = 1;
    assert(duss_hal_heifenc_encfrm(frame, &params) == CFV_MONO_HEIF_REJECTED);
    assert(stock_calls == 1 && encoder_calls == 0);
    mode_enabled = 1;
    assert(duss_hal_heifenc_encfrm(frame, &params) == 0);
    assert(encoder_calls == 1 && releases == 1);
    assert(memcmp(stock, original, sizeof stock) == 0);
    cfv_mono_heif_bridge bridge;
    cfv_mono_heif_bridge_init(&bridge, vendor,
                             x2d_mono_heif_runtime_ops(), &runtime);
    assert(cfv_mono_heif_bridge_encfrm(&bridge, frame, &params, 1) == 0);
    assert(encoder_calls == 2 && releases == 2);
    assert(memcmp(stock, original, sizeof stock) == 0);
    assert(params.input_frame == frame);
    uint8_t lsb[256] = {0};
    for (size_t row = 0; row < 2; ++row)
        for (size_t i = 0; i < 32; ++i) {
            uint32_t v = packed(512, 512, 700) << 2;
            memcpy(lsb + row*128 + i*4, &v, 4);
        }
    assert(x2d_mono_heif_detect_packing(lsb, sizeof lsb, 96, 2, 128) ==
           CFV_HEIF_PACKING_SPARE_LSB);
    source_pattern(1);
    assert(cfv_mono_heif_bridge_encfrm(&bridge, frame, &params, 1) ==
           CFV_MONO_HEIF_REJECTED);
    assert(encoder_calls == 2 && releases == 3);
    assert(duss_hal_heifenc_encfrm(frame, &params) == CFV_MONO_HEIF_REJECTED);
    assert(ready_clears == 1);
    assert(x2d_mono_heif_detect_packing(stock+512, 256, 96, 2, 128) ==
           CFV_HEIF_PACKING_UNVERIFIED);
    puts("X2D HEIF private runtime: OK (mocked vendor ABI)");
}
