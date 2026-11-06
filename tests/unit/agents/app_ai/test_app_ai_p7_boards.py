"""The app AI's board on P7's new combinations: Bloodlines and its Tech
Module on the original board (P7c), Rise of Ix on the Uprising board (P7f).

The AI's spaces, Commander and Ixian Embassy spaces and observation posts
follow the engine's for the same configuration."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.catalog import (
    ACQUIRE_COMMANDER_ABILITY,
    ACQUIRE_TECH_ABILITY,
    POST_INDEX,
    board_space_ids,
    space_archetype,
    space_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.sardaukar import commander_setup_space_ids
from dune_imperium.content.core.icons import AgentIcon
from dune_imperium.content.registry.tech import ixian_embassy_in_play
from dune_imperium.content.rulesets import content_for

IMPERIUM = BaseGame.IMPERIUM
CONFIGS = {
    "original_bloodlines": RulesetConfig(base_game=IMPERIUM, bloodlines=True),
    "original_bloodlines_tech": RulesetConfig(
        base_game=IMPERIUM, bloodlines=True, tech_module=True
    ),
    "original_immortality_bloodlines": RulesetConfig(
        base_game=IMPERIUM, immortality=True, bloodlines=True
    ),
    "original_ix_bloodlines": RulesetConfig(
        base_game=IMPERIUM, rise_of_ix=True, bloodlines=True
    ),
    "uprising_ix": RulesetConfig(rise_of_ix=True),
    "uprising_ix_bloodlines": RulesetConfig(rise_of_ix=True, bloodlines=True),
    "uprising_bloodlines_tech": RulesetConfig(bloodlines=True, tech_module=True),
}


def _board(config: RulesetConfig) -> Board:
    """The AI's board with every Leader's own space (Tuek's Sietch) in."""

    return Board.of(config)._replace(tueks_sietch=True)


def _posts(space_id: str, board: Board) -> tuple[int, ...]:
    posts = space_entity(space_id, board).attr("ObservationPosts", ())
    assert isinstance(posts, tuple)
    return posts


@pytest.mark.parametrize("name", CONFIGS)
def test_the_ais_spaces_are_the_engines(name: str) -> None:
    config = CONFIGS[name]
    engine = {space.space_id for space in content_for(config).board_spaces}
    board = _board(config)
    assert set(board_space_ids(board)) == engine
    assert set(board_space_order(board)) == engine
    for space_id in engine:
        assert space_archetype(space_id, board)  # every space has an archetype


@pytest.mark.parametrize("name", CONFIGS)
def test_commanders_sit_where_the_engine_sets_them(name: str) -> None:
    """[Bloodlines p. 3] on the original board, and with Rise of Ix the two
    covered spaces' Commanders on Dreadnought and Tech Negotiation
    [Bloodlines p. 7] (docs/rules/bloodlines.md section 2a)."""

    config = CONFIGS[name]
    board = _board(config)
    with_commander = {
        space_id
        for space_id in board_space_ids(board)
        if ACQUIRE_COMMANDER_ABILITY in space_entity(space_id, board).ability_ids
    }
    expected = commander_setup_space_ids(config.base_game, rise_of_ix=config.rise_of_ix)
    assert with_commander == (set(expected) if config.bloodlines else set())


@pytest.mark.parametrize("name", CONFIGS)
def test_the_embassys_acquire_tech_is_on_the_boards_landsraad_spaces(
    name: str,
) -> None:
    """The Ixian Embassy's Acquire Tech on a Landsraad visit [Bloodlines
    p. 7], on whichever board (docs/rules/bloodlines.md section 5, P7c);
    none with Rise of Ix, whose Ix board replaces the Embassy (its
    Dreadnought space prints its own)."""

    config = CONFIGS[name]

    def with_tech(board: Board) -> set[str]:
        return {
            space_id
            for space_id in board_space_ids(board)
            if ACQUIRE_TECH_ABILITY in space_entity(space_id, board).ability_ids
        }

    board = _board(config)
    printed = with_tech(board._replace(tech_module=False))
    landsraad = {
        space.space_id
        for space in content_for(config).board_spaces
        if space.agent_icon is AgentIcon.LANDSRAAD
    }
    embassy = landsraad if ixian_embassy_in_play(config) else set()
    assert with_tech(board) == printed | embassy


@pytest.mark.parametrize("name", ["uprising_ix", "uprising_ix_bloodlines"])
def test_uprising_ix_posts_observe_the_engines_spaces(name: str) -> None:
    """P7f's posts: each post's index is on exactly the spaces it observes."""

    config = CONFIGS[name]
    board = _board(config)
    for post in content_for(config).observation_posts:
        index = POST_INDEX[post.post_id]
        observing = {
            space_id
            for space_id in board_space_ids(board)
            if index in _posts(space_id, board)
        }
        assert observing == set(post.connected_space_ids), post.post_id


def test_the_original_board_has_no_post_to_take() -> None:
    """No observation post on the original board, so no free one."""

    config = RulesetConfig(base_game=IMPERIUM, bloodlines=True)
    p = make_profile(first_decision("turn", config=config))
    assert p.ctx.observation_post_ids() == ()
    assert not p._free_post()


def test_prudent_diplomacy_through_servo_receivers_answers_its_refusal() -> None:
    """The original Duke Leto's Prudent Diplomacy (spice 1 -> Influence 1
    where an opponent leads, docs/rules/imperium-base.md section 11) in the
    Signet frame Servo Receivers opens on the original board (P7c): the
    frame offers the payment's refusal, which is the Optional key's empty
    answer, as Final Delivery's."""

    from dataclasses import replace

    from dune_imperium.agents.app_ai.testing import with_player
    from dune_imperium.agents.app_ai.windows import bloodlines as W
    from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
    from dune_imperium.core.decisions import PlayerDecision
    from dune_imperium.rules.engine import UprisingRulesEngine
    from dune_imperium.rules.leader_abilities import use_leader_signet_for_tech

    config = RulesetConfig(base_game=IMPERIUM, bloodlines=True, tech_module=True)
    state = first_decision("turn", config=config)
    seat = make_profile(state).ctx.seat
    other = (seat + 1) % 4
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        leader_id="duke_leto_atreides",
        resources=replace(me.resources, spice=3),
        influence=replace(me.influence, emperor=0),
    )
    them = state.players[other]
    state = with_player(state, other, influence=replace(them.influence, emperor=2))
    state = use_leader_signet_for_tech(
        state, seat, source="test:servo", advance_agent_frame=False
    ).state
    assert state.decision_stack[-1].kind == "leader_signet"
    engine = UprisingRulesEngine()
    assert isinstance(engine.current_decision(state), PlayerDecision)
    legal = engine.whole_actions(state, seat)
    ids = {a.action_id for a in legal}
    assert ids == {"choose_leader_signet_influence", "decline_leader_signet_payment"}
    profile = make_profile(state, seat)
    run = DecisionRun(profile.ctx, profile, legal, profile.rng, Memory())
    assert W.leader_signet(run) in legal


def test_a_signet_that_prices_the_tiles_again_sees_servo_receivers_at_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rise of Ix beside Bloodlines Tech (P7): Servo Receivers' acquire value
    is the Leader's Signet, and Viscount Hundro Moritani's Couriers is worth
    the Freighter, whose selection values the face-up tiles. The inner ask
    sees Servo Receivers worth nothing (docs/app-ai-plan.md 14.3); seeds 2001
    and 2011 of original + Ix + Bloodlines + Tech recursed without it."""

    from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
        ServoReceiversAcquiredAbility,
    )
    from dune_imperium.agents.app_ai.catalog import tech_entity
    from dune_imperium.agents.app_ai.profile import Profile
    from dune_imperium.agents.app_ai.testing import with_player

    config = RulesetConfig(
        base_game=IMPERIUM, rise_of_ix=True, bloodlines=True, tech_module=True
    )
    state = first_decision("turn", config=config)
    seat = make_profile(state).ctx.seat
    hundro = "viscount_hundro_moritani"
    state = with_player(state, seat, leader_id=hundro, leader_face_id=hundro)
    p = make_profile(state, seat)
    servo = ServoReceiversAcquiredAbility(tech_entity("servo_receivers", seat))
    asked: list[float] = []

    def freighter_value(self: Profile) -> float:
        inner = servo.specific_acquire_value(self).sum  # the loop asks again
        asked.append(inner)
        return 1.0

    monkeypatch.setattr(Profile, "freighter_value", freighter_value)
    servo.specific_acquire_value(p)
    assert asked == [0.0]
    assert p.servo_receivers_valuing is False


def test_a_ghola_copy_of_test_of_humanity_is_answered_as_the_card() -> None:
    """Ghola "copies the entire Agent box of the card it's grafted to"
    [Immortality p. 14]: grafted to the original Test of Humanity, its
    victims' frame names the Ghola but carries the box's
    ``or_lose_deployed_troop`` (seed 2014 of original + Immortality +
    Bloodlines + Tech). ``TestOfHumanityDeferredAbility`` answers it."""

    from dune_imperium.agents.app_ai.abilities.original_imperium import (
        TestOfHumanityDeferredAbility,
    )
    from dune_imperium.agents.app_ai.catalog import card_entity
    from dune_imperium.agents.app_ai.windows import uprising
    from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
    from dune_imperium.core.actions import DomainAction
    from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
    from dune_imperium.rules.agent_effects import OR_LOSE_DEPLOYED_TROOP_KEY
    from dune_imperium.rules.frames import FrameKind

    config = RulesetConfig(base_game=IMPERIUM, immortality=True, bloodlines=True)
    state = first_decision("turn", config=config)
    owner = make_profile(state).ctx.seat
    victim = (owner + 1) % 4
    ghola = "tleilaxu:ghola:0"
    context = {
        "covert_operation_card_id": ghola,
        "covert_operation_owner": owner,
        OR_LOSE_DEPLOYED_TROOP_KEY: True,
    }
    state = state.push_decision(
        DecisionFrame(
            kind=FrameKind.OPPONENT_CARD_DISCARD,
            frame_id="test:ghola:opponent",
            decision=PlayerDecision(owner=victim, prompt="test"),
            context=tuple(sorted(context.items())),  # type: ignore[arg-type]
        )
    )
    hand = state.players[victim].hand
    assert hand
    discards = tuple(
        DomainAction(
            action_id="discard_opponent_card", actor=victim, arguments=(("card_id", c),)
        )
        for c in hand
    )
    lose = DomainAction(
        action_id="lose_unit", actor=victim, arguments=(("zone", "conflict"),)
    )
    p = make_profile(state, victim)
    run = DecisionRun(p.ctx, p, (*discards, lose), p.rng, Memory())
    choice = TestOfHumanityDeferredAbility(
        card_entity(ghola, None)
    ).evaluate_resolution_choice(p)
    assert choice.response is not None
    action = uprising.opponent_card_discard(run)
    if choice.response[0][0] == 1:
        assert action == lose
    else:
        assert action in discards


@pytest.mark.parametrize(
    "effect",
    [
        "recall_spy_to_draw_intrigue_if_two_placed",
        "may_recall_two_spies_for_three_persuasion",
        "may_recall_spy_for_three_strength",
    ],
)
def test_a_spy_on_a_rise_of_ix_post_is_a_recall_target(effect: str) -> None:
    """Rise of Ix on the Uprising board counts one observation post on the
    overlay and one on the Ix board [Main p. 18] (docs/rules/rise-of-ix.md
    17): In High Places, Spy Network and Arrakis Observer's Reveal recalls
    see a Spy there too, in the game's post order."""

    from dune_imperium.agents.app_ai.testing import with_player
    from dune_imperium.agents.app_ai.windows import reveal
    from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory

    config = RulesetConfig(rise_of_ix=True, bloodlines=True)
    state = first_decision("turn", config=config)
    seat = make_profile(state).ctx.seat
    posts = (
        "choam-interstellar-shipping-smuggling",
        "landsraad-tech-negotiation-dreadnought",
        "emperor-sardaukar-dutiful-service",
    )
    state = with_player(state, seat, spy_post_ids=posts, spies_supply=0)
    p = make_profile(state, seat)
    run = DecisionRun(p.ctx, p, (), p.rng, Memory())
    build = (
        reveal._bloodlines_request
        if effect == "may_recall_spy_for_three_strength"
        else reveal._choice_request
    )
    request = build(run, effect, "test:card")
    refs = [entity.ref for entity in request.infos[0].entities]
    in_play = [post.post_id for post in content_for(config).observation_posts]
    assert refs == [post for post in in_play if post in posts]
    assert set(refs) == set(posts)
