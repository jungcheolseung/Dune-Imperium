"""The original Dune: Imperium's Intrigue cards (stage P3).

docs/rules/imperium-base.md 5 (Plot timing), 8 (Combat), 11 (the cost arrow,
Retreat), 13.2 (the FAQ rows) and 16 (cost lines need a live reward) with
docs/rules/open-questions.md OQ-003, OQ-058, OQ-060, OQ-071 and OQ-113; the
card text is the Steam app's (docs/base-game-and-ix-plan.md 16.3). Seat 0
holds the card, in an original-game ``RulesetConfig``.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.rulesets import content_for
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


def _plot_hand(card: str, **changes: object) -> tuple[UprisingRulesEngine, GameState]:
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
