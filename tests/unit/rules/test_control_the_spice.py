"""Control the Spice, the Epic Game Mode starting card [Rise of Ix p. 10].

Rule source: ``docs/rules/epic-game-mode.md`` section 6 and the card face:
Spice Trade Agent icon; Agent box "[1 spice] -> [trash a card] [troop]";
Reveal box 1 Persuasion, 1 spice. "화살표의 왼쪽 또는 위쪽은 비용이고 오른쪽
또는 아래쪽은 그 비용으로 얻는 효과다. 비용을 지불하지 않으면 효과를 얻지
못하며, 하나의 화살표 비용과 효과는 한 턴에 한 번만 선택할 수 있다"
[Main p. 9] [FAQ p. 3]; "검은색 카드 폐기 아이콘을 사용하지 않는 경우에는 그
효과를 생략할 수 있다" [FAQ p. 3] (docs/rules/player-turns.md:53-54); "일반
trash 아이콘은 hand, discard pile, in play 가운데 카드 1장을 대상으로 한다"
[Main p. 20] (docs/rules/uprising-systems.md:17); "그 turn에 어떤 출처에서
recruit했든 새 troop은 Conflict에 deploy할 수 있다" [Main p. 10] [FAQ p. 4]
(docs/rules/player-turns.md:137).

Every legal action these tests walk through comes from the engine's own
dispatcher and must encode in the Epic catalog (``_legal``).
"""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.starting_cards import (
    STARTING_CARDS_BY_ID,
    starting_deck_instance_ids,
)
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_turn import (
    apply_reveal_gain,
    begin_reveal_turn,
    legal_reveal_gain_actions,
)

EPIC = RulesetConfig(epic_game=True)
ENGINE = UprisingRulesEngine()
STARTERS = starting_deck_instance_ids(0, epic_game=True)
CONTROL = "player:0:starter:control_the_spice:0"
DAGGER = "player:0:starter:dagger:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
RECONNAISSANCE = "player:0:starter:reconnaissance:0"
CONVINCING = "player:0:starter:convincing_argument:0"
# docs/rules/board-spaces.md:75-79: the five Spice Trade spaces of the base
# board; Deep Desert, Hagga Basin and Imperial Basin are Combat spaces.
SPICE_TRADE_SPACES = frozenset(
    {"accept_contract", "deep_desert", "hagga_basin", "imperial_basin", "shipping"}
)

_CODECS: dict[RulesetConfig, ActionCodec] = {}


def _codec(config: RulesetConfig) -> ActionCodec:
    if config not in _CODECS:
        _CODECS[config] = ActionCodec(config)
    return _CODECS[config]


def _owner(hand: tuple[str, ...], **extra: object) -> PlayerState:
    values: dict[str, object] = {
        "player_id": 0,
        "hand": hand,
        "deck": tuple(
            card for card in STARTERS if card not in hand and card != CONTROL
        )[:3],
    }
    values.update(extra)
    return PlayerState(**values)  # type: ignore[arg-type]


def _state(
    owner: PlayerState,
    *others: PlayerState,
    config: RulesetConfig = EPIC,
) -> GameState:
    seats = [owner, *others]
    seats.extend(PlayerState(player_id=seat) for seat in range(len(seats), 4))
    imperium = imperium_deck_instance_ids(False, bloodlines=config.bloodlines)
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        current_conflict_ids=("choam_security",),
        intrigue_deck=intrigue_deck_instance_ids(False)[:6],
        imperium_row=imperium[:5],
        imperium_deck=imperium[5:20],
        players=tuple(seats),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def _legal(state: GameState, player: int = 0) -> tuple[DomainAction, ...]:
    """The dispatcher's legal set, each action round-tripped through the codec."""

    codec = _codec(state.config)
    actions = ENGINE.legal_actions(state, player)
    for action in actions:
        assert codec.decode(codec.encode(action), player) == action
    return actions


def _find(state: GameState, action_id: str, **arguments: object) -> DomainAction:
    return next(
        action
        for action in _legal(state)
        if action.action_id == action_id
        and all(dict(action.arguments).get(k) == v for k, v in arguments.items())
    )


def _apply(state: GameState, action_id: str, **arguments: object) -> GameState:
    return ENGINE.apply(state, _find(state, action_id, **arguments)).state


def _place(state: GameState, space_id: str) -> GameState:
    return _apply(state, "agent_turn", card_id=CONTROL, space_id=space_id)


def _ids(state: GameState) -> set[str]:
    return {action.action_id for action in _legal(state)}


def _payment_ids(state: GameState) -> set[str]:
    return _ids(state) & {"pay_agent_card_spice", "decline_agent_card_payment"}


def _context(state: GameState) -> dict[str, object]:
    return dict(state.decision_stack[-1].context)


def test_control_the_spice_is_the_printed_starting_card() -> None:
    card = STARTING_CARDS_BY_ID["control_the_spice"]

    assert card.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert card.reveal_persuasion == 1
    assert CONTROL in STARTERS


def test_control_the_spice_goes_only_to_spice_trade_spaces() -> None:
    # Every requirement met (water for the deserts, spice and two Spacing
    # Guild Influence for Shipping) so only the Agent icon limits the choice.
    owner = _owner(
        (CONTROL,),
        resources=Resources(spice=3, water=3),
        influence=Influence(spacing_guild=2),
    )

    spaces = {
        dict(action.arguments)["space_id"]
        for action in _legal(_state(owner))
        if action.action_id == "agent_turn"
    }

    assert spaces == SPICE_TRADE_SPACES


@pytest.mark.parametrize(
    "target",
    [DAGGER, DIPLOMACY, RECONNAISSANCE, CONTROL],
    ids=["hand", "discard_pile", "in_play", "itself"],
)
def test_paying_one_spice_trashes_a_card_and_recruits_a_troop(target: str) -> None:
    owner = _owner(
        (CONTROL, DAGGER),
        discard_pile=(DIPLOMACY,),
        in_play=(RECONNAISSANCE,),
        resources=Resources(spice=2),
    )
    placed = _place(_state(owner), "accept_contract")
    assert _payment_ids(placed) == {
        "pay_agent_card_spice",
        "decline_agent_card_payment",
    }

    paid = _apply(placed, "pay_agent_card_spice")

    seat = paid.players[0]
    assert seat.resources.spice == 1
    assert seat.troops_garrison == owner.troops_garrison + 1
    assert seat.troops_supply == owner.troops_supply - 1
    # The black trash icon is still optional once the spice is paid, and
    # reaches hand, discard pile and play, this card included [Main p. 20].
    assert paid.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    offered = {dict(action.arguments).get("card_id") for action in _legal(paid)}
    assert offered == {None, DAGGER, DIPLOMACY, RECONNAISSANCE, CONTROL}

    trashed = _apply(paid, "trash_optional_card", card_id=target)

    seat = trashed.players[0]
    assert seat.trashed == (target,)
    assert target not in (*seat.hand, *seat.discard_pile, *seat.in_play)
    assert seat.troops_garrison == owner.troops_garrison + 1
    top = trashed.decision_stack[-1]
    assert top.kind == FrameKind.AGENT_EFFECTS
    assert _context(trashed)["pending_agent_effect"] is False
    assert _context(trashed)["troops_recruited"] == 1
    # The arrow is chosen once: the box does not offer the payment again.
    assert not _payment_ids(trashed)


def test_paying_then_declining_the_trash_still_recruits() -> None:
    owner = _owner((CONTROL, DAGGER), resources=Resources(spice=1))
    paid = _apply(_place(_state(owner), "accept_contract"), "pay_agent_card_spice")

    declined = _apply(paid, "decline_optional_trash")

    seat = declined.players[0]
    assert seat.trashed == ()
    assert seat.resources.spice == 0
    assert seat.troops_garrison == owner.troops_garrison + 1
    assert declined.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _context(declined)["pending_agent_effect"] is False


def test_declining_the_payment_pays_and_gains_nothing() -> None:
    owner = _owner((CONTROL, DAGGER), resources=Resources(spice=3))
    placed = _place(_state(owner), "accept_contract")

    declined = _apply(placed, "decline_agent_card_payment")

    seat = declined.players[0]
    assert seat.resources.spice == 3
    assert seat.troops_garrison == owner.troops_garrison
    assert seat.trashed == ()
    assert declined.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _context(declined)["pending_agent_effect"] is False
    assert _context(declined)["troops_recruited"] == 0


def test_without_spice_only_declining_remains_until_a_spice_arrives() -> None:
    owner = _owner((CONTROL,), resources=Resources())
    placed = _place(_state(owner), "imperial_basin")

    assert _payment_ids(placed) == {"decline_agent_card_payment"}

    # The cost is judged when the box resolves in the owner's chosen order
    # (OQ-028): Imperial Basin's own spice, resolved first, pays it.
    gained = placed
    while gained.players[0].resources.spice < 1:
        gained = ENGINE.apply(
            gained,
            next(
                action
                for action in _legal(gained)
                if action.action_id in ("resolve_board_effect", "harvest_maker_spice")
            ),
        ).state
    assert _payment_ids(gained) == {
        "pay_agent_card_spice",
        "decline_agent_card_payment",
    }


def _deploy_counts(state: GameState) -> list[int]:
    return sorted(
        int(str(dict(action.arguments)["count"]))
        for action in _legal(state)
        if action.action_id == "deploy_troops"
    )


def test_the_recruited_troop_deploys_from_a_combat_space() -> None:
    # Imperial Basin is a Spice Trade Combat space (board-spaces.md:78).
    owner = _owner(
        (CONTROL,), resources=Resources(spice=1), troops_garrison=5, troops_supply=7
    )
    placed = _place(_state(owner), "imperial_basin")
    assert _deploy_counts(placed) == [1, 2]

    paid = _apply(placed, "pay_agent_card_spice")
    resumed = _apply(paid, "decline_optional_trash")

    # The new troop plus up to two more from the garrison [Main p. 10].
    assert _context(resumed)["troops_recruited"] == 1
    assert _deploy_counts(resumed) == [1, 2, 3]
    deployed = _apply(resumed, "deploy_troops", count=3)
    assert deployed.players[0].troops_conflict == 3
    assert deployed.players[0].troops_garrison == 3


def test_an_empty_supply_pays_the_spice_without_a_troop() -> None:
    # "supply에 troop이 없으면 recruit할 수 없다" [Main p. 10]; the arrow
    # still pays out its trash. Every troop is already out of the supply.
    owner = _owner(
        (CONTROL, DAGGER),
        resources=Resources(spice=1),
        troops_garrison=3,
        troops_conflict=9,
        troops_supply=0,
    )
    placed = _place(_state(owner), "accept_contract")
    transition = ENGINE.apply(placed, _find(placed, "pay_agent_card_spice"))

    seat = transition.state.players[0]
    assert seat.resources.spice == 0
    assert seat.troops_garrison == owner.troops_garrison
    assert transition.state.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert any(event.kind == "troops_recruit_short" for event in transition.events)


def test_the_trash_opens_when_the_payment_ends_the_turn() -> None:
    # Accept Contract's own icons first, so the paid box is the turn's last
    # effect and the turn closes before the trash is chosen.
    owner = _owner((CONTROL, DAGGER), resources=Resources(spice=1))
    placed = _place(_state(owner), "accept_contract")
    while "resolve_board_effect" in _ids(placed):
        placed = _apply(placed, "resolve_board_effect")

    paid = _apply(placed, "pay_agent_card_spice")

    assert paid.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH
    assert paid.decision_stack[-2].kind == FrameKind.TURN
    trashed = _apply(paid, "trash_optional_card", card_id=DAGGER)
    assert trashed.players[0].trashed == (DAGGER,)
    top = trashed.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert dict(top.context)["turn_owner"] == 1


def test_an_eliminate_allies_trash_after_the_turn_closed_is_not_credited() -> None:
    # Eliminate Allies: "When this card is trashed: 2 troops" [Eliminate
    # Allies card]. As with Throne Room Politics, a trash offered after the
    # payment closed the turn must not credit the fresh turn frame that
    # reopened for this same player (every other seat revealed) [Main p. 10]
    # [FAQ p. 4] (OQ-044 (d)).
    config = RulesetConfig(epic_game=True, bloodlines=True)
    eliminate_allies = "imperium:eliminate_allies:0"
    owner = _owner(
        (CONTROL, eliminate_allies, CONVINCING), resources=Resources(spice=1)
    )
    placed = _place(
        _state(
            owner,
            PlayerState(player_id=1, has_revealed=True),
            PlayerState(player_id=2, has_revealed=True),
            PlayerState(player_id=3, has_revealed=True),
            config=config,
        ),
        "accept_contract",
    )
    while "resolve_board_effect" in _ids(placed):
        placed = _apply(placed, "resolve_board_effect")
    paid = _apply(placed, "pay_agent_card_spice")
    assert paid.decision_stack[-1].kind == FrameKind.OPTIONAL_TRASH

    trashed = _apply(paid, "trash_optional_card", card_id=eliminate_allies)

    # The trash still recruits its two troops; only the credit was at risk.
    assert trashed.players[0].troops_garrison == owner.troops_garrison + 3
    top = trashed.decision_stack[-1]
    assert top.kind == FrameKind.TURN
    assert dict(top.context)["turn_owner"] == 0
    assert dict(top.context).get("troops_recruited") in (None, 0)


def test_reveal_gives_one_persuasion_and_one_spice() -> None:
    owner = _owner((CONTROL,), resources=Resources())
    revealed = begin_reveal_turn(
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert int(str(_context(revealed)["persuasion"])) == 1

    while actions := legal_reveal_gain_actions(revealed, 0):
        revealed = apply_reveal_gain(revealed, actions[0]).state

    assert revealed.players[0].resources.spice == 1


def test_only_epic_catalogs_gain_the_optional_trash_templates() -> None:
    # The paid trash uses the generic optional-trash frame; catalogs that
    # did not hold it (no Bloodlines, Immortality or Scouts) gain it only
    # with Epic Game Mode, so every other catalog is unchanged.
    trash = DomainAction(
        action_id="trash_optional_card", actor=0, arguments=(("card_id", CONTROL),)
    )
    for config in (
        EPIC,
        RulesetConfig(epic_game=True, choam_module=True, promo_cards=True),
        RulesetConfig(epic_game=True, bloodlines=True, tech_module=True),
        RulesetConfig(epic_game=True, immortality=True, go_to_11=True),
        RulesetConfig(epic_game=True, arrakeen_scouts=True),
    ):
        codec = _codec(config)
        for action in (
            trash,
            DomainAction(action_id="decline_optional_trash", actor=0),
            DomainAction(action_id="pay_agent_card_spice", actor=0),
        ):
            assert codec.decode(codec.encode(action), 0) == action
    base = {template.action_id for template in _codec(RulesetConfig()).catalog}
    assert "decline_optional_trash" not in base
