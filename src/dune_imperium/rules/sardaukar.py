"""Sardaukar Commanders and their Skills (Bloodlines, ``docs/rules/bloodlines.md`` §3).

Three decision points are added when the option is on:

- The Commander waiting on a visited board space is one more freely ordered
  effect of the visit: pay 2 Solari to acquire and recruit it and choose one
  face-up Skill (``acquire_sardaukar_commander``), or decline
  (``decline_sardaukar_commander``) [Bloodlines p. 4]. Without a choosable
  Skill the Commander is acquired without one (OQ-031).
- Once per turn, Agent or Reveal, 2 Solari recruit one Commander from the
  supply to the garrison without a new Skill
  (``recruit_sardaukar_commander``) [Bloodlines p. 4].
- Desperate's "Reveal Turn: Trash this -> 3 swords" is an optional arrow of
  the Reveal turn while a Commander is in the Conflict
  (``trash_skill_for_strength``) [Desperate Skill tile].

The basic deployment of a recruited or garrisoned Commander lives in
``combat_deployment`` and its strength in ``strength``.
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_COST_SOLARI,
    SKILLS_BY_ID,
    skill_for_instance,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_trash import (
    with_recruited_units,
)
from dune_imperium.rules.effects import (
    BOARD_ICON_COMMANDER,
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.reveal_turn import (
    add_reveal_optional_sword_strength,
    add_reveal_strength,
)

_FRAME_LABEL = "Agent-turn effect frame"


def _owned_effect_context(
    state: GameState,
    player: int,
) -> dict[str, ActionValue] | None:
    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    return context


def commander_cost(owner: PlayerState) -> int:
    """Return the Solari a Commander costs the owner this turn.

    2 Solari [Bloodlines p. 4], less Honor Guard's discount for the turn
    (Intrigue card face), never below zero.
    """

    return max(0, COMMANDER_COST_SOLARI - owner.commander_discount_turn)


def _skill_identity(instance_id: str) -> str:
    return skill_for_instance(instance_id).skill_id


def eligible_face_up_skill_ids(state: GameState, owner: PlayerState) -> tuple[str, ...]:
    """Return the face-up Skill identities the owner may still choose.

    "You cannot choose a copy of a Sardaukar Commander Skill already in your
    supply" [Bloodlines p. 4]; two face-up copies of one Skill are one
    choice. An empty result means the Commander comes without a Skill (OQ-031).
    """

    held = {_skill_identity(instance_id) for instance_id in owner.skill_ids}
    seen: list[str] = []
    for instance_id in state.skill_face_up:
        skill_id = _skill_identity(instance_id)
        if skill_id in held or skill_id in seen:
            continue
        seen.append(skill_id)
    return tuple(seen)


def legal_sardaukar_commander_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the visited space's Commander for 2 Solari, or its refusal."""

    context = _owned_effect_context(state, player)
    if context is None or not board_icon_is_pending(context, BOARD_ICON_COMMANDER):
        return ()
    decline = DomainAction(action_id="decline_sardaukar_commander", actor=player)
    space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
    owner = state.players[player]
    if (
        space_id not in state.sardaukar_commander_space_ids
        or owner.resources.solari < commander_cost(owner)
    ):
        return (decline,)
    skills = eligible_face_up_skill_ids(state, owner)
    if not skills:
        # OQ-031 (user decision 2026-09-07): every face-up Skill is one the
        # owner already holds, so the Commander is bought without a Skill.
        return (
            decline,
            DomainAction(action_id="acquire_sardaukar_commander", actor=player),
        )
    return (
        decline,
        *(
            DomainAction(
                action_id="acquire_sardaukar_commander",
                actor=player,
                arguments=(("skill_id", skill_id),),
            )
            for skill_id in skills
        ),
    )


def _take_face_up_skill(
    state: GameState,
    owner: PlayerState,
    skill_id: str,
) -> tuple[GameState, PlayerState, str, str | None]:
    """Move one face-up copy of ``skill_id`` to the owner and refill the row."""

    instance_id = next(
        candidate
        for candidate in state.skill_face_up
        if _skill_identity(candidate) == skill_id
    )
    face_up = [
        candidate for candidate in state.skill_face_up if candidate != instance_id
    ]
    revealed: str | None = None
    stack = state.skill_stack
    if stack:
        revealed = stack[0]
        face_up.append(revealed)
        stack = stack[1:]
    next_state = replace(state, skill_face_up=tuple(face_up), skill_stack=stack)
    next_owner = replace(owner, skill_ids=(*owner.skill_ids, instance_id))
    return next_state, next_owner, instance_id, revealed


def apply_sardaukar_commander_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Buy the space's Commander (recruiting it to the garrison) or decline."""

    if action not in legal_sardaukar_commander_actions(state, action.actor):
        raise ValueError("action is not a legal Sardaukar Commander choice")
    _, context = current_agent_effect_context(state)
    player = action.actor
    space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
    source = f"round:{state.round_number}:player:{player}:board:{space_id}"
    finish_board_icon(context, BOARD_ICON_COMMANDER)
    if action.action_id == "decline_sardaukar_commander":
        next_state = advance_after_effect(state, context)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:{BOARD_ICON_COMMANDER}:declined",
                    kind="sardaukar_commander_declined",
                    payload=(("player", player), ("space_id", space_id)),
                ),
            ),
        )

    owner = state.players[player]
    cost = commander_cost(owner)
    next_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari - cost),
        commanders_garrison=owner.commanders_garrison + 1,
    )
    working = replace(
        state,
        sardaukar_commander_space_ids=tuple(
            candidate
            for candidate in state.sardaukar_commander_space_ids
            if candidate != space_id
        ),
    )
    skill_value = dict(action.arguments).get("skill_id")
    skill_id = str(skill_value) if skill_value is not None else ""
    working, next_owner, events = _gain_skill(working, next_owner, skill_id, source)
    # The Commander is recruited this turn, so it may join the turn's basic
    # deployment like a recruited troop [Bloodlines p. 4].
    context["troops_recruited"] = (
        context_int(context, "troops_recruited", owner=_FRAME_LABEL) + 1
    )
    players = replace_player(working.players, next_owner)
    next_state = advance_after_effect(
        replace(working, players=players), context, players
    )
    events.insert(
        0,
        GameEvent(
            event_id=f"{source}:{BOARD_ICON_COMMANDER}",
            kind="sardaukar_commander_acquired",
            payload=(
                ("player", player),
                ("skill_id", skill_id),
                ("solari", cost),
                ("space_id", space_id),
            ),
        ),
    )
    return RuleResult(state=next_state, events=tuple(events))


def _gain_skill(
    state: GameState,
    owner: PlayerState,
    skill_id: str,
    source: str,
) -> tuple[GameState, PlayerState, list[GameEvent]]:
    """Take the chosen face-up Skill; an empty ``skill_id`` takes none (OQ-031)."""

    if not skill_id:
        return state, owner, []
    state, owner, instance_id, revealed = _take_face_up_skill(state, owner, skill_id)
    events = [
        GameEvent(
            event_id=f"{source}:skill:{instance_id}",
            kind="skill_gained",
            payload=(
                ("player", owner.player_id),
                ("skill_id", skill_id),
                ("skill_instance_id", instance_id),
            ),
        )
    ]
    if revealed is not None:
        events.append(
            GameEvent(
                event_id=f"{source}:skill_revealed:{revealed}",
                kind="skill_revealed",
                payload=(
                    ("skill_id", _skill_identity(revealed)),
                    ("skill_instance_id", revealed),
                ),
            )
        )
    return state, owner, events


def _acquire_bank_commander(
    state: GameState,
    player: int,
    card_id: str,
    skill_id: str,
    *,
    source: str,
) -> RuleResult:
    """Move the bank's Commander to the garrison with ``skill_id`` (or none)."""

    if state.sardaukar_commanders_bank < 1:
        raise RuntimeError("no Sardaukar Commander is left in the bank")
    owner = state.players[player]
    working = replace(
        state, sardaukar_commanders_bank=state.sardaukar_commanders_bank - 1
    )
    next_owner = replace(owner, commanders_garrison=owner.commanders_garrison + 1)
    working, next_owner, events = _gain_skill(working, next_owner, skill_id, source)
    players = replace_player(working.players, next_owner)
    # Recruited this turn: it may join an open Agent turn's basic deployment
    # like a recruited troop [Bloodlines p. 4].
    decision_stack = with_recruited_units(working.decision_stack, player, 1)
    events.insert(
        0,
        GameEvent(
            event_id=f"{source}:commander",
            kind="sardaukar_commander_acquired",
            payload=(
                ("card_id", card_id),
                ("player", player),
                ("skill_id", skill_id),
                ("solari", 0),
            ),
        ),
    )
    return RuleResult(
        state=replace(working, players=players, decision_stack=decision_stack),
        events=tuple(events),
    )


def skill_choice_is_queued(state: GameState) -> bool:
    """Return whether an owed Commander acquisition can open its choice now."""

    frame = state.decision_stack[-1] if state.decision_stack else None
    return bool(state.pending_skill_choices) and (
        frame is None or not isinstance(frame.decision, ChanceDecision)
    )


def begin_skill_choice(state: GameState) -> RuleResult:
    """Open the oldest owed Skill choice, or drop it if nothing can be gained."""

    if not state.pending_skill_choices:
        raise ValueError("there is no pending Skill choice")
    player, card_id, source = state.pending_skill_choices[0]
    remaining = replace(state, pending_skill_choices=state.pending_skill_choices[1:])
    if remaining.sardaukar_commanders_bank >= 1 and not eligible_face_up_skill_ids(
        remaining, remaining.players[player]
    ):
        # Every face-up Skill is already held: the Commander comes without
        # a Skill and needs no choice (OQ-031, OQ-035).
        return _acquire_bank_commander(remaining, player, card_id, "", source=source)
    if remaining.sardaukar_commanders_bank < 1:
        # The bank emptied while the trash effect finished (OQ-035).
        return RuleResult(
            state=remaining,
            events=(
                GameEvent(
                    event_id=f"{source}:commander_unavailable",
                    kind="sardaukar_commander_unavailable",
                    payload=(("card_id", card_id), ("player", player)),
                ),
            ),
        )
    frame = DecisionFrame(
        kind=FrameKind.SKILL_CHOICE,
        frame_id=f"{source}:skill_choice",
        decision=PlayerDecision(
            owner=player,
            prompt="Choose the Skill for the acquired Sardaukar Commander",
        ),
        context=(("card_id", card_id), ("player", player), ("source", source)),
    )
    return RuleResult(state=remaining.push_decision(frame))


def legal_skill_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the choosable Skills for a Commander acquired by a card effect."""

    frame = owned_top_frame(state, FrameKind.SKILL_CHOICE, player)
    if frame is None:
        return ()
    return tuple(
        DomainAction(
            action_id="choose_skill",
            actor=player,
            arguments=(("skill_id", skill_id),),
        )
        for skill_id in eligible_face_up_skill_ids(state, state.players[player])
    )


def apply_skill_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Take the bank's Commander into the garrison with the chosen Skill."""

    if action not in legal_skill_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Skill choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source = context_str(context, "source", owner="Skill choice frame")
    card_id = context_str(context, "card_id", owner="Skill choice frame")
    skill_id = str(dict(action.arguments)["skill_id"])
    return _acquire_bank_commander(
        state.pop_decision(), action.actor, card_id, skill_id, source=source
    )


def _can_pay_commander_recruit(owner: PlayerState) -> bool:
    return (
        not owner.commander_recruited_turn
        and owner.commanders_supply > 0
        and owner.resources.solari >= commander_cost(owner)
    )


def legal_commander_recruit_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the once-per-turn paid recruit of a Commander from the supply.

    Available in the Agent turn (its effect frame) and in the Reveal turn
    [Bloodlines p. 4]; the Commander goes to the garrison and, in an Agent
    turn, counts as recruited this turn for the basic deployment.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not state.config.bloodlines:
        return ()
    if (
        _owned_effect_context(state, player) is None
        and owned_top_frame(state, FrameKind.REVEAL, player) is None
    ):
        return ()
    if not _can_pay_commander_recruit(state.players[player]):
        return ()
    return (DomainAction(action_id="recruit_sardaukar_commander", actor=player),)


def apply_commander_recruit(state: GameState, action: DomainAction) -> RuleResult:
    """Pay 2 Solari to move one Commander from the supply to the garrison."""

    if action not in legal_commander_recruit_actions(state, action.actor):
        raise ValueError("action is not a legal Commander recruit")
    player = action.actor
    owner = state.players[player]
    cost = commander_cost(owner)
    next_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari - cost),
        commanders_supply=owner.commanders_supply - 1,
        commanders_garrison=owner.commanders_garrison + 1,
        commander_recruited_turn=True,
    )
    players = replace_player(state.players, next_owner)
    next_state = replace(state, players=players)
    context = _owned_effect_context(state, player)
    if context is not None:
        context["troops_recruited"] = (
            context_int(context, "troops_recruited", owner=_FRAME_LABEL) + 1
        )
        next_state = advance_after_effect(next_state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:recruit_commander:"
            f"{next_owner.commanders_total - next_owner.commanders_supply}"
        ),
        kind="sardaukar_commander_recruited",
        payload=(("player", player), ("solari", cost)),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_skill_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer Desperate's optional trash for three swords in the Reveal turn."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if owned_top_frame(state, FrameKind.REVEAL, player) is None:
        return ()
    owner = state.players[player]
    if owner.commanders_conflict <= 0:
        return ()
    return tuple(
        DomainAction(
            action_id="trash_skill_for_strength",
            actor=player,
            arguments=(("skill_id", _skill_identity(instance_id)),),
        )
        for instance_id in owner.skill_ids
        if skill_for_instance(instance_id).trash_for_strength
    )


def apply_skill_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Trash Desperate for its printed swords during the Reveal turn."""

    if action not in legal_skill_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Skill trash")
    player = action.actor
    owner = state.players[player]
    skill_id = str(dict(action.arguments)["skill_id"])
    instance_id = next(
        candidate
        for candidate in owner.skill_ids
        if _skill_identity(candidate) == skill_id
    )
    swords = SKILLS_BY_ID[skill_id].trash_for_strength
    # A Commander is in the Conflict, so the swords count at once [Main p. 12].
    next_owner = replace(
        owner,
        skill_ids=tuple(
            candidate for candidate in owner.skill_ids if candidate != instance_id
        ),
        combat_strength=owner.combat_strength + swords,
    )
    frames = add_reveal_optional_sword_strength(state.decision_stack, swords)
    frames = add_reveal_strength(frames, swords)
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        skill_trash=(*state.skill_trash, instance_id),
        decision_stack=frames,
    )
    source = f"round:{state.round_number}:player:{player}:skill:{instance_id}"
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:trashed",
                kind="skill_trashed",
                payload=(
                    ("player", player),
                    ("skill_id", skill_id),
                    ("skill_instance_id", instance_id),
                ),
            ),
            GameEvent(
                event_id=f"{source}:strength",
                kind="reveal_strength_gained",
                payload=(("amount", swords), ("player", player)),
            ),
        ),
    )
