import QtQuick

// Independently drawn Qt content, informed by exelban/Stats Kit/Widgets (MIT).
Item {
    id: root
    property var row: ({})
    property color ink: "#202833"
    property color muted: "#566272"
    property string fontFamily: "Segoe UI Variable"
    property bool reserveValueWidth: false
    property bool motionEnabled: false
    readonly property string style: row.style || "label_value"
    readonly property bool hasLabel: style === "label_value"
    readonly property bool hasIcon: style === "icon_value"
    readonly property bool hasTrend: style === "trend_value"
    readonly property bool hasBar: style === "bar_value"
    readonly property bool hasRing: style === "ring_value"
    readonly property bool isGraph: style === "graph"
    readonly property bool isStacked: style === "stacked"
    readonly property bool isDuplexInline: style === "duplex_inline"
    readonly property bool isDuplex: style === "duplex" || isDuplexInline
    readonly property var pairRows: isDuplex ? (row.paired_rows || []).slice(0, 2) : []
    readonly property bool twoRows: isGraph || isStacked || (isDuplex && !isDuplexInline)
    // The controller owns formatting; legacy rows retain their full value.
    readonly property bool splitValue: typeof row.number_text === "string"
    readonly property string numberText: splitValue ? row.number_text : (row.value || "—")
    readonly property string unitText: splitValue ? (row.unit_text || "") : ""
    readonly property real unitGap: unitText ? 3 : 0
    readonly property bool gaugeAvailable: row.available === true && row.gauge_available === true && row.gauge_supported !== false
        && Number.isFinite(row.gauge_fraction) && row.gauge_fraction >= 0 && row.gauge_fraction <= 1
    readonly property real prefixWidth: hasLabel ? Math.min(110, labelMeasure.advanceWidth)
        : hasIcon ? 18 : hasRing ? 14 : hasTrend ? 36 : hasBar ? 22 : 0
    readonly property real contentGap: hasIcon ? 5 : prefixWidth > 0 ? 6 : 0
    readonly property real actualValueWidth: valueMeasure.advanceWidth + unitGap + unitMeasure.advanceWidth
    readonly property real valueWidth: reserveValueWidth && !isGraph
        ? Math.max(actualValueWidth, stableValueMeasure.advanceWidth + unitGap + unitMeasure.advanceWidth) : actualValueWidth
    readonly property bool labelTruncated: shortLabel.truncated
    readonly property real pairAWidth: 18 + Math.max(pairAMeasure.advanceWidth, reserveValueWidth ? pairReserveMeasure.advanceWidth : 0) + (pairAUnit.text ? 3 + pairAUnit.advanceWidth : 0)
    readonly property real pairBWidth: 18 + Math.max(pairBMeasure.advanceWidth, reserveValueWidth ? pairReserveMeasure.advanceWidth : 0) + (pairBUnit.text ? 3 + pairBUnit.advanceWidth : 0)
    readonly property real pairedWidth: isDuplexInline ? pairAWidth+12+pairBWidth : Math.max(pairAWidth, pairBWidth)
    implicitWidth: isDuplex ? Math.max(44, pairedWidth) : isGraph ? Math.max(44, valueWidth)
        : isStacked ? Math.max(Math.min(66, labelMeasure.advanceWidth), valueWidth)
        : prefixWidth + contentGap + valueWidth
    implicitHeight: twoRows ? 24 : Math.max(hasIcon ? 18 : 14, valueText.implicitHeight, hasLabel ? shortLabel.implicitHeight : 0)
    TextMetrics {id:pairAMeasure;text:root.pairRows[0] ? String(root.pairRows[0].number_text || "—") : "—";font.family:root.fontFamily;font.pixelSize:11;font.weight:Font.Medium;font.features:{"tnum":1}}
    TextMetrics {id:pairBMeasure;text:root.pairRows[1] ? String(root.pairRows[1].number_text || "—") : "—";font:pairAMeasure.font}
    TextMetrics {id:pairReserveMeasure;text:"999.9";font:pairAMeasure.font}
    TextMetrics {id:pairAUnit;text:root.pairRows[0] ? String(root.pairRows[0].unit_text || "") : "";font.family:root.fontFamily;font.pixelSize:9}
    TextMetrics {id:pairBUnit;text:root.pairRows[1] ? String(root.pairRows[1].unit_text || "") : "";font:pairAUnit.font}

    Item {
        visible: root.isDuplex
        y:root.isDuplexInline ? (root.height-12)/2 : 0
        Repeater {
            id: pairRepeater
            model: root.pairRows
            delegate: Item {
                id: pairLine
                required property var modelData
                required property int index
                objectName: "topBarPair_" + index
                implicitWidth: 18 + Math.max(pairNumber.advanceWidth, root.reserveValueWidth ? pairReserve.advanceWidth : 0)
                    + (pairLine.modelData.unit_text ? 3 + pairUnit.advanceWidth : 0)
                width: implicitWidth; height: 12
                x:root.isDuplexInline && index===1 ? root.pairAWidth+12 : 0
                y:root.isDuplexInline ? 0 : index*12
                TextMetrics { id: pairNumber; text: String(pairLine.modelData.number_text || "—"); font.family:root.fontFamily; font.pixelSize:11; font.weight:Font.Medium; font.features: {"tnum":1} }
                TextMetrics { id: pairReserve; text:"999.9"; font:pairNumber.font }
                TextMetrics { id: pairUnit; text:String(pairLine.modelData.unit_text || "");font.family:root.fontFamily;font.pixelSize:9 }
                MetricIcon {
                    width:11;height:11;y:.5
                    name: ["download","read","charge"].includes(pairLine.modelData.direction) ? "download" : "upload"
                    ink:root.muted
                    metric: pairLine.modelData.metric || ""
                    effect: root.row.icon_effect || "off"
                    level: pairLine.modelData.effect_level === undefined ? null : pairLine.modelData.effect_level
                    available: pairLine.modelData.available === true && Number.isFinite(pairLine.modelData.numeric_value)
                    motionEnabled: root.motionEnabled
                }
                Text {
                    id: pairValue
                    objectName:"topBarPairNumber_"+pairLine.index
                    x:18; y:(parent.height-height)/2
                    text:pairNumber.text; textFormat:Text.PlainText; font:pairNumber.font
                    color:pairLine.modelData.available === true ? root.ink : root.muted
                }
                Text {
                    x:pairValue.x+pairNumber.advanceWidth+3
                    y:pairValue.y+pairValue.baselineOffset-baselineOffset
                    text:pairUnit.text; textFormat:Text.PlainText; font:pairUnit.font; color:root.muted
                }
            }
        }
    }

    TextMetrics {
        id: labelMeasure
        font.family: root.fontFamily
        font.pixelSize: root.isStacked ? 9 : 11
        font.weight: Font.Normal
        text: root.row.bar_label || root.row.label || ""
    }
    TextMetrics {
        id: valueMeasure
        font.family: root.fontFamily
        font.pixelSize: root.isGraph ? 9 : root.isStacked ? 11 : 12
        font.weight: Font.Medium
        font.features: { "tnum": 1 }
        text: root.numberText
    }
    TextMetrics {
        id: unitMeasure
        font.family: root.fontFamily
        font.pixelSize: root.twoRows ? 9 : 10
        font.weight: Font.Normal
        text: root.unitText
    }
    TextMetrics {
        id: stableValueMeasure
        font: valueMeasure.font
        text: root.splitValue ? (root.row.number_reserve || "999.9") : "999.9 " + (root.row.unit || "")
    }
    Text {
        id: shortLabel
        objectName: "topBarContentLabel"
        visible: root.hasLabel || root.isStacked
        width: root.isStacked ? Math.min(66, root.implicitWidth) : root.prefixWidth
        y: root.isStacked ? 0 : (parent.height - height) / 2
        text: labelMeasure.text
        textFormat: Text.PlainText
        color: root.muted
        font: labelMeasure.font
        elide: Text.ElideRight
    }
    MetricIcon {
        objectName: "topBarContentIcon"
        visible: root.hasIcon
        width: 18; height: 18
        anchors.verticalCenter: parent.verticalCenter
        name: root.row.icon || "sensors"
        ink: root.row.available === true ? root.ink : root.muted
        metric: root.row.metric || ""
        effect: root.row.icon_effect || "off"
        level: root.row.effect_level === undefined ? null : root.row.effect_level
        available: root.row.available === true && Number.isFinite(root.row.numeric_value)
        motionEnabled: root.motionEnabled
    }
    Canvas {
        id: trend
        objectName: "topBarContentTrend"
        visible: root.hasTrend || root.isGraph
        width: root.isGraph ? root.implicitWidth : 36
        height: root.isGraph ? 10 : 14
        y: root.isGraph ? 0 : (parent.height - height) / 2
        antialiasing: true
        onVisibleChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            if (root.row.trend_available !== true || root.row.available !== true) {
                ctx.strokeStyle = Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.3)
                ctx.lineWidth = 1
                ctx.beginPath(); ctx.moveTo(width / 2 - 3, height / 2); ctx.lineTo(width / 2 + 3, height / 2); ctx.stroke()
                return
            }
            ctx.strokeStyle = root.ink
            ctx.lineWidth = 1
            ctx.lineJoin = "round"
            ctx.lineCap = "round"
            let connected = false
            ctx.beginPath()
            for (const point of root.row.trend_points || []) {
                if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)
                        || point.x < 0 || point.x > 1 || point.y < 0 || point.y > 1) {
                    connected = false
                    continue
                }
                const px = 1 + point.x * (width - 2)
                const py = 1 + point.y * (height - 2)
                if (connected) ctx.lineTo(px, py)
                else ctx.moveTo(px, py)
                connected = true
            }
            ctx.stroke()
        }
    }
    Canvas {
        id: gauge
        objectName: "topBarContentGauge"
        visible: root.hasBar || root.hasRing
        width: root.hasBar ? 22 : 14
        height: 14
        anchors.verticalCenter: parent.verticalCenter
        antialiasing: true
        onVisibleChanged: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            const track = Qt.rgba(root.muted.r, root.muted.g, root.muted.b, 0.26)
            const fill = root.row.available === true ? root.ink : root.muted
            ctx.lineWidth = 1
            if (root.hasBar) {
                ctx.fillStyle=track
                ctx.beginPath(); ctx.roundedRect(1, 4, 20, 6, 3, 3); ctx.fill()
                if (root.gaugeAvailable && root.row.gauge_fraction > 0) {
                    ctx.save(); ctx.clip(); ctx.fillStyle=fill
                    ctx.fillRect(1, 4, 20 * root.row.gauge_fraction, 6); ctx.restore()
                }
            } else if (root.row.metric === "battery_percent") {
                ctx.strokeStyle = track
                ctx.strokeRect(0.5, 3.5, 11, 7)
                ctx.fillStyle = track
                ctx.fillRect(12, 5, 1.5, 4)
                if (root.gaugeAvailable) {
                    ctx.fillStyle = fill
                    ctx.fillRect(2, 5, 8 * root.row.gauge_fraction, 4)
                }
            } else {
                ctx.strokeStyle = track
                ctx.lineWidth = 2
                ctx.beginPath(); ctx.arc(7, 7, 5, 0, Math.PI * 2); ctx.stroke()
                if (root.gaugeAvailable && root.row.gauge_fraction > 0) {
                    ctx.strokeStyle = fill
                    ctx.lineCap = "round"
                    ctx.beginPath(); ctx.arc(7, 7, 5, -Math.PI / 2, -Math.PI / 2 + root.row.gauge_fraction * Math.PI * 2); ctx.stroke()
                }
            }
            if (!root.gaugeAvailable) {
                ctx.strokeStyle = root.muted
                ctx.lineWidth = 1
                ctx.beginPath(); ctx.moveTo(width / 2 - 2, 7); ctx.lineTo(width / 2 + 2, 7); ctx.stroke()
            }
        }
    }
    Text {
        id: valueText
        visible: !root.isDuplex
        objectName: "topBarContentValue"
        x: root.twoRows ? 0 : root.prefixWidth + root.contentGap
        y: root.twoRows ? parent.height - height : (parent.height - height) / 2
        text: valueMeasure.text
        textFormat: Text.PlainText
        color: root.row.available === true ? root.ink : root.muted
        font: valueMeasure.font
    }
    Text {
        objectName: "topBarContentUnit"
        visible: !root.isDuplex && !!root.unitText
        x: valueText.x + valueMeasure.advanceWidth + root.unitGap
        y: valueText.y + valueText.baselineOffset - baselineOffset
        text: root.unitText
        textFormat: Text.PlainText
        color: root.muted
        font: unitMeasure.font
    }
    function redraw() { trend.requestPaint(); gauge.requestPaint() }
    onRowChanged: redraw()
    onInkChanged: redraw()
    onMutedChanged: redraw()
}
