#include "cfv_mono_vendor_probe.h"
#include <assert.h>
#include <stdint.h>
#include <string.h>
static void u32(unsigned char *base, size_t offset, uint32_t value) {
    memcpy(base + offset, &value, sizeof value);
}
static void ptr(unsigned char *base, size_t offset, void *value) {
    memcpy(base + offset, &value, sizeof value);
}
static int jpeg_calls, heif_calls;
int cfv_mono_probe_test_jpeg(void *engine, const void *params) {
    assert(engine == (void *)(uintptr_t)0x1111 && params); jpeg_calls++; return 42;
}
int cfv_mono_probe_test_heif(void *engine, const void *params) {
    assert(engine == (void *)(uintptr_t)0x2222 && params); heif_calls++; return 73;
}
extern int duss_hal_ienc_encfrm(void *, const void *);
extern int duss_hal_heifenc_encfrm(void *, const void *);
int main(void) {
    unsigned char input[0x90] = {0}, output[0x90] = {0};
    unsigned char original[0x90];
    void *args[2] = {input, output};
    cfv_mono_probe_sample sample;
    u32(input, 0x28, 103); u32(output, 0x28, 8);
    u32(input, 0x38, 11656); u32(input, 0x3c, 8742);
    u32(output, 0x30, 11656); u32(output, 0x34, 8742);
    u32(input, 0x80, 2); u32(input, 0x40, 11664); u32(input, 0x50, 11664);
    ptr(input, 0x20, (void *)(uintptr_t)0x1234);
    ptr(output, 0x20, (void *)(uintptr_t)0x5678);
    memcpy(original, input, sizeof input);
    assert(cfv_mono_probe_parse(CFV_MONO_PROBE_JPEG, args, &sample) == 0);
    assert(sample.input_format == 103 && sample.output_format == 8);
    assert(sample.width == 11656 && sample.height == 8742);
    assert(sample.plane0_pitch == 11664 && sample.planes == 2);
    assert(sample.input_vmem && sample.output_vmem);
    assert(memcmp(original, input, sizeof input) == 0);
    assert(duss_hal_ienc_encfrm((void *)(uintptr_t)0x1111, args) == 42);
    assert(jpeg_calls == 1 && heif_calls == 0);
    u32(input, 0x28, 1003); u32(output, 0x28, 2);
    assert(cfv_mono_probe_parse(CFV_MONO_PROBE_HEIF, args, &sample) == 0);
    assert(sample.input_format == 1003 && sample.output_format == 2);
    assert(duss_hal_heifenc_encfrm((void *)(uintptr_t)0x2222, args) == 73);
    assert(jpeg_calls == 1 && heif_calls == 1);
    args[1] = input;
    assert(cfv_mono_probe_parse(CFV_MONO_PROBE_HEIF, args, &sample) == -1);
    args[1] = output;
    u32(input, 0x38, 0);
    assert(cfv_mono_probe_parse(CFV_MONO_PROBE_JPEG, args, &sample) == -1);
    return 0;
}
