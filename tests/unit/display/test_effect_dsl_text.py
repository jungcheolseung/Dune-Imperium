"""Tests for the Intrigue effect DSL English text renderer."""

import pytest

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CompletedContractsAtLeast,
    DeployFromGarrison,
    EffectSection,
    FlipBattleCard,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    InfluenceAtLeast,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    PayResources,
    PlaceSpy,
    SandwormsInConflictAtLeast,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS, INTRIGUE_CARDS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, BattleIcon
from dune_imperium.display.effect_dsl_text import (
    condition_text,
    cost_text,
    intrigue_card_text,
    option_text,
    reward_text,
    section_text,
    trigger_text,
)


def test_condition_text_renders_a_faction_influence_threshold() -> None:
    assert (
        condition_text(InfluenceAtLeast(Faction.EMPEROR, 3))
        == "you have 3 or more Emperor Influence"
    )


def test_condition_text_renders_completed_contracts() -> None:
    assert (
        condition_text(CompletedContractsAtLeast(2))
        == "you have completed 2 or more Contracts"
    )


def test_cost_text_renders_pay_resources() -> None:
    assert cost_text(PayResources(spice=2)) == "Pay 2 spice"


def test_cost_text_renders_lose_influence() -> None:
    assert cost_text(LoseInfluence(1)) == "Lose 1 Influence"


def test_reward_text_renders_gain_resources() -> None:
    assert reward_text(GainResources(solari=4)) == "Gain 4 solari"


def test_reward_text_renders_combat_strength_as_swords() -> None:
    assert reward_text(GainCombatStrength(1)) == "Gain 1 sword"
    assert reward_text(GainCombatStrength(4)) == "Gain 4 swords"


def test_trigger_text_renders_on_reveal_acquisition() -> None:
    assert (
        trigger_text(OnRevealAcquisitionThisRound())
        == "Whenever you acquire a card during your Reveal turn this round"
    )


def test_trigger_text_renders_on_units_deployed() -> None:
    # "When you deploy three or more units to the Conflict in a single
    # turn:" [Distraction card; Coercive Negotiation card].
    assert (
        trigger_text(OnUnitsDeployedInTurn(3))
        == "When you deploy 3 or more units to the Conflict in a turn"
    )


def test_section_text_joins_cost_and_reward_with_an_arrow() -> None:
    section = EffectSection(
        costs=(LoseInfluence(1),),
        rewards=(GainResources(solari=4),),
    )

    assert section_text(section) == "Lose 1 Influence → Gain 4 solari"


def test_section_text_prefixes_a_condition() -> None:
    section = EffectSection(
        condition=CompletedContractsAtLeast(2),
        rewards=(GainCombatStrength(4),),
    )

    assert (
        section_text(section)
        == "If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_backed_by_choam_plot_option() -> None:
    entry = INTRIGUE_CARDS_BY_ID["backed_by_choam"]

    assert option_text(entry.options[0]) == "Plot — Lose 1 Influence → Gain 4 solari"
    assert entry.options[0].timing is IntrigueTiming.PLOT
    assert option_text(entry.options[1]) == (
        "Combat — If you have completed 2 or more Contracts: Gain 4 swords"
    )


def test_option_text_renders_a_reveal_acquisition_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["call_to_arms"]

    assert option_text(entry.options[0]) == (
        "Plot — Whenever you acquire a card during your Reveal turn this round: "
        "Recruit 1 troop"
    )


def test_option_text_renders_a_units_deployed_trigger() -> None:
    entry = INTRIGUE_CARDS_BY_ID["distraction"]

    # "You may place this Spy on the same observation post as another
    # player's Spy." [Distraction card]: sharing is allowed, not required.
    assert option_text(entry.options[0]) == (
        "Plot — When you deploy 3 or more units to the Conflict in a turn: "
        "Place a Spy (may share another player's Spy's post)"
    )


def test_option_text_joins_multiple_sections_with_a_semicolon() -> None:
    entry = INTRIGUE_CARDS_BY_ID["depart_for_arrakis"]

    assert option_text(entry.options[0]) == (
        "Plot — Pay 2 spice → Recruit 3 troops; "
        "If you have 3 or more Spacing Guild Influence: Draw 1 card"
    )


def test_intrigue_card_text_covers_every_card_with_non_empty_lines() -> None:
    for entry in INTRIGUE_CARDS:
        if not entry.play_data_complete:
            # Bloodlines cards awaiting transcription (M12) render no options.
            continue
        lines = intrigue_card_text(entry)

        assert lines, f"{entry.card.card_id} produced no option lines"
        for line in lines:
            assert isinstance(line, str)
            assert line.strip()


def test_intrigue_card_text_renders_every_option_of_every_card() -> None:
    for entry in INTRIGUE_CARDS:
        assert len(intrigue_card_text(entry)) == len(entry.options)


def test_cost_text_lose_troops_prints_the_count() -> None:
    # "Lose two of your troops" [Twisted Sinister card face]; the noun-only
    # wording ("Lose troops") dropped the printed count.
    assert cost_text(LoseTroops(2)) == "Lose 2 troops"
    assert cost_text(LoseTroops(1)) == "Lose 1 troop"
    assert (
        cost_text(LoseTroops(2, from_conflict=True))
        == "Lose 2 troops in the Conflict"
    )


def test_twisted_ambitious_and_sinister_name_their_troop_counts() -> None:
    ambitious = intrigue_card_text(INTRIGUE_CARDS_BY_ID["twisted_ambitious"])
    assert "Lose 3 troops" in ambitious[0]
    assert "opponent has more Influence" in ambitious[0]

    sinister = intrigue_card_text(INTRIGUE_CARDS_BY_ID["twisted_sinister"])
    assert "Lose 2 troops" in sinister[0]


def test_gruesome_sacrifice_names_its_troop_count() -> None:
    # "Lose two of your troops in the Conflict" [Gruesome Sacrifice card face].
    lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID["gruesome_sacrifice"])

    assert lines == [
        "Combat — Lose 2 troops in the Conflict → "
        "Tleilaxu (advance your Tleilaxu token), Generate 2 specimens"
    ]


def test_cost_text_flip_battle_card_names_the_wild_alternative() -> None:
    # "Flip one of your face-up [icon] or [wild] Conflict cards" [Crysknife
    # card face] [Desert Mouse card face] [Ornithopter card face]; the
    # interpreter accepts a Wild-icon card too (effect_interpreter.py).
    assert cost_text(FlipBattleCard(BattleIcon.CRYSKNIFE)) == (
        "Flip a face-up won Conflict card (Crysknife or Wild icon) face down"
    )


def test_crysknife_desert_mouse_and_ornithopter_name_the_wild_alternative() -> None:
    for card_id in ("crysknife", "desert_mouse", "ornithopter"):
        lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID[card_id])
        assert any("Wild" in line for line in lines), card_id


def test_reward_text_deploy_from_garrison_names_up_to_and_the_source() -> None:
    # "Deploy up to four troops from your garrison to the Conflict"
    # [Detonation card face]; the old text read "Deploy 4 troops".
    assert reward_text(DeployFromGarrison(4)) == (
        "Deploy up to 4 troops from your garrison to the Conflict"
    )
    assert reward_text(DeployFromGarrison(1)) == (
        "Deploy up to 1 troop from your garrison to the Conflict"
    )


def test_detonation_counterattack_and_twisted_devious_name_up_to() -> None:
    detonation = intrigue_card_text(INTRIGUE_CARDS_BY_ID["detonation"])
    assert "Deploy up to 4 troops from your garrison" in detonation[1]

    counterattack = intrigue_card_text(INTRIGUE_CARDS_BY_ID["counterattack"])
    assert "Deploy up to 2 troops from your garrison" in counterattack[0]

    devious = intrigue_card_text(INTRIGUE_CARDS_BY_ID["twisted_devious"])
    assert "Deploy up to 2 troops from your garrison" in devious[1]


def test_reward_text_trash_personal_card_reads_hand_only_and_bonus_spice() -> None:
    assert reward_text(TrashPersonalCard()) == "Trash a card"
    assert (
        reward_text(TrashPersonalCard(hand_only=True))
        == "Trash a card from your hand"
    )
    # Navigation card 5: "If you trash a card that costs 1 or more: 2 spice"
    # [Navigation Card 5 face].
    assert reward_text(TrashPersonalCard(bonus_spice=2, bonus_minimum_cost=1)) == (
        "Trash a card; if it costs 1 or more: Gain 2 spice"
    )


def test_twisted_devious_first_option_names_the_hand() -> None:
    # "Trash a card from your hand." [Twisted Devious card face].
    lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID["twisted_devious"])

    assert lines[0] == "Plot — Trash a card from your hand"


def test_navigation_card_5_renders_its_bonus_spice_condition() -> None:
    lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID["navigation_card_5"])

    assert lines == ["Trash a card; if it costs 1 or more: Gain 2 spice"]


def test_condition_text_sandworms_in_conflict_names_the_owner() -> None:
    # "If you have one or more sandworms in the Conflict:" [Devour card
    # face] [Ripples in the Sand card face]; the rule checks the owner's own
    # sandworms (effect_interpreter.py), unlike the old "there is a
    # sandworm" wording.
    assert (
        condition_text(SandwormsInConflictAtLeast(1))
        == "you have one or more sandworms in the Conflict"
    )
    assert (
        condition_text(SandwormsInConflictAtLeast(2))
        == "you have 2 or more sandworms in the Conflict"
    )


def test_devour_and_ripples_in_the_sand_name_the_owner() -> None:
    for card_id in ("devour", "ripples_in_the_sand"):
        lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID[card_id])
        assert any(
            "If you have one or more sandworms in the Conflict" in line
            for line in lines
        ), card_id


def test_gain_influence_text_renders_where_opponent_leads() -> None:
    # Twisted Ambitious: "a Faction where an opponent has more Influence
    # than you" [Twisted Ambitious card face].
    assert reward_text(GainInfluence(where_opponent_leads=True)) == (
        "Gain 1 Influence (choose a Faction where an opponent has more "
        "Influence than you)"
    )


def test_gain_influence_text_renders_different_from_trigger_and_minimum() -> None:
    # Navigation card 1: "a different Faction ... where you have 2+
    # Influence" [Navigation Card 1 face].
    assert reward_text(
        GainInfluence(different_from_trigger=True, minimum_own=2)
    ) == "Gain 1 Influence (choose a different Faction where you have 2+ Influence)"


def test_navigation_card_1_names_its_influence_limits() -> None:
    lines = intrigue_card_text(INTRIGUE_CARDS_BY_ID["navigation_card_1"])

    assert "different Faction" in lines[1]
    assert "2+ Influence" in lines[1]


def test_navigation_cards_print_no_timing_label() -> None:
    # A Navigation card is played automatically when Steersman Y'rkoon
    # reaches 2 Influence with a Faction and prints no Plot/Combat/Endgame
    # banner [Navigation card faces].
    for number in range(1, 11):
        entry = INTRIGUE_CARDS_BY_ID[f"navigation_card_{number}"]
        for line in intrigue_card_text(entry):
            assert not line.startswith(("Plot —", "Combat —", "Endgame —")), (
                entry.card.card_id
            )


def test_option_text_show_timing_false_omits_the_prefix() -> None:
    entry = INTRIGUE_CARDS_BY_ID["navigation_card_9"]

    assert option_text(entry.options[0], show_timing=False) == "Draw 1 card"
    assert option_text(entry.options[0]) == "Plot — Draw 1 card"


def test_navigation_cards_carry_no_timing_prefix() -> None:
    # Navigation cards print no timing banner; Plot Course plays them
    # [Steersman Y'rkoon card; navigation_card_10 face].
    navigation = [entry for entry in INTRIGUE_CARDS if entry.navigation]
    assert len(navigation) == 10
    for entry in navigation:
        for line in intrigue_card_text(entry):
            assert not line.startswith(("Plot", "Combat", "Endgame")), line
    (line,) = intrigue_card_text(INTRIGUE_CARDS_BY_ID["navigation_card_10"])
    assert line.startswith("Lose 1 Influence")


def test_special_mission_text_names_the_city_post() -> None:
    # "[Spy] on [City disc]" [Special Mission card]; the post must connect
    # to a City space [Main p. 20].
    entry = INTRIGUE_CARDS_BY_ID["special_mission"]

    assert option_text(entry.options[0]) == "Plot — Place a Spy (City Observation Post)"


def test_place_spy_agent_icon_target_is_validated() -> None:
    assert reward_text(PlaceSpy(agent_icons=(AgentIcon.SPICE_TRADE,))) == (
        "Place a Spy (Spice Trade Observation Post)"
    )
    with pytest.raises(ValueError):
        PlaceSpy(agent_icons=())
    with pytest.raises(ValueError):
        PlaceSpy(agent_icons=(AgentIcon.CITY,), factions=(Faction.FREMEN,))
    with pytest.raises(ValueError):
        PlaceSpy(agent_icons=(AgentIcon.CITY,), shared_post=True)
