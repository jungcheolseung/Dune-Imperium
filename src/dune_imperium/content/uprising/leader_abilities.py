"""The Leaders' printed abilities as ability records (composed effects, A6c, A6e).

docs/composed-effects-plan.md 5 (A6c): each Leader face prints a Signet Ring
ability, used when its owner plays the Signet Ring starting card on an Agent
turn [Main pp. 6, 20] -- the card's Agent box -- or through Servo-Receivers'
acquire icon (OQ-062). Keyed by Leader face (Lady Jessica's two faces print
different ones); Steersman Y'rkoon prints none (Plot Course stands in its
place, and he has no Signet Ring card). ``rules.leader_abilities`` resolves
the ones with nothing to choose from their lines in either host (their
gains, then the box's ``leader_signet_resolved``), reads Spice Agony's and
Water of Life's payment and Arrakis Informant's posts off theirs, and keeps
the others as code under the hooks it registers (``SIGNET_HOOKS``), lines
listed only where the DSL says the whole ability. Fill Coffers' two lines are icons
resolved one action each in the Signet Ring's box (OQ-027, OQ-028).

Each face's left box is ``LEADER_ABILITIES`` (composed A6e), used "at the
time written on the card" [Main p. 6]: triggered abilities with a fixed
reward (the firing sites stay where they are and read the reward off the
record, so nothing is reordered), two automatic Reveal lines (judged after
every step until they first hold, OQ-020), the flows kept as code
(``rules.leader_abilities.LEADER_HOOKS``) and the rule changes in force
while the Leader plays (``STANDING`` records naming the engine branch). The
setup deviations stay ``LeaderDefinition`` fields. The printed text is
``display/leaders.py``.
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
    AcquireTech,
    AllConditions,
    DrawIntrigueCards,
    DrawPersonalCards,
    DrawTwistedIntrigueCards,
    EffectSection,
    GainInfluence,
    GainResources,
    HasAlliance,
    InfluenceAtLeast,
    OnAgentSentTo,
    OnBoardSpaceSolariPaid,
    OnCardTrashed,
    OnHighCouncilSeatTaken,
    OnMakerSpiceHarvested,
    OnOpponentAgentAtSpiedMakerSpace,
    OnReachInfluence,
    OnRoundStart,
    OnSpiceGainedInTurnAtLeast,
    PayResources,
    PlaceNegotiator,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RecruitUndeployableTroops,
    RetreatTroops,
    RevealPersuasion,
    RevealSwords,
    Reward,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    StrengthInConflictAtLeast,
    Trigger,
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
        "chani": _hook(
            "fedaykin_maneuver",
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(RetreatTroops(minimum=0),)),
            EffectSection(
                rewards=(DrawPersonalCards(2),),
                condition=InfluenceAtLeast(Faction.FREMEN, 2),
                costs=(PayResources(water=1),),
            ),
        ),
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
        # The original game's (docs/rules/imperium-base.md 12). Brutality:
        # one troop, or two with a Faction Alliance -- its "-OR-" is no
        # choice (two are never worse; the Steam app offers none, P0 sweep
        # L7), so the first line whose condition holds when it resolves is
        # paid (OQ-028).
        "glossu_rabban": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(rewards=(RecruitTroops(2),), condition=HasAlliance()),
                EffectSection(rewards=(RecruitTroops(1),)),
            ),
            mark=AbilityMark.AUTOMATIC,
            structure=AbilityStructure.ONE_OF,
        ),
        # Manufacturing: 1 Solari.
        "count_ilban_richese": _automatic(
            EffectSection(rewards=(GainResources(solari=1),))
        ),
        # Spice Hoard: 1 spice.
        "earl_memnon_thorvald": _automatic(
            EffectSection(rewards=(GainResources(spice=1),))
        ),
        # Hidden Reservoir: 1 water.
        "countess_ariana_thorvald": _automatic(
            EffectSection(rewards=(GainResources(water=1),))
        ),
        # Prudent Diplomacy (stage P2b): "spice 1 → 상대가 나보다 Influence가
        # 많은 진영에 Influence 1" -- an arrow, so never forced; the Faction is
        # judged as it resolves (OQ-028) and none at the top is offered
        # (OQ-060, P0 sweep L5).
        # Scheme (stage P2b): "1 Solari → Intrigue 1", an arrow, once per
        # play [FAQ p. 3] (docs/rules/imperium-base.md 12).
        "baron_vladimir_harkonnen": _hook(
            "scheme",
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(DrawIntrigueCards(1),), costs=(PayResources(solari=1),)
            ),
        ),
        # Discipline (stage P2b): draw a card.
        "paul_atreides": _automatic(EffectSection(rewards=(DrawPersonalCards(1),))),
        # Manipulate (stage P2b): set a Row card aside and refill the Row;
        # this round's Reveal turn may acquire it for 1 Persuasion less --
        # "Uprising Intrigue Manipulate와 같은 판정 [FAQ p. 3]".
        "helena_richese": _hook(
            "manipulate",
            AbilityMark.MANDATORY,
            EffectSection(rewards=(SetAsideImperiumRowCard(),)),
        ),
        "duke_leto_atreides": _hook(
            "prudent_diplomacy",
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(GainInfluence(where_opponent_leads=True),),
                costs=(PayResources(spice=1),),
            ),
        ),
        # Rise of Ix's (docs/rules/rise-of-ix.md 10; stage P4e). Final
        # Delivery: "7 Solari → Influence 1(골라)·troop 1·spice 1" -- an arrow,
        # so never forced; no Faction at the top is offered (OQ-060,
        # rise-of-ix.md 15).
        "princess_yuna_moritani": _hook(
            "final_delivery",
            AbilityMark.OPTIONAL,
            EffectSection(
                rewards=(GainInfluence(), RecruitTroops(1), GainResources(spice=1)),
                costs=(PayResources(solari=7),),
            ),
        ),
        # Ixian Technology: "Acquire Tech -OR- Tech Negotiation"
        # (rise-of-ix.md 10; the app prints the Negotiator first). Each half
        # is a "may" piece (rise-of-ix.md 4), so the box is optional; its
        # Acquire Tech prints no Tech Discount.
        "prince_rhombur_vernius": _hook(
            "ixian_technology",
            AbilityMark.OPTIONAL,
            EffectSection(rewards=(PlaceNegotiator(),)),
            EffectSection(rewards=(AcquireTech(discount=0),)),
        ),
    }
)


def signet_ability(face_id: str | None) -> Ability | None:
    """The Signet Ring ability a Leader face prints, if any."""

    return None if face_id is None else SIGNET_ABILITIES.get(face_id)


def _triggered(trigger: Trigger, reward: Reward) -> Ability:
    """A triggered ability with a fixed reward."""

    return Ability(
        timing=AbilityTiming.TRIGGERED,
        sections=(EffectSection(rewards=(reward,)),),
        mark=AbilityMark.AUTOMATIC,
        trigger=trigger,
    )


def _left_hook(
    timing: AbilityTiming, hook: str, mark: AbilityMark, *lines: EffectSection
) -> Ability:
    return Ability(timing=timing, sections=lines, mark=mark, hook=hook)


def _standing(hook: str) -> Ability:
    return _left_hook(AbilityTiming.STANDING, hook, AbilityMark.AUTOMATIC)


LEADER_ABILITIES: Final[Mapping[str, tuple[Ability, ...]]] = MappingProxyType(
    {
        # Devious Strength: "Reveal turn, once: Recall one of your placed Spies
        # -> Gain 2 swords" (its recall rows on the Reveal; cleanup-2d).
        "feyd_rautha_harkonnen": (
            Ability(
                timing=AbilityTiming.REVEAL,
                sections=(
                    EffectSection(rewards=(RevealSwords(2),), costs=(RecallSpy(),)),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
        ),
        # Always Smiling: "Reveal turn: If you have 6 or more strength in the
        # Conflict: Gain 1 Persuasion (4-player value)", never taken back
        # (OQ-020).
        "gurney_halleck": (
            Ability(
                timing=AbilityTiming.REVEAL,
                sections=(
                    EffectSection(
                        rewards=(RevealPersuasion(1),),
                        condition=StrengthInConflictAtLeast(6),
                    ),
                ),
                mark=AbilityMark.AUTOMATIC,
            ),
        ),
        # Desert Scouts: "Reveal turn: You may retreat one of your troops".
        "lady_amber_metulli": (
            Ability(
                timing=AbilityTiming.REVEAL,
                sections=(
                    EffectSection(rewards=(RetreatTroops(minimum=1, maximum=1),)),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
        ),
        # Other Memories: on a Bene Gesserit space, return the memories, draw
        # one card per memory and flip (OQ-018) [FAQ p. 3].
        "lady_jessica": (
            _left_hook(AbilityTiming.TRIGGERED, "other_memories", AbilityMark.OPTIONAL),
        ),
        # Reverend Mother: once a turn, 1 water to repeat a Bene Gesserit or
        # Fremen space's printed effect (OQ-019).
        "reverend_mother_jessica": (
            _left_hook(
                AbilityTiming.TRIGGERED, "reverend_mother", AbilityMark.OPTIONAL
            ),
        ),
        # Loyalty: "When you reach 2 Bene Gesserit Influence: Gain 2 spice".
        "lady_margot_fenring": (
            _triggered(
                OnReachInfluence(Faction.BENE_GESSERIT, 2), GainResources(spice=2)
            ),
        ),
        # Unpredictable Foe: "Reveal turn: If you have one or more sandworms in
        # the Conflict: Draw 1 Intrigue card" (OQ-045, OQ-106).
        "muad_dib": (
            Ability(
                timing=AbilityTiming.REVEAL,
                sections=(
                    EffectSection(
                        rewards=(DrawIntrigueCards(1),),
                        condition=SandwormsInConflictAtLeast(1),
                    ),
                ),
                mark=AbilityMark.AUTOMATIC,
            ),
        ),
        # Imperial Birthright: "When you reach 2 Emperor Influence: Draw 1
        # Intrigue card" (OQ-106).
        "princess_irulan": (
            _triggered(OnReachInfluence(Faction.EMPEROR, 2), DrawIntrigueCards(1)),
        ),
        # Smuggle Spice: "Whenever another player sends an Agent to a Maker
        # board space you are spying on: Gain 1 spice" (Limited Allies is a
        # setup field).
        "staban_tuek": (
            _triggered(OnOpponentAgentAtSpiedMakerSpace(), GainResources(spice=1)),
        ),
        # Sardaukar Commander: both Sardaukar Contracts set aside; only he
        # may take them (OQ-021).
        "shaddam_corrino_iv": (_standing("sardaukar_contracts"),),
        # Tactician: the Tactics token advances by the troops retreated or
        # lost [FAQ p. 1].
        "chani": (
            _left_hook(AbilityTiming.TRIGGERED, "tactician", AbilityMark.AUTOMATIC),
        ),
        # Assassin: "Whenever you trash a card: Gain 1 solari".
        "count_hasimir_fenring": (
            _triggered(OnCardTrashed(), GainResources(solari=1)),
        ),
        # Ginaz Swordmaster: "The Swordmaster board space costs you 2 less".
        "duncan_idaho": (_standing("ginaz_swordmaster"),),
        # Tuek's Sietch: "Whenever you send an Agent to Tuek's Sietch: Gain 1
        # solari. Whenever an opponent sends an Agent there: Draw 1 Intrigue
        # card" (the space itself is set up for him, A5's board hook).
        "esmar_tuek": (
            _triggered(OnAgentSentTo("tuek_sietch"), GainResources(solari=1)),
            _triggered(
                OnAgentSentTo("tuek_sietch", opponent=True), DrawIntrigueCards(1)
            ),
        ),
        # Clandestine: every card played has the Spy icon (OQ-055), and
        # Gather Intelligence is forced.
        "gaius_helen_mohiam": (_standing("clandestine"),),
        # Twisted Genius: the Twisted deck is his setup (a setup field); "Round
        # start: draw a Twisted Intrigue card" (OQ-072, OQ-097).
        "piter_de_vries": (_triggered(OnRoundStart(), DrawTwistedIntrigueCards(1)),),
        # Strange Form is setup (fields); Hungry for Spice: "whenever you gain
        # 3 or more spice in a single turn: Draw 1 card" (OQ-063, OQ-106).
        # Plot Course (printed where the Signet would be): "Whenever you reach
        # 2 Influence with a Faction, play the next Navigation card" (OQ-012,
        # OQ-039).
        "steersman_y_rkoon": (
            _triggered(OnSpiceGainedInTurnAtLeast(3), DrawPersonalCards(1)),
            _left_hook(AbilityTiming.TRIGGERED, "plot_course", AbilityMark.AUTOMATIC),
        ),
        # Arrakis Planetologist: Sietch Tabr's requirement ignored, and every
        # sandworm replaced (OQ-037).
        "liet_kynes": (_standing("arrakis_planetologist"),),
        # Secret Project: a Tech tile chosen at game start, acquirable at 1
        # spice less (OQ-041).
        "kota_odax_of_ix": (_standing("secret_project"),),
        # The original game's (docs/rules/imperium-base.md 12; Glossu
        # Rabban's Arrakis Fiefdom is setup, ``LeaderDefinition`` fields).
        # Ruthless Negotiator: a card whenever Solari pay a board space's
        # printed cost [FAQ p. 2], drawn as its own step (OQ-106).
        "count_ilban_richese": (
            _triggered(OnBoardSpaceSolariPaid(), DrawPersonalCards(1)),
        ),
        # Connections: Influence with a Faction of the owner's choice on
        # taking a High Council seat (none at the top, OQ-060).
        "earl_memnon_thorvald": (
            _triggered(OnHighCouncilSeatTaken(), GainInfluence()),
        ),
        # Spice Addict: harvesting at a Maker space -- only there, and not
        # optional [FAQ p. 2] -- yields 1 spice less (the standing record)
        # and a card, drawn as its own step (OQ-106).
        "countess_ariana_thorvald": (
            _standing("spice_addict"),
            _triggered(OnMakerSpiceHarvested(), DrawPersonalCards(1)),
        ),
        # Landsraad Popularity (stage P2b): a Landsraad space's Solari cost
        # is 1 less, never optional (P0 sweep L5).
        "duke_leto_atreides": (_standing("landsraad_popularity"),),
        # Eyes Everywhere (stage P2b): opponents' Agents do not block her on
        # Landsraad and City spaces (P0 sweep L8).
        "helena_richese": (_standing("eyes_everywhere"),),
        # Masterstroke (stage P2b): two Factions chosen in secret before the
        # first round, revealed for an Influence each the first time his
        # turn's deployed troops reach four (OQ-115; ``rules.masterstroke``).
        "baron_vladimir_harkonnen": (_standing("masterstroke"),),
        # Prescience (stage P2b): he sees his deck's top card at any time,
        # none while the deck is empty [DI p. 13] (``core.observation``).
        "paul_atreides": (_standing("prescience"),),
        # Rise of Ix's (docs/rules/rise-of-ix.md 10; stage P4e). Smuggling
        # Operation: no water at setup (a ``LeaderDefinition`` field), and
        # "자기 turn에 Solari를 얻을 때마다 1 더" [FAQ p. 3] -- her own Agent or
        # Reveal turn only (OQ-042, OQ-063; ``rules.leader_abilities.
        # grant_smuggling_operation``).
        "princess_yuna_moritani": (_standing("smuggling_operation"),),
        # Heavy Lasgun Cannons: "dreadnought strength 4" (rise-of-ix.md 6, 10;
        # ``rules.strength.dreadnought_strength``).
        "prince_rhombur_vernius": (_standing("heavy_lasgun_cannons"),),
    }
)


def leader_triggers[T](
    face_id: str | None, kind: type[T]
) -> tuple[tuple[T, tuple[Reward, ...]], ...]:
    """A face's triggered abilities of trigger ``kind``, with their rewards."""

    if face_id is None:
        return ()
    found: list[tuple[T, tuple[Reward, ...]]] = []
    for ability in LEADER_ABILITIES.get(face_id, ()):
        if isinstance(ability.trigger, kind) and ability.hook is None:
            found.append((ability.trigger, ability.sections[0].rewards))
    return tuple(found)


def leader_reveal_line(face_id: str | None) -> EffectSection | None:
    """A face's automatic Reveal line (Always Smiling, Unpredictable Foe)."""

    if face_id is None:
        return None
    for ability in LEADER_ABILITIES.get(face_id, ()):
        if (
            ability.timing is AbilityTiming.REVEAL
            and ability.hook is None
            and ability.mark is AbilityMark.AUTOMATIC
        ):
            return ability.sections[0]
    return None
