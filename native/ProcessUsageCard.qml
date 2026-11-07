import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "processUsageCard"
    property var provider: null
    property string metric: ""
    property string hardwareName: ""
    property bool active: false
    property bool motionEnabled: true
    property color ink: "#202a37"
    property color muted: "#6a7888"
    property string fontFamily: "Segoe UI"
    property string lease: ""
    property bool complete: false
    property bool showLimitations: false
    readonly property bool providerAvailable: !!provider && typeof provider.beginProcessUsage === "function"
    readonly property var context: {
        if (!provider || !lease || typeof provider.processUsage !== "function") return ({})
        const revision = provider.processUsageRevision
        return provider.processUsage(lease)
    }
    readonly property int displayedCount: softwareRows.count
    readonly property bool unsupported: context.reason_code === "not_attributable"
    readonly property bool processIo: context.kind === "io"
    readonly property bool dark: ink.r > .5
    readonly property color accent: dark ? "#79b2ff" : "#2279d5"
    visible: Object.keys(context).length > 0
    spacing: 8
    component PlainTip: ToolTip {
        id: tip
        delay: 450; timeout: 8000
        contentItem: Text {
            text: tip.text; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: root.ink; font.family: root.fontFamily; font.pixelSize: 10
        }
        background: Rectangle {
            radius: 7; color: root.dark ? "#303742" : "#f8fafc"
            border.color: root.dark ? "#4b5461" : "#dce2ea"
        }
    }
    onActiveChanged: syncLease()
    onMetricChanged: { showLimitations = false; syncLease() }
    onHardwareNameChanged: { showLimitations = false; syncLease() }
    onContextChanged: syncRows()
    Component.onCompleted: { complete = true; syncLease(); syncRows() }
    Component.onDestruction: releaseLease()

    function syncLease() {
        if (!complete || !provider || typeof provider.beginProcessUsage !== "function") return
        if (!active || !metric) { releaseLease(); return }
        if (!lease) lease = provider.beginProcessUsage(metric, hardwareName)
        else provider.updateProcessUsage(lease, metric, hardwareName)
    }
    function releaseLease() {
        if (!lease) return
        const previous = lease
        lease = ""
        if (provider && typeof provider.endProcessUsage === "function") provider.endProcessUsage(previous)
    }
    function tr(text) {
        return provider && typeof provider.tr === "function" ? provider.tr(text) : text
    }
    function syncRows() {
        const rows = (context.rows || []).slice(0, 5)
        const largestIo = root.processIo ? Math.max(0,...rows.map(row=>Number.isFinite(row.value)?row.value:0)) : 0
        for (let index = 0; index < rows.length; index++) {
            const row = rows[index]
            const record = {
                softwareName: String(row.name || ""),
                softwareValue: String(row.value_text || "—"),
                softwareCount: Math.max(1, Number(row.process_count) || 1),
                softwareFraction: root.processIo ? (largestIo>0 && Number.isFinite(row.value)?Math.max(0,Math.min(1,row.value/largestIo)):0)
                    : Number.isFinite(row.fraction) ? Math.max(0, Math.min(1, row.fraction)) : 0
            }
            if (index >= softwareRows.count) softwareRows.append(record)
            else {
                const old = softwareRows.get(index)
                if (Object.keys(record).some(key => old[key] !== record[key])) softwareRows.set(index, record)
            }
        }
        if (softwareRows.count > rows.length) softwareRows.remove(rows.length, softwareRows.count - rows.length)
    }
    ListModel { id: softwareRows }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, .09) }
    RowLayout {
        visible: !root.unsupported
        Layout.fillWidth: true; spacing: 8
        Text {
            Layout.fillWidth: true; Layout.minimumWidth: 0
            text: root.context.title || root.tr("占用最多的软件"); textFormat: Text.PlainText
            color: root.ink; font.family: root.fontFamily; font.pixelSize: 13; font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            text: root.context.caption || ""; textFormat: Text.PlainText
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
        }
    }
    Text {
        objectName: "processIoScope"
        visible: root.processIo; Layout.fillWidth: true
        text: root.tr("所有进程读写 I/O，含缓存与设备，非当前磁盘统计。")
        textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 11; lineHeight: 1.2
    }
    ColumnLayout {
        Layout.fillWidth: true; spacing: 2
        Repeater {
            model: softwareRows
            delegate: Item {
                id: software
                required property int index
                required property string softwareName
                required property string softwareValue
                required property int softwareCount
                required property real softwareFraction
                objectName: "processSoftwareRow" + index
                Layout.fillWidth: true; implicitHeight: 34
                Rectangle {
                    anchors.fill: parent; anchors.leftMargin: -6; anchors.rightMargin: -6; radius: 7
                    color: softwareHover.hovered ? Qt.rgba(root.ink.r, root.ink.g, root.ink.b, .045) : "transparent"
                }
                RowLayout {
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    height: 24; spacing: 8
                    Text {
                        text: String(software.index + 1).padStart(2, "0"); textFormat: Text.PlainText
                        font.family: root.fontFamily; font.pixelSize: 10; font.features: {"tnum":1}
                        color: root.muted; Layout.preferredWidth: 16
                    }
                    Text {
                        objectName: "processSoftwareName" + software.index
                        text: software.softwareName; textFormat: Text.PlainText
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        color: root.ink; font.family: root.fontFamily; font.pixelSize: 12; elide: Text.ElideRight
                    }
                    Text {
                        objectName: "processSoftwareValue" + software.index
                        text: software.softwareValue; textFormat: Text.PlainText
                        color: root.ink; font.family: root.fontFamily; font.pixelSize: 12
                        font.weight: Font.Medium; font.features: {"tnum":1}
                    }
                }
                Rectangle {
                    x: 23; y: 27; width: Math.max(0, parent.width - x); height: 2; radius: 1
                    color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, .045)
                    Rectangle {
                        width: parent.width * software.softwareFraction; height: 2; radius: 1
                        color: root.accent; opacity: .7
                        Behavior on width { NumberAnimation { duration: root.motionEnabled ? 180 : 0; easing.type: Easing.OutCubic } }
                    }
                }
                HoverHandler { id: softwareHover }
                PlainTip {
                    visible: softwareHover.hovered
                    text: software.softwareName + " · " + software.softwareCount + " "
                        + (root.provider && typeof root.provider.tr === "function" ? root.provider.tr("个进程") : "")
                }
            }
        }
    }
    Text {
        objectName: "processUsageReason"
        visible: !!text; Layout.fillWidth: true
        text: root.context.reason || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 11; lineHeight: 1.2
    }
    Text {
        visible: !!text && !!root.context.kind; Layout.fillWidth: true
        text: root.context.coverage || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
    }
    Button {
        id: limitationsToggle
        objectName: "processUsageLimitationsToggle"
        visible: (!root.processIo && !!root.context.note) || !!root.context.technical
        Layout.fillWidth: true; implicitHeight: 28; padding: 0
        checkable: true; checked: root.showLimitations
        onClicked: root.showLimitations = checked
        Accessible.name: root.tr("来源与限制")
        contentItem: RowLayout {
            spacing: 8
            Text { Layout.fillWidth: true; text: root.tr("来源与限制"); color: root.muted; font.family: root.fontFamily; font.pixelSize: 11 }
            Icon { name: "chevron"; ink: root.muted; rotation: root.showLimitations ? 270 : 90; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
        }
        background: Rectangle { radius: 5; color: limitationsToggle.hovered ? Qt.rgba(root.ink.r,root.ink.g,root.ink.b,.04) : "transparent"; border.color: limitationsToggle.visualFocus ? root.accent : "transparent" }
    }
    ColumnLayout {
        visible: root.showLimitations; Layout.fillWidth: true; spacing: 6
        Text {
            visible: !root.processIo && !!text; Layout.fillWidth: true
            text: root.context.note || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 11
        }
        Text {
            objectName: "processUsageTechnical"
            visible: !!text; Layout.fillWidth: true
            text: root.context.technical || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: root.muted; font.family: root.fontFamily; font.pixelSize: 10
        }
    }
}
