"""Native skin drawing/state and monitor-scale layout; no Windows or camera."""
import ctypes as C
import unittest
from unittest.mock import patch
import windows_ui as ui


class API:
    def __init__(self):
        self.functions={};self.calls=[];self.checked=False;self.pressed=False
        self.enabled=True;self.next_handle=1000;self.deleted=[]
    def __getattr__(self,name):
        if name not in self.functions:
            def function(*args):return self.call(name,*args)
            self.functions[name]=function
        return self.functions[name]
    def call(self,name,*args):
        self.calls.append((name,args))
        if name=='GetClientRect':
            rect=args[1]._obj;rect.right=212;rect.bottom=64;return 1
        if name=='GetWindowTextW':args[1].value='Connected';return 9
        if name=='SendMessageW':
            if args[1]==0x00F0:return int(self.checked)
            if args[1]==0x00F2:return 4 if self.pressed else 0
            if args[1]==0x0408:return 40
        if name=='IsWindowEnabled':return self.enabled
        if name=='GetFocus':return 0
        if name in ('CreateFontW','CreatePen','CreateSolidBrush'):
            self.next_handle+=1;return self.next_handle
        if name=='DeleteObject':self.deleted.append(args[0]);return 1
        if name=='DefSubclassProc':return 73
        return 1


class NativeStyleTests(unittest.TestCase):
    def setUp(self):
        patcher=patch.object(C,'WINFUNCTYPE',C.CFUNCTYPE,create=True)
        patcher.start();self.addCleanup(patcher.stop)
        self.api=API();self.skin=ui.NativeStyle(self.api,self.api,self.api)

    def test_native_controls_keep_default_keyboard_and_check_state_handling(self):
        self.skin.attach(101,'prank','checkbox')
        for message in (0x0100,0x0101,0x0201,0x0202,0x00F1):
            self.assertEqual(self.skin.control_message(101,message,32,0,1,0),73)
        self.assertTrue(any(name=='InvalidateRect' for name,args in self.api.calls))
        self.api.checked=True
        self.skin.paint_control(101,222)
        self.assertTrue(any(name=='LineTo' for name,args in self.api.calls),'Checked native state draws the check mark')

    def test_button_states_dpi_and_gdi_cleanup(self):
        self.skin.attach(101,'statusbutton',primary=True,dpi=192)
        self.api.pressed=True
        self.skin.paint_control(101,222)
        self.assertEqual(self.skin.dpi,96,'One window must not change another monitor DPI')
        self.assertTrue(any(name=='CreateFontW' and args[0]==-26 for name,args in self.api.calls))
        colors=[args[0] for name,args in self.api.calls if name=='CreateSolidBrush']
        self.assertIn(self.skin.rgb(ui.COLORS['blue_pressed']),colors)
        self.api.enabled=False
        self.skin.paint_control(101,222)
        self.assertTrue(any(name=='CreateSolidBrush' and args[0]==self.skin.rgb(ui.COLORS['disabled']) for name,args in self.api.calls))
        self.assertEqual(sum(name=='SaveDC' for name,args in self.api.calls),sum(name=='RestoreDC' for name,args in self.api.calls))
        expected=set(self.skin.fonts.values())|set(self.skin.brushes.values())|set(self.skin.pens.values())
        self.skin.close();self.assertEqual(set(self.api.deleted),expected)

    def test_progress_and_parent_vectors_use_current_state_and_restore_dc(self):
        self.skin.attach(101,'progress','progress')
        self.skin.paint_control(101,222)
        self.skin.paint_parent(303)
        self.assertTrue(any(name=='Ellipse' for name,args in self.api.calls),'Sun icon has a center ring')
        self.assertTrue(any(name=='SendMessageW' and args[1]==0x0408 for name,args in self.api.calls))
        self.assertEqual(sum(name=='SaveDC' for name,args in self.api.calls),sum(name=='RestoreDC' for name,args in self.api.calls))

    def test_callback_removes_destroyed_handles_and_respects_frozen_language(self):
        self.skin.language='zh'
        self.skin.attach(101,'confirmation_proceed',language='en')
        self.skin.paint_control(101,222)
        self.assertTrue(any(name=='CreateFontW' and args[-1]=='Segoe UI' for name,args in self.api.calls))
        self.assertEqual(self.skin.language,'zh')
        self.skin.control_message(101,0x0082,0,0,1,0)
        self.assertNotIn(101,self.skin.controls)
        self.assertTrue(any(name=='RemoveWindowSubclass' for name,args in self.api.calls))

    def test_failed_skin_attachment_leaves_native_button_usable(self):
        original=self.api.call
        self.api.call=lambda name,*args:0 if name=='SetWindowSubclass' else original(name,*args)
        self.skin.attach(101,'statusbutton')
        self.assertNotIn(101,self.skin.controls)


class LayoutTests(unittest.TestCase):
    def test_controls_fit_and_feature_descriptions_keep_the_same_alignment(self):
        layout=ui.main_layout()
        for key,(x,y,w,h) in layout.items():
            self.assertGreater(w,0,key);self.assertGreater(h,0,key)
            self.assertLessEqual(x+w,ui.WIDTH,key);self.assertLessEqual(y+h,ui.HEIGHT,key)
        self.assertEqual(layout['afc'][0],layout['brightnessdescription'][0])
        for label,caption in (('afc','afcdescription'),('buff','buffdescription'),('brightness','brightnessdescription')):
            self.assertLessEqual(layout[label][1]+layout[label][3],layout[caption][1])
        self.assertLess(layout['progress'][1],layout['statusbutton'][1])
        self.assertLess(layout['buffdescription'][1]+layout['buffdescription'][3],layout['brightness'][1])
        self.assertEqual(ui.text_style('buffdescription')[2],ui.COLORS['orange'])

    def test_short_monitor_scroll_and_keyboard_focus_keep_actions_reachable(self):
        viewport=ui.Viewport(560)
        viewport.scroll(9999);self.assertEqual(viewport.offset,ui.HEIGHT-560)
        viewport.reveal(28,34);self.assertEqual(viewport.offset,16)
        viewport.reveal(551,44);self.assertEqual(viewport.offset,47)
        viewport.resize(ui.HEIGHT);self.assertEqual(viewport.offset,0)
        self.assertEqual(viewport.maximum,0)

    def test_native_font_cache_tracks_language_and_per_window_dpi(self):
        api=API()
        with patch.object(C,'WINFUNCTYPE',C.CFUNCTYPE,create=True):
            skin=ui.NativeStyle(api,api,api)
            values=[skin.font(14,dpi=dpi,language=language) for dpi in (96,120,144,192) for language in ('zh','en')]
            self.assertEqual(len(set(values)),8)
            self.assertEqual(skin.font(14,dpi=120,language='en'),values[3])
            skin.close()


if __name__=='__main__':unittest.main()
