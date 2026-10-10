#ifndef CFV_MONO_VENDOR_PROBE_H
#define CFV_MONO_VENDOR_PROBE_H
#include <stdint.h>

enum { CFV_MONO_PROBE_JPEG = 1, CFV_MONO_PROBE_HEIF = 2 };
typedef struct {
    uint32_t input_format, output_format;
    uint32_t width, height, output_width, output_height;
    uint32_t planes, plane0_pitch, plane1_pitch;
    int input_vmem, output_vmem;
} cfv_mono_probe_sample;
/* Fixed metadata only; no image pixels are mapped or read. */
int cfv_mono_probe_parse(int kind, const void *params,
                         cfv_mono_probe_sample *sample);
#endif
