"""The Rise of Ix Shipping track and the Freighter (stage P4c-3).

"Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수 있다("may"): 한
칸 위로(맨 위면 불가) 또는 맨 아래로 회수. 회수하면 지금 칸과 그 아래 모든
칸의 보상을 **원하는 순서로** 받는다." (docs/rules/rise-of-ix.md 5, [Rise of Ix
p. 5]). The spaces' rewards, bottom to top: "1. 고르기: Dividends(5 Solari,
상대마다 1 Solari) -OR- spice 2. 2. troop 2 recruit + 진영 하나에 Influence 1.
3. Tech Discount 2로 Acquire Tech." The Freighter starts on the bottom, space
0, which pays nothing (``PlayerState.freighter_space``, 0 to 3).

A Freighter icon is the DSL piece ``effect_dsl.Freighter``, offered by whatever
prints it through the executor (``ability_executor``): up one space, recall,
or neither. Where no executor frame owns the icon -- a Conflict reward's
Freighter, "자기 turn 밖" [FAQ p. 3] -- ``freighter_move_frame`` builds the
window ``FrameKind.FREIGHTER_MOVE`` with the same three answers
(``advance_freighter``, ``recall_freighter``, ``decline_freighter``): the
recipient's reward window opens one for each Freighter icon of its row
(``combat.FREIGHTER``, stage P4d-1).

A recall owes the rewards of the Freighter's space and every space below it,
one row each (``resolve_shipping_reward``) in the order the seat picks:
inside its own turn the rows wait on the turn's frame beside the turn's other
effects (``turn_rows.SHIPPING_REWARD``, as a Contract's icons do, OQ-112 (4));
outside it they are the window ``FrameKind.SHIPPING_REWARD_ICONS``. Both
write the spaces still owed where ``core.observation.ix_pending_of`` reads
them. A row is named by its effect: ``dividends`` or ``spice`` (space 1, "고르기"),
``recruit`` (space 2, with the ``faction`` that gains the Influence) and
``tech`` (space 3, the Acquire Tech at Tech Discount 2).

Troops recruited in the owner's own turn join that turn's deployment
allowance ("회수로 recruit한 troop은 Combat 칸에 Agent를 보낸 turn이면
배치할 수 있다" [FAQ p. 4]); outside the owner's turn -- in Combat -- they
stay in the garrison ("Combat 중에 recruit한 troop은 garrison으로", designer
ruling, BGG forum). Troop Transports adds one more troop to each recruit
("Shipping track에서 troop을 recruit할 때마다 하나 더", [Rise of Ix p. 4]).
"""

from copy import replace
from typing import Final

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import SHIPPING_REWARDS_KEY
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.combat_deployment import (
    grant_shipping_troop_deployment,
    note_ungained_shipping_troops,
)
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    own_turn_frame_index,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    update_turn_recruits,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.influence import gain_faction_influence, influence_can_rise
from dune_imperium.rules.tech import push_tech_acquisition

SHIPPING_TOP: Final = 3
"""The Freighter's top space; the bottom is 0 and pays nothing."""

ADVANCE_ACTION: Final = "advance_freighter"
RECALL_ACTION: Final = "recall_freighter"
DECLINE_ACTION: Final = "decline_freighter"
REWARD_ACTION: Final = "resolve_shipping_reward"

PRINTED: Final = "shipping_track"
"""The entity that prints the track's rewards (``printer_value``)."""

DIVIDENDS: Final = "dividends"
SPICE: Final = "spice"
RECRUIT: Final = "recruit"
INFLUENCE: Final = "influence"
TECH: Final = "tech"

# The rewards a recall owes, in the order the track prints them: space 1's
# choice, space 2's two (its recruit and its Influence, separately printed, so
# each its own reward, OQ-148), space 3's Acquire Tech. A reward is named by
# ``"<space>"`` or, where a space prints two, ``"<space>:<part>"``.
CHOICE_REWARD: Final = "1"
RECRUIT_REWARD: Final = "2:recruit"
INFLUENCE_REWARD: Final = "2:influence"
TECH_REWARD: Final = "3"
SPACE_REWARDS: Final = {
    1: (CHOICE_REWARD,),
    2: (RECRUIT_REWARD, INFLUENCE_REWARD),
    3: (TECH_REWARD,),
}
REWARD_ORDER: Final = tuple(
    reward for rewards in SPACE_REWARDS.values() for reward in rewards
)
REWARD_EFFECTS: Final = {
    CHOICE_REWARD: (DIVIDENDS, SPICE),
    RECRUIT_REWARD: (RECRUIT,),
    INFLUENCE_REWARD: (INFLUENCE,),
    TECH_REWARD: (TECH,),
}
EFFECT_REWARD: Final = {
    effect: reward for reward, effects in REWARD_EFFECTS.items() for effect in effects
}
"""The reward each row's effect takes."""

DIVIDENDS_SOLARI: Final = 5
DIVIDENDS_OPPONENT_SOLARI: Final = 1
SPICE_REWARD: Final = 2
RECRUITED_TROOPS: Final = 2
TECH_DISCOUNT: Final = 2

_FRAME: Final = "Shipping track frame"


def freighter_can_advance(state: GameState, player: int) -> bool:
    """Whether ``player``'s Freighter can move up: "한 칸 위로(맨 위면 불가)"
    [Rise of Ix p. 5]."""

    return state.players[player].freighter_space < SHIPPING_TOP


def freighter_can_recall(state: GameState, player: int) -> bool:
    """Whether a recall changes anything: from the bottom it moves nothing and
    pays nothing, so no row offers it (the bottom is no space with a reward)."""

    return state.players[player].freighter_space > 0


def move_freighter_up(state: GameState, player: int, *, source: str) -> RuleResult:
    """Move ``player``'s Freighter up one space [Rise of Ix p. 5]."""

    if not freighter_can_advance(state, player):
        raise ValueError("the Freighter is on the top space")
    owner = state.players[player]
    moved = replace(owner, freighter_space=owner.freighter_space + 1)
    return RuleResult(
        state=replace(state, players=replace_player(state.players, moved)),
        events=(
            GameEvent(
                event_id=f"{source}:freighter_moved",
                kind="freighter_moved",
                payload=(("player", player), ("space", moved.freighter_space)),
            ),
        ),
    )


def recall_freighter(state: GameState, player: int, *, source: str) -> RuleResult:
    """Recall ``player``'s Freighter to the bottom and owe the rewards of the
    space it left and of every space below it, in the order the seat picks
    (module docstring)."""

    if not freighter_can_recall(state, player):
        raise ValueError("the Freighter is on the bottom: a recall pays nothing")
    owner = state.players[player]
    left = owner.freighter_space
    recalled = replace(owner, freighter_space=0)
    working = replace(state, players=replace_player(state.players, recalled))
    owed = tuple(
        reward for space in range(1, left + 1) for reward in SPACE_REWARDS[space]
    )
    return RuleResult(
        state=_owe(working, player, owed, source),
        events=(
            GameEvent(
                event_id=f"{source}:freighter_recalled",
                kind="freighter_recalled",
                payload=(("from_space", left), ("player", player)),
            ),
        ),
    )


def _owe(
    state: GameState, player: int, rewards: tuple[str, ...], source: str
) -> GameState:
    """The rewards a recall owes, one row each: waiting on the owner's own
    turn, else in a window of their own."""

    if turn_rows.waits_on_turn(state, player):
        for reward in rewards:
            queued = turn_rows.queue(
                state, player, (turn_rows.SHIPPING_REWARD, source, reward)
            )
            assert queued is not None
            state = queued
        return state
    return state.push_decision(
        DecisionFrame(
            kind=FrameKind.SHIPPING_REWARD_ICONS,
            frame_id=f"{source}:shipping_rewards",
            decision=PlayerDecision(
                owner=player, prompt="Gain your Shipping track rewards"
            ),
            context=tuple(
                sorted(
                    (
                        (SHIPPING_REWARDS_KEY, _rewards_text(rewards)),
                        ("source", source),
                    )
                )
            ),
        )
    )


def _rewards_text(rewards: tuple[str, ...]) -> str:
    return ",".join(rewards)


def reward_rows(
    state: GameState, player: int, rewards: tuple[str, ...]
) -> tuple[DomainAction, ...]:
    """The rows that take the owed ``rewards``, in the track's order: space
    1's choice of Dividends or spice, space 2's recruit, space 2's Influence
    once for each Faction that can still rise (OQ-060: with every cube at the
    top the Influence is lost and its owner confirms it, one row without a
    Faction), space 3's Acquire Tech. They are separate rewards, so every
    owed one is offered at once, in whatever order the seat picks (OQ-148,
    [Rise of Ix p. 5])."""

    owner = state.players[player]
    rows: list[DomainAction] = []
    for reward in sorted(set(rewards), key=REWARD_ORDER.index):
        for effect in REWARD_EFFECTS[reward]:
            if effect != INFLUENCE:
                rows.append(_row(player, effect))
                continue
            factions = [f for f in Faction if influence_can_rise(owner, f)]
            if not factions:
                rows.append(_row(player, effect))
            rows.extend(_row(player, effect, faction) for faction in factions)
    return tuple(rows)


def _row(player: int, effect: str, faction: Faction | None = None) -> DomainAction:
    arguments: list[tuple[str, ActionValue]] = [("effect", effect)]
    if faction is not None:
        arguments.append(("faction", faction.value))
    return DomainAction(
        action_id=REWARD_ACTION, actor=player, arguments=tuple(sorted(arguments))
    )


def _window_rewards(state: GameState, player: int) -> tuple[str, ...] | None:
    frame = owned_top_frame(state, FrameKind.SHIPPING_REWARD_ICONS, player)
    if frame is None:
        return None
    text = dict(frame.context)[SHIPPING_REWARDS_KEY]
    return tuple(reward for reward in str(text).split(",") if reward)


def legal_shipping_reward_row_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row for each reward waiting on ``player``'s own turn (module
    docstring), every owed reward's at once."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return ()
    rewards = tuple(
        value
        for kind, _source, value in turn_rows.pending(frame)
        if kind == turn_rows.SHIPPING_REWARD
    )
    return reward_rows(state, player, rewards) if rewards else ()


def legal_shipping_reward_window_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row for each reward still owed in ``player``'s window."""

    rewards = _window_rewards(state, player)
    return () if rewards is None else reward_rows(state, player, rewards)


def apply_shipping_reward(state: GameState, action: DomainAction) -> RuleResult:
    """Take one Shipping track reward: a row of the owner's turn or of its
    window."""

    player = action.actor
    arguments = dict(action.arguments)
    effect = str(arguments["effect"])
    reward = EFFECT_REWARD[effect]
    window = _window_rewards(state, player)
    if window is not None:
        if action not in legal_shipping_reward_window_actions(state, player):
            raise ValueError("action is not a legal Shipping track reward")
        frame = state.decision_stack[-1]
        source = context_str(dict(frame.context), "source", owner=_FRAME)
        remaining = list(window)
        remaining.remove(reward)
        if remaining:
            context = dict(frame.context)
            context[SHIPPING_REWARDS_KEY] = _rewards_text(tuple(remaining))
            state = replace_top_frame(state, with_context(frame, context))
        else:
            state = state.pop_decision()
    else:
        if action not in legal_shipping_reward_row_actions(state, player):
            raise ValueError("action is not a legal Shipping track reward")
        rows_frame = turn_rows.rows_frame(state, player)
        assert rows_frame is not None
        item = next(
            item
            for item in turn_rows.pending(rows_frame)
            if item[0] == turn_rows.SHIPPING_REWARD and item[2] == reward
        )
        source = item[1]
        state = turn_rows.take(state, player, item)
    return _pay(state, player, effect, arguments.get("faction"), source)


def _pay(
    state: GameState,
    player: int,
    effect: str,
    faction: ActionValue | None,
    source: str,
) -> RuleResult:
    """Give the reward ``effect`` names to ``player``."""

    owner = state.players[player]
    reward_source = f"{source}:{effect}"
    if effect == DIVIDENDS:
        # "Dividends(5 Solari, 상대마다 1 Solari)" [Rise of Ix p. 5].
        players = state.players
        events: list[GameEvent] = []
        for seat in players:
            amount = (
                DIVIDENDS_SOLARI
                if seat.player_id == player
                else DIVIDENDS_OPPONENT_SOLARI
            )
            paid = replace(
                seat,
                resources=replace(
                    seat.resources, solari=seat.resources.solari + amount
                ),
            )
            players = replace_player(players, paid)
            events.append(
                resources_gained_event(
                    f"{reward_source}:{seat.player_id}", seat.player_id, solari=amount
                )
            )
        return RuleResult(state=replace(state, players=players), events=tuple(events))
    if effect == SPICE:
        paid = replace(
            owner,
            resources=replace(
                owner.resources, spice=owner.resources.spice + SPICE_REWARD
            ),
        )
        return RuleResult(
            state=replace(state, players=replace_player(state.players, paid)),
            events=(resources_gained_event(reward_source, player, spice=SPICE_REWARD),),
        )
    if effect == RECRUIT:
        return _recruit(state, player, reward_source)
    if effect == INFLUENCE:
        return _influence(state, player, faction, reward_source)
    if effect == TECH:
        return push_tech_acquisition(
            state,
            player,
            discount=TECH_DISCOUNT,
            source=reward_source,
            printer=printer_value(Source.BOARD_SPACE, PRINTED),
        )
    raise ValueError(f"{effect!r} is no Shipping track reward")


def shipping_troops(owner_tech_ids: tuple[str, ...]) -> int:
    """The troops one Shipping track recruit gives: 2, and one more with
    Troop Transports ("Shipping track에서 troop을 recruit할 때마다 하나 더",
    [Rise of Ix p. 4])."""

    extra = has_tech(owner_tech_ids, TechAbility.SHIPPING_EXTRA_TROOP)
    return RECRUITED_TROOPS + (1 if extra else 0)


def _recruit(state: GameState, player: int, source: str) -> RuleResult:
    """Space 2's recruit: the troops go to the garrison. In the owner's own
    turn they join its deployment allowance by the Combat-space rule, and with
    Troop Transports -- "You may deploy any of them to the Conflict" -- every
    one of them (the extra troop included) may deploy even where the Agent
    went to no Combat space (docs/rules/rise-of-ix.md 15). Outside the turn,
    in Combat, they only wait in the garrison."""

    owner = state.players[player]
    extra = has_tech(owner.tech_ids, TechAbility.SHIPPING_EXTRA_TROOP)
    count = shipping_troops(owner.tech_ids)
    next_owner, recruited = recruit_troops(owner, count)
    working = replace(state, players=replace_player(state.players, next_owner))
    if own_turn_frame_index(working, player) is not None:
        working = update_turn_recruits(working, troops_recruited=recruited)
        if extra:
            working = grant_shipping_troop_deployment(working, player, recruited)
            # What the supply could not give joins that allowance when a
            # later refill pays it (OQ-030, ``shortfall.refill_shortfall``).
            working = note_ungained_shipping_troops(
                working, player, count - recruited
            )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:troops",
            kind="shipping_troops_recruited",
            payload=(("count", recruited), ("player", player)),
        ),
        *recruit_shortfall_events(source, player, count, recruited),
    ]
    return RuleResult(state=working, events=tuple(events))


def _influence(
    state: GameState, player: int, faction: ActionValue | None, source: str
) -> RuleResult:
    """Space 2's Influence: 1 with ``faction``; with every cube at the top it
    is lost and the owner confirms it (OQ-060)."""

    if faction is None:
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{source}:unavailable",
                    kind="shipping_influence_unavailable",
                    payload=(("player", player),),
                ),
            ),
        )
    return gain_faction_influence(
        state,
        player,
        Faction(str(faction)),
        1,
        event_prefix=f"{source}:{faction}",
    )


# --- The Freighter icon outside its owner's turn ------------------------------


def freighter_move_frame(player: int, *, source: str) -> DecisionFrame:
    """``player``'s window over one Freighter icon it gained where no row of
    its own turn holds it (a Conflict reward's, [FAQ p. 3]): up one space,
    recall or neither [Rise of Ix p. 5]."""

    return DecisionFrame(
        kind=FrameKind.FREIGHTER_MOVE,
        frame_id=f"{source}:freighter_move",
        decision=PlayerDecision(owner=player, prompt="Move your Freighter"),
        context=(("source", source),),
    )


def open_freighter_move(state: GameState, player: int, *, source: str) -> GameState:
    """Open the window ``freighter_move_frame`` builds on top of ``state``."""

    return state.push_decision(freighter_move_frame(player, source=source))


def legal_freighter_move_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Up one space (never from the top), recall (never from the bottom), or
    neither."""

    if owned_top_frame(state, FrameKind.FREIGHTER_MOVE, player) is None:
        return ()
    actions: list[DomainAction] = []
    if freighter_can_advance(state, player):
        actions.append(DomainAction(action_id=ADVANCE_ACTION, actor=player))
    if freighter_can_recall(state, player):
        actions.append(DomainAction(action_id=RECALL_ACTION, actor=player))
    actions.append(DomainAction(action_id=DECLINE_ACTION, actor=player))
    return tuple(actions)


def apply_freighter_move_action(state: GameState, action: DomainAction) -> RuleResult:
    """Answer the open Freighter window."""

    player = action.actor
    if action not in legal_freighter_move_actions(state, player):
        raise ValueError("action is not a legal Freighter move")
    source = context_str(dict(state.decision_stack[-1].context), "source", owner=_FRAME)
    closed = state.pop_decision()
    if action.action_id == ADVANCE_ACTION:
        return move_freighter_up(closed, player, source=source)
    if action.action_id == RECALL_ACTION:
        return recall_freighter(closed, player, source=source)
    return RuleResult(
        state=closed,
        events=(
            GameEvent(
                event_id=f"{source}:freighter_declined",
                kind="freighter_declined",
                payload=(("player", player),),
            ),
        ),
    )
