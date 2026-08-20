"""Shared Faction Influence, track-bonus, and Alliance transitions."""

from dataclasses import replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence, PlayerState
from dune_imperium.core.state import GameState

MAX_INFLUENCE = 6


def gain_faction_influence(
    state: GameState,
    player: int,
    faction: Faction,
    amount: int,
    *,
    event_prefix: str,
) -> RuleResult:
    """Gain Influence one space at a time and resolve crossed boundaries."""

    if not 0 <= player < state.config.players:
        raise ValueError("Influence recipient must identify a configured player")
    if amount < 0:
        raise ValueError("Influence gain must not be negative")

    players = state.players
    intrigue_deck = state.intrigue_deck
    gained = 0
    events: list[GameEvent] = []
    for step in range(amount):
        owner = players[player]
        current = influence_amount(owner.influence, faction)
        if current >= MAX_INFLUENCE:
            break
        next_amount = current + 1
        owner = replace(
            owner,
            influence=replace_influence(owner.influence, faction, next_amount),
            victory_points=owner.victory_points + (1 if next_amount == 2 else 0),
        )
        players = replace_player(players, owner)
        gained += 1

        if next_amount == 4:
            players, intrigue_deck, bonus_payload = _apply_track_bonus(
                players,
                intrigue_deck,
                player,
                faction,
            )
            events.append(
                GameEvent(
                    event_id=f"{event_prefix}:track_bonus:{step}",
                    kind="influence_track_bonus_gained",
                    payload=tuple(
                        sorted(
                            (
                                ("faction", faction.value),
                                ("player", player),
                                *bonus_payload,
                            )
                        )
                    ),
                )
            )

        players, alliance_event = _update_alliance(
            players,
            player,
            faction,
            event_id=f"{event_prefix}:alliance:{step}",
        )
        if alliance_event is not None:
            events.append(alliance_event)

    if gained:
        events.insert(
            0,
            GameEvent(
                event_id=f"{event_prefix}:influence",
                kind="influence_gained",
                payload=(
                    ("amount", gained),
                    ("faction", faction.value),
                    ("player", player),
                ),
            ),
        )
    return RuleResult(
        state=replace(state, players=players, intrigue_deck=intrigue_deck),
        events=tuple(events),
    )


def alliance_recipients_after_influence_loss(
    state: GameState,
    player: int,
    faction: Faction,
) -> tuple[int, ...]:
    """Return players eligible to receive an Alliance after losing one step."""

    if not 0 <= player < state.config.players:
        raise ValueError("Influence owner must identify a configured player")
    owner = state.players[player]
    if faction.value not in owner.alliance_faction_ids:
        return ()
    current = influence_amount(owner.influence, faction)
    if current == 0:
        return ()
    tied = tuple(
        candidate.player_id
        for candidate in state.players
        if candidate.player_id != player
        and influence_amount(candidate.influence, faction) == current
    )
    if tied:
        return tied
    if current - 1 >= 4:
        return ()
    return tuple(
        candidate.player_id
        for candidate in state.players
        if candidate.player_id != player
        and influence_amount(candidate.influence, faction) >= 4
    )


def lose_faction_influence(
    state: GameState,
    player: int,
    faction: Faction,
    amount: int,
    *,
    event_prefix: str,
    alliance_recipient: int | None = None,
) -> RuleResult:
    """Lose Influence one space at a time and resolve held Alliance tokens."""

    if not 0 <= player < state.config.players:
        raise ValueError("Influence owner must identify a configured player")
    if amount < 0:
        raise ValueError("Influence loss must not be negative")
    if amount > 1 and alliance_recipient is not None:
        raise ValueError("an Alliance recipient can only resolve a one-step loss")

    players = state.players
    lost = 0
    events: list[GameEvent] = []
    for step in range(amount):
        step_state = replace(state, players=players)
        recipients = alliance_recipients_after_influence_loss(
            step_state,
            player,
            faction,
        )
        if len(recipients) > 1 and alliance_recipient not in recipients:
            raise ValueError("Influence loss requires an Alliance recipient choice")
        if len(recipients) <= 1 and alliance_recipient is not None:
            raise ValueError(
                "Influence loss does not allow an Alliance recipient choice"
            )

        owner = players[player]
        current = influence_amount(owner.influence, faction)
        if current == 0:
            break
        next_amount = current - 1
        owner = replace(
            owner,
            influence=replace_influence(owner.influence, faction, next_amount),
            victory_points=owner.victory_points - (1 if next_amount == 1 else 0),
        )
        players = replace_player(players, owner)
        lost += 1

        if faction.value in owner.alliance_faction_ids:
            recipient = (
                alliance_recipient
                if len(recipients) > 1
                else recipients[0]
                if recipients
                else None
            )
            if recipient is not None:
                players, event = _transfer_or_return_alliance(
                    players,
                    player,
                    faction,
                    recipient,
                    event_id=f"{event_prefix}:alliance:{step}",
                )
                events.append(event)
            elif next_amount < 4:
                players, event = _transfer_or_return_alliance(
                    players,
                    player,
                    faction,
                    None,
                    event_id=f"{event_prefix}:alliance:{step}",
                )
                events.append(event)

    if lost:
        events.insert(
            0,
            GameEvent(
                event_id=f"{event_prefix}:influence",
                kind="influence_lost",
                payload=(
                    ("amount", lost),
                    ("faction", faction.value),
                    ("player", player),
                ),
            ),
        )
    return RuleResult(state=replace(state, players=players), events=tuple(events))


def influence_amount(influence: Influence, faction: Faction) -> int:
    """Return one faction's position from the fixed Influence record."""

    match faction:
        case Faction.EMPEROR:
            return influence.emperor
        case Faction.SPACING_GUILD:
            return influence.spacing_guild
        case Faction.BENE_GESSERIT:
            return influence.bene_gesserit
        case Faction.FREMEN:
            return influence.fremen


def replace_influence(
    influence: Influence,
    faction: Faction,
    amount: int,
) -> Influence:
    """Return ``influence`` with one faction position replaced."""

    match faction:
        case Faction.EMPEROR:
            return replace(influence, emperor=amount)
        case Faction.SPACING_GUILD:
            return replace(influence, spacing_guild=amount)
        case Faction.BENE_GESSERIT:
            return replace(influence, bene_gesserit=amount)
        case Faction.FREMEN:
            return replace(influence, fremen=amount)


def _apply_track_bonus(
    players: tuple[PlayerState, ...],
    intrigue_deck: tuple[str, ...],
    player: int,
    faction: Faction,
) -> tuple[
    tuple[PlayerState, ...],
    tuple[str, ...],
    tuple[tuple[str, int | str], ...],
]:
    owner = players[player]
    match faction:
        case Faction.EMPEROR:
            recruited = min(2, owner.troops_supply)
            owner = replace(
                owner,
                troops_supply=owner.troops_supply - recruited,
                troops_garrison=owner.troops_garrison + recruited,
            )
            payload: tuple[tuple[str, int | str], ...] = (("troops", recruited),)
        case Faction.SPACING_GUILD:
            owner = replace(
                owner,
                resources=replace(owner.resources, water=owner.resources.water + 3),
            )
            payload = (("water", 3),)
        case Faction.BENE_GESSERIT:
            if not intrigue_deck:
                raise ValueError(
                    "the Bene Gesserit Influence bonus requires an Intrigue card"
                )
            card_id = intrigue_deck[0]
            intrigue_deck = intrigue_deck[1:]
            owner = replace(
                owner,
                intrigue_cards=(*owner.intrigue_cards, card_id),
            )
            payload = (("intrigue_card_id", card_id),)
        case Faction.FREMEN:
            owner = replace(
                owner,
                resources=replace(owner.resources, water=owner.resources.water + 1),
            )
            payload = (("water", 1),)
    return replace_player(players, owner), intrigue_deck, payload


def _update_alliance(
    players: tuple[PlayerState, ...],
    challenger: int,
    faction: Faction,
    *,
    event_id: str,
) -> tuple[tuple[PlayerState, ...], GameEvent | None]:
    faction_id = faction.value
    holder = next(
        (
            player.player_id
            for player in players
            if faction_id in player.alliance_faction_ids
        ),
        None,
    )
    challenger_amount = influence_amount(players[challenger].influence, faction)
    if challenger_amount < 4 or holder == challenger:
        return players, None
    if holder is not None:
        holder_amount = influence_amount(players[holder].influence, faction)
        if challenger_amount <= holder_amount:
            return players, None

    next_players: list[PlayerState] = []
    for owner in players:
        alliance_ids = owner.alliance_faction_ids
        victory_points = owner.victory_points
        if owner.player_id == holder:
            alliance_ids = tuple(
                candidate for candidate in alliance_ids if candidate != faction_id
            )
            victory_points -= 1
        if owner.player_id == challenger:
            alliance_ids = (*alliance_ids, faction_id)
            victory_points += 1
        next_players.append(
            replace(
                owner,
                alliance_faction_ids=alliance_ids,
                victory_points=victory_points,
            )
        )
    event = GameEvent(
        event_id=event_id,
        kind="alliance_gained" if holder is None else "alliance_transferred",
        payload=(
            ("faction", faction_id),
            ("from_player", -1 if holder is None else holder),
            ("to_player", challenger),
        ),
    )
    return tuple(next_players), event


def _transfer_or_return_alliance(
    players: tuple[PlayerState, ...],
    holder: int,
    faction: Faction,
    recipient: int | None,
    *,
    event_id: str,
) -> tuple[tuple[PlayerState, ...], GameEvent]:
    faction_id = faction.value
    next_players: list[PlayerState] = []
    for owner in players:
        alliance_ids = owner.alliance_faction_ids
        victory_points = owner.victory_points
        if owner.player_id == holder:
            alliance_ids = tuple(
                candidate for candidate in alliance_ids if candidate != faction_id
            )
            victory_points -= 1
        if owner.player_id == recipient:
            alliance_ids = (*alliance_ids, faction_id)
            victory_points += 1
        next_players.append(
            replace(
                owner,
                alliance_faction_ids=alliance_ids,
                victory_points=victory_points,
            )
        )
    return (
        tuple(next_players),
        GameEvent(
            event_id=event_id,
            kind="alliance_lost" if recipient is None else "alliance_transferred",
            payload=(
                ("faction", faction_id),
                ("from_player", holder),
                ("to_player", -1 if recipient is None else recipient),
            ),
        ),
    )


def replace_player(
    players: tuple[PlayerState, ...],
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    """Replace one seat in an immutable player tuple."""

    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in players
    )
