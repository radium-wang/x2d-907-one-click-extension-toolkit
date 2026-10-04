"""Qt 6.4.1 offline PlayPage/control test with a Mac loopback-only display fixture."""
import json,os,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
D=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(D/'src'),str(D/'tests')]
from PySide6.QtCore import QUrl,QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine,QQmlComponent
from host_menu_fixtures import register
state=dict(ok=True,ready=True,available=False,enabled=False,effective=False,applied=50,master=True,state='manual')
actions=[]
class Display(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.reply()
    def do_POST(self):
        actions.append(self.path)
        if self.path.endswith('/feature-enable'):state.update(available=True,enabled=True)
        elif self.path.endswith('/feature-disable'):state.update(available=False,enabled=False)
        else:state['enabled']=self.path.endswith('/enable')
        self.reply()
    def reply(self):
        body=json.dumps(state).encode();self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',18765),Display)
threading.Thread(target=server.serve_forever,daemon=True).start()
app=QGuiApplication([]);engine=QQmlEngine();register(engine)
qml='''import QtQuick
Item {
 width: 1024; height: 768
 property bool toggleTrigger: false
 property bool lastResult: false
 onToggleTriggerChanged: lastResult=page.requestBrightnessToggle()
 property alias master: features.master
 QtObject { id: features; property bool master: false; property bool loaded: false; property bool busy: false;
  property bool ready: false; property bool faulted: true; property bool afcEnabled: false; property string statusMessage: "offline" }
 PlayPage {id: page; anchors.fill:parent; pageActive:true; featureController: features}
}'''
component=QQmlComponent(engine);component.setData(qml.encode(),QUrl.fromLocalFile(str(D/'src/OfflineBrightnessCheck.qml')))
root=component.create()
assert root is not None,[str(e) for e in component.errors()]
def wait(test):
    end=time.monotonic()+5
    while time.monotonic()<end:
        app.processEvents()
        if test():return
        time.sleep(.01)
    raise AssertionError('Brightness QML state timed out')
page=root.findChild(QObject,'PlayPageRoot');row=page.findChild(QObject,'X2dPlayAutoBrightnessSwitchRow')
assert row is not None
def toggle():
    root.setProperty('toggleTrigger',not root.property('toggleTrigger'));return root.property('lastResult')
selector=next(child for child in row.findChildren(QObject) if child.metaObject().indexOfProperty('itemEnabled')>=0)
wait(lambda:selector.property('value') is False)
assert not selector.property('itemEnabled')
assert toggle() is False and not actions
root.setProperty('master',True)
wait(lambda:selector.property('itemEnabled'))
# AF service can be unavailable while independent brightness remains usable.
assert page.property('backendAvailable') is False
assert toggle()
wait(lambda:selector.property('value') is True and not page.property('featureBusy'))
assert actions==['/display/feature-enable']
# Display disables Auto independently of the feature's menu availability.
state['enabled']=False
wait(lambda:not page.property('featureBusy'))
assert selector.property('value') is True
state['available']=False
wait(lambda:selector.property('value') is False)
assert actions==['/display/feature-enable']
root.setProperty('master',False)
wait(lambda:not selector.property('itemEnabled'))
assert toggle() is False
assert len(actions)==1
root.deleteLater();app.processEvents();server.shutdown();server.server_close()
print('PASS: real PlayPage row, master gating, independent backend, authoritative manual override, no writes on polling')
