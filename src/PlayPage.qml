import QtQuick
import com.hasselblad.constants
import "qrc:/app/qml/mainmenu" as StockMenu

// 与原厂设置页共用页眉、列表行和开关组件。开关状态来自控制器回读，
// 功能开关以服务和完整函数回读为准。
FocusScope {
    id: root
    objectName: "PlayPageRoot"
    property bool pageActive: false
    readonly property bool masterEnabled: featureController !== null && featureController.master
    property var featureController: null
    property bool requestPending: false
    readonly property bool featureLoaded: featureController !== null && featureController.loaded
    readonly property bool featureBusy: (featureController !== null && featureController.busy) || brightness.busy
    readonly property bool backendAvailable: featureController !== null && featureController.ready &&
                                             !featureController.faulted
    readonly property string statusMessage: !masterEnabled ? "耍起功能已关闭" :
                                            featureController === null ? "对焦加速 buff 控制器尚未就绪" :
                                            !backendAvailable && !featureLoaded ? "对焦加速 buff 条件未满足，暂不可用" :
                                            featureController.statusMessage
    signal backRequested()

    function requestBack() { backRequested() }

    function requestMasterToggle() {
        if (!pageActive || requestPending || featureBusy)
            return false
        return featureController !== null && featureController.setMaster(!masterEnabled)
    }

    function requestAfcToggle() {
        if (!pageActive || !masterEnabled || !backendAvailable || featureBusy) return false
        return featureController.setAfc(!featureController.afcEnabled)
    }
    function requestSpeedToggle() {
        if (!pageActive || !masterEnabled || !backendAvailable || featureBusy) return false
        return featureController.setEnabled(!featureLoaded)
    }

    AutoBrightnessController { id: brightness; masterEnabled: root.masterEnabled; pageActive: root.pageActive }
    function requestBrightnessToggle() {
        if (!pageActive || !masterEnabled || requestPending || featureBusy) return false
        return brightness.toggleFeature()
    }

    Rectangle { anchors.fill: parent; color: Constants.menuBackgroundColor }

    StockMenu.MenuHeader {
        id: header
        objectName: "X2dPlaySettingsHeader"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        showSeparator: !settingsList.atYBeginning
        text: [{ context: "MENUS", text: "耍起功能",
                 color: Constants.settingsMenuHeaderSuffixFontColor }]
        onClose: root.backRequested()
    }

    Flickable {
        id: settingsList
        objectName: "X2dPlaySettingsList"
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        interactive: root.pageActive && contentHeight > height
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: settingsColumn.height

        Column {
            id: settingsColumn
            width: settingsList.width
            spacing: 0

            Item {
                objectName: "X2dPlayMasterSwitchRow"
                width: parent.width
                height: Constants.menuListItemDefaultHeight
                StockMenu.MenuBoolSelector {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    anchors.verticalCenter: parent.verticalCenter
                    text: "耍起功能"
                    value: root.masterEnabled
                    itemEnabled: root.pageActive && !root.featureBusy && !root.requestPending
                    highlighted: masterTouch.pressed
                    showSwitch: true
                    fontWeight: Font.Medium
                }
                MouseArea {
                    id: masterTouch
                    anchors.fill: parent
                    enabled: root.pageActive
                    onClicked: root.requestMasterToggle()
                }
            }

            Rectangle {
                width: parent.width
                height: Constants.menuListDividerHeight
                color: Constants.menuListDividerColor
            }

            Item {
                objectName: "X2dPlayAfcSwitchRow"
                width: parent.width
                height: Constants.menuListItemDefaultHeight
                StockMenu.MenuBoolSelector {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    anchors.verticalCenter: parent.verticalCenter
                    text: "开启 AF-C"
                    value: root.featureController !== null && root.featureController.afcEnabled
                    itemEnabled: root.pageActive && root.masterEnabled && root.backendAvailable &&
                                 !root.featureBusy && !root.requestPending
                    highlighted: afcTouch.pressed
                    showSwitch: true
                    fontWeight: Font.Medium
                }
                MouseArea {
                    id: afcTouch
                    anchors.fill: parent
                    enabled: root.pageActive && root.masterEnabled && root.backendAvailable
                    onClicked: root.requestAfcToggle()
                }
            }


            Item {
                objectName: "X2dPlaySpeedSwitchRow"
                width: parent.width
                height: Constants.menuListItemDefaultHeight
                StockMenu.MenuBoolSelector {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    anchors.verticalCenter: parent.verticalCenter
                    text: "对焦加速 buff"
                    value: root.featureLoaded
                    itemEnabled: root.pageActive && root.masterEnabled && root.backendAvailable &&
                                 !root.featureBusy && !root.requestPending
                    highlighted: speedTouch.pressed
                    showSwitch: true
                    fontWeight: Font.Medium
                }
                MouseArea {
                    id: speedTouch
                    anchors.fill: parent
                    enabled: root.pageActive && root.masterEnabled && root.backendAvailable
                    onClicked: root.requestSpeedToggle()
                }
            }


            Item {
                objectName: "X2dPlayAutoBrightnessSwitchRow"
                width: parent.width
                // Match the stock SwitchDelegate description layout and typography.
                readonly property real topOffset: 16 * 1.6 * Constants.scaleFactorY
                readonly property real bottomOffset: 8 * 1.6 * Constants.scaleFactorY
                height: brightnessColumn.height + topOffset + bottomOffset
                Column {
                    id: brightnessColumn
                    anchors.top: parent.top
                    anchors.topMargin: parent.topOffset
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    spacing: 8 * 1.6 * Constants.scaleFactorY
                    StockMenu.MenuBoolSelector {
                        width: parent.width
                        text: "在亮度菜单中加入自动亮度"
                        value: root.masterEnabled && brightness.availablePreference
                        itemEnabled: root.pageActive && root.masterEnabled && (brightness.ready || brightness.availablePreference) &&
                                     !root.featureBusy && !root.requestPending
                        highlighted: brightnessTouch.pressed
                        showSwitch: true
                        fontWeight: Font.Medium
                    }
                    StockMenu.SettingDescription {
                        id: brightnessHint
                        objectName: "X2dAutoBrightnessHint"
                        width: parent.width
                        text: "请前往显示 → 亮度设置自动亮度"
                        isEnabled: root.masterEnabled
                    }
                }
                MouseArea {
                    id: brightnessTouch
                    anchors.fill: parent
                    enabled: root.pageActive && root.masterEnabled && (brightness.ready || brightness.availablePreference)
                    onClicked: root.requestBrightnessToggle()
                }
            }

            Item { width: parent.width; height: Math.max(0, settingsList.height * 0.35) }
        }
    }

    // 仅左缘明显右滑可返回；纵向手势留给原厂风格的可滚动列表。
    MouseArea {
        id: edgeBack
        objectName: "PlayExitGesture"
        z: 2
        anchors.left: parent.left
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        width: Math.min(64, root.width * 0.12)
        enabled: root.pageActive
        property real startX: 0
        property real startY: 0
        onPressed: (mouse) => { startX = mouse.x; startY = mouse.y }
        onReleased: (mouse) => {
            var dx = mouse.x - startX
            var dy = mouse.y - startY
            if (dx >= Math.max(60, root.width * 0.12) && Math.abs(dy) < root.height * 0.15)
                root.backRequested()
        }
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Back) {
            root.backRequested()
            event.accepted = true
        } else if (event.key === Qt.Key_Up) {
            settingsList.contentY = Math.max(0, settingsList.contentY - 80)
            event.accepted = true
        } else if (event.key === Qt.Key_Down) {
            settingsList.contentY = Math.min(Math.max(0, settingsList.contentHeight - settingsList.height),
                                             settingsList.contentY + 80)
            event.accepted = true
        } else {
            event.accepted = false
        }
    }
}
