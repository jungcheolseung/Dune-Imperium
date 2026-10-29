"""Rise of Ix's three Conflict cards (stage P4d-1).

Rules: docs/rules/rise-of-ix.md 12 (the reward table and the paragraph under
it), 5 (the Freighter outside its owner's turn, ``[Rise of Ix p. 5]``
``[FAQ p. 3]``, OQ-151) and the Windtraps row of 4. The table, from the app's
ability classes:

| Card | Tier | 1st | 2nd | 3rd |
| --- | --- | --- | --- | --- |
| Skirmish (``SkirmishE``) | I | Freighter, troop 1 | spice 2 | spice 1 |
| Skirmish (``SkirmishF``) | I | Freighter, spice 1 | 3 Solari | 2 Solari |
| Trade Monopoly | II | Freighter 2, troop 1 | Intrigue, water | Intrigue -OR- water |

Setup takes ``rise_of_ix`` on the original game since stage P4c-5, but these
tests build their states by hand: an original game's opening state with its
config switched to ``rise_of_ix=True``, moved into the Combat phase with the
seats' troops in the Conflict (the way ``test_dreadnoughts.py`` does), and
run through the engine's Combat Intrigue passes to the first recipient's
reward window.
"""

from dataclasses import replace
from typing import Any

import pytest
from tests.support.pauses import pause_outcome

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec, ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    Freighter,
    GainResources,
    RecruitTroops,
)
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core import DomainAction, GamePhase, GameState, Resources
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import (
    DREADNOUGHT_CONTROL_ACTION,
    DREADNOUGHT_DETONATE_ACTION,
    CombatReward,
    RewardRank,
    _reward_window,
    _winning_intrigue_instances,
    add_late_windtraps_row,
    begin_combat_intrigue,
    legacy_combat_reward_icon,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.pauses import pause_is_pending
from dune_imperium.rules.setup import create_initial_state

ENGINE = UprisingRulesEngine()
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
WINDOW = FrameKind.COMBAT_REWARD_ICONS
LEADERS = (
    "paul_atreides",
    "duke_leto_atreides",
    "glossu_rabban",
    "baron_vladimir_harkonnen",
)
# The tops: Windtraps (cost 2), Detonation Devices (3), Restricted Ordnance (4).
STACKS = (
    ("windtraps", "artillery", "chaumurky"),
    ("detonation_devices", "holtzman_engine", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)
# Seats 0, 1 and 2 take the first three places: 3, 2 and 1 troops.
THREE_PLACES = {0: (3, 0), 1: (2, 0), 2: (1, 0)}


# --- Building a Combat -------------------------------------------------------


def _seat(state: GameState, seat: int, **changes: Any) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _combat(conflict_id: str) -> GameState:
    """The Combat phase of an original game with Rise of Ix, ``conflict_id``
    revealed, the Ix stacks laid and every seat holding five troops in its
    garrison and seven in its supply."""

    state = ENGINE.reset(ORIGINAL, 3)
    state = replace(
        state,
        config=replace(state.config, rise_of_ix=True),
        tech_stacks=STACKS,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        combat_end_triggers_offered=False,
    )
    for seat in range(len(state.players)):
        state = _seat(
            state,
            seat,
            troops_garrison=5,
            troops_supply=7,
            troops_conflict=0,
            dreadnoughts_supply=2,
            dreadnoughts_conflict=0,
            dreadnoughts_garrison=0,
        )
    return state


def _holding(state: GameState, seat: int, tech_id: str) -> GameState:
    """``seat`` holding ``tech_id``, taken from the top of its stack."""

    stacks = tuple(
        tuple(tile for tile in stack if tile != tech_id) for stack in state.tech_stacks
    )
    held = (*state.players[seat].tech_ids, tech_id)
    return _seat(replace(state, tech_stacks=stacks), seat, tech_ids=held)


def _without_winning_intrigue(state: GameState) -> GameState:
    """No "When you win a Conflict" Intrigue card in a deck or a hand, so the
    sole winner's window has no closing row (``winning_intrigue_is_hidden``)
    and closes with its last icon."""

    winning = _winning_intrigue_instances()
    state = replace(
        state,
        intrigue_deck=tuple(c for c in state.intrigue_deck if c not in winning),
    )
    for player in state.players:
        state = _seat(
            state,
            player.player_id,
            intrigue_cards=tuple(c for c in player.intrigue_cards if c not in winning),
        )
    return state


def _fight(
    conflict_id: str,
    units: dict[int, tuple[int, int]] | None = None,
    *,
    seats: dict[int, dict[str, Any]] | None = None,
    held: tuple[tuple[int, str], ...] = (),
    closing_row: bool = True,
) -> GameState:
    """The Combat of ``units`` (seat -> troops, dreadnoughts in the Conflict;
    2 strength a troop, 3 a dreadnought) through its Combat Intrigue passes,
    to the first recipient's reward window. ``seats`` lays further changes on
    seats before the Combat and ``held`` gives seats a Tech tile from its
    stack; ``closing_row`` False takes the winning Intrigue cards out of
    play."""

    state = _combat(conflict_id)
    for seat, tech_id in held:
        state = _holding(state, seat, tech_id)
    if not closing_row:
        state = _without_winning_intrigue(state)
    for seat, (troops, dreadnoughts) in (units or THREE_PLACES).items():
        owner = state.players[seat]
        state = _seat(
            state,
            seat,
            troops_garrison=owner.troops_garrison - troops,
            troops_conflict=troops,
            dreadnoughts_supply=owner.dreadnoughts_supply - dreadnoughts,
            dreadnoughts_conflict=dreadnoughts,
            combat_strength=2 * troops + 3 * dreadnoughts,
        )
    for seat, changes in (seats or {}).items():
        state = _seat(state, seat, **changes)
    state = begin_combat_intrigue(state).state
    while state.decision_stack and state.decision_stack[-1].kind == (
        FrameKind.COMBAT_INTRIGUE
    ):
        owner_id = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
        state = apply_whole(
            ENGINE, state, DomainAction("pass_combat_intrigue", owner_id)
        ).state
    assert state.decision_stack[-1].kind == WINDOW
    return state


# --- Answering ---------------------------------------------------------------


def _icon(kind: str, actor: int = 0) -> DomainAction:
    return DomainAction("resolve_combat_reward_icon", actor, (("effect", kind),))


def _do(state: GameState, action: DomainAction) -> GameState:
    """Apply a whole action the engine offers ``action.actor`` now."""

    offered = ENGINE.whole_actions(state, action.actor)
    assert action in offered, (action, offered)
    return apply_whole(ENGINE, state, action).state


def _shipping(effect: str, faction: str | None = None) -> DomainAction:
    arguments: tuple[tuple[str, str], ...] = (("effect", effect),)
    if faction is not None:
        arguments = (*arguments, ("faction", faction))
    return DomainAction("resolve_shipping_reward", 0, arguments)


def _top(state: GameState) -> FrameKind:
    return FrameKind(state.decision_stack[-1].kind)


def _icons(state: GameState, frame: int = -1) -> list[str]:
    context = dict(state.decision_stack[frame].context)
    return [icon for icon in str(context["icons"]).split(",") if icon]


def _printed(state: GameState, frame: int = -1) -> list[str]:
    context = dict(state.decision_stack[frame].context)
    return str(context["printed"]).split(",")


def _settle(
    state: GameState, *, stop_at_rank: int | None = None
) -> tuple[GameState, list[str]]:
    """Answer every pause, window row and Freighter window (declined) the
    older engine's way until the rewards are paid, or until the window of
    ``stop_at_rank`` is on top; the kinds of the events on the way."""

    kinds: list[str] = []
    for _ in range(80):
        if state.combat_rewards_resolved or state.phase is not GamePhase.COMBAT:
            return state, kinds
        if pause_is_pending(state):
            step = ENGINE.apply(state, pause_outcome(state))
        else:
            frame = state.decision_stack[-1]
            owner = frame.decision.owner  # type: ignore[union-attr]
            if frame.kind == FrameKind.FREIGHTER_MOVE:
                answer: DomainAction | None = DomainAction("decline_freighter", owner)
            else:
                if (
                    stop_at_rank is not None
                    and dict(frame.context).get("rank") == stop_at_rank
                ):
                    return state, kinds
                answer = legacy_combat_reward_icon(state, owner)
            assert answer is not None, frame.kind
            step = apply_whole(ENGINE, state, answer)
        state = step.state
        kinds.extend(event.kind for event in step.events)
    raise AssertionError("the rewards were not paid")


def _round_trips(state: GameState, *seats: int) -> None:
    """Every row the engine offers ``seats`` encodes and decodes to itself in
    the state's own catalog (the original game with Rise of Ix)."""

    codec = ActionCodec(state.config)
    for seat in seats:
        for action in ENGINE.legal_actions(state, seat):
            assert codec.decode(codec.encode(action), action.actor) == action


def _gain(state: GameState, before: GameState, seat: int, **fields: int) -> None:
    """``seat`` gained exactly ``fields`` (resources) since ``before``."""

    now, was = state.players[seat].resources, before.players[seat].resources
    for name in ("solari", "spice", "water"):
        assert getattr(now, name) - getattr(was, name) == fields.get(name, 0), name


# --- The rows ----------------------------------------------------------------


def test_the_three_cards_print_the_rows_of_the_table() -> None:
    """rise-of-ix.md 12, from the app's ability classes: Skirmish E (I) 1st
    Freighter + troop 1, 2nd spice 2, 3rd spice 1; Skirmish F (I) 1st
    Freighter + spice 1, 2nd 3 Solari, 3rd 2 Solari; Trade Monopoly (II) 1st
    Freighter 2 + troop 1, 2nd Intrigue + water, 3rd Intrigue -OR- water.
    None takes control of a space or prints a battle icon."""

    def lines(card_id: str) -> list[list[Any]]:
        rows = CONFLICTS_BY_ID[card_id].reward_rows
        assert rows is not None
        return [[line.rewards for line in row.sections] for row in rows]

    assert lines("skirmish_e") == [
        [(Freighter(), RecruitTroops(1))],
        [(GainResources(spice=2),)],
        [(GainResources(spice=1),)],
    ]
    assert lines("skirmish_f") == [
        [(Freighter(), GainResources(spice=1))],
        [(GainResources(solari=3),)],
        [(GainResources(solari=2),)],
    ]
    assert lines("trade_monopoly") == [
        [(Freighter(), Freighter(), RecruitTroops(1))],
        [(DrawIntrigueCards(1), GainResources(water=1))],
        [(DrawIntrigueCards(1),), (GainResources(water=1),)],
    ]
    for card_id, tier in (
        ("skirmish_e", ConflictTier.ONE),
        ("skirmish_f", ConflictTier.ONE),
        ("trade_monopoly", ConflictTier.TWO),
    ):
        conflict = CONFLICTS_BY_ID[card_id]
        assert conflict.tier is tier
        assert conflict.control_space_id is None
        assert conflict.battle_icon is None


def test_the_pool_is_six_eleven_five_and_twelve_stay_unused() -> None:
    """rise-of-ix.md 3 item 3 (`[Rise of Ix p. 3]`): the original game with
    Rise of Ix draws its ten cards (I 1, II 5, III 4) from I 6, II 11, III 5;
    with the three Ix Conflicts in the pool the 12 left are all unused."""

    content = content_for(IX)
    assert [len(content.conflicts_by_tier(tier)) for tier in ConflictTier] == [
        6,
        11,
        5,
    ]
    assert {c.card.card_id for c in IX_CONFLICTS} <= {
        c.card.card_id for c in content.conflict_pool
    }
    for seed in range(4):
        state = create_initial_state(IX, seed, LEADERS).state
        assert len(state.unused_conflict_ids) == 12
        deck = (*state.current_conflict_ids, *state.conflict_deck)
        assert len(deck) == 10
        assert not set(deck) & set(state.unused_conflict_ids)


# --- The ranks through the reward window --------------------------------------


@pytest.mark.parametrize(
    ("card_id", "winner", "second", "third", "troops_for_first"),
    [
        # Freighter and troop 1 | spice 2 | spice 1.
        ("skirmish_e", {}, {"spice": 2}, {"spice": 1}, 1),
        # Freighter and spice 1 | 3 Solari | 2 Solari.
        ("skirmish_f", {"spice": 1}, {"solari": 3}, {"solari": 2}, 0),
        # Freighter 2 and troop 1 | Intrigue and water | Intrigue (-OR- water).
        ("trade_monopoly", {}, {"water": 1}, {}, 1),
    ],
)
def test_each_rank_is_paid_through_its_window(
    card_id: str,
    winner: dict[str, int],
    second: dict[str, int],
    third: dict[str, int],
    troops_for_first: int,
) -> None:
    """rise-of-ix.md 12: the sole winner, the second and the third place
    receive their rows, one recipient's window after another; the winner's
    Freighter icons each open a Freighter window (declined here), and the
    troop is recruited into the garrison."""

    before = _fight(card_id)
    state, kinds = _settle(before)

    assert state.combat_rewards_resolved
    _gain(state, before, 0, **winner)
    _gain(state, before, 1, **second)
    _gain(state, before, 2, **third)
    owner, was = state.players[0], before.players[0]
    assert owner.troops_garrison - was.troops_garrison == troops_for_first
    assert was.troops_supply - owner.troops_supply == troops_for_first
    intrigue = [len(state.players[i].intrigue_cards) for i in range(3)]
    was_intrigue = [len(before.players[i].intrigue_cards) for i in range(3)]
    assert [now - was for now, was in zip(intrigue, was_intrigue, strict=True)] == (
        [0, 1, 1] if card_id == "trade_monopoly" else [0, 0, 0]
    )
    freighters = {"skirmish_e": 1, "skirmish_f": 1, "trade_monopoly": 2}[card_id]
    assert kinds.count("freighter_declined") == freighters
    assert kinds.count("combat_reward_icon_resolved") >= 3


def test_the_winner_window_holds_one_freighter_row_for_each_icon() -> None:
    """Freighter 아이콘마다 ... [Rise of Ix p. 5] (rise-of-ix.md 5, 12): the
    Skirmishes' first place prints one Freighter icon and Trade Monopoly's
    two, each a row of the window that opens a Freighter window of its own."""

    for card_id, count in (("skirmish_e", 1), ("skirmish_f", 1), ("trade_monopoly", 2)):
        state = _fight(card_id)
        assert _icons(state).count("freighter") == count, card_id
        assert dict(state.decision_stack[-1].context)["rank"] == 1
        _round_trips(state, 0)

    state = _fight("trade_monopoly", seats={0: {"freighter_space": 1}})
    state = _do(state, _icon("freighter"))
    assert _top(state) is FrameKind.FREIGHTER_MOVE
    assert _icons(state, 0).count("freighter") == 1
    first_window = state.decision_stack[-1].frame_id
    state = _do(state, DomainAction("advance_freighter", 0))
    assert state.players[0].freighter_space == 2
    # The second icon moves it again: up to the top, in a window of its own.
    assert _top(state) is WINDOW
    state = _do(state, _icon("freighter"))
    assert state.decision_stack[-1].frame_id != first_window
    state = _do(state, DomainAction("advance_freighter", 0))
    assert state.players[0].freighter_space == 3
    assert "freighter" not in _icons(state)


def test_the_other_places_print_no_freighter() -> None:
    """rise-of-ix.md 12: only the first place prints the Freighter."""

    for card_id in ("skirmish_e", "skirmish_f", "trade_monopoly"):
        for rank in (2, 3):
            state, _ = _settle(_fight(card_id), stop_at_rank=rank)
            assert dict(state.decision_stack[-1].context)["rank"] == rank
            assert "freighter" not in _printed(state), (card_id, rank)


def test_trade_monopolys_third_place_takes_intrigue_or_water() -> None:
    """rise-of-ix.md 12: "3위: Intrigue -OR- water" -- one of the two lines,
    named in the window before it is paid."""

    for line, intrigue, water in ((0, 1, 0), (1, 0, 1)):
        state = _fight("trade_monopoly")
        state, _ = _settle(state, stop_at_rank=3)
        assert dict(state.decision_stack[-1].context)["rank"] == 3
        assert _icons(state) == ["line_0", "line_1"]
        before = state
        state = _do(state, _icon(f"line_{line}", 2))
        # The chosen line is then the window's one row.
        assert "line_0" not in _icons(state) and "line_1" not in _icons(state)
        _round_trips(state, 2)
        state, _ = _settle(state)
        assert state.combat_rewards_resolved
        assert (
            len(state.players[2].intrigue_cards) - len(before.players[2].intrigue_cards)
            == intrigue
        )
        _gain(state, before, 2, water=water)


# --- The Freighter in the winner's window ---------------------------------------


def test_a_sole_recipients_last_freighter_ends_the_rewards() -> None:
    """rise-of-ix.md 12, Skirmish F 1st "Freighter, spice 1", and 5 "자기 turn
    밖의 회수(Conflict 보상의 Freighter)" (`[FAQ p. 3]`): the window closes with
    its last icon, and the Freighter window it opened is the last frame of a
    Combat with one recipient; answering it leaves the rewards paid."""

    state = _fight(
        "skirmish_f", {0: (1, 0)}, seats={0: {"freighter_space": 1}}, closing_row=False
    )
    assert _icons(state) == ["resources", "freighter"]
    state = _do(state, _icon("resources"))
    state = _do(state, _icon("freighter"))
    assert [f.kind for f in state.decision_stack] == [FrameKind.FREIGHTER_MOVE]
    assert not state.combat_rewards_resolved
    state = _do(state, DomainAction("advance_freighter", 0))
    assert state.players[0].freighter_space == 2
    # The Combat goes on to its end: the rewards are paid, the pause is the
    # Conflict end's.
    assert state.combat_rewards_resolved
    assert pause_is_pending(state)


def test_a_recall_during_combat_recruits_into_the_garrison() -> None:
    """rise-of-ix.md 5 and OQ-151 (`[Rise of Ix p. 5]`): "Combat 중에 recruit한
    troop은 garrison으로" -- a recall in the winner's window recruits space 2's
    two troops into the garrison, not the Conflict, with Troop Transports'
    extra one too; the owed spaces are rows of a window of their own."""

    state = _fight(
        "skirmish_f",
        seats={0: {"freighter_space": 2, "tech_ids": ("troop_transports",)}},
    )
    garrison = state.players[0].troops_garrison
    in_conflict = state.players[0].troops_conflict
    state = _do(state, _icon("freighter"))
    state = _do(state, DomainAction("recall_freighter", 0))
    assert state.players[0].freighter_space == 0
    assert _top(state) is FrameKind.SHIPPING_REWARD_ICONS
    assert _icons(state, 0) != []
    _round_trips(state, 0)
    state = _do(state, _shipping("recruit"))
    owner = state.players[0]
    assert owner.troops_garrison == garrison + 3
    assert owner.troops_conflict == in_conflict
    state = _do(state, _shipping("dividends"))
    state = _do(state, _shipping("influence", "fremen"))
    # Back in the window, whose other row is still waiting.
    assert _top(state) is WINDOW
    assert "freighter" not in _icons(state)


def test_a_recall_during_combat_may_acquire_a_tech_tile() -> None:
    """rise-of-ix.md 5 (`[FAQ p. 3]`): "자기 turn 밖의 회수(Conflict 보상의
    Freighter): Tech를 얻을 수 있고" -- space 3's Acquire Tech opens at Tech
    Discount 2 in the winner's window, and the tile is the winner's."""

    state = _fight(
        "skirmish_e",
        seats={0: {"freighter_space": 3, "resources": Resources(spice=2)}},
    )
    state = _do(state, _icon("freighter"))
    state = _do(state, DomainAction("recall_freighter", 0))
    state = _do(state, _shipping("tech"))
    assert _top(state) is FrameKind.TECH_ACQUISITION
    _round_trips(state, 0)
    # Restricted Ordnance costs 4, less the Discount 2.
    state = _do(
        state,
        DomainAction("acquire_tech", 0, (("tech_id", "restricted_ordnance"),)),
    )
    owner = state.players[0]
    assert "restricted_ordnance" in owner.tech_ids
    assert owner.resources.spice == 0
    assert state.tech_stacks[2][0] == "minimic_film"


# --- Windtraps and Detonation Devices acquired by the Freighter -----------------


def _take_windtraps_by_recall(state: GameState) -> GameState:
    """From the Freighter window of a winner whose Freighter is on space 3:
    the recall, Windtraps as the Acquire Tech, its acquire effect's water and
    the recall's other rewards (``_finish_the_recall``) still to take."""

    assert _top(state) is FrameKind.FREIGHTER_MOVE
    state = _do(state, DomainAction("recall_freighter", 0))
    state = _do(state, _shipping("tech"))
    state = _do(state, DomainAction("acquire_tech", 0, (("tech_id", "windtraps"),)))
    return _do(
        state,
        DomainAction(
            "resolve_tech_acquire_effect",
            0,
            (("effect", "water"), ("tech_id", "windtraps")),
        ),
    )


def _finish_the_recall(state: GameState) -> GameState:
    state = _do(state, _shipping("spice"))
    state = _do(state, _shipping("recruit"))
    return _do(state, _shipping("influence", "fremen"))


def test_windtraps_taken_by_the_freighter_pays_this_wins_water_too() -> None:
    """rise-of-ix.md 12: "Freighter 보상으로 그 자리에서 Windtraps를 얻으면 이번
    승리에도 water를 받는다 -- 디자이너 판정(BGG forum, "one from the Acquire
    effect and one for winning the combat")". The acquire effect's water is paid
    with the tile; the winner's window then holds Windtraps' row (rise-of-ix.md
    4: "Conflict를 이기면 water 1"), before the closing row, and resolving it
    is the second water."""

    before = _fight("skirmish_e", seats={0: {"freighter_space": 3}})
    assert "windtraps" not in _icons(before)
    state = _take_windtraps_by_recall(_do(before, _icon("freighter")))
    _gain(state, before, 0, water=1)
    state = _finish_the_recall(state)

    assert _top(state) is WINDOW
    assert _icons(state) == ["troops", "windtraps", "winning_intrigue"]
    assert _printed(state) == ["freighter", "troops", "windtraps", "winning_intrigue"]
    _round_trips(state, 0)
    state = _do(state, _icon("windtraps"))
    _gain(state, before, 0, water=2, spice=2)
    assert "windtraps" not in _icons(state)
    state = _do(state, _icon("troops"))
    state = _do(state, _icon("winning_intrigue"))
    assert state.decision_stack == () or pause_is_pending(state)


def test_windtraps_taken_by_the_freighters_last_icon_still_pays_the_win() -> None:
    """The same ruling when the Freighter is the window's last icon (no
    closing row): the window closes as it opens the Freighter's, so Windtraps'
    row waits in a window of its own at the bottom of the stack and comes up
    once the Freighter's windows are answered."""

    before = _fight("skirmish_e", seats={0: {"freighter_space": 3}}, closing_row=False)
    assert _icons(before) == ["troops", "freighter"]
    state = _do(before, _icon("troops"))
    state = _take_windtraps_by_recall(_do(state, _icon("freighter")))
    assert [f.kind for f in state.decision_stack] == [
        WINDOW,
        FrameKind.SHIPPING_REWARD_ICONS,
    ]
    assert _icons(state, 0) == ["windtraps"]
    assert dict(state.decision_stack[0].context)["rank"] == 1
    state = _finish_the_recall(state)
    assert _top(state) is WINDOW
    assert _icons(state) == ["windtraps"]
    _round_trips(state, 0)
    state = _do(state, _icon("windtraps"))
    _gain(state, before, 0, water=2, spice=2)
    # The reward is paid: the next recipient's pause follows.
    assert pause_is_pending(state) or state.decision_stack == ()
    state, _ = _settle(state)
    assert state.combat_rewards_resolved


def test_a_tile_taken_outside_the_sole_winners_reward_adds_no_row() -> None:
    """The row is the sole winner's ("Conflict를 이기면"): a tile held before
    the window opened has its row once, and the late row is added for the sole
    winner's own window alone -- not for another seat's tile, a second place's
    window, nor before any reward is paid."""

    held = _fight("skirmish_e", held=((0, "windtraps"),))
    assert _printed(held).count("windtraps") == 1
    assert add_late_windtraps_row(held, 0) == held

    # The control: the tile came after the window opened.
    first = _fight("skirmish_e")
    late = _holding(first, 0, "windtraps")
    assert add_late_windtraps_row(late, 0) != late
    assert _printed(add_late_windtraps_row(late, 0)).count("windtraps") == 1
    # A tile of another seat in the winner's window.
    other = _holding(first, 1, "windtraps")
    assert add_late_windtraps_row(other, 1) == other
    # Before any reward is paid.
    unpaid = replace(late, combat_rewards_paid=0)
    assert add_late_windtraps_row(unpaid, 0) == unpaid
    # The second place's window.
    second, _ = _settle(_fight("skirmish_e"), stop_at_rank=2)
    second = _holding(second, 1, "windtraps")
    assert add_late_windtraps_row(second, 1) == second


def test_detonation_devices_taken_by_the_freighter_is_offered_this_win() -> None:
    """rise-of-ix.md 12: "Detonation Devices도 같다": a winner with a
    dreadnought in the Conflict who takes the tile through its Freighter
    before choosing the dreadnought's space is offered "dreadnought를 supply로
    돌려 1 VP" (rise-of-ix.md 4) in this win's choice; without the tile the
    choice offers only the spaces."""

    seats = {0: {"freighter_space": 3, "resources": Resources(spice=1)}}
    units = {0: (1, 1), 1: (0, 1)}

    without = _fight("skirmish_e", units, seats=seats)
    without = _do(without, _icon("dreadnought_control"))
    offered = {a.action_id for a in ENGINE.whole_actions(without, 0)}
    assert offered == {DREADNOUGHT_CONTROL_ACTION}

    state = _fight("skirmish_e", units, seats=seats)
    state = _do(state, _icon("freighter"))
    state = _do(state, DomainAction("recall_freighter", 0))
    state = _do(state, _shipping("tech"))
    # Detonation Devices costs 3, less the Discount 2.
    state = _do(
        state, DomainAction("acquire_tech", 0, (("tech_id", "detonation_devices"),))
    )
    state = _finish_the_recall(state)
    assert _top(state) is WINDOW
    # It has no winner's row: the option is read when the space is chosen.
    assert "windtraps" not in _icons(state)
    victory = state.players[0].victory_points
    state = _do(state, _icon("dreadnought_control"))
    assert _top(state) is FrameKind.DREADNOUGHT_CONTROL_CHOICE
    offered = {a.action_id for a in ENGINE.whole_actions(state, 0)}
    assert offered == {DREADNOUGHT_CONTROL_ACTION, DREADNOUGHT_DETONATE_ACTION}
    _round_trips(state, 0)
    state = _do(state, DomainAction(DREADNOUGHT_DETONATE_ACTION, 0))
    owner = state.players[0]
    assert owner.victory_points == victory + 1
    assert owner.dreadnoughts_conflict == 0
    assert owner.dreadnoughts_supply == 2


# --- The catalogs -------------------------------------------------------------


def test_only_a_rise_of_ix_catalog_holds_the_freighter_row() -> None:
    """rise-of-ix.md 12 (the Freighter in the first places of all three
    cards): the icon is Rise of Ix's, so its reward row, one for each of the
    three Conflicts that print it, is in the original game's Rise of Ix
    catalogs and in no other; the rows the engine offers while the Freighter
    is resolved in Combat encode and decode to themselves."""

    def rows(config: RulesetConfig) -> set[ActionTemplate]:
        return {
            template
            for template in ActionCodec(config).catalog
            if ("icon", "freighter") in template.arguments
            and ("source", "conflict") in template.arguments
        }

    assert rows(IX) == {
        ActionTemplate(
            "advance",
            (("icon", "freighter"), ("printed", card_id), ("source", "conflict")),
        )
        for card_id in ("skirmish_e", "skirmish_f", "trade_monopoly")
    }
    assert rows(replace(IX, leader_draft=True)) == rows(IX)
    for config in (
        ORIGINAL,
        RulesetConfig(),
        replace(ORIGINAL, promo_cards=True),
        RulesetConfig(bloodlines=True, immortality=True, epic_game=True),
    ):
        assert not rows(config), config.identifier

    state = _fight("trade_monopoly", seats={0: {"freighter_space": 2}})
    _round_trips(state, 0)
    state = _do(state, _icon("freighter"))
    assert _top(state) is FrameKind.FREIGHTER_MOVE
    _round_trips(state, 0)
    state = _do(state, DomainAction("recall_freighter", 0))
    _round_trips(state, 0)


def test_the_window_builder_lists_the_freighter_after_the_other_icons() -> None:
    """rise-of-ix.md 12, Trade Monopoly 1st "Freighter 2, troop 1":
    ``_reward_window`` lays the first place's rows as the older engine paid
    them (the AI seats' order), the automatic troop first and Rise of Ix's two
    Freighter icons after it; a sandworm's multiplier (Uprising's, P7) does not
    double a Freighter."""

    state = _fight("trade_monopoly")
    first = CombatReward(0, RewardRank.FIRST, 2)
    frame = _reward_window(state, "trade_monopoly", first)
    icons = str(dict(frame.context)["icons"]).split(",")
    assert icons[:3] == ["troops", "freighter", "freighter"]
    assert icons.count("freighter") == 2
