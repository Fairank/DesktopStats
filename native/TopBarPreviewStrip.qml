import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import DesktopStats 1.0

ColumnLayout {
    id: root
    property var rows: []
    property int barHeight: 32
    property int itemSpacing: 12
    property bool barEnabled: false
    property bool unapplied: false
    property var appearanceConfig: stats.draft
    readonly property bool darkMaterial: appearanceConfig.theme==="dark" || appearanceConfig.skin==="graphite"
    readonly property color barInk: appearanceConfig.skin==="glass" ? (darkMaterial?"#f5f6f8":"#1f242b") : (darkMaterial?"#f4f6f9":"#202833")
    readonly property color barMuted: appearanceConfig.skin==="glass" ? (darkMaterial?"#b8bdc7":"#303945") : (darkMaterial?"#b8c2cf":"#566272")
    property bool freezeModel: false
    property string selectedId: ""
    property int shown: 0
    property var displayRows: []
    property bool dragHeld: false
    property bool dragging: false
    property string draggedId: ""
    property string dropBeforeId: ""
    property string dropPlacement: ""
    property real insertionX: 0
    readonly property var visibleRows: displayRows.slice(0, shown)
    readonly property var leftRows: visibleRows.filter(row => row.placement === "left")
    readonly property var rightRows: visibleRows.filter(row => row.placement !== "left")
    readonly property int hiddenCount: displayRows.length - shown
    signal selected(string identifier)
    signal reordered(string identifier, string before, string placement)
    spacing: 9
    Theme { id: ui }
    component PlainTip: ToolTip {
        id: tip
        delay: 600
        contentItem: Text { text: tip.text; textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap }
        background: GlassSurface { tone: "popup"; radius: 7 }
    }

    function hitWidth(index) {
        const content = measurements.itemAt(index)
        return content ? Math.max(barHeight, Math.ceil(content.implicitWidth + 12)) : 0
    }
    function overflowWidth(count) {
        return Math.max(barHeight, Math.ceil(Math.max(36, overflowFont.advanceWidth("＋" + count)) + 12))
    }
    function rowWidth(row) {
        const index = displayRows.findIndex(value => value.id === row.id)
        return index >= 0 ? hitWidth(index) : barHeight
    }
    function updateFit() {
        const available = strip.width - 16 - Math.max(barHeight, 24) - itemSpacing
        let used = 0
        const widths = [0]
        for (let index = 0; index < displayRows.length; index++) {
            if (!measurements.itemAt(index)) return
            used += hitWidth(index)
            widths.push(used)
        }
        let count = displayRows.length
        if (used + itemSpacing * Math.max(0, count - 1) > available) {
            for (count = displayRows.length - 1; count >= 0; count--) {
                if (widths[count] + itemSpacing * count + overflowWidth(displayRows.length - count) <= available)
                    break
            }
        }
        shown = Math.max(0, count)
    }
    function syncRows() { if (!dragHeld && !freezeModel) { displayRows=rows; fit.restart() } }
    function cancelDrag() { dragHeld=false; dragging=false; draggedId=""; dropPlacement=""; dropBeforeId=""; Qt.callLater(syncRows) }
    function updateDrop(point) {
        dropPlacement="";dropBeforeId=""
        if(point.x<0 || point.x>strip.width || point.y<0 || point.y>strip.height)return
        const slots=[]
        for(const group of [leftMetrics,rightMetrics])for(let i=0;i<group.count;i++){
            const item=group.itemAt(i)
            const origin=item.mapToItem(strip,0,0)
            slots.push({id:item.modelData.id,placement:item.modelData.placement,x:origin.x,width:item.width})
        }
        const hovered=slots.find(slot=>point.x>=slot.x && point.x<=slot.x+slot.width)
        dropPlacement=hovered?hovered.placement:point.x<strip.width/2?"left":"right"
        const peers=slots.filter(slot=>slot.placement===dropPlacement && slot.id!==draggedId).sort((a,b)=>a.x-b.x)
        const before=peers.find(slot=>point.x<slot.x+slot.width/2)
        dropBeforeId=before?before.id:""
        insertionX=before?before.x-itemSpacing/2:peers.length?peers[peers.length-1].x+peers[peers.length-1].width+itemSpacing/2:dropPlacement==="left"?8+Math.max(barHeight,24)+itemSpacing:strip.width-8
    }
    function finishDrag() {
        const identifier=draggedId,before=dropBeforeId,placement=dropPlacement
        const valid=dragging && placement && identifier!==before
        cancelDrag()
        if(valid)reordered(identifier,before,placement)
    }
    onRowsChanged: syncRows()
    onFreezeModelChanged: syncRows()
    onVisibleChanged:if(!visible)cancelDrag()
    onWidthChanged: fit.restart()
    onItemSpacingChanged: fit.restart()
    onBarHeightChanged: fit.restart()
    Timer { id: fit; interval: 0; onTriggered: root.updateFit() }
    FontMetrics {
        id: overflowFont
        font.family: ui.fontFamily
        font.pixelSize: 12
        font.weight: Font.DemiBold
    }
    Repeater {
        id: measurements
        model: root.displayRows
        onItemAdded: fit.restart()
        delegate: TopBarGroupContent {
            required property var modelData
            visible: false
            row: modelData
            reserveValueWidth: true
            fontFamily: ui.fontFamily
            onImplicitWidthChanged: fit.restart()
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Text {
            objectName: "topBarPreviewState"
            Layout.fillWidth: true
            text: !root.barEnabled ? ui.t("预览 · 未启用") : root.unapplied ? ui.t("预览 · 尚未应用") : ui.t("布局预览")
            textFormat: Text.PlainText
            color: ui.muted
            font.family: ui.fontFamily
            font.pixelSize: 11
            font.weight: Font.Medium
            wrapMode: Text.WordWrap
        }
        Text {
            text: root.barHeight + " px"
            color: ui.muted
            font.family: ui.fontFamily
            font.pixelSize: 11
        }
    }
    Item {
        id: strip
        objectName: "topBarAppearancePreview"
        Layout.fillWidth: true
        implicitHeight: root.barHeight
        MaterialSurface {
            anchors.fill: parent
            config: root.appearanceConfig
            frosted: stats.coatingAllowed
            cornerRadius: 0
        }
        Image {
            x: 8 + (Math.max(root.barHeight, 24) - width) / 2
            anchors.verticalCenter: parent.verticalCenter
            width: 20; height: 20
            source: "../assets/icon.png"
            mipmap: true
        }
        component PreviewMetric: ToolButton {
            id: metric
            required property var modelData
            objectName: "topBarPreviewMetric_" + modelData.id
            width: root.rowWidth(modelData)
            height: root.barHeight
            padding: 0
            Accessible.name: (modelData.grouped?modelData.group_label:modelData.label) + " " + (modelData.grouped?modelData.group_value:modelData.value)
            onClicked: root.selected(modelData.id)
            Keys.onShortcutOverride:function(event){if(root.dragHeld && event.key===Qt.Key_Escape)event.accepted=true}
            Keys.onPressed:function(event){
                if(event.modifiers & Qt.AltModifier && [Qt.Key_Left,Qt.Key_Right].includes(event.key)){
                    const peers=root.displayRows.filter(row=>row.placement===modelData.placement)
                    const index=peers.findIndex(row=>row.id===modelData.id)
                    const delta=event.key===Qt.Key_Left?-1:1
                    if(index+delta>=0 && index+delta<peers.length){const before=delta<0?peers[index-1].id:peers[index+2]?peers[index+2].id:"";root.reordered(modelData.id,before,modelData.placement)}
                    event.accepted=true
                }else if(event.key===Qt.Key_Escape && root.dragHeld){root.cancelDrag();event.accepted=true}
            }
            contentItem: Item {
                TopBarGroupContent {
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    width: implicitWidth; height: implicitHeight
                    row: metric.modelData
                    ink: root.barInk; muted: root.barMuted; fontFamily: ui.fontFamily
                }
            }
            background: Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: 5
                color: metric.modelData.id === root.selectedId ? ui.cardSelected : previewMouse.containsMouse ? ui.hover : "transparent"
                border.width:metric.activeFocus?1:0;border.color:ui.accent
            }
            MouseArea {
                id:previewMouse;anchors.fill:parent;hoverEnabled:true;cursorShape:root.dragging?Qt.ClosedHandCursor:Qt.OpenHandCursor
                property point origin:Qt.point(0,0)
                onPressed:function(mouse){root.cancelDrag();root.dragHeld=true;root.draggedId=metric.modelData.id;origin=mapToItem(strip,mouse.x,mouse.y);metric.forceActiveFocus()}
                onPositionChanged:function(mouse){if(!pressed || !root.draggedId)return;const point=mapToItem(strip,mouse.x,mouse.y);if(!root.dragging && Math.hypot(point.x-origin.x,point.y-origin.y)>=6)root.dragging=true;if(root.dragging)root.updateDrop(point)}
                onReleased:{if(!root.dragHeld)return;if(root.dragging)root.finishDrag();else{const id=root.draggedId;root.cancelDrag();root.selected(id)}}
                onCanceled:root.cancelDrag()
            }
            PlainTip { visible: previewMouse.containsMouse && !root.dragHeld; text: (metric.modelData.grouped?metric.modelData.group_label:metric.modelData.label) + "  " + (metric.modelData.grouped?metric.modelData.group_value:metric.modelData.value) }
        }
        Row {
            x: 8 + Math.max(root.barHeight, 24) + root.itemSpacing
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.itemSpacing
            Repeater { id:leftMetrics;model: root.leftRows; delegate: PreviewMetric {} }
        }
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.itemSpacing
            Repeater { id:rightMetrics;model: root.rightRows; delegate: PreviewMetric {} }
            ToolButton {
                objectName: "topBarPreviewOverflow"
                visible: root.hiddenCount > 0
                width: root.overflowWidth(root.hiddenCount)
                height: root.barHeight
                padding: 0
                Accessible.name: ui.t("更多指标")
                onClicked: if (root.hiddenCount > 0) root.selected(root.displayRows[root.shown].id)
                contentItem: Text {
                    text: "＋" + root.hiddenCount
                    textFormat: Text.PlainText
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    color: root.barInk
                    font: overflowFont.font
                }
                background: Rectangle { radius: 5; color: parent.hovered ? ui.hover : "transparent" }
            }
        }
        Rectangle {objectName:"topBarPreviewInsertion";visible:root.dragging && !!root.dropPlacement;x:Math.max(1,Math.min(strip.width-2,root.insertionX));y:3;width:2;height:strip.height-6;radius:1;color:ui.accent}
    }
    Text {Layout.fillWidth:true;text:ui.t("拖动预览中的指标也可排序。");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
}
