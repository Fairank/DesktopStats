import QtQuick
import QtQuick.Controls
ComboBox {
    id: control
    Theme { id: ui }
    property var value
    signal picked(var selected)
    textRole: "label"
    valueRole: "id"
    currentIndex: {
        const entries = model || []
        for (let i = 0; i < entries.length; ++i)
            if (entries[i].id === value) return i
        return -1
    }
    implicitHeight: ui.controlHeight
    implicitWidth: 180
    leftPadding: 11
    rightPadding: 28
    font.family: ui.fontFamily
    font.pixelSize: ui.bodySize
    Accessible.name: displayText
    onActivated: picked(currentValue)
    contentItem: Text { text: control.displayText; font: control.font; color: ui.ink; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
    indicator: Icon { x: control.width - 23; y: (control.height - 14)/2; width:14; height:14; name:"down"; ink:ui.muted }
    background: GlassSurface { tone: "field"; radius: ui.controlRadius; focused: control.activeFocus; highlighted: control.hovered || control.popup.opened }
    delegate: ItemDelegate {
        width: control.popup.availableWidth
        text: modelData.label
        font: control.font
        highlighted: control.highlightedIndex === index
        implicitHeight: 34
        contentItem: Text { text: modelData.label; color: ui.ink; font: control.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        background: GlassSurface { tone: "field"; radius: 7; visible: parent.highlighted; highlighted: true; border.width: 0 }
    }
    popup: Popup {
        y: control.height + 5
        width: control.width
        padding: 5
        implicitHeight: Math.min(contentItem.implicitHeight + 10, 350)
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            // Only keyboard/highlight changes reveal a row. Wheel scrolling
            // without changing the highlight must retain the user's viewport.
            onCurrentIndexChanged: Qt.callLater(() => {
                if (control.popup.visible && currentIndex >= 0)
                    positionViewAtIndex(currentIndex, ListView.Contain)
            })
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: GlassSurface { tone: "popup"; radius: 12 }
    }
}
