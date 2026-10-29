"""Rise of Ix's Unload: a Reveal box gained when its card is discarded or trashed.

Rules: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2] and its
designer ruling ("비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지
해결한 뒤 오른쪽으로 간다"), OQ-120. The mechanism tests mark Ix cards that are
already in the deck as Unload cards with a "1 water" box (``_unload``); the
cards that print Unload are tested with their own data.
"""

import random
from collections.abc import Iterator
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec, action_codec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.effect_dsl import GainResources
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.reveal_abilities import REVEAL_GAIN_ABILITIES
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAcquisitionEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase
from dune_imperium.rules import UprisingRulesEngine, unload
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.frames import FrameKind

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
TRUTHSAYER = "imperium:truthsayer:0"
JAMIS = "imperium:jamis:0"
MOHIAM = "imperium:reverend_mother_mohiam:0"
INITIATE = "imperium:bene_gesserit_initiate:0"
# Marked as Unload cards with a "1 water" box for the mechanism tests.
MARKED = ("imperium:sayyadina:0", "imperium:truthsayer:1")
UNLOAD_ROW = "resolve_unload_icon"


@pytest.fixture
def marked(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """``MARKED`` give one water when discarded or trashed; the catalog is
    rebuilt with their rows, and rebuilt again without them afterwards."""

    def icons(card_id: str) -> tuple[tuple[str, int], ...]:
        return (("water", 1),) if card_id in MARKED else ()

    monkeypatch.setattr(unload, "unload_icons", icons)
    monkeypatch.setattr(action_codec, "unload_icons", icons)
    action_codec._catalog_of.cache_clear()
    yield
    action_codec._catalog_of.cache_clear()


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    codec = ActionCodec(IX)
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert codec.decode(codec.encode(row), seat) == row
    return rows


def _give(state: GameState, seat: int, **zones: tuple[str, ...]) -> GameState:
    """Put the named cards in ``seat``'s zones, taking them out of the
    Imperium deck and Row and of every seat's zones first (seeded decks)."""

    named = {card for cards in zones.values() for card in cards}
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
    return state


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
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
            return RuleResult(state=state, events=tuple(events))


def _offered(state: GameState, action_id: str, seat: int = 0) -> bool:
    _rows(state, seat)
    return any(row.action_id == action_id for row in ENGINE.whole_actions(state, seat))


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


@pytest.mark.usefixtures("marked")
def test_a_discard_cost_pays_the_unload_box_before_the_arrows_reward() -> None:
    """ "비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤
    오른쪽으로 간다" (designer ruling, rise-of-ix.md 7); Truthsayer: "Discard
    -> draw a card"."""
    state = _start()
    unloaded, kept = MARKED[0], state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, unloaded, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    water = state.players[0].resources.water
    top = state.players[0].deck[0]
    result = _do(state, "discard_agent_card", card_id=unloaded)
    owner = result.state.players[0]
    assert owner.resources.water == water + 1
    assert owner.hand == (kept, top)
    kinds = _kinds(result.events)
    unload_gain = next(
        index
        for index, event in enumerate(result.events)
        if event.kind == "resources_gained" and ":unload:" in event.event_id
    )
    # The box's own event closes it once its draw is paid.
    assert (
        kinds.index("card_discarded")
        < kinds.index("card_unloaded")
        < unload_gain
        < kinds.index("agent_card_effect_resolved")
    )
    assert not _offered(result.state, UNLOAD_ROW)


@pytest.mark.usefixtures("marked")
def test_a_trash_effect_in_the_owners_turn_waits_as_a_row_of_the_turn() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card". In the
    owner's own turn each icon is a row of the turn, and a gain holds the
    turn's end until it is taken."""
    state = _start()
    unloaded = MARKED[0]
    state = _give(state, 0, hand=(JAMIS, unloaded))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    water = state.players[0].resources.water
    trashed = _do(state, "trash_agent_card", card_id=unloaded)
    assert unloaded in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    state = trashed.state
    assert state.players[0].resources.water == water
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert not _offered(state, "finish_agent_turn")
    taken = _do(state, UNLOAD_ROW, card_id=unloaded, effect="water")
    assert (
        taken.state.players[0].resources.water == state.players[0].resources.water + 1
    )
    assert not _offered(taken.state, UNLOAD_ROW)
    assert _offered(taken.state, "finish_agent_turn")


@pytest.mark.usefixtures("marked")
def test_an_opponents_discard_opens_the_unload_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7): outside its owner's turn the box is a window of its
    own, answered before the opponent's discard goes on."""
    state = _start()
    unloaded, other = MARKED[0], state.players[1].hand[0]
    state = _give(state, 0, hand=(MOHIAM,), in_play=(INITIATE,))
    state = _give(state, 1, hand=(unloaded, other))
    state = _do(state, "choose_agent_card", card_id=MOHIAM).state
    state = _do(state, "place_agent", space_id="secrets").state
    state = _do(state, "resolve_agent_card_effect").state
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD
    water = state.players[1].resources.water
    state = _do(state, "discard_opponent_card", seat=1, card_id=unloaded).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.UNLOAD_ICONS
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert [row.action_id for row in _rows(state, 1)] == [UNLOAD_ROW]
    state = _do(state, UNLOAD_ROW, seat=1, card_id=unloaded, effect="water").state
    assert state.players[1].resources.water == water + 1
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.OPPONENT_CARD_DISCARD
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1


@pytest.mark.usefixtures("marked")
def test_clean_up_moves_an_unload_card_without_unloading_it() -> None:
    """ "Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다"
    (rise-of-ix.md 7, [FAQ p. 2]; OQ-120)."""
    state = _give(_start(), 0, in_play=(MARKED[0],))
    chance = ChanceResolver(seed=3)
    rng = random.Random(3)
    unloaded: list[GameEvent] = []
    # The card's place is read as it leaves play: the Round 2 draw may shuffle
    # the discard pile back into the deck, as this random game does since
    # Strategic Push joined the Intrigue deck.
    left_play: GameState | None = None
    while state.round_number == 1 and state.phase is not GamePhase.FINISHED:
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            result = ENGINE.apply(state, chance.resolve(decision))
        else:
            assert isinstance(decision, PlayerDecision)
            result = ENGINE.apply(
                state, rng.choice(ENGINE.legal_actions(state, decision.owner))
            )
        unloaded.extend(e for e in result.events if e.kind == "card_unloaded")
        state = result.state
        if left_play is None and MARKED[0] not in state.players[0].in_play:
            left_play = state
    assert state.round_number == 2
    assert left_play is not None
    assert MARKED[0] in left_play.players[0].discard_pile
    assert unloaded == []


# --- Water Peddler -------------------------------------------------------------

WATER_PEDDLER = "imperium:water_peddler:0"
CULL = "intrigue:cull:0"


def _in_row(state: GameState, instance_id: str) -> GameState:
    """``instance_id`` in the Imperium Row's first slot, out of the deck."""

    state = _give(state, 0)
    deck = tuple(card for card in state.imperium_deck if card != instance_id)
    row = tuple(card for card in state.imperium_row if card != instance_id)
    return replace(state, imperium_deck=deck, imperium_row=(instance_id, *row[1:]))


def test_water_peddler_play_data_matches_the_app() -> None:
    """App table: cost 1, 1 copy, no Faction and no Agent icon, AcquireEffect
    Water; screen pieces: acquire "[1 water]", Reveal "[Unload] [1 water]"."""
    entry = IMPERIUM_CARDS_BY_ID["water_peddler"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (1, 1)
    assert entry.factions == () and entry.agent_icons == ()
    assert entry.has_acquisition_bonus
    assert entry.acquisition_effect is PersonalCardAcquisitionEffect.GAIN_ONE_WATER
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    (line,) = REVEAL_GAIN_ABILITIES["water_peddler"].sections
    assert line.rewards == (GainResources(water=1),) and line.condition is None
    assert unload.unload_icons(WATER_PEDDLER) == (("water", 1),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert (WATER_PEDDLER in deck) == config.rise_of_ix


def test_water_peddler_gives_one_water_when_acquired() -> None:
    """Water Peddler's acquire box: "[1 water]" [DI p. 16]."""
    state = _in_row(_start(), WATER_PEDDLER)
    state = _do(state, "reveal_turn").state
    water = state.players[0].resources.water
    result = _do(state, "acquire_imperium", instance_id=WATER_PEDDLER)
    owner = result.state.players[0]
    assert WATER_PEDDLER in owner.discard_pile
    assert owner.resources.water == water + 1
    assert "card_unloaded" not in _kinds(result.events)


def test_water_peddler_revealed_gives_its_box_as_usual() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7)."""
    state = _give(_start(), 0, hand=(WATER_PEDDLER,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    water = revealed.state.players[0].resources.water
    gained = _do(revealed.state, "gain_reveal_resources")
    assert gained.state.players[0].resources.water == water + 1
    assert not _offered(gained.state, "gain_reveal_resources")
    assert not _offered(gained.state, UNLOAD_ROW)


def test_water_peddler_revealed_then_trashed_gives_its_box_again() -> None:
    """OQ-120: "공개한 Unload 카드를 같은 Reveal turn에 trash하면 다시 얻는다";
    Cull: "[1 Solari] -> [trash a card]"."""
    state = _give(_start(), 0, hand=(WATER_PEDDLER,))
    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != CULL)
    )
    state = _give(state, 0, hand=(WATER_PEDDLER,))
    owner = state.players[0]
    state = replace(
        state,
        players=(
            replace(
                owner,
                intrigue_cards=(CULL,),
                resources=replace(owner.resources, solari=1),
            ),
            *state.players[1:],
        ),
    )
    state = _do(state, "reveal_turn").state
    water = state.players[0].resources.water
    state = _do(state, "gain_reveal_resources").state
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    trashed = _do(state, "trash_intrigue_card", card_id=WATER_PEDDLER)
    assert WATER_PEDDLER in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    assert not _offered(trashed.state, "finish_reveal")
    again = _do(trashed.state, UNLOAD_ROW, card_id=WATER_PEDDLER, effect="water")
    assert again.state.players[0].resources.water == water + 2
    assert _offered(again.state, "finish_reveal")


def test_water_peddler_paid_as_a_discard_cost_gives_its_water_at_once() -> None:
    """ "Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (designer ruling,
    rise-of-ix.md 7); Truthsayer: "Discard -> draw a card"."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, WATER_PEDDLER, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    water = state.players[0].resources.water
    result = _do(state, "discard_agent_card", card_id=WATER_PEDDLER)
    assert result.state.players[0].resources.water == water + 1
    assert WATER_PEDDLER in result.state.players[0].discard_pile
    assert not _offered(result.state, UNLOAD_ROW)


def test_cull_trashing_water_peddler_gives_its_water() -> None:
    """Cull's trash is mandatory once it is played ("Cull은 trash해야 낸다",
    rise-of-ix.md 9.3, OQ-113 (C)), and "trash할 때 얻는다" (rise-of-ix.md 7,
    [Rise of Ix p. 7]). Played in the owner's own turn, the trash is an effect,
    not a cost, so the water waits as a row of the turn (the Solari is the
    arrow's cost, a different payment) until it is taken."""
    state = _start()
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(WATER_PEDDLER, kept))
    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != CULL)
    )
    owner = state.players[0]
    state = replace(
        state,
        players=(
            replace(
                owner,
                intrigue_cards=(CULL,),
                resources=replace(owner.resources, solari=1),
            ),
            *state.players[1:],
        ),
    )
    state = _do(state, "play_intrigue", card_id=CULL, option=0).state
    # Mandatory: no refusal, only the cards it may trash.
    assert not _offered(state, "decline_intrigue_trash")
    assert _offered(state, "trash_intrigue_card")
    water = state.players[0].resources.water
    trashed = _do(state, "trash_intrigue_card", card_id=WATER_PEDDLER)
    assert WATER_PEDDLER in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    assert trashed.state.players[0].resources.water == water
    assert _offered(trashed.state, UNLOAD_ROW)
    taken = _do(trashed.state, UNLOAD_ROW, card_id=WATER_PEDDLER, effect="water")
    assert taken.state.players[0].resources.water == water + 1
    assert not _offered(taken.state, UNLOAD_ROW)


SHAI_HULUD = "imperium:shai_hulud:0"


def test_shai_hulud_agent_trash_cost_gives_the_water_before_the_troops() -> None:
    """Shai-Hulud's Agent box "[Trash a card] -> [2 troops]" trashes as a
    cost: "Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (designer ruling,
    rise-of-ix.md 7), so Water Peddler's water is paid inside the payment."""
    state = _start()
    state = _give(state, 0, hand=(SHAI_HULUD, WATER_PEDDLER))
    state = _do(state, "choose_agent_card", card_id=SHAI_HULUD).state
    state = _do(state, "place_agent", space_id="imperial_basin").state
    owner = state.players[0]
    result = _do(state, "trash_agent_card", card_id=WATER_PEDDLER)
    after = result.state.players[0]
    assert WATER_PEDDLER in after.trashed
    assert after.resources.water == owner.resources.water + 1
    assert after.troops_garrison == owner.troops_garrison + 2
    kinds = _kinds(result.events)
    assert kinds.index("card_unloaded") < kinds.index("agent_card_effect_resolved")
    assert not _offered(result.state, UNLOAD_ROW)


def test_shai_hulud_acquire_trash_gives_a_trashed_unload_cards_box() -> None:
    """Shai-Hulud's acquire box (the black Trash icon, optional, resolved when
    the card is acquired, [Main p. 20] [DI p. 16]) is an effect, not a cost:
    a trashed Water Peddler's water waits as a row of the Reveal turn."""
    state = _in_row(_start(), SHAI_HULUD)
    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(kept,), discard_pile=(WATER_PEDDLER,))
    state = _do(state, "reveal_turn").state
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["persuasion"] = 20
    state = replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )
    state = _do(state, "acquire_imperium", instance_id=SHAI_HULUD).state
    water = state.players[0].resources.water
    trashed = _do(state, "trash_optional_card", card_id=WATER_PEDDLER)
    assert WATER_PEDDLER in trashed.state.players[0].trashed
    assert "card_unloaded" in _kinds(trashed.events)
    assert trashed.state.players[0].resources.water == water
    taken = _do(trashed.state, UNLOAD_ROW, card_id=WATER_PEDDLER, effect="water")
    assert taken.state.players[0].resources.water == water + 1
    assert not _offered(taken.state, UNLOAD_ROW)


# --- CHOAM Delegate ------------------------------------------------------------

CHOAM_DELEGATE = "imperium:choam_delegate:0"


def test_choam_delegate_play_data_matches_the_app() -> None:
    """App table: cost 1, 1 copy, no Faction, Agent icon Spice Trade with
    Infiltration (``InfiltrationIconList``), Reveal 3 Solari; screen pieces:
    Reveal "[Unload] [3 Solari]"."""
    entry = IMPERIUM_CARDS_BY_ID["choam_delegate"]
    assert entry.play_data_complete and entry.unload
    assert (entry.copies, entry.acquisition_cost) == (1, 1)
    assert entry.factions == ()
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.agent_effect is None and not entry.has_acquisition_bonus
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    (line,) = REVEAL_GAIN_ABILITIES["choam_delegate"].sections
    assert line.rewards == (GainResources(solari=3),) and line.condition is None
    assert unload.unload_icons(CHOAM_DELEGATE) == (("solari", 3),)
    for config in (IX, replace(IX, rise_of_ix=False), RulesetConfig()):
        deck = content_for(config).imperium_deck_instance_ids
        assert (CHOAM_DELEGATE in deck) == config.rise_of_ix


def test_choam_delegate_revealed_gives_three_solari_as_usual() -> None:
    """ "Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시)" (rise-of-ix.md 7)."""
    state = _give(_start(), 0, hand=(CHOAM_DELEGATE,))
    revealed = _do(state, "reveal_turn")
    assert "card_unloaded" not in _kinds(revealed.events)
    solari = revealed.state.players[0].resources.solari
    gained = _do(revealed.state, "gain_reveal_resources")
    assert gained.state.players[0].resources.solari == solari + 3
    assert not _offered(gained.state, UNLOAD_ROW)


def test_choam_delegate_trashed_in_its_owners_turn_waits_as_a_row() -> None:
    """ "trash할 때 얻는다" [Rise of Ix p. 7]; Jamis: "Trash a card"."""
    state = _give(_start(), 0, hand=(JAMIS, CHOAM_DELEGATE))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    solari = state.players[0].resources.solari
    state = _do(state, "trash_agent_card", card_id=CHOAM_DELEGATE).state
    assert state.players[0].resources.solari == solari
    taken = _do(state, UNLOAD_ROW, card_id=CHOAM_DELEGATE, effect="solari")
    assert taken.state.players[0].resources.solari == solari + 3
    assert not _offered(taken.state, UNLOAD_ROW)


def test_choam_delegate_discarded_by_an_opponent_unloads_in_a_window() -> None:
    """ "남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam)"
    (rise-of-ix.md 7)."""
    state = _start()
    other = state.players[1].hand[0]
    state = _give(state, 0, hand=(MOHIAM,), in_play=(INITIATE,))
    state = _give(state, 1, hand=(CHOAM_DELEGATE, other))
    state = _do(state, "choose_agent_card", card_id=MOHIAM).state
    state = _do(state, "place_agent", space_id="secrets").state
    state = _do(state, "resolve_agent_card_effect").state
    solari = state.players[1].resources.solari
    state = _do(state, "discard_opponent_card", seat=1, card_id=CHOAM_DELEGATE).state
    assert state.decision_stack[-1].kind is FrameKind.UNLOAD_ICONS
    state = _do(
        state, UNLOAD_ROW, seat=1, card_id=CHOAM_DELEGATE, effect="solari"
    ).state
    assert state.players[1].resources.solari == solari + 3
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


def test_choam_delegate_infiltrates_a_spice_trade_space() -> None:
    """ "Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의 칸에서 상대 Agent ...를
    무시하고 보낼 수 있게 한다" [Rise of Ix p. 7]; CHOAM Delegate's icon is
    Spice Trade (app ``InfiltrationIconList``)."""
    state = _give(_start(), 0, hand=(CHOAM_DELEGATE,))
    owner = state.players[1]
    state = replace(
        state,
        players=(
            state.players[0],
            replace(
                owner,
                agent_locations=("smuggling",),
                agents_available=owner.agents_available - 1,
            ),
            *state.players[2:],
        ),
    )
    state = _do(state, "choose_agent_card", card_id=CHOAM_DELEGATE).state
    spaces = {
        str(dict(row.arguments)["space_id"])
        for row in ENGINE.whole_actions(state, 0)
        if row.action_id == "place_agent"
    }
    assert "smuggling" in spaces
    placed = _do(state, "place_agent", space_id="smuggling").state
    assert "smuggling" in placed.players[0].agent_locations
