#!/usr/bin/env python3
"""X2D / 907X 100C shared 4.2.0 software: guarded USB install and restore."""
import argparse, base64, contextlib, hashlib, io, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
from reinstall_confirmation import CONTINUE, prompt as reinstall_prompt
D = Path(__file__).resolve().parent
sys.path.insert(0, str(D / 'transport'))
import collect_x2d_af_usb as usb
ROOT = '/blackbox/.x2d-play-software'
STAGE = ROOT + '/stage'
RC = '/system/etc/init/camera-gui.rc'
O = Path(os.environ.get('X2D_PAYLOAD_DIR', str(D / 'native-package')))
DISPLAY_RC = '/system/etc/init/camera-system.rc'
DISPLAY_SYSTEM_SHA = 'bf854a21881148565ff2cc00376426c37a2b82fed94c653abf024e23ed4ceda6'
DISPLAY_STOCK_RC = 'd43b8b26282f9e1da5825b96699658d444a58a83cda94b622e7da8aa1c35202b'
BRIGHTNESS_PREF = '/blackbox/x2d-play-auto-brightness.enabled'
BRIGHTNESS_FEATURE = '/blackbox/x2d-play-auto-brightness.available'
PREVIOUS_DISPLAY_BRIGHTNESS_SHA = '73d13e8fe5d8295121b47a76fc4c553a71ae1c66cee7b8e6565ec5bf6813ed7a'
PREVIOUS_BRIGHTNESS_SHA = '12a2c8b4785c349e13b03197b692ed1eb4d79cf291a059bf2ec077e50191310e'
PREVIOUS_042_SHA = '34a32083a442cc667e56d311bcd9ea583a15e7f076c39f6cdc4c8e67c9024635'
STOCK_RC = '1d6a8f9e41e269be38b3fb9ba53f4c47d18007f413c90893fdfa9d7542d1f688'
STOCK_GUI = '16391452abdc69de9e0807e065c0f4ab3f1ccb5fc288f6fc4e6f5cb3bdca12e0'
ADB_NAME = 'adb.exe' if os.name == 'nt' else 'adb'
ADB = str(D / 'bin' / ADB_NAME) if (D / 'bin' / ADB_NAME).exists() else ADB_NAME
PROCESS_OPTIONS = dict(creationflags=0x08000000) if os.name == 'nt' else {}
ADB_SERIAL = None
ADB_SESSION = None
INTERACTIVE_CONFIRMATION = False
REINSTALL_CONFIRMED = False
SUPPORTED_USB_PIDS = (0x0009, 0x000A)  # stock setup_product_props.sh: X2D / CFV 100C
PREVIOUS_BUNDLE_SHA = '0cc1e1f8b45fd4416c5449320ec2000a2e53298eb07932f1958c1192928849b6'
PREVIOUS_033_SHA = 'c2ec66226c15442637cbe4332b2fcd9083603faf2dc26628156231a2c9b96f77'
PREVIOUS_032_SHA = '9711b81f42e8620691f10b414ff719203680ab3d18aade0856bc49308d7875ee'
PRANK_FLAG = ROOT + '/prank-ibis'
PREVIOUS_030_SHA = 'b6a2e2e890e2424ca8861c6fe1b9c1605ae04a1fb87642fc06f8858c8c197c00'
sha = lambda b: hashlib.sha256(b).hexdigest()
USB_LIBRARY = D / 'lib' / ('libusb-1.0.dll' if os.name == 'nt' else 'libusb-1.0.dylib')
USB_RUNTIME_ERROR = False
if os.name != 'nt' and USB_LIBRARY.exists():
    try:
        import usb.core as usb_core
        import usb.backend.libusb1 as libusb_backend
        _backend = libusb_backend.get_backend(find_library=lambda _: str(USB_LIBRARY))
        if _backend is None:
            USB_RUNTIME_ERROR = True
        else:
            _find = usb_core.find
            def _bundled_find(*args, **kwargs):
                kwargs.setdefault('backend', _backend)
                return _find(*args, **kwargs)
            usb_core.find = _bundled_find
    except Exception:
        USB_RUNTIME_ERROR = True


def event(kind, **values):
    print('X2D_EVENT ' + json.dumps(dict(type=kind, **values), ensure_ascii=False), flush=True)


def reader(timeout=15000):
    if os.name == 'nt':
        from windows_factory_usb import WindowsFactoryReader
        return WindowsFactoryReader(timeout)
    if USB_RUNTIME_ERROR:
        raise usb.UsbFactoryError('bundled USB runtime failed to load')
    core, _ = usb._load_usb()
    try:
        devices = [device for device in (core.find(find_all=True,idVendor=usb.DEFAULT_VID) or [])
                   if device.idProduct in SUPPORTED_USB_PIDS]
    except Exception as error:
        raise usb.UsbFactoryError('PyUSB backend enumeration failed') from error
    if not devices: raise usb.UsbFactoryError('USB camera was not enumerated')
    if len(devices) != 1: raise RuntimeError('检测到多台相机，请只连接一台后重新检查')
    return usb.FactoryUsbReader(usb.DEFAULT_VID, devices[0].idProduct, usb.DEFAULT_INTERFACE,
                               usb.DEFAULT_ALTSETTING, usb.DEFAULT_OUT_ENDPOINT,
                               usb.DEFAULT_IN_ENDPOINT, timeout)


def shell(command):
    if len(command.encode('ascii')) > 231: raise RuntimeError('Internal command length exceeded')
    with reader() as r:
        return r.factory_shell(command, capture_ms=15000).strip()


def read_bytes(path):
    if not re.fullmatch(r'/[A-Za-z0-9/_.-]+', path): raise RuntimeError('Invalid fixed path')
    return base64.b64decode(shell('base64 ' + path), validate=False)


def adb_call(args, **options):
    prefix = adb_prefix() + (['-s', ADB_SERIAL] if ADB_SERIAL else [])
    options.setdefault('stdin', subprocess.DEVNULL)
    return subprocess.run(prefix + args, capture_output=True, timeout=30, **PROCESS_OPTIONS, **options)


def adb_prefix():
    return ADB_SESSION.prefix() if ADB_SESSION is not None else [ADB]


def close_adb_session():
    global ADB_SESSION
    if ADB_SESSION is not None:
        session, ADB_SESSION = ADB_SESSION, None
        session.close()


def physical_adb_candidates(output):
    # Windows adb may omit usb:; `adb -d` supplies only a physical USB transport.
    candidates = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[1] != 'device': continue
        if 'device:eagle2_ec1706_native' not in fields: continue
        if not any(x.startswith('usb:') for x in fields) and os.name != 'nt': continue
        if ':' in fields[0]: continue  # IP:port and wireless TLS identifiers are excluded.
        if not re.fullmatch(r'[A-Za-z0-9._-]+', fields[0]): continue
        candidates.append(fields[0])
    return candidates


def expected_usb_transition(error):
    # Only the fixed gadget switch may tolerate a disappearing reply channel.
    # It still needs fresh ADB + factory + firmware readback before any upload.
    return usb_failure_code(error) in (-4, -7) or 'timed out' in str(error).lower()


def adb_start_failure(code, output):
    # Classify fixed diagnostic tokens; never expose paths, identities or raw output.
    message = output.lower()
    status = code & 0xffffffff
    if status == 0xc0000135:
        return 'ADB 运行组件缺失，请完整解压安装包，保留 bin 目录内的两个 DLL'
    if status in (0xc000007b, 0xc000012f):
        return 'ADB 运行组件格式不正确，请重新解压完整的 Windows x64 安装包'
    if 'listening on specified hostname currently unsupported' in message:
        return 'ADB 本机通信参数不兼容，请更新至最新工具包后重试；相机安装尚未开始'
    if any(token in message for token in ('access is denied', 'permission denied', '10013')):
        return 'Windows 拒绝 ADB 启动或本机通信，请检查刚才的系统提示和安全软件记录'
    if any(token in message for token in ('cannot bind', 'address already in use', '10048')):
        if ADB_SESSION is not None:
            return 'ADB 独立本机端口无法使用，请检查系统网络权限后重试'
        return 'ADB 本机端口无法使用，请关闭其他使用 ADB 的程序后重试（端口 5037）'
    if 'server version' in message and "doesn't match" in message:
        return '电脑中其他版本的 ADB 与本应用冲突，请关闭使用 ADB 的程序后重试'
    return 'ADB 启动失败（退出码 ' + str(code) + '），请检查系统提示及安全软件记录，并反馈此提示'


def prepare_adb_server():
    global ADB_SESSION
    event('progress', message='正在准备 ADB；如 Windows 弹出允许提示，请先处理提示', percent=10)
    if os.name == 'nt':
        from windows_processes import ADBSession
        if ADB_SESSION is None: ADB_SESSION = ADBSession(ADB)
        ADB_SESSION.start(event, adb_start_failure)
        return
    # Keep ONE start client alive: the server waits for its USB scan before ACK.
    # Killing the client every five seconds can interrupt that handshake. Regular
    # files avoid waiting for EOF on pipes inherited by a background server.
    with tempfile.TemporaryFile() as output:
        try:
            child = subprocess.Popen([ADB, 'start-server'], stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=output, **PROCESS_OPTIONS)
        except OSError as error:
            code = getattr(error, 'winerror', None) or error.errno or 0
            if code in (2, 3):
                detail = '未找到内置 ADB，请完整解压安装包，保留 bin 目录'
            elif code in (5, 13, 740):
                detail = 'Windows 阻止了 ADB 启动，请检查系统提示和安全软件记录'
            elif code == 193:
                detail = 'ADB 程序格式不正确，请重新解压 Windows x64 安装包'
            else:
                detail = '无法启动 ADB（系统错误码 ' + str(code) + '），请反馈此提示'
            raise RuntimeError(detail + '；相机安装尚未开始') from None
        deadline = time.monotonic() + 90
        last_notice = time.monotonic()
        try:
            while True:
                code = child.poll()
                if code is not None:
                    if code == 0: return
                    output.seek(0, os.SEEK_END)
                    output.seek(max(0, output.tell() - 65536))
                    detail = adb_start_failure(code, output.read().decode('utf-8', errors='replace'))
                    raise RuntimeError(detail + '；相机安装尚未开始')
                if time.monotonic() >= deadline:
                    raise RuntimeError('等待 ADB 启动超时（90 秒），请完成 Windows 的提示并检查是否有其他 ADB 程序或安全软件拦截，再重试；相机安装尚未开始')
                if time.monotonic() - last_notice >= 5:
                    event('progress', message='正在等待 ADB 完成启动，请处理 Windows 提示；相机安装尚未开始', percent=10)
                    last_notice = time.monotonic()
                time.sleep(0.25)
        finally:
            if child.poll() is None:
                # Only the client created above is stopped; never kill a system server.
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=5)


def ensure_adb():
    global ADB_SERIAL
    ADB_SERIAL = None
    prepare_adb_server()
    waiting = 'ADB'
    def choose():
        global ADB_SERIAL
        try:
            result = subprocess.run(adb_prefix() + ['devices', '-l'], capture_output=True, text=True, timeout=5, **PROCESS_OPTIONS)
        except subprocess.TimeoutExpired:
            return False
        if result.returncode: return False
        matches = physical_adb_candidates(result.stdout)
        if len(matches) > 1: raise RuntimeError('请只连接一台相机')
        if matches:
            if os.name == 'nt':
                try:
                    physical = subprocess.run(adb_prefix() + ['-d', 'get-serialno'], capture_output=True, text=True, timeout=5, **PROCESS_OPTIONS)
                except subprocess.TimeoutExpired:
                    return False
                if physical.returncode or physical.stdout.strip() != matches[0]: return False
            if not re.fullmatch(r'[A-Za-z0-9._:-]+', matches[0]): raise RuntimeError('Invalid ADB identity')
            if ADB_SERIAL is not None and ADB_SERIAL != matches[0]:
                raise RuntimeError('相机连接对象已变化，请重新点击“已连接”检查状态')
            ADB_SERIAL = matches[0]
            return True
        return False
    if not choose():
        with reader() as r:
            usb.validate_factory_gui_target(r)
            config = r.factory_shell('getprop sys.usb.config').strip()
            if 'adb' not in config.split(','):
                event('progress', message='正在启用临时 USB 传输通道；相机 USB 会自动重新连接', percent=12)
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        usb.run_factory_set_usb_adb_runtime(r, True)
                except usb.UsbFactoryError as error:
                    if not expected_usb_transition(error): raise
                    event('progress', message='USB 正在重新连接，等待相机和 ADB 恢复，请保持数据线连接', percent=13)
            else:
                event('progress', message='相机 ADB 通道已开启，正在等待 Windows 识别；请保持连接', percent=13)
    deadline = time.monotonic() + 120
    last_notice = -10
    last_factory_error = None
    last_factory_notice = None
    stable = 0
    while time.monotonic() < deadline:
        ready = False
        if choose():
            waiting = '工厂接口'
            try:
                # Full GUI hashing needs the same budget as the initial check;
                # a 1.5 s reconnect probe was also limiting sha256sum's reply.
                with reader() as r:
                    usb.validate_factory_gui_target(r)
                    active = r.factory_shell('getprop sys.usb.state', capture_ms=5000).strip()
                ready = 'adb' in active.split(',')
                waiting = '工厂接口' if ready else '相机 USB 配置生效'
                last_factory_error = None
            except usb.UsbFactoryError as error:
                # Unknown target/firmware is a hard failure even during reconnect.
                message = str(error).lower()
                if 'unexpected camera target' in message or 'unknown /system/bin/camera-gui' in message or 'cannot parse' in message:
                    raise
                last_factory_error = factory_reconnect_error(error)
                if last_factory_error != last_factory_notice:
                    event('progress', message='ADB 已连接；' + last_factory_error + '。正在重试，传输尚未开始', percent=13)
                    last_factory_notice = last_factory_error
        else:
            waiting = 'ADB'
        stable = stable + 1 if ready else 0
        if stable >= 2:
            event('progress', message='USB 已重新连接，ADB 与工厂接口校验通过', percent=16)
            return
        if time.monotonic() - last_notice >= 5:
            notice = ('ADB 已连接，正在等待' + waiting + '完成校验；请保持数据线连接'
                      if waiting != 'ADB' else '正在等待相机 ADB 接口；请保持连接，若 Windows 有提示请处理')
            event('progress', message=notice, percent=13)
            last_notice = time.monotonic()
        time.sleep(0.5)
    if waiting == '工厂接口':
        detail = last_factory_error or '工厂接口未通过重连校验'
        raise RuntimeError('ADB 已识别，但工厂接口校验未完成：' + detail + '；请反馈这条完整提示。传输尚未开始')
    if waiting == '相机 USB 配置生效':
        raise RuntimeError('ADB 与工厂接口均已识别，但相机 USB 配置未报告 ADB 已生效；请反馈此提示。传输尚未开始')
    raise RuntimeError('等待 ADB 超时；请检查 Windows 的 ADB 提示和相机 ADB 接口驱动，再重试。传输尚未开始')


def factory_reconnect_error(error):
    message = str(error).lower()
    if str(error).startswith('Windows 工厂接口'):
        return str(error)
    if 'timed out' in message or 'timeout' in message:
        if 'sha256sum /system/bin/camera-gui' in message:
            return '工厂接口的 GUI 文件校验超时（单次等待 15 秒）'
        if 'getprop ro.product.device' in message:
            return '工厂接口的机型读取超时（单次等待 15 秒）'
        if 'getprop sys.usb.state' in message:
            return '工厂接口的 USB 状态读取超时（单次等待 5 秒）'
        return '工厂接口通信超时'
    code = usb_failure_code(error)
    reasons = {-3:'工厂接口访问被拒绝', -4:'工厂接口已断开', -6:'工厂接口被其他程序占用',
               -7:'工厂接口通信超时', -12:'工厂接口驱动不支持当前操作'}
    if code is not None:
        return reasons.get(code,'工厂接口通信失败') + '（USB 错误码 ' + str(code) + '）'
    if 'not enumerated' in message:
        return '工厂接口尚未枚举，需检查相机 Interface 3 的驱动'
    if 'interface' in message or 'endpoints' in message:
        return '工厂接口或端点布局不符合预期'
    return '工厂接口未完成通信（重连检查 05）'


def upload(name, data):
    if not re.fullmatch('[a-z]+', name): raise RuntimeError('Invalid fixed upload name')
    if shell('test ! -L ' + STAGE + '/' + name + ' && echo SAFE') != 'SAFE':
        raise RuntimeError('暂存路径不是普通文件')
    with tempfile.TemporaryDirectory(prefix='x2d-play-') as tmp:
        local = Path(tmp) / name
        local.write_bytes(data)
        result = adb_call(['push', str(local), STAGE + '/' + name])
        if result.returncode:
            raise RuntimeError('USB 文件传输失败，请检查数据线后重试')
    if shell('sha256sum ' + STAGE + '/' + name).split()[0] != sha(data):
        raise RuntimeError('上传文件校验失败')
    if name in ('install', 'restore'):
        if shell('sh -n ' + STAGE + '/' + name + ' && echo SYNTAX_OK') != 'SYNTAX_OK':
            raise RuntimeError('相机端安装脚本未通过语法检查')


def verify_target():
    with reader() as r: usb.validate_factory_gui_target(r)
    # Both models must have these exact shared firmware files; a model label is insufficient.
    for path, expected in {
        '/system/lib64/libaaa.so': 'feef8a8dc3a27395e47232c2b25a5da7a7ab335922fbb527e637c439e35bcec7',
        '/system/bin/camera-service': 'fbcf828f73bca13f0c8b95e7dd0b95ac483ae36954ec06179098c8a1a65f9f82',
    }.items():
        if shell('sha256sum ' + path).split()[0] != expected:
            raise RuntimeError('相机关键文件不属于本版共用的 4.2.0 系统，检查未通过')
    mount = shell("awk '$2==\"/system\"{print $1,$3,$4}' /proc/mounts")
    if not re.fullmatch(r'/dev/block/mmcblk0p1[67] ext4 ro,.*', mount):
        raise RuntimeError('系统挂载状态不符合安装要求')
    return mount


def camera_model():
    # Stock setup_product_props.sh sets this pair from the hardware family.
    values = shell('getprop hbl.usb_pid;getprop hbl.usb_prod_name').splitlines()
    if values == ['0x0009', 'X2D 100C']: return 'X2D 100C'
    if values == ['0x000A', 'CFV 100C']: return '907X & CFV 100C'
    raise RuntimeError('相机型号标识未通过校验，请重新检查连接')


def header():
    return '''#!/system/bin/sh
set -eu
export PATH=/system/bin:/system/xbin:/sbin TMPDIR=/tmp
hashok() { [ "$(sha256sum "$1" | awk '{print $1}')" = "$2" ]; }
state() { awk '$2=="/system"{print $1,$3,$4}' /proc/mounts; }
original_mount=$(state)
case "$original_mount" in '/dev/block/mmcblk0p16 ext4 ro,'*|'/dev/block/mmcblk0p17 ext4 ro,'*) ;; *) exit 30;; esac
'''


def prepare():
    manifest = json.loads((O / 'speed-bundle.json').read_text())
    if manifest.get('format') != 3 or manifest.get('guiSha256') != STOCK_GUI:
        raise RuntimeError('安装包版本不匹配')
    for f in manifest['files']:
        if sha((O / f['source']).read_bytes()) != f['sha256']:
            raise RuntimeError('本地安装包校验失败')
    languages = manifest.get('uiLanguages') or {}
    for language in ('en', 'zh-Hant'):
        overlay = languages.get(language) or []
        if language == 'en' and not overlay:
            raise RuntimeError('安装包缺少英文相机界面文件')
        for f in overlay:
            if sha((O / f['source']).read_bytes()) != f['sha256']:
                raise RuntimeError('本地安装包校验失败')
    if manifest.get('autoBrightness'):
        spec = manifest['autoBrightness']
        if spec != dict(systemSha256=DISPLAY_SYSTEM_SHA, stockConfigSha256=DISPLAY_STOCK_RC,
                        library='/system/lib64/libx2d_play_brightness.so', default='off', masterControlled=True):
            raise RuntimeError('自动亮度安装包校验失败')
        if not any(f['target'] == spec['library'] for f in manifest['files']):
            raise RuntimeError('自动亮度安装包校验失败')
    return manifest


def apply_ui_language(manifest, language='zh'):
    if language == 'zh':
        return manifest
    if language not in ('en', 'zh-Hant'):
        raise RuntimeError('Unsupported camera UI language')
    overlay = (manifest.get('uiLanguages') or {}).get(language)
    if not overlay:
        raise RuntimeError('安装包缺少所选语言的相机界面文件')
    by_target = {entry['target']: entry for entry in overlay}
    selected = dict(manifest)
    selected['files'] = [by_target.get(entry['target'], entry) for entry in manifest['files']]
    return selected


def same_release_files(files, package):
    if files == package['files']:
        return True
    return any(files == apply_ui_language(package, language)['files']
               for language in ('en', 'zh-Hant') if (package.get('uiLanguages') or {}).get(language))


def confirm_reinstall(language):
    if REINSTALL_CONFIRMED:
        return True
    if not INTERACTIVE_CONFIRMATION:
        raise RuntimeError('重新安装会先恢复原状，请确认后重试（命令行使用 --confirm-reinstall）')
    event('confirmation', **reinstall_prompt(language))
    # No ADB setup, upload, restoration or reboot until the desktop explicitly agrees.
    # EOF, cancellation and malformed responses all cancel without changing the camera.
    return sys.stdin.readline(128) == CONTINUE


def recognized_bundle(manifest):
    current = prepare()
    if manifest.get('format') != 3 or manifest.get('guiSha256') != STOCK_GUI:
        raise RuntimeError('安装或恢复清单版本不匹配')
    if same_release_files(manifest.get('files'), current):
        return manifest.get('autoBrightness') == current.get('autoBrightness')
    if manifest.get('autoBrightness'):
        for name, expected in (('previous-bundle-auto-brightness.json', PREVIOUS_BRIGHTNESS_SHA),
                               ('previous-bundle-brightness-display.json', PREVIOUS_DISPLAY_BRIGHTNESS_SHA)):
            previous = (O / name).read_bytes()
            if sha(previous) != expected: raise RuntimeError('自动亮度安装包校验失败')
            known = json.loads(previous)
            if same_release_files(manifest.get('files'), known):
                return manifest.get('autoBrightness') == known.get('autoBrightness')
        return False
    previous_042 = (O / 'previous-bundle-0.4.2.json').read_bytes()
    if sha(previous_042) != PREVIOUS_042_SHA: raise RuntimeError('已知 0.4.2 清单校验失败，请重新解压安装包')
    if same_release_files(manifest.get('files'), json.loads(previous_042)):
        return not manifest.get('autoBrightness')
    previous_033 = (O / 'previous-bundle-0.3.3.json').read_bytes()
    if sha(previous_033) != PREVIOUS_033_SHA: raise RuntimeError('已知 0.3.3 清单校验失败，请重新解压安装包')
    if manifest.get('files') == json.loads(previous_033)['files']: return True
    previous_032 = (O / 'previous-bundle-0.3.2.json').read_bytes()
    if sha(previous_032) != PREVIOUS_032_SHA: raise RuntimeError('已知 0.3.2 清单校验失败，请重新解压安装包')
    if manifest.get('files') == json.loads(previous_032)['files']: return True
    previous_data = (O / 'previous-bundle.json').read_bytes()
    if sha(previous_data) != PREVIOUS_BUNDLE_SHA:
        raise RuntimeError('已知旧版清单校验失败，请重新解压安装包')
    previous = json.loads(previous_data)
    if manifest.get('files') == previous['files']: return True
    previous_data = (O / 'previous-bundle-0.3.0.json').read_bytes()
    if sha(previous_data) != PREVIOUS_030_SHA:
        raise RuntimeError('已知 0.3.0 清单校验失败，请重新解压安装包')
    return manifest.get('files') == json.loads(previous_data)['files']


def init_config(raw):
    if sha(raw) != STOCK_RC: raise RuntimeError('启动配置不是已核验的原厂版本')
    first = b'service camera-gui /system/bin/camera-gui -platform wayland-egl --fullscreen\n'
    if raw.count(first) != 1: raise RuntimeError('未知相机启动配置')
    rc = raw.replace(first, first + b'    setenv X2D_NATIVE_MENU 1\n    setenv LD_PRELOAD /system/lib64/libx2d_native_menu.so\n', 1)
    rc += b'''\n# X2D play software: trusted entry point, fixed loopback service.
service x2d-speed-buff /system/bin/camera-gui --x2d-speed-server
    class core
    user root
    group root
    seclabel u:r:hbl_camera_service:s0
    setenv X2D_SPEED_SERVER 1
    setenv LD_PRELOAD /system/lib64/libx2d_speed_server.so
    oneshot
'''
    return rc


def init_display_config(raw):
    if sha(raw) != DISPLAY_STOCK_RC: raise RuntimeError('屏幕启动配置不是已核验的原厂版本')
    first = next((line for line in raw.splitlines(keepends=True)
                  if line.startswith(b'service camera-system /system/bin/camera-system')), None)
    if first is None or raw.count(first) != 1: raise RuntimeError('未知屏幕启动配置')
    return raw.replace(first, first + b'    setenv X2D_DISPLAY_RUNTIME 1\n    setenv LD_PRELOAD /system/lib64/libx2d_play_brightness.so\n', 1)


def brightness_status():
    raw = shell('busybox wget -T 2 -qO- http://127.0.0.1:18765/display/status | base64')
    state = json.loads(base64.b64decode(raw))
    if state.get('ok') is not True or state.get('ready') is not True:
        raise RuntimeError('自动亮度服务尚未就绪')
    if str(state.get('pid')) != shell('pidof camera-system').strip():
        raise RuntimeError('自动亮度服务尚未就绪')
    return state


def reboot_and_verify(installed, report_result=True, prank_ibis=False, auto_brightness=False):
    event('progress', message='相机正在重启，等待校验', percent=85)
    shell('sync;(sleep 2;reboot) >/tmp/x2d-play-reboot.log 2>&1 & echo REBOOT_DISPATCHED')
    time.sleep(4)
    deadline = time.monotonic() + 70
    last_error = ''
    while time.monotonic() < deadline:
        try:
            verify_target()
            if shell('getprop init.svc.camera-gui') != 'running':
                raise RuntimeError('相机界面尚未启动')
            if installed:
                if shell('getprop init.svc.x2d-speed-buff') != 'running':
                    raise RuntimeError('功能服务尚未启动')
                marker = shell('cat /tmp/x2d-native-menu-preload.status')
                if marker != 'MENU_AND_AFC_SWITCHABLE_READY':
                    raise RuntimeError('菜单扩展未通过启动校验：' + marker)
                ui_marker = shell('cat /tmp/x2d-native-menu-ui.ready 2>/dev/null || echo MENU_PENDING')
                if ui_marker not in ('MENU_ENTRY_READY_11', 'MENU_ENTRY_READY_12'):
                    raise RuntimeError('菜单入口尚未完成挂接，请保持连接并等待相机界面加载')
                state = backend('status')
                if not state['ready']: raise RuntimeError('功能服务未就绪')
                if auto_brightness: state['brightness'] = brightness_status()
                if bool(state.get('prankIbis', False)) != prank_ibis or (prank_ibis and ui_marker != 'MENU_ENTRY_READY_12'):
                    raise RuntimeError('907 防抖彩蛋菜单未通过校验，请保持连接并重新检查')
            else:
                if shell('sha256sum ' + RC).split()[0] != STOCK_RC:
                    raise RuntimeError('原厂启动配置校验失败')
                if auto_brightness and shell('sha256sum ' + DISPLAY_RC).split()[0] != DISPLAY_STOCK_RC:
                    raise RuntimeError('原厂屏幕启动配置校验失败')
                targets = [f['target'] for f in prepare()['files']]
                # Batch short requests to keep the factory protocol within its limit.
                for target in targets:
                    if shell('test ! -e ' + target + ' && echo REMOVED') != 'REMOVED':
                        raise RuntimeError('扩展文件未完全撤回')
                if 'adb' in shell('getprop sys.usb.config').split(','):
                    raise RuntimeError('USB 尚未恢复生产模式')
                state = dict(ready=True, active=False, master=False, afc=False)
            if report_result:
                event('result', success=True, installed=installed, state=state,
                      message='安装完成，菜单入口与开机加载已验证' if installed else '已恢复原状，重启校验通过')
            else:
                event('progress', message='旧版已恢复并通过重启校验，正在继续安装修正版，请保持连接', percent=5)
            return
        except Exception as error:
            last_error = str(error)
        time.sleep(1)
    raise RuntimeError('重启后未能完成校验：' + last_error + '。请保持连接并使用恢复原状。')


def backend(action):
    if action not in ('status', 'enable', 'disable', 'master_on', 'master_off', 'afc_on', 'afc_off'):
        raise RuntimeError('Unknown fixed action')
    if action == 'status':
        raw = shell('busybox wget -T 10 -qO- http://127.0.0.1:18763/status | base64')
        return json.loads(base64.b64decode(raw))
    output = shell('sh /system/etc/x2d-speed-buff/worker ' + action + ' && echo ACTION_FINISHED')
    if output != 'ACTION_FINISHED': raise RuntimeError('功能设置未完成')
    return json.loads(read_bytes('/tmp/x2d-speed-buff/ui.json'))


def install(reboot=True, prank_ibis=False, language='zh'):
    event('progress', message='正在检查相机与安装包', percent=5)
    verify_target()
    m = apply_ui_language(prepare(), language)
    if prank_ibis and camera_model() != '907X & CFV 100C':
        raise RuntimeError('防抖彩蛋仅适用于已识别的 907X / CFV 100C')
    m['prankIbis'] = prank_ibis
    if shell(f'test -e {ROOT}/installed && echo YES || echo NO') == 'YES':
        phase = read_bytes(ROOT + '/installed').decode().strip()
        installed = json.loads(read_bytes(ROOT + '/manifest'))
        if phase != 'INSTALLED': raise RuntimeError('上次操作未完成，请点击恢复原状')
        if installed['files'] == m['files'] and installed.get('autoBrightness') != m.get('autoBrightness'):
            raise RuntimeError('自动亮度安装包校验失败')
        if installed['files'] == m['files'] and bool(installed.get('prankIbis', False)) == prank_ibis:
            state = backend('status')
            if not state['ready']: raise RuntimeError('已安装的服务未就绪，请先恢复原状')
            if shell('cat /tmp/x2d-native-menu-ui.ready 2>/dev/null || echo MENU_PENDING') not in ('MENU_ENTRY_READY_11','MENU_ENTRY_READY_12'):
                raise RuntimeError('当前版本文件已安装，但菜单入口尚未完成挂接；请保持连接并重新检查，必要时恢复原状')
            if bool(state.get('prankIbis', False)) != prank_ibis:
                raise RuntimeError('907 防抖彩蛋菜单未通过校验，请保持连接并重新检查')
            if m.get('autoBrightness'): state['brightness'] = brightness_status()
            event('result', success=True, installed=True, state=state, message='当前版本已经安装')
            return
        if recognized_bundle(installed):
            if not confirm_reinstall(language):
                event('cancelled', message='已取消重新安装，相机未被修改。')
                return
            event('progress', message='检测到已知旧版，将先恢复原状再安装修正版；升级后请重新开启功能', percent=5)
            restore(True, report_result=False)
            return install(reboot, prank_ibis, language)
        raise RuntimeError('相机存在其他版本，请先用对应版本恢复原状')
    raw = read_bytes(RC)
    rc = init_config(raw)
    display = bool(m.get('autoBrightness'))
    if display:
        if shell('sha256sum /system/bin/camera-system').split()[0] != DISPLAY_SYSTEM_SHA:
            raise RuntimeError('屏幕系统不是已核验的原厂版本')
        display_raw = read_bytes(DISPLAY_RC)
        display_rc = init_display_config(display_raw)
        m['displayInitBefore'] = DISPLAY_STOCK_RC
        m['displayInitAfter'] = sha(display_rc)
    m['initBefore'] = STOCK_RC
    m['initAfter'] = sha(rc)
    ensure_adb()
    event('progress', message='正在备份原厂配置并上传文件', percent=20)
    if shell(f'test ! -L {ROOT} && test ! -L {STAGE} && mkdir -p {STAGE} && chmod 700 {ROOT} {STAGE} && echo SAFE') != 'SAFE':
        raise RuntimeError('无法创建安全暂存目录')
    upload('stockrc', raw)
    upload('newrc', rc)
    if display:
        upload('stockdisplayrc', display_raw)
        upload('newdisplayrc', display_rc)
    upload('manifest', json.dumps(m).encode())
    upload('archive', (O / 'speed-bundle.tar.gz').read_bytes())
    shell(f'tar -xzf {STAGE}/archive -C {STAGE}')
    s = header() + f'hashok {RC} {STOCK_RC}\nhashok {STAGE}/stockrc {STOCK_RC}\nhashok {STAGE}/newrc {sha(rc)}\n'
    if display:
        s += f'hashok {DISPLAY_RC} {DISPLAY_STOCK_RC}\nhashok {STAGE}/stockdisplayrc {DISPLAY_STOCK_RC}\nhashok {STAGE}/newdisplayrc {sha(display_rc)}\n'
    for f in m['files']:
        s += f'[ ! -e {f["target"]} ] && [ ! -L {f["target"]} ]\nhashok {STAGE}/{f["source"]} {f["sha256"]}\n'
    if display: s += f'cp {STAGE}/stockdisplayrc {ROOT}/stockdisplayrc\n'
    display_rollback = f'if [ "$display_touched" = 1 ]; then cat {ROOT}/stockdisplayrc >{DISPLAY_RC} || rollback_ok=0; hashok {DISPLAY_RC} {DISPLAY_STOCK_RC} || rollback_ok=0; fi' if display else ':'
    s += f'''cp {STAGE}/stockrc {ROOT}/stockrc
cp {STAGE}/manifest {ROOT}/manifest
success=0; touched=0; display_touched=0; created=""
finish() {{
 set +e
 if [ "$success" != 1 ]; then
  rollback_ok=1
  mount -o remount,rw /system || rollback_ok=0
  if [ "$touched" = 1 ]; then cat {ROOT}/stockrc >{RC} || rollback_ok=0; hashok {RC} {STOCK_RC} || rollback_ok=0; fi
  {display_rollback}
  for path in $created; do rm -f "$path" || rollback_ok=0; done
  rmdir /system/etc/x2d-speed-buff 2>/dev/null || true
  if [ "$rollback_ok" = 1 ]; then rm -f /blackbox/.x2d-play-software/installed /blackbox/.x2d-play-software/prank-ibis; fi
  sync
 fi
 mount -o remount,ro /system
}}
trap finish EXIT
trap 'exit 40' HUP INT TERM
echo PREPARED >{ROOT}/installed
mount -o remount,rw /system
mkdir -p /system/etc/x2d-speed-buff
: >{ROOT}/created
'''
    for f in m['files']:
        s += f'created="{f["target"]} $created"\necho "$created" >{ROOT}/created\ncat {STAGE}/{f["source"]} >{f["target"]}\nchmod 0644 {f["target"]}\nhashok {f["target"]} {f["sha256"]}\n'
    s += f'[ ! -L {PRANK_FLAG} ]\n'
    s += (f': >{PRANK_FLAG}\n' if prank_ibis else f'rm -f {PRANK_FLAG}\n')
    if display:
        s += f'display_touched=1\ncat {STAGE}/newdisplayrc >{DISPLAY_RC}\nhashok {DISPLAY_RC} {sha(display_rc)}\nrm -f {BRIGHTNESS_PREF} {BRIGHTNESS_FEATURE} {BRIGHTNESS_PREF}.next {BRIGHTNESS_FEATURE}.next\n'
    s += f'touched=1\ncat {STAGE}/newrc >{RC}\nhashok {RC} {sha(rc)}\nsync\nmount -o remount,ro /system\n[ "$(state)" = "$original_mount" ]\nsuccess=1\necho INSTALLED >{ROOT}/installed\necho PLAY_SOFTWARE_INSTALLED\n'
    validate_script(s)
    upload('install', s.encode())
    event('progress', message='正在安装菜单和功能服务', percent=55)
    result = shell(f'sh {STAGE}/install')
    if result != 'PLAY_SOFTWARE_INSTALLED': raise RuntimeError('安装事务未确认，请检查状态')
    if reboot: reboot_and_verify(True, prank_ibis=prank_ibis, auto_brightness=display)
    else: event('result', success=True, installed=True, message='文件已安装，待重启验证')


def status():
    verify_target()
    model = camera_model()
    installed = shell(f'test -e {ROOT}/installed && echo YES || echo NO') == 'YES'
    if installed and read_bytes(ROOT + '/installed').decode().strip() != 'INSTALLED':
        event('status', connected=True, model=model, installed=True, recovery=True, firmware='4.2.0',
              message='上次操作未完成，请点击恢复原状')
        return
    if installed:
        try:
            state = backend('status')
            if not state.get('ready'): raise RuntimeError('功能服务未就绪')
        except Exception:
            # A failed loopback service must not prevent an independent USB restore.
            verify_target()
            event('status', connected=True, model=model, installed=True, recovery=True, firmware='4.2.0',
                  message='相机已连接，功能服务未就绪，可使用恢复原状')
            return
        marker = shell('cat /tmp/x2d-native-menu-ui.ready 2>/dev/null || echo MENU_PENDING')
        if marker not in ('MENU_ENTRY_READY_11', 'MENU_ENTRY_READY_12') or (state.get('prankIbis') and marker != 'MENU_ENTRY_READY_12'):
            event('status', connected=True, model=model, installed=True, recovery=True, menuPending=True,
                  firmware='4.2.0', state=state, message='功能文件已安装，菜单回执待刷新',
                  hint='请在相机点击“跳过”并打开主菜单，再点击“已连接”重试；仍未通过时可恢复原状。')
            return
    else:
        if shell('sha256sum ' + RC).split()[0] != STOCK_RC:
            raise RuntimeError('相机启动配置不是本版原厂状态，安装检查未通过')
        state = dict(ready=True, active=False, afc=False, master=False)
    event('status', connected=True, model=model, installed=installed, firmware='4.2.0', state=state,
          message='已安装耍起功能' if installed else '相机就绪，原厂状态')


def restore(reboot=True, report_result=True):
    event('progress', message='正在检查恢复备份', percent=5)
    verify_target()
    if shell(f'test -e {ROOT}/installed && echo YES || echo NO') == 'NO':
        if shell('sha256sum ' + RC).split()[0] != STOCK_RC:
            raise RuntimeError('没有本软件安装记录，且启动配置不是原厂；拒绝覆盖')
        if prepare().get('autoBrightness') and shell('sha256sum ' + DISPLAY_RC).split()[0] != DISPLAY_STOCK_RC:
            raise RuntimeError('原厂屏幕启动配置校验失败')
        if report_result:
            event('result', success=True, installed=False, message='相机已经是原厂状态')
        else:
            event('progress', message='原厂状态已确认，正在继续安装修正版，请保持连接', percent=5)
        return
    m = json.loads(read_bytes(ROOT + '/manifest'))
    if not recognized_bundle(m):
        raise RuntimeError('恢复清单与本软件版本不一致')
    raw = read_bytes(ROOT + '/stockrc')
    if sha(raw) != STOCK_RC or m['initAfter'] != sha(init_config(raw)):
        raise RuntimeError('原厂备份或恢复配置校验失败')
    display = bool(m.get('autoBrightness'))
    if display:
        display_raw = read_bytes(ROOT + '/stockdisplayrc')
        display_rc = init_display_config(display_raw)
        if m.get('displayInitBefore') != DISPLAY_STOCK_RC or m.get('displayInitAfter') != sha(display_rc):
            raise RuntimeError('原厂屏幕备份或恢复配置校验失败')
    phase = read_bytes(ROOT + '/installed').decode().strip()
    if phase not in ('INSTALLED', 'PREPARED', 'RESTORING'):
        raise RuntimeError('未知安装事务状态')
    ledger = read_bytes(ROOT + '/created').decode().split()
    allowed = {f['target'] for f in m['files']}
    if len(ledger) != len(set(ledger)) or not set(ledger) <= allowed:
        raise RuntimeError('恢复路径清单不符合本版本')
    if phase == 'INSTALLED' and set(ledger) != allowed:
        raise RuntimeError('已安装文件清单不完整')
    ensure_adb()
    # Recovery uses the verified host worker even if installation stopped midway.
    upload('recovery', (O / 'speed-worker').read_bytes())
    event('progress', message='正在撤回 AF-C 和对焦加速', percent=20)
    output = shell('sh ' + STAGE + '/recovery master_off && echo ACTION_FINISHED')
    if output != 'ACTION_FINISHED': raise RuntimeError('功能撤回未完成，请保持连接重试')
    state = json.loads(read_bytes('/tmp/x2d-speed-buff/ui.json'))
    if not state['ready'] or state['active'] or state['afc'] or state['master']:
        raise RuntimeError('功能撤回尚未核验，请松开快门后重试')
    s = header() + f'hashok {ROOT}/stockrc {STOCK_RC}\n'
    # For interrupted writes, accept only a prefix of this application's exact bytes.
    if phase == 'INSTALLED':
        s += f'hashok {RC} {m["initAfter"]}\n'
    else:
        current_rc = read_bytes(RC)
        if current_rc not in (raw, init_config(raw)) and not init_config(raw).startswith(current_rc) and not raw.startswith(current_rc):
            raise RuntimeError('中断后的启动配置不是本软件写入的内容')
        s += f'hashok {RC} {sha(current_rc)}\n'
    if display:
        current_display = read_bytes(DISPLAY_RC)
        if phase == 'INSTALLED' and current_display != display_rc:
            raise RuntimeError('屏幕启动配置不是本软件写入的内容')
        if current_display not in (display_raw, display_rc) and not display_raw.startswith(current_display) and not display_rc.startswith(current_display):
            raise RuntimeError('屏幕启动配置不是本软件写入的内容')
        s += f'hashok {ROOT}/stockdisplayrc {DISPLAY_STOCK_RC}\nhashok {DISPLAY_RC} {sha(current_display)}\n'
    for target in ledger:
        s += f'[ ! -L {target} ]\n'
        expected = next(f['sha256'] for f in m['files'] if f['target'] == target)
        # A PREPARED transaction may have created only part of a payload.
        if phase == 'PREPARED':
            f = next(f for f in m['files'] if f['target'] == target)
            upload_source = (O / f['source']).read_bytes()
            if sha(upload_source) != f['sha256']:
                upload_source = (O / 'previous-payloads' / f['sha256']).read_bytes()
            if sha(upload_source) != f['sha256']:
                raise RuntimeError('恢复所需的已知载荷校验失败')
            # base64 transport is fine for the small files; don't pull the GUI hardlink.
            if shell('test -e ' + target + ' && echo YES || echo NO') == 'YES':
                actual = read_bytes(target)
                if not upload_source.startswith(actual): raise RuntimeError('中断文件内容不是本软件载荷')
                expected = sha(actual)
        if phase == 'INSTALLED': s += f'hashok {target} {expected}\n'
        else: s += f'if [ -e {target} ]; then hashok {target} {expected}; fi\n'
    display_stop = '''stop camera-system
n=0
while [ "$(getprop init.svc.camera-system)" != stopped ] || [ -n "$(pidof camera-system || true)" ]; do
 n=$((n+1)); [ "$n" -lt 30 ] || exit 43; sleep 1
done''' if display else ':'
    display_restore = f'cat {ROOT}/stockdisplayrc >{DISPLAY_RC}\nhashok {DISPLAY_RC} {DISPLAY_STOCK_RC}' if display else ':'
    s += f'''echo RESTORING >{ROOT}/installed
stop camera-gui
stop x2d-speed-buff
{display_stop}
sleep 1
trap 'mount -o remount,ro /system' EXIT
mount -o remount,rw /system
cat {ROOT}/stockrc >{RC}
hashok {RC} {STOCK_RC}
{display_restore}
'''
    for target in ledger: s += 'rm -f ' + target + '\n'
    s += f'rmdir /system/etc/x2d-speed-buff 2>/dev/null || true\nsync\nmount -o remount,ro /system\n[ "$(state)" = "$original_mount" ]\nrm -f {ROOT}/installed {PRANK_FLAG} {BRIGHTNESS_PREF} {BRIGHTNESS_FEATURE} {BRIGHTNESS_PREF}.next {BRIGHTNESS_FEATURE}.next\necho PLAY_SOFTWARE_RESTORED\n'
    validate_script(s)
    upload('restore', s.encode())
    event('progress', message='正在恢复原厂启动配置', percent=60)
    if shell(f'sh {STAGE}/restore') != 'PLAY_SOFTWARE_RESTORED':
        raise RuntimeError('恢复事务未确认，请保持连接')
    if reboot:
        if report_result:
            if display: reboot_and_verify(False,auto_brightness=True)
            else: reboot_and_verify(False)
        else:
            if display: reboot_and_verify(False,report_result=False,auto_brightness=True)
            else: reboot_and_verify(False,report_result=False)
    elif report_result: event('result', success=True, installed=False, message='文件已恢复，待重启验证')


def validate_script(script):
    if '\r' in script or '\0' in script or not script.startswith('#!/system/bin/sh\nset -eu\n'):
        raise RuntimeError('内部安装脚本未通过校验')
    if os.name != 'nt':
        subprocess.run(['sh', '-n'], input=script.encode(), check=True)
    # Also syntax-check the uploaded bytes with the CAMERA's shell before execution.


def usb_failure_code(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        code = getattr(error, 'backend_error_code', None)
        if isinstance(code, int): return code
        error = error.__cause__
    return None


def user_error(error):
    """Translate transport failures before they reach the application's visible log."""
    message = str(error)
    if isinstance(error, subprocess.TimeoutExpired) or 'timed out' in message.lower():
        return '相机通信超时，请检查 USB 连接后重试'
    if 'was not enumerated' in message:
        return '未检测到相机，请开机并连接数据线，再点击“已连接”' + ('；Windows 请检查工厂接口的 WinUSB 驱动' if os.name == 'nt' else '')
    if isinstance(error, json.JSONDecodeError):
        return '相机返回的状态未通过校验，请保持连接并重新检查'
    if isinstance(error, usb.UsbFactoryError):
        if message.startswith('Windows 工厂接口'):
            return message
        if error.__cause__ is not None and str(error.__cause__).startswith('Windows 工厂接口'):
            return str(error.__cause__)
        if 'bundled USB runtime' in message:
            return 'USB 运行库加载失败，请重新解压完整安装包；这是应用运行库问题，尚未检查相机驱动（连接检查 01）'
        if 'command failed' in message:
            return '相机执行未完成，请保持连接并重新检查状态，必要时使用恢复原状'
        if 'target' in message.lower() or 'SHA' in message or 'firmware' in message.lower():
            return '相机型号或固件未通过校验，请使用 X2D 100C / 907X 100C 的原厂 4.2.0 系统'
        if os.name == 'nt' and 'could not claim factory USB interface' in message:
            code = usb_failure_code(error)
            reason = {-3:'接口访问被拒绝', -4:'相机已断开', -6:'接口被其他程序占用',
                      -7:'打开接口超时', -12:'当前接口驱动不支持此操作'}.get(code, '无法打开工厂接口')
            suffix = '' if code is None else '，USB 错误码 ' + str(code)
            return '已检测到相机，但' + reason + '；请检查 MI_03 是否绑定 WinUSB，并关闭占用相机的程序（连接检查 03' + suffix + '）'
        if os.name == 'nt' and 'backend' in message.lower():
            return 'USB 运行库未就绪，请重新解压完整安装包（连接检查 01）'
        if os.name == 'nt' and ('interface' in message.lower() or 'endpoints' in message.lower()):
            return '相机 USB 工厂接口布局未通过校验，请反馈此提示；不要修改其他 USB 接口驱动（连接检查 04）'
        return 'USB 通信未完成，请检查相机电源和数据线后重试'
    if re.search(r'[\u4e00-\u9fff]', message):
        return message
    if isinstance(error, FileNotFoundError):
        return '应用文件不完整，请重新解压完整安装包后重试'
    return '操作未完成，状态尚未确认，请保持连接并重新检查'


def main():
    global INTERACTIVE_CONFIRMATION, REINSTALL_CONFIRMED
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['install', 'status', 'restore', 'enable', 'disable', 'master_on', 'master_off', 'afc_on', 'afc_off'])
    p.add_argument('--no-reboot', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--prank-ibis', action='store_true', help='Add the optional CFV-only joke menu')
    p.add_argument('--language', choices=['zh', 'zh-Hant', 'en'], default='zh',
                   help='Install Simplified Chinese, Traditional Chinese or English camera menu labels')
    confirmation = p.add_mutually_exclusive_group()
    confirmation.add_argument('--interactive-confirmation', action='store_true', help=argparse.SUPPRESS)
    confirmation.add_argument('--confirm-reinstall', action='store_true',
                              help='Confirm restoration before reinstalling an existing extension')
    args = p.parse_args()
    if args.prank_ibis and args.action != 'install': p.error('--prank-ibis requires install')
    if args.language != 'zh' and args.action != 'install': p.error('--language requires install')
    if (args.interactive_confirmation or args.confirm_reinstall) and args.action != 'install':
        p.error('reinstall confirmation requires install')
    INTERACTIVE_CONFIRMATION = args.interactive_confirmation
    REINSTALL_CONFIRMED = args.confirm_reinstall
    try:
        if args.action == 'install': install(not args.no_reboot, args.prank_ibis, args.language)
        elif args.action == 'restore': restore(not args.no_reboot)
        elif args.action == 'status': status()
        else:
            verify_target()
            event('status', state=backend(args.action))
    finally:
        close_adb_session()

if __name__ == '__main__':
    try: main()
    except Exception as error:
        event('error', message=user_error(error))
        sys.exit(1)
