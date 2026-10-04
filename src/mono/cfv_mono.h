#ifndef CFV_MONO_H
#define CFV_MONO_H
#include <stddef.h>
#include <stdint.h>

/* Host-tested, out-of-place YUV desaturation. Pixel layout must be verified on
 * the actual CFV before integration. The functions never allocate memory. */
typedef enum {
    CFV_MONO_OK = 0,
    CFV_MONO_BAD_ARGUMENT = 1,
    CFV_MONO_BUFFER_TOO_SMALL = 2,
    CFV_MONO_OVERLAP = 3,
    CFV_MONO_PRIVATE_BUFFER_FAILED = 4,
    CFV_MONO_SYNC_FAILED = 5
} cfv_mono_result;

typedef struct {
    const uint8_t *src_y;
    size_t src_y_size;
    size_t src_y_stride;
    const uint8_t *src_uv;
    size_t src_uv_size;
    size_t src_uv_stride;
    uint8_t *dst_y;
    size_t dst_y_size;
    size_t dst_y_stride;
    uint8_t *dst_uv;
    size_t dst_uv_size;
    size_t dst_uv_stride;
    size_t width;
    size_t height;
    uint32_t pixel_format_id;
} cfv_mono_frame;

/* Accepts only DUSS_PIXFMT_YUV8_SP422_YUV (103).
 * Neutral chroma is 0x80. Y is copied byte-for-byte. */
cfv_mono_result cfv_mono_yuv8_sp422(const cfv_mono_frame *frame);

#endif
