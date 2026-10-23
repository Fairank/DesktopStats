import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id:root
    property var item:null
    property var row:({})
    property int index:-1
    property int count:0
    property bool narrow:false
    property string design:"classic"
    property bool galleryOpen:false
    property bool sourceOpen:false
    property string previousItemId:""
    property string groupError:""
    readonly property bool groupPopupOpen:groupDialog.opened
    property string groupOpeningId:""
    property var groupBaseline:[]
    property var groupDraftMetrics:[]
    readonly property bool pendingGroupEdits:groupDialog.opened && JSON.stringify(groupDraftMetrics)!==JSON.stringify(groupBaseline)
    readonly property var groupMetrics:row.group_metrics || (item?[item.metric]:[])
    readonly property var groupOptions:row.group_options || []
    readonly property var availableGroupOptions:groupOptions.filter(option=>!groupDraftMetrics.includes(option.metric)).map(option=>({id:option.metric,label:option.label}))
    readonly property bool hasTemperature:["°C","°F"].includes(row.unit) || (row.group_rows || []).some(member=>["°C","°F"].includes(member.unit))
    readonly property var effectLabels:({off:ui.t("关闭"),auto:ui.t("硬件联动"),heat:ui.t("热感"),flow:ui.t("流动"),spin:ui.t("旋转"),pulse:ui.t("呼吸")})
    readonly property string selectedEffect:item?item.prefs.icon_effect || "off":"off"
    readonly property string hardwareHint:{
        if(row.auto_effect==="off")return ui.t("此读数不表示实时活动，硬件联动保持静态。")
        const members=row.grouped===true?row.group_rows || []:[row]
        if(members.length && members.every(member=>member.icon==="fan"))return ui.t("按实际转速旋转；停转或缺测时静止。")
        if(members.length && members.every(member=>member.icon==="frequency"))return ui.t("按实际频率变化，不用其他读数代替。")
        const profiles=members.map(member=>(member.hardware_state || {}).profile || "")
        if(profiles.length && profiles.every(profile=>["memory","volume"].includes(profile)))return ui.t("用填充和扫光显示实际占用量。")
        if(profiles.length && profiles.every(profile=>["network","disk"].includes(profile)))return ui.t("两个方向各自变化；空闲时静止。")
        if(profiles.length && profiles.every(profile=>profile==="battery"))return ui.t("电量决定填充，充放电决定流向。")
        return ui.t("温度驱动暖弧，功耗驱动蓝弧；只显示有数据的效果。")
    }
    readonly property var effectOptions:{
        const icons=(row.grouped===true?row.group_rows || []:[row]).map(member=>member.icon || "")
        const ids=["off","auto","pulse"]
        if(icons.includes("temperature"))ids.push("heat")
        if(icons.some(icon=>["network","download","upload","disk_read","disk_write","power","voltage"].includes(icon)))ids.push("flow")
        if(icons.includes("fan"))ids.push("spin")
        if(!ids.includes(selectedEffect))ids.push(selectedEffect)
        return ids.map(id=>({id:id,label:effectLabels[id] || id}))
    }
    readonly property real labelColumnWidth:width>=320?92:76
    signal revealRequested(var target)
    readonly property var stylePreviewRow: {
        const revision=stats.sensorRevision, draft=stats.draft, current=root.row
        if(!root.visible || !root.item)return current
        return typeof stats.topBarStylePreviewRow === "function"
            ? stats.topBarStylePreviewRow(root.item.id) : current
    }
    readonly property var peers:stats.draft.top_bar.items.filter(value=>(value.prefs.placement || "right") === (root.item?(root.item.prefs.placement || "right"):"right"))
    readonly property int peerIndex:root.item?peers.findIndex(value=>value.id===root.item.id):-1
    readonly property var allDisplayStyles: [
            {id:"duplex_inline",label:ui.t("单行双向")},{id:"duplex",label:ui.t("双向读数")},
            {id:"label_value",label:ui.t("标签与数值")},{id:"value",label:ui.t("仅数值")},
            {id:"icon_value",label:ui.t("图标与数值")},{id:"stacked",label:ui.t("上下两行")},
            {id:"trend_value",label:ui.t("趋势与数值")},{id:"graph",label:ui.t("迷你图表")},
            {id:"bar_value",label:ui.t("柱状与数值")},{id:"ring_value",label:ui.t("圆环与数值")}
        ]
    readonly property var displayStyles: {
        const gauges=root.row.grouped===true ? (root.row.group_rows || []).every(member=>member.unit==="%" && member.gauge_supported!==false)
            : root.row.gauge_supported===undefined ? root.row.unit==="%" : root.row.gauge_supported===true
        return allDisplayStyles.filter(option=>(!["bar_value","ring_value"].includes(option.id) || gauges)
            && (!["duplex","duplex_inline"].includes(option.id) || (root.row.grouped!==true && root.row.pair_supported===true)))
    }
    readonly property var meta:{const draft=stats.draft;return item?stats.metricInfoFor("",item.metric):({})}
    readonly property string scope:meta.scope || ""
    readonly property string deviceField:({gpus:"gpu_target",networks:"network_target",disks:"disk_target",volumes:"volume_target",storages:"storage_target"})[scope] || "gpu_target"
    readonly property string deviceDefault:({gpus:"0",networks:"auto",disks:"all",volumes:"system",storages:"0"})[scope] || "0"
    readonly property string selectedStyle:item ? item.prefs.style || "label_value" : "label_value"
    readonly property bool effectStyleVisible:["icon_value","duplex","duplex_inline"].includes(selectedStyle)
    readonly property string selectedStyleLabel:(allDisplayStyles.find(option=>option.id===selectedStyle) || {}).label || selectedStyle
    readonly property string displayTitle:(row.grouped===true || ["duplex","duplex_inline"].includes(selectedStyle)) && row.group_label
        ? row.group_label : row.label || ui.t("指标设置")
    readonly property bool hasDevice:["gpus","networks","disks","volumes","storages"].includes(scope)
    onItemChanged: {
        const identifier=item ? item.id : ""
        if(identifier!==previousItemId){if(focusReveal){focusReveal.stop();focusReveal.target=null}galleryOpen=false;sourceOpen=false;groupDialog.close();groupError="";previousItemId=identifier}
    }
    onVisibleChanged:if(!visible){groupDialog.close();galleryOpen=false}
    Keys.onShortcutOverride:event=>{if(root.galleryOpen && event.key===Qt.Key_Escape)event.accepted=true}
    Keys.onEscapePressed:event=>{if(root.galleryOpen){root.closeGallery();event.accepted=true}else event.accepted=false}
    implicitHeight:content.implicitHeight+24
    Theme {id:ui}
    function revealSoon(target){focusReveal.target=target;focusReveal.restart()}
    function closeGallery(){focusReveal.stop();focusReveal.target=null;galleryOpen=false;Qt.callLater(()=>{if(styleChooser.visible){styleChooser.forceActiveFocus();root.revealSoon(styleChooser)}})}
    function chooseStyle(style){if(!item)return;stats.changeTopBarItem(item.id,"style",style);closeGallery()}
    function sampleTip(style,label) {
        const row=root.stylePreviewRow
        return label+"\n"+(row.grouped===true?(row.group_rows || []).map(value=>[value.label,value.value].filter(Boolean).join(" · ")).join("\n"):["duplex","duplex_inline"].includes(style)
            ? (row.paired_rows || []).map(value=>[value.label,value.value].filter(Boolean).join(" · ")).join("\n")
            : [row.label,row.value].filter(Boolean).join(" · "))
    }
    function openGroup(){
        if(!item)return
        groupOpeningId=item.id;groupBaseline=groupMetrics.slice();groupDraftMetrics=groupMetrics.slice();groupError=""
        groupDialog.open()
    }
    function cancelGroupEditing(){groupDialog.close()}
    function confirmGroup(){
        if(!item || item.id!==groupOpeningId || !root.visible)return
        if(JSON.stringify(groupMetrics)!==JSON.stringify(groupBaseline)){
            groupError=ui.t("组合已在其他位置更改，请重新打开后调整。")
            return
        }
        const accepted=stats.setTopBarGroupMetrics(groupOpeningId,groupDraftMetrics.slice())
        if(accepted)groupDialog.close()
        else groupError=ui.t("组合未更新，请重试。")
    }
    function setGroup(metrics,focusMetric,action){
        if(!item || item.id!==groupOpeningId || !groupDialog.opened)return false
        groupDraftMetrics=metrics.slice();groupError=""
        if(focusMetric)Qt.callLater(()=>{
            for(let index=0;index<groupEntries.count;index++){
                const entry=groupEntries.itemAt(index)
                if(entry && entry.modelData===focusMetric){entry.focusAction(action || "down");return}
            }
            if(groupAdd.visible)groupAdd.forceActiveFocus()
        })
        return true
    }
    function moveGroup(metric,delta){
        const metrics=groupDraftMetrics.slice(),index=metrics.indexOf(metric),target=index+delta
        if(index<1 || target<1 || target>=metrics.length)return
        metrics.splice(index,1);metrics.splice(target,0,metric)
        setGroup(metrics,metric,delta<0?"up":"down")
    }
    function removeGroup(metric){
        const index=groupDraftMetrics.indexOf(metric)
        if(index<1)return
        const metrics=groupDraftMetrics.filter(value=>value!==metric)
        setGroup(metrics,metrics[Math.min(index,metrics.length-1)],"remove")
    }
    function groupPreset(){
        if(!item)return
        const family=groupOptions.some(option=>option.metric==="gpu_usage")?"gpu":"cpu"
        const metrics=[item.metric,family+"_usage",family+"_temp",family+"_power"].filter((value,index,array)=>array.indexOf(value)===index)
        setGroup(metrics)
    }
    Timer {id:focusReveal;interval:16;repeat:false;property var target:null;onTriggered:{const item=target;target=null;if(item && root.visible)root.revealRequested(item)}}
    component StyleSample: Flickable {
        id: sampleViewport
        property string sampleStyle: "label_value"
        property string sampleName: ""
        signal activated()
        readonly property real availableWidth:width
        readonly property real availableHeight:height
        implicitHeight: 28
        interactive:false;clip:true;activeFocusOnTab:false
        flickableDirection:Flickable.HorizontalFlick;boundsBehavior:Flickable.StopAtBounds
        contentWidth: Math.max(availableWidth, rendered.implicitWidth)
        contentHeight: availableHeight
        ScrollBar.horizontal: ScrollBar {
            objectName: sampleViewport.sampleName+"ScrollBar"
            policy: ScrollBar.AsNeeded
            height: 3
            contentItem: Rectangle { implicitHeight: 3; radius: 1.5; color: ui.line }
            background: null
        }
        TapHandler { onTapped: sampleViewport.activated() }
        TopBarGroupContent {
            id: rendered
            objectName: sampleViewport.sampleName
            x: Math.max(0,(sampleViewport.availableWidth-implicitWidth)/2)
            y: Math.max(0,(sampleViewport.availableHeight-implicitHeight)/2)
            row: Object.assign({},root.stylePreviewRow,{style:sampleViewport.sampleStyle})
            motionEnabled:stats.motionEnabled
            design:root.design
            ink: ui.ink; muted: ui.muted; fontFamily: ui.fontFamily
            width: implicitWidth; height: implicitHeight
        }
    }
    component RowLabel:Text {
        objectName:"topBarLabel_"+text
        Layout.minimumWidth:root.labelColumnWidth;Layout.preferredWidth:root.labelColumnWidth;Layout.maximumWidth:root.labelColumnWidth
        textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11
        wrapMode:Text.Wrap
    }
    function deviceOptions(){
        const result=[{id:deviceDefault,label:ui.t("默认设备")}]
        for(const id of Object.keys(stats.devices[scope] || {}))if(id!==deviceDefault)result.push({id:id,label:stats.devices[scope][id].label || id})
        const saved=item?(item.prefs[deviceField] || deviceDefault):deviceDefault
        if(!result.some(row=>row.id===saved))result.push({id:saved,label:saved+" · "+ui.t("未连接")})
        return result
    }
    function moveWithinZone(delta){
        if(!item || peerIndex+delta<0 || peerIndex+delta>=peers.length)return
        const before=delta<0?peers[peerIndex-1].id:(peers[peerIndex+2]?peers[peerIndex+2].id:"")
        stats.placeTopBarMetric(item.id,before,item.prefs.placement || "right")
    }
    GlassSurface {anchors.fill:parent;tone:"card";radius:13}
    ColumnLayout {id:content;x:12;y:12;width:parent.width-24;spacing:12
        RowLayout {Layout.fillWidth:true;spacing:2
            Text {objectName:"topBarInspectorTitle";Layout.fillWidth:true;Layout.minimumWidth:0;text:root.displayTitle;textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.DemiBold;elide:Text.ElideRight}
            IconButton {objectName:"topBarItemMoveUp";symbol:"up";label:ui.t("向前移动");enabled:root.peerIndex>0;implicitWidth:28;implicitHeight:28;onClicked:root.moveWithinZone(-1)}
            IconButton {objectName:"topBarItemMoveDown";symbol:"down";label:ui.t("向后移动");enabled:root.peerIndex>=0 && root.peerIndex<root.peers.length-1;implicitWidth:28;implicitHeight:28;onClicked:root.moveWithinZone(1)}
            IconButton {objectName:"topBarItemRemove";symbol:"trash";label:ui.t("移除");danger:true;implicitWidth:28;implicitHeight:28;onClicked:stats.removeTopBarMetric(root.item.id)}
        }
        Text {Layout.fillWidth:true;visible:!!root.row.group_label && root.row.group_label!==root.displayTitle;text:root.row.group_label || "";textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
        Rectangle {
            Layout.fillWidth:true;implicitHeight:64;radius:9;color:ui.well
            HoverHandler {id:currentPreviewHover}
            ToolTip.visible:currentPreviewHover.hovered;ToolTip.text:root.sampleTip(root.selectedStyle,root.selectedStyleLabel);ToolTip.delay:600
            StyleSample {objectName:"topBarCurrentStylePreview";anchors.fill:parent;anchors.margins:10;sampleStyle:root.selectedStyle;sampleName:"topBarCurrentStyleSample"}
        }
        Button {
            id:groupButton;objectName:"topBarGroupButton";visible:root.row.group_supported===true
            Layout.fillWidth:true;implicitHeight:34;leftPadding:10;rightPadding:10
            Accessible.name:ui.t("组合指标")+" · "+root.groupMetrics.length+" / 4"
            onClicked:root.openGroup()
            background:GlassSurface {tone:"field";radius:8;focused:groupButton.activeFocus;highlighted:groupButton.hovered}
            contentItem:RowLayout {spacing:8
                Text {Layout.fillWidth:true;text:ui.t("组合指标");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12}
                Text {text:root.groupMetrics.length+" / 4";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                Icon {name:"chevron";ink:ui.muted;Layout.preferredWidth:12;Layout.preferredHeight:12}
            }
        }
        GridLayout {Layout.fillWidth:true;columns:2;columnSpacing:12;rowSpacing:8
            RowLabel {text:ui.t("显示方式")}
            Button {
                id:styleChooser;objectName:"topBarStyleChooser";Layout.fillWidth:true;Layout.minimumWidth:128;implicitHeight:34
                padding:8;leftPadding:10;rightPadding:9;focusPolicy:Qt.StrongFocus
                Accessible.name:ui.t("显示方式")+" · "+root.selectedStyleLabel
                Accessible.checkable:true;Accessible.checked:root.galleryOpen
                onClicked:{root.galleryOpen=!root.galleryOpen;if(root.galleryOpen)Qt.callLater(()=>{if(styleGallery.item)styleGallery.item.focusSelected()})}
                contentItem:RowLayout {spacing:6
                    Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:root.selectedStyleLabel;textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:ui.bodySize;elide:Text.ElideRight}
                    Icon {name:"down";ink:ui.muted;rotation:root.galleryOpen?180:0;Layout.preferredWidth:12;Layout.preferredHeight:12}
                }
                background:GlassSurface {tone:"field";radius:8;focused:styleChooser.activeFocus;highlighted:styleChooser.hovered || root.galleryOpen}
                ToolTip.visible:hovered;ToolTip.text:Accessible.name;ToolTip.delay:600
            }
        }
        Loader {
            id:styleGallery;objectName:"topBarStyleGallery";Layout.fillWidth:true
            active:root.galleryOpen;visible:root.galleryOpen
            sourceComponent:galleryComponent
        }
        Component {
            id:galleryComponent
            GridLayout {
                id:styleGrid;objectName:"topBarDisplayStyle";columns:root.width>=280?2:1
                uniformCellWidths:true;columnSpacing:8;rowSpacing:6
                function focusSelected(){const index=root.displayStyles.findIndex(option=>option.id===root.selectedStyle);const target=styleRepeater.itemAt(Math.max(0,index));if(target){target.forceActiveFocus();root.revealSoon(target)}}
                Repeater {id:styleRepeater;model:root.displayStyles
                    ItemDelegate {
                        id:styleTile;required property var modelData
                        readonly property bool chosen:root.selectedStyle===modelData.id
                        objectName:"topBarStyle_"+modelData.id
                        Layout.fillWidth:true;Layout.minimumWidth:0;implicitHeight:66;padding:6
                        Layout.columnSpan:modelData.id==="duplex_inline"?styleGrid.columns:1
                        focusPolicy:Qt.StrongFocus
                        Accessible.role:Accessible.RadioButton;Accessible.checked:chosen;Accessible.name:modelData.label
                        onClicked:root.chooseStyle(modelData.id)
                        Keys.onReturnPressed:event=>{root.chooseStyle(modelData.id);event.accepted=true}
                        Keys.onEnterPressed:event=>{root.chooseStyle(modelData.id);event.accepted=true}
                        background:Rectangle {radius:8;color:styleTile.chosen?ui.cardSelected:styleTile.hovered?ui.hover:"transparent";border.width:styleTile.activeFocus || styleTile.chosen?1:0;border.color:styleTile.activeFocus?ui.accent:ui.selectedLine}
                        contentItem:ColumnLayout {spacing:3
                            RowLayout {Layout.fillWidth:true;spacing:8
                                Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:styleTile.modelData.label;textFormat:Text.PlainText;color:styleTile.chosen?ui.ink:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;elide:Text.ElideRight}
                                Rectangle {implicitWidth:12;implicitHeight:12;radius:6;color:"transparent";border.width:styleTile.chosen?4:1;border.color:styleTile.chosen?ui.accent:ui.line}
                            }
                            StyleSample {Layout.fillWidth:true;Layout.preferredHeight:26;sampleStyle:styleTile.modelData.id;sampleName:"topBarStyleSample_"+styleTile.modelData.id;onActivated:root.chooseStyle(styleTile.modelData.id)}
                        }
                        ToolTip.visible:hovered;ToolTip.text:root.sampleTip(modelData.id,modelData.label);ToolTip.delay:600
                    }
                }
            }
        }
        Rectangle {Layout.fillWidth:true;implicitHeight:1;color:ui.line}
        GridLayout {Layout.fillWidth:true;columns:2;columnSpacing:12;rowSpacing:8
            RowLabel {text:ui.t("小数位数")}
            Choice {objectName:"topBarPrecision";Layout.fillWidth:true;Layout.minimumWidth:128;model:[{id:"auto",label:ui.t("自动")},{id:"0",label:"0"},{id:"1",label:"1"},{id:"2",label:"2"}];value:root.item?root.item.prefs.precision || "auto":"auto";onPicked:selected=>stats.changeTopBarItem(root.item.id,"precision",selected)}
            RowLabel {text:ui.t("图标动效")}
            Choice {objectName:"topBarIconEffect";Layout.fillWidth:true;Layout.minimumWidth:128;model:root.effectOptions;value:root.selectedEffect;hoverEnabled:true;onPicked:selected=>stats.changeTopBarItem(root.item.id,"icon_effect",selected);ToolTip.visible:hovered;ToolTip.text:ui.t("动效显示在“图标与数值”和双向读数的图标上。");ToolTip.delay:600}
            RowLabel {visible:root.hasTemperature;text:ui.t("温度单位")}
            Choice {objectName:"topBarTemperatureUnit";Layout.fillWidth:true;Layout.minimumWidth:128;visible:root.hasTemperature;model:[{id:"C",label:"°C"},{id:"F",label:"°F"}];value:root.item?root.item.prefs.temperature_unit || "C":"C";onPicked:selected=>stats.changeTopBarItem(root.item.id,"temperature_unit",selected)}
            RowLabel {visible:!!root.item && ["net_download","net_upload"].includes(root.item.metric);text:ui.t("网速单位")}
            Choice {objectName:"topBarNetworkUnit";Layout.fillWidth:true;Layout.minimumWidth:128;visible:!!root.item && ["net_download","net_upload"].includes(root.item.metric);model:[{id:"MBps",label:"MB/s"},{id:"Mbps",label:"Mbps"}];value:root.item?root.item.prefs.network_unit || "MBps":"MBps";onPicked:selected=>stats.changeTopBarItem(root.item.id,"network_unit",selected)}
        }
        Text {objectName:"topBarIconEffectStyleHint";Layout.fillWidth:true;visible:root.selectedEffect!=="off";text:ui.t("动效显示在“图标与数值”和双向读数的图标上。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
        Text {objectName:"topBarHardwareEffectHint";Layout.fillWidth:true;visible:root.selectedEffect==="auto";text:root.hardwareHint;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
        Text {objectName:"topBarIconEffectInactiveHint";Layout.fillWidth:true;visible:root.selectedEffect!=="off" && !root.effectStyleVisible;text:ui.t("当前显示方式不含图标，已保留动效设置。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
        ActionButton {objectName:"topBarUseIconStyle";Layout.fillWidth:true;visible:root.selectedEffect!=="off" && !root.effectStyleVisible;text:ui.t("使用图标与数值");quiet:true;onClicked:root.chooseStyle("icon_value")}
        GridLayout {
            Layout.fillWidth:true;visible:root.selectedEffect!=="off"
            columns:3;columnSpacing:8;rowSpacing:2
            Text {text:ui.t("强度");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
            ValueSlider {
                objectName:"topBarEffectIntensity";Layout.fillWidth:true;Layout.minimumWidth:80
                from:0;to:1;value:root.item && root.item.prefs.effect_intensity!==undefined?root.item.prefs.effect_intensity:0.5
                Accessible.name:ui.t("强度")
                onMoved:stats.changeTopBarEffect(root.item.id,"effect_intensity",value)
            }
            Text {Layout.minimumWidth:38;text:Math.round((root.item && root.item.prefs.effect_intensity!==undefined?root.item.prefs.effect_intensity:0.5)*100)+"%";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;horizontalAlignment:Text.AlignRight}
            Text {text:ui.t("速度");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
            ValueSlider {
                objectName:"topBarEffectSpeed";Layout.fillWidth:true;Layout.minimumWidth:80
                from:0.5;to:2;value:root.item && root.item.prefs.effect_speed!==undefined?root.item.prefs.effect_speed:1
                Accessible.name:ui.t("速度")
                onMoved:stats.changeTopBarEffect(root.item.id,"effect_speed",value)
            }
            Text {Layout.minimumWidth:38;text:(root.item && root.item.prefs.effect_speed!==undefined?root.item.prefs.effect_speed:1).toFixed(2)+"×";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;horizontalAlignment:Text.AlignRight}
        }
        Text {objectName:"topBarIconEffectDecorationHint";Layout.fillWidth:true;visible:root.selectedEffect!=="off";text:ui.t("图标动效为装饰，不代表告警、真实转速或额外传感器。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
        Rectangle {Layout.fillWidth:true;implicitHeight:1;color:ui.line}
        GridLayout {Layout.fillWidth:true;columns:2;columnSpacing:12;rowSpacing:8
            RowLabel {text:ui.t("位置")}
            Choice {objectName:"topBarPlacement";Layout.fillWidth:true;Layout.minimumWidth:128;model:[{id:"left",label:ui.t("左侧")},{id:"right",label:ui.t("右侧")}];value:root.item?root.item.prefs.placement || "right":"right";onPicked:selected=>stats.placeTopBarMetric(root.item.id,"",selected)}
            RowLabel {visible:root.hasDevice;text:ui.t("设备")}
            Choice {objectName:"topBarDevice";Layout.fillWidth:true;Layout.minimumWidth:128;visible:root.hasDevice;model:root.deviceOptions();value:root.item?root.item.prefs[root.deviceField] || root.deviceDefault:root.deviceDefault;onPicked:selected=>stats.changeTopBarItem(root.item.id,root.deviceField,selected)}
        }
        Rectangle {Layout.fillWidth:true;implicitHeight:1;color:ui.line}
        Button {
            id:sourceToggle;objectName:"topBarInspectorSourceToggle";Layout.fillWidth:true;implicitHeight:30;padding:0
            Accessible.name:ui.t("数据来源");Accessible.checkable:true;Accessible.checked:root.sourceOpen
            onClicked:root.sourceOpen=!root.sourceOpen
            contentItem:RowLayout {spacing:8
                Text {text:ui.t("数据来源");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:root.row.hardware_name || root.row.source || ui.t("等待读数");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;horizontalAlignment:Text.AlignRight;elide:Text.ElideRight}
                Icon {name:"down";ink:ui.muted;rotation:root.sourceOpen?180:0;Layout.preferredWidth:12;Layout.preferredHeight:12}
            }
            background:Rectangle {radius:5;color:ui.hover;visible:sourceToggle.hovered || sourceToggle.visualFocus;border.width:sourceToggle.visualFocus?1:0;border.color:ui.accent}
        }
        ColumnLayout {Layout.fillWidth:true;visible:root.sourceOpen;spacing:5
            Text {Layout.fillWidth:true;text:[root.row.hardware_name,root.row.source].filter(Boolean).join(" · ") || ui.t("等待读数");textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap;lineHeight:1.2}
        }
        Text {Layout.fillWidth:true;visible:!!root.row.reason;text:root.row.reason || "";textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap;lineHeight:1.2}
    }
    Popup {
        id:groupDialog;objectName:"topBarGroupDialog";parent:Overlay.overlay
        width:Math.min(408,parent?parent.width-32:408)
        height:Math.min(groupBody.implicitHeight+32,parent?parent.height-32:480)
        x:parent?(parent.width-width)/2:0;y:parent?(parent.height-height)/2:0
        padding:16;modal:true;focus:true;closePolicy:Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background:GlassSurface {tone:"popup";radius:13}
        onClosed:{root.groupOpeningId="";root.groupBaseline=[];root.groupDraftMetrics=[];root.groupError="";Qt.callLater(()=>{if(root.visible)groupButton.forceActiveFocus()})}
        contentItem:ScrollView {
            id:groupScroll;contentWidth:availableWidth;clip:true
            ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            ColumnLayout {
                id:groupBody;width:groupScroll.availableWidth;spacing:12
                RowLayout {Layout.fillWidth:true
                    Text {Layout.fillWidth:true;text:ui.t("组合指标");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:16;font.weight:Font.DemiBold}
                    IconButton {objectName:"topBarGroupClose";symbol:"close";label:ui.t("取消");implicitWidth:28;implicitHeight:28;onClicked:groupDialog.close()}
                }
                Text {Layout.fillWidth:true;text:ui.t("同一组可显示 1–4 项指标，一起拖动并查看详情。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                Repeater {
                    id:groupEntries;model:root.groupDraftMetrics
                    RowLayout {
                        id:groupEntry;required property string modelData;required property int index
                        Layout.fillWidth:true;spacing:4
                        function focusAction(action){const target=action==="up"?moveUp:action==="remove"?removeMember:moveDown;if(target.enabled)target.forceActiveFocus();else if(moveUp.enabled)moveUp.forceActiveFocus();else if(removeMember.enabled)removeMember.forceActiveFocus();else groupAdd.forceActiveFocus()}
                        Text {text:(groupEntry.index+1).toString().padStart(2,"0");color:ui.subtle;font.family:ui.fontFamily;font.pixelSize:10;Layout.preferredWidth:22}
                        Text {objectName:"topBarGroupLabel_"+groupEntry.modelData;Layout.fillWidth:true;Layout.minimumWidth:0;text:(root.groupOptions.find(option=>option.metric===groupEntry.modelData) || {}).label || groupEntry.modelData;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;elide:Text.ElideRight}
                        Text {visible:groupEntry.index===0;text:ui.t("主指标");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;Layout.rightMargin:6}
                        IconButton {id:moveUp;objectName:"topBarGroupUp_"+groupEntry.modelData;symbol:"up";label:ui.t("向前移动");visible:groupEntry.index>0;enabled:groupEntry.index>1;implicitWidth:28;implicitHeight:30;onClicked:root.moveGroup(groupEntry.modelData,-1)}
                        IconButton {id:moveDown;objectName:"topBarGroupDown_"+groupEntry.modelData;symbol:"down";label:ui.t("向后移动");visible:groupEntry.index>0;enabled:groupEntry.index>0 && groupEntry.index<root.groupDraftMetrics.length-1;implicitWidth:28;implicitHeight:30;onClicked:root.moveGroup(groupEntry.modelData,1)}
                        IconButton {id:removeMember;objectName:"topBarGroupRemove_"+groupEntry.modelData;symbol:"trash";label:ui.t("移除");visible:groupEntry.index>0;enabled:groupEntry.index>0;danger:true;implicitWidth:28;implicitHeight:30;onClicked:root.removeGroup(groupEntry.modelData)}
                    }
                }
                Choice {id:groupAdd;objectName:"topBarGroupAdd";Layout.fillWidth:true;visible:root.groupDraftMetrics.length<4 && root.availableGroupOptions.length>0;model:root.availableGroupOptions;value:"";displayText:ui.t("添加同组指标");Accessible.name:displayText;onPicked:metric=>root.setGroup(root.groupDraftMetrics.concat([metric]),metric)}
                Rectangle {Layout.fillWidth:true;implicitHeight:1;color:ui.line}
                ActionButton {objectName:"topBarGroupPreset";Layout.fillWidth:true;text:ui.t("使用率 · 温度 · 功耗");quiet:true;onClicked:root.groupPreset()}
                Text {objectName:"topBarGroupError";Layout.fillWidth:true;visible:!!root.groupError;text:root.groupError;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                Text {objectName:"topBarGroupApplyNote";Layout.fillWidth:true;text:ui.t("确认后保留到草稿，点击“应用顶部栏”后生效。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                RowLayout {Layout.fillWidth:true;spacing:8
                    Item {Layout.fillWidth:true}
                    ActionButton {objectName:"topBarGroupCancel";text:ui.t("取消");quiet:true;onClicked:groupDialog.close()}
                    ActionButton {objectName:"topBarGroupConfirm";text:ui.t("确认");accent:true;onClicked:root.confirmGroup()}
                }
            }
        }
    }
}
