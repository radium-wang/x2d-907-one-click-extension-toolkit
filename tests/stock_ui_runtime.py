"""Real pinned stock visual resources; only native hardware/constant proxies.

No QML visual widget, shader, popup, input script or menu widget is fabricated.
"""
import json
from pathlib import Path
from PySide6.QtCore import QFile,QIODevice,QSize,Qt,qRegisterResourceData
from PySide6.QtGui import QImage,QPainter,QFontDatabase
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer
from stock_ui_evidence import verify,REQUIRED_SHA,sha

class Svg(QQuickImageProvider):
    def __init__(self):super().__init__(QQuickImageProvider.Image)
    def requestImage(self,name,size,requested):
        file=QFile(':/icons/'+name+'.svg')
        if not file.open(QIODevice.ReadOnly):raise AssertionError('missing stock SVG: '+name)
        renderer=QSvgRenderer(file.readAll())
        if not renderer.isValid():raise AssertionError('invalid SVG: '+name)
        scale=requested.width()/100 if requested.width()>0 else 1
        default=renderer.defaultSize()
        image=QImage(QSize(max(1,round(default.width()*scale)),max(1,round(default.height()*scale))),QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent);painter=QPainter(image);renderer.render(painter);painter.end();return image

def register(engine,stock,output,fonts=None):
    manifest=verify(stock);tables=[]
    for table in manifest['tables']:
        data=tuple((stock/table[n]['source']).read_bytes() for n in ('tree','names','data'))
        assert qRegisterResourceData(3,*data);tables.append(data)
    for path,expected in REQUIRED_SHA.items():
        file=QFile(':'+path);assert file.open(QIODevice.ReadOnly),path
        assert sha(bytes(file.readAll()))==expected,path
    file=QFile(':/app/qml/components/FocusFramedImage.qml');assert not file.exists()
    # The UI bank pins the native selector constants; do not substitute a
    # gray host highlight or a generic three-row wheel for stock settings.
    source=QFile(':/app/qml/common/GlobalConstants.qml')
    assert source.open(QIODevice.ReadOnly)
    constants_source=bytes(source.readAll()).decode()
    for definition in ('highlightColor: hblOrange','highlightItemColor: colorWhite',
                       'itemColor: colorLightGray','numberOfItemsVisibleInList: 4.3',
                       'listViewSizeIncreaseFactor: 0.3','defaultBorderWidth: 3.2 * root.scaleFactorX'):
        assert definition in constants_source,definition
    engine.addImageProvider('svg',Svg())
    if fonts:
        for name in ('AvenirNext-Regular-08.ttf','AvenirNext-Medium-06.ttf','AvenirNext-Bold-01.ttf','DroidSansFallback.ttf'):
            assert QFontDatabase.addApplicationFont(str(fonts/name))>=0,name
    # Constants are C++ hardware/product properties on the camera, not QML
    # visual components. Relative baseline/candidate checks share these values.
    values={
      'scaleFactor':('real','1'),'scaleFactorX':('real','1'),'scaleFactorY':('real','1'),
      'popupBorderWidth':('int','2'),'popupBorderColor':('color','"#80ffffff"'),
      'popupHeaderTextSize':('int','32'),'popupHeaderHeight':('int','64'),
      'popupBackgroundColor':('color','"black"'),'popupFadeoutColor':('color','"black"'),
      'fadeOutOpacity':('real','0.75'),'fadeOutDuration':('int','0'),
      'popupTextColor':('color','"white"'),'colorWhite':('color','"white"'),
      'highlightColor':('color','"#de4200"'),'menuItemFontName':('string','"Avenir Next"'),
      'uiLut':('url','""'),'imageFragmentShaderFilename':('url','"qrc:/shaders/photo.frag.qsb"'),
      'photoVertexShaderFilename':('url','"qrc:/shaders/photo.vert.qsb"'),
      'menuBackgroundColor':('color','"black"'),'mainBackgroundColor':('color','"black"'),
      'menuHeaderColor':('color','"white"'),'menuItemColor':('color','"white"'),
      'menuItemDisabledTextOpacity':('real','0.6'),'menuListItemDefaultHeight':('int','120'),
      'menuListDividerHeight':('int','1'),'menuListDividerColor':('color','"#444444"'),
      'settingsMenuSettingLeftMargin':('int','40'),'settingsMenuSettingRightMargin':('int','40'),
      'settingsMenuHeaderSuffixFontColor':('color','"white"'),
      'settingsMenuSubSectionHeaderTopMargin':('int','100'),'settingsMenuExternalHeaderTopMargin':('int','100'),
      'externalMenuBackArrowLeftMargin':('int','40'),'menuBackArrowLeftMargin':('int','40'),
      'settingsMenuHeaderFontSize':('int','32'),'settingsMenuHeaderFontName':('string','"Avenir Next"'),
      'settingsMenuSettingSwitchFontName':('string','"Avenir Next"'),'settingsMenuSettingSwitchFontSize':('int','32'),
      'settingsMenuDescriptionFontSize':('int','32'),'wheelTimeoutTimeMs':('int','3000'),
      'defaultCheckBoxSize':('int','32'),
      'defaultBorderWidth':('real','3.2'),'popupListSelectorPixelSize':('real','115.2'),'menuDropDownHeight':('real','505'),
      'popupListMarginY':('int','131'),'numberOfItemsVisibleInList':('real','4.3'),
      'listViewSizeIncreaseFactor':('real','0.3'),'settingsMenuSettingDropDownTextMargin':('int','16'),
      'popoverListViewShadingStartColor':('color','"#a0000000"'),'highlightItemColor':('color','"white"'),'itemColor':('color','"lightgray"')}
    constants='pragma Singleton\nimport QtQuick\nQtObject {\n'+''.join(' property '+t+' '+name+':'+v+'\n' for name,(t,v) in values.items())+'}\n'
    types='''pragma Singleton
import QtQuick
QtObject {
 enum FocusModes { E_FocusModes_Unused,E_FocusModes_Afs,E_FocusModes_Afc,E_FocusModes_Man,E_FocusModes_Reserved,E_FocusModes_Multi,E_FocusModes_Aft,E_FocusModes_Max }
 enum CameraKeyOption { E_CameraKeyOption_OverrideHalfPress }
 enum GuiPopupState { E_GuiPopupState_None,E_GuiPopupState_FocusMode,E_GuiPopupState_Iso }
}'''
    keys='''pragma Singleton
import QtQuick
QtObject {
 enum Functions { Up,Down,NavLeft,NavRight,PopAccept,FocusMode,Abort,Menu,Browse,Select,JstkEscape,ListUp,ListDown,JstkLeft,JstkRight,Play,NavKey,Iso,IsoWb }
 function isFn(key,mods,name) {
  if(name===KeyFn.Up || name===KeyFn.ListUp)return key===Qt.Key_Up
  if(name===KeyFn.Down || name===KeyFn.ListDown)return key===Qt.Key_Down
  if(name===KeyFn.NavLeft)return key===Qt.Key_Left
  if(name===KeyFn.NavRight)return key===Qt.Key_Right
  if(name===KeyFn.PopAccept)return key===Qt.Key_Space || key===Qt.Key_Return
  if(name===KeyFn.Abort || name===KeyFn.JstkEscape)return key===Qt.Key_Escape
  if(name===KeyFn.Menu)return key===Qt.Key_F1
  return false
 }
}'''
    modules=[('constants','Constants',constants),('types','HblmTypes',types),('keys','KeyFn',keys),
             ('proxies','Camera','pragma Singleton\nimport QtQuick\nQtObject {property int focus_mode:1}'),
             ('uiproxies','CameraUI','pragma Singleton\nimport QtQuick\nQtObject {property bool canChangeAfc:true;property bool focusModeSelectable:true}')]
    for module,name,source in modules:
        folder=output/'imports/com/hasselblad'/module;folder.mkdir(parents=True,exist_ok=True)
        (folder/'qmldir').write_text(f'module com.hasselblad.{module}\nsingleton {name} 1.0 {name}.qml\n')
        (folder/(name+'.qml')).write_text(source)
    engine.addImportPath(str(output/'imports'))
    return tables,manifest
