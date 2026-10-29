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
    Resources,
)
from dune_imperium.display import intrigue_card_text
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.intrigue import (
    apply_intrigue_play,
    legal_intrigue_play_actions,
)

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


def _seat(state: GameState, seat: int = 0, /, **changes: object) -> GameState:
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


# --- Cull (Plot) ------------------------------------------------------------

CULL = _intrigue("cull")
DIPLOMACY = "player:0:starter:diplomacy:0"
DAGGER = "player:0:starter:dagger:0"
SEEK_ALLIES = "player:0:starter:seek_allies:0"


def _trash(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="trash_intrigue_card",
        actor=0,
        arguments=(("card_id", card_id),),
    )


DECLINE_TRASH = DomainAction(action_id="decline_intrigue_trash", actor=0)


def _cull_hand(
    solari: int = 2,
    hand: tuple[str, ...] | None = None,
    discard_pile: tuple[str, ...] = (),
    in_play: tuple[str, ...] = (),
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 holding Cull and ``solari`` Solari; ``hand`` (the seat's own when
    ``None``), ``discard_pile`` and ``in_play`` replace the seat's own."""

    engine, state = _start()
    piles: dict[str, object] = {"discard_pile": discard_pile, "in_play": in_play}
    if hand is not None:
        piles["hand"] = hand
    # A card sits in one zone only: take the named ones out of the deck, whose
    # shuffle depends on how many Ix cards the Imperium deck holds.
    named = {*discard_pile, *in_play, *(hand or ())}
    piles["deck"] = tuple(c for c in state.players[0].deck if c not in named)
    return engine, _seat(
        state, intrigue_cards=(CULL,), resources=Resources(solari=solari), **piles
    )


def test_cull_is_one_plot_cost_line_shuffled_in_with_rise_of_ix() -> None:
    # "Played Cull and spent 1 Solari to trash [card]" [Cull card, Steam app
    # log text; the card prints icons only]: Plot, 1 Solari -> Trash; 1 copy
    # [Rise of Ix p. 2]. Shuffled in with Rise of Ix only.
    entry = intrigue_card_for_instance(CULL)
    assert entry.card.name == "Cull"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert len(entry.options[0].sections) == 1
    assert intrigue_card_text(entry) == ["Plot — Pay 1 solari → Trash a card"]
    assert _in_deck("cull", IX)
    assert not _in_deck("cull", ORIGINAL)
    assert "cull" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_cull_pays_one_solari_then_trashes_the_chosen_card() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is played
    # `[FAQ p. 3]`. The reward is the Trash icon: a card from the hand, the
    # discard pile or play `[DI p. 16]` (imperium-base.md 11).
    engine, state = _cull_hand(
        solari=3,
        hand=(DIPLOMACY, DAGGER),
        discard_pile=(SEEK_ALLIES,),
        in_play=(),
    )
    assert legal_intrigue_play_actions(state, 0) == (_play(CULL),)

    result = apply_whole(engine, state, _play(CULL))
    opened = result.state
    # The Solari is paid on playing; nobody else acts meanwhile.
    assert opened.players[0].resources.solari == 2
    assert opened.decision_stack[-1].kind == "intrigue_choice"
    assert engine.whole_actions(opened, 1) == ()
    assert opened.players[0].intrigue_cards == (CULL,)

    done = apply_whole(engine, opened, _trash(DAGGER))
    player = done.state.players[0]
    assert player.hand == (DIPLOMACY,)
    assert player.discard_pile == (SEEK_ALLIES,)
    assert DAGGER in player.trashed
    assert player.intrigue_cards == ()
    assert done.state.intrigue_discard == (CULL,)
    assert [e.kind for e in done.events] == ["card_trashed"]
    # The turn goes on: the Plot did not end it.
    assert done.state.decision_stack[-1].kind == "turn"
    kinds = [event.kind for event in result.events]
    assert "resources_paid" in kinds


def test_cull_trashes_from_the_hand_the_discard_pile_or_play() -> None:
    # The Trash icon takes a card "from your hand, discard pile or in play"
    # `[DI p. 16]` (imperium-base.md 11).
    engine, state = _cull_hand(
        hand=(DIPLOMACY,), discard_pile=(SEEK_ALLIES,), in_play=(DAGGER,)
    )
    opened = apply_whole(engine, state, _play(CULL)).state
    offered = engine.whole_actions(opened, 0)
    assert set(offered) == {
        DECLINE_TRASH,
        _trash(DIPLOMACY),
        _trash(SEEK_ALLIES),
        _trash(DAGGER),
    }

    done = apply_whole(engine, opened, _trash(SEEK_ALLIES)).state.players[0]
    assert done.discard_pile == ()
    assert done.hand == (DIPLOMACY,)
    assert done.in_play == (DAGGER,)
    assert SEEK_ALLIES in done.trashed


def test_cull_trash_is_optional_once_the_solari_is_paid() -> None:
    # The Trash definition "비용이거나 카드가 자기를 trash하라고 할 때만 의무"
    # (imperium-base.md 11, `[DI p. 16]`): a Trash icon that is a reward is not
    # forced, so the seat may decline it. The Solari stays spent (the arrow
    # cost is required once the card is played, `[FAQ p. 3]`).
    engine, state = _cull_hand(hand=(DIPLOMACY,))
    opened = apply_whole(engine, state, _play(CULL)).state
    assert DECLINE_TRASH in engine.whole_actions(opened, 0)

    done = apply_whole(engine, opened, DECLINE_TRASH).state.players[0]
    assert done.hand == (DIPLOMACY,)
    assert done.trashed == ()
    assert done.resources.solari == 1


def test_cull_is_not_played_when_nothing_can_be_trashed() -> None:
    # "Cull은 trash해야 낸다" (rise-of-ix.md 9, the "Message from designer"
    # row, adopted; OQ-113 (C): a cost line needs a live reward, so the
    # Solari is never paid for no trash). With the hand, the discard pile and
    # play all empty there is nothing to trash.
    engine, state = _cull_hand(solari=5, hand=(), discard_pile=(), in_play=())
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(CULL) not in engine.whole_actions(state, 0)
    assert state.players[0].resources.solari == 5

    # One card in any of the three places is enough.
    for hand, discard, in_play in (
        ((DIPLOMACY,), (), ()),
        ((), (DIPLOMACY,), ()),
        ((), (), (DIPLOMACY,)),
    ):
        _, held = _cull_hand(hand=hand, discard_pile=discard, in_play=in_play)
        assert legal_intrigue_play_actions(held, 0) == (_play(CULL),)


def test_cull_needs_one_solari() -> None:
    # The cost is not met without the Solari (FAQ p. 2), whatever else the
    # seat holds.
    engine, state = _cull_hand(solari=0)
    state = _seat(state, resources=Resources(solari=0, spice=5, water=5))
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(CULL) not in engine.whole_actions(state, 0)

    _, exact = _cull_hand(solari=1)
    assert legal_intrigue_play_actions(exact, 0) == (_play(CULL),)


def test_cull_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat keeps
    # the card and the Solari and takes another turn action.
    engine, state = _cull_hand()
    actions = engine.whole_actions(state, 0)
    assert _play(CULL) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (CULL,)
    assert placed.players[0].resources.solari == 2


def test_cull_is_also_played_during_the_reveal_turn() -> None:
    # "아무 때나" within the seat's own Agent or Reveal turn
    # (imperium-base.md 5, `[DI pp. 7-8]`); the revealed cards are in play.
    engine, state = _cull_hand()
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    in_play = revealed.players[0].in_play
    assert in_play
    assert _play(CULL) in engine.whole_actions(revealed, 0)

    opened = apply_whole(engine, revealed, _play(CULL)).state
    assert {_trash(card) for card in in_play} <= set(engine.whole_actions(opened, 0))
    done = apply_whole(engine, opened, _trash(in_play[0])).state.players[0]
    assert in_play[0] in done.trashed
    assert done.resources.solari == 1


def test_cull_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _cull_hand()
    state = _seat(state, 1, intrigue_cards=(CULL,), resources=Resources(solari=2))
    assert legal_intrigue_play_actions(state, 1) == ()


def test_cull_rows_round_trip_through_the_codec() -> None:
    # The Ix catalog lists the decline of the card's Trash (naming Cull as the
    # card that prints it) and the codec round-trips what the seat is offered;
    # the original game's catalog without Rise of Ix has none.
    engine, state = _cull_hand(hand=(DIPLOMACY,), discard_pile=(SEEK_ALLIES,))
    codec = ActionCodec(IX)
    opened = apply_whole(engine, state, _play(CULL)).state
    for held in (state, opened):
        offered = engine.legal_actions(held, 0)
        assert offered
        for action in offered:
            assert codec.decode(codec.encode(action), 0) == action

    def rows(config: RulesetConfig) -> set[str]:
        return {
            template.action_id
            for template in ActionCodec(config).catalog
            if dict(template.arguments).get("printed") == "cull"
        }

    assert rows(IX) == {"decline"}
    assert not rows(ORIGINAL)


# --- Glimpse the Path (Plot) ------------------------------------------------

GLIMPSE = _intrigue("glimpse_the_path")


def _settle(engine: UprisingRulesEngine, state: GameState, seed: int = 3) -> GameState:
    """Resolve the chance decisions (a discard-pile shuffle) waiting in ``state``."""

    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    return state


def _glimpse_hand(
    *, deck: int = 5, discard: int = 0, spice: int = 2
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 with Glimpse the Path, ``spice`` spice and no water, and ``deck``
    / ``discard`` of its ten starter cards left in those piles (the rest stay
    in hand)."""

    engine, state = _start()
    owner = state.players[0]
    cards = (*owner.deck, *owner.hand)
    state = _seat(
        state,
        intrigue_cards=(GLIMPSE,),
        resources=Resources(solari=3, spice=spice, water=0),
        deck=cards[:deck],
        discard_pile=cards[deck : deck + discard],
        hand=cards[deck + discard :],
    )
    return engine, state


def test_glimpse_the_path_is_one_plot_cost_line_shuffled_in_with_rise_of_ix() -> None:
    # "Played Glimpse the Path and spent 1 spice to gain 1 water and draw a
    # card" [Glimpse the Path card, Steam app log text; the card prints icons
    # only]: Plot, 1 spice -> 1 water and a card; 1 copy [Rise of Ix p. 2].
    # Shuffled in with Rise of Ix only.
    entry = intrigue_card_for_instance(GLIMPSE)
    assert entry.card.name == "Glimpse the Path"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot"]
    assert len(entry.options[0].sections) == 1
    assert intrigue_card_text(entry) == [
        "Plot — Pay 1 spice → Gain 1 water, Draw 1 card"
    ]
    assert _in_deck("glimpse_the_path", IX)
    assert not _in_deck("glimpse_the_path", ORIGINAL)
    assert "glimpse_the_path" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_glimpse_the_path_pays_one_spice_for_one_water_and_one_card() -> None:
    # "To play an Intrigue card, you must meet its conditions and pay its
    # costs." `[FAQ p. 2]`; the arrow cost is required once the card is played
    # `[FAQ p. 3]`; the draw comes from the seat's own deck (imperium-base.md
    # 11, "카드 뽑기" `[DI p. 16]`).
    engine, state = _glimpse_hand(deck=5)
    before = state.players[0]
    assert legal_intrigue_play_actions(state, 0) == (_play(GLIMPSE),)

    result = apply_intrigue_play(state, _play(GLIMPSE))
    done = result.state.players[0]

    assert done.resources == Resources(solari=3, spice=1, water=1)
    assert done.hand == (*before.hand, before.deck[0])
    assert done.deck == before.deck[1:]
    assert done.intrigue_cards == ()
    assert result.state.intrigue_discard == (GLIMPSE,)
    kinds = [event.kind for event in result.events]
    assert kinds.index("resources_paid") < kinds.index("resources_gained")
    payload = dict(result.events[kinds.index("resources_paid")].payload)
    assert payload["spice"] == 1
    # The turn goes on: the Plot did not end it.
    assert result.state.decision_stack[-1].kind == "turn"
    assert apply_whole(engine, state, _play(GLIMPSE)).state.players[0] == done


def test_glimpse_the_path_needs_one_spice() -> None:
    # Without the spice the cost is not met (FAQ p. 2), whatever else the seat
    # holds.
    engine, state = _glimpse_hand(spice=0)
    state = _seat(state, resources=Resources(solari=9, spice=0, water=4))
    assert legal_intrigue_play_actions(state, 0) == ()
    assert _play(GLIMPSE) not in engine.whole_actions(state, 0)

    _, exact = _glimpse_hand(spice=1)
    assert legal_intrigue_play_actions(exact, 0) == (_play(GLIMPSE),)
    done = apply_whole(engine, exact, _play(GLIMPSE)).state.players[0]
    assert done.resources == Resources(solari=3, spice=0, water=1)


def test_glimpse_the_path_reshuffles_the_discard_pile_to_draw() -> None:
    # With the deck empty the discard pile is shuffled to make a new deck and
    # the draw goes on (imperium-base.md 11, "카드 뽑기" `[DI p. 16]`).
    engine, state = _glimpse_hand(deck=0, discard=3)
    before = state.players[0]

    opened = apply_whole(engine, state, _play(GLIMPSE)).state
    assert opened.decision_stack[-1].kind == "personal_draw_reshuffle"
    done = _settle(engine, opened).players[0]

    assert len(done.hand) == len(before.hand) + 1
    assert len(done.deck) == 2
    assert done.discard_pile == ()
    assert set(done.hand + done.deck) == set(before.hand + before.discard_pile)
    assert done.resources == Resources(solari=3, spice=1, water=1)


def test_glimpse_the_path_is_played_for_its_water_with_no_card_to_draw() -> None:
    # "보상 중 하나라도 지금 무언가를 바꿀 수 있어야 낸다" (imperium-base.md
    # 16, OQ-071, OQ-113 (C)): the water always changes something, so the
    # line is played even when the deck and the discard pile are both empty;
    # the draw then takes nothing (unlike Water of Life, whose only reward is
    # the draw).
    engine, state = _glimpse_hand(deck=0, discard=0)
    before = state.players[0]
    assert legal_intrigue_play_actions(state, 0) == (_play(GLIMPSE),)

    done = apply_whole(engine, state, _play(GLIMPSE)).state.players[0]

    assert done.hand == before.hand
    assert done.deck == () and done.discard_pile == ()
    assert done.resources == Resources(solari=3, spice=1, water=1)


def test_glimpse_the_path_may_be_declined_by_not_playing_it() -> None:
    # A Plot Intrigue is a choice, never forced `[DI pp. 7-8]`: the seat keeps
    # the card and the spice and takes another turn action.
    engine, state = _glimpse_hand()
    actions = engine.whole_actions(state, 0)
    assert _play(GLIMPSE) in actions
    others = [action for action in actions if action.action_id != "play_intrigue"]
    assert others

    placed = apply_whole(engine, state, others[0]).state

    assert placed.players[0].intrigue_cards == (GLIMPSE,)
    assert placed.players[0].resources == state.players[0].resources


def test_glimpse_the_path_card_is_revealed_at_once_in_the_reveal_turn() -> None:
    # "Reveal turn에 뽑으면 바로 공개해 이번 turn에 쓴다" `[FAQ p. 3]`
    # (imperium-base.md 13.2 Poison Snooper row, 14): in the Reveal turn the
    # drawn card goes straight into play instead of the hand.
    engine, state = _glimpse_hand()
    revealed = apply_whole(
        engine, state, DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == "reveal"
    before = revealed.players[0]
    assert _play(GLIMPSE) in engine.whole_actions(revealed, 0)

    result = apply_whole(engine, revealed, _play(GLIMPSE))
    done = result.state.players[0]

    assert done.hand == before.hand == ()
    assert done.in_play == (*before.in_play, before.deck[0])
    assert done.deck == before.deck[1:]
    assert [e.kind for e in result.events].count("personal_card_late_revealed") == 1
    assert done.resources == Resources(solari=3, spice=1, water=1)


def test_glimpse_the_path_is_not_offered_outside_the_seats_turn() -> None:
    # "Plot Intrigue는 자기 Agent·Reveal turn 안에서" (imperium-base.md 5).
    _, state = _glimpse_hand()
    state = _seat(state, 1, intrigue_cards=(GLIMPSE,), resources=Resources(spice=3))
    assert legal_intrigue_play_actions(state, 1) == ()


def test_glimpse_the_path_rows_round_trip_through_the_codec() -> None:
    # The Ix catalog lists the card (a ``choose_intrigue_card`` row naming
    # it, as every Intrigue card of the deck has) and the codec round-trips
    # what the seat is offered before and after the play; the original
    # game's catalog without Rise of Ix has none.
    engine, state = _glimpse_hand(deck=0, discard=3)
    codec = ActionCodec(IX)
    played = _settle(engine, apply_whole(engine, state, _play(GLIMPSE)).state)
    for held in (state, played):
        offered = engine.legal_actions(held, 0)
        assert offered
        for action in offered:
            assert codec.decode(codec.encode(action), 0) == action

    def rows(config: RulesetConfig) -> set[str]:
        return {
            template.action_id
            for template in ActionCodec(config).catalog
            if dict(template.arguments).get("card_id") == GLIMPSE
        }

    assert rows(IX) == {"choose_intrigue_card"}
    assert not rows(ORIGINAL)
