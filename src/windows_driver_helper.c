/* Camera Interface 3 only. No arbitrary VID/PID/MI, path, INF or driver options.
 * Uses libwdi (LGPL-3.0-or-later); sources/build materials distributed alongside.
 */
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include "libwdi.h"
#include "windows_driver_policy.h"

int main(int argc, char **argv) {
    struct wdi_device_info *list=NULL, *dev, *chosen=NULL;
    struct wdi_options_create_list enumerate={TRUE,FALSE,TRUE};
    struct wdi_options_prepare_driver prepare={0};
    struct wdi_options_install_driver install={0};
    char path[MAX_PATH]; wchar_t temp[MAX_PATH], directory[MAX_PATH];
    int code, count=0, action; char *original_desc;
    if (argc!=2) return 13;
    action=!strcmp(argv[1],"--install") ? 1 : !strcmp(argv[1],"--probe") ? 0 : -1;
    if (action<0) return 13;
    wdi_set_log_level(WDI_LOG_LEVEL_NONE);
    code=wdi_create_list(&list,&enumerate);
    if (code) return 100-code;
    for (dev=list;dev;dev=dev->next) {
        if (camera_driver_target(dev->vid,dev->pid,dev->is_composite,dev->mi,dev->hardware_id)) {
            chosen=dev; count++;
        }
    }
    if (count!=1) { wdi_destroy_list(list); return count==0 ? 11 : 12; }
    if (chosen->driver && !_stricmp(chosen->driver,"WinUSB")) {
        wdi_destroy_list(list); return 0; /* Keep existing bindings. */
    }
    if (!action) { wdi_destroy_list(list); return 10; }
    if (!IsUserAnAdmin()) { wdi_destroy_list(list); return 15; }
    /* A private, newly created directory, no caller-provided extraction path. */
    if (!GetTempPathW(MAX_PATH,temp) || !GetTempFileNameW(temp,L"X2D",0,directory)) {
        wdi_destroy_list(list); return 16;
    }
    if (!DeleteFileW(directory) || !CreateDirectoryW(directory,NULL) ||
        !WideCharToMultiByte(CP_UTF8,0,directory,-1,path,sizeof(path),NULL,NULL)) {
        wdi_destroy_list(list); return 16;
    }
    /* Fixed names avoid copying device serials into the driver or logs. */
    original_desc=chosen->desc;
    chosen->desc=chosen->pid==9 ? "X2D 100C Camera Interface 3" : "CFV 100C Camera Interface 3";
    prepare.driver_type=WDI_WINUSB;
    prepare.vendor_name="Camera USB connection";
    prepare.device_guid="{934A9D45-BC99-4B69-B128-9D65A095A2D3}";
    /* CAT creation/signing stay enabled; no WCID/filter/stealth options. */
    code=wdi_prepare_driver(chosen,path,"camera_interface3.inf",&prepare);
    if (!code) {
        install.pending_install_timeout=120000;
        code=wdi_install_driver(chosen,path,"camera_interface3.inf",&install);
    }
    chosen->desc=original_desc;
    wdi_destroy_list(list);
    return code ? 100-code : 0;
}
