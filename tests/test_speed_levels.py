"""Actual packaged shell with process memory/native calls substituted, no USB."""
import json,os,re,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import x2d_play_software as app
from payload_support import requires_payloads

@requires_payloads
class SpeedLevels(unittest.TestCase):
 def setUp(self):
  self.manifest=app.prepare()
  if not self.manifest.get('speedLevels'):self.skipTest('Three-speed payload required')
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.base=self.root/'system/etc/x2d-speed-buff';self.base.mkdir(parents=True)
  self.blackbox=self.root/'blackbox';self.blackbox.mkdir();(self.blackbox/'.x2d-play-software').mkdir()
  self.d=self.root/'runtime';self.d.mkdir();self.mem=self.root/'mem'
  for source,target in [('speed-original','original'),('speed-candidate','candidate'),('speed-candidate-low','candidate-low'),('speed-candidate-medium','candidate-medium'),('speed-backend','backend'),('speed-transaction','transaction')]:
   (self.base/target).write_bytes((app.O/source).read_bytes())
  (self.root/'boot').write_text('fixture-boot');(self.root/'stat').write_text(' '.join(['0']*21+['1234'])+'\n')
  self.reset_memory()
  (self.blackbox/'x2d-speed-buff.master').touch()
  helper=self.root/'write-memory.py';helper.write_text('''from pathlib import Path
import sys
root=Path(sys.argv[1]);payload=Path(sys.argv[2]).read_bytes()
with (root/'mem').open('r+b') as f:f.seek(705408);f.write(payload)
''')
  code=(app.O/'speed-worker').read_text()
  code=code.replace('export PATH=/system/bin:/system/xbin:/sbin','export PATH=/usr/bin:/bin')
  code=code.replace('export TMPDIR=/tmp',f'export TMPDIR={self.root}')
  code=code.replace('/system/bin/sh','/bin/sh').replace('/tmp/x2d-speed-buff',str(self.d)).replace('/blackbox',str(self.blackbox))
  code=code.replace('/system/etc/x2d-speed-buff',str(self.base)).replace('/proc/"$P"/mem',str(self.mem)).replace('/proc/"$P"/stat',str(self.root/'stat')).replace('/proc/sys/kernel/random/boot_id',str(self.root/'boot'))
  code=re.sub(r'^BIAS=.*$', 'BIAS=0',code,flags=re.M)
  stub=f'''\ngetprop() {{ printf 'eagle2_ec1706_native\\n'; }}
pidof() {{ printf '123\\n'; }}
odindb-send() {{ printf 'focus_mode = E_FocusModes_Afs(1)\\n'; }}
sha256sum() {{
 if [ "${{1:-}}" = /system/lib64/libaaa.so ]; then printf '{self.manifest['speedLevels']['stockFunctionSha256']}  file\\n' | sed 's/{self.manifest['speedLevels']['stockFunctionSha256']}/feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7/';
 else shasum -a 256 "$@"; fi
}}
sh() {{
 case "$1" in
 "{self.d}/install")
  printf 'install\\n' >>'{self.root}/events'
  [ "${{FAIL_INSTALL:-0}}" = 0 ] || return 1
  '{sys.executable}' '{helper}' '{self.root}' '{self.d}/candidate';;
 "{self.d}/restore")
  printf 'restore\\n' >>'{self.root}/events'
  [ "${{FAIL_RESTORE:-0}}" = 0 ] || return 1
  '{sys.executable}' '{helper}' '{self.root}' '{self.d}/original';;
 *) command sh "$@";;
 esac
}}
'''
  # Both outer process and its actual embedded base shell use the same fake
  # hardware. Profile logic, hashes, preference IO and locks are unchanged.
  code=code.replace('set -eu\n','set -eu\n'+stub).replace('odindb-send','odindb_test')
  self.worker=self.root/'worker';self.worker.write_text(code)
 def reset_memory(self):
  with self.mem.open('wb') as f:
   f.seek(705408);f.write((app.O/'speed-original').read_bytes())
   for offset in (2464,2512,2560):f.seek(offset);f.write(struct.pack('<d',1.5))
   f.seek(10680832);f.write(struct.pack('<Q',0))
 def run_action(self,action,mask=7,**env):
  return subprocess.run(['sh',str(self.worker),action],env=dict(os.environ,X2D_FEATURE_MASK=str(mask),**env),text=True,capture_output=True,timeout=10)
 def check(self,action,mask=7,**env):
  r=self.run_action(action,mask,**env);self.assertEqual(r.returncode,0,r.stderr);return json.loads((self.d/'ui.json').read_text())
 def live_hash(self):
  with self.mem.open('rb') as f:f.seek(705408);return app.sha(f.read(1068))
 def test_default_and_off_selection_is_refused_without_code_change(self):
  self.assertEqual(self.check('status')['speedLevel'],'medium')
  for level in ('low','high','medium'):
   self.assertNotEqual(self.run_action('speed_'+level).returncode,0)
   state=self.check('status');self.assertFalse(state['active']);self.assertEqual(state['speedLevel'],'medium')
   self.assertEqual(self.live_hash(),self.manifest['speedLevels']['stockFunctionSha256'])
  self.assertFalse((self.root/'events').exists())
 def test_active_transitions_and_saved_boot_level(self):
  self.assertTrue(self.check('enable')['active'])
  for level in ('low','medium','high','low','high','medium'):
   state=self.check('speed_'+level);self.assertTrue(state['active']);self.assertEqual(state['speedLevel'],level)
   self.assertEqual(self.live_hash(),self.manifest['speedLevels']['levels'][level]['sha256'])
  self.check('disable');self.assertEqual(self.check('status')['speedLevel'],'medium')
  self.reset_memory();(self.d/'identity').unlink();self.assertTrue(self.check('enable')['active'])
  self.assertEqual(self.live_hash(),self.manifest['speedLevels']['levels']['medium']['sha256'])
  self.check('restore_all');self.assertFalse((self.blackbox/'x2d-speed-buff.level').exists())
 def test_all_masks_gate_selection_and_restore_removes_staging(self):
  for mask in range(1,8):
   if mask&2:self.check('enable',mask)
   result=self.run_action('speed_low',mask)
   self.assertEqual(result.returncode==0,bool(mask&2),(mask,result.stderr))
   if mask&2:self.assertEqual(self.check('status',mask)['speedLevel'],'low')
   (self.blackbox/'x2d-speed-buff.level.next').write_text('high\n')
   self.check('restore_all',mask)
   self.assertFalse((self.blackbox/'x2d-speed-buff.level').exists())
   self.assertFalse((self.blackbox/'x2d-speed-buff.level.next').exists())
   (self.blackbox/'x2d-speed-buff.master').touch()
 def test_failed_install_does_not_commit_new_choice_or_boot_intent(self):
  self.check('enable');self.check('speed_low')
  r=self.run_action('speed_high',FAIL_INSTALL='1');self.assertNotEqual(r.returncode,0)
  state=self.check('status');self.assertEqual(state['speedLevel'],'low');self.assertFalse(state['active'])
  self.assertFalse((self.blackbox/'x2d-speed-buff.enabled').exists())
 def test_unknown_code_or_foreign_identity_refuses_write(self):
  with self.mem.open('r+b') as f:f.seek(705408);f.write(b'UNKNOWN')
  self.assertFalse(self.check('status')['ready']);self.assertNotEqual(self.run_action('speed_high').returncode,0)
  self.reset_memory();self.check('enable');(self.d/'identity').write_text('foreign')
  self.assertNotEqual(self.run_action('speed_low').returncode,0)
  self.assertEqual(self.live_hash(),self.manifest['speedLevels']['levels']['medium']['sha256'])
 def test_invalid_or_symlink_preference_refuses_write(self):
  path=self.blackbox/'x2d-speed-buff.level';path.write_text('evil\n')
  self.assertNotEqual(self.run_action('enable').returncode,0);path.unlink();path.symlink_to(self.root/'boot')
  self.assertNotEqual(self.run_action('speed_high').returncode,0)
 def test_master_off_retains_level_but_restore_clears_it(self):
  self.check('enable');self.check('speed_high');state=self.check('master_off')
  self.assertFalse(state['active']);self.assertFalse(state['master']);self.assertEqual(state['speedLevel'],'high')
  self.assertNotEqual(self.run_action('speed_low').returncode,0)
  self.check('restore_all');self.assertEqual(self.check('status')['speedLevel'],'medium')

 def test_failed_restore_cancels_boot_intent_and_keeps_recovery(self):
  self.check('enable');self.check('speed_low')
  result=self.run_action('speed_high',FAIL_RESTORE='1');self.assertNotEqual(result.returncode,0)
  state=self.check('status');self.assertTrue(state['active']);self.assertEqual(state['speedLevel'],'low')
  self.assertEqual(self.live_hash(),self.manifest['speedLevels']['levels']['low']['sha256'])
  self.assertFalse((self.blackbox/'x2d-speed-buff.enabled').exists())
  self.assertTrue((self.d/'restore').is_file())
  self.check('disable');self.assertFalse(self.check('status')['active'])
 def test_save_failure_restores_original_and_preserves_previous_choice(self):
  self.check('enable');self.check('speed_low')
  staging=self.blackbox/'x2d-speed-buff.level.next';staging.mkdir()
  result=self.run_action('speed_high');self.assertNotEqual(result.returncode,0)
  state=self.check('status');self.assertFalse(state['active']);self.assertEqual(state['speedLevel'],'low')
  self.assertEqual(self.live_hash(),self.manifest['speedLevels']['stockFunctionSha256'])
  self.assertFalse((self.blackbox/'x2d-speed-buff.enabled').exists())
  staging.rmdir();self.check('enable');self.assertEqual(self.live_hash(),self.manifest['speedLevels']['levels']['low']['sha256'])

class SpeedRoutes(unittest.TestCase):
 def test_real_c_matcher_rejects_foreign_method_suffix_and_injection(self):
  import shutil
  server=Path(__file__).resolve().parents[1]/'src/speed-buff-server.c'
  # Suppress only constructor invocation; compile the real routing and fixed
  # command dispatcher with native-memory functions supplied as inert stubs.
  source='''#define __attribute__(x)
#include "%s"
int x2d_eye_command(const char *a,const char *b){return 0;}
#include <stdio.h>
int main(){
 const char *good[]={"POST /speed_low HTTP/1.1","POST /speed_medium HTTP/1.0","POST /speed_high HTTP/1.1"};
 const char *expected[]={"speed_low","speed_medium","speed_high"};
 for(int i=0;i<3;i++){const char *a=speed_action(good[i]);if(!a||strcmp(a,expected[i]))return 1;}
 const char *bad[]={"GET /speed_low HTTP/1.1","POST /speed_lowX HTTP/1.1","POST /speed_high;echo HTTP/1.1","POST /speed_medium","POST /speed_evil HTTP/1.1"};
 for(int i=0;i<5;i++)if(speed_action(bad[i]))return 2;
 puts("PASS");return 0;
}'''%str(server)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'probe.c').write_text(source)
   subprocess.run([shutil.which('clang'),'-O2',str(p/'probe.c'),'-o',str(p/'probe')],check=True,capture_output=True)
   self.assertEqual(subprocess.check_output([str(p/'probe')],text=True).strip(),'PASS')
