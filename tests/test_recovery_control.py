"""Run the generated recovery boundary against isolated init and /proc fixtures."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import x2d_play_software as app


DRIVER = r'''
import json, os, sys
from pathlib import Path
root = Path(os.environ['RECOVERY_CONTROL_TEST_ROOT'])
command, arguments = sys.argv[1], sys.argv[2:]
state_path = root / 'state.json'
state = json.loads(state_path.read_text())
event = dict(command=command, arguments=arguments)
exit_code = 0
result = None
if command == 'getprop':
    assert arguments == ['init.svc.x2d-speed-buff']
    index = state.get('getprop_reads', 0)
    states = state.get('service_states', ['stopped'])
    result = states[min(index, len(states) - 1)]
    state['getprop_reads'] = index + 1
    exit_code = state.get('failures', {}).get('getprop', 0)
    if exit_code:
        result = None
    event['result'] = result
elif command == 'sleep':
    assert arguments == ['1']
    state['sleeps'] = state.get('sleeps', 0) + 1
    if state.get('drain_after_sleep') == state['sleeps']:
        for pid in state.get('drain_pids', []):
            (root / 'proc' / str(pid) / 'cmdline').unlink()
        event['drained_pids'] = state.get('drain_pids', [])
elif command == 'recovery':
    assert len(arguments) == 1
    event['mask'] = os.environ.get('X2D_FEATURE_MASK')
    event['remaining_proc'] = sorted(str(p.parent.name) for p in (root / 'proc').glob('[0-9]*/cmdline'))
    exit_code = state.get('failures', {}).get(arguments[0], 0)
elif command in ('start', 'stop'):
    assert arguments == ['x2d-speed-buff']
    exit_code = state.get('failures', {}).get(command, 0)
else:
    raise AssertionError(command)
state_path.write_text(json.dumps(state))
with (root / 'events.jsonl').open('a') as output:
    output.write(json.dumps(event) + '\n')
if result is not None:
    print(result)
sys.exit(exit_code)
'''


class RecoveryControlTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='recovery-control-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.stage = self.root / 'stage'
        self.bin = self.root / 'bin'
        self.proc = self.root / 'proc'
        for folder in (self.stage, self.bin, self.proc):
            folder.mkdir()
        driver = self.root / 'driver.py'
        driver.write_text(DRIVER)
        for name in ('stop', 'getprop', 'start', 'sleep', 'recovery'):
            target = (self.stage if name == 'recovery' else self.bin) / name
            target.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' +
                              shlex.quote(str(driver)) + ' ' + name + ' "$@"\n')
            target.chmod(0o700)
        self.environment = dict(os.environ, RECOVERY_CONTROL_TEST_ROOT=str(self.root))
        self.configure()

    def configure(self, **state):
        (self.root / 'state.json').write_text(json.dumps(state))

    def cmdline(self, pid, arguments):
        directory = self.proc / str(pid)
        directory.mkdir()
        # Linux exposes real argv as NUL-separated bytes, including its final NUL.
        (directory / 'cmdline').write_bytes(b'\0'.join(argument.encode() for argument in arguments) + b'\0')

    def run_control(self, mask, eye=False, expected=0):
        with patch.object(app, 'STAGE', str(self.stage)):
            source = app.recovery_control(mask, eye)
        self.assertIn('export PATH=/system/bin:/system/xbin:/sbin TMPDIR=/tmp', source)
        self.assertIn('/proc/[0-9]*/cmdline', source)
        # Change only fixture paths and the command lookup; execute the generated
        # control flow, real shell, real tr and real awk without mocking the gate.
        source = source.replace('export PATH=/system/bin:/system/xbin:/sbin TMPDIR=/tmp',
                                'export PATH=' + shlex.quote(str(self.bin) + ':/usr/bin:/bin') +
                                ' TMPDIR=' + shlex.quote(str(self.root)))
        source = source.replace('/proc/[0-9]*/cmdline', str(self.proc) + '/[0-9]*/cmdline')
        script = self.root / 'control.sh'
        script.write_text(source)
        result = subprocess.run(['sh', str(script)], env=self.environment,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        events = self.root / 'events.jsonl'
        return [json.loads(line) for line in events.read_text().splitlines()] if events.exists() else []

    @staticmethod
    def actions(events):
        return [event['arguments'][0] for event in events if event['command'] == 'recovery']

    def assert_failure_restart(self, events):
        self.assertEqual(events[-2]['command'], 'recovery')
        self.assertEqual(events[-2]['arguments'], ['status'])
        self.assertEqual(events[-1]['command'], 'start')
        self.assertEqual(events[-1]['arguments'], ['x2d-speed-buff'])
        self.assertEqual(sum(event['command'] == 'start' for event in events), 1)

    def test_legacy_mask_only_restores_master_and_success_keeps_service_stopped(self):
        events = self.run_control(7)
        self.assertEqual(self.actions(events), ['master_off'])
        self.assertEqual(events[0], dict(command='stop', arguments=['x2d-speed-buff']))
        self.assertEqual(events[-1]['mask'], '7')
        self.assertFalse(any(event['command'] == 'start' for event in events))
        self.assertFalse(any(event['command'] == 'sleep' for event in events))

    def test_eye_mask_restores_after_master_and_preserves_exact_dispatch_mask(self):
        events = self.run_control(15, eye=True)
        self.assertEqual(self.actions(events), ['master_off', 'eye_restore'])
        self.assertEqual([event['mask'] for event in events if event['command'] == 'recovery'], ['15', '15'])
        self.assertFalse(any(event['command'] == 'start' for event in events))

    def test_service_must_report_stopped_before_any_recovery_write(self):
        self.configure(service_states=['running', 'stopping', 'stopped'])
        events = self.run_control(15, eye=True)
        first_recovery = next(index for index, event in enumerate(events) if event['command'] == 'recovery')
        states = [event['result'] for event in events[:first_recovery] if event['command'] == 'getprop']
        self.assertEqual(states, ['running', 'stopping', 'stopped'])
        self.assertEqual(sum(event['command'] == 'sleep' for event in events[:first_recovery]), 2)
        self.assertEqual(self.actions(events), ['master_off', 'eye_restore'])

    def test_service_stop_timeout_never_crosses_write_boundary_and_restarts(self):
        self.configure(service_states=['running'])
        events = self.run_control(15, eye=True, expected=42)
        self.assertEqual(self.actions(events), ['status'])
        self.assertEqual(sum(event['command'] == 'getprop' for event in events), 30)
        self.assert_failure_restart(events)

    def test_stop_command_failure_refreshes_status_even_if_refresh_also_fails(self):
        self.configure(failures={'stop': 71, 'status': 72})
        events = self.run_control(15, eye=True, expected=71)
        self.assertEqual(self.actions(events), ['status'])
        self.assertFalse(any(event['command'] == 'getprop' for event in events))
        self.assert_failure_restart(events)

    def test_failed_service_status_is_not_treated_as_an_absent_service(self):
        self.configure(service_states=['running'], failures={'getprop': 76})
        events = self.run_control(15, eye=True, expected=42)
        self.assertEqual(self.actions(events), ['status'])
        self.assertEqual(sum(event['command'] == 'getprop' for event in events), 1)
        self.assert_failure_restart(events)

    def test_every_known_nul_worker_finishes_before_write_boundary(self):
        for pid, script in ((51, '/system/etc/x2d-speed-buff/worker'),
                            (52, '/tmp/x2d-speed-buff/install'),
                            (53, '/tmp/x2d-speed-buff/restore')):
            self.cmdline(pid, ['/system/bin/sh' if pid != 52 else 'sh', script, 'status'])
        self.configure(drain_after_sleep=2, drain_pids=[51, 52, 53])
        events = self.run_control(15, eye=True)
        first_recovery = next(index for index, event in enumerate(events) if event['command'] == 'recovery')
        self.assertEqual(sum(event['command'] == 'sleep' for event in events[:first_recovery]), 2)
        self.assertEqual([event['remaining_proc'] for event in events if event['command'] == 'recovery'], [[], []])
        self.assertEqual(self.actions(events), ['master_off', 'eye_restore'])

    def test_known_worker_timeout_keeps_writes_outside_boundary(self):
        self.cmdline(61, ['sh', '/system/etc/x2d-speed-buff/worker', 'master_on'])
        events = self.run_control(15, eye=True, expected=43)
        self.assertEqual(self.actions(events), ['status'])
        self.assertEqual(sum(event['command'] == 'sleep' for event in events), 29)
        self.assertTrue((self.proc / '61/cmdline').exists())
        self.assert_failure_restart(events)

    def test_unrelated_processes_and_worker_paths_in_other_arguments_do_not_block(self):
        self.cmdline(71, ['/system/bin/sh', '/tmp/unrelated.sh', '/system/etc/x2d-speed-buff/worker'])
        self.cmdline(72, ['python3', '/system/etc/x2d-speed-buff/worker'])
        self.cmdline(73, ['sh', '/system/etc/x2d-speed-buff/worker-foreign'])
        self.cmdline(74, ['sh', str(self.stage / 'recovery'), 'status'])
        events = self.run_control(7)
        self.assertEqual(self.actions(events), ['master_off'])
        self.assertFalse(any(event['command'] == 'sleep' for event in events))
        self.assertEqual(events[-1]['remaining_proc'], ['71', '72', '73', '74'])

    def test_failed_master_restore_does_not_continue_to_eye_and_restarts(self):
        self.configure(failures={'master_off': 73})
        events = self.run_control(15, eye=True, expected=73)
        self.assertEqual(self.actions(events), ['master_off', 'status'])
        self.assert_failure_restart(events)

    def test_failed_eye_restore_refreshes_status_and_restarts_old_service(self):
        self.configure(failures={'eye_restore': 74})
        events = self.run_control(15, eye=True, expected=74)
        self.assertEqual(self.actions(events), ['master_off', 'eye_restore', 'status'])
        self.assert_failure_restart(events)

    def test_untrusted_mask_never_generates_an_executable_script(self):
        for mask in (True, False, 0, 16, '7', '7; reboot', None):
            with self.assertRaises(RuntimeError):
                app.recovery_control(mask)
        self.assertFalse((self.root / 'events.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
