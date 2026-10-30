"""Ix Discard costs reuse the hand-card cost and public discard transition.

Card values: Steam attribute table, screen pieces and English log strings.
Rules: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2], and its
OQ-071 application: costs need a live reward, including a cost-fed draw.
"""

from dataclasses import replace
from types import MappingProxyType

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising import agent_abilities
from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    HasAlliance,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    intrigue_card_for_instance,
)
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    Influence,
)
from dune_imperium.core.engine import IllegalActionError, RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import observe_state
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
TRUTHSAYER = "imperium:truthsayer:0"
PROBE = "intrigue:ixian_probe:0"
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(IX)


def _rows(state: GameState) -> tuple[DomainAction, ...]:
    rows = ENGINE.legal_actions(state, 0)
    for row in rows:
        assert CODEC.decode(CODEC.encode(row), 0) == row
    return rows


def _seat(state: GameState, **changes: object) -> GameState:
    owner = replace(state.players[0], **changes)  # type: ignore[arg-type]
    return replace(state, players=(owner, *state.players[1:]))


def _start() -> GameState:
    state = ENGINE.reset(IX, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    _rows(state)
    return state


def _do(state: GameState, action_id: str, **arguments: object) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(state)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            if not isinstance(ENGINE.current_decision(state), ChanceDecision):
                _rows(state)
            return RuleResult(state=state, events=tuple(events))


def _truthsayer(state: GameState) -> GameState:
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    return _do(state, "place_agent", space_id="wealth").state


def _probe(state: GameState) -> GameState:
    return _do(state, "play_intrigue", card_id=PROBE, option=0).state


def test_card_data_matches_the_app_and_only_joins_the_ix_decks() -> None:
    """Truthsayer: "Discard -> draw a card";
    Ixian Probe: "Discard, Discard -> draw 2 cards"."""
    card = IMPERIUM_CARDS_BY_ID["truthsayer"]
    assert card.play_data_complete
    assert (card.copies, card.acquisition_cost) == (2, 3)
    assert card.factions == (Faction.EMPEROR, Faction.BENE_GESSERIT)
    assert card.agent_icons == (
        AgentIcon.EMPEROR,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.LANDSRAAD,
    )
    assert (card.reveal_persuasion, card.reveal_strength) == (1, 1)
    probe = intrigue_card_for_instance(PROBE)
    assert probe.play_data_complete and probe.copies == 1
    assert probe.options[0].timing.value == "plot"
    (line,) = probe.options[0].sections
    assert line.costs == (DiscardFromHand(2),)
    assert line.rewards == (DrawPersonalCards(2),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        content = content_for(config)
        assert (TRUTHSAYER in content.imperium_deck_instance_ids) == config.rise_of_ix
        assert (PROBE in content.intrigue_deck_instance_ids) == config.rise_of_ix


def test_truthsayer_discards_the_payers_choice_publicly_before_drawing() -> None:
    """ "손의 카드 하나(Intrigue 아님)를 discard pile로" [Rise of Ix p. 7];
    Truthsayer: "draw a card"."""
    state = _start()
    paid, kept = state.players[0].hand[:2]
    top = state.players[0].deck[0]
    state = _seat(state, hand=(TRUTHSAYER, paid, kept), intrigue_cards=(PROBE,))
    state = _truthsayer(state)
    result = _do(state, "discard_agent_card", card_id=paid)
    owner = result.state.players[0]
    assert owner.hand == (kept, top)
    assert paid in owner.discard_pile
    assert owner.intrigue_cards == (PROBE,)
    assert TRUTHSAYER in owner.in_play
    assert paid in observe_state(result.state, 1).players[0].discard_pile
    event = next(event for event in result.events if event.kind == "card_discarded")
    assert event.visible_to is None and dict(event.payload)["card_id"] == paid


def test_truthsayer_does_not_offer_payment_with_no_hand_card() -> None:
    """ "내지 않으면 효과도 없다" [Rise of Ix p. 7].

    The played Truthsayer cannot pay itself.
    """
    state = _seat(_start(), hand=(TRUTHSAYER,), intrigue_cards=(PROBE,))
    state = _truthsayer(state)
    assert not any(
        row.action_id == "discard_agent_card" for row in ENGINE.whole_actions(state, 0)
    )
    assert state.players[0].hand == ()


def test_truthsayer_cost_can_be_left_unpaid() -> None:
    """ "손의 카드 하나(Intrigue 아님) -OR- 내지 않음" [Rise of Ix p. 7]."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _truthsayer(_seat(state, hand=(TRUTHSAYER, kept)))
    deck = state.players[0].deck
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    result = _do(state, "finish_agent_turn")
    assert result.state.players[0].hand == (kept,)
    assert result.state.players[0].deck == deck
    assert not any(event.kind == "cards_drawn" for event in result.events)


def test_truthsayer_reveals_for_one_persuasion_and_one_sword() -> None:
    """Truthsayer Reveal: "Persuasion 1 + 1 sword" (Steam screen pieces)."""
    state = _seat(_start(), hand=(TRUTHSAYER,))
    state = _do(state, "reveal_turn").state
    assert state.players[0].combat_strength == 0  # No Conflict troop [DI p. 11].
    context = dict(state.decision_stack[-1].context)
    assert context["persuasion"] == 1
    assert context["sword_strength"] == 1
    assert state.players[0].hand == ()


@pytest.mark.parametrize("hand_size", [0, 1])
def test_probe_requires_two_personal_hand_cards_even_when_intrigue_is_held(
    hand_size: int,
) -> None:
    """Ixian Probe: "Discard, Discard -> draw 2 cards";
    "Intrigue 아님" [Rise of Ix p. 7]."""
    state = _start()
    state = _seat(
        state,
        hand=state.players[0].hand[:hand_size],
        intrigue_cards=(PROBE, "intrigue:cull:0"),
    )
    _rows(state)
    assert not any(
        row.action_id == "play_intrigue" and dict(row.arguments).get("card_id") == PROBE
        for row in ENGINE.whole_actions(state, 0)
    )


def test_probe_pays_two_distinct_hand_cards_before_drawing_two() -> None:
    """Ixian Probe: "discarded [card2] and [card3] to draw 2 cards"."""
    state = _start()
    first, second, kept = state.players[0].hand[:3]
    deck = state.players[0].deck
    state = _probe(
        _seat(
            state, hand=(first, second, kept), intrigue_cards=(PROBE, "intrigue:cull:0")
        )
    )
    choices = ENGINE.whole_actions(state, 0)
    assert {dict(row.arguments)["card_id"] for row in choices} == {first, second, kept}
    first_result = _do(state, "choose_intrigue_discard", card_id=second)
    state = first_result.state
    assert state.players[0].hand == (first, kept)
    assert state.players[0].deck == deck
    assert not any(event.kind == "cards_drawn" for event in first_result.events)
    assert second in observe_state(state, 1).players[0].discard_pile
    assert {
        dict(row.arguments)["card_id"] for row in ENGINE.whole_actions(state, 0)
    } == {first, kept}
    with pytest.raises(IllegalActionError):
        ENGINE.apply(
            state,
            DomainAction(
                "choose_intrigue_discard", 0, (("card_id", "intrigue:cull:0"),)
            ),
        )
    result = _do(state, "choose_intrigue_discard", card_id=first)
    owner = result.state.players[0]
    assert owner.hand == (kept, *deck[:2])
    assert owner.discard_pile[-2:] == (second, first)
    assert owner.intrigue_cards == ("intrigue:cull:0",)
    assert PROBE in result.state.intrigue_discard


def test_probe_can_draw_the_cards_its_cost_just_discarded() -> None:
    """OQ-071: "discard한 카드는 섞여 다시 뽑히고"; Ixian Probe: "draw 2 cards"."""
    state = _start()
    cards = state.players[0].hand[:2]
    state = _probe(
        _seat(state, hand=cards, deck=(), discard_pile=(), intrigue_cards=(PROBE,))
    )
    state = _do(state, "choose_intrigue_discard", card_id=cards[0]).state
    state = _do(state, "choose_intrigue_discard", card_id=cards[1]).state
    chance = ChanceResolver(seed=7)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    _rows(state)
    assert set(state.players[0].hand) == set(cards)
    assert state.players[0].discard_pile == ()


def test_discard_cost_line_is_not_offered_when_its_reward_is_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다" (Ix 7, OQ-071).

    A synthetic Intrigue line tests the reusable cost's live-reward guard;
    Probe's own draw is always live because its cost feeds the discard pile.
    """
    entry = intrigue_card_for_instance(PROBE)
    option = replace(
        entry.options[0],
        sections=(
            EffectSection(
                costs=(DiscardFromHand(2),),
                rewards=(GainInfluence(factions=(Faction.EMPEROR,)),),
            ),
        ),
    )
    monkeypatch.setitem(
        INTRIGUE_CARDS_BY_INSTANCE, PROBE, replace(entry, options=(option,))
    )
    state = _seat(_start(), intrigue_cards=(PROBE,), influence=Influence(emperor=6))
    _rows(state)
    assert not any(
        row.action_id == "play_intrigue" and dict(row.arguments).get("card_id") == PROBE
        for row in ENGINE.whole_actions(state, 0)
    )
    live = _seat(state, influence=Influence(emperor=5))
    _rows(live)
    assert any(
        row.action_id == "play_intrigue" and dict(row.arguments).get("card_id") == PROBE
        for row in ENGINE.whole_actions(live, 0)
    )
    short = _seat(live, hand=live.players[0].hand[:1])
    _rows(short)
    assert not any(
        row.action_id == "play_intrigue" and dict(row.arguments).get("card_id") == PROBE
        for row in ENGINE.whole_actions(short, 0)
    )


# --- The Discard cost in other Agent boxes (P4d Unload brief, item 0) ---------
#
# Hand-built Agent boxes stand in for the Ix cards that print them (their own
# card briefs transcribe them): Truthsayer's box record is replaced for the
# test, so the card is played as usual and only its arrow differs.


def _box(monkeypatch: pytest.MonkeyPatch, *lines: EffectSection) -> None:
    table = dict(agent_abilities.AGENT_BOX_ABILITIES)
    table[PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE] = Ability(
        timing=AbilityTiming.AGENT_BOX, sections=lines, mark=AbilityMark.OPTIONAL
    )
    monkeypatch.setattr(agent_abilities, "AGENT_BOX_ABILITIES", MappingProxyType(table))


def _discard_rows(state: GameState) -> set[DomainAction]:
    _rows(state)
    return {
        row
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id in ("discard_agent_card", "decline_agent_card_discard")
    }


def test_a_discard_arrow_pays_spice_and_water_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Satellite Ban: "Discard -> 1 spice, 1 water" (app screen pieces); the
    Discard icon costs one hand card [Rise of Ix p. 7]."""
    _box(
        monkeypatch,
        EffectSection(
            costs=(DiscardFromHand(),), rewards=(GainResources(spice=1, water=1),)
        ),
    )
    state = _start()
    paid, kept = state.players[0].hand[:2]
    state = _truthsayer(_seat(state, hand=(TRUTHSAYER, paid, kept)))
    before = state.players[0].resources
    owner = _do(state, "discard_agent_card", card_id=paid).state.players[0]
    assert (owner.resources.spice, owner.resources.water) == (
        before.spice + 1,
        before.water + 1,
    )
    assert owner.hand == (kept,) and owner.discard_pile[-1] == paid


def test_an_alliance_discard_arrow_needs_the_alliance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A discard arrow under "Fremen Alliance:" (a hand-built shape; no Ix card
    prints it -- Spice Trader's gate is an Influence threshold, see
    test_ix_imperium_d). "내지 않으면 효과도 없다" [Rise of Ix p. 7]; the
    condition is judged when the cost is paid (OQ-028), so without the
    Alliance no card pays it (an unused optional arrow lapses at the turn's
    end, OQ-095 (2))."""
    _box(
        monkeypatch,
        EffectSection(
            costs=(DiscardFromHand(),),
            rewards=(GainResources(spice=2),),
            condition=HasAlliance(Faction.FREMEN),
        ),
    )
    state = _start()
    paid, kept = state.players[0].hand[:2]
    played = _truthsayer(_seat(state, hand=(TRUTHSAYER, paid, kept)))
    assert _discard_rows(played) == set()
    allied = _truthsayer(
        _seat(
            state,
            hand=(TRUTHSAYER, paid, kept),
            influence=Influence(fremen=4),
            alliance_faction_ids=("fremen",),
        )
    )
    assert {dict(row.arguments).get("card_id") for row in _discard_rows(allied)} == {
        paid,
        kept,
    }
    spice = allied.players[0].resources.spice
    owner = _do(allied, "discard_agent_card", card_id=paid).state.players[0]
    assert owner.resources.spice == spice + 2


def test_two_discard_icons_take_two_hand_cards_before_the_reward(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ix-Guild Compact: "Discard, Discard -> ..." (app screen pieces): each
    Discard icon costs one hand card, and an unpaid arrow gives nothing
    [Rise of Ix p. 7]. The first pick waits in hand (as Corrinth City's),
    the second discards both. Its dreadnought is not wired here, so 2 spice
    stands in for it."""
    _box(
        monkeypatch,
        EffectSection(costs=(DiscardFromHand(2),), rewards=(GainResources(spice=2),)),
    )
    state = _start()
    first, second, kept = state.players[0].hand[:3]
    short = _truthsayer(_seat(state, hand=(TRUTHSAYER, first)))
    assert _discard_rows(short) == set()
    state = _truthsayer(_seat(state, hand=(TRUTHSAYER, first, second, kept)))
    spice = state.players[0].resources.spice
    picked = _do(state, "discard_agent_card", card_id=first)
    owner = picked.state.players[0]
    assert owner.hand == (first, second, kept)
    assert owner.resources.spice == spice
    assert first not in observe_state(picked.state, 1).players[0].discard_pile
    assert not any(event.kind == "card_discarded" for event in picked.events)
    assert {
        dict(row.arguments).get("card_id") for row in _discard_rows(picked.state)
    } == {second, kept}
    paid = _do(picked.state, "discard_agent_card", card_id=kept)
    owner = paid.state.players[0]
    assert owner.hand == (second,)
    assert owner.discard_pile[-2:] == (first, kept)
    assert owner.resources.spice == spice + 2
    assert [
        dict(event.payload)["card_id"]
        for event in paid.events
        if event.kind == "card_discarded"
    ] == [first, kept]


def test_two_discard_icons_can_still_be_left_unpaid_after_the_first_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "손의 카드 하나(Intrigue 아님) -OR- 내지 않음" [Rise of Ix p. 7]:
    nothing is paid before the second pick, and the turn can end there."""
    _box(
        monkeypatch,
        EffectSection(costs=(DiscardFromHand(2),), rewards=(GainResources(spice=2),)),
    )
    state = _start()
    first, second = state.players[0].hand[:2]
    state = _truthsayer(_seat(state, hand=(TRUTHSAYER, first, second)))
    state = _do(state, "discard_agent_card", card_id=first).state
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    result = _do(state, "finish_agent_turn")
    owner = result.state.players[0]
    assert owner.hand == (first, second)
    assert not any(event.kind == "card_discarded" for event in result.events)
