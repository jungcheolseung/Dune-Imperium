"""Pure four-player Combat ranking rules."""

from dataclasses import dataclass, replace
from enum import IntEnum

from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID, ConflictReward
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    gain_faction_influence,
    influence_amount,
)


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
    """Return pass while individual Combat Intrigue effects remain deferred."""

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


def resolve_combat_rewards(state: GameState) -> RuleResult:
    """Apply supported Conflict rewards and open any Influence choices."""

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
    _validate_supported_rewards(state, ranking, conflict.rewards)
    intrigue_count = sum(
        conflict.rewards[reward.rank - 1].intrigue * reward.multiplier
        for reward in ranking.rewards
    )
    if intrigue_count > len(state.intrigue_deck):
        raise ValueError("Conflict rewards require more Intrigue cards than remain")

    players = list(state.players)
    intrigue_deck = state.intrigue_deck
    choice_owners: list[int] = []
    frames_in_order: list[DecisionFrame] = []
    events: list[GameEvent] = []
    for assignment in ranking.rewards:
        reward = conflict.rewards[assignment.rank - 1]
        amount = assignment.multiplier
        owner = players[assignment.player]
        drawn = intrigue_deck[: reward.intrigue * amount]
        intrigue_deck = intrigue_deck[len(drawn) :]
        contract_solari = 0 if state.config.choam_module else reward.contracts * 2
        recruited = min(owner.troops_supply, reward.troops * amount)
        next_owner = replace(
            owner,
            resources=Resources(
                solari=(
                    owner.resources.solari
                    + reward.solari * amount
                    + contract_solari * amount
                ),
                spice=owner.resources.spice + reward.spice * amount,
                water=owner.resources.water + reward.water * amount,
            ),
            troops_supply=owner.troops_supply - recruited,
            troops_garrison=owner.troops_garrison + recruited,
            intrigue_cards=(*owner.intrigue_cards, *drawn),
            victory_points=owner.victory_points + reward.victory_points * amount,
        )
        players[assignment.player] = next_owner
        if reward.influence_faction is not None:
            influence_result = gain_faction_influence(
                replace(
                    state,
                    players=tuple(players),
                    intrigue_deck=intrigue_deck,
                ),
                assignment.player,
                reward.influence_faction,
                reward.faction_influence * amount,
                event_prefix=(
                    f"round:{state.round_number}:combat_reward:fixed_influence:"
                    f"{assignment.player}:{assignment.rank.value}"
                ),
            )
            players = list(influence_result.state.players)
            intrigue_deck = influence_result.state.intrigue_deck
            events.extend(influence_result.events)
            next_owner = players[assignment.player]
        if reward.control_space_id is not None:
            players = list(
                _apply_control(
                    tuple(players),
                    assignment.player,
                    reward.control_space_id,
                )
            )
        for _ in range(amount):
            for _ in range(reward.choose_influence):
                choice_owners.append(assignment.player)
                frames_in_order.append(
                    _influence_choice_frame(
                        state,
                        assignment.player,
                        len(frames_in_order),
                    )
                )
            if reward.optional_spice_cost:
                frames_in_order.append(
                    _optional_payment_frame(
                        state,
                        assignment.player,
                        len(frames_in_order),
                        "spice",
                        reward.optional_spice_cost,
                        reward.optional_victory_points,
                    )
                )
            if reward.optional_solari_cost:
                frames_in_order.append(
                    _optional_payment_frame(
                        state,
                        assignment.player,
                        len(frames_in_order),
                        "solari",
                        reward.optional_solari_cost,
                        reward.optional_victory_points,
                    )
                )
            if reward.optional_recall_spies:
                frames_in_order.append(
                    _optional_spy_recall_frame(
                        state,
                        assignment.player,
                        len(frames_in_order),
                        reward.optional_recall_spies,
                        reward.optional_victory_points,
                    )
                )
            if reward.choose_distinct_influence:
                group = len(frames_in_order)
                for _ in range(reward.choose_distinct_influence):
                    frames_in_order.append(
                        _distinct_influence_frame(
                            state,
                            assignment.player,
                            len(frames_in_order),
                            group,
                        )
                    )
        trash_candidates = (
            *next_owner.hand,
            *next_owner.discard_pile,
            *next_owner.in_play,
        )
        trash_count = reward.trash_cards * amount if trash_candidates else 0
        for _ in range(trash_count):
            frames_in_order.append(
                _trash_card_frame(
                    state,
                    assignment.player,
                    len(frames_in_order),
                )
            )
        occupied_posts = {
            post_id for player in players for post_id in player.spy_post_ids
        }
        spy_count = min(
            reward.place_spies * amount,
            next_owner.spies_supply,
            len(OBSERVATION_POSTS) - len(occupied_posts),
        )
        for _ in range(spy_count):
            frames_in_order.append(
                _spy_placement_frame(
                    state,
                    assignment.player,
                    len(frames_in_order),
                )
            )
        events.append(
            _combat_reward_event(state, assignment, reward)
        )

    _validate_influence_choices(tuple(players), tuple(choice_owners))
    frames = tuple(reversed(frames_in_order))
    next_state = replace(
        state,
        players=tuple(players),
        intrigue_deck=intrigue_deck,
        combat_rewards_resolved=not frames,
        decision_stack=frames,
    )
    return RuleResult(state=next_state, events=tuple(events))


def legal_combat_reward_optional_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline and, when affordable, pay for an optional reward."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_optional:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    context = dict(frame.context)
    cost = _context_int(context, "cost")
    resource = context.get("resource")
    if resource not in ("solari", "spice"):
        raise RuntimeError("optional Combat reward has invalid resource")
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    if getattr(state.players[player].resources, resource) >= cost:
        actions.append(DomainAction(action_id="pay_combat_reward", actor=player))
    return tuple(actions)


def apply_combat_reward_optional_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pay for or decline one optional Conflict reward."""

    if action not in legal_combat_reward_optional_payment_actions(
        state, action.actor
    ):
        raise ValueError("action is not a legal optional Combat reward choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    choice_index = _context_int(context, "choice_index")
    cost = _context_int(context, "cost")
    resource = context.get("resource")
    if resource not in ("solari", "spice"):
        raise RuntimeError("optional Combat reward has invalid resource")
    victory_points = _context_int(context, "victory_points")
    paid = action.action_id == "pay_combat_reward"
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            **{
                resource: getattr(owner.resources, resource) - (cost if paid else 0)
            },
        ),
        victory_points=owner.victory_points + (victory_points if paid else 0),
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
            f"round:{state.round_number}:combat_reward:optional:"
            f"{choice_index}:{action.actor}"
        ),
        kind=("combat_reward_paid" if paid else "combat_reward_declined"),
        payload=(
            ("cost", cost if paid else 0),
            ("player", action.actor),
            ("resource", resource),
            ("victory_points", victory_points if paid else 0),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_combat_reward_spy_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline plus every payable pair of placed Spies."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_spy_recall:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    count = _context_int(dict(frame.context), "spy_count")
    posts = state.players[player].spy_post_ids
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    if count != 2:
        raise NotImplementedError("only a two-Spy Combat reward cost is supported")
    actions.extend(
        DomainAction(
            action_id="recall_spies_for_combat_reward",
            actor=player,
            arguments=(
                ("first_post_id", posts[first]),
                ("second_post_id", posts[second]),
            ),
        )
        for first in range(len(posts))
        for second in range(first + 1, len(posts))
    )
    return tuple(actions)


def apply_combat_reward_spy_recall(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall a selected Spy pair or decline the optional VP reward."""

    if action not in legal_combat_reward_spy_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Combat reward Spy recall")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    choice_index = _context_int(context, "choice_index")
    spy_count = _context_int(context, "spy_count")
    victory_points = _context_int(context, "victory_points")
    paid = action.action_id == "recall_spies_for_combat_reward"
    recalled = (
        {
            str(dict(action.arguments)["first_post_id"]),
            str(dict(action.arguments)["second_post_id"]),
        }
        if paid
        else set()
    )
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        spies_supply=owner.spies_supply + (spy_count if paid else 0),
        spy_post_ids=tuple(
            post_id for post_id in owner.spy_post_ids if post_id not in recalled
        ),
        victory_points=owner.victory_points + (victory_points if paid else 0),
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
            f"round:{state.round_number}:combat_reward:spy_recall:"
            f"{choice_index}:{action.actor}"
        ),
        kind=("spies_recalled" if paid else "combat_reward_declined"),
        payload=(
            ("player", action.actor),
            ("spies", spy_count if paid else 0),
            ("victory_points", victory_points if paid else 0),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_combat_reward_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline plus eligible hand, discard, and in-play cards."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_trash:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    owner = state.players[player]
    return (
        DomainAction(action_id="decline_combat_reward_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_combat_reward_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in (*owner.hand, *owner.discard_pile, *owner.in_play)
        ),
    )


def apply_combat_reward_trash(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Trash one selected Imperium card for a Conflict reward."""

    if action not in legal_combat_reward_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Combat reward trash choice")
    frame = state.decision_stack[-1]
    choice_index = _context_int(dict(frame.context), "choice_index")
    declined = action.action_id == "decline_combat_reward_trash"
    events: tuple[GameEvent, ...]
    if declined:
        card_id = ""
        working_state = state
        events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:combat_reward:trash:"
                    f"{choice_index}:{action.actor}"
                ),
                kind="combat_reward_trash_declined",
                payload=(("card_id", card_id), ("player", action.actor)),
            ),
        )
    else:
        card_value = dict(action.arguments)["card_id"]
        if not isinstance(card_value, str):
            raise RuntimeError("Combat reward trash choice has invalid card ID")
        card_id = card_value
        trashed = trash_personal_card(
            state,
            action.actor,
            card_id,
            source=(
                f"round:{state.round_number}:combat_reward:trash:"
                f"{choice_index}:{action.actor}"
            ),
        )
        working_state = trashed.state
        events = trashed.events
    remaining = working_state.decision_stack[:-1]
    next_state = replace(
        working_state,
        decision_stack=remaining,
        combat_rewards_resolved=not remaining,
    )
    return RuleResult(state=next_state, events=events)


def legal_combat_reward_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return currently empty Observation Posts for a Conflict reward."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_spy:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    if state.players[player].spies_supply == 0:
        return ()
    occupied = {
        post_id for owner in state.players for post_id in owner.spy_post_ids
    }
    return tuple(
        DomainAction(
            action_id="place_combat_reward_spy",
            actor=player,
            arguments=(("post_id", post.post_id),),
        )
        for post in OBSERVATION_POSTS
        if post.post_id not in occupied
    )


def apply_combat_reward_spy(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Place one Spy from supply on a selected empty Observation Post."""

    if action not in legal_combat_reward_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Combat reward Spy placement")
    post_id = dict(action.arguments)["post_id"]
    if not isinstance(post_id, str):
        raise RuntimeError("Combat reward Spy placement has invalid post ID")
    frame = state.decision_stack[-1]
    choice_index = _context_int(dict(frame.context), "choice_index")
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        spies_supply=owner.spies_supply - 1,
        spy_post_ids=(*owner.spy_post_ids, post_id),
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
            f"round:{state.round_number}:combat_reward:spy:"
            f"{choice_index}:{action.actor}:{post_id}"
        ),
        kind="spy_placed",
        payload=(("player", action.actor), ("post_id", post_id)),
    )
    return RuleResult(state=next_state, events=(event,))


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
        if influence_amount(influence, faction) < MAX_INFLUENCE
        and not (
            faction is Faction.BENE_GESSERIT
            and influence_amount(influence, faction) == 3
            and not state.intrigue_deck
        )
    )


def legal_distinct_combat_reward_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return unchosen factions for one choose-distinct Influence group."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":combat_reward_distinct_influence:" not in frame.frame_id:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    context = dict(frame.context)
    chosen_mask = _context_int(context, "chosen_mask")
    influence = state.players[player].influence
    return tuple(
        DomainAction(
            action_id="choose_distinct_combat_reward_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for index, faction in enumerate(Faction)
        if not chosen_mask & (1 << index)
        and influence_amount(influence, faction) < MAX_INFLUENCE
        and not (
            faction is Faction.BENE_GESSERIT
            and influence_amount(influence, faction) == 3
            and not state.intrigue_deck
        )
    )


def apply_distinct_combat_reward_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain one Influence and exclude that faction within the current group."""

    if action not in legal_distinct_combat_reward_influence_actions(
        state, action.actor
    ):
        raise ValueError("action is not a legal distinct Influence choice")
    faction_value = dict(action.arguments)["faction"]
    if not isinstance(faction_value, str):
        raise RuntimeError("distinct Influence choice has invalid faction")
    faction = Faction(faction_value)
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    choice_index = _context_int(context, "choice_index")
    group = _context_int(context, "group")
    chosen_mask = _context_int(context, "chosen_mask")
    faction_index = tuple(Faction).index(faction)
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:combat_reward:distinct_influence:"
            f"{choice_index}:{action.actor}:{faction.value}"
        ),
    )
    remaining = state.decision_stack[:-1]
    if remaining and _frame_context_int(remaining[-1], "group") == group:
        next_context = dict(remaining[-1].context)
        next_context["chosen_mask"] = chosen_mask | (1 << faction_index)
        remaining = (*remaining[:-1], replace(
            remaining[-1], context=tuple(sorted(next_context.items()))
        ))
    next_state = replace(
        gained.state,
        decision_stack=remaining,
        combat_rewards_resolved=not remaining,
    )
    return RuleResult(state=next_state, events=gained.events)


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
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:combat_reward:influence:"
            f"{choice_index}:{action.actor}:{faction.value}"
        ),
    )
    remaining = state.decision_stack[:-1]
    next_state = replace(
        gained.state,
        decision_stack=remaining,
        combat_rewards_resolved=not remaining,
    )
    return RuleResult(state=next_state, events=gained.events)


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
    contract_solari = (
        0 if state.config.choam_module else reward.contracts * 2
    )
    return GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_reward:{assignment.player}:"
            f"{assignment.rank.value}"
        ),
        kind="combat_reward_gained",
        payload=(
            ("choose_influence", reward.choose_influence * assignment.multiplier),
            ("contracts", reward.contracts * assignment.multiplier),
            ("control_space_id", reward.control_space_id or ""),
            (
                "faction",
                reward.influence_faction.value
                if reward.influence_faction is not None
                else "",
            ),
            (
                "faction_influence",
                reward.faction_influence * assignment.multiplier,
            ),
            ("intrigue", reward.intrigue * assignment.multiplier),
            ("multiplier", assignment.multiplier),
            ("player", assignment.player),
            ("rank", assignment.rank.value),
            (
                "solari",
                (reward.solari + contract_solari) * assignment.multiplier,
            ),
            ("spice", reward.spice * assignment.multiplier),
            ("troops", reward.troops * assignment.multiplier),
            ("water", reward.water * assignment.multiplier),
        ),
    )


def _validate_supported_rewards(
    state: GameState,
    ranking: CombatRanking,
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward],
) -> None:
    for assignment in ranking.rewards:
        reward = rewards[assignment.rank - 1]
        unsupported: list[str] = []
        if reward.contracts and state.config.choam_module:
            unsupported.append("CHOAM contract selection")
        if unsupported:
            raise NotImplementedError(
                "Combat reward choices are not implemented: " + ", ".join(unsupported)
            )

        if reward.choose_distinct_influence:
            influence = state.players[assignment.player].influence
            available = sum(
                influence_amount(influence, faction) < MAX_INFLUENCE
                for faction in Faction
            )
            capacity = sum(
                max(0, MAX_INFLUENCE - influence_amount(influence, faction))
                for faction in Faction
            )
            required = reward.choose_distinct_influence * assignment.multiplier
            if available < reward.choose_distinct_influence or capacity < required:
                raise NotImplementedError(
                    "Influence 4 bonuses and Alliances are not implemented"
                )

def _apply_control(
    players: tuple[PlayerState, ...],
    winner: int,
    space_id: str,
) -> tuple[PlayerState, ...]:
    owner = players[winner]
    if space_id in owner.control_space_ids or len(owner.control_space_ids) == 3:
        return players
    return tuple(
        replace(
            player,
            control_space_ids=(
                (*player.control_space_ids, space_id)
                if player.player_id == winner
                else tuple(
                    controlled
                    for controlled in player.control_space_ids
                    if controlled != space_id
                )
            ),
        )
        for player in players
    )


def _validate_influence_choices(
    players: tuple[PlayerState, ...],
    choice_owners: tuple[int, ...],
) -> None:
    for player in players:
        required = choice_owners.count(player.player_id)
        capacity = sum(
            max(0, MAX_INFLUENCE - influence_amount(player.influence, faction))
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


def _optional_payment_frame(
    state: GameState,
    player: int,
    index: int,
    resource: str,
    cost: int,
    victory_points: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=(
            f"round:{state.round_number}:combat_reward_optional:{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt=(
                f"Pay {cost} {resource.title()} to gain "
                f"{victory_points} Victory Point"
            ),
        ),
        context=(
            ("choice_index", index),
            ("cost", cost),
            ("player", player),
            ("resource", resource),
            ("victory_points", victory_points),
        ),
    )


def _optional_spy_recall_frame(
    state: GameState,
    player: int,
    index: int,
    spy_count: int,
    victory_points: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=(
            f"round:{state.round_number}:combat_reward_spy_recall:{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt=(
                f"Recall {spy_count} placed Spies to gain "
                f"{victory_points} Victory Point"
            ),
        ),
        context=(
            ("choice_index", index),
            ("player", player),
            ("spy_count", spy_count),
            ("victory_points", victory_points),
        ),
    )


def _distinct_influence_frame(
    state: GameState,
    player: int,
    index: int,
    group: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=(
            f"round:{state.round_number}:combat_reward_distinct_influence:"
            f"{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt="Choose a different faction to gain one Influence",
        ),
        context=(
            ("choice_index", index),
            ("chosen_mask", 0),
            ("group", group),
            ("player", player),
        ),
    )


def _trash_card_frame(
    state: GameState,
    player: int,
    index: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=f"round:{state.round_number}:combat_reward_trash:{index}:{player}",
        decision=PlayerDecision(
            owner=player,
            prompt=(
                "Trash an Imperium card from your hand, discard pile, or in play, "
                "or decline"
            ),
        ),
        context=(("choice_index", index), ("player", player)),
    )


def _spy_placement_frame(
    state: GameState,
    player: int,
    index: int,
) -> DecisionFrame:
    return DecisionFrame(
        frame_id=f"round:{state.round_number}:combat_reward_spy:{index}:{player}",
        decision=PlayerDecision(
            owner=player,
            prompt="Choose an empty Observation Post for your Spy",
        ),
        context=(("choice_index", index), ("player", player)),
    )




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


def _frame_context_int(frame: DecisionFrame, key: str) -> int | None:
    value = dict(frame.context).get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


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
