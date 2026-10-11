"""How the launcher window looks in each state: plain data, no Tk.

The window asks these functions what to enable and what to say, so the
rules are tested without a display (docs/server-launcher-plan.md 7).
"""

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
