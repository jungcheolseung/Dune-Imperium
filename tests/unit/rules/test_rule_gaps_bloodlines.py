"""Bloodlines rules from docs/rules that had no regression test (2026-11 audit).

Each test quotes the docs/rules sentence it pins, with its citation.
"""

from dataclasses import replace

from tests.unit.rules.test_navigation import (
    _card,
    _play_option,
    _reach_two,
    _steersman,
)
from tests.unit.rules.test_navigation import _turn_state as _navigation_state
from tests.unit.rules.test_sardaukar import _seat_with_skills, _skill
from tests.unit.rules.test_sardaukar import _turn_state as _skill_state
from tests.unit.rules.test_tech import ACQUIRE_PRINTER, _tech_actions
from tests.unit.rules.test_tech import _acquire as _tech_acquire
from tests.unit.rules.test_tech import _owner as _tech_owner
from tests.unit.rules.test_tech import _turn_state as _tech_state

from dune_imperium import RulesetConfig
from dune_imperium.content.core.icons import Faction
from dune_imperium.content.registry.tech import TECH_TILES_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
    RuleResult,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    apply_imperial_privilege_action,
    legal_imperial_privilege_actions,
)
from dune_imperium.rules.influence import (
    gain_faction_influence,
    lose_faction_influence,
)
from dune_imperium.rules.navigation import (
    begin_navigation_play,
    navigation_play_is_queued,
)
from dune_imperium.rules.strength import refresh_pre_reveal_strength
from dune_imperium.rules.tech import push_tech_acquisition, tech_cost

BLOODLINES = RulesetConfig(bloodlines=True)


def _fenring_at_imperial_privilege() -> GameState:
    dagger = next(card for card in starting_deck_instance_ids(0) if ":dagger:" in card)
    owner = PlayerState(
        player_id=0,
        leader_id="count_hasimir_fenring",
        hand=(dagger,),
        resources=Resources(solari=3, water=0),
        influence=Influence(emperor=2),
        intrigue_cards=("intrigue:held",),
        agents_available=1,
        agent_locations=("arrakeen",),
    )
    state = GameState(
        config=BLOODLINES,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        intrigue_deck=("intrigue:replacement",),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    action = next(
        candidate
        for candidate in legal_agent_actions(state, 0)
        if dict(candidate.arguments)["space_id"] == "imperial_privilege"
    )
    return apply_agent_action(state, action).state


def test_fenring_gains_no_solari_for_trashing_an_intrigue_card() -> None:
    """Assassin pays for personal cards only.

    docs/rules/bloodlines.md: "Count Hasimir Fenring: Intrigue 카드를 trash할
    때 Solari를 얻지 않는다." `[Bloodlines p. 12]`
    """

    state = _fenring_at_imperial_privilege()
    assert state.players[0].resources.solari == 0
    trade = DomainAction(
        action_id="trash_intrigue_for_imperial_privilege",
        actor=0,
        arguments=(("card_id", "intrigue:held"),),
    )
    assert trade in legal_imperial_privilege_actions(state, 0)

    traded = apply_imperial_privilege_action(state, trade).state

    assert "intrigue:held" not in traded.players[0].intrigue_cards
    assert traded.players[0].resources.solari == 0


def test_a_skill_counts_once_however_many_commanders_fight() -> None:
    """Two Commanders in the Conflict do not double a Skill.

    docs/rules/bloodlines.md: "Commander가 여러 개여도 각 Skill은 라운드당 한
    번만 작동한다." `[Bloodlines p. 4]`
    """

    skills = (_skill("canny"), _skill("loyal"))
    one = _seat_with_skills(skill_ids=skills, influence=Influence(emperor=3))
    two = replace(one, commanders_conflict=2)

    def strength(owner: PlayerState) -> tuple[int, int]:
        refreshed = refresh_pre_reveal_strength(
            RuleResult(state=_skill_state(owner))
        ).state.players[0]
        return refreshed.combat_strength, refreshed.skill_strength_applied

    # troop 2 + Commander 2 + Canny 2 (Agent on High Council) + Loyal 2
    # (Emperor Influence 3).
    assert strength(one) == (8, 4)
    # A second Commander adds its own 2; the Skills still add 4.
    assert strength(two) == (10, 4)


def test_y_rkoon_plays_the_next_navigation_card_on_reaching_two_again() -> None:
    """Dropping below 2 and climbing back plays another Navigation card.

    docs/rules/bloodlines.md: "Steersman Y'rkoon: ... Influence를 잃었다가
    다시 얻으면 같은 Faction에서 Influence 2에 여러 번 도달할 수 있고, 그때마다
    Navigation 카드를 play한다." `[Bloodlines p. 12]`
    """

    owner = _steersman((_card(6), _card(7)), influence=Influence(emperor=1))
    played = _play_option(_reach_two(_navigation_state(owner), Faction.EMPEROR), 0)
    assert played.players[0].navigation_played == (_card(6),)

    dropped = lose_faction_influence(
        played, 0, Faction.EMPEROR, 1, event_prefix="test:drop"
    ).state
    assert dropped.players[0].influence.emperor == 1
    assert not navigation_play_is_queued(dropped)

    regained = gain_faction_influence(
        dropped, 0, Faction.EMPEROR, 1, event_prefix="test:again"
    ).state
    assert navigation_play_is_queued(regained)
    opened = begin_navigation_play(regained).state
    frame = opened.decision_stack[-1]
    assert frame.kind == "navigation_choice"
    assert dict(frame.context)["card_id"] == _card(7)


def test_a_tech_tile_never_costs_less_than_zero() -> None:
    """High Council and a Tech Discount icon together stop at 0 spice.

    docs/rules/bloodlines.md: "비용 감소는 두 가지이며 비용은 0 아래로
    내려가지 않는다. High Council 자리가 있으면 Ixian Embassy board의 할인으로
    tile마다 spice 1을 덜 낸다. 카드의 Tech Discount 아이콘은 tile 하나를
    spice 1 할인으로 acquire하게 하며 High Council 할인과 합칠 수 있지만,
    ..." `[Bloodlines pp. 7, 12]`
    """

    owner = _tech_owner(high_council=True, resources=Resources(spice=0, water=0))
    # Training Depot costs 1 spice [Training Depot tile].
    depot = TECH_TILES_BY_ID["training_depot"]
    assert depot.cost == 1
    assert tech_cost(owner, depot, discount=1) == 0

    state = _tech_state(
        owner, stacks=(("training_depot",), ("gene_locked_vault",), ("glowglobes",))
    )
    opened = push_tech_acquisition(
        state, 0, discount=1, source="test", printer=ACQUIRE_PRINTER
    ).state
    offered = _tech_actions(opened)
    key = next(key for key in offered if key.startswith("training_depot"))

    bought = _tech_acquire(opened, key).players[0]

    assert bought.tech_ids == ("training_depot",)
    assert bought.resources.spice == 0
