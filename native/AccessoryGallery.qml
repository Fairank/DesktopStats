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
    readonly property string catalogKey:({case:"cases",cooler:"coolers",psu:"psus",fan:"fans"})[category]
    readonly property var entries:library[catalogKey] || []
    readonly property var brands:[{id:"",label:ui.t("全部品牌")}].concat([...new Set(entries.map(row=>row.brand).filter(Boolean))].sort().map(value=>({id:value,label:value})))
    readonly property var filtered:entries.filter(row=>(!brand||row.brand===brand)&&(!query||((row.label||"")+" "+(row.brand||"")).toLowerCase().includes(query.toLowerCase())))
    readonly property bool visibleRotors: !!grid.contentItem && grid.contentItem.children.some(item=>item.visible && item.hasRotors===true && item.y+item.height>grid.contentY && item.y<grid.contentY+grid.height)
    readonly property bool motionActive:visible && ownerActive && demoMotion && demoRpm>0 && visibleRotors
    parent:Overlay.overlay
    anchors.centerIn:parent
    width:Math.min(1020,parent?parent.width-36:980)
    height:Math.min(760,parent?parent.height-44:700)
    padding:20;modal:true;focus:true
    closePolicy:Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Theme {id:ui}
    background:GlassSurface {tone:"window";radius:18}
    onAboutToShow:{stats.setAccessoryGalleryActive(true);selectedStyle=initialStyle;library=stats.accessoryCatalog}
    onClosed:{demoMotion=false;library=({});stats.setAccessoryGalleryActive(false)}
    onOwnerActiveChanged:if(!ownerActive)close()
    Component.onDestruction:if(typeof stats!=="undefined" && stats)stats.setAccessoryGalleryActive(false)
    onCategoryChanged:{brand="";grid.positionViewAtBeginning()}
    onFilteredChanged:grid.positionViewAtBeginning()
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
            ActionButton {objectName:"accessoryDownload";text:ui.t("下载 SVG 图集");quiet:true;onClicked:stats.downloadAccessoryArt(root.category)
                ToolTip.visible:hovered;ToolTip.text:ui.t("应用已自带这些外观；下载的是独立 SVG 图集。")}
            IconButton {objectName:"closeAccessoryGallery";symbol:"close";label:ui.t("关闭");onClicked:root.close()}
        }
        Text {Layout.fillWidth:true;text:ui.t("按型号浏览二维外观；切换图鉴不会改动装机和顶部栏设置。")
            font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
        Flow {
            Layout.fillWidth:true;spacing:6
            Repeater {
                model:[{id:"case",key:"cases",label:ui.t("机箱")},{id:"cooler",key:"coolers",label:ui.t("CPU 散热器")},
                       {id:"psu",key:"psus",label:ui.t("电源")},{id:"fan",key:"fans",label:ui.t("机箱风扇")}]
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
            Check {objectName:"accessoryDemoToggle";Layout.fillWidth:true;text:ui.t("演示叶轮转动（非实测）");checked:root.demoMotion;enabled:root.visibleRotors
                onToggled:root.demoMotion=checked}
            Choice {objectName:"accessoryDemoRpm";Layout.preferredWidth:108;enabled:root.demoMotion && root.visibleRotors
                model:[600,1200,1800,2400].map(value=>({id:String(value),label:value+" RPM"}));value:String(root.demoRpm)
                Accessible.name:ui.t("参考转速");onPicked:value=>root.demoRpm=Number(value)}
        }
        GridView {
            id:grid;objectName:"accessoryModelGrid"
            Layout.fillWidth:true;Layout.fillHeight:true
            clip:true;cacheBuffer:0
            cellWidth:width/Math.max(2,Math.floor(width/220));cellHeight:218
            model:root.filtered
            ScrollBar.vertical:ScrollBar {policy:ScrollBar.AsNeeded}
            delegate:Item {
                id:card
                required property var modelData
                width:grid.cellWidth;height:grid.cellHeight
                readonly property var art:stats.accessoryModelArt(root.category,modelData.id,root.selectedStyle)
                readonly property bool hasRotors:(art.rotors || []).length>0
                Rectangle {
                    anchors.fill:parent;anchors.margins:5;radius:10
                    color:ui.dark?"#1b2a34":"#f7f9fb";border.width:1;border.color:ui.line
                    Rectangle {
                        anchors.top:parent.top;anchors.topMargin:7;anchors.horizontalCenter:parent.horizontalCenter
                        width:parent.width-14;height:144;radius:7
                        color:root.selectedStyle.indexOf('notebook_')===0?"#fbf8ed":"#edf2f4"
                        AccessoryGlyph {objectName:"accessoryCardGlyph";anchors.fill:parent;anchors.margins:4
                            art:card.art;phase:root.phase;motion:root.motionActive}
                    }
                    ColumnLayout {
                        anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:10;spacing:3
                        Text {Layout.fillWidth:true;text:card.modelData.label;textFormat:Text.PlainText;maximumLineCount:2
                            font.family:ui.fontFamily;font.pixelSize:11;color:ui.ink;wrapMode:Text.WordWrap;elide:Text.ElideRight}
                        Text {Layout.fillWidth:true;text:ui.t(card.art.reference_details?"含参考细节":"原创比例插画")
                            font.family:ui.fontFamily;font.pixelSize:10;color:ui.muted;elide:Text.ElideRight}
                    }
                }
            }
            Text {anchors.centerIn:parent;visible:root.filtered.length===0;text:ui.t("没有匹配的型号")
                font.family:ui.fontFamily;font.pixelSize:13;color:ui.muted}
        }
        Text {Layout.fillWidth:true;text:ui.t("参考插画；演示以转速的 1/120 播放，不绑定本机测速。")
            font.family:ui.fontFamily;font.pixelSize:10;color:ui.muted;wrapMode:Text.WordWrap}
    }
}
