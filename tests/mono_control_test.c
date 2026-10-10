#include "cfv_mono_control.h"
#include "cfv_mono_pref.h"
#include <assert.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    assert(argc == 3);
    const char *feature = argv[1], *preference = argv[2];
    cfv_mono_control control;
    char output[512];
    cfv_mono_control_init(&control, feature, preference);
    assert(!cfv_mono_control_effective(&control));
    assert(cfv_mono_control_request(&control, "POST", "/mono/enable",
                                    output, sizeof output) == 503);
    assert(strstr(output, "\"state\":\"not_installed\"") != NULL);

    int file = open(feature, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    assert(file >= 0 && write(file, "1\n", 2) == 2);
    assert(close(file) == 0);
    cfv_mono_control_set_ready(&control, CFV_MONO_READY_PREVIEW, 1);
    cfv_mono_control_set_ready(&control, CFV_MONO_READY_JPEG, 1);
    assert(cfv_mono_control_request(&control, "POST", "/mono/enable",
                                    output, sizeof output) == 503);
    assert(!cfv_mono_control_effective(&control));
    cfv_mono_control_set_ready(&control, CFV_MONO_READY_HEIF, 1);
    assert(cfv_mono_control_request(&control, "POST", "/mono/enable",
                                    output, sizeof output) == 200);
    assert(cfv_mono_control_effective(&control));
    assert(cfv_mono_control_requested(&control));
    assert(strstr(output, "\"effective\":true") != NULL);
    assert(cfv_mono_control_request(&control, "GET", "/mono/status",
                                    output, sizeof output) == 200);
    assert(strstr(output, "\"selected\":true") != NULL);

    cfv_mono_control next_process;
    cfv_mono_control_init(&next_process, feature, preference);
    assert(!cfv_mono_control_effective(&next_process));
    cfv_mono_control_set_ready(&next_process, CFV_MONO_READY_ALL, 1);
    assert(cfv_mono_control_effective(&next_process));
    cfv_mono_control_set_ready(&next_process, CFV_MONO_READY_JPEG, 0);
    assert(!cfv_mono_control_effective(&next_process));
    assert(cfv_mono_control_requested(&next_process));
    assert(cfv_mono_control_request(&next_process, "POST", "/mono/disable",
                                    output, sizeof output) == 200);
    assert(!cfv_mono_pref_load(feature, preference));
    assert(cfv_mono_control_request(&next_process, "POST", "/mono/enable",
                                    output, sizeof output) == 503);

    cfv_mono_control_set_ready(&next_process, CFV_MONO_READY_JPEG, 1);
    assert(cfv_mono_control_request(&next_process, "POST", "/mono/enable",
                                    output, sizeof output) == 200);
    assert(cfv_mono_pref_clear(feature, preference) == 0);
    assert(!cfv_mono_control_effective(&next_process));
    assert(cfv_mono_control_request(&next_process, "GET", "/mono/status",
                                    output, sizeof output) == 200);
    assert(strstr(output, "\"state\":\"not_installed\"") != NULL);
    assert(cfv_mono_control_request(&next_process, "POST", "/mono/enable",
                                    output, sizeof output) == 503);
    assert(cfv_mono_control_request(&next_process, "DELETE", "/mono/status",
                                    output, sizeof output) == 404);
    return 0;
}
