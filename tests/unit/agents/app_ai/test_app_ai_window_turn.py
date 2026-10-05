"""The ``turn`` window (windows/turn.py): the app's ``DetermineTurn`` prompt.

Each test reaches a real TURN decision (``app_ai.testing``), adjusts the
fields the answer depends on and asserts the exact action. Where a test is
about the window's wiring rather than a value, ``AgentAbility.evaluate`` is
stubbed with a table; ``intrigue_play_sources`` (windows/intrigue.py, ported
elsewhere) is always stubbed.
"""

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import pytest

import dune_imperium.agents.app_ai.agent as agent_module
from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import board as b
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import card_entity, post_entity, space_entity
from dune_imperium.agents.app_ai.context import AppContext, Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import turn
from dune_imperium.agents.app_ai.windows.common import Source, Stage, str_arg
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.content.uprising.board import BOARD_SPACES
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

RS_SIETCH = "arrakis-research-station-sietch-tabr"
RS_REFINERY = "arrakis-research-station-spice-refinery"
REFINERY_ARRAKEEN = "arrakis-spice-refinery-arrakeen"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, ...]]:
    """Stub the shared Plot sources (another agent ports them)."""

    calls: list[tuple[object, ...]] = []

    def sources(
        run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
    ) -> list[Source]:
        calls.append((tuple(actions), combat))
        return []

    monkeypatch.setattr(turn, "intrigue_play_sources", sources)
    return calls


def _owner(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _run(
    state: GameState,
    legal: Sequence[DomainAction] | None = None,
    *,
    rng_seed: int = 0,
) -> DecisionRun:
    seat = _owner(state)
    view = ENGINE.observe(state, seat)
    ctx = AppContext(state, seat, view)
    rng = random.Random(rng_seed)
    actions = tuple(ENGINE.legal_actions(state, seat) if legal is None else legal)
    return DecisionRun(ctx, Profile(ctx, TABLES[2], rng), actions, rng, Memory())


def _turn_state(*, choam: bool = True, seed: int = 1) -> tuple[GameState, int]:
    state = first_decision("turn", choam=choam, seed=seed)
    return state, _owner(state)


def _starter(seat: int, card: str, copy: int = 0) -> str:
    return f"player:{seat}:starter:{card}:{copy}"


def _stub_agent_values(
    monkeypatch: pytest.MonkeyPatch,
    table: Callable[[str, list[str]], tuple[float, str | None]],
) -> list[tuple[str, list[str]]]:
    """Replace ``AgentAbility.evaluate``: ``table(card, spaces)`` -> (value,
    space or None). Records every call's card and offered spaces."""

    calls: list[tuple[str, list[str]]] = []

    def evaluate(self: g.AgentAbility, p: Profile, request: Request) -> Answer:
        spaces = [entity.ref for entity in request.infos[0].entities]
        calls.append((self.owner.ref, spaces))
        value, space = table(self.owner.ref, spaces)
        return Answer(value, None if space is None else ((space,),))

    monkeypatch.setattr(g.AgentAbility, "evaluate", evaluate)
    return calls


def _only(card: str, space: str, value: float = 5.0) -> Callable[..., Any]:
    """A table where ``card`` is worth ``value`` at ``space``, others 0.1."""

    def table(ref: str, spaces: list[str]) -> tuple[float, str | None]:
        if ref == card:
            return value, space
        return 0.1, spaces[0]

    return table


def _args(action: DomainAction | None) -> dict[str, object]:
    assert action is not None
    return dict(action.arguments)


# ---------------------------------------------------------------------------
# Registration and the app's space order
# ---------------------------------------------------------------------------


def test_turn_handler_is_registered() -> None:
    assert turn.HANDLERS == {"turn": turn.turn_window}


#: ``Board.children`` order without CHOAM: the typedef order of the space
#: archetypes in ``dump/worm-canis.dll.cs`` (Uprising namespace 624-644, then
#: BaseSet Arrakeen 650, Imperial Basin 659, Secrets 663).
TYPEDEF_ORDER = (
    "accept_contract",
    "assembly_hall",
    "deep_desert",
    "deliver_supplies",
    "desert_tactics",
    "dutiful_service",
    "espionage",
    "fremkit",
    "gather_support",
    "hagga_basin",
    "heighliner",
    "high_council",
    "imperial_privilege",
    "research_station",
    "sardaukar",
    "shipping",
    "sietch_tabr",
    "spice_refinery",
    "swordmaster",
    "arrakeen",
    "imperial_basin",
    "secrets",
)


def test_board_space_order_follows_the_archetype_typedef_order() -> None:
    assert turn.board_space_order(Board(False)) == TYPEDEF_ORDER
    # CHOAM: the board set loses the two replaced ``…UP`` spaces and the
    # CHOAMModule spaces are appended in typedef order (624 before 630).
    choam = turn.board_space_order(Board(True))
    assert choam == (
        *(s for s in TYPEDEF_ORDER if s not in ("accept_contract", "dutiful_service")),
        "accept_contract",
        "dutiful_service",
    )
    # Every engine space with an app archetype is there, Tuek's Sietch is not.
    ours = {s.space_id for s in BOARD_SPACES} - {"tuek_sietch"}
    assert set(choam) == set(TYPEDEF_ORDER) == ours


def test_space_archetype_order_covers_every_dealt_space_archetype() -> None:
    dealt = {
        a
        for a, arch in ARCHETYPES.items()
        if a.startswith("SpaceArchetypes.")
        and (arch.in_uprising or arch.in_uprising_choam)
    }
    dealt.add("SpaceArchetypes.Immortality.ResearchStationImmortality")
    listed = turn._SPACE_ARCHETYPE_ORDER
    assert len(set(listed)) == len(listed)
    assert set(listed) == dealt
    assert set(turn._SPACE_OF_ARCHETYPE) == dealt


@pytest.mark.parametrize("choam", [False, True])
def test_immortality_moves_research_station_after_the_board_set(choam: bool) -> None:
    """``ResearchStationImmortality`` (typeIndex 649, set ``Immortality``) is
    appended with the other expansion spaces, after the CHOAM ones (624, 630);
    ``ResearchStationUP`` is removed (spec immortality.md §1.1)."""

    without = turn.board_space_order(Board(choam))
    order = turn.board_space_order(Board(choam, immortality=True))
    assert order == (
        *(s for s in without if s != "research_station"),
        "research_station",
    )


@pytest.mark.parametrize("choam", [False, True])
def test_card_spaces_follow_board_order(
    monkeypatch: pytest.MonkeyPatch, choam: bool
) -> None:
    state, seat = _turn_state(choam=choam)
    diplomacy, dune = (
        _starter(seat, "diplomacy"),
        _starter(seat, "dune_the_desert_planet"),
    )
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        hand=(diplomacy, dune),
        deck=tuple(c for c in (*me.deck, *me.hand) if c not in (diplomacy, dune)),
        resources=Resources(solari=10, spice=10, water=5),
    )
    calls = _stub_agent_values(monkeypatch, lambda ref, spaces: (1.0, spaces[0]))
    run = _run(state)
    turn.turn_window(run)
    offered = dict(calls)
    order = turn.board_space_order(Board(choam))
    for card in (diplomacy, dune):
        legal = {
            str_arg(a, "space_id")
            for a in run.by_id("agent_turn")
            if str_arg(a, "card_id") == card
        }
        assert offered[card] == [s for s in order if s in legal]
    expected_diplomacy = [
        "deliver_supplies",
        "desert_tactics",
        "espionage",
        "fremkit",
        "heighliner",
        "sardaukar",
        "secrets",
    ]
    expected_dune = ["deep_desert", "hagga_basin", "imperial_basin"]
    if choam:
        expected_diplomacy.append("dutiful_service")
        expected_dune.append("accept_contract")
    else:
        expected_diplomacy.insert(2, "dutiful_service")
        expected_dune.insert(0, "accept_contract")
    assert offered[diplomacy] == expected_diplomacy
    assert offered[dune] == expected_dune


# ---------------------------------------------------------------------------
# The prompt: placements, Plots, the empty answer
# ---------------------------------------------------------------------------


def test_real_values_pick_the_best_card_and_space() -> None:
    state = play_until(
        lambda s, owner: s.decision_stack[-1].kind == "turn" and s.round_number >= 3,
        seed=2,
    )
    run = _run(state)
    # Independent replay of AgentAbility::Evaluate per hand card.
    profile = _run(state).profile
    best: list[tuple[float, str, str]] = []
    cards = dict.fromkeys(str_arg(a, "card_id") for a in run.by_id("agent_turn"))
    for card in cards:
        assert card is not None
        legal = {
            str_arg(a, "space_id")
            for a in run.by_id("agent_turn")
            if str_arg(a, "card_id") == card
        }
        spaces = tuple(
            space_entity(s, Board(True))
            for s in turn.board_space_order(Board(True))
            if s in legal
        )
        ability = next(
            a
            for a in abilities_of(card_entity(card, run.ctx.seat))
            if isinstance(a, g.AgentAbility)
        )
        answer = ability.evaluate(
            profile, Request(infos=(TargetInfo(entities=spaces),))
        )
        assert answer.response is not None
        best.append((answer.value, card, str(answer.response[0][0])))
    best.sort(reverse=True)
    assert best[0][0] > best[1][0] > 0.0  # a unique best placement
    chosen = turn.turn_window(run)
    assert chosen is not None and chosen.action_id == "agent_turn"
    assert _args(chosen) == {"card_id": best[0][1], "space_id": best[0][2]}


@pytest.mark.parametrize("value", [0.0, -2.5])
def test_no_positive_placement_reveals(
    monkeypatch: pytest.MonkeyPatch, value: float
) -> None:
    state, _ = _turn_state()
    _stub_agent_values(monkeypatch, lambda ref, spaces: (value, spaces[0]))
    chosen = turn.turn_window(_run(state))
    assert chosen is not None and chosen.action_id == "reveal_turn"


def test_answer_space_names_the_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _turn_state()
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "assembly_hall"))
    assert _args(turn.turn_window(_run(state))) == {
        "card_id": dagger,
        "space_id": "assembly_hall",
    }


def test_card_without_a_runnable_space_is_no_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AgentAbility::Evaluate with no stored space answers (0.0, no space).
    state, seat = _turn_state()
    recon = _starter(seat, "reconnaissance")

    def table(ref: str, spaces: list[str]) -> tuple[float, str | None]:
        return (0.0, None) if ref != recon else (0.5, "arrakeen")

    _stub_agent_values(monkeypatch, table)
    assert _args(turn.turn_window(_run(state))) == {
        "card_id": recon,
        "space_id": "arrakeen",
    }


def test_best_key_without_a_space_answers_reveal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # MakeChoice (02 §2) picks the best key before GetResponse: a best key
    # with no space gives the empty answer, not the next-best card.
    state, seat = _turn_state()
    recon = _starter(seat, "reconnaissance")

    def table(ref: str, spaces: list[str]) -> tuple[float, str | None]:
        return (9.0, None) if ref != recon else (0.5, "arrakeen")

    _stub_agent_values(monkeypatch, table)
    chosen = turn.turn_window(_run(state))
    assert chosen is not None and chosen.action_id == "reveal_turn"


@pytest.mark.parametrize("choam", [False, True])
def test_space_tie_inside_a_card_goes_to_the_earlier_board_space(
    monkeypatch: pytest.MonkeyPatch, choam: bool
) -> None:
    # The real AgentAbility::Evaluate keeps the first strictly-best space: with
    # every space worth the same, the board order decides (accept_contract,
    # typeIndex 625/624, comes before dutiful_service, 631/630, in both modes).
    state, seat = _turn_state(choam=choam)
    card = _starter(seat, "diplomacy")
    legal = [
        DomainAction("agent_turn", seat, (("card_id", card), ("space_id", space)))
        for space in ("dutiful_service", "accept_contract")
    ]
    reveal = DomainAction("reveal_turn", seat)

    class Flat(g.SpaceAbility):
        def can_be_run(self, p: Profile) -> bool:
            return True

        def value_for_player(
            self, p: Profile, with_entities: Sequence[Entity] = ()
        ) -> Summer:
            v = Summer()
            v.add("flat", 2.0)
            return v

    def flat_spaces(entity: Entity) -> tuple[Ability, ...]:
        if entity.kind is Kind.SPACE:
            return (Flat(entity),)
        return abilities_of(entity)

    monkeypatch.setattr(g, "abilities_of", flat_spaces)
    monkeypatch.setattr(
        g.AgentAbility, "value_for_player", lambda self, p, with_entities=(): Summer()
    )
    chosen = turn.turn_window(_run(state, [*legal, reveal]))
    assert _args(chosen) == {"card_id": card, "space_id": "accept_contract"}


def _plot_action(seat: int) -> DomainAction:
    return DomainAction(
        "play_intrigue", seat, (("card_id", "intrigue:bribery:0"), ("option", 0))
    )


@pytest.mark.parametrize(("plot_value", "expect"), [(7.0, "play"), (3.0, "agent")])
def test_plots_compete_with_placements(
    monkeypatch: pytest.MonkeyPatch,
    no_plots: list[tuple[object, ...]],
    plot_value: float,
    expect: str,
) -> None:
    state, seat = _turn_state()
    plot = _plot_action(seat)
    legal = (*ENGINE.legal_actions(state, seat), plot)
    calls: list[tuple[object, ...]] = []

    def sources(
        run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
    ) -> list[Source]:
        calls.append((tuple(actions), combat))
        return [
            Source(
                "Plot", Stage.PROMPT, tuple(actions), lambda: (plot_value, actions[0])
            )
        ]

    monkeypatch.setattr(turn, "intrigue_play_sources", sources)
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "assembly_hall", 5.0))
    chosen = turn.turn_window(_run(state, legal))
    assert calls == [((plot,), False)]
    if expect == "play":
        assert chosen == plot
    else:
        assert _args(chosen)["card_id"] == dagger


def test_plot_sources_are_not_asked_without_plots(
    monkeypatch: pytest.MonkeyPatch, no_plots: list[tuple[object, ...]]
) -> None:
    state, _ = _turn_state()
    _stub_agent_values(monkeypatch, lambda ref, spaces: (1.0, spaces[0]))
    turn.turn_window(_run(state))
    assert no_plots == []


def test_only_plots_left_answers_empty_with_reveal(
    no_plots: list[tuple[object, ...]],
) -> None:
    state, seat = _turn_state()
    plot = _plot_action(seat)
    reveal = DomainAction("reveal_turn", seat)
    chosen = turn.turn_window(_run(state, (plot, reveal)))
    assert chosen == reveal
    assert no_plots == [((plot,), False)]


def test_track_spy_is_never_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat = _turn_state()
    track_spy = DomainAction("place_track_spy", seat)
    reveal = DomainAction("reveal_turn", seat)
    assert turn.turn_window(_run(state, (track_spy, reveal))) == reveal
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "assembly_hall"))
    legal = (track_spy, *ENGINE.legal_actions(state, seat))
    chosen = turn.turn_window(_run(state, legal))
    assert chosen is not None and chosen.action_id == "agent_turn"


def test_identical_copies_are_separate_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _turn_state()
    daggers = (_starter(seat, "dagger", 0), _starter(seat, "dagger", 1))

    def table(ref: str, spaces: list[str]) -> tuple[float, str | None]:
        return (4.0 if ref in daggers else 1.0), "assembly_hall"

    calls = _stub_agent_values(monkeypatch, table)
    picked: Counter[object] = Counter()
    for rng_seed in range(12):
        picked[_args(turn.turn_window(_run(state, rng_seed=rng_seed)))["card_id"]] += 1
    assert set(picked) == set(daggers)  # MakeChoice's shuffle breaks the tie
    assert [card for card, _ in calls].count(daggers[0]) == 12


# ---------------------------------------------------------------------------
# Cost-first spaces (Agent-turn state 220)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("solari", "water", "option"), [(3, 0, 1), (2, 0, 0), (3, 3, 0)]
)
def test_gather_support_cost_option(
    monkeypatch: pytest.MonkeyPatch, solari: int, water: int, option: int
) -> None:
    state, seat = _turn_state()
    state = with_player(state, seat, resources=Resources(solari=solari, water=water))
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "gather_support"))
    run = _run(state)
    assert len([a for a in run.by_id("agent_turn") if arg(a, "card_id") == dagger]) == 3
    space = space_entity("gather_support", Board(True))
    ability = next(
        a for a in abilities_of(space) if isinstance(a, b.GatherSupportAbility)
    )
    answer = ability.evaluate(_run(state).profile, Request())
    assert answer.response == ((option,),)
    assert _args(turn.turn_window(run)) == {
        "card_id": dagger,
        "cost_option": option,
        "space_id": "gather_support",
    }


def test_gather_support_without_the_solari_skips_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _turn_state()
    state = with_player(state, seat, resources=Resources(solari=1))
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "gather_support"))

    def never(self: object, p: Profile, request: Request) -> Answer:
        raise AssertionError("a single cost option asks nothing")

    monkeypatch.setattr(b.GatherSupportAbility, "evaluate", never)
    assert _args(turn.turn_window(_run(state)))["cost_option"] == 0


def test_forced_cost_prompt_without_an_answer_is_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # GatherSupport::Evaluate stores nothing without the Solari; the forced
    # prompt then falls back to DefaultRandomChoice (12 §3.4). Our engine
    # never offers option 1 here, so the legal list is synthetic.
    state, seat = _turn_state()
    state = with_player(state, seat, resources=Resources(solari=1))
    dagger = _starter(seat, "dagger")
    _stub_agent_values(monkeypatch, _only(dagger, "gather_support"))
    legal = [
        DomainAction(
            "agent_turn",
            seat,
            (("card_id", dagger), ("cost_option", k), ("space_id", "gather_support")),
        )
        for k in (0, 1)
    ]
    legal.append(DomainAction("reveal_turn", seat))
    options = {
        _args(turn.turn_window(_run(state, legal, rng_seed=s)))["cost_option"]
        for s in range(16)
    }
    assert options == {0, 1}


def _refinery_state(
    solari: int, *, control: bool = False, occupied: bool = False
) -> tuple[GameState, int]:
    state, seat = _turn_state()
    state = with_state(state, round_number=5)
    state = with_player(
        state,
        seat,
        resources=Resources(solari=solari, spice=3, water=1),
        control_space_ids=("spice_refinery",) if control else (),
    )
    if occupied:
        opponent = (seat + 1) % 4
        state = with_player(
            state,
            opponent,
            agent_locations=("spice_refinery",),
            agents_available=state.players[opponent].agents_available - 1,
        )
        state = with_player(
            state, seat, spy_post_ids=(RS_REFINERY, REFINERY_ARRAKEEN), spies_supply=1
        )
    return state, seat


@pytest.mark.parametrize(("solari", "option"), [(8, 1), (9, 0)])
def test_spice_refinery_sells_spice_while_solari_are_worth_it(
    monkeypatch: pytest.MonkeyPatch, solari: int, option: int
) -> None:
    # Hard, round 5: one Solari is worth 0.44 at 8 Solari and 0.22 at 9;
    # GetSpiceForSpiceRefinery sells while it is >= 0.25.
    state, seat = _refinery_state(solari)
    assert _run(state).profile.spice_for_spice_refinery() == option
    recon = _starter(seat, "reconnaissance")
    _stub_agent_values(monkeypatch, _only(recon, "spice_refinery"))
    assert _args(turn.turn_window(_run(state))) == {
        "card_id": recon,
        "cost_option": option,
        "space_id": "spice_refinery",
    }


def test_spice_refinery_sees_its_own_control_bonus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The control Solari is paid in SendAgentToSpace (200), before the
    # cost-first prompt (220): 8 Solari + 1 is past the selling threshold.
    state, seat = _refinery_state(8, control=True)
    assert _run(state).profile.spice_for_spice_refinery() == 1
    recon = _starter(seat, "reconnaissance")
    _stub_agent_values(monkeypatch, _only(recon, "spice_refinery"))
    assert _args(turn.turn_window(_run(state)))["cost_option"] == 0


# ---------------------------------------------------------------------------
# Infiltration (Agent-turn state 240)
# ---------------------------------------------------------------------------


def _research_station_state(*, hooks: bool) -> tuple[GameState, int]:
    state, seat = _turn_state()
    opponent = (seat + 1) % 4
    state = with_player(
        state,
        opponent,
        agent_locations=("research_station",),
        agents_available=state.players[opponent].agents_available - 1,
    )
    state = with_player(
        state,
        seat,
        spy_post_ids=(RS_SIETCH, RS_REFINERY),
        spies_supply=1,
        resources=Resources(solari=3, spice=2, water=3),
        maker_hooks=hooks,
        influence=Influence(fremen=2),
    )
    return state, seat


def test_infiltration_recalls_the_spy_on_the_worst_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With Maker Hooks and 2 Fremen influence the Sietch Tabr post is worth
    # more (PostValueSietchTabr), so GetRecallSpy gives up the other one.
    state, seat = _research_station_state(hooks=True)
    profile = _run(state).profile
    worth = {
        p: profile.post_value(post_entity(p, seat)) for p in (RS_SIETCH, RS_REFINERY)
    }
    assert worth[RS_SIETCH] > worth[RS_REFINERY]
    recon = _starter(seat, "reconnaissance")
    _stub_agent_values(monkeypatch, _only(recon, "research_station"))
    for rng_seed in range(4):
        assert _args(turn.turn_window(_run(state, rng_seed=rng_seed))) == {
            "card_id": recon,
            "infiltrate_post_id": RS_REFINERY,
            "space_id": "research_station",
        }


def test_infiltration_tie_is_broken_by_the_post_shuffle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _research_station_state(hooks=False)
    recon = _starter(seat, "reconnaissance")
    _stub_agent_values(monkeypatch, _only(recon, "research_station"))
    posts = {
        _args(turn.turn_window(_run(state, rng_seed=s)))["infiltrate_post_id"]
        for s in range(16)
    }
    assert posts == {RS_SIETCH, RS_REFINERY}


def test_infiltration_is_judged_after_the_cost_first_ability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Occupied Spice Refinery: 2 cost options x 2 Spies. The cost option is
    # chosen first (220: sell 1 spice for 4 Solari), then GetRecallSpy runs
    # on that state (240), with every Spy still on the board.
    state, seat = _refinery_state(4, occupied=True)
    recon = _starter(seat, "reconnaissance")
    _stub_agent_values(monkeypatch, _only(recon, "spice_refinery"))
    seen: list[tuple[Resources, tuple[str, ...], tuple[str, ...]]] = []

    def post_value(self: Profile, post: Entity, unseen_network: bool = False) -> float:
        me = self.ctx.me
        seen.append((me.resources, me.spy_post_ids, me.in_play))
        return {RS_REFINERY: 2.0, REFINERY_ARRAKEEN: 1.0}[post.ref]

    monkeypatch.setattr(Profile, "post_value", post_value)
    chosen = turn.turn_window(_run(state))
    assert _args(chosen) == {
        "card_id": recon,
        "cost_option": 1,
        "infiltrate_post_id": REFINERY_ARRAKEEN,
        "space_id": "spice_refinery",
    }
    assert seen and all(
        s
        == (
            Resources(solari=8, spice=2, water=1),
            (RS_REFINERY, REFINERY_ARRAKEEN),
            (recon,),
        )
        for s in seen
    )


# ---------------------------------------------------------------------------
# The post-placement states
# ---------------------------------------------------------------------------


def test_after_send_plays_the_card_and_pays_the_control_bonus() -> None:
    state, seat = _turn_state()
    opponent = (seat + 2) % 4
    state = with_player(state, opponent, control_space_ids=("arrakeen",))
    recon = _starter(seat, "reconnaissance")
    me_before = state.players[seat]
    sent = turn._after_send(state, seat, recon, "arrakeen")
    me = sent.players[seat]
    assert me.hand == tuple(c for c in me_before.hand if c != recon)
    assert me.in_play == (*me_before.in_play, recon)
    assert me.agents_available == me_before.agents_available - 1
    assert me.agent_locations == (*me_before.agent_locations, "arrakeen")
    assert me.resources == me_before.resources  # the space cost waits for 400
    assert sent.players[opponent].resources == replace(
        state.players[opponent].resources,
        solari=state.players[opponent].resources.solari + 1,
    )
    basin = turn._after_send(
        with_player(state, seat, control_space_ids=("imperial_basin",)),
        seat,
        _starter(seat, "dagger"),
        "imperial_basin",
    )
    assert basin.players[seat].resources.spice == me_before.resources.spice + 1


@pytest.mark.parametrize(
    ("space_id", "option", "resources", "troops"),
    [
        ("gather_support", 0, Resources(solari=5, spice=2, water=1), 2),
        ("gather_support", 1, Resources(solari=3, spice=2, water=2), 2),
        ("spice_refinery", 0, Resources(solari=7, spice=2, water=1), 0),
        ("spice_refinery", 1, Resources(solari=9, spice=1, water=1), 0),
    ],
)
def test_after_cost_first_applies_the_space_effect(
    space_id: str, option: int, resources: Resources, troops: int
) -> None:
    state, seat = _turn_state()
    state = with_player(state, seat, resources=Resources(solari=5, spice=2, water=1))
    ability = turn._cost_first_ability(space_id, Board(True))
    assert ability is not None
    after = turn._after_cost_first(state, seat, ability, option)
    me, before = after.players[seat], state.players[seat]
    assert me.resources == resources
    assert me.troops_garrison == before.troops_garrison + troops
    assert me.troops_supply == before.troops_supply - troops


def test_gather_support_troops_are_capped_by_the_supply() -> None:
    state, seat = _turn_state()
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        troops_supply=1,
        troops_garrison=me.troops_garrison + me.troops_supply - 1,
    )
    ability = turn._cost_first_ability("gather_support", Board(False))
    assert ability is not None
    after = turn._after_cost_first(state, seat, ability, 0).players[seat]
    assert (after.troops_supply, after.troops_garrison) == (
        0,
        state.players[seat].troops_garrison + 1,
    )


def test_only_spice_refinery_and_gather_support_are_cost_first() -> None:
    cost_first = {
        s
        for s in turn.board_space_order(Board(True))
        if turn._cost_first_ability(s, Board(True)) is not None
    }
    assert cost_first == {"gather_support", "spice_refinery"}


# ---------------------------------------------------------------------------
# Coverage: full games never fall back in the turn window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("choam", "seed"),
    [(False, 1), (False, 2), (False, 3), (True, 7), (True, 11), (True, 13)],
)
def test_full_games_never_fall_back_in_the_turn_window(
    monkeypatch: pytest.MonkeyPatch, choam: bool, seed: int
) -> None:
    # Only this window is mirrored (other windows fall back to the heuristic,
    # whatever their state), so the games test the turn window alone.
    monkeypatch.setattr(
        agent_module,
        "handler_for",
        lambda kind: turn.HANDLERS.get(kind) if kind is not None else None,
    )
    leaders = tuple(
        random.Random(seed).sample(
            [leader.leader_id for leader in leaders_for_choam(choam)], k=4
        )
    )
    engine = UprisingRulesEngine(leader_ids=leaders)
    agents = tuple(AppAIAgent(seed=100 + 10 * seed + seat) for seat in range(4))
    result = run_policy_game(engine, RulesetConfig(choam_module=choam), seed, agents)
    assert result.state.phase is GamePhase.FINISHED
    for agent in agents:
        assert agent.fallbacks["turn"] == 0
        assert agent.fallbacks["view-only:turn"] == 0
    assert sum(agent.mirrored["turn"] for agent in agents) > 40
