"""App-style Bloodlines card abilities (docs/app-ai/bloodlines-cards.md).

The app has no Bloodlines: these classes are app-style extensions built by
the rules of docs/app-ai-plan.md §11 (§11.3 values, §11.4 decisions, §11.5
and §11.7 main-session decisions; §11.7 overrides the spec where they
differ), registered as ``worm.canis.abilities.AppStyle.Bloodlines.<Name>``
exactly as the spec names them. Each class subclasses the port of the app
base class the spec names, so the app machinery (``AgentAbility``'s agent-box
merge, ``RevealAbility``'s reveal sum, ``DeferredThresholdReached``, the
intrigue windows' ``ability_for_prompt``) treats them like app classes. The
archetypes are the synthetic ones of ``data/synthetic.py``.

Scope: spec §2 (shared machinery), §3 (27 Imperium identities, Ruthless
Leadership included), §4 (18 Intrigues), §5 (12 Twisted Intrigues), §6 (the
two Conflict cards reuse ported app classes only), §7 (8 contract tokens) and
the §9 decisions, with §11.7's Urgent Shigawire and GetRevealPreviewValue
revisions.

Numbers come from ``data/constants.py`` (``p.C``), the archetype, a literal
of the precedent app code the spec copies, or the spec's own rule; each
docstring cites its spec section. Summer arithmetic, left-to-right sums,
first-strict-best inside one source and the profile RNG as in the app ports.
State is read only through ``AppContext`` (the seat's own hand/zones and
public state) and through the engine's own legality enumeration over that
same state (``unlock_value``).

Request / answer encoding (``abilities/base``; as ``generic.py`` and
``intrigue.py``): the candidates are ``request.infos[i]`` (entities, or
``options`` for custom choices and unit indices); ``Answer.response is
None`` = nothing stored (value 0), ``()`` = "use it" with no sub-targets,
``((ref, ...), ...)`` = the chosen refs / option ints per target info. Per
class (only the infos the class reads):

- Discard-for-reward boxes (Arrakis Observer, Engineered Miracle, I Believe):
  ``infos[0]`` hand CARD entities -> ``((card,),)``.
- Trash boxes (Ruthless Leadership, Eliminate Allies, Elite Forces,
  Shrouded Counsel): ``infos[0]`` CARD entities -> ``((card,),)`` or
  ``((),)`` (TrashAbility "used, trash nothing" = decline).
- Arrakis Observer reveal: ``infos[0]`` own SPY entities -> ``((spy,),)``.
- CHOAM Demands agent: ``infos[0]`` own active CONTRACT entities.
- Disruption Tactics agent: ``infos[0].options`` = victim codes
  ``retreat_target_code(seat, commander)``.
- Engineered Miracle Command: ``infos[0]`` Imperium Row CARD entities.
- Possible Futures: ``infos[0]`` TRACK entities; answer ``((0,), (track,))``
  influence, ``((1,),)`` two troops, ``((2,), (track,))`` both (Bond).
- Southern Faith: ``((0,),)`` draw, ``((1,),)`` Bene Gesserit influence.
- Delivery Logistics reveal: ``((0,),)`` Persuasion, ``((1,),)`` contract.
- Reveal Combat icons (Ruthless Leadership, Holy War, Disruption Tactics):
  ``DeployUnitsAbility`` encoding (``infos[0].options`` garrison units).
- Plot intrigues with two printed options: ``infos[0].options`` = the
  options the engine offers (empty = all printed ones); the answer starts
  with ``(option,)``. Dependent targets per card: Insider Information
  ``infos[1]`` SPY, ``infos[2]`` trash CARD (answer ``((0,), (spy,),
  (card,)|())``); Sleeper Unit ``infos[1]`` SPY; Rapid Engineering
  ``infos[1]`` hand CARD (discard), ``infos[2]`` TRACK (two gains, answer
  ``((1,), (t1, t2))``); Twisted Devious ``infos[1]`` hand CARD,
  ``infos[2].options`` garrison troops; Twisted Discerning ``infos[1]``
  hand CARD.
- Single-option Plots: Sacred Pools ``infos[0]`` hand CARD; Tenuous Bond
  ``infos[0]`` the lose TRACKs; Twisted Ambitious ``infos[0]`` the gain
  TRACKs; Twisted Insidious / Unnatural ``infos[0]`` the other held
  INTRIGUE entities.
- Combat retreats (Battlefield Research, Withdrawal Agreement):
  ``infos[0].options`` the Conflict units (troops first), answer the first
  ``n``. The Strong Survive: ``infos[0].options`` the ChooseOne, ``infos[1]
  .options`` the retreat option's units (Tactical Option encoding).

A target info the request leaves out falls back to what the engine would
offer from the seat's own state: the hand (this card excluded), the own
Spies, the own active contracts, the Imperium Row, the opponents with a troop
in the Conflict, or one index per Conflict / garrison unit.

Window helpers (§2, §9): ``command_reached``, ``gained_spice``,
``unlock_value``, ``lose_unit_pick``, ``spy_move_pick``,
``junk_intrigue_pick``, ``draw_plot_gate``, ``rank_with``,
``retreat_target_code``/``retreat_target_of``, ``command_center_commanders``,
``grasp_arrakis_flip_pick``, ``tenuous_bond_trash_pick``,
``controlled_peek_choice``, ``optional_trash_pick``,
``reveal_preview_persuasion`` (the ``GetRevealPreviewValue`` overrides
``profile/economy.py`` dispatches to), ``appstyle_contract_terms`` and
``earn_alliance_acquire_value`` (the token terms ``profile/influence.py``
dispatches to).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar, Final
from weakref import WeakKeyDictionary

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    abilities_of,
    ability_for,
    port,
)
from dune_imperium.agents.app_ai.abilities.board import (
    Harvest3ContractAbility,
    Harvest4ContractAbility,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _HIGH_COUNCIL,
    _SWORDMASTER,
    IntrigueAbility,
    StrengthIntrigueAbility,
    _Choice,
    _current_conflict,
    _deploy_window,
    _EndgameIntrigueAbility,
    _in_player_turn,
    _intrigue_hand_count,
    _open_to,
    _placement_value,
    _space_cost,
    _trash_targets,
    intrigue_deploy_troops,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    contract_entity,
    intrigue_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.agent_turn import _placements_for_card
from dune_imperium.rules.effect_interpreter import (
    face_up_conflict_card_ids,
    factions_where_opponent_leads,
)
from dune_imperium.rules.effects import agent_turn_space_id
from dune_imperium.rules.reveal_turn import (
    COMMAND_PERSUASION,
    GENERATED_PERSUASION_KEY,
)
from dune_imperium.rules.sardaukar import commander_cost

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AS: Final = "worm.canis.abilities.AppStyle.Bloodlines."

#: ``PlayerTurnTypes`` (``intrigue.py`` keeps the same values).
_UNDETERMINED: Final = 0
_REVEAL_TURN: Final = 2

#: The engine's unit zones (``lose_intrigue_troop(zone)``, ``rules/intrigue.py``).
GARRISON: Final = "garrison"
CONFLICT: Final = "conflict"

#: Twisted Intrigue archetypes share this prefix (spec §5: ``Twisted<Name>``).
_TWISTED_PREFIX: Final = "IntrigueArchetypes.AppStyle.Twisted"

# ---------------------------------------------------------------------------
# Honest reads (AppContext) and small app helpers
# ---------------------------------------------------------------------------


def _hand(p: Profile) -> list[Entity]:
    """``P.Hand.children`` (own hand, in hand order)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.hand]


def _in_play(p: Profile) -> list[Entity]:
    """``P.AllCardsInPlay`` (our ``in_play``)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.me.in_play]


def _intrigue_hand(p: Profile) -> list[Entity]:
    """``P.IntrigueHand`` (own held Intrigue cards, in hand order)."""

    return [intrigue_entity(i, p.ctx.seat) for i in p.ctx.intrigue_cards]


def _entities(request: Request, index: int, kind: Kind) -> list[Entity]:
    """``choice.GetTargets<T>(index)``: one target info's entities of a kind."""

    if index >= len(request.infos):
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


def _options(request: Request, index: int) -> tuple[int, ...]:
    """The option ints / unit indices of target information ``index``."""

    if index >= len(request.infos):
        return ()
    return request.infos[index].options


def _own_spies(p: Profile) -> list[Entity]:
    """P's Spies on the board (the fallback when a request lists none)."""

    return [spy_entity(post, p.ctx.seat) for post in p.ctx.me.spy_post_ids]


def _unit_indices(count: int) -> tuple[int, ...]:
    """One index per unit (the fallback unit list of a request without
    ``options``; the window maps the first ``n`` back to a count)."""

    return tuple(range(count))


def _option_open(request: Request, option: int) -> bool:
    """Whether the engine offers printed option ``option`` (``infos[0]``).

    An empty ``infos[0].options`` means the request does not restrict the
    options (every printed option is considered).
    """

    offered = _options(request, 0)
    return not offered or option in offered


def _has_faction(card: Entity, faction: str) -> bool:
    """``card.FactionsList.Contains(f)`` (app faction name)."""

    return faction in g.card_factions(card)


def _other_of_faction(p: Profile, owner: Entity, faction: str) -> bool:
    """Pattern OTHER(f) (spec §0): ``(Hand ⧺ AllCardsInPlay).Any(e != Owner
    and e ∋ f)``."""

    return any(
        e.ref != owner.ref and _has_faction(e, faction)
        for e in (*_hand(p), *_in_play(p))
    )


def _in_play_other_of_faction(p: Profile, owner: Entity, faction: str) -> bool:
    """Pattern INPLAY(f) (spec §0): ``AllCardsInPlay.Any(e != Owner and e ∋
    f)``."""

    return any(e.ref != owner.ref and _has_faction(e, faction) for e in _in_play(p))


def _fremen_deck_synergy(p: Profile, pile: Pile, card: Entity) -> Summer:
    """Pattern FDP (spec §0): ``BondAbility::ValueInPileForOtherPlay``."""

    s = Summer()
    if pile is Pile.DECK and _has_faction(card, "Fremen") and not p.is_climax():
        s.add("Fremen in Deck", p.C.SynergyFremenWithBondInDeck)
    return s


def _draw_value(p: Profile) -> float:
    """``CardDrawValue + GetBuyGains(PossiblePersuasionGain())`` (the value of
    one draw in ``DrawAbility.ValueForPlayer``)."""

    return p.card_draw_value() + p.buy_gains(p.possible_persuasion_gain())


def _deployed_spies(p: Profile) -> int:
    """``GetDeployedSpies(P).Count()`` / ``SpyDeployedCount``."""

    return len(p.ctx.me.spy_post_ids)


def _conflict_troops(player: PlayerState) -> int:
    """``ConflictTroops`` with Commanders (bloodlines-systems.md §1.1: a
    Commander is a troop; the Into the Fray Agent is not)."""

    return player.troops_conflict + player.commanders_conflict


def _troop_units(player: PlayerState) -> int:
    """Troops and Commanders in the garrison and the Conflict: the units a
    ``LoseTroops`` cost can take (``rules/intrigue.py``)."""

    return (
        player.troops_garrison
        + player.troops_conflict
        + player.commanders_garrison
        + player.commanders_conflict
    )


def _garrison_units(player: PlayerState) -> int:
    """``GarrisonUnits`` with Commanders (bloodlines-systems.md §1.1)."""

    return player.troops_garrison + player.commanders_garrison


def _tech_tile_count(p: Profile) -> int:
    """``P.TechTileCount``: the seat's Tech tiles (``tech_ids``, public)."""

    return len(p.ctx.me.tech_ids)


def _dmax(a: float, b: float) -> float:
    """``System.Math.Max(double, double)``: NaN wins, else the larger."""

    if a != a:
        return a
    if b != b:
        return b
    return a if a > b else b


def _is_twisted(intrigue: Entity) -> bool:
    """A Twisted Intrigue card (Piter's deck; spec §5)."""

    short = intrigue.short
    return short is not None and short.startswith(_TWISTED_PREFIX)


def _row_cards(p: Profile) -> list[Entity]:
    """``Playmat.ImperiumRow`` cards (public, row order)."""

    return [card_entity(i) for i in p.ctx.imperium_row]


def _own_active_contracts(p: Profile) -> list[Entity]:
    """P's face-up (not completed) contracts."""

    return [contract_entity(i, p.ctx.seat) for i in p.ctx.me.active_contract_ids]


# ---------------------------------------------------------------------------
# §2.1 Command (6+)
# ---------------------------------------------------------------------------


def command_reached(p: Profile) -> bool:
    """``CommandReached(P)`` (spec §2.1).

    In the seat's own Reveal turn: the engine's Command flag, i.e. the
    Persuasion the Reveal turn *generated* reaches ``COMMAND_PERSUASION``
    (6; OQ-033: purchases never cancel it). Outside it: the app's own
    forecast ``possible_persuasion() >= 6`` (pool + High Council 2 + Assembly
    Hall + the hand's reveal previews, this card included; D4).
    """

    context = p.ctx.own_frame_context("reveal")
    if context is not None:  # P.IsInPlayerTurn(Reveal)
        value = context.get(GENERATED_PERSUASION_KEY, context.get("persuasion"))
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        return value >= COMMAND_PERSUASION
    return p.possible_persuasion() >= COMMAND_PERSUASION


@port(_AS + "CommandRevealAbility")
class CommandRevealAbility(g.DeferredAbility):
    """``AS.CommandRevealAbility`` (abstract; spec §2.1): an automatic
    "Command: reward" line of a Reveal box.

    Precedents: the ``RevealAbility`` riders and ``RebelSupplierAbility``
    (Explicit, ``AlwaysRunImmediately``, E 100). ``Cost`` = the engine's
    Command flag (``command_reached``); V = ``CommandReached ? Reward :
    empty``. A self-trash attached to a Command effect is not priced (§2.1).
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return command_reached(p)

    def reward(self, p: Profile) -> Summer:
        """The Command reward (abstract)."""

        return Summer()

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if command_reached(p):
            return self.reward(p)
        return Summer()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Rebel Supplier shape: 100 (ordering only; it runs by itself)."""

        return Answer(100.0, (), f"{type(self).__name__} | 100")


# ---------------------------------------------------------------------------
# §2.2 The Combat icon in a Reveal turn
# ---------------------------------------------------------------------------


@port(_AS + "RevealCombatIconAbility")
class RevealCombatIconAbility(g.DeployUnitsAbility):
    """``AS.RevealCombatIconAbility`` (abstract; spec §2.2, D5).

    ``DeployUnitsAbility`` with a card owner and timing Reveal
    (``SardaukarCoordinationAgentAbility`` precedent; Shadout Mapes shows the
    app deploys in a Reveal turn). V = ``Gate ? DeployValue(Owner) : empty``
    (a card owner skips DeployValue's space terms); E is
    ``DeployUnitsAbility.Evaluate`` (``GetUnitsToDeploy`` at 0.5).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def gate(self, p: Profile) -> bool:
        """The condition of the icon (abstract)."""

        return False

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if self.gate(p):
            v.add("Reveal Combat Icon", p.deploy_value(self.owner))
        return v


# ---------------------------------------------------------------------------
# §2.4 "May discard a card -> reward" (Agent box)
# ---------------------------------------------------------------------------


@port(_AS + "DiscardForRewardAgentAbility")
class DiscardForRewardAgentAbility(g.DeferredAbility):
    """``AS.DiscardForRewardAgentAbility`` (abstract; spec §2.4).

    Precedents ``SpacetimeFoldingAbility`` (imperium-b.md) and the Guild bonus
    of ``GuildSpyAgentAbility`` (imperium-a.md §2.19). Agent, Optional, Cost
    = a card in hand. With ``SG_BONUS`` False the pick is
    ``GetDiscardOrder(targets, false)`` (Captured Mentat's E).
    """

    timing: ClassVar[Timing] = Timing.AGENT
    SG_BONUS: ClassVar[bool] = False

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``HasImperiumCardInHand``."""

        return len(p.ctx.hand) > 0

    def reward(self, p: Profile) -> float:
        """The reward of the discard (abstract)."""

        return 0.0

    def sg_reward(self, p: Profile) -> float:
        """The extra reward of a Spacing Guild discard (``SG_BONUS``)."""

        return 0.0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``E``: ``DiscardValue + Reward`` (+ ``SgReward`` for a Guild card)
        on ``GetDiscardOrder(targets, SgBonus)[0]``; used iff > 0."""

        choice = _Choice()
        s = Summer()
        s.add("Discard", p.discard_value())
        s.add("Reward", self.reward(p))
        targets = _entities(request, 0, Kind.CARD) or [
            c for c in _hand(p) if c.ref != self.owner.ref
        ]
        order = p.discard_order(targets, self.SG_BONUS)
        if not order:
            return choice.answer(f"{type(self).__name__} | no card")
        card = order[0]
        if self.SG_BONUS and _has_faction(card, "SpacingGuild"):
            s.add("Spacing Guild Reward", self.sg_reward(p))
        choice.update_targets(s.sum, (card.ref,))
        return choice.answer(f"{type(self).__name__} | discard {card.ref}")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``V``: ``HandCount >= 2`` -> Discard + Reward; at placement
        (``with.Any()``) the Guild reward when the first of
        ``GetDiscardOrder(hand - this, true)`` is a Guild card."""

        v = Summer()
        if len(p.ctx.hand) < 2:
            return v
        v.add(f"{type(self).__name__} Discard", p.discard_value())
        v.add(f"{type(self).__name__} Reward", self.reward(p))
        if self.SG_BONUS and with_entities:
            others = [c for c in _hand(p) if c.ref != self.owner.ref]
            order = p.discard_order(others, True)
            if order and _has_faction(order[0], "SpacingGuild"):
                v.add(f"{type(self).__name__} SG Reward", self.sg_reward(p))
        return v


# ---------------------------------------------------------------------------
# §2.5 "If you gained n or more spice this turn"
# ---------------------------------------------------------------------------


def spice_gained_this_turn(p: Profile) -> int:
    """``P.HasGainedSpiceThisTurn`` count: spice now - spice at turn start +
    spice spent this turn (the engine's gate, as ``LeverageAbility``)."""

    me = p.ctx.me
    return me.resources.spice - me.spice_at_turn_start + me.spice_spent_turn


def gained_spice(p: Profile, with_entities: Sequence[Entity], n: int) -> bool:
    """``GainedSpice(P, with, n)`` (spec §2.5, D6).

    Already gained this turn, or the candidate space gives it
    (``Spice + BonusSpice``, the ``Harvest3ContractAbility`` V precedent).
    """

    if spice_gained_this_turn(p) >= n:
        return True
    space = g.collect_first(with_entities, Kind.SPACE)
    if space is None:
        return False
    return space.int_attr("Spice") + g._space_bonus_spice(p, space) >= n


# ---------------------------------------------------------------------------
# §2.7 UnlockValue (OPEN-4: the engine's own placement enumeration)
# ---------------------------------------------------------------------------

#: A grant: the seat's ``PlayerState`` as it would be after the effect.
type Grant = Callable[[PlayerState], PlayerState]


def grant_emperor_icon(me: PlayerState) -> PlayerState:
    """Emperor's Invitation: "The card you play this turn has the Emperor
    icon" (``GrantAgentIconThisTurn``)."""

    return replace(me, granted_agent_icon_turn=AgentIcon.EMPEROR.value)


def grant_resourceful_icons(me: PlayerState) -> PlayerState:
    """Twisted Resourceful: the Landsraad, City and Spice Trade icons
    (``GrantAgentIconsThisTurn``, appended as the engine does)."""

    granted = [v for v in me.granted_agent_icon_turn.split(",") if v]
    for icon in (AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE):
        if icon.value not in granted:
            granted.append(icon.value)
    return replace(me, granted_agent_icon_turn=",".join(granted))


def grant_ignore_requirements(me: PlayerState) -> PlayerState:
    """Insider Information: ignore Influence requirements this turn."""

    return replace(me, ignores_influence_requirements_turn=True)


def grant_bene_gesserit_boost(me: PlayerState) -> PlayerState:
    """Urgent Shigawire: the next Bene Gesserit card has every Agent icon."""

    return replace(me, bene_gesserit_boost_pending=True)


#: Per-decision caches (one ``Profile`` per decision): pair values and
#: finished ``unlock_value`` results.
_PAIR_CACHE: WeakKeyDictionary[Profile, dict[tuple[str, str], float | None]] = (
    WeakKeyDictionary()
)
_UNLOCK_CACHE: WeakKeyDictionary[Profile, dict[tuple[object, ...], float]] = (
    WeakKeyDictionary()
)
#: Profiles inside an ``unlock_value`` computation (re-entrancy guard: a
#: placement value that itself asks for an unlock, Urgent Shigawire's V,
#: answers 0 for the unlock term instead of recursing).
_UNLOCKING: set[int] = set()


def unlock_active(p: Profile) -> bool:
    """Whether ``p`` is inside an ``unlock_value`` computation."""

    return id(p) in _UNLOCKING


def _card_spaces(p: Profile, owner: PlayerState, card_ref: str) -> list[str]:
    """The spaces ``card_ref`` can be placed on for ``owner`` (engine order).

    ``rules/agent_turn._placements_for_card`` over the seat's own hand card,
    its own state (``owner``, possibly with a grant applied) and the public
    board (occupancy, Spies, leaders); no Graft variant. The Immortality
    Graft port reads placements the same way.
    """

    actions = _placements_for_card(
        p.ctx.state,
        p.ctx.seat,
        owner,
        card_ref,
        personal_card_for_instance(card_ref),
        False,
    )
    spaces: list[str] = []
    for action in actions:
        for key, value in action.arguments:
            if key == "space_id" and isinstance(value, str) and value not in spaces:
                spaces.append(value)
    return spaces


def _agent_ability(card: Entity) -> g.AgentAbility | None:
    """``card.Abilities.OfType<AgentAbility>().FirstOrDefault()``."""

    for ability in abilities_of(card):
        if isinstance(ability, g.AgentAbility):
            return ability
    return None


def _pair_value(p: Profile, card: Entity, space_id: str) -> float | None:
    """``AgentAbility::Evaluate``'s total for one (card, space) pair.

    ``Σ space abilities' V(P, [card]) + card.AgentAbility.V(P, [space])``;
    None when no ``SpaceAbility`` of the space can run (the app skips it).
    Called only inside ``unlock_value`` (the cache holds the values the
    re-entrancy guard produced).
    """

    cache = _PAIR_CACHE.setdefault(p, {})
    key = (card.ref, space_id)
    if key in cache:
        return cache[key]
    agent = _agent_ability(card)
    value: float | None = None
    if agent is not None:
        space = space_entity(space_id, p.ctx.board)
        answer = agent.evaluate(p, Request((TargetInfo((space,)),)))
        value = answer.value if answer.response is not None else None
    cache[key] = value
    return value


def _best(values: Sequence[float | None]) -> float | None:
    """The first strict maximum of the non-None values."""

    best: float | None = None
    for value in values:
        if value is not None and (best is None or value > best):
            best = value
    return best


def unlock_value(
    p: Profile, grant: Grant, cards: Sequence[Entity] | None = None
) -> float:
    """``UnlockValue(P, grant)`` (spec §2.7; OPEN-4).

    ``best_new - best_now``: ``best_now`` is the best ``AgentAbility``
    total over the (card, space) pairs legal now (0 if none);
    ``best_new`` the best over the pairs that become legal only under
    ``grant`` (of ``cards``, default the whole hand). 0 when the grant
    unlocks nothing. Legality is our engine's per-card placement
    enumeration on the seat's own hand and state and the public board, with
    ``grant`` applied to the seat's ``PlayerState`` only (no hidden state).
    A nested call (a placement value that asks for an unlock itself) answers
    0.
    """

    if id(p) in _UNLOCKING:
        return 0.0
    hand = _hand(p)
    candidates = hand if cards is None else list(cards)
    cache_key = (grant, tuple(c.ref for c in candidates))
    cached = _UNLOCK_CACHE.setdefault(p, {}).get(cache_key)
    if cached is not None:
        return cached
    _UNLOCKING.add(id(p))
    try:
        me = p.ctx.me
        granted = grant(me)
        now: dict[str, list[str]] = {c.ref: _card_spaces(p, me, c.ref) for c in hand}
        new_values: list[float | None] = []
        for card in candidates:
            legal_now = now.get(card.ref)
            if legal_now is None:
                legal_now = _card_spaces(p, me, card.ref)
            for space_id in _card_spaces(p, granted, card.ref):
                if space_id not in legal_now:
                    new_values.append(_pair_value(p, card, space_id))
        best_new = _best(new_values)
        if best_new is None:
            result = 0.0
        else:
            now_values = [
                _pair_value(p, card, space_id)
                for card in hand
                for space_id in now[card.ref]
            ]
            best_now = _best(now_values)
            result = best_new - (best_now if best_now is not None else 0.0)
    finally:
        _UNLOCKING.discard(id(p))
    _UNLOCK_CACHE[p][cache_key] = result
    return result


# ---------------------------------------------------------------------------
# §2.8-§2.13 Helpers for the decision windows
# ---------------------------------------------------------------------------


def lose_unit_pick(
    p: Profile, options: Sequence[tuple[str, bool]]
) -> tuple[str, bool] | None:
    """``LoseUnitPick`` (spec §2.8, D14): which unit pays a unit cost.

    ``options`` = the (zone, is Commander) pairs the engine offers
    (``lose_intrigue_troop(zone[, commanders])``). Precedent Tleilaxu
    Surgeon's reveal / Piter: the **garrison** first when
    ``EstimatedConflictRank(0)`` has a value (a reward place is expected),
    else the **Conflict** (stable, offer order); inside a zone troops before
    Commanders (Desert Scouts, plan §11.5). Own costs only: the victim's
    ``opponent_unit_loss`` follows plan §11.4/§11.5 (least loss,
    bloodlines-systems.md §1.4).
    """

    if not options:
        return None
    preferred = GARRISON if p.estimated_conflict_rank(0) is not None else CONFLICT
    ordered = sorted(
        options, key=lambda option: (option[0] != preferred, bool(option[1]))
    )
    return ordered[0]


def spy_move_pick(p: Profile, posts: Sequence[Entity]) -> Entity | None:
    """``SpyMovePick`` (spec §2.9): the victim's forced Spy move goes to
    ``GetBestPost(allowed posts)`` (``PostValue`` never reads occupancy)."""

    post, _ = p.best_post(posts)
    return post


def _is_bad_intrigue(p: Profile, card: Entity) -> bool:
    """``WormIntriguePlayable::IsBadIntrigue`` = OR over its abilities."""

    for ability in abilities_of(card):
        hook = getattr(ability, "is_bad_intrigue", None)
        if callable(hook) and bool(hook(p)):
            return True
    return False


def junk_intrigue_pick(p: Profile, intrigues: Sequence[Entity]) -> Entity | None:
    """``JunkIntriguePick`` (spec §2.10): ``BranchingPathAbility::Evaluate``.

    The candidates shuffled with the profile RNG, each scored ``IsBadIntrigue
    ? 5.0 : 1.0`` (literals), the first strict best kept. The price of the
    lost card is ``trash_intrigue_value()``.
    """

    shuffled = list(intrigues)
    p.rng.shuffle(shuffled)
    best: Entity | None = None
    best_value = 0.0
    for card in shuffled:
        value = 5.0 if _is_bad_intrigue(p, card) else 1.0
        if best is None or value > best_value:
            best, best_value = card, value
    return best


def draw_plot_gate(p: Profile) -> bool:
    """``DrawPlotGate(P)`` (spec §2.12): ``CunningAbility``'s gate without
    its spice clause."""

    return (
        _intrigue_hand_count(p) > 3
        or p.is_final_round()
        or (_in_player_turn(p, _UNDETERMINED) and p.ctx.me.agents_available > 0)
        or (
            _in_player_turn(p, _REVEAL_TURN)
            and p.buy_gains(p.possible_persuasion_gain()) >= 1.0
        )
    )


def rank_with(p: Profile, strengths: Mapping[int, int]) -> int | None:
    """``RankWith(P, strengths)`` (spec §2.13): the app's ``GetConflictRank``
    (rank 1 + the sizes of the groups above, +1 if tied; beyond 3 in 4p /
    2 otherwise: None) on a modified strength list. ``strengths`` maps
    seats to strength; a missing seat keeps its current strength."""

    players = p.ctx.players
    max_rank = (1 if len(players) >= 4 else 0) | 2
    keys = {
        pl.player_id: strengths.get(pl.player_id, pl.combat_strength) for pl in players
    }
    ordered = sorted(keys, key=lambda seat: keys[seat], reverse=True)
    rank = 1
    index = 0
    while index < len(ordered):
        key = keys[ordered[index]]
        group = [seat for seat in ordered[index:] if keys[seat] == key]
        index += len(group)
        if p.ctx.seat not in group:
            rank += len(group)
            continue
        rank += 1 if len(group) >= 2 else 0
        return rank if rank <= max_rank else None
    return None


def retreat_target_code(seat: int, commander: bool) -> int:
    """Disruption Tactics victim code: ``2 * seat + commander``."""

    return 2 * seat + (1 if commander else 0)


def retreat_target_of(code: int) -> tuple[int, bool]:
    """The (seat, commander) of a ``retreat_target_code``."""

    return code // 2, code % 2 == 1


def command_center_commanders(p: Profile) -> int:
    """Command Center's retreat: Commanders only for the troops missing
    (spec §3.5): ``max(0, 2 - ConflictTroops)``."""

    return max(0, 2 - p.ctx.me.troops_conflict)


def _battle_icon(card_id_: str) -> str:
    """Our battle icon of a face-up Objective or won Conflict card ("" when it
    prints none, e.g. Economic Supremacy); ``GetBattleIconValue`` takes it."""

    objective = OBJECTIVES_BY_ID.get(card_id_)
    if objective is not None:
        return str(objective.battle_icon)
    conflict = CONFLICTS_BY_ID.get(card_id_)
    if conflict is None or conflict.battle_icon is None:
        return ""
    return str(conflict.battle_icon)


def grasp_arrakis_flip_pick(p: Profile, card_ids: Sequence[str]) -> str | None:
    """Grasp Arrakis' ``flip_battle_card`` (spec §4.1, D17): the face-up
    Conflict card (an Objective counts, OQ-005) with the lowest
    ``GetBattleIconValue`` of its icon (the cheapest loss, plan §11.4; the
    half runs after ``ScoreBattleIconsPairs``), first in the engine's order
    on ties."""

    best: str | None = None
    best_value = 0.0
    for card in card_ids:
        value = p.battle_icon_value(_battle_icon(card)).sum
        if best is None or value < best_value:
            best, best_value = card, value
    return best


def tenuous_bond_trash_pick(p: Profile, cards: Sequence[Entity]) -> Entity | None:
    """Tenuous Bond's trashed discard-pile card (spec §4.1):
    ``GetCardToTrash(eligible, 0.0)`` (LLtF threshold), else the lowest
    ``AcquireValue``, first in engine order on ties (Shishakli fallback)."""

    card, _ = p.card_to_trash(cards, 0.0)
    if card is not None:
        return card
    best: Entity | None = None
    best_value = 0.0
    for candidate in cards:
        value = p.acquire_value(candidate).sum
        if best is None or value < best_value:
            best, best_value = candidate, value
    return best


def optional_trash_pick(p: Profile, cards: Sequence[Entity]) -> Entity | None:
    """ "Junk or decline" (``TrashAbility::Evaluate``): ``GetCardToTrash(
    targets, 1.0)`` (Insider Information, The Strong Survive)."""

    card, _ = p.card_to_trash(cards, 1.0)
    return card


#: Twisted Controlled's peek answers (``rules/intrigue.py``).
DISCARD_TOP: Final = "discard_top_card"
DRAW_TOP_FOR_SOLARI: Final = "draw_top_card_for_solari"
PUT_BACK_TOP: Final = "put_back_top_card"


def controlled_peek_choice(p: Profile, top: Entity) -> str:
    """Twisted Controlled after the peek (spec §5, D20; LLtF evaluator).

    Junk (``GetCardToTrash([top], 0.0)``) -> discard it; else draw it for 1
    Solari when ``draw + Solari(-1) > 0`` and a Solari is held; else put it
    back.
    """

    card, _ = p.card_to_trash([top], 0.0)
    if card is not None:
        return DISCARD_TOP
    if p.ctx.me.resources.solari >= 1 and _draw_value(p) + p.solari_value(-1) > 0:
        return DRAW_TOP_FOR_SOLARI
    return PUT_BACK_TOP


# ---------------------------------------------------------------------------
# §2.11 Acquire-effect bonuses
# ---------------------------------------------------------------------------


@port(_AS + "AcquirePlaceSpyBonusAbility")
class AcquirePlaceSpyBonusAbility(g.ActivatedAbility):
    """``AS.AcquirePlaceSpyBonusAbility`` (spec §2.11; plan §11.5).

    The app's ``GetAcquireEffectsValue`` prices a ``PlaceSpy`` acquire effect
    at 0; the ``ChaumurkyAbility.SpecificAcquireValue`` precedent adds the
    effect's price per card. No E; never offered.
    """

    def specific_acquire_value(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Acquire Place Spy", p.spy_value().sum)
        return v


@port(_AS + "AcquireContractBonusAbility")
class AcquireContractBonusAbility(g.ActivatedAbility):
    """``AS.AcquireContractBonusAbility`` (spec §2.11): the acquire effect
    "take a contract" at ``GainContractAbility.ContractValueForPlayer`` (the
    contract value with options, else 2 Solari)."""

    def specific_acquire_value(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Acquire Contract", g.contract_value_for_player(p).sum)
        return v


# ===========================================================================
# §3 Imperium cards
# ===========================================================================

# -- §3.1 Ruthless Leadership (promo) --


@port(_AS + "RuthlessLeadershipTrashAbility")
class RuthlessLeadershipTrashAbility(g.TrashAgentAbility):
    """``AS.RuthlessLeadershipTrashAbility`` (spec §3.1; precedent
    ``BeneGesseritTrashAbility``). Cost: a Commander in the Conflict, then
    the ``TrashAbility`` cost. E = ``TrashAbility.Evaluate``."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.commanders_conflict >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """A Commander in the Conflict or the garrison (D8: the garrison may
        still deploy, ``ChaniCleverTacticianAgentAbility`` V) -> the
        ``TrashAbility`` V (``TrashCardValue + TrashMod``)."""

        me = p.ctx.me
        if me.commanders_conflict + me.commanders_garrison >= 1:
            return super().value_for_player(p, with_entities)
        return Summer()


@port(_AS + "RuthlessLeadershipCommandAbility")
class RuthlessLeadershipCommandAbility(RevealCombatIconAbility):
    """``AS.RuthlessLeadershipCommandAbility`` (spec §3.1): "Command: Combat
    icon"; Gate = ``CommandReached``."""

    def gate(self, p: Profile) -> bool:
        return command_reached(p)


# -- §3.2 Arrakis Observer --


@port(_AS + "ArrakisObserverAgentAbility")
class ArrakisObserverAgentAbility(DiscardForRewardAgentAbility):
    """``AS.ArrakisObserverAgentAbility`` (spec §3.2): discard -> Spy with
    Deep Cover; +2 spice for a Guild discard."""

    SG_BONUS: ClassVar[bool] = True

    def reward(self, p: Profile) -> float:
        return p.spy_value().sum

    def sg_reward(self, p: Profile) -> float:
        return p.spice_value(2)


@port(_AS + "ArrakisObserverRevealAbility")
class ArrakisObserverRevealAbility(g.DeferredAbility):
    """``AS.ArrakisObserverRevealAbility`` (spec §3.2): "may recall a Spy ->
    3 swords". Reveal, Optional, Cost ``HasAtLeastSpiesOnBoard(1)``;
    precedents ``SpyNetworkAbility`` (recall pricing) and
    ``CalculusofPowerEmperorAbility`` (3 Strength)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return _deployed_spies(p) >= 1

    def _value(self, p: Profile) -> Summer:
        s = Summer()
        s.add("3 Strength", p.strength_value(3, False))
        s.add("Recall Spy", p.recall_spy_value().sum)
        return s

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if self.meets_cost(p):
            return self._value(p)
        return Summer()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GetRecallSpy`` (worst post) at 3 Strength + RecallSpyValue; used
        iff > 0."""

        choice = _Choice()
        spy, _ = p.recall_spy(_entities(request, 0, Kind.SPY) or _own_spies(p))
        if spy is None:
            return choice.answer("Arrakis Observer | no spy")
        choice.update_targets(self._value(p).sum, (spy.ref,))
        return choice.answer(f"Arrakis Observer | recall {spy.ref}")


# -- §3.3 Bombast --


@port(_AS + "BombastCommandAbility")
class BombastCommandAbility(CommandRevealAbility):
    """``AS.BombastCommandAbility`` (spec §3.3): "Command: 3 Solari, then
    trash this card" (the self-trash is not priced)."""

    def reward(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Bombast Command Solari", p.solari_value(3))
        return v


# -- §3.4 CHOAM Demands --


def _contract_resource_value(p: Profile, contract: Entity) -> float | None:
    """``c.ContractAbility.GetResourceValue(P).Sum`` (vslot 91)."""

    ability = g._first_contract_ability(contract)
    if ability is None:
        return None
    return ability.resource_value(p).sum


@port(_AS + "CHOAMDemandsAgentAbility")
class CHOAMDemandsAgentAbility(g.DeferredAbility):
    """``AS.CHOAMDemandsAgentAbility`` (spec §3.4): "complete one of your
    contracts (condition ignored)". Agent, Explicit, not automatic."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """The best own active contract's ``GetResourceValue`` (first max)."""

        v = Summer()
        best = _best([_contract_resource_value(p, c) for c in _own_active_contracts(p)])
        if best is not None:
            v.add("CHOAM Demands Contract", best)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Each target contract at its ``GetResourceValue``; first strict best
        (forced: the window answers ``DefaultRandomChoice`` when nothing is
        worth more than 0)."""

        choice = _Choice()
        targets = _entities(request, 0, Kind.CONTRACT) or _own_active_contracts(p)
        for contract in targets:
            value = _contract_resource_value(p, contract)
            if value is not None:
                choice.update_targets(value, (contract.ref,))
        return choice.answer("CHOAM Demands")


@port(_AS + "CHOAMDemandsRevealAbility")
class CHOAMDemandsRevealAbility(g.DeferredAbility):
    """``AS.CHOAMDemandsRevealAbility`` (spec §3.4; precedent
    ``DeliveryAgreementRevealAbility``): with >= 4 completed contracts, may
    trash this -> +1 Influence in all four factions (the card is not
    priced)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return len(p.ctx.me.completed_contract_ids) >= 4

    def _value(self, p: Profile) -> Summer:
        s = Summer()
        for faction in FACTIONS:
            s.add(
                f"Gain {faction} Influence",
                p.gain_influence_value(faction, 1, -1, False).sum,
            )
        return s

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if self.meets_cost(p):
            return self._value(p)
        return Summer()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if self.meets_cost(p):
            choice.update_targets(self._value(p).sum, None)
        return choice.answer("CHOAM Demands Reveal")


# -- §3.5 Command Center --


@port(_AS + "CommandCenterAgentAbility")
class CommandCenterAgentAbility(g.DeferredAbility):
    """``AS.CommandCenterAgentAbility`` (spec §3.5; ``WheelsWithinWheels
    EmperorAbility`` shape): Agent, Explicit, runs by itself, Cost Emperor
    influence >= 2; E = DeferValue (inherited)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.influence.emperor >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if p.ctx.me.influence.emperor >= 2:
            v.add("Command Center Troop", p.troop_value(1, False))
        return v


@port(_AS + "CommandCenterRevealAbility")
class CommandCenterRevealAbility(g.DeferredAbility):
    """``AS.CommandCenterRevealAbility`` (spec §3.5, D25): "may retreat two
    troops -> +2 Persuasion". Reveal, Optional, Cost two troops (Commanders
    count, [Bloodlines p. 4]) in the Conflict. Go to Ground precedent: the
    retreat test ``ShouldPlayRetreatIntrigue("Command Center", 2, 6, 2)``
    passed, the value is the reward."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return _conflict_troops(p.ctx.me) >= 2

    def _passes(self, p: Profile) -> bool:
        s = p.should_play_retreat_intrigue("Command Center", 2, 6, 2)
        return s > 0 and _conflict_troops(p.ctx.me) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if self._passes(p):
            v.add("Command Center Persuasion", p.persuasion_value(2))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if self._passes(p):
            choice.update_targets(p.persuasion_value(2), None)
        return choice.answer("Command Center Reveal")


# -- §3.6 Corrupt Bureaucrat --


@port(_AS + "CorruptBureaucratAgentAbility")
class CorruptBureaucratAgentAbility(g.GainContractAbility):
    """``AS.CorruptBureaucratAgentAbility`` (spec §3.6, D7): take a contract
    if you recalled a Spy this turn. Cost ``HasRecalledSpy`` then the base
    (``PublicSpectacleAbility`` pattern); V gated by the recall (Rebel
    Supplier / Imperial Spymaster); E = ``ContractEvaluate(forced=True)``."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.spies_recalled_turn > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if p.ctx.me.spies_recalled_turn > 0:
            return g.contract_value_for_player(p)
        return Summer()


@port(_AS + "CorruptBureaucratDiscardAbility")
class CorruptBureaucratDiscardAbility(g.TriggeredAbility):
    """``AS.CorruptBureaucratDiscardAbility`` (spec §3.6): "when discarded: 3
    Solari". No AI hook (``SpacingGuildsFavorDiscardAbility`` precedent); the
    interest comes from the ``IncentiveDiscard`` tag."""


# -- §3.7 Delivery Logistics --


@port(_AS + "DeliveryLogisticsRevealAbility")
class DeliveryLogisticsRevealAbility(g.DeferredAbility):
    """``AS.DeliveryLogisticsRevealAbility`` (spec §3.7;
    ``DeliveryAgreementRevealAbility`` shape): 1 Persuasion OR take a
    contract. Reveal, Explicit."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        v.add(
            "Delivery Logistics Reveal",
            _dmax(p.persuasion_value(1), g.contract_value_for_player(p).sum),
        )
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Option 0 (Persuasion) stored first; option 1 (contract) replaces it
        only when strictly greater."""

        choice = _Choice()
        choice.update_responses(p.persuasion_value(1), ((0,),))
        choice.update_responses(g.contract_value_for_player(p).sum, ((1,),))
        return choice.answer("Delivery Logistics Reveal")


# -- §3.8 Disruption Tactics --


def _strength_after_retreat(player: PlayerState) -> int:
    """The strength a seat keeps after one troop (or Commander) retreats.

    Spec §3.8 writes ``o.Strength − 2``; our rule (``rules/units.py``
    ``retreat_units``): each unit carried two strength and "a player left
    without units keeps no strength at all" [Main pp. 12, 14] [Bloodlines
    p. 4], so the last unit's retreat leaves 0 and the total never drops
    below 0.
    """

    if player.units_in_conflict - 1 <= 0:
        return 0
    return max(player.combat_strength - 2, 0)


def disruption_gain(p: Profile, victim: int) -> float:
    """``Gain(P, o)`` (spec §3.8, D9): the change of P's own reward place
    value when ``victim`` loses a troop (``StrengthIntrigueAbility`` reward
    delta, intrigues.md §5.2); the harm itself is 0 (plan §11.4). The
    victim's new strength follows our retreat rule
    (``_strength_after_retreat``)."""

    conflict = _current_conflict(p)
    if conflict is None or p.ctx.me.combat_strength <= 0:
        return 0.0
    current = {pl.player_id: pl.combat_strength for pl in p.ctx.players}
    rank_now = rank_with(p, current)
    v_cur = _placement_value(p, conflict, rank_now if rank_now is not None else 4)
    after = dict(current)
    after[victim] = _strength_after_retreat(p.ctx.player(victim))
    rank_new = rank_with(p, after)
    v_new = _placement_value(p, conflict, rank_new if rank_new is not None else 4)
    return v_new - v_cur


@port(_AS + "DisruptionTacticsAgentAbility")
class DisruptionTacticsAgentAbility(g.DeferredAbility):
    """``AS.DisruptionTacticsAgentAbility`` (spec §3.8): one opponent's troop
    retreats from the Conflict. Agent, Explicit (mandatory; P picks)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``max(0, max_o Gain(P, o))`` over opponents with a troop or
        Commander in the Conflict."""

        best = 0.0
        for opponent in p.ctx.opponents:
            if _conflict_troops(opponent) > 0:
                best = _dmax(best, disruption_gain(p, opponent.player_id))
        v = Summer()
        v.add("Disruption Tactics Retreat", best)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Each victim code at ``Gain``; first strict best (forced)."""

        choice = _Choice()
        codes = _options(request, 0) or tuple(
            retreat_target_code(o.player_id, o.troops_conflict == 0)
            for o in p.ctx.opponents
            if _conflict_troops(o) > 0
        )
        for code in codes:
            seat, _ = retreat_target_of(code)
            choice.update_targets(disruption_gain(p, seat), (code,))
        return choice.answer("Disruption Tactics")


@port(_AS + "DisruptionTacticsRevealAbility")
class DisruptionTacticsRevealAbility(RevealCombatIconAbility):
    """``AS.DisruptionTacticsRevealAbility`` (spec §3.8): "may trash this
    card -> Combat icon"; Optional, Gate true, E inherited (the card loss is
    not priced)."""

    def gate(self, p: Profile) -> bool:
        return True


# -- §3.9 Eliminate Allies --


@port(_AS + "EliminateAlliesTrashAbility")
class EliminateAlliesTrashAbility(g.TriggeredAbility):
    """``AS.EliminateAlliesTrashAbility`` (spec §3.9): "when trashed: recruit
    2". No AI hook (``SardaukarSoldierAbility`` precedent; no TrashValue,
    §1.2)."""


# -- §3.10 Elite Forces --


@port(_AS + "EliteForcesAgentAbility")
class EliteForcesAgentAbility(g.TrashAbility):
    """``AS.EliteForcesAgentAbility`` (spec §3.10): may trash a hand card; an
    Emperor card -> Intrigue + troop + Combat icon. Agent, Optional;
    precedents ``TreacherousManeuverAbility`` (the Emperor pick, the card not
    priced) and ``TrashAbility`` (junk)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def _reward(self, p: Profile) -> Summer:
        s = Summer()
        s.add("Elite Forces Intrigue", p.intrigue_value())
        s.add("Elite Forces Troop", p.troop_value(1, False))
        s.add("Elite Forces Deploy", p.deploy_value(self.owner))
        return s

    def _emperor_pick(self, p: Profile, emperor: Sequence[Entity]) -> Entity | None:
        """The Treacherous Maneuver pick: junk (``GetCardToTrash(emp, 0.0)``),
        else the first costing < 4, else (climax only) the first."""

        card, _ = p.card_to_trash(emperor, 0.0)
        if card is None:
            card = next((c for c in emperor if c.int_attr("PersuasionCost") < 4), None)
        if card is None and p.is_climax() and emperor:
            card = emperor[0]
        return card

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        emperor = [
            c
            for c in _hand(p)
            if c.ref != self.owner.ref and _has_faction(c, "Emperor")
        ]
        if not emperor or self._emperor_pick(p, emperor) is None:
            return Summer()
        return self._reward(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        targets = _entities(request, 0, Kind.CARD) or [
            c for c in _hand(p) if c.ref != self.owner.ref
        ]
        emperor = [c for c in targets if _has_faction(c, "Emperor")]
        best: tuple[float, Entity] | None = None
        card = self._emperor_pick(p, emperor)
        if card is not None:
            best = (self._reward(p).sum, card)
        junk, junk_value = p.card_to_trash(targets, 1.0)
        if junk is not None and (best is None or junk_value > best[0]):
            best = (junk_value, junk)
        choice = _Choice()
        if best is not None:
            choice.update_targets(best[0], (best[1].ref,))
        return choice.answer("Elite Forces")


# -- §3.11 Engineered Miracle --


@port(_AS + "EngineeredMiracleAgentAbility")
class EngineeredMiracleAgentAbility(DiscardForRewardAgentAbility):
    """``AS.EngineeredMiracleAgentAbility`` (spec §3.11): discard -> 1
    water."""

    def reward(self, p: Profile) -> float:
        return p.water_value(1)


@port(_AS + "EngineeredMiracleCommandAbility")
class EngineeredMiracleCommandAbility(CommandRevealAbility):
    """``AS.EngineeredMiracleCommandAbility`` (spec §3.11): "Command: may
    trash this -> acquire any Imperium Row card". Optional; precedent
    ``TleilaxuMasterAbility`` without its cost cap (the card loss is not
    priced)."""

    always_run_immediately: ClassVar[bool] = False

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def reward(self, p: Profile) -> Summer:
        """The best Row card's ``AcquireValue`` (``MaxByOrElse``: first max)."""

        v = Summer()
        best = _best([p.acquire_value(c).sum for c in _row_cards(p)])
        if best is not None:
            v.add("Engineered Miracle Acquire", best)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        for card in _entities(request, 0, Kind.CARD) or _row_cards(p):
            choice.update_targets(p.acquire_value(card).sum, (card.ref,))
        return choice.answer("Engineered Miracle Command")


# -- §3.12 Fremen War Name, §3.23 Sandwalk --


@port(_AS + "FremenWarNameTroopAbility")
class FremenWarNameTroopAbility(g.DeferredAbility):
    """``AS.FremenWarNameTroopAbility`` (spec §3.12; RebelSupplier shape):
    Agent, Explicit, runs by itself, E 100, Cost spice gained >= 2."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return spice_gained_this_turn(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if gained_spice(p, with_entities, 2):
            v.add("Fremen War Name Troop", p.troop_value(1, False))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Fremen War Name Troop | 100")


class _SpiceGainedDrawAbility(g.DrawAbility):
    """Shared body of the two "draw if you gained 2 spice" draws (not an app
    class; spec §3.12, §3.23). Cost ``HasGainedSpiceThisTurn.AtLeast(2)``
    then ``HasDrawableCard``; V = ``DrawAbility`` V with ``GainedSpice`` in
    place of MeetsCost; E (DeferValue) and CanRunImmediately inherited."""

    def meets_cost(self, p: Profile) -> bool:
        return spice_gained_this_turn(p) >= 2 and g._has_drawable_card(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if gained_spice(p, with_entities, 2):
            v.add("Draw Value", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


@port(_AS + "FremenWarNameDrawAbility")
class FremenWarNameDrawAbility(_SpiceGainedDrawAbility):
    """``AS.FremenWarNameDrawAbility`` (spec §3.12)."""


@port(_AS + "SandwalkDrawAbility")
class SandwalkDrawAbility(_SpiceGainedDrawAbility):
    """``AS.SandwalkDrawAbility`` (spec §3.23, as Fremen War Name's)."""


class _FremenRevealBondAbility(g.BondAbility):
    """Shared body of the Fremen Reveal bonds (not an app class; spec §2.3,
    precedent ``SouthernEldersBondAbility``): Reveal, NoCost, ``V =
    OTHER(Fremen) ? Reward : empty``; P = the inherited FDP."""

    timing: ClassVar[Timing] = Timing.REVEAL
    bond_faction: ClassVar[str | None] = "Fremen"
    LABEL: ClassVar[str] = ""

    def reward(self, p: Profile) -> float:
        raise NotImplementedError

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if _other_of_faction(p, self.owner, "Fremen"):
            v.add(self.LABEL, self.reward(p))
        return v


@port(_AS + "FremenWarNameBondAbility")
class FremenWarNameBondAbility(_FremenRevealBondAbility):
    """``AS.FremenWarNameBondAbility`` (spec §3.12): Fremen Bond: 2 swords."""

    LABEL: ClassVar[str] = "Fremen War Name Strength"

    def reward(self, p: Profile) -> float:
        return p.strength_value(2, False)


@port(_AS + "SandwalkBondAbility")
class SandwalkBondAbility(_FremenRevealBondAbility):
    """``AS.SandwalkBondAbility`` (spec §3.23): Fremen Bond: +1 Persuasion."""

    LABEL: ClassVar[str] = "Sandwalk Persuasion"

    def reward(self, p: Profile) -> float:
        return p.persuasion_value(1)


# -- §3.13 Holy War --


@port(_AS + "HolyWarAgentAbility")
class HolyWarAgentAbility(g.DeferredAbility):
    """``AS.HolyWarAgentAbility`` (spec §3.13, D10): each opponent loses a
    unit, then their Spies on your space move. Agent, Explicit, runs by
    itself, E 100, V empty (opponent harm; Gun Thopter precedent)."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Holy War | 100")


@port(_AS + "HolyWarBondAbility")
class HolyWarBondAbility(RevealCombatIconAbility):
    """``AS.HolyWarBondAbility`` (spec §2.2, §3.13): Fremen Bond: Combat
    icon. Gate = OTHER(Fremen); P = FDP (the inherited P of every app Fremen
    ``BondAbility``; this class is a ``DeployUnitsAbility``)."""

    def gate(self, p: Profile) -> bool:
        return _other_of_faction(p, self.owner, "Fremen")

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        return _fremen_deck_synergy(p, pile, card)


# -- §3.14 I Believe --


@port(_AS + "IBelieveAgentAbility")
class IBelieveAgentAbility(DiscardForRewardAgentAbility):
    """``AS.IBelieveAgentAbility`` (spec §3.14): discard -> draw 1."""

    def reward(self, p: Profile) -> float:
        return _draw_value(p)


@port(_AS + "IBelieveCommandAbility")
class IBelieveCommandAbility(CommandRevealAbility):
    """``AS.IBelieveCommandAbility`` (spec §3.14): Command: recruit 2."""

    def reward(self, p: Profile) -> Summer:
        v = Summer()
        v.add("I Believe Command Troops", p.troop_value(2, False))
        return v


# -- §3.15 Imperial Throneship, §3.22 Quash Rebellion, §3.23 Sandwalk reveals --


@port(_AS + "ImperialThroneshipRevealAbility")
class ImperialThroneshipRevealAbility(g.RevealAbility):
    """``AS.ImperialThroneshipRevealAbility`` (spec §2.6, §3.15): the reveal
    box; previews +1 Persuasion while 4+ units are garrisoned (troops and
    Commanders, ``minimum_garrisoned_units``)."""

    def reveal_preview_persuasion(self, p: Profile) -> int:
        bonus = 1 if _garrison_units(p.ctx.me) >= 4 else 0
        return self.owner.int_attr("Persuasion") + bonus


@port(_AS + "ImperialThroneshipTriggeredAbility")
class ImperialThroneshipTriggeredAbility(g.TriggeredAbility):
    """``AS.ImperialThroneshipTriggeredAbility`` (spec §2.6, §3.15;
    ``BeneGesseritOperativeTriggeredAbility`` precedent): Reveal; 4+
    garrisoned units -> +1 Persuasion, 3 Solari."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if _garrison_units(p.ctx.me) >= 4:
            v.add("Imperial Throneship Persuasion", p.persuasion_value(1))
            v.add("Imperial Throneship Solari", p.solari_value(3))
        return v


@port(_AS + "QuashRebellionRevealAbility")
class QuashRebellionRevealAbility(g.RevealAbility):
    """``AS.QuashRebellionRevealAbility`` (spec §2.6, §3.22): previews +2
    Persuasion while a Commander is in the Conflict."""

    def reveal_preview_persuasion(self, p: Profile) -> int:
        bonus = 2 if p.ctx.me.commanders_conflict >= 1 else 0
        return self.owner.int_attr("Persuasion") + bonus


@port(_AS + "QuashRebellionTriggeredAbility")
class QuashRebellionTriggeredAbility(g.TriggeredAbility):
    """``AS.QuashRebellionTriggeredAbility`` (spec §2.6, §3.22): Reveal; a
    Commander in the Conflict -> +2 Persuasion."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if p.ctx.me.commanders_conflict >= 1:
            v.add("Quash Rebellion Persuasion", p.persuasion_value(2))
        return v


@port(_AS + "SandwalkRevealAbility")
class SandwalkRevealAbility(g.RevealAbility):
    """``AS.SandwalkRevealAbility`` (spec §2.3, §3.23): previews the Fremen
    Bond's +1 Persuasion while OTHER(Fremen)."""

    def reveal_preview_persuasion(self, p: Profile) -> int:
        bonus = 1 if _other_of_faction(p, self.owner, "Fremen") else 0
        return self.owner.int_attr("Persuasion") + bonus


#: The app-style ``GetRevealPreviewValue`` overrides (spec §2.3, §2.6,
#: OPEN-6; plan §11.7). The shape follows the two app bodies read in the
#: disassembly: ``BeneGesseritOperativeRevealAbility::GetRevealPreviewValue
#: @0x4c042e0`` = ``{"Persuasion": Owner.Persuasion + 2 * cond}`` and
#: ``SouthernEldersRevealAbility::GetRevealPreviewValue @0x4c4ff90`` =
#: ``{"Persuasion": 2 * OTHER(Fremen)}`` (the card prints no Persuasion):
#: the printed Persuasion plus the conditional bonus while the condition
#: holds now.
APPSTYLE_PREVIEW_REVEALS: Final = frozenset(
    {
        _AS + "ImperialThroneshipRevealAbility",
        _AS + "QuashRebellionRevealAbility",
        _AS + "SandwalkRevealAbility",
    }
)


def reveal_preview_persuasion(ability_class: str, card: Entity, p: Profile) -> int:
    """``GetRevealPreviewValue(M, P)["Persuasion"]`` of an app-style reveal
    box (``profile/economy.py`` ``_reveal_preview_value`` dispatches here for
    ``APPSTYLE_PREVIEW_REVEALS``)."""

    ability = ability_for(ability_class, card)
    preview = getattr(ability, "reveal_preview_persuasion", None)
    if callable(preview):
        return int(preview(p))
    return card.int_attr("Persuasion")


# -- §3.16 Intelligence Training --


@port(_AS + "IntelligenceTrainingCommandAbility")
class IntelligenceTrainingCommandAbility(g.PlaceSpyRevealAbility):
    """``AS.IntelligenceTrainingCommandAbility`` (spec §3.16): "Command:
    place a Spy"; V gated by ``CommandReached``; E inherited (SpyValue)."""

    def meets_cost(self, p: Profile) -> bool:
        return command_reached(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if command_reached(p):
            return super().value_for_player(p, with_entities)
        return Summer()


# -- §3.17 Ixian Ambassador --


@port(_AS + "IxianAmbassadorRevealAbility")
class IxianAmbassadorRevealAbility(g.GainAnyInfluenceRevealAbility):
    """``AS.IxianAmbassadorRevealAbility`` (spec §3.17): with 2+ Tech tiles,
    +1 Influence of choice. V gated the Rebel Supplier way; E inherited
    (+100 per track)."""

    def meets_cost(self, p: Profile) -> bool:
        return _tech_tile_count(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if _tech_tile_count(p) >= 2:
            return super().value_for_player(p, with_entities)
        return Summer()


# -- §3.18 Litany Against Fear --


@port(_AS + "LitanyTurnStartAbility")
class LitanyTurnStartAbility(g.DeferredAbility):
    """``AS.LitanyTurnStartAbility`` (spec §3.18, D11): "turn start: play
    this -> draw 1 and pass". Timing None; offered only in the ``turn``
    window (``play_turn_start_card``), competing with the placements."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CardDrawValueWithBuyGains + CardPlayValueRevealPenalty x the
        card's reveal value`` (the card leaves the hand unrevealed:
        ``AgentAbility`` V term (f)); the pass itself has no app value."""

        s = Summer()
        s.add("Litany Draw", p.card_draw_value_with_buy_gains())
        rv = g.value_for_reveal_abilities(self.owner, p)
        s.add("Reveal Penalty", p.C.CardPlayValueRevealPenalty * rv.sum)
        return Answer(s.sum, (), "Litany Against Fear")


# -- §3.19 Mercantile Affairs --


@port(_AS + "MercantileAffairsAgentAbility")
class MercantileAffairsAgentAbility(g.DeferredAbility):
    """``AS.MercantileAffairsAgentAbility`` (spec §3.19, D6;
    ``ImperialSpymasterAbility`` shape): an Intrigue if you completed a
    contract this turn. Agent, Explicit, E 100."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.contracts_completed_turn > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """Completed this turn, or an own face-up contract completes at the
        candidate space (its ``ContractAbility.ValueForPlayer(P, [S]) > 0``,
        the Smuggler's Harvester / SpaceAbility contract-term test)."""

        v = Summer()
        due = p.ctx.me.contracts_completed_turn > 0
        space = g.collect_first(with_entities, Kind.SPACE)
        if not due and space is not None:
            for contract in _own_active_contracts(p):
                ability = g._first_contract_ability(contract)
                if (
                    ability is not None
                    and ability.value_for_player(p, (space,)).sum > 0
                ):
                    due = True
                    break
        if due:
            v.add("Mercantile Affairs Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Mercantile Affairs | 100")


# -- §3.20 Pointing the Way --


@port(_AS + "PointingTheWayAgentAbility")
class PointingTheWayAgentAbility(g.DeferredAbility):
    """``AS.PointingTheWayAgentAbility`` (spec §3.20; ImperialSpymaster
    shape): an Intrigue with a sandworm in the Conflict (Cost
    ``HasUnitsDeployed<WormSandworm>.Any``, as Leadership)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.sandworms_conflict > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        if p.ctx.me.sandworms_conflict > 0:
            v.add("Pointing the Way Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Pointing the Way | 100")


@port(_AS + "PointingTheWayCommandAbility")
class PointingTheWayCommandAbility(g.GainAnyInfluenceRevealAbility):
    """``AS.PointingTheWayCommandAbility`` (spec §3.20): Command: +1
    Influence of choice; V gated by ``CommandReached``; E inherited."""

    def meets_cost(self, p: Profile) -> bool:
        return command_reached(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if command_reached(p):
            return super().value_for_player(p, with_entities)
        return Summer()


# -- §3.21 Possible Futures, §3.26 Southern Faith --


def _best_track(p: Profile, tracks: Sequence[Entity]) -> tuple[Entity | None, float]:
    """The first strict best of ``GetGainInfluenceValue(t, 1)`` over
    ``tracks`` (all four tracks when none are given)."""

    candidates = list(tracks) or [track_entity(f) for f in FACTIONS]
    best: Entity | None = None
    best_value = 0.0
    for track in candidates:
        value = p.gain_influence_value(track.ref, 1, -1, False).sum
        if best is None or value > best_value:
            best, best_value = track, value
    return best, best_value


@port(_AS + "PossibleFuturesAgentAbility")
class PossibleFuturesAgentAbility(g.DeferredAbility):
    """``AS.PossibleFuturesAgentAbility`` (spec §3.21, D15, D34): +1
    Influence of choice OR recruit 2; both with a Bene Gesserit Bond
    (INPLAY(BG), judged at play like In High Places, OQ-028 (a))."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _bond(self, p: Profile) -> bool:
        return _in_play_other_of_faction(p, self.owner, "BeneGesserit")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """Bond: influence + troops; else the better of the two."""

        v = Summer()
        influence = g.gain_any_influence_value(p, 1).sum
        troops = p.troop_value(2, False)
        if self._bond(p):
            v.add("Possible Futures Influence", influence)
            v.add("Possible Futures Troops", troops)
        else:
            v.add("Possible Futures", _dmax(influence, troops))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Bond: both (option 2) at 100 with the best track; else influence
        (option 0, stored first) and two troops (option 1, strictly greater
        only). Plain values, no +100 (D15)."""

        choice = _Choice()
        track, influence = _best_track(p, _entities(request, 0, Kind.TRACK))
        if track is None:
            return choice.answer("Possible Futures | no track")
        if self._bond(p):
            choice.update_responses(100.0, ((2,), (track.ref,)))
            return choice.answer("Possible Futures | both")
        choice.update_responses(influence, ((0,), (track.ref,)))
        choice.update_responses(p.troop_value(2, False), ((1,),))
        return choice.answer("Possible Futures")

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """BGP with ``X = 0.75 x min(influence, troops)``: the bond's extra
        (D34; the 0.75 literal of ``BeneGesseritDrawAbility``)."""

        def played() -> float:
            influence = g.gain_any_influence_value(p, 1).sum
            troops = p.troop_value(2, False)
            return 0.75 * min(influence, troops)

        return g.bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")


@port(_AS + "SouthernFaithAgentAbility")
class SouthernFaithAgentAbility(g.DeferredAbility):
    """``AS.SouthernFaithAgentAbility`` (spec §3.26, D15, D34): draw 1 OR
    (Bene Gesserit Bond) +1 Bene Gesserit Influence."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _bond(self, p: Profile) -> bool:
        return _in_play_other_of_faction(p, self.owner, "BeneGesserit")

    def _draw(self, p: Profile) -> float:
        return _draw_value(p) if g._has_drawable_card(p) else 0.0

    def _influence(self, p: Profile) -> float:
        return p.gain_influence_value("bene_gesserit", 1, -1, False).sum

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        v = Summer()
        draw = self._draw(p)
        if self._bond(p):
            v.add("Southern Faith", _dmax(draw, self._influence(p)))
        else:
            v.add("Southern Faith Draw", draw)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Draw (option 0) stored first; with the Bond, influence (option 1)
        replaces it only when strictly greater."""

        choice = _Choice()
        choice.update_responses(self._draw(p), ((0,),))
        if self._bond(p):
            choice.update_responses(self._influence(p), ((1,),))
        return choice.answer("Southern Faith")

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """BGP with ``X = 0.75 x max(0, influence - draw)`` (D34)."""

        def played() -> float:
            return 0.75 * max(0.0, self._influence(p) - self._draw(p))

        return g.bg_played_pile_value(p, pile, card, played, "Bene Gesserit Played")


@port(_AS + "SouthernFaithCommandAbility")
class SouthernFaithCommandAbility(CommandRevealAbility):
    """``AS.SouthernFaithCommandAbility`` (spec §3.26): Command: 2 spice."""

    def reward(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Southern Faith Command Spice", p.spice_value(2))
        return v


# -- §3.24 Sardaukar Standard --


@port(_AS + "SardaukarStandardTrashAbility")
class SardaukarStandardTrashAbility(g.TriggeredAbility):
    """``AS.SardaukarStandardTrashAbility`` (spec §3.24): "when trashed:
    acquire the bank Commander (+ Skill)". No AI hook
    (``SardaukarSoldierAbility`` precedent); the ``skill_choice`` it opens
    belongs to bloodlines-systems.md."""


# -- §3.25 Shrouded Counsel --


@port(_AS + "ShroudedCounselCommandAbility")
class ShroudedCounselCommandAbility(g.TrashAbility):
    """``AS.ShroudedCounselCommandAbility`` (spec §3.25): "Command: may trash
    a card". Reveal, Optional; V gated by ``CommandReached``; E =
    ``TrashAbility.Evaluate`` (no junk card -> "used, trash nothing" maps to
    declining)."""

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        return command_reached(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        if command_reached(p):
            return super().value_for_player(p, with_entities)
        return Summer()


# -- §3.27 Urgent Shigawire --


@port(_AS + "UrgentShigawireAgentAbility")
class UrgentShigawireAgentAbility(g.DeferredAbility):
    """``AS.UrgentShigawireAgentAbility`` (spec §3.27, D12 as revised by plan
    §11.7): the next Bene Gesserit card played this round has every Agent
    icon and draws 1. Agent, Explicit, runs by itself, E 100."""

    timing: ClassVar[Timing] = Timing.AGENT
    always_run_immediately: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.EXPLICIT

    def _bene_gesserit_hand(self, p: Profile) -> list[Entity]:
        return [
            c
            for c in _hand(p)
            if c.ref != self.owner.ref and _has_faction(c, "BeneGesserit")
        ]

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """With another Bene Gesserit hand card and 2+ Agents left: ``0.75 x
        draw`` (``BeneGesseritDrawAbility`` P, D12) plus, plan §11.7, ``0.75
        x UnlockValue`` of the best Bene Gesserit hand card under every
        Agent icon (floored at 0: an unused grant costs nothing)."""

        v = Summer()
        bene_gesserit = self._bene_gesserit_hand(p)
        if not bene_gesserit or p.ctx.me.agents_available < 2:
            return v
        v.add("Urgent Shigawire Draw", 0.75 * _draw_value(p))
        unlock = unlock_value(p, grant_bene_gesserit_boost, bene_gesserit)
        v.add("Urgent Shigawire Icons", 0.75 * max(0.0, unlock))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), "Urgent Shigawire | 100")


# ===========================================================================
# §4 Intrigue cards
# ===========================================================================


def _short_of(p: Profile, space_id: str) -> bool:
    """1 or 2 Solari short of an open space (Contingency Plan's unsigned
    range test)."""

    shortfall = p.ctx.me.resources.solari - _space_cost(p, space_id)
    return shortfall in (-2, -1) and _open_to(p, space_id)


def _contingency_plan_short(p: Profile) -> bool:
    """``ContingencyPlanPlotAbility::Evaluate``'s 100 branches (intrigues.md
    §7.5): at T0 with an Agent left and no Swordmaster, 1-2 Solari short of
    the Swordmaster, or (round <= 5, no seat) of the High Council."""

    me = p.ctx.me
    if me.swordmaster_acquired:
        return False
    if not (_in_player_turn(p, _UNDETERMINED) and me.agents_available > 0):
        return False
    if _short_of(p, _SWORDMASTER):
        return True
    return (
        p.ctx.round_number <= 5 and not me.high_council and _short_of(p, _HIGH_COUNCIL)
    )


@port(_AS + "AdaptiveTacticsAbility")
class AdaptiveTacticsAbility(IntrigueAbility):
    """``AS.AdaptiveTacticsAbility`` (spec §4.1, D16): pay 1 spice ->
    recruit 1 + Combat icon. ``MercenariesAbility`` without its deploy-window
    gate (the card brings its own icon); the spice is not priced."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.spice >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Mercenaries (D31): ``CurrentRound < 3``."""

        return p.ctx.round_number < 3

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if p.ctx.me.troops_supply <= 0:  # Mercenaries' b__12_0
            return choice.answer("Adaptive Tactics")
        if p.is_final_round() and _in_player_turn(p, _REVEAL_TURN):
            v = 100
        else:
            v = p.should_play_troop_intrigue("Adaptive Tactics", 6, 4, 1)
        if v > 0:
            choice.update_responses(float(v), ())
        return choice.answer("Adaptive Tactics")


@port(_AS + "BattlefieldResearchCombatAbility")
class BattlefieldResearchCombatAbility(StrengthIntrigueAbility):
    """``AS.BattlefieldResearchCombatAbility`` (spec §4.1, D18): retreat one
    or two troops -> Acquire Tech (1 spice off). Strength-less; Go to Ground
    shape with the reward's app price ``BuyTechValue(1, false)``."""

    def meets_cost(self, p: Profile) -> bool:
        return _conflict_troops(p.ctx.me) >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Reach Agreement: ``IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        s = p.should_play_retreat_intrigue("Battlefield Research", 2, 6, 2)
        n = p.troops_to_retreat(2)
        tech = p.buy_tech_value(1, False)
        if s > 0 and n > 0 and tech > 0:
            troops = _options(request, 0) or _unit_indices(_conflict_troops(p.ctx.me))
            choice.update_responses(tech, (tuple(troops[:n]),))
        return choice.answer("Battlefield Research")


def _endgame_vp_junk(p: Profile, have: int, need: int) -> bool:
    """D32: an Endgame VP half's junk test at CHOAM Profits' distance from
    its threshold: 3+ short -> true, 2 short -> ``IsClimax``, else false."""

    short = need - have
    if short >= 3:
        return True
    if short == 2:
        return p.is_climax()
    return False


@port(_AS + "BattlefieldResearchEndgameAbility")
class BattlefieldResearchEndgameAbility(_EndgameIntrigueAbility):
    """``AS.BattlefieldResearchEndgameAbility`` (spec §4.1): 3+ Tech tiles ->
    1 VP; automatic at the Endgame."""

    def meets_cost(self, p: Profile) -> bool:
        return _tech_tile_count(p) >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        return _endgame_vp_junk(p, _tech_tile_count(p), 3)


@port(_AS + "CoerciveNegotiationAbility")
class CoerciveNegotiationAbility(IntrigueAbility):
    """``AS.CoerciveNegotiationAbility`` (spec §4.1): with 3+ units deployed
    this turn, reveal three contracts and take one. Distraction's gate plus
    the generic contract price (the tokens are hidden until play)."""

    def meets_cost(self, p: Profile) -> bool:
        me = p.ctx.me
        return max(me.units_deployed_turn, me.units_deployed_peak) >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Leverage: ``IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        choice.update_responses(p.gain_contract_value().sum, ())
        return choice.answer("Coercive Negotiation")


@port(_AS + "DesertSupportAbility")
class DesertSupportAbility(StrengthIntrigueAbility):
    """``AS.DesertSupportAbility`` (spec §4.1): pay 1 water -> 5 swords;
    base E (``StrengthValue`` 5 when the water is held; the water is not
    priced, Spice Is Power)."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.water >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Unexpected Allies (D31): ``Water == 0``."""

        return p.ctx.me.resources.water == 0


@port(_AS + "EmperorsInvitationAbility")
class EmperorsInvitationAbility(IntrigueAbility):
    """``AS.EmperorsInvitationAbility`` (spec §4.1, D13): draw 1 OR the
    played card has the Emperor icon."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if (
            _option_open(request, 1)
            and _in_player_turn(p, _UNDETERMINED)
            and unlock_value(p, grant_emperor_icon) > 0
        ):
            choice.update_responses(100.0, ((1,),))
        elif _option_open(request, 0) and draw_plot_gate(p):
            choice.update_responses(_draw_value(p), ((0,),))
        return choice.answer("Emperor's Invitation")


@port(_AS + "FalseOrdersAbility")
class FalseOrdersAbility(IntrigueAbility):
    """``AS.FalseOrdersAbility`` (spec §4.1): opponents' Spies on your turn
    space move and you place a Spy (Distraction shape; moving opponents'
    Spies is harm, valued 0)."""

    def meets_cost(self, p: Profile) -> bool:
        """An Agent sent this turn (the engine's own-frame read)."""

        return agent_turn_space_id(p.ctx.state, p.ctx.seat) is not None

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Distraction: ``SpyDeployedCount >= 2``."""

        return _deployed_spies(p) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if _deployed_spies(p) > 2:
            return choice.answer("False Orders")
        choice.update_responses(p.spy_value().sum, ())
        return choice.answer("False Orders")


@port(_AS + "GraspArrakisCombatAbility")
class GraspArrakisCombatAbility(StrengthIntrigueAbility):
    """``AS.GraspArrakisCombatAbility`` (spec §4.1): 3 swords; base E."""


@port(_AS + "GraspArrakisEndgameAbility")
class GraspArrakisEndgameAbility(_EndgameIntrigueAbility):
    """``AS.GraspArrakisEndgameAbility`` (spec §4.1, D17): flip two face-up
    Conflict cards -> 1 VP; automatic after ``ScoreBattleIconsPairs``
    (the flips: ``grasp_arrakis_flip_pick``)."""

    def meets_cost(self, p: Profile) -> bool:
        """Two face-up Conflict cards (Objectives count, OQ-005)."""

        return len(face_up_conflict_card_ids(p.ctx.me)) >= 2


def _honor_guard_recruit_passes(p: Profile) -> bool:
    """OPEN-2: Honor Guard's discount makes a Commander recruit pass the
    bloodlines-systems.md §2.2 rule this turn when it fails now: the
    profile's ``RecruitNet`` (§1.2: ``CommanderUnitValue − solari_value(
    cost)`` plus Plasteel Blades' extra Skill, plan §11.7) is not > 0 at the
    current cost and is > 0 at the cost one lower."""

    me = p.ctx.me
    if not p.ctx.config.bloodlines:
        return False
    if me.commanders_supply <= 0 or me.commander_recruited_turn:
        return False
    cost = commander_cost(me)
    discounted = max(0, cost - 1)
    if me.resources.solari < discounted:
        return False
    return not p.recruit_net(cost) > 0 and p.recruit_net(discounted) > 0


@port(_AS + "HonorGuardAbility")
class HonorGuardAbility(IntrigueAbility):
    """``AS.HonorGuardAbility`` (spec §4.1; Shaddam's Favor shape): recruit 1
    and a Commander costs 1 less this turn."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Call to Arms (D31): ``GarrisonTroops >= 6`` (Commanders count,
        bloodlines-systems.md §1.1)."""

        return _garrison_units(p.ctx.me) >= 6

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        me = p.ctx.me
        play = me.troops_supply > 0 and (
            _intrigue_hand_count(p) > 3
            or p.is_final_round()
            or (
                _deploy_window(p)
                and p.current_conflict_interest().sum > p.conflict_posture_bounds()[1]
            )
        )
        if play or _honor_guard_recruit_passes(p):
            choice.update_responses(100.0, ())
        return choice.answer("Honor Guard")


@port(_AS + "InsiderInformationAbility")
class InsiderInformationAbility(IntrigueAbility):
    """``AS.InsiderInformationAbility`` (spec §4.1, D13): recall a Spy ->
    trash a card and draw 1, OR ignore Influence requirements this turn."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if (
            _option_open(request, 1)
            and _in_player_turn(p, _UNDETERMINED)
            and unlock_value(p, grant_ignore_requirements) > 0
        ):
            choice.update_responses(100.0, ((1,),))
            return choice.answer("Insider Information | requirements")
        if not _option_open(request, 0) or _deployed_spies(p) <= 0:
            return choice.answer("Insider Information")
        spy, _ = p.recall_spy(_entities(request, 1, Kind.SPY) or _own_spies(p))
        if spy is None:
            return choice.answer("Insider Information | no spy")
        s = Summer()
        s.add("Recall Spy", p.recall_spy_value().sum)
        s.add("Draw 1 card with Buy Gains", p.card_draw_value_with_buy_gains())
        trash = _entities(request, 2, Kind.CARD) or _trash_targets(p)
        junk, junk_value = p.card_to_trash(trash, 1.0)
        junk_item: tuple[str, ...] = ()
        if junk is not None:
            s.add("Trash Value", junk_value)
            junk_item = (junk.ref,)
        if s.sum > 0:
            choice.update_responses(s.sum, ((0,), (spy.ref,), junk_item))
        return choice.answer("Insider Information | recall")


@port(_AS + "RapidEngineeringAbility")
class RapidEngineeringAbility(IntrigueAbility):
    """``AS.RapidEngineeringAbility`` (spec §4.1, D18, D33): discard a card ->
    Acquire Tech (1 spice off), OR with 3+ tiles +1 Influence in two
    factions."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Sietch Ritual (nothing doable): no affordable tile at discount 1
        and fewer than 3 tiles."""

        return p.tech_tile_to_acquire(1, False) is None and _tech_tile_count(p) < 3

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if _option_open(request, 0) and p.tech_tile_to_acquire(1, False) is not None:
            hand = _entities(request, 1, Kind.CARD) or _hand(p)
            order = p.discard_order(hand, False)
            if order:
                s = Summer()
                s.add("Discard", p.discard_value())
                s.add("Buy Tech", p.buy_tech_value(1, False))
                if s.sum > 0:
                    choice.update_responses(s.sum, ((0,), (order[0].ref,)))
        if _option_open(request, 1) and _tech_tile_count(p) >= 3:
            tracks = list(_entities(request, 2, Kind.TRACK)) or [
                track_entity(f) for f in FACTIONS
            ]
            p.rng.shuffle(tracks)  # GainAnyTwoInfluenceConflictAbility E
            scored = [
                (p.gain_influence_value(t.ref, 1, -1, False).sum, t) for t in tracks
            ]
            top = sorted(scored, key=lambda item: item[0], reverse=True)[:2]
            total = 0.0
            for value, _ in top:
                total += value
            vb = _dmax(0.5, total)
            if vb > 0 and len(top) == 2:
                choice.update_responses(vb, ((1,), tuple(t.ref for _, t in top)))
        return choice.answer("Rapid Engineering")


@port(_AS + "ReturnTheFavorAbility")
class ReturnTheFavorAbility(StrengthIntrigueAbility):
    """``AS.ReturnTheFavorAbility`` (spec §4.1): 1 sword + 1 per faction
    with 2+ Influence; base E."""

    def strength_value(self, p: Profile) -> int:
        """The ``WeirdingCombatAbility`` override shape (no MeetsCost)."""

        influence = p.ctx.me.influence
        return 1 + sum(1 for f in FACTIONS if int(getattr(influence, f)) >= 2)


@port(_AS + "RipplesInTheSandAbility")
class RipplesInTheSandAbility(StrengthIntrigueAbility):
    """``AS.RipplesInTheSandAbility`` (spec §4.1): 3 swords; an Intrigue with
    a sandworm in the Conflict (Devour shape, no gate)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Devour: ``!HasMakerHooks && IsClimax``."""

        return not p.ctx.me.maker_hooks and p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        v = self._strength_choice(p).value
        if p.ctx.me.sandworms_conflict > 0:
            v += p.intrigue_value()
        choice.update_responses(v, ())
        return choice.answer("Ripples in the Sand")


@port(_AS + "SacredPoolsPlotAbility")
class SacredPoolsPlotAbility(IntrigueAbility):
    """``AS.SacredPoolsPlotAbility`` (spec §4.1, D29): discard a card -> 1
    water. Held while ``Water >= 3`` (the Endgame VP; Crysknife "keep");
    otherwise the Sietch Ritual shape."""

    def meets_cost(self, p: Profile) -> bool:
        return len(p.ctx.hand) >= 1

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if p.ctx.me.resources.water >= 3:
            return choice.answer("Sacred Pools | keep")
        order = p.discard_order(_entities(request, 0, Kind.CARD) or _hand(p), False)
        if not order:
            return choice.answer("Sacred Pools")
        v = Summer()
        v.add("Water", p.water_value(1))
        if _intrigue_hand_count(p) > 3 or p.is_climax():
            v.add("Four Intrigue or Climax", 10.0)
        if v.sum >= 3.0:
            choice.update_responses(v.sum, ((order[0].ref,),))
        return choice.answer("Sacred Pools")


@port(_AS + "SacredPoolsEndgameAbility")
class SacredPoolsEndgameAbility(_EndgameIntrigueAbility):
    """``AS.SacredPoolsEndgameAbility`` (spec §4.1, D32): 3+ water -> 1 VP;
    automatic at the Endgame."""

    def meets_cost(self, p: Profile) -> bool:
        return p.ctx.me.resources.water >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        return _endgame_vp_junk(p, p.ctx.me.resources.water, 3)


@port(_AS + "SeizeProductionAbility")
class SeizeProductionAbility(IntrigueAbility):
    """``AS.SeizeProductionAbility`` (spec §4.1, D30): 2 Solari OR (a
    Commander in the Conflict) 2 spice."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if _option_open(request, 0) and _contingency_plan_short(p):
            choice.update_responses(100.0, ((0,),))
            return choice.answer("Seize Production | short")
        me = p.ctx.me
        if not (
            p.is_final_round()
            or _intrigue_hand_count(p) > 3
            or (_in_player_turn(p, _UNDETERMINED) and me.agents_available > 0)
        ):
            return choice.answer("Seize Production")
        if _option_open(request, 0):
            choice.update_responses(p.solari_value(2), ((0,),))
        if _option_open(request, 1) and me.commanders_conflict >= 1:
            choice.update_responses(p.spice_value(2), ((1,),))
        return choice.answer("Seize Production")


@port(_AS + "SleeperUnitAbility")
class SleeperUnitAbility(IntrigueAbility):
    """``AS.SleeperUnitAbility`` (spec §4.1): pay 1 Solari -> a Spy, OR
    recall a Spy -> recruit 2 (Special Mission shape)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        me = p.ctx.me
        can_place = (
            _option_open(request, 0)
            and me.resources.solari >= 1
            and (me.spies_supply > 0 or _deployed_spies(p) > 0)
        )
        spy_value = p.spy_value().sum
        if can_place and spy_value > p.solari_value(1):
            choice.update_responses(spy_value, ((0,),))
            return choice.answer("Sleeper Unit | place")
        if not _option_open(request, 1) or _deployed_spies(p) <= 0:
            return choice.answer("Sleeper Unit")
        spy, _ = p.recall_spy(_entities(request, 1, Kind.SPY) or _own_spies(p))
        if spy is None:
            return choice.answer("Sleeper Unit | no spy")
        s = Summer()
        s.add("Recall Spy", p.recall_spy_value().sum)
        s.add("2 Troops", p.troop_value(2, False))
        if s.sum > 0:
            choice.update_responses(s.sum, ((1,), (spy.ref,)))
        return choice.answer("Sleeper Unit | recall")


@port(_AS + "TenuousBondPlotAbility")
class TenuousBondPlotAbility(IntrigueAbility):
    """``AS.TenuousBondPlotAbility`` (spec §4.1): lose 1 Influence -> gain 1
    Influence (the swap branch of Change Allegiances; the gain track is
    ``intrigue.choose_faction_influence``)."""

    def meets_cost(self, p: Profile) -> bool:
        influence = p.ctx.me.influence
        return any(int(getattr(influence, f)) >= 1 for f in FACTIONS)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        tracks = _entities(request, 0, Kind.TRACK) or [
            track_entity(f)
            for f in FACTIONS
            if int(getattr(p.ctx.me.influence, f)) >= 1
        ]
        if not tracks:
            return choice.answer("Tenuous Bond")
        lose, _gain, x = p.best_influence_exchange(
            -1, 1, [t.ref for t in tracks], list(FACTIONS)
        )
        lose_ref = next((t.ref for t in tracks if t.ref == lose), None)
        if lose_ref is not None and x >= 2.0:
            choice.update_responses(x, ((lose_ref,),))
        return choice.answer("Tenuous Bond")


@port(_AS + "TenuousBondCombatAbility")
class TenuousBondCombatAbility(StrengthIntrigueAbility):
    """``AS.TenuousBondCombatAbility`` (spec §4.1): trash a discard-pile card
    costing 1+ -> 4 swords; base E (the trashed card:
    ``tenuous_bond_trash_pick``)."""

    def meets_cost(self, p: Profile) -> bool:
        return any(
            card_entity(i).int_attr("PersuasionCost") >= 1
            for i in p.ctx.me.discard_pile
        )


@port(_AS + "TheStrongSurviveAbility")
class TheStrongSurviveAbility(StrengthIntrigueAbility):
    """``AS.TheStrongSurviveAbility`` (spec §4.1): 3 swords OR retreat one
    troop -> trash a card (Tactical Option shape)."""

    def combat_value(self, p: Profile) -> float:
        """``CombatValue = StrengthValue`` (Tactical Option override)."""

        return float(self.strength_value(p))

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """The strength option at the base value (option 0); the retreat
        option at 150 under Tactical Option's conditions (not close, not
        climax, lead >= 10) and ``GetTroopsToRetreat(1) > 0``."""

        choice = _Choice()
        v = self._strength_choice(p).value
        choice.update_responses(v, ((0,),))
        current = p.ctx.me.combat_strength
        opponents = [o.combat_strength for o in p.ctx.opponents]
        next_below = max((s for s in opponents if current >= s), default=0)
        close = any(s - current >= 0 and s - current < 2 for s in opponents)
        climax = p.is_climax()
        if close or climax or current - next_below < 10:
            return choice.answer("The Strong Survive | strength")
        units = _options(request, 1) or _unit_indices(_conflict_troops(p.ctx.me))
        if p.troops_to_retreat(1) <= 0:
            return choice.answer("The Strong Survive | strength")
        choice.update_responses(150.0, ((1,), tuple(units[:1])))
        return choice.answer("The Strong Survive | retreat")


@port(_AS + "WithdrawalAgreementAbility")
class WithdrawalAgreementAbility(StrengthIntrigueAbility):
    """``AS.WithdrawalAgreementAbility`` (spec §4.1, D26): retreat three
    troops -> +1 Influence of choice. Strength-less; retreat test ``(6, 10,
    3)`` (Spice Is Power's retreat-3), value = the reward (Go to Ground)."""

    def meets_cost(self, p: Profile) -> bool:
        return _conflict_troops(p.ctx.me) >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Reach Agreement (D31): ``IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        s = p.should_play_retreat_intrigue("Withdrawal Agreement", 6, 10, 3)
        if s > 0 and p.ctx.me.units_in_conflict >= 3:
            v = g.gain_any_influence_value(p, 1).sum
            if v > 0:
                units = _options(request, 0) or _unit_indices(
                    _conflict_troops(p.ctx.me)
                )
                choice.update_responses(v, (tuple(units[:3]),))
        return choice.answer("Withdrawal Agreement")


# ===========================================================================
# §5 Twisted Intrigue
# ===========================================================================


@port(_AS + "TwistedAmbitiousAbility")
class TwistedAmbitiousAbility(IntrigueAbility):
    """``AS.TwistedAmbitiousAbility`` (spec §5): lose 3 troops -> +1
    Influence where an opponent leads (Tleilaxu Surgeon's troop cost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Nothing doable: fewer than 3 units, or no faction to gain."""

        return _troop_units(p.ctx.me) < 3 or not factions_where_opponent_leads(
            p.ctx.state, p.ctx.seat
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        tracks = _entities(request, 0, Kind.TRACK) or [
            track_entity(f.value)
            for f in factions_where_opponent_leads(p.ctx.state, p.ctx.seat)
        ]
        track, influence = _best_track(p, tracks) if tracks else (None, 0.0)
        if track is None:
            return choice.answer("Twisted Ambitious")
        s = Summer()
        s.add("Gain Influence", influence)
        s.add("Troop Cost", p.troop_value(-3, False))
        if s.sum > 0:
            choice.update_responses(s.sum, ((track.ref,),))
        return choice.answer("Twisted Ambitious")


@port(_AS + "TwistedCalculatingAbility")
class TwistedCalculatingAbility(IntrigueAbility):
    """``AS.TwistedCalculatingAbility`` (spec §5, D19): 1 Solari per unit type
    in the Conflict, under the Crysknife gate with the Reveal turn in place of
    its T0 spice clause."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        me = p.ctx.me
        k = sum(
            (
                me.troops_conflict > 0,
                me.sandworms_conflict > 0,
                me.commanders_conflict > 0,
                me.agent_in_conflict > 0,
            )
        )
        gate = (
            p.is_final_round()
            or _intrigue_hand_count(p) > 3
            or _in_player_turn(p, _REVEAL_TURN)
        )
        if gate and k >= 1:
            choice.update_responses(p.solari_value(k), ())
        return choice.answer("Twisted Calculating")


@port(_AS + "TwistedControlledPlotAbility")
class TwistedControlledPlotAbility(IntrigueAbility):
    """``AS.TwistedControlledPlotAbility`` (spec §5, D20): look at the top
    card; the play is valued at the expected draw-for-1-Solari (the top
    card is hidden before the peek); after it ``controlled_peek_choice``."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if draw_plot_gate(p):
            s = Summer()
            s.add("Draw", _draw_value(p))
            s.add("Solari Cost", p.solari_value(-1))
            choice.update_responses(s.sum, ())
        return choice.answer("Twisted Controlled")


@port(_AS + "TwistedControlledCombatAbility")
class TwistedControlledCombatAbility(StrengthIntrigueAbility):
    """``AS.TwistedControlledCombatAbility`` (spec §5): 1 sword; base E."""


@port(_AS + "TwistedDeviousAbility")
class TwistedDeviousAbility(IntrigueAbility):
    """``AS.TwistedDeviousAbility`` (spec §5): trash a hand card (mandatory)
    OR deploy up to 2 garrison troops."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """Option 0 only for a junk card (``GetCardToTrash(hand, 1.0)``);
        option 1 at 100 with ``min(2, IntrigueDeployTroops)`` troops,
        replacing option 0 when strictly greater."""

        choice = _Choice()
        if _option_open(request, 0):
            hand = _entities(request, 1, Kind.CARD) or _hand(p)
            card, value = p.card_to_trash(hand, 1.0)
            if card is not None:
                choice.update_responses(value, ((0,), (card.ref,)))
        if _option_open(request, 1):
            garrison = _options(request, 2) or _unit_indices(p.ctx.me.troops_garrison)
            n = min(2, intrigue_deploy_troops(p, garrison))
            if n > 0:
                choice.update_responses(100.0, ((1,), tuple(garrison[:n])))
        return choice.answer("Twisted Devious")


@port(_AS + "TwistedDiscerningAbility")
class TwistedDiscerningAbility(IntrigueAbility):
    """``AS.TwistedDiscerningAbility`` (spec §5): discard -> draw 1 (Space-Time
    Folding) OR with an Alliance draw 1; under ``DrawPlotGate``."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if not draw_plot_gate(p):
            return choice.answer("Twisted Discerning")
        if _option_open(request, 0):
            order = p.discard_order(_entities(request, 1, Kind.CARD) or _hand(p), False)
            if order:
                s = Summer()
                s.add("Discard", p.discard_value())
                s.add("Draw", _draw_value(p))
                if s.sum > 0:
                    choice.update_responses(s.sum, ((0,), (order[0].ref,)))
        if _option_open(request, 1) and p.ctx.me.alliance_faction_ids:
            draw = _draw_value(p)
            if draw > 0:
                choice.update_responses(draw, ((1,),))
        return choice.answer("Twisted Discerning")


def _other_intrigues(p: Profile, owner: Entity, request: Request) -> list[Entity]:
    """The held Intrigue cards other than ``owner`` (``infos[0]`` when given)."""

    given = _entities(request, 0, Kind.INTRIGUE)
    if given:
        return given
    return [i for i in _intrigue_hand(p) if i.ref != owner.ref]


@port(_AS + "TwistedInsidiousAbility")
class TwistedInsidiousAbility(IntrigueAbility):
    """``AS.TwistedInsidiousAbility`` (spec §5, D21): give an Intrigue to an
    opponent (+1 spice more if not Twisted) -> 1 spice. The gift is valued
    0 (plan §11.4); the recipient is the first offered."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Cannot pay: ``IntrigueHandCount < 2``."""

        return _intrigue_hand_count(p) < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        card = junk_intrigue_pick(p, _other_intrigues(p, self.owner, request))
        if card is None:
            return choice.answer("Twisted Insidious")
        s = Summer()
        s.add("Spice", p.spice_value(1 if _is_twisted(card) else 2))
        s.add("Lose Intrigue", p.trash_intrigue_value())
        if s.sum > 0:
            choice.update_responses(s.sum, ((card.ref,),))
        return choice.answer("Twisted Insidious")


@port(_AS + "TwistedResourcefulAbility")
class TwistedResourcefulAbility(IntrigueAbility):
    """``AS.TwistedResourcefulAbility`` (spec §5, D13): the played card has
    the Landsraad, City and Spice Trade icons: 100 at T0 iff it unlocks a
    better placement."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if (
            _in_player_turn(p, _UNDETERMINED)
            and unlock_value(p, grant_resourceful_icons) > 0
        ):
            choice.update_responses(100.0, ())
        return choice.answer("Twisted Resourceful")


@port(_AS + "TwistedSadisticAbility")
class TwistedSadisticAbility(IntrigueAbility):
    """``AS.TwistedSadisticAbility`` (spec §5): lose a troop -> draw 1 (Piter,
    Genius Advisor; no gate)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        s = Summer()
        s.add("Troop Cost", p.troop_value(-1, False))
        s.add("Draw", _draw_value(p))
        if s.sum > 0:
            choice.update_responses(s.sum, ())
        return choice.answer("Twisted Sadistic")


@port(_AS + "TwistedShrewdAbility")
class TwistedShrewdAbility(StrengthIntrigueAbility):
    """``AS.TwistedShrewdAbility`` (spec §5): lose a troop in the Conflict ->
    1 spice (the unit is lost, not retreated)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Reach Agreement (D31): ``IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        if p.should_play_retreat_intrigue("Shrewd", 2, 6, 1) > 0:
            s = Summer()
            s.add("Spice", p.spice_value(1))
            s.add("Troop Cost", p.troop_value(-1, False))
            if s.sum > 0:
                choice.update_responses(s.sum, ())
        return choice.answer("Twisted Shrewd")


@port(_AS + "TwistedSinisterAbility")
class TwistedSinisterAbility(StrengthIntrigueAbility):
    """``AS.TwistedSinisterAbility`` (spec §5): lose two troops -> an Intrigue
    and 1 Solari (Tleilaxu Surgeon's troop cost)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Cannot pay: fewer than 2 units."""

        return _troop_units(p.ctx.me) < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        s = Summer()
        s.add("Intrigue", p.intrigue_value())
        s.add("Solari", p.solari_value(1))
        s.add("Troop Cost", p.troop_value(-2, False))
        if s.sum > 0:
            choice.update_responses(s.sum, ())
        return choice.answer("Twisted Sinister")


@port(_AS + "TwistedUnnaturalAbility")
class TwistedUnnaturalAbility(IntrigueAbility):
    """``AS.TwistedUnnaturalAbility`` (spec §5): trash an Intrigue (+1 troop
    if not Twisted) -> draw an Intrigue."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """Cannot pay: ``IntrigueHandCount < 2``."""

        return _intrigue_hand_count(p) < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        choice = _Choice()
        card = junk_intrigue_pick(p, _other_intrigues(p, self.owner, request))
        if card is None:
            return choice.answer("Twisted Unnatural")
        s = Summer()
        s.add("Intrigue", p.intrigue_value())
        s.add("Trash Intrigue", p.trash_intrigue_value())
        if not _is_twisted(card):
            s.add("Troop", p.troop_value(1, False))
        if s.sum > 0:
            choice.update_responses(s.sum, ((card.ref,),))
        return choice.answer("Twisted Unnatural")


@port(_AS + "TwistedWithdrawnAbility")
class TwistedWithdrawnAbility(IntrigueAbility):
    """``AS.TwistedWithdrawnAbility`` (spec §5, D22): at turn start, pass. A
    pass has no app value (E 0); always junk (the preferred
    ``junk_intrigue_pick`` card)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        return True


# ===========================================================================
# §7 Contract tokens
# ===========================================================================


class _BloodlinesContractTerms(g.ContractAbility):
    """The terms a Bloodlines token adds to ``GetResourceValue`` (spec §7; not
    an app class): ``resource_value`` = the base reward + ``token_terms``.
    The profile's ``contract_resource_value`` (``GetBestContract``'s
    reader) adds the same terms through ``appstyle_contract_terms``."""

    def token_terms(self, p: Profile) -> Summer:
        """The token's terms beyond the printed Water/Solari/Troops."""

        return Summer()

    def resource_value(self, p: Profile) -> Summer:
        v = g.ContractAbility.resource_value(self, p)
        v.merge(self.token_terms(p))
        return v


@port(_AS + "Draw1ContractAbility")
class Draw1ContractAbility(_BloodlinesContractTerms, g.Draw2ContractAbility):
    """``AS.Draw1ContractAbility`` (spec §7; Secrets token: 2 Solari + a
    card). ``Draw2ContractAbility`` with one card (its CanRunImmediately)."""

    def token_terms(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Draw 1", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


class _HarvestSpyContractAbility(_BloodlinesContractTerms):
    """The two Harvest-Spy tokens (spec §7, D24; not an app class):
    ``GetResourceValue`` adds ``SpyValue`` (PlaceSpyContractAbility) and V
    keeps it (the app's Harvest V calls the base non-virtually)."""

    THRESHOLD: ClassVar[int] = 0

    def token_terms(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Place Spy", p.spy_value().sum)
        return v

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """The Harvest gate (the candidate space's ``Spice + BonusSpice``
        reaches the threshold) -> this ``GetResourceValue``."""

        space = g.collect_first(with_entities, Kind.SPACE)
        if (
            space is not None
            and any(s.ref == space.ref for s in g.contract_spaces(p, self.owner))
            and space.int_attr("Spice") + g._space_bonus_spice(p, space)
            >= self.THRESHOLD
        ):
            return self.resource_value(p)
        return Summer()


@port(_AS + "Harvest3SpyContractAbility")
class Harvest3SpyContractAbility(_HarvestSpyContractAbility, Harvest3ContractAbility):
    """``AS.Harvest3SpyContractAbility`` (spec §7): Harvest 3+ -> 2 Solari
    and a Spy."""

    THRESHOLD: ClassVar[int] = 3


@port(_AS + "Harvest4SpyContractAbility")
class Harvest4SpyContractAbility(_HarvestSpyContractAbility, Harvest4ContractAbility):
    """``AS.Harvest4SpyContractAbility`` (spec §7): Harvest 4+ -> 3 Solari
    and a Spy."""

    THRESHOLD: ClassVar[int] = 4


@port(_AS + "ImmediateTrashIntrigueContractAbility")
class ImmediateTrashIntrigueContractAbility(_BloodlinesContractTerms):
    """``AS.ImmediateTrashIntrigueContractAbility`` (spec §7): trash an
    Intrigue -> an Intrigue and a card. ``ContractType`` Immediate, so
    ``SpecificAcquireValue`` is this ``GetResourceValue`` (not
    round-discounted, as ``ContractBase_19``; the token prints no
    Water/Solari/Troops, so the base adds 0); the trash pick is
    ``junk_intrigue_pick``."""

    def token_terms(self, p: Profile) -> Summer:
        v = Summer()
        v.add("Intrigue", p.intrigue_value())
        v.add("Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        v.add("Trash Intrigue", p.trash_intrigue_value())
        return v


def earn_alliance_acquire_value(p: Profile, resource_value: float) -> Summer:
    """Earn Any Alliance's ``SpecificAcquireValue`` (spec §7, D23).

    ``RewardValueMod`` with the Acquire ratio (``max((9 - round) * 0.125,
    0.25) * (ratio * GetResourceValue)``, the literals and order of
    ``RewardValueMod``) and the HighCouncilMod shape of the TSMF contract:
    ``±3.0 * AcquireContractHighCouncilModRatio`` for "one step from a new
    Alliance" (``HasOrWouldGainAlliance(f, 1)`` for a faction whose Alliance
    P does not hold). The Acquire branch's RoundMod is not copied.
    """

    c = p.C
    factor = max((9.0 - p.ctx.round_number) * 0.125, 0.25)
    v = Summer()
    v.add(
        "RewardValueMod",
        factor * (c.AcquireContractRewardValueModRatio * resource_value),
    )
    held = p.ctx.me.alliance_faction_ids
    near = any(f not in held and p.has_or_would_gain_alliance(f, 1) for f in FACTIONS)
    v.add("AllianceMod", (3.0 if near else -3.0) * c.AcquireContractHighCouncilModRatio)
    return v


@port(_AS + "EarnAllianceContractAbility")
class EarnAllianceContractAbility(_BloodlinesContractTerms):
    """``AS.EarnAllianceContractAbility`` (spec §7, D23): earn any Alliance ->
    2 Solari, 2 troops. ``ContractType`` Alliance (new): completion is
    automatic (``rules/contracts.py`` ``complete_alliance_contracts``), so V
    is empty; ``SpecificAcquireValue`` = ``earn_alliance_acquire_value``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        return Summer()

    def specific_acquire_value(self, p: Profile) -> Summer:
        return earn_alliance_acquire_value(p, self.resource_value(p).sum)


#: The token classes ``profile/influence.py`` dispatches to (spec §7).
APPSTYLE_CONTRACT_ABILITIES: Final = frozenset(
    {
        _AS + "Draw1ContractAbility",
        _AS + "EarnAllianceContractAbility",
        _AS + "Harvest3SpyContractAbility",
        _AS + "Harvest4SpyContractAbility",
        _AS + "ImmediateTrashIntrigueContractAbility",
    }
)


def appstyle_contract_terms(ability_class: str, contract: Entity, p: Profile) -> Summer:
    """``token_terms`` of a Bloodlines token's contract ability, for the
    profile's ``contract_resource_value`` (vslot 91)."""

    ability = ability_for(ability_class, contract)
    if isinstance(ability, _BloodlinesContractTerms):
        return ability.token_terms(p)
    return Summer()


__all__ = [
    "APPSTYLE_CONTRACT_ABILITIES",
    "APPSTYLE_PREVIEW_REVEALS",
    "CONFLICT",
    "DISCARD_TOP",
    "DRAW_TOP_FOR_SOLARI",
    "GARRISON",
    "PUT_BACK_TOP",
    "Grant",
    "command_center_commanders",
    "command_reached",
    "controlled_peek_choice",
    "appstyle_contract_terms",
    "disruption_gain",
    "draw_plot_gate",
    "earn_alliance_acquire_value",
    "gained_spice",
    "grant_bene_gesserit_boost",
    "grant_emperor_icon",
    "grant_ignore_requirements",
    "grant_resourceful_icons",
    "grasp_arrakis_flip_pick",
    "junk_intrigue_pick",
    "lose_unit_pick",
    "optional_trash_pick",
    "rank_with",
    "retreat_target_code",
    "retreat_target_of",
    "reveal_preview_persuasion",
    "spice_gained_this_turn",
    "spy_move_pick",
    "tenuous_bond_trash_pick",
    "unlock_active",
    "unlock_value",
]
