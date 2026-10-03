import QtQuick
import com.hasselblad.constants
import "qrc:/app/qml/mainmenu" as StockMenu

// Optional CFV joke page. No backend, switches, or stabilization commands.
FocusScope {
    id: root
    objectName: "PrankIbisPageRoot"
    property bool showing: false
    visible: showing
    enabled: showing
    focus: showing
    signal backRequested()
    Rectangle { anchors.fill: parent; color: Constants.menuBackgroundColor }
    StockMenu.MenuHeader {
        id: header
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        text: [{context: "MENUS", text: "IBIS", color: Constants.settingsMenuHeaderSuffixFontColor}]
        onClose: root.backRequested()
    }
    Text {
        objectName: "PrankIbisMessage"
        anchors.centerIn: parent
        width: parent.width * 0.88
        text: "你被骗了，这里啥也没有\nYou’ve been fooled. There’s nothing here."
        color: "white"; font.pixelSize: 30
        wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
    }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Back) {
            root.backRequested(); event.accepted = true
        } else event.accepted = false
    }
}
