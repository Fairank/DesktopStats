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
    property real intensity: 0.5
    property real speed: 1
    property real phase: 0
    readonly property bool effectControlsValid: Number.isFinite(intensity) && intensity >= 0 && intensity <= 1
        && Number.isFinite(speed) && speed >= 0.5 && speed <= 2
    readonly property bool levelValid: typeof level === "number" && Number.isFinite(level)
        && level >= 0 && level <= 1
    readonly property string resolvedEffect: {
        if (["heat", "flow", "spin", "pulse"].includes(effect)) return effect
        if (effect !== "auto") return "off"
        if (/(?:_temp|_temperature)$/.test(metric)) return "heat"
        if (/(?:^|_)fan_(?:rpm|percent)$/.test(metric)) return "spin"
        if (/^(?:net_(?:download|upload)|disk_(?:read|write))$/.test(metric)
                || /_(?:power|current|voltage|watts)$/.test(metric) || metric === "voltage") return "flow"
        if (/_(?:usage|percent|frequency)$/.test(metric)) return "pulse"
        return "off"
    }
    readonly property bool windowVisible: root.Window.window !== null
        && root.Window.window.visible && root.Window.window.visibility !== Window.Minimized
    readonly property bool animationRunning: visible && windowVisible && motionEnabled
        && available && levelValid && level > 0 && effectControlsValid && intensity > 0 && resolvedEffect !== "off"
    readonly property real cycleDuration: (resolvedEffect === "spin" ? 2400 : 1800) / speed
    readonly property bool outgoing: ["upload", "disk_write"].includes(name)
        || /(?:_upload|_write)$/.test(metric)
    implicitWidth: 18
    implicitHeight: 18
    clip: true
    onAnimationRunningChanged: if (!animationRunning) phase = 0
    onInkChanged: heatStroke.requestPaint()

    // One scalar clock, capped below 30 Hz. SVGs and heat paths are not rebuilt per frame.
    Timer {
        objectName: "metricIconAnimation"
        interval: 34; repeat: true; running: root.animationRunning
        onTriggered: root.phase = (root.phase + interval / root.cycleDuration) % 1
    }
    Icon {
        objectName: "metricIconGlyph"
        anchors.fill: parent; name: root.name; ink: root.ink
        rotation: root.animationRunning && root.resolvedEffect === "spin" ? root.phase * 360 : 0
        opacity: root.animationRunning && root.resolvedEffect === "pulse"
            ? 1 - (0.08 + 0.22 * root.intensity) * (0.5 - 0.5 * Math.cos(root.phase * Math.PI * 2))
            : root.animationRunning && root.resolvedEffect === "spin"
                ? 1 - 0.18 * root.intensity * (0.5 - 0.5 * Math.cos(root.phase * Math.PI * 2))
            : root.animationRunning && root.resolvedEffect === "flow" ? 1 - 0.35 * root.intensity : 1
    }
    // A moving window reveals the actual glyph's strokes, rather than adding floating particles.
    Item {
        id: flowScan
        objectName: "metricIconFlow"
        visible: root.animationRunning && root.resolvedEffect === "flow"
        width: root.width; height: 2 + 3 * root.intensity; clip: true
        y: (root.outgoing ? 1 - root.phase : root.phase) * (root.height + height) - height
        Loader {
            width: root.width; height: root.height; y: -flowScan.y
            active: root.resolvedEffect === "flow"
            sourceComponent: Icon {
                objectName: "metricIconFlowGlyph"
                name: root.name; ink: root.ink
            }
        }
    }
    Canvas {
        id: heatStroke
        objectName: "metricIconHeat"
        visible: root.animationRunning && root.resolvedEffect === "heat"
        property int paintCount: 0
        width: root.width * 0.36; height: root.height * 0.5
        x: root.width - width; y: root.height * 0.05 + Math.sin(root.phase * Math.PI * 2) * root.height * 0.035
        opacity: (0.25 + 0.45 * root.intensity) * (0.65 + 0.35 * Math.sin(root.phase * Math.PI * 2))
        antialiasing: true
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()
        onPaint: {
            paintCount++
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = root.ink; ctx.lineWidth = 0.85; ctx.lineCap = "round"
            for (let index = 0; index < 2; index++) {
                const x = 1.2 + index * (width - 2.4)
                ctx.beginPath(); ctx.moveTo(x, height - 1)
                ctx.bezierCurveTo(x - 1, height * 0.65, x + 1, height * 0.35, x, 1)
                ctx.stroke()
            }
        }
    }
}
