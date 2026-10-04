#ifndef CFV_MONO_VMEM_H
#define CFV_MONO_VMEM_H

#include "cfv_mono_jpeg.h"

/* Adapter for the CFV 4.2.0 frame ABI observed in libdcam_base.so.
 * The caller supplies the full frame descriptor storage and the vendor
 * operations. This unit never hooks a service or changes camera files. */
typedef struct {
    int (*deep_copy)(void *user, void *destination, const void *source,
                     int allocation_flags);
    int (*map)(void *user, void *handle, void **address);
    int (*get_size)(void *user, void *handle, uint32_t *size);
    int (*sync)(void *user, void *handle, int mode);
    int (*free_frame)(void *user, void *frame);
} cfv_mono_vmem_ops;

typedef struct {
    void *descriptor;
    size_t descriptor_size;
    int allocation_flags;
    int source_read_sync_mode;
    int encoder_sync_mode;
    const cfv_mono_vmem_ops *ops;
    void *user;
    int in_flight;
    int poisoned;
} cfv_mono_vmem_context;

/* This memory adapter is single-flight: keep its context and descriptor
 * alive until cfv_mono_jpeg_end. A NULL result means prerequisites failed. */
const cfv_mono_jpeg_memory *cfv_mono_vmem_memory(void);

#endif
