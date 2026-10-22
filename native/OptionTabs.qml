import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: root
    property var options: []
    property string value: ""
    signal picked(string selected)
    implicitWidth: tabs.implicitWidth+6
    implicitHeight: 36
    Theme { id: ui }
    Rectangle { anchors.fill: parent; radius: 9; color: ui.segment }
    RowLayout {
        id: tabs
        anchors.fill: parent; anchors.margins: 3; spacing: 2
        Repeater {
            model: root.options
            ToolButton {
                id: tab
                required property var modelData
                objectName: modelData.objectName || ""
                Layout.fillWidth:true;Layout.minimumWidth:0
                implicitWidth: Math.max(68,caption.implicitWidth+22); implicitHeight: 30
                focusPolicy: Qt.StrongFocus
                onClicked: root.picked(modelData.id)
                Accessible.name: modelData.label
                contentItem: Text { id: caption; text: tab.modelData.label; color: root.value===tab.modelData.id ? ui.ink : ui.muted; font.family: ui.fontFamily; font.pixelSize: ui.captionSize; font.weight: root.value===tab.modelData.id ? Font.DemiBold : Font.Normal; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter;elide:Text.ElideRight }
                ToolTip.visible:hovered && caption.truncated;ToolTip.text:modelData.label;ToolTip.delay:600
                background: Rectangle { radius: 7; color: root.value===tab.modelData.id ? ui.segmentSelected : tab.hovered ? ui.hover : "transparent"; border.color: tab.activeFocus ? ui.accent : "transparent" }
            }
        }
    }
}
