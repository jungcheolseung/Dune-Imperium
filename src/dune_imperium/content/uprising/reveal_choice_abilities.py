"""Reveal choices of personal cards as ability records (composed effects, A4d).

docs/composed-effects-plan.md 5 (A4d): a revealed card's choice effect -- what
the owner chooses during its Reveal turn, in any order beside its purchases
[Main p. 12] -- is written here, keyed by the card's
``reveal_choice_effects`` value. The printed text is
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

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    CommandReached,
    CompletedContractsAtLeast,
    Condition,
    Cost,
    DeployFromGarrison,
    DeployTheseTroops,
    DrawIntrigueCards,
    EffectSection,
    FactionBond,
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
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect

_CHOICE = PersonalCardRevealChoiceEffect
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


REVEAL_CHOICE_ABILITIES: Final[Mapping[PersonalCardRevealChoiceEffect, Ability]] = (
    MappingProxyType(
        {
            # --- Optional: an arrow cost or a black trash icon -------------------
            # Spy Network: "If you have placed 2 or more Spies: You may recall a
            # Spy -> Draw 1 Intrigue card".
            _CHOICE.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED: _choice(
                _line(
                    DrawIntrigueCards(1),
                    costs=(RecallSpy(),),
                    condition=SpiesPlacedAtLeast(2),
                ),
                mark=_OPTIONAL,
            ),
            # In High Places: "You may recall 2 Spies -> +3 Persuasion" -- one
            # row names both posts.
            _CHOICE.MAY_RECALL_TWO_SPIES_FOR_THREE_PERSUASION: _choice(
                _line(RevealPersuasion(3), costs=(RecallSpy(2),)),
                mark=_OPTIONAL,
            ),
            # Captured Mentat: "You may lose 1 Influence with a chosen Faction ->
            # Gain 1 Influence with a chosen Faction" -- one row names both.
            _CHOICE.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE: _choice(
                _line(GainInfluence(), costs=(LoseInfluence(1),)),
                mark=_OPTIONAL,
            ),
            # Spacing Guild's Favor: "You may pay 3 spice -> Gain 1 Influence with
            # a chosen Faction" -- one row names the Faction.
            _CHOICE.MAY_PAY_THREE_SPICE_FOR_INFLUENCE: _choice(
                _line(GainInfluence(), costs=(PayResources(spice=3),)),
                mark=_OPTIONAL,
            ),
            # Calculus of Power: "You may trash another Emperor card in play ->
            # +3 swords".
            _CHOICE.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH: _choice(
                _line(
                    RevealSwords(3),
                    costs=(TrashCard(other_in_play=Faction.EMPEROR),),
                ),
                mark=_OPTIONAL,
            ),
            # Chani, Clever Tactician: "You may retreat 2 troops -> +4 swords".
            _CHOICE.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH: _choice(
                _line(RevealSwords(4), costs=(RetreatTroops(2, 2),)),
                mark=_OPTIONAL,
            ),
            # Shrouded Counsel: "Command (6+ Persuasion): You may trash a card".
            _CHOICE.COMMAND_MAY_TRASH_CARD: _choice(
                _line(TrashPersonalCard(), condition=_COMMAND),
                mark=_OPTIONAL,
            ),
            # Command Center: "You may retreat 2 troops -> +2 Persuasion".
            _CHOICE.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION: _choice(
                _line(RevealPersuasion(2), costs=(RetreatTroops(2, 2),)),
                mark=_OPTIONAL,
            ),
            # Disruption Tactics: "Trash this card -> Combat (deploy as though at
            # a Combat space)".
            _CHOICE.MAY_TRASH_SELF_FOR_COMBAT_ICON: _choice(
                _line(GrantCombatDeployment(), costs=(TrashCard(this_card=True),)),
                mark=_OPTIONAL,
            ),
            # Arrakis Observer: "You may recall a Spy -> +3 swords".
            _CHOICE.MAY_RECALL_SPY_FOR_THREE_STRENGTH: _choice(
                _line(RevealSwords(3), costs=(RecallSpy(),)),
                mark=_OPTIONAL,
            ),
            # Engineered Miracle: "Command (6+ Persuasion): Trash this card ->
            # Acquire a card from the Imperium Row" (any cost; its purchase
            # pipeline lives in ``rules.acquisition``).
            _CHOICE.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD: _choice(
                mark=_OPTIONAL,
                hook="command_acquisition",
            ),
            # CHOAM Demands: "If you have completed 4+ contracts: Trash this card
            # -> Gain 1 Influence with each Faction".
            _CHOICE.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS: _choice(
                _line(
                    *(GainInfluence(factions=(faction,)) for faction in Faction),
                    costs=(TrashCard(this_card=True),),
                    condition=CompletedContractsAtLeast(4),
                ),
                mark=_OPTIONAL,
            ),
            # For Humanity: "Bene Gesserit Alliance: You may lose 2 Influence with
            # one Faction -> Gain 1 VP" -- a "?" Influence diamond with two red
            # chevrons; like gaining two, the steps are not split between
            # Factions [Main p. 20].
            _CHOICE.MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE: _choice(
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
            _CHOICE.MAY_DEPLOY_OR_RETREAT_ONE_TROOP: _choice(
                _line(DeployFromGarrison(1)),
                _line(RetreatTroops(1, 1)),
                mark=_OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            # Unswerving Loyalty: "Fremen Bond: You may deploy or retreat 1
            # troop".
            _CHOICE.MAY_DEPLOY_OR_RETREAT_ONE_TROOP_IF_FREMEN_BOND: _choice(
                _line(DeployFromGarrison(1), condition=FactionBond(Faction.FREMEN)),
                _line(RetreatTroops(1, 1), condition=FactionBond(Faction.FREMEN)),
                mark=_OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            # Gun Thopter (original game): "You may deploy a troop from your
            # garrison to the Conflict" -- the deploy line of Shadout Mapes'
            # choice alone; a Commander is a troop [Bloodlines p. 4].
            _CHOICE.MAY_DEPLOY_ONE_TROOP: _choice(
                _line(DeployFromGarrison(1)), mark=_OPTIONAL
            ),
            # Opulence (original game): "[6 Solari] -> [1 Victory Point]" -- an
            # optional arrow ("You do not have to pay such a cost on a card"
            # [Main p. 20]), paid once [FAQ p. 3].
            _CHOICE.MAY_PAY_SIX_SOLARI_FOR_VICTORY_POINT: _choice(
                _line(GainVictoryPoints(1), costs=(PayResources(solari=6),)),
                mark=_OPTIONAL,
            ),
            # Guild Ambassador (original game): "Spacing Guild Alliance: [3
            # spice] -> [1 Victory Point]" -- an optional arrow paid once, the
            # Alliance judged whenever its row is asked (OQ-028).
            _CHOICE.MAY_PAY_THREE_SPICE_FOR_VICTORY_POINT_IF_SPACING_GUILD_ALLIANCE: (
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
            _CHOICE.MAY_PAY_THREE_SOLARI_FOR_TWO_TROOPS_AND_DEPLOY: _choice(
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
            _CHOICE.MAY_DEPLOY_UP_TO_THREE_TROOPS: _choice(
                _line(DeployFromGarrison(3)), mark=_OPTIONAL
            ),
            # Tleilaxu Surgeon: "You may lose 2 troops -> Generate 2 specimens"
            # (troops only, from either zone, OQ-053).
            _CHOICE.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS: _choice(
                _line(GenerateSpecimens(2), costs=(LoseTroops(2, troops_only=True),)),
                mark=_OPTIONAL,
            ),
            # --- Mandatory: a Spy icon (OQ-057 (14)), a printed "-OR-", a gain ---
            # Public Spectacle, Wheels within Wheels (and Covert Operation's
            # second icon): "Place a Spy".
            _CHOICE.PLACE_SPY: _choice(_line(PlaceSpy()), mark=_MANDATORY),
            # Covert Operation: "Place 2 Spies", each icon on its own.
            _CHOICE.PLACE_TWO_SPIES: _choice(
                _line(PlaceSpy()), _line(PlaceSpy()), mark=_MANDATORY
            ),
            # Intelligence Training: "Command (6+ Persuasion): Place a Spy".
            _CHOICE.COMMAND_PLACE_SPY: _choice(
                _line(PlaceSpy(), condition=_COMMAND), mark=_MANDATORY
            ),
            # Undercover Asset: "Choose one: Place a Spy / +2 swords".
            _CHOICE.PLACE_SPY_OR_GAIN_TWO_STRENGTH: _choice(
                _line(PlaceSpy()),
                _line(RevealSwords(2)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Corrinth City: "Choose one: Gain 5 solari / Pay 5 solari -> Take the
            # High Council seat".
            _CHOICE.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL: _choice(
                _line(GainResources(solari=5)),
                _line(TakeHighCouncilSeat(), costs=(PayResources(solari=5),)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Desert Power: "Choose one: Keep the Persuasion / If Maker Hooks: Pay
            # 1 water -> Summon and deploy a sandworm" -- the printed Persuasion
            # is held from every total until chosen (OQ-069).
            _CHOICE.MAY_PAY_WATER_FOR_SANDWORM: _choice(
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
            _CHOICE.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS: _choice(
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
            _CHOICE.PERSUASION_OR_CONTRACT: _choice(
                _line(RevealPersuasion(1)),
                _line(TakeContract(1)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Pointing the Way: "Command (6+ Persuasion): Gain 1 Influence with a
            # chosen Faction".
            _CHOICE.COMMAND_GAIN_CHOSEN_INFLUENCE: _choice(
                _line(GainInfluence(), condition=_COMMAND), mark=_MANDATORY
            ),
            # Bene Gesserit Sister (original game): "[2 Persuasion] -OR- [2
            # swords]" -- a printed -OR- the owner must settle ("-OR-" is a
            # must-pick-one choice, P0 sweep); the swords count once a unit
            # stands in the Conflict ("Conflict에 troop이 하나도 없으면 0"
            # [DI p. 11]).
            _CHOICE.CHOOSE_TWO_PERSUASION_OR_TWO_STRENGTH: _choice(
                _line(RevealPersuasion(2)),
                _line(RevealSwords(2)),
                mark=_MANDATORY,
                structure=AbilityStructure.ONE_OF,
            ),
            # Ixian Ambassador: "If you have 2 or more Tech tiles: Gain 1
            # Influence with a chosen Faction".
            _CHOICE.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH: _choice(
                _line(GainInfluence(), condition=TechTilesAtLeast(2)),
                mark=_MANDATORY,
            ),
        }
    )
)


def reveal_choice_ability(effect: PersonalCardRevealChoiceEffect) -> Ability:
    """The record of a Reveal choice."""

    return REVEAL_CHOICE_ABILITIES[effect]


def reveal_choice_is_optional(effect: PersonalCardRevealChoiceEffect) -> bool:
    """Whether the owner may leave the Reveal choice unused (its record's
    mark)."""

    return REVEAL_CHOICE_ABILITIES[effect].mark is AbilityMark.OPTIONAL
