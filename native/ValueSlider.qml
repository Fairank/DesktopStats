import QtQuick
import QtQuick.Controls
Slider {
    id: control
    implicitHeight: 32
    implicitWidth: 150
    focusPolicy:Qt.StrongFocus
    hoverEnabled:true
    property real endpointValue: 0
    property bool endpointActive: false
    Binding {
        target: control
        property: "value"
        value: control.endpointValue
        when: control.endpointActive
        restoreMode: Binding.RestoreBindingOrValue
    }
    Keys.onPressed: event => {
        if (!control.enabled || (event.key !== Qt.Key_Home && event.key !== Qt.Key_End)) {
            event.accepted = false
            return
        }
        const limit = event.key === Qt.Key_Home ? control.from : control.to
        if (control.value !== limit) {
            control.endpointValue = limit
            control.endpointActive = true
            control.moved()
            control.endpointActive = false
        }
        event.accepted = true
    }
    leftPadding: 8; rightPadding: 8
    Theme { id: ui }
    background: Rectangle {
        x: control.leftPadding; y: (control.height-height)/2
        width: control.availableWidth; height: 4; radius: 2
        color: control.enabled?(ui.dark ? "#525660" : "#d3d5dc"):(ui.dark?"#42464e":"#dddfe5")
        Rectangle { width: control.visualPosition*parent.width; height: parent.height; radius: 2; color:control.enabled?ui.accent:(ui.dark?"#777c86":"#a3a8b3"); x: control.mirrored ? parent.width-width : 0 }
    }
    handle: Rectangle {
        x: control.leftPadding+control.visualPosition*(control.availableWidth-width)
        y: (control.height-height)/2; width: 16; height: 16; radius: 8
        color:control.enabled?"#ffffff":(ui.dark?"#858a94":"#c7cbd3"); border.color: control.enabled && control.activeFocus ? ui.accent : "#28000000"; antialiasing: true
        Rectangle { visible: control.enabled && control.activeFocus; anchors.fill: parent; anchors.margins: -2; color: "transparent"; radius: 10; border.color: "#602885ff" }
    }
}
