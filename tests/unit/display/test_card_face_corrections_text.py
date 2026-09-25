"""Display lines of Imperium cards re-read from their printed faces (2026-09-26).

Each card's text follows its corrected play data, so the display used to show
the misread effect (or leave a printed line out).
"""

from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect
from dune_imperium.display.cards import personal_card_text
from dune_imperium.rules.reveal_turn import reveal_choice_prompt


def test_covert_operation_shows_its_two_reveal_spies() -> None:
    # The Reveal box prints two Spy icons and no Persuasion [Covert Operation
    # card]; the display had no Reveal line at all.
    entry = IMPERIUM_CARDS_BY_ID["covert_operation"]

    assert personal_card_text(entry) == [
        "Agent: Each opponent discards a card",
        "Reveal: Place 2 Spies",
    ]


def test_in_high_places_shows_its_bond_draw_spy_and_three_persuasion() -> None:
    # "If you have another Bene Gesserit card in play: [draw 1 card] [Spy]"
    # and "[recall Spy] [recall Spy] -> +3 Persuasion" [In High Places card];
    # the display read "Gain 1 water" and "+2 Persuasion".
    entry = IMPERIUM_CARDS_BY_ID["in_high_places"]

    assert personal_card_text(entry) == [
        "Agent: If Bene Gesserit Bond: Draw 1 card, Place a Spy",
        "Reveal: You may recall 2 Spies → +3 Persuasion",
        "On acquire: Place a Spy",
    ]


def test_unswerving_loyalty_shows_its_fremen_bond_line() -> None:
    # "Fremen Bond : You may deploy or retreat one of your troops."
    # [Unswerving Loyalty card]; the display showed only the recruit.
    entry = IMPERIUM_CARDS_BY_ID["unswerving_loyalty"]

    assert personal_card_text(entry) == [
        "Reveal: Recruit 1 troop; Fremen Bond: You may deploy or retreat 1 troop",
    ]


def test_for_humanity_shows_the_two_influence_alliance_cost() -> None:
    # "Bene Gesserit Alliance: [lose two Influence] -> [1 VP]", a "?" diamond
    # with two red chevrons [For Humanity card]; the display said "lose 1".
    entry = IMPERIUM_CARDS_BY_ID["for_humanity"]

    assert personal_card_text(entry) == [
        "Agent: Gain 1 Influence with a chosen Faction",
        "Reveal: Bene Gesserit Alliance: You may lose 2 Influence with one "
        "Faction → Gain 1 VP",
    ]
    assert reveal_choice_prompt(
        PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE
    ) == (
        "Bene Gesserit Alliance: lose two Influence with one Faction for a "
        "Victory Point, or decline"
    )
