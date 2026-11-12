"""Ports of the app's Epic Game Mode and promo ability classes.

spec/epic-goto11-promo-draft.md (its Errata first): Control the Spice (§2.3), Economic
Supremacy (§2.4) and the three Uprising promos (§4.3-§4.5).

Each port subclasses the port of its app base class and registers itself with
``@port("<full app class name>")`` (see ``abilities/base.py``):

- ``ActivatedAbilities.DeferredAbility`` <- ``RiseOfIx.ControlTheSpiceAbility``,
  ``Promo.ArrakisRevoltAbility``,
  ``ability.conflict.ix.economic_supremacy_solari`` and
  ``…SpiceAbility``;
- ``ConflictAbilities.ConflictAbility`` <- ``RiseOfIx.EconomicSupremacyFirst``/
  ``Second``/``ThirdAbility`` (not ``GenericConflictAbility``: the card has no
  ``ConflictRewardArchetypes``, its rewards are in these overrides).

Already ported in ``imperium_b.py`` and checked against §4.4-§4.5 (not
re-registered here): ``Promo.PivotalGambitAbility`` and the three
``Promo.TheBeastsSpoils…Ability`` classes. What §4.4's Errata adds for Pivotal
Gambit is engine-side (the extra influence is lost when the current Conflict
has no ``GenericConflictFirstAbility``); ``pivotal_gambit_reward_ability``
answers that test for the windows.

None of the promos has ``AcquireValue``, ``EarlyMod``/``LateMod``,
``DeferValue`` or ``Tags`` (§4.2): ``ImperiumPlayable.AcquireValue``
starts from 0 for them, as the profile already does for an absent attribute;
there is nothing to port.

Request / answer encoding (``abilities/generic.py``): the candidates of a
prompt are ``request.infos[0]``; ``Answer.response is None`` is the app's
untouched choice (value 0), ``()`` "use" with no sub-targets
(``UpdateSelectionTargets(v, src, empty)``), ``((ref, ...),)`` the chosen refs
of the first target info.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    abilities_of,
    ability_for,
    port,
)
from dune_imperium.agents.app_ai.abilities.generic import (
    ConflictAbility,
    DeferredAbility,
    GenericConflictFirstAbility,
    _targets,
    collect_first,
)
from dune_imperium.agents.app_ai.catalog import card_entity
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.combat import rank_combat

if TYPE_CHECKING:
    from dune_imperium.agents.app_ai.profile import Profile

_ES = "ability.conflict.ix.economic_supremacy"
_ES_SOLARI = _ES + "_solari"
_ES_SPICE = _ES + "_spice"


# ---------------------------------------------------------------------------
# Control the Spice (Epic Game Mode starter) — §2.3
# ---------------------------------------------------------------------------


def find_trash_targets(p: Profile) -> tuple[Entity, ...]:
    """``Player.FindTrashTargets(null)`` for the seat itself.

    ``Hand ++ (PlayArea ++ ActiveAgentArea).OfType<ImperiumPlayable>() ++ Discard``
    (``Enumerable.Concat`` order, minus the cards whose ``Permanent`` attribute is true
    (no archetype sets it). Our ``in_play`` holds both play areas in play order;
    ``counted_in_play`` leaves out a Usurp-borrowed Row card, which our engine never
    offers as a trash target (OQ-054).
    """

    me = p.ctx.me
    cards = (
        card_entity(ref, p.ctx.seat)
        for ref in (*p.ctx.hand, *counted_in_play(me), *me.discard_pile)
    )
    return tuple(card for card in cards if card.attr("Permanent") is not True)


@port("ability.activated.ix.control_the_spice")
class ControlTheSpiceAbility(DeferredAbility):
    """``ability.activated.ix.control_the_spice`` (§2.3).

    ``constructor``: ``DeferredAbility(m, name, 0, 0)``, timing Agent,
    ``HasButtonText``. ``SelectionMode`` = Optional;
    ``CanRunImmediately`` is the default (false), so it is a key of the
    post-Agent-action prompt and never forces it. The card's ``DeferValue`` 2
    is not read by ``evaluate`` (overridden) but counts toward
    ``DeferredThresholdReached`` while the card is this turn's agent card
    (``generic.deferred_threshold_reached`` reads the archetype attribute).

    The app asks one combined question (pay 1 spice, trash the chosen card,
    gain a troop: ``BeginExecution``, pay -> trash -> troop).
    Our engine asks ``pay_agent_card_spice`` and then an ``optional_trash``
    (pay -> troop -> trash; troops are never trash targets, so the list is
    the same). The windows map the app answer onto both: pay iff
    ``evaluate`` wins the post-action prompt (it names a card only then), and
    trash ``trash_target(answer)`` at the second step (plan §4.6,
    ``Memory.intents``).
    """

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``f64=1.0``: the ``minTrashValue`` of ``GetCardToTrash``.
    MIN_TRASH_VALUE: ClassVar[float] = 1.0

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ControlTheSpiceAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 1)`` (literal)."""

        return p.ctx.me.resources.spice >= 1

    def target_request(self, p: Profile) -> Request:
        """``Targets``: the prompt ``evaluate`` sees.

        One target info, kind ``SelectTrashCard``, not forced, max 1, min 0,
        over ``FindTrashTargets(null)``; no target info when that list is
        empty (it never is after the Agent play: the card itself is in play).
        """

        targets = find_trash_targets(p)
        if not targets:
            return Request()
        return Request((TargetInfo(targets, (), 0, 1, False),))

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ControlTheSpiceAbility.Evaluate``.

        ``GetSpiceValue(-1)`` "Pay 1 Spice" + ``TrashCardValue`` "Trash Card"
        + ``TrashMod()`` "Trash Card Bonus" + ``GetTroopValue(1, false)``
        "Troop", then ``GetCardToTrash(targets, 1.0)``: without a card the
        choice stays untouched (value 0, not taken: Optional); with one, the
        sum names that card. The value does not depend on the card, and there
        is no affordability test (``Cost`` gates the offer).
        """

        s = Summer()
        s.add("Pay 1 Spice", p.spice_value(-1))
        s.add("Trash Card", p.trash_card_value())
        s.add("Trash Card Bonus", p.trash_mod())
        s.add("Troop", p.troop_value(1, False))
        card, _score = p.card_to_trash(
            _targets(request, Kind.CARD), self.MIN_TRASH_VALUE
        )
        if card is None:
            return Answer(0.0, None, "Control The Spice (Agent) | nothing to trash")
        return Answer(
            s.sum, ((card.ref,),), f"Control The Spice (Agent) | trashing: {card.ref}"
        )

    @staticmethod
    def trash_target(answer: Answer) -> str | None:
        """The card ref an ``evaluate`` answer trashes (None: not taken)."""

        if answer.response is None or not answer.response or not answer.response[0]:
            return None
        return str(answer.response[0][0])

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ControlTheSpiceAbility.ValueForPlayer``.

        At a space where 1 more spice cannot be paid
        (``CanAgentAbilityBePlayedWithSpace(space, Spice, 1)`` false, to the pay path
        otherwise): ``+ 0.0`` and stop. Unlike Smuggler's Haven and Arrakis Revolt the
        test is not inverted. Else ``-GetSpiceValue(1)`` (with the sign mask) +
        ``TrashCardValue`` + ``TrashMod()`` + ``GetTroopValue(1, false)``. No test that
        a junk card exists (``evaluate`` has it). A missing space takes the pay path.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is not None and not p.can_agent_ability_be_played_with_space(
            space, Attr.SPICE, 1
        ):
            v.add(
                "Control The Spice Ability cost cannot be paid in addition to "
                f"{space.ref} cost",
                0.0,
            )
            return v
        v.add("Control The Spice -1 Spice", -p.spice_value(1))
        v.add("Control The Spice Trash", p.trash_card_value())
        v.add("Trash Card Bonus", p.trash_mod())
        v.add("Control The Spice Troop", p.troop_value(1, False))
        return v


# ---------------------------------------------------------------------------
# Arrakis Revolt (Uprising promo) — §4.3, imperium-a.md §2.1
# ---------------------------------------------------------------------------


@port("ability.activated.promo.arrakis_revolt")
class ArrakisRevoltAbility(DeferredAbility):
    """``ability.activated.promo.arrakis_revolt`` (imperium-a.md §2.1).

    ``constructor``: timing Agent, ``HasButtonText`` set to the card's Agent button.
    ``SelectionMode`` = Optional; ``CanRunImmediately`` default (false): a
    post-Agent-action key. No ``Targets``: the only follow-up question is the
    ``BlowWall`` prompt.

    ``BeginExecution`` (Errata): case 0 sets ``ActiveAbilityIndex`` to 1, then the
    stinger (cases 0/1), ``PaySpice(2)``
, ``BlowWall(aiAlwaysUse = false, intrigueMode = false)`` (case
    4), the sandworm deploy (case 5). A resumed run (``ActiveAbilityIndex != 0``) jumps
    straight to the deploy, skipping the payment and the wall question; that is
    save/restore plumbing, no AI question. ``should_blow_wall_after_payment`` answers
    the wall question on the paid state.
    """

    timing: ClassVar[Timing] = Timing.AGENT
    #: ``HasResources.AtLeast(Spice, 2)`` / ``PaySpice(2)`` / ``GetSpiceValue(-2)``.
    SPICE_COST: ClassVar[int] = 2

    def selection_mode(self, p: Profile) -> SelectionMode:
        """``ArrakisRevoltAbility.SelectionMode``: Optional."""

        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``Cost``: ``HasResources.AtLeast(Spice, 2).Then(
        BoolAction(ctx.GetTarget<Player>()?.HasMakerHooks ?? false))``."""

        me = p.ctx.me
        return me.resources.spice >= self.SPICE_COST and me.maker_hooks

    def evaluate(self, p: Profile, request: Request) -> Answer:
        """``ArrakisRevoltAbility.Evaluate``.

        ``GetSpiceValue(-2)`` "Spice Cost" + ``BlowWallValue()`` "Blow Wall
        Value" (the summer overload ``Add`` =
        ``MergePrependReason``) + ``GetSandWormValue(1, false)`` "Sandworm
        Value"; ``UpdateSelectionTargets(sum, src, [])``. No affordability,
        maker-hook or wall test (``Cost`` gates the offer; ``BlowWallValue``
        ignores whether the wall stands).
        """

        s = Summer()
        s.add("Spice Cost", p.spice_value(-self.SPICE_COST))
        s.merge(p.blow_wall_value())
        s.add("Sandworm Value", p.sandworm_value(1, False))
        return Answer(s.sum, (), "Arrakis Revolt")

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``ArrakisRevoltAbility.ValueForPlayer``.

        Inverted affordability (app bug kept, 17 §16): nothing without a space or
        without maker hooks, and nothing when ``CanAgentAbilityBePlayedWithSpace(space,
        Spice, 2)`` is true (to the epilogue); only an unaffordable trade is valued:
        ``GetSpiceValue(-2)`` "Arrakis RevoltSpice Cost" + ``BlowWallValue()`` +
        ``GetSandWormValue(1, false)``.
        """

        v = Summer()
        space = collect_first(with_entities, Kind.SPACE)
        if space is None:
            return v
        if not p.ctx.me.maker_hooks:
            return v
        if p.can_agent_ability_be_played_with_space(space, Attr.SPICE, self.SPICE_COST):
            return v
        v.add("Arrakis RevoltSpice Cost", p.spice_value(-self.SPICE_COST))
        v.merge(p.blow_wall_value())
        v.add("Sandworm Value", p.sandworm_value(1, False))
        return v

    def should_blow_wall_after_payment(self, p: Profile) -> bool:
        """The ``BlowWall`` prompt's answer: ``ChooseBlowWall``.

        With ``aiAlwaysUse`` and ``intrigueMode`` false the response is
        ``ShouldBlowWall()``; the prompt comes after ``PaySpice(2)``
        (Errata order), so it is evaluated on a copy of the state with the 2
        spice paid, by a fresh profile (a new ``MakeChoice``) sharing ``p``'s
        constants and RNG. Call it only when ``meets_cost`` holds.
        """

        me = p.ctx.me
        paid = replace(
            me,
            resources=replace(me.resources, spice=me.resources.spice - self.SPICE_COST),
        )
        players = tuple(
            paid if player.player_id == me.player_id else player
            for player in p.ctx.players
        )
        state = replace(p.ctx.state, players=players)
        profile = type(p)(AppContext(state, p.ctx.seat, p.ctx.view), p.C, p.rng)
        return profile.should_blow_wall()


# ---------------------------------------------------------------------------
# Pivotal Gambit (Uprising promo) — §4.4 Errata
# ---------------------------------------------------------------------------


def pivotal_gambit_reward_ability(conflict: Entity) -> Ability | None:
    """The reward Pivotal Gambit extends: ``conflict.Abilities.FirstOrDefault( a => a is
    GenericConflictFirstAbility)`` (a type-hierarchy test).

    ``PivotalGambitAbility.BeginExecution`` appends ``GainAnyInfluenceConflictAbility``
    to that ability's ``CustomAbilityIDs``, so the 1st-place winner later gets one more
    "gain any influence" charge. None for Economic Supremacy: then (Errata) both the
    ``ChangeAttribute`` and the ``PivotalGambitInfluence`` counter are skipped and the
    extra influence is silently lost; the self-trash and the troop still happen.
    """

    for ability in abilities_of(conflict):
        if isinstance(ability, GenericConflictFirstAbility):
            return ability
    return None


# ---------------------------------------------------------------------------
# Economic Supremacy (Epic Game Mode Conflict III) — §2.4
# ---------------------------------------------------------------------------


def economic_supremacy_first_reward_vp(player: PlayerState, double_cost: bool) -> int:
    """``EconomicSupremacyFirstAbility.GetPossibleRewardVP``.

    ``2 - (Solari < (doubleCost ? 12 : 6)) + (Spice >= 4 * doubleCost + 4)`` (literals
    of the app) on the player's current resources, for any player (the end-of-round
    projection asks every seat).
    """

    need_solari = 12 if double_cost else 6
    need_spice = 4 * int(double_cost) + 4
    return (
        2
        - int(player.resources.solari < need_solari)
        + int(player.resources.spice >= need_spice)
    )


@port("ability.conflict.ix.economic_supremacy_first")
class EconomicSupremacyFirstAbility(ConflictAbility):
    """``ability.conflict.ix.economic_supremacy_first`` (constructor
: ``ConflictPlace`` 1; ``Cost`` = ``NoCost``).

    ``BeginExecution``: ``GainVP(1)``, the ``EconomicSupremacyPoints`` statistic, then
    (``conflict.Abilities.Count() > 4``) ``GainCustomAbility`` of the card's
    ``EconomicSupremacySolariAbility`` and ``…SpiceAbility`` (the old-save branch builds
    the same two from ``Playmat.Box``), then the ability's own ``CustomAbilityIDs``
    (none: Pivotal Gambit only extends a ``GenericConflictFirstAbility``).
    """

    place: ClassVar[int | None] = 1

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EconomicSupremacyFirstAbility.ValueForPlayer``.

        ``n = 1``; with ``Solari >= 6``: ``GetSolariValue(-6)`` "Economic Supremacy
        First Pay 6 Solari", ``n = 2``; with ``Spice >= 4``: ``GetSpiceValue(1) * -4.0``
        "… Pay 4 Spice", ``n += 1``; then ``GetVictoryPointValue(n)`` "Economic
        Supremacy First <n> VP". Affordability is read on the current resources; the
        literals are the app's.
        """

        v = Summer()
        me = p.ctx.me
        n = 1
        if me.resources.solari >= 6:
            v.add("Economic Supremacy First Pay 6 Solari", p.solari_value(-6))
            n = 2
        if me.resources.spice >= 4:
            v.add("Economic Supremacy First Pay 4 Spice", p.spice_value(1) * -4.0)
            n += 1
        v.add(f"Economic Supremacy First {n} VP", p.victory_point_value(n))
        return v

    def possible_reward_vp(self, p: Profile, double_cost: bool) -> int:
        """``GetPossibleRewardVP`` for the seat itself;
        overrides the base ``place == 1 ? owner.VictoryPoints`` (4 here)."""

        return economic_supremacy_first_reward_vp(p.ctx.me, double_cost)

    def granted_abilities(self) -> tuple[Ability, ...]:
        """The two optional charges its ``BeginExecution`` grants, in order:
        ``EconomicSupremacySolariAbility`` then ``…SpiceAbility`` (owner: the
        Conflict card)."""

        return (ability_for(_ES_SOLARI, self.owner), ability_for(_ES_SPICE, self.owner))


@port("ability.conflict.ix.economic_supremacy_second")
class EconomicSupremacySecondAbility(ConflictAbility):
    """``EconomicSupremacySecondAbility`` (constructor: ``ConflictPlace``
    2; ``Cost`` = ``NoCost``; ``BeginExecution``:
    ``GainVictoryPoints(1)``)."""

    place: ClassVar[int | None] = 2

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EconomicSupremacySecondAbility.ValueForPlayer``:
        ``GetVictoryPointValue(1)`` "Conflict Economic Supremacy Second VP"."""

        v = Summer()
        v.add("Conflict Economic Supremacy Second VP", p.victory_point_value(1))
        return v

    def possible_reward_vp(self, p: Profile, double_cost: bool) -> int:
        """``GetPossibleRewardVP``: always 1."""

        return 1


@port("ability.conflict.ix.economic_supremacy_third")
class EconomicSupremacyThirdAbility(ConflictAbility):
    """``EconomicSupremacyThirdAbility`` (constructor: ``ConflictPlace`` 3;
    ``Cost`` = ``NoCost``; ``BeginExecution``: ``GainSolari(2)``
    then ``GainSpice(2)``). ``GetPossibleRewardVP`` is the base one (place 3
    -> 0)."""

    place: ClassVar[int | None] = 3

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        """``EconomicSupremacyThirdAbility.ValueForPlayer``.

        ``GetSpiceValue(1)`` doubled "Conflict Economic Supremacy Third 2 Spice", then
        ``GetSolariValue(2)`` "… 2 Solari".
        """

        v = Summer()
        spice = p.spice_value(1)
        v.add("Conflict Economic Supremacy Third 2 Spice", spice + spice)
        v.add("Conflict Economic Supremacy Third 2 Solari", p.solari_value(2))
        return v


class _EconomicSupremacyPayAbility(DeferredAbility):
    """Shared shape of the two Economic Supremacy charges (not an app class).

    Both app classes are ``DeferredAbility`` subclasses with identical
    overrides except the resource: constructor timing CombatResolution and
    ``HasButtonText``; ``SelectionMode`` = Optional; ``IsUnexhausted`` = true;
    ``Cost`` = ``IsRewardPlace(1).Then(HasCustomAbility(this)).Then(
    HasResources.AtLeast(<resource>, <n>))``; ``Evaluate`` =
    ``UpdateSelectionTargets(100.0, src, null)`` ("always play").
    ``ValueForPlayer`` and ``GetPossibleConflictVP`` are not overridden (0).
    ``BeginExecution``: pay, ``GainVictoryPoints(1)``,
    ``RemoveCustomAbility(this)``, statistics.

    ``solari_cost``/``spice_cost``/``victory_points`` mirror
    ``PayAttributeToGainVPAbility``'s so a window can match our
    ``combat_reward_optional`` frame (``resource``, ``cost``) to the charge.
    """

    timing: ClassVar[Timing] = Timing.COMBAT_RESOLUTION
    solari_cost: ClassVar[int] = 0
    spice_cost: ClassVar[int] = 0
    #: ``GainVictoryPoints(1, owner, "Conflict")`` in ``BeginExecution``.
    victory_points: ClassVar[int] = 1
    LABEL: ClassVar[str] = ""

    def selection_mode(self, p: Profile) -> SelectionMode:
        return SelectionMode.OPTIONAL

    def meets_cost(self, p: Profile) -> bool:
        """``IsRewardPlace(1)`` (``CanBePaid``: the prompt
        context's ``Place`` is 1), ``HasCustomAbility(this)`` (granted by
        ``EconomicSupremacyFirstAbility``) and the resource.

        Judgement (as ``PayAttributeToGainVPAbility``): the grant is held
        while the seat answers our ``combat_reward_optional`` frame; the place
        is the sole winner of ``rank_combat`` (``DetermineRewards``' place 1).
        """

        ctx = p.ctx
        if ctx.decision_kind != "combat_reward_optional":
            return False
        state = ctx.state
        if rank_combat(state.players, first_player=state.first_player).winner != (
            ctx.seat
        ):
            return False
        me = ctx.me
        return (
            me.resources.solari >= self.solari_cost
            and me.resources.spice >= self.spice_cost
        )

    def evaluate(self, p: Profile, request: Request) -> Answer:
        return Answer(100.0, (), self.LABEL)


@port(_ES_SOLARI)
class EconomicSupremacySolariAbility(_EconomicSupremacyPayAbility):
    """``EconomicSupremacySolariAbility`` (constructor, ``Cost`` = ``AtLeast(Solari,
    6)``, ``SelectionMode``, ``IsUnexhausted``, ``Evaluate`` = 100 "Economic Supremacy
    Solari | always play"; ``BeginExecution``: ``PaySolari(6)``)."""

    solari_cost: ClassVar[int] = 6
    LABEL: ClassVar[str] = "Economic Supremacy Solari | always play"


@port(_ES_SPICE)
class EconomicSupremacySpiceAbility(_EconomicSupremacyPayAbility):
    """``EconomicSupremacySpiceAbility`` (constructor, ``Cost``
    = ... ``AtLeast(Spice, 4)``, ``SelectionMode``,
    ``IsUnexhausted``, ``Evaluate`` = 100 "Economic
    Supremacy Spice | always play"; ``BeginExecution``: ``PaySpice(4)``)."""

    spice_cost: ClassVar[int] = 4
    LABEL: ClassVar[str] = "Economic Supremacy Spice | always play"
