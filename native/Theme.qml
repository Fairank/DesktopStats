import QtQuick
QtObject {
    readonly property bool dark: stats.theme === "dark"
    readonly property var materialReport: stats.material || ({})
    // Backend identity is not permission to paint a transparent surface.
    readonly property bool acrylic: materialReport.material === "desktop-acrylic"
    readonly property bool policyAllowed: !!materialReport.policy
        && materialReport.policy.state === "allowed"
        && (materialReport.coating_allowed === undefined || materialReport.coating_allowed === true)
    readonly property bool materialFallback: !!materialReport.fallback_reason
        || materialReport.ok === false
        || (materialReport.coating_translucent !== undefined && materialReport.coating_translucent !== true)
        || !["configured-unverified", "configured", "verified"].includes(materialReport.status)
    readonly property bool dwmConfigured: acrylic && materialReport.backdrop_result === 0
        && materialReport.backdrop_type === 3
    readonly property bool blurConfigured: materialReport.material === "system-blur"
        && materialReport.blur_configured === true
        && materialReport.coating_allowed === true
        && materialReport.coating_translucent === true && materialReport.ok === true
        && typeof materialReport.bool_result === "number"
        && Number.isInteger(materialReport.bool_result) && materialReport.bool_result !== 0
        && materialReport.bool_result >= -2147483648 && materialReport.bool_result <= 2147483647
    // This permits an alpha coating after a configured own-window request.
    // It never asserts that the native compositor's appearance was verified.
    readonly property bool translucentBackdrop: policyAllowed && !materialFallback
        && (dwmConfigured || blurConfigured)
    readonly property string fontFamily: ({"zh-CN":"Microsoft YaHei UI", "zh-TW":"Microsoft JhengHei UI", "ja":"Yu Gothic UI", "ko":"Malgun Gothic"})[stats.language] || "Segoe UI Variable"
    readonly property bool motionAllowed: stats.motionEnabled === true
    readonly property int titleSize: 22
    readonly property int sectionSize: 14
    readonly property int bodySize: 13
    readonly property int captionSize: 12
    readonly property int metaSize: 11
    readonly property int controlHeight: 34
    readonly property int controlRadius: 8
    readonly property color ink: dark ? "#f5f6f8" : "#1f242b"
    readonly property color muted: dark ? "#b8bdc7" : "#303945"
    readonly property color subtle: translucentBackdrop ? muted : dark ? "#a4aebc" : "#5c6878"
    readonly property color line: dark ? "#1cffffff" : "#13000000"
    readonly property color controlBorder: dark ? "#48515e" : "#dfe3e8"
    readonly property color hover: dark ? "#17ffffff" : "#0c000000"
    readonly property color pressed: dark ? "#24ffffff" : "#14000000"
    readonly property color disabledText: dark ? "#7e8998" : "#88929f"
    readonly property color accent: dark ? "#67a8ff" : "#006fe6"
    readonly property color accentFill: "#006fe6"
    readonly property color accentHover: "#0066d6"
    readonly property color accentPressed: "#0058bf"
    readonly property color selection: dark ? "#334158" : "#e2edff"
    readonly property color selectedLine: dark ? "#6a9ee8" : "#75a9ed"
    readonly property color field: dark ? "#2d323b" : "#ffffff"
    readonly property color group: dark ? "#2a2e35" : "#ffffff"
    readonly property color well: dark ? "#1f2329" : "#edf0f5"
    readonly property color segment: dark ? "#1d2127" : "#e9edf3"
    readonly property color segmentSelected: dark ? "#424954" : "#ffffff"
    readonly property color tile: dark ? "#2d323b" : "#ffffff"
    readonly property color card: dark ? "#2a2f38" : "#fbfcfe"
    readonly property color cardHover: dark ? "#343d49" : "#f0f5fd"
    readonly property color cardSelected: dark ? "#334158" : "#e2edff"
    readonly property color cardTop: card
    readonly property color cardBottom: card
    readonly property color previewCanvas: dark ? "#232931" : "#edf0f5"
    readonly property color fallback: dark ? "#23272e" : "#f6f8fb"
    // The window is the one material plane; controls keep a stable reading fill.
    readonly property color windowTop: translucentBackdrop ? (dark ? "#d6242426" : "#a3ffffff") : fallback
    readonly property color windowBottom: windowTop
    // Match WUJI's chrome coating: 32% light / 72% dark; controls remain legible.
    readonly property color railTop: translucentBackdrop ? (dark ? "#b81e1e22" : "#52f4f6fa") : (dark ? "#1d2128" : "#edf1f7")
    readonly property color railBottom: railTop
    // Only sidebar reading groups receive this second surface; blank chrome
    // keeps WUJI's thin coating. Includes contrast headroom for hover/press.
    readonly property color railReading: translucentBackdrop ? (dark ? "#88000000" : "#90ffffff") : "transparent"
    readonly property color panelTop: group
    readonly property color panelBottom: group
    readonly property color fieldTop: field
    readonly property color fieldBottom: field
    readonly property color popupTop: dark ? "#2b3038" : "#ffffff"
    readonly property color popupBottom: popupTop
    readonly property color frostedPopupTop: translucentBackdrop ? (dark ? "#d12b3038" : "#e8ffffff") : popupTop
    readonly property color frostedPopupBottom: frostedPopupTop
    readonly property color glassEdgeTop: dark ? "#24ffffff" : "#66ffffff"
    readonly property color glassEdgeBottom: dark ? "#08ffffff" : "#18000000"
    function t(text) { return stats.texts[text] || text }
}
