from payload_support import requires_payloads
"""无设备：自动驱动选择范围、授权失败门控与重连，不安装电脑驱动。"""
import hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import windows_connection as connection
import windows_app
import x2d_play_software as app
from test_adb_reconnect import Clock

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);d=self.root/'driver';d.mkdir()
        self.hashes={}
        for name in ('camera-driver.exe','libwdi.dll'):
            (d/name).write_bytes(name.encode());self.hashes[name]=hashlib.sha256(name.encode()).hexdigest()
        (d/'provenance.json').write_text(json.dumps(dict(files=self.hashes)))
    def tearDown(self): self.temp.cleanup()
    def test_already_ready_does_not_reinstall(self):
        call=Mock(return_value=0);emit=Mock()
        connection.prepare_driver(emit,self.root,call)
        self.assertEqual([c.args[1] for c in call.call_args_list],['--probe'])
    def test_missing_driver_installs_once_then_waits_for_reenumeration(self):
        call=Mock(side_effect=[10,0,11,10,0]);emit=Mock();clock=Clock()
        connection.prepare_driver(emit,self.root,call,clock)
        self.assertEqual([c.args[1] for c in call.call_args_list],['--probe','--install','--probe','--probe','--probe'])
        self.assertEqual(clock.now,2)
    def test_no_camera_multiple_or_probe_failure_never_installs(self):
        for code in (11,12,13,103,199):
            call=Mock(return_value=code)
            with self.assertRaises(connection.DriverPreparationError):connection.prepare_driver(Mock(),self.root,call)
            self.assertEqual(call.call_count,1)
    def test_cancelled_and_failed_install_never_reaches_camera_check(self):
        for code in (114,115,119):
            call=Mock(side_effect=[10,code]);session=windows_app.Session();session.start('status')
            with self.assertRaises(connection.DriverPreparationError):connection.prepare_driver(Mock(),self.root,call)
            session.consume(dict(type='error'));session.finish(1)
            self.assertFalse(session.start('install'));self.assertFalse(session.start('restore'))
            self.assertEqual(call.call_count,2)
    def test_reconnect_timeout_does_not_reinstall(self):
        calls=[]
        def call(helper,action,emit):calls.append(action);return 0 if action=='--install' else 10
        with self.assertRaisesRegex(connection.DriverPreparationError,'尚未恢复'):
            connection.prepare_driver(Mock(),self.root,call,Clock())
        self.assertEqual(calls.count('--install'),1)
    def test_hash_mismatch_never_executes_helper(self):
        (self.root/'driver/libwdi.dll').write_bytes(b'changed');call=Mock()
        with self.assertRaisesRegex(connection.DriverPreparationError,'校验失败'):connection.prepare_driver(Mock(),self.root,call)
        call.assert_not_called()
    def test_driver_progress_never_unlocks_install(self):
        session=windows_app.Session();session.start('status')
        session.consume(dict(type='progress',message='驱动已就绪',percent=100));session.finish(0)
        self.assertFalse(session.start('install'))
    def test_fixed_helper_invocation_does_not_kill_pending_install(self):
        process=Mock();process.poll.side_effect=[None,None,0];process.returncode=0
        popen=Mock(return_value=process);clock=Clock()
        self.assertEqual(connection.helper_call(self.root/'driver/camera-driver.exe','--install',Mock(),popen,clock),0)
        args,kwargs=popen.call_args
        self.assertEqual(args[0],[str(self.root/'driver/camera-driver.exe'),'--install'])
        self.assertNotIn('shell',kwargs);process.kill.assert_not_called();process.terminate.assert_not_called()
    def test_actual_c_policy_rejects_other_interfaces_and_parents(self):
        source=r'''
#include "windows_driver_policy.h"
int main(void){
 if(!camera_driver_target(0x2756,9,1,3,"USB\\VID_2756&PID_0009&MI_03"))return 1;
 if(!camera_driver_target(0x2756,10,1,3,"usb\\vid_2756&pid_000a&rev_0001&mi_03"))return 2;
 const char *bad[]={"USB\\VID_2756&PID_0009", "USB\\VID_2756&PID_0009&MI_02", "USB\\VID_2756&PID_0009&MI_03junk", "USB\\VID_2756&PID_0009&REV_ZZZZ&MI_03", "USB\\VID_2756&PID_0010&MI_03", "X2D 100C (Interface 3)"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)if(camera_driver_target(0x2756,9,1,3,bad[i]))return 3;
 if(camera_driver_target(0x2756,9,0,3,"USB\\VID_2756&PID_0009&MI_03"))return 4;
 if(camera_driver_target(0x2756,9,1,2,"USB\\VID_2756&PID_0009&MI_03"))return 5;
 if(camera_driver_target(0x1234,9,1,3,"USB\\VID_2756&PID_0009&MI_03"))return 6;
 return 0;}
'''
        path=self.root/'policy.c';path.write_text(source)
        result=subprocess.run(['/usr/bin/clang','-I'+str(app.D),str(path),'-o',str(self.root/'policy')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run([str(self.root/'policy')],capture_output=True)
        self.assertEqual(result.returncode,0)
    @requires_payloads
    def test_known_030_manifest_remains_accepted_and_hash_pinned(self):
        prior=json.loads((app.O/'previous-bundle-0.3.0.json').read_bytes())
        self.assertTrue(app.recognized_bundle(prior))
        with patch.object(app,'PREVIOUS_030_SHA','0'*64):
            with self.assertRaisesRegex(RuntimeError,'0.3.0 清单'):app.recognized_bundle(prior)
        for item in prior['files']:
            saved=(app.O/'previous-payloads'/item['sha256']).read_bytes()
            self.assertEqual(app.sha(saved),item['sha256'])

if __name__=='__main__':unittest.main()
