"""Qt 6.4.1 cache, private resource and multilingual 2/3-mode checks; no camera.

Needs the private inputs prepared by prepare_focus_ui.py and its Qt host check.
The image item is a geometry substitute; this test does not render camera pixels.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QUICK_BACKEND']='software'
os.environ.pop('QML_DISABLE_DISK_CACHE',None)
os.environ['QML_FORCE_DISK_CACHE']='1'
import PySide6
from PySide6.QtCore import QFile, QIODevice, QObject, QResource, QUrl, qRegisterResourceData, qUnregisterResourceData, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from shiboken6 import getCppPointer

WRAPPER='''import QtQuick
import "qrc:/app/qml/components" as StockComponents
import "qrc:/app/qml/popups"
import com.hasselblad.types
import com.hasselblad.proxies
Item {
 id: root; width: 1024; height: 768
 property bool popupOpen: false
 property bool requestEnable: false
 property int requestToken: 0
 property int currentMode: 0
 property bool lastResult: false
 property int captureToken: 0
 property string snapshot: ""
 property int selectedMode: -1
 property int selectionToken: 0
 onSelectionTokenChanged: popup.contentItem.setSelected()
 onRequestTokenChanged: lastResult = controller.setEnabled(requestEnable)
 onCaptureTokenChanged: {
  var entries=[]
  for (var i=0;i<viewModel.focusModeModel.length;++i) {
   var entry=viewModel.focusModeModel[i]
   entries.push({mode:entry.focusMode,text:entry.text,icon:entry.icon.toString()})
  }
  snapshot=JSON.stringify({items:entries,heading:popup.heading,
    count:popup.contentItem.count,numItems:popup.contentItem.numItems,
    currentMode:Camera.focus_mode,itemWidth:popup.contentItem.itemWidth})
 }
 Binding { target:Camera; property:"focus_mode"; value:root.currentMode }
 QtObject {
  id:viewModel
  property list<StockComponents.FocusModeListItem> focusModeModel: [
   StockComponents.FocusModeListItem { focusMode:HblmTypes.E_FocusModes_Afs; valid:true; text:"Autofocus" },
   StockComponents.FocusModeListItem { focusMode:HblmTypes.E_FocusModes_Man; valid:true; text:"Manual Focus" }
  ]
 }
 X2dAfcMenuController {
  id:controller; objectName:"TestAfcController"
  controlViewModel:viewModel; focusPopover:popup; focusPopoverOpen:root.popupOpen
 }
 PopoverFocusMode {
  id:popup; objectName:"TestPopup"; anchors.fill:parent
  focusModeModel:viewModel.focusModeModel; focusMode:Camera.focus_mode
  onSetFocusMode:(mode)=>root.selectedMode=mode
 }
}'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert qVersion()=='6.4.1'
    inputs=args.inputs.resolve(); output=args.output.resolve()
    if output.exists():raise FileExistsError('Refusing to overwrite Qt test evidence')
    output.mkdir(parents=True)
    os.environ['QML_DISK_CACHE_PATH']=str(output/'cache')
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
                                  ('uiproxies','CameraUI','property bool canChangeAfc: true')]:
        folder=output/'imports/com/hasselblad'/module;folder.mkdir(parents=True,exist_ok=True)
        (folder/'qmldir').write_text('module com.hasselblad.'+module+'\nsingleton '+type_name+' 1.0 '+type_name+'.qml\n')
        (folder/(type_name+'.qml')).write_text('pragma Singleton\nimport QtQuick\nQtObject { '+body+' }\n')
    source=output/'resources';shutil.copytree(fixtures/'app/qml',source)
    (source/'popups/PopoverFocusMode.qml').write_text('import QtQuick\nItem {}\n')
    xml=ET.Element('RCC');qrc=ET.SubElement(xml,'qresource',prefix='/app/qml')
    for path in sorted(source.rglob('*')):
        if path.is_file():ET.SubElement(qrc,'file',alias=path.relative_to(source).as_posix()).text=str(path)
    qrc_file=output/'fixtures.qrc';qrc_file.write_bytes(ET.tostring(xml))
    rcc=Path(PySide6.__file__).parent/'Qt/libexec/rcc'
    subprocess.run([str(rcc),'--binary',str(qrc_file),'-o',str(output/'fixtures.rcc')],check=True)
    assert QResource.registerResource(str(output/'fixtures.rcc'))
    class CachedUnit(ctypes.Structure):
        _fields_=[('data',ctypes.c_void_p),('aot',ctypes.c_void_p),('unused',ctypes.c_void_p)]
    Lookup=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p)
    class Registration(ctypes.Structure):
        _fields_=[('version',ctypes.c_int),('lookup',Lookup)]
    qt=Path(PySide6.__file__).parent/'Qt/lib'
    core=ctypes.CDLL(str(qt/'QtCore.framework/Versions/A/QtCore'))
    qml=ctypes.CDLL(str(qt/'QtQml.framework/Versions/A/QtQml'))
    equal=getattr(core,'_ZNK4QUrleqERKS_');equal.argtypes=[ctypes.c_void_p,ctypes.c_void_p];equal.restype=ctypes.c_bool
    url=QUrl('qrc:/app/qml/popups/PopoverFocusMode.qml')
    storage=ctypes.create_string_buffer((inputs/'focus-popup.qt64.bin').read_bytes())
    cached=CachedUnit(ctypes.addressof(storage),None,None)
    hits=[]
    def lookup(pointer):
        if equal(pointer,getCppPointer(url)[0]):
            hits.append(True);return ctypes.addressof(cached)
        return None
    callback=Lookup(lookup);registration=Registration(0,callback)
    register=getattr(qml,'_ZN11QQmlPrivate11qmlregisterENS_16RegistrationTypeEPv')
    register.argtypes=[ctypes.c_int,ctypes.c_void_p];register.restype=ctypes.c_int
    register(6,ctypes.byref(registration))
    cases=[];retained=[]
    expected={'zh':('对焦模式','单次自动对焦','连续自动对焦','手动对焦'),
              'en':('Focus Mode','Single Autofocus','AF-C','Manual Focus'),
              'zh-Hant':('對焦模式','單次自動對焦','連續自動對焦','手動對焦')}
    for language,labels in expected.items():
        folder=output/language;folder.mkdir()
        suffix='' if language=='zh' else '.'+language
        shutil.copy2(args.payload/('X2dAfcMenuController'+suffix+'.qml'),folder/'X2dAfcMenuController.qml')
        (folder/'Wrapper.qml').write_text(WRAPPER)
        engine=QQmlEngine();engine.addImportPath(str(output/'imports'))
        warnings=[];engine.warnings.connect(lambda values,bucket=warnings:bucket.extend(w.toString() for w in values))
        component=QQmlComponent(engine,QUrl.fromLocalFile(str(folder/'Wrapper.qml')))
        obj=component.create();assert obj is not None,'\n'.join(e.toString() for e in component.errors())
        controller=obj.findChild(QObject,'TestAfcController')
        token=0
        def capture():
            nonlocal token
            for _ in range(5):app.processEvents()
            token+=1;obj.setProperty('captureToken',token);app.processEvents()
            return json.loads(obj.property('snapshot'))
        off=capture();assert len(off['items'])==off['count']==off['numItems']==2,off
        assert [item['text'] for item in off['items']]==[labels[1],labels[3]],off
        assert off['heading']==labels[0] and off['currentMode']==0,off
        assert off['items'][0]['icon']=='image://svg/ic_x2d2_focus_control_AF-S'
        obj.setProperty('requestEnable',True);obj.setProperty('requestToken',1)
        on=capture();assert controller.property('loaded') and obj.property('lastResult')
        assert len(on['items'])==on['count']==on['numItems']==3,on
        assert [item['text'] for item in on['items']]==list(labels[1:]),on
        assert on['currentMode']==0 and abs(on['itemWidth']-226.4)<.001,on
        frame=obj.findChild(QObject,'X2d2FocusPopupFrame')
        assert abs(frame.property('width')-790.4)<.001 and abs(frame.property('height')-460)<.001
        obj.setProperty('currentMode',1);obj.setProperty('requestEnable',False);obj.setProperty('requestToken',2)
        blocked=capture();assert not obj.property('lastResult') and len(blocked['items'])==3
        obj.setProperty('currentMode',2);obj.setProperty('requestToken',3)
        restored=capture();assert obj.property('lastResult') and len(restored['items'])==restored['count']==2
        obj.setProperty('selectionToken',1);app.processEvents();assert obj.property('selectedMode')==2
        assert not warnings,'\n'.join(warnings)
        cases.append(dict(language=language,twoAndThreeModesVerified=True,modeRetainedOnEnable=True,
                          activeAfcDisableBlocked=True,mfSelectionSignalVerified=True,
                          heading=on['heading'],originalTypographyAndBorders=True))
        retained.extend((engine,component,obj))
    assert hits,'Empty-source resource did not use the supplied cache'
    report=dict(desktopOnly=True,targetQt='6.4.1',privateIconsVerified=18,
                originalPopupSourceEmpty=True,cacheHits=len(hits),cases=cases,
                imageProviderSubstituted=True,pixelsRendered=False,deviceValidated=False)
    (output/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert qUnregisterResourceData(3,*tables)


if __name__=='__main__':main()
