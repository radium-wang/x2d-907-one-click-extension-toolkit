"""Rear brightness UI generated from the exact stock resources at build time.

Stock QML remains an ignored build input/output. Structural edits preserve all
other Display delegates, models, submenus, touch handling and key handling.
"""
def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Stock brightness QML anchor changed: ' + old[:70])
    return text.replace(old, new, 1)


def settings(text):
    for old,new in (
        ('import "../components" as Components','import "qrc:/app/qml/components" as Components\nimport "qrc:/app/qml/mainmenu"'),
        ('import "../scripts/Keys.js" as MKeys','import "qrc:/app/qml/scripts/Keys.js" as MKeys'),
        ('import "delegates"','import "qrc:/app/qml/mainmenu/delegates"')):
        text=once(text,old,new)
    return once(text,'                    source: {\n','''                    source: {
                        if (root.menuName === "displayMenu" && model.itemName === "backlight_brightness" &&
                            model.elem === GuiTypes.E_MenuElem_Slider)
                            return "file:///system/etc/X2dDisplayRearBrightness.qml"
''')


def slider(text):
    text=once(text,'import "../scripts/Keys.js" as MKeys','import "qrc:/app/qml/scripts/Keys.js" as MKeys')
    text=once(text,'    property real value: 1','''    // The knob is the saved ceiling; only the fill follows measured output.
    property bool automatic: false
    property real actualValue: value
    property real smoothActualValue: actualValue
    Behavior on smoothActualValue { enabled: root.automatic; NumberAnimation { duration: 200 } }
    property real fillValue: automatic ? Math.max(minValue, Math.min(value, smoothActualValue)) : value
    property real value: 1''')
    text=once(text,'            id: sliderBar','            id: sliderBar\n            objectName: "X2dBrightnessFill"')
    text=once(text,'            width: slidingMarker.x + slidingMarker.width / 2','''            width: root.automatic ? horizontalLine.width * (root.fillValue - root.minValue) / (root.maxValue - root.minValue) :
                                    slidingMarker.x + slidingMarker.width / 2''')
    text=once(text,'            id: slidingMarker','            id: slidingMarker\n            objectName: "X2dBrightnessCeilingKnob"')
    return text


def rear(text):
    text=once(text,'import "../../scripts/Keys.js" as MKeys','import "qrc:/app/qml/scripts/Keys.js" as MKeys')
    text=once(text,'import ".."','import "qrc:/app/qml/mainmenu"\nimport "qrc:/app/qml/mainmenu/delegates"')
    text=once(text,'    height: topOffset + column.height','''    readonly property bool featureAvailable: controller.masterEnabled && controller.availablePreference
    property bool autoSelected: false
    readonly property real autoHeight: featureAvailable ? Constants.menuListItemDefaultHeight : 0
    height: autoHeight + topOffset + column.height
    AutoBrightnessController {
        id: controller
        followMaster: true
        pageActive: root.visible
    }
    Item {
        objectName: "X2dDisplayAutoBrightnessRow"
        width: parent.width; height: root.autoHeight; visible: root.featureAvailable
        MenuBoolSelector {
            objectName: "X2dDisplayAutoBrightnessSwitch"
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
            anchors.rightMargin: Constants.settingsMenuSettingRightMargin
            anchors.verticalCenter: parent.verticalCenter
            text: "自动亮度"
            value: controller.enabledPreference
            itemEnabled: root.model.itemEnabled && !controller.busy && (controller.ready || controller.enabledPreference)
            highlighted: autoTouch.pressed || (root.autoSelected && root.list.highlighting && root.list.currentIndex === root.itemIndex)
            showSwitch: true; fontWeight: Constants.menuItemLabelFontWeight
        }
        MouseArea {
            id: autoTouch; anchors.fill: parent
            enabled: root.model.itemEnabled && !controller.busy && (controller.ready || controller.enabledPreference)
            onClicked: { root.autoSelected = true; controller.toggle() }
        }
    }''')
    text=once(text,'        if (settingsSlider.activeFocus) {','        if (!fromTouch && root.featureAvailable && root.autoSelected) { controller.toggle(); return }\n        if (settingsSlider.activeFocus) {')
    text=once(text,'        anchors.fill: parent\n        color: "transparent"','        anchors.fill: parent\n        anchors.topMargin: root.autoHeight\n        color: "transparent"')
    text=once(text,'            topMargin: root.topOffset','            topMargin: root.autoHeight + root.topOffset')
    text=once(text,'                text: root.model.text1','                text: root.featureAvailable ? "显示屏最高亮度" : root.model.text1')
    text=once(text,'        SettingSlider {','        BrightnessSlider {')
    text=once(text,'            value: root.model.propValue','''            value: root.model.propValue
            automatic: root.featureAvailable && controller.enabledPreference && controller.effective
            actualValue: controller.applied''')
    text=once(text,'    Keys.onPressed: (event)=> {','''    Keys.onPressed: (event)=> {
        if (root.featureAvailable && !settingsSlider.activeFocus) {
            if (root.autoSelected && MKeys.pressedFnAcc(KeyFn.ListDown, event)) {
                root.autoSelected = false; return
            }
            if (!root.autoSelected && MKeys.pressedFnAcc(KeyFn.ListUp, event)) {
                root.autoSelected = true; return
            }
        }
''')
    return text


def generate(resources, out):
    files={'DisplaySettings': ('mainmenu/SettingsGeneric.qml',settings),
           'DisplayRearBrightness': ('mainmenu/delegates/SliderDelegate.qml',rear),
           'BrightnessSlider': ('mainmenu/SettingSlider.qml',slider)}
    generated={}
    for name,(stock,patch) in files.items():
        path=out/(name+'.qml')
        path.write_text(patch(resources[':/app/qml/'+stock].decode('utf-8')),encoding='utf-8')
        generated[name]=path
    return generated
