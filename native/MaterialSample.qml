import QtQuick
import DesktopStats 1.0

// Controlled colour swatch, not a sensor card or a desktop-composition preview.
// All imagery below is generated here; no desktop/window pixels are sampled.
Item {
    id: root
    property string skin: "glass"
    property bool dark: false
    property real concentration: 94
    property real transparency: 50
    property real curvature: 50
    implicitWidth: 140
    implicitHeight: 48

    Rectangle {
        anchors.fill: parent
        radius: 8
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: root.dark ? "#386279" : "#8fc3dc" }
            GradientStop { position: .47; color: root.dark ? "#456c63" : "#b5d5c1" }
            GradientStop { position: 1; color: root.dark ? "#84624f" : "#e5bca5" }
        }
    }
    MaterialSurface {
        objectName: "materialSampleCoating"
        x: 7; y: 6; width: Math.max(1, parent.width - 14); height: Math.max(1, parent.height - 12)
        config: ({ skin: root.skin, theme: root.dark ? "dark" : "light", opacity: root.concentration, glass_transparency: root.transparency, glass_curvature: root.curvature })
        frosted: true
        // Scaled material specimen; full-size cards share the same 160-unit design.
        cornerRadius: ["glass", "frost", "tint"].includes(root.skin) ? (6 + Math.max(0, Math.min(100, root.curvature)) * .24) * height / 160 : 18 * height / 160
    }
    // Neutral type specimen communicates crisp text and the no-panel style.
    Text {
        anchors.centerIn: parent
        text: "Aa"
        color: root.skin === "graphite" || root.dark ? "#f4f6f9" : "#202833"
        font.family: "Segoe UI Variable"
        font.pixelSize: 19
        font.weight: Font.Medium
        renderType: Text.QtRendering
    }
}
