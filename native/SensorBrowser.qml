import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id:root
    property bool active:true
    property string query:""
    property string category:"all"
    property var rows:{const revision=stats.sensorRevision;return active?stats.sensorRows:[]}
    property var entries:[]
    property var externalInfo:active?stats.externalStatus:({})
    property bool restoringFocus:false
    property int modelGeneration:0
    readonly property var byId: {
        const result={}
        for(const row of rows)result[row.id]=row
        return result
    }
    spacing:10
    Theme { id:ui }
    function filterRows(preserveViewport) {
        const q=query.trim().toLowerCase()
        const next=rows.filter(row=>(category==="all" || row.category===category) && (!q || [row.search,row.label,row.hardware_name,row.source,row.unit].filter(Boolean).join(" ").toLowerCase().includes(q)))
        if(next.map(row=>row.id).join(",")!==entries.map(row=>row.id).join(",")) {
            const y=list.contentY
            const focused=!!list.currentItem && list.currentItem.activeFocus
            const current=list.currentItem ? list.currentItem.modelData.id : ""
            const generation=++modelGeneration
            entries=next
            const index=entries.findIndex(row=>row.id===current)
            list.currentIndex=index>=0 ? index : Math.min(list.currentIndex,entries.length-1)
            if(preserveViewport)Qt.callLater(()=>{
                if(generation!==root.modelGeneration)return
                root.restoringFocus=true
                if(focused && list.currentItem)list.currentItem.forceActiveFocus()
                root.restoringFocus=false
                list.contentY=Math.max(0,Math.min(y,Math.max(0,list.contentHeight-list.height)))
            })
        }
    }
    function focusIndex(index) {
        if(!entries.length)return
        list.currentIndex=Math.max(0,Math.min(entries.length-1,index))
        list.positionViewAtIndex(list.currentIndex,ListView.Contain)
        Qt.callLater(()=>{if(list.currentItem)list.currentItem.forceActiveFocus()})
    }
    onQueryChanged:filterRows()
    onCategoryChanged:filterRows()
    onRowsChanged:filterRows(true)
    Component.onCompleted:filterRows()
    RowLayout {
        Layout.fillWidth:true; spacing:12
        ColumnLayout {
            Layout.fillWidth:true; spacing:4
            Text {
                Layout.fillWidth:true; text:"LibreHardwareMonitor"+(root.externalInfo.version ? " · "+root.externalInfo.version : "")
                color:ui.ink; font.family:ui.fontFamily; font.pixelSize:12; font.weight:Font.DemiBold; elide:Text.ElideRight
                HoverHandler { id:sourceHover }
                ToolTip.visible:sourceHover.hovered && !!root.externalInfo.updated_at
                ToolTip.text:ui.t("更新时间")+" · "+(typeof root.externalInfo.updated_at==="number"?new Date(root.externalInfo.updated_at*1000).toLocaleTimeString():root.externalInfo.updated_at || "")
            }
            Text { objectName:"externalSourceDetail"; Layout.fillWidth:true; text:ui.t(root.externalInfo.detail || "等待扩展传感器"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap }
        }
        ActionButton {objectName:"sourceDiagnosticsButton";text:ui.t("来源诊断");quiet:true;implicitHeight:30;onClicked:diagnostics.open()}
        ActionButton { objectName:"rescanExternalButton"; text:ui.t("重新扫描"); quiet:true; implicitHeight:30; onClicked:stats.rescanExternal() }
    }
    RowLayout {
        Layout.fillWidth:true; spacing:8
        TextField {
            id:search; objectName:"sensorSearch"; Layout.fillWidth:true; implicitHeight:36
            text:root.query; onTextEdited:root.query=text
            placeholderText:ui.t("搜索传感器或硬件"); placeholderTextColor:ui.muted
            font.family:ui.fontFamily; font.pixelSize:12; color:ui.ink; selectByMouse:true; leftPadding:33
            background:GlassSurface { tone:"field"; focused:search.activeFocus }
            Icon { x:10; anchors.verticalCenter:parent.verticalCenter; width:14; height:14; name:"search"; ink:ui.muted }
            Keys.onDownPressed:event=>{root.focusIndex(0);event.accepted=true}
        }
        Choice {
            objectName:"sensorCategoryChoice"; Layout.preferredWidth:140
            model:stats.catalog.categories; value:root.category
            onPicked:selected=>root.category=selected
        }
    }
    RowLayout {
        Layout.fillWidth:true
        Text { objectName:"sensorResultCount"; text:root.entries.length+" / "+root.rows.length+" "+ui.t("项指标"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10 }
        Item { Layout.fillWidth:true }
        Text { text:(root.externalInfo.sensor_count || 0)+" "+ui.t("扩展指标")+" · "+(root.externalInfo.hardware_count || 0)+" "+ui.t("个硬件"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10 }
    }
    ListView {
        id:list; objectName:"sensorResultsList"
        Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight:70
        model:root.entries; clip:true; spacing:6; boundsBehavior:Flickable.StopAtBounds
        cacheBuffer:80; reuseItems:true; keyNavigationEnabled:true
        ScrollBar.vertical:ScrollBar { }
        delegate:ItemDelegate {
            id:sensor
            required property var modelData
            required property int index
            readonly property var live:root.byId[modelData.id] || modelData
            objectName:"sensorRow_"+modelData.id
            width:list.width-8; height:live.available || !live.hardware_name ? 57 : 74
            padding:0; focusPolicy:Qt.StrongFocus
            onClicked:list.currentIndex=index
            onActiveFocusChanged:if(activeFocus) {list.currentIndex=index;if(!root.restoringFocus)list.positionViewAtIndex(index,ListView.Contain)}
            Keys.onDownPressed:event=>{root.focusIndex(index+1);event.accepted=true}
            Keys.onUpPressed:event=>{root.focusIndex(index-1);event.accepted=true}
            Keys.onPressed:event=>{
                if(event.key===Qt.Key_Home) {root.focusIndex(0);event.accepted=true}
                else if(event.key===Qt.Key_End) {root.focusIndex(root.entries.length-1);event.accepted=true}
            }
            background:Rectangle { radius:10; color:sensor.hovered || sensor.activeFocus ? ui.hover : ui.tile; border.color:sensor.activeFocus?ui.accent:"transparent" }
            contentItem:Item {
                Text { x:12; y:9; width:parent.width-128; text:sensor.live.label || ""; textFormat:Text.PlainText; color:ui.ink; font.family:ui.fontFamily; font.pixelSize:12; elide:Text.ElideRight }
                Text { anchors.right:parent.right; anchors.rightMargin:12; y:8; width:104; horizontalAlignment:Text.AlignRight; text:sensor.live.available?sensor.live.value:"—"; color:sensor.live.available?ui.ink:ui.muted; font.family:ui.fontFamily; font.pixelSize:14; font.weight:Font.DemiBold; elide:Text.ElideRight }
                Text { x:12; y:31; width:parent.width-24; text:sensor.live.hardware_name || (sensor.live.available ? sensor.live.source : sensor.live.reason) || ""; textFormat:Text.PlainText; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10; elide:Text.ElideRight }
                Text { x:12; y:49; width:parent.width-24; visible:!sensor.live.available && !!sensor.live.hardware_name; text:sensor.live.reason || ui.t("当前设备未提供"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10; elide:Text.ElideRight }
            }
            Accessible.name:(live.hardware_name ? live.hardware_name+" · " : "")+live.label
            Accessible.description:live.available ? live.value : live.reason || ""
            ToolTip.visible:hovered
            ToolTip.delay:600
            ToolTip.text:[live.hardware_name,live.label,live.source,live.available?live.value:live.reason,live.note].filter(Boolean).join("\n")
        }
        Text { anchors.centerIn:parent; visible:root.entries.length===0; text:ui.t("没有匹配的结果"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:12 }
    }
    Text { Layout.fillWidth:true; text:ui.t("未提供的传感器显示为 —，不会估算。"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10; wrapMode:Text.WordWrap }
    Popup {
        id:diagnostics;objectName:"sourceDiagnosticsPopup";parent:Overlay.overlay
        width:Math.min(620,parent.width-32);height:Math.min(480,parent.height-32)
        x:(parent.width-width)/2;y:(parent.height-height)/2;padding:20;modal:true;focus:true
        background:GlassSurface {tone:"popup"}
        ColumnLayout {anchors.fill:parent;spacing:12
            RowLayout {Layout.fillWidth:true
                Text {Layout.fillWidth:true;text:ui.t("来源诊断");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:16;font.weight:Font.DemiBold}
                IconButton {symbol:"close";label:ui.t("关闭");onClicked:diagnostics.close()}
            }
            Text {Layout.fillWidth:true;text:ui.t("显示本轮实际返回的状态；没有证据时保留未知，不判断为权限不足。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
            ScrollView {Layout.fillWidth:true;Layout.fillHeight:true;contentWidth:availableWidth;clip:true
                TextArea {readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;textFormat:TextEdit.PlainText;padding:4;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;background:null
                    text:{const revision=stats.sensorRevision;return stats.sourceDiagnostics.map(row=>[row.label+" · "+row.state,row.detail,row.errors].filter(Boolean).join("\n")).join("\n\n") || ui.t("等待读数")}
                }
            }
        }
    }
}
