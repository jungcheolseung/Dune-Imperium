"""Face-up Intrigue cards waiting on a printed trigger.

A Plot card whose effect does not apply immediately stays face up in front of
its owner until it does [FAQ p. 2]. This module fires those triggers and
expires face-up cards whose window has closed. It deliberately sits below the
acquisition and Reveal modules, so it applies its rewards directly instead of
going through the effect interpreter.
"""

from dataclasses import replace

from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.effect_dsl import (
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    PlaceSpy,
    RecruitTroops,
    RevealContractsTakeOne,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.contract_tiles import receive_contract
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    owned_top_frame,
    replace_player,
    reveal_is_open_for,
)
from dune_imperium.rules.spy_placement import place_spy, recall_spy


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
    return RuleResult(state=next_state, events=tuple(events))


def shared_spy_post_ids(state: GameState, player: int) -> tuple[str, ...]:
    """Return posts holding another player's Spy where ``player`` has none."""

    own = set(state.players[player].spy_post_ids)
    others = {
        post_id
        for candidate in state.players
        if candidate.player_id != player
        for post_id in candidate.spy_post_ids
    }
    return tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id in others and post.post_id not in own
    )


def _deployment_trigger_minimum(card_id: str) -> int | None:
    entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
    if entry is None:
        return None
    for option in entry.options:
        if isinstance(option.trigger, OnUnitsDeployedInTurn):
            return option.trigger.minimum
    return None


def _deployment_trigger_reward(
    card_id: str,
) -> PlaceSpy | RevealContractsTakeOne | None:
    entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
    if entry is None:
        return None
    for option in entry.options:
        if isinstance(option.trigger, OnUnitsDeployedInTurn):
            for section in option.sections:
                for reward in section.rewards:
                    if isinstance(reward, PlaceSpy | RevealContractsTakeOne):
                        return reward
    return None


def _trigger_frame_kind(state: GameState, player: int, card_id: str) -> str | None:
    """Return the frame a face-up trigger card can open now, if any."""

    reward = _deployment_trigger_reward(card_id)
    if isinstance(reward, PlaceSpy):
        if not shared_spy_post_ids(state, player):
            return None
        return FrameKind.INTRIGUE_TRIGGER_SPY
    if isinstance(reward, RevealContractsTakeOne):
        # Coercive Negotiation needs Contracts left in the bank.
        return (
            FrameKind.INTRIGUE_TRIGGER_CONTRACT
            if state.config.choam_module and state.contract_bank
            else None
        )
    return None


def offer_deployment_triggers(result: RuleResult) -> RuleResult:
    """Open the face-up deployment-trigger choice after a transition.

    Runs on every applied action: when a player's per-turn deployment count
    has passed a face-up card's minimum since the last offer and a shared
    post exists, one decision frame per qualifying card opens for its owner.
    A pending chance decision is never buried; a later transition re-offers.
    """

    state = result.state
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return result
    top = state.decision_stack[-1]
    if not isinstance(top.decision, PlayerDecision):
        return result
    next_state = state
    for seat in state.players:
        count = seat.units_deployed_turn
        if not seat.intrigue_faceup or count <= seat.deploy_trigger_offered_at:
            continue
        cards = tuple(
            (card_id, kind)
            for card_id in seat.intrigue_faceup
            if (minimum := _deployment_trigger_minimum(card_id)) is not None
            and minimum <= count
            and (kind := _trigger_frame_kind(next_state, seat.player_id, card_id))
            is not None
        )
        if not cards:
            continue
        marked = replace(seat, deploy_trigger_offered_at=count)
        next_state = replace(
            next_state, players=replace_player(next_state.players, marked)
        )
        for card_id, kind in cards:
            next_state = next_state.push_decision(
                DecisionFrame(
                    kind=kind,
                    frame_id=(
                        f"round:{next_state.round_number}:player:{seat.player_id}:"
                        f"deploy_trigger:{card_id}:at:{count}"
                    ),
                    decision=PlayerDecision(
                        owner=seat.player_id,
                        prompt="Use the face-up Intrigue card or decline",
                    ),
                    context=(
                        ("card_id", card_id),
                        ("turn_owner", seat.player_id),
                    ),
                )
            )
    if next_state is state:
        return result
    return RuleResult(state=next_state, events=result.events)


def legal_trigger_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the choices for one face-up deployment-trigger card."""

    frame = owned_top_frame(state, FrameKind.INTRIGUE_TRIGGER_SPY, player)
    if frame is None:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = [
        DomainAction(action_id="decline_intrigue_trigger", actor=player)
    ]
    targets = shared_spy_post_ids(state, player)
    if owner.spies_supply > 0:
        actions.extend(
            DomainAction(
                action_id="place_trigger_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in targets
        )
    elif targets:
        # No Spy in supply: recall one first [Main pp. 11, 20].
        actions.extend(
            DomainAction(
                action_id="recall_spy_for_trigger",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    return tuple(actions)


def apply_trigger_spy_action(state: GameState, action: DomainAction) -> RuleResult:
    """Decline, recall first, or place the Spy on another player's post."""

    if action not in legal_trigger_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue trigger choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Intrigue trigger frame has invalid card ID")
    player = action.actor
    owner = state.players[player]
    source = frame.frame_id

    if action.action_id == "decline_intrigue_trigger":
        # Not used: the card stays face up for a later qualifying turn
        # (OQ-016) rather than being discarded unused.
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="intrigue_trigger_declined",
                    payload=(("card_id", card_id), ("player", player)),
                ),
            ),
        )

    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Intrigue trigger choice has an invalid post")
    if action.action_id == "recall_spy_for_trigger":
        recalled = recall_spy(owner, post_id)
        next_state = replace(state, players=replace_player(state.players, recalled))
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:spy_recalled:{post_id}",
                    kind="spy_recalled",
                    payload=(("player", player), ("post_id", post_id)),
                ),
            ),
        )

    placed = place_spy(owner, post_id)
    minimum = _deployment_trigger_minimum(card_id)
    used = replace(
        placed,
        intrigue_faceup=tuple(
            held for held in placed.intrigue_faceup if held != card_id
        ),
        # The card consumed this turn's deployment count as its condition:
        # a later withdrawal may not undo it below the minimum (OQ-029).
        units_deployed_committed=max(
            placed.units_deployed_committed, minimum if minimum is not None else 0
        ),
    )
    next_state = replace(
        state.pop_decision(),
        players=replace_player(state.players, used),
        intrigue_discard=(*state.intrigue_discard, card_id),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:used",
                kind="intrigue_triggered",
                payload=(("card_id", card_id), ("player", player)),
            ),
            GameEvent(
                event_id=f"{source}:spy_placed:{post_id}",
                kind="spy_placed",
                payload=(("player", player), ("post_id", post_id)),
            ),
        ),
    )


def legal_trigger_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Coercive Negotiation: take one of the bank's top Contracts, or decline."""

    frame = owned_top_frame(state, FrameKind.INTRIGUE_TRIGGER_CONTRACT, player)
    if frame is None:
        return ()
    card_id = dict(frame.context).get("card_id")
    reward = _deployment_trigger_reward(card_id) if isinstance(card_id, str) else None
    count = reward.count if isinstance(reward, RevealContractsTakeOne) else 0
    return (
        DomainAction(action_id="decline_intrigue_contract_trigger", actor=player),
        *(
            DomainAction(
                action_id="take_trigger_contract",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in state.contract_bank[:count]
        ),
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
    if action.action_id == "decline_intrigue_contract_trigger":
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="intrigue_trigger_declined",
                    payload=(("card_id", card_id), ("player", player)),
                ),
            ),
        )
    reward = _deployment_trigger_reward(card_id)
    count = reward.count if isinstance(reward, RevealContractsTakeOne) else 0
    revealed = state.contract_bank[:count]
    instance_id = str(dict(action.arguments)["instance_id"])
    owner = receive_contract(state.players[player], instance_id)
    minimum = _deployment_trigger_minimum(card_id)
    used = replace(
        owner,
        intrigue_faceup=tuple(
            held for held in owner.intrigue_faceup if held != card_id
        ),
        units_deployed_committed=max(
            owner.units_deployed_committed, minimum if minimum is not None else 0
        ),
    )
    next_state = replace(
        state.pop_decision(),
        players=replace_player(state.players, used),
        contract_bank=state.contract_bank[count:],
        contract_trash=(
            *state.contract_trash,
            *(trashed_id for trashed_id in revealed if trashed_id != instance_id),
        ),
        intrigue_discard=(*state.intrigue_discard, card_id),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:used",
                kind="intrigue_triggered",
                payload=(("card_id", card_id), ("player", player)),
            ),
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
