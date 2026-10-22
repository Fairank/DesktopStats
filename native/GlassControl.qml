import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
RowLayout {
    id:root
    objectName:(local?"glassControl_local_":"glassControl_global_")+field
    required property string field
    required property string label
    property string widgetKey:""
    readonly property bool local:widgetKey.length>0
    readonly property var prefs:stats.draft.widgets[widgetKey] || ({})
    readonly property var overrideValue:prefs[field]
    readonly property bool inherited:overrideValue===null || overrideValue===undefined
    readonly property real globalValue:Number.isFinite(stats.draft[field]) ? stats.draft[field] : 50
    readonly property real resolvedValue:local && !inherited ? overrideValue : globalValue
    readonly property string effectiveSkin:local ? (prefs.skin || stats.draft.skin) : stats.draft.skin
    readonly property bool supported:["glass","frost","tint"].includes(effectiveSkin)
    function commitValue(value) {
        if(root.local)stats.changeWidget(root.widgetKey,root.field,value)
        else stats.change(root.field,value)
    }
    spacing:10
    implicitHeight:Math.max(34,caption.implicitHeight)
    Theme { id:ui }
    Text {
        id:caption
        Layout.fillWidth:true; Layout.minimumWidth:70
        text:root.label; color:ui.ink; font.family:ui.fontFamily; font.pixelSize:13
        wrapMode:Text.WordWrap
    }
    Text {
        Layout.preferredWidth:43
        text:root.resolvedValue.toLocaleString(Qt.locale(stats.language),"f",1)+"%"
        horizontalAlignment:Text.AlignRight
        color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11
    }
    ValueSlider {
        objectName:(root.local?"local_":"global_")+root.field
        Layout.preferredWidth:root.width>=500 ? 164 : 140
        from:0; to:100; stepSize:.1; snapMode:Slider.NoSnap
        value:root.resolvedValue; enabled:root.supported && (!root.local || !root.inherited)
        opacity:enabled?1:.45
        Accessible.name:root.label
        Accessible.description:root.local && root.inherited ? ui.t("跟随全局") : ""
        onMoved:root.commitValue(value)
        Keys.onPressed:event=>{
            if(event.key===Qt.Key_Home) {root.commitValue(0);event.accepted=true}
            else if(event.key===Qt.Key_End) {root.commitValue(100);event.accepted=true}
        }
    }
    Toggle {
        objectName:(root.local?"inherit_":"unused_inherit_")+root.field
        visible:root.local
        checked:root.inherited
        Accessible.name:root.label+" · "+ui.t("跟随全局")
        onToggled:stats.changeWidget(root.widgetKey,root.field,checked?null:root.resolvedValue)
        ToolTip.visible:hovered
        ToolTip.text:ui.t("跟随全局")
        ToolTip.delay:600
    }
}
