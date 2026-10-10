"""The launcher window itself (needs a display; skipped without one).

One hidden Tk root for the whole session, and a hidden window per test, so
a run does not flash windows or steal focus. Nothing here touches the
clipboard or opens a browser. Set DUNE_IMPERIUM_SKIP_GUI_TESTS=1 to skip.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("tkinter")

import tkinter as tk  # noqa: E402

from dune_imperium.launcher import gui  # noqa: E402
from dune_imperium.launcher.addresses import Candidate, Discovery  # noqa: E402
from dune_imperium.launcher.command import Problem, build_plan  # noqa: E402
from dune_imperium.launcher.controller import (  # noqa: E402
    ChecksDone,
    Controller,
    Emit,
    GamesListed,
    LogLine,
    Phase,
    PhaseChanged,
    ServerStopped,
    Started,
    StartFailed,
)
from dune_imperium.launcher.gui import LauncherWindow  # noqa: E402
from dune_imperium.launcher.keepawake import KeepAwake  # noqa: E402
from dune_imperium.launcher.settings import (  # noqa: E402
    LauncherSettings,
    load,
    save,
)
from dune_imperium.launcher.supervisor import Stopped  # noqa: E402


@pytest.fixture(scope="session")
def tk_root() -> Iterator[tk.Tk]:
    if os.environ.get("DUNE_IMPERIUM_SKIP_GUI_TESTS"):
        pytest.skip("DUNE_IMPERIUM_SKIP_GUI_TESTS is set")
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def _no_real_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never open the machine's browser from a test.

    A started server opens the play page when ``open_browser`` is on, which
    is the default: tests that applied ``Started`` without asking for
    ``opened`` popped Chrome up at http://127.0.0.1:8127/ on every full
    pytest run (2026-10-10).
    """

    monkeypatch.setattr(gui, "_open_in_browser", lambda url: None)


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr(gui, "_open_in_browser", urls.append)
    return urls


class RecordingKeepAwake(KeepAwake):
    def __init__(self) -> None:
        super().__init__(platform="none")
        self.calls: list[tuple[str, int | None]] = []

    def hold(self, server_pid: int) -> str | None:
        self.calls.append(("hold", server_pid))
        return None

    def release(self) -> None:
        self.calls.append(("release", None))


def _window(
    tk_root: tk.Tk,
    tmp_path: Path,
    settings: LauncherSettings | None = None,
    keep_awake: KeepAwake | None = None,
) -> LauncherWindow:
    path = tmp_path / "launcher.json"
    if settings is not None:
        save(settings, path)
    top = tk.Toplevel(tk_root)
    top.withdraw()

    def make(settings_path: Path, emit: Emit) -> Controller:
        return Controller(
            settings_path,
            emit,
            discover_addresses=lambda: Discovery((), None, True),
            check_torch=False,
            spawn=lambda name, work: None,
        )

    return LauncherWindow(
        top, path, make_controller=make, keep_awake=keep_awake or RecordingKeepAwake()
    )


def _enabled(widget: tk.Misc) -> bool:
    return "disabled" not in widget.state()  # type: ignore[attr-defined]


def test_the_form_shows_the_settings_and_reads_them_back(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    settings = LauncherSettings(
        mode="remote",
        host="100.101.102.103",
        port=8123,
        public_url="http://100.101.102.103:8123",
        admin_key_mode="fresh",
        saves_dir="saves",
        autosave=False,
        search_checkpoint="checkpoints/play/other.pt",
        ai_pace="fast",
        assets_dir="/somewhere/assets",
        open_browser=False,
    )
    window = _window(tk_root, tmp_path, settings)
    try:
        read = window.read_form()
        assert (
            read.mode,
            read.host,
            read.port,
            read.public_url,
            read.admin_key_mode,
            read.saves_dir,
            read.autosave,
            read.search_checkpoint,
            read.ai_pace,
            read.assets_dir,
            read.open_browser,
        ) == (
            "remote",
            "100.101.102.103",
            8123,
            "http://100.101.102.103:8123",
            "fresh",
            "saves",
            False,
            "checkpoints/play/other.pt",
            "fast",
            "/somewhere/assets",
            False,
        )
        assert window.ai_pace.get() == "빠르게"
    finally:
        window.root.destroy()


def test_the_remote_fields_follow_the_mode_and_lock_while_running(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    window = _window(tk_root, tmp_path)
    try:
        window.mode.set("local")
        window._refresh()
        assert not _enabled(window.address_box)
        window.mode.set("remote")
        window._refresh()
        assert _enabled(window.address_box) and _enabled(window.start_button)
        assert not _enabled(window.stop_button)
        window.apply(PhaseChanged(Phase.RUNNING))
        assert not _enabled(window.address_box) and not _enabled(window.start_button)
        assert _enabled(window.stop_button)
        assert "켜짐" in window.status_text.get()
    finally:
        window.root.destroy()


def test_a_started_server_shows_its_links_and_opens_the_browser(
    tk_root: tk.Tk, tmp_path: Path, opened: list[str]
) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(open_browser=True))
    try:
        settings = LauncherSettings(mode="remote", host="127.0.0.1", port=8124)
        plan = build_plan(settings, "k" * 32, python="py", environ={})
        window.apply(Started(plan, {"access": "remote"}, None))
        window.apply(PhaseChanged(Phase.RUNNING))
        # Shown with the key masked; opened whole.
        assert window.open_url.get() == "http://127.0.0.1:8124/#admin=…"
        assert window.room_base.get() == "http://127.0.0.1:8124"
        assert opened == [plan.open_url]
        assert _enabled(window.copy_open) and _enabled(window.copy_room)
    finally:
        window.root.destroy()


def test_checks_logs_and_an_unexpected_stop_are_shown(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    window = _window(tk_root, tmp_path)
    try:
        window.apply(ChecksDone((Problem("error", "포트 8000을 다른 프로그램이"),)))
        assert "[오류] 포트 8000" in window.problems.get("1.0", "end")
        window.apply(LogLine("INFO: Started server process"))
        assert "Started server process" in window.log.get("1.0", "end")
        window.apply(
            ServerStopped(
                Stopped("already", 0.1, -9, True), unexpected="서버가 멈췄습니다"
            )
        )
        window.apply(PhaseChanged(Phase.IDLE))
        assert "서버가 멈췄습니다" in window.status_text.get()
        assert window.open_url.get() == ""
    finally:
        window.root.destroy()


def test_the_log_keeps_the_last_lines_only(tk_root: tk.Tk, tmp_path: Path) -> None:
    window = _window(tk_root, tmp_path)
    try:
        for number in range(gui._LOG_LIMIT + 150):
            window.apply(LogLine(f"line {number}"))
        text = window.log.get("1.0", "end-1c").splitlines()
        assert len(text) <= gui._LOG_LIMIT
        assert text[-1] == f"line {gui._LOG_LIMIT + 149}"
    finally:
        window.root.destroy()


def test_found_addresses_fill_the_list_and_pick_the_best(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    from dune_imperium.launcher.controller import AddressesFound

    window = _window(tk_root, tmp_path, LauncherSettings(mode="remote", host=""))
    try:
        found = Discovery(
            (
                Candidate("100.87.236.12", "tailscale", "tailscale CLI"),
                Candidate("192.168.0.64", "lan", "host name"),
                Candidate("127.0.0.1", "loopback", "loopback"),
            ),
            None,
            True,
        )
        window.apply(AddressesFound(found))
        assert window.address.get() == "Tailscale — 100.87.236.12"
        assert window.read_form().host == "100.87.236.12"
        values = window.address_box.cget("values")
        assert "같은 네트워크(LAN) — 192.168.0.64" in values
        assert "Tailscale CLI 없음" in window.address_hint.get()
    finally:
        window.root.destroy()


def test_closing_an_idle_window_keeps_the_form(tk_root: tk.Tk, tmp_path: Path) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(port=8125))
    window.port.set("8126")
    window.close()
    assert load(tmp_path / "launcher.json").settings.port == 8126


def test_the_machine_stays_awake_only_while_the_server_runs(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    awake = RecordingKeepAwake()
    window = _window(tk_root, tmp_path, LauncherSettings(keep_awake=True), awake)
    try:
        plan = build_plan(LauncherSettings(port=8127), None, python="py", environ={})
        window.apply(Started(plan, {"access": "open"}, None, 4242))
        assert awake.calls == [("hold", 4242)]
        window.apply(ServerStopped(Stopped("stdin", 0.3, 0, True)))
        assert awake.calls[-1] == ("release", None)
    finally:
        window.root.destroy()


def test_keep_awake_can_be_switched_off(tk_root: tk.Tk, tmp_path: Path) -> None:
    awake = RecordingKeepAwake()
    window = _window(tk_root, tmp_path, LauncherSettings(keep_awake=False), awake)
    try:
        assert window.read_form().keep_awake is False
        plan = build_plan(LauncherSettings(port=8128), None, python="py", environ={})
        window.apply(Started(plan, {"access": "open"}, None, 4242))
        assert ("hold", 4242) not in awake.calls
    finally:
        window.root.destroy()


def _running(window: LauncherWindow, port: int = 8129) -> None:
    settings = LauncherSettings(mode="remote", host="127.0.0.1", port=port)
    plan = build_plan(settings, "k" * 32, python="py", environ={})
    window.apply(Started(plan, {"access": "remote"}, None, None))
    window.apply(PhaseChanged(Phase.RUNNING))


def test_the_open_games_give_room_links(tk_root: tk.Tk, tmp_path: Path) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(open_browser=False))
    try:
        _running(window)
        assert not _enabled(window.copy_game)
        window.apply(
            GamesListed(
                (
                    {"game_id": "aaaa1111", "round_number": 2, "players": []},
                    {"game_id": "bbbb2222", "finished": True, "players": []},
                )
            )
        )
        assert window.games_list.size() == 2
        assert _enabled(window.copy_game)
        assert window.selected_room_link() == "http://127.0.0.1:8129/#game=aaaa1111"
        window.games_list.selection_clear(0, "end")
        window.games_list.selection_set(1)
        # A refresh keeps the host's pick.
        window.apply(
            GamesListed(
                (
                    {"game_id": "aaaa1111", "round_number": 3, "players": []},
                    {"game_id": "bbbb2222", "finished": True, "players": []},
                )
            )
        )
        assert window.selected_game() == "bbbb2222"
    finally:
        window.root.destroy()


def test_closing_a_running_server_asks_with_the_games_in_play(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def no(title: str, message: str, **options: object) -> bool:
        asked.append(message)
        return False

    monkeypatch.setattr("tkinter.messagebox.askyesno", no)
    window = _window(tk_root, tmp_path, LauncherSettings(open_browser=False))
    try:
        _running(window)
        window.apply(
            GamesListed(({"game_id": "aaaa1111", "round_number": 2, "players": []},))
        )
        window.close()
        assert "진행 중인 게임이 1개" in asked[0] and "지금 저장" in asked[0]
        assert window.root.winfo_exists()
    finally:
        window.root.destroy()


def test_a_failed_start_offers_the_last_settings_that_worked(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(port=8130))
    try:
        good = LauncherSettings(mode="remote", host="192.168.0.64", port=8000)
        # The order the controller really sends.
        window.apply(PhaseChanged(Phase.CHECKING))
        window.apply(PhaseChanged(Phase.STARTING))
        window.apply(StartFailed("포트가 이미 쓰이고 있습니다", (), good))
        assert window.retry_button.winfo_manager() == ""
        window.apply(PhaseChanged(Phase.IDLE))
        assert window.retry_button.winfo_manager() == "grid"
        assert "192.168.0.64:8000" in str(window.retry_button.cget("text"))
        window.retry_button.invoke()
        assert window.read_form().port == 8000
        assert window.controller.phase is Phase.CHECKING
        # Gone once a new start is under way, and not back after it.
        window.apply(PhaseChanged(Phase.CHECKING))
        window.apply(PhaseChanged(Phase.IDLE))
        assert window.retry_button.winfo_manager() == ""
    finally:
        window.root.destroy()


def test_no_retry_is_offered_for_the_same_settings(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(port=8131))
    try:
        window.apply(StartFailed("실패", (), LauncherSettings(port=8131)))
        assert window.retry_button.winfo_manager() == ""
    finally:
        window.root.destroy()


def test_no_retry_for_a_local_start_on_the_same_port(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    # A local start listens on 127.0.0.1 whatever remote address is kept.
    window = _window(tk_root, tmp_path, LauncherSettings(port=8132, host="10.0.0.9"))
    try:
        window.apply(PhaseChanged(Phase.STARTING))
        window.apply(
            StartFailed("실패", (), LauncherSettings(port=8132, host="192.168.0.64"))
        )
        window.apply(PhaseChanged(Phase.IDLE))
        assert window.retry_button.winfo_manager() == ""
    finally:
        window.root.destroy()


def test_the_admin_link_is_shown_masked_but_copied_and_opened_whole(
    tk_root: tk.Tk,
    tmp_path: Path,
    opened: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(tk_root, tmp_path, LauncherSettings(open_browser=False))
    copied: list[str] = []
    monkeypatch.setattr(window, "copy", copied.append)
    try:
        key = "k" * 32
        plan = build_plan(
            LauncherSettings(mode="remote", host="127.0.0.1", port=8133),
            key,
            python="py",
            environ={},
        )
        window.apply(Started(plan, {"access": "remote"}, None, None))
        window.apply(PhaseChanged(Phase.RUNNING))
        assert window.open_url.get() == "http://127.0.0.1:8133/#admin=…"
        assert key not in window.open_url.get()
        window.copy_open.invoke()
        window.open_button.invoke()
        assert copied == [plan.open_url] and opened == [plan.open_url]
    finally:
        window.root.destroy()


def test_cmd_q_asks_like_closing_the_window(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if tk_root.tk.call("tk", "windowingsystem") != "aqua":
        pytest.skip("macOS only")
    asked: list[str] = []

    def no(title: str, message: str, **options: object) -> bool:
        asked.append(message)
        return False

    monkeypatch.setattr("tkinter.messagebox.askyesno", no)
    window = _window(tk_root, tmp_path, LauncherSettings(open_browser=False))
    try:
        _running(window)
        window.root.tk.call("::tk::mac::Quit")
        assert asked and "서버를 끄고" in asked[0]
        assert window.root.winfo_exists()
    finally:
        window.root.destroy()


def test_the_shortcut_is_made_off_the_window_thread(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    made_on: list[str] = []
    revealed: list[Path] = []

    def make() -> Path:
        made_on.append(threading.current_thread().name)
        return tmp_path / "Dune Imperium Server.app"

    monkeypatch.setattr(gui, "make_shortcut", make)
    monkeypatch.setattr(gui, "reveal", revealed.append)
    window = _window(tk_root, tmp_path)
    try:
        window._make_shortcut()
        assert not _enabled(window.shortcut_button)
        event = window._events.get(timeout=10)
        assert isinstance(event, gui._ShortcutDone)
        window._shortcut_done(event)
        assert made_on == ["launcher-shortcut"]
        assert revealed == [tmp_path]
        assert _enabled(window.shortcut_button)
        assert "바로가기를 만들었습니다" in window.problems.get("1.0", "end")
    finally:
        window.root.destroy()


def test_a_free_port_search_from_a_bad_number_starts_at_8000(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[int] = []

    def find(host: str, start: int = 8000, count: int = 100) -> int:
        starts.append(start)
        return 8001

    monkeypatch.setattr(gui, "find_free_port", find)
    window = _window(tk_root, tmp_path)
    try:
        window.port.set("0")
        window._free_port()
        assert starts == [8000] and window.port.get() == "8001"
    finally:
        window.root.destroy()
