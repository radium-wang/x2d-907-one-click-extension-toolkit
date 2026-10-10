#include "x2d_mono_preview_runtime.h"
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
    uint8_t *source_y, *source_uv, *private_y, *private_uv;
    int source_object, private_object, lut, overlay;
    int calls, private_calls, prepare_calls, retained, discarded, faults;
    int enabled, attested, ready, verify_fail;
} fixture;
static fixture *active;

int x2d_mono_runtime_enabled(void) { return active->enabled; }
void x2d_mono_runtime_ready(unsigned route, int ready) {
    assert(route == CFV_MONO_READY_PREVIEW);
    active->ready = ready;
}
static int stock(void *control, void *video, const void *lut,
                 uint32_t rec, const void *rect, void *overlay) {
    fixture *f = control;
    assert(f == active && lut == &f->lut && overlay == &f->overlay);
    assert(rect == f && rec == 7);
    assert(video == &f->source_object || video == &f->private_object);
    f->calls++;
    if (video == &f->private_object) f->private_calls++;
    return 1;
}
static int attest(void *user) { return ((fixture *)user)->attested; }
static int prepare(void *user, const void *video, const void *lut,
                   cfv_mono_display_candidate *candidate) {
    fixture *f = user;
    assert(video == &f->source_object && lut == &f->lut);
    f->prepare_calls++;
    candidate->source = (cfv_mono_preview_source){
        f->source_y, f->source_uv, Y, W, UV, W, W, H, &f->source_object};
    candidate->private_frame = (cfv_mono_preview_private){
        f->private_y, f->private_uv, Y, W, UV, W, W, H, &f->private_object};
    candidate->private_video_frame = &f->private_object;
    candidate->lease = &f->private_object;
    return 0;
}
static int verify(void *user, const cfv_mono_display_candidate *candidate) {
    (void)candidate;
    return ((fixture *)user)->verify_fail;
}
static int sync_display(void *user, cfv_mono_display_candidate *candidate) {
    (void)user;
    return candidate->private_frame.uv[0] == 0x80 ? 0 : -1;
}
static int retain(void *user, cfv_mono_display_candidate *candidate) {
    (void)candidate;
    ((fixture *)user)->retained++;
    return 0;
}
static void discard(void *user, cfv_mono_display_candidate *candidate) {
    (void)candidate;
    ((fixture *)user)->discarded++;
}
static void fault(void *user) { ((fixture *)user)->faults++; }
static int invoke(fixture *f) {
    return x2d_mono_preview_handle_buf(f, &f->source_object, &f->lut,
                                        7, f, &f->overlay);
}
int main(void) {
    fixture f = {0};
    active = &f;
    f.source_y = malloc(Y);
    f.source_uv = malloc(UV);
    f.private_y = malloc(Y);
    f.private_uv = malloc(UV);
    assert(f.source_y && f.source_uv && f.private_y && f.private_uv);
    memset(f.source_y, 0x31, Y);
    memset(f.source_uv, 0xab, UV);
    memset(f.private_y, 0x55, Y);
    memset(f.private_uv, 0x66, UV);
    x2d_mono_preview_bind(stock, NULL, NULL);
    f.enabled = 1;
    assert(invoke(&f) == 1 && f.private_calls == 0 && f.ready == 0);
    x2d_mono_preview_vendor vendor = {
        .display = {prepare, verify, sync_display, retain, discard, fault},
        .attest_target_route = attest
    };
    x2d_mono_preview_bind(stock, &vendor, &f);
    assert(invoke(&f) == 1 && f.private_calls == 0 && f.ready == 0);
    f.attested = 1;
    f.enabled = 0;
    assert(invoke(&f) == 1 && f.private_calls == 0 && f.ready == 1);
    f.enabled = 1;
    assert(invoke(&f) == 1 && f.private_calls == 1 && f.retained == 1);
    assert(f.private_y[0] == 0x31 && f.private_uv[0] == 0x80);
    assert(f.source_uv[0] == 0xab && f.faults == 0);
    f.verify_fail = 1;
    assert(invoke(&f) == 1 && f.private_calls == 1);
    assert(f.discarded == 1 && f.faults == 1 && f.ready == 0);
    assert(invoke(&f) == 1 && f.private_calls == 1);
    free(f.source_y); free(f.source_uv);
    free(f.private_y); free(f.private_uv);
    puts("x2d mono preview runtime: OK");
    return 0;
}
