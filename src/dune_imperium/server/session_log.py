"""The server-side session log: every step, its events, and undo history.

The engine's ``GameState.event_log`` is part of the state, so taking a step
back also drops the events it produced. OQ-010 wants the opposite ("once
revealed, information stays re-checkable"), so the server keeps its own
append-only log: one ``LoggedStep`` per applied step — including steps that
were later undone — plus one ``LoggedUndo`` marker per undo. The live game
is the sequence of ``LoggedStep`` entries that are not ``undone``.

Two visibility facts are computed when a step is applied, from
``known_card_seats`` (the visibility authority in ``core.observation``):

- ``reveals``: the step let some seat learn a card it could not identify
  before, other than the actor disclosing a card only the actor knew (an
  Intrigue play, a discard from hand). Such a step cannot be undone: a draw
  would let the owner redraw with knowledge of the deck top, and a refilled
  Imperium Row or a flipped Contract cannot be un-seen. This is the M11
  slice 6 boundary the user fixed on 2026-09-02 (see implementation-plan).
- ``hidden_arguments``: action argument values naming cards that are still
  not public after the step, redacted for every seat but the actor when the
  live log is served.
- ``sealed``: the step is a seat's secret choice (``SEALED_ACTION_IDS``), so
  every one of its arguments is redacted the same way. Its value becomes
  public only through the later step that reveals it, which is a reveal in
  the sense above because the pick is listed in ``known_card_seats``.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.registry.leaders import LEADERS_BY_ID
from dune_imperium.content.registry.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import is_sealed_value_id, known_card_seats
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display.actions import combat_reward_icon_action_text
from dune_imperium.display.tokens import reveal_effect_text
from dune_imperium.display.tokens_ko import reveal_effect_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import COMBAT_INTRIGUE_PLAYED_KEY, REWARD_ICON_ACTION
from dune_imperium.rules.effect_steps import completed_whole, presents_steps
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.reveal_lines import reveal_lines

# Actions whose arguments are the acting seat's secret: Arrakeen Scouts'
# secret pick and sealed bid (docs/rules/arrakeen-scouts.md 7, 8.1). A
# single action id carries the value in its arguments, so the id itself
# tells nothing. An Agent turn's card pick is sealed too (stage B1, OQ-111
# (1): only its seat sees it until the space pick plays the card): its card
# may be one the table already knows in hand, and its graft choice is no
# card at all, so redacting the hidden card ids alone would leave them.
# The original game's Baron Harkonnen chooses his two Masterstroke Factions
# in secret too (docs/rules/imperium-base.md 14), until his deployment
# reveals them. Rise of Ix's Ilesa Ecaz sets a hand card aside face down at
# Round Start, hers alone to know until it returns at her second turn
# (docs/rules/rise-of-ix.md 13): the card is hidden once aside, so its id is
# redacted anyway, but the pick is a secret choice as a whole (a hand card
# the table knew may be the one she set aside). Rise of Ix's starting
# Contracts on Uprising are chosen in secret too, each seat's until the last.
SEALED_ACTION_IDS: Final = frozenset(
    {
        "scouts_secret_pick",
        "scouts_bid",
        "choose_agent_card",
        "choose_masterstroke_faction",
        "set_aside_leader_card",
        # Uprising with Rise of Ix and the CHOAM Module: a seat's starting
        # Contract, chosen "simultaneously" [Main p. 16] -- sealed until the
        # last seat's choice reveals every one (``rules.starting_contracts``).
        "choose_starting_contract",
    }
)
# The argument keys a sealed step shows other seats, redacted, when only
# some of its choices carry the rest: a card pick with ``graft`` would say
# it is a graft by its keys alone. Any other sealed step shows all its keys.
SEALED_SHOWN_KEYS: Final = {
    "choose_agent_card": ("card_id",),
    # The original game's Covert Operation names a Faction with two of its
    # four lines (stage P8c): its key alone would tell them apart.
    "scouts_secret_pick": ("pick",),
}
# The seat-only event of a step toward a waiting effect (``rules.effect_steps``).
EFFECT_PICKED_EVENT: Final = "effect_picked"
# The whole actions a step ends come from the rules' providers alone, so any
# engine instance gives them.
_ENGINE: Final = UprisingRulesEngine()
# Events of the step that reveals sealed choices when they fall due. The
# Masterstroke reveal (``masterstroke_revealed``) is not one: it falls due
# only on the Baron's own turn, by his own deployment, so the one seat whose
# step runs into it already knows both Factions, and its preview (the
# Conflict strength of that very deployment) shows nothing he does not.
SEALED_REVEAL_EVENTS: Final = frozenset(
    {"scouts_secret_revealed", "scouts_bid_revealed"}
)


@dataclass(frozen=True, slots=True)
class LoggedStep:
    """One applied step with the events it produced."""

    step: ReplayStep
    events: tuple[GameEvent, ...]
    reveals: bool
    hidden_arguments: frozenset[str]
    undone: bool = False
    sealed: bool = False
    # Stage B3: the whole action a step's last row of a waiting effect ends
    # (an effect and its target, as the rules resolve it), which the log
    # shows for the step; None for any other step.
    whole: DomainAction | None = None
    # A step its seat had no choice but to make (``made_without_choice``):
    # a Combat or Endgame Intrigue pass, or the winner's close of its reward
    # window, which the server makes for a human seat (user decisions
    # 2026-11-09). ``sessions._apply_step`` clears it on a pass when the
    # seat's own step came right before (a specimen returned, a wild pair
    # flipped: its unit is open and it presses the pass itself). Read off
    # the position and the log, so a load replay rebuilds it, and never
    # saved.
    without_choice: bool = False
    # The words of the printed line an event names by its index -- a
    # Conflict reward's "-OR-" line (``combat_reward_line_chosen``), a
    # Reveal line paid late (``reveal_line_granted_late``) -- as
    # ``(event_id, English, Korean)``: the log shows them, not "N번째 줄" or
    # "효과 번호: 1" (user report 2026-11-09). Read off the position, so a
    # load replay rebuilds them, and never saved; the events stay as the
    # engine logs them.
    event_words: tuple[tuple[str, str, str], ...] = ()

    @property
    def picks(self) -> bool:
        """Whether the step only picks toward a waiting effect (stage B3);
        the step that ends the effect shows it whole."""

        return any(event.kind == EFFECT_PICKED_EVENT for event in self.events)

    @property
    def actor(self) -> int | None:
        return None if isinstance(self.step, ChanceOutcome) else self.step.actor


@dataclass(frozen=True, slots=True)
class LoggedUndo:
    """``seat`` took back its ``count`` latest steps still live at this point.

    Read the log in order as a stack: every step goes on, every marker takes
    its ``count`` off the top. Those steps are flagged ``undone`` where they
    were logged, which need not be right before the marker: a second undo
    reaches past the first one's marker (``A(undone), B(undone), undo(1),
    undo(1)``).
    """

    seat: int
    count: int


# The controller a seat change hands a seat back to (``LoggedSeatChange``).
HUMAN_CONTROLLER: Final = "human"


@dataclass(frozen=True, slots=True)
class LoggedSeatChange:
    """A person's seat changed hands: an AI took it, or its person took it back.

    ``kind`` is the AI seat kind that took the seat (``app_ai``,
    ``search:<path>::...``), or ``HUMAN_CONTROLLER`` once its person took
    it back; ``seed`` is the taking agent's seed (``None`` for the person).
    The change happened before the live steps logged after it, so a load
    makes it at that point of the replay (``seat_changes``) and the agent
    regenerates the same answers. It changes no state: the game's steps and
    its chance stream are the same whoever chooses them.

    A seat's undo window never reaches across its own change
    (``undo_window``): what the AI chose is not its person's to take back,
    nor what the person chose the AI's.
    """

    seat: int
    kind: str
    seed: int | None = None

    @property
    def to_human(self) -> bool:
        return self.kind == HUMAN_CONTROLLER


type LogEntry = LoggedStep | LoggedUndo | LoggedSeatChange


def reveals_hidden_information(
    before: GameState, after: GameState, actor: int | None
) -> bool:
    """Return whether the step from ``before`` to ``after`` revealed a card.

    A card counts as revealed when a seat can identify it after the step
    but could not before. The one exception is the actor voluntarily
    disclosing a card that only the actor knew (playing an Intrigue,
    discarding or trashing from hand, revealing the hand): that is the
    actor's own loss to accept when undoing. Chance steps have no actor,
    so any of their reveals count. A starting card that a Leader pick takes
    out of the game is not a reveal either (``_removed_by_leader_pick``).
    A sealed choice falling due (an Arrakeen Scouts secret pick) is always a
    reveal, the actor's own included: the rules reveal it, not the actor, and
    exempting it would let a step's undoability tell whether any other
    seat's pick was due with it. So is the step that ends the game: once the
    game is over every hidden zone is disclosed (every hand, deck order and
    Intrigue, the shared decks; OQ-010 ruling 4), and "숨겨진 더미에서
    누군가에게 흘러간 정보(자기 draw 포함)는 되돌릴 수 없고" (OQ-010, the undo
    boundary of 2026-09-02).
    """

    if after.phase is GamePhase.FINISHED and before.phase is not GamePhase.FINISHED:
        return True
    everyone = frozenset(range(before.config.players))
    known_before = known_card_seats(before)
    known_after = known_card_seats(after)
    own_secret = frozenset({actor}) if actor is not None else None
    for card_id, seats_before in known_before.items():
        seats_after = known_after.get(card_id, everyone)
        if seats_after <= seats_before:
            continue
        if (
            own_secret is not None
            and seats_before == own_secret
            and not is_sealed_value_id(card_id)
        ):
            continue
        if card_id not in known_after and _removed_by_leader_pick(
            before, after, card_id
        ):
            continue
        return True
    return False


def _removed_by_leader_pick(before: GameState, after: GameState, card_id: str) -> bool:
    """Return whether the step's Leader pick took ``card_id`` out of the game.

    A printed setup rule removes a starting card by name as its Leader is
    drafted (Staban Tuek's Limited Allies: "You start the game without
    Diplomacy in your deck"). The card is in no zone afterwards, which
    ``known_card_seats`` reads as public, but no seat learned anything: the
    ten starting cards are common knowledge, and the pick shows nobody where
    in the shuffled deck the card sat.
    """

    for owner_before, owner_after in zip(before.players, after.players, strict=True):
        if card_id not in owner_before.deck:
            continue
        if owner_before.leader_id is not None or owner_after.leader_id is None:
            return False
        removed = LEADERS_BY_ID[owner_after.leader_id].removed_starting_card_ids
        return starting_card_for_instance(card_id).card.card_id in removed
    return False


def hidden_argument_values(step: ReplayStep, after: GameState) -> frozenset[str]:
    """Return action argument values that name a card still hidden after the step."""

    if isinstance(step, ChanceOutcome):
        return frozenset()
    known = known_card_seats(after)
    everyone = frozenset(range(after.config.players))
    return frozenset(
        value
        for _, value in step.arguments
        if isinstance(value, str) and known.get(value, everyone) != everyone
    )


def log_step(
    before: GameState,
    after: GameState,
    step: ReplayStep,
    events: tuple[GameEvent, ...],
) -> LoggedStep:
    """Build the log entry for one applied step."""

    actor = None if isinstance(step, ChanceOutcome) else step.actor
    whole = (
        completed_whole(before, step, _ENGINE.whole_actions(before, step.actor))
        if not isinstance(step, ChanceOutcome) and presents_steps(before)
        else None
    )
    hidden = hidden_argument_values(step, after)
    if whole is not None:
        hidden |= hidden_argument_values(whole, after)
    return LoggedStep(
        step=step,
        events=events,
        reveals=reveals_hidden_information(before, after, actor),
        hidden_arguments=hidden,
        whole=whole,
        event_words=event_line_words(before, events),
        without_choice=made_without_choice(before, step, whole),
        sealed=not isinstance(step, ChanceOutcome)
        and (
            step.action_id in SEALED_ACTION_IDS
            # A window's target row that ends a secret choice (a Scouts
            # secret pick's option, a sealed bid's count: stage B3d-2b).
            or (whole is not None and whole.action_id in SEALED_ACTION_IDS)
            # A step toward a waiting effect is its seat's half-pick until
            # the effect's last step (stage B3, OQ-111 (4)).
            or any(event.kind == EFFECT_PICKED_EVENT for event in events)
        ),
    )


def event_line_words(
    before: GameState, events: tuple[GameEvent, ...]
) -> tuple[tuple[str, str, str], ...]:
    """The words of the printed lines ``events`` name by their index
    (``LoggedStep.event_words``), read off the position before the step.

    A Conflict reward's chosen line reads as its row did
    (``display.actions.combat_reward_icon_action_text`` on the recipient's
    window); a Reveal line paid late reads as the card prints it
    (``display.tokens.reveal_effect_text``). Public: each names what its
    event already shows.
    """

    words: list[tuple[str, str, str]] = []
    for event in events:
        payload = dict(event.payload)
        text: tuple[str, str] | None = None
        if event.kind == "combat_reward_line_chosen":
            line, seat = payload.get("line"), payload.get("player")
            if isinstance(line, int) and isinstance(seat, int):
                text = combat_reward_icon_action_text(
                    before,
                    DomainAction(
                        action_id=REWARD_ICON_ACTION,
                        actor=seat,
                        arguments=(("effect", f"line_{line}"),),
                    ),
                )
        elif event.kind == "reveal_line_granted_late":
            card_id, index = payload.get("card_id"), payload.get("line_index")
            if isinstance(card_id, str) and isinstance(index, int):
                lines = reveal_lines(personal_card_for_instance(card_id))
                if 0 <= index < len(lines):
                    line_words = lines[index]
                    text = (
                        reveal_effect_text(line_words),
                        reveal_effect_text_ko(line_words),
                    )
        if text is not None:
            words.append((event.event_id, *text))
    return tuple(words)


COMBAT_INTRIGUE_PASS: Final = "pass_combat_intrigue"
ENDGAME_INTRIGUE_PASS: Final = "pass_endgame_intrigue"
SPECIMEN_RETURN: Final = "return_specimen"
INTRIGUE_PASSES: Final = frozenset({COMBAT_INTRIGUE_PASS, ENDGAME_INTRIGUE_PASS})
# The sole winner's close of its reward window, "no more winning Intrigue"
# (``combat.WINNING_INTRIGUE``, OQ-121 decision 6), as a whole action.
WINNING_INTRIGUE_EFFECT: Final = "winning_intrigue"


def winning_intrigue_close(seat: int) -> DomainAction:
    """The winner's close of its Conflict reward window, for ``seat``."""

    return DomainAction(
        action_id=REWARD_ICON_ACTION,
        actor=seat,
        arguments=(("effect", WINNING_INTRIGUE_EFFECT),),
    )


def _only_offered(state: GameState, seat: int, action: DomainAction) -> bool:
    """Whether ``action`` is the one whole action ``seat`` is offered but a
    specimen's return: whatever the seat does next, the window waits for
    that action alone."""

    return [
        offered
        for offered in _ENGINE.whole_actions(state, seat)
        if offered.action_id != SPECIMEN_RETURN
    ] == [action]


def _owns_top(state: GameState, seat: int, kind: FrameKind) -> bool:
    if not state.decision_stack:
        return False
    top = state.decision_stack[-1]
    return (
        top.kind == kind
        and isinstance(top.decision, PlayerDecision)
        and top.decision.owner == seat
    )


def combat_pass_without_choice(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s pending decision is a Combat Intrigue opportunity
    in which it can only pass, by public facts alone.

    The seat holds no Intrigue card, a count every seat sees; it played no
    card in this opportunity (``COMBAT_INTRIGUE_PLAYED_KEY``: its own pass
    would confirm that play); and the pass is the only action offered but
    a specimen's return [Immortality p. 8]: the seat's own windows where a
    troop may be recruited offer that return too, right before the recruit
    -- its Conflict reward window and the windows outside its turn that
    follow a row (a Contract an Alliance completes, a Tech or a Shipping
    recall's rewards; OQ-050, user decisions 2026-11-09) -- so it need not
    be asked here. The hand is read first
    and alone: a seat holding cards it cannot play now is never one, or
    this would tell what it holds. The server passes for a human seat in
    this position whose unit is closed (user request 2026-11-09,
    ``sessions._auto_pass_intrigue_locked``); one whose unit is open
    presses the pass itself.
    """

    if not _owns_top(state, seat, FrameKind.COMBAT_INTRIGUE):
        return False
    if state.players[seat].intrigue_cards:
        return False
    if dict(state.decision_stack[-1].context).get(COMBAT_INTRIGUE_PLAYED_KEY):
        return False
    return _only_offered(
        state, seat, DomainAction(action_id=COMBAT_INTRIGUE_PASS, actor=seat)
    )


def endgame_pass_without_choice(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s pending decision is its Endgame Intrigue go and it
    can only pass, by public facts alone.

    "Endgame Intrigue 카드는 게임 종료 시점에만 플레이할 수 있다. Endgame에
    들어가면 먼저 각자 가진 Endgame Intrigue를 원하는 만큼 플레이하고 해결한 뒤
    최종 Victory Point를 비교한다." [Main p. 7] [Main p. 15]
    (docs/rules/combat-and-round-end.md 9; each seat in turn, with its wild
    pairs, OQ-001). A seat holding no Intrigue card, a count every seat sees, with no
    wild pair among its face-up Objective and Conflict cards
    (``endgame._endgame_wild_matches``) is offered the pass alone; the
    server passes for it while its unit is closed (user decision
    2026-11-09, "둘 다"). A seat holding a card it cannot play is asked,
    as at Combat Intrigue.
    """

    if not _owns_top(state, seat, FrameKind.ENDGAME_INTRIGUE):
        return False
    if state.players[seat].intrigue_cards:
        return False
    return _only_offered(
        state, seat, DomainAction(action_id=ENDGAME_INTRIGUE_PASS, actor=seat)
    )


def intrigue_pass_without_choice(state: GameState, seat: int) -> DomainAction | None:
    """The Combat or Endgame Intrigue pass ``seat`` can only make now
    (``combat_pass_without_choice``, ``endgame_pass_without_choice``), if
    either."""

    if combat_pass_without_choice(state, seat):
        return DomainAction(action_id=COMBAT_INTRIGUE_PASS, actor=seat)
    if endgame_pass_without_choice(state, seat):
        return DomainAction(action_id=ENDGAME_INTRIGUE_PASS, actor=seat)
    return None


def winning_close_without_choice(state: GameState, seat: int) -> bool:
    """Whether ``seat``'s pending decision is its reward window's close and
    nothing else, by public facts alone.

    The original game's and Rise of Ix's sole Conflict winner may play a
    "When you win a Conflict" Intrigue in its reward window ("승리 책략은
    승자의 창(1위 보상과 같은 창)에서만, 보상 아이콘과 원하는 순서로 낸다"
    [DI p. 12] [FAQ p. 4], docs/rules/imperium-base.md, OQ-121), which ends
    with the close row "no more winning Intrigue" once every reward row
    is resolved (``combat.WINNING_INTRIGUE``, OQ-121 decision 6; the row
    shows while such a card is in the deck or a hand, so it tells nothing
    of the winner's hand). A winner holding no Intrigue card, a count every
    seat sees, has nothing to play once the close is all that is left: a
    reward that drew it a card leaves it holding one, and it is asked
    (a card drawn is playable at once [FAQ p. 4]). The server closes the
    window for a human seat in this position (user decision 2026-11-09,
    "둘 다"); a specimen's return offered beside it is no reason to ask,
    since no reward row is left to recruit.
    """

    if not _owns_top(state, seat, FrameKind.COMBAT_REWARD_ICONS):
        return False
    if state.players[seat].intrigue_cards:
        return False
    return _only_offered(state, seat, winning_intrigue_close(seat))


def made_without_choice(
    before: GameState, step: ReplayStep, whole: DomainAction | None = None
) -> bool:
    """Whether ``step`` is a step its seat had no choice but to make, as the
    server makes it for a human seat: a Combat or Endgame Intrigue pass, or
    the winner's close of its reward window (the whole action ``whole`` its
    row step completes), in the position above."""

    if isinstance(step, ChanceOutcome):
        return False
    action = whole or step
    if action.action_id == COMBAT_INTRIGUE_PASS:
        return combat_pass_without_choice(before, action.actor)
    if action.action_id == ENDGAME_INTRIGUE_PASS:
        return endgame_pass_without_choice(before, action.actor)
    if action == winning_intrigue_close(action.actor):
        return winning_close_without_choice(before, action.actor)
    return False


def live_steps(log: list[LogEntry]) -> list[LoggedStep]:
    """Return the log entries that make up the current game, in order."""

    return [
        entry
        for entry in log
        if isinstance(entry, LoggedStep) and not entry.undone
    ]


def undo_window(log: list[LogEntry], seat: int) -> int:
    """Count how many trailing live steps ``seat`` may take back.

    The window holds the seat's own consecutive latest actions and closes
    at the first step that is a chance outcome, another seat's action, or
    a step that revealed hidden information (which cannot be undone
    itself, so the window closes below it). It closes at the seat's own
    change of hands too (``LoggedSeatChange``); another seat's change
    touches no state and does not close it.
    """

    count = 0
    for entry in reversed(log):
        if isinstance(entry, LoggedSeatChange):
            if entry.seat == seat:
                break
            continue
        if isinstance(entry, LoggedUndo) or entry.undone:
            continue
        if entry.actor != seat or entry.reveals:
            break
        count += 1
    return count


def seat_changes(
    log: Iterable[LogEntry | tuple[ReplayStep, bool]],
) -> list[tuple[int, LoggedSeatChange]]:
    """Every seat change with the live step count logged before it.

    That count is where the change happened in the live game: steps an undo
    took back later do not count, so a change logged while another seat's
    steps were still open sits before whatever replaced them. ``log`` is a
    session's log or a save's (whose steps are ``(step, undone)`` pairs).
    """

    changes: list[tuple[int, LoggedSeatChange]] = []
    live_position = 0
    for entry in log:
        if isinstance(entry, LoggedSeatChange):
            changes.append((live_position, entry))
        elif isinstance(entry, LoggedStep):
            live_position += not entry.undone
        elif isinstance(entry, tuple):
            live_position += not entry[1]
    return changes


def mark_undone(log: list[LogEntry], seat: int, count: int) -> None:
    """Flag the last ``count`` live steps as undone and append the marker."""

    remaining = count
    for index in range(len(log) - 1, -1, -1):
        if remaining == 0:
            break
        entry = log[index]
        if isinstance(entry, LoggedStep) and not entry.undone:
            if entry.actor != seat:
                raise ValueError("cannot undo another seat's step")
            log[index] = replace(entry, undone=True)
            remaining -= 1
    if remaining:
        raise ValueError("fewer live steps than the undo count")
    log.append(LoggedUndo(seat=seat, count=count))


def undo_history(log: list[LogEntry]) -> list[tuple[int, LoggedUndo, list[LoggedStep]]]:
    """Return every undo as (live step index it rewound to, marker, undone steps).

    The index counts the live steps of the final game logged before the
    marker; the undone steps are the ones the marker took off the stack
    (``LoggedUndo``), in the order they were taken.
    """

    history: list[tuple[int, LoggedUndo, list[LoggedStep]]] = []
    live_position = 0
    # Undone steps logged but not yet taken off by their marker; nothing
    # live can sit above them, since a marker only takes the top.
    in_play: list[LoggedStep] = []
    for entry in log:
        if isinstance(entry, LoggedSeatChange):
            continue
        if isinstance(entry, LoggedUndo):
            history.append((live_position, entry, in_play[-entry.count :]))
            del in_play[-entry.count :]
        elif entry.undone:
            in_play.append(entry)
        else:
            live_position += 1
    return history

