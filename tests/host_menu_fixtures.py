"""Desktop-only stock settings/service substitutes; no camera communication."""
from pathlib import Path
import subprocess
from PySide6.QtCore import QResource
import PySide6

D = Path(__file__).resolve().parents[1]/'src'
F = D / '.stock-host'

def register(engine):
    def write(name, text):
        path=F/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
    constants='''pragma Singleton
import QtQuick
QtObject {
 property real scaleFactor: 1
 property real scaleFactorX: 1
 property real scaleFactorY: 1
 property color mainBackgroundColor: "black"
 property color menuBackgroundColor: "black"
 property color popupTextColor: "white"
 property color popupFadeoutColor: "black"
 property color popupBackgroundColor: "black"
 property color popupBorderColor: "gray"
 property real popupBorderWidth: 3.2
 property real fadeOutOpacity: 0.8
 property color colorWhite: "white"
 property color highlightColor: "red"
 property color settingsMenuHeaderSuffixFontColor: "white"
 property string menuItemFontName: "Arial"
 property real settingsMenuDescriptionFontSize: 32 * scaleFactor
 property real menuItemDisabledTextOpacity: 0.6
 property int wheelTimeoutTimeMs: 3000
 property int menuListItemDefaultHeight: 120
 property int menuListDividerHeight: 1
 property color menuListDividerColor: "gray"
 property int settingsMenuSettingLeftMargin: 40
 property int settingsMenuSettingRightMargin: 40
}'''
    for module, name, content in [
      ('constants','Constants',constants),
      ('types','HblmTypes','pragma Singleton\nimport QtQuick\nQtObject { enum FocusModes { E_FocusModes_Afs, E_FocusModes_Afc, E_FocusModes_Man } }'),
      ('proxies','Camera','pragma Singleton\nimport QtQuick\nQtObject { property int focus_mode: 0 }'),
      ('uiproxies','CameraUI','pragma Singleton\nimport QtQuick\nQtObject { property bool canChangeAfc: false }')]:
        base='imports/com/hasselblad/'+module+'/'
        write(base+'qmldir',f'module com.hasselblad.{module}\nsingleton {name} 1.0 {name}.qml\n')
        write(base+name+'.qml',content)
    resources={
      'mainmenu/MenuHeader.qml':'import QtQuick\nItem { height:100; property bool showSeparator:false; property var text: []; signal close() }',
      'mainmenu/MenuBoolSelector.qml':'import QtQuick\nItem { height:100; property string text:""; property bool value:false; property bool itemEnabled:true; property bool highlighted:false; property bool showSwitch:true; property int fontWeight:Font.Medium }',
      'components/FocusModeListItem.qml':'import QtQuick\nQtObject { property int focusMode:0; property bool valid:false; property url icon; property string text:"" }'}
    description=D/'outputs/stock-qml/mainmenu/SettingDescription.qml'
    resources['mainmenu/SettingDescription.qml']=description.read_text() if description.exists() else 'import QtQuick\nimport com.hasselblad.constants\nText { property bool isEnabled:true; property bool highlighted:false; font.pixelSize:Constants.settingsMenuDescriptionFontSize; color:Constants.colorWhite; opacity:isEnabled?0.7:Constants.menuItemDisabledTextOpacity; wrapMode:Text.WordWrap }'
    for name, content in resources.items(): write('resource-stubs/'+name,content)
    qrc=F/'resource-stubs.qrc'
    qrc.write_text('<RCC><qresource prefix="/app/qml">'+''.join(f'<file alias="{name}">resource-stubs/{name}</file>' for name in resources)+'</qresource></RCC>')
    rcc=Path(PySide6.__file__).parent/'Qt/libexec/rcc'
    result=subprocess.run([str(rcc),'--binary',str(qrc),'-o',str(F/'resource-stubs.rcc')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert QResource.registerResource(str(F/'resource-stubs.rcc'))
    engine.addImportPath(str(F/'imports'))
