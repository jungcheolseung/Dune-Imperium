"""A revealed card's automatic Reveal lines, read off its ability record.

Stage B3e-2 (docs/stage-b-plan.md, decision E-2, user decision 2026-10-20
"e-2는 추천대로"): the Reveal turn reads each printed line of a card's
Reveal box from the card's ability record
(``content.uprising.reveal_abilities.REVEAL_GAIN_ABILITIES``, one
``EffectSection`` per printed line, each judged on its own) instead of the
totals compiled from it (``PersonalCardRevealEffect``, removed in the Reveal
totals cleanup). A line's conditions are judged where
every effect's are (``conditions.owner_condition_holds``), but a Faction
Bond, which reads the other cards in play, and "Command (6+)", which reads
the Reveal's Persuasion [Bloodlines pp. 5, 12]. What a line gives is its
rewards: Persuasion and swords at once (counted per revealed or in-play
Faction card, per completed Contract, per other sword card), the other
gains as the owner's own steps (OQ-045).

The card text (``display.tokens.reveal_effect_text``) and the action catalog
(``adapters.action_codec``) read the same lines (the Reveal totals cleanup,
2026-10-21): there is no other copy of what a Reveal box gives.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AdvanceTleilaxu,
    AllConditions,
    CommandReached,
    Condition,
    DrawIntrigueCards,
    EffectSection,
    FactionBond,
    GainInfluence,
    GainResources,
    GenerateSpecimens,
    GrantCombatDeployment,
    RecruitTroops,
    Research,
    RevealCount,
    RevealCountKind,
    RevealPersuasion,
    RevealSwords,
    TrashThisCard,
)
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.reveal_abilities import REVEAL_GAIN_ABILITIES
from dune_imperium.core.player import PlayerState
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.conditions import owner_condition_holds

# "Command (6+)": the Reveal turn generates six or more Persuasion
# [Bloodlines pp. 5, 12].
COMMAND_PERSUASION: Final = 6


@dataclass(frozen=True, slots=True)
class RevealLine:
    """One printed line of a card's Reveal box (module docstring)."""

    section: EffectSection

    def __post_init__(self) -> None:
        for reward in self.section.rewards:
            if (
                isinstance(reward, RevealSwords)
                and reward.per is not None
                and (
                    reward.per.kind is RevealCountKind.FACTION_CARD_IN_PLAY
                    or reward.per.kind is RevealCountKind.COMPLETED_CONTRACT
                )
            ):
                raise TypeError(f"no Reveal line counts swords per {reward.per}")
            if (
                isinstance(reward, RevealPersuasion)
                and reward.per is not None
                and (reward.per.kind is RevealCountKind.OTHER_SWORD_CARD)
            ):
                raise TypeError("no Reveal line counts Persuasion per sword card")

    @property
    def conditions(self) -> tuple[Condition, ...]:
        condition = self.section.condition
        if condition is None:
            return ()
        if isinstance(condition, AllConditions):
            return condition.conditions
        return (condition,)

    def _count(self, kind: type[RecruitTroops | DrawIntrigueCards]) -> int:
        return sum(
            reward.count for reward in self.section.rewards if isinstance(reward, kind)
        )

    @property
    def recruit_troops(self) -> int:
        return self._count(RecruitTroops)

    @property
    def draw_intrigue(self) -> int:
        return self._count(DrawIntrigueCards)

    @property
    def specimens(self) -> int:
        return sum(
            reward.count
            for reward in self.section.rewards
            if isinstance(reward, GenerateSpecimens)
        )

    @property
    def tleilaxu(self) -> int:
        return sum(
            reward.count
            for reward in self.section.rewards
            if isinstance(reward, AdvanceTleilaxu)
        )

    @property
    def research(self) -> int:
        # One Research icon each (Tleilaxu Master prints two).
        return sum(isinstance(reward, Research) for reward in self.section.rewards)

    def _resources(self) -> tuple[GainResources, ...]:
        return tuple(
            reward
            for reward in self.section.rewards
            if isinstance(reward, GainResources)
        )

    @property
    def solari(self) -> int:
        return sum(reward.solari for reward in self._resources())

    @property
    def spice(self) -> int:
        return sum(reward.spice for reward in self._resources())

    @property
    def water(self) -> int:
        return sum(reward.water for reward in self._resources())

    @property
    def influence(self) -> tuple[Faction, int] | None:
        """A fixed-Faction Influence gain (Shishakli, Throne Room Politics)."""

        for reward in self.section.rewards:
            if isinstance(reward, GainInfluence) and reward.factions is not None:
                (faction,) = reward.factions
                return faction, reward.times
        return None

    @property
    def trashes_self(self) -> bool:
        # Bombast: "Command: 3 Solari and trash this card".
        return any(isinstance(reward, TrashThisCard) for reward in self.section.rewards)

    @property
    def grants_combat_icon(self) -> bool:
        # Holy War: "Fremen Bond: Combat icon" [Bloodlines p. 5].
        return any(
            isinstance(reward, GrantCombatDeployment) for reward in self.section.rewards
        )

    @property
    def printed_persuasion(self) -> int:
        """The Persuasion the line prints, flat or for each card of a Faction
        (``faction_count``); a Persuasion per completed Contract is apart
        (``persuasion_per_completed_contract``)."""

        return sum(
            reward.amount
            for reward in self.section.rewards
            if isinstance(reward, RevealPersuasion)
            and (reward.per is None or reward.per.faction is not None)
        )

    @property
    def printed_strength(self) -> int:
        """The swords the line prints, flat or for each revealed card of a
        Faction; swords per other sword card are apart
        (``strength_per_other_sword_card``)."""

        return sum(
            reward.amount
            for reward in self.section.rewards
            if isinstance(reward, RevealSwords)
            and (reward.per is None or reward.per.faction is not None)
        )

    @property
    def faction_count(self) -> RevealCount | None:
        """What the line's Persuasion or swords are counted for, when that is
        each card of a Faction (revealed, or in play); None otherwise."""

        for reward in self.section.rewards:
            if (
                isinstance(reward, RevealPersuasion | RevealSwords)
                and reward.per is not None
                and reward.per.faction is not None
            ):
                return reward.per
        return None

    @property
    def persuasion_per_completed_contract(self) -> int:
        """Interstellar Trade's "[1 Persuasion] for each contract you have
        completed" (OQ-028 (c))."""

        return sum(
            reward.amount
            for reward in self.section.rewards
            if isinstance(reward, RevealPersuasion)
            and reward.per is not None
            and reward.per.kind is RevealCountKind.COMPLETED_CONTRACT
        )

    @property
    def strength_per_other_sword_card(self) -> int:
        """Leadership's swords for each other sword card revealed."""

        return sum(
            reward.amount
            for reward in self.section.rewards
            if isinstance(reward, RevealSwords)
            and reward.per is not None
            and reward.per.kind is RevealCountKind.OTHER_SWORD_CARD
        )

    def persuasion_over(
        self,
        revealed_cards: Sequence[PersonalCardDefinition],
        completed_contracts: int,
        in_play_cards: Sequence[PersonalCardDefinition],
    ) -> int:
        """The line's Persuasion: flat, or per revealed Faction card (this
        Reveal's cards), per in-play Faction card (also the cards played on
        this round's Agent turns [Main p. 20 "In Play"] [FAQ p. 2 Liet
        Kynes]) or per completed Contract."""

        total = 0
        for reward in self.section.rewards:
            if not isinstance(reward, RevealPersuasion):
                continue
            per = reward.per
            if per is None:
                total += reward.amount
            elif per.kind is RevealCountKind.COMPLETED_CONTRACT:
                total += reward.amount * completed_contracts
            elif per.kind is RevealCountKind.REVEALED_FACTION_CARD:
                total += reward.amount * _with_faction(revealed_cards, per.faction)
            else:
                total += reward.amount * _with_faction(in_play_cards, per.faction)
        return total

    def strength_over(self, revealed_cards: Sequence[PersonalCardDefinition]) -> int:
        """The line's own swords: flat or per revealed Faction card; a sword
        per other sword card is counted apart (``strength_per_other_sword_card``)."""

        total = 0
        for reward in self.section.rewards:
            if not isinstance(reward, RevealSwords):
                continue
            per = reward.per
            if per is None:
                total += reward.amount
            elif per.kind is RevealCountKind.REVEALED_FACTION_CARD:
                total += reward.amount * _with_faction(revealed_cards, per.faction)
        return total

    def arrival_gains(self, arriving: PersonalCardDefinition) -> tuple[int, int]:
        """The Persuasion and swords this line's Faction count adds when
        ``arriving`` joins the revealed and in-play cards late (a card
        counted per Faction card grows by it)."""

        persuasion = swords = 0
        for reward in self.section.rewards:
            if not isinstance(reward, RevealPersuasion | RevealSwords):
                continue
            per = reward.per
            if per is None or per.faction not in arriving.factions:
                continue
            if isinstance(reward, RevealPersuasion):
                persuasion += reward.amount
            elif per.kind is RevealCountKind.REVEALED_FACTION_CARD:
                swords += reward.amount
        return persuasion, swords


def _with_faction(
    cards: Sequence[PersonalCardDefinition], faction: Faction | None
) -> int:
    return sum(faction in card.factions for card in cards)


@cache
def _lines_of(card_id: str) -> tuple[RevealLine, ...]:
    ability = REVEAL_GAIN_ABILITIES.get(card_id)
    if ability is None:
        return ()
    return tuple(RevealLine(section) for section in ability.sections)


def reveal_lines(card: PersonalCardDefinition) -> tuple[RevealLine, ...]:
    """The card's Reveal lines, in the record's order (its ``card#index``
    keys on the Reveal frame); a card without a record gains nothing."""

    return _lines_of(card.card.card_id)


def line_conditions_hold(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    line: RevealLine,
    *,
    persuasion: int | None = None,
) -> bool:
    """Whether every condition of the revealed card ``card_id``'s line holds.

    A Faction Bond counts the other cards in play (``has_faction_bond``);
    "Command (6+)" reads ``persuasion``, the Reveal turn's total so far
    (``None``, not known yet, never meets it); every other condition reads
    the seat alone (``conditions.owner_condition_holds``).
    """

    for condition in line.conditions:
        match condition:
            case FactionBond(faction=faction):
                held = has_faction_bond(cards_in_play, card_id, faction)
            case CommandReached():
                held = persuasion is not None and persuasion >= COMMAND_PERSUASION
            case _:
                judged = owner_condition_holds(owner, condition)
                if judged is None:
                    raise TypeError(f"{condition!r} is no Reveal line condition")
                held = judged
        if not held:
            return False
    return True
