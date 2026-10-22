import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import DesktopStats 1.0

ColumnLayout {
    id: root
    readonly property var config: stats.draft
    property string value: "glass"
    property string widgetKey: ""
    property bool allowGlobal: false
    property bool compact: false
    signal picked(string selected)
    spacing: 8
    Theme { id: ui }
    readonly property string effectiveValue: value === "global" ? root.config.skin : value
    readonly property string skinLabel: (stats.catalog.skins.find(option => option.id === root.effectiveValue) || {}).label || root.effectiveValue
    readonly property bool glassChosen: ["glass", "frost", "tint"].includes(effectiveValue)
    readonly property var previewInfo: { const layout = stats.previewWindows; return widgetKey ? stats.previewState(widgetKey) : ({}) }
    readonly property bool solidFallback: glassChosen && (widgetKey ? previewInfo.coating_translucent === false : !stats.coatingAllowed)
    readonly property string materialStatus: {
        if (!root.widgetKey) return ui.t("实际效果以桌面组件为准。")
        if (root.previewInfo.coating_translucent === false) return ui.t("实色底色")
        if (root.previewInfo.blur_configured === true) return ui.t(root.previewInfo.compositing_verified === true ? "系统模糊已确认。" : "系统模糊尚未确认。")
        if (root.previewInfo.coating_translucent === true) return ui.t("透明背景，未启用系统模糊。")
        return ui.t("透明效果尚未确认。")
    }
    function optionValue(name) {
        const prefs = widgetKey ? root.config.widgets[widgetKey] || ({}) : ({})
        const own = prefs[name], globalValue = root.config[name]
        return own !== null && own !== undefined ? own : globalValue !== undefined ? globalValue : 50
    }
    function choose(value) {
        root.picked(value)
        if (chooser.opened) chooser.close()
    }
    function description(skin) {
        return ui.t(({glass:"显露背景，轻盈边框",frost:"柔和底色，阅读更稳",tint:"淡彩衬底，柔和层次",
            card:"高对比，专注读数",graphite:"深色底板，夜间舒适",minimal:"保留读数，隐去底板"})[skin] || "")
    }
    function sceneSource() {
        const sky = ui.dark ? ["#243747", "#506171", "#292f3d"] : ["#b8d9e3", "#8dbbce", "#dce9e9"]
        const ridge = ui.dark ? ["#526e6c", "#68716d", "#9b7b68"] : ["#8dbebc", "#c2d2bd", "#e7c9ad"]
        return "data:image/svg+xml;base64," + Qt.btoa('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 190">'
            + '<defs><linearGradient id="s" x2="1" y2="1"><stop stop-color="'+sky[0]+'"/><stop offset=".62" stop-color="'+sky[1]+'"/><stop offset="1" stop-color="'+sky[2]+'"/></linearGradient>'
            + '<linearGradient id="r" x2=".7" y2="1"><stop stop-color="'+ridge[0]+'"/><stop offset="1" stop-color="'+ridge[1]+'"/></linearGradient><clipPath id="c"><rect width="320" height="190" rx="12"/></clipPath></defs>'
            // Qt's SVG Tiny renderer may ignore clipPath: each painted shape
            // also stays inside the same rounded boundary by construction.
            + '<g clip-path="url(#c)"><rect width="320" height="190" rx="12" fill="url(#s)"/>'
            + '<path fill="'+ridge[2]+'" d="M207 0h101q12 0 12 12v72c-30 26-97 17-113-20-8-20-7-44 0-64Z"/>'
            + '<path fill="url(#r)" d="M0 142C48 115 50 69 132 74S229 144 320 80v98q0 12-12 12H12q-12 0-12-12Z"/>'
            + '<path fill="'+ridge[2]+'" d="M0 177c52-32 114-30 185-16s93-3 135-35v52q0 12-12 12H12q-12 0-12-12Z"/>'
            + '<path d="M0 171c61-47 113-39 175-23s96 1 145-34" fill="none" stroke="'+sky[2]+'" stroke-opacity=".32" stroke-width="1.2"/></g></svg>')
    }
    onCompactChanged: chooser.close()

    component CoatingSwatch: Item {
        id: swatch
        property string skin: "glass"
        readonly property bool miniature: width >= 90 && height >= 52
        readonly property color foreground: skin === "graphite" || ui.dark ? "#f5f6f8" : "#1f242b"
        implicitWidth: 176; implicitHeight: 112
        // An original controlled desktop scene. Only the production coating
        // varies between samples; no captured background or native blur claim.
        Rectangle { anchors.fill: parent; color: ui.well; radius: 8 }
        Image {
            objectName: swatch.miniature ? "skinSampleScene_" + swatch.skin : "skinSummaryScene"
            anchors.fill: parent; anchors.margins: 1
            source: root.sceneSource(); fillMode: Image.Stretch
            sourceSize.width: Math.ceil(width * Screen.devicePixelRatio)
            sourceSize.height: Math.ceil(height * Screen.devicePixelRatio)
        }
        Rectangle {
            visible: swatch.miniature && swatch.skin !== "minimal"
            x: mainSample.x + 1; y: mainSample.y + 2; width: mainSample.width; height: mainSample.height
            color: "#140c2232"; radius: 9
        }
        Item {
            id: mainSample
            x: swatch.miniature ? swatch.width * .075 : 3
            y: swatch.miniature ? swatch.height * .15 : 3
            width: swatch.miniature ? swatch.width * .62 : swatch.width - 6
            height: swatch.miniature ? swatch.height * .71 : swatch.height - 6
            MaterialSurface {
                id: mainCoating
                objectName: swatch.miniature ? "skinSampleSurface_" + swatch.skin : "skinSummarySurface"
                anchors.fill: parent
                config: ({skin: swatch.skin, theme: ui.dark ? "dark" : "light", opacity: root.config.opacity,
                    glass_transparency: root.optionValue("glass_transparency"), glass_curvature: root.optionValue("glass_curvature")})
                frosted: true; cornerRadius: swatch.miniature ? 9 : 5
            }
            Column {
                x: 9; y: 8; width: parent.width - 18; spacing: 3; visible: swatch.miniature
                Text { text: "CPU"; color: swatch.foreground; opacity: .72; font.family: ui.fontFamily; font.pixelSize: 8; font.weight: Font.Medium }
                Row {
                    spacing: 3
                    Text { objectName: swatch.miniature ? "skinSampleReading_" + swatch.skin : "skinSummaryReading"; text: "68"; color: swatch.foreground; font.family: ui.fontFamily; font.pixelSize: 22; font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
                    Text { text: "°C"; y: 10; color: swatch.foreground; opacity: .72; font.family: ui.fontFamily; font.pixelSize: 9 }
                }
                Canvas {
                    id: miniTrend
                    width: parent.width; height: 15; antialiasing: true
                    onWidthChanged: requestPaint()
                    onPaint: {
                        const ctx = getContext("2d"), values = [.78,.61,.68,.3,.38,.2,.28,.14]
                        ctx.clearRect(0,0,width,height); ctx.strokeStyle = swatch.foreground; ctx.lineWidth = 1.1; ctx.lineJoin = "round"
                        ctx.beginPath()
                        for(let i=0;i<values.length;i++){const x=1+i*(width-2)/(values.length-1),y=1+values[i]*(height-2);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y)}
                        ctx.stroke()
                    }
                    Connections { target: ui; function onDarkChanged() { miniTrend.requestPaint() } }
                }
            }
            Text { visible: !swatch.miniature; anchors.centerIn: parent; text: "68°"; color: swatch.foreground; font.family: ui.fontFamily; font.pixelSize: 10; font.weight: Font.Medium }
        }
        Item {
            visible: swatch.miniature
            x: swatch.width * .625; y: swatch.height * .5; width: swatch.width * .3; height: swatch.height * .39
            MaterialSurface {
                objectName: "skinSampleSecondarySurface_" + swatch.skin
                anchors.fill: parent; config: mainCoating.config
                frosted: true; cornerRadius: 7
            }
            Column {
                anchors.fill: parent; anchors.margins: 6; spacing: 3
                Text { text: "RAM"; color: swatch.foreground; opacity: .72; font.family: ui.fontFamily; font.pixelSize: 7 }
                Text { text: "71%"; color: swatch.foreground; font.family: ui.fontFamily; font.pixelSize: 12; font.weight: Font.DemiBold }
                Rectangle { width: parent.width; height: 2; radius: 1; color: Qt.rgba(swatch.foreground.r,swatch.foreground.g,swatch.foreground.b,.15)
                    Rectangle { width: parent.width*.71; height: 2; radius: 1; color: swatch.foreground; opacity: .65 }
                }
            }
        }
    }
    Button {
        id: changeButton
        objectName: "skinPickerChangeButton"
        visible: root.compact
        Layout.fillWidth: true
        implicitHeight: 40
        padding: 8; leftPadding: 8; rightPadding: 12
        focusPolicy: Qt.StrongFocus
        Accessible.name: (root.value === "global" ? ui.t("跟随全局") + " · " : "") + root.skinLabel
        onClicked: chooser.open()
        contentItem: RowLayout {
            spacing: 10
            CoatingSwatch { skin: root.effectiveValue; Layout.preferredWidth: 48; Layout.preferredHeight: 28 }
            Text {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                text: changeButton.Accessible.name; textFormat: Text.PlainText
                font.family: ui.fontFamily; font.pixelSize: ui.bodySize; color: ui.ink; elide: Text.ElideRight
            }
            Icon { name: "down"; ink: ui.muted; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
        }
        background: GlassSurface { tone: "field"; focused: changeButton.activeFocus; highlighted: changeButton.hovered || chooser.opened }
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name
        ToolTip.delay: 600
    }
    Loader {
        Layout.fillWidth: true
        active: !root.compact
        sourceComponent: optionsComponent
        visible: active
    }
    Popup {
        id: chooser
        objectName: "skinPickerPopup"
        parent: Overlay.overlay
        readonly property point summaryPosition: parent ? changeButton.mapToItem(parent, 0, 0) : Qt.point(0, 0)
        width: Math.min(620, Math.max(520, root.width), parent ? parent.width - 32 : 620)
        height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, parent ? parent.height - 32 : 420)
        x: parent ? Math.max(16, Math.min(parent.width - width - 16, summaryPosition.x)) : 0
        y: parent ? Math.max(16, Math.min(parent.height - height - 16,
            summaryPosition.y + changeButton.height + 6 + height <= parent.height - 16
                ? summaryPosition.y + changeButton.height + 6 : summaryPosition.y - height - 6)) : 0
        padding: 16
        modal: false; focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: Qt.callLater(() => { if (popupOptions.item) popupOptions.item.focusSelected() })
        onClosed: Qt.callLater(() => { if (root.compact && changeButton.visible) changeButton.forceActiveFocus() })
        background: GlassSurface { tone: "popup"; radius: 10 }
        contentItem: ColumnLayout {
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: ui.t("组件皮肤"); font.family: ui.fontFamily; font.pixelSize: ui.sectionSize; font.weight: Font.DemiBold; color: ui.ink }
                ToolButton {
                    id: closeButton
                    objectName: "closeSkinPicker"
                    implicitWidth: 28; implicitHeight: 28; padding: 6
                    Accessible.name: ui.t("关闭")
                    onClicked: chooser.close()
                    contentItem: Icon { name: "close"; ink: ui.muted }
                    background: Rectangle { radius: 6; color: ui.hover; visible: closeButton.hovered || closeButton.activeFocus; border.width: closeButton.activeFocus ? 1 : 0; border.color: ui.accent }
                }
            }
            ScrollView {
                id: optionsScroll
                objectName: "skinPickerOptionsScroll"
                Layout.fillWidth: true; Layout.fillHeight: true
                implicitHeight: popupOptions.implicitHeight
                contentWidth: availableWidth; contentHeight: popupOptions.implicitHeight
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                Loader {
                    id: popupOptions
                    width: optionsScroll.availableWidth
                    active: chooser.opened
                    sourceComponent: optionsComponent
                }
            }
        }
    }
    Component {
        id: optionsComponent
        ColumnLayout {
            id: choices
            spacing: 10
            readonly property int columns: width >= 520 ? 3 : width >= 270 ? 2 : 1
            function focusAt(index) {
                const offset = root.allowGlobal ? 1 : 0
                const position = Math.max(0, Math.min(optionRepeater.count + offset - 1, index))
                const target = root.allowGlobal && position === 0 ? globalOption : optionRepeater.itemAt(position - offset)
                if (target) {
                    target.forceActiveFocus()
                    if (root.compact && optionsScroll.contentItem) {
                        const flick = optionsScroll.contentItem
                        const p = target.mapToItem(choices, 0, 0)
                        if (p.y < flick.contentY) flick.contentY = p.y
                        else if (p.y + target.height > flick.contentY + optionsScroll.availableHeight) flick.contentY = p.y + target.height - optionsScroll.availableHeight
                    }
                }
            }
            function focusSelected() {
                const index = stats.catalog.skins.findIndex(option => option.id === root.value)
                focusAt(root.value === "global" && root.allowGlobal ? 0 : Math.max(0, index) + (root.allowGlobal ? 1 : 0))
            }
            ActionButton {
                id: globalOption
                objectName: "skinOption_global"
                visible: root.allowGlobal
                Layout.fillWidth: true
                text: (root.value === "global" ? "✓  " : "") + ui.t("跟随全局")
                implicitHeight: 34
                quiet: root.value !== "global"
                onClicked: root.choose("global")
                Keys.onDownPressed: event => { choices.focusAt(1); event.accepted = true }
                Keys.onReturnPressed: event => { root.choose("global"); event.accepted = true }
                Keys.onEnterPressed: event => { root.choose("global"); event.accepted = true }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: choices.columns
                uniformCellWidths: true; columnSpacing: 8; rowSpacing: 8
                Repeater {
                    id: optionRepeater
                    model: stats.catalog.skins
                    ItemDelegate {
                        id: option
                        required property var modelData
                        required property int index
                        readonly property bool selected: root.value === modelData.id
                        objectName: "skinOption_" + modelData.id
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        implicitHeight: 188; padding: 8
                        focusPolicy: Qt.StrongFocus
                        Accessible.name: modelData.label
                        Accessible.description: root.description(modelData.id)
                        Accessible.role: Accessible.RadioButton; Accessible.checked: selected
                        onClicked: root.choose(modelData.id)
                        ToolTip.visible: hovered
                        ToolTip.text: modelData.label+"\n"+root.description(modelData.id)
                        ToolTip.delay: 600
                        Keys.onReturnPressed: event => { root.choose(modelData.id); event.accepted = true }
                        Keys.onEnterPressed: event => { root.choose(modelData.id); event.accepted = true }
                        Keys.onLeftPressed: event => { choices.focusAt(index + (root.allowGlobal ? 1 : 0) - 1); event.accepted = true }
                        Keys.onRightPressed: event => { choices.focusAt(index + (root.allowGlobal ? 1 : 0) + 1); event.accepted = true }
                        Keys.onUpPressed: event => { choices.focusAt(index + (root.allowGlobal ? 1 : 0) - choices.columns); event.accepted = true }
                        Keys.onDownPressed: event => { choices.focusAt(index + (root.allowGlobal ? 1 : 0) + choices.columns); event.accepted = true }
                        background: Rectangle {
                            radius: 8
                            color: option.selected ? ui.selection : option.hovered ? ui.hover : ui.well
                            border.width: 1
                            border.color: option.activeFocus ? ui.accent : option.selected ? ui.selectedLine : "transparent"
                        }
                        contentItem: ColumnLayout {
                            spacing: 6
                            CoatingSwatch { skin: option.modelData.id; Layout.fillWidth: true; Layout.preferredHeight: 112 }
                            RowLayout {
                                Layout.fillWidth: true; spacing: 5
                                Text {
                                    Layout.fillWidth: true; Layout.minimumWidth: 0
                                    text: option.modelData.label; textFormat: Text.PlainText
                                    color: ui.ink; font.family: ui.fontFamily; font.pixelSize: ui.captionSize
                                    font.weight: option.selected ? Font.DemiBold : Font.Normal
                                    elide: Text.ElideRight
                                }
                                Icon { name: "check"; ink: ui.accent; visible: option.selected; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
                            }
                            Text {
                                objectName: "skinDescription_"+option.modelData.id
                                Layout.fillWidth: true; Layout.minimumWidth: 0
                                text: root.description(option.modelData.id); textFormat: Text.PlainText
                                color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 10
                                wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: ui.t("材质示意")
                font.family: ui.fontFamily; font.pixelSize: ui.metaSize; color: ui.muted; wrapMode: Text.WordWrap
            }
            Text {
                objectName: "skinMaterialStatus"
                Layout.fillWidth: true
                visible: root.glassChosen
                text: root.materialStatus
                font.family: ui.fontFamily; font.pixelSize: ui.metaSize; color: ui.muted; wrapMode: Text.WordWrap
            }
        }
    }
}
