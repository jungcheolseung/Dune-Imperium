"""The ``turn`` window: the app's turn-start prompt (``DetermineTurn``).

App side (``analysis/ai/12-turn-structure.md`` §1, ``spec/engine-order.md``
§2.1 and §3.1-3.4). ``PlayerTurnPhase/<DetermineTurn>d__12::MoveNext``
@0x4a1c0c0 builds one **non-forced** ``SelectTargetsFrom`` whose keys are
(``WormPlaymat::GetUsablePrePlayerTurnAbilities`` @0x49ad270, in this order):

1. every hand card whose ``AgentAbility`` can run (an agent in supply and at
   least one legal space); its targets are the card's legal spaces in
   ``Board.children`` order, and ``MakeChoice`` scores it with
   ``AgentAbility::Evaluate`` @0x4bd28b0 (the first strictly best space);
2. every Plot intrigue whose Plot ability can run (``intrigue_play_sources``,
   shared with the other Plot windows);
3. leader abilities without Agent/Reveal timing and playmat abilities: our
   ``turn`` window has no counterpart (``docs/app-ai-plan.md`` §6).

There is no Reveal key: Reveal is the empty answer (no key worth more than 0),
our ``reveal_turn``. A Plot played here returns the app to the same prompt,
as our engine re-offers the TURN frame, so each question is answered afresh.

Our engine bakes two post-placement answers into the ``agent_turn`` action:
the cost option of Gather Support / Spice Refinery (the app's
``CostFirstSpaceAbility`` prompt, Agent-turn state 220) and the Spy recalled
to infiltrate an occupied space (``RecallSpyInfiltrateAbility``, state 240).
Both prompts are forced for an AI seat (``MakeUndoableAbilityResolution``
@0x49daf70, ``forced = !IsUndoAvailable`` = true). The app asks them only
after ``MakeChoice`` has picked the placement, so ``turn_window`` first ranks
the cards on a representative action of the chosen (card, space) and then
realises it with those two Evaluates, run on the state as it stands at that
app state (``_after_send`` / ``_after_cost_first``).

``place_track_spy`` (an owed Emperor-4 Spy) is never chosen here: the app
keeps that Spy for the post-action prompt (agent_effects / reveal windows).
Any other legal id with no key here makes the decision fall back (counted)
rather than the id being passed over unseen (``_KNOWN_ACTION_IDS``).

Bloodlines and the Tech Module (app-style keys, docs/app-ai-plan.md §11.4,
bloodlines-cards.md §3.18 and §8, bloodlines-systems.md §1.7, §3.3-3.4):

- ``play_turn_start_card`` (Litany Against Fear): one key per card,
  ``LitanyTurnStartAbility::Evaluate`` (draw value + the reveal penalty;
  D11), competing with the placements and Plots of this prompt.
- ``flip_tech`` (Advanced Data Analysis, Spy Drones): the tile's Flip ability
  is a key of the turn-start prompt (D25), E 100 (D23).
- ``resolve_tech_acquire_effect`` (a tile bought by a Plot at the turn
  start): resolved at once in the engine's key order (D15), each choice
  answered by its acquire ability (``tech_acquire_effect_sources``).
- Navigation Chamber: every ``agent_turn(discount=spice|solari)`` variant of
  a space is its own target (``space_with_cost_cut``; D60): the plain space,
  then the spice cut, then the Solari cut (our legal order), and the first
  strictly best wins.
- Commander spaces and Tuek's Sietch need nothing here: their abilities are
  overlays of ``catalog.space_entity`` and Tuek's Sietch is in
  ``board_space_order`` when Esmar Tuek plays.

Immortality (``spec/immortality.md`` §4, §8):

- Graft. A Graft card's key is ``GraftAgentAbility::Evaluate`` (every legal
  space valued with its best partner, ``abilities/immortality.py``); a plain
  card's key is the plain ``AgentAbility::Evaluate`` over all its legal spaces
  (with or without a partner). Once a placement wins, the app asks the
  partner at ``AgentTurnPhase`` state 50, *before* the placement
  (``GraftCardEvaluator``, ``graft_card_evaluate``): forced when the played
  card is a Graft card or the space is reachable only with a partner. A
  plain card never takes an optional partner (the evaluator answers
  nothing), so it is played alone where it can be; where it cannot, the
  forced prompt's empty answer is ``DefaultRandomChoice`` (a random legal
  partner). Our engine asks the partner after the placement
  (``agent_turn(graft=True)`` then ``graft_partner``), so the partner is
  computed here on the turn-time state and stored in ``Memory.intents``
  under ``("graft_partner", round, played card)`` for the ``graft_partner``
  window. The legal partners are the engine's own list for the realised
  placement (``legal_graft_partner_actions`` on the placed state).
- ``return_specimen``: ``ReturnSpecimenAbility`` (playmat; Optional, E = 1.0
  only for the troop shortfall, else no answer). ``use_family_atomics``:
  ``FamilyAtomicsAbility`` (E answers only in the seat's Reveal turn, so
  never here). UNTRACED (immortality.md §12 #9): which playmat abilities
  the turn-start filter ``b__3`` keeps; both are taken to be turn-start keys.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to a random legal
action (``DefaultRandomChoice``), counted in ``AppAIAgent.fallbacks``.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace

from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Request,
    TargetInfo,
    abilities_of,
    ability_for,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
    LitanyTurnStartAbility,
)
from dune_imperium.agents.app_ai.abilities.bloodlines_systems import (
    AdvancedDataAnalysisAbility,
    GeneLockedVaultAcquiredAbility,
    RapidDropshipsAbility,
    SpyDronesAbility,
)
from dune_imperium.agents.app_ai.abilities.board import (
    GatherSupportAbility,
    RecallSpyInfiltrateAbility,
    SpiceRefineryAbility,
)
from dune_imperium.agents.app_ai.abilities.generic import AgentAbility, SpaceAbility
from dune_imperium.agents.app_ai.abilities.immortality import graft_card_evaluate
from dune_imperium.agents.app_ai.abilities.tech import MemocordersAcquiredAbility
from dune_imperium.agents.app_ai.catalog import (
    BLOODLINES_SPACE_ORDER,
    CARD_ARCHETYPES,
    IMMORTALITY_SPACE_ARCHETYPES,
    POST_INDEX,
    SPACE_ARCHETYPES,
    TECH_ARCHETYPES,
    card_entity,
    space_entity,
    spy_entity,
    tech_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import default_random_choice
from dune_imperium.agents.app_ai.context import AppContext, Board, card_id
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile.bloodlines import space_with_cost_cut
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    int_arg,
    str_arg,
    with_arg,
)
from dune_imperium.agents.app_ai.windows.intrigue import intrigue_play_sources
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.agent_turn import apply_agent_action
from dune_imperium.rules.graft import legal_graft_partner_actions

#: The board set of a 4-player Uprising game (``SetupPhase/<BeginSetup>``).
_BOARD_SET = "Uprising"
_IMMORTALITY_AA = "worm.canis.abilities.ActivatedAbilities.Immortality."
#: Playmat abilities (``SetupPhase/<BeginSetup>`` adds them with Immortality,
#: spec immortality.md §1.4); their owner is never read.
_RETURN_SPECIMEN = _IMMORTALITY_AA + "ReturnSpecimenAbility"
_FAMILY_ATOMICS = _IMMORTALITY_AA + "FamilyAtomicsAbility"
#: The ``Memory.intents`` key the ``graft_partner`` window reads:
#: ``(GRAFT_PARTNER_INTENT, round, played card ref) -> partner ref``.
GRAFT_PARTNER_INTENT = "graft_partner"
#: The action ids this window answers or leaves on purpose
#: (``place_track_spy``); any other legal id makes it fall back.
_KNOWN_ACTION_IDS: frozenset[str] = frozenset(
    {
        "agent_turn",
        "place_track_spy",
        "play_intrigue",
        "return_specimen",
        "reveal_turn",
        "use_family_atomics",
        # Bloodlines / Tech Module (app-style keys).
        "play_turn_start_card",
        "flip_tech",
        "resolve_tech_acquire_effect",
    }
)
#: Navigation Chamber's discount variants of one space, in our legal order
#: (``rules/agent_turn.py`` ``_actions_for_affordable_costs``): the plain
#: cost, then the spice cut, then the Solari cut.
_DISCOUNT_ORDER: tuple[str | None, ...] = (None, "spice", "solari")
#: A tile's Flip activation (bloodlines-systems.md §3.3; D23-D25).
_FLIP_ABILITIES = (AdvancedDataAnalysisAbility, SpyDronesAbility, RapidDropshipsAbility)
#: Gene-Locked Vault's branches -> our ``choice`` argument.
_VAULT_CHOICES: dict[int, str] = {
    GeneLockedVaultAcquiredAbility.INTRIGUE: "intrigue",
    GeneLockedVaultAcquiredAbility.CARD: "card",
}
#: Space abilities whose ``.ctor`` sets ``CostFirstSpaceAbility``
#: (engine-order §3.1 state 220: Spice Refinery and Gather Support).
_COST_FIRST: tuple[type[SpaceAbility], ...] = (
    GatherSupportAbility,
    SpiceRefineryAbility,
)


# ---------------------------------------------------------------------------
# Board order (the app's target order for spaces)
# ---------------------------------------------------------------------------


#: ``AllArchetypes()`` order of the space archetypes a 4-player Uprising game
#: can deal (with or without CHOAM and Immortality): their typedef (metadata)
#: order in ``dump/worm-canis.dll.cs``, typeIndex in the comments. The space
#: archetypes in between (Rise of Ix 645-648, the rest of the base set) carry
#: no ``Uprising``/``CHOAMModule``/``Immortality`` set, so ``BeginSetup``
#: never keeps them. With Immortality, ``ResearchStationImmortality`` (set
#: ``Immortality``) is appended with the other expansion spaces and
#: ``ResearchStationUP`` is removed (``RemovedFromSetList``).
_SPACE_ARCHETYPE_ORDER: tuple[str, ...] = (
    "SpaceArchetypes.Uprising.AcceptContractCHOAM",  # 624
    "SpaceArchetypes.Uprising.AcceptContractUP",  # 625
    "SpaceArchetypes.Uprising.AssemblyHall",  # 626
    "SpaceArchetypes.Uprising.DeepDesert",  # 627
    "SpaceArchetypes.Uprising.DeliverSupplies",  # 628
    "SpaceArchetypes.Uprising.DesertTactics",  # 629
    "SpaceArchetypes.Uprising.DutifulServiceCHOAM",  # 630
    "SpaceArchetypes.Uprising.DutifulServiceUP",  # 631
    "SpaceArchetypes.Uprising.Espionage",  # 632
    "SpaceArchetypes.Uprising.Fremkit",  # 633
    "SpaceArchetypes.Uprising.GatherSupport",  # 634
    "SpaceArchetypes.Uprising.HaggaBasinUP",  # 635
    "SpaceArchetypes.Uprising.HeighlinerUP",  # 636
    "SpaceArchetypes.Uprising.HighCouncilUP",  # 637
    "SpaceArchetypes.Uprising.ImperialPrivilege",  # 638
    "SpaceArchetypes.Uprising.ResearchStationUP",  # 639
    "SpaceArchetypes.Uprising.Sardaukar",  # 640
    "SpaceArchetypes.Uprising.Shipping",  # 641
    "SpaceArchetypes.Uprising.SietchTabrUP",  # 642
    "SpaceArchetypes.Uprising.SpiceRefinery",  # 643
    "SpaceArchetypes.Uprising.SwordmasterUP",  # 644
    "SpaceArchetypes.Immortality.ResearchStationImmortality",  # 649
    "SpaceArchetypes.BaseSet.Arrakeen",  # 650
    "SpaceArchetypes.BaseSet.ImperialBasin",  # 659
    "SpaceArchetypes.BaseSet.Secrets",  # 663
)
#: Our space id of each app space archetype (both CHOAM variants).
_SPACE_OF_ARCHETYPE: dict[str, str] = {
    **{
        archetype: space_id
        for space_id, variants in SPACE_ARCHETYPES.items()
        for archetype in variants
    },
    **{
        archetype: space_id
        for space_id, archetype in IMMORTALITY_SPACE_ARCHETYPES.items()
    },
}


def _set_attr(archetype: str, name: str) -> tuple[str, ...]:
    """A set-list attribute (``SetList``/``RemovedFromSetList``) of an archetype."""

    value = ARCHETYPES[archetype].attributes.get(name, ())
    return tuple(str(item) for item in value) if isinstance(value, tuple) else ()


def board_space_order(board: Board) -> tuple[str, ...]:
    """``Board.children`` space order (``WormBoard::ValidSpaces`` @0x4828890).

    engine-order §7: ``SetupPhase/<BeginSetup>d__6`` @0x4a42600 takes
    ``AllArchetypes()`` spaces of the board set (``SetList`` holds
    ``Uprising``), then ``AddRange`` the spaces of the other enabled sets
    (CHOAM 4001: ``SetList = [CHOAMModule]``), then ``RemoveAll`` the spaces
    an enabled set removes (``RemovedFromSetList``: the two ``…UP`` spaces
    CHOAM replaces); no sort on the way. ``AgentAbility::Evaluate``
    @0x4bd28b0 keeps the first strictly-best space, so this order settles an
    exact value tie inside one card.

    ``AllArchetypes()`` is ``CanisReflection.MakeArchetypes`` (<>c
    ``b__17_0`` @0x4ead350): ``<MakeArchetypes>d__3::MoveNext`` @0x2ac96d0
    walks ``CanisReflection::ExportedTypes`` @0x8e3220 (the assembly's type
    array, cached, unsorted) in order.

    UNTRACED (engine-order §9): the order of the runtime's type array; the
    spec's assumption, metadata (typedef) order, is ``_SPACE_ARCHETYPE_ORDER``.
    Tuek's Sietch (Bloodlines, no app set) comes last when Esmar Tuek plays.
    """

    # UNTRACED: the reflection order (engine-order §9) is taken to be the
    # typedef order of dump/worm-canis.dll.cs, as the spec assumes.
    enabled = (
        _BOARD_SET,
        *(("CHOAMModule",) if board.choam else ()),
        *(("Immortality",) if board.immortality else ()),
    )
    archetypes = [
        a for a in _SPACE_ARCHETYPE_ORDER if _BOARD_SET in _set_attr(a, "SetList")
    ]
    archetypes.extend(
        a
        for a in _SPACE_ARCHETYPE_ORDER
        if any(s in _set_attr(a, "SetList") for s in enabled[1:])
    )
    app_spaces = tuple(
        _SPACE_OF_ARCHETYPE[a]
        for a in archetypes
        if not any(s in _set_attr(a, "RemovedFromSetList") for s in enabled)
    )
    # App-style (plan §11.8): Tuek's Sietch, a space of no app set, is
    # appended after the app's spaces when Esmar Tuek is in the game, as the
    # app appends an enabled expansion's spaces.
    if board.tueks_sietch:
        return (*app_spaces, *BLOODLINES_SPACE_ORDER)
    return app_spaces


# ---------------------------------------------------------------------------
# The state at the app's post-placement prompts (states 220 and 240)
# ---------------------------------------------------------------------------


def _with_players(state: GameState, players: Sequence[PlayerState]) -> GameState:
    return replace(state, players=tuple(players))


def _after_send(state: GameState, seat: int, card_ref: str, space_id: str) -> GameState:
    """The state after ``PlayAgentCard`` (100) and ``SendAgentToSpace`` (200).

    The card goes from hand to play, the Agent onto the space, and the
    space's controller (any seat) takes its control bonus
    (``ControlSolari``/``ControlSpice``, engine-order §3.1 state 200). The
    space cost is not paid yet: ``SpaceAbility/<BeginExecution>d__10``
    (@0x4bb1a50, case 0, ``PayCost`` vslot 82 at 0x4bb1d50) pays it when the
    space ability runs, at 220 for a cost-first space and at 400 otherwise.

    Judgement: the decision stack (our TURN frame) and the view are kept;
    none of the Evaluates run on this state (Gather Support, Spice Refinery,
    ``GetRecallSpy``) reads the turn type or the open frame. Staban's Smuggle
    Spice (an opponent's spice at a Maker space) is not applied: no read here
    depends on another seat's spice.
    """

    players = list(state.players)
    me = players[seat]
    players[seat] = replace(
        me,
        agents_available=me.agents_available - 1,
        agent_locations=(*me.agent_locations, space_id),
        hand=tuple(card for card in me.hand if card != card_ref),
        in_play=(*me.in_play, card_ref),
    )
    space = space_entity(space_id, Board.of(state.config))
    for attr, field in (("ControlSolari", "solari"), ("ControlSpice", "spice")):
        amount = space.int_attr(attr)
        if amount <= 0:
            continue
        for index, player in enumerate(players):
            if space_id in player.control_space_ids:
                resources = player.resources
                players[index] = replace(
                    player,
                    resources=replace(
                        resources, **{field: getattr(resources, field) + amount}
                    ),
                )
    return _with_players(state, players)


def _after_cost_first(
    state: GameState, seat: int, ability: Ability, option: int
) -> GameState:
    """The state after the cost-first space ability (state 220) ran.

    Gather Support (board §1.4.16): recruit the space's ``Troops`` (2) from
    the supply; option 1 also pays ``FindSolariCost`` (2) Solari for 1 water
    (literal). Spice Refinery (board §1.4.19): pay ``option`` spice and gain
    ``SolariAmount(option)`` Solari. Any other ability: unchanged.
    """

    players = list(state.players)
    me = players[seat]
    resources = me.resources
    if isinstance(ability, GatherSupportAbility):
        troops = min(ability.owner.int_attr("Troops"), me.troops_supply)
        if option == 1:
            resources = replace(
                resources,
                solari=resources.solari - ability.find_solari_cost(),
                water=resources.water + 1,
            )
        me = replace(
            me,
            resources=resources,
            troops_supply=me.troops_supply - troops,
            troops_garrison=me.troops_garrison + troops,
        )
    elif isinstance(ability, SpiceRefineryAbility):
        resources = replace(
            resources,
            spice=resources.spice - option,
            solari=resources.solari + ability.solari_amount(option),
        )
        me = replace(me, resources=resources)
    players[seat] = me
    return _with_players(state, players)


def _profile_on(run: DecisionRun, state: GameState) -> Profile:
    """A fresh profile on ``state``: the app starts a new ``MakeChoice``."""

    ctx = AppContext(state, run.ctx.seat, run.ctx.view)
    return Profile(ctx, run.profile.C, run.rng)


def _cost_first_ability(space_id: str, board: Board) -> Ability | None:
    """The chosen ``SpaceAbility`` when it is cost-first, else None.

    ``<DetermineAbilities>d__23`` @0x49de650: the space's first
    ``SpaceAbility`` that can run; state 220 runs only if it carries
    ``CostFirstSpaceAbility``.
    """

    for ability in abilities_of(space_entity(space_id, board)):
        if isinstance(ability, SpaceAbility):
            return ability if isinstance(ability, _COST_FIRST) else None
    return None


def _forced_pick[T: (int, str)](
    run: DecisionRun, answer: Answer, legal: Sequence[T]
) -> T:
    """``MakeChoice`` on a forced single-key prompt (12 §3.3-3.4).

    The answer stands when it is worth more than 0 and names a legal target;
    otherwise ``PlayerEntity::DetermineDefaultRandomChoice`` @0x9b3340 picks
    the (only) key with random targets: a uniformly random legal target, drawn
    like ``choice.default_random_choice``.
    """

    if answer.value > 0.0 and answer.response:
        item = answer.response[0]
        for target in legal:
            if item and item[0] == target:
                return target
    return legal[run.rng.randrange(len(legal))]


# ---------------------------------------------------------------------------
# Realising the chosen placement
# ---------------------------------------------------------------------------


def _realise(run: DecisionRun, chosen: DomainAction) -> DomainAction:
    """The ``agent_turn`` variant the app ends up playing for (card, space).

    State 220 (cost-first spaces): ``GatherSupportAbility::Evaluate``
    @0x4bba660 / ``SpiceRefineryAbility::Evaluate`` @0x4bbfb90 pick the
    ``cost_option`` on the state after ``_after_send``. State 240 (occupied
    space): ``RecallSpyInfiltrateAbility::Evaluate`` @0x4d31d00 picks the Spy
    (``GetRecallSpy``) on the state after the cost-first ability. Both are
    forced prompts: a non-positive or empty answer is a random legal one.
    """

    card_ref = str_arg(chosen, "card_id")
    space_id = str_arg(chosen, "space_id")
    if card_ref is None or space_id is None:
        return chosen
    variants = [
        action
        for action in run.by_id("agent_turn")
        if str_arg(action, "card_id") == card_ref
        and str_arg(action, "space_id") == space_id
    ]
    # Navigation Chamber (D60): the discount variant the card's key chose.
    discount = str_arg(chosen, "discount")
    variants = [a for a in variants if str_arg(a, "discount") == discount] or variants
    graft = _graft_choice(run, card_ref, variants)
    if graft is not None:
        variants = [a for a in variants if (arg(a, "graft") is True) is graft]
        if len(variants) == 1:
            if graft:
                _store_graft_partner(run, variants[0])
            return variants[0]
    if len(variants) <= 1:
        return chosen
    realised = _realise_costs(run, card_ref, space_id, variants)
    if graft:
        _store_graft_partner(run, realised)
    return realised


def _realise_costs(
    run: DecisionRun, card_ref: str, space_id: str, variants: list[DomainAction]
) -> DomainAction:
    """States 220 and 240 over the variants of one (card, space, graft)."""

    seat = run.ctx.seat
    board = run.ctx.board
    state = _after_send(run.ctx.state, seat, card_ref, space_id)

    options = list(
        dict.fromkeys(
            option
            for option in (int_arg(action, "cost_option") for action in variants)
            if option is not None
        )
    )
    ability = _cost_first_ability(space_id, board)
    cost_first: tuple[Ability, int] | None = None
    if options:
        # Only cost-first spaces have several cost options in Uprising; any
        # other space would keep its first option (legal order).
        option = options[0]
        if len(options) > 1 and ability is not None:
            request = Request(infos=(TargetInfo(options=tuple(options)),), forced=True)
            answer = ability.evaluate(_profile_on(run, state), request)
            option = _forced_pick(run, answer, options)
        variants = [a for a in variants if int_arg(a, "cost_option") == option]
        if ability is not None:
            cost_first = (ability, option)

    posts = [
        post
        for post in dict.fromkeys(
            str_arg(action, "infiltrate_post_id") for action in variants
        )
        if post is not None
    ]
    if len(posts) > 1:
        # Judgement: the app's spy list follows its observation-post order
        # (``POST_INDEX``); ``GetRecallSpy`` shuffles it before ranking, so
        # the order only shifts which equal-valued Spy the shuffle keeps.
        posts.sort(key=lambda post: POST_INDEX[post])
        if cost_first is not None:
            state = _after_cost_first(state, seat, *cost_first)
        spies = tuple(spy_entity(post, seat) for post in posts)
        infiltrate = RecallSpyInfiltrateAbility(space_entity(space_id, board))
        request = Request(infos=(TargetInfo(entities=spies),), forced=True)
        answer = infiltrate.evaluate(_profile_on(run, state), request)
        post = _forced_pick(run, answer, posts)
        variants = [a for a in variants if str_arg(a, "infiltrate_post_id") == post]
    return variants[0]


# ---------------------------------------------------------------------------
# Graft: the state-50 partner question (spec immortality.md §4.1-4.2)
# ---------------------------------------------------------------------------


def _is_graft_card(card_ref: str, seat: int) -> bool:
    """``Graft (27) in card.Tags`` (``GraftCardEvaluator``'s test)."""

    return "Graft" in card_entity(card_ref, seat).list_attr("Tags")


def _graft_choice(
    run: DecisionRun, card_ref: str, variants: Sequence[DomainAction]
) -> bool | None:
    """Whether the app grafts this placement (None: no graft variant).

    ``AgentTurnPhase/<GraftCard>d__22 @0x49df7e0``: the prompt is forced when
    the played card is a Graft card or the space is reachable only with a
    partner (no plain variant here); otherwise ``GraftCardEvaluator`` answers
    nothing for a plain card and the empty answer plays it alone.
    """

    if not any(arg(action, "graft") is True for action in variants):
        return None
    if _is_graft_card(card_ref, run.ctx.seat):
        return True
    return not any(arg(action, "graft") is not True for action in variants)


def _store_graft_partner(run: DecisionRun, placement: DomainAction) -> None:
    """The partner ``GraftCardEvaluator`` picks for ``placement`` (state 50).

    Valued on the turn-time state (the app asks before the placement): each
    legal partner ``c`` at ``GraftCardsValue(A = c, B = played)``, first
    strictly best; a non-positive or empty answer of this forced prompt is
    ``DefaultRandomChoice`` (a random legal partner). The legal partners are
    our engine's for the placed state (judgement: the app's own filters
    ``b__0``/``b__1`` are the same rules). Stored for the ``graft_partner``
    window as ``(GRAFT_PARTNER_INTENT, round, played card) -> partner``, but
    only when that window will be asked: with a single legal partner the
    agent takes it without a handler, so nothing would ever drop the entry
    (the pick still runs, keeping the RNG draws the same).
    """

    card_ref = str_arg(placement, "card_id")
    space_id = str_arg(placement, "space_id")
    if card_ref is None or space_id is None:
        return
    seat = run.ctx.seat
    placed = apply_agent_action(run.ctx.state, placement).state
    partners = [
        ref
        for ref in (
            str_arg(action, "card_id")
            for action in legal_graft_partner_actions(placed, seat)
        )
        if ref is not None
    ]
    if not partners:
        return
    hand = set(run.ctx.hand)
    candidates = tuple(
        card_entity(ref, seat if ref in hand else None) for ref in partners
    )
    request = Request(infos=(TargetInfo(entities=candidates),), forced=True)
    answer = graft_card_evaluate(
        run.profile,
        request,
        card_entity(card_ref, seat),
        space_entity(space_id, run.ctx.board),
    )
    partner = _forced_pick(run, answer, partners)
    if len(partners) > 1:
        key = (GRAFT_PARTNER_INTENT, run.ctx.round_number, card_ref)
        run.memory.intents[key] = partner


# ---------------------------------------------------------------------------
# Playmat abilities offered at the turn start (Immortality)
# ---------------------------------------------------------------------------


def return_specimen_source(run: DecisionRun, action: DomainAction) -> Source:
    """``ReturnSpecimenAbility`` (playmat, Optional; spec immortality.md §3.4).

    E @0x4e1a610: only the troop shortfall (``UngainedTroops``) is returned,
    at 1.0; without one nothing is stored and the key is never chosen. One
    target per specimen (``infos[0].options``); our action returns one, so a
    shortfall of ``n`` is answered over ``n`` decisions.
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        ability = ability_for(_RETURN_SPECIMEN, track_entity("emperor"))
        specimens = tuple(range(run.ctx.specimens()))
        answer = ability.evaluate(
            run.profile, Request(infos=(TargetInfo(options=specimens),))
        )
        return answer.value, (None if answer.response is None else action)

    return Source("Return Specimen", Stage.PROMPT, (action,), evaluate=evaluate)


def family_atomics_source(run: DecisionRun, action: DomainAction) -> Source:
    """``FamilyAtomicsAbility`` (playmat, Optional; spec immortality.md §3.4).

    E @0x4dfd5f0 answers only in the seat's Reveal turn (``[decline,
    confirm]``, 1 = confirm): in a turn-start or Agent-turn prompt it stores
    nothing and the key is never chosen.
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        ability = ability_for(_FAMILY_ATOMICS, track_entity("emperor"))
        answer = ability.evaluate(
            run.profile, Request(infos=(TargetInfo(options=(0, 1)),))
        )
        response = answer.response
        confirmed = bool(response) and response is not None and response[0][:1] == (1,)
        return answer.value, (action if confirmed else None)

    return Source("Family Atomics", Stage.PROMPT, (action,), evaluate=evaluate)


def playmat_sources(run: DecisionRun) -> list[Source]:
    """The Immortality playmat keys of a turn-start or post-action prompt."""

    sources: list[Source] = []
    returned = run.first("return_specimen")
    if returned is not None:
        sources.append(return_specimen_source(run, returned))
    atomics = run.first("use_family_atomics")
    if atomics is not None:
        sources.append(family_atomics_source(run, atomics))
    return sources


# ---------------------------------------------------------------------------
# Sources: one per hand card with a legal placement
# ---------------------------------------------------------------------------


def _agent_ability(card_ref: str, seat: int) -> AgentAbility | None:
    """The card's ``AgentAbility``-family ability (MakeChoice's card route)."""

    for ability in abilities_of(card_entity(card_ref, seat)):
        if isinstance(ability, AgentAbility):
            return ability
    return None


def _card_evaluate(
    run: DecisionRun, card_ref: str, actions: Sequence[DomainAction]
) -> Callable[[], tuple[float, DomainAction | None]]:
    """``AgentAbility::Evaluate`` of one hand card over its legal spaces.

    The answer's space picks the representative action: the first legal
    ``agent_turn`` of (card, space); ``_realise`` settles its cost option and
    infiltrating Spy once the card has won.

    ``MakeChoice`` (02 §2, @0x48fef80) ranks the keys by value first and only
    then asks the best one for ``GetResponse`` (@0x4933e40); on this
    non-forced prompt a best key without a space answers the empty answer, so
    such an answer is a candidate whose action is ``reveal_turn``. The real
    ``AgentAbility::Evaluate`` never yields one: with no stored space its
    value is 0.
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        ability = _agent_ability(card_ref, run.ctx.seat)
        if ability is None:
            return 0.0, None
        discounts: dict[str | None, set[str | None]] = {}
        for action in actions:
            discounts.setdefault(str_arg(action, "space_id"), set()).add(
                str_arg(action, "discount")
            )
        board = run.ctx.board
        spaces = tuple(
            target
            for space_id in board_space_order(board)
            if space_id in discounts
            for target in _space_targets(space_id, board, discounts[space_id])
        )
        if not spaces:
            return 0.0, None
        answer = ability.evaluate(
            run.profile, Request(infos=(TargetInfo(entities=spaces),))
        )
        if not answer.response or not answer.response[0]:
            # GetResponse after MakeChoice picked this key: the empty answer.
            return answer.value, run.first("reveal_turn")
        space_id = answer.response[0][0]
        variants = [t for t in spaces if t.ref == space_id]
        discount = (
            _best_discount(run, ability, variants)
            if len(variants) > 1
            else _discount_of(variants[0])
            if variants
            else None
        )
        for action in actions:
            if (
                str_arg(action, "space_id") == space_id
                and str_arg(action, "discount") == discount
            ):
                return answer.value, action
        return answer.value, None

    return evaluate


def _discount_of(target: Entity) -> str | None:
    """The Navigation Chamber cut a target space carries (None: the plain
    space; ``space_with_cost_cut`` sets ``SpiceDiscount``/``SolariDiscount``)."""

    if target.int_attr("SpiceDiscount") < 0:
        return "spice"
    if target.int_attr("SolariDiscount") < 0:
        return "solari"
    return None


def _space_targets(
    space_id: str, board: Board, discounts: set[str | None]
) -> tuple[Entity, ...]:
    """The targets of one legal space: the space itself, or (Navigation
    Chamber, D60) one target per legal discount variant in our legal order
    (``_DISCOUNT_ORDER``). Without a discount variant this is the plain space
    alone, as before."""

    base = space_entity(space_id, board)
    return tuple(
        base if kind is None else space_with_cost_cut(base, kind)
        for kind in _DISCOUNT_ORDER
        if kind in discounts
    )


def _best_discount(
    run: DecisionRun, ability: AgentAbility, variants: Sequence[Entity]
) -> str | None:
    """Which Navigation Chamber variant of the chosen space won (D60).

    ``AgentAbility::Evaluate`` answers the space ref only; every variant
    shares it, so each variant is valued alone (the same loop on a one-space
    target list) and the first strictly best one, in target order, is the one
    the full evaluation kept.
    """

    best: tuple[float, str | None] | None = None
    for target in variants:
        answer = ability.evaluate(
            run.profile, Request(infos=(TargetInfo(entities=(target,)),))
        )
        if best is None or answer.value > best[0]:
            best = (answer.value, _discount_of(target))
    return None if best is None else best[1]


def _card_sources(run: DecisionRun) -> list[Source]:
    """One PROMPT source per hand card (instance) with ``agent_turn`` actions.

    Identical copies (two Daggers) are separate keys, as in the app, so
    ``MakeChoice``'s shuffle breaks their tie.
    """

    by_card: dict[str, list[DomainAction]] = {}
    for action in run.by_id("agent_turn"):
        card_ref = str_arg(action, "card_id")
        if card_ref is not None:
            by_card.setdefault(card_ref, []).append(action)
    return [
        Source(
            label=card_ref,
            stage=Stage.PROMPT,
            actions=tuple(actions),
            evaluate=_card_evaluate(run, card_ref, actions),
        )
        for card_ref, actions in by_card.items()
    ]


def _turn_start_card_sources(run: DecisionRun) -> list[Source] | None:
    """Litany Against Fear's turn-start play (bloodlines-cards.md §3.18, D11).

    One PROMPT key per ``play_turn_start_card(card_id)``: the card's
    ``LitanyTurnStartAbility`` (Optional, timing None) valued by its
    ``Evaluate`` (``CardDrawValueWithBuyGains`` + the reveal penalty), next to
    the placement and Plot keys of ``DetermineTurn``. None (not mirrored) for
    a card without that ability.
    """

    sources: list[Source] = []
    for action in run.by_id("play_turn_start_card"):
        ref = str_arg(action, "card_id")
        if ref is None or card_id(ref) not in CARD_ARCHETYPES:
            return None
        card = card_entity(ref, run.ctx.seat)
        ability = next(
            (a for a in abilities_of(card) if isinstance(a, LitanyTurnStartAbility)),
            None,
        )
        if ability is None:
            return None
        sources.append(
            Source(
                f"Turn start {ref}",
                Stage.PROMPT,
                (action,),
                _plain_evaluate(run, ability, action),
            )
        )
    return sources


def _plain_evaluate(
    run: DecisionRun, ability: Ability, action: DomainAction
) -> Callable[[], tuple[float, DomainAction | None]]:
    """An ability key with no targets: its ``Evaluate`` value, realised by
    ``action`` when the answer is "use" (a stored response)."""

    def evaluate() -> tuple[float, DomainAction | None]:
        answer = ability.evaluate(run.profile, Request())
        return answer.value, (None if answer.response is None else action)

    return evaluate


def tech_flip_sources(run: DecisionRun) -> list[Source] | None:
    """One PROMPT key per ``flip_tech(tech_id)`` (bloodlines-systems.md §3.3,
    §3.4; D23-D25): the tile's Flip ability (Optional) while its ``Cost``
    holds, valued by its ``Evaluate`` (100, or Rapid Dropships' deploy test).

    Shared by the turn-start prompt and the post-reveal prompt (the
    Agent-turn list is the agent_effects window's). None (not mirrored) for
    a tile without a Flip ability.
    """

    sources: list[Source] = []
    for action in run.by_id("flip_tech"):
        tech_id = str_arg(action, "tech_id")
        if tech_id is None or tech_id not in TECH_ARCHETYPES:
            return None
        tile = tech_entity(tech_id, run.ctx.seat)
        ability = next(
            (a for a in abilities_of(tile) if isinstance(a, _FLIP_ABILITIES)), None
        )
        if ability is None:
            return None
        if not ability.meets_cost(run.profile):
            continue  # ``CanBeRun`` fails: no key (our engine agrees)
        sources.append(
            Source(
                f"Flip {tech_id}",
                Stage.PROMPT,
                (action,),
                _plain_evaluate(run, ability, action),
            )
        )
    return sources


def tech_acquire_effect_sources(run: DecisionRun) -> list[Source] | None:
    """The owed acquire icons of a Tech tile bought in this turn (OQ-098).

    bloodlines-systems.md §3.1 / D15: the app resolves a tile's acquire
    effects at once, right after the purchase (``AcquireTechTile``), so they
    are an automatic stage (``Stage.IMMEDIATE``) taken in the engine's key
    order (our legal order). The first owed icon is realised here; a choice
    inside it is answered by its acquire ability: Memocorders' faction
    (``MemocordersAcquiredAbility::Evaluate``), Gene-Locked Vault's Intrigue
    or card (``GeneLockedVaultAcquiredAbility``, D19) and Forbidden Weapons'
    Shield Wall (destroyed iff ``ShouldBlowWall``, D20). A forced answer
    that names nothing legal is ``DefaultRandomChoice``. Empty when nothing
    is owed; None for an icon whose choice has no app answer here.
    """

    groups: dict[tuple[str, str], list[DomainAction]] = {}
    for action in run.by_id("resolve_tech_acquire_effect"):
        tech_id = str_arg(action, "tech_id")
        effect = str_arg(action, "effect")
        if tech_id is None or effect is None:
            return None
        groups.setdefault((tech_id, effect), []).append(action)
    if not groups:
        return []
    (tech_id, effect), actions = next(iter(groups.items()))
    chosen = _acquire_effect_action(run, tech_id, effect, actions)
    if chosen is None:
        return None
    return [Source(f"Tech acquire {tech_id} {effect}", Stage.IMMEDIATE, (chosen,))]


def _acquire_effect_action(
    run: DecisionRun, tech_id: str, effect: str, actions: Sequence[DomainAction]
) -> DomainAction | None:
    """The app's answer to one owed acquire icon (``tech_acquire_effect_sources``)."""

    if len(actions) == 1:
        return actions[0]
    if tech_id not in TECH_ARCHETYPES:
        return None
    tile = tech_entity(tech_id, run.ctx.seat)
    p = run.profile
    if effect == "influence":
        memocorders = next(
            (
                a
                for a in abilities_of(tile)
                if isinstance(a, MemocordersAcquiredAbility)
            ),
            None,
        )
        factions = [f for f in (str_arg(a, "faction") for a in actions) if f]
        if memocorders is None or len(factions) != len(actions):
            return None
        tracks = tuple(track_entity(f) for f in factions)
        request = Request(infos=(TargetInfo(entities=tracks),), forced=True)
        faction = _forced_pick(run, memocorders.evaluate(p, request), factions)
        return with_arg(actions, "faction", faction)
    if effect == "intrigue_or_card":
        vault = next(
            (
                a
                for a in abilities_of(tile)
                if isinstance(a, GeneLockedVaultAcquiredAbility)
            ),
            None,
        )
        if vault is None:
            return None
        options = list(_VAULT_CHOICES)
        request = Request(infos=(TargetInfo(options=tuple(options)),), forced=True)
        option = _forced_pick(run, vault.evaluate(p, request), options)
        return with_arg(actions, "choice", _VAULT_CHOICES[option])
    if effect == "shield_wall":
        destroy = p.should_blow_wall()
        for action in actions:
            if (arg(action, "destroy_shield_wall") is True) is destroy:
                return action
        return default_random_choice(list(actions), run.rng)
    return None


def turn_window(run: DecisionRun) -> DomainAction | None:
    """``DetermineTurn``: place an Agent, play a Plot, or Reveal (empty answer)."""

    if any(action.action_id not in _KNOWN_ACTION_IDS for action in run.legal):
        return None  # an id with no app key: fall back, never pass it over
    owed = tech_acquire_effect_sources(run)
    if owed is None:
        return None
    if owed:
        return decide(run, owed, skip=None)
    # ``place_track_spy`` is never a source. UNTRACED: 12 §1.3 finds nothing in
    # the playmat ability container (DetermineTurn row 4), while engine-order
    # §3.6 lists custom abilities there; a custom PlaceSpy (timing None) would
    # then be a turn-start key. The app's Emperor-4 Spy is taken to wait for
    # the post-action prompt, as the window brief rules.
    starts = _turn_start_card_sources(run)
    flips = tech_flip_sources(run)
    if starts is None or flips is None:
        return None
    sources = _card_sources(run)
    plots = run.by_id("play_intrigue")
    if plots:
        sources.extend(intrigue_play_sources(run, plots, combat=False))
    sources.extend(playmat_sources(run))
    sources.extend(starts)
    sources.extend(flips)
    chosen = decide(run, sources, skip=run.first("reveal_turn"), forced=False)
    if chosen is not None and chosen.action_id == "agent_turn":
        return _realise(run, chosen)
    return chosen


HANDLERS: dict[str, Handler] = {"turn": turn_window}
