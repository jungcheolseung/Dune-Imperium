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

Stage A0 built the executor; stage A1 (codec v148) wires the Intrigue cards
onto it: their choice frame stores one ``PendingAbility``, offers
``ability_rows`` and applies each answer with ``apply_piece`` and the
automatic rewards with ``apply_automatic_rewards``; their separate-lines
frame (OQ-058) stores a pending list of one entry per line not used yet,
while its own rows (use a line, finish the card) stay the Intrigue
module's. Later stages move the Agent boxes, the Reveal choices and the
rest (plan 5); until stage A4 the tests still hold the pending-list policy
to the Reveal frame's rows, its hold of the turn end and the entry an
action takes.

What a stage still keeps outside: tags (a grafted turn's ``box=1``, a
revealed card's ``source``) are given by the caller, which knows the box or
card; the frames, the events of the card's own play and finish, and the
frame context keys a page or the observation reads stay the adopting
module's.
"""

from collections.abc import Callable, Hashable, Mapping
from copy import replace
from dataclasses import dataclass
from functools import cache, lru_cache
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
    DrawIntrigueCards,
    DrawPersonalCards,
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
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import (
    IntrigueAcquisition,
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
    acquire_imperium_for_intrigue,
    acquire_reserve_for_intrigue,
    take_imperium_row_card,
)
from dune_imperium.rules.action_shapes import (
    Source,
    Target,
    Verb,
    action_shape,
    printer_value,
    template_id,
)
from dune_imperium.rules.card_bonds import trashable_cards
from dune_imperium.rules.card_discard import (
    discard_personal_card_from_hand,
    resolve_personal_card_discard_trigger,
)
from dune_imperium.rules.card_trash import credit_trash_recruits, trash_personal_card
from dune_imperium.rules.combat_deployment import (
    grant_combat_icon,
    reconcile_deployment_after_retreat,
)
from dune_imperium.rules.effect_interpreter import (
    ChoiceSlot,
    apply_rewards,
    automatic_rewards,
    choice_slots,
    condition_holds,
    cost_slots,
    deployable_garrison_units,
    face_up_conflict_card_ids,
    flippable_battle_card_ids,
    influence_gain_candidates,
    trashable_discard_pile_ids,
)
from dune_imperium.rules.effects import (
    agent_turn_space_id,
    open_next_turn,
    recruit_shortfall_events,
    recruit_troops,
)
from dune_imperium.rules.frames import (
    replace_player,
    reveal_is_open_for,
    turn_owner_of,
    update_turn_recruits,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import with_trashed_intrigue
from dune_imperium.rules.planetologist import replace_sandworms
from dune_imperium.rules.reveal_turn import (
    add_reveal_persuasion,
    add_reveal_strength,
    add_units_to_reveal,
    reveal_late_arrivals,
)
from dune_imperium.rules.shield_wall import destroy_shield_wall
from dune_imperium.rules.spy_moves import (
    connected_post_ids,
    spy_placement_frame,
    turn_space_spy_frames,
)
from dune_imperium.rules.spy_placement import (
    place_spy,
    recall_spy,
    spy_options,
    spy_placement_allowed_post_ids,
)
from dune_imperium.rules.strength import reveal_in_progress
from dune_imperium.rules.tactics import advance_tactics_token
from dune_imperium.rules.tech import push_tech_acquisition
from dune_imperium.rules.tleilaxu_row import (
    RECLAIMED_FORCES_CHOICES,
    acquire_reclaimed_forces,
    acquire_tleilaxu_card,
    reclaimed_forces_block,
)
from dune_imperium.rules.unit_loss import lose_unit
from dune_imperium.rules.units import retreat_units, unit_count_arguments, unit_counts

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
    rewards already resolved on their own row. ``held`` lists values a step
    named whose effect waits for a later step (the Factions "Choose two"
    names before either Influence moves, OQ-057), and ``tally`` counts what
    a cost paid one unit per step has taken so far (the troops a "lose N
    troops" cost took from the Conflict, which move the Tactics token once,
    ``apply_piece``).

    A separate-lines ability (OQ-058) waits as a pending list of one entry
    per line not used yet (``encode_pending``); a line used resolves as its
    own entry.
    """

    source: Source
    ref: str
    sections: tuple[int, ...]
    step: int = 0
    chosen: tuple[str, ...] = ()
    rewards_applied: bool = False
    shield_wall: bool = True
    held: tuple[str, ...] = ()
    tally: int = 0

    def __post_init__(self) -> None:
        if self.step < 0 or self.tally < 0:
            raise ValueError("a pending ability cannot take a negative step or tally")
        if any(index < 0 for index in self.sections):
            raise ValueError("section indexes must not be negative")
        for text in (self.ref, *self.chosen, *self.held):
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
                _ITEM.join(self.held),
                str(self.tally),
            )
        )

    @staticmethod
    def decode(text: str) -> PendingAbility:
        """Read an entry ``encode`` wrote; raises ``ValueError`` otherwise."""

        return _decode(text)


# An open frame's entry is read on every legal-action call; the entry is
# immutable, so one string always reads back as the same entry.
@lru_cache(maxsize=4096)
def _decode(text: str) -> PendingAbility:
    fields = text.split(_FIELD)
    if len(fields) != 9 or fields[5] not in ("0", "1") or fields[6] not in (
        "0",
        "1",
    ):
        raise ValueError(f"not a stored pending ability: {text!r}")
    source, ref, sections, step, chosen, applied, wall, held, tally = fields
    return PendingAbility(
        source=Source(source),
        ref=ref,
        sections=tuple(int(index) for index in sections.split(_ITEM) if index),
        step=int(step),
        chosen=tuple(value for value in chosen.split(_ITEM) if value),
        rewards_applied=applied == "1",
        shield_wall=wall == "1",
        held=tuple(value for value in held.split(_ITEM) if value),
        tally=int(tally),
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


def split_intrigue_ref(ref: str) -> tuple[str, int]:
    """The card instance and option index ``intrigue_ref`` joined."""

    card_id, mark, option = ref.rpartition("#")
    if not mark or not card_id or not option.isdigit():
        raise ValueError(f"not an Intrigue option reference: {ref!r}")
    return card_id, int(option)


# A card instance's options never change, and the engine reads an open
# entry's ability on every legal-action call.
@cache
def _intrigue_ref_ability(ref: str) -> Ability:
    card_id, option = split_intrigue_ref(ref)
    return intrigue_ability(intrigue_card_for_instance(card_id).options[option])


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
    empty_confirm: bool = True,
) -> tuple[DomainAction, ...]:
    """The rows that answer ``piece`` for ``player``, named for ``source``.

    ``refusals`` adds an optional piece's refusal (``Presentation``);
    ``chosen`` holds the Factions an earlier step of a "distinct" gain took;
    ``played_card_id`` is the Intrigue card being played, still held while it
    resolves and never its own cost; ``tag_value`` tags a tagged template
    (``action_shapes.Tag``). ``empty_confirm`` gives a gain or an
    acquisition with nothing to take its confirmation row (a stacked
    frame's, OQ-060, OQ-057); an Agent box offers none and waits instead.
    The targets and their order are the ones the engine offered before the
    executor (``intrigue.legal_intrigue_choice_actions`` up to codec v147,
    which offers these rows since stage A1).
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
            if not rows and empty_confirm:
                # Every Faction it may raise is at the top: the gain is lost
                # and its owner confirms it (OQ-060, user ruling 2026-09-30).
                rows.append(row(Verb.CONFIRM_EMPTY, of=Verb.GAIN_INFLUENCE))
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
            rows.extend(
                row(Verb.TRASH, Target.PERSONAL_CARD, (("card_id", card_id),))
                for card_id in trashable_cards(owner, hand_only=hand_only)
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
            if not rows and empty_confirm:
                # Nothing within the cap: the acquisition alone fizzles
                # (designer ruling, Impress; OQ-057).
                rows.append(row(Verb.CONFIRM_EMPTY, of=Verb.ACQUIRE))
        case PlaceSpy():
            # Placing is mandatory while a Spy and a post are free (the
            # designer's erratum to [Main p. 11], OQ-057); the placement is
            # passed up (first) only when it cannot be made, whatever the
            # turn, and a recall-first comes only where it opens a post
            # (``spy_options``).
            options = spy_options(
                state,
                player,
                spy_placement_allowed_post_ids(piece),
                shared_post=piece.shared_post,
            )
            if options.pass_up:
                rows.append(row(Verb.DECLINE, of=Verb.PLACE_SPY))
            rows.extend(
                row(Verb.RECALL_SPY, Target.POST, (("post_id", post_id),))
                for post_id in options.recall
            )
            rows.extend(
                row(Verb.PLACE_SPY, Target.POST, (("post_id", post_id),))
                for post_id in options.place
            )
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


def rewards_wait(entry: PendingAbility) -> bool:
    """Whether every piece is taken and the automatic rewards wait for their step.

    Icons on one line are independent effects in the owner's order (OQ-015
    (d)), so the rewards may resolve before, between or after the reward
    pieces (the rewards row). When they draw hidden cards and the owner took
    the last reward piece first -- Cunning's and Insider Information's
    trash before their draw -- the draw stays its own step instead of riding
    on that piece, so the public choice stays undoable and only the draw
    closes the undo window (OQ-010): "그 외에는 전부 나누자. 특히 카드
    드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를 폐기하고 싶을 수
    있잖아." (user ruling 2026-10-10, OQ-106). Rewards that draw nothing
    still finish with the last piece, and so does a line whose only pieces
    are arrow costs ("discard -> draw"): the cost is paid for that draw, one
    printed unit [Main pp. 9, 20].
    """

    sections = entry_sections(entry)
    pieces = choice_slots(sections, shield_wall_present=entry.shield_wall)
    return (
        not entry.rewards_applied
        and entry.step >= len(pieces)
        and len(pieces) > len(cost_slots(sections))
        and any(
            isinstance(reward, DrawPersonalCards | DrawIntrigueCards)
            for reward in automatic_rewards(sections)
        )
    )


# --- Applying one piece ------------------------------------------------------

# What a refusal or an empty confirmation of a piece announces, by its
# template: the event id's suffix and the event kind. A stage that sends
# another source through ``apply_piece`` adds its templates. (The empty
# confirmation of an acquisition piece is announced by the frame that
# orders the acquisition, which names the card too.)
_PASSED_EVENTS: Final[Mapping[str, tuple[str, str]]] = {
    # One kind for a refused optional trash, wherever it is offered
    # (cleanup-2c-6).
    "decline_intrigue_trash": ("trash_declined", "optional_trash_declined"),
    "decline_intrigue_tleilaxu": (
        "tleilaxu_declined",
        "intrigue_tleilaxu_acquisition_declined",
    ),
    "decline_intrigue_spy": ("spy_declined", "intrigue_spy_declined"),
    "keep_shield_wall": ("shield_wall_kept", "shield_wall_kept"),
    "resolve_intrigue_influence_without_faction": (
        "influence_unavailable",
        "intrigue_influence_unavailable",
    ),
}
# The event a Faction named for a later step announces (``held``), by source.
_HELD_FACTION_EVENTS: Final[Mapping[Source, str]] = {
    Source.INTRIGUE: "intrigue_influence_chosen",
}


def table_event_kinds() -> frozenset[str]:
    """The event kinds ``apply_piece`` names through its tables.

    The page labels every event kind the engine emits; a source scan for
    ``kind="..."`` does not see these (tests/server/test_action_labels.py).
    """

    return frozenset(
        (
            *(kind for _suffix, kind in _PASSED_EVENTS.values()),
            *_HELD_FACTION_EVENTS.values(),
        )
    )


@dataclass(frozen=True, slots=True)
class PieceApplied:
    """One answered piece: what it did, and its entry afterwards.

    ``entry`` has taken the step, unless the answer only prepared the piece
    (a Spy recalled from an empty supply before the placement [Main pp. 11,
    20]): then ``stays`` is true and ``entry`` is the one answered.
    """

    result: RuleResult
    entry: PendingAbility
    stays: bool = False


def _passed(
    state: GameState,
    player: int,
    action: DomainAction,
    step_source: str,
) -> RuleResult:
    """The event of a refusal or an empty confirmation, nothing else."""

    suffix, kind = _PASSED_EVENTS[action.action_id]
    return RuleResult(
        state=state,
        events=(
            GameEvent(
                event_id=f"{step_source}:{suffix}",
                kind=kind,
                payload=(("player", player),),
            ),
        ),
    )


def apply_piece(
    state: GameState,
    player: int,
    entry: PendingAbility,
    action: DomainAction,
    *,
    source: str,
) -> PieceApplied:
    """Apply ``action``, an answer to ``entry``'s current piece.

    What the answer does is read from its shape (``action_shapes``): a
    refusal, an empty confirmation, the recall that prepares a Spy
    placement, the zone or kind of a unit. ``source`` is the ability's event
    source; the piece's events are ``<source>:slot:<step>:...``. An
    acquisition piece is resolved by ``acquire_by_piece`` instead, since its
    follow-up frames open only after the ability finishes.
    """

    pieces = entry_pieces(entry)
    if entry.step >= len(pieces):
        raise RuntimeError("the pending ability has no piece left to answer")
    piece = pieces[entry.step]
    shape = action_shape(action.action_id)
    arguments = dict(action.arguments)
    step_source = f"{source}:slot:{entry.step}"
    taken = replace(entry, step=entry.step + 1)

    match piece:
        case AcquireCardUpTo():
            raise ValueError("an acquisition piece resolves through acquire_by_piece")
        case SetAsideImperiumRowCard():
            instance_id = str(arguments["instance_id"])
            imperium_row, imperium_deck = take_imperium_row_card(state, instance_id)
            owner = state.players[player]
            keeper = replace(
                owner,
                imperium_set_aside=(*owner.imperium_set_aside, instance_id),
            )
            result = RuleResult(
                state=replace(
                    state,
                    players=replace_player(state.players, keeper),
                    imperium_deck=imperium_deck,
                    imperium_row=imperium_row,
                ),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:set_aside:{instance_id}",
                        kind="imperium_row_card_set_aside",
                        payload=(
                            (
                                "card_id",
                                imperium_card_for_instance(instance_id).card.card_id,
                            ),
                            ("instance_id", instance_id),
                            ("player", player),
                        ),
                    ),
                ),
            )
        case TrashDiscardPileCard():
            result = trash_personal_card(
                state, player, str(arguments["card_id"]), source=step_source
            )
            # No AGENT_EFFECTS frame is on top here, so ``trash_personal_card``
            # credited no troop-on-trash trigger (Eliminate Allies) anywhere. A
            # troop recruited during the owner's own turn "from any source" may
            # be deployed [Main p. 10] [FAQ p. 4].
            result = credit_trash_recruits(result, player)
        case AcquireTleilaxuCard():
            if shape.verb is Verb.DECLINE:
                result = _passed(state, player, action, step_source)
            elif shape.target is Target.RECLAIMED_FORCES:
                result = acquire_reclaimed_forces(
                    state, player, str(arguments["choice"]), source=step_source
                )
            else:
                result = acquire_tleilaxu_card(
                    state,
                    player,
                    str(arguments["instance_id"]),
                    to_deck_top=arguments.get("to_deck_top") is True,
                    source=step_source,
                )
        case FlipBattleCard() | FlipFaceUpConflictCard():
            flipped_id = str(arguments["card_id"])
            owner = state.players[player]
            flipped_owner = replace(
                owner,
                face_down_battle_card_ids=(
                    *owner.face_down_battle_card_ids,
                    flipped_id,
                ),
            )
            result = RuleResult(
                state=replace(
                    state, players=replace_player(state.players, flipped_owner)
                ),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:flipped:{flipped_id}",
                        kind="battle_card_flipped",
                        payload=(("card_id", flipped_id), ("player", player)),
                    ),
                ),
            )
        case LoseInfluence():
            faction = Faction(str(arguments["faction"]))
            recipient = arguments.get("alliance_recipient")
            assert recipient is None or isinstance(recipient, int)
            result = lose_faction_influence(
                state,
                player,
                faction,
                1,
                event_prefix=f"{step_source}:lost:{faction.value}",
                alliance_recipient=recipient,
            )
        case GainInfluence() if shape.verb is Verb.CONFIRM_EMPTY:
            # No Faction this gain may raise is below the top: it is lost
            # (OQ-060), while a "Choose two" Faction named before it is still
            # paid ("서로 다른 진영 둘"은 먼저 이름 붙인 진영을 그대로 지급).
            lost = _passed(state, player, action, step_source)
            result = _gain_factions(
                lost.state, player, entry.held, step_source, lost.events
            )
            taken = replace(taken, held=())
        case GainInfluence(distinct=distinct):
            faction = Faction(str(arguments["faction"]))
            later_distinct = distinct and any(
                isinstance(later, GainInfluence) and later.distinct
                for later in pieces[entry.step + 1 :]
            )
            taken = replace(taken, chosen=(*entry.chosen, faction.value))
            if later_distinct:
                # "Choose two" (Rapid Engineering): both Factions are named
                # before either Influence moves (designer ruling, OQ-057).
                taken = replace(taken, held=(*entry.held, faction.value))
                result = RuleResult(
                    state=state,
                    events=(
                        GameEvent(
                            event_id=f"{step_source}:chosen:{faction.value}",
                            kind=_HELD_FACTION_EVENTS[entry.source],
                            payload=(("faction", faction.value), ("player", player)),
                        ),
                    ),
                )
            else:
                result = _gain_factions(
                    state, player, (*entry.held, faction.value), step_source, ()
                )
                taken = replace(taken, held=())
        case DiscardFromHand():
            result = discard_personal_card_from_hand(
                state, player, str(arguments["card_id"]), source=step_source
            )
        case DestroyShieldWall():
            if shape.verb is Verb.DESTROY_SHIELD_WALL:
                result = destroy_shield_wall(
                    state, event_id=f"{step_source}:shield_wall", source=source
                )
            else:
                result = _passed(state, player, action, step_source)
        case DeployFromGarrison():
            count, commanders = unit_counts(arguments)
            if count + commanders == 0:
                # "Deploy up to N troops" chose zero: no unit moves.
                result = RuleResult(state=state)
            else:
                result = _deploy_units(
                    state, player, step_source, troops=count, commanders=commanders
                )
        case TrashPersonalCard(bonus_spice=bonus_spice, bonus_minimum_cost=minimum):
            if shape.verb is Verb.DECLINE:
                result = _passed(state, player, action, step_source)
            else:
                trashed_id = str(arguments["card_id"])
                result = trash_personal_card(
                    state, player, trashed_id, source=step_source
                )
                # As for the discard-pile trash above [Main p. 10] [FAQ p. 4].
                result = credit_trash_recruits(result, player)
                cost = getattr(
                    personal_card_for_instance(trashed_id), "acquisition_cost", None
                )
                if bonus_spice and isinstance(cost, int) and cost >= minimum:
                    # Navigation card 5: spice for a card printed with a cost.
                    paid = result.state.players[player]
                    result = RuleResult(
                        state=replace(
                            result.state,
                            players=replace_player(
                                result.state.players,
                                replace(
                                    paid,
                                    resources=replace(
                                        paid.resources,
                                        spice=paid.resources.spice + bonus_spice,
                                    ),
                                ),
                            ),
                        ),
                        events=result.events,
                    )
        case RetreatTroops():
            count, commanders = unit_counts(arguments)
            if count + commanders == 0:
                # Tactical Option's "any number" retreat chose zero [Main
                # p. 20] [FAQ p. 3]: no unit moves.
                result = RuleResult(state=state)
            else:
                result = _retreat_units(
                    state, player, step_source, troops=count, commanders=commanders
                )
                result = _follow_reveal_strength(state, result, player)
        case LoseTroops():
            zone = str(arguments["zone"])
            commander = arguments.get("commanders") == 1
            result = lose_unit(
                state,
                player,
                zone,
                commander=commander,
                source=step_source,
                advance_tactics=False,
            )
            if zone == "conflict":
                result = RuleResult(
                    state=reconcile_deployment_after_retreat(
                        result.state,
                        player,
                        troops=int(not commander),
                        commanders=int(commander),
                    ),
                    events=result.events,
                )
                result = _follow_reveal_strength(state, result, player)
            # The cost is paid one troop per piece, but it is one source:
            # "Each different source of retreating or losing troops is
            # handled separately" [FAQ p. 1], and "If you lose or retreat
            # enough troops that you would pass the end of the Tactics
            # track, you still reset at the starting space (and do not
            # advance for those extra troops)" [Bloodlines p. 12]. Chani's
            # Tactics token moves once, on the cost's last piece.
            from_conflict = entry.tally + int(zone == "conflict")
            following = pieces[entry.step + 1] if entry.step + 1 < len(pieces) else None
            if following is piece:
                taken = replace(taken, tally=from_conflict)
            else:
                taken = replace(taken, tally=0)
                tactician, tactics_events = advance_tactics_token(
                    result.state.players[player],
                    from_conflict,
                    round_number=result.state.round_number,
                )
                result = RuleResult(
                    state=replace(
                        result.state,
                        players=replace_player(result.state.players, tactician),
                    ),
                    events=(*result.events, *tactics_events),
                )
        case GiveIntrigueToOpponent(bonus_spice_if_not_twisted=bonus):
            result = _give_intrigue_card(
                state,
                player,
                str(arguments["card_id"]),
                arguments["player"],
                bonus,
                step_source,
            )
        case TrashIntrigueCard(troops_if_not_twisted=troops_bonus):
            result = _trash_intrigue_hand_card(
                state, player, str(arguments["card_id"]), troops_bonus, step_source
            )
        case PeekTopCard():
            result = _resolve_peek(state, player, shape.verb, step_source)
        case PlaceSpy() if shape.verb is Verb.DECLINE:
            # The Spy placement is passed up only when it cannot be made
            # (``piece_rows``).
            result = _passed(state, player, action, step_source)
        case RecallSpy() | PlaceSpy():
            post_id = str(arguments["post_id"])
            owner = state.players[player]
            if shape.verb is Verb.RECALL_SPY:
                next_owner = recall_spy(owner, post_id)
                kind = "spy_recalled"
            else:
                next_owner = place_spy(owner, post_id)
                kind = "spy_placed"
            result = RuleResult(
                state=replace(state, players=replace_player(state.players, next_owner)),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:{kind}:{post_id}",
                        kind=kind,
                        payload=(("player", player), ("post_id", post_id)),
                    ),
                ),
            )
            if isinstance(piece, PlaceSpy) and kind == "spy_recalled":
                # The recall only prepared the placement; stay on this piece.
                return PieceApplied(result, entry, stays=True)
        case _:
            raise RuntimeError(f"the executor cannot apply {piece!r}")
    return PieceApplied(result, taken)


def acquires_to_hand(state: GameState, player: int, piece: AcquireCardUpTo) -> bool:
    """Whether the piece's "Put that card in your hand" applies.

    It overrides the discard destination only while its printed condition
    holds when the piece is answered, judged before the piece's frame moves
    on (``acquire_by_piece``).
    """

    return piece.to_hand_if is not None and condition_holds(
        state, player, piece.to_hand_if
    )


def acquire_by_piece(
    state: GameState,
    player: int,
    action: DomainAction,
    *,
    to_hand: bool,
    step_source: str,
) -> IntrigueAcquisition | None:
    """Acquire the card ``action`` names for an acquisition piece.

    None when the answer confirms that nothing is within the cap (designer
    ruling, Impress; OQ-057). ``to_hand`` is ``acquires_to_hand`` on the
    state the answer was given in.
    """

    shape = action_shape(action.action_id)
    if shape.verb is Verb.CONFIRM_EMPTY:
        return None
    arguments = dict(action.arguments)
    if shape.target is Target.RESERVE_CARD:
        return acquire_reserve_for_intrigue(
            state,
            player,
            str(arguments["card_id"]),
            to_hand=to_hand,
            source=step_source,
        )
    return acquire_imperium_for_intrigue(
        state,
        player,
        str(arguments["instance_id"]),
        to_hand=to_hand,
        source=step_source,
    )


def _gain_factions(
    state: GameState,
    player: int,
    factions: tuple[str, ...],
    step_source: str,
    events: tuple[GameEvent, ...],
) -> RuleResult:
    """One Influence with each Faction in turn, after ``events``."""

    working = state
    gained_events: list[GameEvent] = list(events)
    for value in factions:
        gained = gain_faction_influence(
            working,
            player,
            Faction(value),
            1,
            event_prefix=f"{step_source}:gained:{value}",
        )
        working = gained.state
        gained_events.extend(gained.events)
    return RuleResult(state=working, events=tuple(gained_events))


def _give_intrigue_card(
    state: GameState,
    player: int,
    card_id: str,
    recipient: ActionValue,
    bonus_spice: int,
    step_source: str,
) -> RuleResult:
    """Insidious: hand an Intrigue card to an opponent, extra spice if regular."""

    if isinstance(recipient, bool) or not isinstance(recipient, int):
        raise RuntimeError("Intrigue gift has an invalid recipient")
    owner = state.players[player]
    target = state.players[recipient]
    twisted = intrigue_card_for_instance(card_id).twisted
    extra = 0 if twisted else bonus_spice
    giver = replace(
        owner,
        intrigue_cards=tuple(held for held in owner.intrigue_cards if held != card_id),
        resources=replace(owner.resources, spice=owner.resources.spice + extra),
    )
    receiver = replace(target, intrigue_cards=(*target.intrigue_cards, card_id))
    players = replace_player(replace_player(state.players, giver), receiver)
    return RuleResult(
        state=replace(state, players=players),
        events=(
            # The table sees a card change hands; only the two seats
            # involved learn which one [Main p. 7].
            GameEvent(
                event_id=f"{step_source}:given",
                kind="intrigue_card_given",
                payload=(
                    ("bonus_spice", extra),
                    ("player", player),
                    ("recipient", recipient),
                ),
            ),
            GameEvent(
                event_id=f"{step_source}:given:card",
                kind="intrigue_card_given_identity",
                payload=(
                    ("card_id", card_id),
                    ("player", player),
                    ("recipient", recipient),
                ),
                visible_to=(player, recipient),
            ),
        ),
    )


def _trash_intrigue_hand_card(
    state: GameState,
    player: int,
    card_id: str,
    troops_bonus: int,
    step_source: str,
) -> RuleResult:
    """Trash an Intrigue card from hand [Bloodlines p. 11]; Unnatural's troop.

    The troop joins the owner's open turn [Main p. 10] [FAQ p. 4], guarded
    by ``turn_owner_of`` like ``apply_automatic_rewards``: nothing is
    credited outside the owner's own turn. The trashed card joins the
    shared Intrigue discard (OQ-061, user ruling 2026-10-04), a Twisted one
    included as a played Twisted card already does; a Twisted card stays
    there when the discard is reshuffled (OQ-097, ``shufflable_intrigue_
    discard``).
    """

    owner = state.players[player]
    twisted = intrigue_card_for_instance(card_id).twisted
    next_owner = replace(
        owner,
        intrigue_cards=tuple(held for held in owner.intrigue_cards if held != card_id),
    )
    recruited = 0
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{step_source}:intrigue_trashed",
            kind="intrigue_card_trashed",
            payload=(("card_id", card_id), ("player", player)),
        )
    ]
    if not twisted and troops_bonus:
        next_owner, recruited = recruit_troops(next_owner, troops_bonus)
        events.extend(
            recruit_shortfall_events(step_source, player, troops_bonus, recruited)
        )
    next_state = with_trashed_intrigue(
        replace(state, players=replace_player(state.players, next_owner)),
        card_id,
    )
    if recruited and turn_owner_of(next_state) == player:
        next_state = update_turn_recruits(next_state, troops_recruited=recruited)
    return RuleResult(state=next_state, events=tuple(events))


def _resolve_peek(
    state: GameState,
    player: int,
    verb: Verb,
    step_source: str,
) -> RuleResult:
    """Controlled: put the top card back, discard it, or pay a Solari to draw it.

    The discard branch fires the card's own "When this card is discarded"
    trigger (OQ-013, user ruling 2026-10-04).
    """

    owner = state.players[player]
    if not owner.deck:
        raise RuntimeError("Controlled needs a card on top of the deck")
    top = owner.deck[0]
    if verb is Verb.KEEP:
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{step_source}:put_back",
                    kind="top_card_put_back",
                    payload=(("player", player),),
                ),
            ),
        )
    if verb is Verb.DISCARD:
        discarded = replace(
            state,
            players=replace_player(
                state.players,
                replace(
                    owner,
                    deck=owner.deck[1:],
                    discard_pile=(*owner.discard_pile, top),
                ),
            ),
        )
        # A deck discard fires the card's own "When this card is discarded"
        # trigger as a project convention (OQ-013, user ruling 2026-10-04),
        # although the official text reads "Only discarding it from your hand
        # triggers the ability." [Main p. 17]. Putting the card back or paying
        # to draw it is not a discard.
        triggered = resolve_personal_card_discard_trigger(
            discarded, player, top, source=step_source
        )
        return RuleResult(
            state=triggered.state,
            events=(
                GameEvent(
                    event_id=f"{step_source}:top_card_discarded",
                    kind="top_card_discarded",
                    payload=(("card_id", top), ("player", player)),
                ),
                *triggered.events,
            ),
        )
    if owner.resources.solari < 1:
        raise RuntimeError("drawing the peeked card costs one Solari")
    next_owner = replace(
        owner,
        deck=owner.deck[1:],
        hand=(*owner.hand, top),
        resources=replace(owner.resources, solari=owner.resources.solari - 1),
    )
    drawn = replace(state, players=replace_player(state.players, next_owner))
    event = GameEvent(
        event_id=f"{step_source}:top_card_drawn",
        kind="top_card_drawn",
        payload=(("player", player),),
    )
    if reveal_is_open_for(drawn, player):
        # "Reveal turn 도중 card를 draw하면 즉시 그 card를 reveal하고 이번
        # Reveal turn에 사용한다." [FAQ p. 3] (docs/rules/player-turns.md:205):
        # a Plot played in the Reveal turn draws like every other draw
        # (``card_draw``), not into a hand kept to the next round.
        late = reveal_late_arrivals(drawn, player, (top,))
        return RuleResult(state=late.state, events=(event, *late.events))
    return RuleResult(state=drawn, events=(event,))


def _follow_reveal_strength(
    state: GameState, result: RuleResult, player: int
) -> RuleResult:
    """Keep the Reveal frame's counted strength in step with the seat's total.

    A Plot Intrigue played during the owner's Reveal turn may pay a cost
    that removes units from the Conflict (Twisted Ambitious's three troops).
    ``retreat_units`` already sets the running ``combat_strength`` -- "마지막
    unit이 제거되면 sword가 남아 있어도 strength는 0이 된다" [Main p. 12]
    (docs/rules/player-turns.md 231) -- but the Reveal frame keeps its own
    tally for the Desert Power mirror in ``add_units_to_reveal``, and a
    stale tally made the next Combat-icon deployment count a negative
    delta (2026-09-16 A/B, CHOAM+Bloodlines+Tech seed 262). The two Reveal
    handlers that remove units (``apply_reveal_troop_sacrifice`` and the
    card troop retreat) already do this; the Intrigue costs join them. The
    RetreatTroops branch is defensive: today every Intrigue retreat is
    Combat-timed, when no Reveal frame is open, so it is a no-op there.
    """

    if not reveal_in_progress(state, player):
        return result
    delta = (
        result.state.players[player].combat_strength
        - state.players[player].combat_strength
    )
    if not delta:
        return result
    return RuleResult(
        state=replace(
            result.state,
            decision_stack=add_reveal_strength(result.state.decision_stack, delta),
        ),
        events=result.events,
    )


def _retreat_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
    commanders: int = 0,
) -> RuleResult:
    """Return Conflict units to the garrison (see ``rules.units``).

    An Agent-turn retreat also shrinks the turn's withdrawal window so it
    cannot underflow; the deployment allowance stays used (OQ-029,
    ``combat_deployment.reconcile_deployment_after_retreat``).
    """

    retreated = retreat_units(
        state, player, step_source, troops=troops, commanders=commanders
    )
    return RuleResult(
        state=reconcile_deployment_after_retreat(
            retreated.state, player, troops=troops, commanders=commanders
        ),
        events=retreated.events,
    )


def _deploy_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
    commanders: int = 0,
) -> RuleResult:
    """Move garrison units into the Conflict, counting strength mid-Reveal."""

    owner = state.players[player]
    if (
        troops < 0
        or commanders < 0
        or troops + commanders < 1
        or owner.troops_garrison < troops
        or owner.commanders_garrison < commanders
    ):
        raise RuntimeError("Intrigue deployment exceeds the garrison")
    event = GameEvent(
        event_id=f"{step_source}:deploy",
        kind="troops_deployed",
        payload=(
            *((("commanders", commanders),) if commanders else ()),
            ("count", troops + commanders),
            ("player", player),
        ),
    )
    if reveal_is_open_for(state, player):
        counted = add_units_to_reveal(
            state, player, troops=troops, commanders=commanders
        )
        return RuleResult(state=counted.state, events=(event, *counted.events))
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=owner.troops_conflict + troops,
        commanders_garrison=owner.commanders_garrison - commanders,
        commanders_conflict=owner.commanders_conflict + commanders,
        units_deployed_turn=owner.units_deployed_turn + troops + commanders,
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(event,),
    )


# --- Applying the automatic rewards -------------------------------------------


def apply_automatic_rewards(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
    source: str,
    *,
    played_card_id: str,
) -> RuleResult:
    """Apply the played Intrigue card's automatic rewards and their turn
    bookkeeping.

    ``update_turn_recruits`` finds whatever turn-family frame is nearest the
    top regardless of whose it is, so the troop credit is guarded by
    ``turn_owner_of`` against crediting a different seat's frame (a
    Navigation card triggered outside its owner's turn) [Main p. 10]
    [FAQ p. 4].
    """

    outcome = apply_rewards(state, player, automatic_rewards(sections), source=source)
    next_state = _gain_reveal_persuasion_now(state, outcome.result.state, player)
    events: list[GameEvent] = list(outcome.result.events)
    if outcome.troops_recruited and turn_owner_of(next_state) == player:
        next_state = update_turn_recruits(
            next_state, troops_recruited=outcome.troops_recruited
        )
    if outcome.combat_icons:
        next_state = grant_combat_icon(next_state, player)
    if outcome.sandworms_replaced:
        replacement = replace_sandworms(
            next_state, player, outcome.sandworms_replaced, source=source
        )
        next_state = replacement.state
        events.extend(replacement.events)
    for reserve_card_id in outcome.reserve_acquisitions:
        # Navigation card 4: acquire The Spice Must Flow (its acquisition
        # Victory Point included) when a copy is left.
        if dict(next_state.reserve_stacks).get(reserve_card_id, 0) < 1:
            events.append(
                GameEvent(
                    event_id=f"{source}:reserve_exhausted:{reserve_card_id}",
                    kind="reserve_acquisition_unavailable",
                    payload=(("card_id", reserve_card_id), ("player", player)),
                )
            )
            continue
        acquired = acquire_reserve_for_intrigue(
            next_state,
            player,
            reserve_card_id,
            to_hand=False,
            source=source,
        )
        next_state = acquired.result.state
        events.extend(acquired.result.events)
    for discount in outcome.tech_acquisitions:
        # Battlefield Research / Rapid Engineering: the Tech Discount icon
        # opens its own Acquire Tech [Bloodlines pp. 7, 12].
        opened = push_tech_acquisition(
            next_state,
            player,
            discount=discount,
            source=source,
            printer=printer_value(
                Source.INTRIGUE, intrigue_card_for_instance(played_card_id).card.card_id
            ),
        )
        next_state = opened.state
        events.extend(opened.events)
    if outcome.passes_turn:
        # Withdrawn: the turn ends at once; the seat stays unrevealed.
        next_state = open_next_turn(next_state, player)
        events.append(
            GameEvent(
                event_id=f"{source}:turn_passed",
                kind="turn_passed",
                payload=(("player", player),),
            )
        )
    if outcome.redirects_turn_space_spies:
        # False Orders: the owner's placement waits beneath the opponents'
        # forced moves so it resolves after them ("Then you place a Spy").
        space_id = agent_turn_space_id(next_state, player)
        if space_id is None:
            raise RuntimeError("False Orders needs this turn's Agent placement")
        printed = intrigue_card_for_instance(played_card_id).card.card_id
        next_state = spy_placement_frame(
            next_state,
            player,
            connected_post_ids(space_id),
            source=source,
            printer=printer_value(Source.INTRIGUE, printed),
        )
        moved = turn_space_spy_frames(
            next_state,
            player,
            space_id,
            source=source,
            printer=printer_value(Source.INTRIGUE, printed),
        )
        next_state = moved.state
        events.extend(moved.events)
    if outcome.sandworms_deployed and reveal_is_open_for(next_state, player):
        # The interpreter moved the sandworms; during a Reveal turn their
        # strength must also join the revealed total [Main p. 13].
        owner = next_state.players[player]
        rolled_back = replace(
            next_state,
            players=replace_player(
                next_state.players,
                replace(
                    owner,
                    sandworms_conflict=owner.sandworms_conflict
                    - outcome.sandworms_deployed,
                ),
            ),
        )
        counted = add_units_to_reveal(
            rolled_back, player, sandworms=outcome.sandworms_deployed
        )
        next_state = counted.state
        events.extend(counted.events)
    elif outcome.sandworms_deployed:
        # A summoned sandworm is immediately deployed [Main p. 20], so it
        # joins the owner's per-turn deployment count.
        owner = next_state.players[player]
        next_state = replace(
            next_state,
            players=replace_player(
                next_state.players,
                replace(
                    owner,
                    units_deployed_turn=owner.units_deployed_turn
                    + outcome.sandworms_deployed,
                ),
            ),
        )
    return RuleResult(state=next_state, events=tuple(events))


def _gain_reveal_persuasion_now(
    before: GameState, after: GameState, player: int
) -> GameState:
    """Pay "Persuasion during your Reveal turn(s)" into an open Reveal.

    Tleilaxu Puppet: "Gain [1 Persuasion] during your Reveal turn this
    round" [Tleilaxu Puppet card]. A Plot may be played at any time during
    the owner's Agent or Reveal turn [Main p. 7] [Main p. 8]
    (docs/rules/player-turns.md), so one played in the owner's own Reveal
    turn gains the Persuasion in that Reveal; ``begin_reveal_turn`` only
    adds the round bonus when a later Reveal starts. It is generated
    Persuasion, so it counts toward Command (6+) [Bloodlines p. 5].

    Navigation Card 3 from slot 4: "For the rest of the game, during each
    of your Reveal turns, [1 Persuasion]" [Navigation Card 3 card]. Played
    in the owner's own Reveal turn (Influence 2 reached by a Reveal effect
    or a Plot there), that Reveal is one of them and pays the Persuasion
    too (OQ-110, project reading); the lasting bonus stays on the seat for
    every later Reveal, where ``begin_reveal_turn`` adds it.
    """

    owner = after.players[player]
    round_gained = max(
        0,
        owner.reveal_persuasion_round_bonus
        - before.players[player].reveal_persuasion_round_bonus,
    )
    lasting_gained = max(
        0,
        owner.reveal_persuasion_bonus - before.players[player].reveal_persuasion_bonus,
    )
    gained = round_gained + lasting_gained
    if gained <= 0 or not reveal_is_open_for(after, player):
        return after
    return replace(
        after,
        players=replace_player(
            after.players,
            replace(
                owner,
                reveal_persuasion_round_bonus=(
                    owner.reveal_persuasion_round_bonus - round_gained
                ),
            ),
        ),
        decision_stack=add_reveal_persuasion(after.decision_stack, gained),
    )


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
