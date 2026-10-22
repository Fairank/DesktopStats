import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import DesktopStats 1.0
Item {
    id: root
    property string selectedKey: ""
    function showActualSize() { actualPreview.open() }
    property var prefs: stats.draft.widgets[selectedKey]
    property var previewInfo: { const layout=stats.previewWindows; return stats.previewState(selectedKey) }
    property double healthClock: Date.now()/1000
    readonly property var health: {
        const readings=stats.readings
        const draft=stats.draft
        const tick=root.healthClock
        return stats.widgetHealth(root.selectedKey)
    }
    readonly property bool fresh: root.health.fresh===true
    readonly property int available: root.health.available || 0
    readonly property string healthState: root.health.state || "waiting"
    readonly property color healthColor: healthState==="ready" ? "#19845a" : healthState==="partial" || healthState==="stale" ? "#956317" : ui.muted
    readonly property string healthSummary: healthState==="waiting" || healthState==="empty" ? ui.t("等待读数") : healthState==="stale" ? ui.t("读数已过期") : available+" / "+(health.total || 0)+" "+ui.t("项可用")
    readonly property var missing: root.health.missing || []
    readonly property string materialLabel: previewInfo.skin==="minimal" ? ui.t("无底色") : previewInfo.status ? ui.t(previewInfo.status) : ui.t("实色底色")
    readonly property string materialNote: {
        if (!["glass","frost","tint"].includes(root.previewInfo.skin)) return ""
        if (root.previewInfo.compositing_verified===true) return ui.t("系统效果已确认")
        return root.previewInfo.blur_configured ? ui.t("系统模糊尚未确认。") : root.previewInfo.coating_translucent ? ui.t("透明背景，未启用系统模糊。") : ui.t("系统已关闭透明效果，使用实色背景。")
    }
    property int actualHeight: root.previewInfo.height || 168
    property int actualWidth: root.previewInfo.width || actualHeight
    readonly property real cardWidth: Math.min(Math.max(1,width-32),actualWidth)
    readonly property real cardHeight: cardWidth*actualHeight/actualWidth
    implicitHeight: box.implicitHeight
    Theme { id: ui }
    Timer {
        interval:1000; repeat:true; running:!!root.Window.window && root.Window.window.visible
        onTriggered:root.healthClock=Date.now()/1000
    }
    Component {
        id:healthDetails
        ColumnLayout {
            spacing:7
            RowLayout {
                Layout.fillWidth:true; spacing:7
                Rectangle { objectName:"previewHealthDot"; width:5; height:5; radius:3; color:root.healthColor }
                Text { objectName:"previewHealthSummary"; Layout.fillWidth:true; text:root.healthSummary; color:ui.ink; font.family:ui.fontFamily; font.pixelSize:11; font.weight:Font.Medium; wrapMode:Text.WordWrap }
                Text { visible:root.health.age_seconds!==null && root.health.age_seconds!==undefined; text:Math.max(0,Math.floor(root.health.age_seconds || 0))+" "+ui.t("秒前"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10 }
            }
            Repeater {
                model:root.missing.slice(0,2)
                Text {
                    required property var modelData
                    Layout.fillWidth:true
                    text:modelData.label+" · "+modelData.reason
                    color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11
                    wrapMode:Text.WordWrap; lineHeight:1.15
                }
            }
            Text { visible:root.missing.length>2; text:"＋ "+Math.max(0,root.missing.length-2)+" "+ui.t("项未就绪"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11 }
        }
    }
    ColumnLayout {
        id:box; anchors.left:parent.left; anchors.right:parent.right; anchors.top:parent.top; spacing:14
        RowLayout {
            Layout.fillWidth:true
            Text { text:ui.t("组件预览"); color:ui.ink; font.family:ui.fontFamily; font.pixelSize:13; font.weight:Font.DemiBold }
            Item { Layout.fillWidth:true }
            IconButton { symbol:"search"; label:ui.t("实际大小"); enabled:!!root.prefs; onClicked:root.showActualSize() }
        }
        Item {
            objectName:"previewStage"
            Layout.fillWidth:true; implicitHeight:root.cardHeight+40
            Rectangle { anchors.fill:parent; radius:16; color:ui.previewCanvas }
            WidgetPreview {
                objectName:"inlineWidgetPreview"
                anchors.centerIn:parent; width:root.cardWidth; height:root.cardHeight
                moduleKey:root.selectedKey; config:stats.draft; previewInfo:root.previewInfo
                readings:root.Window.window && root.Window.window.visible ? stats.readings : ({})
                history:root.Window.window && root.Window.window.visible ? stats.history : []
                visible:!!root.prefs
            }
            Text { anchors.centerIn:parent; visible:!root.prefs; text:ui.t("添加第一个小组件"); font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted }
        }
        ColumnLayout {
            spacing:5; Layout.fillWidth:true
            Text { objectName:"previewSizeLabel"; Layout.fillWidth:true; text:root.prefs ? root.actualWidth+" × "+root.actualHeight+" · "+ui.t("预览")+" "+Math.round(root.cardWidth/root.actualWidth*100)+"%" : ""; font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted }
            Text { objectName:"previewMaterialLabel"; Layout.fillWidth:true; text:root.materialLabel+(root.materialNote ? " · "+root.materialNote : ""); font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted; wrapMode:Text.WordWrap; lineHeight:1.15 }
            Text { Layout.fillWidth:true; visible:!!root.previewInfo.note; text:ui.t(root.previewInfo.note || ""); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap; lineHeight:1.15 }
        }
        Rectangle { Layout.fillWidth:true; implicitHeight:1; color:ui.line }
        Text { Layout.fillWidth:true; visible:!!root.previewInfo.layout_warning; text:ui.t(root.previewInfo.layout_warning || ""); color:ui.ink; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap; lineHeight:1.15 }
        Loader { Layout.fillWidth:true; sourceComponent:healthDetails; visible:!!root.prefs }
        Text { Layout.fillWidth:true; text:ui.t("桌面上")+" "+(stats.draft.visible?stats.previewWindows.reduce((n,w)=>n+w.cells.length,0):0)+" "+ui.t("个小组件"); font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted }
        Text { Layout.fillWidth:true; text:ui.t("拖动边角缩放，松手自动排列。"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap; lineHeight:1.15 }
    }
    Popup {
        id:actualPreview; objectName:"actualSizePreview"; parent:Overlay.overlay; anchors.centerIn:parent
        width:Math.min(parent?parent.width-32:640,Math.max(300,root.actualWidth+48))
        height:Math.min(parent?parent.height-32:640,actualContent.implicitHeight+48)
        modal:true; focus:true; padding:24
        closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
        background:GlassSurface { radius:18; tone:"popup" }
        ScrollView {
            id:actualScroll
            anchors.fill:parent; contentWidth:Math.max(availableWidth,root.actualWidth+16); clip:true
            ScrollBar.horizontal.policy:ScrollBar.AsNeeded
            ColumnLayout {
                id:actualContent; width:Math.max(actualScroll.availableWidth,root.actualWidth+16); spacing:14
                RowLayout {
                    Layout.fillWidth:true
                    Text { text:ui.t("实际大小")+" · "+root.actualWidth+" × "+root.actualHeight; font.family:ui.fontFamily; font.pixelSize:13; font.weight:Font.DemiBold; color:ui.ink; Layout.fillWidth:true; wrapMode:Text.WordWrap }
                    IconButton { symbol:"close"; label:ui.t("关闭"); onClicked:actualPreview.close() }
                }
                Item {
                    Layout.alignment:Qt.AlignHCenter; Layout.preferredWidth:root.actualWidth; Layout.preferredHeight:root.actualHeight
                    Rectangle { anchors.fill:parent; anchors.margins:-8; radius:16; color:ui.previewCanvas }
                    WidgetPreview { objectName:"actualWidgetPreview"; anchors.fill:parent; moduleKey:root.selectedKey; config:stats.draft; previewInfo:root.previewInfo; readings:actualPreview.opened?stats.readings:({}); history:actualPreview.opened?stats.history:[] }
                }
                Text { Layout.fillWidth:true; Layout.topMargin:4; text:root.materialLabel+(root.materialNote ? " · "+root.materialNote : ""); font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted; wrapMode:Text.WordWrap }
                Loader { Layout.fillWidth:true; sourceComponent:healthDetails }
            }
        }
    }
}
