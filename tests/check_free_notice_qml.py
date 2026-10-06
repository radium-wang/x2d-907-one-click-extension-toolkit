"""Qt 6.4.1 real XHR, first-use notice and persisted C marker checks; no camera."""
import argparse
import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(D / 'tests'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--payload', type=Path, required=True)
parser.add_argument('--output', type=Path, default=D / 'src/outputs/free-notice-check')
args = parser.parse_args()
from PySide6.QtCore import QObject, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from host_menu_fixtures import register
from test_free_notice import FreeNoticeTests

FreeNoticeTests.setUpClass()
probe = FreeNoticeTests()
fixture = dict(path=None, failures=0, acks=0, reads=0, writes=[], delay=0)


class Transport(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, value, status=200):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path == '/notice_status':
            fixture['reads'] += 1
            time.sleep(fixture['delay'])
            self.reply(dict(freeNoticeReady=True, freeNoticeSeen=bool(probe.probe(fixture['path'], 'read'))))
        elif self.path == '/status':
            state = dict(ready=True, active=False, master=True, afc=True, featureMask=7, eyeReady=True, eyeKnown=True, eyeActive=False, eyeEnabled=False, eyeIssue='none', message='fixture')
            state.update(fixture.get('eyeState', {}))
            self.reply(state)
        else:
            self.reply({}, 404)
    def do_POST(self):
        if self.path != '/notice_seen':
            fixture['writes'].append(self.path)
            self.reply({}, 400)
            return
        fixture['acks'] += 1
        if fixture['failures']:
            fixture['failures'] -= 1
            self.reply({}, 500)
            return
        ok = probe.probe(fixture['path'], 'ack') == 0
        self.reply(dict(freeNoticeReady=True, freeNoticeSeen=bool(probe.probe(fixture['path'], 'read')), acknowledged=ok))


server = ThreadingHTTPServer(('127.0.0.1', 18763), Transport)
threading.Thread(target=server.serve_forever, daemon=True).start()
app = QGuiApplication([])
reports = []


def wait(predicate):
    end = time.monotonic() + 6
    while time.monotonic() < end:
        app.processEvents()
        if predicate(): return
        time.sleep(.005)
    raise AssertionError('Notice QML state timed out')


def create(out):
    engine = QQmlEngine()
    register(engine)
    warnings = []
    engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
    qml = '''import QtQuick
Item {
 width:1024;height:768
 X2dSpeedBuffController {id:features;objectName:"Features"}
 X2dPlayPage {id:page;anchors.fill:parent;pageActive:false;featureController:features}
}'''
    component = QQmlComponent(engine)
    component.setData(qml.encode(), QUrl.fromLocalFile(str(out / 'NoticeCheck.qml')))
    root = component.create()
    assert root is not None, [str(item) for item in component.errors()]
    win = QQuickWindow()
    win.resize(1024, 768)
    root.setParentItem(win.contentItem())
    win.show()
    return engine, component, root, win, warnings


def dispose(view):
    engine, component, root, win, warnings = view
    assert not warnings, warnings
    win.close()
    root.deleteLater()
    win.deleteLater()
    component.deleteLater()
    engine.deleteLater()
    app.processEvents()


try:
    for language, suffix in [('zh', ''), ('en', '.en'), ('zh-Hant', '.zh-Hant')]:
        out = args.output / language
        out.mkdir(parents=True, exist_ok=True)
        for name in ('PlayPage', 'SpeedBuffController', 'AutoBrightnessController'):
            source = args.payload / ('X2d' + name + (suffix if name != 'AutoBrightnessController' else '') + '.qml')
            if not source.exists(): source = args.payload / ('X2d' + name + '.qml')
            shutil.copy2(source, out / ('X2d' + name + '.qml'))
        fixture.update(path=FreeNoticeTests.root / ('seen-' + language), failures=1, acks=0, reads=0, writes=[], delay=.12, eyeState={})
        view = create(out)
        root, win = view[2:4]
        page = root.findChild(QObject, 'PlayPageRoot')
        features = root.findChild(QObject, 'Features')
        notice = root.findChild(QObject, 'X2dFreeProjectNotice')
        page.setProperty('pageActive', True)
        assert not notice.isVisible() and not page.property('settingsActive')
        wait(lambda: features.property('ready') and notice.isVisible())
        assert not fixture['path'].exists() and not fixture['writes']
        page.setProperty('pageActive', False)
        page.setProperty('pageActive', True)
        assert notice.isVisible(), 'An unacknowledged notice must return'
        button = root.findChild(QObject, 'X2dFreeProjectNoticeButton')
        point = button.mapToItem(win.contentItem(), QPointF(button.width()/2, button.height()/2))
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
        wait(lambda: fixture['acks'] == 1 and features.property('noticeRequest') is None)
        assert not notice.isVisible() and page.property('settingsActive')
        assert not features.property('freeNoticeSeen') and not fixture['path'].exists()
        page.setProperty('pageActive', False)
        page.setProperty('pageActive', True)
        assert not notice.isVisible(), 'A failed write must not repeat during the session'
        features.pollFreeNotice()
        wait(lambda: features.property('freeNoticeSeen'))
        assert fixture['path'].read_bytes() == b'1\n'
        assert features.property('ready') and features.property('master') and features.property('afcEnabled')
        assert not features.property('loaded') and not features.property('faulted') and not fixture['writes']
        dispose(view)
        # A new QML engine/controller represents GUI/camera restart or an updated payload.
        fixture['delay'] = 0
        view = create(out)
        root = view[2]
        page = root.findChild(QObject, 'PlayPageRoot')
        features = root.findChild(QObject, 'Features')
        notice = root.findChild(QObject, 'X2dFreeProjectNotice')
        page.setProperty('pageActive', True)
        assert not notice.isVisible()
        wait(lambda: page.property('settingsActive') and features.property('ready'))
        for _ in range(100):
            page.setProperty('pageActive', False)
            page.setProperty('pageActive', True)
            assert not notice.isVisible()
        assert fixture['acks'] == 2 and not fixture['writes']
        fixture['eyeState'] = dict(featureMask=8, eyeKnown=True, eyeReady=True, eyeActive=True)
        features.request('status')
        wait(lambda: features.property('eyeInstalled') and features.property('eyeActive'))
        fixture['eyeState'] = dict(featureMask=8, eyeKnown=False, eyeReady=False, eyeActive=False, eyeIssue='unavailable')
        features.request('status')
        wait(lambda: features.property('eyeIssue') == 'unavailable')
        assert features.property('eyeActive'), 'Unknown state must not claim an enabled Eye option was disabled'
        fixture['eyeState'] = dict(featureMask=8, eyeKnown=True, eyeReady=True, eyeActive=False)
        features.request('status')
        wait(lambda: features.property('eyeReady') and not features.property('eyeActive'))
        reports.append(dict(language=language, firstOnly=True, failedAckRetried=True,
                            freshEngineReadPersisted=True, reentries=100, featureStatePreserved=True,
                            eyeUnknownNeverClaimsDisabled=True, eyeActualReadbackPassed=True))
        dispose(view)
finally:
    server.shutdown()
    server.server_close()
    FreeNoticeTests.tearDownClass()
(args.output / 'validation.json').write_text(json.dumps(dict(passed=True, cameraAccessed=False, languages=reports), indent=2)+'\n')
print(json.dumps(reports))
