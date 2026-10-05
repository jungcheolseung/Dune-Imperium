"""The app_ai ``reveal`` and ``reveal_choice`` windows with Immortality, Epic,
Go to 11 and the promos (``windows/reveal.py``).

Real Reveal turns of an Immortality game: a seat's hand is set on a real
turn-start state and ``reveal_turn`` is applied, so every frame, context key
and legal action is the engine's own. ``intrigue_play_sources`` (the intrigue
window's) is stubbed unless a test says otherwise.
"""

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.abilities import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import AcquireAbility
from dune_imperium.agents.app_ai.abilities.immortality import (
    ForHumanityRevealAbility,
    GainResearchRevealAbility,
    ReclaimedForcesAcquireAbility,
    TleilaxuSurgeonRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_b import ShadoutMapesAbility
from dune_imperium.agents.app_ai.catalog import card_entity, track_entity
from dune_imperium.agents.app_ai.context import RECLAIMED_FORCES_REF, AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES, AIConstants
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    with_player,
)
from dune_imperium.agents.app_ai.windows import reveal
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.intrigue import RESEARCH_INTENT
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

IMMORTALITY = RulesetConfig(immortality=True, choam_module=True)
HARD = TABLES[2]
#: Hard constants with no card worth buying (every AcquireValue is zeroed by
#: ``MinimumAcquireValue``), to isolate the other keys of the prompt.
NO_BUYS = replace(
    HARD,
    MinimumAcquireValueEarly=1e9,
    MinimumAcquireValueMid=1e9,
    MinimumAcquireValueLate=1e9,
)
#: A research space past the first genetic marker (column 4) and the second
#: (column 8).
ONE_MARKER = "c4r2"
TWO_MARKERS = "c8r2"
#: A research space before the first marker with two rightward neighbours.
TWO_WAYS = "c1r3"


@pytest.fixture(autouse=True)
def _no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """``intrigue_play_sources`` belongs to the intrigue window: no Plot key."""

    monkeypatch.setattr(
        reveal, "intrigue_play_sources", lambda run, actions, combat: []
    )


# -- helpers ---------------------------------------------------------------------


def owner(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def legal(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.legal_actions(state, owner(state))


def make_run(
    state: GameState,
    memory: Memory | None = None,
    *,
    constants: AIConstants = HARD,
    actions: tuple[DomainAction, ...] | None = None,
) -> DecisionRun:
    seat = owner(state)
    ctx = AppContext(state, seat, ENGINE.observe(state, seat))
    rng = random.Random(0)
    return DecisionRun(
        ctx,
        Profile(ctx, constants, rng),
        legal(state) if actions is None else actions,
        rng,
        memory if memory is not None else Memory(),
    )


def find(state: GameState, action_id: str, **args: object) -> DomainAction:
    for action in legal(state):
        if action.action_id == action_id and all(
            dict(action.arguments).get(k) == v for k, v in args.items()
        ):
            return action
    raise AssertionError(f"{action_id} {args} is not legal")


def apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action, legal_actions=legal(state)).state


def revealed(hand: list[str], **changes: object) -> GameState:
    """A real Immortality Reveal turn of seat 0 (Feyd, seed 3) with ``hand``.

    The troop supply keeps the 12 troops accounted for unless it is given.
    """

    state = first_decision("turn", config=IMMORTALITY, seed=3)
    seat = owner(state)
    me = state.players[seat]
    placed = sum(
        int(str(changes.get(name, getattr(me, name))))
        for name in ("troops_garrison", "troops_conflict", "specimens")
    )
    changes.setdefault("troops_supply", 12 - placed - me.memories - me.troops_parked)
    state = with_player(state, seat, hand=tuple(hand), **changes)
    return apply(state, find(state, "reveal_turn"))


def defer_all(state: GameState) -> GameState:
    while state.decision_stack[-1].kind == "reveal_choice":
        state = apply(state, find(state, "defer_reveal_choice"))
    return state


def resumed(hand: list[str], effect: str, **changes: object) -> GameState:
    state = defer_all(revealed(hand, **changes))
    return apply(state, find(state, "resume_reveal_choice", effect=effect))


def gain_sources(run: DecisionRun) -> list[Source]:
    sources = reveal._gain_sources(run)
    assert sources is not None
    return sources


# ===========================================================================
# Automatic gains: state 300 (printed specimens first) and 400
# ===========================================================================


def test_printed_specimens_run_before_the_other_state_300_gains() -> None:
    """``OrderByDescending(Specimens)``: Spiritual Fervor's specimen before
    Occupation's troop, spice and water although Occupation is revealed
    first."""

    state = revealed(["imperium:occupation:0", "imperium:spiritual_fervor:0"])
    ids = {a.action_id for a in legal(state)}
    assert {"generate_reveal_specimens", "recruit_reveal_troops"} <= ids
    action = reveal.reveal_window(make_run(state))
    assert action is not None and action.action_id == "generate_reveal_specimens"


def test_bene_tleilax_lab_spice_is_a_state_400_gain() -> None:
    """``BeneTleilaxLabAbility`` always runs immediately (state 400): High
    Priority Travel's printed Solari (state 300) comes first."""

    state = revealed(
        ["imperium:bene_tleilax_lab:0", "imperium:high_priority_travel:0"],
        research_space=ONE_MARKER,
    )
    first = reveal.reveal_window(make_run(state))
    assert first == find(state, "gain_reveal_resources", solari=1, spice=0, water=0)
    state = apply(state, first)
    second = reveal.reveal_window(make_run(state))
    assert second == find(state, "gain_reveal_resources", solari=0, spice=1, water=0)


# ===========================================================================
# Explicit prompt gains
# ===========================================================================


def test_tleilaxu_master_research_is_one_explicit_key_per_icon() -> None:
    state = revealed(["imperium:tleilaxu_master:0"], research_space=TWO_WAYS)
    run = make_run(state, constants=NO_BUYS)
    assert run.first("finish_reveal") is None
    research = [
        s for s in gain_sources(run) if s.actions[0].action_id.endswith("research")
    ]
    assert len(research) == 2
    assert all(s.stage == Stage.PROMPT and s.extra["explicit"] for s in research)
    action = reveal.reveal_window(run)
    assert action == find(state, "advance_reveal_research")
    # The key's answer names the space for the research_advance window.
    spaces = tuple(research_space_entity(s) for s in run.ctx.research_next_space_ids())
    ability = GainResearchRevealAbility(card_entity("imperium:tleilaxu_master:0"))
    answer = ability.evaluate(run.profile, Request((TargetInfo(entities=spaces),)))
    assert answer.response is not None and answer.response[0]
    expected = str(answer.response[0][0]).removeprefix("research:")
    key = (RESEARCH_INTENT, state.round_number, run.ctx.seat)
    assert run.memory.intents[key] == expected


def test_research_gain_from_a_card_without_the_reveal_class_is_not_mirrored() -> None:
    """A pending Research / Tleilaxu Reveal gain whose source card has no
    ``GainResearchRevealAbility`` / ``DissectingKitRevealAbility`` (an
    expansion card with the same printed icon) has no app key: None."""

    state = revealed(["imperium:tleilaxu_master:0"], research_space=TWO_WAYS)
    run = make_run(state, constants=NO_BUYS)
    action = find(state, "advance_reveal_research")
    master = [("research", "2", "imperium:tleilaxu_master:0")]
    assert reveal._prompt_gain_sources(run, action, "research", master, {})
    other = [("research", "1", "player:0:starter:dagger:0")]
    assert reveal._prompt_gain_sources(run, action, "research", other, {}) is None


def test_a_single_research_step_stores_no_space() -> None:
    """From the start space the token has one way to go: no
    ``research_advance`` frame, so no intent is left behind."""

    state = revealed(["imperium:tleilaxu_master:0"])
    run = make_run(state, constants=NO_BUYS)
    assert len(run.ctx.research_next_space_ids()) == 1
    assert reveal.reveal_window(run) == find(state, "advance_reveal_research")
    assert (RESEARCH_INTENT, state.round_number, run.ctx.seat) not in run.memory.intents


def test_research_key_without_a_drawable_card_runs_automatically() -> None:
    """With both markers Research draws a card (``Cost`` = a drawable card);
    with none the app offers no key, our engine still owes the gain."""

    state = revealed(
        ["imperium:tleilaxu_master:0"],
        research_space=TWO_MARKERS,
        deck=(),
        discard_pile=(),
    )
    run = make_run(state)
    (source,) = [
        s for s in gain_sources(run) if s.actions[0].action_id.endswith("research")
    ]
    assert source.stage == Stage.REVEAL_AUTO
    assert reveal.reveal_window(run) == find(state, "advance_reveal_research")


def test_dissecting_kit_tleilaxu_step_is_an_explicit_key_worth_one() -> None:
    state = revealed(["imperium:dissecting_kit:0"], research_space=ONE_MARKER)
    run = make_run(state, constants=NO_BUYS)
    (source,) = [
        s for s in gain_sources(run) if s.actions[0].action_id.endswith("tleilaxu")
    ]
    assert source.stage == Stage.PROMPT and source.extra["explicit"]
    assert source.evaluate is not None
    assert source.evaluate() == (1.0, find(state, "advance_reveal_tleilaxu"))
    assert reveal.reveal_window(run) == find(state, "advance_reveal_tleilaxu")


def test_dissecting_kit_at_the_track_end_runs_automatically() -> None:
    state = revealed(
        ["imperium:dissecting_kit:0"], research_space=ONE_MARKER, tleilaxu_space=7
    )
    run = make_run(state)
    (source,) = [
        s for s in gain_sources(run) if s.actions[0].action_id.endswith("tleilaxu")
    ]
    assert source.stage == Stage.REVEAL_AUTO


def test_throne_room_politics_influence_is_an_in_the_shadows_key() -> None:
    state = revealed(["imperium:throne_room_politics:0"])
    run = make_run(state, constants=NO_BUYS)
    influence = find(state, "gain_reveal_faction_influence", faction="bene_gesserit")
    (source,) = [s for s in gain_sources(run) if influence in s.actions]
    assert source.stage == Stage.PROMPT and source.extra["explicit"]
    assert source.evaluate is not None and source.evaluate() == (100.0, influence)


def test_throne_room_politics_influence_at_the_top_runs_automatically() -> None:
    state = revealed(
        ["imperium:throne_room_politics:0"],
        influence=Influence(bene_gesserit=6),
    )
    run = make_run(state)
    influence = find(state, "gain_reveal_faction_influence", faction="bene_gesserit")
    (source,) = [s for s in gain_sources(run) if influence in s.actions]
    assert source.stage == Stage.REVEAL_AUTO


# ===========================================================================
# Tleilaxu buys, Reclaimed Forces, Family Atomics, Return Specimen
# ===========================================================================


def _post_reveal(**changes: object) -> GameState:
    state = revealed(["player:0:starter:dagger:0"], **changes)
    while any(a.action_id == "gain_reveal_resources" for a in legal(state)):
        state = apply(state, find(state, "gain_reveal_resources"))
    return state


def test_tleilaxu_buy_without_a_marker_is_the_plain_acquisition() -> None:
    state = _post_reveal(specimens=4)
    run = make_run(state)
    sources = reveal._tleilaxu_sources(run)
    assert sources
    for source in sources:
        assert source.evaluate is not None
        value, action = source.evaluate()
        instance = str(arg(source.actions[0], "instance_id"))
        ability = AcquireAbility(card_entity(instance))
        assert value == ability.evaluate(run.profile, Request()).value
        assert action is not None and arg(action, "to_deck_top") is None


def test_tleilaxu_buy_with_a_marker_goes_on_top_of_the_deck() -> None:
    """``ChooseAcquireTleilaxuLocation``: the AI answers option 0, "Top of
    Deck" (our ``to_deck_top`` variant)."""

    state = _post_reveal(specimens=4, research_space=ONE_MARKER)
    run = make_run(state)
    sources = reveal._tleilaxu_sources(run)
    assert sources
    for source in sources:
        assert len(source.actions) == 2
        assert source.evaluate is not None
        _value, action = source.evaluate()
        assert action is not None and arg(action, "to_deck_top") is True


@pytest.mark.parametrize("tleilaxu", [0, 7])
def test_reclaimed_forces_follows_its_option_and_never_advances_past_seven(
    tleilaxu: int,
) -> None:
    state = _post_reveal(specimens=3, tleilaxu_space=tleilaxu)
    run = make_run(state)
    (source,) = reveal._reclaimed_forces_source(run)
    assert source.evaluate is not None
    value, action = source.evaluate()
    ability = ReclaimedForcesAcquireAbility(card_entity(RECLAIMED_FORCES_REF))
    answer = ability.evaluate(run.profile, Request((TargetInfo(options=(0, 1)),)))
    assert value == answer.value
    assert answer.response is not None
    wanted = "tleilaxu" if answer.response[0] == (1,) and tleilaxu < 7 else "troops"
    assert action == find(state, "acquire_reclaimed_forces", choice=wanted)
    if tleilaxu == 7:
        assert arg(action, "choice") == "troops"


def test_reclaimed_forces_tleilaxu_option_is_taken_when_it_is_worth_more() -> None:
    """At Tleilaxu rank 3 the step reaches the VP space: option 1."""

    state = _post_reveal(specimens=3, tleilaxu_space=3)
    (source,) = reveal._reclaimed_forces_source(make_run(state))
    assert source.evaluate is not None
    _value, action = source.evaluate()
    assert action == find(state, "acquire_reclaimed_forces", choice="tleilaxu")


@pytest.fixture
def no_tleilaxu_buys(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Tleilaxu Row key (their value ignores ``MinimumAcquireValue``)."""

    monkeypatch.setattr(reveal, "_tleilaxu_sources", lambda run: [])
    monkeypatch.setattr(reveal, "_reclaimed_forces_source", lambda run: [])


@pytest.mark.usefixtures("no_tleilaxu_buys")
def test_family_atomics_is_a_key_worth_100_with_four_to_eight_persuasion() -> None:
    state = defer_all(
        revealed(
            [
                "player:0:starter:experimentation:0",
                "player:0:starter:dagger:0",
                "player:0:starter:diplomacy:0",
                "player:0:starter:seek_allies:0",
                "player:0:starter:signet_ring:0",
                "imperium:for_humanity:0",
            ]
        )
    )
    while any(a.action_id == "generate_reveal_specimens" for a in legal(state)):
        state = apply(state, find(state, "generate_reveal_specimens"))
    run = make_run(state, constants=NO_BUYS)
    persuasion = run.ctx.reveal_persuasion()
    assert persuasion is not None and 4 <= persuasion <= 8
    (source,) = reveal._family_atomics_source(run)
    assert source.evaluate is not None
    assert source.evaluate() == (100.0, find(state, "use_family_atomics"))
    assert reveal.reveal_window(run) == find(state, "use_family_atomics")


@pytest.mark.usefixtures("no_tleilaxu_buys")
def test_family_atomics_outside_four_to_eight_persuasion_is_no_answer() -> None:
    state = _post_reveal()
    run = make_run(state, constants=NO_BUYS)
    persuasion = run.ctx.reveal_persuasion()
    assert persuasion is not None and persuasion < 4
    (source,) = reveal._family_atomics_source(run)
    assert source.evaluate is not None
    value, _action = source.evaluate()
    assert value == 0.0
    assert reveal.reveal_window(run) == find(state, "finish_reveal")


@pytest.mark.usefixtures("no_tleilaxu_buys")
def test_return_specimen_returns_the_whole_shortfall_as_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _post_reveal(
        specimens=3, ungained_troops=2, troops_supply=0, troops_garrison=9
    )
    memory = Memory()
    run = make_run(state, memory, constants=NO_BUYS)
    assert reveal.reveal_window(run) == find(state, "return_specimen")
    key = (reveal._RETURN_BATCH, state.round_number, run.ctx.seat)
    assert memory.intents[key] == 1
    state = apply(state, find(state, "return_specimen"))
    assert state.players[0].ungained_troops == 1  # refilled from the specimen

    def boom(*args: object) -> object:
        raise AssertionError("the rest of the answer is not evaluated again")

    with monkeypatch.context() as patch:
        patch.setattr(reveal, "_return_specimen_source", boom)
        second = make_run(state, memory, constants=NO_BUYS)
        assert reveal.reveal_window(second) == find(state, "return_specimen")
    assert key not in memory.intents
    state = apply(state, find(state, "return_specimen"))
    assert state.players[0].ungained_troops == 0
    assert reveal.reveal_window(make_run(state, memory, constants=NO_BUYS)) == find(
        state, "finish_reveal"
    )


@pytest.mark.usefixtures("no_tleilaxu_buys")
def test_specimens_are_never_returned_without_a_shortfall() -> None:
    state = _post_reveal(specimens=3)
    run = make_run(state, constants=NO_BUYS)
    assert run.first("return_specimen") is not None
    (source,) = reveal._return_specimen_source(run, {})
    assert source.evaluate is not None
    assert source.evaluate() == (0.0, None)
    assert reveal.reveal_window(run) == find(state, "finish_reveal")


@pytest.mark.usefixtures("no_tleilaxu_buys")
def test_a_stale_return_batch_is_dropped() -> None:
    state = _post_reveal(specimens=3)
    memory = Memory()
    key = (reveal._RETURN_BATCH, state.round_number, 0)
    memory.intents[key] = 2
    run = make_run(state, memory, constants=NO_BUYS)
    assert reveal.reveal_window(run) == find(state, "finish_reveal")
    assert key not in memory.intents


# ===========================================================================
# reveal_choice: For Humanity, Shadout Mapes, Tleilaxu Surgeon
# ===========================================================================


def test_for_humanity_choice_is_deferred_first() -> None:
    state = revealed(
        ["imperium:for_humanity:0"],
        alliance_faction_ids=("bene_gesserit",),
        influence=Influence(bene_gesserit=4, fremen=2),
    )
    assert state.decision_stack[-1].kind == "reveal_choice"
    run = make_run(state)
    assert reveal.reveal_choice_window(run) == find(state, "defer_reveal_choice")


def test_for_humanity_loses_on_the_app_best_track() -> None:
    effect = "may_lose_influence_for_vp_if_bene_gesserit_alliance"
    state = resumed(
        ["imperium:for_humanity:0"],
        effect,
        alliance_faction_ids=("bene_gesserit",),
        influence=Influence(bene_gesserit=4, fremen=2, emperor=1),
        victory_points=5,
    )
    run = make_run(state)
    tracks = tuple(track_entity(f) for f in ("bene_gesserit", "fremen"))
    ability = ForHumanityRevealAbility(card_entity("imperium:for_humanity:0"))
    answer = ability.evaluate(run.profile, Request((TargetInfo(entities=tracks),)))
    action = reveal.reveal_choice_window(run)
    if answer.value > 0:
        assert answer.response is not None
        assert action == find(
            state, "lose_reveal_influence_for_vp", faction=answer.response[0][0]
        )
    else:
        assert action == find(state, "decline_reveal_influence_loss")


def test_for_humanity_worth_nothing_declines() -> None:
    effect = "may_lose_influence_for_vp_if_bene_gesserit_alliance"
    state = resumed(
        ["imperium:for_humanity:0"],
        effect,
        alliance_faction_ids=("bene_gesserit",),
        influence=Influence(bene_gesserit=4),
    )
    zero = replace(HARD, VictoryPointValueEarly=-100.0, VictoryPointValueMid=-100.0)
    run = make_run(state, constants=zero)
    assert reveal.reveal_choice_window(run) == find(
        state, "decline_reveal_influence_loss"
    )


def test_shadout_mapes_follows_its_evaluate() -> None:
    state = resumed(
        ["imperium:shadout_mapes:0"],
        "may_deploy_or_retreat_one_troop",
        troops_garrison=3,
    )
    run = make_run(state)
    ability = ShadoutMapesAbility(card_entity("imperium:shadout_mapes:0"))
    answer = ability.evaluate(run.profile, Request((TargetInfo(options=(0,)),)))
    action = reveal.reveal_choice_window(run)
    if answer.value > 0:
        assert action == find(state, "deploy_reveal_card_troop")
    else:
        assert action == find(state, "decline_reveal_troop_move")


@pytest.mark.parametrize(
    ("option", "action_id"),
    [(0, "deploy_reveal_card_troop"), (1, "retreat_reveal_card_troop")],
)
def test_shadout_mapes_options_map_to_deploy_then_retreat(
    option: int, action_id: str
) -> None:
    state = resumed(
        ["imperium:shadout_mapes:0"],
        "may_deploy_or_retreat_one_troop",
        troops_garrison=2,
        troops_conflict=2,
    )
    run = make_run(state)
    answer = Answer(100.0, ((option,),))
    action = reveal._realise(run, "may_deploy_or_retreat_one_troop", answer)
    assert action == find(state, action_id)


def test_tleilaxu_surgeon_trades_the_app_troops_for_specimens() -> None:
    state = resumed(
        ["imperium:tleilaxu_surgeon:0"],
        "may_lose_two_troops_for_two_specimens",
        troops_garrison=3,
        troops_conflict=2,
    )
    run = make_run(state)
    request = reveal._choice_request(
        run, "may_lose_two_troops_for_two_specimens", "imperium:tleilaxu_surgeon:0"
    )
    assert request.infos[0].options == (0, 0, 0, 1, 1)
    ability = TleilaxuSurgeonRevealAbility(card_entity("imperium:tleilaxu_surgeon:0"))
    answer = ability.evaluate(run.profile, request)
    action = reveal.reveal_choice_window(run)
    if answer.value > 0:
        assert answer.response is not None
        zones = ",".join(
            "garrison" if c == 0 else "conflict" for c in sorted(answer.response[0])
        )
        assert action == find(state, "lose_reveal_troops_for_specimens", zones=zones)
    else:
        assert action == find(state, "decline_reveal_troop_sacrifice")


@pytest.mark.parametrize(
    ("codes", "zones"),
    [
        ((0, 0), "garrison,garrison"),
        ((1, 0), "garrison,conflict"),
        ((1, 1), "conflict,conflict"),
    ],
)
def test_surgeon_zone_codes_map_to_our_zone_pairs(
    codes: tuple[int, int], zones: str
) -> None:
    state = resumed(
        ["imperium:tleilaxu_surgeon:0"],
        "may_lose_two_troops_for_two_specimens",
        troops_garrison=2,
        troops_conflict=2,
    )
    run = make_run(state)
    answer = Answer(5.0, (codes,))
    action = reveal._realise(run, "may_lose_two_troops_for_two_specimens", answer)
    assert action == find(state, "lose_reveal_troops_for_specimens", zones=zones)


def test_choice_card_without_its_mapped_ability_is_not_mirrored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A choice effect whose card does not carry the mapped app class (a
    catalog gap) is not valued with another card's ability: no answer."""

    effect = "may_lose_influence_for_vp_if_bene_gesserit_alliance"
    state = resumed(
        ["imperium:for_humanity:0"],
        effect,
        alliance_faction_ids=("bene_gesserit",),
        influence=Influence(bene_gesserit=4, fremen=2),
    )
    run = make_run(state)
    assert reveal.reveal_choice_window(run) is not None
    monkeypatch.setitem(reveal._CHOICE_ABILITIES, effect, ShadoutMapesAbility)
    assert reveal.reveal_choice_window(make_run(state)) is None


def test_buy_key_of_a_card_without_the_acquire_class_is_not_mirrored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every buy key is the card's own ``AcquireAbility``: a card lacking
    the class is a catalog gap and the post-reveal prompt is not answered
    (the class is no longer attached to it)."""

    state = _post_reveal(specimens=4)
    assert reveal._tleilaxu_sources(make_run(state))  # Tleilaxu Row buys
    assert reveal.reveal_window(make_run(state)) is not None
    monkeypatch.setattr(reveal, "AcquireAbility", ReclaimedForcesAcquireAbility)
    assert reveal.reveal_window(make_run(state)) is None


def test_immortality_choices_are_optional_end_turn_blockers() -> None:
    """With nothing else to do the app ends the turn: the pending Optional
    choice is resumed to be declined, then the turn ends."""

    state = defer_all(revealed(["imperium:shadout_mapes:0"], troops_garrison=1))
    resume = find(
        state, "resume_reveal_choice", effect="may_deploy_or_retreat_one_troop"
    )
    assert all(a.action_id != "finish_reveal" for a in legal(state))
    memory = Memory()
    run = make_run(state, memory, constants=NO_BUYS)
    ability = ShadoutMapesAbility(card_entity("imperium:shadout_mapes:0"))
    answer = ability.evaluate(run.profile, Request((TargetInfo(options=(0,)),)))
    assert reveal.reveal_window(run) == resume
    key = ("reveal_choice", state.round_number, "may_deploy_or_retreat_one_troop")
    assert memory.intents[key] == (answer if answer.value > 0 else "decline")


# ===========================================================================
# Full games
# ===========================================================================


@pytest.mark.parametrize(
    "options",
    [
        {"immortality": True},
        {"immortality": True, "go_to_11": True, "epic_game": True},
        {"epic_game": True, "promo_cards": True},
    ],
)
def test_option_games_never_fall_back_in_these_windows(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, bool]
) -> None:
    """Four app_ai seats with only this module's handlers installed (every
    other window answers at random): no ``reveal``/``reveal_choice`` decision
    falls back."""

    monkeypatch.undo()  # the real Plot keys

    def only_reveal(kind: str | None) -> Callable[[DecisionRun], object] | None:
        return None if kind is None else reveal.HANDLERS.get(kind)

    monkeypatch.setattr(agent_module, "handler_for", only_reveal)
    mirrored: Counter[str] = Counter()
    for game in range(2):
        choam = game % 2 == 1
        seed = 70 + game
        leaders = tuple(
            random.Random(seed).sample(
                [leader.leader_id for leader in leaders_for_choam(choam)], k=4
            )
        )
        agents = tuple(AppAIAgent(seed=700 + 10 * game + seat) for seat in range(4))
        result = run_policy_game(
            UprisingRulesEngine(leader_ids=leaders),
            RulesetConfig(choam_module=choam, **options),
            seed,
            agents,
        )
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            for kind in ("reveal", "reveal_choice"):
                assert agent.fallbacks[kind] == 0, (game, kind)
                mirrored[kind] += agent.mirrored[kind]
    assert mirrored["reveal"] > 0, mirrored
