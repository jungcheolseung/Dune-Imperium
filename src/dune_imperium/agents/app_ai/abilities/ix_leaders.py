"""Rise of Ix's leader abilities (``LeaderArchetypes.RiseOfIx``).

Ports of the 12 ability classes of five Rise of Ix leaders (Archduke Armand
Ecaz, Ilesa Ecaz, Prince Rhombur Vernius, "Princess" Yuna Moritani,
Viscount Hundro Moritani), read from the P6 Ix decompilation (assets
``ghidra/p6ix/<addr>.c``, index ``ghidra/p6ix/targets-named.tsv``) and
confirmed in the annotated disassembly
(``dump/asm/worm-canis.dll/worm.canis.abilities.<ActivatedAbilities|
TriggeredAbilities|PlayAbilities>.RiseOfIx.<Class>.asm``). Rhombur's signet
``IxianTechnologyAbility`` is in ``abilities/tech.py``; Tessia Vernius is not
ported here.

App class chains (``dump/worm-canis.dll.cs``):

- ``ActivatedAbilities.SignetAbility`` <- ``RiseOfIx.ConscriptAbility``,
  ``GuildContactsAbility``, ``FinalDeliveryAbility``, ``CouriersAbility``;
- ``ActivatedAbilities.DeferredAbility`` <- ``RiseOfIx.CoordinationAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <-
  ``TriggeredAbilities.RiseOfIx.OneStepAheadRoundAbility``,
  ``OneStepAheadTurnAbility``, ``OneStepAheadSendAbility``,
  ``HeavyLasgunCannonsAbility``, ``IntelligenceAbility`` and
  ``PlayAbilities.RiseOfIx.SmugglingOperationSolariAbility``,
  ``SmugglingOperationWaterAbility`` (two ``TriggeredAbility`` subclasses
  despite their namespace).

How a leader ability reaches the AI is as in ``abilities/leaders.py``: a
Signet's ``value_for_player`` is merged into a placement of a card with
signet icons; ``evaluate`` answers the prompt of a deferred ability. Two
triggered abilities have an AI member: ``OneStepAheadRoundAbility`` overrides
``Evaluate`` (the set-aside pick) and ``IntelligenceAbility`` hands
``EvaluateIntrigue`` to its ``KeepIntrigueCard`` picker
(``evaluate_intrigue``, as ``ImperiumCeremonyAbility`` in
``abilities/immortality.py``); the other five have none and are bare ports
so that the leaders' abilities all resolve.

Request / answer encoding (``request.infos[i]`` is the app's target
information ``i``; answers follow ``abilities/intrigue.py``'s ``_Choice``:
``Answer.response is None`` = nothing stored, value 0):

- Coordination: ``infos[0]`` the CARDs in play (``P.AllCardsInPlay``, kind
  ``SelectTrashCard``, max 1, min 0, not forced; ``<Targets>d__5`` yields no
  info when nothing is in play); the answer is ``((card,),)``, or ``((),)``
  (trash nothing) at ``GetCardToTrash``'s value when no card qualifies.
- Conscript: ``infos[0]`` the Imperium Row then Reserve CARDs of
  ``PersuasionCost <= 3`` (``MakeAcquireImperiumRowCardTargeting(maxCost 3,
  includeReserved, includeCanTopOfDeck)``), ``infos[1]`` the destination
  picker; the answer is ``((card,), (0,))`` (option 0 of the picker, as
  Chronicler's Insight in ``abilities/leaders.py``).
- Guild Contacts: ``infos[0].options`` the destinations of the Foldspace
  (``<Targets>d__8``: "deck" only when ``GetAcquireArchIDAndPickerKind``
  allows it, then "discard"); the answer is ``((0,),)`` (option 0).
- Final Delivery: ``infos[0]`` the faction TRACKs
  (``MakeGainAnyFactionInfluenceTargeting``); the answer is ``((track,),)``.
- Couriers: no entity target; the answer is the Freighter's
  ``IntTargetResponse`` ``((item1,),)`` (1 = recall, 0 = advance;
  ``abilities/ix_board.FREIGHTER_RECALL``).
- One Step Ahead (round): ``infos[0]`` the hand CARDs (kind ``KeepCard``,
  forced, max 1); the answer is ``((card,),)``, the card set aside.
- Intelligence (``evaluate_intrigue``): ``infos[0]`` the two INTRIGUE cards
  drawn (kind ``KeepIntrigueCard``); the answer is ``((card,),)``, the card
  kept.

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    AgentAbility,
    DeferredAbility,
    TriggeredAbility,
    collect_first,
)
from dune_imperium.agents.app_ai.abilities.intrigue import _Choice, _targets
from dune_imperium.agents.app_ai.abilities.leaders import (
    SignetAbility,
    _in_reveal_turn,
)
from dune_imperium.agents.app_ai.abilities.original_board import (
    foldspace_in_reserve,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    is_board_space,
    space_entity,
    swordmaster_space_id,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA: Final = "worm.canis.abilities.ActivatedAbilities.RiseOfIx."
_TA: Final = "worm.canis.abilities.TriggeredAbilities.RiseOfIx."
_PA: Final = "worm.canis.abilities.PlayAbilities.RiseOfIx."

#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``).
_ANY_FACTION: Final = "none"
#: ``ImperiumArchetypes.BaseSet.FoldspaceImperium.archID``.
_FOLDSPACE: Final = "ImperiumArchetypes.BaseSet.FoldspaceImperium"
#: ``AgentIcons`` Circle (1), Triangle (2), Pentagon (3): the City, Spice
#: Trade and Landsraad icons ``HasTwoPCTAgents`` counts (our ``AgentIcon``
#: spelling).
_PCT_ICONS: Final = frozenset({"Pentagon", "Circle", "Triangle"})
#: ``f64=100.0`` (0x520cfc0): Guild Contacts' and One Step Ahead's value.
_HUNDRED: Final = 100.0


def _cost_label(name: str, space: Entity) -> str:
    """The ``DebugOnlyStringInterpolationHandler`` label of the 0.0 term a
    signet adds when the space's own cost leaves too little to pay it."""

    return f"{name} Ability cost cannot be paid in addition to {space.ref} cost"


# ---------------------------------------------------------------------------
# Archduke Armand Ecaz: Coordination and Conscript
# ---------------------------------------------------------------------------


def has_two_pct_agents(p: Profile) -> bool:
    """``CoordinationAbility::HasTwoPCTAgents`` @0x4da4cd0.

    ``Playmat.Board.Descendents.OfType<WormAgent>().Where(b__0).Count() > 1``
    (``cmp; setg`` on ``1 < count``) with ``b__0`` @0x4da5210: the Agent's
    owner is the player, its parent is a ``WormSpace``, and the space's
    ``ActionIcon`` is 3, 1 or 2 (Pentagon, Circle, Triangle: the Landsraad,
    City and Spice Trade spaces). A player without the ``Swordmaster``
    attribute (``isSwordmaster == 0``, 0x4da528a) does not count an Agent on
    the Swordmaster space (``IsSwordmasterSpace``, ``jne`` -> false). Ours:
    the seat's ``agent_locations`` on board spaces; ``swordmaster_acquired``
    is the attribute.
    """

    me = p.ctx.me
    board = p.ctx.board
    swordmaster = swordmaster_space_id(board)
    count = 0
    for space_id in me.agent_locations:
        if not is_board_space(space_id):
            continue
        if not me.swordmaster_acquired and space_id == swordmaster:
            continue
        if space_entity(space_id, board).attr("AgentIcon") in _PCT_ICONS:
            count += 1
    return count > 1


@port(_AA + "CoordinationAbility")
class CoordinationAbility(DeferredAbility):
    """``RiseOfIx.CoordinationAbility`` (Archduke Armand Ecaz: in the Reveal
    turn, with two or more Agents on Landsraad, City or Spice Trade spaces,
    trash a card in play).

    ``.ctor @0x4da4990``: ``AbilityTiming = 2`` (``mov esi, 2``, 0x4da4a60),
    ``HideInvalidDeferred = true``, button text ``generic.trash.inplay``. No
    ``ValueForPlayer`` override (the empty base).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CoordinationAbility::SelectionMode`` @0x4da4e90: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4da4b90: a ``BoolAction`` that the context target is
        a ``WormPlayer`` in its Reveal turn (``IsInPlayerTurn(2)``,
        ``mov esi, 2``) and ``HasTwoPCTAgents``."""

        return _in_reveal_turn(p) and has_two_pct_agents(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CoordinationAbility::Evaluate`` @0x4da4f60.

        ``(card, value) = GetCardToTrash(GetTargets(0).OfType<
        WormImperiumPlayable>(), 1.0)`` (``f64=1.0`` @0x4da5025), then
        ``UpdateSelectionTargets(value, src, card ? [card.ID] :
        Array.Empty)``: without a junk card the AI uses the ability at 1.0
        and trashes nothing (``((),)``), as ``TrashAbility::Evaluate``.
        """

        choice = _Choice()
        card, value = p.card_to_trash(_targets(request, 0, Kind.CARD), 1.0)
        choice.update_targets(value, () if card is None else (card.ref,))
        label = "nothing" if card is None else card.ref
        return choice.answer(f"Coordination | trash {label}")


#: ``GetConscriptTargets``' ``PersuasionCost`` limit (``cmp eax, 3; jle``,
#: 0x4da2225) and ``Evaluate``'s (``cmp eax, 3; jg``, 0x4da1b2b).
_CONSCRIPT_MAX_COST: Final = 3


def conscript_targets(p: Profile) -> list[Entity]:
    """``ConscriptAbility::GetConscriptTargets`` @0x4da1290.

    ``ImperiumRowCards(M).Concat(ReserveRowCards(M, true).Where(b__10_0))
    .OfType<WormImperiumPlayable>().Where(b__1)``: the Row in order, then the
    Reserve without Foldspace (``b__10_0`` @0x4da20a0: ``ArchID !=
    FoldspaceImperium``), each kept when its archetype's ``PersuasionCost``
    (default 99, ``mov edx, 0x63``) is at most 3 (``jle``) and none of its
    factions is in the player's ``FactionsBlocked`` (``b__1`` @0x4da2110;
    ``b__2`` @0x4da22e0). Judgement: ``FactionsBlocked`` is set only by the
    app's Challenge mode (``TriggeredAbilities.Challenge.FactionBlock``),
    which our engine has not. The Reserve holds one entity per non-empty pile
    (``reserve:<card_id>``), in our ``reserve_stacks`` order, with Market
    Opening's discount when Arrakeen Scouts is on (as ``abilities/
    imperium_b``).
    """

    cards = [card_entity(instance_id) for instance_id in p.ctx.imperium_row]
    for reserve_id, count in p.ctx.reserve_stacks:
        if count <= 0:
            continue
        card = card_entity(f"reserve:{reserve_id}")
        if card.short == _FOLDSPACE:
            continue
        if p.ctx.scouts:  # Market Opening's discount (plan §11.8)
            card = p.market_opening_reserve_card(card)
        cards.append(card)
    return [
        card
        for card in cards
        if card.int_attr("PersuasionCost", 99) <= _CONSCRIPT_MAX_COST
    ]


@port(_AA + "ConscriptAbility")
class ConscriptAbility(SignetAbility):
    """``RiseOfIx.ConscriptAbility`` (Archduke Armand Ecaz's signet: acquire
    a card that costs 3 or less).

    ``.ctor @0x4da0e50``: ``WillClearUndo = true``, ``PlaceSpyNoUndo =
    true``; no ``Cost`` override (``SignetAbility::Cost`` = ``HasSignet``).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ConscriptAbility::SelectionMode`` @0x4da1160: Optional (0)."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ConscriptAbility::ValueForPlayer`` @0x4da1500.

        The base summer, then, when ``GetConscriptTargets`` is not empty
        (``Any``): the largest ``AcquireValue(P)`` among them
        (``Enumerable.Max`` of the summers, ``b__0`` @0x4da2340; its ``Sum``
        @+0x18) as "Conscript Acquire Value", and before the Late arc
        (``GetGameArc() > 1`` skips, ``cmp eax, 1; jg``)
        ``ConscriptBeforeLateValue`` as "Conscript Before Late Game". No
        targets: nothing.
        """

        s = Summer()
        targets = conscript_targets(p)
        if not targets:
            return s
        s.add(
            "Conscript Acquire Value",
            max(p.acquire_value(card).sum for card in targets),
        )
        if p.game_arc() <= 1:
            s.add("Conscript Before Late Game", p.C.ConscriptBeforeLateValue)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ConscriptAbility::Evaluate`` @0x4da17e0.

        For each target card (``GetTargets(0).OfType<WormImperiumPlayable>``,
        in order) whose ``PersuasionCost`` (default 0, ``xor edx, edx``) is at
        most 3 (``cmp eax, 3; jg`` skips): its ``AcquireValue(P)`` plus,
        before the Late arc (``cmp eax, 1; jg`` skips),
        ``ConscriptBeforeLateValue`` ("Conscript Before Late Game"), stored
        with ``UpdateSelectionResponses(sum, src, [EntityList([card]),
        Int(0)])`` (strictly better replaces).
        """

        choice = _Choice()
        early = p.game_arc() <= 1
        for card in _targets(request, 0, Kind.CARD):
            if card.int_attr("PersuasionCost") > _CONSCRIPT_MAX_COST:
                continue
            v = p.acquire_value(card)
            if early:
                v.add("Conscript Before Late Game", p.C.ConscriptBeforeLateValue)
            choice.update_responses(v.sum, ((card.ref,), (0,)))
        return choice.answer("Conscript | acquire")


# ---------------------------------------------------------------------------
# Ilesa Ecaz: Guild Contacts and One Step Ahead
# ---------------------------------------------------------------------------


@port(_AA + "GuildContactsAbility")
class GuildContactsAbility(SignetAbility):
    """``RiseOfIx.GuildContactsAbility`` (Ilesa Ecaz's signet: pay a Solari
    for a Foldspace card). ``.ctor @0x4dbdd20``: signet button text only."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildContactsAbility::SelectionMode`` @0x4dbdfe0: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4dbdda0: ``SignetAbility::Cost``, then
        ``HasResources.AtLeast(Solari, 1)`` (``mov esi, 1``), then a
        ``BoolAction`` that ``ReserveRowCards(M, true)`` holds a Foldspace
        (``b__6_0`` @0x4dbe7b0: ``ArchID == FoldspaceImperium``)."""

        return (
            super().meets_cost(p)
            and p.ctx.me.resources.solari >= 1
            and foldspace_in_reserve(p)
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildContactsAbility::ValueForPlayer`` @0x4dbe1d0.

        A space in ``with_entities`` (``ListUtil.CollectFirst<WormSpace>``)
        that leaves no Solari for the signet after its own cost
        (``CanAgentAbilityBePlayedWithSpace(space, Solari, 1)`` false) adds
        0.0 (``xorps``) with the debug label and returns. Otherwise
        ``GetSolariValue(-1)`` ("Guild Contacts Solari Cost", ``mov esi,
        0xffffffff``) and ``FoldspaceValue`` ("Foldspace Gain"); neither the
        Solari nor the Reserve is checked here.
        """

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SOLARI, 1
        ):
            s.add(_cost_label("Guild Contacts", space), 0.0)
            return s
        s.add("Guild Contacts Solari Cost", p.solari_value(-1))
        s.add("Foldspace Gain", p.foldspace_value())
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GuildContactsAbility::Evaluate`` @0x4dbe4f0.

        Nothing in the Late arc (``GetGameArc() > 1``, ``cmp eax, 1; jg``)
        or at the climax (``get_IsClimax``); otherwise
        ``UpdateSelectionResponses(100.0, src, [IntTargetResponse(0)])``
        (``f64=100.0`` @0x4dbe666; log "Guild Contacts | 100").
        """

        choice = _Choice()
        if p.game_arc() > 1 or p.is_climax():
            return choice.answer("Guild Contacts")
        choice.update_responses(_HUNDRED, ((0,),))
        return choice.answer("Guild Contacts | 100")


def _agent_box_value(p: Profile, card: Entity) -> float:
    """``OneStepAheadRoundAbility/<>c__DisplayClass11_0::<Evaluate>b__0``
    @0x4b011b0: ``card.Abilities.OfType<AgentAbility>().FirstOrDefault()``,
    its ``ValueForPlayer(context.Player, Array.Empty)`` (vslot 64) ``Sum``
    (@+0x18), or 0.0 (``xorps``) without an Agent box."""

    for ability in abilities_of(card):
        if isinstance(ability, AgentAbility):
            return ability.value_for_player(p, ()).sum
    return 0.0


def _descending_key(value: float) -> tuple[bool, float]:
    """``OrderByDescending``'s ``Comparer<double>.Default``: NaN sorts below
    every number (``double.CompareTo``), so it comes last; equal keys keep
    their order (a stable sort)."""

    if math.isnan(value):
        return (False, 0.0)
    return (True, value)


@port(_TA + "OneStepAheadRoundAbility")
class OneStepAheadRoundAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadRoundAbility`` (Ilesa Ecaz: set a hand card
    aside at the round start; ``IsValidFor`` fires on
    ``Events.RoundSetupFinishedIlesa``).

    ``.ctor @0x4b00870`` stores no timing; ``Cost @0x4b00a50`` = NoCost.
    ``<Targets>d__7`` @0x4b01d90 lists the hand (kind ``KeepCard``, forced,
    max 1; a human with one card gets no target).
    """

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OneStepAheadRoundAbility::Evaluate`` @0x4b00ba0.

        The hand targets (``OfType<WormImperiumPlayable>``) sorted by the
        value of their Agent box, highest first (``OrderByDescending(b__0)
        .ToList()``). Set aside the first of the top three (``Take(3)``, ``mov
        esi, 3``) that shows exactly one Agent icon (``b__11_1`` @0x4b01160:
        ``IconList.Count == 1``). Without one, ``GetBestOption(sorted)``'s
        card (``original_intrigue.best_option``) is removed from the sorted
        list (``List.Remove``) and its first card is set aside; an empty list
        stores nothing. The pick is ``UpdateSelectionTargets(100.0, src,
        [card.ID])`` (``f64=100.0`` @0x4b01018).
        """

        from dune_imperium.agents.app_ai.abilities.original_intrigue import (
            best_option,
        )

        choice = _Choice()
        hand = _targets(request, 0, Kind.CARD)
        ordered = sorted(
            hand,
            key=lambda card: _descending_key(_agent_box_value(p, card)),
            reverse=True,
        )
        pick = next(
            (card for card in ordered[:3] if len(card.list_attr("IconList")) == 1),
            None,
        )
        if pick is None:
            best, _space, _value = best_option(p, ordered)
            if best is not None and best in ordered:
                ordered.remove(best)
            if not ordered:
                return choice.answer("One Step Ahead")
            pick = ordered[0]
        choice.update_targets(_HUNDRED, (pick.ref,))
        return choice.answer(f"One Step Ahead | Setting aside: {pick.ref}")


@port(_TA + "OneStepAheadTurnAbility")
class OneStepAheadTurnAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadTurnAbility`` (Ilesa Ecaz: the set-aside card
    returns to the hand at the start of the round's second turn;
    ``IsValidFor`` fires on ``Events.TurnStarted``). ``.ctor @0x4b03dd0``
    stores no timing; ``Cost @0x4b03ef0`` = NoCost; no AI hook."""


@port(_TA + "OneStepAheadSendAbility")
class OneStepAheadSendAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadSendAbility`` (Ilesa Ecaz: sending an Agent
    with the returned card that turn gives a spice when it shows exactly one
    Agent icon, else a Solari; ``IsValidFor`` fires on
    ``Events.ImperiumPlayed`` in the Agent turn, ``IsInPlayerTurn(1)``).
    ``get_ShouldExhaust`` @0x4b02280 = false; ``Cost @0x4b02290`` = NoCost;
    no AI hook."""

    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Prince Rhombur Vernius: Heavy Lasgun Cannons
# ---------------------------------------------------------------------------


@port(_TA + "HeavyLasgunCannonsAbility")
class HeavyLasgunCannonsAbility(TriggeredAbility):
    """``RiseOfIx.HeavyLasgunCannonsAbility`` (Prince Rhombur Vernius: his
    dreadnoughts have strength 4). On ``Events.GameStarted`` the
    ``<BeginExecution>d__7`` sets ``Strength`` to 4 (``mov esi, 4``) on the
    player's dreadnoughts (``OfType<WormDreadnought>``). ``.ctor @0x4ada210``
    stores no timing; ``Cost @0x4ada330`` = NoCost; no AI hook."""


# ---------------------------------------------------------------------------
# "Princess" Yuna Moritani: Final Delivery and Smuggling Operation
# ---------------------------------------------------------------------------


@port(_AA + "FinalDeliveryAbility")
class FinalDeliveryAbility(SignetAbility):
    """``RiseOfIx.FinalDeliveryAbility`` (Yuna Moritani's signet: pay 7
    Solari for one Influence, a troop and a spice). ``.ctor @0x4db41e0``:
    signet button text only."""

    #: ``HasResources.AtLeast(Solari, 7)`` (``Cost``) and
    #: ``CanAgentAbilityBePlayedWithSpace(space, Solari, 7)`` (``mov ecx, 7``).
    SOLARI_COST: ClassVar[int] = 7

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FinalDeliveryAbility::SelectionMode`` @0x4db43b0: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4db4300: ``SignetAbility::Cost`` then
        ``HasResources.AtLeast(Solari, 7)``."""

        return super().meets_cost(p) and p.ctx.me.resources.solari >= self.SOLARI_COST

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FinalDeliveryAbility::ValueForPlayer`` @0x4db4580.

        A space in ``with_entities`` that leaves fewer than 7 Solari after its
        own cost (``CanAgentAbilityBePlayedWithSpace(space, Solari, 7)``
        false) adds 0.0 with the debug label and returns. Otherwise
        ``GetSolariValue(-7)`` ("Final Delivery -7 Solari", ``mov esi,
        0xfffffff9``), ``GetSpiceValue(1)`` ("Final Delivery Spice"),
        ``GetTroopValue(1, false)`` ("Final Delivery Troop") and
        ``GetGainInfluenceValue(None, 1, -1, false).Sum`` ("Final Delivery
        Influence"). The Solari held are not checked here.
        """

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SOLARI, self.SOLARI_COST
        ):
            s.add(_cost_label("Final Delivery", space), 0.0)
            return s
        s.add("Final Delivery -7 Solari", p.solari_value(-self.SOLARI_COST))
        s.add("Final Delivery Spice", p.spice_value(1))
        s.add("Final Delivery Troop", p.troop_value(1, False))
        s.add(
            "Final Delivery Influence",
            p.gain_influence_value(_ANY_FACTION, 1, -1, False).sum,
        )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FinalDeliveryAbility::Evaluate`` @0x4db4940.

        A ``DefaultValueSummer`` of ``GetSolariValue(-7)``,
        ``GetSpiceValue(1)`` and ``GetTroopValue(1, false)`` is built
        (0x4db4a70-0x4db4b28) but never read: each offered track
        (``OfType<WormFactionTrack>``) is stored at
        ``GetGainInfluenceValue(track.Faction, 1, -1, false).Sum`` alone
        (``movsd xmm0, [r14+0x18]`` of the influence summer, 0x4db4dd3) with
        ``UpdateSelectionTargets`` (strictly better replaces). No threshold.
        """

        choice = _Choice()
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            choice.update_targets(g.sum, (track.ref,))
        return choice.answer("Final Delivery")


@port(_PA + "SmugglingOperationSolariAbility")
class SmugglingOperationSolariAbility(TriggeredAbility):
    """``PlayAbilities.RiseOfIx.SmugglingOperationSolariAbility`` (Yuna
    Moritani: one more Solari whenever she gains Solari on her turn). On
    ``Events.GameStarted`` it installs ``MakeResourceMod`` @0x4c029d0
    (``Solari`` +1, ``DuringPlayerTurn``, permanent). ``.ctor @0x4c02ae0``
    stores no timing; ``get_ShouldExhaust`` @0x4c02c00 = false; ``Cost
    @0x4c02c10`` = NoCost; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_PA + "SmugglingOperationWaterAbility")
class SmugglingOperationWaterAbility(TriggeredAbility):
    """``PlayAbilities.RiseOfIx.SmugglingOperationWaterAbility`` (Yuna
    Moritani: she starts without water). On ``Events.GameStarted``
    ``<BeginExecution>d__9`` pays all her water (``PayWater(P.Water)``).
    ``.ctor @0x4c03550`` stores ``AbilityTiming = 2`` (``mov esi, 2``,
    0x4c035fa); ``get_ShouldExhaust`` @0x4c03700 = false; ``Cost
    @0x4c03710`` = NoCost; no AI hook."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Viscount Hundro Moritani: Couriers and Intelligence
# ---------------------------------------------------------------------------


@port(_AA + "CouriersAbility")
class CouriersAbility(SignetAbility):
    """``RiseOfIx.CouriersAbility`` (Hundro Moritani's signet: pay a spice to
    move the Freighter). ``.ctor @0x4da5d00``: button text only."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CouriersAbility::SelectionMode`` @0x4da5ee0: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4da5e30: ``SignetAbility::Cost`` then
        ``HasResources.AtLeast(Spice, 1)``."""

        return super().meets_cost(p) and p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CouriersAbility::ValueForPlayer`` @0x4da6010.

        A space in ``with_entities`` that leaves no spice after its own cost
        (``CanAgentAbilityBePlayedWithSpace(space, Spice, 1)`` false) adds 0.0
        with the debug label and returns. Otherwise ``-GetSpiceValue(1)``
        ("Couriers -1 Spice": the value of +1 negated, ``xorps`` with the
        sign mask at 0x520ce10) and ``FreighterValue`` ("Couriers
        Freighter").
        """

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 1
        ):
            s.add(_cost_label("Couriers", space), 0.0)
            return s
        s.add("Couriers -1 Spice", -p.spice_value(1))
        s.add("Couriers Freighter", p.freighter_value())
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CouriersAbility::Evaluate`` @0x4da6330: ``sel =
        GetFreighterSelections(-1)`` (``mov esi, 0xffffffff``), then
        ``UpdateSelectionResponses(FreighterValue, src,
        [IntTargetResponse(sel.Item1)])`` (log "Recall" for a nonzero
        ``Item1``, else "Advance"), as ``FreighterAbility::Evaluate``."""

        choice = _Choice()
        recall, _item2, log = p.freighter_selections(-1)
        verb = "Advance" if recall == 0 else "Recall"
        choice.update_responses(p.freighter_value(), ((recall,),))
        return choice.answer(f"Couriers | {verb} | {log}")


@port(_TA + "IntelligenceAbility")
class IntelligenceAbility(TriggeredAbility):
    """``RiseOfIx.IntelligenceAbility`` (Hundro Moritani: at the game start
    look at the top two Intrigue cards, keep one and put the other back on
    top; ``IsValidFor`` fires on ``Events.LeaderSetupHundro``).

    ``.ctor @0x4afdf60`` stores no timing; ``Cost @0x4afe080`` = NoCost. No
    ``Evaluate`` override: ``<BeginExecution>d__8`` decorates its
    ``KeepIntrigueCard`` picker with ``EvaluateIntrigue``
    (``AIEvaluateSelection``, 0x4aff409).
    """

    def evaluate_intrigue(self, p: Profile, request: Request) -> Answer:
        """``IntelligenceAbility::EvaluateIntrigue`` @0x4afe230.

        Each offered card (``GetTargets(0).OfType<WormIntriguePlayable>``)
        is stored at its ``Rating`` (``GetAttributeValue<int>(Rating, 0)``,
        ``cvtsi2sd``) with ``UpdateSelectionTargets`` (the first sticks, a
        later one only when strictly higher): the highest-rated card is kept.
        """

        choice = _Choice()
        for card in _targets(request, 0, Kind.INTRIGUE):
            choice.update_targets(float(card.int_attr("Rating")), (card.ref,))
        return choice.answer("Intelligence | keep Intrigue")
