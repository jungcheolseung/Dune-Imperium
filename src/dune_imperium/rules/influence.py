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


def replace_player(
    players: tuple[PlayerState, ...],
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    """Replace one seat in an immutable player tuple."""

    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in players
    )
