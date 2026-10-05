"""Small typed effects and pending-effect frame utilities."""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    contract_for_instance,
)
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    card_is_ghola,
    personal_card_for_instance,
)
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind, owes_track_spy, reset_turn_counters
from dune_imperium.rules.strength import conflict_agent_strength


@dataclass(frozen=True, slots=True)
class GainResourcesEffect:
    """Gain public spendable resources from the bank."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource gains must not be negative")
        if self.solari == self.spice == self.water == 0:
            raise ValueError("a resource-gain effect must gain something")


@dataclass(frozen=True, slots=True)
class DrawImperiumCardsEffect:
    """Draw cards from the current player's personal deck."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("card draw count must be positive")


@dataclass(frozen=True, slots=True)
class DrawIntrigueCardsEffect:
    """Draw hidden cards from the shared Intrigue deck."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Intrigue draw count must be positive")


@dataclass(frozen=True, slots=True)
class RecruitTroopsEffect:
    """Recruit as many troops as possible up to ``count``."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("troop recruit count must be positive")


@dataclass(frozen=True, slots=True)
class ResearchEffect:
    """Advance the research token (Immortality's revised Research Station).

    "Draw two cards and research" [Immortality p. 16]; the advance may open
    a direction choice for the owner [Immortality p. 6].
    """


type AutomaticEffect = (
    GainResourcesEffect
    | DrawImperiumCardsEffect
    | DrawIntrigueCardsEffect
    | RecruitTroopsEffect
    | ResearchEffect
)


def recruit_troops(player: PlayerState, count: int) -> tuple[PlayerState, int]:
    """Move up to ``count`` available troops from supply to garrison.

    What the supply cannot cover is recorded as ``ungained_troops``; the
    engine recruits it if troops return to the supply later in the same
    player turn (OQ-030, user ruling 2026-10-04, ``rules.shortfall``).
    """

    if count < 0:
        raise ValueError("troop recruit count must not be negative")
    recruited = min(player.troops_supply, count)
    return (
        replace(
            player,
            troops_supply=player.troops_supply - recruited,
            troops_garrison=player.troops_garrison + recruited,
            ungained_troops=player.ungained_troops + count - recruited,
        ),
        recruited,
    )


def recruit_shortfall_events(
    source: str, player: int, requested: int, recruited: int
) -> tuple[GameEvent, ...]:
    """Return the public event noting a recruit the supply could not cover in full."""
    if recruited >= requested:
        return ()
    return (
        GameEvent(
            event_id=f"{source}:recruit_short",
            kind="troops_recruit_short",
            payload=(
                ("player", player),
                ("recruited", recruited),
                ("requested", requested),
                ("short", requested - recruited),
            ),
        ),
    )


AGENT_EFFECT_CONTEXT_KEYS = frozenset(
    {
        "board_icons",
        "card_id",
        "cost_option",
        # Immortality Graft [Immortality p. 10]: the second played card and
        # its own pending Agent box ("" / False / "" for a single-card play).
        "graft_card_id",
        "graft_pending_effect",
        "graft_pending_icons",
        "pending_agent_effect",
        "pending_board_effect",
        "pending_board_icons",
        "pending_combat_deployment",
        "pending_faction_influence",
        "space_id",
        "spice_at_placement",
        "spice_spent_after_placement",
        "troops_recruited",
        "turn_owner",
    }
)


def open_next_turn(state: GameState, player: int) -> GameState:
    """Replace ``player``'s turn frame with the next unrevealed seat's turn.

    "Pass your turn" (Litany Against Fear, Withdrawn): the seat stays
    unrevealed and comes around again this round. An Emperor track Spy the
    seat still owes is placed before its turn ends (user ruling 2026-10-04);
    the turn-passing plays never meet one, since they are only the turn's
    first action and only an action of the turn leaves a Spy waiting in it
    (OQ-095 (6), user ruling 2026-10-04), so an owed Spy here is a bug.
    """

    if owes_track_spy(state, player):
        raise RuntimeError("a turn cannot pass over an owed Emperor track Spy")
    next_player = next_unrevealed_player(state, player)
    players = reset_turn_counters(state.players, next_player, closing=player)
    frames = list(state.decision_stack)
    for index in range(len(frames) - 1, -1, -1):
        frame = frames[index]
        if frame.kind == FrameKind.TURN and isinstance(frame.decision, PlayerDecision):
            if frame.decision.owner != player:
                raise RuntimeError("only the turn owner can pass the turn")
            frames[index] = DecisionFrame(
                kind=FrameKind.TURN,
                frame_id=f"round:{state.round_number}:turn:{next_player}",
                decision=PlayerDecision(
                    owner=next_player,
                    prompt="Choose an Agent turn or Reveal turn",
                ),
                context=(("round", state.round_number), ("turn_owner", next_player)),
            )
            break
    else:
        raise RuntimeError("passing the turn needs an open turn frame")
    return replace(state, players=players, decision_stack=tuple(frames))


def agent_turn_space_id(state: GameState, player: int) -> str | None:
    """Return the board space ``player`` sent an Agent to this turn, if any.

    Read from the player's open Agent-turn effect frame anywhere in the
    stack (an Intrigue choice may sit above it).
    """

    for frame in reversed(state.decision_stack):
        if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
            frame.decision, PlayerDecision
        ):
            continue
        if frame.decision.owner != player:
            continue
        space_id = dict(frame.context).get("space_id")
        return space_id if isinstance(space_id, str) else None
    return None


def current_agent_effect_context(
    state: GameState,
) -> tuple[DecisionFrame, dict[str, ActionValue]]:
    """Return and validate the current Agent-turn effect frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Agent-turn effect frame")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        raise ValueError("the current decision is not an Agent-turn effect")
    context = dict(frame.context)
    if not AGENT_EFFECT_CONTEXT_KEYS.issubset(context):
        raise ValueError("the Agent-turn effect frame is missing context")
    return frame, context


def pending_board_icons(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """Return the visited space's icons still waiting for their own action.

    ``board_icons`` holds every printed icon of the visit in printed order and
    ``pending_board_icons`` the ones not yet resolved; each icon is one
    independently ordered effect [Main p. 9] (OQ-027). ``pending_board_effect``
    stays the group-level flag the frame's turn-passing logic reads.
    """

    return _icon_keys(context, "pending_board_icons")


def board_icon_is_pending(context: Mapping[str, ActionValue], key: str) -> bool:
    """Return whether the visited space's ``key`` icon still awaits its action."""

    return key in pending_board_icons(context)


def finish_board_icon(context: dict[str, ActionValue], key: str) -> None:
    """Retire one resolved icon and keep the board-effect group flag in step."""

    remaining = list(pending_board_icons(context))
    if key not in remaining:
        raise ValueError(f"board icon is not pending: {key}")
    remaining.remove(key)
    context["pending_board_icons"] = ",".join(remaining)
    context["pending_board_effect"] = bool(remaining)


def add_board_icon(context: dict[str, ActionValue], key: str) -> None:
    """Queue one more freely ordered effect of the visit, unlocked by an icon
    just resolved (Arrakeen Scouts: the new High Council seat's
    subcommittee, OQ-076).

    It joins ``pending_board_icons`` only, not the printed ``board_icons``,
    so a repeat of the printed effects never re-arms it."""

    icons = pending_board_icons(context)
    if key in icons:
        raise ValueError(f"board icon is already pending: {key}")
    context["pending_board_icons"] = ",".join((*icons, key))
    context["pending_board_effect"] = True


def pending_agent_icons(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """Return the played card's Agent-box icons still waiting for their action.

    A card whose Agent box prints several independent icons resolves them
    one action each in the owner's order [Main p. 9] (OQ-027); the list is
    empty for single-effect boxes, which keep the plain resolution action.
    """

    return _icon_keys(context, "pending_agent_icons")


def arm_agent_icons(context: dict[str, ActionValue], icons: tuple[str, ...]) -> None:
    """Queue the played card's printed icons, each for its own action."""

    context["pending_agent_icons"] = ",".join(icons)
    context["pending_agent_effect"] = bool(icons)


def finish_agent_icon(context: dict[str, ActionValue], key: str) -> None:
    """Retire one resolved Agent-box icon and keep the card's group flag in step."""

    remaining = list(pending_agent_icons(context))
    if key not in remaining:
        raise ValueError(f"Agent-card icon is not pending: {key}")
    remaining.remove(key)
    context["pending_agent_icons"] = ",".join(remaining)
    context["pending_agent_effect"] = bool(remaining)


# The Bloodlines Sardaukar Commander offer of a visited space: "an effect of
# the space" ordered freely with the printed icons [Bloodlines p. 4], but not
# a printed icon, so a repeat of the printed effects never re-arms it.
BOARD_ICON_COMMANDER = "sardaukar_commander"
# The Tech Module's Acquire Tech offer of a Landsraad visit: the Ixian
# Embassy board "gives you this option each time you send an Agent to a
# Landsraad board space" [Bloodlines pp. 7, 12]; like the Commander it is an
# effect of the visit, not a printed icon.
BOARD_ICON_TECH = "tech"


def is_grafted(context: Mapping[str, ActionValue]) -> bool:
    """Return whether this Agent turn plays two grafted cards [Immortality p. 11]."""

    return bool(context.get("graft_card_id"))


def other_grafted_card_id(context: Mapping[str, ActionValue]) -> str:
    """Return "the other grafted card" of the box being resolved ("" if none).

    The active box's card sits in ``card_id`` and its partner in
    ``graft_card_id``; ``switch_graft_card`` swaps them, so the partner is
    always the inactive one.
    """

    value = context.get("graft_card_id", "")
    return value if isinstance(value, str) else ""


def borrowed_agent_card(
    card: PersonalCardDefinition, partner_id: str
) -> PersonalCardDefinition:
    """Return ``card`` with Ghola's borrowed box: the other grafted card's.

    "This card has the same Agent box as the other grafted card" [Ghola
    card face], and "Ghola copies the entire Agent box of the card it's
    grafted to" [Immortality p. 14]: the effect together with the box's
    limit on where its Spy may go (Reliable Informant's "[Spy] on ..."
    [Main p. 20]). Every other card keeps its own definition.
    """

    if not partner_id or not card_is_ghola(card):
        return card
    partner = personal_card_for_instance(partner_id)
    return replace(
        card,
        agent_effect=partner.agent_effect,
        agent_spy_factions=partner.agent_spy_factions,
    )


def active_agent_card(context: Mapping[str, ActionValue]) -> PersonalCardDefinition:
    """Return the definition whose Agent box the effect frame is resolving."""

    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        raise RuntimeError("Agent-turn effect frame has invalid card ID")
    return borrowed_agent_card(
        personal_card_for_instance(card_id), other_grafted_card_id(context)
    )


def rearm_board_icons(context: dict[str, ActionValue]) -> None:
    """Queue every printed icon of the visit again (Reverend Mother's repeat)."""

    icons = tuple(
        key
        for key in _icon_keys(context, "board_icons")
        if key not in (BOARD_ICON_COMMANDER, BOARD_ICON_TECH)
    )
    context["pending_board_icons"] = ",".join(icons)
    context["pending_board_effect"] = bool(icons)


def _icon_keys(context: Mapping[str, ActionValue], name: str) -> tuple[str, ...]:
    value = context.get(name, "")
    if not isinstance(value, str):
        raise RuntimeError(f"Agent-turn effect frame has invalid {name}")
    return tuple(key for key in value.split(",") if key)


def _owner_effect_frame(state: GameState, owner: int) -> DecisionFrame:
    """Return the top frame, checked to be ``owner``'s Agent-turn effect frame."""

    frame = state.decision_stack[-1] if state.decision_stack else None
    if (
        frame is None
        or frame.kind != FrameKind.AGENT_EFFECTS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != owner
    ):
        raise RuntimeError("the owner's Agent-turn effect frame must be on top")
    return frame


def advance_after_effect(
    state: GameState,
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...] | None = None,
) -> GameState:
    """Write the effect frame's context back; the turn stays open.

    An Agent turn ends only through its owner's ``finish_agent_turn``, even
    when nothing is left to resolve (user ruling OQ-095): until then the
    owner may still play a Plot Intrigue [Main p. 8], use Family Atomics
    [Immortality p. 12], return a specimen [Immortality p. 8], flip a Tech
    tile [Bloodlines pp. 7, 12] or recruit a Commander [Bloodlines p. 4].
    """

    owner = context["turn_owner"]
    if isinstance(owner, bool) or not isinstance(owner, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    frame = _owner_effect_frame(state, owner)
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(
        state,
        players=state.players if players is None else players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )


def close_agent_turn(state: GameState, owner: int) -> GameState:
    """End ``owner``'s Agent turn and open the next unrevealed seat's turn.

    The one place an Agent turn closes (OQ-095): ``finish_agent_turn`` calls
    it once the press's own steps are done. Whatever the turn's effects left
    behind has been resolved on top of the owner's open frame before the
    end was offered, so nothing of this turn reaches the next one.
    """

    _owner_effect_frame(state, owner)
    seat = state.players[owner]
    if seat.usurped_row_card_id:
        raise RuntimeError("the Usurped card is trashed before the turn closes")
    if (
        any(entry[0] == owner for entry in state.pending_skill_choices)
        or any(entry[0] == owner for entry in state.pending_navigation_plays)
    ):
        raise RuntimeError("an Agent turn cannot close over its queued choices")
    if owes_track_spy(state, owner):
        # Placed in any order, but before the turn ends (user ruling
        # 2026-10-04, overriding OQ-057 (15)).
        raise RuntimeError("an Agent turn cannot close over an owed track Spy")
    next_player = next_unrevealed_player(state, owner)
    players = reset_turn_counters(state.players, next_player, closing=owner)
    next_frame = DecisionFrame(
        kind=FrameKind.TURN,
        frame_id=f"round:{state.round_number}:turn:{next_player}",
        decision=PlayerDecision(
            owner=next_player,
            prompt="Choose an Agent turn or Reveal turn",
        ),
        context=(("round", state.round_number), ("turn_owner", next_player)),
    )
    return replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )


def agent_turn_has_other_pending_effects(
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...],
    *,
    ignore_agent_effect: bool = False,
) -> bool:
    """Return whether a mandatory group of the turn is still pending.

    The Combat deployment window is not one: it stays open until the owner
    finishes the turn (OQ-029, OQ-095). With ``ignore_agent_effect`` a
    pending Agent box is left out — the explicit turn end asks this when
    that box can only fizzle (OQ-057).
    """

    regular_pending = (
        context.get("pending_gather_intelligence", False),
        context.get("pending_leader_ability", False),
        context.get("pending_leader_board_repeat", False),
        False if ignore_agent_effect else context["pending_agent_effect"],
        False if ignore_agent_effect else context.get("graft_pending_effect", False),
        context["pending_board_effect"],
        context["pending_faction_influence"],
    )
    if any(value is True for value in regular_pending):
        return True
    return bool(eligible_agent_contract_ids(context, players))


def pending_agent_contract_ids(
    context: dict[str, ActionValue],
) -> tuple[str, ...]:
    """Decode the Agent-frame snapshot of Contracts held at placement time."""

    value = context.get("pending_contract_ids", "")
    if not isinstance(value, str):
        raise RuntimeError("Agent-turn effect frame has invalid Contract IDs")
    return tuple(instance_id for instance_id in value.split(",") if instance_id)


def eligible_agent_contract_ids(
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...],
) -> tuple[str, ...]:
    """Return snapshot Contracts whose completion condition is now satisfied."""

    owner_value = context.get("turn_owner")
    if isinstance(owner_value, bool) or not isinstance(owner_value, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    if not 0 <= owner_value < len(players):
        raise RuntimeError("Agent-turn effect frame owner is outside player state")
    owner = players[owner_value]
    # "Harvest contract는 Maker space에 Agent를 보내고, 그 turn에 모든 출처를
    # 합쳐 contract에 표시된 양의 spice를 얻으면 완료한다." [Main p. 16]
    # (docs/rules/choam-module.md:26). The whole turn counts, so spice gained
    # before the placement -- a Plot played on the turn frame first (OQ-015
    # (a)) -- adds to the Maker space's own, as in the Steam app; counting
    # only from the placement left it out. ``spice_at_turn_start`` is
    # snapshotted when the owner's turn opens and every spend adds to
    # ``spice_spent_turn``, so spending later in the turn cannot undo a met
    # threshold (the reading of ``agent_effects.spice_gained_this_turn``).
    # Which Contracts may complete is still the placement snapshot below.
    spice_gained = (
        owner.resources.spice - owner.spice_at_turn_start + owner.spice_spent_turn
    )

    eligible: list[str] = []
    for instance_id in pending_agent_contract_ids(context):
        if instance_id not in owner.active_contract_ids:
            continue
        condition = contract_for_instance(instance_id).condition
        if condition.kind is ContractConditionKind.BOARD_SPACE or (
            condition.kind is ContractConditionKind.HARVEST_SPICE
            and spice_gained >= condition.amount
        ):
            eligible.append(instance_id)
    return tuple(eligible)


def turn_agent_in_conflict(
    owner: PlayerState, context: Mapping[str, ActionValue], turn_space_id: str
) -> bool:
    """Return whether Into the Fray moved this turn's Agent to the Conflict.

    Every Recall Agent effect excludes the Agent sent there this turn, per
    the printed Recall Agent icon: "Return one of your other Agents on the
    board to your Leader (not the Agent you sent during this turn)."
    [Main p. 20]. Imperial Privilege's own wording is "Recall one of your
    other Agents from the board" [Board Guide p. 2], and the Contract
    reward (Sardaukar II, the Bloodlines High Council token) prints the
    same Recall Agent icon. An Into the Fray Agent is one of "your Agents"
    that may be recalled only on a later turn (designer ruling adopted as
    OQ-037 (d), extended to every Recall Agent effect by the 2026-09-26 user
    ruling, OQ-068). While the effect is pending, this turn's Agent is
    still on ``turn_space_id``, or Into the Fray has moved it to the
    Conflict, or Twisted Mentat's "You may recall the Agent you sent this
    turn." [Twisted Mentat card] has already sent it home
    (``turn_agent_recalled``), which leaves every Conflict Agent an earlier
    turn's.
    """

    return (
        turn_space_id not in owner.agent_locations
        and context.get("turn_agent_recalled") is not True
    )


def recallable_conflict_agents(owner: PlayerState, *, sent_this_turn: bool) -> int:
    """Count the owner's Conflict Agents a Recall Agent effect may target.

    The Recall Agent icon, "Return one of your other Agents on the board to
    your Leader (not the Agent you sent during this turn)." [Main p. 20],
    excludes the Agent sent there this turn (OQ-068); every other Conflict
    Agent, an earlier turn's Into the Fray Agent, is one of the "other"
    Agents (OQ-037 (d)).
    """

    return max(0, owner.agent_in_conflict - (1 if sent_this_turn else 0))


def recall_conflict_agent(
    owner: PlayerState,
    *,
    player: int,
    source: str,
    event_id: str,
    source_key: str = "source",
) -> tuple[PlayerState, GameEvent]:
    """Return the owner with one Conflict Agent recalled, and its event.

    The recalled Agent leaves the Conflict as a unit and returns to its
    Leader (OQ-037 (d), extended to every Recall Agent effect by the
    2026-09-26 user ruling, OQ-068). It fought as "a 2 strength unit ... If
    you have your Swordmaster, it has 3 strength instead." [Duncan Idaho
    card], so the running Combat strength loses that much here, as
    ``units.retreat_units`` does for a troop: "Conflict에 unit이 하나 이상
    있어야 strength를 가질 수 있다. 마지막 unit이 제거되면 sword가 남아
    있어도 strength는 0이 된다." [Main p. 12] (docs/rules/player-turns.md).
    Before the seat's Reveal ``refresh_pre_reveal_strength`` re-derives the
    same value from the unit counts; during it (Contingencies joined
    through Corrinth City's seat, OQ-075) this is what moves the total, and
    the caller keeps the Reveal frame's tally in step [Main p. 13]. One
    recall brings back one Agent, even when a Servo-Receivers Signet sent a
    second one (OQ-037 (e)). ``source_key`` names the payload key
    ``source`` is filed under, so each caller's ``agent_recalled`` event
    keeps the same shape its own board recall already uses (Steersman's
    Agent-card recall uses ``card_id``; Imperial Privilege and the Contract
    reward use ``source``).
    """

    if owner.agent_in_conflict <= 0:
        raise RuntimeError("owner has no Conflict Agent left to recall")
    remaining_units = owner.units_in_conflict - 1
    next_owner = replace(
        owner,
        agents_available=owner.agents_available + 1,
        agent_in_conflict=owner.agent_in_conflict - 1,
        combat_strength=(
            max(owner.combat_strength - conflict_agent_strength(owner), 0)
            if remaining_units > 0
            else 0
        ),
    )
    event = GameEvent(
        event_id=event_id,
        kind="agent_recalled",
        # GameEvent requires the payload sorted by key name, and the key
        # named by ``source_key`` sorts differently depending on its name
        # ("card_id" before "player"; "source" after it).
        payload=tuple(
            sorted(
                (
                    ("player", player),
                    (source_key, source),
                    ("space_id", "conflict"),
                )
            )
        ),
    )
    return next_owner, event


def next_unrevealed_player(state: GameState, owner: int) -> int:
    """Return the next clockwise seat that has not taken its Reveal turn."""

    for offset in range(1, state.config.players + 1):
        candidate = (owner + offset) % state.config.players
        if not state.players[candidate].has_revealed:
            return candidate
    raise RuntimeError("no unrevealed player remains during Player Turns")
