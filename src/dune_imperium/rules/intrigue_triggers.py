"""Face-up Intrigue cards waiting on a printed trigger, and Coercive
Negotiation's Contract reveal.

A Plot card whose effect does not apply immediately stays face up in front of
its owner until it does [FAQ p. 2] (Call to Arms). This module fires those
triggers and expires face-up cards whose window has closed. It deliberately
sits below the acquisition and Reveal modules, so it applies its rewards
directly instead of going through the effect interpreter.

"When you deploy three or more units to the Conflict in a single turn"
(Distraction, Coercive Negotiation) is a condition for playing the card,
not a trigger it waits for (user ruling 2026-10-03, OQ-016); the reveal
frame Coercive Negotiation opens when played lives here.
"""

from dataclasses import replace

from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.effect_dsl import (
    OnRevealAcquisitionThisRound,
    RecruitTroops,
    RevealContractsTakeOne,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.contract_tiles import (
    contract_intrigue_trash_frame,
    receive_contract,
)
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    owned_top_frame,
    replace_player,
    reveal_is_open_for,
    update_turn_recruits,
)


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
    count; the trigger window is the owner's Reveal turn this round. Troops
    a trigger recruits join the Reveal turn's recruit count like any other
    Reveal-turn recruit: "You may deploy any units you recruit this turn and
    up to two more from your garrison" [Bloodlines p. 5] governs the
    Combat-icon deployment allowance regardless of what recruited them.
    """

    owner = state.players[player]
    if not owner.intrigue_faceup or not reveal_is_open_for(state, player):
        return RuleResult(state=state)
    events: list[GameEvent] = []
    total_recruited = 0
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
        requested_total = 0
        for section in option.sections:
            for reward in section.rewards:
                if not isinstance(reward, RecruitTroops):
                    raise NotImplementedError(
                        "reveal-acquisition triggers only support troop recruits"
                    )
                owner, recruited = recruit_troops(owner, reward.count)
                recruited_total += recruited
                requested_total += reward.count
        total_recruited += recruited_total
        trigger_source = f"{source}:reveal_trigger:{card_id}"
        events.append(
            GameEvent(
                event_id=trigger_source,
                kind="intrigue_triggered",
                payload=(
                    ("card_id", card_id),
                    ("player", player),
                    ("troops", recruited_total),
                ),
            )
        )
        events.extend(
            recruit_shortfall_events(
                trigger_source, player, requested_total, recruited_total
            )
        )
    if not events:
        return RuleResult(state=state)
    next_state = replace(state, players=replace_player(state.players, owner))
    next_state = update_turn_recruits(next_state, troops_recruited=total_recruited)
    return RuleResult(state=next_state, events=tuple(events))


def _reveal_count(card_id: str) -> int:
    """How many bank Contracts ``card_id`` reveals (Coercive Negotiation: 3)."""

    entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
    for option in entry.options if entry is not None else ():
        for section in option.sections:
            for reward in section.rewards:
                if isinstance(reward, RevealContractsTakeOne):
                    return reward.count
    return 0


def open_contract_reveal(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
) -> GameState:
    """Open Coercive Negotiation's reveal once the played card left the hand.

    "When you deploy three or more units to the Conflict in a single turn:
    Reveal three contracts from the bank. Take one and trash the other two."
    [Coercive Negotiation card]. The card is played once that condition
    holds and resolves at once (user ruling 2026-10-03, OQ-016); its
    playability already required three Contracts in the bank (OQ-064). The
    frame kind keeps the revealed Contracts face up to every seat while the
    owner chooses (``core.observation.revealed_contract_ids``).
    """

    return state.push_decision(
        DecisionFrame(
            kind=FrameKind.INTRIGUE_TRIGGER_CONTRACT,
            frame_id=f"{source}:contracts",
            decision=PlayerDecision(
                owner=player, prompt="Take one of the revealed Contracts"
            ),
            context=(("card_id", card_id), ("turn_owner", player)),
        )
    )


def takeable_trigger_contract_ids(
    state: GameState,
    player: int,
    card_id: str,
) -> tuple[str, ...]:
    """Return the bank Contracts ``card_id`` would reveal that ``player`` can take.

    Coercive Negotiation reveals the bank's top three [Coercive Negotiation
    card]. "You can't take the new Immediate contract unless you have an
    Intrigue card to trash." [Bloodlines p. 2]; the played card itself has
    already gone to the discard pile [Main p. 7].
    """

    count = _reveal_count(card_id)
    holds_intrigue = bool(state.players[player].intrigue_cards)
    return tuple(
        instance_id
        for instance_id in state.contract_bank[:count]
        if holds_intrigue
        or not contract_for_instance(instance_id).requires_intrigue_trash
    )


def legal_trigger_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Coercive Negotiation: take one of the bank's top Contracts.

    The card never says "may" ("When you deploy three or more units to the
    Conflict in a single turn: Reveal three contracts from the bank. Take one
    and trash the other two." [Coercive Negotiation card]), and "Most effects
    from a board space or card you play are mandatory, unless: a card says
    'you may' do something" [FAQ p. 3]. So the frame offers no decline. The
    card is playable only with three Contracts in the bank (OQ-064), and
    with three revealed one is always takeable: only the single Immediate
    token needs an Intrigue card to trash [Bloodlines p. 2].
    """

    frame = owned_top_frame(state, FrameKind.INTRIGUE_TRIGGER_CONTRACT, player)
    if frame is None:
        return ()
    card_id = dict(frame.context).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Intrigue trigger frame has invalid card ID")
    takes = takeable_trigger_contract_ids(state, player, card_id)
    if not takes:
        raise RuntimeError("Coercive Negotiation opened with no Contract to take")
    return tuple(
        DomainAction(
            action_id="take_trigger_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in takes
    )


def apply_trigger_contract_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Reveal the bank's top Contracts, keep the chosen one, trash the rest."""

    if action not in legal_trigger_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue Contract trigger choice")
    frame = state.decision_stack[-1]
    card_id = dict(frame.context).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Intrigue trigger frame has invalid card ID")
    player = action.actor
    source = frame.frame_id
    count = _reveal_count(card_id)
    revealed = state.contract_bank[:count]
    instance_id = str(dict(action.arguments)["instance_id"])
    definition = contract_for_instance(instance_id)
    owner = receive_contract(state.players[player], instance_id)
    popped = state.pop_decision()
    if definition.requires_intrigue_trash:
        popped = popped.push_decision(
            contract_intrigue_trash_frame(
                player, instance_id, source=f"{source}:contract:{instance_id}"
            )
        )
    next_state = replace(
        popped,
        players=replace_player(state.players, owner),
        contract_bank=state.contract_bank[count:],
        contract_trash=(
            *state.contract_trash,
            *(trashed_id for trashed_id in revealed if trashed_id != instance_id),
        ),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:contracts_revealed",
                kind="contracts_revealed",
                payload=(("contract_ids", ",".join(revealed)), ("player", player)),
            ),
            GameEvent(
                event_id=f"{source}:contract_taken",
                kind="contract_taken",
                payload=(("contract_id", instance_id), ("player", player)),
            ),
            *(
                GameEvent(
                    event_id=f"{source}:contract_trashed:{trashed_id}",
                    kind="contract_trashed",
                    payload=(("contract_id", trashed_id),),
                )
                for trashed_id in revealed
                if trashed_id != instance_id
            ),
        ),
    )


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
