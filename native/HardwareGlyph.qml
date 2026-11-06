import QtQuick
import QtQuick.Window
import "HardwareShapes.js" as Shapes

// Retained artwork. Motion rotates only prebuilt local fan textures; neither
// a new reading nor an animation tick rebuilds the SVG or discovers hardware.
Item {
    id: root
    property var appearance: ({})
    property color ink: "#69788c"
    property bool fanMotionEnabled: false
    property real fanRotation: 0
    property bool glyphReady: false
    readonly property bool classic: appearance && appearance.icon_set === "classic"
    readonly property string geometryKey: classic ? "" : Shapes.key(appearance, ink)
    readonly property url svgSource: classic ? "" : Shapes.source(geometryKey)
    readonly property bool fanShapeEligible: !classic && appearance && appearance.kind === "gpu"
        && ["solid", "miniature", "soft", "cartoon"].includes(appearance.icon_set)
    readonly property bool wideGpu: appearance && appearance.kind === "gpu"
        && ["solid", "miniature", "soft", "cartoon"].includes(appearance.icon_set)
        && root.width > root.height
    readonly property var fanLayerData: fanMotionEnabled && fanShapeEligible
        ? Shapes.layers(geometryKey) : null
    readonly property bool windowVisible: root.Window.window !== null
        && root.Window.window.visible && root.Window.window.visibility !== Window.Minimized
    readonly property bool exposed: {
        if (!root.glyphReady || !root.visible || !(root.width > 0 && root.height > 0)) return false
        for (let item=root;item;item=item.parent)
            if (item.opacity <= 0) return false
        return true
    }
    readonly property bool fanMotionActive: !!(fanMotionEnabled && fanShapeEligible && exposed && windowVisible
        && Number.isFinite(fanRotation) && fanLayerData && fanLayerData.rotors.length > 0)
    readonly property real artworkUnit: (wideGpu ? Math.max(root.width,root.height) : Math.min(root.width,root.height))/24
    readonly property real artworkLeft: (root.width-artworkUnit*24)/2
    readonly property real artworkTop: (root.height-artworkUnit*24)/2
    implicitWidth: 18
    implicitHeight: 18
    Component.onCompleted: glyphReady=true

    Loader {
        objectName: "hardwareClassicGlyphLoader"
        anchors.fill: parent
        active: root.classic
        sourceComponent: Icon {
            name: root.appearance.kind === "gpu" ? "gpu" : root.appearance.kind === "memory" ? "memory" : "cpu"
            ink: root.ink
        }
    }

    Image {
        objectName: "hardwareGlyphImage"
        anchors.fill: parent
        visible: !root.classic
        source: root.fanMotionActive ? root.fanLayerData.baseSource : root.svgSource
        opacity: root.ink.a
        sourceSize.width: Math.max(1, Math.ceil((root.wideGpu ? Math.max(root.width,root.height) : root.width) * Screen.devicePixelRatio))
        sourceSize.height: Math.max(1, Math.ceil((root.wideGpu ? Math.max(root.width,root.height) : root.height) * Screen.devicePixelRatio))
        fillMode: root.wideGpu ? Image.PreserveAspectCrop : Image.PreserveAspectFit
        asynchronous: false
        cache: true
        smooth: true
        mipmap: false
    }

    Loader {
        objectName: "hardwareFanMotionLoader"
        anchors.fill: parent
        active: root.fanMotionActive
        sourceComponent: Item {
            Repeater {
                model: root.fanLayerData ? root.fanLayerData.rotors : []
                delegate: Item {
                    id: rotor
                    required property int index
                    required property var modelData
                    objectName: "hardwareFanRotor_"+index
                    x: root.artworkLeft+(modelData.cx-modelData.radius)*root.artworkUnit
                    y: root.artworkTop+(modelData.cy-modelData.radius)*root.artworkUnit
                    width: modelData.radius*2*root.artworkUnit
                    height: width
                    transformOrigin: Item.Center
                    rotation: Number.isFinite(root.fanRotation)
                        ? (((root.fanRotation*(modelData.direction===-1?-1:1))%360)+360)%360 : 0
                    Image {
                        objectName: "hardwareFanRotorImage_"+rotor.index
                        anchors.fill: parent
                        source: rotor.modelData.source
                        opacity: root.ink.a
                        sourceSize.width: Math.max(1,Math.ceil(rotor.width*Screen.devicePixelRatio))
                        sourceSize.height: Math.max(1,Math.ceil(rotor.height*Screen.devicePixelRatio))
                        fillMode: Image.PreserveAspectFit
                        asynchronous: false; cache: true; smooth: true; mipmap: false
                    }
                }
            }
        }
    }
}
