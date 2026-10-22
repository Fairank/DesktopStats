import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import DesktopStats 1.0
Popup {
    id: root
    objectName: "widgetGallery"
    property string mode: "widget"
    property string targetKey: ""
    property string category: "all"
    property string query: ""
    property bool onlyAvailable: false
    property Item backdropSource: null
    signal chosen(string key)
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(850, parent ? parent.width - 42 : 800)
    height: Math.min(620, parent ? parent.height - 44 : 600)
    padding: 24; modal: true; focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Theme { id: ui }
    property var entries: []
    property string pendingFocusId: ""
    property int pendingFocusIndex: -1
    property bool pendingFocusWasVisible: true
    property real pendingContentY:0
    property bool restoringEntryFocus: false
    property bool activating:false
    property var pendingMetrics: []
    property string selectionNotice:""
    readonly property int existingCount: {const draft=stats.draft;return mode==="metric" ? stats.widgetContentIds(targetKey).length : 0}
    property var liveRows: {if(!opened || mode!=="metric")return [];const revision=stats.sensorRevision;const draft=stats.draft;return stats.metricRowsFor(targetKey)}
    readonly property var liveById: {const result={};for(const row of liveRows)result[row.id]=row;return result}
    signal dismissed()
    function focusIsInResults() {
        const window=results.Window.window
        for(let item=window ? window.activeFocusItem : null;item;item=item.parent)
            if(item===results)return true
        return false
    }
    function restoreEntryFocus() {
        if(pendingFocusIndex<0)return
        const id=pendingFocusId, previous=pendingFocusIndex, wasVisible=pendingFocusWasVisible
        pendingFocusIndex=-1
        if(!opened)return
        if(!entries.length) {search.forceActiveFocus();return}
        const retained=entries.findIndex(item=>item.id===id)
        const index=retained>=0 ? retained : Math.min(previous,entries.length-1)
        if(wasVisible) {focusIndex(index);return}
        const view=results.contentItem
        const previousY=pendingContentY
        restoringEntryFocus=true
        galleryGrid.currentIndex=index
        Qt.callLater(()=>{
            if(galleryGrid.currentItem)galleryGrid.currentItem.forceActiveFocus()
            restoringEntryFocus=false
            view.contentY=Math.max(0,Math.min(previousY,Math.max(0,view.contentHeight-view.height)))
        })
    }
    function refreshEntries(force) {
        const items=mode==="widget"?stats.catalog.templates:liveRows
        const q=query.trim().toLowerCase()
        const next=items.filter(m=>(category==="all"||m.category===category)&&(!q||[m.search,m.label,m.hardware_name,m.unit].filter(Boolean).join(" ").toLowerCase().includes(q))&&(mode==="widget"||!onlyAvailable||m.available))
        if(force || next.map(m=>m.id).join(",")!==entries.map(m=>m.id).join(",")) {
            const focused=focusIsInResults() ? galleryGrid.currentIndex : -1
            if(focused>=0) {
                pendingFocusId=entries[focused].id;pendingFocusIndex=focused
                const item=galleryGrid.currentItem, view=results.contentItem
                pendingContentY=view.contentY
                const top=item ? item.mapToItem(view,0,0).y : -1
                pendingFocusWasVisible=!!item && top+item.height>0 && top<view.height
            }
            else if(!focusIsInResults())pendingFocusIndex=-1
            entries=next
            if(pendingFocusIndex>=0)Qt.callLater(restoreEntryFocus)
        }
    }
    onQueryChanged:refreshEntries(false)
    onCategoryChanged:refreshEntries(false)
    onOnlyAvailableChanged:refreshEntries(false)
    onLiveRowsChanged:if(opened)refreshEntries(false)
    function activate(item) {
        if(!opened || activating)return
        if(mode==="widget") {activating=true;let key=stats.addWidget(item.id);if(key){chosen(key);close()}else activating=false}
        else if(!item.selected) {
            const next=pendingMetrics.slice(), index=next.indexOf(item.id)
            if(index>=0)next.splice(index,1)
            else if(existingCount+next.length<6)next.push(item.id)
            else {selectionNotice=ui.t("已选择六项指标");return}
            pendingMetrics=next;selectionNotice=""
        }
    }
    function reveal(item) {
        if (!item || !results.contentItem) return
        const view=results.contentItem
        galleryGrid.positionViewAtIndex(item.index,GridView.Contain)
    }
    function focusIndex(index) {
        if(!entries.length)return
        galleryGrid.currentIndex=Math.max(0,Math.min(entries.length-1,index))
        galleryGrid.positionViewAtIndex(galleryGrid.currentIndex,GridView.Contain)
        Qt.callLater(()=>{if(root.opened && galleryGrid.currentItem)galleryGrid.currentItem.forceActiveFocus()})
    }
    function revealCategory(item) {
        const view=categoryScroll.contentItem
        if(!view || view.contentY===undefined)return
        const y=item.mapToItem(categoryColumn,0,0).y
        if(y<view.contentY)view.contentY=y
        else if(y+item.height>view.contentY+view.height)view.contentY=y+item.height-view.height
    }
    function showWidgets() { mode="widget"; targetKey=""; query=""; category="all"; open() }
    function showReadings(key) { mode="metric"; targetKey=key; query=""; category="all"; open(); stats.inspect() }
    onOpened: {activating=false;pendingMetrics=[];selectionNotice="";refreshEntries(true);pendingFocusIndex=-1;search.forceActiveFocus();stats.inspect()}
    onClosed: {pendingFocusIndex=-1;pendingMetrics=[];query="";dismissed()}
    background: FrostedBackdrop {
        objectName: "galleryFrostedBackdrop"
        sourceItem: root.backdropSource
        active: root.opened && ui.translucentBackdrop
        radius: 22
        sourceRect: {
            const geometry = [root.x, root.y, root.width, root.height]
            if (!sourceItem) return Qt.rect(0, 0, width, height)
            const origin = mapToItem(sourceItem, 0, 0)
            return Qt.rect(origin.x, origin.y, width, height)
        }
    }
    Overlay.modal: Rectangle { color: "#40071327" }
    Timer { interval: 3000; repeat: true; running: root.opened; onTriggered: stats.inspect() }
    contentItem: ColumnLayout {
        spacing: 18
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Text { text: ui.t(root.mode === "widget" ? "添加小组件" : "添加指标"); font.family: ui.fontFamily; font.pixelSize: 22; font.weight: Font.DemiBold; color: ui.ink }
                Text { Layout.fillWidth: true; text: ui.t(root.mode === "widget" ? "从一个模板开始，内容随时可改。" : "跨硬件自由组合，最多六项。"); font.family: ui.fontFamily; font.pixelSize: 12; color: ui.muted; wrapMode: Text.WordWrap }
            }
            ActionButton { implicitWidth: 32; implicitHeight: 32; leftPadding: 7; rightPadding: 7; quiet: true; text: "×"; Accessible.name: ui.t("关闭"); onClicked: root.close() }
        }
        TextField {
            id: search; objectName: "gallerySearch"; Layout.fillWidth: true; implicitHeight: 40
            placeholderText: ui.t("搜索名称、指标或单位"); placeholderTextColor: ui.muted
            font.family: ui.fontFamily; font.pixelSize: 13; color: ui.ink; selectByMouse: true
            leftPadding: 38; text: root.query; onTextEdited: root.query = text
            Keys.onDownPressed: event=>{root.focusIndex(0);event.accepted=true}
            onAccepted:if(root.entries.length)root.activate(root.entries[0])
            background: GlassSurface { tone: "field"; radius: 10; focused: search.activeFocus }
            Icon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "search"; ink: ui.muted }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
            ScrollView {
                id:categoryScroll; objectName:"galleryCategoryScroll"
                Layout.preferredWidth:135; Layout.fillHeight:true; clip:true
                contentWidth:availableWidth; contentHeight:categoryColumn.implicitHeight
                ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                ColumnLayout {
                    id:categoryColumn; width:categoryScroll.availableWidth; spacing:3
                    Repeater {
                        model:stats.catalog.categories
                        ActionButton {
                            required property var modelData
                            objectName:"galleryCategory_"+modelData.id
                            visible:root.mode==="metric" || modelData.id!=="advanced"
                            Layout.fillWidth:true; implicitHeight:33; quiet:root.category!==modelData.id
                            text:modelData.label
                            onClicked:root.category=modelData.id
                            onActiveFocusChanged:if(activeFocus)root.revealCategory(this)
                            background:Rectangle { radius:8; color:root.category===parent.modelData.id?(ui.dark?"#253c5b":"#e3edfc"):parent.hovered?ui.hover:"transparent" }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: root.entries.length + " " + ui.t(root.mode === "widget" ? "个模板" : "项指标"); font.family: ui.fontFamily; font.pixelSize: 11; color: ui.muted }
                    Item { Layout.fillWidth: true }
                    CheckBox {
                        id: availableCheck
                        visible: root.mode === "metric"; text: ui.t("仅显示可用"); checked: root.onlyAvailable
                        font.family: ui.fontFamily; font.pixelSize: 11
                        onToggled: root.onlyAvailable = checked
                        palette.windowText: ui.ink
                        indicator: Rectangle {
                            implicitWidth: 16; implicitHeight: 16; radius: 4
                            x: availableCheck.leftPadding
                            y: availableCheck.topPadding+(availableCheck.availableHeight-height)/2
                            color: availableCheck.checked ? ui.accent : ui.field
                            border.color: availableCheck.activeFocus ? ui.accent : ui.line
                            Icon { anchors.centerIn: parent; width: 12; height: 12; name: "check"; ink: "white"; visible: availableCheck.checked }
                        }
                    }
                }
                ScrollView {
                    id:results; objectName:"galleryResultsScroll"
                    Layout.fillWidth:true; Layout.fillHeight:true; clip:true; contentWidth:availableWidth
                    ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                    contentItem:GridView {
                        id:galleryGrid; objectName:"galleryResultsGrid"
                        readonly property int columns:width>=420?2:1
                        cellWidth:width/columns; cellHeight:root.mode==="widget"?122:122
                        model:root.entries; clip:true; cacheBuffer:100
                        boundsBehavior:Flickable.StopAtBounds
                        delegate:ItemDelegate {
                            id:entry
                            required property var modelData
                            required property int index
                            readonly property var live:root.mode==="metric" ? root.liveById[modelData.id] || modelData : modelData
                            objectName:"galleryItem_"+modelData.id
                            width:galleryGrid.cellWidth-10; height:galleryGrid.cellHeight-10
                            focusPolicy:Qt.StrongFocus
                            onClicked:root.activate(live)
                            Keys.onRightPressed:root.focusIndex(index+1)
                            Keys.onLeftPressed:root.focusIndex(index-1)
                            Keys.onDownPressed:root.focusIndex(index+galleryGrid.columns)
                            Keys.onUpPressed:root.focusIndex(index-galleryGrid.columns)
                            Keys.onReturnPressed:event=>{root.activate(live);event.accepted=true}
                            Keys.onEnterPressed:event=>{root.activate(live);event.accepted=true}
                            onActiveFocusChanged:if(activeFocus) {galleryGrid.currentIndex=index;if(!root.restoringEntryFocus)root.reveal(entry)}
                            background:GlassSurface { radius:13; tone:"panel"; focused:entry.activeFocus; highlighted:entry.hovered }
                            contentItem:Item {
                                HardwareCard {
                                    visible:root.mode==="widget" && entry.modelData.id!=="status_bar"; x:4; y:12; width:78; height:78
                                    moduleKey:"gallery"; config:{const draft=stats.draft;return root.mode==="widget"?stats.templatePreview(entry.modelData.id):draft}
                                    readings:root.opened?stats.readings:({}); history:[]; frosted:stats.coatingAllowed; surface:true
                                }
                                Item {
                                    visible:root.mode==="widget" && entry.modelData.id==="status_bar"
                                    x:4;y:12;width:78;height:78
                                    Rectangle {x:1;y:24;width:76;height:30;radius:8;color:ui.field;border.color:ui.line}
                                    Row {
                                        x:8;y:33;spacing:7
                                        Repeater {
                                            model:3
                                            Column {
                                                spacing:3
                                                Rectangle {width:14;height:3;radius:1.5;color:ui.muted;opacity:.7}
                                                Rectangle {width:10;height:3;radius:1.5;color:ui.muted;opacity:.3}
                                            }
                                        }
                                    }
                                }
                                Column {
                                    x:root.mode==="widget"?92:10; y:10; width:parent.width-x-10; spacing:7
                                    RowLayout {
                                        width:parent.width; spacing:6
                                        Text { Layout.fillWidth:true; Layout.preferredHeight:root.mode==="widget"?30:18; text:entry.live.label; textFormat:Text.PlainText; font.family:ui.fontFamily; font.pixelSize:11; font.weight:Font.DemiBold; color:ui.ink; wrapMode:Text.WordWrap; maximumLineCount:2; elide:Text.ElideRight; verticalAlignment:Text.AlignVCenter }
                                        Icon { width:15; height:15; name:root.mode==="metric" && (entry.live.selected || root.pendingMetrics.includes(entry.modelData.id))?"check":"plus"; ink:ui.accent }
                                    }
                                    Text {
                                        width:parent.width; height:30
                                        text:root.mode==="widget"?(entry.modelData.description || ""):(entry.live.hardware_name || entry.live.note || entry.live.source || "")
                                        textFormat:Text.PlainText
                                        font.family:ui.fontFamily; font.pixelSize:10; color:ui.muted
                                        wrapMode:Text.WordWrap; maximumLineCount:2; elide:Text.ElideRight
                                    }
                                    Text { visible:root.mode==="metric"; width:parent.width; text:root.mode==="metric"?(entry.live.available?entry.live.value:(entry.live.reason || ui.t("当前设备未提供"))):""; font.family:ui.fontFamily; font.pixelSize:11; color:entry.live.available?(ui.dark?"#68d5ad":"#29946d"):ui.muted; elide:Text.ElideRight }
                                }
                            }
                            Accessible.name:(live.hardware_name?live.hardware_name+" · ":"")+live.label
                            ToolTip.visible:hovered; ToolTip.delay:600
                            ToolTip.text:[live.hardware_name,live.label,live.source,live.note,live.reason].filter(Boolean).join("\n")
                        }
                        Text { anchors.centerIn:parent; visible:root.entries.length===0; text:ui.t("没有匹配的结果"); font.family:ui.fontFamily; color:ui.muted; font.pixelSize:13 }
                    }
                }
            }
        }
        RowLayout {
            visible:root.mode==="metric"; Layout.fillWidth:true; spacing:10
            Text { Layout.fillWidth:true; text:root.selectionNotice || (root.existingCount+root.pendingMetrics.length)+" / 6 · "+ui.t("可连续选择，完成后一起添加。"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap }
            ActionButton { objectName:"cancelMetricSelection"; quiet:true; text:ui.t("取消"); onClicked:root.close() }
            ActionButton {
                objectName:"confirmMetricSelection"; accent:true
                text:root.pendingMetrics.length?ui.t("添加所选")+" ("+root.pendingMetrics.length+")":ui.t("完成")
                onClicked: {
                    if(!root.pendingMetrics.length || stats.addMetrics(root.targetKey,root.pendingMetrics))root.close()
                    else root.selectionNotice=stats.status || ui.t("操作未完成，请重试")
                }
            }
        }
    }
}
