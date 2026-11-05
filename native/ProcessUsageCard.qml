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
    readonly property var context: {
        if (!provider || !lease || typeof provider.processUsage !== "function") return ({})
        const revision = provider.processUsageRevision
        return provider.processUsage(lease)
    }
    readonly property int displayedCount: softwareRows.count
    readonly property bool dark: ink.r > .5
    readonly property color accent: dark ? "#79b2ff" : "#2279d5"
    visible: Object.keys(context).length > 0
    spacing: 9
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
    onMetricChanged: syncLease()
    onHardwareNameChanged: syncLease()
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
    function syncRows() {
        const rows = (context.rows || []).slice(0, 5)
        for (let index = 0; index < rows.length; index++) {
            const row = rows[index]
            const record = {
                softwareName: String(row.name || ""),
                softwareValue: String(row.value_text || "—"),
                softwareCount: Math.max(1, Number(row.process_count) || 1),
                softwareFraction: Number.isFinite(row.fraction) ? Math.max(0, Math.min(1, row.fraction)) : 0
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
        Layout.fillWidth: true; spacing: 8
        ColumnLayout {
            Layout.fillWidth: true; spacing: 3
            Text {
                text: root.context.title || ""; textFormat: Text.PlainText
                color: root.ink; font.family: root.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold
            }
            Text {
                text: root.context.caption || ""; textFormat: Text.PlainText
                color: root.muted; font.family: root.fontFamily; font.pixelSize: 10
            }
        }
        Rectangle {
            visible: root.displayedCount > 0
            implicitWidth: 38; implicitHeight: 21; radius: 7
            color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, .1)
            Text {
                anchors.centerIn: parent; text: "TOP 5"; textFormat: Text.PlainText
                font.family: root.fontFamily; font.pixelSize: 9; font.weight: Font.Medium; color: root.accent
            }
        }
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
                        font.family: root.fontFamily; font.pixelSize: 9; font.features: {"tnum":1}
                        color: root.muted; opacity: .8; Layout.preferredWidth: 15
                    }
                    Text {
                        objectName: "processSoftwareName" + software.index
                        text: software.softwareName; textFormat: Text.PlainText
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        color: root.ink; font.family: root.fontFamily; font.pixelSize: 11; elide: Text.ElideRight
                    }
                    Text {
                        objectName: "processSoftwareValue" + software.index
                        text: software.softwareValue; textFormat: Text.PlainText
                        color: root.ink; font.family: root.fontFamily; font.pixelSize: 11
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
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 10; lineHeight: 1.2
    }
    Text {
        visible: !!text; Layout.fillWidth: true
        text: root.context.coverage || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 10
    }
    Text {
        visible: !!text; Layout.fillWidth: true
        text: root.context.technical || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap
        color: root.muted; font.family: root.fontFamily; font.pixelSize: 9
    }
    Text {
        Layout.fillWidth: true; visible: root.displayedCount > 0
        text: root.provider && typeof root.provider.tr === "function" ? root.provider.tr("同名进程合并 · 每秒更新") : ""
        textFormat: Text.PlainText; color: root.muted; font.family: root.fontFamily; font.pixelSize: 9
        HoverHandler { id: noteHover }
        PlainTip { visible: noteHover.hovered; text: root.context.note || "" }
    }
}
