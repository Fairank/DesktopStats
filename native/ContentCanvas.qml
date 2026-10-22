import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id:root
    readonly property var config:stats.draft
    required property string widgetKey
    property bool active:visible
    property bool resizing:false
    property var previewReadings:({})
    property var previewHistory:[]
    function refreshPreview(){if(active && !resizing){previewReadings=stats.readings;previewHistory=stats.history}}
    onActiveChanged:refreshPreview()
    onResizingChanged:refreshPreview()
    Component.onCompleted:refreshPreview()
    Connections {target:stats;enabled:root.active && !root.resizing;function onDataChanged(){root.refreshPreview()}}
    readonly property var prefs:root.config.widgets[widgetKey] || ({})
    readonly property var contents:{const draft=root.config;return stats.widgetContentIds(widgetKey)}
    readonly property var dimensions:{const draft=root.config;return stats.widgetDimensions(widgetKey)}
    readonly property bool coatingAllowed:stats.coatingAllowed
    property point temporarySize:Qt.point(0,0)
    property real gestureViewportHeight:0
    readonly property real requestedWidth:temporarySize.x || dimensions.width || 168
    readonly property real requestedHeight:temporarySize.y || dimensions.height || 168
    readonly property var geometry:{const draft=root.config;const size=temporarySize;return stats.widgetContentLayout(widgetKey,size.x || dimensions.width || 168,size.y || dimensions.height || 168)}
    readonly property real designWidth:geometry.width || requestedWidth
    readonly property real designHeight:geometry.height || requestedHeight
    readonly property var body:geometry.body || ({x:0,y:0,width:1,height:1})
    readonly property var readings:geometry.readings || []
    readonly property bool manual:prefs.layout_mode==="manual"
    property string selectedMetric:contents[0] || ""
    property var selectedIds:selectedMetric?[selectedMetric]:[]
    property bool snapEnabled:true
    property real zoom:0
    readonly property real fitScale:Math.max(.01,Math.min(3,(viewport.width-64)/Math.max(1,designWidth),(viewport.height-64)/Math.max(1,designHeight)))
    property real frozenScale:0
    readonly property real viewScale:frozenScale>0?frozenScale:zoom>0?zoom:Math.min(1,fitScale)
    property var ghost:null
    property var ghostPositions:null
    property var assist:({valid:true,guides:[]})
    property string swapTarget:""
    property var dragOrigin:null
    property point pointerOrigin:Qt.point(0,0)
    property bool moved:false
    property bool resizeDrag:false
    property int dropIndex:-1
    property bool widgetResizing:false
    property real resizePlaneX:0
    property real resizePlaneY:0
    property string notice:""
    readonly property var selectedMeta:{const draft=root.config;return selectedMetric?stats.metricInfoFor(widgetKey,selectedMetric):({})}
    readonly property var selectedRect:rectFor(selectedMetric)
    readonly property var viewConfig:{
        const cfg=Object.assign({},root.config)
        if(!ghostPositions && !widgetResizing)return cfg
        cfg.widgets=Object.assign({},cfg.widgets)
        const own=Object.assign({},prefs)
        if(ghostPositions)own.metric_positions=ghostPositions
        if(widgetResizing){const plan=geometry;own.width=Math.round(plan.width || requestedWidth);own.height=Math.round(plan.height || requestedHeight);if(own.form!=="bar")own.form="free"}
        cfg.widgets[widgetKey]=own
        return cfg
    }
    signal selectionEdited()
    signal expandRequested()
    Theme {id:ui}
    function rectFor(id){const row=readings.find(r=>r.id===id);return row && body.width>0 && body.height>0?{x:(row.x-body.x)/body.width,y:(row.y-body.y)/body.height,width:row.width/body.width,height:row.height/body.height}:null}
    function positions(){const map={}
for(const id of contents){const box=rectFor(id);if(box)map[id]=box}return map}
    function pick(id,modifiers){
        if(modifiers&Qt.ControlModifier){const next=selectedIds.slice(),at=next.indexOf(id);if(at>=0)next.splice(at,1);else next.push(id);selectedIds=next;selectedMetric=next[next.length-1] || ""}
        else {selectedMetric=id;selectedIds=[id]}
        selectionEdited()
    }
    function cancelDrag(){const active=!!ghost || widgetResizing;ghost=null;ghostPositions=null;dragOrigin=null;assist=({valid:true,guides:[]});swapTarget="";dropIndex=-1;moved=false;temporarySize=Qt.point(0,0);widgetResizing=false;frozenScale=0;return active}
    function centerView(){viewport.contentX=Math.max(0,(viewport.contentWidth-viewport.width)/2);viewport.contentY=Math.max(0,(viewport.contentHeight-viewport.height)/2)}
    function fitView(){expandRequested();Qt.callLater(()=>{zoom=fitScale;centerView()})}
    function setZoom(value){zoom=Math.max(.05,Math.min(4,value));Qt.callLater(()=>ensureVisible(selectedMetric))}
    function ensureVisible(id){
        const box=rectFor(id);if(!box)return
        const x=plane.x+(body.x+box.x*body.width)*viewScale,y=plane.y+(body.y+box.y*body.height)*viewScale,w=box.width*body.width*viewScale,h=box.height*body.height*viewScale
        if(x<viewport.contentX+24)viewport.contentX=Math.max(0,x-24);else if(x+w>viewport.contentX+viewport.width-24)viewport.contentX=Math.min(viewport.contentWidth-viewport.width,x+w-viewport.width+24)
        if(y<viewport.contentY+24)viewport.contentY=Math.max(0,y-24);else if(y+h>viewport.contentY+viewport.height-24)viewport.contentY=Math.min(viewport.contentHeight-viewport.height,y+h-viewport.height+24)
    }
    function startMetric(id,point,resize,modifiers){pick(id,modifiers);if(!selectedIds.includes(id))return;dragOrigin=rectFor(id);if(!dragOrigin)return;frozenScale=viewScale;pointerOrigin=point;ghost=Object.assign({id:id},dragOrigin);resizeDrag=resize;moved=false;dropIndex=contents.indexOf(id);notice=""}
    function moveMetric(point,modifiers){
        if(!ghost || !dragOrigin)return
        const dx=(point.x-pointerOrigin.x)/Math.max(1,body.width*viewScale),dy=(point.y-pointerOrigin.y)/Math.max(1,body.height*viewScale)
        if(Math.hypot(point.x-pointerOrigin.x,point.y-pointerOrigin.y)>4)moved=true
        const proposed=Object.assign({},dragOrigin)
        if(resizeDrag){proposed.width+=dx;proposed.height+=dy}else{proposed.x+=dx;proposed.y+=dy}
        const logical=plane.mapFromItem(viewport.contentItem,point.x,point.y)
        if(!manual){
            ghost=Object.assign({id:ghost.id},proposed);let distance=Infinity,target=-1
            if(logical.x>=0 && logical.y>=0 && logical.x<=plane.width && logical.y<=plane.height)for(const row of readings){const d=Math.pow((row.x+row.width/2)*viewScale-logical.x,2)+Math.pow((row.y+row.height/2)*viewScale-logical.y,2);if(d<distance){distance=d;target=row.index}}
            dropIndex=target;return
        }
        assist=stats.previewMetricPlacement(widgetKey,ghost.id,proposed,resizeDrag?"resize":"move",snapEnabled,!!(modifiers&Qt.AltModifier))
        ghost=Object.assign({id:ghost.id},assist.rect || proposed);swapTarget="";ghostPositions=null
        if(!resizeDrag && moved)for(const row of readings){if(row.id!==ghost.id && logical.x>(row.x+row.width*.2)*viewScale && logical.x<(row.x+row.width*.8)*viewScale && logical.y>(row.y+row.height*.2)*viewScale && logical.y<(row.y+row.height*.8)*viewScale){swapTarget=row.id;break}}
        if(swapTarget){const result=stats.previewLayoutOperation(widgetKey,"swap",[ghost.id,swapTarget]);if(result.valid)ghostPositions=result.positions;else swapTarget=""}
        if(!swapTarget && assist.valid){const all=positions();all[ghost.id]={x:ghost.x,y:ghost.y,width:ghost.width,height:ghost.height}
ghostPositions=all}
    }
    function endMetric(){
        if(!ghost)return
        const id=ghost.id,from=contents.indexOf(id),to=dropIndex,map=ghostPositions,changed=moved,valid=assist.valid,swapping=!!swapTarget
        cancelDrag();if(!changed)return
        let ok=true
        if(manual)ok=(swapping || valid) && map?stats.commitMetricPositions(widgetKey,map):false
        else if(to>=0 && from!==to)ok=stats.reorderMetric(widgetKey,from,to)
        if(!ok)notice=ui.t("无法放在这里，请避开重叠或使用自动排版。")
        Qt.callLater(()=>{const item=tileFor(id);if(item)item.forceActiveFocus()})
    }
    function tileFor(id){for(let i=0;i<tiles.count;i++){const item=tiles.itemAt(i);if(item && item.modelData.id===id)return item}return null}
    function restoreMetricFocus(id){Qt.callLater(()=>{const item=tileFor(id);if(item){item.forceActiveFocus();ensureVisible(id)}})}
    function removeMetricById(id){if(contents.length<=1)return;const at=contents.indexOf(id);if(at<0)return;const next=contents[at+1] || contents[at-1];cancelDrag();stats.removeMetric(widgetKey,at);selectedMetric=next;if(!selectedIds.includes(next))selectedIds=[next];restoreMetricFocus(next)}
    function operation(command){const draft=root.config;return stats.previewLayoutOperation(widgetKey,command,selectedIds)}
    function applyOperation(command){const result=operation(command);if(result.valid && stats.commitMetricPositions(widgetKey,result.positions))notice="";else notice=result.reason || ui.t("当前选择无法这样排列。")}
    function keyboard(event,id){
        if(event.key===Qt.Key_Escape){cancelDrag();event.accepted=true;return}
        if(event.key===Qt.Key_Delete && contents.length>1){removeMetricById(id);event.accepted=true;return}
        if(![Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down].includes(event.key))return
        if(!manual){if(event.modifiers&Qt.AltModifier){const at=contents.indexOf(id),delta=[Qt.Key_Left,Qt.Key_Up].includes(event.key)?-1:1;if(at+delta>=0 && at+delta<contents.length && stats.reorderMetric(widgetKey,at,at+delta))restoreMetricFocus(id);event.accepted=true}return}
        const rect=rectFor(id),horizontal=[Qt.Key_Left,Qt.Key_Right].includes(event.key),amount=([Qt.Key_Left,Qt.Key_Up].includes(event.key)?-1:1)*(event.modifiers&Qt.ShiftModifier?1:4)/(horizontal?body.width:body.height)
        const field=event.modifiers&Qt.ControlModifier?(horizontal?"width":"height"):(horizontal?"x":"y");rect[field]+=amount
        const result=stats.previewMetricPlacement(widgetKey,id,rect,event.modifiers&Qt.ControlModifier?"resize":"move",false,true)
        if(result.valid){const all=positions();all[id]=result.rect;if(stats.commitMetricPositions(widgetKey,all))restoreMetricFocus(id)}event.accepted=true
    }
    onWidgetKeyChanged:{cancelDrag();selectedMetric=(contents || [])[0] || "";selectedIds=selectedMetric?[selectedMetric]:[];zoom=0;notice="";Qt.callLater(centerView)}
    onContentsChanged:{selectedIds=selectedIds.filter(id=>contents.includes(id));if(!contents.includes(selectedMetric)){selectedMetric=contents[0] || "";selectedIds=selectedMetric?[selectedMetric]:[]}}
    onManualChanged:cancelDrag()
    ScrollView {
        objectName:"workbenchCanvasScroll";anchors.fill:parent;clip:true
        ScrollBar.horizontal.policy:ScrollBar.AsNeeded;ScrollBar.vertical.policy:ScrollBar.AsNeeded
        contentItem:Flickable {
            id:viewport;objectName:"workbenchCanvasViewport";clip:true;contentWidth:Math.max(width,root.designWidth*root.viewScale+64);contentHeight:Math.max(height,root.designHeight*root.viewScale+64)
            interactive:!root.ghost && !root.widgetResizing;boundsBehavior:Flickable.StopAtBounds
            MouseArea {anchors.fill:parent;acceptedButtons:Qt.LeftButton;onClicked:{root.selectedIds=[];root.selectedMetric="";root.selectionEdited()}}
            WheelHandler {target:null;acceptedModifiers:Qt.KeyboardModifierMask;onWheel:event=>{if(event.modifiers&Qt.ControlModifier){root.setZoom(root.viewScale*(event.angleDelta.y>0?1.15:1/1.15));event.accepted=true}else if(viewport.contentWidth>viewport.width+1 && viewport.contentHeight<=viewport.height+1){viewport.contentX=Math.max(0,Math.min(viewport.contentWidth-viewport.width,viewport.contentX-event.angleDelta.y));event.accepted=true}else event.accepted=false}}
            Item {
                id:plane;objectName:"workbenchArtboard";x:root.widgetResizing?root.resizePlaneX:(viewport.contentWidth-width)/2;y:root.widgetResizing?root.resizePlaneY:(viewport.contentHeight-height)/2;width:root.designWidth*root.viewScale;height:root.designHeight*root.viewScale
                WidgetPreview {objectName:"workbenchActualPreview";anchors.fill:parent;moduleKey:root.widgetKey;config:root.viewConfig;previewInfo:({width:root.geometry.width || root.requestedWidth,height:root.geometry.height || root.requestedHeight,card_surfaces:true,coating_translucent:root.coatingAllowed});readings:root.previewReadings;history:root.previewHistory;renderScale:root.viewScale}
                Repeater {
                    id:tiles;model:root.readings
                    FocusScope {
                        id:tile;required property var modelData;objectName:"layoutMetric_"+modelData.id
                        readonly property bool selected:root.selectedIds.includes(modelData.id)
                        x:modelData.x*root.viewScale;y:modelData.y*root.viewScale;width:modelData.width*root.viewScale;height:modelData.height*root.viewScale;activeFocusOnTab:true
                        onActiveFocusChanged:if(activeFocus){root.selectedMetric=modelData.id;if(!root.selectedIds.includes(modelData.id))root.selectedIds=[modelData.id]}
                        Keys.onPressed:event=>root.keyboard(event,modelData.id)
                        Rectangle {anchors.fill:parent;color:tile.selected && root.enabled?"#09007aff":"transparent";border.color:tile.selected && root.enabled?ui.accent:"transparent";border.width:1.4;radius:5}
                        MouseArea {
                            id:drag;objectName:"layoutDrag_"+tile.modelData.id;anchors.fill:parent;acceptedButtons:Qt.LeftButton;preventStealing:true;hoverEnabled:true;cursorShape:pressed?Qt.ClosedHandCursor:Qt.OpenHandCursor
                            onPressed:function(mouse){root.startMetric(tile.modelData.id,mapToItem(viewport.contentItem,mouse.x,mouse.y),false,mouse.modifiers);if(root.selectedIds.includes(tile.modelData.id))tile.forceActiveFocus();else {const selected=root.tileFor(root.selectedMetric);if(selected)selected.forceActiveFocus()}}
                            onPositionChanged:function(mouse){if(pressed)root.moveMetric(mapToItem(viewport.contentItem,mouse.x,mouse.y),mouse.modifiers)}
                            onReleased:root.endMetric();onCanceled:root.cancelDrag()
                            ToolTip.visible:containsMouse && !pressed;ToolTip.delay:700;ToolTip.text:{const draft=root.config;const meta=stats.metricInfoFor(root.widgetKey,tile.modelData.id);return [meta.label,meta.hardware_name].filter(Boolean).join("\n")}
                        }
                        MouseArea {
                            objectName:"layoutResize_"+tile.modelData.id;visible:root.enabled && root.manual && tile.selected;width:18;height:18;anchors.right:parent.right;anchors.bottom:parent.bottom;preventStealing:true;cursorShape:Qt.SizeFDiagCursor
                            onPressed:function(mouse){root.startMetric(tile.modelData.id,mapToItem(viewport.contentItem,mouse.x,mouse.y),true,mouse.modifiers)}
                            onPositionChanged:function(mouse){if(pressed)root.moveMetric(mapToItem(viewport.contentItem,mouse.x,mouse.y),mouse.modifiers)}
                            onReleased:root.endMetric();onCanceled:root.cancelDrag()
                            Rectangle {width:7;height:7;anchors.right:parent.right;anchors.bottom:parent.bottom;radius:2;color:ui.accent}
                        }
                        Accessible.name:{const draft=root.config;return stats.metricInfoFor(root.widgetKey,modelData.id).label || modelData.id}
                    }
                }
                Repeater {model:root.ghost && root.moved && !root.swapTarget?(root.assist.guides || []):[];Rectangle {required property var modelData;x:modelData.axis==="x"?(root.body.x+modelData.position)*root.viewScale:root.body.x*root.viewScale;y:modelData.axis==="y"?(root.body.y+modelData.position)*root.viewScale:root.body.y*root.viewScale;width:modelData.axis==="x"?1:root.body.width*root.viewScale;height:modelData.axis==="y"?1:root.body.height*root.viewScale;color:"#e45ca6ff";z:6}}
                Repeater {model:root.ghost && root.moved?(root.swapTarget?[root.ghost.id,root.swapTarget]:[root.ghost.id]):[];Rectangle {required property string modelData;property var box:root.ghostPositions?root.ghostPositions[modelData]:root.ghost;x:(root.body.x+box.x*root.body.width)*root.viewScale;y:(root.body.y+box.y*root.body.height)*root.viewScale;width:box.width*root.body.width*root.viewScale;height:box.height*root.body.height*root.viewScale;radius:5;color:root.swapTarget || root.assist.valid?"#10007aff":"#24df594d";border.color:root.swapTarget || root.assist.valid?ui.accent:"#d65b4d";border.width:2;z:7}}
                Rectangle {property var target:root.readings.find(row=>row.index===root.dropIndex);visible:!root.manual && !!root.ghost && root.moved && !!target;x:target?target.x*root.viewScale:0;y:target?target.y*root.viewScale:0;width:target?target.width*root.viewScale:0;height:target?target.height*root.viewScale:0;color:"#10007aff";border.color:ui.accent;border.width:2;radius:5;z:8}
                MouseArea {
                    objectName:"widgetCanvasResizeHandle";visible:root.enabled;x:parent.width-8;y:parent.height-8;width:22;height:22;z:10;preventStealing:true;cursorShape:Qt.SizeFDiagCursor
                    property point origin:Qt.point(0,0);property real initialWidth:0;property real initialHeight:0
                    onPressed:function(mouse){root.frozenScale=root.viewScale;root.gestureViewportHeight=root.height;origin=mapToItem(root,mouse.x,mouse.y);initialWidth=root.designWidth;initialHeight=root.designHeight;root.resizePlaneX=plane.x;root.resizePlaneY=plane.y;root.widgetResizing=true;root.notice=""}
                    onPositionChanged:function(mouse){if(!pressed || !root.widgetResizing)return;const point=mapToItem(root,mouse.x,mouse.y);if(Math.hypot(point.x-origin.x,point.y-origin.y)<3)return;root.temporarySize=Qt.point(Math.max(root.dimensions.min_width || 80,Math.min(4096,initialWidth+(point.x-origin.x)/root.viewScale)),Math.max(root.dimensions.min_height || 32,Math.min(2160,initialHeight+(point.y-origin.y)/root.viewScale)))}
                    onReleased:{if(!root.widgetResizing)return;const w=root.designWidth,h=root.designHeight,changed=Math.round(w)!==Math.round(initialWidth) || Math.round(h)!==Math.round(initialHeight);root.cancelDrag();if(changed && !stats.setWidgetDimensions(root.widgetKey,w,h))root.notice=ui.t("尺寸未更改，请检查输入范围与布局。")}
                    onCanceled:root.cancelDrag()
                    Rectangle {width:10;height:10;radius:3;color:ui.accent;border.color:"white";border.width:1;anchors.centerIn:parent}
                    Accessible.name:ui.t("缩放小组件")
                }
            }
        }
    }
    Rectangle {visible:root.ghost && root.moved && !!root.swapTarget;anchors.horizontalCenter:parent.horizontalCenter;anchors.top:parent.top;anchors.topMargin:12;width:swapText.implicitWidth+24;height:30;radius:15;color:ui.segmentSelected;border.color:ui.line;Text {id:swapText;anchors.centerIn:parent;text:ui.t("交换位置");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11}}
    Text {objectName:"contentLayoutNotice";visible:!!root.notice;anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:12;text:root.notice;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
}
