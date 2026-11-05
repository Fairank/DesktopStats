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
    color: tone === "window" ? ui.windowTop : tone === "rail" ? ui.railTop
        : tone === "field" ? ui.fieldTop : tone === "popup" ? ui.popupTop
        : tone === "card" ? ui.cardTop : ui.panelTop
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
