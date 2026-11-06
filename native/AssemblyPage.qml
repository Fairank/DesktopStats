import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ScrollView {
    id: root
    property bool active: false
    property var config: stats.draft.assembly || ({case_model:"",exploded:false,fan_animation:false,appearance_style:"follow"})
    readonly property var info: stats.assemblySummary || ({initialized:false})
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
    ColumnLayout {
        width: root.availableWidth
        spacing: 22
        RowLayout {
            Layout.fillWidth:true;spacing:16
            Text {Layout.fillWidth:true;text:ui.t("整机视图");font.family:ui.fontFamily;font.pixelSize:25;font.weight:Font.DemiBold;color:ui.ink;elide:Text.ElideRight}
            ActionButton {
                objectName:"openAssemblyViewButton"
                text:ui.t("打开三维视图");accent:true;enabled:root.active&&root.info.initialized===true
                onClicked:stats.openAssemblyView()
            }
        }
        Text {
            Layout.fillWidth:true
            text:ui.t("按已识别的组件查看可旋转的三维布局。")
            font.family:ui.fontFamily;font.pixelSize:13;color:ui.muted;wrapMode:Text.WordWrap
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
                       {label:ui.t("主板"),value:root.info.board_label || "—"}]
                RowLayout {
                    required property var modelData
                    Layout.fillWidth:true;spacing:18
                    Text {Layout.preferredWidth:Math.min(110,root.availableWidth*.24);Layout.alignment:Qt.AlignTop;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Text {Layout.fillWidth:true;Layout.alignment:Qt.AlignTop;text:ui.t(modelData.value);textFormat:Text.PlainText;font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;wrapMode:Text.WordWrap}
                }
            }
        }
        SettingsGroup {
            Layout.fillWidth:true;title:ui.t("查看方式")
            SettingRow {id:assemblyStyleSetting;Layout.fillWidth:true;label:ui.t("整机外观");note:ui.t("默认跟随顶部栏，也可单独选择。")
                Choice {objectName:"assemblyStyleChoice";width:Math.min(220,Math.max(150,assemblyStyleSetting.width*.42))
                    model:stats.assemblyStyles;value:root.config.appearance_style || "follow"
                    Accessible.name:ui.t("整机外观");onPicked:selected=>stats.changeAssembly("appearance_style",selected)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("展开组件");note:ui.t("将硬件分开，查看机箱内部布局。")
                Toggle {checked:root.config.exploded===true;onToggled:stats.changeAssembly("exploded",checked)}}
            SettingRow {Layout.fillWidth:true;label:ui.t("风扇随转速转动");note:ui.t("仅在三维视图可见且转速有效时运行。")
                Toggle {checked:root.config.fan_animation===true;onToggled:stats.changeAssembly("fan_animation",checked)}}
        }
        Text {
            Layout.fillWidth:true
            text:ui.t("模型为比例示意，不能代替实物安装检查。未知部件会保留标记；关闭视图后释放三维渲染资源。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap;lineHeight:1.3
        }
        Item {Layout.preferredHeight:8}
    }
}
