#include "cfv_mono_heif_bridge.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { FRAME_SIZE = 0x90, PIXELS = 32 };
typedef struct {
    unsigned char stock[FRAME_SIZE], private_frame[FRAME_SIZE];
    unsigned char output[FRAME_SIZE], stock_pixels[PIXELS];
    unsigned char private_pixels[PIXELS];
    cfv_mono_heif_bridge bridge;
    cfv_mono_heif_ops ops;
    int contract, calls, acquires, neutralizes, syncs, releases;
    int complete, vendor_result, alias, reenter;
    const void *last_params;
} fixture;

static void put_u32(void *base, size_t off, uint32_t value) {
    memcpy((unsigned char *)base + off, &value, sizeof value);
}
static void put_ptr(void *base, size_t off, void *value) {
    memcpy((unsigned char *)base + off, &value, sizeof value);
}

static int contract_verified(void *user) {
    return ((fixture *)user)->contract;
}
static int acquire(void *user, const void *stock,
                   cfv_mono_heif_owned *owned) {
    fixture *f = user;
    assert(stock == f->stock);
    ++f->acquires;
    memcpy(f->private_frame, f->stock, FRAME_SIZE);
    memcpy(f->private_pixels, f->stock_pixels, PIXELS);
    put_ptr(f->private_frame, 0x20,
            f->alias ? f->stock_pixels : f->private_pixels);
    owned->frame = f->private_frame;
    owned->stock_pixels = f->stock_pixels;
    owned->stock_size = PIXELS;
    owned->private_pixels = f->alias ? f->stock_pixels : f->private_pixels;
    owned->private_size = PIXELS;
    return 0;
}
static int neutralize_verified(void *user, cfv_mono_heif_owned *owned) {
    fixture *f = user;
    ++f->neutralizes;
    assert(owned->private_pixels == f->private_pixels);
    /* This fixture is deliberately not a format-1003 converter. A real
     * neutralizer cannot be supplied until its bit layout is proven. */
    f->private_pixels[11] = 0x80;
    return 0;
}
static int sync_for_encoder(void *user, cfv_mono_heif_owned *owned) {
    fixture *f = user;
    assert(owned->frame == f->private_frame);
    ++f->syncs;
    return 0;
}
static int completion_confirmed(void *user) {
    return ((fixture *)user)->complete ? 0 : -1;
}
static int release(void *user, cfv_mono_heif_owned *owned) {
    fixture *f = user;
    assert(owned->frame == f->private_frame);
    ++f->releases;
    return 0;
}
static int vendor(void *engine, const void *params) {
    fixture *f = engine;
    cfv_mono_heif_params p;
    memcpy(&p, params, sizeof p);
    ++f->calls;
    f->last_params = params;
    assert(p.output_frame == f->output);
    if (p.input_frame == f->private_frame) {
        assert(f->private_pixels[11] == 0x80);
        assert(f->releases == 0);
        if (f->reenter) {
            cfv_mono_heif_params nested = { f->stock, f->output };
            assert(cfv_mono_heif_bridge_encfrm(&f->bridge, f, &nested, 0) ==
                   CFV_MONO_HEIF_REJECTED);
            assert(f->calls == 1);
        }
    } else {
        assert(p.input_frame == f->stock);
    }
    return f->vendor_result;
}
static void setup(fixture *f) {
    memset(f, 0, sizeof *f);
    put_ptr(f->stock, 0x20, f->stock_pixels);
    put_ptr(f->private_frame, 0x20, f->private_pixels);
    put_u32(f->stock, 0x28, 1003);
    put_u32(f->stock, 0x38, 8);
    put_u32(f->stock, 0x3c, 4);
    put_u32(f->output, 0x28, 2);
    put_u32(f->output, 0x30, 8);
    put_u32(f->output, 0x34, 4);
    for (int i = 0; i < PIXELS; ++i)
        f->stock_pixels[i] = (unsigned char)(i + 20);
    f->ops.contract_verified = contract_verified;
    f->ops.acquire = acquire;
    f->ops.neutralize_verified = neutralize_verified;
    f->ops.sync_for_encoder = sync_for_encoder;
    f->ops.completion_confirmed = completion_confirmed;
    f->ops.release = release;
    f->contract = 1;
    f->complete = 1;
    cfv_mono_heif_bridge_init(&f->bridge, vendor, &f->ops, f);
}

static void test_original_off(void) {
    fixture f;
    setup(&f);
    cfv_mono_heif_params p = { f.stock, f.output };
    assert(!cfv_mono_heif_bridge_available(&f.bridge));
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 0) == 0);
    assert(f.calls == 1 && f.last_params == &p);
    assert(f.acquires == 0 && f.neutralizes == 0);
    assert(cfv_mono_heif_bridge_available(&f.bridge));
}
static void test_no_verified_layout_refuses(void) {
    fixture f;
    setup(&f);
    cfv_mono_heif_params p = { f.stock, f.output };
    f.contract = 0;
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) ==
           CFV_MONO_HEIF_REJECTED);
    assert(f.calls == 0 && f.acquires == 0 && !cfv_mono_heif_bridge_available(&f.bridge));
    f.contract = 1;
    f.ops.neutralize_verified = NULL;
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) ==
           CFV_MONO_HEIF_REJECTED);
    assert(f.calls == 0);
}
static void test_private_success(void) {
    fixture f;
    setup(&f);
    f.reenter = 1;
    cfv_mono_heif_params p = { f.stock, f.output };
    unsigned char before[PIXELS];
    memcpy(before, f.stock_pixels, sizeof before);
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) == 0);
    assert(f.calls == 1 && f.last_params == &f.bridge.live_params);
    assert(f.acquires == 1 && f.neutralizes == 1 && f.syncs == 1 &&
           f.releases == 1);
    assert(!memcmp(before, f.stock_pixels, sizeof before));
    assert(p.input_frame == f.stock && cfv_mono_heif_bridge_available(&f.bridge));
}
static void test_bad_format_or_alias_refuses(void) {
    fixture f;
    setup(&f);
    cfv_mono_heif_params p = { f.stock, f.output };
    put_u32(f.stock, 0x28, 2);
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) ==
           CFV_MONO_HEIF_REJECTED);
    assert(f.acquires == 0 && f.calls == 0);
    put_u32(f.stock, 0x28, 1003);
    f.alias = 1;
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) ==
           CFV_MONO_HEIF_REJECTED);
    assert(f.acquires == 1 && f.neutralizes == 0 && f.releases == 1 && f.calls == 0);
}
static void test_ambiguous_completion_quarantines(void) {
    fixture f;
    setup(&f);
    f.complete = 0;
    cfv_mono_heif_params p = { f.stock, f.output };
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) == 0);
    assert(f.calls == 1 && f.releases == 0 && !cfv_mono_heif_bridge_available(&f.bridge));
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 0) ==
           CFV_MONO_HEIF_REJECTED);
    assert(cfv_mono_heif_bridge_resolve_quarantine(&f.bridge, 0) == -1);
    assert(f.releases == 0);
    assert(cfv_mono_heif_bridge_resolve_quarantine(&f.bridge, 1) == 1);
    assert(f.releases == 1 && cfv_mono_heif_bridge_available(&f.bridge));
}
static void test_vendor_failure_quarantines(void) {
    fixture f;
    setup(&f);
    f.vendor_result = -42;
    cfv_mono_heif_params p = { f.stock, f.output };
    assert(cfv_mono_heif_bridge_encfrm(&f.bridge, &f, &p, 1) == -42);
    assert(f.releases == 0 && !cfv_mono_heif_bridge_available(&f.bridge));
    assert(cfv_mono_heif_bridge_resolve_quarantine(&f.bridge, 1) == 1);
    assert(f.releases == 1);
}
int main(void) {
    test_original_off();
    test_no_verified_layout_refuses();
    test_private_success();
    test_bad_format_or_alias_refuses();
    test_ambiguous_completion_quarantines();
    test_vendor_failure_quarantines();
    puts("mono HEIF bridge: OK (mocked neutralizer only)");
    return 0;
}
