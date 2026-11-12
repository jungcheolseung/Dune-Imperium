"""Ports of Rise of Ix's three Conflict cards (docs/app-ai-plan.md §13).

Skirmish E, Skirmish F (Conflict I) and Trade Monopoly (Conflict II), one class per
place; each follows the app's AI for that class, and the detailed notes are kept
privately (``docs/app-ai-plan.md`` §13). Trade Monopoly's third place is the app's
``ability.conflict.original.trade_monopoly_third`` (the class belongs to the original
game's set). Economic Supremacy is the Epic port (``abilities/epic_promo.py``).

As the original cards (``abilities/original_conflicts.py``), every class
derives straight from ``ConflictAbilities.ConflictAbility`` and carries its
own rewards; ``ValueForPlayer`` adds the terms in the app's order.

The choices: Skirmish E and F 1st answer their Freighter with
``GetFreighterSelections(-1).Item1`` at ``FreighterValue`` (as
``FreighterAbility.Evaluate``; our engine asks it in the ``freighter_move``
window); Trade Monopoly 1st grants two Freighters it does not evaluate (the
granted Freighter abilities answer); Trade Monopoly 3rd's "-OR-" is a custom
choice of two options.

"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import Answer, Request, port
from dune_imperium.agents.app_ai.abilities.board import _math_max
from dune_imperium.agents.app_ai.abilities.generic import ConflictAbility
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_CA = "ability.conflict.ix."
_CA_BASE = "ability.conflict.original."


def _twice(price: float) -> float:
    """a price counted twice."""

    return price + price


def _freighter_answer(p: Profile, label: str) -> Answer:
    """The Freighter prompt of a 1st place: ``UpdateSelectionResponses(
    FreighterValue, src, [IntTargetResponse(GetFreighterSelections(-1)
    .Item1)])`` (log "<card> First Freighter | Recall/Advance")."""

    recall, _, log = p.freighter_selections(-1)
    verb = "Recall" if recall == 1 else "Advance"
    return Answer(p.freighter_value(), ((recall,),), f"{label} | {verb} | {log}")


# -- Skirmish E ------------------------------------------------------------------


@port(_CA + "skirmish_e_first")
class SkirmishEFirstAbility(ConflictAbility):
    """Skirmish E, first place: a Freighter and one troop."""

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetTroopValue(1)``, then
        ``FreighterValue``."""

        v = Summer()
        v.add("Skirmish E First Troop", p.troop_value(1, False))
        v.add("Skirmish E First Freighter", p.freighter_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishEFirstAbility.Evaluate``: the Freighter."""

        return _freighter_answer(p, "Skirmish E First Freighter")


@port(_CA + "skirmish_e_second")
class SkirmishESecondAbility(ConflictAbility):
    """Skirmish E, second place: 2 spice."""

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetSpiceValue(1)`` doubled."""

        v = Summer()
        v.add("Conflict SkirmishE Second 2 Spice", _twice(p.spice_value(1)))
        return v


@port(_CA + "skirmish_e_third")
class SkirmishEThirdAbility(ConflictAbility):
    """Skirmish E, third place: 1 spice."""

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetSpiceValue(1)``."""

        v = Summer()
        v.add("Conflict SkirmishE Third Spice", p.spice_value(1))
        return v


# -- Skirmish F ------------------------------------------------------------------


@port(_CA + "skirmish_f_first")
class SkirmishFFirstAbility(ConflictAbility):
    """Skirmish F, first place: a Freighter and 1 spice."""

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetSpiceValue(1)``, then
        ``FreighterValue``."""

        v = Summer()
        v.add("Skirmish F First Spice", p.spice_value(1))
        v.add("Skirmish F First Freighter", p.freighter_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SkirmishFFirstAbility.Evaluate``: the Freighter."""

        return _freighter_answer(p, "Skirmish F First Freighter")


@port(_CA + "skirmish_f_second")
class SkirmishFSecondAbility(ConflictAbility):
    """Skirmish F, second place: 3 Solari."""

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetSolariValue(3)``."""

        v = Summer()
        v.add("Conflict SkirmishF Second 3 Solari", p.solari_value(3))
        return v


@port(_CA + "skirmish_f_third")
class SkirmishFThirdAbility(ConflictAbility):
    """Skirmish F, third place: 2 Solari."""

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetSolariValue(2)``."""

        v = Summer()
        v.add("Conflict SkirmishFThird 2 Solari", p.solari_value(2))
        return v


# -- Trade Monopoly ----------------------------------------------------------------


@port(_CA + "trade_monopoly_first")
class TradeMonopolyFirstAbility(ConflictAbility):
    """Trade Monopoly, first place: two Freighters and one troop."""

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetTroopValue(1)``, then
        ``FreighterValue`` doubled."""

        v = Summer()
        v.add("Trade Monopoly First Troop", p.troop_value(1, False))
        v.add("Trade Monopoly 2 Freighter", _twice(p.freighter_value()))
        return v


@port(_CA + "trade_monopoly_second")
class TradeMonopolySecondAbility(ConflictAbility):
    """Trade Monopoly, second place: 1 water and one Intrigue."""

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``GetWaterValue(1)``, then
        ``IntrigueValue``."""

        v = Summer()
        v.add("Conflict Trade Monopoly Second Water", p.water_value(1))
        v.add("Conflict Trade Monopoly Second Intrigue", p.intrigue_value())
        return v


@port(_CA_BASE + "trade_monopoly_third")
class TradeMonopolyThirdAbility(ConflictAbility):
    """Trade Monopoly, third place: one Intrigue -OR- 1 water."""

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ValueForPlayer``: ``Max(IntrigueValue,
        GetWaterValue(1))``."""

        v = Summer()
        v.add(
            "Conflict Trade Monopoly Third Resource",
            _math_max(p.intrigue_value(), p.water_value(1)),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TradeMonopolyThirdAbility.Evaluate``: option 0 (the
        Intrigue) at ``IntrigueValue``, then option 1 (the water) at
        ``GetWaterValue(1)``, each replacing the stored answer only when
        strictly better (a tie keeps the Intrigue)."""

        best = first_strictly_best([(0, p.intrigue_value()), (1, p.water_value(1))])
        assert best is not None
        option, value = best
        return Answer(value, ((option,),), f"Trade Monopoly Third | option {option}")
