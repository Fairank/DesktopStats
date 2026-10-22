import QtQuick
import QtQuick.Layouts
GlassSurface {
    id: root
    property string title: ""
    property string note: ""
    property int inset: 14
    property int spacing: 10
    default property alias content: box.data
    implicitHeight: box.implicitHeight + inset * 2
    tone: "panel"
    radius: 15
    Theme { id: ui }
    ColumnLayout {
        id: box
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: root.inset
        spacing: root.spacing
        Text {
            visible: root.title.length > 0
            text: root.title; Layout.fillWidth: true
            font.family: ui.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold
            color: ui.ink; wrapMode: Text.WordWrap
        }
        Text {
            visible: root.note.length > 0
            text: root.note; Layout.fillWidth: true
            font.family: ui.fontFamily; font.pixelSize: 10; color: ui.muted
            wrapMode: Text.WordWrap; lineHeight: 1.2
        }
    }
}
