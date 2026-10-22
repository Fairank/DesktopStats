import QtQuick
import QtQuick.Window
import "IconData.js" as IconData

// Lucide UI symbols; complete upstream license and provenance are in assets/lucide.
// Existing Niangao brand assets are independent and unchanged.
Item {
    id: root
    property string name: "grid"
    property color ink: "#69788c"
    implicitWidth: 18
    implicitHeight: 18
    readonly property string rgb: "#" + [ink.r, ink.g, ink.b].map(
        channel => Math.round(channel * 255).toString(16).padStart(2, "0")).join("")

    Image {
        id: iconImage
        objectName: "lucideImage"
        anchors.fill: parent
        sourceSize.width: Math.max(1, Math.ceil(root.width * Screen.devicePixelRatio))
        sourceSize.height: Math.max(1, Math.ceil(root.height * Screen.devicePixelRatio))
        fillMode: Image.PreserveAspectFit
        smooth: true
        source: "data:image/svg+xml;base64," + Qt.btoa(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"'
            + ' stroke="' + root.rgb + '" stroke-opacity="' + root.ink.a + '"'
            + ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + IconData.fragment(root.name) + '</svg>')
    }
}
