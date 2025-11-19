from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import tty
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .analysis import PROMPT_SENTINEL
from .db import Database, utcnow
from .engine import RecommendationEngine


def _set_nonblocking(fd: int) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def _winsize() -> bytes:
    try:
        packed = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        return packed
    except Exception:
        return struct.pack("HHHH", 40, 160, 0, 0)


@dataclass
class RecorderState:
    current_command: Optional[str] = None
    current_input: Optional[str] = None
    started_at: Optional[str] = None
    buffer: List[str] = field(default_factory=list)


class SessionRecorder:
    def __init__(self, engine: RecommendationEngine, session_id: int):
        self.engine = engine
        self.session_id = session_id
        self.state = RecorderState()
        self.command_buffer = ""
        self.prompt_window = ""

    def handle_input(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="ignore")
        for ch in text:
            if ch == "\x7f":  # backspace
                self.command_buffer = self.command_buffer[:-1]
            elif ch in ("\r", "\n"):
                self._handle_enter()
            elif ch == "\x03":  # Ctrl+C resets
                self._reset_command()
            else:
                self.command_buffer += ch

    def _reset_command(self) -> None:
        self.command_buffer = ""

    def _handle_enter(self) -> None:
        line = self.command_buffer.strip()
        self.command_buffer = ""
        if not line:
            return
        self.state.current_command = line
        self.state.current_input = line
        self.state.started_at = utcnow()
        self.state.buffer = []

    def handle_output(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="ignore")
        if self.state.current_command:
            self.state.buffer.append(text)
        self.prompt_window += text
        if PROMPT_SENTINEL in self.prompt_window:
            if self.state.current_command:
                self._finalize_event()
            self.prompt_window = ""
        elif len(self.prompt_window) > len(PROMPT_SENTINEL) * 4:
            self.prompt_window = self.prompt_window[-len(PROMPT_SENTINEL) * 4 :]

    def flush(self) -> None:
        self._finalize_event(force=True)

    def _finalize_event(self, force: bool = False) -> None:
        if not self.state.current_command:
            return
        output_text = "".join(self.state.buffer or [])
        if not output_text and not force:
            return
        self.engine.process_event(
            self.session_id,
            command=self.state.current_command,
            raw_input=self.state.current_input or self.state.current_command,
            raw_output=output_text,
            started_at=self.state.started_at,
            finished_at=utcnow(),
        )
        self.state = RecorderState()


class PtySession:
    def __init__(
        self,
        session_name: str,
        command: Sequence[str],
        db: Database,
        engine: RecommendationEngine,
    ):
        self.session_name = session_name
        self.command = list(command)
        self.db = db
        self.engine = engine
        self.session_id = self.db.ensure_session(session_name)
        self.recorder = SessionRecorder(engine, self.session_id)
        self.child_pid: Optional[int] = None
        self.master_fd: Optional[int] = None
        self._orig_tty = None

    def start(self) -> int:
        pid, master_fd = pty.fork()
        if pid == 0:
            self._exec_child()
        self.child_pid = pid
        self.master_fd = master_fd
        self._setup_terminal()
        self._loop()
        return os.waitpid(self.child_pid, 0)[1]

    def _exec_child(self) -> None:  # pragma: no cover - child process
        env = os.environ.copy()
        env.setdefault("PS1", f"{PROMPT_SENTINEL} \\u@\\h:\\w\\$ ")
        env["PROMPT_COMMAND"] = ""
        env["FLAGCADDY_SESSION"] = self.session_name
        try:
            os.execvpe(self.command[0], self.command, env)
        except FileNotFoundError:
            print(f"Unable to exec {self.command[0]}", file=sys.stderr)
            os._exit(1)

    def _setup_terminal(self) -> None:
        assert self.master_fd is not None
        self._orig_tty = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
        _set_nonblocking(self.master_fd)
        _set_nonblocking(sys.stdin.fileno())
        signal.signal(signal.SIGWINCH, self._resize_pty)
        self._resize_pty()

    def _restore_terminal(self) -> None:
        if self._orig_tty:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._orig_tty)
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)

    def _resize_pty(self, *_args) -> None:
        if self.master_fd is None:
            return
        try:
            winsize = _winsize()
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    def _loop(self) -> None:
        assert self.master_fd is not None
        try:
            while True:
                rlist, _, _ = select.select(
                    [self.master_fd, sys.stdin.fileno()],
                    [],
                    [],
                )
                if sys.stdin.fileno() in rlist:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if data:
                        os.write(self.master_fd, data)
                        self.recorder.handle_input(data)
                if self.master_fd in rlist:
                    try:
                        data = os.read(self.master_fd, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
                    self.recorder.handle_output(data)
        finally:
            self.recorder.flush()
            self._restore_terminal()


__all__ = ["PtySession"]
