"""The ``turn`` window on Bloodlines and the Tech Module (``windows/turn.py``).

Each test reaches the first TURN decision of a real Bloodlines + Tech Module
game, changes only what the branch under test needs (a hand card, a held Tech
tile, an owed acquire icon) and builds the ``DecisionRun`` the agent builds.
Expected answers are the app-style abilities' own ``Evaluate``
(docs/app-ai/bloodlines-cards.md §3.18, bloodlines-systems.md §1.7, §3.3).
"""

import random
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import (
    apply_placement,
    placements_for_steps,
)
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
    LitanyTurnStartAbility,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    GeneLockedVaultAcquiredAbility,
)
from dune_imperium.agents.app_ai.abilities.board import RecallSpyInfiltrateAbility
from dune_imperium.agents.app_ai.abilities.generic import AgentAbility
from dune_imperium.agents.app_ai.abilities.tech import MemocordersAcquiredAbility
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    space_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.bloodlines import space_with_cost_cut
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import turn
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, with_context

BL = RulesetConfig(bloodlines=True, tech_module=True, choam_module=True)
LITANY = "imperium:litany_against_fear:0"
RS_REFINERY = "arrakis-research-station-spice-refinery"
REFINERY_ARRAKEEN = "arrakis-spice-refinery-arrakeen"


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the shared Plot sources (the intrigue window's)."""

    monkeypatch.setattr(turn, "intrigue_play_sources", lambda run, plays, combat: [])


def _turn() -> tuple[GameState, int]:
    state = first_decision("turn", config=BL, seed=1)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return state, decision.owner


def _legal(state: GameState, seat: int) -> tuple[DomainAction, ...]:
    """The engine's legal list as the app AI's windows see it: an Agent-turn
    step's rows shown as the placements they stand for (stage B1,
    ``agents.agent_turn_steps``)."""

    legal = ENGINE.legal_actions(state, seat)
    steps = placements_for_steps(state, seat, legal)
    return legal if steps is None else steps[0]


def _run(
    state: GameState,
    seat: int,
    legal: tuple[DomainAction, ...] | None = None,
) -> DecisionRun:
    profile = make_profile(state, seat)
    actions = _legal(state, seat) if legal is None else legal
    return DecisionRun(profile.ctx, profile, actions, random.Random(0), Memory())


def _give_tech(state: GameState, seat: int, *tech_ids: str) -> GameState:
    """``tech_ids`` taken from the stacks into the seat's tiles."""

    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    state = with_state(state, tech_stacks=stacks)
    held = state.players[seat].tech_ids
    return with_player(state, seat, tech_ids=(*held, *tech_ids))


def _owe(state: GameState, *keys: str) -> GameState:
    """The TURN frame with Tech acquire icons owed (``tech_id:effect``)."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context[TECH_ACQUIRE_PENDING_KEY] = ",".join(keys)
    return replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )


# ===========================================================================
# play_turn_start_card: Litany Against Fear
# ===========================================================================


def test_litany_is_a_turn_start_key_valued_by_its_ability() -> None:
    state, seat = _turn()
    state = with_player(state, seat, hand=(LITANY, *state.players[seat].hand))
    run = _run(state, seat)
    play = run.first("play_turn_start_card")
    assert play is not None and arg(play, "card_id") == LITANY
    sources = turn._turn_start_card_sources(run)
    assert sources is not None and len(sources) == 1
    expected = LitanyTurnStartAbility(card_entity(LITANY, seat)).evaluate(
        make_profile(state, seat), Request()
    )
    assert sources[0].evaluate is not None
    assert sources[0].evaluate() == (expected.value, play)
    # Against the empty answer alone: played iff its value is positive.
    reveal = run.first("reveal_turn")
    assert reveal is not None
    chosen = turn.turn_window(_run(state, seat, (play, reveal)))
    assert chosen == (play if expected.value > 0 else reveal)


def test_a_turn_start_card_without_litanys_ability_falls_back() -> None:
    state, seat = _turn()
    run = _run(state, seat)
    other = state.players[seat].hand[0]
    fake = DomainAction(
        action_id="play_turn_start_card", actor=seat, arguments=(("card_id", other),)
    )
    widened = _run(state, seat, (*run.legal, fake))
    assert turn._turn_start_card_sources(widened) is None
    assert turn.turn_window(widened) is None


# ===========================================================================
# flip_tech at the turn start
# ===========================================================================


def test_advanced_data_analysis_flips_at_the_turn_start() -> None:
    state, seat = _turn()
    state = _give_tech(state, seat, "advanced_data_analysis")
    run = _run(state, seat)
    flip = run.first("flip_tech")
    assert flip is not None and arg(flip, "tech_id") == "advanced_data_analysis"
    sources = turn.tech_flip_sources(run)
    assert sources is not None and len(sources) == 1
    assert sources[0].evaluate is not None
    assert sources[0].evaluate() == (100.0, flip)  # D23: always flip
    assert turn.turn_window(run) == flip


def test_a_flip_of_an_unknown_tile_falls_back() -> None:
    state, seat = _turn()
    run = _run(state, seat)
    fake = DomainAction(
        action_id="flip_tech", actor=seat, arguments=(("tech_id", "no_such_tile"),)
    )
    assert turn.turn_window(_run(state, seat, (*run.legal, fake))) is None


# ===========================================================================
# Owed Tech acquire icons (D15): automatic, answered by the acquire ability
# ===========================================================================


def test_an_owed_influence_icon_takes_memocorders_faction_first() -> None:
    state, seat = _turn()
    state = _owe(state, "glowglobes:influence", "glowglobes:solari")
    run = _run(state, seat)
    resolves = run.by_id("resolve_tech_acquire_effect")
    assert len(resolves) == 5  # four factions, then the Solari
    tracks = tuple(
        track_entity(str(arg(a, "faction"))) for a in resolves if arg(a, "faction")
    )
    expected = MemocordersAcquiredAbility(tech_entity("glowglobes")).evaluate(
        make_profile(state, seat), Request(infos=(TargetInfo(entities=tracks),))
    )
    assert expected.response is not None
    chosen = turn.turn_window(run)
    assert chosen is not None and chosen.action_id == "resolve_tech_acquire_effect"
    assert arg(chosen, "faction") == expected.response[0][0]


def test_an_owed_single_icon_is_taken_as_it_is() -> None:
    state, seat = _turn()
    state = _owe(state, "glowglobes:solari")
    run = _run(state, seat)
    assert turn.turn_window(run) == run.first("resolve_tech_acquire_effect")


def test_gene_locked_vault_takes_the_better_of_intrigue_and_card() -> None:
    state, seat = _turn()
    state = _owe(state, "gene_locked_vault:intrigue_or_card")
    run = _run(state, seat)
    answer = GeneLockedVaultAcquiredAbility(tech_entity("gene_locked_vault")).evaluate(
        make_profile(state, seat), Request()
    )
    assert answer.response is not None
    expected = "intrigue" if answer.response[0][0] == 0 else "card"
    chosen = turn.turn_window(run)
    assert chosen is not None and arg(chosen, "choice") == expected


def test_forbidden_weapons_destroys_the_wall_iff_should_blow_wall() -> None:
    state, seat = _turn()
    state = _owe(state, "forbidden_weapons:shield_wall")
    run = _run(state, seat)
    assert len(run.by_id("resolve_tech_acquire_effect")) == 2
    destroy = make_profile(state, seat).should_blow_wall()
    chosen = turn.turn_window(run)
    assert chosen is not None
    assert (arg(chosen, "destroy_shield_wall") is True) is destroy


def test_an_unknown_choice_icon_falls_back() -> None:
    state, seat = _turn()
    run = _run(state, seat)
    fakes = tuple(
        DomainAction(
            action_id="resolve_tech_acquire_effect",
            actor=seat,
            arguments=(("effect", "mystery"), ("option", n), ("tech_id", "glowglobes")),
        )
        for n in range(2)
    )
    assert turn.turn_window(_run(state, seat, (*run.legal, *fakes))) is None


# ===========================================================================
# Navigation Chamber: the cut space is the target (D60)
# ===========================================================================


@pytest.mark.parametrize(
    ("card", "space_id", "kind"),
    [("dagger", "high_council", "solari"), ("diplomacy", "sardaukar", "spice")],
)
def test_navigation_chamber_targets_and_prices_the_cut_space(
    card: str, space_id: str, kind: str
) -> None:
    """The engine offers only the cut placement (OQ-104, codec v142: "Board
    spaces cost you [1 spice] or [1 Solari] less." [Tech tile face] has no
    "may"), so the window sees one variant here and prices the cut cost.
    Before v142 the undiscounted variant came first and ``_best_discount``
    chose between the two; it now separates only Spice Refinery's and Gather
    Support's free option 0 from their cut option 1."""

    state, seat = _turn()
    state = _give_tech(state, seat, "navigation_chamber")
    me = state.players[seat]
    state = with_player(
        state, seat, resources=replace(me.resources, solari=10, spice=10)
    )
    ref = next(r for r in state.players[seat].hand if f":{card}:" in r)
    run = _run(state, seat)
    variants = [
        a
        for a in run.by_id("agent_turn")
        if arg(a, "card_id") == ref and arg(a, "space_id") == space_id
    ]
    assert [arg(a, "discount") for a in variants] == [kind]
    reveal = run.first("reveal_turn")
    assert reveal is not None
    narrowed = _run(state, seat, (*variants, reveal))
    (source,) = turn._card_sources(narrowed)
    assert source.evaluate is not None
    value, action = source.evaluate()
    # The same AgentAbility over the printed and the cut space: the cut
    # cost is what the window prices.
    profile = make_profile(state, seat)
    agent = next(
        a for a in abilities_of(card_entity(ref, seat)) if isinstance(a, AgentAbility)
    )
    base = space_entity(space_id, profile.ctx.board)
    plain = agent.evaluate(profile, Request(infos=(TargetInfo(entities=(base,)),)))
    cut = agent.evaluate(
        profile,
        Request(infos=(TargetInfo(entities=(space_with_cost_cut(base, kind),)),)),
    )
    assert cut.value > plain.value  # the cut cost is priced
    assert action is not None and arg(action, "discount") == kind
    chosen = turn.turn_window(narrowed)
    assert chosen == (action if value > 0 else reveal)


def test_without_navigation_chamber_the_targets_are_the_plain_spaces() -> None:
    state, seat = _turn()
    run = _run(state, seat)
    assert all(arg(a, "discount") is None for a in run.by_id("agent_turn"))
    board = run.ctx.board
    targets = turn._space_targets("high_council", board, {None})
    assert targets == (space_entity("high_council", board),)


def _broke_at_a_taken_refinery() -> tuple[GameState, int]:
    """Navigation Chamber held, no spice, Spice Refinery taken by the next
    seat and the seat's Spies on both of its posts."""

    state, seat = _turn()
    state = _give_tech(state, seat, "navigation_chamber")
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        resources=replace(me.resources, spice=0),
        spy_post_ids=(RS_REFINERY, REFINERY_ARRAKEEN),
        spies_supply=1,
    )
    opponent = (seat + 1) % 4
    state = with_player(
        state,
        opponent,
        agent_locations=("spice_refinery",),
        agents_available=state.players[opponent].agents_available - 1,
    )
    return state, seat


def test_the_free_spice_refinery_trade_is_realised_at_no_spice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 2026-10-09 RL run (readapt-v141): the spice cut makes the 1-spice trade
    # legal at 0 spice; the Spy recall (state 240) was judged on a state that
    # paid the full spice, and the negative spice raised in the window.
    state, seat = _broke_at_a_taken_refinery()
    recon = f"player:{seat}:starter:reconnaissance:0"
    legal = _legal(state, seat)
    variants = tuple(
        a
        for a in legal
        if a.action_id == "agent_turn"
        and arg(a, "card_id") == recon
        and arg(a, "space_id") == "spice_refinery"
    )
    # The game's own legal set offers the trade at 0 spice, with the cut only.
    assert {
        (arg(a, "cost_option"), arg(a, "discount"), arg(a, "infiltrate_post_id"))
        for a in variants
    } == {
        (0, None, RS_REFINERY),
        (0, None, REFINERY_ARRAKEEN),
        (1, "spice", RS_REFINERY),
        (1, "spice", REFINERY_ARRAKEEN),
    }
    reveal = next(a for a in legal if a.action_id == "reveal_turn")
    seen: list[Resources] = []
    recall = RecallSpyInfiltrateAbility.evaluate

    def record(
        self: RecallSpyInfiltrateAbility, p: Profile, request: Request
    ) -> Answer:
        seen.append(p.ctx.me.resources)
        return recall(self, p, request)

    monkeypatch.setattr(RecallSpyInfiltrateAbility, "evaluate", record)
    chosen = turn.turn_window(_run(state, seat, (*variants, reveal)))
    assert chosen in variants
    assert (arg(chosen, "cost_option"), arg(chosen, "discount")) == (1, "spice")
    # GetRecallSpy saw the cut trade: no spice paid, 4 Solari gained.
    before = state.players[seat].resources
    assert seen == [replace(before, solari=before.solari + 4)]
    # The engine charges the same: still no spice after the placement.
    placed = apply_placement(ENGINE, state, chosen).state
    assert placed.players[seat].resources.spice == 0


def test_the_cost_first_payment_takes_the_navigation_chamber_cut() -> None:
    state, seat = _turn()
    me = state.players[seat]
    state = with_player(state, seat, resources=replace(me.resources, solari=1, spice=0))
    board = make_profile(state, seat).ctx.board
    refinery = turn._cost_first_ability("spice_refinery", board, "spice")
    gather = turn._cost_first_ability("gather_support", board, "solari")
    assert refinery is not None and gather is not None
    # Spice Refinery: the 1-spice trade costs nothing; 4 Solari.
    after = turn._after_cost_first(state, seat, refinery, 1).players[seat]
    assert (after.resources.spice, after.resources.solari) == (0, 5)
    # Gather Support: the water costs 1 Solari instead of 2.
    after = turn._after_cost_first(state, seat, gather, 1).players[seat]
    assert (after.resources.solari, after.resources.water) == (
        0,
        me.resources.water + 1,
    )
