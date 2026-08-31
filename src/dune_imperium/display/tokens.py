"""English text for personal-card enum tokens and automatic Reveal effects.

Wording follows the same shared display contract as ``effect_dsl_text`` and
``structs``: short imperative fragments, no trailing period, resources
lowercase, game terms capitalized as printed. Card-specific wording is
sourced from ``docs/implementation-audits/personal-cards.md`` (per-card,
image-verified behaviour) first, ``docs/card-data-sources.md`` second, and
the enum member name only as a last resort.

Every ``PersonalCard*Effect`` enum has one exported ``Mapping`` here so a
regression test can assert full coverage (``set(map) == set(EnumClass)``);
a newly added enum member without matching text then fails that test instead
of silently rendering a ``KeyError`` at display time. ``PersonalCardBond``
(the Faction-affiliation enum used inside ``PersonalCardRevealEffect``) has
no card-facing members of its own, so it stays a private lookup used only by
:func:`reveal_effect_text`.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardBond,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
)

_BOND_NAMES: dict[PersonalCardBond, str] = {
    PersonalCardBond.EMPEROR: "Emperor",
    PersonalCardBond.SPACING_GUILD: "Spacing Guild",
    PersonalCardBond.BENE_GESSERIT: "Bene Gesserit",
    PersonalCardBond.FREMEN: "Fremen",
}


def _bond_name(bond: PersonalCardBond) -> str:
    return _BOND_NAMES[bond]


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


# Agent-box effects. None of the transcribed members are a "no effect"
# sentinel today (a card with no Agent-box text simply leaves
# ``agent_effect`` unset), so every value below is non-empty; the empty-
# string convention noted in the module docstring is reserved for a future
# sentinel member rather than exercised now.
AGENT_EFFECT_TEXT: Final[Mapping[PersonalCardAgentEffect, str]] = MappingProxyType(
    {
        PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF: (
            "Gain 2 Influence with the visited Faction, Trash this card"
        ),
        PersonalCardAgentEffect.LOOK_AT_TOP_THREE: (
            "If you have 3 or more cards in your deck: Look at the top 3 cards, "
            "Draw 1, Discard 1, Trash 1"
        ),
        PersonalCardAgentEffect.TRASH_SELF: "Trash this card",
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD: "You may trash a card",
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE: (
            "You may trash a card → Draw 1 card"
        ),
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND: (
            "If Bene Gesserit Bond: You may trash a card → Draw 1 card"
        ),
        (
            PersonalCardAgentEffect
            .MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        ): (
            "If Bene Gesserit Alliance: You may trash a card → "
            "Draw 1 Intrigue card, Recruit 2 troops"
        ),
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE: (
            "You may trash this card and an Emperor card from your hand → "
            "Gain 1 additional Influence with the visited Faction"
        ),
        PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE: (
            "Trash this card, Gain 1 Influence with a chosen Faction"
        ),
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN: (
            "If you recalled a Spy this turn: Gain 1 Influence with a chosen Faction"
        ),
        # Per task instruction: this member always resolves through the
        # owner's Leader's Signet Ring ability data rather than typed text.
        PersonalCardAgentEffect.LEADER_SIGNET: "Your Leader's Signet Ring ability",
        PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO: (
            "You may pay 2 water → Draw 2 cards"
        ),
        PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP: (
            "You may pay 4 spice → Gain 1 VP"
        ),
        PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP: (
            "You may discard 2 cards and pay 5 solari → Gain 1 VP"
        ),
        (
            PersonalCardAgentEffect
            .MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
        ): (
            "If Spacing Guild Alliance: You may trash an Intrigue card and "
            "pay 2 spice → Gain 1 VP"
        ),
        PersonalCardAgentEffect.ACQUIRE_WITH_SOLARI_TO_HAND: (
            "You may acquire an Imperium Row or Reserve card to your hand, "
            "paying its cost in solari"
        ),
        PersonalCardAgentEffect.TAKE_CONTRACT: "Take 1 face-up Contract",
        PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT: (
            "You may discard a card → Take 1 face-up Contract"
        ),
        PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO: (
            "If you have completed 2 or more Contracts: Draw 1 card, "
            "If you have completed 4 or more Contracts: Draw 1 more card"
        ),
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE: (
            "Gain 1 Influence with a chosen Faction"
        ),
        PersonalCardAgentEffect.DRAW_ONE_AND_RECALL_AGENT: (
            "Draw 1 card, Recall 1 Agent"
        ),
        PersonalCardAgentEffect.DRAW_PERSONAL_CARD: "Draw 1 card",
        PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT: (
            "Draw 1 card per sandworm in the Conflict"
        ),
        PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD: (
            "You may discard a card → Draw 1 card "
            "(2 if the discarded card has Spacing Guild affiliation)"
        ),
        PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: (
            "Discard a card → Draw 2 cards if the discarded card has "
            "Spacing Guild affiliation"
        ),
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD: (
            "You may discard a card → Draw 1 Intrigue card, Draw 1 card"
        ),
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD: (
            "You may discard a card → Draw 1 card (also Draw 1 Intrigue card "
            "if the discarded card has Spacing Guild affiliation)"
        ),
        PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD: (
            "Each opponent discards a card"
        ),
        PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE: (
            "If you are at a Maker space: Gain 1 spice"
        ),
        PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_MAKER_SPACE: (
            "If you are at a Maker space: Gain 2 spice"
        ),
        PersonalCardAgentEffect.GAIN_TWO_SOLARI: "Gain 2 solari",
        PersonalCardAgentEffect.PLACE_SPY: "Place a Spy",
        PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE: (
            "Place a Spy (may share a post with an opponent's Spy if you are "
            "spying on the visited space)"
        ),
        PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN: (
            "If you recalled a Spy this turn: Recruit 3 troops"
        ),
        PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN: (
            "If you recalled a Spy this turn: Recruit 2 troops"
        ),
        PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN: (
            "If you recalled a Spy this turn: Draw 1 Intrigue card"
        ),
        PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT: (
            "If you have 3 or more units in the Conflict: Draw 1 Intrigue card"
        ),
        PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND: (
            "If Bene Gesserit Bond: Gain 1 water"
        ),
        PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE: (
            "Gain 1 additional Influence with the visited Faction"
        ),
        PersonalCardAgentEffect.GAIN_WATER: "Gain 1 water",
        PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: (
            "If you have 2 or more Bene Gesserit Influence: Gain 1 water, "
            "If you have 2 or more Fremen Influence: Gain 1 spice"
        ),
        PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: (
            "If you have 2 or more Emperor Influence: Gain 2 solari, "
            "If you have 2 or more Spacing Guild Influence: Gain 1 spice"
        ),
        PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE: (
            "If you are at a Maker space: Recruit 1 troop"
        ),
        PersonalCardAgentEffect.RECRUIT_TWO_TROOPS: "Recruit 2 troops",
        PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND: (
            "If Bene Gesserit Bond: Recruit 2 troops"
        ),
        PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND: (
            "If Bene Gesserit Bond: Return this card to your hand"
        ),
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: (
            "If you have 2 or more Bene Gesserit Influence: Draw 1 card"
        ),
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: (
            "If you have 2 or more Bene Gesserit Influence: Recruit 1 troop, "
            "Draw 1 card"
        ),
    }
)

TRASH_EFFECT_TEXT: Final[Mapping[PersonalCardTrashEffect, str]] = MappingProxyType(
    {
        PersonalCardTrashEffect.DRAW_INTRIGUE_CARD: "Draw 1 Intrigue card",
    }
)

DISCARD_EFFECT_TEXT: Final[Mapping[PersonalCardDiscardEffect, str]] = MappingProxyType(
    {
        PersonalCardDiscardEffect.GAIN_TWO_SPICE: "Gain 2 spice",
    }
)

ACQUISITION_EFFECT_TEXT: Final[Mapping[PersonalCardAcquisitionEffect, str]] = (
    MappingProxyType(
        {
            PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD: "Draw 1 Intrigue card",
            PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI: "Gain 2 solari",
            PersonalCardAcquisitionEffect.PLACE_SPY: "Place a Spy",
            PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE: (
                "Gain 1 Spacing Guild Influence"
            ),
            PersonalCardAcquisitionEffect.TAKE_CONTRACT: "Take 1 face-up Contract",
        }
    )
)

# The one transcribed member is specific to The Spice Must Flow (see the
# enum member name and Guild Spy's audit entry); ``cards.py`` supplies that
# card-specific condition as the display prefix, so this text is only the
# reward.
REVEAL_ACQUISITION_EFFECT_TEXT: Final[
    Mapping[PersonalCardRevealAcquisitionEffect, str]
] = MappingProxyType(
    {
        (
            PersonalCardRevealAcquisitionEffect
            .GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
        ): (
            "Gain 1 Influence with each Faction you are spying on"
        ),
    }
)

# Reveal-turn choice effects. Persuasion and strength gains use the "+N"
# shorthand (matching reveal_effect_text below) because these are all
# alternate outcomes of the same printed Reveal box, not Agent-box gains.
REVEAL_CHOICE_EFFECT_TEXT: Final[Mapping[PersonalCardRevealChoiceEffect, str]] = (
    MappingProxyType(
        {
            PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED: (
                "If you have placed 2 or more Spies: Recall a Spy, "
                "Draw 1 Intrigue card"
            ),
            PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION: (
                "You may recall 2 Spies → +2 Persuasion"
            ),
            PersonalCardRevealChoiceEffect.PLACE_SPY: "Place a Spy",
            PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH: (
                "Choose one: Place a Spy / +2 swords"
            ),
            PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE: (
                "You may lose 1 Influence with a chosen Faction → "
                "Gain 1 Influence with a chosen Faction"
            ),
            PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE: (
                "You may pay 3 spice → Gain 1 Influence with a chosen Faction"
            ),
            PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH: (
                "You may trash another Emperor card in play → +3 swords"
            ),
            PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH: (
                "You may retreat 2 troops → +4 swords"
            ),
            PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL: (
                "Choose one: Gain 5 solari / "
                "Pay 5 solari → Take the High Council seat"
            ),
            PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM: (
                "Choose one: Keep the Persuasion / "
                "If Maker Hooks: Pay 1 water → Summon and deploy a sandworm"
            ),
            (
                PersonalCardRevealChoiceEffect
                .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
            ): (
                "If you have completed 4 or more Contracts: "
                "Choose one: Keep the spice / Trash this card → Gain 1 VP"
            ),
        }
    )
)

_HANDLED_REVEAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "solari",
        "spice",
        "water",
        "persuasion",
        "recruit_troops",
        "strength",
        "strength_per_other_sword_card",
        "draw_intrigue",
        "influence",
        "influence_faction",
        "required_faction_bond",
        "requires_high_council",
        "requires_swordmaster",
        "minimum_spies_placed",
        "requires_spying_on_maker_space",
        "per_revealed_faction",
        "persuasion_per_completed_contract",
    }
)


def reveal_effect_text(effect: PersonalCardRevealEffect) -> str:
    """Render one automatic Reveal-time gain as ``If <condition>: <gains>``.

    Requirement fields are rendered first as an ``If ...:`` prefix (Faction
    Bond, High Council/Swordmaster, minimum placed Spies, spying on a Maker
    space); ``per_revealed_faction`` instead scales whichever gain
    (Persuasion or strength) it accompanies, so it is folded into that
    gain's own text rather than into the prefix. The gains that follow are
    joined with ", "; Persuasion and strength use the "+N" shorthand that
    matches the printed Reveal diamonds, everything else uses "Gain N ...".
    """

    conditions: list[str] = []
    if effect.required_faction_bond is not None:
        conditions.append(f"{_bond_name(effect.required_faction_bond)} Bond")
    if effect.requires_swordmaster:
        conditions.append("High Council and Swordmaster")
    elif effect.requires_high_council:
        conditions.append("High Council")
    if effect.minimum_spies_placed:
        noun = "Spy" if effect.minimum_spies_placed == 1 else "Spies"
        conditions.append(
            f"you have placed {effect.minimum_spies_placed} or more {noun}"
        )
    if effect.requires_spying_on_maker_space:
        conditions.append("you are spying on a Maker space")

    per_faction = (
        f" per revealed {_bond_name(effect.per_revealed_faction)} card"
        if effect.per_revealed_faction is not None
        else ""
    )

    gains: list[str] = []
    if effect.persuasion:
        gains.append(f"+{effect.persuasion} Persuasion{per_faction}")
    if effect.strength:
        gains.append(
            f"+{effect.strength} {_plural(effect.strength, 'sword')}{per_faction}"
        )
    if effect.strength_per_other_sword_card:
        n = effect.strength_per_other_sword_card
        gains.append(f"+{n} {_plural(n, 'sword')} per other revealed sword card")
    if effect.persuasion_per_completed_contract:
        gains.append(
            f"+{effect.persuasion_per_completed_contract} Persuasion "
            "per completed Contract"
        )
    if effect.solari:
        gains.append(f"Gain {effect.solari} solari")
    if effect.spice:
        gains.append(f"Gain {effect.spice} spice")
    if effect.water:
        gains.append(f"Gain {effect.water} water")
    if effect.draw_intrigue:
        gains.append(
            f"Draw {effect.draw_intrigue} Intrigue "
            f"{_plural(effect.draw_intrigue, 'card')}"
        )
    if effect.recruit_troops:
        gains.append(
            f"Recruit {effect.recruit_troops} {_plural(effect.recruit_troops, 'troop')}"
        )
    if effect.influence:
        assert effect.influence_faction is not None
        gains.append(
            f"Gain {effect.influence} {_bond_name(effect.influence_faction)} Influence"
        )

    text = ", ".join(gains)
    if conditions:
        return f"If {' and '.join(conditions)}: {text}"
    return text
