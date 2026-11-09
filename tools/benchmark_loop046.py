"""Explicit offline microbenchmark of one optional loop pack, not app usage.

Runs without Qt or hardware access. The source archive is installed only into
a temporary private directory; the user's profile and running app are untouched.
"""
import argparse
import gc
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def measure(function,repeats=7,batch=256):
    # Import/first-open costs stay outside these warm picker measurements.
    function();gc.collect();samples=[]
    for _ in range(repeats):
        start=time.process_time_ns()
        for _ in range(batch):function()
        samples.append((time.process_time_ns()-start)/1e6/batch)
    gc.collect();tracemalloc.start()
    for _ in range(32):function()
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    return dict(repeats=repeats,calls_per_sample=batch,timed_allocations_traced=False,allocation_samples=32,
                median_cpu_ms=round(statistics.median(samples),4),
                peak_traced_python_bytes=peak,retained_traced_python_bytes=current)

def deep_size(value,seen=None):
    seen=set() if seen is None else seen
    if id(value) in seen:return 0
    seen.add(id(value));total=sys.getsizeof(value)
    if isinstance(value,dict):total+=sum(deep_size(k,seen)+deep_size(v,seen) for k,v in value.items())
    elif isinstance(value,(list,tuple,set,frozenset)):total+=sum(deep_size(v,seen) for v in value)
    return total

def benchmark(pack):
    import hardware_packs as packs
    from liquid_component_runtime046 import PART_KINDS,choices,grouped_choices,get_component
    with tempfile.TemporaryDirectory(prefix='desktopstats-loop-benchmark-') as scratch:
        store=packs.PackStore(Path(scratch)/'installed');store.install(pack)
        with patch.object(packs,'_store',store):
            grouped=grouped_choices()
            old=measure(lambda:{kind:choices(kind) for kind in PART_KINDS})
            new=measure(grouped_choices)
            for kind,rows in grouped.items():
                for row in rows:get_component(kind,row['id'])
            status=store.memory_status()
            result=dict(scope='Warm optional loop picker and retained data only; not application CPU/RAM/GPU or native acceptance.',
                products=sum(map(len,grouped.values())),six_separate_index_passes=old,one_grouped_index_pass=new,
                median_picker_cpu_reduction_percent=round(100*(1-new['median_cpu_ms']/old['median_cpu_ms']),2) if old['median_cpu_ms'] else None,
                retained_index_python_bytes=deep_size(store._indexes),
                retained_selected_python_bytes=deep_size(store._selected),store=status,
                author_catalogs_imported=any(name in sys.modules for name in ('liquid_block_pump_expansion046','liquid_fitting_tube_expansion046')),
                installed_app_changed=False,qt_or_native_context_started=False)
            store.remove(next(iter(store._indexes)))
            result['selected_records_after_remove']=store.memory_status()['selected_records']
            return result

def main():
    if sys.platform=='win32':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=benchmark(args.pack)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
