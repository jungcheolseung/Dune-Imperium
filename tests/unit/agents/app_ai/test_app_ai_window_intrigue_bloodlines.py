"""The app_ai Intrigue windows with the Bloodlines and Twisted Intrigues and
the Navigation cards (``windows/intrigue.py``, ``windows/combat.py``).

Real Bloodlines games (``testing.first_decision`` / ``play_until``); the
played card is put in the seat's hand (taken out of every other zone) and
the engine's own frames follow the play.
"""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import bloodlines_cards as bc
from dune_imperium.agents.app_ai.abilities.base import Answer
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    navigation_trash_pick,
)
from dune_imperium.agents.app_ai.abilities.intrigue import choose_faction_influence
from dune_imperium.agents.app_ai.catalog import card_entity, spy_entity, track_entity
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import bloodlines as BW
from dune_imperium.agents.app_ai.windows import combat
from dune_imperium.agents.app_ai.windows import intrigue as W
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.navigation import begin_navigation_play

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


def _apply(state: GameState, action: DomainAction) -> GameState:
    return ENGINE.apply(state, action, legal_actions=_legal(state)).state


def _find(state: GameState, action_id: str, **args: object) -> DomainAction:
    for action in _legal(state):
        if action.action_id == action_id and all(
            dict(action.arguments).get(k) == v for k, v in args.items()
        ):
            return action
    raise AssertionError(f"{action_id} {args} is not legal")


def _holding(state: GameState, seat: int, *instances: str) -> GameState:
    """``seat`` holds exactly ``instances`` (taken out of every other zone)."""

    for other in state.players:
        if other.player_id != seat and set(other.intrigue_cards) & set(instances):
            state = with_player(
                state,
                other.player_id,
                intrigue_cards=tuple(
                    i for i in other.intrigue_cards if i not in instances
                ),
            )
    state = with_state(
        state,
        intrigue_deck=tuple(i for i in state.intrigue_deck if i not in instances),
        intrigue_discard=tuple(i for i in state.intrigue_discard if i not in instances),
    )
    return with_player(state, seat, intrigue_cards=tuple(instances))


def _units(
    state: GameState,
    seat: int,
    *,
    garrison: int = 0,
    conflict: int = 0,
    commanders_garrison: int = 0,
    commanders_conflict: int = 0,
) -> GameState:
    return with_player(
        state,
        seat,
        troops_garrison=garrison,
        troops_conflict=conflict,
        troops_supply=12 - garrison - conflict,
        commanders_garrison=commanders_garrison,
        commanders_conflict=commanders_conflict,
    )


def _give_tech(state: GameState, seat: int, *tech_ids: str) -> GameState:
    stacks = tuple(
        tuple(t for t in stack if t not in tech_ids) for stack in state.tech_stacks
    )
    return with_player(with_state(state, tech_stacks=stacks), seat, tech_ids=tech_ids)


def _turn(*instances: str) -> GameState:
    """The first turn-start prompt of a Bloodlines game, the seat holding
    ``instances``."""

    state = first_decision("turn", config=BLOODLINES, seed=3)
    return _holding(state, _seat(state), *instances)


def _combat(*instances: str) -> GameState:
    """The first Combat Intrigue prompt, the seat holding ``instances``."""

    state = first_decision("combat_intrigue", config=BLOODLINES, seed=3)
    return _holding(state, _seat(state), *instances)


def _source(
    state: GameState, instance: str, memory: Memory, *, combat_turn: bool = False
) -> tuple[float, DomainAction | None]:
    """The intrigue key of ``instance``: its value and our action."""

    run = _run(state, memory)
    plays = [a for a in run.by_id("play_intrigue") if arg(a, "card_id") == instance]
    (source,) = W.intrigue_play_sources(run, plays, combat=combat_turn)
    assert source.evaluate is not None
    return source.evaluate()


def _recorded(memory: Memory, instance: str) -> Answer:
    answer = memory.intents[(W.INTENT, instance)]
    assert isinstance(answer, Answer)
    return answer


def _play_recorded(
    state: GameState,
    instance: str,
    memory: Memory,
    option: int,
    *,
    combat_turn: bool = False,
) -> GameState:
    """Evaluate the key (records the answer), then play ``option``.

    The recorded answer stays the play's answer (the play's event index is
    the evaluation's log length), so the follow-up slots replay it.
    """

    _source(state, instance, memory, combat_turn=combat_turn)
    return _apply(state, _find(state, "play_intrigue", card_id=instance, option=option))


def _choice(state: GameState, memory: Memory, rng_seed: int = 0) -> DomainAction:
    action = W.intrigue_choice(_run(state, memory, rng_seed))
    assert action is not None
    return action


# ===========================================================================
# Requests and play keys
# ===========================================================================


def test_requests_of_the_bloodlines_cards() -> None:
    state = _turn()
    seat = _seat(state)
    state = _units(state, seat, garrison=2, conflict=3, commanders_garrison=1)
    state = with_player(state, seat, commanders_conflict=1, spy_post_ids=())
    ctx = _run(state).ctx
    insider = W.intrigue_request(ctx, "intrigue:insider_information:0", False, (0, 1))
    assert insider.infos[0].options == (0, 1)
    assert len(insider.infos) == 3
    rapid = W.intrigue_request(ctx, "intrigue:rapid_engineering:0", False, (1,))
    assert rapid.infos[0].options == (1,)
    assert [e.ref for e in rapid.infos[2].entities] == list(FACTIONS)
    devious = W.intrigue_request(ctx, "intrigue:twisted_devious:0", False, (0, 1))
    assert devious.infos[2].options == (0, 1, 2)  # garrison troops + Commander
    survive = W.intrigue_request(ctx, "intrigue:the_strong_survive:0", True, (0, 1))
    assert survive.infos[1].options == (0, 1, 2, 3)  # Conflict troops + Commander
    research = W.intrigue_request(ctx, "intrigue:battlefield_research:0", True)
    assert research.infos[0].options == (0, 1, 2, 3)
    assert W.intrigue_request(ctx, "intrigue:tenuous_bond:0", True).infos == ()
    bond = W.intrigue_request(ctx, "intrigue:tenuous_bond:0", False)
    assert [e.ref for e in bond.infos[0].entities] == [
        f for f in FACTIONS if getattr(state.players[seat].influence, f) >= 1
    ]
    pools = W.intrigue_request(ctx, "intrigue:sacred_pools:0", False)
    assert [e.ref for e in pools.infos[0].entities] == list(ctx.hand)
    # Commanders count as troops (D1) in the Uprising retreat requests too.
    ground = W.intrigue_request(ctx, "intrigue:go_to_ground:0", True)
    assert ground.infos[0].options == (0, 1, 2, 3)


@pytest.mark.parametrize(
    "instance",
    [
        "intrigue:emperor_s_invitation:0",
        "intrigue:seize_production:0",
        "intrigue:twisted_discerning:0",
        "intrigue:sleeper_unit:0",
    ],
)
def test_two_option_plot_key_plays_the_answer_option(instance: str) -> None:
    state = _turn(instance)
    seat = _seat(state)
    resources = replace(state.players[seat].resources, solari=4)
    state = with_player(state, seat, resources=resources)
    memory = Memory()
    value, action = _source(state, instance, memory)
    answer = _recorded(memory, instance)
    if action is None:
        assert answer.response is None or value <= 0 or not answer.response[0]
        return
    assert answer.response is not None
    assert arg(action, "option") == answer.response[0][0]


def test_the_strong_survive_combat_key_plays_the_answer_option() -> None:
    instance = "intrigue:the_strong_survive:0"
    state = _combat(instance)
    memory = Memory()
    _value, action = _source(state, instance, memory, combat_turn=True)
    answer = _recorded(memory, instance)
    assert answer.response is not None and action is not None
    assert arg(action, "option") == answer.response[0][0]
    assert combat.combat_intrigue(_run(state, Memory())) in (
        action,
        _find(state, "pass_combat_intrigue"),
    )


# ===========================================================================
# Plot follow-ups (intrigue_choice)
# ===========================================================================


def test_twisted_sadistic_pays_its_unit_by_lose_unit_pick() -> None:
    instance = "intrigue:twisted_sadistic:0"
    state = _turn(instance)
    seat = _seat(state)
    state = _units(state, seat, garrison=2, conflict=1, commanders_garrison=1)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    assert state.decision_stack[-1].kind == "intrigue_choice"
    run = _run(state, memory)
    options = [
        (str(arg(a, "zone")), arg(a, "commanders") == 1)
        for a in run.legal
        if a.action_id == "lose_intrigue_troop"
    ]
    pick = bc.lose_unit_pick(run.profile, options)
    action = _choice(state, memory)
    assert (str(arg(action, "zone")), arg(action, "commanders") == 1) == pick
    assert pick is not None and pick[1] is False  # troops before Commanders


def test_twisted_ambitious_loses_three_units_then_gains_the_answer_track() -> None:
    instance = "intrigue:twisted_ambitious:0"
    state = _turn(instance)
    seat = _seat(state)
    state = _units(state, seat, garrison=4)
    leader = (seat + 1) % 4
    influence = replace(state.players[leader].influence, fremen=3)
    state = with_player(state, leader, influence=influence)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    answer = _recorded(memory, instance)
    for _ in range(3):
        action = _choice(state, memory)
        assert action.action_id == "lose_intrigue_troop"
        state = _apply(state, action)
    action = _choice(state, memory)
    assert action.action_id == "choose_intrigue_faction"
    if answer.response is not None:
        assert arg(action, "faction") == answer.response[0][0]


def test_twisted_insidious_gives_the_junk_card_to_the_first_opponent() -> None:
    instance = "intrigue:twisted_insidious:0"
    junk = "intrigue:twisted_withdrawn:0"
    other = "intrigue:return_the_favor:0"
    state = _turn(instance, other, junk)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    run = _run(state, memory)
    gives = [a for a in run.legal if a.action_id == "give_intrigue_card"]
    action = _choice(state, memory)
    assert action.action_id == "give_intrigue_card"
    assert arg(action, "card_id") == junk
    first = next(a for a in gives if arg(a, "card_id") == junk)
    assert arg(action, "player") == arg(first, "player")


def test_twisted_unnatural_trashes_the_answer_card() -> None:
    instance = "intrigue:twisted_unnatural:0"
    junk = "intrigue:twisted_withdrawn:0"
    state = _turn(instance, "intrigue:return_the_favor:0", junk)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    action = _choice(state, memory)
    assert action.action_id == "trash_intrigue_hand_card"
    assert arg(action, "card_id") == junk


def test_twisted_controlled_peek_follows_the_lltf_evaluator() -> None:
    instance = "intrigue:twisted_controlled:0"
    state = _turn(instance)
    seat = _seat(state)
    resources = replace(state.players[seat].resources, solari=3)
    state = with_player(state, seat, resources=resources)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    peeked = str(dict(state.decision_stack[-1].context)["peeked_card_id"])
    assert peeked == state.players[seat].deck[0]
    run = _run(state, memory)
    wanted = bc.controlled_peek_choice(run.profile, card_entity(peeked, seat))
    assert _choice(state, memory).action_id == wanted


def test_twisted_devious_trashes_the_answer_card_or_deploys_its_count() -> None:
    instance = "intrigue:twisted_devious:0"
    state = _turn(instance)
    seat = _seat(state)
    state = _units(state, seat, garrison=3)
    memory = Memory()
    _value, action = _source(state, instance, memory)
    answer = _recorded(memory, instance)
    if action is None or answer.response is None:
        pytest.skip("Devious is not worth playing here")
    state = _apply(state, action)
    choice = _choice(state, memory)
    if answer.response[0][0] == 0:
        assert choice.action_id == "trash_intrigue_card"
        assert arg(choice, "card_id") == answer.response[1][0]
    else:
        assert choice.action_id == "deploy_intrigue_troops"
        assert arg(choice, "count") == len(answer.response[1])


def test_twisted_discerning_discards_the_answer_card() -> None:
    instance = "intrigue:twisted_discerning:0"
    state = _turn(instance)
    memory = Memory()
    state = _play_recorded(state, instance, memory, 0)
    answer = _recorded(memory, instance)
    action = _choice(state, memory)
    assert action.action_id == "choose_intrigue_discard"
    if answer.response is not None and answer.response[0][0] == 0:
        assert arg(action, "card_id") == answer.response[1][0]


def test_sacred_pools_discards_the_answer_card() -> None:
    instance = "intrigue:sacred_pools:0"
    state = _turn(instance)
    memory = Memory()
    W._record(
        _run(state, memory),
        instance,
        Answer(5.0, ((_run(state).ctx.hand[-1],),)),
        len(state.event_log),
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    action = _choice(state, memory)
    assert action.action_id == "choose_intrigue_discard"
    assert arg(action, "card_id") == state.players[_seat(state)].hand[-1]


def test_rapid_engineering_gains_the_answer_tracks_in_order() -> None:
    instance = "intrigue:rapid_engineering:0"
    state = _turn(instance)
    seat = _seat(state)
    state = _give_tech(state, seat, "training_depot", "glowglobes", "delivery_bay")
    memory = Memory()
    W._record(
        _run(state, memory),
        instance,
        Answer(2.0, ((1,), ("fremen", "emperor"))),
        len(state.event_log),
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=1))
    first = _choice(state, memory)
    assert arg(first, "faction") == "fremen"
    state = _apply(state, first)
    second = _choice(state, memory)
    assert arg(second, "faction") == "emperor"


def test_insider_information_recalls_the_answer_spy_and_trashes_its_junk() -> None:
    instance = "intrigue:insider_information:0"
    state = _turn(instance)
    seat = _seat(state)
    posts = ("emperor-sardaukar-dutiful-service", "bene-gesserit-espionage-secrets")
    state = with_player(state, seat, spy_post_ids=posts, spies_supply=1)
    memory = Memory()
    W._record(
        _run(state, memory),
        instance,
        Answer(4.0, ((0,), (posts[1],), ())),
        len(state.event_log),
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    recall = _choice(state, memory)
    assert recall.action_id == "recall_spy_for_intrigue"
    assert arg(recall, "post_id") == posts[1]
    state = _apply(state, recall)
    # The answer's ``()``: trash nothing.
    assert _choice(state, memory).action_id == "decline_intrigue_trash"


def test_sleeper_unit_recalls_the_answer_spy() -> None:
    instance = "intrigue:sleeper_unit:0"
    state = _turn(instance)
    seat = _seat(state)
    posts = ("emperor-sardaukar-dutiful-service", "bene-gesserit-espionage-secrets")
    state = with_player(state, seat, spy_post_ids=posts, spies_supply=1)
    memory = Memory()
    W._record(
        _run(state, memory),
        instance,
        Answer(4.0, ((1,), (posts[0],))),
        len(state.event_log),
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=1))
    action = _choice(state, memory)
    assert action.action_id == "recall_spy_for_intrigue"
    assert arg(action, "post_id") == posts[0]


def test_tenuous_bond_loses_the_answer_track_and_gains_the_pre_loss_pick() -> None:
    instance = "intrigue:tenuous_bond:0"
    state = _turn(instance)
    seat = _seat(state)
    influence = replace(state.players[seat].influence, emperor=2, fremen=1)
    state = with_player(state, seat, influence=influence)
    memory = Memory()
    run = _run(state, memory)
    W._record(run, instance, Answer(3.0, (("emperor",),)), len(state.event_log))
    swap = memory.intents[(W.INTENT_SWAP_GAIN, instance)]
    tracks = W._gain_targeting(run.ctx, "emperor")
    assert isinstance(swap, Answer)
    assert swap == choose_faction_influence(_run(state).profile, tracks)
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    lose = _choice(state, memory)
    assert arg(lose, "faction") == "emperor"
    state = _apply(state, lose)
    gain = _choice(state, memory)
    assert swap.response is not None
    assert arg(gain, "faction") == swap.response[0][0]


# ===========================================================================
# Combat follow-ups
# ===========================================================================


def test_battlefield_research_retreats_its_answer_count_troops_first() -> None:
    instance = "intrigue:battlefield_research:0"
    state = _combat(instance)
    seat = _seat(state)
    state = _units(state, seat, conflict=1, commanders_conflict=1)
    # Spice for a tile: an Acquire Tech with nothing to buy would leave the
    # card unplayable (user ruling 2026-10-06).
    resources = replace(state.players[seat].resources, spice=10)
    state = with_player(state, seat, resources=resources)
    memory = Memory()
    W._record(
        _run(state, memory), instance, Answer(2.0, ((0, 1),)), len(state.event_log)
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    action = _choice(state, memory)
    assert action.action_id == "retreat_intrigue_troops"
    assert arg(action, "count") == 2
    assert arg(action, "commanders") == 1  # the troop first, then the Commander


def test_the_strong_survive_retreats_one_then_trashes_junk_or_declines() -> None:
    instance = "intrigue:the_strong_survive:0"
    state = _combat(instance)
    seat = _seat(state)
    state = _units(state, seat, conflict=2)
    memory = Memory()
    W._record(
        _run(state, memory), instance, Answer(150.0, ((1,), (0,))), len(state.event_log)
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=1))
    retreat = _choice(state, memory)
    assert arg(retreat, "count") == 1
    state = _apply(state, retreat)
    run = _run(state, memory)
    cards = [
        card_entity(str(arg(a, "card_id")), seat)
        for a in run.legal
        if a.action_id == "trash_intrigue_card"
    ]
    junk, _ = _run(state, memory).profile.card_to_trash(cards, 1.0)
    action = _choice(state, memory)
    if junk is None:
        assert action.action_id == "decline_intrigue_trash"
    else:
        assert action.action_id == "trash_intrigue_card"


def test_tenuous_bond_combat_trashes_the_tenuous_bond_pick() -> None:
    instance = "intrigue:tenuous_bond:0"
    state = _combat(instance)
    seat = _seat(state)
    paid = tuple(
        i for i in state.imperium_deck if card_entity(i).int_attr("PersuasionCost") >= 1
    )[:2]
    assert len(paid) == 2
    state = with_state(
        state, imperium_deck=tuple(i for i in state.imperium_deck if i not in paid)
    )
    me = state.players[seat]
    state = with_player(state, seat, discard_pile=(*me.discard_pile, *paid))
    memory = Memory()
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=1))
    run = _run(state, memory)
    cards = [
        card_entity(str(arg(a, "card_id")), seat)
        for a in run.legal
        if a.action_id == "trash_intrigue_card"
    ]
    assert set(paid) <= {c.ref for c in cards}
    pick = bc.tenuous_bond_trash_pick(_run(state, memory).profile, cards)
    action = _choice(state, memory)
    assert pick is not None and arg(action, "card_id") == pick.ref


def test_twisted_shrewd_loses_a_conflict_unit() -> None:
    instance = "intrigue:twisted_shrewd:0"
    state = _combat(instance)
    seat = _seat(state)
    state = _units(state, seat, garrison=2, conflict=1, commanders_conflict=1)
    memory = Memory()
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=0))
    action = _choice(state, memory)
    assert action.action_id == "lose_intrigue_troop"
    assert arg(action, "zone") == "conflict" and arg(action, "commanders") is None


# ===========================================================================
# Endgame (Grasp Arrakis, wild pairs)
# ===========================================================================


def _endgame(seat_cards: Sequence[str], *instances: str) -> GameState:
    """The first Endgame window, its seat holding ``instances`` and exactly
    ``seat_cards`` face up (Objectives face down)."""

    state = first_decision("endgame_intrigue", config=BLOODLINES, seed=3)
    seat = _seat(state)
    for other in state.players:
        if other.player_id == seat:
            continue
        won = tuple(c for c in other.won_conflict_ids if c not in seat_cards)
        state = with_player(
            state,
            other.player_id,
            won_conflict_ids=won,
            face_down_battle_card_ids=tuple(
                c
                for c in other.face_down_battle_card_ids
                if c in (*won, *other.objective_ids)
            ),
        )
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        won_conflict_ids=tuple(seat_cards),
        face_down_battle_card_ids=me.objective_ids,
    )
    return _holding(state, seat, *instances)


def test_bloodlines_endgame_pairs_two_wild_conflicts() -> None:
    state = _endgame(("skirmish_wild", "storms_in_the_south"))
    run = _run(state)
    matches = [a for a in run.legal if a.action_id == "match_endgame_wild_icon"]
    assert len(matches) == 1
    assert combat.endgame_intrigue(run) == matches[0]


def test_grasp_arrakis_flips_after_the_pairs_are_scored() -> None:
    instance = "intrigue:grasp_arrakis:0"
    cards = (
        "storms_in_the_south",
        "battle_for_arrakeen",
        "protect_the_sietches",
        "test_of_loyalty",
    )
    state = _endgame(cards, instance)
    memory = Memory()
    run = _run(state, memory)
    first = combat.endgame_intrigue(run)
    assert first is not None and first.action_id == "match_endgame_wild_icon"
    state = _apply(state, first)
    second = combat.endgame_intrigue(_run(state, memory))
    assert second == _find(state, "play_intrigue", card_id=instance, option=1)
    state = _apply(state, second)
    run = _run(state, memory)
    flips = [
        str(arg(a, "card_id")) for a in run.legal if a.action_id == "flip_battle_card"
    ]
    wanted = bc.grasp_arrakis_flip_pick(run.profile, flips)
    assert arg(_choice(state, memory), "card_id") == wanted


# ===========================================================================
# Navigation follow-ups
# ===========================================================================


def _navigation(card: int, **player: object) -> GameState:
    state = first_decision("turn", config=BLOODLINES, seed=3)
    seat = _seat(state)
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


def test_navigation_card_1_gains_the_remembered_faction() -> None:
    base = first_decision("turn", config=BLOODLINES, seed=3)
    seat = _seat(base)
    me = base.players[seat]
    state = _navigation(
        1,
        influence=replace(me.influence, emperor=2, fremen=2, spacing_guild=3),
        resources=replace(me.resources, solari=6),
    )
    memory = Memory()
    state = _apply(state, _find(state, "play_navigation", option=1))
    key = (W.NAVIGATION_INTENT, "intrigue:navigation_card_1:0")
    memory.intents[key] = "fremen"
    action = _choice(state, memory)
    assert arg(action, "faction") == "fremen"
    assert key not in memory.intents


def test_navigation_card_5_trashes_by_chroniclers_ranking() -> None:
    state = _navigation(5)
    state = _apply(state, _find(state, "play_navigation", option=0))
    memory = Memory()
    run = _run(state, memory)
    cards = [
        card_entity(str(arg(a, "card_id")), run.ctx.seat)
        for a in run.legal
        if a.action_id == "trash_intrigue_card"
    ]
    pick = navigation_trash_pick(_run(state, memory).profile, cards)
    action = _choice(state, memory)
    if pick is None:
        assert action.action_id == "decline_intrigue_trash"
    else:
        assert arg(action, "card_id") == pick.ref


def test_navigation_card_10_loses_the_exchange_faction_then_gains() -> None:
    base = first_decision("turn", config=BLOODLINES, seed=3)
    seat = _seat(base)
    me = base.players[seat]
    state = _navigation(10, influence=replace(me.influence, emperor=3, fremen=1))
    memory = Memory()
    run = _run(state, memory)
    play = _find(state, "play_navigation", option=0)
    BW._store_navigation_intent(run, "intrigue:navigation_card_10:0", 10, play)
    key = (W.NAVIGATION_INTENT, "intrigue:navigation_card_10:0")
    lost = memory.intents[key]
    state = _apply(state, play)
    lose = _choice(state, memory)
    assert lose.action_id == "choose_intrigue_faction" and arg(lose, "faction") == lost
    state = _apply(state, lose)
    gain = _choice(state, memory)
    assert gain.action_id == "choose_intrigue_faction"
    offered = [
        str(arg(a, "faction"))
        for a in _legal(state)
        if a.action_id == "choose_intrigue_faction"
    ]
    tracks = [track_entity(f) for f in FACTIONS if f in offered]
    answer = choose_faction_influence(_run(state, memory).profile, tracks)
    assert answer.response is not None
    assert arg(gain, "faction") == answer.response[0][0]


def test_navigation_intrigue_choice_never_reads_an_intrigue_ability() -> None:
    """A Navigation card is not an Intrigue card: its slots never build an
    Intrigue entity (``intrigue_entity`` would raise)."""

    state = _navigation(2)
    seat = _seat(state)
    me = state.players[seat]
    assert me.spies_supply > 0
    state = _apply(state, _find(state, "play_navigation", option=0))
    action = _choice(state, Memory())
    assert action.action_id == "place_intrigue_spy"


def test_navigation_card_2_recall_takes_the_worst_post_spy() -> None:
    base = first_decision("turn", config=BLOODLINES, seed=3)
    seat = _seat(base)
    posts = ("emperor-sardaukar-dutiful-service", "bene-gesserit-espionage-secrets")
    state = _navigation(2, spy_post_ids=posts, spies_supply=1)
    state = _apply(state, _find(state, "play_navigation", option=1))
    run = _run(state)
    spies = [
        spy_entity(str(arg(a, "post_id")), seat)
        for a in run.legal
        if a.action_id == "recall_spy_for_intrigue"
    ]
    worst, _ = _run(state).profile.recall_spy(spies)
    action = _choice(state, Memory())
    assert worst is not None and arg(action, "post_id") == worst.ref


def test_devious_deploy_sends_a_commander_first_to_activate_a_skill() -> None:
    instance = "intrigue:twisted_devious:0"
    state = _turn(instance)
    seat = _seat(state)
    state = _units(state, seat, garrison=2, commanders_garrison=1)
    stack = tuple(k for k in state.skill_stack if k != "skill:fierce:0")
    face_up = tuple(k for k in state.skill_face_up if k != "skill:fierce:0")
    state = with_state(state, skill_stack=stack, skill_face_up=face_up)
    state = with_player(state, seat, skill_ids=("skill:fierce:0",))
    memory = Memory()
    W._record(
        _run(state, memory), instance, Answer(100.0, ((1,), (0,))), len(state.event_log)
    )
    state = _apply(state, _find(state, "play_intrigue", card_id=instance, option=1))
    action = _choice(state, memory)
    assert action.action_id == "deploy_intrigue_troops"
    # D6: a Skill is held and no Commander fights yet: the Commander first.
    assert arg(action, "count") == 1 and arg(action, "commanders") == 1
