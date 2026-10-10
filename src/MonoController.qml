import QtQuick

// The camera-service backend is the authority. The toggle is unavailable
// until both preview and every enabled photo encoder have reported readiness.
QtObject {
    id: root
    property bool pageActive: false
    property bool masterEnabled: false
    property bool ready: false
    property bool selected: false
    property bool effective: false
    property bool busy: false
    property bool inFlight: false
    property string state: "connecting"
    property var pending: null
    property int sequence: 0

    property Timer deadline: Timer {
        interval: 1500
        onTriggered: {
            root.sequence++
            var request = root.pending
            root.pending = null
            root.inFlight = false
            root.busy = false
            root.ready = false
            root.state = "backend_unavailable"
            if (request) request.abort()
        }
    }

    function request(action) {
        if (inFlight) {
            if (action === "status" || busy) return false
            sequence++
            if (pending) pending.abort()
            pending = null
            deadline.stop()
            inFlight = false
        }
        if (action !== "status" && (!pageActive || !masterEnabled ||
                                    (action === "enable" && !ready))) return false
        var serial = ++sequence
        var xhr = new XMLHttpRequest()
        pending = xhr
        inFlight = true
        busy = action !== "status"
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || serial !== root.sequence) return
            root.deadline.stop()
            root.pending = null
            root.inFlight = false
            root.busy = false
            try {
                if (xhr.status !== 200) throw new Error("mono backend unavailable")
                var reply = JSON.parse(xhr.responseText)
                root.ready = reply.ok === true && reply.available === true &&
                             reply.previewReady === true &&
                             reply.jpegReady === true && reply.heifReady === true
                root.selected = reply.selected === true
                root.effective = root.ready && reply.effective === true
                root.state = reply.state || "backend_unavailable"
            } catch (error) {
                root.ready = false
                root.state = "backend_unavailable"
            }
        }
        xhr.open(action === "status" ? "GET" : "POST",
                 "http://127.0.0.1:18766/mono/" + action)
        deadline.restart()
        xhr.send()
        return true
    }

    function toggle() { return request(selected ? "disable" : "enable") }
    property Timer poll: Timer {
        interval: root.pageActive ? 500 : 2500
        running: true
        repeat: true
        onTriggered: root.request("status")
    }
    Component.onCompleted: request("status")
    Component.onDestruction: {
        sequence++
        if (pending) pending.abort()
    }
}
