"""The Leaders' Signet Ring abilities as ability records (composed effects, A6c).

docs/composed-effects-plan.md 5 (A6c): each Leader face prints a Signet Ring
ability, used when its owner plays the Signet Ring starting card on an Agent
turn [Main pp. 6, 20] -- the card's Agent box -- or through Servo-Receivers'
acquire icon (OQ-062). Keyed by Leader face (Lady Jessica's two faces print
different ones); Steersman Y'rkoon prints none (Plot Course stands in its
place, and he has no Signet Ring card). ``rules.leader_abilities`` resolves
the ones with nothing to choose from their lines in either host (one
``leader_signet_resolved`` event), reads Spice Agony's and Water of Life's
payment and Arrakis Informant's posts off theirs, and keeps the others as
code under the hooks it registers (``SIGNET_HOOKS``), lines listed only
where the DSL says the whole ability. Fill Coffers' two lines are icons
resolved one action each in the Signet Ring's box (OQ-027, OQ-028). The
printed text is ``display/leaders.py``.
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
    AllConditions,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainResources,
    HasAlliance,
    InfluenceAtLeast,
    PayResources,
    PlaceSpy,
    RecruitTroops,
    RecruitUndeployableTroops,
    TroopToMemory,
    VisitedSpaceHasIcon,
)
from dune_imperium.content.uprising.types import AgentIcon


def _automatic(*lines: EffectSection) -> Ability:
    """A Signet with nothing to choose: every applicable line, at once."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX, sections=lines, mark=AbilityMark.AUTOMATIC
    )


def _hook(hook: str, mark: AbilityMark, *lines: EffectSection) -> Ability:
    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=lines,
        mark=mark,
        structure=(
            AbilityStructure.ONE_OF if len(lines) > 1 else AbilityStructure.SEQUENCE
        ),
        hook=hook,
    )


SIGNET_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Warmaster: "Recruit 1 troop" (FAQ p. 4: deployable from a Combat
        # space).
        "gurney_halleck": _automatic(EffectSection(rewards=(RecruitTroops(1),))),
        # Fill Coffers: "[1 Solari] -AND- If you have an Alliance: [1
        # spice]"; the spice waits for an Alliance formed later in the turn
        # (OQ-028, OQ-057 (1)).
        "lady_amber_metulli": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(rewards=(GainResources(solari=1),)),
                EffectSection(
                    rewards=(GainResources(spice=1),), condition=HasAlliance()
                ),
            ),
            mark=AbilityMark.AUTOMATIC,
            structure=AbilityStructure.SEPARATE,
            icons=("solari", "spice"),
        ),
        # Personal Training: advance the Feyd token on the Training track and
        # earn the new space (OQ-017).
        "feyd_rautha_harkonnen": _hook("personal_training", AbilityMark.MANDATORY),
        # Spice Agony: "Pay 1 spice -> Draw 1 Intrigue card and move 1 troop
        # from your supply to the Bene Gesserit board area as a memory".
        "lady_jessica": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(DrawIntrigueCards(1), TroopToMemory()),
                    costs=(PayResources(spice=1),),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Water of Life: "Pay 1 spice -> Gain 1 water".
        "reverend_mother_jessica": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainResources(water=1),), costs=(PayResources(spice=1),)
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Arrakis Informant: a Spy on a post connected to a City board space,
        # recall-first without a Spy in supply (OQ-057 (14)).
        "lady_margot_fenring": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(rewards=(PlaceSpy(agent_icons=(AgentIcon.CITY,)),)),
            ),
        ),
        # Lead the Way: "Draw 1 card".
        "muad_dib": _automatic(EffectSection(rewards=(DrawPersonalCards(1),))),
        # Chronicler's Insight: "You may choose one: Acquire a card that
        # costs 1 to your hand -or- Trash a card from your hand; if it costs
        # 1 or more, Gain 2 spice" -- no piece pays by the trashed card's
        # cost.
        "princess_irulan": _hook("chroniclers_insight", AbilityMark.OPTIONAL),
        # Unseen Network: a Spy anywhere, then a payment chosen by the post
        # it connects to.
        "staban_tuek": _hook("unseen_network", AbilityMark.MANDATORY),
        # Emperor of the Known Universe: "Units can't be deployed to the
        # Conflict this turn", then a choice (OQ-060, OQ-071).
        "shaddam_corrino_iv": _hook(
            "emperor_of_the_known_universe", AbilityMark.MANDATORY
        ),
        # Fedaykin Maneuver: "Retreat any number of your troops -or- with 2
        # Fremen Influence: pay 1 water -> Draw 2 cards" [FAQ p. 3].
        "chani": _hook("fedaykin_maneuver", AbilityMark.OPTIONAL),
        # Corrino Liaison: "You may trash a card in your play area -or- place
        # a Spy with Deep Cover on an Emperor observation post".
        "count_hasimir_fenring": _hook("corrino_liaison", AbilityMark.OPTIONAL),
        # Into the Fray: the Agent sent this turn into the Conflict as a unit
        # (OQ-037).
        "duncan_idaho": _hook("into_the_fray", AbilityMark.OPTIONAL),
        # Smuggle Spice: "Place 1 bonus spice on Tuek's Sietch -or- take 1
        # bonus spice from a Maker board space".
        "esmar_tuek": _hook("esmar_smuggle_spice", AbilityMark.MANDATORY),
        # Listeners: "Place a Spy on a Landsraad observation post -or- pay 1
        # spice -> Place a Spy"; one recall-first serves either half.
        "gaius_helen_mohiam": _hook(
            "listeners",
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(PlaceSpy(agent_icons=(AgentIcon.LANDSRAAD,)),)),
            EffectSection(rewards=(PlaceSpy(),), costs=(PayResources(spice=1),)),
        ),
        # Harkonnen Advisor: "Recruit 1 troop; you can't deploy this troop to
        # the Conflict this turn" (OQ-038).
        "piter_de_vries": _automatic(
            EffectSection(rewards=(RecruitUndeployableTroops(1),))
        ),
        # Judge of the Change: by the space visited this turn (none through
        # Servo-Receivers outside an Agent turn, OQ-062).
        "liet_kynes": _automatic(
            EffectSection(
                rewards=(GainResources(water=1),),
                condition=AllConditions(
                    (
                        VisitedSpaceHasIcon(AgentIcon.LANDSRAAD),
                        InfluenceAtLeast(Faction.EMPEROR, 2),
                    )
                ),
            ),
            EffectSection(
                rewards=(GainResources(solari=1),),
                condition=VisitedSpaceHasIcon(AgentIcon.CITY),
            ),
            EffectSection(
                rewards=(GainResources(spice=1),),
                condition=VisitedSpaceHasIcon(AgentIcon.SPICE_TRADE),
            ),
        ),
        # Reverse Engineering: "Gain 1 spice -or- trash one of your Tech tiles
        # -> Draw 1 Intrigue card, Draw 1 card" (OQ-106).
        "kota_odax_of_ix": _hook("reverse_engineering", AbilityMark.MANDATORY),
    }
)


def signet_ability(face_id: str | None) -> Ability | None:
    """The Signet Ring ability a Leader face prints, if any."""

    return None if face_id is None else SIGNET_ABILITIES.get(face_id)
