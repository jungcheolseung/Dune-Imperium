"""Tests for the basic Reveal-turn transition."""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.reveal_turn import (
    apply_reveal_spy_action,
    begin_reveal_turn,
    finish_reveal_turn,
    legal_finish_reveal_actions,
    legal_reveal_actions,
    legal_reveal_spy_actions,
)


def _instance(card_id: str, copy: int = 0) -> str:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )[copy]


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _state(player: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(player, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
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
    choices = engine.legal_actions(revealed.state, 0)
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

    assert {action.action_id for action in choices} == {"place_reveal_spy"}
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
