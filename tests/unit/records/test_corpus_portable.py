"""The record corpus's portable code: fingerprint, trace codec, step keys."""

import ast
import dataclasses
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.records.portable import trace
from dune_imperium.records.portable.trace import (
    ABSENT,
    UNORDERED,
    Fingerprint,
    KeyIndex,
    TraceReader,
    TraceWriter,
    canonical,
    read_traces,
    step_keys,
    trace_header,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.simulation.coverage import normalize_instance_id

PORTABLE = Path(trace.__file__).parent
SRC = PORTABLE.parents[2]
FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)


def _reset(seed: int = 7) -> GameState:
    return UprisingRulesEngine().reset(FULL, seed)


def _imports(path: Path) -> list[tuple[str, int]]:
    """Every imported module of a file, with the import's relative level."""

    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend((alias.name, 0) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.module or "", node.level))
    return found


def test_the_portable_modules_import_only_the_standard_library() -> None:
    files = sorted(PORTABLE.glob("*.py"))
    assert {path.name for path in files} >= {"__init__.py", "trace.py"}
    for path in files:
        for module, level in _imports(path):
            assert level == 0, f"{path.name}: relative import of {module!r}"
            top = module.partition(".")[0]
            assert top in sys.stdlib_module_names, f"{path.name} imports {module}"


def test_every_unordered_zone_is_a_player_field() -> None:
    # records/problems.py once named zones PlayerState does not have, and
    # its comparison skipped them silently.
    fields = {field.name for field in dataclasses.fields(PlayerState)}
    assert set(UNORDERED) <= fields
    assert "deck" not in UNORDERED


def test_the_field_list_splits_players_per_seat() -> None:
    state = _reset()
    names = trace.field_names(state)
    player_fields = [field.name for field in dataclasses.fields(PlayerState)]
    top = [
        field.name
        for field in dataclasses.fields(GameState)
        if field.name not in {"decision_stack", "event_log", "revision", "players"}
    ]
    assert len(names) == len(top) + 4 * len(player_fields)
    assert "players[3].hand" in names and "decision_stack" not in names
    assert len(Fingerprint()(state)) == len(names)


def test_equal_states_give_equal_digests_and_one_change_one_digest() -> None:
    state = _reset()
    first, second = Fingerprint(), Fingerprint()
    assert first(state) == second(_reset())
    names = trace.field_names(state)
    players = list(state.players)
    resources = players[2].resources
    players[2] = replace(
        players[2], resources=replace(resources, spice=resources.spice + 1)
    )
    changed = replace(state, players=tuple(players))
    before, after = first(state), first(changed)
    pairs = enumerate(zip(before, after, strict=True))
    differ = [names[i] for i, (a, b) in pairs if a != b]
    assert differ == ["players[2].resources"]
    # The identity cache does not hide the change from a fresh fingerprint.
    assert Fingerprint()(changed) == after


def test_unordered_zones_ignore_order_and_the_deck_does_not() -> None:
    state = _reset()
    player = state.players[0]
    assert len(player.deck) > 2
    hand, deck = player.deck[:3], player.deck[3:]
    with_hand = replace(
        state, players=(replace(player, hand=hand, deck=deck), *state.players[1:])
    )
    permuted_hand = replace(
        state, players=(replace(player, hand=hand[::-1], deck=deck), *state.players[1:])
    )
    permuted_deck = replace(
        state, players=(replace(player, deck=player.deck[::-1]), *state.players[1:])
    )
    fingerprint = Fingerprint()
    assert fingerprint(with_hand) == fingerprint(permuted_hand)
    assert fingerprint(state) != fingerprint(permuted_deck)


def test_a_class_schema_leaves_out_fields_a_newer_engine_adds() -> None:
    old = dataclasses.make_dataclass("Resources", [("solari", int), ("spice", int)])
    new = dataclasses.make_dataclass(
        "Resources", [("solari", int), ("spice", int), ("owed", int)]
    )
    seen: dict[str, list[str]] = {}
    old_form = canonical(old(1, 2), seen=seen)
    assert seen == {"Resources": ["solari", "spice"]}
    assert canonical(new(1, 2, 9)) != old_form
    assert canonical(new(1, 2, 9), schema=seen) == old_form


def test_a_missing_field_digests_as_absent() -> None:
    state = _reset()
    fingerprint = Fingerprint(
        names=("round_number", "no_such_field", "players[0].no_such", "players[9].hand")
    )
    digests = fingerprint(state)
    assert digests[0] != ABSENT
    assert digests[1:] == (ABSENT, ABSENT, ABSENT)


def test_fingerprints_are_the_same_in_another_process() -> None:
    code = (
        "from dune_imperium.config import RulesetConfig\n"
        "from dune_imperium.records.portable.trace import Fingerprint\n"
        "from dune_imperium.rules import UprisingRulesEngine\n"
        f"config = RulesetConfig(**{_flags(FULL)!r})\n"
        "state = UprisingRulesEngine().reset(config, 7)\n"
        "print(b''.join(Fingerprint()(state)).hex())\n"
    )
    expected = b"".join(Fingerprint()(_reset())).hex()
    for hash_seed in ("1", "2"):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": hash_seed,
            "PYTHONPATH": os.pathsep.join(
                [str(SRC), *filter(None, [os.environ.get("PYTHONPATH")])]
            ),
        }
        output = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env=environment,
        ).stdout.strip()
        assert output == expected


def _flags(config: RulesetConfig) -> dict[str, Any]:
    """The config's fields as literals (the base game by its string)."""

    return {
        field.name: (
            value.value if isinstance(value, BaseGame) else value
        )
        for field in dataclasses.fields(config)
        for value in (getattr(config, field.name),)
    }


def test_the_trace_codec_round_trips() -> None:
    fields = 300
    reset = tuple(bytes([i % 256, i // 256, 0, 0]) for i in range(fields))
    writer = TraceWriter(reset)
    vectors = [reset]
    current = list(reset)
    # One step changes nothing, one changes 200 fields (a two-byte varint).
    for step, changed in enumerate(([], [5], list(range(200)), [0, fields - 1])):
        for index in changed:
            current[index] = bytes([step, index % 256, 1, 1])
        assert writer.step(current) == len(changed)
        vectors.append(tuple(current))
    blob = trace_header(fields) + writer.to_bytes() + TraceWriter(reset).to_bytes()
    first, empty = read_traces(blob)
    assert first.steps == 4 and empty.steps == 0
    assert [first.before(i) for i in range(5)] == vectors
    assert first.before(1) == reset  # reading backwards restarts
    assert first.final() == vectors[-1]
    assert list(first.vectors()) == vectors
    assert first.delta(1) == ((5, bytes([1, 5, 1, 1])),)
    assert empty.final() == reset
    with pytest.raises(IndexError):
        first.before(5)


def test_a_damaged_trace_is_refused() -> None:
    writer = TraceWriter((b"abcd",))
    writer.step((b"abce",))
    payload = writer.to_bytes()[4:]
    with pytest.raises(ValueError, match="trailing"):
        TraceReader(payload + b"\0", 1)
    with pytest.raises(ValueError, match="not a record-corpus trace"):
        read_traces(b"XXXXX" + payload)


def _frame(kind: str, **context: object) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, context=tuple(sorted(context.items())))


def _seat(**zones: tuple[str, ...]) -> SimpleNamespace:
    empty: dict[str, tuple[str, ...]] = {
        "deck": (),
        "hand": (),
        "discard_pile": (),
        "in_play": (),
        "intrigue_cards": (),
    }
    return SimpleNamespace(**{**empty, **zones})


def _state(
    *seats: SimpleNamespace, frames: tuple[SimpleNamespace, ...] = (), **rest: object
) -> SimpleNamespace:
    zones: dict[str, object] = {"intrigue_deck": (), "intrigue_discard": ()}
    return SimpleNamespace(players=seats, decision_stack=frames, **{**zones, **rest})


def _keys(
    before: SimpleNamespace,
    step: object,
    after: SimpleNamespace | None = None,
    legal: tuple[DomainAction, ...] = (),
    events: tuple[str | GameEvent, ...] = (),
) -> list[str]:
    transition = SimpleNamespace(
        state=after if after is not None else before,
        events=tuple(
            SimpleNamespace(kind=event) if isinstance(event, str) else event
            for event in events
        ),
    )
    return step_keys(before, step, transition, legal, normalize=normalize_instance_id)


def test_step_keys_name_the_frame_the_offer_and_the_forced_bucket() -> None:
    frame = _frame(
        "agent_effects",
        card_id="imperium:spice_hunt:2",
        player=1,
        round=3,
        space_id="arrakeen",
    )
    before = _state(_seat(), frames=(frame,))
    legal = (
        DomainAction("pass", 1),
        DomainAction("resolve", 1, (("x", 1),)),
        DomainAction("resolve", 1, (("x", 2),)),
    )
    keys = _keys(before, legal[0], legal=legal, events=("passed", "passed"))
    assert keys == [
        "action_ids:pass",
        "frames:agent_effects",
        "frames:agent_effects@card_id=spice_hunt",
        "frames:agent_effects@space_id=arrakeen",
        "offered:pass",
        "offered:resolve",
        "forced:agent_effects:3+",
        "events:passed",
        "events:passed",
    ]
    assert "forced:agent_effects:1" in _keys(before, legal[0], legal=legal[:1])


def test_step_keys_count_an_agent_turn_as_the_census_does() -> None:
    step = DomainAction(
        "agent_turn",
        0,
        (
            ("card_id", "player:0:starter:dagger:1"),
            ("cost_option", 1),
            ("space_id", "sietch_tabr"),
        ),
    )
    keys = _keys(_state(_seat()), step)
    assert "agent_placements:sietch_tabr:1" in keys
    assert "cards_played:dagger" in keys


def test_step_keys_count_a_space_pick_with_the_card_picked_before_it() -> None:
    # Stage B1 (OQ-111): the Agent turn is a card pick and then a space pick;
    # the card waits in the turn frame, so the space pick counts it.
    before = _state(
        _seat(),
        frames=(_frame("turn", agent_card_pick="player:0:starter:dagger:1"),),
    )
    step = DomainAction(
        "place_agent", 0, (("cost_option", 1), ("space_id", "sietch_tabr"))
    )
    keys = _keys(before, step)
    assert "action_ids:place_agent" in keys
    assert "agent_placements:sietch_tabr:1" in keys
    assert "cards_played:dagger" in keys
    pick = DomainAction(
        "choose_agent_card", 0, (("card_id", "player:0:starter:dagger:1"),)
    )
    assert "action_ids:choose_agent_card" in _keys(_state(_seat()), pick)


def test_draws_are_state_deltas_inside_another_step() -> None:
    step = DomainAction("resolve_board_effect", 0)
    before = _state(_seat(deck=("a", "b", "c")), _seat())
    shrank = _state(_seat(deck=("c",), hand=("a", "b")), _seat())
    assert "draws:card@resolve_board_effect" in _keys(before, step, shrank)
    # A reshuffle: the deck grows from the discard while the hand grows.
    before = _state(_seat(), _seat(deck=(), discard_pile=("a", "b", "c")))
    reshuffled = _state(_seat(), _seat(deck=("b", "c"), hand=("a",)))
    assert "draws:card@resolve_board_effect" in _keys(before, step, reshuffled)
    # Intrigue: the deck shrank, or a seat's cards grew from the discard.
    before = _state(_seat(), intrigue_deck=("i1", "i2"))
    after = _state(_seat(intrigue_cards=("i1",)), intrigue_deck=("i2",))
    assert "draws:intrigue@resolve_board_effect" in _keys(before, step, after)
    before = _state(_seat(), intrigue_discard=("i1", "i2"))
    after = _state(_seat(intrigue_cards=("i1", "i2")))
    assert "draws:intrigue@resolve_board_effect" in _keys(before, step, after)
    # Nothing moved: no draw; a chance step's draw names its family.
    assert not [key for key in _keys(before, step) if key.startswith("draws:")]
    chance = ChanceOutcome("round:2:player:1:discard_shuffle", ("a", "b"))
    before = _state(_seat(discard_pile=("a", "b")))
    after = _state(_seat(deck=("b",), hand=("a",)))
    assert "draws:card@chance:round:player:discard_shuffle" in _keys(
        before, chance, after
    )


def _draws(before: SimpleNamespace, after: SimpleNamespace) -> list[str]:
    step = DomainAction("resolve_board_effect", 0)
    return [key for key in _keys(before, step, after) if key.startswith("draws:")]


def test_a_draw_in_the_reveal_turn_goes_straight_to_in_play() -> None:
    # card_draw._draw_available reveals a card drawn in its owner's Reveal
    # turn at once (reveal_late_arrivals): the hand never grows. Here the
    # draw also reshuffles the discard pile into the deck (full.h4.9's
    # round:10:player:1:tech_draw:discard_shuffle).
    played = tuple(f"p{index}" for index in range(6))
    discard = tuple(f"d{index}" for index in range(19))
    before = _state(_seat(in_play=played, discard_pile=discard))
    after = _state(_seat(in_play=(*played, "d0"), deck=discard[1:]))
    chance = ChanceOutcome("round:10:player:1:tech_draw:discard_shuffle", discard)
    assert "draws:card@chance:round:player:tech_draw:discard_shuffle" in _keys(
        before, chance, after
    )
    # Without a reshuffle: the deck shrinks into in_play.
    before = _state(_seat(in_play=played, deck=("a", "b")))
    after = _state(_seat(in_play=(*played, "a"), deck=("b",)))
    assert _draws(before, after) == ["draws:card@resolve_board_effect"]


def test_a_draw_beside_a_discard_or_a_played_card_still_counts() -> None:
    # Discard a hand card, then draw one, in one step: the hand keeps its
    # size and the deck and discard pile together keep theirs.
    before = _state(_seat(hand=("h",), deck=("a", "b")))
    after = _state(_seat(hand=("a",), deck=("b",), discard_pile=("h",)))
    assert _draws(before, after) == ["draws:card@resolve_board_effect"]
    # A public hand card played while another is drawn (hand_public is part
    # of hand, so it is not counted twice).
    before = _state(_seat(hand=("h",), hand_public=("h",), deck=("a",)))
    after = _state(_seat(hand=("a",), in_play=("h",)))
    assert _draws(before, after) == ["draws:card@resolve_board_effect"]
    # Cards moving between hand, play and discard are no draw.
    before = _state(_seat(hand=("h", "i"), deck=("a",)))
    after = _state(_seat(hand=("i",), in_play=("h",), deck=("a",)))
    assert _draws(before, after) == []
    after = _state(_seat(in_play=("h",), deck=("a",), discard_pile=("i",)))
    assert _draws(before, after) == []


def test_chance_values_skip_deck_orders_and_pauses() -> None:
    state = _state(_seat())
    shuffle = ChanceOutcome("round:2:player:1:discard_shuffle", ("x:1", "y:2"))
    pause = ChanceOutcome("round:2:conflict_end:pause", ("continue",))
    event = ChanceOutcome("round:4:scouts:event", ("choam_bargain#5",))
    steal = ChanceOutcome(
        "round:3:player:0:board:secrets:steal", ("intrigue:ambush:1",)
    )
    assert _keys(state, shuffle) == ["chance_kinds:round:player:discard_shuffle"]
    assert _keys(state, pause) == ["chance_kinds:round:conflict_end:pause"]
    # Every whole-pile permutation, whatever pile it orders.
    contracts = ChanceOutcome(
        "round:scouts:contract_shuffle", tuple(f"contract_{i}" for i in range(22))
    )
    intrigue = ChanceOutcome(
        "round:3:player:0:board:secrets:intrigue_shuffle", ("intrigue:ambush:1",)
    )
    assert _keys(state, contracts) == ["chance_kinds:round:scouts:contract_shuffle"]
    assert _keys(state, intrigue) == [
        "chance_kinds:round:player:board:secrets:intrigue_shuffle"
    ]
    assert _keys(state, event) == [
        "chance_kinds:round:scouts:event",
        "chance_values:round:scouts:event=choam_bargain",
    ]
    assert "chance_values:round:player:board:secrets:steal=ambush" in _keys(
        state, steal
    )


def test_positions_are_kept_in_full_only_where_the_schema_says() -> None:
    index = KeyIndex()
    for step in range(20):
        keys = ["offered:many", "draws:card@x"]
        if step < 16:
            keys.append("offered:few")
        index.add(step, keys)
    index.add(20, ["cards_played:dagger"])
    row = index.row_keys(
        {"cards_played": {"dagger": 2}, "event_kinds": {"k": 3}},
        ["leader_a", "leader_a"],
    )
    assert row["offered:many"] == [20, 0]
    assert row["offered:few"] == [16, 0, list(range(16))]
    assert row["draws:card@x"] == [20, 0, list(range(20))]
    # The steps count every card play, the event-derived ones too, so the
    # census's step dimensions are left to them.
    assert row["cards_played:dagger"] == [1, 20, [20]]
    assert row["event_kinds:k"] == [3]
    assert row["leaders:leader_a"] == [2]
    assert list(row) == sorted(row)
    assert trace.census_of(row) == {
        "cards_played": {"dagger": 1},
        "event_kinds": {"k": 3},
    }


def test_a_card_played_by_an_event_counts_at_its_step() -> None:
    # collect_game_coverage counts these two events' cards as played cards
    # from the event log; the keys count them at the step that reported
    # them, so the key has its first step and positions.
    revealed = GameEvent(
        "x:late_reveal",
        "personal_card_late_revealed",
        (("card_id", "imperium:spice_hunt:2"), ("player", 1)),
    )
    grafted = GameEvent(
        "round:4:player:0:graft:tleilaxu:clandestine_meeting:1",
        "card_grafted",
        (("card_id", "tleilaxu:clandestine_meeting:1"), ("player", 0)),
    )
    step = DomainAction("resolve_board_effect", 0)
    state = _state(_seat())
    keys = _keys(state, step, events=(revealed, grafted, "agent_placed"))
    assert keys == [
        "action_ids:resolve_board_effect",
        "events:personal_card_late_revealed",
        "cards_played:spice_hunt",
        "events:card_grafted",
        "cards_played:clandestine_meeting",
        "events:agent_placed",
    ]
    index = KeyIndex()
    index.add(0, ["action_ids:agent_turn", "cards_played:dagger"])
    index.add(7, keys)
    row = index.row_keys({"cards_played": {"spice_hunt": 1, "clandestine_meeting": 1}})
    assert row["cards_played:spice_hunt"] == [1, 7, [7]]
    assert row["cards_played:clandestine_meeting"] == [1, 7, [7]]
