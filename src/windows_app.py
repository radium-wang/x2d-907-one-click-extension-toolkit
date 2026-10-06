"""Windows 原生窗口。USB 操作由独立进程执行，主线程只接收中文事件。"""
import ctypes as C
from ctypes import wintypes as W
import json, os, queue, subprocess, sys, threading
from pathlib import Path
from localization import Localizer, translate
from reinstall_confirmation import CONTINUE, CANCEL
from app_settings import UpdatePreferences
from windows_ui import NativeStyle, Viewport, ScrollInfo, WIDTH, HEIGHT, COLORS, main_layout, text_style
from windows_processes import UpdateCheck, stop_process

D = Path(__file__).resolve().parent
VERSION = '0.4.14'


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
        elif kind == 'cancelled':
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

    class MonitorInfo(C.Structure):
        _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]

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
    preferences = UpdatePreferences(Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'settings.json')
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
    move = api(user, 'MoveWindow', W.BOOL, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.BOOL)
    clientrect = api(user, 'GetClientRect', W.BOOL, W.HWND, C.POINTER(W.RECT))
    invalidate = api(user, 'InvalidateRect', W.BOOL, W.HWND, C.POINTER(W.RECT), W.BOOL)
    scrollinfo = api(user, 'SetScrollInfo', C.c_int, W.HWND, C.c_int, C.POINTER(ScrollInfo), W.BOOL)
    getscroll = api(user, 'GetScrollInfo', W.BOOL, W.HWND, C.c_int, C.POINTER(ScrollInfo))
    position = api(user, 'SetWindowPos', W.BOOL, W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT)
    try:
        api(user, 'SetProcessDpiAwarenessContext', W.BOOL, W.HANDLE)(C.c_void_p(-4))
        dpi = api(user, 'GetDpiForSystem', W.UINT)()
    except AttributeError: dpi = 96
    scale = lambda n: round(n * dpi / 96)
    white = brush(0xFFFFFF)
    skin = NativeStyle(user, gdi, common, dpi)
    skin.language = language.language
    normal, small, strong, titlefont = skin.font(14), skin.font(12), skin.font(14, True), skin.font(22, True)
    session = Session()
    events = queue.Queue()
    controls = {}
    placements = {}
    window_dpis = {}
    main_handle = None
    viewport = Viewport()
    content_width = WIDTH
    loglines = []
    logfile = Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'latest.log'
    logfile.parent.mkdir(parents=True, exist_ok=True)
    EVENT_MESSAGE = 0x8001
    update_state = dict(busy=False, version='', installing=False)
    update_check = UpdateCheck()
    closing = threading.Event()
    confirmation_state = dict(window=None, answer=None)
    settings_state = dict(window=None)

    def outer_size(width, height, style):
        rect = W.RECT(0,0,scale(width),scale(height))
        try:
            adjust = api(user,'AdjustWindowRectExForDpi',W.BOOL,C.POINTER(W.RECT),W.DWORD,W.BOOL,W.DWORD,W.UINT)
            adjust(C.byref(rect),style,False,0,dpi)
        except AttributeError:
            api(user,'AdjustWindowRectEx',W.BOOL,C.POINTER(W.RECT),W.DWORD,W.BOOL,W.DWORD)(C.byref(rect),style,False,0)
        return rect.right-rect.left, rect.bottom-rect.top

    def refresh_layout():
        nonlocal content_width
        if main_handle is None:return
        rect=W.RECT();clientrect(main_handle,C.byref(rect))
        content_width=(rect.right*96/dpi) if rect.right else WIDTH
        viewport.resize(rect.bottom*96/dpi if rect.bottom else viewport.height)
        layout=main_layout(content_width,language.language)
        for handle,spec in placements.items():
            geometry=layout.get(spec['key'],spec['rect']) if spec['parent']==main_handle else spec['rect']
            if spec['key']=='updatebutton': geometry=(24,224,134 if language.language=='en' else 82,36)
            if spec['key']=='downloadbutton': geometry=(168 if language.language=='en' else 116,224,238 if language.language=='en' else 134,36)
            x,y,w,h=geometry
            if spec['parent']==main_handle:y-=viewport.offset
            owner_dpi=window_dpis.get(spec['parent'],dpi)
            pixel=lambda value:round(value*owner_dpi/96)
            move(handle,pixel(x),pixel(y),pixel(w),pixel(h),True)
            size,bold,mono=spec['font']
            if not mono and 'language' not in spec:
                size,bold,_=text_style(spec['key'],language.language)
            send(handle,0x0030,skin.font(size,bold,mono,dpi=owner_dpi,language=spec.get('language')),1)
            if spec['key']=='language': send(handle,0x0153,C.c_size_t(-1).value,round(30*owner_dpi/96))
            if handle in skin.controls:skin.controls[handle]['dpi']=owner_dpi
        info=ScrollInfo(C.sizeof(ScrollInfo),0x7,0,scale(HEIGHT)-1,scale(viewport.height),scale(viewport.offset),0)
        scrollinfo(main_handle,1,C.byref(info),True)
        invalidate(main_handle,None,False)
        skin.refresh(language=language.language,dpi=dpi)

    def show_settings():
        if session.busy or update_state['busy']: return
        if settings_state['window'] is None:
            panel_width,panel_height=outer_size(450,284,0x00C80000)
            panel = create(0, 'X2DPlayWindow', language.text('设置'), 0x02C80000,
                           max(0,(screenwidth-panel_width)//2), max(0,(screenheight-panel_height)//2),
                           panel_width,panel_height,hwnd,None,instance,None)
            if not panel: return
            settings_state['window'] = panel
            window_dpis[panel]=dpi
            localized_sources[panel] = '设置'
            control('settingsheading','STATIC','设置',24,28,160,23,parent=panel)
            control('settingsclose','BUTTON','关闭',370,24,56,36,extra=0x10000,identity=113,parent=panel)
            control('languagelabel','STATIC','语言',24,85,100,22,parent=panel)
            control('language','COMBOBOX','',278,78,148,120,extra=0x10003,identity=104,parent=panel)
            for name in ('简体中文','繁體中文','English'):
                send(controls['language'],0x0143,0,C.cast(C.c_wchar_p(name),C.c_void_p).value)
            send(controls['language'],0x014E,1 if language.language=='zh-Hant' else 2 if language.language=='en' else 0,0)
            control('automaticupdates','BUTTON','启动时自动检查更新',24,132,402,22,extra=0x10003,identity=108,parent=panel)
            send(controls['automaticupdates'],0x00F1,1 if preferences.auto_check else 0,0)
            control('updatesdescription','STATIC','自动检查只查找新版，不会自动下载或安装。',24,170,402,36,textfont=small,parent=panel)
            control('updatebutton','BUTTON','检查更新',24,224,112,36,extra=0x10000,identity=106,parent=panel)
            control('downloadbutton','BUTTON','下载并安装更新',148,224,238,36,extra=0x10000,identity=109,parent=panel)
        buttons()
        show(settings_state['window'],5); update(settings_state['window'])

    def confirm_dialog(value):
        # Custom native buttons keep their language independent of Windows' UI language.
        popup_width,popup_height=outer_size(540,270,0x80C80000)
        popup = create(0x00000001, 'X2DPlayWindow', value['title'], 0x82C80000,
                       max(0, (screenwidth-popup_width)//2), max(0, (screenheight-popup_height)//2),
                       popup_width,popup_height,hwnd,None,instance,None)
        if not popup: return False
        confirmation_state.update(window=popup, answer=None)
        window_dpis[popup]=dpi
        enable(hwnd, False)
        text=cancel=proceed=None
        try:
            text = create(0, 'STATIC', value['body'], 0x50000000, scale(22), scale(20),
                          scale(485), scale(160), popup, None, instance, None)
            cancel = create(0, 'BUTTON', value['cancel'], 0x50010001, scale(175), scale(202),
                            scale(130), scale(36), popup, 201, instance, None)
            proceed = create(0, 'BUTTON', value['proceed'], 0x50010000, scale(318), scale(202),
                             scale(185), scale(36), popup, 202, instance, None)
            if not all((text, cancel, proceed)): return False
            for handle,key,rect in ((text,'confirmation_body',(22,20,485,160)),(cancel,'confirmation_cancel',(175,202,130,36)),(proceed,'confirmation_proceed',(318,202,185,36))):
                placements[handle]=dict(key=key,parent=popup,rect=rect,font=(14,False,False),language=value['language'])
                send(handle,0x0030,skin.font(14,language=value['language']),1)
            skin.attach(cancel,'confirmation_cancel',size=(130,36),language=value['language'])
            skin.attach(proceed,'confirmation_proceed',primary=True,size=(185,36),language=value['language'])
            show(popup, 5); update(popup)
            api(user, 'SetFocus', W.HWND, W.HWND)(cancel)
            message = W.MSG()
            while confirmation_state['answer'] is None:
                result = getmsg(C.byref(message), None, 0, 0)
                if result <= 0:
                    if result == 0: quitmessage(message.wParam)
                    return False
                if not dialog(popup, C.byref(message)):
                    translate(C.byref(message)); dispatch(C.byref(message))
            return confirmation_state['answer'] is True
        finally:
            destroy(popup)
            for handle in (text,cancel,proceed):placements.pop(handle,None)
            window_dpis.pop(popup,None)
            confirmation_state.update(window=None, answer=None)
            enable(hwnd, True)

    def selected_features():
        return [feature for feature,key in (('afc','afcchoice'),('speed-buff','buffchoice'),('auto-rear-brightness','brightnesschoice'))
                if send(controls[key],0x00F0,0,0)==1]

    def buttons():
        busy = session.busy or update_state['busy']
        skin.verified = session.verified; skin.busy = busy
        if main_handle: invalidate(main_handle,None,False)
        for key in ('settingsbutton','updatebutton'):
            if key in controls: enable(controls[key],not busy)
        if 'downloadbutton' in controls: enable(controls['downloadbutton'],not busy and bool(update_state['version']))
        eligible = session.verified and session.model == '907X & CFV 100C'
        enable(controls['prank'], eligible and not busy)
        if not eligible: send(controls['prank'], 0x00F1, 0, 0)  # BM_SETCHECK
        enable(controls['statusbutton'], not busy)
        for key in ('afcchoice','buffchoice','brightnesschoice'): enable(controls[key],not busy)
        features = selected_features()
        names = {'afc':'AF-C','speed-buff':'Focus speed','auto-rear-brightness':'Auto brightness'} if language.language=='en' else {'afc':'AF-C','speed-buff':'对焦加速','auto-rear-brightness':'后屏自动亮度'}
        native_settext(controls['selectionsummary'], language.text('尚未选择功能') if not features else ('、' if language.language!='en' else ', ').join(language.text(names[f]) for f in features))
        native_settext(controls['featurecount'], language.text('已选择 ') + str(len(features)) + language.text(' 项'))
        native_settext(controls['logstate'], language.text('操作进行中' if busy else '检查通过' if session.verified else '等待连接'))
        show(controls['prank'],5 if eligible else 0)
        show(controls['dependency'],0 if eligible else 5)
        enable(controls['installbutton'], not busy and session.verified and bool(features))
        enable(controls['restorebutton'], not busy and session.verified)

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
        language.select('zh-Hant' if index == 1 else 'en' if index == 2 else 'zh')
        for handle, text in localized_sources.items():
            native_settext(handle, language.text(text))
        skin.refresh(language=language.language)
        refresh_layout()
        render_logs()
        buttons()

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
            settext(controls['detail'], '在相机菜单中开启已安装的功能。'
                    if event.get('installed') else '原厂界面与启动配置已恢复。')
            send(controls['progress'], 0x0402, 100, 0)
        elif kind == 'cancelled':
            settext(controls['state'], text); settext(controls['detail'], text)
            send(controls['progress'], 0x0402, 0, 0)
        elif kind == 'error':
            settext(controls['state'], '检查未通过' if session.action == 'status' else '操作未完成')
            settext(controls['detail'], text)
        log(text)
        if event.get('menuPending'): log(event.get('hint', ''))

    def worker(action, prank=False, target_language='zh', features=()):
        code = 1
        child = None
        try:
            if action == 'status':
                from windows_connection import prepare_driver
                def driver_event(kind, **values):
                    events.put(('event', dict(type=kind, **values))); post(hwnd, EVENT_MESSAGE, 0, 0)
                prepare_driver(driver_event)
            env = os.environ.copy()
            env.pop('X2D_PAYLOAD_DIR', None)
            env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
            args = [str(D / 'runtime/python.exe'), '-X', 'utf8', '-B', '-u',
                    str(D / 'x2d_play_software.py'), action]
            if action == 'install':
                args += ['--language', target_language, '--interactive-confirmation']
                args += ['--features', *features]
            if prank:
                args.append('--prank-ibis')
            child = subprocess.Popen(args, cwd=str(D), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.PIPE if action == 'install' else subprocess.DEVNULL,
                                     text=True, encoding='utf-8', errors='replace', creationflags=0x08000000)
            for line in child.stdout:
                if not line.startswith('X2D_EVENT '): continue
                try: obj = json.loads(line[10:])
                except ValueError: continue
                if isinstance(obj, dict):
                    if obj.get('type') == 'confirmation':
                        response = queue.Queue(maxsize=1)
                        events.put(('confirmation', (obj, response, target_language)))
                        post(hwnd, EVENT_MESSAGE, 0, 0)
                        child.stdin.write(CONTINUE if response.get() is True else CANCEL)
                        child.stdin.flush()
                        continue
                    events.put(('event', obj)); post(hwnd, EVENT_MESSAGE, 0, 0)
            code = child.wait()
        except Exception as error:
            from windows_connection import DriverPreparationError
            text = str(error) if isinstance(error, DriverPreparationError) else '无法启动操作，请重新解压完整安装包后重试'
            events.put(('event', {'type': 'error', 'message': text}))
        finally:
            if child is not None and child.stdin:
                try: child.stdin.close()
                except OSError: pass
            events.put(('done', code)); post(hwnd, EVENT_MESSAGE, 0, 0)

    def start(action):
        if update_state['busy']: return
        features = tuple(selected_features())
        if action == 'install' and not features: return
        if not session.start(action): return
        buttons()
        settext(controls['state'], {'status': '正在检查相机…', 'install': '准备安装…', 'restore': '准备恢复…'}[action])
        send(controls['progress'], 0x0402, 0, 0)
        prank = action == 'install' and session.model == '907X & CFV 100C' and send(controls['prank'], 0x00F0, 0, 0) == 1
        if prank: log('已选择 907 防抖彩蛋：第 11 格为彩蛋，第 12 格为耍起功能。')
        threading.Thread(target=worker, args=(action, prank, language.language, features), daemon=True).start()

    def update_worker(wanted):
        child = None
        try:
            env = os.environ.copy()
            env.pop('X2D_PAYLOAD_DIR', None)
            env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1')
            args = [str(D / 'runtime/python.exe'), '-B', '-u', str(D / 'app_updates.py'),
                    'install' if wanted else 'check', '--current', VERSION, '--platform', 'win',
                    '--target', str(D), '--parent', str(os.getpid())]
            if wanted: args += ['--wanted', wanted]
            launch = subprocess.Popen if wanted else update_check.launch
            child = launch(args, env=env, cwd=str(D), stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=0x08000000)
            if child is None: return
            received = False
            for line in child.stdout:
                if closing.is_set(): break
                if not line.startswith('TOOLKIT_UPDATE '): continue
                event = json.loads(line[15:])
                received |= event.get('type') in ('available', 'current', 'error', 'restart')
                events.put(('update', event)); post(hwnd, EVENT_MESSAGE, 0, 0)
            code = child.wait()
            if not received: raise RuntimeError('update process ended without result')
        except Exception:
            if not closing.is_set():
                events.put(('update', dict(type='error', message='软件更新未完成，请检查网络连接或重新下载完整安装包；当前应用仍保留')))
        finally:
            if child is not None:
                if not wanted:
                    try: stop_process(child)
                    finally: update_check.release(child)
                child.stdout.close()
            if not closing.is_set():
                events.put(('update_done', None)); post(hwnd, EVENT_MESSAGE, 0, 0)

    def start_update(install=False):
        if closing.is_set() or session.busy or update_state['busy']: return
        if install and not update_state['version']: return
        update_state['busy'] = True
        update_state['installing'] = install
        buttons()
        threading.Thread(target=update_worker, args=(update_state['version'] if install else '',), daemon=True).start()

    @PROC
    def procedure(window, msg, wp, lp):
        nonlocal dpi
        try:
            if msg == 0x000F:
                skin.paint_parent(window,content_width,viewport.offset,main=window==main_handle)
                return 0
            if msg == 0x0014:return 1  # Painting fills the invalid region without background flicker.
            if window==main_handle:
                if msg==0x0005:refresh_layout();return 0
                if msg in (0x0115,0x020A):
                    if msg==0x020A:
                        delta=C.c_short((wp>>16)&0xffff).value
                        viewport.scroll(viewport.offset-delta/120*54)
                    else:
                        action=wp&0xffff
                        info=ScrollInfo(C.sizeof(ScrollInfo),0x10,0,0,0,0,0)
                        getscroll(window,1,C.byref(info))
                        steps={0:-24,1:24,2:-viewport.height+24,3:viewport.height-24}
                        if action in steps:viewport.scroll(viewport.offset+steps[action])
                        elif action in (4,5):viewport.scroll(info.track*96/dpi)
                        elif action==6:viewport.scroll(0)
                        elif action==7:viewport.scroll(viewport.maximum)
                    refresh_layout();return 0
            if msg==0x02E0:  # Per-monitor DPI: use Windows' suggested frame, then rescale all children.
                window_dpis[window]=wp&0xffff or 96
                if window==main_handle:dpi=window_dpis[window]
                skin.refresh(dpi=dpi)
                rect=C.cast(lp,C.POINTER(W.RECT)).contents
                suggested=W.RECT(rect.left,rect.top,rect.right,rect.bottom)
                monitor=api(user,'MonitorFromRect',W.HANDLE,C.POINTER(W.RECT),W.DWORD)(C.byref(suggested),2)
                info=MonitorInfo(C.sizeof(MonitorInfo),W.RECT(),W.RECT(workarea.left,workarea.top,workarea.right,workarea.bottom),0)
                api(user,'GetMonitorInfoW',W.BOOL,W.HANDLE,C.POINTER(MonitorInfo))(monitor,C.byref(info))
                width=min(rect.right-rect.left,info.work.right-info.work.left)
                height=min(rect.bottom-rect.top,max(200,info.work.bottom-info.work.top-32))
                left=max(info.work.left,min(rect.left,info.work.right-width))
                top=max(info.work.top,min(rect.top,info.work.bottom-height))
                position(window,None,left,top,width,height,0x14)
                refresh_layout();return 0
            if window == settings_state['window']:
                if msg == 0x0010: show(window,0); return 0
                if msg == 0x0002: return 0
            if window == confirmation_state['window']:
                if msg == 0x0010:
                    confirmation_state['answer'] = False; return 0
                if msg == 0x0002: return 0
                if msg == 0x0111 and (wp >> 16) == 0:
                    identity = wp & 0xFFFF
                    if identity in (2, 201, 202):
                        confirmation_state['answer'] = identity == 202; return 0
            if window==main_handle and msg==0x0202 and not session.busy and not update_state['busy']:
                x=C.c_short(lp&0xffff).value*96/dpi; y=C.c_short((lp>>16)&0xffff).value*96/dpi+viewport.offset
                if 392<=x<=952:
                    key='afcchoice' if 127<=y<198 else 'buffchoice' if 198<=y<288 else 'brightnesschoice' if 288<=y<359 else None
                    if key:
                        send(controls[key],0x00F1,0 if send(controls[key],0x00F0,0,0)==1 else 1,0);buttons();return 0
            if msg == 0x0010:  # WM_CLOSE
                if session.busy or (update_state['busy'] and update_state['installing']):
                    messagebox(window, language.text('操作尚未结束，请等待完成后退出应用。'), language.text('操作进行中'), 0x40)
                else:
                    closing.set()
                    update_check.close()
                    destroy(window)
                return 0
            if msg == 0x0002:
                quitmessage(0); return 0
            if msg == 0x0111:  # WM_COMMAND
                if lp in placements and (wp>>16) in (0x0100,6):  # EDIT/BUTTON focus: reveal tabbed controls.
                    spec=placements[lp]
                    if spec['parent']==main_handle:
                        rect=main_layout(content_width,language.language).get(spec['key'],spec['rect'])
                        viewport.reveal(rect[1],rect[3]);refresh_layout()
                if (wp & 0xFFFF) == 104 and (wp >> 16) == 1:  # CBN_SELCHANGE
                    change_language(); return 0
                if (wp >> 16) == 0:
                    if (wp & 0xFFFF) == 113: show(settings_state['window'],0); return 0
                    if (wp & 0xFFFF) in (110,111,112): buttons(); return 0
                    if (wp & 0xFFFF) == 107: show_settings(); return 0
                    if (wp & 0xFFFF) == 108:
                        if not preferences.set_auto_check(send(controls['automaticupdates'],0x00F0,0,0)==1):
                            log('设置无法保存，本次选择仅在当前运行中生效。')
                        return 0
                    if (wp & 0xFFFF) == 109: start_update(install=True); return 0
                    if (wp & 0xFFFF) == 106: start_update(); return 0
                    action = {101: 'status', 102: 'install', 103: 'restore'}.get(wp & 0xFFFF)
                    if action: start(action); return 0
            if msg == EVENT_MESSAGE:
                while True:
                    try: kind, value = events.get_nowait()
                    except queue.Empty: break
                    if kind == 'confirmation':
                        request, response, target_language = value
                        approved = False
                        try:
                            if (session.busy and session.action == 'install' and
                                request.get('language') == target_language and
                                all(isinstance(request.get(key), str) for key in ('title','body','cancel','proceed'))):
                                approved = confirm_dialog(request)
                        finally:
                            response.put(approved)
                    elif kind == 'event': consume(value)
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
                    elif kind == 'update_done':
                        update_state['busy'] = False; buttons()
                    else:
                        if not session.finish(value) and not session.error_received:
                            text = '操作尚未确认完成，请保持连接并重新检查状态。'
                            settext(controls['detail'], text); log(text)
                        buttons()
                return 0
            if msg in (0x0138, 0x0133, 0x0135):  # static/edit/button backgrounds
                key=placements.get(lp,{}).get('key','')
                background=skin.rgb(COLORS['surface'] if key in ('summarylabel','selectionsummary','state') else COLORS['background'])
                setbk(wp, background)
                color=text_style(key,language.language)[2]
                setcolor(wp,skin.rgb(color))
                return skin.resource('brush',COLORS['surface']) if key in ('summarylabel','selectionsummary','state') else white
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
    screenwidth = api(user, 'GetSystemMetrics', C.c_int, C.c_int)(0)
    screenheight = user.GetSystemMetrics(1)
    workarea=W.RECT(0,0,screenwidth,screenheight)
    api(user,'SystemParametersInfoW',W.BOOL,W.UINT,W.UINT,W.LPVOID,W.UINT)(0x30,0,C.byref(workarea),0)
    available=max(320,(workarea.bottom-workarea.top-64)*96/dpi)
    viewport.resize(min(HEIGHT,available))
    frame_style=0x02CA0000 | (0x00200000 if viewport.maximum else 0)
    width,height=outer_size(WIDTH,viewport.height,frame_style)
    hwnd = create(0, wc.name, language.text('x2d/907 扩展功能工具包') + ' · ' + VERSION, frame_style,
                  max(0, (screenwidth-width)//2), max(0, (screenheight-height)//2),
                  width, height, None, None, instance, None)
    if not hwnd: raise C.WinError(C.get_last_error())
    main_handle=hwnd
    window_dpis[hwnd]=dpi
    localized_sources[hwnd] = 'x2d/907 扩展功能工具包' + ' · ' + VERSION

    def control(key, classname, text, x, y, w, h, extra=0, identity=0, textfont=None, ex=0, parent=None):
        owner=hwnd if parent is None else parent
        if classname=='BUTTON':extra|=0x4000  # Native focus notifications, including keyboard navigation.
        handle = create(ex, classname, language.text(text), 0x50000000 | extra,
                        scale(x), scale(y), scale(w), scale(h), owner, identity or None, instance, None)
        if not handle: raise C.WinError(C.get_last_error())
        controls[key] = handle
        if key not in ('logs','language'): localized_sources[handle] = text
        size,bold,_=text_style(key,language.language)
        role=(12,False,True) if key=='logs' else (size,bold,False)
        placements[handle]=dict(key=key,parent=owner,rect=(x,y,w,h),font=role)
        send(handle,0x0030,skin.font(*role),1)
        if classname=='BUTTON':skin.attach(handle,key,'checkbox' if (extra&15)==3 else 'button',primary=key=='installbutton',size=(w,h),dpi=window_dpis.get(owner,dpi))
        elif classname=='COMBOBOX':skin.attach(handle,key,'dropdown',size=(w,28),dpi=window_dpis.get(owner,dpi))
        elif classname=='msctls_progress32':skin.attach(handle,key,'progress',size=(w,h))
        return handle

    layout=main_layout(language=language.language)
    def item(key,classname,text,**kwargs):return control(key,classname,text,*layout[key],**kwargs)
    item('title','STATIC','x2d/907 扩展功能工具包',textfont=titlefont)
    item('version','STATIC','v'+VERSION)
    item('settingsbutton','BUTTON','设置',extra=0x10000,identity=107)
    item('subtitle','STATIC','X2D 100C / 907X 100C · 固件 4.2.0')
    item('logheading','STATIC','运行日志')
    item('logstate','STATIC','等待连接',extra=2)
    item('featureheading','STATIC','选择要安装的功能')
    item('featurecount','STATIC','')
    item('afcchoice','BUTTON','AF-C 连续自动对焦',extra=0x10003,identity=110)
    item('buffchoice','BUTTON','对焦加速',extra=0x10003,identity=111)
    item('brightnesschoice','BUTTON','后屏自动亮度',extra=0x10003,identity=112)
    for key in ('afcchoice','buffchoice','brightnesschoice'): send(controls[key],0x00F1,1,0)
    item('afc','STATIC','AF-C 连续自动对焦',textfont=strong)
    item('afcdescription','STATIC','在相机上开启连续自动对焦。',textfont=small)
    item('buff','STATIC','对焦加速',textfont=strong)
    item('buffdescription','STATIC','对焦加速通过将镜头转速提高三倍实现，可安装，但不建议老镜头用户在相机内开启该功能。',textfont=small)
    item('brightness','STATIC','后屏自动亮度',textfont=strong)
    item('brightnessdescription','STATIC','根据环境光调节后屏亮度，可设置最高亮度。',textfont=small)
    item('dependency','STATIC','三项功能可分别选择。')
    item('summarylabel','STATIC','本次安装')
    item('selectionsummary','STATIC','')
    item('prank','BUTTON','添加防抖功能（907 彩蛋）',extra=0x10003,identity=105)
    item('state','STATIC','等待连接检查',extra=0x4000)
    item('detail','STATIC','连接相机并开机，点击“已连接”自动准备驱动并检查状态。\r\n907X 100C 适配版待实机验证。',textfont=small)
    item('progress','msctls_progress32','')
    item('statusbutton','BUTTON','已连接',extra=0x10001,identity=101)
    item('installbutton','BUTTON','安装所选功能',extra=0x10000,identity=102)
    item('restorebutton','BUTTON','恢复原状',extra=0x10000,identity=103)
    item('note','STATIC','日志保存在本地，便于查看操作进度。',textfont=small)
    item('logs','EDIT','',extra=0x00210844,textfont=small)
    refresh_layout()
    log('工具包 Windows 版本：' + VERSION)
    from app_updates import notice
    log(notice(D))
    log('请将相机开机并连接数据线，点击“已连接”；程序会自动准备驱动并检查相机状态。')
    log('若相机提示连接方式，可选择“大容量存储”。')
    buttons()
    show(hwnd, 5); update(hwnd)
    if preferences.auto_check: start_update()
    message = W.MSG()
    try:
        while True:
            result = getmsg(C.byref(message), None, 0, 0)
            if result <= 0: break
            if not dialog(hwnd, C.byref(message)):
                translate(C.byref(message)); dispatch(C.byref(message))
    finally:
        closing.set()
        update_check.close()
        skin.close()
        deleteobject(white)


if __name__ == '__main__':
    try: main()
    except Exception:
        if os.name == 'nt':
            language = Localizer(Path(os.environ.get('LOCALAPPDATA', str(D))) / 'X2DPlay' / 'language.json')
            C.windll.user32.MessageBoxW(None, language.text('应用未能启动，请重新解压完整 Windows 安装包。'), language.text('x2d/907一键扩展功能-工具包'), 0x10)
        raise
