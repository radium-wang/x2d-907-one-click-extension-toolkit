#include "cfv_mono.h"
#include "cfv_mono_jpeg.h"
#include "cfv_mono_vmem.h"
#include <assert.h>
#include <string.h>

static void test_8bit(void) {
    uint8_t sy[12] = {16, 32, 64, 96, 0xa1, 0xa1, 100, 120, 140, 160, 0xa2, 0xa2};
    uint8_t suv[12] = {1, 2, 3, 4, 0xb1, 0xb1, 5, 6, 7, 8, 0xb2, 0xb2};
    uint8_t sy_before[12], suv_before[12], dy[12], duv[12];
    memcpy(sy_before, sy, sizeof sy); memcpy(suv_before, suv, sizeof suv);
    memset(dy, 0xee, sizeof dy); memset(duv, 0xee, sizeof duv);
    cfv_mono_frame f = {sy,12,6,suv,12,6,dy,12,6,duv,12,6,4,2,103};
    assert(cfv_mono_yuv8_sp422(&f) == CFV_MONO_OK);
    assert(memcmp(sy, sy_before, sizeof sy) == 0);
    assert(memcmp(suv, suv_before, sizeof suv) == 0);
    for (size_t row=0; row<2; ++row) {
        assert(memcmp(dy+row*6, sy+row*6, 4) == 0);
        for (size_t col=0; col<4; ++col) assert(duv[row*6+col] == 0x80);
        assert(dy[row*6+4] == 0xee && dy[row*6+5] == 0xee);
        assert(duv[row*6+4] == 0xee && duv[row*6+5] == 0xee);
    }
    f.dst_y = sy;
    assert(cfv_mono_yuv8_sp422(&f) == CFV_MONO_OVERLAP);
    assert(memcmp(sy, sy_before, sizeof sy) == 0);
    f.dst_y = dy; f.dst_uv_size = 3;
    assert(cfv_mono_yuv8_sp422(&f) == CFV_MONO_BUFFER_TOO_SMALL);
    f.dst_uv_size = 12; f.pixel_format_id = 1003;
    memset(dy, 0xee, sizeof dy); memset(duv, 0xee, sizeof duv);
    assert(cfv_mono_yuv8_sp422(&f) == CFV_MONO_BAD_ARGUMENT);
    for (size_t i=0; i<sizeof dy; ++i) assert(dy[i] == 0xee);
    for (size_t i=0; i<sizeof duv; ++i) assert(duv[i] == 0xee);
}

typedef struct { const void *received; unsigned calls; } fake_encoder_state;

static int fake_encode(void *context, const void *frame) {
    fake_encoder_state *state = context;
    state->received = frame;
    ++state->calls;
    return 17;
}

static void test_jpeg_selection(void) {
    uint8_t source_y[8] = {20, 30, 40, 50, 60, 70, 80, 90};
    uint8_t source_uv[8] = {10, 200, 30, 220, 40, 240, 60, 250};
    uint8_t original_uv[8];
    uint8_t private_y[8] = {0};
    uint8_t private_uv[8] = {0};
    int stock_handle = 1, private_handle = 2;
    memcpy(original_uv, source_uv, sizeof source_uv);
    cfv_mono_jpeg_request request = {
        {source_y,8,4,source_uv,8,4,private_y,8,4,private_uv,8,4,4,2,103},
        &stock_handle, &private_handle
    };
    fake_encoder_state state = {0};
    cfv_mono_jpeg_result result = cfv_mono_encode_jpeg(&request, 0, fake_encode, &state);
    assert(result.preparation == CFV_MONO_OK && result.encoder_called);
    assert(result.encoder_result == 17 && state.received == &stock_handle);
    assert(state.calls == 1);
    assert(memcmp(source_uv, original_uv, sizeof source_uv) == 0);

    result = cfv_mono_encode_jpeg(&request, 1, fake_encode, &state);
    assert(result.preparation == CFV_MONO_OK && result.encoder_called);
    assert(state.received == &private_handle && state.calls == 2);
    assert(memcmp(private_y, source_y, sizeof source_y) == 0);
    for (size_t i = 0; i < sizeof private_uv; ++i) assert(private_uv[i] == 0x80);
    assert(memcmp(source_uv, original_uv, sizeof source_uv) == 0);

    request.planes.pixel_format_id = 1003;
    state.received = NULL;
    result = cfv_mono_encode_jpeg(&request, 1, fake_encode, &state);
    assert(result.preparation == CFV_MONO_BAD_ARGUMENT && !result.encoder_called);
    assert(state.calls == 2 && state.received == NULL);

    request.planes.pixel_format_id = 103;
    request.private_encoder_frame = request.stock_encoder_frame;
    result = cfv_mono_encode_jpeg(&request, 1, fake_encode, &state);
    assert(result.preparation == CFV_MONO_BAD_ARGUMENT && !result.encoder_called);
    assert(state.calls == 2);
}

typedef struct {
    fake_encoder_state encoder;
    unsigned acquires;
    unsigned releases;
    unsigned syncs;
    int acquire_fails;
    int sync_fails;
    uint32_t format;
    uint8_t source_y[4];
    uint8_t source_uv[4];
    uint8_t private_y[4];
    uint8_t private_uv[4];
    int private_handle;
} owned_test_state;

static int acquire_private(void *context, const void *stock,
                           cfv_mono_owned_jpeg_frame *frame) {
    owned_test_state *state = context;
    (void)stock;
    ++state->acquires;
    if (state->acquire_fails) return -1;
    frame->planes = (cfv_mono_frame){
        state->source_y,4,4,state->source_uv,4,4,
        state->private_y,4,4,state->private_uv,4,4,4,1,state->format
    };
    frame->encoder_frame = &state->private_handle;
    return 0;
}

static void release_private(void *context, cfv_mono_owned_jpeg_frame *frame) {
    owned_test_state *state = context;
    assert(frame->encoder_frame == &state->private_handle);
    ++state->releases;
}

static int sync_private(void *context, cfv_mono_owned_jpeg_frame *frame) {
    owned_test_state *state = context;
    assert(frame->encoder_frame == &state->private_handle);
    ++state->syncs;
    return state->sync_fails ? -1 : 0;
}

static void test_owned_jpeg_lifetime(void) {
    int stock_handle = 1;
    owned_test_state state = {
        .format = 103,
        .source_y = {16, 32, 64, 96},
        .source_uv = {10, 240, 30, 220}
    };
    cfv_mono_jpeg_memory memory = {acquire_private, sync_private, release_private};
    cfv_mono_jpeg_ticket ticket;
    cfv_mono_result result = cfv_mono_jpeg_begin(
        &stock_handle, 0, &memory, &state, &ticket);
    assert(result == CFV_MONO_OK && ticket.encoder_frame == &stock_handle);
    assert(state.acquires == 0 && state.syncs == 0 && state.releases == 0);
    cfv_mono_jpeg_end(&ticket);
    assert(state.releases == 0);

    result = cfv_mono_jpeg_begin(
        &stock_handle, 1, &memory, &state, &ticket);
    assert(result == CFV_MONO_OK && ticket.encoder_frame == &state.private_handle);
    assert(state.acquires == 1 && state.syncs == 1 && state.releases == 0);
    cfv_mono_jpeg_end(&ticket);
    assert(state.acquires == 1 && state.releases == 1);
    assert(memcmp(state.private_y, state.source_y, 4) == 0);
    for (size_t i=0; i<4; ++i) assert(state.private_uv[i] == 0x80);
    assert(state.source_uv[0] == 10 && state.source_uv[1] == 240);

    state.format = 1003;
    result = cfv_mono_jpeg_begin(
        &stock_handle, 1, &memory, &state, &ticket);
    assert(result == CFV_MONO_BAD_ARGUMENT && ticket.encoder_frame == NULL);
    assert(state.acquires == 2 && state.syncs == 1 && state.releases == 2);

    state.acquire_fails = 1;
    result = cfv_mono_jpeg_begin(
        &stock_handle, 1, &memory, &state, &ticket);
    assert(result == CFV_MONO_PRIVATE_BUFFER_FAILED && ticket.encoder_frame == NULL);
    assert(state.acquires == 3 && state.releases == 2);

    state.acquire_fails = 0;
    state.format = 103;
    state.sync_fails = 1;
    result = cfv_mono_jpeg_begin(
        &stock_handle, 1, &memory, &state, &ticket);
    assert(result == CFV_MONO_SYNC_FAILED && ticket.encoder_frame == NULL);
    assert(state.acquires == 4 && state.syncs == 2 && state.releases == 3);

    state.sync_fails = 0;
    assert(cfv_mono_jpeg_begin(&stock_handle, 1, &memory, &state, &ticket) == CFV_MONO_OK);
    assert(ticket.encoder_frame == &state.private_handle);
    assert(state.acquires == 5 && state.syncs == 3 && state.releases == 3);
    /* The frame remains owned while an asynchronous encoder consumes it. */
    cfv_mono_jpeg_end(&ticket);
    assert(state.releases == 4 && ticket.encoder_frame == NULL);
    cfv_mono_jpeg_end(&ticket);
    assert(state.releases == 4);
}

typedef struct {
    uint8_t source[8], private_pixels[8];
    int source_handle, private_handle;
    unsigned copies, frees, source_syncs, destination_syncs;
    int fail_copy, fail_sync, fail_source_sync, fail_free;
} vmem_test_state;

static void write32(uint8_t *base, size_t at, uint32_t value) {
    memcpy(base + at, &value, sizeof value);
}

static void writeptr(uint8_t *base, size_t at, void *value) {
    memcpy(base + at, &value, sizeof value);
}

static void frame_layout(uint8_t *frame, void *handle) {
    memset(frame, 0, 0x90);
    writeptr(frame, 0x20, handle);
    write32(frame, 0x28, 103);
    write32(frame, 0x38, 4);
    write32(frame, 0x3c, 1);
    write32(frame, 0x40, 4);
    write32(frame, 0x44, 0);
    write32(frame, 0x48, 1);
    write32(frame, 0x50, 4);
    write32(frame, 0x54, 4);
    write32(frame, 0x58, 1);
    write32(frame, 0x80, 2);
}

static int fake_deep_copy(void *opaque, void *destination,
                          const void *source, int flags) {
    vmem_test_state *state = opaque;
    (void)source;
    assert(flags == 0x13);
    ++state->copies;
    writeptr(destination, 0x20, &state->private_handle);
    memcpy(state->private_pixels, state->source, sizeof state->source);
    return state->fail_copy ? -1 : 0;
}

static int fake_map(void *opaque, void *handle, void **mapped) {
    vmem_test_state *state = opaque;
    if (handle == &state->source_handle) *mapped = state->source;
    else if (handle == &state->private_handle) *mapped = state->private_pixels;
    else return -1;
    return 0;
}

static int fake_size(void *opaque, void *handle, uint32_t *size) {
    vmem_test_state *state = opaque;
    if (handle != &state->source_handle &&
        handle != &state->private_handle) return -1;
    *size = sizeof state->source;
    return 0;
}

static int fake_sync(void *opaque, void *handle, int mode) {
    vmem_test_state *state = opaque;
    if (handle == &state->source_handle && mode == 1) {
        ++state->source_syncs;
        return state->fail_source_sync ? -1 : 0;
    }
    assert(handle == &state->private_handle && mode == 2);
    ++state->destination_syncs;
    return state->fail_sync ? -1 : 0;
}

static int fake_free(void *opaque, void *frame) {
    vmem_test_state *state = opaque;
    void *handle = NULL;
    memcpy(&handle, (uint8_t *)frame + 0x20, sizeof handle);
    assert(handle == &state->private_handle);
    ++state->frees;
    if (state->fail_free) return -1;
    writeptr(frame, 0x20, NULL);
    return 0;
}

static void test_vmem_adapter(void) {
    vmem_test_state state = {
        .source = {16, 32, 64, 96, 11, 200, 44, 220}
    };
    uint8_t original[8];
    memcpy(original, state.source, sizeof original);
    uint8_t stock[0x90], private_frame[0x90];
    frame_layout(stock, &state.source_handle);
    cfv_mono_vmem_ops ops = {
        fake_deep_copy, fake_map, fake_size, fake_sync, fake_free
    };
    cfv_mono_vmem_context context = {
        private_frame, sizeof private_frame, 0x13, 1, 2, &ops, &state, 0, 0
    };
    cfv_mono_jpeg_ticket ticket;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) == CFV_MONO_OK);
    assert(ticket.encoder_frame == private_frame && context.in_flight);
    assert(state.copies == 1 && state.source_syncs == 1 &&
           state.destination_syncs == 1 && state.frees == 0);
    assert(memcmp(state.source, original, sizeof original) == 0);
    assert(memcmp(state.private_pixels, original, 4) == 0);
    for (size_t i=4; i<8; ++i) assert(state.private_pixels[i] == 0x80);
    cfv_mono_jpeg_ticket concurrent;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &concurrent) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.frees == 0);
    cfv_mono_jpeg_end(&ticket);
    assert(state.frees == 1 && !context.in_flight);

    state.fail_sync = 1;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) == CFV_MONO_SYNC_FAILED);
    assert(state.frees == 2 && !context.in_flight);
    state.fail_sync = 0;
    state.fail_copy = 1;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.frees == 3 && !context.in_flight);
    state.fail_copy = 0;
    state.fail_source_sync = 1;
    const unsigned copies_before_source_failure = state.copies;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.copies == copies_before_source_failure && state.frees == 3);
    state.fail_source_sync = 0;
    write32(stock, 0x54, 8);
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.frees == 4 && !context.in_flight);
    assert(memcmp(state.source, original, sizeof original) == 0);

    context.allocation_flags = 0;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.copies == 4);
    context.allocation_flags = 0x13;

    write32(stock, 0x54, 4);
    state.fail_free = 1;
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) == CFV_MONO_OK);
    cfv_mono_jpeg_end(&ticket);
    assert(context.poisoned && state.frees == 5);
    assert(cfv_mono_jpeg_begin(stock, 1, cfv_mono_vmem_memory(),
                               &context, &ticket) ==
           CFV_MONO_PRIVATE_BUFFER_FAILED);
    assert(state.copies == 5);
}

int main(void) {
    test_8bit();
    test_jpeg_selection();
    test_owned_jpeg_lifetime();
    test_vmem_adapter();
    return 0;
}
