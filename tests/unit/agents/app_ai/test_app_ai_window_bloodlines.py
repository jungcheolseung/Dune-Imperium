"""The app_ai Bloodlines windows (``windows/bloodlines.py``).

Real Bloodlines games (``testing.first_decision`` / ``play_until``, or a
reset with Bloodlines leaders); a window's frame is the engine's own, pushed
by the engine (setup frames, ``use_leader_signet_for_tech``,
``begin_navigation_play``, ``tech_acquisition_frame``) or built the way the
engine builds it, and the legal actions are the engine's.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    FedaykinManeuverSignetAbility,
    GeneLockedVaultAcquiredAbility,
    IntoTheFraySignetAbility,
    ReverseEngineeringSignetAbility,
    SecretProjectAbility,
    SmuggleSpiceSignetAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import contract_evaluate
from dune_imperium.agents.app_ai.abilities.leaders import SpiceAgonyAbility
from dune_imperium.agents.app_ai.abilities.tech import (
    AcquireTechAbilityDiscount1,
    MemocordersAcquiredAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    POST_INDEX,
    card_entity,
    contract_entity,
    leader_entity,
    post_entity,
    spy_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.bloodlines import navigation_number
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import bloodlines as W
from dune_imperium.agents.app_ai.windows import handler_for
from dune_imperium.agents.app_ai.windows.intrigue import NAVIGATION_INTENT
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, FrameKind
from dune_imperium.rules.leader_abilities import use_leader_signet_for_tech
from dune_imperium.rules.navigation import begin_navigation_play
from dune_imperium.rules.spy_moves import connected_post_ids
from dune_imperium.rules.tech import tech_acquisition_frame

BLOODLINES = RulesetConfig(bloodlines=True, tech_module=True, choam_module=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _legal(state: GameState) -> tuple[DomainAction, ...]:
    return ENGINE.legal_actions(state, _seat(state))


def _run(
    state: GameState, memory: Memory | None = None, rng_seed: int = 0
) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    return DecisionRun(
        profile.ctx, profile, _legal(state), profile.rng, memory or Memory()
    )


def _turn_state() -> GameState:
    """Seat 0's first turn-start prompt of a Bloodlines + Tech + CHOAM game."""

    return first_decision("turn", config=BLOODLINES, seed=3)


def _push(
    state: GameState, kind: FrameKind, owner: int, **context: object
) -> GameState:
    """``state`` with the engine frame ``kind`` (context as the engine
    builds it) on top for ``owner``."""

    frame = DecisionFrame(
        kind=kind,
        frame_id=f"test:{kind.value}:{owner}",
        decision=PlayerDecision(owner=owner, prompt="test"),
        context=tuple(sorted(context.items())),  # type: ignore[arg-type]
    )
    return state.push_decision(frame)


def _reset_with(*leaders: str, seed: int = 1) -> GameState:
    """A fresh Bloodlines + Tech game dealt ``leaders`` (setup frames first)."""

    return UprisingRulesEngine(leader_ids=leaders).reset(BLOODLINES, seed)


def _give_tech(state: GameState, seat: int, *tech_ids: str) -> GameState:
    """``seat`` holds ``tech_ids`` (taken off the Tech stacks)."""

    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    state = with_state(state, tech_stacks=stacks)
    return with_player(state, seat, tech_ids=tech_ids)


def _give_skill(state: GameState, seat: int, *skills: str) -> GameState:
    """``seat`` holds the Skill tiles ``skills`` (taken out of the Skill row)."""

    state = with_state(
        state,
        skill_stack=tuple(k for k in state.skill_stack if k not in skills),
        skill_face_up=tuple(k for k in state.skill_face_up if k not in skills),
    )
    return with_player(state, seat, skill_ids=skills)


def _units(
    state: GameState,
    seat: int,
    *,
    garrison: int = 0,
    conflict: int = 0,
    commanders_garrison: int = 0,
    commanders_conflict: int = 0,
) -> GameState:
    """``seat``'s troops and Commanders (troops from its supply)."""

    return with_player(
        state,
        seat,
        troops_garrison=garrison,
        troops_conflict=conflict,
        troops_supply=12 - garrison - conflict,
        commanders_garrison=commanders_garrison,
        commanders_conflict=commanders_conflict,
    )


def _spies(state: GameState, seat: int, *posts: str) -> GameState:
    """``seat``'s Spies on ``posts``, the rest in its supply."""

    return with_player(state, seat, spy_post_ids=posts, spies_supply=3 - len(posts))


def _ids(actions: tuple[DomainAction, ...], action_id: str, name: str) -> list[object]:
    return [arg(a, name) for a in actions if a.action_id == action_id]


# ===========================================================================
# skill_choice
# ===========================================================================


def _skill_state(card: str, *tech_ids: str) -> GameState:
    state = with_state(_turn_state(), sardaukar_commanders_bank=1)
    if tech_ids:
        state = _give_tech(state, 0, *tech_ids)
    return _push(
        state,
        FrameKind.SKILL_CHOICE,
        0,
        card_id=card,
        player=0,
        source="test",
    )


def test_bank_commander_skill_is_the_best_skill_value() -> None:
    state = _skill_state("imperium:sardaukar_standard:0")
    run = _run(state)
    offered = _ids(run.legal, "choose_skill", "skill_id")
    assert offered and run.first("decline_skill") is None
    values = {str(s): run.profile.skill_value(str(s)) for s in offered}
    action = W.skill_choice(run)
    assert action is not None and action.action_id == "choose_skill"
    best = max(values.values())
    if best > 0:
        assert values[str(arg(action, "skill_id"))] == best


def test_bank_commander_skill_with_nothing_positive_is_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Profile, "skill_value", lambda self, skill, w=(): 0.0)
    state = _skill_state("imperium:sardaukar_standard:0")
    picks = {W.skill_choice(_run(state, rng_seed=s)) for s in range(12)}
    assert None not in picks
    assert len(picks) > 1  # DefaultRandomChoice over the offered Skills


def test_plasteel_blades_keeps_the_tile_unless_a_skill_is_worth_more() -> None:
    state = _skill_state("tech:plasteel_blades", "plasteel_blades")
    run = _run(state)
    assert run.first("decline_skill") is not None
    best = max(
        run.profile.skill_value(str(s))
        for s in _ids(run.legal, "choose_skill", "skill_id")
    )
    held = run.profile.held_tile_value("plasteel_blades")
    assert best - held <= 0  # a Skill is worth less than the 6.0 tile
    assert W.skill_choice(run) == run.first("decline_skill")


def test_plasteel_blades_trades_for_a_skill_worth_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _skill_state("tech:plasteel_blades", "plasteel_blades")
    offered = [str(s) for s in _ids(_legal(state), "choose_skill", "skill_id")]
    wanted = offered[-1]
    monkeypatch.setattr(
        Profile,
        "skill_value",
        lambda self, skill, w=(): 50.0 if skill == wanted else 1.0,
    )
    action = W.skill_choice(_run(state))
    assert action is not None and arg(action, "skill_id") == wanted


# ===========================================================================
# opponent_spy_move / opponent_unit_loss (victim side)
# ===========================================================================


def test_opponent_spy_move_goes_to_the_best_allowed_post() -> None:
    state = _turn_state()
    space = "imperial_privilege"
    origin = connected_post_ids(space)[0]
    state = _spies(state, 1, origin)
    state = _push(
        state,
        FrameKind.OPPONENT_SPY_MOVE,
        1,
        player=1,
        post_id=origin,
        source="test",
        space_id=space,
    )
    run = _run(state)
    posts = [str(p) for p in _ids(run.legal, "move_spy", "post_id")]
    assert posts and origin not in posts
    best, _ = run.profile.best_post([post_entity(p, 1) for p in posts])
    assert best is not None
    action = W.opponent_spy_move(_run(state))  # the same RNG draws
    assert action is not None and arg(action, "post_id") == best.ref


def _loss_state(state: GameState) -> GameState:
    return _push(state, FrameKind.OPPONENT_UNIT_LOSS, 2, player=2, source="test")


def test_opponent_unit_loss_takes_the_least_loss() -> None:
    state = _units(
        _turn_state(),
        2,
        garrison=2,
        conflict=2,
        commanders_garrison=1,
        commanders_conflict=1,
    )
    state = _give_skill(state, 2, "skill:loyal:0")
    influence = replace(state.players[2].influence, emperor=3)
    state = _loss_state(with_player(state, 2, influence=influence))
    run = _run(state)
    rows = [
        (str(arg(a, "zone")), arg(a, "commanders") == 1)
        for a in run.legal
        if a.action_id == "lose_unit"
    ]
    assert len(rows) == 4
    values = {row: run.profile.lose_unit_value(*row) for row in rows}
    least = min(values.values())
    for seed in range(8):
        action = W.opponent_unit_loss(_run(state, rng_seed=seed))
        assert action is not None
        row = (str(arg(action, "zone")), arg(action, "commanders") == 1)
        assert values[row] == least
    # The last Commander in the Conflict carries the Loyal Skill's loss.
    assert values[("conflict", True)] > values[("conflict", False)]


def test_opponent_unit_loss_breaks_ties_at_random() -> None:
    state = _loss_state(_units(_turn_state(), 2, garrison=1, commanders_garrison=1))
    run = _run(state)
    values = [
        run.profile.lose_unit_value(str(arg(a, "zone")), arg(a, "commanders") == 1)
        for a in run.legal
    ]
    assert len(values) == 2 and values[0] == values[1]  # troop == Commander unit
    picks = {W.opponent_unit_loss(_run(state, rng_seed=s)) for s in range(16)}
    assert picks == set(run.legal)


# ===========================================================================
# Contracts
# ===========================================================================


def test_immediate_token_trashes_a_junk_intrigue() -> None:
    junk = "intrigue:twisted_withdrawn:0"
    other = "intrigue:return_the_favor:0"
    state = with_player(_turn_state(), 0, intrigue_cards=(other, junk))
    state = _push(state, FrameKind.CONTRACT_INTRIGUE_TRASH, 0, player=0)
    for seed in range(6):
        action = W.contract_intrigue_trash(_run(state, rng_seed=seed))
        assert action is not None and arg(action, "card_id") == junk


def test_coercive_negotiation_takes_the_best_revealed_contract() -> None:
    state = _push(
        _turn_state(),
        FrameKind.INTRIGUE_TRIGGER_CONTRACT,
        0,
        card_id="intrigue:coercive_negotiation:0",
        turn_owner=0,
    )
    run = _run(state)
    refs = [str(r) for r in _ids(run.legal, "take_trigger_contract", "instance_id")]
    assert len(refs) >= 2
    contracts = tuple(contract_entity(r, 0) for r in refs)
    info = TargetInfo(entities=contracts, min_select=1, max_select=1, forced=True)
    answer = contract_evaluate(run.profile, Request((info,), forced=True), True)
    assert answer.response is not None
    action = W.intrigue_trigger_contract(run)
    assert action is not None and arg(action, "instance_id") == answer.response[0][0]


# ===========================================================================
# Navigation
# ===========================================================================


def test_navigation_setup_fills_each_slot_by_its_value() -> None:
    state = _reset_with("steersman_y_rkoon", "gurney_halleck", "lady_jessica", "chani")
    assert state.decision_stack[-1].kind == "navigation_setup"
    for slot in range(1, 5):
        run = _run(state)
        assert len(run.ctx.navigation_slots) == slot - 1
        values = {
            str(c): run.profile.navigation_value(navigation_number(str(c)), slot, None)
            for c in _ids(run.legal, "place_navigation_card", "card_id")
        }
        action = W.navigation_setup(run)
        assert action is not None
        best = max(values.values())
        if best > 0:
            assert values[str(arg(action, "card_id"))] == best
        state = ENGINE.apply(state, action, legal_actions=run.legal).state
    assert state.decision_stack[-1].kind != "navigation_setup"


def _navigation_state(card: int, **player: object) -> GameState:
    state = _turn_state()
    seat = 0
    state = with_player(
        state,
        seat,
        leader_id="steersman_y_rkoon",
        navigation_slots=(f"intrigue:navigation_card_{card}:0",),
        **player,
    )
    state = with_state(
        state, pending_navigation_plays=((seat, "emperor", "test:plot_course"),)
    )
    return begin_navigation_play(state).state


def test_navigation_choice_plays_the_best_option() -> None:
    state = _navigation_state(
        6, resources=replace(_turn_state().players[0].resources, solari=5)
    )
    run = _run(state)
    options = [int(str(o)) for o in _ids(run.legal, "play_navigation", "option")]
    assert options == [0, 1] and run.first("decline_navigation") is None
    values = {
        o: run.profile.navigation_option_value(6, o, 1, "emperor") for o in options
    }
    action = W.navigation_choice(run)
    assert action is not None
    best = max(v for v in values.values() if v is not None)
    assert values[int(str(arg(action, "option")))] == best


def test_navigation_card_10_declines_an_exchange_below_two() -> None:
    base = _turn_state().players[0].influence
    poor = _navigation_state(10, influence=replace(base, emperor=1))
    run = _run(poor)
    assert run.first("decline_navigation") is not None
    exchange = run.profile.best_influence_exchange(-1, 1)[2]
    assert 0.0 < exchange < 2.0  # worth something, but below the 2.0 literal
    assert W.navigation_choice(_run(poor)) == run.first("decline_navigation")


def test_navigation_card_10_plays_a_good_exchange_and_keeps_the_loss() -> None:
    base = _turn_state().players[0].influence
    state = _navigation_state(10, influence=replace(base, fremen=4, emperor=1))
    memory = Memory()
    action = W.navigation_choice(_run(state, memory))
    assert action is not None and action.action_id == "play_navigation"
    key = (NAVIGATION_INTENT, "intrigue:navigation_card_10:0")
    assert memory.intents[key] == "fremen"


def test_navigation_card_1_remembers_the_faction_it_gains() -> None:
    base = _turn_state().players[0]
    state = _navigation_state(
        1,
        influence=replace(base.influence, emperor=2, fremen=2, spacing_guild=3),
        resources=replace(base.resources, solari=6),
    )
    memory = Memory()
    run = _run(state, memory)
    action = W.navigation_choice(run)
    assert action is not None
    if arg(action, "option") == 1:
        faction = memory.intents[(NAVIGATION_INTENT, "intrigue:navigation_card_1:0")]
        assert faction in ("fremen", "spacing_guild")


# ===========================================================================
# Tech
# ===========================================================================


def _tech_card_state(round_number: int, spice: int) -> GameState:
    state = with_state(_turn_state(), round_number=round_number)
    resources = replace(state.players[0].resources, spice=spice)
    state = with_player(state, 0, resources=resources)
    return state.push_decision(tech_acquisition_frame(0, discount=1, source="test"))


@pytest.mark.parametrize("round_number", [1, 5])
def test_card_tech_discount_buys_the_app_tile(round_number: int) -> None:
    state = _tech_card_state(round_number, spice=12)
    run = _run(state)
    assert run.first("decline_tech") is None  # forced while affordable
    tech_ids = list(
        dict.fromkeys(str(t) for t in _ids(run.legal, "acquire_tech", "tech_id"))
    )
    tiles = tuple(tech_entity(t, 0) for t in tech_ids)
    answer = AcquireTechAbilityDiscount1(tiles[0]).evaluate(
        run.profile, Request((TargetInfo(entities=tiles),))
    )
    action = W.tech_acquisition(run)
    assert action is not None and action.action_id == "acquire_tech"
    if answer.value > 0 and answer.response:
        assert arg(action, "tech_id") == answer.response[0][0]
    else:  # D13: TechTileToAcquire(1)'s tile, even at 0
        best = run.profile.tech_tile_to_acquire(1, False)
        assert best is not None and arg(action, "tech_id") == best.ref


def test_advanced_data_analysis_boxes_the_spy_on_the_worst_post() -> None:
    state = _turn_state()
    posts = tuple(list(POST_INDEX)[:2])
    state = _spies(state, 0, *posts)
    run = _run(state)
    variants = [
        DomainAction(
            "acquire_tech", 0, (("post_id", p), ("tech_id", "advanced_data_analysis"))
        )
        for p in posts
    ]
    spy, _ = run.profile.recall_spy([spy_entity(p, 0) for p in posts])
    assert spy is not None
    chosen = W._tile_action(run, variants, "advanced_data_analysis")
    assert chosen is not None and arg(chosen, "post_id") == spy.ref


def _effects_state(*keys: str, **player: object) -> GameState:
    state = with_player(_turn_state(), 0, **player)
    frame = DecisionFrame(
        kind=FrameKind.TECH_ACQUISITION,
        frame_id="test:tech:effects",
        decision=PlayerDecision(owner=0, prompt="Resolve Tech acquire effects"),
        context=tuple(
            sorted(
                (
                    ("acquire_effects_only", True),
                    (TECH_ACQUIRE_PENDING_KEY, ",".join(keys)),
                )
            )
        ),
    )
    return state.push_decision(frame)


def test_tech_acquire_influence_key_takes_the_memocorders_faction() -> None:
    state = _effects_state("glowglobes:influence", "plasteel_blades:solari")
    run = _run(state)
    tracks = tuple(track_entity(f) for f in FACTIONS)
    answer = MemocordersAcquiredAbility(tech_entity("glowglobes")).evaluate(
        run.profile, Request((TargetInfo(entities=tracks),))
    )
    action = W.tech_acquisition(run)
    assert action is not None
    assert arg(action, "effect") == "influence"  # the first owed key first
    assert answer.response is not None
    assert arg(action, "faction") == answer.response[0][0]


def test_tech_acquire_choice_key_follows_gene_locked_vault() -> None:
    state = _effects_state("gene_locked_vault:intrigue_or_card")
    run = _run(state)
    answer = GeneLockedVaultAcquiredAbility(tech_entity("gene_locked_vault")).evaluate(
        run.profile, Request()
    )
    assert answer.response is not None
    wanted = {0: "intrigue", 1: "card"}[int(answer.response[0][0])]
    action = W.tech_acquisition(run)
    assert action is not None and arg(action, "choice") == wanted


@pytest.mark.parametrize("blow", [True, False])
def test_tech_acquire_shield_wall_key(
    monkeypatch: pytest.MonkeyPatch, blow: bool
) -> None:
    monkeypatch.setattr(Profile, "should_blow_wall", lambda self: blow)
    state = with_state(
        _effects_state("forbidden_weapons:shield_wall"), shield_wall_present=True
    )
    action = W.tech_acquisition(_run(state))
    assert action is not None
    assert (arg(action, "destroy_shield_wall") is True) is blow


def test_secret_project_takes_the_app_tile() -> None:
    state = _reset_with("kota_odax_of_ix", "gurney_halleck", "lady_jessica", "chani")
    assert state.decision_stack[-1].kind == "tech_secret_project"
    run = _run(state)
    tech_ids = [str(t) for t in _ids(run.legal, "choose_secret_project", "tech_id")]
    tiles = tuple(tech_entity(t, run.ctx.seat) for t in tech_ids)
    answer = SecretProjectAbility(leader_entity("kota_odax_of_ix")).evaluate(
        run.profile, Request((TargetInfo(entities=tiles),))
    )
    assert answer.response is not None
    action = W.tech_secret_project(run)
    assert action is not None and arg(action, "tech_id") == answer.response[0][0]


# ===========================================================================
# leader_signet (Servo-Receivers)
# ===========================================================================


def _signet_state(leader: str, state: GameState | None = None) -> GameState:
    """Seat 0 (leader ``leader``) uses its Signet Ring through
    Servo-Receivers' acquire effect."""

    state = with_player(state or _turn_state(), 0, leader_id=leader)
    result = use_leader_signet_for_tech(
        state, 0, source="test:servo", advance_agent_frame=False
    )
    assert result.state.decision_stack[-1].kind == "leader_signet"
    return result.state


def test_kota_reverse_engineering_signet() -> None:
    state = _signet_state(
        "kota_odax_of_ix", _give_tech(_turn_state(), 0, "training_depot")
    )
    run = _run(state)
    ability = ReverseEngineeringSignetAbility(leader_entity("kota_odax_of_ix"))
    answer = ability.evaluate(
        run.profile,
        Request(
            (
                TargetInfo(options=(0, 1)),
                TargetInfo(entities=(tech_entity("training_depot", 0),)),
            )
        ),
    )
    action = W.leader_signet(run)
    assert action is not None
    if answer.response and answer.response[0][0] == 1:
        assert action == run.first("trash_leader_tech")
    else:
        assert action == run.first("gain_leader_signet_spice")


def test_chani_fedaykin_with_nothing_to_do_only_declines() -> None:
    state = _turn_state()
    resources = replace(state.players[0].resources, water=0)
    state = _signet_state("chani", with_player(state, 0, resources=resources))
    # Nothing to retreat and no water: only the decline is left (auto).
    assert [a.action_id for a in _legal(state)] == ["decline_leader_signet_payment"]


def test_chani_fedaykin_follows_its_evaluate() -> None:
    state = _units(_turn_state(), 0, garrison=1, conflict=2)
    base = state.players[0]
    state = with_player(
        state,
        0,
        influence=replace(base.influence, fremen=2),
        resources=replace(base.resources, water=2),
    )
    state = _signet_state("chani", state)
    run = _run(state)
    counts = sorted(
        {int(str(c)) for c in _ids(run.legal, "retreat_leader_troops", "count")}
    )
    assert counts == [1, 2] and run.first("pay_leader_signet_water") is not None
    fedaykin = FedaykinManeuverSignetAbility(leader_entity("chani"))
    request = Request((TargetInfo(options=(0, 1)), TargetInfo(options=(1, 2))))
    answer = fedaykin.evaluate(run.profile, request)
    action = W.leader_signet(run)
    assert action is not None
    if answer.response is None:
        assert action == run.first("decline_leader_signet_payment")
    elif answer.response[0][0] == fedaykin.WATER:
        assert action == run.first("pay_leader_signet_water")
    else:
        assert action.action_id == "retreat_leader_troops"
        assert arg(action, "count") == answer.response[1][0]
        assert arg(action, "commanders") is None  # troops first


def test_esmar_smuggle_spice_takes_bonus_spice_first() -> None:
    state = _reset_with("esmar_tuek", "gurney_halleck", "lady_jessica", "chani")
    state = with_state(
        state,
        maker_bonus_spice=(
            ("deep_desert", 2),
            ("hagga_basin", 1),
            ("imperial_basin", 0),
            ("tuek_sietch", 0),
        ),
    )
    state = _signet_state("esmar_tuek", state)
    run = _run(state)
    assert run.first("decline_leader_signet_payment") is None  # Explicit
    smuggle = SmuggleSpiceSignetAbility(leader_entity("esmar_tuek"))
    place = smuggle.place_value(run.profile)
    action = W.leader_signet(run)
    assert action is not None
    if place > run.profile.spice_value(1):
        assert action.action_id == "place_leader_bonus_spice"
    else:
        # The first Maker space in board order (the first strictly best take).
        order = board_space_order(run.ctx.board)
        first = min(("deep_desert", "hagga_basin"), key=order.index)
        assert action == run.first("take_leader_bonus_spice")
        assert arg(action, "space_id") == first


def test_fenring_corrino_liaison_places_the_spy_without_junk() -> None:
    state = _signet_state("count_hasimir_fenring", _spies(_turn_state(), 0))
    run = _run(state)
    junk, _ = run.profile.card_to_trash(
        [
            card_entity(str(c), 0)
            for c in _ids(run.legal, "trash_leader_card", "card_id")
        ],
        1.0,
    )
    action = W.leader_signet(run)
    assert action is not None
    if junk is None:
        assert action.action_id == "place_leader_spy"
        posts = [str(p) for p in _ids(run.legal, "place_leader_spy", "post_id")]
        best, _ = run.profile.best_post([post_entity(p, 0) for p in posts])
        assert best is not None and arg(action, "post_id") == best.ref
    else:
        assert action.action_id == "trash_leader_card"


def test_duncan_into_the_fray_without_a_placed_agent_only_declines() -> None:
    state = _signet_state("duncan_idaho")
    assert [a.action_id for a in _legal(state)] == ["decline_leader_signet_payment"]


def test_mohiam_listeners_places_a_landsraad_spy() -> None:
    state = _signet_state("gaius_helen_mohiam", _spies(_turn_state(), 0))
    run = _run(state)
    assert run.first("place_leader_spy") is not None
    action = W.leader_signet(run)
    assert action is not None and action.action_id == "place_leader_spy"


def test_uprising_leader_signet_uses_the_agent_effects_rows() -> None:
    state = _turn_state()
    jessica = 3
    assert state.players[jessica].leader_id == "lady_jessica"
    resources = replace(state.players[jessica].resources, spice=3)
    state = with_player(state, jessica, resources=resources)
    state = use_leader_signet_for_tech(
        state, jessica, source="test:servo", advance_agent_frame=False
    ).state
    run = _run(state)
    assert run.first("pay_leader_signet_spice") is not None
    answer = SpiceAgonyAbility(leader_entity("lady_jessica")).evaluate(
        run.profile, Request()
    )
    action = W.leader_signet(run)
    if answer.response is not None and answer.value > 0:
        assert action == run.first("pay_leader_signet_spice")
    else:
        assert action == run.first("decline_leader_signet_payment")


def test_tech_acquire_plain_key_is_resolved_first() -> None:
    state = _effects_state("plasteel_blades:solari", "glowglobes:influence")
    action = W.tech_acquisition(_run(state))
    assert action is not None
    assert (arg(action, "effect"), arg(action, "tech_id")) == (
        "solari",
        "plasteel_blades",
    )


def test_fenring_recalls_the_worst_spy_first_then_places_on_the_best_post() -> None:
    posts = tuple(list(POST_INDEX)[:3])
    state = _signet_state("count_hasimir_fenring", _spies(_turn_state(), 0, *posts))
    state = with_player(state, 0, in_play=())
    run = _run(state)
    recalls = [a for a in run.legal if a.action_id == "recall_spy_for_leader_placement"]
    assert recalls and run.first("place_leader_spy") is None
    spies = [spy_entity(str(arg(a, "post_id")), 0) for a in recalls]
    worst, _ = make_profile(state, 0).recall_spy(spies)
    action = W.leader_signet(run)
    if action is not None and action.action_id == "decline_leader_signet_payment":
        pytest.skip("Corrino Liaison declines here")
    assert action is not None and worst is not None
    assert action.action_id == "recall_spy_for_leader_placement"
    assert arg(action, "post_id") == worst.ref
    state = ENGINE.apply(state, action, legal_actions=run.legal).state
    run = _run(state)
    places = [
        str(arg(a, "post_id")) for a in run.legal if a.action_id == "place_leader_spy"
    ]
    best, _ = run.profile.best_post([post_entity(p, 0) for p in places])
    follow = W.leader_signet(_run(state))
    assert follow is not None and best is not None
    assert arg(follow, "post_id") == best.ref


def test_mohiam_paid_listeners_places_on_the_best_post() -> None:
    state = _signet_state("gaius_helen_mohiam", _spies(_turn_state(), 0))
    resources = replace(state.players[0].resources, spice=2)
    state = with_player(state, 0, resources=resources)
    pay = next(a for a in _legal(state) if a.action_id == "pay_leader_signet_spice")
    state = ENGINE.apply(state, pay, legal_actions=_legal(state)).state
    run = _run(state)
    places = [
        str(arg(a, "post_id")) for a in run.legal if a.action_id == "place_leader_spy"
    ]
    assert places
    best, _ = run.profile.best_post([post_entity(p, 0) for p in places])
    action = W.leader_signet(_run(state))
    assert action is not None and best is not None
    assert arg(action, "post_id") == best.ref


def test_a_key_owed_twice_is_resolved() -> None:
    """Ornithopter Fleet's two troop icons are two identical offers."""

    state = _effects_state("ornithopter_fleet:troops", "ornithopter_fleet:troops")
    run = _run(state)
    assert len(run.legal) == 2 and run.legal[0] == run.legal[1]
    assert W.tech_acquisition(run) == run.legal[0]


@pytest.mark.parametrize(("seed", "deploys"), [(1, True), (5, False)])
def test_duncan_into_the_fray_follows_its_evaluate(seed: int, deploys: bool) -> None:
    """Servo-Receivers during Duncan's Agent turn: ``deploy_leader_agent``
    iff ``IntoTheFraySignetAbility``'s E answers (0.5), else the decline."""

    state = first_decision("agent_effects", config=BLOODLINES, seed=seed)
    seat = _seat(state)
    state = with_player(
        state, seat, leader_id="duncan_idaho", leader_face_id="duncan_idaho"
    )
    state = use_leader_signet_for_tech(
        state, seat, source="test:servo", advance_agent_frame=False
    ).state
    run = _run(state)
    assert run.first("deploy_leader_agent") is not None
    answer = IntoTheFraySignetAbility(leader_entity("duncan_idaho")).evaluate(
        run.profile, Request()
    )
    assert (answer.response is not None and answer.value > 0) is deploys
    wanted = "deploy_leader_agent" if deploys else "decline_leader_signet_payment"
    assert W.leader_signet(_run(state)) == run.first(wanted)


def test_forced_navigation_choice_with_nothing_positive_is_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Profile, "navigation_option_value", lambda self, c, o, s, f: 0.0
    )
    state = _navigation_state(
        6, resources=replace(_turn_state().players[0].resources, solari=5)
    )
    assert _legal(state) and _run(state).first("decline_navigation") is None
    picks = {W.navigation_choice(_run(state, rng_seed=s)) for s in range(12)}
    assert None not in picks and len(picks) > 1  # DefaultRandomChoice


@pytest.mark.parametrize("leader", ["lady_margot_fenring", "staban_tuek"])
def test_uprising_spy_signet_with_an_empty_supply_recalls_the_worst_spy(
    leader: str,
) -> None:
    """Arrakis Informant / Unseen Network (Explicit) with every Spy out: the
    engine offers the recall-first rows beside ``decline_leader_spy_placement``;
    the leader's spy key recalls the worst-post Spy (``spy_answer`` never
    declines) instead of falling back."""

    posts = tuple(list(POST_INDEX)[:3])
    state = with_player(_spies(_turn_state(), 0, *posts), 0, leader_face_id=leader)
    state = _signet_state(leader, state)
    run = _run(state)
    assert run.first("decline_leader_spy_placement") is not None
    recalls = [a for a in run.legal if a.action_id == "recall_spy_for_leader_placement"]
    assert recalls and run.first("place_leader_spy") is None
    worst, _ = make_profile(state, 0).recall_spy(
        [spy_entity(str(arg(a, "post_id")), 0) for a in recalls]
    )
    action = W.leader_signet(run)
    assert worst is not None and action is not None
    assert action.action_id == "recall_spy_for_leader_placement"
    assert arg(action, "post_id") == worst.ref
    if leader != "lady_margot_fenring":
        return
    # The rest of the key: the recalled Spy goes to the best City post.
    state = ENGINE.apply(state, action, legal_actions=run.legal).state
    places = [str(p) for p in _ids(_legal(state), "place_leader_spy", "post_id")]
    best, _ = make_profile(state, 0).best_post([post_entity(p, 0) for p in places])
    follow = W.leader_signet(_run(state))
    assert best is not None and follow is not None
    assert arg(follow, "post_id") == best.ref


def test_card_tech_discount_with_an_empty_answer_buys_the_first_tile() -> None:
    """D13: no tile worth > 0 (round 1, no EarlyMod) and no ``decline_tech``:
    ``TechTileToAcquire(1)``'s tile, the first in stack order at value 0."""

    state = _turn_state()
    tops = ("forbidden_weapons", "gene_locked_vault", "training_depot")
    stacks = tuple(
        (top, *(t for t in stack if t not in tops))
        for top, stack in zip(tops, state.tech_stacks, strict=True)
    )
    state = with_state(state, tech_stacks=stacks, round_number=1)
    resources = replace(state.players[0].resources, spice=4)
    state = with_player(state, 0, resources=resources)
    state = state.push_decision(tech_acquisition_frame(0, discount=1, source="test"))
    run = _run(state)
    assert run.first("decline_tech") is None
    offered = [str(t) for t in _ids(run.legal, "acquire_tech", "tech_id")]
    assert offered == list(tops)
    answer = AcquireTechAbilityDiscount1(tech_entity(tops[0])).evaluate(
        run.profile,
        Request((TargetInfo(entities=tuple(tech_entity(t) for t in tops)),)),
    )
    assert answer.response == ()  # the empty answer (0.5)
    action = W.tech_acquisition(run)
    assert action is not None and arg(action, "tech_id") == "forbidden_weapons"


def test_an_unknown_acquire_key_falls_back() -> None:
    state = _effects_state("plasteel_blades:mystery", "glowglobes:influence")
    run = _run(state)
    assert arg(run.legal[0], "effect") == "mystery"
    assert W.tech_acquisition(run) is None


def test_kota_with_an_unknown_tile_falls_back() -> None:
    state = _signet_state(
        "kota_odax_of_ix", _give_tech(_turn_state(), 0, "training_depot")
    )
    run = _run(state)
    odd = DomainAction("trash_leader_tech", 0, (("tech_id", "mystery_tile"),))
    weird = DecisionRun(run.ctx, run.profile, (*run.legal, odd), run.rng, run.memory)
    assert W.leader_signet(run) is not None
    assert W.leader_signet(weird) is None  # never dropped from the request


def _one_candidate_navigation(card: int, **player: object) -> DecisionRun:
    return _run(_navigation_state(card, **player))


def test_navigation_card_1_keeps_no_intent_for_a_single_faction() -> None:
    """Card 1's gain slot with one candidate Faction is answered without a
    window: no intent is kept (it would never be read and dropped)."""

    base = _turn_state().players[0]
    rich = replace(base.resources, solari=6)
    key = (NAVIGATION_INTENT, "intrigue:navigation_card_1:0")
    play = DomainAction("play_navigation", 0, (("option", 1),))
    lone = replace(base.influence, emperor=2, fremen=2, spacing_guild=0)
    lone = replace(lone, bene_gesserit=0)
    run = _one_candidate_navigation(1, influence=lone, resources=rich)
    W._store_navigation_intent(run, "intrigue:navigation_card_1:0", 1, play)
    assert key not in run.memory.intents  # only Fremen (Emperor triggered)
    state = _navigation_state(1, influence=lone, resources=rich)
    state = ENGINE.apply(state, play, legal_actions=_legal(state)).state
    assert len(_legal(state)) == 1  # the gain slot: one Faction, no window
    two = replace(lone, spacing_guild=3)
    run = _one_candidate_navigation(1, influence=two, resources=rich)
    W._store_navigation_intent(run, "intrigue:navigation_card_1:0", 1, play)
    assert run.memory.intents[key] in ("fremen", "spacing_guild")


def test_navigation_card_10_keeps_no_intent_for_a_single_loss() -> None:
    base = _turn_state().players[0].influence
    lone = replace(base, emperor=0, spacing_guild=0, bene_gesserit=0, fremen=3)
    run = _one_candidate_navigation(10, influence=lone)
    play = DomainAction("play_navigation", 0, (("option", 0),))
    W._store_navigation_intent(run, "intrigue:navigation_card_10:0", 10, play)
    assert (NAVIGATION_INTENT, "intrigue:navigation_card_10:0") not in (
        run.memory.intents
    )


def test_bloodlines_windows_are_registered() -> None:
    for kind in W.HANDLERS:
        assert handler_for(kind) is W.HANDLERS[kind]


def test_an_unknown_action_falls_back() -> None:
    state = _skill_state("imperium:sardaukar_standard:0")
    run = _run(state)
    odd = DomainAction("mystery_action", 0)
    weird = DecisionRun(run.ctx, run.profile, (*run.legal, odd), run.rng, run.memory)
    assert W.skill_choice(weird) is None
