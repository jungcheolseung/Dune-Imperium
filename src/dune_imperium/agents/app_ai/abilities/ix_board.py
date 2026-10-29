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
  ``RiseOfIx.ShippingTrackAbility2`` (no AI override).

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
)
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."

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
