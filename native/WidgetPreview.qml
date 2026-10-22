import QtQuick
import DesktopStats 1.0
Item {
    id: root
    property string moduleKey: ""
    property var config: ({})
    property var previewInfo: ({})
    property var readings: ({})
    property var history: []
    property real renderScale: 1
    clip: true
    Item {
        id: plane
        width: root.previewInfo.width || root.width
        height: root.previewInfo.height || root.height
        scale: root.width / Math.max(1,width)
        transformOrigin: Item.TopLeft
        MaterialSurface {
            visible: !!root.previewInfo.panel_skin
            x: -(root.previewInfo.cell_x || 0)
            y: -(root.previewInfo.cell_y || 0)
            width: root.previewInfo.panel_width || plane.width
            height: root.previewInfo.panel_height || plane.height
            config: {
                const cfg=Object.assign({},root.config)
                cfg.skin=root.previewInfo.panel_skin || cfg.skin
                const options=root.previewInfo.panel_options || ({})
                if(options.transparency!==undefined)cfg.glass_transparency=options.transparency
                if(options.curvature!==undefined)cfg.glass_curvature=options.curvature
                return cfg
            }
            frosted: root.previewInfo.coating_translucent===true
        }
        HardwareCard {
            anchors.fill: parent
            moduleKey: root.moduleKey; config: root.config
            readings: root.readings; history: root.history
            surface: root.previewInfo.card_surfaces!==false
            frosted: root.previewInfo.coating_translucent===true
            textureSize: Qt.size(Math.max(1,Math.round(width*Math.min(Math.max(1,root.renderScale),2048/Math.max(1,width),2048/Math.max(1,height),Math.sqrt(2000000/Math.max(1,width*height))))),
                                 Math.max(1,Math.round(height*Math.min(Math.max(1,root.renderScale),2048/Math.max(1,width),2048/Math.max(1,height),Math.sqrt(2000000/Math.max(1,width*height))))))
        }
    }
}
