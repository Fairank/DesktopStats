"""Hardware meaning and paired channels for menu-bar presentation.

No sampling, GUI, native API, or provider inference. Capacity, I/O and health
stay separate even if Windows happens to deliver them through one provider.
"""
from math import isfinite

PROFILES = {
    'cpu': ('处理器', ('cpu_usage', 'cpu_temp', 'cpu_power', 'cpu_frequency', 'cpu_cores', 'cpu_threads')),
    'gpu': ('图形处理器', ('gpu_usage', 'gpu_temp', 'gpu_power', 'vram_gb', 'vram_total_gb',
                          'vram_percent', 'gpu_clock', 'gpu_memory_clock', 'gpu_fan_percent')),
    'memory': ('内存', ('ram_percent', 'ram_used_gb', 'ram_total_gb', 'ram_available_gb',
                      'swap_percent', 'swap_used_gb')),
    'network': ('网络', ('net_download', 'net_upload', 'net_received_gb', 'net_sent_gb')),
    'disk_io': ('磁盘读写', ('disk_read', 'disk_write')),
    'volume': ('卷容量', ('disk_percent', 'disk_used_gb', 'disk_free_gb', 'disk_total_gb')),
    'storage': ('NVMe 健康', ('storage_temp', 'storage_spare_percent', 'storage_wear_percent')),
    'battery': ('电池', ('battery_percent', 'battery_charge_watts', 'battery_discharge_watts',
                        'battery_remaining_wh', 'battery_time_minutes', 'voltage', 'battery_watts')),
    'power': ('电力流向', ('adapter_input_watts', 'system_power', 'cpu_power', 'gpu_power',
                        'gpu_asic_power', 'battery_charge_watts', 'battery_discharge_watts')),
    'cooling': ('散热', ('cpu_fan_rpm', 'gpu_fan_rpm', 'system_fan_rpm')),
}

PAIRS = (
    (('net_download', 'download'), ('net_upload', 'upload')),
    (('disk_read', 'read'), ('disk_write', 'write')),
    (('battery_charge_watts', 'charge'), ('battery_discharge_watts', 'discharge')),
)

# A group retains one primary item, device selection and hover/drag identity.
# Only CPU and per-device GPU channels share a sufficiently precise identity.
MAX_GROUP_METRICS = 4


def group_channels(metric):
    for family in ('cpu', 'gpu'):
        channels = PROFILES[family][1]
        if metric in channels:
            return channels
    return ()


def validate_group_metrics(metric, value):
    if (not isinstance(value, list) or not 1 <= len(value) <= MAX_GROUP_METRICS
            or any(type(key) is not str for key in value)
            or value[0] != metric or len(set(value)) != len(value)):
        raise ValueError('组合指标应保留主指标，并选择最多四项不同读数')
    if len(value) > 1 and any(key not in group_channels(metric) for key in value):
        raise ValueError('组合指标必须来自同一个 CPU 或 GPU')
    return list(value)


def paired_channels(metric):
    return next((pair for pair in PAIRS if any(key == metric for key, _ in pair)), ())


def detail_profile(metric):
    # Explicit membership takes priority over the power comparison profile.
    for family, (label, channels) in PROFILES.items():
        if metric in channels:
            return family, label, tuple(key for key in channels if key != metric)
    return 'external', '硬件传感器', ()


def can_gauge(meta):
    return meta.get('unit') == '%' and meta.get('maximum') == 100


def align_pair_trends(rows):
    """Project both directions onto the same real amplitude range, with gaps."""
    values = [value for row in rows for value in row.get('trend', ())
              if type(value) in (int, float) and isfinite(value)]
    if not values or len({row.get('unit') for row in rows}) != 1:
        return rows
    low, high = min(0.0, min(values)), max(0.0, max(values))
    result = []
    for row in rows:
        history = row.get('trend', ())
        points = []
        for i, value in enumerate(history):
            if type(value) not in (int, float) or not isfinite(value):
                points.append(None)
                continue
            span = high-low
            y = (.5 if high == low else (high-value)/span if isfinite(span)
                 else (high/2-value/2)/(high/2-low/2))
            original = row.get('trend_points', ())
            point = original[i] if len(original) == len(history) else None
            x = point['x'] if isinstance(point, dict) and type(point.get('x')) in (int, float) else i/max(1, len(history)-1)
            points.append(dict(x=x, y=min(1.0, max(0.0, y))))
        result.append(dict(row, trend_points=points, shared_trend_scale=True,
                           trend_minimum=low, trend_maximum=high))
    return result
