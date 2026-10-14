"""How the launcher window looks in each state: plain data, no Tk.

The window asks these functions what to enable and what to say, so the
rules are tested without a display (docs/server-launcher-plan.md 7).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from dune_imperium.launcher.command import Problem
from dune_imperium.launcher.controller import Phase
from dune_imperium.launcher.settings import Mode, Window

Tone = Literal["plain", "good", "busy", "bad", "warn"]

# The server's --ai-pace values and their words in the window.
AI_PACE_LABELS: Final = {"normal": "보통", "fast": "빠르게", "instant": "즉시"}
_LABEL_SEPARATOR: Final = " — "
DEFAULT_SIZE: Final = (1000, 640)
_MIN_VISIBLE: Final = 80


@dataclass(frozen=True)
class Controls:
    # The settings fields (all of them).
    editable: bool
    # The fields that only a remote game uses.
    remote_fields: bool
    can_start: bool
    can_stop: bool
    links: bool


def controls(phase: Phase, mode: Mode) -> Controls:
    idle = phase is Phase.IDLE
    return Controls(
        editable=idle,
        remote_fields=idle and mode == "remote",
        can_start=idle,
        can_stop=phase in (Phase.CHECKING, Phase.STARTING, Phase.RUNNING),
        links=phase is Phase.RUNNING,
    )


def close_question(playing: int, *, mode: Mode, autosave: bool) -> str:
    """What closing the window asks while the server runs.

    An autosaving server loses only the turn in progress; without autosave
    every unsaved game goes. The save button is the host panel's "지금 저장"
    in a remote game and the top bar's "저장" in a local one.
    """

    games = f"진행 중인 게임이 {playing}개 있습니다. " if playing else ""
    if autosave:
        loss = "진행 중이던 턴은 사라질 수 있습니다."
    else:
        loss = "자동 저장이 꺼져 있어 저장하지 않은 게임은 모두 사라집니다."
    button = "지금 저장" if mode == "remote" else "저장"
    return (
        f"서버를 끄고 런처를 닫을까요?\n\n{games}{loss} "
        f"먼저 게임 화면에서 '{button}'을 누르면 안전합니다."
    )


def status(phase: Phase, *, error: str | None = None) -> tuple[str, Tone]:
    """The status line: a word for the state, never colour alone."""

    if phase is Phase.IDLE:
        if error:
            return f"■ 꺼짐 — {error}", "bad"
        return "■ 꺼짐", "plain"
    if phase is Phase.CHECKING:
        return "… 시작 전 검사 중", "busy"
    if phase is Phase.STARTING:
        return "… 서버를 띄우는 중", "busy"
    if phase is Phase.RUNNING:
        return "● 켜짐", "good"
    return "… 서버를 끄는 중", "busy"


# The server prints English (cli/server.py, uvicorn); the log pane shows the
# lines below in Korean. Python's `\1` is a group of the match. The server's
# own log file keeps what it wrote, and a line with no entry (an access line's
# request, a traceback) stays as it was. Each entry is a whole line, so a
# server that words a line differently is shown as it printed it.
_AFTER_CRASH: Final = "서버가 죽으면: 서버를 다시 띄우고 "
_ADDRESS_UP: Final = (
    " (is that address up on this machine? a Tailscale address only exists "
    "while Tailscale is connected)"
)
_LOG_LINES: Final = tuple(
    (re.compile(pattern), korean)
    for pattern, korean in (
        (
            r"^Remote multiplayer access is on\. "
            r"Host admin link \(keep it private\):$",
            "원격 멀티플레이가 켜져 있습니다. "
            "호스트 관리자 링크 (남에게 보이지 마세요):",
        ),
        (
            r"^Autosave is on: every game keeps one current save in (.+)$",
            r"자동 저장이 켜져 있습니다: 게임마다 현재 저장본 하나를 \1에 둡니다",
        ),
        (
            r"^  \(after a crash: restart, open the admin link, load that save and "
            r"share the new room link\)$",
            f"  ({_AFTER_CRASH}관리자 링크로 들어가 자동 저장을 불러온 뒤, "
            "새 방 링크를 보내세요)",
        ),
        (
            r"^  \(after a crash: restart and load that save\)$",
            f"  ({_AFTER_CRASH}자동 저장을 불러오세요)",
        ),
        (
            r"^Autosave is off: a game lives only as long as this process\.$",
            "자동 저장이 꺼져 있습니다: 게임은 이 서버가 켜져 있는 동안만 남습니다.",
        ),
        (r"^search AI: off \(no file at (.+)\)$", r"탐색 AI: 꺼짐 (\1에 파일이 없음)"),
        (
            r"^search AI: off \(no checkpoint; --search-checkpoint or (.+)\)$",
            r"탐색 AI: 꺼짐 (체크포인트가 없음: 설정에서 파일을 고르거나 \1에 두세요)",
        ),
        (
            r"^search AI: off \(torch not installed: (.+)\)$",
            r"탐색 AI: 꺼짐 (torch가 설치되어 있지 않음: \1)",
        ),
        (
            r"^search AI: off \((.+?) not installed: (.+)\)$",
            r"탐색 AI: 꺼짐 (\1 미설치: \2)",
        ),
        (r"^search AI: (.+)$", r"탐색 AI: \1"),
        (
            r"^INFO:( +)Started server process \[(\d+)\]$",
            r"정보:\1서버 프로세스 시작 [\2]",
        ),
        (
            r"^INFO:( +)Waiting for application startup\.$",
            r"정보:\1서버 앱 시작을 기다리는 중",
        ),
        (r"^INFO:( +)Application startup complete\.$", r"정보:\1서버 앱 시작 완료"),
        (
            r"^INFO:( +)Uvicorn running on (.+) \(Press CTRL\+C to quit\)$",
            r"정보:\1서버가 \2에서 실행 중 (끄려면 CTRL+C)",
        ),
        (r"^INFO:( +)Shutting down$", r"정보:\1서버를 끄는 중"),
        (
            r"^INFO:( +)Waiting for application shutdown\.$",
            r"정보:\1서버 앱 종료를 기다리는 중",
        ),
        (
            r"^INFO:( +)Application shutdown complete\.$",
            r"정보:\1서버 앱 종료 완료",
        ),
        (
            r"^INFO:( +)Finished server process \[(\d+)\]$",
            r"정보:\1서버 프로세스 끝 [\2]",
        ),
        (
            r"^\[launcher\] could not run (.+?): (.*)$",
            r"[launcher] 실행하지 못했습니다 (\1): \2",
        ),
        (
            r"^dune-imperium-server: cannot listen on (\S+): (.*)$",
            r"dune-imperium-server: \1에서 연결을 받을 수 없습니다: \2",
        ),
        (
            r"^dune-imperium-server: cannot resolve --host (\S+): (.*)$",
            r"dune-imperium-server: 주소를 찾을 수 없습니다 (\1): \2",
        ),
        (
            r"^dune-imperium-server: no usable address for --host (\S+)(.*)$",
            r"dune-imperium-server: 쓸 수 있는 주소가 없습니다 (\1)\2",
        ),
        (
            r"^dune-imperium-server: cannot read standard input \((.*)\); "
            r"--exit-when-stdin-closes stops the server$",
            r"dune-imperium-server: 표준 입력을 읽을 수 없어 서버를 끕니다 (\1)",
        ),
        (
            r"^dune-imperium-server: no standard input to watch; "
            r"--exit-when-stdin-closes is ignored$",
            "dune-imperium-server: 감시할 표준 입력이 없어, "
            "입력이 닫혀도 서버를 끄지 않습니다",
        ),
    )
)
# Any other line in uvicorn's format (an access line, a warning) keeps its text
# and gets its level word in Korean.
_LEVEL_WORDS: Final = {
    "INFO": "정보",
    "WARNING": "경고",
    "ERROR": "오류",
    "CRITICAL": "치명",
}
_LEVEL_LINE: Final = re.compile(r"^(INFO|WARNING|ERROR|CRITICAL):( +)(.*)$")
_ADDRESS_UP_KO: Final = (
    " (이 컴퓨터에서 그 주소가 켜져 있나요? Tailscale 주소는 Tailscale이 "
    "연결된 동안에만 있습니다)"
)


def log_line(text: str) -> str:
    """One line of the server's output as the log pane shows it: Korean for
    the lines the server and uvicorn print themselves, any other line as is."""

    for pattern, korean in _LOG_LINES:
        match = pattern.match(text)
        if match:
            return match.expand(korean).replace(_ADDRESS_UP, _ADDRESS_UP_KO)
    level = _LEVEL_LINE.match(text)
    if level:
        return f"{_LEVEL_WORDS[level[1]]}:{level[2]}{level[3]}"
    return text


_PROBLEM_WORDS: Final = {"error": "오류", "warning": "주의", "note": "참고"}
_PROBLEM_TONES: Final[dict[str, Tone]] = {
    "error": "bad",
    "warning": "warn",
    "note": "plain",
}


def problem_lines(problems: Sequence[Problem]) -> list[tuple[str, Tone]]:
    return [
        (f"[{_PROBLEM_WORDS[p.level]}] {p.text}", _PROBLEM_TONES[p.level])
        for p in problems
    ]


@dataclass(frozen=True)
class GameRow:
    game_id: str
    text: str
    finished: bool


def room_link(base: str, game_id: str) -> str:
    """The link the players of one game open (``#game=<id>``)."""

    return f"{base.rstrip('/')}/#game={game_id}"


def game_rows(summaries: Sequence[Mapping[str, object]]) -> list[GameRow]:
    """One line per open game: round, people in it, the start of its ID."""

    rows: list[GameRow] = []
    for summary in summaries:
        game_id = summary.get("game_id")
        if not isinstance(game_id, str):
            continue
        players = summary.get("players")
        humans = online = 0
        if isinstance(players, list):
            for player in players:
                if isinstance(player, Mapping) and player.get("kind") == "human":
                    humans += 1
                    online += player.get("online") is True
        finished = summary.get("finished") is True
        round_number = summary.get("round_number")
        where = "끝남" if finished else f"{round_number}라운드"
        rows.append(
            GameRow(
                game_id,
                f"{where} · 사람 {humans}명(접속 {online}) · {game_id[:8]}",
                finished,
            )
        )
    return rows


def address_choice(label: str, ip: str) -> str:
    return f"{label}{_LABEL_SEPARATOR}{ip}" if label else ip


def address_from_choice(text: str) -> str:
    """The address in a combobox entry: a candidate's label or a typed one."""

    text = text.strip()
    if _LABEL_SEPARATOR in text:
        return text.rsplit(_LABEL_SEPARATOR, 1)[1].strip()
    return text


def window_geometry(
    window: Window | None,
    bounds: tuple[int, int, int, int],
    required: tuple[int, int] = (0, 0),
) -> str:
    """A Tk geometry that puts the window back where it was, on screen.

    ``bounds`` is the desktop (left, top, width, height): on Windows the
    virtual screen of all monitors, so a window kept on a monitor left of
    the main one (negative x) stays there. A window saved off it (a
    monitor since unplugged, another machine) is pulled back so that a
    corner shows. The size is never below what the widgets ``required``
    (fonts grow on a scaled display); with nothing saved the window opens
    centred at its default size.
    """

    left, top, screen_width, screen_height = bounds
    need_width, need_height = required
    if window is not None:
        width, height = window.width, window.height
    else:
        width, height = DEFAULT_SIZE
    width = min(max(width, need_width, 320), screen_width)
    height = min(max(height, need_height, 240), screen_height)
    if window is not None:
        x = min(max(window.x, left), max(left + screen_width - _MIN_VISIBLE, left))
        y = min(max(window.y, top), max(top + screen_height - _MIN_VISIBLE, top))
    else:
        x = left + max((screen_width - width) // 2, 0)
        y = top + max((screen_height - height) // 3, 0)
    return f"{width}x{height}{x:+d}{y:+d}"
