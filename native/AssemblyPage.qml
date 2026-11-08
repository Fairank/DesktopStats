import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ScrollView {
    id: root
    property bool active: false
    signal browseModelsRequested()
    property var config: stats.draft.assembly || ({case_model:"",exploded:false,fan_animation:false,appearance_style:"follow"})
    readonly property var info: stats.assemblySummary || ({initialized:false})
    readonly property var partCatalog: assemblyParts.catalog
    readonly property int independentStyles: Object.keys(root.config.part_styles || ({})).length
    property string brandFilter: ""
    readonly property var allCases: stats.assemblyCases
    readonly property var brandChoices: {
        const brands=[]
        for(const row of allCases)if(row.brand&&brands.indexOf(row.brand)<0)brands.push(row.brand)
        brands.sort((a,b)=>a.localeCompare(b))
        return [{id:"",label:ui.t("全部品牌")}].concat(brands.map(brand=>({id:brand,label:brand})))
    }
    readonly property var filteredCases: allCases.filter(row=>!row.id||!brandFilter||row.brand===brandFilter)
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    Theme { id: ui }
    function showExample(kind) {
        stats.useAssemblyReference(kind)
        stats.openAssemblyView()
    }
    ColumnLayout {
        width: root.availableWidth
        spacing: 22
        RowLayout {
            Layout.fillWidth:true;spacing:16
            Text {Layout.fillWidth:true;text:ui.t("整机视图");font.family:ui.fontFamily;font.pixelSize:25;font.weight:Font.DemiBold;color:ui.ink;elide:Text.ElideRight}
            ActionButton {
                objectName:"openAssemblyDesktopButton"
                text:ui.t("放到桌面");accent:true;enabled:root.active&&root.info.initialized===true
                onClicked:stats.openAssemblyDesktop()
            }
            ActionButton {
                objectName:"openAssemblyViewButton"
                text:ui.t("打开三维视图");enabled:root.active&&root.info.initialized===true
                onClicked:stats.openAssemblyView()
            }
        }
        SettingsGroup {
            objectName:"assemblyAppearanceOverview"
            Layout.fillWidth:true;title:ui.t("硬件模型与外观");spacing:8
            note:ui.t("机箱、散热器、电源与风扇均支持全部外观。")
            Flow {
                objectName:"assemblyCatalogCounts"
                Layout.fillWidth:true;spacing:16
                Repeater {
                    model:[{key:"cases",label:ui.t("机箱"),count:root.allCases.filter(row=>!!row.id).length},
                           {key:"coolers",label:ui.t("CPU 散热器"),count:(root.partCatalog.coolers || []).filter(row=>!!row.id).length},
                           {key:"psus",label:ui.t("电源"),count:(root.partCatalog.psus || []).filter(row=>!!row.id).length},
                           {key:"fans",label:ui.t("机箱风扇"),count:(root.partCatalog.fans || []).filter(row=>!!row.id).length}]
                    Text {
                        required property var modelData
                        objectName:"assemblyCatalogCount_"+modelData.key
                        property int modelCount:modelData.count
                        text:modelData.label+" · "+modelData.count
                        font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted
                    }
                }
            }
            RowLayout {
                Layout.fillWidth:true;spacing:12
                Text {Layout.preferredWidth:88;text:ui.t("整机外观");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                Choice {objectName:"assemblyStyleChoice";Layout.fillWidth:true
                    model:stats.assemblyStyles;value:root.config.appearance_style || "follow"
                    Accessible.name:ui.t("整机外观");onPicked:selected=>stats.changeAssembly("appearance_style",selected)}
            }
            RowLayout {
                Layout.fillWidth:true;spacing:12
                ActionButton {
                    objectName:"assemblyResetPartStyles"
                    text:ui.t("统一应用此风格");enabled:root.independentStyles>0
                    onClicked:stats.resetAssemblyPartStyles()
                }
                Text {
                    objectName:"assemblyIndependentStyles"
                    Layout.fillWidth:true
                    text:ui.t("独立外观设置")+" · "+root.independentStyles
                    font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap
                }
            }
            Flow {
                Layout.fillWidth:true;spacing:8
                ActionButton {objectName:"browseAssemblyModelsButton";text:ui.t("浏览全部型号与外观");accent:true
                    enabled:root.active;onClicked:root.browseModelsRequested()}
                ActionButton {objectName:"assemblyExample_air";text:ui.t("风冷配件示例")
                    enabled:root.active&&root.info.initialized===true;onClicked:root.showExample("air")}
                ActionButton {objectName:"assemblyExample_aio";text:ui.t("一体水冷配件示例")
                    enabled:root.active&&root.info.initialized===true;onClicked:root.showExample("aio")}
                ActionButton {objectName:"assemblyExample_loop";text:ui.t("分体水冷配件示例")
                    enabled:root.active&&root.info.initialized===true;onClicked:root.showExample("loop")}
            }
            Text {
                objectName:"assemblyExamplesNote"
                Layout.fillWidth:true
                text:ui.t("载入主要配件齐全的参考方案，不代表已识别的本机硬件。")
                font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap;lineHeight:1.2
            }
        }
        SettingsGroup {
            objectName:"assemblyWindowModeGroup"
            Layout.fillWidth:true;title:ui.t("桌面显示")
            note:ui.t("将整机模型放到桌面，点击部件查看真实状态；也可保留完整检视窗口。")
            RowLayout {
                Layout.fillWidth:true;spacing:12
                Text {Layout.preferredWidth:88;text:ui.t("查看方式");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted}
                Choice {
                    objectName:"assemblyWindowModeChoice";Layout.fillWidth:true
                    model:[{id:"inspect",label:ui.t("完整检视窗口")},{id:"desktop",label:ui.t("桌面小组件")}]
                    value:root.config.window_mode || "inspect"
                    Accessible.name:ui.t("查看方式");onPicked:selected=>stats.changeAssembly("window_mode",selected)
                }
            }
            SettingRow {
                Layout.fillWidth:true;label:ui.t("小组件边框");note:ui.t("关闭后仅保留模型与紧凑读数，背景透明。")
                Toggle {objectName:"assemblyDesktopFrameToggle";checked:root.config.desktop_frame!==false
                    onToggled:stats.changeAssembly("desktop_frame",checked)}
            }
            ActionButton {objectName:"openAssemblyInspectButton";text:ui.t("完整检视")
                enabled:root.active&&root.info.initialized===true;onClicked:stats.openAssemblyInspect()}
            Text {
                Layout.fillWidth:true
                text:ui.t("桌面小组件不置顶、不抢焦点。拖动模型旋转，滚轮缩放；按住 Alt 拖动移动位置，右键打开菜单。")
                font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap
            }
        }
        SettingsGroup {
            Layout.fillWidth:true;title:ui.t("机箱外观")
            note:root.info.identity_state==="manual"?ui.t("已手动选择图示，系统识别结果保持原样。")
                :root.info.identity_state==="automatic"?ui.t("已按机箱固件标识匹配。")
                :ui.t("系统没有提供具体机箱型号。可选择外观，或先使用参考机箱。")
            RowLayout {
                Layout.fillWidth:true;spacing:12
                Text {Layout.preferredWidth:88;text:ui.t("品牌筛选");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                Choice {objectName:"assemblyBrandChoice";Layout.fillWidth:true;model:root.brandChoices;value:root.brandFilter
                    Accessible.name:ui.t("品牌筛选");onPicked:selected=>root.brandFilter=selected}
            }
            Choice {
                objectName:"assemblyCaseChoice";Layout.fillWidth:true
                model:root.filteredCases;value:root.config.case_model || ""
                displayText:(root.allCases.find(row=>row.id===(root.config.case_model || "")) || {}).label || ""
                Accessible.name:ui.t("机箱外观")
                onPicked:selected=>stats.changeAssembly("case_model",selected)
            }
            Text {
                Layout.fillWidth:true;text:ui.t("当前目录")+" · "+Math.max(0,stats.assemblyCases.length-1)+" "+ui.t("款机箱")
                font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap
            }
            Text {
                Layout.fillWidth:true
                text:{
                    const mount=(root.info.checks || []).find(row=>row.kind==="gpu_mount"&&row.state==="unsupported")
                    if(mount)return ui.t(mount.reason==="low_profile"?"机箱仅支持半高扩展卡。":"机箱不支持独立显卡安装。")
                    const check=(root.info.checks || []).find(row=>row.kind==="gpu_length")
                    if(!check || check.state==="unknown")return ui.t("显卡长度空间尚未核实。")
                    return ui.t("显卡长度")+" "+check.component_mm+" mm · "+ui.t("机箱参考限值")+" "+check.limit_mm+" mm"
                        +(check.state==="exceeds_limit"?" · "+ui.t("已超出参考限值"):"")
                }
                font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap
            }
        }
        InspectorSection {
            Layout.fillWidth:true;title:ui.t("硬件组成")
            Repeater {
                model:[{label:ui.t("处理器"),value:root.info.cpu_label || "—"},
                       {label:ui.t("显卡"),value:(root.info.gpu_label || "—")+(root.info.gpu_source==="manual"?" · "+ui.t("手动外观"):"")},
                       {label:ui.t("内存"),value:(root.info.memory_label || "—")+" · "+(root.info.memory_count || 0)+" "+ui.t("条")},
                       {label:ui.t("主板"),value:(root.info.board_label || "—")+(root.info.board_source==="manual"?" · "+ui.t("手动外观"):"")}]
                RowLayout {
                    required property var modelData
                    Layout.fillWidth:true;spacing:18
                    Text {Layout.preferredWidth:Math.min(110,root.availableWidth*.24);Layout.alignment:Qt.AlignTop;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Text {Layout.fillWidth:true;Layout.alignment:Qt.AlignTop;text:ui.t(modelData.value);textFormat:Text.PlainText;font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;wrapMode:Text.WordWrap}
                }
            }
        }
        AssemblyParts {id:assemblyParts;Layout.fillWidth:true;config:root.config;caseInfo:root.info}
        HardwarePacks {Layout.fillWidth:true}
        SettingsGroup {
            Layout.fillWidth:true;title:ui.t("查看方式")
            SettingRow {id:assemblyDetailSetting;Layout.fillWidth:true;label:ui.t("模型细节");note:ui.t("精细适合日常查看，近看细节用于局部观察。")
                Choice {objectName:"assemblyDetailChoice";width:Math.min(220,Math.max(150,assemblyDetailSetting.width*.42))
                    model:stats.assemblyDetails;value:root.config.detail_level || "balanced"
                    Accessible.name:ui.t("模型细节");onPicked:selected=>stats.changeAssembly("detail_level",selected)}}
            SettingRow {id:lightingSetting;Layout.fillWidth:true;label:ui.t("灯区预览");note:ui.t("只调整模型已有灯区，静态显示；不控制设备灯光。")
                Choice {objectName:"assemblyLightingChoice";width:Math.min(220,Math.max(150,lightingSetting.width*.42))
                    model:[{id:"artwork",label:ui.t("沿用插画")},{id:"off",label:ui.t("熄灯")},
                           {id:"warm",label:ui.t("暖白")},{id:"mint",label:ui.t("薄荷")},{id:"violet",label:ui.t("紫色")}]
                    value:root.config.lighting_preview || "artwork";Accessible.name:ui.t("灯区预览")
                    onPicked:selected=>stats.changeAssembly("lighting_preview",selected)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("展开组件");note:ui.t("将硬件分开，查看机箱内部布局。")
                Toggle {checked:root.config.exploded===true;onToggled:stats.changeAssembly("exploded",checked)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("内部检视");note:ui.t("隐藏外盖与电源罩以查看内部，保留完整硬件与安装检查。")
                Toggle {objectName:"assemblyInspectionCutawayToggle";checked:root.config.inspection_cutaway===true
                    onToggled:stats.changeAssembly("inspection_cutaway",checked)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("风扇随转速转动");note:ui.t("仅在三维视图可见且转速有效时运行。")
                Toggle {checked:root.config.fan_animation===true;onToggled:stats.changeAssembly("fan_animation",checked)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("风格特效");note:ui.t("选择部件时短暂播放，结束后停止。")
                Toggle {checked:root.config.selection_effects!==false;onToggled:stats.changeAssembly("selection_effects",checked)}}
        }
        Text {
            Layout.fillWidth:true
            text:ui.t("模型为比例示意，不能代替实物安装检查。未知部件会保留标记；关闭视图后释放三维渲染资源。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap;lineHeight:1.3
        }
        Item {Layout.preferredHeight:8}
    }
}
