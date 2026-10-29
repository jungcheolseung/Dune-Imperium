"""Conflict cards' reward rows as ability records (composed effects, A5b).

docs/composed-effects-plan.md 5 (A5b): each Conflict card's three reward rows
(first, second, third place) are written here, keyed by the card's id. A row's
first line is what it gives -- resources, troops, Intrigue cards, Spies,
Contracts, trashes, VP, chosen and fixed Influence, control of a space -- and
each optional arrow ("3 spice -> 1 VP") is a line of its own.
The payer (``rules.combat``, one row per icon since stage B2, OQ-112), the
card definition (``ConflictDefinition.reward_rows``), the codec and the card
text (``display/structs.conflict_reward_text``) read these rows; the compiled
``ConflictReward`` copy is gone since the reward totals cleanup (2026-10-21),
and ``conflicts.check_conflict_reward_row`` checks each row instead.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.imperium.conflict_abilities import (
    IMPERIUM_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.rise_of_ix.conflict_abilities import (
    IX_CONFLICT_REWARD_ABILITIES,
)
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    Cost,
    DrawIntrigueCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    Reward,
    TakeContract,
    TakeControl,
    TrashPersonalCard,
)


def _line(*rewards: Reward) -> EffectSection:
    return EffectSection(rewards=rewards)


def _arrow(cost: Cost, victory_points: int) -> EffectSection:
    """An optional "cost -> VP" arrow [FAQ p. 3]."""

    return EffectSection(rewards=(GainVictoryPoints(victory_points),), costs=(cost,))


def _row(*lines: EffectSection) -> Ability:
    return Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=lines)


CONFLICT_REWARD_ABILITIES: Final[Mapping[str, tuple[Ability, Ability, Ability]]] = (
    MappingProxyType(
        {
            # The original game's cards share the table (one id, one
            # printing; docs/base-game-and-ix-plan.md 4.2 item 7).
            **IMPERIUM_CONFLICT_REWARD_ABILITIES,
            # Rise of Ix's three (``content.rise_of_ix.conflict_abilities``).
            **IX_CONFLICT_REWARD_ABILITIES,
            # Skirmish (Crysknife).
            "skirmish_crysknife": (
                _row(_line(GainInfluence())),
                _row(_line(GainResources(spice=1), DrawIntrigueCards(1))),
                _row(_line(GainResources(spice=1))),
            ),
            # Skirmish (Ornithopter).
            "skirmish_ornithopter": (
                _row(_line(GainResources(solari=1), DrawIntrigueCards(1))),
                _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
                _row(_line(DrawIntrigueCards(1))),
            ),
            # Skirmish (Desert Mouse).
            "skirmish_desert_mouse": (
                _row(_line(GainResources(solari=2))),
                _row(_line(GainResources(solari=3))),
                _row(_line(GainResources(solari=2))),
            ),
            # CHOAM Security.
            "choam_security": (
                _row(
                    _line(
                        RecruitTroops(1),
                        TakeContract(1),
                        GainInfluence(factions=(Faction.SPACING_GUILD,)),
                    )
                ),
                _row(_line(GainResources(solari=2, water=1), RecruitTroops(2))),
                _row(_line(DrawIntrigueCards(1), RecruitTroops(1))),
            ),
            # Spice Freighters.
            "spice_freighters": (
                _row(_line(GainInfluence()), _arrow(PayResources(spice=3), 1)),
                _row(_line(GainResources(spice=1, water=1), RecruitTroops(1))),
                _row(_line(GainResources(spice=1), RecruitTroops(1))),
            ),
            # Siege of Arrakeen.
            "siege_of_arrakeen": (
                _row(
                    _line(
                        GainResources(solari=2),
                        RecruitTroops(2),
                        TakeControl("arrakeen"),
                    )
                ),
                _row(_line(GainResources(solari=4), RecruitTroops(1))),
                _row(_line(GainResources(solari=3))),
            ),
            # Seize Spice Refinery.
            "seize_spice_refinery": (
                _row(
                    _line(
                        GainResources(spice=2),
                        PlaceSpy(),
                        TakeControl("spice_refinery"),
                    )
                ),
                _row(
                    _line(
                        GainResources(spice=1), DrawIntrigueCards(1), RecruitTroops(1)
                    )
                ),
                _row(_line(GainResources(spice=2))),
            ),
            # Test of Loyalty.
            "test_of_loyalty": (
                _row(
                    _line(
                        GainResources(solari=2),
                        PlaceSpy(),
                        GainInfluence(factions=(Faction.EMPEROR,)),
                    )
                ),
                _row(_line(GainResources(solari=4), RecruitTroops(1))),
                _row(_line(GainResources(solari=3))),
            ),
            # Shadow Contest.
            "shadow_contest": (
                _row(
                    _line(
                        DrawIntrigueCards(1),
                        GainInfluence(factions=(Faction.BENE_GESSERIT,)),
                    )
                ),
                _row(
                    _line(
                        GainResources(spice=1), DrawIntrigueCards(1), RecruitTroops(1)
                    )
                ),
                _row(_line(GainResources(spice=1), RecruitTroops(1))),
            ),
            # Secure Imperial Basin.
            "secure_imperial_basin": (
                _row(
                    _line(
                        GainResources(spice=2),
                        RecruitTroops(1),
                        TakeControl("imperial_basin"),
                    )
                ),
                _row(_line(GainResources(water=2), RecruitTroops(1))),
                _row(_line(GainResources(water=1), RecruitTroops(1))),
            ),
            # Protect the Sietches.
            "protect_the_sietches": (
                _row(
                    _line(
                        GainResources(water=1),
                        RecruitTroops(1),
                        GainInfluence(factions=(Faction.FREMEN,)),
                    )
                ),
                _row(_line(GainResources(spice=3), RecruitTroops(1))),
                _row(_line(GainResources(spice=2))),
            ),
            # Trade Dispute.
            "trade_dispute": (
                _row(
                    _line(GainResources(water=1), TakeContract(1), TrashPersonalCard())
                ),
                _row(_line(GainResources(spice=1, water=1), TrashPersonalCard())),
                _row(_line(GainResources(water=1), RecruitTroops(1))),
            ),
            # Propaganda.
            "propaganda": (
                _row(_line(GainInfluence(times=2, distinct=True))),
                _row(_line(GainResources(spice=3), DrawIntrigueCards(1))),
                _row(_line(GainResources(spice=3))),
            ),
            # Battle for Imperial Basin.
            "battle_for_imperial_basin": (
                _row(
                    _line(GainVictoryPoints(1), TakeControl("imperial_basin")),
                    _arrow(PayResources(spice=4), 1),
                ),
                _row(_line(GainResources(spice=5))),
                _row(_line(GainResources(spice=3))),
            ),
            # Battle for Arrakeen.
            "battle_for_arrakeen": (
                _row(
                    _line(GainVictoryPoints(1), TakeControl("arrakeen")),
                    _arrow(RecallSpy(2), 1),
                ),
                _row(_line(GainResources(solari=3, spice=1), DrawIntrigueCards(1))),
                _row(_line(GainResources(solari=2, spice=2))),
            ),
            # Battle for Spice Refinery.
            "battle_for_spice_refinery": (
                _row(
                    _line(GainVictoryPoints(1), TakeControl("spice_refinery")),
                    _arrow(PayResources(solari=6), 1),
                ),
                _row(_line(GainResources(spice=3), DrawIntrigueCards(1))),
                _row(_line(GainResources(spice=3))),
            ),
            # Skirmish (Wild).
            "skirmish_wild": (
                _row(_line(TrashPersonalCard())),
                _row(_line(GainResources(solari=1, water=1))),
                _row(_line(GainResources(solari=2))),
            ),
            # Storms in the South. The first place prints a gold Spy behind a grey
            # one: a Spy with Deep Cover, as on Deliver Supplies [Storms in the
            # South card] [Bloodlines p. 5].
            "storms_in_the_south": (
                _row(_line(GainResources(spice=2), PlaceSpy(shared_post=True))),
                _row(_line(GainResources(solari=2), DrawIntrigueCards(2))),
                _row(_line(GainResources(solari=2), DrawIntrigueCards(1))),
            ),
            # Economic Supremacy.
            "economic_supremacy": (
                _row(
                    _line(GainVictoryPoints(1)),
                    _arrow(PayResources(solari=6), 1),
                    _arrow(PayResources(spice=4), 1),
                ),
                _row(_line(GainVictoryPoints(1))),
                _row(_line(GainResources(solari=2, spice=2))),
            ),
        }
    )
)
