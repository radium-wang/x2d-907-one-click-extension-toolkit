import QtQuick

// 扩展项在原厂查表前被本路由消费；原厂十一项仍原样转发。
Item {
    id: root
    objectName: "PlayMenuRoute"
    property bool menuActive: false
    property bool mediaProcessing: false
    property bool stockSubmenuActive: false
    property var featureController: null
    readonly property string extensionName: "x2dPlayUi"
    readonly property bool playShowing: host.showing || prank.showing
    property bool prankEnabled: false
    signal stockRequested(string menuName, string subMenuItem, bool openItem, bool fromShortcut)
    signal blocked()
    signal mainMenuRequested()

    function dispatch(menuName, subMenuItem, openItem, fromShortcut) {
        if (menuName === "x2dPrankIbisUi") {
            if (!prankEnabled || !menuActive || mediaProcessing || stockSubmenuActive || playShowing) blocked()
            else { prank.showing = true; prank.forceActiveFocus() }
            return true
        }
        if (menuName !== extensionName) {
            dismiss()
            stockRequested(menuName, subMenuItem, openItem, fromShortcut)
            return false
        }
        if (!menuActive || mediaProcessing || stockSubmenuActive || playShowing) {
            blocked()
            return true
        }
        if (!host.openPlay())
            blocked()
        return true
    }

    function back() {
        if (prank.showing) { prank.showing = false; mainMenuRequested() }
        else host.back()
    }
    function dismiss() { host.dismiss(); prank.showing = false }
    onMenuActiveChanged: { if (!menuActive) dismiss() }
    onStockSubmenuActiveChanged: { if (stockSubmenuActive) dismiss() }
    onPrankEnabledChanged: { if (!prankEnabled) prank.showing = false }

    PrankIbisPage {
        id: prank
        anchors.fill: parent
        onBackRequested: root.back()
    }

    ResidentPlayHost {
        id: host
        anchors.fill: parent
        menuActive: root.menuActive
        mediaProcessing: root.mediaProcessing
        stockSubmenuActive: root.stockSubmenuActive
        featureController: root.featureController
        onMainMenuRequested: root.mainMenuRequested()
    }
}
