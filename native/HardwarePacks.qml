import QtQuick
import QtQuick.Layouts
SettingsGroup {
    id: root
    readonly property var info: stats.hardwarePacks || ({installed:[]})
    Layout.fillWidth: true
    title: ui.t("硬件扩展包")
    note: ui.t("按喜好从 GitHub 下载；只加载选中型号，不增加后台采集。")
    Theme { id: ui }
    Flow {
        Layout.fillWidth: true
        spacing: 8
        ActionButton { objectName:"hardwarePacksDownload";text:ui.t("前往 GitHub 下载");onClicked:stats.openHardwarePacksDownload() }
        ActionButton { objectName:"hardwarePacksImport";text:ui.t("导入扩展包");onClicked:stats.importHardwarePack() }
    }
    Text {
        Layout.fillWidth:true;text:ui.t("按品牌或类别下载 CPU、风扇、散热器、冷排，以及冷头、水泵、水箱、接头和管材。六套风格共用同一型号目录。")
        color:ui.muted;font.family:ui.fontFamily;font.pixelSize:11;wrapMode:Text.WordWrap
    }
    Text {
        Layout.fillWidth:true;visible:!(root.info.installed || []).length
        text:ui.t("尚未安装可选扩展包。")
        color:ui.muted;font.family:ui.fontFamily;font.pixelSize:12;wrapMode:Text.WordWrap
    }
    Repeater {
        model:root.info.installed || []
        RowLayout {
            required property var modelData
            Layout.fillWidth:true;spacing:8
            ColumnLayout {
                Layout.fillWidth:true;spacing:3
                Text {Layout.fillWidth:true;text:modelData.label;textFormat:Text.PlainText;font.family:ui.fontFamily;font.pixelSize:12;color:ui.ink;wrapMode:Text.WordWrap}
                Text {Layout.fillWidth:true;text:modelData.version+" · "+modelData.products+" "+ui.t("款型号")+" · "+(modelData.bytes/1024).toFixed(1)+" KB"
                    font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap}
            }
            ActionButton {text:ui.t("移除");onClicked:stats.removeHardwarePack(modelData.id)}
        }
    }
    Text {
        Layout.fillWidth:true;visible:!!root.info.status;text:root.info.status || ""
        font.family:ui.fontFamily;font.pixelSize:12;color:ui.muted;wrapMode:Text.WordWrap
    }
    Text {
        Layout.fillWidth:true;visible:root.info.invalid===true;text:ui.t("部分扩展包未通过检查，已跳过；可移除文件后重新导入。")
        font.family:ui.fontFamily;font.pixelSize:11;color:ui.muted;wrapMode:Text.WordWrap
    }
}
