"""The original board's space payouts (2026-11 audit).

docs/rules/imperium-base.md 8 ("보드 칸 22개") lists each space's cost and
effects [DI pp. 17-18]. Mentat, Selective Breeding, Foldspace, Research
Station, Sell Melange, the Maker spaces and the once-per-game spaces had
their tests (tests/unit/rules/test_imperium_board.py); these did not.
"""

from dataclasses import dataclass, replace

import pytest
from tests.unit.rules.test_imperium_board import (
    CONFIG,
    ENGINE,
    LEADERS,
    _place,
    _seat,
    _start,
    _wholes,
    _with_card,
)

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.core.icons import ConflictTier, Faction
from dune_imperium.content.rulesets import content_for
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.reveal_turn import begin_reveal_turn, legal_reveal_actions
from dune_imperium.rules.setup import create_initial_state


def _r(solari: int = 0, spice: int = 0, water: int = 0) -> Resources:
    # ``Resources()`` starts with one water [Main p. 5]; these are exact.
    return Resources(solari=solari, spice=spice, water=water)


@dataclass(frozen=True)
class _Payout:
    space_id: str
    cost: Resources
    faction: Faction | None
    resources: Resources = _r()
    troops: int = 0
    intrigue: int = 0
    fremen_influence: int = 0


# docs/rules/imperium-base.md 8, the rows quoted in each comment.
_PAYOUTS = (
    # "| Conspire | Emperor | spice 4 | Emperor Influence 1, 5 Solari, troop 2,
    # Intrigue 1 |" `[DI p. 17]`
    _Payout("conspire", _r(spice=4), Faction.EMPEROR, _r(solari=5), 2, 1),
    # "| Wealth | Emperor | – | Emperor Influence 1, 2 Solari |" `[DI p. 18]`
    _Payout("wealth", _r(), Faction.EMPEROR, _r(solari=2)),
    # "| Heighliner | Spacing Guild | spice 6 | Guild Influence 1, troop 5,
    # water 2 | × |" `[DI p. 17]`
    _Payout(
        "imperium_heighliner",
        _r(spice=6),
        Faction.SPACING_GUILD,
        _r(water=2),
        5,
    ),
    # "| Hardy Warriors | Fremen | water 1 | Fremen Influence 1, troop 2 | × |"
    # `[DI p. 17]`
    _Payout("hardy_warriors", _r(water=1), Faction.FREMEN, troops=2),
    # "| Stillsuits | Fremen | – | Fremen Influence 1, water 1 | × |" `[DI p. 18]`
    _Payout("stillsuits", _r(), Faction.FREMEN, _r(water=1)),
    # "| Hall of Oratory | Landsraad | – | troop 1; ..." `[DI p. 17]`
    _Payout("hall_of_oratory", _r(), None, troops=1),
    # "| Rally Troops | Landsraad | 4 Solari | troop 4 |" `[DI p. 18]`
    _Payout("rally_troops", _r(solari=4), None, troops=4),
    # "| Carthag | City | – | troop 1, Intrigue 1; controller 1 Solari | × |"
    # `[DI p. 17]`
    _Payout("carthag", _r(), None, troops=1, intrigue=1),
    # "| Sietch Tabr | City | Fremen Influence 2 이상 | troop 1, water 1 | × |"
    # `[DI pp. 9, 18]`
    _Payout(
        "imperium_sietch_tabr",
        _r(),
        None,
        _r(water=1),
        1,
        fremen_influence=2,
    ),
    # "| Secure Contract | Spice Trade | – | 3 Solari |" `[DI p. 18]`
    _Payout("secure_contract", _r(), None, _r(solari=3)),
)


def _resolve_space(state: GameState) -> GameState:
    """Resolve every board icon and the Faction Influence of the visit,
    leaving the played card's own box alone."""

    for _ in range(16):
        rows = [
            action
            for action in _wholes(state)
            if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
        ]
        if not rows:
            return state
        state = apply_whole(ENGINE, state, rows[0]).state
    raise AssertionError("the space's effects did not run out")


@pytest.mark.parametrize("payout", _PAYOUTS, ids=lambda payout: payout.space_id)
def test_an_original_space_pays_its_printed_effects(payout: _Payout) -> None:
    """The space's cost is paid first and its printed effects follow.

    docs/rules/imperium-base.md 8: "비용은 효과보다 먼저 낸다 `[DI p. 9]`."
    and the space's row of its table [DI pp. 17-18].
    """

    state = _seat(
        _start(),
        resources=payout.cost,
        influence=Influence(fremen=payout.fremen_influence),
    )
    before = state.players[0]

    placed = _place(state, payout.space_id)
    assert placed.players[0].resources == _r()
    resolved = _resolve_space(placed).players[0]

    assert resolved.resources == payout.resources
    assert resolved.troops_garrison == before.troops_garrison + payout.troops
    assert resolved.troops_supply == before.troops_supply - payout.troops
    assert len(resolved.intrigue_cards) == len(before.intrigue_cards) + payout.intrigue
    for faction in Faction:
        gained = 1 if faction is payout.faction else 0
        assert getattr(resolved.influence, faction.value) == (
            getattr(before.influence, faction.value) + gained
        ), faction


def test_original_sietch_tabr_needs_two_fremen_influence() -> None:
    """docs/rules/imperium-base.md 8: "| Sietch Tabr | City | Fremen Influence 2
    이상 | troop 1, water 1 | × |" `[DI pp. 9, 18]`"""

    for fremen, open_ in ((1, False), (2, True)):
        state = _seat(
            _with_card(_start(), "reconnaissance"), influence=Influence(fremen=fremen)
        )
        spaces = {
            dict(placement.arguments)["space_id"]
            for placement in executable_placements(state, 0)
        }
        assert ("imperium_sietch_tabr" in spaces) is open_


def _reveal_state(owner: PlayerState) -> GameState:
    return GameState(
        config=CONFIG,
        seed=1,
        maker_bonus_spice=content_for(CONFIG).maker_bonus_spice_for(LEADERS),
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _reveal_persuasion(owner: PlayerState) -> int:
    state = _reveal_state(owner)
    revealed = begin_reveal_turn(state, legal_reveal_actions(state, 0)[0]).state
    context = next(
        dict(frame.context)
        for frame in reversed(revealed.decision_stack)
        if frame.kind == "reveal"
    )
    persuasion = context["persuasion"]
    assert isinstance(persuasion, int)
    return persuasion


def test_an_agent_on_hall_of_oratory_adds_a_persuasion_to_the_reveal() -> None:
    """docs/rules/imperium-base.md 8: "| Hall of Oratory | Landsraad | – |
    troop 1; 여기 Agent가 있으면 자기 Reveal turn에 Persuasion 1 |" `[DI p. 17]`"""

    away = PlayerState(player_id=0, agents_available=1, agent_locations=("wealth",))
    there = replace(away, agent_locations=("hall_of_oratory",))

    assert _reveal_persuasion(away) == 0
    assert _reveal_persuasion(there) == 1


def test_an_original_councilor_adds_two_persuasion_to_every_reveal() -> None:
    """docs/rules/imperium-base.md 8: "| High Council | Landsraad | 5 Solari |
    게임에 한 번; Councilor를 빈 자리에, 이후 Reveal turn마다 Persuasion 2 |"
    `[DI p. 17]`"""

    assert _reveal_persuasion(PlayerState(player_id=0)) == 0
    assert _reveal_persuasion(PlayerState(player_id=0, high_council=True)) == 2


@pytest.mark.parametrize("seed", range(4))
def test_the_original_conflict_deck_uses_every_conflict_iii(seed: int) -> None:
    """docs/rules/imperium-base.md 4: "**B.** Conflict 덱은 Uprising과 같은
    모양(I 1, II 5, III 4)이다. 원판은 III 4장을 모두 쓴다." `[DI p. 4]`"""

    state = create_initial_state(CONFIG, seed, LEADERS).state
    tier_by_id = {
        conflict.card.card_id: conflict.tier
        for conflict in content_for(CONFIG).conflict_pool
    }
    deck = (*state.current_conflict_ids, *state.conflict_deck)

    assert tuple(tier_by_id[card_id] for card_id in deck) == (
        ConflictTier.ONE,
        *(ConflictTier.TWO for _ in range(5)),
        *(ConflictTier.THREE for _ in range(4)),
    )
    assert {
        card_id for card_id, tier in tier_by_id.items() if tier is ConflictTier.THREE
    } <= set(deck)
