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
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue

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
