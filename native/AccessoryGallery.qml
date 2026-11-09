import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Popup {
    id: root
    objectName:"accessoryGallery"
    property bool ownerActive:true
    property string initialStyle:"miniature"
    property string selectedStyle:"miniature"
    property string category:"case"
    property string brand:""
    property string query:""
    property var library:({})
    property real phase:0
    property bool demoMotion:false
    property int demoRpm:1200
    property bool demandPending:false
    readonly property bool gpuMode:category==="gpu"
    property string selectedGpuId:""
    property var gpuReference:({})
    property bool gpuPreviewReady:false
    property int gpuPreviewEpoch:0
    function clearGpuPreview() {
        ++gpuPreviewEpoch
        gpuPreviewReady=false
        gpuReference=({})
    }
    function refreshGpuPreview() {
        const identity=selectedGpuId,epoch=++gpuPreviewEpoch
        // The one descriptor may survive a style change, never its raster item.
        const previous=gpuReference.id===identity && !gpuReference.unavailable?gpuReference:null
        gpuPreviewReady=false
        gpuReference=({})
        if(!visible || !ownerActive || !gpuMode || !identity)return
        Qt.callLater(function() {
            if(epoch!==root.gpuPreviewEpoch || !root.visible || !root.ownerActive
                    || !root.gpuMode || identity!==root.selectedGpuId)return
            const info=previous || (typeof stats.accessoryGpuReference==="function"
                ?stats.accessoryGpuReference(identity):({}))
            root.gpuReference=info && info.id===identity && info.appearance
                ?info:({id:identity,unavailable:true})
            root.gpuPreviewReady=!root.gpuReference.unavailable
        })
    }
    function synchronizeGpuSelection() {
        if(!gpuMode)return
        if(!filtered.some(row=>row.id===selectedGpuId))
            selectedGpuId=filtered.length?filtered[0].id:""
        else if(visible && !gpuReference.id)refreshGpuPreview()
    }
    onSelectedGpuIdChanged:refreshGpuPreview()
    readonly property bool asyncArt:typeof stats.setAccessoryArtDemand==="function"
    function scheduleDemand() {
        if(!asyncArt || demandPending)return
        demandPending=true
        Qt.callLater(submitDemand)
    }
    function submitDemand() {
        demandPending=false
        if(!asyncArt || !visible || !ownerActive)return
        if(gpuMode){stats.setAccessoryArtDemand([]);return}
        const rows=grid.contentItem?grid.contentItem.children.filter(item=>item.inViewport===true && item.artModelId)
            .sort((a,b)=>a.y-b.y || a.x-b.x).slice(0,16).map(item=>({kind:category,id:item.artModelId,style:selectedStyle})):[]
        stats.setAccessoryArtDemand(rows)
    }
    readonly property string catalogKey:({gpu:"gpus",case:"cases",cooler:"coolers",psu:"psus",fan:"fans",radiator:"radiators",
        cpu_block:"cpu_blocks",gpu_block:"gpu_blocks",pump:"loop_pumps",reservoir:"loop_reservoirs",pump_reservoir:"loop_combos",fitting:"loop_fittings",tubing:"loop_tubing"})[category]
    readonly property var entries:library[catalogKey] || []
    readonly property var brands:[{id:"",label:ui.t("全部品牌")}].concat([...new Set(entries.map(row=>row.brand).filter(Boolean))].sort().map(value=>({id:value,label:value})))
    readonly property var filtered:entries.filter(row=>(!brand||row.brand===brand)&&(!query||((row.label||"")+" "+(row.brand||"")).toLowerCase().includes(query.toLowerCase())))
    readonly property bool visibleRotors: !gpuMode && !!grid.contentItem && grid.contentItem.children.some(item=>item.visible && item.hasRotors===true && item.y+item.height>grid.contentY && item.y<grid.contentY+grid.height)
    readonly property bool motionActive:visible && ownerActive && stats.motionEnabled && demoMotion && demoRpm>0 && visibleRotors
    parent:Overlay.overlay
    anchors.centerIn:parent
    width:Math.min(1020,parent?parent.width-36:980)
    height:Math.min(760,parent?parent.height-44:700)
    padding:20;modal:true;focus:true
    closePolicy:Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Theme {id:ui}
    Connections {
        target:stats
        ignoreUnknownSignals:true
        function onHardwarePacksChanged(){if(root.visible){root.library=stats.accessoryCatalog;root.scheduleDemand()}}
    }
    background:GlassSurface {tone:"window";radius:18}
    onAboutToShow:{stats.setAccessoryGalleryActive(true);selectedStyle=initialStyle;library=stats.accessoryCatalog;scheduleDemand()}
    onClosed:{demoMotion=false;clearGpuPreview();selectedGpuId="";library=({});stats.setAccessoryGalleryActive(false)}
    onAboutToHide:clearGpuPreview()
    onOwnerActiveChanged:if(!ownerActive){clearGpuPreview();close()}
    onVisibleChanged:{if(!visible)clearGpuPreview();else synchronizeGpuSelection();scheduleDemand()}
    onSelectedStyleChanged:{if(gpuMode)refreshGpuPreview();scheduleDemand()}
    Component.onDestruction:if(typeof stats!=="undefined" && stats)stats.setAccessoryGalleryActive(false)
    onCategoryChanged:{clearGpuPreview();if(gpuMode)demoMotion=false;brand="";grid.positionViewAtBeginning();synchronizeGpuSelection();scheduleDemand()}
    onFilteredChanged:{grid.positionViewAtBeginning();synchronizeGpuSelection();scheduleDemand()}
    AssemblyClock {
        id: clock
        objectName:"accessoryDemoClock"
        active:root.motionActive
        backend:QtObject {
            function advanceFrame(elapsed) {root.phase=(root.phase+Math.max(0,Math.min(136,elapsed))*root.demoRpm/20000)%360}
        }
    }
    contentItem:ColumnLayout {
        spacing:9
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.fillWidth:true;text:ui.t("硬件型号图鉴");font.family:ui.fontFamily;font.pixelSize:21;font.weight:Font.DemiBold;color:ui.ink}
            ActionButton {
                objectName:"accessoryPacksDownload";text:ui.t("硬件扩展包");quiet:true
                enabled:typeof stats.openHardwarePacksDownload==="function"
                onClicked:stats.openHardwarePacksDownload()
            }
            ActionButton {objectName:"accessoryDownload";visible:["case","cooler","psu","fan"].includes(root.category);text:ui.t("下载 SVG 图集");quiet:true;onClicked:stats.downloadAccessoryArt(root.category)
                ToolTip.visible:hovered;ToolTip.text:ui.t("应用已自带这些外观；下载的是独立 SVG 图集。")}
            IconButton {objectName:"closeAccessoryGallery";symbol:"close";label:ui.t("关闭");onClicked:root.close()}
        }
        Text {Layout.fillWidth:true;text:ui.t(root.gpuMode?"按型号浏览六种外观":"按型号浏览二维外观；切换图鉴不会改动装机和顶部栏设置。")
            font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
        Flow {
            Layout.fillWidth:true;spacing:6
            Repeater {
                model:[{id:"gpu",key:"gpus",label:ui.t("显卡")},{id:"case",key:"cases",label:ui.t("机箱")},{id:"cooler",key:"coolers",label:ui.t("CPU 散热器")},
                       {id:"psu",key:"psus",label:ui.t("电源")},{id:"fan",key:"fans",label:ui.t("机箱风扇")},
                       {id:"radiator",key:"radiators",label:ui.t("独立冷排")},
                       {id:"cpu_block",key:"cpu_blocks",label:ui.t("CPU 冷头")},{id:"gpu_block",key:"gpu_blocks",label:ui.t("GPU 冷头")},
                       {id:"pump",key:"loop_pumps",label:ui.t("水泵／泵盖")},
                       {id:"reservoir",key:"loop_reservoirs",label:ui.t("水箱")},{id:"pump_reservoir",key:"loop_combos",label:ui.t("泵箱组合")},
                       {id:"fitting",key:"loop_fittings",label:ui.t("接头")},{id:"tubing",key:"loop_tubing",label:ui.t("管材")}]
                ActionButton {
                    required property var modelData
                    objectName:"accessoryCategory_"+modelData.id
                    text:modelData.label+" · "+(root.library[modelData.key] || []).length
                    checked:root.category===modelData.id;onClicked:root.category=modelData.id
                }
            }
        }
        RowLayout {
            Layout.fillWidth:true;spacing:8
            TextField {
                objectName:"accessorySearch";Layout.fillWidth:true;implicitHeight:ui.controlHeight
                placeholderText:ui.t("搜索品牌或型号");text:root.query;onTextEdited:root.query=text
                font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;selectByMouse:true
                leftPadding:11;rightPadding:11;placeholderTextColor:ui.muted
                selectionColor:ui.selection;selectedTextColor:ui.ink
                background:GlassSurface {tone:"field";radius:ui.controlRadius}
            }
            Choice {objectName:"accessoryBrandChoice";Layout.preferredWidth:Math.min(190,root.width*.29);model:root.brands;value:root.brand
                Accessible.name:ui.t("品牌筛选");onPicked:value=>root.brand=value}
        }
        RowLayout {
            Layout.fillWidth:true;spacing:8
            Choice {objectName:"accessoryStyleChoice";Layout.preferredWidth:Math.min(220,root.width*.30);model:stats.assemblyStyles.filter(row=>row.id!=="follow")
                value:root.selectedStyle;Accessible.name:ui.t("图鉴外观");onPicked:value=>root.selectedStyle=value}
            Check {objectName:"accessoryDemoToggle";visible:!root.gpuMode;Layout.fillWidth:true;text:ui.t("演示叶轮转动（非实测）");checked:root.demoMotion;enabled:root.visibleRotors
                onToggled:root.demoMotion=checked}
            Choice {objectName:"accessoryDemoRpm";visible:!root.gpuMode;Layout.preferredWidth:108;enabled:root.demoMotion && root.visibleRotors
                model:[600,1200,1800,2400].map(value=>({id:String(value),label:value+" RPM"}));value:String(root.demoRpm)
                Accessible.name:ui.t("参考转速");onPicked:value=>root.demoRpm=Number(value)}
        }
        GridView {
            id:grid;objectName:"accessoryModelGrid"
            visible:!root.gpuMode
            Layout.fillWidth:true;Layout.fillHeight:true
            clip:true;cacheBuffer:0
            cellWidth:width/Math.max(2,Math.floor(width/220));cellHeight:218
            model:root.gpuMode?[]:root.filtered
            onContentYChanged:root.scheduleDemand()
            onWidthChanged:root.scheduleDemand()
            onHeightChanged:root.scheduleDemand()
            onCountChanged:root.scheduleDemand()
            ScrollBar.vertical:ScrollBar {policy:ScrollBar.AsNeeded}
            delegate:Item {
                id:card
                required property var modelData
                width:grid.cellWidth;height:grid.cellHeight
                readonly property string artModelId:modelData.id
                readonly property var art:{
                    const revision=root.asyncArt?stats.accessoryArtRevision:0
                    return inViewport && root.visible?stats.accessoryModelArt(root.category,modelData.id,root.selectedStyle):({})
                }
                readonly property bool hasRotors:(art.rotors || []).length>0
                readonly property bool inViewport:visible && y+height>grid.contentY && y<grid.contentY+grid.height
                onInViewportChanged:root.scheduleDemand()
                Component.onCompleted:root.scheduleDemand()
                Component.onDestruction:root.scheduleDemand()
                Rectangle {
                    anchors.fill:parent;anchors.margins:5;radius:10
                    color:ui.dark?"#1b2a34":"#f7f9fb";border.width:1;border.color:ui.line
                    Rectangle {
                        anchors.top:parent.top;anchors.topMargin:7;anchors.horizontalCenter:parent.horizontalCenter
                        width:parent.width-14;height:144;radius:7
                        color:root.selectedStyle.indexOf('notebook_')===0?"#fbf8ed":"#edf2f4"
                        Image {
                            anchors.fill:parent;anchors.margins:1
                            visible:root.selectedStyle.indexOf('notebook_')===0
                            source:"data:image/svg+xml;charset=utf-8,"+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M16 0H0V16" fill="none" stroke="#8ba8b5" stroke-opacity=".22" stroke-width=".7"/></svg>')
                            fillMode:Image.Tile;sourceSize:Qt.size(16,16)
                            cache:true;asynchronous:false
                        }
                        AccessoryGlyph {objectName:"accessoryCardGlyph";anchors.fill:parent;anchors.margins:4
                            art:card.art;phase:root.phase;motion:root.motionActive && card.inViewport}
                        Text {anchors.centerIn:parent;visible:!!card.art.pending || !!card.art.unavailable
                            text:ui.t(card.art.unavailable?"此型号外观暂不可用":"正在准备外观…")
                            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted}
                    }
                    ColumnLayout {
                        anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:10;spacing:3
                        Text {Layout.fillWidth:true;text:card.modelData.label;textFormat:Text.PlainText;maximumLineCount:2
                            font.family:ui.fontFamily;font.pixelSize:11;color:ui.ink;wrapMode:Text.WordWrap;elide:Text.ElideRight}
                        Text {Layout.fillWidth:true;text:ui.t(card.art.pending?"正在准备外观…":card.art.unavailable?"此型号外观暂不可用":card.art.reference_details?"含参考细节":"原创比例插画")
                            font.family:ui.fontFamily;font.pixelSize:10;color:ui.muted;elide:Text.ElideRight}
                    }
                }
            }
            ColumnLayout {
                objectName:"accessoryEmptyState"
                parent:grid
                anchors.centerIn:parent;width:Math.min(parent.width-32,440);spacing:14
                visible:root.filtered.length===0
                readonly property bool needsPack:root.entries.length===0 && !["case","cooler","psu","fan"].includes(root.category)
                Text {
                    Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter
                    text:ui.t(parent.needsPack?"导入对应型号扩展包后，即可浏览这些配件。":"没有匹配的型号")
                    font.family:ui.fontFamily;font.pixelSize:13;color:ui.muted;wrapMode:Text.WordWrap
                }
                RowLayout {
                    Layout.alignment:Qt.AlignHCenter;spacing:8
                    visible:parent.needsPack
                    ActionButton {
                        objectName:"accessoryEmptyDownload";text:ui.t("前往 GitHub 下载")
                        enabled:typeof stats.openHardwarePacksDownload==="function"
                        onClicked:stats.openHardwarePacksDownload()
                    }
                    ActionButton {
                        objectName:"accessoryEmptyImport";text:ui.t("导入扩展包")
                        enabled:typeof stats.importHardwarePack==="function"
                        onClicked:stats.importHardwarePack()
                    }
                }
            }
        }
        RowLayout {
            objectName:"accessoryGpuBrowser"
            visible:root.gpuMode
            Layout.fillWidth:true;Layout.fillHeight:true;spacing:14
            ListView {
                id:gpuList;objectName:"accessoryGpuList"
                Layout.preferredWidth:Math.min(310,root.width*.34)
                Layout.fillHeight:true
                clip:true;cacheBuffer:0
                model:root.gpuMode?root.filtered:[]
                ScrollBar.vertical:ScrollBar {policy:ScrollBar.AsNeeded}
                delegate:ItemDelegate {
                    required property var modelData
                    objectName:"accessoryGpuRow_"+modelData.id
                    width:gpuList.width;implicitHeight:58
                    highlighted:root.selectedGpuId===modelData.id
                    Accessible.name:modelData.label
                    contentItem:Text {
                        text:modelData.label;textFormat:Text.PlainText
                        font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink
                        wrapMode:Text.WordWrap;maximumLineCount:2;elide:Text.ElideRight
                        verticalAlignment:Text.AlignVCenter
                    }
                    background:Rectangle {
                        radius:ui.controlRadius
                        color:parent.highlighted?ui.selection:parent.hovered?ui.hover:"transparent"
                    }
                    onClicked:root.selectedGpuId=modelData.id
                }
                Text {
                    anchors.centerIn:parent;visible:root.filtered.length===0
                    text:ui.t("没有匹配的型号");font.family:ui.fontFamily
                    font.pixelSize:12;color:ui.muted
                }
            }
            Rectangle {
                Layout.fillWidth:true;Layout.fillHeight:true
                radius:10;color:ui.dark?"#1b2a34":"#f7f9fb";border.color:ui.line
                ColumnLayout {
                    anchors.fill:parent;anchors.margins:16;spacing:10
                    Text {
                        objectName:"accessoryGpuSelectedLabel"
                        Layout.fillWidth:true;text:root.gpuReference.label || ""
                        textFormat:Text.PlainText;font.family:ui.fontFamily
                        font.pixelSize:16;font.weight:Font.DemiBold;color:ui.ink
                        wrapMode:Text.WordWrap
                    }
                    Item {
                        Layout.fillWidth:true;Layout.fillHeight:true
                        Loader {
                            objectName:"accessoryGpuPreviewLoader"
                            anchors.fill:parent
                            active:root.visible && root.ownerActive && root.gpuMode
                                && root.gpuPreviewReady && root.gpuReference.id===root.selectedGpuId
                            sourceComponent:HardwareGlyph {
                                objectName:"accessoryGpuPreviewGlyph"
                                appearance:Object.assign({},root.gpuReference.appearance,{icon_set:root.selectedStyle})
                                modelMode:true;cacheArtwork:false
                                fanMotionEnabled:false;fanRotation:0
                            }
                        }
                        Text {
                            anchors.centerIn:parent
                            visible:!root.gpuPreviewReady
                            text:ui.t(root.gpuReference.unavailable?"此型号外观暂不可用":root.selectedGpuId?"正在准备外观…":"请选择型号")
                            font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted
                        }
                    }
                    Text {
                        objectName:"accessoryGpuQualityNote"
                        Layout.fillWidth:true;text:ui.t("参考型号 · 静态预览 · 部分细节待核")
                        font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap
                    }
                }
            }
        }
        Text {objectName:"accessoryStandaloneNote";Layout.fillWidth:true;visible:root.category==="gpu_block"
            text:ui.t("独立外观检视；显卡安装与连管尚未验证。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
        Text {objectName:"accessoryRadiatorNote";Layout.fillWidth:true;visible:root.category==="radiator"
            text:ui.t("冷排本体；风扇和接头需单独选择，安装容量不代表已装数量。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
        Text {Layout.fillWidth:true;text:ui.t(root.gpuMode?"二维外观参考":"参考插画；演示以转速的 1/120 播放，不绑定本机测速。")
            font.family:ui.fontFamily;font.pixelSize:10;color:ui.muted;wrapMode:Text.WordWrap}
    }
}
