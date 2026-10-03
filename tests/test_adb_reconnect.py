"""离线状态机检查：Windows 提示、USB 重枚举与固件门禁。"""
import subprocess, unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch
import x2d_play_software as app

LINE = 'usb-camera device usb:1 device:eagle2_ec1706_native\n'

class Clock:
    def __init__(self): self.now = 0.0
    def monotonic(self): return self.now
    def sleep(self, duration): self.now += duration


class StartClient:
    def __init__(self, clock, ready_after, code=0):
        self.clock=clock; self.ready_after=ready_after; self.code=code
        self.stopped=False; self.terminated=False
    def poll(self):
        return self.code if self.stopped or self.clock.now >= self.ready_after else None
    def terminate(self): self.terminated=True; self.stopped=True
    def kill(self): self.stopped=True
    def wait(self, timeout): return self.code


class ReconnectTests(unittest.TestCase):
    def setUp(self):
        for name,value in [('ADB_SERIAL',None)]:
            patcher=patch.object(app,name,value);patcher.start();self.addCleanup(patcher.stop)
    def scenario(self, adb_after=0, factory_after=0, already=False, switch_error=None, unknown=False, active_after=0, hash_delay=0, platform='posix'):
        clock = Clock(); mode = {'adb':already}
        reader = MagicMock()
        reader.factory_shell.side_effect = lambda command, **kwargs: (
            'rndis,mass_storage,bulk,acm,adb' if mode['adb'] and
            (command.endswith('config') or clock.now >= active_after) else 'rndis,mass_storage,bulk,acm')
        context = MagicMock()
        def enter():
            if mode['adb'] and clock.now < factory_after:
                raise app.usb.UsbFactoryError('USB camera was not enumerated')
            return reader
        context.__enter__.side_effect = enter
        context.__exit__.return_value = False
        def run(args, **kwargs):
            if 'devices' in args:
                return MagicMock(returncode=0, stdout=LINE if mode['adb'] and clock.now >= adb_after else '')
            if 'get-serialno' in args:
                return MagicMock(returncode=0, stdout='usb-camera\n')
            raise AssertionError(args)
        def switch(*args):
            mode['adb'] = True
            if switch_error: raise switch_error
        def validate(*args):
            if unknown and mode['adb']:
                raise app.usb.UsbFactoryError('unknown /system/bin/camera-gui; refusing write')
            if mode['adb'] and hash_delay:
                budget=args[0].timeout_ms / 1000
                clock.sleep(min(budget,hash_delay))
                if budget < hash_delay:
                    raise app.usb.UsbFactoryError('timed out waiting for USB HblShell result: sha256sum /system/bin/camera-gui')
        def make_reader(timeout=15000):
            reader.timeout_ms=timeout
            return context
        with ExitStack() as stack:
            stack.enter_context(patch.object(app, 'prepare_adb_server'))
            stack.enter_context(patch.object(app.os, 'name', platform))
            stack.enter_context(patch.object(app.time, 'monotonic', clock.monotonic))
            stack.enter_context(patch.object(app.time, 'sleep', clock.sleep))
            stack.enter_context(patch.object(app.subprocess, 'run', side_effect=run))
            stack.enter_context(patch.object(app, 'reader', side_effect=make_reader))
            stack.enter_context(patch.object(app.usb, 'validate_factory_gui_target', side_effect=validate))
            switch_call = stack.enter_context(patch.object(app.usb, 'run_factory_set_usb_adb_runtime', side_effect=switch))
            events = stack.enter_context(patch.object(app, 'event'))
            upload = stack.enter_context(patch.object(app, 'upload'))
            try:
                app.ensure_adb()
            finally:
                upload.assert_not_called()
        return clock, switch_call, events

    def test_legacy_factory_driver_delay_longer_than_20_seconds_is_tolerated(self):
        clock, switch, events = self.scenario(adb_after=45, factory_after=48)
        self.assertGreaterEqual(clock.now, 48.5)
        self.assertEqual(switch.call_count, 1)
        self.assertEqual(app.ADB_SERIAL, 'usb-camera')
        self.assertTrue(any('校验通过' in call.kwargs.get('message','') for call in events.call_args_list))

    def test_windows_reconnect_checks_factory_and_never_calls_adb_shell(self):
        clock, switch, events = self.scenario(adb_after=45, factory_after=48, platform='nt')
        self.assertGreaterEqual(clock.now,48.5)
        switch.assert_called_once()
        self.assertTrue(any('工厂接口校验通过' in call.kwargs.get('message','') for call in events.call_args_list))

    def test_windows_existing_adb_keeps_factory_validation_without_reswitch(self):
        clock, switch, events = self.scenario(already=True, platform='nt',hash_delay=2.5)
        switch.assert_not_called()
        self.assertGreaterEqual(clock.now,5.5)

    def test_disconnected_dispatch_reply_requires_fresh_verified_reconnect(self):
        cause = RuntimeError('device disconnected'); cause.backend_error_code = -4
        error = app.usb.UsbFactoryError('HblShell USB bulk read failed'); error.__cause__ = cause
        self.scenario(adb_after=3, factory_after=5, switch_error=error)

    def test_retry_with_adb_already_enabled_does_not_switch_usb_again(self):
        clock, switch, events = self.scenario(already=True, adb_after=5)
        switch.assert_not_called()

    def test_unknown_firmware_after_reconnect_is_not_retried_or_accepted(self):
        with self.assertRaisesRegex(app.usb.UsbFactoryError, 'unknown'):
            self.scenario(unknown=True)

    def test_failed_switch_access_is_not_treated_as_normal_reconnect(self):
        cause = RuntimeError('access denied'); cause.backend_error_code = -3
        error = app.usb.UsbFactoryError('HblShell USB write failed'); error.__cause__ = cause
        with self.assertRaises(app.usb.UsbFactoryError): self.scenario(switch_error=error)

    def test_adb_missing_driver_has_specific_timeout(self):
        with self.assertRaisesRegex(RuntimeError, '等待 ADB 超时'):
            self.scenario(adb_after=999)

    def test_factory_missing_driver_has_specific_timeout(self):
        with self.assertRaisesRegex(RuntimeError, '工厂接口尚未枚举'):
            self.scenario(factory_after=999)

    def test_gui_hash_longer_than_short_probe_can_complete(self):
        clock,switch,events=self.scenario(hash_delay=2.5)
        self.assertGreaterEqual(clock.now,5.5)
        self.assertLess(clock.now,120)
        self.assertEqual(switch.call_count,1)

    def test_gui_hash_timeout_identifies_step_without_private_data(self):
        message=app.factory_reconnect_error(app.usb.UsbFactoryError(
            'timed out waiting for USB HblShell result: sha256sum /system/bin/camera-gui private-user'))
        self.assertIn('GUI 文件校验超时',message)
        self.assertNotIn('private-user',message)

    def test_reconnect_access_refusal_preserves_usb_code(self):
        cause=RuntimeError('private path'); cause.backend_error_code=-3
        error=app.usb.UsbFactoryError('USB factory interface failed'); error.__cause__=cause
        self.assertEqual(app.factory_reconnect_error(error),'工厂接口访问被拒绝（USB 错误码 -3）')

    def test_inactive_gadget_is_distinguished_from_factory_driver_failure(self):
        with self.assertRaisesRegex(RuntimeError,'USB 配置未报告 ADB 已生效'):
            self.scenario(active_after=999)

    def test_stale_production_gadget_is_not_accepted_before_switch_finishes(self):
        clock, switch, events = self.scenario(active_after=8)
        self.assertGreaterEqual(clock.now, 8.5)

    def startup(self, ready_after, code=0, diagnostic='', launch_error=None):
        clock=Clock(); client=StartClient(clock, ready_after, code)
        def launch(*args, **kwargs):
            if launch_error: raise launch_error
            # The long-lived server must not inherit capture pipes.
            self.assertEqual(kwargs['stdin'], subprocess.DEVNULL)
            self.assertNotEqual(kwargs['stdout'], subprocess.PIPE)
            self.assertIs(kwargs['stdout'], kwargs['stderr'])
            kwargs['stderr'].write(diagnostic.encode()); kwargs['stderr'].flush()
            return client
        with ExitStack() as stack:
            stack.enter_context(patch.object(app.time,'monotonic',clock.monotonic))
            stack.enter_context(patch.object(app.time,'sleep',clock.sleep))
            popen=stack.enter_context(patch.object(app.subprocess,'Popen',side_effect=launch))
            events=stack.enter_context(patch.object(app,'event'))
            switch=stack.enter_context(patch.object(app.usb,'run_factory_set_usb_adb_runtime'))
            upload=stack.enter_context(patch.object(app,'upload'))
            try:
                app.prepare_adb_server()
            finally:
                popen.assert_called_once()
                switch.assert_not_called(); upload.assert_not_called()
                self.last_client=client; self.last_clock=clock
        return client, clock, events

    def test_slow_adb_scan_preserves_single_start_client(self):
        client,clock,events=self.startup(45)
        self.assertEqual(clock.now,45)
        self.assertFalse(client.terminated)
        self.assertGreater(events.call_count,5)

    def test_adb_ready_without_any_windows_prompt_returns_immediately(self):
        client,clock,events=self.startup(0)
        self.assertEqual(clock.now,0)
        self.assertFalse(client.terminated)

    def test_startup_timeout_stops_only_owned_client_before_camera_write(self):
        with self.assertRaisesRegex(RuntimeError,'启动超时（90 秒）'):
            self.startup(999)
        self.assertTrue(self.last_client.terminated)
        self.assertEqual(self.last_clock.now,90)

    def test_failed_startup_reports_port_conflict_without_private_output(self):
        with self.assertRaisesRegex(RuntimeError,'端口 5037') as error:
            self.startup(0,1,'cannot bind: Address already in use C:/diagnostic/example')
        self.assertNotIn('private-user',str(error.exception))
        self.assertEqual(self.last_clock.now,0)

    def test_missing_adb_dll_has_specific_chinese_failure(self):
        with self.assertRaisesRegex(RuntimeError,'运行组件缺失'):
            self.startup(0,-1073741515)

    def test_process_launch_access_refusal_is_specific_and_not_retried(self):
        with self.assertRaisesRegex(RuntimeError,'阻止了 ADB 启动'):
            self.startup(0,launch_error=PermissionError(13,'private path'))

    def test_unknown_failure_preserves_numeric_code_without_raw_text(self):
        with self.assertRaisesRegex(RuntimeError,'退出码 7') as error:
            self.startup(0,7,'unknown detail private-user')
        self.assertNotIn('private-user',str(error.exception))

if __name__ == '__main__': unittest.main()
