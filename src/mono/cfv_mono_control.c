#include "cfv_mono_control.h"
#include "cfv_mono_pref.h"
#include <stdio.h>
#include <string.h>

void cfv_mono_control_init(cfv_mono_control *control,
                           const char *feature_path,
                           const char *preference_path) {
    if (!control) return;
    control->feature_path = feature_path;
    control->preference_path = preference_path;
    atomic_store(&control->ready_mask, 0);
    atomic_store(&control->selected,
                 cfv_mono_pref_load(feature_path, preference_path));
}

void cfv_mono_control_set_ready(cfv_mono_control *control,
                                unsigned route, int ready) {
    if (!control || !route || (route & ~CFV_MONO_READY_ALL)) return;
    if (ready) atomic_fetch_or(&control->ready_mask, route);
    else atomic_fetch_and(&control->ready_mask, ~route);
}

int cfv_mono_control_requested(const cfv_mono_control *control) {
    return control && cfv_mono_feature_available(control->feature_path) &&
           atomic_load(&control->selected);
}

int cfv_mono_control_effective(const cfv_mono_control *control) {
    return cfv_mono_control_requested(control) &&
           atomic_load(&control->ready_mask) == CFV_MONO_READY_ALL;
}

int cfv_mono_control_request(cfv_mono_control *control,
                             const char *method, const char *path,
                             char *output, size_t output_size) {
    if (!control || !method || !path || !output || output_size < 256)
        return 500;
    unsigned mask = atomic_load(&control->ready_mask);
    int available = cfv_mono_feature_available(control->feature_path);
    int selected = available && atomic_load(&control->selected);
    int status = 200;
    if (!strcmp(method, "POST") && !strcmp(path, "/mono/enable")) {
        if (!available || mask != CFV_MONO_READY_ALL) status = 503;
        else if (cfv_mono_pref_save(control->preference_path, 1)) status = 500;
        else { atomic_store(&control->selected, 1); selected = 1; }
    } else if (!strcmp(method, "POST") && !strcmp(path, "/mono/disable")) {
        if (!available) status = 503;
        else if (cfv_mono_pref_save(control->preference_path, 0)) status = 500;
        else { atomic_store(&control->selected, 0); selected = 0; }
    } else if (strcmp(method, "GET") || strcmp(path, "/mono/status")) {
        status = 404;
    }
    const int complete = available && mask == CFV_MONO_READY_ALL;
    int length = snprintf(output, output_size,
        "{\"ok\":%s,\"available\":%s,\"previewReady\":%s,\"jpegReady\":%s,"
        "\"heifReady\":%s,\"selected\":%s,\"effective\":%s,"
        "\"state\":\"%s\"}\n",
        status == 200 ? "true" : "false",
        available ? "true" : "false",
        mask & CFV_MONO_READY_PREVIEW ? "true" : "false",
        mask & CFV_MONO_READY_JPEG ? "true" : "false",
        mask & CFV_MONO_READY_HEIF ? "true" : "false",
        selected ? "true" : "false",
        selected && complete ? "true" : "false",
        !available ? "not_installed" :
        mask != CFV_MONO_READY_ALL ? "routes_unavailable" :
        selected ? "monochrome" : "color");
    return length > 0 && (size_t)length < output_size ? status : 500;
}
