"""Qt 6.4.1 stock/extended popup lifecycle and reversible icon checks; no USB.

Uses pinned private stock sources and reviewed focus inputs. Image rendering
and hardware proxies are substituted; this is not physical camera evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QUICK_BACKEND']='software'
import PySide6
from PySide6.QtCore import QFile, QIODevice, QObject, QResource, QUrl, qRegisterResourceData, qUnregisterResourceData, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

STOCK_HASHES = {
 'PopoverFocusMode.qml':'0a248ff9d99f230d3777c032f8a4a3efd79b31fc0dd8899cdeb8c15eeff2781b',
 'Popover.qml':'17b99b59233da2f603e95f5aa0a243b7531160a651255d9639f4c5d6fd9ee268',
 'FramedItem.qml':'0b0afb398e5d3a99ef93ef68418172cce9bb2abb68066591f8edb64b13fb8dc9',
 'FramedImage.qml':'239ade0d8b54d1c59383e36fac691331358ba3c7ac437b965731649f351e1af7',
 'FocusIndicator.qml':'e34a5ee95ab16997683f266f3cd3d8142ced4d6893d1e4436738e86ec68a69fc',
 'ScaledImage.qml':'0aacd7ab73207d721eff8aa130e9f32398967ed42d1c293a64baea8b718fb04b',
 'DataChangedAnimation.qml':'dc4cae60601ed29bc41e768c70ae370edf74a468387102d229001c570e5f93f2',
}
WRAPPER='''import QtQuick
import "qrc:/app/qml/components" as StockComponents
import "qrc:/app/qml/liveview"
import "qrc:/app/qml/viewmodels"
import com.hasselblad.types
import com.hasselblad.proxies
import com.hasselblad.uiproxies
Item {
 id: root; width: 1024; height: 768
 property bool popupOpen: false
 property bool requestEnable: false
 property int requestToken: 0
 property int currentMode: 0
 property bool selectable: true
 property bool scanRange: false
 property bool showInfo: true
 property bool lastResult: false
 property int captureToken: 0
 property string snapshot: ""
 property int selectedMode: -1
 property int selectionToken: 0
 property int popupCloses: 0
 property bool master:false
 property bool afcEnabled:false
 property int featureMask:7
 readonly property bool afcInstalled:(featureMask & 1)!==0
 property var afcMenu:controller
 property int gateToken:0
 onGateTokenChanged:syncAfcMenu()
 // ACTUAL_SYNC_AFC_MENU
 onSelectionTokenChanged: popup.item.contentItem.setSelected()
 onRequestTokenChanged: lastResult = controller.setEnabled(requestEnable)
 onPopupOpenChanged: {
  viewModel.mainState=popupOpen ? "focus_mode" : ""
  controller.refreshUi()
 }
 onCaptureTokenChanged: {
  var entries=[]
  for (var i=0;i<viewModel.focusModeModel.length;++i) {
   var entry=viewModel.focusModeModel[i]
   entries.push({mode:entry.focusMode,text:entry.text,icon:entry.icon.toString(),valid:entry.valid})
  }
  var p=popup.item
  var bindings=[]
  for (var b=0;b<controller.visualBindings.length;++b) {
   var binding=controller.visualBindings[b]
   bindings.push({name:binding.item.objectName,target:typeof binding.target!=="undefined" ? (binding.target ? binding.target.objectName : "null") : "holder",
                  value:typeof binding.value!=="undefined" ? binding.value : "holder",when:typeof binding.when!=="undefined" ? binding.when : false})
  }
  snapshot=JSON.stringify({items:entries,heading:p ? p.heading : "",source:popup.source.toString(),
    count:p ? p.contentItem.count : 0,numItems:p ? p.contentItem.numItems : 0,
    width:p ? p.contentWidth : 0,height:p ? p.contentHeight : 0,
    currentMode:Camera.focus_mode,badge:badge.symbol,liveIcon:indicator.children[0].source.toString(),
    liveVisible:indicator.children[0].visible,indicatorVisible:indicator.visible,
    stockObjects:viewModel.focusModeModel.length===2 && viewModel.focusModeModel[0]===stockAfs && viewModel.focusModeModel[1]===stockMf,
    originalText:stockAfs.text,originalIcon:stockAfs.icon.toString(),bindings:bindings})
 }
 Binding { target:Camera; property:"focus_mode"; value:root.currentMode }
 Binding { target:CameraUI; property:"focusModeSelectable"; value:root.selectable }
 StockComponents.FocusModeListItem {
  id:stockAfs; focusMode:HblmTypes.E_FocusModes_Afs; valid:root.selectable
  text:"Autofocus"; icon:"image://svg/ic_controlscreen_focus_mode_AF"
 }
 StockComponents.FocusModeListItem {
  id:stockMf; focusMode:HblmTypes.E_FocusModes_Man; valid:true
  text:"Manual Focus"; icon:"image://svg/ic_controlscreen_focus_mode_MF"
 }
 QtObject {
  id:viewModel
  property string mainState: ""
  property list<StockComponents.FocusModeListItem> focusModeModel:[stockAfs,stockMf]
  readonly property string focusModeIcon: "image://svg/ic_controlscreen_focus_mode_" +
     (root.currentMode===0 ? "AF" : root.currentMode===1 ? "AF-C" : "MF") + (root.selectable ? "" : "_disabled")
 }
 Item { id:badge; objectName:"ControlScreen_afControl"; property string symbol:viewModel.focusModeIcon }
 Item {
  property bool overlayOff:false
  property bool infoVisible:root.showInfo
  property bool showOnlyBottomRow:false
  LiveviewViewModel {
   id:liveModel; focusMode:root.currentMode; focusScanRangeEnabled:root.scanRange
   focusModeIcon:"image://svg/" + (root.currentMode===0 ? "ic_liveview_AF" : root.currentMode===1 ? "ic_liveview_AF-C" : "ic_liveview_MF")
  }
  FocusIndicator {
   id:indicator; viewModel:liveModel
   visible:showIndicators && !parent.overlayOff && parent.infoVisible && !parent.showOnlyBottomRow
  }
 }
 X2dAfcMenuController {
  id:controller; objectName:"TestAfcController"; uiRoot:root
  controlViewModel:viewModel; focusPopover:popup.item; focusPopoverOpen:root.popupOpen
  extendedPopupSource:Qt.resolvedUrl("X2dFocusModePopup.qml")
 }
 Loader {
  id:popup; objectName:"ControlScreen_popupLoader"; anchors.fill:parent; active:false
  onLoaded: {
   item.focusMode=Qt.binding(function(){return Camera.focus_mode})
   item.focusModeModel=Qt.binding(function(){return viewModel.focusModeModel})
  }
 }
 // Match the stock ControlScreen PropertyChanges and Loader.onLoaded route.
 Item {
  state:viewModel.mainState
  states:[State {
    name:"focus_mode"
    PropertyChanges { target:popup; source:"qrc:/app/qml/popups/PopoverFocusMode.qml"; restoreEntryValues:false }
    StateChangeScript { script:popup.active=true }
   },State {
    name:""; StateChangeScript { script:{popup.active=false;popup.source=""} }
   }]
 }
 Connections {
  target:popup.item
  function onSetFocusMode(mode) { root.selectedMode=mode }
  function onClosePopup() { root.popupCloses+=1;root.popupOpen=false }
 }
}'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--stock-sources',type=Path,required=True)
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert qVersion()=='6.4.1'
    inputs=args.inputs.resolve(); output=args.output.resolve()
    if output.exists():raise FileExistsError('Refusing to overwrite Qt test evidence')
    output.mkdir(parents=True)
    app=QGuiApplication([])
    tables=[(inputs/name).read_bytes() for name in ('focus.tree','focus.names','focus.data')]
    assert qRegisterResourceData(3,*tables)
    manifest=json.loads((inputs/'focus-ui-inputs.json').read_text())
    for item in manifest['privateIcons']:
        file=QFile(':'+item['path']);assert file.open(QIODevice.ReadOnly)
        content=bytes(file.readAll());file.close()
        assert hashlib.sha256(content).hexdigest()==item['sha256']
    fixtures=inputs/'host-layout'
    shutil.copytree(fixtures/'imports',output/'imports')
    for module,type_name,body in [('proxies','Camera','property int focus_mode: 0'),
                                  ('uiproxies','CameraUI','property bool canChangeAfc: true; property bool focusModeSelectable:true')]:
        folder=output/'imports/com/hasselblad'/module;folder.mkdir(parents=True,exist_ok=True)
        (folder/'qmldir').write_text('module com.hasselblad.'+module+'\nsingleton '+type_name+' 1.0 '+type_name+'.qml\n')
        (folder/(type_name+'.qml')).write_text('pragma Singleton\nimport QtQuick\nQtObject { '+body+' }\n')
    constants=output/'imports/com/hasselblad/constants/Constants.qml'
    constants.write_text(constants.read_text().replace('\n}', '\n property color popupFadeoutColor:"black"\n property color popupBackgroundColor:"black"\n property int animationBlinkLoops:2\n property int animationDurationBlink:200\n}'))
    source=output/'resources';shutil.copytree(fixtures/'app/qml',source)
    for name,expected in STOCK_HASHES.items():
        raw=(args.stock_sources/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==expected,name
        folder='popups' if name.startswith('Popover') else 'liveview' if name=='FocusIndicator.qml' else 'components/buttons' if name in ('FramedImage.qml','FramedItem.qml') else 'components'
        target=source/folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    (source/'components/controls').mkdir(exist_ok=True)
    (source/'components/controls/qmldir').write_text('')
    (source/'viewmodels').mkdir(exist_ok=True)
    (source/'viewmodels/LiveviewViewModel.qml').write_text('''import QtQuick
QtObject {
 property bool canShowFocusMode:true
 property int focusMode:0
 property bool focusScanRangeEnabled:false
 property bool extensionTubeAttached:false
 property string focusModeIcon:""
 property string focusScanRangeIcon:"image://svg/scan-range"
 property string lensMacroIcon:"image://svg/macro"
 property bool inSession:false
 property int afStatus:0
}''')
    xml=ET.Element('RCC');qrc=ET.SubElement(xml,'qresource',prefix='/app/qml')
    for path in sorted(source.rglob('*')):
        if path.is_file():ET.SubElement(qrc,'file',alias=path.relative_to(source).as_posix()).text=str(path)
    qrc_file=output/'fixtures.qrc';qrc_file.write_bytes(ET.tostring(xml))
    rcc=Path(PySide6.__file__).parent/'Qt/libexec/rcc'
    subprocess.run([str(rcc),'--binary',str(qrc_file),'-o',str(output/'fixtures.rcc')],check=True)
    assert QResource.registerResource(str(output/'fixtures.rcc'))
    cases=[];retained=[]
    expected={'zh':('对焦模式','单次自动对焦','连续自动对焦','手动对焦'),
              'en':('Focus Mode','Single Autofocus','AF-C','Manual Focus'),
              'zh-Hant':('對焦模式','單次自動對焦','連續自動對焦','手動對焦')}
    for language,labels in expected.items():
        folder=output/language;folder.mkdir()
        suffix='' if language=='zh' else '.'+language
        shutil.copy2(args.payload/('X2dAfcMenuController'+suffix+'.qml'),folder/'X2dAfcMenuController.qml')
        shutil.copy2(args.payload/'X2dFocusModePopup.qml',folder/'X2dFocusModePopup.qml')
        gate_source=(args.payload/'X2dSpeedBuffController.qml').read_text()
        gate_function=gate_source[gate_source.index('    function syncAfcMenu()'):gate_source.index('    function request(action)')]
        (folder/'Wrapper.qml').write_text(WRAPPER.replace('// ACTUAL_SYNC_AFC_MENU',gate_function))
        engine=QQmlEngine();engine.addImportPath(str(output/'imports'))
        warnings=[];engine.warnings.connect(lambda values,bucket=warnings:bucket.extend(w.toString() for w in values))
        component=QQmlComponent(engine,QUrl.fromLocalFile(str(folder/'Wrapper.qml')))
        obj=component.create();assert obj is not None,'\n'.join(e.toString() for e in component.errors())
        controller=obj.findChild(QObject,'TestAfcController')
        token=0;request_token=0
        def capture():
            nonlocal token
            for _ in range(5):app.processEvents()
            token+=1;obj.setProperty('captureToken',token);app.processEvents()
            return json.loads(obj.property('snapshot'))
        def switch(enable):
            nonlocal request_token
            request_token+=1;obj.setProperty('requestEnable',enable);obj.setProperty('requestToken',request_token)
            return capture()
        def stock_check(s):
            assert s['stockObjects'] and len(s['items'])==2,s
            assert [i['text'] for i in s['items']]==['Autofocus','Manual Focus'],s
            assert s['originalText']=='Autofocus' and s['originalIcon']=='image://svg/ic_controlscreen_focus_mode_AF',s
        off=capture();stock_check(off)
        assert not off['liveVisible'] and not off['indicatorVisible'] and off['badge'].endswith('_AF'),off
        obj.setProperty('popupOpen',True);off_popup=capture();stock_check(off_popup)
        assert off_popup['source'].startswith('qrc:') and off_popup['heading']=='Focus Mode',off_popup
        assert off_popup['numItems']==off_popup['count']==2 and off_popup['width']==672 and off_popup['height']==377.6,off_popup
        assert not switch(True)['source'].endswith('X2dFocusModePopup.qml') and not obj.property('lastResult')
        obj.setProperty('popupOpen',False)
        for gate_token,(master,afc,mask) in enumerate([(False,False,7),(False,True,7),(True,False,7),
                                                      (True,True,6),(True,True,7),(False,True,7)],1):
            obj.setProperty('master',master);obj.setProperty('afcEnabled',afc);obj.setProperty('featureMask',mask)
            obj.setProperty('gateToken',gate_token);s=capture()
            enabled=master and afc and bool(mask & 1)
            assert controller.property('loaded')==enabled,(master,afc,mask,s)
            if not enabled:stock_check(s)
            obj.setProperty('popupOpen',True);p=capture()
            assert p['source'].endswith('X2dFocusModePopup.qml')==enabled,p
            assert p['numItems']==(3 if enabled else 2),p
            obj.setProperty('popupOpen',False)
        for cycle in range(3):
            on=switch(True);assert controller.property('loaded') and obj.property('lastResult'),on
            assert [i['text'] for i in on['items']]==list(labels[1:]),on
            assert on['originalIcon']=='image://svg/ic_controlscreen_focus_mode_AF' and on['originalText']=='Autofocus',on
            for mode,name in [(0,'AF-S'),(1,'AF-C'),(2,'MF')]:
                obj.setProperty('currentMode',mode)
                for selectable in (True,False):
                    obj.setProperty('selectable',selectable);s=capture()
                    assert s['badge']=='image://svg/ic_x2d2_focus_control_'+name+('' if selectable else '_disabled'),s
                    assert s['liveIcon']=='image://svg/ic_x2d2_liveview_'+name+('' if selectable else '_disable'),s
                    assert s['liveVisible'] and s['indicatorVisible'],s
                obj.setProperty('selectable',True)
                obj.setProperty('popupOpen',True);p=capture()
                assert p['source'].endswith('X2dFocusModePopup.qml') and p['heading']==labels[0],p
                assert p['count']==p['numItems']==3 and abs(p['width']-790.4)<.001 and p['height']==460,p
                obj.setProperty('popupOpen',False)
            obj.setProperty('showInfo',False);assert not capture()['indicatorVisible']
            obj.setProperty('showInfo',True)
            obj.setProperty('currentMode',1);blocked=switch(False);assert not obj.property('lastResult') and len(blocked['items'])==3
            obj.setProperty('currentMode',2);restored=switch(False);assert obj.property('lastResult');stock_check(restored)
            for mode in (0,2):
                obj.setProperty('currentMode',mode);s=capture()
                assert s['badge']==('image://svg/ic_controlscreen_focus_mode_AF' if mode==0 else 'image://svg/ic_controlscreen_focus_mode_MF'),s
                assert s['liveIcon']==('image://svg/ic_liveview_AF' if mode==0 else 'image://svg/ic_liveview_MF'),s
                assert s['liveVisible']==(mode==2) and s['indicatorVisible']==(mode==2),s
            obj.setProperty('currentMode',0);obj.setProperty('scanRange',True);s=capture()
            assert s['liveVisible'] and s['indicatorVisible'] and s['liveIcon'].endswith('_AF'),s
            obj.setProperty('scanRange',False);obj.setProperty('popupOpen',True);p=capture();stock_check(p)
            assert p['source'].startswith('qrc:') and p['count']==2 and p['width']==672 and p['height']==377.6,p
            obj.setProperty('selectionToken',cycle+1);app.processEvents()
            assert obj.property('selectedMode')==0 and not obj.property('popupOpen')
        assert not warnings,'\n'.join(warnings)
        cases.append(dict(language=language,cycles=3,stockPopupAndObjectsPreserved=True,
                          actualMasterAndAfcGateVerified=True,
                          allModesAndDisabledIconsSynchronized=True,originalBindingsRestored=True,
                          popupOpenGuard=True,activeAfcDisableBlocked=True,stockSelectionSignal=True))
        retained.extend((engine,component,obj))
    report=dict(desktopOnly=True,targetQt='6.4.1',privateIconsVerified=18,cases=cases,
                stockSourceHashesVerified=True,imageProviderSubstituted=True,pixelsRendered=False,deviceValidated=False)
    (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert qUnregisterResourceData(3,*tables)


if __name__=='__main__':main()
