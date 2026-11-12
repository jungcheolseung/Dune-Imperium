"""Agent-box ability records of personal cards (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2): the personal cards whose Agent box is
a plain or conditional gain are written as ability records here and resolved
by ``rules.agent_box_abilities``. A card's box key (each set's
``*_AGENT_BOXES`` table, by card id; ``UPRISING_AGENT_BOXES`` at the end of
this module) names the record. The printed text is ``display/tokens.py``.

- ``requirement`` is a condition fixed by the placement -- the visited space
  is a Maker space, a Faction Bond among the cards already in play (it can
  only shrink) -- and is judged when the card is played: when it fails the
  box is never pending (OQ-028 (a)).
- A line's ``condition`` is judged when the box resolves, in the owner's
  order (OQ-028); while it fails the box waits and the turn's end fizzles it
  (OQ-057 (1)). A Bond box judges its Bond both ways: a trash in the same
  turn can break it.
- ``icons`` marks a box whose printed icons resolve one action each
  (OQ-027 card Agent box extensions); the others resolve as one action.
- ``hook`` names a special flow kept as code in ``rules.agent_effects``
  (``_BOX_HOOKS``): a box with no event of its own, sources found nowhere
  else, or a frame rewritten mid-way. Its sections list the fragments it
  gives where the DSL has them (the network's card features, plan 4.4);
  they describe the box, the hook judges and pays it (editing a hook
  record's condition changes no play).

Every personal card's Agent box has a record (composed A3g); a leader's
Signet Ring (``leader_signet``) keeps its own code. Since stage 4, step 3c of
docs/content-core-refactor-plan.md, this module keeps the records only
Uprising's cards print (``UPRISING_AGENT_BOX_ABILITIES``, by box key); each
other set keeps its own in its ``agent_abilities`` module, the records cards
of several sets share are in ``content.core.agent_boxes`` with the builders
(``agent_box``, ``hook_box``, ``pay_box``, ...), and
``content.registry.card_abilities`` merges them.
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
    hook_box,
    icon_box,
    pay_box,
    trash_box,
)
from dune_imperium.content.core.effects import (
    AcquireCardForSolari,
    AtFactionSpace,
    AtMakerSpace,
    CompletedContractsAtLeast,
    DestroyShieldWall,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EachOpponentDiscardsCard,
    EffectSection,
    FactionBond,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    HasAlliance,
    InfluenceAtLeast,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecallAgent,
    RecruitTroops,
    ReturnThisCardToHand,
    SandwormsInConflictAtLeast,
    SpyRecalledThisTurn,
    SummonSandworm,
    TakeContract,
    TrashCard,
    TrashIntrigueCard,
    TrashPersonalCard,
    TrashThisCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.core.icons import (
    Faction,
)

_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_BG_TWO = InfluenceAtLeast(_BG, 2)
_GUILD_DISCARD = DiscardedCardHasFaction(Faction.SPACING_GUILD)
# Two box keys too long for a table line.
_BRANCHING_PATH = (
    "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
)
_JUNCTION_HEADQUARTERS = (
    "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
)


UPRISING_AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        "gain_spice_if_maker_space": agent_box(
            GainResources(spice=1), requirement=AtMakerSpace()
        ),
        "gain_two_spice_if_maker_space": agent_box(
            GainResources(spice=2), requirement=AtMakerSpace()
        ),
        "recruit_one_if_maker_space": agent_box(
            RecruitTroops(1), requirement=AtMakerSpace()
        ),
        "recruit_two_if_bene_gesserit_bond": agent_box(
            RecruitTroops(2), condition=_BG_BOND, requirement=_BG_BOND
        ),
        "return_self_if_bene_gesserit_bond": agent_box(
            ReturnThisCardToHand(), condition=_BG_BOND, requirement=_BG_BOND
        ),
        "recruit_three_if_spy_recalled_this_turn": agent_box(
            RecruitTroops(3), condition=SpyRecalledThisTurn()
        ),
        "recruit_two_if_spy_recalled_this_turn": agent_box(
            RecruitTroops(2), condition=SpyRecalledThisTurn()
        ),
        "draw_per_sandworm_in_conflict": agent_box(
            DrawPerSandwormInConflict(), condition=SandwormsInConflictAtLeast(1)
        ),
        "draw_if_bene_gesserit_influence_two": agent_box(
            DrawPersonalCards(1), condition=_BG_TWO
        ),
        "draw_intrigue_if_spy_recalled_this_turn": agent_box(
            DrawIntrigueCards(1), condition=SpyRecalledThisTurn()
        ),
        "draw_intrigue_if_three_units_in_conflict": agent_box(
            DrawIntrigueCards(1), condition=UnitsInConflictAtLeast(3)
        ),
        # --- One action: a follow-up after the box ---------------------------
        "take_contract": agent_box(TakeContract(1)),
        # Public Spectacle: "If you recalled a Spy this turn: ...".
        "gain_chosen_influence_if_spy_recalled_this_turn": agent_box(
            GainInfluence(), condition=SpyRecalledThisTurn()
        ),
        # Bene Gesserit Operative, Reliable Informant: "Place a Spy"; the
        # Faction marks printed beside the Spy icon (the card's
        # ``agent_spy_factions``) limit the post.
        "place_spy": agent_box(PlaceSpy()),
        # Double Agent.
        "place_spy_on_visited_space_may_share": agent_box(
            PlaceSpy(shared_post=True, visited_space=True)
        ),
        # --- Discard arrows (composed effects, A3d) ---------------------------
        # Delivery Agreement.
        "may_discard_to_take_contract": discard_box(box_line(TakeContract(1))),
        # Space-time Folding: "Draw 1 card (2 if the discarded card has
        # Spacing Guild affiliation)".
        "discard_to_draw_one_or_two_if_spacing_guild": discard_box(
            box_line(DrawPersonalCards(1)),
            box_line(DrawPersonalCards(1), condition=_GUILD_DISCARD),
        ),
        # Captured Mentat: the rewards are armed as icons once the discard
        # is paid, each resolved on its own (OQ-027).
        "may_discard_to_draw_intrigue_and_personal_card": discard_box(
            box_line(DrawIntrigueCards(1)),
            box_line(DrawPersonalCards(1)),
            armed=("intrigue", "cards"),
        ),
        # Guild Spy: "Draw 1 card (also Draw 1 Intrigue card if the
        # discarded card has Spacing Guild affiliation)".
        "may_discard_to_draw_one_and_intrigue_if_spacing_guild": discard_box(
            box_line(DrawPersonalCards(1)),
            box_line(DrawIntrigueCards(1), condition=_GUILD_DISCARD),
            armed=("cards", "intrigue"),
        ),
        # Guild Envoy: "[discard]" then, printed below it, "If you
        # discarded a Spacing Guild card: [card][card]" [card face] -- no
        # arrow, so the discard is no cost but the box's own mandatory
        # effect ("Agent turn에 play하면 반드시 card를 discard한다."
        # [FAQ p. 2]). The draw, a hidden draw printed apart, is armed
        # as its own step (OQ-106, user decision 2026-10-25 "Guild Envoy는
        # (가) discard와 draw를 별개 단계로 나눠"; engine audit
        # 2026-10-22, P6), as Guild Spy's is.
        "discard_one_draw_two_if_spacing_guild": discard_box(
            box_line(DrawPersonalCards(2), condition=_GUILD_DISCARD),
            mark=AbilityMark.MANDATORY,
            armed=("cards",),
        ),
        # --- Intrigue arrows (composed effects, A3d) --------------------------
        # Branching Path: "If Bene Gesserit Alliance: You may trash an
        # Intrigue card -> Draw 1 Intrigue card, Gain 2 spice"; the Alliance
        # over the whole arrow sits on the cost line, judged when the cost
        # is paid, and both rewards are then armed.
        _BRANCHING_PATH: Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(DrawIntrigueCards(1),),
                    condition=HasAlliance(_BG),
                    costs=(TrashIntrigueCard(),),
                ),
                box_line(GainResources(spice=2)),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("intrigue", "spice"),
        ),
        # Junction Headquarters: "If Spacing Guild Alliance: You may trash
        # an Intrigue card and pay 2 spice -> Gain 1 VP".
        _JUNCTION_HEADQUARTERS: Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainVictoryPoints(1),),
                    condition=HasAlliance(Faction.SPACING_GUILD),
                    costs=(TrashIntrigueCard(), PayResources(spice=2)),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Pivotal Gambit: the card trashes itself as the cost, then its troop
        # and the first-place pledge are armed as icons (OQ-022, OQ-027).
        "may_trash_self_for_troop_and_first_place_influence": trash_box(
            EffectSection(
                rewards=(RecruitTroops(1),), costs=(TrashCard(this_card=True),)
            ),
            box_line(PledgeFirstPlaceInfluence()),
            armed=("troops", "pledge"),
        ),
        # --- Optional acquisitions (composed effects, A3f) -------------------
        # Price is No Object: "You may acquire an Imperium Row or Reserve
        # card to your hand, paying its cost in solari".
        "acquire_with_solari_to_hand": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(box_line(AcquireCardForSolari()),),
            mark=AbilityMark.OPTIONAL,
        ),
        # Control the Spice: "You may pay 1 spice -> You may trash a card,
        # Recruit 1 troop" -- a paid arrow (``apply_payment``): the troop
        # now, the black trash icon on a frame of its own (cleanup-2d).
        # Control the Spice: "spice 1 → 카드 1장 trash + troop 1 recruit"
        # (docs/rules/epic-game-mode.md 6) -- the cost, then each reward its
        # own step in the owner's order: "화살표 비용 뒤 보상은 아이콘마다,
        # 순서는 소유자" (OQ-148 (가); printed-effects audit P-3, user
        # 2026-11-09). The troop is armed as an icon; the black trash icon,
        # optional once the cost is paid [FAQ p. 3], waits as the turn's
        # optional trash row (``agent_box_abilities.apply_payment``).
        "may_pay_spice_to_trash_and_recruit": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(RecruitTroops(1),), costs=(PayResources(spice=1),)
                ),
                box_line(TrashPersonalCard()),
            ),
            mark=AbilityMark.OPTIONAL,
            armed_icons=("troops", "trash"),
        ),
        # --- Printed icons with a choice icon (composed effects, A3f) -------
        # Each icon resolves on its own (OQ-027); a choice icon is answered
        # by its own rows (the Influence choice, the Agent recall, the trash),
        # an automatic one by ``resolve_agent_card_effect(effect=...)``.
        # Dangerous Rhetoric: "Trash this card, Gain 1 Influence with a chosen
        # Faction" -- queued Influence first, the order the old engine kept.
        "trash_self_and_gain_chosen_influence": icon_box(
            ("influence", box_line(GainInfluence())),
            ("trash_self", box_line(TrashThisCard())),
        ),
        # Steersman: "Draw 1 card, Recall 1 Agent".
        "draw_one_and_recall_agent": icon_box(
            ("cards", box_line(DrawPersonalCards(1))),
            ("recall", box_line(RecallAgent())),
        ),
        # Tread in Darkness: "If Bene Gesserit Bond: You may trash a card,
        # Draw 1 card" -- the Bond opens the box and is judged again on each
        # icon when it resolves (OQ-028); the trash stays optional (OQ-058).
        "trash_personal_card_to_draw_one_if_bene_gesserit_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(TrashPersonalCard(), condition=_BG_BOND),
                box_line(DrawPersonalCards(1), condition=_BG_BOND),
            ),
            structure=AbilityStructure.SEPARATE,
            requirement=_BG_BOND,
            icons=("trash", "cards"),
        ),
        # In High Places: "If you have another Bene Gesserit card in play:
        # [draw 1 card] [Spy]" -- as Tread in Darkness, the Bond opens the
        # box and is judged again on each icon (OQ-028); the Spy icon is
        # answered by the box's Spy rows (cleanup-2d-5).
        "draw_one_and_place_spy_if_bene_gesserit_bond": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                box_line(DrawPersonalCards(1), condition=_BG_BOND),
                box_line(PlaceSpy(), condition=_BG_BOND),
            ),
            structure=AbilityStructure.SEPARATE,
            requirement=_BG_BOND,
            icons=("cards", "spy"),
        ),
        # --- Optional arrows with no target (composed effects, A3b) ---------
        # Ecological Testing Station.
        "pay_two_water_to_draw_two": pay_box(
            PayResources(water=2), DrawPersonalCards(2)
        ),
        # Smuggler's Haven.
        "may_pay_four_spice_for_vp": pay_box(
            PayResources(spice=4), GainVictoryPoints(1)
        ),
        # --- One action with follow-ups for the opponents (composed A3g) -----
        # Covert Operation: "Each opponent discards a card" -- one frame per
        # opponent holding a card, named ``<box>:opponent:<seat>``.
        "each_opponent_discards_personal_card": agent_box(EachOpponentDiscardsCard()),
        # --- Special flows (hooks) -------------------------------------------
        # Seek Allies: "Trash this card." [Main p. 20] -- the box trashes
        # its own card (cleanup-2d).
        "trash_self": agent_box(TrashThisCard()),
        # Overthrow: "Gain two Influence instead of one." [Overthrow card]
        # -- the 2 replace the visited Faction space's 1, as Subversive
        # Advisor's and Treacherous Maneuver's do (OQ-046, OQ-128, user
        # ruling 2026-10-25 "이건 통일하는게 맞아"); nothing to gain off a
        # Faction space.
        "gain_visited_faction_influence": agent_box(
            GainInfluence(visited_space=True, times=2, replaces_space=True),
            requirement=AtFactionSpace(),
        ),
        # Long Live the Fighters: "If you have 3 or more cards in your deck:
        # Look at the top 3 cards, Draw 1, Discard 1, Trash 1" -- the
        # owner's pick frame over the pending box.
        "look_at_top_three": hook_box("long_live_the_fighters"),
        # Treacherous Maneuver: "You may trash this card and an Emperor card
        # from your hand -> Gain 2 Influence instead of 1 Influence with the
        # visited Faction" -- a trash box: the hand's Emperor card is the
        # pick, this card follows it (cleanup-2d).
        "trash_self_and_emperor_from_hand_for_extra_influence": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(
                        GainInfluence(
                            visited_space=True, times=2, replaces_space=True
                        ),
                    ),
                    costs=(
                        TrashCard(hand_only=True, faction=Faction.EMPEROR),
                        TrashCard(this_card=True),
                    ),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Corrinth City: "You may discard 2 cards and pay 5 solari -> Gain 1
        # VP" -- the two discards picked one by one, then all paid at once
        # (a discard-and-pay arrow, cleanup-2d).
        "may_discard_two_and_pay_five_solari_for_vp": Ability(
            timing=AbilityTiming.AGENT_BOX,
            sections=(
                EffectSection(
                    rewards=(GainVictoryPoints(1),),
                    costs=(DiscardFromHand(2), PayResources(solari=5)),
                ),
            ),
            mark=AbilityMark.OPTIONAL,
        ),
        # Arrakis Revolt: "If Maker Hooks: You may pay 2 spice -> You may
        # remove the Shield Wall, Summon 1 sandworm" -- the removal folded
        # into the payment row (OQ-026; a wall-and-worm arrow, cleanup-2d).
        "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks": (
            Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(
                            DestroyShieldWall(),
                            SummonSandworm(requires_maker_hooks=True),
                        ),
                        costs=(PayResources(spice=2),),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
            )
        ),
        # The Beast's Spoils: "Gain rewards for your face-up battle icons:
        # Crysknife: You may trash a card, Desert Mouse: Gain 1 spice,
        # Ornithopter: Recruit 1 troop".
        "gain_rewards_per_face_up_battle_icon": hook_box("beasts_spoils"),
        # --- Icon by icon (OQ-027) -------------------------------------------
        # Hidden Missive.
        "recruit_one_and_draw_if_bene_gesserit_influence_two": icon_box(
            ("troops", box_line(RecruitTroops(1), condition=_BG_TWO)),
            ("cards", box_line(DrawPersonalCards(1), condition=_BG_TWO)),
        ),
        # Maker Keeper.
        "gain_by_bene_gesserit_and_fremen_influence_two": icon_box(
            ("water", box_line(GainResources(water=1), condition=_BG_TWO)),
            (
                "spice",
                box_line(
                    GainResources(spice=1),
                    condition=InfluenceAtLeast(Faction.FREMEN, 2),
                ),
            ),
        ),
        # Wheels Within Wheels.
        "gain_by_emperor_and_spacing_guild_influence_two": icon_box(
            (
                "solari",
                box_line(
                    GainResources(solari=2),
                    condition=InfluenceAtLeast(Faction.EMPEROR, 2),
                ),
            ),
            (
                "spice",
                box_line(
                    GainResources(spice=1),
                    condition=InfluenceAtLeast(Faction.SPACING_GUILD, 2),
                ),
            ),
        ),
        # Cargo Runner: two printed lines, two and four completed Contracts.
        "draw_per_two_completed_contracts_up_to_two": icon_box(
            (
                "cards",
                box_line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(2)),
            ),
            (
                "cards_second",
                box_line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(4)),
            ),
        ),
    }
)



# Uprising's personal cards' Agent boxes (its starting, Reserve and Imperium
# cards), by card id: each value is the box's key (plan 8.3, step 3).
UPRISING_AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "experimentation": "research",
        "control_the_spice": "may_pay_spice_to_trash_and_recruit",
        "seek_allies": "trash_self",
        "signet_ring": "leader_signet",
        "prepare_the_way": "draw_if_bene_gesserit_influence_two",
        "bene_gesserit_operative": "place_spy",
        "branching_path": (
            "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
        ),
        "calculus_of_power": "trash_personal_card",
        "captured_mentat": "may_discard_to_draw_intrigue_and_personal_card",
        "cargo_runner": "draw_per_two_completed_contracts_up_to_two",
        "chani_clever_tactician": "draw_intrigue_if_three_units_in_conflict",
        "corrinth_city": "may_discard_two_and_pay_five_solari_for_vp",
        "covert_operation": "each_opponent_discards_personal_card",
        "dangerous_rhetoric": "trash_self_and_gain_chosen_influence",
        "delivery_agreement": "may_discard_to_take_contract",
        "desert_power": "gain_two_spice_if_maker_space",
        "desert_survival": "trash_personal_card",
        "double_agent": "place_spy_on_visited_space_may_share",
        "ecological_testing_station": "pay_two_water_to_draw_two",
        "fedaykin_stilltent": "recruit_one_if_maker_space",
        "guild_envoy": "discard_one_draw_two_if_spacing_guild",
        "guild_spy": "may_discard_to_draw_one_and_intrigue_if_spacing_guild",
        "hidden_missive": "recruit_one_and_draw_if_bene_gesserit_influence_two",
        "imperial_spymaster": "draw_intrigue_if_spy_recalled_this_turn",
        "in_high_places": "draw_one_and_place_spy_if_bene_gesserit_bond",
        "interstellar_trade": "gain_chosen_influence",
        "junction_headquarters": (
            "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
        ),
        "leadership": "draw_per_sandworm_in_conflict",
        "long_live_the_fighters": "look_at_top_three",
        "maker_keeper": "gain_by_bene_gesserit_and_fremen_influence_two",
        "maula_pistol": "draw_personal_card",
        "northern_watermaster": "gain_water",
        "overthrow": "gain_visited_faction_influence",
        "paracompass": "gain_two_solari",
        "price_is_no_object": "acquire_with_solari_to_hand",
        "priority_contracts": "take_contract",
        "public_spectacle": "gain_chosen_influence_if_spy_recalled_this_turn",
        "rebel_supplier": "recruit_two_if_spy_recalled_this_turn",
        "reliable_informant": "place_spy",
        "shishakli": "trash_personal_card_to_draw_one",
        "smuggler_s_harvester": "gain_spice_if_maker_space",
        "smuggler_s_haven": "may_pay_four_spice_for_vp",
        "southern_elders": "recruit_two_if_bene_gesserit_bond",
        "space_time_folding": "discard_to_draw_one_or_two_if_spacing_guild",
        "spacing_guild_s_favor": "draw_personal_card",
        "steersman": "draw_one_and_recall_agent",
        "stilgar_the_devoted": "recruit_two_troops",
        "strike_fleet": "recruit_three_if_spy_recalled_this_turn",
        "subversive_advisor": "gain_two_visited_faction_influence_and_trash_self",
        "treacherous_maneuver": "trash_self_and_emperor_from_hand_for_extra_influence",
        "tread_in_darkness": "trash_personal_card_to_draw_one_if_bene_gesserit_bond",
        "weirding_woman": "return_self_if_bene_gesserit_bond",
        "wheels_within_wheels": "gain_by_emperor_and_spacing_guild_influence_two",
        "arrakis_revolt": (
            "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks"
        ),
        "pivotal_gambit": "may_trash_self_for_troop_and_first_place_influence",
        "the_beast_s_spoils": "gain_rewards_per_face_up_battle_icon",
    }
)
