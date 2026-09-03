"""Tests for the basic Reveal-turn transition."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    STARTING_DECK,
    starting_deck_instance_ids,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.card_draw import (
    apply_personal_draw_reshuffle,
    draw_or_request_personal_cards,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    apply_contract_reveal_choice,
    apply_corrinth_city_reveal,
    apply_reveal_card_trash,
    apply_reveal_influence_exchange,
    apply_reveal_sandworm_action,
    apply_reveal_spice_influence,
    apply_reveal_spy_action,
    apply_reveal_troop_retreat,
    begin_reveal_turn,
    finish_reveal_turn,
    legal_contract_reveal_choice_actions,
    legal_corrinth_city_reveal_actions,
    legal_defer_reveal_choice_actions,
    legal_finish_reveal_actions,
    legal_reveal_actions,
    legal_reveal_card_trash_actions,
    legal_reveal_influence_exchange_actions,
    legal_reveal_sandworm_actions,
    legal_reveal_spice_influence_actions,
    legal_reveal_spy_actions,
    legal_reveal_troop_retreat_actions,
    reveal_late_arrivals,
)


def test_corrinth_city_can_take_high_council_during_current_reveal() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city,),
        resources=Resources(solari=5),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_corrinth_city_reveal_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
        "take_high_council_from_reveal",
    )
    take_seat = actions[1]
    result = apply_corrinth_city_reveal(revealed, take_seat)
    resolved = result.state.players[0]

    assert resolved.high_council is True
    assert resolved.resources.solari == 0
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "high_council_acquired"


def test_corrinth_city_gains_five_solari_when_seat_is_unavailable() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    owner = PlayerState(
        player_id=0,
        hand=(corrinth_city,),
        resources=Resources(solari=2),
        high_council=True,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_corrinth_city_reveal_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
    )
    result = apply_corrinth_city_reveal(revealed, actions[0])

    assert result.state.players[0].resources.solari == 7
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "reveal_solari_gained"


def test_desert_power_can_keep_persuasion_or_pay_water_for_a_sandworm() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(
        _state(owner),
        current_conflict_ids=("propaganda",),
        shield_wall_present=True,
    )
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    actions = legal_reveal_sandworm_actions(revealed.state, 0)
    assert tuple(action.action_id for action in actions) == (
        "decline_reveal_sandworm",
        "pay_reveal_water_for_sandworm",
    )

    declined = apply_reveal_sandworm_action(revealed.state, actions[0])
    assert dict(declined.state.decision_stack[-1].context)["persuasion"] == 2
    assert declined.state.players[0].sandworms_conflict == 0

    deployed = apply_reveal_sandworm_action(revealed.state, actions[1])
    context = dict(deployed.state.decision_stack[-1].context)
    owner_after = deployed.state.players[0]
    assert owner_after.resources.water == 0
    assert owner_after.maker_hooks is True
    assert owner_after.sandworms_conflict == 1
    assert owner_after.combat_strength == 3
    assert context["persuasion"] == 0
    assert context["strength"] == 3
    assert tuple(event.kind for event in deployed.events) == (
        "reveal_sandworm_deployed",
        "reveal_strength_gained",
    )


def test_desert_power_recalculates_sword_strength_when_sandworm_is_first_unit() -> None:
    desert_power = _imperium_instance("desert_power")
    maula_pistol = _imperium_instance("maula_pistol")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power, maula_pistol),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    assert dict(revealed.state.decision_stack[-2].context)["strength"] == 0
    action = legal_reveal_sandworm_actions(revealed.state, 0)[1]
    deployed = apply_reveal_sandworm_action(revealed.state, action)

    assert deployed.state.players[0].combat_strength == 4
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 4


def test_desert_power_adds_three_strength_to_existing_conflict_units() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
        troops_supply=8,
        troops_conflict=1,
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    deployed = apply_reveal_sandworm_action(
        revealed.state,
        legal_reveal_sandworm_actions(revealed.state, 0)[1],
    )

    assert deployed.state.players[0].combat_strength == 5
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 5


def test_desert_power_reveal_sandworm_is_blocked_by_shield_wall() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(
        _state(owner),
        current_conflict_ids=("siege_of_arrakeen",),
        shield_wall_present=True,
    )
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))

    assert legal_reveal_sandworm_actions(revealed.state, 0) == ()
    assert dict(revealed.state.decision_stack[-1].context)["persuasion"] == 2


def test_desert_power_reveal_sandworm_requires_water_and_maker_hooks() -> None:
    desert_power = _imperium_instance("desert_power")
    for owner in (
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=False,
            resources=Resources(water=1),
        ),
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=True,
            resources=Resources(water=0),
        ),
    ):
        state = replace(_state(owner), current_conflict_ids=("propaganda",))
        revealed = begin_reveal_turn(
            state,
            DomainAction(action_id="reveal_turn", actor=0),
        )

        assert legal_reveal_sandworm_actions(revealed.state, 0) == ()


def test_engine_dispatches_desert_power_reveal_sandworm_choice() -> None:
    desert_power = _imperium_instance("desert_power")
    owner = PlayerState(
        player_id=0,
        hand=(desert_power,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    engine = UprisingRulesEngine()
    revealed = begin_reveal_turn(state, DomainAction(action_id="reveal_turn", actor=0))
    action = next(
        candidate
        for candidate in engine.legal_actions(revealed.state, 0)
        if candidate.action_id == "pay_reveal_water_for_sandworm"
    )

    transition = engine.apply(revealed.state, action)

    assert transition.state.players[0].sandworms_conflict == 1
    assert transition.state.players[0].resources.water == 0


def test_calculus_of_power_trashes_another_emperor_for_strength() -> None:
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
        hand=(calculus, sardaukar),
    )
    state = replace(_state(owner), intrigue_deck=("intrigue:test",))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_card_trash_actions(revealed, 0)

    assert {action.action_id for action in actions} == {
        "decline_reveal_card_trash",
        "trash_reveal_card",
    }
    trash = next(
        action for action in actions if action.action_id == "trash_reveal_card"
    )
    assert dict(trash.arguments)["card_id"] == sardaukar

    result = apply_reveal_card_trash(revealed, trash)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].in_play == (calculus,)
    assert result.state.players[0].trashed == (sardaukar,)
    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.players[0].combat_strength == 6
    assert context["strength"] == 6
    assert context["optional_sword_strength"] == 3
    assert [event.kind for event in result.events] == [
        "card_trashed",
        "intrigue_card_drawn",
        "reveal_strength_gained",
    ]


def test_calculus_of_power_cannot_pay_with_itself() -> None:
    calculus = _imperium_instance("calculus_of_power")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(calculus,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    assert legal_reveal_card_trash_actions(revealed, 0) == ()
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2


def test_desert_power_recounts_calculus_sword_when_it_adds_the_first_unit() -> None:
    desert_power = _imperium_instance("desert_power")
    calculus = _imperium_instance("calculus_of_power")
    sardaukar = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(calculus, desert_power),
        in_play=(sardaukar,),
        maker_hooks=True,
        resources=Resources(water=1),
    )
    state = replace(_state(owner), current_conflict_ids=("propaganda",))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    calculus_trash = next(
        action
        for action in legal_reveal_card_trash_actions(revealed, 0)
        if action.action_id == "trash_reveal_card"
    )
    after_calculus = apply_reveal_card_trash(revealed, calculus_trash).state
    context = dict(after_calculus.decision_stack[-2].context)

    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 3
    desert_action = legal_reveal_sandworm_actions(after_calculus, 0)[1]
    deployed = apply_reveal_sandworm_action(after_calculus, desert_action)

    assert deployed.state.players[0].combat_strength == 6
    assert dict(deployed.state.decision_stack[-1].context)["strength"] == 6


def test_captured_mentat_may_exchange_influence_on_reveal() -> None:
    mentat = _imperium_instance("captured_mentat")
    owner = PlayerState(
        player_id=0,
        hand=(mentat,),
        influence=Influence(emperor=1),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_influence_exchange_actions(revealed, 0)

    assert len(actions) == 5
    assert any(
        dict(action.arguments)
        == {"gained_faction": "emperor", "lost_faction": "emperor"}
        for action in actions
    )
    exchange = next(
        action
        for action in actions
        if dict(action.arguments)
        == {"gained_faction": "fremen", "lost_faction": "emperor"}
    )
    result = apply_reveal_influence_exchange(revealed, exchange)

    assert result.state.players[0].influence.emperor == 0
    assert result.state.players[0].influence.fremen == 1
    assert [event.kind for event in result.events] == [
        "influence_lost",
        "influence_gained",
    ]


def test_captured_mentat_skips_influence_choice_with_no_payable_cost() -> None:
    mentat = _imperium_instance("captured_mentat")

    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(mentat,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    assert legal_reveal_influence_exchange_actions(revealed, 0) == ()
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 1


def test_captured_mentat_selects_between_tied_alliance_recipients() -> None:
    mentat = _imperium_instance("captured_mentat")
    owner = PlayerState(
        player_id=0,
        hand=(mentat,),
        influence=Influence(emperor=4),
        alliance_faction_ids=(Faction.EMPEROR.value,),
        victory_points=2,
    )
    state = _state(owner)
    players = list(state.players)
    players[1] = replace(players[1], influence=Influence(emperor=4))
    players[2] = replace(players[2], influence=Influence(emperor=4))
    state = replace(state, players=tuple(players))
    revealed = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    exchange = next(
        action
        for action in legal_reveal_influence_exchange_actions(revealed, 0)
        if dict(action.arguments)
        == {
            "alliance_recipient": 2,
            "gained_faction": "fremen",
            "lost_faction": "emperor",
        }
    )

    result = apply_reveal_influence_exchange(revealed, exchange).state

    assert result.players[0].alliance_faction_ids == ()
    assert result.players[2].alliance_faction_ids == (Faction.EMPEROR.value,)
    assert result.players[0].influence.fremen == 1


def test_spacing_guilds_favor_may_pay_three_spice_for_influence() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(favor,),
        resources=Resources(spice=3),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    actions = legal_reveal_spice_influence_actions(revealed, 0)

    assert len(actions) == 5
    payment = next(
        action
        for action in actions
        if dict(action.arguments).get("faction") == Faction.FREMEN.value
    )
    result = apply_reveal_spice_influence(revealed, payment)

    assert result.state.players[0].resources.spice == 0
    assert result.state.players[0].influence.fremen == 1
    assert [event.kind for event in result.events] == [
        "reveal_spice_paid",
        "influence_gained",
    ]


def test_spacing_guilds_favor_cleanup_does_not_trigger_discard_effect() -> None:
    favor = _imperium_instance("spacing_guild_s_favor")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(favor,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    result = finish_reveal_turn(
        revealed,
        DomainAction(action_id="finish_reveal", actor=0),
    ).state

    assert result.players[0].discard_pile == (favor,)
    assert result.players[0].resources.spice == 0


def test_two_spacing_guild_favors_cannot_spend_same_spice_twice() -> None:
    favors = tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":spacing_guild_s_favor:" in instance_id
    )
    owner = PlayerState(
        player_id=0,
        hand=favors,
        resources=Resources(spice=3),
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    payment = next(
        action
        for action in legal_reveal_spice_influence_actions(revealed, 0)
        if dict(action.arguments).get("faction") == Faction.EMPEROR.value
    )

    paid = apply_reveal_spice_influence(revealed, payment).state

    assert legal_reveal_spice_influence_actions(paid, 0) == (
        DomainAction(action_id="decline_reveal_spice_influence", actor=0),
    )


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _imperium_instance(
    card_id: str,
    copy: int = 0,
    *,
    choam_module: bool = False,
) -> str:
    return tuple(
        instance_id
        for instance_id in imperium_deck_instance_ids(choam_module)
        if f":{card_id}:" in instance_id
    )[copy]


def _state(player: PlayerState, *, choam_module: bool = False) -> GameState:
    return GameState(
        config=RulesetConfig(choam_module=choam_module),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_reveal_is_available_even_with_agents_remaining() -> None:
    state = _state(PlayerState(player_id=0))

    assert legal_reveal_actions(state, 0) == (
        DomainAction(action_id="reveal_turn", actor=0),
    )
    assert legal_reveal_actions(state, 1) == ()


def test_treacherous_maneuver_reveal_draws_intrigue() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")
    owner = PlayerState(player_id=0, hand=(maneuver,))
    state = replace(_state(owner), intrigue_deck=("intrigue:test",))

    result = begin_reveal_turn(
        state,
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert result.state.players[0].intrigue_cards == ("intrigue:test",)
    assert result.state.intrigue_deck == ()
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert [event.kind for event in result.events] == [
        "reveal_started",
        "intrigue_card_drawn",
    ]


def test_treacherous_maneuver_reveal_tolerates_an_empty_intrigue_deck() -> None:
    maneuver = _imperium_instance("treacherous_maneuver")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(maneuver,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert result.state.players[0].intrigue_cards == ()
    # With the deck empty the draw is owed to the dispatcher, which reshuffles
    # the discard [FAQ p. 2] or stops short when there is nothing to shuffle.
    assert [event.kind for event in result.events] == ["reveal_started"]
    (owed,) = result.state.pending_intrigue_draws
    assert owed[:2] == (0, 1)
    assert owed[2].endswith("treacherous_maneuver:0:intrigue_draw")


def test_chani_retreats_two_troops_for_four_strength() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
        sandworms_conflict=1,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state

    actions = legal_reveal_troop_retreat_actions(revealed, 0)
    assert {action.action_id for action in actions} == {
        "decline_reveal_troop_retreat",
        "retreat_two_troops_for_reveal",
    }
    retreat = next(
        action
        for action in actions
        if action.action_id == "retreat_two_troops_for_reveal"
    )
    result = apply_reveal_troop_retreat(revealed, retreat)
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].sandworms_conflict == 1
    assert result.state.players[0].troops_garrison == 4
    assert result.state.players[0].combat_strength == 7
    assert context["strength"] == 7
    assert context["optional_sword_strength"] == 4
    assert [event.kind for event in result.events] == [
        "troops_retreated",
        "reveal_strength_gained",
    ]


def test_chani_retreat_clears_strength_when_no_unit_remains() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    owner = PlayerState(
        player_id=0,
        hand=(chani,),
        troops_supply=8,
        troops_garrison=2,
        troops_conflict=2,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    retreat = next(
        action
        for action in legal_reveal_troop_retreat_actions(revealed, 0)
        if action.action_id == "retreat_two_troops_for_reveal"
    )

    result = apply_reveal_troop_retreat(revealed, retreat)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].combat_strength == 0
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 4


def test_chani_fremen_bond_adds_two_persuasion() -> None:
    chani = _imperium_instance("chani_clever_tactician")
    fremen = _imperium_instance("desert_survival")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(chani, fremen))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_steersman_reveal_gains_persuasion_and_spice() -> None:
    steersman = _imperium_instance("steersman")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(steersman,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].resources.spice == 2


def test_junction_headquarters_reveal_gains_water_and_recruits() -> None:
    junction = _imperium_instance("junction_headquarters")

    result = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(junction,))),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    owner = result.state.players[0]
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert owner.resources.water == 2
    assert owner.troops_supply == 8
    assert owner.troops_garrison == 4


def test_reveal_moves_hand_to_in_play_and_totals_persuasion() -> None:
    argument = _instance("convincing_argument")
    diplomacy = _instance("diplomacy")
    state = _state(PlayerState(player_id=0, hand=(argument, diplomacy)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.hand == ()
    assert owner.in_play == (argument, diplomacy)
    assert context["persuasion"] == 3
    assert context["revealed_card_count"] == 2
    assert context["revealed_card_000"] == argument
    assert context["revealed_card_001"] == diplomacy


def test_bene_gesserit_operative_gains_persuasion_with_two_placed_spies() -> None:
    operative = _imperium_instance("bene_gesserit_operative")
    without_spies = _state(PlayerState(player_id=0, hand=(operative,)))
    with_spies = _state(
        PlayerState(
            player_id=0,
            hand=(operative,),
            spies_supply=1,
            spy_post_ids=(
                "emperor-sardaukar-dutiful-service",
                "bene-gesserit-espionage-secrets",
            ),
        )
    )

    base = begin_reveal_turn(
        without_spies,
        legal_reveal_actions(without_spies, 0)[0],
    )
    bonus = begin_reveal_turn(
        with_spies,
        legal_reveal_actions(with_spies, 0)[0],
    )

    assert dict(base.state.decision_stack[-1].context)["persuasion"] == 1
    assert dict(bonus.state.decision_stack[-1].context)["persuasion"] == 3


def test_reliable_informant_reveals_for_persuasion_and_solari() -> None:
    informant = _imperium_instance("reliable_informant")
    state = _state(PlayerState(player_id=0, hand=(informant,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.solari == 1


def test_strike_fleet_reveals_for_persuasion_and_strength() -> None:
    strike_fleet = _imperium_instance("strike_fleet")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(strike_fleet,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 5


def test_imperial_spymaster_reveals_for_persuasion_and_strength() -> None:
    spymaster = _imperium_instance("imperial_spymaster")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spymaster,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 3


def test_spy_network_recalls_one_of_two_spies_and_draws_intrigue() -> None:
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spy_network,),
            troops_supply=8,
            troops_conflict=1,
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    choices = tuple(
        action
        for action in engine.legal_actions(revealed.state, 0)
        if action.action_id != "defer_reveal_choice"
    )
    selected = next(
        action
        for action in choices
        if dict(action.arguments)["post_id"] == posts[1]
    )
    result = engine.apply(revealed.state, selected)

    assert tuple(action.action_id for action in choices) == (
        "recall_spy_for_reveal",
        "recall_spy_for_reveal",
    )
    assert {dict(action.arguments)["post_id"] for action in choices} == set(posts)
    assert result.state.players[0].spy_post_ids == (posts[0],)
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].intrigue_cards == ("intrigue:test:0",)
    assert result.state.intrigue_deck == ()
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].combat_strength == 3
    assert tuple(event.kind for event in result.events) == (
        "spy_recalled",
        "intrigue_card_drawn",
    )


def test_spy_network_recall_becomes_unavailable_when_spies_drop_mid_reveal() -> None:
    # The two-Spy condition is judged again when the queued choice resolves
    # in the owner's chosen Reveal order [Main p. 12] [Main pp. 9, 20]; In
    # High Places can recall both remaining Spies first, and the required
    # recall and Intrigue draw are then unavailable.
    in_high_places = _imperium_instance("in_high_places")
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, spy_network),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    pair = next(
        action
        for action in engine.legal_actions(revealed.state, 0)
        if action.action_id == "recall_spies_for_reveal"
    )
    drained = engine.apply(revealed.state, pair).state
    assert drained.players[0].spy_post_ids == ()

    choices = engine.legal_actions(drained, 0)
    assert [action.action_id for action in choices] == [
        "defer_reveal_choice",
        "decline_reveal_spy_recall",
    ]
    resolved = engine.apply(drained, choices[0]).state
    assert resolved.players[0].intrigue_cards == ()
    assert resolved.intrigue_deck == ("intrigue:test:0",)
    assert resolved.players[0].spies_supply == 3
    assert resolved.decision_stack[-1].kind == "reveal"


def test_spy_network_has_no_recall_effect_with_only_one_spy() -> None:
    spy_network = _imperium_instance("spy_network")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spy_network,),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert legal_reveal_spy_actions(result.state, 0) == ()
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_in_high_places_may_recall_two_spies_for_two_persuasion() -> None:
    in_high_places = _imperium_instance("in_high_places")
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places,),
            spies_supply=0,
            spy_post_ids=posts,
        )
    )

    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    choices = legal_reveal_spy_actions(revealed.state, 0)
    recall = next(
        action for action in choices if action.action_id == "recall_spies_for_reveal"
    )
    result = apply_reveal_spy_action(revealed.state, recall)

    assert len(choices) == 4
    assert result.state.players[0].spies_supply == 2
    assert len(result.state.players[0].spy_post_ids) == 1
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 4
    assert tuple(event.kind for event in result.events) == (
        "spy_recalled",
        "spy_recalled",
        "reveal_persuasion_gained",
    )


def test_in_high_places_reveal_spy_recall_may_be_declined() -> None:
    in_high_places = _imperium_instance("in_high_places")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places,),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    decline = next(
        action
        for action in legal_reveal_spy_actions(revealed.state, 0)
        if action.action_id == "decline_reveal_spy_recall"
    )

    result = apply_reveal_spy_action(revealed.state, decline)

    assert result.state.players[0].spy_post_ids == posts
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.events[0].kind == "reveal_spy_recall_declined"


def test_rebel_supplier_reveals_for_spice_and_strength() -> None:
    supplier = _imperium_instance("rebel_supplier")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(supplier,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0
    assert result.state.players[0].resources.spice == 1
    assert result.state.players[0].combat_strength == 3


def test_dangerous_rhetoric_reveals_for_persuasion_and_strength() -> None:
    rhetoric = _imperium_instance("dangerous_rhetoric")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(rhetoric,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].combat_strength == 3


def test_public_spectacle_reveal_places_a_spy() -> None:
    spectacle = _imperium_instance("public_spectacle")
    state = _state(PlayerState(player_id=0, hand=(spectacle,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    engine = UprisingRulesEngine()
    choices = engine.legal_actions(revealed.state, 0)
    selected = next(
        action
        for action in choices
        if dict(action.arguments).get("post_id")
        == "emperor-sardaukar-dutiful-service"
    )

    result = engine.apply(revealed.state, selected)

    assert {action.action_id for action in choices} == {
        "defer_reveal_choice",
        "place_reveal_spy",
    }
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        "emperor-sardaukar-dutiful-service",
    )
    assert result.events[0].kind == "spy_placed"
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_public_spectacle_reveal_recalls_before_placing_with_empty_supply() -> None:
    spectacle = _imperium_instance("public_spectacle")
    original_posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    state = _state(
        PlayerState(
            player_id=0,
            hand=(spectacle,),
            spies_supply=0,
            spy_post_ids=original_posts,
        )
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    recall = legal_reveal_spy_actions(revealed.state, 0)[0]

    recalled = apply_reveal_spy_action(revealed.state, recall)
    placements = legal_reveal_spy_actions(recalled.state, 0)
    destination = next(
        action
        for action in placements
        if dict(action.arguments)["post_id"] not in original_posts
    )
    result = apply_reveal_spy_action(recalled.state, destination)

    recalled_post = dict(recall.arguments)["post_id"]
    destination_post = dict(destination.arguments)["post_id"]
    assert recall.action_id == "recall_spy_for_reveal_placement"
    assert {action.action_id for action in placements} == {"place_reveal_spy"}
    assert result.state.players[0].spies_supply == 0
    assert result.state.players[0].spy_post_ids == (
        *(post_id for post_id in original_posts if post_id != recalled_post),
        destination_post,
    )
    assert tuple(event.kind for event in (*recalled.events, *result.events)) == (
        "spy_recalled",
        "spy_placed",
    )


def test_wheels_within_wheels_reveals_for_persuasion_and_places_a_spy() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    state = _state(PlayerState(player_id=0, hand=(wheels,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    placement = legal_reveal_spy_actions(revealed.state, 0)[0]

    result = apply_reveal_spy_action(revealed.state, placement)

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        dict(placement.arguments)["post_id"],
    )


def test_undercover_asset_reveal_may_place_a_spy() -> None:
    undercover = _imperium_instance("undercover_asset")
    state = _state(PlayerState(player_id=0, hand=(undercover,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    actions = legal_reveal_spy_actions(revealed.state, 0)

    assert {action.action_id for action in actions} == {
        "gain_two_reveal_strength",
        "place_reveal_spy",
    }
    placement = next(
        action for action in actions if action.action_id == "place_reveal_spy"
    )
    result = apply_reveal_spy_action(revealed.state, placement)

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (
        dict(placement.arguments)["post_id"],
    )


def test_undercover_asset_reveal_may_gain_two_strength() -> None:
    undercover = _imperium_instance("undercover_asset")
    owner = PlayerState(
        player_id=0,
        hand=(undercover,),
        troops_supply=8,
        troops_conflict=1,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    strength = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "gain_two_reveal_strength"
    )

    result = apply_reveal_spy_action(revealed, strength)

    assert result.state.players[0].combat_strength == 4
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 4
    assert context["optional_sword_strength"] == 2
    assert tuple(event.kind for event in result.events) == (
        "reveal_strength_gained",
    )


def test_undercover_asset_reveal_strength_needs_a_conflict_unit() -> None:
    undercover = _imperium_instance("undercover_asset")
    revealed = begin_reveal_turn(
        _state(PlayerState(player_id=0, hand=(undercover,))),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    strength = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "gain_two_reveal_strength"
    )

    result = apply_reveal_spy_action(revealed, strength)

    assert result.state.players[0].combat_strength == 0
    context = dict(result.state.decision_stack[-1].context)
    assert context["strength"] == 0
    assert context["optional_sword_strength"] == 2


def test_undercover_asset_commits_to_spy_after_empty_supply_recall() -> None:
    undercover = _imperium_instance("undercover_asset")
    original_posts = tuple(post.post_id for post in OBSERVATION_POSTS[:3])
    owner = PlayerState(
        player_id=0,
        hand=(undercover,),
        spies_supply=0,
        spy_post_ids=original_posts,
    )
    revealed = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state
    recall = next(
        action
        for action in legal_reveal_spy_actions(revealed, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )

    recalled = apply_reveal_spy_action(revealed, recall).state

    assert {action.action_id for action in legal_reveal_spy_actions(recalled, 0)} == {
        "place_reveal_spy"
    }


def test_unswerving_loyalty_reveals_for_persuasion_and_recruits_one() -> None:
    loyalty = _imperium_instance("unswerving_loyalty")
    state = _state(PlayerState(player_id=0, hand=(loyalty,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].troops_supply == 8
    assert result.state.players[0].troops_garrison == 4


def test_stilgar_counts_only_fremen_cards_revealed_this_turn() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")
    previously_played_fremen = _imperium_instance("unswerving_loyalty")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(stilgar, maula, truthtrance),
            in_play=(previously_played_fremen,),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 6


def test_stilgar_counts_itself_as_a_revealed_fremen_card() -> None:
    stilgar = _imperium_instance("stilgar_the_devoted")
    state = _state(PlayerState(player_id=0, hand=(stilgar,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_leadership_gains_strength_per_other_revealed_sword_card() -> None:
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    rhetoric = _imperium_instance("dangerous_rhetoric")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(leadership, dagger, rhetoric),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3
    assert result.state.players[0].combat_strength == 7


def test_leadership_does_not_count_itself_or_an_agent_card_for_bonus() -> None:
    leadership = _imperium_instance("leadership")
    played_dagger = _instance("dagger")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(leadership,),
            in_play=(played_dagger,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].combat_strength == 3


def test_sardaukar_coordination_counts_each_revealed_emperor_card() -> None:
    first = _imperium_instance("sardaukar_coordination", 0)
    second = _imperium_instance("sardaukar_coordination", 1)
    soldier = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(first, second, soldier),
        troops_supply=8,
        troops_conflict=1,
    )

    result = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert result.state.players[0].combat_strength == 11
    assert dict(result.state.decision_stack[-1].context)["strength"] == 11


def test_sardaukar_coordination_ignores_emperor_agent_cards_in_play() -> None:
    coordination = _imperium_instance("sardaukar_coordination")
    played_soldier = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0,
        hand=(coordination,),
        in_play=(played_soldier,),
        troops_supply=8,
        troops_conflict=1,
    )

    result = begin_reveal_turn(
        _state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    )

    assert result.state.players[0].combat_strength == 4


def test_shishakli_reveal_gains_fremen_influence_only_with_bond() -> None:
    shishakli = _imperium_instance("shishakli")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(
        PlayerState(
            player_id=0,
            hand=(shishakli,),
            troops_supply=8,
            troops_conflict=1,
        )
    )
    with_bond = _state(
        PlayerState(
            player_id=0,
            hand=(shishakli, maula),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )

    assert without_result.state.players[0].influence.fremen == 0
    assert without_result.state.players[0].combat_strength == 4
    assert with_result.state.players[0].influence.fremen == 1
    assert with_result.state.players[0].combat_strength == 5
    assert tuple(event.kind for event in with_result.events) == (
        "reveal_started",
        "influence_gained",
    )


def test_tread_in_darkness_reveals_for_persuasion_and_strength() -> None:
    tread = _imperium_instance("tread_in_darkness")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(tread,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].combat_strength == 3


def test_space_time_folding_reveals_for_one_persuasion() -> None:
    folding = _imperium_instance("space_time_folding")
    state = _state(PlayerState(player_id=0, hand=(folding,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_high_council_and_assembly_hall_add_reveal_persuasion() -> None:
    state = _state(
        PlayerState(
            player_id=0,
            high_council=True,
            agents_available=1,
            agent_locations=("assembly_hall",),
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_reveal_strength_requires_a_unit_in_conflict() -> None:
    dagger = _instance("dagger")
    without_unit = _state(PlayerState(player_id=0, hand=(dagger,)))

    no_unit_result = begin_reveal_turn(
        without_unit,
        legal_reveal_actions(without_unit, 0)[0],
    )
    assert no_unit_result.state.players[0].combat_strength == 0

    with_unit = _state(
        PlayerState(
            player_id=0,
            hand=(dagger,),
            troops_supply=8,
            troops_conflict=1,
        )
    )
    unit_result = begin_reveal_turn(
        with_unit,
        legal_reveal_actions(with_unit, 0)[0],
    )
    assert unit_result.state.players[0].combat_strength == 3


def test_reserve_cards_contribute_their_printed_reveal_values() -> None:
    prepare = "reserve:prepare_the_way:7"
    spice = "reserve:the_spice_must_flow:9"
    state = _state(
        PlayerState(
            player_id=0,
            hand=(prepare, spice),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    assert context["strength"] == 3


def test_transcribed_imperium_cards_contribute_reveal_values() -> None:
    maula = _imperium_instance("maula_pistol")
    truthtrance = _imperium_instance("truthtrance")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(maula, truthtrance),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 2
    assert context["strength"] == 3


def test_sardaukar_soldier_contributes_reveal_values() -> None:
    sardaukar = _imperium_instance("sardaukar_soldier")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(sardaukar,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_hidden_missive_contributes_reveal_values() -> None:
    hidden_missive = _imperium_instance("hidden_missive")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(hidden_missive,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_desert_survival_contributes_reveal_values() -> None:
    desert_survival = _imperium_instance("desert_survival")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(desert_survival,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_smugglers_harvester_contributes_reveal_persuasion() -> None:
    harvester = _imperium_instance("smuggler_s_harvester")
    state = _state(PlayerState(player_id=0, hand=(harvester,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1


def test_smugglers_haven_gains_spice_while_spying_on_a_maker_space() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        spies_supply=2,
        spy_post_ids=("arrakis-hagga-basin",),
    )
    state = _state(owner)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.spice == 2


def test_smugglers_haven_has_no_spice_bonus_at_a_non_maker_post() -> None:
    haven = _imperium_instance("smuggler_s_haven")
    owner = PlayerState(
        player_id=0,
        hand=(haven,),
        spies_supply=2,
        spy_post_ids=("emperor-sardaukar-dutiful-service",),
    )
    state = _state(owner)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 1
    assert result.state.players[0].resources.spice == 0


def test_price_is_no_object_reveals_for_persuasion_and_solari() -> None:
    price = _imperium_instance("price_is_no_object")
    state = _state(PlayerState(player_id=0, hand=(price,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2
    assert result.state.players[0].resources.solari == 2


def test_subversive_advisor_reveals_for_one_solari() -> None:
    subversive = _imperium_instance("subversive_advisor")
    state = _state(PlayerState(player_id=0, hand=(subversive,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0
    assert result.state.players[0].resources.solari == 1


def test_interstellar_trade_persuasion_uses_completed_contracts_at_reveal() -> None:
    interstellar = _imperium_instance(
        "interstellar_trade",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(interstellar,),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
        ),
    )
    state = _state(owner, choam_module=True)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 3


def test_delivery_agreement_gains_spice_automatically_below_four_contracts() -> None:
    delivery = _imperium_instance(
        "delivery_agreement",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(delivery,),
        resources=Resources(spice=2),
        completed_contract_ids=("contract:arrakeen_i",),
    )
    state = _state(owner, choam_module=True)

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].resources.spice == 3
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0
    assert legal_contract_reveal_choice_actions(result.state, 0) == ()


def test_four_contract_reveal_can_keep_spice_or_trash_the_card_for_vp() -> None:
    priority = _imperium_instance(
        "priority_contracts",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(priority,),
        resources=Resources(spice=3),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
            "contract:espionage_i",
        ),
    )
    state = _state(owner, choam_module=True)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    actions = legal_contract_reveal_choice_actions(revealed, 0)

    assert tuple(action.action_id for action in actions) == (
        "keep_contract_reveal_spice",
        "trash_contract_reveal_for_vp",
    )
    assert revealed.players[0].resources.spice == 3

    kept = apply_contract_reveal_choice(revealed, actions[0])
    assert kept.state.players[0].resources.spice == 5
    assert priority in kept.state.players[0].in_play
    assert kept.events[0].kind == "contract_reveal_spice_gained"

    trashed = apply_contract_reveal_choice(revealed, actions[1])
    assert trashed.state.players[0].resources.spice == 3
    assert trashed.state.players[0].victory_points == owner.victory_points + 1
    assert trashed.state.players[0].in_play == ()
    assert trashed.state.players[0].trashed == (priority,)


def test_four_contract_trash_for_vp_is_withheld_once_the_card_is_gone() -> None:
    # The self-trash is the Victory Point's cost, adjudicated at resolution
    # time [Main pp. 9, 20]: once another effect trashed the card while this
    # choice was pending, only the Spice branch remains.
    priority = _imperium_instance(
        "priority_contracts",
        choam_module=True,
    )
    owner = PlayerState(
        player_id=0,
        hand=(priority,),
        resources=Resources(spice=3),
        completed_contract_ids=(
            "contract:arrakeen_i",
            "contract:arrakeen_ii",
            "contract:deliver_supplies",
            "contract:espionage_i",
        ),
    )
    state = _state(owner, choam_module=True)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    gone = replace(
        revealed,
        players=(
            replace(revealed.players[0], in_play=(), trashed=(priority,)),
            *revealed.players[1:],
        ),
    )

    actions = legal_contract_reveal_choice_actions(gone, 0)

    assert tuple(action.action_id for action in actions) == (
        "keep_contract_reveal_spice",
    )


def test_fedaykin_stilltent_gains_water_when_revealed() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    state = _state(PlayerState(player_id=0, hand=(stilltent,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].resources.water == 2
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_northern_watermaster_gains_spice_only_with_fremen_bond() -> None:
    watermaster = _imperium_instance("northern_watermaster")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(watermaster,)))
    with_bond = _state(PlayerState(player_id=0, hand=(watermaster, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )

    assert without_result.state.players[0].resources.spice == 0
    assert with_result.state.players[0].resources.spice == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 2


def test_maker_keeper_contributes_two_reveal_persuasion() -> None:
    maker_keeper = _imperium_instance("maker_keeper")
    state = _state(PlayerState(player_id=0, hand=(maker_keeper,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 2


def test_southern_elders_applies_unconditional_and_bond_reveal_effects() -> None:
    southern_elders = _imperium_instance("southern_elders")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(southern_elders,)))
    with_bond = _state(PlayerState(player_id=0, hand=(southern_elders, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )

    assert without_result.state.players[0].resources.water == 2
    assert dict(without_result.state.decision_stack[-1].context)["persuasion"] == 0
    assert with_result.state.players[0].resources.water == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 3


def test_weirding_woman_contributes_reveal_values() -> None:
    weirding_woman = _imperium_instance("weirding_woman")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(weirding_woman,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    context = dict(result.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["strength"] == 3


def test_ecological_testing_station_gains_water_with_fremen_bond() -> None:
    station = _imperium_instance("ecological_testing_station")
    maula = _imperium_instance("maula_pistol")
    without_bond = _state(PlayerState(player_id=0, hand=(station,)))
    with_bond = _state(PlayerState(player_id=0, hand=(station, maula)))

    without_result = begin_reveal_turn(
        without_bond,
        legal_reveal_actions(without_bond, 0)[0],
    )
    with_result = begin_reveal_turn(
        with_bond,
        legal_reveal_actions(with_bond, 0)[0],
    )

    assert without_result.state.players[0].resources.water == 1
    assert with_result.state.players[0].resources.water == 2
    assert dict(with_result.state.decision_stack[-1].context)["persuasion"] == 2


def test_paracompass_reveal_scales_with_council_and_swordmaster() -> None:
    paracompass = _imperium_instance("paracompass")
    neither = _state(PlayerState(player_id=0, hand=(paracompass,)))
    council = _state(
        PlayerState(player_id=0, hand=(paracompass,), high_council=True)
    )
    both = _state(
        PlayerState(
            player_id=0,
            hand=(paracompass,),
            high_council=True,
            swordmaster_acquired=True,
            agents_available=3,
        )
    )

    neither_result = begin_reveal_turn(
        neither,
        legal_reveal_actions(neither, 0)[0],
    )
    council_result = begin_reveal_turn(
        council,
        legal_reveal_actions(council, 0)[0],
    )
    both_result = begin_reveal_turn(
        both,
        legal_reveal_actions(both, 0)[0],
    )

    assert dict(neither_result.state.decision_stack[-1].context)["persuasion"] == 0
    assert dict(council_result.state.decision_stack[-1].context)["persuasion"] == 4
    assert dict(both_result.state.decision_stack[-1].context)["persuasion"] == 5


def test_overthrow_recruits_and_contributes_reveal_values() -> None:
    overthrow = _imperium_instance("overthrow")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(overthrow,),
            troops_supply=8,
            troops_conflict=1,
        )
    )

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.troops_supply == 7
    assert owner.troops_garrison == 4
    assert context["persuasion"] == 2
    assert context["strength"] == 4


def test_reveal_preserves_agent_cards_already_in_play() -> None:
    played = _instance("dagger", 0)
    revealed = _instance("dagger", 1)
    state = _state(PlayerState(player_id=0, hand=(revealed,), in_play=(played,)))

    result = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0])

    assert result.state.players[0].in_play == (played, revealed)


def test_reveal_cleanup_discards_in_play_but_preserves_late_drawn_hand() -> None:
    revealed = _instance("diplomacy")
    retained = _instance("dagger")
    state = _state(PlayerState(player_id=0, hand=(revealed,)))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    owner = replace(state.players[0], hand=(retained,))
    state = replace(state, players=(owner, *state.players[1:]))

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])
    owner = result.state.players[0]

    assert owner.has_revealed is True
    assert result.state.reveal_order == (0,)
    assert owner.in_play == ()
    assert owner.discard_pile == (revealed,)
    assert owner.hand == (retained,)


def test_reveal_cleanup_skips_players_who_already_revealed() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        replace(state.players[1], has_revealed=True),
        state.players[2],
        replace(state.players[3], has_revealed=True),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    decision = result.state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    assert decision.owner == 2


def test_last_reveal_cleanup_enters_combat_without_pending_decision() -> None:
    state = _state(PlayerState(player_id=0))
    state = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    players = (
        state.players[0],
        *(replace(player, has_revealed=True) for player in state.players[1:]),
    )
    state = replace(state, players=players)

    result = finish_reveal_turn(state, legal_finish_reveal_actions(state, 0)[0])

    assert result.state.phase is GamePhase.COMBAT
    assert result.state.decision_stack == ()
    assert all(player.has_revealed for player in result.state.players)


def test_four_empty_reveal_turns_follow_seat_order_into_combat() -> None:
    state = _state(PlayerState(player_id=0))
    state = replace(
        state,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:2",
                decision=PlayerDecision(owner=2, prompt="Choose a turn"),
            ),
        ),
    )

    visited: list[int] = []
    for player in (2, 3, 0, 1):
        decision = state.decision_stack[-1].decision
        assert isinstance(decision, PlayerDecision)
        visited.append(decision.owner)
        state = begin_reveal_turn(
            state,
            legal_reveal_actions(state, player)[0],
        ).state
        state = finish_reveal_turn(
            state,
            legal_finish_reveal_actions(state, player)[0],
        ).state

    assert visited == [2, 3, 0, 1]
    assert state.reveal_order == (2, 3, 0, 1)
    assert state.phase is GamePhase.COMBAT
    assert state.decision_stack == ()


# --- Immediate reveal of cards that arrive during a Reveal turn [FAQ p. 3] --


def _with_late_hand(state: GameState, card_id: str) -> GameState:
    """Simulate a card landing in seat 0's hand mid-Reveal, before revealing it."""

    players = tuple(
        replace(player, hand=(card_id,)) if player.player_id == 0 else player
        for player in state.players
    )
    return replace(state, players=players)


def test_late_reveal_stilgar_gains_a_persuasion_increment_from_a_fremen_arrival() -> (
    None
):
    # Stilgar, The Devoted (per_revealed_faction=FREMEN) is already revealed;
    # a late-arriving Fremen card [FAQ p. 3] adds the increment its own
    # arrival causes on top of its own printed values, without recomputing
    # Stilgar's already-granted amount.
    stilgar = _imperium_instance("stilgar_the_devoted")
    maula = _imperium_instance("maula_pistol")
    state = _state(PlayerState(player_id=0, hand=(stilgar,)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert dict(revealed.decision_stack[-1].context)["persuasion"] == 2

    arrived = _with_late_hand(revealed, maula)
    result = reveal_late_arrivals(arrived, 0, (maula,))
    context = dict(result.state.decision_stack[-1].context)

    assert result.state.players[0].hand == ()
    assert result.state.players[0].in_play == (stilgar, maula)
    # maula's own Persuasion (1) plus the +2 Stilgar increment.
    assert context["persuasion"] == 2 + 1 + 2
    assert context["revealed_card_count"] == 2
    assert context["revealed_card_001"] == maula


def test_late_reveal_leadership_gains_strength_from_a_late_sword_card() -> None:
    # Leadership (strength_per_other_sword_card=1) is already revealed; a
    # late-arriving card with positive strength adds +1 to the group's
    # strength beyond that card's own value [FAQ p. 3].
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(leadership,),
        troops_supply=8,
        troops_conflict=1,
    )
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.players[0].combat_strength == 3

    arrived = _with_late_hand(revealed, dagger)
    result = reveal_late_arrivals(arrived, 0, (dagger,))
    context = dict(result.state.decision_stack[-1].context)

    # dagger's own strength (1) plus the +1 Leadership increment.
    assert result.state.players[0].combat_strength == 3 + 2
    assert context["strength"] == 5
    assert context["sword_strength"] == 3


def test_late_reveal_leadership_counts_an_already_revealed_sword_card() -> None:
    # Leadership arrives late; its own strength_per_other_sword_card effect
    # counts the already-revealed dagger's strength, recomputed purely over
    # the current revealed set [FAQ p. 3].
    leadership = _imperium_instance("leadership")
    dagger = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        troops_supply=8,
        troops_conflict=1,
    )
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.players[0].combat_strength == 3

    arrived = _with_late_hand(revealed, leadership)
    result = reveal_late_arrivals(arrived, 0, (leadership,))
    context = dict(result.state.decision_stack[-1].context)

    # leadership's own strength (1) plus +1 for the already-revealed dagger.
    assert result.state.players[0].combat_strength == 3 + 2
    assert context["persuasion"] == 2
    assert context["strength"] == 5


def test_late_reveal_pushes_a_resolvable_reveal_choice_frame() -> None:
    corrinth_city = _imperium_instance("corrinth_city")
    state = _state(PlayerState(player_id=0, resources=Resources(solari=5)))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.decision_stack[-1].kind == "reveal"

    arrived = _with_late_hand(revealed, corrinth_city)
    result = reveal_late_arrivals(arrived, 0, (corrinth_city,))

    assert result.state.decision_stack[-1].kind == "reveal_choice"
    actions = legal_corrinth_city_reveal_actions(result.state, 0)
    assert tuple(action.action_id for action in actions) == (
        "gain_five_reveal_solari",
        "take_high_council_from_reveal",
    )
    take_seat = actions[1]
    resolved = apply_corrinth_city_reveal(result.state, take_seat)

    assert resolved.state.players[0].high_council is True
    assert resolved.state.decision_stack[-1].kind == "reveal"


def test_late_reveal_grants_resource_effects_at_arrival() -> None:
    stilltent = _imperium_instance("fedaykin_stilltent")
    state = _state(PlayerState(player_id=0))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state

    arrived = _with_late_hand(revealed, stilltent)
    result = reveal_late_arrivals(arrived, 0, (stilltent,))

    assert result.state.players[0].resources.water == 2
    assert result.state.players[0].in_play == (stilltent,)


def test_late_reveal_works_through_the_personal_draw_reshuffle_chance() -> None:
    # An empty personal deck routes the reveal-time draw through the
    # PERSONAL_DRAW_RESHUFFLE chance; the late-reveal hook on the
    # completion path [FAQ p. 3] must still fire once it resolves.
    discarded = _instance("dagger", 1)
    owner = PlayerState(player_id=0, discard_pile=(discarded,))
    state = _state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    assert revealed.decision_stack[-1].kind == "reveal"

    pending = draw_or_request_personal_cards(
        revealed, 0, 1, source="test:late_draw"
    )
    assert pending.state.decision_stack[-1].kind == "personal_draw_reshuffle"
    decision = pending.state.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)

    outcome = ChanceOutcome(decision.decision_id, (discarded,))
    result = apply_personal_draw_reshuffle(pending.state, outcome)

    assert result.state.decision_stack[-1].kind == "reveal"
    owner_after = result.state.players[0]
    assert owner_after.hand == ()
    assert owner_after.in_play == (discarded,)
    context = dict(result.state.decision_stack[-1].context)
    assert context["revealed_card_count"] == 1
    assert context["revealed_card_000"] == discarded


def test_cross_scaling_reveal_effects_have_no_eligibility_gates() -> None:
    # The late-reveal cross-increment path [FAQ p. 3] re-adjudicates a
    # per_revealed_faction/strength_per_other_sword_card effect's
    # eligibility gates at arrival but never revokes an already-granted
    # amount. Today every such effect is unconditional, so re-adjudication
    # is vacuous; this pin fails the suite if future content adds a gated
    # one, which would need the increment logic to also track revocation.
    entries = (*STARTING_DECK, *RESERVE_STACKS, *IMPERIUM_CARDS)
    scaling_effects = [
        effect
        for entry in entries
        for effect in entry.reveal_effects
        if effect.per_revealed_faction is not None
        or effect.strength_per_other_sword_card
    ]

    assert len(scaling_effects) == 3
    for effect in scaling_effects:
        assert effect.requires_high_council is False
        assert effect.requires_swordmaster is False
        assert effect.minimum_spies_placed == 0
        assert effect.required_faction_bond is None
        assert effect.requires_spying_on_maker_space is False


# ---------------------------------------------------------------- free order


def test_reveal_choice_can_be_deferred_and_resumed_in_the_owners_order() -> None:
    # Two Spacing Guild's Favor copies each queue "pay 3 Spice for Influence".
    # Reveal effects resolve in any order the owner likes [Main p. 12]: the
    # first copy's choice is put off, the second resolves, the Reveal frame
    # stays open for acquisitions, and the deferred choice comes back later.
    first = _imperium_instance("spacing_guild_s_favor", 0)
    second = _imperium_instance("spacing_guild_s_favor", 1)
    state = _state(
        PlayerState(player_id=0, hand=(first, second), resources=Resources(spice=6))
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    top = revealed.decision_stack[-1]
    assert top.kind == "reveal_choice"
    assert dict(top.context)["reveal_card_id"] == first
    defer = DomainAction(action_id="defer_reveal_choice", actor=0)
    assert defer in engine.legal_actions(revealed, 0)

    deferred = engine.apply(revealed, defer)
    assert [event.kind for event in deferred.events] == ["reveal_choice_deferred"]
    assert dict(deferred.state.decision_stack[-1].context)["reveal_card_id"] == second
    reveal_frame = deferred.state.decision_stack[-2]
    assert reveal_frame.kind == "reveal"
    assert dict(reveal_frame.context)["deferred_reveal_choices"] == (
        f"{first}|may_pay_three_spice_for_influence"
    )

    pay = next(
        action
        for action in engine.legal_actions(deferred.state, 0)
        if action.action_id == "pay_reveal_spice_influence"
        and dict(action.arguments)["faction"] == "emperor"
    )
    paid = engine.apply(deferred.state, pay).state
    assert paid.decision_stack[-1].kind == "reveal"
    assert paid.players[0].resources.spice == 3
    actions = engine.legal_actions(paid, 0)
    action_ids = {action.action_id for action in actions}
    assert "finish_reveal" not in action_ids
    with pytest.raises(ValueError, match="not a legal Reveal cleanup"):
        finish_reveal_turn(paid, DomainAction(action_id="finish_reveal", actor=0))
    # This bare state has nothing to acquire, so the Reveal frame offers just
    # the resumption; with a market it would also list the acquisitions.
    assert [action.action_id for action in actions] == ["resume_reveal_choice"]
    resume = actions[0]
    assert dict(resume.arguments) == {"effect": "may_pay_three_spice_for_influence"}

    resumed = engine.apply(paid, resume)
    assert [event.kind for event in resumed.events] == ["reveal_choice_resumed"]
    top = resumed.state.decision_stack[-1]
    assert top.kind == "reveal_choice"
    assert dict(top.context)["reveal_card_id"] == first
    assert dict(top.context)["reveal_choice_resumed"] is True
    reveal_context = dict(resumed.state.decision_stack[-2].context)
    assert reveal_context["deferred_reveal_choices"] == ""
    action_ids = {action.action_id for action in engine.legal_actions(resumed.state, 0)}
    # A resumed choice cannot be put off again, so the Reveal cannot cycle.
    assert "defer_reveal_choice" not in action_ids
    assert "pay_reveal_spice_influence" in action_ids

    declined = engine.apply(
        resumed.state,
        DomainAction(action_id="decline_reveal_spice_influence", actor=0),
    ).state
    assert declined.decision_stack[-1].kind == "reveal"
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(declined, 0)
    }


def test_a_started_spy_placement_cannot_be_deferred() -> None:
    wheels = _imperium_instance("wheels_within_wheels")
    posts = (
        "arrakis-hagga-basin",
        "arrakis-deep-desert",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(player_id=0, hand=(wheels,), spies_supply=0, spy_post_ids=posts)
    )
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert legal_defer_reveal_choice_actions(revealed, 0) == (
        DomainAction(action_id="defer_reveal_choice", actor=0),
    )

    recall = next(
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "recall_spy_for_reveal_placement"
    )
    committed = engine.apply(revealed, recall).state

    # The recall committed the placement; only the post choice remains.
    assert legal_defer_reveal_choice_actions(committed, 0) == ()
    assert "defer_reveal_choice" not in {
        action.action_id for action in engine.legal_actions(committed, 0)
    }


def test_a_resumed_choice_whose_condition_lapsed_is_dropped() -> None:
    # In High Places' two-Spy recall is deferred, Spy Network's required
    # recall resolves first and leaves one Spy; brought back, the two-Spy
    # choice is judged again at resolution [Main p. 12] and no longer opens.
    in_high_places = _imperium_instance("in_high_places")
    spy_network = _imperium_instance("spy_network")
    posts = (
        "arrakis-hagga-basin",
        "bene-gesserit-espionage-secrets",
    )
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, spy_network),
            spies_supply=1,
            spy_post_ids=posts,
        )
    )
    state = replace(state, intrigue_deck=("intrigue:test:0",))
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    engine = UprisingRulesEngine()
    assert dict(revealed.decision_stack[-1].context)["reveal_choice_effect"] == (
        "may_recall_two_spies_for_two_persuasion"
    )

    deferred = engine.apply(
        revealed, DomainAction(action_id="defer_reveal_choice", actor=0)
    ).state
    assert dict(deferred.decision_stack[-1].context)["reveal_choice_effect"] == (
        "recall_spy_to_draw_intrigue_if_two_placed"
    )
    recall = next(
        action
        for action in engine.legal_actions(deferred, 0)
        if action.action_id == "recall_spy_for_reveal"
    )
    recalled = engine.apply(deferred, recall).state
    assert len(recalled.players[0].spy_post_ids) == 1
    assert recalled.decision_stack[-1].kind == "reveal"

    resume = next(
        action
        for action in engine.legal_actions(recalled, 0)
        if action.action_id == "resume_reveal_choice"
    )
    result = engine.apply(recalled, resume)

    assert [event.kind for event in result.events] == [
        "reveal_choice_resumed",
        "reveal_choice_unavailable",
    ]
    assert result.state.decision_stack[-1].kind == "reveal"
    reveal_context = dict(result.state.decision_stack[-1].context)
    assert reveal_context["deferred_reveal_choices"] == ""
    assert "finish_reveal" in {
        action.action_id for action in engine.legal_actions(result.state, 0)
    }
