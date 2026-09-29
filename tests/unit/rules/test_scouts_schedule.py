"""Arrakeen Scouts: the schedule draws and the round's Scouts step.

docs/rules/arrakeen-scouts.md sections 2-3, 6 (automatic events and round
modifiers); design docs/arrakeen-scouts-design.md 4.3-4.4. Probabilities are
checked on the draws' option multisets (exactly, with fractions), not by
sampling.
"""

from collections import Counter
from dataclasses import replace
from fractions import Fraction
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    SUBCOMMITTEES_BY_ID,
    ScoutsPool,
    subcommittees_for,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind, turn_owner_of
from dune_imperium.rules.phases import apply_control_defense_action, begin_round
from dune_imperium.rules.scouts import _next_draw, item_kind
from dune_imperium.rules.setup import maker_bonus_spice_for
from dune_imperium.simulation import run_random_game

SCOUTS = RulesetConfig(arrakeen_scouts=True)
SCOUTS_CHOAM = RulesetConfig(arrakeen_scouts=True, choam_module=True)


def _resolve_chance(
    engine: UprisingRulesEngine, state: GameState, resolver: ChanceResolver
) -> GameState:
    while state.decision_stack and isinstance(
        state.decision_stack[-1].decision, ChanceDecision
    ):
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, ChanceDecision)
        state = engine.apply(state, resolver.resolve(decision)).state
    return state


def _choose(state: GameState, engine: UprisingRulesEngine, value: str) -> GameState:
    """Answer the pending Scouts draw with one chosen value."""

    decision = state.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    assert value in decision.options
    return engine.apply(
        state, ChanceOutcome(decision_id=decision.decision_id, values=(value,))
    ).state


def _draw_frame(state: GameState) -> tuple[str, ChanceDecision]:
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    assert isinstance(frame.decision, ChanceDecision)
    return str(dict(frame.context)["step"]), frame.decision


# --- Round 1: the subcommittees -------------------------------------------------------


def test_reset_waits_on_the_first_subcommittee_draw() -> None:
    # [Scouts schedule]: one of each tier, then the rest; round 1 begins
    # inside reset(), so the reset state already waits on the draw, after
    # the Conflict reveal and the draw (OQ-072).
    engine = UprisingRulesEngine()
    state = engine.reset(SCOUTS, 7)
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 1
    assert all(len(player.hand) == 5 for player in state.players)
    step, decision = _draw_frame(state)
    assert step == "subcommittee_tier_0"
    pool = subcommittees_for(ScoutsPool.UPRISING, choam=False)
    assert set(decision.options) == {e.subcommittee_id for e in pool if e.tier == 0}
    assert turn_owner_of(state) is None
    assert state.scouts_opening


def test_five_subcommittees_one_per_tier_then_the_first_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(SCOUTS_CHOAM, 3)
    steps = []
    resolver = ChanceResolver(seed=3)
    for _ in range(4):
        step, decision = _draw_frame(state)
        steps.append((step, decision.count))
        state = engine.apply(state, resolver.resolve(decision)).state
    assert steps == [
        ("subcommittee_tier_0", 1),
        ("subcommittee_tier_1", 1),
        ("subcommittee_tier_2", 1),
        ("subcommittee_rest", 2),
    ]
    drawn = state.scouts_subcommittees
    assert len(drawn) == len(set(drawn)) == 5
    assert [SUBCOMMITTEES_BY_ID[s].tier for s in drawn[:3]] == [0, 1, 2]
    # The step is over: the First Player's turn is open.
    assert not state.scouts_opening
    top = state.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == state.first_player
    revealed = [e for e in state.event_log if e.kind == "scouts_subcommittees_revealed"]
    assert len(revealed) == 1


def test_choam_off_leaves_the_choam_subcommittees_out() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(SCOUTS, 11)
    state = _resolve_chance(engine, state, ChanceResolver(seed=0))
    assert not {"choam_coordination", "choam_management"} & set(
        state.scouts_subcommittees
    )


def test_the_draft_draws_subcommittees_only_after_the_leaders() -> None:
    # The app builds the schedule after the Leaders are chosen, so the draft
    # never sees the subcommittees (design 4.3).
    engine = UprisingRulesEngine()
    config = RulesetConfig(arrakeen_scouts=True, leader_draft=True)
    state = engine.reset(config, 5)
    assert state.phase is GamePhase.SETUP
    assert not state.scouts_subcommittees
    resolver = ChanceResolver(seed=5)
    while state.phase is GamePhase.SETUP:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        state = engine.apply(
            state, engine.legal_actions(state, decision.owner)[0]
        ).state
    assert state.round_number == 1
    step, _ = _draw_frame(state)
    assert step == "subcommittee_tier_0"


# --- The option off ------------------------------------------------------------


def test_without_the_option_the_round_opens_on_the_turn() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 7)
    assert state.decision_stack[-1].kind == FrameKind.TURN
    assert not state.scouts_opening
    with pytest.raises(ValueError, match="Arrakeen Scouts"):
        replace(state, scouts_round_modifier="faction_spaces_are_combat")


# --- Missions ------------------------------------------------------------------


def _at_round(state: GameState, round_number: int, **fields: Any) -> GameState:
    return replace(state, round_number=round_number, decision_stack=(), **fields)


def test_mission_layout_is_seven_to_three() -> None:
    state = _at_round(UprisingRulesEngine().reset(SCOUTS, 1), 2)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "mission_layout"
    layouts = Counter(option.split("#")[0] for option in draw.options)
    assert layouts == {"layout:223": 7, "layout:233": 3}


def test_the_last_mission_differs_in_type_from_the_one_before() -> None:
    base = UprisingRulesEngine().reset(SCOUTS_CHOAM, 1)
    state = _at_round(
        base,
        3,
        scouts_mission_rounds=(2, 2, 3),
        scouts_revealed=((2, "security_detail"), (2, "imperial_reserve")),
    )
    draw = _next_draw(state)
    assert draw is not None and draw.step == "mission"
    # Two type-0 missions out: the third is type 1, from families not drawn.
    assert {MISSIONS_BY_ID[m].mission_type for m in draw.options} == {1}
    assert "fedaykin_assistance" in draw.options  # round 3 only
    # Mission 2 may share mission 1's type; family removal still applies.
    state = _at_round(
        base,
        2,
        scouts_mission_rounds=(2, 2, 3),
        scouts_revealed=((2, "desert_riding"),),
    )
    draw = _next_draw(state)
    assert draw is not None
    assert not {"desert_riding", "urban_surveillance", "planetary_exploration"} & set(
        draw.options
    )
    assert "imperial_reserve" in draw.options
    assert "fedaykin_assistance" not in draw.options  # round 2


def _mission_probabilities(config: RulesetConfig) -> dict[str, Fraction]:
    base = UprisingRulesEngine().reset(config, 1)
    result: dict[str, Fraction] = {}

    def walk(state: GameState, weight: Fraction) -> None:
        missions = [item for _, item in state.scouts_revealed]
        if len(missions) == 3:
            for mission in missions:
                result[mission] = result.get(mission, Fraction(0)) + weight
            return
        slot_round = state.scouts_mission_rounds[len(missions)]
        draw = _next_draw(_at_round(state, slot_round))
        assert draw is not None and draw.step == "mission"
        for option in draw.options:
            walk(
                replace(
                    state,
                    scouts_revealed=(*state.scouts_revealed, (slot_round, option)),
                ),
                weight / len(draw.options),
            )

    for layout, share in (((2, 2, 3), Fraction(7, 10)), ((2, 3, 3), Fraction(3, 10))):
        walk(replace(base, scouts_mission_rounds=layout), share)
    return result


def test_mission_odds_match_the_app_enumeration() -> None:
    # The app analysis enumerated the Uprising pool exactly (0.7/0.3 mix):
    # CHOAM off, Security Detail 71/180 = 0.394, Fedaykin Assistance 0.165;
    # CHOAM on, Weirding Warfare 0.318, Desert Riding 0.2035.
    off = _mission_probabilities(SCOUTS)
    assert off["security_detail"] == Fraction(71, 180)
    assert round(float(off["fedaykin_assistance"]), 3) == 0.165
    assert round(float(off["weirding_warfare"]), 3) == 0.346
    assert round(float(off["prison_planet"]), 3) == 0.294
    on = _mission_probabilities(SCOUTS_CHOAM)
    assert round(float(on["weirding_warfare"]), 3) == 0.318
    assert round(float(on["desert_riding"]), 4) == 0.2035
    # 79/308 = 0.2565 (the analysis's exact fraction; its summary rounded
    # it to 0.257).
    assert on["security_detail"] == Fraction(79, 308)
    assert sum(on.values()) == 3


# --- Events ------------------------------------------------------------------------


def test_round_four_ticket_table() -> None:
    state = _at_round(UprisingRulesEngine().reset(SCOUTS_CHOAM, 1), 4)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "event"
    families = Counter(EVENTS_BY_ID[o.split("#")[0]].app.family for o in draw.options)
    assert sum(families.values()) == 170
    assert families[17] == families[18] == 30
    assert "friends_everywhere#0" not in draw.options  # rounds 5-7
    assert "rebuild_infrastructure#0" not in draw.options  # round 7


def _event_probabilities(config: RulesetConfig) -> dict[int, Fraction]:
    """P(each event family appears in a game) by exact enumeration."""

    base = UprisingRulesEngine().reset(config, 1)
    result: dict[int, Fraction] = {}

    def walk(state: GameState, round_number: int, weight: Fraction) -> None:
        if round_number > 7:
            for _, item in state.scouts_revealed:
                family = EVENTS_BY_ID[item].app.family
                result[family] = result.get(family, Fraction(0)) + weight
            return
        draw = _next_draw(
            _at_round(
                state,
                round_number,
                scouts_mid_auction_round=9,  # keep the auctions out of the way
            )
        )
        assert draw is not None and draw.step == "event"
        tickets = Counter(option.split("#")[0] for option in draw.options)
        total = sum(tickets.values())
        for event_id, count in tickets.items():
            walk(
                replace(
                    state,
                    scouts_revealed=(*state.scouts_revealed, (round_number, event_id)),
                ),
                round_number + 1,
                weight * Fraction(count, total),
            )

    walk(base, 4, Fraction(1))
    return result


def test_event_odds_match_the_app_enumeration() -> None:
    # [Scouts schedule] analysis: Influence Gain 0.5681 with CHOAM / 0.5959
    # without; Rebuild Infrastructure 0.0712 / 0.0774.
    on = _event_probabilities(SCOUTS_CHOAM)
    off = _event_probabilities(SCOUTS)
    assert round(float(on[17]), 4) == 0.5681
    assert round(float(off[17]), 4) == 0.5959
    assert round(float(on[26]), 4) == 0.0712
    assert round(float(off[26]), 4) == 0.0774
    assert sum(on.values()) == sum(off.values()) == 4


# --- Auctions and the sale -----------------------------------------------------------


def test_mid_auction_round_then_auction_before_the_event() -> None:
    engine = UprisingRulesEngine()
    state = _at_round(engine.reset(SCOUTS_CHOAM, 1), 5, scouts_opening=True)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "mid_auction_round"
    assert set(draw.options) == {"round:5", "round:6"}
    state = replace(state, scouts_mid_auction_round=5)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "mid_auction"
    assert set(draw.options) == {
        "highest_bidder_mid",
        "spies_for_hire_mid",
        "mercenaries",
        "critical_moment_mid",
        "choam_negotiations_mid",
    }
    state = replace(state, scouts_revealed=((5, "mercenaries"),))
    draw = _next_draw(state)
    assert draw is not None and draw.step == "event"
    # Round 6 with the auction already in round 5: only the event.
    draw = _next_draw(replace(state, round_number=6))
    assert draw is not None and draw.step == "event"


def test_late_auction_excludes_the_mid_family_and_the_sale_takes_the_other_round() -> (
    None
):
    base = UprisingRulesEngine().reset(SCOUTS, 1)
    state = _at_round(
        base,
        8,
        scouts_mid_auction_round=6,
        scouts_revealed=((6, "spies_for_hire_mid"),),
    )
    draw = _next_draw(state)
    assert draw is not None and draw.step == "late_auction_round"
    state = replace(state, scouts_late_auction_round=9)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "sale"
    assert set(draw.options) == {
        "unravel_the_future",
        "imperium_connections",
        "secrets_for_sale",
        "shadow_warfare",
    }
    state = replace(state, round_number=9)
    draw = _next_draw(state)
    assert draw is not None and draw.step == "late_auction"
    assert set(draw.options) == {
        "highest_bidder_late",
        "mercenaries",
        "critical_moment_late",
    }
    assert all(item_kind(o) == "auction" for o in draw.options)
    # Mercenaries as the mid auction keeps it out of the late one.
    state = replace(
        state, scouts_revealed=((6, "mercenaries"),), scouts_mid_auction_round=6
    )
    draw = _next_draw(state)
    assert draw is not None
    assert "mercenaries" not in draw.options
    assert {AUCTIONS_BY_ID[o].app.family for o in draw.options} == {1, 5, 6}
    assert _next_draw(replace(state, round_number=10)) is None


# --- Automatic events and round modifiers ---------------------------------------------


def _reveal(state: GameState, engine: UprisingRulesEngine, item_id: str) -> GameState:
    """Start a Scouts step in the event's first round and reveal ``item_id``."""

    event = EVENTS_BY_ID[item_id]
    # A mid auction round of 6 keeps round 5 to its event.
    opening = _at_round(
        state, event.rounds[0], scouts_opening=True, scouts_mid_auction_round=6
    )
    advanced = _advance_automatic(RuleResult(state=opening)).state
    step, decision = _draw_frame(advanced)
    assert step == "event"
    ticket = next(o for o in decision.options if o.startswith(f"{item_id}#"))
    return _choose(advanced, engine, ticket)


def test_mating_season_adds_one_spice_to_each_maker_space() -> None:
    engine = UprisingRulesEngine()
    state = _reveal(engine.reset(SCOUTS, 2), engine, "mating_season")
    assert dict(state.maker_bonus_spice) == {
        "deep_desert": 1,
        "hagga_basin": 1,
        "imperial_basin": 1,
    }
    assert state.decision_stack[-1].kind == FrameKind.TURN
    assert any(e.kind == "scouts_maker_spice_added" for e in state.event_log)


def test_mating_season_includes_tueks_sietch_with_bloodlines() -> None:
    # OQ-082: "Maker 아이콘이 있는 모든 칸(Bloodlines의 Tuek's Sietch 포함)에
    # spice 1을 더한다."
    engine = UprisingRulesEngine()
    config = RulesetConfig(arrakeen_scouts=True, bloodlines=True)
    # Esmar Tuek at the table brings Tuek's Sietch [Bloodlines p. 12].
    start = replace(
        engine.reset(config, 2),
        maker_bonus_spice=maker_bonus_spice_for(("esmar_tuek",)),
    )
    state = _reveal(start, engine, "mating_season")
    assert dict(state.maker_bonus_spice) == {
        "deep_desert": 1,
        "hagga_basin": 1,
        "imperial_basin": 1,
        "tuek_sietch": 1,
    }


def test_clear_the_market_replaces_the_row_and_removes_the_old_one() -> None:
    engine = UprisingRulesEngine()
    start = engine.reset(SCOUTS, 4)
    row, deck = start.imperium_row, start.imperium_deck
    state = _reveal(start, engine, "clear_the_market")
    assert state.imperium_row == deck[:5]
    assert state.imperium_deck == deck[5:]
    assert state.imperium_removed[-5:] == row


def test_clear_the_market_with_choam_shuffles_the_old_contracts_into_the_bank() -> None:
    """The CHOAM variant removes and replaces both face-up Contracts and
    mixes the old pair into the face-down supply (``spice.event.description
    .clearthemarket2``). OQ-083, user ruling 2026-09-29: the old pair goes
    into the bank first, then the two face-up Contracts are dealt from the
    shuffled whole, so one chance frame shuffles the bank and the old pair
    together."""

    engine = UprisingRulesEngine()
    start = engine.reset(SCOUTS_CHOAM, 4)
    old, bank = start.face_up_contract_ids, start.contract_bank
    assert len(old) == 2 and len(bank) > 2
    state = _reveal(start, engine, "clear_the_market_choam")
    step, decision = _draw_frame(state)
    assert step == "contract_shuffle"
    assert sorted(decision.options) == sorted((*bank, *old))
    assert decision.count == len(bank) + 2
    # An old Contract may come back face up: the deal is from the whole.
    shuffled = (old[1], *bank, old[0])
    state = engine.apply(
        state, ChanceOutcome(decision_id=decision.decision_id, values=shuffled)
    ).state
    assert state.face_up_contract_ids == (old[1], bank[0])
    assert state.contract_bank == (*bank[1:], old[0])
    assert state.decision_stack[-1].kind == FrameKind.TURN
    (cleared,) = [e for e in state.event_log if e.kind == "scouts_contracts_cleared"]
    assert dict(cleared.payload) == {
        "dealt": f"{old[1]},{bank[0]}",
        "removed": ",".join(old),
    }


def test_clear_the_market_with_choam_deals_two_from_a_random_shuffle() -> None:
    engine = UprisingRulesEngine()
    start = engine.reset(SCOUTS_CHOAM, 4)
    old, bank = start.face_up_contract_ids, start.contract_bank
    state = _reveal(start, engine, "clear_the_market_choam")
    state = _resolve_chance(engine, state, ChanceResolver(seed=9))
    assert len(state.face_up_contract_ids) == 2
    assert sorted((*state.face_up_contract_ids, *state.contract_bank)) == sorted(
        (*bank, *old)
    )
    assert state.decision_stack[-1].kind == FrameKind.TURN


@pytest.mark.parametrize("bank_size", [1, 0])
def test_clear_the_market_with_choam_on_a_short_bank_still_deals_two(
    bank_size: int,
) -> None:
    """OQ-083: with the old pair mixed in first, the bank and the old pair
    always hold two Contracts to deal while both face-up slots were full,
    even when the bank itself is short or empty; an old Contract may come
    back face up."""

    engine = UprisingRulesEngine()
    full = engine.reset(SCOUTS_CHOAM, 4)
    start = replace(full, contract_bank=full.contract_bank[:bank_size])
    old, bank = start.face_up_contract_ids, start.contract_bank
    assert len(old) == 2
    state = _reveal(start, engine, "clear_the_market_choam")
    step, decision = _draw_frame(state)
    assert step == "contract_shuffle"
    assert sorted(decision.options) == sorted((*bank, *old))
    assert decision.count == bank_size + 2
    shuffled = (*old, *bank)
    state = engine.apply(
        state, ChanceOutcome(decision_id=decision.decision_id, values=shuffled)
    ).state
    assert state.face_up_contract_ids == old
    assert state.contract_bank == bank
    assert state.decision_stack[-1].kind == FrameKind.TURN


@pytest.mark.parametrize(("face_up", "bank_size", "dealt"), [(1, 0, 1), (0, 0, 0)])
def test_clear_the_market_with_choam_deals_fewer_only_when_fewer_exist(
    face_up: int, bank_size: int, dealt: int
) -> None:
    """OQ-083: fewer than two are dealt only when the bank and the old pair
    together hold fewer (a face-up slot empties only once the bank is
    empty [Main p. 16]). One lone Contract comes back face up; with none
    anywhere the event changes nothing."""

    engine = UprisingRulesEngine()
    full = engine.reset(SCOUTS_CHOAM, 4)
    start = replace(
        full,
        face_up_contract_ids=full.face_up_contract_ids[:face_up],
        contract_bank=full.contract_bank[:bank_size],
    )
    old = start.face_up_contract_ids
    state = _reveal(start, engine, "clear_the_market_choam")
    state = _resolve_chance(engine, state, ChanceResolver(seed=9))
    assert len(state.face_up_contract_ids) == dealt
    assert state.face_up_contract_ids == old
    assert state.contract_bank == ()
    assert state.decision_stack[-1].kind == FrameKind.TURN


@pytest.mark.parametrize(
    ("event_id", "modifier"),
    [
        ("unlikely_allies", "ignore_influence_requirements"),
        ("eyes_on_arrakis", "faction_spaces_are_combat"),
        ("market_opening", "spice_must_flow_discount"),
        ("friends_everywhere", "any_faction_four_bonus"),
    ],
)
def test_a_round_modifier_lasts_until_the_next_round(
    event_id: str, modifier: str
) -> None:
    engine = UprisingRulesEngine()
    state = _reveal(engine.reset(SCOUTS, 6), engine, event_id)
    assert state.scouts_round_modifier == modifier
    # begin_round clears it.
    cleared = begin_round(
        replace(
            state,
            phase=GamePhase.ROUND_START,
            decision_stack=(),
            players=tuple(
                replace(p, deck=(*p.deck, *p.hand), hand=()) for p in state.players
            ),
        )
    ).state
    assert cleared.scouts_round_modifier == ""
    assert cleared.scouts_opening


# --- The Control defense and turn bookkeeping ----------------------------------------


def test_the_scouts_step_follows_the_control_defense() -> None:
    """Round Start is reveal, then the optional defense, then the draw.

    "Each round begins by revealing a new Conflict card ... Next, each
    player draws five cards" [Main p. 8]; the defense answers the reveal:
    "you may deploy one troop from your supply to the Conflict" [Main p. 10]
    [Main p. 20]. The Scouts step follows the whole Round Start, before the
    first turn (OQ-072), so the defense is asked in Round Start with the
    hands undrawn, and its answer draws them and leaves the step pending.
    """

    engine = UprisingRulesEngine()
    start = _at_round(
        engine.reset(SCOUTS, 2),
        4,
        phase=GamePhase.ROUND_START,
        scouts_opening=False,
    )
    assert start.first_player is not None
    hands = tuple(player.hand for player in start.players)
    undrawn = tuple(
        replace(player, deck=(*player.hand, *player.deck), hand=())
        for player in start.players
    )
    defense = DecisionFrame(
        kind=FrameKind.CONTROL_DEFENSE,
        frame_id="round:4:control_defense",
        decision=PlayerDecision(owner=1, prompt="Deploy one troop"),
        context=(("space_id", "arrakeen"),),
    )
    state = replace(start, players=undrawn, decision_stack=(defense,))

    result = apply_control_defense_action(
        state, DomainAction(action_id="decline_control_defense", actor=1)
    )

    assert [event.kind for event in result.events] == [
        "control_defense_declined",
        *["cards_drawn"] * 4,
    ]
    assert result.state.phase is GamePhase.PLAYER_TURNS
    assert result.state.scouts_opening
    assert result.state.decision_stack == ()
    assert all(len(player.hand) == 5 for player in result.state.players)
    assert tuple(player.hand for player in result.state.players) == hands
    advanced = _advance_automatic(result).state
    step, _ = _draw_frame(advanced)
    assert step == "event"


def test_the_first_turn_resets_the_first_players_turn_counters() -> None:
    engine = UprisingRulesEngine()
    state = _at_round(engine.reset(SCOUTS, 2), 10, scouts_opening=True)
    first = state.first_player
    assert first is not None
    touched = replace(
        state.players[first], spies_recalled_turn=1, contracts_completed_turn=1
    )
    players = tuple(touched if p.player_id == first else p for p in state.players)
    opened = _advance_automatic(RuleResult(state=replace(state, players=players))).state
    assert opened.decision_stack[-1].kind == FrameKind.TURN
    assert opened.players[first].spies_recalled_turn == 0
    assert opened.players[first].contracts_completed_turn == 0
    assert not opened.scouts_opening


# --- Whole games and drivers ----------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [
        SCOUTS,
        RulesetConfig(arrakeen_scouts=True, choam_module=True, immortality=True),
        RulesetConfig(
            arrakeen_scouts=True,
            choam_module=True,
            bloodlines=True,
            tech_module=True,
            leader_draft=True,
        ),
    ],
)
def test_random_games_reveal_the_whole_schedule(config: RulesetConfig) -> None:
    state = run_random_game(UprisingRulesEngine(), config, 12, 13).state
    assert state.phase is GamePhase.FINISHED
    kinds = Counter(item_kind(item) for _, item in state.scouts_revealed)
    rounds = state.round_number
    # Everything due up to the last round played was revealed.
    assert len(state.scouts_subcommittees) == 5
    if rounds >= 3:
        assert kinds["mission"] == 3
    assert kinds["event"] == max(0, min(rounds, 7) - 3)


def test_pettingzoo_reset_resolves_the_opening_draws() -> None:
    pytest.importorskip("pettingzoo")
    from dune_imperium.adapters.pettingzoo_env import env as make_env

    environment = make_env(arrakeen_scouts=True)
    environment.reset(seed=3)
    state = environment._state
    assert state is not None
    assert len(state.scouts_subcommittees) == 5
    assert state.decision_stack[-1].kind == FrameKind.TURN
