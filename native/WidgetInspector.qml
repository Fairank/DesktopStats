import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Item {
    id:root
    readonly property var config:stats.draft
    required property string widgetKey
    required property var canvas
    property bool inlineMode:false
    property bool active:visible
    property bool devicesOpen:false
    property bool positionOpen:false
    property bool displayOpen:false
    property alias previewHost:previewHost
    readonly property real commonHeight:sizeRow.implicitHeight+(styleFields.visible?styleFields.implicitHeight+16:0)
    implicitHeight:fields.implicitHeight+(inlineMode?0:76)
    property string section:"style"
    signal selectSection(string section)
    readonly property var prefs:root.config.widgets[widgetKey] || ({})
    readonly property bool glassSkin:["glass","frost","tint"].includes(root.prefs.skin || root.config.skin)
    readonly property var dimensions:root.canvas.dimensions
    readonly property bool percentFirst:{const draft=root.config;const ids=root.canvas.contents;return !!ids.length && stats.metricInfoFor(widgetKey,ids[0]).unit==="%"}
    property var health:({})
    property bool advanced:false
    readonly property bool pendingInput:{if(widthInput.userEdited || heightInput.userEdited)return true;for(let i=0;i<coordinateInputs.count;i++){const item=coordinateInputs.itemAt(i);if(item && item.pendingInput)return true}return false}
    Theme {id:ui}
    function refreshHealth(){if(active)health=stats.widgetHealth(widgetKey)}
    function openSection(value){if(value==="devices")devicesOpen=true;else if(value==="position")positionOpen=true}
    function sectionPosition(value){const item=value==="devices"?dataSettings:value==="position"?positionSettings:styleFields;return item.mapToItem(root,0,0).y}
    onActiveChanged:refreshHealth()
    Component.onCompleted:refreshHealth()
    Connections {target:stats;enabled:root.active;function onDataChanged(){root.refreshHealth()}function onDraftChanged(){root.refreshHealth()}}
    function commitSize(field){if(field.userEdited && field.targetKey===widgetKey){if(!stats.setWidgetDimensions(widgetKey,Number(widthInput.text),Number(heightInput.text)))sizeNotice.text=ui.t("尺寸未更改，请检查输入范围与布局。");else sizeNotice.text=""}widthInput.userEdited=false;heightInput.userEdited=false;widthInput.text=Qt.binding(()=>String(root.dimensions.width || 168));heightInput.text=Qt.binding(()=>String(root.dimensions.height || 168))}
    function revealFocus(){const win=root.Window.window,item=win?win.activeFocusItem:null,flick=scroll.contentItem;if(!item || !flick || flick.contentY===undefined)return;let ancestor=item;while(ancestor && ancestor!==fields)ancestor=ancestor.parent;if(ancestor!==fields)return;const p=item.mapToItem(fields,0,0);if(p.y<flick.contentY+5)flick.contentY=Math.max(0,p.y-5);else if(p.y+item.height>flick.contentY+scroll.availableHeight-5)flick.contentY=Math.min(Math.max(0,flick.contentHeight-scroll.availableHeight),p.y+item.height-scroll.availableHeight+5)}
    Connections {target:root.Window.window;function onActiveFocusItemChanged(){Qt.callLater(root.revealFocus)}}
    onWidgetKeyChanged:{advanced=false;devicesOpen=false;positionOpen=false;displayOpen=false;refreshHealth()}
    ColumnLayout {
        anchors.fill:parent;anchors.margins:root.inlineMode?0:16;spacing:12
        OptionTabs {visible:!root.inlineMode;Layout.fillWidth:true;options:[{id:"style",label:ui.t("外观"),objectName:"widgetStyleTab"},{id:"devices",label:ui.t("数据"),objectName:"widgetDevicesTab"},{id:"position",label:ui.t("位置"),objectName:"widgetPositionTab"}];value:root.section;onPicked:selected=>root.selectSection(selected)}
        ScrollView {
            id:scroll;objectName:"widgetInspectorScroll";wheelEnabled:!root.inlineMode;Layout.fillWidth:true;Layout.fillHeight:!root.inlineMode;Layout.preferredHeight:root.inlineMode?fields.implicitHeight:-1;contentWidth:availableWidth;clip:!root.inlineMode;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff;ScrollBar.vertical.policy:root.inlineMode?ScrollBar.AlwaysOff:ScrollBar.AsNeeded
            Component.onCompleted:if(root.inlineMode && contentItem)contentItem.interactive=false
            ColumnLayout {
                id:fields
                width:scroll.availableWidth-5;spacing:16
                RowLayout {
                    id:sizeRow;Layout.fillWidth:true;spacing:8
                    Text {text:ui.t("尺寸");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:ui.captionSize}
                    TextField {id:widthInput;objectName:"widgetWidthInput";Layout.preferredWidth:72;implicitHeight:34;property bool userEdited:false;property string targetKey:"";text:String(root.dimensions.width || 168);validator:IntValidator {bottom:80;top:4096}
                        font.family:ui.fontFamily;font.pixelSize:ui.bodySize;color:ui.ink;selectByMouse:true;onTextEdited:{userEdited=true;targetKey=root.widgetKey}onEditingFinished:root.commitSize(widthInput);Accessible.name:ui.t("宽度");background:GlassSurface {tone:"field";radius:7}}
                    Text {text:"×";color:ui.muted}
                    TextField {id:heightInput;objectName:"widgetHeightInput";Layout.preferredWidth:72;implicitHeight:34;property bool userEdited:false;property string targetKey:"";text:String(root.dimensions.height || 168);validator:IntValidator {bottom:32;top:2160}
                        font.family:ui.fontFamily;font.pixelSize:ui.bodySize;color:ui.ink;selectByMouse:true;onTextEdited:{userEdited=true;targetKey=root.widgetKey}onEditingFinished:root.commitSize(heightInput);Accessible.name:ui.t("高度");background:GlassSurface {tone:"field";radius:7}}
                    Text {text:"px";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:ui.metaSize}
                    Item {Layout.fillWidth:true}
                    Text {text:ui.t("显示标题");font.family:ui.fontFamily;font.pixelSize:ui.captionSize;color:ui.ink}
                    Toggle {objectName:"showTitleToggle";checked:root.prefs.show_title!==false;Accessible.name:ui.t("显示标题");onToggled:stats.changeWidget(root.widgetKey,"show_title",checked)}
                }
                Text {id:sizeNotice;Layout.fillWidth:true;visible:!!text;text:"";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:ui.captionSize;wrapMode:Text.WordWrap}
                ColumnLayout {
                    id:styleFields;visible:(root.inlineMode || root.section==="style") && !root.canvas.enabled;Layout.fillWidth:true;spacing:10
                    SkinPicker {objectName:"widgetSkinPicker";Layout.fillWidth:true;allowGlobal:true;compact:root.inlineMode;widgetKey:root.widgetKey;value:root.prefs.skin || "global";onPicked:selected=>stats.changeWidget(root.widgetKey,"skin",selected==="global"?null:selected)}
                    Text {objectName:"glassControlsApplicability";visible:!root.glassSkin;Layout.fillWidth:true;text:ui.t("当前皮肤不使用玻璃参数。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    GridLayout {Layout.fillWidth:true;columns:root.inlineMode && width>=430?2:1;uniformCellWidths:true;columnSpacing:24;rowSpacing:12
                    Repeater {
                        model:root.glassSkin?[{field:"glass_transparency",label:"玻璃透明度"},{field:"glass_curvature",label:"圆角曲率"}]:[]
                        ColumnLayout {
                            id:glass;required property var modelData;Layout.fillWidth:true;spacing:4
                            readonly property bool inherited:root.prefs[modelData.field]===null || root.prefs[modelData.field]===undefined
                            readonly property real resolved:inherited?root.config[modelData.field]:root.prefs[modelData.field]
                            RowLayout {
                                Layout.fillWidth:true;spacing:5
                                Text {Layout.fillWidth:true;text:ui.t(glass.modelData.label);color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                                Check {objectName:"inherit_"+glass.modelData.field;text:ui.t("跟随全局");checked:glass.inherited;implicitHeight:24;Accessible.name:ui.t(glass.modelData.label)+" · "+ui.t("跟随全局");onToggled:stats.changeWidget(root.widgetKey,glass.modelData.field,checked?null:glass.resolved)}
                            }
                            RowLayout {
                                Layout.fillWidth:true;spacing:8
                                ValueSlider {objectName:"local_"+glass.modelData.field;Layout.fillWidth:true;from:0;to:100;stepSize:.1;value:glass.resolved || 0;Accessible.name:ui.t(glass.modelData.label);Accessible.description:ui.t("拖动后仅修改此组件。");onMoved:stats.changeWidget(root.widgetKey,glass.modelData.field,value);ToolTip.visible:hovered;ToolTip.text:ui.t("拖动后仅修改此组件。")}
                                Text {text:Number(glass.resolved || 0).toLocaleString(Qt.locale(stats.language),"f",1)+"%";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10}
                            }
                        }
                    }}
                }
                Item {id:previewHost;objectName:"widgetPreviewHost";Layout.fillWidth:true;implicitHeight:childrenRect.height}
                ActionButton {objectName:"displayOptionsToggle";Layout.alignment:Qt.AlignLeft;leftPadding:0;text:(root.displayOpen?"− ":"＋ ")+ui.t("显示选项");quiet:true;implicitHeight:34;onClicked:root.displayOpen=!root.displayOpen}
                ColumnLayout {visible:root.displayOpen;Layout.fillWidth:true;spacing:10
                    SettingRow {Layout.fillWidth:true;label:ui.t("显示图表");Toggle {objectName:"showChartToggle";checked:root.prefs.chart || false;onToggled:stats.changeWidget(root.widgetKey,"chart",checked)}}
                    FormField {Layout.fillWidth:true;label:ui.t("信息样式");Choice {objectName:"widgetPresentation";Layout.fillWidth:true;model:[{id:"auto",label:ui.t("自动")},{id:"hero",label:ui.t("大数字")},{id:"list",label:ui.t("详细列表")}].concat(root.percentFirst || ["ring","bar"].includes(root.prefs.presentation)?[{id:"ring",label:ui.t("圆环")},{id:"bar",label:ui.t("进度条")}]:[]).concat(root.prefs.kind==="cpu"?[{id:"cores",label:ui.t("每核负载")}]:[]);value:root.prefs.presentation;onPicked:selected=>stats.changeWidget(root.widgetKey,"presentation",selected)}}
                }
                ActionButton {id:dataSettings;objectName:"inlineDataSettings";visible:root.inlineMode;Layout.alignment:Qt.AlignLeft;leftPadding:0;text:(root.devicesOpen?"− ":"＋ ")+ui.t("数据来源与单位");quiet:true;implicitHeight:34;onClicked:root.devicesOpen=!root.devicesOpen}
                ColumnLayout {
                    visible:root.inlineMode?root.devicesOpen:root.section==="devices";Layout.fillWidth:true;spacing:14
                    Text {Layout.fillWidth:true;text:root.canvas.selectedMeta.label || ui.t("选择一个指标查看数据来源");textFormat:Text.PlainText;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.Medium;color:ui.ink;wrapMode:Text.WordWrap}
                    Text {Layout.fillWidth:true;text:[root.canvas.selectedMeta.hardware_name,root.canvas.selectedMeta.note].filter(Boolean).join("\n");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    Text {Layout.fillWidth:true;text:(root.health.available || 0)+" / "+(root.health.total || 0)+" "+ui.t("项可用");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:11}
                    Repeater {model:root.health.missing || [];Text {required property var modelData;Layout.fillWidth:true;text:modelData.label+" · "+modelData.reason;textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}}
                    Text {Layout.fillWidth:true;text:ui.t("新增指标会保留已有摆放。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    Repeater {
                        model:[{scope:"gpus",field:"gpu_target",label:"显卡"},{scope:"networks",field:"network_target",label:"网卡"},{scope:"disks",field:"disk_target",label:"物理磁盘"},{scope:"volumes",field:"volume_target",label:"存储分区"},{scope:"storages",field:"storage_target",label:"NVMe"}]
                        FormField {
                            id:device;required property var modelData
                            visible:{const draft=root.config;return root.canvas.contents.some(id=>stats.metricInfoFor(root.widgetKey,id).scope===modelData.scope)}
                            Layout.fillWidth:true;label:ui.t(modelData.label)
                            Choice {Layout.fillWidth:true;model:{const devices=stats.devices;return stats.deviceChoices(root.widgetKey,device.modelData.scope)}
value:root.prefs[device.modelData.field];onPicked:selected=>stats.changeWidget(root.widgetKey,device.modelData.field,selected)}
                        }
                    }
                    FormField {Layout.fillWidth:true;visible:{const draft=root.config;return root.canvas.contents.some(id=>["°C","°F"].includes(stats.metricInfoFor(root.widgetKey,id).unit))}
                        label:ui.t("温度单位");Choice {objectName:"widgetTemperatureUnit";Layout.fillWidth:true;model:[{id:"C",label:"°C"},{id:"F",label:"°F"}];value:root.prefs.temperature_unit;onPicked:selected=>stats.changeWidget(root.widgetKey,"temperature_unit",selected)}}
                    FormField {Layout.fillWidth:true;visible:{const draft=root.config;return root.canvas.contents.some(id=>id.startsWith("net_") || stats.metricInfoFor(root.widgetKey,id).scope==="networks")}
                        label:ui.t("网络单位");Choice {objectName:"widgetNetworkUnit";Layout.fillWidth:true;model:[{id:"MBps",label:"MB/s"},{id:"Mbps",label:"Mbps"}];value:root.prefs.network_unit;onPicked:selected=>stats.changeWidget(root.widgetKey,"network_unit",selected)}}
                    FormField {Layout.fillWidth:true;label:ui.t("小数位数");Choice {objectName:"widgetPrecision";Layout.fillWidth:true;model:[{id:"auto",label:ui.t("自动")},{id:"0",label:"0"},{id:"1",label:"1"},{id:"2",label:"2"}];value:root.prefs.precision;onPicked:selected=>stats.changeWidget(root.widgetKey,"precision",selected)}}
                }
                ActionButton {id:positionSettings;objectName:"inlinePositionSettings";visible:root.inlineMode;Layout.alignment:Qt.AlignLeft;leftPadding:0;text:(root.positionOpen?"− ":"＋ ")+ui.t("放置位置");quiet:true;implicitHeight:34;onClicked:root.positionOpen=!root.positionOpen}
                ColumnLayout {
                    visible:root.inlineMode?root.positionOpen:root.section==="position";Layout.fillWidth:true;spacing:14
                    FormField {Layout.fillWidth:true;label:ui.t("放置位置");Choice {objectName:"widgetDock";Layout.fillWidth:true;model:[{id:"free",label:ui.t("自由放置")},{id:"top",label:ui.t("屏幕顶部")}];value:root.prefs.dock || "free";onPicked:selected=>stats.changeWidget(root.widgetKey,"dock",selected)}}
                    FormField {Layout.fillWidth:true;label:ui.t("窗口层级");Choice {objectName:"widgetLayer";Layout.fillWidth:true;model:[{id:"desktop",label:ui.t("仅在桌面")},{id:"pinned",label:ui.t("始终置顶")}];value:root.prefs.layer || "desktop";onPicked:selected=>stats.changeWidget(root.widgetKey,"layer",selected)}}
                    FormField {Layout.fillWidth:true;visible:root.prefs.dock==="top";label:ui.t("显示器");Choice {objectName:"widgetScreen";Layout.fillWidth:true;model:stats.screenChoices;value:root.prefs.screen_target || "";onPicked:selected=>stats.changeWidget(root.widgetKey,"screen_target",selected)}}
                    Text {Layout.fillWidth:true;text:ui.t(root.prefs.layer==="pinned"?"置顶会覆盖其他窗口的一小部分，可右击暂时隐藏。":"桌面层级位于其他窗口下方，不遮挡工作。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    SettingRow {Layout.fillWidth:true;visible:root.config.mode==="mixed";label:ui.t("放入组合面板");Toggle {checked:root.prefs.grouped || false;onToggled:stats.changeWidget(root.widgetKey,"grouped",checked)}}
                }
                ActionButton {objectName:"advancedLayoutToggle";visible:!root.inlineMode;Layout.fillWidth:true;text:(root.advanced?"− ":"＋ ")+ui.t("高级");quiet:true;implicitHeight:30;onClicked:root.advanced=!root.advanced}
                ColumnLayout {
                    objectName:"advancedLayoutFields";visible:root.canvas.enabled && (root.inlineMode || root.advanced);Layout.fillWidth:true;spacing:10
                    GridLayout {
                        visible:root.canvas.manual && !!root.canvas.selectedRect && (!root.inlineMode || root.canvas.enabled);Layout.fillWidth:true;columns:2;columnSpacing:8;rowSpacing:8
                        Repeater {
                            id:coordinateInputs
                            model:[{field:"x",label:"横向位置"},{field:"y",label:"纵向位置"},{field:"width",label:"宽度"},{field:"height",label:"高度"}]
                            FormField {
                                id:coordinate;required property var modelData;Layout.fillWidth:true;label:ui.t(modelData.label)+" %"
                                readonly property bool pendingInput:input.userEdited
                                TextField {
                                    id:input;objectName:"metricPosition_"+coordinate.modelData.field;Layout.fillWidth:true;implicitHeight:32
                                    property real percentage:root.canvas.selectedRect?root.canvas.selectedRect[coordinate.modelData.field]*100:0
                                    property bool userEdited:false
                                    property string targetKey:""
                                    property string targetMetric:""
                                    text:percentage.toFixed(1);validator:DoubleValidator {bottom:0;top:100;decimals:1;locale:"C"}
                                    color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;selectByMouse:true
                                    onTextEdited:{userEdited=true;targetKey=root.widgetKey;targetMetric=root.canvas.selectedMetric}
                                    onEditingFinished:{if(userEdited && targetKey===root.widgetKey && targetMetric===root.canvas.selectedMetric && acceptableInput){const all=root.canvas.positions(),id=root.canvas.selectedMetric;if(all[id]){all[id][coordinate.modelData.field]=Number(text)/100;if(!stats.commitMetricPositions(root.widgetKey,all))root.canvas.notice=ui.t("当前选择无法这样排列。")}}userEdited=false;text=Qt.binding(()=>percentage.toFixed(1))}
                                    background:GlassSurface {tone:"field";radius:7;focused:input.activeFocus}
                                }
                            }
                        }
                    }
                    Text {visible:!root.inlineMode || root.canvas.enabled;Layout.fillWidth:true;text:ui.t("拖动右下角改变组件尺寸；这些数值用于精确调整。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;wrapMode:Text.WordWrap}
                }
            }
        }
    }
}
