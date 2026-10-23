import QtQuick
import QtQuick.Window

// Decorative chrome only. All geometry and input stay with the bar's owner.
Item {
    id:root
    property string design:"classic"
    property string role:"metric"
    property color ink:"#202833"
    property color accent:"#006fe6"
    property bool hovered:false
    property bool pressed:false
    property bool selected:false
    property bool pinned:false
    property bool dragged:false
    property bool focused:false
    // Only decorative color transitions; never fade a native material or move a hit target.
    property bool motionEnabled:false
    readonly property bool capsule:design==="capsule"
    readonly property bool instrument:design==="instrument"
    readonly property bool band:role==="band"
    readonly property bool engaged:selected || pinned
    readonly property real hairline:1/Math.max(1,Screen.devicePixelRatio)
    readonly property real inset:instrument?1:2
    function tone(color,alpha){return Qt.rgba(color.r,color.g,color.b,alpha)}

    Rectangle {
        id:pane
        objectName:"topBarChromePane"
        x:root.inset;y:root.inset
        width:Math.max(0,root.width-root.inset*2);height:Math.max(0,root.height-root.inset*2)
        radius:root.capsule?Math.min(13,height/2):root.instrument?3:5
        visible:!root.band
        color:root.pressed?root.tone(root.ink,.13):root.engaged?root.tone(root.accent,root.capsule?.13:.09)
            :root.hovered?root.tone(root.ink,root.capsule?.10:.075)
            :root.tone(root.ink,root.capsule?.05:root.instrument?.025:0)
        border.width:root.focused || root.engaged || root.dragged?1:root.capsule || root.instrument?root.hairline:0
        border.color:root.focused || root.engaged || root.dragged?root.tone(root.accent,.7):root.tone(root.ink,root.capsule?.11:.095)
        Behavior on color {
            enabled:root.motionEnabled && root.visible && !!root.Window.window && root.Window.window.visible
            ColorAnimation { duration:110; easing.type:Easing.OutCubic }
        }
    }
    Rectangle {
        objectName:"topBarChromeBottomEdge"
        visible:root.band
        x:0;y:Math.max(0,root.height-root.hairline);width:root.width;height:root.hairline
        color:root.tone(root.ink,root.instrument?.18:.085)
    }
    Rectangle {
        objectName:"topBarChromeTopEdge"
        visible:root.band && root.instrument
        x:0;y:0;width:root.width;height:root.hairline;color:root.tone(root.ink,.09)
    }
    Rectangle {
        objectName:"topBarChromeInstrumentRail"
        visible:!root.band && root.instrument
        x:pane.x+4;y:Math.max(pane.y,pane.y+pane.height-2)
        width:Math.max(0,pane.width-8);height:root.hairline
        color:root.tone(root.ink,.16)
    }
    Rectangle {
        objectName:"topBarChromeInstrumentMarker"
        visible:!root.band && root.instrument && (root.hovered || root.pressed || root.engaged || root.focused || root.dragged)
        x:pane.x+4;y:Math.max(pane.y,pane.y+pane.height-2)
        width:Math.min(7,Math.max(0,pane.width-8));height:root.hairline;color:root.accent
    }
}
