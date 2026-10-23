import QtQuick
import QtQuick.Window

// Optional decoration. Motion and speed are visual choices, never a sensor scale.
Item {
    id: root
    property string name: "sensors"
    property string metric: ""
    property color ink: "#69788c"
    property string effect: "off"
    property var level: null
    property bool available: false
    property bool motionEnabled: false
    property real phase: 0
    readonly property bool levelValid: typeof level === "number" && Number.isFinite(level)
        && level >= 0 && level <= 1
    readonly property string resolvedEffect: {
        if (["heat", "flow", "spin", "pulse"].includes(effect)) return effect
        if (effect !== "auto") return "off"
        if (/(?:_temp|_temperature)$/.test(metric)) return "heat"
        if (/(?:_fan_rpm|^fan_rpm)$/.test(metric)) return "spin"
        if (/^(?:net_(?:download|upload)|disk_(?:read|write))$/.test(metric)
                || /_(?:power|current|voltage|watts)$/.test(metric) || metric === "voltage") return "flow"
        if (/_(?:usage|percent|frequency)$/.test(metric)) return "pulse"
        return "off"
    }
    readonly property bool windowVisible: root.Window.window !== null
        && root.Window.window.visible && root.Window.window.visibility !== Window.Minimized
    readonly property bool animationRunning: visible && windowVisible && motionEnabled
        && available && levelValid && level > 0 && resolvedEffect !== "off"
    implicitWidth: 18
    implicitHeight: 18
    clip: true
    onAnimationRunningChanged: if (!animationRunning) phase = 0
    onInkChanged: heatStroke.requestPaint()

    NumberAnimation {
        objectName: "metricIconAnimation"
        target: root; property: "phase"; from: 0; to: 1
        duration: root.resolvedEffect === "spin" ? 2400 : 1800
        loops: Animation.Infinite; running: root.animationRunning
    }
    Icon {
        objectName: "metricIconGlyph"
        anchors.fill: parent; name: root.name; ink: root.ink
        rotation: root.animationRunning && root.resolvedEffect === "spin" ? root.phase * 360 : 0
        opacity: root.animationRunning && root.resolvedEffect === "pulse"
            ? 0.8 + 0.2 * Math.sin(root.phase * Math.PI) : 1
    }
    Rectangle {
        objectName: "metricIconPulse"
        visible: root.animationRunning && root.resolvedEffect === "pulse"
        anchors.centerIn: parent; width: parent.width - 2; height: parent.height - 2
        radius: width / 2; color: "transparent"; border.width: 0.8; border.color: root.ink
        opacity: (1 - root.phase) * 0.25; scale: 0.65 + 0.35 * root.phase
    }
    Rectangle {
        objectName: "metricIconFlow"
        visible: root.animationRunning && root.resolvedEffect === "flow"
        width: 2.2; height: 2.2; radius: 1.1; color: root.ink
        x: 1 + root.phase * Math.max(0, root.width - width - 2)
        y: root.height * (0.7 - root.phase * 0.4)
        opacity: Math.sin(root.phase * Math.PI) * 0.85
    }
    Canvas {
        id: heatStroke
        objectName: "metricIconHeat"
        visible: root.animationRunning && root.resolvedEffect === "heat"
        width: root.width * 0.35; height: root.height * 0.45
        x: root.width - width; y: root.height * (0.2 - root.phase * 0.12)
        opacity: Math.sin(root.phase * Math.PI) * 0.8
        antialiasing: true
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = root.ink; ctx.lineWidth = 0.9; ctx.lineCap = "round"
            for (let index = 0; index < 2; index++) {
                const x = 1.2 + index * (width - 2.4)
                ctx.beginPath(); ctx.moveTo(x, height - 1)
                ctx.bezierCurveTo(x - 1, height * 0.65, x + 1, height * 0.35, x, 1)
                ctx.stroke()
            }
        }
    }
}
