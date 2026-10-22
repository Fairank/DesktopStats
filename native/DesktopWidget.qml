import QtQuick
import QtQuick.Window
import QtQuick.Controls
import DesktopStats 1.0
Window {
    id: root
    required property var spec
    property bool registered: false
    property bool resizing: false
    property int nativeFlags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.WindowDoesNotAcceptFocus
    property var composition: ({material:"solid"})
    property var appearanceConfig: null
    property var appearancePolicy: null
    readonly property var paintConfig: appearanceConfig || stats.saved
    readonly property var surfacePolicy: appearancePolicy || spec.material_policy || ({panel_skin:null,card_surfaces:true})
    width: spec.width; height: spec.height
    maximumWidth: 8192; maximumHeight: 8192
    visible: false; color: "transparent"
    title: "Desktop Stats · " + spec.id
    function keyAt(xx, yy) {
        xx=xx*root.spec.width/root.width; yy=yy*root.spec.height/root.height
        const cell=root.spec.cells.find(c=>xx>=c.x&&xx<c.x+c.width&&yy>=c.y&&yy<c.y+c.height)
        return cell?cell.key:root.spec.id
    }
    flags: nativeFlags
    onClosing: function(event) {
        event.accepted = false
        if (registered) stats.closeWindow(spec.id)
    }
    onXChanged: if (registered) stats.moved(spec.id,x,y)
    onYChanged: if (registered) stats.moved(spec.id,x,y)
    MaterialSurface {
        anchors.fill:parent; visible:!!root.surfacePolicy.panel_skin
        config: {
            const cfg=Object.assign({},root.paintConfig)
            cfg.skin=root.surfacePolicy.panel_skin || cfg.skin
            const options=root.surfacePolicy.panel_options || ({})
            if(options.transparency!==undefined)cfg.glass_transparency=options.transparency
            if(options.curvature!==undefined)cfg.glass_curvature=options.curvature
            return cfg
        }
        frosted:root.composition.coating_translucent===true
    }
    Repeater {
        id:cards
        model:root.spec.cells
        HardwareCard {
            required property var modelData
            property var cardPrefs: root.paintConfig.widgets[modelData.key] || ({})
            x:modelData.x*root.width/root.spec.width; y:modelData.y*root.height/root.spec.height
            width:modelData.width*root.width/root.spec.width; height:modelData.height*root.height/root.spec.height
            moduleKey:modelData.key
            config: {
                if(!root.resizing)return root.paintConfig
                const cfg=Object.assign({},root.paintConfig)
                cfg.widgets=Object.assign({},cfg.widgets)
                const prefs=Object.assign({},cfg.widgets[modelData.key])
                prefs.width=Math.round(width);prefs.height=Math.round(height)
                if(prefs.form!=="bar")prefs.form="free"
                cfg.widgets[modelData.key]=prefs
                return cfg
            }
            readings:stats.readings; history:stats.history
            frosted:root.composition.coating_translucent===true
            surface:root.surfacePolicy.card_surfaces
        }
    }
    MouseArea {
        id:moveArea
        objectName:"moveHandle"
        property bool manualMove:false
        property bool moving:false
        property bool dragged:false
        property string hoverLabel:""
        property point pointerOrigin:Qt.point(0,0)
        property point windowOrigin:Qt.point(0,0)
        anchors.fill:parent; acceptedButtons:Qt.LeftButton|Qt.RightButton; hoverEnabled:true
        cursorShape:stats.saved.locked?Qt.ArrowCursor:Qt.SizeAllCursor
        onPressed:function(mouse) {
            if(mouse.button===Qt.LeftButton) {moving=false;dragged=false;manualMove=false}
            if(mouse.button===Qt.LeftButton && !stats.saved.locked) {
                pointerOrigin=mapToGlobal(mouse.x,mouse.y)
                windowOrigin=Qt.point(root.x,root.y)
            }
        }
        onPositionChanged:function(mouse) {
            if(!pressed) {
                hoverLabel=""
                for(let i=0;i<cards.count;i++) {
                    const card=cards.itemAt(i)
                    if(mouse.x>=card.x&&mouse.x<card.x+card.width&&mouse.y>=card.y&&mouse.y<card.y+card.height) {
                        hoverLabel=card.metricLabelAt(mouse.x-card.x,mouse.y-card.y)
                        break
                    }
                }
                return
            }
            if(stats.saved.locked || !(pressedButtons&Qt.LeftButton))return
            const point=mapToGlobal(mouse.x,mouse.y)
            if(!moving) {
                if(Math.hypot(point.x-pointerOrigin.x,point.y-pointerOrigin.y)<6)return
                moving=true;dragged=true
                stats.beginMove(root.spec.id)
                manualMove=!root.startSystemMove()
            }
            if(!manualMove)return
            root.x=Math.round(windowOrigin.x+point.x-pointerOrigin.x)
            root.y=Math.round(windowOrigin.y+point.y-pointerOrigin.y)
        }
        onReleased:function(mouse) {
            if(mouse.button===Qt.LeftButton) {
                if(moving)stats.endMove(root.spec.id)
                manualMove=false;moving=false
            }
        }
        onCanceled: {
            if(moving)stats.endMove(root.spec.id)
            manualMove=false;moving=false;dragged=true
        }
        onClicked:function(mouse) {
            if(mouse.button===Qt.RightButton)stats.widgetMenu(root.keyAt(mouse.x,mouse.y))
            else if(!dragged) {
                const key=root.keyAt(mouse.x,mouse.y)
                const prefs=stats.saved.widgets[key] || ({})
                if(prefs.form==="bar") {
                    for(let i=0;i<cards.count;i++) {
                        const card=cards.itemAt(i)
                        if(card.moduleKey===key) {
                            const index=card.metricAt(mouse.x-card.x,mouse.y-card.y)
                            if(index>=0)stats.openDetails(key,index,root.x+mouse.x,root.y+root.height)
                            break
                        }
                    }
                }
            }
        }
        onDoubleClicked:function(mouse) {
            if(mouse.button===Qt.LeftButton)stats.openSettings(root.keyAt(mouse.x,mouse.y))
        }
        ToolTip.visible:containsMouse && !pressed && hoverLabel.length>0
        ToolTip.text:hoverLabel
        ToolTip.delay:750
        ToolTip.timeout:4000
    }
    MouseArea {
        id:resizeHandle
        objectName:"resizeHandle"
        anchors.right:parent ? parent.right : undefined
        anchors.bottom:parent ? parent.bottom : undefined
        width:26; height:26; z:3
        visible:!stats.saved.locked
        hoverEnabled:true; cursorShape:Qt.SizeFDiagCursor
        property real startX:0
        property real startY:0
        property real startWidth:0
        property real startHeight:0
        property var limits:({})
        onPressed:function(mouse) {
            const point=mapToGlobal(mouse.x,mouse.y)
            startX=point.x;startY=point.y;startWidth=root.width;startHeight=root.height
            limits=stats.resizeLimits(root.spec.id);root.resizing=true
        }
        onPositionChanged:function(mouse) {
            if(!pressed)return
            const point=mapToGlobal(mouse.x,mouse.y)
            const candidateWidth=startWidth+point.x-startX
            limits=stats.resizeLimits(root.spec.id,candidateWidth)
            root.width=Math.round(Math.max(limits.min_width || 80,Math.min(limits.max_width || 4096,candidateWidth)))
            root.height=Math.round(Math.max(limits.min_height || 32,Math.min(limits.max_height || 2160,startHeight+point.y-startY)))
        }
        onReleased: {
            const accepted=stats.resizeWindow(root.spec.id,root.width,root.height)
            root.resizing=false
            if(!accepted) {root.width=root.spec.width;root.height=root.spec.height}
        }
        onCanceled: {root.resizing=false;root.width=root.spec.width;root.height=root.spec.height}
        Canvas {
            anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:7;width:12;height:12
            opacity:resizeHandle.containsMouse || resizeHandle.pressed || moveArea.containsMouse ? .65 : .18
            onPaint: {
                let ctx=getContext("2d")
                ctx.clearRect(0,0,width,height);ctx.strokeStyle=stats.saved.theme==="dark"?"#d9e4f2":"#65768b";ctx.lineWidth=1.2
                ctx.beginPath();ctx.moveTo(3,10);ctx.lineTo(10,3);ctx.moveTo(7,10);ctx.lineTo(10,7);ctx.stroke()
            }
        }
        Accessible.name:stats.tr("缩放小组件")
    }
}
