"""Offline brightness integration: real callbacks and two-config failure recovery."""
import copy,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import x2d_play_software as app

D=Path(__file__).resolve().parents[1]
GUI=b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n    class core\n'
DISPLAY=b'service camera-system /system/bin/camera-system\n    class core\n'

class BrightnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        for attr,value in [('STOCK_RC',app.sha(GUI)),('DISPLAY_STOCK_RC',app.sha(DISPLAY))]:
            p=patch.object(app,attr,value);p.start();self.addCleanup(p.stop)
        self.files=[dict(source='brightness',target='/system/lib64/libx2d_play_brightness.so',sha256=app.sha(b'fixture'),bytes=7)]
        self.m=dict(format=3,guiSha256=app.STOCK_GUI,files=self.files,autoBrightness=dict(systemSha256=app.DISPLAY_SYSTEM_SHA,
            stockConfigSha256=app.DISPLAY_STOCK_RC,library=self.files[0]['target'],default='off',masterControlled=True))
        self.uploads={}

    def install_script(self,foreign_system=False):
        def shell(cmd):
            if cmd.startswith('test -e '):return 'NO'
            if cmd.startswith('if [ -e '):return 'ABSENT'
            if cmd.startswith('test ! -L ') and 'sha256sum' in cmd:
                path=cmd.split(' && sha256sum ')[1].split(' || ')[0]
                return (app.STOCK_RC if path==app.RC else app.DISPLAY_STOCK_RC)+' file'
            if cmd=='sha256sum /system/bin/camera-system':return ('foreign' if foreign_system else app.DISPLAY_SYSTEM_SHA)+' file'
            if 'echo SAFE' in cmd:return 'SAFE'
            if cmd.startswith('tar '):return ''
            if cmd=='sh '+app.STAGE+'/install':return 'PLAY_SOFTWARE_INSTALLED'
            raise AssertionError(cmd)
        (self.folder/'speed-bundle.tar.gz').write_bytes(b'fixture archive')
        with patch.object(app,'O',self.folder),patch.object(app,'verify_target'),patch.object(app,'prepare',return_value=copy.deepcopy(self.m)), \
             patch.object(app,'shell',side_effect=shell),patch.object(app,'read_bytes',side_effect=lambda p:GUI if p==app.RC else DISPLAY), \
             patch.object(app,'ensure_adb') as adb,patch.object(app,'upload',side_effect=lambda n,b:self.uploads.update({n:b})),patch.object(app,'event'):
            if foreign_system:
                with self.assertRaisesRegex(RuntimeError,'屏幕系统'):app.install(False)
                adb.assert_not_called();self.assertFalse(self.uploads);return
            app.install(False)
        return self.uploads['install'].decode()

    def restore_script(self,foreign=False):
        m=copy.deepcopy(self.m);rc=app.init_config(GUI);display=app.init_display_config(DISPLAY)
        m.update(initBefore=app.STOCK_RC,initAfter=app.sha(rc),displayInitBefore=app.DISPLAY_STOCK_RC,displayInitAfter=app.sha(display))
        data={app.ROOT+'/manifest':json.dumps(m).encode(),app.ROOT+'/stockrc':GUI,app.ROOT+'/stockdisplayrc':DISPLAY,
            app.ROOT+'/installed':b'INSTALLED',app.ROOT+'/created':self.files[0]['target'].encode(),app.DISPLAY_RC:b'foreign' if foreign else display,
            '/tmp/x2d-speed-buff/ui.json':b'{"ready":true,"active":false,"afc":false,"master":false}'}
        (self.folder/'speed-worker').write_bytes(b'fixture worker')
        with patch.object(app,'O',self.folder),patch.object(app,'verify_target'),patch.object(app,'recognized_bundle',return_value=True), \
             patch.object(app,'read_bytes',side_effect=lambda p:data[p]),patch.object(app,'ensure_adb'), \
             patch.object(app,'shell',side_effect=lambda cmd:'PLAY_SOFTWARE_RESTORED' if cmd=='sh '+app.STAGE+'/restore' else 'ACTION_FINISHED' if 'ACTION_FINISHED' in cmd else 'YES'), \
             patch.object(app,'upload',side_effect=lambda n,b:self.uploads.update({n:b})),patch.object(app,'event'):
            if foreign:
                with self.assertRaisesRegex(RuntimeError,'屏幕启动配置'):app.restore(False)
                self.assertNotIn('restore',self.uploads);return
            app.restore(False)
        return self.uploads['restore'].decode()

    def execute(self,script,fail=''):
        root=self.folder/'camera';root.mkdir(exist_ok=True)
        for folder in ('system/etc/init','system/lib64','system/etc/x2d-speed-buff','blackbox/.x2d-play-software/stage'):
            (root/folder).mkdir(parents=True,exist_ok=True)
        for name,data in self.uploads.items():(root/'blackbox/.x2d-play-software/stage'/name).write_bytes(data)
        (root/'blackbox/.x2d-play-software/stage/brightness').write_bytes(b'fixture')
        (root/'system/etc/init/camera-gui.rc').write_bytes(GUI)
        (root/'system/etc/init/camera-system.rc').write_bytes(DISPLAY)
        fixed=script.replace('/system',str(root/'system')).replace('/blackbox',str(root/'blackbox'))
        fixed=fixed.replace('sha256sum','shasum -a 256')
        lines=fixed.splitlines();lines[2]='export PATH=/usr/bin:/bin TMPDIR=/private/tmp'
        lines[4]="state() { echo '/dev/block/mmcblk0p16 ext4 ro,fixture'; }"
        lines.insert(3,'''mount() { return 0; }
stop() { return 0; }
getprop() { echo stopped; }
pidof() { return 1; }
cat() { case " $FAIL_SOURCE " in *" ${1##*/} "*) head -c 10 "$1"; return 1;; *) /bin/cat "$@";; esac; }''')
        result=subprocess.run(['sh'],input='\n'.join(lines)+'\n',text=True,capture_output=True,env=dict(os.environ,FAIL_SOURCE=fail))
        return root,result

    def test_foreign_display_binary_refuses_before_adb_or_upload(self):self.install_script(True)
    def test_foreign_display_configuration_refuses_restore(self):self.restore_script(True)
    def test_install_backs_up_and_writes_both_configs(self):
        seen=self.folder/'camera/blackbox/.x2d-play-software/free-notice-seen'
        seen.parent.mkdir(parents=True);seen.write_bytes(b'1\n')
        script=self.install_script();root,result=self.execute(script)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((root/'system/etc/init/camera-gui.rc').read_bytes(),app.init_config(GUI))
        self.assertEqual((root/'system/etc/init/camera-system.rc').read_bytes(),app.init_display_config(DISPLAY))
        self.assertEqual((root/'blackbox/.x2d-play-software/stockdisplayrc').read_bytes(),DISPLAY)
        self.assertEqual(seen.read_bytes(),b'1\n')
    def test_partial_display_write_rolls_back_both_configs(self):self.rollback('newdisplayrc')
    def test_gui_failure_after_display_write_rolls_back_both_configs(self):self.rollback('newrc')
    def rollback(self,fail):
        root,result=self.execute(self.install_script(),fail)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((root/'system/etc/init/camera-gui.rc').read_bytes(),GUI)
        self.assertEqual((root/'system/etc/init/camera-system.rc').read_bytes(),DISPLAY)
        self.assertFalse((root/'system/lib64/libx2d_play_brightness.so').exists())
    def test_failed_rollback_keeps_recovery_record(self):
        root,result=self.execute(self.install_script(),'newrc stockdisplayrc')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((root/'blackbox/.x2d-play-software/installed').read_text().strip(),'PREPARED')
        self.assertEqual((root/'blackbox/.x2d-play-software/stockdisplayrc').read_bytes(),DISPLAY)
    def test_restore_stops_display_process_and_restores_both_configs(self):
        script=self.restore_script();self.assertLess(script.index('stop camera-system'),script.index('mount -o remount,rw'))
        root=self.folder/'camera';(root/'system/etc/init').mkdir(parents=True)
        (root/'blackbox/.x2d-play-software').mkdir(parents=True)
        (root/'blackbox/.x2d-play-software/stockrc').write_bytes(GUI)
        (root/'blackbox/.x2d-play-software/stockdisplayrc').write_bytes(DISPLAY)
        seen=root/'blackbox/.x2d-play-software/free-notice-seen';seen.write_bytes(b'1\n')
        # Execute against an installed fixture; execute() supplies stock before replacing it here.
        script=script.replace('hashok '+app.RC+' '+app.sha(app.init_config(GUI)), 'hashok '+app.RC+' '+app.sha(GUI))
        script=script.replace('hashok '+app.DISPLAY_RC+' '+app.sha(app.init_display_config(DISPLAY)), 'hashok '+app.DISPLAY_RC+' '+app.sha(DISPLAY))
        # Fixture payload is already present when restore begins.
        (root/'system/lib64').mkdir(parents=True);(root/'system/lib64/libx2d_play_brightness.so').write_bytes(b'fixture')
        root,result=self.execute(script)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((root/'system/etc/init/camera-system.rc').read_bytes(),DISPLAY)
        self.assertFalse((root/'system/lib64/libx2d_play_brightness.so').exists())
        self.assertEqual(seen.read_bytes(),b'1\n')
    def test_actual_display_callbacks_include_master_gate(self):
        generated=D/'src/outputs/brightness-runtime/display-generated.h'
        if not generated.exists():self.skipTest('Generate exact display header with brightness/build.py')
        out=self.folder/'runtime'
        subprocess.run(['clang','-O2','-I'+str(generated.parent),str(D/'tests/brightness_runtime_host_test.c'),str(D/'src/brightness/brightness_policy.c'),'-o',str(out)],check=True)
        subprocess.run([str(out),str(self.folder)],check=True)
    def test_previous_brightness_package_recognition_is_pinned(self):
        data=(D/'src/native-package/previous-bundle-auto-brightness.json').read_bytes()
        self.assertEqual(app.sha(data),app.PREVIOUS_BRIGHTNESS_SHA)
        (self.folder/'previous-bundle-auto-brightness.json').write_bytes(data)
        (self.folder/'previous-bundle-brightness-display.json').write_bytes((D/'src/native-package/previous-bundle-brightness-display.json').read_bytes())
        (self.folder/'previous-bundle-0.4.7.json').write_bytes((D/'src/native-package/previous-bundle-0.4.7.json').read_bytes())
        (self.folder/'previous-bundle-0.4.8.json').write_bytes((D/'src/native-package/previous-bundle-0.4.8.json').read_bytes())
        (self.folder/'previous-bundle-0.4.9.json').write_bytes((D/'src/native-package/previous-bundle-0.4.9.json').read_bytes())
        (self.folder/'previous-bundle-0.4.11.json').write_bytes((D/'src/native-package/previous-bundle-0.4.11.json').read_bytes())
        (self.folder/'previous-bundle-0.4.12.json').write_bytes((D/'src/native-package/previous-bundle-0.4.12.json').read_bytes())
        (self.folder/'previous-bundle-0.4.13.json').write_bytes((D/'src/native-package/previous-bundle-0.4.13.json').read_bytes())
        (self.folder/'previous-bundle-0.4.14.json').write_bytes((D/'src/native-package/previous-bundle-0.4.14.json').read_bytes())
        old=json.loads(data)
        current=copy.deepcopy(self.m);current['uiLanguages']=dict(en=current['files'])
        with patch.object(app,'O',self.folder),patch.object(app,'prepare',return_value=current):
            self.assertTrue(app.recognized_bundle(old))
            self.assertTrue(app.recognized_bundle(app.apply_ui_language(old,'en')))
            old=copy.deepcopy(old);old['files'][0]['sha256']='unknown'
            self.assertFalse(app.recognized_bundle(old))

    def test_previous_042_manifest_is_pinned(self):
        data=(D/'src/native-package/previous-bundle-0.4.2.json').read_bytes()
        self.assertEqual(app.sha(data),app.PREVIOUS_042_SHA)
        old=json.loads(data);self.assertNotIn('autoBrightness',old)

if __name__=='__main__':unittest.main()
