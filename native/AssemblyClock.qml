import QtQuick
import "MetricEffectClock.js" as Clock
QtObject {
    id: root
    property var backend: null
    property bool active: false
    property var subscription: null
    property double previousTime: 0
    function updateSubscription() {
        if(active && backend && !subscription) {
            subscription=Clock.subscribe(root,now=>{
                const elapsed=Math.max(0,Math.min(136,now-previousTime))
                previousTime=now
                if(root.backend)root.backend.advanceFrame(elapsed)
            },false)
            previousTime=Clock.timestamp(subscription)
        } else if((!active || !backend) && subscription) {
            Clock.unsubscribe(subscription);subscription=null;previousTime=0
        }
    }
    onActiveChanged:updateSubscription()
    onBackendChanged:updateSubscription()
    Component.onDestruction:if(subscription)Clock.unsubscribe(subscription)
}
