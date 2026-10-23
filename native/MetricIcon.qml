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
    property string automaticEffect: ""
    property var level: null
    property var hardwareState: ({})
    property bool available: false
    property bool motionEnabled: false
    property real intensity: 0.5
    property real speed: 1
    property url warmAtlasSource: Qt.resolvedUrl("../assets/metric-motion/arc-warm.png")
    property url blueAtlasSource: Qt.resolvedUrl("../assets/metric-motion/arc-blue.png")
    readonly property int atlasFrameCount: 48
    readonly property int atlasStageCount: 10
    property real phase: 0
    property real displayedLevel: 0
    property real displayedLoad: 0
    property real displayedThermal: 0
    property real displayedEnergy: 0
    property real displayedInbound: 0
    property real displayedOutbound: 0
    property real displayedSpin: 0
    property real loadPhase: 0
    property real thermalPhase: 0
    property real thermalArcPhase: 0
    property real energyPhase: 0
    property real inboundPhase: 0
    property real outboundPhase: 0
    property real spinPhase: 0
    property double previousTick: 0
    property var clockSubscription: null
    readonly property var clockHost: root.Window.window ? root.Window.window.contentItem : null
    readonly property bool effectControlsValid: Number.isFinite(intensity) && intensity >= 0 && intensity <= 1
        && Number.isFinite(speed) && speed >= 0.5 && speed <= 2
    readonly property bool levelValid: typeof level === "number" && Number.isFinite(level) && level >= 0 && level <= 1
    readonly property bool compositeActive: effect === "auto"
        && hardwareState !== null && typeof hardwareState === "object"
        && Object.keys(hardwareState).length > 0
    readonly property string feedbackProfile: String(hardwareState && hardwareState.profile || "")
    readonly property bool stateAvailable: compositeActive && hardwareState.available === true
        && ["processor","memory","network","disk","battery","fan","volume","storage"].includes(feedbackProfile)
    readonly property bool supportsLoad: ["cpu","gpu","memory","vram","battery","disk","grid","custom","frequency"].includes(name)
        || name==="time" && feedbackProfile==="battery"
    readonly property bool supportsThermal: ["cpu","gpu","temperature","disk"].includes(name)
    readonly property bool supportsEnergy: ["cpu","gpu","power","voltage"].includes(name)
    readonly property bool supportsInbound: ["network","download","disk","disk_read","battery"].includes(name)
        || name==="time" && feedbackProfile==="battery"
    readonly property bool supportsOutbound: ["network","upload","disk","disk_write","battery"].includes(name)
        || name==="time" && feedbackProfile==="battery"
    readonly property var loadTarget: channelTarget("load")
    readonly property var thermalTarget: channelTarget("thermal")
    readonly property var energyTarget: channelTarget("energy")
    readonly property var inboundTarget: channelTarget("inbound")
    readonly property var outboundTarget: channelTarget("outbound")
    readonly property var spinTarget: channelTarget("spin")
    readonly property real targetActivity: compositeActive ? Math.max(supportsLoad && loadTarget || 0,
        supportsThermal && (thermalTarget>.28?thermalTarget:0) || 0,supportsEnergy && energyTarget || 0,
        supportsInbound && inboundTarget || 0,supportsOutbound && outboundTarget || 0,name==="fan" && spinTarget || 0)
        : levelValid ? resolvedEffect==="heat" && level<=.28?0:level : 0
    readonly property bool loadActive: animationRunning && compositeActive && supportsLoad && loadTarget > 0
    readonly property bool thermalActive: animationRunning && compositeActive && supportsThermal && thermalTarget > 0
    readonly property bool energyActive: animationRunning && compositeActive && supportsEnergy && energyTarget > 0
    readonly property bool inboundActive: animationRunning && compositeActive && supportsInbound && inboundTarget > 0
    readonly property bool outboundActive: animationRunning && compositeActive && supportsOutbound && outboundTarget > 0
    readonly property bool spinChannelActive: animationRunning && compositeActive && name==="fan" && spinTarget > 0
    // A decorative thermal response range, never a hardware warning threshold.
    readonly property real heatPresentation:compositeActive?displayedThermal:resolvedEffect==="heat"?displayedLevel:0
    readonly property real thermalArcStrength:Math.max(0,Math.min(1,(heatPresentation-.28)/.55))
    readonly property real thermalArcDuration:2400/(.82+.36*thermalArcStrength)
    readonly property bool processorGlyph:["cpu","gpu"].includes(name)
    readonly property bool thermalContext:animationRunning && name!=="fan"
        && (compositeActive?supportsThermal && thermalTarget!==null:resolvedEffect==="heat")
    readonly property bool thermalArcActive:thermalContext && thermalArcStrength>0
    readonly property real heatPhase:compositeActive?thermalArcPhase:phase
    readonly property real heatBaseDuration:compositeActive?thermalArcDuration:cycleDuration*speed
    readonly property real thermalCharge:heatPhase<.2?smooth01(heatPhase/.2)
        :heatPhase<.32?1:1-smooth01((heatPhase-.32)/.68)
    readonly property bool electricEnabled:animationRunning && (compositeActive?energyActive:energyFlow)
    readonly property real electricActivity:compositeActive?displayedEnergy:displayedLevel
    readonly property real electricPhase:compositeActive?energyPhase:phase
    readonly property real electricBaseDuration:compositeActive?1800/(.55+1.2*displayedEnergy):cycleDuration*speed
    readonly property string resolvedEffect: {
        if (compositeActive) return "hardware"
        if(name==="fan" && ["heat","flow","spin","pulse"].includes(effect))return "spin"
        if (["heat", "flow", "spin", "pulse"].includes(effect)) return effect
        if (effect !== "auto") return "off"
        if (automaticEffect!=="") return ["heat","flow","spin","pulse","off"].includes(automaticEffect)?automaticEffect:"off"
        if (name==="temperature") return "heat"
        if (name==="fan") return "spin"
        if (["power","voltage","network","download","upload","disk_read","disk_write"].includes(name)) return "flow"
        if (["frequency","cpu","gpu","memory","vram","battery","grid","sensors"].includes(name)) return "pulse"
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
        if(!(root.width>0 && root.height>0))return false
        for (let item = root; item; item = item.parent)
            if (!item.visible || item.opacity <= 0) return false
        return true
    }
    readonly property bool animationRunning: exposed && windowVisible && motionEnabled && (compositeActive?stateAvailable:available)
        && targetActivity > 0 && effectControlsValid && intensity > 0 && resolvedEffect !== "off"
        && (resolvedEffect !== "spin" || name === "fan")
    readonly property real activityStrength: 0.28 + 0.72 * displayedLevel
    readonly property real feedbackStrength: intensity * activityStrength
    readonly property real intensityGain: effectControlsValid?intensity*(1.8-.8*intensity):0
    readonly property real accentOpacity: intensityGain * (0.85 + 0.15 * displayedLevel)
    readonly property real cycleDuration: resolvedEffect === "spin" ? 3000/(speed*(.55+1.2*displayedLevel))
        : 2400/(speed*(.82+.36*displayedLevel))
    readonly property real wave: 0.5 - 0.5 * Math.cos(phase * Math.PI * 2)
    readonly property bool darkSurface: ink.r * .2126 + ink.g * .7152 + ink.b * .0722 > .55
    readonly property bool energyFlow: resolvedEffect === "flow" && !arrowFlow
    readonly property color lowColor: resolvedEffect === "heat" ? (darkSurface ? "#fdba40" : "#d97706")
        : resolvedEffect === "spin" ? (darkSurface ? "#39d8c5" : "#0d9488")
        : energyFlow ? (darkSurface ? "#f5d64b" : "#ca8a04")
        : resolvedEffect === "flow" && outgoing ? (darkSurface ? "#b397ff" : "#7c3aed")
        : resolvedEffect === "flow" ? (darkSurface ? "#46ddf0" : "#0284c7")
        : (darkSurface ? "#55a6ff" : "#2563eb")
    readonly property color highColor: resolvedEffect === "heat" ? (darkSurface ? "#ff5b60" : "#dc2626")
        : resolvedEffect === "spin" ? (darkSurface ? "#5de7a7" : "#059669")
        : energyFlow ? (darkSurface ? "#ffab3d" : "#d97706")
        : resolvedEffect === "flow" && outgoing ? (darkSurface ? "#f078e1" : "#c026d3")
        : resolvedEffect === "flow" ? (darkSurface ? "#5a9cff" : "#2563eb")
        : (darkSurface ? "#b18aff" : "#7c3aed")
    readonly property color accentColor: paletteColor(manualColors,displayedLevel)
    // Ten chromatic anchors per independent channel, continuously interpolated.
    // The SVG palette is immutable; only retained texture opacities change.
    readonly property var loadColors: darkSurface
        ? ["#43baff","#4baeff","#599fff","#6992ff","#7985ff","#8879ff","#996fff","#aa66ff","#bb60f9","#ca59ed"]
        : ["#008ddd","#087edc","#206cdb","#365bd9","#4c4bd5","#623dd0","#762dc9","#891dc0","#9b13b4","#ab0aa5"]
    readonly property var thermalColors: darkSurface
        ? ["#55baff","#42d5e1","#b6dc51","#ffe257","#ffc139","#ffa12e","#ff7b30","#ff573c","#ff374c","#ff235c"]
        : ["#177bd6","#008eac","#7c9800","#bd9b00","#db8800","#ec7000","#f0520b","#eb351b","#dc1d2d","#c90d42"]
    readonly property var energyColors: darkSurface
        ? ["#65eaff","#5ce4ff","#53dcff","#4bd4ff","#45cbff","#43c2ff","#46b8ff","#4caeff","#54a4ff","#6099ff"]
        : ["#008fae","#008bb8","#0086c2","#0080cc","#0079d6","#0871df","#1768e6","#275eeb","#3654ee","#4549ee"]
    readonly property var inboundColors: darkSurface
        ? ["#52dcf3","#49d2f6","#41c8fa","#3ebdfd","#40b2ff","#47a7ff","#519cff","#5f91ff","#6f86ff","#807bff"]
        : ["#008ea8","#0087b0","#007eb9","#0074c3","#0069cc","#005dd5","#0d51dc","#2646e0","#403be1","#5a2ee0"]
    readonly property var outboundColors: darkSurface
        ? ["#a9a0ff","#b09aff","#b993ff","#c18bff","#cb82fe","#d579fa","#df70f3","#e868ea","#ef61df","#f65ad3"]
        : ["#6c44d9","#773cd5","#8235d0","#8d2ec9","#9827c1","#a120b8","#aa1aaf","#b315a5","#ba109b","#bf0c92"]
    readonly property var spinColors: darkSurface
        ? ["#42dacd","#3bdac6","#37dbbf","#36dcb7","#39ddaf","#40dea7","#4adf9f","#57e198","#65e291","#74e58b"]
        : ["#009d96","#009d8e","#009d86","#009c7e","#009b75","#009a6d","#049865","#13965d","#239456","#31914e"]
    readonly property var goldColors: darkSurface
        ? ["#ffe577","#ffdd62","#ffd44f","#ffca40","#ffc036","#ffb72f","#ffad2c","#ffa22d","#ff972f","#ff8c34"]
        : ["#b78b00","#c18400","#ca7c00","#d37500","#db6c00","#e36200","#e95803","#ed4c0a","#ef3f15","#ef321f"]
    readonly property var manualColors: resolvedEffect==="heat"?thermalColors:resolvedEffect==="spin"?spinColors
        :energyFlow?energyColors:resolvedEffect==="flow"?(outgoing?outboundColors:inboundColors):loadColors
    readonly property color loadColor: paletteColor(loadColors,displayedLoad)
    readonly property color thermalColor: paletteColor(thermalColors,displayedThermal)
    readonly property color energyColor: paletteColor(energyColors,displayedEnergy)
    readonly property color inboundColor: paletteColor(inboundColors,displayedInbound)
    readonly property color outboundColor: paletteColor(outboundColors,displayedOutbound)
    readonly property color spinColor: paletteColor(spinColors,displayedSpin)
    // Immutable upstream fragments are parsed on glyph changes, never on a frame.
    readonly property var glyphParts: IconData.fragment(name).match(/<(?:path|rect|circle|line|polyline|polygon)\b[^>]*\/>/g) || []
    readonly property string pulsePaths: glyphParts.map(part => {
        const match = part.match(/\bd="([^"]*)"/)
        return match ? "M0 0 " + match[1] : ""
    }).join(" ")
    readonly property bool corePulse: ["cpu", "gpu", "memory", "vram", "battery", "disk"].includes(name) || !pulsePaths.trim()
    readonly property bool arrowFlow: ["network", "download", "upload", "disk_read", "disk_write"].includes(name)
    readonly property bool outgoing: name === "upload" || name === "disk_read"
        || (name === "network" && metric === "net_upload")
    readonly property int flowDirection: outgoing ? -1 : 1
    readonly property string flowMoving: name === "network" && outgoing
        ? glyphParts.slice(2, 4).join("") : glyphParts.slice(0, 2).join("")
    readonly property string flowFixed: name === "network" && outgoing
        ? glyphParts.slice(0, 2).join("") : glyphParts.slice(2).join("")
    readonly property bool flowActive: animationRunning && resolvedEffect === "flow"
    readonly property bool spinActive: animationRunning && name === "fan" && (resolvedEffect === "spin" || spinChannelActive)
    readonly property real rotorOpacity: compositeActive?channelOpacity(displayedSpin):accentOpacity
    readonly property bool outlineActive: animationRunning
        && !["fan","network","download","upload","disk_read","disk_write"].includes(name)
        && (compositeActive ? loadActive || thermalActive || energyActive || inboundActive || outboundActive
            : ["heat","pulse"].includes(resolvedEffect) || energyFlow)
    readonly property var outlineColors: compositeActive
        ? thermalActive?thermalColors:loadActive?loadColors:energyActive?energyColors:inboundActive?inboundColors:outboundColors
        : manualColors
    readonly property real outlineAmount: compositeActive
        ? thermalActive?displayedThermal:loadActive?displayedLoad:energyActive?displayedEnergy:inboundActive?displayedInbound:displayedOutbound
        : displayedLevel
    implicitWidth: 18
    implicitHeight: 18
    clip: false

    function channelTarget(key) {
        const value=hardwareState && hardwareState[key]
        return typeof value==="number" && Number.isFinite(value) && value>=0 && value<=1?value:null
    }
    function channelOpacity(value) {return intensityGain*(.85+.15*value)}
    function smooth01(value) {const t=Math.max(0,Math.min(1,value));return t*t*(3-2*t)}
    function paletteColor(colors,value) {
        const position=Math.max(0,Math.min(1,value))*(colors.length-1),index=Math.floor(position)
        const first=Qt.darker(colors[index],1),second=Qt.darker(colors[Math.min(colors.length-1,index+1)],1),mix=position-index
        return Qt.rgba(first.r+(second.r-first.r)*mix,first.g+(second.g-first.g)*mix,first.b+(second.b-first.b)*mix,1)
    }
    function converge(current,target,elapsed) {
        if(!(target>0))return 0
        const next=current+(target-current)*(1-Math.exp(-elapsed/200))
        return Math.abs(next-target)<.001?target:next
    }
    function resetFeedback() {
        phase=0;loadPhase=0;thermalPhase=0;thermalArcPhase=0;energyPhase=0;inboundPhase=0;outboundPhase=0;spinPhase=0
        displayedLoad=animationRunning && compositeActive?(loadTarget || 0):0
        displayedThermal=animationRunning && compositeActive?(thermalTarget || 0):0
        displayedEnergy=animationRunning && compositeActive?(energyTarget || 0):0
        displayedInbound=animationRunning && compositeActive?(inboundTarget || 0):0
        displayedOutbound=animationRunning && compositeActive?(outboundTarget || 0):0
        displayedSpin=animationRunning && compositeActive?(spinTarget || 0):0
        displayedLevel=animationRunning?(compositeActive?targetActivity:level):0
    }

    // Delayed ticks use elapsed time. Clock corrections and long pauses cannot jump a cycle.
    function advanceClock(now) {
        if (!Number.isFinite(now)) return
        if (!animationRunning) {previousTick = now;resetFeedback();return}
        const elapsed = Math.max(0, Math.min(136, now - previousTick))
        previousTick = now
        if(compositeActive) {
            displayedLoad=converge(displayedLoad,loadTarget,elapsed)
            displayedThermal=converge(displayedThermal,thermalTarget,elapsed)
            displayedEnergy=converge(displayedEnergy,energyTarget,elapsed)
            displayedInbound=converge(displayedInbound,inboundTarget,elapsed)
            displayedOutbound=converge(displayedOutbound,outboundTarget,elapsed)
            displayedSpin=converge(displayedSpin,spinTarget,elapsed)
            displayedLevel=Math.max(loadActive?displayedLoad:0,thermalActive?displayedThermal:0,energyActive?displayedEnergy:0,
                inboundActive?displayedInbound:0,outboundActive?displayedOutbound:0,spinChannelActive?displayedSpin:0)
            loadPhase=loadActive?(loadPhase+elapsed*speed*(.55+1.2*displayedLoad)/2200)%1:0
            thermalPhase=thermalActive?(thermalPhase+elapsed*speed*(.55+1.2*displayedThermal)/2400)%1:0
            thermalArcPhase=thermalArcActive?(thermalArcPhase+elapsed*speed/thermalArcDuration)%1:0
            energyPhase=energyActive?(energyPhase+elapsed*speed*(.82+.36*displayedEnergy)/2400)%1:0
            inboundPhase=inboundActive?(inboundPhase+elapsed*speed*(.82+.36*displayedInbound)/2400)%1:0
            outboundPhase=outboundActive?(outboundPhase+elapsed*speed*(.82+.36*displayedOutbound)/2400)%1:0
            spinPhase=spinChannelActive?(spinPhase+elapsed*speed*(.35+1.65*displayedSpin)/3600)%1:0
        } else displayedLevel=converge(displayedLevel,level,elapsed)
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
        resetFeedback()
        syncClock()
    }
    onCompositeActiveChanged: resetFeedback()
    onLoadTargetChanged: {if(!(loadTarget>0)){displayedLoad=0;loadPhase=0}}
    onThermalTargetChanged: {if(!(thermalTarget>0)){displayedThermal=0;thermalPhase=0;thermalArcPhase=0}}
    onEnergyTargetChanged: {if(!(energyTarget>0)){displayedEnergy=0;energyPhase=0}}
    onInboundTargetChanged: {if(!(inboundTarget>0)){displayedInbound=0;inboundPhase=0}}
    onOutboundTargetChanged: {if(!(outboundTarget>0)){displayedOutbound=0;outboundPhase=0}}
    onSpinTargetChanged: {if(!(spinTarget>0)){displayedSpin=0;spinPhase=0}}
    onClockHostChanged: syncClock()
    Component.onCompleted: syncClock()
    Component.onDestruction: EffectClock.unsubscribe(clockSubscription)
    Icon {
        objectName: "metricIconGlyph"
        anchors.fill: parent; name: root.name; ink: root.ink
        // The neutral carrier survives strength→0; active arrow/rotor layers blend in.
        opacity: root.spinActive ? Math.pow(1-root.rotorOpacity,6) : 1
    }
    // Exact Lucide subpaths separated into fixed structure and moving parts.
    component VectorPart: Image {
        property string fragment: ""
        property string viewBox: "0 0 24 24"
        property real strokeWidth: 2
        property color stroke: root.ink
        property bool filled: false
        anchors.fill: parent
        sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
        sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit; smooth: true
        source: "data:image/svg+xml;base64," + Qt.btoa(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + viewBox + '" fill="' + (filled?stroke.toString():"none") + '" stroke="'
            + "#" + [stroke.r,stroke.g,stroke.b].map(channel=>Math.round(channel*255).toString(16).padStart(2,"0")).join("")
            + '" stroke-opacity="' + stroke.a
            + '" stroke-width="' + strokeWidth + '" stroke-linecap="round" stroke-linejoin="round">' + fragment + '</svg>')
    }
    // Fixed palette endpoints: state changes blend retained textures, never SVG sources.
    component AccentPart: Item {
        property string fragment: ""
        property string viewBox: "0 0 24 24"
        property real strokeWidth: 2
        property bool filled: false
        property var colors: root.manualColors
        property real amount: root.displayedLevel
        anchors.fill: parent
        id:accent
        Repeater {
            model:accent.visible?accent.colors:[]
            VectorPart {
                required property var modelData
                required property int index
                readonly property real position:Math.max(0,Math.min(1,accent.amount))*(accent.colors.length-1)
                fragment:accent.fragment;viewBox:accent.viewBox;strokeWidth:accent.strokeWidth;stroke:modelData;filled:accent.filled
                opacity:index===Math.floor(position)?1:index===Math.floor(position)+1?position-Math.floor(position):0
            }
        }
    }

    // The whole window shares one clock. Image sources never depend on phase,
    // stage or theme; 4 retained quads blend adjacent stage/phase cells.
    component DischargeAtlas: Item {
        id:atlas
        property real amount:0
        property real phaseValue:0
        property bool warm:false
        property real layerOpacity:1
        readonly property real stagePosition:Math.max(0,Math.min(9,amount*10-1))
        readonly property int lowerStage:Math.floor(stagePosition)
        readonly property real stageBlend:stagePosition-lowerStage
        readonly property real framePosition:((phaseValue%1+1)%1)*48
        readonly property int lowerFrame:Math.floor(framePosition)%48
        readonly property real frameBlend:framePosition-Math.floor(framePosition)
        property url atlasSource:warm?root.warmAtlasSource:root.blueAtlasSource
        width:18;height:18
        opacity:root.channelOpacity(amount)*Math.min(1,amount*10)*layerOpacity
        Item {
            x:-7;y:-7;width:32;height:32;clip:true
            Repeater {
                model:4
                Image {
                    required property int index
                    objectName:"metricDischargeCell_"+index
                    readonly property int atlasStage:Math.min(9,atlas.lowerStage+(index>=2?1:0))
                    readonly property int atlasFrame:(atlas.lowerFrame+index%2)%48
                    source:atlas.atlasSource;cache:true;asynchronous:false;smooth:true
                    width:48*32;height:10*32
                    x:-atlasFrame*32;y:-atlasStage*32
                    opacity:(index%2?atlas.frameBlend:1-atlas.frameBlend)
                        *(index>=2?atlas.stageBlend:1-atlas.stageBlend)
                }
            }
        }
    }
    // Non-clipping logical wrappers can be zero/equal-sized. Select the actual
    // nearest row with spare height (including a 12px duplex row) for paint only.
    readonly property var paintBleed: {
        const ignoredY=root.y,ignoredHeight=root.height
        const scale=Math.max(.001,Math.min(root.width,root.height)/18)
        for(let item=root.parent;item;item=item.parent) {
            if(item.width>0 && item.height>=root.height && item.height<=64*scale
                    && (item.height>root.height+.1 || item.clip)) {
                const at=root.mapToItem(item,0,0)
                return {top:Math.min(6,Math.max(0,at.y-.5*scale)/scale),
                    bottom:Math.min(6,Math.max(0,item.height-at.y-root.height-.5*scale)/scale)}
            }
        }
        return {top:2.5,bottom:2.5}
    }
    Item {
        id:composition
        width:18;height:18;anchors.centerIn:parent
        scale:Math.min(root.width,root.height)/18
        Item {
            x:-2.5;y:-root.paintBleed.top;width:23;height:18+root.paintBleed.top+root.paintBleed.bottom;clip:true
            Item {
                x:2.5;y:root.paintBleed.top;width:18;height:18
                Loader {
                    objectName:"metricIconThermalArcs"
                    anchors.fill:parent;active:root.thermalContext
                    sourceComponent:Item {
                        width:18;height:18
                        visible:root.thermalArcActive
                        DischargeAtlas {
                            objectName:"metricIconWarmDischarge"
                            height:root.name==="temperature"?10:18
                            clip:root.name==="temperature"
                            warm:true;amount:root.thermalArcStrength;phaseValue:root.heatPhase
                        }
                    }
                }
                Loader {
                    objectName:"metricIconEnergyArc"
                    anchors.fill:parent;active:root.electricEnabled
                    sourceComponent:DischargeAtlas {
                        objectName:"metricIconBlueDischarge"
                        amount:root.electricActivity;phaseValue:root.electricPhase
                    }
                }
                Loader {
                    objectName:"metricIconFlow"
                    anchors.fill:parent;active:root.flowActive && root.arrowFlow
                    sourceComponent:Item {
                        width:18;height:18
                        Item {
                            x:root.name==="network" && root.outgoing?9:0
                            width:root.name==="network"?9:18
                            height:["disk_read","disk_write"].includes(root.name)?10:root.name==="network"?18:14
                            clip:true
                            DischargeAtlas {
                                objectName:"metricIconFlowArrow_0"
                                x:root.name==="network"?(root.outgoing?-5.25:-3.75):0
                                amount:root.displayedLevel;phaseValue:root.phase
                            }
                        }
                    }
                }
                Loader {
                    objectName:"metricIconTransport"
                    anchors.fill:parent
                    active:root.animationRunning && root.compositeActive && (root.supportsInbound || root.supportsOutbound)
                    sourceComponent:Item {
                        Repeater {
                            model:2
                            Loader {
                                id:packet
                                required property int index
                                readonly property bool inbound:index===0
                                active:inbound?root.inboundActive:root.outboundActive
                                x:root.name==="network" && !inbound?9:0
                                width:root.name==="network"?9:18
                                height:["disk_read","disk_write"].includes(root.name)?10:18
                                clip:root.name==="network" || ["disk_read","disk_write"].includes(root.name)
                                sourceComponent:DischargeAtlas {
                                    objectName:"metricIconTransportArc_"+packet.index
                                    x:root.name==="network"?(packet.inbound?-3.75:-5.25):0
                                    amount:packet.inbound?root.displayedInbound:root.displayedOutbound
                                    phaseValue:packet.inbound?root.inboundPhase:(root.outboundPhase+.23)%1
                                }
                            }
                        }
                    }
                }
                Loader {
                    objectName:"metricIconScalarActivity"
                    anchors.fill:parent
                    active:root.animationRunning && root.resolvedEffect==="pulse" && !root.corePulse
                    sourceComponent:DischargeAtlas {
                        objectName:"metricIconPulseStroke"
                        amount:root.displayedLevel;phaseValue:root.phase
                    }
                }
            }
        }
        Loader {
            anchors.fill:parent;active:root.spinActive
            sourceComponent:Item {
                VectorPart {
                    objectName:"metricIconRotorStructure";fragment:root.glyphParts[0] || ""
                    strokeWidth:1.6;rotation:(root.compositeActive?root.spinPhase:root.phase)*360
                    opacity:1-Math.pow(1-root.rotorOpacity,6)
                }
                AccentPart {
                    objectName:"metricIconRotor";fragment:root.glyphParts[0] || "";strokeWidth:1.6
                    colors:root.compositeActive?root.spinColors:root.manualColors
                    amount:root.compositeActive?root.displayedSpin:root.displayedLevel
                    rotation:(root.compositeActive?root.spinPhase:root.phase)*360;opacity:root.rotorOpacity
                }
                VectorPart {
                    objectName:"metricIconHub";fragment:root.glyphParts.slice(1).join("");strokeWidth:2.4
                    opacity:1-Math.pow(1-root.rotorOpacity,6)
                }
            }
        }
        Item {
            id:heatLayer;objectName:"metricIconHeat"
            readonly property int paintCount:0
            anchors.fill:parent;visible:root.thermalContext && root.name==="temperature"
            readonly property real activity:root.heatPresentation
            readonly property real alpha:root.channelOpacity(activity)
            Rectangle {
                objectName:"metricIconHeatMercury";x:7.8;y:12.3;width:2.4;height:2.4;radius:1.2;antialiasing:true
                color:root.compositeActive?root.thermalColor:root.accentColor;opacity:heatLayer.alpha
            }
            Rectangle {
                x:8.45;width:1.1;height:2+5*heatLayer.activity;y:12.6-height;radius:.55;antialiasing:true
                color:root.compositeActive?root.thermalColor:root.accentColor;opacity:heatLayer.alpha
            }
        }
        Rectangle {
            id:pulseCore;objectName:"metricIconPulseCore"
            visible:root.loadActive || root.animationRunning && root.resolvedEffect==="pulse" && root.corePulse
            readonly property real localWave:visible?(root.compositeActive?.5-.5*Math.cos(root.loadPhase*Math.PI*2):root.wave):0
            readonly property real activity:root.compositeActive?root.displayedLoad:root.displayedLevel
            readonly property real strength:root.intensity*(.28+.72*activity)
            readonly property bool proportional:root.compositeActive || /(?:_usage|_percent)$/.test(root.metric)
            readonly property real fillExtent:proportional?activity:.55
            readonly property bool horizontal:["memory","vram","battery","disk"].includes(root.name)
            width:root.name==="gpu"?10*fillExtent:horizontal?(root.name==="battery"?10:13)*fillExtent:4.4
            height:root.name==="gpu"?2:horizontal?(root.name==="disk"?3.8:4.5):4.4*fillExtent
            x:root.name==="gpu"?3:horizontal?2.5:6.8
            y:root.name==="gpu"?10:root.name==="disk"?10.5:horizontal?6:11.2-height
            radius:.35;antialiasing:true;clip:true
            color:root.compositeActive?root.loadColor:root.accentColor
            opacity:root.channelOpacity(activity)*(["cpu","gpu"].includes(root.name)?.42:.88+.12*localWave)
            Rectangle {
                objectName:"metricIconLoadHighlight"
                readonly property real progress:root.compositeActive?root.loadPhase:root.phase
                x:pulseCore.horizontal?progress*(pulseCore.width+3)-2:0
                y:pulseCore.horizontal?0:(1-progress)*(pulseCore.height+3)-1
                width:pulseCore.horizontal?.8:pulseCore.width;height:pulseCore.horizontal?pulseCore.height:.65
                color:root.darkSurface?"#e9e5ff":"#d9e9ff";opacity:.8
            }
            Loader {
                objectName:"metricIconCapacityActivity"
                active:pulseCore.visible && pulseCore.horizontal
                sourceComponent:DischargeAtlas {
                    x:-pulseCore.x;y:-pulseCore.y;amount:pulseCore.activity
                    phaseValue:root.compositeActive?root.loadPhase:root.phase
                    layerOpacity:.65
                }
            }
        }
    }
}
