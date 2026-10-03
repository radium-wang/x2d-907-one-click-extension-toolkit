from payload_support import requires_payloads
"""Offline menu success gates and execution of fixed marker acknowledgements."""
import json, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import x2d_play_software as app

class MenuReadyTests(unittest.TestCase):
    @requires_payloads
    def test_existing_install_missing_entry_never_reports_success(self):
        for marker in ('MENU_PENDING','MENU_ENTRY_READY_10',''):
            with self.subTest(marker=marker), patch.object(app,'verify_target'), patch.object(app,'event') as event, patch.object(app,'backend',return_value={'ready':True}), patch.object(app,'read_bytes',side_effect=[b'INSTALLED',json.dumps(app.prepare()).encode()]), patch.object(app,'shell',side_effect=['YES',marker]):
                with self.assertRaisesRegex(RuntimeError,'菜单入口'): app.install()
                self.assertFalse(any(c.args[0]=='result' for c in event.call_args_list))

    @requires_payloads
    def test_existing_install_accepts_both_actual_menu_lengths(self):
        for marker in ('MENU_ENTRY_READY_11','MENU_ENTRY_READY_12'):
            with self.subTest(marker=marker), patch.object(app,'verify_target'), patch.object(app,'event') as event, patch.object(app,'backend',return_value={'ready':True}), patch.object(app,'read_bytes',side_effect=[b'INSTALLED',json.dumps(app.prepare()).encode()]), patch.object(app,'shell',side_effect=['YES',marker]):
                app.install()
                self.assertEqual(event.call_args.args[0],'result'); self.assertTrue(event.call_args.kwargs['success'])

    def reboot(self,marker):
        values=['REBOOT_DISPATCHED','running','running','MENU_AND_AFC_SWITCHABLE_READY',marker]
        with patch.object(app,'verify_target'), patch.object(app,'event') as event, patch.object(app,'backend',return_value={'ready':True}) as backend, patch.object(app,'shell',side_effect=values), patch.object(app.time,'sleep'), patch.object(app.time,'monotonic',side_effect=[0,1,72]):
            if marker=='MENU_PENDING':
                with self.assertRaisesRegex(RuntimeError,'菜单入口'): app.reboot_and_verify(True)
                backend.assert_not_called()
                self.assertFalse(any(c.args[0]=='result' for c in event.call_args_list))
            else:
                app.reboot_and_verify(True); self.assertTrue(event.call_args.kwargs['success'])

    def test_reboot_does_not_confuse_preload_marker_with_menu_loaded(self): self.reboot('MENU_PENDING')
    def test_reboot_cfv_and_x2d_menu_ready(self):
        for marker in ('MENU_ENTRY_READY_11','MENU_ENTRY_READY_12'): self.reboot(marker)

    def test_actual_c_ack_fixed_file_short_write_failure_and_unavailable(self):
        code=r'''
extern void *memcpy(void*,const void*,unsigned long);
extern void exit(int);
static char saved[32]; static int short_write, erased;
char *getenv(const char *s){return 0;}
int open(const char *path,int flags,...){if(strcmp(path,"/tmp/x2d-native-menu-ui.ready")) exit(50);return 99;}
long write(int f,const void *value,unsigned long n){if(f!=99||n!=19)exit(51);memcpy(saved,value,n);return short_write?18:19;}
int close(int f){return 0;}
int unlink(const char *path){if(strcmp(path,"/tmp/x2d-native-menu-ui.ready"))exit(52);erased++;return 0;}
int main(void){
 if(menu_ack("menu_ready_11")||strcmp(saved,"MENU_ENTRY_READY_11"))return 1;
 if(menu_ack("menu_ready_12")||strcmp(saved,"MENU_ENTRY_READY_12"))return 2;
 short_write=1;if(menu_ack("menu_ready_11")!=-1)return 3;
 if(menu_ack("menu_unavailable")||erased!=1)return 4;
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'check.c').write_text((app.D/'speed-buff-server.c').read_text()+code)
            compile=subprocess.run(['/usr/bin/clang','-fno-builtin',str(path/'check.c'),'-o',str(path/'check')],capture_output=True,text=True)
            self.assertEqual(compile.returncode,0,compile.stderr)
            self.assertEqual(subprocess.run([str(path/'check')],timeout=5).returncode,0)

if __name__=='__main__': unittest.main()
