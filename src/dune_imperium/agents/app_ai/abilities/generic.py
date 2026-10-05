"""Generic ability classes used across many archetypes — spec/generic-abilities.md.

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``), so the app's
inheritance (``TrashConflictCustomAbility`` -> ``TrashCustomAbility`` ->
``TrashAbility`` -> ``DeferredAbility`` -> ``ActivatedAbility``) is the Python
MRO. Card-, space- and leader-specific classes subclass these bases in the
other modules.

Request / answer encoding used by every ``evaluate`` here (``abilities/base``):

- the candidates of a prompt are ``request.infos[0]``: ``entities`` for entity
  targets (spaces, cards, contracts, spies, agents, faction tracks) and
  ``options`` for custom choices and for garrison units (one index per valid
  unit; ``DeployUnitsAbility``);
- ``Answer.response is None``: nothing stored (the app's untouched choice,
  value 0); ``()``: "use this ability" with no sub-targets (the app's
  ``UpdateSelectionTargets(v, src, null)`` / empty response array);
  ``((ref, ...),)``: the chosen refs / option indices of the first target info.

Engine-side members: ``selection_mode(p)``, ``can_run_immediately(p)``,
``always_run_immediately``, ``contextually_deferred``, ``defer_value(p)``,
``timing``, ``meets_cost(p)`` (the ``Cost`` check where the AI hooks call
``MeetsCost``) and ``possible_conflict_vp(p, double_cost)`` (vslot 88).

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Pile,
    Request,
    SelectionMode,
    Timing,
    UnportedAbility,
    abilities_of,
    ability_for,
    port,
)
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    LEADER_ARCHETYPES,
    SPACE_ARCHETYPES,
    card_entity,
    conflict_entity,
    contract_entity,
    intrigue_entity,
    leader_entity,
    space_archetype,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core.state import GamePhase

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ---------------------------------------------------------------------------
# Shared helpers (the app's extension methods, read through AppContext)
# ---------------------------------------------------------------------------

#: ``get_GetDeferralThreshold @0x483e3a0``: ``CustomDeferralThreshold`` if >= 0,
#: else the literal 3. No Uprising effect sets ``CustomDeferralThreshold``.
DEFERRAL_THRESHOLD = 3

_APP_TO_FACTION = {app: ours for ours, app in FACTION_NAMES.items()}
_TSMF_ARCHETYPES = (
    "ImperiumArchetypes.BaseSet.TheSpiceMustFlow",
    "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP",
)
_SIGNET_RING = "ImperiumArchetypes.BaseSet.SignetRing"
_SIGNET_ABILITY = "worm.canis.abilities.ActivatedAbilities.SignetAbility"
_REVEREND_MOTHER_ABILITY = (
    "worm.canis.abilities.ActivatedAbilities.Uprising.ReverendMotherAbility"
)
_LADY_JESSICA = "LeaderArchetypes.Uprising.LadyJessicaLeader"
_SHADDAM = "LeaderArchetypes.Uprising.ShaddamCorrinoIV"
_IRULAN = "LeaderArchetypes.Uprising.PrincessIrulan"
# Base-game leaders the app tests by ArchID; never dealt in 4-player Uprising
# (``LEADER_ARCHETYPES`` holds none of them), so those branches never fire.
_BARON = "LeaderArchetypes.BaseSet.BaronVladimirHarkonnen"
_MEMNON = "LeaderArchetypes.BaseSet.EarlMemnonThorvald"
_ARIANA = "LeaderArchetypes.BaseSet.CountessArianaThorvald"
_ILBAN = "LeaderArchetypes.BaseSet.CountIlbanRichese"
_ARMAND = "LeaderArchetypes.RiseOfIx.ArchdukeArmandEcaz"
_POST_SPACES: dict[str, tuple[str, ...]] = {
    post.post_id: tuple(post.connected_space_ids) for post in OBSERVATION_POSTS
}


def app_isinstance(ability: Ability, app_class: str) -> bool:
    """C# ``ability is <app_class>`` for ports registered in any module.

    True when the port class of ``ability`` (or one of its bases) is registered
    under ``app_class``, or when ``ability`` is the unported stand-in of exactly
    that class. Lets the generic code test for classes other modules port
    (``SignetAbility``, ``ReverendMotherAbility``) without importing them.
    """

    if isinstance(ability, UnportedAbility):
        return ability.app_class == app_class
    return any(vars(k).get("APP_CLASS") == app_class for k in type(ability).__mro__)


def ability_id(ability: Ability) -> str:
    """``GetAbilityID`` (vslot 47): the app class name of the ability."""

    if isinstance(ability, UnportedAbility):
        return ability.app_class
    return ability.APP_CLASS


def collect_first(entities: Sequence[Entity], kind: Kind) -> Entity | None:
    """``ListUtil.CollectFirst<T>``: the first entity of that type, else None.

    UNTRACED (spec UNTRACED list): assumed "first element of type T".
    """

    for entity in entities:
        if entity.kind is kind:
            return entity
    return None


def _targets(request: Request, kind: Kind) -> list[Entity]:
    """``choice.GetTargets(...).OfType<T>()``: the first target info's entities."""

    if not request.infos:
        return []
    return [e for e in request.infos[0].entities if e.kind is kind]


def _faction_influence(entity: Entity) -> list[tuple[str, int]]:
    """``WormAttributes.FactionInfluence`` as (our faction id, amount) pairs."""

    raw = entity.attr("FactionInfluence")
    if not isinstance(raw, Mapping):
        return []
    return [(_APP_TO_FACTION[str(f)], int(n)) for f, n in raw.items()]


def gain_any_influence_value(p: Profile, amount: int) -> Summer:
    """``GetGainInfluenceValue(Factions.None, amount, -1, false)``.

    The ``F == None`` branch of ``GetGainInfluenceValue @0x490a180``
    (``profile-influence-uprising.md`` §1.1), replayed here so the generic
    ports do not depend on how the influence port spells "no faction":
    ``amount > 0`` (strict) -> the summer of the faction with the largest
    ``Sum`` (``Enumerable.Max``: the first maximum in ``FactionList`` order is
    kept), else the smallest. ``FactionList`` = the four tracks in board order.
    """

    values = [p.gain_influence_value(f, amount, -1, False) for f in FACTIONS]
    best = values[0]
    for value in values[1:]:
        if (value.sum > best.sum) if amount > 0 else (value.sum < best.sum):
            best = value
    return best


def _leader(p: Profile) -> Entity | None:
    """``P.Leader`` with its current face (the flipped face's abilities)."""

    me = p.ctx.me
    if me.leader_id is None or me.leader_id not in LEADER_ARCHETYPES:
        return None
    return leader_entity(me.leader_id, me.leader_face_id)


def _leader_arch_id(p: Profile) -> str | None:
    """``P.Leader.ArchID``.

    Judgement: a flipped leader keeps its own ArchID and gains ``Flipped``
    (the app tests ``ArchID == LadyJessicaLeader and Flipped``), so this is
    the archetype of ``leader_id``, never of the flipped face.
    """

    me = p.ctx.me
    if me.leader_id is None:
        return None
    return LEADER_ARCHETYPES.get(me.leader_id)


def _leader_flipped(p: Profile) -> bool:
    leader = _leader(p)
    return leader is not None and leader.attr("Flipped") is True


def _hand_cards(p: Profile) -> list[Entity]:
    """``P.Hand.children.OfType<WormImperiumPlayable>()`` (own hand, in order)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.hand]


def _cards_in_play(p: Profile) -> list[Entity]:
    """``P.AllCardsInPlay`` / ``P.PlayArea.children`` (our ``in_play``)."""

    return [card_entity(i, p.ctx.seat) for i in p.ctx.me.in_play]


def _intrigue_hand(p: Profile) -> list[Entity]:
    return [intrigue_entity(i, p.ctx.seat) for i in p.ctx.intrigue_cards]


def card_factions(card: Entity) -> tuple[str, ...]:
    """``WormEntityExtensions::FactionsList`` (app faction names)."""

    return card.list_attr("FactionList")


def signet_icons(card: Entity) -> int:
    """``WormEntityExtensions::SignetIcons @0x482d390``.

    The ``SignetIcons`` attribute, or 1 for ``BaseSet.SignetRing`` when the
    attribute is 0 (``leaders.md`` §0.1).
    """

    n = card.int_attr("SignetIcons")
    if n == 0 and card.short == _SIGNET_RING:
        return 1
    return n


def _is_tsmf(card: Entity) -> bool:
    """``IsTheSpiceMustFlowImperium @0x482f1b0``."""

    return card.kind is Kind.CARD and card.short in _TSMF_ARCHETYPES


def _has_drawable_card(p: Profile) -> bool:
    """``HasDrawableCard`` (UNTRACED name-level read): a card to draw or to
    reshuffle, i.e. draw pile or discard pile non-empty (sizes only)."""

    me = p.ctx.me
    return p.ctx.deck_size + len(me.discard_pile) > 0


def _deployed_spies(p: Profile) -> int:
    """``P.GetDeployedSpies().Count()`` / ``SpyDeployedCount``."""

    return len(p.ctx.me.spy_post_ids)


def _observing_spies(p: Profile, space_id: str) -> int:
    """``space.GetObservingSpies(P).Count()``: P's spies on connected posts."""

    return sum(
        1 for post in p.ctx.me.spy_post_ids if space_id in _POST_SPACES.get(post, ())
    )


def _space_bonus_spice(p: Profile, space: Entity) -> int:
    """``WormEntityExtensions::BonusSpice @0x482c780`` (runtime attribute).

    The app keeps the accumulated bonus spice on the maker space entity; ours is
    ``state.maker_bonus_spice`` (public). Other spaces: the archetype value (0).
    """

    for space_id, amount in p.ctx.state.maker_bonus_spice:
        if space_id == space.ref:
            return amount
    return space.int_attr("BonusSpice")


def space_solari_cost(p: Profile, space: Entity) -> int:
    """The space's runtime ``SolariCost`` attribute.

    ``SwordmasterUprisingSpaceAbility/<DecreaseInitialCost>d__6 @0x4bc2bd0``
    adds -2 to the Swordmaster space's ``SolariCost`` (only while it is 8)
    when the first Swordmaster is taken; our engine charges 6 once anyone holds
    one (``agent_turn._effective_costs``). Every other cost is static.
    """

    cost = space.int_attr("SolariCost")
    if space.ref == "swordmaster" and cost == 8:
        if any(pl.swordmaster_acquired for pl in p.ctx.players):
            cost += -2
    return cost


def _space_ids_by_archetype(p: Profile) -> dict[str, str]:
    """Board-space archetype short -> our space id (this game's CHOAM setting)."""

    choam = p.ctx.choam
    return {
        (with_choam if choam else without): space_id
        for space_id, (without, with_choam) in SPACE_ARCHETYPES.items()
    }


def find_space(p: Profile, arch_id: str) -> Entity | None:
    """``Playmat.Board.FindSpace(archID)``: the board space with that archetype."""

    space_id = _space_ids_by_archetype(p).get(arch_id)
    if space_id is None:
        return None
    return space_entity(space_id, p.ctx.board)


def contract_spaces(p: Profile, contract: Entity) -> list[Entity]:
    """``WormContractPlayable.ContractSpaces @0x482a7a0``.

    ``BoardSpaces.Where(ReferencedArchetypeIDs.Contains(ArchID))`` in board
    order (``SPACE_ARCHETYPES`` order).
    """

    referenced = set(contract.list_attr("ReferencedArchetypeIDs"))
    board = p.ctx.board
    spaces = []
    for space_id in SPACE_ARCHETYPES:
        if space_archetype(space_id, board) in referenced:
            spaces.append(space_entity(space_id, board))
    return spaces


def _contract_area(p: Profile) -> list[Entity]:
    """``P.ContractArea`` contracts: completed (flipped) ones stay in it.

    Judgement: the app keeps them in the order taken; ours are split into
    ``completed_contract_ids`` and ``active_contract_ids``, listed oldest
    group first. The order only changes float summation order.
    """

    me = p.ctx.me
    return [
        contract_entity(i, p.ctx.seat)
        for i in (*me.completed_contract_ids, *me.active_contract_ids)
    ]


def _contract_options(p: Profile) -> list[str]:
    """``WormPlayer::GetContractOptions @0x4845240``.

    The contract row, then the set-aside Sardaukar contracts listed in
    ``AdditionalContractOptions`` (only Shaddam's player has them; ours:
    ``state.sardaukar_contract_ids``, public).
    """

    options = list(p.ctx.face_up_contract_ids)
    if _leader_arch_id(p) == _SHADDAM:
        options.extend(p.ctx.state.sardaukar_contract_ids)
    return options


def _this_turn_agent(p: Profile) -> tuple[list[Entity], list[Entity]]:
    """The unexhausted agent card(s) and agent space(s) of this turn.

    ``ActiveAgentArea.children.OfType<WormPlayable>().Where(!IsExhausted)``
    and ``BoardSpaces.Where(PlayerAgent(P) is unexhausted)``: [I]
    (engine-order §4.1) the card and space of the current Agent turn. Ours:
    the ``card_id``/``space_id`` of the seat's own open ``agent_effects``
    frame; none outside an Agent turn. The RoI/Immortality grafted card does
    not exist in Uprising.
    """

    context = p.ctx.own_frame_context("agent_effects")
    if context is None:
        return [], []
    cards = []
    spaces = []
    card_ref = context.get("card_id")
    if isinstance(card_ref, str) and card_ref:
        cards.append(card_entity(card_ref, p.ctx.seat))
    space_ref = context.get("space_id")
    if isinstance(space_ref, str) and space_ref:
        spaces.append(space_entity(space_ref, p.ctx.board))
    return cards, spaces


def deferred_threshold_reached(p: Profile) -> bool:
    """``WormPlayer::DeferredThresholdReached()`` @0x483e470 (core @0x482c8a0).

    engine-order.md §4.1: the summed ``DeferValue`` (archetype attribute,
    absent = 0) of this turn's unexhausted agent card(s), **every intrigue card
    in hand** and this turn's agent space(s), plus one leader extra, plus the
    ``DeferValue`` of P's face-up contracts whose spaces include a turn space,
    reaches ``GetDeferralThreshold`` (3). When it does, draws, space influence
    and contract gains stop running automatically and wait in the post-action
    prompt (``DrawAbility``/``GainInfluenceAbility``/``GainContractAbility``/
    ``Draw2ContractAbility.can_run_immediately``).

    Leader extras (first matching branch only): Baron +2, Earl Memnon +2,
    Countess Ariana +1, Count Ilban +1 are base-game leaders (dead here);
    Princess Irulan +2 at an Emperor-icon space while her Emperor influence is
    below 2 or she holds the ``ImperialBirthrightDeferredAbility`` grant.
    Judgement: our engine resolves Imperial Birthright automatically, so the
    grant is never held; only the influence test remains.
    """

    cards, spaces = _this_turn_agent(p)
    n = 0
    for entity in (*cards, *_intrigue_hand(p), *spaces):
        n += entity.int_attr("DeferValue")
    leader = _leader_arch_id(p)
    if leader == _BARON:  # needs P.PrivateInformation BaronHarkonnenSecretFactions
        pass
    elif leader == _MEMNON and any(s.ref == "high_council" for s in spaces):
        n += 2
    elif leader == _ARIANA and any(
        s.int_attr("Spice") > 0 and s.has("BonusSpice") for s in spaces
    ):
        n += 1
    elif leader == _ILBAN and any(s.attr("AgentIcon") == "Pentagon" for s in spaces):
        n += 1
    elif leader == _IRULAN and any(s.attr("AgentIcon") == "Emperor" for s in spaces):
        if p.ctx.me.influence.emperor < 2:
            n += 2
    turn_space_ids = {s.ref for s in spaces}
    for contract_ref in p.ctx.me.active_contract_ids:  # IsFaceUp: not completed
        contract = contract_entity(contract_ref, p.ctx.seat)
        defer = contract.int_attr("DeferValue")
        if defer > 0 and any(
            s.ref in turn_space_ids for s in contract_spaces(p, contract)
        ):
            n += defer
    return n >= DEFERRAL_THRESHOLD


def _no_current_player(p: Profile) -> bool:
    """``WormMatch.CurrentPlayer() == null``.

    [I] no seat takes a turn outside the player-turns phase. Judgement: inside
    it the current player is taken to be the deciding seat ``p`` (the app asks
    these members of the active player's own abilities).
    """

    return p.ctx.state.phase is not GamePhase.PLAYER_TURNS


def _runs_unless_threshold(p: Profile) -> bool:
    """CanRunImmediately of DrawAbility @0x4cda330 / GainInfluenceAbility
    @0x4bad8b0 / GainContractAbility @0x4d121f0.

    ``cp == null or cp.IsInPlayerTurn(Reveal) or !cp.DeferredThresholdReached()``.
    Ours: in the Reveal turn ``has_revealed`` is already set.
    """

    if _no_current_player(p):
        return True
    if p.ctx.me.has_revealed:
        return True
    return not deferred_threshold_reached(p)


def _in_combat_phase(p: Profile) -> bool:
    """``Playmat.RoundPhase == 20 (Combat)`` / ``IsInPlayerTurn(CombatTurn)``."""

    return p.ctx.state.phase is GamePhase.COMBAT


def value_for_reveal_abilities(card: Entity, p: Profile) -> Summer:
    """``WormImperiumExtensions::GetValueForRevealAbilities @0x4834020``.

    Merge over the card's ``RevealAbility`` objects of ``ValueForPlayer(P, [])``.
    """

    value = Summer()
    for ability in abilities_of(card):
        if isinstance(ability, RevealAbility):
            value.merge(ability.value_for_player(p, ()))
    return value


# ---------------------------------------------------------------------------
# Play abilities: AgentAbility, PowerPlayAgentAbility, RevealAbility
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.PlayAbility")
class PlayAbility(Ability):
    """``PlayAbilities.PlayAbility`` (abstract; source entity = the card)."""


@port("worm.canis.abilities.PlayAbilities.AgentAbility")
class AgentAbility(PlayAbility):
    """``PlayAbilities.AgentAbility``: the generic agent box (spec §2)."""

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``AgentAttributes`` (+0x80, ctor @0x4bd0ab0), insertion order.
    AGENT_ATTRIBUTES: ClassVar[tuple[tuple[str, Attr], ...]] = (
        ("AgentWater", Attr.WATER),
        ("AgentSpice", Attr.SPICE),
        ("AgentSolari", Attr.SOLARI),
    )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AgentAbility::Evaluate`` @0x4bd28b0 (spec §2.1): the space loop.

        For each legal space (``request.infos[0]`` space entities, target
        order) on which some ``SpaceAbility``-derived ability can run:
        ``Σ space abilities' value_for_player(p, [card]) +
        self.value_for_player(p, [space])``; the first strictly best space
        is kept (the first one always sticks, even at a value <= 0).
        """

        stored: Answer | None = None
        for space in _targets(request, Kind.SPACE):
            space_abilities = abilities_of(space)
            runnable = [a for a in space_abilities if isinstance(a, SpaceAbility)]
            if all(not a.can_be_run(p) for a in runnable):
                continue  # also skips a space without any SpaceAbility
            card_v = self.value_for_player(p, (space,))
            space_v = Summer()
            for ability in space_abilities:
                space_v.merge(ability.value_for_player(p, (self.owner,)))
            total = space_v.sum + card_v.sum
            if stored is None or total > stored.value:
                stored = Answer(total, ((space.ref,),), f"AgentAbility -> {space.ref}")
        if stored is None:
            return Answer(0.0, None, "AgentAbility no space")
        return stored

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``AgentAbility::ValueForPlayer`` @0x4bd11d0 (spec §2.2).

        ``with_entities`` is ``[space]`` from ``evaluate``.
        """

        v = Summer()
        card = self.owner
        abilities = abilities_of(card)
        # (a) the card's other agent-timed effects, valued with this space
        for d in abilities:
            if isinstance(d, DeferredAbility) and d.timing == Timing.AGENT:
                v.merge(d.value_for_player(p, with_entities))
        for t in abilities:
            if isinstance(t, TriggeredAbility) and t.timing == Timing.AGENT:
                v.merge(t.value_for_player(p, with_entities))
        # (b) printed agent-box resources
        for card_attr, resource in self.AGENT_ATTRIBUTES:
            n = card.int_attr(card_attr)
            if n > 0:
                v.add("Agent " + card_attr, p.resource_value(resource, n, False))
        troops = card.int_attr("AgentTroops")
        if troops > 0:
            v.add("Agent Troops", p.troop_value(troops, False))
        # (c) "Imperium Play Bonus": the other hand cards' play-area synergy
        bonus: list[Summer] = []
        for other in _hand_cards(p):
            if other.ref == card.ref:
                continue
            for ability in abilities_of(other):
                bonus.append(
                    ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, card)
                )
        if any(b.sum > 0 for b in bonus):  # ``seta``: strict
            whole = Summer()
            for b in bonus:
                whole.merge(b)
            v.add("Imperium Play Bonus", whole.sum)  # the whole concatenation
        # (d) leader signet
        if signet_icons(card) > 0:
            leader = _leader(p)
            if leader is not None:
                for ability in abilities_of(leader):
                    if app_isinstance(ability, _SIGNET_ABILITY):
                        v.merge(ability.value_for_player(p, with_entities))
        # (e) Rise of Ix "One Step Ahead": its player attribute is never set in
        # Uprising, so the term is absent.
        # (f) reveal opportunity cost; Artillery (RoI tech) never applies.
        rv = value_for_reveal_abilities(card, p)
        rv.multiply("Reveal Scale", p.C.CardPlayValueRevealPenalty)
        v.merge(rv)  # MergePrependReason "Reveal Penalty "
        return v


@port("worm.canis.abilities.PlayAbilities.BaseSet.PowerPlayAgentAbility")
class PowerPlayAgentAbility(AgentAbility):
    """``PlayAbilities.BaseSet.PowerPlayAgentAbility`` (spec §2.3)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PowerPlayAgentAbility::ValueForPlayer`` @0x4caab10."""

        v = super().value_for_player(p, with_entities)
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None:
            influence = _faction_influence(space)
            base = 0.0
            for faction, n in influence:  # b__0 @0x4caae30
                base += p.gain_influence_value(faction, n, -1, False).sum
            plus = 0.0
            for faction, n in influence:  # b__1 @0x4caaec0
                plus += p.gain_influence_value(faction, n + 1, -1, False).sum
            v.add("Power Play Bonus Influence", plus - base)
        return v


@port("worm.canis.abilities.PlayAbilities.RevealAbility")
class RevealAbility(Ability):
    """``PlayAbilities.RevealAbility``: the generic reveal box (spec §3).

    Derives from ``WormAbilityDefinition`` directly (not ``PlayAbility``).
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    #: ``ValueAttributes`` (+0x88, ctor @0x4bdae20).
    VALUE_ATTRIBUTES: ClassVar[tuple[Attr, ...]] = (
        Attr.WATER,
        Attr.SPICE,
        Attr.SOLARI,
        Attr.PERSUASION,
        Attr.STRENGTH,
        Attr.SPECIMEN,
        Attr.TROOPS,
    )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``RevealAbility::ValueForPlayer`` @0x4bdbc40 (spec §3.1)."""

        v = Summer()
        for attr in self.VALUE_ATTRIBUTES:
            n = self.owner.int_attr(attr.value)
            if n > 0:
                v.add("Reveal " + attr.value, p.resource_value(attr, n, False))
        abilities = abilities_of(self.owner)
        deferred = 0.0
        for d in abilities:  # b__12_0 (timing == Reveal), b__1
            if isinstance(d, DeferredAbility) and d.timing == Timing.REVEAL:
                deferred += d.value_for_player(p, ()).sum
        v.add("Reveal Deferred", deferred)
        triggered = 0.0
        for t in abilities:  # b__12_2, b__3
            if isinstance(t, TriggeredAbility) and t.timing == Timing.REVEAL:
                triggered += t.value_for_player(p, ()).sum
        v.add("Reveal Triggered", triggered)
        return v


# ---------------------------------------------------------------------------
# Activated abilities: AcquireAbility and the DeferredAbility family
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.ActivatedAbilities.ActivatedAbility")
class ActivatedAbility(Ability):
    """``ActivatedAbilities.ActivatedAbility`` (abstract)."""


@port("worm.canis.abilities.ActivatedAbilities.AcquireAbility")
class AcquireAbility(ActivatedAbility):
    """``ActivatedAbilities.AcquireAbility``: buying a card (spec §4)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AcquireAbility::Evaluate`` @0x4cd3c50 (spec §4.1).

        The Tleilaxu branch (Immortality) never applies. The destination
        picker (``ChooseOne``: option 0 top of deck, 1 hand/discard) is
        expected never to appear in Uprising (spec §4.2, UNTRACED); a request
        whose first target info carries custom ``options`` is treated as that
        picker (judgement).
        """

        card = self.owner
        value = p.acquire_value(card).sum
        if request.infos and request.infos[0].options:
            if _in_combat_phase(p):
                value = 1.0 if value <= 0 else value  # ``cmplesd``
            option = 1 if _is_tsmf(card) else 0
            return Answer(value, ((option,),), f"Acquire {card.ref}")
        return Answer(value, (), f"Acquire {card.ref}")


@port("worm.canis.abilities.ActivatedAbilities.DeferredAbility")
class DeferredAbility(ActivatedAbility):
    """``ActivatedAbilities.DeferredAbility`` (abstract; spec §5)."""

    #: ``get_AlwaysRunImmediately @0x4cd6640``.
    always_run_immediately: ClassVar[bool] = False
    #: ``get_ContextuallyDeferred @0x4cd6650``.
    contextually_deferred: ClassVar[bool] = False

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SelectionMode(ctx)`` (vslot 82): abstract in the app."""

        raise NotImplementedError(f"{type(self).__name__}.selection_mode")

    def can_run_immediately(self, p: Profile) -> bool:
        """``DeferredAbility::CanRunImmediately`` @0x4cd6620."""

        return self.always_run_immediately

    def meets_cost(self, p: Profile) -> bool:
        """``AbilityExtensions::MeetsCost`` with this class's ``Cost``.

        Only the costs the AI hooks read are modelled; the engine owns
        legality otherwise.
        """

        return True

    def defer_value(self, p: Profile) -> int:
        """The owner's ``DeferValue`` (1 if Explicit, else 0 when absent)."""

        default = 1 if self.selection_mode(p) == SelectionMode.EXPLICIT else 0
        return self.owner.int_attr("DeferValue", default)

    def possible_conflict_vp(self, p: Profile, double_cost: bool) -> int:
        """``DeferredAbility::GetPossibleConflictVP`` @0x4cd71d0: 0."""

        return 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DeferredAbility::Evaluate`` @0x4cd71e0 (spec §5.1).

        ``UpdateSelectionTargets((double)DeferValue, src, null)``.
        """

        return Answer(float(self.defer_value(p)), (), f"{type(self).__name__} defer")


# -- draws --


@port("worm.canis.abilities.ActivatedAbilities.DrawAbility")
class DrawAbility(DeferredAbility):
    """``ActivatedAbilities.DrawAbility`` (spec §7); E = DeferValue."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4cda150
    contextually_deferred: ClassVar[bool] = True  # @0x4cda380

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DrawAbility::SelectionMode`` @0x4cda320: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``DrawAbility::CanRunImmediately`` @0x4cda330."""

        return _runs_unless_threshold(p)

    def meets_cost(self, p: Profile) -> bool:
        """``DrawAbility::Cost`` @0x4cda2d0 = ``HasDrawableCard``."""

        return _has_drawable_card(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DrawAbility::ValueForPlayer`` @0x4cda540 (count not read)."""

        v = Summer()
        if self.meets_cost(p):
            v.add("Draw Value", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return v


@port("worm.canis.abilities.ActivatedAbilities.Uprising.SpacingGuildDiscardDrawAbility")
class SpacingGuildDiscardDrawAbility(DrawAbility):
    """``Uprising.SpacingGuildDiscardDrawAbility`` (Guild Envoy, Space-Time
    Folding)."""

    def has_run_token(self, p: Profile) -> bool:
        """``P.CustomAbilityIDs`` holds this ability's id with run tokens left.

        UNTRACED (our engine has no such grant): the card's discard rider
        grants it only while resolving; never held at valuation. A card port
        that models the grant overrides this.
        """

        return False

    def meets_cost(self, p: Profile) -> bool:
        """``SpacingGuildDiscardDrawAbility::Cost`` @0x4d402b0: the granted
        ``CustomAbilityIDs`` entry and ``AbilityRunTokens``; no
        ``HasDrawableCard``."""

        return self.has_run_token(p)


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.BeneGesseritInfluenceDrawAbility"
)
class BeneGesseritInfluenceDrawAbility(DrawAbility):
    """``Uprising.BeneGesseritInfluenceDrawAbility`` (Hidden Missive, Prepare
    the Way)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4ceced0: ``HasFactionInfluence.AtLeast(BG, 2)`` and
        ``HasDrawableCard``."""

        return p.ctx.me.influence.bene_gesserit >= 2 and _has_drawable_card(p)


class _CargoRunnerContractsDrawAbility(DrawAbility):
    """Shared body of the two Cargo Runner draws (not an app class: both app
    classes derive from ``DrawAbility`` directly)."""

    CONTRACTS: ClassVar[int] = 0  # literal of each Cost

    def meets_cost(self, p: Profile) -> bool:
        """``HasAtLeastContractsCompleted(n)`` and ``HasDrawableCard``."""

        completed = len(p.ctx.me.completed_contract_ids)
        return completed >= self.CONTRACTS and _has_drawable_card(p)


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.CargoRunner2ContractsDrawAbility"
)
class CargoRunner2ContractsDrawAbility(_CargoRunnerContractsDrawAbility):
    """``Uprising.CargoRunner2ContractsDrawAbility`` (Cargo Runner)."""

    CONTRACTS: ClassVar[int] = 2


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.CargoRunner4ContractsDrawAbility"
)
class CargoRunner4ContractsDrawAbility(_CargoRunnerContractsDrawAbility):
    """``Uprising.CargoRunner4ContractsDrawAbility`` (Cargo Runner)."""

    CONTRACTS: ClassVar[int] = 4


def bg_played_pile_value(
    p: Profile, pile: Pile, card: Entity, played: Callable[[], float], label: str
) -> Summer:
    """The "BGP" synergy pattern (``imperium-b.md`` §0.5) with term ``played()``.

    Shared by ``BeneGesseritDrawAbility`` and the card classes that use the
    same pattern (Southern Elders agent, Bene Gesserit Trash, Weirding Woman).
    PlayArea: no BG card in play, the candidate is BG and P has >= 2 agents
    left (``cmp eax,2; jge``) -> ``played()`` under ``label``. Deck: the
    candidate is BG and not climax -> ``SynergyBeneGesseritWithBondInDeck``.
    """

    s = Summer()
    if pile is Pile.PLAY_AREA:
        if (
            not any("BeneGesserit" in card_factions(c) for c in _cards_in_play(p))
            and "BeneGesserit" in card_factions(card)
            and p.ctx.me.agents_available >= 2
        ):
            s.add(label, played())
            return s
    if (
        pile is Pile.DECK
        and "BeneGesserit" in card_factions(card)
        and not p.is_climax()
    ):
        s.add("Bene Gesserit in Deck", p.C.SynergyBeneGesseritWithBondInDeck)
    return s


@port("worm.canis.abilities.ActivatedAbilities.BeneGesseritDrawAbility")
class BeneGesseritDrawAbility(DrawAbility):
    """``ActivatedAbilities.BeneGesseritDrawAbility`` (In High Places, Tread in
    Darkness); overrides V and P."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4cdb820: ``HasPlayedFactionCard(BG, owner)`` then
        ``HasDrawableCard``.

        UNTRACED argument roles (``imperium-a.md``): read as another BG card
        than the owner in play.
        """

        other_bg = any(
            "BeneGesserit" in card_factions(c)
            for c in _cards_in_play(p)
            if c.ref != self.owner.ref
        )
        return other_bg and _has_drawable_card(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BeneGesseritDrawAbility::ValueForPlayer`` @0x4cdb8f0.

        ``AllCardsInPlay.Any(BG)`` (owner not excluded) then the
        MeetsCost-gated ``DrawAbility`` value, else empty.
        """

        if any("BeneGesserit" in card_factions(c) for c in _cards_in_play(p)):
            return super().value_for_player(p, ())
        return Summer()

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``BeneGesseritDrawAbility::ValueInPileForOtherPlay`` @0x4cdbae0.

        Pattern BGP with ``X = 0.75 * (CardDrawValue + GetBuyGains(
        PossiblePersuasionGain()))`` (f64 literal 0.75), label "No Bene
        Gesserit in Play".
        """

        def played() -> float:
            return 0.75 * (
                p.card_draw_value() + p.buy_gains(p.possible_persuasion_gain())
            )

        return bg_played_pile_value(p, pile, card, played, "No Bene Gesserit in Play")


# -- influence --


@port("worm.canis.abilities.SpaceAbilities.GainInfluenceAbility")
class GainInfluenceAbility(DeferredAbility):
    """``SpaceAbilities.GainInfluenceAbility``: a faction space's influence
    (spec §8); E = DeferValue of the space."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor stores AbilityTiming 1
    contextually_deferred: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainInfluenceAbility::SelectionMode`` @0x4bad8a0: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``GainInfluenceAbility::CanRunImmediately`` @0x4bad8b0."""

        return _runs_unless_threshold(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainInfluenceAbility::ValueForPlayer`` @0x4badd70 (no MeetsCost).

        ``AdditionalSpaceInfluence`` (a player bool) is never set in Uprising.
        """

        v = Summer()
        for faction, n in _faction_influence(self.owner):
            if n <= 0:
                continue
            amount = n + 0  # + 1 with AdditionalSpaceInfluence
            v.add(
                f"Gain {faction} Influence",
                p.gain_influence_value(faction, amount, -1, False).sum,
            )
        return v


@port("worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceAbility")
class GainAnyInfluenceAbility(DeferredAbility):
    """``ActivatedAbilities.GainAnyInfluenceAbility`` (abstract; spec §9)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainAnyInfluenceAbility::SelectionMode`` @0x4cdc0b0: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainAnyInfluenceAbility::ValueForPlayer`` @0x4cdc370."""

        v = Summer()
        v.add("Gain Any Influence", gain_any_influence_value(p, 1).sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainAnyInfluenceAbility::Evaluate`` @0x4cdc4f0.

        Faction tracks in target order (``request.infos[0]`` TRACK entities,
        ref = our faction id; the app's track order is UNTRACED), no
        shuffle: ``GetGainInfluenceValue(f, 1) + 100`` ("Static Boost"),
        first strict maximum. The House Hagal branch is unreachable.
        """

        stored: Answer | None = None
        for track in _targets(request, Kind.TRACK):
            s = Summer()
            s.merge(p.gain_influence_value(track.ref, 1, -1, False))
            s.add("Static Boost", 100.0)
            if stored is None or s.sum > stored.value:
                stored = Answer(
                    s.sum, ((track.ref,),), f"Gain Any Influence {track.ref}"
                )
        if stored is None:
            return Answer(0.0, None, "Gain Any Influence no track")
        return stored


@port("worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceAgentAbility")
class GainAnyInfluenceAgentAbility(GainAnyInfluenceAbility):
    """``GainAnyInfluenceAgentAbility`` (Interstellar Trade, Shipping)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4cddfa0


@port("worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceRevealAbility")
class GainAnyInfluenceRevealAbility(GainAnyInfluenceAbility):
    """``GainAnyInfluenceRevealAbility`` (no Uprising user)."""

    timing: ClassVar[Timing] = Timing.REVEAL  # ctor @0x4cde1b0


@port("worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceCustomAbility")
class GainAnyInfluenceCustomAbility(GainAnyInfluenceAbility):
    """``GainAnyInfluenceCustomAbility`` (abstract; ``Cost @0x4cde3e0`` =
    ``HasCustomAbility`` and ``CanGainInfluence``; timing None)."""


@port("worm.canis.abilities.ActivatedAbilities.GainAnyInfluenceConflictAbility")
class GainAnyInfluenceConflictAbility(GainAnyInfluenceCustomAbility):
    """``GainAnyInfluenceConflictAbility`` (Skirmish H 1st, Spice Freighters
    1st)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION  # ctor @0x4cde880

    def can_run_immediately(self, p: Profile) -> bool:
        """``GainAnyInfluenceConflictAbility::CanRunImmediately`` @0x4cdea10."""

        return True


# -- intrigue --


@port("worm.canis.abilities.ActivatedAbilities.GainIntrigueAbility")
class GainIntrigueAbility(DeferredAbility):
    """``ActivatedAbilities.GainIntrigueAbility`` (abstract; spec §10)."""

    always_run_immediately: ClassVar[bool] = True  # @0x4cdf320

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainIntrigueAbility::SelectionMode`` @0x4cdf310: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainIntrigueAbility::ValueForPlayer`` @0x4cdf5e0 (one card)."""

        v = Summer()
        if self.meets_cost(p):  # Cost @0x4cdf2c0 = NoCostAction
            v.add("Gain Intrigue", p.intrigue_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainIntrigueAbility::Evaluate`` @0x4cdf750: 100."""

        return Answer(100.0, (), "GainIntrigueAbility | 100")


@port("worm.canis.abilities.ActivatedAbilities.AgentGainIntrigueAbility")
class AgentGainIntrigueAbility(GainIntrigueAbility):
    """``AgentGainIntrigueAbility`` (Assembly Hall, Sardaukar, Secrets)."""

    timing: ClassVar[Timing] = Timing.AGENT


@port("worm.canis.abilities.ActivatedAbilities.RevealGainIntrigueAbility")
class RevealGainIntrigueAbility(GainIntrigueAbility):
    """``RevealGainIntrigueAbility`` (Treacherous Maneuver)."""

    timing: ClassVar[Timing] = Timing.REVEAL


@port("worm.canis.abilities.ActivatedAbilities.GainIntrigueCustomAbility")
class GainIntrigueCustomAbility(GainIntrigueAbility):
    """``GainIntrigueCustomAbility`` (Cost = NoCost and ``HasCustomAbility``;
    timing None)."""

    always_run_immediately: ClassVar[bool] = False  # @0x4ce0ad0

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: ``P`` holds this ability's custom grant.

        Judgement (unreachable today): no Uprising or CHOAM archetype lists
        this class (``Irulan`` and ``Muad'Dib`` derive from
        ``GainIntrigueAbility`` directly), so no frame of ours grants it; never
        held, like ``SpacingGuildDiscardDrawAbility.has_run_token``. A port
        that models the grant overrides this.
        """

        return False

    def meets_cost(self, p: Profile) -> bool:
        """``GainIntrigueCustomAbility::Cost`` @0x4ce0ae0 =
        ``NoCostAction.Then(HasCustomAbility(this))`` (generic-abilities §10).

        This gates the inherited ``GainIntrigueAbility::ValueForPlayer``
        @0x4cdf5e0, so V is 0 without the grant.
        """

        return self.has_custom_ability(p)


@port("worm.canis.abilities.ActivatedAbilities.Uprising.HighCouncilGainIntrigueAbility")
class HighCouncilGainIntrigueAbility(GainIntrigueAbility):
    """``Uprising.HighCouncilGainIntrigueAbility`` (High Council repeat
    visit)."""

    timing: ClassVar[Timing] = Timing.AGENT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d1a1b0 = ``HighCouncilUprisingSpaceAbility.
        MakeRepeatedVisitCost``: ``!CanTakeHighCouncilSeat`` then
        ``IsRepeatHighCouncilUse`` ≈ P holds the seat and did not gain it this
        turn ([I], ``board.md`` §1.4.10). Ours: the seat is held and the own
        open Agent turn at the High Council is not the first visit (its board
        icons hold no ``high_council`` seat icon).
        """

        if not p.ctx.me.high_council:
            return False
        context = p.ctx.own_frame_context("agent_effects")
        if context is not None and context.get("space_id") == "high_council":
            icons = str(context.get("board_icons", "")).split(",")
            if "high_council" in icons:
                return False  # the seat was taken by this visit
        return True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``HighCouncilGainIntrigueAbility::SelectionMode`` @0x4d1a160:
        ``2 | (Cost can be paid ? 1 : 0)`` (Implicit or Explicit; the vslot 12
        identity is [I])."""

        return SelectionMode(2 | (1 if self.meets_cost(p) else 0))


# -- deploy --


@port("worm.canis.abilities.ActivatedAbilities.DeployUnitsAbility")
class DeployUnitsAbility(DeferredAbility):
    """``ActivatedAbilities.DeployUnitsAbility`` (spec §11)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4cd7970

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DeployUnitsAbility::SelectionMode`` @0x4cd78b0: Optional."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DeployUnitsAbility::ValueForPlayer`` @0x4cd8170.

        Shaddam Corrino IV gets no deploy value for a card without a signet
        icon (quirk kept).
        """

        v = Summer()
        card = collect_first(with_entities, Kind.CARD)
        if card is None or signet_icons(card) > 0 or _leader_arch_id(p) != _SHADDAM:
            v.add("Deploy Units", p.deploy_value(self.owner))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DeployUnitsAbility::Evaluate`` @0x4cd7e20.

        ``request.infos[0].options``: one index per valid garrison unit;
        ``max_select`` = the maximum (``NumberToSelect``). The response is the
        first ``GetUnitsToDeploy`` unit indices; value 0.5 (ordering only).
        """

        if not request.infos:
            return Answer(0.0, None, "Deploy Units no target info")
        info = request.infos[0]
        units = info.options
        count = p.units_to_deploy(len(units), info.max_select)
        chosen = units[: max(count, 0)]
        if not chosen:
            return Answer(0.0, None, "Deploy Units none")
        return Answer(0.5, (tuple(chosen),), f"Deploy Units | 0.5 | {len(chosen)}")


# -- trash --


@port("worm.canis.abilities.ActivatedAbilities.TrashAbility")
class TrashAbility(DeferredAbility):
    """``ActivatedAbilities.TrashAbility`` (abstract; spec §12.1)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TrashAbility::SelectionMode`` @0x4ce94c0: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TrashAbility::ValueForPlayer`` @0x4ce9710 (no MeetsCost)."""

        v = Summer()
        v.add("Trash Card", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TrashAbility::Evaluate`` @0x4ce98a0.

        ``GetCardToTrash(targets, minTrashValue = 1.0)`` (literal); without a
        junk card the AI "uses" the trash at 1.0 and trashes nothing
        (response ``((),)``; the prompt's minimum is 0).
        """

        card, value = p.card_to_trash(_targets(request, Kind.CARD), 1.0)
        if card is not None:
            return Answer(value, ((card.ref,),), f"Trash {card.ref}")
        return Answer(value, ((),), "Trash nothing")


@port("worm.canis.abilities.ActivatedAbilities.TrashAgentAbility")
class TrashAgentAbility(TrashAbility):
    """``TrashAgentAbility`` (Desert Survival, Calculus of Power, Desert
    Tactics)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4ceadb0


@port("worm.canis.abilities.ActivatedAbilities.TrashCustomAbility")
class TrashCustomAbility(TrashAbility):
    """``TrashCustomAbility`` (``Cost @0x4ceb0f0`` = ``HasTrashableCard`` and
    ``HasCustomAbility``; timing None)."""


@port("worm.canis.abilities.ConflictAbilities.Uprising.TrashConflictCustomAbility")
class TrashConflictCustomAbility(TrashCustomAbility):
    """``ConflictAbilities.Uprising.TrashConflictCustomAbility`` (Trade Dispute
    1st/2nd); only the prompt archetype differs."""


@port("worm.canis.abilities.ActivatedAbilities.TrashSelfAbility")
class TrashSelfAbility(DeferredAbility):
    """``ActivatedAbilities.TrashSelfAbility`` (spec §12.2): runs by itself."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4ceb660
    always_run_immediately: ClassVar[bool] = True  # @0x4ceb770

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``TrashSelfAbility::SelectionMode`` @0x4ceb760: Implicit."""

        return SelectionMode.IMPLICIT


# -- spies --


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyAbility")
class PlaceSpyAbility(DeferredAbility):
    """``Uprising.PlaceSpyAbility`` (abstract; spec §13)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``PlaceSpyAbility::SelectionMode`` @0x4d2a0b0: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PlaceSpyAbility::ValueForPlayer`` @0x4d2a270 (post-independent)."""

        v = Summer()
        v.add("Place Spy Value", p.spy_value().sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PlaceSpyAbility::Evaluate`` @0x4d2a870.

        Answers "use" at ``SpyValue`` with an empty response: the post is
        chosen later by the ``PlaceSpy`` action's own prompt. The app's
        ``GetSpyAIResponses`` result only feeds a log line, so it is not
        computed (judgement: its shuffles draw from the app's clock RNG and
        cannot change this answer).
        """

        return Answer(p.spy_value().sum, (), "Place Spy")


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyAgentAbility")
class PlaceSpyAgentAbility(PlaceSpyAbility):
    """``PlaceSpyAgentAbility`` (Bene Gesserit Operative, Espionage)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4d2b830


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyRevealAbility")
class PlaceSpyRevealAbility(PlaceSpyAbility):
    """``PlaceSpyRevealAbility`` (Covert Operation, Public Spectacle, Wheels
    Within Wheels)."""

    timing: ClassVar[Timing] = Timing.REVEAL  # ctor @0x4d2ba00


@port("worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyCustomAbility")
class PlaceSpyCustomAbility(PlaceSpyAbility):
    """``PlaceSpyCustomAbility`` (Seize Spice Refinery 1st, Test of Loyalty
    1st; timing None)."""

    def can_run_immediately(self, p: Profile) -> bool:
        """``PlaceSpyCustomAbility::CanRunImmediately`` @0x4d2c330:
        ``Playmat.RoundPhase == Combat``."""

        return _in_combat_phase(p)


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.PlaceSpyCombatResolutionAbility"
)
class PlaceSpyCombatResolutionAbility(PlaceSpyAbility):
    """``PlaceSpyCombatResolutionAbility`` (no Uprising user in the census)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION  # ctor stores 3


# -- agent recall --


@port("worm.canis.abilities.ActivatedAbilities.Uprising.RecallAgentAbility")
class RecallAgentAbility(DeferredAbility):
    """``Uprising.RecallAgentAbility`` (Steersman, Imperial Privilege; §14)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4d2fe00

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``RecallAgentAbility::SelectionMode`` @0x4d2fef0: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``RecallAgentAbility::ValueForPlayer`` @0x4d30240 (no MeetsCost)."""

        v = Summer()
        v.add("Recall Agent Value", p.recall_agent_value())
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``RecallAgentAbility::Evaluate`` @0x4d303a0.

        ``GetRecallAgent(agents) ?? agents.FirstOrDefault()`` (AGENT
        entities of ``request.infos[0]``) at ``RecallAgentValue``.
        """

        agents = _targets(request, Kind.AGENT)
        agent = p.recall_agent(agents)
        if agent is None and agents:
            agent = agents[0]
        if agent is None:
            return Answer(0.0, None, "Recall Agent no target")
        return Answer(p.recall_agent_value(), ((agent.ref,),), f"Recall {agent.ref}")


# -- contracts --


def contract_value_for_player(p: Profile) -> Summer:
    """``GainContractAbility::ContractValueForPlayer`` @0x4d12640."""

    v = Summer()
    if _contract_options(p):
        v.add("Gain Contract Value", p.gain_contract_value().sum)
    else:
        v.add("Gain Contract 2 Solari", p.solari_value(2))
    return v


def contract_evaluate(p: Profile, request: Request, forced: bool) -> Answer:
    """``GainContractAbility::ContractEvaluate(ctx, ability, src, forced)``
    @0x4d127b0 (also Leverage's E with ``forced = False``).

    CONTRACT entities of ``request.infos[0]`` in ``GetContractOptions`` order.
    """

    targets = _targets(request, Kind.CONTRACT)
    best, value = p.best_contract(targets, forced)
    if best is not None:
        return Answer(value, ((best.ref,),), f"Contract {best.ref}")
    if not targets:
        return Answer(p.solari_value(2), (), "No contract: 2 Solari")
    return Answer(0.0, None, "No contract chosen")


@port("worm.canis.abilities.ActivatedAbilities.Uprising.GainContractAbility")
class GainContractAbility(DeferredAbility):
    """``Uprising.GainContractAbility`` (Accept Contract, Dutiful Service,
    Priority Contracts; spec §15)."""

    timing: ClassVar[Timing] = Timing.AGENT  # ctor @0x4d12020
    contextually_deferred: ClassVar[bool] = True

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainContractAbility::SelectionMode`` @0x4d121e0: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``GainContractAbility::CanRunImmediately`` @0x4d121f0."""

        return _runs_unless_threshold(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainContractAbility::ValueForPlayer`` @0x4d125f0."""

        return contract_value_for_player(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainContractAbility::Evaluate`` @0x4d12730 (forced)."""

        return contract_evaluate(p, request, True)


@port("worm.canis.abilities.ActivatedAbilities.Uprising.GainContractCustomAbility")
class GainContractCustomAbility(DeferredAbility):
    """``Uprising.GainContractCustomAbility`` (CHOAM Security and Trade Dispute
    1st with CHOAM; timing None)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GainContractCustomAbility::SelectionMode`` @0x4d13ce0: Explicit."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``GainContractCustomAbility::CanRunImmediately`` @0x4d13ba0:
        ``Playmat.RoundPhase == Combat``."""

        return _in_combat_phase(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GainContractCustomAbility::ValueForPlayer`` @0x4d13ed0."""

        return contract_value_for_player(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainContractCustomAbility::Evaluate`` @0x4d13f20 (forced)."""

        return contract_evaluate(p, request, True)


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.ContractAbility"
)
class ContractAbility(DeferredAbility):
    """``ContractAbilities.ContractAbility``: completing a contract (spec §16,
    ``board.md`` §3.4-3.5). Owner = the contract (``Kind.CONTRACT``)."""

    always_run_immediately: ClassVar[bool] = True  # @0x4d54e80

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ContractAbility::SelectionMode`` @0x4d54e70: Explicit."""

        return SelectionMode.EXPLICIT

    def is_immediate_contract(self) -> bool:
        """``IsImmediateContract`` @0x4d54dc0: ``ContractType == Immediate``."""

        return self.owner.attr("ContractType") == "Immediate"

    def resource_value(self, p: Profile) -> Summer:
        """``ContractAbility::GetResourceValue`` @0x4d546f0 (vslot 91).

        Amounts of 0 add 0 (linear prices); ``NegotiateTechValue x
        TechNegotiator`` is Rise of Ix only and absent here.
        """

        v = Summer()
        o = self.owner
        v.add("Contract Water", p.water_value(o.int_attr("Water")))
        v.add("Contract Solari", p.solari_value(o.int_attr("Solari")))
        v.add("Contract Troops", p.troop_value(o.int_attr("Troops"), False))
        return v

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ContractAbility::ValueForPlayer`` @0x4d55250 (no completed check)."""

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if self.is_immediate_contract() or (
            space is not None
            and any(s.ref == space.ref for s in contract_spaces(p, self.owner))
        ):
            v.merge(self.resource_value(p))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ContractAbility::Evaluate`` @0x4d56c40: 100."""

        return Answer(100.0, (), f"Contract {self.owner.ref} | 100")

    # -- SpecificAcquireValue @0x4d55450 (board.md §3.4) ---------------------

    def _round_factor(self, p: Profile) -> float:
        return max((9.0 - p.ctx.round_number) * 0.125, 0.25)

    def reward_value_mod(self, p: Profile) -> float:
        """``RewardValueMod`` @0x4d558e0."""

        kind = self.owner.attr("ContractType")
        c = p.C
        if kind == "Space":
            ratio = c.SpaceContractRewardValueModRatio
        elif kind == "Harvest":
            ratio = c.HarvestContractRewardValueModRatio
        elif kind == "Acquire":
            ratio = c.AcquireContractRewardValueModRatio
        else:
            ratio = 0.0
        return ratio * self.resource_value(p).sum * self._round_factor(p)

    def agent_icons_mod(self, p: Profile) -> float:
        """``AgentIconsMod`` @0x4d55b00.

        Judgement: ``deck_agent_icons()`` is keyed by the app's AgentIcons
        names (archetype ``IconList``/``AgentIcon`` spelling).
        """

        icons = [
            str(s.attr("AgentIcon"))
            for s in contract_spaces(p, self.owner)
            if s.has("Faction")
        ]
        if not icons:
            return 0.0
        deck_icons = p.deck_agent_icons()
        n = sum(deck_icons.get(icon, 0) for icon in icons)
        if n > 2:
            f = 2.0
        elif n == 2:
            f = 0.0
        elif n == 1:
            f = -2.0
        elif n == 0:
            f = -5.0
        else:
            f = 0.0
        return f * p.C.SpaceContractAgentIconsModRatio

    def resource_mod(self, p: Profile) -> float:
        """``ResourceMod`` @0x4d55f10."""

        kind = self.owner.attr("ContractType")
        if kind == "Space":
            ratio = p.C.SpaceContractResourceModRatio
        elif kind == "Harvest":
            ratio = p.C.HarvestContractResourceModRatio
        else:
            ratio = 0.0
        spaces = contract_spaces(p, self.owner)

        def tri(level: int) -> float:
            if level == 0:
                return -3.0
            return 3.0 if level > 0 else 0.0

        r = 0.0
        if any(s.ref in ("sardaukar", "heighliner") for s in spaces):  # b__25_0
            r = tri(p.abundance_level(Attr.SPICE))
        if any(s.ref == "high_council" for s in spaces):  # b__25_1
            r += tri(p.abundance_level(Attr.SOLARI))
        if any(s.ref == "research_station" for s in spaces):  # b__25_2
            r += tri(p.abundance_level(Attr.WATER))
        if any(s.ref == "spice_refinery" for s in spaces):  # b__25_3
            s1 = p.solari_value(1)
            r += -3.0 if 0.5 > s1 else (3.0 if s1 >= 0.9 else 0.0)
        if any(s.has("BonusSpice") for s in spaces):  # b__25_4: maker spaces
            s1 = p.solari_value(1)
            r += -3.0 if 1.25 > s1 else (3.0 if s1 >= 1.8 else 0.0)
        return ratio * r

    def spy_mod(self, p: Profile) -> float:
        """``SpyMod`` @0x4d56800."""

        if any(_observing_spies(p, s.ref) > 0 for s in contract_spaces(p, self.owner)):
            return 2.0 * p.C.SpaceContractSpyModRatio
        return 0.0

    def bonus_spice_mod(self, p: Profile) -> float:
        """``BonusSpiceMod`` @0x4d56960 (runtime ``BonusSpice``)."""

        total = sum(_space_bonus_spice(p, s) for s in contract_spaces(p, self.owner))
        return p.C.HarvestContractBonusSpiceModRatio * 0.33 * total

    def round_mod(self, p: Profile) -> float:
        """``RoundMod`` @0x4d56b90."""

        arc = p.game_arc()
        factor = 3.0 if arc == 2 else (-3.0 if arc == 0 else 0.0)
        return factor * p.C.AcquireContractRoundModRatio

    def specific_acquire_value(self, p: Profile) -> Summer:
        """``ContractAbility::SpecificAcquireValue`` @0x4d55450.

        ``WormContractPlayable::AcquireValue`` (``profile.contract_acquire_value``)
        is this hook of the contract's ``ContractAbility``.
        """

        v = Summer()
        kind = self.owner.attr("ContractType")
        if kind == "Immediate":
            v.add("Immediate RewardValue", self.resource_value(p).sum)
        elif kind == "Space":
            v.add("RewardValueMod", self.reward_value_mod(p))
            v.add("AgentIconsMod", self.agent_icons_mod(p))
            v.add("ResourceMod", self.resource_mod(p))
            v.add("SpyMod", self.spy_mod(p))
        elif kind == "Harvest":
            v.add("RewardValueMod", self.reward_value_mod(p))
            v.add("ResourceMod", self.resource_mod(p))
            v.add("BonusSpiceMod", self.bonus_spice_mod(p))
        elif kind == "Acquire":
            v.add("RewardValueMod", self.reward_value_mod(p))
            seat = 3.0 if p.ctx.me.high_council else -3.0
            v.add("HighCouncilMod", seat * p.C.AcquireContractHighCouncilModRatio)
            v.add("RoundMod", self.round_mod(p))
        return v


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.Draw2ContractAbility"
)
class Draw2ContractAbility(ContractAbility):
    """``ContractAbilities.Draw2ContractAbility`` (ContractBase_6, _12)."""

    always_run_immediately: ClassVar[bool] = False  # @0x4d59230

    def can_run_immediately(self, p: Profile) -> bool:
        """``Draw2ContractAbility::CanRunImmediately`` @0x4d59200:
        ``cp == null or !cp.DeferredThresholdReached()`` (no Reveal test)."""

        if _no_current_player(p):
            return True
        return not deferred_threshold_reached(p)

    def resource_value(self, p: Profile) -> Summer:
        """``Draw2ContractAbility::GetResourceValue`` @0x4d59300.

        Disassembly (corrects both specs): ``addsd xmm0, xmm0`` doubles
        ``CardDrawValue`` and ``lea esi, [rax + rax]`` doubles the persuasion
        passed to ``GetBuyGains``: ``+ 2 x CardDrawValue`` "Draw 2" and
        ``+ GetBuyGains(2 x PossiblePersuasionGain())`` "Buy Gains Bonus".
        """

        v = super().resource_value(p)
        v.add("Draw 2", p.card_draw_value() * 2.0)
        v.add("Buy Gains Bonus", p.buy_gains(2 * p.possible_persuasion_gain()))
        return v


@port(
    "worm.canis.abilities.ActivatedAbilities.Uprising.ContractAbilities.PlaceSpyContractAbility"
)
class PlaceSpyContractAbility(ContractAbility):
    """``ContractAbilities.PlaceSpyContractAbility`` (ContractBase_4, _9)."""

    always_run_immediately: ClassVar[bool] = False  # @0x4d5a1a0; never auto

    def resource_value(self, p: Profile) -> Summer:
        """``PlaceSpyContractAbility::GetResourceValue`` @0x4d5a270."""

        v = super().resource_value(p)
        v.add("Place Spy", p.spy_value().sum)
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PlaceSpyContractAbility::Evaluate`` @0x4d5a300: ``SpyValue`` with
        an empty response (``GetSpyAIResponses`` discarded, not computed)."""

        return Answer(p.spy_value().sum, (), "Place Spy Contract")


# -- conflict-resolution custom rewards --


@port("worm.canis.abilities.ActivatedAbilities.Uprising.Recall2SpiesVPAbility")
class Recall2SpiesVPAbility(DeferredAbility):
    """``Uprising.Recall2SpiesVPAbility`` (Battle for Arrakeen; spec §21)."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``Recall2SpiesVPAbility::SelectionMode`` @0x4d523a0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4d523b0: ``HasCustomAbility`` and
        ``HasAtLeastSpiesOnBoard(2)``.

        Judgement: the custom grant is held exactly while the seat answers our
        ``combat_reward_spy_recall`` frame (after winning the 1st-place
        reward); at placement valuation it is not.
        """

        granted = p.ctx.decision_kind == "combat_reward_spy_recall"
        return granted and _deployed_spies(p) >= 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``Recall2SpiesVPAbility::ValueForPlayer`` @0x4d52650."""

        v = Summer()
        if self.meets_cost(p):
            v.add("Recall 2 Spies", 2 * p.recall_spy_value().sum)
            v.add("VP", p.victory_point_value(1))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``Recall2SpiesVPAbility::Evaluate`` @0x4d52860.

        SPY entities of ``request.infos[0]``; ``GetRecallSpies(spies, 2)``.
        """

        s = Summer()
        s.add("VP", p.victory_point_value(1))
        spies, _ = p.recall_spies(_targets(request, Kind.SPY), 2)
        if len(spies) != 2:
            return Answer(0.0, None, "Recall 2 Spies: not 2")
        s.add("Remove spies", 2 * p.recall_spy_value().sum)
        return Answer(s.sum, (tuple(spy.ref for spy in spies),), "Recall 2 Spies -> VP")

    def possible_conflict_vp(self, p: Profile, double_cost: bool) -> int:
        """``Recall2SpiesVPAbility::GetPossibleConflictVP`` @0x4d52820:
        ``(SpyDeployedCount >= 2) and not double_cost``."""

        return 1 if (_deployed_spies(p) >= 2 and not double_cost) else 0


@port("worm.canis.abilities.ActivatedAbilities.Uprising.BlowWallCustomAbility")
class BlowWallCustomAbility(DeferredAbility):
    """``Uprising.BlowWallCustomAbility`` (Sietch Tabr; spec §22). V = 0."""

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``BlowWallCustomAbility::SelectionMode`` @0x4cee970: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4cee980: ``HasCustomAbility`` then ``Board.HasShieldWall``.

        Our Sietch Tabr destroy-wall option is part of one action; the grant is
        taken as held whenever the AI is asked (judgement).
        """

        return p.ctx.shield_wall_present

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BlowWallCustomAbility::Evaluate`` @0x4ceeba0: always 100."""

        return Answer(100.0, (), "Blow Wall | 100")


# ---------------------------------------------------------------------------
# Space abilities
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.SpaceAbilities.SpaceAbility")
class SpaceAbility(Ability):
    """``SpaceAbilities.SpaceAbility``: the generic board-space value (§6).

    Owner = the space. Subclasses (High Council, Swordmaster, Espionage, …)
    call ``super().value_for_player`` first, as the app does; the High
    Council's two such classes make the app count this base twice (quirk).
    """

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpaceAbility::ValueForPlayer`` @0x4bafaf0 (spec §6.1, board §1.3).

        ``with_entities`` is never read.
        """

        v = Summer()
        c = p.C
        space = self.owner
        leader = _leader_arch_id(p)
        # --- printed gains and costs (space attributes) ---
        sp = space.int_attr("Spice") + _space_bonus_spice(p, space) * c.BonusSpiceMod
        ariana = False
        if sp > 0 and leader == _ARIANA:
            sp += -1.0
            ariana = True
        if sp > 0:
            v.add("Space Spice", sp * p.spice_value(1))  # unit price x amount
        water = space.int_attr("Water")
        if water > 0:
            v.add("Space Water", p.water_value(water))
        solari = space.int_attr("Solari")
        if solari > 0:
            v.add("Space Solari", p.solari_value(solari))
        troops = space.int_attr("Troops")
        if troops > 0:
            v.add("Space Troops", p.troop_value(troops, False))
        spice_cost = space.int_attr("SpiceCost")
        if spice_cost > 0:
            v.add("Space Spice Cost", p.spice_value(-spice_cost))
        water_cost = space.int_attr("WaterCost")
        if water_cost > 0:
            v.add("Space Water Cost", p.water_value(-water_cost))
        # SolariDiscount: a per-turn player-turn attribute no Uprising effect
        # sets (cleared in PlayerTurnPhase Cleanup); 0 here.
        cost = space_solari_cost(p, space) + space.int_attr("SolariDiscount")
        if cost > 0:
            v.add("Space Solari Cost", p.solari_value(-cost))
        if (cost > 0 and leader == _ILBAN) or ariana:  # ``or al, r15b``
            v.add("Leader Ability Card Draw", p.card_draw_value())
            v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        # Baron (needs BaronHarkonnenSecretFactions) and Archduke Armand Ecaz
        # (Rise of Ix) are never dealt in Uprising: no term.
        # --- Uprising block (IsSetEnabled(4) is true) ---
        for contract in _contracts_for_space(p, space):
            completion = _first_contract_ability(contract)
            if completion is not None:
                v.merge(completion.value_for_player(p, (space,)))
                v.add("Want Contract Count", float(p.want_contract_count()))
        r = 0
        occupied = any(seat != p.ctx.seat for seat in p.ctx.space_occupants(space.ref))
        # ``WormSpace::CanInfiltrateWithoutSpy @0x49c1080`` tests Helena Richese
        # (base leader), RoI ``InfiltrationIconList`` cards and the Tleilaxu
        # Infiltrator (Immortality): never true in Uprising.
        if occupied:
            if _deployed_spies(p) < 3:
                v.add(
                    "Recall spy to infiltrate",
                    -(c.SpyInfiltrateBoardSpaceValueMod * p.spy_value().sum),
                )
            else:
                v.add(
                    "Recall spy to infiltrate (3 Spies)",
                    -c.SpaceSpyUseInfiltrate3SpiesMod,
                )
            r = -1
        if _observing_spies(p, space.ref) + r > 0:
            if (
                p.card_draw_value_with_buy_gains() > p.spy_value().sum
                or _deployed_spies(p) >= 3
            ):
                v.add("Spy Gather Intelligence", c.SpaceSpyUseIntelligenceMod)
        if (
            leader == _LADY_JESSICA
            and _leader_flipped(p)
            and space.attr("Faction") in ("BeneGesserit", "Fremen")
        ):
            jessica = _leader(p)
            if jessica is not None:
                for ability in abilities_of(jessica):  # <>c b__14_1 @0x4bb16e0
                    if app_isinstance(ability, _REVEREND_MOTHER_ABILITY):
                        v.merge(ability.value_for_player(p, (space,)))
                        break
        return v


def _contracts_for_space(p: Profile, space: Entity) -> list[Entity]:
    """``WormPlayer::GetContractsForSpace @0x4845050`` (completed ones too)."""

    return [
        contract
        for contract in _contract_area(p)
        if any(s.ref == space.ref for s in contract_spaces(p, contract))
    ]


def _first_contract_ability(contract: Entity) -> ContractAbility | None:
    """``k.Abilities.OfType<ContractAbility>().FirstOrDefault()``."""

    for ability in abilities_of(contract):
        if isinstance(ability, ContractAbility):
            return ability
    return None


# ---------------------------------------------------------------------------
# Triggered abilities
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.TriggeredAbilities.TriggeredAbility")
class TriggeredAbility(Ability):
    """``TriggeredAbilities.TriggeredAbility`` (abstract; never evaluated)."""


@port(
    "worm.canis.abilities.TriggeredAbilities.Uprising.ActivateContractTriggeredAbility"
)
class ActivateContractTriggeredAbility(TriggeredAbility):
    """``TriggeredAbilities.Uprising.ActivateContractTriggeredAbility`` (spec
    §16, §23; 16 contract archetypes): marks a face-up contract claimable when
    its owner sends an Agent to a contract space (``board.md`` §3.1). No AI
    hook: every member is the ``WormAbilityDefinition`` default."""


@port("worm.canis.abilities.TriggeredAbilities.BondAbility")
class BondAbility(TriggeredAbility):
    """``TriggeredAbilities.BondAbility`` (abstract; spec §17).

    Subclasses set ``bond_faction`` (``get_BondFaction``, vslot 89; app faction
    name) and their own V. Bonds trigger only in the Reveal turn.
    """

    bond_faction: ClassVar[str | None] = None  # abstract in the app
    should_exhaust: ClassVar[bool] = False  # @0x4a8ccd0

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``BondAbility::ValueInPileForOtherPlay`` @0x4a8cf40 (does not call
        the default synergy)."""

        s = Summer()
        if (
            pile is Pile.DECK
            and self.bond_faction == "Fremen"
            and "Fremen" in card_factions(card)
            and not p.is_climax()
        ):
            s.add("Fremen in Deck", p.C.SynergyFremenWithBondInDeck)
        return s


# ---------------------------------------------------------------------------
# Conflict rewards
# ---------------------------------------------------------------------------


def conflict_reward(conflict: Entity, place: int) -> Entity:
    """``ConflictExtensions::GetConflictReward @0x4824e70``: the reward
    archetype ``ConflictRewardArchetypes[place - 1]`` of the card."""

    short = conflict.list_attr("ConflictRewardArchetypes")[place - 1]
    return Entity(Kind.CONFLICT, conflict.ref, ARCHETYPES[short], conflict.owner)


def _custom_reward_ability(ability_id_: str, conflict: Entity) -> Ability:
    """The ``pool.FirstOrDefault(a => a.GetAbilityID() == id)`` of
    ``ValueForRewardsFrom``.

    The pool is the playmat's custom abilities followed by the conflict's
    abilities (lookup lambda UNTRACED). Judgement: the playmat holds one
    instance of every custom reward class, so a lookup always finds the class;
    its ``ValueForPlayer`` does not depend on the owner.
    """

    return ability_for(ability_id_, conflict)


#: ``ResourceActions.ResourceNames.Keys`` that exist as ``Attr`` (Water, Spice,
#: Solari, Strength, Persuasion; PossibleStrength and RevealStrength never
#: appear on an Uprising reward).
_REWARD_RESOURCES = (
    Attr.WATER,
    Attr.SPICE,
    Attr.SOLARI,
    Attr.STRENGTH,
    Attr.PERSUASION,
)


def value_for_rewards_from(p: Profile, reward: Entity, conflict: Entity) -> Summer:
    """``WormPlayerAIExtensions::ValueForRewardsFrom`` @0x49a4be0 (spec §18)."""

    v = Summer()
    vp = reward.int_attr("VictoryPoints")
    if vp > 0:
        v.add("VP", p.victory_point_value(vp))
    for attr in _REWARD_RESOURCES:
        n = reward.int_attr(attr.value)
        if n > 0:
            v.add(f"{attr.value} * {n}", p.resource_value(attr, n, False))
    for faction, n in _faction_influence(reward):  # n is not checked for > 0
        v.add(f"{faction} * {n} ", p.gain_influence_value(faction, n, -1, False).sum)
    troops = reward.int_attr("Troops")
    if troops > 0:
        v.add(f"Troop * {troops}", p.troop_value(troops, False))
    intrigue = reward.int_attr("IntrigueCard")
    if intrigue > 0:
        v.add(f"Intrigue * {intrigue}", p.intrigue_value() * intrigue)
    for custom_id in reward.list_attr("CustomAbilityIDs"):
        ability = _custom_reward_ability(custom_id, conflict)
        v.merge(ability.value_for_player(p, ()))
    return v


@port("worm.canis.abilities.ConflictAbilities.ConflictAbility")
class ConflictAbility(Ability):
    """``ConflictAbilities.ConflictAbility`` (abstract). Owner = the card."""

    #: ``WormAttributes.ConflictPlace`` set by the place subclasses' ctors.
    place: ClassVar[int | None] = None

    def possible_reward_vp(self, p: Profile, double_cost: bool) -> int:
        """``ConflictAbility::GetPossibleRewardVP`` @0x4b6ea00:
        ``place == 1 ? owner.VictoryPoints : 0`` (vslot 81)."""

        return self.owner.int_attr("VictoryPoints") if self.place == 1 else 0


@port("worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictAbility")
class GenericConflictAbility(ConflictAbility):
    """``ConflictAbilities.Uprising.GenericConflictAbility`` (abstract)."""

    def _place(self) -> int:
        return self.place if self.place is not None else 1  # ``cmovne``

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GenericConflictAbility::ValueForPlayer`` @0x4b70ff0.

        The battle icon is passed as the archetype's ``BattleIcon`` name
        (``"None"`` when the card has none).
        """

        v = Summer()
        conflict = self.owner
        place = self._place()
        v.merge(value_for_rewards_from(p, conflict_reward(conflict, place), conflict))
        if place == 1:
            v.merge(p.battle_icon_value(str(conflict.attr("BattleIcon", "None"))))
        return v

    def possible_reward_vp(self, p: Profile, double_cost: bool) -> int:
        """``GenericConflictAbility::GetPossibleRewardVP`` @0x4b71240.

        Reward VP plus, for each custom id of the reward, the
        ``GetPossibleConflictVP`` of the first ``DeferredAbility`` of the
        conflict card with that id (others: nothing).
        """

        conflict = self.owner
        reward = conflict_reward(conflict, self._place())
        vp = reward.int_attr("VictoryPoints")
        card_abilities = [
            a for a in abilities_of(conflict) if isinstance(a, DeferredAbility)
        ]
        for custom_id in reward.list_attr("CustomAbilityIDs"):
            for ability in card_abilities:
                if ability_id(ability) == custom_id:
                    vp += ability.possible_conflict_vp(p, double_cost)
                    break
        return vp


@port("worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictFirstAbility")
class GenericConflictFirstAbility(GenericConflictAbility):
    """``GenericConflictFirstAbility`` (ctor @0x4b71fe0: place 1)."""

    place: ClassVar[int | None] = 1


@port("worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictSecondAbility")
class GenericConflictSecondAbility(GenericConflictAbility):
    """``GenericConflictSecondAbility`` (ctor @0x4b72120: place 2)."""

    place: ClassVar[int | None] = 2


@port("worm.canis.abilities.ConflictAbilities.Uprising.GenericConflictThirdAbility")
class GenericConflictThirdAbility(GenericConflictAbility):
    """``GenericConflictThirdAbility`` (ctor @0x4b72260: place 3)."""

    place: ClassVar[int | None] = 3


@port("worm.canis.abilities.ConflictAbilities.Uprising.TakeControlConflictAbility")
class TakeControlConflictAbility(ConflictAbility):
    """``ConflictAbilities.Uprising.TakeControlConflictAbility`` (spec §19)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``TakeControlConflictAbility::ValueForPlayer`` @0x4b73af0.

        Reads the **current** conflict; prices spice control with
        ``ControlSolariValue`` (quirk kept); no test of the controller.
        """

        v = Summer()
        current = p.ctx.current_conflict_id
        if current is None:
            return v
        conflict = conflict_entity(current, p.ctx.choam)
        for arch_id in conflict.list_attr("ReferencedArchetypeIDs"):
            space = find_space(p, arch_id)
            if space is None:
                continue
            if space.has("ControlSolari"):
                v.add("Control Solari", p.control_solari_value())
            elif space.has("ControlSpice"):
                v.add("Control Spice", p.control_solari_value())
        return v


@port("worm.canis.abilities.ConflictAbilities.Uprising.PayAttributeToGainVPAbility")
class PayAttributeToGainVPAbility(DeferredAbility):
    """``ConflictAbilities.Uprising.PayAttributeToGainVPAbility`` (abstract;
    spec §20). The ctor @0x4b72430 sets the cost and the VP."""

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION
    solari_cost: ClassVar[int] = 0
    spice_cost: ClassVar[int] = 0
    victory_points: ClassVar[int] = 1

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``PayAttributeToGainVPAbility::SelectionMode`` @0x4b72c30: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4b72aa0: ``HasCustomAbility`` then ``Solari >=
        SolariCost and Spice >= SpiceCost``.

        Judgement: the grant is held while the seat answers our
        ``combat_reward_optional`` frame.
        """

        me = p.ctx.me
        granted = p.ctx.decision_kind == "combat_reward_optional"
        return (
            granted
            and me.resources.solari >= self.solari_cost
            and me.resources.spice >= self.spice_cost
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PayAttributeToGainVPAbility::ValueForPlayer`` @0x4b72e10.

        The VP counts even when the cost is unaffordable now (quirk kept).
        """

        v = Summer()
        me = p.ctx.me
        cost = self.solari_cost
        if cost > 0 and me.resources.solari >= cost:
            v.add(f"{cost} solari cost", p.solari_value(-cost))
        cost = self.spice_cost
        if cost > 0 and me.resources.spice >= cost:
            v.add(f"{cost} spice cost", p.spice_value(-cost))
        v.add("VP", p.victory_point_value(self.victory_points))
        return v

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PayAttributeToGainVPAbility::Evaluate`` @0x4b73250: always 100."""

        return Answer(100.0, (), "Pay To Gain VP | always play")

    def possible_conflict_vp(self, p: Profile, double_cost: bool) -> int:
        """``PayAttributeToGainVPAbility::GetPossibleConflictVP`` @0x4b72d20:
        ``Spice >= SpiceCost << d and Solari >= SolariCost << d``."""

        me = p.ctx.me
        shift = 1 if double_cost else 0
        if me.resources.spice < self.spice_cost << shift:
            return 0
        return 1 if me.resources.solari >= self.solari_cost << shift else 0


@port("worm.canis.abilities.ConflictAbilities.Uprising.Pay3SpiceToGain1VPAbility")
class Pay3SpiceToGain1VPAbility(PayAttributeToGainVPAbility):
    """``Pay3SpiceToGain1VPAbility`` (ctor @0x4b723a0: Spice 3, 1 VP;
    Spice Freighters)."""

    spice_cost: ClassVar[int] = 3


@port("worm.canis.abilities.ConflictAbilities.Uprising.Pay4SpiceToGain1VPAbility")
class Pay4SpiceToGain1VPAbility(PayAttributeToGainVPAbility):
    """``Pay4SpiceToGain1VPAbility`` (ctor @0x4b727f0: Spice 4, 1 VP; Battle
    for Imperial Basin)."""

    spice_cost: ClassVar[int] = 4


@port("worm.canis.abilities.ConflictAbilities.Uprising.Pay6SolariToGain1VPAbility")
class Pay6SolariToGain1VPAbility(PayAttributeToGainVPAbility):
    """``Pay6SolariToGain1VPAbility`` (ctor @0x4b72970: Solari 6, 1 VP; Battle
    for Spice Refinery)."""

    solari_cost: ClassVar[int] = 6
