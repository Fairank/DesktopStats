import QtQuick
import QtQuick.Controls
CheckBox {
    id:control
    Theme {id:ui}
    padding:0;spacing:6;implicitHeight:28
    font.family:ui.fontFamily;font.pixelSize:ui.captionSize
    indicator:Rectangle {x:0;y:(control.height-height)/2;width:15;height:15;radius:4;color:control.checked?ui.accentFill:"transparent";border.color:control.checked?ui.accentFill:ui.muted;border.width:1;opacity:control.enabled?1:.45;Icon {anchors.fill:parent;anchors.margins:2;name:"check";ink:"white";visible:control.checked}Rectangle {anchors.fill:parent;anchors.margins:-3;radius:6;color:"transparent";border.color:ui.accent;visible:control.activeFocus}}
    contentItem:Text {text:control.text;font:control.font;color:control.enabled?ui.ink:ui.muted;leftPadding:control.indicator.width+control.spacing;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
}
