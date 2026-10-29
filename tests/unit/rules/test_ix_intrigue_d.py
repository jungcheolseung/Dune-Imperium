"""Ix Intrigue batch 4 (the dreadnought and unit cards), through the original +
Ix engine and ActionCodec.

Rules: imperium-base.md 5 and 10 (Plot and Combat Intrigue timing); "To play
an Intrigue card, you must meet its conditions and pay its costs." [FAQ p. 2];
rise-of-ix.md 6 (a "unit" is a troop or a dreadnought; a dreadnought is 3
strength, and one alone keeps a seat's strength above 0 and lets it play
Combat Intrigue), 9.3 and 15 (OQ-113 (C): Advanced Weaponry's Plot half is a
3 Solari cost line that needs a dreadnought left in the supply). The card
text is the Steam app's (its log strings, English text and screen pieces; the
cards print icons only).
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import (
    AtLeastOfConditions,
    DreadnoughtsAtLeast,
    HasHighCouncil,
    SpiceAtLeast,
    WaterAtLeast,
)
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerState,
    Resources,
)
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.endgame import begin_endgame_intrigue, final_standings
from dune_imperium.rules.intrigue import legal_intrigue_play_actions

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
ENGINE = UprisingRulesEngine(
    leader_ids=(
        "glossu_rabban",
        "count_ilban_richese",
        "earl_memnon_thorvald",
        "countess_ariana_thorvald",
    )
)
CODEC = ActionCodec(CONFIG)


def _seat(state: GameState, seat: int = 0, **changes: Any) -> GameState:
    players = list(state.players)
    troop_fields = ("troops_supply", "troops_garrison", "troops_conflict")
    if any(field in changes for field in troop_fields):
        owner = players[seat]
        if "troops_supply" in changes:
            changes.setdefault(
                "troops_conflict",
                12 - changes["troops_supply"] - changes.get("troops_garrison", 0),
            )
            changes.setdefault(
                "troops_garrison",
                12 - changes["troops_supply"] - changes["troops_conflict"],
            )
        else:
            changes["troops_supply"] = 12 - sum(
                changes.get(field, getattr(owner, field))
                for field in ("troops_garrison", "troops_conflict")
            )
    if "dreadnoughts_garrison" in changes or "dreadnoughts_conflict" in changes:
        changes["dreadnoughts_supply"] = (
            2
            - changes.get("dreadnoughts_garrison", 0)
            - changes.get("dreadnoughts_conflict", 0)
        )
    if "agent_locations" in changes:
        changes["agents_available"] = 2 - len(changes["agent_locations"])
    if "tech_ids" in changes:
        # A held tile lies on no stack (the state checks it is in one zone).
        state = replace(
            state,
            tech_stacks=tuple(
                tuple(tile for tile in stack if tile not in changes["tech_ids"])
                for stack in state.tech_stacks
            ),
        )
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _start(card: str, **changes: Any) -> GameState:
    """Round 1 of the original + Ix game at seat 0's first turn, seat 0
    holding ``card``."""

    state = ENGINE.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return _seat(state, intrigue_cards=(f"intrigue:{card}:0",), **changes)


def _combat(state: GameState) -> GameState:
    """The Combat Intrigue loop of ``state``'s Conflict, seat 0 first."""

    state = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    return begin_combat_intrigue(state).state


def _fight(card: str, *, rival: int = 1, **changes: Any) -> GameState:
    """Seat 0 holding ``card`` and seat 1 with ``rival`` troops, both in the
    Conflict, at seat 0's Combat Intrigue priority."""

    state = _start(card, **changes)
    state = _seat(state, 1, troops_conflict=rival, combat_strength=2 * rival)
    return _combat(state)


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    for row in ENGINE.legal_actions(state, seat):
        assert CODEC.decode(CODEC.encode(row), seat) == row
    return ENGINE.whole_actions(state, seat)


def _take(state: GameState, action_id: str, **arguments: Any) -> GameState:
    (row,) = [
        row
        for row in _rows(state)
        if row.action_id == action_id and dict(row.arguments) == arguments
    ]
    result = apply_whole(ENGINE, state, row).state
    _rows(result)
    return result


def _play(state: GameState, card: str, option: int = 0) -> GameState:
    return _take(state, "play_intrigue", card_id=f"intrigue:{card}:0", option=option)


def _options(state: GameState, card: str) -> set[int]:
    return {
        int(dict(row.arguments)["option"])
        for row in _rows(state)
        if row.action_id == "play_intrigue"
        and dict(row.arguments)["card_id"] == f"intrigue:{card}:0"
    }


def _action_ids(state: GameState, seat: int = 0) -> list[str]:
    return [row.action_id for row in _rows(state, seat)]


def _visit(state: GameState, space: str, card: str = "diplomacy") -> GameState:
    card_id = f"player:0:starter:{card}:0"
    state = _seat(
        state,
        hand=(card_id,),
        deck=tuple(card for card in state.players[0].deck if card != card_id),
    )
    (placement,) = [
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == space
    ]
    return apply_placement(ENGINE, state, placement).state


def _in_deck(card: str, config: RulesetConfig) -> bool:
    return f"intrigue:{card}:0" in content_for(config).intrigue_deck_instance_ids


# Advanced Weaponry --------------------------------------------------------------

THREE_TECHS = ("detonation_devices", "spaceport", "troop_transports")


def test_advanced_weaponry_is_a_plot_and_combat_card_in_the_ix_deck() -> None:
    """ "3 Solari -> Dreadnought" [PLOT] -OR- "If you have three or more
    Techs: 4 swords" [COMBAT] [Advanced Weaponry card, Steam app text and
    screen pieces]; one copy, shuffled in with Rise of Ix only [Rise of Ix
    p. 2]."""
    entry = intrigue_card_for_instance("intrigue:advanced_weaponry:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert [option.timing.value for option in entry.options] == ["plot", "combat"]
    assert _in_deck("advanced_weaponry", CONFIG)
    assert not _in_deck("advanced_weaponry", ORIGINAL)
    assert intrigue_card_text(entry) == [
        "Plot — Pay 3 solari → Commission a dreadnought",
        "Combat — If you have 3 or more Tech tiles: Gain 4 swords",
    ]
    assert intrigue_card_text_ko(entry) == [
        "음모 — {solari:3} 지불 {arrow_right} Commission a dreadnought",
        "전투 — {tech_tile} 3 이상이면: {sword:4}",
    ]


@pytest.mark.parametrize("supply", [2, 1])
def test_advanced_weaponry_plot_pays_three_solari_to_commission(supply: int) -> None:
    """ "3 Solari -> Dreadnought": the Solari are the cost, and the icon says
    "you may commission" a dreadnought from the supply to the garrison
    [Rise of Ix p. 6]."""
    state = _start(
        "advanced_weaponry",
        resources=Resources(solari=4),
        dreadnoughts_supply=supply,
        dreadnoughts_garrison=2 - supply,
    )
    assert _options(state, "advanced_weaponry") == {0}
    opened = _play(state, "advanced_weaponry")
    assert opened.players[0].resources.solari == 1
    assert {"commission_intrigue_dreadnought", "decline_intrigue_dreadnought"} <= set(
        _action_ids(opened)
    )
    done = _take(opened, "commission_intrigue_dreadnought")
    owner = done.players[0]
    assert owner.dreadnoughts_supply == supply - 1
    assert owner.dreadnoughts_garrison == 2 - supply + 1
    assert owner.dreadnoughts_conflict == 0
    assert "intrigue:advanced_weaponry:0" in done.intrigue_discard
    assert _in_deck("advanced_weaponry", CONFIG)


def test_advanced_weaponry_plot_may_leave_the_dreadnought_after_paying() -> None:
    """ "you may commission" [Rise of Ix p. 6]: the icon is optional, and the
    3 Solari of the card's cost line are paid once the card is played
    [FAQ p. 3]."""
    state = _start("advanced_weaponry", resources=Resources(solari=3))
    done = _take(_play(state, "advanced_weaponry"), "decline_intrigue_dreadnought")
    owner = done.players[0]
    assert owner.resources.solari == 0
    assert (owner.dreadnoughts_supply, owner.dreadnoughts_garrison) == (2, 0)
    assert "intrigue:advanced_weaponry:0" in done.intrigue_discard


def test_advanced_weaponry_plot_needs_three_solari() -> None:
    """ "To play an Intrigue card, you must meet its conditions and pay its
    costs." [FAQ p. 2]."""
    state = _start("advanced_weaponry", resources=Resources(solari=2))
    assert _options(state, "advanced_weaponry") == set()


def test_advanced_weaponry_plot_is_not_played_with_both_dreadnoughts_out() -> None:
    """ "Advanced Weaponry는 dreadnought 둘이 있어도 3 Solari를 내고 낼 수
    있다(출처 없음, 추정)" is **not adopted**: it is a 3 Solari cost line, so
    without a dreadnought left in the supply the Plot half is not played
    (rise-of-ix.md 9.3, OQ-113 (C) of 2026-10-24; 15). The garrison, the
    Conflict and a Control space all hold dreadnoughts that are not in the
    supply."""
    state = _start(
        "advanced_weaponry",
        resources=Resources(solari=9),
        dreadnoughts_garrison=1,
        dreadnoughts_conflict=1,
    )
    assert _options(state, "advanced_weaponry") == set()
    state = _start(
        "advanced_weaponry", resources=Resources(solari=9), dreadnoughts_garrison=2
    )
    assert _options(state, "advanced_weaponry") == set()


def test_advanced_weaponry_plot_plays_in_the_reveal_turn() -> None:
    """A Plot is played in the owner's Agent or Reveal turn [DI pp. 7-8]."""
    state = _start("advanced_weaponry", resources=Resources(solari=3))
    state = _take(state, "reveal_turn")
    assert _options(state, "advanced_weaponry") == {0}
    done = _take(_play(state, "advanced_weaponry"), "commission_intrigue_dreadnought")
    assert done.players[0].dreadnoughts_garrison == 1


def test_advanced_weaponry_commission_before_a_combat_space_may_deploy() -> None:
    """ "If you commissioned the dreadnought while sending an Agent to a
    Combat space, you may deploy it to the Conflict" [Rise of Ix p. 6]: the
    Plot played first in the turn, then an Agent to Stillsuits (a Combat
    space), offers the new dreadnought for deployment."""
    state = _start("advanced_weaponry", resources=Resources(solari=3))
    state = _take(_play(state, "advanced_weaponry"), "commission_intrigue_dreadnought")
    placed = _visit(state, "stillsuits")
    deployable = [
        row for row in _rows(placed) if row.action_id == "deploy_dreadnoughts"
    ]
    assert [dict(row.arguments)["count"] for row in deployable] == [1]
    done = apply_whole(ENGINE, placed, deployable[0]).state
    assert done.players[0].dreadnoughts_conflict == 1
    assert done.players[0].dreadnoughts_garrison == 0
    assert done.players[0].combat_strength == 3


def test_advanced_weaponry_is_not_a_combat_card_in_the_plot_window() -> None:
    """Combat Intrigue is played in the Combat phase only [DI p. 12]; its
    Combat half needs the Tech tiles, so it is not offered here whatever the
    seat holds."""
    state = _start(
        "advanced_weaponry", resources=Resources(solari=3), tech_ids=THREE_TECHS
    )
    assert _options(state, "advanced_weaponry") == {0}


@pytest.mark.parametrize("techs", [0, 1, 2])
def test_advanced_weaponry_combat_needs_three_tech_tiles(techs: int) -> None:
    """ "If you have three or more Techs:" [Advanced Weaponry card, Steam app
    text] is a printed condition, mandatory [FAQ p. 2]; only the Plot half is
    free of it."""
    state = _fight(
        "advanced_weaponry",
        tech_ids=THREE_TECHS[:techs],
        troops_conflict=1,
        combat_strength=2,
    )
    assert _options(state, "advanced_weaponry") == set()


@pytest.mark.parametrize(
    "units",
    [
        {"troops_conflict": 1, "combat_strength": 2},
        {"dreadnoughts_conflict": 1, "combat_strength": 3},
    ],
)
def test_advanced_weaponry_combat_adds_four_swords_with_three_tech_tiles(
    units: dict[str, int],
) -> None:
    """ "If you have three or more Techs:" four swords [Steam app text and log
    "gain 4 swords"]; a Combat Intrigue needs a unit in the Conflict, and a
    dreadnought is one [Rise of Ix p. 6] [FAQ p. 2]. The Plot half's 3 Solari
    are not paid."""
    state = _fight(
        "advanced_weaponry",
        resources=Resources(solari=5),
        tech_ids=THREE_TECHS,
        **units,
    )
    assert _options(state, "advanced_weaponry") == {1}
    before = state.players[0].combat_strength
    done = _play(state, "advanced_weaponry", 1)
    assert done.players[0].combat_strength == before + 4
    assert done.players[0].resources.solari == 5
    assert done.players[0].dreadnoughts_supply == 2 - units.get(
        "dreadnoughts_conflict", 0
    )
    assert "intrigue:advanced_weaponry:0" in done.intrigue_discard


def test_advanced_weaponry_combat_needs_a_unit_in_the_conflict() -> None:
    """A Combat Intrigue is played by a seat with a unit in the Conflict
    [Main p. 14]; a dreadnought in the garrison "does nothing" [FAQ p. 2]."""
    state = _fight("advanced_weaponry", tech_ids=THREE_TECHS, dreadnoughts_garrison=1)
    assert _options(state, "advanced_weaponry") == set()


# Grand Conspiracy ----------------------------------------------------------------

CONSPIRACY = "intrigue:grand_conspiracy:0"
# The Reserve card's copies: "reserve:imperium_the_spice_must_flow:<n>".
SPICE_MUST_FLOW = "reserve:imperium_the_spice_must_flow:{}"

# The four items, as the keyword arguments that make a seat meet each one.
ITEMS: dict[str, dict[str, Any]] = {
    "dreadnoughts": {"dreadnoughts_garrison": 1, "dreadnoughts_conflict": 1},
    "spice_must_flow": {"discard_pile": (SPICE_MUST_FLOW.format(0),)},
    "influence": {"influence": Influence(emperor=4, fremen=5)},
    "council": {"high_council": True},
}


def _items(*names: str) -> dict[str, Any]:
    held: dict[str, Any] = {}
    for name in names:
        held.update(ITEMS[name])
    return held


def _window(**changes: Any) -> GameState:
    """The Endgame window of an original + Ix game, seat 0 (the First Player)
    holding Grand Conspiracy and ``changes``."""

    changes.setdefault(
        "dreadnoughts_supply",
        2
        - changes.get("dreadnoughts_garrison", 0)
        - changes.get("dreadnoughts_conflict", 0),
    )
    seat = PlayerState(player_id=0, intrigue_cards=(CONSPIRACY,), **changes)
    players = (seat, *(PlayerState(player_id=n) for n in range(1, 4)))
    content = content_for(CONFIG)
    state = GameState(
        config=CONFIG,
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        maker_bonus_spice=tuple((space, 0) for space in content.maker_space_ids),
        players=players,
    )
    return begin_endgame_intrigue(state).state


def _offered(state: GameState) -> set[int]:
    for row in ENGINE.legal_actions(state, 0):
        assert CODEC.decode(CODEC.encode(row), 0) == row
    return {
        int(dict(action.arguments)["option"])
        for action in legal_intrigue_play_actions(state, 0)
    }


def _conspire(state: GameState, option: int) -> GameState:
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", CONSPIRACY), ("option", option)),
    )
    result = apply_whole(ENGINE, state, play).state
    for row in ENGINE.legal_actions(result, 0):
        assert CODEC.decode(CODEC.encode(row), 0) == row
    return result


def test_grand_conspiracy_is_two_exclusive_endgame_options() -> None:
    """ "• 2 dreadnoughts • 1+ The Spice Must Flow • 4+ Influence on 2+
    Influence tracks • A seat on the High Council", then "If you have any
    three:" one VP -OR- "If you have all four:" two VP [Grand Conspiracy card,
    Steam app text; its prefab has one VP icon beside the first line, two
    beside the second and the -OR- frame between them]. Two exclusive
    options, as Plans Within Plans' (OQ-058: "—OR—로 나뉜 카드는 그대로 배타
    option", imperium-base.md 16); one copy, shuffled in with Rise of Ix only
    [Rise of Ix p. 2]."""
    entry = intrigue_card_for_instance(CONSPIRACY)
    assert entry.play_data_complete
    assert entry.copies == 1
    assert [option.timing.value for option in entry.options] == ["endgame"] * 2
    assert [
        option.sections[0].rewards[0].amount  # type: ignore[union-attr]
        for option in entry.options
    ] == [1, 2]
    assert all(
        len(option.sections) == 1 and not option.sections[0].costs
        for option in entry.options
    )
    assert _in_deck("grand_conspiracy", CONFIG)
    assert not _in_deck("grand_conspiracy", ORIGINAL)
    assert intrigue_card_text(entry) == [
        "Endgame — If at least 3 of these hold: you have 2 dreadnoughts; you own"
        " 1 or more copies of The Spice Must Flow; you have 4 or more Influence"
        " on at least 2 Faction tracks; you hold a High Council seat: Gain 1 VP",
        "Endgame — If you have 2 dreadnoughts and you own 1 or more copies of The"
        " Spice Must Flow and you have 4 or more Influence on at least 2 Faction"
        " tracks and you hold a High Council seat: Gain 2 VP",
    ]
    assert len(intrigue_card_text_ko(entry)) == 2


@pytest.mark.parametrize(
    ("held", "offered"),
    [
        ((), set()),
        (("dreadnoughts",), set()),
        (("council", "influence"), set()),
        (("dreadnoughts", "spice_must_flow", "council"), {0}),
        (("dreadnoughts", "spice_must_flow", "influence"), {0}),
        (("dreadnoughts", "influence", "council"), {0}),
        (("spice_must_flow", "influence", "council"), {0}),
        (("dreadnoughts", "spice_must_flow", "influence", "council"), {0, 1}),
    ],
)
def test_grand_conspiracy_offers_one_vp_for_any_three_and_both_for_all_four(
    held: tuple[str, ...], offered: set[int]
) -> None:
    """ "If you have any three:" one VP, "If you have all four:" two VP
    [Grand Conspiracy card]; "you must meet its conditions" [FAQ p. 2] and a
    condition is judged as the card is resolved (OQ-028)."""
    assert _offered(_window(**_items(*held))) == offered


@pytest.mark.parametrize(
    ("held", "option", "points"),
    [
        (("dreadnoughts", "spice_must_flow", "council"), 0, 1),
        (("dreadnoughts", "spice_must_flow", "influence", "council"), 1, 2),
        # The all-four seat may still take the one-VP option (a choice).
        (("dreadnoughts", "spice_must_flow", "influence", "council"), 0, 1),
    ],
)
def test_grand_conspiracy_scores_its_victory_points(
    held: tuple[str, ...], option: int, points: int
) -> None:
    """One VP for any three, two for all four, never both together: the
    options are exclusive and the card is discarded once played."""
    state = _window(**_items(*held))
    done = _conspire(state, option)
    assert done.players[0].victory_points == state.players[0].victory_points + points
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (CONSPIRACY,)
    assert _offered(done) == set()


def test_grand_conspiracy_changes_the_final_standings() -> None:
    """The two Victory Points count in the final ranking (``final_standings``):
    seat 0 trails seat 1 by one point and passes it."""
    state = _window(
        victory_points=8,
        **_items("dreadnoughts", "spice_must_flow", "influence", "council"),
    )
    state = replace(
        state,
        players=(
            *state.players[:1],
            replace(state.players[1], victory_points=9),
            *state.players[2:],
        ),
    )
    assert [s.player for s in final_standings(state)[:2]] == [1, 0]
    done = _conspire(state, 1)
    assert [s.player for s in final_standings(done)[:2]] == [0, 1]
    assert done.players[0].victory_points == 10


def test_grand_conspiracy_is_an_endgame_card_only() -> None:
    """Endgame Intrigue is played in the Endgame window only [DI p. 13]
    (imperium-base.md 10), never in an Agent or Reveal turn."""
    state = _start(
        "grand_conspiracy",
        **_items("dreadnoughts", "spice_must_flow", "influence", "council"),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _options(state, "grand_conspiracy") == set()
    assert _options(_take(state, "reveal_turn"), "grand_conspiracy") == set()


def test_grand_conspiracy_may_be_declined_in_the_window() -> None:
    """Playing is a choice: the seat passes and keeps the card [DI p. 13]."""
    state = _window(**_items("dreadnoughts", "spice_must_flow", "council"))
    passed = apply_whole(
        ENGINE, state, DomainAction(action_id="pass_endgame_intrigue", actor=0)
    ).state
    assert passed.players[0].intrigue_cards == (CONSPIRACY,)
    assert passed.players[0].victory_points == state.players[0].victory_points


# The items one by one ---------------------------------------------------------


def _with_two_items(**changes: Any) -> GameState:
    """Two sure items (the council seat and an Influence spread) beside the
    one under test: any one more makes three."""

    return _window(**_items("council", "influence"), **changes)


@pytest.mark.parametrize(
    "stand",
    [
        {"dreadnoughts_garrison": 2},
        {"dreadnoughts_conflict": 2},
        {"dreadnoughts_garrison": 1, "dreadnoughts_conflict": 1},
    ],
)
def test_two_dreadnoughts_count_wherever_they_stand(stand: dict[str, int]) -> None:
    """ "2 dreadnoughts" [Grand Conspiracy card] is the count the seat has:
    "Grand Conspiracy의 '2 dreadnoughts'는 가진 수이고" (OQ-121,
    docs/rules/open-questions.md), a garrison and a Conflict dreadnought alike
    (a dreadnought in the garrison "does nothing" in a Conflict [FAQ p. 2],
    but it is the seat's)."""
    assert _offered(_with_two_items(**stand)) == {0}


def test_two_dreadnoughts_count_one_on_a_control_space() -> None:
    """The dreadnought that took a Control space is still the seat's [Rise of
    Ix p. 6]; it stands in ``GameState.dreadnought_control``, outside the
    seat's supply, garrison and Conflict."""
    state = _with_two_items(dreadnoughts_garrison=1, dreadnoughts_supply=0)
    assert _offered(state) == set()
    state = replace(state, dreadnought_control=(("carthag", 0, False),))
    assert _offered(state) == {0}
    # The one waiting to leave at the next Combat's end is still on its space.
    state = replace(state, dreadnought_control=(("carthag", 0, True),))
    assert _offered(state) == {0}


@pytest.mark.parametrize(
    "stand",
    [
        {},
        {"dreadnoughts_garrison": 1},
        {"dreadnoughts_conflict": 1},
    ],
)
def test_a_dreadnought_left_in_the_supply_is_not_one_the_seat_has(
    stand: dict[str, int],
) -> None:
    """A seat holds two dreadnoughts when both are out of its supply
    [Rise of Ix p. 6]; with one still in the supply it has one."""
    assert _offered(_with_two_items(**stand)) == set()


def test_another_seats_dreadnought_on_a_control_space_is_not_the_seats() -> None:
    """The dreadnought on a Control space counts for its owner alone."""
    state = _with_two_items(dreadnoughts_garrison=1, dreadnoughts_supply=0)
    state = replace(state, dreadnought_control=(("carthag", 1, False),))
    assert _offered(state) == set()


@pytest.mark.parametrize("zone", ["deck", "hand", "discard_pile", "in_play"])
def test_a_spice_must_flow_counts_in_every_zone_the_seat_owns(zone: str) -> None:
    """ "1+ The Spice Must Flow" counts every copy the seat has -- deck, hand,
    discard pile and play area, never a trashed one (OQ-123, user ruling
    2026-10-22; Grand Conspiracy is named there)."""
    dreadnoughts = _items("dreadnoughts", "council")
    assert _offered(_window(**dreadnoughts)) == set()
    held = _window(**dreadnoughts, **{zone: (SPICE_MUST_FLOW.format(3),)})
    assert _offered(held) == {0}


def test_a_spice_must_flow_of_the_uprising_reserve_counts_too() -> None:
    """Both printings of the Reserve card are The Spice Must Flow
    (``SpiceMustFlowCardsAtLeast``)."""
    held = _window(
        **_items("dreadnoughts", "council"),
        discard_pile=("reserve:the_spice_must_flow:0",),
    )
    assert _offered(held) == {0}


@pytest.mark.parametrize(
    ("influence", "holds"),
    [
        (Influence(emperor=4, fremen=4), True),
        (Influence(emperor=6, spacing_guild=5), True),
        (Influence(4, 4, 4, 4), True),
        (Influence(emperor=4, fremen=3), False),
        (Influence(emperor=6), False),
        (Influence(3, 3, 3, 3), False),
        (Influence(), False),
    ],
)
def test_four_influence_on_two_tracks(influence: Influence, holds: bool) -> None:
    """ "4+ Influence on 2+ Influence tracks": two Faction tracks at 4 or
    more, a third at 3 notwithstanding."""
    state = _window(**_items("dreadnoughts", "council"), influence=influence)
    assert _offered(state) == ({0} if holds else set())


def test_the_council_seat_is_the_owners_own() -> None:
    """ "A seat on the High Council": an opponent's seat is not the owner's."""
    state = _window(**_items("dreadnoughts", "influence"))
    state = replace(
        state,
        players=(
            state.players[0],
            replace(state.players[1], high_council=True),
            *state.players[2:],
        ),
    )
    assert _offered(state) == set()


def test_the_other_seats_items_are_not_the_owners() -> None:
    """Every item is read off the seat that plays the card."""
    state = _window()
    rival = PlayerState(
        player_id=1,
        dreadnoughts_garrison=2,
        high_council=True,
        influence=Influence(emperor=4, fremen=4),
        discard_pile=(SPICE_MUST_FLOW.format(1),),
    )
    state = replace(state, players=(state.players[0], rival, *state.players[2:]))
    assert _offered(state) == set()


def test_the_new_conditions_reject_counts_they_cannot_mean() -> None:
    """A seat has one or two dreadnoughts to count, and a "some of these"
    count sits strictly between one and all of at least three conditions."""
    with pytest.raises(ValueError):
        DreadnoughtsAtLeast(0)
    with pytest.raises(ValueError):
        DreadnoughtsAtLeast(3)
    three = (HasHighCouncil(), WaterAtLeast(1), SpiceAtLeast(1))
    with pytest.raises(ValueError):
        AtLeastOfConditions(1, three)
    with pytest.raises(ValueError):
        AtLeastOfConditions(3, three)
    with pytest.raises(ValueError):
        AtLeastOfConditions(2, three[:2])
    assert AtLeastOfConditions(2, three).count == 2
