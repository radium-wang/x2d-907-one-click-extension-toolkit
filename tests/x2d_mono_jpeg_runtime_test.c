#include "x2d_mono_jpeg_runtime.h"
#include "x2d_mono_runtime.h"
#include "cfv_mono_jpeg_bridge.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static unsigned char input[0x90], output[0x90], private_frame[0x90];
static unsigned char input_pixels[16], private_pixels[16];
static int enabled, requested, ready, calls, frees, vendor_result, quiescent;

static void put_u32(void *p, size_t offset, uint32_t v) {
    memcpy((unsigned char *)p + offset, &v, sizeof v);
}
static void put_ptr(void *p, size_t offset, void *v) {
    memcpy((unsigned char *)p + offset, &v, sizeof v);
}
static int copy(void *user, void *dst, const void *src, int flags) {
    (void)user;
    assert(dst == private_frame && src == input && flags == 7);
    memcpy(private_pixels, input_pixels, sizeof private_pixels);
    put_ptr(dst, 0x20, private_pixels);
    return 0;
}
static int map(void *user, void *handle, void **address) {
    (void)user;
    *address = handle;
    return 0;
}
static int size(void *user, void *handle, uint32_t *length) {
    (void)user;
    assert(handle == input_pixels || handle == private_pixels);
    *length = 16;
    return 0;
}
static int sync_mem(void *user, void *handle, int mode) {
    (void)user;
    assert((handle == input_pixels && mode == 1) ||
           (handle == private_pixels && mode == 2));
    return 0;
}
static int free_frame(void *user, void *frame) {
    (void)user;
    assert(frame == private_frame);
    ++frees;
    put_ptr(frame, 0x20, NULL);
    return 0;
}
static int is_quiescent(void *user) { (void)user; return quiescent; }
int x2d_mono_runtime_enabled(void) { return enabled; }
int x2d_mono_runtime_requested(void) { return requested; }
void x2d_mono_runtime_ready(unsigned route, int state) {
    assert(route == CFV_MONO_READY_JPEG);
    ready = state;
}
int x2d_mono_jpeg_host_stock(void *engine, const void *params) {
    (void)engine;
    cfv_mono_ienc_params p;
    memcpy(&p, params, sizeof p);
    assert(p.output_frame == output);
    if (enabled) {
        assert(p.input_frame == private_frame);
        assert(private_pixels[8] == 128 && private_pixels[9] == 128);
        assert(private_pixels[10] == 128 && private_pixels[11] == 128);
    } else {
        assert(p.input_frame == input);
    }
    ++calls;
    return vendor_result;
}

int main(void) {
    put_ptr(input, 0x20, input_pixels);
    put_u32(input, 0x28, 103);
    put_u32(input, 0x38, 4);
    put_u32(input, 0x3c, 2);
    put_u32(input, 0x40, 4);
    put_u32(input, 0x44, 0);
    put_u32(input, 0x48, 2);
    put_u32(input, 0x50, 4);
    put_u32(input, 0x54, 8);
    put_u32(input, 0x58, 2);
    put_u32(input, 0x80, 2);
    put_u32(output, 0x28, 8);
    for (unsigned i = 0; i < 16; ++i) input_pixels[i] = (unsigned char)i;
    cfv_mono_ienc_params p = {input, output, 90, 0};
    assert(duss_hal_ienc_encfrm(input, &p) == 0 && calls == 1 && !ready);
    requested = enabled = 1;
    assert(duss_hal_ienc_encfrm(input, &p) == CFV_MONO_BRIDGE_REJECTED);
    assert(calls == 1 && !ready);
    requested = enabled = 0;
    x2d_mono_jpeg_contract contract = {0};
    contract.ops = (cfv_mono_vmem_ops){copy, map, size, sync_mem, free_frame};
    contract.private_descriptor = private_frame;
    contract.descriptor_size = sizeof private_frame;
    contract.allocation_flags = 7;
    contract.source_read_sync_mode = 1;
    contract.encoder_sync_mode = 2;
    contract.encoder_quiescent = is_quiescent;
    assert(x2d_mono_jpeg_bind(&contract) == -1);
    contract.success_means_completed = 1;
    assert(x2d_mono_jpeg_bind(&contract) == 0);
    assert(x2d_mono_jpeg_bind(&contract) == -1);
    assert(ready && !x2d_mono_jpeg_ready());
    requested = 1;
    assert(duss_hal_ienc_encfrm(input, &p) == CFV_MONO_BRIDGE_REJECTED);
    assert(calls == 1);
    requested = 0;
    assert(duss_hal_ienc_encfrm(input, &p) == 0 && calls == 2 && ready);
    requested = enabled = 1;
    assert(duss_hal_ienc_encfrm(input, &p) == 0 && calls == 3 && ready);
    assert(frees == 1 && p.input_frame == input);
    vendor_result = -42;
    assert(duss_hal_ienc_encfrm(input, &p) == -42 && calls == 4);
    assert(frees == 1 && !ready);
    requested = 1; enabled = 0;
    assert(duss_hal_ienc_encfrm(input, &p) == CFV_MONO_BRIDGE_REJECTED);
    assert(calls == 4);
    assert(x2d_mono_jpeg_recover() == -1 && frees == 1);
    quiescent = 1;
    assert(x2d_mono_jpeg_recover() == 1 && frees == 2);
    puts("x2d JPEG runtime: OK");
    return 0;
}
