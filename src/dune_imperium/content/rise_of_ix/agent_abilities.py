"""Rise of Ix's personal cards' Agent boxes, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 3): each value is
the box's key -- the stable string its display text and record are found
by (``content.registry.card_abilities.agent_box_key``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.core.agent_boxes import (
    agent_box,
    box_line,
    discard_box,
    icon_box,
    pay_box,
    trash_box,
)
from dune_imperium.content.core.effects import (
    AcquireTech,
    AtSpaceWithEnemyAgent,
    CommissionDreadnought,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    Freighter,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    InfluenceAtLeast,
    PayResources,
    PutIntrigueOnDeckBottom,
    RecruitTroops,
    TakeAnotherTurn,
    TrashCard,
    TrashPersonalCard,
)
from dune_imperium.content.core.icons import (
    Faction,
)

_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_BG_TWO = InfluenceAtLeast(_BG, 2)
_GUILD_TWO = InfluenceAtLeast(Faction.SPACING_GUILD, 2)


IX_AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "appropriate": "may_acquire_tech_with_spice_or_solari_if_emperor_influence_two",
        "bounty_hunter": "gain_two_solari_if_enemy_agent_on_space",
        "court_intrigue": "may_put_intrigue_on_bottom_to_draw_intrigue",
        "desert_ambush": "may_force_enemy_unit_retreat_for_each_troop_deployed",
        "embedded_agent": "may_move_freighter_twice_if_bene_gesserit_bond",
        "esmar_tuek_card": "may_pay_one_spice_for_spacing_guild_influence_and_draw_one",
        "full_scale_assault": "recruit_two_troops",
        "guild_chief_administrator": "may_discard_to_trash_a_card",
        "imperial_bashar": "recruit_one_or_may_trash_a_card",
        "in_the_shadows": (
            "may_discard_for_chosen_influence_if_bene_gesserit_influence_two"
        ),
        "ix_guild_compact": "may_discard_two_for_dreadnought",
        "ixian_engineer": "may_acquire_tech",
        "jamis": "trash_personal_card",
        "landing_rights": "may_move_freighter",
        "local_fence": (
            "may_pay_two_spice_for_five_solari_or_five_solari_for_four_spice"
        ),
        "satellite_ban": "may_discard_for_one_spice_and_one_water",
        "sayyadina": "may_pay_three_water_for_vp",
        "shai_hulud": "trash_personal_card_to_recruit_two",
        "spice_trader": "may_discard_for_two_spice_if_fremen_influence_two",
        "treachery": "gain_two_visited_faction_influence_and_trash_self",
        "truthsayer": "may_discard_to_draw_one",
        "web_of_power": "gain_by_emperor_spacing_guild_and_fremen_influence_two",
        "weirding_way": "may_take_another_turn",
        "boundless_ambition": "leader_signet",
    }
)


# The Agent-box records only this set's cards print, by box key.
IX_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Sayyadina (Rise of Ix): "[3 water] -> [1 Victory Point]".
        # An optional arrow, once per turn [DI p. 9] [FAQ p. 3].
        "may_pay_three_water_for_vp": pay_box(
            PayResources(water=3), GainVictoryPoints(1)
        ),
        # Local Fence (Rise of Ix): "[2 spice] -> [5 Solari] -OR- [5
        # Solari] -> [4 spice]" [Steam app screen pieces and text]: two
        # arrows, each optional (player-turns.md [Main p. 9] [FAQ p. 3]),
        # and "-OR-" takes one (imperium-base.md 10.1), so the owner pays
        # one or neither; each line is its own row (``payment_box``).
        "may_pay_two_spice_for_five_solari_or_five_solari_for_four_spice": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainResources(solari=5),),
                    costs=(PayResources(spice=2),),
                ),
                EffectSection(
                    rewards=(GainResources(spice=4),),
                    costs=(PayResources(solari=5),),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
            structure=AbilityStructure.ONE_OF,
        ),
        # Bounty Hunter (Rise of Ix): "If used to send an Agent to a board
        # space with an enemy Agent: [2 Solari]" [Steam app text]: the
        # space the Agent goes to is fixed by the placement, so the box is
        # judged when the card is played, as a Maker space's is.
        "gain_two_solari_if_enemy_agent_on_space": agent_box(
            GainResources(solari=2), requirement=AtSpaceWithEnemyAgent()
        ),
        # Desert Ambush (Rise of Ix): "For each troop you deploy this turn,
        # you may force an enemy unit to retreat." [Steam app text] -- an
        # optional target box ("may"), open all turn: each troop the owner
        # deploys this turn (OQ-029's count) buys one retreat of an enemy
        # troop or dreadnought, the owner picking it (rise-of-ix.md 6, 9.3).
        "may_force_enemy_unit_retreat_for_each_troop_deployed": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(ForceEnemyRetreat(units=True, per_troop_deployed=True)),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Guild Chief Administrator (Rise of Ix): "[Discard] -> [Trash a
        # card]" [Steam app screen pieces]. The discard is the arrow's
        # optional cost [Rise of Ix p. 7] [FAQ p. 2], an Unload card's box
        # paid in full before the trash (rise-of-ix.md 7); the trash is a
        # black trash icon, optional once the cost is paid ("검은색 trash
        # 아이콘으로 trash하는 효과는 선택이다" [FAQ p. 3], uprising-
        # systems.md), as Control the Spice's is. The card just discarded
        # is in the discard pile, so a card to trash is always there.
        "may_discard_to_trash_a_card": discard_box(box_line(TrashPersonalCard())),
        # Satellite Ban (Rise of Ix): "[Discard] -> [1 spice] [1 water]" [Steam
        # app screen pieces and log text]: one optional arrow, both gains
        # paid at once.
        "may_discard_for_one_spice_and_one_water": discard_box(
            box_line(GainResources(spice=1, water=1))
        ),
        # Spice Trader (Rise of Ix): "[Fremen] 2 Influence : [Discard] -> [2
        # spice]" [Steam app screen pieces and text]: the Faction icon and the
        # words "2 Influence:" are an Influence threshold over the whole arrow
        # (the one High Priority Travel prints), judged when the cost is paid
        # (OQ-028), not an Alliance.
        "may_discard_for_two_spice_if_fremen_influence_two": discard_box(
            box_line(
                GainResources(spice=2),
                condition=InfluenceAtLeast(Faction.FREMEN, 2),
            )
        ),
        # In The Shadows (Rise of Ix): "[Bene Gesserit] 2 Influence:
        # [Discard] -> Choose one: [Emperor] [Spacing Guild] [Fremen]
        # Influence" [Steam app screen pieces and button text]: Spice
        # Trader's threshold over the whole arrow, judged when the cost is
        # paid (OQ-028), and Firm Grip's choice of three named Factions,
        # armed once the card is discarded and answered by its Faction rows
        # (never a track at the top, OQ-060). With all three at the top the
        # arrow buys nothing and is not offered (OQ-071), also when the card
        # to discard has an Unload box (docs/rules/rise-of-ix.md 15).
        "may_discard_for_chosen_influence_if_bene_gesserit_influence_two": discard_box(
            box_line(
                GainInfluence(
                    factions=(
                        Faction.EMPEROR,
                        Faction.SPACING_GUILD,
                        Faction.FREMEN,
                    )
                ),
                condition=_BG_TWO,
            ),
            armed=("influence",),
        ),
        # Ix-Guild Compact (Rise of Ix): "[Discard] [Discard] ->
        # [Dreadnought]" [Steam app screen pieces and button text] -- an
        # optional arrow of two Discard icons, both paid together; what
        # they buy is commissioned once both are paid. With no
        # dreadnought left in the supply the arrow buys nothing and is not
        # offered (OQ-071), also when a card to discard has an Unload box
        # (docs/rules/rise-of-ix.md 15).
        "may_discard_two_for_dreadnought": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(CommissionDreadnought(),),
                    costs=(DiscardFromHand(2),),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Court Intrigue (Rise of Ix): "Put an Intrigue card on the bottom
        # of the deck -> [Intrigue card]" [Steam app text and screen
        # pieces]: an optional arrow [FAQ p. 3] whose cost is one Intrigue
        # card of the hand put under the Intrigue deck, unseen by the
        # others ([Rise of Ix p. 10], rise-of-ix.md 9.1, 13); the draw, a
        # hidden draw, is then armed as its own step (OQ-106), as
        # Branching Path's. The card put there can be the one drawn when
        # the deck holds nothing else.
        "may_put_intrigue_on_bottom_to_draw_intrigue": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(DrawIntrigueCards(1),),
                    costs=(PutIntrigueOnDeckBottom(),),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("intrigue",),
        ),
        # Shai-Hulud (Rise of Ix): "[Trash a card] -> [2 troops]" [Steam app
        # screen pieces and log text]: an arrow whose cost is a trashed card,
        # optional like every arrow cost [FAQ p. 3]; the troops come at once
        # (``agent_box_abilities.apply_trash``).
        "trash_personal_card_to_recruit_two": trash_box(
            EffectSection(rewards=(RecruitTroops(2),), costs=(TrashCard(),))
        ),
        # Landing Rights (Rise of Ix): the Freighter icon [Steam app screen
        # pieces]: "you may move your Freighter in one of two ways" [Rise
        # of Ix p. 5] (docs/rules/rise-of-ix.md 5). An optional icon
        # (``agent_effects.OPTIONAL_AGENT_ICONS``) answered by its own rows
        # (``advance_agent_card_freighter``, ``recall_agent_card_freighter``).
        "may_move_freighter": icon_box(("freighter", box_line(Freighter()))),
        # Embedded Agent (Rise of Ix): "If you have another Bene Gesserit
        # card in play:" [Steam app text] with two Freighter icons [screen
        # pieces] -- a Bene Gesserit Bond ("one or more other ... cards in
        # play" [Main p. 20]), as In High Places': the Bond opens the box
        # and is judged again on each icon when it resolves (OQ-028); each
        # icon is a "may" of its own [Rise of Ix p. 5] (OQ-027), answered by
        # the Freighter rows (``agent_effects.OPTIONAL_AGENT_ICONS``).
        "may_move_freighter_twice_if_bene_gesserit_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(Freighter(), condition=_BG_BOND),
                box_line(Freighter(), condition=_BG_BOND),
            ),
            structure=AbilityStructure.SEPARATE,
            requirement=_BG_BOND,
            icons=("freighter", "freighter_second"),
        ),
        # Weirding Way (Rise of Ix): "You may take another turn immediately
        # after this one." [Steam app text] -- an optional icon
        # (``agent_effects.OPTIONAL_AGENT_ICONS``) answered by its row
        # (``take_agent_card_extra_turn``); unused, the turn's end lapses it
        # (OQ-095 (2)).
        "may_take_another_turn": icon_box(("extra_turn", box_line(TakeAnotherTurn()))),
        # Ixian Engineer (Rise of Ix): the Acquire Tech icon [Steam app
        # screen pieces]. The card prints no Tech Discount sprite (the
        # Reveal of Ix-Guild Compact prints two), so the icon is the plain
        # one of the Dreadnought space: discount 0. "아이콘마다 ... 하나를
        # 얻을 수 있다("may")" [Rise of Ix p. 4], so the owner may leave it;
        # it opens the Acquire Tech window with its own refusal
        # (``agent_effects.apply_agent_card_tech``).
        "may_acquire_tech": icon_box(("tech", box_line(AcquireTech(discount=0)))),
        # Appropriate (Rise of Ix): "[Emperor] 2 Influence: [Acquire Tech]
        # You may use Solari instead of spice for this purchase." [Steam
        # app text] -- Ixian Engineer's plain Acquire Tech icon (no Tech
        # Discount sprite) behind an Emperor threshold judged when the
        # icon resolves (OQ-028, as Web of Power's), its price payable in
        # Solari instead ("Solari와 spice를 섞어 낼 수 없다. Negotiator
        # 하나가 1 Solari를 깎는다", rise-of-ix.md 4, [Rise of Ix p. 10]).
        "may_acquire_tech_with_spice_or_solari_if_emperor_influence_two": icon_box(
            (
                "tech",
                box_line(
                    AcquireTech(discount=0, solari_allowed=True),
                    condition=InfluenceAtLeast(Faction.EMPEROR, 2),
                ),
            )
        ),
        # Esmar Tuek (Rise of Ix): "[1 spice] -> [Spacing Guild Influence]
        # [draw 1 card]" [Steam app screen pieces and button text] -- a
        # paid arrow whose two rewards wait as icons once the spice is
        # paid, each its own step in the owner's order, as Spice
        # Smugglers' and Duncan Idaho's (OQ-148 (가), OQ-027 (b), OQ-106).
        "may_pay_one_spice_for_spacing_guild_influence_and_draw_one": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainInfluence(factions=(Faction.SPACING_GUILD,)),),
                    costs=(PayResources(spice=1),),
                ),
                box_line(DrawPersonalCards(1)),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("influence", "cards"),
        ),
        # Web of Power (Rise of Ix): three printed lines, "[Emperor] 2
        # Influence: [2 Solari]", "[Spacing Guild] 2 Influence: [draw 1]"
        # and "[Fremen] 2 Influence: [1 water]" [Steam app screen pieces
        # and text] -- the Influence thresholds Wheels Within Wheels prints,
        # each icon its own step with the Influence judged when it resolves
        # (OQ-027, OQ-028).
        "gain_by_emperor_spacing_guild_and_fremen_influence_two": icon_box(
            (
                "solari",
                box_line(
                    GainResources(solari=2),
                    condition=InfluenceAtLeast(Faction.EMPEROR, 2),
                ),
            ),
            ("cards", box_line(DrawPersonalCards(1), condition=_GUILD_TWO)),
            (
                "water",
                box_line(
                    GainResources(water=1),
                    condition=InfluenceAtLeast(Faction.FREMEN, 2),
                ),
            ),
        ),
        # Imperial Bashar (Rise of Ix): "[Troop] -OR- [Trash a card]" [Steam app
        # screen pieces and text: "Choose:" with a troop and a trash button].
        # A printed -OR- beside a black trash icon: "Trash ... 비용이거나
        # 카드가 자기를 trash하라고 할 때만 의무" (docs/rules/imperium-base.md
        # 11, [DI p. 16]), so choosing the trash and declining it equals doing
        # nothing, and the box reaches the same outcomes as an optional one: the
        # recruit (the plain line) or a trash (the choice line), neither
        # forced, lapsing unpaid at the turn's end (OQ-095 (2)). Plain
        # beside choice (``agent_box_abilities.either_box``).
        "recruit_one_or_may_trash_a_card": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(box_line(RecruitTroops(1)), box_line(TrashPersonalCard())),
            mark=AbilityMark.OPTIONAL,
            structure=AbilityStructure.ONE_OF,
        ),
    }
)
