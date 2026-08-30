"""The six-Leader public draft of OQ-007 (project convention, not official).

The official setup only says players select Leaders or assign them randomly
[Main p. 4] and defines no draft order, so the pick sequence here is the
recorded project convention: after Objectives fix the First Player, seats
pick one Leader each from the face-up six-Leader pool in reverse round-1
turn order, the First Player last, everything public. The two unpicked
Leaders stay unused for the game.
"""

from dataclasses import replace

from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import FrameKind, replace_player, top_frame_of_kind
from dune_imperium.rules.setup import SARDAUKAR_CONTRACT_IDS


def draft_pick_order(first_player: int, players: int) -> tuple[int, ...]:
    """Reverse round-1 turn order: the First Player picks last (OQ-007)."""

    return tuple(
        (first_player + offset) % players for offset in range(players - 1, -1, -1)
    )


def remaining_draft_pool(state: GameState) -> tuple[str, ...]:
    """Return the face-up Leaders nobody has picked yet, in draw order."""

    picked = {
        player.leader_id for player in state.players if player.leader_id is not None
    }
    return tuple(
        leader_id
        for leader_id in state.leader_draft_pool
        if leader_id not in picked
    )


def legal_leader_draft_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every remaining pool Leader to the seat holding the pick."""

    frame = top_frame_of_kind(state, FrameKind.LEADER_DRAFT)
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="pick_leader",
            actor=player,
            arguments=(("leader_id", leader_id),),
        )
        for leader_id in remaining_draft_pool(state)
    )


def apply_leader_draft_pick(state: GameState, action: DomainAction) -> RuleResult:
    """Assign the picked Leader and pass the pick on, or finish setup."""

    if action not in legal_leader_draft_actions(state, action.actor):
        raise ValueError("action is not a legal Leader draft pick")
    if state.first_player is None:
        raise RuntimeError("the Leader draft requires a decided First Player")
    picker = action.actor
    leader_id = str(dict(action.arguments)["leader_id"])
    definition = LEADERS_BY_ID[leader_id]
    owner = state.players[picker]
    picked_owner = replace(
        owner,
        leader_id=leader_id,
        # Double-sided Leaders begin on their printed setup face
        # [Main p. 17]; every other Leader's face is its identity.
        leader_face_id=definition.setup_face_id or leader_id,
        # Printed setup rules may remove starting cards (Staban Tuek's
        # Limited Allies); filtering the already-shuffled deck keeps the
        # remaining order uniformly random.
        deck=tuple(
            instance_id
            for instance_id in owner.deck
            if starting_card_for_instance(instance_id).card.card_id
            not in definition.removed_starting_card_ids
        ),
    )
    players = replace_player(state.players, picked_owner)
    events = [
        GameEvent(
            event_id=f"setup:leader_draft:pick:{picker}:{leader_id}",
            kind="leader_drafted",
            payload=(("leader_id", leader_id), ("player", picker)),
        )
    ]

    order = draft_pick_order(state.first_player, state.config.players)
    picked_count = sum(1 for player in players if player.leader_id is not None)
    if picked_count < len(order):
        frame = state.decision_stack[-1]
        next_frame = replace(
            frame,
            decision=PlayerDecision(
                owner=order[picked_count],
                prompt="Pick a Leader from the face-up draft pool",
            ),
        )
        return RuleResult(
            state=replace(
                state,
                players=players,
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=tuple(events),
        )

    return _finish_draft_setup(state, players, events)


def _finish_draft_setup(
    state: GameState,
    players: tuple[PlayerState, ...],
    events: list[GameEvent],
) -> RuleResult:
    """Deal the Contract market and hand the finished setup to Round Start."""

    sardaukar_set_aside: tuple[str, ...] = ()
    face_up: tuple[str, ...] = ()
    bank: tuple[str, ...] = ()
    if state.config.choam_module:
        # Sardaukar Commander sets both Sardaukar Contracts aside; only
        # Shaddam can acquire them [Shaddam Corrino IV card]. Removing them
        # from the pre-shuffled order keeps the rest uniformly random.
        picked = {player.leader_id for player in players}
        if "shaddam_corrino_iv" in picked:
            sardaukar_set_aside = SARDAUKAR_CONTRACT_IDS
        ordered = tuple(
            contract_id
            for contract_id in state.contract_bank
            if contract_id not in sardaukar_set_aside
        )
        face_up, bank = ordered[:2], ordered[2:]

    unused = tuple(
        leader_id
        for leader_id in state.leader_draft_pool
        if leader_id not in {player.leader_id for player in players}
    )
    events.append(
        GameEvent(
            event_id="setup:leader_draft:unused",
            kind="leader_draft_unused",
            payload=(("leader_ids", ",".join(unused)),),
        )
    )
    return RuleResult(
        state=replace(
            state,
            phase=GamePhase.ROUND_START,
            players=players,
            contract_bank=bank,
            face_up_contract_ids=face_up,
            sardaukar_contract_ids=sardaukar_set_aside,
            decision_stack=state.decision_stack[:-1],
        ),
        events=tuple(events),
    )
