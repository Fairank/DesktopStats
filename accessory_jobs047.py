"""One demand-only graphics task, with GUI-owned queues and cache callbacks.

No store, model catalog, sampler or native graphics API is imported here. The
worker receives one detached row, invokes a pure producer and returns data.
"""
from collections import OrderedDict
from itertools import islice
from threading import Event
import atexit
import weakref

from PySide6.QtCore import QObject,QThread,Signal,Slot,Qt
from shiboken6 import isValid
from accessory_cancel047 import ArtCancelled,checkpoint

MAX_DEMAND=16
_LIVE=set()
_REAPER=None


class _Reaper(QObject):
    @Slot()
    def release(self):
        worker=self.sender()
        _LIVE.discard(worker)
        owner=worker.owner()
        if owner is not None and isValid(owner):
            try:owner._receive(worker)
            except RuntimeError:pass  # Its QObject can be gone after shutdown.
        worker.result={};worker.deleteLater()


def _reaper():
    global _REAPER
    if _REAPER is None:_REAPER=_Reaper()
    return _REAPER


def _exit_drain():
    # Only interpreter shutdown, after interactive GUI work has ended. Keeping
    # these unparented QThreads alive avoids destroying a running native thread.
    workers=tuple(_LIVE)
    for worker in workers:worker.cancel.set()
    for worker in workers:
        worker.wait();worker.result={}
    _LIVE.clear()


atexit.register(_exit_drain)


class _Worker(QThread):
    def __init__(self,key,epoch,row,producer,parent):
        super().__init__()  # Never destroyed as a child of a closing controller.
        self.owner=weakref.ref(parent)
        self.key,self.epoch,self.row,self.producer=key,epoch,row,producer
        self.cancel=Event();self.result={};self.failed=False

    def run(self):
        try:
            checkpoint(self.cancel)
            self.result=self.producer(self.row,self.key[2],self.cancel)
            if self.cancel.is_set():self.result={}
        except ArtCancelled:pass
        except Exception:
            # A bad optional reference is unavailable, never a generic model.
            self.failed=True;self.result={}
        finally:
            self.row=None;self.producer=None


class ArtJobs(QObject):
    """All methods/callbacks except _Worker.run belong to this GUI QObject.

    Pending state is at most16 keys; it never owns queued reference rows.
    Completion is delivered through QThread.finished after run has returned,
    so a rapid close/reopen cannot overlap the old and next computation.
    """
    changed=Signal()

    def __init__(self,prepare,producer,cached,commit,generation,parent=None):
        super().__init__(parent)
        self.prepare,self.producer=prepare,producer
        self.cached,self.commit,self.generation=cached,commit,generation
        self.active=False;self.epoch=0;self.wanted=OrderedDict()
        self.worker=None;self.done=set();self.closed=False
        # Capture only one small cancellation holder, never the controller or
        # this QObject. Direct QObject destruction also cancels pending work.
        self._lifetime_cancel={'event':None}
        state=self._lifetime_cancel
        self.destroyed.connect(lambda *_:state['event'].set() if state['event'] is not None else None)

    def activate(self,active):
        active=active is True
        if self.active==active:return
        self.active=active;self.epoch+=1
        self.wanted.clear();self.done.clear()
        if self.worker is not None:self.worker.cancel.set()

    def demand(self,keys):
        if self.closed or not self.active:return
        self.wanted=OrderedDict((key,None) for key in islice(keys,MAX_DEMAND))
        self.done.intersection_update(self.wanted)
        if self.worker is not None and self.worker.key not in self.wanted:self.worker.cancel.set()
        self._dispatch()

    def invalidate(self):
        self.epoch+=1;self.wanted.clear();self.done.clear()
        if self.worker is not None:self.worker.cancel.set()

    def _dispatch(self,retries=0):
        if self.closed or not self.active or self.worker is not None:return
        unavailable=False
        for key in tuple(self.wanted):
            if key in self.done or self.cached(key):continue
            if key[3]!=self.generation():continue
            try:row=self.prepare(key)
            except (OSError,ValueError,KeyError,RuntimeError):row=None
            generation=self.generation()
            if generation!=key[3]:
                self.wanted=OrderedDict(((*item[:3],generation),None) for item in self.wanted)
                self.done.clear()
                # A pack replacement can race a synthetic/custom prepare. Its
                # detached old row must never be relabelled with a new epoch.
                row=None
                if retries>=1:
                    self.done.update(self.wanted)
                    self.changed.emit()
                    return
                return self._dispatch(retries+1)
            if not row:
                self.done.add(key);unavailable=True;continue
            worker=_Worker(key,self.epoch,row,self.producer,self)
            self.worker=worker
            self._lifetime_cancel['event']=worker.cancel
            _LIVE.add(worker)
            worker.finished.connect(_reaper().release,Qt.ConnectionType.QueuedConnection)
            try:worker.start(QThread.Priority.LowPriority)
            except RuntimeError:
                self.worker=None;self._lifetime_cancel['event']=None
                _LIVE.discard(worker);worker.row=None;worker.producer=None
                worker.deleteLater();self.done.add(key);unavailable=True
                continue
            return
        if unavailable:self.changed.emit()

    def _receive(self,worker):
        if worker is None or worker is not self.worker:return
        self._lifetime_cancel['event']=None
        self.worker=None;key=worker.key
        current=(not self.closed and self.active and worker.epoch==self.epoch
                 and key in self.wanted and key[3]==self.generation()
                 and not worker.cancel.is_set())
        if current:
            self.done.add(key)
            if worker.result:self.commit(key,worker.result)
            self.changed.emit()
        self._dispatch()

    def status(self):
        return dict(active=self.active,inflight=int(self.worker is not None),
                    pending=sum(key not in self.done and not self.cached(key) and (self.worker is None or key!=self.worker.key)
                                for key in self.wanted),limit=MAX_DEMAND,epoch=self.epoch)

    def close(self,*,wait=False,timeout_ms=4000):
        self.activate(False);self.closed=True
        worker=self.worker
        self.worker=None
        self._lifetime_cancel['event']=None
        if worker is not None:worker.owner=lambda:None
        if wait and worker is not None:
            # Tests/tools may wait boundedly. Production GUI shutdown never
            # waits: the independent retirement set survives controller death.
            return worker.wait(timeout_ms)
        return worker is None or worker.isFinished()
