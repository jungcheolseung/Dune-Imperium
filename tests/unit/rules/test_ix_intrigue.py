"""Rise of Ix's Intrigue cards (stage P4d), one group per transcribed card.

Rules: docs/rules/imperium-base.md 5 (Plot timing), 6 (Influence), 10
(Combat Intrigue), 11 (the cost arrow, Trash) and 16 (a cost line needs a live
reward, OQ-071, OQ-113 (C)); docs/rules/rise-of-ix.md 2 (the 17 cards are
shuffled into the Intrigue deck) and 9 (the Ix card rulings, Cull's row).
The card text is the Steam app's (its log strings and screen pieces; the
cards print icons only). Seat 0 holds the card in an original game with Rise
of Ix: ``RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)``.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
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
)
from dune_imperium.display import intrigue_card_text
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.intrigue import legal_intrigue_play_actions

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)


def _start(seed: int = 3) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of the original game with Rise of Ix at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(IX, seed)
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


def _pass(actor: int) -> DomainAction:
    return DomainAction(action_id="pass_combat_intrigue", actor=actor)


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
    """The Combat Intrigue loop of an original game with Rise of Ix, seat 0
    first."""

    seats = list(players)
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    content = content_for(IX)
    state = GameState(
        config=IX,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        current_conflict_ids=(content.conflicts[0].card.card_id,),
        maker_bonus_spice=tuple((space, 0) for space in content.maker_space_ids),
        players=tuple(seats),
    )
    return begin_combat_intrigue(state).state


def _in_deck(card_id: str, config: RulesetConfig) -> bool:
    return any(
        instance.startswith(f"intrigue:{card_id}:")
        for instance in content_for(config).intrigue_deck_instance_ids
    )


# --- Blackmail (Combat) -----------------------------------------------------

BLACKMAIL = _intrigue("blackmail")


def _blackmail_state(influence: Influence | None = None, **extra: object) -> GameState:
    return _combat_state(
        _fighter(
            0,
            2,
            intrigue_cards=(BLACKMAIL,),
            influence=influence or Influence(emperor=2, fremen=1),
            **extra,
        ),
        _fighter(1, 1),
    )


def test_blackmail_is_one_combat_cost_line_shuffled_in_with_rise_of_ix() -> None:
    # "Choose a Faction to lose 1 Influence with." (Blackmail's ability) and
    # "[leader] played Blackmail and lost 1 Influence with the [faction] to
    # gain 5 swords" (its log line) [Blackmail card, Steam app text]: Combat,
    # lose 1 Influence -> 5 swords; 1 copy [Rise of Ix p. 2]. The Ix cards are
    # "shuffled into the Intrigue Deck" with Rise of Ix only.
    entry = intrigue_card_for_instance(BLACKMAIL)
    assert entry.card.name == "Blackmail"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["combat"]
    assert intrigue_card_text(entry) == ["Combat — Lose 1 Influence → Gain 5 swords"]
    assert _in_deck("blackmail", IX)
    assert not _in_deck("blackmail", ORIGINAL)
    # Uprising's own card list is untouched.
    assert "blackmail" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_blackmail_is_not_a_plot() -> None:
    # Combat Intrigue is played in the Combat phase only [DI p. 12]
    # (imperium-base.md 10).
    _, state = _start()
    state = _seat(state, intrigue_cards=(BLACKMAIL,), influence=Influence(emperor=2))
    assert legal_intrigue_play_actions(state, 0) == ()


def test_blackmail_loses_influence_with_the_chosen_faction_for_five_swords() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is played
    # `[FAQ p. 3]`; strength is troops x 2 plus swords `[DI p. 11]`. Losing
    # Influence is a Faction the player chooses (imperium-base.md 11, "Influence
    # 얻기(하나·둘·잃기)" `[DI p. 16]`), among those where the seat has some.
    engine = UprisingRulesEngine()
    state = _blackmail_state()
    assert legal_intrigue_play_actions(state, 0) == (_play(BLACKMAIL),)

    opened = apply_whole(engine, state, _play(BLACKMAIL)).state
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert engine.whole_actions(opened, 0) == (
        _choose_faction("emperor"),
        _choose_faction("fremen"),
    )
    # The card stays in hand while its choice resolves; nothing is paid yet.
    assert opened.players[0].intrigue_cards == (BLACKMAIL,)
    assert opened.players[0].influence == Influence(emperor=2, fremen=1)

    result = apply_whole(engine, opened, _choose_faction("fremen"))
    done = result.state
    assert done.players[0].influence == Influence(emperor=2, fremen=0)
    assert done.players[0].combat_strength == 4 + 5
    assert done.players[0].troops_conflict == 2
    assert done.players[0].intrigue_cards == ()
    assert done.intrigue_discard == (BLACKMAIL,)
    kinds = [event.kind for event in result.events]
    assert kinds.index("influence_lost") < kinds.index("combat_strength_gained")
    frame = done.decision_stack[-1]
    assert frame.kind == "combat_intrigue"
    assert dict(frame.context)["consecutive_passes"] == 0


def test_blackmail_influence_loss_goes_through_the_track_rules() -> None:
    # "Influence 2 도달 → 1 VP(내려가면 잃음)" `[DI p. 7]` (imperium-base.md 6):
    # the loss from 2 to 1 takes the Victory Point back.
    engine = UprisingRulesEngine()
    state = _blackmail_state(influence=Influence(emperor=2), victory_points=3)
    opened = apply_whole(engine, state, _play(BLACKMAIL)).state
    done = apply_whole(engine, opened, _choose_faction("emperor")).state

    assert done.players[0].influence.emperor == 1
    assert done.players[0].victory_points == 2
    assert done.players[0].combat_strength == 4 + 5


def test_blackmail_names_only_factions_where_the_seat_has_influence() -> None:
    # One Faction with Influence: it is the only choice, still named.
    engine = UprisingRulesEngine()
    state = _blackmail_state(influence=Influence(bene_gesserit=3))
    opened = apply_whole(engine, state, _play(BLACKMAIL)).state
    assert engine.whole_actions(opened, 0) == (_choose_faction("bene_gesserit"),)

    done = apply_whole(engine, opened, _choose_faction("bene_gesserit")).state
    assert done.players[0].influence == Influence(bene_gesserit=2)


def test_blackmail_needs_influence_to_lose() -> None:
    # A seat with no Influence on any track cannot pay the cost, so the card
    # is not offered and nothing is paid (FAQ p. 2).
    engine = UprisingRulesEngine()
    state = _blackmail_state(influence=Influence())
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(BLACKMAIL) not in engine.whole_actions(state, 0)


def test_blackmail_may_be_declined_by_passing() -> None:
    # Playing is a choice, never forced: the seat passes and keeps the card
    # and its Influence `[DI p. 12]` (imperium-base.md 10).
    engine = UprisingRulesEngine()
    state = _blackmail_state()
    assert _pass(0) in engine.whole_actions(state, 0)

    passed = apply_whole(engine, state, _pass(0)).state

    assert passed.players[0].intrigue_cards == (BLACKMAIL,)
    assert passed.players[0].influence == Influence(emperor=2, fremen=1)
    assert passed.players[0].combat_strength == 4


def test_blackmail_needs_a_unit_in_the_conflict() -> None:
    # "Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다"
    # `[DI p. 12]` (imperium-base.md 10): a seat with no troop in the Conflict
    # is never offered the card, whatever it can pay.
    state = _combat_state(
        PlayerState(
            player_id=0,
            intrigue_cards=(BLACKMAIL,),
            troops_garrison=3,
            influence=Influence(emperor=4),
        ),
        _fighter(1, 2),
    )
    assert legal_intrigue_play_actions(state, 0) == ()


def test_blackmail_rows_round_trip_through_the_codec() -> None:
    # The Ix catalog lists the rows the card prints (its automatic reward
    # step, naming Blackmail as the card that prints it) and the codec
    # round-trips what the seat is offered; the original game's catalog
    # without Rise of Ix has none.
    engine = UprisingRulesEngine()
    codec = ActionCodec(IX)
    state = _blackmail_state()
    opened = apply_whole(engine, state, _play(BLACKMAIL)).state
    for held in (state, opened):
        offered = engine.legal_actions(held, 0)
        assert offered
        for action in offered:
            assert codec.decode(codec.encode(action), 0) == action

    def rows(config: RulesetConfig) -> set[str]:
        return {
            template.action_id
            for template in ActionCodec(config).catalog
            if dict(template.arguments).get("printed") == "blackmail"
        }

    assert rows(IX) == {"resolve"}
    assert not rows(ORIGINAL)
