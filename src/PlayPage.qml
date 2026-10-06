import QtQuick
import com.hasselblad.constants
import "qrc:/app/qml/mainmenu" as StockMenu

// 与原厂设置页共用页眉、列表行和开关组件。开关状态来自控制器回读，
// 功能开关以服务和完整函数回读为准。
FocusScope {
    id: root
    objectName: "PlayPageRoot"
    property bool pageActive: false
    property bool freeNoticeVisible: false
    property bool localNoticeAcknowledged: false
    readonly property bool freeNoticeRequired: featureController === null ? !localNoticeAcknowledged :
        featureController.freeNoticeReady && !featureController.freeNoticeSeen && !featureController.freeNoticeAcknowledged
    readonly property bool settingsActive: pageActive && !freeNoticeVisible &&
        (featureController === null || featureController.freeNoticeReady || featureController.freeNoticeAcknowledged)
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

    onPageActiveChanged: updateFreeNotice()
    onFreeNoticeRequiredChanged: updateFreeNotice()
    function updateFreeNotice() { freeNoticeVisible = pageActive && freeNoticeRequired }
    function focusPage() {
        if (!pageActive) return
        if (freeNoticeVisible) freeNotice.forceActiveFocus()
        else root.forceActiveFocus()
    }
    function dismissFreeNotice() {
        localNoticeAcknowledged = true
        if (featureController !== null) featureController.acknowledgeFreeNotice()
        freeNoticeVisible = false
        if (pageActive) root.forceActiveFocus()
    }
    function requestBack() {
        if (freeNoticeVisible) dismissFreeNotice()
        else backRequested()
    }

    function requestMasterToggle() {
        if (!settingsActive || requestPending || featureBusy)
            return false
        return featureController !== null && featureController.setMaster(!masterEnabled)
    }

    function requestAfcToggle() {
        if (!settingsActive || !masterEnabled || !backendAvailable || featureBusy) return false
        return featureController.setAfc(!featureController.afcEnabled)
    }
    function requestSpeedToggle() {
        if (!settingsActive || !masterEnabled || !backendAvailable || featureBusy) return false
        return featureController.setEnabled(!featureLoaded)
    }

    AutoBrightnessController { id: brightness; masterEnabled: root.masterEnabled; pageActive: root.pageActive
        installed: root.featureController !== null && root.featureController.brightnessInstalled }
    function requestBrightnessToggle() {
        if (!settingsActive || !masterEnabled || requestPending || featureBusy) return false
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
        enabled: root.settingsActive
        text: [{ context: "MENUS", text: "耍起功能",
                 color: Constants.settingsMenuHeaderSuffixFontColor }]
        onClose: root.requestBack()
    }

    Flickable {
        id: settingsList
        objectName: "X2dPlaySettingsList"
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        clip: true
        enabled: root.settingsActive
        interactive: root.settingsActive && contentHeight > height
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
                    itemEnabled: root.settingsActive && !root.featureBusy && !root.requestPending
                    highlighted: masterTouch.pressed
                    showSwitch: true
                    fontWeight: Font.Medium
                }
                MouseArea {
                    id: masterTouch
                    anchors.fill: parent
                    enabled: root.settingsActive
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
                visible: root.featureController !== null && root.featureController.afcInstalled
                height: visible ? Constants.menuListItemDefaultHeight : 0
                StockMenu.MenuBoolSelector {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    anchors.verticalCenter: parent.verticalCenter
                    text: "开启 AF-C"
                    value: root.featureController !== null && root.featureController.afcEnabled
                    itemEnabled: root.settingsActive && root.masterEnabled && root.backendAvailable &&
                                 !root.featureBusy && !root.requestPending
                    highlighted: afcTouch.pressed
                    showSwitch: true
                    fontWeight: Font.Medium
                }
                MouseArea {
                    id: afcTouch
                    anchors.fill: parent
                    enabled: root.settingsActive && root.masterEnabled && root.backendAvailable
                    onClicked: root.requestAfcToggle()
                }
            }


            Item {
                objectName: "X2dPlaySpeedSwitchRow"
                width: parent.width
                visible: root.featureController !== null && root.featureController.speedInstalled
                readonly property real topOffset: 16 * 1.6 * Constants.scaleFactorY
                readonly property real bottomOffset: 8 * 1.6 * Constants.scaleFactorY
                height: visible ? speedColumn.height + topOffset + bottomOffset : 0
                Column {
                    id: speedColumn
                    anchors.top: parent.top
                    anchors.topMargin: parent.topOffset
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Constants.settingsMenuSettingLeftMargin
                    anchors.rightMargin: Constants.settingsMenuSettingRightMargin
                    spacing: 8 * 1.6 * Constants.scaleFactorY
                    StockMenu.MenuBoolSelector {
                        width: parent.width
                        text: "对焦加速"
                        value: root.featureLoaded
                        itemEnabled: root.settingsActive && root.masterEnabled && root.backendAvailable &&
                                     !root.featureBusy && !root.requestPending
                        highlighted: speedTouch.pressed
                        showSwitch: true
                        fontWeight: Font.Medium
                    }
                    StockMenu.SettingDescription {
                        objectName: "X2dFocusSpeedHint"
                        width: parent.width
                        text: "对焦加速通过将镜头转速提高三倍实现，不建议老镜头用户开启。"
                        isEnabled: root.masterEnabled && root.backendAvailable
                    }
                }
                MouseArea {
                    id: speedTouch
                    anchors.fill: parent
                    enabled: root.settingsActive && root.masterEnabled && root.backendAvailable
                    onClicked: root.requestSpeedToggle()
                }
            }


            Item {
                objectName: "X2dPlayAutoBrightnessSwitchRow"
                width: parent.width
                visible: root.featureController !== null && root.featureController.brightnessInstalled
                // Match the stock SwitchDelegate description layout and typography.
                readonly property real topOffset: 16 * 1.6 * Constants.scaleFactorY
                readonly property real bottomOffset: 8 * 1.6 * Constants.scaleFactorY
                height: visible ? brightnessColumn.height + topOffset + bottomOffset : 0
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
                        itemEnabled: root.settingsActive && root.masterEnabled && (brightness.ready || brightness.availablePreference) &&
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
                    enabled: root.settingsActive && root.masterEnabled && (brightness.ready || brightness.availablePreference)
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
        enabled: root.settingsActive
        property real startX: 0
        property real startY: 0
        onPressed: (mouse) => { startX = mouse.x; startY = mouse.y }
        onReleased: (mouse) => {
            var dx = mouse.x - startX
            var dy = mouse.y - startY
            if (dx >= Math.max(60, root.width * 0.12) && Math.abs(dy) < root.height * 0.15)
                root.requestBack()
        }
    }

    Keys.onPressed: (event) => {
        if (root.freeNoticeVisible) {
            event.accepted = false
            return
        }
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Back) {
            root.requestBack()
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

    FocusScope {
        id: freeNotice
        objectName: "X2dFreeProjectNotice"
        anchors.fill: parent
        z: 100
        visible: root.pageActive && root.freeNoticeVisible
        enabled: visible
        focus: visible
        onVisibleChanged: { if (visible) forceActiveFocus() }
        Rectangle {
            anchors.fill: parent
            color: Constants.popupFadeoutColor
            opacity: Constants.fadeOutOpacity
        }
        MouseArea { anchors.fill: parent; onClicked: {} }
        Rectangle {
            id: noticeFrame
            objectName: "X2dFreeProjectNoticeFrame"
            anchors.centerIn: parent
            width: Math.min(parent.width - 64 * Constants.scaleFactorX, 760 * Constants.scaleFactorX)
            height: noticeContent.height + 88 * Constants.scaleFactorY
            color: Constants.popupBackgroundColor
            border.width: Constants.popupBorderWidth
            border.color: Constants.popupBorderColor
            Column {
                id: noticeContent
                anchors.centerIn: parent
                width: parent.width - 80 * Constants.scaleFactorX
                spacing: 32 * Constants.scaleFactorY
                Text {
                    objectName: "X2dFreeProjectNoticeMessage"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width, 560 * Constants.scaleFactorX)
                    text: "本项目完全免费，如果有人收你钱了，那你纯是被骗了"
                    color: Constants.popupTextColor
                    font.family: Constants.menuItemFontName
                    font.pixelSize: 32 * Constants.scaleFactor
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
                Rectangle {
                    objectName: "X2dFreeProjectNoticeButton"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width, 560 * Constants.scaleFactorX)
                    height: 80 * Constants.scaleFactorY
                    color: noticeTouch.pressed ? Constants.highlightColor : Constants.popupBackgroundColor
                    border.width: Constants.popupBorderWidth
                    border.color: Constants.popupBorderColor
                    Text {
                        objectName: "X2dFreeProjectNoticeButtonText"
                        anchors.centerIn: parent
                        width: parent.width - 32 * Constants.scaleFactorX
                        text: "好的，我没被骗"
                        color: Constants.popupTextColor
                        font.family: Constants.menuItemFontName
                        font.pixelSize: 30 * Constants.scaleFactor
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                    MouseArea {
                        id: noticeTouch
                        anchors.fill: parent
                        onClicked: root.dismissFreeNotice()
                    }
                }
            }
        }
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space ||
                    event.key === Qt.Key_Escape || event.key === Qt.Key_Back) {
                root.dismissFreeNotice()
                event.accepted = true
            } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Down ||
                       event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                event.accepted = true
            } else {
                // Preserve stock handling of unrelated camera keys, including half press.
                event.accepted = false
            }
        }
    }
}
