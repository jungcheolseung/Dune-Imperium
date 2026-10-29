"""Ix Intrigue batch 3, through the original + Ix engine and ActionCodec.

Rules: imperium-base.md 5: "Plot Intrigue는 자기 Agent·Reveal turn 안에서
아무 때나 낸다. [DI pp. 7-8]"; rise-of-ix.md 9.3 adopts "Strongarm·Quid Pro
Quo는 Faction 칸에 Agent가 없으면 비용을 못 냄(Message from designer)"; OQ-071
requires a live reward for a paid line, and a gain on a track at the top is
lost (OQ-060). An Agent stays on its space until the Recall ("Recall | ...
Agent recall" [DI p. 13], imperium-base.md 2).
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
from dune_imperium.display.effect_dsl_text import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
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
QUID_PRO_QUO = "intrigue:quid_pro_quo:0"


def _seat(state: GameState, seat: int = 0, **changes: Any) -> GameState:
    players = list(state.players)
    if "agent_locations" in changes:
        changes["agents_available"] = 2 - len(changes["agent_locations"])
    players[seat] = replace(players[seat], **changes)
    return replace(state, players=tuple(players))


def _start(**changes: Any) -> GameState:
    state = ENGINE.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return _seat(state, intrigue_cards=(QUID_PRO_QUO,), **changes)


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


def _playable(state: GameState) -> bool:
    return any(
        row.action_id == "play_intrigue"
        and dict(row.arguments)["card_id"] == QUID_PRO_QUO
        for row in _rows(state)
    )


def _play(state: GameState) -> GameState:
    return _take(state, "play_intrigue", card_id=QUID_PRO_QUO, option=0)


def _visit(state: GameState, space: str, card: str = "diplomacy") -> GameState:
    card_id = f"player:0:starter:{card}:0"
    state = _seat(
        state,
        hand=(card_id,),
        deck=tuple(held for held in state.players[0].deck if held != card_id),
    )
    (placement,) = [
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["space_id"] == space
    ]
    return apply_placement(ENGINE, state, placement).state


def _influence(state: GameState) -> dict[str, int]:
    influence = state.players[0].influence
    return {
        faction: getattr(influence, faction)
        for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
    }


# Quid Pro Quo -----------------------------------------------------------------


def test_quid_pro_quo_joins_the_original_ix_deck_with_its_card_text() -> None:
    """ "Quid Pro Quo" [Steam English title]; [2 spice] -> "Gain one
    Influence with each Faction that has at least one of your Agents on its
    board spaces." [Steam app text]."""
    entry = intrigue_card_for_instance(QUID_PRO_QUO)
    assert entry.play_data_complete
    assert entry.copies == 1
    assert QUID_PRO_QUO in content_for(CONFIG).intrigue_deck_instance_ids
    assert (
        QUID_PRO_QUO
        not in content_for(replace(CONFIG, rise_of_ix=False)).intrigue_deck_instance_ids
    )
    assert intrigue_card_text(entry) == [
        "Plot — Pay 2 spice → Gain 1 Influence with each Faction that has at "
        "least one of your Agents on its board spaces"
    ]
    assert intrigue_card_text_ko(entry) == [
        "음모 — {spice:2} 지불 {arrow_right} 그 팩션의 게임판 장소에 당신의 "
        "{agent}가 하나 이상 있는 각 팩션에서 {influence_any:1}씩 얻음"
    ]


@pytest.mark.parametrize(
    ("locations", "gained"),
    [
        (("wealth",), {"emperor"}),
        (("foldspace",), {"spacing_guild"}),
        (("secrets",), {"bene_gesserit"}),
        (("stillsuits",), {"fremen"}),
        (("wealth", "secrets"), {"emperor", "bene_gesserit"}),
        (("arrakeen", "stillsuits"), {"fremen"}),
    ],
)
def test_quid_pro_quo_pays_two_spice_for_each_faction_with_an_agent(
    locations: tuple[str, ...], gained: set[str]
) -> None:
    """[2 spice] -> "Gain one Influence with each Faction that has at least
    one of your Agents on its board spaces." Agents sent on earlier turns
    of the round still stand there [DI p. 13]."""
    state = _start(resources=Resources(spice=3), agent_locations=locations)
    before = _influence(state)
    assert _playable(state)
    done = _play(state)
    after = _influence(done)
    assert {faction for faction in after if after[faction] != before[faction]} == (
        gained
    )
    assert all(after[faction] == before[faction] + 1 for faction in gained)
    assert done.players[0].resources.spice == 1
    assert QUID_PRO_QUO in done.intrigue_discard


def test_quid_pro_quo_gains_once_per_faction_however_many_agents() -> None:
    """ "...each Faction that has **at least one** of your Agents on its
    board spaces": two Agents on Emperor spaces gain one Emperor Influence."""
    state = _start(resources=Resources(spice=2), agent_locations=("wealth", "conspire"))
    before = _influence(state)
    done = _play(state)
    assert _influence(done) == {**before, "emperor": before["emperor"] + 1}


@pytest.mark.parametrize("locations", [(), ("arrakeen",), ("arrakeen", "carthag")])
def test_quid_pro_quo_needs_an_agent_on_a_faction_space(
    locations: tuple[str, ...],
) -> None:
    """ "Strongarm·Quid Pro Quo는 Faction 칸에 Agent가 없으면 비용을 못 냄"
    (rise-of-ix.md 9.3, Message from designer)."""
    state = _start(resources=Resources(spice=2), agent_locations=locations)
    assert not _playable(state)


def test_quid_pro_quo_ignores_an_opponents_agent() -> None:
    """ "...at least one of **your** Agents on its board spaces"."""
    state = _start(resources=Resources(spice=2))
    state = _seat(state, 1, agent_locations=("wealth",))
    assert not _playable(state)


def test_quid_pro_quo_needs_two_spice() -> None:
    """[2 spice] -> ...: "To play an Intrigue card, you must meet its
    conditions and pay its costs." [FAQ p. 2]."""
    state = _start(resources=Resources(spice=1), agent_locations=("wealth",))
    assert not _playable(state)


def test_quid_pro_quo_needs_a_faction_that_can_still_rise() -> None:
    """OQ-071: a cost that buys nothing is not offered; a gain on a track at
    the top is lost (OQ-060). One Faction below the top keeps it live, and
    only that Faction rises."""
    full = Influence(emperor=6, bene_gesserit=6)
    state = _start(
        resources=Resources(spice=2), influence=full, agent_locations=("wealth",)
    )
    assert not _playable(state)
    state = _seat(state, agent_locations=("wealth", "secrets"))
    assert not _playable(state)
    state = _seat(
        state,
        influence=Influence(emperor=6, bene_gesserit=2),
        agent_locations=(
            "wealth",
            "secrets",
        ),
    )
    done = _play(state)
    assert done.players[0].influence == Influence(emperor=6, bene_gesserit=3)


def test_quid_pro_quo_counts_the_agent_sent_this_turn() -> None:
    """[2 spice] -> "Gain one Influence with each Faction that has at least
    one of your Agents on its board spaces"; a Plot is played any time in the
    seat's own Agent turn [DI pp. 7-8]."""
    state = _visit(_start(resources=Resources(spice=2)), "foldspace")
    before = _influence(state)
    done = _play(state)
    assert _influence(done)["spacing_guild"] == before["spacing_guild"] + 1
    assert done.players[0].resources.spice == 0


def test_quid_pro_quo_plays_in_the_reveal_turn() -> None:
    """ "Plot Intrigue는 자기 Agent·Reveal turn 안에서 아무 때나 낸다"
    [DI pp. 7-8]; the round's Agents are still on their spaces."""
    state = _start(resources=Resources(spice=2), agent_locations=("stillsuits",))
    state = _take(state, "reveal_turn")
    before = _influence(state)
    assert _playable(state)
    done = _play(state)
    assert _influence(done) == {**before, "fremen": before["fremen"] + 1}
