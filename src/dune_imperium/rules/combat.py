"""Pure four-player Combat ranking rules."""

from copy import replace
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import cache
from typing import TYPE_CHECKING, Final

from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.tech_abilities import tech_draws_on
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.uprising.abilities import Ability, AbilityStructure
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflict_abilities import (
    CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTleilaxuCard,
    DrawIntrigueCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    IntrigueOption,
    OnConflictWon,
    OnTroopsLostAtConflictEnd,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    Reward,
    TakeContract,
    TakeControl,
    TakeMentat,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import BattleIcon
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import trashable_cards
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.contracts import contract_choice_frame
from dune_imperium.rules.dreadnoughts import end_combat_dreadnoughts
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
    replace_top_frame,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event, resources_paid_event
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
from dune_imperium.rules.spy_placement import recall_spy, spy_options
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
    if conflict_id not in CONFLICT_REWARD_ABILITIES:
        raise NotImplementedError(
            f"Conflict rewards are not transcribed: {conflict_id}"
        )

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
        # order between them). Each recipient answers its reward icon by
        # icon in its own window (OQ-112); the engine calls again once the
        # window and what it opened are answered.
        paid = _pay_next_combat_reward(
            state, conflict_id, ranking.rewards[state.combat_rewards_paid]
        )
        state = paid.state
        events.extend(paid.events)
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


# --- One recipient's reward, icon by icon (stage B2, OQ-112) ----------------
#
# The recipient answers its reward row in a window of its own: a row per
# icon the record prints (``CONFLICT_REWARD_ABILITIES``), in any order, an
# automatic icon (resources, troops, an Intrigue draw, VP, a fixed
# Influence, control, a Contract without CHOAM) resolved by its row and a
# choice icon (an Influence of its choice, an optional arrow, a Spy, a trash,
# the Contract market) opening its own frame, which is answered before the
# window comes back. A record piece is one icon, its resources one row
# (OQ-112 (3)). A sandworm doubles each icon [Main p. 14]: an automatic one
# pays twice its amount on its row, a choice one is offered twice; control is
# not doubled. The window opens even for a single icon (OQ-112 (2)).

REWARD_ICON_ACTION: Final = "resolve_combat_reward_icon"
# Every icon a Conflict reward row may print, the action codec's order.
COMBAT_REWARD_ICON_KINDS: Final = (
    "resources",
    "intrigue",
    "troops",
    "victory_points",
    "faction_influence",
    "control",
    "contract",
    "choose_influence",
    "distinct_influence",
    "optional_solari",
    "optional_spice",
    "optional_recall_spies",
    "trash",
    "spy",
    "deep_cover_spy",
    # Not a reward icon: Planetary Array's "When you win a Conflict: draw a
    # card", a row of the sole winner's window (OQ-121, user ruling
    # 2026-10-25, "PA는 승자의 창 (추천)").
    "planetary_array",
    # Not a reward icon either: the sole winner's close of the window once
    # every other row is resolved, the press that says "no more winning
    # Intrigue" (OQ-121 decision 6: "안 내도 창이 닫힌다"). Only the original
    # game's catalog holds its row (``action_codec``): only its Intrigue deck
    # holds a winning Intrigue (``winning_intrigue_is_hidden``).
    "winning_intrigue",
    # The original game's (docs/rules/imperium-base.md 9, 10): the Mentat
    # [DI p. 16], two Influence with one Faction [DI p. 16] (Grand Vision),
    # and the lines of a "-OR-" or "Choose two:" row, one row each
    # (``REWARD_LINE_KINDS``; OQ-114).
    "mentat",
    "one_faction_influence",
    "line_0",
    "line_1",
    "line_2",
)
# The kinds only the original game's Conflicts print: a catalog holds their
# rows only when one of its Conflicts prints them (docs/base-game-and-ix-plan.md
# 15.4), so Uprising's rows stay what they were.
REWARD_LINE_KINDS: Final = ("line_0", "line_1", "line_2")
# The window's own closing row (see ``COMBAT_REWARD_ICON_KINDS``); always the
# last of the window's icons, offered when it is the only one left.
WINNING_INTRIGUE: Final = "winning_intrigue"
IMPERIUM_REWARD_ICON_KINDS: Final = frozenset(
    {"mentat", "one_faction_influence", *REWARD_LINE_KINDS}
)
# Frame context keys of the window: the icons still to resolve, in the order
# the engine paid them before stage B2 (``LEGACY_ICON_ORDER``: an older
# record's, and the AI seats', order), the row's kinds in printed order, the
# rank, the sandworm multiplier, and how many choice frames the window has
# opened (their ``choice_index``, which their events carry).
_ICONS_KEY: Final = "icons"
_PRINTED_KEY: Final = "printed"
# The lines picked so far of a row of alternatives (comma-separated
# indexes), and how many it takes: 1 for "-OR-", 2 for "Choose two:".
_CHOSEN_KEY: Final = "chosen_lines"
_TAKES_KEY: Final = "lines_taken"
_RANK_KEY: Final = "rank"
_MULTIPLIER_KEY: Final = "multiplier"
_CHOICE_INDEX_KEY: Final = "choice_index"
# The automatic part, in the order the engine paid it in one step before
# stage B2; a Contract without CHOAM came with the resources.
LEGACY_AUTOMATIC_ORDER: Final = (
    "intrigue",
    "troops",
    "resources",
    "victory_points",
    "faction_influence",
    "control",
)
# The choice icons of one copy of the reward, in the order their frames were
# answered before stage B2 (a sandworm repeats the copy); the trash and Spy
# icons came after both copies.
_LEGACY_COPY_CHOICES: Final = (
    "choose_influence",
    "optional_solari",
    "optional_spice",
    "optional_recall_spies",
    "distinct_influence",
)
_LEGACY_LATER_CHOICES: Final = ("trash", "spy", "deep_cover_spy")


def _arrow_kind(cost: object) -> str:
    match cost:
        case PayResources(solari=solari, spice=0, water=0) if solari:
            return "optional_solari"
        case PayResources(solari=0, spice=spice, water=0) if spice:
            return "optional_spice"
        case RecallSpy():
            return "optional_recall_spies"
    raise TypeError(f"{cost!r} is not a Conflict reward arrow's cost")


def _row_takes(row: Ability) -> int:
    """How many lines a row of alternatives takes (0: a plain row)."""

    match row.structure:
        case AbilityStructure.ONE_OF:
            return 1
        case AbilityStructure.CHOOSE_TWO:
            return 2
    return 0


def _icon_kind(piece: Reward) -> str:
    """The icon a free reward piece of a Conflict row is (``CONFLICT_REWARD``
    records, ``conflict_abilities``)."""

    match piece:
        case GainResources():
            return "resources"
        case DrawIntrigueCards():
            return "intrigue"
        case RecruitTroops():
            return "troops"
        case GainVictoryPoints():
            return "victory_points"
        case TakeControl():
            return "control"
        case TakeContract():
            return "contract"
        case TrashPersonalCard():
            return "trash"
        case TakeMentat():
            return "mentat"
        case PlaceSpy(shared_post=True):
            return "deep_cover_spy"
        case PlaceSpy():
            return "spy"
        case GainInfluence(distinct=True):
            return "distinct_influence"
        case GainInfluence(one_faction=True):
            return "one_faction_influence"
        case GainInfluence(factions=(_,)):
            return "faction_influence"
        case GainInfluence():
            return "choose_influence"
    raise TypeError(f"{piece!r} is not a Conflict reward icon")


def _row_icons(
    row: Ability, chosen: tuple[int, ...] = ()
) -> tuple[tuple[str, Reward | EffectSection], ...]:
    """Each icon of a reward row with the piece (an arrow: its line) that
    prints it, in printed order.

    A row of alternatives ("-OR-", "Choose two:") is one row per line
    (``line_<index>``) until its lines are ``chosen``; then it is the chosen
    lines' icons, their resources one row (OQ-112 (3))."""

    if _row_takes(row):
        if len(chosen) < _row_takes(row):
            return tuple(
                (f"line_{index}", line) for index, line in enumerate(row.sections)
            )
        solari = spice = water = 0
        icons_of_lines: list[tuple[str, Reward | EffectSection]] = []
        for index in sorted(chosen):
            for piece in row.sections[index].rewards:
                if isinstance(piece, GainResources):
                    solari += piece.solari
                    spice += piece.spice
                    water += piece.water
                else:
                    icons_of_lines.append((_icon_kind(piece), piece))
        if solari or spice or water:
            resources = GainResources(solari=solari, spice=spice, water=water)
            icons_of_lines.insert(0, ("resources", resources))
        return tuple(icons_of_lines)
    icons: list[tuple[str, Reward | EffectSection]] = []
    for line in row.sections:
        if line.costs:
            (cost,) = line.costs
            icons.append((_arrow_kind(cost), line))
        else:
            icons.extend((_icon_kind(piece), piece) for piece in line.rewards)
    return tuple(icons)


def conflict_reward_icon_kinds(conflict_id: str) -> tuple[str, ...]:
    """Every icon kind a Conflict's reward rows print, in printed order
    (the action codec's rows, stage B3d-1)."""

    return tuple(
        dict.fromkeys(
            kind
            for row in CONFLICT_REWARD_ABILITIES[conflict_id]
            for kind, _piece in _row_icons(row)
        )
    )


def reward_icon_piece(
    conflict_id: str, rank: int, kind: str, chosen: tuple[int, ...] = ()
) -> Reward | EffectSection | None:
    """The first piece of a Conflict's ``rank`` row that prints ``kind``
    (an arrow's line), or None (Pivotal Gambit's Influence, which no record
    prints); a row of alternatives reads its ``chosen`` lines."""

    row = CONFLICT_REWARD_ABILITIES[conflict_id][rank - 1]
    return next(
        (piece for icon, piece in _row_icons(row, chosen) if icon == kind), None
    )


def chosen_reward_lines(frame: DecisionFrame) -> tuple[int, ...]:
    """The lines a reward window's row of alternatives has picked."""

    text = str(dict(frame.context).get(_CHOSEN_KEY, ""))
    return tuple(int(index) for index in text.split(",") if index)


def _reward_window(
    state: GameState, conflict_id: str, assignment: CombatReward
) -> DecisionFrame:
    """The recipient's window over its reward row's icons."""

    row = CONFLICT_REWARD_ABILITIES[conflict_id][assignment.rank - 1]
    counts: dict[str, int] = {}
    for kind, _piece in _row_icons(row):
        counts[kind] = counts.get(kind, 0) + 1
    printed = list(dict.fromkeys(kind for kind, _piece in _row_icons(row)))
    if (
        assignment.rank is RewardRank.FIRST
        and state.conflict_first_place_influence_bonus
    ):
        # Pivotal Gambit (promo) adds "gain 1 Influence of your choice" to
        # this Conflict's first-place reward (OQ-025); like the printed
        # reward it is doubled by a sandworm [Main p. 14].
        counts["choose_influence"] = (
            counts.get("choose_influence", 0)
            + state.conflict_first_place_influence_bonus
        )
        if "choose_influence" not in printed:
            printed.append("choose_influence")
    multiplier = assignment.multiplier
    choam = state.config.choam_module
    icons: list[str] = []
    for kind in LEGACY_AUTOMATIC_ORDER:
        icons.extend([kind] * counts.get(kind, 0))
        if kind == "resources" and not choam:
            icons.extend(["contract"] * counts.get("contract", 0))
    if choam:
        icons.extend(["contract"] * counts.get("contract", 0))
    for _copy in range(multiplier):
        for kind in _LEGACY_COPY_CHOICES:
            icons.extend([kind] * counts.get(kind, 0))
    for kind in _LEGACY_LATER_CHOICES:
        icons.extend([kind] * (counts.get(kind, 0) * multiplier))
    # The original game's kinds, after every older one (no sandworm doubles
    # them: that board has none).
    for kind in ("mentat", "one_faction_influence", *REWARD_LINE_KINDS):
        icons.extend([kind] * counts.get(kind, 0))
    if assignment.rank is RewardRank.FIRST:
        # The first-place reward goes to a sole winner only (a tie for first
        # takes second place's [Main p. 14]), and its window holds what the
        # win sets off: Planetary Array's card is a row of it, the winner's to
        # order with the reward's icons, before the second place is paid
        # (OQ-121, user ruling 2026-10-25, "PA는 승자의 창 (추천)"; OQ-108
        # re-ruled). Not doubled by a sandworm: it is no reward. Last in the
        # fixed order the AI seats and older records follow.
        draws = tech_draws_on(state.players[assignment.player].tech_ids, OnConflictWon)
        if draws:
            icons.extend(["planetary_array"] * draws)
            printed.append("planetary_array")
        if winning_intrigue_is_hidden(state):
            # "When you win a Conflict" Intrigue (To the Victor..., Demand
            # Respect) is played in this window, in the winner's order with
            # the icons, and "안 내도 창이 닫힌다" (OQ-121 decision 6): the
            # window stays open for the plays until the seat closes it, last.
            # Whether the winner holds one is not shown: the closing row is
            # there on public facts alone (some copy is still in a deck or a
            # hand), as the Conflict-end window opens (OQ-103).
            icons.append(WINNING_INTRIGUE)
            printed.append(WINNING_INTRIGUE)
    context: dict[str, ActionValue] = {
        _ICONS_KEY: ",".join(icons),
        _PRINTED_KEY: ",".join(printed),
        _RANK_KEY: assignment.rank.value,
        _MULTIPLIER_KEY: multiplier,
        _CHOICE_INDEX_KEY: 0,
    }
    if _row_takes(row):
        context[_TAKES_KEY] = _row_takes(row)
        context[_CHOSEN_KEY] = ""
    return DecisionFrame(
        kind=FrameKind.COMBAT_REWARD_ICONS,
        frame_id=(
            f"round:{state.round_number}:combat_reward_icons:{assignment.player}:"
            f"{assignment.rank.value}"
        ),
        decision=PlayerDecision(
            owner=assignment.player, prompt="Resolve your Conflict reward"
        ),
        context=tuple(sorted(context.items())),
    )


def _pay_next_combat_reward(
    state: GameState, conflict_id: str, assignment: CombatReward
) -> RuleResult:
    """Open one ranked recipient's reward window (stage B2, OQ-112)."""

    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_reward:{assignment.player}:"
            f"{assignment.rank.value}"
        ),
        kind="combat_reward_gained",
        # The recipient's reward begins: what it gains comes icon by icon
        # (``combat_reward_icon_resolved`` and each gain's own event).
        payload=(
            ("multiplier", assignment.multiplier),
            ("player", assignment.player),
            ("rank", assignment.rank.value),
        ),
    )
    next_state = replace(
        state,
        combat_rewards_paid=state.combat_rewards_paid + 1,
        # The pledge goes into the first-place window; the first recipient
        # paid is the sole winner when there is one, so a tied first place
        # leaves the pledge unused and it is cleared here too.
        conflict_first_place_influence_bonus=0,
        decision_stack=(
            *state.decision_stack,
            _reward_window(state, conflict_id, assignment),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def _window_icons(frame: DecisionFrame) -> tuple[str, ...]:
    text = dict(frame.context)[_ICONS_KEY]
    return tuple(str(text).split(",")) if text else ()


@cache
def _winning_intrigue_instances() -> frozenset[str]:
    """Every Intrigue instance with a "When you win a Conflict" option (the
    original game's To the Victor... and Demand Respect)."""

    return frozenset(
        instance_id
        for instance_id, entry in INTRIGUE_CARDS_BY_INSTANCE.items()
        if any(isinstance(option.trigger, OnConflictWon) for option in entry.options)
    )


def winning_intrigue_is_hidden(state: GameState) -> bool:
    """Whether a winning Intrigue card is still in a deck or a hand.

    A fact every seat can work out: the discard pile and the cards face up
    are public, so the copies not in them are in the deck or a hand. It
    decides whether the sole winner's window carries the winning Intrigue row
    and its closing (``WINNING_INTRIGUE``) without telling the table whether
    the winner holds one (OQ-121, OQ-103). Uprising's Intrigue deck has none.
    """

    winning = _winning_intrigue_instances()
    return any(card in winning for card in state.intrigue_deck) or any(
        card in winning for seat in state.players for card in seat.intrigue_cards
    )


def winning_intrigue_window_is_open(state: GameState, player: int) -> bool:
    """Whether ``player``'s reward window is on top and still open for its
    winning Intrigue (its closing row is not pressed yet)."""

    frame = owned_top_frame(state, FrameKind.COMBAT_REWARD_ICONS, player)
    return frame is not None and WINNING_INTRIGUE in _window_icons(frame)


def legal_combat_reward_icon_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """One row per icon kind still to resolve, in printed order."""

    frame = owned_top_frame(state, FrameKind.COMBAT_REWARD_ICONS, player)
    if frame is None:
        return ()
    remaining = set(_window_icons(frame))
    printed = str(dict(frame.context)[_PRINTED_KEY]).split(",")
    if remaining & set(REWARD_LINE_KINDS) and chosen_reward_lines(frame):
        # "Choose two": both lines are named before either is paid (OQ-114,
        # OQ-057 (4)), so the second pick comes first.
        remaining &= set(REWARD_LINE_KINDS)
    if remaining != {WINNING_INTRIGUE}:
        # The winning Intrigue's close comes last: until then the seat may
        # still play one (also one a reward row draws, [FAQ p. 4]).
        remaining.discard(WINNING_INTRIGUE)
    return tuple(
        DomainAction(
            action_id=REWARD_ICON_ACTION, actor=player, arguments=(("effect", kind),)
        )
        for kind in printed
        if kind in remaining
    )


def legacy_combat_reward_icon(state: GameState, player: int) -> DomainAction | None:
    """The row the engine before stage B2 resolved next in ``player``'s
    reward window (its fixed order: the automatic part, then the choice
    frames as they were answered), or None outside one. An older record's
    bridge and the AI seats answer the window with it."""

    frame = owned_top_frame(state, FrameKind.COMBAT_REWARD_ICONS, player)
    if frame is None:
        return None
    icons = _window_icons(frame)
    if not icons:
        return None
    return DomainAction(
        action_id=REWARD_ICON_ACTION, actor=player, arguments=(("effect", icons[0]),)
    )


def apply_combat_reward_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one icon of the recipient's reward (OQ-112)."""

    player = action.actor
    frame = owned_top_frame(state, FrameKind.COMBAT_REWARD_ICONS, player)
    if frame is None:
        raise ValueError("no Conflict reward window is open for this seat")
    kind = dict(action.arguments).get("effect")
    icons = list(_window_icons(frame))
    if not isinstance(kind, str) or kind not in icons:
        raise ValueError(f"no {kind!r} icon waits in this reward")
    icons.remove(kind)
    context = dict(frame.context)
    rank = RewardRank(context_int(context, _RANK_KEY, owner="reward window"))
    multiplier = context_int(context, _MULTIPLIER_KEY, owner="reward window")
    index = context_int(context, _CHOICE_INDEX_KEY, owner="reward window")
    conflict_id = state.current_conflict_ids[-1]
    if kind in REWARD_LINE_KINDS:
        return _choose_reward_line(state, frame, player, kind, rank, icons)
    piece = reward_icon_piece(
        conflict_id, rank.value, kind, chosen_reward_lines(frame)
    )
    source = f"round:{state.round_number}:combat_reward:{player}:{rank.value}"

    # The choice frames this icon opens, in the order they are answered.
    opened: list[DecisionFrame] = []
    match kind:
        case "choose_influence":
            opened.append(_influence_choice_frame(state, player, index))
        case "one_faction_influence":
            assert isinstance(piece, GainInfluence)
            opened.append(
                _influence_choice_frame(state, player, index, times=piece.times)
            )
        case "optional_solari" | "optional_spice":
            assert isinstance(piece, EffectSection)
            (cost,) = piece.costs
            (points,) = piece.rewards
            assert isinstance(cost, PayResources)
            assert isinstance(points, GainVictoryPoints)
            resource = "solari" if kind == "optional_solari" else "spice"
            opened.append(
                _optional_payment_frame(
                    state,
                    player,
                    index,
                    resource,
                    cost.solari if resource == "solari" else cost.spice,
                    points.amount,
                )
            )
        case "optional_recall_spies":
            assert isinstance(piece, EffectSection)
            (cost,) = piece.costs
            (points,) = piece.rewards
            assert isinstance(cost, RecallSpy)
            assert isinstance(points, GainVictoryPoints)
            opened.append(
                _optional_spy_recall_frame(
                    state, player, index, cost.count, points.amount
                )
            )
        case "distinct_influence":
            assert isinstance(piece, GainInfluence)
            opened.extend(
                _distinct_influence_frame(state, player, index + pick, index)
                for pick in range(piece.times)
            )
        case "trash":
            opened.append(_trash_card_frame(state, player, index))
        case "spy" | "deep_cover_spy":
            opened.append(
                _spy_placement_frame(
                    state, player, index, deep_cover=kind == "deep_cover_spy"
                )
            )
        case "contract" if state.config.choam_module:
            assert isinstance(piece, TakeContract)
            opened.append(
                contract_choice_frame(player, piece.count * multiplier, source=source)
            )

    if icons:
        context[_ICONS_KEY] = ",".join(icons)
        context[_CHOICE_INDEX_KEY] = index + len(opened)
        stack = (*state.decision_stack[:-1], with_context(frame, context))
    else:
        stack = state.decision_stack[:-1]
    state = replace(state, decision_stack=stack)
    events: list[GameEvent] = []
    details: list[tuple[str, ActionValue]] = []
    if not opened:
        resolved = _resolve_automatic_icon(
            state, player, kind, piece, multiplier, source, rank
        )
        state = resolved.state
        events.extend(resolved.events)
        details.extend(_icon_details(state, kind, piece, multiplier))
    elif kind == "contract":
        # The Contract market takes the Contracts; the row says how many,
        # for the Combat result line (``render.js``).
        details.extend(_icon_details(state, kind, piece, multiplier))
    if kind != WINNING_INTRIGUE:
        # The window's own close is no reward: its seat gained nothing, so
        # the Combat result line has nothing to say for it.
        events.append(
            GameEvent(
                event_id=f"{source}:icon:{len(icons)}",
                kind="combat_reward_icon_resolved",
                payload=tuple(
                    sorted(
                        (
                            ("effect", kind),
                            ("player", player),
                            ("rank", rank.value),
                            *details,
                        )
                    )
                ),
            )
        )
    remaining = tuple(reversed(opened))
    state = replace(
        state,
        decision_stack=(*state.decision_stack, *remaining),
    )
    if not state.decision_stack:
        state = replace(
            state, combat_rewards_resolved=combat_rewards_done(state, ())
        )
    return RuleResult(state=state, events=tuple(events))


def _choose_reward_line(
    state: GameState,
    frame: DecisionFrame,
    player: int,
    kind: str,
    rank: RewardRank,
    icons: list[str],
) -> RuleResult:
    """Pick one line of the window's row of alternatives.

    The original game prints "-OR-" (one line) and "Choose two:" (two
    different lines, both named before either is paid: OQ-114, OQ-057 (4))
    on some Conflicts [DI p. 12]. Once the row has its lines, they become the
    window's icons, each resolved on its own (OQ-112): a public choice before
    the hidden Intrigue draw it may name (OQ-106). ``icons`` is the window's
    remaining icons, ``kind`` already removed.
    """

    context = dict(frame.context)
    chosen = (*chosen_reward_lines(frame), int(kind.removeprefix("line_")))
    takes = context_int(context, _TAKES_KEY, owner="reward window")
    if len(chosen) >= takes:
        icons = [icon for icon in icons if icon not in REWARD_LINE_KINDS]
        conflict_id = state.current_conflict_ids[-1]
        row = CONFLICT_REWARD_ABILITIES[conflict_id][rank.value - 1]
        added = [icon for icon, _piece in _row_icons(row, chosen)]
        # The winning Intrigue's close stays the last icon of the window.
        closing = [icon for icon in icons if icon == WINNING_INTRIGUE]
        icons = [icon for icon in icons if icon != WINNING_INTRIGUE]
        icons.extend(added)
        icons.extend(closing)
        printed = [
            icon
            for icon in str(context[_PRINTED_KEY]).split(",")
            if icon not in REWARD_LINE_KINDS and icon != WINNING_INTRIGUE
        ]
        context[_PRINTED_KEY] = ",".join(
            (*printed, *dict.fromkeys(added), *closing)
        )
    context[_CHOSEN_KEY] = ",".join(str(index) for index in chosen)
    context[_ICONS_KEY] = ",".join(icons)
    stack = (*state.decision_stack[:-1], with_context(frame, context))
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:combat_reward:{player}:{rank.value}:{kind}"
        ),
        kind="combat_reward_line_chosen",
        payload=(
            ("line", int(kind.removeprefix("line_"))),
            ("player", player),
            ("rank", rank.value),
        ),
    )
    return RuleResult(state=replace(state, decision_stack=stack), events=(event,))


def _icon_details(
    state: GameState,
    kind: str,
    piece: Reward | EffectSection | None,
    multiplier: int,
) -> tuple[tuple[str, ActionValue], ...]:
    """What an automatic icon gave, for its ``combat_reward_icon_resolved``
    (resources ride on ``resources_gained``)."""

    match kind, piece:
        case "troops", RecruitTroops(count=count):
            return (("troops", count * multiplier),)
        case "intrigue", DrawIntrigueCards(count=count):
            return (("intrigue", count * multiplier),)
        case "victory_points", GainVictoryPoints(amount=amount):
            return (("victory_points", amount * multiplier),)
        case "faction_influence", GainInfluence(times=times, factions=(faction,)):
            return (("faction", faction.value), ("influence", times * multiplier))
        case "control", TakeControl(space_id=space_id):
            return (("space_id", space_id),)
        case "contract", TakeContract(count=count):
            return (("contracts", count * multiplier),)
        case "planetary_array", None:
            return (("cards", 1),)
    return ()


def _with_owner(state: GameState, owner: PlayerState) -> GameState:
    return replace(state, players=replace_player(state.players, owner))


def _resolve_automatic_icon(
    state: GameState,
    player: int,
    kind: str,
    piece: Reward | EffectSection | None,
    multiplier: int,
    source: str,
    rank: RewardRank,
) -> RuleResult:
    """Pay one automatic icon of a Conflict reward (doubled by a sandworm,
    control excepted)."""

    owner = state.players[player]
    match kind, piece:
        case "intrigue", DrawIntrigueCards(count=count):
            wanted = count * multiplier
            deck = state.intrigue_deck
            drawn = deck[:wanted]
            events: tuple[GameEvent, ...] = (
                (
                    GameEvent(
                        event_id=f"{source}:intrigue_draw:{len(deck)}",
                        kind="intrigue_card_drawn",
                        payload=(("count", len(drawn)), ("player", player)),
                    ),
                )
                if drawn
                else ()
            )
            pending = state.pending_intrigue_draws
            if wanted > len(drawn):
                # Deck exhausted: the dispatcher reshuffles the discard
                # [FAQ p. 2].
                pending = (
                    *pending,
                    (
                        player,
                        wanted - len(drawn),
                        (
                            f"round:{state.round_number}:combat_reward:intrigue:"
                            f"{player}:{rank.value}"
                        ),
                    ),
                )
            next_owner = replace(
                owner, intrigue_cards=(*owner.intrigue_cards, *drawn)
            )
            return RuleResult(
                state=replace(
                    _with_owner(state, next_owner),
                    intrigue_deck=deck[len(drawn) :],
                    pending_intrigue_draws=pending,
                ),
                events=events,
            )
        case "troops", RecruitTroops(count=count):
            recruited_owner, recruited = recruit_troops(owner, count * multiplier)
            return RuleResult(
                state=_with_owner(state, recruited_owner),
                events=recruit_shortfall_events(
                    source, player, count * multiplier, recruited
                ),
            )
        case "resources", GainResources(solari=solari, spice=spice, water=water):
            next_owner = replace(
                owner,
                resources=Resources(
                    solari=owner.resources.solari + solari * multiplier,
                    spice=owner.resources.spice + spice * multiplier,
                    water=owner.resources.water + water * multiplier,
                ),
            )
            return RuleResult(
                state=_with_owner(state, next_owner),
                events=(
                    resources_gained_event(
                        source,
                        player,
                        solari=solari * multiplier,
                        spice=spice * multiplier,
                        water=water * multiplier,
                    ),
                ),
            )
        case "victory_points", GainVictoryPoints(amount=amount):
            next_owner = replace(
                owner, victory_points=owner.victory_points + amount * multiplier
            )
            return RuleResult(state=_with_owner(state, next_owner))
        case "mentat", TakeMentat():
            # Sort Through the Chaos: the winner takes the Mentat "at the
            # start of the next round" [FAQ p. 4] and keeps it as an Agent
            # for that round [DI p. 16] (``phases.begin_round``).
            return RuleResult(
                state=replace(state, mentat_owed_to=player),
                events=(
                    GameEvent(
                        event_id=f"{source}:mentat",
                        kind="mentat_won",
                        payload=(("player", player),),
                    ),
                ),
            )
        case "winning_intrigue", None:
            # The window's own close: nothing is gained (the plays it ends
            # were cards of their own, ``intrigue.apply_intrigue_play``).
            return RuleResult(state=state)
        case "planetary_array", None:
            # "When you win a Conflict: draw a card" [Planetary Array Tech
            # tile], drawn as this row resolves, before the next place is
            # paid (OQ-121); its reshuffle keeps the Tech draw's decision id.
            return draw_or_request_personal_cards(
                state,
                player,
                1,
                source=f"round:{state.round_number}:player:{player}:tech_draw",
            )
        case "contract", TakeContract(count=count):
            # Without the CHOAM Module a Contract icon is 2 Solari
            # [Main pp. 16, 20].
            solari = 2 * count * multiplier
            next_owner = replace(
                owner,
                resources=replace(
                    owner.resources, solari=owner.resources.solari + solari
                ),
            )
            return RuleResult(
                state=_with_owner(state, next_owner),
                events=(
                    resources_gained_event(f"{source}:contract", player, solari=solari),
                ),
            )
        case "faction_influence", GainInfluence(times=times, factions=(faction,)):
            return gain_faction_influence(
                state,
                player,
                faction,
                times * multiplier,
                event_prefix=(
                    f"round:{state.round_number}:combat_reward:fixed_influence:"
                    f"{player}:{rank.value}"
                ),
            )
        case "control", TakeControl(space_id=space_id):
            events_list: list[GameEvent] = []
            scouts_goods = state.scouts_goods
            if space_id not in owner.control_space_ids:
                # Arrakeen Scouts' Prison Planet may hold this seat's last
                # marker.
                scouts_goods, released = free_prison_marker(
                    scouts_goods,
                    player,
                    len(owner.control_space_ids),
                    source=f"round:{state.round_number}:combat_reward",
                )
                events_list.extend(released)
            return RuleResult(
                state=replace(
                    state,
                    players=_apply_control(state.players, player, space_id),
                    scouts_goods=scouts_goods,
                ),
                events=tuple(events_list),
            )
    raise ValueError(f"{kind!r} is not an automatic Conflict reward icon")


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
    source = (
        f"round:{state.round_number}:combat_reward:optional:"
        f"{choice_index}:{action.actor}"
    )
    if paid:
        # The payment, then what it bought (cleanup-2c-6).
        return RuleResult(
            state=next_state,
            events=(
                resources_paid_event(source, action.actor, **{resource: cost}),
                *(
                    (
                        resources_gained_event(
                            source, action.actor, victory_points=victory_points
                        ),
                    )
                    if victory_points
                    else ()
                ),
            ),
        )
    event = GameEvent(
        event_id=source,
        kind="combat_reward_declined",
        payload=(("player", action.actor), ("resource", resource)),
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
        # No zero amounts (cleanup-2c-6, the event grammar).
        payload=(
            (
                ("player", action.actor),
                ("spies", spy_count),
                ("victory_points", victory_points),
            )
            if paid
            else (("player", action.actor),)
        ),
    )
    return RuleResult(state=next_state, events=(event,))


COMBAT_TRASH_NO_CARD: Final = "resolve_combat_trash_without_card"


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
    cards = trashable_cards(state.players[player])
    if not cards:
        # No card to trash: its owner confirms (user ruling 2026-09-30, "결정
        # 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다"; cleanup-2f).
        return (DomainAction(action_id=COMBAT_TRASH_NO_CARD, actor=player),)
    return (
        DomainAction(action_id="decline_combat_reward_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_combat_reward_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in cards
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
    if action.action_id == COMBAT_TRASH_NO_CARD:
        working_state = state
        events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:combat_reward:trash_unavailable:"
                    f"{choice_index}:{action.actor}"
                ),
                kind="combat_reward_trash_unavailable",
                payload=(("choice_index", choice_index), ("player", action.actor)),
            ),
        )
    elif declined:
        card_id = ""
        working_state = state
        # One kind for a refused optional trash, wherever it is offered
        # (cleanup-2c-6).
        events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:combat_reward:trash:"
                    f"{choice_index}:{action.actor}:trash_declined"
                ),
                kind="optional_trash_declined",
                payload=(("player", action.actor),),
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
    options = spy_options(
        state, player, None, shared_post=dict(frame.context).get("deep_cover") is True
    )
    return (
        *(
            (DomainAction(action_id="decline_combat_reward_spy", actor=player),)
            if options.pass_up
            else ()
        ),
        *(
            DomainAction(
                action_id="recall_spy_for_combat_reward",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.recall
        ),
        *(
            DomainAction(
                action_id="place_combat_reward_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.place
        ),
    )


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
    # Two Influence with one Faction gain both there; a track tops out at 6
    # (OQ-060).
    times = frame_context_int(frame, "times") or 1
    gained = gain_faction_influence(
        state,
        action.actor,
        faction,
        times,
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
    """Whether playing ``option`` now could change something.

    "To play an Intrigue card, you must meet its conditions and pay its
    costs." [FAQ p. 2]. Harvest Cells has no cost, so it is offered in its
    window either way (OQ-113 (C), user ruling 2026-10-24, (2) 6); the page
    warns before a play that would change nothing. The window
    opens once the Conflict's troops are back in the supply ("When
    resolving combat, troops that return to your supply are considered
    'lost.'" [FAQ p. 1]) and the card resolves as it is played (user
    decision 2026-10-18), so its specimens can be made while the supply
    holds a troop ("take a troop from your supply" [Immortality p. 8];
    Sardaukar Commanders go back to their own supply [Bloodlines p. 4] and
    make none). Otherwise its Tleilaxu card can still be bought if the
    seat's specimens pay for a Row card or a Reclaimed Forces effect.
    """

    from dune_imperium.rules.tleilaxu_row import (
        RECLAIMED_FORCES_CHOICES,
        reclaimed_forces_block,
    )

    owner = state.players[player]
    if _trigger_specimens(option) and owner.troops_supply >= 1:
        return True
    if not any(
        isinstance(reward, AcquireTleilaxuCard)
        for section in option.sections
        for reward in section.rewards
    ):
        return False
    return any(
        tleilaxu_card_for_instance(instance_id).specimen_cost <= owner.specimens
        for instance_id in state.tleilaxu_row
    ) or any(
        reclaimed_forces_block(owner, choice) is None
        for choice in RECLAIMED_FORCES_CHOICES
    )


# A Conflict-end window's context: the units its seat lost as they went
# back to the supply, and whether the seat played a card in it.
_LOST_KEY: Final = "lost"
_PLAYED_KEY: Final = "played"


class ConflictEndTriggerBlock(StrEnum):
    """Why a held Conflict-end trigger card is not offered in its window.

    ``conflict_end_trigger_block`` returns one of these, or the option's own
    reason (``option_unplayable_reason``); the window offers exactly the
    cards without a block (``_conflict_end_trigger_cards``), and the page
    greys out the others with that reason (``display.unavailable``, user
    request 2026-09-29).
    """

    # Fewer units left the Conflict than the trigger names.
    LOSS = "loss"


def conflict_end_trigger_block(
    state: GameState, player: int, option: IntrigueOption, lost: int | None = None
) -> ConflictEndTriggerBlock | OptionUnplayable | None:
    """Why ``player`` may not play ``option``, a Conflict-end loss trigger,
    in its Conflict-end window now, or None when it may.

    In order: the trigger's loss ("When you lose at least three troops at
    the end of a Conflict:" [Harvest Cells card]; ``lost`` defaults to the
    seat's loss, ``conflict_end_loss``), then the play's own conditions and
    costs (``option_unplayable_reason``). A copy that could change nothing
    is offered too: the card has no cost (OQ-113 (C), user ruling
    2026-10-24, (2) 6).
    """

    from dune_imperium.rules.effect_interpreter import option_unplayable_reason

    trigger = option.trigger
    if not isinstance(trigger, OnTroopsLostAtConflictEnd):
        raise ValueError("not a Conflict-end loss trigger")
    if lost is None:
        lost = conflict_end_loss(state, player)
    if lost < trigger.minimum:
        return ConflictEndTriggerBlock.LOSS
    return option_unplayable_reason(state, player, option)


def _conflict_end_trigger_cards(
    state: GameState, player: int, lost: int
) -> tuple[str, ...]:
    """Hand Intrigue whose Conflict-end trigger would fire now and is
    playable (``conflict_end_trigger_block``)."""

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


def conflict_end_loss(state: GameState, player: int) -> int:
    """The units ``player`` lost at this Conflict's end: as its window
    recorded them once they went back to the supply, or, before the
    return, those still in the Conflict."""

    for frame in reversed(state.decision_stack):
        if frame.kind == FrameKind.CONFLICT_END_TRIGGER and isinstance(
            frame.decision, PlayerDecision
        ):
            if frame.decision.owner == player:
                return context_int(
                    dict(frame.context), _LOST_KEY, owner="Conflict-end Intrigue window"
                )
    return _conflict_losses(state)[player]


def _return_conflict_units(
    state: GameState, losses: tuple[int, ...]
) -> RuleResult:
    """Every seat's troops and Sardaukar Commanders leave the Conflict for
    the supply: "Once all rewards have been given, each player takes their
    troops from the Conflict and puts them in their supply" [Main p. 14]
    [Bloodlines p. 4], and "troops that return to your supply are
    considered 'lost.'" [FAQ p. 1]. The Tactician token advances once by the
    whole loss, the cleanup being one source [Chani card]. The Conflict card
    went to its winner just before (``_award_conflict``, OQ-108); sandworms
    and the Combat markers wait for ``finish_combat``.

    A dreadnought never goes to the supply: "끈질김. Combat이 해결되면
    Conflict의 dreadnought는 supply로 가지 않는다" and it goes to the garrison
    "troop을 supply로 돌리는 정리 단계에서 함께" (OQ-121 ruling 2,
    docs/rules/rise-of-ix.md 6) [Rise of Ix p. 6]. It is no troop, so it is not
    "lost" (``_conflict_losses`` counts troops and Commanders only)."""

    players = tuple(
        replace(
            player,
            troops_supply=player.troops_supply + player.troops_conflict,
            troops_conflict=0,
            commanders_supply=player.commanders_supply + player.commanders_conflict,
            commanders_conflict=0,
            dreadnoughts_garrison=(
                player.dreadnoughts_garrison + player.dreadnoughts_conflict
            ),
            dreadnoughts_conflict=0,
        )
        for player in state.players
    )
    advanced = [
        advance_tactics_token(player, lost, round_number=state.round_number)
        for player, lost in zip(players, losses, strict=True)
    ]
    return RuleResult(
        state=replace(state, players=tuple(player for player, _ in advanced)),
        events=tuple(
            event for _, tactics_events in advanced for event in tactics_events
        ),
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
    """Award the Conflict card, return the Conflict's units, then open the
    window for Intrigue that triggers at this Conflict's end.

    The winner takes the Conflict card once every reward is resolved
    (``_award_conflict``, OQ-108). The troops go back to the supply next
    (``_return_conflict_units``):
    that return is the loss ("troops that return to your supply are
    considered 'lost.'" [FAQ p. 1]), so a card that triggers on it resolves
    as it is played, with the troops back for its specimens (user decision
    2026-10-18). Each seat's loss rides on its window. Harvest Cells is
    played only here, after the rewards: "This card is played after combat
    resolves." (designer ruling, OQ-057 (11); ``IntriguePlayBlock.
    CONFLICT_END`` keeps it out of Combat Intrigue). Each seat, in turn
    order from the First Player (OQ-002), may play a hand card whose
    Conflict-end trigger fires -- one held from earlier or one just received
    as a reward.

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
    awarded = _award_conflict(state)
    losses = _conflict_losses(awarded.state)
    returned = _return_conflict_units(awarded.state, losses)
    state = returned.state
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
                context=((_LOST_KEY, losses[player]), ("player", player)),
            )
        )
    next_state = replace(
        state,
        combat_end_triggers_offered=True,
        decision_stack=tuple(reversed(frames)),
    )
    return RuleResult(
        state=next_state,
        events=(
            *awarded.events,
            *returned.events,
            *(
                GameEvent(
                    event_id=f"{frame.frame_id}:offered",
                    kind="conflict_end_trigger_offered",
                    payload=(("player", dict(frame.context)["player"]),),
                )
                for frame in frames
            ),
        ),
    )


def legal_conflict_end_trigger_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Play one of the seat's Conflict-end trigger cards now, or decline --
    or, once a card is played in this window, finish it ("끝내기", user
    decision 2026-10-18: the window stays open after a play, OQ-103, and its
    one press no longer reads as declining)."""

    frame = owned_top_frame(state, FrameKind.CONFLICT_END_TRIGGER, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    lost = context_int(context, _LOST_KEY, owner="Conflict-end Intrigue window")
    end = (
        "finish_conflict_end_intrigue"
        if context.get(_PLAYED_KEY) is True
        else "decline_conflict_end_intrigue"
    )
    return (
        DomainAction(action_id=end, actor=player),
        *(
            DomainAction(
                action_id="play_conflict_end_intrigue",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in _conflict_end_trigger_cards(state, player, lost)
        ),
    )


def spent_conflict_end_window(state: GameState) -> bool:
    """Whether a Conflict-end window a card was played in is back on top
    with its seat holding no Intrigue card: nothing is left to decide there
    (OQ-103, OQ-109), and the engine closes it (``close_spent_conflict_end_
    window``) as the play used to when it left the hand empty."""

    if not state.decision_stack:
        return False
    frame = state.decision_stack[-1]
    if (
        frame.kind != FrameKind.CONFLICT_END_TRIGGER
        or dict(frame.context).get(_PLAYED_KEY) is not True
        or not isinstance(frame.decision, PlayerDecision)
    ):
        return False
    return not state.players[frame.decision.owner].intrigue_cards


def close_spent_conflict_end_window(state: GameState) -> RuleResult:
    """Close a played Conflict-end window whose seat holds no Intrigue card."""

    if not spent_conflict_end_window(state):
        raise ValueError("the Conflict-end window on top is not spent")
    return RuleResult(state=state.pop_decision())


def apply_conflict_end_trigger(state: GameState, action: DomainAction) -> RuleResult:
    """Play the chosen hand card, resolving it at once, or close the window.

    The troops already went back to the supply as the window opened, so the
    loss the card names has happened: "When you lose at least three troops
    at the end of a Conflict:" [Harvest Cells card], "When resolving combat,
    troops that return to your supply are considered 'lost.'" [FAQ p. 1].
    Its specimens come at once from the supply ("take a troop from your
    supply" [Immortality p. 8]) and only its "You may also acquire a
    Tleilaxu card" is asked (user decision 2026-10-18,
    ``intrigue.resolve_conflict_end_trigger``).
    """

    if action not in legal_conflict_end_trigger_actions(state, action.actor):
        raise ValueError("action is not a legal Conflict-end Intrigue choice")
    from dune_imperium.rules.intrigue import (
        resolve_conflict_end_trigger,
        without_effect_event,
    )

    player = action.actor
    frame = state.decision_stack[-1]
    if action.action_id in (
        "decline_conflict_end_intrigue",
        "finish_conflict_end_intrigue",
    ):
        finished = action.action_id == "finish_conflict_end_intrigue"
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=(
                        f"{frame.frame_id}:{'finished' if finished else 'declined'}"
                    ),
                    kind=(
                        "conflict_end_trigger_finished"
                        if finished
                        else "conflict_end_trigger_declined"
                    ),
                    payload=(("player", player),),
                ),
            ),
        )
    card_id = str(dict(action.arguments)["card_id"])
    # The window stays open while the seat holds an Intrigue card, a public
    # fact: closing it only when no other copy could change something would
    # tell the table whether a second Harvest Cells is in the hand (OQ-103).
    # Whether it is still holding one is judged when the window comes back
    # on top (``spent_conflict_end_window``), so a card the played one's
    # acquisition drew -- a Tleilaxu track Intrigue space -- may be played
    # too (user decision 2026-10-18, OQ-109).
    window = replace_top_frame(
        state, with_context(frame, {**dict(frame.context), _PLAYED_KEY: True})
    )
    played = GameEvent(
        event_id=f"{frame.frame_id}:played:{card_id}",
        kind="intrigue_played",
        payload=(("card_id", card_id), ("player", player)),
    )
    source = f"round:{state.round_number}:player:{player}:conflict_end:{card_id}"
    option = _loss_trigger_option(card_id)
    assert option is not None
    # A copy that changes nothing is played all the same (OQ-113 (C)) and
    # noted, as the page warned (``intrigue.without_effect_event``).
    noted = (
        ()
        if _harvest_cells_has_effect(window, player, option)
        else (without_effect_event(source, card_id, player),)
    )
    resolved = resolve_conflict_end_trigger(window, player, card_id, source=source)
    return RuleResult(
        state=resolved.state, events=(played, *noted, *resolved.events)
    )


def _award_conflict(state: GameState) -> RuleResult:
    """The sole winner takes the Conflict card: "모든 순위 보상을 처리한 뒤,
    승자는 Conflict 카드를 face-up 상태로 자신의 supply에 놓고 battle icon
    일치를 확인한다. [Main p. 14]" (docs/rules/combat-and-round-end.md), before
    the cleanup returns the troops (user decision 2026-10-18, OQ-108). A tie
    leaves the card on the board [Main pp. 8, 14]. Planetary Array's card
    ("When you win a Conflict: draw a card") is no longer drawn here but in
    the winner's reward window (OQ-121, user ruling 2026-10-25; OQ-108
    re-ruled): the win sets it off, the Conflict card's award is a step of
    its own after every place's reward [Main p. 14]."""

    if not state.current_conflict_ids:
        raise ValueError("Combat cleanup requires a current Conflict")
    conflict_id = state.current_conflict_ids[-1]
    ranking = rank_combat(state.players)
    if ranking.winner is None:
        return RuleResult(state=state)
    if state.config.base_game is BaseGame.IMPERIUM:
        # The original game's Conflict cards stay where they were revealed,
        # the next one "on top of any Conflict cards from previous rounds"
        # [DI p. 8]: no winner takes one, and none prints a battle icon
        # (docs/rules/imperium-base.md 2, 10).
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:conflict_won:{ranking.winner}"
                    ),
                    kind="conflict_won",
                    payload=(("conflict_id", conflict_id), ("player", ranking.winner)),
                ),
            ),
        )
    players = state.players
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
    match_events: tuple[GameEvent, ...] = ()
    if fleet:
        # Ornithopter Fleet: every icon is an Ornithopter, so the new
        # card pairs with any face-up one [Bloodlines p. 12].
        winner, match_events = match_all_battle_icons(
            winner, source=f"round:{state.round_number}:conflict_won"
        )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"round:{state.round_number}:conflict_won:{ranking.winner}",
            kind="conflict_won",
            payload=(("conflict_id", conflict_id), ("player", ranking.winner)),
        )
    ]
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
    return RuleResult(
        state=replace(
            state,
            players=replace_player(players, winner),
            current_conflict_ids=state.current_conflict_ids[:-1],
        ),
        events=tuple(events),
    )


def finish_combat(state: GameState) -> RuleResult:
    """Finish the Combat cleanup and enter Makers.

    The Conflict card went to its winner and the troops and Sardaukar
    Commanders back to the supply as the Conflict-end windows opened
    (``offer_conflict_end_triggers``); sandworms return to the bank and
    every Combat marker to 0 now [Main p. 14]. Rise of Ix's dreadnoughts on
    Control spaces take their turn last: the ones leaving go back to their
    garrisons and the rest become leaving, winner or none
    (``dreadnoughts.end_combat_dreadnoughts``) [Rise of Ix p. 6]
    (docs/rules/rise-of-ix.md 6, OQ-121 ruling 1).
    """

    if state.phase is not GamePhase.COMBAT:
        raise ValueError("Combat can finish only during Combat")
    if not state.combat_rewards_resolved:
        raise ValueError("Combat rewards must resolve before cleanup")
    if state.decision_stack:
        raise ValueError("Combat cannot finish with a pending decision")
    if any(
        player.troops_conflict
        or player.commanders_conflict
        or player.dreadnoughts_conflict
        for player in state.players
    ):
        raise RuntimeError("the Conflict's units return before the cleanup")
    players = tuple(
        replace(
            player,
            sandworms_conflict=0,
            # Into the Fray's Agent comes back too (it is recalled with the
            # others in the Recall phase either way) [Duncan Idaho card].
            agents_available=player.agents_available + player.agent_in_conflict,
            agent_in_conflict=0,
            combat_strength=0,
            skill_strength_applied=0,
        )
        for player in state.players
    )
    next_state = replace(
        state,
        phase=GamePhase.MAKERS,
        players=players,
        combat_intrigue_players=(),
    )
    # The Combat phase's last act (OQ-121 ruling 1).
    ended = end_combat_dreadnoughts(next_state)
    return RuleResult(
        state=ended.state,
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:combat_cleanup",
                kind="combat_cleaned_up",
            ),
            *ended.events,
        ),
    )


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
    *,
    times: int = 1,
) -> DecisionFrame:
    """A chosen Faction's Influence; ``times`` more than once with that one
    Faction (Grand Vision's two-chevron icon [DI p. 16])."""

    return DecisionFrame(
        kind=FrameKind.COMBAT_REWARD_INFLUENCE,
        frame_id=(
            f"round:{state.round_number}:combat_reward_influence:{index}:{player}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt=(
                "Choose a faction to gain one Influence"
                if times == 1
                else f"Choose a faction to gain {times} Influence"
            ),
        ),
        context=(
            ("choice_index", index),
            ("player", player),
            *((("times", times),) if times > 1 else ()),
        ),
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


