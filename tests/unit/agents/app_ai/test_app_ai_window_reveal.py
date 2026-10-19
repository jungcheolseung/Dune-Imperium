"""The app_ai ``reveal``, ``reveal_choice`` and ``acquisition_spy`` windows.

Real Reveal turns: a seat's hand is set on a real turn-start state and
``reveal_turn`` is applied, so every frame, context key and legal action is
the engine's own. ``intrigue_play_sources`` (another window's) is stubbed.
"""

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import agent as agent_module
from dune_imperium.agents.app_ai.abilities import Answer, Request
from dune_imperium.agents.app_ai.abilities.base import ResponseItem
from dune_imperium.agents.app_ai.abilities.generic import (
    AcquireAbility,
    PlaceSpyCustomAbility,
    PlaceSpyRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    CalculusofPowerEmperorAbility,
    CorrinthCityRevealAbility,
    DesertPowerDeferredAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_b import (
    SpacingGuildsFavorRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.leaders import DeviousStrengthAbility
from dune_imperium.agents.app_ai.catalog import card_entity, post_entity, track_entity
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES, AIConstants
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import reveal
from dune_imperium.agents.app_ai.windows.common import Source, Stage, decide
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

HARD = TABLES[2]
#: Hard constants with no card worth buying (every AcquireValue is zeroed by
#: ``MinimumAcquireValue``), to isolate the other keys of the prompt.
NO_BUYS = replace(
    HARD,
    MinimumAcquireValueEarly=1e9,
    MinimumAcquireValueMid=1e9,
    MinimumAcquireValueLate=1e9,
)
FEYD_POSTS = (
    "emperor-sardaukar-dutiful-service",
    "bene-gesserit-espionage-secrets",
    "arrakis-hagga-basin",
)


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
    # The whole actions the rules resolve (stage B3b-2: the Reveal frame
    # offers its effects effect first, and the agents see whole actions).
    return ENGINE.whole_actions(state, owner(state))


def make_run(
    state: GameState,
    memory: Memory | None = None,
    *,
    rng_seed: int = 0,
    constants: AIConstants = HARD,
    actions: tuple[DomainAction, ...] | None = None,
) -> DecisionRun:
    seat = owner(state)
    ctx = AppContext(state, seat, ENGINE.observe(state, seat))
    rng = random.Random(rng_seed)
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
    return apply_whole(ENGINE, state, action, legal_actions=legal(state)).state


def revealed(hand: list[str], **changes: object) -> GameState:
    """A real Reveal turn of the first turn's seat (Feyd, seed 3) with ``hand``."""

    state = first_decision("turn", choam=True, seed=3)
    state = with_player(state, owner(state), hand=tuple(hand), **changes)
    return apply(state, find(state, "reveal_turn"))


def take_gains(state: GameState) -> GameState:
    """Answer the automatic gains until the post-reveal prompt is reached."""

    gain_ids = {
        "recruit_reveal_troops",
        "draw_reveal_intrigue",
        "gain_reveal_resources",
    }
    while any(a.action_id in gain_ids for a in legal(state)):
        action = reveal.reveal_window(make_run(state))
        assert action is not None
        state = apply(state, action)
    return state


def entry_of(state: GameState, effect: str) -> reveal._Entry:
    """The pending choice of ``effect`` that offers rows (the only one)."""

    entries = reveal._choice_entries(make_run(state))
    assert entries is not None
    (entry,) = [e for e in entries if e.effect == effect]
    return entry


def entry_run(state: GameState, effect: str) -> DecisionRun:
    """A run over the rows of the pending choice of ``effect``."""

    return reveal._entry_run(make_run(state), entry_of(state, effect))


def choice_source(
    state: GameState, effect: str, constants: AIConstants = HARD
) -> Source:
    """The post-reveal key of the pending choice of ``effect``."""

    run = make_run(state, constants=constants)
    (source,) = reveal._choice_sources(run, [entry_of(state, effect)], {})
    return source


def best_post(run: DecisionRun, actions: tuple[DomainAction, ...]) -> str:
    """The unique highest ``PostValue`` among the actions' posts."""

    values = {
        str(dict(a.arguments)["post_id"]): run.profile.post_value(
            post_entity(str(dict(a.arguments)["post_id"]))
        )
        for a in actions
    }
    top = max(values.values())
    best = [post for post, value in values.items() if value == top]
    assert len(best) == 1
    return best[0]


def worst_post(run: DecisionRun, posts: tuple[str, ...]) -> str:
    values = {post: run.profile.post_value(post_entity(post)) for post in posts}
    low = min(values.values())
    worst = [post for post, value in values.items() if value == low]
    assert len(worst) == 1
    return worst[0]


# ===========================================================================
# Pending choices: rows of the Reveal frame, keys of the post-reveal prompt
# ===========================================================================


def test_revealed_choices_wait_on_the_reveal_frame() -> None:
    """Codec v147: no choice frame is pushed; each choice is a pending entry
    whose rows the Reveal frame offers, and no refusal is offered."""

    state = revealed(
        ["imperium:public_spectacle:0", "imperium:spacing_guild_s_favor:0"],
        resources=Resources(spice=5),
    )
    assert state.decision_stack[-1].kind == "reveal"
    entries = reveal._choice_entries(make_run(state))
    assert entries is not None
    assert [e.effect for e in entries] == [
        "place_spy",
        "may_pay_three_spice_for_influence",
    ]
    assert {a.action_id for a in entries[0].rows} == {"place_reveal_spy"}
    cards = {dict(a.arguments)["source"] for a in entries[0].rows}
    assert cards == {"public_spectacle"}
    assert {a.action_id for a in entries[1].rows} == {"pay_reveal_spice_influence"}
    assert not any(a.action_id.startswith("decline_") for a in legal(state))
    # The Explicit Spy key blocks the End Turn; the Optional key does not.
    sources = reveal._choice_sources(make_run(state), entries, {})
    assert [s.extra for s in sources] == [
        {"blocking": True, "explicit": True},
        {"blocking": False, "explicit": False},
    ]


def test_seated_corrinth_city_runs_immediately() -> None:
    """``CorrinthCityRevealAbility::CanRunImmediately`` = HighCouncilSeat: the
    seated owner's choice is a state-400 step after the printed gains, not a
    prompt key (option 1 is not ours: 5 Solari); unseated, it is a key."""

    hand = ["imperium:corrinth_city:0", "imperium:sardaukar_soldier:0"]
    seated = take_gains(
        revealed(hand, high_council=True, resources=Resources(solari=6))
    )
    run = make_run(seated, constants=NO_BUYS)
    entry = entry_of(seated, "gain_five_solari_or_take_high_council")
    assert reveal._outside_prompt(run, entry)
    action = reveal.reveal_window(run)
    assert action == find(seated, "gain_five_reveal_solari")
    unseated = take_gains(revealed(hand, resources=Resources(solari=6)))
    entry = entry_of(unseated, "gain_five_solari_or_take_high_council")
    assert not reveal._outside_prompt(make_run(unseated), entry)
    action = reveal.reveal_window(make_run(unseated, constants=NO_BUYS))
    assert action is not None and action in entry.rows


def test_recalled_spy_frame_places_on_the_best_post() -> None:
    state = revealed(
        ["imperium:public_spectacle:0"], spies_supply=0, spy_post_ids=FEYD_POSTS
    )
    state = apply(
        state, find(state, "recall_spy_for_reveal_placement", post_id=FEYD_POSTS[0])
    )
    assert dict(state.decision_stack[-1].context)["reveal_spy_recalled"] is True
    run = make_run(state)
    expected = best_post(make_run(state), run.by_id("place_reveal_spy"))
    action = reveal.reveal_choice_window(run)
    assert action == find(state, "place_reveal_spy", post_id=expected)


def test_a_choice_frame_other_than_the_recalled_spy_is_not_mirrored() -> None:
    """Our engine leaves no other choice frame on top: None (counted)."""

    state = revealed(
        ["imperium:public_spectacle:0"], spies_supply=0, spy_post_ids=FEYD_POSTS
    )
    state = apply(
        state, find(state, "recall_spy_for_reveal_placement", post_id=FEYD_POSTS[0])
    )
    frame = state.decision_stack[-1]
    for changes in ({"reveal_spy_recalled": False}, {"reveal_choice_effect": "x"}):
        context = {**dict(frame.context), **changes}
        fake = replace(frame, context=tuple(sorted(context.items())))
        odd = with_state(state, decision_stack=(*state.decision_stack[:-1], fake))
        assert reveal.reveal_choice_window(make_run(odd, actions=legal(state))) is None


def test_spy_key_with_an_empty_supply_recalls_the_worst_spy() -> None:
    state = take_gains(
        revealed(
            ["imperium:public_spectacle:0"], spies_supply=0, spy_post_ids=FEYD_POSTS
        )
    )
    expected = worst_post(make_run(state), FEYD_POSTS)
    recall = find(state, "recall_spy_for_reveal_placement", post_id=expected)
    run = entry_run(state, "place_spy")
    assert reveal._realise(run, "place_spy", Answer(1.0, ())) == recall
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == recall


def test_a_choice_key_answers_with_its_row(monkeypatch: pytest.MonkeyPatch) -> None:
    effect = "may_pay_three_spice_for_influence"
    state = take_gains(
        revealed(["imperium:spacing_guild_s_favor:0"], resources=Resources(spice=5))
    )
    answer = Answer(3.0, (("bene_gesserit",),), "SGF")
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility, "evaluate", lambda s, p, r: answer
    )
    pay = find(state, "pay_reveal_spice_influence", faction="bene_gesserit")
    source = choice_source(state, effect)
    assert source.evaluate is not None and source.evaluate() == (3.0, pay)
    run = make_run(state, constants=NO_BUYS)
    assert reveal.reveal_window(run) == pay
    assert run.memory.intents == {} and run.memory.data == {}


def test_an_optional_choice_worth_nothing_lapses_at_the_end_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The app's End Turn leaves its Optional keys: ``finish_reveal`` is the
    skip, and the engine lapses the unused choice (no refusal step)."""

    state = take_gains(
        revealed(["imperium:spacing_guild_s_favor:0"], resources=Resources(spice=5))
    )
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility,
        "evaluate",
        lambda s, p, r: Answer(0.0, (("fremen",),), "worth nothing"),
    )
    finish = find(state, "finish_reveal")
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == finish
    events = apply_whole(ENGINE, state, finish, legal_actions=legal(state)).events
    assert [e.kind for e in events if e.kind == "reveal_choice_lapsed"] == [
        "reveal_choice_lapsed"
    ]


def test_optional_keys_follow_their_value() -> None:
    """An Optional key is used iff its ``Evaluate`` value is > 0."""

    # Captured Mentat's E never finds an InfluenceDelta 2 info: value 0.
    mentat = take_gains(
        revealed(
            ["imperium:captured_mentat:0"], influence=Influence(emperor=1, fremen=1)
        )
    )
    effect = "may_lose_influence_to_gain_influence"
    source = choice_source(mentat, effect)
    assert source.evaluate is not None and source.evaluate()[0] == 0.0
    run = make_run(mentat, constants=NO_BUYS)
    assert reveal.reveal_window(run) == find(mentat, "finish_reveal")
    # Calculus of Power with a cheap Emperor card in play: trash it.
    calculus = take_gains(
        revealed(
            ["imperium:calculus_of_power:0", "imperium:sardaukar_soldier:0"],
            troops_conflict=2,
            troops_supply=7,
        )
    )
    run = make_run(calculus)
    ability_c = CalculusofPowerEmperorAbility(
        card_entity("imperium:calculus_of_power:0")
    )
    answer = ability_c.evaluate(
        run.profile,
        reveal._choice_request(
            run,
            "may_trash_other_emperor_for_three_strength",
            "imperium:calculus_of_power:0",
        ),
    )
    assert answer.value > 0.0
    assert answer.response == (("imperium:sardaukar_soldier:0",),)
    trash = find(
        calculus,
        "trash_reveal_card",
        card_id="imperium:sardaukar_soldier:0",
        source="calculus_of_power",
    )
    assert reveal.reveal_window(make_run(calculus, constants=NO_BUYS)) == trash


def test_explicit_key_uses_its_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desert Power (Explicit, value > 0): its answer. Real values: the
    2 Persuasion (with Buy Gains) beat a sandworm (``SandWorms`` 3.0 minus a
    water); a sandworm worth more takes the worm branch."""

    state = take_gains(
        revealed(
            ["imperium:desert_power:0"],
            maker_hooks=True,
            resources=Resources(water=2),
        )
    )
    answer = DesertPowerDeferredAbility(
        card_entity("imperium:desert_power:0")
    ).evaluate(make_run(state).profile, Request())
    assert answer.response == ((0,),)
    assert answer.value == pytest.approx(4.78)
    assert make_run(state).first("finish_reveal") is None  # mandatory
    action = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert action == find(state, "decline_reveal_sandworm")
    monkeypatch.setattr(Profile, "sandworm_value", lambda self, n, cpm=False: 20.0)
    action = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert action == find(state, "pay_reveal_water_for_sandworm")


def _desert_power_alone() -> tuple[GameState, tuple[DomainAction, ...]]:
    """Desert Power's pending choice as the only legal rows (a forced prompt
    with this one key)."""

    state = take_gains(
        revealed(
            ["imperium:desert_power:0"],
            maker_hooks=True,
            resources=Resources(water=2),
        )
    )
    return state, entry_of(state, "may_pay_water_for_sandworm").rows


@pytest.mark.parametrize(
    "answer",
    [Answer(0.0, None, "nothing"), Answer(0.0, ((1,),), "worth nothing")],
    ids=["no-response", "worth-nothing"],
)
def test_forced_key_worth_nothing_runs_with_a_random_row(
    monkeypatch: pytest.MonkeyPatch, answer: Answer
) -> None:
    """``MakeChoice`` keeps only a value > 0: a forced prompt whose single
    key is worth 0 goes to ``DefaultRandomChoice``, and the picked key runs
    with a random row of its own, whatever response the ability stored
    (engine-order.md §0)."""

    state, rows = _desert_power_alone()
    monkeypatch.setattr(
        DesertPowerDeferredAbility, "evaluate", lambda self, p, request: answer
    )
    picks = {
        reveal.reveal_window(make_run(state, rng_seed=seed, actions=rows))
        for seed in range(8)
    }
    assert {a.action_id for a in picks if a is not None} == {
        "pay_reveal_water_for_sandworm",
        "decline_reveal_sandworm",
    }


def test_seated_corrinth_city_worth_nothing_answers_at_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``CanRunImmediately`` run is a forced single-key prompt: value 0
    -> ``DefaultRandomChoice`` (our engine then offers only the Solari)."""

    calls: list[str] = []
    original = reveal._random_option

    def recording(run: DecisionRun, effect: str) -> DomainAction | None:
        calls.append(effect)
        return original(run, effect)

    monkeypatch.setattr(reveal, "_random_option", recording)
    hand = ["imperium:corrinth_city:0", "imperium:sardaukar_soldier:0"]
    seated = take_gains(
        revealed(hand, high_council=True, resources=Resources(solari=6))
    )
    solari = find(seated, "gain_five_reveal_solari")
    assert reveal.reveal_window(make_run(seated)) == solari
    assert calls == []
    monkeypatch.setattr(
        CorrinthCityRevealAbility,
        "evaluate",
        lambda self, p, request: Answer(0.0, ((0,),), "worth nothing"),
    )
    assert reveal.reveal_window(make_run(seated)) == solari
    assert calls == ["gain_five_solari_or_take_high_council"]


# -- realising each choice's answer -------------------------------------------------

_SPIES_2 = {"spy_post_ids": FEYD_POSTS[:2], "spies_supply": 1}


@pytest.mark.parametrize(
    ("hand", "effect", "changes", "answer", "expected"),
    [
        (
            ["imperium:spy_network:0"],
            "recall_spy_to_draw_intrigue_if_two_placed",
            _SPIES_2,
            ((FEYD_POSTS[1],),),
            ("recall_spy_for_reveal", {"post_id": FEYD_POSTS[1]}),
        ),
        (
            ["imperium:in_high_places:0"],
            "may_recall_two_spies_for_three_persuasion",
            _SPIES_2,
            ((FEYD_POSTS[1], FEYD_POSTS[0]),),  # unordered pair
            (
                "recall_spies_for_reveal",
                {"first_post_id": FEYD_POSTS[0], "second_post_id": FEYD_POSTS[1]},
            ),
        ),
        (
            ["imperium:captured_mentat:0"],
            "may_lose_influence_to_gain_influence",
            {"influence": Influence(emperor=1)},
            (("emperor",), ("fremen",)),  # the app's dead swap path
            (
                "exchange_reveal_influence",
                {"lost_faction": "emperor", "gained_faction": "fremen"},
            ),
        ),
        (
            ["imperium:calculus_of_power:0", "imperium:sardaukar_soldier:0"],
            "may_trash_other_emperor_for_three_strength",
            {},
            (("imperium:sardaukar_soldier:0",),),
            ("trash_reveal_card", {"card_id": "imperium:sardaukar_soldier:0"}),
        ),
        (
            ["imperium:calculus_of_power:0", "imperium:sardaukar_soldier:0"],
            "may_trash_other_emperor_for_three_strength",
            {},
            (("imperium:not_in_play:0",),),  # unrealisable -> not used
            None,
        ),
        (
            ["imperium:chani_clever_tactician:0"],
            "may_retreat_two_troops_for_four_strength",
            {"troops_conflict": 3, "troops_garrison": 0, "troops_supply": 9},
            (),
            ("retreat_two_troops_for_reveal", {}),
        ),
        (
            ["imperium:unswerving_loyalty:0", "imperium:fedaykin_stilltent:0"],
            "may_deploy_or_retreat_one_troop_if_fremen_bond",
            {"troops_conflict": 1, "troops_garrison": 2, "troops_supply": 9},
            ((0,),),
            ("deploy_reveal_card_troop", {}),
        ),
        (
            ["imperium:unswerving_loyalty:0", "imperium:fedaykin_stilltent:0"],
            "may_deploy_or_retreat_one_troop_if_fremen_bond",
            {"troops_conflict": 1, "troops_garrison": 2, "troops_supply": 9},
            ((1,),),
            ("retreat_reveal_card_troop", {}),
        ),
        (
            ["imperium:unswerving_loyalty:0", "imperium:fedaykin_stilltent:0"],
            "may_deploy_or_retreat_one_troop_if_fremen_bond",
            {"troops_conflict": 1, "troops_garrison": 0, "troops_supply": 11},
            ((0,),),  # garrison empty: index 0 is the retreat
            ("retreat_reveal_card_troop", {}),
        ),
        (
            ["imperium:unswerving_loyalty:0", "imperium:fedaykin_stilltent:0"],
            "may_deploy_or_retreat_one_troop_if_fremen_bond",
            {"troops_conflict": 0, "troops_garrison": 2, "troops_supply": 10},
            ((1,),),  # the app's retreat index with no deployed troop
            None,
        ),
        (
            ["imperium:corrinth_city:0"],
            "gain_five_solari_or_take_high_council",
            {"resources": Resources(solari=6)},
            ((1,),),
            ("take_high_council_from_reveal", {}),
        ),
        (
            ["imperium:corrinth_city:0"],
            "gain_five_solari_or_take_high_council",
            {"resources": Resources(solari=6)},
            ((0,),),
            ("gain_five_reveal_solari", {}),
        ),
        (
            ["imperium:desert_power:0"],
            "may_pay_water_for_sandworm",
            {"maker_hooks": True, "resources": Resources(water=2)},
            ((1,),),
            ("pay_reveal_water_for_sandworm", {}),
        ),
        (
            ["imperium:desert_power:0"],
            "may_pay_water_for_sandworm",
            {"maker_hooks": True, "resources": Resources(water=2)},
            ((0,),),
            ("decline_reveal_sandworm", {}),
        ),
        (
            ["imperium:delivery_agreement:0"],
            "keep_spice_or_trash_self_for_vp_if_four_contracts",
            {"completed_contract_ids": tuple(f"contract:x{i}" for i in range(4))},
            ((1,),),
            ("trash_contract_reveal_for_vp", {}),
        ),
        (
            ["imperium:delivery_agreement:0"],
            "keep_spice_or_trash_self_for_vp_if_four_contracts",
            {"completed_contract_ids": tuple(f"contract:x{i}" for i in range(4))},
            ((0,),),
            ("keep_contract_reveal_spice", {}),
        ),
        (
            ["imperium:undercover_asset:0"],
            "place_spy_or_gain_two_strength",
            {},
            ((1,),),
            ("gain_two_reveal_strength", {}),
        ),
    ],
)
def test_choice_answer_maps_to_its_row(
    hand: list[str],
    effect: str,
    changes: dict[str, object],
    answer: tuple[ResponseItem, ...],
    expected: tuple[str, dict[str, object]] | None,
) -> None:
    """``_realise`` over the entry's rows (offered from the Reveal's start,
    before the gains); an Optional answer no row carries realises nothing
    (the choice is not used)."""

    state = revealed(hand, **changes)
    action = reveal._realise(entry_run(state, effect), effect, Answer(1.0, answer))
    if expected is None:
        assert action is None
    else:
        assert action == find(state, expected[0], **expected[1])


def test_undercover_asset_spy_answer_places_or_recalls() -> None:
    effect = "place_spy_or_gain_two_strength"
    state = take_gains(revealed(["imperium:undercover_asset:0"]))
    run = entry_run(state, effect)
    expected = best_post(make_run(state), run.by_id("place_reveal_spy"))
    assert reveal._realise(run, effect, Answer(1.0, ((0,),))) == find(
        state, "place_reveal_spy", post_id=expected, source="undercover_asset"
    )
    empty = take_gains(
        revealed(
            ["imperium:undercover_asset:0"], spies_supply=0, spy_post_ids=FEYD_POSTS
        )
    )
    run = entry_run(empty, effect)
    expected = worst_post(make_run(empty), FEYD_POSTS)
    assert reveal._realise(run, effect, Answer(1.0, ((0,),))) == find(
        empty, "recall_spy_for_reveal_placement", post_id=expected
    )


def test_seated_corrinth_option_one_falls_back_to_solari() -> None:
    """Our engine offers a seated owner only the 5 Solari (module judgement)."""

    state = take_gains(
        revealed(
            ["imperium:corrinth_city:0"],
            high_council=True,
            resources=Resources(solari=6),
        )
    )
    run = entry_run(state, "gain_five_solari_or_take_high_council")
    action = reveal._realise(
        run, "gain_five_solari_or_take_high_council", Answer(9.0, ((1,),))
    )
    assert action is not None and action.action_id == "gain_five_reveal_solari"


# ===========================================================================
# reveal: automatic gains
# ===========================================================================


def test_automatic_gains_run_first_in_app_order() -> None:
    """State 300 printed gains by reveal position, then the state-400
    immediate (Treacherous Maneuver's ``RevealGainIntrigueAbility``)."""

    state = revealed(
        [
            "imperium:treacherous_maneuver:0",
            "imperium:rebel_supplier:0",
            "imperium:junction_headquarters:0",
        ]
    )
    picks = []
    for _ in range(4):
        action = reveal.reveal_window(make_run(state))
        assert action is not None
        picks.append((action.action_id, dict(action.arguments)))
        state = apply(state, action)
    assert picks == [
        ("gain_reveal_resources", {"solari": 0, "spice": 1, "water": 0}),
        ("recruit_reveal_troops", {}),
        ("gain_reveal_resources", {"solari": 0, "spice": 0, "water": 1}),
        ("draw_reveal_intrigue", {}),
    ]
    assert reveal.reveal_window(make_run(state)) is not None


def test_smugglers_haven_spice_is_a_state_400_gain() -> None:
    """``SmugglersHavenRevealAbility`` is an ``AlwaysRunImmediately`` deferred
    ability (state 400): its 2 Spice follow a later card's printed state-300
    gains (Junction Headquarters' troop and water)."""

    state = revealed(
        ["imperium:smuggler_s_haven:0", "imperium:junction_headquarters:0"],
        spy_post_ids=("arrakis-hagga-basin",),
        spies_supply=2,
    )
    picks = []
    for _ in range(3):
        action = reveal.reveal_window(make_run(state))
        assert action is not None
        picks.append((action.action_id, dict(action.arguments)))
        state = apply(state, action)
    assert picks == [
        ("recruit_reveal_troops", {}),
        ("gain_reveal_resources", {"solari": 0, "spice": 0, "water": 1}),
        ("gain_reveal_resources", {"solari": 0, "spice": 2, "water": 0}),
    ]


def test_shishakli_influence_is_an_explicit_prompt_key() -> None:
    """``CrysknifeAbility``: Explicit, not auto-run, E = DeferValue 2."""

    state = revealed(["imperium:shishakli:0", "imperium:fedaykin_stilltent:0"])
    first = reveal.reveal_window(make_run(state))
    assert first == find(state, "gain_reveal_resources", solari=0, spice=0, water=1)
    state = apply(state, first)
    run = make_run(state, constants=NO_BUYS)
    influence = find(state, "gain_reveal_faction_influence", faction="fremen")
    sources = reveal._gain_sources(run)
    assert sources is not None
    (source,) = [s for s in sources if influence in s.actions]
    assert source.stage is Stage.PROMPT
    assert source.extra == {"blocking": True, "explicit": True}
    assert source.evaluate is not None and source.evaluate() == (2.0, influence)
    assert run.first("finish_reveal") is None
    assert reveal.reveal_window(run) == influence


# ===========================================================================
# reveal: the post-reveal prompt
# ===========================================================================


def _acquire_values(run: DecisionRun) -> dict[DomainAction, float]:
    values: dict[DomainAction, float] = {}
    for action in run.legal:
        args = dict(action.arguments)
        if action.action_id == "acquire_reserve":
            card = card_entity(f"reserve:{args['card_id']}")
        elif action.action_id.startswith("acquire_"):
            card = card_entity(str(args["instance_id"]))
        else:
            continue
        values[action] = AcquireAbility(card).evaluate(run.profile, Request()).value
    return values


def test_the_best_card_is_acquired() -> None:
    state = take_gains(revealed(["imperium:steersman:0"], reveal_persuasion_bonus=12))
    values = _acquire_values(make_run(state))
    assert len(values) == 7  # five Row cards and both Reserve piles
    best = max(values.values())
    assert best > 0.0 and list(values.values()).count(best) == 1
    expected = next(a for a, v in values.items() if v == best)
    assert reveal.reveal_window(make_run(state)) == expected


def test_reserve_piles_are_acquire_reserve_keys() -> None:
    state = take_gains(revealed(["imperium:steersman:0"], reveal_persuasion_bonus=12))
    state = with_state(state, imperium_row=())
    run = make_run(state)
    values = _acquire_values(run)
    assert {a.action_id for a in values} == {"acquire_reserve"}
    sources = reveal._acquire_sources(run)
    assert [s.label for s in sources] == [
        "Acquire reserve:prepare_the_way",
        "Acquire reserve:the_spice_must_flow",
    ]
    best = max(values, key=lambda a: values[a])
    assert values[best] > 0.0
    assert reveal.reveal_window(make_run(state)) == best


def test_a_set_aside_card_is_an_acquire_key() -> None:
    """Manipulate's set-aside card joins the list (``FindSetAside``)."""

    state = take_gains(
        revealed(
            ["imperium:steersman:0"],
            reveal_persuasion_bonus=12,
            imperium_set_aside=("imperium:guild_spy:0",),
        )
    )
    state = with_state(
        state,
        imperium_row=(),
        reserve_stacks=(("prepare_the_way", 0), ("the_spice_must_flow", 0)),
    )
    run = make_run(state)
    (source,) = reveal._acquire_sources(run)
    action = find(
        state, "acquire_manipulated_imperium", instance_id="imperium:guild_spy:0"
    )
    assert source.actions == (action,)
    value = AcquireAbility(card_entity("imperium:guild_spy:0")).evaluate(
        run.profile, Request()
    )
    assert source.evaluate is not None and source.evaluate() == (value.value, action)
    expected = action if value.value > 0.0 else find(state, "finish_reveal")
    assert reveal.reveal_window(make_run(state)) == expected


def test_nothing_positive_ends_the_turn() -> None:
    state = take_gains(revealed(["imperium:steersman:0"], reveal_persuasion_bonus=12))
    action = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert action == find(state, "finish_reveal")


def test_a_choice_key_competes_with_buys(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pending choice is one key of the same prompt as the buys (the app's
    own list): the higher value wins."""

    state = take_gains(
        revealed(
            ["imperium:spacing_guild_s_favor:0"],
            resources=Resources(spice=5),
            reveal_persuasion_bonus=12,
        )
    )
    pay = find(state, "pay_reveal_spice_influence", faction="fremen")
    answer = Answer(7.0, (("fremen",),), "patched")
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility, "evaluate", lambda s, p, r: answer
    )
    monkeypatch.setattr(
        AcquireAbility, "evaluate", lambda s, p, r: Answer(6.0, (), "buy")
    )
    run = make_run(state)
    assert reveal.reveal_window(run) == pay
    monkeypatch.setattr(
        AcquireAbility, "evaluate", lambda s, p, r: Answer(8.0, (), "buy")
    )
    action = reveal.reveal_window(make_run(state))
    assert action is not None and action.action_id.startswith("acquire_")


def test_end_turn_is_one_answer_with_optional_choices_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12 §4.3: one ``MakeChoice`` gives the empty answer and the turn ends.
    Two Optional choices worth nothing hold nothing back: ``finish_reveal``
    after a single evaluation of the prompt, and both lapse."""

    state = take_gains(
        revealed(
            ["imperium:captured_mentat:0", "imperium:spacing_guild_s_favor:0"],
            influence=Influence(emperor=1),
            resources=Resources(spice=5),
        )
    )
    entries = reveal._choice_entries(make_run(state))
    assert entries is not None and len(entries) == 2
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility,
        "evaluate",
        lambda self, p, request: Answer(0.0, (("fremen",),), "worth nothing"),
    )
    prompts: list[int] = []
    original = decide

    def counting(
        run: DecisionRun,
        sources: list[Source],
        *,
        skip: DomainAction | None,
        forced: bool | Callable[[], bool] | None = None,
    ) -> DomainAction | None:
        prompts.append(len(sources))
        return original(run, sources, skip=skip, forced=forced)

    monkeypatch.setattr(reveal, "decide", counting)
    memory = Memory()
    finish = find(state, "finish_reveal")
    assert reveal.reveal_window(make_run(state, memory, constants=NO_BUYS)) == finish
    assert len(prompts) == 1
    assert memory.intents == {} and memory.data == {}
    events = apply_whole(ENGINE, state, finish, legal_actions=legal(state)).events
    lapsed = [
        dict(e.payload)["effect"] for e in events if e.kind == "reveal_choice_lapsed"
    ]
    assert sorted(lapsed) == sorted(e.effect for e in entries)


def test_end_turn_mark_finishes_or_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_END_TURN`` (a declined subcommittee offer) takes ``finish_reveal``
    without a second ``MakeChoice``; a mark from another Reveal, or one that
    meets a blocked finish, is dropped and the prompt is evaluated."""

    plain = take_gains(revealed(["imperium:steersman:0"]))
    memory = Memory()
    memory.data[reveal._END_TURN] = (plain.round_number, owner(plain))

    def no_prompt(*args: object, **kwargs: object) -> DomainAction | None:
        raise AssertionError("the empty answer is not asked again")

    with monkeypatch.context() as patch:
        patch.setattr(reveal, "decide", no_prompt)
        run = make_run(plain, memory)
        assert reveal.reveal_window(run) == find(plain, "finish_reveal")
    assert reveal._END_TURN not in memory.data
    state = take_gains(revealed(["imperium:public_spectacle:0"]))
    spy = entry_of(state, "place_spy")
    for mark in [(state.round_number, owner(state)), (state.round_number - 1, 0)]:
        memory = Memory()
        memory.data[reveal._END_TURN] = mark
        action = reveal.reveal_window(make_run(state, memory, constants=NO_BUYS))
        assert action is not None and action in spy.rows
        assert reveal._END_TURN not in memory.data


def test_each_pending_entry_is_its_own_key() -> None:
    """Delivery Agreement (1 Spice) and Priority Contracts (2 Spice) share a
    choice effect: two keys, each valued by its own card and answered with
    its own ``source`` row; two copies of one card are two keys too."""

    effect = "keep_spice_or_trash_self_for_vp_if_four_contracts"
    state = take_gains(
        revealed(["imperium:priority_contracts:0", "imperium:delivery_agreement:0"])
    )
    run = make_run(state)
    entries = reveal._choice_entries(run)
    assert entries is not None
    assert [(e.card, e.effect) for e in entries] == [
        ("imperium:priority_contracts:0", effect),
        ("imperium:delivery_agreement:0", effect),
    ]
    used: dict[DomainAction, tuple[reveal._Entry, Answer]] = {}
    sources = reveal._choice_sources(run, entries, used)
    values = []
    for source, card in zip(
        sources, ("priority_contracts", "delivery_agreement"), strict=True
    ):
        assert source.evaluate is not None
        value, action = source.evaluate()
        assert action == find(state, "keep_contract_reveal_spice", source=card)
        assert used[action][1].response == ((0,),)
        values.append(value)
    assert values == [
        pytest.approx(run.profile.spice_value(2)),
        pytest.approx(run.profile.spice_value(1)),
    ]
    twins = take_gains(
        revealed(["imperium:public_spectacle:0", "imperium:public_spectacle:1"])
    )
    entries = reveal._choice_entries(make_run(twins))
    assert entries is not None and len(entries) == 2
    assert entries[0].rows == entries[1].rows


def test_covert_operation_places_its_two_spies_as_two_keys() -> None:
    """``place_two_spies`` is a key valued by ``SpyValue`` that places one
    Spy; the second icon waits as a fresh ``place_spy`` entry of the same
    card and is its own key of the re-issued prompt."""

    state = take_gains(revealed(["imperium:covert_operation:0"]))
    entry = entry_of(state, "place_two_spies")
    run = make_run(state, constants=NO_BUYS)
    (source,) = reveal._choice_sources(run, [entry], {})
    assert source.evaluate is not None
    value, _action = source.evaluate()
    assert value == pytest.approx(run.profile.spy_value().sum)
    expected = best_post(make_run(state), make_run(state).by_id("place_reveal_spy"))
    placed = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert placed == find(
        state, "place_reveal_spy", post_id=expected, source="covert_operation"
    )
    state = apply(state, placed)
    second = entry_of(state, "place_spy")
    assert second.card == "imperium:covert_operation:0"
    action = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert action is not None and action in second.rows


def test_unmirrored_blockers_fall_back() -> None:
    """``None`` (the agent falls back) when finish is blocked by something
    with no app key, a choice row belongs to no pending entry, or an action
    is not one this adapter knows."""

    state = take_gains(revealed(["imperium:steersman:0"]))
    seat = owner(state)
    no_finish = tuple(a for a in legal(state) if a.action_id != "finish_reveal")
    assert reveal.reveal_window(make_run(state, actions=no_finish)) is None
    ghosts = [
        DomainAction(
            "resume_reveal_choice",
            seat,
            (("effect", "may_pay_three_spice_for_influence"),),
        ),
        DomainAction(
            "trash_reveal_card",
            seat,
            (("card_id", "imperium:steersman:0"), ("source", "calculus_of_power")),
        ),
    ]
    for ghost in ghosts:
        run = make_run(state, actions=(*legal(state), ghost))
        assert reveal.reveal_window(run) is None


def test_explicit_blocker_is_resolved_by_value() -> None:
    state = take_gains(revealed(["imperium:public_spectacle:0"]))
    assert make_run(state).first("finish_reveal") is None
    source = choice_source(state, "place_spy", NO_BUYS)
    assert source.extra == {"blocking": True, "explicit": True}
    assert source.evaluate is not None
    value, action = source.evaluate()
    assert value == pytest.approx(make_run(state).profile.spy_value().sum)
    expected = best_post(make_run(state), make_run(state).by_id("place_reveal_spy"))
    assert action == find(state, "place_reveal_spy", post_id=expected)
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == action


def test_forced_prompt_with_nothing_positive_picks_at_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DefaultRandomChoice`` over the whole list (a buy worth 0 too, an
    Optional choice worth 0 too); a choice key picked so runs with a random
    row of its own (Spacing Guild's Favor: a random track)."""

    state = take_gains(
        revealed(
            ["imperium:public_spectacle:0", "imperium:spacing_guild_s_favor:0"],
            resources=Resources(spice=5),
        )
    )
    monkeypatch.setattr(
        PlaceSpyRevealAbility, "evaluate", lambda s, p, r: Answer(0.0, ())
    )
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility,
        "evaluate",
        lambda s, p, r: Answer(0.0, (("fremen",),)),
    )
    picks: Counter[str] = Counter()
    factions: set[object] = set()
    for seed in range(40):
        run = make_run(state, constants=NO_BUYS, rng_seed=seed)
        action = reveal.reveal_window(run)
        assert action is not None
        picks[action.action_id] += 1
        if action.action_id == "pay_reveal_spice_influence":
            factions.add(dict(action.arguments)["faction"])
        assert run.memory.intents == {}
    assert set(picks) >= {
        "place_reveal_spy",
        "pay_reveal_spice_influence",
        "acquire_imperium",
    }
    assert len(factions) > 1


def test_track_spy_is_an_explicit_spy_value_key() -> None:
    state = take_gains(revealed(["imperium:steersman:0"]))
    state = with_state(state, pending_track_spies=((owner(state), "test"),))
    run = make_run(state, constants=NO_BUYS)
    track = find(state, "place_track_spy")
    assert run.first("finish_reveal") is None
    (source,) = reveal._track_spy_source(run)
    assert source.extra == {"blocking": True, "explicit": True}
    spy = PlaceSpyCustomAbility(track_entity("emperor"))
    assert spy.evaluate(run.profile, Request()).value == pytest.approx(
        run.profile.spy_value().sum
    )
    assert reveal.reveal_window(run) == track


def test_plot_keys_come_from_the_intrigue_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = take_gains(
        revealed(
            ["imperium:steersman:0"],
            intrigue_cards=("intrigue:buy_access:0",),
            resources=Resources(solari=10, spice=10, water=3),
        )
    )
    plays = make_run(state).by_id("play_intrigue")
    assert plays
    calls: list[bool] = []

    def plot_sources(
        run: DecisionRun, actions: tuple[DomainAction, ...], *, combat: bool
    ) -> list[Source]:
        calls.append(combat)
        assert actions == plays
        return [Source("Plot", Stage.PROMPT, actions, lambda: (500.0, actions[0]))]

    monkeypatch.setattr(reveal, "intrigue_play_sources", plot_sources)
    assert reveal.reveal_window(make_run(state)) == plays[0]
    assert calls == [False]


def test_non_core_reveal_action_is_not_mirrored() -> None:
    state = take_gains(revealed(["imperium:steersman:0"]))
    odd = DomainAction(action_id="resolve_command_choice", actor=owner(state))
    run = make_run(state, actions=(*legal(state), odd))
    assert reveal.reveal_window(run) is None


def test_gain_action_without_its_pending_entry_is_not_mirrored() -> None:
    state = take_gains(revealed(["imperium:steersman:0"]))
    odd = DomainAction(action_id="advance_reveal_research", actor=owner(state))
    run = make_run(state, actions=(*legal(state), odd))
    assert reveal.reveal_window(run) is None


# -- leader keys ----------------------------------------------------------------


def test_devious_strength_needs_its_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """``DeviousStrengthAbility.Cost``: a spy out and a unit in the Conflict;
    without a unit the key is not in the list (our engine still offers it)."""

    monkeypatch.setattr(
        DeviousStrengthAbility,
        "evaluate",
        lambda s, p, r: Answer(100.0, ((FEYD_POSTS[1],),)),
    )
    state = take_gains(
        revealed(["imperium:steersman:0"], spy_post_ids=FEYD_POSTS[:2], spies_supply=1)
    )
    assert state.players[owner(state)].leader_id == "feyd_rautha_harkonnen"
    assert make_run(state).by_id("recall_spy_for_leader")
    action = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert action == find(state, "finish_reveal")
    armed = take_gains(
        revealed(
            ["imperium:steersman:0"],
            spy_post_ids=FEYD_POSTS[:2],
            spies_supply=1,
            troops_conflict=2,
            troops_supply=7,
        )
    )
    action = reveal.reveal_window(make_run(armed, constants=NO_BUYS))
    assert action == find(armed, "recall_spy_for_leader", post_id=FEYD_POSTS[1])


def test_devious_strength_in_the_last_round_recalls_the_worst_spy() -> None:
    """Real E: the final round with fewer than 3 spies -> 100 ("Last Round"),
    the spy on the worst post."""

    state = take_gains(
        revealed(
            ["imperium:steersman:0"],
            spy_post_ids=(FEYD_POSTS[0], FEYD_POSTS[2]),
            spies_supply=1,
            troops_conflict=2,
            troops_supply=7,
            victory_points=10,
        )
    )
    run = make_run(state, constants=NO_BUYS)
    assert run.profile.is_final_round()
    expected = worst_post(make_run(state), (FEYD_POSTS[0], FEYD_POSTS[2]))
    assert reveal.reveal_window(run) == find(
        state, "recall_spy_for_leader", post_id=expected
    )


@pytest.mark.parametrize(("troops", "retreat"), [(2, False), (6, True)])
def test_desert_scouts_retreats_when_get_troops_to_retreat_says_so(
    troops: int, retreat: bool
) -> None:
    state = take_gains(
        revealed(
            ["imperium:steersman:0"],
            leader_id="lady_amber_metulli",
            leader_face_id="lady_amber_metulli",
            troops_conflict=troops,
            troops_garrison=0,
            troops_supply=12 - troops,
        )
    )
    run = make_run(state, constants=NO_BUYS)
    assert (run.profile.troops_to_retreat(1) > 0) is retreat
    expected = "retreat_leader_troop" if retreat else "finish_reveal"
    assert reveal.reveal_window(run) == find(state, expected)


# ===========================================================================
# acquisition_spy
# ===========================================================================


def _bought_spy_network(**changes: object) -> GameState:
    state = take_gains(
        revealed(["imperium:steersman:0"], reveal_persuasion_bonus=12, **changes)
    )
    state = with_state(state, imperium_row=("imperium:spy_network:0",))
    state = apply(
        state, find(state, "acquire_imperium", instance_id="imperium:spy_network:0")
    )
    assert state.decision_stack[-1].kind == "acquisition_spy"
    return state


def test_acquisition_spy_goes_to_the_best_post() -> None:
    state = _bought_spy_network()
    run = make_run(state)
    expected = best_post(make_run(state), run.by_id("place_acquisition_spy"))
    assert reveal.acquisition_spy_window(run) == find(
        state, "place_acquisition_spy", post_id=expected
    )


def test_acquisition_spy_with_an_empty_supply_recalls_first() -> None:
    state = _bought_spy_network(spies_supply=0, spy_post_ids=FEYD_POSTS)
    assert make_run(state).first("decline_acquisition_spy") is not None
    expected = worst_post(make_run(state), FEYD_POSTS)
    assert reveal.acquisition_spy_window(make_run(state)) == find(
        state, "recall_spy_for_acquisition", post_id=expected
    )


# ===========================================================================
# Coverage: full games
# ===========================================================================


def test_full_games_never_fall_back_in_these_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four app_ai seats, base and CHOAM, rotated leaders: every ``reveal``,
    ``reveal_choice`` and ``acquisition_spy`` decision is mirrored.

    Only this module's handlers are installed (the other windows fall back
    to the heuristic), so the test does not depend on their progress.
    """

    def only_reveal(kind: str | None) -> Callable[[DecisionRun], object] | None:
        return None if kind is None else reveal.HANDLERS.get(kind)

    monkeypatch.setattr(agent_module, "handler_for", only_reveal)
    mirrored: Counter[str] = Counter()
    for game in range(6):
        choam = game % 2 == 1
        seed = 40 + game
        leaders = tuple(
            random.Random(seed).sample(
                [leader.leader_id for leader in leaders_for_choam(choam)], k=4
            )
        )
        agents = tuple(AppAIAgent(seed=900 + 10 * game + seat) for seat in range(4))
        result = run_policy_game(
            UprisingRulesEngine(leader_ids=leaders),
            RulesetConfig(choam_module=choam),
            seed,
            agents,
        )
        assert result.state.phase is GamePhase.FINISHED
        for agent in agents:
            for kind in reveal.HANDLERS:
                assert agent.fallbacks[kind] == 0, (game, kind)
                mirrored[kind] += agent.mirrored[kind]
    # A ``reveal_choice`` frame stays on top only after a Spy recalled for a
    # placement: once in these six games.
    assert all(mirrored[kind] > 0 for kind in reveal.HANDLERS), mirrored
