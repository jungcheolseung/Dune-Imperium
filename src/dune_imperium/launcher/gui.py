"""The launcher window: tkinter/ttk, Korean labels (plan 2, 5.8, 5.9).

Only Tk's thread touches a widget. The controller reports from its worker
threads into ``self._events``; ``_pump`` applies them every 0.1 s. Tk 8.6
(uv's Windows Python 3.14 before PBS 20260804) and 9.0 (macOS) are both
supported, so nothing here needs Tk 9.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
import webbrowser
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from types import TracebackType
from typing import Final

from dune_imperium.launcher.addresses import best_remote_address
from dune_imperium.launcher.command import find_free_port
from dune_imperium.launcher.controller import (
    AddressesFound,
    ChecksDone,
    Controller,
    Emit,
    Event,
    LogLine,
    Phase,
    PhaseChanged,
    ServerStopped,
    Started,
    StartFailed,
)
from dune_imperium.launcher.settings import (
    SETTINGS_FILE,
    KeyMode,
    LauncherSettings,
    Mode,
    Window,
    resolved_path,
    stored_path,
)
from dune_imperium.launcher.supervisor import LOG_DIR
from dune_imperium.launcher.view import (
    AI_PACE_LABELS,
    Tone,
    address_from_choice,
    controls,
    problem_lines,
    status,
    window_geometry,
)
from dune_imperium.paths import PROJECT_ROOT

TITLE: Final = "Dune Imperium 서버"
LAUNCHER_LOG: Final = LOG_DIR / "launcher.log"
_LOG_LIMIT: Final = 2000
_LAUNCHER_LOG_BYTES: Final = 1_000_000
_PUMP_MS: Final = 100
# Readable on the light and the dark theme alike; the status line also
# always says its state in words.
_TONE_COLOURS: Final[dict[Tone, str]] = {
    "plain": "",
    "good": "#2f9e44",
    "busy": "#d9822b",
    "warn": "#d9822b",
    "bad": "#d64545",
}

MakeController = Callable[[Path, Emit], Controller]


class _Close:
    """Sent to the pump once the server is down and the window may go."""


def launcher_log(text: str) -> None:
    """Append to ``tmp/launcher/launcher.log``: the windowless launcher's
    only output (``pythonw`` has no console). Rotated once at 1 MB."""

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LAUNCHER_LOG.exists() and LAUNCHER_LOG.stat().st_size > _LAUNCHER_LOG_BYTES:
            os.replace(LAUNCHER_LOG, LAUNCHER_LOG.with_suffix(".log.1"))
        stamp = datetime.now().isoformat(timespec="seconds")
        with LAUNCHER_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {text}\n")
    except OSError:
        pass


def reveal(path: Path) -> None:
    """Show a folder in Finder or Explorer."""

    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _open_in_browser(url: str) -> None:
    threading.Thread(
        target=webbrowser.open, args=(url,), name="launcher-browser", daemon=True
    ).start()


def _windows_dpi_awareness() -> None:
    """Draw sharply on a scaled Windows display, as IDLE does.

    Neither python.exe nor Tk declares DPI awareness, so without this the
    window is a blurred bitmap at 125-200 %. System awareness (1), not per
    monitor: Tk does not handle WM_DPICHANGED. Before the first Tk().
    """

    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.OleDLL("shcore").SetProcessDpiAwareness(1)
        except ImportError, AttributeError, OSError:
            pass


def _korean_fonts(root: tk.Misc) -> None:
    """On Windows, the UI fonts in Malgun Gothic when it is there."""

    if sys.platform != "win32":
        return
    if "Malgun Gothic" not in tkfont.families(root):
        return
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name, root).configure(family="Malgun Gothic")


class LauncherWindow:
    def __init__(
        self,
        root: tk.Tk | tk.Toplevel,
        settings_path: Path = SETTINGS_FILE,
        *,
        make_controller: MakeController = lambda path, emit: Controller(path, emit),
    ) -> None:
        self.root = root
        self._events: queue.Queue[Event | _Close] = queue.Queue()
        self.controller = make_controller(settings_path, self._events.put)
        self._phase = Phase.IDLE
        self._error: str | None = None
        self._closing = False
        self._edit_widgets: list[ttk.Widget] = []
        self._remote_widgets: list[ttk.Widget] = []
        self._build()
        self.fill_form(self.controller.settings)
        for note in self.controller.notes:
            self._show_problem(f"[참고] {note}", "plain")
        self._refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(_PUMP_MS, self._pump)
        self.controller.find_addresses()

    # --- layout -----------------------------------------------------------

    def _build(self) -> None:
        root = self.root
        root.title(TITLE)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frame = ttk.Frame(root, padding=12)
        frame.grid(sticky="nsew")
        # Settings on the left, running the server on the right: short
        # enough for a 1280x800 laptop screen.
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)
        side = ttk.Frame(frame)
        side.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(12, 0))
        side.columnconfigure(0, weight=1)
        side.rowconfigure(2, weight=1)

        self.mode = tk.StringVar(master=root)
        self.address = tk.StringVar(master=root)
        self.port = tk.StringVar(master=root)
        self.public_url = tk.StringVar(master=root)
        self.key_mode = tk.StringVar(master=root)
        self.saves_dir = tk.StringVar(master=root)
        self.autosave = tk.BooleanVar(master=root)
        self.search_checkpoint = tk.StringVar(master=root)
        self.ai_pace = tk.StringVar(master=root)
        self.assets_dir = tk.StringVar(master=root)
        self.open_browser = tk.BooleanVar(master=root)
        self.status_text = tk.StringVar(master=root)
        self.open_url = tk.StringVar(master=root)
        self.room_base = tk.StringVar(master=root)
        self.address_hint = tk.StringVar(master=root, value="주소를 찾는 중…")

        server = ttk.LabelFrame(frame, text="서버", padding=8)
        server.grid(row=0, column=0, sticky="new")
        server.columnconfigure(1, weight=1)
        modes = ttk.Frame(server)
        modes.grid(row=0, column=0, columnspan=3, sticky="w")
        local = ttk.Radiobutton(
            modes,
            text="이 컴퓨터에서만 (로컬)",
            value="local",
            variable=self.mode,
            command=self._refresh,
        )
        local.grid(row=0, column=0, padx=(0, 16))
        remote = ttk.Radiobutton(
            modes,
            text="다른 사람과 (원격: 같은 네트워크·Tailscale)",
            value="remote",
            variable=self.mode,
            command=self._refresh,
        )
        remote.grid(row=0, column=1)
        self._edit_widgets += [local, remote]

        ttk.Label(server, text="주소").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.address_box = ttk.Combobox(server, textvariable=self.address)
        self.address_box.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        rescan = ttk.Button(server, text="다시 찾기", command=self._rescan)
        rescan.grid(row=1, column=2, padx=(6, 0), pady=(8, 0))
        ttk.Label(server, textvariable=self.address_hint).grid(
            row=2, column=1, columnspan=2, sticky="w"
        )
        self._remote_widgets += [self.address_box, rescan]

        ttk.Label(server, text="포트").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ports = ttk.Frame(server)
        ports.grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))
        port_box = ttk.Spinbox(
            ports, from_=1, to=65535, textvariable=self.port, width=8
        )
        port_box.grid(row=0, column=0)
        free = ttk.Button(ports, text="빈 포트 찾기", command=self._free_port)
        free.grid(row=0, column=1, padx=(6, 0))
        self._edit_widgets += [port_box, free]

        ttk.Label(server, text="공개 주소").grid(
            row=4, column=0, sticky="w", pady=(6, 0)
        )
        public = ttk.Entry(server, textvariable=self.public_url)
        public.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(server, text="비우면 http://<주소>:<포트> (방 링크의 앞부분)").grid(
            row=5, column=1, columnspan=2, sticky="w"
        )
        self._remote_widgets.append(public)

        keys = ttk.Frame(server)
        keys.grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(keys, text="관리자 키").grid(row=0, column=0, padx=(0, 8))
        fixed = ttk.Radiobutton(
            keys, text="고정 (같은 관리자 링크)", value="fixed", variable=self.key_mode
        )
        fixed.grid(row=0, column=1, padx=(0, 12))
        fresh = ttk.Radiobutton(
            keys, text="시작할 때마다 새로", value="fresh", variable=self.key_mode
        )
        fresh.grid(row=0, column=2, padx=(0, 12))
        renew = ttk.Button(keys, text="새 키 만들기", command=self._renew_key)
        renew.grid(row=0, column=3)
        self._remote_widgets += [fixed, fresh, renew]

        game = ttk.LabelFrame(frame, text="게임", padding=8)
        game.grid(row=1, column=0, sticky="new", pady=(10, 0))
        game.columnconfigure(1, weight=1)
        self._path_row(game, 0, "저장 폴더", self.saves_dir, directory=True)
        autosave = ttk.Checkbutton(
            game, text="자동 저장 (원격: 턴이 넘어갈 때마다)", variable=self.autosave
        )
        autosave.grid(row=1, column=1, columnspan=2, sticky="w")
        self._remote_widgets.append(autosave)
        self._path_row(game, 2, "탐색 AI 망", self.search_checkpoint, directory=False)
        ttk.Label(game, text="비우면 checkpoints/play/search.pt").grid(
            row=3, column=1, columnspan=2, sticky="w"
        )
        ttk.Label(game, text="AI 속도").grid(row=4, column=0, sticky="w", pady=(6, 0))
        pace = ttk.Combobox(
            game,
            textvariable=self.ai_pace,
            values=list(AI_PACE_LABELS.values()),
            state="readonly",
            width=10,
        )
        pace.grid(row=4, column=1, sticky="w", pady=(6, 0))
        self._edit_widgets.append(pace)
        self._path_row(game, 5, "그림 폴더", self.assets_dir, directory=True)
        ttk.Label(game, text="비우면 프로젝트의 assets").grid(
            row=6, column=1, columnspan=2, sticky="w"
        )

        run = ttk.Frame(side)
        run.grid(row=0, column=0, sticky="ew")
        run.columnconfigure(3, weight=1)
        browser = ttk.Checkbutton(
            run, text="시작하면 브라우저로 열기", variable=self.open_browser
        )
        browser.grid(row=0, column=0, columnspan=4, sticky="w")
        self._edit_widgets.append(browser)
        self.start_button = ttk.Button(run, text="시작", command=self.start)
        self.start_button.grid(row=1, column=0, pady=(6, 0))
        self.stop_button = ttk.Button(run, text="중지", command=self.stop)
        self.stop_button.grid(row=1, column=1, padx=(6, 0), pady=(6, 0))
        self.status_label = ttk.Label(run, textvariable=self.status_text)
        self.status_label.grid(row=1, column=3, sticky="w", padx=(12, 0), pady=(6, 0))
        self.problems = tk.Text(run, height=5, width=48, wrap="word", relief="flat")
        self.problems.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        for tone, colour in _TONE_COLOURS.items():
            if colour:
                self.problems.tag_configure(tone, foreground=colour)
        self.problems.configure(state="disabled")

        links = ttk.LabelFrame(side, text="링크", padding=8)
        links.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        links.columnconfigure(1, weight=1)
        self.open_label = ttk.Label(links, text="관리자 링크")
        self.open_label.grid(row=0, column=0, sticky="w")
        self.open_entry = ttk.Entry(links, textvariable=self.open_url, state="readonly")
        self.open_entry.grid(row=0, column=1, sticky="ew")
        self.copy_open = ttk.Button(
            links, text="복사", command=lambda: self.copy(self.open_url.get())
        )
        self.copy_open.grid(row=0, column=2, padx=(6, 0))
        self.open_button = ttk.Button(
            links, text="열기", command=lambda: _open_in_browser(self.open_url.get())
        )
        self.open_button.grid(row=0, column=3, padx=(6, 0))
        ttk.Label(links, text="방 링크 앞부분").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(links, textvariable=self.room_base, state="readonly").grid(
            row=1, column=1, sticky="ew", pady=(6, 0)
        )
        self.copy_room = ttk.Button(
            links, text="복사", command=lambda: self.copy(self.room_base.get())
        )
        self.copy_room.grid(row=1, column=2, padx=(6, 0), pady=(6, 0))

        logs = ttk.LabelFrame(side, text="서버 로그", padding=8)
        logs.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        logs.columnconfigure(0, weight=1)
        logs.rowconfigure(0, weight=1)
        self.log = tk.Text(logs, height=8, width=48, wrap="none", font="TkFixedFont")
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(logs, orient="vertical", command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set, state="disabled")
        ttk.Button(logs, text="로그 폴더 열기", command=lambda: reveal(LOG_DIR)).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

    def _path_row(
        self,
        parent: ttk.Frame | ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        directory: bool,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(6, 0))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=(6, 0))

        def browse() -> None:
            current = variable.get().strip()
            start = resolved_path(current) if current else PROJECT_ROOT
            if directory:
                chosen = filedialog.askdirectory(
                    parent=self.root, initialdir=str(start)
                )
            else:
                chosen = filedialog.askopenfilename(
                    parent=self.root,
                    initialdir=str(start.parent if start.suffix else start),
                    filetypes=[("PyTorch 체크포인트", "*.pt"), ("모든 파일", "*")],
                )
            if chosen:
                variable.set(stored_path(Path(chosen)))

        button = ttk.Button(parent, text="찾아보기", command=browse)
        button.grid(row=row, column=2, padx=(6, 0), pady=(6, 0))
        self._edit_widgets += [entry, button]

    # --- form <-> settings ------------------------------------------------

    def fill_form(self, settings: LauncherSettings) -> None:
        self.mode.set(settings.mode)
        self.address.set(settings.host)
        self.port.set(str(settings.port))
        self.public_url.set(settings.public_url or "")
        self.key_mode.set(settings.admin_key_mode)
        self.saves_dir.set(settings.saves_dir or "")
        self.autosave.set(settings.autosave)
        self.search_checkpoint.set(settings.search_checkpoint or "")
        self.ai_pace.set(AI_PACE_LABELS.get(settings.ai_pace, AI_PACE_LABELS["normal"]))
        self.assets_dir.set(settings.assets_dir or "")
        self.open_browser.set(settings.open_browser)

    def read_form(self) -> LauncherSettings:
        """The settings the form shows, on top of what it does not show."""

        try:
            port = int(self.port.get().strip())
        except ValueError:
            port = 0
        pace = next(
            (
                value
                for value, label in AI_PACE_LABELS.items()
                if label == self.ai_pace.get()
            ),
            "normal",
        )
        mode: Mode = "remote" if self.mode.get() == "remote" else "local"
        key_mode: KeyMode = "fresh" if self.key_mode.get() == "fresh" else "fixed"
        return replace(
            self.controller.settings,
            mode=mode,
            host=address_from_choice(self.address.get()),
            port=port,
            public_url=self.public_url.get().strip() or None,
            admin_key_mode=key_mode,
            saves_dir=self.saves_dir.get().strip() or None,
            autosave=self.autosave.get(),
            search_checkpoint=self.search_checkpoint.get().strip() or None,
            ai_pace=pace,
            assets_dir=self.assets_dir.get().strip() or None,
            open_browser=self.open_browser.get(),
            window=self._geometry(),
        )

    def _geometry(self) -> Window | None:
        try:
            self.root.update_idletasks()
            width, height = self.root.winfo_width(), self.root.winfo_height()
            if width < 50 or height < 50:
                return self.controller.settings.window
            return Window(self.root.winfo_x(), self.root.winfo_y(), width, height)
        except tk.TclError:
            return self.controller.settings.window

    # --- actions ----------------------------------------------------------

    def start(self) -> None:
        self._error = None
        self._clear_problems()
        self.controller.start(self.read_form())

    def stop(self) -> None:
        self.controller.stop()

    def copy(self, text: str) -> None:
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._show_problem("[참고] 클립보드에 복사했습니다", "plain", replace_all=True)

    def _rescan(self) -> None:
        self.address_hint.set("주소를 찾는 중…")
        self.controller.find_addresses()

    def _free_port(self) -> None:
        settings = self.read_form()
        host = (
            settings.host
            if settings.mode == "remote" and settings.host
            else "127.0.0.1"
        )
        try:
            start = int(self.port.get())
        except ValueError:
            start = 8000
        try:
            self.port.set(str(find_free_port(host, start)))
        except OSError as error:
            self._show_problem(f"[오류] 빈 포트를 찾지 못했습니다: {error}", "bad")

    def _renew_key(self) -> None:
        if messagebox.askyesno(
            TITLE,
            "관리자 키를 새로 만들까요?\n"
            "예전 관리자 링크는 다음 시작부터 쓸 수 없습니다.",
            parent=self.root,
        ):
            self.controller.remember(replace(self.read_form(), admin_key=None))

    def close(self) -> None:
        """Close the window; a running server is stopped first, on a yes."""

        if self._closing:
            return
        if self._phase is Phase.IDLE:
            self._finish_close()
            return
        if not messagebox.askyesno(
            TITLE,
            "서버를 끄고 런처를 닫을까요?\n\n진행 중이던 턴은 사라질 수 있습니다. "
            "먼저 게임 화면에서 '지금 저장'을 누르면 안전합니다.",
            parent=self.root,
        ):
            return
        self._closing = True
        self.controller.remember(self.read_form())
        if not self.controller.stop(then=lambda: self._events.put(_Close())):
            self._events.put(_Close())

    def _finish_close(self) -> None:
        self.controller.remember(self.read_form())
        self.root.destroy()

    # --- events from the controller --------------------------------------

    def _pump(self) -> None:
        try:
            self.controller.poll()
            while True:
                try:
                    event = self._events.get_nowait()
                except queue.Empty:
                    break
                if isinstance(event, _Close):
                    self.root.destroy()
                    return
                self.apply(event)
        except Exception:  # keep pumping: one bad event must not freeze the window
            launcher_log(traceback.format_exc())
        self.root.after(_PUMP_MS, self._pump)

    def apply(self, event: Event) -> None:
        if isinstance(event, PhaseChanged):
            self._phase = event.phase
        elif isinstance(event, AddressesFound):
            self._show_addresses(event)
        elif isinstance(event, ChecksDone):
            self._clear_problems()
            for text, tone in problem_lines(event.problems):
                self._show_problem(text, tone)
        elif isinstance(event, Started):
            self.open_label.configure(
                text="관리자 링크" if event.plan.remote else "게임 화면"
            )
            self.open_url.set(event.plan.open_url)
            self.room_base.set(event.plan.room_base)
            if self.open_browser.get():
                _open_in_browser(event.plan.open_url)
        elif isinstance(event, StartFailed):
            self._error = event.message
            self._show_problem(f"[오류] {event.message}", "bad")
        elif isinstance(event, ServerStopped):
            self.open_url.set("")
            self.room_base.set("")
            if event.unexpected:
                self._error = event.unexpected
                self._show_problem(f"[오류] {event.unexpected}", "bad")
            elif not event.result.port_free:
                self._show_problem(
                    "[주의] 서버는 꺼졌지만 포트가 아직 풀리지 않았습니다", "warn"
                )
        elif isinstance(event, LogLine):
            self._append_log(event.text)
        self._refresh()

    def _show_addresses(self, event: AddressesFound) -> None:
        found = event.discovery
        self.address_box.configure(values=[c.label for c in found.candidates])
        current = address_from_choice(self.address.get())
        match = next((c for c in found.candidates if c.ip == current), None)
        if match is not None:
            self.address.set(match.label)
        elif not current:
            best = best_remote_address(found)
            pick = next((c for c in found.candidates if c.ip == best), None)
            if pick is not None:
                self.address.set(pick.label)
        hints = []
        if found.tailscale is None:
            hints.append("Tailscale CLI 없음")
        elif not found.tailscale.running:
            hints.append("Tailscale 꺼짐")
        if not found.internet_route:
            hints.append("인터넷 없음(LAN 플레이 가능)")
        self.address_hint.set(" · ".join(hints) if hints else "")

    # --- drawing ------------------------------------------------------------

    def _refresh(self) -> None:
        mode: Mode = "remote" if self.mode.get() == "remote" else "local"
        shown = controls(self._phase, mode)
        for widget in self._edit_widgets:
            widget.state(["!disabled"] if shown.editable else ["disabled"])
        for widget in self._remote_widgets:
            widget.state(["!disabled"] if shown.remote_fields else ["disabled"])
        self.start_button.state(["!disabled"] if shown.can_start else ["disabled"])
        self.stop_button.state(["!disabled"] if shown.can_stop else ["disabled"])
        for widget in (self.copy_open, self.open_button, self.copy_room):
            widget.state(["!disabled"] if shown.links else ["disabled"])
        text, tone = status(self._phase, error=self._error)
        self.status_text.set(text)
        self.status_label.configure(foreground=_TONE_COLOURS[tone])

    def _clear_problems(self) -> None:
        self.problems.configure(state="normal")
        self.problems.delete("1.0", "end")
        self.problems.configure(state="disabled")

    def _show_problem(
        self, text: str, tone: Tone, *, replace_all: bool = False
    ) -> None:
        if replace_all:
            self._clear_problems()
        self.problems.configure(state="normal")
        self.problems.insert("end", text + "\n", (tone,))
        self.problems.configure(state="disabled")
        self.problems.see("end")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > _LOG_LIMIT:
            self.log.delete("1.0", f"{lines - _LOG_LIMIT}.0")
        self.log.configure(state="disabled")
        self.log.see("end")


def main(settings_path: Path = SETTINGS_FILE) -> int:
    _windows_dpi_awareness()
    try:
        root = tk.Tk()
    except tk.TclError as error:
        launcher_log(f"cannot open a window: {error}")
        if sys.stderr is not None:
            sys.stderr.write(f"dune-imperium-launcher: cannot open a window: {error}\n")
        return 1
    _korean_fonts(root)
    launcher_log(
        f"start: Python {sys.version.split()[0]}, Tk {tk.TkVersion}, {sys.executable}"
    )

    def report(
        kind: type[BaseException], error: BaseException, tb: TracebackType | None
    ) -> None:
        launcher_log("".join(traceback.format_exception(kind, error, tb)))
        messagebox.showerror(
            TITLE, f"런처 오류: {error}\n(자세한 내용: {LAUNCHER_LOG})", parent=root
        )

    root.report_callback_exception = report
    window = LauncherWindow(root, settings_path)
    root.geometry(
        window_geometry(
            window.controller.settings.window,
            root.winfo_screenwidth(),
            root.winfo_screenheight(),
        )
    )
    try:
        root.mainloop()
    finally:
        window.controller.shutdown()
    return 0
