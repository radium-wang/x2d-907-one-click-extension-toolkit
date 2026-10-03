"""Windows 原生窗口。USB 操作由独立进程执行，主线程只接收中文事件。"""
import ctypes as C
from ctypes import wintypes as W
import json, os, queue, subprocess, sys, threading
from pathlib import Path
from localization import Localizer, translate

D = Path(__file__).resolve().parent
VERSION = '0.4.1'


class Session:
    """只接受完整的检查结果，失败或重新检查会撤回写入入口。"""
    def __init__(self):
        self.verified = False
        self.busy = False
        self.result = False
        self.action = ''
        self.error_received = False
        self.model = ''

    def start(self, action):
        if self.busy or (action != 'status' and not self.verified): return False
        if action == 'status': self.verified = False; self.model = ''
        self.action, self.busy, self.result = action, True, False
        self.error_received = False
        return True

    def consume(self, event):
        kind = event.get('type')
        if kind == 'status':
            self.model = event.get('model', '')
            self.verified = event.get('connected') is True and event.get('firmware') == '4.2.0'
            self.result = True
        elif kind == 'result':
            self.result = event.get('success') is True
        elif kind == 'error':
            self.model = ''
            self.verified = False
            self.result = True
            self.error_received = True

    def finish(self, code):
        self.busy = False
        if code or not self.result:
            self.verified = False
            return False
        return True


def main():
    if os.name != 'nt': raise RuntimeError('Windows 版需要 Windows 10 / 11（64 位）')
    user = C.WinDLL('user32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    gdi = C.WinDLL('gdi32', use_last_error=True)
    common = C.WinDLL('comctl32', use_last_error=True)
    PTR = C.c_ssize_t
    WP = C.c_size_t
    PROC = C.WINFUNCTYPE(PTR, W.HWND, W.UINT, WP, PTR)

    class WindowClass(C.Structure):
        _fields_ = [('size', W.UINT), ('style', W.UINT), ('proc', PROC),
                    ('classExtra', C.c_int), ('windowExtra', C.c_int), ('instance', W.HINSTANCE),
                    ('icon', W.HICON), ('cursor', W.HANDLE), ('brush', W.HBRUSH),
                    ('menu', W.LPCWSTR), ('name', W.LPCWSTR), ('smallIcon', W.HICON)]

    class InitCommon(C.Structure):
        _fields_ = [('size', W.DWORD), ('classes', W.DWORD)]

    # Explicit signatures preserve handles on 64-bit Windows.
    def api(dll, name, result, *args):
        fn = getattr(dll, name); fn.restype = result; fn.argtypes = list(args)
        return fn
    create = api(user, 'CreateWindowExW', W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
                 C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID)
    default = api(user, 'DefWindowProcW', PTR, W.HWND, W.UINT, WP, PTR)
    send = api(user, 'SendMessageW', PTR, W.HWND, W.UINT, WP, PTR)
    post = api(user, 'PostMessageW', W.BOOL, W.HWND, W.UINT, WP, PTR)
    native_settext = api(user, 'SetWindowTextW', W.BOOL, W.HWND, W.LPCWSTR)
    localized_sources = {}
    language = Localizer(Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'language.json')
    def settext(handle, text):
        localized_sources[handle] = text
        return native_settext(handle, language.text(text))
    enable = api(user, 'EnableWindow', W.BOOL, W.HWND, W.BOOL)
    messagebox = api(user, 'MessageBoxW', C.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
    register = api(user, 'RegisterClassExW', W.WORD, C.POINTER(WindowClass))
    module = api(kernel, 'GetModuleHandleW', W.HMODULE, W.LPCWSTR)
    loadcursor = api(user, 'LoadCursorW', W.HANDLE, W.HINSTANCE, W.LPVOID)
    createfont = api(gdi, 'CreateFontW', W.HANDLE, *([C.c_int] * 5), *([W.DWORD] * 8), W.LPCWSTR)
    setcolor = api(gdi, 'SetTextColor', W.DWORD, W.HDC, W.DWORD)
    setbk = api(gdi, 'SetBkColor', W.DWORD, W.HDC, W.DWORD)
    brush = api(gdi, 'CreateSolidBrush', W.HBRUSH, W.DWORD)
    destroy = api(user, 'DestroyWindow', W.BOOL, W.HWND)
    show = api(user, 'ShowWindow', W.BOOL, W.HWND, C.c_int)
    update = api(user, 'UpdateWindow', W.BOOL, W.HWND)
    getmsg = api(user, 'GetMessageW', C.c_int, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
    translate = api(user, 'TranslateMessage', W.BOOL, C.POINTER(W.MSG))
    dispatch = api(user, 'DispatchMessageW', PTR, C.POINTER(W.MSG))
    dialog = api(user, 'IsDialogMessageW', W.BOOL, W.HWND, C.POINTER(W.MSG))
    quitmessage = api(user, 'PostQuitMessage', None, C.c_int)
    deleteobject = api(gdi, 'DeleteObject', W.BOOL, W.HANDLE)
    initcommon = api(common, 'InitCommonControlsEx', W.BOOL, C.POINTER(InitCommon))
    try:
        api(user, 'SetProcessDpiAwarenessContext', W.BOOL, W.HANDLE)(C.c_void_p(-4))
        dpi = api(user, 'GetDpiForSystem', W.UINT)()
    except AttributeError: dpi = 96
    scale = lambda n: round(n * dpi / 96)
    white = brush(0xFFFFFF)
    fonts = []
    def font(size, bold=False):
        f = createfont(-scale(size), 0, 0, 0, 600 if bold else 400,
                       0, 0, 0, 1, 0, 0, 5, 0, 'Microsoft YaHei UI')
        fonts.append(f); return f
    normal, small, strong, titlefont = font(14), font(12), font(14, True), font(22, True)
    session = Session()
    events = queue.Queue()
    controls = {}
    loglines = []
    logfile = Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'latest.log'
    logfile.parent.mkdir(parents=True, exist_ok=True)
    EVENT_MESSAGE = 0x8001
    update_state = dict(busy=False, version='')

    def buttons():
        busy = session.busy or update_state['busy']
        enable(controls['updatebutton'], not busy)
        eligible = session.verified and session.model == '907X & CFV 100C'
        enable(controls['prank'], eligible and not busy)
        if not eligible: send(controls['prank'], 0x00F1, 0, 0)  # BM_SETCHECK
        enable(controls['statusbutton'], not busy)
        for key in ('installbutton', 'restorebutton'):
            enable(controls[key], not busy and session.verified)

    def render_logs():
        translated_lines = [language.text(line) for line in loglines]
        content = '\r\n'.join(translated_lines)[-14000:]
        native_settext(controls['logs'], content)
        send(controls['logs'], 0x00B1, len(content), len(content))  # EM_SETSEL
        send(controls['logs'], 0x00B7, 0, 0)  # EM_SCROLLCARET
        try: logfile.write_text('\n'.join(translated_lines) + '\n', encoding='utf-8')
        except OSError: pass

    def log(text):
        if not text: return
        loglines.append(text)
        render_logs()

    def change_language():
        index = send(controls['language'], 0x0147, 0, 0)  # CB_GETCURSEL
        language.select('en' if index == 1 else 'zh')
        for handle, text in localized_sources.items():
            native_settext(handle, language.text(text))
        render_logs()

    def consume(event):
        session.consume(event)
        kind, text = event.get('type'), event.get('message', '')
        if kind == 'progress':
            settext(controls['state'], {'status':'正在检查相机…', 'install':'正在安装…',
                                       'restore':'正在恢复…'}.get(session.action, '正在操作…'))
            settext(controls['detail'], text)
            send(controls['progress'], 0x0402, int(event.get('percent', 0)), 0)
        elif kind == 'status':
            settext(controls['state'], text)
            settext(controls['detail'], event.get('hint', '') if event.get('menuPending') else '主菜单末尾进入耍起功能，总开关控制下方功能。'
                    if event.get('installed') else '相机处于原厂状态，可以安装耍起功能。')
        elif kind == 'result':
            settext(controls['state'], text)
            settext(controls['detail'], '在相机菜单中分别开启 AF-C 与对焦加速 buff。'
                    if event.get('installed') else '原厂界面与启动配置已恢复。')
            send(controls['progress'], 0x0402, 100, 0)
        elif kind == 'error':
            settext(controls['state'], '检查未通过' if session.action == 'status' else '操作未完成')
            settext(controls['detail'], text)
        log(text)
        if event.get('menuPending'): log(event.get('hint', ''))

    def worker(action, prank=False):
        code = 1
        try:
            if action == 'status':
                from windows_connection import prepare_driver
                def driver_event(kind, **values):
                    events.put(('event', dict(type=kind, **values))); post(hwnd, EVENT_MESSAGE, 0, 0)
                prepare_driver(driver_event)
            env = os.environ.copy()
            env.pop('X2D_PAYLOAD_DIR', None)
            env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
            child = subprocess.Popen([str(D / 'runtime/python.exe'), '-X', 'utf8', '-B', '-u',
                                      str(D / 'x2d_play_software.py'), action] + (['--prank-ibis'] if prank else []),
                                     cwd=str(D), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding='utf-8', errors='replace', creationflags=0x08000000)
            for line in child.stdout:
                if not line.startswith('X2D_EVENT '): continue
                try: obj = json.loads(line[10:])
                except ValueError: continue
                if isinstance(obj, dict):
                    events.put(('event', obj)); post(hwnd, EVENT_MESSAGE, 0, 0)
            code = child.wait()
        except Exception as error:
            from windows_connection import DriverPreparationError
            text = str(error) if isinstance(error, DriverPreparationError) else '无法启动操作，请重新解压完整安装包后重试'
            events.put(('event', {'type': 'error', 'message': text}))
        finally:
            events.put(('done', code)); post(hwnd, EVENT_MESSAGE, 0, 0)

    def start(action):
        if update_state['busy']: return
        if not session.start(action): return
        buttons()
        settext(controls['state'], {'status': '正在检查相机…', 'install': '准备安装…', 'restore': '准备恢复…'}[action])
        send(controls['progress'], 0x0402, 0, 0)
        prank = action == 'install' and session.model == '907X & CFV 100C' and send(controls['prank'], 0x00F0, 0, 0) == 1
        if prank: log('已选择 907 防抖彩蛋：第 11 格为彩蛋，第 12 格为耍起功能。')
        threading.Thread(target=worker, args=(action, prank), daemon=True).start()

    def update_worker(wanted):
        try:
            env = os.environ.copy()
            env.pop('X2D_PAYLOAD_DIR', None)
            env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
            args = [str(D / 'runtime/python.exe'), '-B', '-u', str(D / 'app_updates.py'),
                    'install' if wanted else 'check', '--current', VERSION, '--platform', 'win',
                    '--target', str(D), '--parent', str(os.getpid())]
            if wanted: args += ['--wanted', wanted]
            child = subprocess.Popen(args, env=env, cwd=str(D), stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=0x08000000)
            received = False
            for line in child.stdout:
                if not line.startswith('TOOLKIT_UPDATE '): continue
                event = json.loads(line[15:])
                received |= event.get('type') in ('available', 'current', 'error', 'restart')
                events.put(('update', event)); post(hwnd, EVENT_MESSAGE, 0, 0)
            code = child.wait()
            if not received: raise RuntimeError('update process ended without result')
        except Exception:
            events.put(('update', dict(type='error', message='软件更新未完成，请检查网络连接或重新下载完整安装包；当前应用仍保留')))
        finally:
            events.put(('update_done', None)); post(hwnd, EVENT_MESSAGE, 0, 0)

    def start_update():
        if session.busy or update_state['busy']: return
        update_state['busy'] = True; buttons()
        threading.Thread(target=update_worker, args=(update_state['version'],), daemon=True).start()

    @PROC
    def procedure(window, msg, wp, lp):
        try:
            if msg == 0x0010:  # WM_CLOSE
                if session.busy or update_state['busy']:
                    messagebox(window, language.text('相机操作尚未完成，请保持连接并等待完成后退出。'), language.text('操作进行中'), 0x40)
                else: destroy(window)
                return 0
            if msg == 0x0002:
                quitmessage(0); return 0
            if msg == 0x0111:  # WM_COMMAND
                if (wp & 0xFFFF) == 104 and (wp >> 16) == 1:  # CBN_SELCHANGE
                    change_language(); return 0
                if (wp >> 16) == 0:
                    if (wp & 0xFFFF) == 106: start_update(); return 0
                    action = {101: 'status', 102: 'install', 103: 'restore'}.get(wp & 0xFFFF)
                    if action: start(action); return 0
            if msg == EVENT_MESSAGE:
                while True:
                    try: kind, value = events.get_nowait()
                    except queue.Empty: break
                    if kind == 'event': consume(value)
                    elif kind == 'update':
                        text = value.get('message', '')
                        log(text); settext(controls['detail'], text)
                        send(controls['progress'], 0x0402, int(value.get('percent', 0)), 0)
                        if value['type'] == 'available':
                            update_state['version'] = value['version']
                            settext(controls['state'], '发现软件新版本：' + value['version'])
                        elif value['type'] in ('current', 'error'):
                            update_state['version'] = ''
                            settext(controls['state'], '软件更新未完成' if value['type'] == 'error' else text)
                        elif value['type'] == 'restart':
                            destroy(window); return 0
                        settext(controls['updatebutton'], '下载并安装更新' if update_state['version'] else '检查更新')
                    elif kind == 'update_done':
                        update_state['busy'] = False; buttons()
                    else:
                        if not session.finish(value) and not session.error_received:
                            text = '操作尚未确认完成，请保持连接并重新检查状态。'
                            settext(controls['detail'], text); log(text)
                        buttons()
                return 0
            if msg in (0x0138, 0x0133):  # static/edit colors
                setbk(wp, 0xFFFFFF)
                setcolor(wp, 0x0060BA if lp == controls.get('warning') else 0x343434)
                return white
        except Exception:
            # Keep the window alive and never enable writes on an unexpected UI error.
            session.verified = False
            if controls.get('installbutton'): buttons()
        return default(window, msg, wp, lp)

    instance = module(None)
    wc = WindowClass(C.sizeof(WindowClass), 0, procedure, 0, 0, instance, None,
                     loadcursor(None, C.c_void_p(32512)), white, None, 'X2DPlayWindow', None)
    if not register(C.byref(wc)): raise C.WinError(C.get_last_error())
    init = InitCommon(C.sizeof(InitCommon), 0x20)
    initcommon(C.byref(init))
    width, height = scale(620), scale(822)
    screenwidth = api(user, 'GetSystemMetrics', C.c_int, C.c_int)(0)
    screenheight = user.GetSystemMetrics(1)
    hwnd = create(0, wc.name, language.text('x2d/907一键扩展功能-工具包 · ') + VERSION, 0x00CA0000,
                  max(0, (screenwidth-width)//2), max(0, (screenheight-height)//2),
                  width, height, None, None, instance, None)
    if not hwnd: raise C.WinError(C.get_last_error())
    localized_sources[hwnd] = 'x2d/907一键扩展功能-工具包 · ' + VERSION

    def control(key, classname, text, x, y, w, h, extra=0, identity=0, textfont=None, ex=0):
        handle = create(ex, classname, language.text(text), 0x50000000 | extra,
                        scale(x), scale(y), scale(w), scale(h), hwnd, identity or None, instance, None)
        if not handle: raise C.WinError(C.get_last_error())
        controls[key] = handle
        if key not in ('logs','language'): localized_sources[handle] = text
        send(handle, 0x0030, textfont or normal, 1)
        return handle

    control('title', 'STATIC', 'x2d/907一键扩展功能-工具包', 28, 24, 370, 42, textfont=titlefont)
    control('language', 'COMBOBOX', '', 430, 28, 146, 120, extra=0x10003, identity=104)
    for name in ('中文', 'English'):
        send(controls['language'], 0x0143, 0, C.cast(C.c_wchar_p(name), C.c_void_p).value)
    send(controls['language'], 0x014E, 1 if language.language == 'en' else 0, 0)
    control('subtitle', 'STATIC', 'X2D 100C / 907X 100C · 固件 4.2.0', 28, 75, 555, 22)
    control('box', 'BUTTON', '相机功能', 28, 110, 548, 142, extra=7)
    control('afc', 'STATIC', 'AF-C 连续自动对焦', 48, 140, 510, 24, textfont=strong)
    control('afcdescription', 'STATIC', '在相机上开启连续自动对焦', 48, 168, 510, 20, textfont=small)
    control('buff', 'STATIC', '对焦加速 buff', 48, 195, 510, 24, textfont=strong)
    control('buffdescription', 'STATIC', '加快对焦扫描，关闭后恢复原厂速度', 48, 223, 510, 20, textfont=small)
    control('prank', 'BUTTON', '添加防抖功能（907 彩蛋）', 28, 263, 548, 26, extra=0x10003, identity=105)
    control('state', 'STATIC', '等待连接相机', 28, 306, 548, 24, textfont=strong)
    control('detail', 'STATIC', '连接相机并开机，点击“已连接”自动准备驱动并检查状态。\r\n907X 100C 适配版待实机验证。', 28, 338, 548, 42, textfont=small)
    control('progress', 'msctls_progress32', '', 28, 390, 548, 12)
    control('statusbutton', 'BUTTON', '已连接', 28, 420, 120, 38, extra=0x10000, identity=101)
    control('installbutton', 'BUTTON', '一键安装', 161, 420, 165, 38, extra=0x10000, identity=102)
    control('restorebutton', 'BUTTON', '一键恢复原状', 339, 420, 237, 38, extra=0x10000, identity=103)
    control('updatebutton', 'BUTTON', '检查更新', 28, 465, 200, 28, extra=0x10000, identity=106)
    control('warning', 'STATIC', '开启对焦 buff 后切勿取下镜头。\r\n更换镜头前，请先关闭对焦加速 buff。', 28, 510, 548, 46, textfont=strong)
    control('note', 'STATIC', '安装会自动备份原厂配置，并重启校验。恢复会撤回本应用的菜单与功能。\r\n请等待操作完成再拔线；首次连接会自动准备相机工厂接口驱动。', 28, 569, 548, 46, textfont=small)
    control('logs', 'EDIT', '', 28, 627, 548, 138, extra=0x00200844, textfont=small, ex=0x200)
    log('工具包 Windows 版本：' + VERSION)
    from app_updates import notice
    log(notice(D))
    log('请将相机开机并连接数据线，点击“已连接”；程序会自动准备驱动并检查相机状态。')
    log('若相机提示连接方式，可选择“大容量存储”。')
    buttons()
    show(hwnd, 5); update(hwnd)
    message = W.MSG()
    while True:
        result = getmsg(C.byref(message), None, 0, 0)
        if result <= 0: break
        if not dialog(hwnd, C.byref(message)):
            translate(C.byref(message)); dispatch(C.byref(message))
    for f in fonts: deleteobject(f)
    deleteobject(white)


if __name__ == '__main__':
    try: main()
    except Exception:
        if os.name == 'nt':
            language = Localizer(Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'language.json')
            C.windll.user32.MessageBoxW(None, language.text('应用未能启动，请重新解压完整 Windows 安装包。'), language.text('x2d/907一键扩展功能-工具包'), 0x10)
        raise
