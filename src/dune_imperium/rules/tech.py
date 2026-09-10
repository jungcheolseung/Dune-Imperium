"""The Tech Module's Acquire Tech decision (``docs/rules/bloodlines.md`` §5).

"The Acquire Tech icon is the only way to acquire a Tech tile"
[Bloodlines p. 7]. Two decision points open it:

- A Landsraad visit: "during a turn in which you send an Agent to a
  Landsraad board space, you may acquire one Tech tile" [Bloodlines p. 7].
  The offer is one more freely ordered effect of the visit
  (``BOARD_ICON_TECH`` on the Agent-turn effect frame).
- A card's Tech Discount icon (Battlefield Research, Rapid Engineering): a
  ``TECH_ACQUISITION`` frame carrying the discount [Bloodlines pp. 7, 12].

Either way the owner chooses ``acquire_tech(tech_id, ...)`` for a face-up
tile on top of a stack (or Kota Odax's Secret Project tile), pays its spice
cost less the discounts (never below zero), puts it in the supply and turns
the stack's next tile face up; the tile's acquire effect pays once
[Bloodlines p. 7]. ``decline_tech`` refuses the offer.
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import (
    HIGH_COUNCIL_TECH_DISCOUNT,
    TECH_TILES_BY_ID,
    TechAbility,
    TechTile,
    has_tech,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import with_recruited_units
from dune_imperium.rules.combat_deployment import grant_combat_icon
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    BOARD_ICON_TECH,
    advance_after_effect,
    board_icon_is_pending,
    current_agent_effect_context,
    finish_board_icon,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    reveal_is_open_for,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.ornithopter import (
    has_ornithopter_fleet,
    match_all_battle_icons,
)
from dune_imperium.rules.reveal_turn import (
    TECH_PENDING_KEY,
    add_reveal_optional_sword_strength,
    add_reveal_strength,
    add_units_to_reveal,
    tech_reveal_pending,
)
from dune_imperium.rules.shield_wall import destroy_shield_wall
from dune_imperium.rules.spy_moves import spy_placement_frame

_FRAME_LABEL = "Agent-turn effect frame"
_ACQUISITION_LABEL = "Tech acquisition frame"
# Kota Odax's Secret Project: "Whenever you could acquire a Tech tile, you
# may choose this one. It costs 1 less" [Kota Odax of Ix card].
SECRET_PROJECT_DISCOUNT = 1
ALL_POST_IDS = tuple(post.post_id for post in OBSERVATION_POSTS)


def tech_cost(
    owner: PlayerState,
    tile: TechTile,
    *,
    discount: int = 0,
    secret_project: bool = False,
) -> int:
    """Return the spice the tile costs the owner now.

    The Ixian Embassy takes one off with a High Council seat, a card's Tech
    Discount icon one more, and Kota Odax's Secret Project tile one more;
    "the cost can never be less than 0" [Bloodlines p. 7].
    """

    cost = tile.cost - discount
    if owner.high_council:
        cost -= HIGH_COUNCIL_TECH_DISCOUNT
    if secret_project:
        cost -= SECRET_PROJECT_DISCOUNT
    return max(cost, 0)


def face_up_tech_ids(state: GameState) -> tuple[str, ...]:
    """Return the face-up tile on top of each non-empty stack, in stack order."""

    return tuple(stack[0] for stack in state.tech_stacks if stack)


def tech_acquisition_frame(player: int, *, discount: int, source: str) -> DecisionFrame:
    """Return the frame of a card-granted Acquire Tech with ``discount``."""

    return DecisionFrame(
        kind=FrameKind.TECH_ACQUISITION,
        frame_id=f"{source}:tech_acquisition",
        decision=PlayerDecision(owner=player, prompt="Acquire a Tech tile or decline"),
        context=(("discount", discount), ("player", player), ("source", source)),
    )


def push_tech_acquisition(
    state: GameState,
    player: int,
    *,
    discount: int,
    source: str,
) -> RuleResult:
    """Open a card-granted Acquire Tech, or note that nothing can be acquired."""

    if not state.config.tech_module:
        raise ValueError("Acquire Tech requires the Tech Module")
    owner = state.players[player]
    if not face_up_tech_ids(state) and not owner.secret_project_tech_id:
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{source}:tech_unavailable",
                    kind="tech_acquisition_unavailable",
                    payload=(("player", player),),
                ),
            ),
        )
    return RuleResult(
        state=state.push_decision(
            tech_acquisition_frame(player, discount=discount, source=source)
        )
    )


def _pending_board_context(
    state: GameState, player: int
) -> dict[str, ActionValue] | None:
    """Return the owner's effect-frame context while its Tech offer is pending."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if not board_icon_is_pending(context, BOARD_ICON_TECH):
        return None
    return context


def _offer(state: GameState, player: int) -> tuple[int, str] | None:
    """Return (discount, source) of the open Acquire Tech offer, if any."""

    context = _pending_board_context(state, player)
    if context is not None:
        space_id = context_str(context, "space_id", owner=_FRAME_LABEL)
        return 0, f"round:{state.round_number}:player:{player}:board:{space_id}:tech"
    frame = owned_top_frame(state, FrameKind.TECH_ACQUISITION, player)
    if frame is None:
        return None
    frame_context = dict(frame.context)
    return (
        context_int(frame_context, "discount", owner=_ACQUISITION_LABEL),
        context_str(frame_context, "source", owner=_ACQUISITION_LABEL),
    )


def _candidate_tiles(
    state: GameState, owner: PlayerState
) -> tuple[tuple[TechTile, bool], ...]:
    """Return the tiles the owner may choose from: stack tops, then the secret one."""

    candidates = [
        (TECH_TILES_BY_ID[tech_id], False) for tech_id in face_up_tech_ids(state)
    ]
    if owner.secret_project_tech_id:
        candidates.append((TECH_TILES_BY_ID[owner.secret_project_tech_id], True))
    return tuple(candidates)


def _acquisition_variants(
    state: GameState,
    owner: PlayerState,
    tile: TechTile,
) -> tuple[tuple[tuple[str, ActionValue], ...], ...]:
    """Return the argument tuples of the tile's acquire choices (beyond ``tech_id``)."""

    if tile.acquire_requires_spy_trash:
        # "You must trash one of your Spies from the board".
        return tuple((("post_id", post_id),) for post_id in owner.spy_post_ids)
    if tile.acquire_influence_choice:
        return tuple((("faction", faction.value),) for faction in Faction)
    if tile.acquire_intrigue_or_card:
        return ((("choice", "intrigue"),), (("choice", "card"),))
    if tile.acquire_may_destroy_shield_wall and state.shield_wall_present:
        return ((), (("destroy_shield_wall", True),))
    return ((),)


def legal_tech_acquisition_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every affordable face-up tile (and the Secret Project), or a refusal."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not state.config.tech_module:
        return ()
    offer = _offer(state, player)
    if offer is None:
        return ()
    discount, _ = offer
    owner = state.players[player]
    actions = [DomainAction(action_id="decline_tech", actor=player)]
    for tile, secret in _candidate_tiles(state, owner):
        cost = tech_cost(owner, tile, discount=discount, secret_project=secret)
        if owner.resources.spice < cost:
            continue
        actions.extend(
            DomainAction(
                action_id="acquire_tech",
                actor=player,
                arguments=tuple(sorted((("tech_id", tile.tech_id), *variant))),
            )
            for variant in _acquisition_variants(state, owner, tile)
        )
    if len(actions) > 1 and _pending_board_context(state, player) is None:
        # A card's Tech Discount icon (Battlefield Research, Rapid
        # Engineering) must be used once the card is played and a tile is
        # affordable (designer ruling, OQ-057); only the Landsraad visit's
        # "may acquire" keeps its refusal [Bloodlines p. 7].
        actions = actions[1:]
    return tuple(actions)


def _take_tile(
    state: GameState,
    owner: PlayerState,
    tech_id: str,
    *,
    source: str,
) -> tuple[GameState, PlayerState, tuple[GameEvent, ...], bool]:
    """Move the tile from its stack (revealing the next) or the Secret Project."""

    if owner.secret_project_tech_id == tech_id:
        return (
            state,
            replace(
                owner, secret_project_tech_id="", tech_ids=(*owner.tech_ids, tech_id)
            ),
            (),
            True,
        )
    stacks = list(state.tech_stacks)
    events: list[GameEvent] = []
    for index, stack in enumerate(stacks):
        if stack and stack[0] == tech_id:
            stacks[index] = stack[1:]
            if stacks[index]:
                events.append(
                    GameEvent(
                        event_id=f"{source}:{tech_id}:revealed:{stacks[index][0]}",
                        kind="tech_revealed",
                        payload=(("stack", index), ("tech_id", stacks[index][0])),
                    )
                )
            break
    else:
        raise RuntimeError("Tech tile is not on top of a stack")
    return (
        replace(state, tech_stacks=tuple(stacks)),
        replace(owner, tech_ids=(*owner.tech_ids, tech_id)),
        tuple(events),
        False,
    )


def apply_tech_acquisition(state: GameState, action: DomainAction) -> RuleResult:
    """Buy the chosen tile with its acquire effect, or decline the offer."""

    if action not in legal_tech_acquisition_actions(state, action.actor):
        raise ValueError("action is not a legal Tech acquisition choice")
    player = action.actor
    context = _pending_board_context(state, player)
    offer = _offer(state, player)
    if offer is None:
        raise RuntimeError("Tech acquisition lost its offer")
    discount, source = offer

    if action.action_id == "decline_tech":
        event = GameEvent(
            event_id=f"{source}:declined",
            kind="tech_declined",
            payload=(("player", player),),
        )
        if context is not None:
            finish_board_icon(context, BOARD_ICON_TECH)
            return RuleResult(
                state=advance_after_effect(state, context), events=(event,)
            )
        return RuleResult(state=state.pop_decision(), events=(event,))

    arguments = dict(action.arguments)
    tech_id = str(arguments["tech_id"])
    tile = TECH_TILES_BY_ID[tech_id]
    owner = state.players[player]
    secret = owner.secret_project_tech_id == tech_id
    cost = tech_cost(owner, tile, discount=discount, secret_project=secret)
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:{tech_id}",
            kind="tech_acquired",
            payload=(
                ("player", player),
                ("secret_project", secret),
                ("spice", cost),
                ("tech_id", tech_id),
            ),
        )
    ]
    working, next_owner, reveal_events, _ = _take_tile(
        state, owner, tech_id, source=source
    )
    events.extend(reveal_events)
    next_owner = replace(
        next_owner,
        resources=replace(
            next_owner.resources, spice=next_owner.resources.spice - cost
        ),
    )

    # --- immediate acquire effects on the owner ---------------------------
    if tile.acquire_requires_spy_trash:
        post_id = str(arguments["post_id"])
        next_owner = replace(
            next_owner,
            spy_post_ids=tuple(
                candidate
                for candidate in next_owner.spy_post_ids
                if candidate != post_id
            ),
            spies_boxed=next_owner.spies_boxed + 1,
        )
        events.append(
            GameEvent(
                event_id=f"{source}:{tech_id}:spy_trashed:{post_id}",
                kind="spy_trashed",
                payload=(("player", player), ("post_id", post_id)),
            )
        )
    if tile.acquire_solari or tile.acquire_victory_points:
        next_owner = replace(
            next_owner,
            resources=replace(
                next_owner.resources,
                solari=next_owner.resources.solari + tile.acquire_solari,
            ),
            victory_points=next_owner.victory_points + tile.acquire_victory_points,
        )
        if tile.acquire_victory_points:
            events.append(
                GameEvent(
                    event_id=f"{source}:{tech_id}:victory_points",
                    kind="victory_points_gained",
                    payload=(
                        ("amount", tile.acquire_victory_points),
                        ("player", player),
                    ),
                )
            )
    troops_recruited = 0
    if tile.acquire_troops:
        next_owner, troops_recruited = recruit_troops(next_owner, tile.acquire_troops)
        events.extend(
            recruit_shortfall_events(
                f"{source}:{tech_id}", player, tile.acquire_troops, troops_recruited
            )
        )
    if has_ornithopter_fleet(next_owner):
        # Acquiring the Fleet (or any tile while holding it) matches at once
        # [Bloodlines p. 12].
        next_owner, match_events = match_all_battle_icons(
            next_owner, source=f"{source}:{tech_id}"
        )
        events.extend(match_events)
    players = replace_player(working.players, next_owner)
    working = replace(working, players=players)

    # --- frame bookkeeping ------------------------------------------------
    if context is not None:
        finish_board_icon(context, BOARD_ICON_TECH)
        context["troops_recruited"] = (
            context_int(context, "troops_recruited", owner=_FRAME_LABEL)
            + troops_recruited
        )
        working = advance_after_effect(working, context, players)
    else:
        working = working.pop_decision()
        working = replace(
            working,
            decision_stack=with_recruited_units(
                working.decision_stack, player, troops_recruited
            ),
        )

    # --- effects that touch shared state or open follow-up frames ---------
    if arguments.get("destroy_shield_wall") is True:
        destroyed = destroy_shield_wall(
            working, event_id=f"{source}:{tech_id}:shield_wall", source=tech_id
        )
        working = destroyed.state
        events.extend(destroyed.events)
    faction_value = arguments.get("faction")
    if tile.acquire_influence_choice and isinstance(faction_value, str):
        gained = gain_faction_influence(
            working,
            player,
            Faction(faction_value),
            1,
            event_prefix=f"{source}:{tech_id}:influence:{faction_value}",
        )
        working = gained.state
        events.extend(gained.events)
    intrigue = tile.acquire_intrigue
    cards = tile.acquire_cards
    if tile.acquire_intrigue_or_card:
        if arguments.get("choice") == "intrigue":
            intrigue += 1
        else:
            cards += 1
    if tile.acquire_contracts:
        contracts = begin_contract_gain(
            working, player, tile.acquire_contracts, source=f"{source}:{tech_id}"
        )
        working = contracts.state
        events.extend(contracts.events)
    if tile.acquire_may_trash_card:
        working = working.push_decision(
            optional_trash_frame(player, f"{source}:{tech_id}")
        )
    for index in range(tile.acquire_deep_cover_spies):
        working = spy_placement_frame(
            working,
            player,
            ALL_POST_IDS,
            source=f"{source}:{tech_id}:{index}",
            deep_cover=True,
        )
    if intrigue:
        drawn = draw_or_queue_intrigue_cards(
            working, player, intrigue, source=f"{source}:{tech_id}:intrigue"
        )
        working = drawn.state
        events.extend(drawn.events)
    if cards:
        drawn = draw_or_request_personal_cards(
            working, player, cards, source=f"{source}:{tech_id}:draw"
        )
        working = drawn.state
        events.extend(drawn.events)
    return RuleResult(state=working, events=tuple(events))


# --- abilities ----------------------------------------------------------------

PLASTEEL_BLADES_CARD_ID = "tech:plasteel_blades"
_TURN_FRAME_KINDS = (FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL)


def _owned_turn_frame(state: GameState, player: int) -> DecisionFrame | None:
    """Return the top frame if it is one of the owner's turn frames."""

    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if (
        frame.kind not in _TURN_FRAME_KINDS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    return frame


def legal_tech_flip_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Offer the owner's unflipped Flip tiles during one of their turns.

    "An ability with this icon is used during one of your turns, and can be
    used only once per round" [Bloodlines p. 7]. Rapid Dropships prints
    "Agent Turn", so its Combat icon is offered after the Agent placement
    only; the other two flip from the turn, Agent-effect or Reveal frame.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if not state.config.tech_module:
        return ()
    frame = _owned_turn_frame(state, player)
    if frame is None:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    for tech_id in owner.tech_ids:
        tile = TECH_TILES_BY_ID[tech_id]
        if not tile.flips or tech_id in owner.tech_flipped:
            continue
        if tile.ability is TechAbility.FLIP_COMBAT_ICON and (
            frame.kind != FrameKind.AGENT_EFFECTS
            or not state.current_conflict_ids
            or units_deployment_blocked(state, player)
        ):
            continue
        actions.append(
            DomainAction(
                action_id="flip_tech", actor=player, arguments=(("tech_id", tech_id),)
            )
        )
    return tuple(actions)


def apply_tech_flip(state: GameState, action: DomainAction) -> RuleResult:
    """Flip the tile face down and resolve its printed ability."""

    if action not in legal_tech_flip_actions(state, action.actor):
        raise ValueError("action is not a legal Tech flip")
    player = action.actor
    tech_id = str(dict(action.arguments)["tech_id"])
    tile = TECH_TILES_BY_ID[tech_id]
    owner = state.players[player]
    source = f"round:{state.round_number}:player:{player}:tech:{tech_id}:flip"
    flipped = replace(owner, tech_flipped=(*owner.tech_flipped, tech_id))
    events: list[GameEvent] = [
        GameEvent(
            event_id=source,
            kind="tech_flipped",
            payload=(("player", player), ("tech_id", tech_id)),
        )
    ]
    working = replace(state, players=replace_player(state.players, flipped))
    if tile.ability is TechAbility.FLIP_DRAW_INTRIGUE:
        drawn = draw_or_queue_intrigue_cards(working, player, 1, source=source)
        working = drawn.state
        events.extend(drawn.events)
    elif tile.ability is TechAbility.FLIP_COMBAT_ICON:
        working = grant_combat_icon(working, player)
    elif tile.ability is TechAbility.FLIP_SOLARI_AND_TRASH:
        seat = working.players[player]
        seat = replace(
            seat, resources=replace(seat.resources, solari=seat.resources.solari + 1)
        )
        working = replace(working, players=replace_player(working.players, seat))
        if seat.spies_recalled_turn > 0:
            # "If you recalled a Spy this turn: trash a card" (the trash icon
            # is optional, like every printed trash).
            working = working.push_decision(optional_trash_frame(player, source))
    return RuleResult(state=working, events=tuple(events))


def _reveal_top(state: GameState, player: int) -> DecisionFrame | None:
    """Return the owner's Reveal frame while it is the top decision."""

    return owned_top_frame(state, FrameKind.REVEAL, player)


def panopticon_spy_possible(owner: PlayerState) -> bool:
    """Return whether Panopticon's Spy can still be placed this Reveal.

    Thirteen posts outnumber the twelve Spies, so a Spy in supply or one
    to recall first [Main pp. 11, 20] always finds a post; only a seat
    whose Spies all left for the box (Advanced Data Analysis) has none.
    """

    return owner.spies_supply > 0 or bool(owner.spy_post_ids)


def legal_tech_reveal_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the Reveal-turn tile effects still pending, in the owner's order.

    Reveal effects resolve in any order the owner likes [Main p. 12], so
    Forbidden Weapons' mandatory choice and Panopticon's Spy wait on the
    Reveal frame until the owner takes them (OQ-044). The strength option
    "must lose one Influence with a Faction where you have at least one
    Influence (if possible)" [Bloodlines p. 12]: one action per such
    Faction (with the Alliance recipient when the loss hands a token to
    one of several opponents), or a bare action when the owner has no
    Influence at all.
    """

    if not state.config.tech_module:
        return ()
    frame = _reveal_top(state, player)
    if frame is None:
        return ()
    pending = tech_reveal_pending(dict(frame.context))
    owner = state.players[player]
    actions: list[DomainAction] = []
    if "forbidden_weapons" in pending:
        strength: list[DomainAction] = []
        for faction in Faction:
            if influence_amount(owner.influence, faction) == 0:
                continue
            recipients = alliance_recipients_after_influence_loss(
                state, player, faction
            )
            recipient_options: tuple[int | None, ...] = (
                tuple(recipients) if len(recipients) > 1 else (None,)
            )
            for recipient in recipient_options:
                arguments: tuple[tuple[str, ActionValue], ...] = (
                    ("faction", faction.value),
                )
                if recipient is not None:
                    arguments = (("alliance_recipient", recipient), *arguments)
                strength.append(
                    DomainAction(
                        action_id="choose_tech_strength",
                        actor=player,
                        arguments=arguments,
                    )
                )
        if not strength:
            strength.append(
                DomainAction(action_id="choose_tech_strength", actor=player)
            )
        actions.extend(strength)
        actions.append(DomainAction(action_id="choose_tech_trash", actor=player))
    if "panopticon" in pending and panopticon_spy_possible(owner):
        actions.append(DomainAction(action_id="place_tech_spy", actor=player))
    return tuple(actions)


def _settle_tech_reveal(state: GameState, player: int, tech_id: str) -> GameState:
    """Drop ``tech_id`` from the Reveal frame's pending tile effects."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining = tuple(key for key in tech_reveal_pending(context) if key != tech_id)
    context[TECH_PENDING_KEY] = ",".join(remaining)
    return replace(
        state,
        decision_stack=(
            *state.decision_stack[:-1],
            replace(frame, context=tuple(sorted(context.items()))),
        ),
    )


def apply_place_tech_spy(state: GameState, action: DomainAction) -> RuleResult:
    """Panopticon: open the Spy placement on any Observation Post."""

    if action not in legal_tech_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Panopticon Spy placement")
    player = action.actor
    source = f"round:{state.round_number}:player:{player}:reveal:panopticon"
    settled = _settle_tech_reveal(state, player, "panopticon")
    return RuleResult(
        state=spy_placement_frame(settled, player, ALL_POST_IDS, source=source)
    )


def apply_tech_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve Forbidden Weapons: swords and an Influence loss, or spice and trash."""

    if action not in legal_tech_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Forbidden Weapons choice")
    player = action.actor
    tech_id = "forbidden_weapons"
    source = f"round:{state.round_number}:player:{player}:reveal:{tech_id}"
    owner = state.players[player]
    settled = _settle_tech_reveal(state, player, tech_id)
    if action.action_id == "choose_tech_trash":
        trashed = replace(
            owner,
            resources=replace(owner.resources, spice=0),
            tech_ids=tuple(held for held in owner.tech_ids if held != tech_id),
            tech_flipped=tuple(held for held in owner.tech_flipped if held != tech_id),
        )
        return RuleResult(
            state=replace(
                settled,
                players=replace_player(settled.players, trashed),
                tech_trash=(*settled.tech_trash, tech_id),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:trashed",
                    kind="tech_trashed",
                    payload=(
                        ("player", player),
                        ("spice", owner.resources.spice),
                        ("tech_id", tech_id),
                    ),
                ),
            ),
        )
    swords = 3
    units = owner.units_in_conflict
    frames = add_reveal_optional_sword_strength(settled.decision_stack, swords)
    next_owner = owner
    if units > 0:
        # The swords count at once with a unit in the Conflict [Main p. 12].
        frames = add_reveal_strength(frames, swords)
        next_owner = replace(owner, combat_strength=owner.combat_strength + swords)
    working = replace(
        settled,
        players=replace_player(settled.players, next_owner),
        decision_stack=frames,
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:strength",
            kind="reveal_strength_gained",
            payload=(("amount", swords), ("player", player)),
        )
    ]
    arguments = dict(action.arguments)
    faction_value = arguments.get("faction")
    if isinstance(faction_value, str):
        recipient = arguments.get("alliance_recipient")
        assert recipient is None or isinstance(recipient, int)
        lost = lose_faction_influence(
            working,
            player,
            Faction(faction_value),
            1,
            event_prefix=f"{source}:lost:{faction_value}",
            alliance_recipient=recipient,
        )
        working = lost.state
        events.extend(lost.events)
    return RuleResult(state=working, events=tuple(events))


def deploy_suspensor_troops(result: RuleResult) -> RuleResult:
    """Suspensor Suits: a troop into the Conflict per Intrigue card gained.

    "For each Intrigue card you draw or steal during your turn: troop,
    deploy it to the Conflict" [Suspensor Suits Tech tile]. The draw paths
    record the cards gained by the turn owner in ``suspensor_owed``; this
    hook pays them out after the transition, from the supply, into the
    Conflict (through the Reveal bookkeeping when the Reveal is open), and
    drops what the supply or a blocked deployment cannot honour (OQ-030).
    """

    state = result.state
    if not any(seat.suspensor_owed for seat in state.players):
        return result
    events = list(result.events)
    for seat in state.players:
        if seat.suspensor_owed <= 0:
            continue
        owed = seat.suspensor_owed
        player = seat.player_id
        cleared = replace(seat, suspensor_owed=0)
        state = replace(state, players=replace_player(state.players, cleared))
        source = f"round:{state.round_number}:player:{player}:suspensor_suits"
        count = min(owed, cleared.troops_supply)
        if (
            count == 0
            or not state.current_conflict_ids
            or units_deployment_blocked(state, player)
        ):
            events.append(
                GameEvent(
                    event_id=f"{source}:unavailable",
                    kind="suspensor_deployment_unavailable",
                    payload=(("player", player), ("troops", owed)),
                )
            )
            continue
        if reveal_is_open_for(state, player):
            staged = replace(
                cleared,
                troops_supply=cleared.troops_supply - count,
                troops_garrison=cleared.troops_garrison + count,
            )
            state = replace(state, players=replace_player(state.players, staged))
            deployed = add_units_to_reveal(state, player, troops=count)
            state = deployed.state
            events.extend(deployed.events)
        else:
            deployed_seat = replace(
                cleared,
                troops_supply=cleared.troops_supply - count,
                troops_conflict=cleared.troops_conflict + count,
                units_deployed_turn=cleared.units_deployed_turn + count,
            )
            state = replace(state, players=replace_player(state.players, deployed_seat))
        events.append(
            GameEvent(
                event_id=f"{source}:deployed",
                kind="troops_deployed",
                payload=(("count", count), ("player", player), ("source", "tech")),
            )
        )
    return RuleResult(state=state, events=tuple(events))


def apply_endgame_tech_effects(state: GameState) -> RuleResult:
    """Pay the Endgame lines of CHOAM Transports and Panopticon.

    "Endgame: worth 1 VP if you have completed four or more contracts"
    [CHOAM Transports Tech tile]; "Endgame: gain 1 Influence with each
    Faction where you have 1 or less Influence" [Panopticon Tech tile].
    Resolved as the Endgame opens, before the Endgame Intrigue window
    (project convention, OQ-040).
    """

    events: list[GameEvent] = []
    for seat in state.players:
        player = seat.player_id
        source = f"round:{state.round_number}:player:{player}:endgame_tech"
        if (
            has_tech(seat.tech_ids, TechAbility.CONTRACT_COMPLETION_DRAW)
            and len(seat.completed_contract_ids) >= 4
        ):
            scored = replace(seat, victory_points=seat.victory_points + 1)
            state = replace(state, players=replace_player(state.players, scored))
            events.append(
                GameEvent(
                    event_id=f"{source}:choam_transports",
                    kind="victory_points_gained",
                    payload=(("amount", 1), ("player", player), ("source", "tech")),
                )
            )
        if has_tech(seat.tech_ids, TechAbility.PANOPTICON):
            for faction in Faction:
                if influence_amount(state.players[player].influence, faction) > 1:
                    continue
                gained = gain_faction_influence(
                    state,
                    player,
                    faction,
                    1,
                    event_prefix=f"{source}:panopticon:{faction.value}",
                )
                state = gained.state
                events.extend(gained.events)
    return RuleResult(state=state, events=tuple(events))


def draw_owed_tech_cards(result: RuleResult) -> RuleResult:
    """Draw the cards CHOAM Transports and Planetary Array owe after a step.

    Both tiles pay inside another effect's resolution (a contract
    completion, the Combat cleanup), where a discard reshuffle could not be
    pushed safely; the owing seat records the count and this hook draws
    once the transition has settled. A pending chance frame defers it to
    the next transition, like Hungry for Spice.
    """

    state = result.state
    if not any(seat.tech_cards_owed for seat in state.players):
        return result
    if state.decision_stack and isinstance(
        state.decision_stack[-1].decision, ChanceDecision
    ):
        return result
    events = list(result.events)
    for seat in state.players:
        if seat.tech_cards_owed <= 0:
            continue
        owed = seat.tech_cards_owed
        cleared = replace(seat, tech_cards_owed=0)
        state = replace(state, players=replace_player(state.players, cleared))
        drawn = draw_or_request_personal_cards(
            state,
            seat.player_id,
            owed,
            source=f"round:{state.round_number}:player:{seat.player_id}:tech_draw",
        )
        state = drawn.state
        events.extend(drawn.events)
        if state.decision_stack and isinstance(
            state.decision_stack[-1].decision, ChanceDecision
        ):
            # One reshuffle at a time; the next seat waits for the next step.
            break
    return RuleResult(state=state, events=tuple(events))


# --- Kota Odax of Ix: Secret Project ----------------------------------------------


def assign_secret_project(state: GameState) -> GameState:
    """Open Kota Odax's game-start pick of a bottom Tech tile.

    "Game Start: Peek at the bottom Tech tile of each stack. Place one face
    down here" [Kota Odax of Ix card]. The frame pauses the game in SETUP
    (like the Navigation setup) until the owner has chosen.
    """

    if not state.config.tech_module or not any(state.tech_stacks):
        return state
    seat = next(
        (
            candidate
            for candidate in state.players
            if candidate.leader_id == "kota_odax_of_ix"
        ),
        None,
    )
    if seat is None or seat.secret_project_tech_id:
        return state
    candidates = tuple(stack[-1] for stack in state.tech_stacks if stack)
    frame = DecisionFrame(
        kind=FrameKind.TECH_SECRET_PROJECT,
        frame_id=f"setup:secret_project:{seat.player_id}",
        decision=PlayerDecision(
            owner=seat.player_id,
            prompt="Secret Project: place one bottom Tech tile on your Leader",
        ),
        context=(
            ("candidates", ",".join(candidates)),
            ("player", seat.player_id),
            ("resume_phase", state.phase.value),
        ),
    )
    return replace(
        state, phase=GamePhase.SETUP, decision_stack=(*state.decision_stack, frame)
    )


def legal_secret_project_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the bottom tile of each stack (the owner alone sees them)."""

    frame = owned_top_frame(state, FrameKind.TECH_SECRET_PROJECT, player)
    if frame is None:
        return ()
    candidates = context_str(
        dict(frame.context), "candidates", owner="Secret Project frame"
    )
    return tuple(
        DomainAction(
            action_id="choose_secret_project",
            actor=player,
            arguments=(("tech_id", tech_id),),
        )
        for tech_id in candidates.split(",")
        if tech_id
    )


def apply_secret_project(state: GameState, action: DomainAction) -> RuleResult:
    """Move the chosen bottom tile face down onto Kota Odax's Leader card."""

    if action not in legal_secret_project_actions(state, action.actor):
        raise ValueError("action is not a legal Secret Project choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    tech_id = str(dict(action.arguments)["tech_id"])
    stacks = tuple(
        stack[:-1] if stack and stack[-1] == tech_id else stack
        for stack in state.tech_stacks
    )
    owner = state.players[action.actor]
    chosen = replace(owner, secret_project_tech_id=tech_id)
    resume = GamePhase(
        context_str(context, "resume_phase", owner="Secret Project frame")
    )
    return RuleResult(
        state=replace(
            state,
            phase=resume,
            tech_stacks=stacks,
            players=replace_player(state.players, chosen),
            decision_stack=state.decision_stack[:-1],
        ),
        events=(
            # The identity is the owner's; everyone sees that a tile left.
            GameEvent(
                event_id=f"{frame.frame_id}:chosen",
                kind="secret_project_chosen",
                payload=(("player", action.actor),),
            ),
            GameEvent(
                event_id=f"{frame.frame_id}:identity",
                kind="secret_project_identity",
                payload=(("player", action.actor), ("tech_id", tech_id)),
                visible_to=(action.actor,),
            ),
        ),
    )
