import QtQuick
QtObject {
    id: root
    property var afcMenu: null
    property bool ready: false
    property bool faulted: false
    property bool busy: false
    property bool inFlight: false
    property bool loaded: false
    property bool master: false
    property bool afcEnabled: false
    property bool prankIbis: false
    property int featureMask: 0
    readonly property bool afcInstalled: (featureMask & 1) !== 0
    readonly property bool speedInstalled: (featureMask & 2) !== 0
    readonly property bool brightnessInstalled: (featureMask & 4) !== 0
    property string statusMessage: "正在读取功能状态"
    property var currentRequest: null
    property bool freeNoticeReady: false
    property bool freeNoticeSeen: false
    property bool freeNoticeAcknowledged: false
    property var noticeRequest: null
    function requestFreeNotice(action) {
        if (noticeRequest !== null) return false
        var xhr = new XMLHttpRequest()
        noticeRequest = xhr
        noticeDeadline.restart()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || noticeRequest !== xhr) return
            noticeDeadline.stop()
            noticeRequest = null
            try {
                if (xhr.status !== 200) return
                var state = JSON.parse(xhr.responseText)
                if (state.freeNoticeReady !== true || typeof state.freeNoticeSeen !== "boolean") return
                freeNoticeSeen = state.freeNoticeSeen
                freeNoticeReady = true
            } catch (e) { }
        }
        xhr.open(action === "notice_status" ? "GET" : "POST", "http://127.0.0.1:18763/" + action)
        xhr.send()
        return true
    }
    function acknowledgeFreeNotice() {
        freeNoticeAcknowledged = true
        return requestFreeNotice("notice_seen")
    }
    function pollFreeNotice() {
        if (freeNoticeAcknowledged && !freeNoticeSeen) requestFreeNotice("notice_seen")
        else if (!freeNoticeReady) requestFreeNotice("notice_status")
    }
    function syncAfcMenu() {
        if (afcMenu !== null && afcMenu.ready && !afcMenu.focusPopoverOpen)
            afcMenu.setEnabled(afcInstalled && master && afcEnabled)
    }
    function request(action) {
        if (inFlight) return false
        inFlight = true
        // Quiet polling never changes the UI's operation spinner.
        busy = action !== "status"
        var xhr = new XMLHttpRequest()
        currentRequest = xhr
        requestDeadline.restart()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || currentRequest !== xhr) return
            requestDeadline.stop()
            currentRequest = null
            inFlight = false
            busy = false
            try {
                if (xhr.status !== 200) throw new Error("backend unavailable")
                var state = JSON.parse(xhr.responseText)
                prankIbis = state.prankIbis === true
                featureMask = state.featureMask === undefined ? 7 : Number(state.featureMask)
                if (state.ready === true) {
                    loaded = state.active === true
                    master = state.master === true
                    afcEnabled = state.afc === true
                }
                ready = state.ready === true
                faulted = !ready
                statusMessage = state.message
                syncAfcMenu()
            } catch (e) {
                ready = false; faulted = true
                statusMessage = "服务未就绪；请检查连接或使用恢复原状"
            }
        }
        xhr.open(action === "status" ? "GET" : "POST", "http://127.0.0.1:18763/" + action)
        xhr.send()
        return true
    }
    function setEnabled(value) { return !value || speedInstalled ? request(value ? "enable" : "disable") : false }
    function setAfc(value) { return !value || afcInstalled ? request(value ? "afc_on" : "afc_off") : false }
    function setMaster(value) { return request(value ? "master_on" : "master_off") }
    property Timer poll: Timer {
        interval: 2500; running: true; repeat: true
        onTriggered: { root.request("status"); root.pollFreeNotice() }
    }
    property Timer noticeDeadline: Timer {
        interval: 5000
        onTriggered: {
            var xhr = root.noticeRequest
            root.noticeRequest = null
            if (xhr !== null) xhr.abort()
        }
    }
    property Timer requestDeadline: Timer {
        interval: 15000
        onTriggered: {
            var xhr = root.currentRequest
            root.currentRequest = null; root.inFlight = false; root.busy = false
            if (xhr !== null) xhr.abort()
            root.ready = false; root.faulted = true
            root.statusMessage = "读取超时，尚未确认本次操作结果"
        }
    }
    property Connections afcChanges: Connections {
        target: root.afcMenu
        function onReadyChanged() { root.syncAfcMenu() }
        function onFocusPopoverOpenChanged() { root.syncAfcMenu() }
    }
    Component.onCompleted: { request("status"); pollFreeNotice() }
    Component.onDestruction: {
        var xhr = noticeRequest
        noticeRequest = null
        if (xhr !== null) xhr.abort()
    }
}
