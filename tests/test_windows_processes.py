"""Exit/ownership regressions with no camera or real Windows driver access."""
import ctypes as C
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import windows_processes as p
import x2d_play_software as camera


class Child:
    def __init__(self):
        self._handle = 123
        self.code = None
        self.terminated = self.killed = False
    def poll(self): return self.code
    def terminate(self): self.terminated = True; self.code = 0
    def kill(self): self.killed = True; self.code = 0
    def wait(self, timeout=None): return self.code


class Processes(unittest.TestCase):
    def setUp(self):
        reservation = MagicMock()
        reservation.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 23456)
        sockets = patch.object(p.socket, 'socket', return_value=reservation)
        sockets.start(); self.addCleanup(sockets.stop)

    def test_close_before_launch_prevents_late_worker(self):
        check = p.UpdateCheck(); check.close()
        with patch.object(p.subprocess, 'Popen') as launch:
            self.assertIsNone(check.launch(['unused']))
            launch.assert_not_called()

    def test_close_stops_real_blocked_check_and_releases_file_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'check-output.txt'
            with path.open('w') as output:
                check = p.UpdateCheck()
                child = check.launch([sys.executable, '-c', 'import time; time.sleep(60)'],
                    cwd=folder, stdout=output, stderr=subprocess.DEVNULL)
                check.close(); check.close()
                self.assertIsNotNone(child.poll())
            renamed = Path(folder).with_name(Path(folder).name+'-moved')
            Path(folder).rename(renamed); renamed.rename(folder)

    def test_close_serializes_with_inflight_launch(self):
        entered, resume = threading.Event(), threading.Event()
        child = Child(); check = p.UpdateCheck()
        def launch(*a, **kw): entered.set(); resume.wait(5); return child
        with patch.object(p.subprocess, 'Popen', side_effect=launch):
            worker = threading.Thread(target=lambda: check.launch(['unused']))
            worker.start(); self.assertTrue(entered.wait(2))
            closer = threading.Thread(target=check.close); closer.start()
            resume.set(); worker.join(2); closer.join(2)
            self.assertFalse(worker.is_alive()); self.assertFalse(closer.is_alive())
        self.assertTrue(child.terminated)

    def test_timeout_kills_only_owned_child_then_waits(self):
        child = Child()
        child.terminate = Mock()
        child.wait = Mock(side_effect=[subprocess.TimeoutExpired('owned', 2), 0])
        p.stop_process(child)
        self.assertTrue(child.killed)
        self.assertEqual(child.wait.call_count, 2)

    def test_private_adb_uses_foreground_loopback_and_releases_job(self):
        job = Mock(); child = Child()
        session = p.ADBSession('adb.exe', job_factory=lambda: job)
        self.assertTrue(session.endpoint.startswith('tcp:127.0.0.1:'))
        self.assertNotEqual(session.endpoint, 'tcp:127.0.0.1:5037')
        with patch.object(p.subprocess, 'Popen', return_value=child) as launch, patch.object(p, 'server_ready', return_value=True):
            session.start(Mock(), Mock())
        self.assertEqual(launch.call_args.args[0], session.prefix()+['server','nodaemon'])
        self.assertNotIn('start-server', launch.call_args.args[0])
        self.assertIsNot(launch.call_args.kwargs['stdout'], subprocess.PIPE)
        job.attach.assert_called_once_with(child)
        output = session.output
        session.close(); session.close()
        self.assertTrue(child.terminated); self.assertTrue(output.closed)
        job.close.assert_called_once()

    def test_failed_job_assignment_does_not_leave_adb_running(self):
        job = Mock(); job.attach.side_effect = OSError('refused')
        child = Child(); session = p.ADBSession('adb.exe', job_factory=lambda: job)
        with patch.object(p.subprocess, 'Popen', return_value=child):
            with self.assertRaisesRegex(OSError, 'refused'): session.start(Mock(), Mock())
        self.assertTrue(child.terminated); job.close.assert_called_once()

    def test_failed_and_timed_out_startup_release_owned_server(self):
        for code in (1, None):
            child = Child(); child.code = code; job = Mock()
            session = p.ADBSession('adb.exe', job_factory=lambda: job)
            with patch.object(p.subprocess, 'Popen', return_value=child), patch.object(p, 'server_ready', return_value=False), patch.object(p.time, 'monotonic', side_effect=[0,0,91]):
                with self.assertRaises(RuntimeError): session.start(Mock(), lambda *a:'failed')
            job.close.assert_called_once()
            self.assertIsNone(session.output)
            if code is None: self.assertTrue(child.terminated)

    def test_host_probe_handles_partial_reply_without_running_adb_client(self):
        stream = Mock(); stream.recv.side_effect = [b'O', b'KAY']
        connection = Mock(); connection.__enter__ = Mock(return_value=stream); connection.__exit__ = Mock()
        with patch.object(p.socket, 'create_connection', return_value=connection), patch.object(p.subprocess, 'Popen') as launch:
            self.assertTrue(p.server_ready('tcp:127.0.0.1:23456'))
            stream.sendall.assert_called_once_with(b'000chost:version')
            launch.assert_not_called()

    def test_all_camera_adb_commands_keep_private_socket_and_serial(self):
        session = Mock(); session.prefix.return_value = ['adb.exe','-L','tcp:127.0.0.1:23456']
        with patch.object(camera, 'ADB_SESSION', session), patch.object(camera, 'ADB_SERIAL', 'offline-camera'), patch.object(camera.subprocess, 'run') as run:
            camera.adb_call(['push','local','fixed-target'])
        self.assertEqual(run.call_args.args[0],session.prefix()+['-s','offline-camera','push','local','fixed-target'])

    def test_camera_action_failure_also_closes_private_server(self):
        session = Mock()
        with patch.object(camera, 'ADB_SESSION', session), patch.object(sys, 'argv', ['tool','install']), patch.object(camera, 'install', side_effect=RuntimeError('failed')):
            with self.assertRaisesRegex(RuntimeError,'failed'): camera.main()
            self.assertIsNone(camera.ADB_SESSION)
        session.close.assert_called_once()

    def test_windows_job_uses_correct_x64_layout_and_kill_on_close(self):
        self.assertEqual(C.sizeof(p.BasicLimits),64)
        self.assertEqual(C.sizeof(p.ExtendedLimits),144)
        kernel = Mock(); kernel.CreateJobObjectW.return_value = 999
        kernel.SetInformationJobObject.return_value = kernel.AssignProcessToJobObject.return_value = 1
        with patch.object(p.C, 'WinDLL', return_value=kernel, create=True):
            job = p.ProcessJob(); job.attach(Child()); job.close(); job.close()
        args = kernel.SetInformationJobObject.call_args.args
        self.assertEqual(args[1],9); self.assertEqual(args[2]._obj.basic.flags,0x2000)
        self.assertEqual(args[3],144)
        kernel.CloseHandle.assert_called_once_with(999)


if __name__ == '__main__': unittest.main()
