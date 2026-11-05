import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Window {
    id:root
    property string widgetKey:""
    property int metricIndex:0
    readonly property var state:{const fresh=stats.readings;const saved=stats.saved;return stats.detailState(widgetKey,metricIndex)}
    width:326; height:Math.min(600,340+(state.items || []).length*35)
    visible:false; color:"transparent"
    flags:Qt.Popup | Qt.FramelessWindowHint
    title:"Desktop Stats"
    Theme { id:ui }
    Rectangle { anchors.fill:parent; radius:16; color:ui.dark?"#f0262b34":"#faF7F9FC"; border.color:ui.line }
    ColumnLayout {
        anchors.fill:parent; anchors.margins:18; spacing:10
        RowLayout {
            Layout.fillWidth:true
            Text { Layout.fillWidth:true; text:root.state.title || ""; textFormat:Text.PlainText; color:ui.ink; font.family:ui.fontFamily; font.pixelSize:13; font.weight:Font.DemiBold; elide:Text.ElideRight }
            ActionButton { text:"×"; quiet:true; implicitWidth:28; implicitHeight:28; Accessible.name:ui.t("关闭"); onClicked:root.hide() }
        }
        Text { Layout.fillWidth:true; Layout.minimumWidth:0; text:(root.state.selected || {}).label || ""; textFormat:Text.PlainText; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; elide:Text.ElideRight
            ToolTip.visible:detailLabelHover.hovered; ToolTip.text:text
            HoverHandler { id:detailLabelHover }
        }
        Text {
            Layout.fillWidth:true; Layout.minimumWidth:0; Layout.preferredHeight:42
            text:(root.state.selected || {}).value || "—"; color:ui.ink; font.family:ui.fontFamily
            font.pixelSize:32; font.weight:Font.DemiBold; textFormat:Text.PlainText
            fontSizeMode:Text.Fit; minimumPixelSize:10; verticalAlignment:Text.AlignVCenter
            ToolTip.visible:detailValueHover.hovered; ToolTip.text:text
            HoverHandler { id:detailValueHover }
        }
        Text {
            Layout.fillWidth:true; Layout.minimumWidth:0
            text:[(root.state.selected || {}).hardware_name,(root.state.selected || {}).source].filter(v=>!!v).join(" · ")
            textFormat:Text.PlainText; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10; elide:Text.ElideRight
            ToolTip.visible:detailSourceHover.hovered; ToolTip.text:text
            HoverHandler { id:detailSourceHover }
        }
        Rectangle { Layout.fillWidth:true; height:1; color:ui.line }
        ScrollView {
            id: detailScroll
            objectName: "widgetDetailScroll"
            Layout.fillWidth:true; Layout.fillHeight:true; clip:true; contentWidth:availableWidth
            ScrollBar.vertical:ScrollBar { }
            ColumnLayout {
                width:detailScroll.availableWidth; spacing:10
                ProcessUsageCard {
                    Layout.fillWidth:true; provider:stats
                    metric:(root.state.selected || {}).id || ""
                    hardwareName:(root.state.selected || {}).hardware_name || ""
                    active:root.visible && root.visibility!==Window.Minimized
                    ink:ui.ink; muted:ui.muted; fontFamily:ui.fontFamily
                    motionEnabled:ui.motionAllowed
                }
                Repeater {
                    model:root.state.items || []
                    delegate:ItemDelegate {
                        id:row
                        required property var modelData
                        required property int index
                        Layout.fillWidth:true; implicitHeight:35
                        onClicked:root.metricIndex=index
                        background:Rectangle { radius:7; color:row.hovered || row.index===root.metricIndex?ui.hover:"transparent" }
                        contentItem:RowLayout {
                            Text { Layout.fillWidth:true; Layout.minimumWidth:0; text:row.modelData.label; textFormat:Text.PlainText; font.family:ui.fontFamily; font.pixelSize:11; color:ui.muted; elide:Text.ElideRight }
                            Text { text:row.modelData.value; textFormat:Text.PlainText; font.family:ui.fontFamily; font.pixelSize:13; font.weight:Font.DemiBold; color:ui.ink }
                        }
                    }
                }
            }
        }
        ActionButton { Layout.fillWidth:true; quiet:true; text:ui.t("编辑此组件"); onClicked:{root.hide();stats.openSettings(root.widgetKey)} }
    }
    Shortcut { sequence:"Escape"; onActivated:root.hide() }
}
