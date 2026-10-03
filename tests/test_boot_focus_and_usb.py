from payload_support import requires_payloads
"""无相机：实际服务构造器不强切 AF-C；精确 USB PID 与旧版升级门禁。"""
import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
import x2d_play_software as app
import windows_factory_usb as native
from test_windows_adb_transport import EnumerateAPI,PATH

HARNESS=r'''
#include <stdlib.h>
#include <string.h>
char *getenv(const char *name) { return !strcmp(name,"X2D_SPEED_SERVER") ? "1" : 0; }
int unsetenv(const char *name) { return 0; }
int system(const char *command) { if(strstr(command,"worker afc_on")) exit(42); return 0; }
int socket(int a,int b,int c) { return 1; }
int bind(int a,const void *b,unsigned c) { return 0; }
int listen(int a,int b) { return 0; }
int setsockopt(int a,int b,int c,const void *d,unsigned e) { return 0; }
int accept(int a,void *b,void *c) { exit(0); }
int close(int a) { return 0; }
int open(const char *a,int b,...) { return -1; }
long read(int a,void *b,unsigned long c) { return -1; }
long write(int a,const void *b,unsigned long c) { return -1; }
void _exit(int code) { exit(code); }
int unlink(const char *path) { return 0; }
int main(void) { return 43; }
'''

class BootAndUSBTests(unittest.TestCase):
    def test_real_constructor_no_longer_runs_afc_on_but_old_boot_path_reproduces(self):
        source=(app.D/'speed-buff-server.c').read_text()
        old=' system("/system/bin/sh /system/etc/x2d-speed-buff/worker afc_on");\n'
        with tempfile.TemporaryDirectory(prefix='boot-regression-') as directory:
            root=Path(directory);(root/'harness.c').write_text(HARNESS)
            for label,code,expected in [('fixed',source,0),('old-path',source.replace(' /* The saved AF-C flag',old+' /* The saved AF-C flag',1),42)]:
                (root/'server.c').write_text(code)
                compile=subprocess.run(['/usr/bin/clang','-fno-builtin',str(root/'server.c'),str(root/'harness.c'),'-o',str(root/'probe')],capture_output=True,text=True)
                self.assertEqual(compile.returncode,0,compile.stderr)
                run=subprocess.run([str(root/'probe')],capture_output=True,text=True,timeout=5)
                self.assertEqual(run.returncode,expected,label)

    def test_mac_reader_selects_x2d_and_cfv_without_accepting_other_pids(self):
        core=MagicMock()
        for pid in (0x0009,0x000A):
            core.find.return_value=[MagicMock(idProduct=0x4321),MagicMock(idProduct=pid)]
            with patch.object(app.os,'name','posix'),patch.object(app,'USB_RUNTIME_ERROR',False), \
                 patch.object(app.usb,'_load_usb',return_value=(core,MagicMock())), \
                 patch.object(app.usb,'FactoryUsbReader') as reader:
                app.reader()
                self.assertEqual(reader.call_args.args[1],pid)
                self.assertEqual(reader.call_args.args[2:6],(3,0,4,0x85))

    def test_mac_reader_rejects_unknown_pid_and_multiple_target_models(self):
        core=MagicMock()
        for ids in ([0x4321],[9,10]):
            core.find.return_value=[MagicMock(idProduct=pid) for pid in ids]
            with patch.object(app.os,'name','posix'),patch.object(app,'USB_RUNTIME_ERROR',False), \
                 patch.object(app.usb,'_load_usb',return_value=(core,MagicMock())), \
                 patch.object(app.usb,'FactoryUsbReader') as reader:
                with self.assertRaises(Exception): app.reader()
                reader.assert_not_called()

    def test_windows_cfv_uses_same_exact_interface_and_path_guards(self):
        cfv=PATH.replace('pid_0009','pid_000a')
        self.assertTrue(native.target_id('USB\\VID_2756&PID_000A&MI_03'))
        self.assertTrue(native.target_path(cfv))
        self.assertFalse(native.target_id('USB\\VID_2756&PID_000A&MI_02'))
        api=EnumerateAPI();api.ids[1]='USB\\VID_2756&PID_000A&MI_03';api.interface_paths=[(2,cfv)]
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            self.assertEqual(api.factory_path(),cfv)

    def test_windows_x2d_and_cfv_connected_together_are_rejected(self):
        api=EnumerateAPI();api.ids.append('USB\\VID_2756&PID_000A&MI_03')
        with patch.object(native.C,'get_last_error',side_effect=lambda:api.error,create=True):
            with self.assertRaisesRegex(app.usb.UsbFactoryError,'多台'): api.factory_path()

    @requires_payloads
    def test_preceding_installed_bundle_differs_only_in_boot_service(self):
        old=json.loads((app.O/'previous-bundle.json').read_bytes())
        new=json.loads((app.O/'previous-bundle-0.3.2.json').read_bytes())
        changed=[a['source'] for a,b in zip(old['files'],new['files']) if a!=b]
        self.assertEqual(set(changed),{'libx2d_speed_server.so','X2dNativeMenuModel.qml','X2dNativeMenuBootstrap.qml'})
        saved=(app.O/'previous-speed-server.so').read_bytes()
        old_service=next(item for item in old['files'] if item['source']=='libx2d_speed_server.so')
        self.assertEqual(app.sha(saved),old_service['sha256'])

if __name__=='__main__':unittest.main()
