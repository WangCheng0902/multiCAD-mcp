"""Serialize CAD work on one message-pumping STA; never share COM across callers."""
import atexit
import contextvars
import logging
import queue
import threading
from concurrent.futures import Future
from functools import wraps

import pythoncom

logger = logging.getLogger(__name__)


class CadExecutor:
    def __init__(self):
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self._thread = None
        self._owner = None
        self._closed = False
        self._ready = threading.Event()
        self._startup_error = None

    def _run(self):
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        except BaseException as error:
            self._startup_error = error
            self._ready.set()
            return
        self._owner = threading.get_ident()
        self._ready.set()
        logger.info("CAD STA ready owner_thread=%s", self._owner)
        try:
            while True:
                pythoncom.PumpWaitingMessages()
                try:
                    work = self._queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                if work is None:
                    break
                future, context, function, args, kwargs, caller = work
                if not future.set_running_or_notify_cancel():
                    continue
                logger.info("CAD dispatch task=%s caller_thread=%s owner_thread=%s",
                            function.__name__, caller, self._owner)
                try:
                    future.set_result(context.run(function, *args, **kwargs))
                except BaseException as error:
                    future.set_exception(error)
        finally:
            # Release cached COM references in their owning apartment.
            from adapters.adapter_manager import shutdown_all
            from mcp_tools.decorators import set_current_adapter
            shutdown_all()
            set_current_adapter(None)
            pythoncom.CoUninitialize()

    def call(self, function, *args, **kwargs):
        if threading.get_ident() == self._owner:
            return function(*args, **kwargs)
        with self._lock:
            if self._closed:
                raise RuntimeError("CAD executor is closed")
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="CAD-STA", daemon=True)
                self._thread.start()
            if not self._ready.wait(timeout=5):
                raise RuntimeError("CAD STA initialization timed out")
            if self._startup_error is not None:
                raise RuntimeError("CAD STA initialization failed") from self._startup_error
            future = Future()
            self._queue.put((future, contextvars.copy_context(), function, args, kwargs,
                             threading.get_ident()))
        # A running write is never timed out and replayed by this executor.
        return future.result()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._thread is None:
                return
            self._queue.put(None)
        if threading.get_ident() != self._owner:
            self._thread.join(timeout=5)


executor = CadExecutor()
atexit.register(executor.close)


def cad_serialized(function):
    @wraps(function)
    def serialized(*args, **kwargs):
        return executor.call(function, *args, **kwargs)
    return serialized
