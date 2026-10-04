"""Qt 6.4.1: real stock widgets + packaged rear delegate, loopback mocks only."""
import argparse,json,os,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QML_DISABLE_DISK_CACHE']='1'
from PySide6.QtCore import QUrl,QResource,QObject,QPoint,QPointF,Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow,QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlEngine,QQmlComponent,QJSEngine
import PySide6
D=Path(__file__).resolve().parents[1]
state=dict(ok=True,ready=True,master=True,available=True,enabled=True,effective=True,applied=30,state='auto')
actions=[]
class Backend(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):self.answer()
    def do_POST(self):
        actions.append(self.path)
        if self.path=='/display/enable':state.update(enabled=True,effective=True)
        elif self.path=='/display/disable':state.update(enabled=False,effective=False)
        else:raise AssertionError(self.path)
        self.answer()
    def answer(self):
        body=json.dumps(state).encode();self.send_response(200)
        self.send_header('Content-Length',str(len(body)));self.send_header('Content-Type','application/json')
        self.end_headers();self.wfile.write(body)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stock-qml',type=Path,required=True);parser.add_argument('--payload',type=Path,required=True)
    args=parser.parse_args();args.stock_qml=args.stock_qml.resolve();args.payload=args.payload.resolve();out=args.payload/'display-qml-test';out.mkdir(exist_ok=True)
    constants=dict(scaleFactorX=1,scaleFactorY=1,scaleFactor=1,menuListItemDefaultHeight=80,settingsMenuSettingLeftMargin=32,settingsMenuSettingRightMargin=32,settingsMenuSliderLeftMargin=32,settingsMenuSliderRightMargin=32,settingsMenuTextFontSize=28,menuItemLabelFontWeight=500,menuItemValueFontWeight=500,menuItemDisabledTextOpacity=.4,settingsMenuSettingSwitchFontSize=28,defaultCheckBoxSize=24,viewEndLineWidth=1,settingsMenuSliderKnobDiameter=22,settingsMenuSliderMiddleMarkerHeight=8,settingsMenuSliderThickness=2)
    modules={
        'constants':('Constants',''.join('property real %s: %s\n'%(k,v) for k,v in constants.items())+'property string menuItemFontName: "Arial"\nproperty string settingsMenuSettingSwitchFontName: "Arial"\n'+''.join('property color %s: "%s"\n'%(k,v) for k,v in dict(colorWhite='white',menuItemColor='white',highlightColor='#555555',cameraViewLineColor='gray',settingsMenuSliderKnobFillColor='white').items())),
        'keys':('KeyFn','enum Codes { ListUp=1, ListDown, Select, HighlightSelect, JstkSelect, Cross, Ael, JstkEscape, NavLeft=16777234, NavRight=16777236 }\nfunction isFn(key,modifiers,name){return key===name}'),
        'types':('GuiTypes','enum Codes { E_MenuOption_SliderContinuous=1 }'),
        'valueformatter':('ValueFormatter','function getMinValue(name){return 1}\nfunction getMaxValue(name){return 100}\nfunction getStepsForValue(name){return 1}'),
        'menumodel':('Dummy','property int value: 0')}
    for module,(name,body) in modules.items():
        folder=out/'com/hasselblad'/module;folder.mkdir(parents=True,exist_ok=True)
        (folder/'qmldir').write_text('module com.hasselblad.%s\nsingleton %s 1.0 %s.qml\n'%(module,name,name))
        (folder/(name+'.qml')).write_text('pragma Singleton\nimport QtQuick\nQtObject {\n'+body+'\n}')
    files=['mainmenu/SettingSlider.qml','mainmenu/MenuBoolSelector.qml','components/ToggleSwitch.qml','components/TextCheckbox.qml','components/ScaledImage.qml','components/Checkbox.qml','scripts/Keys.js']
    qrc=['<RCC><qresource prefix="/app/qml">']
    for name in files:qrc.append('<file alias="%s">%s</file>'%(name,args.stock_qml/name))
    (out/'UiImage.qml').write_text('import QtQuick\nImage { sourceSize: Qt.size(100,100) }')
    qrc.append('<file alias="components/UiImage.qml">%s</file>'%(out/'UiImage.qml'))
    (out/'BaseDelegate.qml').write_text('''import QtQuick
FocusScope {
 property int itemIndex: 0
 property var viewModel: null
 property var list: null
 property var subDialog: null
 property var model: null
 property bool externalMenu: false
 property real defaultHeight: 80
 property int defaultLabelFontWeight: 500
 property int defaultValueFontWeight: 500
 width: list ? list.width : 800
 signal activateSettingsSubMenu(int level,string menu,string file,string owner)
}''')
    qrc.append('<file alias="mainmenu/delegates/BaseDelegate.qml">%s</file>'%(out/'BaseDelegate.qml'));qrc.append('</qresource></RCC>')
    (out/'widgets.qrc').write_text('\n'.join(qrc))
    rcc=Path(PySide6.__file__).resolve().parent/'Qt/libexec/rcc'
    subprocess.run([str(rcc),'--binary',str(out/'widgets.qrc'),'-o',str(out/'widgets.rcc')],check=True)
    app=QGuiApplication([]);assert QResource.registerResource(str(out/'widgets.rcc'))
    engine=QQmlEngine();engine.addImportPath(str(out));errors=[]
    engine.warnings.connect(lambda items:errors.extend(x.toString() for x in items if 'Invalid image provider' not in x.toString()))
    server=ThreadingHTTPServer(('127.0.0.1',18765),Backend);threading.Thread(target=server.serve_forever,daemon=True).start()
    stock=(args.stock_qml/'mainmenu/delegates/SliderDelegate.qml').read_text().replace('import "../../scripts/Keys.js" as MKeys','import "qrc:/app/qml/scripts/Keys.js" as MKeys').replace('import ".."','import "qrc:/app/qml/mainmenu"\nimport "qrc:/app/qml/mainmenu/delegates"')
    (args.payload/'StockRearBrightness.qml').write_text(stock)
    def settle(pred):
        end=time.monotonic()+5
        while time.monotonic()<end:
            app.processEvents()
            if pred():return
            time.sleep(.005)
        raise AssertionError('Timeout: '+repr(errors))
    component=QQmlComponent(engine);component.setData(b'''import QtQuick
Item {
 width:800; height:500
 QtObject { id: bodyModel; objectName:"bodyModel"; property string itemName:"backlight_brightness"; property real propValue:80; property string text1:"Rear Screen Brightness"; property bool itemEnabled:true; property int options:1 }
 Item {id:list; width:800; property bool highlighting:true; property int currentIndex:0; function startHighlight(){} }
 X2dDisplayRearBrightness {id:row; model:bodyModel; list:list}
 QtObject {id:stockModel; objectName:"stockModel"; property string itemName:"backlight_brightness"; property real propValue:50; property string text1:"Rear Screen Brightness"; property bool itemEnabled:true; property int options:1}
 StockRearBrightness {objectName:"stockRow"; visible:false; model:stockModel; list:list}
}''',QUrl.fromLocalFile(str(args.payload/'fixture.qml')))
    fixture=component.create();assert fixture is not None,[e.toString() for e in component.errors()]
    try:
        row=fixture.findChild(QObject,'SliderDelegate_root');model=fixture.findChild(QObject,'bodyModel')
        slider=row.findChild(QObject,'settingsSlider');switch=row.findChild(QObject,'X2dDisplayAutoBrightnessSwitch')
        fill=row.findChild(QObject,'X2dBrightnessFill');knob=row.findChild(QObject,'X2dBrightnessCeilingKnob')
        settle(lambda:switch.property('value') and slider.property('automatic'))
        assert switch.property('text')=='自动亮度'
        assert not actions,'Opening the page must not write preferences'
        assert slider.property('value')==80 and model.property('propValue')==80
        settle(lambda:abs(fill.width()-slider.width()*29/99)<.2)
        x=knob.x();state['applied']=55
        settle(lambda:abs(fill.width()-slider.width()*54/99)<.2)
        assert knob.x()==x and model.property('propValue')==80,'Output must move fill only'
        state['applied']=15
        settle(lambda:abs(fill.width()-slider.width()*14/99)<.2)
        assert knob.x()==x
        # Native model updates keep the saved ceiling, and produce no control POSTs.
        for level in (74,78,82,87,74):
            slider.setProperty('value',level);app.processEvents();assert model.property('propValue')==level
        assert not actions and switch.property('value')
        state['applied']=74;settle(lambda:abs(fill.width()-slider.width()*73/99)<.2)
        slider.setProperty('value',20);app.processEvents()
        assert fill.width()<=knob.x()+knob.width()/2+.1,'Fill must stay left of the ceiling during edits'
        state['applied']=15;slider.setProperty('value',74);app.processEvents()
        window=QQuickWindow();window.resize(800,500);fixture.setParentItem(window.contentItem());window.show()
        assert QTest.qWaitForWindowExposed(window)
        auto_row=row.findChild(QQuickItem,'X2dDisplayAutoBrightnessRow')
        point=auto_row.mapToScene(QPointF(auto_row.width()/2,auto_row.height()/2)).toPoint()
        QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point,10)
        settle(lambda:not switch.property('value') and not slider.property('automatic'))
        assert actions==['/display/disable'] and row.property('featureAvailable')
        assert abs(fill.width()-knob.x()-knob.width()/2)<.1
        QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point,10)
        settle(lambda:switch.property('value') and slider.property('automatic'))
        assert actions==['/display/disable','/display/enable']
        stock_row=fixture.findChild(QObject,'stockRow');stock_model=fixture.findChild(QObject,'stockModel');stock_slider=stock_row.findChild(QObject,'settingsSlider')
        def drag(control,body,direction):
            control.setProperty('value',50);body.setProperty('propValue',50);app.processEvents()
            area=next(x for x in control.findChildren(QQuickItem) if x.metaObject().className()=='QQuickMouseArea')
            point=area.mapToScene(QPointF(area.width()/2,area.height()/2)).toPoint()
            QTest.mousePress(window,Qt.LeftButton,Qt.NoModifier,point,10);values=[]
            for offset in (12,24,42,64,86,108,130,152):
                QTest.mouseMove(window,point+QPoint(direction*offset,0),20);app.processEvents();values.append(body.property('propValue'))
            QTest.mouseRelease(window,Qt.LeftButton,Qt.NoModifier,point+QPoint(direction*152,0),10);app.processEvents();values.append(body.property('propValue'))
            assert len(set(values))>=5,values
            return values
        for direction in (1,-1):
            row.setVisible(False);stock_row.setVisible(True);app.processEvents();expected=drag(stock_slider,stock_model,direction)
            stock_row.setVisible(False);row.setVisible(True);app.processEvents();actual=drag(slider,model,direction)
            assert actual==expected,(actual,expected)
        assert actions==['/display/disable','/display/enable'] and state['enabled']
        # Stock navigation edits the ceiling without consuming feature control actions.
        slider.forceActiveFocus();before=model.property('propValue');QTest.keyClick(window,Qt.Key_Left);app.processEvents()
        assert model.property('propValue')==before-1
        assert actions==['/display/disable','/display/enable']
        state['available']=False;state['enabled']=False;state['effective']=False
        settle(lambda:not row.property('featureAvailable') and not slider.property('automatic'))
        assert auto_row.height()==0 and not auto_row.isVisible()
        assert abs(fill.width()-knob.x()-knob.width()/2)<.1
        # Execute the actual Bootstrap route function with a stock source and menu.
        source=(D/'src/Bootstrap.qml').read_text();start=source.index('    function routeDisplaySettings()');end=source.index('    Connections {',start)
        js=QJSEngine();result=js.evaluate('''var attached=true,root=this;
var originalLoader={source:"qrc:/app/qml/mainmenu/SettingsGeneric.qml"};
var screen={viewModel:{menu:{menuName:"displayMenu"}}};
'''+source[start:end]+'''
routeDisplaySettings();if(originalLoader.source!=="file:///system/etc/X2dDisplaySettings.qml")throw Error("display routing");
originalLoader.source="qrc:/app/qml/mainmenu/SettingsGeneric.qml";screen.viewModel.menu.menuName="focusMenu";
routeDisplaySettings();if(originalLoader.source!=="qrc:/app/qml/mainmenu/SettingsGeneric.qml")throw Error("other menu changed");true;''')
        assert not result.isError(),result.toString()
        if errors:raise AssertionError('\n'.join(errors))
        report=dict(passed=True,cameraAccessed=False,qt='6.4.1',checks=['actual generated packaged delegate and stock widgets','Display Auto enable/disable preserves availability','saved ceiling knob fixed as measured fill changes','no preference writes on status refresh','real continuous drags match stock in both directions and preserve Auto','feature off restores stock row geometry','Bootstrap Display-only routing'],limitations='Native model, sensor and service mocked; Android/camera lifecycle unverified')
        (args.payload/'display-qml-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
        window.close();fixture.setParentItem(None)
    finally:fixture.deleteLater();app.processEvents();server.shutdown();server.server_close()
if __name__=='__main__':main()
