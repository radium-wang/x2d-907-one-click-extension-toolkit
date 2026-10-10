#ifndef CFV_MONO_HEIF_FORMAT_H
#define CFV_MONO_HEIF_FORMAT_H

#include <stddef.h>
#include <stdint.h>

/* Format 1003 is three 10-bit samples per 32-bit little-endian word.
 * The position of its two spare bits remains unproven on CFV firmware.
 * A caller must independently attest one layout; there is no default. */
typedef enum {
    CFV_HEIF_PACKING_UNVERIFIED = 0,
    CFV_HEIF_PACKING_SPARE_MSB = 1, /* samples at bits 0, 10, 20 */
    CFV_HEIF_PACKING_SPARE_LSB = 2  /* samples at bits 2, 12, 22 */
} cfv_heif_packing;

typedef struct {
    const uint8_t *src_y;
    const uint8_t *src_uv;
    uint8_t *dst_y;
    uint8_t *dst_uv;
    size_t width, height;
    size_t src_y_stride, src_uv_stride, dst_y_stride, dst_uv_stride;
    size_t src_y_size, src_uv_size, dst_y_size, dst_uv_size;
    cfv_heif_packing packing;
    int independently_attested;
} cfv_heif_neutralize_request;

typedef enum {
    CFV_HEIF_NEUTRAL_OK = 0,
    CFV_HEIF_NEUTRAL_UNVERIFIED = -1,
    CFV_HEIF_NEUTRAL_BAD_LAYOUT = -2,
    CFV_HEIF_NEUTRAL_BAD_SPAN = -3,
    CFV_HEIF_NEUTRAL_OVERLAP = -4
} cfv_heif_neutral_result;

/* Copies both whole source planes, including row padding, into equally
 * strided private destinations, then sets each active chroma sample to 512.
 * U/V order is immaterial because both values become neutral. Source buffers
 * and spare bits remain unchanged. No write occurs on failure. */
cfv_heif_neutral_result cfv_mono_heif_1003_neutralize(
    const cfv_heif_neutralize_request *request);

#endif
