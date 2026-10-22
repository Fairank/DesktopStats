import QtQuick
import QtQuick.Controls
Row {
    id:root
    property bool ready:false
    readonly property bool pendingInput:ready && field.contentItem.text!==field.textFromValue(field.value,field.locale)
    spacing:8
    Theme {id:ui}
    Component.onCompleted:Qt.callLater(()=>root.ready=true)
    SpinBox {
        id:field;objectName:"samplingIntervalChoice";width:126;implicitHeight:34;from:1;to:500;stepSize:1;editable:true;wheelEnabled:activeFocus
        value:Math.round(stats.draft.refresh*100);locale:Qt.locale(stats.language);Accessible.name:ui.t("检测频率");Accessible.description:ui.t("范围：0.01–5 秒");font.family:ui.fontFamily;font.pixelSize:ui.bodySize;leftPadding:29;rightPadding:29;inputMethodHints:Qt.ImhFormattedNumbersOnly
        validator:DoubleValidator {bottom:.01;top:5;decimals:2;notation:DoubleValidator.StandardNotation;locale:field.locale.name}
        textFromValue:function(value,locale){return Number(value/100).toLocaleString(locale,"f",2)}
        valueFromText:function(text,locale){try{const parsed=Number.fromLocaleString(locale,text);return isFinite(parsed)?Math.round(parsed*100):field.value}catch(error){return field.value}}
        onValueModified:stats.change("refresh",value/100)
        contentItem:TextInput {objectName:"samplingIntervalInput";text:field.displayText;font:field.font;color:ui.ink;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;readOnly:!field.editable;validator:field.validator;inputMethodHints:field.inputMethodHints;selectByMouse:true;selectionColor:ui.accent;selectedTextColor:"white"}
        up.indicator:Rectangle {x:field.width-width;width:29;height:field.height;radius:8;color:field.up.pressed?ui.selection:field.up.hovered?ui.hover:"transparent";opacity:field.value<field.to?1:.35;Rectangle {anchors.centerIn:parent;width:10;height:1;color:ui.ink}Rectangle {anchors.centerIn:parent;width:1;height:10;color:ui.ink}}
        down.indicator:Rectangle {width:29;height:field.height;radius:8;color:field.down.pressed?ui.selection:field.down.hovered?ui.hover:"transparent";opacity:field.value>field.from?1:.35;Rectangle {anchors.centerIn:parent;width:10;height:1;color:ui.ink}}
        background:GlassSurface {tone:"field";radius:8;focused:field.activeFocus;highlighted:field.hovered}
    }
    Text {text:ui.t("秒");height:34;verticalAlignment:Text.AlignVCenter;color:ui.muted;font.family:ui.fontFamily;font.pixelSize:ui.captionSize}
}
