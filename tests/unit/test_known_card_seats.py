"""Who can identify which card: ``known_card_seats`` against the table.

``known_card_seats`` is the one list the server reads to redact the live log,
to decide which steps an undo may take back (OQ-010: information that left a
hidden pile cannot be taken back) and, through the sweep, which public events
would leak. A hidden zone missing from it is public to the server: on
2026-09-24 a human bought from the Tleilaxu Row, took the purchase back and
had seen the Tleilaxu deck's next card, because the deck was not listed.
"""

import dataclasses
import random
from collections.abc import Iterable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GameState, PlayerState
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.observation import known_card_seats, observe_state
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind

EVERY_MODULE = RulesetConfig(
    choam_module=True, bloodlines=True, tech_module=True, immortality=True
)


def _state() -> GameState:
    players = tuple(
        PlayerState(player_id=seat, deck=(f"p{seat}:a", f"p{seat}:b", f"p{seat}:c"))
        for seat in range(4)
    )
    return GameState(config=EVERY_MODULE, seed=3, players=players)


def _frame(kind: FrameKind, owner: int, **context: ActionValue) -> DecisionFrame:
    return DecisionFrame(
        kind=kind,
        frame_id=f"test:{kind}",
        decision=PlayerDecision(owner=owner, prompt="test"),
        context=tuple(sorted(context.items())),
    )


def test_the_expansions_face_down_stacks_are_known_to_nobody() -> None:
    state = replace(
        _state(),
        tleilaxu_deck=("tleilaxu:a", "tleilaxu:b"),
        tleilaxu_row=("tleilaxu:row",),
        skill_stack=("skill:a", "skill:b"),
        skill_face_up=("skill:up",),
        tech_stacks=(("tech:top", "tech:under", "tech:bottom"), ("tech:only",)),
        unused_conflict_ids=("conflict_unused",),
    )
    known = known_card_seats(state)

    for hidden in (
        "tleilaxu:a",
        "tleilaxu:b",
        "skill:a",
        "skill:b",
        "tech:under",
        "tech:bottom",
        "conflict_unused",
    ):
        assert known[hidden] == frozenset(), hidden
    # Face up: the Tleilaxu Row, the four Skills and each stack's top tile.
    for public in ("tleilaxu:row", "skill:up", "tech:top", "tech:only"):
        assert public not in known, public


def test_a_secret_project_tile_is_its_owners_alone() -> None:
    players = list(_state().players)
    players[2] = replace(players[2], secret_project_tech_id="tech:secret")
    state = replace(_state(), players=tuple(players))

    assert known_card_seats(state)["tech:secret"] == frozenset({2})


def test_a_peeked_deck_top_is_known_to_its_owner() -> None:
    # Controlled shows the top card while its choice is up; Glowglobes lets
    # its owner look at the top card at any time [Glowglobes Tech tile].
    controlled = replace(
        _state(),
        decision_stack=(
            _frame(FrameKind.INTRIGUE_CHOICE, 1, card_id="x", peeked_card_id="p1:a"),
        )
    )
    known = known_card_seats(controlled)
    assert known["p1:a"] == frozenset({1})
    assert known["p1:b"] == frozenset()

    players = list(_state().players)
    players[3] = replace(players[3], tech_ids=("glowglobes",))
    glowglobes = known_card_seats(replace(_state(), players=tuple(players)))
    assert glowglobes["p3:a"] == frozenset({3})
    assert glowglobes["p3:b"] == frozenset()


def test_long_live_the_fighters_shows_its_owner_the_top_three() -> None:
    state = replace(_state(), decision_stack=(_frame(FrameKind.LONG_LIVE_FIGHTERS, 0),))
    known = known_card_seats(state)

    assert [known[card] for card in ("p0:a", "p0:b", "p0:c")] == [frozenset({0})] * 3
    assert known["p1:a"] == frozenset()


def test_kota_odax_sees_the_bottom_tiles_while_choosing() -> None:
    state = replace(
        _state(),
        tech_stacks=(("tech:top", "tech:bottom"), ("tech:top2", "tech:bottom2")),
        decision_stack=(
            _frame(
                FrameKind.TECH_SECRET_PROJECT,
                2,
                candidates="tech:bottom,tech:bottom2",
            ),
        ),
    )
    known = known_card_seats(state)

    assert known["tech:bottom"] == known["tech:bottom2"] == frozenset({2})


def test_the_contracts_coercive_negotiation_reveals_are_public_while_it_chooses() -> (
    None
):
    # "Reveal three contracts from the bank. Take one and trash the other
    # two." [Coercive Negotiation card]; a revealed card is shown "to your
    # opponents" [Main p. 7]. All three are face up to the whole table while
    # the owner chooses, including the Immediate it cannot take without an
    # Intrigue card to trash [Bloodlines p. 2]. known_card_seats used to give
    # them to the owner alone while nothing showed the untakeable Immediate
    # to anyone (the seat saw only its take actions).
    bank = (
        "contract:bloodlines_immediate",
        "contract:arrakeen_i",
        "contract:arrakeen_ii",
        "contract:secrets",
    )
    card = "intrigue:coercive_negotiation:0"
    players = list(_state().players)
    players[0] = replace(players[0], intrigue_faceup=(card,))
    state = replace(
        _state(),
        players=tuple(players),
        phase=GamePhase.PLAYER_TURNS,
        contract_bank=bank,
        decision_stack=(
            _frame(FrameKind.INTRIGUE_TRIGGER_CONTRACT, 0, card_id=card, turn_owner=0),
        ),
    )
    known = known_card_seats(state)

    for revealed in bank[:3]:
        assert revealed not in known, revealed
    assert known["contract:secrets"] == frozenset()
    for seat in range(4):
        assert observe_state(state, seat).revealed_contract_ids == bank[:3]
    assert list(_mismatches(UprisingRulesEngine(), state, {})) == []


# ---------------------------------------------------------------------------
# The whole table: every card of random games against what each seat is shown.


def _strings(value: object, out: set[str]) -> None:
    if isinstance(value, str):
        if value:
            out.add(value)
    elif isinstance(value, tuple | list | frozenset | set):
        for item in value:
            _strings(item, out)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            _strings(getattr(value, field.name), out)


def _zones(state: GameState) -> dict[str, frozenset[str]]:
    """Every string of the state's zones, with the zones (seat-qualified) holding it."""

    where: dict[str, set[str]] = {}

    def add(zone: str, value: object) -> None:
        found: set[str] = set()
        _strings(value, found)
        for card in found:
            where.setdefault(card, set()).add(zone)

    for field in dataclasses.fields(state):
        if field.name not in _NOT_ZONES:
            add(field.name, getattr(state, field.name))
    for player in state.players:
        for field in dataclasses.fields(player):
            if field.name not in _NOT_PLAYER_ZONES:
                zone = f"player{player.player_id}.{field.name}"
                add(zone, getattr(player, field.name))
    return {card: frozenset(zones) for card, zones in where.items()}


# Fields whose strings name no card: bookkeeping, effect sources, factions
# and spaces.
_NOT_ZONES = frozenset(
    {
        "decision_stack",
        "event_log",
        "config",
        "players",
        "pending_intrigue_draws",
        "pending_skill_choices",
        "pending_navigation_plays",
        "pending_track_spies",
    }
)
_NOT_PLAYER_ZONES = frozenset(
    {
        "leader_id",
        "leader_face_id",
        "feyd_track_space",
        "granted_agent_icon_turn",
        "navigation_trigger_faction",
        "research_space",
    }
)


def _shown_to_seats(
    engine: UprisingRulesEngine,
    state: GameState,
    zones: dict[str, frozenset[str]],
    memory: dict[tuple[str, int], dict[str, frozenset[str]]],
) -> dict[int, set[str]]:
    """What each seat is shown: its view, and the choices put to it.

    A card an open choice has named stays known to that seat while it sits
    where it was named (Long Live the Fighters' drawn card is no longer
    offered for the discard, but its owner has seen it).
    """

    decision = engine.current_decision(state)
    top = state.decision_stack[-1] if state.decision_stack else None
    shown: dict[int, set[str]] = {}
    for seat in range(state.config.players):
        seen: set[str] = set()
        _strings(observe_state(state, seat), seen)
        if isinstance(decision, PlayerDecision) and decision.owner == seat:
            offered: set[str] = set()
            for action in engine.legal_actions(state, seat):
                _strings(tuple(value for _, value in action.arguments), offered)
            if top is not None:
                named = memory.setdefault((top.frame_id, seat), {})
                for card in offered:
                    named[card] = zones.get(card, frozenset())
                offered |= {
                    card
                    for card, zone in named.items()
                    if zones.get(card, frozenset()) == zone
                }
            seen |= offered
        shown[seat] = seen
    return shown


def _mismatches(
    engine: UprisingRulesEngine,
    state: GameState,
    memory: dict[tuple[str, int], dict[str, frozenset[str]]],
) -> Iterable[str]:
    seats = frozenset(range(state.config.players))
    zones = _zones(state)
    shown = _shown_to_seats(engine, state, zones, memory)
    known = known_card_seats(state)
    for card, zone in zones.items():
        seeing = frozenset(seat for seat in seats if card in shown[seat])
        claimed = known.get(card, seats)
        if seeing != claimed:
            yield (
                f"{card!r} in {sorted(zone)}: shown to {sorted(seeing)}, "
                f"known_card_seats says {sorted(claimed)}"
            )


@pytest.mark.parametrize(
    ("config", "seed"),
    [
        (RulesetConfig(choam_module=True, leader_draft=True), 1),
        (RulesetConfig(bloodlines=True, tech_module=True, choam_module=True), 2),
        (
            RulesetConfig(
                choam_module=True,
                bloodlines=True,
                tech_module=True,
                immortality=True,
                promo_cards=True,
                leader_draft=True,
            ),
            0,
        ),
    ],
)
def test_known_card_seats_matches_what_each_seat_is_shown(
    config: RulesetConfig, seed: int
) -> None:
    # Every state of a random game: a card's knowers are exactly the seats
    # whose view or pending choices name it. A seat left out would let an
    # undo take back a step that showed it the card; a seat added would hide
    # that step's reveal the same way.
    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    memory: dict[tuple[str, int], dict[str, frozenset[str]]] = {}
    problems: list[str] = []
    for _ in range(20_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        problems.extend(_mismatches(engine, state, memory))
        actions = engine.legal_actions(state, decision.owner)
        state = engine.apply(state, rng.choice(actions)).state
    assert state.phase is GamePhase.FINISHED
    assert problems == [], problems[:5]
