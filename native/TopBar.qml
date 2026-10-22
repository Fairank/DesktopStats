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
    property bool dragHeld: false
    property bool dragging: false
    property string draggedId: ""
    property string dropBeforeId: ""
    property string dropPlacement: ""
    property real insertionX: 0
    property var dragSlots: []
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
    function beginDrag(identifier) {
        cancelDrag()
        dragHeld=true;draggedId=identifier
        const slots=[]
        for(let index=0;index<metrics.count;index++){
            const item=metrics.itemAt(index)
            slots.push({id:item.modelData.id,x:item.x,width:item.width,placement:item.modelData.placement || "right"})
        }
        dragSlots=slots
        barState.leaveBar()
    }
    function cancelDrag() {dragHeld=false;dragging=false;draggedId="";dropBeforeId="";dropPlacement="";dragSlots=[]}
    function updateDrop(point) {
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
        background: Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: 5
            color: root.tint(menuButton.down ? 0.11 : 0.065)
            visible: menuButton.hovered || menuButton.down
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
            Accessible.name:(modelData.label || "")+" "+(modelData.value || "—")
            Accessible.onPressAction:root.barState.clickMetric(modelData.id)
            x: frozenSlot?frozenSlot.x:modelData.x
            y: modelData.y
            width: frozenSlot?frozenSlot.width:modelData.width
            height: modelData.height
            opacity:root.dragging && root.draggedId===modelData.id?.5:1

            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: 5
                color: root.tint(metricMouse.pressed ? 0.11 : 0.065)
                visible: metricMouse.containsMouse || (root.barState.pinned && root.barState.detail.id === metric.modelData.id)
            }
            TopBarMetricContent {
                id: metricContent
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
                onPressed:function(mouse){if(mouse.button===Qt.LeftButton){root.beginDrag(metric.modelData.id);pressPoint=mapToItem(root.contentItem,mouse.x,mouse.y)}}
                onPositionChanged:function(mouse){
                    if(!pressed || !root.dragHeld)return
                    const point=mapToItem(root.contentItem,mouse.x,mouse.y)
                    if(!root.dragging && Math.hypot(point.x-pressPoint.x,point.y-pressPoint.y)>=6)root.dragging=true
                    if(root.dragging)root.updateDrop(point)
                }
                onReleased:function(mouse){if(mouse.button===Qt.LeftButton){if(!root.dragHeld)return;if(root.dragging)root.finishDrag();else{root.cancelDrag();root.barState.clickMetric(metric.modelData.id)}}else{root.cancelDrag();root.barState.menu()}}
                onCanceled:root.cancelDrag()
            }
            PlainTip {
                visible: metricMouse.containsMouse && metricContent.labelTruncated && !root.dragHeld && !root.barState.detail.id && !root.barState.operationMessage
                text: (metric.modelData.label || "") + "  " + (metric.modelData.value || "—")
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
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: 5
            color: root.tint(overflowMouse.pressed ? 0.11 : 0.065)
            visible: overflowMouse.containsMouse
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
        width:2;height:Math.max(0,root.height-8);radius:1;color:root.foreground
    }
}
