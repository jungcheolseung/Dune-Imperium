"""Rise of Ix's Intrigue abilities (``PlayAbilities.RiseOfIx``).

Ports of the ability classes of the 17 ``IntrigueArchetypes.RiseOfIx`` cards
(``docs/app-ai-plan.md`` §13.4 slice 7), read from the P6 Ix decompilation
(assets ``ghidra/p6ix/<addr>.c``, index ``ghidra/p6ix/targets-named.tsv``)
and confirmed line by line in the annotated disassembly
(``dump/asm/worm-canis.dll/worm.canis.abilities.PlayAbilities.RiseOfIx.
<Class>.asm``).

``GlimpseThePathAbility`` and ``IxianProbeAbility`` read
``WormAIProfile::GetBestOption`` @0x4911370 (the best ``(card, space, value)``
of the hand), ``original_intrigue.best_option``.

App class chains (``dump/worm-canis.dll.cs``):

- ``PlayAbilities.IntrigueAbility`` <- ``RiseOfIx.AdvancedWeaponryPlotAbility``,
  ``CullAbility``, ``DiversionAbility``, ``ExpediteAbility``,
  ``FinessePlotAbility``, ``MachineCulturePlotAbility``,
  ``QuidProQuoAbility``, ``SecretForcesAbility``, ``StrongarmAbility``
  (Plot); ``GrandConspiracyAbility``, ``MachineCultureEndgameAbility``,
  ``WarChestEndgameAbility`` (Endgame: each ``.ctor`` stores timing 4);
- ``PlayAbilities.StrengthIntrigueAbility`` <-
  ``RiseOfIx.AdvancedWeaponryCombatAbility``, ``BlackmailAbility``,
  ``CannonTurretsAbility``, ``FinesseCombatAbility``, ``SecondWaveAbility``,
  ``StrategicPushAbility``, ``WarChestCombatAbility`` (Combat).

Advanced Weaponry, Finesse, Machine Culture and War Chest carry two of these
(``WormAbilityIDs``); a window evaluates the half ``ability_for_prompt``
names. No class here overrides ``ValueForPlayer``, ``SelectionMode`` or
``SpecificAcquireValue``; ``ShowHinting`` is the UI's, and
``IsEndgamePlayable`` / ``GetConditionalEndgameVP`` have no AI caller (as in
``abilities/original_intrigue.py``).

Request / answer encoding (on top of ``abilities/intrigue.py``'s; what a
window builds and what ``evaluate`` reads). ``request.infos[i]`` is the app's
target information ``i`` of the ability. Per card (only the infos the
ability reads; every other card reads none):

- Blackmail: ``infos[0]`` the faction TRACKs to lose an Influence on; the
  answer is ``((track,),)``.
- Cull: ``infos[0]`` the CARDs that may be trashed; the answer is
  ``((card,),)``.
- Diversion, Expedite: no info; the answer is the Freighter's
  ``IntTargetResponse`` ``((item1,),)`` (1 = recall, 0 = advance;
  ``abilities/ix_board.FREIGHTER_RECALL``).
- Finesse (Plot): ``infos[0]`` the TRACKs of the loss (``InfluenceDelta`` -1,
  ``abilities.FinessePlotAbility.minusone``), ``infos[1]`` those of the gain
  (+1, ``plusone``; ``<Targets>d__7`` yields them in that order); the answer
  is ``((lose,), (gain,))``.
- Machine Culture (Plot): ``infos[0]`` the Tech tiles offered; the answer is
  ``((tile,),)``.
- Second Wave: ``infos[0].options`` one index per garrison unit offered, the
  seat's garrison dreadnoughts first (the order ``GetUnitsToDeploy``'s
  ``OrderByDescending(Strength)`` gives them); ``max_select`` the
  ``NumberToSelect`` (``Min(garrison, 2)``); the answer is
  ``((indices...),)``.
- Strongarm: ``infos[0].options`` the ``ChooseOne`` (0 = lose a garrison
  troop, 1 = a deployed one; ``<Targets>d__6`` adds "garrison" then
  "deployed" and asks only when both exist); the answer is ``((option,),)``.

Answers follow ``abilities/intrigue.py`` (``WormAIChoiceSelectionWithTargets``,
``_Choice``): ``Answer.response is None`` = nothing stored (value 0); ``()`` =
"play it" with no sub-targets (``UpdateSelectionTargets(v, src, null)``).

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

import sys
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Pile,
    Request,
    port,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _REVEAL_TURN,
    _TSMF_ARCHETYPES,
    _UNDETERMINED,
    ENDGAME_TIMING,
    IntrigueAbility,
    StrengthIntrigueAbility,
    _can_gain_faction_influence,
    _Choice,
    _count_the_spice_must_flow,
    _in_player_turn,
    _influence,
    _intrigue_hand_count,
    _targets,
)
from dune_imperium.agents.app_ai.abilities.tech import is_tech_tile
from dune_imperium.agents.app_ai.catalog import (
    FACTION_NAMES,
    board_space_ids,
    card_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.strength import dreadnought_strength

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_PA: Final = "worm.canis.abilities.PlayAbilities.RiseOfIx."

_APP_TO_FACTION: Final = {app: ours for ours, app in FACTION_NAMES.items()}
#: ``f64=-1.7976931348623157e+308`` (``double.MinValue``): Blackmail's start.
_DOUBLE_MIN: Final = -sys.float_info.max

# ---------------------------------------------------------------------------
# Shared reads
# ---------------------------------------------------------------------------


def _tech_tile_count(p: Profile) -> int:
    """``P.TechTileCount`` (@0x4844320) and ``HasTechTiles``: the seat's Tech
    tiles (``tech_ids``, public)."""

    return len(p.ctx.me.tech_ids)


def _active_space(p: Profile) -> Entity | None:
    """``P.ActiveSpace.FirstOrDefault()`` (@0x483dd20): this Agent turn's space.

    Judgement (as ``abilities/imperium_a._active_space``): the ``space_id`` of
    the seat's own open ``agent_effects`` frame; none outside an Agent turn.
    """

    context = p.ctx.own_frame_context("agent_effects")
    if context is None:
        return None
    space_id = context.get("space_id")
    if not isinstance(space_id, str) or not space_id:
        return None
    return space_entity(space_id, p.ctx.board)


def _is_combat_space(space: Entity) -> bool:
    """``WormEntityExtensions::IsCombatSpace`` @0x482e130."""

    return space.attr("CombatSpace", False) is True


def _space_faction(space: Entity) -> str | None:
    """``space.Faction()`` (@0x4828ff0) as our faction id; ``None`` for
    ``Factions.None``."""

    app_faction = space.attr("Faction")
    if not isinstance(app_faction, str):
        return None
    return _APP_TO_FACTION.get(app_faction)


def _has_any_influence(p: Profile) -> bool:
    """``HasFactionInfluence.AtLeast(F, 1)`` for Emperor (1), Fremen (4), Bene
    Gesserit (3) and Spacing Guild (2), joined with ``CostAction::Or``."""

    me = p.ctx.me
    return any(_influence(me, f) >= 1 for f in FACTIONS)


def _endgame_started(p: Profile) -> bool:
    """``Playmat.GetAttributeValue<bool>(EndgameStarted)``.

    Judgement: our engine's Endgame phase (``GamePhase.ENDGAME``, then
    ``FINISHED``), the phases ``rules/endgame.py`` reads as the endgame.
    """

    return p.ctx.state.phase in (GamePhase.ENDGAME, GamePhase.FINISHED)


# ---------------------------------------------------------------------------
# Advanced Weaponry
# ---------------------------------------------------------------------------


@port(_PA + "AdvancedWeaponryPlotAbility")
class AdvancedWeaponryPlotAbility(IntrigueAbility):
    """``RiseOfIx.AdvancedWeaponryPlotAbility``: the Plot half (pay 3 Solari
    for a dreadnought)."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bdfb40: ``HasResources.AtLeast(Solari, 3)`` then
        (``CostAction::Then``, vslot 13) ``HasUnitsInSupply<WormDreadnought>
        .Any``."""

        me = p.ctx.me
        return me.resources.solari >= 3 and me.dreadnoughts_supply > 0

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bdfd40: false with more than one Tech tile
        (``cmp eax, 1; jg``); else fewer than 2 dreadnoughts in the Supply
        (``Supply.children.OfType<WormDreadnought>().Count()``, ``cmp eax, 2;
        setl``)."""

        if _tech_tile_count(p) > 1:
            return False
        return p.ctx.me.dreadnoughts_supply < 2

    def troop_value(self, p: Profile) -> int:
        """``TroopValue`` @0x4bdfdd0 (vslot 86): the ``Strength`` of
        ``GetNextUnits<WormDreadnought>(1).FirstOrDefault()``, 0 for none."""

        me = p.ctx.me
        if me.dreadnoughts_supply <= 0:
            return 0
        return dreadnought_strength(me)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``AdvancedWeaponryPlotAbility::Evaluate`` @0x4bdfe60.

        Only on a combat space (``ActiveSpace.FirstOrDefault()``,
        ``IsCombatSpace``), and only when ``GetDreadnoughtValue(1, false)``
        reaches ``GetSolariValue(1) * 3.0 + 1.0`` (``mulsd f64=3.0``,
        ``addsd f64=1.0``, ``ucomisd; jb``): then the literal 1.0 with no
        sub-targets.
        """

        choice = _Choice()
        space = _active_space(p)
        if space is None or not _is_combat_space(space):
            return choice.answer("Advanced Weaponry (Plot)")
        solari = p.solari_value(1)
        if p.dreadnought_value(1, False) < solari * 3.0 + 1.0:
            return choice.answer("Advanced Weaponry (Plot)")
        choice.update_targets(1.0, None)
        return choice.answer("Advanced Weaponry (Plot) | 1")


@port(_PA + "AdvancedWeaponryCombatAbility")
class AdvancedWeaponryCombatAbility(StrengthIntrigueAbility):
    """``RiseOfIx.AdvancedWeaponryCombatAbility`` (Strength 4, CombatValue
    5.0): the base ``Evaluate``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bdf390: ``RiseOfIx.HasTechTiles.AtLeast(3)``."""

        return _tech_tile_count(p) >= 3


# ---------------------------------------------------------------------------
# The other Combat intrigues
# ---------------------------------------------------------------------------


@port(_PA + "BlackmailAbility")
class BlackmailAbility(StrengthIntrigueAbility):
    """``RiseOfIx.BlackmailAbility`` (Strength 5, CombatValue 6.5): lose one
    Influence for the swords."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4be07d0 (``_has_any_influence``)."""

        return _has_any_influence(p)

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4be0a30: ``GetGameArc() == 0``."""

        return p.game_arc() == 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``BlackmailAbility::Evaluate`` @0x4be0a60.

        ``StrengthIntrigueAbility::Evaluate`` (called non-virtually) gives
        ``v``; ``v <= 0`` returns the empty choice. The faction tracks
        (``GetTargets(...).OfType<WormFactionTrack>()``) are shuffled
        (``ListUtil.Shuffle``, here ``p.rng``) and the one whose
        ``G(F, -1, -1, false)`` is strictly highest from ``double.MinValue``
        (``ucomisd; jbe`` keeps the earlier) is stored at ``v``.
        """

        choice = _Choice()
        v = self._strength_choice(p).value
        if not v > 0.0:  # ``ucomisd v, 0.0; jbe`` @0x4be0b9f: NaN returns too
            return choice.answer("Blackmail")
        tracks = list(_targets(request, 0, Kind.TRACK))
        p.rng.shuffle(tracks)
        best: Entity | None = None
        best_value = _DOUBLE_MIN
        for track in tracks:
            g = p.gain_influence_value(track.ref, -1, -1, False)
            if g.sum > best_value:
                best, best_value = track, g.sum
        if best is None:
            return choice.answer("Blackmail")
        choice.update_targets(v, (best.ref,))
        return choice.answer(f"Blackmail | losing {best.ref}")


@port(_PA + "CannonTurretsAbility")
class CannonTurretsAbility(StrengthIntrigueAbility):
    """``RiseOfIx.CannonTurretsAbility`` (Strength 2, CombatValue 4.0): the
    base ``Evaluate``; ``Cost`` @0x4be1ec0 = NoCost."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue`` @0x4be1fd0 (vslot 88; no ``MeetsCost``).

        The seats ahead of the player in ``GetCurrentCombatOrder()``
        (``TakeWhile(b__0)``: ``seat != player``); when every one of them has
        a dreadnought in the Conflict (``All(b__1)``:
        ``GetPlayerDeployed(seat).children.OfType<WormDreadnought>().Any()``;
        true for no seat ahead) the card's ``Strength`` plus 3 (``add eax,
        3``), else its ``Strength``.
        """

        strength = self.owner.int_attr("Strength")
        ahead: list[int] = []
        for seat in p.current_combat_order():
            if seat == p.ctx.seat:
                break
            ahead.append(seat)
        if all(p.ctx.player(seat).dreadnoughts_conflict > 0 for seat in ahead):
            return strength + 3
        return strength

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4be2250: every opponent holds both
        dreadnoughts in its Supply (``b__9_0``: ``Count() == 2``)."""

        return all(o.dreadnoughts_supply == 2 for o in p.ctx.opponents)


@port(_PA + "FinesseCombatAbility")
class FinesseCombatAbility(StrengthIntrigueAbility):
    """``RiseOfIx.FinesseCombatAbility`` (Strength 2, CombatValue 2.0): the
    Combat half of Finesse; the base ``Evaluate``; ``Cost`` @0x4be6e00 =
    NoCost."""


@port(_PA + "SecondWaveAbility")
class SecondWaveAbility(StrengthIntrigueAbility):
    """``RiseOfIx.SecondWaveAbility`` (Strength 2, CombatValue 7.0): deploy up
    to two garrison units. ``Cost`` @0x4bf7080 = NoCost."""

    def strength_value(self, p: Profile) -> int:
        """``StrengthValue`` @0x4bf71b0 (no ``MeetsCost``): ``Strength + 2 *
        Min(2, GarrisonTroops)`` (``lea eax, [rax + r14*2]``; Bloodlines
        Commanders count, bloodlines-systems.md §1.1, D1)."""

        garrison = min(2, p.garrison_troop_count())
        return self.owner.int_attr("Strength") + 2 * garrison

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SecondWaveAbility::Evaluate`` @0x4bf7240.

        ``StrengthIntrigueAbility::Evaluate`` (non-virtual) gives ``v`` (not
        tested). With a first target information its units go through
        ``GetUnitsToDeploy(units, NumberToSelect)`` (strongest first:
        ``units_to_deploy_split`` over the offered dreadnoughts and troops)
        and are stored at ``v`` (``UpdateSelectionTargets``; none chosen
        stores an empty list).
        """

        choice = _Choice()
        v = self._strength_choice(p).value
        if not request.infos:
            return choice.answer("Second Wave")
        info = request.infos[0]
        units = info.options
        dreadnoughts = min(p.ctx.me.dreadnoughts_garrison, len(units))
        troops = len(units) - dreadnoughts
        n_dreads, n_troops = p.units_to_deploy_split(
            troops, dreadnoughts, info.max_select
        )
        chosen = (
            *units[: min(n_dreads, dreadnoughts)],
            *units[dreadnoughts : dreadnoughts + min(n_troops, troops)],
        )
        choice.update_targets(v, chosen)
        return choice.answer(f"Second Wave | {v} | {len(chosen)}")


@port(_PA + "StrategicPushAbility")
class StrategicPushAbility(StrengthIntrigueAbility):
    """``RiseOfIx.StrategicPushAbility`` (Strength 2, CombatValue 0.5): the
    base ``Evaluate``; ``Cost`` @0x4bf9700 = NoCost."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bf9810: ``GetGameArc() == 2``."""

        return p.game_arc() == 2


@port(_PA + "WarChestCombatAbility")
class WarChestCombatAbility(StrengthIntrigueAbility):
    """``RiseOfIx.WarChestCombatAbility`` (Strength 4, CombatValue 3.0): the
    Combat half of War Chest; the base ``Evaluate``."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bfd400: ``HasResources.AtLeast(Solari, 2)``."""

        return p.ctx.me.resources.solari >= 2


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


@port(_PA + "CullAbility")
class CullAbility(IntrigueAbility):
    """``RiseOfIx.CullAbility``: pay a Solari to trash a card."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4be32e0: ``HasResources.AtLeast(Solari, 1)``."""

        return p.ctx.me.resources.solari >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4be34f0: ``GetGameArc() != 0`` (``setne``)."""

        return p.game_arc() != 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``CullAbility::Evaluate`` @0x4be3520.

        Held back at exactly 8 Solari without the Swordmaster (``cmp eax, 8;
        je``) and at exactly 5 (``cmp eax, 5; je``). Needs a card worth
        trashing among the discard pile and the cards in play
        (``Discard.children ++ AllCardsInPlay``, ``b__11_0``: ``TrashValue >=
        1.0``, ``ucomisd; setae``). Then ``GetCardToTrash(targets, 1.0)``
        (``f64=1.0``) is stored at its value.
        """

        choice = _Choice()
        me = p.ctx.me
        solari = me.resources.solari
        if (not me.swordmaster_acquired and solari == 8) or solari == 5:
            return choice.answer("Cull")
        seat = p.ctx.seat
        cards = [card_entity(i, seat) for i in (*me.discard_pile, *me.in_play)]
        if not any(c.float_attr("TrashValue", 0.0) >= 1.0 for c in cards):
            return choice.answer("Cull")
        card, value = p.card_to_trash(_targets(request, 0, Kind.CARD), 1.0)
        if card is None:
            return choice.answer("Cull")
        choice.update_targets(value, (card.ref,))
        return choice.answer(f"Cull | trashing {card.ref} | {value}")


class _FreighterIntrigue(IntrigueAbility):
    """Diversion and Expedite: a Freighter icon on an Intrigue card."""

    def _freighter_answer(self, p: Profile, item1: int, label: str) -> Answer:
        """``UpdateSelectionResponses(FreighterValue, src,
        [IntTargetResponse(item1)])``.

        The app reads ``get_FreighterValue`` twice, once for the log line and
        once for the value; only the value's read is made here (as
        ``ix_board.FreighterAbility``), so the RNG of a level-2 selection is
        drawn once for the response and once for the value.
        """

        choice = _Choice()
        choice.update_responses(p.freighter_value(), ((item1,),))
        return choice.answer(label)


@port(_PA + "DiversionAbility")
class DiversionAbility(_FreighterIntrigue):
    """``RiseOfIx.DiversionAbility``: after deploying four units this turn,
    the Freighter."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4be4650: ``HasUnitsDeployedThisTurn<WormUnit>
        .AtLeast(4)`` (our turn counter and its peak, as Distraction's
        ``.AtLeast(3)`` in ``abilities/intrigue.py``)."""

        me = p.ctx.me
        return max(me.units_deployed_turn, me.units_deployed_peak) >= 4

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4be4790: ``GetGameArc() == 2``."""

        return p.game_arc() == 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``DiversionAbility::Evaluate`` @0x4be47c0: ungated;
        ``sel = GetFreighterSelections(-1)``, the response is ``sel.Item1`` at
        ``FreighterValue``."""

        recall, _, log = p.freighter_selections(-1)
        verb = "Recall" if recall == 1 else "Advance"
        return self._freighter_answer(p, recall, f"Diversion | {verb} | {log}")


@port(_PA + "ExpediteAbility")
class ExpediteAbility(_FreighterIntrigue):
    """``RiseOfIx.ExpediteAbility``: pay a spice for the Freighter."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4be5a00: ``HasResources.AtLeast(Spice, 1)``."""

        return p.ctx.me.resources.spice >= 1

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4be5b50: in the Late arc (``GetGameArc() ==
        2``) a Freighter below space 2 (``GetShippingTrackSpace``, ``cmp eax,
        2; setl``); any other arc: false."""

        if p.game_arc() != 2:
            return False
        return p.ctx.me.freighter_space < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ExpediteAbility::Evaluate`` @0x4be5ba0: only when
        ``GetFreighterSelections(-1).Item1 == 1`` (recall; ``cmp eax, 1;
        jne`` returns); then ``IntTargetResponse(1)`` at ``FreighterValue``."""

        recall, _, log = p.freighter_selections(-1)
        if recall != 1:
            return _Choice().answer("Expedite")
        return self._freighter_answer(p, 1, f"Expedite | Recall | {log}")


@port(_PA + "FinessePlotAbility")
class FinessePlotAbility(IntrigueAbility):
    """``RiseOfIx.FinessePlotAbility``: the Plot half of Finesse (lose one
    Influence, gain one)."""

    #: The ``InfluenceDelta`` ``<Targets>d__7`` puts on its two infos ("minusone"
    #: ``mov esi, 0xffffffff`` @0x4be9a42, "plusone" ``mov esi, 1``).
    TARGET_INFLUENCE_DELTAS: ClassVar[tuple[int, ...]] = (-1, 1)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4be7780 (``_has_any_influence``)."""

        return _has_any_influence(p)

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``FinessePlotAbility::Evaluate`` @0x4be7b20.

        The "lose" info (``InfluenceDelta == -1``, ``b__13_0``) and the "gain"
        info (``== 1``, ``b__13_1``); either missing returns.
        ``GetBestInfluenceExchange(-1, 1, true, loseFactions, gainFactions)``;
        both tracks of the winning exchange must be among the infos'
        entities (``b__4`` / ``b__5``), and the exchange must reach the
        literal 2.0 (``ucomisd; jb`` returns). The value is a fresh summer of
        the exchange ("Best Influence Exchange Value").
        """

        choice = _Choice()
        infos = list(zip(request.infos, self.TARGET_INFLUENCE_DELTAS, strict=False))
        lose = next((info for info, delta in infos if delta == -1), None)
        gain = next((info for info, delta in infos if delta == 1), None)
        if lose is None or gain is None:
            return choice.answer("Finesse (plot)")
        lose_tracks = [e for e in lose.entities if e.kind is Kind.TRACK]
        gain_tracks = [e for e in gain.entities if e.kind is Kind.TRACK]
        lose_faction, gain_faction, exchange = p.best_influence_exchange(
            -1, 1, [t.ref for t in lose_tracks], [t.ref for t in gain_tracks]
        )
        lose_track = next((t for t in lose_tracks if t.ref == lose_faction), None)
        gain_track = next((t for t in gain_tracks if t.ref == gain_faction), None)
        if lose_track is None or gain_track is None:
            return choice.answer("Finesse (plot)")
        if not exchange >= 2.0:  # ``ucomisd; jb`` @0x4be81d1: NaN returns too
            return choice.answer("Finesse (plot)")
        v = Summer()
        v.add("Best Influence Exchange Value", exchange)
        choice.update_responses(v.sum, ((lose_track.ref,), (gain_track.ref,)))
        return choice.answer(f"Finesse (plot) | {lose_track.ref}->{gain_track.ref}")


@port(_PA + "MachineCulturePlotAbility")
class MachineCulturePlotAbility(IntrigueAbility):
    """``RiseOfIx.MachineCulturePlotAbility``: the Plot half of Machine
    Culture (acquire a Tech tile). ``Cost`` @0x4bf32d0 = NoCost."""

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bf36e0: in the Late arc fewer than 2 Tech
        tiles (``cmp eax, 2; setl``); any other arc: false."""

        if p.game_arc() != 2:
            return False
        return _tech_tile_count(p) < 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MachineCulturePlotAbility::Evaluate`` @0x4bf3730.

        Not with more than 2 Tech tiles (``cmp eax, 2; jg``). With
        ``TechTileToAcquire(0, false)`` found and fewer than 2 tiles: "0 or 1
        Tech Tile". With exactly 2: only in the Reveal turn of the final
        round with a tile found ("2 Tech Tiles"). Then each offered tile
        (``GetTargets(...).OfType<WormTechTilePlayable>()``) is stored at its
        ``AcquireValue(P).Sum`` (strictly better replaces).
        """

        choice = _Choice()
        count = _tech_tile_count(p)
        if count > 2:
            return choice.answer("Machine Culture Acquire Tech")
        tile = p.tech_tile_to_acquire(0, False)
        if tile is None or count == 2:
            if count != 2:
                return choice.answer("Machine Culture Acquire Tech")
            if not _in_player_turn(p, _REVEAL_TURN):
                return choice.answer("Machine Culture Acquire Tech")
            if not p.is_final_round() or tile is None:
                return choice.answer("Machine Culture Acquire Tech")
            path = "2 Tech Tiles"
        else:
            path = "0 or 1 Tech Tile"
        if request.infos:
            for target in request.infos[0].entities:
                if not is_tech_tile(target):
                    continue
                value = p.tech_tile_acquire_value(target).sum
                choice.update_targets(value, (target.ref,))
        return choice.answer(f"Machine Culture Acquire Tech | path: {path}")


def _agent_space_factions(p: Profile) -> list[str]:
    """``QuidProQuoAbility::GetAgentSpaceFactions`` @0x4bf53b0.

    ``BoardSpaces.Where(b__0).Select(Faction).Distinct().ToList()``: the
    Factions (board order) of the Faction spaces holding one of the player's
    Agents (``b__0`` @0x4bf6030: ``Faction != None`` and an Agent child owned
    by the player, ``b__2``).
    """

    board = p.ctx.board
    factions: list[str] = []
    for space_id in board_space_ids(board):
        if p.ctx.seat not in p.ctx.space_occupants(space_id):
            continue
        faction = _space_faction(space_entity(space_id, board))
        if faction is not None and faction not in factions:
            factions.append(faction)
    return factions


@port(_PA + "QuidProQuoAbility")
class QuidProQuoAbility(IntrigueAbility):
    """``RiseOfIx.QuidProQuoAbility``: pay 2 spice for one Influence with each
    Faction whose space holds one of your Agents."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bf5220: ``HasResources.AtLeast(Spice, 2)`` then a
        ``BoolAction`` of ``GetAgentSpaceFactions(player).Any()``."""

        return p.ctx.me.resources.spice >= 2 and bool(_agent_space_factions(p))

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bf57f0: the Early arc (``mov al, 1``), else a
        tail call of ``get_IsSpiceShort``."""

        if p.game_arc() == 0:
            return True
        return p.is_spice_short()

    def _close_opponent(self, p: Profile, faction: str) -> bool:
        """``<Evaluate>b__0`` @0x4bf5c80: the player can gain on the track and
        stands at 3 or more (``cmp eax, 3; jl``), and some opponent stands
        level with it (``b__3`` @0x4bf5ed0) and either has an Agent left or
        ``HasTurnBeforeOpponentNextRound(opponent)``."""

        me = p.ctx.me
        if not _can_gain_faction_influence(me, faction):
            return False
        mine = _influence(me, faction)
        if mine < 3:
            return False
        return any(
            _influence(o, faction) == mine
            and (
                o.agents_available > 0
                or p.has_turn_before_opponent_next_round(o.player_id)
            )
            for o in p.ctx.opponents
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``QuidProQuoAbility::Evaluate`` @0x4bf5840: the literal 1.0 with no
        sub-targets on the first path that holds.

        "Close Opponent": some Faction of ``GetAgentSpaceFactions`` passes
        ``b__0``. "Multiple Factions": in the Reveal turn more than one
        (``cmp eax, 1; jg``) can still be gained on (``b__1``:
        ``CanGainFactionInfluence``). "Single Faction": in the final round one
        can be gained on and ``G(F, +1, -1, false)`` exceeds the literal 3.5
        (``b__2``: ``ucomisd; seta``).
        """

        choice = _Choice()
        me = p.ctx.me
        factions = _agent_space_factions(p)
        path: str | None = None
        if any(self._close_opponent(p, f) for f in factions):
            path = "Close Opponent"
        elif (
            _in_player_turn(p, _REVEAL_TURN)
            and sum(1 for f in factions if _can_gain_faction_influence(me, f)) > 1
        ):
            path = "Multiple Factions"
        elif p.is_final_round() and any(
            _can_gain_faction_influence(me, f)
            and p.gain_influence_value(f, 1, -1, False).sum > 3.5
            for f in factions
        ):
            path = "Single Faction"
        if path is None:
            return choice.answer("Quid Pro Quo")
        choice.update_targets(1.0, None)
        return choice.answer(f"Quid Pro Quo | 1 | path: {path}")


@port(_PA + "SecretForcesAbility")
class SecretForcesAbility(IntrigueAbility):
    """``RiseOfIx.SecretForcesAbility``: with a High Council seat, two troops.
    ``GetUnusualSelections`` @0x4bf85c0 is interface plumbing."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bf84b0: ``HasHighCouncilSeat``."""

        return p.ctx.me.high_council

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bf8820: ``!HighCouncilSeat`` (``xor al, 1``)."""

        return not p.ctx.me.high_council

    def troop_value(self, p: Profile) -> int:
        """``TroopValue`` @0x4bf88c0 (vslot 86): 4 with the seat (``shl eax,
        2``), else 0."""

        return 4 if p.ctx.me.high_council else 0

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SecretForcesAbility::Evaluate`` @0x4bf8960.

        Only on a combat space (``ActiveSpace``, ``IsCombatSpace``), with two
        troops to take (``GetNextTroops(2)``, ``cmp [rax+0x18], 2; jne``: the
        Supply's) that ``GetUnitsToDeploy(troops, 2)`` would deploy at least
        one of (``cmp [rax+0x18], 0; jle``): then the literal 1.0.
        """

        choice = _Choice()
        space = _active_space(p)
        if space is None or not _is_combat_space(space):
            return choice.answer("Secret Forces")
        troops = min(2, p.ctx.me.troops_supply)
        if troops != 2:
            return choice.answer("Secret Forces")
        if p.units_to_deploy(troops, 2) <= 0:
            return choice.answer("Secret Forces")
        choice.update_targets(1.0, None)
        return choice.answer("Secret Forces | 1")


#: ``Strongarm``'s ``ChooseOne`` options (``<Targets>d__6``).
STRONGARM_GARRISON: Final = 0
STRONGARM_DEPLOYED: Final = 1


@port(_PA + "StrongarmAbility")
class StrongarmAbility(IntrigueAbility):
    """``RiseOfIx.StrongarmAbility``: lose a troop for one Influence with the
    Faction of the space your Agent was sent to. ``WillClearUndo`` @0x4bfa880
    is the engine's."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bfa140: ``HasUnitsDeployed<WormTroop>.Any`` ``Or``
        ``HasUnitsGarrisoned<WormTroop>.Any``, with a ``BoolAction`` that the
        Agent's space (``ActiveSpace.FirstOrDefault()``) has a Faction
        (``setne``). Bloodlines Commanders count as troops (D1)."""

        if p.conflict_troop_count() <= 0 and p.garrison_troop_count() <= 0:
            return False
        space = _active_space(p)
        return space is not None and _space_faction(space) is not None

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``StrongarmAbility::Evaluate`` @0x4bfa490.

        Needs the Agent's space to have a Faction whose ``G(F, +1, -1,
        false)`` reaches the literal 3.5 (``ucomisd; jb`` returns). With an
        ``EstimatedConflictRank(0)`` the garrison troop is lost unless the
        garrison has none; without one a deployed troop is lost when there is
        one. The literal 1.0 with ``IntTargetResponse`` (0 garrison, 1
        deployed).
        """

        choice = _Choice()
        space = _active_space(p)
        if space is None:
            return choice.answer("Strongarm")
        faction = _space_faction(space)
        if faction is None:
            return choice.answer("Strongarm")
        # ``ucomisd G, 3.5; jb`` @0x4bfa5f3: NaN returns too.
        if not p.gain_influence_value(faction, 1, -1, False).sum >= 3.5:
            return choice.answer("Strongarm")
        if p.estimated_conflict_rank(0) is not None:
            deployed = p.garrison_troop_count() <= 0
        else:
            deployed = p.conflict_troop_count() > 0
        option = STRONGARM_DEPLOYED if deployed else STRONGARM_GARRISON
        choice.update_responses(1.0, ((option,),))
        where = "Deployed" if deployed else "Garrison"
        return choice.answer(f"Strongarm | 1 | Losing troop from {where}")


# ---------------------------------------------------------------------------
# Endgame intrigues
# ---------------------------------------------------------------------------


class _EndgameIxAbility(IntrigueAbility):
    """The three Rise of Ix Endgame classes: ``.ctor`` stores timing 4
    (``mov esi, 4``); ``Evaluate`` is the ungated literal 100.0 ("... | always
    play", no sub-targets)."""

    ability_timing: ClassVar[int] = ENDGAME_TIMING
    #: The log line of ``Evaluate``.
    LOG: ClassVar[str] = ""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``Evaluate`` (@0x4beca10, @0x4bf1f90, @0x4bfe1e0): 100.0
        (``f64=100.0``) with no sub-targets."""

        choice = _Choice()
        choice.update_targets(100.0, None)
        return choice.answer(self.LOG)


@port(_PA + "GrandConspiracyAbility")
class GrandConspiracyAbility(_EndgameIxAbility):
    """``RiseOfIx.GrandConspiracyAbility`` (Endgame). ``Cost`` @0x4bec120 =
    NoCost; ``IsEndgamePlayable`` @0x4bec6f0 (``CountTotalPoints > 0``) and
    ``GetConditionalEndgameVP`` @0x4bec710 have no AI caller."""

    LOG: ClassVar[str] = "Grand Conspiracy | always play"

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bec820: the Early arc is bad, the Mid arc is
        not. In the Late arc it is not with a High Council seat, nor with no
        dreadnought in the Supply (``Supply.children.OfType<WormDreadnought>
        ().Any()``); else bad without a Spice Must Flow among
        ``AllImperiumCards`` (``Any(IsTheSpiceMustFlowImperium)``, ``xor
        r14b, 1``)."""

        arc = p.game_arc()
        if arc == 0:
            return True
        if arc != 2:
            return False
        me = p.ctx.me
        if me.high_council:
            return False
        if me.dreadnoughts_supply <= 0:
            return False
        return _count_the_spice_must_flow(p) == 0

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``GrandConspiracyAbility::ValueInPileForOtherPlay`` @0x4becae0.

        A fresh ``DefaultValueSummer`` (not the base tag synergy): in the
        Deck pile (``pile.Is(EntityNames.Deck)``) a Spice Must Flow card
        (``IsTheSpiceMustFlowImperium`` @0x482f1b0) multiplies it by
        ``GrandConspiracyTSMFMod`` ("Grand Conspiracy TSMF"). The summer has
        no term to scale, so its sum stays 0 (app quirk kept).
        """

        s = Summer()
        if pile is not Pile.DECK:
            return s
        if card.kind is Kind.CARD and card.short in _TSMF_ARCHETYPES:
            s.multiply("Grand Conspiracy TSMF", p.C.GrandConspiracyTSMFMod)
        return s


@port(_PA + "MachineCultureEndgameAbility")
class MachineCultureEndgameAbility(_EndgameIxAbility):
    """``RiseOfIx.MachineCultureEndgameAbility``: the Endgame half of Machine
    Culture. ``IsEndgamePlayable`` @0x4bf1e60 = false and
    ``GetConditionalEndgameVP`` @0x4bf1e70 have no AI caller."""

    LOG: ClassVar[str] = "Machine Culture | always play"

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4bf1ac0: a ``BoolAction`` of the Playmat's
        ``EndgameStarted`` (false outside a ``WormMatch``)."""

        return _endgame_started(p)

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``ValueInPileForOtherPlay`` @0x4bf2060: ``DefaultValueSummer``
        (empty; not the base tag synergy)."""

        return Summer()


@port(_PA + "WarChestEndgameAbility")
class WarChestEndgameAbility(_EndgameIxAbility):
    """``RiseOfIx.WarChestEndgameAbility``: the Endgame half of War Chest.
    ``Cost`` @0x4bfdd80 = NoCost; ``IsEndgamePlayable`` @0x4bfe060 = false and
    ``GetConditionalEndgameVP`` @0x4bfe070 have no AI caller."""

    LOG: ClassVar[str] = "War Chest | always play"

    def is_bad_intrigue(self, p: Profile) -> bool:
        """``IsBadIntrigue`` @0x4bfe190: false in the Late arc
        (``GetGameArc() == 2``), else a tail call of ``get_IsSolariShort``."""

        if p.game_arc() == 2:
            return False
        return p.is_solari_short()

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        """``ValueInPileForOtherPlay`` @0x4bfe2b0: ``DefaultValueSummer``
        (empty; not the base tag synergy)."""

        return Summer()


# ---------------------------------------------------------------------------
# GetBestOption readers
# ---------------------------------------------------------------------------


@port(_PA + "GlimpseThePathAbility")
class GlimpseThePathAbility(IntrigueAbility):
    """``RiseOfIx.GlimpseThePathAbility``: pay 1 spice, gain 1 water and draw
    a card."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4beb130: at least 1 spice."""

        return p.ctx.me.resources.spice >= 1

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``GlimpseThePathAbility::Evaluate``: a path, then the play.

        "Before Agent/Reveal": at the turn start (``IsInPlayerTurn(0)``) with
        an Agent left, when the spice differs from ``GetBestOption``'s card
        plus space ``SpiceCost`` (a lifted nullable sum: no option is
        different too). "During Reveal" (``IsInPlayerTurn(2)``): at the climax
        or with ``GetBuyGains(PossiblePersuasionGain()) >= 2.5``. With no
        path, "4+ Intrigue Cards". The play is ``UpdateSelectionTargets(sum,
        null)`` of "Play early" 100.0, ``GetSpiceValue(-1)`` ("Pay 1 Spice"),
        ``GetWaterValue(1)``, ``CardDrawValue`` and
        ``GetBuyGains(PossiblePersuasionGain())`` ("Buy Gains Bonus").
        """

        from dune_imperium.agents.app_ai.abilities.original_intrigue import (
            best_option,
        )

        choice = _Choice()
        me = p.ctx.me
        path: str | None = None
        if _in_player_turn(p, _UNDETERMINED) and me.agents_available > 0:
            card, space, _value = best_option(p)
            if card is None or space is None:
                path = "Before Agent/Reveal"
            else:
                cost = card.int_attr("SpiceCost", 0) + space.int_attr("SpiceCost", 0)
                if me.resources.spice != cost:
                    path = "Before Agent/Reveal"
        elif _in_player_turn(p, _REVEAL_TURN) and (
            p.is_climax() or p.buy_gains(p.possible_persuasion_gain()) >= 2.5
        ):
            path = "During Reveal"
        if path is None and _intrigue_hand_count(p) >= 4:
            path = "4+ Intrigue Cards"
        if path is None:
            return choice.answer("Glimpse The Path")
        v = Summer()
        v.add("Play early", 100.0)
        v.add("Pay 1 Spice", p.spice_value(-1))
        v.add("Water", p.water_value(1))
        v.add("Card Draw", p.card_draw_value())
        v.add("Buy Gains Bonus", p.buy_gains(p.possible_persuasion_gain()))
        choice.update_targets(v.sum, None)
        return choice.answer(f"Glimpse The Path | {v.sum} | path: {path}")


@port(_PA + "IxianProbeAbility")
class IxianProbeAbility(IntrigueAbility):
    """``RiseOfIx.IxianProbeAbility``: discard two cards, draw two."""

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4befdd0: two or more Imperium cards in hand."""

        return len(p.ctx.me.hand) >= 2

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``IxianProbeAbility::Evaluate``: at the climax; with no Agent left,
        a hand of 4 or more and ``5.0 >= GetBuyValue()``; or with an Agent
        left, ``GetBestOption`` worth at most 4.0. The play is the summer of
        "Discard 2" (2 x ``DiscardValue``), "Draw 2" (2 x ``CardDrawValue``)
        and "2 Buy Gains Bonus" (2 x ``GetBuyGains(PossiblePersuasionGain())``),
        answered with the first two of ``GetDiscardOrder(P, cards, false)``;
        not exactly two, no play."""

        from dune_imperium.agents.app_ai.abilities.original_intrigue import (
            best_option,
        )

        choice = _Choice()
        me = p.ctx.me
        if p.is_climax():
            path = "Climax"
        elif me.agents_available <= 0:
            if not (len(me.hand) >= 4 and 5.0 >= p.buy_value()):
                return choice.answer("Ixian Probe")
            path = "No Agents Remaining"
        else:
            if not 4.0 >= best_option(p)[2]:
                return choice.answer("Ixian Probe")
            path = "Agents Remaining"
        v = Summer()
        v.add("Discard 2", 2 * p.discard_value())
        v.add("Draw 2", 2 * p.card_draw_value())
        v.add("2 Buy Gains Bonus", 2 * p.buy_gains(p.possible_persuasion_gain()))
        order = p.discard_order(_targets(request, 0, Kind.CARD), False)[:2]
        if len(order) != 2:
            return choice.answer("Ixian Probe")
        choice.update_targets(v.sum, tuple(c.ref for c in order))
        return choice.answer(f"Ixian Probe | {v.sum} | path: {path}")
