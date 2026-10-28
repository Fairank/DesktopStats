import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Item {
    id:root
    objectName:"historyPage"
    property var controller:stats
    property bool active:visible
    readonly property bool uiActive:active && root.Window.window !== null
        && root.Window.window.visible && root.Window.window.visibility !== Window.Minimized
    property string selectedId:""
    property string period:"10m"
    property var result:({state:"empty",points:[]})
    property var selectedMetadata:({})
    property bool clearArmed:false
    property bool componentReady:false
    readonly property var options:controller?controller.historyMetricChoices:[]
    readonly property var status:controller && uiActive?controller.historyStatus:({})
    readonly property bool recording:controller && controller.historyRecording===true
    readonly property var choices:options.map(row=>({id:row.id,label:row.label+(row.device_label?" · "+row.device_label:"")}))
    readonly property var lastPoint:(result.points || []).filter(point=>point && typeof point.timestamp==="number" && Number.isFinite(point.timestamp) && typeof point.value==="number" && Number.isFinite(point.value)).slice(-1)[0]
    readonly property real latestTime:typeof result.latest_time==="number" && Number.isFinite(result.latest_time)?result.latest_time:lastPoint?lastPoint.timestamp:NaN
    readonly property bool loading:result.state==="loading" || status.state==="loading"
    readonly property bool failed:result.state==="error" || result.state==="failed"
    readonly property bool readable:!failed && !loading && typeof result.latest==="number" && Number.isFinite(result.latest)
    readonly property bool narrow:width<580
    implicitWidth:760;implicitHeight:620
    Theme {id:ui}

    function number(value) {
        if(typeof value!=="number" || !Number.isFinite(value))return "—"
        if(value===0)return "0"
        return Math.abs(value)>=100000 || Math.abs(value)<.01?value.toExponential(2):Number(value.toPrecision(4)).toString()
    }
    function choose(identifier) {
        selectedId=identifier
        const choice=options.find(row=>row.id===identifier)
        if(choice)selectedMetadata=Object.assign({},choice)
        clearArmed=false
        refresh()
    }
    function ensureSelection() {
        if(!selectedId && options.length)choose(options[0].id)
        else if(selectedId) {
            const choice=options.find(row=>row.id===selectedId)
            if(choice)selectedMetadata=Object.assign({},choice)
        }
    }
    function refresh() {
        if(!componentReady || !uiActive || !controller || !selectedId)return
        const response=controller.historyQuery(selectedId,period)
        result=response || {state:"error",detail:ui.t("无法读取历史记录"),points:[]}
    }
    function timeText(timestamp) {
        return Number.isFinite(timestamp)?new Date(timestamp*1000).toLocaleString(Qt.locale(),"MM/dd hh:mm:ss"):""
    }
    function cancelInspection() {
        if (!Number.isFinite(chart.hoverTimestamp)) return false
        chart.hoverTimestamp = NaN
        return true
    }
    onOptionsChanged:ensureSelection()
    onUiActiveChanged:if(uiActive){ensureSelection();refresh()}else clearArmed=false
    onPeriodChanged:refresh()
    Component.onCompleted:{componentReady=true;ensureSelection();refresh()}
    Connections {
        target:root.controller
        function onHistoryChanged(){if(root.uiActive && !poll.running)poll.start()}
        function onHistoryRecordingChanged(){if(root.uiActive)root.refresh()}
    }
    Timer {id:poll;objectName:"historyRefreshTimer";interval:2000;repeat:true;running:root.uiActive;onTriggered:root.refresh()}

    ScrollView {
        id:scroll
        objectName:"historyPageScroll"
        anchors.fill:parent;anchors.margins:root.narrow?20:28
        contentWidth:availableWidth;contentHeight:content.implicitHeight;clip:true
        ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
        ColumnLayout {
            id:content
            width:Math.min(880,scroll.availableWidth-6);x:Math.max(0,(scroll.availableWidth-width)/2)
            spacing:22
            RowLayout {
                Layout.fillWidth:true;spacing:12
                ColumnLayout {
                    Layout.fillWidth:true;spacing:5
                    Text {Layout.fillWidth:true;text:ui.t("历史记录");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:22;font.weight:Font.DemiBold}
                    Text {Layout.fillWidth:true;text:ui.t("看清变化，找到值得关注的时刻。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
                }
                ColumnLayout {
                    spacing:2
                    Toggle {objectName:"historyRecordingToggle";Layout.alignment:Qt.AlignRight;checked:root.recording;Accessible.name:ui.t("记录历史");onToggled:{root.controller.setHistoryRecording(checked);checked=Qt.binding(()=>root.recording)}}
                    Text {text:root.recording?ui.t("正在记录"):ui.t("已暂停记录");color:root.recording?ui.accent:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                }
            }
            ColumnLayout {
                Layout.fillWidth:true;spacing:10
                Text {text:ui.t("指标与设备");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12}
                GridLayout {
                    Layout.fillWidth:true;columns:root.narrow?1:2;rowSpacing:10;columnSpacing:16
                    Choice {id:metricChoice;objectName:"historyMetricChoice";Layout.fillWidth:true;Layout.minimumWidth:0;model:root.choices;value:root.selectedId;enabled:root.choices.length>0;onPicked:identifier=>root.choose(identifier);Accessible.name:ui.t("选择历史指标与设备")}
                    RowLayout {
                        Layout.fillWidth:true;Layout.alignment:Qt.AlignRight;spacing:4
                        Repeater {
                            model:[{id:"10m",label:"10 分钟"},{id:"1h",label:"1 小时"},{id:"24h",label:"24 小时"}]
                            ActionButton {
                                required property var modelData
                                objectName:"historyRange_"+modelData.id
                                Layout.fillWidth:root.narrow;Layout.minimumWidth:0
                                text:ui.t(modelData.label);quiet:true;checked:root.period===modelData.id
                                onClicked:root.period=modelData.id
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth:true;spacing:14
                RowLayout {
                    Layout.fillWidth:true;spacing:12
                    Rectangle {Layout.preferredWidth:36;Layout.preferredHeight:36;radius:10;color:ui.selection;Icon {anchors.centerIn:parent;width:18;height:18;name:root.selectedMetadata.icon || "sensors";ink:ui.accent}}
                    ColumnLayout {
                        Layout.fillWidth:true;Layout.minimumWidth:0;spacing:4
                        Text {objectName:"historyMetricLabel";Layout.fillWidth:true;text:root.result.label || root.selectedMetadata.label || ui.t("选择一个指标");textFormat:Text.PlainText;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:14;font.weight:Font.DemiBold;elide:Text.ElideRight}
                        Text {objectName:"historyDeviceLabel";Layout.fillWidth:true;text:root.selectedMetadata.device_label || ui.t("本机");textFormat:Text.PlainText;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;elide:Text.ElideRight;HoverHandler {id:deviceHover}ToolTip.visible:deviceHover.hovered && truncated;ToolTip.text:text;ToolTip.delay:500}
                    }
                    ActionButton {objectName:"historyRetryButton";visible:root.failed;text:ui.t("重试");quiet:true;onClicked:root.refresh()}
                }
                RowLayout {
                    Layout.fillWidth:true;spacing:8;Layout.alignment:Qt.AlignLeft
                    Text {objectName:"historyLatestValue";text:root.readable?root.number(root.result.latest):"—";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:30;font.weight:Font.DemiBold}
                    Text {objectName:"historyLatestUnit";text:root.result.unit || root.selectedMetadata.unit || "";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:13;Layout.alignment:Qt.AlignBottom;Layout.bottomMargin:5}
                    Item {Layout.fillWidth:true}
                    ColumnLayout {
                        Layout.minimumWidth:0;spacing:4;Layout.alignment:Qt.AlignRight
                        Text {Layout.alignment:Qt.AlignRight;text:ui.t("最近记录");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                        Text {objectName:"historyLastSampleTime";Layout.alignment:Qt.AlignRight;text:Number.isFinite(root.latestTime)?(root.narrow?new Date(root.latestTime*1000).toLocaleTimeString(Qt.locale(),"hh:mm:ss"):root.timeText(root.latestTime)):"—";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                    }
                }
                TrendChart {
                    id:chart
                    objectName:"historyTrendChart"
                    Layout.fillWidth:true;Layout.preferredHeight:root.failed || root.loading || !root.result.count?164:root.narrow?222:254
                    series:[{id:root.selectedId,label:root.result.label || root.selectedMetadata.label || "",unit:root.result.unit || root.selectedMetadata.unit || "",points:root.result.points || []}]
                    unit:root.result.unit || root.selectedMetadata.unit || ""
                    rangeStart:typeof root.result.start==="number"?root.result.start:NaN
                    rangeEnd:typeof root.result.end==="number"?root.result.end:NaN
                    minimum:unit==="%"?0:NaN
                    maximum:unit==="%"?100:NaN
                    loading:root.loading
                    errorText:root.failed?root.result.detail || ui.t("无法读取历史记录"):""
                    emptyText:root.options.length?ui.t("这段时间还没有记录"):ui.t("开启记录后，可在这里查看设备的变化")
                }
                GridLayout {
                    Layout.fillWidth:true;columns:3;columnSpacing:18;rowSpacing:4;visible:!root.failed && !root.loading && root.result.count>0
                    Repeater {
                        model:[{label:"平均值",value:root.result.mean},{label:"峰值",value:root.result.peak},{label:"最低值",value:root.result.minimum}]
                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth:true;Layout.minimumWidth:0;spacing:5
                            Text {text:ui.t(modelData.label);color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                            Text {Layout.fillWidth:true;text:root.failed || root.loading?"—":root.number(modelData.value)+(typeof modelData.value==="number" && Number.isFinite(modelData.value)?" "+(root.result.unit || ""):"");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.Medium;elide:Text.ElideRight;HoverHandler {id:statHover}ToolTip.visible:statHover.hovered && truncated;ToolTip.text:text;ToolTip.delay:500}
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth:true;spacing:8;visible:!root.failed && !root.loading
                    Text {objectName:"historySampleCount";Layout.fillWidth:true;text:(Number.isInteger(root.result.count)?root.result.count:0)+" "+ui.t("个采样点")+(root.result.missing_count?" · "+root.result.missing_count+" "+ui.t("次缺失"):"");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    Text {visible:typeof root.result.coverage==="number" && Number.isFinite(root.result.coverage);text:ui.t("覆盖率")+" "+Math.round(Math.max(0,Math.min(1,root.result.coverage || 0))*100)+"%";color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11}
                }
                Text {objectName:"historyAggregationNote";Layout.fillWidth:true;visible:chart.hasRanges && !root.failed && !root.loading;text:ui.t("折线表示区间均值，细线保留最低值与峰值。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
            }
            Rectangle {Layout.fillWidth:true;height:1;color:ui.line}
            ColumnLayout {
                Layout.fillWidth:true;spacing:12
                Text {objectName:"historyStorageStatus";Layout.fillWidth:true;text:root.status.detail || ui.t("记录仅保存在这台电脑上。暂停后会保留已有记录。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
                RowLayout {
                    Layout.fillWidth:true;spacing:8
                    Icon {name:"time";ink:ui.muted;Layout.preferredWidth:14;Layout.preferredHeight:14}
                    Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:ui.t("曲线空白处代表缺失，不会补成 0。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap}
                    ActionButton {objectName:"historyClearButton";text:ui.t("清空记录");quiet:true;onClicked:root.clearArmed=true;enabled:!root.loading}
                }
                Rectangle {
                    objectName:"historyClearConfirmation"
                    Layout.fillWidth:true;implicitHeight:confirmColumn.implicitHeight+24;visible:root.clearArmed
                    color:ui.card;radius:9;border.color:ui.line
                    ColumnLayout {
                        id:confirmColumn;anchors.fill:parent;anchors.margins:12;spacing:10
                        Text {Layout.fillWidth:true;text:ui.t("清空这台电脑上的全部历史记录？此操作无法撤销。");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
                        RowLayout {
                            Layout.alignment:Qt.AlignRight;spacing:8
                            ActionButton {objectName:"historyCancelClear";text:ui.t("取消");quiet:true;onClicked:root.clearArmed=false}
                            ActionButton {objectName:"historyConfirmClear";text:ui.t("确认清空");onClicked:{root.controller.clearHistory();root.clearArmed=false;root.refresh()}}
                        }
                    }
                }
            }
        }
    }
}
