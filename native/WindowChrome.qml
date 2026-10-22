import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: root
    required property var targetWindow
    property string titleText: "Desktop Stats"
    readonly property bool maximized: targetWindow.visibility === Window.Maximized
    Theme { id: ui }
    function toggleMaximized() {
        if (maximized) targetWindow.showNormal()
        else targetWindow.showMaximized()
    }
    Rectangle {
        width: parent.width; height: 34
        color: ui.windowTop
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: ui.line }
        MouseArea {
            objectName: "windowTitleDrag"
            anchors.left: parent.left; anchors.right: windowButtons.left
            height: parent.height; acceptedButtons: Qt.LeftButton
            onPressed: root.targetWindow.startSystemMove()
            onDoubleClicked: root.toggleMaximized()
        }
        Text {
            anchors.left: parent.left; anchors.leftMargin: 18; anchors.verticalCenter: parent.verticalCenter
            text: root.titleText; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11
        }
        Row {
            id: windowButtons
            anchors.right: parent.right
            Repeater {
                model: ["minimize", "maximize", "close"]
                ToolButton {
                    id: button
                    required property string modelData
                    objectName: "window_" + modelData
                    width: 46; height: 34; padding: 0; focusPolicy: Qt.TabFocus
                    readonly property string actionLabel: ui.t(modelData === "close" ? "关闭" : modelData === "minimize" ? "最小化" : root.maximized ? "还原" : "最大化")
                    Accessible.name: actionLabel
                    ToolTip.visible: hovered; ToolTip.delay: 700; ToolTip.text: actionLabel
                    onClicked: {
                        if (modelData === "close") root.targetWindow.close()
                        else if (modelData === "minimize") root.targetWindow.showMinimized()
                        else root.toggleMaximized()
                    }
                    background: Rectangle {
                        color: button.hovered || button.down ? (button.modelData === "close" ? "#c42b1c" : ui.hover) : "transparent"
                        Rectangle { anchors.fill: parent; anchors.margins: 3; color: "transparent"; radius: 3; border.color: ui.accent; visible: button.activeFocus }
                    }
                    contentItem: Item {
                        readonly property color ink: (button.hovered || button.down) && button.modelData === "close" ? "white" : ui.ink
                        Icon { anchors.centerIn: parent; width: 15; height: 15; name: "close"; ink: parent.ink; visible: button.modelData === "close" }
                        Rectangle { anchors.centerIn: parent; width: 10; height: 1; color: parent.ink; visible: button.modelData === "minimize" }
                        Rectangle { anchors.centerIn: parent; width: 10; height: 9; color: "transparent"; border.color: parent.ink; visible: button.modelData === "maximize" }
                        Rectangle { x: parent.width/2 - 2; y: parent.height/2 - 6; width: 9; height: 8; color: "transparent"; border.color: parent.ink; visible: button.modelData === "maximize" && root.maximized }
                    }
                }
            }
        }
    }
    Repeater {
        model: [Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge,
                Qt.LeftEdge|Qt.TopEdge, Qt.RightEdge|Qt.TopEdge,
                Qt.LeftEdge|Qt.BottomEdge, Qt.RightEdge|Qt.BottomEdge]
        MouseArea {
            required property int modelData
            readonly property bool leftEdge: !!(modelData & Qt.LeftEdge)
            readonly property bool rightEdge: !!(modelData & Qt.RightEdge)
            readonly property bool topEdge: !!(modelData & Qt.TopEdge)
            readonly property bool bottomEdge: !!(modelData & Qt.BottomEdge)
            readonly property bool corner: (leftEdge || rightEdge) && (topEdge || bottomEdge)
            objectName: "windowResize_" + modelData
            visible: !root.maximized
            z: 1000
            x: rightEdge ? root.width - width : corner || leftEdge ? 0 : 7
            y: bottomEdge ? root.height - height : corner || topEdge ? 0 : 34
            width: corner || leftEdge || rightEdge ? 7 : Math.max(0, root.width - 14)
            height: corner || topEdge || bottomEdge ? 7 : Math.max(0, root.height - 41)
            cursorShape: corner ? (leftEdge === topEdge ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor) : leftEdge || rightEdge ? Qt.SizeHorCursor : Qt.SizeVerCursor
            acceptedButtons: Qt.LeftButton
            onPressed: root.targetWindow.startSystemResize(modelData)
        }
    }
}
