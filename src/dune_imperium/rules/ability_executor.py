"""Pending-ability executor of the composed-effects engine.

docs/composed-effects-plan.md 4.2-4.3. An open turn keeps a list of pending
abilities; each entry is resolved step by step: its applicable lines were
judged when it opened, then its choices come in the interpreter's order
(every cost choice, then every reward choice in printed order,
``effect_interpreter.choice_slots``), and its automatic rewards apply at
the end or, where the turn allows, on a row of their own once the costs are
paid (OQ-015). Each choice -- a *piece* -- is offered through one decision
shape whose action id comes from the shape table
(``action_shapes.template_id``): the same piece is a trash of a personal
card whether an Intrigue, an Agent box or a revealed card asks for it, and
only the source changes the id.

Stage A0 builds the executor without wiring it into the engine: nothing
here changes what the engine offers or does. Stage A1 moves the Intrigue
choice frame onto it, later stages the Agent boxes, the Reveal choices and
the rest (plan 5). Until then the tests hold it to the engine: on the
states of seeded games the rows it builds for an open Intrigue choice equal
``intrigue.legal_intrigue_choice_actions``, and the pending-list policy
reproduces the Reveal frame's rows, its hold of the turn end and the entry
an action takes.

What a stage still keeps outside: tags (a grafted turn's ``box=1``, a
revealed card's ``source``) are given by the caller, which knows the box or
card; the events and frame context keys a page or the observation reads
stay the adopting module's.
"""

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import Final

from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.uprising.abilities import Ability, intrigue_ability
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireTleilaxuCard,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GiveIntrigueToOpponent,
    LoseInfluence,
    LoseTroops,
    PeekTopCard,
    PlaceSpy,
    RecallSpy,
    RetreatTroops,
    SetAsideImperiumRowCard,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import (
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
)
from dune_imperium.rules.action_shapes import (
    Source,
    Target,
    Verb,
    action_shape,
    template_id,
)
from dune_imperium.rules.card_bonds import counted_in_play
from dune_imperium.rules.effect_interpreter import (
    ChoiceSlot,
    automatic_rewards,
    choice_slots,
    cost_slots,
    deployable_garrison_units,
    face_up_conflict_card_ids,
    flippable_battle_card_ids,
    influence_gain_candidates,
    spy_placement_allowed_post_ids,
    spy_placement_targets,
    trashable_discard_pile_ids,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    influence_amount,
)
from dune_imperium.rules.spy_placement import solo_occupied_post_ids
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    reclaimed_forces_block,
)
from dune_imperium.rules.units import unit_count_arguments

# --- Pending entries ---------------------------------------------------------

# Separators of the stored form: fields, list items, entries. An entry whose
# reference or chosen value holds one of them is refused when it is made.
_FIELD: Final = "|"
_ITEM: Final = ","
_ENTRY: Final = ";"


@dataclass(frozen=True, slots=True)
class PendingAbility:
    """One ability waiting in an open turn, in the form its frame stores.

    ``ref`` addresses the ability within its source (``intrigue_ref`` for an
    Intrigue option). ``sections`` are the indexes of its applicable lines,
    judged when it opened (an Intrigue's conditions are judged when it is
    played); ``shield_wall`` is whether the Shield Wall stood then, which
    decides whether a detonation icon is a choice. ``step`` counts the
    choices taken, ``chosen`` the values earlier steps picked (the Factions
    of a "distinct" gain), and ``rewards_applied`` whether the automatic
    rewards already resolved on their own row.
    """

    source: Source
    ref: str
    sections: tuple[int, ...]
    step: int = 0
    chosen: tuple[str, ...] = ()
    rewards_applied: bool = False
    shield_wall: bool = True

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("a pending ability cannot take a negative step")
        if any(index < 0 for index in self.sections):
            raise ValueError("section indexes must not be negative")
        for text in (self.ref, *self.chosen):
            if not text or any(mark in text for mark in (_FIELD, _ITEM, _ENTRY)):
                raise ValueError(f"cannot store {text!r} in a pending ability")

    def encode(self) -> str:
        """The entry as one frame-context string (``decode`` reads it back)."""

        return _FIELD.join(
            (
                self.source.value,
                self.ref,
                _ITEM.join(str(index) for index in self.sections),
                str(self.step),
                _ITEM.join(self.chosen),
                "1" if self.rewards_applied else "0",
                "1" if self.shield_wall else "0",
            )
        )

    @staticmethod
    def decode(text: str) -> PendingAbility:
        """Read an entry ``encode`` wrote; raises ``ValueError`` otherwise."""

        fields = text.split(_FIELD)
        if len(fields) != 7 or fields[5] not in ("0", "1") or fields[6] not in (
            "0",
            "1",
        ):
            raise ValueError(f"not a stored pending ability: {text!r}")
        source, ref, sections, step, chosen, applied, wall = fields
        return PendingAbility(
            source=Source(source),
            ref=ref,
            sections=tuple(int(index) for index in sections.split(_ITEM) if index),
            step=int(step),
            chosen=tuple(value for value in chosen.split(_ITEM) if value),
            rewards_applied=applied == "1",
            shield_wall=wall == "1",
        )


def encode_pending(entries: tuple[PendingAbility, ...]) -> str:
    """A pending list as one frame-context string, oldest entry first."""

    return _ENTRY.join(entry.encode() for entry in entries)


def decode_pending(text: str) -> tuple[PendingAbility, ...]:
    """The pending list ``encode_pending`` wrote."""

    return tuple(PendingAbility.decode(item) for item in text.split(_ENTRY) if item)


# --- Abilities by reference --------------------------------------------------


def intrigue_ref(card_id: str, option: int) -> str:
    """The reference of an Intrigue (or Navigation) card instance's option."""

    if option < 0:
        raise ValueError("an Intrigue option index cannot be negative")
    return f"{card_id}#{option}"


def _intrigue_ref_ability(ref: str) -> Ability:
    card_id, _, option = ref.rpartition("#")
    return intrigue_ability(intrigue_card_for_instance(card_id).options[int(option)])


# Each source's ability lookup; later stages add theirs.
_ABILITIES: Final[Mapping[Source, Callable[[str], Ability]]] = {
    Source.INTRIGUE: _intrigue_ref_ability,
}


def ability_of(entry: PendingAbility) -> Ability:
    """The ability ``entry`` resolves."""

    try:
        lookup = _ABILITIES[entry.source]
    except KeyError as error:
        raise LookupError(f"no ability lookup for {entry.source}") from error
    return lookup(entry.ref)


def entry_sections(entry: PendingAbility) -> tuple[EffectSection, ...]:
    """The applicable lines of ``entry``'s ability, in printed order."""

    sections = ability_of(entry).sections
    return tuple(sections[index] for index in entry.sections)


def entry_pieces(entry: PendingAbility) -> tuple[ChoiceSlot, ...]:
    """Every choice ``entry`` asks for, in order (``choice_slots``)."""

    return choice_slots(entry_sections(entry), shield_wall_present=entry.shield_wall)


def current_piece(entry: PendingAbility) -> ChoiceSlot | None:
    """The choice ``entry`` asks for now; None once every choice is taken."""

    pieces = entry_pieces(entry)
    return pieces[entry.step] if entry.step < len(pieces) else None


# --- Presentation ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Presentation:
    """How a turn offers its pending abilities' choices.

    ``refusals``: an optional piece offers a refusal row. Inside the owner's
    own turn it does not -- leaving it unused lapses it at the turn's end
    (OQ-095 (2), (7)) -- but a frame stacked on the turn (an Intrigue's
    choices) still does. ``rewards_row``: once the costs are paid, the
    automatic rewards resolve on a row of their own, before, between or
    after the remaining reward choices (OQ-015).
    """

    refusals: bool = False
    rewards_row: bool = False


# A frame stacked on the turn: an Intrigue card's choices.
STACKED: Final = Presentation(refusals=True, rewards_row=True)
# Rows of the owner's own Agent or Reveal turn.
IN_TURN: Final = Presentation()


# --- Rows of one piece -------------------------------------------------------


def _row(
    template: str,
    player: int,
    arguments: tuple[tuple[str, ActionValue], ...] = (),
    tag_value: ActionValue | None = None,
) -> DomainAction:
    """``template``'s action for ``player``, tagged when its shape is tagged."""

    tag = action_shape(template).tag
    if tag is not None and tag_value is not None:
        arguments = tuple(sorted((*arguments, (tag.value, tag_value))))
    return DomainAction(action_id=template, actor=player, arguments=arguments)


def piece_rows(
    state: GameState,
    player: int,
    piece: ChoiceSlot,
    source: Source,
    *,
    refusals: bool,
    chosen: tuple[str, ...] = (),
    played_card_id: str | None = None,
    tag_value: ActionValue | None = None,
) -> tuple[DomainAction, ...]:
    """The rows that answer ``piece`` for ``player``, named for ``source``.

    ``refusals`` adds an optional piece's refusal (``Presentation``);
    ``chosen`` holds the Factions an earlier step of a "distinct" gain took;
    ``played_card_id`` is the Intrigue card being played, still held while it
    resolves and never its own cost; ``tag_value`` tags a tagged template
    (``action_shapes.Tag``). The targets and their order are the engine's
    own (``intrigue.legal_intrigue_choice_actions``, which stage A1
    replaces with this).
    """

    owner = state.players[player]

    def row(
        verb: Verb,
        target: Target | None = None,
        arguments: tuple[tuple[str, ActionValue], ...] = (),
        *,
        of: Verb | None = None,
        variant: str = "",
    ) -> DomainAction:
        template = template_id(verb, source, target, of=of, variant=variant)
        return _row(template, player, arguments, tag_value)

    rows: list[DomainAction] = []
    match piece:
        case LoseInfluence():
            for faction in Faction:
                if influence_amount(owner.influence, faction) == 0:
                    continue
                recipients = alliance_recipients_after_influence_loss(
                    state, player, faction
                )
                for recipient in tuple(recipients) if len(recipients) > 1 else (None,):
                    arguments: tuple[tuple[str, ActionValue], ...] = (
                        ("faction", faction.value),
                    )
                    if recipient is not None:
                        arguments = (("alliance_recipient", recipient), *arguments)
                    rows.append(row(Verb.LOSE_INFLUENCE, Target.FACTION, arguments))
        case GainInfluence(distinct=distinct) as gain:
            taken = {Faction(value) for value in chosen}
            # Printed limits, never a cube already at the top (OQ-060).
            rows.extend(
                row(Verb.GAIN_INFLUENCE, Target.FACTION, (("faction", faction.value),))
                for faction in influence_gain_candidates(state, player, gain)
                if not (distinct and faction in taken)
            )
            if not rows:
                # Every Faction it may raise is at the top: the gain is lost
                # and its owner confirms it (OQ-060, user ruling 2026-09-30).
                rows.append(row(Verb.RESOLVE_EMPTY, of=Verb.GAIN_INFLUENCE))
        case DiscardFromHand():
            rows.extend(
                row(Verb.DISCARD, Target.PERSONAL_CARD, (("card_id", card_id),))
                for card_id in owner.hand
            )
        case DestroyShieldWall():
            # The detonation icon is a choice [Main pp. 10, 20].
            rows.append(row(Verb.DESTROY_SHIELD_WALL))
            rows.append(row(Verb.DECLINE, of=Verb.DESTROY_SHIELD_WALL))
        case DeployFromGarrison(up_to=up_to):
            # "Deploy up to N troops": zero stays offered; a garrisoned
            # Sardaukar Commander is a troop here [Bloodlines p. 4].
            troops, commanders = deployable_garrison_units(state, player)
            rows.extend(
                row(Verb.DEPLOY, Target.UNITS, arguments)
                for arguments in unit_count_arguments(
                    minimum=0, maximum=up_to, troops=troops, commanders=commanders
                )
            )
        case TrashPersonalCard(hand_only=hand_only, mandatory=mandatory):
            # The black trash icon is optional [Main p. 20]. A Row card
            # borrowed with Usurp is not "in play" (OQ-054).
            if refusals and not mandatory:
                rows.append(row(Verb.DECLINE, of=Verb.TRASH))
            candidates = (
                owner.hand
                if hand_only
                else (*owner.hand, *owner.discard_pile, *counted_in_play(owner))
            )
            rows.extend(
                row(Verb.TRASH, Target.PERSONAL_CARD, (("card_id", card_id),))
                for card_id in candidates
            )
        case LoseTroops(from_conflict=from_conflict):
            # The zone and, for a Sardaukar Commander, the kind (OQ-038).
            for zone in ("conflict",) if from_conflict else ("garrison", "conflict"):
                if getattr(owner, f"troops_{zone}"):
                    rows.append(row(Verb.LOSE_UNIT, Target.UNITS, (("zone", zone),)))
                if getattr(owner, f"commanders_{zone}"):
                    rows.append(
                        row(
                            Verb.LOSE_UNIT,
                            Target.UNITS,
                            (("commanders", 1), ("zone", zone)),
                        )
                    )
        case GiveIntrigueToOpponent():
            rows.extend(
                row(
                    Verb.GIVE,
                    Target.INTRIGUE_CARD,
                    (("card_id", held), ("player", seat.player_id)),
                )
                for held in owner.intrigue_cards
                if held != played_card_id
                for seat in state.players
                if seat.player_id != player
            )
        case TrashIntrigueCard():
            rows.extend(
                row(Verb.TRASH, Target.INTRIGUE_CARD, (("card_id", held),))
                for held in owner.intrigue_cards
                if held != played_card_id
            )
        case AcquireTleilaxuCard():
            # "You may also acquire a Tleilaxu card (paying its normal
            # cost)"; Reclaimed Forces is one too (OQ-066).
            deck_top = bool(owner.research_space) and (
                genetic_markers_reached(owner.research_space) >= 1
            )
            for instance_id in state.tleilaxu_row:
                if tleilaxu_card_for_instance(instance_id).specimen_cost > (
                    owner.specimens
                ):
                    continue
                arguments = (("instance_id", instance_id),)
                rows.append(row(Verb.ACQUIRE, Target.TLEILAXU_CARD, arguments))
                if deck_top:
                    rows.append(
                        row(
                            Verb.ACQUIRE,
                            Target.TLEILAXU_CARD,
                            (*arguments, ("to_deck_top", True)),
                        )
                    )
            rows.extend(
                row(Verb.ACQUIRE, Target.RECLAIMED_FORCES, (("choice", choice),))
                for choice in RECLAIMED_FORCES_CHOICES
                if reclaimed_forces_block(owner, choice) is None
            )
            if refusals:
                rows.append(row(Verb.DECLINE, of=Verb.ACQUIRE))
        case PeekTopCard():
            if owner.deck:
                rows.append(row(Verb.KEEP, variant="deck_top"))
                rows.append(row(Verb.DISCARD, variant="deck_top"))
                if owner.resources.solari >= 1:
                    rows.append(row(Verb.DRAW, variant="deck_top"))
        case RecallSpy():
            rows.extend(
                row(Verb.RECALL_SPY, Target.POST, (("post_id", post_id),))
                for post_id in owner.spy_post_ids
            )
        case RetreatTroops(minimum=minimum, maximum=maximum):
            # Commanders in the Conflict are troops for a retreat
            # [Bloodlines p. 4].
            rows.extend(
                row(Verb.RETREAT, Target.UNITS, arguments)
                for arguments in unit_count_arguments(
                    minimum=minimum,
                    maximum=maximum,
                    troops=owner.troops_conflict,
                    commanders=owner.commanders_conflict,
                )
            )
        case FlipBattleCard(icon=icon):
            rows.extend(
                row(Verb.FLIP, Target.CONFLICT_CARD, (("card_id", conflict_id),))
                for conflict_id in flippable_battle_card_ids(owner, icon)
            )
        case FlipFaceUpConflictCard():
            rows.extend(
                row(Verb.FLIP, Target.CONFLICT_CARD, (("card_id", conflict_id),))
                for conflict_id in face_up_conflict_card_ids(owner)
            )
        case TrashDiscardPileCard(minimum_cost=minimum_cost):
            # A cost: mandatory once the card is played [FAQ p. 3].
            rows.extend(
                row(Verb.TRASH, Target.PERSONAL_CARD, (("card_id", card_id),))
                for card_id in trashable_discard_pile_ids(owner, minimum_cost)
            )
        case SetAsideImperiumRowCard():
            rows.extend(
                row(Verb.SET_ASIDE, Target.IMPERIUM_CARD, (("instance_id", instance),))
                for instance in state.imperium_row
            )
        case AcquireCardUpTo(max_cost=max_cost):
            rows.extend(
                row(Verb.ACQUIRE, Target.RESERVE_CARD, (("card_id", card_id),))
                for card_id in acquirable_reserve_card_ids(state, max_cost)
            )
            rows.extend(
                row(Verb.ACQUIRE, Target.IMPERIUM_CARD, (("instance_id", instance),))
                # The owner's own Manipulate set-aside card is within reach
                # at its printed cost, never an opponent's [FAQ p. 3].
                for instance in acquirable_imperium_instance_ids(
                    state, max_cost, player=player
                )
            )
            if not rows:
                # Nothing within the cap: the acquisition alone fizzles
                # (designer ruling, Impress; OQ-057).
                rows.append(row(Verb.RESOLVE_EMPTY, of=Verb.ACQUIRE))
        case PlaceSpy():
            targets = spy_placement_targets(state, player, piece)
            if owner.spies_supply > 0:
                rows.extend(
                    row(Verb.PLACE_SPY, Target.POST, (("post_id", post_id),))
                    for post_id in targets
                )
            else:
                # With an empty supply one Spy may be recalled first
                # [Main pp. 11, 20], only where the placement stays
                # reachable: any Spy while a target post is free, else the
                # sole occupant of an allowed post.
                recallable = (
                    owner.spy_post_ids
                    if targets
                    else solo_occupied_post_ids(
                        state, player, spy_placement_allowed_post_ids(piece)
                    )
                )
                rows.extend(
                    row(Verb.RECALL_SPY, Target.POST, (("post_id", post_id),))
                    for post_id in recallable
                )
            # Placing is mandatory while a Spy and a post are free (the
            # designer's erratum to [Main p. 11], OQ-057); the placement is
            # passed up only when it cannot be made, whatever the turn.
            if owner.spies_supply == 0 or not targets:
                rows.append(row(Verb.DECLINE, of=Verb.PLACE_SPY))
    return tuple(rows)


# --- Rows of one entry -------------------------------------------------------


def ability_rows(
    state: GameState,
    player: int,
    entry: PendingAbility,
    presentation: Presentation,
    *,
    played_card_id: str | None = None,
    tag_value: ActionValue | None = None,
) -> tuple[DomainAction, ...]:
    """What ``entry`` offers ``player`` now under ``presentation``.

    The rows of its current piece, then -- when the presentation gives the
    automatic rewards their own row and every cost is paid -- the row that
    resolves them (OQ-015). With every piece taken and the rewards still to
    resolve (a draw kept as its own step, OQ-106) that row is all it offers.
    """

    sections = entry_sections(entry)
    pieces = choice_slots(sections, shield_wall_present=entry.shield_wall)
    rows: list[DomainAction] = []
    if entry.step < len(pieces):
        rows.extend(
            piece_rows(
                state,
                player,
                pieces[entry.step],
                entry.source,
                refusals=presentation.refusals,
                chosen=entry.chosen,
                played_card_id=played_card_id,
                tag_value=tag_value,
            )
        )
    if (
        presentation.rewards_row
        and not entry.rewards_applied
        and entry.step >= len(cost_slots(sections))
        and automatic_rewards(sections)
    ):
        resolve = template_id(Verb.RESOLVE, entry.source)
        rows.append(_row(resolve, player, (), tag_value))
    return tuple(rows)


# --- The pending list --------------------------------------------------------

type EntryRows[E] = Callable[[GameState, int, E], tuple[DomainAction, ...]]


def pending_rows[E: Hashable](
    state: GameState,
    player: int,
    entries: tuple[E, ...],
    rows_of: EntryRows[E],
) -> tuple[DomainAction, ...]:
    """Every pending entry's rows at once, in entry order.

    The Agent and Reveal turns' policy: each entry that can act offers what
    it would on its own (``rows_of``; () for one that waits), and a row two
    interchangeable entries offer (two copies of one card) appears once.
    """

    return tuple(
        dict.fromkeys(row for entry in entries for row in rows_of(state, player, entry))
    )


def entry_taking[E: Hashable](
    state: GameState,
    player: int,
    entries: tuple[E, ...],
    action: DomainAction,
    rows_of: EntryRows[E],
) -> int | None:
    """The index of the entry ``action`` answers: the first that offers it.

    None when no entry offers it (the action is the turn's own).
    """

    for index, entry in enumerate(entries):
        if action in rows_of(state, player, entry):
            return index
    return None


def holds_turn_end[E: Hashable](
    state: GameState,
    player: int,
    entries: tuple[E, ...],
    rows_of: EntryRows[E],
    mandatory: Callable[[E], bool],
) -> bool:
    """Whether a mandatory entry offers something now, holding the turn's end.

    One that offers nothing now (its condition fails, nothing to choose, its
    card left play) does not hold it and lapses with the end (OQ-057,
    OQ-095 (2), (7)); an optional one never holds it.
    """

    return any(
        mandatory(entry) and rows_of(state, player, entry) for entry in entries
    )
