#include "x2d_mono_heif_runtime.h"
#include <stdint.h>
#include <string.h>

enum { X2D_HEIF_FORMAT = 1003 };

static uint32_t word(const void *base, size_t offset) {
    uint32_t value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static void *handle(const void *base, size_t offset) {
    void *value;
    memcpy(&value, (const uint8_t *)base + offset, sizeof value);
    return value;
}

static void set_handle(void *base, size_t offset, void *value) {
    memcpy((uint8_t *)base + offset, &value, sizeof value);
}

static int field_fits(size_t size, size_t offset, size_t field_size) {
    return offset <= size && field_size <= size - offset;
}

static int disjoint(const void *a, size_t asize, const void *b, size_t bsize) {
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    if (!a || !b || !asize || !bsize || asize > UINTPTR_MAX - x ||
        bsize > UINTPTR_MAX - y) return 0;
    return x + asize <= y || y + bsize <= x;
}

cfv_heif_packing x2d_mono_heif_detect_packing(
    const uint8_t *uv, size_t size, size_t width, size_t rows, size_t stride) {
    if (!uv || !width || !rows || width > SIZE_MAX - 2 ||
        (width + 2) / 3 > SIZE_MAX / 4) return CFV_HEIF_PACKING_UNVERIFIED;
    size_t used = ((width + 2) / 3) * 4;
    size_t full_words = width / 3;
    if (stride < used || rows - 1 > (SIZE_MAX - stride) / stride ||
        (rows - 1) * stride + used > size ||
        full_words < 1 || rows > SIZE_MAX / full_words ||
        rows * full_words < 64) return CFV_HEIF_PACKING_UNVERIFIED;
    int low_zero = 1, high_zero = 1;
    for (size_t row = 0; row < rows; ++row) {
        const uint8_t *p = uv + row * stride;
        for (size_t i = 0; i < full_words; ++i) {
            uint32_t v = (uint32_t)p[4*i] | ((uint32_t)p[4*i+1] << 8) |
                         ((uint32_t)p[4*i+2] << 16) |
                         ((uint32_t)p[4*i+3] << 24);
            if (v & UINT32_C(0x00000003)) low_zero = 0;
            if (v & UINT32_C(0xc0000000)) high_zero = 0;
            if (!low_zero && !high_zero)
                return CFV_HEIF_PACKING_UNVERIFIED;
        }
    }
    if (high_zero && !low_zero) return CFV_HEIF_PACKING_SPARE_MSB;
    if (low_zero && !high_zero) return CFV_HEIF_PACKING_SPARE_LSB;
    return CFV_HEIF_PACKING_UNVERIFIED;
}

static int contract_verified(void *opaque) {
    const x2d_mono_heif_runtime *r = opaque;
    if (!r || !r->memory || !r->private_descriptor || r->in_flight ||
        r->poisoned || !r->contract.abi_attested ||
        !r->contract.neutral_512_attested ||
        !r->contract.completion_attested ||
        r->contract.vmem_offset != 0x20 ||
        r->contract.format_offset != 0x28 ||
        r->contract.width_offset != 0x38 ||
        r->contract.height_offset != 0x3c ||
        r->contract.plane_count_offset != 0x80 ||
        r->contract.y_plane_offset != 0x40 ||
        r->contract.uv_plane_offset != 0x50 ||
        r->contract.allocation_flags <= 0 ||
        r->contract.source_read_sync_mode <= 0 ||
        r->contract.encoder_sync_mode <= 0 ||
        !r->memory->deep_copy || !r->memory->map ||
        !r->memory->get_size || !r->memory->sync ||
        !r->memory->free_frame || !r->memory->encoder_complete)
        return 0;
    size_t n = r->contract.descriptor_size;
    return n >= 0x90 &&
           field_fits(n, r->contract.vmem_offset, sizeof(void *)) &&
           field_fits(n, r->contract.format_offset, 4) &&
           field_fits(n, r->contract.width_offset, 4) &&
           field_fits(n, r->contract.height_offset, 4) &&
           field_fits(n, r->contract.plane_count_offset, 4) &&
           field_fits(n, r->contract.y_plane_offset, 12) &&
           field_fits(n, r->contract.uv_plane_offset, 12) &&
           r->contract.y_plane_offset != r->contract.uv_plane_offset;
}

static int plane(const void *desc, size_t field, uint8_t *base,
                 size_t total, size_t required_rows, size_t required_bytes,
                 uint8_t **ptr, size_t *size, size_t *stride) {
    size_t pitch = word(desc, field);
    size_t offset = word(desc, field + 4);
    size_t rows = word(desc, field + 8);
    if (!required_rows || !pitch || pitch < required_bytes ||
        rows < required_rows || rows > SIZE_MAX / pitch ||
        offset > total || rows * pitch > total - offset)
        return -1;
    *ptr = base + offset;
    *size = rows * pitch;
    *stride = pitch;
    return 0;
}

static int discard(x2d_mono_heif_runtime *r) {
    void *h = handle(r->private_descriptor, r->contract.vmem_offset);
    if (h && r->memory->free_frame(r->user, r->private_descriptor) != 0) {
        r->poisoned = 1;
        return -1;
    }
    set_handle(r->private_descriptor, r->contract.vmem_offset, NULL);
    r->in_flight = 0;
    memset(&r->neutralize, 0, sizeof r->neutralize);
    return 0;
}

static int acquire(void *opaque, const void *stock_frame,
                   cfv_mono_heif_owned *owned) {
    x2d_mono_heif_runtime *r = opaque;
    if (!contract_verified(r) || !stock_frame || !owned ||
        r->private_descriptor == stock_frame) return -1;
    const x2d_mono_heif_contract *c = &r->contract;
    size_t width = word(stock_frame, c->width_offset);
    size_t height = word(stock_frame, c->height_offset);
    if (word(stock_frame, c->format_offset) != X2D_HEIF_FORMAT ||
        word(stock_frame, c->plane_count_offset) != 2 ||
        !width || !height || width > 20000 || height > 20000 ||
        (width & 1) || (height & 1) || width > SIZE_MAX - 2 ||
        (width + 2) / 3 > SIZE_MAX / 4) return -1;
    void *source_handle = handle(stock_frame, c->vmem_offset);
    if (!source_handle || r->memory->sync(r->user, source_handle,
                                           c->source_read_sync_mode) != 0)
        return -1;
    memcpy(r->private_descriptor, stock_frame, c->descriptor_size);
    set_handle(r->private_descriptor, c->vmem_offset, NULL);
    if (r->memory->deep_copy(r->user, r->private_descriptor, stock_frame,
                             c->allocation_flags) != 0) {
        (void)discard(r);
        return -1;
    }
    void *private_handle = handle(r->private_descriptor, c->vmem_offset);
    if (!private_handle || private_handle == source_handle ||
        word(r->private_descriptor, c->format_offset) != X2D_HEIF_FORMAT ||
        word(r->private_descriptor, c->plane_count_offset) != 2 ||
        word(r->private_descriptor, c->width_offset) != width ||
        word(r->private_descriptor, c->height_offset) != height ||
        r->memory->sync(r->user, private_handle,
                        c->source_read_sync_mode) != 0) {
        (void)discard(r);
        return -1;
    }
    uint8_t *src = NULL, *dst = NULL;
    uint32_t src_size = 0, dst_size = 0;
    if (r->memory->get_size(r->user, source_handle, &src_size) ||
        r->memory->get_size(r->user, private_handle, &dst_size) ||
        r->memory->map(r->user, source_handle, (void **)&src) ||
        r->memory->map(r->user, private_handle, (void **)&dst) ||
        !disjoint(src, src_size, dst, dst_size)) {
        (void)discard(r);
        return -1;
    }
    cfv_heif_neutralize_request q = {0};
    q.width = width;
    q.height = height;
    size_t used = ((width + 2) / 3) * 4;
    if (plane(stock_frame, c->y_plane_offset, src, src_size, height, used,
              (uint8_t **)&q.src_y, &q.src_y_size, &q.src_y_stride) ||
        plane(stock_frame, c->uv_plane_offset, src, src_size, height / 2, used,
              (uint8_t **)&q.src_uv, &q.src_uv_size, &q.src_uv_stride) ||
        plane(r->private_descriptor, c->y_plane_offset, dst, dst_size,
              height, used, &q.dst_y, &q.dst_y_size, &q.dst_y_stride) ||
        plane(r->private_descriptor, c->uv_plane_offset, dst, dst_size,
              height / 2, used, &q.dst_uv, &q.dst_uv_size,
              &q.dst_uv_stride) ||
        q.src_y_stride != q.dst_y_stride ||
        q.src_uv_stride != q.dst_uv_stride ||
        !disjoint(q.src_y, q.src_y_size, q.src_uv, q.src_uv_size) ||
        !disjoint(q.dst_y, q.dst_y_size, q.dst_uv, q.dst_uv_size)) {
        (void)discard(r);
        return -1;
    }
    /* Confirm the private copy actually contains the synchronized source.
     * A stale or partially copied VMem allocation must never be inferred as
     * a valid pixel layout. */
    for (size_t row = 0; row < height; ++row) {
        if (memcmp(q.src_y + row * q.src_y_stride,
                   q.dst_y + row * q.dst_y_stride, q.src_y_stride) != 0) {
            (void)discard(r);
            return -1;
        }
    }
    for (size_t row = 0; row < height / 2; ++row) {
        if (memcmp(q.src_uv + row * q.src_uv_stride,
                   q.dst_uv + row * q.dst_uv_stride, q.src_uv_stride) != 0) {
            (void)discard(r);
            return -1;
        }
    }
    q.packing = x2d_mono_heif_detect_packing(
        q.dst_uv, q.dst_uv_size, width, height / 2, q.dst_uv_stride);
    if (q.packing == CFV_HEIF_PACKING_UNVERIFIED) {
        (void)discard(r);
        return -1;
    }
    q.independently_attested = 1;
    r->neutralize = q;
    owned->frame = r->private_descriptor;
    owned->stock_pixels = src;
    owned->stock_size = src_size;
    owned->private_pixels = dst;
    owned->private_size = dst_size;
    r->in_flight = 1;
    return 0;
}

static int neutralize(void *opaque, cfv_mono_heif_owned *owned) {
    x2d_mono_heif_runtime *r = opaque;
    return r && r->in_flight && owned &&
           owned->frame == r->private_descriptor &&
           cfv_mono_heif_1003_neutralize(&r->neutralize) ==
               CFV_HEIF_NEUTRAL_OK ? 0 : -1;
}

static int sync_for_encoder(void *opaque, cfv_mono_heif_owned *owned) {
    x2d_mono_heif_runtime *r = opaque;
    if (!r || !r->in_flight || !owned ||
        owned->frame != r->private_descriptor) return -1;
    return r->memory->sync(r->user,
        handle(r->private_descriptor, r->contract.vmem_offset),
        r->contract.encoder_sync_mode);
}

static int completion_confirmed(void *opaque) {
    x2d_mono_heif_runtime *r = opaque;
    return r && r->in_flight && r->memory->encoder_complete(r->user) == 0
        ? 0 : -1;
}

static int release(void *opaque, cfv_mono_heif_owned *owned) {
    x2d_mono_heif_runtime *r = opaque;
    if (!r || !owned || owned->frame != r->private_descriptor ||
        !r->in_flight) return -1;
    if (discard(r) != 0) return -1;
    memset(owned, 0, sizeof *owned);
    return 0;
}

const cfv_mono_heif_ops *x2d_mono_heif_runtime_ops(void) {
    static const cfv_mono_heif_ops ops = {
        contract_verified, acquire, neutralize, sync_for_encoder,
        completion_confirmed, release
    };
    return &ops;
}

/* The preload must resolve the named stock provider; RTLD_NEXT could return
 * another interposer, including this one. Never load the observation probe
 * into this runtime module because it exports the same HAL entry point. */
#include "x2d_mono_runtime.h"
#include <stdatomic.h>
#ifndef X2D_MONO_HEIF_HOST_TEST
#include <dlfcn.h>
#include <pthread.h>
static pthread_once_t provider_once = PTHREAD_ONCE_INIT;
static void *provider;
static void open_provider(void) {
    provider = dlopen("libduml_vcodec.so", RTLD_NOW | RTLD_LOCAL);
}
static cfv_mono_heif_hal_encfrm stock_provider(void) {
    pthread_once(&provider_once, open_provider);
    void *symbol = provider ? dlsym(provider, "duss_hal_heifenc_encfrm") : NULL;
    cfv_mono_heif_hal_encfrm call = NULL;
    memcpy(&call, &symbol, sizeof call);
    return call;
}
#else
extern int x2d_mono_heif_test_stock(void *, const void *);
static cfv_mono_heif_hal_encfrm stock_provider(void) {
    return x2d_mono_heif_test_stock;
}
#endif
static cfv_mono_heif_bridge active_bridge;
static _Atomic(x2d_mono_heif_runtime *) active_runtime;

int x2d_mono_heif_bind(x2d_mono_heif_runtime *runtime) {
    if (!runtime || atomic_load(&active_runtime) ||
        !contract_verified(runtime)) return -1;
    cfv_mono_heif_hal_encfrm original = stock_provider();
    if (!original) return -1;
    cfv_mono_heif_bridge_init(&active_bridge, original,
                              x2d_mono_heif_runtime_ops(), runtime);
    atomic_store(&active_runtime, runtime);
    x2d_mono_runtime_ready(CFV_MONO_READY_HEIF, 1);
    return 0;
}

int duss_hal_heifenc_encfrm(void *engine, const void *params) {
    cfv_mono_heif_hal_encfrm original = stock_provider();
    if (!original || !engine || !params) return CFV_MONO_HEIF_REJECTED;
    x2d_mono_heif_runtime *runtime = atomic_load(&active_runtime);
    int requested = x2d_mono_runtime_requested();
    if (!requested) return original(engine, params);
    if (!runtime || !x2d_mono_runtime_enabled())
        return CFV_MONO_HEIF_REJECTED;
    int result = cfv_mono_heif_bridge_encfrm(&active_bridge, engine, params, 1);
    if (result != 0) x2d_mono_runtime_ready(CFV_MONO_READY_HEIF, 0);
    return result;
}
