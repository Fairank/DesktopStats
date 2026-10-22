import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root
    objectName: "topBarSettings"
    property bool active: false
    property Item headerHost: null
    property Item scrollHost: null
    property real viewportY: 0
    property string selectedItem: ""
    property string addingPlacement: "right"
    property bool barOptionsOpen: false
    property bool placementOpen: false
    readonly property var config: stats.draft.top_bar
    readonly property var rows: { const revision = stats.sensorRevision; const draft = stats.draft; return active ? stats.topBarDraftRows() : [] }
    readonly property var selected: config.items.find(item => item.id === selectedItem)
    readonly property var selectedRow: rows.find(item => item.id === selectedItem) || ({})
    readonly property var sensorChoices:{if(!root.active || !picker.opened)return [];const revision=stats.sensorRevision;return stats.sensorRows}
    readonly property bool sideInspector: width >= 740
    readonly property bool unapplied: JSON.stringify(config) !== JSON.stringify(stats.saved.top_bar)
    readonly property var liveStatus: stats.topBarStatus || ({})
    readonly property var appearance: config.appearance || ({follow_global:true,skin:"glass",glass_transparency:50})
    readonly property var previewConfig: {
        const value=Object.assign({},stats.draft)
        if(appearance.follow_global===false){value.skin=appearance.skin;value.glass_transparency=appearance.glass_transparency}
        if(value.skin==="minimal")value.skin="glass"
        return value
    }
    readonly property real headerHeight: fixedHeader.height
    readonly property real stickyHeaderInset: headerHost ? 0 : fixedHeader.height + 10
    readonly property bool dragging: dragActive
    property string draggedId: ""
    property bool dragActive: false
    property string dropPlacement: ""
    property string dropBeforeId: ""
    property point dragScenePoint: Qt.point(0, 0)
    signal revealInspector(var item)
    spacing: 18
    Theme { id: ui }

    function rowFor(identifier) { return rows.find(row => row.id === identifier) || ({}) }
    function chooseMetric(identifier) {
        if(identifier && stats.addTopBarMetric(identifier)){
            const items=stats.draft.top_bar.items
            root.selectedItem=items[items.length-1].id
            if(addingPlacement!=="right")stats.placeTopBarMetric(root.selectedItem,"",addingPlacement)
            Qt.callLater(root.revealCurrentInspector)
            picker.close()
        }
    }
    function refreshChoices() {
        if(!picker.opened)return
        const q=query.text.toLowerCase().trim()
        const ids=sensorChoices.filter(row=>!q || [row.label,row.search,row.hardware_name,row.unit].join(" ").toLowerCase().includes(q)).map(row=>row.id)
        const oldId=picker.choiceIds[choices.currentIndex]
        if(JSON.stringify(ids)!==JSON.stringify(picker.choiceIds)){
            const hadFocus=choices.activeFocus || !!(choices.currentItem && choices.currentItem.activeFocus)
            const previous=choices.currentIndex
            picker.choiceIds=ids
            choices.currentIndex=ids.length?Math.max(0,ids.includes(oldId)?ids.indexOf(oldId):Math.min(previous,ids.length-1)):-1
            if(hadFocus)Qt.callLater(()=>{if(choices.currentItem)choices.currentItem.forceActiveFocus()})
        }
    }
    onSensorChoicesChanged:refreshChoices()
    function selectItem(identifier) { selectedItem = identifier; Qt.callLater(revealCurrentInspector) }
    function revealCurrentInspector() {
        if (!sideInspector && selected) root.revealInspector(selectedInspector)
    }
    function stateLabel() {
        const state = liveStatus.state || "disabled"
        if (["failed", "error", "unavailable", "unsupported"].includes(state)) return ui.t("无法显示")
        if (state === "partial") return ui.t("部分显示器不可用")
        if (!stats.saved.top_bar.enabled) return ui.t("未启用")
        if (state === "paused" || liveStatus.paused === true) return ui.t("已暂停")
        if (state === "missing_screen") return ui.t("未连接显示器")
        return state === "ready" ? ui.t("运行中") : ui.t("等待显示")
    }
    function stateDetail() {
        if (!stats.saved.top_bar.enabled && liveStatus.state === "disabled") return ""
        return liveStatus.detail || liveStatus.reason || (liveStatus.errors || []).join("\n") || ""
    }
    function cancelDrag() {
        dragActive = false; draggedId = ""; dropPlacement = ""; dropBeforeId = ""
    }
    function updateDrag(scenePoint) {
        dragScenePoint = scenePoint
        dropPlacement = ""; dropBeforeId = ""
        const inHeader = fixedHeader.mapFromItem(null, scenePoint.x, scenePoint.y)
        if (inHeader.x >= 0 && inHeader.x <= fixedHeader.width && inHeader.y >= 0 && inHeader.y <= fixedHeader.height) return
        for (const zone of [leftZone, rightZone]) {
            const point = zone.mapFromItem(null, scenePoint.x, scenePoint.y)
            if (point.x >= 0 && point.x <= zone.width && point.y >= 0 && point.y <= zone.height) {
                dropPlacement = zone.placement
                dropBeforeId = zone.beforeAt(point.y)
                return
            }
        }
    }
    function finishDrag() {
        const identifier = draggedId, before = dropBeforeId, placement = dropPlacement
        const valid = dragActive && !!placement && identifier !== before
        cancelDrag()
        if (valid && stats.placeTopBarMetric(identifier, before, placement)) selectedItem = identifier
    }
    function moveWithinZone(identifier, delta) {
        const item = config.items.find(value => value.id === identifier)
        if (!item) return
        const placement = item.prefs.placement || "right"
        const peers = config.items.filter(value => (value.prefs.placement || "right") === placement)
        const index = peers.findIndex(value => value.id === identifier)
        if (index + delta < 0 || index + delta >= peers.length) return
        const before = delta < 0 ? peers[index - 1].id : (peers[index + 2] ? peers[index + 2].id : "")
        stats.placeTopBarMetric(identifier, before, placement)
    }
    onConfigChanged: {
        if (draggedId && !config.items.some(item => item.id === draggedId)) cancelDrag()
        if (!config.items.some(item => item.id === selectedItem)) selectedItem = config.items.length ? config.items[0].id : ""
    }
    onActiveChanged: if (!active) cancelDrag()
    Keys.onShortcutOverride: function(event) { if (dragging && event.key === Qt.Key_Escape) event.accepted = true }
    Keys.onEscapePressed: function(event) { if (dragging || draggedId) { cancelDrag(); event.accepted = true } }
    Timer {
        interval: 40; repeat: true; running: root.dragging && !!root.scrollHost
        onTriggered: {
            const flick = root.scrollHost
            const point = flick.mapFromItem(null, root.dragScenePoint.x, root.dragScenePoint.y)
            const delta = point.y < root.stickyHeaderInset + 24 ? -12 : point.y > flick.height - 28 ? 12 : 0
            if (delta) {
                flick.contentY = Math.max(0, Math.min(Math.max(0, flick.contentHeight - flick.height), flick.contentY + delta))
                root.updateDrag(root.dragScenePoint)
            }
        }
    }
    component PlainTip: ToolTip {
        id: tip
        delay: 650
        contentItem: Text { text: tip.text; textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 11; wrapMode: Text.Wrap; width: Math.min(360, implicitWidth) }
        background: GlassSurface { tone: "popup"; radius: 7 }
    }
    Item {
        id: headerSlot
        Layout.fillWidth: true
        implicitHeight: root.headerHost ? 0 : fixedHeader.height + 8
        z: 30
        Item {
            id: fixedHeader
            objectName: "topBarFixedHeader"
            parent: root.headerHost || headerSlot
            width: parent.width
            height: headerContent.implicitHeight + 18
            y: root.headerHost ? 0 : Math.max(0, root.viewportY - headerSlot.y)
            z: 30
            Rectangle { visible: !root.headerHost; anchors.fill: parent; anchors.topMargin: -8; color: ui.translucentBackdrop ? (ui.dark ? "#e6242426" : "#d9ffffff") : ui.fallback }
            ColumnLayout {
                id: headerContent
                x: 0; y: 2; width: parent.width
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Text { objectName: "topBarTitle"; text: ui.t("顶部栏"); textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 23; font.weight: Font.DemiBold }
                    Item { Layout.fillWidth: true }
                    Text { text: ui.t("即时生效"); color: ui.muted; font.family: ui.fontFamily; font.pixelSize: ui.metaSize }
                    Toggle { objectName: "topBarEnabled"; checked: stats.saved.top_bar.enabled; Accessible.name: ui.t("启用顶部栏"); onToggled: stats.setTopBarEnabled(checked) }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Text { objectName: "topBarLiveState"; text: root.stateLabel(); textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 11; font.weight: Font.Medium }
                    Text { Layout.fillWidth: true; text: root.unapplied ? ui.t("布局有未应用更改") : ""; textFormat: Text.PlainText; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11; elide: Text.ElideRight }
                }
                Text {
                    id: runtimeMessage
                    objectName: "topBarRuntimeMessage"
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: root.stateDetail()
                    textFormat: Text.PlainText
                    color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11
                    wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                    MouseArea { id: statusHover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                    PlainTip { visible: statusHover.containsMouse; text: runtimeMessage.text }
                }
            }
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: ui.line }
        }
    }
    TopBarPreviewStrip {
        Layout.fillWidth: true
        rows: root.rows; barHeight: root.config.height; itemSpacing: root.config.spacing
        barEnabled: stats.saved.top_bar.enabled; unapplied: root.unapplied; selectedId: root.selectedItem
        appearanceConfig:root.previewConfig;freezeModel:root.dragging || !!root.draggedId
        onSelected: identifier => root.selectItem(identifier)
        onReordered:(identifier,before,placement)=>{if(stats.placeTopBarMetric(identifier,before,placement))root.selectedItem=identifier}
    }
    Flow {
        parent: barOptions
        Layout.fillWidth:true;spacing:6
        Repeater {model:[{id:"compact",label:ui.t("紧凑数字")},{id:"balanced",label:ui.t("均衡")},{id:"graphs",label:ui.t("迷你图表")}]
            ActionButton {required property var modelData;objectName:"topBarPreset_"+modelData.id;text:modelData.label;quiet:true;implicitHeight:28;onClicked:stats.applyTopBarPreset(modelData.id)}
        }
    }
    GridLayout {
        parent: barOptions
        Layout.fillWidth: true; columns: root.width >= 720 ? 3 : root.width >= 440 ? 2 : 1
        uniformCellWidths: true; columnSpacing: 18; rowSpacing: 12
        FormField {
            Layout.fillWidth: true; label: ui.t("显示器")
            Choice { objectName: "topBarMonitorChoice"; Layout.fillWidth: true; implicitHeight: 34; model: [{id:"primary",label:ui.t("主显示器")},{id:"all",label:ui.t("所有显示器")},{id:"selected",label:ui.t("选择显示器")}]; value: root.config.monitor_mode; onPicked: selected => stats.changeTopBar("monitor_mode", selected) }
        }
        FormField {
            Layout.fillWidth: true; label: ui.t("高度")
            Choice { objectName: "topBarHeightChoice"; Layout.fillWidth: true; implicitHeight: 34; model: [{id:"28",label:ui.t("紧凑")+" · 28 px"},{id:"32",label:ui.t("标准")+" · 32 px"},{id:"40",label:ui.t("宽松")+" · 40 px"}]; value: String(root.config.height); onPicked: selected => stats.changeTopBar("height", Number(selected)) }
        }
        FormField {
            Layout.fillWidth: true; label: ui.t("指标间距")
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                ValueSlider { objectName: "topBarSpacing"; Layout.fillWidth: true; from: 4; to: 24; stepSize: 1; value: root.config.spacing; Accessible.name: ui.t("指标间距"); onMoved: stats.changeTopBar("spacing", Math.round(value)) }
                Text { text: root.config.spacing + " px"; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11 }
            }
        }
    }
    Flow {
        parent: barOptions
        Layout.fillWidth: true; spacing: 8; visible: root.config.monitor_mode === "selected"
        Repeater {
            model: stats.topBarScreenChoices
            Check {
                required property var modelData
                objectName: "topBarScreen_" + modelData.id
                text: modelData.label
                checked: root.config.screens.includes(modelData.id)
                onToggled: stats.setTopBarScreenSelected(modelData.id, checked)
            }
        }
    }
    Text { parent: barOptions; Layout.fillWidth: true; visible: root.config.monitor_mode === "selected" && !root.config.screens.length; text: ui.t("选择至少一个显示器后应用。"); textFormat: Text.PlainText; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11; wrapMode: Text.WordWrap }
    ColumnLayout {
        parent: barOptions
        objectName:"topBarAppearanceSettings";Layout.fillWidth:true;spacing:10
        RowLayout {
            Layout.fillWidth:true;spacing:10
            Text {Layout.fillWidth:true;text:ui.t("顶栏外观");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.DemiBold}
            Text {text:ui.t("跟随全局");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
            Toggle {objectName:"topBarFollowGlobal";checked:root.appearance.follow_global;Accessible.name:ui.t("跟随全局");onToggled:stats.changeTopBarAppearance("follow_global",checked)}
        }
        GridLayout {
            Layout.fillWidth:true;visible:root.appearance.follow_global===false
            columns:width>=500?2:1;uniformCellWidths:true;columnSpacing:18;rowSpacing:10
            FormField {Layout.fillWidth:true;label:ui.t("材质")
                Choice {objectName:"topBarSkinChoice";Layout.fillWidth:true;implicitHeight:34;model:[{id:"glass",label:ui.t("清透玻璃")},{id:"frost",label:ui.t("柔雾玻璃")},{id:"tint",label:ui.t("柔彩玻璃")},{id:"card",label:ui.t("经典卡片")},{id:"graphite",label:ui.t("石墨黑")}];value:root.appearance.skin;onPicked:selected=>stats.changeTopBarAppearance("skin",selected)}
            }
            FormField {Layout.fillWidth:true;label:ui.t("透明度");enabled:["glass","frost","tint"].includes(root.appearance.skin)
                RowLayout {Layout.fillWidth:true;spacing:8
                    ValueSlider {objectName:"topBarTransparency";Layout.fillWidth:true;from:0;to:100;value:root.appearance.glass_transparency;Accessible.name:ui.t("透明度");onMoved:stats.changeTopBarAppearance("glass_transparency",value)}
                    Text {text:Math.round(root.appearance.glass_transparency)+"%";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                }
            }
        }
    }
    GridLayout {
        parent: metricsListColumn
        objectName:"topBarMetricsHeading"
        readonly property bool singleLine:width>=600
        Layout.fillWidth:true;Layout.minimumWidth:0;Layout.row:0;Layout.column:0
        columns:singleLine?3:2;columnSpacing:8;rowSpacing:6
        RowLayout {
            Layout.row:0;Layout.column:0;Layout.columnSpan:parent.singleLine?1:2
            Layout.fillWidth:true;Layout.minimumWidth:0;spacing:6
            Text { Layout.minimumWidth:0; text:ui.t("栏内指标"); color:ui.ink; font.family:ui.fontFamily; font.pixelSize:14; font.weight:Font.DemiBold; elide:Text.ElideRight }
            Text { text:root.config.items.length+" / 64"; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11 }
            Item { Layout.fillWidth:true }
        }
        ActionButton { objectName:"topBarPlacementToggle"; Layout.row:parent.singleLine?0:1;Layout.column:parent.singleLine?1:0;Layout.alignment:Qt.AlignLeft;text:ui.t("左右布局"); quiet:!root.placementOpen; implicitHeight:32; onClicked:root.placementOpen=!root.placementOpen }
        ActionButton { id:addMetricButton;objectName:"topBarAddMetric";Layout.row:parent.singleLine?0:1;Layout.column:parent.singleLine?2:1;Layout.alignment:Qt.AlignRight;text:"＋ "+ui.t("添加指标");quiet:true;implicitHeight:32;enabled:root.config.items.length<64;onClicked:{root.addingPlacement="right";picker.open()} }
    }
    Text { parent:metricsListColumn;Layout.fillWidth:true;Layout.row:1;Layout.column:0;text:ui.t("拖动把手排序，或移到左侧与右侧。");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap }
    component MetricZone: ColumnLayout {
        id: zone
        required property string placement
        readonly property var items: root.config.items.filter(item => (item.prefs.placement || "right") === placement)
        visible: items.length > 0 || root.dragging || root.placementOpen
        objectName: "topBarZone_" + placement
        spacing: 5
        function beforeAt(localY) {
            for (let index = 0; index < entries.count; index++) {
                const item = entries.itemAt(index)
                if (item.modelData.id === root.draggedId) continue
                const point = item.mapToItem(zone, 0, item.height / 2)
                if (localY < point.y) return item.modelData.id
            }
            return ""
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: zone.placement === "left" ? ui.t("左侧") : ui.t("右侧"); color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 12; font.weight: Font.Medium }
            Text { text: zone.items.length; color: ui.subtle; font.family: ui.fontFamily; font.pixelSize: 10 }
            Item { Layout.fillWidth: true }
        }
        Repeater {
            id: entries
            model: zone.items
            delegate: ItemDelegate {
                id: card
                required property var modelData
                required property int index
                readonly property var reading: root.rowFor(modelData.id)
                objectName: "topBarItem_" + modelData.id
                Layout.fillWidth: true; Layout.minimumWidth: 0
                implicitHeight: 48; padding: 8
                opacity: root.dragging && root.draggedId === modelData.id ? 0.4 : 1
                focusPolicy: Qt.StrongFocus
                onClicked: root.selectItem(modelData.id)
                Accessible.name: (reading.label || "") + " " + (reading.value || "—")
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Delete) { stats.removeTopBarMetric(modelData.id); event.accepted = true }
                    else if (event.modifiers & Qt.AltModifier) {
                        if ([Qt.Key_Up, Qt.Key_Down].includes(event.key)) { root.moveWithinZone(modelData.id, event.key === Qt.Key_Up ? -1 : 1); event.accepted = true }
                        else if ([Qt.Key_Left, Qt.Key_Right].includes(event.key)) { stats.placeTopBarMetric(modelData.id, "", event.key === Qt.Key_Left ? "left" : "right"); event.accepted = true }
                    }
                }
                background: Rectangle { radius: 7; color: root.selectedItem === card.modelData.id ? ui.cardSelected : card.hovered ? ui.cardHover : "transparent"; border.width: card.activeFocus ? 1 : 0; border.color: ui.accent }
                contentItem: RowLayout {
                    spacing: 8
                    Item {
                        id: dragHandle
                        objectName: "topBarDrag_" + card.modelData.id
                        Layout.preferredWidth: 24; Layout.fillHeight: true
                        Item {
                            anchors.centerIn: parent; width: 10; height: 16
                            Repeater { model: 6; Rectangle { required property int index; x: (index % 2) * 6; y: Math.floor(index / 2) * 6; width: 2; height: 2; radius: 1; color: ui.subtle } }
                        }
                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.SizeAllCursor
                            property point pressPoint: Qt.point(0, 0)
                            onPressed: function(mouse) { root.cancelDrag(); root.draggedId = card.modelData.id; pressPoint = mapToItem(null, mouse.x, mouse.y); root.forceActiveFocus() }
                            onPositionChanged: function(mouse) {
                                if (!pressed || !root.draggedId) return
                                const point = mapToItem(null, mouse.x, mouse.y)
                                if (!root.dragActive && Math.hypot(point.x - pressPoint.x, point.y - pressPoint.y) >= 6) root.dragActive = true
                                if (root.dragActive) root.updateDrag(point)
                            }
                            onReleased: root.finishDrag()
                            onCanceled: root.cancelDrag()
                        }
                    }
                    Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.reading.label || ""; textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 12; elide: Text.ElideRight }
                    TopBarMetricContent { objectName:"topBarValue_"+card.modelData.id;row: card.reading; ink: ui.ink; muted: ui.muted; fontFamily: ui.fontFamily; Layout.preferredWidth: implicitWidth; Layout.preferredHeight: implicitHeight }
                }
                Rectangle { x: 0; y: -3; width: parent.width; height: 2; color: ui.accent; visible: root.dragging && root.dropPlacement === zone.placement && root.dropBeforeId === card.modelData.id }
                PlainTip { visible: card.hovered && !root.dragging; text: [card.reading.label, card.reading.hardware_name, card.reading.source, card.reading.reason].filter(Boolean).join("\n") }
            }
        }
        Item {
            Layout.fillWidth: true
            implicitHeight: zone.items.length ? 12 : 48
            Rectangle { anchors.fill: parent; radius: 6; color: root.dragging && root.dropPlacement === zone.placement && !root.dropBeforeId ? ui.hover : "transparent"; border.width: zone.items.length ? 0 : 1; border.color: ui.line }
            Rectangle { x: 0; y: 1; width: parent.width; height: 2; color: ui.accent; visible: root.dragging && root.dropPlacement === zone.placement && !root.dropBeforeId }
            Text { anchors.centerIn: parent; visible: !zone.items.length; text: ui.t("拖到这里"); color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11 }
        }
    }
    GridLayout {
        id: metricsBody
        Layout.fillWidth: true; columns: root.sideInspector ? 2 : 1; columnSpacing: 20; rowSpacing: 16
        GridLayout {
            id:metricsListColumn
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.alignment: Qt.AlignTop
            columns: 1; rowSpacing: 12
            MetricZone { id: leftZone; placement: "left"; Layout.fillWidth: true; Layout.row: items.length ? 2 : 3; Layout.column: 0 }
            MetricZone { id: rightZone; placement: "right"; Layout.fillWidth: true; Layout.row: leftZone.items.length ? 3 : 2; Layout.column: 0 }
        }
        Item {
            Layout.preferredWidth: root.sideInspector ? (root.width >= 900 ? 336 : 280) : -1
            Layout.fillWidth: !root.sideInspector
            Layout.fillHeight: root.sideInspector
            Layout.alignment: Qt.AlignTop
            implicitHeight: selectedInspector.implicitHeight
            visible: !!root.selected
            TopBarItemInspector { id: selectedInspector; objectName: "topBarSelectedInspector"; width: parent.width; y: root.sideInspector ? Math.max(0, Math.min(Math.max(0, metricsBody.height - height), root.viewportY + root.stickyHeaderInset + 8 - metricsBody.y)) : 0; item: root.selected || null; row: root.selectedRow; index: root.config.items.findIndex(item => item.id === root.selectedItem); count: root.config.items.length; narrow: !root.sideInspector; onRevealRequested:target=>root.revealInspector(target) }
        }
    }
    Text { Layout.fillWidth: true; text: ui.t("悬停查看详情，拖动调整顺序。更多指标收在 +N 中。"); textFormat: Text.PlainText; color: ui.muted; font.family: ui.fontFamily; font.pixelSize: 11; wrapMode: Text.WordWrap }
    ActionButton { objectName:"topBarOptionsToggle"; text:(root.barOptionsOpen ? "− " : "+ ")+ui.t("栏设置")+" · "+root.config.height+" px"; quiet:true; onClicked:root.barOptionsOpen=!root.barOptionsOpen }
    ColumnLayout { id:barOptions; objectName:"topBarSecondarySettings"; Layout.fillWidth:true; visible:root.barOptionsOpen; spacing:16 }
    Rectangle {
        parent: fixedHeader
        visible: root.dragging
        x: parent.mapFromItem(null, root.dragScenePoint.x, root.dragScenePoint.y).x + 12
        y: parent.mapFromItem(null, root.dragScenePoint.x, root.dragScenePoint.y).y + 12
        z: 100
        width: Math.min(220, dragLabel.implicitWidth + 20); height: 32; radius: 7
        color: ui.popupTop; border.width: 1; border.color: ui.selectedLine
        Text { id: dragLabel; anchors.centerIn: parent; text: root.rowFor(root.draggedId).label || ""; textFormat: Text.PlainText; color: ui.ink; font.family: ui.fontFamily; font.pixelSize: 11 }
    }
    Popup {
        id:picker;objectName:"topBarMetricPicker";parent:Overlay.overlay
        property var choiceIds:[]
        x:Math.max(12,(parent.width-width)/2);y:Math.max(12,(parent.height-height)/2)
        width:Math.min(540,parent.width-24);height:Math.min(520,parent.height-24);padding:22;modal:true;focus:true;closePolicy:Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background:GlassSurface {tone:"popup"}
        ColumnLayout {anchors.fill:parent;spacing:10
            RowLayout {Layout.fillWidth:true
                Text {Layout.fillWidth:true;text:ui.t("添加指标");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:20;font.weight:Font.DemiBold}
                IconButton {objectName:"topBarPickerClose";symbol:"close";label:ui.t("关闭");onClicked:picker.close()}
            }
            TextField {id:query;objectName:"topBarMetricSearch";Layout.fillWidth:true;implicitHeight:38;placeholderText:ui.t("搜索传感器或硬件");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;selectByMouse:true;background:GlassSurface {tone:"field"}
                onTextChanged:root.refreshChoices()
                Keys.onDownPressed:event=>{if(choices.count){if(choices.currentIndex<0)choices.currentIndex=0;choices.positionViewAtIndex(choices.currentIndex,ListView.Contain);if(choices.currentItem)choices.currentItem.forceActiveFocus()}event.accepted=true}
                Keys.onReturnPressed:event=>{root.chooseMetric(picker.choiceIds[choices.currentIndex]);event.accepted=true}
                Keys.onEnterPressed:event=>{root.chooseMetric(picker.choiceIds[choices.currentIndex]);event.accepted=true}
            }
            ListView {id:choices;objectName:"topBarMetricChoices";Layout.fillWidth:true;Layout.fillHeight:true;clip:true;boundsBehavior:Flickable.StopAtBounds;reuseItems:true
                model:picker.choiceIds
                ScrollBar.vertical:ScrollBar {}
                delegate:ItemDelegate {id:option;required property var modelData;required property int index;readonly property var entry:root.sensorChoices.find(row=>row.id===modelData) || ({});objectName:"topBarMetricOption_"+modelData;width:choices.width-6;height:54;padding:10;onClicked:root.chooseMetric(modelData)
                    onActiveFocusChanged:if(activeFocus){choices.currentIndex=index;choices.positionViewAtIndex(index,ListView.Contain)}
                    Keys.onReturnPressed:event=>{root.chooseMetric(modelData);event.accepted=true}
                    Keys.onEnterPressed:event=>{root.chooseMetric(modelData);event.accepted=true}
                    Keys.onDownPressed:event=>{if(index<choices.count-1){choices.currentIndex=index+1;choices.positionViewAtIndex(index+1,ListView.Contain);Qt.callLater(()=>{if(choices.currentItem)choices.currentItem.forceActiveFocus()})}event.accepted=true}
                    Keys.onUpPressed:event=>{if(index>0){choices.currentIndex=index-1;choices.positionViewAtIndex(index-1,ListView.Contain);Qt.callLater(()=>{if(choices.currentItem)choices.currentItem.forceActiveFocus()})}else query.forceActiveFocus();event.accepted=true}
                    background:Rectangle {radius:7;color:option.activeFocus?ui.cardSelected:option.hovered?ui.hover:"transparent";border.width:option.activeFocus?1:0;border.color:ui.accent}
                    contentItem:Column {spacing:4
                        Text {width:parent.width;text:(option.entry.label || "")+"   "+(option.entry.value || "—");textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;elide:Text.ElideRight}
                        Text {width:parent.width;text:option.entry.hardware_name || option.entry.reason || option.entry.source || "";textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;elide:Text.ElideRight}
                    }
                }
            }
            ActionButton {Layout.alignment:Qt.AlignRight;text:ui.t("取消");quiet:true;onClicked:picker.close()}
        }
        onOpened:{query.text="";root.refreshChoices();query.forceActiveFocus();stats.inspect()}
        onClosed:addMetricButton.forceActiveFocus()
        Timer {interval:3000;running:picker.opened;repeat:true;onTriggered:stats.inspect()}
    }
}

