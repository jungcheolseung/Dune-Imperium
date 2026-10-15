"""Ability records of the composed-effects engine (docs/composed-effects-plan.md 4.1).

A card -- personal card, Intrigue, Leader, Tech, Contract, Conflict, board
space or Scouts card -- is its printed values plus a list of abilities. An
ability widens ``effect_dsl.IntrigueOption``: when it is used (``timing``),
whether it must be used (``mark``), how its printed lines combine
(``structure``), what gates it (``requirement``), and its lines, each an
``EffectSection`` of a condition, costs and rewards in printed order.

A line's "distinct k", "for each" and "up to n" stay on its rewards
(``GainInfluence.distinct``/``times``, ``GainSolariPerUnitType``,
``DeployFromGarrison.up_to``), as the DSL already writes them. The
requirement tree has the DSL's conjunction (``AllConditions``); "or" and
"not" are added when the first card that prints one moves into a record
(Interstellar Conspiracy's "If grafted with an Emperor or Spacing Guild
card", card-specific code until then), together with its wording in both
languages: the display renders every DSL condition, and no card written in
the DSL yet prints either.

An effect that data would only make harder to read is a hook: ``hook`` names
the executor function that resolves it through the common decisions and
state helpers, and its sections may still list the fragments it gives (for
the network's card features, plan 4.4). The plan counts the hooks stage by
stage.

Intrigue options convert both ways without loss (``intrigue_ability``,
``intrigue_option``), so stage A1 can resolve the 90 identities through the
executor while their transcription stays as it is.
"""

from dataclasses import dataclass
from enum import StrEnum

from dune_imperium.content.uprising.effect_dsl import (
    Condition,
    EffectSection,
    IntrigueOption,
    IntrigueTiming,
    Trigger,
)


class AbilityTiming(StrEnum):
    """When an ability is used."""

    AGENT_BOX = "agent_box"
    REVEAL = "reveal"
    ACQUIRE = "acquire"
    TRASH = "trash"
    DISCARD = "discard"
    TURN_START = "turn_start"
    PLOT = "plot"
    COMBAT = "combat"
    ENDGAME = "endgame"
    # An event fires it (a Leader's standing ability, a face-up trigger).
    TRIGGERED = "triggered"


class AbilityMark(StrEnum):
    """Whether an ability must be used."""

    # Used while it can be: an open one holds its turn's end (OQ-057).
    MANDATORY = "mandatory"
    # "You may", an arrow cost or a black trash icon [FAQ p. 3]: offered
    # without a refusal inside its owner's turn, lapsing at the turn's end
    # when unused (OQ-095 (2), (7)).
    OPTIONAL = "optional"
    # Nothing to choose: resolved without a decision.
    AUTOMATIC = "automatic"


class AbilityStructure(StrEnum):
    """How an ability's printed lines combine."""

    # Every applicable line, in printed order.
    SEQUENCE = "sequence"
    # Exactly one line (the halves of a "—OR—" box).
    ONE_OF = "one_of"
    # Lines printed without "—OR—", each used on its own (OQ-058).
    SEPARATE = "separate"


@dataclass(frozen=True, slots=True)
class Ability:
    """One ability of a card (see the module doc)."""

    timing: AbilityTiming
    sections: tuple[EffectSection, ...]
    mark: AbilityMark = AbilityMark.MANDATORY
    structure: AbilityStructure = AbilityStructure.SEQUENCE
    requirement: Condition | None = None
    # A face-up card's trigger: playing it does nothing until it fires.
    trigger: Trigger | None = None
    # A Plot used "at the start of your turn" (Withdrawn, OQ-095 (6)).
    at_turn_start: bool = False
    hook: str | None = None
    # An Agent box whose printed icons resolve one action each, in the
    # owner's order (OQ-027): one row key per line, ``sections[i]`` resolved
    # by ``resolve_agent_card_effect(effect=icons[i])``.
    icons: tuple[str, ...] = ()
    # An arrow whose rewards resolve one action each once its cost is paid
    # (OQ-027): one row key per line, armed by the cost's answer
    # (``effects.arm_agent_icons``) instead of queued at placement; a line
    # whose condition fails then is not armed.
    armed_icons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.timing, AbilityTiming):
            raise TypeError("ability timing must use AbilityTiming")
        if not self.sections and self.hook is None:
            raise ValueError("an ability needs a printed line or a hook")
        if self.hook == "":
            raise ValueError("a hook must be named")
        if self.structure is not AbilityStructure.SEQUENCE and len(self.sections) < 2:
            raise ValueError(f"a {self.structure} ability needs two or more lines")
        if self.mark is AbilityMark.AUTOMATIC and any(
            section.costs for section in self.sections
        ):
            raise ValueError("an automatic ability has nothing to pay")
        if self.trigger is not None and any(
            section.costs or section.condition is not None for section in self.sections
        ):
            raise ValueError("triggered lines must be free and unconditional")
        if self.at_turn_start and self.timing is not AbilityTiming.PLOT:
            raise ValueError("only a Plot is played at the start of a turn")
        if self.icons:
            if self.timing is not AbilityTiming.AGENT_BOX:
                raise ValueError("only an Agent box resolves icon by icon")
            if self.structure is not AbilityStructure.SEPARATE:
                raise ValueError("an icon-by-icon box uses each line on its own")
            if len(self.icons) != len(self.sections):
                raise ValueError("an icon-by-icon box keys every line")
            if len(set(self.icons)) != len(self.icons) or not all(self.icons):
                raise ValueError("icon keys must be named and distinct")
        if self.armed_icons:
            if self.timing is not AbilityTiming.AGENT_BOX or self.icons:
                raise ValueError("only an Agent box arrow arms its rewards as icons")
            if len(self.armed_icons) != len(self.sections):
                raise ValueError("an arrow arming its rewards keys every line")
            if len(set(self.armed_icons)) != len(self.armed_icons) or not all(
                self.armed_icons
            ):
                raise ValueError("icon keys must be named and distinct")
            if not self.sections[0].costs:
                raise ValueError("an arrow arms its rewards after its cost")


_FROM_INTRIGUE = {
    IntrigueTiming.PLOT: AbilityTiming.PLOT,
    IntrigueTiming.COMBAT: AbilityTiming.COMBAT,
    IntrigueTiming.ENDGAME: AbilityTiming.ENDGAME,
}
_TO_INTRIGUE = {timing: intrigue for intrigue, timing in _FROM_INTRIGUE.items()}


def intrigue_ability(option: IntrigueOption) -> Ability:
    """The ability of one way to play an Intrigue (or Navigation) card.

    Every applicable cost is mandatory once the card is played [FAQ p. 2],
    so the ability is mandatory; an optional icon on a line (the black
    trash icon) stays optional on its reward.
    """

    return Ability(
        timing=_FROM_INTRIGUE[option.timing],
        sections=option.sections,
        structure=(
            AbilityStructure.SEPARATE if option.separate else AbilityStructure.SEQUENCE
        ),
        trigger=option.trigger,
        at_turn_start=option.turn_start_only,
    )


def intrigue_option(ability: Ability) -> IntrigueOption:
    """The Intrigue option an ability describes; the inverse of ``intrigue_ability``.

    Raises ``ValueError`` for an ability no Intrigue option can hold.
    """

    timing = _TO_INTRIGUE.get(ability.timing)
    if (
        timing is None
        or ability.mark is not AbilityMark.MANDATORY
        or ability.structure is AbilityStructure.ONE_OF
        or ability.requirement is not None
        or ability.hook is not None
        or ability.icons
    ):
        raise ValueError(f"no Intrigue option holds {ability!r}")
    return IntrigueOption(
        timing=timing,
        sections=ability.sections,
        trigger=ability.trigger,
        turn_start_only=ability.at_turn_start,
        separate=ability.structure is AbilityStructure.SEPARATE,
    )
