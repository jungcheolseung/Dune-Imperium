"""Each seat's Victory Point changes, step by step: the seat panel's VP list.

Victory Points change at about two dozen places in the engine (an Influence
track reaching 2, an Alliance gained, passed on or lost, a Conflict reward,
a Battle icon match, Endgame cards, Intrigue cards, the research and
Tleilaxu tracks, Tech, ...), and most of them emit no Victory Point event:
reaching 2 Influence logs ``influence_gained`` alone, and an Alliance passing
from one seat to another logs ``alliance_transferred`` while one seat loses
a point and the other gains one. So the ledger does not read events. It walks
the live steps of the game from the opening state, as an undo or a review
rebuilds a state (``sessions._state_after``), and compares every seat's
``victory_points`` before and after each step.

A row names the step by its index in the session log, the index every
client already holds for the log entry (``_log_entry_json``), so a client
names the cause from its own, already redacted, log entry and can scroll to
it. Everything else in a row is public: the round, the seat and how its
Victory Points moved, which the board's track shows every seat. Steps taken
back are not live and never appear; chance steps are, and count like any
other step (the pause before a Conflict reward carries the reward).

The ledger is kept per session and extended as the game goes on
(``extend_ledger``): it remembers how many live steps it walked and the log
index of the last one. The log only ever grows, and a step logged after an
undo has a larger index than every step before it, so while the live step at
that position still has that index, every step the ledger walked is still
live and in the same order.

Every step also splits each seat's change into its sources, the score
window's composition (user request 2026-11-08): a ``VpPart`` names the
kind of source and, where there is one, what it was (a Faction, a card, a
Conflict, a Tech tile, a battle icon). The split reads only what every
seat sees: the Influence tracks and Alliance tokens on the board, and the
step's public events. Points change only where the board shows it or a
public event says so: Influence reaching 2 (and dropping back below it)
and an Alliance gained, passed on or lost are the board's own (no event
carries those points); everything else is a ``battle_icons_matched`` or
``endgame_wild_matched`` event (one point each), a Reserve card acquired
with its acquisition points (The Spice Must Flow), or an event with a
``victory_points`` payload. A remainder no source explains would go to
``other``; tests/server/test_vp_ledger.py shows none in games of every
expansion. A step can move the total by 0 and still have parts (For
Humanity: a card's point for an Influence point that drops a Faction below
2), so parts are kept apart from the rows of nonzero changes.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Final

from dune_imperium.config import RulesetConfig
from dune_imperium.content.core.icons import BattleIcon, Faction
from dune_imperium.content.registry.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.rulesets import content_for
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.influence import influence_amount
from dune_imperium.server.persistence import JsonObject, JsonValue

# The kinds of source a seat's points come from, in the order the score
# window lists them. ``start`` is the points every seat opens with
# (``starting_victory_points``: 1, or 0 with Go to 11).
PART_KINDS: Final = (
    "start",
    "influence",
    "alliance",
    "spice_must_flow",
    "conflict",
    "battle_icons",
    "intrigue",
    "card",
    "tleilaxu",
    "tech",
    "other",
)

# The log index of the opening state's parts: before every step.
OPENING_INDEX: Final = -1

# The Influence a Faction must reach to score its point [Main p. 7].
_INFLUENCE_POINT_AT: Final = 2

# Event kinds whose ``victory_points`` name a card's own effect: an Agent
# card trashed for points (Ghola, Scientific Breakthrough), a Reveal choice
# (Ixian Engineer, For Humanity) and a contract count's trash (Delivery
# Agreement, Priority Contracts).
_CARD_VP_KINDS: Final = frozenset(
    {
        "agent_card_trashed_for_vp",
        "contract_reveal_card_trashed_for_vp",
        "reveal_victory_point_gained",
    }
)
# Event kinds whose ``victory_points`` are a Conflict reward.
_CONFLICT_VP_KINDS: Final = frozenset({"combat_reward_icon_resolved", "spies_recalled"})
# ``game_finished`` carries the winner's total, not a gain.
_NOT_A_GAIN_KINDS: Final = frozenset({"game_finished"})
# An engine card instance ("imperium:opulence:0", "tleilaxu:ghola:1",
# "intrigue:crysknife:0"): the catalog id is the middle part.
_INSTANCE: Final = re.compile(r"^(?:imperium|reserve|tleilaxu|intrigue):(.+):\d+$")


@dataclass(frozen=True, slots=True)
class VpChange:
    """One seat's Victory Points moved by one live step."""

    # The step's index in the session log (``LoggedStep`` entries and undo
    # markers alike are counted), as a client's log entries carry it.
    index: int
    # The round the step was taken in: the round before the step, so a step
    # that ends a round counts its points to the round it ended.
    round: int
    seat: int
    delta: int
    # The seat's Victory Points after the step.
    total: int


@dataclass(frozen=True, slots=True)
class VpPart:
    """Part of one seat's change at one step, by its source.

    ``item`` names the source as ``"<catalog section>:<id>"`` (``faction``,
    ``cards``, ``intrigue``, ``conflicts``, ``tech``, ``battle_icon``), or
    is ``None`` where the kind is the whole name (the Tleilaxu track).
    """

    # The step's log index, or ``OPENING_INDEX`` for the opening points.
    index: int
    seat: int
    kind: str
    item: str | None
    points: int


@dataclass(frozen=True, slots=True)
class VpLedger:
    """The ledger of a game's first ``steps`` live steps."""

    steps: int
    # The log index of the last live step walked; -1 before any.
    last_index: int
    # The state after those steps, where the walk goes on from.
    state: GameState
    # Every seat's Victory Points in the opening state.
    start: tuple[int, ...]
    changes: tuple[VpChange, ...]
    # Every change split by source, the opening points first.
    parts: tuple[VpPart, ...]

    def extends(self, live: Sequence[tuple[int, ReplayStep]]) -> bool:
        """Whether every step walked is still the same live step of ``live``.

        ``live`` is the game's live steps in order, each with its log index.
        """

        if self.steps > len(live):
            return False
        return self.steps == 0 or live[self.steps - 1][0] == self.last_index


def start_ledger(state: GameState) -> VpLedger:
    """The empty ledger of a game whose opening state is ``state``."""

    return VpLedger(
        steps=0,
        last_index=-1,
        state=state,
        start=tuple(player.victory_points for player in state.players),
        changes=(),
        parts=opening_parts(state),
    )


def opening_parts(state: GameState) -> tuple[VpPart, ...]:
    """Every seat's opening points: Influence and Alliances it opens with
    (none in any setup today) and the rest as its starting points."""

    parts: list[VpPart] = []
    for seat, player in enumerate(state.players):
        board = [
            *(
                VpPart(OPENING_INDEX, seat, "influence", f"faction:{faction.value}", 1)
                for faction in Faction
                if influence_amount(player.influence, faction) >= _INFLUENCE_POINT_AT
            ),
            *(
                VpPart(OPENING_INDEX, seat, "alliance", f"faction:{faction_id}", 1)
                for faction_id in player.alliance_faction_ids
            ),
        ]
        rest = player.victory_points - len(board)
        if rest:
            parts.append(VpPart(OPENING_INDEX, seat, "start", None, rest))
        parts.extend(board)
    return tuple(parts)


def step_parts(
    before: GameState,
    after: GameState,
    events: Sequence[GameEvent],
    index: int,
) -> tuple[VpPart, ...]:
    """Every seat's change at one step, split by source (``VpPart``).

    The parts of a seat add up to its change; a remainder no source names
    is an ``other`` part.
    """

    conflict = _round_conflict(before, after)
    config = before.config
    public = tuple(event for event in events if event.visible_to is None)
    parts: list[VpPart] = []
    for seat, (was, now) in enumerate(zip(before.players, after.players, strict=True)):
        found = [
            *_board_parts(was, now),
            *(
                part
                for event in public
                if dict(event.payload).get("player") == seat
                for part in _event_parts(event, conflict, config)
            ),
        ]
        rest = now.victory_points - was.victory_points - sum(p for _, _, p in found)
        if rest:
            found.append(("other", None, rest))
        parts.extend(
            VpPart(index, seat, kind, item, points) for kind, item, points in found
        )
    return tuple(parts)


_Found = tuple[str, str | None, int]


def _board_parts(was: PlayerState, now: PlayerState) -> list[_Found]:
    """The points the board itself shows moving: a Faction's Influence
    crossing 2 either way, and an Alliance token gained or lost."""

    found: list[_Found] = []
    for faction in Faction:
        crossed = int(
            influence_amount(now.influence, faction) >= _INFLUENCE_POINT_AT
        ) - int(influence_amount(was.influence, faction) >= _INFLUENCE_POINT_AT)
        if crossed:
            found.append(("influence", f"faction:{faction.value}", crossed))
    held, holds = set(was.alliance_faction_ids), set(now.alliance_faction_ids)
    found.extend(
        ("alliance", f"faction:{faction_id}", 1)
        for faction_id in now.alliance_faction_ids
        if faction_id not in held
    )
    found.extend(
        ("alliance", f"faction:{faction_id}", -1)
        for faction_id in was.alliance_faction_ids
        if faction_id not in holds
    )
    return found


def _event_parts(
    event: GameEvent, conflict: str | None, config: RulesetConfig
) -> list[_Found]:
    """The points one public event names for its player."""

    payload = dict(event.payload)
    if event.kind == "battle_icons_matched":
        return [("battle_icons", _match_item(event, config), 1)]
    if event.kind == "endgame_wild_matched":
        return [("battle_icons", f"battle_icon:{BattleIcon.WILD.value}", 1)]
    if event.kind == "card_acquired":
        stack = RESERVE_STACKS_BY_ID.get(str(payload.get("card_id")))
        if stack is None or not stack.acquisition_vp:
            return []
        return [("spice_must_flow", None, stack.acquisition_vp)]
    points = payload.get("victory_points")
    if not isinstance(points, int) or event.kind in _NOT_A_GAIN_KINDS:
        return []
    if event.kind == "tleilaxu_advanced":
        return [("tleilaxu", None, points)]
    if event.kind == "tech_acquire_effect_resolved":
        return [("tech", f"tech:{payload['tech_id']}", points)]
    if event.kind in _CARD_VP_KINDS:
        return [("card", _card_item(str(payload["card_id"])), points)]
    if event.kind in _CONFLICT_VP_KINDS:
        return [("conflict", _conflict_item(conflict), points)]
    if event.kind == "resources_gained":
        source = str(payload.get("source", event.event_id))
        kind, item = _source_part(source, conflict)
        return [(kind, item, points)]
    return [("other", None, points)]


def _source_part(source: str, conflict: str | None) -> tuple[str, str | None]:
    """A gain's kind and item from the source its line names.

    "round:3:player:1:intrigue:intrigue:crysknife:0" is an Intrigue card,
    "…:agent_card:imperium:corrinth_city:0" and "…:reveal_card:imperium:
    opulence:0:solari_vp" an Imperium card's box, "…:tech:spy_satellites:
    trash" and "…:endgame_tech:memocorders" a Tech tile, and
    "round:5:combat_reward:…" the round's Conflict, except Detonation
    Devices' dreadnought, which is the tile's ([Detonation Devices tile]).
    """

    parts = source.split(":")
    for at, segment in enumerate(parts[:-1]):
        if segment == "intrigue" and at + 2 < len(parts):
            return "intrigue", f"intrigue:{parts[at + 2]}"
        if segment in ("agent_card", "reveal_card") and at + 2 < len(parts):
            return "card", f"cards:{parts[at + 2]}"
        if segment in ("tech", "endgame_tech"):
            return "tech", f"tech:{parts[at + 1]}"
        if segment == "combat_reward":
            if parts[at + 1] == "dreadnought_detonation":
                return "tech", "tech:detonation_devices"
            return "conflict", _conflict_item(conflict)
    return "other", None


def _card_item(card_id: str) -> str:
    match = _INSTANCE.match(card_id)
    return f"cards:{match.group(1) if match else card_id}"


def _conflict_item(conflict: str | None) -> str | None:
    return None if conflict is None else f"conflicts:{conflict}"


def _round_conflict(before: GameState, after: GameState) -> str | None:
    """The Conflict being resolved: the top card in play before the step,
    or, for a step that turns one over, after it.

    Earlier cards can stay in play beneath it: on the original board
    "Conflict 카드는 공개한 자리에 남고 다음 라운드의 카드가 그 위에
    쌓인다 [DI p. 8]" (docs/rules/imperium-base.md), so the engine
    resolves rewards on ``current_conflict_ids[-1]`` (rules/combat.py), and
    so does this.
    """

    current = before.current_conflict_ids or after.current_conflict_ids
    return current[-1] if current else None


def _match_item(event: GameEvent, config: RulesetConfig) -> str:
    """A battle icon match's item: the icon the pair shares, or the
    Ornithopter Fleet tile whose owner's icons are all Ornithopters
    [Bloodlines p. 12] (``ornithopter.match_all_battle_icons``)."""

    if "ornithopter_match" in event.event_id:
        return "tech:ornithopter_fleet"
    payload = dict(event.payload)
    icons = [
        _battle_icon(str(payload[key]), config)
        for key in ("first_card_id", "second_card_id")
    ]
    printed = [icon for icon in icons if icon not in (None, BattleIcon.WILD)]
    icon = printed[0] if printed else BattleIcon.WILD
    return f"battle_icon:{icon.value}"


def _battle_icon(card_id: str, config: RulesetConfig) -> BattleIcon | None:
    objective = _objective_icons(config).get(card_id)
    if objective is not None:
        return objective
    conflict = CONFLICTS_BY_ID.get(card_id)
    return None if conflict is None else conflict.battle_icon


@cache
def _objective_icons(config: RulesetConfig) -> dict[str, BattleIcon]:
    """The battle icon of each Objective the configuration's game deals."""

    return {
        objective.objective_id: objective.battle_icon
        for objective in content_for(config).objectives
    }


def step_changes(
    before: GameState, after: GameState, index: int
) -> tuple[VpChange, ...]:
    """The Victory Point changes of one step, seat by seat (zero ones left out)."""

    pairs = zip(before.players, after.players, strict=True)
    return tuple(
        VpChange(
            index=index,
            round=before.round_number,
            seat=seat,
            delta=now.victory_points - was.victory_points,
            total=now.victory_points,
        )
        for seat, (was, now) in enumerate(pairs)
        if now.victory_points != was.victory_points
    )


def extend_ledger(
    engine: UprisingRulesEngine,
    ledger: VpLedger,
    live: Sequence[tuple[int, ReplayStep]],
) -> VpLedger:
    """Walk the live steps the ledger has not walked yet.

    ``live`` is every live step of the game in order, each with its log
    index, and must extend the ledger (``VpLedger.extends``).
    """

    if not ledger.extends(live):
        raise ValueError("the live steps do not extend this ledger")
    if ledger.steps == len(live):
        return ledger
    state = ledger.state
    changes = list(ledger.changes)
    parts = list(ledger.parts)
    for index, step in live[ledger.steps :]:
        transition = engine.apply(state, step)
        after = transition.state
        changes.extend(step_changes(state, after, index))
        parts.extend(step_parts(state, after, transition.events, index))
        state = after
    return VpLedger(
        steps=len(live),
        last_index=live[-1][0],
        state=state,
        start=ledger.start,
        changes=tuple(changes),
        parts=tuple(parts),
    )


def ledger_json(ledger: VpLedger) -> JsonObject:
    """The public payload: the opening points, every change, in order, and
    every change split by source (``parts``, the opening ones first)."""

    entries: list[JsonValue] = [
        {
            "index": change.index,
            "round": change.round,
            "seat": change.seat,
            "delta": change.delta,
            "total": change.total,
        }
        for change in ledger.changes
    ]
    parts: list[JsonValue] = [
        {
            "index": part.index,
            "seat": part.seat,
            "kind": part.kind,
            "item": part.item,
            "points": part.points,
        }
        for part in ledger.parts
    ]
    return {
        "step_count": ledger.steps,
        "start": list(ledger.start),
        "entries": entries,
        "parts": parts,
    }
