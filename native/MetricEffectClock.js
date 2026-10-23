.pragma library

// One nonvisual clock per window, owned by that window's content item.
// Lists are replaced on subscription changes; notification itself allocates no snapshot.
var windows = [];
var source = 'import QtQuick; QtObject { id: clock; objectName: "metricEffectClock";'
    + ' property int subscriberCount: 0; signal tick(double now); signal retiring();'
    + ' property Timer beat: Timer { objectName: "metricIconAnimation"; interval: 34; repeat: true;'
    + ' onTriggered: clock.tick(Date.now()) }'
    + ' function start() { beat.start() } function stop() { beat.stop() }'
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
    var snapshot = entry.listeners;
    for (var index = 0; index < snapshot.length; index++) {
        if (entry.retired) break;
        var listener = snapshot[index];
        if (listener.active && listener.callback) listener.callback(now);
    }
}

function subscribe(host, callback) {
    if (!host) return null;
    var entry = null;
    for (var index = 0; index < windows.length; index++) {
        if (!windows[index].retired && windows[index].host === host) { entry = windows[index]; break; }
    }
    if (!entry) {
        var clock = Qt.createQmlObject(source, host, "MetricEffectClock");
        entry = {host: host, clock: clock, listeners: [], retired: false};
        windows = windows.concat([entry]);
        clock.tick.connect(function(now) { notify(entry, now); });
        clock.retiring.connect(function() { retire(entry, false); });
    }
    var listener = {entry: entry, callback: callback, active: true};
    entry.listeners = entry.listeners.concat([listener]);
    entry.clock.subscriberCount = entry.listeners.length;
    entry.clock.start();
    return listener;
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
    else entry.clock.subscriberCount = entry.listeners.length;
}

function activeWindowCount() { return windows.length; }
function subscriberCount(host) {
    for (var index = 0; index < windows.length; index++)
        if (!windows[index].retired && windows[index].host === host) return windows[index].listeners.length;
    return 0;
}
