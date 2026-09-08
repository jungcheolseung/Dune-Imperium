"""Acquiring from the Tleilaxu Row [Immortality pp. 8-9].

"You can spend your specimens in the Axolotl tanks to acquire a Tleilaxu
card in the Tleilaxu Row (paying the specimen cost shown in the top right
corner)" during the Reveal turn; the card goes to the discard pile, or, once
the first genetic marker is reached, may go on top of the deck [Immortality
pp. 6, 8]. "The Tleilaxu Row must always have two cards plus Reclaimed
Forces. Whenever it does not, replace missing cards from the top of the
Tleilaxu deck. The Reclaimed Forces card is never removed ... When a player
'acquires' it, they choose one of its effects (to recruit two troops, or
advance their Tleilaxu token one space on the Tleilaxu track), but leave the
card in place" [Immortality p. 9].
"""

from dataclasses import replace

from dune_imperium.content.immortality.board import (
    TLEILAXU_ROW_SIZE,
    genetic_markers_reached,
)
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import (
    apply_acquisition_track_effects,
    resolve_acquisition_bonus,
    with_pending_draw,
)
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    frame_context,
    owned_top_frame,
    replace_player,
    with_context,
)
from dune_imperium.rules.immortality import advance_tleilaxu
from dune_imperium.rules.specimens import spend_specimens

RECLAIMED_FORCES_CHOICES = ("troops", "tleilaxu")


def refill_tleilaxu_row(state: GameState) -> GameState:
    """Fill the Row back up to two cards from the top of the Tleilaxu deck."""

    row = list(state.tleilaxu_row)
    deck = list(state.tleilaxu_deck)
    while len(row) < TLEILAXU_ROW_SIZE and deck:
        row.append(deck.pop(0))
    return replace(state, tleilaxu_row=tuple(row), tleilaxu_deck=tuple(deck))


def legal_tleilaxu_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the Row cards and Reclaimed Forces the revealer can pay for."""

    if not state.config.immortality:
        return ()
    if owned_top_frame(state, FrameKind.REVEAL, player) is None:
        return ()
    owner = state.players[player]
    deck_top_allowed = genetic_markers_reached(owner.research_space) >= 1
    actions: list[DomainAction] = []
    for instance_id in state.tleilaxu_row:
        if tleilaxu_card_for_instance(instance_id).specimen_cost > owner.specimens:
            continue
        actions.append(
            DomainAction(
                action_id="acquire_tleilaxu",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
        )
        if deck_top_allowed:
            actions.append(
                DomainAction(
                    action_id="acquire_tleilaxu",
                    actor=player,
                    arguments=(("instance_id", instance_id), ("to_deck_top", True)),
                )
            )
    if owner.specimens >= RECLAIMED_FORCES.specimen_cost:
        actions.extend(
            DomainAction(
                action_id="acquire_reclaimed_forces",
                actor=player,
                arguments=(("choice", choice),),
            )
            for choice in RECLAIMED_FORCES_CHOICES
        )
    return tuple(actions)


def apply_tleilaxu_acquisition(state: GameState, action: DomainAction) -> RuleResult:
    """Pay the specimens, take the card, refill the Row, pay the acquire box."""

    if action not in legal_tleilaxu_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Tleilaxu Row acquisition")
    player = action.actor
    arguments = dict(action.arguments)
    source = f"round:{state.round_number}:player:{player}:acquire_tleilaxu"
    if action.action_id == "acquire_reclaimed_forces":
        return _apply_reclaimed_forces(state, player, str(arguments["choice"]), source)
    return acquire_tleilaxu_card(
        state,
        player,
        str(arguments["instance_id"]),
        to_deck_top=arguments.get("to_deck_top") is True,
        source=source,
    )


def acquire_tleilaxu_card(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    to_deck_top: bool,
    source: str,
) -> RuleResult:
    """Take a Row card for its specimens (also for Harvest Cells' offer)."""

    if instance_id not in state.tleilaxu_row:
        raise ValueError("the card is not in the Tleilaxu Row")
    definition = tleilaxu_card_for_instance(instance_id)
    if (
        to_deck_top
        and genetic_markers_reached(state.players[player].research_space) < 1
    ):
        raise ValueError("the deck top needs the first genetic marker")
    owner = spend_specimens(state.players[player], definition.specimen_cost)
    next_owner = replace(
        owner,
        # "you may put Tleilaxu cards you acquire on top of your deck"
        # [Immortality p. 6]; otherwise the discard pile [Immortality p. 8].
        deck=(instance_id, *owner.deck) if to_deck_top else owner.deck,
        discard_pile=(
            owner.discard_pile if to_deck_top else (*owner.discard_pile, instance_id)
        ),
    )
    bonus = resolve_acquisition_bonus(state, player, instance_id, next_owner)
    next_state = refill_tleilaxu_row(
        replace(
            state,
            players=replace_player(state.players, bonus.owner),
            tleilaxu_row=tuple(
                card_id for card_id in state.tleilaxu_row if card_id != instance_id
            ),
            intrigue_deck=bonus.intrigue_deck,
            pending_intrigue_draws=with_pending_draw(state, bonus.pending_draw),
        )
    )
    if bonus.places_spy or bonus.takes_contract:
        raise NotImplementedError("Tleilaxu acquire boxes never place Spies")
    tracked = apply_acquisition_track_effects(
        next_state, player, definition, source=f"{source}:{instance_id}"
    )
    return RuleResult(
        state=tracked.state,
        events=(
            GameEvent(
                event_id=f"{source}:{instance_id}",
                kind="tleilaxu_card_acquired",
                # The identity was public in the Row; the instance is named
                # only while it stays public (the discard pile), since the
                # deck order is hidden (OQ-010).
                payload=(
                    ("card_id", definition.card.card_id),
                    *(() if to_deck_top else (("instance_id", instance_id),)),
                    ("player", player),
                    ("specimens", definition.specimen_cost),
                    ("to_deck_top", to_deck_top),
                ),
            ),
            *bonus.events,
            *tracked.events,
        ),
    )


def _apply_reclaimed_forces(
    state: GameState, player: int, choice: str, source: str
) -> RuleResult:
    owner = spend_specimens(state.players[player], RECLAIMED_FORCES.specimen_cost)
    event = GameEvent(
        event_id=f"{source}:reclaimed_forces",
        kind="reclaimed_forces_acquired",
        payload=(
            ("choice", choice),
            ("player", player),
            ("specimens", RECLAIMED_FORCES.specimen_cost),
        ),
    )
    if choice == "tleilaxu":
        paid = replace(state, players=replace_player(state.players, owner))
        advanced = advance_tleilaxu(
            paid, player, 1, source=f"{source}:reclaimed_forces"
        )
        return RuleResult(state=advanced.state, events=(event, *advanced.events))
    recruited_owner, recruited = recruit_troops(owner, 2)
    next_state = _record_reveal_recruits(
        replace(state, players=replace_player(state.players, recruited_owner)),
        recruited,
    )
    return RuleResult(
        state=next_state,
        events=(
            event,
            *recruit_shortfall_events(
                f"{source}:reclaimed_forces", player, 2, recruited
            ),
        ),
    )


def _record_reveal_recruits(state: GameState, recruited: int) -> GameState:
    """Count Reveal-turn recruits toward a Combat-icon deployment [Bloodlines p. 5]."""

    frame = state.decision_stack[-1]
    context = frame_context(frame)
    previous = context.get("reveal_troops_recruited", 0)
    if isinstance(previous, bool) or not isinstance(previous, int):
        raise RuntimeError("Reveal frame has an invalid recruit count")
    context["reveal_troops_recruited"] = previous + recruited
    return replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )
