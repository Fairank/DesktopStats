import QtQuick
import QtQuick.Window
import "IconData.js" as IconData
import "MetricEffectClock.js" as EffectClock
import "HardwareShapes.js" as HardwareShapes

// Optional feedback. Fill follows normalized readings; motion is decorative, never an alarm.
Item {
    id: root
    property string name: "sensors"
    property string metric: ""
    property color ink: "#69788c"
    property string effect: "off"
    property string automaticEffect: ""
    property var level: null
    property var hardwareState: ({})
    property var hardwareAppearance: ({})
    property string iconStyle: "classic"
    readonly property string cartoonSymbol: ["cartoon","sketch","notebook_line","notebook_color","notebook_smile"].includes(iconStyle) && !hasHardwareAppearance
        ? HardwareShapes.genericSource(name, ink, spinActive, iconStyle) : ""
    readonly property bool hasHardwareAppearance: (processorGlyph || name === "memory")
        && hardwareAppearance && hardwareAppearance.kind === name
        && hardwareAppearance.icon_set !== "classic"
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
    property real displayedTemperature: 0
    property real loadPhase: 0
    property real thermalArcPhase: 0
    property real energyPhase: 0
    property real inboundPhase: 0
    property real outboundPhase: 0
    property real spinPhase: 0
    property real gpuFanPhase: 0
    property double gpuFanSampleTick: 0
    property double previousTick: 0
    property var clockSubscription: null
    property bool feedbackReady: false
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
    readonly property bool thermometerGlyph: name === "temperature"
    readonly property var thermometerTarget: compositeActive ? thermalTarget : levelValid ? level : null
    readonly property bool thermometerEnabled: thermometerGlyph && exposed && windowVisible && motionEnabled
        && (compositeActive ? stateAvailable : available) && thermometerTarget !== null
        && effectControlsValid && intensity > 0 && !["off", "spin"].includes(resolvedEffect)
    readonly property bool thermometerChanging: thermometerEnabled
        && Math.abs(displayedTemperature - thermometerTarget) > .001
    readonly property real thermometerWarmth: Math.max(0, Math.min(1, (displayedTemperature - .28) / .55))
    readonly property real targetActivity: thermometerGlyph
        ? thermometerEnabled && (thermometerTarget > .28 || thermometerChanging) ? Math.max(.001, thermometerTarget) : 0
        : compositeActive ? Math.max(supportsLoad && loadTarget || 0,
        supportsThermal && (thermalTarget>.28?thermalTarget:0) || 0,supportsEnergy && energyTarget || 0,
        supportsInbound && inboundTarget || 0,supportsOutbound && outboundTarget || 0,name==="fan" && spinTarget || 0,gpuFanCanAnimate?1:0)
        : levelValid ? resolvedEffect==="heat" && level<=.28?0:level : 0
    readonly property bool loadActive: animationRunning && compositeActive && supportsLoad && loadTarget > 0
    readonly property bool thermalActive: animationRunning && compositeActive && supportsThermal && thermalTarget > 0
    readonly property bool energyActive: animationRunning && compositeActive && supportsEnergy && energyTarget > 0
    readonly property bool inboundActive: animationRunning && compositeActive && supportsInbound && inboundTarget > 0
    readonly property bool outboundActive: animationRunning && compositeActive && supportsOutbound && outboundTarget > 0
    readonly property bool spinChannelActive: animationRunning && compositeActive && name==="fan" && spinTarget > 0
    // A decorative thermal response range, never a hardware warning threshold.
    readonly property real heatPresentation:thermometerGlyph?displayedTemperature
        :compositeActive?displayedThermal:resolvedEffect==="heat"?displayedLevel:0
    readonly property real thermalArcStrength:Math.max(0,Math.min(1,(heatPresentation-.28)/.55))
    readonly property real thermalArcDuration:2400/(.82+.36*thermalArcStrength)
    readonly property bool processorGlyph:["cpu","gpu"].includes(name)
    // A local decorative stress response: temperature and utilisation remain
    // independent real channels. Missing temperature never invents a hot reading.
    readonly property real processorLoadPressure:processorGlyph && compositeActive && loadActive?displayedLoad:0
    readonly property real processorWarmth:animationRunning && processorGlyph
        ?Math.max(thermalContext?thermalArcStrength:0,Math.max(0,(processorLoadPressure-.5)*2)):0
    readonly property var processorWarmColors:darkSurface
        ?["#ffd565","#ffca50","#ffbb41","#ffaa36","#ff9532","#ff7c35","#ff623c","#ff4d46","#ff3b50","#ff2c59"]
        :["#f3b330","#f5a62a","#f79726","#fa8525","#fc7028","#fb5b2d","#f74834","#ee383c","#e42b43","#d91e49"]
    readonly property color processorWarmColor:paletteColor(processorWarmColors,processorWarmth)
    // Continuous ten-band response:1x through50%,2x at60%,3x at80%,4x at100%.
    // This changes the rate of decorative packets, never the measured power.
    readonly property real processorDischargeRate:processorLoadPressure<=.5?1
        :processorLoadPressure<=.6?1+10*(processorLoadPressure-.5):2+5*(processorLoadPressure-.6)
    readonly property bool thermalContext:animationRunning && !thermometerGlyph && name!=="fan"
        && (compositeActive?supportsThermal && thermalTarget!==null:resolvedEffect==="heat")
    readonly property bool thermalArcActive:thermalContext && thermalArcStrength>0
    readonly property real heatPhase:compositeActive?thermalArcPhase:phase
    readonly property real heatBaseDuration:compositeActive?thermalArcDuration:cycleDuration*speed
    readonly property real thermalCharge:heatPhase<.2?smooth01(heatPhase/.2)
        :heatPhase<.32?1:1-smooth01((heatPhase-.32)/.68)
    readonly property bool electricEnabled:animationRunning && !thermometerGlyph && (compositeActive?energyActive:energyFlow)
    readonly property real electricActivity:compositeActive?displayedEnergy:displayedLevel
    readonly property real electricPhase:compositeActive?energyPhase:phase
    readonly property real electricBaseDuration:compositeActive?1800/(.55+1.2*displayedEnergy):cycleDuration*speed
    readonly property string resolvedEffect: {
        if (compositeActive) return "hardware"
        // Old manually saved flow/pulse choices cannot turn a thermometer into
        // an electrical quantity. Explicit automatic-off still stays off.
        if (thermometerGlyph && ["heat", "flow", "pulse", "spin"].includes(effect)) return "heat"
        if(name==="fan" && ["heat","flow","spin","pulse"].includes(effect))return "spin"
        if (["heat", "flow", "spin", "pulse"].includes(effect)) return effect
        if (effect !== "auto") return "off"
        if (automaticEffect!=="") {
            if (!["heat","flow","spin","pulse","off"].includes(automaticEffect)) return "off"
            return thermometerGlyph && ["heat", "flow", "pulse", "spin"].includes(automaticEffect) ? "heat" : automaticEffect
        }
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
        // Item.visible already includes ancestor visibility. Wait until caller
        // bindings settle before reading exposure or subscribing a new clock.
        if(!root.feedbackReady || !root.visible || !(root.width>0 && root.height>0))return false
        for (let item = root; item; item = item.parent)
            if (item.opacity <= 0) return false
        return true
    }
    readonly property bool animationRunning: exposed && windowVisible && motionEnabled && (compositeActive?stateAvailable:available)
        && targetActivity > 0 && effectControlsValid && intensity > 0 && resolvedEffect !== "off"
        && (resolvedEffect !== "spin" || name === "fan")
    readonly property int gpuVisibleFans: {
        const value=root.hardwareAppearance
        if (!value || value.kind!=="gpu" || value.confidence!=="model"
            || !["gpu_axial","gpu_blower","gpu_hybrid"].includes(value.style)) return 0
        const front=value.visible_fan_count, total=value.fan_count
        if (Number.isInteger(front) && front>0 && front<=3 && (total==null || Number.isInteger(total) && front<=total)) return front
        return Number.isInteger(total) && total>0 && total<=3 ? total : 0
    }
    readonly property var gpuFanReading: compositeActive && hardwareState.fan_speed ? hardwareState.fan_speed : ({})
    readonly property real gpuFanRpm: {
        const wake=root.gpuFanSampleTick, sample=root.gpuFanReading
        const now=Date.now()/1000
        if (sample.available!==true || ["measured","driver_current_rpm"].indexOf(sample.semantics)<0 || sample.scope!=="card"
            || typeof sample.rpm!=="number" || !Number.isFinite(sample.rpm) || sample.rpm<0 || sample.rpm>100000
            || typeof sample.timestamp!=="number" || !Number.isFinite(sample.timestamp)
            || now-sample.timestamp<-.01 || now-sample.timestamp>3) return NaN
        return sample.rpm
    }
    // Fixed slow motion keeps blade direction readable on a low-cadence bar.
    // Keep reported RPM unchanged; load, heat and effect-speed never set it.
    readonly property real gpuFanDisplaySlowdown: 120
    readonly property bool gpuFanCanAnimate: name==="gpu" && hasHardwareAppearance && compositeActive
        && Number.isFinite(gpuFanRpm) && gpuFanRpm>0
        && gpuVisibleFans>0 && ["solid","miniature","soft","cartoon","sketch","notebook_line","notebook_color","notebook_smile"].includes(hardwareAppearance.icon_set)
        && hardwareAppearance.fan_profile && hardwareAppearance.fan_profile.render_ready===true
        && resolvedEffect==="hardware"
    readonly property bool gpuFanMotionActive: gpuFanCanAnimate && animationRunning
    readonly property real activityStrength: 0.28 + 0.72 * displayedLevel
    readonly property real feedbackStrength: intensity * activityStrength
    readonly property real intensityGain: effectControlsValid?intensity*(1.8-.8*intensity):0
    readonly property real accentOpacity: intensityGain * (0.85 + 0.15 * displayedLevel)
    // Decorative fan speed is continuous and separate from the measured RPM.
    // At 2x it stays below 3.2 turns/s to avoid a four-blade stroboscopic reversal
    // during occasional delayed frames. No per-icon animation timer.
    readonly property real fanActivity:Math.max(0,Math.min(1,compositeActive?displayedSpin:displayedLevel))
    readonly property real fanRotationsPerSecond:speed*(.08+1.52*(1-Math.exp(-3*fanActivity))/(1-Math.exp(-3)))
    readonly property real fanTrailStrength:Math.max(0,Math.min(1,(fanActivity-.2)/.6))
    readonly property real cycleDuration: resolvedEffect === "spin" ? 1000/fanRotationsPerSecond
        : resolvedEffect === "flow" && arrowFlow ? 1000/(speed*streamCadence(displayedLevel))
        : resolvedEffect === "flow" && name === "power" ? 1400/(speed*streamCadence(displayedLevel))
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
    // Occupancy is still an exact linear fill. Only its decorative ink changes
    // from cool light to amber as the available capacity approaches saturation.
    readonly property var memoryColors: darkSurface
        ? ["#58d5f4","#64ccfc","#72c1ff","#86b5ff","#9aa8ff","#b39bf1","#c9a0cc","#e6bc77","#ffd15c","#ffb83d"]
        : ["#008ab2","#078cc2","#248cd0","#4389da","#6482da","#877bcb","#ab85a0","#c59859","#d9a12b","#e39515"]
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
        :energyFlow?energyColors:resolvedEffect==="flow"?(outgoing?outboundColors:inboundColors):memoryGlyph?memoryColors:loadColors
    readonly property color loadColor: paletteColor(loadColors,displayedLoad)
    readonly property color thermalColor: paletteColor(thermalColors,displayedThermal)
    readonly property var thermometerColors: darkSurface
        ? ["#f5d470","#f9cc59","#ffc247","#ffb33a","#ffa032","#ff8c31","#ff7537","#ff5f40","#ff4b4b","#ff3c58"]
        : ["#ad7909","#bc7c08","#cb7d08","#d97709","#e36b0d","#e65b14","#e64820","#e1352b","#d62639","#c91b45"]
    readonly property color thermometerColor: paletteColor(thermometerColors, displayedTemperature)
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
    readonly property bool memoryGlyph:["memory","vram"].includes(name)
    readonly property bool transportGlyph:["network","download","upload","disk","disk_read","disk_write"].includes(name)
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
    // A perceptual throughput scale, independent of the displayed units. It
    // gives small real transfers readable packets without inflating the value.
    function streamCadence(value) {return .4+1.6*Math.sqrt(Math.max(0,Math.min(1,value)))}
    function smooth01(value) {const t=Math.max(0,Math.min(1,value));return t*t*(3-2*t)}
    function paletteColor(colors,value) {
        const position=Math.max(0,Math.min(1,value))*(colors.length-1),index=Math.floor(position)
        const first=Qt.darker(colors[index],1),second=Qt.darker(colors[Math.min(colors.length-1,index+1)],1),mix=position-index
        return Qt.rgba(first.r+(second.r-first.r)*mix,first.g+(second.g-first.g)*mix,first.b+(second.b-first.b)*mix,1)
    }
    function converge(current,target,smoothing) {
        if(!(target>0))return 0
        const next=current+(target-current)*smoothing
        return Math.abs(next-target)<.001?target:next
    }
    function resetFeedback() {
        phase=0;loadPhase=0;thermalArcPhase=0;energyPhase=0;inboundPhase=0;outboundPhase=0;spinPhase=0
        displayedLoad=animationRunning && compositeActive && supportsLoad?(loadTarget || 0):0
        displayedThermal=animationRunning && compositeActive && supportsThermal?(thermalTarget || 0):0
        displayedEnergy=animationRunning && compositeActive && supportsEnergy?(energyTarget || 0):0
        displayedInbound=animationRunning && compositeActive && supportsInbound?(inboundTarget || 0):0
        displayedOutbound=animationRunning && compositeActive && supportsOutbound?(outboundTarget || 0):0
        displayedSpin=animationRunning && compositeActive && name==="fan"?(spinTarget || 0):0
        displayedLevel=animationRunning?(compositeActive?targetActivity:level):0
    }

    // Delayed ticks use elapsed time. Clock corrections and long pauses cannot jump a cycle.
    function advanceClock(now) {
        if (!Number.isFinite(now)) return
        if (!animationRunning) {previousTick = now;resetFeedback();return}
        const elapsed = Math.max(0, Math.min(136, now - previousTick))
        gpuFanSampleTick=now
        const smoothing = 1-Math.exp(-elapsed/200)
        previousTick = now
        if (thermometerEnabled) displayedTemperature=converge(displayedTemperature,thermometerTarget,smoothing)
        if(compositeActive && name === "fan") {
            // A rotor needs one smoothed channel and one transform per frame;
            // unrelated thermal/electrical phases belong to slower listeners.
            displayedSpin=converge(displayedSpin,spinTarget,smoothing)
            displayedLevel=spinChannelActive?displayedSpin:0
            spinPhase=spinChannelActive?(spinPhase+Math.min(.1,elapsed*fanRotationsPerSecond/1000))%1:0
            return
        } else if(compositeActive) {
            displayedLoad=supportsLoad?converge(displayedLoad,loadTarget,smoothing):0
            displayedThermal=supportsThermal?converge(displayedThermal,thermalTarget,smoothing):0
            displayedEnergy=supportsEnergy?converge(displayedEnergy,energyTarget,smoothing):0
            displayedInbound=supportsInbound?converge(displayedInbound,inboundTarget,smoothing):0
            displayedOutbound=supportsOutbound?converge(displayedOutbound,outboundTarget,smoothing):0
            displayedLevel=Math.max(loadActive?displayedLoad:0,thermalActive?displayedThermal:0,energyActive?displayedEnergy:0,
                inboundActive?displayedInbound:0,outboundActive?displayedOutbound:0,spinChannelActive?displayedSpin:0)
            loadPhase=loadActive?(loadPhase+elapsed*speed*(.55+1.2*displayedLoad)/2200)%1:0
            thermalArcPhase=thermalArcActive?(thermalArcPhase+elapsed*speed*processorDischargeRate/thermalArcDuration)%1:0
            energyPhase=energyActive?(energyPhase+elapsed*speed*(name==="power"?streamCadence(displayedEnergy)/1400:processorDischargeRate*(.82+.36*displayedEnergy)/2400))%1:0
            inboundPhase=inboundActive?(inboundPhase+elapsed*speed*(transportGlyph?streamCadence(displayedInbound)/1000:(.82+.36*displayedInbound)/2400))%1:0
            outboundPhase=outboundActive?(outboundPhase+elapsed*speed*(transportGlyph?streamCadence(displayedOutbound)/1000:(.82+.36*displayedOutbound)/2400))%1:0
        } else displayedLevel=converge(displayedLevel,level,smoothing)
        // Follow the measured card tachometer with a fixed 120x slow-motion
        // ratio. Never synthesize RPM from utilization, temperature or percent.
        if (gpuFanMotionActive)
            gpuFanPhase=(gpuFanPhase+elapsed*gpuFanRpm/(60000*gpuFanDisplaySlowdown))%1
        // Four identical blades repeat every quarter-turn; bound a delayed
        // rotor step below half that pitch so it cannot appear to reverse.
        phase = (phase + (spinActive?Math.min(.1,elapsed/cycleDuration):elapsed/cycleDuration)) % 1
    }
    function syncClock() {
        if (clockSubscription && (!clockSubscription.active || !animationRunning
                || !clockSubscription.entry || clockSubscription.entry.host !== clockHost)) {
            EffectClock.unsubscribe(clockSubscription)
            clockSubscription = null
        }
        if (animationRunning && clockHost && !clockSubscription) {
            clockSubscription = EffectClock.subscribe(clockHost, now => root.advanceClock(now), name === "fan")
            previousTick = EffectClock.timestamp(clockSubscription)
        }
        EffectClock.setCadence(clockSubscription, name === "fan")
    }
    onAnimationRunningChanged: {
        resetFeedback()
        syncClock()
    }
    onCompositeActiveChanged: resetFeedback()
    onThermometerEnabledChanged: displayedTemperature=thermometerEnabled?thermometerTarget:0
    onThermometerTargetChanged: {
        if (!thermometerEnabled || !(thermometerTarget > 0)) displayedTemperature=thermometerEnabled?thermometerTarget:0
    }
    onLoadTargetChanged: {if(!(loadTarget>0)){displayedLoad=0;loadPhase=0}}
    onThermalTargetChanged: {if(!(thermalTarget>0)){displayedThermal=0;thermalArcPhase=0}}
    onEnergyTargetChanged: {if(!(energyTarget>0)){displayedEnergy=0;energyPhase=0}}
    onInboundTargetChanged: {if(!(inboundTarget>0)){displayedInbound=0;inboundPhase=0}}
    onOutboundTargetChanged: {if(!(outboundTarget>0)){displayedOutbound=0;outboundPhase=0}}
    onSpinTargetChanged: {if(!(spinTarget>0)){displayedSpin=0;spinPhase=0}}
    // A glyph change discards only channels it no longer paints. Newly added
    // channels start from their current target; channels shared by both glyphs
    // keep their filtered value and phase instead of restarting the icon.
    onSupportsLoadChanged: {
        displayedLoad=animationRunning && compositeActive && supportsLoad?(loadTarget || 0):0
        if(!supportsLoad)loadPhase=0
    }
    onSupportsThermalChanged: {
        displayedThermal=animationRunning && compositeActive && supportsThermal?(thermalTarget || 0):0
        if(!supportsThermal)thermalArcPhase=0
    }
    onSupportsEnergyChanged: {
        displayedEnergy=animationRunning && compositeActive && supportsEnergy?(energyTarget || 0):0
        if(!supportsEnergy)energyPhase=0
    }
    onSupportsInboundChanged: {
        displayedInbound=animationRunning && compositeActive && supportsInbound?(inboundTarget || 0):0
        if(!supportsInbound)inboundPhase=0
    }
    onSupportsOutboundChanged: {
        displayedOutbound=animationRunning && compositeActive && supportsOutbound?(outboundTarget || 0):0
        if(!supportsOutbound)outboundPhase=0
    }
    onClockHostChanged: syncClock()
    onNameChanged: {
        displayedSpin=animationRunning && compositeActive && name==="fan"?(spinTarget || 0):0
        if(name!=="fan")spinPhase=0
        syncClock()
    }
    Component.onCompleted: { feedbackReady=true; syncClock() }
    Component.onDestruction: EffectClock.unsubscribe(clockSubscription)
    Loader {
        objectName:"metricIconPowerCore";anchors.fill:parent;z:-1
        active:root.name==="power" && root.electricEnabled
        sourceComponent:AccentPart {
            fragment:root.glyphParts.join("");filled:true;strokeWidth:0
            colors:root.energyColors;amount:root.electricActivity
            opacity:root.intensityGain*(.35+.4*Math.sqrt(Math.max(0,root.electricActivity)))
        }
    }
    Loader {
        objectName:"metricIconProcessorWarmth"
        // Retain the small geometry while a processor is active, so crossing
        // the heat threshold adds no delegates or textures during a sample.
        anchors.fill:parent;z:-1;active:root.processorGlyph && root.animationRunning
        sourceComponent:Item {
            visible:root.processorWarmth>0
            Item {
                width:18;height:18;anchors.centerIn:parent
                scale:Math.min(root.width,root.height)/18
                Item {
                    x:-2.5;y:-root.paintBleed.top;width:23;height:18+root.paintBleed.top+root.paintBleed.bottom;clip:true
                    Item {
                        x:2.5;y:root.paintBleed.top;width:18;height:18
                        Rectangle {
                            id:processorBody;objectName:"metricIconProcessorBodyWarmth"
                            x:root.name==="gpu"?1.5:3;y:root.name==="gpu"?3.75:3
                            width:root.name==="gpu"?15:12;height:root.name==="gpu"?9:12
                            radius:1.6;antialiasing:true;color:root.processorWarmColor
                            opacity:root.channelOpacity(root.processorWarmth)*root.processorWarmth*.22
                        }
                        Repeater {
                            model:3
                            Rectangle {
                                required property int index
                                objectName:"metricIconProcessorHalo_"+index
                                readonly property real spread:4.8-index*1.6
                                width:processorBody.width+spread*2;height:processorBody.height+spread*2
                                x:processorBody.x-spread;y:processorBody.y-spread;radius:processorBody.radius+spread
                                antialiasing:true;color:root.processorWarmColor
                                opacity:root.channelOpacity(root.processorWarmth)*root.processorWarmth*(.14-.025*index)
                            }
                        }
                    }
                }
            }
        }
    }
    Icon {
        objectName: "metricIconGlyph"
        anchors.fill: parent; name: root.name; ink: root.ink
        visible: !root.hasHardwareAppearance && !root.cartoonSymbol
        // The neutral carrier survives strength→0; active arrow/rotor layers blend in.
        opacity: root.spinActive ? Math.pow(1-root.rotorOpacity,6) : 1
    }
    Image {
        objectName: "metricCartoonSymbol"
        anchors.fill: parent
        visible: !!root.cartoonSymbol
        source: root.cartoonSymbol
        sourceSize.width: Math.max(1,Math.ceil(root.width*Screen.devicePixelRatio))
        sourceSize.height: Math.max(1,Math.ceil(root.height*Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit
        opacity: root.ink.a
        smooth: true; cache: true; asynchronous: false; mipmap: false
    }
    Loader {
        objectName: "metricHardwareGlyphLoader"
        anchors.fill: parent
        active: root.hasHardwareAppearance
        sourceComponent: HardwareGlyph {
            appearance: root.hardwareAppearance
            ink: root.ink
            fanMotionEnabled: root.gpuFanMotionActive
            fanRotation: root.gpuFanPhase*360
        }
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

    // Retained data packets: the neutral upstream arrow stays fixed. Each
    // real direction owns its colour, position and smoothed activity. No SVG
    // regeneration, extra textures, per-packet timer or model reset per sample.
    component TransportStream: Item {
        id:stream
        property real amount:0
        property real phaseValue:0
        property bool incoming:true
        readonly property real signal:Math.sqrt(Math.max(0,Math.min(1,amount)))
        readonly property bool disk:["disk","disk_read","disk_write"].includes(root.name)
        readonly property var blueColors:root.darkSurface
            ?["#48d7f5","#46d1f9","#45cbfc","#46c5ff","#48bfff","#4bb9ff","#4fb3ff","#53adff","#58a7ff","#5ea1ff"]
            :["#0086af","#0089bb","#008bc8","#008bd5","#048be0","#0b88e9","#1384f0","#1b7ef5","#2377f8","#2a70fa"]
        readonly property var purpleColors:root.darkSurface
            ?["#afa0ff","#b19eff","#b39bff","#b598ff","#b795ff","#ba92ff","#bd8fff","#c08cff","#c389ff","#c786ff"]
            :["#7142c8","#7641d0","#7c3fd7","#823ddd","#893be2","#9038e6","#9735e9","#9e32e9","#a62fe8","#ae2ce6"]
        readonly property color packetInk:root.paletteColor(incoming?blueColors:purpleColors,signal)
        readonly property real alpha:root.channelOpacity(amount)*Math.min(1,signal*24)
        readonly property real shaftX:root.name==="network"?(incoming?5.25:12.75):9
        readonly property real shaftTop:disk?1.5:root.name==="network"?3:2.25
        readonly property real shaftBottom:disk?7.5:root.name==="network"?15:12.75
        readonly property int direction:disk?(incoming?-1:1):(incoming?1:-1)
        readonly property real density:1+3*signal
        width:18;height:18
        Item {
            id:lane;x:stream.shaftX-1.2;y:stream.shaftTop;width:2.4;height:stream.shaftBottom-stream.shaftTop;clip:true
            Repeater {
                model:4
                Rectangle {
                    required property int index
                    objectName:"metricIconDataPacket_"+index
                    readonly property real t:((stream.phaseValue+index/4)%1+1)%1
                    readonly property real progress:stream.direction>0?t:1-t
                    width:lane.width;height:1.8+1.4*stream.signal;radius:width/2;antialiasing:true
                    y:progress*(lane.height+height)-height
                    opacity:stream.alpha*Math.max(0,Math.min(1,stream.density-index))
                    gradient:Gradient {
                        GradientStop {position:0;color:Qt.rgba(stream.packetInk.r,stream.packetInk.g,stream.packetInk.b,0)}
                        GradientStop {position:.3;color:stream.packetInk}
                        GradientStop {position:.62;color:Qt.lighter(stream.packetInk,1.35)}
                        GradientStop {position:1;color:Qt.rgba(stream.packetInk.r,stream.packetInk.g,stream.packetInk.b,0)}
                    }
                }
            }
        }
        Rectangle {
            objectName:"metricIconDiskActivityGlow"
            visible:stream.disk
            width:3;height:3;radius:1.5;x:(stream.incoming?4.5:7.5)-width/2
            y:(root.name==="disk"?12:13.5)-height/2
            color:stream.packetInk;opacity:stream.alpha*.2;antialiasing:true
        }
        Rectangle {
            objectName:"metricIconDiskActivityLight"
            visible:stream.disk
            width:1.55;height:1.55;radius:width/2;x:(stream.incoming?4.5:7.5)-width/2
            y:(root.name==="disk"?12:13.5)-height/2
            color:stream.packetInk;opacity:stream.alpha;antialiasing:true
        }
    }

    // The whole window shares one clock. RHI combines the same four weighted
    // cells in one quad; software/error paths retain the original image blend.
    component DischargeAtlas: Item {
        id:atlas
        property real amount:0
        property real densityAmount:amount
        property real phaseValue:0
        property bool warm:false
        property real layerOpacity:1
        readonly property real stagePosition:Math.max(0,Math.min(9,densityAmount*10-1))
        readonly property int lowerStage:Math.floor(stagePosition)
        readonly property real stageBlend:stagePosition-lowerStage
        readonly property real framePosition:((phaseValue%1+1)%1)*48
        readonly property int lowerFrame:Math.floor(framePosition)%48
        readonly property real frameBlend:framePosition-Math.floor(framePosition)
        property url atlasSource:warm?root.warmAtlasSource:root.blueAtlasSource
        width:18;height:18
        opacity:Math.min(1,root.channelOpacity(amount)*(["cpu","gpu"].includes(root.name)?1.08:1))
            *Math.min(1,amount*10)*layerOpacity
        readonly property bool shaderSupported: GraphicsInfo.api === GraphicsInfo.OpenGL
            || GraphicsInfo.api === GraphicsInfo.Direct3D11 || GraphicsInfo.api === GraphicsInfo.Direct3D12
            || GraphicsInfo.api === GraphicsInfo.Vulkan || GraphicsInfo.api === GraphicsInfo.Metal
        property bool shaderFailed: false
        function disableShader() { shaderFailed = true }
        Loader {
            id: shaderLayer; objectName: "metricDischargeShaderLoader"
            x:-7;y:-7;width:32;height:32
            active:atlas.shaderSupported && !atlas.shaderFailed
            sourceComponent: ShaderEffect {
                objectName:"metricDischargeShader"
                property var source: Image {source:atlas.atlasSource;visible:false;cache:true;smooth:true}
                property real stagePosition:atlas.stagePosition
                property real framePosition:atlas.framePosition
                fragmentShader:Qt.resolvedUrl("../assets/shaders/metric-discharge.frag.qsb")
                onStatusChanged:if(status===ShaderEffect.Error)Qt.callLater(atlas.disableShader)
            }
        }
        Item {
            x:-7;y:-7;width:32;height:32;clip:true;visible:!shaderLayer.active
            Repeater {
                model:shaderLayer.active?0:4
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
                            warm:true;amount:root.thermalArcStrength;phaseValue:root.heatPhase
                            densityAmount:root.processorGlyph?Math.max(amount,root.processorLoadPressure):amount
                        }
                    }
                }
                Loader {
                    objectName:"metricIconEnergyArc"
                    anchors.fill:parent;active:root.electricEnabled
                    sourceComponent:DischargeAtlas {
                        objectName:"metricIconBlueDischarge"
                        amount:root.electricActivity;phaseValue:root.electricPhase
                        densityAmount:root.processorGlyph?Math.max(amount,root.processorLoadPressure):amount
                    }
                }
                Loader {
                    objectName:"metricIconFlow"
                    anchors.fill:parent;active:root.flowActive && root.arrowFlow
                    sourceComponent:TransportStream {
                        objectName:"metricIconFlowArrow_0"
                        incoming:root.name==="disk_read" || (root.name!=="disk_write" && !root.outgoing)
                        amount:root.displayedLevel;phaseValue:root.phase
                    }
                }
                Loader {
                    objectName:"metricIconTransport"
                    anchors.fill:parent
                    active:!root.thermometerGlyph && root.animationRunning && root.compositeActive && (root.supportsInbound || root.supportsOutbound)
                    sourceComponent:Item {
                        Repeater {
                            model:2
                            Loader {
                                id:packet
                                required property int index
                                readonly property bool inbound:index===0
                                active:inbound?root.inboundActive:root.outboundActive
                                width:18;height:18
                                sourceComponent:root.transportGlyph?streamPart:legacyPart
                                Component {
                                    id:streamPart
                                    TransportStream {
                                        objectName:"metricIconTransportArc_"+packet.index
                                        incoming:packet.inbound
                                        amount:packet.inbound?root.displayedInbound:root.displayedOutbound
                                        phaseValue:packet.inbound?root.inboundPhase:(root.outboundPhase+.23)%1
                                    }
                                }
                                Component {
                                    id:legacyPart
                                    DischargeAtlas {
                                        objectName:"metricIconTransportArc_"+packet.index
                                        amount:packet.inbound?root.displayedInbound:root.displayedOutbound
                                        phaseValue:packet.inbound?root.inboundPhase:(root.outboundPhase+.23)%1
                                    }
                                }
                            }
                        }
                    }
                }
                Loader {
                    objectName:"metricIconScalarActivity"
                    anchors.fill:parent
                    active:!root.thermometerGlyph && root.animationRunning && root.resolvedEffect==="pulse" && !root.corePulse
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
                Item {
                    objectName:"metricIconRotorAssembly";anchors.fill:parent
                    rotation:(root.compositeActive?root.spinPhase:root.phase)*360
                    VectorPart {
                        objectName:"metricIconRotorTrail";fragment:root.glyphParts[0] || ""
                        strokeWidth:1.8;rotation:-16
                        opacity:root.rotorOpacity*.18*root.fanTrailStrength
                    }
                    VectorPart {
                        objectName:"metricIconRotorStructure";fragment:root.glyphParts[0] || ""
                        strokeWidth:1.8;opacity:1-Math.pow(1-root.rotorOpacity,6)
                    }
                    AccentPart {
                        objectName:"metricIconRotor";fragment:root.glyphParts[0] || "";strokeWidth:1.8
                        colors:root.compositeActive?root.spinColors:root.manualColors
                        amount:root.compositeActive?root.displayedSpin:root.displayedLevel
                        opacity:root.rotorOpacity
                    }
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
            anchors.fill:parent;visible:root.thermometerEnabled;clip:true
            readonly property real activity:root.displayedTemperature
            readonly property real alpha:Math.min(1,root.channelOpacity(activity)*1.08)
            // Local, soft warmth belongs to temperature. No atlas, travelling
            // highlight or electrical discharge is created for this glyph.
            readonly property real haloAlpha:alpha*root.thermometerWarmth*(.82+.18*root.wave)
            Repeater {
                model:heatLayer.visible?3:0
                Rectangle {
                    required property int index
                    objectName:"metricIconTemperatureHalo_"+index
                    width:8.8-index*1.9;height:width;x:9-width/2;y:13.5-height/2
                    radius:width/2;antialiasing:true;color:root.thermometerColor
                    opacity:heatLayer.haloAlpha*(.1+.045*index)
                }
            }
            Rectangle {
                objectName:"metricIconHeatMercury";x:7.5;y:12;width:3;height:3;radius:1.5;antialiasing:true
                color:root.thermometerColor;opacity:heatLayer.alpha
            }
            Rectangle {
                objectName:"metricIconTemperatureColumn"
                x:8.35;width:1.3;height:10*heatLayer.activity;y:13.5-height;radius:.65;antialiasing:true
                color:root.thermometerColor;opacity:heatLayer.alpha
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
            color:root.memoryGlyph?root.paletteColor(root.memoryColors,activity):root.compositeActive?root.loadColor:root.accentColor
            opacity:root.channelOpacity(activity)*(["cpu","gpu"].includes(root.name)?.5:.88+.12*localWave)
            Rectangle {
                objectName:"metricIconLoadHighlight"
                readonly property real progress:root.compositeActive?root.loadPhase:root.phase
                x:pulseCore.horizontal?progress*(pulseCore.width+3)-2:0
                y:pulseCore.horizontal?0:(1-progress)*(pulseCore.height+3)-1
                width:pulseCore.horizontal?(root.memoryGlyph?2.7:.8):pulseCore.width;height:pulseCore.horizontal?pulseCore.height:.65
                color:root.darkSurface?"#e9e5ff":"#d9e9ff";opacity:.8
                gradient:root.memoryGlyph?memorySweep:null
                Gradient {
                    id:memorySweep;orientation:Gradient.Horizontal
                    GradientStop {position:0;color:"transparent"}
                    GradientStop {position:.55;color:root.darkSurface?"#f5faff":"#e7f6ff"}
                    GradientStop {position:1;color:"transparent"}
                }
            }
            Loader {
                objectName:"metricIconCapacityActivity"
                active:pulseCore.visible && pulseCore.horizontal && !root.memoryGlyph
                sourceComponent:DischargeAtlas {
                    x:-pulseCore.x;y:-pulseCore.y;amount:pulseCore.activity
                    phaseValue:root.compositeActive?root.loadPhase:root.phase
                    layerOpacity:.65
                }
            }
        }
    }
}
