"""Rise of Ix Imperium batch F: the last eight Imperium cards (stage P4d).

Card values: the Steam app's attribute table, per-card UI pieces and English
text (4.1.2.1808, dad97e20). Rules: docs/rules/rise-of-ix.md -- each test's
docstring quotes the line it applies. Every offered row round-trips through
``ActionCodec``.
"""

from dataclasses import replace

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import ix_pending_of, known_intrigue_places
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.simulation.invariants import check_observation_privacy

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
CODEC = ActionCodec(IX)
WATER_PEDDLER = "imperium:water_peddler:0"
UNLOAD_ROW = "resolve_unload_icon"


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert CODEC.decode(CODEC.encode(row), seat) == row
    return rows


def _give(state: GameState, seat: int, **zones: object) -> GameState:
    """Put the named cards in ``seat``'s zones, taking them out of the
    Imperium deck and Row and of every seat's zones first (seeded decks);
    other keyword arguments set the seat's fields."""

    named = {
        card
        for cards in zones.values()
        if isinstance(cards, tuple)
        for card in cards
        if isinstance(card, str)
    }
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _start(seed: int = 3) -> GameState:
    state = ENGINE.reset(IX, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    _rows(state)
    return state


def _whole(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> DomainAction | None:
    return next(
        (
            row
            for row in ENGINE.whole_actions(state, seat)
            if row.action_id == action_id
            and all(
                dict(row.arguments).get(key) == value
                for key, value in arguments.items()
            )
        ),
        None,
    )


def _offered(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> bool:
    _rows(state, seat)
    return _whole(state, action_id, seat, **arguments) is not None


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = _whole(state, action_id, seat, **arguments)
    assert whole is not None, (action_id, arguments)
    events: list[GameEvent] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            if not isinstance(ENGINE.current_decision(state), ChanceDecision):
                _rows(state, seat)
            return RuleResult(state=state, events=tuple(events))


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


# --- Guild Chief Administrator ----------------------------------------------

GCA = "imperium:guild_chief_administrator:0"
_ADVANCE = "advance_reveal_freighter"
_RECALL = "recall_reveal_freighter"


def _placed(state: GameState, *hand: str) -> GameState:
    """Guild Chief Administrator sent to Arrakeen (its City icon), its box
    pending; ``hand`` is the rest of the hand."""

    state = _give(state, 0, hand=(GCA, *hand))
    state = _do(state, "choose_agent_card", card_id=GCA).state
    return _do(state, "place_agent", space_id="arrakeen").state


def _space_done(state: GameState) -> GameState:
    """Arrakeen's troop and card (the visited space's own effects)."""

    state = _do(state, "resolve_board_effect", effect="troops").state
    return _do(state, "resolve_board_effect", effect="cards").state


def test_guild_chief_administrator_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Spacing Guild, cost 4, one copy; Spacing Guild, City and
    Spice Trade icons; Reveal 1 Persuasion. Screen pieces: Agent "[Discard] ->
    [Trash a card]"; Reveal "[1 Persuasion] [Freighter]"."""
    entry = IMPERIUM_CARDS_BY_ID["guild_chief_administrator"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.SPACING_GUILD,)
    assert entry.agent_icons == (
        AgentIcon.SPACING_GUILD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_DISCARD_TO_TRASH_A_CARD
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_MOVE_FREIGHTER,
    )
    assert entry.play_data_complete
    assert GCA in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert GCA not in content_for(config).imperium_deck_instance_ids


def test_guild_chief_administrator_card_text() -> None:
    """The box's discard arrow and the Reveal's Freighter, in both languages."""
    entry = IMPERIUM_CARDS_BY_ID["guild_chief_administrator"]
    english = personal_card_text(entry)
    korean = personal_card_text_ko(entry)
    assert "Agent: You may discard a card → You may trash a card" in english
    assert any(
        "You may move your Freighter up one space or recall it" in line
        for line in english
    )
    assert any("운송 트랙에서 한 칸 위로 또는 회수 가능" in line for line in korean)
    assert len(english) == len(korean)


def test_the_discard_pays_for_a_trash_of_any_card_including_the_discarded_one() -> None:
    """ "Discard 아이콘. 손의 카드 하나(Intrigue 아님)를 discard pile로. 대개
    비용이고, 내지 않으면 효과도 없다" (rise-of-ix.md 7, [Rise of Ix p. 7]); the
    trash takes a card "from hand, discard or play" (``TrashPersonalCard``):
    the card just discarded is in the discard pile, so it may be trashed."""
    state = _start()
    paid, kept = state.players[0].hand[:2]
    state = _placed(state, paid, kept)
    discarded = _do(state, "discard_agent_card", card_id=paid).state
    owner = discarded.players[0]
    assert paid in owner.discard_pile and paid not in owner.hand
    targets = {
        dict(row.arguments)["card_id"]
        for row in ENGINE.whole_actions(discarded, 0)
        if row.action_id == "trash_optional_card"
    }
    assert {paid, kept, GCA} <= targets
    trashed = _do(discarded, "trash_optional_card", card_id=paid).state
    assert paid in trashed.players[0].trashed
    assert paid not in trashed.players[0].discard_pile
    assert not _offered(trashed, "trash_optional_card")


def test_the_trash_stays_optional_once_the_discard_is_paid() -> None:
    """ "검은색 trash 아이콘으로 trash하는 효과는 선택이다" (uprising-systems.md,
    [FAQ p. 3]): no refusal row; the turn ends with it unused and it lapses
    (OQ-095 (2))."""
    state = _start()
    paid = state.players[0].hand[0]
    state = _placed(state, paid)
    state = _do(state, "discard_agent_card", card_id=paid).state
    state = _space_done(state)
    assert not _offered(state, "decline_optional_trash")
    assert _offered(state, "trash_optional_card")
    finished = _do(state, "finish_agent_turn")
    assert "optional_trash_lapsed" in _kinds(finished.events)
    assert paid in finished.state.players[0].discard_pile
    assert not finished.state.players[0].trashed


def test_the_discard_can_be_left_unpaid_and_needs_a_hand_card() -> None:
    """ "Discard 비용 | 낸 좌석 | 손의 카드 하나(Intrigue 아님) -OR- 내지 않음"
    (rise-of-ix.md 14): an optional arrow offers no refusal in its owner's
    turn and lapses at the turn's end (OQ-095 (2)) with nothing trashed; with
    no other hand card no discard is offered (the played card cannot pay
    itself)."""
    state = _start()
    paid = state.players[0].hand[0]
    state = _space_done(_placed(state, paid))
    assert not _offered(state, "decline_agent_card_discard")
    assert not _offered(state, "trash_optional_card")
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)
    assert paid in finished.state.players[0].hand
    assert not finished.state.players[0].trashed

    alone = _placed(_start())
    assert not _offered(alone, "discard_agent_card")


def test_a_discarded_unload_card_pays_before_the_trash_and_again_if_trashed() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한
    뒤 오른쪽으로 간다" and "trash할 때 얻는다" (rise-of-ix.md 7, [Rise of Ix
    p. 7]): Water Peddler's water comes with the discard, and trashing it
    from the discard pile gives the box again."""
    state = _start()
    state = _placed(state, WATER_PEDDLER)
    water = state.players[0].resources.water
    discarded = _do(state, "discard_agent_card", card_id=WATER_PEDDLER).state
    assert discarded.players[0].resources.water == water + 1
    assert not _offered(discarded, UNLOAD_ROW)
    trashed = _do(discarded, "trash_optional_card", card_id=WATER_PEDDLER)
    assert "card_unloaded" in _kinds(trashed.events)
    again = _do(trashed.state, UNLOAD_ROW, card_id=WATER_PEDDLER, effect="water")
    assert again.state.players[0].resources.water == water + 2


def _revealed(state: GameState, space: int) -> GameState:
    state = _give(state, 0, hand=(GCA,), freighter_space=space)
    return _do(state, "reveal_turn").state


def _freighter_rows(state: GameState) -> set[str]:
    _rows(state)
    return {
        row.action_id
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id in (_ADVANCE, _RECALL)
    }


def test_the_reveal_freighter_moves_up_from_the_bottom_only() -> None:
    """ "Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수 있다
    ("may"): 한 칸 위로(맨 위면 불가) 또는 맨 아래로 회수" (rise-of-ix.md 5,
    [Rise of Ix p. 5]): from the bottom a recall moves nothing, so only the
    move up; the Reveal's 1 Persuasion beside it."""
    state = _revealed(_start(), 0)
    assert dict(state.decision_stack[-1].context)["persuasion"] == 1
    assert _freighter_rows(state) == {_ADVANCE}
    moved = _do(state, _ADVANCE).state
    assert moved.players[0].freighter_space == 1
    assert _freighter_rows(moved) == set()


def test_the_reveal_freighter_recall_owes_its_rewards_on_the_reveal() -> None:
    """ "회수하면 지금 칸과 그 아래 모든 칸의 보상을 원하는 순서로 받는다"
    (rise-of-ix.md 5): from space 2 both moves; the recall owes space 1's
    choice and space 2's recruit and Influence as rows of the Reveal, which
    hold its end until taken."""
    state = _revealed(_start(), 2)
    assert _freighter_rows(state) == {_ADVANCE, _RECALL}
    recalled = _do(state, _RECALL)
    assert "freighter_recalled" in _kinds(recalled.events)
    state = recalled.state
    assert state.players[0].freighter_space == 0
    assert ix_pending_of(state, 0).shipping_rewards == (1, 2)
    assert _freighter_rows(state) == set()
    assert not _offered(state, "finish_reveal")
    spice = state.players[0].resources.spice
    state = _do(state, "resolve_shipping_reward", effect="spice").state
    assert state.players[0].resources.spice == spice + 2
    state = _do(state, "resolve_shipping_reward", effect="recruit").state
    state = _do(
        state, "resolve_shipping_reward", effect="influence", faction="emperor"
    ).state
    assert ix_pending_of(state, 0).shipping_rewards == ()
    assert _offered(state, "finish_reveal")


def test_the_reveal_freighter_has_no_refusal_and_lapses_with_the_reveal() -> None:
    """ "you may move" (rise-of-ix.md 14, "Freighter 아이콘 하나 | 받은 좌석 |
    위로 한 칸 -OR- 회수 -OR- 쓰지 않음"): an optional Reveal choice offers no
    refusal and lapses when the Reveal ends (OQ-095 (7) addition)."""
    state = _revealed(_start(), 1)
    assert not any(
        row.action_id.startswith("decline_") for row in ENGINE.whole_actions(state, 0)
    )
    assert _offered(state, "finish_reveal")
    finished = _do(state, "finish_reveal")
    assert "reveal_choice_lapsed" in _kinds(finished.events)
    assert finished.state.players[0].freighter_space == 1


def test_the_reveal_freighter_rows_are_in_the_ix_catalog_only() -> None:
    """The two moves are shown by effect rows naming the card that prints them
    (``effect_steps``), in the original game with Rise of Ix only [Rise of Ix
    p. 2]."""
    state = _revealed(_start(), 1)
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "guild_chief_administrator"
    ]
    assert {(row.action_id, dict(row.arguments).get("icon")) for row in rows} == {
        ("advance", "freighter"),
        ("collect", "freighter"),
    }
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        template = ActionTemplate(row.action_id, row.arguments)
        assert template in set(CODEC.catalog) - plain
    assert not any(
        dict(template.arguments).get("printed") == "guild_chief_administrator"
        for template in ActionCodec(RulesetConfig()).catalog
    )


# --- Negotiated Withdrawal -----------------------------------------------------

WITHDRAWAL = "imperium:negotiated_withdrawal:0"
_UNIT_RETREAT = "retreat_reveal_units_for_influence"


def _withdrawal(
    state: GameState, *, troops: int = 0, dreadnoughts: int = 0, swords: int = 0
) -> GameState:
    """Negotiated Withdrawal revealed with ``troops`` and ``dreadnoughts`` in
    the Conflict, at the strength the engine keeps for them (2 a troop, 3 a
    dreadnought)."""

    owner = state.players[0]
    from_garrison = min(troops, owner.troops_garrison)
    state = _give(
        state,
        0,
        hand=(WITHDRAWAL,),
        troops_supply=owner.troops_supply - (troops - from_garrison),
        troops_garrison=owner.troops_garrison - from_garrison,
        troops_conflict=troops,
        dreadnoughts_supply=2 - dreadnoughts,
        dreadnoughts_conflict=dreadnoughts,
        combat_strength=2 * troops + 3 * dreadnoughts,
    )
    return _do(state, "reveal_turn").state


def _unit_rows(state: GameState) -> list[dict[str, object]]:
    _rows(state)
    return [
        dict(row.arguments)
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == _UNIT_RETREAT
    ]


def test_negotiated_withdrawal_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: no Faction, cost 4, two copies; Landsraad, City and Spice
    Trade icons and no Agent box; AcquireEffectList Troop; Reveal 2
    Persuasion. Text: "Retreat three of your units -> [Influence with any
    Faction]"."""
    entry = IMPERIUM_CARDS_BY_ID["negotiated_withdrawal"]
    assert (entry.copies, entry.acquisition_cost) == (2, 4)
    assert entry.factions == ()
    assert entry.agent_icons == (
        AgentIcon.LANDSRAAD,
        AgentIcon.CITY,
        AgentIcon.SPICE_TRADE,
    )
    assert entry.agent_effect is None
    assert entry.acquisition_effect is PersonalCardAcquisitionEffect.RECRUIT_ONE_TROOP
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.reveal_choice_effects == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_THREE_UNITS_FOR_INFLUENCE,
    )
    assert entry.play_data_complete
    ids = content_for(IX).imperium_deck_instance_ids
    assert {WITHDRAWAL, "imperium:negotiated_withdrawal:1"} <= set(ids)
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert WITHDRAWAL not in content_for(config).imperium_deck_instance_ids
    english = personal_card_text(entry)
    korean = personal_card_text_ko(entry)
    assert any("You may retreat 3 of your units" in line for line in english)
    assert any("부대 3" in line for line in korean)
    assert len(english) == len(korean)


def test_three_troops_retreat_for_an_influence_of_the_owners_choice() -> None:
    """ "Retreat three of your units -> [Influence with any Faction]": an
    optional arrow [FAQ p. 3]; the troops go back to the garrison with their
    strength (2 each [Main p. 12]), then one Influence."""
    state = _withdrawal(_start(), troops=4)
    assert dict(state.decision_stack[-1].context)["persuasion"] == 2
    rows = _unit_rows(state)
    assert [row["faction"] for row in rows] == [faction.value for faction in Faction]
    assert all(set(row) == {"count", "faction"} for row in rows)
    before = state.players[0]
    result = _do(state, _UNIT_RETREAT, faction="fremen")
    owner = result.state.players[0]
    assert (owner.troops_conflict, owner.troops_garrison) == (
        1,
        before.troops_garrison + 3,
    )
    assert owner.troops_supply == before.troops_supply
    assert owner.combat_strength == before.combat_strength - 6
    assert owner.influence.fremen == before.influence.fremen + 1
    assert "troops_retreated" in _kinds(result.events)
    assert _unit_rows(result.state) == []


def test_a_dreadnought_is_one_of_the_three_units() -> None:
    """ "unit | ... Negotiated Withdrawal(retreat three units) ... | 예"
    (rise-of-ix.md 6, [Rise of Ix p. 6]): with two troops and a dreadnought
    the three may be all of them; a seat left with no unit keeps no strength
    [Main p. 12]."""
    state = _withdrawal(_start(), troops=2, dreadnoughts=1)
    rows = _unit_rows(state)
    assert {row.get("dreadnoughts") for row in rows} == {1}
    result = _do(state, _UNIT_RETREAT, dreadnoughts=1, faction="emperor")
    owner = result.state.players[0]
    assert (owner.troops_conflict, owner.dreadnoughts_conflict) == (0, 0)
    assert owner.dreadnoughts_garrison == 1
    assert owner.combat_strength == 0
    assert "dreadnought_retreated" in _kinds(result.events)


def test_two_dreadnoughts_and_troops_give_every_mix() -> None:
    """The owner picks which three units go (a dreadnought or a troop is
    each a unit [Rise of Ix p. 6])."""
    state = _withdrawal(_start(), troops=3, dreadnoughts=2)
    mixes = {row.get("dreadnoughts", 0) for row in _unit_rows(state)}
    assert mixes == {0, 1, 2}
    result = _do(state, _UNIT_RETREAT, dreadnoughts=2, faction="bene_gesserit")
    owner = result.state.players[0]
    assert (owner.troops_conflict, owner.dreadnoughts_conflict) == (2, 0)
    assert owner.combat_strength == 4


def test_fewer_than_three_units_offer_nothing_and_the_arrow_lapses() -> None:
    """The cost is three units: with two it cannot be paid, so the arrow is
    not offered (OQ-071) and lapses unused when the Reveal ends (OQ-095 (7)
    addition)."""
    state = _withdrawal(_start(), troops=1, dreadnoughts=1)
    assert _unit_rows(state) == []
    finished = _do(state, "finish_reveal")
    assert "reveal_choice_lapsed" in _kinds(finished.events)


def test_no_row_while_every_cube_is_at_the_top() -> None:
    """A gain on a cube at the top is lost (OQ-060), so an arrow buying only
    that is not offered (OQ-071)."""
    state = _start()
    owner = state.players[0]
    top = replace(
        owner.influence, emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6
    )
    state = _give(state, 0, influence=top)
    state = _withdrawal(state, troops=3)
    assert _unit_rows(state) == []


def _in_row(state: GameState, instance_id: str) -> GameState:
    """``instance_id`` in the Imperium Row's first slot, out of the deck."""

    state = _give(state, 0)
    deck = tuple(card for card in state.imperium_deck if card != instance_id)
    row = tuple(card for card in state.imperium_row if card != instance_id)
    return replace(state, imperium_deck=deck, imperium_row=(instance_id, *row[1:]))


def _with_persuasion(state: GameState, persuasion: int) -> GameState:
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = persuasion
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def test_negotiated_withdrawal_recruits_a_troop_when_acquired() -> None:
    """App AcquireEffectList Troop: "When you acquire a card, you immediately
    resolve its acquire box" [DI p. 16] -- one troop to the garrison."""
    state = _in_row(_start(), WITHDRAWAL)
    state = _with_persuasion(_do(state, "reveal_turn").state, 4)
    garrison = state.players[0].troops_garrison
    result = _do(state, "acquire_imperium", instance_id=WITHDRAWAL)
    owner = result.state.players[0]
    assert WITHDRAWAL in owner.discard_pile
    assert owner.troops_garrison == garrison + 1


def test_the_unit_retreat_rows_are_in_the_ix_catalog_only() -> None:
    """The arrow's rows (the Faction row, the unit mix riding on it) are in
    the original game's catalog with Rise of Ix alone [Rise of Ix p. 2]."""
    state = _withdrawal(_start(), troops=2, dreadnoughts=1)
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "negotiated_withdrawal"
    ]
    assert rows
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        assert (
            ActionTemplate(row.action_id, row.arguments) in set(CODEC.catalog) - plain
        )
    assert not any(
        dict(template.arguments).get("printed") == "negotiated_withdrawal"
        for template in ActionCodec(RulesetConfig()).catalog
    )


# --- Desert Ambush --------------------------------------------------------------

AMBUSH = "imperium:desert_ambush:0"
_ENEMY_RETREAT = "retreat_opponent_troop"


def _ambush(state: GameState, *, garrison: int = 3, dreadnoughts: int = 0) -> GameState:
    """Desert Ambush sent to Imperial Basin (its Spice Trade icon, a Combat
    space); seat 1 has two troops and a dreadnought in the Conflict."""

    rival = state.players[1]
    state = _give(
        state,
        1,
        troops_garrison=rival.troops_garrison - 2,
        troops_conflict=2,
        dreadnoughts_supply=1,
        dreadnoughts_conflict=1,
        combat_strength=7,
    )
    owner = state.players[0]
    state = _give(
        state,
        0,
        hand=(AMBUSH,),
        troops_supply=owner.troops_supply + owner.troops_garrison - garrison,
        troops_garrison=garrison,
        dreadnoughts_supply=2 - dreadnoughts,
        dreadnoughts_garrison=dreadnoughts,
    )
    state = _do(state, "choose_agent_card", card_id=AMBUSH).state
    return _do(state, "place_agent", space_id="imperial_basin").state


def _enemy_rows(state: GameState) -> list[dict[str, object]]:
    _rows(state)
    return [
        dict(row.arguments)
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == _ENEMY_RETREAT
    ]


def test_desert_ambush_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Fremen, cost 3, one copy; the Spice Trade icon; Reveal 1
    Persuasion, 1 sword. Text: "For each troop you deploy this turn, you may
    force an enemy unit to retreat." """
    entry = IMPERIUM_CARDS_BY_ID["desert_ambush"]
    assert (entry.copies, entry.acquisition_cost) == (1, 3)
    assert entry.factions == (Faction.FREMEN,)
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_FORCE_ENEMY_UNIT_RETREAT_FOR_EACH_TROOP_DEPLOYED
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert AMBUSH in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert AMBUSH not in content_for(config).imperium_deck_instance_ids
    assert (
        "Agent: For each troop you deploy this turn, you may force an enemy unit"
        " to retreat" in personal_card_text(entry)
    )
    assert len(personal_card_text(entry)) == len(personal_card_text_ko(entry))


def test_each_deployed_troop_buys_one_retreat_of_an_enemy_unit() -> None:
    """ "For each troop you deploy this turn, you may force an enemy unit to
    retreat"; "unit | ... Desert Ambush(enemy unit) | 예" (rise-of-ix.md 6,
    [Rise of Ix p. 6]): before a deployment nothing; with one troop deployed
    one retreat, of a troop or a dreadnought, the player of the card picking
    it (rise-of-ix.md 9.3)."""
    state = _ambush(_start())
    assert _enemy_rows(state) == []
    state = _do(state, "deploy_troops", count=1).state
    assert {tuple(sorted(row.items())) for row in _enemy_rows(state)} == {
        (("player", 1),),
        (("dreadnoughts", 1), ("player", 1)),
    }
    result = _do(state, _ENEMY_RETREAT, player=1, dreadnoughts=1)
    rival = result.state.players[1]
    assert (rival.dreadnoughts_conflict, rival.dreadnoughts_garrison) == (0, 1)
    assert rival.combat_strength == 4
    assert "dreadnought_retreated" in _kinds(result.events)
    assert _enemy_rows(result.state) == []
    again = _do(result.state, "deploy_troops", count=1).state
    assert _enemy_rows(again) == [{"player": 1}]
    done = _do(again, _ENEMY_RETREAT, player=1).state
    assert done.players[1].troops_conflict == 1
    assert _enemy_rows(done) == []


def test_a_retreat_bought_holds_the_deployment_it_counted() -> None:
    """ "이번 turn의 배치 수를 조건으로 이미 사용한 효과가 있으면, 배치 수를 그
    조건(최소 수) 아래로 내리는 회수는 허용하지 않는다" (OQ-029 (3)): with two
    troops deployed and one retreat bought, only one troop may be withdrawn."""
    state = _ambush(_start())
    state = _do(state, "deploy_troops", count=2).state
    assert len(_enemy_rows(state)) == 2
    state = _do(state, _ENEMY_RETREAT, player=1).state
    withdrawals = {
        dict(row.arguments)["count"]
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == "withdraw_troops"
    }
    assert withdrawals == {1}
    withdrawn = _do(state, "withdraw_troops", count=1).state
    assert _enemy_rows(withdrawn) == []


def test_a_withdrawn_troop_counts_once_when_deployed_again() -> None:
    """ "같은 큐브를 retreat했다 다시 배치해도 두 번 세지 않음" (rise-of-ix.md
    15, OQ-029): a troop deployed, withdrawn and deployed again buys one
    retreat."""
    state = _ambush(_start())
    state = _do(state, "deploy_troops", count=1).state
    state = _do(state, "withdraw_troops", count=1).state
    state = _do(state, "deploy_troops", count=1).state
    state = _do(state, _ENEMY_RETREAT, player=1).state
    assert _enemy_rows(state) == []


def test_a_deployed_dreadnought_is_no_troop() -> None:
    """ "원판 카드의 "troop"은 유닛을 뜻하지 않아 dreadnought에 작용하지 않는다"
    and the table's "troop recruit/잃기/retreat/배치 | ... | 아니오"
    (rise-of-ix.md 6, [Rise of Ix p. 6]): deploying a dreadnought buys no
    retreat."""
    state = _ambush(_start(), dreadnoughts=1)
    state = _do(state, "deploy_dreadnoughts", count=1).state
    assert state.players[0].dreadnoughts_conflict == 1
    assert _enemy_rows(state) == []


def test_unused_retreats_lapse_with_the_turn() -> None:
    """ "you may force": an optional box offers no refusal and the turn's end
    lapses it (OQ-095 (2))."""
    state = _ambush(_start())
    state = _do(state, "deploy_troops", count=1).state
    state = _do(state, "harvest_maker_spice", space_id="imperial_basin").state
    assert not any(
        row.action_id.startswith("decline_") for row in ENGINE.whole_actions(state, 0)
    )
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)
    assert finished.state.players[1].troops_conflict == 2


def test_the_enemy_unit_rows_are_in_the_ix_catalog_only() -> None:
    """A dreadnought's row is in the original game's catalog with Rise of Ix
    alone [Rise of Ix p. 2]."""
    state = _ambush(_start())
    state = _do(state, "deploy_troops", count=1).state
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "desert_ambush"
    ]
    assert rows
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        template = ActionTemplate(row.action_id, row.arguments)
        assert template in set(CODEC.catalog) - plain


# --- Full-Scale Assault ---------------------------------------------------------

ASSAULT = "imperium:full_scale_assault:0"
_ACQUIRE_ICON = "resolve_acquire_icon"


def _assault_revealed(
    state: GameState, *, troops: int = 1, dreadnoughts: int = 0, garrisoned: int = 0
) -> GameState:
    """Full-Scale Assault revealed with ``troops`` and ``dreadnoughts`` in
    the Conflict (2 strength a troop, 3 a dreadnought)."""

    owner = state.players[0]
    state = _give(
        state,
        0,
        hand=(ASSAULT,),
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=troops,
        dreadnoughts_supply=2 - dreadnoughts - garrisoned,
        dreadnoughts_garrison=garrisoned,
        dreadnoughts_conflict=dreadnoughts,
        combat_strength=2 * troops + 3 * dreadnoughts,
    )
    return _do(state, "reveal_turn").state


def test_full_scale_assault_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Emperor, cost 8, one copy; Emperor and City icons;
    AgentTroops 2; AcquireEffectList Dreadnought; Reveal 2 Persuasion. Text:
    "[3 swords] for each of your dreadnoughts in the Conflict." """
    entry = IMPERIUM_CARDS_BY_ID["full_scale_assault"]
    assert (entry.copies, entry.acquisition_cost) == (1, 8)
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == (AgentIcon.EMPEROR, AgentIcon.CITY)
    assert entry.agent_effect is PersonalCardAgentEffect.RECRUIT_TWO_TROOPS
    assert entry.acquisition_effect is (
        PersonalCardAcquisitionEffect.MAY_COMMISSION_DREADNOUGHT
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (2, 0)
    assert entry.play_data_complete
    assert ASSAULT in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert ASSAULT not in content_for(config).imperium_deck_instance_ids
    english = personal_card_text(entry)
    assert any(
        "+3 swords per dreadnought of yours in the Conflict" in line for line in english
    )
    assert len(english) == len(personal_card_text_ko(entry))


def test_three_swords_for_each_dreadnought_in_the_conflict() -> None:
    """ "[3 swords] for each of your dreadnoughts in the Conflict": two
    dreadnoughts give six swords beside the Reveal's 2 Persuasion."""
    state = _assault_revealed(_start(), troops=1, dreadnoughts=2)
    context = dict(state.decision_stack[-1].context)
    assert context["persuasion"] == 2
    assert context["sword_strength"] == 6
    assert state.players[0].combat_strength == 2 + 6 + 6


def test_no_dreadnought_gives_no_sword() -> None:
    """With no dreadnought in the Conflict the line gives nothing: a
    dreadnought in the garrison does nothing [FAQ p. 2] (rise-of-ix.md 6)."""
    state = _assault_revealed(_start(), troops=2, garrisoned=1)
    context = dict(state.decision_stack[-1].context)
    assert context["sword_strength"] == 0
    assert state.players[0].combat_strength == 4


def test_the_swords_stay_when_a_dreadnought_leaves_later() -> None:
    """ "Full-Scale Assault의 sword는 Reveal 때 고정, 나중에 dreadnought가 빠져도
    유지(BGG Forum) | 채택 — sword는 공개한 카드가 준 값 [DI p. 11]"
    (rise-of-ix.md 9.3): a dreadnought retreated after the Reveal takes its
    own 3 strength, not the card's swords."""
    from dune_imperium.rules.units import retreat_dreadnought

    state = _assault_revealed(_start(), troops=1, dreadnoughts=1)
    assert state.players[0].combat_strength == 2 + 3 + 3
    state = _do(state, "finish_reveal").state
    retreated = retreat_dreadnought(state, 0, "test").state
    assert retreated.players[0].combat_strength == 2 + 3


def test_full_scale_assault_recruits_two_troops_with_its_agent_box() -> None:
    """App AgentTroops 2: "[troop] [troop]"; sent to a Combat space the
    troops may be deployed [DI p. 10]."""
    state = _start()
    state = _give(state, 0, hand=(ASSAULT,))
    garrison = state.players[0].troops_garrison
    state = _do(state, "choose_agent_card", card_id=ASSAULT).state
    state = _do(state, "place_agent", space_id="arrakeen").state
    state = _do(state, "resolve_agent_card_effect").state
    assert state.players[0].troops_garrison == garrison + 2


def test_the_acquire_dreadnought_is_an_optional_row() -> None:
    """ "Dreadnought 아이콘마다 supply의 dreadnought 하나를 garrison에
    commission할 수 있다("may")" (rise-of-ix.md 6, [Rise of Ix p. 6]): bought
    in a Reveal turn, its icon waits as a row of the Reveal; taken, a
    dreadnought goes to the garrison; left, the Reveal's end lapses it."""
    state = _in_row(_start(), ASSAULT)
    state = _with_persuasion(_do(state, "reveal_turn").state, 8)
    bought = _do(state, "acquire_imperium", instance_id=ASSAULT).state
    assert _offered(bought, _ACQUIRE_ICON, effect="dreadnought")
    assert _offered(bought, "finish_reveal")
    taken = _do(bought, _ACQUIRE_ICON, effect="dreadnought").state
    owner = taken.players[0]
    assert (owner.dreadnoughts_supply, owner.dreadnoughts_garrison) == (1, 1)
    lapsed = _do(bought, "finish_reveal")
    assert "acquire_icon_lapsed" in _kinds(lapsed.events)
    assert lapsed.state.players[0].dreadnoughts_supply == 2


def test_no_dreadnought_row_with_none_in_the_supply() -> None:
    """ "supply에 없으면 더 얻지 못한다" (rise-of-ix.md 6): with both
    dreadnoughts out of the supply the icon offers nothing."""
    state = _in_row(_start(), ASSAULT)
    state = _give(state, 0, dreadnoughts_supply=0, dreadnoughts_garrison=2)
    state = _with_persuasion(_do(state, "reveal_turn").state, 8)
    bought = _do(state, "acquire_imperium", instance_id=ASSAULT).state
    assert not _offered(bought, _ACQUIRE_ICON)
    assert _offered(bought, "finish_reveal")


def _with_tile(state: GameState, tech_id: str) -> GameState:
    """Seat 0 holding ``tech_id``, taken out of the Ix board's stacks."""

    stacks = tuple(
        tuple(tile for tile in stack if tile != tech_id) for stack in state.tech_stacks
    )
    return _give(replace(state, tech_stacks=stacks), 0, tech_ids=(tech_id,))


def test_artillery_counts_the_assault_only_when_it_gave_swords() -> None:
    """Artillery: "Reveal turn: sword를 주는 공개 카드마다 sword 1"
    (rise-of-ix.md 4): Full-Scale Assault provides swords only with a
    dreadnought in the Conflict ("이번 turn에 실제로 sword를 준 다른 카드만
    센다", rise-of-ix.md 9.1, the same reading)."""
    without = _assault_revealed(_with_tile(_start(), "artillery"))
    assert dict(without.decision_stack[-1].context)["sword_strength"] == 0
    with_one = _assault_revealed(_with_tile(_start(), "artillery"), dreadnoughts=1)
    assert dict(with_one.decision_stack[-1].context)["sword_strength"] == 3 + 1


# --- Embedded Agent -------------------------------------------------------------

EMBEDDED = "imperium:embedded_agent:0"
INITIATE = "imperium:bene_gesserit_initiate:0"
_AGENT_ADVANCE = "advance_agent_card_freighter"
_AGENT_RECALL = "recall_agent_card_freighter"


def _embedded(state: GameState, *, bond: bool = True, space: int = 0) -> GameState:
    """Embedded Agent sent to Tech Negotiation (its Landsraad icon), with
    another Bene Gesserit card in play when ``bond``."""

    state = _give(
        state,
        0,
        hand=(EMBEDDED,),
        in_play=(INITIATE,) if bond else (),
        freighter_space=space,
    )
    state = _do(state, "choose_agent_card", card_id=EMBEDDED).state
    return _do(state, "place_agent", space_id="tech_negotiation").state


def _agent_freighter_rows(state: GameState) -> list[str]:
    _rows(state)
    return [
        row.action_id
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id in (_AGENT_ADVANCE, _AGENT_RECALL)
    ]


def test_embedded_agent_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Bene Gesserit, cost 5, one copy; the Landsraad icon, its
    Infiltration icon; Reveal 1 Persuasion. Screen pieces: Agent "If you have
    another Bene Gesserit card in play: [Freighter] [Freighter]"; Reveal
    "[Intrigue card]"."""
    entry = IMPERIUM_CARDS_BY_ID["embedded_agent"]
    assert (entry.copies, entry.acquisition_cost) == (1, 5)
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.LANDSRAAD,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_MOVE_FREIGHTER_TWICE_IF_BENE_GESSERIT_BOND
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert EMBEDDED in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert EMBEDDED not in content_for(config).imperium_deck_instance_ids
    english = personal_card_text(entry)
    assert any(
        "If Bene Gesserit Bond: You may move your Freighter" in line for line in english
    )
    assert len(english) == len(personal_card_text_ko(entry))


def test_the_two_freighter_icons_are_two_moves() -> None:
    """ "Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수 있다"
    (rise-of-ix.md 5, [Rise of Ix p. 5]): with the Bond, two icons -- up from
    the bottom, then up again or a recall of the space reached."""
    state = _embedded(_start())
    assert _agent_freighter_rows(state) == [_AGENT_ADVANCE]
    once = _do(state, _AGENT_ADVANCE)
    assert once.state.players[0].freighter_space == 1
    assert set(_agent_freighter_rows(once.state)) == {_AGENT_ADVANCE, _AGENT_RECALL}
    recalled = _do(once.state, _AGENT_RECALL)
    assert recalled.state.players[0].freighter_space == 0
    assert ix_pending_of(recalled.state, 0).shipping_rewards == (1,)
    assert _agent_freighter_rows(recalled.state) == []
    assert "agent_card_effect_resolved" in _kinds(recalled.events)


def test_without_another_bene_gesserit_card_the_box_gives_nothing() -> None:
    """ "If you have another Bene Gesserit card in play:" -- a Bene Gesserit
    Bond ("one or more other ... cards in play" [Main p. 20]): without it no
    Freighter is offered (OQ-028)."""
    state = _embedded(_start(), bond=False)
    assert _agent_freighter_rows(state) == []


def test_unused_freighter_icons_lapse_with_the_turn() -> None:
    """Each icon is a "may" (rise-of-ix.md 14): no refusal row; the turn's end
    lapses what is left (OQ-095 (2))."""
    state = _embedded(_start())
    state = _do(state, _AGENT_ADVANCE).state
    assert not any(
        row.action_id.startswith("decline_") for row in ENGINE.whole_actions(state, 0)
    )
    # Tech Negotiation's own "Choose one" (a Negotiator here).
    state = _do(state, "place_board_negotiator").state
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)
    assert finished.state.players[0].freighter_space == 1


def test_embedded_agent_infiltrates_a_landsraad_space() -> None:
    """ "Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의 칸에서 상대 Agent(여럿이어도)를
    무시하고 보낼 수 있게 한다" (rise-of-ix.md 7, [Rise of Ix p. 7]): Embedded
    Agent goes to Tech Negotiation past an enemy Agent."""
    state = _start()
    state = _give(state, 1, agent_locations=("tech_negotiation",), agents_available=1)
    state = _embedded(state)
    assert "tech_negotiation" in state.players[0].agent_locations


def test_embedded_agent_reveals_an_intrigue_card() -> None:
    """Reveal "[1 Persuasion] [Intrigue card]": the draw waits as the owner's
    own step (OQ-045)."""
    state = _give(_start(), 0, hand=(EMBEDDED,))
    state = _do(state, "reveal_turn").state
    assert dict(state.decision_stack[-1].context)["persuasion"] == 1
    held = len(state.players[0].intrigue_cards)
    drawn = _do(state, "draw_reveal_intrigue").state
    assert len(drawn.players[0].intrigue_cards) == held + 1


# --- Court Intrigue -------------------------------------------------------------

COURT = "imperium:court_intrigue:0"
_PUT = "put_intrigue_on_bottom_for_agent_card"


def _court(state: GameState, *intrigue: str) -> GameState:
    """Court Intrigue sent to Wealth (its Emperor icon), the seat holding
    ``intrigue`` (taken out of the Intrigue deck)."""

    deck = tuple(card for card in state.intrigue_deck if card not in intrigue)
    state = _give(replace(state, intrigue_deck=deck), 0, hand=(COURT,))
    state = _give(state, 0, intrigue_cards=intrigue)
    state = _do(state, "choose_agent_card", card_id=COURT).state
    return _do(state, "place_agent", space_id="wealth").state


def _intrigue_ids(state: GameState, count: int) -> tuple[str, ...]:
    return state.intrigue_deck[:count]


def test_court_intrigue_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Emperor, cost 2, one copy; the Emperor icon, its
    Infiltration icon; Reveal 1 Persuasion, 1 sword. Text: "Put an Intrigue
    card on the bottom of the deck -> [Intrigue card]"."""
    entry = IMPERIUM_CARDS_BY_ID["court_intrigue"]
    assert (entry.copies, entry.acquisition_cost) == (1, 2)
    assert entry.factions == (Faction.EMPEROR,)
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.EMPEROR,)
    assert entry.agent_effect is (
        PersonalCardAgentEffect.MAY_PUT_INTRIGUE_ON_BOTTOM_TO_DRAW_INTRIGUE
    )
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert COURT in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert COURT not in content_for(config).imperium_deck_instance_ids
    assert (
        "Agent: You may put an Intrigue card on the bottom of the Intrigue deck → "
        "Draw 1 Intrigue card" in personal_card_text(entry)
    )
    assert len(personal_card_text(entry)) == len(personal_card_text_ko(entry))


def test_the_card_goes_under_the_deck_unseen_then_one_is_drawn() -> None:
    """ "Court Intrigue·Sonic Snoopers — Intrigue를 덱 맨 아래에 놓을 때 상대에게
    보이지 않는다" (rise-of-ix.md 9.1, [Rise of Ix p. 10]); "놓은 좌석이 Intrigue
    덱 맨 아래 카드(들) ... 공개하지 않는다" (rise-of-ix.md 13, OQ-149): the
    seat knows the card at the bottom, the others do not and forget what they
    knew of its hand; the draw from the top is its own step (OQ-106)."""
    state = _start()
    held, kept = _intrigue_ids(state, 2)
    state = _give(state, 1, known_intrigue_ids=(held, kept))
    state = _court(state, held, kept)
    top = state.intrigue_deck[0]
    put = _do(state, _PUT, intrigue_card_id=held)
    events = [event for event in put.events if event.kind == "intrigue_put_on_bottom"]
    assert len(events) == 1 and "card_id" not in dict(events[0].payload)
    state = put.state
    assert state.intrigue_deck[-1] == held
    assert state.players[0].intrigue_cards == (kept,)
    assert known_intrigue_places(state, state.players[0])[1] == ((0, held),)
    assert state.players[1].known_intrigue_ids == ()
    check_observation_privacy(state)
    drawn = _do(state, "resolve_agent_card_effect", effect="intrigue").state
    assert drawn.players[0].intrigue_cards == (kept, top)
    assert drawn.intrigue_deck[-1] == held
    check_observation_privacy(drawn)


def test_the_card_put_down_is_drawn_back_from_a_deck_of_one() -> None:
    """The draw takes the deck's top card; with nothing else left in the deck
    it is the card just put there, back in the seat's hand, where its
    knowledge record ends (OQ-149, ``settle_known_intrigue``)."""
    state = _start()
    (held,) = _intrigue_ids(state, 1)
    state = _court(state, held)
    state = replace(state, intrigue_deck=(), intrigue_discard=())
    put = _do(state, _PUT, intrigue_card_id=held).state
    assert put.intrigue_deck == (held,)
    drawn = _do(put, "resolve_agent_card_effect", effect="intrigue").state
    assert drawn.players[0].intrigue_cards == (held,)
    assert drawn.intrigue_deck == ()
    assert drawn.players[0].known_intrigue_ids == ()


def test_no_intrigue_card_no_payment_and_the_arrow_lapses() -> None:
    """ "내지 않으면 효과도 없다": with no Intrigue card the cost cannot be paid;
    the optional arrow lapses at the turn's end (OQ-095 (2))."""
    state = _court(_start())
    assert not _offered(state, _PUT)
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)


def test_court_intrigue_infiltrates_an_emperor_space() -> None:
    """ "잠입 아이콘 카드 7장: ... Court Intrigue(Emperor)" (rise-of-ix.md 7):
    it goes to Wealth past an enemy Agent."""
    state = _start()
    state = _give(state, 1, agent_locations=("wealth",), agents_available=1)
    state = _court(state)
    assert "wealth" in state.players[0].agent_locations


def test_the_deck_bottom_rows_are_in_the_ix_catalog_only() -> None:
    """The rows naming the Intrigue card are in the original game's catalog
    with Rise of Ix alone [Rise of Ix p. 2]."""
    state = _start()
    (held,) = _intrigue_ids(state, 1)
    state = _court(state, held)
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "court_intrigue"
    ]
    assert rows
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        template = ActionTemplate(row.action_id, row.arguments)
        assert template in set(CODEC.catalog) - plain


# --- Weirding Way ---------------------------------------------------------------

WEIRDING = "imperium:weirding_way:0"
_EXTRA = "take_agent_card_extra_turn"


def _weirding(state: GameState, *hand: str, space: str = "arrakeen") -> GameState:
    """Weirding Way sent to ``space`` (Arrakeen, its City icon), ``hand`` the
    rest of the hand; the space's own effects done."""

    state = _give(state, 0, hand=(WEIRDING, *hand))
    state = _do(state, "choose_agent_card", card_id=WEIRDING).state
    state = _do(state, "place_agent", space_id=space).state
    return _space_done(state)


def _turn_owner(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert not isinstance(decision, ChanceDecision)
    return decision.owner  # type: ignore[union-attr]


def test_weirding_way_matches_the_app_and_joins_the_ix_deck() -> None:
    """App table: Bene Gesserit, cost 3, one copy; City and Spice Trade
    icons; Reveal 1 Persuasion, 2 swords. Text: "You may take another turn
    immediately after this one." """
    entry = IMPERIUM_CARDS_BY_ID["weirding_way"]
    assert (entry.copies, entry.acquisition_cost) == (1, 3)
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.CITY, AgentIcon.SPICE_TRADE)
    assert entry.agent_effect is PersonalCardAgentEffect.MAY_TAKE_ANOTHER_TURN
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 2)
    assert entry.play_data_complete
    assert WEIRDING in content_for(IX).imperium_deck_instance_ids
    for config in (replace(IX, rise_of_ix=False), RulesetConfig()):
        assert WEIRDING not in content_for(config).imperium_deck_instance_ids
    assert (
        "Agent: You may take another turn immediately after this one"
        in personal_card_text(entry)
    )
    assert len(personal_card_text(entry)) == len(personal_card_text_ko(entry))


def test_the_extra_turn_follows_at_once_then_play_goes_on() -> None:
    """ "You may take another turn immediately after this one": taken, the
    turn's end opens the owner's next turn (an Agent or a Reveal turn [DI p.
    8]); that one's end hands the turn to the next seat clockwise."""
    state = _weirding(_start(), *_start().players[0].hand[:2])
    assert _offered(state, _EXTRA)
    taken = _do(state, _EXTRA)
    assert "extra_turn_taken" in _kinds(taken.events)
    state = _do(taken.state, "finish_agent_turn").state
    assert _turn_owner(state) == 0
    assert _offered(state, "reveal_turn")
    card = state.players[0].hand[0]
    state = _do(state, "choose_agent_card", card_id=card).state
    rows = [
        row for row in ENGINE.whole_actions(state, 0) if row.action_id == "place_agent"
    ]
    state = _do(
        state, "place_agent", space_id=dict(rows[0].arguments)["space_id"]
    ).state
    while not _offered(state, "finish_agent_turn"):
        row = next(
            row
            for row in ENGINE.whole_actions(state, 0)
            if not row.action_id.startswith(("deploy", "withdraw"))
        )
        arguments: dict[str, object] = dict(row.arguments)
        state = _do(state, row.action_id, 0, **arguments).state
    state = _do(state, "finish_agent_turn").state
    assert _turn_owner(state) == 1


def test_an_unused_extra_turn_lapses_and_the_next_seat_plays() -> None:
    """ "you may": no refusal row; the turn's end lapses it (OQ-095 (2))."""
    state = _weirding(_start())
    assert not any(
        row.action_id.startswith("decline_") for row in ENGINE.whole_actions(state, 0)
    )
    finished = _do(state, "finish_agent_turn")
    assert "agent_card_effect_lapsed" in _kinds(finished.events)
    assert _turn_owner(finished.state) == 1


def test_the_voice_does_not_block_the_extra_turn() -> None:
    """ "Weirding Way의 둘째 turn은 The Voice에 막히지 않음(BGG forum) | 채택"
    (rise-of-ix.md 9.3; imperium-base.md 13.1, OQ-116: the block lasts to the
    opponent's next Agent placement this round): blocked from Imperial Basin
    before this turn, the seat may go there in its extra turn."""
    state = _start()
    dune = "player:0:starter:dune_the_desert_planet:1"
    state = _give(state, 0, voice_blocked_space_ids=("imperial_basin",))
    state = _weirding(state, dune)
    assert state.players[0].voice_blocked_space_ids == ()
    state = _do(state, _EXTRA).state
    state = _do(state, "finish_agent_turn").state
    assert _turn_owner(state) == 0
    state = _do(state, "choose_agent_card", card_id=dune).state
    assert _offered(state, "place_agent", space_id="imperial_basin")


def test_ilesas_extra_turn_is_her_second_turn() -> None:
    """ "Ilesa Ecaz ... Agent 없는 pass와 Weirding Way 추가 turn 모두 센다(OQ-119
    사용자 확정)" (rise-of-ix.md 10): her set-aside card returns to her hand
    at the start of the extra turn that follows her first."""
    state = _start()
    kept = "player:0:starter:diplomacy:0"
    state = _give(
        state,
        0,
        hand=(),
        leader_id="ilesa_ecaz",
        leader_face_id="ilesa_ecaz",
        set_aside_card_id=kept,
    )
    state = _weirding(state)
    assert kept not in state.players[0].hand
    state = _do(state, _EXTRA).state
    result = _do(state, "finish_agent_turn")
    owner = result.state.players[0]
    assert _turn_owner(result.state) == 0
    assert kept in owner.hand
    assert owner.set_aside_card_id is None or owner.set_aside_card_id == ""


def test_the_extra_turn_row_is_in_the_ix_catalog_only() -> None:
    """The row naming the card is in the original game's catalog with Rise of
    Ix alone [Rise of Ix p. 2]."""
    state = _weirding(_start())
    rows = [
        row
        for row in ENGINE.legal_actions(state, 0)
        if dict(row.arguments).get("printed") == "weirding_way"
    ]
    assert rows
    plain = set(ActionCodec(replace(IX, rise_of_ix=False)).catalog)
    for row in rows:
        template = ActionTemplate(row.action_id, row.arguments)
        assert template in set(CODEC.catalog) - plain


def test_a_taken_extra_turn_stays_when_the_card_is_trashed() -> None:
    """ "trash되는 카드의 Unload는 일어난다; Weirding Way처럼 '이미 설치된
    효과'는 카드가 trash돼도 남는다(BGG Forum) | 채택" (rise-of-ix.md 9.3):
    Cull trashing Weirding Way after its extra turn was taken leaves the
    extra turn owed."""
    cull = "intrigue:cull:0"
    state = _start()
    deck = tuple(card for card in state.intrigue_deck if card != cull)
    state = replace(state, intrigue_deck=deck)
    owner = state.players[0]
    state = _give(
        state,
        0,
        intrigue_cards=(cull,),
        resources=replace(owner.resources, solari=1),
    )
    state = _weirding(state)
    state = _do(state, _EXTRA).state
    state = _do(state, "play_intrigue", card_id=cull, option=0).state
    state = _do(state, "trash_intrigue_card", card_id=WEIRDING).state
    assert WEIRDING in state.players[0].trashed
    state = _do(state, "finish_agent_turn").state
    assert _turn_owner(state) == 0
