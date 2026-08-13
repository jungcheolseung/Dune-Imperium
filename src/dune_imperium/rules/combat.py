"""Pure four-player Combat ranking rules."""

from dataclasses import dataclass, replace
from enum import IntEnum

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID, ConflictReward
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState


class RewardRank(IntEnum):
    """Printed Conflict reward rows."""

    FIRST = 1
    SECOND = 2
    THIRD = 3


@dataclass(frozen=True, slots=True)
class CombatReward:
    """The reward row and multiplier earned by one player."""

    player: int
    rank: RewardRank
    multiplier: int = 1

    def __post_init__(self) -> None:
        if self.player < 0:
            raise ValueError("reward player must not be negative")
        if self.multiplier not in (1, 2):
            raise ValueError("Combat reward multiplier must be one or two")


@dataclass(frozen=True, slots=True)
class CombatRanking:
    """Complete reward assignment and the sole Conflict winner, if any."""

    rewards: tuple[CombatReward, ...]
    winner: int | None

    def __post_init__(self) -> None:
        players = tuple(reward.player for reward in self.rewards)
        if len(players) != len(set(players)):
            raise ValueError("a player cannot receive two Conflict reward rows")
        first = tuple(
            reward.player
            for reward in self.rewards
            if reward.rank is RewardRank.FIRST
        )
        if self.winner is None and first:
            raise ValueError("a first-place reward requires a winner")
        if self.winner is not None and first != (self.winner,):
            raise ValueError("winner must be the sole first-place recipient")


def rank_combat(players: tuple[PlayerState, ...]) -> CombatRanking:
    """Apply the official four-player tie and zero-strength reward rules."""

    if len(players) != 4 or tuple(player.player_id for player in players) != tuple(
        range(4)
    ):
        raise ValueError("Combat ranking requires players in seat order 0 through 3")

    groups = _positive_strength_groups(players)
    if not groups:
        return CombatRanking(rewards=(), winner=None)

    top = groups[0]
    rewards: list[CombatReward] = []
    if len(top) > 1:
        rewards.extend(_rewards(players, top, RewardRank.SECOND))
        if len(top) == 2 and len(groups) > 1 and len(groups[1]) == 1:
            rewards.extend(_rewards(players, groups[1], RewardRank.THIRD))
        return CombatRanking(rewards=tuple(rewards), winner=None)

    winner = top[0]
    rewards.extend(_rewards(players, top, RewardRank.FIRST))
    if len(groups) == 1:
        return CombatRanking(rewards=tuple(rewards), winner=winner)

    second = groups[1]
    if len(second) > 1:
        rewards.extend(_rewards(players, second, RewardRank.THIRD))
        return CombatRanking(rewards=tuple(rewards), winner=winner)

    rewards.extend(_rewards(players, second, RewardRank.SECOND))
    if len(groups) > 2 and len(groups[2]) == 1:
        rewards.extend(_rewards(players, groups[2], RewardRank.THIRD))
    return CombatRanking(rewards=tuple(rewards), winner=winner)


def begin_combat_intrigue(state: GameState) -> RuleResult:
    """Open Combat Intrigue priority at the first eligible seat."""

    if state.phase is not GamePhase.COMBAT:
        raise ValueError("Combat Intrigue can begin only during Combat")
    if state.first_player is None:
        raise ValueError("Combat Intrigue requires a First Player")
    if state.decision_stack:
        raise ValueError("Combat Intrigue cannot begin with a pending decision")
    if state.combat_intrigue_complete:
        raise ValueError("Combat Intrigue is already complete")

    participants = _participants_from(state, state.first_player)
    if any(state.players[player].intrigue_cards for player in participants):
        raise NotImplementedError(
            "Combat Intrigue card eligibility is not transcribed yet"
        )
    if not participants:
        next_state = replace(state, combat_intrigue_complete=True)
        event = GameEvent(
            event_id=f"round:{state.round_number}:combat_intrigue",
            kind="combat_intrigue_finished",
        )
        return RuleResult(state=next_state, events=(event,))

    first = participants[0]
    frame = _combat_intrigue_frame(
        state,
        participants=participants,
        current_index=0,
        consecutive_passes=0,
    )
    next_state = replace(state, decision_stack=(frame,))
    event = GameEvent(
        event_id=f"round:{state.round_number}:combat_intrigue:{first}",
        kind="combat_intrigue_started",
        payload=(("player", first),),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_combat_intrigue_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return pass while Combat Intrigue card play remains unimplemented."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if not frame.frame_id.endswith(":combat_intrigue"):
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    return (DomainAction(action_id="pass_combat_intrigue", actor=player),)


def apply_combat_intrigue_pass(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Record one pass and finish after every participant passes consecutively."""

    if action not in legal_combat_intrigue_actions(state, action.actor):
        raise ValueError("action is not a legal Combat Intrigue pass")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    participants = _participants_from_mask(
        state.config.players,
        _context_int(context, "participants_mask"),
        state.first_player,
    )
    current_index = _context_int(context, "current_index")
    consecutive_passes = _context_int(context, "consecutive_passes") + 1
    if consecutive_passes == len(participants):
        next_state = replace(
            state,
            combat_intrigue_complete=True,
            decision_stack=state.decision_stack[:-1],
        )
        kind = "combat_intrigue_finished"
    else:
        next_index = (current_index + 1) % len(participants)
        next_frame = _combat_intrigue_frame(
            state,
            participants=participants,
            current_index=next_index,
            consecutive_passes=consecutive_passes,
        )
        next_state = replace(
            state,
            decision_stack=(*state.decision_stack[:-1], next_frame),
        )
        kind = "combat_intrigue_passed"
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_intrigue:pass:{action.actor}:"
            f"{consecutive_passes}"
        ),
        kind=kind,
        payload=(("player", action.actor),),
    )
    return RuleResult(state=next_state, events=(event,))


def resolve_tier_one_combat_rewards(state: GameState) -> RuleResult:
    """Apply transcribed Conflict rewards and open any Influence choices."""

    if state.phase is not GamePhase.COMBAT:
        raise ValueError("Combat rewards can resolve only during Combat")
    if not state.combat_intrigue_complete:
        raise ValueError("Combat Intrigue must finish before rewards")
    if state.combat_rewards_resolved:
        raise ValueError("Combat rewards are already resolved")
    if state.decision_stack:
        raise ValueError("Combat rewards cannot resolve with a pending decision")
    if not state.current_conflict_ids:
        raise ValueError("Combat rewards require a current Conflict")

    conflict_id = state.current_conflict_ids[-1]
    conflict = CONFLICTS_BY_ID[conflict_id]
    if conflict.rewards is None:
        raise NotImplementedError(
            f"Conflict rewards are not transcribed: {conflict_id}"
        )

    ranking = rank_combat(state.players)
    intrigue_count = sum(
        conflict.rewards[reward.rank - 1].intrigue * reward.multiplier
        for reward in ranking.rewards
    )
    if intrigue_count > len(state.intrigue_deck):
        raise ValueError("Conflict rewards require more Intrigue cards than remain")

    players = list(state.players)
    intrigue_deck = state.intrigue_deck
    choice_owners: list[int] = []
    events: list[GameEvent] = []
    for assignment in ranking.rewards:
        reward = conflict.rewards[assignment.rank - 1]
        amount = assignment.multiplier
        owner = players[assignment.player]
        drawn = intrigue_deck[: reward.intrigue * amount]
        intrigue_deck = intrigue_deck[len(drawn) :]
        players[assignment.player] = replace(
            owner,
            resources=Resources(
                solari=owner.resources.solari + reward.solari * amount,
                spice=owner.resources.spice + reward.spice * amount,
                water=owner.resources.water,
            ),
            intrigue_cards=(*owner.intrigue_cards, *drawn),
        )
        choice_owners.extend(
            assignment.player for _ in range(reward.choose_influence * amount)
        )
        events.append(
            _combat_reward_event(state, assignment, reward)
        )

    _validate_influence_choices(tuple(players), tuple(choice_owners))
    frames = tuple(
        _influence_choice_frame(state, player, index)
        for index, player in reversed(tuple(enumerate(choice_owners)))
    )
    next_state = replace(
        state,
        players=tuple(players),
        intrigue_deck=intrigue_deck,
        combat_rewards_resolved=not frames,
        decision_stack=frames,
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_combat_reward_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return factions whose Alliance boundary is not reached yet."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_influence:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    influence = state.players[player].influence
    return tuple(
        DomainAction(
            action_id="choose_combat_reward_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if _influence_amount(influence, faction) < 3
    )


def apply_combat_reward_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one queued choose-a-faction Influence reward."""

    if action not in legal_combat_reward_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Combat reward Influence choice")
    faction_value = dict(action.arguments)["faction"]
    if not isinstance(faction_value, str):
        raise RuntimeError("Combat reward Influence choice has invalid faction")
    faction = Faction(faction_value)
    frame = state.decision_stack[-1]
    choice_index = _context_int(dict(frame.context), "choice_index")
    owner = state.players[action.actor]
    current = _influence_amount(owner.influence, faction)
    next_owner = replace(
        owner,
        influence=_replace_influence(owner.influence, faction, current + 1),
        victory_points=owner.victory_points + (1 if current == 1 else 0),
    )
    remaining = state.decision_stack[:-1]
    next_state = replace(
        state,
        players=tuple(
            next_owner if player.player_id == action.actor else player
            for player in state.players
        ),
        decision_stack=remaining,
        combat_rewards_resolved=not remaining,
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_reward:influence:"
            f"{choice_index}:{action.actor}:{faction.value}"
        ),
        kind="influence_gained",
        payload=(("amount", 1), ("faction", faction.value), ("player", action.actor)),
    )
    return RuleResult(state=next_state, events=(event,))


def finish_combat(state: GameState) -> RuleResult:
    """Award the Conflict card, clean up combat units, and enter Makers."""

    if state.phase is not GamePhase.COMBAT:
        raise ValueError("Combat can finish only during Combat")
    if not state.combat_rewards_resolved:
        raise ValueError("Combat rewards must resolve before cleanup")
    if state.decision_stack:
        raise ValueError("Combat cannot finish with a pending decision")
    if not state.current_conflict_ids:
        raise ValueError("Combat cleanup requires a current Conflict")

    conflict_id = state.current_conflict_ids[-1]
    ranking = rank_combat(state.players)
    players = state.players
    current_conflict_ids = state.current_conflict_ids
    events: list[GameEvent] = []
    if ranking.winner is not None:
        winner = players[ranking.winner]
        matched_card_id = _matching_battle_card(winner, conflict_id)
        face_down = winner.face_down_battle_card_ids
        victory_points = winner.victory_points
        if matched_card_id is not None:
            face_down = (*face_down, matched_card_id, conflict_id)
            victory_points += 1
        winner = replace(
            winner,
            victory_points=victory_points,
            won_conflict_ids=(*winner.won_conflict_ids, conflict_id),
            face_down_battle_card_ids=face_down,
        )
        players = tuple(
            winner if player.player_id == ranking.winner else player
            for player in players
        )
        current_conflict_ids = current_conflict_ids[:-1]
        events.append(
            GameEvent(
                event_id=f"round:{state.round_number}:conflict_won:{ranking.winner}",
                kind="conflict_won",
                payload=(("conflict_id", conflict_id), ("player", ranking.winner)),
            )
        )
        if matched_card_id is not None:
            events.append(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:battle_icons_matched:"
                        f"{ranking.winner}"
                    ),
                    kind="battle_icons_matched",
                    payload=(
                        ("first_card_id", matched_card_id),
                        ("player", ranking.winner),
                        ("second_card_id", conflict_id),
                    ),
                )
            )

    players = tuple(
        replace(
            player,
            troops_supply=player.troops_supply + player.troops_conflict,
            troops_conflict=0,
            sandworms_conflict=0,
            combat_strength=0,
        )
        for player in players
    )
    next_state = replace(
        state,
        phase=GamePhase.MAKERS,
        players=players,
        current_conflict_ids=current_conflict_ids,
    )
    events.append(
        GameEvent(
            event_id=f"round:{state.round_number}:combat_cleanup",
            kind="combat_cleaned_up",
        )
    )
    return RuleResult(state=next_state, events=tuple(events))


def _matching_battle_card(player: PlayerState, conflict_id: str) -> str | None:
    battle_icon = CONFLICTS_BY_ID[conflict_id].battle_icon
    if battle_icon is None:
        raise NotImplementedError(
            f"Conflict battle icon is not transcribed: {conflict_id}"
        )
    face_up = (
        card_id
        for card_id in (*player.objective_ids, *player.won_conflict_ids)
        if card_id not in player.face_down_battle_card_ids
    )
    matches = tuple(
        card_id
        for card_id in face_up
        if _battle_icon_for(card_id) is battle_icon
    )
    if len(matches) > 1:
        raise NotImplementedError("choosing among matching battle icons is unresolved")
    return matches[0] if matches else None


def _battle_icon_for(card_id: str) -> BattleIcon:
    if card_id in OBJECTIVES_BY_ID:
        return OBJECTIVES_BY_ID[card_id].battle_icon
    battle_icon = CONFLICTS_BY_ID[card_id].battle_icon
    if battle_icon is None:
        raise NotImplementedError(f"Conflict battle icon is not transcribed: {card_id}")
    return battle_icon


def _combat_reward_event(
    state: GameState,
    assignment: CombatReward,
    reward: ConflictReward,
) -> GameEvent:
    return GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_reward:{assignment.player}:"
            f"{assignment.rank.value}"
        ),
        kind="combat_reward_gained",
        payload=(
            ("choose_influence", reward.choose_influence * assignment.multiplier),
            ("intrigue", reward.intrigue * assignment.multiplier),
            ("multiplier", assignment.multiplier),
            ("player", assignment.player),
            ("rank", assignment.rank.value),
            ("solari", reward.solari * assignment.multiplier),
            ("spice", reward.spice * assignment.multiplier),
        ),
    )


def _validate_influence_choices(
    players: tuple[PlayerState, ...],
    choice_owners: tuple[int, ...],
) -> None:
    for player in players:
        required = choice_owners.count(player.player_id)
        capacity = sum(
            max(0, 3 - _influence_amount(player.influence, faction))
            for faction in Faction
        )
        if required > capacity:
            raise NotImplementedError(
                "Influence 4 bonuses and Alliances are not implemented"
            )


def _influence_choice_frame(
    state: GameState,
    player: int,
    index: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=(
            f"round:{state.round_number}:combat_reward_influence:{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt="Choose a faction to gain one Influence",
        ),
        context=(("choice_index", index), ("player", player)),
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


def _positive_strength_groups(
    players: tuple[PlayerState, ...],
) -> tuple[tuple[int, ...], ...]:
    strengths = sorted(
        {player.combat_strength for player in players if player.combat_strength > 0},
        reverse=True,
    )
    return tuple(
        tuple(
            player.player_id
            for player in players
            if player.combat_strength == strength
        )
        for strength in strengths
    )


def _participants_from(state: GameState, first_player: int) -> tuple[int, ...]:
    return tuple(
        player
        for offset in range(state.config.players)
        if _has_conflict_units(
            state.players[player := (first_player + offset) % state.config.players]
        )
    )


def _has_conflict_units(player: PlayerState) -> bool:
    return player.troops_conflict + player.sandworms_conflict > 0


def _participants_from_mask(
    players: int,
    mask: int,
    first_player: int | None,
) -> tuple[int, ...]:
    if first_player is None:
        raise RuntimeError("Combat Intrigue frame requires a First Player")
    return tuple(
        player
        for offset in range(players)
        if mask & (1 << (player := (first_player + offset) % players))
    )


def _combat_intrigue_frame(
    state: GameState,
    participants: tuple[int, ...],
    current_index: int,
    consecutive_passes: int,
) -> DecisionFrame:
    mask = sum(1 << player for player in participants)
    return DecisionFrame(
        frame_id=f"round:{state.round_number}:combat_intrigue",
        decision=PlayerDecision(
            owner=participants[current_index],
            prompt="Play Combat Intrigue cards or pass",
        ),
        context=(
            ("consecutive_passes", consecutive_passes),
            ("current_index", current_index),
            ("participants_mask", mask),
        ),
    )


def _context_int(context: dict[str, bool | int | str], key: str) -> int:
    value = context.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"Combat Intrigue frame has invalid {key}")
    return value


def _rewards(
    players: tuple[PlayerState, ...],
    recipients: tuple[int, ...],
    rank: RewardRank,
) -> tuple[CombatReward, ...]:
    return tuple(
        CombatReward(
            player=player,
            rank=rank,
            multiplier=2 if players[player].sandworms_conflict > 0 else 1,
        )
        for player in recipients
    )
