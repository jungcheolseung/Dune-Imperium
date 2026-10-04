"""The Imperium Row card borrowed with Usurp is not "in play" (OQ-054).

Rule source: "A grafted card in the Imperium Row isn't considered to be 'in
play.'" [Immortality p. 14]; the designer ruling adopted on 2026-09-09
("Usurp로 빌린 Row 카드는 'in play'가 아니다", OQ-054). User ruling
2026-10-04: the borrowed card keeps its placement (the owner's play area,
the Row refilled at once, trashed when the owner ends the turn) but counts
as in play for no rule: not for another card's Faction Bond, not for an
in-play count, not as a trash target, and it never returns to a hand.
"""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.immortality.board import RESEARCH_START_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_effects import (
    legal_agent_card_trash_actions,
    resolve_agent_card_effect,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import legal_desert_tactics_actions
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.effects import current_agent_effect_context
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.graft import (
    apply_graft_partner,
    apply_graft_switch,
    legal_graft_partner_actions,
    legal_graft_switch_actions,
)
from dune_imperium.rules.optional_trash import (
    legal_optional_trash_actions,
    optional_trash_frame,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn

IMMORTALITY = RulesetConfig(immortality=True, promo_cards=True)
STARTERS = starting_deck_instance_ids(0, immortality=True)
DAGGER = next(card for card in STARTERS if "dagger:0" in card)
USURP = "tleilaxu:usurp:0"
WEIRDING_WOMAN = "imperium:weirding_woman:0"
TRUTHTRANCE = "imperium:truthtrance:0"
REPLACEMENT_EYES = "imperium:replacement_eyes:0"
STILGAR_DEVOTED = "imperium:stilgar_the_devoted:0"
DESERT_SURVIVAL = "imperium:desert_survival:0"
CHANI = "imperium:chani_clever_tactician:0"


def _seat(seat: int, **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": seat,
        "research_space": RESEARCH_START_ID,
        "family_atomics": True,
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(owner: PlayerState, row_card: str) -> GameState:
    """Seat 0 to act, with ``row_card`` first in the Imperium Row."""

    owned = (*owner.hand, *owner.in_play, *owner.discard_pile)
    imperium = tuple(
        card
        for card in imperium_deck_instance_ids(False)
        if card != row_card and card not in owned
    )
    return GameState(
        config=IMMORTALITY,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=(CONFLICTS[0].card.card_id,),
        intrigue_deck=intrigue_deck_instance_ids(False, immortality=True)[:6],
        imperium_row=(row_card, *imperium[:4]),
        imperium_deck=imperium[4:20],
        tleilaxu_track_spice=2,
        players=(owner, *(_seat(seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _owner(hand: tuple[str, ...], **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "hand": hand,
        "deck": tuple(card for card in STARTERS if card not in hand),
        "resources": Resources(solari=4, spice=2, water=2),
        "troops_supply": 9,
    }
    values.update(extra)
    return _seat(0, **values)


def _place(
    state: GameState, card_id: str, space_id: str, *, graft: bool = False
) -> GameState:
    action = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["card_id"] == card_id
        and dict(action.arguments)["space_id"] == space_id
        and (dict(action.arguments).get("graft") is True) == graft
        and "infiltrate_post_id" not in dict(action.arguments)
    )
    return apply_agent_action(state, action).state


def _usurp(state: GameState, space_id: str, row_card: str) -> GameState:
    """Place Usurp on ``space_id`` and borrow ``row_card`` from the Row."""

    placed = _place(state, USURP, space_id, graft=True)
    partner = next(
        action
        for action in legal_graft_partner_actions(placed, 0)
        if dict(action.arguments)["card_id"] == row_card
    )
    grafted = apply_graft_partner(placed, partner).state
    owner = grafted.players[0]
    assert row_card in owner.in_play and owner.usurped_row_card_id == row_card
    return grafted


def _switch(state: GameState) -> GameState:
    return apply_graft_switch(state, legal_graft_switch_actions(state, 0)[0]).state


def _trash_targets(actions: tuple[DomainAction, ...]) -> set[str]:
    return {
        str(dict(action.arguments)["card_id"])
        for action in actions
        if "card_id" in dict(action.arguments)
    }


def _finish_turn(state: GameState) -> GameState:
    """Resolve the owner's pending boxes through the engine until the turn closes."""

    engine = UprisingRulesEngine()
    for _ in range(20):
        if state.decision_stack[-1].kind == FrameKind.TURN:
            return state
        actions = engine.legal_actions(state, 0)
        preferred = [
            a
            for a in actions
            if a.action_id
            in (
                "resolve_agent_card_effect",
                "resolve_board_effect",
                "finish_agent_turn",
            )
        ] or [a for a in actions if not a.action_id.startswith("deploy")]
        state = engine.apply(state, preferred[0]).state
    raise AssertionError("the Agent turn did not close")


def test_counted_in_play_leaves_out_only_the_borrowed_row_card() -> None:
    seat = _seat(0, in_play=(TRUTHTRANCE, USURP, WEIRDING_WOMAN))
    assert counted_in_play(seat) == seat.in_play
    borrowed = replace(seat, usurped_row_card_id=WEIRDING_WOMAN)
    assert counted_in_play(borrowed) == (TRUTHTRANCE, USURP)
    # The play area itself keeps the card until the turn's end trashes it.
    assert borrowed.in_play == seat.in_play


def test_a_borrowed_weirding_woman_never_returns_to_hand() -> None:
    # Weirding Woman: "If you have another Bene Gesserit card in play: Return
    # this card to your hand." Truthtrance, played on an earlier Agent turn,
    # is that other card. Borrowed through Usurp the card is not in play
    # [Immortality p. 14] (OQ-054), so it stays where it is and the turn's
    # end trashes it, as Stillsuit Manufacturer's return does not happen.
    owner = _owner((USURP,), in_play=(TRUTHTRANCE,))
    grafted = _usurp(_state(owner, WEIRDING_WOMAN), "arrakeen", WEIRDING_WOMAN)
    _, context = current_agent_effect_context(grafted)
    # The box is never left waiting: it could never resolve.
    assert context["graft_pending_effect"] is False
    assert legal_graft_switch_actions(grafted, 0) == ()
    assert all(
        action.action_id != "resolve_agent_card_effect"
        for action in UprisingRulesEngine().legal_actions(grafted, 0)
    )

    closed = _finish_turn(grafted).players[0]
    assert WEIRDING_WOMAN in closed.trashed
    assert WEIRDING_WOMAN not in (*closed.hand, *closed.in_play)


def test_weirding_woman_played_from_hand_still_returns_with_a_bond() -> None:
    # The guard is the Usurp case only: the same box on a played card returns
    # it [Weirding Woman card] [Main pp. 9, 20].
    owner = _owner((WEIRDING_WOMAN,), in_play=(TRUTHTRANCE,))
    placed = _place(_state(owner, REPLACEMENT_EYES), WEIRDING_WOMAN, "arrakeen")
    resolved = resolve_agent_card_effect(placed).state.players[0]
    assert WEIRDING_WOMAN in resolved.hand and WEIRDING_WOMAN not in resolved.in_play


def test_the_borrowed_card_is_not_a_target_of_its_own_trash_icon() -> None:
    # Replacement Eyes: "Trash a card -> draw a card". The black trash icon
    # takes a card "from your hand, discard pile, or in play" [Main p. 20];
    # the borrowed Row card is in none of them (OQ-054), while Usurp, played
    # from the hand, is in play.
    owner = _owner((USURP, DAGGER))
    grafted = _usurp(_state(owner, REPLACEMENT_EYES), "arrakeen", REPLACEMENT_EYES)
    targets = _trash_targets(legal_agent_card_trash_actions(_switch(grafted), 0))
    assert REPLACEMENT_EYES not in targets
    assert {USURP, DAGGER} <= targets


def test_desert_tactics_does_not_offer_the_borrowed_card() -> None:
    # Desert Tactics' optional trash [Main p. 20] on a Usurp turn that
    # borrowed Stilgar, The Devoted for its Fremen icon.
    owner = _owner((USURP, DAGGER))
    grafted = _usurp(_state(owner, STILGAR_DEVOTED), "desert_tactics", STILGAR_DEVOTED)
    targets = _trash_targets(legal_desert_tactics_actions(grafted, 0))
    assert STILGAR_DEVOTED not in targets
    assert {USURP, DAGGER} <= targets


def test_an_optional_trash_frame_does_not_offer_the_borrowed_card() -> None:
    owner = _owner((USURP, DAGGER))
    grafted = _usurp(_state(owner, REPLACEMENT_EYES), "arrakeen", REPLACEMENT_EYES)
    pushed = grafted.push_decision(optional_trash_frame(0, "test"))
    targets = _trash_targets(legal_optional_trash_actions(pushed, 0))
    assert REPLACEMENT_EYES not in targets
    assert {USURP, DAGGER} <= targets


@pytest.mark.parametrize(
    ("revealed", "with_borrowed", "without_borrowed"),
    [
        # Chani, Clever Tactician: "Fremen Bond: 2 Persuasion"; only the
        # borrowed Desert Survival would be the other Fremen card.
        (CHANI, 2, 0),
        # Stilgar, The Devoted: "2 Persuasion for each Fremen card you have
        # in play (including this one)".
        (STILGAR_DEVOTED, 4, 2),
    ],
)
def test_a_borrowed_fremen_card_counts_for_no_reveal_bond_or_count(
    revealed: str, with_borrowed: int, without_borrowed: int
) -> None:
    # Not reachable in a game: the borrowed card is trashed when its Agent
    # turn ends (``finish_agent_turn``), before any Reveal, and Round Start
    # clears the mark. The Reveal still reads only the cards that count as
    # in play, so a borrowed card would neither be the other card of a Fremen
    # Bond [Main p. 20] nor add to an in-play count (OQ-054).
    seat = PlayerState(player_id=0, hand=(revealed,), in_play=(DESERT_SURVIVAL,))
    reveal = DomainAction(action_id="reveal_turn", actor=0)

    def persuasion(owner: PlayerState) -> int:
        state = GameState(
            config=RulesetConfig(),
            seed=1,
            phase=GamePhase.PLAYER_TURNS,
            round_number=1,
            players=(owner, *(PlayerState(player_id=other) for other in range(1, 4))),
            decision_stack=(
                DecisionFrame(
                    kind="turn",
                    frame_id="round:1:turn:0",
                    decision=PlayerDecision(owner=0, prompt="Choose a turn"),
                ),
            ),
        )
        revealed_state = begin_reveal_turn(state, reveal).state
        value = dict(revealed_state.decision_stack[-1].context)["persuasion"]
        assert isinstance(value, int)
        return value

    assert persuasion(seat) == with_borrowed
    borrowed = replace(seat, usurped_row_card_id=DESERT_SURVIVAL)
    assert persuasion(borrowed) == without_borrowed
