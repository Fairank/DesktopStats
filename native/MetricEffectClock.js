.pragma library

// One nonvisual clock per window, owned by that window's content item.
// Lists are replaced on subscription changes; notification itself allocates no snapshot.
var windows = [];
var source = 'import QtQuick; QtObject { id: clock; objectName: "metricEffectClock";'
    + ' property int subscriberCount: 0; property bool frameDriven: false; property bool enabled: false;'
    + ' property double currentTime: Date.now(); property double lastWallTime: Date.now();'
    + ' signal tick(double now); signal retiring();'
    + ' property QtObject beat: QtObject { objectName: "metricIconAnimation"; signal triggered();'
    + ' readonly property int interval: clock.frameDriven ? 0 : 34;'
    + ' function start() { clock.enabled = true } function stop() { clock.enabled = false } }'
    + ' property FrameAnimation frameDriver: FrameAnimation { objectName: "metricEffectFrameDriver";'
    + ' running: clock.enabled && clock.frameDriven; onTriggered: clock.step(frameTime * 1000) }'
    + ' property Timer backgroundDriver: Timer { objectName: "metricEffectBackgroundDriver"; interval: 34; repeat: true;'
    + ' running: clock.enabled && !clock.frameDriven;'
    + ' onTriggered: { const now = Date.now(); clock.step(Math.min(136, Math.max(0, now - clock.lastWallTime))); clock.lastWallTime = now } }'
    + ' function step(elapsed) { clock.currentTime += Math.max(0, elapsed); clock.tick(clock.currentTime); beat.triggered() }'
    + ' function start() { if (!enabled) lastWallTime = Date.now(); beat.start() } function stop() { beat.stop() }'
    + ' onFrameDrivenChanged: { lastWallTime = Date.now() }'
    + ' Component.onDestruction: retiring() }';

function retire(entry, destroy) {
    if (!entry || entry.retired) return;
    entry.retired = true;
    windows = windows.filter(value => value !== entry);
    var listeners = entry.listeners;
    entry.listeners = [];
    for (var index = 0; index < listeners.length; index++) {
        listeners[index].active = false;
        listeners[index].callback = null;
        listeners[index].entry = null;
    }
    if (destroy && entry.clock) {
        entry.clock.stop();
        entry.clock.subscriberCount = 0;
        entry.clock.destroy();
    }
    entry.clock = null;
    entry.host = null;
}

function notify(entry, now) {
    if (!entry || entry.retired) return;
    // Continuous rotors follow rendered frames. Keep decorative electrical/
    // thermal channels at their previous bounded background cadence instead
    // of multiplying every icon's work on high-refresh-rate displays.
    var backgroundElapsed = now - entry.lastBackground;
    var backgroundDue = !entry.clock.frameDriven || backgroundElapsed >= 34;
    if (backgroundDue) entry.lastBackground = entry.clock.frameDriven
        ? now - backgroundElapsed % 34 : now;
    var snapshot = entry.listeners;
    for (var index = 0; index < snapshot.length; index++) {
        if (entry.retired) break;
        var listener = snapshot[index];
        if (listener.active && listener.callback && (listener.everyFrame || backgroundDue)) listener.callback(now);
    }
}

function subscribe(host, callback, everyFrame) {
    if (!host) return null;
    var entry = null;
    var created = false;
    for (var index = 0; index < windows.length; index++) {
        if (!windows[index].retired && windows[index].host === host) { entry = windows[index]; break; }
    }
    if (!entry) {
        created = true;
        var clock = Qt.createQmlObject(source, host, "MetricEffectClock");
        entry = {host: host, clock: clock, listeners: [], retired: false, lastBackground: clock.currentTime};
        windows = windows.concat([entry]);
        clock.tick.connect(function(now) { notify(entry, now); });
        clock.retiring.connect(function() { retire(entry, false); });
    }
    var listener = {entry: entry, callback: callback, active: true, everyFrame: everyFrame === true};
    entry.listeners = entry.listeners.concat([listener]);
    entry.clock.subscriberCount = entry.listeners.length;
    updateCadence(entry);
    // A new listener must not resume a window clock explicitly paused by its
    // owner; normal active clocks are already running.
    if (created) entry.clock.start();
    return listener;
}

function setCadence(listener, everyFrame) {
    if (listener && listener.active && listener.everyFrame !== (everyFrame === true)) {
        listener.everyFrame = everyFrame === true;
        updateCadence(listener.entry);
    }
}

function updateCadence(entry) {
    if (entry && !entry.retired && entry.clock)
        entry.clock.frameDriven = entry.listeners.some(listener => listener.active && listener.everyFrame);
}

function timestamp(listener) {
    return listener && listener.active && listener.entry && listener.entry.clock
        ? listener.entry.clock.currentTime : 0;
}

function unsubscribe(listener) {
    if (!listener || !listener.active) return;
    var entry = listener.entry;
    listener.active = false;
    listener.callback = null;
    listener.entry = null;
    if (!entry || entry.retired) return;
    entry.listeners = entry.listeners.filter(value => value !== listener);
    if (!entry.listeners.length) retire(entry, true);
    else {
        entry.clock.subscriberCount = entry.listeners.length;
        updateCadence(entry);
    }
}

function activeWindowCount() { return windows.length; }
function subscriberCount(host) {
    for (var index = 0; index < windows.length; index++)
        if (!windows[index].retired && windows[index].host === host) return windows[index].listeners.length;
    return 0;
}
