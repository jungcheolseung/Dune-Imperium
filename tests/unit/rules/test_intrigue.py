"""Plot Intrigue play through the composable effect DSL."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.effect_dsl import IntrigueTiming
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    intrigue_card_for_instance,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_play,
    legal_intrigue_play_actions,
)


def _intrigue(card_id: str, copy: int = 0) -> str:
    return f"intrigue:{card_id}:{copy}"


def _starter(card_id: str, player: int = 0) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(player)
        if f":{card_id}:" in instance_id
    )


def _turn_state(
    owner: PlayerState,
    *,
    intrigue_deck: tuple[str, ...] = (),
    intrigue_discard: tuple[str, ...] = (),
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        intrigue_deck=intrigue_deck,
        intrigue_discard=intrigue_discard,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _play(state: GameState, card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def test_transcribed_intrigue_options_are_well_formed() -> None:
    transcribed = [entry for entry in INTRIGUE_CARDS if entry.play_data_complete]

    assert len(transcribed) == 26
    for entry in transcribed:
        assert entry.options
        for option in entry.options:
            assert option.timing in IntrigueTiming
            assert all(section.rewards for section in option.sections)
    assert intrigue_card_for_instance(_intrigue("contingency_plan", 2)).timings == {
        IntrigueTiming.PLOT,
        IntrigueTiming.COMBAT,
    }


def test_untranscribed_intrigue_cards_offer_no_play() -> None:
    owner = PlayerState(player_id=0, intrigue_cards=(_intrigue("manipulate"),))
    assert legal_intrigue_play_actions(_turn_state(owner), 0) == ()


def test_only_the_turn_owner_may_play_plot_intrigue() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    assert legal_intrigue_play_actions(state, 1) == ()
    with pytest.raises(IllegalActionError):
        UprisingRulesEngine().apply(state, replace(_play(state, card), actor=1))


def test_plot_intrigue_is_not_offered_outside_player_turns() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = replace(_turn_state(owner), phase=GamePhase.COMBAT)

    assert legal_intrigue_play_actions(state, 0) == ()


def test_contingency_plan_plot_option_gains_two_solari_and_is_discarded() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)

    # Only the Plot half is offered during Player Turns.
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)

    result = apply_intrigue_play(state, _play(state, card, 0))

    assert result.state.players[0].resources.solari == 2
    assert result.state.players[0].intrigue_cards == ()
    assert result.state.intrigue_discard == (card,)
    assert [event.kind for event in result.events] == ["intrigue_played"]
    assert result.events[0].visible_to is None
    # The turn frame is untouched: the owner still chooses an Agent or Reveal turn.
    assert result.state.decision_stack == state.decision_stack


def test_councilors_ambition_requires_a_high_council_seat() -> None:
    card = _intrigue("councilor_s_ambition")
    without_seat = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(without_seat), 0) == ()

    with_seat = replace(without_seat, high_council=True)
    state = _turn_state(with_seat)
    result = apply_intrigue_play(state, _play(state, card))

    assert result.state.players[0].resources.water == 3


def test_market_opportunity_offers_each_affordable_exchange() -> None:
    card = _intrigue("market_opportunity")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=2)
    )
    state = _turn_state(owner)

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)

    result = apply_intrigue_play(state, _play(state, card, 0))
    assert result.state.players[0].resources == Resources(solari=5, spice=0, water=1)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "intrigue_cost_paid",
    ]

    rich = _turn_state(replace(owner, resources=Resources(solari=5, spice=2)))
    assert legal_intrigue_play_actions(rich, 0) == (
        _play(rich, card, 0),
        _play(rich, card, 1),
    )
    swapped = apply_intrigue_play(rich, _play(rich, card, 1))
    assert swapped.state.players[0].resources == Resources(solari=0, spice=7, water=1)


def test_shaddams_favor_conditional_section_applies_independently() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    plain = apply_intrigue_play(_turn_state(owner), _play(_turn_state(owner), card))
    assert plain.state.players[0].troops_garrison == 4
    assert plain.state.players[0].resources.solari == 0

    loyal = replace(owner, influence=Influence(emperor=3))
    state = _turn_state(loyal)
    favored = apply_intrigue_play(state, _play(state, card))
    assert favored.state.players[0].troops_garrison == 4
    assert favored.state.players[0].resources.solari == 3


def test_strategic_stockpiling_makes_every_applicable_cost_mandatory() -> None:
    card = _intrigue("strategic_stockpiling")
    # Without Fremen 3 only the Spice line applies.
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=5)
    )
    state = _turn_state(owner)
    result = apply_intrigue_play(state, _play(state, card))
    assert result.state.players[0].victory_points == 2
    assert result.state.players[0].resources.spice == 0

    # With Fremen 3 the Water line also applies, so both costs are required.
    fremen = replace(owner, influence=Influence(fremen=3))
    assert legal_intrigue_play_actions(_turn_state(fremen), 0) == ()
    funded = _turn_state(replace(fremen, resources=Resources(spice=5, water=3)))
    both = apply_intrigue_play(funded, _play(funded, card))
    assert both.state.players[0].victory_points == 3
    assert both.state.players[0].resources == Resources(spice=0, water=0)


def test_depart_for_arrakis_recruits_and_draws_with_guild_influence() -> None:
    card = _intrigue("depart_for_arrakis")
    deck = (_starter("dagger"),)
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=2),
        influence=Influence(spacing_guild=3),
        deck=deck,
    )
    state = _turn_state(owner)

    result = apply_intrigue_play(state, _play(state, card))

    player = result.state.players[0]
    assert player.troops_garrison == 6
    assert player.troops_supply == 6
    assert player.resources.spice == 0
    assert player.hand == deck


def test_intelligence_report_draws_more_with_two_spies() -> None:
    card = _intrigue("intelligence_report")
    deck = (_starter("dagger"), _starter("diplomacy"))
    owner = PlayerState(player_id=0, intrigue_cards=(card,), deck=deck)
    one = apply_intrigue_play(_turn_state(owner), _play(_turn_state(owner), card))
    assert one.state.players[0].hand == deck[:1]

    spying = replace(
        owner,
        spies_supply=1,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-sietch-tabr",
        ),
    )
    state = _turn_state(spying)
    two = apply_intrigue_play(state, _play(state, card))
    assert two.state.players[0].hand == deck


def test_mercenaries_draws_intrigue_and_recruits_two() -> None:
    card = _intrigue("mercenaries")
    drawn = _intrigue("cunning")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner, intrigue_deck=(drawn,))

    result = apply_intrigue_play(state, _play(state, card))

    player = result.state.players[0]
    assert player.resources.solari == 0
    assert player.intrigue_cards == (drawn,)
    assert player.troops_garrison == 5
    assert result.state.intrigue_deck == ()
    assert result.state.intrigue_discard == (card,)


def test_intrigue_draw_reshuffles_the_discard_through_chance() -> None:
    card = _intrigue("mercenaries")
    discard = (_intrigue("cunning"), _intrigue("devour"), _intrigue("impress"))
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner, intrigue_discard=discard)
    engine = UprisingRulesEngine()

    pending = engine.apply(state, _play(state, card))

    decision = pending.next_decision
    assert isinstance(decision, ChanceDecision)
    # The card being resolved is not part of the pile that gets reshuffled.
    assert decision.options == discard
    assert pending.state.players[0].intrigue_cards == ()
    assert pending.state.intrigue_discard == (*discard, card)

    outcome = ChanceResolver(seed=3).resolve(decision)
    resolved = engine.apply(pending.state, outcome)

    assert resolved.state.intrigue_discard == (card,)
    assert resolved.state.players[0].intrigue_cards == (outcome.values[0],)
    assert resolved.state.intrigue_deck == outcome.values[1:]
    assert resolved.state.decision_stack[-1].kind == "turn"
    assert [event.kind for event in resolved.events] == [
        "intrigue_discard_shuffled",
        "intrigue_card_drawn",
    ]


def test_intrigue_draw_stops_short_when_no_cards_remain() -> None:
    card = _intrigue("mercenaries")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner)

    result = apply_intrigue_play(state, _play(state, card))

    assert result.state.players[0].intrigue_cards == ()
    assert result.state.intrigue_discard == (card,)
    assert result.state.decision_stack[-1].kind == "turn"


def test_troops_recruited_before_placing_the_agent_may_still_be_deployed() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        troops_supply=12,
        troops_garrison=0,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    recruited = engine.apply(state, _play(state, card)).state
    assert dict(recruited.decision_stack[-1].context)["troops_recruited"] == 1
    to_arrakeen = next(
        action
        for action in engine.legal_actions(recruited, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = engine.apply(recruited, to_arrakeen).state

    assert dict(placed.decision_stack[-1].context)["troops_recruited"] == 1
    deployments = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "deploy_troops"
    }
    assert deployments == {0, 1}


def test_intrigue_spice_trades_keep_harvest_accounting_honest() -> None:
    # Harvest Contracts count Spice gained from every source during the turn
    # [Main p. 16]: paid Spice must not hide a harvest, and gained Spice counts.
    card = _intrigue("market_opportunity")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        resources=Resources(solari=5, spice=2),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_arrakeen = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = engine.apply(state, to_arrakeen).state
    before = dict(placed.decision_stack[-1].context)
    assert before["spice_spent_after_placement"] == 0
    assert before["spice_at_placement"] == 2

    sold = engine.apply(placed, _play(placed, card, 0)).state
    context = dict(sold.decision_stack[-1].context)
    assert context["spice_spent_after_placement"] == 2

    bought = engine.apply(placed, _play(placed, card, 1)).state
    context = dict(bought.decision_stack[-1].context)
    assert context["spice_at_placement"] == 2
    assert context["spice_spent_after_placement"] == 0


def test_reveal_turn_withholds_plot_options_that_draw_personal_cards() -> None:
    report = _intrigue("intelligence_report")
    plan = _intrigue("contingency_plan")
    owner = PlayerState(
        player_id=0, intrigue_cards=(report, plan), deck=(_starter("dagger"),)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    assert _play(state, report) in engine.legal_actions(state, 0)
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    offered = [
        a for a in engine.legal_actions(revealed, 0) if a.action_id == "play_intrigue"
    ]
    assert offered == [_play(revealed, plan)]


def test_intrigue_card_stays_in_hand_while_its_choices_resolve() -> None:
    card = _intrigue("buy_access")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=5)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].intrigue_cards == (card,)
    assert opened.intrigue_discard == ()
    once = engine.apply(opened, _choose_faction("fremen")).state
    assert once.players[0].intrigue_cards == (card,)
    done = engine.apply(once, _choose_faction("emperor")).state
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (card,)


def test_placeholder_intrigue_ids_are_ignored_by_the_play_provider() -> None:
    owner = PlayerState(player_id=0, intrigue_cards=("intrigue:test",))
    assert legal_intrigue_play_actions(_turn_state(owner), 0) == ()


def test_troops_recruited_by_plot_during_an_agent_turn_may_be_deployed() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        troops_supply=12,
        troops_garrison=0,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_arrakeen = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, to_arrakeen).state

    # Plot Intrigue is offered inside the Agent-turn effect frame.
    assert _play(placed, card) in engine.legal_actions(placed, 0)
    played = engine.apply(placed, _play(placed, card)).state
    assert dict(played.decision_stack[-1].context)["troops_recruited"] == 1

    deployments = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(played, 0)
        if action.action_id == "deploy_troops"
    }
    assert deployments == {0, 1}


def test_plot_intrigue_is_offered_during_the_reveal_turn() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    revealed = engine.apply(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert _play(revealed, card) in engine.legal_actions(revealed, 0)

    played = engine.apply(revealed, _play(revealed, card)).state
    assert played.players[0].resources.solari == 2
    assert played.decision_stack == revealed.decision_stack


def test_every_intrigue_instance_has_a_definition() -> None:
    for instance_id in intrigue_deck_instance_ids(True):
        assert intrigue_card_for_instance(instance_id).card.card_id in instance_id
    with pytest.raises(ValueError):
        intrigue_card_for_instance("imperium:maula_pistol:0")


def _choose_faction(faction: str, recipient: int | None = None) -> DomainAction:
    arguments: tuple[tuple[str, str | int], ...] = (("faction", faction),)
    if recipient is not None:
        arguments = (("alliance_recipient", recipient), *arguments)
    return DomainAction(
        action_id="choose_intrigue_faction", actor=0, arguments=arguments
    )


def _choose_discard(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="choose_intrigue_discard", actor=0, arguments=(("card_id", card_id),)
    )


def test_buy_access_opens_two_distinct_faction_choices() -> None:
    card = _intrigue("buy_access")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=5)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card))
    assert opened.state.decision_stack[-1].kind == "intrigue_choice"
    assert opened.state.players[0].resources.solari == 0
    offered = {
        dict(a.arguments)["faction"] for a in engine.legal_actions(opened.state, 0)
    }
    assert offered == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    # Opponents have nothing to do while the choice is open.
    assert engine.legal_actions(opened.state, 1) == ()

    first = engine.apply(opened.state, _choose_faction("fremen"))
    assert first.state.players[0].influence.fremen == 1
    remaining = {
        dict(a.arguments)["faction"] for a in engine.legal_actions(first.state, 0)
    }
    assert "fremen" not in remaining and len(remaining) == 3

    second = engine.apply(first.state, _choose_faction("emperor"))
    assert second.state.players[0].influence.emperor == 1
    assert second.state.decision_stack == state.decision_stack
    assert second.state.intrigue_discard == (card,)
    assert second.state.players[0].intrigue_cards == ()


def test_imperium_politics_limits_the_choice_to_emperor_or_guild() -> None:
    card = _intrigue("imperium_politics")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=1)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (
        _choose_faction("emperor"),
        _choose_faction("spacing_guild"),
    )
    done = engine.apply(opened, _choose_faction("spacing_guild")).state
    assert done.players[0].influence.spacing_guild == 1
    assert done.decision_stack == state.decision_stack


def test_change_allegiances_loss_requires_influence_and_offers_both_options() -> None:
    card = _intrigue("change_allegiances")
    poor = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(poor), 0) == ()

    owner = replace(
        poor, influence=Influence(bene_gesserit=1), resources=Resources(spice=3)
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == (
        _play(state, card, 0),
        _play(state, card, 1),
    )
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card, 0)).state
    # Only Factions where the player still has Influence can be lost.
    assert engine.legal_actions(opened, 0) == (_choose_faction("bene_gesserit"),)
    lost = engine.apply(opened, _choose_faction("bene_gesserit")).state
    assert lost.players[0].influence.bene_gesserit == 0
    gained = engine.apply(lost, _choose_faction("fremen")).state
    assert gained.players[0].influence.fremen == 1
    assert gained.players[0].resources.spice == 3
    assert gained.decision_stack == state.decision_stack


def test_losing_influence_for_intrigue_offers_alliance_recipients() -> None:
    card = _intrigue("change_allegiances")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(fremen=4),
        alliance_faction_ids=("fremen",),
    )
    rivals = (
        PlayerState(player_id=1, influence=Influence(fremen=4)),
        PlayerState(player_id=2, influence=Influence(fremen=4)),
        PlayerState(player_id=3),
    )
    state = replace(_turn_state(owner), players=(owner, *rivals))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (
        _choose_faction("fremen", recipient=1),
        _choose_faction("fremen", recipient=2),
    )
    lost = engine.apply(opened, _choose_faction("fremen", recipient=2)).state
    assert lost.players[0].alliance_faction_ids == ()
    assert lost.players[2].alliance_faction_ids == ("fremen",)


def test_opportunism_loses_two_influence_and_pays_solari_for_a_point() -> None:
    card = _intrigue("opportunism")
    short = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(emperor=1),
        resources=Resources(solari=2),
    )
    assert legal_intrigue_play_actions(_turn_state(short), 0) == ()

    owner = replace(short, influence=Influence(emperor=2))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].resources.solari == 0
    once = engine.apply(opened, _choose_faction("emperor")).state
    assert once.players[0].influence.emperor == 1
    # Dropping below two Influence forfeits the Friendship Victory Point.
    assert once.players[0].victory_points == 0
    twice = engine.apply(once, _choose_faction("emperor")).state
    assert twice.players[0].influence.emperor == 0
    assert twice.players[0].victory_points == 1
    assert twice.decision_stack == state.decision_stack


def test_sietch_ritual_discards_a_hand_card_then_chooses_a_faction() -> None:
    card = _intrigue("sietch_ritual")
    favor = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":spacing_guild_s_favor:" in instance_id
    )
    empty_handed = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(empty_handed), 0) == ()

    owner = replace(empty_handed, hand=(_starter("dagger"), favor))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (
        _choose_discard(_starter("dagger")),
        _choose_discard(favor),
    )
    discarded = engine.apply(opened, _choose_discard(favor)).state
    assert discarded.players[0].discard_pile == (favor,)
    # The hand-discard trigger of Spacing Guild's Favor still fires.
    assert discarded.players[0].resources.spice == 2
    assert engine.legal_actions(discarded, 0) == (
        _choose_faction("bene_gesserit"),
        _choose_faction("fremen"),
    )
    done = engine.apply(discarded, _choose_faction("bene_gesserit")).state
    assert done.players[0].influence.bene_gesserit == 1
    assert done.intrigue_discard == (card,)


def test_backed_by_choam_plot_half_trades_influence_for_solari() -> None:
    card = _intrigue("backed_by_choam")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), influence=Influence(spacing_guild=2)
    )
    state = replace(_turn_state(owner), config=RulesetConfig(choam_module=True))
    engine = UprisingRulesEngine()

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
    opened = engine.apply(state, _play(state, card, 0)).state
    done = engine.apply(opened, _choose_faction("spacing_guild")).state
    assert done.players[0].influence.spacing_guild == 1
    assert done.players[0].resources.solari == 4


def test_owed_intrigue_draws_reshuffle_the_discard_before_the_next_decision() -> None:
    # Assembly Hall's board effect draws an Intrigue card. With the deck empty
    # the dispatcher shuffles the discard into a new deck [FAQ p. 2] and then
    # completes the draw before the owner's next decision.
    discard = (_intrigue("cunning"), _intrigue("devour"))
    owner = PlayerState(player_id=0, hand=(_starter("dagger"),))
    state = _turn_state(owner, intrigue_discard=discard)
    engine = UprisingRulesEngine()
    to_hall = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = engine.apply(state, to_hall).state

    pending = engine.apply(
        placed, DomainAction(action_id="resolve_board_effect", actor=0)
    )
    decision = pending.next_decision
    assert isinstance(decision, ChanceDecision)
    assert decision.options == discard
    assert pending.state.pending_intrigue_draws == ()

    outcome = ChanceResolver(seed=5).resolve(decision)
    resolved = engine.apply(pending.state, outcome)
    assert resolved.state.players[0].intrigue_cards == (outcome.values[0],)
    assert resolved.state.intrigue_discard == ()
    # The board effect was the last pending group, so the turn passed on.
    top = resolved.state.decision_stack[-1]
    assert top.kind == "turn" and isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == 1


def test_owed_intrigue_draw_stops_short_with_nothing_to_shuffle() -> None:
    owner = PlayerState(player_id=0, hand=(_starter("dagger"),))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_hall = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = engine.apply(state, to_hall).state

    done = engine.apply(placed, DomainAction(action_id="resolve_board_effect", actor=0))

    assert done.state.players[0].intrigue_cards == ()
    assert done.state.pending_intrigue_draws == ()
    assert done.state.decision_stack[-1].kind == "turn"


def _conflict(protected: bool) -> str:
    from dune_imperium.content.uprising.conflicts import CONFLICTS

    return next(
        conflict.card.card_id
        for conflict in CONFLICTS
        if conflict.shield_wall_protected is protected
    )


def _detonate() -> DomainAction:
    return DomainAction(action_id="detonate_shield_wall", actor=0)


def _keep_wall() -> DomainAction:
    return DomainAction(action_id="keep_shield_wall", actor=0)


def _deploy(count: int) -> DomainAction:
    return DomainAction(
        action_id="deploy_intrigue_troops", actor=0, arguments=(("count", count),)
    )


def test_detonation_may_remove_the_shield_wall_or_keep_it() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    # Option 0 is the detonation icon, option 1 the garrison deployment
    # (unavailable here: the garrison holds troops, so it is offered too).
    offered = legal_intrigue_play_actions(state, 0)
    assert _play(state, card, 0) in offered

    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_detonate(), _keep_wall())

    detonated = engine.apply(opened, _detonate())
    assert detonated.state.shield_wall_present is False
    assert "shield_wall_destroyed" in [e.kind for e in detonated.events]
    assert detonated.state.intrigue_discard == (card,)

    kept = engine.apply(opened, _keep_wall()).state
    assert kept.shield_wall_present is True
    assert kept.intrigue_discard == (card,)

    # Once the token is gone the detonation option has nothing to do.
    gone = replace(_turn_state(owner), shield_wall_present=False)
    assert legal_intrigue_play_actions(gone, 0) == (_play(gone, card, 1),)


def test_detonation_deploys_up_to_four_garrison_troops() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(player_id=0, intrigue_cards=(card,), troops_garrison=3)
    state = replace(
        _turn_state(replace(owner, troops_supply=9)),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    assert engine.legal_actions(opened, 0) == (_deploy(1), _deploy(2), _deploy(3))

    deployed = engine.apply(opened, _deploy(3)).state
    assert deployed.players[0].troops_garrison == 0
    assert deployed.players[0].troops_conflict == 3
    assert deployed.decision_stack[-1].kind == "turn"

    empty = PlayerState(
        player_id=0, intrigue_cards=(card,), troops_supply=12, troops_garrison=0
    )
    assert legal_intrigue_play_actions(_turn_state(empty), 0) == (
        _play(state, card, 0),
    )


def test_units_deployed_by_plot_during_reveal_count_toward_strength() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(_starter("dagger"),),
        troops_garrison=3,
        troops_supply=9,
    )
    state = replace(_turn_state(owner), current_conflict_ids=(_conflict(False),))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    # Dagger reveals for one sword, but with no units it does not count yet.
    assert revealed.players[0].combat_strength == 0

    opened = engine.apply(revealed, _play(revealed, card, 1)).state
    deployed = engine.apply(opened, _deploy(2)).state

    assert deployed.players[0].troops_conflict == 2
    # Two troops (4) plus the revealed sword (1).
    assert deployed.players[0].combat_strength == 5
    reveal_frame = next(f for f in deployed.decision_stack if f.kind == "reveal")
    assert dict(reveal_frame.context)["strength"] == 5


def test_unexpected_allies_detonates_then_summons_a_sandworm() -> None:
    card = _intrigue("unexpected_allies")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(water=2)
    )
    state = replace(_turn_state(owner), current_conflict_ids=(_conflict(True),))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].resources.water == 0
    assert engine.legal_actions(opened, 0) == (_detonate(), _keep_wall())

    summoned = engine.apply(opened, _detonate())
    assert summoned.state.shield_wall_present is False
    assert summoned.state.players[0].sandworms_conflict == 1
    assert [e.kind for e in summoned.events] == [
        "shield_wall_destroyed",
        "sandworm_deployed",
    ]

    # Keeping the wall leaves the protected Conflict untouched [Main p. 20].
    blocked = engine.apply(opened, _keep_wall())
    assert blocked.state.players[0].sandworms_conflict == 0
    assert blocked.state.players[0].resources.water == 0
    assert "sandworm_summon_unavailable" in [e.kind for e in blocked.events]


def test_unexpected_allies_without_a_wall_summons_directly() -> None:
    card = _intrigue("unexpected_allies")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(_starter("dagger"),),
        resources=Resources(water=2),
    )
    state = replace(
        _turn_state(owner),
        shield_wall_present=False,
        current_conflict_ids=(_conflict(True),),
    )
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state

    done = engine.apply(revealed, _play(revealed, card)).state

    assert done.players[0].sandworms_conflict == 1
    # Sandworm (3) plus the revealed sword (1), no choice frame was needed.
    assert done.players[0].combat_strength == 4
    assert done.decision_stack[-1].kind == "reveal"


def _trash(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="trash_intrigue_card", actor=0, arguments=(("card_id", card_id),)
    )


def _place_spy(post_id: str) -> DomainAction:
    return DomainAction(
        action_id="place_intrigue_spy", actor=0, arguments=(("post_id", post_id),)
    )


def _recall_spy(post_id: str) -> DomainAction:
    return DomainAction(
        action_id="recall_spy_for_intrigue", actor=0, arguments=(("post_id", post_id),)
    )


def test_cunning_offers_a_free_draw_or_a_paid_draw_with_optional_trash() -> None:
    card = _intrigue("cunning")
    dagger = _starter("dagger")
    deck = (_starter("diplomacy"),)
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(dagger,),
        discard_pile=(_starter("reconnaissance"),),
        deck=deck,
        resources=Resources(spice=1),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    free = engine.apply(state, _play(state, card, 0)).state
    assert free.players[0].hand == (dagger, *deck)
    assert free.players[0].resources.spice == 1

    opened = engine.apply(state, _play(state, card, 1)).state
    assert opened.players[0].resources.spice == 0
    offered = engine.legal_actions(opened, 0)
    assert offered[0].action_id == "decline_intrigue_trash"
    assert {dict(a.arguments)["card_id"] for a in offered[1:]} == {
        dagger,
        _starter("reconnaissance"),
    }

    trashed = engine.apply(opened, _trash(dagger)).state
    assert trashed.players[0].trashed == (dagger,)
    assert trashed.players[0].hand == deck
    assert trashed.intrigue_discard == (card,)

    declined = engine.apply(
        opened, DomainAction(action_id="decline_intrigue_trash", actor=0)
    ).state
    assert declined.players[0].trashed == ()
    assert declined.players[0].hand == (dagger, *deck)


def test_special_mission_places_a_spy_on_a_bene_gesserit_post() -> None:
    card = _intrigue("special_mission")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    targets = {
        str(dict(a.arguments)["post_id"]) for a in engine.legal_actions(opened, 0)
    }
    assert targets and all("bene-gesserit" in post for post in targets)
    post = sorted(targets)[0]
    placed = engine.apply(opened, _place_spy(post)).state
    assert placed.players[0].spy_post_ids == (post,)
    assert placed.players[0].spies_supply == 2
    assert placed.intrigue_discard == (card,)


def test_special_mission_recalls_first_when_no_spy_is_in_supply() -> None:
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
        ),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    assert {a.action_id for a in engine.legal_actions(opened, 0)} == {
        "recall_spy_for_intrigue"
    }
    recalled = engine.apply(
        opened, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert recalled.players[0].spies_supply == 1
    # The slot is still open: now the placement itself is offered.
    assert {a.action_id for a in engine.legal_actions(recalled, 0)} == {
        "place_intrigue_spy"
    }


def test_special_mission_recall_option_pays_out_after_the_detonation_choice() -> None:
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    assert _play(state, card, 1) in legal_intrigue_play_actions(state, 0)
    opened = engine.apply(state, _play(state, card, 1)).state
    assert engine.legal_actions(opened, 0) == (
        _recall_spy("landsraad-assembly-hall-gather-support"),
    )
    recalled = engine.apply(
        opened, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert recalled.players[0].spies_supply == 3
    assert engine.legal_actions(recalled, 0) == (_detonate(), _keep_wall())
    done = engine.apply(recalled, _keep_wall()).state
    assert done.players[0].resources.spice == 2
    assert done.shield_wall_present is True

    # Without a placed Spy the recall option cannot be played at all.
    grounded = _turn_state(PlayerState(player_id=0, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(grounded, 0) == (_play(grounded, card, 0),)


def _combat_state(*players: PlayerState) -> GameState:
    from dune_imperium.rules.combat import begin_combat_intrigue

    seats = list(players)
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(_conflict(False),),
        players=tuple(seats),
    )
    return begin_combat_intrigue(state).state


def _pass(actor: int) -> DomainAction:
    return DomainAction(action_id="pass_combat_intrigue", actor=actor)


def test_combat_intrigue_is_offered_only_to_the_participant_with_priority() -> None:
    card = _intrigue("weirding_combat")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        troops_supply=10,
        troops_garrison=1,
        troops_conflict=1,
        combat_strength=2,
    )
    rival = PlayerState(
        player_id=1,
        intrigue_cards=(_intrigue("weirding_combat", 0),),
        troops_supply=10,
        troops_garrison=1,
        troops_conflict=1,
        combat_strength=2,
    )
    bystander = PlayerState(player_id=2, intrigue_cards=())
    state = _combat_state(fighter, replace(rival, intrigue_cards=()), bystander)
    engine = UprisingRulesEngine()

    assert state.decision_stack[-1].kind == "combat_intrigue"
    assert engine.legal_actions(state, 0) == (_pass(0), _play(state, card))
    assert engine.legal_actions(state, 1) == ()

    played = engine.apply(state, _play(state, card))
    assert played.state.players[0].combat_strength == 5
    assert "combat_strength_gained" in [e.kind for e in played.events]
    # After playing, priority stays with the same player [Main p. 14].
    assert engine.legal_actions(played.state, 0) == (_pass(0),)


def test_weirding_combat_adds_two_more_with_three_bene_gesserit() -> None:
    card = _intrigue("weirding_combat")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(bene_gesserit=3),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    played = engine.apply(state, _play(state, card)).state
    assert played.players[0].combat_strength == 7


def test_playing_combat_intrigue_restarts_the_consecutive_pass_count() -> None:
    card = _intrigue("weirding_combat")
    first = PlayerState(
        player_id=0, troops_supply=11, troops_garrison=0, troops_conflict=1,
        combat_strength=2,
    )
    second = PlayerState(
        player_id=1,
        intrigue_cards=(card,),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(first, second)
    engine = UprisingRulesEngine()

    passed = engine.apply(state, _pass(0)).state
    assert dict(passed.decision_stack[-1].context)["consecutive_passes"] == 1
    play_as_second = DomainAction(
        action_id="play_intrigue", actor=1, arguments=(("card_id", card), ("option", 0))
    )
    played = engine.apply(passed, play_as_second).state
    assert dict(played.decision_stack[-1].context)["consecutive_passes"] == 0
    # Both players must pass again in a row before Combat resolves.
    once = engine.apply(played, _pass(1)).state
    assert once.decision_stack[-1].kind == "combat_intrigue"
    twice = engine.apply(once, _pass(0)).state
    assert twice.combat_intrigue_complete is True


def test_questionable_methods_requires_losing_influence_for_the_bonus() -> None:
    card = _intrigue("questionable_methods")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(fremen=1),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert engine.legal_actions(opened, 0) == (_choose_faction("fremen"),)
    done = engine.apply(opened, _choose_faction("fremen")).state
    assert done.players[0].influence.fremen == 0
    assert done.players[0].combat_strength == 7
    assert done.decision_stack[-1].kind == "combat_intrigue"

    # Under OQ-015(b) the Influence line is mandatory, so a player without
    # any Influence cannot play the card at all.
    broke = _combat_state(replace(fighter, influence=Influence()))
    assert legal_intrigue_play_actions(broke, 0) == ()


def test_find_weakness_recalls_a_spy_for_the_bonus() -> None:
    card = _intrigue("find_weakness")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (
        _recall_spy("landsraad-assembly-hall-gather-support"),
    )
    done = engine.apply(
        opened, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert done.players[0].spies_supply == 3
    assert done.players[0].combat_strength == 7


def test_combat_intrigue_is_not_offered_during_player_turns() -> None:
    card = _intrigue("weirding_combat")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(owner), 0) == ()


def _retreat(count: int, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="retreat_intrigue_troops", actor=actor, arguments=(("count", count),)
    )


def _fighter(player_id: int, troops: int, **extra: object) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        troops_supply=12 - troops,
        troops_garrison=0,
        troops_conflict=troops,
        combat_strength=2 * troops,
        **extra,  # type: ignore[arg-type]
    )


def test_go_to_ground_retreats_then_places_a_spy_and_drops_an_empty_player() -> None:
    card = _intrigue("go_to_ground")
    state = _combat_state(_fighter(0, 1, intrigue_cards=(card,)), _fighter(1, 2))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    # Only one troop is in the Conflict, so only a one-troop retreat is offered.
    assert engine.legal_actions(opened, 0) == (_retreat(1),)
    retreated = engine.apply(opened, _retreat(1)).state
    assert retreated.players[0].troops_conflict == 0
    assert retreated.players[0].combat_strength == 0
    # The Spy placement still resolves before the card finishes.
    assert {a.action_id for a in engine.legal_actions(retreated, 0)} == {
        "place_intrigue_spy"
    }
    post = str(dict(engine.legal_actions(retreated, 0)[0].arguments)["post_id"])
    done = engine.apply(retreated, _place_spy(post)).state

    assert done.players[0].spy_post_ids == (post,)
    # OQ-003 convention: with no units left, player 0 leaves the loop at once
    # and priority moves to the next remaining participant.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 1
    assert dict(frame.context)["participants_mask"] == 0b10
    assert engine.legal_actions(done, 0) == ()


def test_tactical_option_retreating_the_last_units_ends_combat_intrigue() -> None:
    card = _intrigue("tactical_option")
    state = _combat_state(_fighter(0, 2, intrigue_cards=(card,)))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    assert engine.legal_actions(opened, 0) == (_retreat(1), _retreat(2))
    # Resolve the slot without the dispatcher so the round does not run on.
    done = apply_intrigue_choice(opened, _retreat(2))

    assert done.state.players[0].troops_garrison == 2
    assert done.state.players[0].combat_strength == 0
    assert done.state.combat_intrigue_complete is True
    assert done.state.decision_stack == ()


def test_tactical_option_partial_retreat_keeps_the_player_in_the_loop() -> None:
    card = _intrigue("tactical_option")
    state = _combat_state(_fighter(0, 3, intrigue_cards=(card,)), _fighter(1, 1))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    done = engine.apply(opened, _retreat(1)).state

    assert done.players[0].troops_conflict == 2
    assert done.players[0].combat_strength == 4
    frame = done.decision_stack[-1]
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 0
    assert dict(frame.context)["consecutive_passes"] == 0


def test_spice_is_power_offers_both_halves_when_affordable() -> None:
    card = _intrigue("spice_is_power")
    rich = _fighter(0, 3, intrigue_cards=(card,), resources=Resources(spice=3))
    state = _combat_state(rich, _fighter(1, 1))
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (
        _play(state, card, 0),
        _play(state, card, 1),
    )

    swords = engine.apply(state, _play(state, card, 1)).state
    assert swords.players[0].resources.spice == 0
    assert swords.players[0].combat_strength == 12

    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_retreat(3),)
    paid = engine.apply(opened, _retreat(3)).state
    assert paid.players[0].resources.spice == 6
    assert paid.players[0].troops_conflict == 0
    assert dict(paid.decision_stack[-1].context)["participants_mask"] == 0b10

    poor = _combat_state(_fighter(0, 2, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(poor, 0) == ()


def test_devour_adds_more_and_offers_a_trash_with_a_sandworm() -> None:
    card = _intrigue("devour")
    plain = _combat_state(_fighter(0, 1, intrigue_cards=(card,)))
    engine = UprisingRulesEngine()
    done = engine.apply(plain, _play(plain, card)).state
    assert done.players[0].combat_strength == 4
    assert done.decision_stack[-1].kind == "combat_intrigue"

    worm = _fighter(0, 1, intrigue_cards=(card,), hand=(_starter("dagger"),))
    worm = replace(worm, sandworms_conflict=1, combat_strength=5)
    state = _combat_state(worm)
    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert engine.legal_actions(opened, 0)[0].action_id == "decline_intrigue_trash"
    trashed = engine.apply(opened, _trash(_starter("dagger"))).state
    assert trashed.players[0].trashed == (_starter("dagger"),)
    assert trashed.players[0].combat_strength == 9


def test_reach_agreement_retreats_for_a_contract_in_the_choam_module() -> None:
    card = _intrigue("reach_agreement")
    fighter = _fighter(0, 2, intrigue_cards=(card,))
    state = replace(
        _combat_state(fighter, _fighter(1, 1)),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate", "contract:heighliner_iii"),
        contract_bank=(),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (_retreat(1), _retreat(2))
    market = engine.apply(opened, _retreat(1)).state
    assert market.decision_stack[-1].kind == "contract_market"
    assert {a.action_id for a in engine.legal_actions(market, 0)} == {"take_contract"}

    # Without the CHOAM Module the Contract icon has no market to use.
    assert legal_intrigue_play_actions(_combat_state(fighter), 0) == ()

