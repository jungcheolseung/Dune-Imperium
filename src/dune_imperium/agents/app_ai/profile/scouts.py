"""App-style Arrakeen Scouts profile terms (docs/app-ai/scouts.md §2.1).

The Steam app has no Arrakeen Scouts, so every method here is an app-style
extension (docs/app-ai-plan.md §11.1 option 3) built from the app's own
prices: the line value of a Scouts cost -> reward line (``scouts_line_value``,
§2.2), the troop and delayed-payout prices the Scouts lines need (§2.1), the
subcommittee opportunity (§4.5), the Influence-4 bonus prices (§3.11, §4.7),
and the Scouts valuation terms the faithful ports call behind a Scouts gate
(§4: Valued Informants on posts, CHOAM Escort goods on a Contract, Sponsored
Research, Back Room Deal, Tleilaxu Offering, Friends Everywhere and Market
Opening). Every term reads Scouts state that exists only with the
``arrakeen_scouts`` option, so games without it never reach a Scouts value.

Numbers come from ``data/constants.py`` through the existing prices, from the
printed data of ``content/arrakeen_scouts`` (via the line archetypes of
``data/synthetic.py``), or from the spec's rule (the 6/4 literals of the
conflict gate, the 100 of the gate itself); each method cites its section.
"""

import copy
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    card_entity,
    scouts_line_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, AppContext
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.arrakeen_scouts import (
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    RoundModifier,
)
from dune_imperium.content.arrakeen_scouts.types import GainSpiceWithHelixBonus
from dune_imperium.content.immortality.board import (
    FIRST_GENETIC_MARKER_COLUMN,
    RESEARCH_SPACES_BY_ID,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.scouts_missions import (
    _TO_CONFLICT,
    HELIX,
    RECLAIMED_FORCES,
    TLEILAXU_OFFERING_SPACE,
    TLEILAXU_OFFERING_TRACK_SPACE,
    _collects,
)

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

#: Offworld Operation's Helix spice line (``events.py``; scouts.md §1
#: ``GainSpiceWithHelixBonus``): the printed plain and Helix amounts.
HELIX_SPICE: Final = next(
    reward
    for choice in EVENTS_BY_ID["offworld_operation"].secret_choices
    for reward in choice.option.rewards
    if isinstance(reward, GainSpiceWithHelixBonus)
)
#: ShouldPlayTroopIntrigue's (notFirstExtra, firstExtra) that both app callers
#: pass (Mercenaries ``(6, 4, 2)``, Depart for Arrakis ``(6, 4, 3)``;
#: spec/intrigues.md §4.2, §7.9, §7.18; scouts.md §2.1).
_NOT_FIRST_EXTRA: Final = 6
_FIRST_EXTRA: Final = 4
#: ``ShouldPlayTroopIntrigue``'s two answers (spec/intrigues.md §4.2).
_GATE_YES: Final = 100
_GATE_NO: Final = 0
_FRIENDS_EVERYWHERE: Final = RoundModifier.ANY_FACTION_FOUR_BONUS.value
_MARKET_OPENING: Final = RoundModifier.SPICE_MUST_FLOW_DISCOUNT.value
#: Goods-row resource -> ``GetResourceValue`` attribute.
RESOURCE_ATTRS: Final = {
    "solari": Attr.SOLARI,
    "spice": Attr.SPICE,
    "water": Attr.WATER,
}


def mission_troops_to_conflict(mission_id: str) -> bool:
    """Whether a mission's parked troops go to the Conflict on the visit
    (``rules/scouts_missions.py`` ``_TO_CONFLICT``, OQ-077); the others are
    recruited to the garrison."""

    return MISSIONS_BY_ID[mission_id].kind in _TO_CONFLICT


def mission_collected_on_visit(mission_id: str) -> bool:
    """Whether a mission's pieces are collected by a board-space visit
    (``rules/scouts_missions.py`` ``_VISITED``)."""

    return _collects(mission_id)


class OwnSupplyContext(AppContext):
    """``base`` with this seat's supply troops read as ``troops``.

    The hypothetical behind ``uncapped_troop_value`` (scouts.md §2.1): the
    supply cap is the only reader of ``troops_supply`` in a troop price, so
    the same ``GetTroopValue`` on a supply that cannot bind it is the price
    without the cap line. The seat's ``PlayerState`` is copied without its
    12-troop check (the extra troops are notional); every other read is
    ``base``'s.
    """

    def __init__(self, base: AppContext, troops: int) -> None:
        super().__init__(base.state, base.seat, base.view)
        me = copy.copy(base.me)
        object.__setattr__(me, "troops_supply", troops)
        self._me = me

    @property
    def me(self) -> PlayerState:
        return self._me


class ScoutsMixin(ProfileCore):
    """The app-style Arrakeen Scouts ``Profile`` methods (scouts.md §2.1)."""

    _scouts_gate: int | None = None

    def _p(self) -> Profile:
        """``self`` as the full ``Profile`` the ability hooks expect."""

        return cast("Profile", self)

    # ===========================================================================
    # §2.1 Troop prices, the Conflict gate, delayed payouts
    # ===========================================================================

    def uncapped_troop_value(self, amount: int) -> float:
        """``UTr(n)``: ``GetResourceValue(Troops, n, false)`` without its
        ``amount = Min(amount, supply troops)`` line (scouts.md §2.1, D10).

        For troops that do not come from the supply: parked mission troops,
        troops a specimen top-up will supply. The cap is the only reader of
        the supply in a troop price (profile-economy §3), so the same call
        on a supply that cannot bind it is the uncapped price.
        """

        if amount <= self.ctx.me.troops_supply:
            return self.troop_value(amount, False)
        other = type(self)(OwnSupplyContext(self.ctx, amount), self.C, self.rng)
        other._is_climax = self._is_climax  # the same decision's caches
        other._is_final_round = self._is_final_round
        return other.troop_value(amount, False)

    def scouts_conflict_troops_gate(self) -> int:
        """``Gate``: ``ShouldPlayTroopIntrigue`` without its supply line, with
        the (6, 4) both app callers pass (scouts.md §2.1; D11, D44).

        0 or 100. Computed once per decision (the state does not change
        within one; the app's method reads only it).
        """

        if self._scouts_gate is not None:
            return self._scouts_gate
        self._scouts_gate = self._compute_conflict_troops_gate()
        return self._scouts_gate

    def _compute_conflict_troops_gate(self) -> int:
        if not self._p()._can_deploy():
            return _GATE_NO
        lb, ub = self.conflict_posture_bounds()
        interest = self.current_conflict_interest().sum
        if self.is_climax():
            return _GATE_YES
        if interest > ub:
            return _GATE_YES
        if not interest > lb:
            return _GATE_NO
        exp = self.est_strength().sum
        opp = max(
            (self.est_opponent_strength(op.player_id).sum for op in self.ctx.opponents),
            default=0,
        )
        d = opp - exp
        if d > 0:
            return _GATE_NO if abs(d) > _NOT_FIRST_EXTRA else _GATE_YES
        return _GATE_NO if exp > opp + _FIRST_EXTRA else _GATE_YES

    def conflict_troop_value(self, amount: int) -> float:
        """``CT(n)``: supply troops straight into the Conflict, ``Tr(n)``
        while the gate is open, else 0 (scouts.md §0, D11)."""

        if self.scouts_conflict_troops_gate() > 0:
            return self.troop_value(amount, False)
        return 0.0

    def parked_conflict_troop_value(self, amount: int) -> float:
        """``CTp(n)``: parked (not supply) troops into the Conflict, ``UTr(n)``
        while the gate is open, else 0 (scouts.md §0, D10, D44)."""

        if self.scouts_conflict_troops_gate() > 0:
            return self.uncapped_troop_value(amount)
        return 0.0

    def scouts_later(self, value: float, delay: int) -> float:
        """``later(v, d)``: a payout ``delay`` rounds away (scouts.md §2.1,
        D13; plan §11.4, §11.5): no discount, 0 when the game may end first.

        ``d >= 1`` in the final round (``IsFinalRound``) or ``d >= 2`` in the
        climax (``IsClimax``; IsFinalRound implies IsClimax) -> 0.
        """

        if delay >= 1 and self.is_final_round():
            return 0.0
        if delay >= 2 and self.is_climax():
            return 0.0
        return value

    # ===========================================================================
    # §3.11, §4.7 Influence-4 bonuses
    # ===========================================================================

    def track_bonus_value(self, faction: str) -> float:
        """``TB(f)``: block (C) of ``GetGainInfluenceValue`` for one track
        (profile-influence-uprising §1.1, Uprising branch; scouts.md §2.1).

        Emperor ``SpyValue``, Spacing Guild 3 Solari, Bene Gesserit
        ``IntrigueValue``, Fremen 1 water (the app's block (C) literals).
        """

        if faction == "emperor":
            return self.spy_value().sum
        if faction == "spacing_guild":
            return self.resource_value(Attr.SOLARI, 3, False)
        if faction == "bene_gesserit":
            return self.intrigue_value()
        return self.resource_value(Attr.WATER, 1, False)

    def any_faction_four_bonus_value(self) -> float:
        """``max_g TB(g)`` (``FactionList`` order, first max): the Influence-4
        bonus while Friends Everywhere lets the seat pick any track's
        (scouts.md §4.7, D29)."""

        best = self.track_bonus_value(FACTIONS[0])
        for faction in FACTIONS[1:]:
            value = self.track_bonus_value(faction)
            if value > best:
                best = value
        return best

    def friends_everywhere_active(self) -> bool:
        """This round's modifier is Friends Everywhere (public)."""

        return self.ctx.scouts_round_modifier == _FRIENDS_EVERYWHERE

    # ===========================================================================
    # §2.2 Line values
    # ===========================================================================

    def scouts_line_value(
        self, line: Entity, *, uncapped_troops: bool = False
    ) -> Summer:
        """``L(x)``: the value of one Scouts line archetype (scouts.md §2.2, D1).

        ``WormSpace::ValueForPlayer``'s shape (generic §14.2): the attribute
        prices of ``ValueForRewardsFrom`` (generic §18) and the
        ``SpaceAbility`` cost lines (generic §6.1), then the merge of the
        line's abilities' ``ValueForPlayer(P, [])`` (owner = the line). The
        spec's ``L`` is the summer's ``Sum``. ``uncapped_troops`` prices the
        ``Troops`` attribute with ``UTr`` (the troop way of a mission join
        that a specimen top-up supplies, §3.4).
        """

        from dune_imperium.agents.app_ai.abilities import abilities_of
        from dune_imperium.agents.app_ai.abilities.generic import _faction_influence

        v = Summer()
        spice_cost = line.int_attr("SpiceCost")
        if spice_cost > 0:
            v.add("Scouts Spice Cost", self.spice_value(-spice_cost))
        solari_cost = line.int_attr("SolariCost")
        if solari_cost > 0:
            v.add("Scouts Solari Cost", self.solari_value(-solari_cost))
        water_cost = line.int_attr("WaterCost")
        if water_cost > 0:
            v.add("Scouts Water Cost", self.water_value(-water_cost))
        specimen_cost = line.int_attr("SpecimenCost")
        if specimen_cost > 0:
            v.add("Scouts Specimen Cost", self.specimen_value(-specimen_cost))
        for attr in (Attr.WATER, Attr.SPICE, Attr.SOLARI):
            amount = line.int_attr(attr.value)
            if amount > 0:
                v.add(attr.value, self.resource_value(attr, amount, False))
        for faction, n in _faction_influence(line):
            v.add(
                f"Influence {faction}",
                self.gain_influence_value(faction, n, -1, False).sum,
            )
        troops = line.int_attr("Troops")
        if troops > 0:
            price = (
                self.uncapped_troop_value(troops)
                if uncapped_troops
                else self.troop_value(troops, False)
            )
            v.add("Troop * n", price)
        intrigue = line.int_attr("IntrigueCard")
        if intrigue > 0:
            v.add("Intrigue * n", self.intrigue_value() * intrigue)
        specimens = line.int_attr("Specimen")
        if specimens > 0:
            v.add("Specimens", self.specimen_value(specimens))
        profile = self._p()
        for ability in abilities_of(line):
            v.merge(ability.value_for_player(profile, ()))
        return v

    def scouts_item_line_value(self, item_id: str, line: int) -> float:
        """``L(line(item, k))``: the line value of ``<item>:<k>``."""

        entity = scouts_line_entity(item_id, line, self.ctx.seat)
        return self.scouts_line_value(entity).sum

    # ===========================================================================
    # §4.5 The subcommittee opportunity
    # ===========================================================================

    def subcommittee_opportunity(self, exclude_space: str) -> float:
        """``max(0, max over joinable s of L(line of s))`` (scouts.md §2.1,
        §4.5; D23, D24).

        0 while the seat holds a council seat or has joined a subcommittee
        (``joinable_subcommittees`` is then empty). Affordability is the
        current state's (the seat's 5 Solari is not subtracted, D24).
        """

        if self.ctx.me.high_council:
            return 0.0
        best = 0.0
        for subcommittee_id in self.ctx.joinable_subcommittees(exclude_space):
            value = self.scouts_item_line_value(subcommittee_id, 0)
            if value > best:
                best = value
        return best

    # ===========================================================================
    # §3.9-3.10 Cards acquired to hand
    # ===========================================================================

    def acquire_to_hand_value(self, card: Entity) -> float:
        """``A(c) + CDV``: a card acquired into the hand (scouts.md §1
        ``AcquireReserveCardToHand``, §3.9, §3.10; D12): its
        ``AcquireValue`` and one more card in hand this round."""

        return self.acquire_value(card).sum + self.card_draw_value()

    # ===========================================================================
    # §4 Valuation terms the faithful ports call (each gated by Scouts state)
    # ===========================================================================

    def valued_informants_post_value(self, post_id: str) -> Summer:
        """Valued Informants goods on a post (scouts.md §4.3, D33): ``+ Sol(n)``
        Urban Surveillance / ``+ Spi(n)`` Planetary Exploration for the goods
        rows at ``post:<id>`` (``place_mission_goods``). Empty without them."""

        s = Summer()
        location = f"post:{post_id}"
        for mission_id, where, resource, amount, _seat in self.ctx.scouts_goods:
            if where != location or amount <= 0:
                continue
            attr = RESOURCE_ATTRS.get(resource)
            if attr is None:
                continue
            s.add(MISSIONS_BY_ID[mission_id].name, self.resource_value(attr, amount))
        return s

    def choam_escort_contract_value(self, contract_ref: str) -> Summer:
        """CHOAM Escort goods loaded on this seat's Contract ``contract_ref``
        (scouts.md §4.4, D34): ``+ Sol(1) + Spi(1)``, paid on completion
        (``claim_due_mission_goods``), one term per goods row."""

        s = Summer()
        location = f"contract:{contract_ref}"
        seat = self.ctx.seat
        for _mission, where, resource, amount, owner in self.ctx.scouts_goods:
            if where != location or owner != seat or amount <= 0:
                continue
            attr = RESOURCE_ATTRS.get(resource)
            if attr is not None:
                s.add("CHOAM Escort", self.resource_value(attr, amount))
        return s

    def sponsored_research_value(self, space_id: str) -> Summer:
        """Sponsored Research's Helix spice (scouts.md §4.6, D35): ``+ Spi(n)``
        on a first-marker research space (app idx 7-9, the first genetic
        marker's column) while the spice waits and ``GeneticMarkers == 0``
        (claim: ``rules/immortality.py``)."""

        s = Summer()
        if self.ctx.genetic_markers() != 0:
            return s
        if RESEARCH_SPACES_BY_ID[space_id].column != FIRST_GENETIC_MARKER_COLUMN:
            return s
        for _mission, where, resource, amount, _seat in self.ctx.scouts_goods:
            attr = RESOURCE_ATTRS.get(resource)
            if where == HELIX and attr is not None and amount > 0:
                s.add("Sponsored Research", self.resource_value(attr, amount))
        return s

    def back_room_deal_value(self) -> float:
        """Back Room Deal's Solari on Reclaimed Forces (scouts.md §4.6, D36):
        ``+ Sol(n)`` while the goods wait (claim ``rules/tleilaxu_row.py``)."""

        total = 0.0
        for _mission, where, resource, amount, _seat in self.ctx.scouts_goods:
            attr = RESOURCE_ATTRS.get(resource)
            if where == RECLAIMED_FORCES and attr is not None and amount > 0:
                total += self.resource_value(attr, amount)
        return total

    def tleilaxu_offering_specimens(self, amount: int) -> int:
        """Tleilaxu Offering (scouts.md §4.6, D37): the troops this seat parked
        on the Tleilaxu track's third space when ``amount`` steps from its
        rank reach it (``cur < 3 <= cur + n``); 0 otherwise."""

        current = self.ctx.tleilaxu_influence()
        if not current < TLEILAXU_OFFERING_TRACK_SPACE <= current + amount:
            return 0
        seat = self.ctx.seat
        return sum(
            troops
            for _mission, owner, location, troops in self.ctx.scouts_parked
            if owner == seat and location == TLEILAXU_OFFERING_SPACE
        )

    def market_opening_reserve_card(self, entity: Entity) -> Entity:
        """The Reserve The Spice Must Flow while Market Opening's discount is
        unused (scouts.md §4.7, D31): ``PersuasionCost`` less the engine's
        discount (9 - 2 = 7), read by PredictCardBuys/GetBuyGains and the
        AcquireValue consolidation term. Any other entity, and every entity
        outside Market Opening, is returned unchanged."""

        if self.ctx.scouts_round_modifier != _MARKET_OPENING:
            return entity
        reserve_id = entity.ref.removeprefix("reserve:")
        discount = self.ctx.market_opening_discount(reserve_id)
        if discount <= 0 or entity.archetype is None:
            return entity
        return discounted_card(entity, discount)


def discounted_card(entity: Entity, discount: int) -> Entity:
    """``entity`` with its archetype's ``PersuasionCost`` lowered by
    ``discount`` (the other attributes, ``short`` and ``ref`` unchanged)."""

    archetype = entity.archetype
    assert archetype is not None
    attributes = dict(archetype.attributes)
    attributes["PersuasionCost"] = entity.int_attr("PersuasionCost") - discount
    return replace(
        entity,
        archetype=replace(archetype, attributes=MappingProxyType(attributes)),
    )


def reserve_card(reserve_id: str) -> Entity:
    """The Reserve pile entity ``reserve:<id>`` (``economy._row_cards``)."""

    return card_entity(f"reserve:{reserve_id}")


def reserve_ids_of(short: str) -> tuple[str, ...]:
    """Our Reserve card ids whose archetype is ``short`` (Moment of
    Revelation's ``ReferencedArchetypeIDs`` -> ``prepare_the_way``)."""

    return tuple(cid for cid, arch in CARD_ARCHETYPES.items() if arch == short)
