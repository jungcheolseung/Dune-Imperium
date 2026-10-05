"""Intrigue card abilities (Plot, Combat, Endgame) — spec/intrigues.md.

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``). The app's
chain is ``PlayAbility`` -> ``IntrigueAbility`` -> ``StrengthIntrigueAbility``
(every Uprising combat intrigue) and ``CunningTrashAbility`` ->
``TrashAbility`` (``worm-canis.dll.cs``); this module mirrors it on top of
``abilities/generic.py``.

Request / answer encoding (what a window builds and what ``evaluate`` reads).
``request.infos[i]`` is the app's target information ``i`` of the ability;
entity targets are ``entities`` (TRACK = faction track, ref our faction id;
CARD = personal card; SPY = spy on a post; CONTRACT; POST), custom choices and
troops are ``options``: a ``ChooseOne`` lists the option ints offered and a
troop list gives one index per troop (there are no troop entities; as in
``DeployUnitsAbility``), the response naming the first ``n`` indices. Per card
(only the infos the ability reads):

- Backed by CHOAM (Plot), Change Allegiances, Imperium Politics, Buy Access,
  Opportunism, Questionable Methods: ``infos[0]`` faction tracks.
- Sietch Ritual: ``infos[0]`` hand cards (discard), ``infos[1]`` tracks.
- Impress, Inspire Awe, Manipulate: ``infos[0]`` cards (acquirable / Row).
- Devour: ``infos[0]`` trash candidates (with a sandworm in the Conflict).
- Find Weakness, Spring the Trap: ``infos[0]`` own spies.
- Leverage: ``infos[0]`` contracts (``GainContractAbility.ContractEvaluate``).
- Tactical Option: ``infos[0].options`` the ``ChooseOne`` (0 = +2 swords, 1 =
  retreat); ``infos[1].options`` the retreat option's dependent troops.
- Go to Ground, Reach Agreement: ``infos[0].options`` troops; Reach Agreement
  ``infos[1]`` contracts.
- Detonation: with the Shield Wall standing ``infos[0].options`` = (0 wall, 1
  deploy) and ``infos[1].options`` the deploy option's garrison troops;
  without it ``infos[0].options`` the troops.
- Special Mission: with a free City post (``CanDeployOnCircle``) and a spy out,
  ``infos[0].options`` = (0 place, 1 recall) and ``infos[1]`` the recall
  option's spies; with no free City post ``infos[0]`` the spies.
- Every other card reads no target info.

Answers follow ``WormAIChoiceSelectionWithTargets`` (spec §1, ``_Choice``):
``Answer.response is None`` = nothing stored (value 0); otherwise one item per
stored ``TargetResponse`` in order — ``(n,)`` for ``IntTargetResponse(n)``,
``(ref, ...)`` (or troop indices) for ``EntityListTargetResponse``; ``()`` is
"play it" with an empty response list. Dual cards: a window evaluates the half
``ability_for_prompt`` names (``MakeChoice`` lambdas ``b__12_2``/``b__12_3``).

Engine-side members: ``meets_cost(p)`` (the ability's ``Cost``),
``can_be_run(p)`` (``CanBeRun`` = MeetsCost; ``HasTargets``/``IsUnexhausted``
are the engine's), ``is_bad_intrigue(p)`` (vslot 87, read by
``Profile.bad_intrigue_cards_in_hand``), ``troop_value(p)`` (vslot 86),
``strength_value(p)``/``combat_value(p)`` (vslots 88/89, read by
``Profile.intrigue_hand_strength_value``), ``timing`` and ``ability_timing``
(the raw ``AbilityTiming``: 0 Plot, 4 Endgame, 5 Combat; ``base.Timing`` has
no Endgame member). The Endgame window helpers are at the end of the module
(§2.3, §8.4: auto-play and ``ScoreBattleIconsPairs``).

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    ResponseItem,
    Timing,
    abilities_of,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    ConflictAbility,
    PlayAbility,
    TrashAbility,
    contract_evaluate,
    space_solari_cost,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    card_entity,
    conflict_entity,
    intrigue_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS, card_id
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.objectives import OBJECTIVES_BY_ID
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.ornithopter import face_up_battle_card_ids
from dune_imperium.rules.spy_placement import observation_post_ids_for_agent_icons

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

# ---------------------------------------------------------------------------
# Constants and shared reads (the app's extension methods, read honestly)
# ---------------------------------------------------------------------------

#: ``AbilityTiming`` values (``worm-canis.dll.cs``): Plot abilities set none.
PLOT_TIMING: Final = 0
#: Immortality's Harvest Cells (``HarvestCellsAbility`` ``.ctor @0x4c74ee0``).
COMBAT_RESOLUTION_TIMING: Final = 3
ENDGAME_TIMING: Final = 4
COMBAT_TIMING: Final = 5

#: ``PlayerTurnTypes``: Undetermined 0, AgentTurn 1, RevealTurn 2, CombatTurn 3,
#: Endgame 4.
_UNDETERMINED: Final = 0
_AGENT_TURN: Final = 1
_REVEAL_TURN: Final = 2
_COMBAT_TURN: Final = 3
_ENDGAME_TURN: Final = 4

#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``;
#: not imported: the profile package imports this one).
_ANY_FACTION: Final = "none"

#: ``StrengthIntrigueAbility::Evaluate``'s ``GetCombinations`` stops after a
#: wall-clock budget (``TickCount - start >= 751``, ``cmp eax, 0x2ef``), checked
#: on every resume after a yield (spec §5.3). The port counts yielded
#: combinations instead, so a decision never depends on the machine. 4096 is
#: ``2**12``: a hand of 12 strength intrigues still enumerates in full, and
#: the app's own budget never binds below about 7 cards (<= 127 combinations).
GET_COMBINATIONS_BUDGET: Final = 4096

_SWORDMASTER: Final = "swordmaster"
_HIGH_COUNCIL: Final = "high_council"
_TSMF_ARCHETYPES: Final = (
    "ImperiumArchetypes.BaseSet.TheSpiceMustFlow",
    "ImperiumArchetypes.Uprising.TheSpiceMustFlowUP",
)
#: Our battle icon ids -> the app's ``BattleIcons`` names.
_APP_BATTLE_ICONS: Final = {
    "crysknife": "Crysknife",
    "desert_mouse": "DesertMouse",
    "ornithopter": "Ornithopter",
    "wild": "Wildcard",
}
_NO_ICON: Final = "None"
_WILDCARD: Final = "Wildcard"
_POST_SPACES: Final = {
    post.post_id: tuple(post.connected_space_ids) for post in OBSERVATION_POSTS
}
#: ``ArrakisInformantAbility::IsCircleObservationPost``: the posts connected to
#: a City space (judgement: the app's "circle" posts are our City posts, the
#: same filter as Special Mission's ``PlaceSpy(agent_icons=(CITY,))``).
_CITY_POSTS: Final = observation_post_ids_for_agent_icons((AgentIcon.CITY,))
#: The turn's own frame (``rules/frames.py``) -> ``IsInPlayerTurn`` type.
_TURN_FRAMES: Final = {
    "turn": _UNDETERMINED,
    "agent_effects": _AGENT_TURN,
    "reveal": _REVEAL_TURN,
    "combat_intrigue": _COMBAT_TURN,
    "endgame_intrigue": _ENDGAME_TURN,
}


def _player_turn(p: Profile) -> int | None:
    """``P.GetAttributeValue(PlayerTurn)``: the type of this seat's open turn.

    Judgement (R4 §2.4): our engine has no ``PlayerTurn`` attribute. The
    turn's own frame sits lowest on the stack (``turn``, ``agent_effects`` or
    ``reveal``; ``combat_intrigue``/``endgame_intrigue`` outside the player
    turns) and follow-up frames above it; the topmost such frame decides, and
    only when this seat owns it. Reads frame kinds and owners only.
    """

    for frame in reversed(p.ctx.state.decision_stack):
        turn = _TURN_FRAMES.get(frame.kind)
        if turn is None:
            continue
        return turn if getattr(frame.decision, "owner", None) == p.ctx.seat else None
    return None


def _in_player_turn(p: Profile, turn: int) -> bool:
    """``WormPlayer::IsInPlayerTurn(turn)``."""

    return _player_turn(p) == turn


def _intrigue_hand_count(p: Profile) -> int:
    """``WormPlayer::get_IntrigueHandCount @0x483ca60``.

    Judgement (R4 open point 4): the held Intrigue cards, including the one
    being evaluated; a face-up Call to Arms is not held.
    """

    return len(p.ctx.intrigue_cards)


def _influence(player: PlayerState, faction: str) -> int:
    """``GetFactionInfluence(F)`` (public)."""

    return int(getattr(player.influence, faction))


def _highest_opponent_rank(p: Profile, faction: str) -> int:
    """``WormFactionTrack::HighestOpponentRank(P)`` (track vslot 37)."""

    return max(_influence(o, faction) for o in p.ctx.opponents)


def _can_gain_faction_influence(player: PlayerState, faction: str) -> bool:
    """``WormPlayer::CanGainFactionInfluence @0x4846040``: rank <= 5, then
    ``MeetsFactionCountRequirements`` (UNTRACED: taken as always true; it
    gates the base game's Ix factions)."""

    return _influence(player, faction) <= 5


def _deployed_spies(p: Profile) -> int:
    """``P.GetDeployedSpies().Count()`` / ``SpyDeployedCount``."""

    return len(p.ctx.me.spy_post_ids)


def _observes(p: Profile, space_id: str) -> bool:
    """``WormSpace.HasObservingSpy(P)``: P's spy on a post seeing the space."""

    return any(space_id in _POST_SPACES.get(post, ()) for post in p.ctx.me.spy_post_ids)


def _open_to(p: Profile, space_id: str) -> bool:
    """``!space.HasAgent || space.HasObservingSpy(P)`` (any seat's agent)."""

    return not p.ctx.space_occupants(space_id) or _observes(p, space_id)


def _space_cost(p: Profile, space_id: str) -> int:
    """The space's runtime ``SolariCost`` (Swordmaster drops to 6)."""

    return space_solari_cost(p, space_entity(space_id, p.ctx.board))


def _persuasion(p: Profile) -> int:
    """``P.GetAttributeValue<int>(Persuasion, 0)``: the live Reveal pool.

    Our engine keeps Persuasion inside the seat's own Reveal frame only (the
    spendable rest after purchases); outside it the pool is 0.
    """

    context = p.ctx.own_frame_context("reveal")
    if context is None:
        return 0
    value = context.get("persuasion")
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _deploy_window(p: Profile) -> bool:
    """``P.GetDeployUnitsAbilities(false).Any()`` @0x48466d0.

    UNTRACED lifetime (spec §13). Judgement: the app grants ``DeployUnits``
    on a Conflict-icon visit; ours is the open deployment allowance of the
    seat's own Agent turn (``pending_combat_deployment``).
    """

    context = p.ctx.own_frame_context("agent_effects")
    return context is not None and context.get("pending_combat_deployment") is True


def _has_drawable_card(p: Profile) -> bool:
    """``HasDrawableCard``: a card to draw, or a discard pile to reshuffle."""

    return p.ctx.deck_size + len(p.ctx.me.discard_pile) > 0


def _trash_targets(p: Profile) -> list[Entity]:
    """``P.FindTrashTargets().OfType<WormImperiumPlayable>()``.

    UNTRACED order (it is shuffled by ``GetCardToTrash`` anyway): hand,
    discard pile, then cards in play — our ``trash_intrigue_card`` targets.
    """

    me = p.ctx.me
    return [
        card_entity(i, p.ctx.seat) for i in (*me.hand, *me.discard_pile, *me.in_play)
    ]


def _count_the_spice_must_flow(p: Profile) -> int:
    """``SecureSpiceTradeAbility::CountTheSpiceMustFlow @0x4c4e060``.

    ``AllImperiumCards.Count(IsTheSpiceMustFlowImperium)``: own draw pile (as a
    multiset), hand, discard pile and cards in play.
    """

    me = p.ctx.me
    ids = list(p.ctx.deck_multiset.elements())
    ids.extend(card_id(i) for i in (*me.hand, *me.discard_pile, *me.in_play))
    return sum(1 for i in ids if CARD_ARCHETYPES.get(i) in _TSMF_ARCHETYPES)


def battle_icon_list(player: PlayerState) -> list[tuple[str, str]]:
    """``WormPlayer.BattleIconList`` with the card behind each icon.

    ``(card id, app icon name)`` for the face-up Objective and won Conflict
    cards, Objective first then Conflicts in the order won (R5 §4.5: paired
    cards are flipped face down and leave the list).
    """

    icons: list[tuple[str, str]] = []
    for battle_card in face_up_battle_card_ids(player):
        objective = OBJECTIVES_BY_ID.get(battle_card)
        icon = (
            objective.battle_icon
            if objective is not None
            else CONFLICTS_BY_ID[battle_card].battle_icon
        )
        if icon is not None:
            icons.append((battle_card, _APP_BATTLE_ICONS[str(icon)]))
    return icons


def _current_conflict(p: Profile) -> Entity | None:
    """``WormMatchExtensions::CurrentConflict``."""

    conflict_id = p.ctx.current_conflict_id
    if conflict_id is None:
        return None
    return conflict_entity(conflict_id, p.ctx.choam)


def _ability_for_placement(conflict: Entity, place: int) -> ConflictAbility | None:
    """``WormConflictPlayable::AbilityForPlacement(place) @0x4829c40``.

    ``Abilities.OfType<ConflictAbility>().FirstOrDefault(ConflictPlace ==
    place)`` (b__0 @0x482a4b0; an ability without the attribute reads 0, so
    place 4 finds nothing).
    """

    for ability in abilities_of(conflict):
        if isinstance(ability, ConflictAbility) and (ability.place or 0) == place:
            return ability
    return None


def _placement_value(p: Profile, conflict: Entity, place: int) -> float:
    """``conflict.AbilityForPlacement(place)?.ValueForPlayer(P, []).Sum ?? 0``."""

    ability = _ability_for_placement(conflict, place)
    if ability is None:
        return 0.0
    return ability.value_for_player(p, ()).sum


def _targets(request: Request, index: int, kind: Kind) -> list[Entity]:
    """``choice.GetTargets<T>(index)`` (or ``GetDependentTargets``)."""

    if index >= len(request.infos):
        return []
    return [e for e in request.infos[index].entities if e.kind is kind]


def _options(request: Request, index: int) -> tuple[int, ...]:
    """The option ints / troop indices of target information ``index``."""

    if index >= len(request.infos):
        return ()
    return request.infos[index].options


def _dsum(values: Sequence[float]) -> float:
    """``Enumerable.Sum`` over doubles: left to right from 0.0 (no compensation)."""

    total = 0.0
    for value in values:
        total += value
    return total


class _Choice:
    """``WormAIChoiceSelectionWithTargets`` (spec §1, ctor @0x4932a00).

    ``UpdateSelectionTargets`` @0x4932c00 and ``UpdateSelectionResponses``
    @0x4932fa0 replace the stored answer when the value is strictly greater
    *or the stored response list is empty* (``ListUtil.IsEmpty``), so the
    first update always sticks and an empty stored answer can be overwritten
    by an equal or lower one.
    """

    __slots__ = ("response", "stored", "value")

    def __init__(self) -> None:
        self.value = 0.0
        self.response: list[ResponseItem] = []
        self.stored = False

    def _replaces(self, value: float) -> bool:
        return value > self.value or not self.response

    def update_targets(self, value: float, ids: Sequence[str | int] | None) -> None:
        """``UpdateSelectionTargets(v, src, ids)``: ``ids`` None stores nothing,
        an empty ``ids`` stores one empty entity list."""

        if self._replaces(value):
            self.value = value
            self.response = []
            self.stored = True
            if ids is not None:
                self.response.append(tuple(ids))

    def update_responses(
        self, value: float, responses: Sequence[ResponseItem] | None
    ) -> None:
        """``UpdateSelectionResponses(v, src, resps)``: an empty array leaves
        the response list empty."""

        if self._replaces(value):
            self.value = value
            self.response = []
            self.stored = True
            if responses is not None:
                self.response.extend(responses)

    def answer(self, label: str) -> Answer:
        if not self.stored:
            return Answer(0.0, None, label)
        return Answer(self.value, tuple(self.response), label)


def get_combinations[T](
    source: Sequence[T], budget: int = GET_COMBINATIONS_BUDGET
) -> list[tuple[T, ...]]:
    """``WormEnumerableAIExtensions.GetCombinations`` + ``ToList`` (spec §5.3).

    Shared generic @0x1489670 (``<GetCombinations>d__1`` @0x292a890, inner
    ``d__0`` @0x2929990): sizes 1..n, each size in lexicographic order of
    ``source`` (``itertools.combinations`` yields the same order). The
    751 ms wall-clock cut-off is replaced by ``budget`` combinations: after
    each yield the enumeration stops once ``budget`` were produced.
    """

    out: list[tuple[T, ...]] = []
    for size in range(1, len(source) + 1):
        for combo in itertools.combinations(source, size):
            out.append(combo)
            if len(out) >= budget:
                return out
    return out


# ---------------------------------------------------------------------------
# IntrigueAbility and StrengthIntrigueAbility
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.IntrigueAbility")
class IntrigueAbility(PlayAbility):
    """``PlayAbilities.IntrigueAbility`` (abstract; spec §3.1, §4.5, §4.9)."""

    #: The raw ``AbilityTiming`` (0 Plot, 4 Endgame, 5 Combat).
    ability_timing: ClassVar[int] = PLOT_TIMING

    def meets_cost(self, p: Profile) -> bool:
        """``AbilityExtensions.MeetsCost`` with this class's ``Cost``."""

        return True

    def can_be_run(self, p: Profile) -> bool:
        """``WormAbilityDefinition::CanBeRun @0x4a890d0`` = ``MeetsCost &&
        HasTargets && IsUnexhausted``; the last two are the engine's (UNTRACED
        ``HasTargets`` per card, spec §13)."""

        return self.meets_cost(p)

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IntrigueAbility::IsBadIntrigue @0x4bd81e0``: false."""

        return False

    def troop_value(self, p: Profile) -> int:
        """``IntrigueAbility::TroopValue @0x4bd81d0``: 0 (spec §4.9; only
        base/RoI/Immortality intrigues override it)."""

        return 0

    def has_matching_timing(self, turn_type: int) -> bool:
        """``WormAbilityDefinition::HasMatchingTiming @0x4a89f30``.

        The jump table (``il2dis``): timing 0 (None) matches the turn types
        {Undetermined, Agent, Reveal} (spec §2.1); 1 Agent the AgentTurn; 2
        Reveal the RevealTurn; 3 CombatResolution and 5 Combat the
        CombatTurn; 4 Endgame the Endgame turn; anything else matches every
        turn (``cmp ecx, 5; ja`` keeps ``al = 1``). Only Immortality's Harvest
        Cells uses 3.
        """

        timing = self.ability_timing
        if timing == PLOT_TIMING:
            return turn_type in (_UNDETERMINED, _AGENT_TURN, _REVEAL_TURN)
        if timing == Timing.AGENT:
            return turn_type == _AGENT_TURN
        if timing == Timing.REVEAL:
            return turn_type == _REVEAL_TURN
        if timing in (COMBAT_RESOLUTION_TIMING, COMBAT_TIMING):
            return turn_type == _COMBAT_TURN
        if timing == ENDGAME_TIMING:
            return turn_type == _ENDGAME_TURN
        return True


def ability_for_prompt(card: Entity, combat_turn: bool) -> IntrigueAbility | None:
    """The ability ``MakeChoice`` evaluates for an intrigue key (spec §1).

    ``src.Abilities.First(a => a.HasMatchingTiming(CombatTurn))`` while P is
    in its combat turn (``b__12_3 @0x4928670``), else ``First(a =>
    !a.HasMatchingTiming(CombatTurn))`` (``b__12_2 @0x4928640``).
    """

    for ability in abilities_of(card):
        if not isinstance(ability, IntrigueAbility):
            continue
        if ability.has_matching_timing(_COMBAT_TURN) == combat_turn:
            return ability
    return None


@port("worm.canis.abilities.PlayAbilities.StrengthIntrigueAbility")
class StrengthIntrigueAbility(IntrigueAbility):
    """``PlayAbilities.StrengthIntrigueAbility`` (abstract; spec §5).

    ``.ctor @0x4bdd700`` sets ``AbilityTiming = Combat`` (5).
    """

    timing: ClassVar[Timing] = Timing.COMBAT
    ability_timing: ClassVar[int] = COMBAT_TIMING

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4bdd7f0`` (vslot 88): ``MeetsCost ?
        Owner.Strength : 0``."""

        return self.owner.int_attr("Strength") if self.meets_cost(p) else 0

    def combat_value(self, p: Profile) -> float:
        """``CombatValue @0x4bdd840`` (vslot 89): the ``CombatValue``
        attribute, 0.0 when absent."""

        return self.owner.float_attr("CombatValue", 0.0)

    def _is_self(self, other: StrengthIntrigueAbility) -> bool:
        """``List.Contains(this)``: the same ability object (card and class)."""

        return other.owner.ref == self.owner.ref and other.APP_CLASS == self.APP_CLASS

    def _strength_choice(self, p: Profile) -> _Choice:
        """``StrengthIntrigueAbility::Evaluate @0x4bdda30`` (spec §5.2).

        Wrappers call it non-virtually, as the app does; ``strength_value``
        and ``combat_value`` stay virtual. ``HagalMode == Solo`` never holds.
        """

        choice = _Choice()
        me = p.ctx.me
        conflict = _current_conflict(p)
        sv = self.strength_value(p)
        if conflict is None or sv <= 0:
            return choice
        if me.combat_strength <= 0:
            return choice
        r = p.current_conflict_rank(0)
        rank = r if r is not None else 4
        if r is not None and r < 2:
            value = -1.0  # sole first now: hold (0x4bddef9)
        elif p.ctx.conflict_deck_size == 0 or self._decisive(p, conflict):
            # PrivateArmy (base set, 50.0) is never dealt in Uprising.
            value = 100.0 - self.combat_value(p)
        else:
            value = self._first_improving_value(p, conflict, rank)
        choice.update_responses(value, ())
        return choice

    def _decisive(self, p: Profile, conflict: Entity) -> bool:
        """``top.VictoryPoints() + conflict.VictoryPoints() >= 10`` (0x4bde072).

        ``top`` = ``Match.Players.OrderByDescending(Strength).FirstOrDefault()``
        (stable: seat order on ties). The literal is 10, not the trigger
        score; the conflict card's own ``VictoryPoints`` is 0 in Uprising.
        """

        top = sorted(p.ctx.players, key=lambda pl: pl.combat_strength, reverse=True)
        if not top:
            return False
        return p.ctx.vp(top[0]) + conflict.int_attr("VictoryPoints") >= 10

    def _first_improving_value(self, p: Profile, conflict: Entity, rank: int) -> float:
        """The normal branch: only the first improving combination counts."""

        v_cur = _placement_value(p, conflict, rank)
        mine: list[StrengthIntrigueAbility] = []
        for instance in p.ctx.intrigue_cards:
            card = intrigue_entity(instance, p.ctx.seat)
            mine.extend(
                a for a in abilities_of(card) if isinstance(a, StrengthIntrigueAbility)
            )
        mine.sort(key=lambda a: a.strength_value(p))  # OrderBy: stable
        mine = [a for a in mine if a.strength_value(p) != 0]  # RemoveAll(== 0)
        for combo in get_combinations(mine):
            add = sum(a.strength_value(p) for a in combo)
            r2 = p.current_conflict_rank(add)
            v_new = _placement_value(p, conflict, r2 if r2 is not None else 4)
            cost = _dsum([a.combat_value(p) for a in combo])
            if v_new > cost + v_cur:  # strict
                if any(self._is_self(a) for a in combo):
                    return 10.0 - self.combat_value(p)
                return 0.0
        return 0.0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StrengthIntrigueAbility::Evaluate @0x4bdda30`` (spec §5.2):
        ``UpdateSelectionResponses(value, src, Array.Empty)``."""

        return self._strength_choice(p).answer(f"{type(self).__name__} strength")


# ---------------------------------------------------------------------------
# Combat intrigues (spec §6)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.Uprising.WeirdingCombatAbility")
class WeirdingCombatAbility(StrengthIntrigueAbility):
    """``Uprising.WeirdingCombatAbility`` (spec §6.1; no Evaluate override)."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4c5a680``: ``3 + 2 * (BG influence >= 3)``
        (``setge``; ``lea eax, [rcx*2+3]``; no MeetsCost, Cost is true)."""

        return 3 + 2 * (1 if p.ctx.me.influence.bene_gesserit >= 3 else 0)


@port("worm.canis.abilities.PlayAbilities.Uprising.ContingencyPlanCombatAbility")
class ContingencyPlanCombatAbility(StrengthIntrigueAbility):
    """``Uprising.ContingencyPlanCombatAbility`` (spec §6.2): base Evaluate,
    ``Cost @0x4c07cc0`` = NoCost, ``IsBadIntrigue @0x4c07dd0`` = false."""


@port("worm.canis.abilities.PlayAbilities.BaseSet.BackedbyCHOAMCombatAbility")
class BackedbyCHOAMCombatAbility(StrengthIntrigueAbility):
    """``BaseSet.BackedbyCHOAMCombatAbility`` (spec §6.3; CHOAM only)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cbf8c0`` = ``HasAtLeastContractsCompleted(2)``."""

        return len(p.ctx.me.completed_contract_ids) >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cbf9e0``: false."""

        return False


@port("worm.canis.abilities.PlayAbilities.Uprising.TacticalOptionAbility")
class TacticalOptionAbility(StrengthIntrigueAbility):
    """``Uprising.TacticalOptionAbility`` (spec §6.4)."""

    def combat_value(self, p: Profile) -> float:
        """``CombatValue @0x4c57770`` = ``(double) StrengthValue(p)`` (2.0;
        the archetype's 1.0 is never read)."""

        return float(self.strength_value(p))

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``TacticalOptionAbility::Evaluate @0x4c57790`` (spec §6.4).

        ``infos[0]`` = the ChooseOne, ``infos[1].options`` = the retreat
        option's troops (``GetDependentTargets<WormTroop>(1)``).
        """

        choice = _Choice()
        v = self._strength_choice(p).value
        choice.update_responses(v, ((0,),))  # unconditional, may be <= 0
        cur = p.ctx.me.combat_strength
        opp = [o.combat_strength for o in p.ctx.opponents]  # b__11_0
        next_below = max((s for s in opp if cur >= s), default=0)  # b__1, MaxOrElse
        close = any(s - cur >= 0 and s - cur < 2 for s in opp)  # b__2
        climax = p.is_climax()  # ``or al, bl``: both evaluated
        if close or climax:
            return choice.answer("Tactical Option strength")
        if cur - next_below < 10:  # cmp 0xa; jl
            return choice.answer("Tactical Option strength")
        troops = _options(request, 1)
        n = p.troops_to_retreat(len(troops))
        if n <= 0:
            return choice.answer("Tactical Option strength")
        choice.update_responses(150.0, ((1,), tuple(troops[:n])))
        return choice.answer(f"Tactical Option| value to retreat {n} troops: 150")


@port("worm.canis.abilities.PlayAbilities.Uprising.QuestionableMethodsAbility")
class QuestionableMethodsAbility(StrengthIntrigueAbility):
    """``Uprising.QuestionableMethodsAbility`` (spec §6.5)."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4c48e20``: ``1 + 4 * FactionList.Any(inf > 0)``
        (b__0 @0x4c49800, ``setg``)."""

        me = p.ctx.me
        return 1 + 4 * (1 if any(_influence(me, f) > 0 for f in FACTIONS) else 0)

    def combat_value(self, p: Profile) -> float:
        """``CombatValue @0x4c48f20`` = ``(double) StrengthValue(p)``."""

        return float(self.strength_value(p))

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``QuestionableMethodsAbility::Evaluate @0x4c48f40`` (spec §6.5).

        ``v <= 0`` returns the base choice itself. The baseline
        ``UpdateSelectionTargets(1.0, [])`` stores a non-empty response, so a
        faction answer needs a strictly greater ``0.1 * G(f, -1) + v``.
        """

        base = self._strength_choice(p)
        v = base.value
        if not v > 0:  # ucomisd v, 0; jbe
            return base.answer("Questionable Methods base")
        choice = _Choice()
        tracks = _targets(request, 0, Kind.TRACK)
        if tracks:
            choice.update_targets(1.0, ())
            for track in tracks:
                g = p.gain_influence_value(track.ref, -1, -1, False).sum
                choice.update_targets(g * 0.1 + v, (track.ref,))  # mulsd; addsd
        else:
            choice.update_targets(v, ())
        return choice.answer("Questionable Methods")


@port("worm.canis.abilities.PlayAbilities.Uprising.ImpressAbility")
class ImpressAbility(StrengthIntrigueAbility):
    """``Uprising.ImpressAbility`` (spec §6.6)."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImpressAbility::Evaluate @0x4c0f900`` (spec §6.6), no ``v > 0`` gate.

        Judgement: ``GetValidTargets(match, P).Any()`` (@0x4c0f6c0) is read as
        "the request lists a card": the window builds ``infos[0]`` from the
        same acquirable cards (BasePersuasion < 4 that P can acquire).
        """

        choice = _Choice()
        v = self._strength_choice(p).value
        cards = _targets(request, 0, Kind.CARD)
        if not cards:
            choice.update_responses(v, ())
            return choice.answer("Impress no target")
        for card in cards:
            a = p.acquire_value(card).sum
            choice.update_responses(a * 0.1 + v, ((card.ref,),))  # mulsd; addsd
        return choice.answer("Impress | acquire card")


@port("worm.canis.abilities.PlayAbilities.Uprising.DevourAbility")
class DevourAbility(StrengthIntrigueAbility):
    """``Uprising.DevourAbility`` (spec §6.7)."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4c0a740``: ``2 + AdditionalStrengthValue``
        (@0x4c0a710: 2 with a sandworm in the Conflict)."""

        return 2 + (2 if p.ctx.me.sandworms_conflict > 0 else 0)

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c0aa30``: ``!HasMakerHooks && IsClimax``."""

        return not p.ctx.me.maker_hooks and p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DevourAbility::Evaluate @0x4c0aa80`` (spec §6.7), no gate."""

        choice = _Choice()
        v = self._strength_choice(p).value
        if p.ctx.me.sandworms_conflict > 0:
            card, tv = p.card_to_trash(_targets(request, 0, Kind.CARD), 1.0)
            if card is not None:
                choice.update_responses(v + tv, ((card.ref,),))
            else:
                choice.update_responses(v, ((),))
        else:
            choice.update_responses(v, ())
        return choice.answer("Devour")


@port("worm.canis.abilities.PlayAbilities.Uprising.FindWeaknessAbility")
class FindWeaknessAbility(StrengthIntrigueAbility):
    """``Uprising.FindWeaknessAbility`` (spec §6.8)."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue @0x4c0c100``: ``2 + 3 * (SpyDeployedCount > 0)``."""

        return 2 + 3 * (1 if _deployed_spies(p) > 0 else 0)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FindWeaknessAbility::Evaluate @0x4c0c1f0`` (spec §6.8)."""

        choice = _Choice()
        spies = _targets(request, 0, Kind.SPY)
        v = self._strength_choice(p).value
        spy, _ = p.recall_spy(spies)
        if spy is None:
            return choice.answer("Find Weakness no spy")
        choice.update_targets(v + 0.1, (spy.ref,))
        return choice.answer("Find Weakness")


@port("worm.canis.abilities.PlayAbilities.Uprising.SpringTheTrapAbility")
class SpringTheTrapAbility(StrengthIntrigueAbility):
    """``Uprising.SpringTheTrapAbility`` (spec §6.9)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c543c0`` = ``HasAtLeastSpiesOnBoard(2)``."""

        return _deployed_spies(p) >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c54520``: ``!GetDeployedSpies(P).Any()``."""

        return _deployed_spies(p) == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpringTheTrapAbility::Evaluate @0x4c54570`` (spec §6.9)."""

        choice = _Choice()
        v = self._strength_choice(p).value
        if not v > 0:  # ucomisd v, 0; jbe
            return choice.answer("Spring the Trap")
        spies, _ = p.recall_spies(_targets(request, 0, Kind.SPY), 2)
        if len(spies) != 2:
            return choice.answer("Spring the Trap not 2 spies")
        choice.update_targets(v, tuple(spy.ref for spy in spies))  # b__10_0
        return choice.answer("Spring the Trap")


@port("worm.canis.abilities.PlayAbilities.Uprising.SpiceIsPowerAbility")
class SpiceIsPowerAbility(StrengthIntrigueAbility):
    """``Uprising.SpiceIsPowerAbility`` (spec §6.10)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c52d90``: ``GetDeployedTroops(P).Count > 2 || Spice >= 3``
        (troops only: sandworms are not troops)."""

        me = p.ctx.me
        return me.troops_conflict > 2 or me.resources.spice >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c52f40``: false."""

        return False

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpiceIsPowerAbility::Evaluate @0x4c52f60`` (spec §6.10).

        Answers the app's fixed ints: 1 = pay 3 spice for +6, 0 = retreat
        three troops (our option indices are the same, R4 §9.1).
        """

        choice = _Choice()
        me = p.ctx.me
        if me.resources.spice >= 3:  # cmp 3; jl
            v = self._strength_choice(p).value
            choice.update_responses(v, ((1,),))
        if (
            me.troops_conflict >= 3  # WormPlayer::get_ConflictTroops
            and p.should_play_retreat_intrigue("Spice Is Power", 6, 10, 3) > 0
        ):
            choice.update_responses(150.0, ((0,),))
        return choice.answer("Spice Is Power")


@port("worm.canis.abilities.PlayAbilities.Uprising.GoToGroundAbility")
class GoToGroundAbility(StrengthIntrigueAbility):
    """``Uprising.GoToGroundAbility`` (spec §6.11): no Strength attribute, so
    ``StrengthValue`` and ``CombatValue`` are 0; ``Cost`` is true."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c0d0e0``: ``SpyDeployedCount >= 2``."""

        return _deployed_spies(p) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GoToGroundAbility::Evaluate @0x4c0d100`` (spec §6.11).

        The ``PlaceSpyAbility.GetSpyAIResponses`` result only feeds a log
        line and is discarded (judgement, as in ``PlaceSpyAbility``: not
        computed). The post is chosen later by the PlaceSpy prompt.
        """

        choice = _Choice()
        s = p.should_play_retreat_intrigue("Go To Ground", 2, 6, 2)
        if s <= 0:
            return choice.answer("Go To Ground")
        troops = _options(request, 0)
        n = p.troops_to_retreat(2)
        if n <= 0:
            return choice.answer("Go To Ground")
        responses: tuple[ResponseItem, ...] = (tuple(troops[:n]),)  # b__10_0
        choice.update_responses(p.spy_value().sum, responses)
        return choice.answer("Go To Ground Place Spy")


@port("worm.canis.abilities.PlayAbilities.Uprising.ReachAgreementAbility")
class ReachAgreementAbility(StrengthIntrigueAbility):
    """``Uprising.ReachAgreementAbility`` (spec §6.12; CHOAM only)."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c4a660``: ``P.AIProfile.IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ReachAgreementAbility::Evaluate @0x4c4a690`` (spec §6.12).

        The contract's value only feeds the log; the answer is worth
        ``(double) s`` (1.0).
        """

        choice = _Choice()
        s = p.should_play_retreat_intrigue("Reach Agreement", 2, 6, 2)
        if s <= 0:
            return choice.answer("Reach Agreement")
        troops = _options(request, 0)
        contracts = _targets(request, 1, Kind.CONTRACT)
        n = p.troops_to_retreat(2)
        if n <= 0:
            return choice.answer("Reach Agreement")
        ids = tuple(troops[:n])  # b__10_0
        best, _ = p.best_contract(contracts, True)
        if best is not None:
            choice.update_responses(float(s), (ids, (best.ref,)))
        elif not contracts:
            choice.update_responses(float(s), (ids,))
        return choice.answer("Reach Agreement")


# ---------------------------------------------------------------------------
# Plot intrigues (spec §7)
# ---------------------------------------------------------------------------


@port("worm.canis.abilities.PlayAbilities.BaseSet.BackedByCHOAMPlotAbility")
class BackedByCHOAMPlotAbility(IntrigueAbility):
    """``BaseSet.BackedByCHOAMPlotAbility`` (spec §7.1; CHOAM only).

    ``Cost @0x4cbde20`` = NoCost.
    """

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cbe060``: ``completed > 1 ? false : IsClimax``."""

        if len(p.ctx.me.completed_contract_ids) > 1:  # cmp 1; jle
            return False
        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BackedByCHOAMPlotAbility::Evaluate @0x4cbe0b0`` (spec §7.1).

        Still blocked once the AI owns the Swordmaster (app quirk kept).
        """

        choice = _Choice()
        me = p.ctx.me
        if me.swordmaster_acquired:
            return choice.answer("Backed by CHOAM")
        if not (_in_player_turn(p, _UNDETERMINED) and me.agents_available > 0):
            return choice.answer("Backed by CHOAM")
        solari = me.resources.solari
        d = solari - _space_cost(p, _SWORDMASTER)
        if -4 <= d <= -1 and _open_to(p, _SWORDMASTER):  # unsigned range 0x4cbe429
            reason = "Swordmaster"
        elif p.ctx.round_number <= 5 and not me.high_council:
            if -4 <= solari - _space_cost(p, _HIGH_COUNCIL) <= -1 and _open_to(
                p, _HIGH_COUNCIL
            ):
                reason = "High Council"
            else:
                return choice.answer("Backed by CHOAM")
        else:
            if len(me.completed_contract_ids) != 0:
                return choice.answer("Backed by CHOAM")
            if not any(  # b__1 @0x4cbeca0
                _influence(me, f) >= 3
                and _highest_opponent_rank(p, f) - _influence(me, f) >= 2
                for f in FACTIONS
            ):
                return choice.answer("Backed by CHOAM")
            reason = "No completed contracts"
        for track in _targets(request, 0, Kind.TRACK):
            v = p.gain_influence_value(track.ref, -1, -1, False).sum + 100.0
            choice.update_targets(v, (track.ref,))
        return choice.answer(f"Backed by CHOAM ({reason})")


@port("worm.canis.abilities.PlayAbilities.Uprising.BuyAccessAbility")
class BuyAccessAbility(IntrigueAbility):
    """``Uprising.BuyAccessAbility`` (spec §7.2)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c045e0`` = ``HasResources.AtLeast(Solari, 5).Then(new
        CanGainInfluence())``. UNTRACED ``CanGainInfluence::CanBePaid``
        (@0x4a6a670) predicate: any faction P can still gain on."""

        me = p.ctx.me
        return me.resources.solari >= 5 and any(
            _can_gain_faction_influence(me, f) for f in FACTIONS
        )

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c04850``: ``(!HasSwordmaster && Solari < 3) ||
        2.5 >= G(None, +1).Sum`` (f64 2.5, ``setae``)."""

        me = p.ctx.me
        if not me.swordmaster_acquired and me.resources.solari < 3:
            return True
        return 2.5 >= p.gain_influence_value(_ANY_FACTION, 1, -1, False).sum

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BuyAccessAbility::Evaluate @0x4c048e0`` (spec §7.2).

        The tracks are shuffled (``ListUtil.Shuffle``, 0x4c04b5f); every
        ``GetGainInfluenceValue`` summer is a new dictionary key, so the
        stable ``OrderByDescending(Sum)`` breaks ties in shuffled order.
        """

        choice = _Choice()
        tracks = list(_targets(request, 0, Kind.TRACK))
        if not tracks:
            return choice.answer("Buy Access")
        p.rng.shuffle(tracks)
        scores = [
            (p.gain_influence_value(t.ref, 1, -1, False).sum, t.ref) for t in tracks
        ]
        top2 = sorted(scores, key=lambda item: item[0], reverse=True)[:2]  # b__11_0
        if (
            p.ctx.me.swordmaster_acquired and top2[0][0] >= 3.75  # f64 3.75, jae
        ) or p.is_climax():
            choice.update_targets(1.0, tuple(ref for _, ref in top2))
        return choice.answer("Buy Access Play | 1")


@port("worm.canis.abilities.PlayAbilities.BaseSet.CallToArmsAbility")
class CallToArmsAbility(IntrigueAbility):
    """``BaseSet.CallToArmsAbility`` (spec §7.3); ``Cost @0x4cbff70``: none."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cc0180``: ``GarrisonTroops >= 6``."""

        return p.ctx.me.troops_garrison >= 6

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CallToArmsAbility::Evaluate @0x4cc0380`` (spec §7.3)."""

        choice = _Choice()
        if not _in_player_turn(p, _REVEAL_TURN):
            return choice.answer("Call to Arms")
        if not p.is_final_round():
            persuasion = _persuasion(p)
            cards = p.acquire_cards_by_value(persuasion)
            if not cards:
                return choice.answer("Call to Arms")
            if persuasion - cards[0].int_attr("PersuasionCost") < 2:  # cmp 2; jl
                return choice.answer("Call to Arms")
        choice.update_targets(100.0, None)
        return choice.answer("Call to Arms| 100")


@port("worm.canis.abilities.PlayAbilities.BaseSet.ChangeAllegiancesAbility")
class ChangeAllegiancesAbility(IntrigueAbility):
    """``BaseSet.ChangeAllegiancesAbility`` (spec §7.4)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc0ee0`` = ``HasFactionInfluence.AtLeast(1).Or(
        HasResources.AtLeast(Spice, 3))``. Judgement: ``AtLeast(1)`` without
        a faction reads any faction."""

        me = p.ctx.me
        return any(_influence(me, f) >= 1 for f in FACTIONS) or me.resources.spice >= 3

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ChangeAllegiancesAbility::Evaluate @0x4cc17a0`` (spec §7.4).

        The gain track is picked later by ``ChooseFactionInfluenceEvaluator``
        (``choose_faction_influence``); UNTRACED how the 3-spice payment
        (state 201) is answered.
        """

        choice = _Choice()
        tracks = _targets(request, 0, Kind.TRACK)
        lose_ref: str | None = None
        if tracks:
            lose, _gain, x = p.best_influence_exchange(
                -1, 1, [t.ref for t in tracks], list(FACTIONS)
            )
            lose_ref = next((t.ref for t in tracks if t.ref == lose), None)  # b__1
            if lose_ref is not None and x >= 2.0:  # ucomisd x, 2.0; jb
                choice.update_responses(x, ((lose_ref,),))
                return choice.answer("Change Allegiance")
        me = p.ctx.me
        if (
            _in_player_turn(p, _REVEAL_TURN)
            and me.resources.spice >= 3
            and (p.is_climax() or p.is_final_round())
        ):
            responses: tuple[ResponseItem, ...]
            if not tracks:
                responses = ()
            elif lose_ref is None:
                responses = ((),)
            else:
                responses = ((lose_ref,),)
            choice.update_responses(10.0, responses)  # logged '| 100'
        return choice.answer("Change Allegiance")


def choose_faction_influence(p: Profile, tracks: Sequence[Entity]) -> Answer:
    """``ChooseFactionInfluenceEvaluator::Evaluate @0x492eca0`` (spec §7.4).

    The gain-track picker of Change Allegiances: ``G(f, +1) + 100`` ("Static
    Boost") per track in target order, first strictly best.
    """

    choice = _Choice()
    for track in tracks:
        s = Summer()
        s.merge(p.gain_influence_value(track.ref, 1, -1, False))
        s.add("Static Boost", 100.0)
        choice.update_targets(s.sum, (track.ref,))
    return choice.answer("Choose Faction Influence")


@port("worm.canis.abilities.PlayAbilities.BaseSet.ContingencyPlanPlotAbility")
class ContingencyPlanPlotAbility(IntrigueAbility):
    """``BaseSet.ContingencyPlanPlotAbility`` (spec §7.5); ``Cost
    @0x4cc3070``: none; ``IsBadIntrigue @0x4cc3190``: false."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ContingencyPlanPlotAbility::Evaluate @0x4cc31a0`` (spec §7.5)."""

        choice = _Choice()
        me = p.ctx.me
        if me.swordmaster_acquired:
            return choice.answer("Contingency Plan")
        if not (_in_player_turn(p, _UNDETERMINED) and me.agents_available > 0):
            return choice.answer("Contingency Plan")
        solari = me.resources.solari
        # unsigned compare at 0x4cc33b4: shortfall of exactly 1 or 2 Solari.
        if solari - _space_cost(p, _SWORDMASTER) in (-2, -1) and _open_to(
            p, _SWORDMASTER
        ):
            choice.update_targets(100.0, None)
            return choice.answer("Contingency Plan (Swordmaster) | 100")
        if (
            p.ctx.round_number <= 5
            and not me.high_council
            and solari - _space_cost(p, _HIGH_COUNCIL) in (-2, -1)
            and _open_to(p, _HIGH_COUNCIL)
        ):
            choice.update_targets(100.0, None)
            return choice.answer("Contingency Plan (High Council) | 100")
        return choice.answer("Contingency Plan")


@port("worm.canis.abilities.PlayAbilities.BaseSet.CouncilorsAmbitionAbility")
class CouncilorsAmbitionAbility(IntrigueAbility):
    """``BaseSet.CouncilorsAmbitionAbility`` (spec §7.6)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc3ac0`` = ``HasHighCouncilSeat``."""

        return p.ctx.me.high_council

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cc3bf0``: ``!seat || Water > 2 || IsClimax``."""

        me = p.ctx.me
        return not me.high_council or me.resources.water > 2 or p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CouncilorsAmbitionAbility::Evaluate @0x4cc3c50`` (spec §7.6)."""

        choice = _Choice()
        v = Summer()
        v.add("Water", p.water_value(2))  # mov esi, 2
        if (
            p.is_final_round()
            or _intrigue_hand_count(p) > 3
            or (_in_player_turn(p, _UNDETERMINED) and p.ctx.me.agents_available > 0)
        ):
            choice.update_targets(v.sum, None)
        return choice.answer("Councilor's Ambition")


@port("worm.canis.abilities.PlayAbilities.BaseSet.GainSpiceIntrigueAbility")
class GainSpiceIntrigueAbility(IntrigueAbility):
    """``BaseSet.GainSpiceIntrigueAbility``: the Plot half of Crysknife,
    Desert Mouse and Ornithopter (spec §7.7); ``Cost @0x4cc7cc0``: none."""

    def battle_icon(self) -> str:
        """``GetBattleIconFromOwner @0x4cc7df0``: the owner's ``BattleIcon``."""

        return str(self.owner.attr("BattleIcon", _NO_ICON))

    def _keeps_for_pair(self, p: Profile) -> bool:
        """``!owned.All(x => x != icon && x != Wildcard)`` (b__0 @0x4cc8610)."""

        icon = self.battle_icon()
        owned = [i for _, i in battle_icon_list(p.ctx.me)]
        return not all(x != icon and x != _WILDCARD for x in owned)

    def _conflict_icon(self, p: Profile) -> str | None:
        """``CurrentConflict()?.GetBattleIcon()`` (@0x482a3d0: ``None`` when the
        card has no icon; null without a current conflict)."""

        conflict = _current_conflict(p)
        if conflict is None:
            return None
        return str(conflict.attr("BattleIcon", _NO_ICON))

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cc7f40`` (spec §7.7)."""

        if not p.is_climax():
            return False
        if self._keeps_for_pair(p):
            return False
        r = p.estimated_conflict_rank(0)
        ci = self._conflict_icon(p)
        if (
            r is not None
            and r < 2
            and ci is not None
            and (ci == self.battle_icon() or ci == _WILDCARD)
        ):
            return False
        return True

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GainSpiceIntrigueAbility::Evaluate @0x4cc81d0`` (spec §7.7).

        Wildcard is not tested against the current conflict's icon here.
        """

        choice = _Choice()
        icon = self.battle_icon()
        if self._keeps_for_pair(p):
            return choice.answer(f"Intrigue {icon} keep")
        ci = self._conflict_icon(p)
        if (ci if ci is not None else _NO_ICON) == icon:
            return choice.answer(f"Intrigue {icon} keep")
        me = p.ctx.me
        if (
            p.is_final_round()
            or _intrigue_hand_count(p) > 3
            or (
                _in_player_turn(p, _UNDETERMINED)
                and me.agents_available > 0
                and me.resources.spice <= 4
            )
        ):
            choice.update_targets(100.0, None)
        return choice.answer(f"Intrigue {icon} for Spice | 100")


@port("worm.canis.abilities.PlayAbilities.Uprising.CunningAbility")
class CunningAbility(IntrigueAbility):
    """``Uprising.CunningAbility`` (spec §7.8)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c08510`` = ``HasDrawableCard.Or(CanPaySpiceToTrash)``;
        ``CanPaySpiceToTrash @0x4c08450`` = ``Spice >= 1 .Then(
        HasTrashableCard)``."""

        if _has_drawable_card(p):
            return True
        return p.ctx.me.resources.spice >= 1 and bool(_trash_targets(p))

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CunningAbility::Evaluate @0x4c08780`` (spec §7.8).

        Answers ``Int(0)`` draw only or ``Int(1)`` draw + trash; the card is
        chosen later by ``CunningTrashAbility`` (UNTRACED that this prompt is
        raised there).
        """

        choice = _Choice()
        me = p.ctx.me
        gate = (
            _intrigue_hand_count(p) > 3
            or p.is_final_round()
            or (
                _in_player_turn(p, _UNDETERMINED)
                and me.agents_available > 0
                and me.resources.spice > 0
            )
            or (
                _in_player_turn(p, _REVEAL_TURN)
                and p.buy_gains(p.possible_persuasion_gain()) >= 1.0
            )
        )
        if not gate:
            return choice.answer("Cunning")
        draw = p.card_draw_value()
        v0 = draw + p.buy_gains(p.possible_persuasion_gain())
        choice.update_responses(v0, ((0,),))
        if (
            me.resources.spice > 0
            and len(me.hand) > 0
            and p.trash_card_value() > p.spice_value(1)  # ucomisd; jbe
        ):
            card, tv = p.card_to_trash(_trash_targets(p), 1.0)
            if card is not None:
                rest = v0 - p.spice_value(1)
                v1 = tv + (p.trash_card_value() + rest)
                choice.update_responses(v1, ((1,),))
        return choice.answer("Cunning")


@port("worm.canis.abilities.PlayAbilities.Uprising.CunningTrashAbility")
class CunningTrashAbility(TrashAbility):
    """``Uprising.CunningTrashAbility`` (``: TrashAbility``; no AI override):
    ``TrashAbility::Evaluate @0x4ce98a0`` picks the card (spec §7.8)."""


@port("worm.canis.abilities.PlayAbilities.BaseSet.DepartForArrakisAbility")
class DepartForArrakisAbility(IntrigueAbility):
    """``BaseSet.DepartForArrakisAbility`` (spec §7.9)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc43e0`` = ``Guild >= 3 .Or(Spice >= 2)``."""

        me = p.ctx.me
        return me.influence.spacing_guild >= 3 or me.resources.spice >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DepartForArrakisAbility::Evaluate @0x4cc48d0`` (spec §7.9).

        Never played without Guild 3 (app quirk kept).
        """

        choice = _Choice()
        me = p.ctx.me
        draw_only = True
        if me.resources.spice >= 2 and me.influence.spacing_guild >= 3:
            draw_only = False
            if _deploy_window(p):
                v = (
                    100
                    if p.is_final_round()
                    else p.should_play_troop_intrigue("Depart For Arrakis", 6, 4, 3)
                )
                if v > 0:
                    choice.update_responses(float(v), ((1,),))
                    return choice.answer("Depart For Arrakis | troops")
        if (
            p.is_final_round()
            and _in_player_turn(p, _REVEAL_TURN)
            and me.influence.spacing_guild >= 3
        ):
            choice.update_responses(100.0, () if draw_only else ((0,),))
        return choice.answer("Depart For Arrakis | 100 | Draw only")


def intrigue_deploy_troops(p: Profile, garrison_targets: Sequence[int]) -> int:
    """``RapidMobilizationAbility.IntrigueDeployTroops @0x4cace80`` (spec §4.7).

    ``garrison_targets`` = the troop targets of the deploy option (all troops).
    The search passes ``k`` troops as ``k`` *strength* (app quirk kept).
    """

    count = len(garrison_targets)
    if p.is_final_round():
        return count  # 'deploy all troops for climax conflict'
    exp = p.est_strength().sum
    lb, ub = p.conflict_posture_bounds()
    interest = p.current_conflict_interest().sum
    me = p.ctx.me
    if not _in_player_turn(p, _REVEAL_TURN):
        return 0
    if me.troops_garrison <= 0:
        return 0
    if not interest > lb:  # ucomisd interest, lb; jbe
        return 0
    troops = count  # garrisonTargets.OfType<WormTroop>().Count()
    if not any(  # b__0 @0x4cad820
        o.troops_conflict + o.sandworms_conflict > 0
        and abs(exp - p.est_opponent_strength(o.player_id).sum) <= 2 * troops
        and exp + 3 <= p.est_opponent_strength(o.player_id).sum
        for o in p.ctx.opponents
    ):
        return 0
    opp = sorted(
        (p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents),
        reverse=True,
    )
    top = opp[0] if opp else 0
    second = opp[1] if len(opp) > 1 else 0
    if interest > ub:  # ucomisd interest, ub; ja
        if any(abs(s - exp) < 6 for s in opp):  # b__3 @0x4cad9f0
            n = math.ceil((top - exp + 7) * 0.5)  # roundsd 0xA, cvttsd2si
        else:
            n = 0
    elif abs(top - exp) <= 5:
        n = math.ceil((top - exp + 4) * 0.5)
    elif abs(second - exp) <= 3:
        n = math.ceil((second - exp + 4) * 0.5)
    else:
        n = 0
    if n > count:  # cmp n, Count; jle
        r = p.estimated_conflict_rank(0)
        r0 = r if r is not None else 4
        n = 0
        for k in range(count, 0, -1):
            rk = p.estimated_conflict_rank(k)
            if (rk if rk is not None else 4) < r0:
                n = k  # keeps the smallest improving k
    return n if n > 0 else 0


@port("worm.canis.abilities.PlayAbilities.BaseSet.DetonationAbility")
class DetonationAbility(IntrigueAbility):
    """``BaseSet.DetonationAbility`` (spec §7.10)."""

    def _can_blow_shield_wall(self, p: Profile) -> bool:
        """``CanBlowShieldWall @0x4cc5b20`` = ``Board.HasShieldWall``."""

        return p.ctx.shield_wall_present

    def _can_deploy_units(self, p: Profile) -> bool:
        """``CanDeployUnits::CanBePaid @0x4a6a050``: the conflict area is
        ``Deployable`` and ``BelowMax`` (UNTRACED: taken as true)."""

        return not units_deployment_blocked(p.ctx.state, p.ctx.seat)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc5c40`` = ``CanBlowShieldWall.Or(CanDeployUnits)``."""

        return self._can_blow_shield_wall(p) or self._can_deploy_units(p)

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cc5f80``: ``Garrison <= 2 && (!HasShieldWall ||
        !HasMakerHooks)``."""

        me = p.ctx.me
        return me.troops_garrison <= 2 and (
            not p.ctx.shield_wall_present or not me.maker_hooks
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DetonationAbility::Evaluate @0x4cc6000`` (spec §7.10)."""

        choice = _Choice()
        if p.intrigue_blow_wall():
            choice.update_responses(100.0, ((0,),))
            return choice.answer("Detonation | 100 | Blow Wall")
        if not self._can_deploy_units(p) or p.ctx.me.troops_garrison <= 0:
            return choice.answer("Detonation")
        both = self._can_blow_shield_wall(p)
        troops = _options(request, 1) if both else _options(request, 0)
        n = intrigue_deploy_troops(p, troops)
        if n <= 0:
            return choice.answer("Detonation")
        deployed = tuple(troops[:n])
        choice.update_responses(100.0, ((1,), deployed) if both else (deployed,))
        return choice.answer(f"Detonation | 100 | deploy {n}")


@port("worm.canis.abilities.PlayAbilities.Uprising.DistractionAbility")
class DistractionAbility(IntrigueAbility):
    """``Uprising.DistractionAbility`` (spec §7.11)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c0b5d0`` = ``HasUnitsDeployedThisTurn.AtLeast(3)`` (our
        turn counter and its peak, as the engine's gate reads them)."""

        me = p.ctx.me
        return max(me.units_deployed_turn, me.units_deployed_peak) >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c0b7f0``: ``SpyDeployedCount >= 2``."""

        return _deployed_spies(p) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DistractionAbility::Evaluate @0x4c0b810`` (spec §7.11).

        ``GetSpyAIResponses`` only feeds the log (not computed).
        """

        choice = _Choice()
        if _deployed_spies(p) > 2:
            return choice.answer("Distraction")
        choice.update_responses(p.spy_value().sum, ())
        return choice.answer("Distraction")


@port("worm.canis.abilities.PlayAbilities.Uprising.ImperiumPoliticsAbility")
class ImperiumPoliticsAbility(IntrigueAbility):
    """``Uprising.ImperiumPoliticsAbility`` (spec §7.12); ``IsBadIntrigue
    @0x4c0e710``: false."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c0e430`` = ``Solari >= 1 .Then(Emperor < 6 .Or(Guild <
        6))`` (the faction of each ``LessThan`` is read from the card text)."""

        me = p.ctx.me
        return me.resources.solari >= 1 and (
            me.influence.emperor < 6 or me.influence.spacing_guild < 6
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ImperiumPoliticsAbility::Evaluate @0x4c0e720`` (spec §7.12)."""

        choice = _Choice()
        need_threshold = _intrigue_hand_count(p) <= 3 and not p.is_climax()
        for track in _targets(request, 0, Kind.TRACK):
            v = Summer()
            v.merge(p.gain_influence_value(track.ref, 1, -1, False))
            v.add("Intrigue Count or Climax", 10.0)  # unconditional
            threshold = p.C.ImperiumPoliticsInfluenceThreshold
            if need_threshold and not v.sum >= threshold:
                continue  # ucomisd v, thr; jb (also taken for NaN)
            choice.update_targets(v.sum, (track.ref,))
        return choice.answer("ImperiumPoliticsAbility")


@port("worm.canis.abilities.PlayAbilities.Uprising.InspireAweAbility")
class InspireAweAbility(IntrigueAbility):
    """``Uprising.InspireAweAbility`` (spec §7.13); ``Cost @0x4c10990``: none."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c10bc0``: ``!HasMakerHooks && IsClimax``."""

        return not p.ctx.me.maker_hooks and p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``InspireAweAbility::Evaluate @0x4c10c10`` (spec §7.13).

        The second response ``Int(0)`` is the app's destination picker
        (presumably; our engine asks none).
        """

        choice = _Choice()
        if not request.infos:  # no EntityListTargetInformation (b__11_0)
            return choice.answer("Inspire Awe")
        worm = p.ctx.me.sandworms_conflict > 0
        for card in _targets(request, 0, Kind.CARD):
            v = p.acquire_value(card).sum
            ok = v >= 3.0 or (
                v >= 2.5 and card.attr("ImperiumType") == "Reserve" and worm
            )
            if ok:
                choice.update_responses(v, ((card.ref,), (0,)))
        return choice.answer("Inspire Awe | acquire")


@port("worm.canis.abilities.PlayAbilities.Uprising.IntelligenceReportAbility")
class IntelligenceReportAbility(IntrigueAbility):
    """``Uprising.IntelligenceReportAbility`` (spec §7.14)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c41560`` = ``HasDrawableCard``."""

        return _has_drawable_card(p)

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c41680``: ``!GetDeployedSpies(P).Any()``."""

        return _deployed_spies(p) == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IntelligenceReportAbility::Evaluate @0x4c416d0`` (spec §7.14).

        No ``CardDrawValue`` term: only the buy gains, doubled with 2+ spies
        (table @0x52f3cf0 = {1.0, 2.0}).
        """

        choice = _Choice()
        me = p.ctx.me
        gate = (
            _intrigue_hand_count(p) > 3
            or p.is_final_round()
            or (
                _in_player_turn(p, _UNDETERMINED)
                and me.agents_available > 0
                and _deployed_spies(p) > 1
            )
            or (
                _in_player_turn(p, _REVEAL_TURN)
                and p.buy_gains(p.possible_persuasion_gain()) >= 1.0
            )
        )
        if not gate:
            return choice.answer("Intelligence Report")
        k = 2.0 if _deployed_spies(p) >= 2 else 1.0
        choice.update_targets(p.buy_gains(p.possible_persuasion_gain()) * k, None)
        return choice.answer("Intelligence Report | Draw card(s)")


@port("worm.canis.abilities.PlayAbilities.BaseSet.LeverageAbility")
class LeverageAbility(IntrigueAbility):
    """``BaseSet.LeverageAbility`` (spec §7.15; CHOAM only)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc8da0`` = ``GainedSpiceThisTurn > 0`` (ours: spice now -
        spice at turn start + spice spent this turn, the engine's gate)."""

        me = p.ctx.me
        gained = me.resources.spice - me.spice_at_turn_start + me.spice_spent_turn
        return gained > 0

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4cc9080``: ``P.AIProfile.IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``LeverageAbility::Evaluate @0x4cc90b0``: tail call of
        ``GainContractAbility.ContractEvaluate(ctx, this, src, forced=false)``."""

        return contract_evaluate(p, request, False)


@port("worm.canis.abilities.PlayAbilities.Uprising.ManipulateUPAbility")
class ManipulateUPAbility(IntrigueAbility):
    """``Uprising.ManipulateUPAbility`` (spec §7.16); ``Cost @0x4c42fb0``:
    none."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c431e0``: ``P.AIProfile.IsClimax``."""

        return p.is_climax()

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ManipulateUPAbility::Evaluate @0x4c43210`` (spec §7.16)."""

        choice = _Choice()
        if not (p.buy_gains(1) >= 1.33 or p.is_climax()):
            return choice.answer("Manipulate (Intrigue)")
        if not (_in_player_turn(p, _REVEAL_TURN) or _intrigue_hand_count(p) >= 4):
            return choice.answer("Manipulate (Intrigue)")
        for card in _targets(request, 0, Kind.CARD):
            v = p.acquire_value(card)
            if card.int_attr("PersuasionCost") > p.possible_persuasion() + 1:
                continue
            choice.update_targets(v.sum, (card.ref,))
        return choice.answer("Manipulate (Intrigue) | set aside")


@port("worm.canis.abilities.PlayAbilities.BaseSet.MarketOpportunityAbility")
class MarketOpportunityAbility(IntrigueAbility):
    """``BaseSet.MarketOpportunityAbility`` (spec §7.17); ``IsBadIntrigue
    @0x4cc9de0``: false."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4cc9b40`` = ``Spice >= 2`` and ``Solari >= 5`` joined by a
        merged virtual call (UNTRACED: read as ``Or``)."""

        me = p.ctx.me
        return me.resources.spice >= 2 or me.resources.solari >= 5

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MarketOpportunityAbility::Evaluate @0x4cc9df0`` (spec §7.17).

        Answers the fixed ints 0 (2 spice -> 5 Solari) and 1 (5 Solari -> 5
        spice); a positive option 0 ends the evaluation.
        """

        choice = _Choice()
        me = p.ctx.me
        if not (
            _intrigue_hand_count(p) > 3
            or p.is_final_round()
            or (_in_player_turn(p, _UNDETERMINED) and me.agents_available > 0)
        ):
            return choice.answer("Market Opportunity")
        spice = me.resources.spice
        solari = me.resources.solari
        if spice >= 7 and solari <= 7:  # cmp 7; jl / jle
            choice.update_responses(100.0, ((0,),))
            return choice.answer(
                "Market Opportunity | SpiceCount >= 7, SolariCount <= 7"
            )
        if (
            spice >= 2
            and not me.swordmaster_acquired
            and solari <= _space_cost(p, _SWORDMASTER)
            and _open_to(p, _SWORDMASTER)
        ):
            choice.update_responses(100.0, ((0,),))
            return choice.answer("Market Opportunity | !Swordmaster")
        s1 = p.spice_value(1)
        o5 = 5.0 * p.solari_value(1)
        if spice >= 2:
            x = o5 - (s1 + s1)
            if x > 0:
                choice.update_responses(x, ((0,),))
                return choice.answer("Market Opportunity | 2 Spice -> 5 Solari")
        if solari >= 5:
            y = 5.0 * s1 - o5
            if y > 0:
                choice.update_responses(y, ((1,),))
        return choice.answer("Market Opportunity | 5 Solari -> 5 Spice")


@port("worm.canis.abilities.PlayAbilities.Uprising.MercenariesAbility")
class MercenariesAbility(IntrigueAbility):
    """``Uprising.MercenariesAbility`` (spec §7.18)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c445e0`` = ``Solari >= 3``."""

        return p.ctx.me.resources.solari >= 3

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c44720``: ``CurrentRound < 3``."""

        return p.ctx.round_number < 3

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MercenariesAbility::Evaluate @0x4c44930`` (spec §7.18)."""

        choice = _Choice()
        if not _deploy_window(p):
            return choice.answer("Mercenaries")
        if p.ctx.me.troops_supply <= 0:  # b__12_0
            return choice.answer("Mercenaries")
        if p.is_final_round() and _in_player_turn(p, _REVEAL_TURN):
            v = 100
        else:
            v = p.should_play_troop_intrigue("Mercenaries", 6, 4, 2)
        if v > 0:
            choice.update_responses(float(v), ())
        return choice.answer("Mercenaries")


@port("worm.canis.abilities.PlayAbilities.Uprising.OpportunismAbility")
class OpportunismAbility(IntrigueAbility):
    """``Uprising.OpportunismAbility`` (spec §7.19)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c454f0``: ``Solari >= 2`` and the influence summed over
        ``FactionList`` reaches 2 (``add r12d, eax; cmp r12d, 2``)."""

        me = p.ctx.me
        if me.resources.solari < 2:
            return False
        total = 0
        for faction in FACTIONS:
            total += _influence(me, faction)
            if total >= 2:
                return True
        return False

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c45ad0``: ``CurrentRound < 4``."""

        return p.ctx.round_number < 4

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``OpportunismAbility::Evaluate @0x4c45b00`` (spec §7.19).

        The tracks are shuffled before any gate (the RNG draw happens even
        when nothing is answered).
        """

        choice = _Choice()
        tracks = list(_targets(request, 0, Kind.TRACK))
        p.rng.shuffle(tracks)
        if not p.is_final_round():
            return choice.answer("Opportunism")
        if not _in_player_turn(p, _REVEAL_TURN):  # mov esi, 2
            return choice.answer("Opportunism")
        me = p.ctx.me
        if not any(  # b__0 @0x4c46dd0
            _influence(me, t.ref) == 1
            or _highest_opponent_rank(p, t.ref) - _influence(me, t.ref) >= 2
            for t in tracks
        ):
            return choice.answer("Opportunism")
        if len(tracks) >= 2:
            single = [
                (p.gain_influence_value(t.ref, -1, -1, False).sum, t.ref)
                for t in tracks
            ]
            top2 = sorted(single, key=lambda item: item[0], reverse=True)[:2]
            v = _dsum([value for value, _ in top2]) + 100.0  # b__16_3
            choice.update_responses(v, ((top2[0][1],), (top2[1][1],)))
        for track in tracks:
            if _influence(me, track.ref) < 2:  # b__4 @0x4c46e40
                continue
            v = p.gain_influence_value(track.ref, -2, -1, False).sum + 100.0
            choice.update_responses(v, ((track.ref,), (track.ref,)))
        return choice.answer("Opportunism")


@port("worm.canis.abilities.PlayAbilities.BaseSet.ShaddamsFavorAbility")
class ShaddamsFavorAbility(IntrigueAbility):
    """``BaseSet.ShaddamsFavorAbility`` (spec §7.20); ``Cost @0x4ccb530``:
    none."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4ccb650``: ``Emperor influence < 2``."""

        return p.ctx.me.influence.emperor < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ShaddamsFavorAbility::Evaluate @0x4ccb860`` (spec §7.20)."""

        choice = _Choice()
        me = p.ctx.me
        play = False
        if me.influence.emperor > 2:  # cmp 2; jle
            play = True
        elif me.troops_supply <= 0:  # b__11_0: no troop in Supply
            return choice.answer("Shaddam's Favor")
        elif _intrigue_hand_count(p) > 3 or p.is_final_round():
            play = True
        elif _deploy_window(p):
            if me.influence.emperor < 2:
                play = True
            elif p.current_conflict_interest().sum > p.conflict_posture_bounds()[1]:
                play = True
        if play:
            choice.update_responses(100.0, ())
        return choice.answer("Shaddam's Favor | 100")


@port("worm.canis.abilities.PlayAbilities.BaseSet.SietchRitualAbility")
class SietchRitualAbility(IntrigueAbility):
    """``BaseSet.SietchRitualAbility`` (spec §7.21)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4ccc300`` = ``HasImperiumCardInHand.AtLeast(1)``."""

        return len(p.ctx.hand) >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4ccc6e0`` = ``!ShowHinting`` (@0x4ccc690):
        ``!(CanGainFactionInfluence(Fremen) || CanGainFactionInfluence(BG))``."""

        me = p.ctx.me
        return not (
            _can_gain_faction_influence(me, "fremen")
            or _can_gain_faction_influence(me, "bene_gesserit")
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SietchRitualAbility::Evaluate @0x4ccc700`` (spec §7.21).

        Every track is priced as a *Fremen* gain (``esi = 4`` at 0x4cccadb, app
        quirk kept), so the first track in target order wins.
        """

        choice = _Choice()
        no_bonus = _intrigue_hand_count(p) <= 3 and not p.is_climax()
        tracks = _targets(request, 1, Kind.TRACK)
        order = p.discard_order(_targets(request, 0, Kind.CARD), False)
        if not order:
            return choice.answer("Sietch Ritual")
        discard = order[0]
        for track in tracks:
            v = Summer()
            v.merge(p.gain_influence_value("fremen", 1, -1, False))
            if not no_bonus:
                v.add("Four Intrigue or Climax", 10.0)
            if v.sum >= 3.0:
                choice.update_responses(v.sum, ((discard.ref,), (track.ref,)))
        return choice.answer("Sietch Ritual")


@port("worm.canis.abilities.PlayAbilities.Uprising.SpecialMissionAbility")
class SpecialMissionAbility(IntrigueAbility):
    """``Uprising.SpecialMissionAbility`` (spec §7.22); no ``IsBadIntrigue``."""

    def _can_deploy_on_circle(self, p: Profile) -> bool:
        """``CanDeployOnCircle @0x4c505a0``: a City post with no spy at all
        (b__7_0: ``!post.HasSpy && IsCircleObservationPost``); P's spy supply
        is not checked."""

        return any(p.ctx.post_owner(post) is None for post in sorted(_CITY_POSTS))

    def _can_recall_spy(self, p: Profile) -> bool:
        """``CanRecallSpy @0x4c50770``: ``GetDeployedSpies(P).Any()``."""

        return _deployed_spies(p) > 0

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c50820`` = ``CanDeployOnCircle`` joined to
        ``CanRecallSpy`` by a merged virtual call (UNTRACED: read as ``Or``)."""

        return self._can_deploy_on_circle(p) or self._can_recall_spy(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SpecialMissionAbility::Evaluate @0x4c50cf0`` (spec §7.22)."""

        choice = _Choice()
        s1 = p.spice_value(1)
        sv = p.spy_value().sum
        can_place = self._can_deploy_on_circle(p)
        can_recall = self._can_recall_spy(p)
        if can_place:
            if not p.ctx.me.maker_hooks and sv > s1:
                choice.update_responses(sv, ((0,),) if can_recall else ())
                return choice.answer("Special Mission Place Spy")
            if not (s1 - sv >= 1.0 or p.intrigue_blow_wall()):
                return choice.answer("Special Mission")
        if not can_recall:
            return choice.answer("Special Mission | Recall Spy:No Circle posts")
        v = Summer()
        v.add("Recall Spy", p.recall_spy_value().sum)
        v.add("Blow Wall", p.blow_wall_value().sum)
        v.add("2 Spice", p.spice_value(2))
        spies = (
            _targets(request, 1, Kind.SPY)
            if can_place
            else _targets(request, 0, Kind.SPY)
        )
        spy, _ = p.recall_spy(spies)
        if spy is None:
            return choice.answer("Special Mission")
        responses: tuple[ResponseItem, ...] = (
            ((1,), (spy.ref,)) if can_place else ((spy.ref,),)
        )
        choice.update_responses(v.sum, responses)
        return choice.answer("Special Mission Recall Spy")


@port("worm.canis.abilities.PlayAbilities.Uprising.StrategicStockpilingAbility")
class StrategicStockpilingAbility(IntrigueAbility):
    """``Uprising.StrategicStockpilingAbility`` (spec §7.23)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c553b0`` = ``HasInfluenceAndWater`` (@0x4c552b0: ``Water
        >= 3 .Then(Fremen >= 3)``) joined to ``Spice >= 5`` (UNTRACED
        combinator: read as ``Or``)."""

        me = p.ctx.me
        water_line = me.resources.water >= 3 and me.influence.fremen >= 3
        return water_line or me.resources.spice >= 5

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c55c60`` (spec §7.23): reads the *Emperor*
        track (``mov esi, 1`` at 0x4c55cbc), app quirk kept."""

        me = p.ctx.me
        if p.ctx.round_number < 4:
            return True
        if me.resources.spice > 2:
            return False
        if me.resources.water < 2:
            return True
        return me.influence.emperor < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StrategicStockpilingAbility::Evaluate @0x4c55ce0`` (spec §7.23):
        ``Int(1)`` = ``button.confirm``."""

        choice = _Choice()
        if not p.is_climax():
            return choice.answer("Strategic Stockpiling")
        if not (_in_player_turn(p, _REVEAL_TURN) or _intrigue_hand_count(p) >= 4):
            return choice.answer("Strategic Stockpiling")
        choice.update_responses(100.0, ((1,),))
        return choice.answer("Strategic Stockpiling | 100")

    def choose_yes(self) -> int:
        """``ChooseYesEvaluator @0x4c55eb0``: the water line is always "yes"
        (``AIChoiceCustom(response = 1)``)."""

        return 1


@port("worm.canis.abilities.PlayAbilities.Uprising.UnexpectedAlliesAbility")
class UnexpectedAlliesAbility(IntrigueAbility):
    """``Uprising.UnexpectedAlliesAbility`` (spec §7.24)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c59310`` = ``Water >= 2``."""

        return p.ctx.me.resources.water >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c59540``: ``Water == 0``."""

        return p.ctx.me.resources.water == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``UnexpectedAlliesAbility::Evaluate @0x4c59560`` (spec §7.24): the
        window is ``opp[1] - 3 < exp <= opp[1]`` (the second-strongest
        opponent)."""

        choice = _Choice()
        if len(p.ctx.opponents) < 2:  # cmp 2; jl
            return choice.answer("Unexpected Allies")
        interest = p.current_conflict_interest().sum
        if not interest >= p.conflict_posture_bounds()[0]:  # ucomisd; jb (NaN too)
            return choice.answer("Unexpected Allies")
        opp = sorted(
            (p.est_opponent_strength(o.player_id).sum for o in p.ctx.opponents),
            reverse=True,
        )  # b__13_0 / b__13_1
        exp = p.est_strength().sum
        if exp > opp[1]:  # jg
            return choice.answer("Unexpected Allies")
        if exp + 3 <= opp[1]:  # jle
            return choice.answer("Unexpected Allies")
        choice.update_responses(100.0, ())
        return choice.answer("Unexpected Allies | 100")


# ---------------------------------------------------------------------------
# Endgame intrigues (spec §8): no AI hook, auto-played by EndgamePhase
# ---------------------------------------------------------------------------


class _EndgameIntrigueAbility(IntrigueAbility):
    """Shared timing of the four Endgame ability classes (not an app class:
    each derives from ``IntrigueAbility``; every ctor stores timing 4)."""

    ability_timing: ClassVar[int] = ENDGAME_TIMING


@port("worm.canis.abilities.PlayAbilities.Uprising.CHOAMProfitsAbility")
class CHOAMProfitsAbility(_EndgameIntrigueAbility):
    """``Uprising.CHOAMProfitsAbility`` (spec §8.1; CHOAM only).

    ``Cost @0x4c06320`` = NoCost: always played; scores only with 4+
    completed contracts.
    """

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c06510``: completed < 2 -> true, == 2 ->
        ``IsClimax``, > 2 -> false."""

        completed = len(p.ctx.me.completed_contract_ids)
        if completed < 2:
            return True
        if completed == 2:
            return p.is_climax()
        return False


@port("worm.canis.abilities.PlayAbilities.Uprising.SecureSpiceTradeAbility")
class SecureSpiceTradeAbility(_EndgameIntrigueAbility):
    """``Uprising.SecureSpiceTradeAbility`` (spec §8.2)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c4df60``: ``CountTheSpiceMustFlow >= 2``."""

        return _count_the_spice_must_flow(p) >= 2

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c4e2e0``: ``CountTheSpiceMustFlow == 0``."""

        return _count_the_spice_must_flow(p) == 0


@port("worm.canis.abilities.PlayAbilities.Uprising.ShadowAllianceAbility")
class ShadowAllianceAbility(_EndgameIntrigueAbility):
    """``Uprising.ShadowAllianceAbility`` (spec §8.3); ``Cost @0x4c4ed80`` =
    NoCost: always played."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue @0x4c4f2e0``: every faction has P's influence < 3
        (b__0 ``cmp 3; jl``; the effect needs 4) or no opponent in its
        Alliance (b__1 @0x4c4f570)."""

        me = p.ctx.me
        return all(
            _influence(me, f) < 3
            or all(f not in o.alliance_faction_ids for o in p.ctx.opponents)
            for f in FACTIONS
        )


@port(
    "worm.canis.abilities.PlayAbilities.Uprising.CompleteBattleIconPairEndgameAbility"
)
class CompleteBattleIconPairEndgameAbility(_EndgameIntrigueAbility):
    """``Uprising.CompleteBattleIconPairEndgameAbility`` (spec §8.4): the
    Endgame half of Crysknife, Desert Mouse and Ornithopter;
    ``IsBadIntrigue @0x4c07810`` = false."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost @0x4c074f0`` = ``HasMatchingBattleIcon(Owner,
        includeWilds=true)``: P's list holds the card's icon or a Wildcard
        (``CanBePaid @0x4a73fb0`` internals UNTRACED)."""

        icon = str(self.owner.attr("BattleIcon", _NO_ICON))
        return any(i in (icon, _WILDCARD) for _, i in battle_icon_list(p.ctx.me))


# ---------------------------------------------------------------------------
# Endgame window helpers (spec §2.3, §8.4; ScoreBattleIconsPairs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BattleIconSet:
    """One set ``ScoreBattleIconsPairs`` completes (``BattleIconSetPoints``:
    1 VP). ``refs`` are the removed list entries (battle card ids, or the
    intrigue instance id of the added icon), standard icons first."""

    icon: str
    refs: tuple[str, ...]
    wild: bool


def _remove_n(items: list[tuple[str, str]], icon: str, n: int) -> tuple[str, ...]:
    """``ScoreBattleIconsPairs::RemoveN @0x1397800``: ``n`` times
    ``List.Remove`` (first occurrence); returns the removed refs."""

    removed: list[str] = []
    for _ in range(n):
        index = next((k for k, item in enumerate(items) if item[1] == icon), None)
        if index is None:
            break
        removed.append(items.pop(index)[0])
    return tuple(removed)


def _counts(items: Sequence[tuple[str, str]]) -> list[tuple[str, int]]:
    """``ListUtil.Counts``: per icon, in first-occurrence order (UNTRACED:
    a ``Dictionary`` filled in list order and never shrunk)."""

    counts: dict[str, int] = {}
    for _, icon in items:
        counts[icon] = counts.get(icon, 0) + 1
    return list(counts.items())


def score_battle_icons_pairs(
    icons: Sequence[tuple[str, str]],
    *,
    include_wildcards: bool,
    additional: tuple[str, str] | None = None,
    requirement: int = 2,
) -> tuple[tuple[BattleIconSet, ...], tuple[tuple[str, str], ...]]:
    """``ScoreBattleIconsPairs/<execute>d__6::MoveNext @0x4a61e40``.

    ``icons`` is ``BattleIconList`` as ``(ref, app icon)``. Returns the
    completed sets in scoring order and the list left afterwards.
    ``BattleIconSetRequirement``/``Points`` default to 2/1 and the intrigue
    constructor (@0x4a61940, ``additional``) forces them. Steps:

    1. ``additional`` is appended to the list.
    2. Natural sets: per icon other than None/Wildcard (b__6_0) in
       ``Counts`` order, while ``remaining >= requirement`` remove
       ``requirement`` of it (``remaining -= requirement`` at 0x4a62702).
    3. With ``include_wildcards``: standard = the ``additional`` icon only
       (b__2) or every non-wild icon (``ListUtil.Partition``), wild = the
       Wildcards (b__6_3/b__6_5); for ``k = 1 ..`` while ``w = requirement -
       k > 0``: each icon (one ``Counts`` pass) with ``>= k`` standard and
       ``>= w`` wild left completes a set. Wildcards never pair with each
       other.
    4. An unused ``additional`` icon is removed again (``List.Remove``).
    """

    items = list(icons)
    if additional is not None:
        requirement = 2  # movabs 0x100000002: requirement 2, points 1
        items.append(additional)
    sets: list[BattleIconSet] = []
    for icon, remaining in _counts(
        [it for it in items if it[1] not in (_NO_ICON, _WILDCARD)]
    ):
        while remaining >= requirement:
            refs = _remove_n(items, icon, requirement)
            if len(refs) == requirement:
                sets.append(BattleIconSet(icon, refs, False))
            remaining -= requirement
    if include_wildcards:
        if additional is not None:
            standard = [it for it in items if it[1] == additional[1]]
            wild = [it for it in items if it[1] == _WILDCARD]
        else:
            present = [it for it in items if it[1] != _NO_ICON]
            wild = [it for it in present if it[1] == _WILDCARD]
            standard = [it for it in present if it[1] != _WILDCARD]
        k = 1
        while requirement - k > 0:
            w = requirement - k
            for icon, count in _counts(standard):
                if count < k or len(wild) < w:
                    continue
                if len(_remove_n(standard, icon, k)) != k:
                    continue
                if len(_remove_n(wild, _WILDCARD, w)) != w:
                    continue
                refs = _remove_n(items, icon, k) + _remove_n(items, _WILDCARD, w)
                sets.append(BattleIconSet(icon, refs, True))
            k += 1
    if additional is not None:
        for index, item in enumerate(items):
            if item[1] == additional[1]:
                del items[index]
                break
    return tuple(sets), tuple(items)


def endgame_auto_plays(p: Profile) -> list[tuple[Entity, IntrigueAbility]]:
    """``EndgamePhase/<PlayEndgameIntrigues>d__9`` for this seat (spec §2.3).

    The app plays, for every seat, each Endgame-timed ability that can run of
    every held card with an Endgame type (``get_PlayableEndgameIntrigueCards
    @0x49fbb10`` + ``b__9_2``), all decided before the first play. Seats are
    ordered by VP ascending (stable over turn order); one seat's plays keep
    hand order, then ability order. Our engine opens one window per seat
    clockwise from the First Player (OQ-001); the effects are seat-local, so
    a window plays this list in order and the outcome is the same.
    """

    plays: list[tuple[Entity, IntrigueAbility]] = []
    for instance in p.ctx.intrigue_cards:
        card = intrigue_entity(instance, p.ctx.seat)
        if "Endgame" not in card.list_attr("IntrigueTypeList"):
            continue
        playable = [
            a
            for a in abilities_of(card)
            if isinstance(a, IntrigueAbility)
            and a.ability_timing == ENDGAME_TIMING
            and a.can_be_run(p)
        ]
        plays.extend((card, a) for a in playable)
    return plays


def complete_battle_icon_pair_card(p: Profile, card: Entity) -> str | None:
    """The battle card the Endgame half of ``card`` (Crysknife, Desert Mouse,
    Ornithopter) pairs with: ``ScoreBattleIconsPairs(true, icon)``
    (``<RunImmediateEffects>d__6`` @0x4c079df) on P's list with the card's
    icon added. A natural match beats a Wildcard; None when nothing pairs.
    Our engine asks this as ``flip_battle_card(card_id)``.
    """

    icon = str(card.attr("BattleIcon", _NO_ICON))
    sets, _ = score_battle_icons_pairs(
        battle_icon_list(p.ctx.me),
        include_wildcards=True,
        additional=(card.ref, icon),
    )
    for scored in sets:
        if card.ref in scored.refs:
            others = [ref for ref in scored.refs if ref != card.ref]
            return others[0] if others else None
    return None


def endgame_wild_pairs(p: Profile) -> list[tuple[str, str]]:
    """The closing ``ScoreBattleIconsPairs(includeWildcards=true)`` per seat
    (``EndgamePhase`` @0x4a000a2, after every Endgame intrigue).

    ``(matching card id, wild card id)`` per wildcard set, in the app's order:
    our ``match_endgame_wild_icon`` arguments. Natural pairs are already
    flipped at each combat (``CombatPhase`` runs the same action without
    wildcards; ours ``combat._matching_battle_card``).
    """

    sets, _ = score_battle_icons_pairs(
        battle_icon_list(p.ctx.me), include_wildcards=True
    )
    pairs: list[tuple[str, str]] = []
    for scored in sets:
        if scored.wild and len(scored.refs) == 2:
            pairs.append((scored.refs[0], scored.refs[1]))
    return pairs


__all__ = [
    "COMBAT_TIMING",
    "ENDGAME_TIMING",
    "GET_COMBINATIONS_BUDGET",
    "PLOT_TIMING",
    "BattleIconSet",
    "IntrigueAbility",
    "StrengthIntrigueAbility",
    "ability_for_prompt",
    "battle_icon_list",
    "choose_faction_influence",
    "complete_battle_icon_pair_card",
    "endgame_auto_plays",
    "endgame_wild_pairs",
    "get_combinations",
    "intrigue_deploy_troops",
    "score_battle_icons_pairs",
]
