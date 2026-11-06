"""Rise of Ix's starting Contracts on Uprising (stage P7f-2).

"Playing the CHOAM Module with RISE OF IX ... UPRISING includes 10
additional contracts (with different backs) to use specifically when
playing with RISE OF IX. After setting up the 20 standard contracts, shuffle
the 10 RISE OF IX contracts and give two to each player. Each player looks
at the two they've been given, choosing simultaneously which contract they
want to begin the game with (placing it face up in their supply). Return all
of the unchosen RISE OF IX contracts to the box." [Main p. 16]
(docs/rules/choam-module.md).

- **Shuffle.** Setup shuffles the ten tiles into ``GameState.contract_box``
  right after the standard Contracts (``rules.setup``), a chance decision of
  its own that only this combination draws, so no other game's chance stream
  moves.
- **Deal** (``deal_starting_contracts``). The box's top two go to each seat,
  from the First Player clockwise (the order of the choice below, and the
  app's, P7g A6), once every Leader is known: at once without the Leader draft,
  after the draft's last pick with it -- as Epic Game Mode's setup Intrigue
  card is dealt once every Leader is known [Rise of Ix p. 10]
  (``rules.setup.deal_setup_intrigue``), so no seat picks its Leader while
  holding its two. The rulebook orders neither the deal nor the Leaders
  around it (project convention, OQ-161 (1)).
- **Choice.** "Choosing simultaneously" is a sealed choice each seat makes in
  turn from the First Player, clockwise (the order of every seat-by-seat
  setup or Scouts choice, OQ-071; an engine reason, OQ-161 (2)), in a
  ``FrameKind.STARTING_CONTRACT``
  frame that pauses the game in SETUP like the Baron's Masterstroke: a
  seat's two tiles and its choice are its own (``core.observation``'s
  registry and private view, ``server.session_log``'s sealed action), so a
  later chooser learns nothing from an earlier one but that it has chosen.
- **Reveal.** The last choice turns every chosen tile face up into its
  seat's active Contracts and returns the unchosen ones to the box, face
  down. None of the ten completes when taken (each needs a visit or a
  harvest, ``content.rise_of_ix.contracts.IX_CONTRACTS``).
"""

from copy import replace
from typing import Final

from dune_imperium.content.rise_of_ix.contracts import IX_CONTRACTS
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
)

CHOOSE_ACTION: Final = "choose_starting_contract"
STARTING_CONTRACTS_PER_SEAT: Final = 2
PROMPT: Final = "Choose your starting Contract"
_FRAME: Final = "Starting Contract frame"
_RESUME_KEY: Final = "resume_phase"


def _frame(player: int, resume: GamePhase) -> DecisionFrame:
    return DecisionFrame(
        kind=FrameKind.STARTING_CONTRACT,
        frame_id=f"setup:starting_contract:{player}",
        decision=PlayerDecision(owner=player, prompt=PROMPT),
        context=(("player", player), (_RESUME_KEY, resume.value)),
    )


def _next_chooser(state: GameState) -> int | None:
    """The next seat from the First Player, clockwise, still to choose."""

    first = state.first_player or 0
    for offset in range(state.config.players):
        seat = state.players[(first + offset) % state.config.players]
        if seat.starting_contract_ids and not seat.starting_contract_pick:
            return seat.player_id
    return None


def deal_starting_contracts(state: GameState) -> GameState:
    """Give each seat the box's next two Rise of Ix tiles and open the first
    seat's choice; a game whose box holds none is returned itself."""

    if len(state.contract_box) != len(IX_CONTRACTS):
        # Not dealt yet only while every tile is in the box.
        return state
    box = state.contract_box
    seats = state.config.players
    first = state.first_player or 0
    players = list(state.players)
    for turn in range(seats):
        seat = (first + turn) % seats
        players[seat] = replace(
            players[seat],
            starting_contract_ids=box[
                turn * STARTING_CONTRACTS_PER_SEAT : (turn + 1)
                * STARTING_CONTRACTS_PER_SEAT
            ],
        )
    dealt = replace(
        state,
        players=tuple(players),
        contract_box=box[STARTING_CONTRACTS_PER_SEAT * len(players) :],
    )
    chooser = _next_chooser(dealt)
    assert chooser is not None
    return replace(
        dealt,
        phase=GamePhase.SETUP,
        decision_stack=(*dealt.decision_stack, _frame(chooser, state.phase)),
    )


def legal_starting_contract_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Either of the two tiles the seat was given."""

    if owned_top_frame(state, FrameKind.STARTING_CONTRACT, player) is None:
        return ()
    return tuple(
        DomainAction(
            action_id=CHOOSE_ACTION,
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in state.players[player].starting_contract_ids
    )


def apply_starting_contract_choice(
    state: GameState, action: DomainAction
) -> RuleResult:
    """Seal the seat's choice; the last one reveals every seat's."""

    player = action.actor
    if action not in legal_starting_contract_actions(state, player):
        raise ValueError("action is not a legal starting Contract choice")
    frame = state.decision_stack[-1]
    resume = GamePhase(context_str(dict(frame.context), _RESUME_KEY, owner=_FRAME))
    instance_id = str(dict(action.arguments)["instance_id"])
    chosen = replace(state.players[player], starting_contract_pick=instance_id)
    state = replace(
        state,
        players=replace_player(state.players, chosen),
        decision_stack=state.decision_stack[:-1],
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{frame.frame_id}:chosen",
            kind="starting_contract_chosen",
            payload=(("player", player),),
        ),
        GameEvent(
            event_id=f"{frame.frame_id}:identity",
            kind="starting_contract_identity",
            payload=(("contract_id", instance_id), ("player", player)),
            visible_to=(player,),
        ),
    ]
    chooser = _next_chooser(state)
    if chooser is not None:
        return RuleResult(
            state=replace(
                state, decision_stack=(*state.decision_stack, _frame(chooser, resume))
            ),
            events=tuple(events),
        )
    returned: list[str] = []
    players = []
    for seat in state.players:
        pick = seat.starting_contract_pick
        returned.extend(card for card in seat.starting_contract_ids if card != pick)
        players.append(
            replace(
                seat,
                active_contract_ids=(*seat.active_contract_ids, pick),
                starting_contract_ids=(),
                starting_contract_pick="",
            )
        )
        events.append(
            GameEvent(
                event_id=f"setup:starting_contract:{seat.player_id}:revealed",
                kind="starting_contract_revealed",
                payload=(("contract_id", pick), ("player", seat.player_id)),
            )
        )
    return RuleResult(
        state=replace(
            state,
            phase=resume,
            players=tuple(players),
            contract_box=(*state.contract_box, *returned),
        ),
        events=tuple(events),
    )
