"""App-style Arrakeen Scouts abilities and evaluators (docs/app-ai/scouts.md).

The app has no Scouts: every class here is an app-style extension
(``worm.canis.abilities.AppStyle.Scouts.*``, evaluators
``worm.canis.ai.evaluators.AppStyle.Scouts.*``) under docs/app-ai-plan.md §11.
Values are the existing profile prices (``profile/scouts.py`` adds the Scouts
ones, scouts.md §2.1); decisions follow plan §11.4/§11.5 as scouts.md §3 and
§7 apply them, with plan §11.7's revision of the forced hand trash.

Line abilities (scouts.md §2.3): owned by a Scouts line entity
(``catalog.scouts_line_entity``, ``Kind.SCOUTS``); common members unless a
class says otherwise: base ``DeferredAbility``, timing None, always run
immediately (a line's steps are never post-action keys), Implicit (2) or
Explicit (3) for a step that asks. ``scouts_line_value`` merges their
``ValueForPlayer`` into the line value. Board abilities (§2.3, §4): the
mission pieces of a space (``MissionPiecesSpaceAbility``), Desert Riding at
Hagga Basin, the subcommittee offer at High Council (overlays of
``catalog.space_entity``, scouts.md §4.8) and Corrinth City's Reveal with the
subcommittee opportunity.

Request / answer encoding (``abilities/base``, as in ``generic.py``): the
candidates of an ability's prompt are ``request.infos[0].entities`` (cards,
Intrigue cards, spies, faction tracks); ``Answer.response`` holds the chosen
refs per target info, ``None`` = the empty answer. Evaluators (§2.4) take
their candidates as plain arguments (the window's legal values, in legal
order) and answer ``((value,),)`` with the chosen line / subcommittee /
pick / slot / count / faction, or ``(("<action id>", argument),)`` where the
answer selects one of two actions (mission join vs specimen top-up, bid vs
confirm). ``response is None`` is the empty answer (pass, decline). Every
forced evaluator always answers (``make_choice``, then the forced rule:
least loss or ``DefaultRandomChoice``, drawn from the profile rng over the
candidates in the order given, as ``choice.default_random_choice`` draws
over the legal actions).
"""

import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    Timing,
    port,
)
from dune_imperium.agents.app_ai.abilities.board import (
    HaggaBasinUprisingDeferredAbility,
)
from dune_imperium.agents.app_ai.abilities.immortality import _can_gain_tleilaxu
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    CorrinthCityRevealAbility,
    _trash_intrigue_choice,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import _Choice as _FirstChoice
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _Choice,
    choose_faction_influence,
)
from dune_imperium.agents.app_ai.catalog import card_entity, scouts_line_entity
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.scouts import (
    HELIX_SPICE,
    RESOURCE_ATTRS,
    mission_collected_on_visit,
    mission_troops_to_conflict,
    reserve_card,
    reserve_ids_of,
)
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    MissionKind,
)
from dune_imperium.rules.influence import MAX_INFLUENCE

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AS: Final = "worm.canis.abilities.AppStyle.Scouts."
_EV: Final = "worm.canis.ai.evaluators.AppStyle.Scouts."

#: scouts.md §3.1: the mandatory Influence Reduction family (app family 18,
#: ``Def_Event_InfluenceReduction_*``), answered by least loss (D15).
INFLUENCE_REDUCTION_EVENTS: Final = frozenset(
    {
        "crackdown",
        "water_for_spice_smugglers",
        "bene_gesserit_treachery",
        "funeral_rites",
    }
)


# ---------------------------------------------------------------------------
# The decision rules (plan §4.1, §11.4; scouts.md §0)
# ---------------------------------------------------------------------------


def make_choice_of[T](
    items: Sequence[tuple[T, float]], rng: random.Random
) -> tuple[T, float] | None:
    """``mc``: ``choice.make_choice`` over ``(item, value)`` pairs.

    Shuffle everything, keep ``value > 0`` (strict), stable-sort descending,
    take the first; None is the empty answer.
    """

    pool = list(items)
    rng.shuffle(pool)
    positive = [item for item in pool if item[1] > 0.0]
    if not positive:
        return None
    positive.sort(key=lambda item: item[1], reverse=True)
    return positive[0]


def least_loss[T](
    items: Sequence[tuple[T, float]], rng: random.Random
) -> tuple[T, float] | None:
    """**Least loss** (plan §11.4, scouts.md §0, D16): shuffle with the agent
    rng, then the first strictly best over all candidates, values <= 0
    included (uniform among tied best)."""

    pool = list(items)
    rng.shuffle(pool)
    return first_strictly_best(pool)


def default_random[T](items: Sequence[T], rng: random.Random) -> T:
    """``DefaultRandomChoice`` over ``items`` (``choice.default_random_choice``
    draws the same way over the legal actions)."""

    return items[rng.randrange(len(items))]


def _forced_answer[T: (int, str)](
    p: Profile, items: Sequence[tuple[T, float]], label: str
) -> Answer:
    """A forced several-options prompt (plan §11.4, D40): ``mc``; no positive
    candidate -> ``DefaultRandomChoice``."""

    if not items:
        return Answer(0.0, None, f"{label} | no candidate")
    chosen = make_choice_of(items, p.rng)
    if chosen is not None:
        return Answer(chosen[1], ((chosen[0],),), label)
    pick = default_random([item for item, _ in items], p.rng)
    value = next(v for item, v in items if item == pick)
    return Answer(value, ((pick,),), f"{label} | DefaultRandomChoice")


def _targets(request: Request, kind: Kind) -> list[Entity]:
    if not request.infos:
        return []
    return [e for e in request.infos[0].entities if e.kind is kind]


def _influence(p: Profile, faction: str) -> int:
    return int(getattr(p.ctx.me.influence, faction))


# ---------------------------------------------------------------------------
# §2.3 Line abilities
# ---------------------------------------------------------------------------


class _ScoutsLineAbility(g.DeferredAbility):
    """The common members of the Scouts line abilities (scouts.md §2.3).

    Not an app class: a shared base like ``_CargoRunnerContractsDrawAbility``.
    Timing None; ``AlwaysRunImmediately`` (a line's steps are never
    post-action keys); Implicit unless a class asks (Explicit). ``Cost`` is
    the engine's (``option_is_affordable``), read by no AI hook here.
    """

    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.IMPLICIT

    def troops(self) -> int:
        """The ability's troop count (the line's ``AbilityTroops``; B1's
        encoding of the spec's ``(Troops n)`` ctor attribute)."""

        return self.owner.int_attr("AbilityTroops")


@port(_AS + "RecallSpyCostAbility")
class RecallSpyCostAbility(_ScoutsLineAbility):
    """``RecallSpy(n)`` cost: one per Spy recalled (scouts.md §1, §2.3).

    Precedent ``Recall2SpiesVPAbility`` (generic §21: ``2·RecallSpyValue``).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{RecallSpyValue().Sum "Scouts Recall Spy"}``."""

        v = Summer()
        v.add("Scouts Recall Spy", p.recall_spy_value().sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecallSpyEvaluator`` (influence §2.5): ``GetRecallSpy`` over the
        SPY targets, ``UpdateTargets(v + 100.0, [spy])``."""

        spy, value = p.recall_spy(_targets(request, Kind.SPY))
        if spy is None:
            return Answer(0.0, None, "Scouts Recall Spy | none")
        return Answer(value + 100.0, ((spy.ref,),), f"Scouts Recall Spy {spy.ref}")


@port(_AS + "DiscardCostAbility")
class DiscardCostAbility(_ScoutsLineAbility):
    """``DiscardFromHand(n)`` cost (scouts.md §1, §2.3, D4): Corrinth City
    Agent / Delivery Agreement precedent (imperium-a §2.8, §2.11)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{DiscardValue "Scouts Discard"}``."""

        v = Summer()
        v.add("Scouts Discard", p.discard_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChooseDiscardEvaluator``: ``GetDiscardOrder(P, targets, false)
        .First()`` at 1.0."""

        order = p.discard_order(_targets(request, Kind.CARD), False)
        if not order:
            return Answer(0.0, None, "Scouts Discard | none")
        card = order[0]
        return Answer(1.0, ((card.ref,),), f"Scouts Discard {card.ref}")


@port(_AS + "TrashIntrigueCostAbility")
class TrashIntrigueCostAbility(_ScoutsLineAbility):
    """``TrashIntrigueCard()`` cost (scouts.md §1, §2.3, D6): Branching Path
    precedent (imperium-a §2.3; intrigues §4.5)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{TrashIntrigueValue()}`` (0 with a junk Intrigue in hand)."""

        v = Summer()
        v.add("Scouts Trash Intrigue", p.trash_intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Shuffled INTRIGUE targets, 5.0 for ``IsBadIntrigue`` else 1.0,
        first sticks / strict (Branching Path's pick)."""

        return _trash_intrigue_choice(p, request, "Scouts Trash Intrigue")


@port(_AS + "TrashFromHandCostAbility")
class TrashFromHandCostAbility(_ScoutsLineAbility):
    """Mandatory hand trash (Funeral Rites, Termination Request; scouts.md
    §1, §2.3, D5 as revised by plan §11.7).

    A junk card in hand (``GetCardToTrash(hand, 1.0)`` finds one, the
    ``TrashAbility`` threshold) is priced ``TrashCardValue`` and trashed;
    otherwise the card with the smallest ``AcquireValue`` is the forced
    loss, priced ``-AcquireValue`` (plan §11.7: the app's ``TrashValue``
    cannot price losing a good card for good; holding it is worth its
    ``AcquireValue``).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        hand = g._hand_cards(p)
        card, _ = p.card_to_trash(hand, 1.0)
        if card is not None:
            v.add("Scouts Trash Junk", p.trash_card_value())
            return v
        if hand:
            least = min(p.acquire_value(c).sum for c in hand)
            v.add("Scouts Trash Least Card", -least)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        cards = _targets(request, Kind.CARD)
        card, value = p.card_to_trash(cards, 1.0)
        if card is not None:
            return Answer(value, ((card.ref,),), f"Scouts Trash junk {card.ref}")
        loss = least_loss([(c, -p.acquire_value(c).sum) for c in cards], p.rng)
        if loss is None:
            return Answer(0.0, None, "Scouts Trash | no card")
        least, value = loss
        return Answer(value, ((least.ref,),), f"Scouts Trash least {least.ref}")


@port(_AS + "LoseGarrisonTroopsCostAbility")
class LoseGarrisonTroopsCostAbility(_ScoutsLineAbility):
    """``LoseGarrisonTroops(1)`` cost (scouts.md §1, §2.3, D7)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{GetTroopValue(-1, false) "Scouts Lose Troop"}``."""

        v = Summer()
        v.add("Scouts Lose Troop", p.troop_value(-1, False))
        return v


@port(_AS + "RecruitToConflictAbility")
class RecruitToConflictAbility(_ScoutsLineAbility):
    """``RecruitToConflict(n)`` (Shadow Warfare; scouts.md §1, §2.3, D11)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Gate > 0 ? {GetTroopValue(Troops, false)} : {}``."""

        v = Summer()
        if p.scouts_conflict_troops_gate() > 0:
            v.add("Scouts Troops To Conflict", p.troop_value(self.troops(), False))
        return v


@port(_AS + "ParkedTroopsToConflictAbility")
class ParkedTroopsToConflictAbility(_ScoutsLineAbility):
    """Mission troops that reach the Conflict on the seat's visit (Security
    Detail, Weirding Warfare, Send for Aid; scouts.md §2.3, D10, D44)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Gate > 0 ? {UTr(Troops)} : {}``."""

        v = Summer()
        if p.scouts_conflict_troops_gate() > 0:
            v.add(
                "Scouts Parked Troops To Conflict",
                p.uncapped_troop_value(self.troops()),
            )
        return v


@port(_AS + "ParkedTroopsToGarrisonAbility")
class ParkedTroopsToGarrisonAbility(_ScoutsLineAbility):
    """Mission troops recruited to the garrison on the visit (Fedaykin
    Assistance, Coordinate With The Emperor; scouts.md §2.3, D10)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{UTr(Troops)}``."""

        v = Summer()
        v.add("Scouts Parked Troops To Garrison", p.uncapped_troop_value(self.troops()))
        return v


def _lowest_tracks(p: Profile) -> list[str]:
    """``FactionList`` tracks where P's influence is minimal and can still
    gain (``rules/scouts_effects.py`` ``_lowest_factions``)."""

    lowest = min(_influence(p, f) for f in FACTIONS)
    return [
        f for f in FACTIONS if _influence(p, f) == lowest and lowest < MAX_INFLUENCE
    ]


def _highest_tracks(p: Profile) -> list[str]:
    """Tracks where P's influence is maximal and above 0 (``rules/
    scouts_effects.py`` ``highest_factions``)."""

    highest = max(_influence(p, f) for f in FACTIONS)
    if highest == 0:
        return []
    return [f for f in FACTIONS if _influence(p, f) == highest]


def _first_max(values: Sequence[float]) -> float:
    """``Enumerable.Max`` keeping the first maximum (0 when empty)."""

    if not values:
        return 0.0
    best = values[0]
    for value in values[1:]:
        if value > best:
            best = value
    return best


@port(_AS + "GainLowestInfluenceAbility")
class GainLowestInfluenceAbility(_ScoutsLineAbility):
    """``GainLowestInfluence()`` (Covert Operation 3; scouts.md §1, §2.3,
    D47): ``ChooseFactionInfluenceEvaluator`` over the lowest tracks."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Max over lowest of GetGainInfluenceValue(f, 1)`` (first max)."""

        v = Summer()
        tracks = _lowest_tracks(p)
        if tracks:
            values = [p.gain_influence_value(f, 1, -1, False).sum for f in tracks]
            v.add("Scouts Gain Lowest Influence", _first_max(values))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``G(f, 1) + 100`` per offered TRACK, first strictly best."""

        return choose_faction_influence(p, _targets(request, Kind.TRACK))


@port(_AS + "LoseHighestInfluenceAbility")
class LoseHighestInfluenceAbility(_ScoutsLineAbility):
    """``LoseHighestInfluence()`` (Political Equilibrium; scouts.md §1, §2.3,
    §3.2, D16): the loss side of ``GetBestInfluenceExchange``."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Max over highest of GetGainInfluenceValue(f, -1)`` (least
        negative, first max); ``{}`` with no track above 0."""

        v = Summer()
        tracks = _highest_tracks(p)
        if tracks:
            values = [p.gain_influence_value(f, -1, -1, False).sum for f in tracks]
            v.add("Scouts Lose Highest Influence", _first_max(values))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Least loss: shuffled TRACK targets, ``G(f, -1)``, first call sticks,
        strict."""

        return lose_influence_answer(p, [t.ref for t in _targets(request, Kind.TRACK)])


def lose_influence_answer(p: Profile, factions: Sequence[str]) -> Answer:
    """``LoseHighestInfluenceAbility.E`` over our faction ids (scouts.md §3.2):
    the least loss ``G(f, -1)`` after a shuffle; ``((faction,),)``.

    The window then takes the **first** offered action of that faction
    (``scouts_lose_influence_to``'s Alliance recipient: plan §11.5, D17).
    """

    shuffled = list(factions)
    p.rng.shuffle(shuffled)
    choice = _Choice()
    for faction in shuffled:
        choice.update_targets(
            p.gain_influence_value(faction, -1, -1, False).sum, (faction,)
        )
    return choice.answer("Scouts Lose Influence")


@port(_AS + "AcquireReserveToHandAbility")
class AcquireReserveToHandAbility(_ScoutsLineAbility):
    """``AcquireReserveCardToHand(c)`` (Moment of Revelation; scouts.md §1,
    §2.3, D12). ``ReferencedArchetypeIDs`` = the Reserve card (Prepare the
    Way)."""

    def _card(self, p: Profile) -> Entity | None:
        stacks = dict(p.ctx.reserve_stacks)
        for short in self.owner.list_attr("ReferencedArchetypeIDs"):
            for reserve_id in reserve_ids_of(short):
                if stacks.get(reserve_id, 0) > 0:
                    return reserve_card(reserve_id)
        return None

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``stack not empty ? {AcquireValue(card, P).Sum "Acquire",
        CardDrawValue "To Hand"} : {}``."""

        v = Summer()
        card = self._card(p)
        if card is not None:
            v.add("Acquire", p.acquire_value(card).sum)
            v.add("To Hand", p.card_draw_value())
        return v


@port(_AS + "HelixSpiceAbility")
class HelixSpiceAbility(_ScoutsLineAbility):
    """``GainSpiceWithHelixBonus()`` (Offworld Operation 1; scouts.md §1,
    OQ-089 (b))."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{GetSpiceValue(P.GeneticMarkers >= 1 ? 2 : 1)}`` (printed
        amounts of the content's ``GainSpiceWithHelixBonus``)."""

        amount = (
            HELIX_SPICE.helix_spice
            if p.ctx.genetic_markers() >= 1
            else HELIX_SPICE.spice
        )
        v = Summer()
        v.add("Scouts Helix Spice", p.spice_value(amount))
        return v


@port(_AS + "GainTwoTleilaxuAbility")
class GainTwoTleilaxuAbility(_ScoutsLineAbility):
    """``AdvanceTleilaxu(2)`` (Tleilaxu Relations; scouts.md §1, §2.3):
    precedent ``PaySolariForTleilaxuInfluence``'s ``TleilaxuValue(2)``."""

    def meets_cost(self, p: Profile) -> bool:
        """``CanGainTleilaxuInfluence`` (rank below 7; the Immortality port's
        ``_can_gain_tleilaxu``)."""

        return _can_gain_tleilaxu(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{TleilaxuValue(2).Sum}``."""

        v = Summer()
        v.add("Scouts Two Tleilaxu", p.tleilaxu_value(2).sum)
        return v


@port(_AS + "ShieldWallReturnAbility")
class ShieldWallReturnAbility(_ScoutsLineAbility):
    """Rebuild Infrastructure's Shield Wall return (scouts.md §1, §2.3, D28)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{-BlowWallValue().Sum "Shield Wall Returned"}``."""

        v = Summer()
        v.add("Shield Wall Returned", -p.blow_wall_value().sum)
        return v


# ---------------------------------------------------------------------------
# §2.3, §4 Board abilities
# ---------------------------------------------------------------------------


def _imperial_reserve_goods(p: Profile, space_id: str) -> list[tuple[str, int]]:
    """Imperial Reserve's goods waiting on ``space_id`` (resource, amount), in
    the goods placement order (spice then Solari)."""

    return [
        (resource, amount)
        for mission_id, where, resource, amount, _seat in p.ctx.scouts_goods
        if where == space_id
        and amount > 0
        and MISSIONS_BY_ID[mission_id].kind is MissionKind.IMPERIAL_RESERVE
    ]


@port(_AS + "MissionPiecesSpaceAbility")
class MissionPiecesSpaceAbility(g.DeferredAbility):
    """What a visit to this space collects for P (scouts.md §2.3, §4.1, D46).

    A ``DeferredAbility``, not a ``SpaceAbility`` (that would add the
    generic space value a second time, board §1.4.10); owner = the space.
    Timing None; runs immediately (engine-order state 400, the space's own
    gains); Explicit when Imperial Reserve's two goods both wait, else
    Implicit. ``Cost`` = ``mission_collectable`` gates the prompt only; V is
    not gated by it, as ``SpaceAbility``'s V is not.
    """

    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        if len(_imperial_reserve_goods(p, self.owner.ref)) > 1:
            return SelectionMode.EXPLICIT
        return SelectionMode.IMPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.mission_collectable(self.owner.ref)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """§4.1: P's parked troops here (``CTp`` to the Conflict, ``UTr`` to
        the garrison), the goods for P or anyone (Imperial Reserve: the
        better one of its two, OQ-078), and one face-down card (Contract
        ``KC``, Intrigue ``Int``; identities hidden). ``{}`` with nothing."""

        v = Summer()
        space_id = self.owner.ref
        seat = p.ctx.seat
        for mission_id, owner, location, troops in p.ctx.scouts_parked:
            if owner != seat or location != space_id:
                continue
            if not mission_collected_on_visit(mission_id):
                continue
            if mission_troops_to_conflict(mission_id):
                v.add(
                    "Mission Troops To Conflict", p.parked_conflict_troop_value(troops)
                )
            else:
                v.add("Mission Troops To Garrison", p.uncapped_troop_value(troops))
        reserve: list[float] = []
        for mission_id, location, resource, amount, owner in p.ctx.scouts_goods:
            if location != space_id or owner not in (-1, seat) or amount <= 0:
                continue
            if not mission_collected_on_visit(mission_id) or resource == "marker":
                continue
            attr = RESOURCE_ATTRS.get(resource)
            if attr is None:
                continue
            price = p.resource_value(attr, amount)
            if MISSIONS_BY_ID[mission_id].kind is MissionKind.IMPERIAL_RESERVE:
                reserve.append(price)
            else:
                v.add("Mission Goods", price)
        if reserve:
            v.add("Imperial Reserve", max(reserve))
        card = next(
            (
                mission_id
                for mission_id, location, count in p.ctx.scouts_board_card_counts
                if location == space_id
                and count > 0
                and mission_collected_on_visit(mission_id)
            ),
            None,
        )
        if card is not None:
            if MISSIONS_BY_ID[card].kind is MissionKind.CHOAM_RESEARCH:
                v.add("Mission card", p.gain_contract_value().sum)
            else:
                v.add("Mission card", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """§2.3 / §3.5 (D26): with Imperial Reserve's two goods, ``FSB`` of
        ``("spice", Spi(1))``, ``("solari", Sol(2))`` in placement order
        (spice on ties); otherwise ``Upd(V.Sum, [""])``. The response is the
        ``scouts_collect_mission`` choice."""

        goods = _imperial_reserve_goods(p, self.owner.ref)
        if len(goods) > 1:
            choice = _Choice()
            for resource, amount in goods:
                attr = RESOURCE_ATTRS[resource]
                choice.update_targets(p.resource_value(attr, amount), (resource,))
            return choice.answer("Imperial Reserve")
        value = self.value_for_player(p, ()).sum
        return Answer(value, (("",),), "Mission pieces")


@port(_AS + "DesertRidingAbility")
class DesertRidingAbility(HaggaBasinUprisingDeferredAbility):
    """Hagga Basin while Desert Riding's Maker Hooks token is out (scouts.md
    §2.3, §4.2, D27): a third option, the token at ``MakerHooksValue`` (the
    Sietch Tabr hooks price, influence §5.2), for a seat without hooks.

    Replaces ``HaggaBasinUprisingDeferredAbility`` on the space whenever
    Scouts is on (``catalog.space_entity``); without the token it is the base
    ability. Option 2 = ``take_desert_riding_hooks``.
    """

    def _token_option(self, p: Profile) -> bool:
        return p.ctx.desert_riding_token() is not None and not p.ctx.me.maker_hooks

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """Base V, plus ``MakerHooksValue - sV`` when the hooks are worth more
        than the spice (V becomes ``max(Spi(2), H)`` for a hookless seat)."""

        s = super().value_for_player(p, with_entities)
        if self._token_option(p):
            spice = self._spice_value(p)
            hooks = p.maker_hooks_value()
            if hooks > spice:
                s.add("Desert Riding", hooks - spice)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Base E, then option 2 at ``MakerHooksValue`` when strictly greater
        (spice wins ties)."""

        stored = super().evaluate(p, request)
        if self._token_option(p):
            hooks = p.maker_hooks_value()
            if hooks > stored.value:
                return Answer(hooks, ((2,),), "Desert Riding Hooks")
        return stored


@port(_AS + "SubcommitteeOfferAbility")
class SubcommitteeOfferAbility(g.DeferredAbility):
    """The subcommittee a new council seat may join (scouts.md §2.3, §3.3,
    §4.5; D23, D24): on High Council (overlay), and the PROMPT source of
    Corrinth City's Reveal-turn offer.

    Optional; a post-action / post-reveal key (``CanRunImmediately`` false,
    overriding the common default). Timing Agent (the space's; the Reveal
    offer is asked through the same ``evaluate``). ``Cost`` = choosing is
    legal (>= 1 joinable now) gates the prompt key only, not V.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def can_run_immediately(self, p: Profile) -> bool:
        return False

    def meets_cost(self, p: Profile) -> bool:
        """``choose_subcommittee`` is legal (``rules/scouts_effects.py``
        ``legal_subcommittee_choice_actions``)."""

        exclude = p.ctx.pending_subcommittee_exclude()
        return exclude is not None and bool(p.ctx.joinable_subcommittees(exclude))

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``{subcommittee_opportunity(excl)}`` unless P holds the seat;
        ``excl`` = this space (the Agent being placed is the one
        Contingencies may not recall)."""

        v = Summer()
        if not p.ctx.me.high_council:
            v.add(
                "Subcommittee Opportunity", p.subcommittee_opportunity(self.owner.ref)
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``mc`` over the joinable subcommittees' line values with the open
        offer's ``exclude_space`` (``pending_subcommittee_exclude``); the
        empty answer declines (Optional). ``((subcommittee_id,),)``."""

        exclude = p.ctx.pending_subcommittee_exclude()
        if exclude is None:
            return Answer(0.0, None, "Subcommittee | no offer")
        return SubcommitteeEvaluator.evaluate(p, p.ctx.joinable_subcommittees(exclude))


@port(_AS + "CorrinthCityRevealScoutsAbility")
class CorrinthCityRevealScoutsAbility(CorrinthCityRevealAbility):
    """Corrinth City's Reveal with the subcommittee opportunity (scouts.md
    §2.3, §4.5, D24): E adds ``subcommittee_opportunity("")`` to option 1's
    summer while P can take the seat; V unchanged (its seat test is
    inverted: the opportunity is 0 in the seated branch it values).

    Not attached by any archetype overlay: the Reveal window uses it in place
    of ``CorrinthCityRevealAbility`` in Scouts games.
    """

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _FirstChoice()
        choice.update(p.solari_value(5), ((0,),), "Corrinth City | 5 Solari")
        if p.ctx.me.resources.solari >= 5:
            s = Summer()
            s.add("5 SolariCost", p.solari_value(-5))
            s.add("High Council Seat", p.high_council_value())
            if not p.ctx.me.high_council:  # CanTakeHighCouncilSeat
                s.add("Subcommittee Opportunity", p.subcommittee_opportunity(""))
            choice.update(s.sum, ((1,),), "Corrinth City | High Council Seat")
        return choice.answer("Corrinth City")


# ---------------------------------------------------------------------------
# §2.4 Evaluators (``worm.canis.ai.evaluators.AppStyle.Scouts.*``)
# ---------------------------------------------------------------------------


class ScoutsChoiceEvaluator:
    """``scouts_choice`` (scouts.md §3.1; D15, D40): an event's or sale's
    lines, Rebuild Infrastructure, a revealed secret pick's only line.

    ``v_i = L(line(item, i))`` per offered line. With a pass: ``mc``; None ->
    pass (empty answer). Mandatory: ``mc`` if any ``v_i > 0``; otherwise the
    Influence Reduction family's least loss, the other items
    ``DefaultRandomChoice``. Answer ``((line,),)``.
    """

    APP_CLASS: ClassVar[str] = _EV + "ScoutsChoiceEvaluator"

    @staticmethod
    def evaluate(
        p: Profile, item_id: str, lines: Sequence[int], *, passable: bool
    ) -> Answer:
        values = [(line, p.scouts_item_line_value(item_id, line)) for line in lines]
        label = f"Scouts choice {item_id}"
        if passable:
            chosen = make_choice_of(values, p.rng)
            if chosen is None:
                return Answer(0.0, None, f"{label} | pass")
            return Answer(chosen[1], ((chosen[0],),), label)
        if not values:
            return Answer(0.0, None, f"{label} | no line")
        if any(value > 0.0 for _, value in values):
            chosen = make_choice_of(values, p.rng)
            assert chosen is not None
            return Answer(chosen[1], ((chosen[0],),), label)
        if item_id in INFLUENCE_REDUCTION_EVENTS:
            loss = least_loss(values, p.rng)
            assert loss is not None
            return Answer(loss[1], ((loss[0],),), f"{label} | least loss")
        return _forced_answer(p, values, label)


class SubcommitteeEvaluator:
    """Subcommittee join (scouts.md §3.3; D23): ``mc`` over the joinable
    subcommittees' line values; None declines. No deny or wait term (plan
    §11.5). Answer ``((subcommittee_id,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "SubcommitteeEvaluator"

    @staticmethod
    def evaluate(p: Profile, subcommittees: Sequence[str]) -> Answer:
        values = [(s, p.scouts_item_line_value(s, 0)) for s in subcommittees]
        chosen = make_choice_of(values, p.rng)
        if chosen is None:
            return Answer(0.0, None, "Subcommittee | decline")
        return Answer(chosen[1], ((chosen[0],),), f"Subcommittee {chosen[0]}")


def mission_join_line(mission_id: str, target: str) -> int:
    """The join line of ``target`` (scouts.md §3.4, §5.2): CHOAM Escort
    ``"recruit"`` -> 0, a Contract -> 1; every other mission's ``""`` -> 0."""

    if MISSIONS_BY_ID[mission_id].kind is MissionKind.CHOAM_ESCORT:
        return 0 if target == "recruit" else 1
    return 0


class MissionJoinEvaluator:
    """``scouts_mission`` (scouts.md §3.4; D25, D45, D49): each legal target
    at ``J(t) = L(line(mission, t))``; with top-up counts legal, the troop
    way that needs them at ``J(troop line, troops priced UTr) +
    Spec(-short)``. ``mc``; None declines.

    Answer ``(("scouts_join_mission", target),)`` or
    ``(("scouts_return_specimens", short),)`` (``short`` = the largest
    offered count; after the top-up the frame asks again and the join is
    legal).
    """

    APP_CLASS: ClassVar[str] = _EV + "MissionJoinEvaluator"

    @staticmethod
    def evaluate(
        p: Profile, mission_id: str, targets: Sequence[str], top_up: int = 0
    ) -> Answer:
        seat = p.ctx.seat
        candidates: list[tuple[tuple[str, str | int], float]] = []
        for target in targets:
            line = scouts_line_entity(
                mission_id, mission_join_line(mission_id, target), seat
            )
            candidates.append(
                (("scouts_join_mission", target), p.scouts_line_value(line).sum)
            )
        if top_up > 0:
            troop_target = (
                "recruit"
                if MISSIONS_BY_ID[mission_id].kind is MissionKind.CHOAM_ESCORT
                else ""
            )
            line = scouts_line_entity(
                mission_id, mission_join_line(mission_id, troop_target), seat
            )
            value = p.scouts_line_value(line, uncapped_troops=True).sum
            value += p.specimen_value(-top_up)
            candidates.append((("scouts_return_specimens", top_up), value))
        chosen = make_choice_of(candidates, p.rng)
        if chosen is None:
            return Answer(0.0, None, f"Mission {mission_id} | decline")
        return Answer(chosen[1], (chosen[0],), f"Mission {mission_id}")


class SecretPickEvaluator:
    """``scouts_secret`` (scouts.md §3.6; D13, D14, D40): pick ``k`` worth
    ``later(L_k, d_k)`` with ``L_k = max(0, L)`` for a line with a cost (it
    resolves as an optional only-line). ``mc``; forced: none > 0 ->
    ``DefaultRandomChoice``. Prices use the current state. Answer
    ``((pick,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "SecretPickEvaluator"

    @staticmethod
    def evaluate(p: Profile, event_id: str, picks: Sequence[int]) -> Answer:
        choices = EVENTS_BY_ID[event_id].secret_choices
        values: list[tuple[int, float]] = []
        for pick in picks:
            secret = choices[pick]
            line = p.scouts_item_line_value(event_id, pick)
            if secret.option.costs:
                line = max(0.0, line)
            values.append((pick, p.scouts_later(line, secret.delay)))
        return _forced_answer(p, values, f"Secret pick {event_id}")


def bid_answer(p: Profile, bid: int, label: str) -> Answer:
    """The two-step bid (scouts.md §3.7): own bid == ``bid`` (none counts as
    0) -> ``confirm_scouts_bid``; else ``scouts_bid(count=bid)``."""

    own = p.ctx.own_scouts_bid()
    if own == bid or (own < 0 and bid == 0):
        return Answer(float(bid), (("confirm_scouts_bid",),), f"{label} | confirm")
    return Answer(float(bid), (("scouts_bid", bid),), f"{label} | bid {bid}")


class SealedBidEvaluator:
    """Sealed auctions (scouts.md §3.7; D18, D19): ``V = L(first-place
    line)``; ``b* = max{b in [1, cap] : V + Cur(-b) > 0}``, else 0 (the
    currency is the auction's: Solari for every sealed auction)."""

    APP_CLASS: ClassVar[str] = _EV + "SealedBidEvaluator"

    @staticmethod
    def best_bid(p: Profile, auction_id: str, cap: int) -> int:
        value = p.scouts_item_line_value(auction_id, 0)
        attr = RESOURCE_ATTRS[AUCTIONS_BY_ID[auction_id].currency]
        best = 0
        for bid in range(1, cap + 1):
            if value + p.resource_value(attr, -bid) > 0.0:
                best = bid
        return best

    @staticmethod
    def evaluate(p: Profile, auction_id: str, cap: int) -> Answer:
        bid = SealedBidEvaluator.best_bid(p, auction_id, cap)
        return bid_answer(p, bid, f"Sealed bid {auction_id}")


class MercenariesBidEvaluator:
    """Mercenaries (scouts.md §3.7; D20): ``M(b) = CTp(b) + Spi(-b) + (b >
    supply ? Spec(-(b - supply)) : 0)`` (auto top-up, OQ-074 (a));
    ``b* = max{b in [1, cap] : M(b) > 0}``, else 0."""

    APP_CLASS: ClassVar[str] = _EV + "MercenariesBidEvaluator"

    @staticmethod
    def bid_value(p: Profile, bid: int) -> float:
        supply = p.ctx.me.troops_supply
        value = p.parked_conflict_troop_value(bid) + p.spice_value(-bid)
        if bid > supply:
            value += p.specimen_value(-(bid - supply))
        return value

    @staticmethod
    def best_bid(p: Profile, cap: int) -> int:
        best = 0
        for bid in range(1, cap + 1):
            if MercenariesBidEvaluator.bid_value(p, bid) > 0.0:
                best = bid
        return best

    @staticmethod
    def evaluate(p: Profile, cap: int) -> Answer:
        return bid_answer(p, MercenariesBidEvaluator.best_bid(p, cap), "Mercenaries")


def scouts_bid_evaluate(p: Profile, cap: int) -> Answer:
    """The ``scouts_bid`` frame's answer for the running auction
    (``AppContext.scouts_item``): Mercenaries or a sealed auction."""

    auction_id = p.ctx.scouts_item
    if auction_id == "mercenaries":
        return MercenariesBidEvaluator.evaluate(p, cap)
    return SealedBidEvaluator.evaluate(p, auction_id, cap)


class MercenariesRetreatEvaluator:
    """``scouts_retreat`` (scouts.md §3.8; D21): ``min(GetTroopsToRetreat(max),
    max)`` with ``max`` the largest legal count. Answer ``((count,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "MercenariesRetreatEvaluator"

    @staticmethod
    def evaluate(p: Profile, max_count: int) -> Answer:
        count = min(p.troops_to_retreat(max_count), max_count)
        count = max(count, 0)
        return Answer(1.0, ((count,),), f"Mercenaries retreat {count}")


class CriticalMomentCallEvaluator:
    """``scouts_call`` (scouts.md §3.9; D22): ``V = max over the revealed
    cards of A(c) + CDV``; ``r = max{b >= 1 : V + Spi(-b) > 0}``; the largest
    legal amount <= r, else 0 (pass). Answer ``((amount,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "CriticalMomentCallEvaluator"

    @staticmethod
    def evaluate(p: Profile, amounts: Sequence[int]) -> Answer:
        cards = [card_entity(c) for c in p.ctx.scouts_market_cards]
        if not cards:
            return Answer(0.0, ((0,),), "Critical Moment | no card")
        worth = _first_max([p.acquire_to_hand_value(c) for c in cards])
        reservation = 0
        for bid in range(1, max(amounts, default=0) + 1):
            if worth + p.spice_value(-bid) > 0.0:
                reservation = bid
        call = max((a for a in amounts if 0 < a <= reservation), default=0)
        return Answer(worth, ((call,),), f"Critical Moment call {call}")


class CriticalMomentTakeEvaluator:
    """``scouts_market`` (scouts.md §3.10; D22, D40): ``u_s = A(card) + CDV``
    per slot. Place 0 (forced): ``mc``; none > 0 -> ``DefaultRandomChoice``.
    Place 1: ``s = mc``; take it iff ``u_s + Spi(-amount) > 0``, else (and
    for None) decline (empty answer). Answer ``((slot,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "CriticalMomentTakeEvaluator"

    @staticmethod
    def evaluate(p: Profile, slots: Sequence[int], amount: int, place: int) -> Answer:
        market = p.ctx.scouts_market_cards
        values = [
            (slot, p.acquire_to_hand_value(card_entity(market[slot]))) for slot in slots
        ]
        if place == 0:
            return _forced_answer(p, values, "Critical Moment take")
        chosen = make_choice_of(values, p.rng)
        if chosen is None:
            return Answer(0.0, None, "Critical Moment | decline")
        slot, worth = chosen
        net = worth + p.spice_value(-amount)
        if net > 0.0:
            return Answer(net, ((slot,),), f"Critical Moment buy {slot}")
        return Answer(0.0, None, "Critical Moment | decline")


class FourBonusEvaluator:
    """``scouts_four_bonus`` (scouts.md §3.11; D38, D40): ``mc`` over ``TB(f)``
    (Emperor Spy, Spacing Guild 3 Solari, Bene Gesserit Intrigue, Fremen 1
    water); forced: none > 0 -> ``DefaultRandomChoice``. Answer
    ``((faction,),)``."""

    APP_CLASS: ClassVar[str] = _EV + "FourBonusEvaluator"

    @staticmethod
    def evaluate(p: Profile, factions: Sequence[str]) -> Answer:
        values = [(f, p.track_bonus_value(f)) for f in factions]
        return _forced_answer(p, values, "Friends Everywhere bonus")


def line_top_up_answer(counts: Sequence[int]) -> Answer:
    """``scouts_return_specimens`` inside a line's recruit (scouts.md §3.2,
    D39): the largest offered count (``ReturnSpecimenAbility`` returns
    exactly the shortfall, immortality §3.4). Answer ``((count,),)``."""

    count = max(counts, default=0)
    return Answer(1.0, ((count,),), f"Scouts top-up {count}")
