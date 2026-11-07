"""Existing cache only: no new fan sampling or inferred case/PSU tachometers."""
import math
import time

from top_bar_feedback import GPU_FAN_MAX_AGE


def cpu_fan_state(data,*,now=None):
    now=time.time() if now is None else now
    data=data if isinstance(data,dict) else {}
    statuses=data.get('channel_status') or {}
    channel=statuses.get('cpu_fan_rpm') or {} if isinstance(statuses,dict) else {}
    channel=channel if isinstance(channel,dict) else {}
    stamps=data.get('metric_timestamps') or {}
    sample=data.get('sample_status');sample=sample if isinstance(sample,dict) else {}
    stamp=channel.get('timestamp',stamps.get('cpu_fan_rpm',data.get('time')) if isinstance(stamps,dict) else None)
    rpm=data.get('cpu_fan_rpm')
    numeric=lambda value:type(value) in (int,float) and math.isfinite(value)
    available=(numeric(rpm) and 0<=rpm<=12000 and numeric(stamp) and numeric(now)
               and 0<=now-stamp<=GPU_FAN_MAX_AGE and channel.get('state') in (None,'available')
               and sample.get('state')!='stale')
    return dict(available=bool(available),rpm=rpm if available else None,
                timestamp=stamp if available else None,source='CPU_FAN',scope='cpu_header',
                semantics='header_tachometer',independent_fans=False,display_slowdown=120)
