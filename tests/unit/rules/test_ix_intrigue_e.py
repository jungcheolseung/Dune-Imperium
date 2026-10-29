"""Ix Intrigue batch 5 (War Chest, Machine Culture, Diversion), through the
original + Ix engine and ActionCodec.

Rules: imperium-base.md 5 and 10 (Plot, Combat and Endgame Intrigue timing);
"To play an Intrigue card, you must meet its conditions and pay its costs."
[FAQ p. 2]; rise-of-ix.md 9.3 and 15 (OQ-113 (C): Machine Culture's Plot half
is a cost line paid with the tile's spice, so it is played only when a tile
can be bought, and once played the tile is taken), 6 (a "unit" is a troop or
a dreadnought; Diversion's "four or more units" counts both) and the deploy
count of Distraction (OQ-016, OQ-029). The card text is the Steam app's (its
log strings, English text and screen pieces; the cards print icons only).
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    PlayerState,
    Resources,
)
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.endgame import begin_endgame_intrigue
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


def _in_deck(card: str, config: RulesetConfig) -> bool:
    return f"intrigue:{card}:0" in content_for(config).intrigue_deck_instance_ids


def _window(card: str, **changes: Any) -> GameState:
    """The Endgame window of an original + Ix game, seat 0 (the First Player)
    holding ``card`` and ``changes``."""

    changes.setdefault(
        "dreadnoughts_supply",
        2
        - changes.get("dreadnoughts_garrison", 0)
        - changes.get("dreadnoughts_conflict", 0),
    )
    seat = PlayerState(player_id=0, intrigue_cards=(f"intrigue:{card}:0",), **changes)
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


def _end_play(state: GameState, card: str, option: int) -> GameState:
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", f"intrigue:{card}:0"), ("option", option)),
    )
    result = apply_whole(ENGINE, state, play).state
    for row in ENGINE.legal_actions(result, 0):
        assert CODEC.decode(CODEC.encode(row), 0) == row
    return result


# One troop in the Conflict and its 2 strength: the unit a Combat Intrigue needs.
UNIT: dict[str, int] = {"troops_conflict": 1, "combat_strength": 2}

# War Chest ----------------------------------------------------------------------

WAR_CHEST = "war_chest"


def test_war_chest_is_a_combat_and_endgame_card_in_the_ix_deck() -> None:
    """ "2 Solari -> 4 swords" [COMBAT] -OR- "If you have 10 or more Solari:
    1 VP" [ENDGAME] [War Chest card, Steam app text, log lines and screen
    pieces; the log reads "played War Chest and spent 2 Solari to gain 4
    swords"]; one copy, shuffled in with Rise of Ix only [Rise of Ix p. 2]."""
    entry = intrigue_card_for_instance("intrigue:war_chest:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert [option.timing.value for option in entry.options] == ["combat", "endgame"]
    assert _in_deck(WAR_CHEST, CONFIG)
    assert not _in_deck(WAR_CHEST, ORIGINAL)
    assert intrigue_card_text(entry) == [
        "Combat — Pay 2 solari → Gain 4 swords",
        "Endgame — If you have 10 or more solari: Gain 1 VP",
    ]
    assert len(intrigue_card_text_ko(entry)) == 2


@pytest.mark.parametrize(
    ("solari", "offered"), [(0, set()), (1, set()), (2, {0}), (9, {0}), (10, {0})]
)
def test_war_chest_combat_pays_two_solari(solari: int, offered: set[int]) -> None:
    """ "To play an Intrigue card, you must meet its conditions and pay its
    costs." [FAQ p. 2]: the 2 Solari left of the arrow are a cost, so a seat
    with fewer does not play the Combat half; the Endgame half is not one of
    this window's."""
    state = _fight(WAR_CHEST, resources=Resources(solari=solari), **UNIT)
    assert _options(state, WAR_CHEST) == offered


def test_war_chest_combat_adds_four_swords_for_two_solari() -> None:
    """ "spent 2 Solari to gain 4 swords" [War Chest card, Steam app log
    line]: the Combat marker rises by four, the Solari fall by two, and the
    card is discarded."""
    state = _fight(WAR_CHEST, resources=Resources(solari=5), troops_conflict=2)
    before = state.players[0].combat_strength
    done = _play(state, WAR_CHEST)
    assert done.players[0].combat_strength == before + 4
    assert done.players[0].resources.solari == 3
    assert "intrigue:war_chest:0" in done.intrigue_discard
    assert done.players[0].intrigue_cards == ()


def test_war_chest_combat_needs_a_unit_in_the_conflict() -> None:
    """A Combat Intrigue is played by a seat with a unit in the Conflict
    [Main p. 14]; the Solari alone do not play it."""
    state = _fight(
        WAR_CHEST,
        resources=Resources(solari=5),
        troops_garrison=2,
        troops_supply=10,
        troops_conflict=0,
    )
    assert _options(state, WAR_CHEST) == set()


def test_war_chest_combat_plays_with_a_lone_dreadnought() -> None:
    """A dreadnought is a unit [Rise of Ix p. 6], so a seat with only one in
    the Conflict plays the card."""
    state = _fight(
        WAR_CHEST,
        resources=Resources(solari=2),
        dreadnoughts_conflict=1,
        combat_strength=3,
    )
    assert _options(state, WAR_CHEST) == {0}


def test_war_chest_is_not_a_plot() -> None:
    """Combat Intrigue is played in the Combat phase only [DI p. 12], and
    Endgame Intrigue in the Endgame window only [DI p. 13]: the Agent turn
    offers neither half."""
    state = _start(
        WAR_CHEST,
        resources=Resources(solari=12),
        troops_conflict=1,
        combat_strength=2,
    )
    assert _options(state, WAR_CHEST) == set()


@pytest.mark.parametrize(("solari", "offered"), [(9, set()), (10, {1}), (30, {1})])
def test_war_chest_endgame_needs_ten_solari(solari: int, offered: set[int]) -> None:
    """ "If you have 10 or more Solari:" one VP [War Chest card, Steam app
    text]: a printed condition, mandatory [FAQ p. 2], judged as the card is
    played (OQ-028). The Combat half is not an Endgame card."""
    state = _window(WAR_CHEST, resources=Resources(solari=solari))
    assert _offered(state) == offered


def test_war_chest_endgame_scores_one_victory_point_and_keeps_the_solari() -> None:
    """The Endgame half is a condition, not a cost: its 1 VP comes with every
    Solari still held."""
    state = _window(WAR_CHEST, resources=Resources(solari=10), victory_points=7)
    done = _end_play(state, WAR_CHEST, 1)
    assert done.players[0].victory_points == 8
    assert done.players[0].resources.solari == 10
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == ("intrigue:war_chest:0",)
    assert _offered(done) == set()


def test_war_chest_endgame_may_be_declined() -> None:
    """Playing is a choice: the seat passes and keeps the card [DI p. 13]."""
    state = _window(WAR_CHEST, resources=Resources(solari=10))
    passed = apply_whole(
        ENGINE, state, DomainAction(action_id="pass_endgame_intrigue", actor=0)
    ).state
    assert passed.players[0].intrigue_cards == ("intrigue:war_chest:0",)
    assert passed.players[0].victory_points == state.players[0].victory_points
