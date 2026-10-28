"""Bypass Protocol and Recruitment Mission, the original game's acquiring Plots
(stage P3).

docs/rules/imperium-base.md 13.2 (Recruitment Mission: the whole card applies
only to the owner's Reveal turn this round, and "for each card acquired the
owner chooses top of deck or discard pile" [FAQ p. 3]), 13.3 (the card is not
retroactive; a cost-free effect is played even when it fizzles, OQ-113 (C)),
14 (a card put on top of the deck is as hidden as any deck card) and 16 (the
-OR- cards) with docs/rules/open-questions.md OQ-016 (a Plot whose effect
waits for the Reveal turn stays face up until that turn ends [FAQ p. 2]),
OQ-058, OQ-071 and OQ-125 (a cost cap reaches the Imperium Row's five cards
and the Reserve's Arrakis Liaison and The Spice Must Flow, never Foldspace
[DI p. 11] [FAQ p. 2]). The card text is the Steam app's
(docs/base-game-and-ix-plan.md 16.3). Seat 0 holds the card, in an
original-game ``RulesetConfig``.
"""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireToDeckTopThisRound,
    PayResources,
    RevealPersuasionThisRound,
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
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.core.observation import known_card_seats
from dune_imperium.display import intrigue_card_text
from dune_imperium.display.effect_dsl_text_ko import intrigue_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.acquisition import (
    apply_reveal_command_acquisition,
    legal_imperium_acquisitions,
    legal_reveal_command_acquisition_actions,
)
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.intrigue import legal_intrigue_play_actions
from dune_imperium.rules.reveal_turn import begin_reveal_turn
from dune_imperium.rules.tleilaxu_row import (
    apply_tleilaxu_acquisition,
    legal_tleilaxu_acquisitions,
)

CONFIG = RulesetConfig(base_game=BaseGame.IMPERIUM, first_player_seat_zero=True)
IMMORTALITY_UPRISING = RulesetConfig(immortality=True)
BLOODLINES_UPRISING = RulesetConfig(bloodlines=True)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)

BYPASS = "intrigue:bypass_protocol:0"
MISSION = "intrigue:recruitment_mission:0"
REVEAL = DomainAction(action_id="reveal_turn", actor=0)
FINISH_REVEAL = DomainAction(action_id="finish_reveal", actor=0)

# The original Imperium Row cards used here, with their printed cost.
MISSIONARIA = "imperium:missionaria_protectiva:0"  # 1
INFANTRY = "imperium:sardaukar_infantry:1"  # 1
SISTER = "imperium:bene_gesserit_sister:2"  # 3
CARRYALL = "imperium:carryall:0"  # 5
CHANI = "imperium:chani_card:0"  # 5, acquire box: 1 water
JESSICA = "imperium:lady_jessica_card:0"  # 7
DIRECTORSHIP = "imperium:choam_directorship:0"  # 8
CONVINCING = (
    "player:0:starter:convincing_argument:0",
    "player:0:starter:convincing_argument:1",
)
# The Reserve: Arrakis Liaison 2, The Spice Must Flow 9, Foldspace (an icon).
LIAISON = "arrakis_liaison"
FOLDSPACE = "foldspace_card"


def _start(
    config: RulesetConfig = CONFIG, seed: int = 3
) -> tuple[UprisingRulesEngine, GameState]:
    """Round 1 of the original game at seat 0's first turn."""

    engine = UprisingRulesEngine(leader_ids=LEADERS)
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    players = list(state.players)
    players[seat] = replace(players[seat], **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _with_hand(state: GameState, hand: tuple[str, ...]) -> GameState:
    """Seat 0 holding ``hand``; the cards it held go back into its deck."""

    owner = state.players[0]
    rest = tuple(card for card in (*owner.hand, *owner.deck) if card not in hand)
    return _seat(state, hand=hand, deck=rest)


def _market(
    state: GameState,
    row: tuple[str, ...],
    *,
    liaison: int = 8,
    spice_must_flow: int = 10,
    foldspace: int = 6,
) -> GameState:
    """``state`` with ``row`` as the Imperium Row, the rest of the deck as it was."""

    return replace(
        state,
        imperium_row=row,
        imperium_deck=tuple(card for card in state.imperium_deck if card not in row),
        reserve_stacks=(
            (LIAISON, liaison),
            ("imperium_the_spice_must_flow", spice_must_flow),
            (FOLDSPACE, foldspace),
        ),
    )


def _play(card: str, option: int = 0, actor: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=actor,
        arguments=(("card_id", card), ("option", option)),
    )


def _acquire(action_id: str, name: str, value: str, *, top: bool) -> DomainAction:
    return DomainAction(
        action_id=action_id,
        actor=0,
        arguments=(
            (name, value),
            *((("to_deck_top", True),) if top else ()),
        ),
    )


def _imperium(card: str, *, top: bool = False) -> DomainAction:
    return _acquire("acquire_imperium", "instance_id", card, top=top)


def _reserve(card: str, *, top: bool = False) -> DomainAction:
    return _acquire("acquire_reserve", "card_id", card, top=top)


def _by_intrigue(card: str, *, top: bool = False) -> DomainAction:
    """The Intrigue acquisition of an Imperium instance or a Reserve card id."""

    if ":" in card:
        return _acquire("acquire_intrigue_imperium", "instance_id", card, top=top)
    return _acquire("acquire_intrigue_reserve", "card_id", card, top=top)


def _offered(
    engine: UprisingRulesEngine, state: GameState, *action_ids: str
) -> list[DomainAction]:
    """The whole actions of seat 0 with one of ``action_ids``, in offer order."""

    return [
        action
        for action in engine.whole_actions(state, 0)
        if action.action_id in action_ids
    ]


def _twin(action: DomainAction) -> bool:
    return dict(action.arguments).get("to_deck_top") is True


def _persuasion(state: GameState) -> int:
    frame = state.decision_stack[-1]
    assert frame.kind == FrameKind.REVEAL
    persuasion = dict(frame.context)["persuasion"]
    assert isinstance(persuasion, int)
    return persuasion


def _bypass_hand(
    spice: int = 2, *, row: tuple[str, ...] | None = None
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 at its first turn holding Bypass Protocol, with the market below."""

    engine, state = _start()
    state = _market(state, row or (MISSIONARIA, SISTER, CARRYALL, CHANI, JESSICA))
    return engine, _seat(
        state, intrigue_cards=(BYPASS,), resources=Resources(spice=spice)
    )


def _mission_hand(
    config: RulesetConfig = CONFIG,
    row: tuple[str, ...] = (MISSIONARIA, SISTER, CARRYALL, CHANI, JESSICA),
    **changes: Any,
) -> tuple[UprisingRulesEngine, GameState]:
    """Seat 0 at its first turn holding Recruitment Mission and two Persuasion
    cards (4 Persuasion), with ``row`` as the Imperium Row."""

    engine, state = _start(config)
    state = _with_hand(_market(state, row), CONVINCING)
    return engine, _seat(state, intrigue_cards=(MISSION,), **changes)


def _mission_reveal(
    config: RulesetConfig = CONFIG, **changes: Any
) -> tuple[UprisingRulesEngine, GameState]:
    """The above after Recruitment Mission was played in the Agent turn and
    the Reveal turn began: 5 Persuasion, the deck-top option effective."""

    engine, state = _mission_hand(config, **changes)
    played = apply_whole(engine, state, _play(MISSION)).state
    return engine, engine.apply(played, REVEAL).state


# --- Bypass Protocol (Plot) --------------------------------------------------


def test_bypass_protocol_is_two_exclusive_plot_options() -> None:
    # "Acquire a card that costs [Persuasion 3] or less." -OR- "[2 spice] ->
    # Acquire a card that costs [Persuasion 5] or less to the top of your
    # deck." [Bypass Protocol card, app text]; 1 copy [DI p. 3]. Two exclusive
    # Plot options (OQ-058, imperium-base.md 16).
    entry = intrigue_card_for_instance(BYPASS)
    assert entry.card.name == "Bypass Protocol"
    assert entry.copies == 1
    assert entry.play_data_complete
    assert [option.timing.value for option in entry.options] == ["plot", "plot"]
    first, second = (option.sections for option in entry.options)
    assert first[0].costs == ()
    assert first[0].rewards == (AcquireCardUpTo(3),)
    assert second[0].costs == (PayResources(spice=2),)
    assert second[0].rewards == (AcquireCardUpTo(5, to_deck_top=True),)
    assert intrigue_card_text(entry) == [
        "Plot — Acquire a card costing 3 or less",
        "Plot — Pay 2 spice → Acquire a card costing 5 or less to the top of your deck",
    ]
    assert intrigue_card_text_ko(entry)[1].endswith("(카드덱 맨 위로)")
    assert "bypass_protocol" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_bypass_protocol_first_option_offers_row_and_reserve_cards_up_to_three() -> (
    None
):
    # OQ-125 (decided 2026-10-23): "a card that costs N or less" is the Row's
    # five cards and the Reserve's Arrakis Liaison and The Spice Must Flow,
    # never Foldspace [DI p. 11] [FAQ p. 2]. Row: costs 1, 3, 5, 5, 7;
    # Reserve: Liaison 2 (offered), The Spice Must Flow 9, Foldspace (an
    # icon, cost 0, with a copy left, never offered).
    engine, state = _bypass_hand()
    assert legal_intrigue_play_actions(state, 0) == (
        _play(BYPASS, 0),
        _play(BYPASS, 1),
    )
    opened = apply_whole(engine, state, _play(BYPASS, 0)).state

    rows = _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    )
    assert rows == [
        _by_intrigue(LIAISON),
        _by_intrigue(MISSIONARIA),
        _by_intrigue(SISTER),
    ]
    assert not any(_twin(row) for row in rows)
    assert _by_intrigue(FOLDSPACE) not in rows


def test_bypass_protocol_first_option_acquires_to_the_discard_pile() -> None:
    engine, state = _bypass_hand(spice=0)
    deck = state.players[0].deck
    opened = apply_whole(engine, state, _play(BYPASS, 0)).state

    done = apply_whole(engine, opened, _by_intrigue(SISTER)).state

    owner = done.players[0]
    assert owner.discard_pile == (*state.players[0].discard_pile, SISTER)
    assert owner.deck == deck
    assert SISTER not in done.imperium_row
    assert done.intrigue_discard == (BYPASS,)
    assert owner.intrigue_cards == ()
    assert done.decision_stack[-1].kind == FrameKind.TURN


def test_bypass_protocol_first_option_takes_a_reserve_card() -> None:
    engine, state = _bypass_hand(spice=0)
    opened = apply_whole(engine, state, _play(BYPASS, 0)).state

    done = apply_whole(engine, opened, _by_intrigue(LIAISON)).state

    (taken,) = (
        card for card in done.players[0].discard_pile if card.startswith("reserve:")
    )
    assert taken.startswith(f"reserve:{LIAISON}:")
    assert dict(done.reserve_stacks)[LIAISON] == 7
    assert done.players[0].deck == state.players[0].deck


def test_bypass_protocol_first_option_is_played_with_nothing_to_acquire() -> None:
    # Cost-free, so played even when it then does nothing (OQ-113 (C),
    # imperium-base.md 16): every Row card costs more than 3 and the Reserve's
    # Arrakis Liaison is gone (Foldspace still has copies, and is no choice).
    engine, state = _bypass_hand(row=(CARRYALL, CHANI, JESSICA, DIRECTORSHIP))
    state = replace(state, reserve_stacks=((LIAISON, 0), (FOLDSPACE, 6)))
    assert _play(BYPASS, 0) in legal_intrigue_play_actions(state, 0)
    opened = apply_whole(engine, state, _play(BYPASS, 0)).state

    actions = engine.whole_actions(opened, 0)
    assert [action.action_id for action in actions] == ["skip_intrigue_acquisition"]
    done = apply_whole(engine, opened, actions[0]).state
    assert done.players[0].discard_pile == state.players[0].discard_pile
    assert done.players[0].deck == state.players[0].deck
    assert done.intrigue_discard == (BYPASS,)


def test_bypass_protocol_second_option_pays_two_spice_and_tops_the_deck() -> None:
    # "[2 spice] -> Acquire a card that costs [Persuasion 5] or less to the top
    # of your deck": the cost is paid, the card is placed on the deck first
    # and its acquire box resolves (Chani's one water), the deck order being
    # hidden as for any deck card (imperium-base.md 14, OQ-010).
    engine, state = _bypass_hand(spice=3)
    water = state.players[0].resources.water
    deck = state.players[0].deck
    opened = apply_whole(engine, state, _play(BYPASS, 1))
    assert opened.state.players[0].resources.spice == 1

    result = apply_whole(engine, opened.state, _by_intrigue(CHANI, top=True))
    done = result.state

    owner = done.players[0]
    assert owner.deck == (CHANI, *deck)
    assert CHANI not in owner.discard_pile
    assert CHANI not in done.imperium_row
    assert owner.resources.spice == 1
    assert owner.resources.water == water + 1
    assert done.intrigue_discard == (BYPASS,)
    (event,) = (e for e in result.events if e.kind == "card_acquired")
    assert dict(event.payload) == {
        "card_id": "chani_card",
        "destination": "deck_top",
        "player": 0,
    }
    assert known_card_seats(done)[CHANI] == frozenset()


def test_bypass_protocol_second_option_offers_only_the_deck_top_rows() -> None:
    # "to the top of your deck" is the card's own destination, not a choice:
    # every row is a ``to_deck_top`` twin, up to cost 5 (Row costs 1, 3, 5, 5,
    # 7; Liaison 2; never Foldspace).
    engine, state = _bypass_hand()
    opened = apply_whole(engine, state, _play(BYPASS, 1)).state

    rows = _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    )
    assert rows == [
        _by_intrigue(LIAISON, top=True),
        _by_intrigue(MISSIONARIA, top=True),
        _by_intrigue(SISTER, top=True),
        _by_intrigue(CARRYALL, top=True),
        _by_intrigue(CHANI, top=True),
    ]


def test_bypass_protocol_second_option_takes_a_reserve_card_to_the_deck() -> None:
    engine, state = _bypass_hand()
    opened = apply_whole(engine, state, _play(BYPASS, 1)).state

    done = apply_whole(engine, opened, _by_intrigue(LIAISON, top=True)).state

    owner = done.players[0]
    assert owner.deck[0].startswith(f"reserve:{LIAISON}:")
    assert owner.deck[1:] == state.players[0].deck
    assert not any(card.startswith("reserve:") for card in owner.discard_pile)
    assert dict(done.reserve_stacks)[LIAISON] == 7


def test_bypass_protocol_second_option_needs_two_spice() -> None:
    engine, state = _bypass_hand(spice=1)
    assert legal_intrigue_play_actions(state, 0) == (_play(BYPASS, 0),)
    assert _play(BYPASS, 1) not in engine.whole_actions(state, 0)


def test_bypass_protocol_second_option_needs_a_card_of_cost_five_or_less() -> None:
    # A cost line needs a reward that can change something (OQ-071): with only
    # cards above 5 in reach, the first option is still played and the second
    # is not.
    engine, state = _bypass_hand(row=(JESSICA, DIRECTORSHIP))
    state = replace(state, reserve_stacks=((LIAISON, 0), (FOLDSPACE, 6)))
    assert legal_intrigue_play_actions(state, 0) == (_play(BYPASS, 0),)


def test_bypass_protocol_second_option_reaches_a_card_of_cost_exactly_five() -> None:
    engine, state = _bypass_hand(row=(JESSICA, DIRECTORSHIP, CARRYALL))
    state = replace(state, reserve_stacks=((LIAISON, 0), (FOLDSPACE, 6)))
    assert _play(BYPASS, 1) in legal_intrigue_play_actions(state, 0)
    opened = apply_whole(engine, state, _play(BYPASS, 1)).state
    assert _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    ) == [_by_intrigue(CARRYALL, top=True)]


def test_bypass_protocol_reaches_the_owners_set_aside_card_at_its_printed_cost() -> (
    None
):
    # "You may use other means to acquire the card (for example: Bypass
    # Protocol, Boundless Ambition), though the 1 persuasion discount will not
    # apply" [FAQ p. 3]: the owner's own Manipulate set-aside card is within
    # reach at its printed cost (``AcquireCardUpTo``'s existing behaviour,
    # kept), also on top of the deck.
    engine, state = _bypass_hand(row=(JESSICA, DIRECTORSHIP))
    state = _seat(state, imperium_set_aside=(SISTER,))
    state = replace(state, reserve_stacks=((LIAISON, 0), (FOLDSPACE, 6)))
    opened = apply_whole(engine, state, _play(BYPASS, 0)).state
    assert _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    ) == [_by_intrigue(SISTER)]

    done = apply_whole(engine, opened, _by_intrigue(SISTER)).state
    assert SISTER in done.players[0].discard_pile
    assert done.players[0].imperium_set_aside == ()

    deck_opened = apply_whole(engine, state, _play(BYPASS, 1)).state
    top = apply_whole(engine, deck_opened, _by_intrigue(SISTER, top=True)).state
    assert top.players[0].deck[0] == SISTER
    assert top.players[0].imperium_set_aside == ()


# --- Recruitment Mission (Plot) ----------------------------------------------


def test_recruitment_mission_is_one_plot_of_persuasion_and_the_deck_top() -> None:
    # "Gain [Persuasion 1] during your Reveal turn this round." / "You may put
    # cards you acquire on top of your deck." [Recruitment Mission card, app
    # text]; 1 copy [DI p. 3]. One cost-free Plot whose whole effect waits for
    # the owner's Reveal turn [FAQ p. 2].
    entry = intrigue_card_for_instance(MISSION)
    assert entry.card.name == "Recruitment Mission"
    assert entry.copies == 1
    assert entry.play_data_complete
    (option,) = entry.options
    assert option.timing.value == "plot"
    (section,) = option.sections
    assert section.costs == ()
    assert section.rewards == (
        RevealPersuasionThisRound(1),
        AcquireToDeckTopThisRound(),
    )
    assert intrigue_card_text(entry) == [
        "Plot — Gain 1 Persuasion during your Reveal turn this round,"
        " you may put cards you acquire on top of your deck"
    ]
    assert "{acquire}" in intrigue_card_text_ko(entry)[0]
    assert "recruitment_mission" not in {entry.card.card_id for entry in INTRIGUE_CARDS}


def test_recruitment_mission_waits_face_up_and_gives_one_persuasion() -> None:
    # "If the card does something that won't apply until your next Reveal turn
    # (for example: Charisma, Recruitment Mission), keep it face up in front of
    # you until then, then use and discard it." [FAQ p. 2]
    engine, state = _mission_hand()
    assert legal_intrigue_play_actions(state, 0) == (_play(MISSION),)
    plain = _persuasion(engine.apply(state, REVEAL).state)

    result = apply_whole(engine, state, _play(MISSION))
    played = result.state

    assert played.players[0].intrigue_cards == ()
    assert played.players[0].intrigue_faceup == (MISSION,)
    assert MISSION not in played.intrigue_discard
    assert played.players[0].acquire_to_deck_top_round is True
    assert "intrigue_kept_faceup" in [event.kind for event in result.events]
    assert played.decision_stack[-1].kind == FrameKind.TURN
    revealed = engine.apply(played, REVEAL).state
    assert _persuasion(revealed) == plain + 1
    # The option is the owner's alone.
    assert [seat.acquire_to_deck_top_round for seat in played.players] == [
        True,
        False,
        False,
        False,
    ]


def test_every_reveal_acquisition_offers_both_destinations() -> None:
    # "for each card acquired the owner chooses top of deck or discard pile"
    # [FAQ p. 3]: the Row's cards, the Reserve's and the seat's own Manipulate
    # set-aside card each come as the plain row and its ``to_deck_top`` twin.
    engine, state = _mission_hand(imperium_set_aside=(INFANTRY,))
    revealed = engine.apply(
        apply_whole(engine, state, _play(MISSION)).state, REVEAL
    ).state
    assert _persuasion(revealed) == 5

    row = _offered(engine, revealed, "acquire_imperium")
    assert row == [
        action
        for card in (MISSIONARIA, SISTER, CARRYALL, CHANI)
        for action in (_imperium(card), _imperium(card, top=True))
    ]
    assert _offered(engine, revealed, "acquire_reserve") == [
        _reserve(LIAISON),
        _reserve(LIAISON, top=True),
    ]
    assert _offered(engine, revealed, "acquire_manipulated_imperium") == [
        _acquire("acquire_manipulated_imperium", "instance_id", INFANTRY, top=False),
        _acquire("acquire_manipulated_imperium", "instance_id", INFANTRY, top=True),
    ]
    codec = ActionCodec(CONFIG)
    for action in engine.legal_actions(revealed, 0):
        codec.encode(action)


def test_a_reveal_acquisition_may_go_on_top_of_the_deck() -> None:
    # The card is placed first and its acquire box then resolves (Chani's
    # water); the Persuasion is paid as for a plain purchase and the Row
    # refills. The identity is public, the instance named only while it stays
    # public (OQ-010) and, once on the deck, known to nobody.
    engine, state = _mission_reveal()
    owner = state.players[0]
    persuasion = _persuasion(state)

    result = apply_whole(engine, state, _imperium(CHANI, top=True))
    done = result.state

    after = done.players[0]
    assert after.deck == (CHANI, *owner.deck)
    assert after.discard_pile == owner.discard_pile
    assert after.resources.water == owner.resources.water + 1
    assert CHANI not in done.imperium_row
    assert len(done.imperium_row) == 5
    assert _persuasion(done) == persuasion - 5
    (event,) = (e for e in result.events if e.kind == "card_acquired")
    assert dict(event.payload) == {
        "card_id": "chani_card",
        "destination": "deck_top",
        "player": 0,
    }
    assert known_card_seats(done)[CHANI] == frozenset()
    assert _persuasion(done) == 0


def test_a_reveal_acquisition_may_still_go_to_the_discard_pile() -> None:
    engine, state = _mission_reveal()
    owner = state.players[0]

    result = apply_whole(engine, state, _imperium(SISTER))
    done = result.state

    assert done.players[0].deck == owner.deck
    assert done.players[0].discard_pile == (*owner.discard_pile, SISTER)
    (event,) = (e for e in result.events if e.kind == "card_acquired")
    assert dict(event.payload)["instance_id"] == SISTER
    assert "destination" not in dict(event.payload)


def test_a_reserve_card_and_a_set_aside_card_may_go_on_top_of_the_deck() -> None:
    engine, state = _mission_reveal(imperium_set_aside=(INFANTRY,))
    owner = state.players[0]

    reserve = apply_whole(engine, state, _reserve(LIAISON, top=True)).state
    assert reserve.players[0].deck[0].startswith(f"reserve:{LIAISON}:")
    assert reserve.players[0].deck[1:] == owner.deck
    assert reserve.players[0].discard_pile == owner.discard_pile
    assert dict(reserve.reserve_stacks)[LIAISON] == 7

    manipulated = apply_whole(
        engine,
        state,
        _acquire("acquire_manipulated_imperium", "instance_id", INFANTRY, top=True),
    ).state
    assert manipulated.players[0].deck == (INFANTRY, *owner.deck)
    assert manipulated.players[0].imperium_set_aside == ()


def test_a_card_bought_before_the_plot_is_played_is_unaffected() -> None:
    # "Recruitment Mission은 소급하지 않는다" (imperium-base.md 13.3): played
    # in the Reveal turn after a purchase, it changes nothing about that
    # card, gives its Persuasion at once, and offers both destinations for
    # the cards acquired after it.
    engine, state = _mission_hand()
    revealed = engine.apply(state, REVEAL).state
    assert not any(_twin(action) for action in engine.whole_actions(revealed, 0))
    assert _persuasion(revealed) == 4

    bought = apply_whole(engine, revealed, _imperium(SISTER)).state
    owner = bought.players[0]
    assert SISTER in owner.discard_pile
    assert _persuasion(bought) == 1
    assert _play(MISSION) in engine.whole_actions(bought, 0)

    played = apply_whole(engine, bought, _play(MISSION)).state
    assert played.decision_stack[-1].kind == FrameKind.REVEAL
    assert _persuasion(played) == 2
    assert played.players[0].discard_pile == owner.discard_pile
    assert played.players[0].deck == owner.deck
    assert played.players[0].intrigue_faceup == (MISSION,)
    assert _offered(engine, played, "acquire_imperium") == [
        _imperium(MISSIONARIA),
        _imperium(MISSIONARIA, top=True),
    ]


def test_nothing_is_offered_in_an_agent_turn() -> None:
    # The whole card applies only to the owner's Reveal turn [FAQ p. 3]: with
    # the option set and the seat in an Agent turn, Bypass Protocol's first
    # option (an acquisition in the Agent turn) offers plain rows only, and
    # there is no purchase to put anywhere.
    engine, state = _bypass_hand(spice=0)
    state = _seat(state, acquire_to_deck_top_round=True)
    assert not [
        a for a in engine.whole_actions(state, 0) if a.action_id.startswith("acquire")
    ]

    opened = apply_whole(engine, state, _play(BYPASS, 0)).state

    rows = _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    )
    assert rows
    assert not any(_twin(row) for row in rows)


def test_another_seats_reveal_offers_no_deck_top() -> None:
    # "your Reveal turn": the option sits on the playing seat only.
    engine, state = _mission_hand()
    state = _seat(state, 0, acquire_to_deck_top_round=False)
    state = _seat(state, 1, acquire_to_deck_top_round=True)
    revealed = engine.apply(state, REVEAL).state
    assert not any(_twin(action) for action in engine.whole_actions(revealed, 0))


def test_the_option_ends_with_the_reveal_turn() -> None:
    # The card stays face up through its owner's Reveal turn and is discarded
    # when that turn ends [FAQ p. 2]; the option goes with it.
    engine, state = _mission_reveal()

    finished = engine.apply(state, FINISH_REVEAL)
    after = finished.state

    assert after.players[0].intrigue_faceup == ()
    assert MISSION in after.intrigue_discard
    assert after.players[0].acquire_to_deck_top_round is False
    expired = [e for e in finished.events if e.kind == "intrigue_expired"]
    assert [dict(e.payload)["card_id"] for e in expired] == [MISSION]


def test_recruitment_mission_played_in_the_reveal_turn_still_counts() -> None:
    # A Plot may be played at any time during the owner's Reveal turn
    # [Main pp. 7-8]: the Persuasion joins that Reveal and the card is
    # discarded as the turn ends [FAQ p. 2] (Tleilaxu Puppet's shape).
    engine, state = _mission_hand()
    revealed = engine.apply(state, REVEAL).state
    persuasion = _persuasion(revealed)

    played = apply_whole(engine, revealed, _play(MISSION)).state

    assert played.decision_stack[-1].kind == FrameKind.REVEAL
    assert _persuasion(played) == persuasion + 1
    assert played.players[0].reveal_persuasion_round_bonus == 0
    assert played.players[0].acquire_to_deck_top_round is True
    finished = engine.apply(played, FINISH_REVEAL).state
    assert finished.players[0].intrigue_faceup == ()
    assert MISSION in finished.intrigue_discard
    assert finished.players[0].acquire_to_deck_top_round is False


def test_bypass_protocol_in_the_reveal_turn_offers_both_destinations() -> None:
    # Bypass Protocol's first option acquires a card in the Reveal turn like
    # any other acquisition [FAQ p. 3], so with Recruitment Mission effective
    # each card comes to the discard pile or on the deck; the second option
    # is "to the top of your deck" and keeps its twins only.
    engine, state = _mission_hand()
    state = _seat(state, intrigue_cards=(MISSION, BYPASS), resources=Resources(spice=2))
    revealed = engine.apply(
        apply_whole(engine, state, _play(MISSION)).state, REVEAL
    ).state

    opened = apply_whole(engine, revealed, _play(BYPASS, 0)).state
    rows = _offered(
        engine, opened, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    )
    assert rows == [
        action
        for card in (LIAISON, MISSIONARIA, SISTER)
        for action in (_by_intrigue(card), _by_intrigue(card, top=True))
    ]
    codec = ActionCodec(CONFIG)
    for action in engine.legal_actions(opened, 0):
        codec.encode(action)

    plain = apply_whole(engine, opened, _by_intrigue(SISTER)).state
    assert SISTER in plain.players[0].discard_pile
    assert plain.decision_stack[-1].kind == FrameKind.REVEAL

    top = apply_whole(engine, opened, _by_intrigue(SISTER, top=True)).state
    assert top.players[0].deck[0] == SISTER
    assert SISTER not in top.players[0].discard_pile

    paid = apply_whole(engine, revealed, _play(BYPASS, 1)).state
    second = _offered(
        engine, paid, "acquire_intrigue_imperium", "acquire_intrigue_reserve"
    )
    assert second and all(_twin(row) for row in second)


def _bare_reveal(
    config: RulesetConfig, owner: PlayerState, **overrides: object
) -> GameState:
    """A Reveal turn of seat 0 (``owner``) in a hand-built state of ``config``.

    Recruitment Mission is an original-game card, but the original game takes
    no expansion before stage P7 (``setup._IMPERIUM_PENDING_OPTIONS``); the
    deck-top option is the seat's flag, so the expansion rows are checked on
    an Uprising game with the flag set as the card's play sets it.
    """

    imperium = imperium_deck_instance_ids(False)
    values: dict[str, object] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "current_conflict_ids": (CONFLICTS[0].card.card_id,),
        "intrigue_deck": intrigue_deck_instance_ids(False)[:6],
        "imperium_row": imperium[:5],
        "imperium_deck": imperium[5:20],
        "players": (
            owner,
            *(
                PlayerState(player_id=seat, research_space=owner.research_space)
                for seat in range(1, 4)
            ),
        ),
        "sardaukar_commander_space_ids": (),
        "sardaukar_commanders_bank": 1 if config.bloodlines else 0,
        "decision_stack": (
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    }
    values.update(overrides)
    state = GameState(**values)  # type: ignore[arg-type]
    return begin_reveal_turn(
        state, DomainAction(action_id="reveal_turn", actor=0)
    ).state


def test_a_tleilaxu_card_may_top_the_deck_without_a_genetic_marker() -> None:
    # Immortality [Immortality p. 6]: Tleilaxu cards go on top of the deck
    # only once the first genetic marker is reached, so a seat below it is
    # offered the plain row alone; Recruitment Mission covers "cards you
    # acquire" in its Reveal turn, so while it is effective the Tleilaxu Row
    # gives the twin too (the first marker or the card), beside the Imperium
    # Row's.
    deck = starting_deck_instance_ids(0, immortality=True)
    contaminator = "tleilaxu:contaminator:0"
    subject = "tleilaxu:subject_x_137:0"

    def owner(**changes: object) -> PlayerState:
        values: dict[str, object] = {
            "player_id": 0,
            "hand": deck[:5],
            "deck": deck[5:],
            "resources": Resources(solari=4, spice=2, water=2),
            "research_space": RESEARCH_START_ID,
            "specimens": 6,
            "troops_supply": 3,
        }
        values.update(changes)
        return PlayerState(**values)  # type: ignore[arg-type]

    overrides: dict[str, object] = {
        "tleilaxu_row": (contaminator, subject),
        "tleilaxu_deck": (),
    }
    plain = _bare_reveal(IMMORTALITY_UPRISING, owner(), **overrides)
    rows = legal_tleilaxu_acquisitions(plain, 0)
    assert not any(_twin(action) for action in rows)
    assert not any(_twin(action) for action in legal_imperium_acquisitions(plain, 0))

    state = _bare_reveal(
        IMMORTALITY_UPRISING, owner(acquire_to_deck_top_round=True), **overrides
    )
    rows = legal_tleilaxu_acquisitions(state, 0)
    for card in (contaminator, subject):
        plain_row = DomainAction("acquire_tleilaxu", 0, (("instance_id", card),))
        twin_row = DomainAction(
            "acquire_tleilaxu", 0, (("instance_id", card), ("to_deck_top", True))
        )
        assert rows.index(twin_row) == rows.index(plain_row) + 1
    assert any(_twin(a) for a in legal_imperium_acquisitions(state, 0))
    codec = ActionCodec(IMMORTALITY_UPRISING)
    for action in UprisingRulesEngine().legal_actions(state, 0):
        if action.action_id in ("acquire_tleilaxu", "choose_tleilaxu_card"):
            codec.encode(action)

    twin = DomainAction(
        "acquire_tleilaxu", 0, (("instance_id", subject), ("to_deck_top", True))
    )
    result = apply_tleilaxu_acquisition(state, twin)
    after = result.state.players[0]
    assert after.deck == (subject, *state.players[0].deck)
    assert subject not in after.discard_pile
    assert after.specimens < 6
    (event,) = (e for e in result.events if e.kind == "tleilaxu_card_acquired")
    assert dict(event.payload)["to_deck_top"] is True
    # Without the option or the marker the same twin is refused.
    with pytest.raises(ValueError, match="legal Tleilaxu Row acquisition"):
        apply_tleilaxu_acquisition(plain, twin)


# --- Engineered Miracle's Command (Bloodlines) -------------------------------


def test_a_commanded_row_card_comes_both_ways_while_the_option_is_effective() -> None:
    # Engineered Miracle's "Command: Trash this card -> Acquire a card from the
    # Imperium Row" is an acquisition in the Reveal turn like any other.
    miracle = "imperium:engineered_miracle:0"
    row = ("imperium:guild_envoy:0", "imperium:maula_pistol:0")
    starters = starting_deck_instance_ids(0)
    owner = PlayerState(
        player_id=0,
        hand=("imperium:sandwalk:0", "imperium:sandwalk:1", miracle),
        deck=starters[:4],
        high_council=True,
        acquire_to_deck_top_round=True,
    )
    revealed = _bare_reveal(BLOODLINES_UPRISING, owner, imperium_row=row)

    rows = legal_reveal_command_acquisition_actions(revealed, 0)
    assert rows == tuple(
        _acquire("command_acquire_row_card", "instance_id", card, top=top)
        for card in row
        for top in (False, True)
    )
    done = apply_reveal_command_acquisition(revealed, rows[3]).state
    assert done.players[0].deck == (row[1], *starters[:4])
    assert miracle in done.players[0].trashed
    assert row[1] not in done.players[0].discard_pile

    plain = apply_reveal_command_acquisition(revealed, rows[2]).state
    assert row[1] in plain.players[0].discard_pile
    assert plain.players[0].deck == starters[:4]

    unflagged = _bare_reveal(
        BLOODLINES_UPRISING,
        replace(owner, acquire_to_deck_top_round=False),
        imperium_row=row,
    )
    assert not any(
        _twin(a) for a in legal_reveal_command_acquisition_actions(unflagged, 0)
    )


# --- The catalogs ------------------------------------------------------------


def test_only_the_original_catalogs_hold_the_deck_top_twins() -> None:
    def twins(config: RulesetConfig) -> set[str]:
        return {
            template.action_id
            for template in ActionCodec(config).catalog
            if ("to_deck_top", True) in template.arguments
        }

    original = twins(CONFIG)
    assert {
        "choose_imperium_card",
        "choose_reserve_card",
    } <= original
    # Uprising's catalogs hold no deck-top row outside Immortality's Tleilaxu
    # Row, and Immortality's gain none beyond it.
    assert twins(RulesetConfig()) == set()
    assert twins(RulesetConfig(immortality=True)) <= {
        "choose_tleilaxu_card",
        "acquire_tleilaxu",
        "acquire_intrigue_tleilaxu",
    }
