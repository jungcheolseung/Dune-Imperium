"""One effect's Influence over several Factions it names, a row each (OQ-153).

docs/rules/open-questions.md OQ-153 (2026-10-30, project convention applying
OQ-027, OQ-112 and OQ-141): "진영을 모두 정해 주는 효과(Quid Pro Quo)는 진영마다
줄 하나를 내고 소유자가 원하는 순서로 받는다(OQ-141과 같은 꼴). 받을 진영이 하나뿐이면
줄 하나." The order matters once Tessia Vernius' Snooper tokens are on the
tracks: which track a gain reaches first takes the next Snooper reward
(docs/rules/rise-of-ix.md 10).

Quid Pro Quo is a Plot, played only in its owner's own turn [DI pp. 7-8], so
its Faction rows wait on that turn's frame (``turn_rows.EFFECT_INFLUENCE``)
beside the turn's other effects and hold its end until taken, as an acquire
box's fixed icons do (OQ-141). The Factions are those with one of the
player's Agents when the card resolves ("Gain one Influence with each
Faction that has at least one of your Agents on its board spaces" [Quid Pro
Quo card]); a Faction at the top gains nothing when its row is taken
(OQ-060).

The effect only announces the rows it owes (``EFFECT_INFLUENCE_OWED``); they
are queued once the action's handler is done (``settle_effect_influence``),
because the Intrigue play writes its frames back after the rewards, which
would drop a row put there before (the pattern ``rules.unload`` uses).

Outside its owner's turn the same rows are offered in a window of their own
(``FrameKind.EFFECT_INFLUENCE_WINDOW``, ``effect_influence_window``), as a
Contract's reward icons are (OQ-112 (4)): Panopticon's Endgame line in a
Rise of Ix game, "Endgame: Influence 1 이하인 진영마다 Influence 1"
(docs/rules/bloodlines.md 5), whose order OQ-153's combination note settles
("들 수 있으면 같은 원칙(진영마다 줄)을 따르고"; ``rules.tech``). The window
names what resumes once its last row is taken (``RESUME_KEY``).
"""

from collections.abc import Iterable
from typing import Final

from dune_imperium.content.core.icons import Faction
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.influence import gain_faction_influence

EFFECT_INFLUENCE_ACTION: Final = "resolve_effect_influence"
EFFECT_INFLUENCE_OWED: Final = "effect_influence_owed"
FACTIONS_KEY: Final = "factions"
"""The window's Factions still owed, comma-joined, in Faction order."""
RESUME_KEY: Final = "resume"
"""What resumes once the window's last row is taken: ``RESUME_ENDGAME_TECH``
(the Endgame's Tech lines from the window's owner on, ``rules.tech``)."""
RESUME_ENDGAME_TECH: Final = "endgame_tech"
_FRAME: Final = "Faction Influence window"


def effect_influence_owed(
    source: str, player: int, factions: Iterable[Faction]
) -> GameEvent:
    """The event announcing an effect's Influence rows, one per Faction."""

    return GameEvent(
        event_id=f"{source}:influence_rows",
        kind="effect_influence_owed",
        payload=(
            ("factions", ",".join(faction.value for faction in factions)),
            ("player", player),
        ),
    )


def settle_effect_influence(
    result: RuleResult, *, skip: frozenset[str] = frozenset()
) -> RuleResult:
    """Queue the rows ``result``'s events announce on their owner's turn
    (``skip``: event ids already settled earlier in the transition)."""

    state = result.state
    for event in result.events:
        if event.kind != EFFECT_INFLUENCE_OWED or event.event_id in skip:
            continue
        payload = dict(event.payload)
        player, factions = payload["player"], payload["factions"]
        assert isinstance(player, int) and isinstance(factions, str)
        for value in factions.split(","):
            queued = turn_rows.queue(
                state, player, (turn_rows.EFFECT_INFLUENCE, event.event_id, value)
            )
            if queued is None:
                raise NotImplementedError(
                    "an effect's per-Faction Influence waits on its owner's turn "
                    "(a Plot is played only there, OQ-153)"
                )
            state = queued
    if state is result.state:
        return result
    return RuleResult(state=state, events=result.events)


def effect_influence_event_ids(events: Iterable[GameEvent]) -> frozenset[str]:
    """The ids of the announcements among ``events``, for ``skip``."""

    return frozenset(
        event.event_id for event in events if event.kind == EFFECT_INFLUENCE_OWED
    )


def _row(player: int, faction: str) -> DomainAction:
    return DomainAction(
        action_id=EFFECT_INFLUENCE_ACTION,
        actor=player,
        arguments=(("faction", faction),),
    )


def effect_influence_window(
    player: int, source: str, factions: Iterable[Faction], *, resume: str
) -> DecisionFrame:
    """The owner's window over an effect's per-Faction Influence outside its
    turn, a row per Faction in any order (OQ-153); ``source`` names each
    gain's events (``<source>:<faction>``), ``resume`` what follows it."""

    context: dict[str, ActionValue] = {
        FACTIONS_KEY: ",".join(faction.value for faction in factions),
        RESUME_KEY: resume,
        "source": source,
        "turn_owner": player,
    }
    return with_context(
        DecisionFrame(
            kind=FrameKind.EFFECT_INFLUENCE_WINDOW,
            frame_id=f"{source}:influence_rows",
            decision=PlayerDecision(
                owner=player, prompt="Gain Influence with each Faction, in any order"
            ),
            context=(),
        ),
        context,
    )


def _window_factions(frame: DecisionFrame) -> tuple[str, ...]:
    text = context_str(dict(frame.context), FACTIONS_KEY, owner=_FRAME)
    return tuple(value for value in text.split(",") if value)


def legal_effect_influence_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row per Faction waiting on ``player``'s own turn, or in its open
    window."""

    window = owned_top_frame(state, FrameKind.EFFECT_INFLUENCE_WINDOW, player)
    if window is not None:
        return tuple(_row(player, value) for value in _window_factions(window))
    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return ()
    return tuple(
        dict.fromkeys(
            _row(player, value)
            for kind, _source, value in turn_rows.pending(frame)
            if kind == turn_rows.EFFECT_INFLUENCE
        )
    )


def apply_effect_influence(state: GameState, action: DomainAction) -> RuleResult:
    """Take one Faction's Influence (the oldest waiting row of it)."""

    player = action.actor
    if action not in legal_effect_influence_actions(state, player):
        raise ValueError("action is not a legal Faction Influence row")
    faction = str(dict(action.arguments)["faction"])
    window = owned_top_frame(state, FrameKind.EFFECT_INFLUENCE_WINDOW, player)
    if window is not None:
        return _apply_window_row(state, player, window, faction)
    frame = turn_rows.rows_frame(state, player)
    assert frame is not None
    item = next(
        item
        for item in turn_rows.pending(frame)
        if item[0] == turn_rows.EFFECT_INFLUENCE and item[2] == faction
    )
    return gain_faction_influence(
        turn_rows.take(state, player, item),
        player,
        Faction(faction),
        1,
        event_prefix=f"{item[1]}:influence:{faction}",
    )


def _apply_window_row(
    state: GameState, player: int, window: DecisionFrame, faction: str
) -> RuleResult:
    """Take one Faction's row of the open window; its last row closes it and
    resumes what it held back (``RESUME_KEY``)."""

    context = dict(window.context)
    source = context_str(context, "source", owner=_FRAME)
    remaining = [value for value in _window_factions(window) if value != faction]
    if remaining:
        context[FACTIONS_KEY] = ",".join(remaining)
        state = replace_top_frame(state, with_context(window, context))
    else:
        state = state.pop_decision()
    gained = gain_faction_influence(
        state, player, Faction(faction), 1, event_prefix=f"{source}:{faction}"
    )
    if remaining:
        return gained
    resume = context_str(context, RESUME_KEY, owner=_FRAME)
    if resume != RESUME_ENDGAME_TECH:
        raise ValueError(f"a Faction Influence window does not resume {resume!r}")
    # Imported here: the Tech rules import the effect interpreter, which
    # imports this module.
    from dune_imperium.rules.tech import apply_endgame_tech_effects

    resumed = apply_endgame_tech_effects(gained.state, resume_after=player)
    return RuleResult(state=resumed.state, events=(*gained.events, *resumed.events))
