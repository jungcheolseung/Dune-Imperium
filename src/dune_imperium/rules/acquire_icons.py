"""An Imperium card's acquire box taken icon by icon (OQ-141).

"When you acquire a card, you immediately resolve its acquire box, once"
[DI p. 16]; the box's printed icons are independent effects whose order the
documents leave to their owner, as an Agent box's icons (OQ-027) and a
Conflict or Contract reward line's (OQ-112) are. So a box of more than one
icon -- the original game's CHOAM Directorship prints an Influence icon for
each of the four Factions -- or an icon that needs a choice -- Lady Jessica's
Influence with a Faction of the owner's choice -- is paid one row per icon,
in the order its owner picks. A box of a single icon with nothing to choose
(Steersman, Imperial Throneship, every other Uprising card) is paid at once,
as it always was (``rules.acquisition``).

The rows are the Contract reward's pattern in the owner's own turn (OQ-112
(4), user decision 2026-10-19 B3-4: "차례 안에서 완수한 계약의 보상은 차례의
줄이다"): each icon waits on the turn's frame (``turn_rows.ACQUIRE_ICON``),
whichever Agent turn or Reveal turn took the card, beside the turn's other
effects, and holds the turn's end until it is taken. A fixed Faction's icon
is always a row; a Faction already at 6 gains nothing (OQ-060). The chosen
Faction's icon offers a row per Faction that can still rise, and with every
cube at the top it waits and the turn-end press lapses it, as every in-turn
"Influence with any Faction" does (``turn_rows``, OQ-057 (1)).

Nothing in the original game acquires a card with such a box outside its
owner's turn, but Arrakeen Scouts' Critical Moment market can, in a
combination (``rules.scouts_auctions``): there the box would need a window of
its own, which this module does not open (``queue_acquire_icons`` refuses).
"""

from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import GainInfluence, Reward
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.trigger_abilities import acquisition_ability
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.influence import gain_faction_influence, influence_can_rise

ACQUIRE_ICON_ACTION: Final = "resolve_acquire_icon"
ACQUIRED_CARD_ARGUMENT: Final = "acquired_card_id"
_FIXED_PREFIX: Final = "influence_"


def _box_pieces(entry: ImperiumCardEntry) -> tuple[Reward, ...]:
    ability = acquisition_ability(entry.acquisition_effect)
    return () if ability is None else ability.sections[0].rewards


def _icon_of(piece: Reward) -> str:
    """The icon label of one Influence piece of an acquire box: the
    Faction's for a fixed one, the chosen icon's for "any Faction"."""

    if (
        not isinstance(piece, GainInfluence)
        or piece.times != 1
        or piece.visited_space
        or piece.distinct
        or piece.one_faction
        or piece.where_opponent_leads
        or piece.different_from_trigger
    ):
        raise NotImplementedError(f"{piece!r} is not an acquire box's icon yet")
    if piece.factions is None:
        return turn_rows.CHOSEN_INFLUENCE_ICON
    if len(piece.factions) != 1:
        raise NotImplementedError(f"{piece!r} limits the choice to some Factions")
    return f"{_FIXED_PREFIX}{piece.factions[0].value}"


def acquire_box_icons(entry: ImperiumCardEntry) -> tuple[str, ...] | None:
    """The icons of ``entry``'s acquire box when it is paid icon by icon, in
    printed order; None when it is paid at once (a single icon with nothing
    to choose, or a box without Influence, whose other icons the acquisition
    paths pay themselves).

    A box that mixes Influence with other icons is not transcribed yet: a
    later card that prints one needs its own rows (OQ-141).
    """

    pieces = _box_pieces(entry)
    if not any(isinstance(piece, GainInfluence) for piece in pieces):
        return None
    if not all(isinstance(piece, GainInfluence) for piece in pieces):
        raise NotImplementedError(
            f"{entry.card.card_id}: an acquire box of Influence and other icons"
        )
    icons = tuple(_icon_of(piece) for piece in pieces)
    if len(icons) == 1 and icons[0] != turn_rows.CHOSEN_INFLUENCE_ICON:
        return None
    return icons


def acquire_icon_faction(icon: str) -> Faction | None:
    """The Faction a fixed icon raises, None for the chosen icon."""

    if icon == turn_rows.CHOSEN_INFLUENCE_ICON:
        return None
    return Faction(icon.removeprefix(_FIXED_PREFIX))


def acquire_icon_row(
    player: int, card_id: str, icon: str, faction: Faction | None = None
) -> DomainAction:
    """The row that takes ``icon`` of ``card_id``'s acquire box, naming the
    Faction a chosen icon raises."""

    arguments: list[tuple[str, ActionValue]] = [
        (ACQUIRED_CARD_ARGUMENT, card_id),
        ("effect", icon),
    ]
    if faction is not None:
        arguments.append(("faction", faction.value))
    return DomainAction(
        action_id=ACQUIRE_ICON_ACTION, actor=player, arguments=tuple(arguments)
    )


def _item_value(card_id: str, icon: str) -> str:
    return f"{card_id}|{icon}"


def queue_acquire_icons(
    state: GameState, player: int, entry: ImperiumCardEntry, *, source: str
) -> GameState:
    """Put each icon of ``entry``'s acquire box on ``player``'s own open
    turn, a row each (``turn_rows``), in printed order.

    ``source`` names the acquisition (the rows' events are named after it).
    """

    icons = acquire_box_icons(entry)
    if icons is None:
        raise ValueError(f"{entry.card.card_id}'s acquire box is paid at once")
    for icon in icons:
        queued = turn_rows.queue(
            state,
            player,
            (
                turn_rows.ACQUIRE_ICON,
                source,
                _item_value(entry.card.card_id, icon),
            ),
        )
        if queued is None:
            raise NotImplementedError(
                f"{entry.card.card_id} was acquired outside its owner's turn: "
                "an acquire box of several icons waits on a turn (OQ-141)"
            )
        state = queued
    return state


def legal_acquire_icon_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row per acquire icon waiting on ``player``'s own turn (OQ-141): a
    fixed Faction's icon as it is, the chosen icon once for each Faction that
    can still rise (OQ-060)."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return ()
    owner = state.players[player]
    rows: dict[DomainAction, None] = {}
    for kind, _source, value in turn_rows.pending(frame):
        if kind != turn_rows.ACQUIRE_ICON:
            continue
        card_id, icon = value.split("|")
        if icon != turn_rows.CHOSEN_INFLUENCE_ICON:
            rows.setdefault(acquire_icon_row(player, card_id, icon), None)
            continue
        for faction in Faction:
            if influence_can_rise(owner, faction):
                rows.setdefault(acquire_icon_row(player, card_id, icon, faction), None)
    return tuple(rows)


def apply_acquire_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Take one acquire icon: its Influence, the Faction fixed or chosen."""

    player = action.actor
    if action not in legal_acquire_icon_actions(state, player):
        raise ValueError("action is not a legal acquire icon row")
    arguments = dict(action.arguments)
    card_id, icon = str(arguments[ACQUIRED_CARD_ARGUMENT]), str(arguments["effect"])
    frame = turn_rows.rows_frame(state, player)
    assert frame is not None
    item = next(
        item
        for item in turn_rows.pending(frame)
        if item[0] == turn_rows.ACQUIRE_ICON and item[2] == _item_value(card_id, icon)
    )
    faction = acquire_icon_faction(icon) or Faction(str(arguments["faction"]))
    return gain_faction_influence(
        turn_rows.take(state, player, item),
        player,
        faction,
        1,
        event_prefix=f"{item[1]}:influence:{faction.value}",
    )
