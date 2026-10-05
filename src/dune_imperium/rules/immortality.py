"""The Bene Tleilax board and Family Atomics (``docs/rules/immortality.md``).

- Research track: "Each time you trigger the Research icon, advance your
  research token one space to the right. Often, but not always, you will
  have a choice between two rightward directions ... When you advance to a
  research space, immediately gain the bonus shown there" [Immortality
  p. 6]. Past the second genetic marker "triggering the Research icon no
  longer advances your research token; instead, you draw a card".
- Tleilaxu track: "Each time you gain a Tleilaxu icon, advance your Tleilaxu
  token one space ... Whenever your Tleilaxu token reaches a space with a
  bonus, gain it immediately" [Immortality p. 7].
- Specimens: "take a troop from your supply and place it in the Axolotl
  tanks ... You may return any of your specimens to your supply at any
  time" [Immortality p. 8].
- Family Atomics: "Once per game, you may spend yours during your turn ...
  to remove all cards from the Imperium Row, then deal a new Imperium Row
  from the top of the Imperium Deck" [Immortality p. 12].

Rulings the official documents leave open are OQ-048 to OQ-051.
"""

from dataclasses import replace
from enum import StrEnum

from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES_BY_ID,
    TLEILAXU_TRACK,
    TLEILAXU_TRACK_END,
    ResearchBonus,
    TleilaxuBonus,
    genetic_markers_reached,
    research_next_space_ids,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import (
    draw_or_queue_intrigue_cards,
    with_trashed_intrigue,
)
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.scouts_missions import (
    HELIX,
    TLEILAXU_OFFERING_TRACK_SPACE,
    claim_goods_at,
    release_offering,
)
from dune_imperium.rules.specimens import generate_specimens, spend_specimens

__all__ = [
    "ResearchBonusBlock",
    "advance_research",
    "advance_tleilaxu",
    "apply_family_atomics",
    "apply_research_advance",
    "apply_research_bonus",
    "apply_specimen_return",
    "generate_specimens",
    "legal_family_atomics_actions",
    "legal_research_advance_actions",
    "legal_research_bonus_actions",
    "legal_specimen_return_actions",
    "move_research_token",
    "research_bonus_block",
    "spend_specimens",
]

_ADVANCE_LABEL = "Research advance frame"
_BONUS_LABEL = "Research bonus frame"
SEVEN_SOLARI_COST = 7
# Every frame kind in which its owner is "during your turn" for the freely
# timed choices (returning specimens, Family Atomics).
_OWN_TURN_FRAME_KINDS = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)


def _owner_in_own_turn(state: GameState, player: int) -> bool:
    if state.phase is not GamePhase.PLAYER_TURNS or not state.config.immortality:
        return False
    if not 0 <= player < state.config.players:
        return False
    return any(
        owned_top_frame(state, kind, player) is not None
        for kind in _OWN_TURN_FRAME_KINDS
    )


# --- specimens -----------------------------------------------------------


def legal_specimen_return_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer returning one specimen to the supply.

    "You may return any of your specimens to your supply at any time"
    [Immortality p. 8]. The engine offers it at every decision of the
    owner's own Agent or Reveal turn, at the owner's Combat Intrigue
    priority, and -- while the supply has no troop -- at the owner's Round
    Start Control defense, so the defending troop can come from a specimen
    (OQ-050; user ruling 2026-10-04 following the Steam app, which converts
    at most one specimen there).
    """

    if not 0 <= player < state.config.players or state.players[player].specimens < 1:
        return ()
    if not (
        _owner_in_own_turn(state, player)
        or _owner_at_combat_intrigue(state, player)
        or _owner_defending_without_troops(state, player)
    ):
        return ()
    return (DomainAction(action_id="return_specimen", actor=player),)


def _owner_at_combat_intrigue(state: GameState, player: int) -> bool:
    return (
        state.config.immortality
        and state.phase is GamePhase.COMBAT
        and owned_top_frame(state, FrameKind.COMBAT_INTRIGUE, player) is not None
    )


def _owner_defending_without_troops(state: GameState, player: int) -> bool:
    return (
        state.config.immortality
        and state.players[player].troops_supply == 0
        and owned_top_frame(state, FrameKind.CONTROL_DEFENSE, player) is not None
    )


def apply_specimen_return(state: GameState, action: DomainAction) -> RuleResult:
    """Return one specimen from the Axolotl tanks to the supply."""

    if action not in legal_specimen_return_actions(state, action.actor):
        raise ValueError("action is not a legal specimen return")
    owner = state.players[action.actor]
    next_owner = spend_specimens(owner, 1)
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"specimen_return:{owner.specimens}"
                ),
                kind="specimen_returned",
                payload=(("player", action.actor),),
            ),
        ),
    )


# --- Tleilaxu track ------------------------------------------------------


def tleilaxu_track_finished(owner: PlayerState) -> bool:
    """Whether the seat's Tleilaxu token is on the track's last space.

    A further advance there does nothing: "끝까지 가고 나면 뭐 없는 게
    맞다" (OQ-048, ``advance_tleilaxu``). So a cost line whose only reward
    is that advance buys nothing and is not offered: "비용이 있는 줄은 보상
    중 하나라도 무언가를 바꿀 수 있을 때만 제시한다" (OQ-071, user
    decision 2026-09-29; precedent OQ-046).
    """

    return owner.tleilaxu_space >= TLEILAXU_TRACK_END


def advance_tleilaxu(
    state: GameState,
    player: int,
    steps: int,
    *,
    source: str,
) -> RuleResult:
    """Advance the Tleilaxu token ``steps`` spaces, paying each space's bonus.

    On the last space the token stays and a further advance does nothing
    (OQ-048).
    """

    if steps < 1:
        raise ValueError("Tleilaxu advance must be positive")
    if not state.config.immortality:
        raise ValueError("the Tleilaxu track requires Immortality")
    events: list[GameEvent] = []
    working = state
    for step in range(steps):
        owner = working.players[player]
        step_source = f"{source}:tleilaxu:{step}"
        if tleilaxu_track_finished(owner):
            events.append(
                GameEvent(
                    event_id=f"{step_source}:end",
                    kind="tleilaxu_track_end",
                    payload=(("player", player),),
                )
            )
            break
        space = owner.tleilaxu_space + 1
        bonus = TLEILAXU_TRACK[space]
        next_owner = replace(owner, tleilaxu_space=space)
        payload: list[tuple[str, bool | int | str]] = [
            ("player", player),
            ("space", space),
        ]
        track_spice = working.tleilaxu_track_spice
        if bonus in (
            TleilaxuBonus.VICTORY_POINT,
            TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE,
        ):
            next_owner = replace(
                next_owner, victory_points=next_owner.victory_points + 1
            )
            payload.append(("victory_points", 1))
        if bonus is TleilaxuBonus.VICTORY_POINT_AND_FIRST_SPICE and track_spice:
            # "The first player to reach it takes an additional bonus: the
            # 2 spice that was placed here during setup" [Immortality p. 7].
            next_owner = replace(
                next_owner,
                resources=replace(
                    next_owner.resources,
                    spice=next_owner.resources.spice + track_spice,
                ),
            )
            payload.append(("spice", track_spice))
            track_spice = 0
        working = replace(
            working,
            players=replace_player(working.players, next_owner),
            tleilaxu_track_spice=track_spice,
        )
        events.append(
            GameEvent(
                event_id=step_source,
                kind="tleilaxu_advanced",
                payload=tuple(sorted(payload)),
            )
        )
        if space == TLEILAXU_OFFERING_TRACK_SPACE:
            # Arrakeen Scouts' Tleilaxu Offering waits on this space.
            offered = release_offering(working, player, source=step_source)
            working = offered.state
            events.extend(offered.events)
        if bonus is TleilaxuBonus.INTRIGUE:
            drawn = draw_or_queue_intrigue_cards(working, player, 1, source=step_source)
            working = drawn.state
            events.extend(drawn.events)
    return RuleResult(state=working, events=tuple(events))


# --- research track ------------------------------------------------------


def advance_research(state: GameState, player: int, *, source: str) -> RuleResult:
    """Trigger one Research icon for ``player``.

    Past the second genetic marker the icon draws a card instead
    [Immortality p. 6]. With a single rightward space the token moves at
    once; with two the owner chooses through a ``RESEARCH_ADVANCE`` frame.
    """

    if not state.config.immortality:
        raise ValueError("the research track requires Immortality")
    owner = state.players[player]
    if genetic_markers_reached(owner.research_space) >= 2:
        drawn = draw_or_request_personal_cards(
            state, player, 1, source=f"{source}:research_draw"
        )
        return RuleResult(
            state=drawn.state,
            events=(
                GameEvent(
                    event_id=f"{source}:research_draw",
                    kind="research_drew_card",
                    payload=(("player", player),),
                ),
                *drawn.events,
            ),
        )
    options = research_next_space_ids(owner.research_space)
    if len(options) == 1:
        return move_research_token(state, player, options[0], source=source)
    frame = DecisionFrame(
        kind=FrameKind.RESEARCH_ADVANCE,
        frame_id=f"{source}:research_advance",
        decision=PlayerDecision(
            owner=player, prompt="Choose where to advance your research token"
        ),
        context=(("player", player), ("source", source)),
    )
    return RuleResult(state=state.push_decision(frame), events=())


def legal_research_advance_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the rightward spaces the research token can move to."""

    frame = owned_top_frame(state, FrameKind.RESEARCH_ADVANCE, player)
    if frame is None:
        return ()
    owner = state.players[player]
    return tuple(
        DomainAction(
            action_id="choose_research_space",
            actor=player,
            arguments=(("space_id", space_id),),
        )
        for space_id in research_next_space_ids(owner.research_space)
    )


def apply_research_advance(state: GameState, action: DomainAction) -> RuleResult:
    """Move the token to the chosen space and pay that space's bonus."""

    if action not in legal_research_advance_actions(state, action.actor):
        raise ValueError("action is not a legal research advance")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source = context_str(context, "source", owner=_ADVANCE_LABEL)
    space_id = str(dict(action.arguments)["space_id"])
    return move_research_token(
        state.pop_decision(), action.actor, space_id, source=source
    )


def move_research_token(
    state: GameState,
    player: int,
    space_id: str,
    *,
    source: str,
) -> RuleResult:
    """Advance the token to ``space_id`` and resolve the printed bonus."""

    owner = state.players[player]
    if space_id not in research_next_space_ids(owner.research_space):
        raise ValueError("research token can only advance to a connected space")
    space = RESEARCH_SPACES_BY_ID[space_id]
    markers_before = genetic_markers_reached(owner.research_space)
    next_owner = replace(owner, research_space=space_id)
    markers = genetic_markers_reached(space_id)
    moved = replace(state, players=replace_player(state.players, next_owner))
    step_source = f"{source}:research:{space_id}"
    helix: tuple[GameEvent, ...] = ()
    if markers_before == 0 and markers:
        # Arrakeen Scouts' Sponsored Research: the spice beside the Helix
        # (the first genetic marker) goes to the next seat to reach it
        # (OQ-089 (b)).
        claimed = claim_goods_at(moved, player, HELIX, source=step_source)
        moved = claimed.state
        helix = claimed.events
    events: list[GameEvent] = [
        GameEvent(
            event_id=step_source,
            kind="research_advanced",
            payload=(
                ("bonus", space.bonus.value),
                ("genetic_markers", markers),
                ("player", player),
                ("space_id", space_id),
            ),
        )
    ]
    if markers > markers_before:
        events.append(
            GameEvent(
                event_id=f"{step_source}:marker",
                kind="genetic_marker_reached",
                payload=(("genetic_markers", markers), ("player", player)),
            )
        )
    events.extend(helix)
    bonus = _resolve_research_bonus(moved, player, space.bonus, source=step_source)
    return RuleResult(state=bonus.state, events=(*events, *bonus.events))


def _resolve_research_bonus(
    state: GameState,
    player: int,
    bonus: ResearchBonus,
    *,
    source: str,
) -> RuleResult:
    owner = state.players[player]
    match bonus:
        case ResearchBonus.NONE:
            return RuleResult(state=state, events=())
        case ResearchBonus.SPECIMEN:
            return generate_specimens(state, player, 1, source=source)
        case ResearchBonus.TLEILAXU:
            return advance_tleilaxu(state, player, 1, source=source)
        case ResearchBonus.RESEARCH:
            return advance_research(state, player, source=source)
        case ResearchBonus.TRASH_AND_SPECIMEN:
            # A black trash icon is optional [Main p. 20]; the specimen is
            # not.
            specimen = generate_specimens(state, player, 1, source=source)
            return RuleResult(
                state=specimen.state.push_decision(
                    optional_trash_frame(player, source)
                ),
                events=specimen.events,
            )
        case ResearchBonus.TLEILAXU_AND_SPECIMEN:
            specimen = generate_specimens(state, player, 1, source=source)
            advanced = advance_tleilaxu(specimen.state, player, 1, source=source)
            return RuleResult(
                state=advanced.state, events=(*specimen.events, *advanced.events)
            )
        case (
            ResearchBonus.SOLARI_ONE | ResearchBonus.SPICE_ONE | ResearchBonus.SPICE_TWO
        ):
            solari = 1 if bonus is ResearchBonus.SOLARI_ONE else 0
            spice = {
                ResearchBonus.SPICE_ONE: 1,
                ResearchBonus.SPICE_TWO: 2,
            }.get(bonus, 0)
            next_owner = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari + solari,
                    spice=owner.resources.spice + spice,
                ),
            )
            return RuleResult(
                state=replace(state, players=replace_player(state.players, next_owner)),
                events=(
                    GameEvent(
                        event_id=f"{source}:resources",
                        kind="research_resources_gained",
                        payload=(
                            ("player", player),
                            ("solari", solari),
                            ("spice", spice),
                        ),
                    ),
                ),
            )
        case (
            ResearchBonus.INFLUENCE_ANY
            | ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
            | ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
        ):
            # The window opens even when an arrow's cost cannot be paid
            # (``research_bonus_block``): its owner then confirms the lapse
            # with ``decline_research_bonus``, the only legal choice (user
            # ruling 2026-09-30, "결정 창 없이 자동으로 넘어가는 곳도 모두
            # 결정 창을 연다").
            return RuleResult(
                state=state.push_decision(
                    _bonus_frame(player, bonus, source)
                ),
                events=(),
            )


def _bonus_frame(
    player: int, bonus: ResearchBonus, source: str
) -> DecisionFrame:
    """Return the frame offering a research space's printed bonus choice."""

    return DecisionFrame(
        kind=FrameKind.RESEARCH_BONUS,
        frame_id=f"{source}:research_bonus",
        decision=PlayerDecision(
            owner=player, prompt="Resolve the research space bonus"
        ),
        context=(
            ("bonus", bonus.value),
            ("player", player),
            ("source", source),
        ),
    )


class ResearchBonusBlock(StrEnum):
    """Why a research space's arrow is not offered right now.

    Its cost cannot be paid, or (OQ-071) its reward would change nothing.

    "Trash an Intrigue card" (c7r3) takes one from the owner's hand
    [Immortality p. 16], and c8r6 costs 7 Solari [Immortality p. 3 board
    artwork]; an arrow's cost is the price of its effect ("비용을 지불하지
    않으면 효과를 얻지 못하며", docs/rules/player-turns.md [Main p. 9]
    [FAQ p. 3]). ``legal_research_bonus_actions`` offers the payment exactly
    when ``research_bonus_block`` is None, and the page's greyed-out row
    reads the same block (``display.unavailable``), so the reason shown can
    never disagree with the legal list.
    """

    NO_INTRIGUE = "no_intrigue"  # no Intrigue card in hand to trash
    SOLARI = "solari"  # fewer than 7 Solari
    # The two advances would do nothing (``tleilaxu_track_finished``).
    TLEILAXU_TRACK_END = "tleilaxu_track_end"


def research_bonus_block(
    owner: PlayerState, bonus: ResearchBonus
) -> ResearchBonusBlock | None:
    """Return why ``owner`` cannot pay ``bonus``'s arrow cost now, or None.

    None for a bonus with no cost. Reads only the owner's own Intrigue hand,
    Solari and Tleilaxu token. c8r6 is not offered once the token is on the
    track's last space: its reward would change nothing (OQ-071), so only
    the decline remains, as when the Solari are short.
    """

    if (
        bonus is ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE
        and not owner.intrigue_cards
    ):
        return ResearchBonusBlock.NO_INTRIGUE
    if (
        bonus is ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
        and tleilaxu_track_finished(owner)
    ):
        return ResearchBonusBlock.TLEILAXU_TRACK_END
    if (
        bonus is ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU
        and owner.resources.solari < SEVEN_SOLARI_COST
    ):
        return ResearchBonusBlock.SOLARI
    return None


def legal_research_bonus_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the chosen Influence, the optional trash, or the optional payment.

    While the arrow's cost cannot be paid (``research_bonus_block``) only
    ``decline_research_bonus`` is offered: the window still opens, and its
    owner confirms the lapse (user ruling 2026-09-30).
    """

    frame = owned_top_frame(state, FrameKind.RESEARCH_BONUS, player)
    if frame is None:
        return ()
    bonus = ResearchBonus(context_str(dict(frame.context), "bonus", owner=_BONUS_LABEL))
    owner = state.players[player]
    if bonus is ResearchBonus.INFLUENCE_ANY:
        return tuple(
            DomainAction(
                action_id="choose_research_influence",
                actor=player,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        )
    decline = DomainAction(action_id="decline_research_bonus", actor=player)
    if research_bonus_block(owner, bonus) is not None:
        return (decline,)
    if bonus is ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE:
        return (
            decline,
            *(
                DomainAction(
                    action_id="trash_intrigue_for_research_bonus",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in owner.intrigue_cards
            ),
        )
    if bonus is ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU:
        return (decline, DomainAction(action_id="pay_research_bonus", actor=player))
    raise RuntimeError(f"research bonus frame has no choices: {bonus}")


def apply_research_bonus(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve the research bonus choice and close its frame."""

    if action not in legal_research_bonus_actions(state, action.actor):
        raise ValueError("action is not a legal research bonus choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source = context_str(context, "source", owner=_BONUS_LABEL)
    bonus = ResearchBonus(context_str(context, "bonus", owner=_BONUS_LABEL))
    player = action.actor
    popped = state.pop_decision()
    arguments = dict(action.arguments)
    if action.action_id == "decline_research_bonus":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:bonus_declined",
                    kind="research_bonus_declined",
                    payload=(("bonus", bonus.value), ("player", player)),
                ),
            ),
        )
    if action.action_id == "choose_research_influence":
        faction = Faction(str(arguments["faction"]))
        return gain_faction_influence(
            popped,
            player,
            faction,
            1,
            event_prefix=f"{source}:influence:{faction.value}",
        )
    if action.action_id == "trash_intrigue_for_research_bonus":
        # The trashed Intrigue card joins the shared Intrigue discard before
        # the draw, so an empty deck's reshuffle can bring it back (OQ-061,
        # user ruling 2026-10-04).
        card_id = str(arguments["card_id"])
        owner = popped.players[player]
        trashed_state = with_trashed_intrigue(
            replace(
                popped,
                players=replace_player(
                    popped.players,
                    replace(
                        owner,
                        intrigue_cards=tuple(
                            held for held in owner.intrigue_cards if held != card_id
                        ),
                    ),
                ),
            ),
            card_id,
        )
        trashed_event = GameEvent(
            event_id=f"{source}:intrigue_trashed:{card_id}",
            kind="intrigue_card_trashed",
            payload=(("card_id", card_id), ("player", player)),
        )
        intrigue = draw_or_queue_intrigue_cards(
            trashed_state, player, 1, source=f"{source}:intrigue"
        )
        drawn = draw_or_request_personal_cards(
            intrigue.state, player, 1, source=f"{source}:card"
        )
        return RuleResult(
            state=drawn.state,
            events=(trashed_event, *intrigue.events, *drawn.events),
        )
    # pay_research_bonus: "7 Solari -> two Tleilaxu advances".
    owner = popped.players[player]
    paid = replace(
        owner,
        resources=replace(
            owner.resources, solari=owner.resources.solari - SEVEN_SOLARI_COST
        ),
    )
    paid_state = replace(popped, players=replace_player(popped.players, paid))
    advanced = advance_tleilaxu(paid_state, player, 2, source=source)
    return RuleResult(
        state=advanced.state,
        events=(
            GameEvent(
                event_id=f"{source}:paid",
                kind="research_bonus_paid",
                payload=(("player", player), ("solari", SEVEN_SOLARI_COST)),
            ),
            *advanced.events,
        ),
    )


# --- Family Atomics ------------------------------------------------------


def legal_family_atomics_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the once-per-game Family Atomics during the owner's turn."""

    if not _owner_in_own_turn(state, player):
        return ()
    if not state.players[player].family_atomics:
        return ()
    return (DomainAction(action_id="use_family_atomics", actor=player),)


def apply_family_atomics(state: GameState, action: DomainAction) -> RuleResult:
    """Remove the Imperium Row and deal a new one from the deck.

    The removed cards leave the game (OQ-051); the token returns to the box.
    """

    if action not in legal_family_atomics_actions(state, action.actor):
        raise ValueError("action is not a legal Family Atomics use")
    owner = state.players[action.actor]
    removed = state.imperium_row
    next_row = state.imperium_deck[:5]
    next_state = replace(
        state,
        players=replace_player(state.players, replace(owner, family_atomics=False)),
        imperium_removed=(*state.imperium_removed, *removed),
        imperium_row=next_row,
        imperium_deck=state.imperium_deck[5:],
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:family_atomics"
                ),
                kind="family_atomics_used",
                payload=(
                    ("player", action.actor),
                    ("removed", ",".join(removed)),
                ),
            ),
        ),
    )


def research_context_player(frame: DecisionFrame) -> int:
    """Return the owner recorded on a research frame (for display helpers)."""

    return context_int(dict(frame.context), "player", owner=_ADVANCE_LABEL)
