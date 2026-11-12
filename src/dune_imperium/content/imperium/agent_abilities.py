"""The original Dune: Imperium's personal cards' Agent boxes, by card id.

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
    icon_box,
    pay_box,
    trash_box,
)
from dune_imperium.content.core.effects import (
    BlockChosenSpaceForOpponentsNextAgent,
    DoubleBaseHarvestSpice,
    DoubleBonusHarvestSpice,
    DrawIntrigueCards,
    DrawPersonalCards,
    EachOpponentDiscardsCard,
    EachOpponentDiscardsOrLosesDeployedTroop,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    GainInfluence,
    GainResources,
    InfluenceAtLeast,
    LoseInfluence,
    PayResources,
    RecruitTroops,
    TakeCardFromDiscard,
    TrashCard,
    TrashPersonalCard,
    TrashThisCard,
)
from dune_imperium.content.core.icons import (
    Faction,
)

_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_GUILD_TWO = InfluenceAtLeast(Faction.SPACING_GUILD, 2)


IMPERIUM_AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "arrakis_recruiter": "recruit_one_troop",
        "spice_smugglers": (
            "may_pay_two_spice_for_spacing_guild_influence_and_three_solari"
        ),
        "gun_thopter": "each_opponent_loses_garrison_troop",
        "bene_gesserit_initiate": "draw_personal_card",
        "carryall": "double_base_harvest_spice",
        "crysknife_card": "gain_one_solari",
        "dr_yueh": "draw_personal_card",
        "duncan_idaho_card": "may_pay_one_water_for_troop_and_draw_one",
        "fedaykin_death_commando": "trash_personal_card",
        "firm_grip": "may_pay_two_solari_for_chosen_influence",
        "fremen_camp": "may_pay_two_spice_for_three_troops",
        "gene_manipulation": "may_trash_and_gain_two_spice_if_bene_gesserit_bond",
        "guild_administrator": "trash_personal_card",
        "guild_ambassador": "gain_spacing_guild_influence_or_two_spice",
        "gurney_halleck_card": "recruit_two_and_draw_one",
        "imperial_spy": "may_trash_self_to_draw_intrigue",
        "kwisatz_haderach": "draw_personal_card",
        "lady_jessica_card": "draw_two_cards",
        "missionaria_protectiva": "gain_chosen_influence_if_bene_gesserit_bond",
        "opulence": "gain_three_solari",
        "other_memory": "draw_one_or_bene_gesserit_card_from_discard",
        "piter_de_vries_card": "draw_intrigue_card",
        "power_play": "gain_two_visited_faction_influence_and_trash_self",
        "reverend_mother_mohiam": "each_opponent_discards_two_if_bene_gesserit_bond",
        "sardaukar_legion": "recruit_two_troops",
        "shifting_allegiances": (
            "may_lose_influence_and_pay_two_spice_for_two_influence"
        ),
        "sietch_reverend_mother": "trash_personal_card",
        "smugglers_thopter": "draw_two_if_spacing_guild_influence_two",
        "space_travel": "draw_personal_card",
        "stilgar": "gain_water",
        "test_of_humanity": "each_opponent_discards_or_loses_deployed_troop",
        "the_voice": "block_chosen_space_for_opponents_next_agent",
        "thufir_hawat": "draw_personal_card",
        "worm_riders": "gain_two_spice",
        "duncan_loyal_blade": "recruit_one_troop",
        "jessica_of_arrakis": "draw_two_if_bene_gesserit_bond",
        "thumper": "double_bonus_harvest_spice",
        "foldspace_card": "draw_one_and_trash_self",
    }
)


# The Agent-box records only this set's cards print, by box key.
IMPERIUM_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        # Crysknife (original game): one Solari.
        "gain_one_solari": agent_box(GainResources(solari=1)),
        # Opulence (original game): three Solari.
        "gain_three_solari": agent_box(GainResources(solari=3)),
        # Arrakis Recruiter (original game): one troop; a Combat space
        # lets the owner deploy it [DI p. 10] [FAQ p. 4].
        "recruit_one_troop": agent_box(RecruitTroops(1)),
        # Foldspace (the original game's Reserve): "Draw 1 card" and "Trash
        # this card", separate effects (designer ruling, BGG Forum;
        # docs/rules/imperium-base.md 13.3); trashed by its own effect it
        # keeps the draw (OQ-022's designer follow-up).
        "draw_one_and_trash_self": icon_box(
            ("cards", box_line(DrawPersonalCards(1))),
            ("trash_self", box_line(TrashThisCard())),
        ),
        # Spice Smugglers (original game): "[2 spice] -> [Spacing Guild
        # Influence] [3 Solari]" -- a paid arrow whose two rewards wait as
        # icons once the spice is paid, each its own step in the owner's
        # order: user ruling 2026-10-29 (OQ-148 (가)), as Duncan Idaho's
        # (OQ-027, OQ-106). The Solari keep it worth paying at the top of
        # the Guild's track (OQ-060, OQ-071).
        "may_pay_two_spice_for_spacing_guild_influence_and_three_solari": (
            Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainInfluence(factions=(Faction.SPACING_GUILD,)),),
                        costs=(PayResources(spice=2),),
                    ),
                    box_line(GainResources(solari=3)),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("influence", "solari"),
            )
        ),
        # Fremen Camp (original game): "[2 spice] -> [3 troops]" -- a paid
        # arrow, the troops recruited at once [DI p. 9] [FAQ p. 3].
        "may_pay_two_spice_for_three_troops": pay_box(
            PayResources(spice=2), RecruitTroops(3)
        ),
        # Duncan Idaho (original game): "[1 water] -> [troop] [draw 1
        # card]" -- a paid arrow whose two rewards wait as icons once the
        # water is paid, each its own step (OQ-027 (b), OQ-106).
        "may_pay_one_water_for_troop_and_draw_one": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(RecruitTroops(1),), costs=(PayResources(water=1),)
                ),
                box_line(DrawPersonalCards(1)),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("troops", "cards"),
        ),
        # Gun Thopter (original game): "Each opponent loses one garrisoned
        # troop" -- Holy War's window, each loss limited to the garrison;
        # an opponent with none is unaffected [FAQ p. 2].
        "each_opponent_loses_garrison_troop": agent_box(
            EachOpponentLosesTroop(garrison_only=True)
        ),
        # Smuggler's Thopter (original game): "Spacing Guild Influence 2:
        # [draw] [draw]" -- two printed draw icons, each its own step with
        # the Influence judged when it resolves (OQ-027, OQ-028, OQ-106).
        "draw_two_if_spacing_guild_influence_two": icon_box(
            ("cards", box_line(DrawPersonalCards(1), condition=_GUILD_TWO)),
            ("cards_second", box_line(DrawPersonalCards(1), condition=_GUILD_TWO)),
        ),
        # Worm Riders (original game): two spice.
        "gain_two_spice": agent_box(GainResources(spice=2)),
        # Guild Ambassador (original game): "[Spacing Guild Influence] -OR-
        # [2 spice]" -- a printed -OR- the owner must settle (the P0
        # sweep's "choose one (must)"; Southern Faith's plain-beside-choice
        # shape). The 2 spice is the plain line, the Influence the choice
        # line; a track at 6 gains nothing (OQ-060), so only the spice is
        # then offered.
        "gain_spacing_guild_influence_or_two_spice": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(GainResources(spice=2)),
                box_line(GainInfluence(factions=(Faction.SPACING_GUILD,))),
            ),
            structure=AbilityStructure.ONE_OF,
        ),
        # The Voice (original game): "Choose any board space. Opponents can't
        # send their next Agents there this round." -- one mandatory target
        # choice among every board space on the table (imperium-base.md 15):
        # its rows are the spaces (``agent_box_abilities.target_rows``), and
        # the block lands on every opponent's seat state
        # (``PlayerState.voice_blocked_space_ids``, OQ-116).
        "block_chosen_space_for_opponents_next_agent": agent_box(
            BlockChosenSpaceForOpponentsNextAgent()
        ),
        # Other Memory (original game): "[draw 1] -OR- Draw a Bene Gesserit
        # card from your discard pile" -- a printed -OR- the owner must
        # settle (the P0 sweep's "choose one (must)"; Guild Ambassador's
        # plain-beside-choice shape). The draw is the plain line, its own
        # hidden step (OQ-106); the card taken from the discard pile is the
        # choice line, offered only with a Bene Gesserit card there.
        "draw_one_or_bene_gesserit_card_from_discard": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(DrawPersonalCards(1)),
                box_line(TakeCardFromDiscard(Faction.BENE_GESSERIT)),
            ),
            structure=AbilityStructure.ONE_OF,
        ),
        # Gurney Halleck (original game): "[2 troops] [draw 1 card]" -- two
        # printed icons, each its own step in the owner's order (OQ-027);
        # the hidden draw is apart from the public recruit (OQ-106).
        "recruit_two_and_draw_one": icon_box(
            ("troops", box_line(RecruitTroops(2))),
            ("cards", box_line(DrawPersonalCards(1))),
        ),
        # Imperial Spy (original game): "Trash this card -> [Intrigue card]"
        # -- the card trashes itself as the arrow's cost, then the Intrigue
        # draw is armed as an icon of its own (OQ-022, OQ-106; Pivotal
        # Gambit's shape). Trashed by anything else it draws nothing
        # [FAQ p. 2].
        "may_trash_self_to_draw_intrigue": trash_box(
            EffectSection(
                rewards=(DrawIntrigueCards(1),),
                costs=(TrashCard(this_card=True),),
            ),
            armed=("intrigue",),
        ),
        # Missionaria Protectiva (original game): "If you have another Bene
        # Gesserit card in play: [Influence of your choice]" -- the Bond
        # opens the box at the placement and is judged again when it
        # resolves (OQ-028); a track at 6 is not offered (OQ-060).
        "gain_chosen_influence_if_bene_gesserit_bond": agent_box(
            GainInfluence(), condition=_BG_BOND, requirement=_BG_BOND
        ),
        # Gene Manipulation (original game): "[trash] AND If you have
        # another Bene Gesserit card in play: [2 spice]" -- two printed
        # icons, each its own step in the owner's order (OQ-027), the Bond
        # judged when the spice icon resolves (OQ-028: trashing the other
        # Bene Gesserit card first loses the spice); the black trash icon is
        # optional [DI p. 16] [FAQ p. 3].
        "may_trash_and_gain_two_spice_if_bene_gesserit_bond": icon_box(
            ("trash", box_line(TrashPersonalCard())),
            ("spice", box_line(GainResources(spice=2), condition=_BG_BOND)),
        ),
        # Reverend Mother Mohiam (original game): "If you have another Bene
        # Gesserit card in play, each opponent discards two cards" -- the
        # Bond opens the box at the placement and is judged again when it
        # resolves (OQ-028); each opponent picks, clockwise from the next
        # seat, as many as the hand holds (OQ-118, [FAQ p. 3]).
        "each_opponent_discards_two_if_bene_gesserit_bond": agent_box(
            EachOpponentDiscardsCard(2), condition=_BG_BOND, requirement=_BG_BOND
        ),
        # Firm Grip (original game): "[2 Solari] -> Choose one: [Spacing Guild
        # Influence] / [Bene Gesserit Influence] / [Fremen Influence]" -- an
        # optional arrow paid once [DI p. 9] [FAQ p. 3]; paid, its reward waits
        # as an icon and the owner picks the Faction (never a track at 6,
        # OQ-060). No Emperor choice.
        "may_pay_two_solari_for_chosen_influence": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(
                        GainInfluence(
                            factions=(
                                Faction.SPACING_GUILD,
                                Faction.BENE_GESSERIT,
                                Faction.FREMEN,
                            )
                        ),
                    ),
                    costs=(PayResources(solari=2),),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("influence",),
        ),
        # Shifting Allegiances (original game): "[lose 1 Influence with a
        # chosen Faction] [2 spice] -> [2 Influence with one chosen
        # Faction]" -- an optional arrow paid once [DI p. 9] [FAQ p. 3]; the
        # loss and the spice are its cost, and paid, the +2 waits as an
        # armed "influence" icon whose Faction the owner picks (the same
        # one may be lost and gained again [FAQ p. 4]; one unbreakable
        # gain, imperium-base.md 13.3).
        "may_lose_influence_and_pay_two_spice_for_two_influence": (
            Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainInfluence(times=2, one_faction=True),),
                        costs=(LoseInfluence(1), PayResources(spice=2)),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("influence",),
            )
        ),
        # Test of Humanity (original game): "Each opponent chooses: Discard a
        # card -OR- Lose a deployed troop" -- one frame per opponent, the
        # next seat first, named ``<box>:opponent:<seat>`` as Covert
        # Operation's; each offers what it can do (imperium-base.md 13.1).
        "each_opponent_discards_or_loses_deployed_troop": agent_box(
            EachOpponentDiscardsOrLosesDeployedTroop()
        ),
        # Carryall (original game): "Double the base (not bonus) spice you
        # harvest with this Agent" -- the harvest reads this record
        # (``board_effects.apply_maker_space_action``); there is nothing to
        # resolve, so the box never opens (``AbilityMark.AUTOMATIC``,
        # ``agent_box_abilities.opens_at_placement``).
        "double_base_harvest_spice": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(box_line(DoubleBaseHarvestSpice()),),
            mark=AbilityMark.AUTOMATIC,
        ),
        # Thumper (promo): "Double the bonus spice you harvest with this
        # Agent" -- Carryall's shape for the bonus; the harvest reads this
        # record and the box never opens.
        "double_bonus_harvest_spice": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(box_line(DoubleBonusHarvestSpice()),),
            mark=AbilityMark.AUTOMATIC,
        ),
        # Jessica of Arrakis (promo): "If you have another Bene Gesserit card
        # in play: [draw 1] [draw 1]" -- the Bond opens the box at the
        # placement and is judged again on each icon when it resolves
        # (OQ-028), each draw its own step (OQ-027, OQ-106); Smuggler's
        # Thopter's two draw icons (``cards`` / ``cards_second``) under
        # Tread in Darkness's Bond.
        "draw_two_if_bene_gesserit_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(DrawPersonalCards(1), condition=_BG_BOND),
                box_line(DrawPersonalCards(1), condition=_BG_BOND),
            ),
            structure=AbilityStructure.SEPARATE,
            requirement=_BG_BOND,
            icons=("cards", "cards_second"),
        ),
    }
)
