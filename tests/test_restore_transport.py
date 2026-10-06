"""Restore execution stays off the short factory RPC and requires a fresh receipt."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import x2d_play_software as app


class RestoreTransportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='restore-transport-')
        self.addCleanup(temp.cleanup)
        self.stage = Path(temp.name)
        self.patches = [patch.object(app, 'STAGE', str(self.stage)),
                        patch.object(app, 'ADB_SERIAL', 'offline-camera')]
        for item in self.patches:
            item.start(); self.addCleanup(item.stop)

    def execute(self, name, source):
        (self.stage / name).write_text('#!/bin/sh\nset -eu\n' + source)
        def adb(arguments, **options):
            self.assertEqual(arguments[0], 'shell')
            self.assertEqual(options['timeout'], 180)
            return subprocess.run(['sh', '-c', arguments[1]], capture_output=True,
                                  timeout=options['timeout'])
        with patch.object(app, 'adb_call', side_effect=adb), \
             patch.object(app, 'shell', side_effect=RuntimeError('factory owner stopped')) as factory:
            output = app.run_restore_stage(name)
        factory.assert_not_called()
        return output

    def test_recovery_longer_than_factory_capture_budget_completes(self):
        started = time.monotonic()
        self.assertEqual(self.execute('recover', 'sleep 16\nprintf "worker finished\\n"\n'), 'ACTION_FINISHED')
        self.assertGreaterEqual(time.monotonic()-started, 15)
        self.assertEqual((self.stage/'recover.log').read_text(), 'worker finished\n')

    def test_restoration_receipt_survives_stopping_factory_owner(self):
        # The fixture makes the old RPC unusable before completion. The new path
        # must finish without reading or dispatching anything through that RPC.
        self.assertEqual(self.execute('restore', 'printf "owner stopped\\n"\n'), 'PLAY_SOFTWARE_RESTORED')

    def test_script_failure_never_becomes_success_even_if_it_prints_a_marker(self):
        self.assertEqual(self.execute('recover', 'echo ACTION_FINISHED\nexit 42\n'), 'RECOVERY_FAILED')
        self.assertEqual((self.stage/'recover.log').read_text(), 'ACTION_FINISHED\n')

    def test_foreign_log_symlink_or_fifo_is_not_written_or_waited_on(self):
        (self.stage/'recover').write_text('echo touched > '+str(self.stage/'touched'))
        target=self.stage/'foreign';target.write_text('preserve')
        for kind in ('symlink','fifo'):
            log=self.stage/'recover.log'
            if kind=='symlink':log.symlink_to(target)
            else:os.mkfifo(log)
            with self.subTest(kind=kind):
                self.assertEqual(self.execute('recover', 'echo touched > '+str(self.stage/'touched')+'\n'), 'RECOVERY_FAILED')
                self.assertFalse((self.stage/'touched').exists())
                self.assertEqual(target.read_text(), 'preserve')
            log.unlink()

    def test_unverified_camera_and_arbitrary_stage_never_reach_adb(self):
        for name,serial in [('recover',None),('install','offline-camera'),('recover;reboot','offline-camera')]:
            with self.subTest(name=name),patch.object(app,'ADB_SERIAL',serial),patch.object(app,'adb_call') as adb:
                with self.assertRaises(RuntimeError):app.run_restore_stage(name)
                adb.assert_not_called()

    def test_disconnect_timeout_and_bad_receipt_do_not_read_cached_state(self):
        outcomes=[subprocess.TimeoutExpired('adb',180),
                  subprocess.CompletedProcess([],1,b'ACTION_FINISHED\n',b'private identity'),
                  subprocess.CompletedProcess([],0,b'unexpected\n',b'')]
        for outcome in outcomes:
            with self.subTest(outcome=outcome),patch.object(app,'read_bytes') as read,patch.object(app,'shell') as factory,patch.object(app,'adb_call',side_effect=outcome if isinstance(outcome,Exception) else None,return_value=outcome):
                with self.assertRaisesRegex(RuntimeError,'尚未确认恢复结果') as error:app.run_restore_stage('recover')
                self.assertNotIn('private identity',str(error.exception))
                read.assert_not_called();factory.assert_not_called()

    def test_adb_budget_override_retains_serial_and_private_socket(self):
        session=Mock();session.prefix.return_value=['adb','-L','tcp:localhost:23456']
        with patch.object(app,'ADB_SESSION',session),patch.object(app.subprocess,'run') as run:
            app.adb_call(['shell','fixed'],timeout=180)
            self.assertEqual(run.call_args.args[0],session.prefix()+['-s','offline-camera','shell','fixed'])
            self.assertEqual(run.call_args.kwargs['timeout'],180)
            app.adb_call(['push','local','fixed'])
            self.assertEqual(run.call_args.kwargs['timeout'],30)


if __name__=='__main__':unittest.main()
