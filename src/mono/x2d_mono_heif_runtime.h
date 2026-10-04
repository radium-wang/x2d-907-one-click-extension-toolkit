#ifndef X2D_MONO_HEIF_RUNTIME_H
#define X2D_MONO_HEIF_RUNTIME_H

#include "cfv_mono_heif_bridge.h"
#include "cfv_mono_heif_format.h"

/* Bind only to the exact X2D 100C 4.2.0 ABI. Missing attestation leaves
 * monochrome HEIF unavailable. One private frame lives through encoding. */
typedef struct {
    int (*deep_copy)(void *, void *destination, const void *source, int flags);
    int (*map)(void *, void *handle, void **address);
    int (*get_size)(void *, void *handle, uint32_t *size);
    int (*sync)(void *, void *handle, int mode);
    int (*free_frame)(void *, void *frame);
    int (*encoder_complete)(void *);
} x2d_mono_heif_memory_ops;

typedef struct {
    size_t descriptor_size;
    size_t vmem_offset, format_offset, width_offset, height_offset;
    size_t plane_count_offset, y_plane_offset, uv_plane_offset;
    /* At each plane offset: pitch, byte offset, row count, as uint32_t. */
    int allocation_flags, source_read_sync_mode, encoder_sync_mode;
    int abi_attested, neutral_512_attested, completion_attested;
} x2d_mono_heif_contract;

typedef struct {
    const x2d_mono_heif_memory_ops *memory;
    void *user;
    void *private_descriptor;
    x2d_mono_heif_contract contract;
    cfv_heif_neutralize_request neutralize;
    int in_flight, poisoned;
} x2d_mono_heif_runtime;

/* Call only with a mapped, CPU-synchronized private UV plane and a checked
 * span. At least 64 complete words are required. Ambiguity is rejected. */
cfv_heif_packing x2d_mono_heif_detect_packing(
    const uint8_t *uv, size_t size, size_t width, size_t rows, size_t stride);

const cfv_mono_heif_ops *x2d_mono_heif_runtime_ops(void);

/* Register the reviewed private-memory contract at camera-service startup.
 * The stock provider stays active until this succeeds. */
int x2d_mono_heif_bind(x2d_mono_heif_runtime *runtime);
int duss_hal_heifenc_encfrm(void *engine, const void *params);

#endif
