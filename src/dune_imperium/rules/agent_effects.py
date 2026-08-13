"""Resolution of starting-card and Faction Agent-turn effects."""

from dataclasses import replace

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.starting_cards import (
    StartingCardAgentEffect,
    starting_card_for_instance,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence, PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
)


def resolve_agent_card_effect(state: GameState) -> RuleResult:
    """Resolve the supported Agent box in the current effect frame."""

    _, context = current_agent_effect_context(state)
    if context["pending_agent_effect"] is not True:
        raise ValueError("the current Agent turn has no pending card effect")
    player, card_instance_id, _ = _effect_subject(context)
    card = starting_card_for_instance(card_instance_id)
    if card.agent_effect is not StartingCardAgentEffect.TRASH_SELF:
        raise NotImplementedError(
            f"starting-card Agent effect is not implemented: {card.card.card_id}"
        )

    owner = state.players[player]
    next_owner = replace(
        owner,
        in_play=tuple(
            card_id for card_id in owner.in_play if card_id != card_instance_id
        ),
        trashed=(*owner.trashed, card_instance_id),
    )
    players = _replace_player(state, next_owner)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{player}:trash:{card_instance_id}",
        kind="card_trashed",
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    return RuleResult(state=next_state, events=(event,))


def resolve_faction_influence(state: GameState) -> RuleResult:
    """Gain the visited Faction's Influence through the Friendship boundary."""

    _, context = current_agent_effect_context(state)
    if context["pending_faction_influence"] is not True:
        raise ValueError("the current Agent turn has no pending Faction Influence")
    player, _, space_id = _effect_subject(context)
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is None:
        raise RuntimeError("pending Faction Influence requires a Faction space")

    owner = state.players[player]
    current = _influence_amount(owner.influence, faction)
    if current >= 3:
        raise NotImplementedError(
            "Influence 4 bonuses and Alliances are not implemented"
        )
    influence = _replace_influence(owner.influence, faction, current + 1)
    friendship_vp = 1 if current == 1 else 0
    next_owner = replace(
        owner,
        influence=influence,
        victory_points=owner.victory_points + friendship_vp,
    )
    players = _replace_player(state, next_owner)
    context["pending_faction_influence"] = False
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:influence:{faction.value}"
        ),
        kind="influence_gained",
        payload=(
            ("amount", 1),
            ("faction", faction.value),
            ("player", player),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def _effect_subject(context: dict[str, bool | int | str]) -> tuple[int, str, str]:
    player = context["turn_owner"]
    card_id = context["card_id"]
    space_id = context["space_id"]
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or not isinstance(card_id, str)
        or not isinstance(space_id, str)
    ):
        raise RuntimeError("Agent-turn effect frame has invalid subject")
    return player, card_id, space_id


def _replace_player(
    state: GameState,
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in state.players
    )


def _influence_amount(influence: Influence, faction: Faction) -> int:
    match faction:
        case Faction.EMPEROR:
            return influence.emperor
        case Faction.SPACING_GUILD:
            return influence.spacing_guild
        case Faction.BENE_GESSERIT:
            return influence.bene_gesserit
        case Faction.FREMEN:
            return influence.fremen


def _replace_influence(
    influence: Influence,
    faction: Faction,
    amount: int,
) -> Influence:
    match faction:
        case Faction.EMPEROR:
            return replace(influence, emperor=amount)
        case Faction.SPACING_GUILD:
            return replace(influence, spacing_guild=amount)
        case Faction.BENE_GESSERIT:
            return replace(influence, bene_gesserit=amount)
        case Faction.FREMEN:
            return replace(influence, fremen=amount)
