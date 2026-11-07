import QtQuick
import QtQuick.Window
import "HardwareShapes.js" as Shapes
import "HardwareCpuPackages.js" as Cpu

// Retained artwork. Motion rotates only prebuilt local fan textures; neither
// a new reading nor an animation tick rebuilds the SVG or discovers hardware.
Item {
    id: root
    property var appearance: ({})
    property bool modelMode: false
    property color ink: "#69788c"
    property bool fanMotionEnabled: false
    property real fanRotation: 0
    property bool glyphReady: false
    readonly property bool classic: !modelMode && appearance && appearance.icon_set === "classic"
        && !(appearance.kind === "cpu" && Cpu.key(appearance))
    readonly property var geometryInput: modelMode ? Object.assign({},appearance,{model_mode:true}) : appearance
    readonly property string geometryKey: classic ? "" : Shapes.key(geometryInput, ink)
    // Models already build a retained base plus local rotors below. Reuse that
    // base instead of also generating/retaining an unused whole-card SVG.
    // CPU and ordinary small icons keep their original source path.
    readonly property url svgSource: classic ? "" : modelMode && fanLayerData
        ? fanLayerData.baseSource : Shapes.source(geometryKey)
    readonly property bool fanShapeEligible: !classic && appearance && appearance.kind === "gpu"
        && (["solid", "miniature", "soft", "cartoon", "sketch", "notebook_line", "notebook_color", "notebook_smile", "sticker", "papercut", "inkwash"].includes(appearance.icon_set)
            || modelMode && ["classic","outline"].includes(appearance.icon_set))
    readonly property bool wideGpu: appearance && appearance.kind === "gpu"
        && (["solid", "miniature", "soft", "cartoon", "sketch", "notebook_line", "notebook_color", "notebook_smile", "sticker", "papercut", "inkwash"].includes(appearance.icon_set)
            || modelMode && ["classic","outline"].includes(appearance.icon_set))
        && root.width > root.height
    readonly property var fanLayerData: (modelMode || fanMotionEnabled) && fanShapeEligible
        ? Shapes.layers(geometryKey) : null
    // A large model keeps the same cached base/rotor textures at zero RPM.
    // Switching between a whole SVG and separately rasterized fractional-size
    // sprites changed antialiasing visibly on notebook ink. Only transforms
    // change now; retaining these few small textures creates no idle clock.
    readonly property bool layeredArtwork: !!((modelMode || fanMotionActive)
        && fanLayerData && fanLayerData.rotors.length>0)
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
    // Large/high-DPI desktop models must not allocate an8K square texture for
    // a small schematic. Normal widget sizes keep their requested density.
    function rasterEdge(value,rotor) {
        const pixels=Math.max(1,Math.ceil(value*Screen.devicePixelRatio))
        return modelMode?Math.min(rotor?1024:2048,pixels):pixels
    }
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
        source: root.layeredArtwork ? root.fanLayerData.baseSource : root.svgSource
        opacity: root.ink.a
        sourceSize.width: root.rasterEdge(root.wideGpu?Math.max(root.width,root.height):root.width,false)
        sourceSize.height: root.rasterEdge(root.wideGpu?Math.max(root.width,root.height):root.height,false)
        fillMode: root.wideGpu ? Image.PreserveAspectCrop : Image.PreserveAspectFit
        asynchronous: false
        cache: true
        smooth: true
        mipmap: false
    }

    Loader {
        objectName: "hardwareFanMotionLoader"
        anchors.fill: parent
        active: root.layeredArtwork
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
                    rotation: root.fanMotionActive && Number.isFinite(root.fanRotation)
                        ? (((root.fanRotation*(modelData.direction===-1?-1:1))%360)+360)%360 : 0
                    Image {
                        objectName: "hardwareFanRotorImage_"+rotor.index
                        anchors.fill: parent
                        source: rotor.modelData.source
                        opacity: root.ink.a
                        sourceSize.width: root.rasterEdge(rotor.width,true)
                        sourceSize.height: root.rasterEdge(rotor.height,true)
                        fillMode: Image.PreserveAspectFit
                        asynchronous: false; cache: true; smooth: true; mipmap: false
                    }
                }
            }
        }
    }
}
