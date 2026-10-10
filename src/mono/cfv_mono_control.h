#ifndef CFV_MONO_CONTROL_H
#define CFV_MONO_CONTROL_H

#include <stddef.h>
#include <stdatomic.h>

enum {
    CFV_MONO_READY_PREVIEW = 1,
    CFV_MONO_READY_JPEG = 2,
    CFV_MONO_READY_HEIF = 4,
    CFV_MONO_READY_ALL = 7
};

typedef struct {
    const char *feature_path;
    const char *preference_path;
    atomic_uint ready_mask;
    atomic_int selected;
} cfv_mono_control;

/* Initialize after camera-service startup. Read the on/off choice from the
 * persistent camera-data area; no output path is enabled until all three
 * image routes independently report that their hooks are active. */
void cfv_mono_control_init(cfv_mono_control *control,
                           const char *feature_path,
                           const char *preference_path);
void cfv_mono_control_set_ready(cfv_mono_control *control,
                                unsigned route, int ready);
int cfv_mono_control_requested(const cfv_mono_control *control);
int cfv_mono_control_effective(const cfv_mono_control *control);

/* Fixed loopback protocol used by X2dMonoController.qml. Return HTTP status
 * code and write one JSON object to `output`; no request text reaches a shell.
 * Disable remains possible after an image-route failure. */
int cfv_mono_control_request(cfv_mono_control *control,
                             const char *method, const char *path,
                             char *output, size_t output_size);

#endif
