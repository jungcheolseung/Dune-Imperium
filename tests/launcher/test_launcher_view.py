"""What the launcher window enables and says in each state (no display)."""

import ast
import re
from pathlib import Path

import pytest

from dune_imperium.launcher.command import Problem
from dune_imperium.launcher.controller import Phase
from dune_imperium.launcher.settings import Window
from dune_imperium.launcher.view import (
    address_choice,
    address_from_choice,
    close_question,
    controls,
    log_line,
    problem_lines,
    status,
    window_geometry,
)


def test_only_an_idle_launcher_takes_new_settings() -> None:
    idle = controls(Phase.IDLE, "remote")
    assert idle.editable and idle.remote_fields and idle.can_start
    assert not idle.can_stop and not idle.links
    for phase in (Phase.CHECKING, Phase.STARTING, Phase.RUNNING, Phase.STOPPING):
        busy = controls(phase, "remote")
        assert not busy.editable and not busy.remote_fields and not busy.can_start


def test_the_remote_fields_follow_the_mode() -> None:
    assert not controls(Phase.IDLE, "local").remote_fields
    assert controls(Phase.IDLE, "remote").remote_fields


def test_a_start_can_be_called_off_until_the_server_is_stopping() -> None:
    assert controls(Phase.CHECKING, "local").can_stop
    assert controls(Phase.STARTING, "local").can_stop
    assert controls(Phase.RUNNING, "local").can_stop
    assert not controls(Phase.STOPPING, "local").can_stop


def test_the_links_show_only_while_the_server_runs() -> None:
    assert controls(Phase.RUNNING, "local").links
    assert not controls(Phase.STARTING, "local").links


@pytest.mark.parametrize("phase", list(Phase))
def test_every_state_is_said_in_words_not_colour_alone(phase: Phase) -> None:
    text, _tone = status(phase)
    assert any(word in text for word in ("꺼짐", "켜짐", "중"))


def test_a_failed_start_stays_on_the_status_line() -> None:
    text, tone = status(Phase.IDLE, error="포트가 이미 쓰이고 있습니다")
    assert "포트가 이미" in text and tone == "bad"


def test_problems_are_labelled_by_level() -> None:
    lines = problem_lines(
        [Problem("error", "a"), Problem("warning", "b"), Problem("note", "c")]
    )
    assert lines == [("[오류] a", "bad"), ("[주의] b", "warn"), ("[참고] c", "plain")]


@pytest.mark.parametrize(
    ("text", "address"),
    [
        ("Tailscale — 100.87.236.12", "100.87.236.12"),
        ("같은 네트워크(LAN) — 192.168.0.64", "192.168.0.64"),
        ("  192.168.0.9 ", "192.168.0.9"),
        ("", ""),
    ],
)
def test_the_address_is_read_from_a_label_or_as_typed(text: str, address: str) -> None:
    assert address_from_choice(text) == address


def test_a_label_and_its_address_round_trip() -> None:
    assert address_from_choice(address_choice("LAN", "10.0.0.2")) == "10.0.0.2"


SCREEN = (0, 0, 1920, 1080)


def test_a_saved_window_comes_back_where_it_was() -> None:
    assert window_geometry(Window(100, 50, 700, 600), SCREEN) == "700x600+100+50"


def test_a_window_off_the_screen_is_pulled_back() -> None:
    # Saved on a wider screen, or on another machine.
    geometry = window_geometry(Window(3000, 2000, 900, 900), (0, 0, 1280, 800))
    size, x, y = geometry.split("+")
    assert size == "900x800" and int(x) <= 1280 - 80 and int(y) <= 800 - 80


def test_without_a_saved_window_it_opens_centred() -> None:
    assert window_geometry(None, SCREEN) == "1000x640+460+146"


def test_a_window_on_a_monitor_left_of_the_main_one_stays_there() -> None:
    # Windows' virtual screen starts at -1920 with a monitor on the left.
    desktop = (-1920, 0, 3840, 1080)
    assert window_geometry(Window(-1700, 100, 1000, 640), desktop) == (
        "1000x640-1700+100"
    )


def test_the_window_is_never_smaller_than_its_widgets_need() -> None:
    # A 150 % Windows display: the fonts grow, the saved size does not.
    geometry = window_geometry(Window(10, 10, 1000, 640), SCREEN, (1180, 720))
    assert geometry.startswith("1180x720")
    assert window_geometry(None, SCREEN, (1180, 720)).startswith("1180x720")


def test_each_open_game_gets_a_line_and_a_room_link() -> None:
    from dune_imperium.launcher.view import game_rows, room_link

    rows = game_rows(
        [
            {
                "game_id": "abcdef1234567890",
                "round_number": 3,
                "finished": False,
                "players": [
                    {"seat": 0, "kind": "human", "online": True},
                    {"seat": 1, "kind": "human", "online": False},
                    {"seat": 2, "kind": "app_ai", "online": False},
                ],
            },
            {"game_id": "ffff0000ffff0000", "finished": True, "players": []},
            {"no": "id"},
        ]
    )
    assert [row.text for row in rows] == [
        "3라운드 · 사람 2명(접속 1) · abcdef12",
        "끝남 · 사람 0명(접속 0) · ffff0000",
    ]
    assert rows[1].finished and not rows[0].finished
    assert (
        room_link("http://100.1.2.3:8000/", "abc")
        == "http://100.1.2.3:8000/#game=abc"
    )


def test_closing_says_what_is_lost_and_which_button_saves() -> None:
    local = close_question(2, mode="local", autosave=True)
    assert "진행 중인 게임이 2개" in local and "턴은 사라질 수" in local
    assert "'저장'" in local and "지금 저장" not in local
    remote = close_question(0, mode="remote", autosave=True)
    assert "진행 중인 게임" not in remote and "'지금 저장'" in remote
    # Without autosave nothing survives the server but what was saved by hand.
    unsaved = close_question(1, mode="local", autosave=False)
    assert "자동 저장이 꺼져" in unsaved and "모두 사라집니다" in unsaved


# --- the server log pane in Korean (user decision 2026-10-14) ----------------

_HANGUL = re.compile(r"[가-힣]")


def test_the_servers_own_lines_read_in_korean() -> None:
    # What `dune-imperium-server --remote` prints before and while uvicorn runs.
    assert log_line(
        "Remote multiplayer access is on. Host admin link (keep it private):"
    ) == "원격 멀티플레이가 켜져 있습니다. 호스트 관리자 링크 (남에게 보이지 마세요):"
    assert log_line(
        "Autosave is on: every game keeps one current save in /games/saves"
    ) == "자동 저장이 켜져 있습니다: 게임마다 현재 저장본 하나를 /games/saves에 둡니다"
    assert log_line("Autosave is off: a game lives only as long as this process.") == (
        "자동 저장이 꺼져 있습니다: 게임은 이 서버가 켜져 있는 동안만 남습니다."
    )
    assert log_line(
        "INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)"
    ) == "정보:     서버가 http://127.0.0.1:8000에서 실행 중 (끄려면 CTRL+C)"
    assert log_line("INFO:     Started server process [9095]") == (
        "정보:     서버 프로세스 시작 [9095]"
    )
    assert log_line("INFO:     Application startup complete.") == (
        "정보:     서버 앱 시작 완료"
    )
    assert log_line("INFO:     Shutting down") == "정보:     서버를 끄는 중"
    assert log_line("INFO:     Finished server process [9095]") == (
        "정보:     서버 프로세스 끝 [9095]"
    )


def test_a_request_line_keeps_its_request_and_names_its_level_in_korean() -> None:
    line = 'INFO:     127.0.0.1:57091 - "GET /whoami HTTP/1.1" 200 OK'
    assert log_line(line) == '정보:     127.0.0.1:57091 - "GET /whoami HTTP/1.1" 200 OK'
    assert log_line("WARNING:  Invalid HTTP request received.") == (
        "경고:  Invalid HTTP request received."
    )
    assert log_line("ERROR:    Exception in ASGI application") == (
        "오류:    Exception in ASGI application"
    )


def test_a_line_with_no_entry_stays_as_the_server_printed_it() -> None:
    for line in (
        "  http://127.0.0.1:8000/#admin=***",
        "Traceback (most recent call last):",
        '  File "app.py", line 3, in <module>',
        "ValueError: something new",
        "[launcher] 설정을 저장하지 못했습니다: disk full",
        "",
    ):
        assert log_line(line) == line


def test_the_admin_link_is_never_read_into_a_translation() -> None:
    # The supervisor masks the key before the line reaches the pane; nothing
    # here may bring it back or move it.
    assert log_line("  http://127.0.0.1:8000/#admin=***") == (
        "  http://127.0.0.1:8000/#admin=***"
    )


def _search_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """Every startup line `resolve_search_checkpoint` can print, as the server
    itself words it (not retyped here)."""

    from argparse import Namespace

    from dune_imperium.cli import server as server_cli

    def line(named: str | None = None) -> str:
        arguments = Namespace(search_checkpoint=named)
        return server_cli.resolve_search_checkpoint(arguments, {})[1]

    network = tmp_path / "search.pt"
    network.write_bytes(b"x")
    missing = tmp_path / "missing.pt"
    lines = {"no file": line(str(missing))}
    monkeypatch.setattr(server_cli, "DEFAULT_SEARCH_CHECKPOINT", missing)
    lines["no checkpoint"] = line()
    monkeypatch.setattr(server_cli, "DEFAULT_SEARCH_CHECKPOINT", network)
    lines["on"] = line()
    monkeypatch.setattr(
        server_cli, "find_spec", lambda name: None if name == "torch" else object()
    )
    lines["no torch"] = line()
    monkeypatch.setattr(
        server_cli,
        "find_spec",
        lambda name: None if name in ("numpy", "pettingzoo") else object(),
    )
    lines["no rl"] = line()
    return lines


def test_every_search_ai_startup_line_reads_in_korean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = _search_lines(tmp_path, monkeypatch)
    assert len(lines) == 5
    for name, line in lines.items():
        korean = log_line(line)
        assert korean.startswith("탐색 AI: "), (name, line, korean)
        assert "search AI" not in korean, (name, korean)
    assert "꺼짐" in log_line(lines["no file"])
    assert log_line(lines["no torch"]) == (
        "탐색 AI: 꺼짐 (torch가 설치되어 있지 않음: uv sync --extra train)"
    )
    assert log_line(lines["no rl"]) == (
        "탐색 AI: 꺼짐 (numpy, pettingzoo 미설치: uv sync --extra rl --extra train)"
    )
    assert "꺼짐" not in log_line(lines["on"])


def test_the_bind_problems_the_server_prints_read_in_korean() -> None:
    import socket

    from dune_imperium.cli.server import bind_problem

    problems = []
    problems.append(bind_problem("no-such-host.invalid", 8000))
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        problems.append(bind_problem("127.0.0.1", taken.getsockname()[1]))
    # An address this machine does not have: the Tailscale hint is appended.
    problems.append(bind_problem("203.0.113.9", 8000))
    seen = [problem for problem in problems if problem]
    assert len(seen) == 3, problems
    for problem in seen:
        korean = log_line(f"dune-imperium-server: {problem}")
        assert _HANGUL.search(korean), problem
        assert "cannot" not in korean and "usable" not in korean, korean
        assert "Tailscale address only exists" not in korean, korean


def test_the_stdin_watch_lines_read_in_korean() -> None:
    assert log_line(
        "dune-imperium-server: cannot read standard input ([Errno 9] Bad file "
        "descriptor); --exit-when-stdin-closes stops the server"
    ) == (
        "dune-imperium-server: 표준 입력을 읽을 수 없어 서버를 끕니다 "
        "([Errno 9] Bad file descriptor)"
    )
    assert _HANGUL.search(
        log_line(
            "dune-imperium-server: no standard input to watch; "
            "--exit-when-stdin-closes is ignored"
        )
    )


def test_every_line_the_server_prints_has_a_korean_form() -> None:
    """The `print(...)` literals of cli/server.py, f-string holes read as 3."""

    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "dune_imperium"
        / "cli"
        / "server.py"
    )
    lines = []
    for node in ast.walk(ast.parse(source.read_text())):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
            and node.args
        ):
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            lines.append(first.value)
        elif isinstance(first, ast.JoinedStr):
            lines.append(
                "".join(
                    str(piece.value) if isinstance(piece, ast.Constant) else "3"
                    for piece in first.values
                )
            )
    # The admin link itself is a URL, not a sentence, and "dune-imperium-server:
    # {problem}" wraps a bind problem (its own test); both stay as they are.
    wrappers = ("3", "dune-imperium-server: 3")
    lines = [line for line in lines if line.strip() not in wrappers]
    assert len(lines) >= 6, lines
    for line in lines:
        korean = log_line(line)
        assert korean != line and _HANGUL.search(korean), line
