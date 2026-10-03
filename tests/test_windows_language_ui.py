"""Execute Windows UI callbacks with system API substitutes; no USB or worker process."""
import ctypes as C
import json,re,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import windows_app as app

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
            self.snapshots.append({key:value.copy() for key,value in self.controls.items()})
            self.session.busy=True
            self.selection=1
            self.proc(101,0x0111,(1<<16)|104,0)
            self.snapshots.append({key:value.copy() for key,value in self.controls.items()})
            assert self.session.busy and not self.session.verified
            self.session.busy=False
            return 0
        return 1

class WindowsLanguageUITests(unittest.TestCase):
    def test_real_selection_callback_refreshes_all_controls_logs_and_preferences(self):
        api=WindowAPI()
        class Session(app.Session):
            def __init__(self): super().__init__();api.session=self
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(app,'os',SimpleNamespace(name='nt',environ={'LOCALAPPDATA':folder})), patch.object(app.C,'WinDLL',side_effect=lambda *a,**k:api,create=True),patch.object(app.C,'WINFUNCTYPE',C.CFUNCTYPE,create=True),patch.object(app,'Session',Session),patch.object(app.subprocess,'Popen') as worker:
                app.main()
                worker.assert_not_called()
            initial,english=api.snapshots
            self.assertTrue(any(x['text']=='耍起功能' for x in initial.values()))
            self.assertTrue(any(x['text']=='Shuaqi' for x in english.values()))
            for item in english.values(): self.assertFalse(re.search('[\u3400-\u9fff]',item['text']),item)
            labels={item['id']:item['text'] for item in english.values() if item['id']}
            self.assertEqual(labels[101],'Connected');self.assertEqual(labels[102],'Install');self.assertEqual(labels[103],'Restore original')
            for handle,item in english.items():
                if item['id'] in (102,103): self.assertFalse(api.enabled[handle])
            self.assertEqual(json.loads((Path(folder)/'X2DPlay/language.json').read_text()),{'language':'en'})
            saved=(Path(folder)/'X2DPlay/latest.log').read_text()
            self.assertIn('Click Connected',saved.replace('click Connected','Click Connected'))
            self.assertFalse(re.search('[\u3400-\u9fff]',saved))

if __name__=='__main__': unittest.main()
