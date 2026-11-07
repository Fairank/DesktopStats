import QtQuick
import QtQuick.Window

// This is the same retained hardware and shared motion clock used by the bar.
// Identity is refreshed by sampled data; animation changes transforms only.
Item {
    id: root
    objectName: "desktopHardwareModel"
    required property string moduleKey
    required property var config
    property bool draftMode: false
    property bool previewPrefs: false
    property bool motionAllowed: false
    property bool active: visible && root.Window.window !== null && root.Window.window.visible
    readonly property var prefs: config.widgets && config.widgets[moduleKey] || ({})
    readonly property var geometry: stats.widgetHardwareLayout(width, height, prefs)
    property var snapshot: ({})
    readonly property bool isModel: prefs.presentation === "hardware" && ["cpu","gpu"].includes(prefs.kind)
    readonly property var appearance: {
        const value=Object.assign({},snapshot.appearance || ({}))
        value.icon_set=prefs.hardware_icon_style || "miniature"
        return value
    }
    visible: isModel
    Theme { id: ui }
    function refresh() {
        if (isModel && active) snapshot=previewPrefs ? stats.widgetHardwarePreviewState(prefs)
            : stats.widgetHardwareState(moduleKey, draftMode)
    }
    onActiveChanged: refresh()
    onModuleKeyChanged: refresh()
    onConfigChanged: refresh()
    onDraftModeChanged: refresh()
    Component.onCompleted: refresh()
    Connections {
        target: stats
        enabled: root.active && root.isModel
        function onDataChanged() { root.refresh() }
    }
    Item {
        id: artwork
        objectName: "desktopHardwareArtwork"
        readonly property var area: root.geometry.image || ({})
        x: area.x || 0; y: area.y || 0
        width: area.width || 0; height: area.height || 0
        clip: true
    MetricIcon {
        id: modelIcon
        objectName: "desktopHardwareModelIcon"
        anchors.centerIn: parent
        width: parent.width * (root.prefs.kind === "cpu" ? 1.2 : 1)
        height: parent.height * (root.prefs.kind === "cpu" ? 1.2 : 1)
        name: root.prefs.kind || "cpu"
        modelMode: true
        metric: name+"_usage"
        ink: ui.ink
        iconStyle: root.prefs.hardware_icon_style || "miniature"
        hardwareAppearance: root.appearance
        hardwareState: root.snapshot.hardware_state || ({})
        available: root.snapshot.available === true
        effect: root.prefs.icon_effect || "auto"
        intensity: root.prefs.effect_intensity === undefined ? .5 : root.prefs.effect_intensity
        speed: root.prefs.effect_speed === undefined ? 1 : root.prefs.effect_speed
        motionEnabled: root.active && root.motionAllowed && stats.motionEnabled === true
    }
    }
    Text {
        objectName: "desktopHardwareModelName"
        readonly property var area: root.geometry.caption || ({})
        x: area.x || 0; y: area.y || 0
        width: area.width || 0; height: area.height || 0
        text: root.snapshot.name || ui.t(root.prefs.kind === "gpu" ? "显卡型号尚未读取" : "处理器型号尚未读取")
        textFormat: Text.PlainText
        color: ui.muted; font.family: ui.fontFamily; font.pixelSize: root.width<280?11:12
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
