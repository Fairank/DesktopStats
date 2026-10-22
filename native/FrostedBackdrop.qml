import QtQuick
import QtQuick.Window
import QtQuick.Effects
Item {
    id: root
    property Item sourceItem: null
    property rect sourceRect: Qt.rect(0, 0, width, height)
    property bool active: false
    property real radius: 22
    // MultiEffect needs a shader-capable RHI backend. The software/null paths
    // must keep an opaque surface instead of revealing unblurred content.
    readonly property bool effectBackendSupported: GraphicsInfo.api === GraphicsInfo.OpenGL
        || GraphicsInfo.api === GraphicsInfo.Direct3D11
        || GraphicsInfo.api === GraphicsInfo.Direct3D12
        || GraphicsInfo.api === GraphicsInfo.Vulkan
        || GraphicsInfo.api === GraphicsInfo.Metal
    readonly property bool sampling: active && !!sourceItem && !!sourceItem.Window.window && sourceItem.Window.window.visible && width > 0 && height > 0
    Theme { id: ui }

    Rectangle { anchors.fill: parent; radius: root.radius; color: ui.fallback; visible: !effectLayer.active }
    Loader {
        id: effectLayer
        objectName: "galleryFrostedLayer"
        anchors.fill: parent
        active: root.sampling && root.effectBackendSupported
        sourceComponent: Item {
            Item {
                id: opaqueSample
                width: Math.max(1, Math.ceil(root.width*.6)); height: Math.max(1, Math.ceil(root.height*.6))
                visible: false
                layer.enabled: true
                layer.textureSize: Qt.size(width, height)
                Rectangle { anchors.fill: parent; color: ui.fallback }
                ShaderEffectSource {
                    id: region
                    objectName: "galleryBackdropSample"
                    anchors.fill: parent
                    sourceItem: root.sourceItem
                    sourceRect: root.sourceRect
                    textureSize: Qt.size(width, height)
                    hideSource: false; recursive: false; live: root.sampling
                    smooth: true
                }
            }
            Rectangle {
                id: roundedMask
                anchors.fill: parent; radius: root.radius; color: "white"
                visible: false; layer.enabled: true; layer.smooth: true
            }
            MultiEffect {
                objectName: "galleryBackdropBlur"
                anchors.fill: parent
                source: opaqueSample
                autoPaddingEnabled: false
                blurEnabled: true; blurMax: 32; blurMultiplier: 1.5; blur: 1
                maskEnabled: true; maskSource: roundedMask
                saturation: -.12
            }
        }
    }
    Rectangle {
        anchors.fill: parent; radius: root.radius
        border.color: ui.line
        gradient: Gradient {
            GradientStop { position: 0; color: ui.frostedPopupTop }
            GradientStop { position: 1; color: ui.frostedPopupBottom }
        }
    }
}
