"""The original game's Urgent Mission and Calculated Hire, and its three promos
(stage P3).

docs/rules/imperium-base.md 9 (the Mentat is one of its holder's Agents for
all purposes; Calculated Hire takes it only from its own space), 13.3 ("Urgent
Mission은 Agent가 남지 않아도 낸다(Reveal turn을 선언하기 전)", the Calculated
Hire row), 16 (OQ-113 (C): a cost-free effect is played even when it fizzles,
a cost line needs a live reward; "Calculated Hire·Urgent Mission은 자기 Reveal
turn에도 낼 수 있다"; the Duncan, Jessica and Thumper lines) with
docs/rules/open-questions.md OQ-015 (a) (a Plot may open the turn), OQ-022,
OQ-028, OQ-068, OQ-071, OQ-113, OQ-115 and OQ-139 (the engine does not tell the
Mentat from the seat's other Agents, user ruling (가) 2026-10-28). The printed
values are the Steam app's attribute table and card text
(docs/base-game-and-ix-plan.md 2.4, 16.3). Seat 0 holds the card, in an
original-game ``RulesetConfig``.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import (
    PayResources,
    RecallYourAgent,
    TakeMentat,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    intrigue_card_for_instance,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Resources,
)
from dune_imperium.display import intrigue_card_text
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.effect_interpreter import play_changes_nothing
from dune_imperium.rules.effects import mentat_rests
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.phases import resolve_recall_or_endgame

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
URGENT = "intrigue:urgent_mission:0"
HIRE = "intrigue:calculated_hire:0"
# City-only cards: a seat holding them reaches Arrakeen, Carthag and the
# Research Station whatever the shuffle dealt.
RECRUITER = "imperium:arrakis_recruiter:0"
RECRUITER_TWO = "imperium:arrakis_recruiter:1"


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of an original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _play(card: str, option: int = 0, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=actor,
        arguments=(("card_id", card), ("option", option)),
    )


def _recall(space_id: str) -> DomainAction:
    return DomainAction(
        action_id="recall_agent_for_intrigue",
        actor=0,
        arguments=(("space_id", space_id),),
    )


RECALL_CONFLICT = DomainAction(action_id="recall_conflict_agent_for_intrigue", actor=0)
SKIP_RECALL = DomainAction(action_id="skip_intrigue_recall_agent", actor=0)
REVEAL = DomainAction(action_id="reveal_turn", actor=0)


def _spaces(state: GameState, seat: int = 0) -> set[str]:
    return {
        str(dict(placement.arguments)["space_id"])
        for placement in executable_placements(state, seat)
    }


def _frame_kinds(state: GameState) -> list[str]:
    return [str(frame.kind) for frame in state.decision_stack]


# --- Urgent Mission (Plot, stage P3c) -----------------------------------------


def _urgent_hand(**changes: object) -> tuple[UprisingRulesEngine, GameState]:
    engine, state = _start()
    return engine, _seat(state, intrigue_cards=(URGENT,), **changes)


def test_urgent_mission_is_one_cost_free_plot_with_one_copy() -> None:
    # "Recall one of your Agents" [Urgent Mission card, Steam app text]; 1 copy
    # in the deck [DI p. 3]; cost-free, so OQ-113 (C) plays it even when it
    # fizzles (imperium-base.md 13.3).
    entry = intrigue_card_for_instance(URGENT)
    assert entry.card.name == "Urgent Mission"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    (section,) = entry.options[0].sections
    assert not section.costs
    assert section.rewards == (RecallYourAgent(),)
    assert intrigue_card_text(entry) == ["Plot — Recall one of your Agents"]
    assert reward_text(RecallYourAgent()) == "Recall one of your Agents"
    assert "{agent}" in reward_text_ko(RecallYourAgent())
    assert "urgent_mission" not in {entry.card.card_id for entry in INTRIGUE_CARDS}
    assert URGENT in content_for(CONFIG).intrigue_deck_instance_ids


def test_urgent_mission_recalls_the_agent_the_owner_names() -> None:
    # "Recall one of your Agents": the Agent returns to its Leader and its
    # space is free again [DI p. 16] (agents_available + 1).
    engine, state = _urgent_hand(
        agents_available=0, agent_locations=("arrakeen", "carthag")
    )
    assert legal_intrigue_play_actions(state, 0) == (_play(URGENT),)

    opened = apply_whole(engine, state, _play(URGENT)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    # Every space the seat has an Agent on is offered, nothing else.
    assert set(engine.whole_actions(opened, 0)) == {
        _recall("arrakeen"),
        _recall("carthag"),
    }
    assert engine.whole_actions(opened, 1) == ()

    done = apply_whole(engine, opened, _recall("arrakeen"))
    player = done.state.players[0]
    assert player.agents_available == 1
    assert player.agent_locations == ("carthag",)
    assert [event.kind for event in done.events].count("agent_recalled") == 1
    assert done.state.decision_stack[-1].kind == "turn"
    # The card is discarded once its choice is resolved.
    assert URGENT not in player.intrigue_cards
    assert URGENT in done.state.intrigue_discard
    # The recalled Agent may be used again this round: its space is free for
    # anyone, and the seat can send it out.
    assert "arrakeen" not in {
        space for seat in done.state.players for space in seat.agent_locations
    }


def test_urgent_mission_with_no_agent_on_the_board_fizzles_but_is_played() -> None:
    # "Urgent Mission은 Agent가 남지 않아도 낸다 ... 비용이 없으므로 되돌릴
    # Agent가 보드에 없어도 낸다(불발; OQ-113 (C))" (imperium-base.md 13.3): the
    # app's HasDeployedAgents gate is not followed. The empty confirmation is
    # the only row, and the page can tell the play changes nothing.
    engine, state = _urgent_hand(agents_available=2, agent_locations=())
    assert legal_intrigue_play_actions(state, 0) == (_play(URGENT),)
    (section,) = intrigue_card_for_instance(URGENT).options[0].sections
    assert play_changes_nothing(state, 0, (section,))

    opened = apply_whole(engine, state, _play(URGENT)).state
    assert engine.whole_actions(opened, 0) == (SKIP_RECALL,)

    done = apply_whole(engine, opened, SKIP_RECALL)
    assert [event.kind for event in done.events] == ["intrigue_agent_unavailable"]
    player = done.state.players[0]
    assert player.agents_available == 2
    assert player.agent_locations == ()
    assert URGENT in done.state.intrigue_discard


def test_urgent_mission_in_an_empty_leaders_turn_start_leads_to_an_agent_turn() -> None:
    # "자기 Reveal turn에도 낼 수 있다"; "Agent가 남지 않아도 낸다(Reveal turn을
    # 선언하기 전)" (imperium-base.md 13.3, 16) and OQ-015 (a): the Plot window
    # opens with the turn frame. A seat whose Leader holds no Agent has only the
    # Reveal turn and its Plots; the recall gives it an Agent turn.
    engine, state = _urgent_hand(
        agents_available=0,
        agent_locations=("arrakeen", "landsraad"),
        hand=(RECRUITER, RECRUITER_TWO),
    )
    assert state.decision_stack[-1].kind == "turn"
    assert _spaces(state) == set()
    offered = {action.action_id for action in engine.whole_actions(state, 0)}
    assert "reveal_turn" in offered
    assert "choose_agent_card" not in offered
    assert _play(URGENT) in engine.whole_actions(state, 0)

    opened = apply_whole(engine, state, _play(URGENT)).state
    recalled = apply_whole(engine, opened, _recall("landsraad")).state
    assert recalled.decision_stack[-1].kind == "turn"
    assert recalled.players[0].agents_available == 1
    # The Agent turn is back: the recalled Agent goes to a City space.
    assert _spaces(recalled) >= {"carthag"}
    assert "choose_agent_card" in {
        action.action_id for action in engine.whole_actions(recalled, 0)
    }


def test_urgent_mission_may_recall_the_agent_sent_this_turn() -> None:
    # "Recall one of your Agents" has no "other": the exclusion belongs to
    # Uprising's Recall Agent icon [Main p. 20] (P0 sweep S29, imperium-base.md
    # 13.3). The Agent sent this turn is one of the seat's Agents; effects of
    # the space it already got stay (effects are gained by sending [DI p. 9]).
    engine, state = _urgent_hand(agents_available=2, hand=(RECRUITER, RECRUITER_TWO))
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "carthag"
        and dict(placement.arguments)["card_id"] == RECRUITER
    )
    sent = apply_placement(engine, state, placement).state
    assert sent.players[0].agent_locations == ("carthag",)
    assert "agent_effects" in _frame_kinds(sent)
    assert _play(URGENT) in engine.whole_actions(sent, 0)

    opened = apply_whole(engine, sent, _play(URGENT)).state
    assert _recall("carthag") in engine.whole_actions(opened, 0)
    done = apply_whole(engine, opened, _recall("carthag")).state
    player = done.players[0]
    assert player.agent_locations == ()
    assert player.agents_available == 2
    # The Agent-effect frame notes that this turn's Agent is home, as Twisted
    # Mentat's recall does, so a later "other Agents" recall of the turn does
    # not leave one more Agent out of the Conflict.
    effects = next(f for f in done.decision_stack if f.kind == "agent_effects")
    assert dict(effects.context).get("turn_agent_recalled") is True


def test_urgent_mission_may_recall_an_agent_in_the_conflict() -> None:
    # OQ-068 (user ruling 2026-09-26): "모든 recall 효과가 같게 동작" -- an
    # Agent Into the Fray left in the Conflict is one of "your Agents" too. It
    # leaves as a 2 strength unit, so the running strength drops with it.
    engine, state = _urgent_hand(
        agents_available=1,
        agent_locations=(),
        agent_in_conflict=1,
        troops_supply=8,
        troops_conflict=1,
        combat_strength=4,
    )
    assert _play(URGENT) in engine.whole_actions(state, 0)
    opened = apply_whole(engine, state, _play(URGENT)).state
    assert engine.whole_actions(opened, 0) == (RECALL_CONFLICT,)

    done = apply_whole(engine, opened, RECALL_CONFLICT)
    player = done.state.players[0]
    assert player.agent_in_conflict == 0
    assert player.agents_available == 2
    assert player.combat_strength == 2
    (recalled,) = [e for e in done.events if e.kind == "agent_recalled"]
    assert dict(recalled.payload)["space_id"] == "conflict"


def test_urgent_mission_recalls_from_the_board_or_the_conflict_as_named() -> None:
    engine, state = _urgent_hand(
        agents_available=0,
        agent_locations=("arrakeen",),
        agent_in_conflict=1,
        troops_supply=8,
        troops_conflict=1,
        combat_strength=4,
    )
    opened = apply_whole(engine, state, _play(URGENT)).state
    assert set(engine.whole_actions(opened, 0)) == {
        _recall("arrakeen"),
        RECALL_CONFLICT,
    }


def test_urgent_mission_in_the_reveal_turn_keeps_the_reveal_tally_in_step() -> None:
    # "Calculated Hire·Urgent Mission은 자기 Reveal turn에도 낼 수 있다"
    # (imperium-base.md 16). A Conflict Agent recalled in the Reveal turn takes
    # its strength off the Reveal frame's own tally too, as any unit removed
    # there does [Main p. 13].
    engine, state = _urgent_hand(
        agents_available=1,
        agent_locations=(),
        agent_in_conflict=1,
        troops_supply=8,
        troops_conflict=1,
        combat_strength=4,
    )
    revealed = apply_whole(engine, state, REVEAL).state
    frame = revealed.decision_stack[-1]
    assert frame.kind == "reveal"
    before = dict(frame.context)["strength"]
    assert isinstance(before, int)

    opened = apply_whole(engine, revealed, _play(URGENT)).state
    done = apply_whole(engine, opened, RECALL_CONFLICT).state
    after = done.decision_stack[-1]
    assert after.kind == "reveal"
    assert dict(after.context)["strength"] == before - 2
    assert done.players[0].combat_strength == revealed.players[0].combat_strength - 2


def test_urgent_mission_is_also_played_in_the_reveal_turn_with_a_board_agent() -> None:
    engine, state = _urgent_hand(agents_available=1, agent_locations=("arrakeen",))
    revealed = apply_whole(engine, state, REVEAL).state
    assert _play(URGENT) in engine.whole_actions(revealed, 0)
    opened = apply_whole(engine, revealed, _play(URGENT)).state
    done = apply_whole(engine, opened, _recall("arrakeen")).state
    assert done.players[0].agents_available == 2
    assert done.decision_stack[-1].kind == "reveal"


def test_urgent_mission_counts_the_mentat_as_one_of_the_seats_agents() -> None:
    # OQ-139 (가): the Mentat is one of its holder's Agents "for all purposes"
    # (imperium-base.md 9) and the engine does not tell its piece from the
    # others: all three Agents are offered, the recall gives the Leader an
    # Agent back and the seat keeps the Mentat for the round.
    engine, state = _urgent_hand(
        mentat=True,
        agents_available=0,
        agent_locations=("arrakeen", "carthag", "mentat"),
    )
    opened = apply_whole(engine, state, _play(URGENT)).state
    assert {
        dict(action.arguments)["space_id"] for action in engine.whole_actions(opened, 0)
    } == {"arrakeen", "carthag", "mentat"}

    done = apply_whole(engine, opened, _recall("mentat")).state
    player = done.players[0]
    assert player.mentat
    assert player.agents_available == 1
    assert player.agent_locations == ("arrakeen", "carthag")
    # Recall at the round's end still returns the Mentat to its space.
    assert not mentat_rests(done)


def test_urgent_mission_rows_have_codec_templates_and_only_the_original_game() -> None:
    engine, state = _urgent_hand(
        agents_available=0,
        agent_locations=("arrakeen",),
        agent_in_conflict=1,
        troops_supply=8,
        troops_conflict=1,
        combat_strength=4,
    )
    codec = ActionCodec(CONFIG)
    opened = apply_whole(engine, state, _play(URGENT)).state
    offered = engine.legal_actions(opened, 0)
    assert offered
    for action in offered:
        assert codec.decode(codec.encode(action), 0) == action
    empty = apply_whole(
        engine,
        _seat(state, agents_available=2, agent_locations=(), agent_in_conflict=0),
        _play(URGENT),
    ).state
    for action in engine.legal_actions(empty, 0):
        assert codec.decode(codec.encode(action), 0) == action

    def rows(config: RulesetConfig) -> set[str]:
        return {
            template.action_id
            for template in ActionCodec(config).catalog
            if dict(template.arguments).get("printed") == "urgent_mission"
        }

    assert rows(CONFIG) == {"confirm_empty"}
    assert not rows(RulesetConfig())
    assert not rows(RulesetConfig(bloodlines=True, tech_module=True))


# --- Calculated Hire (Plot, stage P3c) ----------------------------------------


def _hire_hand(**changes: object) -> tuple[UprisingRulesEngine, GameState]:
    engine, state = _start()
    return engine, _seat(
        state, intrigue_cards=(HIRE,), resources=Resources(spice=1), **changes
    )


def test_calculated_hire_is_one_plot_cost_line_with_one_copy() -> None:
    # "[1 spice] -> Take the Mentat from its designated space in the Landsraad"
    # [Calculated Hire card, Steam app text]; 1 copy [DI p. 3]; a cost arrow
    # line [DI p. 16].
    entry = intrigue_card_for_instance(HIRE)
    assert entry.card.name == "Calculated Hire"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    (section,) = entry.options[0].sections
    assert section.costs == (PayResources(spice=1),)
    assert section.rewards == (TakeMentat(),)
    assert intrigue_card_text(entry) == [
        "Plot — Pay 1 spice → Take the Mentat from its space"
    ]
    assert HIRE in content_for(CONFIG).intrigue_deck_instance_ids


def test_calculated_hire_pays_one_spice_and_takes_the_mentat() -> None:
    # "take it and place it on your Leader; this round, you may use it as one
    # of your Agents" [DI p. 18] (imperium-base.md 9): one Agent more this
    # round, and the Mentat no longer rests on its space.
    engine, state = _hire_hand()
    assert mentat_rests(state)
    assert legal_intrigue_play_actions(state, 0) == (_play(HIRE),)

    done = apply_whole(engine, state, _play(HIRE))
    player = done.state.players[0]
    assert player.mentat
    assert player.agents_available == state.players[0].agents_available + 1
    assert player.resources.spice == 0
    assert [event.kind for event in done.events].count("mentat_taken") == 1
    assert not mentat_rests(done.state)
    assert HIRE in done.state.intrigue_discard
    assert done.state.decision_stack[-1].kind == "turn"


def test_calculated_hire_needs_one_spice() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." [FAQ p. 2]
    _, state = _hire_hand()
    assert legal_intrigue_play_actions(_seat(state, resources=Resources()), 0) == ()


def test_calculated_hire_needs_the_mentat_on_its_own_space() -> None:
    # "Calculated Hire는 Mentat을 Landsraad의 제 자리에서만 가져온다 `[DI p. 13]`,
    # Mentat이 그 자리에 있어야 낼 수 있다(디자이너 판정)" (imperium-base.md 9):
    # a Mentat an opponent holds, one a Sort Through the Chaos winner is owed
    # [FAQ p. 4] or one the seat already holds is nothing to take, so the cost
    # line has no live reward and the card is not played (OQ-071, OQ-113 (C)).
    _, state = _hire_hand()
    held_by_opponent = _seat(
        state, 1, mentat=True, agents_available=2, agent_locations=("carthag",)
    )
    owed = replace(state, mentat_owed_to=2)
    held_by_owner = _seat(state, 0, mentat=True, agents_available=3)
    for blocked in (held_by_opponent, owed, held_by_owner):
        assert not mentat_rests(blocked)
        assert legal_intrigue_play_actions(blocked, 0) == ()


def test_calculated_hire_in_an_empty_leaders_turn_start_enables_an_agent_turn() -> None:
    # OQ-015 (a): the Plot window opens with the turn. With every Agent on the
    # board the seat has only the Reveal turn; the Mentat is a new Agent to
    # send (imperium-base.md 9, "Agent turn에 보낼 수 있다").
    engine, state = _hire_hand(
        agents_available=0,
        agent_locations=("arrakeen", "landsraad"),
        hand=(RECRUITER, RECRUITER_TWO),
    )
    assert _spaces(state) == set()

    opened = apply_whole(engine, state, _play(HIRE)).state
    assert opened.players[0].agents_available == 1
    assert opened.decision_stack[-1].kind == "turn"
    assert "carthag" in _spaces(opened)
    placement = next(
        placement
        for placement in executable_placements(opened, 0)
        if dict(placement.arguments)["space_id"] == "carthag"
    )
    sent = apply_placement(engine, opened, placement).state
    player = sent.players[0]
    assert player.mentat
    assert player.agents_available == 0
    assert set(player.agent_locations) == {"arrakeen", "landsraad", "carthag"}


def test_calculated_hire_is_also_played_in_the_reveal_turn() -> None:
    # "Calculated Hire의 '1 spice → Mentat'은 Mentat이 자리를 떠나 보드가 바뀌므로
    # 비용 줄의 보상이 살아 있다" (imperium-base.md 16): playable in the seat's
    # own Reveal turn, where it takes the Mentat off its space and enables no
    # Agent turn.
    engine, state = _hire_hand()
    revealed = apply_whole(engine, state, REVEAL).state
    assert _play(HIRE) in engine.whole_actions(revealed, 0)
    done = apply_whole(engine, revealed, _play(HIRE)).state
    assert done.players[0].mentat
    assert not mentat_rests(done)
    assert done.decision_stack[-1].kind == "reveal"


def _with_dagger(state: GameState) -> GameState:
    """Seat 0 with a starting Dagger (a Landsraad card) in hand."""

    owner = state.players[0]
    if any(":dagger:" in card for card in owner.hand):
        return state
    instance = next(card for card in owner.deck if ":dagger:" in card)
    return _seat(
        state,
        hand=(*owner.hand, instance),
        deck=tuple(card for card in owner.deck if card != instance),
    )


def test_calculated_hire_takes_the_mentat_from_the_space_the_agent_is_visiting() -> (
    None
):
    # "If the Mentat is here, take it" [DI p. 18] is a printed condition, and
    # conditions are judged when they resolve (OQ-028, imperium-base.md 16): an
    # Agent sent to the Mentat space with the Mentat resting arms the take, and
    # Calculated Hire played before it takes the Mentat first -- the space's
    # take then finds nothing there, so it waits greyed out and the turn's end
    # lapses it (like Shipping's blocked Influence); the card draw is the
    # visit's other effect and stays.
    engine, state = _hire_hand()
    state = _with_dagger(_seat(state, resources=Resources(solari=2, spice=1)))
    placement = next(
        placement
        for placement in executable_placements(state, 0)
        if dict(placement.arguments)["space_id"] == "mentat"
    )
    placed = apply_placement(engine, state, placement).state
    resolve = DomainAction("resolve_board_effect", 0, (("effect", "mentat"),))
    assert resolve in engine.whole_actions(placed, 0)

    hired = apply_whole(engine, placed, _play(HIRE)).state
    assert hired.players[0].mentat
    offered = engine.whole_actions(hired, 0)
    assert resolve not in offered
    assert DomainAction("resolve_board_effect", 0, (("effect", "cards"),)) in offered

    drawn = apply_whole(
        engine,
        hired,
        DomainAction("resolve_board_effect", 0, (("effect", "cards"),)),
    ).state
    boxed = apply_whole(
        engine, drawn, DomainAction("resolve_agent_card_effect", 0)
    ).state
    finished = apply_whole(engine, boxed, DomainAction("finish_agent_turn", 0))
    lapsed = [e for e in finished.events if e.kind == "board_effect_lapsed"]
    assert [dict(event.payload)["effect"] for event in lapsed] == ["mentat"]
    # One Agent on the Mentat space, one on the Leader: the Mentat's.
    owner = finished.state.players[0]
    assert owner.mentat
    assert owner.agents_available == 2


def test_the_mentat_icon_key_agrees_between_the_two_modules() -> None:
    from dune_imperium.rules.board_effects import BOARD_ICON_MENTAT
    from dune_imperium.rules.effects import MENTAT_BOARD_ICON

    assert MENTAT_BOARD_ICON == BOARD_ICON_MENTAT


def test_calculated_hire_mentat_goes_home_at_recall() -> None:
    # "Phase 5 Recall에 제 칸으로 돌린다" (imperium-base.md 9): at the round's
    # end the Mentat returns to its space, the Leader holds the printed number of
    # Agents again and the space rests.
    engine, state = _hire_hand()
    taken = apply_whole(engine, state, _play(HIRE)).state
    assert taken.players[0].mentat
    cleaned = replace(
        taken,
        decision_stack=(),
        phase=GamePhase.RECALL_OR_ENDGAME,
        players=tuple(replace(player, has_revealed=True) for player in taken.players),
    )
    after = resolve_recall_or_endgame(cleaned).state
    assert not after.players[0].mentat
    assert after.players[0].agents_available == 2
    assert mentat_rests(after)


def test_calculated_hire_rows_have_codec_templates() -> None:
    engine, state = _hire_hand()
    codec = ActionCodec(CONFIG)
    for action in engine.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action
    assert _play(HIRE) in engine.whole_actions(state, 0)
    # Staged, the play is the Plot window's own effect row.
    assert DomainAction(
        "play", 0, (("printed", "plot"), ("source", "intrigue"))
    ) in engine.legal_actions(state, 0)
