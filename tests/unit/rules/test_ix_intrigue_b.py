"""Ix Intrigue batch 2, through the original + Ix engine and ActionCodec.

Rules: imperium-base.md 5: "Plot Intrigue는 자기 Agent·Reveal turn 안에서
아무 때나 낸다. [DI pp. 7-8]"; 16: "Finesse(Ix)·Shifting Allegiances로 같은
진영을 잃고 다시 얻을 수 있다 [FAQ p. 4]". rise-of-ix.md 9.3 requires
Strongarm's visited Faction. OQ-071 requires a live reward for paid lines;
OQ-113 (C) permits free effects to fizzle, preserving printed conditions
("To play an Intrigue card, you must meet its conditions and pay its costs."
[FAQ p. 2]). English icon-only effects below spell out the Steam UI pieces.
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
    Influence,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
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
    state = ENGINE.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return _seat(state, intrigue_cards=(f"intrigue:{card}:0",), **changes)


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
    return apply_whole(ENGINE, state, row).state


def _play(state: GameState, card: str, option: int = 0) -> GameState:
    return _take(state, "play_intrigue", card_id=f"intrigue:{card}:0", option=option)


def _options(state: GameState, card: str) -> set[int]:
    return {
        int(dict(row.arguments)["option"])
        for row in _rows(state)
        if row.action_id == "play_intrigue"
        and dict(row.arguments)["card_id"] == f"intrigue:{card}:0"
    }


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


# Expedite -----------------------------------------------------------------


@pytest.mark.parametrize("space", range(4))
def test_expedite_pays_one_spice_and_moves_from_each_space(space: int) -> None:
    """ "1 spice -> Freighter" [Steam app screen pieces; Rise of Ix p. 5]."""
    state = _start("expedite", resources=Resources(spice=2), freighter_space=space)
    assert _options(state, "expedite") == {0}
    opened = _play(state, "expedite")
    assert opened.players[0].resources.spice == 1
    ids = {row.action_id for row in _rows(opened)}
    assert ("advance_intrigue_freighter" in ids) == (space < 3)
    assert ("recall_intrigue_freighter" in ids) == (space > 0)
    if space < 3:
        done = _take(opened, "advance_intrigue_freighter")
        assert done.players[0].freighter_space == space + 1
        assert "intrigue:expedite:0" in done.intrigue_discard
    else:
        done = _take(opened, "recall_intrigue_freighter")
        assert done.players[0].freighter_space == 0
        _rows(done)


def test_expedite_cannot_pay_without_spice() -> None:
    """ "1 spice -> Freighter" requires the spice cost [FAQ p. 2]."""
    state = _start("expedite", resources=Resources())
    assert _options(state, "expedite") == set()


def test_expedite_recall_takes_the_shipping_reward() -> None:
    """ "1 spice -> Freighter": recalling space 1 pays 2 spice [Ix p. 5]."""
    state = _start("expedite", resources=Resources(spice=1), freighter_space=1)
    state = _take(_play(state, "expedite"), "recall_intrigue_freighter")
    state = _take(state, "resolve_shipping_reward", effect="spice")
    assert state.players[0].resources.spice == 2
    assert state.players[0].freighter_space == 0


def test_expedite_can_decline_the_freighter_after_paying() -> None:
    """ "1 spice -> Freighter": the icon says "may" [Rise of Ix p. 5]."""
    state = _start("expedite", resources=Resources(spice=1))
    done = _take(_play(state, "expedite"), "decline_intrigue_freighter")
    assert done.players[0].freighter_space == 0
    assert done.players[0].resources.spice == 0
    assert "intrigue:expedite:0" in done.intrigue_discard


# Finesse ------------------------------------------------------------------


def test_finesse_plot_loses_then_gains_influence() -> None:
    """ "Lose 1 Influence -> gain 1 Influence" -OR- "2 swords" [Steam UI]."""
    state = _start("finesse", influence=Influence(emperor=1))
    assert _options(state, "finesse") == {0}
    state = _play(state, "finesse")
    assert {dict(row.arguments)["faction"] for row in _rows(state)} == {"emperor"}
    state = _take(state, "choose_intrigue_faction", faction="emperor")
    assert state.players[0].influence.emperor == 0
    assert {dict(row.arguments)["faction"] for row in _rows(state)} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    done = _take(state, "choose_intrigue_faction", faction="fremen")
    assert done.players[0].influence.fremen == 1
    assert done.players[0].combat_strength == 0
    assert "intrigue:finesse:0" in done.intrigue_discard


def test_finesse_plot_requires_influence_to_lose() -> None:
    """ "Lose 1 Influence -> gain 1 Influence" needs an Influence to lose."""
    assert _options(_start("finesse", influence=Influence()), "finesse") == set()


def test_finesse_can_regain_the_same_faction_even_with_every_track_full() -> None:
    """ "Lose 1 Influence -> gain 1 Influence": same Faction [FAQ p. 4]."""
    state = _start(
        "finesse",
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    )
    state = _take(_play(state, "finesse"), "choose_intrigue_faction", faction="emperor")
    assert state.players[0].influence.emperor == 5
    assert {dict(row.arguments)["faction"] for row in _rows(state)} == {"emperor"}
    done = _take(state, "choose_intrigue_faction", faction="emperor")
    assert done.players[0].influence.emperor == 6


def test_finesse_regaining_four_repeats_the_faction_bonus() -> None:
    """ "Lose 1 Influence -> gain 1 Influence": regain 4's bonus [DI p. 7]."""
    state = _start(
        "finesse", influence=Influence(spacing_guild=4), resources=Resources()
    )
    state = _take(
        _play(state, "finesse"), "choose_intrigue_faction", faction="spacing_guild"
    )
    done = _take(state, "choose_intrigue_faction", faction="spacing_guild")
    assert done.players[0].influence.spacing_guild == 4
    assert done.players[0].resources.solari == 3


@pytest.mark.parametrize("troops,dreadnoughts", [(1, 0), (0, 1), (0, 0)])
def test_finesse_combat_uses_only_the_swords(troops: int, dreadnoughts: int) -> None:
    """ "2 swords" is Finesse's Combat half; Ix dreadnoughts qualify [Ix p. 6]."""
    state = _start(
        "finesse",
        influence=Influence(),
        troops_conflict=troops,
        dreadnoughts_conflict=dreadnoughts,
        combat_strength=2 * troops + 3 * dreadnoughts,
    )
    state = _seat(state, 1, troops_conflict=1, combat_strength=2)
    state = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    state = begin_combat_intrigue(state).state
    if troops or dreadnoughts:
        assert _options(state, "finesse") == {1}
        before = state.players[0].combat_strength
        done = _play(state, "finesse", 1)
        assert done.players[0].combat_strength == before + 2
        assert done.players[0].influence == Influence()
        assert "intrigue:finesse:0" in done.intrigue_discard
    else:
        assert _options(state, "finesse") == set()


# Secret Forces ------------------------------------------------------------


@pytest.mark.parametrize("supply,expected", [(5, 2), (1, 1), (0, 0)])
def test_secret_forces_recruits_with_a_council_seat(supply: int, expected: int) -> None:
    """ "If you have a seat on the High Council:" recruit 2 troops [Steam UI]."""
    state = _start(
        "secret_forces", high_council=True, troops_supply=supply, troops_garrison=0
    )
    # No cost: even an empty supply may fizzle (OQ-113 (C)).
    assert _options(state, "secret_forces") == {0}
    done = _play(state, "secret_forces")
    assert done.players[0].troops_garrison == expected
    assert done.players[0].troops_supply == supply - expected
    assert "intrigue:secret_forces:0" in done.intrigue_discard


def test_secret_forces_requires_its_owners_council_seat() -> None:
    """ "If you have a seat on the High Council:" is mandatory [FAQ p. 2]."""
    state = _start("secret_forces", high_council=False)
    state = _seat(state, 1, high_council=True)
    assert _options(state, "secret_forces") == set()


# Strongarm ----------------------------------------------------------------


@pytest.mark.parametrize(
    "space,faction",
    [
        ("wealth", "emperor"),
        ("foldspace", "spacing_guild"),
        ("secrets", "bene_gesserit"),
        ("stillsuits", "fremen"),
    ],
)
@pytest.mark.parametrize("zone", ["garrison", "conflict"])
def test_strongarm_loses_a_troop_for_the_faction_visited_this_turn(
    space: str, faction: str, zone: str
) -> None:
    """ "Lose a troop" -> "Gain one Influence with a Faction whose board
    space you sent an Agent to this turn." [Steam app English text]."""
    state = _start(
        "strongarm",
        troops_garrison=int(zone == "garrison"),
        troops_conflict=int(zone == "conflict"),
        troops_supply=11,
    )
    state = _visit(state, space)
    before = getattr(state.players[0].influence, faction)
    supply = state.players[0].troops_supply
    assert _options(state, "strongarm") == {0}
    opened = _play(state, "strongarm")
    assert {dict(row.arguments)["zone"] for row in _rows(opened)} == {zone}
    done = _take(opened, "lose_intrigue_troop", zone=zone)
    assert getattr(done.players[0].influence, faction) == before + 1
    assert done.players[0].troops_supply == supply + 1
    assert getattr(done.players[0], f"troops_{zone}") == 0
    assert "intrigue:strongarm:0" in done.intrigue_discard


def test_strongarm_requires_a_placement_this_turn() -> None:
    """ "...whose board space you sent an Agent to this turn" excludes old Agents."""
    state = _start("strongarm", troops_garrison=1, agent_locations=("wealth",))
    assert _options(state, "strongarm") == set()


def test_strongarm_cannot_use_a_non_faction_placement() -> None:
    """ "Gain one Influence with a Faction whose board space..." needs a Faction."""
    state = _visit(
        _start("strongarm", troops_garrison=1), "smuggling", "dune_the_desert_planet"
    )
    assert _options(state, "strongarm") == set()


def test_strongarm_requires_a_troop_and_cannot_lose_a_dreadnought() -> None:
    """ "Lose a troop" cannot lose a dreadnought [Rise of Ix p. 6]."""
    state = _visit(
        _start(
            "strongarm", troops_garrison=0, troops_conflict=0, dreadnoughts_garrison=1
        ),
        "wealth",
    )
    assert _options(state, "strongarm") == set()


def test_strongarm_cannot_pay_when_the_visited_track_is_full() -> None:
    """ "Lose a troop" -> "Gain one Influence..." needs a live reward (OQ-071)."""
    state = _visit(
        _start("strongarm", troops_garrison=1, influence=Influence(emperor=6)), "wealth"
    )
    assert _options(state, "strongarm") == set()


@pytest.mark.parametrize("card", ["expedite", "finesse", "secret_forces", "strongarm"])
def test_completed_cards_join_the_original_ix_deck(card: str) -> None:
    """ "Expedite / Finesse / Secret Forces / Strongarm" [Steam English titles]."""
    entry = intrigue_card_for_instance(f"intrigue:{card}:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert f"intrigue:{card}:0" in content_for(CONFIG).intrigue_deck_instance_ids


@pytest.mark.parametrize("card", ["expedite", "finesse", "secret_forces"])
def test_plot_halves_are_playable_in_the_reveal_turn(card: str) -> None:
    """ "1 spice -> Freighter" / "Lose 1 Influence -> gain 1 Influence" /
    "If you have a seat on the High Council:" recruit 2 [Steam UI]."""
    state = _start(
        card,
        resources=Resources(spice=1),
        high_council=True,
        influence=Influence(emperor=1),
    )
    state = _take(state, "reveal_turn")
    assert _options(state, card) == {0}
    _rows(_play(state, card))
