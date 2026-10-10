#include "cfv_mono_pref.h"
#include <stdio.h>
#include <string.h>

/* Separate invocations simulate a service process being stopped and started.
 * No camera path is opened: callers pass paths in a temporary test directory. */
int main(int argc, char **argv) {
    if (argc < 4) return 2;
    if (strcmp(argv[1], "read") == 0)
        return cfv_mono_pref_load(argv[2], argv[3]) ? 0 : 1;
    if (strcmp(argv[1], "on") == 0)
        return cfv_mono_pref_save(argv[3], 1) == 0 ? 0 : 2;
    if (strcmp(argv[1], "off") == 0)
        return cfv_mono_pref_save(argv[3], 0) == 0 ? 0 : 2;
    if (strcmp(argv[1], "restore") == 0)
        return cfv_mono_pref_clear(argv[2], argv[3]) == 0 ? 0 : 2;
    return 2;
}
