"""The app AI with the original cards and Leaders in Uprising (P7e,
``imperium_cards``): the windows that meet an original card beside an
Uprising system."""

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import Answer
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import intrigue
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.core.actions import DomainAction

P7E = RulesetConfig(
    imperium_cards=True, promo_cards=True, leader_draft=True, bloodlines=True
)


def _loss(**arguments: object) -> DomainAction:
    return DomainAction(
        action_id="lose_intrigue_troop",
        actor=0,
        arguments=tuple(sorted(arguments.items())),  # type: ignore[arg-type]
    )


def test_staged_incident_loses_a_plain_troop_before_a_commander() -> None:
    """The original Staged Incident in a Bloodlines game: its app ability
    names no target, so the plain Conflict troop goes first and a Commander
    only for a missing troop (Gruesome Sacrifice's rule, plan §11.4)."""

    p = make_profile(first_decision("turn", config=P7E))
    commander = _loss(commanders=1, zone="conflict")
    troop = _loss(zone="conflict")
    run = DecisionRun(p.ctx, p, (commander, troop), p.rng, Memory())
    empty = Answer(0.0, None, "")
    assert intrigue._lose_troops(run, "staged_incident", lambda: empty) is troop
    only = DecisionRun(p.ctx, p, (commander,), p.rng, Memory())
    assert intrigue._lose_troops(only, "staged_incident", lambda: empty) is commander


def test_a_kwisatz_move_sends_an_agent_already_on_the_board() -> None:
    """The original Kwisatz Haderach: "Agent가 남지 않아도 낼 수 있다(이미 칸에
    있는 Agent를 보낸다)" (docs/rules/imperium-base.md, [DI p. 13]). The state
    after its send keeps the seat's available Agents and moves the one from
    ``from_space`` (seed 7401, original + Immortality, had none left)."""

    from dune_imperium.agents.app_ai.testing import with_player
    from dune_imperium.agents.app_ai.windows import turn
    from dune_imperium.config import BaseGame

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, immortality=True)
    state = first_decision("turn", config=config)
    seat = make_profile(state).ctx.seat
    state = with_player(
        state, seat, agents_available=0, agent_locations=("arrakeen", "carthag")
    )
    card = "imperium:kwisatz_haderach:0"
    after = turn._after_send(state, seat, card, "sell_melange", "arrakeen")
    me = after.players[seat]
    assert me.agents_available == 0
    assert sorted(me.agent_locations) == ["carthag", "sell_melange"]
    plain = with_player(state, seat, agents_available=1, agent_locations=("carthag",))
    sent = turn._after_send(plain, seat, card, "sell_melange").players[seat]
    assert sent.agents_available == 0
    assert sorted(sent.agent_locations) == ["carthag", "sell_melange"]


def test_the_original_board_takes_the_immortality_research_station() -> None:
    """P7b: with Immortality the app removes ``BaseSet.ResearchStation``
    (``RemovedFromSetList = [Immortality]``) and appends
    ``ResearchStationImmortality``, which our engine keeps on the original
    space's id."""

    from dune_imperium.agents.app_ai.catalog import space_archetype
    from dune_imperium.agents.app_ai.context import Board
    from dune_imperium.agents.app_ai.windows.turn import board_space_order

    space = "imperium_research_station"
    with_immortality = Board(False, True, original=True)
    plain = Board(False, False, original=True)
    assert space_archetype(space, with_immortality) == (
        "SpaceArchetypes.Immortality.ResearchStationImmortality"
    )
    assert space_archetype(space, plain) == "SpaceArchetypes.BaseSet.ResearchStation"
    order = board_space_order(with_immortality)
    assert order[-1] == space and "research_station" not in order
    assert len(order) == len(board_space_order(plain)) == 22
