import QtQuick
import com.hasselblad.types
import com.hasselblad.proxies
import com.hasselblad.uiproxies
import "qrc:/app/qml/components" as StockComponents

// Runtime model experiment. This never writes /proc/mem or camera files.
// It is deliberately fail-closed until an exact two-item stock model and
// CameraUI.canChangeAfc are visible through ControlDrawer.
Item {
    id: root
    objectName: "X2dAfcMenuController"
    visible: false
    width: 0
    height: 0

    property var controlViewModel: null
    property bool focusPopoverOpen: false
    property var focusPopover: null
    property var uiRoot: null
    property var controlRoot: null
    property var popupLoader: null
    property url extendedPopupSource: "file:///system/etc/X2dFocusModePopup.qml"
    property string focusTitle: "对焦模式"
    property string afsCaption: "单次自动对焦"
    property string mfCaption: "手动对焦"
    property var stockAfs: null
    property var stockMf: null
    property var afcItem: null
    property var extendedAfs: null
    property var extendedMf: null
    property var visualBindings: []
    property bool loaded: false
    property bool busy: false
    property bool faulted: false
    property string statusMessage: "AF-C 尚未开启"
    readonly property bool ready: !faulted && controlViewModel !== null && CameraUI.canChangeAfc
    signal result(bool loaded, bool busy, string message)

    Component {
        id: afsFactory
        StockComponents.FocusModeListItem {
            focusMode: HblmTypes.E_FocusModes_Afs
            valid: root.stockAfs ? root.stockAfs.valid : false
            icon: "image://svg/ic_x2d2_focus_control_AF-S"
            text: root.afsCaption
        }
    }
    Component {
        id: mfFactory
        StockComponents.FocusModeListItem {
            focusMode: HblmTypes.E_FocusModes_Man
            valid: root.stockMf ? root.stockMf.valid : false
            icon: "image://svg/ic_x2d2_focus_control_MF"
            text: root.mfCaption
        }
    }
    Component {
        id: afcFactory
        StockComponents.FocusModeListItem {
            focusMode: HblmTypes.E_FocusModes_Afc
            valid: CameraUI.canChangeAfc
            icon: "image://svg/ic_x2d2_focus_control_AF-C"
            text: "连续自动对焦"
        }
    }

    function modeName(mode) {
        if (mode === HblmTypes.E_FocusModes_Afs) return "AF-S"
        if (mode === HblmTypes.E_FocusModes_Afc) return "AF-C"
        if (mode === HblmTypes.E_FocusModes_Man) return "MF"
        return ""
    }
    function modeIcon(mode, liveview) {
        var name = modeName(mode)
        if (!name) return ""
        return "image://svg/ic_x2d2_" + (liveview ? "liveview_" : "focus_control_") + name +
                (CameraUI.focusModeSelectable ? "" : liveview ? "_disable" : "_disabled")
    }
    // Binding restores the original binding (including future mode/lens
    // changes), rather than saving a stale icon or visibility value.
    Component {
        id: controlBindingFactory
        Item {
            id: controlBinding
            property var item: null
            Binding {
                target: controlBinding.item
                property: "symbol"
                value: root.modeIcon(Camera.focus_mode, false) || root.controlViewModel.focusModeIcon
                when: root.loaded && controlBinding.item !== null
                restoreMode: Binding.RestoreBindingOrValue
            }
        }
    }
    Component {
        id: liveviewBindingFactory
        Item {
            id: liveBinding
            property var item: null
            property var icon: item ? item.children[0] : null
            Binding {
                target: liveBinding.icon; property: "source"
                value: liveBinding.item ? (root.modeIcon(liveBinding.item.viewModel.focusMode, true) ||
                                           liveBinding.item.viewModel.focusModeIcon) : ""
                when: root.loaded && liveBinding.item !== null
                restoreMode: Binding.RestoreBindingOrValue
            }
            Binding {
                target: liveBinding.icon; property: "visible"
                value: liveBinding.item ? liveBinding.item.viewModel.canShowFocusMode : false
                when: root.loaded && liveBinding.item !== null
                restoreMode: Binding.RestoreBindingOrValue
            }
            Binding {
                target: liveBinding.item; property: "visible"
                value: liveBinding.item !== null && (liveBinding.item.viewModel.canShowFocusMode || liveBinding.item.showIndicators) &&
                       !liveBinding.item.parent.overlayOff && liveBinding.item.parent.infoVisible &&
                       !liveBinding.item.parent.showOnlyBottomRow
                when: root.loaded && liveBinding.item !== null
                restoreMode: Binding.RestoreBindingOrValue
            }
        }
    }
    function bindVisual(item, factory) {
        for (var i = 0; i < visualBindings.length; ++i)
            if (visualBindings[i].item === item) return
        var binding = factory.createObject(root, {item: item})
        if (binding) visualBindings.push(binding)
    }
    function discover(item, controls) {
        if (!item) return
        if (controls && item.objectName === "ControlScreen_popupLoader") popupLoader = item
        if (controls && item.objectName === "ControlScreen_afControl" && typeof item.symbol !== "undefined")
            bindVisual(item, controlBindingFactory)
        if (item.objectName === "FocusIndicator_root" && item.viewModel && item.children.length >= 2 &&
                typeof item.children[0].source !== "undefined" && item.parent &&
                typeof item.parent.overlayOff === "boolean")
            bindVisual(item, liveviewBindingFactory)
        for (var i = 0; i < item.children.length; ++i) discover(item.children[i], controls)
    }
    function refreshUi() {
        if (!loaded) return
        discover(uiRoot, false)
        discover(controlRoot || uiRoot, true)
        routeFocusPopup()
    }
    function routeFocusPopup() {
        if (!loaded || !popupLoader || !controlViewModel || controlViewModel.mainState !== "focus_mode") return
        var source = popupLoader.source.toString()
        if (source.indexOf("/popups/PopoverFocusMode.qml") !== -1)
            popupLoader.source = extendedPopupSource
    }
    Connections {
        target: root.popupLoader
        function onSourceChanged() { root.routeFocusPopup() }
        function onLoaded() {
            if (root.loaded && root.popupLoader.source.toString() === root.extendedPopupSource.toString())
                root.popupLoader.item.heading = root.focusTitle
        }
    }
    Timer { interval: 1000; repeat: true; running: root.loaded; onTriggered: root.refreshUi() }
    function clearExtendedItems() {
        // Keep Binding objects alive while their `when` becomes false. Qt
        // restores the saved binding then; destroying one immediately after
        // changing loaded can discard that restoration on Qt 6.4.1.
        popupLoader = null
        if (extendedAfs) extendedAfs.destroy()
        if (afcItem) afcItem.destroy()
        if (extendedMf) extendedMf.destroy()
        extendedAfs = null; afcItem = null; extendedMf = null
    }

    function sameModel(items) {
        if (!controlViewModel || controlViewModel.focusModeModel.length !== items.length)
            return false
        for (var i = 0; i < items.length; ++i) {
            if (controlViewModel.focusModeModel[i] !== items[i])
                return false
        }
        return true
    }

    function replaceModel(items) {
        // A list property is mutable in QML. Read back every entry: a silent
        // append/conversion must never be reported as a successful switch.
        controlViewModel.focusModeModel.length = 0
        for (var i = 0; i < items.length; ++i)
            controlViewModel.focusModeModel.push(items[i])
        return sameModel(items)
    }

    function publish(message) {
        statusMessage = message
        result(loaded, busy, message)
    }

    function setEnabled(enable) {
        if (busy || faulted)
            return false
        if (enable === loaded) {
            publish(loaded ? "AF-C 菜单扩展已加载" : "AF-C 尚未开启")
            return true
        }
        if (enable && !ready) {
            publish("AF-C 条件未满足，未加载")
            return false
        }
        if (focusPopoverOpen) {
            publish("请先关闭对焦模式弹窗")
            return false
        }
        if (!enable && Camera.focus_mode === HblmTypes.E_FocusModes_Afc) {
            publish("请先切换到 AF-S 或 MF，再关闭耍起功能")
            return false
        }
        if (!enable && !sameModel([extendedAfs, afcItem, extendedMf])) {
            publish("对焦列表被其他代码修改，拒绝卸载")
            return false
        }

        busy = true
        var didMutate = false
        try {
            if (enable) {
                var model = controlViewModel.focusModeModel
                if (model.length !== 2 ||
                    model[0].focusMode !== HblmTypes.E_FocusModes_Afs ||
                    model[1].focusMode !== HblmTypes.E_FocusModes_Man) {
                    throw new Error("原厂对焦列表不是预期的 AF-S/MF 两项")
                }
                stockAfs = model[0]
                stockMf = model[1]
                // Never rewrite stock captions/icons; their validity bindings
                // and translation context remain available for exact restore.
                extendedAfs = afsFactory.createObject(root)
                afcItem = afcFactory.createObject(root)
                extendedMf = mfFactory.createObject(root)
                didMutate = true
                if (!extendedAfs || !afcItem || !extendedMf ||
                        !replaceModel([extendedAfs, afcItem, extendedMf]))
                    throw new Error("AF-C 条目插入后回读不一致")
                loaded = true
                refreshUi()
                publish("AF-C 菜单扩展已加载")
            } else {
                didMutate = true
                if (!replaceModel([stockAfs, stockMf]))
                    throw new Error("恢复原厂两项后回读不一致")
                loaded = false
                clearExtendedItems()
                publish("AF-C 尚未开启")
            }
            return true
        } catch (error) {
            // Keep the AF-C object alive if the list still references it.
            // A failed rollback is reported, never shown as OFF.
            if (didMutate && stockAfs && stockMf) {
                try {
                    if (replaceModel([stockAfs, stockMf])) {
                        loaded = false
                        clearExtendedItems()
                    } else {
                        faulted = true
                    }
                } catch (recoveryError) {
                    faulted = true
                }
            }
            publish(faulted ? "对焦列表状态不确定；请重启 GUI：" + error :
                    didMutate ? "切换未生效，已恢复原厂列表：" + error :
                                "未加载：" + error)
            return false
        } finally {
            busy = false
            result(loaded, busy, statusMessage)
        }
    }
}
