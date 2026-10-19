"""Tests for the fixed integer Uprising action codec."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters import ACTION_CODEC_VERSION, ActionCodec
from dune_imperium.adapters.action_codec import (
    ActionTemplate,
    _scouts_templates,
    catalog_spaces,
)
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect
from dune_imperium.core import DomainAction, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effects import AUTOMATIC_AGENT_ICONS
from dune_imperium.rules.board_effects import AUTOMATIC_BOARD_ICONS
from dune_imperium.rules.effect_steps import steps_for
from dune_imperium.simulation import run_random_round

_SCOUTS_ACTION_PREFIXES = (
    "choose_four_bonus",
    "choose_subcommittee",
    "join_subcommittee",
    "decline_subcommittee",
    "scouts_",
    # The generic optional-trash frame's actions, which only the Bloodlines
    # and Immortality catalogs hold otherwise.
    "decline_optional_trash",
    "trash_optional_card",
    "take_desert_riding_hooks",
    "confirm_scouts_bid",
    # A Scouts choice with no line the seat can take (codec v149).
    "resolve_scouts_choice_without_option",
)


def _round_trip_steps(
    codec: ActionCodec,
    whole: DomainAction,
    printed: str | None = None,
) -> tuple[DomainAction, ...]:
    """Stage B3a: the Agent-effect frame offers ``whole`` as its effect row
    and target rows (``effect_steps.steps_for``, ``printed`` naming the card
    type or space that printed the effect). Check that each row round trips
    through the codec and return them."""

    rows = steps_for(whole, printed)
    for row in rows:
        assert codec.decode(codec.encode(row), actor=whole.actor) == row
    return rows


def test_catalog_is_fixed_and_versioned_for_a_ruleset() -> None:
    first = ActionCodec(RulesetConfig())
    second = ActionCodec(RulesetConfig())

    assert ACTION_CODEC_VERSION == 150
    assert first.catalog == second.catalog
    assert first.size == len(first.catalog)
    # v92/v93/v97: the Reveal gain actions join every catalog (troops, Intrigue,
    # and seven distinct printed resource bundles — Occupation adds water+spice).
    # v100: skip_intrigue_acquisition and Change Allegiances' third option.
    # v103: separate Intrigue lines (use_intrigue_effect x2, finish; Change
    # Allegiances back to one option).
    # v106: trash_intrigue_for_agent_card joins one template per base-catalog
    # Intrigue instance (Branching Path's re-transcribed Agent box), +40; its
    # corrected City icon (not Landsraad) also shifts which board spaces (and
    # their cost/infiltration-post combinations) its agent_turn templates
    # cover, a net +1.
    # v107: the generic Spy placement frame serves every ruleset (the Emperor
    # track's Influence 4 Spy [Main p. 7]): place_spy_on_space and
    # recall_spy_for_placement per post (13 + 13) and decline_spy_placement
    # join the catalogs without Bloodlines, +27.
    # v108 (2026-09-26 card-transcription audit, net per catalog without
    # Bloodlines): Maker Keeper's single City icon and Undercover Asset's
    # missing Spy icon [card faces] drop 36 agent_turn placements; a Conflict
    # reward Spy may recall first or decline [Main pp. 11, 20] (+13 recalls,
    # +1 decline) and so may a Leader Spy (+1); Covert Operation's two Reveal
    # Spies (+1 resume) and Unswerving Loyalty's Fremen Bond troop move (+1
    # resume, and Shadout Mapes' deploy/retreat/decline join every catalog,
    # +3).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    # v109 (OQ-068, 2026-09-26 user ruling): every Recall Agent effect may
    # recall an Into the Fray Agent from the Conflict, not only Imperial
    # Privilege. Both new templates need Bloodlines (an Into the Fray Agent
    # only exists then), so the Bloodlines-less base catalog is unchanged.
    # v110: an Agent-box Spy may pass up the recall-first too, when the box
    # resolves (decline_agent_card_spy, +1).
    # v125 (L2): Imperial Privilege's recall with no target is confirmed
    # (resolve_imperial_privilege_without_recall, +1).
    # v125 (L2): a Conflict reward Influence choice with every eligible
    # Faction at the top is confirmed
    # (resolve_combat_influence_without_faction, +1).
    # v129 (OQ-016, user ruling 2026-10-03): Distraction plays once its
    # deployment condition holds and places its Spy through the Intrigue
    # choice, so decline_intrigue_trigger and the 13 + 13 place/recall
    # trigger templates leave every catalog (-27).
    # v130 (OQ-005, user ruling 2026-10-04): flip_battle_card gains one
    # template per Objective, which counts as a won Conflict card (+4).
    # v131 (user ruling 2026-10-04, overriding OQ-057 (15)): the owner's
    # waiting Emperor track Spy is opened by place_track_spy (+1).
    # v134: finish_leader_draft confirms the last reversible pick (+1).
    assert first.size == (
        4354
        + 2
        + 7
        + 4
        + 1
        + 2
        + 1
        + 40
        + 1
        + 27
        - 36
        + 13
        + 1
        + 1
        + 1
        + 1
        + 3
        + 1
        + 1
        + 1
        + 1
        - 27
        + 4
        + 1
        + 1
        + 1  # v137: the cards_second icon key
        + 1  # v137: the research icon key
        + 1  # v137: the return_self icon key
        + 1  # v137: the Intrigue Influence confirm
        + 1  # v137: Tactical Option retreats 0
        + 1  # v137: an "up to" deploy of 0
        + 1  # v142: draw_owed_intrigue (OQ-106)
        # v147 (OQ-095 (7) addition): the ``source``-named Reveal choice
        # rows of the base deck's cards -- Spy Network's recall (13), the
        # placement and recall-first of Public Spectacle, Wheels within
        # Wheels, Covert Operation and Undercover Asset (4 x 26), Chani's
        # retreat (1), Calculus of Power's trash of an Emperor card (17),
        # the plain Spy icons' pass of their recall-first (3) and Unswerving
        # Loyalty's deploy and retreat (2).
        + 140
        # v149 (cleanup-2f, user decision 2026-10-18): four refusals the
        # engine no longer offers leave (decline_other_memories,
        # decline_leader_board_repeat, resolve_desert_tactics_without_trash,
        # decline_imperial_privilege_intrigue) and two confirms join
        # (resolve_leader_signet_without_option,
        # resolve_combat_trash_without_card).
        - 2
        # v150 (stage B1, OQ-111): the Agent turn is a card pick and a space
        # pick, so the one agent_turn template per card-and-space
        # combination gives way to a choose_agent_card per card (and graft)
        # and a place_agent per space variant.
        - 1634
        # v150 (stage B2, OQ-112): a Conflict reward's icon rows, one per
        # icon kind but the Bloodlines-only Deep Cover Spy.
        + 14
        # v150 (stage B3a, OQ-111): the Agent-effect frame offers a waiting
        # effect as an effect row (its verb, the entity that printed it and
        # its icon) and then one target row per target. The whole templates
        # of the ids in ``effect_steps.STEP_SPECS`` that no other frame still
        # offers as they are (the per-card trash, discard and Corrinth City
        # picks, the per-card Solari acquisitions, the per-post Spy rows ...)
        # leave (792), and the rows that stand for them join (964).
        - 792
        + 964
        # v150 (stage B3b-2): the Reveal frame offers its effects effect
        # first too: the purchases' and the Reveal leader rows' whole
        # templates leave (146), their effect rows and the target rows not
        # yet in the catalog (an Alliance recipient's seat) join (28).
        - 146
        + 28
    )
    # v143: the box 1 twins of a grafted turn join the Immortality catalogs
    # only, so the base catalog is unchanged by them. Stage B3a's net +172
    # (above) took it from 2,931 to 3,103, stage B3b-2's net -118 to 2,985.
    assert first.size == 2985


def _scouts_catalog_additions(
    config: RulesetConfig, scouts_only: set[ActionTemplate]
) -> set[ActionTemplate]:
    """What a Scouts catalog holds beyond the catalog without the option.

    Stage B3a: the Agent-effect frame offers two Scouts ids only as steps
    (``scouts_collect_mission`` and ``take_desert_riding_hooks``), so their
    whole templates are not in the catalog; the rows that stand for them are
    -- the mission's ``collect`` effect row per visited space and its
    ``choose_option`` target rows, and the Maker icon's ``take`` row.
    """

    step_only = {"scouts_collect_mission", "take_desert_riding_hooks"}
    collect_rows = {
        ActionTemplate(
            "collect",
            (
                ("icon", "scouts_mission"),
                ("printed", space.space_id),
                ("source", "board_space"),
            ),
        )
        for space in catalog_spaces(config)
    }
    choice_rows = {
        ActionTemplate("choose_option", (("option", option),))
        for option in ("solari", "spice")
    }
    maker_row = ActionTemplate(
        "take",
        (("icon", "maker"), ("printed", "hagga_basin"), ("source", "board_space")),
    )
    return {
        *(t for t in scouts_only if t.action_id not in step_only),
        *collect_rows,
        *choice_rows,
        maker_row,
    }


def test_arrakeen_scouts_templates_join_only_the_scouts_catalogs() -> None:
    # Design 4.9: every Scouts template sits in one gated block, so the
    # catalogs without the option are byte for byte what they were (base
    # 4,427) and a Scouts catalog adds exactly those templates -- and, since
    # stage B3a, the effect rows that stand for the two Scouts ids the
    # Agent-effect frame offers only as steps.
    for options in (
        {},
        {
            "choam_module": True,
            "promo_cards": True,
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
        },
    ):
        without = ActionCodec(RulesetConfig(**options))
        scouts_config = RulesetConfig(arrakeen_scouts=True, **options)
        with_scouts = ActionCodec(scouts_config)
        scouts_only = set(_scouts_templates(scouts_config))
        added = _scouts_catalog_additions(scouts_config, scouts_only)
        assert set(with_scouts.catalog) - set(without.catalog) == added
        assert all(t.action_id.startswith(_SCOUTS_ACTION_PREFIXES) for t in scouts_only)
        assert set(without.catalog) <= set(with_scouts.catalog)
        assert not any(
            t.action_id in {"scouts_collect_mission", "take_desert_riding_hooks"}
            for t in with_scouts.catalog
        )
    assert ActionCodec(RulesetConfig()).size == 2985
    base_scouts = RulesetConfig(arrakeen_scouts=True)
    assert ActionCodec(base_scouts).size == 2985 + len(
        _scouts_catalog_additions(base_scouts, set(_scouts_templates(base_scouts)))
    )


def test_scouts_specimen_return_needs_immortality_recall_conflict_always_in() -> None:
    """OQ-074, OQ-075 (D), user ruling 2026-09-29: the specimen top-up
    template range (0..MAX_SPECIMEN_TOP_UP) needs Immortality on; a
    ``scouts_recall_agent`` with ``space_id="conflict"`` (Into the Fray) is
    in every Scouts catalog, with or without Immortality."""

    from dune_imperium.content.arrakeen_scouts import MAX_SPECIMEN_TOP_UP

    plain = ActionCodec(RulesetConfig(arrakeen_scouts=True))
    immortal = ActionCodec(RulesetConfig(arrakeen_scouts=True, immortality=True))
    assert not any(t.action_id == "scouts_return_specimens" for t in plain.catalog)
    counts = sorted(
        dict(t.arguments)["count"]
        for t in immortal.catalog
        if t.action_id == "scouts_return_specimens"
    )
    assert counts == list(range(MAX_SPECIMEN_TOP_UP + 1))
    for codec in (plain, immortal):
        assert any(
            t.action_id == "scouts_recall_agent"
            and dict(t.arguments)["space_id"] == "conflict"
            for t in codec.catalog
        )


def test_choam_contract_choice_round_trips_only_in_the_module_catalog() -> None:
    action = DomainAction(
        action_id="take_contract",
        actor=2,
        arguments=(("instance_id", "contract:high_council_ii"),),
    )
    codec = ActionCodec(RulesetConfig(choam_module=True))

    assert codec.decode(codec.encode(action), actor=2) == action
    # v96: the research icon's board-effect resolution (Immortality).
    # v106: trash_intrigue_for_agent_card joins one template per CHOAM-catalog
    # Intrigue instance (+44) and Branching Path's corrected City icon shifts
    # its agent_turn space coverage by +1 (see test_catalog_is_fixed...).
    # v107: +27, the generic Spy placement frame (see above).
    # v108 (2026-09-26 card-transcription audit, net per catalog without
    # Bloodlines): Maker Keeper's single City icon and Undercover Asset's
    # missing Spy icon [card faces] drop 36 agent_turn placements; a Conflict
    # reward Spy may recall first or decline [Main pp. 11, 20] (+13 recalls,
    # +1 decline) and so may a Leader Spy (+1); Covert Operation's two Reveal
    # Spies (+1 resume) and Unswerving Loyalty's Fremen Bond troop move (+1
    # resume, and Shadout Mapes' deploy/retreat/decline join every catalog,
    # +3).
    # The CHOAM catalogs also gain decline_contract_spy (+1).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    # v109 (OQ-068): both new Conflict-recall templates also need Bloodlines,
    # so the CHOAM-without-Bloodlines catalog is unchanged (see v109 above).
    # v110: an Agent-box Spy may pass up the recall-first too, when the box
    # resolves (decline_agent_card_spy, +1).
    # v125 (L2): the recall confirms, resolve_imperial_privilege_without_recall
    # and resolve_contract_without_recall (+2).
    # v125 (L2): a Conflict reward Influence choice with every eligible
    # Faction at the top is confirmed
    # (resolve_combat_influence_without_faction, +1).
    # v129 (OQ-016, user ruling 2026-10-03): Distraction plays once its
    # deployment condition holds and places its Spy through the Intrigue
    # choice, so decline_intrigue_trigger and the 13 + 13 place/recall
    # trigger templates leave every catalog (-27).
    # v130 (OQ-021, user ruling 2026-10-04): Shaddam's icon over an exhausted
    # market takes a set-aside Contract, so take_exhausted_contract_solari
    # leaves the CHOAM catalogs (-1).
    # v130 (OQ-005, user ruling 2026-10-04): flip_battle_card gains one
    # template per Objective, which counts as a won Conflict card (+4).
    # v131 (user ruling 2026-10-04, overriding OQ-057 (15)): the owner's
    # waiting Emperor track Spy is opened by place_track_spy (+1).
    # v134: finish_leader_draft confirms the last reversible pick (+1).
    assert codec.size == (
        4640
        + 2
        + 7
        + 4
        + 1
        + 2
        + 1
        + 44
        + 1
        + 27
        - 36
        + 13
        + 1
        + 1
        + 1
        + 1
        + 3
        + 1
        + 1
        + 1
        + 2
        + 1
        - 27
        - 1
        + 4
        + 1
        + 1
        + 1  # v137: the cards_second icon key
        + 1  # v137: the research icon key
        + 1  # v137: the return_self icon key
        + 1  # v137: the Intrigue Influence confirm
        + 1  # v137: Tactical Option retreats 0
        + 1  # v137: an "up to" deploy of 0
            + 1  # v142: draw_owed_intrigue (OQ-106)
        # v147: the base catalog's 140 ``source``-named Reveal rows plus
        # Priority Contracts' and Delivery Agreement's spice-or-VP (2 x 2).
        + 144
        # v149 (cleanup-2f, user decision 2026-10-18): four refusals the
        # engine no longer offers leave (decline_other_memories,
        # decline_leader_board_repeat, resolve_desert_tactics_without_trash,
        # decline_imperial_privilege_intrigue) and two confirms join
        # (resolve_leader_signet_without_option,
        # resolve_combat_trash_without_card).
        - 2
        # v150 (stage B1, OQ-111): the Agent turn's card and space picks
        # replace its card-and-space agent_turn templates (see
        # test_catalog_is_fixed...).
        - 1735
        # v150 (stage B2, OQ-112): a Conflict reward's icon rows (14) and a
        # completed Contract's (9).
        + 14
        + 9
        # v150 (stage B3a, OQ-111): the Agent-effect frame's effect and target
        # rows replace the whole templates of the ids in
        # ``effect_steps.STEP_SPECS`` that no other frame still offers as they
        # are (see test_catalog_is_fixed...): 848 leave, 1,024 rows join (the
        # CHOAM catalogs also trade a completed Contract's 20 whole
        # templates for 20 effect rows).
        - 848
        + 1024
        # v150 (stage B3b, OQ-112 (4)): a Contract completed in its owner's
        # turn leaves its icons as turn rows naming it -- a whole template
        # per Contract and icon (23) and its effect row (23).
        + 23
        + 23
        # v150 (stage B3b-2): the Reveal frame's effect rows (see above):
        # 154 whole templates leave and 32 rows join.
        - 154
        + 32
    )

    try:
        ActionCodec(RulesetConfig()).encode(action)
    except ValueError as error:
        assert "not present" in str(error)
    else:
        raise AssertionError("module-off codec accepted a Contract action")


def test_bloodlines_contract_tokens_round_trip_only_with_both_options() -> None:
    # v98: the eight Bloodlines contract tokens and the Immediate's Intrigue
    # trash join the CHOAM+Bloodlines catalog; v99: Imperial Privilege may
    # recall Duncan Idaho's Into the Fray Agent (OQ-037(d)).
    both = ActionCodec(RulesetConfig(choam_module=True, bloodlines=True))
    take_contract = DomainAction(
        action_id="take_contract",
        actor=1,
        arguments=(("instance_id", "contract:bloodlines_earn_any_alliance"),),
    )
    trash_intrigue = DomainAction(
        action_id="trash_intrigue_for_contract",
        actor=1,
        arguments=(("card_id", "intrigue:backed_by_choam:0"),),
    )
    # Stage B3a: the Agent-effect frame offers a recall from the Conflict as
    # the Recall Agent effect row of its source (Imperial Privilege, a card)
    # and then the Conflict as a ``choose_space`` target row.
    recall_conflict_privilege = steps_for(
        DomainAction(action_id="recall_conflict_agent_for_imperial_privilege", actor=1),
        "imperial_privilege",
    )
    # v109 (OQ-068, 2026-09-26 user ruling): Steersman's Recall Agent icon
    # and Twisted Mentat, and the Sardaukar II / High Council token Contract
    # reward, may likewise recall an Into the Fray Agent from the Conflict.
    recall_conflict_agent_card = steps_for(
        DomainAction(action_id="recall_conflict_agent_for_agent_card", actor=1),
        "steersman",
    )
    conflict_target = DomainAction(
        action_id="choose_space", actor=1, arguments=(("space_id", "conflict"),)
    )
    assert recall_conflict_privilege[-1] == conflict_target
    assert recall_conflict_agent_card[-1] == conflict_target
    recall_conflict_contract = DomainAction(
        action_id="recall_conflict_agent_for_contract", actor=1
    )
    # v125 (L2): only the Bloodlines Immediate can be out of reach (OQ-059).
    hold_icons = DomainAction(action_id="hold_contract_icons", actor=1)
    fizzle_icons = DomainAction(
        action_id="resolve_contract_icons_without_contract", actor=1
    )
    actions = (
        take_contract,
        trash_intrigue,
        *recall_conflict_privilege,
        *recall_conflict_agent_card,
        recall_conflict_contract,
        hold_icons,
        fizzle_icons,
    )
    for action in actions:
        assert both.decode(both.encode(action), actor=1) == action
    # v104: the Commander share of a retreat reaches 12 troops + 7
    # Commanders, which adds 28 unit-count templates [Bloodlines p. 4].
    # v105: Fedaykin Maneuver's Commander-share retreats reach 19 units (+28).
    # v106: trash_intrigue_for_agent_card joins one template per
    # CHOAM+Bloodlines-catalog Intrigue instance, including Piter de Vries'
    # Twisted Intrigue cards (+72). Branching Path's corrected City icon does
    # not change its agent_turn coverage here (unlike the base/CHOAM
    # catalogs, see test_catalog_is_fixed_and_versioned_for_a_ruleset):
    # every Bene Gesserit card already gets every Agent icon's placements
    # under Bloodlines, for Urgent Shigawire's boost.
    # v108 (2026-09-26 card-transcription audit): the Conflict reward and
    # Leader Spies' recall-first (+15, see the base catalog test), Covert
    # Operation and Unswerving Loyalty (+5), Unswerving Loyalty's and Shadout
    # Mapes' Commander moves in every Bloodlines catalog (+2, a Commander "is
    # a 'troop'" [Bloodlines p. 4]); one timing per printed band for Grasp
    # Arrakis and Tenuous Bond (-3 play_intrigue), a forced Spy move with no
    # post off the Agent's space loses the Spy (+1 lose_moved_spy, OQ-065),
    # Navigation card 10's arrow cost may be declined (+1), Coercive
    # Negotiation is mandatory (-1 decline, OQ-064).
    # The CHOAM catalog also gains decline_contract_spy (+1).
    # decline_acquisition_spy: an acquisition-bonus Spy may pass up the
    # recall-first without a Spy in supply [Main pp. 11, 20] (+1).
    # v109 (OQ-068): recall_conflict_agent_for_agent_card (+1) and
    # recall_conflict_agent_for_contract (+1).
    # v110: an Agent-box Spy may pass up the recall-first too, when the box
    # resolves (decline_agent_card_spy, +1).
    # v125 (L2): the recall confirms, resolve_imperial_privilege_without_recall
    # and resolve_contract_without_recall (+2).
    # v125 (L2): a Conflict reward Influence choice with every eligible
    # Faction at the top is confirmed
    # (resolve_combat_influence_without_faction, +1).
    # v125 (L2): a Holy War opponent with no unit to lose confirms it
    # (resolve_unit_loss_without_unit, +1).
    # v125 (L2): a bank Commander with no choosable Skill is confirmed
    # (resolve_commander_without_skill, +1).
    # v125 (L2): Contract icons over a market with nothing takeable are held
    # by the owner's confirm (hold_contract_icons, +1; OQ-059).
    # v126: a Combat Intrigue's icons fizzle at once by the owner's confirm
    # (resolve_contract_icons_without_contract, +1; user ruling 2026-10-02).
    # v129 (OQ-016, user ruling 2026-10-03): Distraction plays once its
    # deployment condition holds and places its Spy through the Intrigue
    # choice, so decline_intrigue_trigger and the 13 + 13 place/recall
    # trigger templates leave every catalog (-27).
    # v130 (OQ-021): take_exhausted_contract_solari leaves the CHOAM catalogs
    # (-1).
    # v130 (OQ-005, user ruling 2026-10-04): flip_battle_card gains one
    # template per Objective, which counts as a won Conflict card (+4).
    # v131 (user ruling 2026-10-04, overriding OQ-057 (15)): the owner's
    # waiting Emperor track Spy is opened by place_track_spy (+1).
    # v134: finish_leader_draft confirms the last reversible pick (+1).
    assert (
        both.size
        == 11100 + 28 + 28 + 72 + 15 + 5 + 2 - 3 + 1 + 1 - 1 + 1 + 1 + 1 + 1 + 1 + 2
        + 1
        + 1
        + 1
        + 1
        + 1
        - 27
        - 1
        + 4
        + 1
        + 1
        + 1  # v137: the cards_second icon key
        + 1  # v137: the research icon key
        + 1  # v137: the return_self icon key
        + 1  # v137: the Intrigue Influence confirm
        + 1  # v137: Tactical Option retreats 0
        + 1  # v137: an "up to" deploy of 0
        + 1  # v142: draw_planetologist_intrigue (OQ-106)
        + 1  # v142: draw_owed_intrigue (OQ-106)
        + 1  # v142: draw_owed_card (OQ-106)
        # v147: the ``source``-named Reveal choice rows of the CHOAM and
        # Bloodlines decks' cards (Shrouded Counsel's trash of any personal
        # card alone is one per instance).
        + 334
        # v149 (cleanup-2f): the five refusals the engine no longer offers
        # leave (decline_sardaukar_commander among them) and two confirms
        # join.
        - 3
        # v150 (stage B1, OQ-111): the Agent turn's card and space picks
        # replace its card-and-space agent_turn templates (see
        # test_catalog_is_fixed...).
        - 6425
        # v150 (stage B2, OQ-112): a Conflict reward's icon rows, with the
        # Deep Cover Spy (15), and a completed Contract's (9).
        + 15
        + 9
        # v150 (stage B3a, OQ-111): the Agent-effect frame's effect and target
        # rows replace the whole templates of the ids in
        # ``effect_steps.STEP_SPECS`` that no other frame still offers as they
        # are (see test_catalog_is_fixed...): 1,170 leave, 1,523 rows join
        # (the Bloodlines cards' retreat, Contract and Sardaukar Commander
        # picks among them).
        - 1170
        + 1523
        # v150 (stage B3b, OQ-112 (4)): the in-turn Contract rows, a whole
        # template per Contract and icon (37) and its effect row (37).
        + 37
        + 37
        # v150 (stage B3b-2): the Reveal frame's effect rows: 222 whole
        # templates leave (the Commander Skill trash among them) and 53 rows
        # join.
        - 222
        + 53
    )

    choam_only = ActionCodec(RulesetConfig(choam_module=True))
    # The two recalls' effect rows are in every catalog; the Conflict they
    # may pick (stage B3a: the target row) needs Bloodlines.
    recall_effect_rows = (recall_conflict_privilege[0], recall_conflict_agent_card[0])
    for action in actions:
        if action in recall_effect_rows:
            assert choam_only.decode(choam_only.encode(action), actor=1) == action
            continue
        with pytest.raises(ValueError, match="not present"):
            choam_only.encode(action)
    bloodlines_only = ActionCodec(RulesetConfig(bloodlines=True))
    for action in (take_contract, trash_intrigue, recall_conflict_contract, hold_icons):
        with pytest.raises(ValueError, match="not present"):
            bloodlines_only.encode(action)
    # recall_conflict_agent_for_imperial_privilege and
    # recall_conflict_agent_for_agent_card (their rows) need only Bloodlines:
    # an Into the Fray Agent exists without the CHOAM Module (OQ-068).
    for action in (*recall_conflict_privilege, *recall_conflict_agent_card):
        assert bloodlines_only.decode(bloodlines_only.encode(action), actor=1) == action


def test_choam_contract_completion_and_spy_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig(choam_module=True))
    # Stage B3a: completing a Contract is an effect row naming the Contract
    # (an effect without a target is one row).
    complete = DomainAction(
        action_id="complete_contract",
        actor=1,
        arguments=(("instance_id", "contract:arrakeen_ii"),),
    )
    (complete_row,) = _round_trip_steps(codec, complete)
    assert complete_row.action_id == "complete_contract"
    assert dict(complete_row.arguments) == {
        "printed": "contract:arrakeen_ii",
        "source": "contract",
    }
    actions = (
        DomainAction(
            action_id="place_contract_spy",
            actor=1,
            arguments=(("post_id", "arrakis-spice-refinery-arrakeen"),),
        ),
        DomainAction(
            action_id="recall_spy_for_contract",
            actor=1,
            arguments=(("post_id", "arrakis-spice-refinery-arrakeen"),),
        ),
        DomainAction(action_id="decline_contract_spy", actor=1),
        DomainAction(action_id="keep_contract_reveal_spice", actor=1),
        DomainAction(action_id="trash_contract_reveal_for_vp", actor=1),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=1) == action


def test_spy_recall_first_choices_round_trip_in_every_catalog() -> None:
    # A Spy icon without a Spy in supply: "you may first recall one of your
    # Spies for no effect" [Main pp. 11, 20] -- the Conflict reward and
    # Leader Spies' recall and decline templates exist in every catalog, and
    # so do the acquisition-bonus and Agent-box Spies' declines.
    actions = (
        DomainAction(action_id="decline_combat_reward_spy", actor=2),
        DomainAction(
            action_id="recall_spy_for_combat_reward",
            actor=2,
            arguments=(("post_id", "arrakis-deep-desert"),),
        ),
        DomainAction(action_id="decline_leader_spy_placement", actor=2),
        DomainAction(action_id="decline_acquisition_spy", actor=2),
        DomainAction(action_id="decline_agent_card_spy", actor=2),
    )
    for config in (
        RulesetConfig(),
        RulesetConfig(choam_module=True),
        RulesetConfig(bloodlines=True, choam_module=True),
    ):
        codec = ActionCodec(config)
        for action in actions:
            assert codec.decode(codec.encode(action), actor=2) == action


def test_board_effect_icons_round_trip_and_the_bare_action_is_gone() -> None:
    # One template per printed automatic icon (OQ-027); the old argument-less
    # "resolve everything at once" action left the catalog with codec v86.
    codec = ActionCodec(RulesetConfig())
    assert AUTOMATIC_BOARD_ICONS == tuple(sorted(AUTOMATIC_BOARD_ICONS))
    for key in AUTOMATIC_BOARD_ICONS:
        action = DomainAction(
            action_id="resolve_board_effect",
            actor=1,
            arguments=(("effect", key),),
        )
        # Stage B3a: the Agent-effect frame offers the icon as one effect row
        # (its verb, the visited space and the icon), not as the whole
        # action, which the catalog no longer holds.
        (row,) = _round_trip_steps(codec, action, "arrakeen")
        assert dict(row.arguments) == {
            "icon": key,
            "printed": "arrakeen",
            "source": "board_space",
        }
        with pytest.raises(ValueError, match="not present"):
            codec.encode(action)

    try:
        codec.encode(DomainAction(action_id="resolve_board_effect", actor=1))
    except ValueError as error:
        assert "not present" in str(error)
    else:
        raise AssertionError("the catalog still lists the bare board-effect action")


def test_agent_card_icons_round_trip_beside_the_bare_action() -> None:
    # Multi-icon Agent boxes resolve one keyed template per icon (OQ-027);
    # single-effect boxes keep the argument-less template (codec v87).
    codec = ActionCodec(RulesetConfig())
    assert AUTOMATIC_AGENT_ICONS == tuple(sorted(AUTOMATIC_AGENT_ICONS))
    bare = DomainAction(action_id="resolve_agent_card_effect", actor=2)
    assert codec.decode(codec.encode(bare), actor=2) == bare
    for key in AUTOMATIC_AGENT_ICONS:
        action = DomainAction(
            action_id="resolve_agent_card_effect",
            actor=2,
            arguments=(("effect", key),),
        )
        assert codec.decode(codec.encode(action), actor=2) == action


def test_reveal_choice_deferral_and_resumption_round_trip() -> None:
    # Free Reveal ordering [Main p. 12]: one bare deferral plus one resume
    # template per choice-effect kind (codec v88).
    # Bloodlines and Immortality choice kinds join only the option's
    # catalogs.
    codec = ActionCodec(RulesetConfig(bloodlines=True, immortality=True))
    defer = DomainAction(action_id="defer_reveal_choice", actor=3)
    assert codec.decode(codec.encode(defer), actor=3) == defer
    for effect in PersonalCardRevealChoiceEffect:
        action = DomainAction(
            action_id="resume_reveal_choice",
            actor=3,
            arguments=(("effect", effect.value),),
        )
        assert codec.decode(codec.encode(action), actor=3) == action


def test_corrinth_city_staged_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    # Stage B3a: each stage is an effect row (the Agent box of Corrinth
    # City: discard, then pay) and the chosen card as its target row.
    discard = DomainAction(
        action_id="select_corrinth_city_discard",
        actor=0,
        arguments=(("card_id", "imperium:spacing_guild_s_favor:0"),),
    )
    pay = DomainAction(
        action_id="pay_corrinth_city",
        actor=0,
        arguments=(("card_id", "player:0:starter:dagger:0"),),
    )

    discard_rows = _round_trip_steps(codec, discard, "corrinth_city")
    pay_rows = _round_trip_steps(codec, pay, "corrinth_city")
    target = "choose_personal_card"
    assert [row.action_id for row in discard_rows] == ["discard", target]
    assert [row.action_id for row in pay_rows] == ["pay", target]


def test_agent_card_spice_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(action_id="pay_agent_card_spice", actor=0)

    # Stage B3a: a payment without a target is one ``pay`` effect row.
    (row,) = _round_trip_steps(codec, action, "junction_headquarters")
    assert row.action_id == "pay"


def test_desert_power_reveal_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig())
    actions = (
        DomainAction(action_id="decline_reveal_sandworm", actor=0),
        DomainAction(action_id="pay_reveal_water_for_sandworm", actor=2),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=action.actor) == action


def test_long_live_the_fighters_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig())
    actions = (
        DomainAction(
            action_id="select_long_live_fighters_draw",
            actor=0,
            arguments=(("card_id", "player:0:starter:dagger:0"),),
        ),
        DomainAction(
            action_id="select_long_live_fighters_discard",
            actor=2,
            arguments=(("card_id", "imperium:sardaukar_soldier:0"),),
        ),
    )

    for action in actions:
        assert codec.decode(codec.encode(action), actor=action.actor) == action


def test_subversive_advisor_agent_turn_round_trips() -> None:
    # Stage B1: the Agent turn is a card pick, then a space pick.
    codec = ActionCodec(RulesetConfig())
    pick = DomainAction(
        action_id="choose_agent_card",
        actor=0,
        arguments=(("card_id", "imperium:subversive_advisor:0"),),
    )
    space = DomainAction(
        action_id="place_agent",
        actor=0,
        arguments=(("space_id", "dutiful_service"),),
    )

    for action in (pick, space):
        assert codec.decode(codec.encode(action), actor=0) == action


def test_agent_card_solari_acquisition_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="acquire_imperium_with_solari",
        actor=0,
        arguments=(("instance_id", "imperium:sardaukar_soldier:0"),),
    )

    # Stage B3a: the ``acquire`` effect row, then the card as its target.
    rows = _round_trip_steps(codec, action, "price_is_no_object")
    assert [row.action_id for row in rows] == ["acquire", "choose_imperium_card"]


def test_reveal_influence_exchange_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="exchange_reveal_influence",
        actor=0,
        arguments=(
            ("alliance_recipient", 2),
            ("gained_faction", "emperor"),
            ("lost_faction", "emperor"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_reveal_spice_influence_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="pay_reveal_spice_influence",
        actor=0,
        arguments=(("faction", "spacing_guild"),),
    )

    assert codec.decode(codec.encode(action), actor=0) == action


def test_agent_card_spy_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="place_agent_card_spy",
        actor=1,
        arguments=(("post_id", "bene-gesserit-espionage-secrets"),),
    )

    # Stage B3a: the ``place_spy`` effect row, then the post as its target.
    rows = _round_trip_steps(codec, action, "bene_gesserit_operative")
    assert [row.action_id for row in rows] == ["place_spy", "choose_post"]


def test_agent_card_influence_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="choose_agent_card_influence",
        actor=2,
        arguments=(("faction", "fremen"),),
    )

    # Stage B3a: the ``gain_influence`` effect row, then the Faction as its
    # target.
    rows = _round_trip_steps(codec, action, "public_spectacle")
    assert [row.action_id for row in rows] == ["gain_influence", "choose_faction"]


def test_reveal_spy_placement_choice_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="place_reveal_spy",
        actor=3,
        arguments=(("post_id", "emperor-sardaukar-dutiful-service"),),
    )

    assert codec.decode(codec.encode(action), actor=3) == action


def test_starting_card_actions_share_an_index_between_players() -> None:
    codec = ActionCodec(RulesetConfig())
    first = DomainAction(
        action_id="choose_agent_card",
        actor=0,
        arguments=(("card_id", "player:0:starter:dagger:0"),),
    )
    second = DomainAction(
        action_id="choose_agent_card",
        actor=3,
        arguments=(("card_id", "player:3:starter:dagger:0"),),
    )

    assert codec.encode(first) == codec.encode(second)
    assert codec.decode(codec.encode(first), actor=3) == second


def test_infiltrate_agent_action_round_trips_with_selected_spy() -> None:
    codec = ActionCodec(RulesetConfig())
    # The selected Spy belongs to the space pick (stage B1).
    action = DomainAction(
        action_id="place_agent",
        actor=2,
        arguments=(
            (
                "infiltrate_post_id",
                "landsraad-assembly-hall-gather-support",
            ),
            ("space_id", "assembly_hall"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=2) == action


def test_reserve_agent_action_round_trips_without_actor_rewriting() -> None:
    codec = ActionCodec(RulesetConfig())
    pick = DomainAction(
        action_id="choose_agent_card",
        actor=2,
        arguments=(("card_id", "reserve:prepare_the_way:7"),),
    )
    space = DomainAction(
        action_id="place_agent",
        actor=2,
        arguments=(("space_id", "assembly_hall"),),
    )

    for action in (pick, space):
        assert codec.decode(codec.encode(action), actor=2) == action


def test_imperium_agent_action_round_trips_with_stable_instance_id() -> None:
    codec = ActionCodec(RulesetConfig())
    pick = DomainAction(
        action_id="choose_agent_card",
        actor=2,
        arguments=(("card_id", "imperium:maula_pistol:0"),),
    )
    space = DomainAction(
        action_id="place_agent",
        actor=2,
        arguments=(("space_id", "arrakeen"),),
    )

    for action in (pick, space):
        assert codec.decode(codec.encode(action), actor=2) == action


def test_agent_card_trash_round_trips_with_actor_owned_starting_card() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="trash_agent_card",
        actor=2,
        arguments=(("card_id", "player:2:starter:dagger:0"),),
    )

    # Stage B3a: the ``trash`` effect row, then the card as the
    # ``choose_personal_card`` target row, which carries the starting-card
    # normalization (the actor's own starting card shares one index).
    rows = _round_trip_steps(codec, action, "branching_path")
    assert [row.action_id for row in rows] == ["trash", "choose_personal_card"]
    other = DomainAction(
        action_id="choose_personal_card",
        actor=0,
        arguments=(("card_id", "player:0:starter:dagger:0"),),
    )
    assert codec.encode(rows[1]) == codec.encode(other)


def test_endgame_wild_match_round_trips_with_both_card_ids() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="match_endgame_wild_icon",
        actor=1,
        arguments=(
            ("matching_card_id", "objective_crysknife_1"),
            ("wild_card_id", "propaganda"),
        ),
    )

    assert codec.decode(codec.encode(action), actor=1) == action


def test_every_action_in_seeded_round_round_trips_through_codec() -> None:
    codec = ActionCodec(RulesetConfig())
    result = run_random_round(
        UprisingRulesEngine(),
        RulesetConfig(),
        game_seed=4,
        policy_seed=4004,
    )

    for step in result.replay.steps:
        if isinstance(step, DomainAction):
            assert codec.decode(codec.encode(step), step.actor) == step


def test_legal_action_mask_marks_exactly_the_supplied_actions() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), seed=2)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    player = decision.owner
    legal_actions = engine.legal_actions(state, player)
    codec = ActionCodec(state.config)

    mask = codec.legal_action_mask(legal_actions)
    enabled = tuple(index for index, value in enumerate(mask) if value)

    assert len(mask) == codec.size
    assert len(enabled) == len(legal_actions)
    assert {codec.decode(index, player) for index in enabled} == set(legal_actions)


def test_leader_draft_picks_round_trip_in_both_catalogs() -> None:
    base = ActionCodec(RulesetConfig())
    choam = ActionCodec(RulesetConfig(choam_module=True))
    pick = DomainAction(
        action_id="pick_leader",
        actor=1,
        arguments=(("leader_id", "staban_tuek"),),
    )
    shaddam = DomainAction(
        action_id="pick_leader",
        actor=1,
        arguments=(("leader_id", "shaddam_corrino_iv"),),
    )

    assert base.decode(base.encode(pick), actor=1) == pick
    assert choam.decode(choam.encode(shaddam), actor=1) == shaddam
    try:
        base.encode(shaddam)
    except ValueError as error:
        assert "not present" in str(error)
    else:
        raise AssertionError("the base catalog accepted a CHOAM-only Leader")


def test_leader_draft_reset_masks_exactly_the_pool_picks() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig(leader_draft=True)
    state = engine.reset(config, 21)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    codec = ActionCodec(config)

    legal_actions = engine.legal_actions(state, decision.owner)
    mask = codec.legal_action_mask(legal_actions)
    enabled = tuple(index for index, value in enumerate(mask) if value)

    assert len(enabled) == 6
    assert {codec.decode(index, decision.owner) for index in enabled} == set(
        legal_actions
    )


def test_fedaykin_maneuver_retreats_encode_up_to_troops_plus_commanders() -> None:
    # v105: Chani's Fedaykin Maneuver retreats troops and Commanders together
    # (Commanders are troops [Bloodlines p. 4]; rules/leader_abilities.py
    # offers every count up to troops_conflict + commanders_conflict). The
    # Commander-share templates stopped at MAX_DEPLOYMENT_COUNT, so a
    # 12-troop Conflict with one Commander offered a count of 13 that the
    # codec could not encode; a trained policy hit it in greedy play
    # (2026-09-18). The range now matches retreat_intrigue_troops.
    codec = ActionCodec(RulesetConfig(bloodlines=True))
    fedaykin = [t for t in codec.catalog if t.action_id == "retreat_leader_troops"]
    assert len(fedaykin) == 12 + 91
    for troops in range(0, 13):
        for commanders in range(0, 8):
            for count in range(1, troops + commanders + 1):
                for share in range(0, min(count, commanders) + 1):
                    if count - share > troops:
                        continue
                    action = DomainAction(
                        "retreat_leader_troops",
                        actor=2,
                        arguments=(
                            *((("commanders", share),) if share else ()),
                            ("count", count),
                        ),
                    )
                    assert codec.decode(codec.encode(action), actor=2) == action
    beyond = DomainAction(
        "retreat_leader_troops", actor=0, arguments=(("commanders", 1), ("count", 20))
    )
    with pytest.raises(ValueError, match="not present"):
        codec.encode(beyond)


@pytest.mark.parametrize("bloodlines", [False, True])
def test_c7r3_s_owed_card_encodes_with_or_without_bloodlines(bloodlines: bool) -> None:
    # c7r3's card is owed in its owner's turn since codec v149 (cleanup-2b,
    # rule decision 5; OQ-106): an Immortality game without Bloodlines, whose
    # catalog held no ``draw_owed_card`` before, encodes it too.
    codec = ActionCodec(RulesetConfig(immortality=True, bloodlines=bloodlines))
    codec.encode(DomainAction(action_id="draw_owed_card", actor=0))
