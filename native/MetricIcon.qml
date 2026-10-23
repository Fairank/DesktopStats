import QtQuick
import QtQuick.Window
import "IconData.js" as IconData
import "MetricEffectClock.js" as EffectClock

// Optional decoration. Neither rhythm nor geometry is a sensor scale.
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
    property double previousTick: 0
    property var clockSubscription: null
    readonly property var clockHost: root.Window.window ? root.Window.window.contentItem : null
    readonly property bool effectControlsValid: Number.isFinite(intensity) && intensity >= 0 && intensity <= 1
        && Number.isFinite(speed) && speed >= 0.5 && speed <= 2
    readonly property bool levelValid: typeof level === "number" && Number.isFinite(level) && level >= 0 && level <= 1
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
    readonly property bool exposed: {
        for (let item = root; item; item = item.parent)
            if (!item.visible || item.opacity <= 0) return false
        return true
    }
    readonly property bool animationRunning: exposed && windowVisible && motionEnabled && available
        && levelValid && level > 0 && effectControlsValid && intensity > 0 && resolvedEffect !== "off"
        && (resolvedEffect !== "spin" || name === "fan")
    readonly property real cycleDuration: (resolvedEffect === "heat" ? 2800 : resolvedEffect === "spin" ? 3200
        : resolvedEffect === "pulse" ? 2400 : 2000) / speed
    readonly property real wave: 0.5 - 0.5 * Math.cos(phase * Math.PI * 2)
    readonly property string rgb: "#" + [ink.r, ink.g, ink.b].map(
        channel => Math.round(channel * 255).toString(16).padStart(2, "0")).join("")
    // Immutable upstream fragments are parsed on glyph changes, never on a frame.
    readonly property var glyphParts: IconData.fragment(name).match(/<(?:path|rect|circle|line|polyline|polygon)\b[^>]*\/>/g) || []
    readonly property string pulsePaths: glyphParts.map(part => {
        const match = part.match(/\bd="([^"]*)"/)
        return match ? "M0 0 " + match[1] : ""
    }).join(" ")
    readonly property bool corePulse: ["cpu", "gpu", "memory", "vram", "battery"].includes(name) || !pulsePaths.trim()
    readonly property bool arrowFlow: ["network", "download", "upload", "disk_read", "disk_write"].includes(name)
    readonly property bool outgoing: name === "upload" || name === "disk_read"
        || (name === "network" && metric === "net_upload")
    readonly property int flowDirection: outgoing ? -1 : 1
    readonly property string flowMoving: name === "network" && outgoing
        ? glyphParts.slice(2, 4).join("") : glyphParts.slice(0, 2).join("")
    readonly property string flowFixed: name === "network" && outgoing
        ? glyphParts.slice(0, 2).join("") : glyphParts.slice(2).join("")
    readonly property bool flowActive: animationRunning && resolvedEffect === "flow"
    readonly property bool spinActive: animationRunning && resolvedEffect === "spin" && name === "fan"
    implicitWidth: 18
    implicitHeight: 18
    clip: true

    // Delayed ticks use elapsed time. Clock corrections and long pauses cannot jump a cycle.
    function advanceClock(now) {
        if (!Number.isFinite(now)) return
        if (!animationRunning) {previousTick = now;phase = 0;return}
        const elapsed = Math.max(0, Math.min(136, now - previousTick))
        previousTick = now
        phase = (phase + elapsed / cycleDuration) % 1
    }
    function syncClock() {
        if (clockSubscription && (!clockSubscription.active || !animationRunning
                || !clockSubscription.entry || clockSubscription.entry.host !== clockHost)) {
            EffectClock.unsubscribe(clockSubscription)
            clockSubscription = null
        }
        if (animationRunning && clockHost && !clockSubscription) {
            previousTick = Date.now()
            clockSubscription = EffectClock.subscribe(clockHost, now => root.advanceClock(now))
        }
    }
    onAnimationRunningChanged: {
        if (!animationRunning) phase = 0
        syncClock()
    }
    onClockHostChanged: syncClock()
    Component.onCompleted: syncClock()
    Component.onDestruction: EffectClock.unsubscribe(clockSubscription)
    Icon {
        objectName: "metricIconGlyph"
        anchors.fill: parent; name: root.name; ink: root.ink
        visible: !(root.flowActive && root.arrowFlow) && !root.spinActive
    }
    // Exact Lucide subpaths separated into fixed structure and moving parts.
    component VectorPart: Image {
        property string fragment: ""
        property string viewBox: "0 0 24 24"
        property real strokeWidth: 2
        anchors.fill: parent
        sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
        sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit; smooth: true
        source: "data:image/svg+xml;base64," + Qt.btoa(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + viewBox + '" fill="none" stroke="'
            + root.rgb + '" stroke-opacity="' + root.ink.a
            + '" stroke-width="' + strokeWidth + '" stroke-linecap="round" stroke-linejoin="round">' + fragment + '</svg>')
    }
    Item {
        id: composition
        width: 18; height: 18; anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 18

        Loader {
            objectName: "metricIconFlow"
            anchors.fill: parent
            active: root.flowActive && root.arrowFlow
            sourceComponent: Item {
                VectorPart {objectName:"metricIconFlowStructure";fragment:root.flowFixed}
                Repeater {
                    model: 2
                    Item {
                        id: stream
                        required property int index
                        readonly property real progress: (root.phase + index * 0.5) % 1
                        anchors.fill: parent
                        transform: Translate {y:root.flowDirection * (stream.progress - 0.5) * (0.8 + 1.4 * root.intensity)}
                        opacity: Math.pow(Math.sin(stream.progress * Math.PI), 2)
                        VectorPart {objectName:"metricIconFlowArrow_"+stream.index;fragment:root.flowMoving}
                    }
                }
            }
        }
        Loader {
            anchors.fill: parent; active: root.spinActive
            sourceComponent: Item {
                VectorPart {
                    objectName:"metricIconRotor";fragment:root.glyphParts[0] || ""
                    rotation:root.phase*360
                    opacity:1-0.18*root.intensity*root.wave
                }
                VectorPart {objectName:"metricIconHub";fragment:root.glyphParts.slice(1).join("")}
            }
        }
        Item {
            objectName: "metricIconHeat"
            // Retained paths: no Canvas repaint or raster upload on each frame.
            readonly property int paintCount: 0
            anchors.fill: parent
            visible: root.animationRunning && root.resolvedEffect === "heat"
            Rectangle {
                visible:root.name==="temperature"
                x:7.8;y:12.3;width:2.4;height:2.4;radius:1.2;antialiasing:true
                color:Qt.rgba(root.ink.r,root.ink.g,root.ink.b,.08+.14*root.intensity)
            }
            Repeater {
                model: 2
                Item {
                    id: plume
                    required property int index
                    readonly property real progress: root.animationRunning && root.resolvedEffect === "heat"
                        ? (root.phase + index * 0.5) % 1 : 0
                    readonly property real bend: Math.sin(progress * Math.PI * 2) * (0.3 + root.intensity * 0.55)
                    objectName: "metricIconHeatPlume_" + index
                    width:18;height:18
                    y:-progress*(0.7+root.intensity*1.1)
                    opacity:Math.pow(Math.sin(progress*Math.PI),2)*(0.35+root.intensity*0.5)
                    transform: [
                        Rotation {origin.x:12+plume.index*3;origin.y:10;angle:plume.bend*3},
                        Scale {origin.x:12+plume.index*3;origin.y:10;xScale:1+plume.bend*.12;yScale:1}
                    ]
                    VectorPart {
                        viewBox:"0 0 18 18";strokeWidth:.75
                        fragment:plume.index===0?'<path d="M12 10 C11.1 7.8 13.1 5.2 12 3"/>'
                            :'<path d="M15 10 C14.1 7.8 16.1 5.2 15 3.7"/>'
                    }
                }
            }
        }
        Loader {
            objectName:"metricIconEnergyPath"
            anchors.fill:parent;active:root.flowActive && !root.arrowFlow
            sourceComponent: Item {
                id: energyTrace
                readonly property string route:root.name==="voltage"?"M3.8 13.5 A6 6 0 1 1 14.2 13.5"
                    :root.name==="power"?"M11 4 L6.8 9.2 L10.3 9.2 L7.3 14.5":"M6 6 L12 6 L12 12 L6 12 Z"
                VectorPart {
                    opacity:root.intensity*.16;viewBox:"0 0 18 18";strokeWidth:.6
                    fragment:'<path d="'+energyTrace.route+'"/>'
                }
                Repeater {
                    model:2
                    Item {
                        id: current
                        required property int index
                        readonly property real progress:(root.phase+index*.5)%1
                        PathInterpolator {
                            id:alongRail;progress:current.progress
                            path:Path {PathSvg {path:energyTrace.route}}
                        }
                        Rectangle {
                            width:1.5+root.intensity*.6;height:.7;radius:.35;antialiasing:true
                            x:alongRail.x-width/2;y:alongRail.y-height/2;rotation:alongRail.angle
                            color:root.ink;opacity:Math.pow(Math.sin(current.progress*Math.PI),2)*(.4+root.intensity*.5)
                        }
                    }
                }
            }
        }
        Rectangle {
            id: pulseCore
            objectName:"metricIconPulseCore"
            visible:root.animationRunning && root.resolvedEffect === "pulse" && root.corePulse
            // A small inner core expands while the outer glyph remains stable.
            readonly property real localWave:visible?root.wave:0
            width:root.name==="gpu"?1.2+.6*root.intensity*localWave:2.4+1.8*root.intensity*localWave
            height:root.name==="memory" || root.name==="vram"?2:width
            x:(root.name==="gpu"?6:9)-width/2
            y:(root.name==="gpu" || root.name==="memory" || root.name==="vram"?8.25:9)-height/2
            radius:.65;antialiasing:true
            color:Qt.rgba(root.ink.r,root.ink.g,root.ink.b,root.intensity*(.08+.2*localWave))
            border.width:.6;border.color:Qt.rgba(root.ink.r,root.ink.g,root.ink.b,.35+root.intensity*.35)
        }
        Loader {
            anchors.fill:parent
            active:root.animationRunning && root.resolvedEffect === "pulse" && !root.corePulse
            sourceComponent: Item {
                x:4;y:3;width:10;height:12;clip:true
                VectorPart {
                    objectName:"metricIconPulseStroke"
                    anchors.fill:null;x:-4;y:-3;width:18;height:18
                    fragment:'<path d="'+root.pulsePaths+'"/>'
                    transform:Scale {origin.x:9;origin.y:9;xScale:1+.025*root.intensity*root.wave;yScale:xScale}
                }
            }
        }
    }
}
