/* Exact scope for driver binding. Friendly names never authorize changes. */
#ifndef CAMERA_DRIVER_POLICY_H
#define CAMERA_DRIVER_POLICY_H
#include <string.h>
#include <ctype.h>
static int camera_hardware_id(const char *id, unsigned short pid) {
    const char *prefix = pid == 9 ? "USB\\VID_2756&PID_0009" :
                         pid == 10 ? "USB\\VID_2756&PID_000A" : NULL;
    size_t n, i;
    if (!id || !prefix) return 0;
    n = strlen(prefix);
    if (strlen(id) < n) return 0;
    for (i=0;i<n;i++) if (toupper((unsigned char)id[i]) != prefix[i]) return 0;
    id += n;
    if (strlen(id) == 15) {
        if (id[0]!='&' || toupper(id[1])!='R' || toupper(id[2])!='E' || toupper(id[3])!='V' || id[4]!='_') return 0;
        for (i=5;i<9;i++) if (!isxdigit((unsigned char)id[i])) return 0;
        id += 9;
    }
    return strlen(id)==6 && id[0]=='&' && toupper(id[1])=='M' && toupper(id[2])=='I' &&
           id[3]=='_' && id[4]=='0' && id[5]=='3';
}
static int camera_driver_target(unsigned short vid, unsigned short pid, int composite,
                                unsigned char mi, const char *id) {
    return vid==0x2756 && composite && mi==3 && camera_hardware_id(id,pid);
}
#endif
