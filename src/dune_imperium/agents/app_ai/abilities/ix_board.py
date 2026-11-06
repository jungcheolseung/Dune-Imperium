"""Rise of Ix's Freighter and Shipping track (docs/app-ai-plan.md §13).

Ports of the app's ``RiseOfIx`` Freighter and Shipping-track reward classes,
read from spec/rix-tech.md §4.6-4.7 and §6.6 ([V]) and the P6 Ix
decompilation (assets ``ghidra/p6ix/<addr>.c``, index
``ghidra/p6ix/targets-named.tsv``), confirmed in the annotated disassembly
(``dump/asm/worm-canis.dll/<class>.asm``).

App class chains (``dump/worm-canis.dll.cs``):

- ``ActivatedAbilities.DeferredAbility`` <- ``RiseOfIx.FreighterAbility``
  (abstract) <- ``FreighterAgentAbility``, ``FreighterRevealAbility``,
  ``FreighterCustomAbility`` (the subclasses override only their id, and the
  custom one its execution: the AI hooks are the base's);
- ``DeferredAbility`` <- ``RiseOfIx.ShippingTrackAbility1``,
  ``RiseOfIx.ShippingTrackAbility3``;
- ``ActivatedAbilities.GainAnyInfluenceAbility`` <-
  ``RiseOfIx.ShippingTrackAbility2`` (no AI override);
- ``SpaceAbilities.SpaceAbility`` <- the four Ix spaces' classes;
  ``TriggeredAbilities.TriggeredAbility`` <-
  ``RiseOfIx.TechNegotiationTriggeredAbility``.

The spaces' other abilities are ported elsewhere and summed with these
(generic-abilities.md §2.1): Freighter icons (``FreighterAgentAbility``
below), the Dreadnought space's ``AcquireTechAbility`` and Tech Negotiation's
``TechNegotiationDeferredAbility`` (``abilities/tech.py``).

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    Timing,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    GainAnyInfluenceAbility,
    SpaceAbility,
    TriggeredAbility,
)
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."
_SA = "worm.canis.abilities.SpaceAbilities.RiseOfIx."
_TA = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."
_CA = "worm.canis.abilities.ConflictAbilities.RiseOfIx."

#: ``DreadnoughtControlAbility::Evaluate``'s first response: 0 places the
#: dreadnought on the space named second, 1 is Detonation Devices' VP.
DREADNOUGHT_PLACE = 0
DREADNOUGHT_DETONATE = 1

#: ``FreighterAbility::Evaluate``'s response: ``Item1`` of
#: ``GetFreighterSelections`` (log 'Recall' / 'Advance', spec §4.7).
FREIGHTER_RECALL = 1
FREIGHTER_ADVANCE = 0
#: ``ShippingTrackAbility1::Evaluate``'s response: ``Item2`` (log 'Solari' /
#: 'Spice'): space 1's Dividends or its spice.
SHIPPING_SOLARI = 0
SHIPPING_SPICE = 1


# -- the Freighter -------------------------------------------------------------------


class FreighterAbility(DeferredAbility):
    """``RiseOfIx.FreighterAbility`` (abstract): move the Freighter up one
    space or recall it (spec §6.6)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FreighterAbility::SelectionMode`` @0x4db8470: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FreighterAbility::ValueForPlayer`` @0x4db8640:
        ``Add(FreighterValue, "Freighter Ability")``."""

        v = Summer()
        v.add("Freighter Ability", p.freighter_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FreighterAbility::Evaluate`` @0x4db87a0:
        ``UpdateSelectionResponses(FreighterValue, src,
        [IntTargetResponse(sel.Item1)])``, ``sel =
        GetFreighterSelections(-1)``."""

        recall, _, log = p.freighter_selections(-1)
        verb = "Recall" if recall == FREIGHTER_RECALL else "Advance"
        return Answer(
            p.freighter_value(), ((recall,),), f"Freighter Ability | {verb} | {log}"
        )


@port(_AA + "FreighterAgentAbility")
class FreighterAgentAbility(FreighterAbility):
    """``RiseOfIx.FreighterAgentAbility``: a Freighter icon of an Agent box or
    a space (Interstellar Shipping, Smuggling, Landing Rights)."""

    timing: ClassVar[Timing] = Timing.AGENT


@port(_AA + "FreighterRevealAbility")
class FreighterRevealAbility(FreighterAbility):
    """``RiseOfIx.FreighterRevealAbility``: a Reveal box's Freighter icon."""

    timing: ClassVar[Timing] = Timing.REVEAL


@port(_AA + "FreighterCustomAbility")
class FreighterCustomAbility(FreighterAbility):
    """``RiseOfIx.FreighterCustomAbility``: a Freighter granted by another
    ability (Conflict rewards, Intrigue cards, Hundro's Couriers); its
    ``Cost``/``CustomExecution`` are the engine's, its AI hooks the base's."""


# -- the Shipping track's recall rewards ---------------------------------------------


@port(_AA + "ShippingTrackAbility1")
class ShippingTrackAbility1(DeferredAbility):
    """``RiseOfIx.ShippingTrackAbility1``: space 1, Dividends (5 Solari, each
    opponent 1) or 2 spice."""

    def __init__(self, owner: Entity, last_recall_space: int = -1) -> None:
        super().__init__(owner)
        #: The ability's ``LastShippingRecallSpace`` attribute: the space the
        #: Freighter was recalled from (-1 when unset, as the app's default).
        self.last_recall_space = last_recall_space

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ShippingTrackAbility1::SelectionMode`` @0x4ddecf0: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShippingTrackAbility1::Evaluate`` @0x4ddee30: ``sel =
        GetFreighterSelections(LastShippingRecallSpace)``, answered
        ``IntTargetResponse(sel.Item2)`` at the f64 100.0 (log "Shipping
        Track 1 | 100 | Solari/Spice")."""

        _, choice, log = p.freighter_selections(self.last_recall_space)
        part = "Solari" if choice == SHIPPING_SOLARI else "Spice"
        return Answer(100.0, ((choice,),), f"Shipping Track 1 | 100 | {part} {log}")


@port(_AA + "ShippingTrackAbility2")
class ShippingTrackAbility2(GainAnyInfluenceAbility):
    """``RiseOfIx.ShippingTrackAbility2``: space 2, recruit two troops and one
    Influence of choice; ``GainAnyInfluenceAbility``'s hooks (no override:
    the class has only ``Targets``, ``Cost``, ``SelectionMode`` 3 @0x4de0c70
    and its execution)."""


@port(_AA + "ShippingTrackAbility3")
class ShippingTrackAbility3(DeferredAbility):
    """``RiseOfIx.ShippingTrackAbility3``: space 3, Acquire Tech at Tech
    Discount 2 (the tile itself is ``AcquireTechAbilityShippingTrack2``'s
    pick, ``abilities/tech.py``)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ShippingTrackAbility3::SelectionMode`` @0x4de16b0: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShippingTrackAbility3::Evaluate`` @0x4de17d0:
        ``UpdateSelectionTargets(100.0, src, [])`` (f64 100.0 at
        0x4de1836): taken, no target."""

        return Answer(100.0, (), "Shipping Track 3 | 100")


# -- the four Rise of Ix spaces ------------------------------------------------------


@port(_SA + "DreadnoughtSpaceAbility")
class DreadnoughtSpaceAbility(SpaceAbility):
    """``SpaceAbilities.RiseOfIx.DreadnoughtSpaceAbility``: commission a
    dreadnought (the space's Acquire Tech is ``AcquireTechAbility``)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DreadnoughtSpaceAbility::ValueForPlayer`` @0x4bc3600 (rix-tech.md
        §6.7): the generic space value plus ``GetDreadnoughtValue(1, false)``
        ("Dreadnought from Space"); the -10.0 is the ``TutorialROI``
        scenario's only."""

        v = super().value_for_player(p, ())
        v.add("Dreadnought from Space", p.dreadnought_value(1, False))
        return v


@port(_SA + "InterstellarShippingSpaceAbility")
class InterstellarShippingSpaceAbility(SpaceAbility):
    """``SpaceAbilities.RiseOfIx.InterstellarShippingSpaceAbility``:
    ``ValueForPlayer`` @0x4bc42b0 is the generic space value (its -10.0 is
    the ``TutorialROI`` scenario's only); the two Freighters are
    ``FreighterAgentAbility``."""


@port(_SA + "SmugglingSpaceAbility")
class SmugglingSpaceAbility(SpaceAbility):
    """``SpaceAbilities.RiseOfIx.SmugglingSpaceAbility``: ``ValueForPlayer``
    @0x4bc46f0 is the generic space value (the ``TutorialROI`` -10.0
    aside); its Freighter is ``FreighterAgentAbility``."""


@port(_SA + "TechNegotiationSpaceAbility")
class TechNegotiationSpaceAbility(SpaceAbility):
    """``SpaceAbilities.RiseOfIx.TechNegotiationSpaceAbility``: no AI
    override (only ``MakeGameLogBuilder``); its choice is
    ``TechNegotiationDeferredAbility``."""


@port(_TA + "TechNegotiationTriggeredAbility")
class TechNegotiationTriggeredAbility(TriggeredAbility):
    """``TriggeredAbilities.RiseOfIx.TechNegotiationTriggeredAbility``: +1
    Persuasion on the Reveal turn while the Agent stands here."""

    should_exhaust: ClassVar[bool] = False  # get_ShouldExhaust @0x4b08ea0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TechNegotiationTriggeredAbility::ValueForPlayer`` @0x4b090a0:
        ``GetPersuasionValue(1)``."""

        v = Summer()
        v.add("Tech Negotiation Persuasion", p.persuasion_value(1))
        return v


# -- the Conflict winner's dreadnought ----------------------------------------------


@port(_CA + "DreadnoughtControlAbility")
class DreadnoughtControlAbility(DeferredAbility):
    """``ConflictAbilities.RiseOfIx.DreadnoughtControlAbility``: the winner
    places a dreadnought from the Conflict on a Control space without one
    [Rise of Ix p. 6], or (Detonation Devices) takes 1 VP instead."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DreadnoughtControlAbility::SelectionMode`` @0x4b74f70: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DreadnoughtControlAbility::Evaluate`` @0x4b75520.

        With Detonation Devices held, ``IntTargetResponse(1)`` at the f64
        100.0 first ("Detonation Devices | 100"). Then the spaces of
        ``request.infos[0]`` (``ValidEntities``), shuffled
        (``ListUtil.Shuffle``, the seat's RNG here), each answered
        ``[IntTargetResponse(0), space]`` and kept only when strictly
        better: a space another seat controls at that seat's
        ``VictoryPoints``, the seat's own at 1.0 ("Already controlled"), an
        uncontrolled Imperial Basin at 3.0 and any other uncontrolled space
        at 2.0 ("not controlled"; ``ArchID == BaseSet.ImperialBasin``).
        ``controllers`` maps each space ref to its ``ControllingPlayer``
        seat (a dreadnought ahead of the marker).
        """

        best: Answer | None = None
        if p.ctx.has_tech("detonation_devices"):
            best = Answer(100.0, ((DREADNOUGHT_DETONATE,),), "Detonation Devices | 100")
        spaces = list(request.infos[0].entities) if request.infos else []
        p.rng.shuffle(spaces)
        for space in spaces:
            controller = self.controllers.get(space.ref)
            if controller is None:
                basin = space.short == "SpaceArchetypes.BaseSet.ImperialBasin"
                value = 3.0 if basin else 2.0
                log = (
                    f"Dreadnought Control | {int(value)} | {space.ref} | not controlled"
                )
            elif controller == p.ctx.seat:
                value = 1.0
                log = f"Dreadnought Control | 1 | {space.ref} | Already controlled"
            else:
                value = float(p.ctx.vp(p.ctx.players[controller]))
                log = f"Dreadnought Control | {int(value)} | {space.ref} | controlled"
            if best is None or value > best.value:
                best = Answer(value, ((DREADNOUGHT_PLACE,), (space.ref,)), log)
        return best if best is not None else Answer(0.0, None, "Dreadnought Control")

    def __init__(
        self, owner: Entity, controllers: dict[str, int | None] | None = None
    ) -> None:
        super().__init__(owner)
        #: Each offered space's ``ControllingPlayer`` (the window's).
        self.controllers = controllers or {}
