"""Uprising leader abilities and signet rings — spec/leaders.md.

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``), so the app's inheritance
(``LeadTheWayAbility`` -> ``DisciplineAbility`` -> ``SignetAbility`` ->
``DeferredAbility``) is the Python MRO. Leader-specific branches inside ``AIProfile``
methods (influence terms, Gurney's deploy top-up, Muad'Dib's sandworm and hooks terms,
Staban's post and icon terms, the Feyd/Margot WantSpy multiplier, Lady Jessica's
return-memories gate) live in the profile, and the Shaddam deploy inversion and the
Reverend Mother space merge live in the generic ports; they are not repeated here.

How a leader ability reaches the AI (spec §0.1): the ``ValueForPlayer`` of
the leader's ``SignetAbility`` is merged into a placement only when the card
played has signet icons (``AgentAbility``), the Reverend Mother's into the
generic ``SpaceAbility`` value; every other leader ``ValueForPlayer`` has no
AI caller and is ported for completeness. ``evaluate`` answers the prompts.

Request / answer encoding (on top of ``abilities/generic.py``'s):

- one target info: ``request.infos[0]`` entities (spies, training spaces,
  cards) as in the generic ports; ``Answer.response`` ``((ref,),)``;
- the two custom choices with a dependent list (Chronicler's Insight,
  Emperor of the Known Universe): ``infos[0].options`` = the offered options
  (0, 1), ``infos[1]`` = the dependent list of option 1 (hand cards, faction
  tracks); the answer is ``((option,),)`` or ``((1,), (ref,))``;
- Chronicler's Insight acquire: ``infos[0]`` = the cards, the answer
  ``((card,), (0,))`` (option 0 of the destination picker);
- Feyd's training spaces are ``training_space_entity(space_id)`` entities
  (``Kind.SPACE``, ref = our ``FEYD_TRAINING_TRACK`` space id) carrying the
  app's space definition (``TrainingTrack.SpaceDefs``).
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
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
    DeferredAbility,
    GainIntrigueAbility,
    SpaceAbility,
    TrashCustomAbility,
    TriggeredAbility,
    collect_first,
    deferred_threshold_reached,
    gain_any_influence_value,
    signet_icons,
    value_for_reveal_abilities,
)
from dune_imperium.agents.app_ai.catalog import (
    LEADER_ARCHETYPES,
    POST_INDEX,
    board_space_ids,
    card_entity,
    conflict_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.actions import ActionValue
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.leader_abilities import (
    FACTION_POST_IDS,
    LANDSRAAD_POST_IDS,
)

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA = "ability.activated."
_AU = _AA + "uprising."
_TU = "ability.triggered.uprising."

_FEYD = "leader.uprising.feyd_rautha_harkonnen"
_BATTLE_FOR_ARRAKEEN = "conflict.uprising.battle_for_arrakeen_up"
_SECRETS = "space.original.secrets"
_DESERT_TACTICS = "space.uprising.desert_tactics"
_FREMKIT = "space.uprising.fremkit"
_ESPIONAGE = "space.uprising.espionage"
_FOLDSPACE = "imperium.original.foldspace_imperium"
_DAGGER = "imperium.original.dagger"
_DUNE = "imperium.original.dune_the_desert_planet"
_RECONNAISSANCE = "imperium.original.reconnaissance"
#: The Uprising reserve in ``Decks.UprisingReserveDeck`` order (Foldspace,
#: absent from our engine, has no ``PersuasionCost`` and never passes the
#: cost filter of ``GetImperiumRowAcquireCardTargets``).
_RESERVE_ORDER: Final = ("prepare_the_way", "the_spice_must_flow")

# ---------------------------------------------------------------------------
# Shared helpers (the app's extension methods, read through AppContext)
# ---------------------------------------------------------------------------


def _leader_arch_id(p: Profile) -> str | None:
    """``P.Leader.ArchID`` (a flipped leader keeps its own ArchID)."""

    leader_id = p.ctx.me.leader_id
    return None if leader_id is None else LEADER_ARCHETYPES.get(leader_id)


def _agent_frame(p: Profile) -> Mapping[str, ActionValue] | None:
    """The context of the seat's own open ``agent_effects`` frame."""

    return p.ctx.own_frame_context("agent_effects")


def _in_agent_turn(p: Profile) -> bool:
    """``player.IsInPlayerTurn(PlayerTurnTypes.AgentTurn = 1)``.

    The app sets the Agent turn type once the Agent card is played and keeps
    it to End Turn; ours is the seat's own open ``agent_effects`` frame.
    """

    return _agent_frame(p) is not None


def _in_reveal_turn(p: Profile) -> bool:
    """``IsInRevealTurn`` / ``player.IsInPlayerTurn(RevealTurn = 2)``.

    Ours: the seat's own open ``reveal`` frame.
    """

    return p.ctx.own_frame_context("reveal") is not None


def _targets(request: Request, index: int, kind: Kind) -> list[Entity]:
    """``choice.GetTargets<T>(index)`` / ``GetDependentTargets<T>(index)``."""

    if len(request.infos) <= index:
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


#: Our ``agent_effects`` context keys that hold a signet's follow-up once the
#: signet itself has run: Feyd's training reward (``feyd_track_stage``) and
#: Staban's paid follow-up (``staban_bonus_post``). Our engine keeps
#: ``pending_agent_effect`` True through them; the app has paid the icon.
_SIGNET_FOLLOW_UP_KEYS: Final = ("feyd_track_stage", "staban_bonus_post")


def _has_signet_icon(p: Profile) -> bool:
    """``HasSignet.CanBePaid``: ``player.SignetIcons() > 0``.

    The app gains the icon when a card with signet icons is played as an Agent
    (``GainSignetIcon``) and pays it after the signet ability ran: ``SignetAbility
    constructor`` binds state 100 to ``Cleanup``, whose ``Cleanup`` yields
    ``PaySignetIcon`` (spec §0.1.2). Ours: the own open Agent turn plays a card with
    signet icons whose Agent box (the signet) is still pending
    (``pending_agent_effect``) and has not reached a follow-up stage
    (``_SIGNET_FOLLOW_UP_KEYS``): Personal Training's ``Train(space)`` grants the space
    reward by ``ChangeRankBonuses`` ``AddCustomAbility`` (§3.2) and Unseen Network's
    ``EmitSequence`` its follow-up (§12.2), both inside the signet's execution, so the
    icon is paid before the post-Agent window lists the grant. A recall-first spy
    (``leader_spy_recalled``) keeps the icon: the recall is chosen inside the signet's
    own ``PlaceSpy`` (``RecallSpyEvaluator``, §3.4), before ``Cleanup``.
    (``feyd_spy_recalled`` only exists beside ``feyd_track_stage``.)
    """

    context = _agent_frame(p)
    if context is None:
        return False
    card_ref = context.get("card_id")
    if not isinstance(card_ref, str) or not card_ref:
        return False
    if signet_icons(card_entity(card_ref, p.ctx.seat)) <= 0:
        return False
    if context.get("pending_agent_effect") is not True:
        return False
    return not any(
        isinstance(context.get(key), str) and context.get(key)
        for key in _SIGNET_FOLLOW_UP_KEYS
    )


def _deployed_spies(p: Profile) -> int:
    """``player.SpyDeployedCount`` (``GetDeployedSpies().Count()``)."""

    return len(p.ctx.me.spy_post_ids)


def _deployed_units(p: Profile) -> int:
    """``ConflictArea.GetPlayerDeployed(player).children.Count``.

    The player's units in the Conflict: troops and sandworms (no dreadnoughts
    in Uprising), and the Bloodlines Commanders and Into the Fray Agent
    (``units_in_conflict``; docs/app-ai/bloodlines-systems.md §1.1, read
    only with the option: ``Profile.conflict_unit_count``).
    """

    return p.conflict_unit_count()


def _has_trashable_card(p: Profile) -> bool:
    """``HasTrashableCard``: ``Player.FindTrashTargets`` is not empty.

    [I] the trash targets are the hand, the discard pile and the cards in
    play, as our engine's trash stages offer them (``counted_in_play``).
    """

    me = p.ctx.me
    return bool(me.hand or me.discard_pile or counted_in_play(me))


def chroniclers_acquire_targets(p: Profile) -> list[Entity]:
    """``ChroniclersInsightAbility.GetAcquireTargets``.

    ``Playmat.GetImperiumRowAcquireCardTargets(player, maxCost = 1, includeReserve =
    true)`` -> the Imperium Row cards passing the first filter (not Foldspace,
    ``PersuasionCost`` (default 99) ``<= maxCost``, ``CanAcquire``), then the reserve
    cards passing the second filter (``PersuasionCost`` (default 99) ``<= maxCost``).
    The set-aside part needs Helena Richese or a set-aside Imperium card and the final
    ``FactionsBlocked`` filter a blocked faction: none exist in Uprising. Judgement:
    ``CanAcquire.Check`` passes for every Row card (our engine offers each of them). The
    reserve holds one entity per non-empty pile (``reserve:<card_id>``, as
    ``economy._row_cards``).
    """

    max_cost = 1  # literal (GetAcquireTargets)
    cards: list[Entity] = []
    for instance_id in p.ctx.imperium_row:
        card = card_entity(instance_id)
        if card.short != _FOLDSPACE and card.int_attr("PersuasionCost", 99) <= max_cost:
            cards.append(card)
    remaining = dict(p.ctx.reserve_stacks)
    for reserve_id in _RESERVE_ORDER:
        if remaining.get(reserve_id, 0) > 0:
            card = card_entity(f"reserve:{reserve_id}")
            if p.ctx.scouts:  # Market Opening's discount (plan §11.8)
                card = p.market_opening_reserve_card(card)
            if card.int_attr("PersuasionCost", 99) <= max_cost:
                cards.append(card)
    return cards


def is_circle_observation_post(post_id: str, board: Board) -> bool:
    """``ArrakisInformantAbility.IsCircleObservationPost``.

    ``post.ObservedSpaces.Any(s => s.ActionIcon == Circle (1))``: a post connected to a
    City (Circle-icon) board space. Also the post filter of Arrakis Informant's
    ``PlaceSpy``.
    """

    index = POST_INDEX[post_id]
    for space_id in board_space_ids(board):  # BoardSpaces order
        space = space_entity(space_id, board)
        posts = space.attr("ObservationPosts", ())
        if (
            isinstance(posts, tuple)
            and index in posts
            and space.attr("AgentIcon") == "Circle"
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Feyd-Rautha's training track: ``TrainingTrack`` (spec §3.2-3.3)
# ---------------------------------------------------------------------------

_PAY_TO_TRASH_ID = _AU + "personal_training_pay_to_trash"
_TRAINING_TRASH_ID = _AU + "personal_training_trash"
_PLACE_SPY_CUSTOM_ID = _AU + "place_spy_custom"

#: ``TrainingTrack.SpaceDefs`` (literal data of the app's
#: code; spec §3.2): (our ``FEYD_TRAINING_TRACK`` space id, Index,
#: NextIndices, Spice, Troops, AbilityIDs). Our track is the same graph
#: (``test_training_track_matches_our_engine``).
_TRAINING_SPACE_DEFS: Final[
    tuple[tuple[str, int, tuple[int, ...], int, int, tuple[str, ...]], ...]
] = (
    ("start", 0, (1, 2), 0, 0, ()),
    ("paid_trash", 1, (3,), 0, 0, (_PAY_TO_TRASH_ID,)),
    ("first_spy", 2, (3,), 0, 0, (_PLACE_SPY_CUSTOM_ID,)),
    ("mid_trash", 3, (4, 5), 0, 0, (_TRAINING_TRASH_ID,)),
    ("late_trash", 4, (7,), 0, 0, (_TRAINING_TRASH_ID,)),
    ("second_spy", 5, (6,), 0, 0, (_PLACE_SPY_CUSTOM_ID,)),
    ("double_spice", 6, (7,), 2, 0, ()),
    ("final", 7, (), 0, 1, (_PLACE_SPY_CUSTOM_ID,)),
)


def _training_space(
    space_id: str,
    index: int,
    next_indices: tuple[int, ...],
    spice: int,
    troops: int,
    ability_ids: tuple[str, ...],
) -> Entity:
    archetype = Archetype(
        short=f"training_track.space{index}",
        kind="training_space",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(
            {
                "Index": index,
                "NextIndices": next_indices,
                "Spice": spice,
                "Troops": troops,
                "AbilityIDs": ability_ids,
            }
        ),
    )
    return Entity(Kind.SPACE, space_id, archetype)


_TRAINING_SPACES: Final[tuple[Entity, ...]] = tuple(
    _training_space(*definition) for definition in _TRAINING_SPACE_DEFS
)
_TRAINING_BY_ID: Final[Mapping[str, Entity]] = MappingProxyType(
    {space.ref: space for space in _TRAINING_SPACES}
)


def training_space_entity(space_id: str) -> Entity:
    """The training-track space ``space_id`` (our ``FEYD_TRAINING_TRACK`` id)."""

    return _TRAINING_BY_ID[space_id]


def _training_index(space: Entity) -> int:
    return space.int_attr("Index")


def has_training_track(p: Profile) -> bool:
    """``player.TrainingTrack() != null``: built by Feyd's setup ability."""

    return _leader_arch_id(p) == _FEYD


def training_rank(p: Profile) -> int:
    """``TrainingTrack.CurrentRank(player)``: the index of Feyd's token."""

    return _training_index(training_space_entity(p.ctx.me.feyd_track_space))


def training_next_spaces(p: Profile) -> list[Entity]:
    """``TrainingTrack.GetNextSpaces``.

    The current space is the ``CurrentRank``-th child; it yields the spaces at
    its ``NextIndices`` in list order.
    """

    current = _TRAINING_SPACES[training_rank(p)]
    nexts = current.attr("NextIndices", ())
    assert isinstance(nexts, tuple)
    return [_TRAINING_SPACES[int(i)] for i in nexts]


def training_space_value(p: Profile, space: Entity) -> Summer:
    """``TrainingTrack.TrainingSpaceValue(space, player)``.

    Spec §3.3: the spice and troop rewards are added unconditionally (0 when absent);
    each ``AbilityIDs`` entry adds its reward. Pay-to-Trash adds nothing with 0 Solari.
    The spy reward's label is the app's copy-pasted "Trash Card".
    """

    s = Summer()
    s.add(f"Index: {_training_index(space)}", 0.0)
    s.add("Spice", p.spice_value(space.int_attr("Spice")))
    s.add("Troops", p.troop_value(space.int_attr("Troops"), False))
    for ability_id in space.list_attr("AbilityIDs"):  # GetFromOrEmpty
        if ability_id == _PAY_TO_TRASH_ID:
            if p.ctx.me.resources.solari > 0:
                s.add("Solari Cost", p.solari_value(-1))
                s.add("Trash Card", p.trash_card_value())
        elif ability_id == _TRAINING_TRASH_ID:
            s.add("Trash Card", p.trash_card_value())
        elif ability_id == _PLACE_SPY_CUSTOM_ID:
            s.add("Trash Card", p.spy_value().sum)
    return s


def _feyd_stage(p: Profile) -> str | None:
    """The training reward pending in the own Agent turn (``feyd_track_stage``).

    Our engine keeps the reward of the space just reached in the
    ``agent_effects`` frame until it is used or declined; the app grants it as
    a custom ability (``ChangeRankBonuses`` ``AddCustomAbility``) that lives to
    the end of the turn.
    """

    context = _agent_frame(p)
    if context is None:
        return None
    stage = context.get("feyd_track_stage")
    return stage if isinstance(stage, str) and stage else None


#: Our ``feyd_track_stage`` ids whose space lists ``PlaceSpyCustomAbility``
#: (training indices 2, 5 and 7; ``_TRAINING_SPACE_DEFS``).
TRAINING_SPY_STAGES: Final = ("first_spy", "second_spy", "final")


def training_spy_grant_pending(p: Profile) -> bool:
    """Feyd's half of ``PlaceSpyCustomAbility``'s ``HasCustomAbility``.

    ``PlaceSpyCustomAbility.Cost`` = ``HasCustomAbility``
    (spec §3.4); ``ChangeRankBonuses`` grants it on reaching
    a spy space (§3.2). Ours: the own Agent turn holds one of
    ``TRAINING_SPY_STAGES``. The ``PlaceSpyCustomAbility`` port lives in
    ``abilities/generic.py``, which also owns the conflict-reward grant
    (Seize Spice Refinery 1st, Test of Loyalty 1st); its ``meets_cost``
    should call this.
    """

    return _feyd_stage(p) in TRAINING_SPY_STAGES


# ---------------------------------------------------------------------------
# SignetAbility and DisciplineAbility (the base classes of the signets)
# ---------------------------------------------------------------------------


@port(_AA + "signet")
class SignetAbility(DeferredAbility):
    """``ActivatedAbilities.SignetAbility`` (abstract; spec §0.1.6).

    ``constructor`` sets ``AbilityTiming = Agent``;
    ``IsUnexhausted`` = true; ``RunCopiesTogether`` =
    false; ``Cost`` = ``HasSignet``.
    """

    timing: ClassVar[Timing] = Timing.AGENT

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SignetAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``SignetAbility.Cost``: ``new HasSignet``."""

        return _has_signet_icon(p)


@port(_AA + "original.discipline")
class DisciplineAbility(SignetAbility):
    """``ability.activated.original.discipline`` (spec §9.2).

    ``constructor``: ``WillClearUndo = true``.
    """

    contextually_deferred: ClassVar[bool] = True

    def meets_cost(self, p: Profile) -> bool:
        """``DisciplineAbility.Cost``: Signet then ``HasDrawableCard``.

        ``HasDrawableCard`` (name-level read, as ``generic``): a card in the
        draw pile or one to reshuffle.
        """

        me = p.ctx.me
        return super().meets_cost(p) and p.ctx.deck_size + len(me.discard_pile) > 0

    def can_run_immediately(self, p: Profile) -> bool:
        """``DisciplineAbility.CanRunImmediately``.

        ``owner == null or pl is not Player`` (never: the leader belongs to
        the seat) -> true; ``!pl.IsInPlayerTurn(AgentTurn)`` -> true; else
        ``!pl.DeferredThresholdReached()``.
        """

        if not _in_agent_turn(p):
            return True
        return not deferred_threshold_reached(p)

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DisciplineAbility.ValueForPlayer`` (no MeetsCost)."""

        s = Summer()
        s.add("Discipline Draw", p.card_draw_value())
        s.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        return s


# ---------------------------------------------------------------------------
# Feyd-Rautha Harkonnen (spec §3)
# ---------------------------------------------------------------------------


@port(_AU + "devious_strength")
class DeviousStrengthAbility(DeferredAbility):
    """``Uprising.DeviousStrengthAbility`` (spec §3.1): recall a Spy for +2
    strength in the Reveal turn."""

    timing: ClassVar[Timing] = Timing.REVEAL  # constructor

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DeviousStrengthAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``IsInRevealTurn`` -> ``HasAtLeastSpiesOnBoard(1)``
        -> ``HasUnitsDeployed<Unit>.AtLeast(1)``."""

        return (
            _in_reveal_turn(p) and _deployed_spies(p) >= 1 and _deployed_units(p) >= 1
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DeviousStrengthAbility.ValueForPlayer`` (no AI caller).

        Both terms are inside the ``MeetsCost`` test.
        """

        s = Summer()
        if self.meets_cost(p):
            s.add("Recall Spy Value", p.recall_spy_value().sum)
            s.add("2 Strength Value", p.strength_value(2, False))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DeviousStrengthAbility.Evaluate`` (spec §3.1).

        ``request.infos[0]``: the deployed spies (SPY entities). In the final
        round the ability is used ("Last Round") unless 3 spies are out and the
        Conflict is Battle for Arrakeen; otherwise (or then) only when the
        interest reaches the upper posture bound with an opponent's estimate
        within 5 (strict), or the lower bound with one within 2. The answer is
        the spy on the worst post at the sentinel 100.
        """

        reason: str | None = None
        if p.is_final_round():
            if _deployed_spies(p) < 3:
                reason = "Last Round"
            else:
                current = p.ctx.current_conflict_id
                arch = None
                if current is not None:
                    arch = conflict_entity(current, p.ctx.choam).short
                if arch != _BATTLE_FOR_ARRAKEEN:  # ``CurrentConflict?.ArchID !=``
                    reason = "Last Round"
        if reason is None:
            lower, upper = p.conflict_posture_bounds()
            interest = p.current_conflict_interest().sum
            mine = p.est_strength().sum
            opponents = [
                p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents
            ]
            # a failed high test still tries the mid test.
            if interest >= upper and any(abs(mine - s) < 5 for s in opponents):
                reason = "High conflict interest"
            elif interest >= lower and any(abs(mine - s) < 2 for s in opponents):
                reason = "Mid conflict interest"
            else:
                return Answer(0.0, None, "Devious Strength: not used")
        s = Summer()
        s.add("2 Strength Value", p.strength_value(2, False))
        spy, _ = p.recall_spy(_targets(request, 0, Kind.SPY))
        if spy is None:
            return Answer(0.0, None, "Devious Strength: no spy")
        s.add(f"Remove spy {spy.ref}", p.recall_spy_value().sum)  # only logged
        return Answer(100.0, ((spy.ref,),), f"Devious Strength | {reason}")


@port(_TU + "personal_training_setup")
class PersonalTrainingSetupAbility(TriggeredAbility):
    """``PersonalTrainingSetupAbility`` (``GameStarted``: builds the training
    track; no prompt, no AI hook)."""


@port(_AU + "personal_training")
class PersonalTrainingAbility(SignetAbility):
    """``Uprising.PersonalTrainingAbility`` (Feyd's signet; spec §3.3).

    Explicit (inherited); the prompt is forced, exactly one next space (``Targets``:
    forced 1, max 1, min -1).
    """

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Signet then ``TrainingTrack != null and CurrentRank < 7``."""

        return (
            super().meets_cost(p)
            and has_training_track(p)
            and training_rank(p) < 7  # literal
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PersonalTrainingAbility.ValueForPlayer``.

        The summer of the best next space (strictly above the best so far, starting at
        0.0); the base (0) at the last rank or when no next space is worth more than 0.
        ``with_entities`` is unused.
        """

        result = Summer()
        if not has_training_track(p):
            return result
        best = 0.0
        for space in training_next_spaces(p):
            value = training_space_value(p, space)
            if value.sum > best:
                result = value
                best = value.sum
        return result

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PersonalTrainingAbility.Evaluate``.

        ``request.infos[0]``: the next training spaces in ``NextIndices`` order
        (``training_space_entity``). Strict argmax; the first space lands even
        at a value <= 0.
        """

        stored: Answer | None = None
        for space in _targets(request, 0, Kind.SPACE):
            value = training_space_value(p, space).sum
            if stored is None or value > stored.value:
                stored = Answer(
                    value,
                    ((space.ref,),),
                    f"PersonalTraining Space {_training_index(space)} | {value}",
                )
        if stored is None:
            return Answer(0.0, None, "PersonalTraining: no space")
        return stored


@port(_AU + "personal_training_trash")
class PersonalTrainingTrashAbility(TrashCustomAbility):
    """``Uprising.PersonalTrainingTrashAbility`` (training indices 3 and 4;
    spec §3.4). ``Evaluate``/``ValueForPlayer`` are ``TrashAbility``'s: the
    worst junk card at ``GetCardToTrash(targets, 1.0)``, else an empty pick at
    1.0 (quirk kept). Timing None."""

    #: Our ``feyd_track_stage`` ids whose reward is this custom grant.
    GRANT_STAGES: ClassVar[tuple[str, ...]] = ("mid_trash", "late_trash")

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``PersonalTrainingTrashAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: the training reward is pending.

        Our engine's pending stage stands for the app's custom grant
        (``_feyd_stage``).
        """

        return _feyd_stage(p) in self.GRANT_STAGES

    def meets_cost(self, p: Profile) -> bool:
        """``TrashCustomAbility.Cost``: ``HasTrashableCard`` then
        ``HasCustomAbility``."""

        return _has_trashable_card(p) and self.has_custom_ability(p)


@port(_AU + "personal_training_pay_to_trash")
class PersonalTrainingPayToTrashAbility(PersonalTrainingTrashAbility):
    """``Uprising.PersonalTrainingPayToTrashAbility`` (training index 1).

    ``BeginExecution`` pays the Solari before trashing, even when
    the AI's pick is empty (spec §3.4; our engine cannot pay without trashing:
    the window maps an empty pick to the decline).
    """

    GRANT_STAGES: ClassVar[tuple[str, ...]] = ("paid_trash",)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``TrashCustomAbility.Cost`` then
        ``HasResources.AtLeast(Solari, 1)``."""

        return super().meets_cost(p) and p.ctx.me.resources.solari >= 1


# ---------------------------------------------------------------------------
# Gurney Halleck (spec §4)
# ---------------------------------------------------------------------------


@port(_AU + "warmaster")
class WarmasterAbility(SignetAbility):
    """``Uprising.WarmasterAbility`` (Gurney's signet: +1 troop; spec §4.1).

    Runs as an immediate (static picker, no AI call); if asked, the default
    ``DeferredAbility`` evaluate gives 1.0 (Explicit, no ``DeferValue``).
    """

    always_run_immediately: ClassVar[bool] = True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WarmasterAbility.ValueForPlayer``."""

        s = Summer()
        s.add("Troop", p.troop_value(1, False))
        return s


@port(_TU + "always_smiling")
class AlwaysSmilingAbility(TriggeredAbility):
    """``AlwaysSmilingAbility`` (+1 Persuasion at 6 strength in the Reveal;
    triggered, no AI hook; spec §4.2). Its only AI trace is Gurney's 6-strength
    top-up in ``GetUnitsToDeploy`` (profile)."""


# ---------------------------------------------------------------------------
# Lady Amber Metulli (spec §8)
# ---------------------------------------------------------------------------


@port(_AU + "desert_scouts")
class DesertScoutsAbility(DeferredAbility):
    """``Uprising.DesertScoutsAbility`` (retreat one troop in the Reveal; spec
    §8.1). No targets: the engine retreats the first troop."""

    timing: ClassVar[Timing] = Timing.REVEAL  # constructor

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``DesertScoutsAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasUnitsDeployed<Troop>.Any``.

        Bloodlines Commanders are troops (bloodlines-systems.md §1.1, §2.3).
        """

        return p.conflict_troop_count() > 0

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``DesertScoutsAbility.ValueForPlayer`` (no AI caller).

        ``Math.Min(0.5 * deployed units, 1.0)`` (f64 literals 0.5 and 1.0).
        """

        s = Summer()
        s.add(
            "Desert Scouts Reveal Troop Retreat Bonus",
            min(0.5 * _deployed_units(p), 1.0),
        )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DesertScoutsAbility.Evaluate``.

        ``GetTroopsToRetreat(1) > 0`` -> 1.0 with an empty response; else nothing.
        """

        if p.troops_to_retreat(1) > 0:
            return Answer(1.0, (), "Desert Scouts | 1")
        return Answer(0.0, None, "Desert Scouts: keep troops")


@port(_AU + "fill_coffers")
class FillCoffersAbility(SignetAbility):
    """``Uprising.FillCoffersAbility`` (Amber's signet: +1 spice with an
    Alliance; the +1 Solari is the trigger below; spec §8.2).

    ``RunCopiesTogether`` = true; runs by itself (no choice).
    """

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Signet then ``HasFactionAlliance(None)``."""

        return super().meets_cost(p) and bool(p.ctx.me.alliance_faction_ids)

    def can_run_immediately(self, p: Profile) -> bool:
        """``FillCoffersAbility.CanRunImmediately``: true."""

        return True

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``FillCoffersAbility.ValueForPlayer``.

        ``InAlliance(None)``: any Alliance token.
        """

        s = Summer()
        s.add("Fill Coffers Solari", p.solari_value(1))
        if p.ctx.me.alliance_faction_ids:
            s.add("Fill Coffers Spice", p.spice_value(1))
        return s


@port(_TU + "fill_coffers_triggered")
class FillCoffersTriggeredAbility(TriggeredAbility):
    """``FillCoffersTriggeredAbility`` (+1 Solari on ``SignetIconGained``;
    no prompt, no AI hook)."""


# ---------------------------------------------------------------------------
# Lady Jessica and Reverend Mother Jessica (spec §5, §6)
# ---------------------------------------------------------------------------


@port(_TU + "other_memories_setup")
class OtherMemoriesSetupAbility(TriggeredAbility):
    """``OtherMemoriesSetupAbility`` (``GameStarted``: the Memories area; no
    prompt, no AI hook)."""


@port(_TU + "other_memories_triggered")
class OtherMemoriesTriggeredAbility(TriggeredAbility):
    """``OtherMemoriesTriggeredAbility`` (Agent on a BG-icon space grants
    ``OtherMemoriesAbility``; no prompt, no AI hook)."""


@port(_AU + "other_memories")
class OtherMemoriesAbility(DeferredAbility):
    """``Uprising.OtherMemoriesAbility`` (return the memories, draw, flip;
    spec §5.3). Timing None."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``OtherMemoriesAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: granted by the BG-space trigger.

        Ours: the own Agent turn's ``pending_leader_ability`` flag (set when
        the Lady Jessica face sends an Agent to a Bene Gesserit space).
        """

        context = _agent_frame(p)
        return context is not None and context.get("pending_leader_ability") is True

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasCustomAbility``."""

        return self.has_custom_ability(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OtherMemoriesAbility.Evaluate``: 100 iff
        ``LadyJessicaReturnMemories``, else nothing (declined)."""

        if p.lady_jessica_return_memories():
            return Answer(100.0, (), "Other Memories | 100")
        return Answer(0.0, None, "Other Memories: keep")


@port(_AU + "spice_agony")
class SpiceAgonyAbility(SignetAbility):
    """``Uprising.SpiceAgonyAbility`` (Lady Jessica's signet: 1 spice ->
    intrigue, a troop becomes a memory; spec §5.5)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SpiceAgonyAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Signet then ``HasResources.AtLeast(Spice, 1)``."""

        return super().meets_cost(p) and p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceAgonyAbility.ValueForPlayer`` (no affordability
        test). ``GetNextTroops(1).Any()``: a troop in supply."""

        s = Summer()
        s.add("Spice Cost", p.spice_value(-1))
        s.add("Intrigue", p.intrigue_value())
        if p.ctx.me.troops_supply > 0:
            s.add("Spice Agony Mod", p.C.LadyJessicaSpiceAgonyMod)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceAgonyAbility.Evaluate``: 100 iff ``Spice > 1`` or the Swordmaster."""

        me = p.ctx.me
        if me.resources.spice > 1 or me.swordmaster_acquired:
            return Answer(100.0, (), "Spice Agony | 100")
        return Answer(0.0, None, "Spice Agony: keep spice")


@port(_AU + "water_of_life_signet")
class WaterOfLifeSignetAbility(SignetAbility):
    """``Uprising.WaterOfLifeSignetAbility`` (Reverend Mother's signet: 1
    spice -> 1 water; spec §6.1)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``WaterOfLifeSignetAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Signet then ``Spice >= 1``."""

        return super().meets_cost(p) and p.ctx.me.resources.spice >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``WaterOfLifeSignetAbility.ValueForPlayer``.

        With a space that leaves no spice for the signet after its own cost,
        the value is 0.
        """

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 1
        ):
            s.add(
                "Water Of Life Signet Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return s
        s.add("Water Of Life Spice Cost", p.spice_value(-1))
        s.add("Water Of Life Water", p.water_value(1))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``WaterOfLifeSignetAbility.Evaluate``: used iff
        ``Spice(-1) + Water(1) > 0`` (``MakeChoice``)."""

        s = Summer()
        s.add("Spice Cost", p.spice_value(-1))
        s.add("Water", p.water_value(1))
        return Answer(s.sum, (), "Water Of Life")


def deployed_faction_space(p: Profile) -> Entity | None:
    """``ReverendMotherAbility.DeployedFactionSpace``.

    ``DeployedFactionAction``: the first deployed Agent that is not exhausted and stands
    on a space whose ``ActionIcon & ~1 == 6`` (BG 6 or Fremen 7).

    UNTRACED (spec §17.5): whether the unexhausted Agent is always the one
    sent this turn. Read as this Agent turn's space (the own open
    ``agent_effects`` frame); none outside an Agent turn.
    """

    # UNTRACED: "not exhausted" read as "sent this Agent turn" (spec §17.5).
    context = _agent_frame(p)
    if context is None:
        return None
    space_id = context.get("space_id")
    if not isinstance(space_id, str) or not space_id:
        return None
    space = space_entity(space_id, p.ctx.board)
    if space.attr("AgentIcon") in ("BeneGesserit", "Fremen"):
        return space
    return None


@port(_AU + "reverend_mother")
class ReverendMotherAbility(DeferredAbility):
    """``Uprising.ReverendMotherAbility`` (pay 1 water to repeat the BG or
    Fremen space; spec §6.2). ``OncePerTurn``, ``HideInvalidDeferred``."""

    timing: ClassVar[Timing] = Timing.AGENT  # constructor

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ReverendMotherAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Water, 1)`` then
        ``DeployedFactionAction(player)?.Parent is Space``."""

        return p.ctx.me.resources.water >= 1 and deployed_faction_space(p) is not None

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ReverendMotherAbility.ValueForPlayer``.

        Merged by ``SpaceAbility`` with ``[thisSpace]`` (spec §6.3). With a
        space whose own water cost leaves no water for the repeat: 0. Without
        a space only the water cost is added (every archetype test fails).
        """

        s = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.WATER, 1
        ):
            s.add(
                "Reverend Mother Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return s
        s.add("Reverend Mother WaterCost", p.water_value(-1))
        arch = None if space is None else space.short
        if arch == _SECRETS:
            s.add("Reverend Mother Intrigue", p.intrigue_value())
        elif arch == _DESERT_TACTICS:
            s.add("Reverend Mother Troop", p.troop_value(1, False))
            s.add("Reverend Mother Trash", p.trash_card_value())
        elif arch == _FREMKIT:
            s.add("Reverend Mother Draw", p.card_draw_value_with_buy_gains())
        elif arch == _ESPIONAGE:
            s.add("Reverend Mother Draw", p.card_draw_value_with_buy_gains())
            s.add("Reverend Mother Spy", p.spy_value().sum)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReverendMotherAbility.Evaluate``.

        ``-Water(1)`` plus the merged ``ValueForPlayer(player, [])`` of every
        ``SpaceAbility`` of the visited space, which already holds this ability's own
        term through ``SpaceAbility`` (water counted again; quirk kept). Used iff the
        sum is > 0.
        """

        s = Summer()
        space = deployed_faction_space(p)
        s.add("Water Cost", p.water_value(-1))
        if space is not None:
            for ability in abilities_of(space):
                if isinstance(ability, SpaceAbility):
                    s.merge(ability.value_for_player(p, ()))
        return Answer(s.sum, (), "Reverend Mother")


# ---------------------------------------------------------------------------
# Lady Margot Fenring (spec §7)
# ---------------------------------------------------------------------------


@port(_AU + "arrakis_informant")
class ArrakisInformantAbility(SignetAbility):
    """``Uprising.ArrakisInformantAbility`` (Margot's signet: a Spy on a City
    post; spec §7.2). The post is chosen later by ``PlaceSpy``'s evaluator
    over the posts passing ``is_circle_observation_post``."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ArrakisInformantAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ArrakisInformantAbility.ValueForPlayer``.

        Nothing with more than 2 spies out; otherwise, when any Circle post exists on
        the board (free or not; always true in Uprising): ``SpyValue`` scaled by
        ``ArrakisInformantMod``.
        """

        s = Summer()
        if _deployed_spies(p) > 2:
            return s
        posts = p.ctx.observation_post_ids()
        if any(is_circle_observation_post(post, p.ctx.board) for post in posts):
            s.add("Place Spy Value", p.spy_value().sum)
            s.multiply("Arrakis Informant Spy", p.C.ArrakisInformantMod)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ArrakisInformantAbility.Evaluate``.

        ``SpyValue`` with an empty response; ``GetSpyAIResponses`` only feeds a
        log line and is not computed (as ``PlaceSpyAbility``'s port).
        """

        return Answer(p.spy_value().sum, (), "Arrakis Informant")


@port(_TU + "loyalty")
class LoyaltyAbility(TriggeredAbility):
    """``LoyaltyAbility`` (2 spice on reaching BG 2; no prompt). The AI side
    is Margot's term in ``GetGainInfluenceValue`` (profile)."""


# ---------------------------------------------------------------------------
# Muad'Dib (spec §9)
# ---------------------------------------------------------------------------


@port(_AU + "lead_the_way")
class LeadTheWayAbility(DisciplineAbility):
    """``Uprising.LeadTheWayAbility`` (Muad'Dib's signet: draw a card; no
    overrides of ``DisciplineAbility``; spec §9.2)."""


@port(_AU + "unpredictable_foe")
class UnpredictableFoeAbility(GainIntrigueAbility):
    """``Uprising.UnpredictableFoeAbility`` (an intrigue card with a sandworm
    in the Conflict; spec §9.1). Explicit, auto-run, Evaluate 100 (inherited
    from ``GainIntrigueAbility``)."""

    timing: ClassVar[Timing] = Timing.REVEAL  # constructor

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``IsInPlayerTurn(RevealTurn) and
        HasDeployedSandworms``."""

        return _in_reveal_turn(p) and p.ctx.me.sandworms_conflict > 0


# ---------------------------------------------------------------------------
# Princess Irulan (spec §10)
# ---------------------------------------------------------------------------


@port(_TU + "imperial_birthright")
class ImperialBirthrightAbility(TriggeredAbility):
    """``ImperialBirthrightAbility`` (Emperor 2 grants the deferred intrigue
    below; no prompt, no AI hook)."""


@port(_AU + "imperial_birthright_deferred")
class ImperialBirthrightDeferredAbility(GainIntrigueAbility):
    """``Uprising.ImperialBirthrightDeferredAbility`` (spec §10.1).

    Timing None; ``IsUnexhausted`` = true; auto-run and Evaluate
    100 inherited from ``GainIntrigueAbility``.
    """

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``.

        Judgement: our engine resolves Imperial Birthright automatically when
        Emperor influence reaches 2 (``rules/influence.py``), so the grant is
        never held at a decision (as ``deferred_threshold_reached`` assumes).
        """

        return False

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``GainIntrigue.Cost`` (NoCost) then
        ``HasCustomAbility``. Gates the inherited ``ValueForPlayer``."""

        return self.has_custom_ability(p)


@port(_AU + "chroniclers_insight")
class ChroniclersInsightAbility(SignetAbility):
    """``Uprising.ChroniclersInsightAbility`` (Irulan's signet: acquire a
    cost-1 card to hand, or trash a hand card for 2 spice if it cost 1 or
    more; spec §10.2)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ChroniclersInsightAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: Signet then ``HandCards().Any() or
        GetAcquireTargets(player).Any()``."""

        if not super().meets_cost(p):
            return False
        return bool(p.ctx.hand) or bool(chroniclers_acquire_targets(p))

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ChroniclersInsightAbility.ValueForPlayer``.

        The best ``AcquireValue`` among the cost-1 targets (``Enumerable.Max``); the
        trash option is not valued.
        """

        s = Summer()
        targets = chroniclers_acquire_targets(p)
        if targets:
            s.add(
                "Imperium Row Card",
                max(p.acquire_value(card).sum for card in targets),
            )
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChroniclersInsightAbility.Evaluate`` (fixed priority).

        ``request.infos[1]``: the hand cards of the trash option (the
        dependent list at key 1). In order: the best junk card with a cost
        (``GetCardToTrash(paid, 0.0)``), the best junk card
        (``GetCardToTrash(hand, 0.0)``), the cost 1-2 card with the lowest
        Reveal value at 1.0 (``UnityLinqExtensions.MinBy``: the
        first strict minimum), the acquire option at 1.0, else the first
        Dagger / Dune / Reconnaissance at the last ``GetCardToTrash`` value.
        """

        # UNTRACED: option enabling of the custom choice (spec §17.3); the
        # hand list is read from the request as the app reads its targets.
        hand = _targets(request, 1, Kind.CARD)
        paid = [c for c in hand if c.int_attr("PersuasionCost") > 0]
        card, value = p.card_to_trash(paid, 0.0)  # minTrashValue 0.0
        if card is not None:
            return Answer(value, ((1,), (card.ref,)), "Trash value with cost >= 1")
        card, value = p.card_to_trash(hand, 0.0)
        if card is not None:
            return Answer(value, ((1,), (card.ref,)), "Trash value with cost == 0")
        cheap = [c for c in paid if c.int_attr("PersuasionCost") < 3]
        if cheap:
            best: Entity | None = None
            best_value = 0.0
            for candidate in cheap:  # MinBy: first strict minimum
                reveal = value_for_reveal_abilities(candidate, p).sum
                if best is None or reveal < best_value:
                    best, best_value = candidate, reveal
            assert best is not None
            return Answer(1.0, ((1,), (best.ref,)), "Trash cost == 1 or 2")
        if chroniclers_acquire_targets(p):
            return Answer(1.0, ((0,),), "Chroniclers Insight | acquire")
        for short in (_DAGGER, _DUNE, _RECONNAISSANCE):  # /4/5
            specific = next((c for c in hand if c.short == short), None)
            if specific is not None:
                return Answer(value, ((1,), (specific.ref,)), "Trash specific card")
        return Answer(0.0, None, "Chroniclers Insight: nothing")


@port(_AU + "chroniclers_insight_acquire")
class ChroniclersInsightAcquireAbility(DeferredAbility):
    """``Uprising.ChroniclersInsightAcquireAbility`` (the acquire half of
    Chronicler's Insight, started by its ``ResumeExecution``; spec §10.3).

    ``constructor``: ``WillClearUndo``, ``HideInvalidDeferred``, timing
    None.
    """

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ChroniclersInsightAcquireAbility.SelectionMode``:
        Explicit."""

        return SelectionMode.EXPLICIT

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: implicit ``(true, match)``.

        UNTRACED (spec §17.2): what keeps the ability out of the prompts when
        Chronicler's Insight's acquire option was not chosen; ask it only
        after that option.
        """

        # UNTRACED: listing gate of an always-payable leader ability.
        return True

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChroniclersInsightAcquireAbility.Evaluate``.

        ``request.infos[0]``: the cost-1 cards. ``AcquireValue + 100``, strict
        argmax (the first card lands); option 0 of the destination picker.
        """

        stored: Answer | None = None
        for card in _targets(request, 0, Kind.CARD):
            value = p.acquire_value(card).sum + 100.0
            if stored is None or value > stored.value:
                stored = Answer(value, ((card.ref,), (0,)), f"Acquire {card.ref}")
        if stored is None:
            return Answer(0.0, None, "Chroniclers Insight acquire: no card")
        return stored


# ---------------------------------------------------------------------------
# Shaddam Corrino IV (CHOAM; spec §11)
# ---------------------------------------------------------------------------


@port(_TU + "sardaukar_commander")
class SardaukarCommanderAbility(TriggeredAbility):
    """``SardaukarCommanderAbility`` (sets the Sardaukar contracts aside for
    Shaddam; no prompt). They join his contract options
    (``generic._contract_options``)."""


@port(_TU + "emperor_of_the_known_universe_suppress")
class EmperorOfTheKnownUniverseSuppressAbility(TriggeredAbility):
    """``EmperorOfTheKnownUniverseSuppressAbility`` (no deploying on the
    signet turn; no prompt). The AI trace is ``DeployUnitsAbility``'s
    inverted Shaddam test (generic)."""


@port(_AU + "emperor_of_the_known_universe_signet")
class EmperorOfTheKnownUniverseSignetAbility(SignetAbility):
    """``Uprising.EmperorOfTheKnownUniverseSignetAbility`` (Shaddam's signet:
    +1 Solari and +1 troop, or 3 Solari -> +1 influence; spec §11.3).
    Explicit (inherited)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EmperorOfTheKnownUniverseSignetAbility.ValueForPlayer``.

        ``Math.Max(Solari(1) + Troop(1), Solari(-3) + best influence)`` (no
        Solari test, no Round / 3), then the posture penalty: interest strictly
        above the upper bound -> ``ShaddamCorrinoIVSignetHigh``, else strictly
        above the lower bound -> ``ShaddamCorrinoIVSignetMid``.
        """

        c = p.C
        s = Summer()
        a = p.solari_value(1) + p.troop_value(1, False)
        b = p.solari_value(-3) + gain_any_influence_value(p, 1).sum
        s.add("Emperor of the Known Universe", max(a, b))
        lower, upper = p.conflict_posture_bounds()
        interest = p.current_conflict_interest().sum
        if interest > upper:
            s.add("Signet High Conflict Interest", c.ShaddamCorrinoIVSignetHigh)
        elif interest > lower:
            s.add("Signet Mid Conflict Interest", c.ShaddamCorrinoIVSignetMid)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``EmperorOfTheKnownUniverseSignetAbility.Evaluate``.

        Option 0 (``Solari(1) + Troop(1)``) lands first; then each faction
        track of ``request.infos[1]`` (the dependent list of option 1, empty
        when that option is not offered) in request order:
        ``GetGainInfluenceValue(f, 1) + Solari(-3) + Round / 3.0``, kept only
        when strictly better.
        """

        s0 = Summer()
        s0.add("Solari", p.solari_value(1))
        s0.add("Troop", p.troop_value(1, False))
        stored = Answer(s0.sum, ((0,),), "Emperor of the Known Universe | option 0")
        pay3 = p.solari_value(-3)
        round_third = float(p.ctx.round_number) / 3.0  # literal 3.0
        # UNTRACED: whether option 1 keeps its tracks when Solari < 3 (spec
        # §17.3); the request carries them only when the pay option is offered.
        for track in _targets(request, 1, Kind.TRACK):
            st = Summer()
            st.merge(p.gain_influence_value(track.ref, 1, -1, False))
            st.add("Pay 3 Solari", pay3)
            st.add("Round / 3", round_third)
            if st.sum > stored.value:
                stored = Answer(
                    st.sum,
                    ((1,), (track.ref,)),
                    f"Emperor of the Known Universe | {track.ref}",
                )
        return stored


# ---------------------------------------------------------------------------
# Staban Tuek (spec §12)
# ---------------------------------------------------------------------------


@port(_TU + "limited_allies")
class LimitedAlliesAbility(TriggeredAbility):
    """``LimitedAlliesAbility`` (no Diplomacy in the starting deck; setup,
    no AI hook)."""


@port(_TU + "smuggle_spice")
class SmuggleSpiceAbility(TriggeredAbility):
    """``SmuggleSpiceAbility`` (+1 spice when another seat visits a watched
    Maker space; no prompt). The AI side is Staban's Maker post term in
    ``PostValue`` (profile)."""


@port(_AU + "unseen_network")
class UnseenNetworkAbility(SignetAbility):
    """``Uprising.UnseenNetworkAbility`` (Staban's signet: a Spy anywhere,
    then a paid follow-up by post; spec §12.2). The post is chosen by
    ``PlaceSpyEvaluator`` with ``UnseenNetwork = true``
    (``best_post(posts, unseen_network=True)``)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``UnseenNetworkAbility.SelectionMode``: Explicit."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``UnseenNetworkAbility.ValueForPlayer``."""

        s = Summer()
        s.add("Unseen Network Mod", p.C.StabanTuekUnseenNetworkMod)
        if _deployed_spies(p) <= 2:  # skipped with more than 2
            s.add("Place Spy Value", p.spy_value().sum)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UnseenNetworkAbility.Evaluate``: ``SpyValue`` with an
        empty response (as Arrakis Informant)."""

        return Answer(p.spy_value().sum, (), "Unseen Network")


def _staban_bonus_post(p: Profile) -> str | None:
    """The post of the Unseen Network Spy whose paid follow-up is pending.

    ``UnseenNetworkAbility.EmitSequence`` grants the Landsraad follow-up for a Pentagon
    post and the Influence follow-up for an influence-icon post; ours keeps the post in
    the ``staban_bonus_post`` context until paid or declined, and splits the posts with
    the same rule (``LANDSRAAD_POST_IDS`` / ``FACTION_POST_IDS``).
    """

    context = _agent_frame(p)
    if context is None:
        return None
    post = context.get("staban_bonus_post")
    return post if isinstance(post, str) and post else None


@port(_AU + "unseen_network_landsraad")
class UnseenNetworkLandsraadAbility(DeferredAbility):
    """``Uprising.UnseenNetworkLandsraadAbility`` (1 spice -> 3 Solari after a
    Landsraad post; timing None; spec §12.3)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``UnseenNetworkLandsraadAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: a Landsraad (Pentagon) post was used."""

        post = _staban_bonus_post(p)
        return post is not None and post in LANDSRAAD_POST_IDS

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasCustomAbility`` then ``Spice >= 1``."""

        return self.has_custom_ability(p) and p.ctx.me.resources.spice >= 1

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UnseenNetworkLandsraadAbility.Evaluate``: used iff
        ``Spice(-1) + Solari(3) > 0``."""

        s = Summer()
        s.add("Pay Spice", p.spice_value(-1))
        s.add("Gain 3 Solari", p.solari_value(3))
        return Answer(s.sum, (), "Unseen Network Landsraad")


@port(_AU + "unseen_network_influence")
class UnseenNetworkInfluenceAbility(DeferredAbility):
    """``Uprising.UnseenNetworkInfluenceAbility`` (2 Solari -> intrigue after a
    faction post; timing None; ``WillClearUndo``; spec §12.3)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``UnseenNetworkInfluenceAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def has_custom_ability(self, p: Profile) -> bool:
        """``HasCustomAbility(this)``: an influence-icon (faction) post."""

        post = _staban_bonus_post(p)
        return post is not None and post in FACTION_POST_IDS

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasCustomAbility`` then ``Solari >= 2``."""

        return self.has_custom_ability(p) and p.ctx.me.resources.solari >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UnseenNetworkInfluenceAbility.Evaluate``: used iff
        ``Solari(-2) + IntrigueValue > 0``."""

        s = Summer()
        s.add("Pay 2 Solari", p.solari_value(-2))
        s.add("Intrigue", p.intrigue_value())
        return Answer(s.sum, (), "Unseen Network Influence")
