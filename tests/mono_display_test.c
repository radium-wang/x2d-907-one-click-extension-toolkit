#include "cfv_mono_display.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 1944u
#define H 1248u
#define YN (W * H)
#define UVN (W * H / 2u)

typedef struct {
    uint8_t *source_y, *source_uv, *private_y, *private_uv;
    int stock_capsule, private_capsule, stock_descriptor, private_descriptor;
    int stock_calls, private_calls, prepare_calls, verify_calls, sync_calls;
    int retained, discarded, faults;
    int prepare_error, verify_error, sync_error, retain_error, stock_result;
    int alias_owner;
} fixture;

static fixture *active;
static void *expected_overlay;
static int stock(void *control, void *video, const void *capsule,
                 uint32_t recommendation, const void *rectangle,
                 void *overlay) {
    fixture *f = active;
    assert(control == f);
    assert(overlay == expected_overlay);
    assert(recommendation == 7u);
    assert(rectangle == f);
    f->stock_calls++;
    assert(capsule == &f->stock_capsule);
    if (video == &f->private_descriptor)
        f->private_calls++;
    else {
        assert(video == &f->stock_descriptor);
    }
    return f->stock_result;
}
static int prepare(void *user, const void *video, const void *capsule,
                   cfv_mono_display_candidate *candidate) {
    fixture *f = user;
    assert(capsule == &f->stock_capsule);
    assert(video == &f->stock_descriptor);
    f->prepare_calls++;
    candidate->source = (cfv_mono_preview_source){
        f->source_y, f->source_uv, YN, W, UVN, W, W, H,
        &f->stock_capsule};
    candidate->private_frame = (cfv_mono_preview_private){
        f->private_y, f->private_uv, YN, W, UVN, W, W, H,
        f->alias_owner ? &f->stock_capsule : &f->private_capsule};
    candidate->private_video_frame = &f->private_descriptor;
    candidate->lease = f;
    return f->prepare_error;
}
static int verify(void *user, const cfv_mono_display_candidate *c) {
    fixture *f = user;
    f->verify_calls++;
    assert(c->source.owner != 0);
    return f->verify_error;
}
static int sync_display(void *user, cfv_mono_display_candidate *c) {
    fixture *f = user;
    f->sync_calls++;
    assert(c->private_frame.uv[0] == 0x80);
    return f->sync_error;
}
static int retain(void *user, cfv_mono_display_candidate *c) {
    fixture *f = user;
    f->retained++;
    assert(c->lease == f);
    return f->retain_error;
}
static void discard(void *user, cfv_mono_display_candidate *c) {
    fixture *f = user;
    f->discarded++;
    (void)c;
}
static void fault(void *user) { ((fixture *)user)->faults++; }
static const cfv_mono_display_ops ops = {
    prepare, verify, sync_display, retain, discard, fault};
static int run_overlay(fixture *f, int enabled, void *overlay) {
    active = f;
    expected_overlay = overlay;
    return cfv_mono_display_dispatch(enabled, stock, f,
        &f->stock_descriptor, &f->stock_capsule, 7, f, overlay, &ops, f);
}
static int run(fixture *f, int enabled) {
    return run_overlay(f, enabled, f);
}
static void reset(fixture *f) {
    f->stock_calls = f->private_calls = f->prepare_calls = 0;
    f->verify_calls = f->sync_calls = f->retained = 0;
    f->discarded = f->faults = 0;
    f->prepare_error = f->verify_error = f->sync_error = 0;
    f->retain_error = f->alias_owner = 0;
    f->stock_result = 1;
    memset(f->private_y, 0x55, YN);
    memset(f->private_uv, 0x66, UVN);
}
int main(void) {
    fixture f = {0};
    f.source_y = malloc(YN);
    f.source_uv = malloc(UVN);
    f.private_y = malloc(YN);
    f.private_uv = malloc(UVN);
    assert(f.source_y && f.source_uv && f.private_y && f.private_uv);
    memset(f.source_y, 0x39, YN);
    memset(f.source_uv, 0xab, UVN);

    reset(&f);
    assert(run(&f, 0) == 1);
    assert(f.stock_calls == 1 && f.private_calls == 0 && f.prepare_calls == 0);
    assert(f.faults == 0);

    reset(&f);
    assert(run(&f, 1) == 1);
    assert(f.stock_calls == 1 && f.private_calls == 1 && f.retained == 1);
    assert(f.discarded == 0 && f.faults == 0 && f.sync_calls == 1);
    assert(f.private_y[0] == 0x39 && f.private_uv[0] == 0x80);
    assert(f.source_uv[0] == 0xab);

    reset(&f);
    assert(run_overlay(&f, 1, NULL) == 1);
    assert(f.private_calls == 0 && f.prepare_calls == 0 && f.faults == 0);

    reset(&f);
    f.prepare_error = -1;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 1 && f.private_calls == 0 && f.faults == 1);

    reset(&f);
    f.prepare_error = CFV_MONO_DISPLAY_BUSY;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 0 && f.private_calls == 0 && f.faults == 0);

    reset(&f);
    f.alias_owner = 1;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 1 && f.private_calls == 0 && f.faults == 1);

    reset(&f);
    f.verify_error = 1;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 1 && f.private_calls == 0 && f.faults == 1);

    reset(&f);
    f.sync_error = 1;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 1 && f.private_calls == 0 && f.faults == 1);

    reset(&f);
    f.stock_result = 0;
    assert(run(&f, 1) == 0);
    assert(f.discarded == 0 && f.retained == 1 && f.faults == 1);

    reset(&f);
    f.retain_error = 1;
    assert(run(&f, 1) == 1);
    assert(f.discarded == 1 && f.retained == 1 && f.faults == 1);
    assert(f.private_calls == 0);

    free(f.source_y);
    free(f.source_uv);
    free(f.private_y);
    free(f.private_uv);
    puts("mono display dispatch: OK");
    return 0;
}
