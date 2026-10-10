#ifndef CFV_MONO_PREVIEW_H
#define CFV_MONO_PREVIEW_H
#include <stddef.h>
#include <stdint.h>

typedef enum {
    CFV_MONO_PREVIEW_OK = 0,
    CFV_MONO_PREVIEW_OFF,
    CFV_MONO_PREVIEW_BAD_FRAME,
    CFV_MONO_PREVIEW_TOO_SMALL,
    CFV_MONO_PREVIEW_ALIAS,
    CFV_MONO_PREVIEW_PRIVATE_FAILED,
    CFV_MONO_PREVIEW_SYNC_FAILED,
    CFV_MONO_PREVIEW_PRESENT_FAILED
} cfv_mono_preview_result;

typedef struct {
    const uint8_t *y, *uv;
    size_t y_size, y_stride, uv_size, uv_stride, width, height;
    const void *owner; /* Original VMem handle, never writable here. */
} cfv_mono_preview_source;

typedef struct {
    uint8_t *y, *uv;
    size_t y_size, y_stride, uv_size, uv_stride, width, height;
    void *owner;
} cfv_mono_preview_private;

/* Out-of-place YUV8 SP420. Neutral chroma is 0x80. Padding is untouched.
 * The source and destination planes must be completely disjoint. */
cfv_mono_preview_result cfv_mono_preview_convert(
    const cfv_mono_preview_source *source,
    const cfv_mono_preview_private *private_frame);

typedef struct {
    /* Must allocate fresh pixels, not just a new descriptor/shadow alias. */
    int (*acquire_private)(void *user, const cfv_mono_preview_source *source,
                           cfv_mono_preview_private *private_frame);
    /* Must attest that the two VMem handles do not alias physical pixels. */
    int (*verify_private)(void *user, const cfv_mono_preview_source *source,
                          const cfv_mono_preview_private *private_frame);
    int (*sync_private)(void *user, cfv_mono_preview_private *private_frame);
    /* Success transfers ownership until the original Wayland release event. */
    int (*present_private)(void *user, cfv_mono_preview_private *private_frame);
    void (*release_private)(void *user, cfv_mono_preview_private *private_frame);
} cfv_mono_preview_ops;

/* Guarded bridge. Any failure leaves stock display fallback to caller.
 * It does not know the vendor duss_object/FrameData ABI or install a hook.
 * An adapter must preserve the stock display LUT and QML overlays. */
cfv_mono_preview_result cfv_mono_preview_process(
    int enabled, const cfv_mono_preview_source *source,
    const cfv_mono_preview_ops *ops, void *user);
#endif
