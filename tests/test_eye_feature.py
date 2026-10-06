"""Execute fixed Eye transport and the real worker against isolated stock-state fixtures."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

ODIN_FIXTURE = r'''
import json, os, sys
from pathlib import Path
root=Path(os.environ['EYE_TEST_ROOT']);state=json.loads((root/'state.json').read_text());args=sys.argv[1:]
names=['EyeDetection','FaceDetection','Recalibrate','Touch','TouchPointerHandlers','Dcf','Browse']
def ini():
 tokens=['E_DebugOption_'+name for bit,name in enumerate(names) if state['options']&(1<<bit)] or ['E_DebugOption_None']
 (root/'data/config/system.ini').write_text('[Default]\ndebug_mode='+str(state['mode']).lower()+'\ndebug_options=HblmTypes::'+'|'.join(tokens)+'\n')
field=args[args.index('-p')+1]
if '--' in args:
 value=args[args.index('--')+1]
 if field==state.get('fail'):sys.exit(2)
 if field==state.get('ignore'):sys.exit(0)
 if field=='debug_mode':state['mode']=value=='true'
 elif field=='debug_options':state['options']=int(value)
 else:sys.exit(3)
 ini();(root/'state.json').write_text(json.dumps(state))
 with (root/'writes.jsonl').open('a') as out:out.write(json.dumps(dict(field=field,value=value,mode=state['mode'],options=state['options'],effective=state['options'] if state['mode'] else 0))+'\n')
else:
 if state.get('bad_read')==field:print('system.'+field+' = unknown');sys.exit(0)
 if field=='debug_mode':print('system.debug_mode = '+str(state['mode']).lower())
 elif field=='debug_options':
  mask=state['options'] if state['mode'] else 0;tokens=['E_DebugOption_'+name for bit,name in enumerate(names) if mask&(1<<bit)] or ['E_DebugOption_None']
  label=tokens[0] if len(tokens)==1 else '['+' | '.join(tokens)+']'
  print('system.debug_options = '+label+'('+str(mask)+')')
 else:sys.exit(3)
'''


class EyeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='eye-worker-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ('bin', 'data/config', 'blackbox/.x2d-play-software', 'proc/42', 'proc/sys/kernel/random', 'system/etc/x2d-speed-buff', 'system/bin'):
            (self.root / folder).mkdir(parents=True)
        (self.root / 'proc/42/stat').write_text(' '.join(['42'] * 22) + '\n')
        (self.root / 'proc/42/maps').write_text('00001000-00900000 r-xp 00000000 00:00 0 /system/lib64/libaaa.so\n')
        (self.root / 'proc/42/mem').write_bytes(bytes(705408 + 1068))
        (self.root / 'proc/sys/kernel/random/boot_id').write_text('fixture-boot\n')
        for command, body in [('getprop', 'echo eagle2_ec1706_native'), ('pidof', 'echo 42'), ('sync', 'exit 0')]:
            path = self.root / 'bin' / command
            path.write_text('#!/bin/sh\n' + body + '\n'); path.chmod(0o700)
        odin = self.root / 'bin/odindb-send'
        odin.write_text('#!' + sys.executable + '\n' + ODIN_FIXTURE); odin.chmod(0o700)
        (self.root / 'system/bin/odindb-send').symlink_to(odin)
        system = self.root / 'system/bin/camera-system'; system.write_bytes(b'known stock system fixture')
        toybox = self.root / 'system/bin/toybox'
        toybox.write_text('#!' + sys.executable + '\nimport fcntl,sys\nassert sys.argv[1]=="flock"\nflags=fcntl.LOCK_UN if "-u" in sys.argv else fcntl.LOCK_EX|fcntl.LOCK_NB\ntry:fcntl.flock(int(sys.argv[-1]),flags)\nexcept BlockingIOError:sys.exit(1)\n')
        toybox.chmod(0o700)
        hash_command = self.root / 'bin/sha256sum'
        hash_command.write_text('#!' + sys.executable + '\nimport hashlib,sys\nfrom pathlib import Path\ndata=Path(sys.argv[1]).read_bytes() if len(sys.argv)>1 else sys.stdin.buffer.read()\nprint(hashlib.sha256(data).hexdigest()+"  fixture")\n')
        hash_command.chmod(0o700)
        source = (ROOT / 'src/speed-buff-worker.sh').read_text()
        source = source.replace('export PATH=/system/bin:/system/xbin:/sbin', 'export PATH=' + str(self.root / 'bin') + ':/usr/bin:/bin')
        # Relocate only hardware/filesystem paths and the known stock memory hash.
        source = source.replace('/tmp/x2d-speed-buff', str(self.root / 'tmp-speed'))
        source = source.replace('/blackbox', str(self.root / 'blackbox')).replace('/data/config', str(self.root / 'data/config'))
        source = source.replace('/proc/', str(self.root / 'proc') + '/')
        source = source.replace('/system/bin/', str(self.root / 'system/bin') + '/')
        source = source.replace('c8b5407c615b60c05078bc7ba9ada8cf53c905bac17faa59561f948feac0d430', hashlib.sha256(bytes(1068)).hexdigest())
        source = source.replace('bf854a21881148565ff2cc00376426c37a2b82fed94c653abf024e23ed4ceda6', hashlib.sha256(system.read_bytes()).hexdigest())
        source = source.replace('4fdf240bd521fbf54ec638617446e4eb8778335734cb36752df6ff1a2336f62b', hashlib.sha256(odin.read_bytes()).hexdigest())
        source = source.replace('999a0669ef654efbda54bc585c0f3c00643d1af61c985bfb7968cfd2f9aed840', hashlib.sha256(toybox.read_bytes()).hexdigest())
        self.worker = self.root / 'worker'; self.worker.write_text(source)
        self.environment = dict(os.environ, EYE_TEST_ROOT=str(self.root), X2D_FEATURE_MASK='8')
        self.master = self.root / 'blackbox/x2d-speed-buff.master'
        self.baseline = self.root / 'blackbox/.x2d-play-software/eye-debug-baseline'
        self.transaction = self.root / 'blackbox/.x2d-play-software/eye-debug-transaction'
        self.preference = self.root / 'blackbox/x2d-play-eye.preference'
        self.set_stock(False, 0)

    def set_stock(self, mode, options, **extra):
        state = dict(mode=mode, options=options, **extra)
        (self.root / 'state.json').write_text(json.dumps(state))
        names = ['EyeDetection', 'FaceDetection', 'Recalibrate', 'Touch', 'TouchPointerHandlers', 'Dcf', 'Browse']
        labels = ['E_DebugOption_' + name for bit, name in enumerate(names) if options & (1 << bit)] or ['E_DebugOption_None']
        (self.root / 'data/config/system.ini').write_text('[Default]\ndebug_mode=' + str(mode).lower() + '\ndebug_options=HblmTypes::' + '|'.join(labels) + '\n')

    def state(self):
        value = json.loads((self.root / 'state.json').read_text())
        return value['mode'], value['options']

    def run_worker(self, action, expected=0):
        result = subprocess.run(['sh', str(self.worker), action], env=self.environment, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        if expected:
            return None
        return json.loads((self.root / 'tmp-speed/ui.json').read_text())

    def writes(self):
        path = self.root / 'writes.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_install_and_status_never_enable_eye_and_real_combined_reply_parses(self):
        for mode, mask in [(False, 6), (True, 3), (True, 127), (False, 0)]:
            self.set_stock(mode, mask)
            state = self.run_worker('status')
            self.assertTrue(state['eyeReady'])
            self.assertEqual(state['eyeActive'], mode and bool(mask & 1))
            self.assertEqual(self.state(), (mode, mask))
        self.assertFalse(self.baseline.exists()); self.assertEqual(self.writes(), [])

    def test_hidden_flags_are_saved_never_activated_and_off_restores(self):
        self.set_stock(False, 6)
        self.master.touch()
        state = self.run_worker('eye_on')
        self.assertTrue(state['eyeActive']); self.assertTrue(state['eyeEnabled'])
        self.assertEqual(self.state(), (True, 1)); self.assertEqual(self.baseline.read_text(), '1 0 6\n')
        self.run_worker('eye_on')
        self.assertEqual(self.baseline.read_text(), '1 0 6\n')
        state = self.run_worker('eye_off')
        self.assertFalse(state['eyeActive']); self.assertEqual(self.state(), (False, 6))
        self.assertFalse(self.baseline.exists()); self.assertFalse(self.preference.exists())
        self.assertTrue(all(write['effective'] in (0, 1) for write in self.writes()))

    def test_active_other_flags_and_original_eye_restore_without_afc_change(self):
        self.set_stock(True, 3); self.master.touch()
        state = self.run_worker('eye_off')
        self.assertFalse(state['eyeActive']); self.assertEqual(self.state(), (True, 2))
        self.set_stock(True, 10)  # External user added Touch while Eye was disabled.
        state = self.run_worker('master_off')
        self.assertFalse(state['master']); self.assertEqual(self.state(), (True, 11))
        self.assertFalse(self.baseline.exists()); self.assertFalse(self.preference.exists())
        self.set_stock(False, 64)  # A later stock change is beyond toolkit ownership.
        state = self.run_worker('eye_restore')
        self.assertTrue(state['eyeRestored']); self.assertEqual(self.state(), (False, 64))

    def test_conflict_rejects_before_writes_and_other_features_remain_ready(self):
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        self.set_stock(True, 5)
        before = self.writes()
        for action in ('status', 'eye_off', 'master_off'):
            state = self.run_worker(action)
            self.assertTrue(state['ready']); self.assertFalse(state['eyeReady'])
            self.assertEqual(state['eyeIssue'], 'changed'); self.assertTrue(state['master'])
            self.assertEqual(self.state(), (True, 5)); self.assertEqual(self.writes(), before)
        self.run_worker('eye_restore', expected=39)
        self.assertTrue(self.baseline.exists()); self.assertTrue(self.preference.exists())
        self.set_stock(True, 1)
        self.run_worker('master_off'); self.assertEqual(self.state(), (False, 6))

    def test_partial_enable_transaction_is_recoverable_without_foreign_overwrite(self):
        self.set_stock(False, 6, fail='debug_mode'); self.master.touch()
        state = self.run_worker('eye_on')
        self.assertFalse(state['eyeReady']); self.assertEqual(state['eyeIssue'], 'incomplete')
        self.assertEqual(self.state(), (False, 1)); self.assertTrue(self.transaction.exists())
        self.set_stock(False, 1)
        self.run_worker('eye_restore'); self.assertEqual(self.state(), (False, 6))
        self.assertFalse(self.baseline.exists()); self.assertFalse(self.transaction.exists())

    def test_partial_restore_can_retry_and_stale_transaction_cannot_overwrite(self):
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        self.set_stock(True, 1, fail='debug_options')
        self.run_worker('eye_restore', expected=39)
        self.assertEqual(self.state(), (False, 1)); self.assertTrue(self.transaction.exists())
        self.set_stock(False, 1)
        self.run_worker('eye_restore'); self.assertEqual(self.state(), (False, 6))
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        self.transaction.write_text('1 0 6 1 1\n'); self.set_stock(False, 64)
        before = self.writes(); self.run_worker('eye_restore', expected=39)
        self.assertEqual(self.state(), (False, 64)); self.assertEqual(self.writes(), before)

    def test_unknown_ini_duplicate_symlink_and_getter_mismatch_stop_writes(self):
        self.master.touch()
        ini = self.root / 'data/config/system.ini'
        for text in ('[Default]\ndebug_options=HblmTypes::E_DebugOption_Max\n', '[Default]\ndebug_mode=false\ndebug_mode=false\n', '[Default]\n[Default]\n', '[Default]\ndebug_options=HblmTypes::E_DebugOption_None|E_DebugOption_EyeDetection\n'):
            ini.write_text(text)
            state = self.run_worker('eye_on'); self.assertFalse(state['eyeReady'])
            self.assertFalse(self.baseline.exists()); self.assertEqual(self.writes(), [])
        self.set_stock(False, 0, bad_read='debug_options')
        state = self.run_worker('eye_on'); self.assertFalse(state['eyeReady'])
        self.assertFalse(self.baseline.exists()); self.assertEqual(self.writes(), [])
        self.set_stock(False, 0)
        self.baseline.symlink_to(ini)
        state = self.run_worker('eye_on'); self.assertFalse(state['eyeReady'])
        self.assertEqual(self.writes(), []); self.assertTrue(self.baseline.is_symlink())

    def test_boot_reapplies_only_owned_preference_and_master_off_relinquishes(self):
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        self.set_stock(False, 6)  # A firmware reload returned the stock setting.
        state = self.run_worker('eye_resume'); self.assertTrue(state['eyeActive'])
        self.run_worker('master_off'); self.assertFalse(self.preference.exists())
        self.set_stock(False, 64)
        self.run_worker('master_on'); self.assertEqual(self.state(), (False, 64))

    def test_disabled_debug_master_is_external_conflict_for_original_on_baseline(self):
        self.set_stock(True, 3); self.master.touch(); self.run_worker('eye_off')
        self.set_stock(False, 2); before = self.writes()
        state = self.run_worker('master_off')
        self.assertFalse(state['eyeReady']); self.assertTrue(state['master'])
        self.run_worker('eye_restore', expected=39)
        self.assertEqual(self.state(), (False, 2)); self.assertEqual(self.writes(), before)

    def test_uninstalled_eye_actions_are_rejected_before_filesystem_access(self):
        self.environment['X2D_FEATURE_MASK'] = '7'
        for action in ('eye_on', 'eye_off', 'eye_resume'):
            self.run_worker(action, expected=38)
        self.assertFalse((self.root / 'tmp-speed').exists()); self.assertEqual(self.writes(), [])

    def test_non_eye_master_off_preserves_debug_state_and_unrelated_eye_metadata(self):
        self.environment['X2D_FEATURE_MASK'] = '7'
        self.set_stock(True, 3); self.master.touch()
        self.baseline.write_text('foreign local file\n'); self.preference.write_text('1\n')
        state = self.run_worker('master_off')
        self.assertFalse(state['master']); self.assertEqual(self.state(), (True, 3))
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.baseline.read_text(), 'foreign local file\n'); self.assertEqual(self.preference.read_text(), '1\n')

    def test_modified_system_or_tool_hash_is_rejected_before_debug_read_or_write(self):
        self.master.touch()
        for path in (self.root / 'system/bin/camera-system', self.root / 'bin/odindb-send'):
            original = path.read_bytes(); path.write_bytes(original + b'\n# modified\n')
            state = self.run_worker('eye_on')
            self.assertFalse(state['eyeReady']); self.assertEqual(self.writes(), [])
            self.assertFalse(self.baseline.exists()); path.write_bytes(original)

    def test_verified_pending_preference_and_transaction_files_recover_after_crash(self):
        for kind in ('preference', 'transaction'):
            self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
            pending = Path(str(self.preference if kind == 'preference' else self.transaction) + '.next')
            pending.write_text('1\n' if kind == 'preference' else '1 1 1 0 6\n')
            state = self.run_worker('status')
            self.assertFalse(state['eyeReady']); self.assertEqual(state['eyeIssue'], 'incomplete')
            state = self.run_worker('eye_restore')
            self.assertTrue(state['eyeRestored']); self.assertEqual(self.state(), (False, 6))
            self.assertFalse(pending.exists()); self.assertFalse(self.baseline.exists())

    def test_unknown_or_mismatched_pending_files_preserve_state_and_ownership(self):
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        for path, content in [(Path(str(self.preference) + '.next'), '0\n'), (Path(str(self.transaction) + '.next'), '1 1 1 1 127\n')]:
            path.write_text(content); before = self.writes()
            self.run_worker('eye_restore', expected=39)
            self.assertEqual(self.state(), (True, 1)); self.assertEqual(self.writes(), before)
            self.assertTrue(self.baseline.exists()); self.assertEqual(path.read_text(), content); path.unlink()

    def test_kernel_transaction_lock_ignores_old_stale_directory_and_blocks_concurrency(self):
        self.run_worker('status')
        (self.root / 'tmp-speed/lock').mkdir()  # Stale old-version mkdir lock.
        self.run_worker('status')
        with (self.root / 'tmp-speed/lockfile').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.worker.write_text(self.worker.read_text().replace('sleep 1', 'sleep 0.02'))
            self.run_worker('status', expected=36)
            fcntl.flock(lock, fcntl.LOCK_UN)
        self.run_worker('status')

    def test_silent_stock_setter_refusal_never_activates_saved_hidden_options(self):
        self.set_stock(False, 6); self.master.touch(); self.run_worker('eye_on')
        self.set_stock(True, 1, ignore='debug_mode'); before = self.writes()
        self.run_worker('eye_restore', expected=39)
        self.assertEqual(self.state(), (True, 1)); self.assertEqual(self.writes(), before)
        self.assertTrue(self.baseline.exists()); self.assertTrue(self.transaction.exists())
        self.set_stock(True, 1); self.run_worker('eye_restore')
        self.assertEqual(self.state(), (False, 6))
        self.assertTrue(all(write['effective'] in (0, 1) for write in self.writes()))

    def test_silent_options_refusal_never_enables_debug_with_hidden_options(self):
        self.set_stock(False, 6, ignore='debug_options'); self.master.touch()
        state = self.run_worker('eye_on')
        self.assertFalse(state['eyeReady']); self.assertEqual(self.state(), (False, 6))
        self.assertEqual(self.writes(), [])
        self.set_stock(False, 6); self.run_worker('eye_restore')
        self.assertEqual(self.state(), (False, 6))

    def test_orphaned_preference_never_recaptures_baseline_or_enables_at_startup(self):
        self.set_stock(False, 6); self.master.touch(); self.preference.write_text('1\n')
        state = self.run_worker('status')
        self.assertFalse(state['eyeReady']); self.assertEqual(state['eyeIssue'], 'unavailable')
        self.run_worker('eye_resume', expected=39)
        state = self.run_worker('master_on'); self.assertFalse(state['eyeReady'])
        self.assertFalse(self.baseline.exists()); self.assertEqual(self.writes(), [])
        self.assertEqual(self.state(), (False, 6))
        state = self.run_worker('master_off')
        self.assertFalse(state['eyeReady']); self.assertTrue(state['master'])
        self.run_worker('eye_restore', expected=39)
        self.assertTrue(self.preference.exists()); self.assertFalse(self.baseline.exists())
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.state(), (False, 6))


class EyeTransportTests(unittest.TestCase):
    def test_real_dispatch_accepts_only_fixed_eye_actions(self):
        source = (ROOT / 'src/speed-buff-server.c').read_text()
        harness = r'''
#include <string.h>
static const char *last_command = 0;
char *getenv(const char *name) { return 0; }
int system(const char *command) { last_command = command; return 0; }
int main(void) {
 if(run("eye_on") || strcmp(last_command,"/system/bin/sh /system/etc/x2d-speed-buff/worker eye_on")) return 1;
 if(run("eye_off") || strcmp(last_command,"/system/bin/sh /system/etc/x2d-speed-buff/worker eye_off")) return 2;
 last_command = 0;
 if(run("eye_on; reboot") != -1 || last_command) return 3;
 if(run("eye_off --foreign") != -1 || last_command) return 4;
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='eye-transport-') as directory:
            path = Path(directory)
            (path / 'probe.c').write_text(source + harness)
            result = subprocess.run(['/usr/bin/clang', '-fno-builtin', str(path / 'probe.c'), '-o', str(path / 'probe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / 'probe')], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
