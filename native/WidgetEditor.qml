import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Item {
    id:root
    readonly property var config:stats.draft
    required property string selectedKey
    property bool active:visible
    property bool resizing:false
    signal requestReadings(string key)
    signal selectKey(string key)
    signal requestApply()
    readonly property var prefs:root.config.widgets[selectedKey] || ({})
    readonly property var meta:stats.catalog.modules.find(m=>m.id===prefs.kind) || ({})
    readonly property bool wide:width>=700
    readonly property real centerWidth:width
    readonly property real workWidth:Math.min(centerWidth,860)
    readonly property real contentInset:Math.max(24,(centerWidth-workWidth)/2+24)
    readonly property string currentPreset:prefs.form==="bar"?"horizontal":prefs.layout_mode==="vertical"?"vertical":"card"
    property string section:"style"
    property alias canvas:canvas
    readonly property bool pendingInput:inspector.pendingInput
    property bool expandedCanvas:false
    property bool defaultsOpen:false
    property bool gestureCompact:false
    readonly property bool compactEligible:!expandedCanvas && workWidth>=430 && canvas.zoom<=1 && currentPreset!=="horizontal"
    readonly property bool compactWorkspace:canvas.widgetResizing?gestureCompact:compactEligible
    readonly property real compactStageLimit:Math.max(160,Math.min(360,workspace.height*.66))
    readonly property real naturalStageHeight:root.compactWorkspace?Math.max(156,Math.min(200,canvas.designHeight+64)):Math.max(104,Math.min(220,canvas.designHeight+64))
    Theme {id:ui}
    component EditorMenu: Menu {
        id:menuControl
        padding:6
        font.family:ui.fontFamily
        font.pixelSize:14
        onCurrentIndexChanged:Qt.callLater(()=>{
            if(menuControl.opened && menuControl.currentIndex>=0 && menuControl.contentItem)
                menuControl.contentItem.positionViewAtIndex(menuControl.currentIndex,ListView.Contain)
        })
        background:Rectangle {
            implicitWidth:208;implicitHeight:40;radius:10;antialiasing:true
            color:ui.dark?"#292a2d":"#fbfbfc"
            border.color:ui.dark?"#4b4e55":"#d8dbe1";border.width:1
        }
    }
    component EditorMenuItem: MenuItem {
        id:entry
        property string glyph:""
        property bool danger:false
        property bool caption:false
        readonly property color normalInk:ui.dark?"#f1f3f4":"#202124"
        readonly property color mutedInk:ui.dark?"#b8bdc5":"#62666d"
        readonly property color disabledInk:ui.dark?"#858a93":"#92969e"
        readonly property color dangerInk:ui.dark?"#ffb4ab":"#b3261e"
        implicitHeight:caption?28:32
        implicitWidth:Math.max(196,contentItem.implicitWidth+leftPadding+rightPadding)
        leftPadding:10;rightPadding:10;topPadding:4;bottomPadding:4
        font.family:ui.fontFamily;font.pixelSize:caption?12:14
        font.weight:caption?Font.Medium:Font.Normal
        hoverEnabled:true
        contentItem:RowLayout {
            spacing:10
            Icon {
                visible:entry.glyph.length>0;name:entry.glyph
                Layout.preferredWidth:16;Layout.preferredHeight:16
                ink:!entry.enabled?entry.disabledInk:entry.danger?entry.dangerInk:entry.mutedInk
            }
            Text {
                Layout.fillWidth:true;Layout.minimumWidth:0
                text:entry.text;textFormat:Text.PlainText;font:entry.font
                color:entry.caption?entry.mutedInk:!entry.enabled?entry.disabledInk:entry.danger?entry.dangerInk:entry.normalInk
                verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight
            }
        }
        background:Rectangle {
            radius:5;antialiasing:true
            visible:entry.enabled && entry.highlighted
            color:entry.danger?(ui.dark?"#533332":"#fcebe9"):(ui.dark?"#3b3e44":"#edf0f4")
        }
    }
    component EditorMenuSeparator: MenuSeparator {
        leftPadding:10;rightPadding:10;topPadding:4;bottomPadding:4
        implicitHeight:9
        contentItem:Rectangle {implicitWidth:180;implicitHeight:1;color:ui.dark?"#42454b":"#e2e4e8"}
    }
    function cancelEditing(){return canvas.cancelDrag()}
    function showInspector(section){root.section=section || "style";inspector.openSection(root.section);Qt.callLater(()=>{const flick=workspace.contentItem,position=inspector.sectionPosition(root.section);if(flick)flick.contentY=Math.min(Math.max(0,flick.contentHeight-flick.height),inspector.y+position)})}
    function revealFocus(){
        const win=root.Window.window,item=win?win.activeFocusItem:null,flick=workspace.contentItem
        if(!item || !flick || flick.contentY===undefined)return
        let ancestor=item
        while(ancestor && ancestor!==workColumn)ancestor=ancestor.parent
        if(ancestor!==workColumn)return
        const point=item.mapToItem(workColumn,0,0)
        if(point.y<flick.contentY+5)flick.contentY=Math.max(0,point.y-5)
        else if(point.y+item.height>flick.contentY+workspace.availableHeight-5)flick.contentY=Math.min(Math.max(0,flick.contentHeight-workspace.availableHeight),point.y+item.height-workspace.availableHeight+5)
    }
    function chooseMetric(id,modifiers){canvas.pick(id,modifiers);canvas.restoreMetricFocus(canvas.selectedMetric)}
    function metricStep(id,delta){const at=canvas.contents.indexOf(id);canvas.cancelDrag();if(stats.reorderMetric(root.selectedKey,at,at+delta))canvas.restoreMetricFocus(id)}
    onSelectedKeyChanged:{expandedCanvas=false;if(workspace.contentItem)workspace.contentItem.contentY=0}
    Connections {target:root.Window.window;function onActiveFocusItemChanged(){Qt.callLater(root.revealFocus)}}
    Item {
        width:root.centerWidth;height:parent.height
        RowLayout {
            x:root.contentInset;y:16;width:parent.width-root.contentInset*2;height:36;spacing:10
            Rectangle {width:8;height:8;radius:4;color:root.meta.color || ui.accent}
            Text {text:ui.t("名称");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:ui.captionSize}
            TextField {
                objectName:"widgetTitle";Layout.fillWidth:true;Layout.minimumWidth:80;Layout.maximumWidth:320;implicitHeight:34;maximumLength:12
                text:root.prefs.title || "";placeholderText:root.meta.label || "";placeholderTextColor:ui.ink
                font.family:ui.fontFamily;font.pixelSize:20;font.weight:Font.DemiBold;color:ui.ink;selectByMouse:true;leftPadding:0
                onTextEdited:stats.changeWidget(root.selectedKey,"title",text)
                background:Rectangle {color:"transparent";border.color:parent.activeFocus?ui.line:"transparent";radius:5}
            }
            Item {Layout.fillWidth:true}
            Text {text:ui.t("显示组件");font.family:ui.fontFamily;font.pixelSize:ui.captionSize;color:ui.ink}
            Toggle {objectName:"widgetVisibilityToggle";checked:root.prefs.enabled || false;Accessible.name:ui.t("显示");onToggled:stats.changeWidget(root.selectedKey,"enabled",checked)}
            ActionButton {id:widgetMoreButton;objectName:"widgetMoreButton";text:"···";quiet:true;implicitWidth:32;implicitHeight:30;leftPadding:0;rightPadding:0;Accessible.name:ui.t("更多");onClicked:widgetMenu.open()}
            EditorMenu {
                id:widgetMenu;objectName:"widgetOptionsMenu"
                x:widgetMoreButton.x+widgetMoreButton.width-width;y:widgetMoreButton.y+widgetMoreButton.height+4
                EditorMenuItem {objectName:"widgetDuplicateAction";glyph:"copy";text:ui.t("复制小组件");enabled:root.config.widget_order.length<24;onTriggered:{const key=stats.duplicateWidget(root.selectedKey);if(key)root.selectKey(key)}}
                EditorMenuItem {objectName:"widgetMoveUpAction";glyph:"up";text:ui.t("上移");enabled:root.config.widget_order.indexOf(root.selectedKey)>0;onTriggered:stats.moveWidget(root.selectedKey,-1)}
                EditorMenuItem {objectName:"widgetMoveDownAction";glyph:"down";text:ui.t("下移");enabled:root.config.widget_order.indexOf(root.selectedKey)<root.config.widget_order.length-1;onTriggered:stats.moveWidget(root.selectedKey,1)}
                EditorMenuSeparator {}
                EditorMenuItem {objectName:"widgetRemoveAction";glyph:"trash";danger:true;text:ui.t("移除小组件");onTriggered:stats.removeWidget(root.selectedKey)}
            }
        }
        RowLayout {
            x:root.contentInset;y:64;width:parent.width-root.contentInset*2;height:34;spacing:5
            Repeater {
                model:[{id:"card",label:"卡片"},{id:"horizontal",label:"横条"},{id:"vertical",label:"竖条"}]
                ActionButton {
                    required property var modelData
                    objectName:"layoutPreset_"+modelData.id;text:ui.t(modelData.label);quiet:root.currentPreset!==modelData.id
                    checkable:true;checked:root.currentPreset===modelData.id;font.weight:checked?Font.DemiBold:Font.Normal
                    implicitHeight:32;leftPadding:12;rightPadding:12
                    onClicked:{canvas.cancelDrag();stats.applyLayoutPreset(root.selectedKey,modelData.id);canvas.zoom=0;root.expandedCanvas=false;workspace.contentItem.contentY=0}
                }
            }
            Item {Layout.fillWidth:true}
            ActionButton {objectName:"expandCanvasButton";text:ui.t("精细排版");quiet:!root.expandedCanvas;Layout.maximumWidth:130;implicitWidth:100;implicitHeight:32;leftPadding:8;rightPadding:8;Accessible.name:ui.t("精细排版");checkable:true;checked:root.expandedCanvas;onClicked:{canvas.cancelDrag();root.expandedCanvas=!root.expandedCanvas;workspace.contentItem.contentY=0}
                Icon {objectName:"expandCanvasIcon";visible:false;width:16;height:16;ink:ui.muted;name:root.expandedCanvas?"collapse":"expand"}
                ToolTip.visible:hovered;ToolTip.text:ui.t(root.expandedCanvas?"收起画布":"展开画布")}
            ActionButton {objectName:"addReadingButton";implicitHeight:32;enabled:canvas.contents.length<6;text:"＋ "+ui.t("添加指标");onClicked:root.requestReadings(root.selectedKey)}
        }
        RowLayout {
            id:selectionTools
            x:root.contentInset;y:106;width:parent.width-root.contentInset*2;height:28;spacing:8
            visible:root.expandedCanvas && (canvas.manual || canvas.contents.length>1)
            Text {objectName:"selectedLayoutName";Layout.fillWidth:true;text:canvas.selectedIds.length>1?canvas.selectedIds.length+" "+ui.t("项已选"):canvas.manual?canvas.selectedMeta.label:ui.t("拖动指标改变顺序");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;elide:Text.ElideRight}
            Text {objectName:"selectedLayoutReading";visible:false;text:""
                color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.DemiBold}
            IconButton {id:layoutAlignmentButton;objectName:"layoutAlignmentButton";symbol:"sliders";label:ui.t("对齐与均分");enabled:canvas.manual && canvas.selectedIds.length>0;onClicked:alignMenu.open()}
            IconButton {objectName:"removeSelectedMetric";symbol:"close";label:ui.t("移除");enabled:canvas.contents.length>1 && !!canvas.selectedMetric;onClicked:canvas.removeMetricById(canvas.selectedMetric)}
            EditorMenu {
                id:alignMenu;objectName:"layoutAlignmentMenu"
                x:layoutAlignmentButton.x+layoutAlignmentButton.width-width;y:layoutAlignmentButton.y+layoutAlignmentButton.height+4
                EditorMenuItem {caption:true;enabled:false;text:ui.t(canvas.selectedIds.length>1?"对齐选中项":"对齐到组件")}
                Repeater {
                    model:[{id:"left",label:"左对齐"},{id:"center",label:"水平居中"},{id:"right",label:"右对齐"},{id:"top",label:"顶部对齐"},{id:"middle",label:"垂直居中"},{id:"bottom",label:"底部对齐"},{id:"distribute_x",label:"水平等间距"},{id:"distribute_y",label:"垂直等间距"}]
                    EditorMenuItem {
                        required property var modelData
                        objectName:"layoutOp_"+modelData.id
                        property var result:alignMenu.visible && canvas.manual && canvas.selectedIds.length?canvas.operation(modelData.id):({valid:false,reason:""})
                        text:ui.t(modelData.label);enabled:result.valid===true;onTriggered:canvas.applyOperation(modelData.id)
                        ToolTip.visible:hovered && !enabled;ToolTip.text:result.reason || ""
                    }
                }
            }
        }
        ScrollView {
            id:workspace;objectName:"widgetWorkspaceScroll";x:0;y:selectionTools.visible?140:106;width:parent.width;height:parent.height-y
            contentWidth:availableWidth;contentHeight:workColumn.height;clip:true;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            Item {
                id:workColumn;width:Math.min(workspace.availableWidth,860);x:(workspace.availableWidth-width)/2;height:desktopDefaults.y+desktopDefaults.height+24
                WidgetInspector {id:inspector;x:24;y:0;width:parent.width-48;height:implicitHeight;widgetKey:root.selectedKey;canvas:canvas;inlineMode:true;active:root.active && !root.resizing;section:root.section;onSelectSection:selected=>root.section=selected}
                Item {
                    id:stage;parent:inspector.previewHost;width:parent.width;height:Math.max(metricList.y+metricList.height,canvasTools.y+canvasTools.height,canvas.height+(previewCaption.visible?22:0))
                ContentLayoutEditor {
                    id:canvas;objectName:"contentLayoutEditor";x:0;y:0;width:root.compactWorkspace?Math.max(196,Math.min(248,parent.width*.36)):parent.width
                    height:widgetResizing?gestureViewportHeight:root.expandedCanvas?Math.max(104,workspace.availableHeight-inspector.commonHeight-62):root.naturalStageHeight
                    widgetKey:root.selectedKey
                    active:root.active
                    resizing:root.resizing
                    enabled:root.expandedCanvas
                    onExpandRequested:root.expandedCanvas=true
                    onWidgetResizingChanged:if(widgetResizing)root.gestureCompact=root.compactEligible
                }
                Text {id:previewCaption;visible:!root.expandedCanvas;x:0;y:canvas.height+2;width:canvas.width;text:ui.t("预览")+" · "+Math.round(canvas.viewScale*100)+"%";horizontalAlignment:Text.AlignHCenter;font.family:ui.fontFamily;font.pixelSize:ui.metaSize;color:ui.muted}
                RowLayout {
                    id:canvasTools;objectName:"canvasTools";x:0;y:canvas.height+8;width:parent.width;height:visible?30:0;spacing:8;visible:root.expandedCanvas
                    IconButton {objectName:"undoDraftButton";symbol:"undo";label:ui.t("撤销");enabled:stats.canUndoDraft;onClicked:{canvas.cancelDrag();stats.undoDraft()}}
                    IconButton {objectName:"redoDraftButton";symbol:"redo";label:ui.t("重做");enabled:stats.canRedoDraft;onClicked:{canvas.cancelDrag();stats.redoDraft()}}
                    Check {objectName:"manualLayoutToggle";text:ui.t("自由摆放");checked:canvas.manual;onToggled:{canvas.cancelDrag();stats.changeWidget(root.selectedKey,"layout_mode",checked?"manual":"auto")}}
                    Check {objectName:"canvasSnapToggle";text:ui.t("吸附");visible:canvas.manual;checked:canvas.snapEnabled;onToggled:canvas.snapEnabled=checked;ToolTip.visible:hovered;ToolTip.text:ui.t("按住 Alt 暂时关闭吸附")}
                    Item {Layout.fillWidth:true}
                    ActionButton {objectName:"actualCanvasSizeButton";text:Math.round(canvas.designWidth)+" × "+Math.round(canvas.designHeight);quiet:true;implicitHeight:28;font.pixelSize:10;leftPadding:4;rightPadding:4;onClicked:canvas.setZoom(1);ToolTip.visible:hovered;ToolTip.text:ui.t("实际大小")}
                    ActionButton {objectName:"fitCanvasButton";text:ui.t("适合");quiet:true;implicitHeight:28;leftPadding:7;rightPadding:7;onClicked:canvas.fitView()}
                    Choice {objectName:"canvasZoomChoice";implicitHeight:28;Layout.preferredWidth:76;model:[{id:.5,label:"50%"},{id:1,label:"100%"},{id:1.5,label:"150%"},{id:2,label:"200%"},{id:3,label:"300%"}];value:canvas.viewScale;displayText:Math.round(canvas.viewScale*100)+"%";onPicked:selected=>canvas.setZoom(selected)}
                }
                Column {
                    id:metricList;objectName:"widgetMetricList";x:root.compactWorkspace?canvas.width+12:0;y:root.compactWorkspace?4:canvasTools.y+canvasTools.height+14;width:parent.width-x;height:59+canvas.contents.length*37;spacing:1
                    Text {height:26;text:ui.t("已添加的指标");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;verticalAlignment:Text.AlignVCenter}
                    Repeater {
                        model:canvas.contents
                        Item {
                            id:metricRow;required property string modelData;required property int index
                            objectName:"metricListRow_"+modelData;width:metricList.width;height:36
                            readonly property var info:{const draft=root.config;return stats.metricInfoFor(root.selectedKey,modelData)}
                            Rectangle {anchors.fill:parent;radius:6;color:canvas.selectedIds.includes(metricRow.modelData)?ui.selection:metricMouse.containsMouse?ui.hover:"transparent"}
                            MouseArea {id:metricMouse;objectName:"metricListSelect_"+metricRow.modelData;anchors.fill:parent;hoverEnabled:true;onClicked:mouse=>root.chooseMetric(metricRow.modelData,mouse.modifiers)}
                            RowLayout {
                                anchors.fill:parent;anchors.leftMargin:9;anchors.rightMargin:3;spacing:root.compactWorkspace?6:9
                                Text {text:metricRow.index+1;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;Layout.preferredWidth:14}
                                Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:metricRow.info.label || metricRow.modelData;textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:ui.captionSize;elide:Text.ElideRight;ToolTip.visible:metricMouse.containsMouse && truncated;ToolTip.text:text}
                                Text {objectName:"metricListValue_"+metricRow.modelData;text:{const data=canvas.previewReadings;return stats.readingFor(root.selectedKey,metricRow.modelData)}
                                    color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;font.weight:Font.DemiBold;Layout.preferredWidth:root.compactWorkspace?72:100;horizontalAlignment:Text.AlignRight;elide:Text.ElideRight}
                                IconButton {objectName:"metricListUp_"+metricRow.modelData;symbol:"up";label:ui.t("上移");implicitWidth:26;implicitHeight:26;enabled:metricRow.index>0;onClicked:root.metricStep(metricRow.modelData,-1)}
                                IconButton {objectName:"metricListDown_"+metricRow.modelData;symbol:"down";label:ui.t("下移");implicitWidth:26;implicitHeight:26;enabled:metricRow.index<canvas.contents.length-1;onClicked:root.metricStep(metricRow.modelData,1)}
                                IconButton {objectName:"metricListRemove_"+metricRow.modelData;symbol:"close";label:ui.t("移除");implicitWidth:26;implicitHeight:26;enabled:canvas.contents.length>1;onClicked:canvas.removeMetricById(metricRow.modelData)}
                            }
                        }
                    }
                    RowLayout {
                        width:metricList.width; height:32; spacing:8
                        Text {Layout.fillWidth:true;text:(inspector.health.available || 0)+" / "+(inspector.health.total || 0)+" "+ui.t("项可用");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10}
                        ActionButton {objectName:"metricSourcesButton";text:ui.t("数据");quiet:true;implicitHeight:28;leftPadding:8;rightPadding:8;onClicked:root.showInspector("devices")}
                    }
                }
                }
                Column {id:desktopDefaults;objectName:"desktopDefaultsSection";x:24;y:inspector.height+24;width:parent.width-48;spacing:12
                    ActionButton {objectName:"desktopDefaultsToggle";width:parent.width;text:(root.defaultsOpen?"− ":"＋ ")+ui.t("桌面默认设置");quiet:true;onClicked:root.defaultsOpen=!root.defaultsOpen}
                    Appearance {visible:root.defaultsOpen;width:parent.width;height:root.defaultsOpen?implicitHeight:0}
                }
            }
        }
    }
}
