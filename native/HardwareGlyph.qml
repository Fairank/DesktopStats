import QtQuick
import QtQuick.Window
import "HardwareShapes.js" as Shapes

// A retained, static texture. Rebuilt only for a changed appearance/ink value;
// fresh map objects from sensor projections do not invalidate the SVG source.
Item {
    id: root
    property var appearance: ({})
    property color ink: "#69788c"
    readonly property string geometryKey: Shapes.key(appearance, ink)
    readonly property url svgSource: Shapes.source(geometryKey)
    implicitWidth: 18
    implicitHeight: 18

    Image {
        objectName: "hardwareGlyphImage"
        anchors.fill: parent
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
