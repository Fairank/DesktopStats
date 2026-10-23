import QtQuick

// A group is one hit target in its parent. Leaf rendering stays unchanged.
Item {
    id:root
    property var row:({})
    property color ink:"#202833"
    property color muted:"#566272"
    property string fontFamily:"Segoe UI Variable"
    property bool reserveValueWidth:false
    property bool motionEnabled:false
    readonly property bool grouped:row.grouped===true && (row.group_rows || []).length>1
    readonly property var members:grouped?(row.group_rows || []).slice(0,4):[]
    readonly property var pairRows:single.pairRows
    readonly property bool labelTruncated: {
        if(!grouped)return single.labelTruncated
        for(let index=0;index<entries.count;index++) {
            const item=entries.itemAt(index)
            if(item && item.labelTruncated)return true
        }
        return false
    }
    implicitWidth:grouped?groupLine.implicitWidth:single.implicitWidth
    implicitHeight:grouped?groupLine.implicitHeight:single.implicitHeight
    TopBarMetricContent {
        id:single
        visible:!root.grouped
        row:root.grouped?({}):root.row
        ink:root.ink;muted:root.muted;fontFamily:root.fontFamily
        reserveValueWidth:root.reserveValueWidth
        motionEnabled:root.motionEnabled
        width:implicitWidth;height:implicitHeight
        anchors.verticalCenter:parent.verticalCenter
    }
    Row {
        id:groupLine
        visible:root.grouped
        spacing:10
        height:implicitHeight
        anchors.verticalCenter:parent.verticalCenter
        Repeater {
            id:entries
            model:root.members
            TopBarMetricContent {
                required property var modelData
                objectName:"topBarGroupMember_"+(modelData.metric || "")
                row:Object.assign({},modelData,{style:root.row.style || modelData.style || "label_value"})
                ink:root.ink;muted:root.muted;fontFamily:root.fontFamily
                reserveValueWidth:root.reserveValueWidth
                motionEnabled:root.motionEnabled
                width:implicitWidth;height:implicitHeight
                y:(groupLine.height-height)/2
            }
        }
    }
}
