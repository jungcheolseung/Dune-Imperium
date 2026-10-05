"""App-style Bloodlines profile terms (docs/app-ai/bloodlines-systems.md).

The app has no Bloodlines, so these are not ports: they are the app-style
helpers ``bloodlines-systems.md`` defines (§1 shared machinery, §2.2 Skill
prices, §3.3 ``HeldTileValue``, §4.1 the Tactics reward, §5 Navigation, §9 the
valuation terms of the automatic effects), built only from the profile's
existing prices (docs/app-ai-plan.md §11.3-§11.5) as settled by plan §11.7.
Section numbers below are those of ``bloodlines-systems.md``; D-numbers are
its §10 decisions.

Every method reads state through ``AppContext`` (public state and this seat's
own Bloodlines items: Kota's Secret Project and Y'rkoon's Navigation slots
are the owner's only, ``context.py`` "Bloodlines"). Nothing here runs in a
game without Bloodlines: the shared methods call these only behind their
option or behind state that exists only with it (a Bloodlines leader, a Tech
tile, a Commander or Skill), and every Bloodlines count is 0 otherwise.

Numbers: the app constants (``C.<Getter>``), our printed content
(``content/bloodlines``, ``rules/tactics.py``) and the literals of the app
code a precedent ports (named where used).
"""

from collections.abc import Callable, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

from dune_imperium.agents.app_ai.catalog import (
    POST_INDEX,
    card_entity,
    skill_entity,
    tech_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, card_id
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.bloodlines.sardaukar import COMMANDER_STRENGTH
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.effects import board_icon_is_pending
from dune_imperium.rules.tactics import (
    TACTICS_SPICE_SPACE,
    TACTICS_TRACK_END,
    uses_tactics_track,
)

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

#: A troop's strength (``WormUnit`` vslot 35; ``profile/combat.py``
#: ``_TROOP_STRENGTH``): the unit a Commander is priced against (§1.2).
TROOP_STRENGTH: Final = 2

# Our leader ids (``content/uprising/leaders.py``).
CHANI: Final = "chani"
MOHIAM: Final = "gaius_helen_mohiam"
YRKOON: Final = "steersman_y_rkoon"

# Our Tech tile ids (``content/bloodlines/tech.py``).
PLASTEEL_BLADES: Final = "plasteel_blades"
SUSPENSOR_SUITS: Final = "suspensor_suits"
SELF_DESTROYING_MESSAGES: Final = "self_destroying_messages"
SERVO_RECEIVERS: Final = "servo_receivers"

#: ``ImperiumArchetypes.BaseSet.SignetRing`` and the four Faction icons
#: Servo-Receivers prints on it (§1.7, D40; app ``IconList`` names).
SIGNET_RING: Final = "ImperiumArchetypes.BaseSet.SignetRing"
SERVO_ICONS: Final = ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen")
#: Clandestine's icon on every card Mohiam plays (§1.7, D40).
SPY_ICON: Final = "Spy"

#: Skills whose loss with the last Commander in the Conflict costs their value
#: now (strength Skills) or before the Reveal (Reveal Skills) (§1.4).
_STRENGTH_SKILLS: Final = ("canny", "fierce", "loyal")
_REVEAL_SKILLS: Final = ("charismatic", "driven", "hardy")

#: Navigation card 10's play threshold: ``ChangeAllegiancesAbility``'s
#: literal 2.0 (intrigues §7.4; D48).
NAVIGATION_EXCHANGE_THRESHOLD: Final = 2.0
#: Navigation card 9's spice cost and card 6's / card 1's Solari costs, card 2's
#: and card 4's gains (``content/uprising/intrigue.py`` Navigation cards).
_NAV9_SPICE: Final = 5
_NAV6_SOLARI: Final = 3
_NAV6_TROOPS: Final = 3
_NAV1_SOLARI: Final = 2
_NAV1_MIN_OWN: Final = 2
_NAV2_SPICE: Final = 2
_NAV3_SOLARI: Final = 2
_NAV3_SLOT: Final = 4
_NAV4_SLOT: Final = 1
_TSMF_RESERVE: Final = "the_spice_must_flow"


class BloodlinesMixin(ProfileCore):
    """The app-style Bloodlines ``Profile`` methods."""

    #: Re-entrancy guard of the Plot Course term: Navigation card 10's
    #: exchange calls ``gain_influence_value``, which would ask for the Plot
    #: Course term again (an implementation necessity, not an app rule).
    _plot_course_busy: bool = False

    def _bl_profile(self) -> Profile:
        """``self`` as the full ``Profile`` the ability hooks expect."""

        return cast("Profile", self)

    def _leader_id(self) -> str | None:
        return self.ctx.me.leader_id

    # ===========================================================================
    # §1.1 Units: the app's unit and troop counts (D1; plan §11.8)
    # ===========================================================================
    #
    # The card ports read these instead of our troop fields, so a Commander
    # (a "troop" worth 2 strength) and Duncan's Into the Fray Agent (a unit,
    # not a troop) count where the app counts every ``WormUnit`` or
    # ``WormTroop``. Each count adds the Bloodlines pieces only while the
    # option is on, so every other game reads exactly the old troop fields.
    # Supply reads stay troops only (§1.1: a supply Commander cannot be
    # recruited by a troop icon).

    def conflict_unit_count(self, player: PlayerState | None = None) -> int:
        """``P.ConflictUnits`` (§1.1): troops and sandworms in the Conflict;
        with Bloodlines also Commanders and the Into the Fray Agent
        (``PlayerState.units_in_conflict``). ``player`` defaults to this
        seat."""

        pl = self.ctx.me if player is None else player
        if self.ctx.bloodlines:
            return pl.units_in_conflict
        return pl.troops_conflict + pl.sandworms_conflict

    def conflict_troop_count(self, player: PlayerState | None = None) -> int:
        """``ConflictTroops`` / ``GetDeployedTroops`` /
        ``HasUnitsDeployed<WormTroop>`` (§1.1): troops in the Conflict; with
        Bloodlines also Commanders. Never a sandworm or the Into the Fray
        Agent."""

        pl = self.ctx.me if player is None else player
        if self.ctx.bloodlines:
            return pl.troops_conflict + pl.commanders_conflict
        return pl.troops_conflict

    def garrison_troop_count(self, player: PlayerState | None = None) -> int:
        """``GarrisonTroops`` / ``GarrisonUnits`` (§1.1, the two are the same
        set): garrison troops; with Bloodlines also garrison Commanders."""

        pl = self.ctx.me if player is None else player
        if self.ctx.bloodlines:
            return pl.troops_garrison + pl.commanders_garrison
        return pl.troops_garrison

    # ===========================================================================
    # §1.2 Commander and Skill prices
    # ===========================================================================

    def commander_unit_value(self) -> float:
        """``CommanderUnitValue`` (§1.2): a troop plus the strength above one.

        ``uncapped_troop_value(1) + strength_value(COMMANDER_STRENGTH - 2)``;
        the second term is ``GetResourceValue(Strength, 0) = 0`` with our
        2-strength Commander (``content/bloodlines/sardaukar.py``). The troop
        price skips the troop-supply cap (plan §11.8): a Commander does not
        come from the troop supply, so an empty supply must not price it at
        0 (``ScoutsMixin.uncapped_troop_value``, scouts.md §2.1; equal to
        ``troop_value(1)`` while a supply troop is left).
        """

        return self._bl_profile().uncapped_troop_value(1) + self.strength_value(
            COMMANDER_STRENGTH - TROOP_STRENGTH, False
        )

    def skill_value(
        self, skill: str | Entity, with_entities: Sequence[Entity] = ()
    ) -> float:
        """``SkillValue(skill)`` (§1.2, §2.2): Σ of the Skill's abilities' V.

        A one-time price with its condition judged now (D2, plan §11.7).
        ``skill`` is a Skill entity, a skill id or a tile instance id.
        """

        from dune_imperium.agents.app_ai.abilities import abilities_of

        entity = (
            skill if isinstance(skill, Entity) else skill_entity(skill, self.ctx.seat)
        )
        total = Summer()
        for ability in abilities_of(entity):
            total.merge(ability.value_for_player(self._bl_profile(), with_entities))
        return total.sum

    def commander_cost(self) -> int:
        """``commander_cost(me)`` (``rules/sardaukar.py``): the Solari a
        Commander costs this seat now."""

        return self.ctx.commander_cost()

    def held_tile_value(self, tile: str | Entity) -> float:
        """``HeldTileValue(t)`` (§3.3, D11 as revised by plan §11.7).

        ``AcquireValue × [EarlyMod (1.0), 1.0, LateMod (1.0)][arc]``: the
        purchase cut-offs and acquire-effect terms of the buying value are left
        out.
        """

        entity = tile if isinstance(tile, Entity) else tech_entity(tile)
        s = Summer()
        s.add("Archetype Value", entity.float_attr("AcquireValue", 0.0))
        mods = (
            entity.float_attr("EarlyMod", 1.0),
            1.0,
            entity.float_attr("LateMod", 1.0),
        )
        s.multiply("Game Arc", mods[self.game_arc()])
        return s.sum

    def plasteel_extra_skill_value(self, taken: str | None = None) -> float:
        """Plasteel Blades' extra Skill on a recruit (plan §11.7, OPEN 9).

        For the tile's owner: ``max(0, SkillValue(k*) − HeldTileValue)`` with
        ``k*`` the first strictly best Skill the seat could still take after
        ``taken`` (D10's own formula); 0 without the tile or a Skill to take.
        """

        if not self.ctx.has_tech(PLASTEEL_BLADES):
            return 0.0
        best: float | None = None
        for skill_id in self.ctx.eligible_skill_ids():
            if skill_id == taken:
                continue
            value = self.skill_value(skill_id)
            if best is None or value > best:
                best = value
        if best is None:
            return 0.0
        return max(0.0, best - self.held_tile_value(PLASTEEL_BLADES))

    def commander_acquire_net(
        self, skill: str | None, with_entities: Sequence[Entity] = ()
    ) -> float:
        """``CommanderAcquireNet(skill, with)`` (§1.2; plan §11.5, §11.7).

        ``CommanderUnitValue + SkillValue(skill) − solari_value(cost)`` plus
        Plasteel Blades' extra Skill; ``skill`` None: a Commander without one.
        """

        s = Summer()
        s.add("Commander Unit", self.commander_unit_value())
        if skill is not None:
            s.add(f"Skill {skill}", self.skill_value(skill, with_entities))
        s.add("Commander Cost", -self.solari_value(self.commander_cost()))
        s.add("Plasteel Blades Skill", self.plasteel_extra_skill_value(skill))
        return s.sum

    def recruit_net(self, cost: int | None = None) -> float:
        """``RecruitNet()`` (§1.2): the supply re-buy, no Skill attached.

        ``CommanderUnitValue − solari_value(cost)`` plus Plasteel Blades' extra
        Skill. ``cost`` defaults to ``commander_cost``; Honor Guard (cards spec
        OPEN-2) passes its discounted cost: the recruit passes the rule iff the
        result is > 0 (plan §11.4).
        """

        if cost is None:
            cost = self.commander_cost()
        s = Summer()
        s.add("Commander Unit", self.commander_unit_value())
        s.add("Commander Cost", -self.solari_value(cost))
        s.add("Plasteel Blades Skill", self.plasteel_extra_skill_value(None))
        return s.sum

    # ===========================================================================
    # §1.3 Deploying with Commanders, §1.4 retreat and forced loss
    # ===========================================================================

    def commanders_deploy_first(self) -> bool:
        """§1.3, D6: Commanders first iff a Skill is held and none fights yet."""

        me = self.ctx.me
        return bool(me.skill_ids) and me.commanders_conflict == 0

    def deploy_split(
        self, count: int, troop_max: int, commander_max: int
    ) -> tuple[int, int]:
        """§1.3: split ``units_to_deploy``'s count into (troops, Commanders).

        The kind ``commanders_deploy_first`` puts first takes as many as its
        legal maximum allows, the other kind the rest (each capped).
        """

        if self.commanders_deploy_first():
            commanders = min(count, commander_max)
            troops = min(count - commanders, troop_max)
        else:
            troops = min(count, troop_max)
            commanders = min(count - troops, commander_max)
        return troops, commanders

    def retreat_split(self, count: int) -> tuple[int, int]:
        """§1.4, D7: a retreat of ``count`` units as (troops, Commanders),
        troops first (``DesertScoutsAbility`` precedent, plan §11.5)."""

        troops = min(count, self.ctx.me.troops_conflict)
        return troops, count - troops

    def tactics_reward(self, k: int) -> float:
        """``TacticsReward(k)`` (§4.1): Chani's track advanced ``k`` spaces.

        ``spice_value(1)`` if the token passes the spice space, plus
        ``water_value(1)`` if it reaches the end (then resets; the rest of the
        advance is dropped) — ``rules/tactics.py``. 0 for other leaders.
        """

        s = Summer()
        me = self.ctx.me
        if k < 1 or not uses_tactics_track(me):
            return s.sum
        space = me.tactics_track_space
        spice = False
        water = False
        for _ in range(k):
            space += 1
            if space == TACTICS_SPICE_SPACE:
                spice = True
            if space >= TACTICS_TRACK_END:
                water = True
                break
        if spice:
            s.add("Tactics Spice", self.spice_value(1))
        if water:
            s.add("Tactics Water", self.water_value(1))
        return s.sum

    def active_skill_loss(self, skill_id: str) -> float:
        """``ActiveSkillLoss(s)`` (§1.4): what a Skill loses with the last
        Commander in the Conflict.

        Canny / Fierce / Loyal: their ``SkillValue`` now; Charismatic /
        Driven / Hardy: their ``SkillValue`` while the seat has not revealed
        this round (paid when the Reveal begins), else 0; Desperate: 0.
        "Not revealed" means the Reveal has not begun: ``has_revealed`` is
        set only when the Reveal turn ends, so the seat's own open Reveal
        turn (bonus already paid) counts as revealed.
        """

        if skill_id in _STRENGTH_SKILLS:
            return self.skill_value(skill_id)
        if (
            skill_id in _REVEAL_SKILLS
            and not self.ctx.me.has_revealed
            and self.ctx.own_frame_context("reveal") is None
        ):
            return self.skill_value(skill_id)
        return 0.0

    def lose_unit_value(self, zone: str, commander: bool) -> float:
        """``LoseUnitValue(zone, kind)`` (§1.4, D8; plan §11.4 "강제 손실").

        Garrison troop ``troop_value(1)``, garrison Commander
        ``CommanderUnitValue``, a unit in the Conflict ``strength_value(2)``
        (plus every active Skill's loss for the last Commander there); Chani's
        Conflict losses advance her track (− ``TacticsReward(1)``).
        """

        me = self.ctx.me
        s = Summer()
        if zone == "garrison":
            if commander:
                s.add("Garrison Commander", self.commander_unit_value())
            else:
                s.add("Garrison Troop", self.troop_value(1, False))
            return s.sum
        if commander:
            s.add("Conflict Commander", self.strength_value(COMMANDER_STRENGTH, False))
            if me.commanders_conflict == 1:
                for skill_id in self.ctx.skill_ids():
                    s.add(f"Skill {skill_id}", self.active_skill_loss(skill_id))
        else:
            s.add("Conflict Troop", self.strength_value(TROOP_STRENGTH, False))
        if me.leader_id == CHANI:
            s.add("Tactics", -self.tactics_reward(1))
        return s.sum

    def least_loss_choice(self, values: Sequence[float]) -> int:
        """The index of the smallest loss value (plan §11.4 "강제 손실").

        Ties are broken at random from the agent RNG: every index is shuffled
        (``make_choice``'s shuffle) and the first smallest in shuffled order
        wins.
        """

        order = list(range(len(values)))
        self.rng.shuffle(order)
        best = order[0]
        for index in order[1:]:
            if values[index] < values[best]:
                best = index
        return best

    # ===========================================================================
    # §1.7 Icon grants
    # ===========================================================================

    def icon_list(self, card: Entity) -> tuple[str, ...]:
        """This seat's ``IconList`` of ``card`` (§1.7, D40).

        The printed icons ∪ the permanent grants: Mohiam's Clandestine adds the
        Spy icon to every card, Servo-Receivers the four Faction icons to the
        Signet Ring. Without either grant: the printed list.
        """

        icons = card.list_attr("IconList")
        grants: tuple[str, ...] = ()
        if self._leader_id() == MOHIAM:
            grants = (SPY_ICON,)
        if card.short == SIGNET_RING and self.ctx.has_tech(SERVO_RECEIVERS):
            grants = (*grants, *SERVO_ICONS)
        if not grants:
            return icons
        added = [icon for icon in grants if icon not in icons]
        return (*icons, *dict.fromkeys(added))

    def best_agent_eval(
        self,
        card: Entity,
        icons: Sequence[str],
        valid_spaces: Callable[[Entity, Sequence[str]], Sequence[Entity]],
    ) -> float | None:
        """``best_s∈Valid(c) AgentEval(c, s)`` (§1.7): the card's
        ``AgentAbility::Evaluate`` total over the spaces ``valid_spaces(card,
        icons)`` lists (the caller owns legality). None without a space or an
        Agent box."""

        from dune_imperium.agents.app_ai.abilities import (
            Request,
            TargetInfo,
            abilities_of,
        )
        from dune_imperium.agents.app_ai.abilities.generic import AgentAbility

        spaces = tuple(valid_spaces(card, icons))
        if not spaces:
            return None

        for ability in abilities_of(card):
            if isinstance(ability, AgentAbility):
                answer = ability.evaluate(
                    self._bl_profile(), Request(infos=(TargetInfo(entities=spaces),))
                )
                return None if answer.response is None else answer.value
        return None

    def icon_grant_value(
        self,
        grant: Sequence[str],
        valid_spaces: Callable[[Entity, Sequence[str]], Sequence[Entity]],
    ) -> float:
        """``IconGrantValue`` (§1.7): what a decision granting ``grant`` adds.

        ``max(0, max_c best AgentEval(c ∪ grant) − max_c best AgentEval(c))``
        over the hand cards, with ``AgentEval`` the ``AgentAbility::Evaluate``
        total and ``valid_spaces(card, icons)`` the caller's legal spaces for
        a card with those icons. A side with no valid space counts 0.
        """

        with_grant: float | None = None
        without: float | None = None
        for instance in self.ctx.hand:
            card = card_entity(instance, self.ctx.seat)
            icons = self.icon_list(card)
            granted = (*icons, *(i for i in grant if i not in icons))
            a = self.best_agent_eval(card, granted, valid_spaces)
            b = self.best_agent_eval(card, icons, valid_spaces)
            if a is not None and (with_grant is None or a > with_grant):
                with_grant = a
            if b is not None and (without is None or b > without):
                without = b
        return max(0.0, (with_grant or 0.0) - (without or 0.0))

    # ===========================================================================
    # §4 Leader helpers
    # ===========================================================================

    def draw_two_value(self) -> float:
        """``Draw2()`` (§4.1): the ``Draw2ContractAbility`` price.

        ``2 × CardDrawValue + GetBuyGains(2 × PossiblePersuasionGain)``: the
        port's disassembly-corrected form (``abilities/generic.py``
        ``Draw2ContractAbility.resource_value``; the spec text writes the gain
        undoubled).
        """

        s = Summer()
        s.add("Draw 2", self.card_draw_value() * 2.0)
        s.add("Buy Gains Bonus", self.buy_gains(2 * self.possible_persuasion_gain()))
        return s.sum

    def tuek_sietch_choice_pending(self, with_entities: Sequence[Entity] = ()) -> bool:
        """Tuek's Sietch's spice-or-card choice is still to come (§4.4).

        The space in ``with_entities`` is Tuek's Sietch (a placement being
        valued), or this seat's own Agent turn is on it with the
        ``tuek_sietch`` icon pending (``board_effects.py`` pays the space's
        bonus spice with that choice).
        """

        if any(e.ref == "tuek_sietch" for e in with_entities):
            return True
        context = self.ctx.own_frame_context("agent_effects")
        return (
            context is not None
            and context.get("space_id") == "tuek_sietch"
            and board_icon_is_pending(context, "tuek_sietch")
        )

    # ===========================================================================
    # §5 Navigation (Steersman Y'rkoon)
    # ===========================================================================

    def navigation_option_value(
        self, card: int, option: int, slot: int, faction: str | None
    ) -> float | None:
        """``OptionValue(card, option, slot, F)`` (§5): None when not playable.

        ``faction`` is the triggering Faction (our id), None at setup, where
        every trigger-, alliance- and influence-conditional part is 0 (plan
        §11.4 "as now"; the influence-conditional option of card 1 and card
        10's exchange are then not available).
        """

        me = self.ctx.me
        res = me.resources
        s = Summer()
        if card == 1:
            if option == 0:
                s.add("Navigation Spice", self.spice_value(1))
                return s.sum
            if option == 1 and faction is not None and res.solari >= _NAV1_SOLARI:
                best: float | None = None
                for other in FACTIONS:  # GainAnyInfluence max over G != F
                    if other == faction:
                        continue
                    if getattr(me.influence, other) < _NAV1_MIN_OWN:
                        continue
                    value = self.gain_influence_value(other, 1, -1, False).sum
                    if best is None or value > best:
                        best = value
                if best is None:
                    return None
                s.add("Navigation Influence", best)
                s.add("Navigation Solari Cost", self.solari_value(-_NAV1_SOLARI))
                return s.sum
            return None
        if card == 2:
            if option == 0:
                if not (me.spy_post_ids or (me.spies_supply > 0 and self._free_post())):
                    return None
                s.add("Navigation Spy", self.spy_value().sum)  # PlaceSpyAbility V
                return s.sum
            if option == 1 and me.spy_post_ids:
                s.add("Navigation Recall Spy", self.recall_spy_value().sum)
                s.add("Navigation Intrigue", self.intrigue_value())
                s.add("Navigation Spice", self.spice_value(_NAV2_SPICE))
                return s.sum
            return None
        if card == 3 and option == 0:
            s.add("Navigation Solari", self.solari_value(_NAV3_SOLARI))
            if slot == _NAV3_SLOT:  # one-time price (D2, plan §11.7)
                s.add("Navigation Reveal Persuasion", self.persuasion_value(1))
            return s.sum
        if card == 4:
            if option == 0:
                s.add("Navigation Spice", self.spice_value(1))
                return s.sum
            if option == 1 and slot == _NAV4_SLOT and res.water >= 1:
                if dict(self.ctx.reserve_stacks).get(_TSMF_RESERVE, 0) <= 0:
                    return None
                tsmf = card_entity(f"reserve:{_TSMF_RESERVE}", self.ctx.seat)
                if self.ctx.scouts:  # Market Opening's discount (plan §11.8)
                    tsmf = self._bl_profile().market_opening_reserve_card(tsmf)
                s.add("Navigation TSMF", self.acquire_value(tsmf).sum)
                s.add("Navigation Water Cost", self.water_value(-1))
                return s.sum
            return None
        if card == 5 and option == 0:
            # TrashAbility V; the +2 spice is left unpriced (D47).
            s.add("Navigation Trash", self.trash_card_value())
            s.add("Navigation Trash Bonus", self.trash_mod())
            return s.sum
        if card == 6:
            if option == 0:
                s.add("Navigation Troop", self.troop_value(1, False))
                return s.sum
            if option == 1 and res.solari >= _NAV6_SOLARI:
                s.add("Navigation Troops", self.troop_value(_NAV6_TROOPS, False))
                s.add("Navigation Solari Cost", self.solari_value(-_NAV6_SOLARI))
                return s.sum
            return None
        if card == 7 and option == 0:
            s.add("Navigation Spice", self.spice_value(1))
            if faction is not None and me.alliance_faction_ids:
                s.add("Navigation Intrigue", self.intrigue_value())
            return s.sum
        if card == 8 and option == 0:
            s.add("Navigation Water", self.water_value(1))
            if faction == "spacing_guild":
                s.add("Navigation Spice", self.spice_value(1))
            return s.sum
        if card == 9:
            if option == 0:
                s.add("Navigation Draw", self.card_draw_value_with_buy_gains())
                return s.sum
            if option == 1 and res.spice >= _NAV9_SPICE:
                s.add("Navigation Spice Cost", self.spice_value(-_NAV9_SPICE))
                s.add("Navigation VP", self.victory_point_value(1))
                return s.sum
            return None
        if card == 10 and option == 0:
            if faction is None:
                return None
            _, _, value = self.best_influence_exchange(-1, 1)
            # ChangeAllegiancesAbility: played iff the exchange reaches 2.0 (D48).
            s.add(
                "Navigation Exchange",
                value if value >= NAVIGATION_EXCHANGE_THRESHOLD else 0.0,
            )
            return s.sum
        return None

    def navigation_value(self, card: int, slot: int, faction: str | None) -> float:
        """``NavigationValue(card, slot, F)`` (§5): the best playable option.

        0 when no option is playable (or worth more than 0).
        """

        best = 0.0
        for option in (0, 1):
            value = self.navigation_option_value(card, option, slot, faction)
            if value is not None and value > best:
                best = value
        return best

    def _free_post(self) -> bool:
        """An observation post with no Spy (a plain placement's target)."""

        return any(self.ctx.post_owner(post) is None for post in POST_INDEX)

    # ===========================================================================
    # §9 Valuation terms the shared methods add (each gated by the caller)
    # ===========================================================================

    def plot_course_value(self, faction: str, amount: int) -> float:
        """Y'rkoon's Plot Course term of ``GetGainInfluenceValue`` (§9, D43).

        ``amount × NavigationValue(next slot card, its slot, F)``: the card in
        the next slot (this seat's own slots) and its slot number (cards played
        + 1, ``rules/navigation.py``); 0 with no card left, and 0 inside the
        term's own evaluation (re-entrancy guard, see ``_plot_course_busy``).
        """

        slots = self.ctx.navigation_slots
        if not slots or self._plot_course_busy:
            return 0.0
        number = _navigation_number(slots[0])
        slot = len(self.ctx.navigation_played()) + 1
        self._plot_course_busy = True
        try:
            value = self.navigation_value(number, slot, faction)
        finally:
            self._plot_course_busy = False
        return amount * value

    def hungry_for_spice_value(self, space_spice: int) -> float:
        """Y'rkoon's Hungry for Spice term of ``SpaceAbility`` V (§9, D42).

        ``space_spice`` = the space's ``Spice + BonusSpice + PossibleSpice``.
        The draw (``CardDrawValue + GetBuyGains(PossiblePersuasionGain)``, the
        Count Ilban precedent) when the placement would make this turn's spice
        reach 3 for the first time (``rules/agent_effects.py``); else 0.
        """

        me = self.ctx.me
        if me.leader_id != YRKOON or me.hungry_for_spice_granted_turn:
            return 0.0
        gained = self.ctx.spice_gained_this_turn()
        if not (gained < 3 <= gained + space_spice):  # literal 3 (the card face)
            return 0.0
        return self.card_draw_value() + self.buy_gains(self.possible_persuasion_gain())

    def planetologist_value(self, amount: int) -> float:
        """Liet's ``GetResourceValue(SandWorms, n)`` (§4.8, D44).

        ``n × (TrashCardValue + TrashMod + spice_value(1) + IntrigueValue)``
        "Planetologist", replacing the sandworm value (Muad'Dib's per-worm
        add-on precedent).
        """

        s = Summer()
        if amount == 0:
            return s.sum
        s.add("Planetologist Trash", self.trash_card_value())
        s.add("Planetologist Trash Bonus", self.trash_mod())
        s.add("Planetologist Spice", self.spice_value(1))
        s.add("Planetologist Intrigue", self.intrigue_value())
        s.multiply("Amount", float(amount))
        return s.sum

    def suspensor_suits_active(self) -> bool:
        """Suspensor Suits' term condition (§9, D59): the seat owns the tile
        and is in its own Agent or Reveal turn."""

        if not self.ctx.has_tech(SUSPENSOR_SUITS):
            return False
        return (
            self.ctx.own_frame_context("agent_effects") is not None
            or self.ctx.own_frame_context("reveal") is not None
        )

    def reveal_preview_bonus(self) -> int:
        """The Bloodlines Persuasion of ``GetRevealPreview`` outside the own
        Reveal turn (§9, D62; Minimic Film precedent).

        Self-Destroying Messages +1, Charismatic +1 with a Commander in the
        Conflict, Navigation card 3's permanent Reveal Persuasion.
        """

        me = self.ctx.me
        bonus = 0
        if self.ctx.has_tech(SELF_DESTROYING_MESSAGES):
            bonus += 1
        if me.commanders_conflict > 0 and "charismatic" in self.ctx.skill_ids():
            bonus += 1
        bonus += me.reveal_persuasion_bonus
        return bonus

    def clandestine_recall_value(self) -> float:
        """Mohiam's forced Gather Intelligence (plan §11.7, OPEN 8).

        ``CardDrawValueWithBuyGains − SpyValue`` when negative (the comparison
        the app uses to decide whether it wants the recall), else 0.
        """

        diff = self.card_draw_value_with_buy_gains() - self.spy_value().sum
        return diff if diff < 0.0 else 0.0

    def counts_conflict_agent(self) -> bool:
        """``RecallAgentValue`` counts the Into the Fray Agent (D56, plan
        §11.7): Bloodlines games only."""

        return self.ctx.bloodlines and self.ctx.me.agent_in_conflict > 0


def _navigation_number(navigation_card: str) -> int:
    """The printed number of a Navigation card id (``navigation_card_<n>``)."""

    return int(card_id(navigation_card).rsplit("_", 1)[1])


def navigation_number(navigation_card: str) -> int:
    """The printed number (1-10) of a Navigation card or instance id."""

    return _navigation_number(navigation_card)


def space_with_cost_cut(space: Entity, kind: str) -> Entity:
    """A space entity with Navigation Chamber's −1 on one cost (§1.7, D60).

    ``kind`` ``"solari"`` sets the app's ``SolariDiscount`` to −1, ``"spice"``
    the NEW ``SpiceDiscount``; both feed ``SpaceAbility``'s costs and
    ``CanAgentAbilityBePlayedWithSpace``. Each discount variant of a legal
    ``agent_turn`` is its own target.
    """

    assert space.archetype is not None
    key = "SolariDiscount" if kind == "solari" else "SpiceDiscount"
    attributes = dict(space.archetype.attributes)
    attributes[key] = -1
    base = space.archetype
    return Entity(
        space.kind,
        space.ref,
        Archetype(
            short=base.short,
            kind=base.kind,
            title=base.title,
            in_uprising=base.in_uprising,
            in_uprising_choam=base.in_uprising_choam,
            attributes=MappingProxyType(attributes),
        ),
        space.owner,
    )
