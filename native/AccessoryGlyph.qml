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
    readonly property real previewScale:art.kind==="psu"?1.35:1
    readonly property real unit: Math.min(width/120,height/100)*previewScale
    readonly property real artworkLeft: (width-120*unit)/2
    readonly property real artworkTop: height/2-(art.kind==="psu"?41:50)*unit
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
            id:rotorLayer
            required property var modelData
            x:root.artworkLeft;y:root.artworkTop;width:120*root.unit;height:100*root.unit
        Item {
            id:rotorPlane
            readonly property var modelData:rotorLayer.modelData
            readonly property var affine:modelData.affine || null
            readonly property real diameter:Math.max(modelData.width,modelData.height)*root.unit
            readonly property int rasterSize:Math.max(1,Math.ceil((affine?100*root.unit*Math.hypot(affine[0],affine[1],affine[2],affine[3]):diameter)*Screen.devicePixelRatio))
            x:affine?0:modelData.x*root.unit
            y:affine?0:modelData.y*root.unit
            width:affine?100*root.unit:diameter;height:width
            transform:Matrix4x4 {matrix:rotorPlane.affine?
                Qt.matrix4x4(rotorPlane.affine[0],rotorPlane.affine[2],0,rotorPlane.affine[4]*root.unit,
                             rotorPlane.affine[1],rotorPlane.affine[3],0,rotorPlane.affine[5]*root.unit,
                             0,0,1,0,0,0,0,1):
                Qt.matrix4x4(rotorPlane.modelData.width/Math.max(rotorPlane.modelData.width,rotorPlane.modelData.height),0,0,0,
                             0,rotorPlane.modelData.height/Math.max(rotorPlane.modelData.width,rotorPlane.modelData.height),0,0,
                             0,0,1,0,0,0,0,1)}
            Image {
                objectName:"accessoryRotorImage"
                anchors.fill:parent;source:root.source(modelData.svg)
                sourceSize:Qt.size(rotorPlane.rasterSize,rotorPlane.rasterSize)
                cache:false;asynchronous:false
                rotation:root.phase*(modelData.direction===-1?-1:1)
                transformOrigin:Item.Center
            }
        }
        Image {
            objectName:"accessoryRotorOcclusionImage"
            anchors.fill:parent;visible:!!rotorLayer.modelData.after_svg
            source:root.source(rotorLayer.modelData.after_svg)
            sourceSize:Qt.size(Math.max(1,Math.ceil(width*Screen.devicePixelRatio)),Math.max(1,Math.ceil(height*Screen.devicePixelRatio)))
            cache:false;asynchronous:false;fillMode:Image.PreserveAspectFit
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
