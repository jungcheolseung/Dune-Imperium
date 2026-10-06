"""Plot Intrigue play through the composable effect DSL."""

import itertools
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents import HeuristicAgent
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    DeployFromGarrison,
    DrawIntrigueCards,
    DrawPersonalCards,
    IntrigueTiming,
    PlaceSpy,
    RecruitTroops,
    SummonSandworm,
    TakeContract,
)
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    intrigue_card_for_instance,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.engine import IllegalActionError, Transition
from dune_imperium.core.observation import observe_state
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import (
    apply_imperium_acquisition,
    legal_imperium_acquisitions,
)
from dune_imperium.rules.agent_effects import spice_gained_this_turn
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.combat_deployment import legal_combat_deployments
from dune_imperium.rules.effect_interpreter import OptionBlock, option_unplayable_reason
from dune_imperium.rules.frames import FrameKind, end_turn_start
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_play,
    legal_intrigue_play_actions,
)
from dune_imperium.rules.reveal_turn import (
    apply_reveal_spy_action,
    legal_reveal_spy_actions,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/support/turn_end.py's module docstring).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from turn_end import finish_agent_turn  # type: ignore[import-not-found]  # noqa: E402


def _intrigue(card_id: str, copy: int = 0) -> str:
    return f"intrigue:{card_id}:{copy}"


def _starter(card_id: str, player: int = 0) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(player)
        if f":{card_id}:" in instance_id
    )


def _turn_state(
    owner: PlayerState,
    *,
    intrigue_deck: tuple[str, ...] = (),
    intrigue_discard: tuple[str, ...] = (),
) -> GameState:
    return GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        intrigue_deck=intrigue_deck,
        intrigue_discard=intrigue_discard,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _after_plot(state: GameState) -> tuple[DecisionFrame, ...]:
    """The stack a Plot played through the engine from ``state``'s turn
    start returns to: the same turn frame, with the start of the turn over
    (OQ-095 (6), user ruling 2026-10-04)."""

    return end_turn_start(state, 0).decision_stack


def _play(state: GameState, card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def test_transcribed_intrigue_options_are_well_formed() -> None:
    transcribed = [entry for entry in INTRIGUE_CARDS if entry.play_data_complete]

    # Every Uprising identity and the 11 Immortality cards; Bloodlines cards
    # join as they are transcribed.
    assert (
        sum(
            not entry.bloodlines_only and not entry.immortality_only
            for entry in transcribed
        )
        == 39
    )
    assert sum(entry.immortality_only for entry in transcribed) == 11
    for entry in transcribed:
        assert entry.options
        for option in entry.options:
            assert option.timing in IntrigueTiming
            assert all(section.rewards for section in option.sections)
    assert intrigue_card_for_instance(_intrigue("contingency_plan", 2)).timings == {
        IntrigueTiming.PLOT,
        IntrigueTiming.COMBAT,
    }


def test_every_intrigue_identity_is_transcribed() -> None:
    # Bloodlines cards are transcribed slice by slice (M12) and stay out of
    # the deck until then.
    assert all(
        entry.play_data_complete
        for entry in INTRIGUE_CARDS
        if not entry.bloodlines_only and not entry.immortality_only
    )


def test_only_the_turn_owner_may_play_plot_intrigue() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    assert legal_intrigue_play_actions(state, 1) == ()
    with pytest.raises(IllegalActionError):
        UprisingRulesEngine().apply(state, replace(_play(state, card), actor=1))


def test_plot_intrigue_is_not_offered_outside_player_turns() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = replace(_turn_state(owner), phase=GamePhase.COMBAT)

    assert legal_intrigue_play_actions(state, 0) == ()


def test_contingency_plan_plot_option_gains_two_solari_and_is_discarded() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)

    # Only the Plot half is offered during Player Turns.
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)

    result = apply_intrigue_play(state, _play(state, card, 0))

    assert result.state.players[0].resources.solari == 2
    assert result.state.players[0].intrigue_cards == ()
    assert result.state.intrigue_discard == (card,)
    assert [event.kind for event in result.events] == ["intrigue_played"]
    assert result.events[0].visible_to is None
    # The turn frame is untouched: the owner still chooses an Agent or Reveal turn.
    assert result.state.decision_stack == state.decision_stack


def test_councilors_ambition_requires_a_high_council_seat() -> None:
    card = _intrigue("councilor_s_ambition")
    without_seat = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(without_seat), 0) == ()

    with_seat = replace(without_seat, high_council=True)
    state = _turn_state(with_seat)
    result = apply_intrigue_play(state, _play(state, card))

    assert result.state.players[0].resources.water == 3


def test_market_opportunity_offers_each_affordable_exchange() -> None:
    card = _intrigue("market_opportunity")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=2)
    )
    state = _turn_state(owner)

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)

    result = apply_intrigue_play(state, _play(state, card, 0))
    assert result.state.players[0].resources == Resources(solari=5, spice=0, water=1)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "intrigue_cost_paid",
    ]

    rich = _turn_state(replace(owner, resources=Resources(solari=5, spice=2)))
    assert legal_intrigue_play_actions(rich, 0) == (
        _play(rich, card, 0),
        _play(rich, card, 1),
    )
    swapped = apply_intrigue_play(rich, _play(rich, card, 1))
    assert swapped.state.players[0].resources == Resources(solari=0, spice=7, water=1)


def test_shaddams_favor_conditional_section_applies_independently() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    plain = apply_intrigue_play(_turn_state(owner), _play(_turn_state(owner), card))
    assert plain.state.players[0].troops_garrison == 4
    assert plain.state.players[0].resources.solari == 0

    loyal = replace(owner, influence=Influence(emperor=3))
    state = _turn_state(loyal)
    favored = apply_intrigue_play(state, _play(state, card))
    assert favored.state.players[0].troops_garrison == 4
    assert favored.state.players[0].resources.solari == 3



# "To play an Intrigue card, you must meet its conditions and pay its costs."
# [FAQ p. 2] (docs/rules/player-turns.md), and the user's ruling of
# 2026-10-06 that an Intrigue option also needs an effect that can change
# something now ("아무 효과 없이 책략을 쓸 수 없는거지"); the option's other
# effects fizzle when it is played.


def test_shaddams_favor_recruit_needs_a_troop_it_can_take() -> None:
    # A recruit with no troop in the supply changes nothing, in a player turn
    # too: a recorded shortfall does not count (main-session decision on the
    # 2026-10-06 ruling, as the Arrakeen Scouts recruit, OQ-071).
    card = _intrigue("shaddam_s_favor")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), troops_supply=0, troops_garrison=12
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == ()
    assert option_unplayable_reason(state, 0, option) == RecruitTroops(count=1)

    # With Emperor 3 its 3 Solari still change something; the troop falls
    # short.
    loyal = _turn_state(replace(owner, influence=Influence(emperor=3)))
    assert legal_intrigue_play_actions(loyal, 0) == (_play(loyal, card),)
    played = apply_intrigue_play(loyal, _play(loyal, card))
    assert played.state.players[0].resources.solari == 3
    assert "troops_recruit_short" in [event.kind for event in played.events]

    # Under Immortality a specimen may be returned to the supply first
    # [Immortality p. 8].
    base = _turn_state(owner)
    immortal = replace(
        base,
        config=RulesetConfig(immortality=True),
        players=(replace(owner, troops_garrison=11, specimens=1), *base.players[1:]),
    )
    assert legal_intrigue_play_actions(immortal, 0) == (_play(immortal, card),)


def _use_line(section: int, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="use_intrigue_effect", actor=actor, arguments=(("section", section),)
    )


def _finish_lines(actor: int = 0) -> DomainAction:
    return DomainAction(action_id="finish_intrigue_effects", actor=actor)


def test_strategic_stockpiling_lines_are_used_and_paid_separately() -> None:
    # Two arrow lines with no "—OR—" (OQ-058, user ruling): playing the card
    # opens its lines; each is paid when used. At least one must be used
    # (OQ-058, user ruling 2026-10-04): the card cannot be finished before.
    card = _intrigue("strategic_stockpiling")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=5)
    )
    engine = UprisingRulesEngine()
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_effects"
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    paid = engine.apply(opened, _use_line(0)).state
    assert paid.players[0].victory_points == 2
    assert paid.players[0].resources.spice == 0
    # Without Fremen 3 no line can follow: the card closes on its own.
    assert paid.decision_stack[-1].kind == "turn"
    assert card in paid.intrigue_discard

    # With Fremen 3 the Water line is open too but not mandatory: short of
    # water the owner finishes with the Spice line alone.
    fremen = _turn_state(replace(owner, influence=Influence(fremen=3)))
    opened = engine.apply(fremen, _play(fremen, card)).state
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    paid = engine.apply(opened, _use_line(0)).state
    assert engine.legal_actions(paid, 0) == (_finish_lines(),)
    done = engine.apply(paid, _finish_lines()).state
    assert done.players[0].victory_points == 2
    assert card in done.intrigue_discard

    funded = _turn_state(
        replace(
            owner,
            influence=Influence(fremen=3),
            resources=Resources(spice=5, water=3),
        )
    )
    opened = engine.apply(funded, _play(funded, card)).state
    assert engine.legal_actions(opened, 0) == (_use_line(0), _use_line(1))
    # After either line the other is optional.
    water = engine.apply(opened, _use_line(1)).state
    assert engine.legal_actions(water, 0) == (_finish_lines(), _use_line(0))
    both = engine.apply(water, _use_line(0)).state
    assert both.players[0].victory_points == 3
    assert both.players[0].resources == Resources(spice=0, water=0)
    assert both.decision_stack[-1].kind == "turn"


def test_depart_for_arrakis_draws_at_once_and_recruits_on_its_spice_line() -> None:
    card = _intrigue("depart_for_arrakis")
    deck = (_starter("dagger"),)
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=2),
        influence=Influence(spacing_guild=3),
        deck=deck,
    )
    engine = UprisingRulesEngine()
    state = _turn_state(owner)

    # The cost-free Guild line resolves as the card is played (OQ-058); the
    # Spice line waits to be used.
    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].hand == deck
    assert opened.decision_stack[-1].kind == "intrigue_effects"
    # The draw is a line used, so the Spice line is optional (OQ-058, user
    # ruling 2026-10-04).
    assert engine.legal_actions(opened, 0) == (_finish_lines(), _use_line(0))
    recruited = engine.apply(opened, _use_line(0)).state
    player = recruited.players[0]
    assert player.troops_garrison == 6
    assert player.troops_supply == 6
    assert player.resources.spice == 0
    assert card in recruited.intrigue_discard

    # Without spice the Guild draw alone makes the card playable.
    broke = _turn_state(replace(owner, resources=Resources()))
    assert legal_intrigue_play_actions(broke, 0) == (_play(broke, card),)
    drawn = engine.apply(broke, _play(broke, card)).state
    assert drawn.players[0].hand == deck
    assert engine.legal_actions(drawn, 0) == (_finish_lines(),)


def test_depart_for_arrakis_below_guild_three_must_use_its_spice_line() -> None:
    # At least one line must be used (OQ-058, user ruling 2026-10-04, "최소
    # 한 줄은 써야 함", as the Steam app does): "To play an Intrigue card,
    # you must meet its conditions and pay its costs" [FAQ pp. 2-3]. Below
    # Guild 3 nothing resolves at play, so the Spice line is the only one.
    card = _intrigue("depart_for_arrakis")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=2)
    )
    engine = UprisingRulesEngine()
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_effects"
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    with pytest.raises(IllegalActionError):
        engine.apply(opened, _finish_lines())
    recruited = engine.apply(opened, _use_line(0)).state
    assert recruited.players[0].troops_garrison == 6
    assert recruited.players[0].resources.spice == 0
    # No line can follow: the card closes on its own.
    assert recruited.decision_stack[-1].kind == "turn"
    assert card in recruited.intrigue_discard



def test_depart_for_arrakis_with_neither_line_live_is_not_offered() -> None:
    # The Spice line cannot be paid and the Guild draw has no card to draw:
    # no line can change anything, so the card is not offered (OQ-058).
    card = _intrigue("depart_for_arrakis")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), influence=Influence(spacing_guild=3)
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == ()
    assert option_unplayable_reason(state, 0, option) is OptionBlock.NO_LINE
    # A card in the discard pile is enough for the draw.
    reshuffle = _turn_state(replace(owner, discard_pile=(_starter("dagger"),)))
    assert legal_intrigue_play_actions(reshuffle, 0) == (_play(reshuffle, card),)
    # A Spice line with no troop to recruit changes nothing either.
    empty = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=2),
        troops_supply=0,
        troops_garrison=12,
    )
    assert legal_intrigue_play_actions(_turn_state(empty), 0) == ()


def test_depart_for_arrakis_dead_draw_line_is_not_counted_as_used() -> None:
    # With Guild 3 but nothing to draw, the cost-free line is neither resolved
    # nor counted as used, so the Spice line must still be used (OQ-058, "최소
    # 한 줄은 써야 함").
    card = _intrigue("depart_for_arrakis")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=2),
        influence=Influence(spacing_guild=3),
    )
    engine = UprisingRulesEngine()
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].hand == ()
    assert opened.decision_stack[-1].kind == "intrigue_effects"
    assert dict(opened.decision_stack[-1].context)["used"] == ""
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    with pytest.raises(IllegalActionError):
        engine.apply(opened, _finish_lines())
    recruited = engine.apply(opened, _use_line(0)).state
    assert recruited.players[0].troops_garrison == 6
    assert recruited.players[0].resources.spice == 0
    assert recruited.decision_stack[-1].kind == "turn"
    assert card in recruited.intrigue_discard


@pytest.mark.parametrize(
    "card_id", ["change_allegiances", "strategic_stockpiling", "depart_for_arrakis"]
)
def test_a_played_lines_card_offers_a_line_before_it_can_be_finished(
    card_id: str,
) -> None:
    # The card is playable only with a usable line (OQ-058), and nothing acts
    # between the play and the owner's first choice, so before any line is
    # used a line is always offered and finishing never is (OQ-058, user
    # ruling 2026-10-04). The heuristic drives every playable case through
    # without meeting an empty legal list. Find Weakness and Questionable
    # Methods resolve their sword line at play, so they finish at once.
    card = _intrigue(card_id)
    engine = UprisingRulesEngine()
    played = unused = 0
    for spice, water, level in itertools.product((0, 2, 3, 5), (0, 3), (0, 1, 3)):
        owner = PlayerState(
            player_id=0,
            intrigue_cards=(card,),
            resources=Resources(spice=spice, water=water),
            influence=Influence(emperor=level, spacing_guild=level, fremen=level),
        )
        state = _turn_state(owner)
        plays = legal_intrigue_play_actions(state, 0)
        if not plays:
            continue
        played += 1
        current = engine.apply(state, plays[0]).state
        agent = HeuristicAgent(seed=played)
        for _ in range(20):
            frame = current.decision_stack[-1]
            if frame.kind == FrameKind.TURN:
                break
            legal = engine.legal_actions(current, 0)
            assert legal
            if frame.kind == FrameKind.INTRIGUE_EFFECTS and not dict(
                frame.context
            ).get("used"):
                unused += 1
                assert legal and all(
                    action.action_id == "use_intrigue_effect" for action in legal
                )
            choice = agent.choose_action(observe_state(current, 0), legal)
            current = engine.apply(current, choice).state
        assert current.decision_stack[-1].kind == FrameKind.TURN
        assert card in current.intrigue_discard
    assert played and unused


def test_finishing_opens_if_no_line_can_be_used_before_any_was() -> None:
    # Dead-end guard (``intrigue_effects_finish_is_open``): unreachable in
    # play (above), so the owner's spice is taken away by hand after the
    # play. With no line left to use the card can still be finished.
    card = _intrigue("strategic_stockpiling")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=5)
    )
    engine = UprisingRulesEngine()
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    stripped = replace(
        opened,
        players=(
            replace(opened.players[0], resources=Resources()),
            *opened.players[1:],
        ),
    )
    assert engine.legal_actions(stripped, 0) == (_finish_lines(),)
    done = engine.apply(stripped, _finish_lines()).state
    assert done.decision_stack[-1].kind == "turn"
    assert card in done.intrigue_discard


def test_intelligence_report_draws_more_with_two_spies() -> None:
    card = _intrigue("intelligence_report")
    deck = (_starter("dagger"), _starter("diplomacy"))
    owner = PlayerState(player_id=0, intrigue_cards=(card,), deck=deck)
    one = apply_intrigue_play(_turn_state(owner), _play(_turn_state(owner), card))
    assert one.state.players[0].hand == deck[:1]

    spying = replace(
        owner,
        spies_supply=1,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-sietch-tabr",
        ),
    )
    state = _turn_state(spying)
    two = apply_intrigue_play(state, _play(state, card))
    assert two.state.players[0].hand == deck



def test_intelligence_report_is_not_offered_with_deck_and_discard_empty() -> None:
    card = _intrigue("intelligence_report")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    spying = replace(
        owner,
        spies_supply=1,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-sietch-tabr",
        ),
    )
    for seat in (owner, spying):
        state = _turn_state(seat)
        assert legal_intrigue_play_actions(state, 0) == ()
        assert option_unplayable_reason(state, 0, option) == DrawPersonalCards(count=1)
    # One card is enough: the second draw has nothing left and draws nothing.
    one = _turn_state(replace(spying, discard_pile=(_starter("dagger"),)))
    assert legal_intrigue_play_actions(one, 0) == (_play(one, card),)


def test_mercenaries_draws_intrigue_and_recruits_two() -> None:
    card = _intrigue("mercenaries")
    drawn = _intrigue("cunning")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner, intrigue_deck=(drawn,))

    result = apply_intrigue_play(state, _play(state, card))

    player = result.state.players[0]
    assert player.resources.solari == 0
    assert player.intrigue_cards == (drawn,)
    assert player.troops_garrison == 5
    assert result.state.intrigue_deck == ()
    assert result.state.intrigue_discard == (card,)



def test_mercenaries_with_no_intrigue_to_draw_still_recruits() -> None:
    # Only Twisted cards in the Intrigue discard pile: they are never shuffled
    # into a new deck (OQ-097), so the draw is dead, but the recruit counts.
    card = _intrigue("mercenaries")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner, intrigue_discard=(_intrigue("twisted_controlled"),))
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    result = apply_intrigue_play(state, _play(state, card))
    assert result.state.players[0].troops_garrison == 5
    assert "intrigue_draw_short" in [event.kind for event in result.events]


def test_mercenaries_is_not_offered_when_neither_reward_can_happen() -> None:
    card = _intrigue("mercenaries")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(solari=3),
        troops_supply=0,
        troops_garrison=12,
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == ()
    # The first reward in printed order is named; the Solari stay unpaid.
    assert option_unplayable_reason(state, 0, option) == DrawIntrigueCards(count=1)
    # An Intrigue card left to draw makes it playable again.
    drawable = _turn_state(owner, intrigue_deck=(_intrigue("cunning"),))
    assert legal_intrigue_play_actions(drawable, 0) == (_play(drawable, card),)


def test_intrigue_draw_reshuffles_the_discard_through_chance() -> None:
    card = _intrigue("mercenaries")
    discard = (_intrigue("cunning"), _intrigue("devour"), _intrigue("impress"))
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner, intrigue_discard=discard)
    engine = UprisingRulesEngine()

    pending = engine.apply(state, _play(state, card))

    decision = pending.next_decision
    assert isinstance(decision, ChanceDecision)
    # The card being resolved is not part of the pile that gets reshuffled.
    assert decision.options == discard
    assert pending.state.players[0].intrigue_cards == ()
    assert pending.state.intrigue_discard == (*discard, card)

    outcome = ChanceResolver(seed=3).resolve(decision)
    resolved = engine.apply(pending.state, outcome)

    assert resolved.state.intrigue_discard == (card,)
    assert resolved.state.players[0].intrigue_cards == (outcome.values[0],)
    assert resolved.state.intrigue_deck == outcome.values[1:]
    assert resolved.state.decision_stack[-1].kind == "turn"
    assert [event.kind for event in resolved.events] == [
        "intrigue_discard_shuffled",
        "intrigue_card_drawn",
    ]


def test_intrigue_draw_stops_short_when_no_cards_remain() -> None:
    card = _intrigue("mercenaries")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=3)
    )
    state = _turn_state(owner)

    result = apply_intrigue_play(state, _play(state, card))

    assert result.state.players[0].intrigue_cards == ()
    assert result.state.intrigue_discard == (card,)
    assert result.state.decision_stack[-1].kind == "turn"


def test_troops_recruited_before_placing_the_agent_may_still_be_deployed() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        troops_supply=12,
        troops_garrison=0,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    recruited = engine.apply(state, _play(state, card)).state
    assert dict(recruited.decision_stack[-1].context)["troops_recruited"] == 1
    to_arrakeen = next(
        action
        for action in engine.legal_actions(recruited, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = engine.apply(recruited, to_arrakeen).state

    assert dict(placed.decision_stack[-1].context)["troops_recruited"] == 1
    deployments = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(placed, 0)
        if action.action_id == "deploy_troops"
    }
    assert deployments == {1}


def test_intrigue_spice_trades_keep_harvest_accounting_honest() -> None:
    # Harvest Contracts count Spice gained from every source during the turn
    # [Main p. 16]: paid Spice must not hide a harvest, and gained Spice counts.
    # The seat's turn counters (spice_at_turn_start, spice_spent_turn) carry
    # it, read by rules/effects.py ``eligible_agent_contract_ids``.
    card = _intrigue("market_opportunity")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        resources=Resources(solari=5, spice=2),
        spice_at_turn_start=2,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_arrakeen = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = engine.apply(state, to_arrakeen).state
    assert placed.players[0].spice_spent_turn == 0
    assert spice_gained_this_turn(placed.players[0]) == 0

    sold = engine.apply(placed, _play(placed, card, 0)).state
    assert sold.players[0].resources.spice == 0
    assert sold.players[0].spice_spent_turn == 2
    assert spice_gained_this_turn(sold.players[0]) == 0

    bought = engine.apply(placed, _play(placed, card, 1)).state
    assert bought.players[0].resources.spice == 7
    assert bought.players[0].spice_spent_turn == 0
    assert spice_gained_this_turn(bought.players[0]) == 5


def test_reveal_turn_offers_and_immediately_reveals_a_drawn_plot_card() -> None:
    # A card drawn during the owner's own Reveal turn is revealed and used
    # at once [FAQ p. 3], so a Plot Intrigue that draws a personal card is
    # no longer withheld while the Reveal turn is open.
    report = _intrigue("intelligence_report")
    plan = _intrigue("contingency_plan")
    diplomacy = _starter("diplomacy")
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(
        player_id=0, intrigue_cards=(report, plan), deck=(diplomacy,)
    )
    state = replace(
        _turn_state(owner),
        imperium_row=(cheap,),
        imperium_deck=(_imperium_instance("maula_pistol"),),
    )
    engine = UprisingRulesEngine()

    assert _play(state, report) in engine.legal_actions(state, 0)
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    offered = {
        dict(a.arguments)["card_id"]
        for a in engine.legal_actions(revealed, 0)
        if a.action_id == "play_intrigue"
    }
    assert offered == {report, plan}
    assert legal_imperium_acquisitions(revealed, 0) == ()

    result = apply_intrigue_play(revealed, _play(revealed, report))
    played = result.state
    owner_after = played.players[0]

    # The drawn card lands directly in play, not in hand.
    assert owner_after.hand == ()
    assert owner_after.deck == ()
    assert diplomacy in owner_after.in_play
    context = dict(played.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["revealed_card_count"] == 1
    assert context["revealed_card_000"] == diplomacy
    assert "personal_card_late_revealed" in {event.kind for event in result.events}

    # Its Persuasion pays for an acquisition this same Reveal turn.
    acquisition = next(
        action
        for action in legal_imperium_acquisitions(played, 0)
        if dict(action.arguments)["instance_id"] == cheap
    )
    acquired = apply_imperium_acquisition(played, acquisition).state
    assert acquired.players[0].discard_pile == (cheap,)


def test_intrigue_card_stays_in_hand_while_its_choices_resolve() -> None:
    card = _intrigue("buy_access")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=5)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].intrigue_cards == (card,)
    assert opened.intrigue_discard == ()
    once = engine.apply(opened, _choose_faction("fremen")).state
    assert once.players[0].intrigue_cards == (card,)
    done = engine.apply(once, _choose_faction("emperor")).state
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (card,)


def test_placeholder_intrigue_ids_are_ignored_by_the_play_provider() -> None:
    owner = PlayerState(player_id=0, intrigue_cards=("intrigue:test",))
    assert legal_intrigue_play_actions(_turn_state(owner), 0) == ()


def test_troops_recruited_by_plot_during_an_agent_turn_may_be_deployed() -> None:
    card = _intrigue("shaddam_s_favor")
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(card,),
        troops_supply=12,
        troops_garrison=0,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_arrakeen = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, to_arrakeen).state

    # Plot Intrigue is offered inside the Agent-turn effect frame.
    assert _play(placed, card) in engine.legal_actions(placed, 0)
    played = engine.apply(placed, _play(placed, card)).state
    assert dict(played.decision_stack[-1].context)["troops_recruited"] == 1

    deployments = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(played, 0)
        if action.action_id == "deploy_troops"
    }
    assert deployments == {1}


def test_plot_intrigue_is_offered_during_the_reveal_turn() -> None:
    card = _intrigue("contingency_plan")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    revealed = engine.apply(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert _play(revealed, card) in engine.legal_actions(revealed, 0)

    played = engine.apply(revealed, _play(revealed, card)).state
    assert played.players[0].resources.solari == 2
    assert played.decision_stack == revealed.decision_stack


def test_every_intrigue_instance_has_a_definition() -> None:
    for instance_id in intrigue_deck_instance_ids(True):
        assert intrigue_card_for_instance(instance_id).card.card_id in instance_id
    with pytest.raises(ValueError):
        intrigue_card_for_instance("imperium:maula_pistol:0")


def _choose_faction(faction: str, recipient: int | None = None) -> DomainAction:
    arguments: tuple[tuple[str, str | int], ...] = (("faction", faction),)
    if recipient is not None:
        arguments = (("alliance_recipient", recipient), *arguments)
    return DomainAction(
        action_id="choose_intrigue_faction", actor=0, arguments=arguments
    )


def _choose_discard(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="choose_intrigue_discard", actor=0, arguments=(("card_id", card_id),)
    )


def test_buy_access_opens_two_distinct_faction_choices() -> None:
    card = _intrigue("buy_access")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=5)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card))
    assert opened.state.decision_stack[-1].kind == "intrigue_choice"
    assert opened.state.players[0].resources.solari == 0
    offered = {
        dict(a.arguments)["faction"] for a in engine.legal_actions(opened.state, 0)
    }
    assert offered == {"emperor", "spacing_guild", "bene_gesserit", "fremen"}
    # Opponents have nothing to do while the choice is open.
    assert engine.legal_actions(opened.state, 1) == ()

    first = engine.apply(opened.state, _choose_faction("fremen"))
    # "Two different Factions": both are named before either Influence moves
    # (designer ruling on "Choose two", OQ-057).
    assert first.state.players[0].influence.fremen == 0
    remaining = {
        dict(a.arguments)["faction"] for a in engine.legal_actions(first.state, 0)
    }
    assert "fremen" not in remaining and len(remaining) == 3

    second = engine.apply(first.state, _choose_faction("emperor"))
    assert second.state.players[0].influence.fremen == 1
    assert second.state.players[0].influence.emperor == 1
    assert second.state.decision_stack == _after_plot(state)
    assert second.state.intrigue_discard == (card,)
    assert second.state.players[0].intrigue_cards == ()


def test_imperium_politics_limits_the_choice_to_emperor_or_guild() -> None:
    card = _intrigue("imperium_politics")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(solari=1)
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (
        _choose_faction("emperor"),
        _choose_faction("spacing_guild"),
    )
    done = engine.apply(opened, _choose_faction("spacing_guild")).state
    assert done.players[0].influence.spacing_guild == 1
    assert done.decision_stack == _after_plot(state)


def test_imperium_politics_never_offers_a_faction_at_the_top() -> None:
    """OQ-060: a gain on a cube at 6 is lost, so the picker leaves it out;
    with both printed Factions there the Solari would buy nothing and the
    card is not offered: "비용이 있는 줄은 보상 중 하나라도 무언가를 바꿀 수
    있을 때만 제시한다" (OQ-071). Before 2026-10-06 both were offered."""

    card = _intrigue("imperium_politics")
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(solari=1),
        influence=Influence(emperor=6, spacing_guild=2),
    )
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (_choose_faction("spacing_guild"),)

    full = _turn_state(
        replace(owner, influence=Influence(emperor=6, spacing_guild=6))
    )
    assert legal_intrigue_play_actions(full, 0) == ()


def test_buy_access_pays_the_one_faction_below_the_top_and_loses_the_other() -> (
    None
):
    """"Choose two" with one Faction below the top: that one is named and
    paid, the second gain is lost and its owner confirms it, as OQ-060
    rules for a Conflict reward's "two different Factions"; with all four
    at the top the five Solari are not offered (OQ-071)."""

    card = _intrigue("buy_access")
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(solari=5),
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=3),
    )
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (_choose_faction("fremen"),)
    named = engine.apply(opened, _choose_faction("fremen")).state
    assert named.players[0].influence.fremen == 3
    confirm = DomainAction(
        action_id="resolve_intrigue_influence_without_faction", actor=0
    )
    assert engine.legal_actions(named, 0) == (confirm,)
    done = engine.apply(named, confirm)
    assert done.state.players[0].influence.fremen == 4
    assert done.state.players[0].influence.emperor == 6
    assert "intrigue_influence_unavailable" in {e.kind for e in done.events}
    assert done.state.intrigue_discard == (card,)
    assert done.state.decision_stack == _after_plot(state)

    full = _turn_state(
        replace(
            owner,
            influence=Influence(
                emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6
            ),
        )
    )
    assert legal_intrigue_play_actions(full, 0) == ()


def test_change_allegiances_regains_the_faction_it_lost_at_the_top() -> None:
    """With every cube at 6 the swap still works: the Faction just lowered
    is below the top again and is the only one offered; the spice line's
    gain would be lost, so that line is not offered (OQ-060, OQ-071)."""

    card = _intrigue("change_allegiances")
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=3),
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    losing = engine.apply(opened, _use_line(0)).state
    lost = engine.apply(losing, _choose_faction("emperor")).state
    assert lost.players[0].influence.emperor == 5
    assert engine.legal_actions(lost, 0) == (_choose_faction("emperor"),)
    regained = engine.apply(lost, _choose_faction("emperor")).state
    assert regained.players[0].influence.emperor == 6
    assert engine.legal_actions(regained, 0) == (_finish_lines(),)


def test_change_allegiances_opens_both_lines_and_either_may_be_used() -> None:
    card = _intrigue("change_allegiances")
    poor = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(poor), 0) == ()

    owner = replace(
        poor, influence=Influence(bene_gesserit=1), resources=Resources(spice=3)
    )
    state = _turn_state(owner)
    # One option: playing the card opens its two lines (OQ-058).
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card, 0)).state
    # At least one line must be used before the card can be finished
    # (OQ-058, user ruling 2026-10-04).
    assert engine.legal_actions(opened, 0) == (_use_line(0), _use_line(1))
    losing = engine.apply(opened, _use_line(0)).state
    # Only Factions where the player still has Influence can be lost.
    assert engine.legal_actions(losing, 0) == (_choose_faction("bene_gesserit"),)
    lost = engine.apply(losing, _choose_faction("bene_gesserit")).state
    assert lost.players[0].influence.bene_gesserit == 0
    gained = engine.apply(lost, _choose_faction("fremen")).state
    assert gained.players[0].influence.fremen == 1
    assert gained.players[0].resources.spice == 3
    # The Spice line is still open; the owner may finish without it.
    assert engine.legal_actions(gained, 0) == (_finish_lines(), _use_line(1))
    done = engine.apply(gained, _finish_lines()).state
    assert done.decision_stack[-1].kind == "turn"
    assert card in done.intrigue_discard
    assert done.players[0].resources.spice == 3


def test_change_allegiances_second_line_may_be_paid_with_spice_the_first_produced() -> (
    None
):
    # User ruling (OQ-058): the lines are separate actions, each paid when
    # used, so Lady Margot's Loyalty spice from the first line can pay the
    # second even though the card was played with too little spice.
    card = _intrigue("change_allegiances")
    owner = PlayerState(
        player_id=0,
        leader_id="lady_margot_fenring",
        intrigue_cards=(card,),
        influence=Influence(bene_gesserit=1, fremen=1),
        resources=Resources(spice=1),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_use_line(0),)
    losing = engine.apply(opened, _use_line(0)).state
    lost = engine.apply(losing, _choose_faction("fremen")).state
    gained = engine.apply(lost, _choose_faction("bene_gesserit")).state
    # Loyalty: reaching 2 Bene Gesserit Influence pays 2 spice.
    assert gained.players[0].influence.bene_gesserit == 2
    assert gained.players[0].resources.spice == 3
    assert engine.legal_actions(gained, 0) == (_finish_lines(), _use_line(1))
    paying = engine.apply(gained, _use_line(1)).state
    assert paying.players[0].resources.spice == 0
    second = engine.apply(paying, _choose_faction("emperor")).state
    assert second.players[0].influence.emperor == 1
    # Both lines used: the card closes on its own.
    assert second.decision_stack[-1].kind == "turn"
    assert card in second.intrigue_discard


def test_an_intrigue_s_emperor_spy_waits_in_the_turn_until_placed() -> None:
    # User ruling 2026-10-04, overriding the designer ruling OQ-057 (15)
    # ("You need to finish resolving that Spy placement before you move on
    # to other 'player initiated actions.'"): "엄연히 agent턴 내에 순서를 정해서
    # 할 수 있는 의무 행동으로 보는거지". As in the Steam app, the Emperor
    # track's Influence 4 Spy [Main p. 7] waits in the turn: the card's
    # remaining line and the turn's other actions come in any order, and
    # the turn cannot end before the Spy is placed.
    card = _intrigue("change_allegiances")
    engine = UprisingRulesEngine()

    def gain_emperor(state: GameState, line: int, lose: str = "") -> GameState:
        state = engine.apply(state, _use_line(line)).state
        if lose:
            state = engine.apply(state, _choose_faction(lose)).state
        return engine.apply(state, _choose_faction("emperor")).state

    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(emperor=2, fremen=1),
        resources=Resources(spice=3),
    )
    # The designer's example: from 2, both lines reach 4; the card closes
    # and the turn frame offers the Spy beside the turn's own choices.
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card, 0)).state
    reached = gain_emperor(gain_emperor(opened, 0, lose="fremen"), 1)
    assert reached.players[0].influence.emperor == 4
    assert reached.decision_stack[-1].kind == FrameKind.TURN
    assert [seat for seat, _ in reached.pending_track_spies] == [0]
    assert {"place_track_spy", "reveal_turn"} <= {
        a.action_id for a in engine.legal_actions(reached, 0)
    }

    # Reaching 4 with the first line: the second line is still offered, and
    # the Spy is not (only the turn's own frames offer it).
    state = _turn_state(replace(owner, influence=Influence(emperor=3, fremen=1)))
    opened = engine.apply(state, _play(state, card, 0)).state
    reached = gain_emperor(opened, 0, lose="fremen")
    assert reached.decision_stack[-1].kind == FrameKind.INTRIGUE_EFFECTS
    assert [seat for seat, _ in reached.pending_track_spies] == [0]
    assert engine.legal_actions(reached, 0) == (_finish_lines(), _use_line(1))
    second = engine.apply(reached, _use_line(1)).state
    second = engine.apply(second, _choose_faction("bene_gesserit")).state
    assert second.players[0].influence.bene_gesserit == 1
    assert second.decision_stack[-1].kind == FrameKind.TURN
    assert [a.action_id for a in engine.legal_actions(second, 0)] == [
        "reveal_turn",
        "place_track_spy",
    ]

    # The turn goes on; its end waits for the Spy.
    revealed = engine.apply(second, DomainAction("reveal_turn", 0)).state
    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL
    assert [a.action_id for a in engine.legal_actions(revealed, 0)] == [
        "place_track_spy"
    ]
    opening = engine.apply(revealed, DomainAction("place_track_spy", 0)).state
    assert opening.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT
    assert opening.pending_track_spies == ()
    posts = engine.legal_actions(opening, 0)
    assert {a.action_id for a in posts} == {"place_spy_on_space"}
    placed = engine.apply(opening, posts[0]).state
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert [a.action_id for a in engine.legal_actions(placed, 0)] == [
        "finish_reveal"
    ]


def test_losing_influence_for_intrigue_offers_alliance_recipients() -> None:
    card = _intrigue("change_allegiances")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(fremen=4),
        alliance_faction_ids=("fremen",),
    )
    rivals = (
        PlayerState(player_id=1, influence=Influence(fremen=4)),
        PlayerState(player_id=2, influence=Influence(fremen=4)),
        PlayerState(player_id=3),
    )
    state = replace(_turn_state(owner), players=(owner, *rivals))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    losing = engine.apply(opened, _use_line(0)).state
    assert engine.legal_actions(losing, 0) == (
        _choose_faction("fremen", recipient=1),
        _choose_faction("fremen", recipient=2),
    )
    lost = engine.apply(losing, _choose_faction("fremen", recipient=2)).state
    assert lost.players[0].alliance_faction_ids == ()
    assert lost.players[2].alliance_faction_ids == ("fremen",)


def test_opportunism_loses_two_influence_and_pays_solari_for_a_point() -> None:
    card = _intrigue("opportunism")
    short = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(emperor=1),
        resources=Resources(solari=2),
    )
    assert legal_intrigue_play_actions(_turn_state(short), 0) == ()

    owner = replace(short, influence=Influence(emperor=2))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].resources.solari == 0
    once = engine.apply(opened, _choose_faction("emperor")).state
    assert once.players[0].influence.emperor == 1
    # Dropping below two Influence forfeits the Friendship Victory Point.
    assert once.players[0].victory_points == 0
    twice = engine.apply(once, _choose_faction("emperor")).state
    assert twice.players[0].influence.emperor == 0
    assert twice.players[0].victory_points == 1
    assert twice.decision_stack == _after_plot(state)


def test_sietch_ritual_discards_a_hand_card_then_chooses_a_faction() -> None:
    card = _intrigue("sietch_ritual")
    favor = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if ":spacing_guild_s_favor:" in instance_id
    )
    empty_handed = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(empty_handed), 0) == ()

    owner = replace(empty_handed, hand=(_starter("dagger"), favor))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (
        _choose_discard(_starter("dagger")),
        _choose_discard(favor),
    )
    discarded = engine.apply(opened, _choose_discard(favor)).state
    assert discarded.players[0].discard_pile == (favor,)
    # The hand-discard trigger of Spacing Guild's Favor still fires.
    assert discarded.players[0].resources.spice == 2
    assert engine.legal_actions(discarded, 0) == (
        _choose_faction("bene_gesserit"),
        _choose_faction("fremen"),
    )
    done = engine.apply(discarded, _choose_faction("bene_gesserit")).state
    assert done.players[0].influence.bene_gesserit == 1
    assert done.intrigue_discard == (card,)


def test_backed_by_choam_plot_half_trades_influence_for_solari() -> None:
    card = _intrigue("backed_by_choam")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), influence=Influence(spacing_guild=2)
    )
    state = replace(_turn_state(owner), config=RulesetConfig(choam_module=True))
    engine = UprisingRulesEngine()

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
    opened = engine.apply(state, _play(state, card, 0)).state
    done = engine.apply(opened, _choose_faction("spacing_guild")).state
    assert done.players[0].influence.spacing_guild == 1
    assert done.players[0].resources.solari == 4


def test_owed_intrigue_draws_reshuffle_the_discard_before_the_next_decision() -> None:
    # Assembly Hall's board effect draws an Intrigue card. With the deck empty
    # the dispatcher shuffles the discard into a new deck [FAQ p. 2] and then
    # completes the draw before the owner's next decision.
    discard = (_intrigue("cunning"), _intrigue("devour"))
    owner = PlayerState(player_id=0, hand=(_starter("dagger"),))
    state = _turn_state(owner, intrigue_discard=discard)
    engine = UprisingRulesEngine()
    to_hall = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = engine.apply(state, to_hall).state

    pending = engine.apply(placed, _board_icon_action("intrigue"))
    decision = pending.next_decision
    assert isinstance(decision, ChanceDecision)
    assert decision.options == discard
    assert pending.state.pending_intrigue_draws == ()

    outcome = ChanceResolver(seed=5).resolve(decision)
    resolved = engine.apply(pending.state, outcome)
    assert resolved.state.players[0].intrigue_cards == (outcome.values[0],)
    assert resolved.state.intrigue_discard == ()
    # The board effect was the last pending group: the owner's turn stays
    # open with only its end left, and the press passes the turn on (user
    # ruling OQ-095 (1)).
    top = resolved.state.decision_stack[-1]
    assert top.kind == FrameKind.AGENT_EFFECTS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 0
    assert DomainAction("finish_agent_turn", 0) in engine.legal_actions(
        resolved.state, 0
    )
    top = finish_agent_turn(resolved.state).decision_stack[-1]
    assert top.kind == "turn" and isinstance(top.decision, PlayerDecision)
    assert top.decision.owner == 1


def test_owed_intrigue_draw_stops_short_with_nothing_to_shuffle() -> None:
    owner = PlayerState(player_id=0, hand=(_starter("dagger"),))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    to_hall = next(
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "agent_turn"
        and dict(action.arguments)["space_id"] == "assembly_hall"
    )
    placed = engine.apply(state, to_hall).state

    done = engine.apply(placed, _board_icon_action("intrigue"))

    assert done.state.players[0].intrigue_cards == ()
    assert done.state.pending_intrigue_draws == ()
    # The turn stays open until its owner presses the end (OQ-095).
    assert done.state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert finish_agent_turn(done.state).decision_stack[-1].kind == "turn"


def _conflict(protected: bool) -> str:
    from dune_imperium.content.uprising.conflicts import CONFLICTS

    return next(
        conflict.card.card_id
        for conflict in CONFLICTS
        if conflict.shield_wall_protected is protected
    )


def _detonate() -> DomainAction:
    return DomainAction(action_id="detonate_shield_wall", actor=0)


def _keep_wall() -> DomainAction:
    return DomainAction(action_id="keep_shield_wall", actor=0)


def _deploy(count: int) -> DomainAction:
    return DomainAction(
        action_id="deploy_intrigue_troops", actor=0, arguments=(("count", count),)
    )


def test_detonation_may_remove_the_shield_wall_or_keep_it() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    # Option 0 is the detonation icon, option 1 the garrison deployment
    # (unavailable here: the garrison holds troops, so it is offered too).
    offered = legal_intrigue_play_actions(state, 0)
    assert _play(state, card, 0) in offered

    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_detonate(), _keep_wall())

    detonated = engine.apply(opened, _detonate())
    assert detonated.state.shield_wall_present is False
    assert "shield_wall_destroyed" in [e.kind for e in detonated.events]
    assert detonated.state.intrigue_discard == (card,)

    kept = engine.apply(opened, _keep_wall()).state
    assert kept.shield_wall_present is True
    assert kept.intrigue_discard == (card,)

    # Once the token is gone the detonation option has nothing to do.
    gone = replace(_turn_state(owner), shield_wall_present=False)
    assert legal_intrigue_play_actions(gone, 0) == (_play(gone, card, 1),)


def test_detonation_deploys_up_to_four_garrison_troops() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(player_id=0, intrigue_cards=(card,), troops_garrison=3)
    state = replace(
        _turn_state(replace(owner, troops_supply=9)),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    # "Deploy up to four troops" [card face]: zero is a choice too.
    assert engine.legal_actions(opened, 0) == (
        _deploy(0),
        _deploy(1),
        _deploy(2),
        _deploy(3),
    )

    deployed = engine.apply(opened, _deploy(3)).state
    assert deployed.players[0].troops_garrison == 0
    assert deployed.players[0].troops_conflict == 3
    assert deployed.decision_stack[-1].kind == "turn"

    # An empty garrison bars the line: it could change nothing (user ruling
    # 2026-10-06); only the detonation is offered.
    empty = PlayerState(
        player_id=0, intrigue_cards=(card,), troops_supply=12, troops_garrison=0
    )
    empty_state = _turn_state(empty)
    assert legal_intrigue_play_actions(empty_state, 0) == (_play(state, card, 0),)


def _with_turn_context(state: GameState, **context: object) -> GameState:
    """The owner's turn frame with ``context`` (a deployment block, say)."""

    frame = state.decision_stack[-1]
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),  # type: ignore[arg-type]
        ),
    )


def test_detonation_deploy_line_needs_a_deployable_garrison_unit() -> None:
    # "Deploy up to four troops from your garrison" [card face] with nothing
    # it may deploy changes nothing: an empty garrison, Emperor of the Known
    # Universe's block for the turn [Main p. 17], or only Harkonnen
    # Advisor's troop (OQ-038). Once played, zero stays a choice.
    card = _intrigue("detonation")
    option = intrigue_card_for_instance(card).options[1]
    engine = UprisingRulesEngine()
    empty = _turn_state(
        PlayerState(
            player_id=0, intrigue_cards=(card,), troops_supply=12, troops_garrison=0
        )
    )
    garrisoned = _turn_state(
        PlayerState(
            player_id=0, intrigue_cards=(card,), troops_supply=10, troops_garrison=2
        )
    )
    blocked = _with_turn_context(garrisoned, units_deploy_blocked=True)
    advisor = _with_turn_context(
        _turn_state(
            PlayerState(
                player_id=0, intrigue_cards=(card,), troops_supply=11, troops_garrison=1
            )
        ),
        undeployable_troops=1,
    )
    for state in (empty, blocked, advisor):
        assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
        assert option_unplayable_reason(state, 0, option) == DeployFromGarrison(
            up_to=4
        )
        # With the Shield Wall gone the card has nothing to play.
        assert legal_intrigue_play_actions(
            replace(state, shield_wall_present=False), 0
        ) == ()

    assert _play(garrisoned, card, 1) in legal_intrigue_play_actions(garrisoned, 0)
    opened = engine.apply(garrisoned, _play(garrisoned, card, 1)).state
    assert engine.legal_actions(opened, 0) == (_deploy(0), _deploy(1), _deploy(2))


def test_units_deployed_by_plot_during_reveal_count_toward_strength() -> None:
    card = _intrigue("detonation")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(_starter("dagger"),),
        troops_garrison=3,
        troops_supply=9,
    )
    state = replace(_turn_state(owner), current_conflict_ids=(_conflict(False),))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state
    # Dagger reveals for one sword, but with no units it does not count yet.
    assert revealed.players[0].combat_strength == 0

    opened = engine.apply(revealed, _play(revealed, card, 1)).state
    deployed = engine.apply(opened, _deploy(2)).state

    assert deployed.players[0].troops_conflict == 2
    # Two troops (4) plus the revealed sword (1).
    assert deployed.players[0].combat_strength == 5
    reveal_frame = next(f for f in deployed.decision_stack if f.kind == "reveal")
    assert dict(reveal_frame.context)["strength"] == 5


def test_unexpected_allies_detonates_then_summons_a_sandworm() -> None:
    card = _intrigue("unexpected_allies")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(water=2)
    )
    state = replace(_turn_state(owner), current_conflict_ids=(_conflict(True),))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].resources.water == 0
    assert engine.legal_actions(opened, 0) == (
        _detonate(),
        _keep_wall(),
        DomainAction(action_id="resolve_intrigue_rewards", actor=0),
    )

    summoned = engine.apply(opened, _detonate())
    assert summoned.state.shield_wall_present is False
    assert summoned.state.players[0].sandworms_conflict == 1
    assert [e.kind for e in summoned.events] == [
        "shield_wall_destroyed",
        "sandworm_deployed",
    ]

    # Keeping the wall leaves the protected Conflict untouched [Main p. 20].
    blocked = engine.apply(opened, _keep_wall())
    assert blocked.state.players[0].sandworms_conflict == 0
    assert blocked.state.players[0].resources.water == 0
    assert "sandworm_summon_unavailable" in [e.kind for e in blocked.events]


def test_unexpected_allies_without_a_wall_summons_directly() -> None:
    card = _intrigue("unexpected_allies")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(_starter("dagger"),),
        resources=Resources(water=2),
    )
    state = replace(
        _turn_state(owner),
        shield_wall_present=False,
        current_conflict_ids=(_conflict(True),),
    )
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0)).state

    done = engine.apply(revealed, _play(revealed, card)).state

    assert done.players[0].sandworms_conflict == 1
    # Sandworm (3) plus the revealed sword (1), no choice frame was needed.
    assert done.players[0].combat_strength == 4
    assert done.decision_stack[-1].kind == "reveal"



def test_unexpected_allies_without_the_wall_needs_a_deployable_sandworm() -> None:
    # With the Shield Wall gone only the sandworm is left, and it changes
    # nothing while Emperor of the Known Universe blocks deployment
    # [Main p. 17] or with no Conflict this round.
    card = _intrigue("unexpected_allies")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(water=2)
    )
    open_field = replace(
        _turn_state(owner),
        shield_wall_present=False,
        current_conflict_ids=(_conflict(False),),
    )
    assert legal_intrigue_play_actions(open_field, 0) == (_play(open_field, card),)
    blocked = _with_turn_context(open_field, units_deploy_blocked=True)
    no_conflict = replace(open_field, current_conflict_ids=())
    for state in (blocked, no_conflict):
        assert legal_intrigue_play_actions(state, 0) == ()
        assert option_unplayable_reason(state, 0, option) == SummonSandworm()

    # With the wall standing the detonation is an effect of its own, so the
    # card is played and the sandworm fizzles.
    walled = _with_turn_context(
        replace(_turn_state(owner), current_conflict_ids=(_conflict(False),)),
        units_deploy_blocked=True,
    )
    engine = UprisingRulesEngine()
    opened = engine.apply(walled, _play(walled, card)).state
    summoned = engine.apply(opened, _detonate())
    assert summoned.state.shield_wall_present is False
    assert summoned.state.players[0].sandworms_conflict == 0
    assert "sandworm_summon_unavailable" in [e.kind for e in summoned.events]


def _trash(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="trash_intrigue_card", actor=0, arguments=(("card_id", card_id),)
    )


def _place_spy(post_id: str) -> DomainAction:
    return DomainAction(
        action_id="place_intrigue_spy", actor=0, arguments=(("post_id", post_id),)
    )


def _recall_spy(post_id: str) -> DomainAction:
    return DomainAction(
        action_id="recall_spy_for_intrigue", actor=0, arguments=(("post_id", post_id),)
    )


def test_cunning_offers_a_free_draw_or_a_paid_draw_with_optional_trash() -> None:
    card = _intrigue("cunning")
    dagger = _starter("dagger")
    deck = (_starter("diplomacy"),)
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(dagger,),
        discard_pile=(_starter("reconnaissance"),),
        deck=deck,
        resources=Resources(spice=1),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    free = engine.apply(state, _play(state, card, 0)).state
    assert free.players[0].hand == (dagger, *deck)
    assert free.players[0].resources.spice == 1

    opened = engine.apply(state, _play(state, card, 1)).state
    assert opened.players[0].resources.spice == 0
    offered = engine.legal_actions(opened, 0)
    assert offered[0].action_id == "decline_intrigue_trash"
    assert {
        dict(a.arguments)["card_id"]
        for a in offered
        if a.action_id == "trash_intrigue_card"
    } == {
        dagger,
        _starter("reconnaissance"),
    }

    trashed = engine.apply(opened, _trash(dagger)).state
    assert trashed.players[0].trashed == (dagger,)
    assert trashed.players[0].hand == deck
    assert trashed.intrigue_discard == (card,)

    declined = engine.apply(
        opened, DomainAction(action_id="decline_intrigue_trash", actor=0)
    ).state
    assert declined.players[0].trashed == ()
    assert declined.players[0].hand == (dagger, *deck)


def test_cunning_owner_may_draw_first_and_trash_the_drawn_card() -> None:
    # Icons on one Intrigue line are independent effects resolved in the
    # order the owner picks (OQ-015 ruling), so resolving the draw first
    # makes the drawn card a legal trash target.
    card = _intrigue("cunning")
    dagger = _starter("dagger")
    drawn = _starter("diplomacy")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(dagger,),
        deck=(drawn,),
        resources=Resources(spice=1),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    resolved = engine.apply(
        opened, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state
    assert resolved.players[0].hand == (dagger, drawn)
    offered = engine.legal_actions(resolved, 0)
    assert "resolve_intrigue_rewards" not in {a.action_id for a in offered}
    assert drawn in {
        dict(a.arguments)["card_id"]
        for a in offered
        if a.action_id == "trash_intrigue_card"
    }

    trashed = engine.apply(resolved, _trash(drawn)).state
    assert trashed.players[0].trashed == (drawn,)
    assert trashed.players[0].hand == (dagger,)
    assert trashed.players[0].deck == ()
    assert trashed.intrigue_discard == (card,)


def test_cunning_trash_of_eliminate_allies_before_placement_joins_the_combat_turn() -> (
    None
):
    # Eliminate Allies: "When this card is trashed: 2 troops" [Eliminate
    # Allies card]. Cunning's paid option trashes from the Intrigue choice
    # frame (``apply_intrigue_choice``'s ``TrashPersonalCard`` branch), not
    # an AGENT_EFFECTS frame, so ``trash_personal_card``'s own crediting
    # never applied there: "그 turn에 어떤 출처에서 recruit했든 새 troop은
    # Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4]
    # (docs/rules/player-turns.md:137). Played before the Agent is placed,
    # the credit must reach the bare turn frame and carry into the Agent
    # turn's Combat deployment [Main p. 10].
    card = _intrigue("cunning")
    eliminate_allies = "imperium:eliminate_allies:0"
    diplomacy = _starter("diplomacy")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        hand=(eliminate_allies, diplomacy),
        deck=(_starter("reconnaissance"),),
        resources=Resources(spice=6),
    )
    state = replace(_turn_state(owner), config=RulesetConfig(bloodlines=True))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    resolved = engine.apply(
        opened, DomainAction(action_id="resolve_intrigue_rewards", actor=0)
    ).state
    trashed = engine.apply(resolved, _trash(eliminate_allies)).state

    assert trashed.decision_stack[-1].kind == "turn"
    assert trashed.players[0].troops_garrison == 3 + 2
    assert dict(trashed.decision_stack[-1].context)["troops_recruited"] == 2

    placed = engine.apply(
        trashed,
        next(
            a
            for a in legal_agent_actions(trashed, 0)
            if dict(a.arguments)["card_id"] == diplomacy
            and dict(a.arguments)["space_id"] == "heighliner"
        ),
    ).state
    assert {
        dict(a.arguments)["count"] for a in legal_combat_deployments(placed, 0)
    } == {1, 2, 3, 4}



def test_cunning_free_draw_is_not_offered_with_deck_and_discard_empty() -> None:
    card = _intrigue("cunning")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(player_id=0, intrigue_cards=(card,), hand=(_starter("dagger"),))
    state = _turn_state(owner)
    assert _play(state, card, 0) not in legal_intrigue_play_actions(state, 0)
    assert option_unplayable_reason(state, 0, option) == DrawPersonalCards(count=1)
    # A card in the discard pile is enough: the empty deck reshuffles it.
    discard = _turn_state(replace(owner, discard_pile=(_starter("diplomacy"),)))
    assert _play(discard, card, 0) in legal_intrigue_play_actions(discard, 0)


def test_cunning_paid_draw_is_offered_while_a_card_can_be_trashed() -> None:
    # Deck and discard pile empty: the draw fizzles, but the trash can still
    # take a card from hand or from play.
    card = _intrigue("cunning")
    dagger = _starter("dagger")
    engine = UprisingRulesEngine()
    for owner in (
        PlayerState(
            player_id=0,
            intrigue_cards=(card,),
            hand=(dagger,),
            resources=Resources(spice=1),
        ),
        PlayerState(
            player_id=0,
            intrigue_cards=(card,),
            in_play=(dagger,),
            resources=Resources(spice=1),
        ),
    ):
        state = _turn_state(owner)
        assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 1),)
        opened = engine.apply(state, _play(state, card, 1)).state
        offered = engine.legal_actions(opened, 0)
        assert offered[0].action_id == "decline_intrigue_trash"
        assert _trash(dagger) in offered


def test_cunning_paid_draw_is_not_offered_with_no_personal_card() -> None:
    card = _intrigue("cunning")
    option = intrigue_card_for_instance(card).options[1]
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(spice=1)
    )
    state = _turn_state(owner)
    assert legal_intrigue_play_actions(state, 0) == ()
    # The draw is named first; the spice is never paid for nothing.
    assert option_unplayable_reason(state, 0, option) == DrawPersonalCards(count=1)


_CITY_POSTS = frozenset(
    {
        "arrakis-research-station-spice-refinery",
        "arrakis-research-station-sietch-tabr",
        "arrakis-spice-refinery-arrakeen",
    }
)


def test_special_mission_places_a_spy_on_a_city_post() -> None:
    # The card prints "[Spy] on [City disc]" (the blue-violet disc is the
    # City Agent icon, not the Bene Gesserit ornament) [Special Mission
    # card]; '"[Spy] on [City]" means the observation post must connect to
    # a [City] board space' [Main p. 20]. It used to target the Bene
    # Gesserit post.
    card = _intrigue("special_mission")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    offered = engine.legal_actions(opened, 0)
    # With a Spy in the supply the placement is mandatory: the designer's
    # erratum to [Main p. 11] ("The word 'may' is incorrectly used here. It
    # is mandatory to place a Spy if you have at least one Spy in your
    # supply", Hidden Assets Discord; adopted with OQ-057).
    assert {a.action_id for a in offered} == {"place_intrigue_spy"}
    targets = {
        str(dict(a.arguments)["post_id"])
        for a in offered
        if a.action_id == "place_intrigue_spy"
    }
    assert targets == _CITY_POSTS
    assert "bene-gesserit-espionage-secrets" not in targets
    post = sorted(targets)[0]
    placed = engine.apply(opened, _place_spy(post)).state
    assert placed.players[0].spy_post_ids == (post,)
    assert placed.players[0].spies_supply == 2
    assert placed.intrigue_discard == (card,)


def test_special_mission_spy_placement_can_only_be_declined_without_a_spy() -> None:
    # Placing is mandatory with a Spy in the supply (the erratum to [Main
    # p. 11], OQ-057); with an empty supply the recall that would free one is
    # the owner's choice ("you may first recall one of your Spies" [Main
    # pp. 11, 20]), so the slot can be declined there.
    card = _intrigue("special_mission")
    engine = UprisingRulesEngine()
    supplied = _turn_state(PlayerState(player_id=0, intrigue_cards=(card,)))
    opened = engine.apply(supplied, _play(supplied, card, 0)).state
    with pytest.raises(ValueError):
        engine.apply(opened, DomainAction(action_id="decline_intrigue_spy", actor=0))

    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
        ),
    )
    state = _turn_state(owner)
    opened = engine.apply(state, _play(state, card, 0)).state
    declined = engine.apply(
        opened, DomainAction(action_id="decline_intrigue_spy", actor=0)
    ).state

    assert declined.players[0].spy_post_ids == owner.spy_post_ids
    assert declined.players[0].spies_supply == 0
    assert declined.intrigue_discard == (card,)
    assert declined.decision_stack[-1].kind == "turn"


def test_special_mission_recalls_first_when_no_spy_is_in_supply() -> None:
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "landsraad-assembly-hall-gather-support",
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
        ),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    # The preparatory recall is optional [Main pp. 11, 20].
    assert {a.action_id for a in engine.legal_actions(opened, 0)} == {
        "recall_spy_for_intrigue",
        "decline_intrigue_spy",
    }
    recalled = engine.apply(
        opened, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert recalled.players[0].spies_supply == 1
    # The slot is still open: only the placement remains (the recalled Spy is
    # in the supply, so it has to be placed), and exactly one Spy can be
    # recalled per placement [Main p. 11].
    assert {a.action_id for a in engine.legal_actions(recalled, 0)} == {
        "place_intrigue_spy",
    }


def _city_posts_held_by_rivals(state: GameState) -> GameState:
    """Fill the two City posts the owner does not watch with rival Spies."""

    first = replace(
        state.players[1],
        spies_supply=2,
        spy_post_ids=("arrakis-research-station-sietch-tabr",),
    )
    second = replace(
        state.players[2],
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )
    return replace(state, players=(state.players[0], first, second, state.players[3]))


def test_special_mission_shared_post_does_not_make_the_placement_playable() -> None:
    # Seed-97 sweep shape: the owner's only City Spy shares its post with
    # another player's Spy and the other City posts are full, so recalling
    # it cannot free a post [Main pp. 11, 20] and option 0 must not be
    # offered at all.
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
            "landsraad-assembly-hall-gather-support",
        ),
    )
    state = _city_posts_held_by_rivals(_turn_state(owner))
    watcher = replace(
        state.players[3],
        spies_supply=2,
        spy_post_ids=("arrakis-research-station-spice-refinery",),
    )
    state = replace(state, players=(*state.players[:3], watcher))
    engine = UprisingRulesEngine()

    actions = engine.legal_actions(state, 0)
    assert _play(state, card, 0) not in actions
    # The recall option of the same card stays playable.
    assert _play(state, card, 1) in actions


def test_special_mission_slot_declines_after_a_drift_strands_the_placement() -> None:
    # A trigger placement can occupy the freed post between the play-time
    # check and the slot resolution; the stranded slot must resolve through
    # the optional decline instead of deadlocking [Main pp. 11, 20].
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
            "landsraad-assembly-hall-gather-support",
        ),
    )
    state = _city_posts_held_by_rivals(_turn_state(owner))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 0)).state
    watcher = replace(
        opened.players[3],
        spies_supply=2,
        spy_post_ids=("arrakis-research-station-spice-refinery",),
    )
    drifted = replace(opened, players=(*opened.players[:3], watcher))

    assert {a.action_id for a in engine.legal_actions(drifted, 0)} == {
        "decline_intrigue_spy"
    }
    declined = engine.apply(
        drifted, DomainAction(action_id="decline_intrigue_spy", actor=0)
    ).state
    assert declined.intrigue_discard == (card,)
    assert declined.decision_stack[-1].kind == "turn"



def test_special_mission_city_spy_is_not_offered_after_a_recall_this_turn() -> None:
    # Supply empty and every City post full, one held by the owner's Spy
    # alone: recalling that Spy and placing it back changes nothing once a
    # Spy was already recalled this turn (state A). Before any recall this
    # turn the counter's 0 -> 1 is the change and the play stays (OQ-101 (b)).
    card = _intrigue("special_mission")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=(
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
            "landsraad-assembly-hall-gather-support",
        ),
    )
    fresh = _city_posts_held_by_rivals(_turn_state(owner))
    assert _play(fresh, card, 0) in legal_intrigue_play_actions(fresh, 0)
    recalled = _city_posts_held_by_rivals(
        _turn_state(replace(owner, spies_recalled_turn=1))
    )
    assert _play(recalled, card, 0) not in legal_intrigue_play_actions(recalled, 0)
    assert option_unplayable_reason(recalled, 0, option) == PlaceSpy(
        agent_icons=option.sections[0].rewards[0].agent_icons  # type: ignore[union-attr]
    )


def test_special_mission_recall_option_pays_out_after_the_detonation_choice() -> None:
    card = _intrigue("special_mission")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    assert _play(state, card, 1) in legal_intrigue_play_actions(state, 0)
    opened = engine.apply(state, _play(state, card, 1)).state
    assert engine.legal_actions(opened, 0) == (
        _recall_spy("landsraad-assembly-hall-gather-support"),
    )
    recalled = engine.apply(
        opened, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert recalled.players[0].spies_supply == 3
    assert engine.legal_actions(recalled, 0) == (
        _detonate(),
        _keep_wall(),
        DomainAction(action_id="resolve_intrigue_rewards", actor=0),
    )
    done = engine.apply(recalled, _keep_wall()).state
    assert done.players[0].resources.spice == 2
    assert done.shield_wall_present is True

    # Without a placed Spy the recall option cannot be played at all.
    grounded = _turn_state(PlayerState(player_id=0, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(grounded, 0) == (_play(grounded, card, 0),)


def _combat_state(*players: PlayerState) -> GameState:
    from dune_imperium.rules.combat import begin_combat_intrigue

    seats = list(players)
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(_conflict(False),),
        players=tuple(seats),
    )
    return begin_combat_intrigue(state).state


def _pass(actor: int) -> DomainAction:
    return DomainAction(action_id="pass_combat_intrigue", actor=actor)


def test_combat_intrigue_is_offered_only_to_the_participant_with_priority() -> None:
    card = _intrigue("weirding_combat")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        troops_supply=10,
        troops_garrison=1,
        troops_conflict=1,
        combat_strength=2,
    )
    rival = PlayerState(
        player_id=1,
        intrigue_cards=(_intrigue("weirding_combat", 0),),
        troops_supply=10,
        troops_garrison=1,
        troops_conflict=1,
        combat_strength=2,
    )
    bystander = PlayerState(player_id=2, intrigue_cards=())
    state = _combat_state(fighter, replace(rival, intrigue_cards=()), bystander)
    engine = UprisingRulesEngine()

    assert state.decision_stack[-1].kind == "combat_intrigue"
    assert engine.legal_actions(state, 0) == (_pass(0), _play(state, card))
    assert engine.legal_actions(state, 1) == ()

    played = engine.apply(state, _play(state, card))
    assert played.state.players[0].combat_strength == 5
    assert "combat_strength_gained" in [e.kind for e in played.events]
    # After playing, priority stays with the same player [Main p. 14].
    assert engine.legal_actions(played.state, 0) == (_pass(0),)


def test_weirding_combat_adds_two_more_with_three_bene_gesserit() -> None:
    card = _intrigue("weirding_combat")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(bene_gesserit=3),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    played = engine.apply(state, _play(state, card)).state
    assert played.players[0].combat_strength == 7


def test_playing_combat_intrigue_restarts_the_consecutive_pass_count() -> None:
    card = _intrigue("weirding_combat")
    first = PlayerState(
        player_id=0, troops_supply=11, troops_garrison=0, troops_conflict=1,
        combat_strength=2,
    )
    second = PlayerState(
        player_id=1,
        intrigue_cards=(card,),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(first, second)
    engine = UprisingRulesEngine()

    passed = engine.apply(state, _pass(0)).state
    assert dict(passed.decision_stack[-1].context)["consecutive_passes"] == 1
    play_as_second = DomainAction(
        action_id="play_intrigue", actor=1, arguments=(("card_id", card), ("option", 0))
    )
    played = engine.apply(passed, play_as_second).state
    assert dict(played.decision_stack[-1].context)["consecutive_passes"] == 0
    # Both players must pass again in a row before Combat resolves.
    once = engine.apply(played, _pass(1)).state
    assert once.decision_stack[-1].kind == "combat_intrigue"
    twice = engine.apply(once, _pass(0)).state
    assert twice.combat_intrigue_complete is True


def test_questionable_methods_sword_is_automatic_and_the_influence_line_optional() -> (
    None
):
    card = _intrigue("questionable_methods")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(fremen=1),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    # The sword line has no cost and lands as the card is played (OQ-058).
    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].combat_strength == 3
    assert opened.decision_stack[-1].kind == "intrigue_effects"
    assert engine.legal_actions(opened, 0) == (_finish_lines(), _use_line(1))
    choosing = engine.apply(opened, _use_line(1)).state
    assert engine.legal_actions(choosing, 0) == (_choose_faction("fremen"),)
    done = engine.apply(choosing, _choose_faction("fremen")).state
    assert done.players[0].influence.fremen == 0
    assert done.players[0].combat_strength == 7
    assert done.decision_stack[-1].kind == "combat_intrigue"

    # Without any Influence the card is still playable for its sword; the
    # arrow line cannot be used and the owner finishes.
    broke = _combat_state(replace(fighter, influence=Influence()))
    assert legal_intrigue_play_actions(broke, 0) == (_play(broke, card),)
    sword = engine.apply(broke, _play(broke, card)).state
    assert sword.players[0].combat_strength == 3
    assert engine.legal_actions(sword, 0) == (_finish_lines(),)
    finished = engine.apply(sword, _finish_lines()).state
    assert card in finished.intrigue_discard
    assert finished.decision_stack[-1].kind == "combat_intrigue"


def test_find_weakness_recalls_a_spy_for_the_bonus() -> None:
    card = _intrigue("find_weakness")
    fighter = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=2,
        spy_post_ids=("landsraad-assembly-hall-gather-support",),
        troops_supply=11,
        troops_garrison=0,
        troops_conflict=1,
        combat_strength=2,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.players[0].combat_strength == 4
    assert engine.legal_actions(opened, 0) == (_finish_lines(), _use_line(1))
    recalling = engine.apply(opened, _use_line(1)).state
    assert engine.legal_actions(recalling, 0) == (
        _recall_spy("landsraad-assembly-hall-gather-support"),
    )
    done = engine.apply(
        recalling, _recall_spy("landsraad-assembly-hall-gather-support")
    ).state
    assert done.players[0].spies_supply == 3
    assert done.players[0].combat_strength == 7
    assert card in done.intrigue_discard


def test_combat_intrigue_is_not_offered_during_player_turns() -> None:
    card = _intrigue("weirding_combat")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(_turn_state(owner), 0) == ()


def _retreat(count: int, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="retreat_intrigue_troops", actor=actor, arguments=(("count", count),)
    )


def _fighter(player_id: int, troops: int, **extra: object) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        troops_supply=12 - troops,
        troops_garrison=0,
        troops_conflict=troops,
        combat_strength=2 * troops,
        **extra,  # type: ignore[arg-type]
    )


def test_go_to_ground_retreats_then_places_a_spy_and_drops_an_empty_player() -> None:
    card = _intrigue("go_to_ground")
    state = _combat_state(_fighter(0, 1, intrigue_cards=(card,)), _fighter(1, 2))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    # Only one troop is in the Conflict, so only a one-troop retreat is offered.
    assert engine.legal_actions(opened, 0) == (_retreat(1),)
    retreated = engine.apply(opened, _retreat(1)).state
    assert retreated.players[0].troops_conflict == 0
    assert retreated.players[0].combat_strength == 0
    # The Spy placement still resolves before the card finishes, and with a
    # Spy in the supply it is mandatory (the erratum to [Main p. 11], OQ-057).
    assert {a.action_id for a in engine.legal_actions(retreated, 0)} == {
        "place_intrigue_spy",
    }
    post = str(dict(engine.legal_actions(retreated, 0)[0].arguments)["post_id"])
    done = engine.apply(retreated, _place_spy(post)).state

    assert done.players[0].spy_post_ids == (post,)
    # OQ-003 convention: with no units left, player 0 leaves the loop at once
    # and priority moves to the next remaining participant.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 1
    assert dict(frame.context)["participants_mask"] == 0b10
    assert engine.legal_actions(done, 0) == ()


def test_tactical_option_retreating_the_last_units_ends_combat_intrigue() -> None:
    card = _intrigue("tactical_option")
    state = _combat_state(_fighter(0, 2, intrigue_cards=(card,)))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    # "Retreat any number of your troops." [card face]: zero included
    # [Main p. 20] [FAQ p. 3].
    assert engine.legal_actions(opened, 0) == (_retreat(0), _retreat(1), _retreat(2))
    # Resolve the slot without the dispatcher so the round does not run on.
    done = apply_intrigue_choice(opened, _retreat(2))

    assert done.state.players[0].troops_garrison == 2
    assert done.state.players[0].combat_strength == 0
    assert done.state.combat_intrigue_complete is True
    assert done.state.decision_stack == ()
    # The emptied loop announces the stage end like its other endings.
    finished = [e for e in done.events if e.kind == "combat_intrigue_finished"]
    assert [e.event_id for e in finished] == ["round:1:combat_intrigue:emptied"]


def test_tactical_option_partial_retreat_keeps_the_player_in_the_loop() -> None:
    card = _intrigue("tactical_option")
    state = _combat_state(_fighter(0, 3, intrigue_cards=(card,)), _fighter(1, 1))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    done = engine.apply(opened, _retreat(1)).state

    assert done.players[0].troops_conflict == 2
    assert done.players[0].combat_strength == 4
    frame = done.decision_stack[-1]
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 0
    assert dict(frame.context)["consecutive_passes"] == 0


def test_tactical_option_may_retreat_no_troops() -> None:
    # "효과가 `any number`의 troop을 retreat하게 하면 0개도 선택할 수 있다.
    # `[Main p. 20]` `[FAQ p. 3]`" (docs/rules/uprising-systems.md).
    card = _intrigue("tactical_option")
    state = _combat_state(_fighter(0, 2, intrigue_cards=(card,)), _fighter(1, 1))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card, 1)).state
    result = engine.apply(opened, _retreat(0))
    done = result.state

    assert "troops_retreated" not in [event.kind for event in result.events]
    assert done.players[0].troops_conflict == 2
    assert done.players[0].troops_garrison == 0
    assert done.players[0].combat_strength == 4
    assert card in done.intrigue_discard
    # The card was still played: the pass count restarts and the seat stays.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0
    assert dict(frame.context)["participants_mask"] == 0b11


def test_tactical_option_retreat_still_needs_a_unit_in_the_conflict() -> None:
    # The Retreat half stays unplayable without a unit in the Conflict (the
    # Steam app offers it the same way); only the swords half is offered.
    card = _intrigue("tactical_option")
    fighter = replace(
        _fighter(0, 0, intrigue_cards=(card,)), sandworms_conflict=1
    )
    state = _combat_state(fighter, _fighter(1, 1))
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)


def test_spice_is_power_offers_both_halves_when_affordable() -> None:
    card = _intrigue("spice_is_power")
    rich = _fighter(0, 3, intrigue_cards=(card,), resources=Resources(spice=3))
    state = _combat_state(rich, _fighter(1, 1))
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (
        _play(state, card, 0),
        _play(state, card, 1),
    )

    swords = engine.apply(state, _play(state, card, 1)).state
    assert swords.players[0].resources.spice == 0
    assert swords.players[0].combat_strength == 12

    opened = engine.apply(state, _play(state, card, 0)).state
    assert engine.legal_actions(opened, 0) == (_retreat(3),)
    paid = engine.apply(opened, _retreat(3)).state
    assert paid.players[0].resources.spice == 6
    assert paid.players[0].troops_conflict == 0
    assert dict(paid.decision_stack[-1].context)["participants_mask"] == 0b10

    poor = _combat_state(_fighter(0, 2, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(poor, 0) == ()


def test_devour_adds_more_and_offers_a_trash_with_a_sandworm() -> None:
    card = _intrigue("devour")
    plain = _combat_state(_fighter(0, 1, intrigue_cards=(card,)))
    engine = UprisingRulesEngine()
    done = engine.apply(plain, _play(plain, card)).state
    assert done.players[0].combat_strength == 4
    assert done.decision_stack[-1].kind == "combat_intrigue"

    worm = _fighter(0, 1, intrigue_cards=(card,), hand=(_starter("dagger"),))
    worm = replace(worm, sandworms_conflict=1, combat_strength=5)
    state = _combat_state(worm)
    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert engine.legal_actions(opened, 0)[0].action_id == "decline_intrigue_trash"
    trashed = engine.apply(opened, _trash(_starter("dagger"))).state
    assert trashed.players[0].trashed == (_starter("dagger"),)
    assert trashed.players[0].combat_strength == 9


def _imperium_instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in imperium_deck_instance_ids(False)
        if f":{card_id}:" in instance_id
    )


def _acquire_imperium(instance_id: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="acquire_intrigue_imperium",
        actor=actor,
        arguments=(("instance_id", instance_id),),
    )


def _acquire_reserve(card_id: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="acquire_intrigue_reserve",
        actor=actor,
        arguments=(("card_id", card_id),),
    )


def _with_market(state: GameState) -> GameState:
    return replace(
        state,
        imperium_row=(
            _imperium_instance("sardaukar_soldier"),
            _imperium_instance("steersman"),
        ),
        imperium_deck=(_imperium_instance("maula_pistol"),),
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 10)),
    )


def test_inspire_awe_acquires_a_cheap_card_to_the_discard_pile() -> None:
    card = _intrigue("inspire_awe")
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    # Only targets within the printed cap are offered: Prepare the Way costs
    # 2 and Sardaukar Soldier 1, while The Spice Must Flow (9) and
    # Steersman (8) are out of reach.
    assert engine.legal_actions(opened, 0) == (
        _acquire_reserve("prepare_the_way"),
        _acquire_imperium(cheap),
    )

    result = engine.apply(opened, _acquire_imperium(cheap))
    done = result.state
    assert "card_acquired" in [event.kind for event in result.events]
    # Without a sandworm the card lands in the discard pile [Main p. 13] and
    # the Row refills from the Imperium Deck at once.
    assert done.players[0].discard_pile == (cheap,)
    assert done.players[0].hand == ()
    assert done.imperium_row == (
        _imperium_instance("maula_pistol"),
        _imperium_instance("steersman"),
    )
    assert done.imperium_deck == ()
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (card,)
    assert done.decision_stack == _after_plot(state)


def test_inspire_awe_puts_the_card_in_hand_with_a_sandworm_in_the_conflict() -> None:
    card = _intrigue("inspire_awe")
    owner = PlayerState(player_id=0, intrigue_cards=(card,), sandworms_conflict=1)
    state = replace(
        _with_market(_turn_state(owner)),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    done = engine.apply(opened, _acquire_reserve("prepare_the_way")).state

    assert done.players[0].hand == ("reserve:prepare_the_way:7",)
    assert done.players[0].discard_pile == ()
    assert dict(done.reserve_stacks)["prepare_the_way"] == 7
    assert done.intrigue_discard == (card,)


def test_inspire_awe_without_a_target_is_not_offered() -> None:
    # With nothing within its cap to acquire, its only effect changes nothing
    # (user ruling 2026-10-06); Impress keeps the designer's exception
    # through its swords (OQ-057 (6)).
    card = _intrigue("inspire_awe")
    option = intrigue_card_for_instance(card).options[0]
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = replace(
        _turn_state(owner),
        imperium_row=(_imperium_instance("steersman"),),
        imperium_deck=(_imperium_instance("maula_pistol"),),
        reserve_stacks=(("prepare_the_way", 0), ("the_spice_must_flow", 10)),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    assert option_unplayable_reason(state, 0, option) == AcquireCardUpTo(
        max_cost=3, to_hand_if=option.sections[0].rewards[0].to_hand_if  # type: ignore[union-attr]
    )
    # An opponent's set-aside card is never within reach [FAQ p. 3] ...
    survival = _imperium_instance("desert_survival")  # costs 2
    rival = replace(state.players[1], imperium_set_aside=(survival,))
    rivalled = replace(state, players=(state.players[0], rival, *state.players[2:]))
    assert legal_intrigue_play_actions(rivalled, 0) == ()
    # ... but the owner's own is, at its printed cost.
    own = replace(
        state,
        players=(replace(owner, imperium_set_aside=(survival,)), *state.players[1:]),
    )
    assert legal_intrigue_play_actions(own, 0) == (_play(own, card),)


def test_inspire_awe_to_hand_immediately_reveals_during_the_owners_reveal_turn() -> (
    None
):
    card = _intrigue("inspire_awe")
    owner = PlayerState(player_id=0, intrigue_cards=(card,), sandworms_conflict=1)
    state = replace(
        _with_market(_turn_state(owner)),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    # With a sandworm the acquired card enters the hand mid-Reveal, so it is
    # revealed and used at once [FAQ p. 3] instead of being withheld.
    revealed = engine.apply(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert legal_intrigue_play_actions(revealed, 0) == (_play(revealed, card),)

    opened = engine.apply(revealed, _play(revealed, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"

    result = engine.apply(opened, _acquire_reserve("prepare_the_way"))
    done = result.state
    owner_after = done.players[0]

    # The acquired card is immediately revealed into play rather than
    # sitting in hand.
    assert owner_after.hand == ()
    assert "reserve:prepare_the_way:7" in owner_after.in_play
    assert owner_after.discard_pile == ()
    assert dict(done.reserve_stacks)["prepare_the_way"] == 7
    assert done.intrigue_discard == (card,)
    assert done.decision_stack[-1].kind == "reveal"
    context = dict(done.decision_stack[-1].context)
    assert context["persuasion"] == 2
    assert context["revealed_card_count"] == 1
    assert context["revealed_card_000"] == "reserve:prepare_the_way:7"
    assert "personal_card_late_revealed" in {event.kind for event in result.events}

    # Without a sandworm the card still goes to the discard pile untouched.
    calm = _with_market(_turn_state(replace(owner, sandworms_conflict=0)))
    shown = engine.apply(calm, DomainAction(action_id="reveal_turn", actor=0)).state
    assert legal_intrigue_play_actions(shown, 0) == (_play(shown, card),)


def test_inspire_awe_late_reveal_choice_does_not_bury_the_intrigue_choice() -> None:
    # The acquired card's own REVEAL_CHOICE frame [FAQ p. 3] must slot in
    # above the Reveal frame without burying Inspire Awe's still-resolving
    # Intrigue choice frame, which sits above the Reveal frame too.
    card = _intrigue("inspire_awe")
    wheels = _imperium_instance("wheels_within_wheels")
    owner = PlayerState(player_id=0, intrigue_cards=(card,), sandworms_conflict=1)
    state = replace(
        _turn_state(owner),
        imperium_row=(wheels,),
        imperium_deck=(_imperium_instance("maula_pistol"),),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    revealed = engine.apply(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    opened = engine.apply(revealed, _play(revealed, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"

    done = engine.apply(opened, _acquire_imperium(wheels)).state

    # Inspire Awe fully resolved (discarded) in the same step, and the
    # acquired card's PLACE_SPY choice is now the only frame above Reveal.
    assert done.intrigue_discard == (card,)
    assert done.players[0].in_play == (wheels,)
    assert done.decision_stack[-1].kind == "reveal_choice"
    assert done.decision_stack[-2].kind == "reveal"

    spy_actions = legal_reveal_spy_actions(done, 0)
    assert spy_actions
    resolved = apply_reveal_spy_action(done, spy_actions[0]).state
    assert resolved.decision_stack[-1].kind == "reveal"
    assert resolved.players[0].spy_post_ids == (
        dict(spy_actions[0].arguments)["post_id"],
    )


def test_impress_adds_strength_and_acquires_during_combat() -> None:
    card = _intrigue("impress")
    state = _with_market(
        _combat_state(_fighter(0, 1), _fighter(1, 1, intrigue_cards=(card,)))
    )
    engine = UprisingRulesEngine()

    passed = engine.apply(state, _pass(0)).state
    assert dict(passed.decision_stack[-1].context)["consecutive_passes"] == 1
    play = DomainAction(
        action_id="play_intrigue",
        actor=1,
        arguments=(("card_id", card), ("option", 0)),
    )
    opened = engine.apply(passed, play).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    # The swords are an automatic reward: they land when the card finishes.
    assert opened.players[1].combat_strength == 2

    cheap = _imperium_instance("sardaukar_soldier")
    done = engine.apply(opened, _acquire_imperium(cheap, actor=1)).state
    assert done.players[1].combat_strength == 4
    assert done.players[1].discard_pile == (cheap,)
    assert done.intrigue_discard == (card,)
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    # Playing the card restarts the consecutive-pass count [Main p. 14].
    assert dict(frame.context)["consecutive_passes"] == 0
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == 1


def test_impress_without_an_affordable_target_still_adds_its_strength() -> None:
    # Designer ruling (Message from designer, OQ-057): Impress may be played
    # with no card of cost 3 or less available; the two swords land and the
    # acquisition alone fizzles.
    card = _intrigue("impress")
    state = _combat_state(_fighter(0, 1, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    engine = UprisingRulesEngine()
    opened = engine.apply(state, _play(state, card)).state
    # The swords may be taken first (OQ-015); the acquisition can only be skipped.
    assert {action.action_id for action in engine.legal_actions(opened, 0)} == {
        "resolve_intrigue_rewards",
        "skip_intrigue_acquisition",
    }
    done = engine.apply(
        opened, DomainAction(action_id="skip_intrigue_acquisition", actor=0)
    ).state
    assert done.players[0].combat_strength == 2 + 2
    assert card in done.intrigue_discard
    assert done.decision_stack[-1].kind == "combat_intrigue"


def test_impress_acquiring_spy_network_opens_the_spy_frame_after_the_card() -> None:
    card = _intrigue("impress")
    spy_network = _imperium_instance("spy_network")
    state = replace(
        _combat_state(_fighter(0, 1, intrigue_cards=(card,))),
        imperium_row=(spy_network,),
        imperium_deck=(_imperium_instance("maula_pistol"),),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    acquired = engine.apply(opened, _acquire_imperium(spy_network)).state

    # The acquire box opens its Spy placement only after the Intrigue card
    # has fully resolved [Main p. 20].
    assert acquired.decision_stack[-1].kind == "acquisition_spy"
    assert acquired.intrigue_discard == (card,)
    assert acquired.players[0].combat_strength == 4
    below = acquired.decision_stack[-2]
    assert below.kind == "combat_intrigue"
    assert dict(below.context)["consecutive_passes"] == 0

    spy_actions = engine.legal_actions(acquired, 0)
    assert {action.action_id for action in spy_actions} == {"place_acquisition_spy"}
    done = engine.apply(acquired, spy_actions[0]).state
    assert len(done.players[0].spy_post_ids) == 1
    assert done.decision_stack[-1].kind == "combat_intrigue"


def _persuasion_hand(copies: int = 2) -> tuple[str, ...]:
    return tuple(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if ":convincing_argument:" in instance_id
    )[:copies]


def _reveal(state: GameState) -> DomainAction:
    return DomainAction(action_id="reveal_turn", actor=0)


def test_call_to_arms_waits_face_up_when_played() -> None:
    card = _intrigue("call_to_arms")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    result = engine.apply(state, _play(state, card))
    done = result.state
    assert done.players[0].intrigue_cards == ()
    assert done.players[0].intrigue_faceup == (card,)
    assert done.intrigue_discard == ()
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "intrigue_kept_faceup",
    ]
    # The turn frame is untouched: no choice frame opens for a waiting card.
    assert done.decision_stack == _after_plot(state)


def test_call_to_arms_recruits_per_reveal_acquisition_then_expires() -> None:
    card = _intrigue("call_to_arms")
    owner = PlayerState(
        player_id=0, intrigue_faceup=(card,), hand=_persuasion_hand()
    )
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    cheap = _imperium_instance("sardaukar_soldier")
    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", cheap),),
        ),
    )
    assert bought.state.players[0].troops_garrison == 4
    assert "intrigue_triggered" in [event.kind for event in bought.events]

    again = engine.apply(
        bought.state,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state
    assert again.players[0].troops_garrison == 5
    # The card stays face up between firings [FAQ p. 2].
    assert again.players[0].intrigue_faceup == (card,)

    finished = engine.apply(
        again, DomainAction(action_id="finish_reveal", actor=0)
    )
    assert finished.state.players[0].intrigue_faceup == ()
    assert finished.state.intrigue_discard == (card,)
    assert "intrigue_expired" in [event.kind for event in finished.events]


def test_arrakis_revolt_and_call_to_arms_credit_the_same_acquisition_additively() -> (
    None
):
    # Two independent recruit mechanisms firing on the same acquisition must
    # add, not double count or clobber each other: Arrakis Revolt's own
    # acquire box [Main p. 20] and Call to Arms' per-Reveal-acquisition
    # trigger [Bloodlines pp. 5, 12] (docs/rules/bloodlines.md) both feed
    # ``reveal_troops_recruited``, since "그 turn에 어떤 출처에서 recruit
    # 했든 새 troop은 Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4]
    # (docs/rules/player-turns.md).
    call = _intrigue("call_to_arms")
    arrakis_revolt = "imperium:arrakis_revolt:0"
    owner = PlayerState(
        player_id=0, intrigue_faceup=(call,), hand=_persuasion_hand()
    )
    state = _with_market(_turn_state(owner))
    state = replace(state, imperium_row=(arrakis_revolt, *state.imperium_row))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state
    frame = revealed.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = 10
    revealed = replace(
        revealed,
        decision_stack=(
            *revealed.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", arrakis_revolt),),
        ),
    )

    # 1 from Arrakis Revolt's own acquire box, 1 from Call to Arms: neither
    # mechanism overwrites the other's credit.
    assert bought.state.players[0].troops_garrison == owner.troops_garrison + 2
    context_after = dict(bought.state.decision_stack[-1].context)
    assert context_after["reveal_troops_recruited"] == 2


def test_call_to_arms_troop_counts_toward_reveal_deployment_allowance() -> None:
    # "You may deploy any units you recruit this turn and up to two more
    # from your garrison" [Bloodlines p. 5] does not carve out an exception
    # for a troop a face-up Call to Arms recruits: it is still recruited
    # during this Reveal turn. The trigger used to leave
    # ``reveal_troops_recruited`` unchanged, so a Combat icon's deployment
    # allowance never grew past the flat 2 from the garrison no matter how
    # many acquisitions fired the card.
    from dune_imperium.rules.reveal_turn import legal_reveal_deployments

    card = _intrigue("call_to_arms")
    owner = PlayerState(
        player_id=0,
        intrigue_faceup=(card,),
        hand=_persuasion_hand(1),
        combat_icon_turn=True,
    )
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state

    context = dict(bought.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1
    assert {
        dict(action.arguments)["count"]
        for action in legal_reveal_deployments(bought, 0)
        if action.action_id == "deploy_troops"
    } == {1, 2, 3}


def test_call_to_arms_played_during_the_reveal_applies_at_once() -> None:
    card = _intrigue("call_to_arms")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), hand=_persuasion_hand(1)
    )
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    played = engine.apply(revealed, _play(revealed, card)).state
    assert played.players[0].intrigue_faceup == (card,)
    bought = engine.apply(
        played,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    ).state
    assert bought.players[0].troops_garrison == 4


def test_call_to_arms_ignores_acquisitions_outside_the_reveal_turn() -> None:
    call = _intrigue("call_to_arms")
    awe = _intrigue("inspire_awe")
    owner = PlayerState(player_id=0, intrigue_cards=(awe,), intrigue_faceup=(call,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, awe)).state
    done = engine.apply(opened, _acquire_reserve("prepare_the_way")).state
    # An Agent-turn acquisition is outside the Reveal-turn window.
    assert done.players[0].troops_garrison == 3
    assert done.players[0].intrigue_faceup == (call,)


def test_call_to_arms_counts_intrigue_acquisitions_during_the_reveal() -> None:
    call = _intrigue("call_to_arms")
    awe = _intrigue("inspire_awe")
    owner = PlayerState(player_id=0, intrigue_cards=(awe,), intrigue_faceup=(call,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    opened = engine.apply(revealed, _play(revealed, awe)).state
    done = engine.apply(opened, _acquire_reserve("prepare_the_way")).state
    assert done.players[0].troops_garrison == 4


def test_call_to_arms_trigger_is_supply_limited() -> None:
    card = _intrigue("call_to_arms")
    owner = PlayerState(
        player_id=0,
        intrigue_faceup=(card,),
        troops_supply=0,
        troops_garrison=12,
        hand=_persuasion_hand(1),
    )
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_reserve",
            actor=0,
            arguments=(("card_id", "prepare_the_way"),),
        ),
    )
    assert bought.state.players[0].troops_garrison == 12
    triggered = next(
        event for event in bought.events if event.kind == "intrigue_triggered"
    )
    assert dict(triggered.payload)["troops"] == 0


def test_call_to_arms_is_not_offered_in_a_reveal_with_nothing_left_to_acquire() -> (
    None
):
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." [FAQ p. 2] (docs/rules/player-turns.md), with the user's
    # ruling of 2026-10-06 that an Intrigue option needs an effect that can
    # change something: Call to Arms recruits only "whenever you acquire a
    # card" in its owner's Reveal turn, so once that Reveal is open with no
    # Persuasion to spend and nothing else on offer, it would change nothing.
    card = _intrigue("call_to_arms")
    option = intrigue_card_for_instance(card).options[0]
    engine = UprisingRulesEngine()
    state = _with_market(
        _turn_state(PlayerState(player_id=0, intrigue_cards=(card,)))
    )
    # Before the Reveal the whole Reveal turn is still ahead.
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)

    broke = _revealed_with_persuasion(state, 0)
    assert broke.decision_stack[-1].kind == FrameKind.REVEAL
    assert _play(broke, card) not in engine.legal_actions(broke, 0)
    assert (
        option_unplayable_reason(broke, 0, option) is OptionBlock.NO_ACQUISITION_AHEAD
    )
    # Two Persuasion buy Prepare the Way (or Sardaukar Soldier).
    rich = _revealed_with_persuasion(state, 2)
    assert _play(rich, card) in engine.legal_actions(rich, 0)
    # Inspire Awe, playable in the same Reveal, still acquires a card
    # costing 3 or less, and Call to Arms counts it.
    awe = _intrigue("inspire_awe")
    holding = _revealed_with_persuasion(
        _with_market(
            _turn_state(PlayerState(player_id=0, intrigue_cards=(card, awe)))
        ),
        0,
    )
    assert _play(holding, card) in engine.legal_actions(holding, 0)

    # Under Immortality a Tleilaxu Row card costs specimens instead of
    # Persuasion ("Persuasion 대신 specimen을 비용으로 낸다." [Immortality
    # p. 8]): Shadowy Bargain, playable in the same Reveal, makes the
    # specimen that buys Contaminator, and Call to Arms counts that
    # acquisition.
    def tanks(*held: str) -> GameState:
        state = _with_market(
            _turn_state(PlayerState(player_id=0, intrigue_cards=(card, *held)))
        )
        return replace(
            state,
            config=RulesetConfig(immortality=True),
            tleilaxu_row=("tleilaxu:contaminator:0", "tleilaxu:corrino_genes:0"),
            players=tuple(
                replace(seat, research_space="c0r3") for seat in state.players
            ),
        )

    alone = _revealed_with_persuasion(tanks(), 0)
    assert _play(alone, card) not in engine.legal_actions(alone, 0)
    bargain = _revealed_with_persuasion(tanks(_intrigue("shadowy_bargain")), 0)
    assert bargain.players[0].specimens == 0
    assert _play(bargain, card) in engine.legal_actions(bargain, 0)


def test_call_to_arms_needs_a_troop_it_could_recruit() -> None:
    # The user's ruling of 2026-10-06 reads a recruit as the Arrakeen Scouts
    # one is (OQ-071): with no troop in the supply and no specimen to return,
    # the troop it would recruit cannot come, so the card is not offered
    # even before the Reveal.
    card = _intrigue("call_to_arms")
    option = intrigue_card_for_instance(card).options[0]
    empty = _turn_state(
        PlayerState(
            player_id=0, intrigue_cards=(card,), troops_supply=0, troops_garrison=12
        )
    )
    assert legal_intrigue_play_actions(empty, 0) == ()
    assert option_unplayable_reason(empty, 0, option) == RecruitTroops(1)
    one = _turn_state(
        PlayerState(
            player_id=0, intrigue_cards=(card,), troops_supply=1, troops_garrison=11
        )
    )
    assert legal_intrigue_play_actions(one, 0) == (_play(one, card),)


def _revealed_with_persuasion(
    state: GameState, persuasion: int = 10
) -> GameState:
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state
    frame = revealed.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = persuasion
    return replace(
        revealed,
        decision_stack=(
            *revealed.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def _assert_call_to_arms_fired_last(
    result: Transition, call: str, source: str, garrison: int
) -> None:
    """The troop came after the frame's answer, with the usual event and credit."""

    assert [event.kind for event in result.events][-1] == "intrigue_triggered"
    triggered = result.events[-1]
    # The same event an acquisition without a frame emits.
    assert triggered.event_id == f"{source}:reveal_trigger:{call}"
    assert dict(triggered.payload) == {"card_id": call, "player": 0, "troops": 1}
    done = result.state
    assert done.players[0].troops_garrison == garrison + 1
    assert done.decision_stack[-1].kind == FrameKind.REVEAL
    context = dict(done.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1
    assert "deferred_acquisition_triggers" not in context


def test_call_to_arms_waits_for_the_acquired_card_s_spy_post() -> None:
    # OQ-012 fixes "획득한 카드 자신의 acquire 보상 → … → face-up trigger
    # Intrigue(Call to Arms의 troop recruit)", and the user ruling 2026-10-04
    # ("선택 뒤로 맞춤") keeps that order when the card's own acquire box
    # opens a decision: Spy Network's Spy post is placed first, and Call to
    # Arms' troop follows only then.
    call = _intrigue("call_to_arms")
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(player_id=0, intrigue_faceup=(call,))
    state = _with_market(_turn_state(owner))
    state = replace(state, imperium_row=(spy_network, *state.imperium_row))
    revealed = _revealed_with_persuasion(state)
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", spy_network),),
        ),
    )
    assert [event.kind for event in bought.events] == ["card_acquired"]
    assert bought.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    assert bought.state.players[0].troops_garrison == garrison

    placed = engine.apply(bought.state, engine.legal_actions(bought.state, 0)[0])
    assert [event.kind for event in placed.events] == [
        "spy_placed",
        "intrigue_triggered",
    ]
    _assert_call_to_arms_fired_last(
        placed, call, f"round:1:player:0:acquire:{spy_network}", garrison
    )


def test_call_to_arms_waits_for_a_set_aside_card_s_spy_post() -> None:
    # Same ruling (OQ-012, user ruling 2026-10-04) on the Manipulate path.
    call = _intrigue("call_to_arms")
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(
        player_id=0, intrigue_faceup=(call,), imperium_set_aside=(spy_network,)
    )
    revealed = _revealed_with_persuasion(_with_market(_turn_state(owner)))
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_manipulated_imperium",
            actor=0,
            arguments=(("instance_id", spy_network),),
        ),
    )
    assert [event.kind for event in bought.events] == ["card_acquired"]
    assert bought.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY

    placed = engine.apply(bought.state, engine.legal_actions(bought.state, 0)[0])
    _assert_call_to_arms_fired_last(
        placed,
        call,
        f"round:1:player:0:acquire_manipulated:{spy_network}",
        garrison,
    )


def test_call_to_arms_waits_for_an_intrigue_acquired_card_s_spy_post() -> None:
    # Inspire Awe played in the Reveal: Spy Network's Spy post opens only
    # after the Intrigue card has resolved [Main p. 20], and Call to Arms
    # waits for that post too (OQ-012, user ruling 2026-10-04).
    call = _intrigue("call_to_arms")
    awe = _intrigue("inspire_awe")
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(player_id=0, intrigue_cards=(awe,), intrigue_faceup=(call,))
    state = _with_market(_turn_state(owner))
    state = replace(state, imperium_row=(spy_network, *state.imperium_row))
    revealed = _revealed_with_persuasion(state)
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()

    opened = engine.apply(revealed, _play(revealed, awe)).state
    acquired = engine.apply(opened, _acquire_imperium(spy_network))
    assert "intrigue_triggered" not in [event.kind for event in acquired.events]
    assert acquired.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    assert awe in acquired.state.intrigue_discard

    placed = engine.apply(
        acquired.state, engine.legal_actions(acquired.state, 0)[0]
    )
    assert [event.kind for event in placed.events] == [
        "spy_placed",
        "intrigue_triggered",
    ]
    _assert_call_to_arms_fired_last(
        placed, call, f"round:1:player:0:intrigue:{awe}:slot:0", garrison
    )


def test_inspire_awe_on_a_set_aside_card_is_a_full_acquisition() -> None:
    # Taking the owner's Manipulate card by "other means" [FAQ p. 3] is an
    # ordinary acquisition: Spy Network's acquire box opens its Spy post and
    # Call to Arms follows (OQ-012, user ruling 2026-10-04).
    call = _intrigue("call_to_arms")
    awe = _intrigue("inspire_awe")
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(awe,),
        intrigue_faceup=(call,),
        imperium_set_aside=(spy_network,),
    )
    state = _with_market(_turn_state(owner))
    revealed = _revealed_with_persuasion(state)
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()

    opened = engine.apply(revealed, _play(revealed, awe)).state
    assert _acquire_imperium(spy_network) in engine.legal_actions(opened, 0)
    acquired = engine.apply(opened, _acquire_imperium(spy_network))
    assert acquired.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    assert acquired.state.players[0].imperium_set_aside == ()
    assert acquired.state.players[0].discard_pile == (spy_network,)
    assert acquired.state.imperium_row == state.imperium_row
    # No discount: the Reveal's Persuasion is untouched by an Intrigue pick.
    assert dict(acquired.state.decision_stack[-2].context)["persuasion"] == 10

    placed = engine.apply(
        acquired.state, engine.legal_actions(acquired.state, 0)[0]
    )
    _assert_call_to_arms_fired_last(
        placed, call, f"round:1:player:0:intrigue:{awe}:slot:0", garrison
    )


def _choam_trade_state(
    call: str, market: tuple[str, ...]
) -> tuple[GameState, str]:
    trade = next(
        instance_id
        for instance_id in imperium_deck_instance_ids(True)
        if ":interstellar_trade:" in instance_id
    )
    state = replace(
        _with_market(
            _turn_state(PlayerState(player_id=0, intrigue_faceup=(call,)))
        ),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=market,
    )
    state = replace(state, imperium_row=(trade, *state.imperium_row))
    return _revealed_with_persuasion(state), trade


def test_call_to_arms_waits_for_the_acquired_card_s_contract_market() -> None:
    # Interstellar Trade's acquire box takes a Contract: the market choice
    # comes first, then Call to Arms (OQ-012, user ruling 2026-10-04).
    call = _intrigue("call_to_arms")
    revealed, trade = _choam_trade_state(
        call, ("contract:arrakeen_i", "contract:high_council_ii")
    )
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", trade),),
        ),
    )
    assert [event.kind for event in bought.events] == ["card_acquired"]
    assert bought.state.decision_stack[-1].kind == FrameKind.CONTRACT_MARKET

    taken = engine.apply(bought.state, engine.legal_actions(bought.state, 0)[0])
    assert [event.kind for event in taken.events] == [
        "contract_taken",
        "intrigue_triggered",
    ]
    _assert_call_to_arms_fired_last(
        taken, call, f"round:1:player:0:acquire:{trade}", garrison
    )


def test_call_to_arms_fires_in_the_acquisition_when_no_frame_opens() -> None:
    # An exhausted market opens no frame: the icon turns into Solari and
    # Call to Arms fires inside the acquisition, in the order it always did.
    call = _intrigue("call_to_arms")
    revealed, trade = _choam_trade_state(call, ())
    engine = UprisingRulesEngine()

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", trade),),
        ),
    )
    assert [event.kind for event in bought.events] == [
        "card_acquired",
        "contract_icons_converted_to_solari",
        "intrigue_triggered",
    ]
    assert bought.state.decision_stack[-1].kind == FrameKind.REVEAL
    context = dict(bought.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 1
    assert "deferred_acquisition_triggers" not in context


def test_a_later_call_to_arms_trigger_queues_behind_a_waiting_one() -> None:
    # Troops come in acquisition order (OQ-012, user ruling 2026-10-04): while
    # Spy Network's trigger waits for its Spy post, a later acquisition whose
    # card opened nothing does not fire first but joins the queue behind it.
    from dune_imperium.rules.intrigue_triggers import (
        fire_reveal_acquisition_intrigue,
    )

    call = _intrigue("call_to_arms")
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(player_id=0, intrigue_faceup=(call,))
    state = _with_market(_turn_state(owner))
    state = replace(state, imperium_row=(spy_network, *state.imperium_row))
    revealed = _revealed_with_persuasion(state)
    garrison = revealed.players[0].troops_garrison
    engine = UprisingRulesEngine()
    later = "round:1:player:0:later_acquisition"
    # With nothing waiting, the same acquisition fires at once.
    alone = fire_reveal_acquisition_intrigue(
        revealed, 0, source=later, started=revealed
    )
    assert [event.kind for event in alone.events] == ["intrigue_triggered"]

    bought = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_imperium",
            actor=0,
            arguments=(("instance_id", spy_network),),
        ),
    )
    assert bought.state.decision_stack[-1].kind == FrameKind.ACQUISITION_SPY
    queued = fire_reveal_acquisition_intrigue(
        bought.state, 0, source=later, started=bought.state
    )
    assert queued.events == ()
    assert queued.state.players[0].troops_garrison == garrison

    placed = engine.apply(queued.state, engine.legal_actions(queued.state, 0)[0])
    assert [event.kind for event in placed.events] == [
        "spy_placed",
        "intrigue_triggered",
        "intrigue_triggered",
    ]
    assert [event.event_id for event in placed.events[1:]] == [
        f"round:1:player:0:acquire:{spy_network}:reveal_trigger:{call}",
        f"{later}:reveal_trigger:{call}",
    ]
    assert placed.state.players[0].troops_garrison == garrison + 2
    context = dict(placed.state.decision_stack[-1].context)
    assert context["reveal_troops_recruited"] == 2
    assert "deferred_acquisition_triggers" not in context


def _post(index: int) -> str:
    from dune_imperium.content.uprising.board import OBSERVATION_POSTS

    return OBSERVATION_POSTS[index].post_id


def _place_intrigue_spy(post_id: str, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="place_intrigue_spy",
        actor=actor,
        arguments=(("post_id", post_id),),
    )


def _spy_rival(post_id: str) -> PlayerState:
    return PlayerState(player_id=1, spies_supply=2, spy_post_ids=(post_id,))


def _board_icon_action(effect: str) -> DomainAction:
    return DomainAction(
        action_id="resolve_board_effect",
        actor=0,
        arguments=(("effect", effect),),
    )


def _resolve_board_icons(
    engine: UprisingRulesEngine,
    state: GameState,
    *effects: str,
) -> GameState:
    """Resolve the named printed icons of the visited space in order."""

    for effect in effects:
        state = engine.apply(state, _board_icon_action(effect)).state
    return state


def _distraction_arrakeen_state(*, rival_post: str | None) -> GameState:
    owner = PlayerState(
        player_id=0,
        hand=(_starter("reconnaissance"),),
        intrigue_cards=(_intrigue("shaddam_s_favor"), _intrigue("distraction")),
        troops_supply=9,
        troops_garrison=3,
    )
    players: tuple[PlayerState, ...] = (
        owner,
        _spy_rival(rival_post) if rival_post else PlayerState(player_id=1),
        PlayerState(player_id=2),
        PlayerState(player_id=3),
    )
    state = _turn_state(owner)
    return replace(state, players=players)


def _deployed_three_at_arrakeen(
    engine: UprisingRulesEngine, state: GameState
) -> GameState:
    """Arrakeen, one Plot recruit, the board icons, then three troops in."""

    to_arrakeen = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = engine.apply(state, to_arrakeen).state
    # Recruit one troop by Plot so three troops may be deployed [Main p. 12].
    recruited = engine.apply(
        placed, _play(placed, _intrigue("shaddam_s_favor"))
    ).state
    board_done = _resolve_board_icons(engine, recruited, "troops", "cards")
    return engine.apply(
        board_done,
        DomainAction(action_id="deploy_troops", actor=0, arguments=(("count", 3),)),
    ).state


def test_distraction_needs_three_units_deployed_this_turn() -> None:
    # "When you deploy three or more units to the Conflict in a single
    # turn:" [Distraction card] is a condition for playing the card -- "To
    # play an Intrigue card, you must meet its conditions" [FAQ p. 2] -- met
    # once the units are deployed: "Muad'Dib may play Distraction because he
    # shared in the deployment of these units." [Board Guide p. 10]. It no
    # longer waits face up for the deployment (user ruling 2026-10-03,
    # OQ-016).
    card = _intrigue("distraction")
    engine = UprisingRulesEngine()
    for deployed, playable in ((0, False), (2, False), (3, True), (4, True)):
        owner = PlayerState(
            player_id=0, intrigue_cards=(card,), units_deployed_turn=deployed
        )
        state = _turn_state(owner)
        assert (_play(state, card) in engine.legal_actions(state, 0)) is playable


def test_distraction_is_played_after_an_agent_deployment() -> None:
    rival_post = _post(0)
    card = _intrigue("distraction")
    state = _distraction_arrakeen_state(rival_post=rival_post)
    engine = UprisingRulesEngine()
    assert _play(state, card) not in engine.legal_actions(state, 0)

    deployed = _deployed_three_at_arrakeen(engine, state)
    assert deployed.players[0].units_deployed_turn == 3
    assert deployed.players[0].units_deployed_peak == 3
    # Nothing opens by itself: the deployment keeps the Agent turn open
    # (OQ-029, OQ-095) and the card is now a legal Plot.
    assert deployed.decision_stack[-1].kind == "agent_effects"
    assert deployed.players[0].intrigue_faceup == ()
    assert _play(deployed, card) in engine.legal_actions(deployed, 0)

    played = engine.apply(deployed, _play(deployed, card)).state
    assert played.decision_stack[-1].kind == "intrigue_choice"
    actions = engine.legal_actions(played, 0)
    # Placing is mandatory while a Spy is in the supply (OQ-057 (14)).
    assert not any(action.action_id == "decline_intrigue_spy" for action in actions)
    assert _place_intrigue_spy(rival_post) in actions
    done = engine.apply(played, _place_intrigue_spy(rival_post)).state
    # Both players now share the post [Distraction card].
    assert rival_post in done.players[0].spy_post_ids
    assert rival_post in done.players[1].spy_post_ids
    assert done.intrigue_discard[-1] == card
    assert card not in done.players[0].intrigue_cards
    assert done.decision_stack[-1].kind == "agent_effects"
    # The played card used "three or more units deployed this turn": the
    # deployment may not be withdrawn below that minimum (OQ-029 exception),
    # so with exactly three deployed no withdrawal is offered at all.
    assert done.players[0].units_deployed_committed == 3
    assert not any(
        action.action_id == "withdraw_troops"
        for action in engine.legal_actions(done, 0)
    )
    finished = engine.apply(
        done, DomainAction(action_id="finish_agent_turn", actor=0)
    ).state
    assert finished.decision_stack[-1].kind == "turn"
    assert finished.players[0].troops_conflict == 3


def test_a_withdrawal_undoes_the_deployment_distraction_needs() -> None:
    # Before the card is played nothing is committed, so the deployment may
    # still be taken back (OQ-029); a withdrawal undoes the deployment, so
    # it lowers the turn's peak and the card is no longer playable until
    # three units are deployed again.
    card = _intrigue("distraction")
    state = _distraction_arrakeen_state(rival_post=_post(0))
    engine = UprisingRulesEngine()
    deployed = _deployed_three_at_arrakeen(engine, state)

    assert deployed.players[0].units_deployed_committed == 0
    withdrawals = {
        dict(action.arguments)["count"]
        for action in engine.legal_actions(deployed, 0)
        if action.action_id == "withdraw_troops"
    }
    assert withdrawals == {1, 2, 3}
    back = engine.apply(
        deployed,
        DomainAction(action_id="withdraw_troops", actor=0, arguments=(("count", 1),)),
    ).state
    assert back.players[0].units_deployed_turn == 2
    assert back.players[0].units_deployed_peak == 2
    assert _play(back, card) not in engine.legal_actions(back, 0)
    again = engine.apply(
        back,
        DomainAction(action_id="deploy_troops", actor=0, arguments=(("count", 1),)),
    ).state
    assert again.players[0].units_deployed_peak == 3
    assert _play(again, card) in engine.legal_actions(again, 0)


def test_a_retreat_after_the_deployment_keeps_distraction_playable() -> None:
    # "You need to have a moment in time when there are 3 units in the
    # conflict that were deployed to the conflict this turn, then that
    # requirement becomes true." (Message from designer, OQ-057's rule): a
    # later retreat leaves the turn's peak standing (OQ-016).
    from dune_imperium.core.engine import RuleResult
    from dune_imperium.rules.combat_deployment import (
        reconcile_deployment_after_retreat,
        record_deployment_peak,
    )

    card = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        troops_supply=6,
        troops_conflict=3,
        units_deployed_turn=3,
    )
    state = record_deployment_peak(RuleResult(state=_turn_state(owner))).state
    assert state.players[0].units_deployed_peak == 3
    retreated = reconcile_deployment_after_retreat(state, 0, troops=1)
    assert retreated.players[0].units_deployed_turn == 2
    assert retreated.players[0].units_deployed_peak == 3
    assert _play(retreated, card) in UprisingRulesEngine().legal_actions(
        retreated, 0
    )
    # Without that moment (two deployed and nothing higher) it is not met.
    two = _turn_state(replace(owner, units_deployed_turn=2))
    assert _play(two, card) not in UprisingRulesEngine().legal_actions(two, 0)


def test_a_card_played_off_the_peak_never_raises_the_deployed_count() -> None:
    # Played after a retreat left one unit of the turn's three in the
    # Conflict, the card commits its minimum of three (OQ-029) but a later
    # loss must not lift the count back up to that floor.
    from dune_imperium.rules.combat_deployment import (
        reconcile_deployment_after_retreat,
    )

    card = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        troops_supply=8,
        troops_conflict=1,
        units_deployed_turn=1,
        units_deployed_peak=3,
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()
    played = engine.apply(state, _play(state, card)).state
    played = engine.apply(played, _place_intrigue_spy(_post(0))).state
    assert played.players[0].units_deployed_committed == 3
    lost = reconcile_deployment_after_retreat(played, 0, troops=1)
    assert lost.players[0].units_deployed_turn <= 1
    assert lost.players[0].units_deployed_peak == 3


def test_both_distractions_can_use_the_same_deployment() -> None:
    # The condition describes the turn and is not used up by a play: each
    # copy may be played once three units were deployed (as two face-up
    # copies used to fire on the same deployment).
    first, second = _intrigue("distraction"), _intrigue("distraction", 1)
    owner = PlayerState(
        player_id=0, intrigue_cards=(first, second), units_deployed_turn=3
    )
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    once = engine.apply(state, _play(state, first)).state
    once = engine.apply(once, _place_intrigue_spy(_post(0))).state
    assert _play(once, second) in engine.legal_actions(once, 0)
    twice = engine.apply(once, _play(once, second)).state
    twice = engine.apply(twice, _place_intrigue_spy(_post(1))).state
    assert set(twice.players[0].spy_post_ids) == {_post(0), _post(1)}
    assert twice.intrigue_discard[-2:] == (first, second)


def test_distraction_played_after_detonation_deploys_three() -> None:
    rival_post = _post(2)
    detonation = _intrigue("detonation")
    distraction = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(detonation, distraction),
        troops_supply=9,
        troops_garrison=3,
    )
    state = replace(
        _turn_state(owner),
        players=(
            owner,
            _spy_rival(rival_post),
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
    )
    engine = UprisingRulesEngine()
    assert _play(state, distraction) not in engine.legal_actions(state, 0)

    opened = engine.apply(state, _play(state, detonation, 1)).state
    deployed = engine.apply(
        opened,
        DomainAction(
            action_id="deploy_intrigue_troops", actor=0, arguments=(("count", 3),)
        ),
    ).state
    assert deployed.players[0].units_deployed_turn == 3
    assert deployed.decision_stack[-1].kind == "turn"

    played = engine.apply(deployed, _play(deployed, distraction)).state
    assert played.decision_stack[-1].kind == "intrigue_choice"
    done = engine.apply(played, _place_intrigue_spy(rival_post)).state
    assert rival_post in done.players[0].spy_post_ids
    assert done.intrigue_discard[-1] == distraction


def test_distraction_places_without_any_opponent_spy_on_the_board() -> None:
    # The Spy icon places "on an unoccupied observation post" [Main p. 20];
    # "You may place this Spy on the same observation post as another
    # player's Spy" [Distraction card] only adds a permission, like Deep
    # Cover's "you also have the option to ignore any opponents' Spies"
    # [Bloodlines p. 5]. So the card works with no opponent Spy anywhere and
    # offers the empty posts.
    from dune_imperium.content.uprising.board import OBSERVATION_POSTS

    card = _intrigue("distraction")
    state = _distraction_arrakeen_state(rival_post=None)
    engine = UprisingRulesEngine()
    deployed = _deployed_three_at_arrakeen(engine, state)
    played = engine.apply(deployed, _play(deployed, card)).state

    offered = {
        dict(action.arguments)["post_id"]
        for action in engine.legal_actions(played, 0)
        if action.action_id == "place_intrigue_spy"
    }
    assert offered == {post.post_id for post in OBSERVATION_POSTS}
    done = engine.apply(played, _place_intrigue_spy(_post(0))).state
    assert done.players[0].spy_post_ids == (_post(0),)
    assert done.intrigue_discard[-1] == card


def test_distraction_offers_empty_and_rival_posts_but_never_its_own() -> None:
    from dune_imperium.content.uprising.board import OBSERVATION_POSTS

    rival_post = _post(1)
    own_post = _post(2)
    card = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=2,
        spy_post_ids=(own_post,),
        units_deployed_turn=3,
    )
    state = replace(
        _turn_state(owner),
        players=(
            owner,
            _spy_rival(rival_post),
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
    )
    engine = UprisingRulesEngine()
    played = engine.apply(state, _play(state, card)).state
    targets = {
        dict(action.arguments)["post_id"]
        for action in engine.legal_actions(played, 0)
        if action.action_id == "place_intrigue_spy"
    }
    # Empty posts and the rival's post [Distraction card; Bloodlines p. 5],
    # but not a post the owner already watches.
    assert rival_post in targets
    assert _post(0) in targets
    assert own_post not in targets
    assert targets == {post.post_id for post in OBSERVATION_POSTS} - {own_post}


def test_reveal_deployment_counts_for_distraction() -> None:
    # A Reveal turn is a turn of its own [Main p. 8]: units deployed in it
    # count for the card played in it.
    rival_post = _post(3)
    detonation = _intrigue("detonation")
    distraction = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(detonation, distraction),
        troops_supply=9,
        troops_garrison=3,
    )
    state = replace(
        _turn_state(owner),
        players=(
            owner,
            _spy_rival(rival_post),
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
    )
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state
    assert _play(revealed, distraction) not in engine.legal_actions(revealed, 0)

    opened = engine.apply(revealed, _play(revealed, detonation, 1)).state
    deployed = engine.apply(
        opened,
        DomainAction(
            action_id="deploy_intrigue_troops", actor=0, arguments=(("count", 3),)
        ),
    ).state
    assert deployed.decision_stack[-1].kind == "reveal"
    played = engine.apply(deployed, _play(deployed, distraction)).state
    assert played.decision_stack[-1].kind == "intrigue_choice"
    assert played.decision_stack[-2].kind == "reveal"
    done = engine.apply(played, _place_intrigue_spy(rival_post)).state
    assert done.decision_stack[-1].kind == "reveal"
    assert rival_post in done.players[0].spy_post_ids


def test_sandworm_summon_counts_as_a_deployed_unit() -> None:
    card = _intrigue("unexpected_allies")
    owner = PlayerState(
        player_id=0, intrigue_cards=(card,), resources=Resources(water=2)
    )
    state = replace(
        _turn_state(owner),
        current_conflict_ids=(_conflict(False),),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    done = engine.apply(opened, _keep_wall()).state
    # A summoned sandworm is immediately deployed [Main p. 20].
    assert done.players[0].sandworms_conflict == 1
    assert done.players[0].units_deployed_turn == 1


def test_distraction_recalls_a_spy_first_when_the_supply_is_empty() -> None:
    rival_post = _post(4)
    own_posts = (_post(5), _post(6), _post(7))
    card = _intrigue("distraction")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        spies_supply=0,
        spy_post_ids=own_posts,
        units_deployed_turn=3,
    )
    state = replace(
        _turn_state(owner),
        players=(
            owner,
            _spy_rival(rival_post),
            PlayerState(player_id=2),
            PlayerState(player_id=3),
        ),
    )
    engine = UprisingRulesEngine()
    played = engine.apply(state, _play(state, card)).state
    assert played.decision_stack[-1].kind == "intrigue_choice"

    # "If you have no Spies in your supply when you need to place one, you
    # may first recall one of your Spies for no effect." [Main p. 11]: the
    # recall is the owner's choice, as for every Intrigue Spy (OQ-057 (14)).
    actions = engine.legal_actions(played, 0)
    assert DomainAction(action_id="decline_intrigue_spy", actor=0) in actions
    recall_ids = {
        dict(action.arguments)["post_id"]
        for action in actions
        if action.action_id == "recall_spy_for_intrigue"
    }
    assert recall_ids == set(own_posts)

    recalled = engine.apply(
        played,
        DomainAction(
            action_id="recall_spy_for_intrigue",
            actor=0,
            arguments=(("post_id", own_posts[0]),),
        ),
    ).state
    # The recall keeps the slot open, and the freed Spy must now be placed:
    # "recall한 뒤에는 그 Spy가 supply에 있으므로 배치가 의무다" (OQ-057 (14)).
    assert recalled.decision_stack[-1].kind == "intrigue_choice"
    after_recall = engine.legal_actions(recalled, 0)
    assert after_recall
    assert {action.action_id for action in after_recall} == {"place_intrigue_spy"}
    done = engine.apply(recalled, _place_intrigue_spy(rival_post)).state
    assert rival_post in done.players[0].spy_post_ids
    assert done.intrigue_discard == (card,)


def test_leverage_needs_spice_gained_this_turn() -> None:
    card = _intrigue("leverage")
    # Holding Spice is not gaining it: a fresh turn snapshot equals the
    # current total, so the condition does not hold.
    idle = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        resources=Resources(spice=5),
        spice_at_turn_start=5,
    )
    state = replace(
        _turn_state(idle),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate",),
    )
    assert legal_intrigue_play_actions(state, 0) == ()

    # Spending down to the starting total does not hide the gain.
    churned = replace(
        idle, resources=Resources(spice=5), spice_at_turn_start=5, spice_spent_turn=2
    )
    churning = replace(
        _turn_state(churned),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:heighliner_ii",),
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(churning, 0) == (_play(churning, card),)

    market = engine.apply(churning, _play(churning, card)).state
    assert market.players[0].resources.solari == 1
    assert market.decision_stack[-1].kind == "contract_market"
    taken = engine.apply(
        market,
        DomainAction(
            action_id="take_contract",
            actor=0,
            arguments=(("instance_id", "contract:heighliner_ii"),),
        ),
    ).state
    assert "contract:heighliner_ii" in taken.players[0].active_contract_ids
    assert taken.intrigue_discard == (card,)


def test_leverage_sees_spice_gained_through_a_played_intrigue() -> None:
    leverage = _intrigue("leverage")
    market_card = _intrigue("market_opportunity")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(market_card, leverage),
        resources=Resources(solari=5),
    )
    state = replace(
        _turn_state(owner),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate",),
    )
    engine = UprisingRulesEngine()
    assert _play(state, leverage) not in legal_intrigue_play_actions(state, 0)

    # Market Opportunity's second half turns 5 Solari into 5 Spice.
    swapped = engine.apply(state, _play(state, market_card, 1)).state
    assert swapped.players[0].resources.spice == 5
    assert _play(swapped, leverage) in legal_intrigue_play_actions(swapped, 0)

    # After this player's turn passes, the next turn starts a fresh snapshot.
    revealed = engine.apply(swapped, _reveal(swapped)).state
    finished = engine.apply(
        revealed, DomainAction(action_id="finish_reveal", actor=0)
    ).state
    follower = finished.players[1]
    assert follower.spice_at_turn_start == follower.resources.spice
    assert follower.spice_spent_turn == 0


def _endgame_window(owner: PlayerState, *, choam: bool = False) -> GameState:
    from dune_imperium.rules.endgame import begin_endgame_intrigue

    state = GameState(
        config=RulesetConfig(choam_module=choam),
        seed=1,
        phase=GamePhase.ENDGAME,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    )
    return begin_endgame_intrigue(state).state


def _conflict_with_icon(icon_name: str) -> str:
    from dune_imperium.content.uprising.conflicts import CONFLICTS
    from dune_imperium.content.uprising.types import BattleIcon

    return next(
        conflict.card.card_id
        for conflict in CONFLICTS
        if conflict.battle_icon is BattleIcon(icon_name)
    )


def test_crysknife_flips_a_matching_conflict_card_for_a_point() -> None:
    card = _intrigue("crysknife")
    printed = _conflict_with_icon("crysknife")
    wild = _conflict_with_icon("wild")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        won_conflict_ids=(printed, wild),
    )
    state = _endgame_window(owner)
    engine = UprisingRulesEngine()

    # Only the Endgame half is offered inside the window.
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 1),)
    opened = engine.apply(state, _play(state, card, 1)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    targets = {
        dict(action.arguments)["card_id"]
        for action in engine.legal_actions(opened, 0)
    }
    # The printed icon or the wild icon may be flipped [Crysknife card].
    assert targets == {printed, wild}

    done = engine.apply(
        opened,
        DomainAction(
            action_id="flip_battle_card",
            actor=0,
            arguments=(("card_id", printed),),
        ),
    ).state
    assert done.players[0].victory_points == 2
    assert done.players[0].face_down_battle_card_ids == (printed,)
    assert done.intrigue_discard == (card,)
    assert done.decision_stack[-1].kind == "endgame_intrigue"


def test_endgame_flip_takes_a_face_up_objective_card() -> None:
    card = _intrigue("desert_mouse")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        objective_ids=("objective_desert_mouse",),
    )
    state = _endgame_window(owner)
    engine = UprisingRulesEngine()

    # An Objective reads "This counts as a Conflict card you've already
    # won." [Objective card], so the Desert Mouse flip may take it (OQ-005,
    # user ruling 2026-10-04).
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 1),)
    opened = engine.apply(state, _play(state, card, 1)).state
    targets = [
        dict(action.arguments)["card_id"] for action in engine.legal_actions(opened, 0)
    ]
    assert targets == ["objective_desert_mouse"]

    done = engine.apply(
        opened,
        DomainAction(
            action_id="flip_battle_card",
            actor=0,
            arguments=(("card_id", "objective_desert_mouse"),),
        ),
    ).state
    assert done.players[0].victory_points == 2
    assert done.players[0].face_down_battle_card_ids == ("objective_desert_mouse",)


def test_endgame_flip_leaves_a_face_down_objective_alone() -> None:
    card = _intrigue("crysknife")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        objective_ids=("objective_crysknife_1",),
        face_down_battle_card_ids=("objective_crysknife_1",),
    )
    state = _endgame_window(owner)
    # Only a face-up card can be flipped face down.
    assert legal_intrigue_play_actions(state, 0) == ()


def test_crysknife_plot_half_gains_spice_during_a_turn() -> None:
    card = _intrigue("crysknife")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _turn_state(owner)
    engine = UprisingRulesEngine()

    assert legal_intrigue_play_actions(state, 0) == (_play(state, card, 0),)
    done = engine.apply(state, _play(state, card, 0)).state
    assert done.players[0].resources.spice == 1


def test_choam_profits_needs_four_completed_contracts() -> None:
    card = _intrigue("choam_profits")
    contracts = tuple(f"contract:heighliner_i{'i' * copy}" for copy in range(1, 4))
    short = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        completed_contract_ids=contracts,
    )
    assert legal_intrigue_play_actions(_endgame_window(short, choam=True), 0) == ()

    full = replace(
        short, completed_contract_ids=(*contracts, "contract:arrakeen_i")
    )
    state = _endgame_window(full, choam=True)
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    done = engine.apply(state, _play(state, card)).state
    assert done.players[0].victory_points == 2


def test_secure_spice_trade_counts_owned_spice_must_flow_copies() -> None:
    card = _intrigue("secure_spice_trade")
    single = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        deck=("reserve:the_spice_must_flow:0",),
        trashed=("reserve:the_spice_must_flow:1",),
    )
    # A trashed copy has left the game, so one owned copy is not enough.
    assert legal_intrigue_play_actions(_endgame_window(single), 0) == ()

    double = replace(
        single,
        discard_pile=("reserve:the_spice_must_flow:2",),
    )
    state = _endgame_window(double)
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)
    done = engine.apply(state, _play(state, card)).state
    assert done.players[0].victory_points == 2
    assert done.players[0].resources.spice == 2


def test_shadow_alliance_needs_an_opponent_held_alliance() -> None:
    card = _intrigue("shadow_alliance")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        influence=Influence(fremen=4),
    )
    # Nobody holds the Fremen Alliance: the condition does not hold.
    assert legal_intrigue_play_actions(_endgame_window(owner), 0) == ()

    # Holding the Alliance oneself does not satisfy the card either.
    self_held = replace(owner, alliance_faction_ids=("fremen",))
    assert legal_intrigue_play_actions(_endgame_window(self_held), 0) == ()

    state = _endgame_window(owner)
    rival = replace(
        state.players[2],
        influence=Influence(fremen=5),
        alliance_faction_ids=("fremen",),
    )
    contested = replace(
        state, players=(*state.players[:2], rival, state.players[3])
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(contested, 0) == (_play(contested, card),)
    done = engine.apply(contested, _play(contested, card)).state
    assert done.players[0].victory_points == 2


def test_a_window_may_play_several_endgame_cards_before_passing() -> None:
    crysknife = _intrigue("crysknife")
    mouse = _intrigue("desert_mouse")
    printed = _conflict_with_icon("crysknife")
    wild = _conflict_with_icon("wild")
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(crysknife, mouse),
        won_conflict_ids=(printed, wild),
    )
    state = _endgame_window(owner)
    engine = UprisingRulesEngine()

    first = engine.apply(state, _play(state, crysknife, 1)).state
    flipped = engine.apply(
        first,
        DomainAction(
            action_id="flip_battle_card",
            actor=0,
            arguments=(("card_id", printed),),
        ),
    ).state
    # Desert Mouse may still flip the remaining wild Conflict card.
    second = engine.apply(flipped, _play(flipped, mouse, 1)).state
    done = engine.apply(
        second,
        DomainAction(
            action_id="flip_battle_card",
            actor=0,
            arguments=(("card_id", wild),),
        ),
    ).state
    assert done.players[0].victory_points == 3
    assert set(done.players[0].face_down_battle_card_ids) == {printed, wild}
    assert done.decision_stack[-1].kind == "endgame_intrigue"

    # Passing every window afterwards finishes the game.
    working = done
    for seat in range(4):
        working = engine.apply(
            working,
            DomainAction(action_id="pass_endgame_intrigue", actor=seat),
        ).state
    assert working.phase is GamePhase.FINISHED


def test_spring_the_trap_recalls_two_spies_for_seven_swords() -> None:
    card = _intrigue("spring_the_trap")
    posts = (_post(0), _post(1))
    fighter = _fighter(
        0,
        1,
        intrigue_cards=(card,),
        spies_supply=1,
        spy_post_ids=posts,
    )
    state = _combat_state(fighter)
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    first = engine.apply(
        opened,
        DomainAction(
            action_id="recall_spy_for_intrigue",
            actor=0,
            arguments=(("post_id", posts[0]),),
        ),
    ).state
    done = engine.apply(
        first,
        DomainAction(
            action_id="recall_spy_for_intrigue",
            actor=0,
            arguments=(("post_id", posts[1]),),
        ),
    ).state
    assert done.players[0].spies_supply == 3
    assert done.players[0].combat_strength == 9
    assert done.intrigue_discard == (card,)
    assert done.decision_stack[-1].kind == "combat_intrigue"

    # With fewer than two placed Spies the mandatory cost cannot be paid.
    lone = _combat_state(
        _fighter(0, 1, intrigue_cards=(card,), spies_supply=2, spy_post_ids=(posts[0],))
    )
    assert legal_intrigue_play_actions(lone, 0) == ()


def test_manipulate_sets_a_row_card_aside_for_its_owner() -> None:
    card = _intrigue("manipulate")
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    targets = {
        dict(action.arguments)["instance_id"]
        for action in engine.legal_actions(opened, 0)
    }
    assert targets == set(state.imperium_row)

    done = engine.apply(
        opened,
        DomainAction(
            action_id="manipulate_imperium_row",
            actor=0,
            arguments=(("instance_id", cheap),),
        ),
    ).state
    # The Row is replaced at once and the card waits with its owner.
    assert cheap not in done.imperium_row
    assert done.imperium_row == (
        _imperium_instance("maula_pistol"),
        _imperium_instance("steersman"),
    )
    assert done.players[0].imperium_set_aside == (cheap,)
    assert done.intrigue_discard == (card,)


def test_manipulate_with_an_empty_deck_shrinks_the_row() -> None:
    # OQ-004 convention: nothing refills the set-aside position once the
    # Imperium Deck is exhausted [Main p. 13]; the Row keeps fewer cards.
    card = _intrigue("manipulate")
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, intrigue_cards=(card,))
    state = replace(_with_market(_turn_state(owner)), imperium_deck=())
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    done = engine.apply(
        opened,
        DomainAction(
            action_id="manipulate_imperium_row",
            actor=0,
            arguments=(("instance_id", cheap),),
        ),
    ).state

    assert done.imperium_row == (_imperium_instance("steersman"),)
    assert done.imperium_deck == ()
    assert done.players[0].imperium_set_aside == (cheap,)


def test_manipulated_card_is_acquired_at_a_discount_during_the_reveal() -> None:
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, imperium_set_aside=(cheap,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()

    # Sardaukar Soldier costs 1, so the discount makes it free: the option
    # appears even with zero Persuasion, for the owner only.
    revealed = engine.apply(state, _reveal(state)).state
    offers = [
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "acquire_manipulated_imperium"
    ]
    assert offers == [
        DomainAction(
            action_id="acquire_manipulated_imperium",
            actor=0,
            arguments=(("instance_id", cheap),),
        )
    ]
    assert engine.legal_actions(revealed, 1) == ()

    result = engine.apply(revealed, offers[0])
    done = result.state
    assert done.players[0].imperium_set_aside == ()
    assert done.players[0].discard_pile == (cheap,)
    acquired = next(e for e in result.events if e.kind == "card_acquired")
    assert dict(acquired.payload)["discount"] == 1
    # The Row is untouched by a set-aside acquisition.
    assert done.imperium_row == state.imperium_row


def test_manipulated_card_spends_the_discounted_persuasion() -> None:
    spy_network = _imperium_instance("spy_network")
    owner = PlayerState(
        player_id=0,
        imperium_set_aside=(spy_network,),
        hand=_persuasion_hand(1),
    )
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    acquired = engine.apply(
        revealed,
        DomainAction(
            action_id="acquire_manipulated_imperium",
            actor=0,
            arguments=(("instance_id", spy_network),),
        ),
    ).state
    # Spy Network costs 2: one Persuasion is spent and its acquire box opens
    # the shared Spy placement frame [Main p. 20].
    frame = acquired.decision_stack[-1]
    assert frame.kind == "acquisition_spy"
    reveal_frame = acquired.decision_stack[-2]
    assert dict(reveal_frame.context)["persuasion"] == 1

    placed = engine.apply(
        acquired, engine.legal_actions(acquired, 0)[0]
    ).state
    assert len(placed.players[0].spy_post_ids) == 1
    assert placed.decision_stack[-1].kind == "reveal"


def test_unacquired_manipulated_card_leaves_the_game_with_the_reveal() -> None:
    cheap = _imperium_instance("sardaukar_soldier")
    owner = PlayerState(player_id=0, imperium_set_aside=(cheap,))
    state = _with_market(_turn_state(owner))
    engine = UprisingRulesEngine()
    revealed = engine.apply(state, _reveal(state)).state

    result = engine.apply(
        revealed, DomainAction(action_id="finish_reveal", actor=0)
    )
    done = result.state
    assert done.players[0].imperium_set_aside == ()
    assert done.players[0].discard_pile == ()
    assert done.imperium_removed == (cheap,)
    assert "imperium_card_removed" in [event.kind for event in result.events]


def test_inspire_awe_reaches_its_owners_set_aside_card_at_the_printed_cost() -> (
    None
):
    # "You may use other means to acquire the card (for example: Bypass
    # Protocol, Boundless Ambition), though the 1 persuasion discount will
    # not apply" [FAQ p. 3]: Inspire Awe's cap of 3 reads the printed cost.
    card = _intrigue("inspire_awe")
    survival = _imperium_instance("desert_survival")  # costs 2
    paracompass = _imperium_instance("paracompass")  # costs 4 (3 discounted)
    rival_card = _imperium_instance("hidden_missive")  # costs 2
    owner = PlayerState(
        player_id=0,
        intrigue_cards=(card,),
        imperium_set_aside=(survival, paracompass),
    )
    state = _with_market(_turn_state(owner))
    rival = replace(state.players[1], imperium_set_aside=(rival_card,))
    state = replace(state, players=(state.players[0], rival, *state.players[2:]))
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    # The owner's set-aside card follows the Row; Paracompass is over the
    # cap without the discount, and an opponent's set-aside card is never
    # offered [FAQ p. 3].
    assert engine.legal_actions(opened, 0) == (
        _acquire_reserve("prepare_the_way"),
        _acquire_imperium(_imperium_instance("sardaukar_soldier")),
        _acquire_imperium(survival),
    )

    result = engine.apply(opened, _acquire_imperium(survival))
    done = result.state
    assert "card_acquired" in [event.kind for event in result.events]
    assert done.players[0].discard_pile == (survival,)
    assert done.players[0].imperium_set_aside == (paracompass,)
    # The Row refilled when the card was set aside, so nothing refills now.
    assert done.imperium_row == state.imperium_row
    assert done.imperium_deck == state.imperium_deck
    assert done.players[1].imperium_set_aside == (rival_card,)
    assert done.intrigue_discard == (card,)
    assert done.decision_stack == _after_plot(state)


def test_reach_agreement_retreats_for_a_contract_in_the_choam_module() -> None:
    card = _intrigue("reach_agreement")
    fighter = _fighter(0, 2, intrigue_cards=(card,))
    state = replace(
        _combat_state(fighter, _fighter(1, 1)),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate", "contract:heighliner_ii"),
        contract_bank=(),
    )
    engine = UprisingRulesEngine()

    opened = engine.apply(state, _play(state, card)).state
    assert engine.legal_actions(opened, 0) == (_retreat(1), _retreat(2))
    market = engine.apply(opened, _retreat(1)).state
    assert market.decision_stack[-1].kind == "contract_market"
    assert {a.action_id for a in engine.legal_actions(market, 0)} == {"take_contract"}

    # Without the CHOAM Module the Contract icon has no market to use.
    assert legal_intrigue_play_actions(_combat_state(fighter), 0) == ()



def test_reach_agreement_needs_a_contract_it_can_take() -> None:
    # "You can't take the new Immediate contract unless you have an Intrigue
    # card to trash." [Bloodlines p. 2]: with only that token face up and no
    # other Intrigue card held, the Contract icon changes nothing.
    card = _intrigue("reach_agreement")
    option = intrigue_card_for_instance(card).options[0]
    choam = RulesetConfig(choam_module=True, bloodlines=True)

    def combat(fighter: PlayerState, **extra: object) -> GameState:
        return replace(
            _combat_state(fighter, _fighter(1, 1)),
            config=choam,
            face_up_contract_ids=("contract:bloodlines_immediate",),
            contract_bank=(),
            **extra,  # type: ignore[arg-type]
        )

    alone = combat(_fighter(0, 2, intrigue_cards=(card,)))
    assert legal_intrigue_play_actions(alone, 0) == ()
    assert option_unplayable_reason(alone, 0, option) == TakeContract()

    # Another Intrigue card to trash, an empty market (2 Solari [Main
    # p. 16]), or Shaddam's set-aside Sardaukar Contract [FAQ p. 3] each
    # make it playable.
    second = combat(_fighter(0, 2, intrigue_cards=(card, _intrigue("cunning"))))
    empty_market = replace(alone, face_up_contract_ids=())
    shaddam = combat(
        _fighter(0, 2, intrigue_cards=(card,), leader_id="shaddam_corrino_iv"),
        sardaukar_contract_ids=("contract:sardaukar_i",),
    )
    for state in (second, empty_market, shaddam):
        assert legal_intrigue_play_actions(state, 0) == (_play(state, card),)


def _reach_agreement_after_two_passes(troops: int) -> tuple[GameState, str]:
    """Seats 0 and 1 have passed (two in a row); seat 2 holds Reach Agreement
    and ``troops`` troops, and the CHOAM market can pay its Contract."""

    card = _intrigue("reach_agreement")
    state = replace(
        _combat_state(
            _fighter(0, 1), _fighter(1, 1), _fighter(2, troops, intrigue_cards=(card,))
        ),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate", "contract:heighliner_ii"),
        contract_bank=(),
    )
    engine = UprisingRulesEngine()
    state = engine.apply(engine.apply(state, _pass(0)).state, _pass(1)).state
    assert dict(state.decision_stack[-1].context)["consecutive_passes"] == 2
    return state, card


def _take_first_contract(state: GameState, actor: int) -> GameState:
    engine = UprisingRulesEngine()
    take = next(
        a for a in engine.legal_actions(state, actor) if a.action_id == "take_contract"
    )
    return engine.apply(state, take).state


def test_a_combat_intrigue_that_opens_a_contract_market_restarts_the_passes() -> None:
    """ "전투 참여자 전원이 **연속으로** pass했을 때만 카드 플레이 절차를 끝내고
    Combat를 해결한다." [Main p. 14] (docs/rules/combat-and-round-end.md).
    Reach Agreement leaves its Contract market above the Combat Intrigue
    loop when its play finishes; the play still restarts the pass count, so
    the seats that passed before it answer again. Before 2026-10-02 the
    count stayed at two and seat 2's next pass ended Combat Intrigue."""

    engine = UprisingRulesEngine()
    state, card = _reach_agreement_after_two_passes(2)
    play = DomainAction(
        action_id="play_intrigue", actor=2, arguments=(("card_id", card), ("option", 0))
    )
    market = engine.apply(engine.apply(state, play).state, _retreat(1, actor=2)).state
    assert market.decision_stack[-1].kind == "contract_market"
    loop = next(f for f in market.decision_stack if f.kind == "combat_intrigue")
    assert dict(loop.context)["consecutive_passes"] == 0

    after = _take_first_contract(market, 2)
    assert dict(after.decision_stack[-1].context)["consecutive_passes"] == 0
    once = engine.apply(after, _pass(2)).state
    assert once.combat_intrigue_complete is False
    assert once.decision_stack[-1].decision.owner == 0  # type: ignore[union-attr]
    twice = engine.apply(once, _pass(0)).state
    assert twice.combat_intrigue_complete is False
    done = engine.apply(twice, _pass(1)).state
    assert done.combat_intrigue_complete is True


def test_a_seat_left_without_units_leaves_the_loop_once_its_market_closes() -> (
    None
):
    """OQ-003 (project convention): a player whose last unit leaves the
    Conflict during Combat Intrigue is removed from the loop at once. When
    Reach Agreement retreats seat 2's last troops and leaves its Contract
    market open, the loop drops seat 2 as soon as the market closes and
    priority passes clockwise to seat 0."""

    engine = UprisingRulesEngine()
    state, card = _reach_agreement_after_two_passes(2)
    play = DomainAction(
        action_id="play_intrigue", actor=2, arguments=(("card_id", card), ("option", 0))
    )
    market = engine.apply(engine.apply(state, play).state, _retreat(2, actor=2)).state
    assert market.players[2].troops_conflict == 0

    after = _take_first_contract(market, 2)
    top = after.decision_stack[-1]
    assert top.kind == "combat_intrigue"
    assert dict(top.context)["participants_mask"] == 0b011
    assert top.decision.owner == 0  # type: ignore[union-attr]
    once = engine.apply(after, _pass(0)).state
    done = engine.apply(once, _pass(1)).state
    assert done.combat_intrigue_complete is True


def test_battlefield_research_drops_its_player_after_the_tech_window() -> None:
    """The same two rules when the window is Battlefield Research's Tech
    acquisition ("Retreat one or two of your troops -> Acquire Tech"
    [card face]): seat 2 retreats its last troop, buys the tile, and the loop
    then drops it (OQ-003) and counts the passes from zero again [Main p. 14].
    Before 2026-10-02 seat 2 -- with no unit left -- was offered the next
    pass, and that one pass ended Combat Intrigue."""

    card = _intrigue("battlefield_research")
    state = replace(
        _combat_state(
            _fighter(0, 1),
            _fighter(1, 1),
            _fighter(2, 1, intrigue_cards=(card,), resources=Resources(spice=2)),
        ),
        config=RulesetConfig(bloodlines=True, tech_module=True),
        tech_stacks=(("plasteel_blades",), ("delivery_bay",), ("servo_receivers",)),
    )
    engine = UprisingRulesEngine()
    state = engine.apply(engine.apply(state, _pass(0)).state, _pass(1)).state
    play = DomainAction(
        action_id="play_intrigue", actor=2, arguments=(("card_id", card), ("option", 0))
    )
    window = engine.apply(engine.apply(state, play).state, _retreat(1, actor=2)).state
    assert window.decision_stack[-1].kind == "tech_acquisition"
    assert window.players[2].troops_conflict == 0

    buy = next(
        a
        for a in engine.legal_actions(window, 2)
        if dict(a.arguments).get("tech_id") == "plasteel_blades"
    )
    after = engine.apply(window, buy).state
    # OQ-098: the once-only acquire icons [Bloodlines p. 7] are choices
    # owned by the buyer before Battlefield Research returns to Combat.
    assert after.decision_stack[-1].kind == "tech_acquisition"
    reward = next(
        action
        for action in engine.legal_actions(after, 2)
        if action.action_id == "resolve_tech_acquire_effect"
    )
    after = engine.apply(after, reward).state
    top = after.decision_stack[-1]
    assert top.kind == "combat_intrigue"
    assert dict(top.context)["participants_mask"] == 0b011
    assert dict(top.context)["consecutive_passes"] == 0
    assert top.decision.owner == 0  # type: ignore[union-attr]
    once = engine.apply(after, _pass(0)).state
    assert once.combat_intrigue_complete is False
    done = engine.apply(once, _pass(1)).state
    assert done.combat_intrigue_complete is True


def _to_next_round(state: GameState) -> GameState:
    """Give a Combat Intrigue test state the next round's Conflict, so an
    emptied loop runs on through Combat into round 2 instead of Endgame."""

    return replace(state, conflict_deck=(_conflict(True),), reveal_order=(0, 1, 2, 3))


def _finished(events: tuple[GameEvent, ...]) -> list[GameEvent]:
    return [event for event in events if event.kind == "combat_intrigue_finished"]


def test_a_card_that_empties_the_loop_still_announces_the_stage_end() -> None:
    """OQ-003: the loop ends once its last participant has no unit. That
    ending emits the same ``combat_intrigue_finished`` as the last pass and a
    Conflict nobody entered, with an event id ending in ``:emptied`` and no
    payload (2026-10-02; it used to end silently, and the log missed its
    "Combat Intrigue stage finished" line). Go to Ground retreats the only
    participant's troop and finishes its play with the Spy placement. These
    tests pin the event after the choice's or window's own events; no
    current card's own reward emits an event on an emptying play, so the
    order inside ``finish_intrigue_play`` is not exercised."""

    card = _intrigue("go_to_ground")
    state = _to_next_round(_combat_state(_fighter(0, 1, intrigue_cards=(card,))))
    engine = UprisingRulesEngine()
    opened = engine.apply(engine.apply(state, _play(state, card)).state, _retreat(1))
    assert _finished(opened.events) == []
    spy = next(
        a
        for a in engine.legal_actions(opened.state, 0)
        if a.action_id == "place_intrigue_spy"
    )
    placed = engine.apply(opened.state, spy)
    kinds = [event.kind for event in placed.events]
    assert kinds.index("spy_placed") < kinds.index("combat_intrigue_finished")
    assert kinds.index("combat_intrigue_finished") < kinds.index("combat_cleaned_up")
    (finished,) = _finished(placed.events)
    assert finished.event_id == "round:1:combat_intrigue:emptied"
    assert finished.payload == ()


def test_a_loop_emptied_behind_a_window_announces_the_end_when_it_closes() -> (
    None
):
    """The same ending when Reach Agreement's Contract market is still open
    as the play finishes: the engine drops the seat once the market closes,
    and the stage-end event follows the Contract's own events (OQ-003)."""

    card = _intrigue("reach_agreement")
    state = replace(
        _to_next_round(_combat_state(_fighter(0, 2, intrigue_cards=(card,)))),
        config=RulesetConfig(choam_module=True),
        face_up_contract_ids=("contract:immediate", "contract:heighliner_ii"),
        contract_bank=(),
    )
    engine = UprisingRulesEngine()
    play = DomainAction(
        action_id="play_intrigue", actor=0, arguments=(("card_id", card), ("option", 0))
    )
    retreated = engine.apply(engine.apply(state, play).state, _retreat(2))
    assert retreated.state.decision_stack[-1].kind == "contract_market"
    assert _finished(retreated.events) == []
    take = next(
        a
        for a in engine.legal_actions(retreated.state, 0)
        if a.action_id == "take_contract"
    )
    taken = engine.apply(retreated.state, take)
    kinds = [event.kind for event in taken.events]
    assert kinds.index("contract_taken") < kinds.index("combat_intrigue_finished")
    assert kinds.index("combat_intrigue_finished") < kinds.index("combat_cleaned_up")
    (finished,) = _finished(taken.events)
    assert finished.event_id == "round:1:combat_intrigue:emptied"
    assert finished.payload == ()
