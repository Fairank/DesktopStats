import QtQuick
import QtQuick.Layouts
ColumnLayout {
    id:root
    property string widgetKey:""
    readonly property var prefs:stats.draft.widgets[widgetKey] || ({})
    readonly property string effectiveSkin:widgetKey.length>0 ? (prefs.skin || stats.draft.skin) : stats.draft.skin
    spacing:4
    Theme { id:ui }
    Text {
        visible:root.widgetKey.length>0; Layout.fillWidth:true
        text:ui.t("跟随全局"); horizontalAlignment:Text.AlignRight
        color:ui.muted; font.family:ui.fontFamily; font.pixelSize:10
    }
    GlassControl { Layout.fillWidth:true; field:"glass_transparency"; label:ui.t("玻璃透明度"); widgetKey:root.widgetKey }
    GlassControl { Layout.fillWidth:true; field:"glass_curvature"; label:ui.t("圆角曲率"); widgetKey:root.widgetKey }
    Text {
        Layout.fillWidth:true; Layout.topMargin:3
        text:(["glass","frost","tint"].includes(root.effectiveSkin) ? "" : ui.t("两项控制仅用于玻璃皮肤。")+" ")+ui.t("实色回退时保留可读底色。")
        color:ui.muted; font.family:ui.fontFamily; font.pixelSize:11; wrapMode:Text.WordWrap
    }
}
