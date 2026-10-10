#include "x2d_mono_preview_pool_adapter.h"
#include "x2d_mono_runtime.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 1944u
#define H 1248u
#define Y (W * H)
#define UV (Y / 2u)

typedef struct {
    x2d_mono_preview_pool_adapter adapter;
    uint8_t *source_y, *source_uv, *private_y, *private_uv;
    int stock_obj, private_obj, stock_handle, private_handle;
    int lut, overlay, wl_buffer, eagle_buffer, lease;
    int enabled, attested, ready, allocs, private_calls, stock_calls;
    int faults, frees, releases, destroys;
} fixture;
static fixture *active;
int x2d_mono_runtime_enabled(void) { return active->enabled; }
void x2d_mono_runtime_ready(unsigned route, int ready) {
    assert(route == CFV_MONO_READY_PREVIEW);
    active->ready = ready;
}
static int map_source(void *user, const void *object,
                      cfv_mono_preview_source *source) {
    fixture *f = user;
    assert(object == &f->stock_obj);
    *source = (cfv_mono_preview_source){
        f->source_y, f->source_uv, Y, W, UV, W, W, H, &f->stock_handle};
    return 0;
}
static int verify_private(void *user, const cfv_mono_display_candidate *c) {
    fixture *f = user;
    return c->source.owner == &f->stock_handle &&
           c->private_frame.owner == &f->private_handle &&
           c->source.y != c->private_frame.y ? 0 : -1;
}
static int sync_private(void *user, cfv_mono_preview_private *frame) {
    (void)user;
    return frame->uv[0] == 0x80 ? 0 : -1;
}
static int attest(void *user) { return ((fixture *)user)->attested; }
static void fault(void *user) { ((fixture *)user)->faults++; }
static void free_lease(void *user, void *lease) {
    fixture *f = user;
    assert(lease == &f->lease);
    f->frees++;
}
static x2d_mono_wayland_buffer_pair stock_alloc(void *control,
                                                 const void *frame,
                                                 uint32_t recommendation) {
    fixture *f = control;
    assert(frame == &f->private_obj && recommendation == 7);
    f->allocs++;
    return (x2d_mono_wayland_buffer_pair){&f->wl_buffer, &f->eagle_buffer};
}
static int stock_handle(void *control, void *video, const void *lut,
                        uint32_t recommendation, const void *rect,
                        void *overlay) {
    fixture *f = control;
    assert(lut == &f->lut && rect == f && overlay == &f->overlay);
    assert(recommendation == 7);
    f->stock_calls++;
    if (video == &f->private_obj) {
        f->private_calls++;
        if (!f->allocs) {
            x2d_mono_wayland_buffer_pair pair =
                x2d_mono_wayland_alloc_interpose(f, video, recommendation);
            assert(pair.wl_buffer == &f->wl_buffer);
        }
    } else assert(video == &f->stock_obj);
    return 1;
}
static void stock_release(void *control, void *buffer) {
    fixture *f = control;
    assert(buffer == &f->wl_buffer);
    f->releases++;
}
static void stock_destroy(void *buffer) {
    fixture *f = active;
    assert(buffer == &f->wl_buffer);
    f->destroys++;
}
int main(void) {
    fixture f = {0};
    active = &f;
    f.source_y = malloc(Y); f.source_uv = malloc(UV);
    f.private_y = malloc(Y); f.private_uv = malloc(UV);
    assert(f.source_y && f.source_uv && f.private_y && f.private_uv);
    memset(f.source_y, 0x35, Y);
    memset(f.source_uv, 0xb5, UV);
    memset(f.private_y, 0x55, Y);
    memset(f.private_uv, 0x66, UV);
    assert(x2d_mono_preview_pool_adapter_init(&f.adapter,
        &(x2d_mono_preview_pool_vendor_ops){map_source, verify_private,
            sync_private, attest, fault}, &f) == 0);
    assert(x2d_mono_preview_pool_adapter_bind(&f.adapter, stock_handle,
        stock_alloc, stock_release, stock_destroy) == -1);
    cfv_mono_preview_private frame = {
        f.private_y, f.private_uv, Y, W, UV, W, W, H, &f.private_handle};
    assert(x2d_mono_preview_pool_adapter_add_slot(&f.adapter,
        &f.private_obj, &frame, &f.lease, free_lease, &f) == 0);
    assert(x2d_mono_preview_pool_adapter_bind(&f.adapter, stock_handle,
        stock_alloc, stock_release, stock_destroy) == 0);
    f.enabled = f.attested = 1;
    for (int i = 0; i < 50; ++i) {
        assert(x2d_mono_preview_handle_buf(&f, &f.stock_obj, &f.lut,
                                            7, &f, &f.overlay) == 1);
        assert(f.private_calls == i + 1);
        assert(f.private_y[0] == 0x35 && f.private_uv[0] == 0x80);
        assert(f.source_uv[0] == 0xb5);
        x2d_mono_buffer_release_interpose(&f, &f.wl_buffer);
    }
    assert(f.allocs == 1 && f.releases == 50);
    assert(f.faults == 0 && f.ready == 1);
    /* A busy one-slot pool forwards stock for this frame, then resumes. */
    assert(x2d_mono_preview_handle_buf(&f, &f.stock_obj, &f.lut,
                                        7, &f, &f.overlay) == 1);
    assert(f.private_calls == 51);
    assert(x2d_mono_preview_handle_buf(&f, &f.stock_obj, &f.lut,
                                        7, &f, &f.overlay) == 1);
    assert(f.private_calls == 51 && f.stock_calls == 52);
    assert(f.faults == 0 && f.ready == 1);
    assert(f.frees == 0);
    x2d_mono_buffer_release_interpose(&f, &f.wl_buffer);
    assert(x2d_mono_preview_handle_buf(&f, &f.stock_obj, &f.lut,
                                        7, &f, &f.overlay) == 1);
    assert(f.private_calls == 52 && f.faults == 0);
    x2d_mono_buffer_release_interpose(&f, &f.wl_buffer);
    x2d_mono_preview_pool_adapter_retire(&f.adapter);
    assert(f.ready == 0 && f.frees == 0);
    wl_proxy_destroy(&f.wl_buffer);
    assert(f.frees == 1 && f.destroys == 1);
    assert(x2d_mono_wayland_pool_destroy(&f.adapter.pool) == 0);
    free(f.source_y); free(f.source_uv);
    free(f.private_y); free(f.private_uv);
    puts("x2d mono preview pool adapter: OK");
    return 0;
}
