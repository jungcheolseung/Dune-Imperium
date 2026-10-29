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


@pytest.mark.parametrize("card", ["expedite"])
def test_completed_cards_join_the_original_ix_deck(card: str) -> None:
    """ "Expedite / Finesse / Secret Forces / Strongarm" [Steam English titles]."""
    entry = intrigue_card_for_instance(f"intrigue:{card}:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert f"intrigue:{card}:0" in content_for(CONFIG).intrigue_deck_instance_ids


@pytest.mark.parametrize("card", ["expedite"])
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
