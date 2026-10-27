"""The original game's Reinforcements and the ``DeployTheseTroops`` piece.

"3 Solari -> 3 troops. If it's your Reveal turn, you may deploy any of these
troops to the Conflict." [Reinforcements card, Steam app text]. The recruit
is as many as the supply holds (OQ-030); a played Intrigue's arrow cost is
required [FAQ p. 3] and the card is not played when its line cannot change
anything (OQ-071, docs/rules/imperium-base.md 16). In an Agent turn the
troops deploy by the Combat space rule [DI p. 10] [FAQ p. 4] and the line
opens nothing more; in a Reveal turn any of these troops, and no other
garrison troop, may be deployed.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    Resources,
)
from dune_imperium.core.state import GamePhase
from dune_imperium.display import intrigue_card_text
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.intrigue import legal_intrigue_play_actions

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
# Four Leaders without the Baron, whose Masterstroke would pause the setup.
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
CARD = "intrigue:reinforcements:0"
PLAY = DomainAction("play_intrigue", 0, (("card_id", CARD), ("option", 0)))
REVEAL = DomainAction(action_id="reveal_turn", actor=0)


def _hand(
    solari: int = 3, supply: int | None = None
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 at its first turn holding Reinforcements, with ``solari`` and
    (if given) only ``supply`` troops left in its supply."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    seat = replace(
        state.players[0], intrigue_cards=(CARD,), resources=Resources(solari=solari)
    )
    if supply is not None:
        seat = replace(
            seat,
            troops_garrison=seat.troops_garrison + seat.troops_supply - supply,
            troops_supply=supply,
        )
    return engine, replace(state, players=(seat, *state.players[1:]))


def _deploys(engine: UprisingRulesEngine, state: GameState) -> list[int]:
    return sorted(
        int(dict(action.arguments)["count"])
        for action in engine.legal_actions(state, 0)
        if action.action_id == "deploy_troops"
    )


def test_reinforcements_is_one_plot_cost_line() -> None:
    entry = intrigue_card_for_instance(CARD)
    assert (entry.card.name, entry.copies) == ("Reinforcements", 1)
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert intrigue_card_text(entry) == [
        "Plot — Pay 3 solari → Recruit 3 troops, In your Reveal turn, you may "
        "deploy these troops to the Conflict"
    ]


def test_in_a_reveal_turn_any_of_these_troops_may_be_deployed() -> None:
    engine, state = _hand()
    revealed = engine.apply(state, REVEAL).state
    garrison = revealed.players[0].troops_garrison
    assert _deploys(engine, revealed) == []
    played = apply_whole(engine, revealed, PLAY).state
    seat = played.players[0]
    assert seat.resources.solari == 0
    assert seat.troops_garrison == garrison + 3
    # These three, and no other garrison troop (no Combat icon).
    assert _deploys(engine, played) == [1, 2, 3]
    two = engine.apply(played, DomainAction("deploy_troops", 0, (("count", 2),))).state
    assert two.players[0].troops_conflict == seat.troops_conflict + 2
    assert _deploys(engine, two) == [1]


def test_a_short_supply_opens_only_the_troops_recruited() -> None:
    # As many as the supply holds (OQ-030): two troops left, two to deploy.
    engine, short = _hand(supply=2)
    revealed = engine.apply(short, REVEAL).state
    played = apply_whole(engine, revealed, PLAY).state
    assert _deploys(engine, played) == [1, 2]


def test_in_an_agent_turn_the_line_opens_no_deployment() -> None:
    engine, state = _hand()
    played = apply_whole(engine, state, PLAY).state
    assert played.players[0].troops_garrison == state.players[0].troops_garrison + 3
    assert _deploys(engine, played) == []
    assert played.decision_stack[-1].kind == "turn"


def test_not_played_without_three_solari_or_a_troop_to_recruit() -> None:
    _, poor = _hand(solari=2)
    assert legal_intrigue_play_actions(poor, 0) == ()
    _, empty = _hand(supply=0)
    assert legal_intrigue_play_actions(empty, 0) == ()
