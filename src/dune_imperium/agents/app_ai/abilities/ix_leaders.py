"""Rise of Ix's leader abilities.

Ports of the 20 ability classes of the six Rise of Ix leaders (Archduke Armand Ecaz,
Ilesa Ecaz, Prince Rhombur Vernius, "Princess" Yuna Moritani, Tessia Vernius, Viscount
Hundro Moritani) and of Tessia's abstract ``CarefulObservationFactionAbility``; each
follows the app's AI for that class, and the detailed notes are kept privately
(``docs/app-ai-plan.md`` §13). Rhombur's signet ``IxianTechnologyAbility`` is in
``abilities/tech.py``.

App class chains:

- ``ActivatedAbilities.SignetAbility`` <- ``RiseOfIx.ConscriptAbility``,
  ``GuildContactsAbility``, ``FinalDeliveryAbility``, ``CouriersAbility`` and
  ``ability.activated.original.duplicity`` (Tessia's signet, despite
  its namespace);
- ``ActivatedAbilities.DeferredAbility`` <- ``RiseOfIx.CoordinationAbility``,
  ``RiseOfIx.CarefulObservationFactionAbility`` (abstract) <-
  ``CarefulObservationEmperorAbility``, ``SpacingGuildAbility``,
  ``BeneGesseritAbility``, ``FremenAbility`` (each only overrides
  ``SnooperFaction`` and its constructors);
- ``TriggeredAbilities.TriggeredAbility`` <-
  ``ability.triggered.ix.one_step_ahead_round``,
  ``OneStepAheadTurnAbility``, ``OneStepAheadSendAbility``,
  ``HeavyLasgunCannonsAbility``, ``IntelligenceAbility``,
  ``CarefulObeservationSetupAbility`` (the app's spelling) and
  ``ability.play.ix.smuggling_operation_solari``,
  ``SmugglingOperationWaterAbility``, ``CarefulObservationTriggeredAbility``,
  ``CarefulObservationOppTriggeredAbility`` (four ``TriggeredAbility``
  subclasses despite their namespace).

How a leader ability reaches the AI is as in ``abilities/leaders.py``: a
Signet's ``value_for_player`` is merged into a placement of a card with
signet icons; ``evaluate`` answers the prompt of a deferred ability. Two
triggered abilities have an AI member: ``OneStepAheadRoundAbility`` overrides
``Evaluate`` (the set-aside pick) and ``IntelligenceAbility`` hands
``EvaluateIntrigue`` to its ``KeepIntrigueCard`` picker
(``evaluate_intrigue``, as ``ImperiumCeremonyAbility`` in
``abilities/immortality.py``); the other eight have none and are bare ports
so that the leaders' abilities all resolve.

Tessia Vernius' Careful Observation in the app: the setup trigger puts the
four Factions in her Leader's ``SnooperFactions``; reaching a token in her
own turn (``CarefulObservationTriggeredAbility``) or in another seat's
(``...OppTriggeredAbility``, which then runs it at once) removes the track
from that list and grants the track's ``CarefulObservation<Faction>Ability``
as a custom ability. That deferred ability pays the reward when it runs: it
adds its track to ``SnooperFactionsUsed`` and pays by the list's new count
(1: discard -> 1 spice; 2 and 4: the track's 4-space bonus; 3 and 4: one
Influence on it), so the app numbers the rewards by the order the abilities
run. Ours numbers them by the order the tokens are reached and pays (2)-(4)
at once (``rules.influence._reach_snooper``); only reward (1) waits for a
decision (``rules.snoopers``), and that is the only prompt the faction
classes answer.

Request / answer encoding (``request.infos[i]`` is the app's target
information ``i``; answers follow ``abilities/intrigue.py``'s ``_Choice``:
``Answer.response is None`` = nothing stored, value 0):

- Coordination: ``infos[0]`` the CARDs in play (``P.AllCardsInPlay``, kind
  ``SelectTrashCard``, max 1, min 0, not forced; ``Targets`` yields no
  info when nothing is in play); the answer is ``((card,),)``, or ``((),)``
  (trash nothing) at ``GetCardToTrash``'s value when no card qualifies.
- Conscript: ``infos[0]`` the Imperium Row then Reserve CARDs of
  ``PersuasionCost <= 3`` (``MakeAcquireImperiumRowCardTargeting(maxCost 3,
  includeReserved, includeCanTopOfDeck)``), ``infos[1]`` the destination
  picker; the answer is ``((card,), (0,))`` (option 0 of the picker, as
  Chronicler's Insight in ``abilities/leaders.py``).
- Guild Contacts: ``infos[0].options`` the destinations of the Foldspace
  (``Targets``: "deck" only when ``GetAcquireArchIDAndPickerKind``
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
- Careful Observation (``CarefulObservation<Faction>Ability.evaluate``, the
  class of the track whose token was reached): ``infos[0]`` the hand CARDs
  (``Targets``: kind ``DiscardCard``, max 1; in her own
  turn min 1 and not forced, outside it min 0 and forced,
  ``IsOpponentTurn``). The app yields no information once a Snooper reward
  has run (``SnooperFactionsUsed.Any()``) and, for a human only, with an
  empty hand. Every answer is worth 1.0: ``((card,),)`` discards that card
  for the spice; ``((),)`` (``Array.Empty``) discards nothing (Discard +
  Spice not above 0, or no card in the discard order); ``()`` (no target
  array) when the reward is not the first or no hand card was offered. Our
  rows: reward (1)'s ``discard_snooper_card(card_id)`` (an Agent-turn row in
  her own turn, ``turn_rows.SNOOPER_DISCARD``) and the ``OPTIONAL_DISCARD``
  window outside it, each with ``infos[0]`` = the hand cards its rows offer;
  ``((card,),)`` picks that card's row. ``((),)`` and ``()`` choose no card:
  the window's ``decline_snooper_discard``; in her own turn the app's
  prompt asks for at least one card (min 1, how it takes an empty answer is
  UNTRACED) and our row has no refusal (it lapses at the turn-end press).
- Duplicity: one app prompt with two target informations
  (``Targets``, each kind ``SelectFaction``, forced, max
  1): ``infos[0]`` the TRACKs she has Influence on (``minusone``,
  ``InfluenceDelta`` -1, ``GetFactionInfluence > 0``), ``infos[1]`` the
  TRACKs holding a Snooper token (``plusone``, ``InfluenceDelta`` +1), both
  in ``FactionTracks`` order and neither when no track holds a token
  (``Any`` on the token tracks). The app's ``Evaluate`` finds
  them by that attribute; ours by position. The answer is
  ``((lose,), (gain,))`` (``UpdateSelectionResponses``), which may name one
  track twice. Our rows
  ``lose_leader_influence(faction)`` and the gain row after it take
  ``response[0]`` and ``response[1]`` of the one answer, made before the
  loss as the app makes both picks at once.

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
from dune_imperium.agents.app_ai.abilities.board import _math_max
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
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.rules import turn_rows
from dune_imperium.rules.frames import FrameKind, own_turn_frame_index

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA: Final = "ability.activated.ix."
_TA: Final = "ability.triggered.ix."
_PA: Final = "ability.play.ix."
_AB: Final = "ability.activated.original."

#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``).
_ANY_FACTION: Final = "none"
#: ``imperium.original.foldspace_imperium.archID``.
_FOLDSPACE: Final = "imperium.original.foldspace_imperium"
#: ``AgentIcons`` Circle (1), Triangle (2), Pentagon (3): the City, Spice
#: Trade and Landsraad icons ``HasTwoPCTAgents`` counts (our ``AgentIcon``
#: spelling).
_PCT_ICONS: Final = frozenset({"Pentagon", "Circle", "Triangle"})
#: ``f64=100.0``: Guild Contacts' and One Step Ahead's value.
_HUNDRED: Final = 100.0


def _cost_label(name: str, space: Entity) -> str:
    """The ``DebugOnlyStringInterpolationHandler`` label of the 0.0 term a
    signet adds when the space's own cost leaves too little to pay it."""

    return f"{name} Ability cost cannot be paid in addition to {space.ref} cost"


# ---------------------------------------------------------------------------
# Archduke Armand Ecaz: Coordination and Conscript
# ---------------------------------------------------------------------------


def has_two_pct_agents(p: Profile) -> bool:
    """``CoordinationAbility.HasTwoPCTAgents``.

    ``Playmat.Board.Descendents.OfType<Agent>().Where(...).Count() > 1`` (on ``1 <
    count``) with the filter: the Agent's owner is the player, its parent is a
    ``Space``, and the space's ``ActionIcon`` is 3, 1 or 2 (Pentagon, Circle, Triangle:
    the Landsraad, City and Spice Trade spaces). A player without the ``Swordmaster``
    attribute (``isSwordmaster == 0``) does not count an Agent on the Swordmaster space
    (``IsSwordmasterSpace``, false). Ours: the seat's ``agent_locations`` on board
    spaces; ``swordmaster_acquired`` is the attribute.
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


@port(_AA + "coordination")
class CoordinationAbility(DeferredAbility):
    """``RiseOfIx.CoordinationAbility`` (Archduke Armand Ecaz: in the Reveal
    turn, with two or more Agents on Landsraad, City or Spice Trade spaces,
    trash a card in play).

    ``constructor``: ``AbilityTiming = 2``, ``HideInvalidDeferred = true``, button text
    ``generic.trash.inplay``. No ``ValueForPlayer`` override (the empty base).
    """

    timing: ClassVar[Timing] = Timing.REVEAL

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CoordinationAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: a ``BoolAction`` that the context target is a ``Player`` in its
        Reveal turn (``IsInPlayerTurn(2)``) and ``HasTwoPCTAgents``."""

        return _in_reveal_turn(p) and has_two_pct_agents(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CoordinationAbility.Evaluate``.

        ``(card, value) = GetCardToTrash(GetTargets(0).OfType<
        ImperiumPlayable>(), 1.0)`` (``f64=1.0``), then
        ``UpdateSelectionTargets(value, src, card ? [card.ID] :
        Array.Empty)``: without a junk card the AI uses the ability at 1.0
        and trashes nothing (``((),)``), as ``TrashAbility.Evaluate``.
        """

        choice = _Choice()
        card, value = p.card_to_trash(_targets(request, 0, Kind.CARD), 1.0)
        choice.update_targets(value, () if card is None else (card.ref,))
        label = "nothing" if card is None else card.ref
        return choice.answer(f"Coordination | trash {label}")


#: ``GetConscriptTargets``' ``PersuasionCost`` limit and ``Evaluate``'s.
_CONSCRIPT_MAX_COST: Final = 3


def conscript_targets(p: Profile) -> list[Entity]:
    """``ConscriptAbility.GetConscriptTargets``.

    ``ImperiumRowCards(M).Concat(ReserveRowCards(M, true).Where(...))
    .OfType<ImperiumPlayable>().Where(...)``: the Row in order, then the Reserve without
    Foldspace (``ArchID != FoldspaceImperium``), each kept when its archetype's
    ``PersuasionCost`` (default 99) is at most 3 and none of its factions is in the
    player's ``FactionsBlocked``. Judgement: ``FactionsBlocked`` is set only by the
    app's Challenge mode (``TriggeredAbilities.Challenge.FactionBlock``), which our
    engine has not. The Reserve holds one entity per non-empty pile
    (``reserve:<card_id>``), in our ``reserve_stacks`` order, with Market Opening's
    discount when Arrakeen Scouts is on (as ``abilities/ imperium_b``).
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


@port(_AA + "conscript")
class ConscriptAbility(SignetAbility):
    """``RiseOfIx.ConscriptAbility`` (Archduke Armand Ecaz's signet: acquire
    a card that costs 3 or less).

    ``constructor``: ``WillClearUndo = true``, ``PlaceSpyNoUndo =
    true``; no ``Cost`` override (``SignetAbility.Cost`` = ``HasSignet``).
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ConscriptAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ConscriptAbility.ValueForPlayer``.

        The base summer, then, when ``GetConscriptTargets`` is not empty (``Any``): the
        largest ``AcquireValue(P)`` among them (``Enumerable.Max`` of the summers; its
        ``Sum`` @+0x18) as "Conscript Acquire Value", and before the Late arc
        (``GetGameArc() > 1`` skips) ``ConscriptBeforeLateValue`` as "Conscript Before
        Late Game". No targets: nothing.
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
        """``ConscriptAbility.Evaluate``.

        For each target card (``GetTargets(0).OfType<ImperiumPlayable>``, in order)
        whose ``PersuasionCost`` (default 0) is at most 3 (skips): its
        ``AcquireValue(P)`` plus, before the Late arc (skips),
        ``ConscriptBeforeLateValue`` ("Conscript Before Late Game"), stored with
        ``UpdateSelectionResponses(sum, src, [EntityList([card]), Int(0)])`` (strictly
        better replaces).
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


@port(_AA + "guild_contacts")
class GuildContactsAbility(SignetAbility):
    """``RiseOfIx.GuildContactsAbility`` (Ilesa Ecaz's signet: pay a Solari
    for a Foldspace card). ``constructor``: signet button text only."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``GuildContactsAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``SignetAbility.Cost``, then ``HasResources.AtLeast(Solari, 1)``,
        then a ``BoolAction`` that ``ReserveRowCards(M, true)`` holds a Foldspace
        (``ArchID == FoldspaceImperium``)."""

        return (
            super().meets_cost(p)
            and p.ctx.me.resources.solari >= 1
            and foldspace_in_reserve(p)
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``GuildContactsAbility.ValueForPlayer``.

        A space in ``with_entities`` (``ListUtil.CollectFirst<Space>``) that leaves no
        Solari for the signet after its own cost
        (``CanAgentAbilityBePlayedWithSpace(space, Solari, 1)`` false) adds 0.0 with the
        debug label and returns. Otherwise ``GetSolariValue(-1)`` ("Guild Contacts
        Solari Cost") and ``FoldspaceValue`` ("Foldspace Gain"); neither the Solari nor
        the Reserve is checked here.
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
        """``GuildContactsAbility.Evaluate``.

        Nothing in the Late arc (``GetGameArc() > 1``) or at the climax (``IsClimax``);
        otherwise ``UpdateSelectionResponses(100.0, src, [IntTargetResponse(0)])`` (log
        "Guild Contacts | 100").
        """

        choice = _Choice()
        if p.game_arc() > 1 or p.is_climax():
            return choice.answer("Guild Contacts")
        choice.update_responses(_HUNDRED, ((0,),))
        return choice.answer("Guild Contacts | 100")


def _agent_box_value(p: Profile, card: Entity) -> float:
    """``OneStepAheadRoundAbility.Evaluate`` :
``card.Abilities.OfType<AgentAbility>().FirstOrDefault()``,
    its ``ValueForPlayer(context.Player, Array.Empty)`` ``Sum`` (@+0x18), or 0.0 without
    an Agent box."""

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


@port(_TA + "one_step_ahead_round")
class OneStepAheadRoundAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadRoundAbility`` (Ilesa Ecaz: set a hand card
    aside at the round start; ``IsValidFor`` fires on
    ``Events.RoundSetupFinishedIlesa``).

    ``constructor`` stores no timing; ``Cost`` = NoCost.
    ``Targets`` lists the hand (kind ``KeepCard``, forced,
    max 1; a human with one card gets no target).
    """

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OneStepAheadRoundAbility.Evaluate``.

        The hand targets (``OfType<ImperiumPlayable>``) sorted by the value of their
        Agent box, highest first (``OrderByDescending(...) .ToList()``). Set aside the
        first of the top three (``Take(3)``) that shows exactly one Agent icon
        (``IconList.Count == 1``). Without one, ``GetBestOption(sorted)``'s card
        (``original_intrigue.best_option``) is removed from the sorted list
        (``List.Remove``) and its first card is set aside; an empty list stores nothing.
        The pick is ``UpdateSelectionTargets(100.0, src, [card.ID])``.
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


@port(_TA + "one_step_ahead_turn")
class OneStepAheadTurnAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadTurnAbility`` (Ilesa Ecaz: the set-aside card
    returns to the hand at the start of the round's second turn;
    ``IsValidFor`` fires on ``Events.TurnStarted``). ``constructor``
    stores no timing; ``Cost`` = NoCost; no AI hook."""


@port(_TA + "one_step_ahead_send")
class OneStepAheadSendAbility(TriggeredAbility):
    """``RiseOfIx.OneStepAheadSendAbility`` (Ilesa Ecaz: sending an Agent
    with the returned card that turn gives a spice when it shows exactly one
    Agent icon, else a Solari; ``IsValidFor`` fires on
    ``Events.ImperiumPlayed`` in the Agent turn, ``IsInPlayerTurn(1)``).
    ``ShouldExhaust`` = false; ``Cost`` = NoCost;
    no AI hook."""

    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Prince Rhombur Vernius: Heavy Lasgun Cannons
# ---------------------------------------------------------------------------


@port(_TA + "heavy_lasgun_cannons")
class HeavyLasgunCannonsAbility(TriggeredAbility):
    """``RiseOfIx.HeavyLasgunCannonsAbility`` (Prince Rhombur Vernius: his dreadnoughts
    have strength 4). On ``Events.GameStarted`` the ``BeginExecution`` sets ``Strength``
    to 4 on the player's dreadnoughts (``OfType<Dreadnought>``). ``constructor`` stores
    no timing; ``Cost`` = NoCost; no AI hook."""


# ---------------------------------------------------------------------------
# "Princess" Yuna Moritani: Final Delivery and Smuggling Operation
# ---------------------------------------------------------------------------


@port(_AA + "final_delivery")
class FinalDeliveryAbility(SignetAbility):
    """``RiseOfIx.FinalDeliveryAbility`` (Yuna Moritani's signet: pay 7
    Solari for one Influence, a troop and a spice). ``constructor``:
    signet button text only."""

    #: ``HasResources.AtLeast(Solari, 7)`` (``Cost``) and
    #: ``CanAgentAbilityBePlayedWithSpace(space, Solari, 7)``.
    SOLARI_COST: ClassVar[int] = 7

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``FinalDeliveryAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``SignetAbility.Cost`` then
        ``HasResources.AtLeast(Solari, 7)``."""

        return super().meets_cost(p) and p.ctx.me.resources.solari >= self.SOLARI_COST

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FinalDeliveryAbility.ValueForPlayer``.

        A space in ``with_entities`` that leaves fewer than 7 Solari after its own cost
        (``CanAgentAbilityBePlayedWithSpace(space, Solari, 7)`` false) adds 0.0 with the
        debug label and returns. Otherwise ``GetSolariValue(-7)`` ("Final Delivery -7
        Solari"), ``GetSpiceValue(1)`` ("Final Delivery Spice"), ``GetTroopValue(1,
        false)`` ("Final Delivery Troop") and ``GetGainInfluenceValue(None, 1, -1,
        false).Sum`` ("Final Delivery Influence"). The Solari held are not checked here.
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
        """``FinalDeliveryAbility.Evaluate``.

        A ``DefaultValueSummer`` of ``GetSolariValue(-7)``, ``GetSpiceValue(1)`` and
        ``GetTroopValue(1, false)`` is built but never read: each offered track
        (``OfType<FactionTrack>``) is stored at ``GetGainInfluenceValue(track.Faction,
        1, -1, false).Sum`` alone (of the influence summer) with
        ``UpdateSelectionTargets`` (strictly better replaces). No threshold.
        """

        choice = _Choice()
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            choice.update_targets(g.sum, (track.ref,))
        return choice.answer("Final Delivery")


@port(_PA + "smuggling_operation_solari")
class SmugglingOperationSolariAbility(TriggeredAbility):
    """``ability.play.ix.smuggling_operation_solari`` (Yuna
    Moritani: one more Solari whenever she gains Solari on her turn). On
    ``Events.GameStarted`` it installs ``MakeResourceMod``
    (``Solari`` +1, ``DuringPlayerTurn``, permanent). ``constructor``
    stores no timing; ``ShouldExhaust`` = false; ``Cost`` = NoCost; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_PA + "smuggling_operation_water")
class SmugglingOperationWaterAbility(TriggeredAbility):
    """``ability.play.ix.smuggling_operation_water`` (Yuna Moritani: she starts without
    water). On ``Events.GameStarted`` ``BeginExecution`` pays all her water
    (``PayWater(P.Water)``). ``constructor`` stores ``AbilityTiming = 2``;
    ``ShouldExhaust`` = false; ``Cost`` = NoCost; no AI hook."""

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


# ---------------------------------------------------------------------------
# Viscount Hundro Moritani: Couriers and Intelligence
# ---------------------------------------------------------------------------


@port(_AA + "couriers")
class CouriersAbility(SignetAbility):
    """``RiseOfIx.CouriersAbility`` (Hundro Moritani's signet: pay a spice to
    move the Freighter). ``constructor``: button text only."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CouriersAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``SignetAbility.Cost`` then
        ``HasResources.AtLeast(Spice, 1)``."""

        return super().meets_cost(p) and p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``CouriersAbility.ValueForPlayer``.

        A space in ``with_entities`` that leaves no spice after its own cost
        (``CanAgentAbilityBePlayedWithSpace(space, Spice, 1)`` false) adds 0.0 with the
        debug label and returns. Otherwise ``-GetSpiceValue(1)`` ("Couriers -1 Spice":
        the value of +1 negated, with the sign mask) and ``FreighterValue`` ("Couriers
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
        """``CouriersAbility.Evaluate``: ``sel = GetFreighterSelections(-1)``, then
        ``UpdateSelectionResponses(FreighterValue, src,
        [IntTargetResponse(sel.Item1)])`` (log "Recall" for a nonzero ``Item1``, else
        "Advance"), as ``FreighterAbility.Evaluate``."""

        choice = _Choice()
        recall, _item2, log = p.freighter_selections(-1)
        verb = "Advance" if recall == 0 else "Recall"
        choice.update_responses(p.freighter_value(), ((recall,),))
        return choice.answer(f"Couriers | {verb} | {log}")


@port(_TA + "intelligence")
class IntelligenceAbility(TriggeredAbility):
    """``RiseOfIx.IntelligenceAbility`` (Hundro Moritani: at the game start
    look at the top two Intrigue cards, keep one and put the other back on
    top; ``IsValidFor`` fires on ``Events.LeaderSetupHundro``).

    ``constructor`` stores no timing; ``Cost`` = NoCost. No
    ``Evaluate`` override: ``BeginExecution`` decorates its
    ``KeepIntrigueCard`` picker with ``EvaluateIntrigue``
    (``AIEvaluateSelection``).
    """

    def evaluate_intrigue(self, p: Profile, request: Request) -> Answer:
        """``IntelligenceAbility.EvaluateIntrigue``.

        Each offered card (``GetTargets(0).OfType<IntriguePlayable>``) is stored at its
        ``Rating`` (``GetAttributeValue<int>(Rating, 0)``) with
        ``UpdateSelectionTargets`` (the first sticks, a later one only when strictly
        higher): the highest-rated card is kept.
        """

        choice = _Choice()
        for card in _targets(request, 0, Kind.INTRIGUE):
            choice.update_targets(float(card.int_attr("Rating")), (card.ref,))
        return choice.answer("Intelligence | keep Intrigue")


# ---------------------------------------------------------------------------
# Tessia Vernius: Careful Observation and Duplicity
# ---------------------------------------------------------------------------

#: Our id of Tessia Vernius (``rules.snoopers.TESSIA``): only her Leader's
#: ``SnooperFactions`` is ever set (``CarefulObeservationSetupAbility``).
_TESSIA: Final = "tessia_vernius"
#: ``Factions.SpacingGuild`` (2), tested by Duplicity's V and E.
_SPACING_GUILD: Final = "spacing_guild"
#: ``Factions.None`` (0): the abstract ``SnooperFaction``.
_NO_FACTION: Final = "none"
#: every Careful Observation answer's value.
_ONE: Final = 1.0
#: ``CarefulObservationFactionAbility`` ``SelectionMode`` / ``CanRunImmediately``:
#: ``SnooperFactions.Count`` compared with 3.
_FIRST_SNOOPER_LEFT: Final = 3


def _snooper_factions(p: Profile) -> tuple[str, ...] | None:
    """``Leader.SnooperFactions`` (``Player`` +0x130 is ``Leader``): the
    tracks still holding a Snooper token, ``None`` for a leader whose list
    was never set (every leader but Tessia). Ours:
    ``PlayerState.snooper_faction_ids``; like the app's list, it loses a
    track as its token is reached, before the reward is offered."""

    me = p.ctx.me
    if me.leader_id != _TESSIA:
        return None
    return me.snooper_faction_ids


def snooper_discards_waiting(p: Profile) -> tuple[str, ...]:
    """The tracks whose reward (1), "discard -> 1 spice", waits for its
    discard: our stand-in for the app's granted, not yet run
    ``CarefulObservation<Faction>Ability`` (``HasCustomAbility``).

    Ours pays rewards (2)-(4) at the reach and holds only (1) for a
    decision (``rules.snoopers.settle_snooper_discards``): an item of kind
    ``turn_rows.SNOOPER_DISCARD`` (value: the track) waiting on her own open
    turn frame, or her own ``OPTIONAL_DISCARD`` window (context
    ``faction``) outside her turn.
    """

    ctx = p.ctx
    found: list[str] = []
    index = own_turn_frame_index(ctx.state, ctx.seat)
    if index is not None:
        frame = ctx.state.decision_stack[index]
        found.extend(
            value
            for kind, _source, value in turn_rows.pending(frame)
            if kind == turn_rows.SNOOPER_DISCARD
        )
    window = ctx.own_frame_context(FrameKind.OPTIONAL_DISCARD)
    if window is not None:
        faction = window.get("faction")
        if isinstance(faction, str):
            found.append(faction)
    return tuple(found)


def snooper_factions_used(p: Profile) -> tuple[str, ...]:
    """``Leader.SnooperFactionsUsed``: the tracks whose Snooper reward has
    run (``BeginExecution`` adds its track before paying by the list's
    count).

    Ours keeps no such list. The app numbers the rewards by the order its
    abilities run, so the reward (1) that waits in ours is the app's first
    run, before which the list is empty: ``()`` while one waits (judgement;
    ours numbers them by the order the tokens are reached, so a second token
    reached by the same action has already been paid then). With none
    waiting, every reached token's reward has been paid: the tracks without
    a token, in ``FACTIONS`` order. ``()`` for a leader without the list
    (the app's ``null``, read as empty by every caller).
    """

    tokens = _snooper_factions(p)
    if tokens is None or snooper_discards_waiting(p):
        return ()
    return tuple(f for f in FACTIONS if f not in tokens)


@port(_AA + "careful_observation_faction")
class CarefulObservationFactionAbility(DeferredAbility):
    """``RiseOfIx.CarefulObservationFactionAbility`` (abstract; Tessia
    Vernius' Snooper reward for one track, granted as a custom ability by
    ``CarefulObservationTriggeredAbility`` / ``...OppTriggeredAbility``).

    ``constructor``: ``DeferredAbility constructor(m, name, 0, 0)``,
    ``HideInvalidDeferred = true``, ``KeepImperiumRowOpen = true``, the
    dynamic button texts; no ``AbilityTiming`` stored. No ``ValueForPlayer``
    override (the empty base). ``BeginExecution`` (``BeginExecution``
) adds the track to ``SnooperFactionsUsed``, then by its count
    1: ``Discard`` of the picked card and ``GainSpice(1)``; 2 or 4:
    ``FactionTrackBonusAction``; 3 or 4: ``GainFactionInfluence``; then
    ``RemoveCustomAbility``.
    """

    #: ``SnooperFaction``, our faction id.
    snooper_faction: ClassVar[str] = _NO_FACTION

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``CarefulObservationFactionAbility.SelectionMode``.

        Optional (0) unless the context target is a ``Player`` whose Leader's
        ``SnooperFactions`` is set with fewer than 3 tracks (0), then Explicit: the
        first reward (three tokens left) is optional, the later ones explicit.
        """

        tokens = _snooper_factions(p)
        if tokens is None or len(tokens) >= _FIRST_SNOOPER_LEFT:
            return SelectionMode.OPTIONAL
        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CarefulObservationFactionAbility.CanRunImmediately``.

        A ``Player`` target with ``HandCount == 0`` (false) whose ``SnooperFactions`` is
        set and holds exactly 3 tracks: the first reward with no card to discard runs at
        once (the token covers the top space, no spice).
        """

        tokens = _snooper_factions(p)
        return (
            len(p.ctx.hand) == 0
            and tokens is not None
            and len(tokens) == _FIRST_SNOOPER_LEFT
        )

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: the track's reward was granted and has
        not run. Ours: its reward (1) waits (``snooper_discards_waiting``)."""

        return self.snooper_faction in snooper_discards_waiting(p)

    def meets_cost(self, p: Profile) -> bool:
        """``CarefulObservationFactionAbility.Cost``.

        ``HasCustomAbility(this)`` then a ``BoolAction``: the context target is a
        ``Player`` (``TargetIs<Player>``) and its Leader's ``SnooperFactionsUsed`` does
        not hold ``SnooperFaction`` (``Contains`` then; a ``null`` list passes).
        """

        return self.has_custom_ability(p) and (
            self.snooper_faction not in snooper_factions_used(p)
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CarefulObservationFactionAbility.Evaluate``.

        ``SnooperFactionsUsed`` (a ``null`` list is a new empty one) not empty
        (``ListUtil.IsEmpty`` false): ``UpdateSelectionTargets(1.0, src, null)``. Empty
        (the first reward): a ``DefaultValueSummer`` of ``DiscardValue`` ("Discard") and
        ``GetSpiceValue(1)`` ("Spice"); the targets
        ``GetTargets(this).OfType<ImperiumPlayable>().ToList()``; none: ``(1.0, null)``.
        Else ``card = ChooseDiscardEvaluator. GetDiscardOrder(P, targets,
        false).FirstOrDefault()``, and ``UpdateSelectionTargets(1.0, src, [card.ID])``
        unless ``0.0 >= Sum`` (a NaN sum takes the card) or no card, then ``(1.0, src,
        Array.Empty)``. The summer only gates; the value is always 1.0.
        """

        choice = _Choice()
        if snooper_factions_used(p):
            choice.update_targets(_ONE, None)
            return choice.answer("Careful Observation")
        v = Summer()
        v.add("Discard", p.discard_value())
        v.add("Spice", p.spice_value(1))
        targets = _targets(request, 0, Kind.CARD)
        if not targets:
            choice.update_targets(_ONE, None)
            return choice.answer("Careful Observation (First Snooper Token)")
        order = p.discard_order(targets, False)
        card = order[0] if order else None
        label = (
            f"Careful Observation (First Snooper Token) | {v.sum} | discarding: "
            f"{None if card is None else card.ref} | hand: "
            f"{', '.join(c.ref for c in order)}"
        )
        if not (0.0 >= v.sum) and card is not None:
            choice.update_targets(_ONE, (card.ref,))
        else:
            choice.update_targets(_ONE, ())
        return choice.answer(label)


@port(_AA + "careful_observation_emperor")
class CarefulObservationEmperorAbility(CarefulObservationFactionAbility):
    """``RiseOfIx.CarefulObservationEmperorAbility``: ``constructor`` (the base's with
    its name); ``SnooperFaction`` = ``Emperor``."""

    snooper_faction: ClassVar[str] = "emperor"


@port(_AA + "careful_observation_spacing_guild")
class CarefulObservationSpacingGuildAbility(CarefulObservationFactionAbility):
    """``RiseOfIx.CarefulObservationSpacingGuildAbility``: ``constructor
``; ``SnooperFaction`` = ``SpacingGuild``
    ."""

    snooper_faction: ClassVar[str] = "spacing_guild"


@port(_AA + "careful_observation_bene_gesserit")
class CarefulObservationBeneGesseritAbility(CarefulObservationFactionAbility):
    """``RiseOfIx.CarefulObservationBeneGesseritAbility``: ``constructor
``; ``SnooperFaction`` = ``BeneGesserit``
    ."""

    snooper_faction: ClassVar[str] = "bene_gesserit"


@port(_AA + "careful_observation_fremen")
class CarefulObservationFremenAbility(CarefulObservationFactionAbility):
    """``RiseOfIx.CarefulObservationFremenAbility``: ``constructor``; ``SnooperFaction``
    = ``Fremen``."""

    snooper_faction: ClassVar[str] = "fremen"


@port(_TA + "careful_obeservation_setup")
class CarefulObeservationSetupAbility(TriggeredAbility):
    """``ability.triggered.ix.careful_obeservation_setup`` (the
    app's spelling; Tessia Vernius: a Snooper token on each track at setup).
    ``IsValidFor`` (``IsValidFor``) fires on
    ``Events.GameStarted`` for a ``Leader`` owner held by a
    ``Player``; ``BeginExecution`` sets the Leader's
    ``SnooperFactions`` to Emperor, Spacing Guild, Bene Gesserit, Fremen
    (``ChangeAttribute``). ``constructor`` stores no timing; ``Cost`` = NoCost; no AI
    hook."""


@port(_PA + "careful_observation_triggered")
class CarefulObservationTriggeredAbility(TriggeredAbility):
    """``ability.play.ix.careful_observation_triggered``
    (Tessia Vernius reaches a Snooper token in her own turn).

    ``IsValidFor`` (``IsValidFor``) fires on ``Events.InfluenceGained`` for a ``Player``
    target when not ``IsOpponentTurn``, the event's Faction's Influence is at least
    ``GetSnooperInfluenceLevel`` and her ``SnooperFactions`` holds it;
    ``BeginExecution`` removes the track from the list ("SnooperTokenRemoved") and
    grants its ``CarefulObservation<Faction>Ability`` (``AddCustomAbility``).
    ``constructor`` stores ``AbilityTiming = 2``; ``ShouldExhaust`` = false; ``Cost`` =
    NoCost; no AI hook.
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


@port(_PA + "careful_observation_opp_triggered")
class CarefulObservationOppTriggeredAbility(TriggeredAbility):
    """``ability.play.ix.careful_observation_opp_triggered``
    (Tessia Vernius reaches a Snooper token outside her own turn).

    ``IsValidFor`` (``IsValidFor``) is the own-turn
    trigger's with ``IsOpponentTurn`` true; ``BeginExecution``
    removes the token, grants the track's ability and runs it at
    once (``RunUsableAbilityForPlayer``, the ability picked by type).
    ``constructor`` stores ``AbilityTiming = 2``; ``ShouldExhaust`` = false;
    ``Cost`` = NoCost; no AI hook.
    """

    timing: ClassVar[Timing] = Timing.REVEAL
    should_exhaust: ClassVar[bool] = False


def _faction_influence(p: Profile, faction: str) -> int:
    """``Player.GetFactionInfluence(F)``."""

    return int(getattr(p.ctx.me.influence, faction))


#: ``Cost``'s ``HasFactionInfluence.AtLeast(F, 1)`` factions in the app's order, joined
#: by ``Or``.
_DUPLICITY_COST_FACTIONS: Final = (
    "emperor",
    "fremen",
    "bene_gesserit",
    "spacing_guild",
)
#: ``HasFactionInfluence.AtLeast(F, 1)``.
_DUPLICITY_MIN_INFLUENCE: Final = 1
#: ``GetBestInfluenceExchange(-1, 1, ...)`` in both V and E.
_DUPLICITY_LOSE: Final = -1
_DUPLICITY_GAIN: Final = 1


@port(_AB + "duplicity")
class DuplicityAbility(SignetAbility):
    """``ability.activated.original.duplicity`` (Tessia Vernius'
    signet: lose one Influence for one with a Faction holding a Snooper
    token).

    ``constructor``: the ``SignetAbility`` constructor, ``HideInvalidDeferred =
    true``, signet button text ``tessiavernius``.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DuplicityAbility.SelectionMode``: Optional (0)."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``DuplicityAbility.Cost``.

        ``SignetAbility.Cost``, then a ``BoolAction`` that the target is a ``Player``
        whose Leader's ``SnooperFactions`` is set and not empty, then
        ``HasFactionInfluence.AtLeast(F, 1)`` for Emperor, Fremen, Bene Gesserit or
        Spacing Guild (``Or``).
        """

        if not super().meets_cost(p):
            return False
        tokens = _snooper_factions(p)
        if tokens is None or not len(tokens) > 0:
            return False
        return any(
            _faction_influence(p, f) >= _DUPLICITY_MIN_INFLUENCE
            for f in _DUPLICITY_COST_FACTIONS
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DuplicityAbility.ValueForPlayer``.

        The base summer (``AbilityDefinition.ValueForPlayer(P, Array.Empty)``, empty;
        ``with_entities`` is not read), then with the Leader's ``SnooperFactions``
        (``null`` read as a new empty list): nothing when it is exactly
        ``[SpacingGuild]`` (and ``Contains(2)``) or empty (``Any``); else "Duplicity" =
        ``Math.Max(0.0, GetBestInfluenceExchange(-1, 1, false, null,
        SnooperFactions).Item3)`` (then ``Math.Max``, NaN kept). The app shuffles the
        Leader's own list in place (the gain list is the attribute itself); ours passes
        a copy.
        """

        s = Summer()
        tokens = _snooper_factions(p) or ()
        if len(tokens) == 1 and _SPACING_GUILD in tokens:
            return s
        if not tokens:
            return s
        _lose, _gain, value = p.best_influence_exchange(
            _DUPLICITY_LOSE, _DUPLICITY_GAIN, None, list(tokens)
        )
        s.add("Duplicity", _math_max(0.0, value))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DuplicityAbility.Evaluate``.

        The lose tracks are the ``ValidEntities<FactionTrack>`` of the target
        information with ``InfluenceDelta == -1``, the gain tracks those of the one with
        ``+1``; ours ``infos[0]`` and ``infos[1]``. Nothing without the lose
        information, when the lose tracks are exactly one Spacing Guild track (``Faction
        == 2``), or without the gain information. ``(lose, gain, value) =
        GetBestInfluenceExchange(-1, 1, true, loseFactions, gainFactions)`` (showLog);
        the first lose track of ``lose`` and gain track of ``gain``, else nothing
        (``Factions.None`` matches no track: no exchange above 0). The answer is a
        ``DefaultValueSummer`` "Best Influence Exchange Value" stored with
        ``UpdateSelectionResponses(Sum, src, [EntityList([lose]),
        EntityList([gain])])``; no threshold.
        """

        choice = _Choice()
        if not request.infos:
            return choice.answer("Duplicity")
        lose_tracks = _targets(request, 0, Kind.TRACK)
        if len(lose_tracks) == 1 and lose_tracks[0].ref == _SPACING_GUILD:
            return choice.answer("Duplicity")
        if len(request.infos) < 2:
            return choice.answer("Duplicity")
        gain_tracks = _targets(request, 1, Kind.TRACK)
        lose, gain, value = p.best_influence_exchange(
            _DUPLICITY_LOSE,
            _DUPLICITY_GAIN,
            [t.ref for t in lose_tracks],
            [t.ref for t in gain_tracks],
        )
        lose_track = next((t for t in lose_tracks if t.ref == lose), None)
        gain_track = next((t for t in gain_tracks if t.ref == gain), None)
        if lose_track is None or gain_track is None:
            return choice.answer("Duplicity")
        v = Summer()
        v.add("Best Influence Exchange Value", value)
        choice.update_responses(v.sum, ((lose_track.ref,), (gain_track.ref,)))
        return choice.answer(f"Duplicity | {v.sum}")
