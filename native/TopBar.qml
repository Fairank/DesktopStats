import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import DesktopStats 1.0

Window {
    id: root
    objectName: "topBarWindow"
    required property var barState
    readonly property color foreground: barState.ink
    readonly property color secondary: barState.muted
    readonly property string barDesign:["classic","capsule","instrument"].includes(barState.config.bar_design)?barState.config.bar_design:"classic"
    readonly property color barAccent:foreground.r>.5?"#67a8ff":"#006fe6"
    property bool dragHeld: false
    property bool dragging: false
    property string draggedId: ""
    property string dropBeforeId: ""
    property string dropPlacement: ""
    property real insertionX: 0
    property var dragSlots: []
    property var draggedRow: ({})
    property real dragGrabOffset: 0
    property real dragPointerX: 0
    property real operationAnchorX: 0

    visible: false
    color: "transparent"
    width: 1
    height: 1
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
    title: "Desktop Stats"

    function tint(alpha) {
        return Qt.rgba(foreground.r, foreground.g, foreground.b, alpha)
    }
    function beginDrag(identifier, point) {
        cancelDrag()
        dragHeld=true;draggedId=identifier
        const slots=[]
        for(let index=0;index<metrics.count;index++){
            const item=metrics.itemAt(index)
            slots.push({id:item.modelData.id,x:item.x,width:item.width,placement:item.modelData.placement || "right"})
        }
        dragSlots=slots
        const source=slots.find(slot=>slot.id===identifier)
        const itemIndex=slots.findIndex(slot=>slot.id===identifier)
        draggedRow=itemIndex>=0?metrics.itemAt(itemIndex).modelData:({})
        dragPointerX=point?point.x:source?source.x:0
        dragGrabOffset=source?dragPointerX-source.x:0
        barState.leaveBar()
    }
    function cancelDrag() {dragHeld=false;dragging=false;draggedId="";dropBeforeId="";dropPlacement="";dragSlots=[];draggedRow=({})}
    function updateDrop(point) {
        dragPointerX=point.x
        dropPlacement="";dropBeforeId=""
        if(point.x<0 || point.x>width || point.y<0 || point.y>height)return
        const hovered=dragSlots.find(slot=>point.x>=slot.x && point.x<=slot.x+slot.width)
        dropPlacement=hovered?hovered.placement:point.x<width/2?"left":"right"
        const peers=dragSlots.filter(slot=>slot.placement===dropPlacement && slot.id!==draggedId).sort((a,b)=>a.x-b.x)
        const before=peers.find(slot=>point.x<slot.x+slot.width/2)
        dropBeforeId=before?before.id:""
        insertionX=before?before.x-barState.spacing/2:peers.length?peers[peers.length-1].x+peers[peers.length-1].width+barState.spacing/2:dropPlacement==="left"?menuButton.x+menuButton.width+barState.spacing:width-8
    }
    function finishDrag() {
        const identifier=draggedId,before=dropBeforeId,placement=dropPlacement
        const valid=dragging && !!placement && identifier!==before
        const slot=dragSlots.find(value=>value.id===identifier)
        operationAnchorX=slot?slot.x:8
        cancelDrag()
        if(valid)barState.moveMetric(identifier,before,placement)
    }
    onVisibleChanged:if(!visible)cancelDrag()
    onWidthChanged:if(dragHeld)cancelDrag()
    onHeightChanged:if(dragHeld)cancelDrag()
    Shortcut {sequence:"Escape";enabled:root.dragHeld;onActivated:root.cancelDrag()}

    component PlainTip: ToolTip {
        id: tip
        delay: 650
        padding: 9
        popupType: Popup.Window
        contentItem: Text {
            text: tip.text
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.barState.fontFamily
            font.pixelSize: 11
            wrapMode: Text.Wrap
            width: Math.min(280, implicitWidth)
        }
        background: MaterialSurface {
            config: root.barState.config
            frosted: false
            cornerRadius: 8
        }
    }

    MaterialSurface {
        anchors.fill: parent
        config: root.barState.config
        frosted: root.barState.coatingTranslucent
        cornerRadius: 0
    }
    TopBarChrome {objectName:"topBarBandChrome";anchors.fill:parent;design:root.barDesign;role:"band";ink:root.foreground;accent:root.barAccent}

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: root.barState.menu()
    }
    HoverHandler {
        onHoveredChanged: if (!hovered) root.barState.leaveBar()
    }

    ToolButton {
        id: menuButton
        objectName: "topBarMenu"
        x: root.barState.menuRect.x || 0
        y: root.barState.menuRect.y || 0
        width: root.barState.menuRect.width || 0
        height: root.barState.menuRect.height || 0
        padding: 0
        focusPolicy: Qt.NoFocus
        icon.source: Qt.resolvedUrl("../assets/icon-20.svg")
        icon.color: "transparent"
        icon.width: 20
        icon.height: 20
        display: AbstractButton.IconOnly
        Accessible.name: root.barState.tr("顶部栏")
        background: TopBarChrome {
            objectName:"topBarMenuChrome"
            anchors.fill: parent
            design:root.barDesign;role:"menu";ink:root.foreground;accent:root.barAccent
            motionEnabled:root.barState.motionEnabled
            hovered:menuButton.hovered;pressed:menuButton.down
        }
        onClicked: root.barState.menu()
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton
            onClicked: root.barState.menu()
        }
    }

    Repeater {
        id:metrics
        model: root.barState.rows
        delegate: Item {
            id: metric
            required property var modelData
            required property int index
            readonly property var frozenSlot:root.dragHeld?root.dragSlots.find(slot=>slot.id===modelData.id):null
            objectName: "topBarMetric_" + modelData.id
            Accessible.role:Accessible.Button
            Accessible.name:((modelData.grouped?modelData.group_label:modelData.label) || "")+" "+((modelData.grouped?modelData.group_value:modelData.value) || "—")
            Accessible.onPressAction:root.barState.clickMetric(modelData.id)
            x: frozenSlot?frozenSlot.x:modelData.x
            y: modelData.y
            width: frozenSlot?frozenSlot.width:modelData.width
            height: modelData.height

            TopBarChrome {
                objectName:"topBarMetricChrome_"+metric.modelData.id
                anchors.fill: parent
                opacity:root.dragging && root.draggedId===metric.modelData.id?.35:1
                design:root.barDesign;ink:root.foreground;accent:root.barAccent
                motionEnabled:root.barState.motionEnabled
                hovered:metricMouse.containsMouse;pressed:metricMouse.pressed
                selected:root.barState.detail.id===metric.modelData.id
                pinned:root.barState.pinned && root.barState.detail.id===metric.modelData.id
                dragged:root.dragging && root.draggedId===metric.modelData.id
            }
            TopBarGroupContent {
                design:root.barDesign
                motionEnabled:root.barState.motionEnabled
                id: metricContent
                opacity:root.dragging && root.draggedId===metric.modelData.id?0:1
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 6
                width: implicitWidth
                height: implicitHeight
                row: metric.modelData
                ink: root.foreground
                muted: root.secondary
                fontFamily: root.barState.fontFamily
            }
            MouseArea {
                id: metricMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                cursorShape: root.dragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                property point pressPoint:Qt.point(0,0)
                onEntered: if(!root.dragHeld)root.barState.hoverMetric(metric.modelData.id)
                onExited: if(!root.dragging)root.barState.leaveBar()
                property bool canceledByRight: false
                onPressed:function(mouse){
                    if(mouse.button===Qt.RightButton && root.dragHeld){root.cancelDrag();canceledByRight=true;return}
                    if(mouse.button===Qt.LeftButton){canceledByRight=false;pressPoint=mapToItem(root.contentItem,mouse.x,mouse.y);root.beginDrag(metric.modelData.id,pressPoint)}
                }
                onPositionChanged:function(mouse){
                    if(!pressed || !root.dragHeld)return
                    const point=mapToItem(root.contentItem,mouse.x,mouse.y)
                    if(!root.dragging && Math.hypot(point.x-pressPoint.x,point.y-pressPoint.y)>=6)root.dragging=true
                    if(root.dragging)root.updateDrop(point)
                }
                onReleased:function(mouse){if(mouse.button===Qt.LeftButton){if(!root.dragHeld)return;if(root.dragging)root.finishDrag();else{root.cancelDrag();root.barState.clickMetric(metric.modelData.id)}}else{root.cancelDrag();if(!canceledByRight)root.barState.menu();canceledByRight=false}}
                onCanceled:root.cancelDrag()
            }
            PlainTip {
                visible: metricMouse.containsMouse && metricContent.labelTruncated && !root.dragHeld && !root.barState.detail.id && !root.barState.operationMessage
                text: ((metric.modelData.grouped?metric.modelData.group_label:metric.modelData.label) || "") + "  " + ((metric.modelData.grouped?metric.modelData.group_value:metric.modelData.value) || "—")
            }
        }
    }
    PlainTip {
        objectName: "topBarOperationFeedback"
        parent: root.contentItem
        visible: !!root.barState.operationMessage && root.visible
        delay: 0
        text: root.barState.operationMessage
        x: Math.max(4, Math.min(root.width - width - 4, root.operationAnchorX))
        y: root.height + 4
    }

    Item {
        id: overflow
        objectName: "topBarOverflow"
        Accessible.role:Accessible.Button
        Accessible.name:root.barState.tr("更多指标")+" "+root.barState.overflowCount
        Accessible.onPressAction:root.barState.clickMetric("__overflow__")
        readonly property var rect: root.barState.overflowRect || ({})
        visible: root.barState.overflowCount > 0 && !!root.barState.overflowRect
        x: rect.x || 0
        y: rect.y || 0
        width: rect.width || 0
        height: rect.height || 0
        TopBarChrome {
            objectName:"topBarOverflowChrome"
            anchors.fill: parent
            design:root.barDesign;role:"overflow";ink:root.foreground;accent:root.barAccent
            motionEnabled:root.barState.motionEnabled
            hovered:overflowMouse.containsMouse;pressed:overflowMouse.pressed
            selected:root.barState.detail.id==="__overflow__"
            pinned:root.barState.pinned && root.barState.detail.id==="__overflow__"
        }
        Text {
            anchors.centerIn: parent
            text: "＋" + root.barState.overflowCount
            textFormat: Text.PlainText
            color: root.foreground
            font.family: root.barState.fontFamily
            font.pixelSize: 12
            font.weight: Font.Medium
        }
        MouseArea {
            id: overflowMouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            cursorShape: Qt.PointingHandCursor
            onEntered: if(!root.dragHeld)root.barState.hoverMetric("__overflow__")
            onExited: root.barState.leaveBar()
            onClicked: function(mouse) {
                if (mouse.button === Qt.RightButton) root.barState.menu()
                else root.barState.clickMetric("__overflow__")
            }
        }
    }
    Rectangle {
        objectName:"topBarLiveInsertion"
        visible:root.dragging && !!root.dropPlacement
        x:Math.max(1,Math.min(root.width-2,root.insertionX));y:4
        width:2;height:Math.max(0,root.height-8);radius:1;color:root.barAccent
    }
    // An exact-width travelling copy makes the insertion target understandable.
    // Frozen source slots and immediate pointer tracking avoid a moving hit area.
    Item {
        id:dragPreview
        objectName:"topBarDragPreview"
        readonly property var slot:root.dragSlots.find(value=>value.id===root.draggedId)
        visible:root.dragging && !!slot
        x:Math.max(0,Math.min(root.width-width,root.dragPointerX-root.dragGrabOffset))
        y:Number.isFinite(root.draggedRow.y)?root.draggedRow.y:0
        width:slot?slot.width:0
        height:Number.isFinite(root.draggedRow.height)?root.draggedRow.height:0
        Rectangle {
            anchors.fill:parent;anchors.margins:1
            radius:root.barDesign==="capsule"?Math.min(13,height/2):6
            color:root.foreground.r>.5?"#303a48":"#f7faff"
            border.color:root.barAccent;border.width:1
        }
        TopBarGroupContent {
            anchors.left:parent.left;anchors.leftMargin:6;anchors.verticalCenter:parent.verticalCenter
            width:implicitWidth;height:implicitHeight
            row:root.draggedRow;design:root.barDesign;ink:root.foreground;muted:root.secondary
            fontFamily:root.barState.fontFamily;motionEnabled:false
        }
    }
}
