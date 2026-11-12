"""Card-specific abilities of Uprising Imperium, reserve and starter cards A–L.

Spec: spec/imperium-a.md (with 17-card-followups.md, 09-card-ability-hooks.md §3 and
their Errata).

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``), so the app's
inheritance (``DangerousRhetoricAbility`` -> ``GainAnyInfluenceAgentAbility``
-> ``GainAnyInfluenceAbility`` -> ``DeferredAbility``) is the Python MRO.

Classes of these cards that ``generic.py`` already ports (and that are not
re-registered here): ``CargoRunner2ContractsDrawAbility``,
``CargoRunner4ContractsDrawAbility`` (Cargo Runner),
``SpacingGuildDiscardDrawAbility`` (Guild Envoy),
``BeneGesseritInfluenceDrawAbility`` (Hidden Missive) and
``BeneGesseritDrawAbility`` (In High Places). Classes shared with an M–Z card
whose first user is A–L live here: ``SouthernEldersRevealAbility`` and
``SouthernEldersBondAbility`` (Chani; Southern Elders),
``DeliveryAgreementRevealAbility`` (Delivery Agreement; Priority Contracts'
reveal subclasses it and overrides ``spice_amount``). The promo Arrakis Revolt
(``ability.activated.promo.arrakis_revolt``) is out of scope.

Request / answer encoding (``abilities/base``, as in ``generic.py``): the
candidates of a prompt are ``request.infos[i]`` in the order the app's
``Targets`` yields its target infos (``entities`` for entity targets,
``options`` for custom choices). ``Answer.response is None`` = nothing stored
(value 0); ``()`` = "use" with no sub-targets
(``UpdateSelectionTargets(v, src, null)``); ``((ref, ...), ...)`` = the chosen
refs / option indices per target info.

Engine-side members: ``timing``, ``selection_mode(p)``,
``can_run_immediately(p)`` / ``always_run_immediately``, ``defer_value(p)``
(inherited), ``meets_cost(p)`` where an AI hook calls ``MeetsCost``.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    ResponseItem,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    BondAbility,
    DeferredAbility,
    GainAnyInfluenceAgentAbility,
    PlaceSpyAbility,
    RevealAbility,
    TriggeredAbility,
    card_factions,
    collect_first,
    contract_evaluate,
)
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    card_entity,
    conflict_entity,
    intrigue_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.registry.board import ALL_OBSERVATION_POSTS

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ``Factions.None`` as ``gain_influence_value`` spells it (the value of
# ``profile.influence.NO_FACTION``; importing the profile here would cycle).
_ANY_FACTION = "none"
_APP_TO_FACTION = {app: ours for ours, app in FACTION_NAMES.items()}
_POST_SPACES: dict[str, tuple[str, ...]] = {
    post.post_id: tuple(post.connected_space_ids) for post in ALL_OBSERVATION_POSTS
}

_AA = "ability.activated."
_PA = "ability.play."
_TA = "ability.triggered."


# ---------------------------------------------------------------------------
# Honest reads (AppContext rules) and small app helpers
# ---------------------------------------------------------------------------


def _hand(p: Profile) -> list[Entity]:
    """``P.Hand.children`` / ``P.HandCards()`` (own hand, in hand order)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.hand]


def _in_play(p: Profile) -> list[Entity]:
    """``P.AllCardsInPlay`` (our ``in_play``: PlayArea and ActiveAgentArea)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.me.in_play]


def _intrigue_hand(p: Profile) -> list[Entity]:
    """``P.IntrigueHand.children.OfType<IntriguePlayable>()``."""

    return [intrigue_entity(i, p.ctx.seat) for i in p.ctx.intrigue_cards]


def _targets(request: Request, kind: Kind, index: int = 0) -> list[Entity]:
    """``choice.GetTargets(this).OfType<T>()``: one target info's entities."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


def _has_faction(card: Entity, faction: str) -> bool:
    """``card.FactionsList.Contains(f)`` (app faction name)."""

    return faction in card_factions(card)


def _is_bad_intrigue(p: Profile, card: Entity) -> bool:
    """``IntriguePlayable.IsBadIntrigue(match, P)``.

    ``Abilities.OfType<IntrigueAbility>().Any(a => a.IsBadIntrigue(match,
    P))`` (intrigues.md §4.5). Like ``bad_intrigue_cards_in_hand``, an
    intrigue port answers through an ``is_bad_intrigue(profile)`` hook; a port
    without it (the ``IntrigueAbility`` default) counts false.
    """

    for ability in abilities_of(card):
        hook = getattr(ability, "is_bad_intrigue", None)
        if callable(hook) and bool(hook(p)):
            return True
    return False


def _dmax(a: float, b: float) -> float:
    """``System.Math.Max(double, double)``: NaN wins, else the larger."""

    if a != a:
        return a
    if b != b:
        return b
    return a if a > b else b


def _hand_count(p: Profile) -> int:
    """``Player.HandCount``."""

    return len(p.ctx.hand)


def _conflict_units(p: Profile) -> int:
    """``P.ConflictUnits`` (R5 §4.5: troops + sandworms in the Conflict; with
    Bloodlines also Commanders and the Into the Fray Agent,
    bloodlines-systems.md §1.1, D1, plan §11.8)."""

    return p.conflict_unit_count()


def _deployed_spies(p: Profile) -> int:
    """``GetDeployedSpies(P).Count()`` / ``HasAtLeastSpiesOnBoard``."""

    return len(p.ctx.me.spy_post_ids)


def _is_maker_space(space: Entity) -> bool:
    """``EntityExtensions.IsMakerSpace``: ``BonusSpice``
    (``Nullable<int>``) has a value."""

    return space.has("BonusSpice")


def _can_deploy_sandworms(p: Profile) -> bool:
    """``Player.CanDeploySandworms``.

    ``CanDeploy && !Board.CurrentConflictBehindShieldWall``. ``CanDeploy``
 reads the player's ``Deployable`` attribute (unset = true),
    which only ``EmperorOfTheKnownUniverseSuppressAbility`` (not in a
    4-player Uprising game) writes: true here. ``CurrentConflictBehindShieldWall``
 = the board still has the Shield Wall and the current Conflict
    ``IsShieldWallConflict`` (its ``Tags`` hold ``ShieldWall``).
    """

    current = p.ctx.current_conflict_id
    if current is None or not p.ctx.shield_wall_present:
        return True
    conflict = conflict_entity(current, p.ctx.choam)
    return "ShieldWall" not in conflict.list_attr("Tags")


def _active_space(p: Profile) -> Entity | None:
    """``P.ActiveSpace.FirstOrDefault()``: the space of this Agent turn.

    Judgement: ours is the ``space_id`` of the seat's own open
    ``agent_effects`` frame (none outside an Agent turn).
    """

    context = p.ctx.own_frame_context("agent_effects")
    if context is None:
        return None
    space_id = context.get("space_id")
    if not isinstance(space_id, str) or not space_id:
        return None
    return space_entity(space_id, p.ctx.board)


class _Choice:
    """``AIChoiceSelectionWithTargets`` (value 0, empty response).

    ``UpdateSelectionTargets`` / ``UpdateSelectionResponses``
 replace the stored answer iff the value is strictly greater
    or the stored response is still empty: the first call always sticks.
    """

    def __init__(self) -> None:
        self.value = 0.0
        self.response: tuple[ResponseItem, ...] | None = None
        self.label = ""

    def update(
        self, value: float, response: tuple[ResponseItem, ...], label: str
    ) -> None:
        if self.response is None or value > self.value:
            self.value = value
            self.response = response
            self.label = label

    def answer(self, default_label: str) -> Answer:
        return Answer(self.value, self.response, self.label or default_label)


def _trash_intrigue_choice(p: Profile, request: Request, name: str) -> Answer:
    """The shared E of Branching Path and Junction Headquarters.

    ``BranchingPathAbility.Evaluate`` /
    ``JunctionHeadquartersAbility.Evaluate`` (imperium-a §2.3,
    §2.24; 17 §13): the ctx-only choice, the held intrigues of
    the target info shuffled (``ListUtil.Shuffle``), each one offered at 5.0
    when ``IsBadIntrigue`` else 1.0 (literals), first-sticks / strict update.
    """

    intrigues = _targets(request, Kind.INTRIGUE)
    shuffled = list(intrigues)
    p.rng.shuffle(shuffled)
    choice = _Choice()
    for intrigue in shuffled:
        value = 5.0 if _is_bad_intrigue(p, intrigue) else 1.0
        choice.update(value, ((intrigue.ref,),), f"{name} | trash {intrigue.ref}")
    return choice.answer(f"{name} | no intrigue")


# ---------------------------------------------------------------------------
# RevealAbility subclasses that change only the constructor (imperium-a §0.1)
# ---------------------------------------------------------------------------


@port(_PA + "uprising.bene_gesserit_operative_reveal")
class BeneGesseritOperativeRevealAbility(RevealAbility):
    """``ability.play.uprising.bene_gesserit_operative_reveal`` (§2.2).

    constructor (timing Reveal); it overrides only
    ``GetRevealPreviewValue`` (UI), so the AI sees ``RevealAbility``.
    """


@port(_PA + "uprising.calculus_of_power_reveal")
class CalculusofPowerRevealAbility(RevealAbility):
    """``ability.play.uprising.calculus_of_power_reveal`` (§2.4):
    ``GetRevealPreviewValue`` only (UI)."""


@port(_PA + "uprising.southern_elders_reveal")
class SouthernEldersRevealAbility(RevealAbility):
    """``ability.play.uprising.southern_elders_reveal`` (§2.7; Chani,
    Southern Elders): ``GetRevealPreviewValue`` only (UI)."""


@port(_PA + "uprising.desert_power_reveal")
class DesertPowerRevealAbility(RevealAbility):
    """``ability.play.uprising.desert_power_reveal`` (§2.14):
    ``GetRevealPreviewValue`` only (UI). Desert Power has no
    printed reveal attributes in the app, so the box adds 0."""


@port(_PA + "original.in_high_places_reveal")
class InHighPlacesRevealAbility(RevealAbility):
    """``ability.play.original.in_high_places_reveal`` (§2.22):
    ``GetRevealPreviewValue`` only (UI)."""


@port(_PA + "uprising.interstellar_trade_reveal")
class InterstellarTradeRevealAbility(RevealAbility):
    """``ability.play.uprising.interstellar_trade_reveal`` (§2.23)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InterstellarTradeRevealAbility.ValueForPlayer``.

        ``RevealAbility.ValueForPlayer`` then ``+ GetPersuasionValue(
        P.GetContractsCompletedCount)`` "Interstellar Trade Reveal".
        """

        v = super().value_for_player(p, with_entities)
        completed = len(p.ctx.me.completed_contract_ids)
        v.add("Interstellar Trade Reveal", p.persuasion_value(completed))
        return v


# ---------------------------------------------------------------------------
# Triggered abilities
# ---------------------------------------------------------------------------


@port(_TA + "immortality.bene_gesserit_operative_triggered")
class BeneGesseritOperativeTriggeredAbility(TriggeredAbility):
    """``ability.triggered.immortality.bene_gesserit_operative_triggered``
    (§2.2). constructor: timing Reveal; ``ShouldExhaust``
 = false. No E (a trigger)."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneGesseritOperativeTriggeredAbility.ValueForPlayer``.

        ``GetDeployedSpies(P).Count() >= 2`` -> ``+ GetPersuasionValue(2)``.
        """

        v = Summer()
        if _deployed_spies(p) >= 2:
            v.add("Bene Gesserit Operative Persuasion", p.persuasion_value(2))
        return v


@port(_TA + "uprising.southern_elders_bond")
class SouthernEldersBondAbility(BondAbility):
    """``ability.triggered.uprising.southern_elders_bond`` (§2.7; Chani,
    Southern Elders). constructor: timing Reveal;
    ``BondFaction`` = Fremen; Cost = NoCostAction. P is the
    inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SouthernEldersBondAbility.ValueForPlayer``.

        Another Fremen card in hand or in play -> ``+ GetPersuasionValue(2)`` under the
        app's (wrong) label "Southern Elders water".
        """

        v = Summer()
        others = (*_hand(p), *_in_play(p))
        if any(c.ref != self.owner.ref and _has_faction(c, "Fremen") for c in others):
            v.add("Southern Elders water", p.persuasion_value(2))
        return v


@port(_TA + "uprising.ecological_testing_station_bond")
class EcologicalTestingStationBondAbility(BondAbility):
    """``ability.triggered.uprising.ecological_testing_station_bond``
    (§2.16). constructor: timing Reveal; ``BondFaction``
 = Fremen. P is the inherited ``BondAbility`` synergy."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EcologicalTestingStationBondAbility.ValueForPlayer``.

        Another Fremen card in hand or in play -> ``+ GetWaterValue(1)``.
        """

        v = Summer()
        others = (*_hand(p), *_in_play(p))
        if any(c.ref != self.owner.ref and _has_faction(c, "Fremen") for c in others):
            v.add("Ecological Testing Station Water", p.water_value(1))
        return v


@port(_PA + "original.interstellar_trade")
class InterstellarTradeAbility(TriggeredAbility):
    """``ability.play.original.interstellar_trade`` (a
    ``TriggeredAbility``; §2.23). constructor: timing Reveal. It
    fires on ``ContractCompleted`` while the card is in play
    (``GainPersuasion(1)``); no E/V/P override, so a contract completed in the
    Reveal turn is never valued."""

    timing: ClassVar[Timing] = Timing.REVEAL


@port(_TA + "uprising.interstellar_trade_triggered")
class InterstellarTradeTriggeredAbility(TriggeredAbility):
    """``ability.triggered.uprising.interstellar_trade_triggered``
    (§2.23). constructor: timing Reveal. No E/V/P override."""

    timing: ClassVar[Timing] = Timing.REVEAL


@port(_TA + "ix.imperial_bashar_reveal")
class ImperialBasharRevealAbility(TriggeredAbility):
    """``ability.triggered.ix.imperial_bashar_reveal`` (Leadership's
    reveal, §2.25). constructor: timing Reveal; Cost =
    ``IsInPlay``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialBasharRevealAbility.ValueForPlayer``.

        ``n = P.HandCards().Count(c => c != Owner && c.Strength() > 0)``, then always
        ``+ GetStrengthValue(n, false)``.
        """

        v = Summer()
        n = sum(
            1
            for c in _hand(p)
            if c.ref != self.owner.ref and c.int_attr("Strength") > 0
        )
        v.add("Imperial Bashar Reveal Strength", p.strength_value(n, False))
        return v


# ---------------------------------------------------------------------------
# Deferred abilities, by card
# ---------------------------------------------------------------------------


@port(_AA + "uprising.branching_path")
class BranchingPathAbility(DeferredAbility):
    """``ability.activated.uprising.branching_path`` (§2.3).

    constructor: timing Agent. Cost = BG alliance then an
    intrigue held. Targets: the held intrigues (max 1, min 0).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BranchingPathAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BranchingPathAbility.ValueForPlayer`` (§2.3).

        The visited space supplies the missing BG influence (``amount = 1``
        on a Bene Gesserit space); with intrigue held and the alliance had or
        reachable: ``+ TrashIntrigueValue()`` only when no held intrigue is
        bad, ``+ IntrigueValue``, ``+ GetSpiceValue(2)``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        amount = (
            1 if space is not None and space.attr("Faction") == "BeneGesserit" else 0
        )
        intrigues = _intrigue_hand(p)
        if intrigues and p.has_or_would_gain_alliance("bene_gesserit", amount):
            if all(not _is_bad_intrigue(p, i) for i in intrigues):
                v.add("Trash Intrigue", p.trash_intrigue_value())
            v.add("Draw Intrigue", p.intrigue_value())
            v.add("2 Spice", p.spice_value(2))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BranchingPathAbility.Evaluate`` (§2.3, 17 §13).

        ``request.infos[0]``: the held intrigues. A bad one (first in the
        shuffled order) at 5.0, else the first at 1.0.
        """

        return _trash_intrigue_choice(p, request, "Branching Path")


@port(_AA + "uprising.calculus_of_power_emperor")
class CalculusofPowerEmperorAbility(DeferredAbility):
    """``ability.activated.uprising.calculus_of_power_emperor`` (§2.4).

    constructor: timing Reveal. Cost =
    ``HasPlayedFactionCard(Emperor, owner)``. Targets: the other Emperor cards
    in play (forced, max 1).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CalculusofPowerEmperorAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CalculusofPowerEmperorAbility.ValueForPlayer`` (§2.4).

        Candidates: Emperor cards in play **and in hand** other than the owner. With a
        junk card (``GetCardToTrash(cands, 0.0)``) or any candidate costing < 4: ``+
        TrashCardValue`` (a gain) and ``+ GetStrengthValue(3, false)``.
        """

        v = Summer()
        cands = [
            c
            for c in (*_in_play(p), *_hand(p))
            if _has_faction(c, "Emperor") and c.ref != self.owner.ref
        ]
        card, _ = p.card_to_trash(cands, 0.0)
        if card is not None or any(c.int_attr("PersuasionCost") < 4 for c in cands):
            v.add("Trash Card", p.trash_card_value())
            v.add("3 Strength", p.strength_value(3, False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CalculusofPowerEmperorAbility.Evaluate`` (§2.4, 17 §7).

        ``request.infos[0]``: the other Emperor cards in play. ``GetCardToTrash(targets,
        0.0)`` (Uprising: never a match, value 0.0) plus ``GetStrengthValue(3, false)``;
        with no junk card the first target costing < 4, else nothing (value 0).
        """

        targets = _targets(request, Kind.CARD)
        card, tv = p.card_to_trash(targets, 0.0)
        s = Summer()
        s.add("Trash Value", tv)
        s.add("3 Strength", p.strength_value(3, False))
        if card is None:
            card = next((c for c in targets if c.int_attr("PersuasionCost") < 4), None)
            if card is None:
                return Answer(0.0, None, "Calculus of Power | no card")
        return Answer(s.sum, ((card.ref,),), f"Calculus of Power | {card.ref}")


@port(_AA + "ix.captured_mentat_agent")
class CapturedMentatAgentAbility(DeferredAbility):
    """``ability.activated.ix.captured_mentat_agent`` (§2.5).

    constructor: timing Agent. Cost = a card in hand.
    Targets: the hand (forced, max 1, min 1).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CapturedMentatAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CapturedMentatAgentAbility.ValueForPlayer``.

        ``P.HandCount >= 2`` (this card is still in hand) -> Discard, Draw,
        Intrigue and Buy Gains terms.
        """

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Captured Mentat Discard", p.discard_value())
            v.add("Captured Mentat Draw", p.card_draw_value())
            v.add("Captured Mentat Intrigue", p.intrigue_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CapturedMentatAgentAbility.Evaluate`` (§2.5, 17 §14).

        ``request.infos[0]``: the hand. The first card of
        ``GetDiscardOrder(P, targets, false)`` at Discard + Draw + Intrigue +
        Buy Gains (always positive in practice).
        """

        s = Summer()
        s.add("Discard", p.discard_value())
        s.add("Draw", p.card_draw_value())
        s.add("Intrigue", p.intrigue_value())
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        order = p.discard_order(_targets(request, Kind.CARD), False)
        if not order:
            return Answer(0.0, None, "Captured Mentat | no card")
        card = order[0]
        return Answer(s.sum, ((card.ref,),), f"Captured Mentat | {card.ref}")


@port(_AA + "original.captured_mentat_reveal")
class CapturedMentatRevealAbility(DeferredAbility):
    """``ability.activated.original.captured_mentat_reveal`` (§2.5).

    constructor: timing Reveal. Cost = any faction
    influence >= 1. Targets (``Targets``) yields two faction
    track infos: "lose" (tracks with influence > 0, ``InfluenceDelta = -1``)
    then "gain" (all tracks, ``InfluenceDelta = 1``).
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    #: The ``InfluenceDelta`` attribute Targets puts on each of its two infos (for the
    #: gain info).
    TARGET_INFLUENCE_DELTAS: ClassVar[tuple[int, ...]] = (-1, 1)

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CapturedMentatRevealAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CapturedMentatRevealAbility.ValueForPlayer``.

        ``GetBestInfluenceExchange(-1, +1, false, null, null)`` floored at 0
        (``Math.Max(0.0, v)``): the swap is valued although E never makes it.
        """

        v = Summer()
        _, _, value = p.best_influence_exchange(-1, 1, None, None)
        v.add("Captured Mentat Reveal", _dmax(0.0, value))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CapturedMentatRevealAbility.Evaluate`` (§2.5, §4.1).

        ``request.infos``: the two infos in Targets order. E looks up the "lose" info by
        ``InfluenceDelta == -1`` and the "gain" info by ``InfluenceDelta == 2``; Targets
        sets +1, so the second lookup always fails and the AI never makes the swap
        (value 0 on an Optional ability). The swap path below is kept as the app's dead
        code.

        ``GetTargetInfos(this.Owner)`` is keyed by the card, so the app falls
        back to the first prompt key's infos; either way no info carries
        ``InfluenceDelta == 2`` [I]. Judgement: ``request.infos`` are this
        ability's own infos.
        """

        infos = list(zip(request.infos, self.TARGET_INFLUENCE_DELTAS, strict=False))
        lose = next((info for info, delta in infos if delta == -1), None)
        if lose is None:
            return Answer(0.0, None, "Captured Mentat Reveal | no lose info")
        lose_tracks = [e for e in lose.entities if e.kind is Kind.TRACK]
        gain = next((info for info, delta in infos if delta == 2), None)
        if gain is None:
            return Answer(0.0, None, "Captured Mentat Reveal | no +2 info")
        gain_tracks = [e for e in gain.entities if e.kind is Kind.TRACK]
        lose_faction, gain_faction, value = p.best_influence_exchange(
            -1, 1, [t.ref for t in lose_tracks], [t.ref for t in gain_tracks]
        )
        s = Summer()
        s.add("Best Influence Exchange Value", value)
        lt = next((t for t in lose_tracks if t.ref == lose_faction), None)
        gt = next((t for t in gain_tracks if t.ref == gain_faction), None)
        if lt is None or gt is None:
            return Answer(0.0, None, "Captured Mentat Reveal | no exchange")
        return Answer(
            s.sum,
            ((lt.ref,), (gt.ref,)),
            f"Captured Mentat Reveal | {lt.ref}->{gt.ref}",
        )


@port(_AA + "uprising.chani_clever_tactician_agent")
class ChaniCleverTacticianAgentAbility(DeferredAbility):
    """``ability.activated.uprising.chani_clever_tactician_agent`` (§2.7).

    constructor: timing Agent. Cost =
    ``HasUnitsDeployed<Unit>.AtLeast(3)``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ChaniCleverTacticianAgentAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ChaniCleverTacticianAgentAbility.ValueForPlayer``.

        ``P.ConflictUnits + P.GarrisonUnits >= 3`` (the garrison may still deploy) ->
        ``+ IntrigueValue``. Bloodlines Commanders count in both (§1.1, D1).
        """

        v = Summer()
        if _conflict_units(p) + p.garrison_troop_count() >= 3:
            v.add("Chani Clever Tactician Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChaniCleverTacticianAgentAbility.Evaluate``:
        ``UpdateSelectionTargets(IntrigueValue, src, null)`` (ordering)."""

        return Answer(p.intrigue_value(), (), "Chani, Clever Tactician (Agent)")


@port(_AA + "uprising.chani_clever_tactician_reveal")
class ChaniCleverTacticianRevealAbility(DeferredAbility):
    """``ability.activated.uprising.chani_clever_tactician_reveal``
    (§2.7). constructor: timing Reveal. Cost =
    ``HasUnitsDeployed<Troop>.AtLeast(2)``."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ChaniCleverTacticianRevealAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def _wants_retreat(self, p: Profile) -> bool:
        """The shared condition of E and V: >= 3 units and >= 2 troops in the
        Conflict (Bloodlines Commanders are troops, §1.1, D1), and not the
        final round."""

        return (
            _conflict_units(p) >= 3
            and p.conflict_troop_count() >= 2
            and not p.is_final_round()
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ChaniCleverTacticianRevealAbility.ValueForPlayer``:
        the E condition, then ``+ GetTroopValue(2, false)`` (the troops coming
        home; the -4/+4 strength is neutral)."""

        v = Summer()
        if self._wants_retreat(p):
            v.add("Chani Clever Tactician Reveal Strength", p.troop_value(2, False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChaniCleverTacticianRevealAbility.Evaluate``.

        Under the condition: ``GetTroopValue(2, false)``; otherwise value 0
        (declined).
        """

        if not self._wants_retreat(p):
            return Answer(0.0, None, "Chani, Clever Tactician | keep troops")
        s = Summer()
        s.add("Chani Clever Tactician Reveal Strength", p.troop_value(2, False))
        return Answer(s.sum, (), "Chani, Clever Tactician | retreat 2")


@port(_AA + "uprising.corrinth_city_agent")
class CorrinthCityAgentAbility(DeferredAbility):
    """``ability.activated.uprising.corrinth_city_agent`` (§2.8).

    constructor: timing Agent. Cost = two hand cards then
    5 Solari. Targets: the hand (forced, max 2, min 2).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CorrinthCityAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CorrinthCityAgentAbility.ValueForPlayer``.

        ``P.HandCount >= 3`` (this card and two others) -> 2 x Discard,
        ``GetSolariValue(-5)``, ``GetVictoryPointValue(1)``. No Solari test
        (only Cost gates the offer).
        """

        v = Summer()
        if _hand_count(p) >= 3:
            v.add("Corrinth City Agent 2x Discard", 2.0 * p.discard_value())
            v.add("Corrinth City 5 solari cost", p.solari_value(-5))
            v.add("Corrinth City VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CorrinthCityAgentAbility.Evaluate`` (§2.8, 17 §10).

        ``request.infos[0]``: the hand. The first two of ``GetDiscardOrder(P, targets,
        false)`` (none with fewer than two) at 2 x Discard - 5 Solari + 1 VP.
        """

        s = Summer()
        s.add("Discard 2", 2.0 * p.discard_value())
        s.add("Pay 5 Solari", p.solari_value(-5))
        s.add("VP", p.victory_point_value(1))
        order = p.discard_order(_targets(request, Kind.CARD), False)
        if len(order) < 2:
            return Answer(0.0, None, "Corrinth City | fewer than 2 cards")
        refs = (order[0].ref, order[1].ref)
        return Answer(s.sum, (refs,), f"Corrinth City | discard {refs}")


@port(_AA + "uprising.corrinth_city_reveal")
class CorrinthCityRevealAbility(DeferredAbility):
    """``ability.activated.uprising.corrinth_city_reveal`` (§2.8).

    constructor: timing Reveal. Cost = NoCostAction. Targets: a
    custom choice, option 0 = 5 Solari, option 1 = pay 5 Solari for the High
    Council seat (offered to the AI whenever Solari >= 5, seated or not).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CorrinthCityRevealAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CorrinthCityRevealAbility.CanRunImmediately``:
        ``GetAttributeValue<bool>(HighCouncilSeat)``: a seated player runs it
        at once (forced single-key prompt)."""

        return p.ctx.me.high_council

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CorrinthCityRevealAbility.ValueForPlayer`` (§2.8, §4.2).

        Seat test inverted (``test al,al; je``): unseated -> ``max(5 Solari,
        0)``; seated -> ``max(5 Solari, -5 Solari + HighCouncilValue)``.
        """

        v = Summer()
        a = p.solari_value(5)
        has_seat = p.ctx.me.high_council
        b = p.solari_value(-5) + p.high_council_value() if has_seat else 0.0
        v.add("Corrinth City Reveal", _dmax(a, b))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CorrinthCityRevealAbility.Evaluate`` (§2.8, 17 §10).

        Option 0 at ``GetSolariValue(5)`` first (sticks); with Solari >= 5,
        option 1 at ``GetSolariValue(-5) + HighCouncilValue`` replaces it only
        when strictly greater. ``HighCouncilValue`` has no seat test, so a
        seated AI can pick option 1 (the engine then falls back, [I] paying
        the 5 Solari).
        """

        choice = _Choice()
        choice.update(p.solari_value(5), ((0,),), "Corrinth City | 5 Solari")
        if p.ctx.me.resources.solari >= 5:
            s = Summer()
            s.add("5 SolariCost", p.solari_value(-5))
            s.add("High Council Seat", p.high_council_value())
            choice.update(s.sum, ((1,),), "Corrinth City | High Council Seat")
        return choice.answer("Corrinth City")


@port(_AA + "uprising.covert_operation")
class CovertOperationAbility(DeferredAbility):
    """``ability.activated.uprising.covert_operation`` (§2.9).

    constructor: timing Agent. Cost = NoCostAction; no targets. E is
    the inherited ``DeferredAbility.Evaluate`` (DeferValue 2, ordering only);
    each victim picks its own discard with ``ChooseDiscardEvaluator``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CovertOperationAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CovertOperationAbility.ValueForPlayer``.

        ``OpponentRatio(o => o.HandCount > 0)`` x ``CovertOperationMod``.
        """

        v = Summer()
        ratio = p.opponent_ratio(lambda o: len(o.hand) > 0)
        v.add("Covert Operation Discard", ratio * p.C.CovertOperationMod)
        return v


@port(_AA + "uprising.dangerous_rhetoric")
class DangerousRhetoricAbility(GainAnyInfluenceAgentAbility):
    """``ability.activated.uprising.dangerous_rhetoric`` (§2.10).

    Overrides only ``LoggingMode`` and ``CustomExecution``
 (the log line); every AI hook and the Agent timing come from
    ``GainAnyInfluenceAgentAbility``. The card's "trash this card" is the
    separate ``TrashSelfAbility``, never priced.
    """


@port(_AA + "uprising.delivery_agreement_agent")
class DeliveryAgreementAgentAbility(DeferredAbility):
    """``ability.activated.uprising.delivery_agreement_agent`` (§2.11).

    constructor: timing Agent. Cost = a card in hand.
    Targets (``Targets``): the hand discard picker, with the
    contract picker (``GainContractAbility.MakeTargets``) as a dependent
    ``DeferredLeafSelection``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DeliveryAgreementAgentAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DeliveryAgreementAgentAbility.ValueForPlayer``:
        ``P.HandCount >= 2`` -> ``+ DiscardValue + GainContractValue()``."""

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Delivery Agreement Agent Discard", p.discard_value())
            v.add("Contract Value", p.gain_contract_value().sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DeliveryAgreementAgentAbility.Evaluate`` (§2.11, 17 §11).

        ``request.infos[0]``: the hand. The first card of
        ``GetDiscardOrder(P, targets, false)`` at Discard + GainContractValue.
        The contract itself is a separate (leaf) answer: ``evaluate_contract``.
        """

        s = Summer()
        s.add("Discard", p.discard_value())
        s.add("Contract", p.gain_contract_value().sum)
        order = p.discard_order(_targets(request, Kind.CARD), False)
        if not order:
            return Answer(0.0, None, "Delivery Agreement | no card")
        card = order[0]
        return Answer(s.sum, ((card.ref,),), f"Delivery Agreement | {card.ref}")

    def evaluate_contract(self, p: Profile, request: Request) -> Answer:
        """The dependent contract selection of the discard.

        UNTRACED (imperium-a §5): how the AI answers the
        ``DeferredLeafSelection`` that ``BeginExecution`` reads with
        ``GetTargetsFromQueue<ContractPlayable>``. Most likely reading:
        the picker ``GainContractAbility.MakeTargets`` builds is answered like
        ``GainContractAbility`` (``ContractEvaluate``, forced: the discard is
        already paid). ``request.infos[0]``: the contract options.
        """

        return contract_evaluate(p, request, True)


@port(_AA + "uprising.delivery_agreement_reveal")
class DeliveryAgreementRevealAbility(DeferredAbility):
    """``ability.activated.uprising.delivery_agreement_reveal`` (§2.11;
    Priority Contracts' reveal subclasses it).

    constructor: timing Reveal. Cost = NoCostAction. Targets: custom
    choice, option 0 = ``spice_amount`` Spice, option 1 = trash this card for
    1 VP (only with >= 4 completed contracts).
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    #: ``SpiceAmount``.
    spice_amount: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DeliveryAgreementRevealAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DeliveryAgreementRevealAbility.ValueForPlayer``:
        ``max(GetSpiceValue(SpiceAmount), >= 4 contracts ? VP(1) : 0)``; the
        trashed card is never priced."""

        v = Summer()
        spice = p.spice_value(self.spice_amount)
        completed = len(p.ctx.me.completed_contract_ids)
        vp = p.victory_point_value(1) if completed >= 4 else 0.0
        v.add("Delivery Agreement/Priority Contracts Reveal", _dmax(spice, vp))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DeliveryAgreementRevealAbility.Evaluate`` (§2.11).

        With >= 4 completed contracts option 1 at ``GetVictoryPointValue(1)``
        first (sticks); then option 0 at ``GetSpiceValue(SpiceAmount)`` wins
        when strictly greater (or when nothing is stored).
        """

        choice = _Choice()
        if len(p.ctx.me.completed_contract_ids) >= 4:
            choice.update(p.victory_point_value(1), ((1,),), "Trash -> 1 VP")
        choice.update(p.spice_value(self.spice_amount), ((0,),), "Spice")
        return choice.answer("Delivery Agreement Reveal")


@port(_AA + "uprising.demand_attention")
class DemandAttentionAbility(DeferredAbility):
    """``ability.activated.uprising.demand_attention`` (§2.12; the
    card is in no ``Decks`` list, so absent from a normal game).

    constructor: timing Agent, ``GainInfluenceReplacement``. Targets:
    custom choice, option 0 = the space's influence, option 1 = 4 Spice for
    two influence (offered only when ``CanPayForAdditional``, a Targets-side
    test the AI does not read). V/P: not overridden (0).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DemandAttentionAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def space_faction(self, p: Profile) -> str:
        """``DemandAttentionAbility.GetSpaceFaction(P)``.

        The active space's ``FactionInfluence`` when it names exactly one
        faction (our faction id), else ``Factions.None``.
        """

        space = _active_space(p)
        if space is None:
            return _ANY_FACTION
        raw = space.attr("FactionInfluence")
        if not isinstance(raw, Mapping):
            return _ANY_FACTION
        keys = [str(k) for k in raw]
        if len(keys) != 1:
            return _ANY_FACTION
        return _APP_TO_FACTION.get(keys[0], _ANY_FACTION)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DemandAttentionAbility.Evaluate`` (§2.12, 17 §8).

        Option 0 at ``GetGainInfluenceValue(f, 1)`` first; option 1 at
        ``GetSpiceValue(-4) + GetGainInfluenceValue(f, 2)`` when strictly
        greater. No affordability test (UNTRACED in the spec whether a
        one-option prompt still reaches E).
        """

        faction = self.space_faction(p)
        choice = _Choice()
        choice.update(
            p.gain_influence_value(faction, 1, -1, False).sum, ((0,),), "1 Influence"
        )
        s = Summer()
        s.add("4 SpiceCost", p.spice_value(-4))
        s.add("2 Influence", p.gain_influence_value(faction, 2, -1, False).sum)
        choice.update(s.sum, ((1,),), "4 Spice -> 2 Influence")
        return choice.answer("Demand Attention")


@port(_AA + "uprising.desert_call")
class DesertCallAbility(DeferredAbility):
    """``ability.activated.uprising.desert_call`` (§2.13; absent from a
    normal game).

    constructor: timing Agent. Cost = 1 Water then maker
    hooks. E is the inherited ``DeferredAbility.Evaluate``: the card has no
    DeferValue and the ability is Optional, so the value is 0 and the AI
    never uses it. V: not overridden (0).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertCallAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL


@port(_AA + "uprising.desert_power_agent")
class DesertPowerAgentAbility(DeferredAbility):
    """``ability.activated.uprising.desert_power_agent`` (§2.14).

    constructor: timing Agent. Cost =
    ``HasPlayedToMakerSpaceThisTurn``.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertPowerAgentAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertPowerAgentAbility.ValueForPlayer``: a Maker
        candidate space -> ``+ GetSpiceValue(2)``."""

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and _is_maker_space(space):
            v.add("Desert Power Spice", p.spice_value(2))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DesertPowerAgentAbility.Evaluate``: 100 (literal)."""

        return Answer(100.0, (), "Desert Power (Agent) | 100")


@port(_AA + "uprising.desert_power_deferred")
class DesertPowerDeferredAbility(DeferredAbility):
    """``ability.activated.uprising.desert_power_deferred`` (the reveal
    choice, §2.14). constructor: timing Reveal. Cost = NoCostAction.
    Targets: option 0 = 2 Persuasion; option 1 = sandworm for 1 Water (only
    with Water > 0, maker hooks and ``CanDeploySandworms``)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertPowerDeferredAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def _worm_option(self, p: Profile) -> bool:
        me = p.ctx.me
        return me.resources.water > 0 and me.maker_hooks and _can_deploy_sandworms(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertPowerDeferredAbility.ValueForPlayer``.

        ``max(Persuasion(2) + BuyGains(2), worm option ? Water(-1) +
        Sandworm(1) : 0)``; Buy Gains is counted twice (once inside
        ``GetPersuasionValue``).
        """

        v = Summer()
        persuasion = p.persuasion_value(2) + p.buy_gains(2)
        worm = (
            p.water_value(-1) + p.sandworm_value(1, False)
            if self._worm_option(p)
            else 0.0
        )
        v.add("Desert Power Reveal", _dmax(persuasion, worm))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DesertPowerDeferredAbility.Evaluate`` (§2.14, 17 §17).

        The worm option (1) first when offered (sticks), then option 0 at
        ``GetPersuasionValue(2) + GetBuyGains(2)`` when strictly greater.
        """

        choice = _Choice()
        if self._worm_option(p):
            worm = p.water_value(-1) + p.sandworm_value(1, False)
            choice.update(worm, ((1,),), "Desert Power | sandworm")
        persuasion = p.persuasion_value(2) + p.buy_gains(2)
        choice.update(persuasion, ((0,),), "Desert Power | 2 Persuasion")
        return choice.answer("Desert Power")


@port(_AA + "uprising.double_agent")
class DoubleAgentAbility(PlaceSpyAbility):
    """``ability.activated.uprising.double_agent`` (§2.15).

    constructor: timing Agent. SelectionMode, Cost and E (full
    ``SpyValue``) are inherited from ``PlaceSpyAbility``. UNTRACED (spec §5):
    how the three post overrides shape the post targets.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``PostFilter``: ``PlaceSpyPostFilter.PlayerSpace`` (3).
    post_filter: ClassVar[int] = 3
    #: ``AutoSelectPost``.
    auto_select_post: ClassVar[bool] = True
    #: ``AllowMultipleSpies``.
    allow_multiple_spies: ClassVar[bool] = True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DoubleAgentAbility.ValueForPlayer``:
        ``PlaceSpyAbility.ValueForPlayer`` scaled by ``DoubleAgentMod`` (0.5)
        with ``AIProfileAbsUtils.Multiply`` (E is not scaled)."""

        v = super().value_for_player(p, with_entities)
        v.multiply("Double Agent Spy", p.C.DoubleAgentMod)
        return v


@port(_AA + "uprising.ecological_testing_station")
class EcologicalTestingStationAbility(DeferredAbility):
    """``ability.activated.uprising.ecological_testing_station`` (§2.16).

    constructor: timing Agent. Cost = 2 Water then a
    drawable card.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``EcologicalTestingStationAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EcologicalTestingStationAbility.ValueForPlayer``.

        At a space where 2 Water cannot also be paid: ``+ 0.0`` and stop. Else
        ``WaterValue(1) x -2.0`` (literal), 2 draws and ``GetBuyGains(2 x
        PossiblePersuasionGain())``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.WATER, 2
        ):
            v.add(
                "Ecological Testing Station Ability cost cannot be paid in "
                f"addition to {space.ref} cost",
                0.0,
            )
            return v
        v.add("Ecological Testing Station Water cost", p.water_value(1) * -2.0)
        v.add("Ecological Testing Station Draw", p.card_draw_value() * 2.0)
        v.add("Buy Gains Bonus", p.buy_gains(2 * p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EcologicalTestingStationAbility.Evaluate`` (§2.16).

        ``GetWaterValue(-2)`` + 2 draws + ``GetBuyGains(PossiblePersuasionGain())``
        (one card's buy gains); taken iff > 0.
        """

        s = Summer()
        s.add("Pay 2 water", p.water_value(-2))
        s.add("Card Draw", p.card_draw_value() * 2.0)
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return Answer(s.sum, (), "Ecological Testing Station")


@port(_AA + "uprising.fedaykin_stilltent")
class FedaykinStilltentAbility(DeferredAbility):
    """``ability.activated.uprising.fedaykin_stilltent`` (§2.17).

    constructor: timing Agent. Cost =
    ``HasPlayedToMakerSpaceThisTurn``. E: the inherited
    ``DeferredAbility.Evaluate`` (no DeferValue, Explicit -> 1); it auto-runs.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FedaykinStilltentAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FedaykinStilltentAbility.ValueForPlayer``: a Maker
        candidate space -> ``+ GetSpiceValue(1)`` (the card gives a troop; the
        app prices one Spice)."""

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and _is_maker_space(space):
            v.add("Fedaykin Stilltent Troop", p.spice_value(1))
        return v


@port(_AA + "uprising.guild_envoy")
class GuildEnvoyAbility(DeferredAbility):
    """``ability.activated.uprising.guild_envoy`` (§2.18).

    constructor: timing Agent. Cost = a card in hand.
    Targets: the hand (forced, max 1). The two draws are the separate
    ``SpacingGuildDiscardDrawAbility`` (generic.py).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildEnvoyAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildEnvoyAbility.ValueForPlayer`` (§2.18).

        ``HandCount >= 2`` and a candidate space given: the first card of
        ``GetDiscardOrder(P, other hand cards, true)`` (the filter drops the owner); a
        Spacing Guild one -> 2 draws and ``GetBuyGains(2 x PPG)``. The discard itself is
        not counted.
        """

        v = Summer()
        if _hand_count(p) >= 2 and len(with_entities) > 0:
            cards = [c for c in _hand(p) if c.ref != self.owner.ref]
            order = p.discard_order(cards, True)
            if order and _has_faction(order[0], "SpacingGuild"):
                v.add("Guild Envoy Draw", p.card_draw_value() * 2.0)
                v.add("Buy Gains Bonus", p.buy_gains(2 * p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildEnvoyAbility.Evaluate`` (§2.18, 17 §1).

        ``request.infos[0]``: the hand. The first card of
        ``GetDiscardOrder(P, targets, true)``; Discard, plus 2 draws and
        ``GetBuyGains(2 x PPG)`` for a Spacing Guild card; value floored at
        0.5 (literal).
        """

        s = Summer()
        s.add("Discard", p.discard_value())
        order = p.discard_order(_targets(request, Kind.CARD), True)
        if not order:
            return Answer(0.0, None, "Guild Envoy | no card")
        card = order[0]
        if _has_faction(card, "SpacingGuild"):
            s.add("Draw", p.card_draw_value() * 2.0)
            s.add("Buy Gains Bonus", p.buy_gains(2 * p.possible_persuasion_gain()))
        return Answer(_dmax(s.sum, 0.5), ((card.ref,),), f"Guild Envoy | {card.ref}")


@port(_AA + "uprising.guild_spy_agent")
class GuildSpyAgentAbility(DeferredAbility):
    """``ability.activated.uprising.guild_spy_agent`` (§2.19).

    constructor: timing Agent. Cost = a card in hand.
    Targets: the hand (not forced, max 1).
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildSpyAgentAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def can_run_immediately(self, p: Profile) -> bool:
        """``GuildSpyAgentAbility.CanRunImmediately``: false."""

        return False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildSpyAgentAbility.ValueForPlayer`` (§2.19).

        ``HandCount >= 2`` -> Discard, Draw, Buy Gains; then, with a candidate space,
        the first of ``GetDiscardOrder(P, other hand cards, true)`` being Spacing Guild
        -> ``+ IntrigueValue``. The ``Any`` receiver is ``withEntities``.
        """

        v = Summer()
        if _hand_count(p) >= 2:
            v.add("Guild Spy Discard", p.discard_value())
            v.add("Guild Spy Draw", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
            if len(with_entities) > 0:
                cards = [c for c in _hand(p) if c.ref != self.owner.ref]
                order = p.discard_order(cards, True)
                if order and _has_faction(order[0], "SpacingGuild"):
                    v.add("Guild Spy SG Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildSpyAgentAbility.Evaluate`` (§2.19, 17 §2).

        ``request.infos[0]``: the hand. Discard + Draw + Buy Gains, plus
        ``IntrigueValue`` when the first of ``GetDiscardOrder(P, targets,
        true)`` is Spacing Guild; no floor.
        """

        s = Summer()
        s.add("Discard", p.discard_value())
        s.add("Draw", p.card_draw_value())
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        order = p.discard_order(_targets(request, Kind.CARD), True)
        if not order:
            return Answer(0.0, None, "Guild Spy | no card")
        card = order[0]
        if _has_faction(card, "SpacingGuild"):
            s.add("Intrigue", p.intrigue_value())
        return Answer(s.sum, ((card.ref,),), f"Guild Spy | {card.ref}")


def factions_observed(p: Profile) -> list[str]:
    """``GuildSpyRevealAbility.FactionsObserved(P)``.

    ``GetDeployedSpies(P).SelectMany(GetObservingSpaces).Select(Faction)
    .Distinct().Where(f != None)``: our faction ids, first-seen order (spies
    in placement order, each post's spaces in board order).
    """

    seen: list[str] = []
    for post in p.ctx.me.spy_post_ids:
        for space_id in _POST_SPACES.get(post, ()):
            app_faction = space_entity(space_id, p.ctx.board).attr("Faction")
            if not isinstance(app_faction, str):
                continue
            faction = _APP_TO_FACTION.get(app_faction)
            if faction is not None and faction not in seen:
                seen.append(faction)
    return seen


@port(_AA + "uprising.guild_spy_reveal")
class GuildSpyRevealAbility(DeferredAbility):
    """``ability.activated.uprising.guild_spy_reveal`` (§2.19).

    constructor: timing Reveal. Cost: The Spice Must Flow
    acquired this turn and a faction observed.
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildSpyRevealAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def can_run_immediately(self, p: Profile) -> bool:
        """``GuildSpyRevealAbility.CanRunImmediately``: true."""

        return True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildSpyRevealAbility.ValueForPlayer`` (§2.19, §4.5).

        ``+ GetGainInfluenceValue(f, 1)`` for every faction observed, with no
        test that The Spice Must Flow will be acquired.
        """

        v = Summer()
        for faction in factions_observed(p):
            v.add(
                "Guild Spy reveal " + faction,
                p.gain_influence_value(faction, 1, -1, False).sum,
            )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildSpyRevealAbility.Evaluate``: 1.0 (literal)."""

        return Answer(1.0, (), "Guild Spy (Reveal) | 1")


@port(_AA + "uprising.bene_gesserit_influence_troop")
class BeneGesseritInfluenceTroopAbility(DeferredAbility):
    """``ability.activated.uprising.bene_gesserit_influence_troop``
    (Hidden Missive, §2.20). constructor: timing Agent. Cost
 = BG influence >= 2 then a troop in supply."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BeneGesseritInfluenceTroopAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneGesseritInfluenceTroopAbility.ValueForPlayer``:
        ``+ GetTroopValue(1, false)`` with no influence condition."""

        v = Summer()
        v.add("Hidden Missive Troops", p.troop_value(1, False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BeneGesseritInfluenceTroopAbility.Evaluate``: 100."""

        return Answer(100.0, (), "Hidden Missive Troop | 100")


@port(_AA + "uprising.imperial_spymaster")
class ImperialSpymasterAbility(DeferredAbility):
    """``ability.activated.uprising.imperial_spymaster`` (§2.21).

    constructor: timing Agent. Cost = ``HasRecalledSpy``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ImperialSpymasterAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ImperialSpymasterAbility.ValueForPlayer``.

        ``P.GetAttributeValue<bool>(HasRecalledSpyThisTurn)`` (receiver = the player,
        settled) -> ``+ IntrigueValue``. Ours: ``spies_recalled_turn > 0`` (R5 §4.5).
        """

        v = Summer()
        if p.ctx.me.spies_recalled_turn > 0:
            v.add("Imperial Spymaster Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperialSpymasterAbility.Evaluate``: 100."""

        return Answer(100.0, (), "Imperial Spymaster | 100")


def _bg_in_play(p: Profile) -> bool:
    """``P.AllCardsInPlay.Any(e => e.FactionsList ∋ BeneGesserit)``."""

    return any(_has_faction(c, "BeneGesserit") for c in _in_play(p))


@port(_AA + "uprising.in_high_places_place_spy")
class InHighPlacesPlaceSpyAbility(PlaceSpyAbility):
    """``ability.activated.uprising.in_high_places_place_spy`` (§2.22).

    constructor: timing Agent. Cost =
    ``HasPlayedFactionCard(BeneGesserit, owner)``. SelectionMode and E come
    from ``PlaceSpyAbility``; the post overrides keep their defaults.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InHighPlacesPlaceSpyAbility.ValueForPlayer``: a Bene
        Gesserit card in play (owner not excluded) -> the
        ``PlaceSpyAbility`` value, else empty."""

        if _bg_in_play(p):
            return super().value_for_player(p, with_entities)
        return Summer()

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``InHighPlacesPlaceSpyAbility.ValueInPileForOtherPlay``.

        Play area only: no BG card in play, ``card`` is BG and >= 2 agents left ->
        ``0.75 x PlaceSpyAbility value`` (f64 0.75) "No Bene Gesserit in Play". No Deck
        branch (and no default synergy).
        """

        s = Summer()
        if pile is not Pile.PLAY_AREA:
            return s
        if _bg_in_play(p):
            return s
        if not _has_faction(card, "BeneGesserit"):
            return s
        if p.ctx.me.agents_available < 2:
            return s
        spy = PlaceSpyAbility.value_for_player(self, p, ())
        s.add("No Bene Gesserit in Play", spy.sum * 0.75)
        return s


@port(_AA + "uprising.in_high_places_persuasion")
class InHighPlacesPersuasionAbility(DeferredAbility):
    """``ability.activated.uprising.in_high_places_persuasion`` (§2.22).

    constructor: timing Reveal. Targets: the own spies on posts
    (forced, max 2, min 2).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``InHighPlacesPersuasionAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` = ``HasAtLeastSpiesOnBoard(2)``."""

        return _deployed_spies(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``InHighPlacesPersuasionAbility.ValueForPlayer``:
        ``MeetsCost`` -> ``2 x RecallSpyValue()`` then
        ``GetPersuasionValue(3)`` (the app's "Placess" labels)."""

        v = Summer()
        if self.meets_cost(p):
            v.add("In High Placess Recall 2 Spies", 2.0 * p.recall_spy_value().sum)
            v.add("In High Placess Recall 3 Persuasion", p.persuasion_value(3))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InHighPlacesPersuasionAbility.Evaluate`` (§2.22).

        ``request.infos[0]``: the own spies. ``GetPersuasionValue(3)``, then
        ``GetRecallSpies(spies, 2)``; with exactly two ``+ 2 x RecallSpyValue()``, taken
        iff > 0.
        """

        s = Summer()
        s.add("3 Persuasion", p.persuasion_value(3))
        spies, _ = p.recall_spies(_targets(request, Kind.SPY), 2)
        if len(spies) != 2:
            return Answer(0.0, None, "In High Places | not 2 spies")
        refs = tuple(spy.ref for spy in spies)
        s.add(f"Remove spies {refs[0]} + {refs[1]}", 2.0 * p.recall_spy_value().sum)
        return Answer(s.sum, (refs,), "In High Places | recall 2 spies")


@port(_AA + "uprising.junction_headquarters")
class JunctionHeadquartersAbility(DeferredAbility):
    """``ability.activated.uprising.junction_headquarters`` (§2.24).

    constructor: timing Agent. Targets: the held intrigues (max 1,
    min 0), as Branching Path.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``JunctionHeadquartersAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Spacing Guild alliance, then an intrigue held,
        then ``HasResources.AtLeast(Spice, 2)``."""

        me = p.ctx.me
        return (
            "spacing_guild" in me.alliance_faction_ids
            and len(p.ctx.intrigue_cards) > 0
            and me.resources.spice >= 2
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``JunctionHeadquartersAbility.ValueForPlayer`` (§2.24).

        ``MeetsCost`` (the alliance must already exist) -> ``+ TrashIntrigueValue()``
        when no held intrigue is bad, ``+ GetSpiceValue(-2)``, ``+
        GetVictoryPointValue(1)``.
        """

        v = Summer()
        if self.meets_cost(p):
            if all(not _is_bad_intrigue(p, i) for i in _intrigue_hand(p)):
                v.add("Trash Intrigue", p.trash_intrigue_value())
            v.add("Pay 2 Spice", p.spice_value(-2))
            v.add("VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``JunctionHeadquartersAbility.Evaluate``: Branching
        Path's E (5.0 for a bad intrigue, else 1.0; always made)."""

        return _trash_intrigue_choice(p, request, "Junction Headquarters")


@port(_AA + "uprising.leadership_agent")
class LeadershipAgentAbility(DeferredAbility):
    """``ability.activated.uprising.leadership_agent`` (§2.25).

    constructor: timing Agent. Cost = a sandworm deployed
    then a drawable card.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``LeadershipAgentAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LeadershipAgentAbility.ValueForPlayer``.

        ``n = P.ConflictSandwormCount``; ``n > 0`` -> ``CardDrawValue x n``
        and ``GetBuyGains(n x PossiblePersuasionGain())`` (``imul``).
        """

        v = Summer()
        n = p.ctx.me.sandworms_conflict
        if n > 0:
            v.add("Leadership Draw Value", p.card_draw_value() * n)
            v.add("Buy Gains Bonus", p.buy_gains(n * p.possible_persuasion_gain()))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LeadershipAgentAbility.Evaluate`` (17 §9):
        ``max(1.0, GetSandWormValue(1, false) + -1.0)`` (literals; ordering
        only, priced as a sandworm)."""

        value = _dmax(1.0, p.sandworm_value(1, False) + -1.0)
        return Answer(value, (), "Leadership (Agent)")


@port(_AA + "uprising.long_live_the_fighters_start")
class LongLiveTheFightersStartAbility(DeferredAbility):
    """``ability.activated.uprising.long_live_the_fighters_start`` (§2.26).

    constructor: timing Agent. Cost = ``DeckCount >= 3``.
    Its execution runs ``LongLiveTheFightersAbility``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``LongLiveTheFightersStartAbility.SelectionMode``:
        Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``LongLiveTheFightersStartAbility.ValueForPlayer``.

        Fewer than 3 cards in the deck: ``+ 0.0`` and stop. Else 2 draws (for
        one drawn card), ``GetBuyGains(PPG)``, ``TrashCardValue`` and
        ``LongLiveTheFightersMod``.
        """

        v = Summer()
        if p.ctx.deck_size < 3:
            v.add("Not Enough cards in deck", 0.0)
            return v
        v.add("Draw Value", p.card_draw_value() * 2.0)
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        v.add("Fighters Trash Value", p.trash_card_value())
        v.add("Mod Value", p.C.LongLiveTheFightersMod)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LongLiveTheFightersStartAbility.Evaluate``: 100."""

        return Answer(100.0, (), "Long Live the Fighters | start")


class LongLiveTheFightersEvaluator:
    """``evaluator.long_live_the_fighters_evaluator`` (§2.26).

    A ``AISelectionEvaluator`` attached to the discard prompt that
    ``LongLiveTheFightersAbility``'s execution builds (not an ability, so not
    registered in ``PORTS``). The selected card is discarded, then the other
    one trashed (17 Errata).
    """

    @staticmethod
    def get_trash_card(p: Profile, targets: Sequence[Entity]) -> Entity:
        """``LongLiveTheFightersEvaluator.GetTrashCard``.

        ``GetCardToTrash(targets, 0.0).card ?? targets.OrderBy(PersuasionCost)
        .First()`` (stable: ties keep target order).
        """

        card, _ = p.card_to_trash(list(targets), 0.0)
        if card is not None:
            return card
        return sorted(targets, key=lambda c: c.int_attr("PersuasionCost"))[0]

    @staticmethod
    def evaluate(p: Profile, request: Request) -> Answer:
        """``LongLiveTheFightersEvaluator.Evaluate``.

        ``request.infos[0]``: the two remaining cards. Drop the trash card,
        answer the first remaining one at 100 (``UpdateTargets``).
        """

        remaining = _targets(request, Kind.CARD)
        remaining.remove(LongLiveTheFightersEvaluator.get_trash_card(p, remaining))
        card = remaining[0]
        return Answer(
            100.0, ((card.ref,),), f"Long Live the Fighters | discard {card.ref}"
        )


@port(_AA + "uprising.long_live_the_fighters")
class LongLiveTheFightersAbility(DeferredAbility):
    """``ability.activated.uprising.long_live_the_fighters`` (the "draw"
    prompt, §2.26). constructor: timing Agent. Never offered by
    itself (Cost false); run by the start ability. V: not overridden (0)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``LongLiveTheFightersAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` = ``CostAction(false)``."""

        return False

    def can_be_run(self, p: Profile) -> bool:
        """``CanBeRun``: false, since the Cost never holds."""

        return self.meets_cost(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LongLiveTheFightersAbility.Evaluate`` (§2.26, 17 §6).

        ``request.infos[0]``: the top three cards of the deck. Remove the evaluator's
        trash card, order the rest by ``PersuasionCost`` descending (stable), and draw
        the first unless it costs >= 9 (The Spice Must Flow), then the second; 100.
        """

        cards = _targets(request, Kind.CARD)
        cards.remove(LongLiveTheFightersEvaluator.get_trash_card(p, cards))
        ordered = sorted(
            cards, key=lambda c: c.int_attr("PersuasionCost"), reverse=True
        )
        draw = ordered[1 if ordered[0].int_attr("PersuasionCost") >= 9 else 0]
        return Answer(
            100.0, ((draw.ref,),), f"Long Live the Fighters | draw {draw.ref}"
        )
