"""Bounded recovery for COM reads. Never retry a mutating method or setter."""
import logging
import time
import pythoncom
from win32com.client import dynamic

logger = logging.getLogger(__name__)
def pump_pause(seconds):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        pythoncom.PumpWaitingMessages()
        time.sleep(0.01)
READ_METHODS = {"Item", "GetVariable", "GetBoundingBox", "GetFont"}
METHODS = READ_METHODS | {
    "Activate", "Close", "Open", "Save", "SaveAs", "Regen", "Move", "Copy",
    "Delete", "Clear", "Select", "SelectOnScreen", "SetVariable", "SetFont",
    "SendCommand", "ZoomExtents", "ZoomWindow", "InsertBlock", "Rotate",
    "ScaleEntity", "Explode", "AppendOuterLoop", "AppendInnerLoop", "Evaluate",
}

def read_call(fn, label):
    for attempt in range(3):
        try:
            return fn()
        except pythoncom.com_error as error:
            if error.hresult != -2147418111 or attempt == 2:
                raise
            logger.warning("COM read rejected: %s; bounded recovery %d/2", label, attempt + 1)
            deadline = time.monotonic() + 0.2
            while time.monotonic() < deadline:
                pythoncom.PumpWaitingMessages()
                time.sleep(0.01)

def wrap(value):
    if isinstance(value, ReadOnlyRecovery):
        return value
    if hasattr(value, "_oleobj_"):
        return ReadOnlyRecovery(dynamic.Dispatch(value._oleobj_))
    if isinstance(value, tuple):
        return tuple(wrap(item) for item in value)
    return value

class ReadOnlyRecovery:
    def __init__(self, target):
        object.__setattr__(self, "_target", target)

    @property
    def _oleobj_(self):
        return self._target._oleobj_

    def _FlagAsMethod(self, name):
        self._target._FlagAsMethod(name)

    def __getattr__(self, name):
        def lookup():
            if name in METHODS or name.startswith("Add"):
                self._target._FlagAsMethod(name)
            try:
                return getattr(self._target, name)
            except AttributeError:
                # pywin32 suppresses errors during lazy GetIDsOfNames. Expose the
                # actual HRESULT so only genuine call rejection is recoverable.
                self._target._oleobj_.GetIDsOfNames(name)
                return getattr(self._target, name)
        value = read_call(lookup, name + " member lookup")
        if hasattr(value, "_oleobj_"):
            return wrap(value)
        if callable(value):
            def call(*args, **kwargs):
                if name not in READ_METHODS:
                    pump_pause(0.05)
                operation = lambda: value(*args, **kwargs)
                result = read_call(operation, name) if name in READ_METHODS else operation()
                return wrap(result)
            return call
        return value

    def __setattr__(self, name, value):
        pump_pause(0.05)
        setattr(self._target, name, value)

    def __iter__(self):
        iterator = read_call(lambda: iter(self._target), "collection enumeration")
        while True:
            pythoncom.PumpWaitingMessages()
            try:
                value = read_call(lambda: next(iterator), "collection next")
            except StopIteration:
                return
            yield wrap(value)

    def __getitem__(self, index):
        return wrap(read_call(lambda: self._target[index], "collection index"))
