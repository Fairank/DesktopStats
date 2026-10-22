import QtQuick
import QtQuick.Layouts
ColumnLayout {
    id: root
    property string title: ""
    default property alias content: body.data
    spacing: 12
    Theme { id: ui }
    Text { visible: root.title.length>0; Layout.fillWidth: true; text: root.title; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
    ColumnLayout { id: body; Layout.fillWidth: true; spacing: 12 }
}
