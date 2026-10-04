#include "cfv_mono_vendor_probe.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

static uint32_t read_u32(const void *base, size_t offset) {
    uint32_t value;
    memcpy(&value, (const unsigned char *)base + offset, sizeof value);
    return value;
}
static void *read_ptr(const void *base, size_t offset) {
    void *value;
    memcpy(&value, (const unsigned char *)base + offset, sizeof value);
    return value;
}
int cfv_mono_probe_parse(int kind, const void *params,
                         cfv_mono_probe_sample *sample) {
    if ((kind != CFV_MONO_PROBE_JPEG && kind != CFV_MONO_PROBE_HEIF) ||
        !params || !sample) return -1;
    void *input = read_ptr(params, 0);
    void *output = read_ptr(params, 8);
    if (!input || !output || input == output) return -1;
    memset(sample, 0, sizeof *sample);
    sample->input_format = read_u32(input, 0x28);
    sample->output_format = read_u32(output, 0x28);
    sample->width = read_u32(input, 0x38);
    sample->height = read_u32(input, 0x3c);
    sample->output_width = read_u32(output, 0x30);
    sample->output_height = read_u32(output, 0x34);
    sample->planes = read_u32(input, 0x80);
    sample->plane0_pitch = read_u32(input, 0x40);
    sample->plane1_pitch = read_u32(input, 0x50);
    sample->input_vmem = read_ptr(input, 0x20) != NULL;
    sample->output_vmem = read_ptr(output, 0x20) != NULL;
    if (!sample->width || !sample->height ||
        sample->width > 20000 || sample->height > 20000 ||
        sample->planes > 3) return -1;
    return 0;
}

#ifndef CFV_MONO_PROBE_CORE_ONLY
#include <dlfcn.h>
#include <stdatomic.h>
#include <stdlib.h>
#ifndef CFV_MONO_PROBE_HOST_TEST
#include <pthread.h>
#endif
#ifdef CFV_MONO_PROBE_HOST_TEST
#define ANDROID_LOG_ERROR 6
#define ANDROID_LOG_WARN 5
#define ANDROID_LOG_INFO 4
static int __android_log_print(int priority, const char *tag, const char *format, ...) {
    (void)priority; (void)tag; (void)format; return 0;
}
#else
#include <android/log.h>
#endif

typedef int (*encoder_call)(void *engine, const void *params);
static atomic_uint jpeg_seen, heif_seen;

#ifdef CFV_MONO_PROBE_HOST_TEST
extern int cfv_mono_probe_test_jpeg(void *, const void *);
extern int cfv_mono_probe_test_heif(void *, const void *);
static encoder_call original(const char *name) {
    return !strcmp(name, "duss_hal_ienc_encfrm") ? cfv_mono_probe_test_jpeg :
           !strcmp(name, "duss_hal_heifenc_encfrm") ? cfv_mono_probe_test_heif : NULL;
}
#else
static pthread_once_t provider_once = PTHREAD_ONCE_INIT;
static void *provider;
static void open_provider(void) {
    /* The verified stock provider is a dependency of both encoder plugins. */
    provider = dlopen("libduml_vcodec.so", RTLD_NOW | RTLD_LOCAL);
}
static encoder_call original(const char *name) {
    /* Resolve from the named stock provider, never from our own preload. */
    pthread_once(&provider_once, open_provider);
    void *symbol = provider ? dlsym(provider, name) : NULL;
    encoder_call call = NULL;
    memcpy(&call, &symbol, sizeof call);
    return call;
}
#endif
static int observe_and_forward(int kind, void *engine, const void *params,
                               const char *symbol, atomic_uint *counter) {
    encoder_call call = original(symbol);
    if (!call) {
        __android_log_print(ANDROID_LOG_ERROR, "CFVMonoProbe",
                            "%s unavailable; stock call not made", symbol);
        return -1;
    }
    unsigned index = atomic_fetch_add(counter, 1);
    if (index < 8) {
        const char *metadata_opt_in = getenv("CFV_MONO_PROBE_META");
        if (!metadata_opt_in || strcmp(metadata_opt_in, "1")) {
            __android_log_print(ANDROID_LOG_INFO, "CFVMonoProbe",
                                "kind=%d reached; metadata disabled", kind);
            return call(engine, params);
        }
        cfv_mono_probe_sample sample;
        if (!cfv_mono_probe_parse(kind, params, &sample))
            __android_log_print(ANDROID_LOG_INFO, "CFVMonoProbe",
                "kind=%d in=%u out=%u size=%ux%u outsize=%ux%u planes=%u pitch=%u,%u vmem=%d,%d",
                kind, sample.input_format, sample.output_format,
                sample.width, sample.height, sample.output_width,
                sample.output_height, sample.planes, sample.plane0_pitch,
                sample.plane1_pitch, sample.input_vmem, sample.output_vmem);
        else
            __android_log_print(ANDROID_LOG_WARN, "CFVMonoProbe",
                                "kind=%d metadata unavailable", kind);
    }
    return call(engine, params);
}
int duss_hal_ienc_encfrm(void *engine, const void *params) {
    return observe_and_forward(CFV_MONO_PROBE_JPEG, engine, params,
                               "duss_hal_ienc_encfrm", &jpeg_seen);
}
int duss_hal_heifenc_encfrm(void *engine, const void *params) {
    return observe_and_forward(CFV_MONO_PROBE_HEIF, engine, params,
                               "duss_hal_heifenc_encfrm", &heif_seen);
}
#endif
