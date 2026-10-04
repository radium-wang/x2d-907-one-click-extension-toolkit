"""Render the Windows skin's shared layout/vectors without Windows or USB.

This is a layout preview, not evidence of native Windows execution. Requires
optional PySide6, which is never included in the desktop distribution.
"""
import argparse,ast,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from windows_ui import WIDTH,HEIGHT,COLORS,decorations,icon_lines,main_layout,button_colors,text_style
from localization import translate


def labels():
    tree=ast.parse((Path(__file__).resolve().parents[1]/'src/windows_app.py').read_text())
    return {call.args[0].value:(call.args[1].value,call.args[2].value) for call in ast.walk(tree)
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='item'}


def render(path,language='zh',scale=2,height=HEIGHT,offset=0,connected=False,settings=False):
    from PySide6.QtCore import Qt,QRectF,QPointF
    from PySide6.QtGui import QImage,QPainter,QColor,QFont,QPen,QFontMetricsF
    width=450 if settings else WIDTH
    if settings:height=246
    layout=main_layout()
    content=labels()
    if settings:
        tree=ast.parse((Path(__file__).resolve().parents[1]/'src/windows_app.py').read_text())
        calls=[call for call in ast.walk(tree) if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='control' and len(call.args)>=7 and all(isinstance(arg,ast.Constant) for arg in call.args[:7])]
        content={call.args[0].value:(call.args[1].value,call.args[2].value) for call in calls}
        layout={call.args[0].value:tuple(arg.value for arg in call.args[3:7]) for call in calls}
        layout['language']=(*layout['language'][:3],28)
    image=QImage(round(width*scale),round((height+36)*scale),QImage.Format_ARGB32)
    image.fill(QColor('white'))
    painter=QPainter(image);painter.scale(scale,scale)
    painter.setRenderHint(QPainter.Antialiasing)
    issues=[]
    def shape(rect,radius,fill,border=None):
        painter.setBrush(QColor(fill));painter.setPen(QPen(QColor(border),1) if border else Qt.NoPen)
        painter.drawRoundedRect(QRectF(*rect),radius,radius)
    def font(size,bold=False,mono=False):
        value=QFont('Consolas' if mono else 'Segoe UI' if language=='en' else 'Microsoft YaHei UI')
        value.setPixelSize(size);value.setWeight(QFont.DemiBold if bold else QFont.Normal)
        return value
    def text(value,rect,size,color,bold=False,center=False,wrap=False,check=True):
        painter.setFont(font(size,bold));painter.setPen(QColor(color))
        flags=Qt.AlignCenter if center else Qt.AlignLeft|Qt.AlignVCenter
        if wrap:flags=Qt.AlignLeft|Qt.AlignTop|Qt.TextWordWrap
        bounds=QRectF(*rect)
        measured=QFontMetricsF(painter.font()).boundingRect(bounds,flags,value)
        if check and (measured.width()>rect[2]+1 or measured.height()>rect[3]+1):
            issues.append(dict(text=value,available=rect,measured=[measured.width(),measured.height()]))
        painter.drawText(bounds,flags,value)
    # Neutral Windows title bar; the operating system supplies the real frame.
    shape((0,0,width,36),0,'#fafafa')
    title=translate('设置',language) if settings else translate('x2d/907一键扩展功能-工具包',language)
    text(title,(16,0,width-154,36),12,COLORS['text'],check=False)
    for index,glyph in enumerate(('−','□','×')):text(glyph,(width-138+46*index,0,46,36),15,COLORS['secondary'],center=True)
    painter.translate(0,36)
    painter.setClipRect(QRectF(0,0,width,height))
    for kind,geometry,fill,border in [] if settings else decorations(WIDTH,offset):
        if kind=='round':shape(geometry[:4],geometry[4],fill,border)
        else:
            x,y,w,h,name=geometry
            painter.setPen(QPen(QColor(fill),1));painter.setBrush(Qt.NoBrush)
            for points in icon_lines(name):
                for a,b in zip(points,points[1:]):painter.drawLine(QPointF(x+a[0],y+a[1]),QPointF(x+b[0],y+b[1]))
            if name=='sun':painter.drawEllipse(QRectF(x+5,y+5,8,8))
    for key,(kind,source) in content.items():
        x,y,w,h=layout[key];y-=offset
        value=translate(source,language)
        if key=='logs':continue
        if key=='progress':
            shape((x,y,w,h),h/2,'#ededee',COLORS['border'])
            if connected:shape((x,y,w*.4,h),h/2,COLORS['blue'])
        elif kind=='COMBOBOX':
            shape((x,y,w,h),4,'white',COLORS['border'])
            text('English' if language=='en' else '中文',(x+10,y,w-35,h),14,COLORS['text'])
            text('⌄',(x+w-28,y,20,h),16,COLORS['secondary'],center=True)
        elif kind=='BUTTON':
            enabled=key not in ('installbutton','restorebutton','prank','downloadbutton') or connected
            if key in ('prank','automaticupdates'):
                shape((x,y+(h-16)/2,16,16),4,COLORS['blue'] if key=='automaticupdates' else COLORS['surface'])
                if key=='automaticupdates':
                    painter.setPen(QPen(QColor('white'),1.5))
                    painter.drawLine(QPointF(x+4,y+h/2),QPointF(x+7,y+h/2+3))
                    painter.drawLine(QPointF(x+7,y+h/2+3),QPointF(x+12,y+h/2-4))
                text(value,(x+23,y,w-23,h),14,COLORS['text'] if enabled else COLORS['disabled_text'])
            else:
                fill,color=button_colors(key=='statusbutton',enabled)
                shape((x+1,y+1,w-2,h-2),min(15,h/2-1),fill)
                text(value,(x+6,y,w-12,h),14,color,key=='statusbutton',center=True)
        else:
            size,bold,color=text_style(key,language)
            text(value,(x,y,w,h),size,color,bold,wrap=key in ('detail','note','warning','updatesdescription'))
    painter.end();image.save(str(path))
    return dict(page='settings' if settings else 'main',language=language,scale=scale,height=height,offset=offset,issues=issues)


if __name__=='__main__':
    from PySide6.QtGui import QGuiApplication
    app=QGuiApplication([])
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    reports=[]
    for language in ('zh','en'):
        reports.append(render(args.output/('windows-'+language+'.png'),language))
        reports.append(render(args.output/('windows-'+language+'-small.png'),language,1.25,560,HEIGHT-560))
        reports.append(render(args.output/('windows-settings-'+language+'.png'),language,settings=True))
    (args.output/'layout-report.json').write_text(json.dumps(dict(nativeWindows=False,sharedNativeLayout=True,layouts=reports),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(reports,ensure_ascii=False))
    assert not any(report['issues'] for report in reports),'Text exceeds its shared native rectangle'
