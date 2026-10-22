import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    readonly property var config: stats.draft
    readonly property bool twoColumns: body.width >= 430
    readonly property int skinOverrides: root.config.widget_order.filter(function(key) { const prefs=root.config.widgets[key]; return prefs && !!prefs.skin }).length
    implicitHeight: body.implicitHeight
    Theme { id: ui }

    ColumnLayout {
        id: body
        width: Math.min(root.width, 620)
        x: (root.width-width)/2
        spacing: 24
        RowLayout {
            Layout.fillWidth: true; spacing: 14
            Text { text:ui.t("布局预设"); color:ui.ink; font.family:ui.fontFamily; font.pixelSize:12; font.weight:Font.Medium }
            Choice { Layout.preferredWidth:Math.min(250,body.width*.65); model:[{id:"",label:ui.t("选择布局模板")}].concat(stats.catalog.presets); value:""; onPicked:function(selected){if(selected)stats.preset(selected);currentIndex=0} }
            Item { Layout.fillWidth:true }
        }
        InspectorSection {
            Layout.fillWidth: true; title:ui.t("材质与颜色")
            SkinPicker { objectName:"globalSkinPicker"; Layout.fillWidth:true;compact:true;value:root.config.skin; onPicked:selected=>stats.change("skin",selected) }
            RowLayout {
                visible:root.skinOverrides>0; Layout.fillWidth:true; spacing:12
                Text { Layout.fillWidth:true; text:root.skinOverrides+" "+ui.t("个组件使用单独皮肤"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap }
                ActionButton { objectName:"useGlobalSkinButton"; text:ui.t("全部跟随全局"); quiet:true; implicitHeight:30; onClicked:stats.useGlobalSkin() }
            }
            Text { Layout.fillWidth:true; text:ui.t("玻璃默认参数"); color:ui.ink; font.family:ui.fontFamily; font.pixelSize:12; font.weight:Font.Medium }
            GridLayout {
                Layout.fillWidth:true; columns:root.twoColumns?2:1; uniformCellWidths:true; columnSpacing:24; rowSpacing:12
                Repeater {
                    model:[{field:"glass_transparency",label:"玻璃透明度"},{field:"glass_curvature",label:"圆角曲率"}]
                    ColumnLayout {
                        id:glassDefault; required property var modelData
                        objectName:"glassControl_global_"+modelData.field
                        Layout.fillWidth:true; spacing:3
                        RowLayout {
                            Layout.fillWidth:true; spacing:8
                            Text { Layout.fillWidth:true; text:ui.t(glassDefault.modelData.label); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:12 }
                            Text { text:Number(root.config[glassDefault.modelData.field]).toLocaleString(Qt.locale(stats.language),"f",1)+"%"; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11 }
                        }
                        ValueSlider { objectName:"global_"+glassDefault.modelData.field; Layout.fillWidth:true; from:0; to:100; stepSize:.1; value:root.config[glassDefault.modelData.field]; Accessible.name:ui.t(glassDefault.modelData.label); onMoved:stats.change(glassDefault.modelData.field,value) }
                    }
                }
            }
            Text { objectName:"globalGlassDefaultsNote"; Layout.fillWidth:true; text:ui.t("默认参数仅作用于使用玻璃皮肤的组件。"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap }
        }
        InspectorSection {
            Layout.fillWidth:true; title:ui.t("排列与大小")
            GridLayout {
                Layout.fillWidth:true; columns:root.twoColumns?2:1; uniformCellWidths:true; columnSpacing:24; rowSpacing:14
                FormField { Layout.fillWidth:true; label:ui.t("组件形态"); Choice { Layout.fillWidth:true; model:[{id:"separate",label:ui.t("独立")},{id:"combined",label:ui.t("组合")},{id:"mixed",label:ui.t("混合")}]; value:root.config.mode; onPicked:selected=>stats.change("mode",selected) } }
                FormField { Layout.fillWidth:true; label:ui.t("独立排列"); Choice { Layout.fillWidth:true; model:[{id:"grid",label:ui.t("自适应网格")},{id:"row",label:ui.t("横排")},{id:"column",label:ui.t("竖排")}]; value:root.config.layout; onPicked:selected=>stats.change("layout",selected) } }
                FormField { visible:root.config.mode!=="separate"; Layout.fillWidth:true; label:ui.t("组合列数"); Choice { Layout.fillWidth:true; model:[{id:1,label:"1"},{id:2,label:"2"},{id:3,label:"3"}]; value:root.config.group_columns; onPicked:selected=>stats.change("group_columns",selected) } }
                FormField {
                    Layout.fillWidth:true; label:ui.t("全局组件大小")
                    RowLayout {
                        Layout.fillWidth:true; spacing:10
                        ValueSlider { Layout.fillWidth:true; from:76; to:180; stepSize:1; value:root.config.size; Accessible.name:ui.t("全局组件大小"); onMoved:stats.change("size",Math.round(value)) }
                        Text { text:Math.round(root.config.size*1.5)+" px"; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11 }
                    }
                }
            }
            GridLayout {
                Layout.fillWidth:true; columns:root.twoColumns?2:1; uniformCellWidths:true; columnSpacing:24; rowSpacing:7
                SettingRow { objectName:"reflowSettingRow"; Layout.fillWidth:true; label:ui.t("缩放后自动排列"); Toggle { objectName:"reflowOnResizeToggle"; checked:root.config.reflow_on_resize; Accessible.name:ui.t("缩放后自动排列"); onToggled:stats.change("reflow_on_resize",checked) } }
                SettingRow { objectName:"magnetEnabledSettingRow"; Layout.fillWidth:true; label:ui.t("磁吸避让"); Toggle { objectName:"magnetEnabledToggle"; checked:root.config.magnet_enabled; Accessible.name:ui.t("磁吸避让"); onToggled:stats.change("magnet_enabled",checked) } }
                FormField {
                    Layout.fillWidth:true; label:ui.t("组件间距")
                    RowLayout {
                        Layout.fillWidth:true; spacing:10
                        ValueSlider { objectName:"magnetGapSlider"; Layout.fillWidth:true; from:0; to:64; stepSize:1; enabled:root.config.magnet_enabled; opacity:enabled?1:.45; value:root.config.magnet_gap; Accessible.name:ui.t("组件间距"); onMoved:stats.change("magnet_gap",Math.round(value)) }
                        Text { text:root.config.magnet_gap+" px"; color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11 }
                    }
                }
                SettingRow { objectName:"magnetBounceSettingRow"; Layout.fillWidth:true; label:ui.t("回弹动画"); Toggle { objectName:"magnetBounceToggle"; enabled:root.config.magnet_enabled; opacity:enabled?1:.45; checked:root.config.magnet_bounce; Accessible.name:ui.t("回弹动画"); onToggled:stats.change("magnet_bounce",checked) } }
            }
            Text { Layout.fillWidth:true; text:ui.t("避免组件相互重叠。松手后按设定间距落位。"); color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap }
        }
        InspectorSection {
            Layout.fillWidth:true; title:ui.t("行为")
            GridLayout {
                Layout.fillWidth:true; columns:root.twoColumns?2:1; uniformCellWidths:true; columnSpacing:24; rowSpacing:7
                SettingRow { Layout.fillWidth:true; label:ui.t("显示桌面组件"); Toggle { checked:root.config.visible; Accessible.name:ui.t("显示桌面组件"); onToggled:stats.change("visible",checked) } }
                SettingRow { Layout.fillWidth:true; label:ui.t("锁定桌面位置"); Toggle { checked:root.config.locked; Accessible.name:ui.t("锁定桌面位置"); onToggled:stats.change("locked",checked) } }
            }
        }
        ActionButton {objectName:"rearrangeButton";text:ui.t("应用并排列");quiet:true;onClicked:stats.rearrangeDesktop()}
    }
}
