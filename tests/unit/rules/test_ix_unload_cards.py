"""Rise of Ix's Unload cards transcribed in stage P4d (one section per card).

Rules: docs/rules/rise-of-ix.md 7 "Unload" [Rise of Ix p. 7]: "Unload 표시가
있는 Reveal box는 Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시) 말고도,
그 카드를 **discard할 때**와 **trash할 때** 얻는다. 남의 효과로 버려져도 된다";
"discard"는 손의 카드이고 Clean Up은 discard가 아니다 [FAQ p. 2]; the designer
ruling "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
오른쪽으로 간다"; OQ-120 (a revealed Unload card trashed in the same Reveal
turn gives its box again) and OQ-022 (no effect from an already-trashed card).
The mechanism itself is tested in ``test_ix_unload.py``; these tests drive
each card's own data through ``UprisingRulesEngine`` in an original game with
Rise of Ix.
"""

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    DeployFromSupply,
    GainInfluence,
    GainResources,
    HasAlliance,
)
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS_BY_ID,
    imperium_card_for_instance,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.reveal_abilities import REVEAL_GAIN_ABILITIES
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, canonical_state_hash
from dune_imperium.display.unavailable import unavailable_choices
from dune_imperium.rules import UprisingRulesEngine, unload
from dune_imperium.rules.agent_box_abilities import AgentPaymentBlock
from dune_imperium.rules.agent_effects import agent_card_payment_block
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.frames import FrameKind, is_unload_hold
from dune_imperium.rules.pauses import (
    ROUND_START,
    pause_is_pending,
    pending_pause_point,
)
from dune_imperium.server.persistence import deserialize_step, serialize_step
from dune_imperium.simulation.invariants import check_observation_privacy

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(IX)
_CODECS: dict[RulesetConfig, ActionCodec] = {IX: CODEC}
TRUTHSAYER = "imperium:truthsayer:0"
JAMIS = "imperium:jamis:0"
MOHIAM = "imperium:reverend_mother_mohiam:0"
INITIATE = "imperium:bene_gesserit_initiate:0"
CULL = "intrigue:cull:0"
UNLOAD_ROW = "resolve_unload_icon"


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    """The seat's legal rows, each round-tripped through the action codec of
    the game's options."""

    if state.config not in _CODECS:
        _CODECS[state.config] = ActionCodec(state.config)
    codec = _CODECS[state.config]
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert codec.decode(codec.encode(row), seat) == row
    return rows


def _give(state: GameState, seat: int, **zones: tuple[str, ...]) -> GameState:
    """Put the named cards in ``seat``'s zones, taking them out of the
    Imperium deck and Row and of every seat's zones first (seeded decks)."""

    named = {card for cards in zones.values() for card in cards}
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _seat(state: GameState, seat: int, **fields: object) -> GameState:
    owner = replace(state.players[seat], **fields)  # type: ignore[arg-type]
    return replace(
        state,
        players=(*state.players[:seat], owner, *state.players[seat + 1 :]),
    )


def _with_cull(state: GameState, seat: int = 0, solari: int = 1) -> GameState:
    """``seat`` holds Cull ("[1 Solari] -> [trash a card]") and ``solari``."""

    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != CULL)
    )
    owner = state.players[seat]
    return _seat(
        state,
        seat,
        intrigue_cards=(CULL,),
        resources=replace(owner.resources, solari=solari),
    )


def _start(seed: int = 3, config: RulesetConfig = IX) -> GameState:
    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events))


def _offered(state: GameState, action_id: str, seat: int = 0) -> bool:
    _rows(state, seat)
    return any(row.action_id == action_id for row in ENGINE.whole_actions(state, seat))


def _arguments(
    state: GameState, action_id: str, seat: int = 0
) -> set[tuple[tuple[str, ActionValue], ...]]:
    _rows(state, seat)
    return {
        row.arguments
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
    }


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


def _clean_up_round(state: GameState) -> tuple[GameState, list[GameEvent]]:
    """Play the round out at random up to the next Round Start's pause, after
    Clean Up and before its reshuffles (``rules.pauses``); return that state
    and every ``card_unloaded`` event on the way."""

    chance = ChanceResolver(seed=3)
    rng = random.Random(3)
    unloaded: list[GameEvent] = []
    while not (pause_is_pending(state) and pending_pause_point(state) == ROUND_START):
        assert state.phase is not GamePhase.FINISHED
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            result = ENGINE.apply(state, chance.resolve(decision))
        else:
            assert isinstance(decision, PlayerDecision)
            result = ENGINE.apply(
                state, rng.choice(ENGINE.legal_actions(state, decision.owner))
            )
        unloaded.extend(e for e in result.events if e.kind == "card_unloaded")
        state = result.state
    return state, unloaded


def _mohiam_asks_seat_one(state: GameState, *hand: str) -> GameState:
    """Seat 0 plays Reverend Mother Mohiam with another Bene Gesserit card in
    play ("each opponent discards two cards", OQ-118); seat 1 holds ``hand``
    and is the first asked [FAQ p. 3]."""

    state = _give(state, 0, hand=(MOHIAM,), in_play=(INITIATE,))
    state = _give(state, 1, hand=hand)
    state = _do(state, "choose_agent_card", card_id=MOHIAM).state
    state = _do(state, "place_agent", space_id="secrets").state
    state = _do(state, "resolve_agent_card_effect").state
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD
    return state


# --- Esmar Tuek ---------------------------------------------------------------

ESMAR = "imperium:esmar_tuek_card:0"
_ESMAR_BOX = (
    PersonalCardAgentEffect.MAY_PAY_ONE_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_DRAW_ONE
)


def test_esmar_tuek_play_data_matches_the_app() -> None:
    """App table: cost 5, 1 copy, Spacing Guild, the City and Spice Trade
    icons, Reveal 2 spice and 2 Solari; screen pieces: Agent "[1 spice] ->
    [Spacing Guild Influence] [draw 1 card]", Reveal "[Unload] [2 spice] [2
    Solari]". The card is not Bloodlines' Leader Esmar Tuek (plan 17.2)."""
    entry = IMPERIUM_CARDS_BY_ID["esmar_tuek_card"]
    assert "esmar_tuek" not in IMPERIUM_CARDS_BY_ID
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (1, 5)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is _ESMAR_BOX
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    (line,) = REVEAL_GAIN_ABILITIES["esmar_tuek_card"].sections
    assert line.rewards == (GainResources(solari=2, spice=2),)
    assert line.condition is None
    assert unload.unload_icons(ESMAR) == (("solari", 2), ("spice", 2))
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert (ESMAR in deck) == config.rise_of_ix


def _esmar_placed(state: GameState, space_id: str = "arrakeen") -> GameState:
    state = _give(state, 0, hand=(ESMAR,))
    state = _do(state, "choose_agent_card", card_id=ESMAR).state
    return _do(state, "place_agent", space_id=space_id).state


def test_esmar_tuek_pays_one_spice_for_guild_influence_and_a_card() -> None:
    """ "[1 spice] -> [Spacing Guild Influence] [draw 1 card]": the arrow is
    optional [DI p. 9] [FAQ p. 3]; once the spice is paid, the Influence and
    the hidden draw are two steps in the owner's order (OQ-027, OQ-106,
    OQ-148), and the turn cannot end while either waits."""
    state = _esmar_placed(_start())
    before = state.players[0]
    assert before.resources.spice >= 1
    assert _offered(state, "pay_agent_card_spice")
    paid = _do(state, "pay_agent_card_spice").state
    assert paid.players[0].resources.spice == before.resources.spice - 1
    assert paid.players[0].influence == before.influence
    assert _arguments(paid, "choose_agent_card_influence") == {
        (("faction", "spacing_guild"),)
    }
    assert (("effect", "cards"),) in _arguments(paid, "resolve_agent_card_effect")
    assert not _offered(paid, "finish_agent_turn")
    drawn = _do(paid, "resolve_agent_card_effect", effect="cards").state
    assert len(drawn.players[0].hand) == len(paid.players[0].hand) + 1
    check_observation_privacy(drawn)
    done = _do(drawn, "choose_agent_card_influence", faction="spacing_guild").state
    assert done.players[0].influence.spacing_guild == before.influence.spacing_guild + 1


def test_esmar_tuek_revealed_gives_its_box_as_usual() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7)."""
    state = _give(_start(), 0, hand=(ESMAR,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    owner = revealed.state.players[0]
    gained = _do(revealed.state, "gain_reveal_resources")
    after = gained.state.players[0]
    assert after.resources.solari == owner.resources.solari + 2
    assert after.resources.spice == owner.resources.spice + 2
    assert not _offered(gained.state, UNLOAD_ROW)


def test_esmar_tuek_discarded_as_a_cost_pays_its_box_before_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": "비용 → 효과 줄의 왼쪽(비용)이
    Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (designer
    ruling, rise-of-ix.md 7)."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, ESMAR, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    before = state.players[0]
    result = _do(state, "discard_agent_card", card_id=ESMAR)
    after = result.state.players[0]
    assert ESMAR in after.discard_pile
    assert after.resources.solari == before.resources.solari + 2
    assert after.resources.spice == before.resources.spice + 2
    kinds = _kinds(result.events)
    unload_gain = next(
        index
        for index, event in enumerate(result.events)
        if event.kind == "resources_gained" and ":unload:" in event.event_id
    )
    assert (
        kinds.index("card_discarded")
        < kinds.index("card_unloaded")
        < unload_gain
        < kinds.index("agent_card_effect_resolved")
    )
    assert not _offered(result.state, UNLOAD_ROW)
    check_observation_privacy(result.state)


def test_esmar_tuek_trashed_by_jamis_waits_as_rows_of_the_turn() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card" -- an
    effect in the owner's own turn, so each icon is a row of the turn that
    holds its end until taken, in the owner's order."""
    state = _give(_start(), 0, hand=(JAMIS, ESMAR))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    before = state.players[0].resources
    trashed = _do(state, "trash_agent_card", card_id=ESMAR)
    assert ESMAR in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    state = trashed.state
    assert state.players[0].resources == before
    assert _arguments(state, UNLOAD_ROW) == {
        (("card_id", ESMAR), ("effect", "solari")),
        (("card_id", ESMAR), ("effect", "spice")),
    }
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert not _offered(state, "finish_agent_turn")
    spice = state.players[0].resources.spice
    state = _do(state, UNLOAD_ROW, card_id=ESMAR, effect="spice").state
    assert state.players[0].resources.spice == spice + 2
    assert not _offered(state, "finish_agent_turn")
    solari = state.players[0].resources.solari
    state = _do(state, UNLOAD_ROW, card_id=ESMAR, effect="solari").state
    assert state.players[0].resources.solari == solari + 2
    assert not _offered(state, UNLOAD_ROW)
    assert _offered(state, "finish_agent_turn")


def test_esmar_tuek_discarded_by_an_opponent_unloads_in_its_owners_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): outside its owner's turn the box is a window of the
    owner's, who takes its icons in its own order before the discard goes on."""
    state = _start()
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, ESMAR, other)
    before = state.players[1].resources
    state = _do(state, "discard_opponent_card", seat=1, card_id=ESMAR).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert not _rows(state, 0)
    assert {row.arguments for row in _rows(state, 1)} == {
        (("card_id", ESMAR), ("effect", "solari")),
        (("card_id", ESMAR), ("effect", "spice")),
    }
    state = _do(state, UNLOAD_ROW, seat=1, card_id=ESMAR, effect="spice").state
    assert state.decision_stack[-1].kind is FrameKind.UNLOAD_ICONS
    state = _do(state, UNLOAD_ROW, seat=1, card_id=ESMAR, effect="solari").state
    after = state.players[1].resources
    assert (after.solari, after.spice) == (before.solari + 2, before.spice + 2)
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_esmar_tuek_revealed_then_trashed_gives_its_box_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다";
    Cull: "[1 Solari] -> [trash a card]"."""
    state = _with_cull(_give(_start(), 0, hand=(ESMAR,)))
    state = _do(state, "reveal_turn").state
    before = state.players[0].resources
    state = _do(state, "gain_reveal_resources").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    trashed = _do(state, "trash_intrigue_card", card_id=ESMAR)
    assert ESMAR in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    assert not _offered(trashed.state, "finish_reveal")
    state = _do(trashed.state, UNLOAD_ROW, card_id=ESMAR, effect="spice").state
    state = _do(state, UNLOAD_ROW, card_id=ESMAR, effect="solari").state
    after = state.players[0].resources
    assert after.spice == before.spice + 4
    assert after.solari == before.solari + 4 - 1
    assert _offered(state, "finish_reveal")


def test_esmar_tuek_trashed_before_its_box_cannot_pay_it_with_its_spice() -> None:
    """ "Esmar Tuek를 Cull로 trash해 얻은 spice로 그 Agent box를 낼 수 없다"
    (OQ-022, rise-of-ix.md 7 and 9.3): the Unload comes while the card is
    trashed, and the card's box, not yet resolved, expires with it."""
    state = _esmar_placed(_with_cull(_start()), "arrakeen")
    state = _seat(
        state, 0, resources=replace(state.players[0].resources, spice=0, solari=1)
    )
    assert not _offered(state, "pay_agent_card_spice")
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    trashed = _do(state, "trash_intrigue_card", card_id=ESMAR)
    assert ESMAR in trashed.state.players[0].trashed
    assert "agent_card_effect_expired" in _kinds(trashed.events)
    state = _do(trashed.state, UNLOAD_ROW, card_id=ESMAR, effect="spice").state
    assert state.players[0].resources.spice == 2
    assert not _offered(state, "pay_agent_card_spice")


def test_clean_up_moves_esmar_tuek_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2]; OQ-120)."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(ESMAR,)))
    assert state.phase is GamePhase.ROUND_START
    assert ESMAR in state.players[0].discard_pile
    assert unloaded == []


# --- Guild Accord -------------------------------------------------------------

GUILD_ACCORD = "imperium:guild_accord:0"
SEEK_ALLIES = "player:0:starter:seek_allies:0"
HEIGHLINER = "imperium_heighliner"


def _guild_alliance(state: GameState, seat: int) -> GameState:
    """``seat`` holds the Spacing Guild Alliance (4 Influence, the token)."""

    owner = state.players[seat]
    return _seat(
        state,
        seat,
        influence=replace(owner.influence, spacing_guild=4),
        alliance_faction_ids=("spacing_guild",),
    )


def _spice(state: GameState, seat: int, spice: int) -> GameState:
    owner = state.players[seat]
    return _seat(state, seat, resources=replace(owner.resources, spice=spice))


def _heighliner_rows(state: GameState, card_id: str) -> bool:
    chosen = _do(state, "choose_agent_card", card_id=card_id).state
    return (("space_id", HEIGHLINER),) in _arguments(chosen, "place_agent")


def test_guild_accord_play_data_matches_the_app() -> None:
    """App table: cost 6, 1 copy, Spacing Guild, the Spacing Guild icon (its
    Infiltration icon too), Reveal 1 water. Agent: "It costs [2 spice] less to
    send an Agent to the Heighliner board space with this card." Reveal
    "[Unload] [1 water]; [Spacing Guild] Alliance: [3 spice]"."""
    entry = IMPERIUM_CARDS_BY_ID["guild_accord"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (1, 6)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.SPACING_GUILD,)
    assert entry.agent_effect is None and entry.heighliner_spice_discount == 2
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    water, spice = REVEAL_GAIN_ABILITIES["guild_accord"].sections
    assert water.rewards == (GainResources(water=1),) and water.condition is None
    assert spice.rewards == (GainResources(spice=3),)
    assert spice.condition == HasAlliance(Faction.SPACING_GUILD)
    assert unload.unload_icons(GUILD_ACCORD) == (("water", 1), ("spice", 3))
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert (GUILD_ACCORD in deck) == config.rise_of_ix


def test_guild_accord_sends_an_agent_to_the_heighliner_for_two_spice_less() -> None:
    """ "It costs [2 spice] less to send an Agent to the Heighliner board space
    with this card": the Heighliner's 6 spice [DI p. 17] are 4 with Guild
    Accord, and only with it; no "may", so the cut always applies."""
    state = _spice(_give(_start(), 0, hand=(GUILD_ACCORD, SEEK_ALLIES)), 0, 4)
    assert _heighliner_rows(state, GUILD_ACCORD)
    assert not _heighliner_rows(state, SEEK_ALLIES)
    assert _heighliner_rows(_spice(state, 0, 6), SEEK_ALLIES)
    assert not _heighliner_rows(_spice(state, 0, 3), GUILD_ACCORD)
    state = _do(state, "choose_agent_card", card_id=GUILD_ACCORD).state
    placed = _do(state, "place_agent", space_id=HEIGHLINER).state
    assert placed.players[0].resources.spice == 0
    assert HEIGHLINER in placed.players[0].agent_locations


def test_guild_accord_infiltrates_the_heighliner() -> None:
    """ "Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의 칸에서 상대 Agent ...를
    무시하고 보낼 수 있게 한다" [Rise of Ix p. 7]; Guild Accord's Spacing Guild
    icon is one (app ``InfiltrationIconList``)."""
    state = _spice(_give(_start(), 0, hand=(GUILD_ACCORD,)), 0, 4)
    other = state.players[1]
    state = _seat(
        state,
        1,
        agent_locations=(HEIGHLINER,),
        agents_available=other.agents_available - 1,
    )
    assert _heighliner_rows(state, GUILD_ACCORD)


def test_guild_accord_revealed_gives_its_alliance_line_only_with_the_alliance() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7):
    the water, and the 3 spice with the Spacing Guild Alliance -- one step,
    as every card's resources wait as one gain (stage B3e-1, decision 3)."""
    for alliance in (False, True):
        state = _give(_start(), 0, hand=(GUILD_ACCORD,))
        if alliance:
            state = _guild_alliance(state, 0)
        revealed = _do(state, "reveal_turn")
        assert "card_unloaded" not in _kinds(revealed.events)
        state = revealed.state
        before = state.players[0].resources
        (gain,) = (
            row
            for row in ENGINE.whole_actions(state, 0)
            if row.action_id == "gain_reveal_resources"
        )
        assert dict(gain.arguments)["spice"] == (3 if alliance else 0)
        state = _do(state, "gain_reveal_resources").state
        assert not _offered(state, "gain_reveal_resources")
        after = state.players[0].resources
        assert after.water == before.water + 1
        assert after.spice == before.spice + (3 if alliance else 0)
        assert not _offered(state, UNLOAD_ROW)


def test_guild_accord_discarded_as_a_cost_pays_its_box_before_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": "Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7); the Alliance line is
    judged as the card is discarded."""
    for alliance in (False, True):
        state = _start()
        kept = state.players[0].hand[0]
        state = _give(state, 0, hand=(TRUTHSAYER, GUILD_ACCORD, kept))
        if alliance:
            state = _guild_alliance(state, 0)
        state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
        state = _do(state, "place_agent", space_id="wealth").state
        before = state.players[0].resources
        result = _do(state, "discard_agent_card", card_id=GUILD_ACCORD)
        after = result.state.players[0].resources
        assert after.water == before.water + 1
        assert after.spice == before.spice + (3 if alliance else 0)
        kinds = _kinds(result.events)
        assert kinds.index("card_unloaded") < kinds.index("agent_card_effect_resolved")
        assert not _offered(result.state, UNLOAD_ROW)


def test_guild_accord_trashed_in_its_owners_turn_waits_as_rows() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card". The
    Alliance line is gained only if the Alliance is held as the card is
    trashed; each gained icon waits as a row of the turn."""
    for alliance in (False, True):
        state = _give(_start(), 0, hand=(JAMIS, GUILD_ACCORD))
        if alliance:
            state = _guild_alliance(state, 0)
        state = _do(state, "choose_agent_card", card_id=JAMIS).state
        state = _do(state, "place_agent", space_id="stillsuits").state
        trashed = _do(state, "trash_agent_card", card_id=GUILD_ACCORD)
        assert GUILD_ACCORD in trashed.state.players[0].trashed
        expected = {(("card_id", GUILD_ACCORD), ("effect", "water"))}
        if alliance:
            expected.add((("card_id", GUILD_ACCORD), ("effect", "spice")))
        assert _arguments(trashed.state, UNLOAD_ROW) == expected
        state = trashed.state
        before = state.players[0].resources
        state = _do(state, UNLOAD_ROW, card_id=GUILD_ACCORD, effect="water").state
        if alliance:
            state = _do(state, UNLOAD_ROW, card_id=GUILD_ACCORD, effect="spice").state
        after = state.players[0].resources
        assert after.water == before.water + 1
        assert after.spice == before.spice + (3 if alliance else 0)
        assert not _offered(state, UNLOAD_ROW)


def test_guild_accord_discarded_by_an_opponent_unloads_in_its_owners_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): the owner's window holds the water, and the 3 spice
    only with its own Spacing Guild Alliance."""
    for alliance in (False, True):
        state = _start()
        other = state.players[1].hand[0]
        if alliance:
            state = _guild_alliance(state, 1)
        state = _mohiam_asks_seat_one(state, GUILD_ACCORD, other)
        before = state.players[1].resources
        state = _do(state, "discard_opponent_card", seat=1, card_id=GUILD_ACCORD).state
        top = state.decision_stack[-1]
        assert top.kind is FrameKind.UNLOAD_ICONS
        assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
        effects = {dict(row.arguments)["effect"] for row in _rows(state, 1)}
        assert effects == ({"water", "spice"} if alliance else {"water"})
        for effect in sorted(effects):
            taken = _do(state, UNLOAD_ROW, seat=1, card_id=GUILD_ACCORD, effect=effect)
            state = taken.state
        after = state.players[1].resources
        assert after.water == before.water + 1
        assert after.spice == before.spice + (3 if alliance else 0)
        assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_guild_accord_revealed_then_trashed_gives_its_box_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_guild_alliance(_give(_start(), 0, hand=(GUILD_ACCORD,)), 0))
    state = _do(state, "reveal_turn").state
    before = state.players[0].resources
    while _offered(state, "gain_reveal_resources"):
        state = _do(state, "gain_reveal_resources").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    trashed = _do(state, "trash_intrigue_card", card_id=GUILD_ACCORD)
    assert "card_unloaded" in _kinds(trashed.events)
    assert not _offered(trashed.state, "finish_reveal")
    state = _do(trashed.state, UNLOAD_ROW, card_id=GUILD_ACCORD, effect="water").state
    state = _do(state, UNLOAD_ROW, card_id=GUILD_ACCORD, effect="spice").state
    after = state.players[0].resources
    assert (after.water, after.spice) == (before.water + 2, before.spice + 6)
    assert _offered(state, "finish_reveal")


def test_clean_up_moves_guild_accord_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(GUILD_ACCORD,)))
    assert state.phase is GamePhase.ROUND_START
    assert GUILD_ACCORD in state.players[0].discard_pile
    assert unloaded == []


# --- In The Shadows -----------------------------------------------------------

SHADOWS = "imperium:in_the_shadows:0"
SHADOWS_TWO = "imperium:in_the_shadows:1"
_BOX = PersonalCardAgentEffect
_SHADOWS_BOX = _BOX.MAY_DISCARD_FOR_CHOSEN_INFLUENCE_IF_BENE_GESSERIT_INFLUENCE_TWO
_BG = "influence_bene_gesserit"


def _influence(state: GameState, seat: int, **tracks: int) -> GameState:
    owner = state.players[seat]
    return _seat(state, seat, influence=replace(owner.influence, **tracks))


def _shadows_placed(state: GameState, *hand: str) -> GameState:
    state = _give(state, 0, hand=(SHADOWS, *hand))
    state = _do(state, "choose_agent_card", card_id=SHADOWS).state
    return _do(state, "place_agent", space_id="arrakeen").state


def test_in_the_shadows_play_data_matches_the_app() -> None:
    """App table: cost 2, 2 copies, Bene Gesserit, the Landsraad and City
    icons; screen pieces: Agent "[Bene Gesserit] 2 Influence: [Discard] ->
    Choose one: [Emperor] [Spacing Guild] [Fremen] Influence", Reveal
    "[Unload] [Bene Gesserit Influence]"."""
    entry = IMPERIUM_CARDS_BY_ID["in_the_shadows"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (2, 2)
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert entry.agent_effect is _SHADOWS_BOX
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    (line,) = REVEAL_GAIN_ABILITIES["in_the_shadows"].sections
    assert line.rewards == (GainInfluence(factions=(Faction.BENE_GESSERIT,)),)
    assert unload.unload_icons(SHADOWS) == ((_BG, 1),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert ({SHADOWS, SHADOWS_TWO} <= set(deck)) == config.rise_of_ix


def test_in_the_shadows_discards_for_a_chosen_influence_at_two_bene_gesserit() -> None:
    """ "[Bene Gesserit] 2 Influence: [Discard] -> Choose one: ..." -- the
    threshold over the whole arrow (Spice Trader's), the Discard optional
    [Rise of Ix p. 7], and the Influence with one of the three named
    Factions, never one at the top (OQ-060)."""
    state = _start()
    kept = state.players[0].hand[0]
    below = _shadows_placed(_influence(state, 0, bene_gesserit=1), kept)
    assert not _offered(below, "discard_agent_card")
    state = _influence(state, 0, bene_gesserit=2, emperor=6)
    placed = _shadows_placed(state, kept)
    discarded = _do(placed, "discard_agent_card", card_id=kept).state
    assert kept in discarded.players[0].discard_pile
    assert _arguments(discarded, "choose_agent_card_influence") == {
        (("faction", "spacing_guild"),),
        (("faction", "fremen"),),
    }
    assert not _offered(discarded, "finish_agent_turn")
    done = _do(discarded, "choose_agent_card_influence", faction="fremen").state
    assert done.players[0].influence.fremen == placed.players[0].influence.fremen + 1
    assert done.players[0].influence.bene_gesserit == 2


def test_in_the_shadows_arrow_is_not_offered_with_its_three_factions_at_the_top() -> (
    None
):
    """ "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다 ... 버릴 카드에
    Unload가 있어도 같다" (docs/rules/rise-of-ix.md 15, OQ-071): the Emperor,
    Spacing Guild and Fremen at 6, the discard buys nothing, also with the
    other In The Shadows (an Unload card) in hand."""
    state = _influence(
        _start(), 0, bene_gesserit=2, emperor=6, spacing_guild=6, fremen=6
    )
    placed = _shadows_placed(state, SHADOWS_TWO)
    assert not _offered(placed, "discard_agent_card")
    assert (
        agent_card_payment_block(placed, 0, _SHADOWS_BOX)
        is AgentPaymentBlock.NO_FACTION_TO_RAISE
    )
    lower = _influence(placed, 0, fremen=5)
    assert _offered(lower, "discard_agent_card")
    assert agent_card_payment_block(lower, 0, _SHADOWS_BOX) is None


def test_in_the_shadows_discarded_as_its_twin_s_cost_unloads_before_the_choice() -> (
    None
):
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다" (designer ruling, rise-of-ix.md 7): the discarded copy's
    Bene Gesserit Influence comes inside the payment, before the chosen
    Faction's."""
    state = _influence(_start(), 0, bene_gesserit=2)
    placed = _shadows_placed(state, SHADOWS_TWO)
    result = _do(placed, "discard_agent_card", card_id=SHADOWS_TWO)
    after = result.state.players[0]
    assert after.influence.bene_gesserit == 3
    kinds = _kinds(result.events)
    assert kinds.index("card_discarded") < kinds.index("card_unloaded")
    assert kinds.index("card_unloaded") < kinds.index("influence_gained")
    assert not _offered(result.state, UNLOAD_ROW)
    assert _offered(result.state, "choose_agent_card_influence")
    check_observation_privacy(result.state)


def test_in_the_shadows_revealed_gives_its_influence_as_usual() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7)."""
    state = _give(_start(), 0, hand=(SHADOWS,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    before = revealed.state.players[0].influence.bene_gesserit
    gained = _do(revealed.state, "gain_reveal_faction_influence").state
    assert gained.players[0].influence.bene_gesserit == before + 1
    assert not _offered(gained, UNLOAD_ROW)


def test_in_the_shadows_trashed_by_jamis_waits_as_a_row() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card"."""
    state = _give(_start(), 0, hand=(JAMIS, SHADOWS))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    before = state.players[0].influence.bene_gesserit
    state = _do(state, "trash_agent_card", card_id=SHADOWS).state
    assert state.players[0].influence.bene_gesserit == before
    assert _arguments(state, UNLOAD_ROW) == {(("card_id", SHADOWS), ("effect", _BG))}
    taken = _do(state, UNLOAD_ROW, card_id=SHADOWS, effect=_BG)
    assert taken.state.players[0].influence.bene_gesserit == before + 1
    assert "influence_gained" in _kinds(taken.events)
    assert not _offered(taken.state, UNLOAD_ROW)


def test_in_the_shadows_discarded_by_an_opponent_unloads_in_its_owners_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): seat 1 gains its own Bene Gesserit Influence in its
    window."""
    state = _start()
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, SHADOWS, other)
    before = state.players[1].influence.bene_gesserit
    state = _do(state, "discard_opponent_card", seat=1, card_id=SHADOWS).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    state = _do(state, UNLOAD_ROW, seat=1, card_id=SHADOWS, effect=_BG).state
    assert state.players[1].influence.bene_gesserit == before + 1
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_in_the_shadows_revealed_then_trashed_gives_its_influence_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_give(_start(), 0, hand=(SHADOWS,)))
    state = _do(state, "reveal_turn").state
    before = state.players[0].influence.bene_gesserit
    state = _do(state, "gain_reveal_faction_influence").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=SHADOWS).state
    assert not _offered(state, "finish_reveal")
    state = _do(state, UNLOAD_ROW, card_id=SHADOWS, effect=_BG).state
    assert state.players[0].influence.bene_gesserit == before + 2
    assert _offered(state, "finish_reveal")


def test_clean_up_moves_in_the_shadows_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(SHADOWS,)))
    assert state.phase is GamePhase.ROUND_START
    assert SHADOWS in state.players[0].discard_pile
    assert unloaded == []


# --- Treachery ----------------------------------------------------------------

TREACHERY = "imperium:treachery:0"
TREACHERY_TWO = "imperium:treachery:1"
_DEPLOY = "deploy"


def test_treachery_play_data_matches_the_app() -> None:
    """App table: cost 6, 2 copies, no Faction, the four Faction icons;
    Agent "Gain two Influence instead of one. Trash this card." (Power Play's
    box), Reveal "[Unload] [troop] [troop] Deploy these troops to the
    Conflict."."""
    entry = IMPERIUM_CARDS_BY_ID["treachery"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (2, 6)
    assert entry.factions == ()
    assert entry.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert entry.agent_effect is IMPERIUM_CARDS_BY_ID["power_play"].agent_effect
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    (line,) = REVEAL_GAIN_ABILITIES["treachery"].sections
    assert line.rewards == (DeployFromSupply(2),) and line.condition is None
    assert unload.unload_icons(TREACHERY) == ((_DEPLOY, 2),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert ({TREACHERY, TREACHERY_TWO} <= set(deck)) == config.rise_of_ix


def test_treachery_revealed_deploys_two_troops_from_the_supply() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7):
    "Deploy these troops to the Conflict" moves two troops from the supply,
    the owner's own step as a recruit is (OQ-045), counted in this Reveal's
    strength; the Reveal cannot end before it."""
    state = _give(_start(), 0, hand=(TREACHERY,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    state = revealed.state
    assert not _offered(state, "finish_reveal")
    before = state.players[0]
    deployed = _do(state, "deploy_reveal_supply_troops")
    after = deployed.state.players[0]
    assert after.troops_supply == before.troops_supply - 2
    assert after.troops_conflict == before.troops_conflict + 2
    assert after.troops_garrison == before.troops_garrison
    assert after.combat_strength == before.combat_strength + 4
    assert "troops_deployed" in _kinds(deployed.events)
    assert _offered(deployed.state, "finish_reveal")
    assert not _offered(deployed.state, UNLOAD_ROW)


def test_treachery_revealed_with_one_troop_in_the_supply_deploys_it() -> None:
    """ "my supply may be empty" [FAQ p. 2]: one troop deploys and the other
    is recorded as Double Cross's shortfall is (OQ-042 (2), "원판·Ix의 Double
    Cross·Treachery(supply에서 Conflict로 배치)도 같은 기록을 쓴다")."""
    state = _give(_start(), 0, hand=(TREACHERY,))
    owner = state.players[0]
    state = _seat(
        state,
        0,
        troops_supply=1,
        troops_garrison=owner.troops_garrison + owner.troops_supply - 1,
    )
    state = _do(state, "reveal_turn").state
    after = _do(state, "deploy_reveal_supply_troops").state.players[0]
    assert (after.troops_supply, after.troops_conflict) == (0, 1)
    assert after.ungained_conflict_troops == 1


def test_treachery_trashing_itself_on_its_agent_turn_deploys_its_troops() -> None:
    """Power Play's box: "Gain two Influence instead of one. Trash this
    card." -- and "Treachery는 자기를 trash한다고 적혀 있어 예외" (rise-of-ix.md 7,
    [Rise of Ix p. 10]): trashed by its own text, its Unload comes as a row of
    its owner's turn, two troops to the Conflict by the card's text."""
    state = _give(_start(), 0, hand=(TREACHERY,))
    state = _do(state, "choose_agent_card", card_id=TREACHERY).state
    state = _do(state, "place_agent", space_id="wealth").state
    before = state.players[0]
    boxed = _do(state, "resolve_agent_card_effect")
    assert TREACHERY in boxed.state.players[0].trashed
    assert "card_unloaded" in _kinds(boxed.events)
    state = boxed.state
    assert state.players[0].influence.emperor == before.influence.emperor + 2
    assert _arguments(state, UNLOAD_ROW) == {
        (("card_id", TREACHERY), ("effect", _DEPLOY))
    }
    state = _do(state, "resolve_board_effect", effect="resources").state
    assert not _offered(state, "finish_agent_turn")
    state = _do(state, UNLOAD_ROW, card_id=TREACHERY, effect=_DEPLOY).state
    after = state.players[0]
    assert after.troops_conflict == before.troops_conflict + 2
    assert after.troops_supply == before.troops_supply - 2
    assert _offered(state, "finish_agent_turn")


def test_treachery_discarded_as_a_cost_deploys_before_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": "Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7)."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, TREACHERY, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    before = state.players[0]
    result = _do(state, "discard_agent_card", card_id=TREACHERY)
    after = result.state.players[0]
    assert after.troops_conflict == before.troops_conflict + 2
    kinds = _kinds(result.events)
    assert (
        kinds.index("card_unloaded")
        < kinds.index("troops_deployed")
        < kinds.index("agent_card_effect_resolved")
    )
    assert not _offered(result.state, UNLOAD_ROW)
    check_observation_privacy(result.state)


def test_treachery_discarded_by_an_opponent_deploys_its_owners_troops() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): seat 1's window, seat 1's troops, in another seat's
    turn -- the card's "Deploy these troops" needs no Combat space."""
    state = _start()
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, TREACHERY, other)
    before = state.players[1]
    state = _do(state, "discard_opponent_card", seat=1, card_id=TREACHERY).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    state = _do(state, UNLOAD_ROW, seat=1, card_id=TREACHERY, effect=_DEPLOY).state
    after = state.players[1]
    assert after.troops_conflict == before.troops_conflict + 2
    assert after.troops_supply == before.troops_supply - 2
    assert state.players[0].troops_conflict == 0
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_treachery_revealed_then_trashed_deploys_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_give(_start(), 0, hand=(TREACHERY,)))
    state = _do(state, "reveal_turn").state
    before = state.players[0]
    state = _do(state, "deploy_reveal_supply_troops").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=TREACHERY).state
    assert not _offered(state, "finish_reveal")
    state = _do(state, UNLOAD_ROW, card_id=TREACHERY, effect=_DEPLOY).state
    after = state.players[0]
    assert after.troops_conflict == before.troops_conflict + 4
    assert after.combat_strength == before.combat_strength + 8
    assert _offered(state, "finish_reveal")


def test_treachery_trashed_by_a_combat_reward_deploys_for_the_next_step() -> None:
    """OQ-127: "Combat 보상 지급 중(Terrible Purpose의 trash 보상 등)에 열린
    Treachery의 Unload는 문장대로 troop 둘을 Conflict에 배치하고, 그 troop은 바로
    다음 단계에서 supply로 돌아간다" (rise-of-ix.md 7)."""
    conflict = "terrible_purpose"
    state = _give(_start(), 0, discard_pile=(TREACHERY,))
    state = replace(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict
        ),
        phase=GamePhase.COMBAT,
        decision_stack=(),
        current_conflict_ids=(conflict,),
        combat_intrigue_complete=False,
        combat_rewards_resolved=False,
        combat_end_triggers_offered=False,
    )
    owner = state.players[0]
    state = _seat(
        state,
        0,
        troops_garrison=owner.troops_garrison - 2,
        troops_conflict=2,
        combat_strength=4,
    )
    state = begin_combat_intrigue(state).state
    while state.decision_stack[-1].kind is FrameKind.COMBAT_INTRIGUE:
        passing = state.decision_stack[-1].decision
        assert isinstance(passing, PlayerDecision)
        state = _do(state, "pass_combat_intrigue", seat=passing.owner).state
    state = _do(state, "resolve_combat_reward_icon", effect="trash").state
    trashed = _do(state, "trash_combat_reward_card", card_id=TREACHERY)
    assert "card_unloaded" in _kinds(trashed.events)
    state = trashed.state
    assert state.decision_stack[-1].kind is FrameKind.UNLOAD_ICONS
    supply = state.players[0].troops_supply
    state = _do(state, UNLOAD_ROW, card_id=TREACHERY, effect=_DEPLOY).state
    assert state.players[0].troops_conflict == 4
    assert state.players[0].troops_supply == supply - 2
    state = _do(state, "resolve_combat_reward_icon", effect="victory_points").state
    chance = ChanceResolver(seed=3)
    while state.phase is GamePhase.COMBAT:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        assert not any(
            row.action_id == UNLOAD_ROW for row in _rows(state, decision.owner)
        )
        state = ENGINE.apply(state, _rows(state, decision.owner)[0]).state
    assert state.players[0].troops_conflict == 0
    assert state.players[0].troops_supply == supply + 2


def test_clean_up_moves_treachery_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(TREACHERY,)))
    assert state.phase is GamePhase.ROUND_START
    assert TREACHERY in state.players[0].discard_pile
    assert unloaded == []


# --- Freighter Fleet ----------------------------------------------------------

FLEET = "imperium:freighter_fleet:0"
FLEET_TWO = "imperium:freighter_fleet:1"
SHAI_HULUD = "imperium:shai_hulud:0"
_FREIGHTER = "freighter"


def _freighter_rows(state: GameState, seat: int = 0) -> set[str]:
    return {
        row.action_id
        for row in _rows(state, seat)
        if row.action_id
        in ("advance_freighter", "recall_freighter", "decline_freighter")
    }


def test_freighter_fleet_play_data_matches_the_app() -> None:
    """App table: cost 2, 2 copies, no Faction, the Spice Trade icon, no
    Agent box; screen pieces: Reveal "[Unload] [Freighter]"."""
    entry = IMPERIUM_CARDS_BY_ID["freighter_fleet"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (2, 2)
    assert entry.factions == () and entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is None
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_MOVE_FREIGHTER,
    )
    assert "freighter_fleet" not in REVEAL_GAIN_ABILITIES
    assert unload.unload_icons(FLEET) == ((_FREIGHTER, 1),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert ({FLEET, FLEET_TWO} <= set(deck)) == config.rise_of_ix


def test_freighter_fleet_revealed_may_move_its_freighter() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7):
    "you may move your Freighter in one of two ways" [Rise of Ix p. 5] -- up
    from the bottom, never a recall there; optional, so the Reveal may end
    with it unused (OQ-095 (2))."""
    state = _give(_start(), 0, hand=(FLEET,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    state = revealed.state
    ids = {row.action_id for row in ENGINE.whole_actions(state, 0)}
    assert "advance_reveal_freighter" in ids
    assert "recall_reveal_freighter" not in ids
    assert "finish_reveal" in ids
    moved = _do(state, "advance_reveal_freighter").state
    assert moved.players[0].freighter_space == 1
    assert not any(
        row.action_id.endswith("_reveal_freighter")
        for row in ENGINE.whole_actions(moved, 0)
    )
    unused = _do(state, "finish_reveal").state
    assert unused.players[0].freighter_space == 0


def test_freighter_fleet_and_guild_chief_administrator_name_their_freighter() -> (
    None
):
    """Both cards print the Reveal Freighter icon: each row names its card
    (``source``), so the move taken uses up that card's icon and the other's
    stays, still "may" (OQ-095 (2))."""
    administrator = "imperium:guild_chief_administrator:0"
    state = _give(_start(), 0, hand=(FLEET, administrator))
    state = _do(state, "reveal_turn").state
    assert _arguments(state, "advance_reveal_freighter") == {
        (("source", "freighter_fleet"),),
        (("source", "guild_chief_administrator"),),
    }
    moved = _do(state, "advance_reveal_freighter", source="freighter_fleet")
    assert any(
        f"reveal_card:{FLEET}:freighter" in event.event_id for event in moved.events
    )
    assert moved.state.players[0].freighter_space == 1
    assert _arguments(moved.state, "advance_reveal_freighter") == {
        (("source", "guild_chief_administrator"),),
    }
    assert _offered(moved.state, "finish_reveal")


def test_freighter_fleet_revealed_recall_owes_its_rewards_on_the_reveal() -> None:
    """A recall takes "지금 칸과 그 아래 모든 칸의 보상을 원하는 순서로" [Rise of
    Ix p. 5]: in the owner's Reveal they wait as rows of the turn."""
    state = _seat(_give(_start(), 0, hand=(FLEET,)), 0, freighter_space=1)
    state = _do(state, "reveal_turn").state
    recalled = _do(state, "recall_reveal_freighter").state
    assert recalled.players[0].freighter_space == 0
    assert recalled.decision_stack[-1].kind is FrameKind.REVEAL
    assert "resolve_shipping_reward" in {
        row.action_id for row in ENGINE.whole_actions(recalled, 0)
    }


def test_freighter_fleet_discarded_as_a_cost_holds_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": "Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7) -- the Freighter is a
    decision, so the draw waits under a hold until it is answered."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, FLEET, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    paid = _do(state, "discard_agent_card", card_id=FLEET)
    state = paid.state
    assert "agent_card_effect_resolved" not in _kinds(paid.events)
    assert state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    assert {row.action_id for row in _rows(state)} == {
        "advance_freighter",
        "decline_freighter",
    }
    hand = len(state.players[0].hand)
    check_observation_privacy(state)
    moved = _do(state, "advance_freighter")
    assert moved.state.players[0].freighter_space == 1
    assert len(moved.state.players[0].hand) == hand + 1
    kinds = _kinds(moved.events)
    assert kinds.index("freighter_moved") < kinds.index("agent_card_effect_resolved")


def test_freighter_fleet_trashed_as_a_cost_holds_what_the_trash_buys() -> None:
    """Shai-Hulud's "[Trash a card] -> [2 troops]": the troops wait for the
    Freighter's answer, its "may" decline included."""
    state = _give(_start(), 0, hand=(SHAI_HULUD, FLEET))
    state = _do(state, "choose_agent_card", card_id=SHAI_HULUD).state
    state = _do(state, "place_agent", space_id="imperial_basin").state
    garrison = state.players[0].troops_garrison
    state = _do(state, "trash_agent_card", card_id=FLEET).state
    assert FLEET in state.players[0].trashed
    assert state.players[0].troops_garrison == garrison
    assert _freighter_rows(state) == {"advance_freighter", "decline_freighter"}
    state = _do(state, "decline_freighter").state
    assert state.players[0].troops_garrison == garrison + 2
    assert state.players[0].freighter_space == 0


def test_freighter_fleet_trashed_by_jamis_waits_as_a_may_row() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; an effect in the owner's turn:
    the Freighter is a "may" row of the turn that opens its window."""
    state = _give(_start(), 0, hand=(JAMIS, FLEET))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    state = _do(state, "trash_agent_card", card_id=FLEET).state
    assert _arguments(state, UNLOAD_ROW) == {
        (("card_id", FLEET), ("effect", _FREIGHTER))
    }
    opened = _do(state, UNLOAD_ROW, card_id=FLEET, effect=_FREIGHTER).state
    assert opened.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    moved = _do(opened, "advance_freighter").state
    assert moved.players[0].freighter_space == 1
    assert moved.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS


def test_freighter_fleet_discarded_by_an_opponent_opens_its_owners_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): seat 1's own Freighter window, then back to the
    discard."""
    state = _start()
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, FLEET, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=FLEET).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.FREIGHTER_MOVE
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert not _rows(state, 0)
    state = _do(state, "advance_freighter", seat=1).state
    assert state.players[1].freighter_space == 1
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_freighter_fleet_revealed_then_trashed_moves_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_give(_start(), 0, hand=(FLEET,)))
    state = _do(state, "reveal_turn").state
    state = _do(state, "advance_reveal_freighter").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=FLEET).state
    state = _do(state, UNLOAD_ROW, card_id=FLEET, effect=_FREIGHTER).state
    state = _do(state, "advance_freighter").state
    assert state.players[0].freighter_space == 2
    assert state.decision_stack[-1].kind is FrameKind.REVEAL


def test_clean_up_moves_freighter_fleet_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(FLEET,)))
    assert state.phase is GamePhase.ROUND_START
    assert FLEET in state.players[0].discard_pile
    assert unloaded == []


# --- Ix-Guild Compact ---------------------------------------------------------

COMPACT = "imperium:ix_guild_compact:0"
WATER_PEDDLER = "imperium:water_peddler:0"
CHOAM_DELEGATE = "imperium:choam_delegate:0"
_NEGOTIATOR = "negotiator"


def _compact_placed(state: GameState, *hand: str) -> GameState:
    state = _give(state, 0, hand=(COMPACT, *hand))
    state = _do(state, "choose_agent_card", card_id=COMPACT).state
    return _do(state, "place_agent", space_id="foldspace").state


def test_ix_guild_compact_play_data_matches_the_app() -> None:
    """App table: cost 3, 1 copy, Spacing Guild, the Spacing Guild icon;
    screen pieces: Agent "[Discard] [Discard] -> [Dreadnought]", Reveal
    "[Unload] [Tech Negotiation] [Tech Negotiation]"."""
    entry = IMPERIUM_CARDS_BY_ID["ix_guild_compact"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (1, 3)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (AgentIcon.SPACING_GUILD,)
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_DISCARD_TWO_FOR_DREADNOUGHT
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_PLACE_TWO_NEGOTIATORS,
    )
    assert unload.unload_icons(COMPACT) == ((_NEGOTIATOR, 1), (_NEGOTIATOR, 1))
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert (COMPACT in deck) == config.rise_of_ix


def test_ix_guild_compact_discards_two_for_a_dreadnought() -> None:
    """ "[Discard] [Discard] -> [Dreadnought]": both cards are the cost
    [Rise of Ix p. 7] ("비용으로 두 장을 버리는 효과는 ... 비용 전액을 내야
    한다", OQ-118), the dreadnought commissioned once both are paid [Rise of
    Ix p. 6]."""
    state = _start()
    first, second = state.players[0].hand[:2]
    placed = _compact_placed(state, first, second)
    before = placed.players[0]
    picked = _do(placed, "discard_agent_card", card_id=first)
    assert "dreadnought_commissioned" not in _kinds(picked.events)
    assert first in picked.state.players[0].hand
    paid = _do(picked.state, "discard_agent_card", card_id=second)
    after = paid.state.players[0]
    assert {first, second} <= set(after.discard_pile)
    assert after.dreadnoughts_supply == before.dreadnoughts_supply - 1
    assert after.dreadnoughts_garrison == before.dreadnoughts_garrison + 1
    kinds = _kinds(paid.events)
    assert kinds.index("dreadnought_commissioned") < kinds.index(
        "agent_card_effect_resolved"
    )


def test_ix_guild_compact_arrow_needs_a_dreadnought_to_commission() -> None:
    """ "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다 ... 버릴 카드에
    Unload가 있어도 같다(Ix-Guild Compact에서 dreadnought가 둘 다 나가 있을 때"
    (docs/rules/rise-of-ix.md 15, OQ-071)."""
    state = _seat(_start(), 0, dreadnoughts_supply=0, dreadnoughts_garrison=2)
    placed = _compact_placed(state, WATER_PEDDLER, CHOAM_DELEGATE)
    assert not _offered(placed, "discard_agent_card")
    assert (
        agent_card_payment_block(placed, 0, _BOX.MAY_DISCARD_TWO_FOR_DREADNOUGHT)
        is AgentPaymentBlock.NO_DREADNOUGHT_TO_COMMISSION
    )
    one = _seat(placed, 0, dreadnoughts_supply=1, dreadnoughts_garrison=1)
    assert _offered(one, "discard_agent_card")


def test_ix_guild_compact_holds_its_dreadnought_for_a_discarded_freighter() -> None:
    """Two discarded Unload cards: Water Peddler's water is paid inside the
    payment, Freighter Fleet's Freighter is a decision -- the dreadnought
    waits under the hold until it is answered ("Unload를 끝까지 해결한 뒤
    오른쪽으로 간다", rise-of-ix.md 7)."""
    placed = _compact_placed(_start(), WATER_PEDDLER, FLEET)
    water = placed.players[0].resources.water
    supply = placed.players[0].dreadnoughts_supply
    state = _do(placed, "discard_agent_card", card_id=WATER_PEDDLER).state
    paid = _do(state, "discard_agent_card", card_id=FLEET)
    state = paid.state
    assert state.players[0].resources.water == water + 1
    assert state.players[0].dreadnoughts_supply == supply
    assert _freighter_rows(state) == {"advance_freighter", "decline_freighter"}
    done = _do(state, "advance_freighter").state
    assert done.players[0].dreadnoughts_supply == supply - 1
    assert done.players[0].freighter_space == 1


def test_ix_guild_compact_revealed_may_place_two_negotiators() -> None:
    """ "Reveal turn에 공개할 때(보통처럼)": each Tech Negotiation icon "you may
    take a troop from your supply" [Rise of Ix p. 4], one row each, in any
    order with the Reveal's others, optional (OQ-095 (2)); none with an empty
    supply ("supply가 비면 아무 일도 없다")."""
    state = _give(_start(), 0, hand=(COMPACT,))
    state = _do(state, "reveal_turn").state
    supply = state.players[0].troops_supply
    assert _offered(state, "place_reveal_negotiator")
    assert _offered(state, "finish_reveal")
    once = _do(state, "place_reveal_negotiator").state
    assert once.players[0].negotiators == state.players[0].negotiators + 1
    assert _offered(once, "place_reveal_negotiator")
    twice = _do(once, "place_reveal_negotiator").state
    assert twice.players[0].negotiators == state.players[0].negotiators + 2
    assert twice.players[0].troops_supply == supply - 2
    assert not _offered(twice, "place_reveal_negotiator")
    owner = state.players[0]
    empty = _seat(
        state,
        0,
        troops_supply=0,
        troops_garrison=owner.troops_garrison + owner.troops_supply,
    )
    assert not _offered(empty, "place_reveal_negotiator")


def test_ix_guild_compact_discarded_as_a_cost_holds_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": the two Tech Negotiation
    icons are decisions, each placed or refused in a window above the hold,
    and only then the card is drawn."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, COMPACT, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    state = _do(state, "discard_agent_card", card_id=COMPACT).state
    assert state.decision_stack[-1].kind is FrameKind.UNLOAD_ICONS
    rows = {(row.action_id, row.arguments) for row in _rows(state)}
    value = (("card_id", COMPACT), ("effect", _NEGOTIATOR))
    assert rows == {(UNLOAD_ROW, value), ("decline_unload_icon", value)}
    hand = len(state.players[0].hand)
    negotiators = state.players[0].negotiators
    state = _do(state, UNLOAD_ROW, card_id=COMPACT, effect=_NEGOTIATOR).state
    assert len(state.players[0].hand) == hand
    declined = _do(state, "decline_unload_icon", card_id=COMPACT, effect=_NEGOTIATOR)
    assert "unload_icon_declined" in _kinds(declined.events)
    after = declined.state.players[0]
    assert after.negotiators == negotiators + 1
    assert len(after.hand) == hand + 1


def test_ix_guild_compact_trashed_by_jamis_waits_as_may_rows() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; in its owner's turn each Tech
    Negotiation is a "may" row of the turn, holding no turn end back and
    lapsing at the press."""
    state = _give(_start(), 0, hand=(JAMIS, COMPACT))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    state = _do(state, "trash_agent_card", card_id=COMPACT).state
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert _offered(state, "finish_agent_turn")
    negotiators = state.players[0].negotiators
    state = _do(state, UNLOAD_ROW, card_id=COMPACT, effect=_NEGOTIATOR).state
    assert state.players[0].negotiators == negotiators + 1
    assert _offered(state, UNLOAD_ROW)
    finished = _do(state, "finish_agent_turn")
    assert _kinds(finished.events).count("unload_icon_lapsed") == 1


def test_ix_guild_compact_discarded_by_an_opponent_unloads_in_its_owners_window() -> (
    None
):
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): seat 1's window offers each icon and its refusal."""
    state = _start()
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, COMPACT, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=COMPACT).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert {row.action_id for row in _rows(state, 1)} == {
        UNLOAD_ROW,
        "decline_unload_icon",
    }
    negotiators = state.players[1].negotiators
    state = _do(state, UNLOAD_ROW, seat=1, card_id=COMPACT, effect=_NEGOTIATOR).state
    state = _do(state, UNLOAD_ROW, seat=1, card_id=COMPACT, effect=_NEGOTIATOR).state
    assert state.players[1].negotiators == negotiators + 2
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_ix_guild_compact_revealed_then_trashed_negotiates_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_give(_start(), 0, hand=(COMPACT,)))
    state = _do(state, "reveal_turn").state
    negotiators = state.players[0].negotiators
    state = _do(state, "place_reveal_negotiator").state
    state = _do(state, "place_reveal_negotiator").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=COMPACT).state
    state = _do(state, UNLOAD_ROW, card_id=COMPACT, effect=_NEGOTIATOR).state
    assert state.players[0].negotiators == negotiators + 3
    assert _offered(state, "finish_reveal")


def test_clean_up_moves_ix_guild_compact_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state, unloaded = _clean_up_round(_give(_start(), 0, in_play=(COMPACT,)))
    assert state.phase is GamePhase.ROUND_START
    assert COMPACT in state.players[0].discard_pile
    assert unloaded == []


# --- Boundless Ambition (promo) ------------------------------------------------

IX_PROMOS = replace(IX, promo_cards=True)
AMBITION = "imperium:boundless_ambition:0"
SIGNET_RING = "player:0:starter:signet_ring:0"
LIET_KYNES = "imperium:liet_kynes_card:0"
_ACQUIRE = "acquisition"
_REVEAL_ACQUISITIONS = ("acquire_reveal_imperium_card", "acquire_reveal_reserve_card")
_UNLOAD_ACQUISITIONS = ("acquire_unload_imperium_card", "acquire_unload_reserve_card")
type _Row = tuple[str, tuple[tuple[str, ActionValue], ...]]


def _cost(instance_id: str) -> int:
    cost = imperium_card_for_instance(instance_id).acquisition_cost
    assert cost is not None
    return cost


def _within_five(state: GameState, prefix: str) -> set[_Row]:
    """The rows "Acquire a card that costs [5] or less" should offer: each
    Row card and each Reserve card within 5, never Foldspace (OQ-125)."""

    return {
        (f"acquire_{prefix}_imperium_card", (("instance_id", instance_id),))
        for instance_id in state.imperium_row
        if _cost(instance_id) <= 5
    } | {
        (f"acquire_{prefix}_reserve_card", (("card_id", card_id),))
        for card_id, count in state.reserve_stacks
        if count
        and not RESERVE_STACKS_BY_ID[card_id].icon_only
        and RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= 5
    }


def _acquisition_rows(state: GameState, seat: int = 0) -> set[_Row]:
    _rows(state, seat)
    return {
        (row.action_id, row.arguments)
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id in (*_REVEAL_ACQUISITIONS, *_UNLOAD_ACQUISITIONS)
    }


def _with_spaceport(state: GameState, seat: int) -> GameState:
    """``seat`` holding Spaceport, taken from its Tech stack."""

    stacks = tuple(
        tuple(tile for tile in stack if tile != "spaceport")
        for stack in state.tech_stacks
    )
    held = (*state.players[seat].tech_ids, "spaceport")
    return _seat(replace(state, tech_stacks=stacks), seat, tech_ids=held)


def _cheap_row_card(state: GameState) -> str:
    """A Row card within 5 whose acquisition is the acquisition alone (no
    acquire box, which may open a window of its own), so the step after it
    is the one under test."""

    return next(
        card
        for card in state.imperium_row
        if _cost(card) <= 5
        and imperium_card_for_instance(card).acquisition_effect is None
    )


def _nothing_within_five(state: GameState) -> GameState:
    """Every Row card costs more than 5 and no Reserve card within 5 is
    left (an emptied Arrakis Liaison stack)."""

    dear = [card for card in state.imperium_deck if _cost(card) > 5]
    row = tuple(card if _cost(card) > 5 else dear.pop(0) for card in state.imperium_row)
    deck = tuple(
        card
        for card in (*state.imperium_deck, *state.imperium_row)
        if card not in row
    )
    reserve = tuple(
        (card_id, 0 if RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= 5 else count)
        for card_id, count in state.reserve_stacks
    )
    return replace(state, imperium_row=row, imperium_deck=deck, reserve_stacks=reserve)


def _in_row(state: GameState, card: str) -> GameState:
    """``card`` takes the Row's first position, whose card goes to its place
    in the Imperium deck."""

    assert card in state.imperium_deck
    first = state.imperium_row[0]
    return replace(
        state,
        imperium_row=(card, *state.imperium_row[1:]),
        imperium_deck=tuple(first if c == card else c for c in state.imperium_deck),
    )


def _acquisition_window(state: GameState, seat: int) -> None:
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert dict(top.context)[unload.UNLOAD_ACQUIRE_KEY] == AMBITION
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == seat


def test_boundless_ambition_play_data_matches_the_app() -> None:
    """App table: cost 5, 1 copy, no Faction, the four Faction icons, one
    Signet Ring icon; text: Agent "[Signet Ring]", Reveal "[Unload] Acquire a
    card that costs [5] or less." -- a promo, shuffled in with
    ``promo_cards`` only (rise-of-ix.md 1)."""
    entry = IMPERIUM_CARDS_BY_ID["boundless_ambition"]
    assert entry.play_data_complete and entry.unload and entry.promo
    assert (entry.copies, entry.acquisition_cost) == (1, 5)
    assert entry.factions == ()
    assert entry.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.LEADER_SIGNET
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.ACQUIRE_CARD_UP_TO_FIVE,
    )
    assert "boundless_ambition" not in REVEAL_GAIN_ABILITIES
    assert unload.unload_icons(AMBITION) == ((_ACQUIRE, 5),)
    for config in (IX_PROMOS, IX, replace(IX_PROMOS, rise_of_ix=False)):
        deck = content_for(config).imperium_deck_instance_ids
        assert (AMBITION in deck) == (config.rise_of_ix and config.promo_cards)


def test_boundless_ambition_uses_the_leaders_signet_ring_ability() -> None:
    """ "When you play your Signet Ring card on an Agent turn, you use the
    Signet Ring ability (with the corresponding icon) on your Leader." [Main
    p. 20]: its box is the Signet Ring card's -- Rabban's Brutality, "troop
    1" (docs/rules/imperium-base.md 12) -- sent with one of its four Faction
    icons."""
    state = _give(_start(config=IX_PROMOS), 0, hand=(AMBITION, SIGNET_RING))
    picked = _do(state, "choose_agent_card", card_id=AMBITION).state
    assert {
        dict(row.arguments)["space_id"]
        for row in ENGINE.whole_actions(picked, 0)
        if row.action_id == "place_agent"
    } >= {"secrets", "stillsuits", "wealth", "foldspace"}
    placed = _do(picked, "place_agent", space_id="secrets").state
    garrison = placed.players[0].troops_garrison
    resolved = _do(placed, "resolve_agent_card_effect")
    assert "leader_signet_resolved" in _kinds(resolved.events)
    assert resolved.state.players[0].troops_garrison == garrison + 1


def test_boundless_ambition_revealed_acquires_a_card_within_five() -> None:
    """ "Acquire a card that costs [5] or less." from the Row or the Reserve,
    not Foldspace (OQ-125); no "may", so it holds the Reveal's end while a
    card is in reach; free of Persuasion, the Row refills from the deck [Main
    p. 13]."""
    state = _give(_start(config=IX_PROMOS), 0, hand=(AMBITION,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    state = revealed.state
    assert _acquisition_rows(state) == _within_five(state, "reveal")
    assert not _offered(state, "finish_reveal")
    card = _cheap_row_card(state)
    refill = state.imperium_deck[0]
    position = state.imperium_row.index(card)
    acquired = _do(state, "acquire_reveal_imperium_card", instance_id=card)
    assert "card_acquired" in _kinds(acquired.events)
    state = acquired.state
    assert card in state.players[0].discard_pile
    assert state.imperium_row[position] == refill
    assert not _acquisition_rows(state)
    assert _offered(state, "finish_reveal")


def test_boundless_ambition_revealed_with_nothing_in_reach_lapses() -> None:
    """A mandatory choice with nothing to choose does not hold the Reveal's
    end and lapses with it (``reveal_turn.mandatory_choice_is_pending``); the
    page shows it waiting, with why."""
    state = _nothing_within_five(_give(_start(config=IX_PROMOS), 0, hand=(AMBITION,)))
    state = _do(state, "reveal_turn").state
    assert not _acquisition_rows(state)
    assert _offered(state, "finish_reveal")
    shown = unavailable_choices(state, 0, ENGINE.legal_actions(state, 0))
    assert shown is not None
    rows = shown["rows"]
    assert isinstance(rows, list)
    waiting = [row for row in rows if row["surface"] == "waiting"]
    assert [row["reason"] for row in waiting] == [
        "No card costing 5 or less to acquire; it lapses if still unmet when the "
        "Reveal turn ends"
    ]


def test_boundless_ambition_revealed_with_spaceport_may_go_on_the_deck() -> None:
    """Spaceport: "얻는 카드를 덱 위에 놓을 수 있다" (rise-of-ix.md 4) -- each
    acquisition row has its deck-top twin."""
    state = _with_spaceport(_give(_start(config=IX_PROMOS), 0, hand=(AMBITION,)), 0)
    state = _do(state, "reveal_turn").state
    rows = _acquisition_rows(state)
    plain = _within_five(state, "reveal")
    assert rows == plain | {
        (action_id, (*arguments, ("to_deck_top", True)))
        for action_id, arguments in plain
    }
    card = _cheap_row_card(state)
    on_top = _do(
        state, "acquire_reveal_imperium_card", instance_id=card, to_deck_top=True
    ).state
    assert on_top.players[0].deck[0] == card
    assert card not in on_top.players[0].discard_pile


def test_boundless_ambition_discarded_as_a_cost_holds_the_draw() -> None:
    """Truthsayer's "[Discard] -> [draw 1 card]": "Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7) -- the acquisition is a
    decision, so the draw waits under a hold until a card is acquired."""
    state = _start(config=IX_PROMOS)
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, AMBITION, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    paid = _do(state, "discard_agent_card", card_id=AMBITION)
    state = paid.state
    assert "agent_card_effect_resolved" not in _kinds(paid.events)
    _acquisition_window(state, 0)
    assert {(row.action_id, row.arguments) for row in _rows(state)} == _within_five(
        state, "unload"
    )
    hand = len(state.players[0].hand)
    check_observation_privacy(state)
    acquired = _do(state, "acquire_unload_reserve_card", card_id="arrakis_liaison")
    after = acquired.state.players[0]
    liaisons = [card for card in after.discard_pile if "arrakis_liaison" in card]
    assert len(liaisons) == 1
    assert len(after.hand) == hand + 1
    kinds = _kinds(acquired.events)
    assert kinds.index("card_acquired") < kinds.index("agent_card_effect_resolved")


def test_boundless_ambition_trashed_as_a_cost_holds_what_the_trash_buys() -> None:
    """Shai-Hulud's "[Trash a card] -> [2 troops]": the troops wait for the
    acquisition."""
    state = _give(_start(config=IX_PROMOS), 0, hand=(SHAI_HULUD, AMBITION))
    state = _do(state, "choose_agent_card", card_id=SHAI_HULUD).state
    state = _do(state, "place_agent", space_id="imperial_basin").state
    garrison = state.players[0].troops_garrison
    state = _do(state, "trash_agent_card", card_id=AMBITION).state
    assert AMBITION in state.players[0].trashed
    assert state.players[0].troops_garrison == garrison
    _acquisition_window(state, 0)
    card = _cheap_row_card(state)
    state = _do(state, "acquire_unload_imperium_card", instance_id=card).state
    assert card in state.players[0].discard_pile
    assert state.players[0].troops_garrison == garrison + 2


def test_boundless_ambition_trashed_by_jamis_holds_the_turns_end() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; in its owner's turn the
    acquisition is a mandatory row of the turn (no "may"), opening its
    window."""
    state = _give(_start(config=IX_PROMOS), 0, hand=(JAMIS, AMBITION))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    state = _do(state, "trash_agent_card", card_id=AMBITION).state
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert _arguments(state, UNLOAD_ROW) == {
        (("card_id", AMBITION), ("effect", _ACQUIRE))
    }
    assert not _offered(state, "finish_agent_turn")
    opened = _do(state, UNLOAD_ROW, card_id=AMBITION, effect=_ACQUIRE).state
    _acquisition_window(opened, 0)
    assert _acquisition_rows(opened) == _within_five(opened, "unload")
    card = _cheap_row_card(opened)
    done = _do(opened, "acquire_unload_imperium_card", instance_id=card).state
    assert card in done.players[0].discard_pile
    assert done.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS
    assert _offered(done, "finish_agent_turn")


def test_boundless_ambition_discarded_by_an_opponent_acquires_in_its_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): an acquisition outside its owner's turn, in seat 1's
    own window; the Row refills from the deck [Main p. 13], then back to the
    discard."""
    state = _start(config=IX_PROMOS)
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, AMBITION, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=AMBITION).state
    _acquisition_window(state, 1)
    assert not _rows(state, 0)
    assert _acquisition_rows(state, 1) == _within_five(state, "unload")
    check_observation_privacy(state)
    card = _cheap_row_card(state)
    refill = state.imperium_deck[0]
    position = state.imperium_row.index(card)
    state = _do(state, "acquire_unload_imperium_card", seat=1, instance_id=card).state
    assert card in state.players[1].discard_pile
    assert state.imperium_row[position] == refill
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_boundless_ambition_out_of_turn_keeps_spaceport_and_acquire_boxes() -> None:
    """Outside its owner's turn, Spaceport's deck-top choice (rise-of-ix.md 4)
    stands as anywhere, and an acquire box of one icon is gained at once
    (OQ-141: "아이콘 하나에 고를 것이 없는 지금의 획득 보너스는 그대로 즉시
    받는다") -- Liet Kynes' Emperor Influence."""
    state = _in_row(_start(config=IX_PROMOS), LIET_KYNES)
    state = _with_spaceport(state, 1)
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, AMBITION, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=AMBITION).state
    rows = _acquisition_rows(state, 1)
    plain = _within_five(state, "unload")
    assert rows == plain | {
        (action_id, (*arguments, ("to_deck_top", True)))
        for action_id, arguments in plain
    }
    emperor = state.players[1].influence.emperor
    state = _do(
        state,
        "acquire_unload_imperium_card",
        seat=1,
        instance_id=LIET_KYNES,
        to_deck_top=True,
    ).state
    assert state.players[1].deck[0] == LIET_KYNES
    assert state.players[1].influence.emperor == emperor + 1
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


@pytest.mark.parametrize(
    "card", ["imperium:chani_card:0", "imperium:water_peddler:0"]
)
def test_boundless_ambition_out_of_turn_gains_a_water_acquire_box(card: str) -> None:
    """Chani's and Water Peddler's acquire box, one water, is gained at once
    outside its owner's turn too (OQ-141)."""
    state = _in_row(_start(config=IX_PROMOS), card)
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, AMBITION, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=AMBITION).state
    water = state.players[1].resources.water
    state = _do(state, "acquire_unload_imperium_card", seat=1, instance_id=card).state
    assert card in state.players[1].discard_pile
    assert state.players[1].resources.water == water + 1
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_boundless_ambition_with_nothing_in_reach_fizzles_in_its_window() -> None:
    """ "That part of the effect fizzles" (the designer's ruling on Impress,
    OQ-057 (6)): with no card within 5 the window confirms it and closes."""
    state = _nothing_within_five(_start(config=IX_PROMOS))
    other = state.players[1].hand[0]
    state = _mohiam_asks_seat_one(state, AMBITION, other)
    state = _do(state, "discard_opponent_card", seat=1, card_id=AMBITION).state
    _acquisition_window(state, 1)
    assert {row.action_id for row in _rows(state, 1)} == {"skip_unload_acquisition"}
    skipped = _do(state, "skip_unload_acquisition", seat=1)
    assert "unload_acquisition_empty" in _kinds(skipped.events)
    assert skipped.state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_boundless_ambition_revealed_then_trashed_acquires_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다"."""
    state = _with_cull(_give(_start(config=IX_PROMOS), 0, hand=(AMBITION,)))
    state = _do(state, "reveal_turn").state
    first = _cheap_row_card(state)
    state = _do(state, "acquire_reveal_imperium_card", instance_id=first).state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=AMBITION).state
    assert not _offered(state, "finish_reveal")
    state = _do(state, UNLOAD_ROW, card_id=AMBITION, effect=_ACQUIRE).state
    _acquisition_window(state, 0)
    second = _cheap_row_card(state)
    state = _do(state, "acquire_unload_imperium_card", instance_id=second).state
    assert {first, second} <= set(state.players[0].discard_pile)
    assert state.decision_stack[-1].kind is FrameKind.REVEAL
    assert _offered(state, "finish_reveal")


def test_clean_up_moves_boundless_ambition_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2])."""
    state = _give(_start(config=IX_PROMOS), 0, in_play=(AMBITION,))
    state, unloaded = _clean_up_round(state)
    assert state.phase is GamePhase.ROUND_START
    assert AMBITION in state.players[0].discard_pile
    assert unloaded == []


# --- Several Unloads held by one cost ------------------------------------------
#
# "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
# 오른쪽으로 간다" (designer ruling, rise-of-ix.md 7): a cost of two cards is
# both discards, so every Unload it triggers resolves before the right side.
# Several cards' held icons open one window above the hold, every icon a row,
# and the owner picks their order (``unload._open_held``).

CORRINTH = "imperium:corrinth_city:0"


def _taken(
    state: GameState,
    action_id: str,
    arguments: Mapping[str, object],
    *,
    codec: bool = True,
) -> tuple[RuleResult, tuple[DomainAction, ...]]:
    """Seat 0's whole action by its steps: the result and the steps taken,
    each row round-tripped through the codec unless ``codec`` is False."""

    seat = 0

    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    steps: list[DomainAction] = []
    while True:
        rows = _rows(state, seat) if codec else ENGINE.legal_actions(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        steps.append(row)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events)), tuple(steps)


def _loaded(start: GameState, steps: tuple[DomainAction, ...]) -> GameState:
    """A save writes a game's steps from its start as JSON
    (``server.persistence``); a load replays them, as an undo replays the
    steps before the one it takes back."""

    saved = json.dumps([serialize_step(step) for step in steps])
    state = start
    for index, value in enumerate(json.loads(saved)):
        state = ENGINE.apply(state, deserialize_step(value, index)).state
    return state


def _holds(state: GameState) -> int:
    return sum(1 for frame in state.decision_stack if is_unload_hold(frame))


type _Step = tuple[str, dict[str, object]]


@dataclass(frozen=True)
class _HeldRun:
    held: GameState
    answered: tuple[tuple[str, ...], ...]
    """Each answer's event kinds, in order."""
    finished: GameState


def _held_run(
    start: GameState,
    setup: tuple[_Step, ...],
    opening: _Step,
    answers: tuple[_Step, ...],
    *,
    codec: bool = True,
) -> _HeldRun:
    """Play ``setup``, the payment ``opening`` that holds, then ``answers``.

    On the way: the undo of the opening step (the steps before it replayed)
    leaves no hold and taking it again opens the same one; a save and load in
    the middle of the answers (after half of them) is the same state; the
    whole game replays to the finished state.
    """

    state = start
    steps: tuple[DomainAction, ...] = ()
    for action_id, arguments in setup:
        result, taken = _taken(state, action_id, arguments, codec=codec)
        state, steps = result.state, (*steps, *taken)
    before, before_steps = state, steps
    opened, taken = _taken(state, *opening, codec=codec)
    held, steps = opened.state, (*steps, *taken)
    assert _holds(held) == 1
    check_observation_privacy(held)
    undone = _loaded(start, before_steps)
    assert canonical_state_hash(undone) == canonical_state_hash(before)
    assert _holds(undone) == 0
    again, _ = _taken(undone, *opening, codec=codec)
    assert canonical_state_hash(again.state) == canonical_state_hash(held)
    state = held
    answered: list[tuple[str, ...]] = []
    for index, (action_id, arguments) in enumerate(answers):
        if index == len(answers) // 2:
            loaded = _loaded(start, steps)
            assert canonical_state_hash(loaded) == canonical_state_hash(state)
            state = loaded
        result, taken = _taken(state, action_id, arguments, codec=codec)
        answered.append(tuple(_kinds(result.events)))
        state, steps = result.state, (*steps, *taken)
        if index < len(answers) - 1:
            assert _holds(state) == 1
    assert _holds(state) == 0
    assert canonical_state_hash(_loaded(start, steps)) == canonical_state_hash(state)
    return _HeldRun(held=held, answered=tuple(answered), finished=state)


def _held_rows(state: GameState, seat: int = 0, *, codec: bool = True) -> set[_Row]:
    rows = _rows(state, seat) if codec else ENGINE.legal_actions(state, seat)
    return {(row.action_id, row.arguments) for row in rows}


def _icon(card_id: str, effect: str) -> tuple[tuple[str, ActionValue], ...]:
    return (("card_id", card_id), ("effect", effect))


def _paid_once_last(run: _HeldRun, kind: str, after: str) -> None:
    """The right side's event ``kind`` comes once, in the last answer, after
    that answer's ``after``."""

    assert [kinds.count(kind) for kinds in run.answered] == [
        *([0] * (len(run.answered) - 1)),
        1,
    ]
    last = run.answered[-1]
    assert last.index(after) < last.index(kind)


_COMPACT_SETUP: tuple[_Step, ...] = (
    ("choose_agent_card", {"card_id": COMPACT}),
    ("place_agent", {"space_id": "foldspace"}),
)


def test_two_freighter_fleets_discarded_together_both_move_first() -> None:
    """Ix-Guild Compact's "[Discard] [Discard] -> [Dreadnought]" paid with two
    Freighter Fleets: both Freighters are offered at once, the owner picks
    the second card's first, and the dreadnought comes once, after both."""
    start = _give(_start(), 0, hand=(COMPACT, FLEET, FLEET_TWO))
    supply = start.players[0].dreadnoughts_supply
    run = _held_run(
        start,
        (*_COMPACT_SETUP, ("discard_agent_card", {"card_id": FLEET})),
        ("discard_agent_card", {"card_id": FLEET_TWO}),
        (
            (UNLOAD_ROW, {"card_id": FLEET_TWO, "effect": _FREIGHTER}),
            ("advance_freighter", {}),
            (UNLOAD_ROW, {"card_id": FLEET, "effect": _FREIGHTER}),
            ("advance_freighter", {}),
        ),
    )
    top = run.held.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert dict(top.context)[unload.UNLOAD_BY_CARD_KEY] is True
    assert _held_rows(run.held) == {
        (action_id, _icon(card, _FREIGHTER))
        for action_id in (UNLOAD_ROW, "decline_unload_icon")
        for card in (FLEET, FLEET_TWO)
    }
    assert run.held.players[0].dreadnoughts_supply == supply
    _paid_once_last(run, "dreadnought_commissioned", "freighter_moved")
    assert run.finished.players[0].freighter_space == 2
    assert run.finished.players[0].dreadnoughts_supply == supply - 1
    assert run.finished.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS


def test_a_freighter_and_an_acquisition_discarded_together_in_the_owners_order() -> (
    None
):
    """Two different decision boxes in one payment, Freighter Fleet's
    Freighter and Boundless Ambition's acquisition: the owner takes the
    acquisition first, then leaves the "may" Freighter; the dreadnought comes
    once, after both."""
    start = _give(_start(config=IX_PROMOS), 0, hand=(COMPACT, FLEET, AMBITION))
    card = _cheap_row_card(start)
    run = _held_run(
        start,
        (*_COMPACT_SETUP, ("discard_agent_card", {"card_id": FLEET})),
        ("discard_agent_card", {"card_id": AMBITION}),
        (
            (UNLOAD_ROW, {"card_id": AMBITION, "effect": _ACQUIRE}),
            ("acquire_unload_imperium_card", {"instance_id": card}),
            ("decline_unload_icon", {"card_id": FLEET, "effect": _FREIGHTER}),
        ),
    )
    assert _held_rows(run.held) == {
        (UNLOAD_ROW, _icon(FLEET, _FREIGHTER)),
        ("decline_unload_icon", _icon(FLEET, _FREIGHTER)),
        (UNLOAD_ROW, _icon(AMBITION, _ACQUIRE)),
    }
    assert "card_acquired" in run.answered[1]
    _paid_once_last(run, "dreadnought_commissioned", "unload_icon_declined")
    assert card in run.finished.players[0].discard_pile
    assert run.finished.players[0].freighter_space == 0


def test_a_freighter_held_beside_water_peddlers_water_paid_at_once() -> None:
    """One decision box and one plain box in one payment: Water Peddler's
    water is paid inside it, Freighter Fleet's Freighter holds the
    dreadnought."""
    start = _give(_start(), 0, hand=(COMPACT, WATER_PEDDLER, FLEET))
    water = start.players[0].resources.water
    run = _held_run(
        start,
        (*_COMPACT_SETUP, ("discard_agent_card", {"card_id": WATER_PEDDLER})),
        ("discard_agent_card", {"card_id": FLEET}),
        (("decline_freighter", {}),),
    )
    assert run.held.players[0].resources.water == water + 1
    assert run.held.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    _paid_once_last(run, "dreadnought_commissioned", "freighter_declined")
    assert run.finished.players[0].resources.water == water + 1


def test_corrinth_city_pays_its_victory_point_after_two_unload_cards() -> None:
    """Corrinth City's "discard 2 cards and pay 5 Solari -> 1 Victory Point"
    paid with Freighter Fleet and Ix-Guild Compact: the Freighter and both
    Tech Negotiations are offered at once, in the owner's order, and the
    Victory Point comes once, after all three. No catalog holds Corrinth
    City beside the Rise of Ix cards yet (Uprising with Rise of Ix is P7), so
    its rows are not round-tripped through a codec."""
    state = _give(_start(), 0, hand=(CORRINTH, FLEET, COMPACT))
    owner = state.players[0]
    start = _seat(state, 0, resources=replace(owner.resources, solari=5))
    points = start.players[0].victory_points
    negotiators = start.players[0].negotiators
    run = _held_run(
        start,
        (
            ("choose_agent_card", {"card_id": CORRINTH}),
            ("place_agent", {"space_id": "wealth"}),
            ("select_corrinth_city_discard", {"card_id": FLEET}),
        ),
        ("pay_corrinth_city", {"card_id": COMPACT}),
        (
            (UNLOAD_ROW, {"card_id": COMPACT, "effect": _NEGOTIATOR}),
            (UNLOAD_ROW, {"card_id": FLEET, "effect": _FREIGHTER}),
            ("advance_freighter", {}),
            (UNLOAD_ROW, {"card_id": COMPACT, "effect": _NEGOTIATOR}),
        ),
        codec=False,
    )
    assert _held_rows(run.held, codec=False) == {
        (action_id, _icon(card, effect))
        for action_id in (UNLOAD_ROW, "decline_unload_icon")
        for card, effect in ((FLEET, _FREIGHTER), (COMPACT, _NEGOTIATOR))
    }
    assert run.held.players[0].victory_points == points
    assert run.held.players[0].resources.solari == 0
    _paid_once_last(run, "resources_gained", "negotiator_placed")
    after = run.finished.players[0]
    assert after.victory_points == points + 1
    assert after.negotiators == negotiators + 2
    assert after.freighter_space == 1
