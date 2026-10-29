"""The original game's leader abilities (``LeaderArchetypes.BaseSet``).

Ports of the 18 ability classes of the eight base-game leaders (Paul
Atreides, Duke Leto, Glossu Rabban, Baron Harkonnen, Count Ilban Richese,
Helena Richese, Earl Memnon Thorvald, Countess Ariana Thorvald), read from
the P3d decompilation (assets ``ghidra/p3d-types/<class>.c``) and confirmed
in the annotated disassembly (``dump/asm/worm-canis.dll/<class>.asm``);
``docs/app-ai-plan.md`` §12. Paul's Discipline (``DisciplineAbility``) and
the Signet base classes are in ``abilities/leaders.py``.

App class chains (``dump/worm-canis.dll.cs``):

- ``ActivatedAbilities.SignetAbility`` <- ``BaseSet.BrutalityAbility``,
  ``HiddenReservoirAbility``, ``ManipulateAbility``,
  ``ManufacturingAbility``, ``PrudentDiplomacyAbility``, ``SchemeAbility``,
  ``SpiceHoardAbility``;
- ``ActivatedAbilities.DeferredAbility`` <-
  ``BaseSet.ConnectionsInfluenceAbility``;
- ``ActivatedAbilities.DrawAbility`` <- ``ActivatedAbilities.LeaderDrawAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <- ``BaseSet.PrescienceAbility``,
  ``LandsraadPopularityAbility``, ``ArrakisFiefdomAbility``,
  ``MasterstrokeAbility1`` and ``2``, ``RuthlessNegotiatorAbility``,
  ``ConnectionsAbility``, ``SpiceAddictAbility1`` and ``2``.

How a leader ability reaches the AI is as in ``abilities/leaders.py``: a
Signet's ``value_for_player`` is merged into a placement of a card with
signet icons; ``evaluate`` answers the prompt of a deferred ability. Only
five of these classes have an ``Evaluate``; the triggered abilities have no
AI member (the engine runs them) and are bare ports so that the leader's
abilities all resolve.

Request / answer encoding (``infos[i]`` is the app's target information
``i``; the answers follow ``abilities/intrigue.py``'s ``_Choice``):

- Prudent Diplomacy, Connections' Influence: ``infos[0]`` the faction TRACKs
  the prompt offers (``MakeGainAnyFactionInfluenceTargeting`` / the tracks an
  opponent leads on); the answer is ``((track,),)``.
- Scheme: no target information; the answer ``((),)`` (one empty entity list,
  ``UpdateSelectionTargets(v, src, Array.Empty)``) plays it.
- Manipulate: ``infos[0]`` the Imperium Row CARDs it may set aside; the answer
  is ``((card,),)``, or ``((),)`` for the 0.5 fallback with no target.
- Masterstroke (``MasterstrokeAbility1``, the Baron's secret factions):
  ``infos[0]`` the four faction TRACKs; the answer is two of them in the
  shuffled order the app takes, ``((track, track),)``.

Addresses are build dad97e2021144d45b5b4f022e07bd3b3.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Final

from dune_imperium.agents.app_ai.abilities.base import (
    Answer,
    Request,
    SelectionMode,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    DeferredAbility,
    DrawAbility,
    TriggeredAbility,
    _runs_unless_threshold,
    collect_first,
)
from dune_imperium.agents.app_ai.abilities.intrigue import (
    _can_gain_faction_influence,
    _Choice,
    _highest_opponent_rank,
    _influence,
    _targets,
)
from dune_imperium.agents.app_ai.abilities.leaders import SignetAbility
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_AA: Final = "worm.canis.abilities.ActivatedAbilities."
_TA: Final = "worm.canis.abilities.TriggeredAbilities.BaseSet."

#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``).
_ANY_FACTION: Final = "none"

# ---------------------------------------------------------------------------
# Triggered abilities: no AI member (``TriggeredAbility`` is never evaluated)
# ---------------------------------------------------------------------------


@port(_TA + "PrescienceAbility")
class PrescienceAbility(TriggeredAbility):
    """``BaseSet.PrescienceAbility`` (Paul: look at an opponent's cards in
    combat). ``get_ShouldExhaust`` @0x4b5c3b0 = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "LandsraadPopularityAbility")
class LandsraadPopularityAbility(TriggeredAbility):
    """``BaseSet.LandsraadPopularityAbility`` (Duke Leto: a free Agent at the
    Landsraad). ``get_ShouldExhaust`` @0x4b592e0 = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "ArrakisFiefdomAbility")
class ArrakisFiefdomAbility(TriggeredAbility):
    """``BaseSet.ArrakisFiefdomAbility`` (Glossu Rabban: spice and Solari
    from his Maker and Landsraad visits); no AI hook."""


@port(_TA + "MasterstrokeAbility2")
class MasterstrokeAbility2(TriggeredAbility):
    """``BaseSet.MasterstrokeAbility2`` (the Baron's reveal of his secret
    Factions); no AI hook."""


@port(_TA + "RuthlessNegotiatorAbility")
class RuthlessNegotiatorAbility(TriggeredAbility):
    """``BaseSet.RuthlessNegotiatorAbility`` (Count Ilban: Solari at the
    Pentagon spaces). ``get_ShouldExhaust`` @0x4b5cdc0 = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "ConnectionsAbility")
class ConnectionsAbility(TriggeredAbility):
    """``BaseSet.ConnectionsAbility`` (Earl Memnon: the High Council grants
    ``ConnectionsInfluenceAbility``). ``get_ShouldExhaust`` @0x4b57130 =
    false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "SpiceAddictAbility1")
class SpiceAddictAbility1(TriggeredAbility):
    """``BaseSet.SpiceAddictAbility1`` (Countess Ariana: spice from the
    Maker spaces). ``get_ShouldExhaust`` @0x4b5d600 = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "SpiceAddictAbility2")
class SpiceAddictAbility2(TriggeredAbility):
    """``BaseSet.SpiceAddictAbility2`` (Countess Ariana: her second Spice
    Addict trigger). ``get_ShouldExhaust`` @0x4b5e280 = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "MasterstrokeAbility1")
class MasterstrokeAbility1(TriggeredAbility):
    """``BaseSet.MasterstrokeAbility1`` (the Baron's setup: two Factions
    chosen in secret). ``Cost @0x4b59e90`` = NoCost."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MasterstrokeAbility1::Evaluate`` @0x4b59fe0.

        ``GetTargets(owner, 2)`` ``.OfType<WormFactionTrack>().ToList()`` is
        shuffled (``ListUtil.Shuffle``, 0x4b5a1f7) and its first two stored at
        the literal 1.0 (``f64=1.0``). The Solo-Hagal branch
        (``HagalInfluenceEvaluate``) never holds.
        """

        choice = _Choice()
        tracks = list(_targets(request, 0, Kind.TRACK))
        p.rng.shuffle(tracks)
        choice.update_targets(1.0, tuple(t.ref for t in tracks[:2]))
        return choice.answer("Masterstroke | pick two factions")


# ---------------------------------------------------------------------------
# Signets with a plain ValueForPlayer (Brutality, Manufacturing, Spice Hoard,
# Hidden Reservoir)
# ---------------------------------------------------------------------------


@port(_AA + "BaseSet.BrutalityAbility")
class BrutalityAbility(SignetAbility):
    """``ActivatedAbilities.BaseSet.BrutalityAbility`` (Glossu Rabban's
    signet: a troop, two with an Alliance)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BrutalityAbility::ValueForPlayer`` @0x4e33ba0: ``GetTroopValue(1 +
        InAlliance(None), false)`` ("Brutality Troops"; ``movzx esi, al; inc
        esi``)."""

        s = Summer()
        troops = 1 + (1 if p.ctx.me.alliance_faction_ids else 0)
        s.add("Brutality Troops", p.troop_value(troops, False))
        return s


class _SignetRunsAtOnce(SignetAbility):
    """The three one-resource signets: ``get_AlwaysRunImmediately`` and
    ``get_RunCopiesTogether`` both return true (``mov al, 1``)."""

    always_run_immediately: ClassVar[bool] = True


@port(_AA + "BaseSet.ManufacturingAbility")
class ManufacturingAbility(_SignetRunsAtOnce):
    """``BaseSet.ManufacturingAbility`` (Count Ilban's signet: a Solari);
    ``get_AlwaysRunImmediately`` @0x4e4be10."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ManufacturingAbility::ValueForPlayer`` @0x4e4bf10:
        ``GetSolariValue(1)``."""

        s = Summer()
        s.add("Manufacturing Solari", p.solari_value(1))
        return s


@port(_AA + "BaseSet.SpiceHoardAbility")
class SpiceHoardAbility(_SignetRunsAtOnce):
    """``BaseSet.SpiceHoardAbility`` (Earl Memnon's signet: a spice);
    ``get_AlwaysRunImmediately`` @0x4e5c780."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceHoardAbility::ValueForPlayer`` @0x4e5c880:
        ``GetSpiceValue(1)``."""

        s = Summer()
        s.add("Spice Hoard Spice", p.spice_value(1))
        return s


@port(_AA + "BaseSet.HiddenReservoirAbility")
class HiddenReservoirAbility(_SignetRunsAtOnce):
    """``BaseSet.HiddenReservoirAbility`` (Countess Ariana's signet: a
    water); ``get_AlwaysRunImmediately`` @0x4e46d80."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HiddenReservoirAbility::ValueForPlayer`` @0x4e46e80:
        ``GetWaterValue(1)``."""

        s = Summer()
        s.add("Hidden Reservoir Water", p.water_value(1))
        return s


# ---------------------------------------------------------------------------
# Prudent Diplomacy, Scheme, Manipulate
# ---------------------------------------------------------------------------


@port(_AA + "BaseSet.PrudentDiplomacyAbility")
class PrudentDiplomacyAbility(SignetAbility):
    """``BaseSet.PrudentDiplomacyAbility`` (Duke Leto's signet: pay a spice
    for one Influence where an opponent leads)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``PrudentDiplomacyAbility::SelectionMode`` @0x4e51cd0: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4e51ae0: ``SignetAbility::Cost`` then ``Spice >= 1``
        then a ``BoolAction`` that ``GetFactionTrackTargets(player,
        OpponentHasMoreFilter)`` is not empty (``OpponentHasMoreFilter``
        @0x4e519c0: ``CurrentRank(player) < HighestOpponentRank``)."""

        me = p.ctx.me
        return (
            super().meets_cost(p)
            and me.resources.spice >= 1
            and any(
                _can_gain_faction_influence(me, f)
                and _influence(me, f) < _highest_opponent_rank(p, f)
                for f in FACTIONS
            )
        )

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``PrudentDiplomacyAbility::ValueForPlayer`` @0x4e51de0.

        Without spice nothing. A space in ``with_entities`` (``ListUtil.
        CollectFirst``) that leaves no spice for the signet after its own
        cost adds 0 ("Prudent Diplomacy Lack of Spice for Space"). Otherwise
        ``G(None, +1, -1, false)``, added as "Prudent Diplomacy Influence"
        when it reaches ``DukeLetoAtreidesPrudentDiplomacyInfluenceValueThreshold``
        (``ucomisd; jae``) or in the Early arc (``GetGameArc() > 0`` returns),
        then ``-GetSpiceValue(1)`` ("Prudent Diplomacy Spice Cost").
        """

        s = Summer()
        if p.ctx.me.resources.spice <= 0:
            return s
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 1
        ):
            s.add("Prudent Diplomacy Lack of Spice for Space", 0.0)
            return s
        g = p.gain_influence_value(_ANY_FACTION, 1, -1, False)
        if (
            not g.sum >= p.C.DukeLetoAtreidesPrudentDiplomacyInfluenceValueThreshold
            and p.game_arc() > 0
        ):
            return s
        s.add("Prudent Diplomacy Influence", g.sum)
        s.add("Prudent Diplomacy Spice Cost", -p.spice_value(1))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``PrudentDiplomacyAbility::Evaluate`` @0x4e52110.

        Each offered track is priced ``G(track, +1, -1, false)``; one worth
        the same threshold, or any in the Early arc, is stored with its sum
        (strictly better replaces). The Solo-Hagal branch never holds."""

        choice = _Choice()
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            if (
                g.sum >= p.C.DukeLetoAtreidesPrudentDiplomacyInfluenceValueThreshold
                or p.game_arc() == 0
            ):
                choice.update_targets(g.sum, (track.ref,))
        return choice.answer("Prudent Diplomacy")


@port(_AA + "BaseSet.SchemeAbility")
class SchemeAbility(SignetAbility):
    """``BaseSet.SchemeAbility`` (the Baron's signet: pay a Solari for an
    Intrigue card)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SchemeAbility::SelectionMode`` @0x4e55d60: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4e55cb0: ``SignetAbility::Cost`` then ``Solari >= 1``."""

        return super().meets_cost(p) and p.ctx.me.resources.solari >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SchemeAbility::ValueForPlayer`` @0x4e55e70: with any Solari,
        ``get_IntrigueValue`` then ``GetSolariValue(-1)``."""

        s = Summer()
        if p.ctx.me.resources.solari > 0:
            s.add("Scheme Intrigue", p.intrigue_value())
            s.add("Scheme Solari Cost", p.solari_value(-1))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SchemeAbility::Evaluate`` @0x4e56010.

        With exactly 8 Solari (``cmp eax, 8``) and no Swordmaster the Solari
        are kept; with more than two Intrigue cards in hand it is not played.
        Otherwise the owner's ``DeferValue`` (default 1, ``mov edx, 1``) as a
        value with an empty (non-null) target array."""

        choice = _Choice()
        me = p.ctx.me
        if me.resources.solari == 8 and not me.swordmaster_acquired:
            return choice.answer("Scheme")
        if len(p.ctx.intrigue_cards) > 2:
            return choice.answer("Scheme")
        choice.update_targets(float(self.owner.int_attr("DeferValue", 1)), ())
        return choice.answer("Scheme")


@port(_AA + "BaseSet.ManipulateAbility")
class ManipulateAbility(SignetAbility):
    """``BaseSet.ManipulateAbility`` (Helena Richese's signet: set aside an
    Imperium Row card; +1 Persuasion in the Reveal turn)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ManipulateAbility::SelectionMode`` @0x4e4a460: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ManipulateAbility::ValueForPlayer`` @0x4e4a590:
        ``GetPersuasionValue(1) * 1.5`` ("Manipulate Persuasion", ``f64=1.5``),
        and with two or more Agents left (``RemainingAgents.Count``)
        ``count * 1.5``."""

        s = Summer()
        s.add("Manipulate Persuasion", p.persuasion_value(1) * 1.5)
        agents = p.ctx.me.agents_available
        if agents >= 2:
            s.add("Manipulate Agents", float(agents) * 1.5)
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ManipulateAbility::Evaluate`` @0x4e4a760.

        Each Row card (``infos[0]``) whose ``PersuasionCost`` is at most
        ``PossiblePersuasion + 1`` is stored at its ``AcquireValue`` (strictly
        better replaces). With nothing stored above 0 (``0.0 <= value``,
        0x4e4ace3) the literal 0.5 is stored with an empty target array."""

        choice = _Choice()
        for card in _targets(request, 0, Kind.CARD):
            value = p.acquire_value(card)
            if card.int_attr("PersuasionCost") <= p.possible_persuasion() + 1:
                choice.update_targets(value.sum, (card.ref,))
        if not 0.0 < choice.value:  # ucomisd 0.0, value; jb -> return
            choice.update_targets(0.5, ())
        return choice.answer("Manipulate")


# ---------------------------------------------------------------------------
# Connections' Influence and Leader Draw
# ---------------------------------------------------------------------------


@port(_AA + "BaseSet.ConnectionsInfluenceAbility")
class ConnectionsInfluenceAbility(DeferredAbility):
    """``BaseSet.ConnectionsInfluenceAbility`` (Earl Memnon: the one Influence
    his High Council visit grants)."""

    contextually_deferred: ClassVar[bool] = True  # get_ContextuallyDeferred @0x4e35460

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ConnectionsInfluenceAbility::SelectionMode`` @0x4e35400:
        Explicit (3)."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CanRunImmediately`` @0x4e35410: ``CurrentPlayer == null ||
        IsInPlayerTurn(Reveal) || !DeferredThresholdReached()``."""

        return _runs_unless_threshold(p)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost`` @0x4e35510: ``HasHighCouncilSeat``, then (``CostAction::
        Then``) ``CanGainInfluence`` and ``HasCustomAbility`` (the grant the
        leader's trigger made, the engine's)."""

        me = p.ctx.me
        return me.high_council and any(
            _can_gain_faction_influence(me, f) for f in FACTIONS
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ConnectionsInfluenceAbility::Evaluate`` @0x4e356f0.

        Each offered track is priced ``G(track, +1, -1, false)`` and stored at
        its sum when that is above 0.0 (``cmpnlesd``; the constant at
        0x520cdf8 is 0.0), else at the literal 0.5 (strictly better
        replaces)."""

        choice = _Choice()
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            choice.update_targets(g.sum if g.sum > 0.0 else 0.5, (track.ref,))
        return choice.answer("Connections Influence")


@port(_AA + "LeaderDrawAbility")
class LeaderDrawAbility(DrawAbility):
    """``ActivatedAbilities.LeaderDrawAbility`` (Count Ilban's and Countess
    Ariana's draw): ``DrawAbility`` with ``HideInvalidDeferred`` set
    (``.ctor`` @0x4ce1fa0) and no AI override; ``IsUnexhausted @0x4ce22a0`` =
    true. ``Cost @0x4ce2110`` adds the player's ``LeaderDrawAbility``
    attribute (the engine's grant) to ``DrawAbility``'s ``HasDrawableCard``."""
