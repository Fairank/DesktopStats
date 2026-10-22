import QtQuick
import QtQuick.Controls
ToolButton {
    id: control
    property string symbol: "plus"
    property string label: ""
    property bool danger: false
    implicitWidth: 32; implicitHeight: 32
    focusPolicy: Qt.StrongFocus
    Theme { id: ui }
    Accessible.name: label
    contentItem: Icon {
        name: control.symbol; width: 16; height: 16
        ink: control.danger && (control.hovered || control.down) ? (ui.dark ? "#ff8c8c" : "#d44343") : control.hovered ? ui.ink : ui.muted
        opacity: control.enabled ? 1 : .35
    }
    background: GlassSurface {
        radius: 8; tone: "field"; focused: control.activeFocus
        visible: control.hovered || control.activeFocus || control.down
        highlighted: control.down; opacity: control.down ? 1 : .75
    }
    ToolTip {
        visible: control.hovered || control.activeFocus
        text: control.label; delay: 400; padding: 8
        font.family: ui.fontFamily; font.pixelSize: 12
        contentItem: Text { text: control.label; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 12 }
        background: GlassSurface { tone: "popup"; radius: 9 }
    }
}
