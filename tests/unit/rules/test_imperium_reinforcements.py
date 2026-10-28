"""The original game's Reinforcements and the ``DeployTheseTroops`` piece.

"3 Solari -> 3 troops. If it's your Reveal turn, you may deploy any of these
troops to the Conflict." [Reinforcements card, Steam app text]. The recruit
is as many as the supply holds (OQ-030); a played Intrigue's arrow cost is
required [FAQ p. 3] and the card is not played when its line cannot change
anything (OQ-071, docs/rules/imperium-base.md 16). In an Agent turn the
troops deploy by the Combat space rule [DI p. 10] [FAQ p. 4] and the line
opens nothing more.

In a Reveal turn any of the troops the line recruited may be deployed, and a
troop the supply could not cover once it is refilled later in the turn
(OQ-140, user rulings 2026-10-28: "각각 최대 3개, 2개의 병력을 교전칸에 넣을
수 있게 하고, 만약 지금 부족하다면 지금 가능한 개수만 보여주고, 공급처에
가능한 병력이 생기면 그때 또 추가 배치가 가능하게"; "Reinforcements·Gurney 가
아닌 다른 효과로 얻은 병력은 배치 가능한 병력이 아니잖아"; a refill goes to
these cards' owed troops first, "이 카드들 몫 먼저"). No other garrison troop
deploys by it, and no Sardaukar Commander (OQ-070).
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
from dune_imperium.rules.shortfall import refill_shortfall

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


def _seat(state: GameState, **changes: object) -> GameState:
    seat = replace(state.players[0], **changes)  # type: ignore[arg-type]
    return replace(state, players=(seat, *state.players[1:]))


def _reveal_context(state: GameState, **changes: int) -> GameState:
    """The Reveal frame (on top) with ``changes`` to its context."""

    frame = state.decision_stack[-1]
    assert frame.kind == "reveal"
    context = dict(frame.context)
    context.update(changes)
    top = replace(frame, context=tuple(sorted(context.items())))
    return replace(state, decision_stack=(*state.decision_stack[:-1], top))


def _recruited_earlier(state: GameState, count: int) -> GameState:
    """Seat 0 recruited ``count`` troops earlier in this Reveal turn (another
    card or Intrigue): supply to garrison, counted as the turn's recruits."""

    seat = state.players[0]
    moved = _seat(
        state,
        troops_supply=seat.troops_supply - count,
        troops_garrison=seat.troops_garrison + count,
    )
    recruited = dict(state.decision_stack[-1].context)["reveal_troops_recruited"]
    assert isinstance(recruited, int)
    return _reveal_context(moved, reveal_troops_recruited=recruited + count)


def test_a_shortfall_refilled_later_in_the_turn_may_deploy_too() -> None:
    """Two troops left: two recruited and one owed. When a troop comes back
    to the supply later in the turn the owed one is recruited then (OQ-030),
    and its deploy appears then (OQ-140); the cap stays three."""

    engine, short = _hand(supply=2)
    revealed = engine.apply(short, REVEAL).state
    played = apply_whole(engine, revealed, PLAY).state
    assert played.players[0].ungained_troops == 1
    deployed = engine.apply(
        played, DomainAction("deploy_troops", 0, (("count", 2),))
    ).state
    assert _deploys(engine, deployed) == []
    # A garrison troop lost to the supply (a Twisted Intrigue's cost, a
    # Tleilaxu Surgeon's, or a specimen returned, in a combined game).
    seat = deployed.players[0]
    assert seat.troops_garrison >= 1
    back = _seat(
        deployed, troops_garrison=seat.troops_garrison - 1, troops_supply=1
    )
    refilled = refill_shortfall(back, 0).state
    assert refilled.players[0].ungained_troops == 0
    assert _deploys(engine, refilled) == [1]
    third = engine.apply(
        refilled, DomainAction("deploy_troops", 0, (("count", 1),))
    ).state
    assert third.players[0].troops_conflict == played.players[0].troops_conflict + 3
    assert third.players[0].units_deployed_turn == 3  # OQ-115 counts them
    # The cap is used up; the garrison's other troops stay.
    assert third.players[0].troops_garrison >= 1
    assert _deploys(engine, third) == []


def test_troops_recruited_by_another_effect_never_deploy_by_it() -> None:
    """Only the card's own troops: two recruited earlier in the Reveal turn by
    another effect stay out, and with one troop left in the supply the line
    recruits one, owes two, and deploys one (user 2026-10-28: "그 카드로
    소집한 병력이 아닌걸?")."""

    engine, state = _hand(supply=3)
    revealed = _recruited_earlier(engine.apply(state, REVEAL).state, 2)
    played = apply_whole(engine, revealed, PLAY).state
    assert played.players[0].ungained_troops == 2
    assert _deploys(engine, played) == [1]


def test_an_empty_supply_does_not_play_it_even_with_troops_waiting() -> None:
    """The line's recruit with no troop to take changes nothing (OQ-071), and
    the deploy only lets the card's own troops go: troops another effect
    recruited this Reveal turn do not make the card playable."""

    engine, state = _hand()
    revealed = engine.apply(state, REVEAL).state
    empty = _seat(
        revealed,
        troops_garrison=revealed.players[0].troops_garrison
        + revealed.players[0].troops_supply,
        troops_supply=0,
    )
    assert legal_intrigue_play_actions(empty, 0) == ()
    waiting = _reveal_context(empty, reveal_troops_recruited=2)
    assert legal_intrigue_play_actions(waiting, 0) == ()


def test_a_refill_goes_to_these_cards_owed_troops_first() -> None:
    """Another effect owed a troop before the card and the card owes two: the
    one troop that comes back is the card's ("이 카드들 몫 먼저"), so it may
    deploy; the other effect's stays owed."""

    engine, state = _hand(supply=1)
    revealed = engine.apply(state, REVEAL).state
    other_owed = _seat(revealed, ungained_troops=1)
    played = apply_whole(engine, other_owed, PLAY).state
    assert played.players[0].ungained_troops == 3
    assert _deploys(engine, played) == [1]
    one = engine.apply(played, DomainAction("deploy_troops", 0, (("count", 1),))).state
    seat = one.players[0]
    back = _seat(one, troops_garrison=seat.troops_garrison - 1, troops_supply=1)
    refilled = refill_shortfall(back, 0).state
    assert refilled.players[0].ungained_troops == 2
    assert _deploys(engine, refilled) == [1]


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
