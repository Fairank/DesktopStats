import QtQuick
import QtQuick.Controls
Button {
    id: control
    property bool accent: false
    property bool quiet: false
    hoverEnabled: true
    Theme { id: ui }
    font.family: ui.fontFamily
    font.pixelSize: ui.bodySize
    font.weight: Font.Medium
    padding: 4
    leftPadding: 12
    rightPadding: 12
    implicitHeight: ui.controlHeight
    Accessible.name: text
    contentItem: Text {
        text: control.text; font: control.font
        color: !control.enabled ? ui.disabledText : control.accent ? "white" : ui.ink
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Item {
        opacity: control.enabled ? 1 : .45
        GlassSurface {
            anchors.fill: parent; tone: "field"; radius: ui.controlRadius
            visible: !control.accent && !control.quiet && !control.checked
            highlighted: control.hovered || control.down
        }
        Rectangle {
            anchors.fill: parent; radius: ui.controlRadius
            visible: !control.accent && (control.checked || control.quiet && (control.hovered || control.down))
            color: control.checked ? ui.selection : control.down ? ui.pressed : ui.hover
        }
        Rectangle {
            anchors.fill: parent; radius: ui.controlRadius; visible: control.accent
            color: control.down ? ui.accentPressed : control.hovered ? ui.accentHover : ui.accentFill
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: -2; radius: ui.controlRadius + 2; color: "transparent"
            border.color: ui.accent; border.width: 1; visible: control.visualFocus
        }
    }
}
