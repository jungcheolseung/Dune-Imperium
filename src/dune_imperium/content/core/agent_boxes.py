"""Agent-box record builders and the records several sets' cards share.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 3c): each set keeps its
cards' Agent-box records (``<set>.agent_abilities``), keyed by the box key
its cards' card-id table names; a record that cards of more than one set
print lives here once. ``content.registry.card_abilities`` merges them. How
a record reads (requirement, condition, icons, hook) is told in
``content.uprising.agent_abilities``.
"""

from collections.abc import Mapping
from copy import replace
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.effects import (
    AtFactionSpace,
    Condition,
    Cost,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    RecruitTroops,
    Research,
    Reward,
    TrashCard,
    TrashPersonalCard,
    TrashThisCard,
)

# The Signet Ring icon's box (Signet Ring, Boundless Ambition): played on an
# Agent turn, it uses the owner's Leader's Signet Ring ability [Main p. 20].
# It has no record of its own -- the Leader's record is its effect -- so the
# engine asks for the icon (``registry.card_abilities.box_uses_signet``),
# never for a card.
SIGNET_BOX: Final = "leader_signet"


def box_line(*rewards: Reward, condition: Condition | None = None) -> EffectSection:
    return EffectSection(rewards=rewards, condition=condition)


def agent_box(
    *rewards: Reward,
    condition: Condition | None = None,
    requirement: Condition | None = None,
) -> Ability:
    """A box resolved as one action: its rewards on one line."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(box_line(*rewards, condition=condition),),
        requirement=requirement,
    )


def hook_box(
    name: str,
    *rewards: Reward,
    condition: Condition | None = None,
    requirement: Condition | None = None,
    mark: AbilityMark = AbilityMark.MANDATORY,
) -> Ability:
    """A box resolved by the named special flow (``agent_effects._BOX_HOOKS``)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(box_line(*rewards, condition=condition),) if rewards else (),
        mark=mark,
        requirement=requirement,
        hook=name,
    )


def pay_box(cost: Cost, *rewards: Reward) -> Ability:
    """An optional arrow with no target to pick: "You may pay X -> Y" (the
    arrow cost is optional [Main p. 20] [FAQ p. 3])."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(EffectSection(rewards=rewards, costs=(cost,)),),
        mark=AbilityMark.OPTIONAL,
    )


def discard_box(
    *lines: EffectSection,
    mark: AbilityMark = AbilityMark.OPTIONAL,
    armed: tuple[str, ...] = (),
) -> Ability:
    """A discard arrow: "[You may] discard a card -> ...". The first line
    carries the cost; a later line's condition reads the discarded card;
    ``armed`` keys the lines armed as icons once the cost is paid."""

    first, *rest = lines
    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(replace(first, costs=(DiscardFromHand(),)), *rest),
        mark=mark,
        armed_icons=armed,
    )


def trash_box(*lines: EffectSection, armed: tuple[str, ...] = ()) -> Ability:
    """An optional trash box: black trash icons [FAQ p. 3], or an arrow whose
    first line carries a ``TrashCard`` cost."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=lines,
        mark=AbilityMark.OPTIONAL,
        armed_icons=armed,
    )


def icon_box(*lines: tuple[str, EffectSection]) -> Ability:
    """A box whose printed icons resolve one action each (OQ-027)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=tuple(section for _, section in lines),
        structure=AbilityStructure.SEPARATE,
        icons=tuple(key for key, _ in lines),
    )


SHARED_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # --- One action: gains -------------------------------------------
        "gain_two_solari": agent_box(GainResources(solari=2)),
        "gain_water": agent_box(GainResources(water=1)),
        "recruit_two_troops": agent_box(RecruitTroops(2)),
        # --- One action: card draws ----------------------------------------
        "draw_personal_card": agent_box(DrawPersonalCards(1)),
        "draw_two_cards": agent_box(DrawPersonalCards(2)),
        # --- One action: Intrigue draws ------------------------------------
        "draw_intrigue_card": agent_box(DrawIntrigueCards(1)),
        "research": agent_box(Research()),
        # --- A choice of target (composed effects, A3c) ----------------------
        # Interstellar Trade, For Humanity: "Gain 1 Influence with a chosen
        # Faction".
        "gain_chosen_influence": agent_box(GainInfluence()),
        # I Believe.
        "may_discard_to_draw_one": discard_box(box_line(DrawPersonalCards(1))),
        # --- Trash boxes (composed effects, A3e) -----------------------------
        # Calculus of Power, Desert Survival, Eliminate Allies: "You may trash
        # a card" -- the black trash icon is the whole box.
        "trash_personal_card": trash_box(box_line(TrashPersonalCard())),
        # Shishakli, Replacement Eyes: "You may trash a card -> Draw 1 card".
        "trash_personal_card_to_draw_one": trash_box(
            EffectSection(rewards=(DrawPersonalCards(1),), costs=(TrashCard(),))
        ),
        # --- Special flows of the boxes no stage listed (composed A3g) -------
        # Their rows, events and frames are their own. A record lists its
        # lines when the DSL can say the whole box; a box it cannot say
        # whole has no line (a part alone would misread as the box), its
        # printed text in the comment.
        # Subversive Advisor: "Gain 2 Influence with the visited Faction,
        # Trash this card" -- the 2 replace the space's 1 (never 2 + 1).
        "gain_two_visited_faction_influence_and_trash_self": agent_box(
            GainInfluence(visited_space=True, times=2, replaces_space=True),
            TrashThisCard(),
            requirement=AtFactionSpace(),
        ),
    }
)
