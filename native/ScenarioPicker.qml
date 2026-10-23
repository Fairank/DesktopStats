import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id:root
    objectName:"scenarioPicker"
    property var scenarios:[]
    property string selectedId:""
    property string appliedId:""
    property bool busy:false
    property string errorText:""
    property bool allowSave:true
    property bool showHeading:true
    property string removeId:""
    readonly property int columns:width>=620?2:1
    signal previewRequested(string id)
    signal applyRequested(string id)
    signal saveRequested(string name)
    signal removeRequested(string id)
    onVisibleChanged:if(!visible)removeId=""
    onScenariosChanged:if(removeId && !scenarios.some(row=>row.id===removeId))removeId=""
    implicitHeight:content.implicitHeight
    Theme {id:ui}
    ColumnLayout {
        id:content;width:parent.width;spacing:14
        RowLayout {
            Layout.fillWidth:true;visible:root.showHeading
            ColumnLayout {
                Layout.fillWidth:true;spacing:4
                Text {Layout.fillWidth:true;text:ui.t("从一个场景开始");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:16;font.weight:Font.DemiBold}
                Text {Layout.fillWidth:true;text:ui.t("先看布局，再选择适合你的工作方式。");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
            }
            BusyIndicator {Layout.preferredWidth:24;Layout.preferredHeight:24;visible:root.busy;running:visible && ui.motionAllowed}
        }
        GridLayout {
            id:cards;Layout.fillWidth:true;columns:root.columns;columnSpacing:12;rowSpacing:12
            Repeater {
                model:root.scenarios
                Rectangle {
                    id:card
                    required property var modelData
                    required property int index
                    objectName:"scenarioCard_"+modelData.id
                    readonly property bool selected:root.selectedId===modelData.id
                    readonly property bool applied:root.appliedId===modelData.id
                    readonly property var preview:modelData.preview || ({})
                    readonly property var metrics:preview.metrics || []
                    readonly property var tiles:preview.tiles===undefined?metrics.map(metric=>({label:metric.label,icon:metric.icon,metrics:[metric]})):(preview.tiles || [])
                    readonly property color accent:modelData.accent || ui.accent
                    Layout.fillWidth:true;Layout.minimumWidth:0;Layout.preferredWidth:root.columns===2?(root.width-12)/2:root.width
                    implicitHeight:cardContent.implicitHeight+28
                    radius:12;color:selected?ui.cardSelected:ui.card
                    border.color:selected?ui.selectedLine:ui.line;border.width:1
                    Behavior on color {ColorAnimation {duration:ui.motionAllowed?120:0}}
                    ColumnLayout {
                        id:cardContent;anchors.fill:parent;anchors.margins:14;spacing:12
                        Item {
                            objectName:"scenarioPreview_"+card.modelData.id
                            Layout.fillWidth:true;Layout.preferredHeight:100
                            clip:true
                            Rectangle {anchors.fill:parent;radius:8;gradient:Gradient {GradientStop {position:0;color:ui.dark?"#293b40":"#e1eded"}GradientStop {position:1;color:ui.dark?"#30364a":"#dbe3f3"}}}
                            Rectangle {
                                visible:card.preview.kind==="bar"
                                x:10;y:(parent.height-height)/2;width:parent.width-20;height:24;radius:4
                                color:ui.dark?"#da2c323a":"#eaffffff"
                                Row {
                                    anchors.centerIn:parent;spacing:14
                                    Repeater {model:card.metrics.slice(0,4);Row {required property var modelData;spacing:4;Icon {width:10;height:10;name:modelData.icon || "sensors";ink:card.accent}Text {text:ui.t(modelData.label);color:ui.ink;font.family:ui.fontFamily;font.pixelSize:9}}}
                                }
                            }
                            Row {
                                anchors.centerIn:parent;spacing:7;visible:card.preview.kind!=="bar"
                                Repeater {
                                    model:card.tiles.slice(0,3)
                                    Rectangle {
                                        required property var modelData
                                        required property int index
                                        objectName:"scenarioTile_"+card.modelData.id+"_"+index
                                        width:Math.min(106,(card.width-62)/Math.min(3,Math.max(1,card.tiles.length)));height:card.preview.kind==="compact"?56:78;radius:8
                                        color:ui.dark?"#df2d343f":"#ecffffff"
                                        Column {anchors.fill:parent;anchors.margins:8;spacing:7
                                            Row {spacing:5;Icon {width:11;height:11;name:modelData.icon || "sensors";ink:card.accent}Text {width:parent.parent.width-16;text:ui.t(modelData.label || "");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:9;font.weight:Font.Medium;elide:Text.ElideRight}}
                                            Repeater {
                                                model:(modelData.metrics || []).slice(0,card.preview.kind==="compact"?1:2)
                                                Row {
                                                    required property var modelData
                                                    width:parent.width;spacing:4
                                                    Text {width:parent.width-14;text:ui.t(modelData.label || "");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:9;elide:Text.ElideRight}
                                                    Text {text:"—";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:10;font.weight:Font.Medium}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Text {visible:card.preview.kind!=="bar" && card.tiles.length>3;anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:7;text:"+"+(card.tiles.length-3);color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10}
                        }
                        RowLayout {
                            Layout.fillWidth:true;spacing:7
                            Icon {name:card.modelData.icon || "grid";ink:card.accent;Layout.preferredWidth:16;Layout.preferredHeight:16}
                            Text {Layout.fillWidth:true;Layout.minimumWidth:0;text:ui.t(card.modelData.label || card.modelData.id);color:ui.ink;font.family:ui.fontFamily;font.pixelSize:14;font.weight:Font.DemiBold;elide:Text.ElideRight}
                            Text {visible:card.applied;text:ui.t("已应用");color:ui.accent;font.family:ui.fontFamily;font.pixelSize:11;font.weight:Font.Medium}
                            IconButton {objectName:"scenarioRemoveButton_"+card.modelData.id;visible:card.modelData.custom===true && card.modelData.id!=="previous";enabled:!root.busy;symbol:"trash";label:ui.t("移除")+" · "+ui.t(card.modelData.label || card.modelData.id);onClicked:root.removeId=card.modelData.id;ToolTip.visible:hovered;ToolTip.text:label}
                        }
                        Text {Layout.fillWidth:true;text:ui.t(card.modelData.description || "");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap;Layout.minimumHeight:36}
                        Text {Layout.fillWidth:true;text:ui.t(card.modelData.summary || "");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;elide:Text.ElideRight;visible:!!text}
                        RowLayout {
                            Layout.fillWidth:true;spacing:8;visible:root.removeId!==card.modelData.id
                            ActionButton {objectName:"scenarioPreviewButton_"+card.modelData.id;Layout.fillWidth:true;text:card.selected?ui.t("正在预览"):ui.t("预览方案");checked:card.selected;enabled:!root.busy;onClicked:root.previewRequested(card.modelData.id)}
                            ActionButton {objectName:"scenarioApplyButton_"+card.modelData.id;Layout.fillWidth:true;text:ui.t("使用方案");accent:card.selected;enabled:!root.busy;onClicked:root.applyRequested(card.modelData.id)}
                        }
                        RowLayout {
                            Layout.fillWidth:true;spacing:8;visible:root.removeId===card.modelData.id
                            Text {Layout.fillWidth:true;text:ui.t("移除")+"？";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12}
                            ActionButton {objectName:"scenarioRemoveCancel_"+card.modelData.id;text:ui.t("取消");quiet:true;enabled:!root.busy;onClicked:root.removeId=""}
                            ActionButton {objectName:"scenarioRemoveConfirm_"+card.modelData.id;text:ui.t("移除");enabled:!root.busy;Accessible.name:ui.t("移除")+" · "+ui.t(card.modelData.label || card.modelData.id);contentItem:Text {text:parent.text;color:ui.dark?"#ffb4ab":"#b3261e";font:parent.font;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}onClicked:root.removeRequested(card.modelData.id)}
                        }
                    }
                    Accessible.role:Accessible.Grouping
                    Accessible.name:ui.t(card.modelData.label || card.modelData.id)
                }
            }
        }
        Text {objectName:"scenarioError";Layout.fillWidth:true;visible:!!root.errorText;text:root.errorText;color:ui.dark?"#ffb4ab":"#b3261e";font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap}
        Text {Layout.fillWidth:true;visible:!root.scenarios.length;text:ui.t("暂无可用场景");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12}
        ColumnLayout {
            Layout.fillWidth:true;spacing:8;visible:root.allowSave
            Text {text:ui.t("保存自己的工作方式");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.Medium}
            RowLayout {
                Layout.fillWidth:true;spacing:8
                TextField {id:scenarioName;objectName:"scenarioNameInput";Layout.fillWidth:true;Layout.minimumWidth:0;implicitHeight:34;maximumLength:20;placeholderText:ui.t("给当前布局命名");placeholderTextColor:ui.muted;color:ui.ink;font.family:ui.fontFamily;font.pixelSize:12;selectByMouse:true;background:GlassSurface {tone:"field";focused:scenarioName.activeFocus}}
                ActionButton {objectName:"scenarioSaveButton";text:ui.t("保存布局");enabled:!root.busy && scenarioName.text.trim().length>0;onClicked:root.saveRequested(scenarioName.text.trim())}
            }
        }
    }
}
