#include "cfv_mono_jpeg_bridge.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { FRAME_SIZE = 0x90, PIXEL_SIZE = 16 };

typedef struct {
    unsigned char stock[FRAME_SIZE], private_frame[FRAME_SIZE], output[FRAME_SIZE];
    unsigned char stock_pixels[PIXEL_SIZE], private_pixels[PIXEL_SIZE];
    cfv_mono_vmem_context vmem;
    cfv_mono_vmem_ops ops;
    cfv_mono_jpeg_bridge bridge;
    int calls, frees, syncs, fail_copy, vendor_return, reenter;
    int saw_private;
    const void *received_params;
} fixture;

static void put_u32(void *base, size_t off, uint32_t value) {
    memcpy((unsigned char *)base + off, &value, sizeof value);
}

static void put_ptr(void *base, size_t off, void *value) {
    memcpy((unsigned char *)base + off, &value, sizeof value);
}

static void *get_ptr(const void *base, size_t off) {
    void *value;
    memcpy(&value, (const unsigned char *)base + off, sizeof value);
    return value;
}

static int copy_frame(void *user, void *destination, const void *source,
                      int flags) {
    fixture *f = user;
    assert(flags == 7 && destination == f->private_frame && source == f->stock);
    if (f->fail_copy) return -1;
    memcpy(f->private_pixels, f->stock_pixels, PIXEL_SIZE);
    put_ptr(destination, 0x20, f->private_pixels);
    return 0;
}

static int map(void *user, void *handle, void **address) {
    fixture *f = user;
    assert(handle == f->stock_pixels || handle == f->private_pixels);
    *address = handle;
    return 0;
}

static int get_size(void *user, void *handle, uint32_t *size) {
    fixture *f = user;
    assert(handle == f->stock_pixels || handle == f->private_pixels);
    *size = PIXEL_SIZE;
    return 0;
}

static int sync_mem(void *user, void *handle, int mode) {
    fixture *f = user;
    assert((handle == f->stock_pixels && mode == 1) ||
           (handle == f->private_pixels && mode == 2));
    ++f->syncs;
    return 0;
}

static int free_frame(void *user, void *frame) {
    fixture *f = user;
    assert(frame == f->private_frame);
    ++f->frees;
    put_ptr(frame, 0x20, NULL);
    return 0;
}

static int vendor(void *engine, const void *params) {
    fixture *f = engine;
    cfv_mono_ienc_params p;
    memcpy(&p, params, sizeof p);
    f->received_params = params;
    ++f->calls;
    assert(p.output_frame == f->output && p.quality == 90 && p.reserved == 0);
    if (p.input_frame == f->private_frame) {
        f->saw_private = 1;
        assert(f->vmem.in_flight && f->frees == 0);
        assert(f->private_pixels[8] == 128 && f->private_pixels[9] == 128);
        assert(f->private_pixels[10] == 128 && f->private_pixels[11] == 128);
        if (f->reenter) {
            cfv_mono_ienc_params nested = { f->stock, f->output, 90, 0 };
            assert(cfv_mono_jpeg_bridge_encfrm(&f->bridge, f, &nested, 0) ==
                   CFV_MONO_BRIDGE_REJECTED);
            assert(f->calls == 1);
        }
    } else {
        assert(p.input_frame == f->stock);
    }
    return f->vendor_return;
}

static void setup(fixture *f) {
    memset(f, 0, sizeof *f);
    put_ptr(f->stock, 0x20, f->stock_pixels);
    put_u32(f->stock, 0x28, 103);
    put_u32(f->stock, 0x38, 4);
    put_u32(f->stock, 0x3c, 2);
    put_u32(f->stock, 0x40, 4);
    put_u32(f->stock, 0x44, 0);
    put_u32(f->stock, 0x48, 2);
    put_u32(f->stock, 0x50, 4);
    put_u32(f->stock, 0x54, 8);
    put_u32(f->stock, 0x58, 2);
    put_u32(f->stock, 0x80, 2);
    put_u32(f->output, 0x28, 8);
    for (int i = 0; i < PIXEL_SIZE; ++i) f->stock_pixels[i] = (unsigned char)(i + 16);
    f->ops.deep_copy = copy_frame;
    f->ops.map = map;
    f->ops.get_size = get_size;
    f->ops.sync = sync_mem;
    f->ops.free_frame = free_frame;
    f->vmem.descriptor = f->private_frame;
    f->vmem.descriptor_size = FRAME_SIZE;
    f->vmem.allocation_flags = 7;
    f->vmem.source_read_sync_mode = 1;
    f->vmem.encoder_sync_mode = 2;
    f->vmem.ops = &f->ops;
    f->vmem.user = f;
    cfv_mono_jpeg_bridge_init(&f->bridge, vendor, &f->vmem);
}

static void test_off_passthrough(void) {
    fixture f;
    setup(&f);
    cfv_mono_ienc_params p = { f.stock, f.output, 90, 0 };
    assert(!cfv_mono_jpeg_bridge_ready(&f.bridge));
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 0) == 0);
    assert(f.calls == 1 && f.received_params == &p && !f.saw_private);
    assert(f.frees == 0 && f.syncs == 0);
    assert(cfv_mono_jpeg_bridge_ready(&f.bridge));
}

static void test_private_frame_and_sync_lifetime(void) {
    fixture f;
    setup(&f);
    f.reenter = 1;
    cfv_mono_ienc_params p = { f.stock, f.output, 90, 0 };
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 1) == 0);
    assert(f.calls == 1 && f.saw_private && f.received_params != &p);
    assert(p.input_frame == f.stock && get_ptr(f.stock, 0x20) == f.stock_pixels);
    assert(f.frees == 1 && f.syncs == 2 && !f.vmem.in_flight);
    assert(cfv_mono_jpeg_bridge_ready(&f.bridge));
}

static void test_fail_closed(void) {
    fixture f;
    setup(&f);
    cfv_mono_ienc_params p = { f.stock, f.output, 90, 0 };
    put_u32(f.output, 0x28, 103);
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 1) == CFV_MONO_BRIDGE_REJECTED);
    assert(f.calls == 0 && f.frees == 0);
    put_u32(f.output, 0x28, 8);
    p.quality = 0;
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 1) == CFV_MONO_BRIDGE_REJECTED);
    p.quality = 90;
    f.fail_copy = 1;
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 1) == CFV_MONO_BRIDGE_REJECTED);
    assert(f.calls == 0 && !f.vmem.in_flight);
}

static void test_quarantine(void) {
    fixture f;
    setup(&f);
    f.vendor_return = -42;
    cfv_mono_ienc_params p = { f.stock, f.output, 90, 0 };
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 1) == -42);
    assert(f.calls == 1 && f.frees == 0 && f.vmem.in_flight);
    assert(f.received_params == &f.bridge.live_params);
    assert(f.bridge.live_params.input_frame == f.private_frame);
    assert(!cfv_mono_jpeg_bridge_ready(&f.bridge));
    assert(cfv_mono_jpeg_bridge_encfrm(&f.bridge, &f, &p, 0) == CFV_MONO_BRIDGE_REJECTED);
    assert(f.calls == 1);
    assert(cfv_mono_jpeg_bridge_resolve_quarantine(&f.bridge, 0) == -1);
    assert(f.frees == 0);
    assert(cfv_mono_jpeg_bridge_resolve_quarantine(&f.bridge, 1) == 1);
    assert(f.frees == 1 && !f.vmem.in_flight);
    assert(cfv_mono_jpeg_bridge_ready(&f.bridge));
}

int main(void) {
    test_off_passthrough();
    test_private_frame_and_sync_lifetime();
    test_fail_closed();
    test_quarantine();
    puts("mono JPEG bridge: OK");
    return 0;
}
