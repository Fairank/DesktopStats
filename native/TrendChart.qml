import QtQuick
import QtQuick.Controls
import QtQuick.Window

Item {
    id: root
    objectName: "trendChart"
    property var series: []
    property real rangeStart: NaN
    property real rangeEnd: NaN
    property real minimum: NaN
    property real maximum: NaN
    property string unit: ""
    property bool loading: false
    property string errorText: ""
    property string emptyText: ui.t("这段时间还没有记录")
    property bool motionEnabled: ui.motionAllowed
    property real hoverTimestamp: NaN
    readonly property bool hasTimeRange: Number.isFinite(rangeStart) && Number.isFinite(rangeEnd) && rangeEnd > rangeStart
    readonly property bool compatibleUnits: series.every(row => !row.unit || row.unit === root.unit)
    readonly property var finitePoints: {
        const result = []
        for (let row = 0; row < series.length; ++row)
            for (const point of series[row].points || [])
                if (validPoint(point)) result.push({timestamp:point.timestamp, value:point.value, minimum:point.minimum, peak:point.peak, row:row})
        return result
    }
    readonly property bool hasRanges: finitePoints.some(point=>validRange(point) && point.peak>point.minimum)
    readonly property bool hasData: finitePoints.length > 0 && hasTimeRange && compatibleUnits
    readonly property var axis: {
        const values = finitePoints.reduce((values,point)=>values.concat(validRange(point)?[point.value,point.minimum,point.peak]:[point.value]),[])
        let low = Number.isFinite(minimum) ? minimum : values.length ? Math.min(0, ...values) : 0
        let high = Number.isFinite(maximum) ? maximum : values.length ? Math.max(0, ...values) : 1
        if (high < low) { low = 0; high = 1 }
        if (high === low) { const padding = Math.max(1, Math.abs(low) * .05); low -= padding; high += padding }
        return {low:low, high:high}
    }
    readonly property real axisWidth: Math.min(80, Math.max(40, Math.max(highMeasure.width, lowMeasure.width) + 10))
    readonly property rect plotRect: Qt.rect(axisWidth, 18, Math.max(1, width-axisWidth-8), Math.max(80, height-48))
    readonly property var hoverRows: {
        if (!Number.isFinite(hoverTimestamp)) return []
        return series.map((row,index) => {
            const point = (row.points || []).find(point => validPoint(point) && Math.abs(point.timestamp-hoverTimestamp) < .001)
            return {label:row.label || row.id || "", value:point ? formatValue(point.value) : "—", color:row.color || colorAt(index),
                range:validRange(point) && point.peak>point.minimum?formatValue(point.minimum)+" – "+formatValue(point.peak)+(root.unit?" "+root.unit:""):""}
        })
    }
    readonly property var sampleTimes: Array.from(new Set(finitePoints.map(point => point.timestamp))).sort((a,b) => a-b)
    signal pointHovered(real timestamp)
    implicitWidth: 580
    implicitHeight: 242
    activeFocusOnTab: true
    Accessible.role: Accessible.Chart
    Accessible.name: ui.t("历史趋势")
    Accessible.description: hasData ? sampleTimes.length + " " + ui.t("个采样点") + ", " + unit : loading ? ui.t("正在读取记录") : errorText || emptyText
    Theme { id: ui }
    TextMetrics { id: highMeasure; font.family:ui.fontFamily; font.pixelSize:11; text:root.formatAxis(root.axis.high) }
    TextMetrics { id: lowMeasure; font.family:ui.fontFamily; font.pixelSize:11; text:root.formatAxis(root.axis.low) }

    function validPoint(point) {
        return !!point && point.available !== false && typeof point.timestamp === "number" && Number.isFinite(point.timestamp)
            && typeof point.value === "number" && Number.isFinite(point.value)
            && (!hasTimeRange || point.timestamp >= rangeStart && point.timestamp <= rangeEnd)
    }
    function validRange(point) {
        return validPoint(point) && typeof point.minimum==="number" && Number.isFinite(point.minimum)
            && typeof point.peak==="number" && Number.isFinite(point.peak)
            && point.minimum<=point.value && point.value<=point.peak
    }
    function colorAt(index) { return index === 0 ? (ui.dark ? "#79b5ff" : "#216ac7") : (ui.dark ? "#c6a0ff" : "#8651b8") }
    function formatAxis(value) {
        if (!Number.isFinite(value)) return "—"
        return value === 0 ? "0" : Math.abs(value) >= 100000 || Math.abs(value) < .01 ? value.toExponential(2) : Number(value.toPrecision(3)).toString()
    }
    function formatValue(value) {
        if (!Number.isFinite(value)) return "—"
        return Math.abs(value) >= 1000 ? formatAxis(value) : Number(value.toFixed(2)).toString()
    }
    function axisAt(fraction) { return axis.low*(1-fraction)+axis.high*fraction }
    function timeLabel(timestamp, full) {
        if (!Number.isFinite(timestamp)) return ""
        const date = new Date(timestamp * 1000)
        if (full) return date.toLocaleString(Qt.locale(), "MM/dd hh:mm:ss")
        return date.toLocaleString(Qt.locale(), rangeEnd-rangeStart >= 86400 ? "MM/dd hh:mm" : rangeEnd-rangeStart <= 300 ? "hh:mm:ss" : "hh:mm")
    }
    function pointX(timestamp) { return plotRect.x + (timestamp-rangeStart)/(rangeEnd-rangeStart) * plotRect.width }
    function pointY(value) {
        const span = axis.high-axis.low
        const position = Number.isFinite(span) ? (axis.high-value)/span : (axis.high/2-value/2)/(axis.high/2-axis.low/2)
        return plotRect.y + Math.max(0, Math.min(1, position)) * plotRect.height
    }
    function pickAt(x) {
        if (!hasData || !finitePoints.length) { hoverTimestamp=NaN; return }
        let nearest=finitePoints[0], distance=Infinity
        for (const point of finitePoints) {
            const next=Math.abs(pointX(point.timestamp)-x)
            if(next<distance) { nearest=point; distance=next }
        }
        hoverTimestamp=nearest.timestamp
        pointHovered(hoverTimestamp)
    }
    function moveCursor(step) {
        if (!sampleTimes.length) return
        let index=sampleTimes.indexOf(hoverTimestamp)
        if(index<0)index=step<0?sampleTimes.length: -1
        hoverTimestamp=sampleTimes[Math.max(0,Math.min(sampleTimes.length-1,index+step))]
        pointHovered(hoverTimestamp)
    }
    onSeriesChanged: { hoverTimestamp=NaN; plot.requestPaint() }
    onAxisChanged: plot.requestPaint()
    onPlotRectChanged: plot.requestPaint()
    onRangeStartChanged: plot.requestPaint()
    onRangeEndChanged: plot.requestPaint()
    onCompatibleUnitsChanged: plot.requestPaint()
    Keys.onPressed: event => {
        if(event.key===Qt.Key_Left)moveCursor(-1)
        else if(event.key===Qt.Key_Right)moveCursor(1)
        else if(event.key===Qt.Key_Home && sampleTimes.length)hoverTimestamp=sampleTimes[0]
        else if(event.key===Qt.Key_End && sampleTimes.length)hoverTimestamp=sampleTimes[sampleTimes.length-1]
        else if(event.key===Qt.Key_Escape)hoverTimestamp=NaN
        else { event.accepted=false; return }
        event.accepted=true
    }

    Text { objectName:"trendAxisUnit"; x:0; y:0; width:root.axisWidth-8; text:root.unit; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; elide:Text.ElideRight; visible:root.hasData }
    Repeater {
        model:3
        Text {
            required property int index
            objectName:"trendAxisTick_"+index
            x:0; y:root.plotRect.y+index*root.plotRect.height/2-height/2; width:root.axisWidth-10
            text:root.formatAxis(root.axisAt(1-index/2))
            color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11
            horizontalAlignment:Text.AlignRight; visible:root.hasData
        }
    }
    Row {
        x:root.plotRect.x;y:0;width:root.plotRect.width;spacing:12;visible:root.series.length>1 && root.hasData
        Repeater {
            model:root.series
            Row {
                required property var modelData
                required property int index
                width:Math.min((root.plotRect.width-12*(root.series.length-1))/root.series.length,label.implicitWidth+12);spacing:6
                Rectangle {width:6;height:6;radius:3;color:modelData.color || root.colorAt(index);anchors.verticalCenter:parent.verticalCenter}
                Text {id:label;width:parent.width-12;text:modelData.label || modelData.id || "";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;elide:Text.ElideRight}
            }
        }
    }
    Repeater {
        model:3
        Text {
            required property int index
            objectName:"trendTimeTick_"+index
            x:index===0?root.plotRect.x:index===1?root.plotRect.x+root.plotRect.width/2-width/2:root.plotRect.x+root.plotRect.width-width
            y:root.plotRect.y+root.plotRect.height+10
            text:root.timeLabel(root.rangeStart+index*(root.rangeEnd-root.rangeStart)/2,false)
            color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; visible:root.hasData
        }
    }
    Canvas {
        id:plot
        objectName:"trendPlot"
        anchors.fill:parent
        visible:root.hasData && !root.loading && !root.errorText
        onPaint: {
            const ctx=getContext("2d")
            ctx.reset()
            const p=root.plotRect
            ctx.strokeStyle=ui.line; ctx.lineWidth=1
            for(let row=0;row<3;++row) { const y=p.y+p.height*row/2;ctx.beginPath();ctx.moveTo(p.x,y);ctx.lineTo(p.x+p.width,y);ctx.stroke() }
            for(let col=1;col<4;++col) { const x=p.x+p.width*col/4;ctx.beginPath();ctx.moveTo(x,p.y);ctx.lineTo(x,p.y+p.height);ctx.stroke() }
            ctx.save();ctx.beginPath();ctx.rect(p.x-2,p.y-2,p.width+4,p.height+4);ctx.clip()
            for(let row=0;row<root.series.length;++row) {
                const series=root.series[row], points=series.points || []
                ctx.strokeStyle=series.color || root.colorAt(row);ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=1;ctx.lineJoin="miter";ctx.miterLimit=3;ctx.lineCap="butt"
                // A bin's extrema are real observations, not extra trend samples.
                // Independent whiskers never invent a peak trajectory or bridge a gap.
                ctx.globalAlpha=0.26;ctx.beginPath()
                for(const point of points)if(root.validRange(point) && point.peak>point.minimum) {
                    const x=root.pointX(point.timestamp)
                    ctx.moveTo(x,root.pointY(point.minimum));ctx.lineTo(x,root.pointY(point.peak))
                }
                ctx.stroke();ctx.globalAlpha=1;ctx.lineWidth=2
                let segments=[],segment=[],previous=null,last=null
                for(const point of points) {
                    if(!root.validPoint(point) || previous && point.timestamp<previous.timestamp) {
                        if(segment.length)segments.push(segment)
                        segment=[];previous=null
                        if(!root.validPoint(point))continue
                    }
                    segment.push(point);previous=point;last=point
                }
                if(segment.length)segments.push(segment)
                for(const segment of segments) {
                    if(segment.length>1) {
                        ctx.globalAlpha=ui.dark ? 0.09 : 0.065
                        ctx.beginPath();ctx.moveTo(root.pointX(segment[0].timestamp),p.y+p.height)
                        for(const point of segment)ctx.lineTo(root.pointX(point.timestamp),root.pointY(point.value))
                        ctx.lineTo(root.pointX(segment[segment.length-1].timestamp),p.y+p.height);ctx.closePath();ctx.fill();ctx.globalAlpha=1
                    }
                    ctx.beginPath()
                    for(let at=0;at<segment.length;++at) {
                        const point=segment[at],x=root.pointX(point.timestamp),y=root.pointY(point.value)
                        if(at)ctx.lineTo(x,y);else ctx.moveTo(x,y)
                    }
                    ctx.stroke()
                }
                // Sparse samples remain visibly sparse rather than implying a long history.
                if(points.filter(point=>root.validPoint(point)).length<=6)
                    for(const point of points)if(root.validPoint(point)) {ctx.beginPath();ctx.arc(root.pointX(point.timestamp),root.pointY(point.value),2.5,0,Math.PI*2);ctx.fill()}
                if(last) {ctx.beginPath();ctx.arc(root.pointX(last.timestamp),root.pointY(last.value),3,0,Math.PI*2);ctx.fill()}
            }
            ctx.restore()
        }
    }
    Rectangle {
        objectName:"trendCursor"
        visible:root.hasData && Number.isFinite(root.hoverTimestamp) && !root.loading && !root.errorText
        x:root.pointX(root.hoverTimestamp);y:root.plotRect.y;width:1;height:root.plotRect.height
        color:ui.dark?"#5affffff":"#45000000"
    }
    HoverHandler {
        id:hover
        onPointChanged:if(hovered && point.position.x>=root.plotRect.x && point.position.x<=root.plotRect.x+root.plotRect.width)root.pickAt(point.position.x)
        onHoveredChanged:if(!hovered && !root.activeFocus)root.hoverTimestamp=NaN
    }
    TapHandler { onTapped: {root.forceActiveFocus();root.pickAt(point.position.x)} }
    Rectangle {
        id:reading
        objectName:"trendHoverReadout"
        visible:root.hasData && Number.isFinite(root.hoverTimestamp) && !root.loading && !root.errorText
        x:Math.max(root.plotRect.x,Math.min(root.width-width,root.pointX(root.hoverTimestamp)+12))
        y:root.plotRect.y+6;width:Math.min(242,root.plotRect.width);height:readingColumn.implicitHeight+18
        radius:8;color:ui.popupTop;border.color:ui.line
        Column {
            id:readingColumn
            anchors.fill:parent;anchors.margins:9;spacing:7
            Text {width:parent.width;text:root.timeLabel(root.hoverTimestamp,true);color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;elide:Text.ElideRight}
            Repeater {
                model:root.hoverRows
                Column {
                    required property var modelData
                    width:readingColumn.width;spacing:3
                    Row {
                        width:parent.width;spacing:7
                        Rectangle {width:6;height:6;radius:3;color:modelData.color;anchors.verticalCenter:parent.verticalCenter}
                        Text {width:parent.width-valueLabel.width-20;text:modelData.label;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;elide:Text.ElideRight}
                        Text {id:valueLabel;text:modelData.value+(modelData.value!=="—" && root.unit?" "+root.unit:"");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;font.weight:Font.Medium}
                    }
                    Text {visible:!!modelData.range;width:parent.width;text:ui.t("区间范围")+" "+modelData.range;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;elide:Text.ElideRight}
                }
            }
        }
    }
    Column {
        objectName:"trendEmptyState"
        anchors.centerIn:parent;width:Math.max(1,parent.width-32);spacing:10
        visible:!root.hasData || root.loading || !!root.errorText
        BusyIndicator {anchors.horizontalCenter:parent.horizontalCenter;width:28;height:28;visible:root.loading;running:visible && root.motionEnabled}
        Icon {anchors.horizontalCenter:parent.horizontalCenter;width:26;height:26;name:root.errorText?"sensors":"time";ink:ui.muted;visible:!root.loading}
        Text {width:parent.width;text:root.loading?ui.t("正在读取记录"):root.errorText || (!root.compatibleUnits?ui.t("不同单位的读数不能共用量程"):root.emptyText);color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.WordWrap}
    }
    Rectangle {anchors.fill:parent;color:"transparent";radius:8;border.color:ui.accent;border.width:root.activeFocus?1:0}
}
