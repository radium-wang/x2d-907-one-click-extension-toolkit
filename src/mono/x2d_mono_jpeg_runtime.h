#ifndef X2D_MONO_JPEG_RUNTIME_H
#define X2D_MONO_JPEG_RUNTIME_H
#include "cfv_mono_vmem.h"
#include <stddef.h>

/* Supplied only after target-specific review of the actual X2D 4.2.0 ABI.
 * Storage and callback user must remain valid for the process lifetime. */
typedef struct {
    cfv_mono_vmem_ops ops;
    void *vendor_user;
    void *private_descriptor;
    size_t descriptor_size;
    int allocation_flags;
    int source_read_sync_mode;
    int encoder_sync_mode;
    int success_means_completed;
    int (*encoder_quiescent)(void *user);
    void *quiescence_user;
} x2d_mono_jpeg_contract;

/* A one-time bind. The runtime copies the ops and refuses incomplete values.
 * No arbitrary stock encoder pointer is accepted: the implementation resolves
 * duss_hal_ienc_encfrm from the named stock libduml_vcodec.so provider. */
int x2d_mono_jpeg_bind(const x2d_mono_jpeg_contract *contract);
int x2d_mono_jpeg_ready(void);
int x2d_mono_jpeg_recover(void);
int duss_hal_ienc_encfrm(void *engine, const void *params);
#endif
