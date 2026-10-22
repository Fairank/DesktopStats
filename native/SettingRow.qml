import QtQuick
import QtQuick.Layouts
Item {
    id: root
    property string label
    property string note: ""
    property bool separator: false
    default property alias controls: controls.data
    implicitHeight: Math.max(40, caption.implicitHeight + 12, controls.implicitHeight + 4)
    Theme { id: ui }
    Column {
        id: caption
        anchors.left: parent.left; anchors.right: controls.left; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter
        spacing: 3
        Text { width: parent.width; text: root.label; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: ui.bodySize; wrapMode: Text.WordWrap }
        Text { width: parent.width; text: root.note; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: ui.captionSize; wrapMode: Text.WordWrap; visible: text.length > 0 }
    }
    Row { id: controls; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 8 }
    Rectangle { visible: root.separator; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: ui.line }
}
