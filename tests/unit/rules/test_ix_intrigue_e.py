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
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    UnitsDeployedThisTurnAtLeast,
)
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
from dune_imperium.rules.action_shapes import Source, printer_value
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.combat_deployment import (
    UNITS_COMMITTED_KEY,
    commit_units_with_dreadnoughts,
    dreadnoughts_deployed_this_turn,
    reconcile_deployment_after_retreat,
)
from dune_imperium.rules.effect_interpreter import (
    condition_holds,
    option_unplayable_reason,
)
from dune_imperium.rules.endgame import begin_endgame_intrigue
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.tech import face_up_tech_ids, push_tech_acquisition

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


# Machine Culture ----------------------------------------------------------------

MACHINE = "machine_culture"
# Ix's three stacks of six, the top face up: the tops cost Detonation Devices
# 3, Holtzman Engine 6 and Restricted Ordnance 4 (the next tiles are Artillery
# 1, Invasion Ships 5 and Minimic Film 2). Laid by hand so a test never
# depends on what a seed dealt.
STACKS = (
    ("detonation_devices", "artillery", "chaumurky"),
    ("holtzman_engine", "invasion_ships", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)
THREE_TECHS = ("detonation_devices", "spaceport", "troop_transports")


def _tech_game(
    card: str = MACHINE,
    *,
    spice: int,
    negotiators: int = 0,
    stacks: tuple[tuple[str, ...], ...] = STACKS,
    **changes: Any,
) -> GameState:
    """Seat 0 holding ``card`` with ``spice`` and ``negotiators`` (taken from
    its supply), the Ix stacks laid as ``stacks`` less any tile it holds, at
    its first turn."""

    state = _start(card, **changes)
    owner = state.players[0]
    owner = replace(
        owner,
        resources=replace(owner.resources, spice=spice),
        troops_supply=owner.troops_supply - negotiators,
        negotiators=negotiators,
    )
    return replace(
        state,
        players=(owner, *state.players[1:]),
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile not in owner.tech_ids)
            for stack in stacks
        ),
    )


def test_machine_culture_is_a_plot_and_endgame_card_in_the_ix_deck() -> None:
    """The Acquire Tech icon [PLOT] -OR- "If you have three or more Techs:"
    1 VP [ENDGAME] [Machine Culture card, Steam app text, log line and screen
    pieces]; one copy, shuffled in with Rise of Ix only [Rise of Ix p. 2]."""
    entry = intrigue_card_for_instance("intrigue:machine_culture:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert [option.timing.value for option in entry.options] == ["plot", "endgame"]
    assert _in_deck(MACHINE, CONFIG)
    assert not _in_deck(MACHINE, ORIGINAL)
    assert intrigue_card_text(entry) == [
        "Plot — Acquire a Tech tile",
        "Endgame — If you have 3 or more Tech tiles: Gain 1 VP",
    ]
    assert len(intrigue_card_text_ko(entry)) == 2


def test_machine_culture_plot_is_an_acquire_tech_with_no_discount() -> None:
    """The Plot band prints the icon alone, no discount number: "Machine
    Culture Plot면("Acquire Tech", 할인 없음)" (open-questions.md OQ-113 (C),
    rise-of-ix.md 15). The piece's own default is a 1 spice discount, so the
    entry states 0."""
    entry = intrigue_card_for_instance("intrigue:machine_culture:0")
    (section,) = entry.options[0].sections
    assert section.costs == ()
    assert section.rewards == (AcquireTech(discount=0),)
    assert AcquireTech().discount == 1


@pytest.mark.parametrize(
    ("spice", "negotiators", "offered"),
    [
        # The cheapest top is Detonation Devices at 3 spice.
        (0, 0, set()),
        (2, 0, set()),
        (3, 0, {0}),
        (9, 0, {0}),
        # "Negotiator를 supply로 돌려 하나에 spice 1씩 깎는다" (rise-of-ix.md
        # 4): the Negotiators in hand count toward what can be bought.
        (1, 1, set()),
        (1, 2, {0}),
        (0, 3, {0}),
    ],
)
def test_machine_culture_plot_is_played_only_while_a_tile_can_be_bought(
    spice: int, negotiators: int, offered: set[int]
) -> None:
    """ "Machine Culture는 Tech를 얻어야 낸다" (the designer, rise-of-ix.md 9.3;
    OQ-113 (C): the tile's price is the card's cost), and "To play an Intrigue
    card, you must meet its conditions and pay its costs." [FAQ p. 2]. A tile
    is in reach when its spice cost, less the Negotiators returned, is within
    the seat's spice."""
    state = _tech_game(spice=spice, negotiators=negotiators)
    assert _options(state, MACHINE) == offered


def test_machine_culture_plot_is_not_played_with_every_stack_empty() -> None:
    """With no tile left to take the icon buys nothing, however much spice the
    seat holds, so the card is not played (OQ-113 (C))."""
    state = _tech_game(spice=20, negotiators=2, stacks=((), (), ()))
    assert _options(state, MACHINE) == set()


def test_machine_culture_plot_names_the_tile_it_cannot_buy() -> None:
    """The page's reason for the greyed-out card reads the check the legal list
    does (``option_unplayable_reason``): the Acquire Tech has no tile in
    reach."""
    state = _tech_game(spice=1)
    entry = intrigue_card_for_instance("intrigue:machine_culture:0")
    assert option_unplayable_reason(state, 0, entry.options[0]) == AcquireTech(0)
    assert option_unplayable_reason(_tech_game(spice=3), 0, entry.options[0]) is None


def test_machine_culture_plot_must_acquire_once_played() -> None:
    """ "You must acquire a tech when you play Machine Culture" (the designer,
    rise-of-ix.md 9.3; designer-rulings-audit.md 9: "Intrigue 출처 frame에서만
    decline 제거"): unlike a board space's "may" [Rise of Ix p. 4] the frame
    offers every tile in reach and no refusal."""
    state = _tech_game(spice=4)
    opened = _play(state, MACHINE)
    rows = [
        row
        for row in _rows(opened)
        if row.action_id in ("acquire_tech", "decline_tech")
    ]
    assert [dict(row.arguments)["tech_id"] for row in rows] == [
        "detonation_devices",
        "restricted_ordnance",
    ]
    assert {row.action_id for row in rows} == {"acquire_tech"}
    # Playing the card spends nothing: the price is paid with the tile.
    assert opened.players[0].resources.spice == 4


def test_machine_culture_plot_buys_a_tile_at_its_full_price() -> None:
    """No discount: the seat pays the tile's printed spice cost, takes the
    tile, the stack's next tile turns face up, and the card is discarded."""
    state = _tech_game(spice=9)
    done = _take(_play(state, MACHINE), "acquire_tech", tech_id="restricted_ordnance")
    owner = done.players[0]
    assert owner.resources.spice == 9 - 4
    assert owner.tech_ids == ("restricted_ordnance",)
    assert face_up_tech_ids(done) == (
        "detonation_devices",
        "holtzman_engine",
        "minimic_film",
    )
    assert owner.intrigue_cards == ()
    assert "intrigue:machine_culture:0" in done.intrigue_discard
    assert all(
        frame.kind is not FrameKind.TECH_ACQUISITION for frame in done.decision_stack
    )


def test_machine_culture_plot_may_return_negotiators_toward_the_price() -> None:
    """The Acquire Tech icon of Rise of Ix lets the buyer return Negotiators,
    one spice off each [Rise of Ix p. 4]; the card's own discount adds none."""
    state = _tech_game(spice=1, negotiators=2)
    opened = _play(state, MACHINE)
    (row,) = [row for row in _rows(opened) if row.action_id == "acquire_tech"]
    assert dict(row.arguments) == {"negotiators": 2, "tech_id": "detonation_devices"}
    done = _take(opened, "acquire_tech", negotiators=2, tech_id="detonation_devices")
    owner = done.players[0]
    assert owner.resources.spice == 0
    assert owner.negotiators == 0
    assert owner.tech_ids == ("detonation_devices",)


def test_machine_culture_plot_plays_in_the_reveal_turn() -> None:
    """A Plot is played in the owner's Agent or Reveal turn [DI pp. 7-8]."""
    state = _take(_tech_game(spice=4), "reveal_turn")
    assert _options(state, MACHINE) == {0}
    done = _take(_play(state, MACHINE), "acquire_tech", tech_id="detonation_devices")
    assert done.players[0].tech_ids == ("detonation_devices",)


def test_machine_culture_refusal_stays_when_no_tile_is_in_reach() -> None:
    """Were the frame ever open with nothing to buy, the refusal is its only
    row and the printer it names is the card's own: the catalog holds that
    row (``decline_tech`` of the Intrigue cards that print the icon)."""
    state = _tech_game(spice=0)
    opened = push_tech_acquisition(
        state,
        0,
        discount=0,
        source="s",
        printer=printer_value(Source.INTRIGUE, MACHINE),
    ).state
    assert [row.action_id for row in _rows(opened)] == ["decline_tech"]


def test_machine_culture_plot_is_not_a_combat_or_an_endgame_card() -> None:
    """Combat Intrigue is played in the Combat phase only [DI p. 12]: the Plot
    half is not offered there, however much spice the seat holds."""
    state = replace(
        _fight(MACHINE, resources=Resources(spice=9), **UNIT), tech_stacks=STACKS
    )
    assert _options(state, MACHINE) == set()


@pytest.mark.parametrize(("tiles", "offered"), [(0, set()), (2, set()), (3, {1})])
def test_machine_culture_endgame_needs_three_tech_tiles(
    tiles: int, offered: set[int]
) -> None:
    """ "If you have three or more Techs:" one VP [Machine Culture card, Steam
    app text]: a printed condition, mandatory [FAQ p. 2]. The Plot half is not
    an Endgame card, with spice for a tile or without."""
    state = _window(MACHINE, resources=Resources(spice=9), tech_ids=THREE_TECHS[:tiles])
    assert _offered(state) == offered


def test_machine_culture_endgame_scores_one_victory_point() -> None:
    """The Endgame half is a condition, not a cost: the tiles stay and the card
    is discarded."""
    state = _window(MACHINE, tech_ids=THREE_TECHS, victory_points=6)
    done = _end_play(state, MACHINE, 1)
    assert done.players[0].victory_points == 7
    assert done.players[0].tech_ids == THREE_TECHS
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == ("intrigue:machine_culture:0",)


def test_machine_culture_endgame_is_not_played_in_a_turn() -> None:
    """Endgame Intrigue is played in the Endgame window only [DI p. 13]: a seat
    with three tiles is not offered the Endgame half in its Agent turn."""
    state = _tech_game(spice=0, tech_ids=THREE_TECHS)
    assert _options(state, MACHINE) == set()


# Diversion ----------------------------------------------------------------------

DIVERSION = "diversion"


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


def _hardy(troops: int, ships: int, **changes: Any) -> GameState:
    """Seat 0 holds Diversion, three troops and both dreadnoughts at home, and
    sends an Agent to Hardy Warriors (a Combat space that recruits two
    troops), deploying ``troops`` troops and ``ships`` dreadnoughts: the
    deployment window stays open, the turn not yet ended [Main p. 10]."""

    state = _start(
        DIVERSION,
        resources=Resources(solari=5, spice=5, water=5),
        troops_garrison=3,
        troops_supply=9,
        troops_conflict=0,
        dreadnoughts_garrison=2,
        **changes,
    )
    state = _take(
        _visit(state, "hardy_warriors"), "resolve_board_effect", effect="troops"
    )
    state = _take(state, "resolve_faction_influence")
    if troops:
        state = _take(state, "deploy_troops", count=troops)
    if ships:
        state = _take(state, "deploy_dreadnoughts", count=ships)
    return state


def _withdrawals(state: GameState) -> dict[str, set[int]]:
    found: dict[str, set[int]] = {}
    for row in _rows(state):
        if row.action_id.startswith("withdraw_"):
            found.setdefault(row.action_id, set()).add(
                int(dict(row.arguments)["count"])
            )
    return found


def test_diversion_is_a_plot_card_in_the_ix_deck() -> None:
    """ "When you deploy four or more units to the Conflict in a single turn:"
    the Freighter icon [Diversion card, Steam app text, log line "Played
    Diversion to gain Freighter" and screen pieces]; one copy, shuffled in
    with Rise of Ix only [Rise of Ix p. 2]."""
    entry = intrigue_card_for_instance("intrigue:diversion:0")
    assert entry.play_data_complete
    assert entry.copies == 1
    assert [option.timing.value for option in entry.options] == ["plot"]
    (section,) = entry.options[0].sections
    assert section.condition == UnitsDeployedThisTurnAtLeast(4, dreadnoughts=True)
    assert section.costs == ()
    assert _in_deck(DIVERSION, CONFIG)
    assert not _in_deck(DIVERSION, ORIGINAL)
    assert intrigue_card_text(entry) == [
        "Plot — If you have deployed 4 or more units to the Conflict this turn:"
        " Move your Freighter up one space or recall it"
    ]
    assert len(intrigue_card_text_ko(entry)) == 1


@pytest.mark.parametrize(
    ("troops", "ships", "offered"),
    [
        (0, 0, set()),
        (3, 0, set()),
        (2, 1, set()),
        (0, 2, set()),
        # "four or more units": a dreadnought is a unit, though no troop
        # [Rise of Ix p. 6] (rise-of-ix.md 6, table row "unit").
        (4, 0, {0}),
        (3, 1, {0}),
        (2, 2, {0}),
    ],
)
def test_diversion_counts_the_dreadnoughts_with_the_troops(
    troops: int, ships: int, offered: set[int]
) -> None:
    """The units deployed this turn, troops and dreadnoughts together, are the
    condition: "To play an Intrigue card, you must meet its conditions"
    [FAQ p. 2], met once the units are deployed [Board Guide p. 10]
    (OQ-016)."""
    assert _options(_hardy(troops, ships), DIVERSION) == offered


def test_diversion_counts_only_the_deployment_of_this_turn() -> None:
    """ "in a single turn": units that stood in the Conflict before the turn,
    dreadnoughts among them, are no deployment of this turn."""
    state = _start(
        DIVERSION,
        troops_conflict=3,
        troops_supply=9,
        troops_garrison=0,
        dreadnoughts_conflict=2,
        combat_strength=12,
    )
    assert _options(state, DIVERSION) == set()
    assert dreadnoughts_deployed_this_turn(state, 0) == 0


def test_the_plain_unit_condition_still_leaves_the_dreadnoughts_out() -> None:
    """Distraction's and Coercive Negotiation's count is the turn's troops,
    Commanders and sandworms: only a condition that says ``dreadnoughts``
    adds the turn's dreadnoughts (the same deployment, two troops and two
    dreadnoughts)."""
    state = _hardy(2, 2)
    assert dreadnoughts_deployed_this_turn(state, 0) == 2
    assert condition_holds(state, 0, UnitsDeployedThisTurnAtLeast(2))
    assert not condition_holds(state, 0, UnitsDeployedThisTurnAtLeast(3))
    assert condition_holds(state, 0, UnitsDeployedThisTurnAtLeast(4, dreadnoughts=True))
    assert not condition_holds(
        state, 0, UnitsDeployedThisTurnAtLeast(5, dreadnoughts=True)
    )


def test_a_withdrawal_undoes_the_deployment_diversion_needs() -> None:
    """Before the card is played nothing is committed, so the deployment may
    still be taken back (OQ-029) and a withdrawal undoes it: with a dreadnought
    back in the garrison the card is no longer playable until four units are
    deployed again."""
    state = _hardy(2, 2)
    assert _options(state, DIVERSION) == {0}
    assert _withdrawals(state) == {
        "withdraw_troops": {1, 2},
        "withdraw_dreadnoughts": {1, 2},
    }
    back = _take(state, "withdraw_dreadnoughts", count=1)
    assert dreadnoughts_deployed_this_turn(back, 0) == 1
    assert _options(back, DIVERSION) == set()
    again = _take(back, "deploy_dreadnoughts", count=1)
    assert _options(again, DIVERSION) == {0}


def test_a_retreat_after_the_deployment_keeps_diversion_playable() -> None:
    """ "a moment in time when there are [N] units in the conflict that were
    deployed to the conflict this turn, then that requirement becomes true"
    (Message from designer, OQ-016; rise-of-ix.md 15): a card's retreat leaves
    the turn's count standing, the dreadnoughts' too -- only a withdrawal
    lowers the frame's count."""
    state = _hardy(2, 2)
    retreated = reconcile_deployment_after_retreat(state, 0, troops=0, dreadnoughts=1)
    assert dreadnoughts_deployed_this_turn(retreated, 0) == 2
    assert _options(retreated, DIVERSION) == {0}


def test_diversion_reads_the_troops_alone_outside_an_agent_turn() -> None:
    """A Reveal turn has no dreadnought deployment, so its four units are the
    turn's count (``units_deployed_turn``) alone, and a Plot is played in the
    owner's Agent or Reveal turn [DI pp. 7-8]."""
    state = _start(
        DIVERSION,
        troops_conflict=4,
        troops_supply=8,
        troops_garrison=0,
        units_deployed_turn=4,
        units_deployed_peak=4,
        combat_strength=8,
    )
    assert _options(state, DIVERSION) == {0}
    assert _options(_take(state, "reveal_turn"), DIVERSION) == {0}


def test_diversion_gains_a_freighter_move_that_may_be_declined() -> None:
    """The Freighter icon: a move up or a recall, "you may" [Rise of Ix p. 5],
    as Expedite's: the played card is discarded whichever the seat answers."""
    state = _hardy(2, 2)
    opened = _play(state, DIVERSION)
    ids = {row.action_id for row in _rows(opened)}
    assert {"advance_intrigue_freighter", "decline_intrigue_freighter"} <= ids
    done = _take(opened, "advance_intrigue_freighter")
    assert done.players[0].freighter_space == 1
    assert "intrigue:diversion:0" in done.intrigue_discard
    declined = _take(_play(state, DIVERSION), "decline_intrigue_freighter")
    assert declined.players[0].freighter_space == 0
    assert "intrigue:diversion:0" in declined.intrigue_discard
    # The deployment itself is untouched by the card.
    assert done.players[0].troops_conflict == 2
    assert done.players[0].dreadnoughts_conflict == 2


@pytest.mark.parametrize(("troops", "ships"), [(4, 0), (3, 1), (2, 2)])
def test_a_played_diversion_keeps_its_four_units_deployed(
    troops: int, ships: int
) -> None:
    """ "배치 수를 그 조건(최소 수) 아래로 내리는 회수는 허용하지 않는다"
    (OQ-029 (3)): the four units the card used, troops and dreadnoughts
    together, may not be withdrawn below four, whichever kind goes first."""
    state = _hardy(troops, ships)
    played = _take(_play(state, DIVERSION), "decline_intrigue_freighter")
    assert _withdrawals(played) == {}
    frame = played.decision_stack[-1]
    assert dict(frame.context)[UNITS_COMMITTED_KEY] == 4
    # The troops' own floor is Distraction's and Coercive Negotiation's.
    assert played.players[0].units_deployed_committed == 0
    done = _take(played, "finish_agent_turn")
    assert done.players[0].troops_conflict == troops
    assert done.players[0].dreadnoughts_conflict == ships


def test_a_commitment_below_the_total_leaves_the_rest_to_withdraw() -> None:
    """The floor is on the total: with four units deployed and three
    committed, one unit of either kind may still go back, and only one."""
    state = commit_units_with_dreadnoughts(_hardy(2, 2), 0, 3)
    assert _withdrawals(state) == {
        "withdraw_troops": {1},
        "withdraw_dreadnoughts": {1},
    }
    # The commitment only ever rises.
    again = commit_units_with_dreadnoughts(state, 0, 2)
    assert dict(again.decision_stack[-1].context)[UNITS_COMMITTED_KEY] == 3


def test_a_commitment_outside_an_agent_turn_records_nothing() -> None:
    """No withdrawal exists outside an Agent turn's deployment window."""
    state = _start(DIVERSION)
    assert commit_units_with_dreadnoughts(state, 0, 4) is state
