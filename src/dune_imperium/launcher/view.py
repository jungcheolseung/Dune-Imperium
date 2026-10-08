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
    window: Window | None, screen_width: int, screen_height: int
) -> str:
    """A Tk geometry that puts the window back where it was, on screen.

    A window saved on a larger screen (or another machine) is pulled back
    so that at least a corner of it shows; with nothing saved the window
    opens centred at its default size.
    """

    width, height = DEFAULT_SIZE
    if window is not None:
        width = max(320, min(window.width, screen_width))
        height = max(240, min(window.height, screen_height))
        x = min(max(window.x, 0), max(screen_width - _MIN_VISIBLE, 0))
        y = min(max(window.y, 0), max(screen_height - _MIN_VISIBLE, 0))
    else:
        width = min(width, screen_width)
        height = min(height, screen_height)
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 3, 0)
    return f"{width}x{height}+{x}+{y}"
