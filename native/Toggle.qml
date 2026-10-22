import QtQuick
import QtQuick.Controls
Switch {
    id: control
    Theme { id: ui }
    implicitWidth: 40
    implicitHeight: 30
    padding: 0
    indicator: Rectangle {
        width: 36; height: 22; x: 2; y: 4; radius: 11
        color: control.checked ? ui.accentFill : ui.dark ? "#646d7b" : "#a4aebb"
        Rectangle {
            width: 18; height: 18; radius: 9; y: 2; x: control.checked ? 16 : 2
            color: "#fcfdff"
            Behavior on x { NumberAnimation { duration: ui.motionAllowed ? 110 : 0 } }
        }
        Rectangle { anchors.fill: parent; anchors.margins: -3; radius: 14; color: "transparent"; border.width: 1.5; border.color: ui.accent; visible: control.activeFocus }
    }
}
