import QtQuick
import QtQuick.Controls

Item {
    id:root
    objectName:"sceneLivePreview"
    property var proposal:({})
    property var readings:({})
    readonly property var windows:(proposal.windows || []).slice(0,3)
    readonly property real totalWidth:windows.reduce((sum,row)=>sum+row.width,0)+Math.max(0,windows.length-1)*14
    readonly property real tallest:windows.reduce((height,row)=>Math.max(height,row.height),1)
    readonly property real viewScale:Math.min(1,(width-32)/Math.max(1,totalWidth),(height-32)/Math.max(1,tallest))
    implicitHeight:172
    clip:true
    Theme {id:ui}
    Rectangle {anchors.fill:parent;radius:12;color:ui.previewCanvas;border.color:ui.line}
    Row {
        x:Math.max(16,(root.width-root.totalWidth*root.viewScale)/2)
        y:Math.max(16,(root.height-root.tallest*root.viewScale)/2)
        spacing:14*root.viewScale
        Repeater {
            model:root.windows
            Item {
                id:panel
                required property var modelData
                width:modelData.width*root.viewScale;height:modelData.height*root.viewScale
                Repeater {
                    model:panel.modelData.cells
                    WidgetPreview {
                        required property var modelData
                        objectName:"sceneLiveWidget_"+modelData.key
                        x:modelData.x*root.viewScale;y:modelData.y*root.viewScale
                        width:modelData.width*root.viewScale;height:modelData.height*root.viewScale
                        moduleKey:modelData.key;config:root.proposal.config || ({})
                        previewInfo:({width:modelData.width,height:modelData.height})
                        readings:root.readings;renderScale:root.viewScale
                    }
                }
            }
        }
    }
    Text {anchors.centerIn:parent;visible:root.windows.length===0;text:ui.t("此场景没有启用的桌面组件");font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted}
    Text {anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:8;visible:(root.proposal.windows || []).length>3;text:"＋ "+Math.max(0,(root.proposal.windows || []).length-3);font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted}
}
