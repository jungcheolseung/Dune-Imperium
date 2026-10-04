"""The spy, contract and misc decision windows of app_ai (``windows/uprising``).

Each window is reached in a real heuristic game (``play_until``), adjusted
with ``with_player``/``with_state`` where a branch needs it, and answered
through a ``DecisionRun`` exactly as ``AppAIAgent`` builds it. The expected
answers come from the profile's real values (printed next to each case).
"""

import math
import random
from collections import Counter
from collections.abc import Callable, Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai import windows as windows_package
from dune_imperium.agents.app_ai.abilities.base import Answer
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.data.constants import TABLES
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    play_until,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import handler_for
from dune_imperium.agents.app_ai.windows import intrigue as intrigue_window
from dune_imperium.agents.app_ai.windows import uprising as window
from dune_imperium.agents.app_ai.windows.common import Source
from dune_imperium.agents.app_ai.windows.intrigue import INTENT, INTENT_AT
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.agents.app_ai.windows.turn import board_space_order
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

KINDS = (
    "spy_placement",
    "contract_market",
    "contract_reward_spy",
    "contract_reward_recall",
    "opponent_card_discard",
    "long_live_fighters",
)

POST_EMPEROR = "emperor-sardaukar-dutiful-service"
POST_LANDSRAAD = "landsraad-high-council-imperial-privilege-swordmaster"
POST_ASSEMBLY = "landsraad-assembly-hall-gather-support"
POST_SHIPPING = "choam-shipping-accept-contract"
POST_BASIN = "arrakis-imperial-basin"
POST_DEEP = "arrakis-deep-desert"
POST_BG = "bene-gesserit-espionage-secrets"
POST_FREMEN = "fremen-desert-tactics-fremkit"


# -- helpers ---------------------------------------------------------------------------


def _first(
    kind: str, seed: int, more: Callable[[GameState, int], bool] | None = None
) -> GameState:
    return play_until(
        lambda s, o: s.decision_stack[-1].kind == kind and (more is None or more(s, o)),
        seed=seed,
        choam=True,
    )


def _owner(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _profile(state: GameState, seat: int, rng: random.Random) -> Profile:
    view = ENGINE.observe(state, seat)
    return Profile(AppContext(state, seat, view), TABLES[2], rng)


def _run(
    state: GameState,
    *,
    seed: int = 0,
    memory: Memory | None = None,
    patch: Callable[[Profile], None] | None = None,
) -> tuple[DecisionRun, tuple[DomainAction, ...]]:
    seat = _owner(state)
    legal = ENGINE.legal_actions(state, seat)
    rng = random.Random(seed)
    profile = _profile(state, seat, rng)
    if patch is not None:
        patch(profile)
    view = ENGINE.observe(state, seat)
    ctx = AppContext(state, seat, view)
    run = DecisionRun(ctx, profile, legal, rng, memory or Memory())
    return run, legal


def _answer(
    state: GameState,
    *,
    seed: int = 0,
    memory: Memory | None = None,
    patch: Callable[[Profile], None] | None = None,
) -> DomainAction | None:
    """The window's answer, checked to be legal."""

    run, legal = _run(state, seed=seed, memory=memory, patch=patch)
    handler = handler_for(state.decision_stack[-1].kind)
    assert handler is not None
    action = handler(run)
    assert action is None or action in legal
    return action


def _act(action_id: str, actor: int, **arguments: str) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=actor, arguments=tuple(arguments.items())
    )


def _occupy(state: GameState, me: int, free: set[str]) -> GameState:
    """Opponents' spies on every post that is not in ``free`` nor mine."""

    mine = set(state.players[me].spy_post_ids)
    fill = [
        p.post_id
        for p in OBSERVATION_POSTS
        if p.post_id not in free and p.post_id not in mine
    ]
    for seat in range(4):
        if seat == me:
            continue
        posts = tuple(fill[:3])
        fill = fill[3:]
        state = with_player(
            state, seat, spy_post_ids=posts, spies_supply=3 - len(posts)
        )
    assert not fill, "more posts than opponent spies"
    return state


def _market(
    state: GameState, face_up: tuple[str, ...], aside: tuple[str, ...] = ()
) -> GameState:
    """Put ``face_up`` in the row and ``aside`` aside; the rest in the bank."""

    pool = (
        *state.contract_bank,
        *state.face_up_contract_ids,
        *state.sardaukar_contract_ids,
    )
    return with_state(
        state,
        face_up_contract_ids=face_up,
        sardaukar_contract_ids=aside,
        contract_bank=tuple(c for c in pool if c not in face_up and c not in aside),
    )


def _with_top_context(state: GameState, **changes: ActionValue) -> GameState:
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    top = type(frame)(
        frame.kind, frame.frame_id, frame.decision, tuple(context.items())
    )
    return with_state(state, decision_stack=(*state.decision_stack[:-1], top))


# -- real states (heuristic games, CHOAM) ----------------------------------------------

# Round 7, seat 0 (Feyd), Emperor-4 track Spy, supply 3, no spy out. Post
# values: Emperor, Landsraad (High Council), BG, Fremen 2.0; the rest 0.0.
SPY = _first("spy_placement", 1)
# Seat 1 (Gurney), supply 3: Landsraad (High Council) 3.0, Fremen 3.0,
# Emperor/Guild/BG 2.0, Assembly Hall 1.0, the rest 0.0.
CONTRACT_SPY = _first("contract_reward_spy", 2)
# Seat 3 (Jessica), supply 0, spies on Fremen 5.0, Shipping 4.0, BG 6.0;
# empty Emperor post 7.0 (the best).
CONTRACT_SPY_RECALL = _first(
    "contract_reward_spy", 14, lambda s, o: s.players[o].spies_supply == 0
)
# Round 1, seat 0 (Feyd) at Dutiful Service: Arrakeen I 1.40625, Immediate 2.86.
MARKET = _first("contract_market", 1)
# Seat 3 completed Sardaukar II at Sardaukar: Arrakeen (combat, value 6.78)
# and Secrets (BG; seat 3 has 1, seat 2 has 4) are offered.
RECALL = _first(
    "contract_reward_recall", 7, lambda s, o: len(ENGINE.legal_actions(s, o)) > 1
)
# Seat 2, one Agent left, hand: Weirding Woman, Dune, Steersman, Dune, TSMF.
DISCARD = _first("opponent_card_discard", 7)
# Seat 1: top three Weirding Woman (1), Unswerving Loyalty (1), Signet Ring (0).
LLTF = _first("long_live_fighters", 1)


def test_handlers_are_registered() -> None:
    for kind in KINDS:
        assert handler_for(kind) is window.HANDLERS[kind]


# -- spy_placement ---------------------------------------------------------------------


def test_spy_placement_places_on_the_best_post() -> None:
    seat = _owner(SPY)
    # Free: Assembly Hall, Imperial Basin, Deep Desert 0.0; BG 2.0.
    state = _occupy(SPY, seat, {POST_ASSEMBLY, POST_BASIN, POST_BG, POST_DEEP})
    _, legal = _run(state)
    assert {a.action_id for a in legal} == {"place_spy_on_space"}
    assert _answer(state) == _act("place_spy_on_space", seat, post_id=POST_BG)


def test_spy_placement_breaks_ties_at_random() -> None:
    """``GetPostSelection`` shuffles before its stable sort: tied best posts
    (Emperor 2.0, BG 2.0) are both reachable."""

    seat = _owner(SPY)
    state = _occupy(SPY, seat, {POST_ASSEMBLY, POST_EMPEROR, POST_BG, POST_DEEP})
    picks = {_answer(state, seed=seed) for seed in range(12)}
    assert picks == {
        _act("place_spy_on_space", seat, post_id=POST_EMPEROR),
        _act("place_spy_on_space", seat, post_id=POST_BG),
    }


def test_spy_placement_with_an_empty_supply_recalls_the_worst_post_first() -> None:
    seat = _owner(SPY)
    # Own spies on Emperor (2.0), Assembly Hall (0.0), BG (2.0); free: Fremen
    # (2.0) and Deep Desert (0.0).
    state = with_player(
        SPY, seat, spies_supply=0, spy_post_ids=(POST_EMPEROR, POST_ASSEMBLY, POST_BG)
    )
    state = _occupy(state, seat, {POST_FREMEN, POST_DEEP})
    _, legal = _run(state)
    assert _act("decline_spy_placement", seat) in legal
    recall = _answer(state)
    assert recall == _act("recall_spy_for_placement", seat, post_id=POST_ASSEMBLY)
    # The window stays open with a Spy in supply: the placement follows.
    after = ENGINE.apply(state, recall).state
    assert after.decision_stack[-1].kind == "spy_placement"
    assert _answer(after) == _act("place_spy_on_space", seat, post_id=POST_FREMEN)


def test_spy_placement_with_an_unknown_action_is_not_mirrored() -> None:
    run, legal = _run(SPY)
    seat = _owner(SPY)
    odd = DecisionRun(
        run.ctx,
        run.profile,
        (*legal, _act("move_spy", seat)),
        run.rng,
        run.memory,
    )
    assert window.spy_placement(odd) is None


# -- contract_reward_spy ---------------------------------------------------------------


def test_contract_spy_places_on_the_best_post() -> None:
    seat = _owner(CONTRACT_SPY)
    # Fremen (3.0) taken by an opponent: Landsraad (3.0) is the unique best.
    state = _occupy(
        CONTRACT_SPY, seat, {POST_LANDSRAAD, POST_ASSEMBLY, POST_EMPEROR, POST_SHIPPING}
    )
    assert _answer(state) == _act("place_contract_spy", seat, post_id=POST_LANDSRAAD)


def test_contract_spy_tied_best_posts_are_both_reachable() -> None:
    seat = _owner(CONTRACT_SPY)
    picks = {_answer(CONTRACT_SPY, seed=seed) for seed in range(12)}
    assert picks == {
        _act("place_contract_spy", seat, post_id=POST_LANDSRAAD),
        _act("place_contract_spy", seat, post_id=POST_FREMEN),
    }


def test_contract_spy_with_an_empty_supply_never_declines() -> None:
    seat = _owner(CONTRACT_SPY_RECALL)
    _, legal = _run(CONTRACT_SPY_RECALL)
    assert _act("decline_contract_spy", seat) in legal
    recall = _answer(CONTRACT_SPY_RECALL)
    assert recall == _act("recall_spy_for_contract", seat, post_id=POST_SHIPPING)
    after = ENGINE.apply(CONTRACT_SPY_RECALL, recall).state
    assert after.decision_stack[-1].kind == "contract_reward_spy"
    assert _answer(after) == _act("place_contract_spy", seat, post_id=POST_EMPEROR)


# -- contract_market -------------------------------------------------------------------


def test_contract_market_takes_the_best_acquire_value() -> None:
    seat = _owner(MARKET)
    assert MARKET.face_up_contract_ids == ("contract:arrakeen_i", "contract:immediate")
    assert _answer(MARKET) == _act(
        "take_contract", seat, instance_id="contract:immediate"
    )


@pytest.mark.parametrize(
    "row",
    [
        ("contract:harvest_3", "contract:harvest_3_copy_2"),
        ("contract:harvest_3_copy_2", "contract:harvest_3"),
        ("contract:harvest_4", "contract:immediate"),  # both 2.86
        ("contract:immediate", "contract:harvest_4"),
    ],
)
def test_contract_market_keeps_the_first_strict_maximum(row: tuple[str, str]) -> None:
    seat = _owner(MARKET)
    state = _market(MARKET, row)
    assert _answer(state) == _act("take_contract", seat, instance_id=row[0])


def test_contract_market_scores_shaddams_set_aside_contracts_after_the_row() -> None:
    seat = _owner(MARKET)
    state = with_player(MARKET, seat, leader_id="shaddam_corrino_iv")
    # Heighliner II 0.2325, High Council I 0.645; set aside Sardaukar I 0.17,
    # Sardaukar II 1.17.
    state = _market(
        state,
        ("contract:heighliner_ii", "contract:high_council_i"),
        ("contract:sardaukar_i", "contract:sardaukar_ii"),
    )
    _, legal = _run(state)
    assert [dict(a.arguments)["instance_id"] for a in legal] == [
        "contract:heighliner_ii",
        "contract:high_council_i",
        "contract:sardaukar_i",
        "contract:sardaukar_ii",
    ]
    assert _answer(state) == _act(
        "take_contract", seat, instance_id="contract:sardaukar_ii"
    )


def _played(iid: str) -> tuple[GameState, int]:
    """MARKET opened by the play of Intrigue ``iid``: its ``intrigue_played``
    event and the market frame's source, as ``rules/intrigue.py`` writes
    them. Returns the state and the event's index (the intent stamp)."""

    seat = _owner(MARKET)
    play = f"round:1:player:{seat}:intrigue:{iid}"
    event = GameEvent(
        event_id=play,
        kind="intrigue_played",
        payload=(("card_id", iid), ("option", 0), ("player", seat)),
    )
    state = with_state(MARKET, event_log=(*MARKET.event_log, event))
    return _with_top_context(state, source=f"{play}:contract"), len(MARKET.event_log)


def _intents(iid: str, answer: Answer, stamp: int | None) -> Memory:
    memory = Memory()
    memory.intents[(INTENT, iid)] = answer
    memory.intents[(INTENT_AT, iid)] = stamp
    return memory


def test_contract_market_takes_the_contract_of_the_intrigue_answer() -> None:
    """Leverage's play already chose Arrakeen I (intrigues.md §7.15), though
    Immediate is worth more now."""

    iid = "intrigue:leverage:0"
    state, stamp = _played(iid)
    seat = _owner(state)
    answer = Answer(1.40625, (("contract:arrakeen_i",),), "Leverage")
    memory = _intents(iid, answer, stamp)
    assert _answer(state, memory=memory) == _act(
        "take_contract", seat, instance_id="contract:arrakeen_i"
    )
    # The intrigue windows own the keys: the answer stays.
    assert memory.intents[(INTENT, iid)] is answer


def test_contract_market_reads_the_contract_among_other_targets() -> None:
    """Reach Agreement answers ``[troops], [contract]`` (intrigues.md §6.12)."""

    iid = "intrigue:reach_agreement:1"
    state, stamp = _played(iid)
    seat = _owner(state)
    answer = Answer(1.0, ((0, 1), ("contract:arrakeen_i",)), "Reach Agreement")
    assert _answer(state, memory=_intents(iid, answer, stamp)) == _act(
        "take_contract", seat, instance_id="contract:arrakeen_i"
    )


@pytest.mark.parametrize(
    ("contract", "shift"),
    [
        ("contract:harvest_4", 0),  # names no offered contract
        ("contract:arrakeen_i", 1),  # evaluated for an earlier play (stale)
    ],
)
def test_contract_market_ignores_an_unusable_intent(contract: str, shift: int) -> None:
    iid = "intrigue:leverage:0"
    state, stamp = _played(iid)
    seat = _owner(state)
    answer = Answer(1.0, ((contract,),), "Leverage")
    memory = _intents(iid, answer, stamp - shift)
    assert _answer(state, memory=memory) == _act(
        "take_contract", seat, instance_id="contract:immediate"
    )


def test_contract_market_without_a_positive_answer_picks_at_random() -> None:
    """No contract beats ``-DBL_MAX`` (NaN values): the forced prompt's
    ``DefaultRandomChoice`` over every offered contract."""

    def nan_values(profile: Profile) -> None:
        def value(contract: Entity) -> Summer:
            s = Summer()
            s.add("NaN", math.nan)
            return s

        profile.contract_acquire_value = value  # type: ignore[method-assign]

    _, legal = _run(MARKET)
    for seed in range(4):
        expected = legal[random.Random(seed).randrange(len(legal))]
        assert _answer(MARKET, seed=seed, patch=nan_values) == expected


# -- contract_reward_recall ------------------------------------------------------------


def test_recall_takes_the_trailing_faction_space_over_a_combat_space() -> None:
    seat = _owner(RECALL)
    assert RECALL.players[seat].agent_locations == ("arrakeen", "secrets", "sardaukar")
    # Secrets: BG 1 vs 4 -> 75; Arrakeen: 50 - 6.78.
    assert _answer(RECALL) == _act(
        "recall_agent_for_contract", seat, space_id="secrets"
    )


def test_recall_prefers_a_factionless_non_combat_space() -> None:
    seat = _owner(RECALL)
    state = with_player(
        RECALL, seat, agent_locations=("assembly_hall", "secrets", "sardaukar")
    )
    assert _answer(state) == _act(
        "recall_agent_for_contract", seat, space_id="assembly_hall"
    )


def test_recall_otherwise_takes_the_lowest_space_value() -> None:
    seat = _owner(RECALL)
    # BG 3 vs 4: no longer trailing by 2. Secrets 50 - 4.75, Arrakeen
    # 50 - 4.0979: the lower-valued Arrakeen scores higher.
    state = with_player(
        RECALL,
        seat,
        influence=Influence(emperor=3, spacing_guild=1, bene_gesserit=3, fremen=2),
    )
    assert _answer(state) == _act(
        "recall_agent_for_contract", seat, space_id="arrakeen"
    )


def _recall_in_reverse_board_order() -> tuple[GameState, str, str]:
    """RECALL with Arrakeen and Secrets placed against the board order.

    Returns the state, the board-first and the board-second space.
    """

    order = board_space_order(True)
    first, second = sorted(("arrakeen", "secrets"), key=order.index)
    seat = _owner(RECALL)
    state = with_player(RECALL, seat, agent_locations=(second, first, "sardaukar"))
    offered = [
        a.arguments
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "recall_agent_for_contract"
    ]
    assert offered == [(("space_id", second),), (("space_id", first),)]
    return state, first, second


def test_recall_with_nothing_positive_takes_the_first_agent_in_board_order() -> None:
    """``GetRecallAgent`` returns null: ``?? agents.FirstOrDefault()`` over
    ``GetTargets`` = ``Board.Descendents`` order (space by space), not our
    placement order (the engine offers the second-placed Agent last)."""

    state, first, _ = _recall_in_reverse_board_order()
    seat = _owner(state)

    def high_values(profile: Profile) -> None:
        def value(space: Entity) -> Summer:
            s = Summer()
            s.add("High", 60.0)
            return s

        profile.space_value_for_player = value  # type: ignore[method-assign]

    # BG 3 vs 4: Secrets is no longer trailing; both 50 - 60 < 0.
    state = with_player(
        state,
        seat,
        influence=Influence(emperor=3, spacing_guild=1, bene_gesserit=3, fremen=2),
    )
    assert _answer(state, patch=high_values) == _act(
        "recall_agent_for_contract", seat, space_id=first
    )


def test_recall_hands_the_agents_to_get_recall_agent_in_board_order() -> None:
    """The shuffle's input list is ``GetTargets``' board order too."""

    seen: list[tuple[str, ...]] = []

    def record(profile: Profile) -> None:
        def recall_agent(agents: Sequence[Entity]) -> Entity | None:
            seen.append(tuple(a.ref for a in agents))
            return None

        profile.recall_agent = recall_agent  # type: ignore[method-assign]

    state, first, second = _recall_in_reverse_board_order()
    assert _answer(state, patch=record) == _act(
        "recall_agent_for_contract", _owner(state), space_id=first
    )
    assert seen == [(first, second)]


def test_board_order_keeps_unknown_spaces_last_in_offered_order() -> None:
    order = board_space_order(True)
    head, last = order[0], order[-1]
    assert window._in_board_order(["tueks_sietch", last, "x", head], True) == [
        head,
        last,
        "tueks_sietch",
        "x",
    ]


# -- opponent_card_discard -------------------------------------------------------------


def test_covert_operation_victim_discards_the_first_of_its_discard_order() -> None:
    seat = _owner(DISCARD)
    assert DISCARD.players[seat].agents_available == 1
    # Both Dunes lead (TrashValue 1.0); the stable sort keeps hand order.
    assert _answer(DISCARD) == _act(
        "discard_opponent_card",
        seat,
        card_id=f"player:{seat}:starter:dune_the_desert_planet:1",
    )


def _two_card_hand(agents: int) -> GameState:
    seat = _owner(DISCARD)
    player = DISCARD.players[seat]
    keep = ("imperium:steersman:0", "reserve:the_spice_must_flow:9")
    moved = tuple(c for c in player.hand if c not in keep)
    state = with_player(
        DISCARD, seat, hand=keep, discard_pile=(*player.discard_pile, *moved)
    )
    if agents == 0:
        state = with_player(
            state,
            seat,
            agents_available=0,
            agent_locations=(*player.agent_locations, "shipping"),
        )
    return state


@pytest.mark.parametrize(
    ("agents", "card"),
    [(1, "imperium:steersman:0"), (0, "reserve:the_spice_must_flow:9")],
)
def test_covert_operation_victim_orders_by_its_own_agents(
    agents: int, card: str
) -> None:
    """With an Agent left the key is led by 100 x cost (Steersman first);
    without one by 100 x reveal value (The Spice Must Flow first)."""

    state = _two_card_hand(agents)
    seat = _owner(state)
    assert _answer(state) == _act("discard_opponent_card", seat, card_id=card)


def test_choose_discard_evaluator_with_nothing_to_pick() -> None:
    profile = _profile(DISCARD, _owner(DISCARD), random.Random(0))
    assert window.choose_discard_evaluate(profile, [], 1) == Answer(
        0.0, None, "ChooseDiscardEvaluator | nothing"
    )


# -- long_live_fighters ----------------------------------------------------------------


def _deck_top(state: GameState, top: tuple[str, ...]) -> GameState:
    seat = _owner(state)
    deck = state.players[seat].deck
    assert set(top) <= set(deck)
    return with_player(state, seat, deck=(*top, *(c for c in deck if c not in top)))


def test_lltf_draw_trashes_the_cheapest_when_nothing_is_junk() -> None:
    """No TrashValue among the three: ``GetCardToTrash`` returns null and the
    cheapest (Signet Ring) is set aside; the first of the two cost-1 cards is
    drawn, the other discarded."""

    seat = _owner(LLTF)
    draw = _answer(LLTF)
    assert draw == _act(
        "select_long_live_fighters_draw", seat, card_id="imperium:weirding_woman:0"
    )
    after = ENGINE.apply(LLTF, draw).state
    assert _answer(after) == _act(
        "select_long_live_fighters_discard",
        seat,
        card_id="imperium:unswerving_loyalty:0",
    )


def test_lltf_draw_uses_get_card_to_trash() -> None:
    """Signet Ring (0), Dagger (0, TrashValue 1.0), Convincing Argument (0,
    TrashValue 0.25): Dagger is the trash card, so the first remaining 0-cost
    card (Signet Ring) is drawn — the cheapest-card fallback would have set
    the Signet Ring aside instead."""

    seat = _owner(LLTF)
    signet = f"player:{seat}:starter:signet_ring:0"
    dagger = f"player:{seat}:starter:dagger:1"
    argument = f"player:{seat}:starter:convincing_argument:0"
    state = _deck_top(LLTF, (signet, dagger, argument))
    draw = _answer(state)
    assert draw == _act("select_long_live_fighters_draw", seat, card_id=signet)
    after = ENGINE.apply(state, draw).state
    assert _answer(after) == _act(
        "select_long_live_fighters_discard", seat, card_id=argument
    )


def test_lltf_draw_takes_the_most_expensive_remaining_card() -> None:
    seat = _owner(LLTF)
    state = _deck_top(
        LLTF,
        (
            "imperium:unswerving_loyalty:0",
            "imperium:maula_pistol:1",
            f"player:{seat}:starter:dagger:1",
        ),
    )
    assert _answer(state) == _act(
        "select_long_live_fighters_draw", seat, card_id="imperium:maula_pistol:1"
    )


def test_lltf_draw_skips_the_spice_must_flow() -> None:
    """The most expensive remaining card costs >= 9: the cheaper is drawn."""

    seat = _owner(LLTF)
    tsmf = "reserve:the_spice_must_flow:9"
    pino = "imperium:price_is_no_object:0"
    holder = next(p for p in LLTF.players if tsmf in p.discard_pile)
    swapped = with_player(
        LLTF,
        holder.player_id,
        discard_pile=tuple(pino if c == tsmf else c for c in holder.discard_pile),
    )
    deck = swapped.players[seat].deck
    swapped = with_player(
        swapped, seat, deck=tuple(tsmf if c == pino else c for c in deck)
    )
    # The Spice Must Flow (9) took Price is No Object's place in the deck.
    paracompass = "imperium:paracompass:0"  # cost 4
    state = _deck_top(swapped, (tsmf, paracompass, f"player:{seat}:starter:dagger:1"))
    assert _answer(state) == _act(
        "select_long_live_fighters_draw", seat, card_id=paracompass
    )


# -- coverage: full games of four app_ai seats -----------------------------------------


@pytest.fixture
def intrigue_plays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tolerate the shared ``intrigue_play_sources`` while it is unported.

    Another window module implements it; until then its ``NotImplementedError``
    is read as "no intrigue source" so full games still exercise these
    windows. Once implemented, the real function runs unchanged.
    """

    original = intrigue_window.intrigue_play_sources

    def tolerant(
        run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
    ) -> list[Source]:
        try:
            return original(run, actions, combat=combat)
        except NotImplementedError:
            return []

    for module in vars(windows_package).values():
        if getattr(module, "intrigue_play_sources", None) is original:
            monkeypatch.setattr(module, "intrigue_play_sources", tolerant)


@pytest.mark.usefixtures("intrigue_plays")
@pytest.mark.parametrize(
    ("choam", "seed"), [(c, s) for c in (False, True) for s in (1, 2, 3)]
)
def test_full_games_never_fall_back_in_these_windows(choam: bool, seed: int) -> None:
    leaders = tuple(
        random.Random(seed).sample(
            [leader.leader_id for leader in leaders_for_choam(choam)], k=4
        )
    )
    engine = UprisingRulesEngine(leader_ids=leaders)
    agents = tuple(AppAIAgent(seed=10 * seed + seat) for seat in range(4))
    result = run_policy_game(engine, RulesetConfig(choam_module=choam), seed, agents)
    assert result.state.phase is GamePhase.FINISHED
    fallbacks: Counter[str] = Counter()
    mirrored: Counter[str] = Counter()
    for agent in agents:
        fallbacks.update(agent.fallbacks)
        mirrored.update(agent.mirrored)
    assert not {kind: n for kind, n in fallbacks.items() if kind in KINDS}
    if choam:
        assert mirrored["contract_market"] > 0
