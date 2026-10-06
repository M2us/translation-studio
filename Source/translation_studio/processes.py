"""Background action execution with a Windows Job Object for the entire process tree."""
import ctypes
import codecs
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

from .core import Issue, StudioError, ProjectLock, digest, json_bytes, safe_path, work_path, file_hash
from .diagnostics import TailFile, ACTION_LOG_LIMIT, rotate_pair


class WindowsJob:
    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.kernel.SetInformationJobObject(
                self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process):
        if self.handle and not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def worker():
    """Wait for parent to attach the job before starting any action or descendants."""
    output_encoding = "utf-8"
    try:
        request = json.loads(sys.stdin.readline())
        output_encoding = request.get("outputEncoding", "utf-8")
        child = subprocess.Popen(request["command"], cwd=request["cwd"], stdin=subprocess.DEVNULL,
                                 stdout=sys.stdout, stderr=sys.stdout, shell=False,
                                 env={**os.environ, "PYTHONIOENCODING": output_encoding,
                                      "PYTHONUNBUFFERED": "1"})
        return child.wait()
    except Exception as error:
        # Worker diagnostics use the same encoding as the action's output channel.
        sys.stdout.buffer.write((str(error) + "\n").encode(output_encoding, errors="backslashreplace"))
        sys.stdout.buffer.flush()
        return 127


def worker_command():
    if getattr(sys, "frozen", False):
        # A windowed executable has no Python stdio, even with redirected handles.
        return [str(Path(sys.executable).with_name("TranslationStudio.Cli.exe")), "--worker"]
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "app.py"), "--worker"]


class ActionRunner:
    def __init__(self, project, action, python_override=""):
        self.project, self.action = project, action
        self.python_override = python_override
        self.events = queue.Queue(maxsize=512)
        self.process = None
        self.job = None
        self.cancelled = False
        self.finished = False
        self.guard = threading.Lock()
        self.log_path = None
        self.raw_log_path = None
        self.log_guard = None

    def emit(self, kind, value):
        while True:
            try:
                self.events.put_nowait((kind, value))
                return
            except queue.Full:
                try:
                    self.events.get_nowait()
                except queue.Empty:
                    pass

    def command(self):
        exe = self.action["executable"]
        if exe.lower() in ("python", "python.exe", "python3") and self.python_override:
            exe = self.python_override
        elif "/" in exe:
            exe = str(safe_path(self.project.root, exe))
        else:
            exe = shutil.which(exe)
        if not exe or not Path(exe).is_file():
            raise StudioError("missing_program", path=self.action["executable"])
        cwd = safe_path(self.project.root, self.action["workingDirectory"])
        if not cwd.is_dir():
            raise StudioError("missing_file", path=str(cwd))
        return [exe, *self.action["arguments"]], str(cwd)

    def start(self):
        if self.project.dirty:
            raise StudioError("unsaved")
        self.project.check_external()
        tabs = [key for key, tab in self.project.tabs.items()
                if tab.get("datasetId") in self.action["datasetIds"]]
        errors = [i for i in self.project.issues(tabs, self.action["targetLanguage"],
                                               self.action["requiresComplete"]) if i.severity == "error"]
        if errors:
            error = StudioError("validation", detail="\n".join(i.message() for i in errors))
            error.issues = errors
            raise error
        command, cwd = self.command()
        self.before = dict(self.project.hashes)
        log_dir = work_path(self.project.root, "Work/TranslationStudio/Logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_guard = ProjectLock(log_dir / "action.lock")
        if self.log_guard.stream is None:
            raise StudioError("busy")
        # Recognized logs from older builds are disposable output, not author data.
        for old in log_dir.iterdir():
            if re.fullmatch(r"\d{8}-\d{6}-\d+\.(log|output\.bin)", old.name) and old.is_file():
                old.unlink()
        self.log_path = rotate_pair(log_dir)
        rotate_pair(log_dir, ".output.bin")
        self.raw_log_path = self.log_path.with_suffix(".output.bin")
        self.thread = threading.Thread(target=self._run, args=(command, cwd), daemon=True)
        self.thread.start()

    def _run(self, command, cwd):
        result = 127
        encoding = self.action.get("outputEncoding", "utf-8")
        warned = False
        try:
            with TailFile(self.log_path, ACTION_LOG_LIMIT) as log, TailFile(self.raw_log_path, ACTION_LOG_LIMIT, binary=True) as raw_log:
                line = json.dumps({"command": command, "cwd": cwd, "outputEncoding": encoding}, ensure_ascii=False) + "\n"
                log.write(line)
                self.emit("line", line)
                with self.guard:
                    if self.cancelled:
                        return
                    self.job = WindowsJob()
                    self.process = subprocess.Popen(
                        worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
                    # The worker cannot execute the configured command until we send this payload.
                    self.job.assign(self.process)
                    payload = {"command": command, "cwd": cwd, "outputEncoding": encoding}
                    self.process.stdin.write((json.dumps(payload, ensure_ascii=True) + "\n").encode("ascii"))
                    self.process.stdin.close()
                decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
                buffered = ""
                while True:
                    raw = self.process.stdout.read1(4096)
                    raw_log.write(raw)
                    state = decoder.getstate()
                    try:
                        output = decoder.decode(raw, final=not raw)
                    except UnicodeDecodeError:
                        decoder.setstate(state)
                        decoder.errors = "backslashreplace"
                        output = decoder.decode(raw, final=not raw)
                        decoder.errors = "strict"
                        if not warned:
                            warned = True
                            issue = Issue("log_encoding", {"encoding": encoding, "path": str(self.raw_log_path)}, "warning")
                            log.write(issue.message("ru") + "\n")
                            self.emit("warning", issue)
                    log.write(output)
                    buffered += output
                    while "\n" in buffered or len(buffered) >= 4096:
                        length = min(buffered.find("\n") + 1 if "\n" in buffered else 4096, 4096)
                        self.emit("line", buffered[:length].replace("\r\n", "\n"))
                        buffered = buffered[length:]
                    if not raw:
                        if buffered:
                            self.emit("line", buffered)
                        break
                result = self.process.wait()
                log.write(f"\n[exit={result}; cancelled={self.cancelled}]\n")
        except Exception as error:
            self.emit("line", str(error) + "\n")
            try:
                with TailFile(self.log_path, ACTION_LOG_LIMIT, append=True) as stream:
                    stream.write("\n[runner error: " + type(error).__name__ + "]\n")
            except OSError:
                pass
        finally:
            with self.guard:
                if self.job:
                    self.job.close()
                if self.process and self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
            changed = any(file_hash(path) != expected for path, expected in self.before.items())
            if self.log_guard:
                self.log_guard.close()
            self.finished = True
            self.emit("done", {"code": result, "cancelled": self.cancelled, "changed": changed})

    def cancel(self):
        with self.guard:
            self.cancelled = True
            if self.job:
                self.job.close()
            if self.process and self.process.poll() is None and os.name != "nt":
                self.process.kill()


def trust_key(project):
    return digest(json_bytes({"root": str(project.root), "projectId": project.config["projectId"],
                              "actions": project.config.get("actions", [])}))
