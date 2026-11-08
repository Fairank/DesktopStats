import QtQuick
import QtQuick.Layouts

SettingsGroup {
    id: root
    property var config: ({})
    property var catalog: ({})
    property bool interfacesExpanded: false
    readonly property bool componentsSelected: config.loop_components_mode === "selected"
    readonly property bool hasCombo: !!config.pump_reservoir_model
    readonly property var interfaceRows: visible && componentsSelected && interfacesExpanded
                                         ? (stats.assemblyLoopPorts || []) : []

    title: ui.t("自定义水冷部件")
    note: ui.t("按喜欢的型号组装参考水冷，不补全未知的水温、流量或泵转速。")
    spacing: 12
    Theme { id: ui }

    function selectedLabel(entries, value) {
        const selected = (entries || []).find(row => row.id === value)
        return selected ? selected.label : value || ""
    }
    function flowPort(port) {
        return ["inlet", "outlet", "connection"].indexOf(port.role) >= 0
    }
    function fittingRows(port) {
        return [{id:"", label:ui.t(flowPort(port) ? "沿用默认接头" : "不放置接头")}]
            .concat((catalog.loop_fittings || []).filter(row => row.id))
    }
    function roleLabel(role) {
        return ui.t(({inlet:"进水口", outlet:"出水口", connection:"连接口", fill:"补液口",
                      drain:"排水口", auxiliary:"辅助口", closure:"封闭口"})[role] || "接口")
    }
    onVisibleChanged: if (!visible) interfacesExpanded = false
    onComponentsSelectedChanged: if (!componentsSelected) interfacesExpanded = false

    component PartChoice: RowLayout {
        id: row
        property string field: ""
        property string caption: ""
        property var entries: []
        Layout.fillWidth: true
        spacing: 12
        Text {
            Layout.preferredWidth: 90
            text: row.caption
            font.family: ui.fontFamily; font.pixelSize: 12; color: ui.muted
            wrapMode: Text.WordWrap
        }
        Choice {
            objectName: "loopPart_" + row.field
            Layout.fillWidth: true
            model: row.entries
            value: root.config[row.field] || ""
            displayText: root.selectedLabel(row.entries, value)
            Accessible.name: row.caption
            onPicked: selected => stats.changeAssembly(row.field, selected)
        }
    }

    SettingRow {
        Layout.fillWidth: true
        label: ui.t("按部件组水冷")
        Toggle {
            objectName: "loopComponentsToggle"
            checked: root.componentsSelected
            Accessible.name: ui.t("按部件组水冷")
            onToggled: stats.changeAssembly("loop_components_mode", checked ? "selected" : "reference")
        }
    }
    ColumnLayout {
        objectName: "loopSelectedComponents"
        Layout.fillWidth: true
        visible: root.componentsSelected
        spacing: 10
        PartChoice { field:"cpu_block_model"; caption:ui.t("CPU 冷头"); entries:root.catalog.cpu_blocks || [] }
        PartChoice { field:"pump_reservoir_model"; caption:ui.t("泵箱组合"); entries:root.catalog.loop_combos || [] }
        PartChoice {
            field:"pump_model"; caption:ui.t("水泵／电机")
            entries:root.catalog.loop_pumps || []
        }
        PartChoice {
            field:"pump_top_model"; caption:ui.t("泵盖"); entries:root.catalog.loop_pump_tops || []
            visible: !root.hasCombo || !!root.config.pump_top_model
        }
        PartChoice {
            field:"reservoir_model"; caption:ui.t("水箱"); entries:root.catalog.loop_reservoirs || []
            visible: !root.hasCombo || !!root.config.reservoir_model
        }
        Rectangle { Layout.fillWidth:true; implicitHeight:1; color:ui.line; Layout.topMargin:3; Layout.bottomMargin:3 }
        PartChoice { field:"fitting_model"; caption:ui.t("默认接头"); entries:root.catalog.loop_fittings || [] }
        PartChoice { field:"tubing_model"; caption:ui.t("管材"); entries:root.catalog.loop_tubing || [] }
        SettingRow {
            Layout.fillWidth: true
            label: ui.t("参考连管")
            note: ui.t("显示示意走管，可随时关闭。")
            Toggle {
                objectName: "loopReferenceTubesToggle"
                checked: root.config.loop_tubes_visible !== false
                Accessible.name: ui.t("参考连管")
                onToggled: stats.changeAssembly("loop_tubes_visible", checked)
            }
        }
        ActionButton {
            objectName: "loopInterfacesButton"
            Layout.fillWidth: true
            quiet: true
            text: root.interfacesExpanded ? ui.t("收起各接口接头") : ui.t("各接口接头")
            Accessible.description: ui.t("为每个已选部件的接口单独选择接头")
            onClicked: root.interfacesExpanded = !root.interfacesExpanded
        }
        ColumnLayout {
            objectName: "loopInterfacesContent"
            Layout.fillWidth: true
            visible: root.interfacesExpanded
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: ui.t("流通口留空沿用默认；补液、排水口不自动连管。")
                font.family: ui.fontFamily; font.pixelSize: 11; color: ui.muted
                wrapMode: Text.WordWrap
            }
            Text {
                objectName: "loopNoInterfaces"
                Layout.fillWidth: true
                visible: root.interfaceRows.length === 0
                text: ui.t("选择部件后，在这里配置已核实的接口。")
                font.family: ui.fontFamily; font.pixelSize: 11; color: ui.muted
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: root.interfaceRows
                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 5
                    Text {
                        Layout.fillWidth: true
                        text: modelData.label + " · " + root.roleLabel(modelData.role)
                        font.family: ui.fontFamily; font.pixelSize: 11; color: ui.muted
                        wrapMode: Text.WordWrap
                    }
                    Choice {
                        objectName: "loopPort_" + modelData.key
                        Layout.fillWidth: true
                        model: root.fittingRows(modelData)
                        value: (root.config.loop_fittings || {})[modelData.key] || ""
                        displayText: root.selectedLabel(model, value)
                        Accessible.name: modelData.label + " · " + root.roleLabel(modelData.role)
                        onPicked: selected => stats.changeAssemblyLoopFitting(modelData.key, selected)
                    }
                }
            }
        }
    }
}
