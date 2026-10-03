import QtQuick
import QtQml.Models

// 保留原厂全部项目；X2D 十一项、CFV 十项（无防抖）布局均在末尾追加入口。
DelegateModel {
    id: root
    objectName: "PlayMenuModel"
    property var sourceModel: null
    property Component stockDelegate: null
    property bool supportedLayout: true
    property bool extensionEnabled: true
    property bool prankEnabled: false
    readonly property string prankName: "x2dPrankIbisUi"
    readonly property int prankIndex: prankPresent ? items.count - 2 : -1
    property bool prankPresent: false
    property string playLabel: "耍起功能"
    // 原厂 SVG provider 接受不带 .svg 后缀的 file URL。
    property string playIcon: "file:///system/etc/X2dPlayIcon"
    readonly property string extensionName: "x2dPlayUi"
    readonly property int extensionIndex: extensionPresent ? items.count - 1 : -1
    property bool reconciling: false
    property bool ready: false
    property bool extensionPresent: false
    property string rejectionReason: "not-ready"
    model: sourceModel
    delegate: stockDelegate

    function itemEnabled(ix) {
        if (ix < 0 || ix >= items.count)
            return false
        var entry = items.get(ix)
        if (entry.isUnresolved)
            return extensionPresent && extensionEnabled && (entry.model.menuName === extensionName || entry.model.menuName === prankName)
        return sourceModel !== null && sourceModel.itemEnabled(ix)
    }

    function requestReconcile() {
        if (ready && !reconciling)
            Qt.callLater(reconcile)
    }

    function reconcile() {
        if (!ready || reconciling)
            return
        reconciling = true
        var tail = -1
        var prankTail = -1
        var originals = 0
        var collision = false
        var names = []
        var expected = ["exposureMenu", "focusMenu", "qualityMenu", "cropModesMenu", "flashMenu",
                        "displayMenu", "powerMenu", "storageMenu", "wifiMenu", "generalMenu"]
        for (var i = 0; i < items.count; ++i) {
            var entry = items.get(i)
            if (entry.isUnresolved && entry.model.menuName === extensionName)
                tail = i
            else if (entry.isUnresolved && entry.model.menuName === prankName)
                prankTail = i
            else {
                originals++
                names.push(entry.model.menuName)
                if (entry.model.menuName === extensionName || entry.model.menuName === prankName)
                    collision = true
            }
        }
        var layoutKnown = originals === 10 || originals === 11
        if (originals === 11) expected.push("ibisMenu")
        for (var e = 0; e < expected.length; ++e)
            if (names.indexOf(expected[e]) < 0 || names.indexOf(expected[e]) !== names.lastIndexOf(expected[e]))
                layoutKnown = false
        var reason = sourceModel === null ? "no-source" :
                     !supportedLayout ? "unsupported-layout" :
                     collision ? "reserved-name-collision" :
                     !layoutKnown ? "unknown-stock-layout" : ""
        // Recreate only our reserved unresolved prank row; never mutate stock rows.
        if (prankTail >= 0 && !(reason === "" && prankEnabled && originals === 10 && prankTail === items.count - 2 && tail === items.count - 1)) {
            items.remove(prankTail, 1)
            if (tail > prankTail) tail--
            prankTail = -1
        }
        prankPresent = prankTail >= 0 && reason === "" && prankEnabled && originals === 10 && prankTail === items.count - 2 && tail === items.count - 1
        if (reason !== "") {
            if (tail >= 0)
                items.remove(tail, 1)
            extensionPresent = false
        } else {
            if (tail < 0) {
                items.insert(items.count, {
                    label: playLabel, labelContext: "X2dMenuExtension",
                    iconSrc: playIcon, itemEnabled: extensionEnabled,
                    menuName: extensionName
                })
            } else {
                if (tail !== items.count - 1)
                    items.move(tail, items.count - 1, 1)
                var data = items.get(items.count - 1).model
                data.label = playLabel
                data.iconSrc = playIcon
                data.itemEnabled = extensionEnabled
            }
            extensionPresent = true
            if (prankEnabled && originals === 10 && !prankPresent) {
                items.insert(items.count - 1, {
                    label: "防抖", labelContext: "X2dMenuExtension",
                    iconSrc: "qrc:/icons/ibisMenu",
                    itemEnabled: true, menuName: prankName
                })
                prankPresent = true
            }
        }
        rejectionReason = reason
        reconciling = false
    }

    items.onChanged: requestReconcile()
    property Connections sourceChanges: Connections {
        target: root.sourceModel
        ignoreUnknownSignals: true
        function onDataChanged() { root.requestReconcile() }
    }
    onSourceModelChanged: requestReconcile()
    onSupportedLayoutChanged: requestReconcile()
    onExtensionEnabledChanged: requestReconcile()
    onPrankEnabledChanged: requestReconcile()
    onPlayLabelChanged: requestReconcile()
    onPlayIconChanged: requestReconcile()
    Component.onCompleted: { ready = true; requestReconcile() }
}
