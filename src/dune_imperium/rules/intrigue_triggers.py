"""Face-up Intrigue cards waiting on a printed trigger.

A Plot card whose effect does not apply immediately stays face up in front of
its owner until it does [FAQ p. 2]. This module fires those triggers and
expires face-up cards whose window has closed. It deliberately sits below the
acquisition and Reveal modules, so it applies its rewards directly instead of
going through the effect interpreter.
"""

from dataclasses import replace

from dune_imperium.content.uprising.effect_dsl import (
    OnRevealAcquisitionThisRound,
    RecruitTroops,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import replace_player, reveal_is_open_for


def _faceup_entries_with_trigger(
    faceup: tuple[str, ...],
    trigger_type: type,
) -> tuple[str, ...]:
    matches: list[str] = []
    for card_id in faceup:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None:
            continue
        if any(isinstance(option.trigger, trigger_type) for option in entry.options):
            matches.append(card_id)
    return tuple(matches)


def fire_reveal_acquisition_intrigue(
    state: GameState,
    player: int,
    *,
    source: str,
) -> RuleResult:
    """Fire each face-up per-acquisition card once for one Reveal acquisition.

    Only acquisitions made while the owner's own Reveal frame is on the stack
    count; the trigger window is the owner's Reveal turn this round.
    """

    owner = state.players[player]
    if not owner.intrigue_faceup or not reveal_is_open_for(state, player):
        return RuleResult(state=state)
    events: list[GameEvent] = []
    for card_id in _faceup_entries_with_trigger(
        owner.intrigue_faceup, OnRevealAcquisitionThisRound
    ):
        entry = INTRIGUE_CARDS_BY_INSTANCE[card_id]
        option = next(
            option
            for option in entry.options
            if isinstance(option.trigger, OnRevealAcquisitionThisRound)
        )
        recruited_total = 0
        for section in option.sections:
            for reward in section.rewards:
                if not isinstance(reward, RecruitTroops):
                    raise NotImplementedError(
                        "reveal-acquisition triggers only support troop recruits"
                    )
                owner, recruited = recruit_troops(owner, reward.count)
                recruited_total += recruited
        events.append(
            GameEvent(
                event_id=f"{source}:reveal_trigger:{card_id}",
                kind="intrigue_triggered",
                payload=(
                    ("card_id", card_id),
                    ("player", player),
                    ("troops", recruited_total),
                ),
            )
        )
    if not events:
        return RuleResult(state=state)
    next_state = replace(state, players=replace_player(state.players, owner))
    return RuleResult(state=next_state, events=tuple(events))


def expire_reveal_faceup_intrigue(state: GameState, player: int) -> RuleResult:
    """Discard face-up cards whose window was the owner's Reveal turn.

    Called when the owner's Reveal turn ends: a per-acquisition card's
    "this round" window has closed, whether or not it ever fired.
    """

    owner = state.players[player]
    expired = _faceup_entries_with_trigger(
        owner.intrigue_faceup, OnRevealAcquisitionThisRound
    )
    if not expired:
        return RuleResult(state=state)
    next_owner = replace(
        owner,
        intrigue_faceup=tuple(
            card_id for card_id in owner.intrigue_faceup if card_id not in expired
        ),
    )
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        intrigue_discard=(*state.intrigue_discard, *expired),
    )
    events = tuple(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{player}:intrigue_expired:{card_id}"
            ),
            kind="intrigue_expired",
            payload=(("card_id", card_id), ("player", player)),
        )
        for card_id in expired
    )
    return RuleResult(state=next_state, events=events)
