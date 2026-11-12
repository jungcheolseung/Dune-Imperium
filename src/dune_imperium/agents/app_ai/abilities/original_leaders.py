"""The original game's leader abilities.

Ports of the 18 ability classes of the eight base-game leaders (Paul Atreides, Duke
Leto, Glossu Rabban, Baron Harkonnen, Count Ilban Richese, Helena Richese, Earl Memnon
Thorvald, Countess Ariana Thorvald); each follows the app's AI for that class, and the
detailed notes are kept privately (``docs/app-ai-plan.md`` §12). Paul's Discipline
(``DisciplineAbility``) and the Signet base classes are in ``abilities/leaders.py``.

App class chains:

- ``ActivatedAbilities.SignetAbility`` <- ``BrutalityAbility``,
  ``HiddenReservoirAbility``, ``ManipulateAbility``,
  ``ManufacturingAbility``, ``PrudentDiplomacyAbility``, ``SchemeAbility``,
  ``SpiceHoardAbility``;
- ``ActivatedAbilities.DeferredAbility`` <-
  ``ConnectionsInfluenceAbility``;
- ``ActivatedAbilities.DrawAbility`` <- ``ActivatedAbilities.LeaderDrawAbility``;
- ``TriggeredAbilities.TriggeredAbility`` <- ``PrescienceAbility``,
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

_AA: Final = "ability.activated."
_TA: Final = "ability.triggered.original."

#: ``Factions.None`` of ``GetGainInfluenceValue`` (``influence.NO_FACTION``).
_ANY_FACTION: Final = "none"

# ---------------------------------------------------------------------------
# Triggered abilities: no AI member (``TriggeredAbility`` is never evaluated)
# ---------------------------------------------------------------------------


@port(_TA + "prescience")
class PrescienceAbility(TriggeredAbility):
    """``PrescienceAbility`` (Paul: look at an opponent's cards in combat).
    ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "landsraad_popularity")
class LandsraadPopularityAbility(TriggeredAbility):
    """``LandsraadPopularityAbility`` (Duke Leto: a free Agent at the Landsraad).
    ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "arrakis_fiefdom")
class ArrakisFiefdomAbility(TriggeredAbility):
    """``ArrakisFiefdomAbility`` (Glossu Rabban: spice and Solari from his Maker and
    Landsraad visits); no AI hook."""


@port(_TA + "masterstroke_ability2")
class MasterstrokeAbility2(TriggeredAbility):
    """``MasterstrokeAbility2`` (the Baron's reveal of his secret Factions); no AI
    hook."""


@port(_TA + "ruthless_negotiator")
class RuthlessNegotiatorAbility(TriggeredAbility):
    """``RuthlessNegotiatorAbility`` (Count Ilban: Solari at the Pentagon spaces).
    ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "connections")
class ConnectionsAbility(TriggeredAbility):
    """``ConnectionsAbility`` (Earl Memnon: the High Council grants
    ``ConnectionsInfluenceAbility``). ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "spice_addict_ability1")
class SpiceAddictAbility1(TriggeredAbility):
    """``SpiceAddictAbility1`` (Countess Ariana: spice from the Maker spaces).
    ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "spice_addict_ability2")
class SpiceAddictAbility2(TriggeredAbility):
    """``SpiceAddictAbility2`` (Countess Ariana: her second Spice Addict trigger).
    ``ShouldExhaust`` = false; no AI hook."""

    should_exhaust: ClassVar[bool] = False


@port(_TA + "masterstroke_ability1")
class MasterstrokeAbility1(TriggeredAbility):
    """``MasterstrokeAbility1`` (the Baron's setup: two Factions chosen in secret).
    ``Cost`` = NoCost."""

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``MasterstrokeAbility1.Evaluate``.

        ``GetTargets(owner, 2)`` ``.OfType<FactionTrack>().ToList()`` is
        shuffled (``ListUtil.Shuffle``) and its first two stored at
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


@port(_AA + "original.brutality")
class BrutalityAbility(SignetAbility):
    """``ability.activated.original.brutality`` (Glossu Rabban's
    signet: a troop, two with an Alliance)."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``BrutalityAbility.ValueForPlayer``: ``GetTroopValue(1 + InAlliance(None),
        false)`` ("Brutality Troops")."""

        s = Summer()
        troops = 1 + (1 if p.ctx.me.alliance_faction_ids else 0)
        s.add("Brutality Troops", p.troop_value(troops, False))
        return s


class _SignetRunsAtOnce(SignetAbility):
    """The three one-resource signets: ``AlwaysRunImmediately`` and
    ``RunCopiesTogether`` both return true."""

    always_run_immediately: ClassVar[bool] = True


@port(_AA + "original.manufacturing")
class ManufacturingAbility(_SignetRunsAtOnce):
    """``ManufacturingAbility`` (Count Ilban's signet: a Solari);
    ``AlwaysRunImmediately``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ManufacturingAbility.ValueForPlayer``:
        ``GetSolariValue(1)``."""

        s = Summer()
        s.add("Manufacturing Solari", p.solari_value(1))
        return s


@port(_AA + "original.spice_hoard")
class SpiceHoardAbility(_SignetRunsAtOnce):
    """``SpiceHoardAbility`` (Earl Memnon's signet: a spice);
    ``AlwaysRunImmediately``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SpiceHoardAbility.ValueForPlayer``:
        ``GetSpiceValue(1)``."""

        s = Summer()
        s.add("Spice Hoard Spice", p.spice_value(1))
        return s


@port(_AA + "original.hidden_reservoir")
class HiddenReservoirAbility(_SignetRunsAtOnce):
    """``HiddenReservoirAbility`` (Countess Ariana's signet: a water);
    ``AlwaysRunImmediately``."""

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``HiddenReservoirAbility.ValueForPlayer``:
        ``GetWaterValue(1)``."""

        s = Summer()
        s.add("Hidden Reservoir Water", p.water_value(1))
        return s


# ---------------------------------------------------------------------------
# Prudent Diplomacy, Scheme, Manipulate
# ---------------------------------------------------------------------------


@port(_AA + "original.prudent_diplomacy")
class PrudentDiplomacyAbility(SignetAbility):
    """``PrudentDiplomacyAbility`` (Duke Leto's signet: pay a spice for one Influence
    where an opponent leads)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``PrudentDiplomacyAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``SignetAbility.Cost`` then ``Spice >= 1``
        then a ``BoolAction`` that ``GetFactionTrackTargets(player,
        OpponentHasMoreFilter)`` is not empty (``OpponentHasMoreFilter``
: ``CurrentRank(player) < HighestOpponentRank``)."""

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
        """``PrudentDiplomacyAbility.ValueForPlayer``.

        Without spice nothing. A space in ``with_entities`` (``ListUtil. CollectFirst``)
        that leaves no spice for the signet after its own cost adds 0 ("Prudent
        Diplomacy Lack of Spice for Space"). Otherwise ``G(None, +1, -1, false)``, added
        as "Prudent Diplomacy Influence" when it reaches
        ``DukeLetoAtreidesPrudentDiplomacyInfluenceValueThreshold`` or in the Early arc
        (``GetGameArc() > 0`` returns), then ``-GetSpiceValue(1)`` ("Prudent Diplomacy
        Spice Cost").
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
        """``PrudentDiplomacyAbility.Evaluate``.

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


@port(_AA + "original.scheme")
class SchemeAbility(SignetAbility):
    """``SchemeAbility`` (the Baron's signet: pay a Solari for an Intrigue card)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``SchemeAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``SignetAbility.Cost`` then ``Solari >= 1``."""

        return super().meets_cost(p) and p.ctx.me.resources.solari >= 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``SchemeAbility.ValueForPlayer``: with any Solari,
        ``IntrigueValue`` then ``GetSolariValue(-1)``."""

        s = Summer()
        if p.ctx.me.resources.solari > 0:
            s.add("Scheme Intrigue", p.intrigue_value())
            s.add("Scheme Solari Cost", p.solari_value(-1))
        return s

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``SchemeAbility.Evaluate``.

        With exactly 8 Solari and no Swordmaster the Solari are kept; with more than two
        Intrigue cards in hand it is not played. Otherwise the owner's ``DeferValue``
        (default 1) as a value with an empty (non-null) target array."""

        choice = _Choice()
        me = p.ctx.me
        if me.resources.solari == 8 and not me.swordmaster_acquired:
            return choice.answer("Scheme")
        if len(p.ctx.intrigue_cards) > 2:
            return choice.answer("Scheme")
        choice.update_targets(float(self.owner.int_attr("DeferValue", 1)), ())
        return choice.answer("Scheme")


@port(_AA + "original.manipulate")
class ManipulateAbility(SignetAbility):
    """``ManipulateAbility`` (Helena Richese's signet: set aside an Imperium Row card;
    +1 Persuasion in the Reveal turn)."""

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ManipulateAbility.SelectionMode``: Explicit (3)."""

        return SelectionMode.EXPLICIT

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ManipulateAbility.ValueForPlayer``:
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
        """``ManipulateAbility.Evaluate``.

        Each Row card (``infos[0]``) whose ``PersuasionCost`` is at most
        ``PossiblePersuasion + 1`` is stored at its ``AcquireValue`` (strictly better
        replaces). With nothing stored above 0 (``0.0 <= value``) the literal 0.5 is
        stored with an empty target array."""

        choice = _Choice()
        for card in _targets(request, 0, Kind.CARD):
            value = p.acquire_value(card)
            if card.int_attr("PersuasionCost") <= p.possible_persuasion() + 1:
                choice.update_targets(value.sum, (card.ref,))
        if not 0.0 < choice.value:  # -> return
            choice.update_targets(0.5, ())
        return choice.answer("Manipulate")


# ---------------------------------------------------------------------------
# Connections' Influence and Leader Draw
# ---------------------------------------------------------------------------


@port(_AA + "original.connections_influence")
class ConnectionsInfluenceAbility(DeferredAbility):
    """``ConnectionsInfluenceAbility`` (Earl Memnon: the one Influence his High Council
    visit grants)."""

    contextually_deferred: ClassVar[bool] = True  # ContextuallyDeferred

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ConnectionsInfluenceAbility.SelectionMode``:
        Explicit (3)."""

        return SelectionMode.EXPLICIT

    def can_run_immediately(self, p: Profile) -> bool:
        """``CanRunImmediately``: ``CurrentPlayer == null ||
        IsInPlayerTurn(Reveal) || !DeferredThresholdReached()``."""

        return _runs_unless_threshold(p)

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasHighCouncilSeat``, then (``CostAction.Then``)
        ``CanGainInfluence`` and ``HasCustomAbility`` (the grant the leader's trigger
        made, the engine's)."""

        me = p.ctx.me
        return me.high_council and any(
            _can_gain_faction_influence(me, f) for f in FACTIONS
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ConnectionsInfluenceAbility.Evaluate``.

        Each offered track is priced ``G(track, +1, -1, false)`` and stored at
        its sum when that is above 0.0 (``cmpnlesd``; the constant at
        0x520cdf8 is 0.0), else at the literal 0.5 (strictly better
        replaces)."""

        choice = _Choice()
        for track in _targets(request, 0, Kind.TRACK):
            g = p.gain_influence_value(track.ref, 1, -1, False)
            choice.update_targets(g.sum if g.sum > 0.0 else 0.5, (track.ref,))
        return choice.answer("Connections Influence")


@port(_AA + "leader_draw")
class LeaderDrawAbility(DrawAbility):
    """``ActivatedAbilities.LeaderDrawAbility`` (Count Ilban's and Countess
    Ariana's draw): ``DrawAbility`` with ``HideInvalidDeferred`` set
    (constructor) and no AI override; ``IsUnexhausted`` =
    true. ``Cost`` adds the player's ``LeaderDrawAbility``
    attribute (the engine's grant) to ``DrawAbility``'s ``HasDrawableCard``."""
