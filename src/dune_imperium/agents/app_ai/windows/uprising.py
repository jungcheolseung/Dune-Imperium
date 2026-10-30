"""Spy, contract and misc windows.

``spy_placement``, ``contract_market``, ``contract_reward_*``,
``opponent_card_discard``, ``long_live_fighters``.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.

Every window here is one frame of ours that corresponds to one app prompt
the app engine raises while an action runs (it is never one of several
sources competing in a turn prompt), so each handler evaluates a single app
source (``common.decide`` with one PROMPT source; the app prompt is forced,
so a value of 0 or less means ``DefaultRandomChoice`` over every legal
answer) or answers through the shared spy evaluators:

- ``spy_placement`` and ``contract_reward_spy``: the ``actions.Uprising.
  PlaceSpy`` action's two prompts, ``RecallSpyEvaluator`` (forced recall of
  the spy on the worst post when the supply is empty) then
  ``PlaceSpyEvaluator`` (``GetBestPost``, ``UnseenNetwork`` false), via
  ``common.spy_answer``. The app never declines (``R6`` §1, §16).
- ``contract_market``: ``GainContractAbility.ContractEvaluate(forced=true)``
  (``spec/board.md`` §3.3) over ``GetContractOptions`` = the face-up row then
  Shaddam's set-aside Sardaukar contracts (§3.7; our ``take_contract`` list
  has the same order). An Intrigue card the app plays with its contract
  already chosen (Leverage, Reach Agreement) leaves that answer in
  ``run.memory.intents[("intrigue", <intrigue instance id>)]``
  (``windows/intrigue.py``); the market uses it when it is fresh.
- ``contract_reward_recall``: ``RecallAgentContractAbility::Evaluate``
  (``abilities/board.py``) over the offered Agents in board order.
- ``opponent_card_discard``: each victim's ``ChooseDiscardEvaluator::
  Evaluate`` (``spec/profile-economy.md`` §12.2) with
  ``spacingGuildBonus = false``; a victim with an empty hand, which the app
  never asks, confirms (OQ-138).
- ``long_live_fighters``: the draw prompt = ``LongLiveTheFightersAbility::
  Evaluate``, the discard prompt = ``LongLiveTheFightersEvaluator::Evaluate``
  (``abilities/imperium_a.py``; ``R6`` §12: our two steps are the app's two
  prompts in the same order).

A legal action id outside a window's known core ids (an expansion's) makes
the handler return None: those situations are not mirrored.
"""

import re
from collections.abc import Callable, Sequence

from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.board import RecallAgentContractAbility
from dune_imperium.agents.app_ai.abilities.generic import contract_evaluate
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    LongLiveTheFightersAbility,
    LongLiveTheFightersEvaluator,
)
from dune_imperium.agents.app_ai.abilities.original_imperium import (
    TestOfHumanityDeferredAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    agent_entity,
    card_entity,
    contract_entity,
)
from dune_imperium.agents.app_ai.context import Board, card_id
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.windows.common import (
    Source,
    Stage,
    decide,
    spy_answer,
    str_arg,
    with_arg,
)
from dune_imperium.agents.app_ai.windows.intrigue import (
    INTENT,
    INTENT_AT,
    play_event_index,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.core.actions import DomainAction

# The only Uprising contract whose reward recalls an Agent (ContractBase_13).
_SARDAUKAR_II = "contract:sardaukar_ii"
# ``rules/intrigue.py``'s play source: ``round:<n>:player:<seat>:intrigue:<iid>``.
_INTRIGUE_SOURCE = re.compile(r":intrigue:(intrigue:[^:]+:\d+)")


def _known_only(run: DecisionRun, ids: frozenset[str]) -> bool:
    """Whether every legal action is one of the window's core action ids."""

    return all(action.action_id in ids for action in run.legal)


def _single_ref(answer: Answer) -> str | int | None:
    """The one target an app answer names (``((ref,),)``), if any."""

    if not answer.response or not answer.response[0]:
        return None
    return answer.response[0][0]


def _one_source(
    run: DecisionRun,
    label: str,
    actions: Sequence[DomainAction],
    arg_name: str,
    answer: Callable[[], Answer],
) -> DomainAction | None:
    """A forced app prompt with a single source, mapped to our actions.

    The source's answer names one target (``arg_name`` of an action). The
    prompt is forced: with no positive answer ``MakeChoice`` falls back to
    ``DefaultRandomChoice`` ("a random key with random legal targets",
    spec/engine-order.md §0), i.e. a random action of the window.
    """

    def evaluate() -> tuple[float, DomainAction | None]:
        app = answer()
        ref = _single_ref(app)
        action = None if ref is None else with_arg(actions, arg_name, ref)
        return app.value, (action if app.value > 0.0 else None)

    source = Source(label, Stage.PROMPT, tuple(actions), evaluate)
    return decide(run, [source], skip=None, forced=True)


def _request(entities: Sequence[Entity]) -> Request:
    """A forced one-of-N prompt over ``entities`` (one target info)."""

    info = TargetInfo(entities=tuple(entities), min_select=1, max_select=1, forced=True)
    return Request(infos=(info,), forced=True)


# -- spies ----------------------------------------------------------------------------

_SPY_PLACEMENT_IDS = frozenset(
    {"place_spy_on_space", "recall_spy_for_placement", "decline_spy_placement"}
)
_CONTRACT_SPY_IDS = frozenset(
    {"place_contract_spy", "recall_spy_for_contract", "decline_contract_spy"}
)


def spy_placement(run: DecisionRun) -> DomainAction | None:
    """``spy_placement`` (Emperor-4 track Spy, In High Places' Agent box).

    App: ``actions.Uprising.PlaceSpy`` — ``RecallSpyEvaluator`` (with an
    empty supply, the spy on the worst post; the app never declines) then
    ``PlaceSpyEvaluator`` = ``GetBestPost(posts, UnseenNetwork=false)``
    (leaders.md, ``PlaceSpy/<SelectPost>d__20 @0x4a59d70``;
    ``PlaceSpyEvaluator::Evaluate @0x49319f0``).
    """

    if not _known_only(run, _SPY_PLACEMENT_IDS):
        return None
    return spy_answer(
        run,
        run.by_id("place_spy_on_space"),
        run.by_id("recall_spy_for_placement"),
        run.first("decline_spy_placement"),
    )


def contract_reward_spy(run: DecisionRun) -> DomainAction | None:
    """``contract_reward_spy`` (Arrakeen II, Research Station I).

    App: ``PlaceSpyContractAbility`` (Explicit, ``Evaluate @0x4d5a300`` =
    ``SpyValue``, empty response) whose ``PlaceSpy`` action asks the same two
    prompts as ``spy_placement``.
    """

    if not _known_only(run, _CONTRACT_SPY_IDS):
        return None
    return spy_answer(
        run,
        run.by_id("place_contract_spy"),
        run.by_id("recall_spy_for_contract"),
        run.first("decline_contract_spy"),
    )


# -- contracts ------------------------------------------------------------------------

_CONTRACT_MARKET_IDS = frozenset({"take_contract"})
_CONTRACT_RECALL = "recall_agent_for_contract"
# An earlier turn's Into the Fray Agent in the Conflict (OQ-037 (d), OQ-068).
_CONTRACT_RECALL_CONFLICT = "recall_conflict_agent_for_contract"
_CONTRACT_RECALL_IDS = frozenset({_CONTRACT_RECALL, _CONTRACT_RECALL_CONFLICT})
_CONFLICT_AGENT = "conflict"


def _intrigue_contract_intent(run: DecisionRun, offered: Sequence[str]) -> str | None:
    """The contract an app Intrigue answer already chose for this market.

    Leverage (``BaseSet.LeverageAbility::Evaluate @0x4cc90b0``) and Reach
    Agreement (``Uprising.ReachAgreementAbility::Evaluate @0x4c4a690``) pick
    their contract inside the play's single answer (intrigues.md §7.15,
    §6.12), before our engine pays Leverage's Solari or Reach Agreement's
    retreat. ``windows/intrigue.py`` records that answer under
    ``(INTENT, <intrigue instance id>)`` with the event-log stamp
    ``(INTENT_AT, <id>)``; the market frame's ``source`` names the playing
    card. The answer counts only when its stamp is the index of the card's
    latest ``intrigue_played`` event (it was evaluated for this very play)
    and it names exactly one offered contract. It is left in memory for the
    intrigue windows, which own those keys.
    """

    source = run.ctx.top_frame_context.get("source")
    if not isinstance(source, str):
        return None
    match = _INTRIGUE_SOURCE.search(source)
    if match is None:
        return None
    instance = match.group(1)
    stored = run.memory.intents.get((INTENT, instance))
    stamp = run.memory.intents.get((INTENT_AT, instance))
    if not isinstance(stored, Answer) or stamp is None:
        return None
    if stamp != play_event_index(run.ctx, instance):
        return None
    named = list(
        dict.fromkeys(
            ref
            for item in stored.response or ()
            for ref in item
            if isinstance(ref, str) and ref in offered
        )
    )
    return named[0] if len(named) == 1 else None


def contract_market(run: DecisionRun) -> DomainAction | None:
    """``contract_market``: which contract a Contract icon takes.

    App: ``GainContractAbility::ContractEvaluate @0x4d127b0`` with
    ``forced = true`` (``GainContractAbility``, ``GainContractCustomAbility``,
    Delivery Agreement's dependent pick (imperium-a §5 UNTRACED, most likely
    reading), Interstellar Trade's acquire box), i.e. ``GetBestContract
    @0x491cf10``: ``AcquireValue`` in ``GetContractOptions`` order, first
    strict maximum, a forced pick worth <= 0 reported at 1.0 (spec/board.md
    §3.3). Shaddam's set-aside Sardaukar contracts follow the row in both
    engines (board.md §3.7, leaders.md §11.1). Our engine offers no decline
    here, so Leverage's ``forced = false`` (whose answer is taken from the
    play's intent when the app played it) is evaluated forced when no fresh
    intent exists: the app only plays Leverage with a best value > 0, where
    both flags pick the same first strict maximum.
    """

    if not _known_only(run, _CONTRACT_MARKET_IDS):
        return None
    takes = run.by_id("take_contract")
    offered = [str_arg(a, "instance_id") for a in takes]
    ids = [i for i in offered if i is not None]
    intended = _intrigue_contract_intent(run, ids)
    if intended is not None:
        return with_arg(takes, "instance_id", intended)
    seat = run.ctx.seat
    contracts = [contract_entity(i, seat) for i in ids]
    profile: Profile = run.profile
    return _one_source(
        run,
        "GainContract",
        takes,
        "instance_id",
        lambda: contract_evaluate(profile, _request(contracts), True),
    )


def _in_board_order(spaces: Sequence[str], board: Board) -> list[str]:
    """``spaces`` in ``Board.Descendents`` order.

    ``Entity::buildDescendents @0x9a3ab0`` is a depth-first preorder
    (``[self]`` then each child's descendents, in ``children`` order), so the
    Agents under the Board come space by space in ``Board.children`` order
    (``turn.board_space_order``, whose reflection order is UNTRACED there,
    engine-order §9). A space outside that order (no app
    archetype) keeps its offered position after every known space (stable
    sort); our engine has at most one Agent of a seat per offered space.
    """

    order = {space_id: i for i, space_id in enumerate(board_space_order(board))}
    return sorted(spaces, key=lambda s: order.get(s, len(order)))


def contract_reward_recall(run: DecisionRun) -> DomainAction | None:
    """``contract_reward_recall`` (Sardaukar II's "recall one other Agent").

    App: ``RecallAgentContractAbility::Evaluate @0x4d5c140`` —
    ``GetRecallAgent(agents) ?? agents[0]`` (shuffles a copy; spec
    profile-influence-uprising §7.2, board.md §3.3) at
    ``RecallAgentValue + 1.0``. The targets are ``GetTargets @0x4d5bde0`` =
    ``Board.Descendents.OfType<WormAgent>().Where(b__0)``, with ``b__0
    @0x4d5c470`` = ``a.OwningPlayer == player && !a.Disabled && a.entityID
    != player.AgentEntityPlayedThisTurn``: the seat's Agents on the board
    except this turn's one, which is what our engine offers [Main p. 20].
    They are taken in board order (``_in_board_order``), not our
    ``agent_locations`` (placement) order: that order is what both the
    shuffle's input and the ``?? agents[0]`` fallback read.

    An earlier turn's Into the Fray Agent in the Conflict comes after the
    board's Agents, as in ``RecallAgentAbility``'s targets
    (``agent_effects._recall_request``; bloodlines-systems.md §8, D55).
    """

    if not _known_only(run, _CONTRACT_RECALL_IDS):
        return None
    recalls = run.by_id(_CONTRACT_RECALL)
    conflict = run.first(_CONTRACT_RECALL_CONFLICT)
    seat = run.ctx.seat
    offered = [str_arg(a, "space_id") for a in recalls]
    spaces = _in_board_order([s for s in offered if s is not None], run.ctx.board)
    agents = [agent_entity(s, seat) for s in spaces]
    if conflict is not None:
        agents.append(agent_entity(_CONFLICT_AGENT, seat))
    ability = RecallAgentContractAbility(contract_entity(_SARDAUKAR_II, seat))
    profile: Profile = run.profile
    if conflict is None:
        return _one_source(
            run,
            "RecallAgentContract",
            recalls,
            "space_id",
            lambda: ability.evaluate(profile, _request(agents)),
        )

    def evaluate() -> tuple[float, DomainAction | None]:
        app = ability.evaluate(profile, _request(agents))
        ref = _single_ref(app)
        action = (
            conflict
            if ref == _CONFLICT_AGENT
            else (None if ref is None else with_arg(recalls, "space_id", ref))
        )
        return app.value, (action if app.value > 0.0 else None)

    source = Source(
        "RecallAgentContract", Stage.PROMPT, (*recalls, conflict), evaluate
    )
    return decide(run, [source], skip=None, forced=True)


# -- Covert Operation victims ---------------------------------------------------------

_OPPONENT_DISCARD = "discard_opponent_card"
# A victim with an empty hand confirms it discards nothing (OQ-138); the app
# asks no such seat, so the confirm, always offered alone, is the answer.
_OPPONENT_DISCARD_CONFIRM = "resolve_opponent_discard_without_card"
_OPPONENT_DISCARD_IDS = frozenset({_OPPONENT_DISCARD, _OPPONENT_DISCARD_CONFIRM})
# The original Test of Humanity's victim may lose a deployed troop instead
# (the frame's ``or_lose_deployed_troop``).
_LOSE_UNIT = "lose_unit"


def choose_discard_evaluate(p: Profile, cards: Sequence[Entity], n: int) -> Answer:
    """``ChooseDiscardEvaluator::Evaluate @0x492dfe0`` (profile-economy §12.2).

    ``order = GetDiscardOrder(player, targets, spacingGuildBonus=false)``,
    pick its first ``n`` (``Forced ? NumberToSelect : MinimumToSelect``: 1
    for Covert Operation) at value 1.0 (literal); an empty pick leaves the
    choice unset (value 0).
    """

    pick = p.discard_order(list(cards), False)[:n]
    if not pick:
        return Answer(0.0, None, "ChooseDiscardEvaluator | nothing")
    refs = tuple(card.ref for card in pick)
    return Answer(1.0, (refs,), f"ChooseDiscardEvaluator | discarding {refs}")


def opponent_card_discard(run: DecisionRun) -> DomainAction | None:
    """``opponent_card_discard``: a Covert Operation victim's discard.

    App: ``CovertOperationAbility`` attaches ``ChooseDiscardEvaluator`` to
    each opponent's discard prompt; the victim's own profile answers it
    (``R6`` §13). Targets: the victim's hand in hand order (stable sort ties).
    A victim with an empty hand is asked too (OQ-138) and only confirms
    (``resolve_opponent_discard_without_card``, offered alone).
    """

    lose = run.first(_LOSE_UNIT)
    if lose is not None:
        choice = _test_of_humanity_choice(run)
        if choice is None:
            return None
        if choice == 1 or not run.by_id(_OPPONENT_DISCARD):
            return lose
    elif not _known_only(run, _OPPONENT_DISCARD_IDS):
        return None
    discards = run.by_id(_OPPONENT_DISCARD)
    if not discards:
        return run.first(_OPPONENT_DISCARD_CONFIRM)
    seat = run.ctx.seat
    ids = [str_arg(a, "card_id") for a in discards]
    cards = [card_entity(i, seat) for i in ids if i is not None]
    profile: Profile = run.profile
    return _one_source(
        run,
        "ChooseDiscardEvaluator",
        discards,
        "card_id",
        lambda: choose_discard_evaluate(profile, cards, 1),
    )


def _test_of_humanity_choice(run: DecisionRun) -> int | None:
    """The victim's "discard a card or lose a deployed troop" of the original
    Test of Humanity: ``TestOfHumanityDeferredAbility::
    EvaluateResolutionChoice`` on the victim's own profile (0 discard, 1
    troop). None when the frame is not that card's."""

    if not _known_only(run, _OPPONENT_DISCARD_IDS | {_LOSE_UNIT}):
        return None
    source = run.ctx.top_frame_context.get("covert_operation_card_id")
    if not isinstance(source, str) or card_id(source) != "test_of_humanity":
        return None
    owner = card_entity(source, None)
    answer = TestOfHumanityDeferredAbility(owner).evaluate_resolution_choice(
        run.profile
    )
    item = answer.response[0] if answer.response else ()
    return 1 if item and item[0] == 1 else 0


# -- Long Live the Fighters ----------------------------------------------------------

_LLTF_DRAW = "select_long_live_fighters_draw"
_LLTF_DISCARD = "select_long_live_fighters_discard"
_LLTF_IDS = frozenset({_LLTF_DRAW, _LLTF_DISCARD})


def long_live_fighters(run: DecisionRun) -> DomainAction | None:
    """``long_live_fighters``: draw one of the top three, then discard one.

    App (``R6`` §12, imperium-a §2.26, 17 §6 + Errata): the draw prompt is
    answered by ``LongLiveTheFightersAbility::Evaluate @0x4d22670`` over the
    top three cards (deck order), the discard prompt by
    ``LongLiveTheFightersEvaluator::Evaluate @0x4931710`` over the two left;
    the last card is trashed. Each prompt recomputes ``GetTrashCard`` (as
    the app does). The card ids come from our legal actions, which show the
    owner the top three cards.
    """

    draws = run.by_id(_LLTF_DRAW)
    discards = run.by_id(_LLTF_DISCARD)
    if (draws and discards) or not _known_only(run, _LLTF_IDS):
        return None
    seat = run.ctx.seat
    actions = draws or discards
    ids = [str_arg(a, "card_id") for a in actions]
    cards = [card_entity(i, seat) for i in ids if i is not None]
    profile: Profile = run.profile
    if draws:
        # The ability's owner (the played card) is not read by its Evaluate.
        source_card = run.ctx.top_frame_context.get("source_card_id")
        if not isinstance(source_card, str):
            return None
        ability = LongLiveTheFightersAbility(card_entity(source_card, seat))
        return _one_source(
            run,
            "LongLiveTheFighters",
            draws,
            "card_id",
            lambda: ability.evaluate(profile, _request(cards)),
        )
    return _one_source(
        run,
        "LongLiveTheFightersEvaluator",
        discards,
        "card_id",
        lambda: LongLiveTheFightersEvaluator.evaluate(profile, _request(cards)),
    )


HANDLERS: dict[str, Handler] = {
    "spy_placement": spy_placement,
    "contract_market": contract_market,
    "contract_reward_spy": contract_reward_spy,
    "contract_reward_recall": contract_reward_recall,
    "opponent_card_discard": opponent_card_discard,
    "long_live_fighters": long_live_fighters,
}
