"""Execute Windows UI callbacks with system API substitutes; no USB or worker process."""
import ctypes as C
import io,json,re,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import windows_app as app
from reinstall_confirmation import CONTINUE, CANCEL, prompt
from app_settings import UpdatePreferences as RealUpdatePreferences

class Function:
    def __init__(self,name,owner): self.name,self.owner=name,owner
    def __call__(self,*args): return self.owner.call(self.name,*args)

class WindowAPI:
    def __init__(self):
        self.functions={};self.controls={};self.enabled={};self.next_handle=100;self.selection=0;self.snapshots=[];self.proc=None;self.session=None
    def __getattr__(self,name):
        return self.functions.setdefault(name,Function(name,self))
    def call(self,name,*args):
        if name=='CreateWindowExW':
            self.next_handle+=1;handle=self.next_handle
            self.controls[handle]={'class':args[1],'text':args[2],'id':args[9]};return handle
        if name=='SetWindowTextW': self.controls[args[0]]['text']=args[1];return True
        if name=='EnableWindow': self.enabled[args[0]]=bool(args[1]);return True
        if name=='RegisterClassExW': self.proc=args[0]._obj.proc;return 1
        if name=='GetModuleHandleW': return 1
        if name=='LoadCursorW': return 1
        if name in ('CreateFontW','CreateSolidBrush'): return 1
        if name=='GetDpiForSystem': return 96
        if name=='GetSystemMetrics': return 1440 if args[0]==0 else 1200
        if name=='SendMessageW':
            if args[1]==0x014E: self.selection=args[2]
            if args[1]==0x0147: return self.selection
            return 0
        if name=='GetMessageW':
            self.proc(101,0x0111,107,0)
            self.snapshots.append({key:value.copy() for key,value in self.controls.items()})
            self.session.busy=True
            self.selection=2
            self.proc(101,0x0111,(1<<16)|104,0)
            self.snapshots.append({key:value.copy() for key,value in self.controls.items()})
            assert self.session.busy and not self.session.verified
            self.session.busy=False
            return 0
        return 1

class WindowsLanguageUITests(unittest.TestCase):
    def setUp(self):
        preferences=patch.object(app,'UpdatePreferences',return_value=SimpleNamespace(auto_check=False,set_auto_check=lambda value:True))
        preferences.start();self.addCleanup(preferences.stop)

    def test_window_close_cancels_real_blocked_update_child_without_camera_work(self):
        ready = threading.Event(); children = []
        popen = subprocess.Popen
        def check_child(args, **kwargs):
            assert args[4] == 'check'
            kwargs.pop('creationflags',None)
            child = popen([sys.executable,'-c','import time; time.sleep(60)'], **kwargs)
            children.append(child); ready.set(); return child
        class CloseAPI(WindowAPI):
            closed = False
            def call(self,name,*args):
                if name == 'GetMessageW':
                    self.proc(101,0x0111,106,0)
                    assert ready.wait(3), 'Check process must be running before close'
                    self.proc(101,0x0010,0,0)
                    assert self.closed
                    return 0
                if name == 'DestroyWindow': self.closed=True; return 1
                return super().call(name,*args)
        api = CloseAPI()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder},getpid=lambda:123)),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app.subprocess,'Popen',side_effect=check_child):
                app.main()
        self.assertEqual(len(children),1)
        self.assertIsNotNone(children[0].poll())

    def test_camera_work_and_update_install_still_block_window_close(self):
        for camera in (False,True):
            class ProtectedAPI(WindowAPI):
                destroyed=0
                blocked=0
                def call(self,name,*args):
                    if name == 'PostMessageW': self.proc(*args); return 1
                    if name == 'DestroyWindow': self.destroyed+=1; return 1
                    if name == 'MessageBoxW': self.blocked+=1; return 1
                    if name == 'GetMessageW':
                        if camera:
                            self.session.start('status')
                        else:
                            self.proc(101,0x0111,106,0)
                            self.proc(101,0x0111,109,0)
                        self.proc(101,0x0010,0,0)
                        return 0
                    return super().call(name,*args)
            api = ProtectedAPI()
            class Session(app.Session):
                def __init__(self): super().__init__(); api.session=self
            class Thread:
                def __init__(self,target,args,daemon): self.target,self.args=target,args
                def start(self):
                    if not self.args[0]: self.target(*self.args)
            event = dict(type='available',version='0.4.5',message='发现软件新版本：0.4.5')
            child = SimpleNamespace(stdout=io.StringIO('TOOLKIT_UPDATE '+json.dumps(event)+'\n'),wait=lambda:0,poll=lambda:0)
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder},getpid=lambda:123)),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.threading,'Thread',Thread),patch.object(app.subprocess,'Popen',return_value=child):
                    app.main()
            self.assertEqual(api.destroyed,0,'Protected operation must block close')
            self.assertEqual(api.blocked,1)

    def test_monitor_dpi_rescales_controls_and_tab_focus_reveals_hidden_actions(self):
        class MonitorAPI(WindowAPI):
            dpi=96
            height=560
            moves={}
            fonts=[]
            def call(self,name,*args):
                if name=='GetClientRect':
                    rect=args[1]._obj;rect.right=round(580*self.dpi/96);rect.bottom=round(self.height*self.dpi/96)
                    return 1
                if name=='CreateFontW':self.fonts.append((args[0],args[-1]))
                if name=='MoveWindow':self.moves[args[0]]=args[1:5];return 1
                if name=='GetMessageW':
                    self.proc(101,0x0005,0,0)
                    logs=next(h for h,item in self.controls.items() if item['class']=='EDIT')
                    install=next(h for h,item in self.controls.items() if item['id']==102)
                    self.proc(101,0x0111,0x100<<16,logs)
                    assert self.moves[logs][1]+self.moves[logs][3]<=560
                    self.proc(101,0x0111,(6<<16)|102,install)
                    assert 0<=self.moves[install][1]<560
                    self.dpi=144
                    frame=C.wintypes.RECT(10,10,910,910)
                    self.proc(101,0x02E0,144|(144<<16),C.addressof(frame))
                    assert self.moves[install][0]==round(146*1.5)
                    assert any(size==-33 for size,face in self.fonts)
                    self.proc(101,0x0111,107,0)
                    self.selection=2;self.proc(101,0x0111,(1<<16)|104,0)
                    assert any(size==-28 and face=='Segoe UI' for size,face in self.fonts)
                    assert not self.session.verified and not self.session.busy
                    return 0
                return super().call(name,*args)
        api=MonitorAPI()
        class Session(app.Session):
            def __init__(self):super().__init__();api.session=self
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder})),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.subprocess,'Popen') as worker:
                app.main();worker.assert_not_called()

    def test_startup_preference_manual_check_and_download_are_separate_actions(self):
        for automatic in (False,True):
            calls=[]
            class SettingsAPI(WindowAPI):
                checks={}
                started=False
                def call(self,name,*args):
                    if name=='SendMessageW':
                        if args[1]==0x00F1:self.checks[args[0]]=args[2]
                        if args[1]==0x00F0:return self.checks.get(args[0],0)
                    if name=='PostMessageW':self.proc(*args);return 1
                    if name=='GetMessageW':
                        if self.started:return 0
                        self.started=True
                        assert len(calls)==int(automatic)
                        self.proc(101,0x0111,107,0)
                        checkbox=next(h for h,item in self.controls.items() if item['id']==108)
                        assert self.checks[checkbox]==int(automatic)
                        self.checks[checkbox]=0;self.proc(101,0x0111,108,0)
                        self.proc(101,0x0111,106,0)
                        assert calls[-1][4]=='check'
                        # A known newer version must not turn the manual check into Install.
                        self.proc(101,0x0111,106,0)
                        assert calls[-1][4]=='check'
                        self.proc(101,0x0111,109,0)
                        assert calls[-1][4]=='install' and calls[-1][-2:]==['--wanted','0.4.3']
                        assert not self.session.busy and not self.session.verified
                        return 0
                    return super().call(name,*args)
            api=SettingsAPI()
            class Session(app.Session):
                def __init__(self):super().__init__();api.session=self
            class Thread:
                def __init__(self,target,args,daemon):self.target,self.args=target,args
                def start(self):self.target(*self.args)
            def child(args,**kwargs):
                calls.append(args)
                event=dict(type='available',version='0.4.3',message='发现软件新版本：0.4.3')
                if args[4]=='install':event=dict(type='error',message='软件更新未完成')
                return SimpleNamespace(stdout=io.StringIO('TOOLKIT_UPDATE '+json.dumps(event)+'\n'),wait=lambda:0,poll=lambda:0)
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'X2DPlay/settings.json'
                RealUpdatePreferences(path).set_auto_check(automatic)
                with patch.object(app,'UpdatePreferences',RealUpdatePreferences),patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder},getpid=lambda:123)),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.threading,'Thread',Thread),patch.object(app.subprocess,'Popen',side_effect=child):
                    app.main()
                self.assertFalse(RealUpdatePreferences(path).auto_check)
                self.assertEqual(len(calls),int(automatic)+3)

    def test_reinstall_dialog_uses_frozen_target_language_and_explicit_response(self):
        for target_language, answer in (('en',202),('zh',201),('zh-Hant',202),('en','close')):
            pending=[]; replies=[]
            class Input(io.StringIO):
                def close(self):
                    replies.append(self.getvalue()); super().close()
            child=SimpleNamespace(stdin=Input(),stdout=io.StringIO(
                'X2D_EVENT '+json.dumps(dict(type='confirmation',**prompt(target_language)))+'\n'+
                'X2D_EVENT '+json.dumps(dict(type='cancelled',message='已取消重新安装，相机未被修改。'))+'\n'),wait=lambda:0)
            class ConfirmationAPI(WindowAPI):
                started=False
                popup=None
                popup_controls=None
                quit_count=0
                def call(self,name,*args):
                    if name=='CreateWindowExW':
                        result=super().call(name,*args)
                        if args[2]==prompt(target_language)['title']:self.popup=result
                        if args[9]==201:assert args[3]&1, 'Cancel must be default'
                        return result
                    if name=='PostMessageW':
                        self.proc(*args);return 1
                    if name=='PostQuitMessage':self.quit_count+=1;return 1
                    if name=='GetMessageW':
                        if self.popup is not None:
                            self.popup_controls={key:value.copy() for key,value in self.controls.items()}
                            if answer=='close':self.proc(self.popup,0x0010,0,0)
                            else:self.proc(self.popup,0x0111,answer,0)
                            return 1
                        if self.started:return 0
                        self.started=True;self.session.verified=True
                        self.proc(101,0x0111,107,0)
                        self.proc(101,0x0111,102,0)
                        self.selection=0 if target_language=='en' else 2
                        self.proc(101,0x0111,(1<<16)|104,0)
                        fn,arguments=pending.pop()
                        assert arguments[-1]==target_language
                        fn(*arguments)
                        assert not self.session.busy and self.session.verified
                        return 0
                    return super().call(name,*args)
            api=ConfirmationAPI()
            class Session(app.Session):
                def __init__(self):super().__init__();api.session=self
            class Thread:
                def __init__(self,target,args,daemon):self.target,self.args=target,args
                def start(self):pending.append((self.target,self.args))
            with tempfile.TemporaryDirectory() as folder:
                preferences=Path(folder)/'X2DPlay/language.json'
                preferences.parent.mkdir();preferences.write_text(json.dumps(dict(language=target_language)))
                with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder})),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.threading,'Thread',Thread),patch.object(app.subprocess,'Popen',return_value=child) as worker:
                    app.main()
                arguments=worker.call_args.args[0]
                self.assertEqual(arguments[arguments.index('--language')+1],target_language)
                self.assertIn('--interactive-confirmation',arguments)
            shown=[value['text'] for value in api.popup_controls.values()]
            for key in ('title','body','cancel','proceed'):self.assertIn(prompt(target_language)[key],shown)
            self.assertEqual(replies,[CONTINUE if answer==202 else CANCEL])
            self.assertEqual(api.quit_count,0,'Closing the prompt must not quit the app')
            self.assertTrue(api.enabled[101])

    def test_update_check_blocks_writes_but_allows_window_close_before_worker_launch(self):
        class UpdateAPI(WindowAPI):
            closed=False
            def call(self,name,*args):
                if name=='GetMessageW':
                    self.session.verified=True
                    self.proc(101,0x0111,107,0)
                    self.proc(101,0x0111,106,0)
                    self.proc(101,0x0111,102,0)
                    self.proc(101,0x0111,103,0)
                    self.proc(101,0x0111,106,0)
                    self.proc(101,0x0010,0,0)
                    assert self.closed, 'Read-only update check must allow close'
                    assert not self.session.busy and self.session.action==''
                    for h,item in self.controls.items():
                        if item['id'] in (101,102,103,106):assert not self.enabled[h]
                    return 0
                if name=='DestroyWindow':self.closed=True;return 1
                return super().call(name,*args)
        api=UpdateAPI()
        class Session(app.Session):
            def __init__(self):super().__init__();api.session=self
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder})),patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.threading,'Thread') as thread,patch.object(app.subprocess,'Popen') as worker:
                app.main()
                self.assertEqual(thread.call_count,1)
                worker.assert_not_called()

    def test_real_selection_callback_refreshes_all_controls_logs_and_preferences(self):
        api=WindowAPI()
        class Session(app.Session):
            def __init__(self): super().__init__();api.session=self
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder})), patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.subprocess,'Popen') as worker:
                app.main()
                worker.assert_not_called()
            initial,english=api.snapshots
            self.assertTrue(any(x['text']=='x2d/907一键扩展功能-工具包' for x in initial.values()))
            self.assertTrue(any(x['text']=='X2D/907 One-Click Extension Toolkit' for x in english.values()))
            for item in english.values(): self.assertFalse(re.search('[\u3400-\u9fff]',item['text']),item)
            labels={item['id']:item['text'] for item in english.values() if item['id']}
            self.assertEqual(labels[106],'Check for Updates');
            self.assertEqual(labels[101],'Connected');self.assertEqual(labels[102],'Install');self.assertEqual(labels[103],'Restore original')
            for handle,item in english.items():
                if item['id'] in (102,103): self.assertFalse(api.enabled[handle])
            self.assertEqual(json.loads((Path(folder)/'X2DPlay/language.json').read_text()),{'language':'en'})
            saved=(Path(folder)/'X2DPlay/latest.log').read_text()
            self.assertIn('Click Connected',saved.replace('click Connected','Click Connected'))
            self.assertFalse(re.search('[\u3400-\u9fff]',saved))

if __name__=='__main__': unittest.main()
