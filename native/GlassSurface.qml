import QtQuick
import QtQuick.Window
Rectangle {
    id: root
    property string tone: "panel"
    property bool focused: false
    property bool highlighted: false
    Theme { id: ui }
    radius: tone === "window" || tone === "rail" ? 0 : tone === "field" ? ui.controlRadius : 10
    border.color: focused ? ui.accent : tone === "field" ? ui.controlBorder : ui.line
    border.width: tone === "window" || tone === "rail" ? 0 : 1
    gradient: Gradient {
        GradientStop {
            position: 0
            color: root.tone === "window" ? ui.windowTop : root.tone === "rail" ? ui.railTop : root.tone === "field" ? ui.fieldTop : root.tone === "popup" ? ui.popupTop : root.tone === "card" ? ui.cardTop : ui.panelTop
        }
        GradientStop {
            position: 1
            color: root.tone === "window" ? ui.windowBottom : root.tone === "rail" ? ui.railBottom : root.tone === "field" ? ui.fieldBottom : root.tone === "popup" ? ui.popupBottom : root.tone === "card" ? ui.cardBottom : ui.panelBottom
        }
    }
    Rectangle {
        anchors.fill: parent; radius: root.radius
        color: root.highlighted ? ui.hover : "transparent"
    }
    // One edge and one reading surface. No second decorative rim or fake glass.
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        visible: root.focused
        radius: root.radius + 2
        color: "transparent"
        border.width: 1 / Screen.devicePixelRatio
        border.color: ui.accent
    }
}
