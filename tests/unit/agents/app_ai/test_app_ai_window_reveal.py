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
    CapturedMentatRevealAbility,
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
    return ENGINE.legal_actions(state, owner(state))


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
    return ENGINE.apply(state, action, legal_actions=legal(state)).state


def revealed(hand: list[str], **changes: object) -> GameState:
    """A real Reveal turn of the first turn's seat (Feyd, seed 3) with ``hand``."""

    state = first_decision("turn", choam=True, seed=3)
    state = with_player(state, owner(state), hand=tuple(hand), **changes)
    return apply(state, find(state, "reveal_turn"))


def defer_all(state: GameState) -> GameState:
    while state.decision_stack[-1].kind == "reveal_choice":
        state = apply(state, find(state, "defer_reveal_choice"))
    return state


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


def resumed(hand: list[str], effect: str, **changes: object) -> GameState:
    """``hand`` revealed, every choice deferred, then ``effect`` resumed."""

    state = defer_all(revealed(hand, **changes))
    return apply(state, find(state, "resume_reveal_choice", effect=effect))


def intent_run(
    state: GameState, effect: str, intent: object, *, rng_seed: int = 0
) -> DecisionRun:
    """A run whose memory holds the Reveal window's intent for ``effect``."""

    memory = Memory()
    memory.intents[("reveal_choice", state.round_number, effect)] = intent
    return make_run(state, memory, rng_seed=rng_seed)


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
# reveal_choice
# ===========================================================================


def test_initial_choice_frame_is_deferred() -> None:
    state = revealed(["imperium:public_spectacle:0", "imperium:desert_power:0"])
    assert state.decision_stack[-1].kind == "reveal_choice"
    action = reveal.reveal_choice_window(make_run(state))
    assert action is not None and action.action_id == "defer_reveal_choice"


def test_seated_corrinth_city_runs_immediately() -> None:
    """``CorrinthCityRevealAbility::CanRunImmediately`` = HighCouncilSeat: the
    seated owner's choice is answered at once (option 1 is not ours: 5 Solari)."""

    hand = ["imperium:corrinth_city:0", "imperium:sardaukar_soldier:0"]
    seated = revealed(hand, high_council=True, resources=Resources(solari=6))
    action = reveal.reveal_choice_window(make_run(seated))
    assert action is not None and action.action_id == "gain_five_reveal_solari"
    unseated = revealed(hand, resources=Resources(solari=6))
    action = reveal.reveal_choice_window(make_run(unseated))
    assert action is not None and action.action_id == "defer_reveal_choice"


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


def test_resumed_spy_with_empty_supply_recalls_the_worst_spy() -> None:
    state = resumed(
        ["imperium:public_spectacle:0"],
        "place_spy",
        spies_supply=0,
        spy_post_ids=FEYD_POSTS,
    )
    run = intent_run(state, "place_spy", Answer(1.0, (), "Place Spy"))
    expected = worst_post(make_run(state), FEYD_POSTS)
    action = reveal.reveal_choice_window(run)
    assert action == find(state, "recall_spy_for_reveal_placement", post_id=expected)


def test_intent_answer_is_realised_and_consumed() -> None:
    state = resumed(
        ["imperium:spacing_guild_s_favor:0"],
        "may_pay_three_spice_for_influence",
        resources=Resources(spice=5),
    )
    run = intent_run(
        state,
        "may_pay_three_spice_for_influence",
        Answer(3.0, (("bene_gesserit",),), "SGF"),
    )
    action = reveal.reveal_choice_window(run)
    assert action == find(state, "pay_reveal_spice_influence", faction="bene_gesserit")
    assert run.memory.intents == {}


def test_decline_intent_declines() -> None:
    state = resumed(
        ["imperium:spacing_guild_s_favor:0"],
        "may_pay_three_spice_for_influence",
        resources=Resources(spice=5),
    )
    run = intent_run(state, "may_pay_three_spice_for_influence", "decline")
    action = reveal.reveal_choice_window(run)
    assert action is not None and action.action_id == "decline_reveal_spice_influence"


def test_random_intent_runs_the_ability_with_a_random_target() -> None:
    """``DefaultRandomChoice``: an Optional key picked at random is used."""

    state = resumed(
        ["imperium:spacing_guild_s_favor:0"],
        "may_pay_three_spice_for_influence",
        resources=Resources(spice=5),
    )
    seen = set()
    for seed in range(8):
        run = intent_run(
            state, "may_pay_three_spice_for_influence", "random", rng_seed=seed
        )
        action = reveal.reveal_choice_window(run)
        assert action is not None
        assert action.action_id == "pay_reveal_spice_influence"
        seen.add(dict(action.arguments)["faction"])
    assert len(seen) > 1


def test_resumed_optional_without_intent_follows_its_value() -> None:
    """No intent (the Reveal decision had one legal action): an Optional
    ability is used iff its ``Evaluate`` value is > 0."""

    # Captured Mentat's E never finds an InfluenceDelta 2 info: value 0.
    mentat = resumed(
        ["imperium:captured_mentat:0"],
        "may_lose_influence_to_gain_influence",
        influence=Influence(emperor=1, fremen=1),
    )
    run = make_run(mentat)
    ability = CapturedMentatRevealAbility(card_entity("imperium:captured_mentat:0"))
    request = reveal._choice_request(
        run, "may_lose_influence_to_gain_influence", "imperium:captured_mentat:0"
    )
    assert ability.evaluate(run.profile, request).value == 0.0
    action = reveal.reveal_choice_window(run)
    assert action is not None
    assert action.action_id == "decline_reveal_influence_exchange"
    # Calculus of Power with a cheap Emperor card in play: trash it.
    calculus = resumed(
        ["imperium:calculus_of_power:0", "imperium:sardaukar_soldier:0"],
        "may_trash_other_emperor_for_three_strength",
        troops_conflict=2,
        troops_supply=7,
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
    action = reveal.reveal_choice_window(make_run(calculus))
    assert action == find(
        calculus, "trash_reveal_card", card_id="imperium:sardaukar_soldier:0"
    )


def test_resumed_explicit_without_intent_uses_its_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desert Power (Explicit, value > 0): its answer. Real values: the
    2 Persuasion (with Buy Gains) beat a sandworm (``SandWorms`` 3.0 minus a
    water); a sandworm worth more takes the worm branch."""

    state = resumed(
        ["imperium:desert_power:0"],
        "may_pay_water_for_sandworm",
        maker_hooks=True,
        resources=Resources(water=2),
    )
    answer = DesertPowerDeferredAbility(
        card_entity("imperium:desert_power:0")
    ).evaluate(make_run(state).profile, Request())
    assert answer.response == ((0,),)
    assert answer.value == pytest.approx(4.78)
    action = reveal.reveal_choice_window(make_run(state))
    assert action == find(state, "decline_reveal_sandworm")
    monkeypatch.setattr(Profile, "sandworm_value", lambda self, n, cpm=False: 20.0)
    action = reveal.reveal_choice_window(make_run(state))
    assert action == find(state, "pay_reveal_water_for_sandworm")


def test_explicit_without_a_response_answers_at_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = resumed(
        ["imperium:desert_power:0"],
        "may_pay_water_for_sandworm",
        maker_hooks=True,
        resources=Resources(water=2),
    )
    monkeypatch.setattr(
        DesertPowerDeferredAbility,
        "evaluate",
        lambda self, p, request: Answer(0.0, None, "nothing"),
    )
    picks = {
        reveal.reveal_choice_window(make_run(state, rng_seed=seed)) for seed in range(8)
    }
    assert {a.action_id for a in picks if a is not None} == {
        "pay_reveal_water_for_sandworm",
        "decline_reveal_sandworm",
    }


def test_explicit_worth_nothing_answers_at_random_despite_its_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``MakeChoice`` keeps only a value > 0: a forced prompt whose single
    key is worth 0 goes to ``DefaultRandomChoice`` even though the ability
    stored a response (engine-order.md §0)."""

    state = resumed(
        ["imperium:desert_power:0"],
        "may_pay_water_for_sandworm",
        maker_hooks=True,
        resources=Resources(water=2),
    )
    monkeypatch.setattr(
        DesertPowerDeferredAbility,
        "evaluate",
        lambda self, p, request: Answer(0.0, ((1,),), "worth nothing"),
    )
    picks = {
        reveal.reveal_choice_window(make_run(state, rng_seed=seed)) for seed in range(8)
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
    seated = revealed(hand, high_council=True, resources=Resources(solari=6))
    solari = find(seated, "gain_five_reveal_solari")
    assert reveal.reveal_choice_window(make_run(seated)) == solari
    assert calls == []
    monkeypatch.setattr(
        CorrinthCityRevealAbility,
        "evaluate",
        lambda self, p, request: Answer(0.0, ((0,),), "worth nothing"),
    )
    assert reveal.reveal_choice_window(make_run(seated)) == solari
    assert calls == ["gain_five_solari_or_take_high_council"]


def test_decline_intent_without_a_decline_action_is_evaluated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desert Power has no decline action: a ``"decline"`` intent is
    consumed and the ability's own answer is used."""

    state = resumed(
        ["imperium:desert_power:0"],
        "may_pay_water_for_sandworm",
        maker_hooks=True,
        resources=Resources(water=2),
    )
    monkeypatch.setattr(Profile, "sandworm_value", lambda self, n, cpm=False: 20.0)
    run = intent_run(state, "may_pay_water_for_sandworm", "decline")
    action = reveal.reveal_choice_window(run)
    assert action == find(state, "pay_reveal_water_for_sandworm")
    assert run.memory.intents == {}


def test_non_core_choice_is_not_mirrored() -> None:
    state = revealed(["imperium:public_spectacle:0"])
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["reveal_choice_effect"] = "command_place_spy"
    fake = replace(frame, context=tuple(sorted(context.items())))
    odd = with_state(state, decision_stack=(*state.decision_stack[:-1], fake))
    assert reveal.reveal_choice_window(make_run(odd, actions=legal(state))) is None


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
            (("imperium:not_in_play:0",),),  # unrealisable -> decline
            ("decline_reveal_card_trash", {}),
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
            ("decline_reveal_troop_move", {}),
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
def test_resumed_answer_maps_to_our_action(
    hand: list[str],
    effect: str,
    changes: dict[str, object],
    answer: tuple[ResponseItem, ...],
    expected: tuple[str, dict[str, object]],
) -> None:
    state = resumed(hand, effect, **changes)
    run = intent_run(state, effect, Answer(1.0, answer, "test"))
    action = reveal.reveal_choice_window(run)
    assert action == find(state, expected[0], **expected[1])


def test_undercover_asset_spy_answer_places_or_recalls() -> None:
    state = resumed(["imperium:undercover_asset:0"], "place_spy_or_gain_two_strength")
    run = intent_run(state, "place_spy_or_gain_two_strength", Answer(1.0, ((0,),)))
    expected = best_post(make_run(state), make_run(state).by_id("place_reveal_spy"))
    assert reveal.reveal_choice_window(run) == find(
        state, "place_reveal_spy", post_id=expected
    )
    empty = resumed(
        ["imperium:undercover_asset:0"],
        "place_spy_or_gain_two_strength",
        spies_supply=0,
        spy_post_ids=FEYD_POSTS,
    )
    run = intent_run(empty, "place_spy_or_gain_two_strength", Answer(1.0, ((0,),)))
    expected = worst_post(make_run(empty), FEYD_POSTS)
    assert reveal.reveal_choice_window(run) == find(
        empty, "recall_spy_for_reveal_placement", post_id=expected
    )


def test_seated_corrinth_option_one_falls_back_to_solari() -> None:
    """Our engine offers a seated owner only the 5 Solari (module judgement)."""

    state = revealed(
        ["imperium:corrinth_city:0"], high_council=True, resources=Resources(solari=6)
    )
    actions = legal(state)
    run = make_run(state, actions=actions)
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
    (source,) = [s for s in reveal._gain_sources(run) if influence in s.actions]
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


def test_resume_key_competes_with_buys(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deferred choice is one key of the same prompt: the higher value
    wins, and the chosen answer is kept for the resumed frame."""

    state = take_gains(
        defer_all(
            revealed(
                ["imperium:spacing_guild_s_favor:0"],
                resources=Resources(spice=5),
                reveal_persuasion_bonus=12,
            )
        )
    )
    effect = "may_pay_three_spice_for_influence"
    resume = find(state, "resume_reveal_choice", effect=effect)
    answer = Answer(7.0, (("fremen",),), "patched")
    monkeypatch.setattr(
        SpacingGuildsFavorRevealAbility, "evaluate", lambda s, p, r: answer
    )
    monkeypatch.setattr(
        AcquireAbility, "evaluate", lambda s, p, r: Answer(6.0, (), "buy")
    )
    run = make_run(state)
    assert reveal.reveal_window(run) == resume
    assert run.memory.intents == {("reveal_choice", state.round_number, effect): answer}
    monkeypatch.setattr(
        AcquireAbility, "evaluate", lambda s, p, r: Answer(8.0, (), "buy")
    )
    run = make_run(state)
    action = reveal.reveal_window(run)
    assert action is not None and action.action_id.startswith("acquire_")
    assert run.memory.intents == {}


def test_optional_blocker_is_resumed_to_be_declined() -> None:
    """Nothing positive and only an Optional choice in the way: the app ends
    the turn, so the choice is resumed with a ``"decline"`` intent."""

    state = take_gains(
        defer_all(
            revealed(["imperium:captured_mentat:0"], influence=Influence(emperor=1))
        )
    )
    assert find(state, "resume_reveal_choice") is not None
    run = make_run(state, constants=NO_BUYS)
    effect = "may_lose_influence_to_gain_influence"
    action = reveal.reveal_window(run)
    assert action == find(state, "resume_reveal_choice", effect=effect)
    assert run.memory.intents == {
        ("reveal_choice", state.round_number, effect): "decline"
    }
    state = apply(state, action)
    choice = reveal.reveal_choice_window(make_run(state, run.memory))
    assert choice == find(state, "decline_reveal_influence_exchange")


def test_end_turn_declines_every_optional_blocker_after_one_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12 §4.3: one ``MakeChoice`` gives the empty answer and the turn ends.
    Two Optional blockers are declined and the Reveal finished with a single
    evaluation of the prompt (no second shuffle)."""

    state = take_gains(
        defer_all(
            revealed(
                ["imperium:captured_mentat:0", "imperium:spacing_guild_s_favor:0"],
                influence=Influence(emperor=1),
                resources=Resources(spice=5),
            )
        )
    )
    assert len(make_run(state).by_id("resume_reveal_choice")) == 2
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
        forced: bool | None = None,
    ) -> DomainAction | None:
        prompts.append(len(sources))
        return original(run, sources, skip=skip, forced=forced)

    monkeypatch.setattr(reveal, "decide", counting)
    memory = Memory()
    taken: list[str] = []
    while True:
        kind = state.decision_stack[-1].kind
        handler = (
            reveal.reveal_window if kind == "reveal" else reveal.reveal_choice_window
        )
        action = handler(make_run(state, memory, constants=NO_BUYS))
        assert action is not None
        taken.append(action.action_id)
        if action.action_id == "finish_reveal":
            break
        state = apply(state, action)
    assert len(prompts) == 1
    assert sorted(taken) == sorted(
        [
            "resume_reveal_choice",
            "decline_reveal_influence_exchange",
            "resume_reveal_choice",
            "decline_reveal_spice_influence",
            "finish_reveal",
        ]
    )
    assert taken[0] == "resume_reveal_choice" and taken[2] == "resume_reveal_choice"
    assert reveal._END_TURN not in memory.data
    assert memory.intents == {}


def test_end_turn_mark_is_dropped_when_it_does_not_fit() -> None:
    """A mark from another Reveal, or one that meets an Explicit blocker, is
    dropped and the prompt is evaluated as usual."""

    state = take_gains(defer_all(revealed(["imperium:public_spectacle:0"])))
    resume = find(state, "resume_reveal_choice", effect="place_spy")
    for mark in [(state.round_number, owner(state)), (state.round_number - 1, 0)]:
        memory = Memory()
        memory.data[reveal._END_TURN] = mark
        run = make_run(state, memory, constants=NO_BUYS)
        assert reveal.reveal_window(run) == resume
        assert reveal._END_TURN not in memory.data
        (intent,) = memory.intents.values()
        assert isinstance(intent, Answer)


def test_two_copies_of_one_choice_are_one_key_of_the_oldest_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delivery Agreement (1 Spice) and Priority Contracts (2 Spice) share a
    kind: one ``resume`` key, valued by the oldest openable entry's card
    (``_resumed_card``); a waiting entry is skipped."""

    effect = "keep_spice_or_trash_self_for_vp_if_four_contracts"
    state = take_gains(
        defer_all(
            revealed(["imperium:priority_contracts:0", "imperium:delivery_agreement:0"])
        )
    )
    run = make_run(state)
    queue = reveal._deferred_entries(reveal._reveal_context(run))
    assert [kind for _, kind in queue] == [effect, effect]
    (oldest, _), (newest, _) = queue
    (resume,) = run.by_id("resume_reveal_choice")
    spice = {
        "imperium:priority_contracts:0": run.profile.spice_value(2),
        "imperium:delivery_agreement:0": run.profile.spice_value(1),
    }
    assert spice[oldest] != spice[newest]
    answers: dict[str, Answer] = {}
    sources = reveal._resume_sources(run, answers)
    assert sources is not None
    (source,) = sources
    assert source.evaluate is not None
    value, action = source.evaluate()
    assert value == pytest.approx(spice[oldest]) and action == resume
    assert answers[effect].response == ((0,),)
    # The oldest entry waits (its condition fails): the next one is resumed.
    monkeypatch.setattr(
        reveal, "waiting_deferred_choices", lambda state, seat: ((oldest, effect),)
    )
    assert reveal._resumed_card(run, effect) == newest
    sources = reveal._resume_sources(run, {})
    assert sources is not None
    (source,) = sources
    assert source.evaluate is not None
    value, action = source.evaluate()
    assert value == pytest.approx(spice[newest]) and action == resume


def test_covert_operation_places_its_two_spies_as_two_keys() -> None:
    """``place_two_spies`` is deferred, resumed by value, and places one Spy;
    the second icon's fresh ``place_spy`` frame is deferred again and comes
    back as its own key of the re-issued prompt."""

    state = revealed(["imperium:covert_operation:0"])
    context = dict(state.decision_stack[-1].context)
    assert context["reveal_choice_effect"] == "place_two_spies"
    first = reveal.reveal_choice_window(make_run(state))
    assert first == find(state, "defer_reveal_choice")
    state = take_gains(apply(state, first))
    run = make_run(state, constants=NO_BUYS)
    assert reveal.reveal_window(run) == find(
        state, "resume_reveal_choice", effect="place_two_spies"
    )
    (intent,) = run.memory.intents.values()
    assert isinstance(intent, Answer)
    assert intent.value == pytest.approx(run.profile.spy_value().sum)
    state = apply(state, find(state, "resume_reveal_choice", effect="place_two_spies"))
    choice_run = make_run(state, run.memory)
    expected = best_post(make_run(state), choice_run.by_id("place_reveal_spy"))
    placed = reveal.reveal_choice_window(choice_run)
    assert placed == find(state, "place_reveal_spy", post_id=expected)
    state = apply(state, placed)
    context = dict(state.decision_stack[-1].context)
    assert context["reveal_choice_effect"] == "place_spy"
    second = reveal.reveal_choice_window(make_run(state))
    assert second == find(state, "defer_reveal_choice")
    state = apply(state, second)
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == find(
        state, "resume_reveal_choice", effect="place_spy"
    )


def test_unmirrored_blockers_fall_back() -> None:
    """``None`` (the agent falls back) when finish is blocked by something
    with no app key, or a ``resume`` key has no openable card / no port."""

    state = take_gains(revealed(["imperium:steersman:0"]))
    seat = owner(state)
    no_finish = tuple(a for a in legal(state) if a.action_id != "finish_reveal")
    assert reveal.reveal_window(make_run(state, actions=no_finish)) is None
    for effect in ("may_pay_three_spice_for_influence", "command_place_spy"):
        ghost = DomainAction("resume_reveal_choice", seat, (("effect", effect),))
        run = make_run(state, actions=(*legal(state), ghost))
        assert reveal.reveal_window(run) is None


def test_explicit_blocker_is_resolved_by_value() -> None:
    state = take_gains(defer_all(revealed(["imperium:public_spectacle:0"])))
    run = make_run(state, constants=NO_BUYS)
    action = reveal.reveal_window(run)
    assert action == find(state, "resume_reveal_choice", effect="place_spy")
    (intent,) = run.memory.intents.values()
    assert isinstance(intent, Answer)
    assert intent.value == pytest.approx(run.profile.spy_value().sum)


def test_forced_prompt_with_nothing_positive_picks_at_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DefaultRandomChoice`` over the whole list (a buy worth 0 too); a
    resumed pick runs the ability with random targets (intent ``"random"``)."""

    state = take_gains(defer_all(revealed(["imperium:public_spectacle:0"])))
    monkeypatch.setattr(
        PlaceSpyRevealAbility, "evaluate", lambda s, p, r: Answer(0.0, ())
    )
    resume = find(state, "resume_reveal_choice", effect="place_spy")
    picks: set[str] = set()
    for seed in range(12):
        run = make_run(state, constants=NO_BUYS, rng_seed=seed)
        action = reveal.reveal_window(run)
        assert action is not None
        picks.add(action.action_id)
        if action == resume:
            assert list(run.memory.intents.values()) == ["random"]
        else:
            assert action.action_id.startswith("acquire_")
            assert run.memory.intents == {}
    assert picks >= {"resume_reveal_choice", "acquire_imperium"}


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
    odd = DomainAction(action_id="advance_reveal_research", actor=owner(state))
    run = make_run(state, actions=(*legal(state), odd))
    assert reveal.reveal_window(run) is None


def test_stale_choice_intents_are_dropped() -> None:
    state = take_gains(revealed(["imperium:steersman:0"]))
    memory = Memory()
    memory.intents[("reveal_choice", 1, "may_pay_water_for_sandworm")] = "decline"
    memory.intents[("intrigue", "x")] = "kept"
    reveal.reveal_window(make_run(state, memory))
    assert memory.intents == {("intrigue", "x"): "kept"}


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
    assert all(mirrored[kind] > 0 for kind in reveal.HANDLERS), mirrored
