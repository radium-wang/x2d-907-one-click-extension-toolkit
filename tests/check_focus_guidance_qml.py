"""Qt 6.4.1 three-language stock-style hint and touch checks; no camera access."""
import argparse,json,os,sys,time,shutil
from pathlib import Path
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'tests'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--payload',type=Path,default=Path(os.environ.get('X2D_PAYLOAD_DIR',str(D/'src/native-package'))))
parser.add_argument('--output',type=Path,default=D/'src/outputs/focus-guidance-layout')
args=parser.parse_args()
from PySide6.QtCore import QUrl,QObject,Qt,QPoint,QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine,QQmlComponent
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from host_menu_fixtures import register
app=QGuiApplication([]);reports=[]
payload=args.payload.resolve()
for language,suffix in [('zh',''),('en','.en'),('zh-Hant','.zh-Hant')]:
 engine=QQmlEngine();register(engine)
 out=args.output/language;out.mkdir(parents=True,exist_ok=True)
 shutil.copy2(payload/('X2dPlayPage'+suffix+'.qml'),out/'X2dPlayPage.qml')
 shutil.copy2(payload/'X2dAutoBrightnessController.qml',out/'X2dAutoBrightnessController.qml')
 qml='''import QtQuick
import com.hasselblad.constants
import "qrc:/app/qml/mainmenu" as StockMenu
Item {
 width:1024;height:768
 property real uiScale:1
 property alias master:features.master
 property alias loaded:features.loaded
 property alias calls:features.calls
 property alias featureMask:features.featureMask
 property alias noticeReady:features.freeNoticeReady
 property alias noticeSeen:features.freeNoticeSeen
 property alias noticeAcknowledged:features.freeNoticeAcknowledged
 onUiScaleChanged:{Constants.scaleFactor=uiScale;Constants.scaleFactorX=uiScale;Constants.scaleFactorY=uiScale}
 QtObject {id:features;property bool master:true;property int featureMask:7;readonly property bool afcInstalled:(featureMask&1)!==0;readonly property bool speedInstalled:(featureMask&2)!==0;readonly property bool brightnessInstalled:(featureMask&4)!==0;property bool loaded:false;property bool busy:false;property bool ready:true;property bool faulted:false;property bool afcEnabled:false;property string statusMessage:"offline";property int calls:0
 property bool freeNoticeReady:false;property bool freeNoticeSeen:false;property bool freeNoticeAcknowledged:false
 function acknowledgeFreeNotice(){freeNoticeAcknowledged=true;freeNoticeSeen=true;return true}
 function setEnabled(value){loaded=value;calls++;return true}}
 X2dPlayPage {anchors.fill:parent;pageActive:true;featureController:features}
 StockMenu.SettingDescription {objectName:"StockDescriptionReference";text:"Reference";isEnabled:features.master;visible:false}
}'''
 c=QQmlComponent(engine);c.setData(qml.encode(),QUrl.fromLocalFile(str(out/'layout.qml')))
 root=c.create();assert root is not None,[str(e) for e in c.errors()]
 win=QQuickWindow();win.resize(1024,768);root.setParentItem(win.contentItem());win.show()
 hint=root.findChild(QObject,'X2dFocusSpeedHint');row=root.findChild(QObject,'X2dPlaySpeedSwitchRow');ref=root.findChild(QObject,'StockDescriptionReference');list_=root.findChild(QObject,'X2dPlaySettingsList')
 page=root.findChild(QObject,'PlayPageRoot')
 notice=root.findChild(QObject,'X2dFreeProjectNotice')
 noticeFrame=root.findChild(QObject,'X2dFreeProjectNoticeFrame')
 message=root.findChild(QObject,'X2dFreeProjectNoticeMessage')
 button=root.findChild(QObject,'X2dFreeProjectNoticeButton')
 buttonText=root.findChild(QObject,'X2dFreeProjectNoticeButtonText')
 copy={
  'zh':('本项目完全免费，如果有人收你钱了，那你纯是被骗了','好的，我没被骗'),
  'zh-Hant':('本項目完全免費，如果有人收你錢了，那你純是被騙了','好的，我沒被騙'),
  'en':('This project is completely free. If someone charged you for it, you were scammed.',"Okay, I wasn't scammed")}
 def settle():
  end=time.monotonic()+.15
  while time.monotonic()<end:app.processEvents();time.sleep(.003)
 for index,(scale,width) in enumerate([(1,1024),(.75,768),(1,620)]):
  root.setProperty('uiScale',scale);root.setProperty('width',width);win.resize(width,768);settle()
  page.setProperty('pageActive',False)
  root.setProperty('noticeReady',False);root.setProperty('noticeSeen',False);root.setProperty('noticeAcknowledged',False)
  page.setProperty('pageActive',True);settle()
  assert not notice.isVisible() and not page.property('settingsActive')
  root.setProperty('noticeReady',True);settle()
  assert notice.isVisible() and not page.property('settingsActive')
  assert message.property('text')==copy[language][0] and buttonText.property('text')==copy[language][1]
  assert not message.property('truncated') and message.property('contentWidth')<=message.width()+.5
  assert not buttonText.property('truncated') and buttonText.property('contentHeight')<=button.height()
  assert noticeFrame.height()<=win.height() and noticeFrame.width()<=win.width()
  before=root.property('calls')
  QTest.mouseClick(win,Qt.LeftButton,Qt.NoModifier,QPoint(20,120));settle()
  assert notice.isVisible() and root.property('calls')==before
  win.grabWindow().save(str(out/('notice-'+str(width)+'.png')))
  point=button.mapToItem(win.contentItem(),QPointF(button.width()/2,button.height()/2))
  QTest.mouseClick(win,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())));settle()
  assert not notice.isVisible() and page.property('settingsActive') and root.property('calls')==before
  page.setProperty('pageActive',False);page.setProperty('pageActive',True);settle()
  assert not notice.isVisible() and page.property('settingsActive')
  assert hint.property('font').pixelSize()==ref.property('font').pixelSize()==round(32*scale)
  assert hint.property('opacity')==ref.property('opacity')==.7
  assert not hint.property('truncated')
  assert hint.property('contentWidth')<=hint.property('width')+.5
  assert hint.height()>=hint.property('contentHeight')-.5
  assert hint.parentItem().y()+hint.y()+hint.height()<=row.height()+.5
  point=row.mapToItem(win.contentItem(),QPointF(width/2,15))
  QTest.mouseClick(win,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())));settle()
  assert root.property('calls')==index+1,(language,root.property('calls'))
  reports.append(dict(language=language,width=width,scale=scale,fontPixels=hint.property('font').pixelSize(),lines=hint.property('lineCount'),rowHeight=row.height(),text=hint.property('text'),realSwitchClickPassed=True,noticeText=message.property('text'),noticeButton=buttonText.property('text'),noticeInputBlocked=True,noticeFirstOnlyAndButtonClosePassed=True))
 win.grabWindow().save(str(out/'enabled.png'))
 root.setProperty('master',False);settle();assert hint.property('opacity')==ref.property('opacity')
 point=row.mapToItem(win.contentItem(),QPointF(310,15));before=root.property('calls')
 QTest.mouseClick(win,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())));settle();assert root.property('calls')==before
 win.grabWindow().save(str(out/'disabled.png'))
 for mask in range(1,8):
  root.setProperty('featureMask',mask);settle()
  for bit,name in [(1,'X2dPlayAfcSwitchRow'),(2,'X2dPlaySpeedSwitchRow'),(4,'X2dPlayAutoBrightnessSwitchRow')]:
   selectedRow=root.findChild(QObject,name);assert selectedRow is not None,name
   assert selectedRow.property('visible')==bool(mask&bit),(language,mask,name)
   assert (selectedRow.height()>0)==bool(mask&bit),(language,mask,name)
 win.close();root.deleteLater();win.deleteLater();app.processEvents()
(args.output/'focus-guidance-layout-validation.json').write_text(json.dumps(dict(passed=True,cameraAccessed=False,stockComponent='SettingDescription',layouts=reports),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(reports,ensure_ascii=False))
