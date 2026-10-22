import QtQuick
import QtQuick.Layouts
ColumnLayout {
    id: root
    property string label: ""
    default property alias controls: body.data
    spacing: 6
    Theme { id: ui }
    Text {
        Layout.fillWidth: true; text: root.label
        color: ui.muted; font.family: ui.fontFamily; font.pixelSize: ui.captionSize; font.weight: Font.Normal
        wrapMode: Text.WordWrap
    }
    ColumnLayout { id: body; Layout.fillWidth: true; spacing: 0 }
}
