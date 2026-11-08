import QtQuick
import QtQuick.Layouts
ColumnLayout {
    id: root
    property var config: ({})
    property var caseInfo: ({})
    readonly property var catalog: stats.assemblyParts || ({})
    property string gpuBrand: ""
    property string gpuSeries: ""
    readonly property var gpuBrands: [{id:"",label:ui.t("全部品牌")}].concat([...new Set((catalog.gpus || []).map(row=>row.brand).filter(Boolean))].sort().map(brand=>({id:brand,label:brand})))
    readonly property var gpuSeriesRows: {
        const rows=[],seen=new Set()
        for(const row of catalog.gpus || [])if(row.series_id&&(!gpuBrand||row.brand===gpuBrand)&&!seen.has(row.series_id)) {
            seen.add(row.series_id);rows.push({id:row.series_id,label:row.series_label})
        }
        rows.sort((a,b)=>a.label.localeCompare(b.label))
        return [{id:"",label:ui.t("全部系列")}].concat(rows)
    }
    readonly property var filteredGpus: (catalog.gpus || []).filter(row=>!row.id||(!gpuBrand||row.brand===gpuBrand)&&(!gpuSeries||row.series_id===gpuSeries))
    readonly property var counts: [1,2,3,4].map(n=>({id:String(n),label:String(n)}))
    readonly property string coolerKind: ((catalog.coolers || []).find(row=>row.id===config.cooler_model) || {}).kind || ""
    spacing: 18
    Theme { id: ui }
    function fan(mount) {return (config.case_fans || []).find(row=>row.mount===mount) || ({model:"",count:1,direction:mount==="top"||mount==="rear"?"exhaust":"intake"})}
    function radiatorFanSize(prefix) {
        const radiator=(root.catalog.radiators || []).find(row=>row.id===root.config[prefix+"radiator_model"])
        const cooler=(root.catalog.coolers || []).find(row=>row.id===root.config.cooler_model)
        return root.coolerKind==="custom_loop"&&radiator&&radiator.id?radiator.fan_size_mm:(cooler || {}).fan_size_mm
    }
    function radiatorFanFits(prefix,fan) {
        if(!fan||!fan.id)return true
        return fan.size_mm===radiatorFanSize(prefix)&&fan.frame!=="round"&&!fan.frameless
    }
    function radiatorMountReview(prefix) {
        const radiator=root.coolerKind==="custom_loop"?(root.catalog.radiators || []).find(row=>row.id===root.config[prefix+"radiator_model"]):null
        const fan=(root.catalog.radiator_fans || []).find(row=>row.id===root.config[prefix+"radiator_fan_model"])
        return root.config[prefix+"radiator_fan_layout"]!=="none"&&radiator&&fan&&radiator.fan_mount_pitch_mm&&fan.mount_pitch_verified&&Math.abs(radiator.fan_mount_pitch_mm-fan.mount_pitch_mm)>0.05
    }
    function radiatorFansFor(prefix) {
        return (root.catalog.radiator_fans || []).filter(row=>radiatorFanFits(prefix,row)||row.id===root.config[prefix+"radiator_fan_model"])
    }
    function radiatorFanConflict(prefix) {
        const fan=(root.catalog.radiator_fans || []).find(row=>row.id===root.config[prefix+"radiator_fan_model"])
        return root.config[prefix+"radiator_fan_layout"]!=="none"&&((root.config[prefix+"radiator_fan_model"]&&!fan)||!radiatorFanFits(prefix,fan))
    }
    function chooseGpuBrand(value) {gpuSeries="";gpuBrand=value}
    function changeFan(mount,key,value) {const row=Object.assign({},fan(mount));row[key]=value;stats.changeAssemblyFan(mount,row.model,Number(row.count),row.direction)}
    function fansFor(mount) {
        const caps=caseInfo.fan_mounts || []
        if(!caps.length)return root.catalog.fans || []
        return (root.catalog.fans || []).filter(row=>!row.id || caps.some(cap=>cap.position===mount&&(cap.size_mm || []).indexOf(row.size_mm)>=0))
    }
    function countsFor(mount,model) {
        const caps=caseInfo.fan_mounts || [],fan=(root.catalog.fans || []).find(row=>row.id===model)
        if(!caps.length||!fan)return root.counts
        const max=caps.filter(cap=>cap.position===mount&&(cap.size_mm || []).indexOf(fan.size_mm)>=0).reduce((n,row)=>Math.max(n,row.count),0)
        return root.counts.filter(row=>Number(row.id)<=max)
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("配件与安装")
        note:ui.t("选择参考型号补全装机外观，不会把自选模型当作系统识别结果。")
        Repeater {
            model:[{key:"cpu_model",label:ui.t("处理器"),rows:root.catalog.cpus || []},
                   {key:"gpu_model",label:ui.t("显卡"),rows:root.filteredGpus}]
            ColumnLayout {
                required property var modelData
                Layout.fillWidth:true;spacing:8
                RowLayout {
                    Layout.fillWidth:true;spacing:8;visible:modelData.key==="gpu_model"
                    Choice {objectName:"assemblyGpuBrandFilter";Layout.fillWidth:true;model:root.gpuBrands;value:root.gpuBrand
                        Accessible.name:ui.t("品牌筛选");onPicked:selected=>root.chooseGpuBrand(selected)}
                    Choice {objectName:"assemblyGpuSeriesFilter";Layout.fillWidth:true;model:root.gpuSeriesRows;value:root.gpuSeries
                        Accessible.name:ui.t("系列筛选");onPicked:selected=>root.gpuSeries=selected}
                }
                RowLayout {
                    Layout.fillWidth:true;spacing:12
                    Text {Layout.preferredWidth:90;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Choice {objectName:"assemblyReference_"+modelData.key;Layout.fillWidth:true;model:modelData.rows;value:root.config[modelData.key] || ""
                        displayText:((modelData.key==="gpu_model"?root.catalog.gpus:root.catalog.cpus).find(row=>row.id===(root.config[modelData.key] || "")) || {}).label || ""
                        Accessible.name:modelData.label;onPicked:selected=>stats.changeAssembly(modelData.key,selected)}
                }
            }
        }
        Text {Layout.fillWidth:true;text:ui.t("更换参考 CPU、显卡或内存后，不将本机实时读数用于该模型。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.preferredWidth:90;text:ui.t("主板型号");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
            Choice {objectName:"assemblyBoardChoice";Layout.fillWidth:true;model:root.catalog.boards || [];value:root.config.board_model || ""
                Accessible.name:ui.t("主板型号");onPicked:selected=>stats.changeAssembly("board_model",selected)}
        }
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.preferredWidth:90;text:ui.t("CPU 散热器");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
            Choice {objectName:"assemblyCoolerChoice";Layout.fillWidth:true;model:root.catalog.coolers || [];value:root.config.cooler_model || ""
                Accessible.name:ui.t("CPU 散热器");onPicked:selected=>stats.changeAssembly("cooler_model",selected)}
        }
        RowLayout {
            Layout.fillWidth:true;spacing:12;visible:root.coolerKind==="aio"||root.coolerKind==="custom_loop"
            Text {Layout.preferredWidth:90;text:ui.t("冷排位置");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
            Choice {objectName:"assemblyRadiatorMountChoice";Layout.fillWidth:true;model:root.catalog.mounts || [];value:root.config.cooler_mount || "top"
                Accessible.name:ui.t("冷排位置");onPicked:selected=>stats.changeAssembly("cooler_mount",selected)}
        }
        Repeater {
            model:[{prefix:"",label:ui.t("主冷排"),secondary:false},
                   {prefix:"secondary_",label:ui.t("第二冷排"),secondary:true}]
            ColumnLayout {
                required property var modelData
                readonly property string prefix:modelData.prefix
                Layout.fillWidth:true;spacing:8
                visible:(root.coolerKind==="aio"||root.coolerKind==="custom_loop")&&(!modelData.secondary||(root.coolerKind==="custom_loop"&&root.config.gpu_waterblock===true))
                Text {text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;font.weight:Font.DemiBold;color:ui.ink}
                RowLayout {
                    Layout.fillWidth:true;spacing:12;visible:root.coolerKind==="custom_loop"
                    Text {Layout.preferredWidth:90;text:ui.t("独立冷排");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Choice {objectName:"assemblyRadiatorChoice_"+prefix;Layout.fillWidth:true;model:root.catalog.radiators || []
                        value:root.config[prefix+"radiator_model"] || "";Accessible.name:modelData.label+" "+ui.t("独立冷排")
                        onPicked:selected=>stats.changeAssembly(prefix+"radiator_model",selected)}
                }
                RowLayout {
                    Layout.fillWidth:true;spacing:12
                    Text {Layout.preferredWidth:90;text:ui.t("冷排风扇");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Choice {objectName:"assemblyRadiatorFanChoice_"+prefix;Layout.fillWidth:true;model:root.radiatorFansFor(prefix)
                        value:root.config[prefix+"radiator_fan_model"] || "";Accessible.name:modelData.label+" "+ui.t("冷排风扇")
                        onPicked:selected=>stats.changeAssembly(prefix+"radiator_fan_model",selected)}
                }
                Text {objectName:"assemblyRadiatorFanConflict_"+prefix;Layout.fillWidth:true;visible:root.radiatorFanConflict(prefix)
                    text:ui.t("当前风扇与冷排规格不匹配，请重新选择。")
                    font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
                Text {objectName:"assemblyRadiatorMountReview_"+prefix;Layout.fillWidth:true;visible:!!root.radiatorMountReview(prefix)
                    text:ui.t("风扇标称孔距与冷排不同，安装间隙待核。")
                    font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
                RowLayout {
                    Layout.fillWidth:true;spacing:12
                    Text {Layout.preferredWidth:90;text:ui.t("风扇布局");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                    Choice {objectName:"assemblyRadiatorLayoutChoice_"+prefix;Layout.fillWidth:true;model:root.catalog.radiator_layouts || []
                        value:root.config[prefix+"radiator_fan_layout"] || "single";Accessible.name:modelData.label+" "+ui.t("风扇布局")
                        onPicked:selected=>stats.changeAssembly(prefix+"radiator_fan_layout",selected)}
                }
            }
        }
        Text {Layout.fillWidth:true;visible:root.coolerKind==="aio";text:ui.t("一体式水冷保留原厂冷排；独立冷排用于自定义回路。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
        LoopParts046 {Layout.fillWidth:true;visible:root.coolerKind==="custom_loop";config:root.config;catalog:root.catalog}
        SettingRow {Layout.fillWidth:true;visible:root.coolerKind==="custom_loop"&&root.config.loop_components_mode!=="selected";label:ui.t("显卡水冷头（参考）")
            note:ui.t("仅替换三维外观，不代表检测到本机改装。")
            Toggle {checked:root.config.gpu_waterblock===true;onToggled:stats.changeAssembly("gpu_waterblock",checked)}}
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.preferredWidth:90;text:ui.t("电源型号");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
            Choice {objectName:"assemblyPsuChoice";Layout.fillWidth:true;model:root.catalog.psus || [];value:root.config.psu_model || ""
                Accessible.name:ui.t("电源型号");onPicked:selected=>stats.changeAssembly("psu_model",selected)}
        }
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("内存组合")
        note:(root.config.memory_models || []).length?ui.t("自选内存组合；每条可以单独选择型号和外观。") :ui.t("当前跟随已识别的内存数量和型号。")
        Repeater {
            model:root.config.memory_models || []
            RowLayout {
                required property string modelData
                required property int index
                Layout.fillWidth:true;spacing:8
                Choice {objectName:"assemblyMemory_"+index;Layout.fillWidth:true;model:root.catalog.memory || [];value:modelData
                    Accessible.name:ui.t("内存")+" "+(index+1);onPicked:selected=>stats.changeAssemblyMemory(index,selected)}
                IconButton {symbol:"trash";label:ui.t("移除");onClicked:stats.changeAssemblyMemory(index,"")}
            }
        }
        Flow {
            Layout.fillWidth:true;spacing:8
            ActionButton {objectName:"assemblyAddMemory";text:ui.t("添加参考内存");enabled:(root.config.memory_models || []).length<8&&(root.catalog.memory || []).length>0
                onClicked:stats.changeAssemblyMemory(-1,root.catalog.memory[0].id)}
            ActionButton {text:ui.t("恢复本机内存");enabled:(root.config.memory_models || []).length>0;onClicked:stats.resetAssemblyMemory()}
        }
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("机箱风扇")
        note:ui.t("按安装面选择型号、数量与进排风；转速缺失时实测模式保持静止。")
        Repeater {
            model:root.catalog.mounts || []
            ColumnLayout {
                required property var modelData
                readonly property string mount: modelData.id
                readonly property var selected: root.fan(mount)
                Layout.fillWidth:true;spacing:6
                RowLayout {
                    Layout.fillWidth:true;spacing:10
                    Text {Layout.preferredWidth:46;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted}
                    Choice {Layout.fillWidth:true;model:root.fansFor(mount);value:selected.model || ""
                        Accessible.name:modelData.label+" "+ui.t("风扇型号");onPicked:value=>root.changeFan(mount,"model",value)}
                }
                RowLayout {
                    Layout.fillWidth:true;spacing:10;enabled:!!selected.model
                    Item {Layout.preferredWidth:46}
                    Text {text:ui.t("数量");font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted}
                    Choice {Layout.preferredWidth:70;model:root.countsFor(mount,selected.model);value:String(selected.count || 1);onPicked:value=>root.changeFan(mount,"count",Number(value))}
                    Choice {Layout.fillWidth:true;model:[{id:"intake",label:ui.t("进风")},{id:"exhaust",label:ui.t("排风")}]
                        value:selected.direction;onPicked:value=>root.changeFan(mount,"direction",value)}
                }
            }
        }
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("存储与扩展")
        Repeater {
            model:(root.catalog.storage || []).filter(row=>row.id)
            RowLayout {
                required property var modelData
                readonly property var selected: (root.config.storage || []).find(row=>row.model_id===modelData.id)
                Layout.fillWidth:true;spacing:12
                Text {Layout.fillWidth:true;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;wrapMode:Text.WordWrap}
                Choice {Layout.preferredWidth:80;model:[{id:"0",label:ui.t("不放置")}].concat(root.counts);value:String(selected?selected.count:0)
                    Accessible.name:modelData.label+" "+ui.t("数量");onPicked:value=>stats.changeAssemblyStorage(modelData.id,Number(value))}
            }
        }
        Repeater {
            model:(root.catalog.expansion || []).filter(row=>row.id)
            SettingRow {
                required property var modelData
                Layout.fillWidth:true;label:modelData.label
                Toggle {checked:(root.config.expansion_cards || []).some(row=>row.model_id===modelData.id)
                    onToggled:stats.changeAssemblyExpansion(modelData.id,checked)}
            }
        }
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("混搭外观")
        note:ui.t("每类硬件可以单独选择风格；在三维窗口选中某一件，还能单独切换。")
        Repeater {
            model:stats.assemblyStyleTargets
            RowLayout {
                required property var modelData
                Layout.fillWidth:true;spacing:12
                Text {Layout.preferredWidth:90;text:modelData.label;font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}
                Choice {objectName:"assemblyPartStyle_"+modelData.id;Layout.fillWidth:true
                    model:stats.assemblyStyles.map(row=>({id:row.id,label:row.id==="follow"?ui.t("跟随默认外观"):row.label}))
                    value:(root.config.part_styles || {})[modelData.id] || "follow"
                    Accessible.name:modelData.label+" "+ui.t("此部件外观")
                    onPicked:selected=>stats.changeAssemblyPartStyle(modelData.id,selected)}
            }
        }
        Text {Layout.fillWidth:true;text:ui.t("单件设置优先于同类设置，同类设置优先于整机外观。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
    }
    SettingsGroup {
        Layout.fillWidth:true;title:ui.t("线缆与转动")
        SettingRow {Layout.fillWidth:true;label:ui.t("连接线缆");note:ui.t("按选定的电源和配件连接供电与数据线。")
            Toggle {objectName:"assemblyCablesToggle";checked:root.config.cables_enabled===true;onToggled:stats.changeAssembly("cables_enabled",checked)}}
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.preferredWidth:90;text:ui.t("线缆颜色");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted}
            Choice {Layout.fillWidth:true;model:root.catalog.colors || [];value:root.config.cable_color || "black";onPicked:selected=>stats.changeAssembly("cable_color",selected)}
        }
        RowLayout {
            Layout.fillWidth:true;spacing:12
            Text {Layout.preferredWidth:90;text:ui.t("转动来源");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted}
            Choice {objectName:"assemblyFanMotionChoice";Layout.fillWidth:true;model:root.catalog.motion || [];value:root.config.fan_motion || "measured"
                onPicked:selected=>stats.changeAssembly("fan_motion",selected)}
        }
        Text {Layout.fillWidth:true;text:ui.t("实测模式使用已有转速；参考转动仅演示机械动作，不代表本机转速。")
            font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
    }
}
