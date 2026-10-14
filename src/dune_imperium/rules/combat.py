"""Pure four-player Combat ranking rules."""

from copy import replace
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID, ConflictReward
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTleilaxuCard,
    GenerateSpecimens,
    IntrigueOption,
    OnTroopsLostAtConflictEnd,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.contracts import contract_choice_frame
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    frame_context_int,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    gain_faction_influence,
    influence_amount,
)
from dune_imperium.rules.ornithopter import (
    has_ornithopter_fleet,
    match_all_battle_icons,
)
from dune_imperium.rules.pauses import REWARDS, push_pause
from dune_imperium.rules.scouts_missions import free_prison_marker
from dune_imperium.rules.spy_placement import recall_spy
from dune_imperium.rules.tactics import advance_tactics_token

if TYPE_CHECKING:
    # Typing only: effect_interpreter's own imports reach this module, so
    # its functions are imported where they are called.
    from dune_imperium.rules.effect_interpreter import OptionUnplayable


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
            reward.player for reward in self.rewards if reward.rank is RewardRank.FIRST
        )
        if self.winner is None and first:
            raise ValueError("a first-place reward requires a winner")
        if self.winner is not None and first != (self.winner,):
            raise ValueError("winner must be the sole first-place recipient")


def rank_combat(
    players: tuple[PlayerState, ...],
    *,
    first_player: int | None = None,
) -> CombatRanking:
    """Apply the official four-player tie and zero-strength reward rules.

    Players sharing a reward line are listed in turn order from the First
    Player when one is given (designer ruling, OQ-002), else by seat.
    """

    if len(players) != 4 or tuple(player.player_id for player in players) != tuple(
        range(4)
    ):
        raise ValueError("Combat ranking requires players in seat order 0 through 3")

    groups = _positive_strength_groups(players, first_player)
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


COMBAT_INTRIGUE_PLAYED_KEY = "played_at_priority"
"""Set on the Combat Intrigue frame (absent means not) once its owner has
played a Combat Intrigue card since priority last came to it. Such a seat's
opportunity was to play cards, so its pass only hands priority on and does
not count as one of the consecutive passes [Main pp. 14-15]. The frame is
rebuilt without it whenever priority moves to another seat."""


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
    if frame.kind != FrameKind.COMBAT_INTRIGUE:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    return (DomainAction(action_id="pass_combat_intrigue", actor=player),)


def apply_combat_intrigue_pass(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Record one pass and finish after every participant passes consecutively.

    A pass by a seat that played a Combat Intrigue card since priority last
    came to it only hands priority on: it is not one of the consecutive
    passes (``COMBAT_INTRIGUE_PLAYED_KEY``), unless the seat is the only
    participant.
    """

    if action not in legal_combat_intrigue_actions(state, action.actor):
        raise ValueError("action is not a legal Combat Intrigue pass")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    participants = _participants_from_mask(
        state.config.players,
        context_int(context, "participants_mask"),
        state.first_player,
    )
    current_index = context_int(context, "current_index")
    if context.get(COMBAT_INTRIGUE_PLAYED_KEY) and len(participants) > 1:
        # "each player with at least one unit in the Conflict may play any
        # number of Combat Intrigue cards, or may pass. ... Once all players
        # involved in Combat pass consecutively, you then resolve the
        # Combat." [Main p. 14]; in the worked example Abby plays, John
        # passes again, and Abby still decides last [Main p. 15]. A seat
        # that played this opportunity hands priority on without passing.
        # A lone participant's next opportunity would be its own again with
        # nothing in between, so its pass after playing is the final one.
        consecutive_passes = 0
    else:
        consecutive_passes = context_int(context, "consecutive_passes") + 1
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
    """Pay the next ranked recipient's Conflict reward and open its choices.

    The engine calls this whenever the stack is empty and the rewards are
    not resolved. A call after a recipient has been paid, before the next
    one is, pauses first (``rules/pauses.py``): the previous recipient's
    choices are done, and paying the next one can reveal a card (its
    Intrigue draw). The pause's answer runs ``pay_combat_rewards``.
    """

    _check_combat_rewards(state)
    ranking = rank_combat(state.players, first_player=state.first_player)
    if 0 < state.combat_rewards_paid < len(ranking.rewards):
        where = f"round:{state.round_number}:reward:{state.combat_rewards_paid}"
        return push_pause(state, REWARDS, where)
    return pay_combat_rewards(state)


def _check_combat_rewards(state: GameState) -> None:
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


def pay_combat_rewards(state: GameState) -> RuleResult:
    """Pay the ranked recipients from the next one on, until one stops.

    The first payment logs the whole standing (``combat_standing``).
    """

    _check_combat_rewards(state)
    conflict_id = state.current_conflict_ids[-1]
    conflict = CONFLICTS_BY_ID[conflict_id]
    if conflict.rewards is None:
        raise NotImplementedError(
            f"Conflict rewards are not transcribed: {conflict_id}"
        )
    rewards = conflict.rewards

    events: list[GameEvent] = []
    if state.combat_rewards_paid == 0:
        events.extend(_combat_standing_events(state, conflict_id))
    while True:
        ranking = rank_combat(state.players, first_player=state.first_player)
        if state.combat_rewards_paid >= len(ranking.rewards):
            # Every recipient's reward, with its choices, is handed out.
            state = replace(
                state,
                combat_rewards_resolved=True,
                conflict_first_place_influence_bonus=0,
            )
            break
        # One recipient at a time, in rank order (tied recipients from the
        # First Player, OQ-002): its whole reward, automatic parts and
        # choices alike, sandworm copy included, is answered before the next
        # recipient is paid (user ruling 2026-10-07, "순위대로 (앱처럼)"; the
        # official text gives the rewards by rank [Main p. 14] but not the
        # order between them). A recipient that opens a choice or queues a
        # step (an owed Intrigue draw, a track Spy) stops here; the engine
        # calls again once those are answered.
        queued = _reward_queues(state)
        paid = _pay_next_combat_reward(
            state, rewards, ranking.rewards[state.combat_rewards_paid]
        )
        state = paid.state
        events.extend(paid.events)
        if state.decision_stack or _reward_queues(state) != queued:
            break
    return RuleResult(state=state, events=tuple(events))


def _combat_standing_events(
    state: GameState, conflict_id: str
) -> tuple[GameEvent, ...]:
    """The Combat's final standing, one public event per seat in it.

    Emitted once, as the rewards begin: the reward rows are paid one
    recipient at a time, and the strengths are gone after cleanup, so the
    log carries the whole standing here for the table to show ("전투 단계
    종료 때 전투 최종 순위도 그렇게 보여지면 좋겠고", user, 2026-10-08).
    Recipients come in ``rank_combat``'s order with their rank and
    sandworm multiplier; every other seat with strength or units in the
    Conflict follows with rank 0, by strength and then in turn order from
    the First Player. Strength and units in the Conflict are public, so the
    events tell no seat anything new.
    """

    players = state.players
    ranking = rank_combat(players, first_player=state.first_player)
    rewarded = {reward.player for reward in ranking.rewards}
    first = state.first_player or 0
    seats = len(players)
    turn_order = tuple((first + offset) % seats for offset in range(seats))
    others = sorted(
        (
            seat
            for seat in turn_order
            if seat not in rewarded
            and (players[seat].combat_strength or players[seat].units_in_conflict)
        ),
        key=lambda seat: -players[seat].combat_strength,
    )
    standing = [
        (reward.player, reward.rank.value, reward.multiplier)
        for reward in ranking.rewards
    ] + [(seat, 0, 1) for seat in others]
    return tuple(
        GameEvent(
            event_id=f"round:{state.round_number}:combat_standing:{seat}",
            kind="combat_standing",
            payload=(
                ("conflict_id", conflict_id),
                ("multiplier", multiplier),
                ("player", seat),
                ("rank", rank),
                ("strength", players[seat].combat_strength),
            ),
        )
        for seat, rank, multiplier in standing
    )


def combat_rewards_done(
    state: GameState, remaining: tuple[DecisionFrame, ...]
) -> bool:
    """``combat_rewards_resolved`` once ``remaining`` is the whole stack.

    The rewards are resolved when no frame is left and every ranked
    recipient has been paid (``resolve_combat_rewards`` pays them one at a
    time, user ruling 2026-10-07); a recipient's last frame closing before
    that leaves the next recipient for the engine to pay.
    """

    if state.combat_rewards_resolved:
        return True
    if (
        remaining
        or state.phase is not GamePhase.COMBAT
        or not state.combat_intrigue_complete
        or not state.current_conflict_ids
    ):
        return False
    ranking = rank_combat(state.players, first_player=state.first_player)
    return state.combat_rewards_paid >= len(ranking.rewards)


def _reward_queues(state: GameState) -> tuple[object, ...]:
    """The queued steps a Conflict reward can add to (compared, not read)."""

    return (
        state.pending_intrigue_draws,
        state.pending_navigation_plays,
        state.pending_track_spies,
        state.pending_skill_choices,
        state.scouts_four_bonus_choices,
    )


def _pay_next_combat_reward(
    state: GameState,
    rewards: tuple[ConflictReward, ConflictReward, ConflictReward],
    assignment: CombatReward,
) -> RuleResult:
    """Pay one ranked recipient's reward and push its choice frames."""

    paid = state.combat_rewards_paid
    players = list(state.players)
    scouts_goods = state.scouts_goods
    intrigue_deck = state.intrigue_deck
    pending_draws = state.pending_intrigue_draws
    # The queues an Influence gain may add to (Navigation plays at 2, the
    # Emperor track's Spy at 4) travel with the rewards like the owed draws.
    pending_navigation = state.pending_navigation_plays
    pending_spies = state.pending_track_spies
    # Friends Everywhere's Influence 4 choices (Arrakeen Scouts) likewise.
    pending_four = state.scouts_four_bonus_choices
    frames_in_order: list[DecisionFrame] = []
    events: list[GameEvent] = []
    reward = rewards[assignment.rank - 1]
    if (
        assignment.rank is RewardRank.FIRST
        and state.conflict_first_place_influence_bonus
    ):
        # Pivotal Gambit (promo) adds "gain 1 Influence of your choice"
        # to this Conflict's first-place reward (OQ-025); like the
        # printed reward it is doubled by a sandworm [Main p. 14].
        reward = replace(
            reward,
            choose_influence=(
                reward.choose_influence + state.conflict_first_place_influence_bonus
            ),
        )
    amount = assignment.multiplier
    owner = players[assignment.player]
    drawn = intrigue_deck[: reward.intrigue * amount]
    intrigue_deck = intrigue_deck[len(drawn) :]
    if reward.intrigue * amount > len(drawn):
        # Deck exhausted: the dispatcher reshuffles the discard [FAQ p. 2].
        pending_draws = (
            *pending_draws,
            (
                assignment.player,
                reward.intrigue * amount - len(drawn),
                (
                    f"round:{state.round_number}:combat_reward:intrigue:"
                    f"{assignment.player}:{assignment.rank.value}"
                ),
            ),
        )
    contract_solari = 0 if state.config.choam_module else reward.contracts * 2
    recruited_owner, recruited = recruit_troops(owner, reward.troops * amount)
    next_owner = replace(
        recruited_owner,
        resources=Resources(
            solari=(
                recruited_owner.resources.solari
                + reward.solari * amount
                + contract_solari * amount
            ),
            spice=recruited_owner.resources.spice + reward.spice * amount,
            water=recruited_owner.resources.water + reward.water * amount,
        ),
        intrigue_cards=(*recruited_owner.intrigue_cards, *drawn),
        victory_points=(
            recruited_owner.victory_points + reward.victory_points * amount
        ),
    )
    players[assignment.player] = next_owner
    if reward.influence_faction is not None:
        influence_result = gain_faction_influence(
            replace(
                state,
                players=tuple(players),
                intrigue_deck=intrigue_deck,
                pending_intrigue_draws=pending_draws,
                pending_navigation_plays=pending_navigation,
                pending_track_spies=pending_spies,
                scouts_four_bonus_choices=pending_four,
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
        pending_draws = influence_result.state.pending_intrigue_draws
        pending_navigation = influence_result.state.pending_navigation_plays
        pending_spies = influence_result.state.pending_track_spies
        pending_four = influence_result.state.scouts_four_bonus_choices
        events.extend(influence_result.events)
        next_owner = players[assignment.player]
    if (
        reward.control_space_id is not None
        and reward.control_space_id
        not in players[assignment.player].control_space_ids
    ):
        # Arrakeen Scouts' Prison Planet may hold this seat's last marker.
        scouts_goods, released = free_prison_marker(
            scouts_goods,
            assignment.player,
            len(players[assignment.player].control_space_ids),
            source=f"round:{state.round_number}:combat_reward",
        )
        events.extend(released)
    if reward.control_space_id is not None:
        players = list(
            _apply_control(
                tuple(players),
                assignment.player,
                reward.control_space_id,
            )
        )
    if reward.contracts and state.config.choam_module:
        frames_in_order.append(
            contract_choice_frame(
                assignment.player,
                reward.contracts * amount,
                source=(
                    f"round:{state.round_number}:combat_reward:"
                    f"{assignment.player}:{assignment.rank.value}"
                ),
            )
        )
    for _ in range(amount):
        for _ in range(reward.choose_influence):
            frames_in_order.append(
                _influence_choice_frame(
                    state,
                    assignment.player,
                    len(frames_in_order),
                )
            )
        # Each optional cost is its own arrow, paid or declined on its
        # own and at most once per reward [Main p. 9] [FAQ p. 3];
        # Economic Supremacy prints two (6 Solari, then 4 spice) and
        # they are offered in that printed order. A sandworm offers
        # each arrow a second time [Main p. 14].
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
        *counted_in_play(next_owner),
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
    # One frame per printed Spy, repeated by a sandworm [Main p. 14],
    # each judged when it resolves: with the supply empty its owner may
    # first recall a Spy [Main pp. 11, 20], so the supply at payment
    # does not cap them. A Spy with Deep Cover ignores opponents' Spies
    # [Bloodlines pp. 5, 12].
    for deep_cover in (False,) * (reward.place_spies * amount) + (True,) * (
        reward.deep_cover_spies * amount
    ):
        frames_in_order.append(
            _spy_placement_frame(
                state,
                assignment.player,
                len(frames_in_order),
                deep_cover=deep_cover,
            )
        )
    reward_event = _combat_reward_event(state, assignment, reward)
    events.append(reward_event)
    events.extend(
        recruit_shortfall_events(
            reward_event.event_id,
            assignment.player,
            reward.troops * amount,
            recruited,
        )
    )

    frames = tuple(reversed(frames_in_order))
    next_state = replace(
        state,
        players=tuple(players),
        intrigue_deck=intrigue_deck,
        pending_intrigue_draws=pending_draws,
        pending_navigation_plays=pending_navigation,
        pending_track_spies=pending_spies,
        scouts_four_bonus_choices=pending_four,
        scouts_goods=scouts_goods,
        combat_rewards_paid=paid + 1,
        # The pledge was folded into the first-place frames above; the first
        # recipient paid is the sole winner when there is one, so a tied
        # first place leaves the pledge unused and it is cleared here too.
        conflict_first_place_influence_bonus=0,
        decision_stack=frames,
    )
    return RuleResult(state=next_state, events=tuple(events))


def combat_reward_payment_block(
    frame: DecisionFrame, owner: PlayerState
) -> OptionalEffectBlock | None:
    """Return why ``owner`` cannot pay an optional Conflict reward's cost, or None.

    "Each optional cost is its own arrow" [Main p. 9] [FAQ p. 3]: the
    reward's printed resource (``solari`` or ``spice``, in the frame's
    context) is short when the owner holds less than its cost.
    ``legal_combat_reward_optional_payment_actions`` offers
    ``pay_combat_reward`` exactly when this is None, and the page's greyed-out
    row reads the same block (``display.unavailable``), so the reason shown
    can never disagree with the legal list. Reads only the frame's printed
    terms and the owner's own resources.
    """

    context = dict(frame.context)
    cost = context_int(context, "cost")
    resource = context.get("resource")
    if resource not in ("solari", "spice"):
        raise RuntimeError("optional Combat reward has invalid resource")
    return short_of(
        OptionalBlockKind.SOLARI if resource == "solari" else OptionalBlockKind.SPICE,
        cost,
        getattr(owner.resources, resource),
    )


def legal_combat_reward_optional_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline and, when affordable, pay for an optional reward."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_OPTIONAL:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    if combat_reward_payment_block(frame, state.players[player]) is None:
        actions.append(DomainAction(action_id="pay_combat_reward", actor=player))
    return tuple(actions)


def apply_combat_reward_optional_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pay for or decline one optional Conflict reward."""

    if action not in legal_combat_reward_optional_payment_actions(state, action.actor):
        raise ValueError("action is not a legal optional Combat reward choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    choice_index = context_int(context, "choice_index")
    cost = context_int(context, "cost")
    resource = context.get("resource")
    if resource not in ("solari", "spice"):
        raise RuntimeError("optional Combat reward has invalid resource")
    victory_points = context_int(context, "victory_points")
    paid = action.action_id == "pay_combat_reward"
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            **{resource: getattr(owner.resources, resource) - (cost if paid else 0)},
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
        combat_rewards_resolved=combat_rewards_done(state, remaining),
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


def combat_reward_spy_recall_block(
    frame: DecisionFrame, owner: PlayerState
) -> OptionalEffectBlock | None:
    """Return why ``owner`` cannot recall the Spies an optional reward costs, or None.

    Arrakeen's "recall 2 Spies" arrow [Main p. 9] needs that many of the
    owner's Spies on the board (``spy_post_ids``). Only the two-Spy cost
    exists, so any other raises as the provider always has.
    ``legal_combat_reward_spy_recall_actions`` offers a pair of posts exactly
    when this is None, and the page's greyed-out row reads the same block
    (``display.unavailable``). Reads only the frame's printed terms and the
    owner's own Spies.
    """

    count = context_int(dict(frame.context), "spy_count")
    if count != 2:
        raise NotImplementedError("only a two-Spy Combat reward cost is supported")
    return short_of(OptionalBlockKind.SPIES_ON_BOARD, count, len(owner.spy_post_ids))


def legal_combat_reward_spy_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return decline plus every payable pair of placed Spies."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_SPY_RECALL:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    owner = state.players[player]
    posts = owner.spy_post_ids
    actions = [DomainAction(action_id="decline_combat_reward", actor=player)]
    if combat_reward_spy_recall_block(frame, owner) is not None:
        return tuple(actions)
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
    choice_index = context_int(context, "choice_index")
    spy_count = context_int(context, "spy_count")
    victory_points = context_int(context, "victory_points")
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
        combat_rewards_resolved=combat_rewards_done(state, remaining),
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
    if frame.kind != FrameKind.COMBAT_REWARD_TRASH:
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
            for card_id in (*owner.hand, *owner.discard_pile, *counted_in_play(owner))
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
    choice_index = context_int(dict(frame.context), "choice_index")
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
        combat_rewards_resolved=combat_rewards_done(state, remaining),
    )
    return RuleResult(state=next_state, events=events)


def legal_combat_reward_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the choices of a Conflict reward Spy now.

    A plain reward Spy needs an empty post; a Spy with Deep Cover needs only
    a post without the owner's own Spy. Placing is mandatory while a Spy is
    in the supply (the erratum to [Main p. 11], OQ-057 (14)). Without one,
    "you may first recall one of your Spies for no effect" [Main pp. 11,
    20]: the recall can be declined, and once made the Spy is back in the
    supply and must be placed -- on the post it left, if its owner likes.
    With nothing to place or recall the decline is the only choice ("놓을
    post가 없으면 거절만 남는다", OQ-057 (14)), so the window never stands
    without an action. A four-player game never gets there -- thirteen
    posts for twelve Spies, and Advanced Data Analysis boxes at most one
    Spy -- but the frame is answered by its owner rather than dropped
    unasked (user ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도
    모두 결정 창을 연다").
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_SPY:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    owner = state.players[player]
    if dict(frame.context).get("deep_cover") is True:
        # Spy with Deep Cover: opponents' Spies may be ignored, never one's
        # own [Bloodlines pp. 5, 12].
        occupied = set(owner.spy_post_ids)
    else:
        occupied = {
            post_id for seat in state.players for post_id in seat.spy_post_ids
        }
    targets = tuple(
        post.post_id for post in OBSERVATION_POSTS if post.post_id not in occupied
    )
    if targets and owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_combat_reward_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in targets
        )
    if targets and owner.spy_post_ids:
        return (
            DomainAction(action_id="decline_combat_reward_spy", actor=player),
            *(
                DomainAction(
                    action_id="recall_spy_for_combat_reward",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in owner.spy_post_ids
            ),
        )
    return (DomainAction(action_id="decline_combat_reward_spy", actor=player),)


def apply_combat_reward_spy(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Place the reward Spy, or recall one first, or pass up that recall.

    The decline also answers a Spy with nothing to place or recall; either
    way the Spy is lost publicly (``combat_reward_spy_unavailable``).
    """

    if action not in legal_combat_reward_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Combat reward Spy placement")
    frame = state.decision_stack[-1]
    choice_index = context_int(dict(frame.context), "choice_index")
    if action.action_id == "decline_combat_reward_spy":
        remaining = state.decision_stack[:-1]
        return RuleResult(
            state=replace(
                state,
                decision_stack=remaining,
                combat_rewards_resolved=combat_rewards_done(state, remaining),
            ),
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:combat_reward:spy_unavailable:"
                        f"{choice_index}:{action.actor}"
                    ),
                    kind="combat_reward_spy_unavailable",
                    payload=(
                        ("choice_index", choice_index),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
    post_id = dict(action.arguments)["post_id"]
    if not isinstance(post_id, str):
        raise RuntimeError("Combat reward Spy placement has invalid post ID")
    owner = state.players[action.actor]
    if action.action_id == "recall_spy_for_combat_reward":
        # The frame stays: the recalled Spy now has to be placed.
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, recall_spy(owner, post_id)),
            ),
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:combat_reward:spy_recalled:"
                        f"{choice_index}:{action.actor}:{post_id}"
                    ),
                    kind="spy_recalled",
                    payload=(("player", action.actor), ("post_id", post_id)),
                ),
            ),
        )
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
        combat_rewards_resolved=combat_rewards_done(state, remaining),
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


class CombatInfluenceBlock(StrEnum):
    """Why a Conflict reward's "choose a Faction" cannot take a Faction now.

    ``legal_combat_reward_influence_actions`` and
    ``legal_distinct_combat_reward_influence_actions`` offer a Faction
    exactly when ``combat_reward_influence_block`` is None, and the page's
    greyed-out rows read the same block (``display.unavailable``), so the
    reason shown can never disagree with the legal list.
    """

    TOP = "top"  # the cube is at the top of its track (6)
    NAMED = "named"  # already named for this "Choose two" reward


def combat_reward_influence_block(
    frame: DecisionFrame, owner: PlayerState, faction: Faction
) -> CombatInfluenceBlock | None:
    """Return why ``faction`` cannot be chosen in ``frame`` now, or None.

    A cube at the top of its track cannot rise (OQ-060), and "Choose two"
    names two different Factions [Propaganda card], so a distinct group's
    second pick skips the first one. Reads only public state: the owner's
    Influence and the Factions this reward already named.
    """

    if frame.kind is FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE:
        chosen_mask = context_int(dict(frame.context), "chosen_mask")
        if chosen_mask & (1 << tuple(Faction).index(faction)):
            return CombatInfluenceBlock.NAMED
    if influence_amount(owner.influence, faction) >= MAX_INFLUENCE:
        return CombatInfluenceBlock.TOP
    return None


def _combat_influence_choices(
    frame: DecisionFrame, state: GameState, player: int, action_id: str
) -> tuple[DomainAction, ...]:
    """One action per Faction that can be chosen, else the confirm.

    With every eligible Faction blocked the reward is lost (OQ-060), but
    the window still opens and its owner confirms the loss (user ruling
    2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을
    연다"); the confirm is never offered beside a Faction, since the gain
    is mandatory while one can be taken.
    """

    owner = state.players[player]
    choices = tuple(
        DomainAction(
            action_id=action_id,
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
        if combat_reward_influence_block(frame, owner, faction) is None
    )
    confirm = DomainAction(
        action_id="resolve_combat_influence_without_faction", actor=player
    )
    return choices or (confirm,)


def legal_combat_reward_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every Faction whose track is below the top, else the confirm.

    "Choose any one of the four Factions" [Main p. 20]. Bene Gesserit at 3
    stays a choice with the Intrigue deck empty: the track's Influence 4
    Intrigue card is drawn after the discard is reshuffled [FAQ p. 2].
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_INFLUENCE:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    return _combat_influence_choices(
        frame, state, player, "choose_combat_reward_influence"
    )


def legal_distinct_combat_reward_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return unchosen factions for one choose-distinct Influence group,
    else the confirm."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE:
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    return _combat_influence_choices(
        frame, state, player, "choose_distinct_combat_reward_influence"
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
    choice_index = context_int(context, "choice_index")
    group = context_int(context, "group")
    chosen_mask = context_int(context, "chosen_mask")
    previous = tuple(
        Faction(value)
        for value in str(context.get("chosen_factions", "")).split(",")
        if value
    )
    faction_index = tuple(Faction).index(faction)
    prefix = (
        f"round:{state.round_number}:combat_reward:distinct_influence:"
        f"{choice_index}:{action.actor}:{faction.value}"
    )
    remaining = state.decision_stack[:-1]
    if remaining and frame_context_int(remaining[-1], "group") == group:
        # "Choose two": both Factions are named before either Influence
        # moves (designer ruling, OQ-057), so the second pick cannot be made
        # after seeing what the first one drew.
        next_context = dict(remaining[-1].context)
        next_context["chosen_mask"] = chosen_mask | (1 << faction_index)
        next_context["chosen_factions"] = ",".join(
            pick.value for pick in (*previous, faction)
        )
        remaining = (
            *remaining[:-1],
            replace(remaining[-1], context=tuple(sorted(next_context.items()))),
        )
        return RuleResult(
            state=replace(
                state,
                decision_stack=remaining,
                combat_rewards_resolved=combat_rewards_done(state, remaining),
            ),
            events=(
                GameEvent(
                    event_id=f"{prefix}:chosen",
                    kind="combat_reward_influence_chosen",
                    payload=(("faction", faction.value), ("player", action.actor)),
                ),
            ),
        )
    working = replace(
        state,
        decision_stack=remaining,
        combat_rewards_resolved=combat_rewards_done(state, remaining),
    )
    events: list[GameEvent] = []
    for pick in (*previous, faction):
        gained = gain_faction_influence(
            working,
            action.actor,
            pick,
            1,
            event_prefix=(
                f"round:{state.round_number}:combat_reward:distinct_influence:"
                f"{choice_index}:{action.actor}:{pick.value}"
            ),
        )
        working = gained.state
        events.extend(gained.events)
    return RuleResult(state=working, events=tuple(events))


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
    choice_index = context_int(dict(frame.context), "choice_index")
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
        combat_rewards_resolved=combat_rewards_done(state, remaining),
    )
    return RuleResult(state=next_state, events=gained.events)


def apply_combat_influence_without_faction(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Confirm a Conflict reward Influence choice no Faction can take.

    The choice is lost the way a plain Influence gain is lost at the top of
    the track (OQ-060). A "choose two" group still pays the Factions its
    earlier pick named, since those were chosen before this one ran out of
    options. The events are those of the automatic step this confirm
    replaced (user ruling 2026-09-30).
    """

    offered = (
        *legal_combat_reward_influence_actions(state, action.actor),
        *legal_distinct_combat_reward_influence_actions(state, action.actor),
    )
    if (
        action.action_id != "resolve_combat_influence_without_faction"
        or action not in offered
    ):
        raise ValueError("action is not a legal Influence confirm without a Faction")
    frame = state.decision_stack[-1]
    player = action.actor
    context = dict(frame.context)
    choice_index = context_int(context, "choice_index")
    remaining = state.decision_stack[:-1]
    working = replace(
        state,
        decision_stack=remaining,
        combat_rewards_resolved=combat_rewards_done(state, remaining),
    )
    prefix = (
        f"round:{state.round_number}:combat_reward:influence_unavailable:"
        f"{choice_index}:{player}"
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=prefix,
            kind="combat_reward_influence_unavailable",
            payload=(("choice_index", choice_index), ("player", player)),
        )
    ]
    if frame.kind is FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE:
        for pick in (
            Faction(value)
            for value in str(context.get("chosen_factions", "")).split(",")
            if value
        ):
            gained = gain_faction_influence(
                working,
                player,
                pick,
                1,
                event_prefix=(
                    f"round:{state.round_number}:combat_reward:distinct_influence:"
                    f"{choice_index}:{player}:{pick.value}"
                ),
            )
            working = gained.state
            events.extend(gained.events)
    return RuleResult(state=working, events=tuple(events))


def _loss_trigger_option(card_id: str) -> IntrigueOption | None:
    """The card's Conflict-end loss trigger option (Harvest Cells), if any."""

    entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
    if entry is None:
        return None
    return next(
        (
            option
            for option in entry.options
            if isinstance(option.trigger, OnTroopsLostAtConflictEnd)
        ),
        None,
    )


def _trigger_specimens(option: IntrigueOption) -> int:
    return sum(
        reward.count
        for section in option.sections
        for reward in section.rewards
        if isinstance(reward, GenerateSpecimens)
    )


def _harvest_cells_has_effect(
    state: GameState, player: int, option: IntrigueOption
) -> bool:
    """Whether one more face-up copy of ``option`` could change something.

    "To play an Intrigue card, you must meet its conditions and pay its
    costs." [FAQ p. 2], with the user's ruling of 2026-10-06 that an
    Intrigue option needs an effect that can change something. Harvest
    Cells fires after the cleanup has put the Conflict's troops back in the
    supply ("When resolving combat, troops that return to your supply are
    considered 'lost.'" [FAQ p. 1]); Sardaukar Commanders go back to their
    own supply [Bloodlines p. 4], so they make no specimen. Its specimens
    can be made while those troops and the supply's outnumber what the
    copies already face up take. Otherwise its Tleilaxu card can still be
    bought if the specimens the earlier copies made pay for a Row card or a
    Reclaimed Forces effect -- an upper bound, since an earlier copy may
    spend them first, so it can only let a copy through, never keep one
    out. The Row is judged as the window opens.
    """

    from dune_imperium.rules.tleilaxu_row import (
        RECLAIMED_FORCES_CHOICES,
        reclaimed_forces_block,
    )

    owner = state.players[player]
    staged = sum(
        _trigger_specimens(staged_option)
        for card_id in owner.intrigue_faceup
        if (staged_option := _loss_trigger_option(card_id)) is not None
    )
    returning = owner.troops_supply + owner.troops_conflict
    if _trigger_specimens(option) and returning - staged >= 1:
        return True
    if not any(
        isinstance(reward, AcquireTleilaxuCard)
        for section in option.sections
        for reward in section.rewards
    ):
        return False
    # The earlier copies' specimens, as troops taken from the supply the
    # cleanup refills (the seat still accounts for all its troops).
    made = min(staged, returning)
    from_conflict = min(made, owner.troops_conflict)
    projected = replace(
        owner,
        specimens=owner.specimens + made,
        troops_conflict=owner.troops_conflict - from_conflict,
        troops_supply=owner.troops_supply - (made - from_conflict),
    )
    return any(
        tleilaxu_card_for_instance(instance_id).specimen_cost <= projected.specimens
        for instance_id in state.tleilaxu_row
    ) or any(
        reclaimed_forces_block(projected, choice) is None
        for choice in RECLAIMED_FORCES_CHOICES
    )


class ConflictEndTriggerBlock(StrEnum):
    """Why a held Conflict-end trigger card is not offered in its window.

    ``conflict_end_trigger_block`` returns one of these, or the option's own
    reason (``option_unplayable_reason``); the window offers exactly the
    cards without a block (``_conflict_end_trigger_cards``), and the page
    greys out the others with that reason (``display.unavailable``, user
    request 2026-09-29).
    """

    # Fewer units leave the Conflict than the trigger names.
    LOSS = "loss"
    # One more copy could change nothing (``_harvest_cells_has_effect``):
    # no Tleilaxu card its specimens could pay for, and no troop in the
    # supply once the Conflict's troops are back there ...
    NO_TROOP = "no_troop"
    # ... or the copies already face up take every such troop.
    TROOPS_TAKEN = "troops_taken"


def conflict_end_trigger_block(
    state: GameState, player: int, option: IntrigueOption, lost: int | None = None
) -> ConflictEndTriggerBlock | OptionUnplayable | None:
    """Why ``player`` may not play ``option``, a Conflict-end loss trigger,
    in its Conflict-end window now, or None when it may.

    In order: the trigger's loss ("When you lose at least three troops at
    the end of a Conflict:" [Harvest Cells card]; ``lost`` defaults to the
    units in the Conflict, ``_conflict_losses``), the play's own conditions
    and costs (``option_unplayable_reason``), then an effect that could
    change something (``_harvest_cells_has_effect``, user ruling
    2026-10-06).
    """

    from dune_imperium.rules.effect_interpreter import option_unplayable_reason

    trigger = option.trigger
    if not isinstance(trigger, OnTroopsLostAtConflictEnd):
        raise ValueError("not a Conflict-end loss trigger")
    if lost is None:
        lost = _conflict_losses(state)[player]
    if lost < trigger.minimum:
        return ConflictEndTriggerBlock.LOSS
    unplayable = option_unplayable_reason(state, player, option)
    if unplayable is not None:
        return unplayable
    if _harvest_cells_has_effect(state, player, option):
        return None
    # The troops ``_harvest_cells_has_effect`` counts as back in the supply.
    owner = state.players[player]
    if owner.troops_supply + owner.troops_conflict == 0:
        return ConflictEndTriggerBlock.NO_TROOP
    return ConflictEndTriggerBlock.TROOPS_TAKEN


def _conflict_end_trigger_cards(
    state: GameState, player: int, lost: int
) -> tuple[str, ...]:
    """Hand Intrigue whose Conflict-end trigger would fire now, is playable,
    and could change something (``conflict_end_trigger_block``)."""

    cards: list[str] = []
    for card_id in state.players[player].intrigue_cards:
        option = _loss_trigger_option(card_id)
        if (
            option is not None
            and conflict_end_trigger_block(state, player, option, lost) is None
        ):
            cards.append(card_id)
    return tuple(cards)


def _conflict_losses(state: GameState) -> tuple[int, ...]:
    return tuple(
        player.troops_conflict + player.commanders_conflict for player in state.players
    )


def _loss_triggers() -> tuple[tuple[str, int], ...]:
    """Every Intrigue instance with a Conflict-end loss trigger, and its
    minimum loss (Harvest Cells' two copies, three troops)."""

    return tuple(
        (instance_id, option.trigger.minimum)
        for instance_id, entry in INTRIGUE_CARDS_BY_INSTANCE.items()
        for option in entry.options
        if isinstance(option.trigger, OnTroopsLostAtConflictEnd)
    )


def _conflict_end_window_opens(state: GameState, player: int, lost: int) -> bool:
    """Whether ``player`` gets a Conflict-end window, on public facts only.

    Every seat sees the units in the Conflict, how many Intrigue cards a
    seat holds, the Intrigue discard and the cards face up; none sees a
    hand. So the window opens with the Immortality module for a seat that
    loses at least the smallest loss any such card names and holds an
    Intrigue card, unless every copy of those cards is already public.
    """

    triggers = _loss_triggers()
    if not state.config.immortality or not triggers:
        return False
    if lost < min(minimum for _, minimum in triggers):
        return False
    if not state.players[player].intrigue_cards:
        return False
    public = {
        *state.intrigue_discard,
        *(card for seat in state.players for card in seat.intrigue_faceup),
    }
    return any(instance_id not in public for instance_id, _ in triggers)


def offer_conflict_end_triggers(state: GameState) -> RuleResult:
    """Open the window for Intrigue that triggers at this Conflict's end.

    Harvest Cells is played only here, after the rewards and before the
    cleanup: "This card is played after combat resolves." (designer ruling,
    OQ-057 (11); ``IntriguePlayBlock.CONFLICT_END`` keeps it out of Combat
    Intrigue). Each seat, in turn order from the First Player (OQ-002), may
    play a hand card whose Conflict-end trigger would fire -- one held from
    earlier or one just received as a reward.

    Whether a seat's window opens is decided on public facts only
    (``_conflict_end_window_opens``), the same frame, prompt and event for
    every seat, so a window no longer tells the table that its seat holds
    Harvest Cells (OQ-103, user decision 2026-10-09: "1번은 A안으로 가자").
    A seat that can play nothing gets only the decline. The play itself
    keeps its condition: "To play an Intrigue card, you must meet its
    conditions and pay its costs." [FAQ p. 2] (user ruling 2026-10-06,
    ``legal_conflict_end_trigger_actions``).
    """

    if state.phase is not GamePhase.COMBAT:
        raise ValueError("Conflict-end triggers can be offered only during Combat")
    if not state.combat_rewards_resolved or state.decision_stack:
        raise ValueError("Conflict-end triggers follow the resolved rewards")
    if state.combat_end_triggers_offered:
        raise ValueError("Conflict-end triggers were already offered")
    losses = _conflict_losses(state)
    first = state.first_player or 0
    frames: list[DecisionFrame] = []
    for offset in range(state.config.players):
        player = (first + offset) % state.config.players
        if not _conflict_end_window_opens(state, player, losses[player]):
            continue
        frames.append(
            DecisionFrame(
                kind=FrameKind.CONFLICT_END_TRIGGER,
                frame_id=f"round:{state.round_number}:conflict_end_trigger:{player}",
                decision=PlayerDecision(
                    owner=player,
                    prompt=(
                        "Play an Intrigue card that triggers at this Conflict's "
                        "end, or decline"
                    ),
                ),
                context=(("player", player),),
            )
        )
    next_state = replace(
        state,
        combat_end_triggers_offered=True,
        decision_stack=tuple(reversed(frames)),
    )
    return RuleResult(
        state=next_state,
        events=tuple(
            GameEvent(
                event_id=f"{frame.frame_id}:offered",
                kind="conflict_end_trigger_offered",
                payload=(("player", dict(frame.context)["player"]),),
            )
            for frame in frames
        ),
    )


def legal_conflict_end_trigger_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Play one of the seat's Conflict-end trigger cards now, or decline."""

    frame = owned_top_frame(state, FrameKind.CONFLICT_END_TRIGGER, player)
    if frame is None:
        return ()
    losses = _conflict_losses(state)
    return (
        DomainAction(action_id="decline_conflict_end_intrigue", actor=player),
        *(
            DomainAction(
                action_id="play_conflict_end_intrigue",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in _conflict_end_trigger_cards(state, player, losses[player])
        ),
    )


def apply_conflict_end_trigger(state: GameState, action: DomainAction) -> RuleResult:
    """Stage the chosen hand card face up, or close the window.

    The card is played now (designer ruling, OQ-057) but its effect waits
    for the loss it names: "When you lose at least three troops at the end
    of a Conflict:" [Harvest Cells card], and "When resolving combat, troops
    that return to your supply are considered 'lost.'" [FAQ p. 1]. So it
    joins the face-up cards that ``finish_combat`` fires after the troops
    are back in the supply -- where its specimens come from ("take a troop
    from your supply" [Immortality p. 8]) -- in turn order (OQ-002).
    """

    if action not in legal_conflict_end_trigger_actions(state, action.actor):
        raise ValueError("action is not a legal Conflict-end Intrigue choice")
    player = action.actor
    frame = state.decision_stack[-1]
    if action.action_id == "decline_conflict_end_intrigue":
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{frame.frame_id}:declined",
                    kind="conflict_end_trigger_declined",
                    payload=(("player", player),),
                ),
            ),
        )
    card_id = str(dict(action.arguments)["card_id"])
    owner = state.players[player]
    staged = replace(
        owner,
        intrigue_cards=tuple(held for held in owner.intrigue_cards if held != card_id),
        intrigue_faceup=(*owner.intrigue_faceup, card_id),
    )
    after = replace(state, players=replace_player(state.players, staged))
    # The window stays open while the seat holds an Intrigue card, a public
    # fact: closing it only when no other copy could change something would
    # tell the table whether a second Harvest Cells is in the hand (OQ-103).
    # Its play actions still offer only a copy that would change something
    # (``_harvest_cells_has_effect``).
    return RuleResult(
        state=after if staged.intrigue_cards else after.pop_decision(),
        events=(
            GameEvent(
                event_id=f"{frame.frame_id}:played:{card_id}",
                kind="intrigue_played",
                payload=(("card_id", card_id), ("player", player)),
            ),
        ),
    )


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
    match_events: tuple[GameEvent, ...] = ()
    if ranking.winner is not None:
        winner = players[ranking.winner]
        fleet = has_ornithopter_fleet(winner)
        matched_card_id = None if fleet else _matching_battle_card(winner, conflict_id)
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
        if fleet:
            # Ornithopter Fleet: every icon is an Ornithopter, so the new
            # card pairs with any face-up one [Bloodlines p. 12].
            winner, match_events = match_all_battle_icons(
                winner, source=f"round:{state.round_number}:conflict_won"
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
        events.extend(match_events)

    # Harvest Cells (Immortality): troops returning to the supply at
    # cleanup are "lost" [FAQ p. 1]; the card the Conflict-end window laid
    # face up fires after the return.
    losses = tuple(
        player.troops_conflict + player.commanders_conflict for player in players
    )
    # Troops and Sardaukar Commanders return to the supply, sandworms to
    # the bank, every marker to 0 [Main p. 14] [Bloodlines p. 4].
    players = tuple(
        replace(
            player,
            troops_supply=player.troops_supply + player.troops_conflict,
            troops_conflict=0,
            sandworms_conflict=0,
            commanders_supply=player.commanders_supply + player.commanders_conflict,
            commanders_conflict=0,
            # Into the Fray's Agent comes back too (it is recalled with the
            # others in the Recall phase either way) [Duncan Idaho card].
            agents_available=player.agents_available + player.agent_in_conflict,
            agent_in_conflict=0,
            combat_strength=0,
            skill_strength_applied=0,
        )
        for player in players
    )
    # Tactician: "When resolving combat, troops that return to your supply
    # are considered 'lost.' Each different source of retreating or losing
    # troops is handled separately" [FAQ p. 1] -- the cleanup is one source,
    # so the token advances once by the whole loss [Chani card].
    advanced = [
        advance_tactics_token(
            player,
            lost,
            source=f"round:{state.round_number}:player:{player.player_id}:"
            "combat_cleanup",
        )
        for player, lost in zip(players, losses, strict=True)
    ]
    players = tuple(player for player, _ in advanced)
    events.extend(event for _, tactics_events in advanced for event in tactics_events)
    next_state = replace(
        state,
        phase=GamePhase.MAKERS,
        players=players,
        current_conflict_ids=current_conflict_ids,
        combat_intrigue_players=(),
    )
    next_state, loss_events = _fire_troop_loss_triggers(next_state, losses)
    events.extend(loss_events)
    events.append(
        GameEvent(
            event_id=f"round:{state.round_number}:combat_cleanup",
            kind="combat_cleaned_up",
        )
    )
    if ranking.winner is not None and has_tech(
        next_state.players[ranking.winner].tech_ids, TechAbility.CONFLICT_WIN_DRAW
    ):
        # Planetary Array: "When you win a Conflict: draw a card" — a sole
        # winner only [FAQ p. 4] [Planetary Array Tech tile]; owed to the
        # engine's post-step draw.
        seat = next_state.players[ranking.winner]
        next_state = replace(
            next_state,
            players=replace_player(
                next_state.players,
                replace(seat, tech_cards_owed=seat.tech_cards_owed + 1),
            ),
        )
    return RuleResult(state=next_state, events=tuple(events))


def _matching_battle_card(player: PlayerState, conflict_id: str) -> str | None:
    battle_icon = CONFLICTS_BY_ID[conflict_id].battle_icon
    if battle_icon is None:
        # No printed icon (Economic Supremacy): the card stays face up in
        # the winner's supply but never matches on arrival (OQ-094 (a)).
        return None
    if battle_icon is BattleIcon.WILD:
        # A wild battle icon is matched during the Endgame, by choice, not
        # on arrival [Main p. 20] [Bloodlines p. 5].
        return None
    face_up = (
        card_id
        for card_id in (*player.objective_ids, *player.won_conflict_ids)
        if card_id not in player.face_down_battle_card_ids
    )
    matches = tuple(
        card_id for card_id in face_up if _battle_icon_for(card_id) is battle_icon
    )
    if len(matches) > 1:
        raise NotImplementedError("choosing among matching battle icons is unresolved")
    return matches[0] if matches else None


def face_up_battle_icons(player: PlayerState) -> frozenset[BattleIcon]:
    """Return the icons on the player's face-up Objective and won Conflicts.

    Immediate matching flips every same-icon pair on arrival [Main p. 14],
    so at most one face-up card per printed icon exists and the set of
    icons is the whole information. A face-up wild card (Propaganda)
    reports ``BattleIcon.WILD``, never one of the three printed icons. With
    Ornithopter Fleet every icon is an Ornithopter [Bloodlines p. 12]. A
    face-up card with no printed icon (Economic Supremacy) adds nothing,
    Ornithopter Fleet or not (OQ-094 (c), (d)).
    """

    face_down = set(player.face_down_battle_card_ids)
    face_up = (
        _battle_icon_for(card_id)
        for card_id in (*player.objective_ids, *player.won_conflict_ids)
        if card_id not in face_down
    )
    icons = frozenset(icon for icon in face_up if icon is not None)
    if has_ornithopter_fleet(player):
        return frozenset({BattleIcon.ORNITHOPTER}) if icons else frozenset()
    return icons


def _battle_icon_for(card_id: str) -> BattleIcon | None:
    """Return the card's printed icon; ``None`` when it prints none (OQ-094)."""

    if card_id in OBJECTIVES_BY_ID:
        return OBJECTIVES_BY_ID[card_id].battle_icon
    return CONFLICTS_BY_ID[card_id].battle_icon


def _combat_reward_event(
    state: GameState,
    assignment: CombatReward,
    reward: ConflictReward,
) -> GameEvent:
    contract_solari = 0 if state.config.choam_module else reward.contracts * 2
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
            ("victory_points", reward.victory_points * assignment.multiplier),
            ("water", reward.water * assignment.multiplier),
        ),
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


def _influence_choice_frame(
    state: GameState,
    player: int,
    index: int,
) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.COMBAT_REWARD_INFLUENCE,
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
        kind=FrameKind.COMBAT_REWARD_OPTIONAL,
        frame_id=(
            f"round:{state.round_number}:combat_reward_optional:{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt=(
                f"Pay {cost} {resource.title()} to gain {victory_points} Victory Point"
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
        kind=FrameKind.COMBAT_REWARD_SPY_RECALL,
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
        kind=FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE,
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
            ("chosen_factions", ""),
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
        kind=FrameKind.COMBAT_REWARD_TRASH,
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
    *,
    deep_cover: bool = False,
) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.COMBAT_REWARD_SPY,
        frame_id=f"round:{state.round_number}:combat_reward_spy:{index}:{player}",
        decision=PlayerDecision(
            owner=player,
            prompt=(
                "Choose an Observation Post for your Spy with Deep Cover"
                if deep_cover
                else "Choose an empty Observation Post for your Spy"
            ),
        ),
        # Plain reward Spies keep their earlier context (and replay digests).
        context=(
            (("choice_index", index), ("deep_cover", True), ("player", player))
            if deep_cover
            else (("choice_index", index), ("player", player))
        ),
    )


def _positive_strength_groups(
    players: tuple[PlayerState, ...],
    first_player: int | None = None,
) -> tuple[tuple[int, ...], ...]:
    strengths = sorted(
        {player.combat_strength for player in players if player.combat_strength > 0},
        reverse=True,
    )
    ordered = (
        tuple(
            players[(first_player + offset) % len(players)]
            for offset in range(len(players))
        )
        if first_player is not None
        else players
    )
    return tuple(
        tuple(
            player.player_id for player in ordered if player.combat_strength == strength
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
    return player.units_in_conflict > 0


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
    *,
    played: bool = False,
) -> DecisionFrame:
    mask = sum(1 << player for player in participants)
    return DecisionFrame(
        kind=FrameKind.COMBAT_INTRIGUE,
        frame_id=f"round:{state.round_number}:combat_intrigue",
        decision=PlayerDecision(
            owner=participants[current_index],
            prompt="Play Combat Intrigue cards or pass",
        ),
        context=(
            ("consecutive_passes", consecutive_passes),
            ("current_index", current_index),
            ("participants_mask", mask),
            *(((COMBAT_INTRIGUE_PLAYED_KEY, 1),) if played else ()),
        ),
    )


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


def combat_participants_are_stale(state: GameState) -> bool:
    """Whether the Combat Intrigue loop on top lists a seat with no unit left.

    A card's play refreshes the loop as it finishes, but only when the loop
    is on top then; a card that leaves a window of its own (Reach
    Agreement's Contract market, Battlefield Research's Tech window) is
    refreshed by the engine once that window resolves and the loop is on
    top again (OQ-003).
    """

    if not state.decision_stack:
        return False
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_INTRIGUE:
        return False
    participants = _participants_from_mask(
        state.config.players,
        context_int(dict(frame.context), "participants_mask"),
        state.first_player,
    )
    return any(not _has_conflict_units(state.players[seat]) for seat in participants)


def refresh_combat_participants(state: GameState) -> RuleResult:
    """Drop participants who no longer have units from the priority loop.

    Project convention for OQ-003: a player whose last unit leaves the
    Conflict during Combat Intrigue is removed at once, and no player can join
    the loop after Combat began. If nobody remains the Intrigue step ends,
    with the ``combat_intrigue_finished`` event its other two endings emit;
    the event id ends in ``:emptied`` (no participant has a unit left). It
    has no payload, so the log line reads like the one for a Conflict
    nobody entered.
    """

    if not state.decision_stack:
        return RuleResult(state=state)
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.COMBAT_INTRIGUE:
        return RuleResult(state=state)
    context = dict(frame.context)
    participants = _participants_from_mask(
        state.config.players,
        context_int(context, "participants_mask"),
        state.first_player,
    )
    current_index = context_int(context, "current_index")
    current = participants[current_index]
    remaining = tuple(
        player for player in participants if _has_conflict_units(state.players[player])
    )
    if remaining == participants:
        return RuleResult(state=state)
    if not remaining:
        event = GameEvent(
            event_id=f"round:{state.round_number}:combat_intrigue:emptied",
            kind="combat_intrigue_finished",
        )
        return RuleResult(
            state=replace(
                state,
                combat_intrigue_complete=True,
                decision_stack=state.decision_stack[:-1],
            ),
            events=(event,),
        )
    if current in remaining:
        next_index = remaining.index(current)
    else:
        # Priority passes to the next remaining participant clockwise.
        later = [p for p in participants[current_index + 1 :] if p in remaining]
        next_index = remaining.index(later[0]) if later else 0
    consecutive_passes = min(context_int(context, "consecutive_passes"), len(remaining))
    next_frame = _combat_intrigue_frame(
        state,
        participants=remaining,
        current_index=next_index,
        consecutive_passes=consecutive_passes,
        # A seat that keeps priority keeps its played mark; priority that
        # moves on reaches a seat that has played nothing yet.
        played=current in remaining
        and bool(context.get(COMBAT_INTRIGUE_PLAYED_KEY)),
    )
    return RuleResult(
        state=replace(state, decision_stack=(*state.decision_stack[:-1], next_frame))
    )


def _fire_troop_loss_triggers(
    state: GameState, losses: tuple[int, ...]
) -> tuple[GameState, tuple[GameEvent, ...]]:
    """Resolve face-up Intrigue waiting on a Conflict-end troop loss.

    Only the Conflict-end window lays such a card face up, and only when
    this loss meets its trigger (``legal_conflict_end_trigger_actions``);
    nothing changes the troops in the Conflict between that window and the
    cleanup, so the card always fires. It used to expire when a card laid face up in
    Combat Intrigue lost too few (gone with the user ruling of 2026-10-06).
    """

    from dune_imperium.rules.intrigue import resolve_faceup_trigger_option

    next_state = state
    events: list[GameEvent] = []
    # Turn order from the First Player when several seats fire (designer
    # ruling, OQ-002).
    first = state.first_player or 0
    for offset in range(state.config.players):
        player = (first + offset) % state.config.players
        lost = losses[player]
        for card_id in state.players[player].intrigue_faceup:
            entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
            if entry is None:
                continue
            minimum = next(
                (
                    option.trigger.minimum
                    for option in entry.options
                    if isinstance(option.trigger, OnTroopsLostAtConflictEnd)
                ),
                None,
            )
            if minimum is None:
                continue
            source = (
                f"round:{state.round_number}:player:{player}:conflict_end:{card_id}"
            )
            if lost < minimum:
                raise RuntimeError(
                    "a Conflict-end trigger card waits face up without its loss"
                )
            fired = resolve_faceup_trigger_option(
                next_state, player, card_id, source=source
            )
            next_state = fired.state
            events.extend(fired.events)
    return next_state, tuple(events)
