import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Window {
    id: root
    readonly property var draftConfig:stats.draft
    objectName: "settingsWindow"
    property int page: 0
    property string selectedKey: root.draftConfig.widget_order[0] || ""
    property bool nativeHosted:false
    readonly property int titlebarHeight:nativeHosted?0:34
    readonly property int clientY:titlebarHeight
    readonly property real clientHeight:Math.max(0,height-clientY)
    readonly property int replacementBannerHeight:stats.replacementPending?40:0
    readonly property string currentScope:page===3?"topbar":page===1 || page===2 || page===4?"preferences":"desktop"
    readonly property int railWidth: layoutWidth<900?184:200
    readonly property bool atWidgetLimit: root.draftConfig.widget_order.length >= 24
    property bool editorReady: false
    // Keep editor instances and uncommitted input alive during native resize.
    // Only the lightweight shell follows every pixel; content settles once.
    property real layoutWidth:width
    property real layoutHeight:height
    property bool resizeInProgress:false
    function scheduleLayout(){if(!visible || !editorReady){layoutWidth=width;layoutHeight=height;resizeInProgress=false}else{resizeInProgress=true;layoutSettle.restart()}}
    onWidthChanged:scheduleLayout()
    onHeightChanged:scheduleLayout()
    onVisibleChanged:if(visible){layoutWidth=width;layoutHeight=height;resizeInProgress=false}
    Timer {id:layoutSettle;interval:120;onTriggered:{root.layoutWidth=root.width;root.layoutHeight=root.height;root.resizeInProgress=false}}
    readonly property bool pendingInput:frequency.pendingInput || (!!widgetEditorLoader.item && widgetEditorLoader.item.pendingInput)
    readonly property bool pendingEdits: stats.dirty || pendingInput || topBarEditor.pendingGroupEdits
    readonly property bool currentPendingInput:currentScope==="preferences"?frequency.pendingInput:currentScope==="desktop" && !!widgetEditorLoader.item && widgetEditorLoader.item.pendingInput
    readonly property bool currentDirty:stats.replacementPending || !!stats.scopeDirty[currentScope] || currentPendingInput
    width:1280; height:760; minimumWidth:720; minimumHeight:600
    color:"transparent"; title:"Desktop Stats"
    flags:nativeHosted?Qt.Widget:Qt.Window | Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
    Theme {id:ui}
    Component.onCompleted:Qt.callLater(()=>root.editorReady=true)
    onClosing:function(close){close.accepted=false;root.hide()}
    onSelectedKeyChanged:Qt.callLater(root.revealSelected)
    function selectWidget(key){if(root.draftConfig.widget_order.includes(key))selectedKey=key;page=0;Qt.callLater(root.revealSelected)}
    function selectHistory(identifier){page=4;if(identifier)historyPage.choose(identifier)}
    function showGallery(){if(!atWidgetLimit)gallery.showWidgets()}
    function selectNext(){if(!root.draftConfig.widget_order.includes(selectedKey))selectedKey=root.draftConfig.widget_order[0] || ""}
    function restoreGalleryFocus(){const row=instanceRepeater.itemAt(root.draftConfig.widget_order.indexOf(selectedKey));if(row)row.forceActiveFocus();else addWidgetButton.forceActiveFocus()}
    function applySettings(rearrange){settingsBody.forceActiveFocus();if(widgetEditorLoader.item)widgetEditorLoader.item.cancelEditing();if(stats.replacementPending)stats.applyReplacement();else if(page===3)stats.applyTopBar();else if(currentScope==="preferences")stats.applyPreferences();else if(rearrange===true)stats.rearrangeDesktop();else stats.applyDesktop()}
    function discardChanges(){settingsBody.forceActiveFocus();if(widgetEditorLoader.item)widgetEditorLoader.item.cancelEditing();if(stats.replacementPending)stats.cancelReplacement();else if(page===3)stats.revertTopBarDraft();else if(currentScope==="preferences")stats.revertPreferencesDraft();else stats.revertDesktopDraft()}
    function revealSelected(){const row=instanceRepeater.itemAt(root.draftConfig.widget_order.indexOf(selectedKey));if(row)revealInstance(row)}
    function revealInstance(item){const flick=added.contentItem;if(!flick || flick.contentY===undefined)return;const point=item.mapToItem(instanceColumn,0,0);if(point.y<flick.contentY)flick.contentY=point.y;else if(point.y+item.height>flick.contentY+added.availableHeight)flick.contentY=point.y+item.height-added.availableHeight}
    function textEditing(){const item=root.activeFocusItem;return !!item && item.cursorPosition!==undefined && item.text!==undefined}
    function undo(redo){if(widgetEditorLoader.item)widgetEditorLoader.item.cancelEditing();if(redo)stats.redoDraft();else stats.undoDraft()}
    Connections {target:stats;function onDraftChanged(){root.selectNext()}}
    Shortcut {sequence:"Ctrl+S";enabled:root.page!==4 && !gallery.opened && !scenePopup.opened && !topBarEditor.groupPopupOpen;onActivated:root.applySettings()}
    Shortcut {sequence:"Ctrl+N";enabled:!root.atWidgetLimit && !gallery.opened && !scenePopup.opened && !topBarEditor.groupPopupOpen;onActivated:root.showGallery()}
    Shortcut {sequence:"Ctrl+Z";enabled:root.page!==4 && !gallery.opened && !scenePopup.opened && !topBarEditor.groupPopupOpen && !root.textEditing();onActivated:root.undo(false)}
    Shortcut {sequence:"Ctrl+Shift+Z";enabled:root.page!==4 && !gallery.opened && !scenePopup.opened && !topBarEditor.groupPopupOpen && !root.textEditing();onActivated:root.undo(true)}
    Shortcut {sequence:"Escape";enabled:!gallery.opened && !scenePopup.opened && !topBarEditor.groupPopupOpen;onActivated:{if(root.page===4 && historyPage.cancelInspection())return;if(!widgetEditorLoader.item || !widgetEditorLoader.item.cancelEditing())root.hide()}}
    Timer {interval:3000;running:root.visible && (root.page===2 || stats.dirty);repeat:true;triggeredOnStart:true;onTriggered:stats.inspect()}
    Item {
        id:settingsBody;objectName:"settingsBackdropSource";y:root.clientY;width:root.width;height:root.clientHeight
        Rectangle {anchors.fill:parent;visible:!ui.translucentBackdrop;color:ui.fallback}
        GlassSurface {objectName:"settingsWindowSurface";x:ui.translucentBackdrop?root.railWidth:0;width:parent.width-x;height:parent.height;tone:"window"}
        GlassSurface {objectName:"settingsRailSurface";width:root.railWidth;height:parent.height;tone:"rail"}
        Rectangle {x:root.railWidth-1;width:1;height:parent.height;color:ui.line}
        Rectangle {objectName:"sidebarBrandReadingSurface";x:12;y:brandIdentity.y-8;width:root.railWidth-24;height:brandIdentity.implicitHeight+16;radius:8;border.width:0;color:ui.railReading}
        Row {
            id:brandIdentity;objectName:"sidebarBrandContent"
            x:20;y:26;spacing:10
            Image {source:"../assets/icon-32.svg";width:27;height:27;mipmap:true}
            Column {width:root.railWidth-76;spacing:4;Text {width:parent.width;text:"Desktop Stats";color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:Font.DemiBold;elide:Text.ElideRight}Text {width:parent.width;text:"WINDOWS · "+stats.version;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:9;font.letterSpacing:.3;elide:Text.ElideRight}}
        }
        Item {
            id:mainNavigation;x:12;y:94;width:root.railWidth-24;height:175
            Rectangle {objectName:"sidebarNavigationReadingSurface";anchors.fill:parent;radius:8;border.width:0;color:ui.railReading}
            Rectangle {
                objectName:"sidebarSelectionSurface";width:parent.width;height:40;y:root.page===0?0:root.page===3?45:root.page===4?90:135
                radius:7;color:ui.selection;border.color:ui.line
                Behavior on y {NumberAnimation {duration:root.visible && stats.motionEnabled?200:0;easing.type:Easing.OutCubic}}
            }
            Column {anchors.fill:parent;spacing:5
              Repeater {
                model:[{id:0,label:"桌面组件",icon:"grid"},{id:3,label:"顶部栏",icon:"sliders"},{id:4,label:"历史记录",icon:"time"},{id:1,label:"偏好",icon:"sliders"}]
                ItemDelegate {
                    id:nav;required property var modelData;required property int index;objectName:"nav_"+modelData.id
                    width:root.railWidth-24;height:40;leftPadding:12;rightPadding:10;focusPolicy:Qt.StrongFocus;onClicked:root.page=modelData.id
                    background:Rectangle {radius:7;color:nav.hovered && root.page!==nav.modelData.id?ui.hover:"transparent";border.color:nav.activeFocus?ui.accent:"transparent"}
                    contentItem:RowLayout {spacing:10;Icon {name:nav.modelData.icon;width:16;height:16;ink:root.page===nav.modelData.id?ui.accent:ui.muted}Text {Layout.fillWidth:true;text:ui.t(nav.modelData.label);color:ui.ink;font.family:ui.fontFamily;font.pixelSize:13;font.weight:root.page===nav.modelData.id || (root.page===2 && nav.modelData.id===1)?Font.DemiBold:Font.Normal;elide:Text.ElideRight}}
                    Accessible.name:ui.t(modelData.label);ToolTip.visible:hovered;ToolTip.text:ui.t(modelData.label);ToolTip.delay:600
                }
              }
            }
        }
        Rectangle {objectName:"sidebarWidgetsReadingSurface";x:12;y:283;width:root.railWidth-24;height:Math.min(Math.max(0,languageSelector.y-y-12),Math.max(44,added.y-y+Math.min(added.height,instanceColumn.implicitHeight)+6));radius:8;border.width:0;color:ui.railReading}
        RowLayout {
            objectName:"sidebarWidgetCountContent"
            x:22;y:291;width:root.railWidth-42;height:30
            Text {Layout.fillWidth:true;text:stats.catalog.instances.length+" "+ui.t("个小组件");color:ui.muted;font.family:ui.fontFamily;font.pixelSize:10;elide:Text.ElideRight}
            ActionButton {objectName:"openScenesButton";text:ui.t("场景");quiet:true;implicitWidth:42;implicitHeight:28;leftPadding:2;rightPadding:2;onClicked:scenePopup.open();ToolTip.visible:hovered;ToolTip.text:ui.t("场景方案")}
            ActionButton {id:addWidgetButton;objectName:"addWidgetButton";text:"＋";quiet:true;implicitWidth:28;implicitHeight:28;leftPadding:0;rightPadding:0;enabled:!root.atWidgetLimit;Accessible.name:ui.t("添加小组件");onClicked:root.showGallery();ToolTip.visible:hovered;ToolTip.text:root.atWidgetLimit?ui.t("最多添加 24 个小组件"):ui.t("添加小组件")}
        }
        ScrollView {
            id:added;objectName:"widgetListScroll";x:12;y:331;width:root.railWidth-24;height:Math.max(1,languageSelector.y-y-20)
            contentWidth:availableWidth;contentHeight:instanceColumn.implicitHeight;clip:true;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
            Column {
                id:instanceColumn;width:added.availableWidth;spacing:4
                Repeater {
                    id:instanceRepeater;model:stats.catalog.instances
                    ItemDelegate {
                        id:instance;required property var modelData;objectName:"widgetRow_"+modelData.id
                        width:instanceColumn.width;height:38;leftPadding:12;rightPadding:10;focusPolicy:Qt.StrongFocus;onClicked:root.selectWidget(modelData.id);onActiveFocusChanged:if(activeFocus)root.revealInstance(instance)
                        background:Rectangle {radius:7;color:root.page===0 && root.selectedKey===instance.modelData.id?ui.selection:instance.hovered?ui.hover:"transparent";border.color:instance.activeFocus?ui.accent:"transparent"}
                        contentItem:RowLayout {spacing:9;Icon {width:15;height:15;name:instance.modelData.kind;ink:instance.modelData.color;opacity:instance.modelData.enabled?1:.4}Text {Layout.fillWidth:true;text:instance.modelData.label;font.family:ui.fontFamily;font.pixelSize:12;font.weight:root.page===0 && root.selectedKey===instance.modelData.id?Font.DemiBold:Font.Normal;color:instance.modelData.enabled?ui.ink:ui.muted;elide:Text.ElideRight}}
                        Accessible.name:modelData.label;ToolTip.visible:hovered;ToolTip.text:modelData.label;ToolTip.delay:600
                    }
                }
            }
        }
        Rectangle {objectName:"sidebarFooterReadingSurface";x:12;y:languageSelector.y-7;width:root.railWidth-24;height:languageSelector.height+14;radius:8;border.width:0;color:ui.railReading}
        Column {id:languageSelector;objectName:"sidebarFooterContent";x:18;width:root.railWidth-36;anchors.bottom:parent.bottom;anchors.bottomMargin:22;spacing:7;Text {width:parent.width;text:stats.version;font.family:ui.fontFamily;font.pixelSize:ui.metaSize;color:ui.muted;elide:Text.ElideRight}}
        Item {x:root.railWidth;width:parent.width-x;height:parent.height-72-root.replacementBannerHeight;clip:true
        Item {
            id:workspace;width:root.layoutWidth-root.railWidth;height:root.layoutHeight-root.clientY-72-root.replacementBannerHeight
            Loader {id:widgetEditorLoader;anchors.fill:parent;active:!!root.draftConfig.widgets[root.selectedKey];visible:root.page===0;sourceComponent:WidgetEditor {selectedKey:root.selectedKey;active:root.visible && root.page===0;resizing:root.resizeInProgress;onRequestApply:root.applySettings();onRequestReadings:key=>gallery.showReadings(key);onSelectKey:key=>root.selectWidget(key)}}
            Column {visible:root.page===0 && !widgetEditorLoader.active;anchors.centerIn:parent;spacing:20;Text {text:ui.t("你的桌面，从一个小组件开始。");font.family:ui.fontFamily;font.pixelSize:18;color:ui.ink}ActionButton {anchors.horizontalCenter:parent.horizontalCenter;text:"＋ "+ui.t("添加第一个小组件");accent:true;onClicked:root.showGallery()}}
            ScrollView {id:appearanceScroll;objectName:"editorScroll";anchors.fill:parent;anchors.margins:28;visible:root.page===1;contentWidth:availableWidth;clip:true;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                Column {objectName:"appearanceContentColumn";width:Math.min(620,appearanceScroll.availableWidth-8);x:(appearanceScroll.availableWidth-width)/2;spacing:25
                    Text {text:ui.t("偏好");font.family:ui.fontFamily;font.pixelSize:ui.titleSize;font.weight:Font.DemiBold;color:ui.ink}
                    InspectorSection {width:parent.width;title:ui.t("常规")
                        SettingRow {Layout.fillWidth:true;label:ui.t("显示语言");Choice {objectName:"languageChoice";width:200;model:stats.catalog.languages;value:root.draftConfig.language;onPicked:selected=>stats.change("language",selected)}}
                        SettingRow {Layout.fillWidth:true;label:ui.t("外观模式");OptionTabs {options:[{id:"light",label:ui.t("浅色")},{id:"dark",label:ui.t("深色")}];value:root.draftConfig.theme;onPicked:selected=>stats.change("theme",selected)}}
                        SettingRow {Layout.fillWidth:true;label:ui.t("登录时自动启动");Toggle {objectName:"autostartToggle";checked:root.draftConfig.autostart;Accessible.name:ui.t("登录时自动启动");onToggled:stats.change("autostart",checked)}}
                        SettingRow {Layout.fillWidth:true;label:ui.t("检测频率");note:ui.t("范围：0.01–5 秒");SamplingControl {id:frequency}}
                        Text {Layout.fillWidth:true;text:ui.t("更短的间隔会增加系统开销。应用后从下一轮采样生效。");font.family:ui.fontFamily;font.pixelSize:ui.captionSize;color:ui.muted;wrapMode:Text.WordWrap}
                    }
                    Rectangle {width:parent.width;height:1;color:ui.line}
                    ActionButton {objectName:"nav_2";text:ui.t("传感器与来源")+"  ›";quiet:true;onClicked:root.page=2}
                    ActionButton {objectName:"preferenceScenesButton";text:ui.t("场景方案")+"  ›";quiet:true;onClicked:scenePopup.open()}
                    Flow {width:parent.width;spacing:8;ActionButton {objectName:"importSettingsButton";text:ui.t("导入设置");quiet:true;onClicked:stats.importSettings()}ActionButton {objectName:"exportSettingsButton";text:ui.t("导出设置");quiet:true;onClicked:stats.exportSettings()}ActionButton {objectName:"resetSettingsButton";text:ui.t("恢复默认");quiet:true;onClicked:stats.reset()}}
                }
            }
            Item {id:topBarHeaderHost;objectName:"topBarHeaderHost";x:28+(parent.width-56-width)/2;y:28;width:Math.min(1000,parent.width-64);height:topBarEditor.headerHeight;visible:root.page===3;z:30}
            ScrollView {id:topBarScroll;objectName:"topBarSettingsScroll";anchors.fill:parent;anchors.margins:28;anchors.topMargin:28+topBarHeaderHost.height+16;visible:root.page===3;contentWidth:availableWidth;clip:true;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                TopBarSettings {id:topBarEditor;width:Math.min(1000,topBarScroll.availableWidth-8);x:(topBarScroll.availableWidth-width)/2;active:root.visible && root.page===3;viewportY:topBarScroll.contentItem?topBarScroll.contentItem.contentY:0;scrollHost:topBarScroll.contentItem;headerHost:topBarHeaderHost
                    onRevealInspector:item=>{const flick=topBarScroll.contentItem;if(item && flick){const top=item.mapToItem(topBarEditor,0,0).y;const bottom=top+item.height;let target=flick.contentY;if(item.height>flick.height-16 || top<target+8)target=top-8;else if(bottom>target+flick.height-8)target=bottom-flick.height+8;flick.contentY=Math.max(0,Math.min(Math.max(0,flick.contentHeight-flick.height),target))}}
                }
            }
            ColumnLayout {
                id:sensorPage;visible:root.page===2;width:Math.min(900,parent.width-52);height:parent.height-52;x:(parent.width-width)/2;y:26;spacing:16
                RowLayout {
                    Layout.fillWidth:true;spacing:14
                    ColumnLayout {Layout.fillWidth:true;spacing:6;ActionButton {objectName:"sensorBackButton";text:"‹ "+ui.t("偏好");quiet:true;implicitHeight:28;leftPadding:0;onClicked:root.page=1}Text {text:ui.t("传感器");font.family:ui.fontFamily;font.pixelSize:25;font.weight:Font.DemiBold;color:ui.ink}Text {Layout.fillWidth:true;text:ui.t("查看真实读数与数据来源。");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap}}
                }
                Text {Layout.fillWidth:true;text:ui.t("硬件传感器的实际更新速度可能更慢。");font.family:ui.fontFamily;font.pixelSize:ui.captionSize;color:ui.muted;wrapMode:Text.WordWrap}
                SensorBrowser {objectName:"sensorBrowser";active:root.visible && root.page===2;Layout.fillWidth:true;Layout.fillHeight:true}
            }
            HistoryPage {id:historyPage;anchors.fill:parent;visible:root.page===4;active:root.visible && root.page===4}
        }}
        Rectangle {objectName:"replacementPreviewBanner";x:root.railWidth;y:parent.height-72-root.replacementBannerHeight;width:parent.width-x;height:root.replacementBannerHeight;visible:stats.replacementPending;color:ui.selection
            Text {anchors.fill:parent;anchors.leftMargin:28;anchors.rightMargin:28;text:ui.t("将替换全部设置");verticalAlignment:Text.AlignVCenter;font.family:ui.fontFamily;font.pixelSize:ui.captionSize;font.weight:Font.Medium;color:ui.ink}
        }
        Rectangle {x:root.railWidth;y:parent.height-72;width:parent.width-x;height:1;color:ui.line}
        RowLayout {x:root.railWidth+28;y:parent.height-54;width:parent.width-x-28;height:36;spacing:12
            Text {objectName:"saveStateText";Layout.fillWidth:true;text:stats.commitError || (root.page===4?ui.t("历史记录与布局设置独立保存"):root.currentDirty?ui.t("设置尚未应用"):ui.t("设置已同步"));font.family:ui.fontFamily;font.pixelSize:ui.captionSize;color:stats.commitError?ui.ink:ui.muted;elide:Text.ElideRight;ToolTip.visible:saveHover.containsMouse && !!stats.commitError;ToolTip.text:stats.commitError;MouseArea {id:saveHover;anchors.fill:parent;hoverEnabled:true;acceptedButtons:Qt.NoButton}}
            ActionButton {objectName:"historySourcesButton";visible:root.page===4;text:ui.t("传感器与来源")+"  ›";quiet:true;onClicked:root.page=2}
            ActionButton {objectName:"revertButton";visible:root.page!==4;text:ui.t(stats.replacementPending?"取消全部预览":"恢复");quiet:true;enabled:root.currentDirty;onClicked:root.discardChanges();ToolTip.visible:hovered;ToolTip.text:ui.t("恢复已应用")}
            ActionButton {objectName:"applyButton";visible:root.page!==4;text:ui.t(stats.replacementPending?"应用全部设置":root.page===3?"应用顶部栏":root.currentScope==="preferences"?"应用偏好":"应用到桌面");accent:true;onClicked:root.applySettings()}
        }
    }
    WindowChrome {anchors.fill:parent;visible:!root.nativeHosted;enabled:visible;targetWindow:root;titleText:"Desktop Stats"}
    Gallery {id:gallery;backdropSource:settingsBody;onDismissed:root.restoreGalleryFocus();onChosen:key=>root.selectWidget(key)}
    Popup {
        id:scenePopup;objectName:"scenePopup";parent:Overlay.overlay
        property string selectedId:""
        property var proposal:({})
        property string confirmId:""
        width:Math.min(860,parent.width-40);height:Math.min(740,parent.height-40)
        x:(parent.width-width)/2;y:(parent.height-height)/2;padding:20;modal:true;focus:true
        background:GlassSurface {tone:"popup"}
        onOpened:{stats.refreshScenes();confirmId="";proposal=selectedId?stats.scenePreview(selectedId):({})}
        function useScene(identifier){
            if((stats.scopeDirty.desktop || stats.scopeDirty.topbar) && confirmId!==identifier){confirmId=identifier;return}
            if(stats.applyScene(identifier)){confirmId="";close()}
        }
        ColumnLayout {anchors.fill:parent;spacing:12
            RowLayout {Layout.fillWidth:true
                Text {Layout.fillWidth:true;text:ui.t("场景方案");color:ui.ink;font.family:ui.fontFamily;font.pixelSize:20;font.weight:Font.DemiBold}
                IconButton {symbol:"close";label:ui.t("关闭");onClicked:scenePopup.close()}
            }
            ColumnLayout {Layout.fillWidth:true;visible:!!scenePopup.selectedId;spacing:6
                ScenePreview {objectName:"selectedSceneLivePreview";Layout.fillWidth:true;Layout.preferredHeight:150;proposal:scenePopup.proposal;readings:scenePopup.opened?stats.readings:({})}
                Text {Layout.fillWidth:true;text:ui.t("当前读数预览 · 尚未应用");font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted}
            }
            ScrollView {id:sceneScroll;objectName:"scenePickerScroll";Layout.fillWidth:true;Layout.fillHeight:true;contentWidth:availableWidth;clip:true;ScrollBar.horizontal.policy:ScrollBar.AlwaysOff
                ScenarioPicker {id:scenarioPicker;width:sceneScroll.availableWidth-8;scenarios:stats.scenes;selectedId:scenePopup.selectedId;appliedId:stats.appliedSceneId;errorText:stats.sceneError;showHeading:false
                    onPreviewRequested:identifier=>{scenePopup.selectedId=identifier;scenePopup.confirmId="";scenePopup.proposal=stats.scenePreview(identifier)}
                    onApplyRequested:identifier=>scenePopup.useScene(identifier)
                    onSaveRequested:name=>stats.saveScene(name)
                    onRemoveRequested:identifier=>{if(stats.removeScene(identifier) && scenePopup.selectedId===identifier){scenePopup.selectedId="";scenePopup.proposal=({});scenePopup.confirmId=""}}
                }
            }
            Text {Layout.fillWidth:true;text:ui.t("切换桌面组件与顶部栏，保留语言和采样设置；可用“上次布局”恢复。");font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
            ColumnLayout {Layout.fillWidth:true;visible:!!scenePopup.confirmId;spacing:8
                Text {Layout.fillWidth:true;text:ui.t("这会替换尚未应用的桌面与顶部栏修改。");font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;wrapMode:Text.WordWrap}
                RowLayout {Layout.alignment:Qt.AlignRight
                    ActionButton {text:ui.t("取消");quiet:true;onClicked:scenePopup.confirmId=""}
                    ActionButton {objectName:"confirmSceneApply";text:ui.t("确认使用");accent:true;onClicked:scenePopup.useScene(scenePopup.confirmId)}
                }
            }
        }
    }
}
