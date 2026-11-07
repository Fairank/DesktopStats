import QtQuick
import QtQuick.Window

// Lightweight retained SVG layers. Animation changes transforms only and is
// driven by the gallery's single, explicitly enabled demonstration clock.
Item {
    id: root
    property var art: ({})
    property bool motion: false
    property real phase: 0
    readonly property var rotors: art.rotors || []
    readonly property bool moving: motion && rotors.length>0
    readonly property real unit: Math.min(width/120,height/100)
    readonly property real artworkLeft: (width-120*unit)/2
    readonly property real artworkTop: (height-100*unit)/2
    implicitWidth: 180
    implicitHeight: 150
    function source(svg) {return typeof svg==="string" && svg.length?"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(svg):""}
    Image {
        objectName:"accessoryStaticImage"
        x:root.artworkLeft;y:root.artworkTop;width:120*root.unit;height:100*root.unit
        source:root.source(root.moving?root.art.body_svg:root.art.svg)
        sourceSize.width:Math.max(1,Math.ceil(width*Screen.devicePixelRatio))
        sourceSize.height:Math.max(1,Math.ceil(height*Screen.devicePixelRatio))
        fillMode:Image.PreserveAspectFit;cache:false;asynchronous:false
    }
    Repeater {
        model:root.moving?root.rotors:[]
        Item {
            id:rotorPlane
            required property var modelData
            readonly property real diameter:Math.max(modelData.width,modelData.height)*root.unit
            readonly property int rasterSize:Math.max(1,Math.ceil(diameter*Screen.devicePixelRatio))
            x:root.artworkLeft+modelData.x*root.unit
            y:root.artworkTop+modelData.y*root.unit
            width:diameter;height:diameter
            transform:Scale {xScale:modelData.width/Math.max(modelData.width,modelData.height);yScale:modelData.height/Math.max(modelData.width,modelData.height)}
            Image {
                objectName:"accessoryRotorImage"
                anchors.fill:parent;source:root.source(modelData.svg)
                sourceSize:Qt.size(rotorPlane.rasterSize,rotorPlane.rasterSize)
                cache:false;asynchronous:false
                rotation:root.phase*(modelData.direction===-1?-1:1)
                transformOrigin:Item.Center
            }
        }
    }
    Image {
        objectName:"accessoryForegroundImage"
        x:root.artworkLeft;y:root.artworkTop;width:120*root.unit;height:100*root.unit;visible:root.moving
        source:root.moving?root.source(root.art.foreground_svg):""
        sourceSize.width:Math.max(1,Math.ceil(width*Screen.devicePixelRatio))
        sourceSize.height:Math.max(1,Math.ceil(height*Screen.devicePixelRatio))
        fillMode:Image.PreserveAspectFit;cache:false;asynchronous:false
    }
}
