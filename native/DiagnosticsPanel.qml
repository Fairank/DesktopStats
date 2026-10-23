import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id:root
    objectName:"diagnosticsPanel"
    property var controller:stats
    property bool active:true
    property bool closable:false
    signal closeRequested()
    property var expandedIds:[]
    readonly property var sources:active?controller.diagnosticCards:[]
    property var sourceIds:[]
    readonly property var sourceById: {
        const entries={}
        for(const source of sources)entries[source.id]=source
        return entries
    }
    readonly property var check:controller.diagnosticCheck || ({})
    readonly property bool checking:check.state==="checking"
    readonly property int healthy:sources.filter(row=>row.healthy).length
    spacing:14
    Theme {id:ui}
    function toggle(identifier) {
        expandedIds=expandedIds.includes(identifier)?expandedIds.filter(id=>id!==identifier):expandedIds.concat([identifier])
    }
    function updateSourceIds() {
        const next=sources.map(source=>source.id)
        if(next.join("\n")===sourceIds.join("\n"))return
        const previousY=list?list.contentY:0
        sourceIds=next
        Qt.callLater(()=>{if(list)list.contentY=Math.max(0,Math.min(previousY,Math.max(0,list.contentHeight-list.height)))})
    }
    onSourcesChanged:updateSourceIds()
    Component.onCompleted:updateSourceIds()
    RowLayout {
        Layout.fillWidth:true;spacing:10
        ColumnLayout {
            Layout.fillWidth:true;spacing:5
            Text {text:ui.t("读数从哪里来");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:18;font.weight:Font.DemiBold}
            Text {Layout.fillWidth:true;text:ui.t("先看原因，再选择下一步。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
        }
        Text {objectName:"diagnosticHealthyCount";visible:root.sources.length>0;text:root.healthy+" / "+root.sources.length+" "+ui.t("正常");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
        IconButton {visible:root.closable;symbol:"close";label:ui.t("关闭");onClicked:root.closeRequested()}
    }
    RowLayout {
        Layout.fillWidth:true;spacing:8
        ActionButton {objectName:"diagnosticCheckButton";text:ui.t(root.checking?"正在检查…":"重新检查");accent:true;enabled:!root.checking;onClicked:root.controller.checkSources()}
        ActionButton {objectName:"diagnosticExportButton";text:ui.t("导出诊断");onClicked:root.controller.exportDiagnostics()}
        Item {Layout.fillWidth:true}
    }
    Text {objectName:"diagnosticCheckFeedback";Layout.fillWidth:true;visible:!!root.check.detail;text:root.check.detail;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
    ListView {
        id:list;objectName:"diagnosticSourcesList"
        Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:130
        model:root.sourceIds;clip:true;spacing:8;boundsBehavior:Flickable.StopAtBounds
        ScrollBar.vertical:ScrollBar {policy:ScrollBar.AsNeeded}
        delegate:Rectangle {
            id:card
            required property string modelData
            readonly property var source:root.sourceById[modelData] || ({id:modelData,label:"",healthy:false,badge:"",detail:"",hint:"",errors:""})
            objectName:"diagnosticCard_"+source.id
            readonly property bool expanded:root.expandedIds.includes(source.id)
            readonly property color statusColor:source.healthy?(ui.dark?"#8fceaf":"#287253"):ui.muted
            width:list.width-8;height:body.implicitHeight+26;radius:11;color:ui.card;border.color:ui.line
            ColumnLayout {
                id:body;x:14;y:13;width:parent.width-28;spacing:9
                RowLayout {
                    Layout.fillWidth:true;spacing:8
                    Icon {name:({nvml:"gpu",asus:"fan",battery:"battery",network:"network",disk:"disk",volumes:"disk",storage:"disk",hwinfo:"power"})[card.source.id] || "sensors";ink:ui.muted;Layout.preferredWidth:16;Layout.preferredHeight:16}
                    Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:card.source.label;textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.DemiBold;elide:Text.ElideRight}
                    Rectangle {width:6;height:6;radius:3;color:card.statusColor}
                    Text {text:card.source.badge;color:card.statusColor;font.family:ui.fontFamily;font.pixelSize:11}
                }
                Text {Layout.fillWidth:true;text:card.source.detail || card.source.hint;textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
                Text {Layout.fillWidth:true;visible:!!card.source.detail;text:card.source.hint;textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                ActionButton {objectName:"diagnosticDetails_"+card.source.id;visible:!!card.source.errors;text:ui.t(card.expanded?"收起接口详情":"查看接口详情");quiet:true;implicitHeight:26;leftPadding:0;onClicked:root.toggle(card.source.id)}
                Rectangle {
                    Layout.fillWidth:true;implicitHeight:errorText.implicitHeight+18;visible:card.expanded && !!card.source.errors
                    radius:7;color:ui.well
                    TextEdit {id:errorText;objectName:"diagnosticErrorText_"+card.source.id;x:9;y:9;width:parent.width-18;readOnly:true;selectByMouse:true;text:card.source.errors || "";textFormat:TextEdit.PlainText;wrapMode:TextEdit.Wrap;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                }
            }
        }
        Column {
            anchors.centerIn:parent;width:Math.min(320,parent.width-32);spacing:8;visible:root.sources.length===0
            Icon {anchors.horizontalCenter:parent.horizontalCenter;name:"sensors";ink:ui.muted;width:24;height:24}
            Text {width:parent.width;text:ui.t("等待第一轮读数");horizontalAlignment:Text.AlignHCenter;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:14;font.weight:Font.Medium}
            Text {width:parent.width;text:ui.t("重新检查会请求新的读数，不会自动修改权限或安装驱动。");horizontalAlignment:Text.AlignHCenter;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
        }
    }
    Text {Layout.fillWidth:true;text:ui.t("导出仅包含软件版本和接口状态，不含原始读数、设备标识或本地路径。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
}
