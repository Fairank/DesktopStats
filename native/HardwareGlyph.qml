import QtQuick
import QtQuick.Window
import "HardwareShapes.js" as Shapes

// A retained, static texture. Rebuilt only for a changed appearance/ink value;
// fresh map objects from sensor projections do not invalidate the SVG source.
Item {
    id: root
    property var appearance: ({})
    property color ink: "#69788c"
    readonly property bool classic: appearance && appearance.icon_set === "classic"
    readonly property string geometryKey: classic ? "" : Shapes.key(appearance, ink)
    readonly property url svgSource: classic ? "" : Shapes.source(geometryKey)
    implicitWidth: 18
    implicitHeight: 18

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
        source: root.svgSource
        opacity: root.ink.a
        sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
        sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit
        asynchronous: false
        cache: true
        smooth: true
        mipmap: false
    }
}
