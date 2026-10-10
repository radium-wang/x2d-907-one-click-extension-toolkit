"""Compare real stock menu widgets with the original stable baseline, no USB."""
import json
import math
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
import time
from PySide6.QtCore import QObject,QPoint,QPointF,Qt,QUrl,QMetaObject,QCoreApplication,QEvent
from PySide6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression
from PySide6.QtTest import QTest
from PySide6.QtGui import QKeyEvent,QMouseEvent

def check(engine,app,win,payload,baseline,output):
    state=dict(ready=True,master=False,active=False,afc=False,featureMask=7,
               speedLevel='medium',eyeReady=True,eyeActive=False,eyeSaved=False,eyeSuppressed=False,
               aftReady=True,aftActive=False,aftSaved=False,focusMode=1,message='local hardware proxy')
    requests=[];click_results=[];fail_speed=[False]
    status_requests=[];hold_reply=[False];reply_arrived=threading.Event();release_reply=threading.Event()
    def runtime():
        value=dict(state)
        value['eyeActive']=value['master'] and value['eyeSaved'] and value['focusMode']!=6
        value['eyeSuppressed']=value['master'] and value['eyeSaved'] and value['focusMode']==6
        return value
    class HTTP(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            value=runtime()
            if self.server.server_port==18763:
                status_requests.append(time.monotonic())
                if hold_reply[0]:reply_arrived.set();release_reply.wait(3)
            self.reply(value)
        def do_POST(self):
            requests.append(self.path)
            if self.path=='/master_on':state['master']=True
            elif self.path=='/master_off':state.update(master=False,aftActive=False,aftSaved=False,
                                                      eyeActive=False,eyeSaved=False,eyeSuppressed=False)
            elif self.path=='/aft_on':state.update(aftActive=True,aftSaved=True)
            elif self.path=='/aft_off':state.update(aftActive=False,aftSaved=False)
            elif self.path=='/eye_on':state.update(eyeSaved=True)
            elif self.path=='/eye_off':state.update(eyeSaved=False,eyeActive=False,eyeSuppressed=False)
            elif self.path=='/afc_on':state['afc']=True
            elif self.path=='/afc_off':state['afc']=False
            if self.path in ('/speed_low','/speed_medium','/speed_high'):
                if fail_speed[0]: self.reply(dict(runtime(),ready=False));return
                state['speedLevel']=self.path[7:]
            elif self.path=='/enable':state['active']=True
            elif self.path=='/disable':state['active']=False
            self.reply(runtime())
        def reply(self,current):
            value=dict(ok=True,ready=True,master=state['master'],available=False,enabled=False,
                       effective=False,applied=1,state='local hardware proxy') if self.server.server_port==18765 else current
            data=json.dumps(value).encode();self.send_response(200)
            self.send_header('Content-Length',str(len(data)));self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
    servers=[]
    roots=[]
    def wait(condition,timeout=5):
        limit=time.monotonic()+timeout
        while time.monotonic()<limit:
            app.processEvents()
            if condition():return
            time.sleep(.01)
        raise AssertionError('real menu test timed out')
    def mouse_click(window,point):
        # Deliver directly to the test window's real Qt scene; OS focus may
        # change while the owner is using the desktop during a long run.
        local=QPointF(point)
        for event_type,buttons in ((QEvent.MouseButtonPress,Qt.LeftButton),(QEvent.MouseButtonRelease,Qt.NoButton)):
            event=QMouseEvent(event_type,local,local,Qt.LeftButton,buttons,Qt.NoModifier)
            QCoreApplication.sendEvent(window,event)
    def key_click(window,key):
        QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier))
        QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyRelease,key,Qt.NoModifier))
    def drain():
        for _ in range(25):app.processEvents();time.sleep(.01)
    def create(folder):
        source='''import QtQuick
Item {
 width:1024;height:768
 X2dSpeedBuffController {id:features;objectName:"LocalMenuController"}
 X2dPlayPage {anchors.fill:parent;pageActive:true;featureController:features}
}'''
        c=QQmlComponent(engine);c.setData(source.encode(),QUrl.fromLocalFile(str(folder/'LocalMenuCheck.qml')))
        item=c.create();assert item is not None,[e.toString() for e in c.errors()]
        roots.append((c,item));item.setParentItem(win.contentItem())
        controller=item.findChild(QObject,'LocalMenuController')
        wait(lambda:controller.property('ready') and not controller.property('inFlight'))
        win.update();win.grabWindow();drain();return item,controller
    def row(item,name):return item.findChild(QObject,name)
    def selector(item):return item.findChild(QObject,'MenuBoolSelector_root')
    def snapshot(item):
        widget=selector(item);assert widget is not None
        texts=[];icons=[]
        for node in widget.findChildren(QObject):
            if node.metaObject().indexOfProperty('font')>=0:
                font=node.property('font')
                texts.append(dict(text=node.property('text'),size=font.pixelSize(),family=font.family(),
                                  weight=font.weight(),color=node.property('color').name(),
                                  opacity=node.property('opacity')))
            if node.objectName()=='uiimage_root':
                icons.append(dict(source=node.property('source').toString(),height=node.height(),width=node.width()))
        return dict(height=item.height(),width=item.width(),selectorX=widget.x(),selectorWidth=widget.width(),
                    texts=texts,icons=icons)
    def click(item):
        before=len(requests);name=item.objectName()
        point=item.mapToItem(win.contentItem(),QPointF(item.width()*.8,item.height()*.5))
        mouse_click(win,QPoint(round(point.x()),round(point.y())))
        drain()
        click_results.append((name,requests[before:]))
    try:
        for port in (18763,18765):
            server=ThreadingHTTPServer(('127.0.0.1',port),HTTP);servers.append(server)
            threading.Thread(target=server.serve_forever,daemon=True).start()
        reference,old_controller=create(baseline)
        names=['X2dPlayMasterSwitchRow','X2dPlayAfcSwitchRow','X2dPlaySpeedSwitchRow','X2dPlayAutoBrightnessSwitchRow']
        old={name:snapshot(row(reference,name)) for name in names}
        reference.setVisible(False)
        current,controller=create(payload)
        current_rows={name:row(current,name) for name in names}
        for name in names:
            actual=snapshot(current_rows[name])
            if name=='X2dPlaySpeedSwitchRow':
                # Only the explanatory text changes; native row geometry/fonts remain stock.
                assert actual['height']==old[name]['height'] and actual['width']==old[name]['width']
            else:assert actual==old[name],(name,old[name],actual)
        master=current_rows['X2dPlayMasterSwitchRow']
        speed_level=row(current,'X2dPlaySpeedLevelRow')
        speed_row=current_rows['X2dPlaySpeedSwitchRow']
        assert abs(speed_level.y()-speed_row.y()-speed_row.height())<.001
        for mask in range(1,8):
            state['featureMask']=mask
            expr=QQmlExpression(QQmlEngine.contextForObject(controller),controller,'request("status")');expr.evaluate()
            wait(lambda:controller.property('featureMask')==mask and not controller.property('inFlight'))
            for name,bit in [('X2dPlayAfcSwitchRow',1),('X2dPlaySpeedSwitchRow',2),('X2dPlaySpeedLevelRow',2),('X2dPlayAutoBrightnessSwitchRow',4)]:
                item=row(current,name);assert item.isVisible()==bool(mask&bit) and (item.height()>0)==bool(mask&bit),(mask,name)
        def qml_value(item,expression):
            expression=QQmlExpression(QQmlEngine.contextForObject(item),item,expression)
            result,undefined=expression.evaluate()
            assert not undefined and not expression.hasError(),expression.error().toString()
            return result
        def picker(chooser):
            native=row(chooser,'PopupListSelector_list');assert native is not None
            assert qml_value(native,'orientation === ListView.Vertical') and native.property('interactive')
            assert qml_value(native,'highlightItem.color.toString()')=='#de4200'
            return native
        def move_to(native,index):
            chooser=row(current,'X2dSpeedLevelPage');chooser.forceActiveFocus()
            for _ in range(abs(index-native.property('currentIndex'))):
                key_click(win,Qt.Key_Down if index>native.property('currentIndex') else Qt.Key_Up)
            drain();assert native.property('currentIndex')==index
        def accept_current(native):
            point=native.mapToItem(win.contentItem(),QPointF(native.width()/2,native.height()/2))
            mouse_click(win,QPoint(round(point.x()),round(point.y())));drain()
        speed_checks=None
        if manifest_speed := json.loads((payload/'speed-bundle.json').read_text()).get('speedLevels'):
            click(master);wait(lambda:controller.property('master') and not controller.property('inFlight'))
            assert controller.property('speedLevel')=='medium'
            listing=row(current,'X2dPlaySettingsList')
            listing.setProperty('contentY',max(0,speed_level.y()-200));drain()
            before=len(requests);click(speed_level)
            assert row(current,'X2dSpeedLevelPage') is None and len(requests)==before
            values=[n for n in speed_level.findChildren(QObject) if n.metaObject().indexOfProperty('valueText')>=0]
            assert values and values[0].property('enabled') is False
            opacity=QQmlExpression(QQmlEngine.contextForObject(values[0]),values[0],'rightText.opacity')
            number,undefined=opacity.evaluate();assert not opacity.hasError() and not undefined and number==0.6
            win.grabWindow().save(str(output/'speed-off-gray.png'))
            click(current_rows['X2dPlaySpeedSwitchRow']);wait(lambda:controller.property('loaded') and not controller.property('inFlight'))
            for level in ('low','medium','high'):
                # Bring the new row into view; the real stock Flickable clips it.
                listing=row(current,'X2dPlaySettingsList')
                listing.setProperty('contentY',max(0,speed_level.y()-200));drain()
                click(speed_level);drain()
                chooser=row(current,'X2dSpeedLevelPage');assert chooser is not None
                native=picker(chooser);move_to(native,('low','medium','high').index(level))
                print('SPEED_BEFORE',level,dict(index=native.property('currentIndex'),y=native.property('contentY'),ready=controller.property('ready'),busy=controller.property('busy'),inFlight=controller.property('inFlight'),state=dict(state)),flush=True)
                accept_current(native)
                print('SPEED_AFTER',level,dict(index=native.property('currentIndex') if row(current,'X2dSpeedLevelPage') is not None else None,actual=controller.property('speedLevel'),ready=controller.property('ready'),busy=controller.property('busy'),inFlight=controller.property('inFlight'),requests=requests[-5:]),flush=True)
                wait(lambda:controller.property('speedLevel')==level and not controller.property('inFlight'))
                assert row(current,'X2dSpeedLevelPage') is None
                assert controller.property('loaded')
            click(speed_level);drain();native=picker(row(current,'X2dSpeedLevelPage'));move_to(native,0)
            fail_speed[0]=True;accept_current(native);wait(lambda:not controller.property('inFlight'))
            assert controller.property('speedLevel')=='high' and row(current,'X2dSpeedLevelPage') is not None
            fail_speed[0]=False;wait(lambda:controller.property('ready'))
            native=picker(row(current,'X2dSpeedLevelPage'));accept_current(native)
            wait(lambda:controller.property('speedLevel')=='low' and not controller.property('inFlight'))
            assert controller.property('loaded')
            click(speed_level);drain();chooser=row(current,'X2dSpeedLevelPage');chooser.forceActiveFocus();win.requestActivate();drain()
            key_click(win,Qt.Key_Down);key_click(win,Qt.Key_Return);drain()
            wait(lambda:controller.property('speedLevel')=='medium' and not controller.property('inFlight'))
            click(speed_level);drain();row(current,'X2dSpeedLevelPage').forceActiveFocus();key_click(win,Qt.Key_Escape);drain()
            assert row(current,'X2dSpeedLevelPage') is None
            click(speed_level);drain();native=picker(row(current,'X2dSpeedLevelPage'))
            assert native.property('currentIndex')==1
            point=native.mapToItem(win.contentItem(),QPointF(native.width()/2,native.height()/2))
            x,y=round(point.x()),round(point.y());distance=round(native.height()/4.3*1.5)
            before=len(requests)
            QTest.mousePress(win,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
            for step in range(1,13):
                QTest.mouseMove(win,QPoint(x,y-round(distance*step/12)),20);app.processEvents()
            QTest.mouseRelease(win,Qt.LeftButton,Qt.NoModifier,QPoint(x,y-distance))
            wait(lambda:not native.property('moving'));drain()
            assert native.property('currentIndex')==2 and len(requests)==before,dict(index=native.property('currentIndex'),y=native.property('contentY'),requests=requests[before:],height=native.height(),distance=distance)
            # Touching the dimmed area confirms the centered value as in stock.
            mouse_click(win,QPoint(80,380));drain()
            wait(lambda:controller.property('speedLevel')=='high' and not controller.property('inFlight'))
            assert row(current,'X2dSpeedLevelPage') is None and controller.property('loaded')
            click(speed_level);drain();native=picker(row(current,'X2dSpeedLevelPage'));move_to(native,1);accept_current(native)
            wait(lambda:controller.property('speedLevel')=='medium' and not controller.property('inFlight'))
            # Hold a real status XHR while confirming a user choice. The
            # command must preempt that read and ignore its late response.
            hold_reply[0]=True;reply_arrived.clear();release_reply.clear()
            expression=QQmlExpression(QQmlEngine.contextForObject(controller),controller,'request("status")')
            expression.evaluate();assert not expression.hasError()
            wait(lambda:reply_arrived.is_set() and controller.property('inFlight'))
            click(speed_level);drain();native=picker(row(current,'X2dSpeedLevelPage'));move_to(native,0)
            accept_current(native)
            wait(lambda:controller.property('speedLevel')=='low' and not controller.property('inFlight'))
            hold_reply[0]=False;release_reply.set();drain()
            assert controller.property('speedLevel')=='low' and controller.property('loaded')
            click(speed_level);drain();native=picker(row(current,'X2dSpeedLevelPage'));move_to(native,1);accept_current(native)
            wait(lambda:controller.property('speedLevel')=='medium' and not controller.property('inFlight'))
            language_shots=[]
            for language,suffix in [('zh',''),('zh-Hant','.zh-Hant'),('en','.en')]:
                folder=output/('speed-language-'+language);folder.mkdir()
                for name in ('PlayPage','SpeedBuffController','AutoBrightnessController'):
                    source=payload/('X2d'+name+suffix+'.qml')
                    if not source.exists():source=payload/('X2d'+name+'.qml')
                    (folder/('X2d'+name+'.qml')).write_bytes(source.read_bytes())
                current.setVisible(False)
                translated,translated_controller=create(folder)
                listing=row(translated,'X2dPlaySettingsList');translated_row=row(translated,'X2dPlaySpeedLevelRow')
                listing.setProperty('contentY',max(0,translated_row.y()-200));drain()
                assert controller.property('speedLevel')=='medium'
                win.grabWindow().save(str(output/('speed-menu-'+language+'.png')))
                click(translated_row);drain()
                translated_page=row(translated,'X2dSpeedLevelPage');assert translated_page is not None
                drain()
                native=picker(translated_page)
                assert native.property('currentIndex')==1
                expected=['低','中','高'] if language!='en' else ['Low','Medium','High']
                assert json.loads(qml_value(translated_page,'JSON.stringify(model)'))==expected
                assert qml_value(native,'highlightRangeMode === ListView.StrictlyEnforceRange')
                win.grabWindow().save(str(output/('speed-options-'+language+'.png')))
                translated_page.forceActiveFocus();key_click(win,Qt.Key_Escape);drain()
                assert row(translated,'X2dSpeedLevelPage') is None
                language_shots.append(language);translated.setVisible(False)
            current.setVisible(True);drain()
            click(current_rows['X2dPlaySpeedSwitchRow']);wait(lambda:not controller.property('loaded') and not controller.property('inFlight'))
            assert controller.property('speedLevel')=='medium' and values[0].property('enabled') is False
            assert qml_value(values[0],'rightText.opacity')==0.6
            before=len(requests);click(speed_level)
            assert row(current,'X2dSpeedLevelPage') is None and len(requests)==before
            click(master);wait(lambda:not controller.property('master') and not controller.property('inFlight'))
            speed_checks=dict(default='medium',levels=['low','medium','high'],selectionReadback=True,
                failureKeepsPreviousSelection=True,keyboardAndBack=True,disabledWhileOff=True,
                activeSelectionRetainsEnabled=True,languages=language_shots,nativeVerticalPicker=True,swipeNavigation=True,stockOrangeHighlight=True,userCommandOverridesPolling=True,
                stockTypes=['TextValueRow','PopupListSelector','PopupBackground','HblListView','ScaledDelegate','ListGradient'])
        return dict(speedMenu=speed_checks,selectionMasksVerified=7,existingRowsMatchBaseline=True,speedImmediatelyBelowBoost=True,deviceAccessed=False)
    finally:
        hold_reply[0]=False;release_reply.set()
        for _,item in roots:item.setVisible(False);item.deleteLater()
        app.processEvents()
        for server in servers:server.shutdown();server.server_close()

from pathlib import Path

def main():
    import argparse
    from PySide6.QtCore import qVersion
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickWindow
    from stock_ui_runtime import register
    from stock_ui_evidence import sha,BANKS_SHA,REQUIRED_SHA
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('payload','baseline','stock-ui','fonts','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((a.payload/'speed-bundle.json').read_text())
    assert manifest['softwareBaseline']=='v0.4.12' and not manifest.get('aft') and not manifest.get('eyeMemory')
    for f in manifest['files']+[f for rows in manifest['uiLanguages'].values() for f in rows]:assert sha((a.payload/f['source']).read_bytes())==f['sha256']
    app=QGuiApplication([]);engine=QQmlEngine();tables,stock=register(engine,a.stock_ui,a.output,a.fonts)
    print('STOCK_REGISTERED',flush=True)
    from PySide6.QtCore import QFile,QIODevice,QDir
    warm=[]
    icons=[name[:-4] for name in QDir(':/icons').entryList(['*.svg']) if 'switch' in name or name=='ic_menu_back.svg']
    print('WARM_ICONS',icons,flush=True)
    for name in icons:
        component=QQmlComponent(engine)
        source='import QtQuick\nimport "qrc:/app/qml/components" as Stock\nStock.ScaledImage {source:"image://svg/'+name+'";sourceSize:Qt.size(160,160);asynchronous:false}'
        component.setData(source.encode(),QUrl('file:///LocalWarm.qml'))
        item=component.create();assert item is not None,[e.toString() for e in component.errors()]
        warm.append((component,item));app.processEvents()
    print('WARMED',flush=True)
    warnings=[];engine.warnings.connect(lambda values:warnings.extend(v.toString() for v in values))
    win=QQuickWindow();win.setGeometry(200,100,1024,768);win.show();win.requestActivate()
    menu=check(engine,app,win,a.payload,a.baseline,a.output)
    assert not warnings,warnings
    report=dict(schema=1,qt=qVersion(),graphicsApi='Metal',payloadManifestSha256=sha((a.payload/'speed-bundle.json').read_bytes()),stockGuiSha256=stock['guiSha256'],stockUiBanksSha256=BANKS_SHA,realVisualTypes=REQUIRED_SHA,visualMocks=False,menuStyle=menu,deviceAccessed=False,limits=['hardware, backend and native constants proxied','physical camera touchscreen/GPU/optical behavior unverified'])
    (a.output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));win.close()
if __name__=='__main__':main()
