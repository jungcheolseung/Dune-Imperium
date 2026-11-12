"""The original board's space abilities.

Ports of the original game's space classes the Uprising board does not use; each follows
the app's AI for that class, and the detailed notes are kept privately
(``docs/app-ai-plan.md`` §12). The classes the Uprising board shares (High Council,
Heighliner, Secrets) are in ``abilities/board.py``.

App class chains:

- ``SpaceAbilities.SpaceAbility`` <- ``ConspireSpaceAbility``,
  ``MentatSpaceAbility``, ``SwordmasterSpaceAbility``, ``SellMelangeSpaceAbility``,
  ``HallOfOratorySpaceAbility``;
- ``ActivatedAbilities.DeferredAbility`` <-
  ``FoldspaceDeferredAbility``, ``SelectiveBreedingDeferredAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <- ``HallOfOratoryAbility2``.

"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    SpaceAbility,
    TriggeredAbility,
    _runs_unless_threshold,
    _targets,
)
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "ability.activated.original."
_SA = "ability.space.original."
_TA = "ability.triggered.original."

#: Our Reserve stack of the app's ``imperium.original.foldspace_imperium``.
FOLDSPACE_CARD = "foldspace_card"


def _missing_swordmaster(p: Profile) -> bool:
    """``!P.Swordmaster && GetGameArc() < 2``: the shared test of Conspire's and Sell
    Melange's Swordmaster bonus."""

    return not p.ctx.me.swordmaster_acquired and p.game_arc() <= 1


# -- Conspire ------------------------------------------------------------------


@port(_SA + "conspire_space")
class ConspireSpaceAbility(SpaceAbility):
    """``ability.space.original.conspire_space`` (4 spice: 5 Solari,
    2 troops, 1 Intrigue)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ConspireSpaceAbility.ValueForPlayer``.

        The generic space value (``Array.Empty``), then, without the Swordmaster early
        on and with more than 3 spice, ``ConspireSpaceBonus``: the Solari buy the
        Swordmaster.
        """

        v = super().value_for_player(p, ())
        if _missing_swordmaster(p) and p.ctx.me.resources.spice > 3:
            v.add("Space Conspire Missing Swordmaster", p.C.ConspireSpaceBonus)
        return v


# -- Mentat --------------------------------------------------------------------


@port(_SA + "mentat_space")
class MentatSpaceAbility(SpaceAbility):
    """``ability.space.original.mentat_space`` (2 Solari: the Mentat
    while it is here; the space's ``DrawAbility`` draws the card)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``MentatSpaceAbility.ValueForPlayer``.

        The generic space value, then ``MentatValue`` when the space's children hold the
        Mentat (an entity named ``EntityNames.Mentat``): nobody took it this round and
        no Sort Through the Chaos winner waits for it (``AppContext.mentat_rests``).
        """

        v = super().value_for_player(p, ())
        if p.ctx.mentat_rests:
            v.add("Space Mentat", p.mentat_value())
        return v


# -- Swordmaster ---------------------------------------------------------------


@port(_SA + "swordmaster_space")
class SwordmasterSpaceAbility(SpaceAbility):
    """``ability.space.original.swordmaster_space`` (8 Solari, never
    cheaper on the original board)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SwordmasterSpaceAbility.ValueForPlayer``: the generic
        space value plus ``SwordmasterValue``."""

        v = super().value_for_player(p, ())
        v.add("Space Swordmaster", p.swordmaster_value())
        return v


# -- Sell Melange ----------------------------------------------------------------


def sell_melange_solari(spice: int) -> int:
    """The Solari ``n`` spice sells for: ``2n + 2`` (``iVar5 * 2 + 2`` in
    both ``ValueForPlayer`` and ``Evaluate``; 2, 3, 4, 5 spice -> 6, 8, 10,
    12 Solari [DI p. 18])."""

    return spice * 2 + 2


@port(_SA + "sell_melange_space")
class SellMelangeSpaceAbility(SpaceAbility):
    """``ability.space.original.sell_melange_space``: sell 2-5 spice."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SellMelangeSpaceAbility.ValueForPlayer``.

        The generic space value; with ``n = GetSpiceForSellMelange() >= 1``
        the spice paid and the Solari gained; then, without the Swordmaster
        early on, ``SellMelangeSpaceBonus``.
        """

        v = super().value_for_player(p, ())
        n = p.spice_for_sell_melange()
        if n < 1:
            return v
        v.add("Space Sell Melange Spice Cost", p.spice_value(-n))
        v.add("Space Sell Melange Solari", p.solari_value(sell_melange_solari(n)))
        if _missing_swordmaster(p):
            v.add("Space Sell Melange Missing Swordmaster", p.C.SellMelangeSpaceBonus)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SellMelangeSpaceAbility.Evaluate``.

        ``n = GetSpiceForSellMelange()``; below 1 the empty choice. The value
        is the Solari minus the spice; a sum ``<= 0`` is reset to 1.0
        ("Ensure positive value", ``Multiply(0)`` then the f64 literal 1.0).
        The response is ``IntListTargetResponse(n)``: option ``n`` (the spice
        sold).
        """

        n = p.spice_for_sell_melange()
        if n < 1:
            return Answer(0.0, None, "SellMelange none")
        v = Summer()
        v.add("Solari", p.solari_value(sell_melange_solari(n)))
        v.add("Spice Cost", p.spice_value(-n))
        value = v.sum if v.sum > 0.0 else 1.0
        return Answer(value, ((n,),), f"SellMelange | sell {n} | {value}")


# -- Hall of Oratory ---------------------------------------------------------------


@port(_SA + "hall_of_oratory_space")
class HallOfOratorySpaceAbility(SpaceAbility):
    """``ability.space.original.hall_of_oratory_space``: no AI override
    (the generic space value: its troop)."""


@port(_TA + "hall_of_oratory_ability2")
class HallOfOratoryAbility2(TriggeredAbility):
    """``ability.triggered.original.hall_of_oratory_ability2``: +1 Persuasion on
    the Reveal turn while the Agent stands here."""

    should_exhaust: ClassVar[bool] = False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HallOfOratoryAbility2.ValueForPlayer`` (literal 1)."""

        v = Summer()
        v.add("Hall of Oratory Persuasion", p.persuasion_value(1))
        return v


# -- Foldspace -------------------------------------------------------------------


def foldspace_in_reserve(p: Profile) -> bool:
    """``ReserveRowCards(M, true).Any(ArchID == FoldspaceImperium)``: a Foldspace card
    is left in the Reserve."""

    return any(
        card == FOLDSPACE_CARD and count > 0 for card, count in p.ctx.reserve_stacks
    )


@port(_AA + "foldspace_deferred")
class FoldspaceDeferredAbility(DeferredAbility):
    """``ability.activated.original.foldspace_deferred``: gain the
    Foldspace card."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FoldspaceDeferredAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``FoldspaceDeferredAbility.CanRunImmediately`` (the
        ``DrawAbility`` test)."""

        return _runs_unless_threshold(p)

    def meets_cost(self, p: Profile) -> bool:
        """``FoldspaceDeferredAbility.Cost``."""

        return foldspace_in_reserve(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FoldspaceDeferredAbility.ValueForPlayer``: the base
        value plus ``FoldspaceValue`` while one is left (the ``TutorialROI``
        term is the tutorial's only)."""

        v = Summer()
        if foldspace_in_reserve(p):
            v.add("Foldspace Gain", p.foldspace_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FoldspaceDeferredAbility.Evaluate``: the f64 literal
        100.0 with ``IntTargetResponse(0)``."""

        return Answer(100.0, ((0,),), "Foldspace | 100")


# -- Selective Breeding ------------------------------------------------------------


@port(_AA + "selective_breeding_deferred")
class SelectiveBreedingDeferredAbility(DeferredAbility):
    """``ability.activated.original.selective_breeding_deferred``: trash
    a card to draw two."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SelectiveBreedingDeferredAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SelectiveBreedingDeferredAbility.ValueForPlayer``: the trash, two draws
        with buy gains and the trash bonus."""

        v = Summer()
        v.add("Selective Breeding Trash", p.trash_card_value())
        v.add(
            "Selective Breeding Draw with Buy Gains",
            2 * p.card_draw_value_with_buy_gains(),
        )
        v.add("Selective Breeding Trash Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SelectiveBreedingDeferredAbility.Evaluate``.

        ``GetCardToTrash(targets, 1.0)``; without a junk card the target of least
        ``AcquireValue`` (``OrderBy(c => c.AcquireValue(player)) .First()``; stable, in
        the targets' order). The value is the trash value plus two draws with buy gains;
        the response names that card.
        """

        targets = _targets(request, Kind.CARD)
        card, trash_value = p.card_to_trash(targets, 1.0)
        v = Summer()
        v.add("Trash Value", trash_value)
        if card is None:
            if not targets:
                return Answer(0.0, None, "Selective Breeding no target")
            card = min(targets, key=lambda c: p.acquire_value(c).sum)
        v.add("Draw 2 cards with Buy Gains", 2 * p.card_draw_value_with_buy_gains())
        return Answer(
            v.sum, ((card.ref,),), f"Selective Breeding | {v.sum} | {card.ref}"
        )
