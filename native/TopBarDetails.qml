import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import DesktopStats 1.0

Window {
    id: root
    objectName: "topBarDetailsWindow"
    required property var barState
    property bool nativeHosted: false
    property bool nativeRounded: false
    readonly property var detail: barState.detail || ({})
    readonly property bool overflowMode: detail.overflow === true
    readonly property var groupRows:detail.grouped===true?(detail.group_rows || []).slice(0,4):[]
    readonly property bool hasGroup:groupRows.length>1
    readonly property var cpuContext: detail.cpu_context || ({})
    readonly property bool hasCpuContext: detail.cpu_context !== undefined
        && detail.cpu_context !== null && !overflowMode
    readonly property var cpuRelatedRows: (cpuContext.related_rows || []).filter(row =>
        row.metric !== root.detail.metric
        && !root.groupRows.some(member => member.metric === row.metric)
        && !root.pairedRows.some(member => member.metric === row.metric))
    readonly property int coreColumns: cpuCells.count > 16 ? 8 : 4
    readonly property var relatedRows: (detail.related || []).filter(row => {
        if (!row.metric) return true
        if (root.pairedRows.some(pair => pair.metric === row.metric)) return false
        if (root.groupRows.some(member => member.metric === row.metric)) return false
        if (root.hasCpuContext && root.cpuRelatedRows.some(member => member.metric === row.metric)) return false
        return !root.hasCapacity || !["ram_used_gb","ram_total_gb","vram_gb","vram_total_gb","disk_used_gb","disk_total_gb"].includes(row.metric)
    }).slice(0, 12)
    readonly property var availableRows: relatedRows.filter(row => root.relatedAvailable(row))
    readonly property var missingRows: relatedRows.filter(row => !root.relatedAvailable(row))
    readonly property var pairedRows: (detail.paired_rows || []).slice(0, 2)
    readonly property bool hasPair: pairedRows.length === 2
    readonly property var capacity: detail.capacity_summary || ({})
    readonly property bool hasCapacity: typeof capacity.used_text === "string" && !!capacity.used_text
        && typeof capacity.total_text === "string" && !!capacity.total_text
        && Number.isFinite(capacity.fraction) && capacity.fraction >= 0 && capacity.fraction <= 1
    readonly property color foreground: barState.ink
    readonly property color secondary: barState.muted
    readonly property bool hasTrend: hasPair ? pairedRows.some(row => root.trendReadable(row)) : root.trendReadable(detail)
    readonly property var chartRows: hasPair ? pairedRows : [detail]
    readonly property var chartScale: scaleFor(chartRows)
    readonly property string deviceName: {
        const value = String(cpuContext.hardware_name || detail.hardware_name || "").trim()
        return /^(\d+|auto|all|system)$/i.test(value) ? "" : value
    }
    readonly property int sampleCount: Number.isInteger(detail.history_samples)
        ? detail.history_samples : (detail.history || []).length
    readonly property bool dark: foreground.r > 0.5
    property bool showMissing: false
    property bool showMetadata: false
    onCpuContextChanged: syncCpuRows()
    Component.onCompleted: syncCpuRows()

    ListModel { id: cpuCells }

    function syncCpuRows() {
        if (!cpuCells) return
        const rows = cpuContext.logical_rows || []
        for (let index = 0; index < rows.length; index++) {
            const row = rows[index]
            const valid = row.available === true && typeof row.numeric_value === "number"
                && Number.isFinite(row.numeric_value) && row.numeric_value >= 0 && row.numeric_value <= 100
            const record = {
                logicalIndex: Number.isInteger(row.index) && row.index >= 0 ? row.index : -1,
                logicalLabel: String(row.label || ""),
                usageText: valid && typeof row.value === "string" ? row.value : "—",
                readingAvailable: valid, usageFraction: valid ? row.numeric_value / 100 : 0,
                readingReason: String(row.reason || cpuContext.reason || ""),
                readingSource: String(row.source || cpuContext.source || "")
            }
            if (index >= cpuCells.count) cpuCells.append(record)
            else {
                const before = cpuCells.get(index)
                if (Object.keys(record).some(key => before[key] !== record[key])) cpuCells.set(index, record)
            }
        }
        if (cpuCells.count > rows.length) cpuCells.remove(rows.length, cpuCells.count - rows.length)
    }
    function cpuCounts() {
        const counts = []
        if (Number.isInteger(cpuContext.physical_cores) && cpuContext.physical_cores > 0)
            counts.push(cpuContext.physical_cores + " " + root.tr("物理核心"))
        if (Number.isInteger(cpuContext.logical_processors) && cpuContext.logical_processors > 0)
            counts.push(cpuContext.logical_processors + " " + root.tr("逻辑处理器"))
        return counts.join(" · ")
    }

    visible: false
    color: "transparent"
    width: 336
    height: Math.min(barState.panelMaximumHeight, panelContent.implicitHeight + 32)
    // The manager decides focus flags before retaining this window's HWND.
    flags: nativeHosted ? Qt.Widget : Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
    title: "Desktop Stats"
    onClosing: function(event) {
        event.accepted = false
        root.barState.closePanel()
    }
    onDetailChanged: {
        if (root.detail.id !== root.previousId) {
            root.showMissing = false
            root.showMetadata = false
            root.previousId = root.detail.id || ""
            metricScroll.contentY = 0
        }
        history.requestPaint()
    }
    property string previousId: ""

    function tint(alpha) { return Qt.rgba(foreground.r, foreground.g, foreground.b, alpha) }
    function relatedAvailable(row) {
        if (typeof row.available === "boolean") return row.available
        return !!row.value && row.value !== "—"
    }
    function tr(text) {
        // Python slots do not expose their internal language-property reads.
        const language = root.barState.config.language
        return root.barState.tr(text)
    }
    function validPoint(point) {
        return !!point && Number.isFinite(point.x) && Number.isFinite(point.y)
            && point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1
    }
    function trendReadable(row) {
        return row.available === true && row.trend_available === true
            && (row.trend_points || []).some((point, index, points) => index > 0
                && root.validPoint(point) && root.validPoint(points[index - 1]))
    }
    function pairColor(index) {
        return foreground.r > 0.5 ? (index === 0 ? "#75b3ff" : "#cc9aff")
            : (index === 0 ? "#246dcb" : "#9550bf")
    }
    function seriesColor(index) {
        return root.pairedRows[index] && root.pairedRows[index].available !== true ? root.secondary : root.pairColor(index)
    }
    function readingTip(row) { return [row.label, row.value, row.source, row.reason].filter(value => !!value).join("\n") }
    function pairLabel(row) {
        return row.label || root.tr(({download:"下载", down:"下载", upload:"上传", up:"上传", read:"读取", write:"写入"})[row.direction] || row.direction || "")
    }
    function readingNumber(row) {
        if (row.available !== true) return "—"
        return typeof row.number_text === "string" ? row.number_text : (row.value || "—")
    }
    function readingUnit(row) { return row.available === true && typeof row.number_text === "string" ? (row.unit_text || "") : "" }
    function directionIcon(row) {
        return ({download:"download", down:"download", upload:"upload", up:"upload", read:"disk_read", write:"disk_write", charge:"power", discharge:"battery"})[row.direction] || row.icon || "sensors"
    }
    function finiteValues(row) {
        return (row.trend || row.history || []).filter(value => typeof value === "number" && Number.isFinite(value))
    }
    function scaleFor(rows) {
        if (!rows.length) return {valid:false, low:0, high:0}
        const first = rows[0]
        const low = root.hasPair ? first.trend_minimum : first.trend_min
        const high = root.hasPair ? first.trend_maximum : first.trend_max
        if (typeof low === "number" && Number.isFinite(low) && typeof high === "number" && Number.isFinite(high) && high >= low)
            return {valid:true, low:low, high:high}
        const values = rows.reduce((all, row) => all.concat(root.finiteValues(row)), [])
        return values.length ? {valid:true, low:Math.min(0, ...values), high:Math.max(0, ...values)} : {valid:false, low:0, high:0}
    }
    function axisNumber(value) {
        if (typeof value !== "number" || !Number.isFinite(value)) return "—"
        const magnitude = Math.abs(value)
        if (value === 0) return "0"
        return magnitude >= 100000 || magnitude < .01 ? value.toExponential(2) : Number(value.toPrecision(3)).toString()
    }
    function summaryNumber(row, mode) {
        const values = root.finiteValues(row)
        if (!values.length || row.available !== true) return "—"
        const supplied = mode === "peak" ? row.history_max : row.history_mean
        const value = typeof supplied === "number" && Number.isFinite(supplied) ? supplied
            : mode === "peak" ? Math.max(...values) : values.reduce((a,b) => a + b/values.length, 0)
        const original = String(row.number_text || "")
        const decimals = original.includes(".") ? Math.min(2, original.length-original.indexOf(".")-1) : 0
        return value.toFixed(decimals) + (row.unit ? " " + row.unit : "")
    }
    function spanText() {
        const value = root.detail.history_elapsed_s
        if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return ""
        return value >= 60 ? (value/60).toFixed(value < 600 ? 1 : 0)+" min" : value.toFixed(value < 10 ? 1 : 0)+" s"
    }
    function chartPoints(row) {
        const values = row.trend || row.history || []
        if (!root.chartScale.valid || !values.length) return row.trend_points || []
        const lo = root.chartScale.low, hi = root.chartScale.high, span = hi-lo
        return values.map((value,index) => {
            if (typeof value !== "number" || !Number.isFinite(value)) return null
            const y = hi===lo ? .5 : Number.isFinite(span) ? (hi-value)/span : (hi/2-value/2)/(hi/2-lo/2)
            const original=(row.trend_points || [])[index]
            const x=root.validPoint(original)?original.x:index/Math.max(1,values.length-1)
            return {x:x,y:Math.max(0,Math.min(1,y))}
        })
    }

    component PlainTip: ToolTip {
        id: tip
        delay: 550
        padding: 9
        contentItem: Text {
            text: tip.text; textFormat: Text.PlainText; color: root.foreground
            font.family: root.barState.fontFamily; font.pixelSize: 11
            wrapMode: Text.Wrap; width: Math.min(300, implicitWidth)
        }
        background: MaterialSurface { config: root.barState.config; frosted: false; cornerRadius: 8 }
    }
    component QuietScrollBar: ScrollBar {
        id: scrollHandle
        policy: ScrollBar.AsNeeded
        visible: size < 0.999
        padding: 1
        contentItem: Rectangle {
            implicitWidth: 3; implicitHeight: 24; radius: 1.5
            color: root.tint(scrollHandle.pressed ? 0.4 : 0.23)
        }
        background: null
    }
    component HeaderButton: ToolButton {
        id: tool
        property string glyph: "close"
        Layout.preferredWidth: 28; Layout.minimumHeight: 28
        Layout.preferredHeight: 28; Layout.maximumHeight: 28
        padding: 6; focusPolicy: Qt.TabFocus; hoverEnabled: true
        contentItem: Icon { name: tool.glyph; ink: root.secondary }
        background: Rectangle {
            radius: 7; color: root.tint(tool.down ? 0.12 : 0.07)
            visible: tool.hovered || tool.visualFocus || tool.down
            border.width: tool.visualFocus ? 1 : 0
            border.color: root.tint(0.35)
        }
    }

    MaterialSurface {
        objectName: "topBarDetailsMaterialSurface"
        anchors.fill: parent; config: root.barState.config
        frosted: root.barState.detailCoatingTranslucent; cornerRadius: root.nativeRounded ? 0 : 16
    }
    HoverHandler {
        onHoveredChanged: {
            if (hovered) root.barState.enterPanel()
            else root.barState.leavePanel()
        }
    }
    Shortcut {
        sequence: "Escape"; context: Qt.WindowShortcut; enabled: root.active
        onActivated: root.barState.closePanel()
    }
    ColumnLayout {
        id: panelContent
        anchors.fill: parent; anchors.margins: 16
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: 28; Layout.preferredHeight: 28; Layout.maximumHeight: 28
            spacing: 6
            MetricIcon {
                visible: !root.overflowMode
                name: ({network:"network",disk_io:"disk",volume:"disk",storage:"disk",cooling:"fan",memory:"memory",cpu:"cpu",gpu:"gpu",battery:"battery",power:"power"})[root.detail.family] || root.detail.icon || "sensors"; ink: root.secondary
                Layout.preferredWidth: 16; Layout.preferredHeight: 16
                metric: root.detail.metric || ""
                effect: root.detail.icon_effect || "off"
                level: root.detail.effect_level === undefined ? null : root.detail.effect_level
                intensity: root.detail.effect_intensity === undefined ? 0.5 : root.detail.effect_intensity
                speed: root.detail.effect_speed === undefined ? 1 : root.detail.effect_speed
                available: root.detail.available === true && Number.isFinite(root.detail.numeric_value)
                motionEnabled: root.barState.motionEnabled === true
            }
            Text {
                id: detailTitle
                objectName: "topBarDetailTitle"
                Layout.fillWidth: true; Layout.minimumWidth: 0
                text: (root.hasGroup || root.hasPair) && root.detail.group_label ? root.detail.group_label
                    : root.detail.label || (root.overflowMode ? root.tr("更多指标") : "")
                textFormat: Text.PlainText; color: root.foreground
                font.family: root.barState.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold
                elide: Text.ElideRight
                HoverHandler { id: titleHover }
                PlainTip { visible: titleHover.hovered && detailTitle.truncated; text: detailTitle.text }
            }
            HeaderButton {
                id: historyButton
                objectName: "topBarDetailsHistory"
                visible: root.detail.history_recordable === true
                glyph: "time"
                Accessible.name: root.tr("查看历史记录")
                onClicked: root.barState.openHistory()
                PlainTip { visible: historyButton.hovered; text: root.tr("查看历史记录") }
            }
            HeaderButton {
                id: editButton
                objectName: "topBarDetailsEdit"
                glyph: "sliders"
                Accessible.name: root.tr("编辑顶部栏")
                onClicked: root.barState.openSettings()
                PlainTip { visible: editButton.hovered; text: root.tr("编辑顶部栏") }
            }
            HeaderButton {
                id: closeButton
                objectName: "topBarDetailsClose"
                Accessible.name: root.tr("关闭")
                onClicked: root.barState.closePanel()
                PlainTip { visible: closeButton.hovered; text: root.tr("关闭") }
            }
        }
        Text {
            id: deviceSummary
            objectName: "topBarDetailDeviceName"
            visible: !root.overflowMode && !!root.deviceName
            Layout.fillWidth: true; Layout.minimumWidth: 0
            text: root.deviceName; textFormat: Text.PlainText
            color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 11
            elide: Text.ElideRight
            HoverHandler { id: deviceHover }
            PlainTip { visible: deviceHover.hovered && deviceSummary.truncated; text: root.deviceName }
        }
        Item {
            id: detailBody
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
            implicitHeight: root.overflowMode
                ? Math.min(320, Math.max(36, overflowList.count * 36)) : metricContent.implicitHeight
            ListView {
                id: overflowList
                objectName: "topBarOverflowList"
                anchors.fill: parent; visible: root.overflowMode
                model: root.overflowMode ? root.barState.overflowRows : null
                clip: true; boundsBehavior: Flickable.StopAtBounds; reuseItems: true
                ScrollBar.vertical: QuietScrollBar { }
                delegate: ItemDelegate {
                    id: overflowRow
                    required property var modelData
                    objectName: "topBarOverflowRow_" + modelData.id
                    width: overflowList.width; height: 36
                    leftPadding: 8; rightPadding: 8; topPadding: 0; bottomPadding: 0
                    focusPolicy: Qt.TabFocus; hoverEnabled: true
                    onClicked: root.barState.clickMetric(modelData.id)
                    background: Rectangle {
                        radius: 7; color: root.tint(overflowRow.down ? 0.11 : 0.065)
                        visible: overflowRow.hovered || overflowRow.visualFocus || overflowRow.down
                    }
                    contentItem: RowLayout {
                        spacing: 10
                        Text {
                            id: overflowLabel
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            text: (overflowRow.modelData.grouped?overflowRow.modelData.group_label:overflowRow.modelData.label) || ""; textFormat: Text.PlainText
                            color: root.secondary; font.family: root.barState.fontFamily
                            font.pixelSize: 12; elide: Text.ElideRight
                        }
                        Text {
                            id: overflowValue
                            Layout.maximumWidth: 128
                            text: (overflowRow.modelData.grouped?overflowRow.modelData.group_value:overflowRow.modelData.value) || "—"; textFormat: Text.PlainText
                            color: (overflowRow.modelData.grouped?overflowRow.modelData.group_available:overflowRow.modelData.available) ? root.foreground : root.secondary
                            font.family: root.barState.fontFamily; font.pixelSize: 12; font.weight: Font.Medium
                            elide: Text.ElideRight
                        }
                    }
                    PlainTip { visible: overflowRow.hovered && (overflowLabel.truncated || overflowValue.truncated); text: root.readingTip(overflowRow.modelData) }
                }
            }
            Flickable {
                id: metricScroll
                objectName: "topBarDetailScroll"
                anchors.fill: parent; visible: !root.overflowMode; clip: true
                contentWidth: width; contentHeight: metricContent.implicitHeight
                interactive: contentHeight > height; boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: QuietScrollBar { }
                ColumnLayout {
                    id: metricContent
                    width: Math.max(0, metricScroll.width-(metricScroll.interactive?6:0))
                    spacing: 14
                    Item {
                        visible: !root.hasPair && !root.hasGroup
                        Layout.fillWidth: true; Layout.preferredHeight: 44
                        Text {
                            id: primaryValue
                            objectName: "topBarDetailValue"
                            width: Math.max(0, Math.min(implicitWidth, parent.width - primaryUnit.implicitWidth - 6))
                            y: (parent.height - height) / 2
                            text: typeof root.detail.number_text === "string" ? root.readingNumber(root.detail) : (root.detail.value || "—"); textFormat: Text.PlainText
                            color: root.detail.available ? root.foreground : root.secondary
                            font.family: root.barState.fontFamily; font.pixelSize: 32; font.weight: Font.Medium
                            font.features: { "tnum": 1 }
                            elide: Text.ElideRight
                            HoverHandler { id: valueHover }
                            PlainTip { visible: valueHover.hovered && primaryValue.truncated; text: primaryValue.text }
                        }
                        Text {
                            id: primaryUnit
                            objectName: "topBarDetailUnit"
                            visible: !!text
                            text: root.readingUnit(root.detail); textFormat: Text.PlainText
                            color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 12
                            x: primaryValue.width + 6
                            y: primaryValue.y + primaryValue.baselineOffset - baselineOffset
                        }
                    }
                    GridLayout {
                        objectName:"topBarDetailGroupValues"
                        visible:root.hasGroup
                        Layout.fillWidth:true;columns:root.groupRows.length===3?3:2;uniformCellWidths:true;columnSpacing:12;rowSpacing:12
                        Repeater {
                            model:root.groupRows
                            ColumnLayout {
                                id:selectedMember;required property var modelData
                                Layout.fillWidth:true;Layout.minimumWidth:0;spacing:6
                                RowLayout {Layout.fillWidth:true;spacing:5
                                    Icon {name:selectedMember.modelData.icon || "sensors";ink:root.secondary;Layout.preferredWidth:13;Layout.preferredHeight:13}
                                    Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:selectedMember.modelData.label || "";textFormat:Text.PlainText;color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10;elide:Text.ElideRight}
                                }
                                Text {objectName:"topBarGroupDetail_"+selectedMember.modelData.metric;Layout.fillWidth:true;Layout.minimumWidth:0;text:selectedMember.modelData.value || "—";textFormat:Text.PlainText;color:selectedMember.modelData.available?root.foreground:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:20;font.weight:Font.Medium;font.features:{"tnum":1};elide:Text.ElideRight}
                                HoverHandler {id:selectedMemberHover}
                                PlainTip {visible:selectedMemberHover.hovered;text:root.readingTip(selectedMember.modelData)}
                            }
                        }
                    }
                    GridLayout {
                        objectName: "topBarDetailPairedValues"
                        visible: root.hasPair
                        Layout.fillWidth: true; columns: 2; uniformCellWidths: true; columnSpacing: 20
                        Repeater {
                            model: root.pairedRows
                            ColumnLayout {
                                id: pairedReading
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 5
                                RowLayout {
                                    Layout.fillWidth: true; spacing: 6
                                    Icon { name:root.directionIcon(pairedReading.modelData); ink:root.seriesColor(pairedReading.index); Layout.preferredWidth:14; Layout.preferredHeight:14 }
                                    Text {
                                        objectName: "topBarPairLabel_" + pairedReading.index
                                        Layout.fillWidth: true; Layout.minimumWidth: 0
                                        text: root.pairLabel(pairedReading.modelData); textFormat: Text.PlainText
                                        font.family: root.barState.fontFamily; font.pixelSize: 11
                                        color: root.secondary; elide: Text.ElideRight
                                    }
                                }
                                Item {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: pairedNumber.implicitHeight
                                    Text {
                                        id: pairedNumber
                                        objectName: "topBarPairValue_" + pairedReading.index
                                        width: parent.width
                                        text: root.readingNumber(pairedReading.modelData); textFormat: Text.PlainText
                                        font.family: root.barState.fontFamily; font.pixelSize: 28; font.weight: Font.Medium
                                        font.features: { "tnum": 1 }; elide: Text.ElideRight
                                        color: pairedReading.modelData.available === true ? root.foreground : root.secondary
                                    }
                                }
                                Text {
                                    id: pairedUnit
                                    objectName: "topBarPairUnit_" + pairedReading.index
                                    Layout.fillWidth: true; Layout.minimumWidth:0
                                    text: root.readingUnit(pairedReading.modelData); textFormat: Text.PlainText
                                    font.family: root.barState.fontFamily; font.pixelSize: 11
                                    color: root.secondary
                                }
                                HoverHandler { id: pairedHover }
                                PlainTip { visible: pairedHover.hovered; text: root.readingTip(pairedReading.modelData) }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "topBarDetailCapacity"
                        visible: root.hasCapacity
                        Layout.fillWidth: true; spacing: 6
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text {
                                Layout.fillWidth: true; Layout.minimumWidth: 0
                                text: root.capacity.label || ""; textFormat: Text.PlainText
                                color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 11
                                elide: Text.ElideRight
                            }
                            Text {
                                objectName: "topBarDetailCapacityValue"
                                text: root.hasCapacity ? root.capacity.used_text + " / " + root.capacity.total_text : ""
                                textFormat: Text.PlainText; color: root.foreground
                                font.family: root.barState.fontFamily; font.pixelSize: 11
                                font.features: { "tnum": 1 }
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true; implicitHeight: 4; radius: 2
                            color: root.tint(0.09)
                            Rectangle {
                                objectName: "topBarDetailCapacityFill"
                                width: parent.width * (root.hasCapacity ? root.capacity.fraction : 0)
                                height: 4; radius: 2; color: root.tint(0.65)
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "topBarCpuContext"
                        visible: root.hasCpuContext
                        Layout.fillWidth: true; spacing: 9
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text {
                                text: root.tr("逻辑处理器"); textFormat: Text.PlainText
                                color: root.foreground; font.family: root.barState.fontFamily
                                font.pixelSize: 11; font.weight: Font.Medium
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: root.tr("使用率") + " · %"; textFormat: Text.PlainText
                                color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                            }
                        }
                        Text {
                            objectName: "topBarCpuTopology"
                            visible: !!text; Layout.fillWidth: true; Layout.minimumWidth: 0
                            text: root.cpuCounts(); textFormat: Text.PlainText
                            color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }
                        GridView {
                            id: coreGrid
                            objectName: "topBarCpuCoreGrid"
                            visible: cpuCells.count > 0
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.min(208, Math.ceil(cpuCells.count / root.coreColumns) * cellHeight)
                            Layout.minimumHeight: 0; Layout.maximumHeight: 208
                            model: cpuCells; clip: true; reuseItems: true; cacheBuffer: 0
                            cellWidth: Math.max(1, (width - 5) / root.coreColumns)
                            cellHeight: root.coreColumns === 8 ? 34 : 44
                            interactive: contentHeight > height; boundsBehavior: Flickable.StopAtBounds
                            ScrollBar.vertical: QuietScrollBar { }
                            delegate: Rectangle {
                                id: coreTile
                                required property int logicalIndex
                                required property string logicalLabel
                                required property string usageText
                                required property bool readingAvailable
                                required property real usageFraction
                                required property string readingReason
                                required property string readingSource
                                objectName: "topBarCpuLogical_" + logicalIndex
                                width: Math.max(0, coreGrid.cellWidth - 4); height: coreGrid.cellHeight - 4
                                radius: 4
                                color: readingAvailable ? Qt.rgba(0.22, 0.48, 0.82, 0.065 + 0.28 * usageFraction)
                                    : root.tint(0.035)
                                border.width: 0.6; border.color: root.tint(0.065)
                                Accessible.role: Accessible.StaticText
                                Accessible.name: logicalLabel + " " + usageText
                                Accessible.description: readingReason || readingSource
                                Text {
                                    objectName: "topBarCpuLogicalLabel_" + coreTile.logicalIndex
                                    x: 4; y: 3; width: parent.width - 8
                                    text: root.coreColumns === 8 ? (coreTile.logicalIndex >= 0 ? String(coreTile.logicalIndex) : "—")
                                        : coreTile.logicalLabel
                                    textFormat: Text.PlainText; color: root.secondary
                                    font.family: root.barState.fontFamily; font.pixelSize: root.coreColumns === 8 ? 8 : 9
                                    elide: Text.ElideRight
                                }
                                Text {
                                    objectName: "topBarCpuLogicalValue_" + coreTile.logicalIndex
                                    x: 4; anchors.bottom: parent.bottom; anchors.bottomMargin: 3
                                    width: parent.width - 8
                                    text: root.coreColumns === 8 ? coreTile.usageText.replace(/\s+%$/, "%") : coreTile.usageText
                                    textFormat: Text.PlainText
                                    color: coreTile.readingAvailable ? root.foreground : root.secondary
                                    font.family: root.barState.fontFamily; font.pixelSize: root.coreColumns === 8 ? 9 : 12
                                    font.weight: Font.Medium; font.features: { "tnum": 1 }; elide: Text.ElideRight
                                }
                                HoverHandler { id: coreHover }
                                PlainTip {
                                    visible: coreHover.hovered
                                    text: [coreTile.logicalLabel, coreTile.usageText, coreTile.readingSource,
                                           coreTile.readingReason].filter(value => !!value).join("\n")
                                }
                            }
                        }
                        Text {
                            objectName: "topBarCpuContextReason"
                            visible: !!root.cpuContext.reason; Layout.fillWidth: true
                            text: root.cpuContext.reason || ""; textFormat: Text.PlainText
                            color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                            wrapMode: Text.Wrap
                        }
                        Text {
                            objectName: "topBarCpuContextTruncated"
                            visible: root.cpuContext.truncated === true; Layout.fillWidth: true
                            text: root.tr("显示 %1 / %2 个逻辑处理器")
                                .replace("%1", String(cpuCells.count)).replace("%2", String(root.cpuContext.logical_processors || "—"))
                            textFormat: Text.PlainText; color: root.secondary
                            font.family: root.barState.fontFamily; font.pixelSize: 10; wrapMode: Text.Wrap
                        }
                        GridLayout {
                            objectName: "topBarCpuRelatedGrid"
                            visible: root.cpuRelatedRows.length > 0
                            Layout.fillWidth: true; columns: 2; uniformCellWidths: true
                            columnSpacing: 10; rowSpacing: 10
                            Repeater {
                                model: root.cpuRelatedRows
                                ColumnLayout {
                                    id: cpuRelated
                                    required property var modelData
                                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                                    Text {
                                        Layout.fillWidth: true; Layout.minimumWidth: 0
                                        text: cpuRelated.modelData.label || ""; textFormat: Text.PlainText
                                        color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        objectName: "topBarCpuRelatedValue_" + cpuRelated.modelData.metric
                                        Layout.fillWidth: true; Layout.minimumWidth: 0
                                        text: cpuRelated.modelData.available === true ? (cpuRelated.modelData.value || "—") : "—"
                                        textFormat: Text.PlainText
                                        color: cpuRelated.modelData.available === true ? root.foreground : root.secondary
                                        font.family: root.barState.fontFamily; font.pixelSize: 13
                                        font.weight: Font.Medium; font.features: { "tnum": 1 }; elide: Text.ElideRight
                                    }
                                    HoverHandler { id: cpuRelatedHover }
                                    PlainTip { visible: cpuRelatedHover.hovered; text: root.readingTip(cpuRelated.modelData) }
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        objectName: "topBarDetailHistorySection"
                        Layout.fillWidth: true; spacing: 9
                        RowLayout {
                            visible: root.hasTrend
                            Layout.fillWidth: true; spacing: 10
                            Text {
                                visible: !root.hasPair
                                Layout.fillWidth: true
                                text: root.tr("趋势"); textFormat: Text.PlainText
                                color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 11
                            }
                            RowLayout {
                                visible: root.hasPair
                                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 14
                                Repeater {
                                    model: root.pairedRows
                                    RowLayout {
                                        required property var modelData
                                        required property int index
                                        Layout.minimumWidth: 0; spacing: 5
                                        Rectangle { implicitWidth: 6; implicitHeight: 6; radius: 3; color: root.seriesColor(parent.index) }
                                        Text {
                                            objectName: "topBarPairTrendLabel_" + parent.index
                                            Layout.fillWidth: true; Layout.minimumWidth: 0
                                            text: root.pairLabel(parent.modelData); textFormat: Text.PlainText
                                            color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                                Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
                            }
                            Text {
                                visible: root.hasTrend && root.chartScale.valid
                                text: root.detail.unit || ""; textFormat: Text.PlainText
                                color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 10
                            }
                        }
                        Item {
                            id: chartArea
                            Layout.fillWidth: true; Layout.preferredHeight: root.hasTrend ? 108 : 48
                            Canvas {
                                id: history
                                objectName: "topBarDetailTrend"
                                visible: root.hasTrend
                                width: root.chartScale.valid ? parent.width-52 : parent.width
                                height: 88
                                antialiasing: true
                                onVisibleChanged: requestPaint()
                                onWidthChanged: requestPaint()
                                onHeightChanged: requestPaint()
                                onPaint: {
                                    const ctx = getContext("2d")
                                    ctx.clearRect(0, 0, width, height)
                                    if (!root.hasTrend) return
                                    const px=3, py=6, pw=width-6, ph=height-12
                                    ctx.lineWidth=.6; ctx.strokeStyle=root.tint(root.dark?.15:.11)
                                    for(let i=0;i<3;i++) {
                                        const y=py+i*ph/2
                                        ctx.beginPath();ctx.moveTo(px,y);ctx.lineTo(px+pw,y);ctx.stroke()
                                    }
                                    ctx.strokeStyle=root.tint(root.dark?.055:.04)
                                    for(let i=1;i<4;i++) {
                                        const x=px+i*pw/4
                                        ctx.beginPath();ctx.moveTo(x,py);ctx.lineTo(x,py+ph);ctx.stroke()
                                    }
                                    for(let index=0;index<root.chartRows.length;index++) {
                                        const row=root.chartRows[index]
                                        if(!root.trendReadable(row))continue
                                        const color=root.hasPair?root.pairColor(index):root.pairColor(0)
                                        const points=root.chartPoints(row)
                                        let segment=[],last=null
                                        const drawSegment=function() {
                                            if(segment.length<2){segment=[];return}
                                            ctx.beginPath();ctx.moveTo(segment[0].x,py+ph)
                                            for(const point of segment)ctx.lineTo(point.x,point.y)
                                            ctx.lineTo(segment[segment.length-1].x,py+ph);ctx.closePath()
                                            ctx.fillStyle=color;ctx.globalAlpha=.065;ctx.fill();ctx.globalAlpha=1
                                            ctx.beginPath();ctx.moveTo(segment[0].x,segment[0].y)
                                            for(let n=1;n<segment.length;n++)ctx.lineTo(segment[n].x,segment[n].y)
                                            ctx.lineWidth=1.6;ctx.lineJoin="round";ctx.lineCap="round";ctx.strokeStyle=color;ctx.stroke()
                                            segment=[]
                                        }
                                        for(const point of points) {
                                            if(!root.validPoint(point)){drawSegment();continue}
                                            const pixel={x:px+point.x*pw,y:py+point.y*ph}
                                            segment.push(pixel);last=pixel
                                        }
                                        drawSegment()
                                        if(points.length<=8)for(const point of points)if(root.validPoint(point)) {
                                            ctx.beginPath();ctx.arc(px+point.x*pw,py+point.y*ph,1.7,0,Math.PI*2)
                                            ctx.fillStyle=color;ctx.fill()
                                        }
                                        if(last){ctx.beginPath();ctx.arc(last.x,last.y,2.4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill()}
                                    }
                                }
                            }
                            Repeater {
                                model: root.hasTrend && root.chartScale.valid ? 3 : 0
                                Text {
                                    id: axisText
                                    required property int index
                                    readonly property real numericValue:index===0?root.chartScale.high:index===2?root.chartScale.low:root.chartScale.high/2+root.chartScale.low/2
                                    objectName: "topBarTrendAxis_"+index
                                    x:history.width+8; y:6+index*(history.height-12)/2-height/2
                                    width:44
                                    text:root.axisNumber(numericValue)
                                    textFormat:Text.PlainText; color:root.secondary
                                    font.family:root.barState.fontFamily;font.pixelSize:10;font.features:{"tnum":1}
                                    elide:Text.ElideRight
                                    HoverHandler {id:axisHover}
                                    PlainTip {visible:axisHover.hovered;text:axisText.numericValue+" "+(root.detail.unit || "")}
                                }
                            }
                            Text {
                                visible:root.hasTrend
                                x:3;y:91
                                text:root.tr("起点");textFormat:Text.PlainText
                                color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10
                            }
                            Text {
                                visible:root.hasTrend
                                x:history.width-width-3;y:91
                                text:root.tr("最新");textFormat:Text.PlainText
                                color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10
                            }
                            Column {
                                visible:!root.hasTrend
                                anchors.verticalCenter:parent.verticalCenter
                                spacing:3
                                Text {text:root.tr("尚无连续读数");textFormat:Text.PlainText;color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:11}
                                Text {text:root.tr("采样后将显示趋势");textFormat:Text.PlainText;color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10}
                            }
                        }
                        RowLayout {
                            Layout.fillWidth:true
                            Text {
                                objectName:"topBarDetailHistoryCount"
                                Layout.fillWidth:true
                                text:root.sampleCount+" "+root.tr("次采样");textFormat:Text.PlainText
                                color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10
                            }
                            Text {
                                objectName:"topBarDetailHistoryElapsed"
                                text:root.spanText();textFormat:Text.PlainText;visible:!!text
                                color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10
                            }
                        }
                        GridLayout {
                            objectName:"topBarHistorySummary"
                            visible:root.hasTrend
                            Layout.fillWidth:true;columns:2;uniformCellWidths:true;columnSpacing:20;rowSpacing:4
                            Repeater {
                                model:root.hasPair?root.pairedRows:[root.detail,root.detail]
                                ColumnLayout {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth:true;Layout.minimumWidth:0;spacing:3
                                    Text {
                                        Layout.fillWidth:true;Layout.minimumWidth:0
                                        text:root.hasPair?root.pairLabel(parent.modelData)+" · "+root.tr("峰值"):root.tr(parent.index===0?"峰值":"平均值")
                                        textFormat:Text.PlainText;color:root.secondary;font.family:root.barState.fontFamily;font.pixelSize:10;elide:Text.ElideRight
                                    }
                                    Text {
                                        id: summaryValue
                                        objectName:"topBarHistorySummaryValue_"+parent.index
                                        Layout.fillWidth:true;Layout.minimumWidth:0
                                        text:root.summaryNumber(parent.modelData,root.hasPair || parent.index===0?"peak":"mean")
                                        textFormat:Text.PlainText;color:root.foreground;font.family:root.barState.fontFamily;font.pixelSize:13;font.weight:Font.Medium;elide:Text.ElideRight
                                        HoverHandler {id:summaryHover}
                                        PlainTip {visible:summaryHover.hovered;text:summaryValue.text}
                                    }
                                }
                            }
                        }
                    }
                    Text {
                        objectName: "topBarDetailReason"
                        Layout.fillWidth: true; visible: !!root.detail.reason
                        text: root.detail.reason || ""; textFormat: Text.PlainText; color: root.secondary
                        font.family: root.barState.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; visible: root.availableRows.length > 0; spacing: 10
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.tint(0.09) }
                        Text {
                            objectName: "topBarRelatedTitle"
                            visible: !root.hasPair
                            text: root.detail.group_label || root.tr("相关读数"); textFormat: Text.PlainText; color: root.secondary
                            font.family: root.barState.fontFamily; font.pixelSize: 11
                        }
                        GridLayout {
                            objectName: "topBarRelatedGrid"
                            Layout.fillWidth: true; columns: 2; uniformCellWidths: true
                            columnSpacing: 16; rowSpacing: 12
                            Repeater {
                                model: root.availableRows
                                delegate: ColumnLayout {
                                    id: relatedRow
                                    required property var modelData
                                    required property int index
                                    objectName: "topBarRelated_" + index
                                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                                    Text {
                                        id: relatedLabel
                                        Layout.fillWidth: true; Layout.minimumWidth: 0
                                        text: relatedRow.modelData.label || ""; textFormat: Text.PlainText
                                        color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        id: relatedValue
                                        Layout.fillWidth: true; Layout.minimumWidth: 0
                                        text: relatedRow.modelData.value || "—"; textFormat: Text.PlainText
                                        color: root.foreground; font.family: root.barState.fontFamily
                                        font.pixelSize: 14; font.weight: Font.Medium; font.features: { "tnum": 1 }; elide: Text.ElideRight
                                    }
                                    HoverHandler { id: relatedHover }
                                    PlainTip { visible: relatedHover.hovered; text: root.readingTip(relatedRow.modelData) }
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; visible: root.missingRows.length > 0; spacing: 8
                        Button {
                            id: missingToggle
                            objectName: "topBarDetailMissingToggle"
                            Layout.fillWidth: true; implicitHeight: 28
                            padding: 0; checkable: true; checked: root.showMissing; hoverEnabled: true
                            onClicked: root.showMissing = checked
                            Accessible.name: root.missingRows.length + " " + root.tr("项不可用")
                            contentItem: RowLayout {
                                spacing: 6
                                Text {
                                    Layout.fillWidth: true; text: missingToggle.Accessible.name
                                    textFormat: Text.PlainText; color: root.secondary
                                    font.family: root.barState.fontFamily; font.pixelSize: 11
                                }
                                Icon { name: "chevron"; ink: root.secondary; rotation: root.showMissing ? 270 : 90; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
                            }
                            background: Rectangle { radius: 6; color: root.tint(0.05); visible: missingToggle.hovered || missingToggle.visualFocus; border.width: missingToggle.visualFocus ? 1 : 0; border.color: root.tint(0.3) }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; visible: root.showMissing; spacing: 10
                            Repeater {
                                model: root.missingRows
                                delegate: ColumnLayout {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true; spacing: 3
                                    Text {
                                        Layout.fillWidth: true; text: modelData.label || ""; textFormat: Text.PlainText
                                        color: root.foreground; font.family: root.barState.fontFamily; font.pixelSize: 11
                                        wrapMode: Text.Wrap
                                    }
                                    Text {
                                        objectName: "topBarMissingReason_" + index
                                        Layout.fillWidth: true
                                        text: modelData.reason || modelData.source || root.tr("无法读取")
                                        textFormat: Text.PlainText; color: root.secondary
                                        font.family: root.barState.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap
                                    }
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: !!root.detail.hardware_name || !!root.detail.source
                        spacing: 6
                        Rectangle { Layout.fillWidth:true; implicitHeight:1; color:root.tint(.08) }
                        Button {
                            id: metadataToggle
                            objectName: "topBarDetailMetadataToggle"
                            Layout.fillWidth: true; implicitHeight: 28; padding: 0
                            checkable: true; checked: root.showMetadata; hoverEnabled: true
                            onClicked: root.showMetadata = checked
                            Accessible.name: root.tr("设备与来源")
                            contentItem: RowLayout {
                                spacing: 7
                                Text {
                                    id: sourceSummary
                                    objectName: "topBarDetailMetadataSummary"
                                    Layout.fillWidth: true; Layout.minimumWidth: 0
                                    text: root.tr("设备与来源")
                                    textFormat: Text.PlainText; color: root.secondary
                                    font.family: root.barState.fontFamily; font.pixelSize: 11; elide: Text.ElideRight
                                }
                                Icon { name: "chevron"; ink: root.secondary; rotation: root.showMetadata ? 270 : 90; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
                            }
                            background: Rectangle { radius: 6; color: root.tint(0.05); visible: metadataToggle.hovered || metadataToggle.visualFocus; border.width: metadataToggle.visualFocus ? 1 : 0; border.color: root.tint(0.3) }
                            PlainTip { visible: metadataToggle.hovered; text: [root.detail.hardware_name, root.detail.source].filter(value => !!value).join("\n") }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; visible: root.showMetadata; spacing: 5
                            Text {
                                id: hardwareText
                                objectName: "topBarDetailHardware"
                                Layout.fillWidth: true; visible: !!text
                                text: root.detail.hardware_name || ""; textFormat: Text.PlainText
                                color: root.foreground; font.family: root.barState.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap
                            }
                            Text {
                                id: sourceText
                                objectName: "topBarDetailSource"
                                Layout.fillWidth: true; visible: !!text
                                text: root.detail.source || ""; textFormat: Text.PlainText
                                color: root.secondary; font.family: root.barState.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
        }
    }
    Connections {
        target: root.barState
        function onChanged() { history.requestPaint() }
    }
}
