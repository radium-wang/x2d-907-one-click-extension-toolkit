"""Mac-aligned layout and GDI skin for native Windows controls.

Native BUTTON/EDIT/COMBOBOX controls retain input, accessibility and state.
Only their painting and placement change. No USB or application workers here.
"""
import ctypes as C
from ctypes import wintypes as W
import math
import json
from pathlib import Path

LOOK = json.loads((Path(__file__).with_name('desktop-ui.json')).read_text(encoding='utf-8'))
WIDTH, HEIGHT = LOOK['width'], LOOK['height']
COLORS = LOOK['colors']

def text_style(key, language='zh'):
    if key=='title':return 21, True, COLORS['text']
    if key in ('featureheading','settingsheading'):return 16,True,COLORS['text']
    if key=='logheading':return 14,True,COLORS['text']
    if key in ('version','state','featurecount','dependency','summarylabel'):return 12,False,COLORS['secondary']
    if key in ('note','logstate'):return 11,False,COLORS['secondary']
    if key=='selectionsummary':return 14,False,COLORS['text']
    if key=='buffdescription':return 12,False,COLORS['orange']
    if key in ('pixelshift','facetracking'):return 14,True,COLORS['disabled_text']
    if key in ('pixelshiftdescription','facetrackingdescription'):return 12,False,COLORS['disabled_text']
    if key in ('afc','buff','brightness','eye'):return 14,True,COLORS['text']
    if key=='subtitle':return 13,False,COLORS['secondary']
    if key in ('detail','note','updatesdescription','selectionsummary') or key.endswith('description'):return 12,False,COLORS['secondary']
    return 14,False,COLORS['text']


def main_layout(width=WIDTH, language='zh'):
    """Logical pixels, scaled once by the window's current monitor DPI."""
    layout = dict(LOOK['layout']);layout.update(LOOK.get('languageLayout',{}).get(language,{}))
    return {key:tuple(rect) for key,rect in layout.items()}


def button_colors(primary=False, enabled=True, hovered=False, pressed=False):
    if not enabled: return ('#88bcfc','#ffffff') if primary else (COLORS['background'],COLORS['disabled_text'])
    if primary:
        return COLORS['blue_pressed' if pressed else 'blue_hover' if hovered else 'blue'], '#ffffff'
    return ('#dedee1' if pressed else '#e6e6e8' if hovered else COLORS['background']), COLORS['text']


class Viewport:
    def __init__(self, height=HEIGHT):
        self.height, self.offset = height, 0

    @property
    def maximum(self): return max(0, HEIGHT-self.height)

    def resize(self, height):
        self.height = max(1, height)
        self.scroll(self.offset)

    def scroll(self, offset):
        self.offset = min(self.maximum, max(0, round(offset)))
        return self.offset

    def reveal(self, y, height):
        if y < self.offset: self.scroll(y-12)
        elif y+height > self.offset+self.height: self.scroll(y+height-self.height+12)


def decorations(width=WIDTH, offset=0, language='zh'):
    """Shared vector geometry for native painting and the offline preview."""
    layout = main_layout(width,language)
    result = []
    for key,radius,color,border in [('box',10,'background',True),('logbox',9,'background',True),('summarybox',8,'surface',False)]:
        x,y,w,h = layout[key]
        result.append(('round',(x,y-offset,w,h,radius),COLORS[color],COLORS['border'] if border else None))
    for x,y,w in [(392,198,560),(392,288,560),(392,359,560),(392,430,560),(392,501,560),(43,140,310),(43,546,310)]:
        result.append(('line',(x,y-offset,w),COLORS['border'],None))
    for kind,key in [('focus','afcchoice'),('bolt','buffchoice'),('sun','brightnesschoice'),('eye','eyechoice'),('pixelshift','pixelshiftchoice'),('facetracking','facetrackingchoice')]:
        color='disabled_text' if key in ('pixelshiftchoice','facetrackingchoice') else 'secondary'
        result.append(('icon',(448,layout[key][1]-offset,18,18,kind),COLORS[color],None))
    result.append(('dot',(layout['state'][0]-13,layout['state'][1]+5-offset,8,8),COLORS['orange'],None))
    return result


def icon_lines(kind):
    if kind in LOOK.get('iconTiles',{}):return []
    if kind in LOOK.get('iconLines',{}):return LOOK['iconLines'][kind]
    if kind == 'focus':
        return [[(0,5),(0,1),(1,0),(5,0)],[(13,0),(17,0),(18,1),(18,5)],
                [(18,13),(18,17),(17,18),(13,18)],[(5,18),(1,18),(0,17),(0,13)]]
    if kind == 'bolt': return [[(10,0),(3,10),(9,10),(7,18),(15,7),(9,7),(10,0)]]
    result = []
    for index in range(8):
        angle=index*math.pi/4
        result.append([(9+6.5*math.cos(angle),9+6.5*math.sin(angle)),
                       (9+9*math.cos(angle),9+9*math.sin(angle))])
    return result


class Paint(C.Structure):
    _fields_=[('hdc',W.HDC),('erase',W.BOOL),('rect',W.RECT),
              ('restore',W.BOOL),('update',W.BOOL),('reserved',C.c_byte*32)]


class TrackMouse(C.Structure):
    _fields_=[('size',W.DWORD),('flags',W.DWORD),('window',W.HWND),('time',W.DWORD)]


class ScrollInfo(C.Structure):
    _fields_=[('size',W.UINT),('mask',W.UINT),('minimum',C.c_int),('maximum',C.c_int),
              ('page',W.UINT),('position',C.c_int),('track',C.c_int)]


class NativeStyle:
    def __init__(self, user, gdi, common, dpi=96):
        self.dpi=dpi
        self.controls={}
        self.fonts={}
        self.brushes={}
        self.pens={}
        self.hovered=set()
        self.language='zh'
        self.verified=False
        self.busy=False
        def api(dll,name,result,*args):
            fn=getattr(dll,name);fn.restype=result;fn.argtypes=list(args);return fn
        self.begin=api(user,'BeginPaint',W.HDC,W.HWND,C.POINTER(Paint))
        self.end=api(user,'EndPaint',W.BOOL,W.HWND,C.POINTER(Paint))
        self.client=api(user,'GetClientRect',W.BOOL,W.HWND,C.POINTER(W.RECT))
        self.invalidate=api(user,'InvalidateRect',W.BOOL,W.HWND,C.POINTER(W.RECT),W.BOOL)
        self.fill=api(user,'FillRect',C.c_int,W.HDC,C.POINTER(W.RECT),W.HBRUSH)
        self.drawtext=api(user,'DrawTextW',C.c_int,W.HDC,W.LPCWSTR,C.c_int,C.POINTER(W.RECT),W.UINT)
        self.gettext=api(user,'GetWindowTextW',C.c_int,W.HWND,W.LPWSTR,C.c_int)
        self.send=api(user,'SendMessageW',C.c_ssize_t,W.HWND,W.UINT,C.c_size_t,C.c_ssize_t)
        self.enabled=api(user,'IsWindowEnabled',W.BOOL,W.HWND)
        self.focus=api(user,'GetFocus',W.HWND)
        self.track=api(user,'TrackMouseEvent',W.BOOL,C.POINTER(TrackMouse))
        self.save=api(gdi,'SaveDC',C.c_int,W.HDC)
        self.restore=api(gdi,'RestoreDC',W.BOOL,W.HDC,C.c_int)
        self.select=api(gdi,'SelectObject',W.HANDLE,W.HDC,W.HANDLE)
        self.delete=api(gdi,'DeleteObject',W.BOOL,W.HANDLE)
        self.brush=api(gdi,'CreateSolidBrush',W.HBRUSH,W.DWORD)
        self.pen=api(gdi,'CreatePen',W.HANDLE,C.c_int,C.c_int,W.DWORD)
        self.createfont=api(gdi,'CreateFontW',W.HANDLE,*([C.c_int]*5),*([W.DWORD]*8),W.LPCWSTR)
        self.color=api(gdi,'SetTextColor',W.DWORD,W.HDC,W.DWORD)
        self.bkmode=api(gdi,'SetBkMode',C.c_int,W.HDC,C.c_int)
        self.roundrect=api(gdi,'RoundRect',W.BOOL,W.HDC,*([C.c_int]*6))
        self.ellipse=api(gdi,'Ellipse',W.BOOL,W.HDC,*([C.c_int]*4))
        self.move=api(gdi,'MoveToEx',W.BOOL,W.HDC,C.c_int,C.c_int,W.LPVOID)
        self.line=api(gdi,'LineTo',W.BOOL,W.HDC,C.c_int,C.c_int)
        self.polygon=api(gdi,'Polygon',W.BOOL,W.HDC,C.POINTER(W.POINT),C.c_int)
        self.stock=api(gdi,'GetStockObject',W.HANDLE,C.c_int)
        self.SUBPROC=C.WINFUNCTYPE(C.c_ssize_t,W.HWND,W.UINT,C.c_size_t,C.c_ssize_t,C.c_size_t,C.c_size_t)
        self.subclass=api(common,'SetWindowSubclass',W.BOOL,W.HWND,self.SUBPROC,C.c_size_t,C.c_size_t)
        self.remove=api(common,'RemoveWindowSubclass',W.BOOL,W.HWND,self.SUBPROC,C.c_size_t)
        self.default=api(common,'DefSubclassProc',C.c_ssize_t,W.HWND,W.UINT,C.c_size_t,C.c_ssize_t)
        self.callback=self.SUBPROC(self.control_message)  # Keep the callback alive.

    def scale(self, value): return round(value*self.dpi/96)

    @staticmethod
    def rgb(value):
        r,g,b=(int(value[i:i+2],16) for i in (1,3,5))
        return r|(g<<8)|(b<<16)

    def resource(self, kind, color):
        cache=self.brushes if kind=='brush' else self.pens
        key=color if kind=='brush' else (color,self.dpi)
        if key not in cache:
            cache[key]=self.brush(self.rgb(color)) if kind=='brush' else self.pen(0,max(1,self.scale(1)),self.rgb(color))
        return cache[key]

    def font(self, size=14, bold=False, mono=False, dpi=None, language=None):
        dpi=self.dpi if dpi is None else dpi
        language=self.language if language is None else language
        face='Consolas' if mono else 'Segoe UI' if language=='en' else 'Microsoft JhengHei UI' if language=='zh-Hant' else 'Microsoft YaHei UI'
        key=(size,bold,face,dpi)
        if key not in self.fonts:
            self.fonts[key]=self.createfont(-round(size*dpi/96),0,0,0,600 if bold else 400,0,0,0,1,0,0,5,0,face)
        return self.fonts[key]

    def attach(self, handle, key, kind='button', primary=False, size=(100,32), dpi=None, language=None):
        self.controls[handle]=dict(key=key,kind=kind,primary=primary,size=size,dpi=dpi or self.dpi,language=language)
        if not self.subclass(handle,self.callback,1,0):
            self.controls.pop(handle,None)  # Retain a working native control if skinning fails.

    def refresh(self, language=None, dpi=None):
        if language is not None:self.language=language
        if dpi is not None:self.dpi=dpi
        for handle in self.controls:self.invalidate(handle,None,False)

    def rect(self, geometry):
        x,y,w,h=geometry
        return W.RECT(self.scale(x),self.scale(y),self.scale(x+w),self.scale(y+h))

    def shape(self, hdc, geometry, radius, fill, border=None):
        x,y,w,h=geometry
        self.select(hdc,self.resource('brush',fill))
        self.select(hdc,self.resource('pen',border) if border else self.stock(8))  # NULL_PEN
        self.roundrect(hdc,self.scale(x),self.scale(y),self.scale(x+w),self.scale(y+h),self.scale(2*radius),self.scale(2*radius))

    def polyline(self, hdc, points, color):
        self.select(hdc,self.resource('pen',color))
        self.move(hdc,self.scale(points[0][0]),self.scale(points[0][1]),None)
        for x,y in points[1:]:self.line(hdc,self.scale(x),self.scale(y))

    def tiled_icon(self, hdc, kind, x, y):
        # Exact SVG tile vertices and back-to-front order, shared with AppKit.
        for tile in LOOK['iconTiles'][kind]:
            points=(W.POINT*len(tile['points']))(*[W.POINT(self.scale(x-4+px/2),self.scale(y-4+py/2)) for px,py in tile['points']])
            self.select(hdc,self.resource('brush',COLORS['background']))
            self.select(hdc,self.resource('pen',COLORS['background']))
            self.polygon(hdc,points,len(points))
            alpha=tile['opacity']
            color='#'+''.join(f'{round(255*(1-alpha)+int(COLORS["disabled_text"][i:i+2],16)*alpha):02x}' for i in (1,3,5))
            self.select(hdc,self.stock(5))  # Transparent tile interior after masking lower outlines.
            self.select(hdc,self.resource('pen',color))
            self.polygon(hdc,points,len(points))

    def text(self, hdc, value, geometry, size, color, bold=False, center=False, wrap=False):
        rect=self.rect(geometry)
        self.select(hdc,self.font(size,bold))
        self.color(hdc,self.rgb(color));self.bkmode(hdc,1)
        flags=0x800 | (0x10 if wrap else 0x20|0x4)  # NOPREFIX, WORDBREAK or SINGLELINE/VCENTER
        if center:flags|=1
        self.drawtext(hdc,value,len(value),C.byref(rect),flags)

    def paint_parent(self, window, width=WIDTH, offset=0, main=True):
        paint=Paint();hdc=self.begin(window,C.byref(paint))
        if not hdc:return
        saved=self.save(hdc)
        try:
            self.fill(hdc,C.byref(paint.rect),self.resource('brush',COLORS['background']))
            for kind,geometry,fill,border in decorations(width,offset,self.language) if main else []:
                if kind=='dot':fill=COLORS['blue' if self.busy else 'green' if self.verified else 'orange']
                if kind=='round':self.shape(hdc,geometry[:4],geometry[4],fill,border)
                elif kind=='line':
                    x,y,w=geometry;self.polyline(hdc,[(x,y),(x+w,y)],fill)
                elif kind=='dot':
                    x,y,w,h=geometry;self.select(hdc,self.resource('brush',fill));self.select(hdc,self.stock(8));self.ellipse(hdc,self.scale(x),self.scale(y),self.scale(x+w),self.scale(y+h))
                else:
                    x,y,w,h,name=geometry
                    if name in LOOK.get('iconTiles',{}):
                        self.tiled_icon(hdc,name,x,y)
                        continue
                    for points in icon_lines(name):self.polyline(hdc,[(x+px,y+py) for px,py in points],fill)
                    if name=='sun':
                        self.select(hdc,self.stock(5))  # NULL_BRUSH
                        self.ellipse(hdc,self.scale(x+5),self.scale(y+5),self.scale(x+13),self.scale(y+13))
        finally:self.restore(hdc,saved);self.end(window,C.byref(paint))

    def paint_control(self, window, hdc):
        spec=self.controls[window]
        previous_dpi,previous_language=self.dpi,self.language
        self.dpi=spec['dpi']
        if spec['language'] is not None:self.language=spec['language']
        bounds=W.RECT();self.client(window,C.byref(bounds))
        w=(bounds.right-bounds.left)*96/self.dpi or spec['size'][0]
        h=(bounds.bottom-bounds.top)*96/self.dpi or spec['size'][1]
        saved=self.save(hdc)
        try:
            self.fill(hdc,C.byref(self.rect((0,0,w,h))),self.resource('brush',COLORS['background']))
            if spec['kind']=='progress':
                self.shape(hdc,(0,0,w,h),h/2,COLORS['surface'])
                value=max(0,min(100,self.send(window,0x0408,0,0)))  # PBM_GETPOS
                if value:self.shape(hdc,(0,0,max(h,w*value/100),h),h/2,COLORS['blue'])
                return
            enabled=bool(self.enabled(window))
            state=self.send(window,0x00F2,0,0)  # BM_GETSTATE
            text=C.create_unicode_buffer(2048);self.gettext(window,text,len(text))
            if spec['kind']=='checkbox':
                checked=self.send(window,0x00F0,0,0)==1
                fill=COLORS['disabled_checkbox'] if not enabled else COLORS['blue'] if checked else COLORS['surface']
                self.shape(hdc,(0,(h-18)/2,18,18),4,fill,COLORS['border'] if enabled and not checked else None)
                if checked:self.polyline(hdc,[(4,h/2),(7,h/2+3),(13,h/2-4)],'#ffffff' if enabled else COLORS['disabled_text'])
                if not spec['key'].endswith('choice'):
                    self.text(hdc,text.value,(23,0,w-23,h),14,COLORS['text'] if enabled else COLORS['disabled_text'])
            elif spec['kind']=='dropdown':
                self.shape(hdc,(1,1,w-2,h-2),8,'#ffffff',COLORS['border'])
                self.text(hdc,text.value,(10,0,w-40,h),14,COLORS['text'] if enabled else COLORS['disabled_text'])
                self.polyline(hdc,[(w-23,h/2-2),(w-18,h/2+3),(w-13,h/2-2)],COLORS['secondary'])
            else:
                fill,color=button_colors(spec['primary'],enabled,window in self.hovered,bool(state&4))
                self.shape(hdc,(.5,.5,w-1,h-1),7,fill,fill if spec['primary'] else '#d8d8dc' if enabled else '#ededee')
                self.text(hdc,text.value,(8,0,w-16,h),13,color,False,center=True)
            if enabled and self.focus()==window:
                self.select(hdc,self.stock(5));self.select(hdc,self.resource('pen',COLORS['focus']))
                self.roundrect(hdc,self.scale(1),self.scale(1),self.scale(w-1),self.scale(h-1),self.scale(10),self.scale(10))
        finally:
            self.restore(hdc,saved)
            self.dpi,self.language=previous_dpi,previous_language

    def control_message(self, window, message, wp, lp, identity, data):
        try:
            if message==0x0082:  # NCDESTROY
                self.remove(window,self.callback,identity);self.controls.pop(window,None);self.hovered.discard(window)
            if window in self.controls:
                if message==0x000F:
                    paint=Paint();hdc=self.begin(window,C.byref(paint))
                    if hdc:
                        try:self.paint_control(window,hdc)
                        finally:self.end(window,C.byref(paint))
                    return 0
                if message==0x0318: self.paint_control(window,wp);return 0  # PRINTCLIENT
                if message==0x0014:return 1
                if message==0x0200:
                    self.hovered.add(window)
                    track=TrackMouse(C.sizeof(TrackMouse),2,window,0);self.track(C.byref(track))
                    self.invalidate(window,None,False)
                if message==0x02A3:self.hovered.discard(window);self.invalidate(window,None,False)
                if message in (0x0007,0x0008,0x000A,0x000C,0x0030,0x00F1,0x00F3,0x0201,0x0202,0x0100,0x0101,0x0402):
                    result=self.default(window,message,wp,lp)
                    self.invalidate(window,None,False);return result
        except Exception:
            # Native controls remain usable when drawing fails.
            pass
        return self.default(window,message,wp,lp)

    def close(self):
        # Called only after all windows are destroyed and no callbacks can paint.
        for cache in (self.fonts,self.brushes,self.pens):
            for handle in cache.values():self.delete(handle)
            cache.clear()
