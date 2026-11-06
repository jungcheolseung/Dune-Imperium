"""Immortality rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from dataclasses import replace

from tests.support.reward_windows import settle_reward_window
from tests.unit.rules.test_tleilaxu_row import (
    CONTAMINATOR,
    FROM_THE_TANKS,
    SUBJECT,
    _owner,
    _reveal_state,
)

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.registry.imperium import imperium_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.acquisition import legal_imperium_acquisitions
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.combat import (
    legal_combat_reward_influence_actions,
    resolve_combat_rewards,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind, top_frame

IMMORTALITY = RulesetConfig(immortality=True)


def _seat(seat: int, **changes: object) -> PlayerState:
    player = PlayerState(
        player_id=seat, research_space=RESEARCH_START_ID, family_atomics=True
    )
    return replace(player, **changes)  # type: ignore[arg-type]


def test_any_faction_influence_never_offers_the_tleilaxu_track() -> None:
    """A "choose a Faction" Influence choice offers the four Factions only.

    docs/rules/immortality.md: "Bene Tleilax는 Faction이 아니다. "아무
    Faction의 Influence"를 주는 효과로 Tleilaxu track을 전진할 수 없다."
    `[FAQ p. 4]`
    """

    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=tuple(
            _seat(seat, combat_strength=strength)
            for seat, strength in enumerate((8, 6, 4, 0))
        ),
        # Skirmish (Crysknife)'s 1st reward: one Influence of any Faction.
        current_conflict_ids=("skirmish_crysknife",),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
        tleilaxu_row=(CONTAMINATOR, SUBJECT),
        tleilaxu_deck=(FROM_THE_TANKS,),
        tleilaxu_track_spice=2,
    )
    opened = settle_reward_window(resolve_combat_rewards(state).state)
    frame = top_frame(opened)
    assert frame is not None and frame.kind == FrameKind.COMBAT_REWARD_INFLUENCE

    offered = {
        dict(action.arguments)["faction"]
        for action in legal_combat_reward_influence_actions(opened, 0)
    }

    assert offered == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}


def _with_persuasion(state: GameState, persuasion: int) -> GameState:
    frame = state.decision_stack[-1]
    assert frame.kind == "reveal"
    context = dict(frame.context)
    context["persuasion"] = persuasion
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(context.items())),
        ),
    )


def test_persuasion_buys_from_the_imperium_row_never_from_the_tleilaxu_row() -> None:
    """Persuasion acquisitions reach the Imperium Row, not the Tleilaxu Row.

    docs/rules/immortality.md: "Imperium Row에서 카드를 acquire하는 효과로는
    Tleilaxu 카드를 acquire할 수 없고, Persuasion 비용을 참조·수정하는 효과도
    쓸 수 없다." `[Immortality p. 9]`
    """

    state = _with_persuasion(_reveal_state(_owner()), 30)

    bought = {
        str(dict(action.arguments)["instance_id"])
        for action in legal_imperium_acquisitions(state, 0)
    }

    assert bought == set(state.imperium_row)
    assert not bought & set(state.tleilaxu_row)


def test_price_is_no_object_cannot_take_a_tleilaxu_card() -> None:
    """Price is No Object's acquisition skips the Tleilaxu Row.

    docs/rules/immortality.md: "Imperium Row에서 카드를 acquire하는 효과로는
    Tleilaxu 카드를 acquire할 수 없고, Persuasion 비용을 참조·수정하는 효과도
    쓸 수 없다." `[Immortality p. 9]`; Price is No Object acquires "Imperium
    Row 또는 Reserve의 card 하나를 Persuasion 대신 같은 양의 Solari로"
    (docs/rules/player-turns.md, `[Price is No Object card]`).
    """

    instances = imperium_deck_instance_ids(False)
    price = next(card for card in instances if ":price_is_no_object:" in card)
    others = tuple(card for card in instances if card != price)
    state = GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(
            _seat(0, hand=(price,), resources=Resources(solari=20)),
            *(_seat(seat) for seat in range(1, 4)),
        ),
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
        imperium_row=others[:5],
        imperium_deck=others[5:20],
        tleilaxu_row=(CONTAMINATOR, SUBJECT),
        tleilaxu_deck=(FROM_THE_TANKS,),
        tleilaxu_track_spice=2,
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    agent = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "dutiful_service"
    )
    placed = apply_agent_action(state, agent).state
    engine = UprisingRulesEngine()

    named = {
        str(dict(action.arguments)[key])
        for action in engine.whole_actions(placed, 0)
        for key in ("instance_id", "card_id")
        if key in dict(action.arguments)
    }

    assert set(placed.imperium_row) <= named
    assert not named & set(placed.tleilaxu_row)
    # Taking a row card works as without Immortality.
    take = next(
        action
        for action in engine.whole_actions(placed, 0)
        if dict(action.arguments).get("instance_id") == placed.imperium_row[0]
    )
    taken = apply_whole(engine, placed, take).state
    assert placed.imperium_row[0] in taken.players[0].hand
