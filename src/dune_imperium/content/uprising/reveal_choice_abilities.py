"""Reveal choices of personal cards as ability records (composed effects, A4d).

docs/composed-effects-plan.md 5 (A4d): a revealed card's choice effect -- what
the owner chooses during its Reveal turn, in any order beside its purchases
[Main p. 12] -- is written here, keyed by the choice's key (each set's
``*_REVEAL_CHOICES`` table lists a card's keys by its id;
``UPRISING_REVEAL_CHOICES`` at the end of this module). The printed text is
``display/tokens.REVEAL_CHOICE_EFFECT_TEXT``.

- ``mark`` says whether the owner may leave it unused (OQ-095 (7) addition,
  user ruling 2026-10-14): an optional choice -- "may", an arrow cost or a
  black trash icon [FAQ p. 3] ("You do not have to pay such a cost on a card"
  [Main p. 20]) -- offers no refusal, does not hold ``finish_reveal`` back and
  lapses when the Reveal ends; a mandatory one holds the end while it offers
  something.
- Every choice of a revealed card is queued whatever its condition, which is
  judged whenever its rows are asked (OQ-028); none has a ``requirement``.
- ``hook`` names a choice whose flow stays code in ``rules.reveal_turn``
  (``REVEAL_CHOICE_HOOKS``): one action pays a cost with its targets in one
  row, or the choice reaches outside its entry. As with the Agent boxes, a
  record lists its lines only when the DSL can say the whole choice.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.effects import (
    AcquireCardUpTo,
    CommandReached,
    CompletedContractsAtLeast,
    Condition,
    Cost,
    DeployFromGarrison,
    DeployTheseTroops,
    DrawIntrigueCards,
    EffectSection,
    FactionBond,
    Freighter,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    GrantCombatDeployment,
    HasAlliance,
    KeepPrintedReveal,
    LoseInfluence,
    LoseTroops,
    PayResources,
    PlaceNegotiator,
    PlaceSpy,
    PrintedRevealValue,
    RecallSpy,
    RecruitTroops,
    RetreatTroops,
    RevealPersuasion,
    RevealSwords,
    Reward,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TakeHighCouncilSeat,
    TechTilesAtLeast,
    TrashCard,
    TrashPersonalCard,
)
from dune_imperium.content.core.icons import Faction

_OPTIONAL = AbilityMark.OPTIONAL
_MANDATORY = AbilityMark.MANDATORY
_COMMAND = CommandReached()


def _line(
    *rewards: Reward, costs: tuple[Cost, ...] = (), condition: Condition | None = None
) -> EffectSection:
    return EffectSection(rewards=rewards, costs=costs, condition=condition)


def _choice(
    *lines: EffectSection,
    mark: AbilityMark,
    structure: AbilityStructure = AbilityStructure.SEQUENCE,
    hook: str | None = None,
) -> Ability:
    return Ability(
        timing=AbilityTiming.REVEAL,
        sections=lines,
        mark=mark,
        structure=structure,
        hook=hook,
    )


REVEAL_CHOICE_ABILITIES: Final[Mapping[str, Ability]] = (
    MappingProxyType(
        {
            # --- Optional: an arrow cost or a black trash icon -------------------
            # Spy Network: "If you have placed 2 or more Spies: You may recall a
            # Spy -> Draw 1 Intrigue card".
            "recall_spy_to_draw_intrigue_if_two_placed": _choice(
                _line(
                    DrawIntrigueCards(1),
                    costs=(RecallSpy(),),
                    condition=SpiesPlacedAtLeast(2),
                ),
                mark=_OPTIONAL,
            ),
            # In High Places: "You may recall 2 Spies -> +3 Persuasion" -- one
            # row names both posts.
            "may_recall_two_spies_for_three_persuasion": _choice(
                _line(RevealPersuasion(3), costs=(RecallSpy(2),)),
                mark=_OPTIONAL,
            ),
            # Captured Mentat: "You may lose 1 Influence with a chosen Faction ->
            # Gain 1 Influence with a chosen Faction" -- one row names both.
            "may_lose_influence_to_gain_influence": _choice(
                _line(GainInfluence(), costs=(LoseInfluence(1),)),
                mark=_OPTIONAL,
            ),
            # Spacing Guild's Favor: "You may pay 3 spice -> Gain 1 Influence with
            # a chosen Faction" -- one row names the Faction.
            "may_pay_three_spice_for_influence": _choice(
                _line(GainInfluence(), costs=(PayResources(spice=3),)),
                mark=_OPTIONAL,
            ),
            # Calculus of Power: "You may trash another Emperor card in play ->
            # +3 swords".
            "may_trash_other_emperor_for_three_strength": _choice(
                _line(
                    RevealSwords(3),
                    costs=(TrashCard(other_in_play=Faction.EMPEROR),),
                ),
                mark=_OPTIONAL,
            ),
            # Chani, Clever Tactician: "You may retreat 2 troops -> +4 swords".
            "may_retreat_two_troops_for_four_strength": _choice(
                _line(RevealSwords(4), costs=(RetreatTroops(2, 2),)),
                mark=_OPTIONAL,
            ),
            # Shrouded Counsel: "Command (6+ Persuasion): You may trash a card".
            "command_may_trash_card": _choice(
                _line(TrashPersonalCard(), condition=_COMMAND),
                mark=_OPTIONAL,
            ),
            # Command Center: "You may retreat 2 troops -> +2 Persuasion".
            "may_retreat_two_troops_for_two_persuasion": _choice(
                _line(RevealPersuasion(2), costs=(RetreatTroops(2, 2),)),
                mark=_OPTIONAL,
            ),
            # Disruption Tactics: "Trash this card -> Combat (deploy as though at
            # a Combat space)".
            "may_trash_self_for_combat_icon": _choice(
                _line(GrantCombatDeployment(), costs=(TrashCard(this_card=True),)),
                mark=_OPTIONAL,
            ),
            # Arrakis Observer: "You may recall a Spy -> +3 swords".
            "may_recall_spy_for_three_strength": _choice(
                _line(RevealSwords(3), costs=(RecallSpy(),)),
                mark=_OPTIONAL,
            ),
            # Engineered Miracle: "Command (6+ Persuasion): Trash this card ->
            # Acquire a card from the Imperium Row" (any cost; its purchase
            # pipeline lives in ``rules.acquisition``).
            "command_may_trash_self_to_acquire_row_card": _choice(
                mark=_OPTIONAL,
                hook="command_acquisition",
            ),
            # CHOAM Demands: "If you have completed 4+ contracts: Trash this card
            # -> Gain 1 Influence with each Faction".
            "may_trash_self_for_four_influence_if_four_contracts": _choice(
                _line(
                    *(GainInfluence(factions=(faction,)) for faction in Faction),
                    costs=(TrashCard(this_card=True),),
                    condition=CompletedContractsAtLeast(4),
                ),
                mark=_OPTIONAL,
            ),
            # Ixian Engineer (Rise of Ix): "If you have three or more Tech
            # tiles: Trash this card -> 1 Victory Point" [Steam app text] --
            # CHOAM Demands' shape, an optional arrow whose cost is the card's
            # own trash and whose condition is judged whenever its row is
            # asked (OQ-028).
            "may_trash_self_for_victory_point_if_three_tech_tiles": _choice(
                _line(
                    GainVictoryPoints(1),
                    costs=(TrashCard(this_card=True),),
                    condition=TechTilesAtLeast(3),
                ),
                mark=_OPTIONAL,
            ),
            # Ix-Guild Compact (Rise of Ix): two Tech Negotiation icons [Steam
            # app screen pieces; P0 face reading], each "you may take a troop
            # from your supply and place it on the Ix board" [Rise of Ix p. 4]:
            # each its own optional choice, so the first resolved, the second
            # waits as a plain icon (Covert Operation's two Spies' shape).
            "may_place_two_negotiators": _choice(
                _line(PlaceNegotiator(), PlaceNegotiator()), mark=_OPTIONAL
            ),
            "may_place_negotiator": _choice(
                _line(PlaceNegotiator()), mark=_OPTIONAL
            ),
            # Boundless Ambition (Rise of Ix promo): "Acquire a card that costs
            # [5] or less." [Steam app text] -- a Row or Reserve card, not
            # Foldspace (OQ-125). No "may": it holds the Reveal's end while a
            # card is in reach, and lapses with it when none is.
            "acquire_card_up_to_five": _choice(
                _line(AcquireCardUpTo(5)), mark=_MANDATORY
            ),
            # For Humanity: "Bene Gesserit Alliance: You may lose 2 Influence with
            # one Faction -> Gain 1 VP" -- a "?" Influence diamond with two red
            # chevrons; like gaining two, the steps are not split between
            # Factions [Main p. 20].
            "may_lose_influence_for_vp_if_bene_gesserit_alliance": _choice(
                _line(
                    GainVictoryPoints(1),
                    costs=(LoseInfluence(2, one_faction=True),),
                    condition=HasAlliance(Faction.BENE_GESSERIT),
                ),
                mark=_OPTIONAL,
            ),
            # Shadout Mapes: "You may deploy or retreat 1 troop" -- the card's
            # own permission to deploy, no Combat icon needed; a Commander is a
            # troop [Bloodlines p. 4].
            "may_deploy_or_retreat_one_troop": _choice(
                _line(DeployFromGarrison(1)),
                _line(RetreatTroops(1, 1)),
                mark=_OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            # Unswerving Loyalty: "Fremen Bond: You may deploy or retreat 1
            # troop".
            "may_deploy_or_retreat_one_troop_if_fremen_bond": _choice(
                _line(DeployFromGarrison(1), condition=FactionBond(Faction.FREMEN)),
                _line(RetreatTroops(1, 1), condition=FactionBond(Faction.FREMEN)),
                mark=_OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            # Gun Thopter (original game): "You may deploy a troop from your
            # garrison to the Conflict" -- the deploy line of Shadout Mapes'
            # choice alone; a Commander is a troop [Bloodlines p. 4].
            "may_deploy_one_troop": _choice(
                _line(DeployFromGarrison(1)), mark=_OPTIONAL
            ),
            # Opulence (original game): "[6 Solari] -> [1 Victory Point]" -- an
            # optional arrow ("You do not have to pay such a cost on a card"
            # [Main p. 20]), paid once [FAQ p. 3].
            "may_pay_six_solari_for_victory_point": _choice(
                _line(GainVictoryPoints(1), costs=(PayResources(solari=6),)),
                mark=_OPTIONAL,
            ),
            # Guild Ambassador (original game): "Spacing Guild Alliance: [3
            # spice] -> [1 Victory Point]" -- an optional arrow paid once, the
            # Alliance judged whenever its row is asked (OQ-028).
            "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance": (
                _choice(
                    _line(
                        GainVictoryPoints(1),
                        costs=(PayResources(spice=3),),
                        condition=HasAlliance(Faction.SPACING_GUILD),
                    ),
                    mark=_OPTIONAL,
                )
            ),
            # Gurney Halleck (original game): "[3 Solari] -> [2 troops], you may
            # deploy these troops to the Conflict" -- an optional arrow paid once;
            # in a Reveal turn the two recruits may deploy ("these troops" only,
            # no garrison share).
            "may_pay_three_solari_for_two_troops_and_deploy": _choice(
                _line(
                    RecruitTroops(2),
                    DeployTheseTroops(),
                    costs=(PayResources(solari=3),),
                ),
                mark=_OPTIONAL,
            ),
            # Sardaukar Legion (original game): "Deploy up to three troops from
            # your garrison to the Conflict" -- a count the owner picks, none
            # included ("up to" [FAQ p. 3]); troops only (a Commander's share
            # is for the combinations stage, P7).
            "may_deploy_up_to_three_troops": _choice(
                _line(DeployFromGarrison(3)), mark=_OPTIONAL
            ),
            # Scout (original game): "Retreat up to two of your troops" to the
            # garrison [DI p. 16], none included.
            "may_retreat_up_to_two_troops": _choice(
                _line(RetreatTroops(0, 2)), mark=_OPTIONAL
            ),
            # Chani (original game): "Retreat any number of your troops", none
            # included [FAQ p. 3].
            "may_retreat_any_number_of_troops": _choice(
                _line(RetreatTroops(0, None)), mark=_OPTIONAL
            ),
            # Duncan, Loyal Blade (original game promo): "Trash this card -> Deploy
            # or retreat any number of your troops from or to your garrison" --
            # the trash is the cost of either line and the owner names one
            # direction and a count, none included ("any number" [FAQ p. 3]);
            # troops only (a Commander is a troop [Bloodlines p. 4], OQ-115).
            "may_trash_self_to_move_any_number_of_troops": _choice(
                _line(
                    DeployFromGarrison(up_to=None), costs=(TrashCard(this_card=True),)
                ),
                _line(RetreatTroops(0, None), costs=(TrashCard(this_card=True),)),
                mark=_OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            # Guild Chief Administrator (Rise of Ix): the Freighter icon beside
            # its 1 Persuasion [Steam app screen pieces]: "Freighter 아이콘마다
            # Freighter를 둘 가운데 하나로 움직일 수 있다("may")" [Rise of Ix
            # p. 5] (rise-of-ix.md 5) -- an optional choice, its two rows
            # (up one space, recall), lapsing unused when the Reveal ends.
            "may_move_freighter": _choice(_line(Freighter()), mark=_OPTIONAL),
            # Negotiated Withdrawal (Rise of Ix): "Retreat three of your units
            # -> [Influence with any Faction]" [Steam app text and screen
            # pieces]: an optional arrow [FAQ p. 3] whose cost is exactly
            # three units, troops or dreadnoughts in any mix ("unit" -- 예,
            # rise-of-ix.md 6, [Rise of Ix p. 6]); one row names the mix and
            # the Faction, never a cube at the top (OQ-060, OQ-071).
            "may_retreat_three_units_for_influence": _choice(
                _line(GainInfluence(), costs=(RetreatTroops(3, 3, units=True),)),
                mark=_OPTIONAL,
            ),
            # Tleilaxu Surgeon: "You may lose 2 troops -> Generate 2 specimens"
            # (troops only, from either zone, OQ-053).
            "may_lose_two_troops_for_two_specimens": _choice(
                _line(GenerateSpecimens(2), costs=(LoseTroops(2, troops_only=True),)),
                mark=_OPTIONAL,
            ),
            # --- Mandatory: a Spy icon (OQ-057 (14)), a printed "-OR-", a gain ---
            # Public Spectacle, Wheels within Wheels (and Covert Operation's
            # second icon): "Place a Spy".
            "place_spy": _choice(_line(PlaceSpy()), mark=_MANDATORY),
            # Covert Operation: "Place 2 Spies", each icon on its own.
            "place_two_spies": _choice(
                _line(PlaceSpy()), _line(PlaceSpy()), mark=_MANDATORY
            ),
            # Intelligence Training: "Command (6+ Persuasion): Place a Spy".
            "command_place_spy": _choice(
                _line(PlaceSpy(), condition=_COMMAND), mark=_MANDATORY
            ),
            # Undercover Asset: "Choose one: Place a Spy / +2 swords".
            "place_spy_or_gain_two_strength": _choice(
                _line(PlaceSpy()),
                _line(RevealSwords(2)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Corrinth City: "Choose one: Gain 5 solari / Pay 5 solari -> Take the
            # High Council seat".
            "gain_five_solari_or_take_high_council": _choice(
                _line(GainResources(solari=5)),
                _line(TakeHighCouncilSeat(), costs=(PayResources(solari=5),)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Desert Power: "Choose one: Keep the Persuasion / If Maker Hooks: Pay
            # 1 water -> Summon and deploy a sandworm" -- the printed Persuasion
            # is held from every total until chosen (OQ-069).
            "may_pay_water_for_sandworm": _choice(
                _line(KeepPrintedReveal(PrintedRevealValue.PERSUASION)),
                _line(
                    SummonSandworm(requires_maker_hooks=True),
                    costs=(PayResources(water=1),),
                ),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Priority Contracts, Delivery Agreement: "If you have completed 4 or
            # more Contracts: Choose one: Keep the spice / Trash this card -> Gain
            # 1 VP" -- the card's printed spice is paid only by this choice,
            # which always opens; the four Contracts are judged on the trash
            # line when it resolves (OQ-028 (b) addition).
            "keep_spice_or_trash_self_for_vp_if_four_contracts": _choice(
                _line(KeepPrintedReveal(PrintedRevealValue.SPICE)),
                _line(
                    GainVictoryPoints(1),
                    costs=(TrashCard(this_card=True),),
                    condition=CompletedContractsAtLeast(4),
                ),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Delivery Logistics: "Choose one: 1 Persuasion / Contract".
            "persuasion_or_contract": _choice(
                _line(RevealPersuasion(1)),
                _line(TakeContract(1)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Pointing the Way: "Command (6+ Persuasion): Gain 1 Influence with a
            # chosen Faction".
            "command_gain_chosen_influence": _choice(
                _line(GainInfluence(), condition=_COMMAND), mark=_MANDATORY
            ),
            # Bene Gesserit Sister (original game): "[2 Persuasion] -OR- [2
            # swords]" -- a printed -OR- the owner must settle ("-OR-" is a
            # must-pick-one choice, P0 sweep); the swords count once a unit
            # stands in the Conflict ("Conflict에 troop이 하나도 없으면 0"
            # [DI p. 11]).
            "choose_two_persuasion_or_two_strength": _choice(
                _line(RevealPersuasion(2)),
                _line(RevealSwords(2)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Ixian Ambassador: "If you have 2 or more Tech tiles: Gain 1
            # Influence with a chosen Faction".
            "gain_chosen_influence_if_two_tech": _choice(
                _line(GainInfluence(), condition=TechTilesAtLeast(2)),
                mark=_MANDATORY,
            ),
            # Web of Power (Rise of Ix): the wild Influence icon, "Choose a
            # Faction to gain 1 Influence with" [Steam app text] -- no "may"
            # and no condition, so Pointing the Way's choice without its
            # Command.
            "gain_chosen_influence": _choice(
                _line(GainInfluence()), mark=_MANDATORY
            ),
        }
    )
)


def reveal_choice_ability(effect: str) -> Ability:
    """The record of a Reveal choice."""

    return REVEAL_CHOICE_ABILITIES[effect]


def reveal_choice_is_optional(effect: str) -> bool:
    """Whether the owner may leave the Reveal choice unused (its record's
    mark)."""

    return REVEAL_CHOICE_ABILITIES[effect].mark is AbilityMark.OPTIONAL


# Uprising's Imperium cards' Reveal choices, by card id, in printed order
# (plan 8.3, step 4).
UPRISING_REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "calculus_of_power": (
            "may_trash_other_emperor_for_three_strength",
        ),
        "captured_mentat": (
            "may_lose_influence_to_gain_influence",
        ),
        "chani_clever_tactician": (
            "may_retreat_two_troops_for_four_strength",
        ),
        "corrinth_city": (
            "gain_five_solari_or_take_high_council",
        ),
        "covert_operation": (
            "place_two_spies",
        ),
        "delivery_agreement": (
            "keep_spice_or_trash_self_for_vp_if_four_contracts",
        ),
        "desert_power": (
            "may_pay_water_for_sandworm",
        ),
        "in_high_places": (
            "may_recall_two_spies_for_three_persuasion",
        ),
        "priority_contracts": (
            "keep_spice_or_trash_self_for_vp_if_four_contracts",
        ),
        "public_spectacle": (
            "place_spy",
        ),
        "spacing_guild_s_favor": (
            "may_pay_three_spice_for_influence",
        ),
        "spy_network": (
            "recall_spy_to_draw_intrigue_if_two_placed",
        ),
        "undercover_asset": (
            "place_spy_or_gain_two_strength",
        ),
        "unswerving_loyalty": (
            "may_deploy_or_retreat_one_troop_if_fremen_bond",
        ),
        "wheels_within_wheels": (
            "place_spy",
        ),
    }
)
