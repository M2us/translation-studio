"""Bounded, flushed diagnostics. Never record exception messages, locals or UI text."""
import faulthandler
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from .settings import logs_path

APP_LOG_LIMIT = 2 * 1024 * 1024
ACTION_LOG_LIMIT = 2 * 1024 * 1024
_session = None


class TailFile:
    """Retain the tail in one file; keep its descriptor stable for faulthandler."""
    def __init__(self, path, limit, *, binary=False, append=False):
        self.path, self.limit, self.binary = Path(path), limit, binary
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("r+b" if append and self.path.exists() else "w+b", buffering=0)
        self.lock = threading.RLock()

    def write(self, value):
        raw = value if isinstance(value, bytes) else value.encode("utf-8", errors="backslashreplace")
        with self.lock:
            self.stream.seek(0, 2)
            if self.stream.tell() + len(raw) > self.limit:
                keep = self.limit // 2
                self.stream.seek(max(0, self.stream.tell() - keep))
                raw = (self.stream.read() + raw)[-self.limit:]
                if not self.binary:
                    # Drop a partial first line/character after a tail truncation.
                    raw = raw[raw.find(b"\n") + 1:] if b"\n" in raw else raw.decode("utf-8", "ignore").encode("utf-8")
                self.stream.seek(0)
                self.stream.truncate()
            self.stream.write(raw)
        return len(value)

    def flush(self):
        self.stream.flush()

    def fileno(self):
        return self.stream.fileno()

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def rotate_pair(directory, suffix=".log"):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    current, previous = directory / ("current" + suffix), directory / ("previous" + suffix)
    if current.exists():
        # Includes direct native-crash output, which bypasses TailFile.write.
        raw = current.read_bytes()
        if len(raw) > APP_LOG_LIMIT:
            current.write_bytes(raw[-APP_LOG_LIMIT:])
        os.replace(current, previous)
    return current


class Session:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        # Two instances must never rotate/write the same session files.
        from .core import ProjectLock
        self.guard = ProjectLock(self.directory / "session.lock")
        if self.guard.stream is None:
            raise RuntimeError("Translation Studio is already using this portable profile")
        self.log = TailFile(rotate_pair(self.directory), APP_LOG_LIMIT - 512 * 1024)
        self.hooks = sys.excepthook, threading.excepthook, sys.unraisablehook
        sys.excepthook = lambda typ, value, tb: self.exception(value, tb, "unhandled")
        threading.excepthook = lambda args: self.exception(args.exc_value, args.exc_traceback, "thread")
        sys.unraisablehook = lambda args: self.exception(args.exc_value, args.exc_traceback, "unraisable")
        faulthandler.enable(self.log.stream, all_threads=False)
        self.event("application.start", python=sys.version.split()[0])

    def event(self, name, **fields):
        # Call sites pass only fixed event names, enums and numeric counts.
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": name, **fields}
        self.log.write(json.dumps(record, ensure_ascii=True) + "\n")

    def exception(self, error, tb=None, origin="handled"):
        if tb is None:
            tb = error.__traceback__
        frames = [{"file": Path(frame.f_code.co_filename).name, "line": line,
                   "function": frame.f_code.co_name} for frame, line in traceback.walk_tb(tb)]
        self.event("error", origin=origin, type=type(error).__name__,
                   code=getattr(getattr(error, "issue", None), "code", None),
                   errno=getattr(error, "errno", None), winerror=getattr(error, "winerror", None), frames=frames)

    def close(self):
        global _session
        self.event("application.exit")
        faulthandler.disable()
        sys.excepthook, threading.excepthook, sys.unraisablehook = self.hooks
        self.log.close()
        self.guard.close()
        if _session is self:
            _session = None


def start(directory=None):
    global _session
    _session = Session(directory or logs_path())
    return _session


def event(name, **fields):
    if _session:
        try:
            _session.event(name, **fields)
        except OSError:
            pass  # A full/unmounted disk must not prevent editing or error dialogs.


def error(exc):
    if _session:
        try:
            _session.exception(exc)
        except OSError:
            pass
