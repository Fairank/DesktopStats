"""Read-only, device-scoped channels for optional hardware icon feedback."""

import time

from metrics import display_value, metric_info, numeric

CHANNELS = ('load', 'thermal', 'energy', 'inbound', 'outbound', 'spin')
GPU_FAN_MAX_AGE = 3.0


def gpu_fan_feedback(data, prefs, *, stale=False):
    """Accept selected-card tachometer/current RPM, never targets, chassis or %."""
    target = prefs.get('gpu_target') or '0'
    devices = data.get('gpus')
    row = devices.get(target, {}) if isinstance(devices, dict) else {}
    if not isinstance(row, dict):
        row = {}
    statuses = row.get('channel_status')
    status = statuses.get('gpu_fan_rpm', {}) if isinstance(statuses, dict) else {}
    status_valid = isinstance(status, dict)
    rpm, timestamp = row.get('gpu_fan_rpm'), row.get('gpu_fan_rpm_timestamp')
    source = row.get('gpu_fan_rpm_source')
    semantics, scope = row.get('gpu_fan_rpm_semantics'), row.get('gpu_fan_rpm_scope')
    available = (not stale and numeric(rpm) and 0 <= rpm <= 100000
                 and numeric(timestamp) and 0 <= time.time()-timestamp <= GPU_FAN_MAX_AGE
                 and isinstance(source, str) and bool(source.strip())
                 and semantics in ('measured', 'driver_current_rpm') and scope == 'card'
                 and status_valid and (not status or status.get('state') == 'available'))
    return dict(available=bool(available), rpm=rpm if available else None,
                timestamp=timestamp if available else None,
                source=source[:160] if isinstance(source, str) else '',
                semantics=semantics if available else 'unknown', scope='card',
                aggregate=status.get('aggregate', '') if status_valid else '',
                display_slowdown=120)


def hardware_feedback(data, metric, prefs, *, stale=False):
    """Normalize real channels; never infer heat, power or a different device.

    These reference scales control decoration, not warnings or rated hardware
    limits. Providers already return their own channel set when sampled; this
    function performs no extra sampling and makes no native/API calls.
    """
    if prefs.get('icon_effect', 'off') != 'auto':
        return {}
    if metric in ('cpu_frequency', 'gpu_clock', 'gpu_memory_clock'):
        # Frequency has its own real scalar response. Do not substitute usage,
        # or suppress a real clock when unrelated processor channels are absent.
        return {}
    canonical = dict(prefs, temperature_unit='C', network_unit='MBps')

    def activity(key, *, cold_is_zero=False, signed_is_magnitude=False):
        value, _, _ = display_value(data, key, canonical)
        maximum = metric_info(key, canonical)['maximum']
        if not numeric(value) or not numeric(maximum) or maximum <= 0:
            return None
        if value < 0:
            if signed_is_magnitude:
                return min(1.0, abs(value) / maximum)
            return 0.0 if cold_is_zero else None
        return min(1.0, value / maximum)

    def occupancy(percent, used, total):
        fraction = activity(percent)
        if fraction is not None:
            return fraction
        amount, _, _ = display_value(data, used, canonical)
        capacity, _, _ = display_value(data, total, canonical)
        if numeric(amount) and numeric(capacity) and 0 <= amount <= capacity and capacity > 0:
            return amount / capacity
        return None

    state = dict.fromkeys(CHANNELS)
    if metric in ('cpu_fan_rpm', 'gpu_fan_rpm', 'system_fan_rpm', 'gpu_fan_percent'):
        profile = 'fan'
        state['spin'] = activity(metric)
        # Only the scoped NVML percentage has an explicit same-device GPU link.
        if metric == 'gpu_fan_percent':
            state['thermal'] = activity('gpu_temp', cold_is_zero=True)
    elif metric.startswith(('ram_', 'swap_')):
        profile = 'memory'
        if metric.startswith('swap_'):
            state['load'] = activity('swap_percent')
        else:
            state['load'] = occupancy('ram_percent', 'ram_used_gb', 'ram_total_gb')
    elif metric.startswith('vram_'):
        profile = 'memory'
        state['load'] = occupancy('vram_percent', 'vram_gb', 'vram_total_gb')
    elif metric.startswith('cpu_'):
        profile = 'processor'
        state.update(load=activity('cpu_usage'),
                     thermal=activity('cpu_temp', cold_is_zero=True),
                     energy=activity('cpu_power'))
    elif metric_info(metric, prefs).get('scope') == 'gpus':
        profile = 'processor'
        state.update(load=activity('gpu_usage'),
                     thermal=activity('gpu_temp', cold_is_zero=True),
                     energy=activity('gpu_power'))
        state['fan_speed'] = gpu_fan_feedback(data, prefs, stale=stale)
    elif metric.startswith('net_'):
        profile = 'network'
        state.update(inbound=activity('net_download'), outbound=activity('net_upload'))
    elif metric in ('disk_read', 'disk_write'):
        profile = 'disk'
        state.update(inbound=activity('disk_read'), outbound=activity('disk_write'))
    elif metric.startswith('battery_'):
        profile = 'battery'
        state.update(load=activity('battery_percent'),
                     inbound=activity('battery_charge_watts'),
                     outbound=activity('battery_discharge_watts'))
        if metric in ('battery_watts', 'battery_charge_watts', 'battery_discharge_watts'):
            # A power glyph represents its own selected quantity. Signed legacy
            # watts provide magnitude only, never an inferred charging direction.
            state['energy'] = activity(metric, signed_is_magnitude=metric == 'battery_watts')
    elif metric in ('disk_percent', 'disk_used_gb', 'disk_free_gb', 'disk_total_gb'):
        profile = 'volume'
        state['load'] = occupancy('disk_percent', 'disk_used_gb', 'disk_total_gb')
    elif metric.startswith('storage_'):
        profile = 'storage'
        state['thermal'] = activity('storage_temp', cold_is_zero=True)
    else:
        return {}
    if stale:
        state = dict.fromkeys(CHANNELS)
    state.update(profile=profile, available=any(state.get(key) is not None for key in CHANNELS)
                 or bool(state.get('fan_speed', {}).get('available')))
    return state
