"""The ``reveal`` and ``reveal_choice`` windows with Bloodlines, the Tech
Module and Arrakeen Scouts (``windows/reveal.py``, module rule 7).

Real Reveal turns: seat 0's hand (and only the fields a branch needs) is set
on the first TURN decision of a real game and ``reveal_turn`` is applied, so
every frame, context key and legal action is the engine's own. Expected
answers are the app-style abilities' own ``Evaluate``
(docs/app-ai/bloodlines-cards.md §2.1-2.2, §3, §8; bloodlines-systems.md
§1.3-1.4, §2.3, §3.4; scouts.md §3.3, §4.7). ``intrigue_play_sources`` (the
intrigue window's) is stubbed.
"""

import random
from collections.abc import Sequence
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import (
    Answer,
    Request,
    TargetInfo,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
    ArrakisObserverRevealAbility,
    CHOAMDemandsRevealAbility,
    CommandCenterRevealAbility,
    DeliveryLogisticsRevealAbility,
    DisruptionTacticsRevealAbility,
    EngineeredMiracleCommandAbility,
    IxianAmbassadorRevealAbility,
    PointingTheWayCommandAbility,
    ShroudedCounselCommandAbility,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    DesperateSkillAbility,
    ForbiddenWeaponsAbility,
    RecruitCommanderAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AcquireAbility,
    DeployUnitsAbility,
    PlaceSpyRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import CorrinthCityRevealAbility
from dune_imperium.agents.app_ai.abilities.scouts import (
    CorrinthCityRevealScoutsAbility,
    SubcommitteeOfferAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    skill_entity,
    space_entity,
    spy_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES, AIConstants
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import reveal
from dune_imperium.agents.app_ai.windows.common import Stage, best_place_action
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, with_context

BL = RulesetConfig(bloodlines=True, tech_module=True, choam_module=True)
SCOUTS = RulesetConfig(arrakeen_scouts=True, choam_module=True)
HARD = TABLES[2]
#: Hard constants under which no card is worth buying.
NO_BUYS = replace(
    HARD,
    MinimumAcquireValueEarly=1e9,
    MinimumAcquireValueMid=1e9,
    MinimumAcquireValueLate=1e9,
)
#: Seven Persuasion between them: with any Bloodlines card, Command (6+).
RICH = [
    "imperium:imperium_ceremony:0",
    "imperium:leadership:0",
    "imperium:maker_keeper:0",
]
#: A card with no Reveal effect (fills a hand without opening a choice).
PLAIN = "imperium:guild_spy:0"
#: Two observation posts (board order) for the Spies a test needs.
POSTS = ("arrakis-imperial-basin", "bene-gesserit-espionage-secrets")


@pytest.fixture(autouse=True)
def _no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
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


def profile(state: GameState, constants: AIConstants = HARD) -> Profile:
    return make_run(state, constants=constants).profile


def find(state: GameState, action_id: str, **args: object) -> DomainAction:
    for action in legal(state):
        if action.action_id == action_id and all(
            dict(action.arguments).get(k) == v for k, v in args.items()
        ):
            return action
    raise AssertionError(f"{action_id} {args} is not legal")


def apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action, legal_actions=legal(state)).state


def turn_start(config: RulesetConfig = BL) -> GameState:
    return first_decision("turn", config=config, seed=1)


def give_tech(state: GameState, seat: int, *tech_ids: str) -> GameState:
    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    state = with_state(state, tech_stacks=stacks)
    return with_player(state, seat, tech_ids=(*state.players[seat].tech_ids, *tech_ids))


def give_skill(state: GameState, seat: int, skill: str) -> GameState:
    state = with_state(
        state,
        skill_stack=tuple(s for s in state.skill_stack if s != skill),
        skill_face_up=tuple(s for s in state.skill_face_up if s != skill),
    )
    return with_player(state, seat, skill_ids=(*state.players[seat].skill_ids, skill))


def revealed(
    hand: Sequence[str],
    *,
    config: RulesetConfig = BL,
    prepare: object = None,
    **changes: object,
) -> GameState:
    """Seat 0's Reveal with ``hand`` (troop supply kept at 12 troops)."""

    state = turn_start(config)
    seat = owner(state)
    if callable(prepare):
        state = prepare(state, seat)
    me = state.players[seat]
    placed = sum(
        int(str(changes.get(name, getattr(me, name))))
        for name in ("troops_garrison", "troops_conflict")
    )
    changes.setdefault(
        "troops_supply",
        12 - placed - me.memories - me.specimens - me.troops_parked,
    )
    state = with_player(state, seat, hand=tuple(hand), **changes)
    return apply(state, find(state, "reveal_turn"))


def entry_of(state: GameState, effect: str) -> reveal._Entry:
    """The pending choice of ``effect`` that offers rows (the only one)."""

    entries = reveal._choice_entries(make_run(state))
    assert entries is not None
    (entry,) = [e for e in entries if e.effect == effect]
    return entry


def entry_run(state: GameState, effect: str) -> DecisionRun:
    """A run over the rows of the pending choice of ``effect``."""

    return reveal._entry_run(make_run(state), entry_of(state, effect))


def key_of(
    state: GameState, effect: str, constants: AIConstants = HARD
) -> tuple[float, DomainAction | None]:
    """The post-reveal key of the pending choice of ``effect``: its value
    and the row its answer names."""

    run = make_run(state, constants=constants)
    (source,) = reveal._choice_sources(run, [entry_of(state, effect)], {})
    assert source.evaluate is not None
    return source.evaluate()


def passed(memory: Memory) -> frozenset[tuple[str, str]]:
    stored = memory.data.get(reveal._PASSED)
    assert isinstance(stored, tuple)
    choices = stored[1]
    assert isinstance(choices, frozenset)
    return choices


def settle_gains(state: GameState) -> GameState:
    """Take the automatic Reveal gains (state 300/400) the window takes."""

    while True:
        run = make_run(state)
        sources = reveal._gain_sources(run)
        assert sources is not None
        auto = [s for s in sources if s.stage < Stage.PROMPT]
        if not auto:
            return state
        state = apply(state, auto[0].actions[0])


def with_reveal_context(state: GameState, **changes: ActionValue) -> GameState:
    """The seat's Reveal frame (on top) with context keys changed."""

    frame = state.decision_stack[-1]
    assert frame.kind == "reveal"
    context = dict(frame.context)
    context.update(changes)
    return replace(
        state, decision_stack=(*state.decision_stack[:-1], with_context(frame, context))
    )


# ===========================================================================
# Command (6+) choices: automatic steps before any buy (plan §11.5)
# ===========================================================================

_GAIN_IDS = frozenset(
    {"recruit_reveal_troops", "draw_reveal_intrigue", "gain_reveal_resources"}
)


@pytest.mark.parametrize("junk", [True, False])
def test_shrouded_counsel_command_trash_is_answered_before_the_prompt(
    junk: bool,
) -> None:
    def starters_discarded(state: GameState, seat: int) -> GameState:
        # The starting hand (starter cards: junk to the app) in the discard.
        if not junk:
            return state
        hand = state.players[seat].hand
        return with_player(state, seat, discard_pile=hand, hand=())

    state = revealed(["imperium:shrouded_counsel:0", *RICH], prepare=starters_discarded)
    entry = entry_of(state, "command_may_trash_card")
    assert entry.card == "imperium:shrouded_counsel:0"
    seat = owner(state)
    me = state.players[seat]
    targets = tuple(
        card_entity(c, seat) for c in (*me.hand, *me.discard_pile, *counted_in_play(me))
    )
    expected = ShroudedCounselCommandAbility(
        card_entity("imperium:shrouded_counsel:0", seat)
    ).evaluate(profile(state), Request((TargetInfo(entities=targets),)))
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory))
    picked = expected.response[0] if expected.response else ()
    if junk:
        assert expected.value > 0 and picked and picked[0] in me.discard_pile
        assert chosen == find(
            state, "trash_reveal_card", card_id=picked[0], source="shrouded_counsel"
        )
        assert reveal._PASSED not in memory.data
    else:
        # "use, trash nothing" (``((),)``): not used, never asked again.
        assert picked == ()
        assert chosen is not None and chosen not in entry.rows
        assert passed(memory) == {(entry.card, entry.effect)}
        state = apply(state, chosen)
        again = reveal.reveal_window(make_run(state, memory))
        assert again is not None and again not in entry.rows


def test_command_choices_resolve_in_card_order_before_the_prompt() -> None:
    """Pointing the Way's track, Intelligence Training's best post and
    Engineered Miracle's best Row card, each as an automatic step in card
    order."""

    hand = [
        "imperium:pointing_the_way:0",
        "imperium:intelligence_training:0",
        "imperium:engineered_miracle:0",
        *RICH,
    ]
    state = revealed(hand)
    seat = owner(state)
    # Pointing the Way (Explicit, +100 per track): GainAnyInfluence's track.
    tracks = tuple(track_entity(f) for f in FACTIONS)
    gain = PointingTheWayCommandAbility(card_entity(hand[0], seat)).evaluate(
        profile(state), Request((TargetInfo(entities=tracks),))
    )
    assert gain.response is not None
    chosen = reveal.reveal_window(make_run(state))
    assert chosen == find(state, "gain_reveal_influence", faction=gain.response[0][0])
    state = apply(state, chosen)
    # Intelligence Training: the Spy on the app's best post.
    run = make_run(state)
    chosen = reveal.reveal_window(run)
    assert chosen is not None and chosen.action_id == "place_reveal_spy"
    places = entry_run(state, "command_place_spy").by_id("place_reveal_spy")
    assert chosen == best_place_action(make_run(state), places)
    state = apply(state, chosen)
    # Engineered Miracle (Optional): the best Row card by AcquireValue.
    entry = entry_of(state, "command_may_trash_self_to_acquire_row_card")
    row = tuple(card_entity(i) for i in state.imperium_row)
    miracle = EngineeredMiracleCommandAbility(card_entity(hand[2], seat)).evaluate(
        profile(state), Request((TargetInfo(entities=row),))
    )
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory))
    if miracle.value > 0 and miracle.response:
        assert chosen == find(
            state, "command_acquire_row_card", instance_id=miracle.response[0][0]
        )
    else:
        assert chosen is not None and chosen not in entry.rows
        assert passed(memory) == {(entry.card, entry.effect)}


def test_a_waiting_command_choice_runs_once_it_opens() -> None:
    """A Command choice that opens after the Reveal began (the sixth
    Persuasion came later) is answered as an automatic step, before buys."""

    state = settle_gains(
        revealed(["imperium:shrouded_counsel:0", PLAIN], troops_garrison=0)
    )
    assert not any(a.action_id == "trash_reveal_card" for a in legal(state))
    state = with_reveal_context(state, persuasion_generated=6)
    entry = entry_of(state, "command_may_trash_card")
    seat = owner(state)
    me = state.players[seat]
    targets = tuple(
        card_entity(c, seat) for c in (*me.hand, *me.discard_pile, *counted_in_play(me))
    )
    expected = ShroudedCounselCommandAbility(
        card_entity("imperium:shrouded_counsel:0", seat)
    ).evaluate(profile(state), Request((TargetInfo(entities=targets),)))
    picked = expected.response[0] if expected.response else ()
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory))
    if expected.value > 0 and picked:
        assert chosen == find(state, "trash_reveal_card", card_id=picked[0])
    else:
        assert chosen not in entry.rows
        assert passed(memory) == {(entry.card, entry.effect)}


@pytest.mark.parametrize("command_first", [True, False])
def test_a_late_command_choice_runs_at_its_cards_reveal_position(
    command_first: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Command choice that opens late is a state-300 step ranked by its
    card's reveal position among the automatic gains (module rule 7):
    before a later card's printed gain, after an earlier card's."""

    cards = ["imperium:shrouded_counsel:0", "imperium:price_is_no_object:0"]
    hand = cards if command_first else cards[::-1]
    state = revealed(hand, troops_garrison=0)
    gain = find(state, "gain_reveal_resources", solari=2, spice=0, water=0)
    state = with_reveal_context(state, persuasion_generated=6)
    trash = find(state, "trash_reveal_card", card_id="imperium:price_is_no_object:0")
    monkeypatch.setattr(
        ShroudedCounselCommandAbility,
        "evaluate",
        lambda s, p, r: Answer(5.0, (("imperium:price_is_no_object:0",),)),
    )
    assert reveal.reveal_window(make_run(state)) == (trash if command_first else gain)


def test_a_passed_mark_of_another_reveal_is_ignored() -> None:
    """``_PASSED`` holds this Reveal's choices only: another Reveal's mark
    does not keep a Command choice from being answered."""

    state = settle_gains(
        revealed(["imperium:shrouded_counsel:0", PLAIN], troops_garrison=0)
    )
    state = with_reveal_context(state, persuasion_generated=6)
    entry = entry_of(state, "command_may_trash_card")
    stale = Memory()
    stale.data[reveal._PASSED] = (
        (state.round_number - 1, owner(state)),
        frozenset({(entry.card, entry.effect)}),
    )
    fresh = Memory()
    assert reveal.reveal_window(make_run(state, stale)) == reveal.reveal_window(
        make_run(state, fresh)
    )
    assert stale.data.get(reveal._PASSED) == fresh.data.get(reveal._PASSED)


def test_an_automatic_command_reward_is_a_state_400_gain() -> None:
    """Bombast's "Command: 3 Solari" is ``AS.CommandRevealAbility`` (always
    runs immediately, state 400): Price Is No Object's printed 2 Solari
    (state 300) comes first though Bombast is revealed first."""

    state = revealed(
        [
            "imperium:bombast:0",
            "imperium:price_is_no_object:0",
            "imperium:imperium_ceremony:0",
        ]
    )
    first = reveal.reveal_window(make_run(state))
    assert first == find(state, "gain_reveal_resources", solari=2, spice=0, water=0)
    state = apply(state, first)
    second = reveal.reveal_window(make_run(state))
    assert second == find(state, "gain_reveal_resources", solari=3, spice=0, water=0)


# ===========================================================================
# Bloodlines choices as prompt keys (valued and realised in the prompt)
# ===========================================================================


def test_command_center_retreats_a_commander_only_for_the_missing_troop() -> None:
    state = settle_gains(
        revealed(
            ["imperium:command_center:0", PLAIN],
            troops_conflict=1,
            commanders_conflict=1,
            commanders_supply=0,
            combat_strength=4,
        )
    )
    effect = "may_retreat_two_troops_for_two_persuasion"
    run = entry_run(state, effect)
    forms = {arg(a, "commanders") for a in run.by_id("retreat_two_troops_for_reveal")}
    assert forms == {1}  # one troop and one Commander fight
    realised = reveal._realise(run, effect, Answer(1.0, ()))
    assert realised == find(
        state, "retreat_two_troops_for_reveal", commanders=1, source="command_center"
    )
    expected = CommandCenterRevealAbility(
        card_entity("imperium:command_center:0", owner(state))
    ).evaluate(profile(state), Request())
    value, action = key_of(state, effect)
    assert value == expected.value
    if expected.response is not None:
        assert action == realised


def test_chani_retreat_takes_troops_first_with_commanders() -> None:
    state = settle_gains(
        revealed(
            ["imperium:chani_clever_tactician:0", PLAIN],
            troops_conflict=1,
            commanders_conflict=1,
            combat_strength=4,
        )
    )
    effect = "may_retreat_two_troops_for_four_strength"
    realised = reveal._realise(entry_run(state, effect), effect, Answer(1.0, ()))
    assert realised == find(
        state,
        "retreat_two_troops_for_reveal",
        commanders=1,
        source="chani_clever_tactician",
    )


def test_disruption_tactics_trash_carries_its_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One app answer (trash -> deploy units) over two of our decisions."""

    monkeypatch.setattr(
        Profile, "units_to_deploy", lambda self, units, most: min(units, most, 2)
    )
    state = settle_gains(
        revealed(["imperium:disruption_tactics:0", PLAIN], troops_garrison=3)
    )
    effect = "may_trash_self_for_combat_icon"
    trash = find(state, "trash_reveal_card", source="disruption_tactics")
    run = make_run(state)
    used: dict[DomainAction, tuple[reveal._Entry, Answer]] = {}
    (source,) = reveal._choice_sources(run, [entry_of(state, effect)], used)
    assert source.evaluate is not None
    assert source.evaluate() == (0.5, trash)  # DeployUnitsAbility's value
    assert used[trash][1].response == ((0, 1),)
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory, constants=NO_BUYS))
    assert chosen == trash
    key = (reveal._DEPLOY_INTENT, state.round_number, owner(state))
    assert memory.intents[key] == 2
    state = apply(state, chosen)
    assert reveal.reveal_window(make_run(state, memory)) == find(
        state, "deploy_troops", count=2
    )
    assert key not in memory.intents


def test_disruption_tactics_is_not_used_with_nothing_to_deploy() -> None:
    state = settle_gains(
        revealed(["imperium:disruption_tactics:0", PLAIN], troops_garrison=0)
    )
    seat = owner(state)
    ability = DisruptionTacticsRevealAbility(
        card_entity("imperium:disruption_tactics:0", seat)
    )
    assert ability.evaluate(profile(state), Request((TargetInfo(),))).response is None
    assert key_of(state, "may_trash_self_for_combat_icon")[0] <= 0.0
    memory = Memory()
    assert reveal.reveal_window(make_run(state, memory, constants=NO_BUYS)) == find(
        state, "finish_reveal"
    )
    assert memory.intents == {}


def test_disruption_tactics_keeps_the_card_when_an_icon_is_already_open() -> None:
    """A second Combat icon adds no room ("한 turn에 이 아이콘이 둘 이상이어도
    garrison에서 deploy하는 수는 두 개를 넘지 못한다" [Bloodlines pp. 5, 12],
    docs/rules/bloodlines.md §4): with Holy War's Fremen Bond icon open, the
    trash opens no deployment, so its ``DeployUnitsAbility`` E stores nothing
    and the card is kept; the deploy key alone deploys. Regression: the trash
    key tied the deploy key at 0.5 and the card was trashed for nothing."""

    state = revealed(
        ["imperium:disruption_tactics:0", "imperium:holy_war:0"], troops_garrison=3
    )
    state = settle_gains(state)
    assert dict(state.decision_stack[-1].context)["combat_deployment"] is True
    effect = "may_trash_self_for_combat_icon"
    run = make_run(state)
    used: dict[DomainAction, tuple[reveal._Entry, Answer]] = {}
    (source,) = reveal._choice_sources(run, [entry_of(state, effect)], used)
    assert source.evaluate is not None
    assert source.evaluate()[0] == 0.0
    assert used == {}  # no answer names the trash
    (deploy,) = reveal._deploy_sources(run, {})
    assert deploy.evaluate is not None
    value, action = deploy.evaluate()
    assert value == 0.5 and action is not None  # GetUnitsToDeploy wants units
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == action
    # After the deployment the trash still is not used: the turn ends.
    state = apply(state, action)
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == find(
        state, "finish_reveal"
    )


def test_arrakis_observer_recalls_the_worst_post_spy() -> None:
    def spies(state: GameState, seat: int) -> GameState:
        return with_player(state, seat, spy_post_ids=POSTS, spies_supply=1)

    state = settle_gains(
        revealed(["imperium:arrakis_observer:0", PLAIN], prepare=spies)
    )
    effect = "may_recall_spy_for_three_strength"
    seat = owner(state)
    expected = ArrakisObserverRevealAbility(
        card_entity("imperium:arrakis_observer:0", seat)
    ).evaluate(
        profile(state),
        Request((TargetInfo(entities=tuple(spy_entity(p, seat) for p in POSTS)),)),
    )
    chosen = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    if expected.value > 0 and expected.response:
        assert chosen == find(
            state,
            "recall_spy_for_reveal",
            post_id=expected.response[0][0],
            source="arrakis_observer",
        )
    else:
        assert key_of(state, effect)[0] == expected.value
        assert chosen == find(state, "finish_reveal")


def test_choam_demands_trashes_itself_for_four_influence() -> None:
    def contracts(state: GameState, seat: int) -> GameState:
        four = state.contract_bank[:4]
        state = with_state(state, contract_bank=state.contract_bank[4:])
        return with_player(state, seat, completed_contract_ids=four)

    state = settle_gains(
        revealed(["imperium:choam_demands:0", PLAIN], prepare=contracts)
    )
    effect = "may_trash_self_for_four_influence_if_four_contracts"
    expected = CHOAMDemandsRevealAbility(
        card_entity("imperium:choam_demands:0", owner(state))
    ).evaluate(profile(state), Request())
    assert expected.response == () and expected.value > 0
    trash = find(
        state,
        "trash_reveal_card",
        card_id="imperium:choam_demands:0",
        source="choam_demands",
    )
    assert key_of(state, effect) == (expected.value, trash)
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == trash


def test_delivery_logistics_takes_the_better_of_persuasion_and_contract() -> None:
    state = settle_gains(revealed(["imperium:delivery_logistics:0", PLAIN]))
    assert make_run(state).first("finish_reveal") is None  # mandatory
    expected = DeliveryLogisticsRevealAbility(
        card_entity("imperium:delivery_logistics:0", owner(state))
    ).evaluate(profile(state), Request((TargetInfo(options=(0, 1)),)))
    assert expected.response is not None
    wanted = (
        "take_reveal_contract"
        if expected.response[0][0] == 1
        else "gain_reveal_persuasion"
    )
    assert key_of(state, "persuasion_or_contract") == (
        expected.value,
        find(state, wanted),
    )


def test_ixian_ambassador_gains_gainanyinfluences_track() -> None:
    def tiles(state: GameState, seat: int) -> GameState:
        return give_tech(state, seat, "glowglobes", "suspensor_suits")

    state = settle_gains(
        revealed(["imperium:ixian_ambassador:0", PLAIN], prepare=tiles)
    )
    tracks = tuple(track_entity(f) for f in FACTIONS)
    expected = IxianAmbassadorRevealAbility(
        card_entity("imperium:ixian_ambassador:0", owner(state))
    ).evaluate(profile(state), Request((TargetInfo(entities=tracks),)))
    assert expected.response is not None
    assert key_of(state, "gain_chosen_influence_if_two_tech") == (
        expected.value,
        find(state, "gain_reveal_influence", faction=expected.response[0][0]),
    )


def test_corrinth_city_uses_the_scouts_ability_only_in_scouts_games() -> None:
    card = "imperium:corrinth_city:0"
    effect = "gain_five_solari_or_take_high_council"
    scouts = revealed([card, PLAIN], config=SCOUTS)
    assert entry_of(scouts, effect).card == card
    ability = reveal._choice_ability(make_run(scouts), effect, card)
    assert isinstance(ability, CorrinthCityRevealScoutsAbility)
    plain = revealed([card, PLAIN])
    ability = reveal._choice_ability(make_run(plain), effect, card)
    assert type(ability) is CorrinthCityRevealAbility


# ===========================================================================
# The Reveal-turn Combat icon (D5, D61, §1.3)
# ===========================================================================


def test_the_reveal_deploy_key_splits_commanders_first_with_a_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Profile, "units_to_deploy", lambda self, units, most: min(units, most)
    )

    def skilled(state: GameState, seat: int) -> GameState:
        return give_skill(state, seat, "skill:canny:0")

    state = revealed(
        [PLAIN],
        prepare=skilled,
        troops_garrison=2,
        commanders_garrison=1,
        commanders_supply=0,
    )
    state = with_reveal_context(settle_gains(state), combat_deployment=True)
    run = make_run(state, constants=NO_BUYS)
    units, troop_max, commander_max, most = reveal._reveal_deploy_limits(run)
    assert (units, troop_max, commander_max, most) == (3, 2, 1, 2)
    assert run.profile.commanders_deploy_first()
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory, constants=NO_BUYS))
    assert chosen == find(state, "deploy_commanders", count=1)
    key = (reveal._DEPLOY_INTENT, state.round_number, owner(state))
    assert memory.intents[key] == ("deploy_troops", 1)
    state = apply(state, chosen)
    assert reveal.reveal_window(make_run(state, memory, constants=NO_BUYS)) == find(
        state, "deploy_troops", count=1
    )
    assert key not in memory.intents
    # Used once per Reveal: no second deploy key.
    state = apply(state, find(state, "deploy_troops", count=1))
    assert reveal._deploy_sources(make_run(state), {}) == []


def test_the_reveal_deploy_key_is_deployunitsabilitys_answer() -> None:
    state = revealed([PLAIN], troops_garrison=2)
    state = with_reveal_context(settle_gains(state), combat_deployment=True)
    run = make_run(state)
    rests: dict[DomainAction, tuple[str, int]] = {}
    (source,) = reveal._deploy_sources(run, rests)
    units, _t, _c, most = reveal._reveal_deploy_limits(run)
    expected = DeployUnitsAbility(Entity(Kind.LEADER, "x")).evaluate(
        profile(state),
        Request((TargetInfo(options=tuple(range(units)), max_select=most),)),
    )
    assert source.evaluate is not None
    value, action = source.evaluate()
    assert value == expected.value
    if expected.response:
        assert action == find(state, "deploy_troops", count=len(expected.response[0]))
    else:
        assert action is None
    assert not rests  # troops only: nothing left for a second decision


# ===========================================================================
# Commanders, Skills, Desert Scouts
# ===========================================================================


def test_recruit_commander_is_a_key_at_its_net_or_100() -> None:
    def solari(state: GameState, seat: int) -> GameState:
        me = state.players[seat]
        return with_player(state, seat, resources=replace(me.resources, solari=5))

    state = settle_gains(revealed([PLAIN], prepare=solari, commanders_supply=1))
    run = make_run(state)
    recruit = find(state, "recruit_sardaukar_commander")
    sources = reveal._commander_sources(run)
    assert sources is not None and len(sources) == 1
    expected = RecruitCommanderAbility(Entity(Kind.LEADER, "x")).evaluate(
        profile(state), Request()
    )
    assert sources[0].evaluate is not None
    assert sources[0].evaluate() == (
        expected.value,
        None if expected.response is None else recruit,
    )


def test_desperate_is_a_key_per_tile() -> None:
    def desperate(state: GameState, seat: int) -> GameState:
        return give_skill(state, seat, "skill:desperate:0")

    state = settle_gains(
        revealed(
            [PLAIN],
            prepare=desperate,
            commanders_conflict=1,
            commanders_supply=0,
            combat_strength=2,
        )
    )
    action = find(state, "trash_skill_for_strength", skill_id="desperate")
    sources = reveal._commander_sources(make_run(state))
    assert sources is not None and len(sources) == 1
    tile = skill_entity("desperate", owner(state))
    expected = DesperateSkillAbility(tile).evaluate(
        profile(state), Request((TargetInfo(entities=(tile,)),))
    )
    assert sources[0].evaluate is not None
    assert sources[0].evaluate() == (
        expected.value,
        None if expected.response is None else action,
    )


def test_desert_scouts_retreats_a_commander_only_without_a_troop() -> None:
    def amber(state: GameState, seat: int) -> GameState:
        return with_player(
            state,
            seat,
            leader_id="lady_amber_metulli",
            leader_face_id="lady_amber_metulli",
        )

    state = settle_gains(
        revealed(
            [PLAIN],
            prepare=amber,
            troops_conflict=0,
            commanders_conflict=1,
            commanders_supply=0,
            combat_strength=2,
        )
    )
    run = make_run(state)
    assert run.first("retreat_leader_troop") is None
    commander = find(state, "retreat_leader_commander")
    sources = reveal._leader_sources(run)
    assert [s.actions for s in sources] == [(commander,)]
    with_troop = settle_gains(
        revealed(
            [PLAIN],
            prepare=amber,
            troops_conflict=1,
            commanders_conflict=1,
            commanders_supply=0,
            combat_strength=4,
        )
    )
    sources = reveal._leader_sources(make_run(with_troop))
    assert [s.actions for s in sources] == [(find(with_troop, "retreat_leader_troop"),)]


# ===========================================================================
# Tech tiles in the Reveal
# ===========================================================================


def test_panopticon_and_forbidden_weapons_are_explicit_blocking_keys() -> None:
    def tiles(state: GameState, seat: int) -> GameState:
        return give_tech(state, seat, "panopticon", "forbidden_weapons")

    state = settle_gains(revealed([PLAIN], prepare=tiles))
    run = make_run(state)
    assert run.first("finish_reveal") is None
    sources = reveal._tech_reveal_sources(run)
    assert sources is not None and len(sources) == 2
    spy, weapons = sources
    assert spy.extra == {"blocking": True, "explicit": True}
    assert weapons.extra == {"blocking": True, "explicit": True}
    assert spy.evaluate is not None
    seat = owner(state)
    panopticon = PlaceSpyRevealAbility(tech_entity("panopticon", seat))
    assert spy.evaluate() == (
        panopticon.evaluate(profile(state), Request()).value,
        find(state, "place_tech_spy"),
    )
    strength = run.by_id("choose_tech_strength")
    factions = [f for f in dict.fromkeys(arg(a, "faction") for a in strength) if f]
    request = Request(
        (
            TargetInfo(options=(0, 1)),
            TargetInfo(entities=tuple(track_entity(str(f)) for f in factions)),
        )
    )
    expected = ForbiddenWeaponsAbility(tech_entity("forbidden_weapons", seat)).evaluate(
        profile(state), request
    )
    assert expected.response is not None
    assert weapons.evaluate is not None
    value, action = weapons.evaluate()
    assert value == expected.value >= 1.0  # a forced loss, at least 1.0 (D26)
    if expected.response[0][0] == 1:
        assert action == find(state, "choose_tech_trash")
    elif len(expected.response) > 1:
        assert action is not None and action.action_id == "choose_tech_strength"
        assert arg(action, "faction") == expected.response[1][0]
    else:
        assert action == next(a for a in strength if not a.arguments)
    # The prompt is forced: the window answers one of them.
    chosen = reveal.reveal_window(make_run(state, constants=NO_BUYS))
    assert chosen is not None and chosen.action_id in (
        "place_tech_spy",
        "choose_tech_strength",
        "choose_tech_trash",
    )


def test_a_flip_tile_is_a_reveal_key_at_100() -> None:
    def tiles(state: GameState, seat: int) -> GameState:
        return give_tech(state, seat, "spy_drones")

    state = settle_gains(revealed([PLAIN], prepare=tiles))
    flip = find(state, "flip_tech", tech_id="spy_drones")
    assert reveal.reveal_window(make_run(state, constants=NO_BUYS)) == flip


def test_an_owed_acquire_icon_is_resolved_before_the_prompt() -> None:
    state = settle_gains(revealed([PLAIN]))
    state = with_reveal_context(
        state, **{TECH_ACQUIRE_PENDING_KEY: "glowglobes:solari"}
    )
    assert reveal.reveal_window(make_run(state)) == find(
        state, "resolve_tech_acquire_effect"
    )


# ===========================================================================
# Arrakeen Scouts: the subcommittee offer and Market Opening
# ===========================================================================


def test_the_reveal_subcommittee_offer_is_a_key_and_its_decline_ends_the_turn() -> None:
    state = settle_gains(revealed([PLAIN], config=SCOUTS))
    seat = owner(state)
    state = with_state(state, scouts_subcommittee_offers=((seat, "test", ""),))
    run = make_run(state, constants=NO_BUYS)
    assert run.first("finish_reveal") is None
    decline = find(state, "decline_subcommittee")
    offer = next(
        a
        for a in abilities_of(space_entity("high_council", run.ctx.board))
        if isinstance(a, SubcommitteeOfferAbility)
    )
    expected = offer.evaluate(profile(state, NO_BUYS), Request())
    memory = Memory()
    chosen = reveal.reveal_window(make_run(state, memory, constants=NO_BUYS))
    key = (reveal._SUBCOMMITTEE_INTENT, state.round_number, seat)
    if expected.value > 0 and expected.response:
        assert chosen == find(state, "choose_subcommittee")
        assert memory.intents[key] == expected.response[0][0]
    else:
        assert chosen == decline
        assert key not in memory.intents
        assert memory.data[reveal._END_TURN] == (state.round_number, seat)


def test_the_subcommittee_decline_is_followed_by_the_end_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declined offer was the prompt's empty answer: ``finish_reveal``
    follows without a second ``MakeChoice``."""

    state = settle_gains(revealed([PLAIN], config=SCOUTS))
    seat = owner(state)
    offered = with_state(state, scouts_subcommittee_offers=((seat, "test", ""),))
    monkeypatch.setattr(
        SubcommitteeOfferAbility, "evaluate", lambda s, p, r: Answer(0.0, None)
    )
    memory = Memory()
    decline = find(offered, "decline_subcommittee")
    assert reveal.reveal_window(make_run(offered, memory, constants=NO_BUYS)) == decline
    assert memory.data[reveal._END_TURN] == (state.round_number, seat)

    def no_prompt(*args: object, **kwargs: object) -> DomainAction | None:
        raise AssertionError("the empty answer is not asked again")

    monkeypatch.setattr(reveal, "decide", no_prompt)
    assert reveal.reveal_window(make_run(state, memory)) == find(state, "finish_reveal")
    assert reveal._END_TURN not in memory.data


def test_market_opening_values_the_discounted_reserve_card() -> None:
    state = settle_gains(revealed(RICH, config=SCOUTS))
    state = with_state(state, scouts_round_modifier="spice_must_flow_discount")
    run = make_run(state)
    action = find(state, "acquire_reserve", card_id="the_spice_must_flow")
    source = next(s for s in reveal._acquire_sources(run) if s.actions == (action,))
    entity = run.profile.market_opening_reserve_card(
        card_entity("reserve:the_spice_must_flow")
    )
    assert entity.int_attr("PersuasionCost") == 7  # 9 - Market Opening's 2
    expected = AcquireAbility(entity).evaluate(profile(state), Request())
    assert source.evaluate is not None
    assert source.evaluate() == (expected.value, action)
