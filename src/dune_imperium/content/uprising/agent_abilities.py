"""Agent-box ability records of personal cards (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2): the personal cards whose Agent box is
a plain or conditional gain are written as ability records here and resolved
by ``rules.agent_box_abilities``; the card keeps its ``agent_effect`` value,
which names the record. The printed text is ``display/tokens.py``.

- ``requirement`` is a condition fixed by the placement -- the visited space
  is a Maker space, a Faction Bond among the cards already in play (it can
  only shrink) -- and is judged when the card is played: when it fails the
  box is never pending (OQ-028 (a)).
- A line's ``condition`` is judged when the box resolves, in the owner's
  order (OQ-028); while it fails the box waits and the turn's end fizzles it
  (OQ-057 (1)). A Bond box judges its Bond both ways: a trash in the same
  turn can break it.
- ``icons`` marks a box whose printed icons resolve one action each
  (OQ-027 card Agent box extensions); the others resolve as one action.

The boxes not here keep their own code in ``rules.agent_effects`` until a
later stage moves them (plan 5).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AtMakerSpace,
    BoostNextBeneGesseritCard,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    GainedSpiceThisTurn,
    GainResources,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    RecruitTroops,
    Research,
    ReturnThisCardToHand,
    Reward,
    SandwormsInConflictAtLeast,
    SpyRecalledThisTurn,
    TakeContract,
    TrashPersonalCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.uprising.types import PersonalCardAgentEffect

_BOX = PersonalCardAgentEffect
_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_BG_TWO = InfluenceAtLeast(_BG, 2)
_TWO_SPICE = GainedSpiceThisTurn(2)


def _line(*rewards: Reward, condition: Condition | None = None) -> EffectSection:
    return EffectSection(rewards=rewards, condition=condition)


def _box(
    *rewards: Reward,
    condition: Condition | None = None,
    requirement: Condition | None = None,
) -> Ability:
    """A box resolved as one action: its rewards on one line."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(_line(*rewards, condition=condition),),
        requirement=requirement,
    )


def _icons(*lines: tuple[str, EffectSection]) -> Ability:
    """A box whose printed icons resolve one action each (OQ-027)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=tuple(section for _, section in lines),
        structure=AbilityStructure.SEPARATE,
        icons=tuple(key for key, _ in lines),
    )


AGENT_BOX_ABILITIES: Final[Mapping[PersonalCardAgentEffect, Ability]] = (
    MappingProxyType(
        {
            # --- One action: gains -------------------------------------------
            _BOX.GAIN_TWO_SOLARI: _box(GainResources(solari=2)),
            _BOX.GAIN_ONE_SPICE: _box(GainResources(spice=1)),
            _BOX.GAIN_WATER: _box(GainResources(water=1)),
            _BOX.RECRUIT_TWO_TROOPS: _box(RecruitTroops(2)),
            _BOX.BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND: _box(
                BoostNextBeneGesseritCard()
            ),
            _BOX.GAIN_SPICE_IF_MAKER_SPACE: _box(
                GainResources(spice=1), requirement=AtMakerSpace()
            ),
            _BOX.GAIN_TWO_SPICE_IF_MAKER_SPACE: _box(
                GainResources(spice=2), requirement=AtMakerSpace()
            ),
            _BOX.RECRUIT_ONE_IF_MAKER_SPACE: _box(
                RecruitTroops(1), requirement=AtMakerSpace()
            ),
            _BOX.RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO: _box(
                RecruitTroops(1), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
            ),
            _BOX.RECRUIT_TWO_IF_BENE_GESSERIT_BOND: _box(
                RecruitTroops(2), condition=_BG_BOND, requirement=_BG_BOND
            ),
            _BOX.RETURN_SELF_IF_BENE_GESSERIT_BOND: _box(
                ReturnThisCardToHand(), condition=_BG_BOND, requirement=_BG_BOND
            ),
            _BOX.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN: _box(
                RecruitTroops(3), condition=SpyRecalledThisTurn()
            ),
            _BOX.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN: _box(
                RecruitTroops(2), condition=SpyRecalledThisTurn()
            ),
            _BOX.GAIN_TWO_SPICE_IF_GRAFTED: _box(
                GainResources(spice=2), condition=Grafted()
            ),
            _BOX.GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO: _box(
                GainResources(spice=2), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
            ),
            # Throne Room Politics: the troop, then the black trash icon on a
            # frame of its own [Main p. 20].
            _BOX.RECRUIT_ONE_AND_MAY_TRASH: _box(RecruitTroops(1), TrashPersonalCard()),
            # --- One action: card draws ----------------------------------------
            _BOX.DRAW_PERSONAL_CARD: _box(DrawPersonalCards(1)),
            _BOX.DRAW_TWO_CARDS: _box(DrawPersonalCards(2)),
            _BOX.DRAW_PER_SANDWORM_IN_CONFLICT: _box(
                DrawPerSandwormInConflict(), condition=SandwormsInConflictAtLeast(1)
            ),
            _BOX.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: _box(
                DrawPersonalCards(1), condition=_BG_TWO
            ),
            _BOX.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: _box(
                DrawPersonalCards(1), condition=_TWO_SPICE
            ),
            _BOX.DRAW_TWO_IF_ONE_MARKER: _box(
                DrawPersonalCards(2), condition=GeneticMarkersAtLeast(1)
            ),
            # --- One action: Intrigue draws ------------------------------------
            _BOX.DRAW_INTRIGUE_CARD: _box(DrawIntrigueCards(1)),
            _BOX.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT: _box(
                DrawIntrigueCards(1), condition=SandwormsInConflictAtLeast(1)
            ),
            _BOX.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN: _box(
                DrawIntrigueCards(1), condition=ContractCompletedThisTurn()
            ),
            _BOX.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN: _box(
                DrawIntrigueCards(1), condition=SpyRecalledThisTurn()
            ),
            _BOX.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT: _box(
                DrawIntrigueCards(1), condition=UnitsInConflictAtLeast(3)
            ),
            # --- One action: a follow-up after the box ---------------------------
            _BOX.TAKE_CONTRACT: _box(TakeContract(1)),
            _BOX.TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN: _box(
                TakeContract(1), condition=SpyRecalledThisTurn()
            ),
            _BOX.RESEARCH: _box(Research()),
            _BOX.ADVANCE_TLEILAXU: _box(AdvanceTleilaxu(1)),
            _BOX.ADVANCE_TLEILAXU_IF_ONE_MARKER: _box(
                AdvanceTleilaxu(1), condition=GeneticMarkersAtLeast(1)
            ),
            _BOX.ADVANCE_TLEILAXU_IF_GRAFTED: _box(
                AdvanceTleilaxu(1), condition=Grafted()
            ),
            _BOX.GENERATE_SPECIMEN: _box(GenerateSpecimens(1)),
            _BOX.PEEK_TWO_INTRIGUE_KEEP_ONE: _box(LookAtIntrigueKeepOne(2)),
            # --- Icon by icon (OQ-027) -------------------------------------------
            # Hidden Missive.
            _BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: _icons(
                ("troops", _line(RecruitTroops(1), condition=_BG_TWO)),
                ("cards", _line(DrawPersonalCards(1), condition=_BG_TWO)),
            ),
            # Maker Keeper.
            _BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: _icons(
                ("water", _line(GainResources(water=1), condition=_BG_TWO)),
                (
                    "spice",
                    _line(
                        GainResources(spice=1),
                        condition=InfluenceAtLeast(Faction.FREMEN, 2),
                    ),
                ),
            ),
            # Wheels Within Wheels.
            _BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: _icons(
                (
                    "solari",
                    _line(
                        GainResources(solari=2),
                        condition=InfluenceAtLeast(Faction.EMPEROR, 2),
                    ),
                ),
                (
                    "spice",
                    _line(
                        GainResources(spice=1),
                        condition=InfluenceAtLeast(Faction.SPACING_GUILD, 2),
                    ),
                ),
            ),
            # Fremen War Name: "If you gained [2 spice] or more this turn:".
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: _icons(
                ("troops", _line(RecruitTroops(1), condition=_TWO_SPICE)),
                ("cards", _line(DrawPersonalCards(1), condition=_TWO_SPICE)),
            ),
            # Tleilaxu Infiltrator (its "Enemy Agents don't block your Agent
            # this turn" is a placement rule, ``agent_turn``).
            _BOX.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                (
                    "intrigue",
                    _line(DrawIntrigueCards(1), condition=GeneticMarkersAtLeast(2)),
                ),
            ),
            # Sardaukar Quartermaster: "If grafted: troop, draw a card".
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED: _icons(
                ("troops", _line(RecruitTroops(1), condition=Grafted())),
                ("cards", _line(DrawPersonalCards(1), condition=Grafted())),
            ),
            # Cargo Runner: two printed lines, two and four completed Contracts.
            _BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO: _icons(
                (
                    "cards",
                    _line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(2)),
                ),
                (
                    "cards_second",
                    _line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(4)),
                ),
            ),
            # Industrial Espionage: "[draw 1]" and, on its own line, "If
            # grafted: [Research] [specimen]".
            _BOX.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                (
                    "research",
                    _line(Research(), GenerateSpecimens(1), condition=Grafted()),
                ),
            ),
            # Stillsuit Manufacturer: "[water] —AND— [Fremen] Alliance: Return
            # this card from play to your hand."
            _BOX.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE: _icons(
                ("water", _line(GainResources(water=1))),
                (
                    "return_self",
                    _line(
                        ReturnThisCardToHand(),
                        condition=HasAlliance(Faction.FREMEN),
                    ),
                ),
            ),
        }
    )
)


def agent_box_ability(effect: PersonalCardAgentEffect | None) -> Ability | None:
    """The record of ``effect``'s Agent box; None while its own code resolves it."""

    if effect is None:
        return None
    return AGENT_BOX_ABILITIES.get(effect)
