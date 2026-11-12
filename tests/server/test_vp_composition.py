"""The score window's composition: the VP ledger's ``parts``.

User request 2026-11-08: besides the step-by-step list, show what a seat's
points are made of (The Spice Must Flow 2, Influence 4, Alliances 1, ...).
The ledger splits every seat's change at every step by source
(``vp_ledger.step_parts``). The oracle is the engine's own points: a seat's
parts add up to its change at every step, Influence or an Alliance lost
included, and to its points at the end, with nothing left unexplained.
Victory Points are lost only where Influence drops below 2 or an Alliance
passes on or is lost ([Main pp. 7, 17] [FAQ p. 1]; docs/rules/
immortality.md: "카드·확장 효과에 VP를 잃는 것은 없다").

The games run both boards with every expansion and module in the
combinations the setup allows, one seed each, on the app AI table. Each
game must show the kinds ``SHOWS`` names for it (seed 1's games, 2026-11-08;
re-pick the seed if a change moves one), and together they show every kind
but ``other``, which no game may show.
"""

from collections import Counter
from copy import replace

import pytest

from dune_imperium.content.core.icons import BattleIcon, Faction
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.server.catalog import build_catalog
from dune_imperium.server.session_log import LoggedStep
from dune_imperium.server.sessions import GameSessionManager, JsonObject
from dune_imperium.server.vp_ledger import (
    OPENING_INDEX,
    PART_KINDS,
    VpPart,
    step_parts,
)

APP_TABLE = ("app_ai",) * 4
PART_KEYS = {"index", "seat", "kind", "item", "points"}

# Every board and expansion, in combinations create_game accepts (the
# original board takes Epic only with Rise of Ix, Go to 11 needs
# Immortality, Rise of Ix's tiles alone need the Tech Module).
COMBINATIONS: dict[str, dict[str, object]] = {
    "uprising": {},
    "uprising_all": {
        "choam_module": True,
        "bloodlines": True,
        "tech_module": True,
        "immortality": True,
        "arrakeen_scouts": True,
        "promo_cards": True,
    },
    "uprising_epic_go_to_11": {
        "epic_game": True,
        "go_to_11": True,
        "immortality": True,
    },
    "uprising_ix_all": {
        "rise_of_ix": True,
        "bloodlines": True,
        "tech_module": True,
        "arrakeen_scouts": True,
        "go_to_11": True,
        "immortality": True,
        "choam_module": True,
        "epic_game": True,
    },
    "imperium": {"base_game": "imperium"},
    "imperium_ix": {"base_game": "imperium", "rise_of_ix": True},
    "imperium_ix_all": {
        "base_game": "imperium",
        "rise_of_ix": True,
        "immortality": True,
        "bloodlines": True,
        "tech_module": True,
        "arrakeen_scouts": True,
        "epic_game": True,
        "promo_cards": True,
    },
    "imperium_immortality_bloodlines": {
        "base_game": "imperium",
        "immortality": True,
        "bloodlines": True,
        "tech_module": True,
        "arrakeen_scouts": True,
        "go_to_11": True,
    },
}

# Where an item's id is looked up: a catalog section, or the engine's own
# vocabulary for Factions and battle icons.
_CATALOG_SECTIONS = ("cards", "intrigue", "conflicts", "tech")
_VOCABULARY = {
    "faction": {faction.value for faction in Faction},
    "battle_icon": {icon.value for icon in BattleIcon},
}
_ITEM_SECTIONS = {
    "start": set(),
    "influence": {"faction"},
    "alliance": {"faction"},
    "spice_must_flow": set(),
    "conflict": {"conflicts"},
    "battle_icons": {"battle_icon", "tech"},
    "intrigue": {"intrigue"},
    "card": {"cards"},
    "tleilaxu": set(),
    "tech": {"tech"},
}

# What each game shows besides Influence, Alliances, Conflict rewards and
# The Spice Must Flow, which every one of them shows.
EVERY_GAME = {"influence", "alliance", "conflict", "spice_must_flow"}
# The seat seed of each combination's game, 1 unless named here: seed 1's
# Rise of Ix game moved when Slig Farmer's box became two steps (2026-11-08,
# OQ-027) and no longer scores an Intrigue; seed 2's shows every kind below.
SEEDS: dict[str, int] = {"uprising_ix_all": 2}
SHOWS: dict[str, set[str]] = {
    "uprising": {"start", "battle_icons"},
    "uprising_all": {"start", "battle_icons", "intrigue"},
    "uprising_epic_go_to_11": {"battle_icons", "card", "intrigue", "tleilaxu"},
    "uprising_ix_all": {"battle_icons", "intrigue", "tech", "tleilaxu"},
    "imperium": {"start", "card"},
    "imperium_ix": {"start", "intrigue", "tech"},
    "imperium_ix_all": {"start", "card", "intrigue", "tleilaxu"},
    "imperium_immortality_bloodlines": {"intrigue"},
}


def _parts(payload: JsonObject) -> list[dict[str, object]]:
    parts = payload["parts"]
    assert isinstance(parts, list)
    rows: list[dict[str, object]] = []
    for part in parts:
        assert isinstance(part, dict)
        assert set(part) == PART_KEYS
        rows.append(dict(part))
    return rows


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


@pytest.fixture(scope="module")
def catalog_ids() -> dict[str, set[str]]:
    catalog = build_catalog()
    ids = {name: set(ids) for name, ids in _VOCABULARY.items()}
    for section in _CATALOG_SECTIONS:
        entries = catalog[section]
        assert isinstance(entries, dict)
        ids[section] = set(entries)
    return ids


@pytest.mark.parametrize("name", sorted(COMBINATIONS))
def test_every_seats_parts_add_up_to_its_points(
    name: str, catalog_ids: dict[str, set[str]]
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(
        APP_TABLE,
        game_seed=SEEDS.get(name, 1),
        **COMBINATIONS[name],  # type: ignore[arg-type]
    )
    assert summary["finished"] is True
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    payload = manager.vp_ledger(game_id)
    parts = _parts(payload)

    # At the end: each seat's parts are its points, nothing unexplained.
    totals = [0] * len(session.state.players)
    for part in parts:
        totals[_int(part["seat"])] += _int(part["points"])
        assert part["points"] != 0
        assert part["kind"] in PART_KINDS
        assert part["kind"] != "other", part
    assert totals == [player.victory_points for player in session.state.players]

    # At every step: a seat's parts are its change, a zero change included.
    entries = payload["entries"]
    assert isinstance(entries, list)
    deltas: Counter[tuple[int, int]] = Counter()
    for entry in entries:
        assert isinstance(entry, dict)
        deltas[(_int(entry["index"]), _int(entry["seat"]))] += _int(entry["delta"])
    sums: Counter[tuple[int, int]] = Counter()
    for part in parts:
        sums[(_int(part["index"]), _int(part["seat"]))] += _int(part["points"])
    opening = session.engine.reset(session.config, session.game_seed)
    for seat, player in enumerate(opening.players):
        assert sums.pop((OPENING_INDEX, seat), 0) == player.victory_points
    # A step's parts can cancel out (For Humanity from 2 Influence): such a
    # step has no row, and every row's change is its parts' sum.
    assert {key: points for key, points in sums.items() if points} == dict(deltas)
    live = {
        index
        for index, entry in enumerate(session.log)
        if isinstance(entry, LoggedStep) and not entry.undone
    }
    assert {index for index, _ in sums} <= live

    # The opening is the starting points, 0 with Go to 11.
    start = [part for part in parts if part["kind"] == "start"]
    assert all(part["index"] == OPENING_INDEX for part in start)
    expected = 0 if COMBINATIONS[name].get("go_to_11") else 1
    assert sorted(_int(part["seat"]) for part in start) == (
        [] if expected == 0 else [0, 1, 2, 3]
    )
    assert all(part["points"] == expected for part in start)

    # An item names the catalog entry the screen shows.
    for part in parts:
        item = part["item"]
        allowed = _ITEM_SECTIONS[str(part["kind"])]
        if item is None:
            assert not allowed, part
            continue
        assert isinstance(item, str)
        section, _, item_id = item.partition(":")
        assert section in allowed, part
        assert item_id in catalog_ids[section], part
    assert {str(part["kind"]) for part in parts} >= EVERY_GAME | SHOWS[name]

    # A Conflict reward names the Conflict the engine resolves: the top card
    # in play (rules/combat.py reads ``current_conflict_ids[-1]``). On the
    # original board earlier rounds' cards stay beneath it, "Conflict 카드는
    # 공개한 자리에 남고 다음 라운드의 카드가 그 위에 쌓인다 [DI p. 8]"
    # (docs/rules/imperium-base.md); the first card was once named instead
    # (Codex review 2026-11-08: original board, seed 1, log index 149).
    resolving: dict[int, str | None] = {}
    state = opening
    for index, logged in enumerate(session.log):
        if not isinstance(logged, LoggedStep) or logged.undone:
            continue
        current = state.current_conflict_ids
        resolving[index] = current[-1] if current else None
        state = session.engine.apply(state, logged.step).state
    rewards = [part for part in parts if part["kind"] == "conflict"]
    assert rewards
    misnamed = [
        (part, resolving[_int(part["index"])])
        for part in rewards
        if part["item"] != f"conflicts:{resolving[_int(part['index'])]}"
    ]
    assert not misnamed, misnamed[:3]


def test_the_games_together_show_every_kind_of_source() -> None:
    assert set(SHOWS) == set(COMBINATIONS)
    shown = EVERY_GAME.union(*SHOWS.values())
    assert shown == set(PART_KINDS) - {"other"}


# ---------- one step, by hand ----------


def _opening() -> GameState:
    manager = GameSessionManager()
    summary = manager.create_game(("human",) * 4)
    session = manager._get(str(summary["game_id"]))
    return session.state


def _with(state: GameState, seat: int, **changes: object) -> GameState:
    player = replace(state.players[seat], **changes)
    return replace(state, players=replace_player(state.players, player))


def _event(kind: str, event_id: str, *payload: tuple[str, object]) -> GameEvent:
    return GameEvent(event_id=event_id, kind=kind, payload=payload)  # type: ignore[arg-type]


def _found(parts: tuple[VpPart, ...]) -> list[tuple[int, str, str | None, int]]:
    return [(part.seat, part.kind, part.item, part.points) for part in parts]


def test_for_humanity_scores_a_card_point_and_loses_an_influence_one() -> None:
    """For Humanity: lose an Influence for a Victory Point. From 2 Emperor
    Influence the seat's total does not move, yet the card scored a point
    and the Emperor's point is gone ([For Humanity])."""

    opening = _opening()
    before = _with(opening, 1, influence=Influence(emperor=2), victory_points=2)
    after = _with(opening, 1, influence=Influence(emperor=1), victory_points=2)
    event = _event(
        "reveal_victory_point_gained",
        "round:4:player:1:reveal_card:imperium:for_humanity:0:influence_loss:victory_point",
        ("card_id", "imperium:for_humanity:0"),
        ("player", 1),
        ("victory_points", 1),
    )
    assert _found(step_parts(before, after, (event,), 7)) == [
        (1, "influence", "faction:emperor", -1),
        (1, "card", "cards:for_humanity", 1),
    ]


def test_an_alliance_passing_on_moves_its_point_between_seats() -> None:
    opening = _opening()
    before = _with(
        _with(opening, 0, alliance_faction_ids=("fremen",), victory_points=2),
        2,
        victory_points=1,
    )
    after = _with(
        _with(before, 0, alliance_faction_ids=(), victory_points=1),
        2,
        alliance_faction_ids=("fremen",),
        victory_points=2,
    )
    assert _found(step_parts(before, after, (), 3)) == [
        (0, "alliance", "faction:fremen", -1),
        (2, "alliance", "faction:fremen", 1),
    ]


def test_sources_name_their_card_tile_or_conflict() -> None:
    opening = _opening()
    conflict, *deck = opening.conflict_deck
    before = replace(
        opening, conflict_deck=tuple(deck), current_conflict_ids=(conflict,)
    )
    after = _with(before, 3, victory_points=before.players[3].victory_points + 9)
    events = (
        _event(
            "resources_gained",
            "round:5:player:3:intrigue:intrigue:crysknife:0:resources",
            ("player", 3),
            ("source", "round:5:player:3:intrigue:intrigue:crysknife:0"),
            ("victory_points", 1),
        ),
        _event(
            "resources_gained",
            "round:5:player:3:reveal_card:imperium:opulence:0:solari_vp:resources",
            ("player", 3),
            ("source", "round:5:player:3:reveal_card:imperium:opulence:0:solari_vp"),
            ("victory_points", 1),
        ),
        _event(
            "agent_card_trashed_for_vp",
            "round:5:player:3:agent_card:tleilaxu:ghola:0:victory_point",
            ("card_id", "tleilaxu:ghola:0"),
            ("player", 3),
            ("victory_points", 1),
        ),
        _event(
            "resources_gained",
            "round:5:player:3:endgame_tech:memocorders:resources",
            ("player", 3),
            ("source", "round:5:player:3:endgame_tech:memocorders"),
            ("victory_points", 1),
        ),
        _event(
            "resources_gained",
            "round:5:combat_reward:dreadnought_detonation:0:3:resources",
            ("player", 3),
            ("source", "round:5:combat_reward:dreadnought_detonation:0:3"),
            ("victory_points", 1),
        ),
        _event(
            "combat_reward_icon_resolved",
            "round:5:combat_reward:3:1:icon:0",
            ("effect", "victory_points"),
            ("player", 3),
            ("rank", 1),
            ("victory_points", 1),
        ),
        _event(
            "battle_icons_matched",
            "round:5:conflict_won:ornithopter_match:0",
            ("first_card_id", "objective_crysknife_1"),
            ("player", 3),
            ("second_card_id", "battle_for_imperial_basin"),
        ),
        _event(
            "endgame_wild_matched",
            "round:5:endgame_wild:3:propaganda:siege_of_arrakeen",
            ("matching_card_id", "siege_of_arrakeen"),
            ("player", 3),
            ("wild_card_id", "propaganda"),
        ),
        _event(
            "card_acquired",
            "round:5:player:3:acquire:reserve:the_spice_must_flow:9",
            ("card_id", "the_spice_must_flow"),
            ("player", 3),
        ),
        # Another seat's gain and the winner's total are not seat 3's.
        _event("tleilaxu_advanced", "x", ("player", 0), ("victory_points", 1)),
        _event("game_finished", "y", ("player", 3), ("victory_points", 12)),
    )
    found = _found(step_parts(before, after, events, 9))
    assert found == [
        (0, "tleilaxu", None, 1),
        (0, "other", None, -1),
        (3, "intrigue", "intrigue:crysknife", 1),
        (3, "card", "cards:opulence", 1),
        (3, "card", "cards:ghola", 1),
        (3, "tech", "tech:memocorders", 1),
        (3, "tech", "tech:detonation_devices", 1),
        (3, "conflict", f"conflicts:{conflict}", 1),
        (3, "battle_icons", "tech:ornithopter_fleet", 1),
        (3, "battle_icons", "battle_icon:wild", 1),
        (3, "spice_must_flow", None, 1),
    ]


def test_a_reward_names_the_top_conflict_card_of_a_stack() -> None:
    """On the original board the Conflict cards of earlier rounds stay in
    play under the new one [DI p. 8]; the reward is the top card's
    (rules/combat.py ``current_conflict_ids[-1]``)."""

    opening = _opening()
    first, second, *deck = opening.conflict_deck
    before = replace(
        opening, conflict_deck=tuple(deck), current_conflict_ids=(first, second)
    )
    after = _with(before, 0, victory_points=before.players[0].victory_points + 1)
    event = _event(
        "combat_reward_icon_resolved",
        "round:2:combat_reward:0:1:icon:0",
        ("effect", "victory_points"),
        ("player", 0),
        ("rank", 1),
        ("victory_points", 1),
    )
    assert _found(step_parts(before, after, (event,), 5)) == [
        (0, "conflict", f"conflicts:{second}", 1),
    ]


def test_a_plain_match_names_the_icon_and_a_private_event_names_nothing() -> None:
    opening = _opening()
    after = _with(opening, 2, victory_points=opening.players[2].victory_points + 2)
    events = (
        _event(
            "battle_icons_matched",
            "round:2:battle_icons_matched:2",
            ("first_card_id", "objective_crysknife_1"),
            ("player", 2),
            ("second_card_id", "spice_freighters"),
        ),
        GameEvent(
            event_id="round:2:player:2:intrigue:intrigue:crysknife:0:resources",
            kind="resources_gained",
            payload=(("player", 2), ("victory_points", 1)),
            visible_to=(2,),
        ),
    )
    assert _found(step_parts(opening, after, events, 4)) == [
        (2, "battle_icons", "battle_icon:crysknife", 1),
        (2, "other", None, 1),
    ]
