"""The original Dune: Imperium's Intrigue cards (stage P3).

docs/rules/imperium-base.md 5 (Plot timing), 8 (Combat), 11 (the cost arrow,
Retreat), 13.2 (the FAQ rows) and 16 (cost lines need a live reward) with
docs/rules/open-questions.md OQ-003, OQ-058, OQ-060, OQ-071 and OQ-113; the
card text is the Steam app's (docs/base-game-and-ix-plan.md 16.3). Seat 0
holds the card, in an original-game ``RulesetConfig``.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import (
    DeployFromGarrison,
    HasAlliance,
    LoseTroops,
    PayResources,
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
    Influence,
    PlayerState,
    Resources,
)
from dune_imperium.display import intrigue_card_text
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.intrigue import (
    apply_intrigue_choice,
    apply_intrigue_play,
    legal_intrigue_play_actions,
)

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
FACTIONS = {"emperor", "spacing_guild", "bene_gesserit", "fremen"}


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of the original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _intrigue(card_id: str, copy: int = 0) -> str:
    return f"intrigue:{card_id}:{copy}"


def _play(card: str, option: int = 0, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=actor,
        arguments=(("card_id", card), ("option", option)),
    )


def _choose_faction(faction: str) -> DomainAction:
    return DomainAction(
        action_id="choose_intrigue_faction",
        actor=0,
        arguments=(("faction", faction),),
    )


def _offered_factions(engine: UprisingRulesEngine, state: GameState) -> set[str]:
    return {
        str(dict(action.arguments)["faction"])
        for action in engine.whole_actions(state, 0)
        if action.action_id == "choose_intrigue_faction"
    }


# --- Bribery (Plot) ---------------------------------------------------------

BRIBERY = _intrigue("bribery")


def _bribery_hand(
    solari: int = 2, influence: Influence | None = None
) -> tuple[UprisingRulesEngine, GameState]:
    engine, state = _start()
    return engine, _seat(
        state,
        intrigue_cards=(BRIBERY,),
        resources=Resources(solari=solari),
        influence=influence or Influence(),
    )


def test_bribery_is_one_plot_cost_line_with_one_copy() -> None:
    # "Plot: 2 Solari -> 1 Influence (any Faction)" [Bribery card, Steam app
    # text]; 1 copy in the deck [DI p. 3].
    entry = intrigue_card_for_instance(BRIBERY)
    assert entry.card.name == "Bribery"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert len(entry.options) == 1
    assert intrigue_card_text(entry) == [
        "Plot — Pay 2 solari → Gain 1 Influence (choose any Faction)"
    ]
    # Uprising's own card list is untouched (the original's cards are not in
    # it while stage P3 is a trial).
    assert "bribery" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_bribery_pays_two_solari_for_one_influence_of_the_chosen_faction() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서 아무 때나 낸다. `[DI pp.
    # 7-8]`" (imperium-base.md 5): playable at the start of the turn. The cost
    # arrow "비용 화살표" `[DI p. 16]` is paid when the card is played (FAQ's
    # "paying a cost is required" for an Intrigue card, OQ-058), the reward is
    # one Influence with a Faction of the player's choice.
    engine, state = _bribery_hand(solari=3)
    assert legal_intrigue_play_actions(state, 0) == (_play(BRIBERY),)

    opened = apply_whole(engine, state, _play(BRIBERY)).state
    assert opened.players[0].resources.solari == 1
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    # Any of the four Factions may be named; nobody else acts meanwhile.
    assert _offered_factions(engine, opened) == FACTIONS
    assert engine.whole_actions(opened, 1) == ()
    # The card stays in hand while its choice resolves.
    assert opened.players[0].intrigue_cards == (BRIBERY,)

    done = apply_whole(engine, opened, _choose_faction("spacing_guild"))
    player = done.state.players[0]
    assert player.influence == Influence(spacing_guild=1)
    assert player.resources.solari == 1
    assert player.intrigue_cards == ()
    assert done.state.intrigue_discard == (BRIBERY,)
    assert [e.kind for e in done.events if e.kind == "intrigue_without_effect"] == []
    # The turn goes on: the Plot did not end it.
    assert done.state.decision_stack[-1].kind == "turn"


def test_bribery_influence_goes_through_the_track_rules() -> None:
    # "Influence 2 도달 → 1 VP" `[DI p. 7]` (imperium-base.md 6): Bribery's
    # Influence is a normal gain, so reaching 2 scores the point.
    engine, state = _bribery_hand(influence=Influence(fremen=1))
    before = state.players[0].victory_points

    opened = apply_whole(engine, state, _play(BRIBERY)).state
    done = apply_whole(engine, opened, _choose_faction("fremen")).state

    assert done.players[0].influence.fremen == 2
    assert done.players[0].victory_points == before + 1


def test_bribery_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced: the seat keeps the card and
    # the two Solari and takes another turn action instead [DI pp. 7-8].
    engine, state = _bribery_hand()
    actions = engine.whole_actions(state, 0)
    assert _play(BRIBERY) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others, "the turn offers other actions beside the Plot"
    # Taking another action (here the Agent turn's card choice) leaves the
    # card and the Solari alone.
    placed = apply_whole(engine, state, others[0]).state
    assert placed.players[0].intrigue_cards == (BRIBERY,)
    assert placed.players[0].resources.solari == 2


def test_bribery_is_also_played_during_the_reveal_turn() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn
    # (imperium-base.md 5, `[DI pp. 7-8]`).
    engine, state = _bribery_hand()
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert _play(BRIBERY) in engine.whole_actions(revealed, 0)

    opened = apply_whole(engine, revealed, _play(BRIBERY)).state
    done = apply_whole(engine, opened, _choose_faction("emperor")).state
    assert done.players[0].influence.emperor == 1
    assert done.players[0].resources.solari == 0


def test_bribery_is_not_offered_to_a_seat_outside_its_own_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _bribery_hand()
    state = _seat(state, 1, intrigue_cards=(BRIBERY,), resources=Resources(solari=2))
    assert legal_intrigue_play_actions(state, 1) == ()


def test_bribery_needs_two_solari() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]` (Bribery is the FAQ's own example).
    engine, state = _bribery_hand(solari=1)
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(BRIBERY) not in engine.whole_actions(state, 0)


def test_bribery_names_only_factions_below_the_top_of_their_track() -> None:
    # OQ-060 (decided 2026-09-16): Influence on a track already at 6 is
    # discarded, so the choice lists the Factions that can still move.
    engine, state = _bribery_hand(
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=3, fremen=5)
    )
    opened = apply_whole(engine, state, _play(BRIBERY)).state
    assert _offered_factions(engine, opened) == {"bene_gesserit", "fremen"}

    done = apply_whole(engine, opened, _choose_faction("fremen")).state
    assert done.players[0].influence == Influence(
        emperor=6, spacing_guild=6, bene_gesserit=3, fremen=6
    )


def test_bribery_with_one_faction_below_six_still_names_it() -> None:
    # One live Faction: the Influence is still gained by naming it.
    engine, state = _bribery_hand(
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=5)
    )
    opened = apply_whole(engine, state, _play(BRIBERY)).state
    assert engine.whole_actions(opened, 0) == (_choose_faction("fremen"),)
    done = apply_whole(engine, opened, _choose_faction("fremen")).state
    assert done.players[0].influence.fremen == 6
    assert done.players[0].resources.solari == 0
    assert done.intrigue_discard == (BRIBERY,)


def test_bribery_is_not_played_when_every_track_is_at_six() -> None:
    # "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다(OQ-071)"
    # (imperium-base.md 16) — OQ-113 (C): a cost line needs a live reward, so
    # with all four tracks at 6 the two Solari are never paid for nothing.
    engine, state = _bribery_hand(
        solari=5,
        influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(BRIBERY) not in engine.whole_actions(state, 0)
    assert state.players[0].resources.solari == 5


# --- Master Tactician (Combat) ---------------------------------------------

TACTICIAN = _intrigue("master_tactician")


def _fighter(player_id: int, troops: int, **extra: object) -> PlayerState:
    """``troops`` in the Conflict, 2 swords each [DI p. 11]."""

    return PlayerState(
        player_id=player_id,
        troops_supply=12 - troops,
        troops_garrison=0,
        troops_conflict=troops,
        combat_strength=2 * troops,
        **extra,  # type: ignore[arg-type]
    )


def _combat_state(*players: PlayerState) -> GameState:
    """The original game's Combat Intrigue loop, seat 0 first."""

    seats = list(players)
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    content = content_for(CONFIG)
    state = GameState(
        config=CONFIG,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(content.conflicts[0].card.card_id,),
        maker_bonus_spice=tuple((space, 0) for space in content.maker_space_ids),
        players=tuple(seats),
    )
    return begin_combat_intrigue(state).state


def _retreat(count: int) -> DomainAction:
    return DomainAction(
        action_id="retreat_intrigue_troops", actor=0, arguments=(("count", count),)
    )


def test_master_tactician_is_one_card_kind_of_two_combat_options() -> None:
    # "Combat: +3 swords -OR- Retreat up to three of your troops." [Master
    # Tactician card, Steam app text]; 3 copies [DI p. 3]. The two halves are
    # exclusive options like Uprising's Tactical Option (OQ-058: "—OR—로 나뉜
    # 카드 ... 그대로 배타 option").
    entry = intrigue_card_for_instance(_intrigue("master_tactician", 2))
    assert entry.card.name == "Master Tactician"
    assert entry.copies == 3
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat", "combat"]
    assert intrigue_card_text(entry) == [
        "Combat — Gain 3 swords",
        "Combat — Retreat up to 3 troops",
    ]
    assert "master_tactician" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_master_tactician_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 8), never in the seat's Agent turn.
    _, state = _start()
    state = _seat(state, intrigue_cards=(TACTICIAN,))
    assert legal_intrigue_play_actions(state, 0) == ()


def test_master_tactician_gains_three_swords_and_is_discarded() -> None:
    # Option A: "+3 swords" — strength is troops x 2 plus swords
    # `[DI p. 11]` (imperium-base.md 8).
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(TACTICIAN,)), _fighter(1, 1)
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (
        _play(TACTICIAN, 0),
        _play(TACTICIAN, 1),
    )

    done = apply_whole(engine, state, _play(TACTICIAN, 0)).state

    assert done.players[0].combat_strength == 4 + 3
    assert done.players[0].troops_conflict == 2
    assert done.players[0].troops_garrison == 0
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (TACTICIAN,)
    # The card was played: the pass count restarts and the seat stays in.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0
    assert dict(frame.context)["participants_mask"] == 0b11


def test_master_tactician_retreat_offers_zero_to_three_troops() -> None:
    # Option B: "Retreat up to three of your troops" — "up to" allows zero
    # `[FAQ p. 3]` (imperium-base.md 13.2, the Chani and Rapid Mobilization
    # rows), never more than the printed three, never more than the Conflict
    # holds.
    engine = UprisingRulesEngine()
    two = _combat_state(_fighter(0, 2, intrigue_cards=(TACTICIAN,)), _fighter(1, 1))
    opened = apply_whole(engine, two, _play(TACTICIAN, 1)).state
    assert engine.whole_actions(opened, 0) == (_retreat(0), _retreat(1), _retreat(2))

    five = _combat_state(_fighter(0, 5, intrigue_cards=(TACTICIAN,)), _fighter(1, 1))
    opened = apply_whole(engine, five, _play(TACTICIAN, 1)).state
    assert engine.whole_actions(opened, 0) == (
        _retreat(0),
        _retreat(1),
        _retreat(2),
        _retreat(3),
    )


def test_master_tactician_retreats_the_chosen_troops_to_the_garrison() -> None:
    # "Retreat(garrison으로)" `[DI p. 16]`: the troops leave the Conflict for
    # the garrison and their strength leaves the total at once.
    engine = UprisingRulesEngine()
    state = _combat_state(
        _fighter(0, 5, intrigue_cards=(TACTICIAN,)), _fighter(1, 1)
    )
    opened = apply_whole(engine, state, _play(TACTICIAN, 1)).state
    # Resolve the slot without the dispatcher so the round does not run on.
    done = apply_intrigue_choice(opened, _retreat(3))

    player = done.state.players[0]
    assert player.troops_conflict == 2
    assert player.troops_garrison == 3
    assert player.combat_strength == 4
    assert "troops_retreated" in [event.kind for event in done.events]
    assert done.state.intrigue_discard == (TACTICIAN,)
    # No swords came with it: the options are exclusive.
    assert player.combat_strength == 2 * player.troops_conflict


def test_master_tactician_may_retreat_no_troops() -> None:
    # "up to" allows zero `[FAQ p. 3]`: playing the card and retreating none
    # is a played card (the passes restart) that moves nothing.
    engine = UprisingRulesEngine()
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(TACTICIAN,)), _fighter(1, 1)
    )
    opened = apply_whole(engine, state, _play(TACTICIAN, 1)).state

    result = apply_whole(engine, opened, _retreat(0))
    done = result.state

    assert "troops_retreated" not in [event.kind for event in result.events]
    assert done.players[0].troops_conflict == 2
    assert done.players[0].troops_garrison == 0
    assert done.players[0].combat_strength == 4
    assert TACTICIAN in done.intrigue_discard
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0


def test_master_tactician_retreating_the_last_troops_leaves_the_rotation() -> None:
    # OQ-003 (a): a seat with no unit left in the Conflict drops out of the
    # Combat Intrigue loop at once; with nobody left the stage ends.
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(0, 2, intrigue_cards=(TACTICIAN,)))
    opened = apply_whole(engine, state, _play(TACTICIAN, 1)).state
    assert engine.whole_actions(opened, 0) == (_retreat(0), _retreat(1), _retreat(2))

    done = apply_intrigue_choice(opened, _retreat(2))

    assert done.state.players[0].troops_garrison == 2
    assert done.state.players[0].combat_strength == 0
    assert done.state.combat_intrigue_complete is True
    assert done.state.decision_stack == ()
    finished = [e for e in done.events if e.kind == "combat_intrigue_finished"]
    assert [e.event_id for e in finished] == ["round:1:combat_intrigue:emptied"]


def test_master_tactician_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]` (imperium-base.md 8): a seat with no troop in the Conflict
    # takes no part, so it is never offered the card.
    state = _combat_state(
        PlayerState(player_id=0, intrigue_cards=(TACTICIAN,), troops_garrison=3),
        _fighter(1, 2),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    # Seat 1 is the participant with priority but holds no card.
    assert legal_intrigue_play_actions(state, 1) == ()



def _pass(actor: int) -> DomainAction:
    return DomainAction(action_id="pass_combat_intrigue", actor=actor)


# --- Ambush (Combat) --------------------------------------------------------

AMBUSH = _intrigue("ambush")


def test_ambush_is_one_cost_free_combat_option_with_two_copies() -> None:
    # "Combat: +4 swords" [Ambush card, Steam app text]; 2 copies [DI p. 3].
    # No arrow, no condition: a cost-free Combat line (OQ-113 (C)).
    entry = intrigue_card_for_instance(_intrigue("ambush", 1))
    assert entry.card.name == "Ambush"
    assert entry.copies == 2
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat"]
    assert entry.options[0].sections[0].costs == ()
    assert entry.options[0].sections[0].condition is None
    assert intrigue_card_text(entry) == ["Combat — Gain 4 swords"]
    assert "ambush" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_ambush_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 8, 10), never in the seat's Agent or Reveal turn.
    _, state = _start()
    state = _seat(state, intrigue_cards=(AMBUSH,))
    assert legal_intrigue_play_actions(state, 0) == ()


def test_ambush_gains_four_swords_and_is_discarded() -> None:
    # "strength는 troop 2 + sword 1"; Combat Intrigue strength changes update
    # the marker at once `[DI pp. 11-12]` (imperium-base.md 10).
    state = _combat_state(_fighter(0, 2, intrigue_cards=(AMBUSH,)), _fighter(1, 1))
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == (_play(AMBUSH),)

    result = apply_whole(engine, state, _play(AMBUSH))
    done = result.state

    assert done.players[0].combat_strength == 4 + 4
    assert done.players[0].troops_conflict == 2
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (AMBUSH,)
    # Nothing was paid: no resource event, no "without effect" note.
    kinds = [event.kind for event in result.events]
    assert "resources_paid" not in kinds
    assert "intrigue_without_effect" not in kinds
    assert "combat_strength_gained" in kinds
    # The card was played: the pass count restarts and the seat stays in.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0
    assert dict(frame.context)["participants_mask"] == 0b11


def test_ambush_copies_are_played_one_at_a_time() -> None:
    # Two copies in hand are two cards: each is its own instance and a play
    # discards exactly one of them.
    second = _intrigue("ambush", 1)
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(AMBUSH, second)), _fighter(1, 1)
    )
    assert legal_intrigue_play_actions(state, 0) == (_play(AMBUSH), _play(second))

    done = apply_whole(UprisingRulesEngine(), state, _play(second)).state

    assert done.players[0].combat_strength == 4 + 4
    assert done.players[0].intrigue_cards == (AMBUSH,)
    assert done.intrigue_discard == (second,)


def test_ambush_may_be_declined_by_passing() -> None:
    # Playing is a choice, never forced: the seat passes and keeps the card
    # `[DI p. 12]` (imperium-base.md 10: "Combat Intrigue를 내거나 pass한다").
    state = _combat_state(_fighter(0, 2, intrigue_cards=(AMBUSH,)), _fighter(1, 1))
    engine = UprisingRulesEngine()
    assert _pass(0) in engine.whole_actions(state, 0)

    passed = apply_whole(engine, state, _pass(0)).state

    assert passed.players[0].intrigue_cards == (AMBUSH,)
    assert passed.players[0].combat_strength == 4
    assert passed.intrigue_discard == ()


def test_ambush_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]` (imperium-base.md 10): a seat with no troop in the Conflict
    # takes no part, so it is never offered the card.
    state = _combat_state(
        PlayerState(player_id=0, intrigue_cards=(AMBUSH,), troops_garrison=3),
        _fighter(1, 2),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    assert legal_intrigue_play_actions(state, 1) == ()


def test_ambush_is_offered_only_to_the_seat_with_priority() -> None:
    # Participants act in turn from the First Player [DI p. 12]
    # (imperium-base.md 10): seat 1 holds a card but seat 0 has priority.
    state = _combat_state(
        _fighter(0, 2), _fighter(1, 1, intrigue_cards=(AMBUSH,))
    )
    assert legal_intrigue_play_actions(state, 1) == ()
    passed = apply_whole(UprisingRulesEngine(), state, _pass(0)).state
    assert legal_intrigue_play_actions(passed, 1) == (_play(AMBUSH, actor=1),)


# --- CHOAM Shares (Plot) ----------------------------------------------------

SHARES = _intrigue("choam_shares")


def _plot_hand(card: str, **changes: Any) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 at its first turn holding ``card``, with ``changes`` applied."""

    engine, state = _start()
    return engine, _seat(state, intrigue_cards=(card,), **changes)


def test_choam_shares_is_one_plot_cost_line() -> None:
    # "Plot: 7 Solari -> 1 VP" [CHOAM Shares card, Steam app text]; 1 copy
    # [DI p. 3].
    entry = intrigue_card_for_instance(SHARES)
    assert entry.card.name == "CHOAM Shares"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert len(entry.options) == 1
    assert intrigue_card_text(entry) == ["Plot — Pay 7 solari → Gain 1 VP"]
    assert "choam_shares" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_choam_shares_pays_seven_solari_for_one_victory_point() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`, and "CHOAM Shares는 7 Solari를 내야 낸다"
    # (imperium-base.md 13.3); the arrow cost is required once the card is
    # played `[FAQ p. 3]`.
    engine, state = _plot_hand(SHARES, resources=Resources(solari=9, spice=1))
    assert legal_intrigue_play_actions(state, 0) == (_play(SHARES),)
    points = state.players[0].victory_points

    result = apply_intrigue_play(state, _play(SHARES))
    done = result.state

    assert done.players[0].resources == Resources(solari=2, spice=1)
    assert done.players[0].victory_points == points + 1
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (SHARES,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_paid",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["solari"] == 7
    assert dict(result.events[2].payload)["victory_points"] == 1
    # The turn goes on: the Plot did not end it.
    assert done.decision_stack[-1].kind == "turn"
    # The dispatcher reaches the same seats.
    assert apply_whole(engine, state, _play(SHARES)).state.players == done.players


def test_choam_shares_needs_the_full_seven_solari() -> None:
    # Six Solari do not pay the cost: the card is not offered, and nothing is
    # paid for a partial price (imperium-base.md 13.3, FAQ p. 2).
    engine, state = _plot_hand(SHARES, resources=Resources(solari=6, spice=9))
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(SHARES) not in engine.whole_actions(state, 0)

    exact = _seat(state, resources=Resources(solari=7))
    assert legal_intrigue_play_actions(exact, 0) == (_play(SHARES),)
    done = apply_whole(engine, exact, _play(SHARES)).state
    assert done.players[0].resources.solari == 0


def test_choam_shares_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat keeps
    # the card and the Solari and takes another turn action.
    engine, state = _plot_hand(SHARES, resources=Resources(solari=7))
    actions = engine.whole_actions(state, 0)
    assert _play(SHARES) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others, "the turn offers other actions beside the Plot"

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (SHARES,)
    assert placed.players[0].resources.solari == 7
    assert placed.players[0].victory_points == state.players[0].victory_points


def test_choam_shares_is_also_played_during_the_reveal_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서 아무 때나 낸다"
    # (imperium-base.md 5, `[DI pp. 7-8]`).
    engine, state = _plot_hand(SHARES, resources=Resources(solari=7))
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert _play(SHARES) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(SHARES)).state

    assert done.players[0].resources.solari == 0
    assert done.players[0].victory_points == state.players[0].victory_points + 1


def test_choam_shares_is_not_offered_to_a_seat_outside_its_own_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(SHARES)
    state = _seat(
        state, 1, intrigue_cards=(SHARES,), resources=Resources(solari=9)
    )
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Private Army (Combat) --------------------------------------------------

ARMY = _intrigue("private_army")


def test_private_army_is_one_combat_cost_line_with_two_copies() -> None:
    # "Combat: 2 spice -> +5 swords" [Private Army card, Steam app text];
    # 2 copies [DI p. 3].
    entry = intrigue_card_for_instance(_intrigue("private_army", 1))
    assert entry.card.name == "Private Army"
    assert entry.copies == 2
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat"]
    assert intrigue_card_text(entry) == ["Combat — Pay 2 spice → Gain 5 swords"]
    assert "private_army" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_private_army_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 10).
    _, state = _start()
    state = _seat(state, intrigue_cards=(ARMY,), resources=Resources(spice=5))
    assert legal_intrigue_play_actions(state, 0) == ()


def test_private_army_pays_two_spice_for_five_swords() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is
    # played `[FAQ p. 3]`; strength is troops x 2 plus swords `[DI p. 11]`.
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(ARMY,), resources=Resources(spice=3)),
        _fighter(1, 1),
    )
    assert legal_intrigue_play_actions(state, 0) == (_play(ARMY),)

    result = apply_whole(UprisingRulesEngine(), state, _play(ARMY))
    done = result.state

    assert done.players[0].resources == Resources(spice=1)
    assert done.players[0].combat_strength == 4 + 5
    assert done.players[0].troops_conflict == 2
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (ARMY,)
    kinds = [event.kind for event in result.events]
    assert kinds.index("resources_paid") < kinds.index("combat_strength_gained")
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0


def test_private_army_needs_two_spice() -> None:
    # One spice does not pay the cost: the card is not offered and nothing is
    # paid (FAQ p. 2).
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(ARMY,), resources=Resources(spice=1, solari=9)),
        _fighter(1, 1),
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(ARMY) not in engine.whole_actions(state, 0)
    # Solari are no substitute for the spice.
    assert state.players[0].resources == Resources(solari=9, spice=1)


def test_private_army_may_be_declined_by_passing() -> None:
    # Playing is a choice, never forced: the seat passes and keeps the card
    # and the spice `[DI p. 12]` (imperium-base.md 10).
    state = _combat_state(
        _fighter(0, 2, intrigue_cards=(ARMY,), resources=Resources(spice=2)),
        _fighter(1, 1),
    )
    engine = UprisingRulesEngine()
    assert _pass(0) in engine.whole_actions(state, 0)

    passed = apply_whole(engine, state, _pass(0)).state

    assert passed.players[0].intrigue_cards == (ARMY,)
    assert passed.players[0].resources == Resources(spice=2)
    assert passed.players[0].combat_strength == 4


def test_private_army_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]` (imperium-base.md 10): a seat with no troop in the Conflict
    # takes no part, so it is never offered the card, whatever it can pay.
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(ARMY,),
            troops_garrison=3,
            resources=Resources(spice=5),
        ),
        _fighter(1, 2),
    )
    assert legal_intrigue_play_actions(state, 0) == ()


# --- The Sleeper Must Awaken (Plot) -----------------------------------------

SLEEPER = _intrigue("the_sleeper_must_awaken")


def test_the_sleeper_must_awaken_is_one_plot_cost_line() -> None:
    # "Plot: 4 spice -> 1 VP" [The Sleeper Must Awaken card, Steam app text];
    # 1 copy [DI p. 3].
    entry = intrigue_card_for_instance(SLEEPER)
    assert entry.card.name == "The Sleeper Must Awaken"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert intrigue_card_text(entry) == ["Plot — Pay 4 spice → Gain 1 VP"]
    assert "the_sleeper_must_awaken" not in {
        entry.card.card_id for entry in INTRIGUE_CARDS
    }


def test_the_sleeper_must_awaken_pays_four_spice_for_one_victory_point() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is
    # played `[FAQ p. 3]`; a Plot may be played at any time in the seat's own
    # turn `[DI pp. 7-8]` (imperium-base.md 5).
    _, state = _plot_hand(SLEEPER, resources=Resources(solari=2, spice=6))
    assert legal_intrigue_play_actions(state, 0) == (_play(SLEEPER),)
    points = state.players[0].victory_points

    result = apply_intrigue_play(state, _play(SLEEPER))
    done = result.state

    assert done.players[0].resources == Resources(solari=2, spice=2)
    assert done.players[0].victory_points == points + 1
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (SLEEPER,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_paid",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["spice"] == 4
    assert dict(result.events[2].payload)["victory_points"] == 1
    assert done.decision_stack[-1].kind == "turn"


def test_the_sleeper_must_awaken_needs_four_spice() -> None:
    # Three spice do not pay the cost: the card is not offered (FAQ p. 2);
    # Solari do not stand in for spice.
    engine, state = _plot_hand(SLEEPER, resources=Resources(solari=9, spice=3))
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(SLEEPER) not in engine.whole_actions(state, 0)

    exact = _seat(state, resources=Resources(spice=4))
    assert legal_intrigue_play_actions(exact, 0) == (_play(SLEEPER),)
    done = apply_whole(engine, exact, _play(SLEEPER)).state
    assert done.players[0].resources.spice == 0


def test_the_sleeper_must_awaken_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat keeps
    # the card and the spice and takes another turn action.
    engine, state = _plot_hand(SLEEPER, resources=Resources(spice=4))
    actions = engine.whole_actions(state, 0)
    assert _play(SLEEPER) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (SLEEPER,)
    assert placed.players[0].resources.spice == 4
    assert placed.players[0].victory_points == state.players[0].victory_points


def test_the_sleeper_must_awaken_is_played_in_the_reveal_turn_too() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn (imperium-base.md
    # 5, `[DI pp. 7-8]`).
    engine, state = _plot_hand(SLEEPER, resources=Resources(spice=4))
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    assert _play(SLEEPER) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(SLEEPER)).state

    assert done.players[0].resources.spice == 0
    assert done.players[0].victory_points == state.players[0].victory_points + 1


def test_the_sleeper_must_awaken_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(SLEEPER)
    state = _seat(state, 1, intrigue_cards=(SLEEPER,), resources=Resources(spice=9))
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Water Peddlers Union (Plot) --------------------------------------------

PEDDLERS = _intrigue("water_peddlers_union")


def test_water_peddlers_union_is_one_cost_free_plot() -> None:
    # "Plot: +1 water" [Water Peddlers Union card, Steam app text]; 1 copy
    # [DI p. 3].
    entry = intrigue_card_for_instance(PEDDLERS)
    assert entry.card.name == "Water Peddlers Union"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert intrigue_card_text(entry) == ["Plot — Gain 1 water"]
    assert "water_peddlers_union" not in {
        entry.card.card_id for entry in INTRIGUE_CARDS
    }


def test_water_peddlers_union_gains_one_water() -> None:
    # A Plot Intrigue may be played at any time in the seat's own turn
    # `[DI pp. 7-8]` (imperium-base.md 5); with no arrow there is no cost.
    _, state = _plot_hand(PEDDLERS, resources=Resources(solari=1, spice=2, water=1))
    assert legal_intrigue_play_actions(state, 0) == (_play(PEDDLERS),)

    result = apply_intrigue_play(state, _play(PEDDLERS))
    done = result.state

    assert done.players[0].resources == Resources(solari=1, spice=2, water=2)
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (PEDDLERS,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["water"] == 1
    assert done.decision_stack[-1].kind == "turn"


def test_water_peddlers_union_is_played_with_nothing_in_hand_to_pay() -> None:
    # No cost and nothing to wait for: the seat may play it holding no
    # resource at all (OQ-113 (C): a cost-free effect is played).
    engine, state = _plot_hand(PEDDLERS, resources=Resources(water=0))
    assert legal_intrigue_play_actions(state, 0) == (_play(PEDDLERS),)

    done = apply_whole(engine, state, _play(PEDDLERS)).state

    assert done.players[0].resources == Resources(water=1)


def test_water_peddlers_union_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`.
    engine, state = _plot_hand(PEDDLERS)
    actions = engine.whole_actions(state, 0)
    assert _play(PEDDLERS) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (PEDDLERS,)
    assert placed.players[0].resources == state.players[0].resources


def test_water_peddlers_union_is_played_in_the_reveal_turn_too() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn (imperium-base.md
    # 5, `[DI pp. 7-8]`).
    engine, state = _plot_hand(PEDDLERS)
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _play(PEDDLERS) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(PEDDLERS)).state

    assert done.players[0].resources.water == state.players[0].resources.water + 1


def test_water_peddlers_union_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(PEDDLERS)
    state = _seat(state, 1, intrigue_cards=(PEDDLERS,))
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Windfall (Plot) --------------------------------------------------------

WINDFALL = _intrigue("windfall")


def test_windfall_is_one_cost_free_plot() -> None:
    # "Plot: +2 Solari" [Windfall card, Steam app text]; 1 copy [DI p. 3].
    entry = intrigue_card_for_instance(WINDFALL)
    assert entry.card.name == "Windfall"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert intrigue_card_text(entry) == ["Plot — Gain 2 solari"]
    assert "windfall" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_windfall_gains_two_solari() -> None:
    # A Plot Intrigue may be played at any time in the seat's own turn
    # `[DI pp. 7-8]` (imperium-base.md 5); with no arrow there is no cost.
    _, state = _plot_hand(WINDFALL, resources=Resources(solari=1, spice=2, water=1))
    assert legal_intrigue_play_actions(state, 0) == (_play(WINDFALL),)

    result = apply_intrigue_play(state, _play(WINDFALL))
    done = result.state

    assert done.players[0].resources == Resources(solari=3, spice=2, water=1)
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (WINDFALL,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["solari"] == 2
    assert done.decision_stack[-1].kind == "turn"


def test_windfall_is_played_holding_no_resource_at_all() -> None:
    # OQ-113 (C): a cost-free effect is played; nothing to pay, nothing to
    # wait for.
    engine, state = _plot_hand(WINDFALL, resources=Resources(water=0))
    assert legal_intrigue_play_actions(state, 0) == (_play(WINDFALL),)

    done = apply_whole(engine, state, _play(WINDFALL)).state

    assert done.players[0].resources == Resources(solari=2, water=0)


def test_windfall_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`.
    engine, state = _plot_hand(WINDFALL)
    actions = engine.whole_actions(state, 0)
    assert _play(WINDFALL) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (WINDFALL,)
    assert placed.players[0].resources == state.players[0].resources


def test_windfall_is_played_in_the_reveal_turn_too() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn (imperium-base.md
    # 5, `[DI pp. 7-8]`).
    engine, state = _plot_hand(WINDFALL)
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _play(WINDFALL) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(WINDFALL)).state

    assert done.players[0].resources.solari == state.players[0].resources.solari + 2


def test_windfall_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(WINDFALL)
    state = _seat(state, 1, intrigue_cards=(WINDFALL,))
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Water of Life (Plot) ---------------------------------------------------

LIFE = _intrigue("water_of_life")


def _settle(engine: UprisingRulesEngine, state: GameState, seed: int = 3) -> GameState:
    """Resolve the chance decisions (a discard-pile shuffle) waiting in ``state``."""

    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return state


def _life_hand(
    *, deck: int = 5, discard: int = 0, resources: Resources | None = None
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 with Water of Life and ``deck`` / ``discard`` of its ten starter
    cards left in those piles (the rest stay in hand)."""

    engine, state = _start()
    owner = state.players[0]
    cards = (*owner.deck, *owner.hand)
    state = _seat(
        state,
        intrigue_cards=(LIFE,),
        resources=resources or Resources(solari=1, spice=1, water=1),
        deck=cards[:deck],
        discard_pile=cards[deck : deck + discard],
        hand=cards[deck + discard :],
    )
    return engine, state


def test_water_of_life_is_one_plot_cost_line() -> None:
    # "Plot: 1 water + 1 spice -> draw 3 cards" [Water of Life card, Steam app
    # text]; 1 copy [DI p. 3]. One cost line paying both resources.
    entry = intrigue_card_for_instance(LIFE)
    assert entry.card.name == "Water of Life"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert len(entry.options[0].sections) == 1
    assert intrigue_card_text(entry) == ["Plot — Pay 1 spice, 1 water → Draw 3 cards"]
    assert "water_of_life" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_water_of_life_pays_one_water_and_one_spice_to_draw_three_cards() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is
    # played `[FAQ p. 3]`; the reward is a draw of three from the seat's own
    # deck (imperium-base.md 11, "카드 뽑기" `[DI p. 16]`).
    engine, state = _life_hand(resources=Resources(solari=4, spice=3, water=2))
    before = state.players[0]
    assert legal_intrigue_play_actions(state, 0) == (_play(LIFE),)

    result = apply_intrigue_play(state, _play(LIFE))
    done = result.state.players[0]

    assert done.resources == Resources(solari=4, spice=2, water=1)
    assert done.hand == (*before.hand, *before.deck[:3])
    assert done.deck == before.deck[3:]
    assert done.intrigue_cards == ()
    assert result.state.intrigue_discard == (LIFE,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_paid",
    ]
    payload = dict(result.events[1].payload)
    assert (payload["spice"], payload["water"]) == (1, 1)
    # The turn goes on: the Plot did not end it.
    assert result.state.decision_stack[-1].kind == "turn"
    assert apply_whole(engine, state, _play(LIFE)).state.players[0] == done


def test_water_of_life_needs_both_the_water_and_the_spice() -> None:
    # One resource does not pay a two-resource cost: with no water or no
    # spice the card is not offered (FAQ p. 2), whatever else the seat holds.
    engine, no_water = _life_hand(resources=Resources(solari=9, spice=5, water=0))
    assert legal_intrigue_play_actions(no_water, 0) == ()
    assert _play(LIFE) not in engine.whole_actions(no_water, 0)

    _, no_spice = _life_hand(resources=Resources(solari=9, spice=0, water=4))
    assert legal_intrigue_play_actions(no_spice, 0) == ()

    _, exact = _life_hand(resources=Resources(spice=1, water=1))
    assert legal_intrigue_play_actions(exact, 0) == (_play(LIFE),)
    done = apply_whole(engine, exact, _play(LIFE)).state.players[0]
    assert done.resources == Resources(spice=0, water=0)


def test_water_of_life_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat keeps
    # the card, the water and the spice and takes another turn action.
    engine, state = _life_hand()
    actions = engine.whole_actions(state, 0)
    assert _play(LIFE) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (LIFE,)
    assert placed.players[0].resources == state.players[0].resources


def test_water_of_life_draws_every_card_when_fewer_than_three_remain() -> None:
    # "draw as many as exist": with two cards in the deck and nothing in the
    # discard pile there is nothing to shuffle, and the draw takes the two.
    engine, state = _life_hand(deck=2, discard=0)
    before = state.players[0]
    assert legal_intrigue_play_actions(state, 0) == (_play(LIFE),)

    done = apply_whole(engine, state, _play(LIFE)).state.players[0]

    assert done.deck == ()
    assert done.discard_pile == ()
    assert done.hand == (*before.hand, *before.deck)
    assert done.resources == Resources(solari=1, spice=0, water=0)


def test_water_of_life_reshuffles_the_discard_pile_to_finish_the_draw() -> None:
    # With the deck too short the discard pile is shuffled to make a new deck
    # and the draw goes on (imperium-base.md 11, "카드 뽑기" `[DI p. 16]`): two
    # cards from the old deck, then one from the new one.
    engine, state = _life_hand(deck=2, discard=3)
    before = state.players[0]

    opened = apply_whole(engine, state, _play(LIFE)).state
    assert opened.decision_stack[-1].kind == "personal_draw_reshuffle"
    settled = _settle(engine, opened)

    done = settled.players[0]
    assert len(done.hand) == len(before.hand) + 3
    assert done.hand[: len(before.hand) + 2] == (*before.hand, *before.deck)
    assert len(done.deck) == 2
    assert done.discard_pile == ()
    held = before.hand + before.deck + before.discard_pile
    assert set(done.hand + done.deck) == set(held)
    assert settled.intrigue_discard == (LIFE,)


def test_water_of_life_reshuffles_a_discard_pile_when_the_deck_is_empty() -> None:
    # An empty deck is no bar while the discard pile holds cards: the shuffle
    # makes the deck and all three cards come from it.
    engine, state = _life_hand(deck=0, discard=4)
    assert legal_intrigue_play_actions(state, 0) == (_play(LIFE),)
    before = state.players[0]

    settled = _settle(engine, apply_whole(engine, state, _play(LIFE)).state)

    done = settled.players[0]
    assert len(done.hand) == len(before.hand) + 3
    assert len(done.deck) == 1
    assert done.discard_pile == ()


def test_water_of_life_is_not_played_when_deck_and_discard_are_both_empty() -> None:
    # "Water of Life는 ... 비용 줄이라 덱과 버린 더미가 모두 비면 **막는다**"
    # (imperium-base.md 13.3, OQ-113 (C): a line with a cost needs a live
    # reward, so the water and the spice are never paid for no card).
    engine, state = _life_hand(deck=0, discard=0, resources=Resources(spice=3, water=3))
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(LIFE) not in engine.whole_actions(state, 0)
    assert state.players[0].resources == Resources(spice=3, water=3)

    # One card anywhere is enough: the draw then changes something.
    _, one = _life_hand(deck=1, discard=0)
    assert legal_intrigue_play_actions(one, 0) == (_play(LIFE),)
    _, one_discarded = _life_hand(deck=0, discard=1)
    assert legal_intrigue_play_actions(one_discarded, 0) == (_play(LIFE),)


def test_water_of_life_cards_are_revealed_at_once_in_the_reveal_turn() -> None:
    # "Reveal turn에 뽑으면 바로 공개해 이번 turn에 쓴다" `[FAQ p. 3]`
    # (imperium-base.md 13.2 Poison Snooper row, 14): in the Reveal turn the
    # three drawn cards go straight into play instead of the hand.
    engine, state = _life_hand()
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    before = revealed.players[0]
    assert _play(LIFE) in engine.whole_actions(revealed, 0)

    result = apply_whole(engine, revealed, _play(LIFE))
    done = result.state.players[0]

    assert done.hand == before.hand == ()
    assert done.in_play == (*before.in_play, *before.deck[:3])
    assert done.deck == before.deck[3:]
    assert [e.kind for e in result.events].count("personal_card_late_revealed") == 3
    assert done.resources == Resources(solari=1, spice=0, water=0)


def test_water_of_life_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _life_hand()
    state = _seat(
        state, 1, intrigue_cards=(LIFE,), resources=Resources(spice=3, water=3)
    )
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Councilor's Dispensation (Plot) ----------------------------------------

DISPENSATION = _intrigue("councilors_dispensation")


def test_councilors_dispensation_is_one_conditional_plot() -> None:
    # "Plot: If you have a seat on the High Council: +2 spice" [Councilor's
    # Dispensation card, Steam app text]; 1 copy [DI p. 3].
    entry = intrigue_card_for_instance(DISPENSATION)
    assert entry.card.name == "Councilor's Dispensation"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert intrigue_card_text(entry) == [
        "Plot — If you hold a High Council seat: Gain 2 spice"
    ]
    assert "councilors_dispensation" not in {
        entry.card.card_id for entry in INTRIGUE_CARDS
    }


def test_councilors_dispensation_gains_two_spice_with_a_high_council_seat() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`: with the seat the condition holds, and a Plot may
    # be played at any time in the seat's own turn `[DI pp. 7-8]`
    # (imperium-base.md 5).
    _, state = _plot_hand(
        DISPENSATION, high_council=True, resources=Resources(solari=1, spice=1)
    )
    assert legal_intrigue_play_actions(state, 0) == (_play(DISPENSATION),)

    result = apply_intrigue_play(state, _play(DISPENSATION))
    done = result.state

    assert done.players[0].resources == Resources(solari=1, spice=3)
    assert done.players[0].high_council is True
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (DISPENSATION,)
    assert [event.kind for event in result.events] == [
        "intrigue_played",
        "resources_gained",
    ]
    assert dict(result.events[1].payload)["spice"] == 2
    assert done.decision_stack[-1].kind == "turn"


def test_councilors_dispensation_is_not_played_without_a_seat() -> None:
    # "원로회 자리가 있어야 Councilor's Dispensation을 낸다" `[FAQ p. 2]`
    # (open-questions.md OQ-071 re-ruling (6), OQ-113 (C): "공식 문서가 조건으로
    # 정한 것(원로회 자리 ...)은 그대로 조건이다", imperium-base.md 16): the
    # condition is not a cost, so a seat without it is not offered the card
    # even though a cost-free effect would otherwise be played.
    engine, state = _plot_hand(DISPENSATION, high_council=False)
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(DISPENSATION) not in engine.whole_actions(state, 0)


def test_councilors_dispensation_follows_the_seat_as_it_comes_and_goes() -> None:
    # "조건은 해결할 때 판정한다" (imperium-base.md 16, OQ-028): the check
    # reads the seat's High Council seat at the moment of playing.
    _, state = _plot_hand(DISPENSATION, high_council=False)
    assert legal_intrigue_play_actions(state, 0) == ()
    seated = _seat(state, high_council=True)
    assert legal_intrigue_play_actions(seated, 0) == (_play(DISPENSATION),)
    # Another seat's seat does not count.
    other = _seat(state, 1, high_council=True)
    assert legal_intrigue_play_actions(other, 0) == ()


def test_councilors_dispensation_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`.
    engine, state = _plot_hand(DISPENSATION, high_council=True)
    actions = engine.whole_actions(state, 0)
    assert _play(DISPENSATION) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (DISPENSATION,)
    assert placed.players[0].resources.spice == state.players[0].resources.spice


def test_councilors_dispensation_is_played_in_the_reveal_turn_too() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn (imperium-base.md
    # 5, `[DI pp. 7-8]`).
    engine, state = _plot_hand(DISPENSATION, high_council=True)
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _play(DISPENSATION) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(DISPENSATION)).state

    assert done.players[0].resources.spice == state.players[0].resources.spice + 2


def test_councilors_dispensation_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(DISPENSATION)
    state = _seat(state, 1, intrigue_cards=(DISPENSATION,), high_council=True)
    assert legal_intrigue_play_actions(state, 1) == ()


# --- Allied Armada (Combat) -------------------------------------------------

ARMADA = _intrigue("allied_armada")


def _armada_fighter(alliances: tuple[str, ...] = ("fremen",)) -> PlayerState:
    """Seat 0 with two troops fighting, Allied Armada and exactly its spice."""

    return _fighter(
        0,
        2,
        intrigue_cards=(ARMADA,),
        alliance_faction_ids=alliances,
        resources=Resources(spice=2),
    )


def test_allied_armada_is_one_conditional_combat_cost_line() -> None:
    # "Combat: If you have a Faction Alliance: 2 spice -> +7 swords" [Allied
    # Armada card, Steam app text]; 1 copy [DI p. 3].
    entry = intrigue_card_for_instance(ARMADA)
    assert entry.card.name == "Allied Armada"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat"]
    section = entry.options[0].sections[0]
    assert section.condition == HasAlliance()
    assert section.costs == (PayResources(spice=2),)
    assert intrigue_card_text(entry) == [
        "Combat — If you have an Alliance: Pay 2 spice → Gain 7 swords"
    ]
    assert "allied_armada" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_allied_armada_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 10).
    _, state = _start()
    state = _seat(
        state,
        intrigue_cards=(ARMADA,),
        alliance_faction_ids=("fremen",),
        resources=Resources(spice=5),
    )
    assert legal_intrigue_play_actions(state, 0) == ()


def test_allied_armada_pays_two_spice_for_seven_swords_with_an_alliance() -> None:
    # "Allied Armada는 Alliance와 spice 2가 있어야 낸다 ... 채택(FAQ p. 2 'pay
    # its costs'와 같다)" (imperium-base.md 13.3); the arrow cost is required
    # once the card is played `[FAQ p. 3]`; strength is troops x 2 plus
    # swords `[DI p. 11]`.
    state = _combat_state(_armada_fighter(), _fighter(1, 1))
    assert legal_intrigue_play_actions(state, 0) == (_play(ARMADA),)

    result = apply_whole(UprisingRulesEngine(), state, _play(ARMADA))
    done = result.state

    assert done.players[0].resources == Resources(spice=0)
    assert done.players[0].combat_strength == 4 + 7
    assert done.players[0].troops_conflict == 2
    assert done.players[0].alliance_faction_ids == ("fremen",)
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (ARMADA,)
    kinds = [event.kind for event in result.events]
    assert kinds.index("resources_paid") < kinds.index("combat_strength_gained")
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0


def test_allied_armada_accepts_an_alliance_with_any_faction() -> None:
    # "If you have a Faction Alliance" names no Faction: any one of the four
    # Alliance tokens satisfies it ([DI p. 16] "Alliance 조건", imperium-base.md
    # 11), and a second Alliance changes nothing.
    for held in (
        ("emperor",),
        ("spacing_guild",),
        ("bene_gesserit",),
        ("fremen", "emperor"),
    ):
        state = _combat_state(_armada_fighter(held), _fighter(1, 1))
        assert legal_intrigue_play_actions(state, 0) == (_play(ARMADA),), held
        done = apply_whole(UprisingRulesEngine(), state, _play(ARMADA)).state
        assert done.players[0].combat_strength == 4 + 7, held


def test_allied_armada_is_not_played_without_an_alliance() -> None:
    # The Alliance is a condition and the spice a cost, and the card needs
    # both (imperium-base.md 13.3): two spice alone do not play it.
    state = _combat_state(
        _fighter(
            0,
            2,
            intrigue_cards=(ARMADA,),
            resources=Resources(solari=9, spice=6),
        ),
        _fighter(1, 1),
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(ARMADA) not in engine.whole_actions(state, 0)
    # Another seat's Alliance does not count.
    elsewhere = _combat_state(
        _fighter(
            0, 2, intrigue_cards=(ARMADA,), resources=Resources(spice=6)
        ),
        _fighter(1, 1, alliance_faction_ids=("fremen",)),
    )
    assert legal_intrigue_play_actions(elsewhere, 0) == ()


def test_allied_armada_needs_two_spice_even_with_an_alliance() -> None:
    # "pay its costs" `[FAQ p. 2]` (imperium-base.md 13.3): one spice leaves
    # the cost unpaid, so the card is not offered and nothing is spent.
    state = _combat_state(
        _fighter(
            0,
            2,
            intrigue_cards=(ARMADA,),
            alliance_faction_ids=("fremen",),
            resources=Resources(solari=9, spice=1),
        ),
        _fighter(1, 1),
    )
    assert legal_intrigue_play_actions(state, 0) == ()
    assert state.players[0].resources == Resources(solari=9, spice=1)


def test_allied_armada_may_be_declined_by_passing() -> None:
    # Playing is a choice, never forced: the seat passes and keeps the card,
    # the spice and the Alliance `[DI p. 12]` (imperium-base.md 10).
    state = _combat_state(_armada_fighter(), _fighter(1, 1))
    engine = UprisingRulesEngine()
    assert _pass(0) in engine.whole_actions(state, 0)

    passed = apply_whole(engine, state, _pass(0)).state

    assert passed.players[0].intrigue_cards == (ARMADA,)
    assert passed.players[0].resources == Resources(spice=2)
    assert passed.players[0].combat_strength == 4


def test_allied_armada_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]` (imperium-base.md 10): a seat with no troop in the Conflict
    # takes no part, so it is never offered the card.
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(ARMADA,),
            troops_garrison=3,
            alliance_faction_ids=("fremen",),
            resources=Resources(spice=5),
        ),
        _fighter(1, 2),
    )
    assert legal_intrigue_play_actions(state, 0) == ()


# --- Staged Incident (Combat) -----------------------------------------------

INCIDENT = _intrigue("staged_incident")


def _lose_conflict_troop() -> DomainAction:
    return DomainAction(
        action_id="lose_intrigue_troop",
        actor=0,
        arguments=(("zone", "conflict"),),
    )


def _lose_three(
    engine: UprisingRulesEngine, state: GameState
) -> tuple[GameState, list[str]]:
    """Play Staged Incident and pay its three troops one by one."""

    played = apply_whole(engine, state, _play(INCIDENT))
    state = played.state
    kinds = [event.kind for event in played.events]
    for _ in range(3):
        assert engine.whole_actions(state, 0) == (_lose_conflict_troop(),)
        result = apply_whole(engine, state, _lose_conflict_troop())
        state = result.state
        kinds.extend(event.kind for event in result.events)
    return state, kinds


def test_staged_incident_is_one_combat_line_losing_three_troops() -> None:
    # "Combat: Lose three of your troops in the Conflict -> 1 VP" [Staged
    # Incident card, Steam app text]; 1 copy [DI p. 3].
    entry = intrigue_card_for_instance(INCIDENT)
    assert entry.card.name == "Staged Incident"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat"]
    section = entry.options[0].sections[0]
    assert section.costs == (LoseTroops(3, from_conflict=True),)
    assert intrigue_card_text(entry) == [
        "Combat — Lose 3 troops in the Conflict → Gain 1 VP"
    ]
    assert "staged_incident" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_staged_incident_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 10), never in the seat's Agent or Reveal turn.
    _, state = _start()
    state = _seat(
        state,
        intrigue_cards=(INCIDENT,),
        troops_supply=7,
        troops_garrison=0,
        troops_conflict=5,
    )
    assert legal_intrigue_play_actions(state, 0) == ()


def test_staged_incident_loses_three_conflict_troops_for_one_victory_point() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`: the three lost troops are the cost, paid in full
    # before the point is gained. A lost troop goes back to the supply
    # `[DI p. 16]` (imperium-base.md 11, "troop 잃기(supply로)").
    engine = UprisingRulesEngine()
    state = _combat_state(
        _fighter(0, 5, intrigue_cards=(INCIDENT,)), _fighter(1, 1)
    )
    points = state.players[0].victory_points
    assert legal_intrigue_play_actions(state, 0) == (_play(INCIDENT),)

    played = apply_whole(engine, state, _play(INCIDENT)).state
    # Nothing is lost or gained until the owner names the troops.
    assert played.players[0].troops_conflict == 5
    assert played.players[0].victory_points == points
    assert played.decision_stack[-1].kind == "intrigue_choice"

    done, kinds = _lose_three(engine, state)

    player = done.players[0]
    assert player.troops_conflict == 2
    assert player.troops_garrison == 0
    assert player.troops_supply == 7 + 3
    assert player.victory_points == points + 1
    assert player.intrigue_cards == ()
    assert done.intrigue_discard == (INCIDENT,)
    assert kinds.count("unit_lost") == 3
    assert kinds[-1] == "resources_gained"
    # The card was played: the passes restart and the seat stays in.
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0
    assert dict(frame.context)["participants_mask"] == 0b11


def test_staged_incident_moves_the_strength_marker_down() -> None:
    # "strength를 낮추는 조정으로 marker를 옮긴다" `[FAQ p. 4]`
    # (imperium-base.md 13.2): each lost troop takes its 2 strength off the
    # marker, and the swords already counted stay.
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(INCIDENT,),
            troops_supply=8,
            troops_garrison=0,
            troops_conflict=4,
            combat_strength=4 * 2 + 3,
        ),
        _fighter(1, 1),
    )
    done, _ = _lose_three(UprisingRulesEngine(), state)

    assert done.players[0].troops_conflict == 1
    assert done.players[0].combat_strength == 2 + 3


def test_staged_incident_needs_three_troops_in_the_conflict() -> None:
    # "pay its costs" `[FAQ p. 2]` in full: two troops in the Conflict do not
    # pay a cost of three, and troops waiting in the garrison are not "in the
    # Conflict", so the card is not offered.
    two = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(INCIDENT,),
            troops_supply=4,
            troops_garrison=6,
            troops_conflict=2,
            combat_strength=4,
        ),
        _fighter(1, 1),
    )
    engine = UprisingRulesEngine()
    assert legal_intrigue_play_actions(two, 0) == ()
    assert _play(INCIDENT) not in engine.whole_actions(two, 0)

    exact = _combat_state(
        _fighter(0, 3, intrigue_cards=(INCIDENT,)), _fighter(1, 1)
    )
    assert legal_intrigue_play_actions(exact, 0) == (_play(INCIDENT),)


def test_staged_incident_may_be_declined_by_passing() -> None:
    # Playing is a choice, never forced: the seat passes and keeps the card
    # and its troops `[DI p. 12]` (imperium-base.md 10).
    state = _combat_state(
        _fighter(0, 4, intrigue_cards=(INCIDENT,)), _fighter(1, 1)
    )
    engine = UprisingRulesEngine()
    assert _pass(0) in engine.whole_actions(state, 0)

    passed = apply_whole(engine, state, _pass(0)).state

    assert passed.players[0].intrigue_cards == (INCIDENT,)
    assert passed.players[0].troops_conflict == 4
    assert passed.players[0].combat_strength == 8
    assert passed.players[0].victory_points == state.players[0].victory_points


def test_staged_incident_losing_the_last_troops_leaves_the_rotation() -> None:
    # OQ-003 (a): a seat with no unit left in the Conflict drops out of the
    # Combat Intrigue loop at once; with nobody left the stage ends. Three
    # troops lost from three is the whole force (`[DI p. 12]`: only a seat
    # with troops in the Conflict takes part).
    engine = UprisingRulesEngine()
    state = _combat_state(_fighter(0, 3, intrigue_cards=(INCIDENT,)))
    points = state.players[0].victory_points

    state = apply_whole(engine, state, _play(INCIDENT)).state
    for _ in range(2):
        state = apply_whole(engine, state, _lose_conflict_troop()).state
    # Resolve the last slot without the dispatcher so the round does not run
    # on into the Endgame of this minimal state.
    done = apply_intrigue_choice(state, _lose_conflict_troop()).state

    assert done.players[0].troops_conflict == 0
    assert done.players[0].combat_strength == 0
    assert done.players[0].victory_points == points + 1
    assert done.intrigue_discard == (INCIDENT,)
    assert done.combat_intrigue_complete is True
    assert done.decision_stack == ()


def test_staged_incident_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]`: a seat with no troop in the Conflict takes no part.
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(INCIDENT,),
            troops_supply=6,
            troops_garrison=6,
        ),
        _fighter(1, 3),
    )
    assert legal_intrigue_play_actions(state, 0) == ()


# --- Charisma (Plot) --------------------------------------------------------

CHARISMA = _intrigue("charisma")
REVEAL = DomainAction(action_id="reveal_turn", actor=0)
FINISH_REVEAL = DomainAction(action_id="finish_reveal", actor=0)


def _reveal_persuasion(state: GameState) -> int:
    """The Persuasion the open Reveal frame of ``state`` holds."""

    frame = state.decision_stack[-1]
    assert frame.kind == "reveal"
    persuasion = dict(frame.context)["persuasion"]
    assert isinstance(persuasion, int)
    return persuasion


def test_charisma_is_one_plot_for_two_persuasion_this_round() -> None:
    # "Plot: Gain 2 Persuasion during your Reveal turn this round" [Charisma
    # card, Steam app text]; 1 copy [DI p. 3]. No arrow: a cost-free Plot.
    entry = intrigue_card_for_instance(CHARISMA)
    assert entry.card.name == "Charisma"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert intrigue_card_text(entry) == [
        "Plot — Gain 2 Persuasion during your Reveal turn this round"
    ]
    assert "charisma" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_charisma_played_in_an_agent_turn_waits_face_up_for_the_reveal_turn() -> None:
    # "If the card does something that won't apply until your next Reveal
    # turn (for example: Charisma, Recruitment Mission), keep it face up in
    # front of you until then, then use and discard it." `[FAQ p. 2]`
    # (imperium-base.md 13.2, "Charisma -> Intrigue cards"): the card is not
    # discarded when played, it pays its Persuasion when the Reveal turn
    # begins and goes to the discard pile when that turn ends.
    engine, state = _plot_hand(CHARISMA)
    assert legal_intrigue_play_actions(state, 0) == (_play(CHARISMA),)
    plain = _reveal_persuasion(engine.apply(state, REVEAL).state)

    result = apply_whole(engine, state, _play(CHARISMA))
    played = result.state

    assert played.players[0].intrigue_cards == ()
    assert played.players[0].intrigue_faceup == (CHARISMA,)
    assert CHARISMA not in played.intrigue_discard
    assert "intrigue_kept_faceup" in [event.kind for event in result.events]
    # The turn goes on: the Plot did not end it.
    assert played.decision_stack[-1].kind == "turn"

    revealed = engine.apply(played, REVEAL).state
    assert _reveal_persuasion(revealed) == plain + 2
    assert revealed.players[0].intrigue_faceup == (CHARISMA,)

    finished = engine.apply(revealed, FINISH_REVEAL)
    after = finished.state
    assert after.players[0].intrigue_faceup == ()
    assert CHARISMA in after.intrigue_discard
    expired = [e for e in finished.events if e.kind == "intrigue_expired"]
    assert [dict(e.payload)["card_id"] for e in expired] == [CHARISMA]


def test_charisma_played_in_the_reveal_turn_pays_that_reveal() -> None:
    # "Gain 2 Persuasion during your Reveal turn this round": a Plot may be
    # played at any time in the owner's Agent or Reveal turn `[DI pp. 7-8]`
    # (imperium-base.md 5), so played after the Reveal began the Persuasion
    # joins that Reveal at once, and the card is discarded as the turn ends
    # `[FAQ p. 2]`.
    engine, state = _plot_hand(CHARISMA)
    revealed = engine.apply(state, REVEAL).state
    persuasion = _reveal_persuasion(revealed)
    assert _play(CHARISMA) in engine.whole_actions(revealed, 0)

    played = apply_whole(engine, revealed, _play(CHARISMA)).state

    assert played.decision_stack[-1].kind == "reveal"
    assert _reveal_persuasion(played) == persuasion + 2
    assert played.players[0].intrigue_faceup == (CHARISMA,)
    assert CHARISMA not in played.intrigue_discard

    finished = engine.apply(played, FINISH_REVEAL).state
    assert finished.players[0].intrigue_faceup == ()
    assert CHARISMA in finished.intrigue_discard


def test_charisma_is_played_without_spending_the_persuasion() -> None:
    # "Charisma는 Persuasion을 쓰지 않아도 낸다 | 채택(Persuasion을 얻는 것이
    # 효과)" (imperium-base.md 13.3, OQ-113 (C)): the effect is the Persuasion
    # itself, so the card is offered with no purchase in sight -- here a seat
    # whose Imperium Row is empty and whose hand holds nothing to buy with.
    engine, state = _plot_hand(CHARISMA, hand=())
    state = replace(state, imperium_row=())
    assert legal_intrigue_play_actions(state, 0) == (_play(CHARISMA),)

    played = apply_whole(engine, state, _play(CHARISMA)).state

    assert played.players[0].intrigue_faceup == (CHARISMA,)
    assert played.players[0].reveal_persuasion_round_bonus == 2


def test_charisma_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat
    # keeps the card in hand and takes another turn action.
    engine, state = _plot_hand(CHARISMA)
    actions = engine.whole_actions(state, 0)
    assert _play(CHARISMA) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (CHARISMA,)
    assert placed.players[0].intrigue_faceup == ()
    assert placed.players[0].reveal_persuasion_round_bonus == 0


def test_charisma_gives_the_persuasion_to_its_owner_only() -> None:
    # "your Reveal turn": a Charisma played by seat 0 adds nothing to another
    # seat's Reveal (the bonus sits on the playing seat).
    engine, state = _plot_hand(CHARISMA)
    played = apply_whole(engine, state, _play(CHARISMA)).state
    assert [seat.reveal_persuasion_round_bonus for seat in played.players] == [
        2,
        0,
        0,
        0,
    ]


def test_charisma_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _plot_hand(CHARISMA)
    state = _seat(state, 1, intrigue_cards=(CHARISMA,))
    assert legal_intrigue_play_actions(state, 1) == ()


# --- The four Faction Plots: Favored Subject, ... ----------------------------
#
# "+1 <Faction> Influence" [app text of each card]: a cost-free Plot naming
# its Faction. Each card adds its row to this table.

# card id, printed name, Faction, the Influence field of that Faction
FACTION_PLOTS = (
    ("favored_subject", "Favored Subject", "emperor", "Emperor"),
    ("guild_authorization", "Guild Authorization", "spacing_guild", "Spacing Guild"),
    ("know_their_ways", "Know Their Ways", "fremen", "Fremen"),
    (
        "secret_of_the_sisterhood",
        "Secret of the Sisterhood",
        "bene_gesserit",
        "Bene Gesserit",
    ),
)


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_is_one_cost_free_plot_of_one_influence(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "Plot: 1 <Faction> Influence" [app text]; 1 copy [DI p. 3]. No arrow:
    # a cost-free Plot (OQ-113 (C)).
    entry = intrigue_card_for_instance(_intrigue(card_id))
    assert entry.card.name == name
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert entry.options[0].sections[0].condition is None
    assert intrigue_card_text(entry) == [f"Plot — Gain 1 {label} Influence"]
    assert card_id not in {entry.card.card_id for entry in INTRIGUE_CARDS}


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_gains_one_influence_with_its_own_faction(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서 아무 때나 낸다. `[DI pp.
    # 7-8]`" (imperium-base.md 5); the card names its Faction, so there is no
    # choice to open and the Influence is gained at once (imperium-base.md 6,
    # `[DI p. 7]`: Influence goes through the track rules).
    card = _intrigue(card_id)
    engine, state = _plot_hand(card, influence=Influence())
    assert legal_intrigue_play_actions(state, 0) == (_play(card),)

    result = apply_whole(engine, state, _play(card))
    done = result.state

    assert done.players[0].influence == Influence(**{faction: 1})
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (card,)
    assert [e.kind for e in result.events if e.kind == "intrigue_without_effect"] == []
    # No choice frame opened and the turn goes on: the Plot did not end it.
    assert done.decision_stack[-1].kind == "turn"


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_influence_goes_through_the_track_rules(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "Influence 2 도달 → 1 VP" `[DI p. 7]` (imperium-base.md 6): reaching
    # 2 scores the point, like a Faction space's Influence.
    card = _intrigue(card_id)
    engine, state = _plot_hand(card, influence=Influence(**{faction: 1}))
    before = state.players[0].victory_points

    done = apply_whole(engine, state, _play(card)).state

    assert getattr(done.players[0].influence, faction) == 2
    assert done.players[0].victory_points == before + 1


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_is_played_with_its_track_at_the_top(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "Know Their Ways는 Fremen track 맨 위에서도 낸다(불발)" (imperium-base.md
    # 13.3, OQ-113 (C): "비용이 없는 효과는 모두 불발해도 낸다"; the designer
    # ruling names Know Their Ways, its three siblings have the same shape).
    # OQ-060: the Influence on a track already at 6 is lost, so nothing moves.
    card = _intrigue(card_id)
    engine, state = _plot_hand(card, influence=Influence(**{faction: 6}))
    assert legal_intrigue_play_actions(state, 0) == (_play(card),)
    before = state.players[0]

    done = apply_whole(engine, state, _play(card)).state

    assert done.players[0].influence == before.influence
    assert done.players[0].victory_points == before.victory_points
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (card,)
    assert done.decision_stack[-1].kind == "turn"


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_may_be_declined_by_not_playing_it(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`.
    card = _intrigue(card_id)
    engine, state = _plot_hand(card)
    actions = engine.whole_actions(state, 0)
    assert _play(card) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (card,)
    assert placed.players[0].influence == state.players[0].influence


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_is_played_in_the_reveal_turn_too(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn (imperium-base.md
    # 5, `[DI pp. 7-8]`).
    card = _intrigue(card_id)
    engine, state = _plot_hand(card)
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _play(card) in engine.whole_actions(revealed, 0)

    done = apply_whole(engine, revealed, _play(card)).state

    assert getattr(done.players[0].influence, faction) == 1


@pytest.mark.parametrize(("card_id", "name", "faction", "label"), FACTION_PLOTS)
def test_a_faction_plot_is_not_offered_outside_the_seats_turn(
    card_id: str, name: str, faction: str, label: str
) -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    card = _intrigue(card_id)
    _, state = _plot_hand(card)
    state = _seat(state, 1, intrigue_cards=(card,))
    assert legal_intrigue_play_actions(state, 1) == ()


def test_know_their_ways_at_the_top_of_the_fremen_track_fizzles() -> None:
    # "Know Their Ways는 Fremen track 맨 위에서도 낸다(불발)" (imperium-base.md
    # 13.3; OQ-113 (3): "Know Their Ways(Fremen 맨 위) 낸다"): the designer
    # ruling the project adopted by (C). The other tracks are untouched.
    card = _intrigue("know_their_ways")
    engine, state = _plot_hand(
        card, influence=Influence(emperor=2, fremen=6, bene_gesserit=3)
    )

    done = apply_whole(engine, state, _play(card)).state

    assert done.players[0].influence == Influence(emperor=2, fremen=6, bene_gesserit=3)
    assert done.intrigue_discard == (card,)


# --- Rapid Mobilization (Plot) ----------------------------------------------

MOBILIZATION = _intrigue("rapid_mobilization")


def _deploy_troops(count: int) -> DomainAction:
    return DomainAction(
        action_id="deploy_intrigue_troops", actor=0, arguments=(("count", count),)
    )


def _mobilization_hand(garrison: int) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 holding Rapid Mobilization with ``garrison`` troops at home."""

    return _plot_hand(
        MOBILIZATION,
        troops_garrison=garrison,
        troops_supply=12 - garrison,
        troops_conflict=0,
    )


def test_rapid_mobilization_is_one_cost_free_plot_deploying_any_number() -> None:
    # "Plot: Deploy any number of your garrisoned troops to the Conflict"
    # [Rapid Mobilization card, Steam app text]; 1 copy [DI p. 3]. No arrow:
    # a cost-free Plot.
    entry = intrigue_card_for_instance(MOBILIZATION)
    assert entry.card.name == "Rapid Mobilization"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert entry.options[0].sections[0].costs == ()
    assert entry.options[0].sections[0].rewards == (DeployFromGarrison(up_to=None),)
    assert intrigue_card_text(entry) == [
        "Plot — Deploy any number of troops from your garrison to the Conflict"
    ]
    assert "rapid_mobilization" not in {
        entry.card.card_id for entry in INTRIGUE_CARDS
    }


def test_rapid_mobilization_deploys_the_whole_garrison_past_two_troops() -> None:
    # "any number of your garrisoned troops": the choice runs from none up to
    # every troop at home, with no two-troop limit (the limit is the Agent
    # turn's `[DI p. 10]`, the card is its own effect). A Plot is played at
    # any time in the seat's own turn `[DI pp. 7-8]` (imperium-base.md 5).
    engine, state = _mobilization_hand(5)
    assert legal_intrigue_play_actions(state, 0) == (_play(MOBILIZATION),)

    opened = apply_whole(engine, state, _play(MOBILIZATION)).state
    # Nothing moves until the owner names the number; the card waits in hand.
    assert opened.players[0].troops_garrison == 5
    assert opened.players[0].intrigue_cards == (MOBILIZATION,)
    assert engine.whole_actions(opened, 0) == tuple(_deploy_troops(n) for n in range(6))
    assert engine.whole_actions(opened, 1) == ()

    done = apply_whole(engine, opened, _deploy_troops(5)).state

    player = done.players[0]
    assert player.troops_garrison == 0
    assert player.troops_conflict == 5
    assert player.troops_supply == 7
    assert player.intrigue_cards == ()
    assert done.intrigue_discard == (MOBILIZATION,)
    # The turn goes on: the Plot did not end it.
    assert done.decision_stack[-1].kind == "turn"


def test_rapid_mobilization_may_deploy_only_some_of_the_garrison() -> None:
    # "any number" includes a part of the garrison; the rest stays home.
    engine, state = _mobilization_hand(4)
    opened = apply_whole(engine, state, _play(MOBILIZATION)).state

    done = apply_whole(engine, opened, _deploy_troops(3)).state

    assert done.players[0].troops_garrison == 1
    assert done.players[0].troops_conflict == 3


def test_rapid_mobilization_may_deploy_zero_troops() -> None:
    # "'any number'는 0 가능" `[FAQ p. 3]` (imperium-base.md 13.2, the
    # Retreat row the FAQ points Rapid Mobilization at; 13.3: "Rapid
    # Mobilization은 0개를 배치하며 낼 수 있다"): zero is a number, the card is
    # still played and discarded.
    engine, state = _mobilization_hand(3)
    opened = apply_whole(engine, state, _play(MOBILIZATION)).state

    done = apply_whole(engine, opened, _deploy_troops(0)).state

    assert done.players[0].troops_garrison == 3
    assert done.players[0].troops_conflict == 0
    assert done.intrigue_discard == (MOBILIZATION,)
    assert done.decision_stack[-1].kind == "turn"


def test_rapid_mobilization_is_played_with_an_empty_garrison() -> None:
    # "garrison에 troop이 없어도 낸다(0개 배치; OQ-113 (2) 1)" (imperium-base.md
    # 13.3, OQ-113 (C): "비용이 없는 효과는 모두 불발해도 낸다"): the card is
    # offered, only the zero deployment is, and the play is logged as a play
    # that changes nothing.
    engine, state = _mobilization_hand(0)
    assert legal_intrigue_play_actions(state, 0) == (_play(MOBILIZATION),)

    played = apply_whole(engine, state, _play(MOBILIZATION))
    assert engine.whole_actions(played.state, 0) == (_deploy_troops(0),)
    assert "intrigue_without_effect" in [e.kind for e in played.events]

    done = apply_whole(engine, played.state, _deploy_troops(0)).state
    assert done.players[0].troops_conflict == 0
    assert done.intrigue_discard == (MOBILIZATION,)


def test_rapid_mobilization_counts_as_a_deployment_this_turn() -> None:
    # "When you deploy 4+ troops to the Conflict in a turn" (Baron's
    # Masterstroke, OQ-115: "그 turn에 배치한 troop"): troops deployed by an
    # Intrigue are deployed this turn like Detonation's, so the seat's
    # count of the turn's deployments rises with them.
    engine, state = _mobilization_hand(4)
    opened = apply_whole(engine, state, _play(MOBILIZATION)).state

    done = apply_whole(engine, opened, _deploy_troops(4)).state

    assert done.players[0].units_deployed_turn == 4
    assert done.players[0].units_deployed_peak == 4


def test_rapid_mobilization_in_the_reveal_turn_adds_troop_strength() -> None:
    # "troop 2" strength `[DI p. 11]` (imperium-base.md 10): a Plot played in
    # the Reveal turn puts its troops into the Conflict before the strength
    # is set, so each adds 2.
    engine, state = _mobilization_hand(3)
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert _play(MOBILIZATION) in engine.whole_actions(revealed, 0)
    swords = dict(revealed.decision_stack[-1].context)["sword_strength"]
    assert isinstance(swords, int)
    opened = apply_whole(engine, revealed, _play(MOBILIZATION)).state

    done = apply_whole(engine, opened, _deploy_troops(3)).state

    assert done.players[0].troops_conflict == 3
    assert done.players[0].combat_strength == 2 * 3 + swords


def test_rapid_mobilization_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`.
    engine, state = _mobilization_hand(3)
    actions = engine.whole_actions(state, 0)
    assert _play(MOBILIZATION) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (MOBILIZATION,)
    assert placed.players[0].troops_garrison == 3


def test_rapid_mobilization_is_not_a_combat_card_nor_offered_off_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _mobilization_hand(3)
    other = _seat(state, 1, intrigue_cards=(MOBILIZATION,), troops_garrison=3)
    assert legal_intrigue_play_actions(other, 1) == ()

    fighting = _combat_state(
        _fighter(0, 2, intrigue_cards=(MOBILIZATION,)), _fighter(1, 1)
    )
    assert legal_intrigue_play_actions(fighting, 0) == ()
