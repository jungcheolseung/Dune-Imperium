"""Tests for the fixed integer Uprising action codec."""

from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ACTION_CODEC_VERSION, ActionCodec
from dune_imperium.adapters.action_codec import (
    ActionTemplate,
    _scouts_templates,
    catalog_spaces,
)
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS,
    EVENTS,
    SALES,
    missions_for,
    scouts_pool,
)
from dune_imperium.content.uprising.types import (
    IMPERIUM_REVEAL_CHOICE_EFFECTS,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import DomainAction, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effects import AUTOMATIC_AGENT_ICONS
from dune_imperium.rules.board_effects import (
    AUTOMATIC_BOARD_ICONS,
    IMPERIUM_ONLY_BOARD_ICONS,
)
from dune_imperium.rules.effect_steps import (
    STEP_SPECS,
    TARGET_SPECS,
    steps_for,
)
from dune_imperium.rules.scouts_effects import scouts_spy_items, scouts_trash_items
from dune_imperium.rules.scouts_missions import mission_takes_supply_troops
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
    # Political Equilibrium with every track at 0 (codec v152, OQ-131).
    "resolve_scouts_loss_without_influence",
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

    # v152 (engine audit 2026-10-22, P4): Interstellar Conspiracy's spice icon
    # rows (box 0 and box 1) join the Immortality catalogs, 4,311 to 4,313
    # with every option on; the base catalog keeps its 1,434. v153 (general
    # rules audit 2026-10-25) adds no template. v154 (OQ-121): Planetary
    # Array's reward-window row and its step row join the Tech catalogs only.
    # v155 (OQ-138): Covert Operation's confirm of an empty hand joins every
    # catalog (its ``confirm_empty`` row; Ghola's too with Immortality, 4,336
    # to 4,338 with every option on). v156 (base game P3): the original
    # game's cards add templates to its own catalogs only; every Uprising
    # catalog stays as it was. v157 (base game P4): Rise of Ix on the
    # original game adds templates to the original game's Rise of Ix
    # catalogs only; every catalog without Rise of Ix stays as it was.
    assert ACTION_CODEC_VERSION == 157
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
        # v150 (stage B3c-1): a card is played effect first on every frame
        # that offers a play: the play_intrigue and wild-match whole
        # templates leave (73), the window's play rows, the Endgame match
        # row and the target rows not yet in the catalog (the Conflict and
        # Objective cards, two more options) join (26).
        - 73
        + 26
        # v150 (stage B3d-1): the windows that offer several effects at once
        # (a Conflict or Contract reward's icons, an Intrigue card's lines,
        # Servo-Receivers' Signet, a research pair, a Tech tile's acquire
        # icons) offer effect rows: their whole templates leave (228; the
        # Signet frame's were the last holders of the leader rows' wholes)
        # and the effect rows not yet in the catalog join (68).
        - 228
        + 68
        # v150 (stage B3d-2a, D-1 (가)): a window opened for one effect
        # offers its own effect by its target rows, so its whole templates
        # leave (1,466: the per-card, per-post, per-Contract and per-leader
        # window rows, and the Reveal choices a frame no longer offers
        # whole); the target rows not yet in the catalog (a count of
        # troops, a leader) and the effect rows beside a window's own (a
        # recall first by what opened the window, an Intrigue card's
        # rewards, a control defense, a reward's payment) join (54).
        - 1466
        + 54
        # v150 (stage B3d-3): every refusal and empty confirmation is one of
        # two effect rows (``decline`` or ``confirm_empty``, naming the
        # effect answered and its place): the refusals' whole templates
        # leave (37; four of them the dead ``decline_reveal_*`` ids no
        # handler answered) and the rows that stand for them join (100).
        - 37
        + 100
        # v150 (stage B3d-4, D-3): the turn's owed Intrigue draw and Emperor
        # track Spy are effect rows naming what earned them, so their bare
        # templates leave (2) and the rows the base game may name join (4:
        # the Bene Gesserit track's 4, Overthrow's acquire box, Sardaukar
        # Soldier's "when trashed", the Emperor track's Spy).
        - 2
        + 4
        # v150 (stage B3e-1): a Reveal gain by the entity that printed it.
        # The seven Reveal gain ids' whole templates leave (13: troops,
        # Intrigue, seven resource bundles and four Faction Influences, one
        # each per kind) and the rows naming their printers join (16: the
        # base cards' troops, Intrigue, resources and Faction Influence). A
        # research icon and a triggered draw are rows the catalog already
        # held.
        - 13
        + 16
        # v154 (OQ-113 (C)): Manipulate's set-aside with an empty Imperium Row
        # is confirmed by a row of its own (skip_intrigue_set_aside).
        + 1
        # v155 (OQ-138): Covert Operation's confirm of an empty hand
        # (resolve_opponent_discard_without_card).
        + 1
    )
    # v143: the box 1 twins of a grafted turn join the Immortality catalogs
    # only, so the base catalog is unchanged by them. Stage B3a's net +172
    # (above) took it from 2,931 to 3,103, stage B3b-2's net -118 to 2,985,
    # stage B3c-1's net -47 to 2,938, stage B3d-1's net -160 to 2,778,
    # stage B3d-2a's net -1,412 to 1,366, stage B3d-3's net +63 to 1,429,
    # stage B3d-4's net +2 to 1,431, stage B3e-1's net +3 to 1,434, codec
    # v154's Manipulate confirmation (OQ-113 (C)) +1 to 1,435, codec v155's
    # Covert Operation confirmation (OQ-138) +1 to 1,436.
    assert first.size == 1436


def _scouts_step_rows(
    config: RulesetConfig, scouts_only: set[ActionTemplate]
) -> set[DomainAction]:
    """The rows that stand for the whole templates of the Scouts windows
    (stage B3d-2b): a window's own effect by its target rows
    (``effect_steps.TARGET_SPECS``), the High Council's subcommittee list and
    a mission's plain way in by their ``join`` effect rows, and a mission's
    other ways by ``choose_mission``. Since stage B3d-4 the specimen return
    beside a mission that takes supply troops is its ``return_specimen``
    effect row, then a count."""

    missions = missions_for(
        scouts_pool(immortality=config.immortality), choam=config.choam_module
    )
    rows: set[DomainAction] = set()
    for template in scouts_only:
        whole = DomainAction(template.action_id, 0, template.arguments)
        if template.action_id == "scouts_return_specimens":
            for mission in missions:
                if mission_takes_supply_troops(mission):
                    rows.update(steps_for(whole, mission.mission_id))
        elif template.action_id in TARGET_SPECS or template.action_id == (
            "choose_subcommittee"
        ):
            rows.update(steps_for(whole))
        elif template.action_id == "scouts_join_mission":
            if dict(template.arguments)["target"]:
                rows.update(steps_for(whole, effect_row=False))
            else:
                for mission in missions:
                    rows.update(steps_for(whole, mission.mission_id))
    return rows


def _scouts_catalog_additions(
    config: RulesetConfig, scouts_only: set[ActionTemplate]
) -> set[ActionTemplate]:
    """What a Scouts catalog holds beyond the catalog without the option.

    Stage B3a: the Agent-effect frame offers two Scouts ids only as steps
    (``scouts_collect_mission`` and ``take_desert_riding_hooks``), so their
    whole templates are not in the catalog; the rows that stand for them are
    -- the mission's ``collect`` effect row per visited space and its
    ``choose_option`` target rows, and the Maker icon's ``take`` row. Stage
    B3d-2a: a Scouts line that places a Spy opens the Spy placement window,
    whose recall first names that line's item; its optional trash window
    offers the trash by its card's target row, which every catalog holds.
    Stage B3d-2b: the ten Scouts windows are windows opened for one effect
    too, so their whole templates are not in the catalog either; the rows
    that stand for them are (``_scouts_step_rows``), but only the Scouts
    catalogs add the ones no catalog without the option holds (a
    subcommittee, a mission, a bid above the base counts, a secret pick or a
    market slot as an option, the High Council's and the missions' ``join``
    rows); a faction, a card, a post or a space is held already. Stage
    B3d-3: the Scouts refusals' whole templates are not in the catalog
    either; their ``decline`` and ``confirm_empty`` rows are
    (``_scouts_refusal_rows``).
    """

    held = set(ActionCodec(replace(config, arrakeen_scouts=False)).catalog)
    step_only = {*STEP_SPECS, *TARGET_SPECS}
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
    spy_rows = {
        ActionTemplate("recall_spy", (("printed", item), ("source", "scouts")))
        for item in scouts_spy_items()
    }
    window_rows = {
        ActionTemplate(row.action_id, row.arguments)
        for row in _scouts_step_rows(config, scouts_only)
    }
    return {
        *(t for t in scouts_only if t.action_id not in step_only),
        *collect_rows,
        *choice_rows,
        maker_row,
        *spy_rows,
        *window_rows,
        *_scouts_refusal_rows(config),
    } - held


def _scouts_refusal_rows(config: RulesetConfig) -> set[ActionTemplate]:
    """The rows that stand for the refusals and empty confirmations naming a
    Scouts item (stage B3d-3): every refusal is a ``decline`` and every
    empty confirmation a ``confirm_empty``, naming the effect answered
    (``of``) and the item that printed it. ``decline_subcommittee`` and
    ``scouts_decline_mission`` refuse a join (the High Council's list, a
    mission), ``scouts_decline_card`` an auction's acquire,
    ``resolve_scouts_choice_without_option`` an event's or sale's choice,
    ``resolve_scouts_loss_without_influence`` Political Equilibrium's loss
    (codec v152, OQ-131), the optional trash window's refusal a trash, and the
    Spy placement window's empty confirmation a Scouts line's Spy."""

    missions = missions_for(
        scouts_pool(immortality=config.immortality), choam=config.choam_module
    )

    def row(action_id: str, of: str, printed: str) -> ActionTemplate:
        return ActionTemplate(
            action_id, (("of", of), ("printed", printed), ("source", "scouts"))
        )

    return {
        row("decline", "join", "high_council"),
        *(row("decline", "join", mission.mission_id) for mission in missions),
        *(row("decline", "acquire", auction.auction_id) for auction in AUCTIONS),
        *(row("confirm_empty", "choose", event.event_id) for event in EVENTS),
        *(row("confirm_empty", "choose", sale.sale_id) for sale in SALES),
        row("confirm_empty", "lose_influence", "political_equilibrium"),
        *(row("decline", "trash", item) for item in scouts_trash_items()),
        *(row("confirm_empty", "place_spy", item) for item in scouts_spy_items()),
    }


def test_arrakeen_scouts_templates_join_only_the_scouts_catalogs() -> None:
    # Design 4.9: every Scouts template sits in one gated block, so the
    # catalogs without the option are byte for byte what they were (base
    # 4,427) and a Scouts catalog adds exactly those templates -- and, since
    # stage B3a, the effect rows that stand for the two Scouts ids the
    # Agent-effect frame offers only as steps and, since stage B3d-2b, the
    # target and effect rows that stand for the Scouts windows' whole ids.
    option_sets: tuple[dict[str, Any], ...] = (
        {},
        {
            "choam_module": True,
            "promo_cards": True,
            "bloodlines": True,
            "tech_module": True,
            "immortality": True,
        },
    )
    for options in option_sets:
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
        # Stage B3d-2b: the Scouts windows' whole templates left the catalog
        # (the specimen return's too since stage B3d-4), and their rows round
        # trip in their place.
        window_ids = {t.action_id for t in scouts_only} & {
            *TARGET_SPECS,
            "scouts_return_specimens",
        }
        assert {"scouts_bid", "scouts_secret_pick", "join_subcommittee"} <= window_ids
        assert not any(
            t.action_id in {*window_ids, "scouts_join_mission"}
            for t in with_scouts.catalog
        )
        # A bare ``choose_subcommittee`` is the High Council's list, now the
        # ``join`` effect row; the id as a row names a subcommittee.
        assert ActionTemplate("choose_subcommittee") not in with_scouts.catalog
        assert ActionTemplate(
            "join", (("printed", "high_council"), ("source", "scouts"))
        ) in set(with_scouts.catalog)
        # Stage B3d-3: so did the Scouts refusals' and empty confirmations'
        # (the optional trash window's refusal too, which the Scouts
        # catalogs once held whole beside the Bloodlines and Immortality
        # ones); their rows join instead.
        refusal_ids = {
            "decline_subcommittee",
            "scouts_decline_mission",
            "scouts_decline_card",
            "resolve_scouts_choice_without_option",
            "resolve_scouts_loss_without_influence",
        }
        assert refusal_ids <= {t.action_id for t in scouts_only}
        assert not any(
            t.action_id in {*refusal_ids, "decline_optional_trash"}
            for t in with_scouts.catalog
        )
        refusal_rows = _scouts_refusal_rows(scouts_config)
        assert refusal_rows <= set(with_scouts.catalog)
        assert {t.action_id for t in refusal_rows} == {"decline", "confirm_empty"}
        step_rows = _scouts_step_rows(scouts_config, scouts_only)
        assert step_rows
        for row in step_rows:
            # A row names its card by template id; the decoded one by the
            # seat's own instance, so compare by template.
            index = with_scouts.encode(row)
            assert with_scouts.catalog[index] == ActionTemplate(
                row.action_id, row.arguments
            )
            assert with_scouts.encode(with_scouts.decode(index, actor=0)) == index
    assert ActionCodec(RulesetConfig()).size == 1436
    base_scouts = RulesetConfig(arrakeen_scouts=True)
    assert ActionCodec(base_scouts).size == 1436 + len(
        _scouts_catalog_additions(base_scouts, set(_scouts_templates(base_scouts)))
    )


def test_scouts_specimen_return_needs_immortality_recall_conflict_always_in() -> None:
    """OQ-074, OQ-075 (D), user ruling 2026-09-29: the specimen top-up
    needs Immortality on; a ``scouts_recall_agent`` with
    ``space_id="conflict"`` (Into the Fray) is in every Scouts catalog, with
    or without Immortality."""

    from dune_imperium.content.arrakeen_scouts import MAX_SPECIMEN_TOP_UP

    plain = ActionCodec(RulesetConfig(arrakeen_scouts=True))
    immortal = ActionCodec(RulesetConfig(arrakeen_scouts=True, immortality=True))

    def side_branches(codec: ActionCodec) -> set[str]:
        return {
            str(dict(t.arguments)["printed"])
            for t in codec.catalog
            if t.action_id == "return_specimen"
            and dict(t.arguments).get("source") == "scouts"
        }

    # Stage B3d-4: no whole template is left; the top-up is a recruit step's
    # count, or beside a mission that takes supply troops its effect row.
    for codec in (plain, immortal):
        assert not any(t.action_id == "scouts_return_specimens" for t in codec.catalog)
    assert side_branches(plain) == set()
    # (The CHOAM escort's recruit needs the CHOAM module too.)
    assert side_branches(immortal) == {
        "fedaykin_assistance",
        "security_detail",
        "tleilaxu_offering",
        "weirding_warfare",
    }
    counts = {
        dict(t.arguments)["count"]
        for t in immortal.catalog
        if t.action_id == "choose_count"
    }
    assert set(range(1, MAX_SPECIMEN_TOP_UP + 1)) <= counts
    for codec in (plain, immortal):
        # Stage B3d-2b: the window offers the Agent by a ``choose_space`` row;
        # the whole template left the catalog.
        assert not any(t.action_id == "scouts_recall_agent" for t in codec.catalog)
        assert any(
            t.action_id == "choose_space"
            and dict(t.arguments)["space_id"] == "conflict"
            for t in codec.catalog
        )


def test_choam_contract_choice_round_trips_only_in_the_module_catalog() -> None:
    whole = DomainAction(
        action_id="take_contract",
        actor=2,
        arguments=(("instance_id", "contract:high_council_ii"),),
    )
    # Stage B3d-2a: the Contract market (a window opened for one effect)
    # offers the pick by its target row, ``choose_contract``; the whole
    # template left the catalog.
    (action,) = steps_for(whole, effect_row=False)
    assert action == DomainAction(
        action_id="choose_contract",
        actor=2,
        arguments=(("instance_id", "contract:high_council_ii"),),
    )
    codec = ActionCodec(RulesetConfig(choam_module=True))

    assert codec.decode(codec.encode(action), actor=2) == action
    with pytest.raises(ValueError, match="not present"):
        codec.encode(whole)
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
        # v150 (stage B3c-1): the played cards' rows (see above): 78 whole
        # templates leave and 26 rows join.
        - 78
        + 26
        # v150 (stage B3d-1): the several-effect windows' rows (see above):
        # 268 whole templates leave and 68 rows join.
        - 268
        + 68
        # v150 (stage B3d-2a): the one-effect windows' rows (see
        # test_catalog_is_fixed...): 1,577 whole templates leave (the
        # Contract picks and Spy windows' among them) and 79 rows join.
        - 1577
        + 79
        # v150 (stage B3d-3): every refusal and empty confirmation is a
        # ``decline`` or ``confirm_empty`` row (see test_catalog_is_fixed...):
        # 39 whole templates leave and 105 rows join.
        - 39
        + 105
        # v150 (stage B3d-4): the owed Intrigue draw and the Emperor track
        # Spy by their effect rows (see test_catalog_is_fixed...).
        - 2
        + 4
        # v150 (stage B3e-1): a Reveal gain by the entity that printed it
        # (see test_catalog_is_fixed...): 13 whole templates leave and 16
        # rows join (the CHOAM cards' Reveal spice is a Reveal choice's).
        - 13
        + 16
        # v154 (OQ-113 (C)): Manipulate's set-aside with an empty Imperium Row
        # is confirmed by a row of its own (skip_intrigue_set_aside).
        + 1
        # v155 (OQ-138): Covert Operation's confirm of an empty hand
        # (resolve_opponent_discard_without_card).
        + 1
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
    # Stage B3d-2a: the Contract market and the Contract trash window (windows
    # opened for one effect) offer their picks by target rows.
    (take_contract,) = steps_for(
        DomainAction(
            action_id="take_contract",
            actor=1,
            arguments=(("instance_id", "contract:bloodlines_earn_any_alliance"),),
        ),
        effect_row=False,
    )
    (trash_intrigue,) = steps_for(
        DomainAction(
            action_id="trash_intrigue_for_contract",
            actor=1,
            arguments=(("card_id", "intrigue:backed_by_choam:0"),),
        ),
        effect_row=False,
    )
    assert take_contract.action_id == "choose_contract"
    assert trash_intrigue.action_id == "choose_intrigue_card"
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
    # The Contract reward's recall from the Conflict is the same target row
    # (stage B3d-2a), so it needs only Bloodlines like the other two recalls'.
    (recall_conflict_contract,) = steps_for(
        DomainAction(action_id="recall_conflict_agent_for_contract", actor=1),
        effect_row=False,
    )
    assert recall_conflict_contract == conflict_target
    # v125 (L2): only the Bloodlines Immediate can be out of reach (OQ-059).
    # Stage B3d-3: the Contract market's empty confirmations are the
    # ``confirm_empty`` row of the market (``hold`` beside it when the icons
    # wait), and the whole templates left the catalog.
    hold_icons = DomainAction(action_id="hold_contract_icons", actor=1)
    fizzle_icons = DomainAction(
        action_id="resolve_contract_icons_without_contract", actor=1
    )
    market = (("printed", "contract_market"), ("source", "contract"))
    (hold_row,) = steps_for(hold_icons)
    (fizzle_row,) = steps_for(fizzle_icons)
    assert hold_row == DomainAction(
        "confirm_empty",
        1,
        (("of", "take"), ("option", "hold"), *market),
    )
    assert fizzle_row == DomainAction("confirm_empty", 1, (("of", "take"), *market))
    for whole in (hold_icons, fizzle_icons):
        with pytest.raises(ValueError, match="not present"):
            both.encode(whole)
    actions = (
        take_contract,
        trash_intrigue,
        *recall_conflict_privilege,
        *recall_conflict_agent_card,
        hold_row,
        fizzle_row,
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
        # v150 (stage B3c-1): the played cards' rows: 159 whole templates
        # leave (Litany Against Fear's turn-start play among them) and 29
        # rows join.
        - 159
        + 29
        # v150 (stage B3c-2b): Arrakis Planetologist's optional trash names
        # its leader (trash(source=leader, printed=liet_kynes)).
        + 1
        # v150 (stage B3d-1): the several-effect windows' rows (see
        # test_catalog_is_fixed...): 453 whole templates leave and 73 rows
        # join.
        - 453
        + 73
        # v150 (stage B3d-2a): the one-effect windows' rows (see
        # test_catalog_is_fixed...): 2,890 whole templates leave and 195
        # rows join.
        - 2890
        + 195
        # v150 (stage B3d-3): every refusal and empty confirmation is a
        # ``decline`` or ``confirm_empty`` row (see test_catalog_is_fixed...):
        # 48 whole templates leave and 164 rows join.
        - 48
        + 164
        # v150 (stage B3d-4): the owed draws, the Emperor track Spy and the
        # Sardaukar Commander recruit by their effect rows (see
        # test_catalog_is_fixed...): 4 bare templates leave and 5 rows join
        # (a Bloodlines leader's owed card is its leader's row already).
        - 4
        + 5
        # v150 (stage B3e-1): a Reveal gain by the entity that printed it
        # (see test_catalog_is_fixed...): 13 whole templates leave and 25
        # rows join (the Bloodlines cards' and Commander Skills' among them).
        - 13
        + 25
        # v154 (OQ-113 (C)): Manipulate's set-aside with an empty Imperium Row
        # is confirmed by a row of its own (skip_intrigue_set_aside), and so
        # are Twisted Controlled's look at an empty deck and Twisted Devious'
        # mandatory trash with an empty hand (Bloodlines catalogs, +2).
        + 1
        + 2
        # v155 (OQ-138): Covert Operation's confirm of an empty hand
        # (resolve_opponent_discard_without_card).
        + 1
    )

    choam_only = ActionCodec(RulesetConfig(choam_module=True))
    # The two recalls' effect rows are in every catalog; the Conflict they
    # may pick (stage B3a: the target row) needs Bloodlines. The Intrigue
    # card's target row is shared with the other windows that pick one, so the
    # CHOAM catalog holds it for the CHOAM Intrigue card (stage B3d-2a).
    recall_effect_rows = (recall_conflict_privilege[0], recall_conflict_agent_card[0])
    for action in actions:
        if action in (*recall_effect_rows, trash_intrigue):
            assert choam_only.decode(choam_only.encode(action), actor=1) == action
            continue
        with pytest.raises(ValueError, match="not present"):
            choam_only.encode(action)
    bloodlines_only = ActionCodec(RulesetConfig(bloodlines=True))
    for action in (take_contract, trash_intrigue, hold_icons):
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
    post = (("post_id", "arrakis-spice-refinery-arrakeen"),)
    place = DomainAction(action_id="place_contract_spy", actor=1, arguments=post)
    recall = DomainAction(action_id="recall_spy_for_contract", actor=1, arguments=post)
    # Stage B3d-2a: the Contract Spy window (opened for one effect) offers
    # the Spy it places by the post's target row, and recalling one first (a
    # Spy in none of the supply) by an effect row naming the Contract that
    # printed the Spy icon, then the post.
    (place_row,) = steps_for(place, effect_row=False)
    assert place_row == DomainAction("choose_post", 1, post)
    recall_effect, recall_row = _round_trip_steps(codec, recall, "contract:arrakeen_ii")
    assert recall_effect.action_id == "recall_spy"
    assert dict(recall_effect.arguments) == {
        "printed": "contract:arrakeen_ii",
        "source": "contract",
    }
    assert recall_row == place_row
    # Stage B3d-3: the refusal is the ``decline`` row of the Spy placement,
    # naming the Contract that printed the Spy icon; a revealed Contract
    # card's choices are effect rows naming the card type that printed them
    # (an effect without a target is one row).
    decline = DomainAction(action_id="decline_contract_spy", actor=1)
    keep = DomainAction(
        action_id="keep_contract_reveal_spice",
        actor=1,
        arguments=(("source", "priority_contracts"),),
    )
    trash = DomainAction(
        action_id="trash_contract_reveal_for_vp",
        actor=1,
        arguments=(("source", "priority_contracts"),),
    )
    (decline_row,) = _round_trip_steps(codec, decline, "contract:arrakeen_ii")
    assert decline_row == DomainAction(
        action_id="decline",
        actor=1,
        arguments=(
            ("of", "place_spy"),
            ("printed", "contract:arrakeen_ii"),
            ("source", "contract"),
        ),
    )
    (keep_row,) = _round_trip_steps(codec, keep)
    (trash_row,) = _round_trip_steps(codec, trash)
    assert keep_row.action_id == "keep"
    assert trash_row.action_id == "trash"
    for whole in (place, recall, decline, keep, trash):
        with pytest.raises(ValueError, match="not present"):
            codec.encode(whole)


def test_spy_recall_first_choices_round_trip_in_every_catalog() -> None:
    # A Spy icon without a Spy in supply: "you may first recall one of your
    # Spies for no effect" [Main pp. 11, 20] -- the Conflict reward and
    # Leader Spies' recall and decline templates exist in every catalog, and
    # so do the acquisition-bonus and Agent-box Spies' declines. Stage B3d-2a:
    # the Conflict reward Spy window offers the recall by an effect row naming
    # the Conflict card that printed the Spy icon, then the post.
    recall_whole = DomainAction(
        action_id="recall_spy_for_combat_reward",
        actor=2,
        arguments=(("post_id", "arrakis-deep-desert"),),
    )
    recall_first = steps_for(recall_whole, "seize_spice_refinery")
    assert [row.action_id for row in recall_first] == ["recall_spy", "choose_post"]
    # Stage B3d-3: each decline is the ``decline`` row of the Spy placement it
    # refuses (``of=place_spy``), naming the Conflict card (and its icon),
    # leader, acquired card or Agent card that printed the Spy icon.
    declines: tuple[tuple[DomainAction, str, str, dict[str, str]], ...] = (
        (
            DomainAction(action_id="decline_combat_reward_spy", actor=2),
            "seize_spice_refinery",
            "conflict",
            {"icon": "spy"},
        ),
        (
            DomainAction(action_id="decline_leader_spy_placement", actor=2),
            "feyd_rautha_harkonnen",
            "leader",
            {},
        ),
        (
            DomainAction(action_id="decline_acquisition_spy", actor=2),
            "guild_spy",
            "acquisition",
            {},
        ),
        (
            DomainAction(action_id="decline_agent_card_spy", actor=2),
            "double_agent",
            "agent_card",
            {},
        ),
    )
    decline_rows = []
    for whole, printed, source, extra in declines:
        (row,) = steps_for(whole, printed, icon=extra.get("icon"))
        assert row == DomainAction(
            action_id="decline",
            actor=2,
            arguments=tuple(
                sorted(
                    {
                        "of": "place_spy",
                        "printed": printed,
                        "source": source,
                        **extra,
                    }.items()
                )
            ),
        )
        decline_rows.append(row)
    actions = (*decline_rows, *recall_first)
    for config in (
        RulesetConfig(),
        RulesetConfig(choam_module=True),
        RulesetConfig(bloodlines=True, choam_module=True),
    ):
        codec = ActionCodec(config)
        for action in actions:
            assert codec.decode(codec.encode(action), actor=2) == action
        for whole in (recall_whole, *(decline[0] for decline in declines)):
            with pytest.raises(ValueError, match="not present"):
                codec.encode(whole)


def test_board_effect_icons_round_trip_and_the_bare_action_is_gone() -> None:
    # One template per printed automatic icon (OQ-027); the old argument-less
    # "resolve everything at once" action left the catalog with codec v86.
    assert AUTOMATIC_BOARD_ICONS == tuple(sorted(AUTOMATIC_BOARD_ICONS))
    for key in AUTOMATIC_BOARD_ICONS:
        # The original board's own icons are only in its catalog
        # (docs/base-game-and-ix-plan.md 15.4).
        codec = ActionCodec(
            RulesetConfig(base_game=BaseGame.IMPERIUM)
            if key in IMPERIUM_ONLY_BOARD_ICONS
            else RulesetConfig()
        )
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
    # single-effect boxes keep the argument-less resolution (codec v87).
    # Stage B3a shows them as effect rows naming the box's card; since stage
    # B3d-1 no frame offers the whole action, so only those rows are coded:
    # a plain ``resolve`` row and one verb row per icon (each icon on some
    # card of the expansions), each round-tripping.
    codec = ActionCodec(
        RulesetConfig(
            choam_module=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
        )
    )
    assert AUTOMATIC_AGENT_ICONS == tuple(sorted(AUTOMATIC_AGENT_ICONS))
    rows = [
        template
        for template in codec.catalog
        if ("source", "agent_card") in template.arguments
    ]
    assert any(
        t.action_id == "resolve" and "icon" not in dict(t.arguments) for t in rows
    )
    assert not any(t.action_id == "resolve_agent_card_effect" for t in codec.catalog)
    for key in AUTOMATIC_AGENT_ICONS:
        keyed = [t for t in rows if dict(t.arguments).get("icon") == key]
        assert keyed, key
        for template in keyed:
            action = DomainAction(template.action_id, 2, template.arguments)
            assert codec.decode(codec.encode(action), actor=2) == action


def test_reveal_choice_deferral_and_resumption_round_trip() -> None:
    # Free Reveal ordering [Main p. 12]: one bare deferral plus one resume
    # template per choice-effect kind (codec v88).
    # Bloodlines and Immortality choice kinds join only the option's
    # catalogs; the original game's cards' (stage P3) join its catalog later.
    codec = ActionCodec(RulesetConfig(bloodlines=True, immortality=True))
    defer = DomainAction(action_id="defer_reveal_choice", actor=3)
    assert codec.decode(codec.encode(defer), actor=3) == defer
    for effect in PersonalCardRevealChoiceEffect:
        if effect in IMPERIUM_REVEAL_CHOICE_EFFECTS:
            continue
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
    # Stage B3d-2a: the Reveal choice window (opened for one effect) offers
    # the water payment as the effect row of the card that prints it (an
    # effect without a target is one row). Stage B3d-3: the refusal is the
    # ``decline`` row of the payment it refuses, naming the same card.
    pay = DomainAction(action_id="pay_reveal_water_for_sandworm", actor=2)
    (pay_row,) = _round_trip_steps(codec, pay)
    assert pay_row == DomainAction(
        action_id="pay",
        actor=2,
        arguments=(("printed", "desert_power"), ("source", "reveal_card")),
    )
    decline = DomainAction(action_id="decline_reveal_sandworm", actor=0)
    (decline_row,) = _round_trip_steps(codec, decline)
    assert decline_row == DomainAction(
        action_id="decline",
        actor=0,
        arguments=(
            ("of", "pay"),
            ("printed", "desert_power"),
            ("source", "reveal_card"),
        ),
    )
    for whole in (pay, decline):
        with pytest.raises(ValueError, match="not present"):
            codec.encode(whole)


def test_long_live_the_fighters_choices_round_trip() -> None:
    codec = ActionCodec(RulesetConfig())
    wholes = (
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

    # Stage B3d-2a: the window (opened for one effect) offers each pick by
    # its card's target row; the whole templates left the catalog.
    for whole in wholes:
        (action,) = steps_for(whole, effect_row=False)
        assert action.action_id == "choose_personal_card"
        assert action.arguments == whole.arguments
        assert codec.decode(codec.encode(action), actor=action.actor) == action
        with pytest.raises(ValueError, match="not present"):
            codec.encode(whole)


@pytest.mark.parametrize(
    ("config", "cards"),
    [
        (RulesetConfig(), ("covert_operation",)),
        (RulesetConfig(immortality=True), ("covert_operation", "ghola")),
    ],
    ids=["base", "immortality"],
)
def test_covert_operation_s_empty_hand_confirm_round_trips(
    config: RulesetConfig, cards: tuple[str, ...]
) -> None:
    # Codec v155 (OQ-138, user ruling 2026-10-26): an opponent with an empty
    # hand confirms it discards nothing, the ``confirm_empty`` row naming the
    # card that opened the window, in every catalog; Ghola copies the box
    # with Immortality. The whole template is not in the catalog.
    from dune_imperium.rules.action_shapes import Source

    codec = ActionCodec(config)
    whole = DomainAction(action_id="resolve_opponent_discard_without_card", actor=2)
    for card in cards:
        (row,) = steps_for(whole, card, Source.AGENT_CARD)
        assert row == DomainAction(
            action_id="confirm_empty",
            actor=2,
            arguments=(("of", "discard"), ("printed", card), ("source", "agent_card")),
        )
        assert codec.decode(codec.encode(row), actor=2) == row
    with pytest.raises(ValueError, match="not present"):
        codec.encode(whole)


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

    # Stage B3d-2a: the Reveal choice window (opened for one effect) offers
    # the exchange by its target rows alone -- the Faction lost, the one
    # gained and who takes an Alliance token handed on; the Reveal frame
    # offers it effect first (the effect row names the card).
    assert [row.action_id for row in steps_for(action, effect_row=False)] == [
        "choose_faction",
        "choose_faction",
        "choose_seat",
    ]
    rows = _round_trip_steps(codec, action, "captured_mentat")
    assert [row.action_id for row in rows] == [
        "exchange_influence",
        "choose_faction",
        "choose_faction",
        "choose_seat",
    ]
    for row in steps_for(action, effect_row=False):
        assert codec.decode(codec.encode(row), actor=0) == row
    with pytest.raises(ValueError, match="not present"):
        codec.encode(action)


def test_reveal_spice_influence_payment_round_trips() -> None:
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="pay_reveal_spice_influence",
        actor=0,
        arguments=(("faction", "spacing_guild"),),
    )

    # Stage B3d-2a: the payment is the effect row of Spacing Guild's Favor,
    # then the Faction as its target row.
    rows = _round_trip_steps(codec, action, "spacing_guild_s_favor")
    assert [row.action_id for row in rows] == ["pay", "choose_faction"]
    with pytest.raises(ValueError, match="not present"):
        codec.encode(action)


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
        arguments=(
            ("post_id", "emperor-sardaukar-dutiful-service"),
            ("source", "wheels_within_wheels"),
        ),
    )

    # Stage B3d-2a: the Reveal choice window (opened for one effect) offers
    # the Spy by the post's target row; the Reveal frame offers the effect
    # row of the card that prints it first.
    (target,) = steps_for(action, effect_row=False)
    assert target == DomainAction(
        action_id="choose_post",
        actor=3,
        arguments=(("post_id", "emperor-sardaukar-dutiful-service"),),
    )
    assert codec.decode(codec.encode(target), actor=3) == target
    effect, post = _round_trip_steps(codec, action)
    assert effect.action_id == "place_spy"
    assert post == target
    with pytest.raises(ValueError, match="not present"):
        codec.encode(action)


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
    # Stage B3c-1: the match is its effect row, then the card to match, then
    # the wild card (``effect_steps.steps_for``).
    codec = ActionCodec(RulesetConfig())
    action = DomainAction(
        action_id="match_endgame_wild_icon",
        actor=1,
        arguments=(
            ("matching_card_id", "objective_crysknife_1"),
            ("wild_card_id", "propaganda"),
        ),
    )
    rows = steps_for(action)
    assert rows == (
        DomainAction("match", 1, (("printed", "wild_icon"), ("source", "endgame"))),
        DomainAction(
            "choose_conflict_card", 1, (("card_id", "objective_crysknife_1"),)
        ),
        DomainAction("choose_conflict_card", 1, (("card_id", "propaganda"),)),
    )
    for row in rows:
        assert codec.decode(codec.encode(row), actor=1) == row


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
    # Stage B3d-2a: the draft window (opened for one effect) offers a pick by
    # its leader's target row, ``choose_leader``; the whole template left the
    # catalog, and a replay records the row.
    pick = DomainAction(
        action_id="choose_leader",
        actor=1,
        arguments=(("leader_id", "staban_tuek"),),
    )
    shaddam = DomainAction(
        action_id="choose_leader",
        actor=1,
        arguments=(("leader_id", "shaddam_corrino_iv"),),
    )
    for row in (pick, shaddam):
        whole = DomainAction("pick_leader", row.actor, row.arguments)
        assert steps_for(whole, effect_row=False) == (row,)
        for codec in (base, choam):
            with pytest.raises(ValueError, match="not present"):
                codec.encode(whole)

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
    # Stage B3a shows it as Chani's ``retreat`` effect row carrying the mix;
    # since stage B3d-1 no frame offers the whole action, so the rows are
    # what is coded.
    from dune_imperium.rules.action_shapes import Source

    codec = ActionCodec(RulesetConfig(bloodlines=True))
    fedaykin = [
        t
        for t in codec.catalog
        if t.action_id == "retreat" and ("printed", "chani") in t.arguments
    ]
    assert len(fedaykin) == 12 + 91
    assert not any(t.action_id == "retreat_leader_troops" for t in codec.catalog)
    for troops in range(0, 13):
        for commanders in range(0, 8):
            for count in range(1, troops + commanders + 1):
                for share in range(0, min(count, commanders) + 1):
                    if count - share > troops:
                        continue
                    whole = DomainAction(
                        "retreat_leader_troops",
                        actor=2,
                        arguments=(
                            *((("commanders", share),) if share else ()),
                            ("count", count),
                        ),
                    )
                    (row,) = steps_for(whole, "chani", Source.LEADER)
                    assert codec.decode(codec.encode(row), actor=2) == row
    beyond = DomainAction(
        "retreat_leader_troops", actor=0, arguments=(("commanders", 1), ("count", 20))
    )
    with pytest.raises(ValueError, match="not present"):
        codec.encode(steps_for(beyond, "chani", Source.LEADER)[0])


@pytest.mark.parametrize("bloodlines", [False, True])
def test_c7r3_s_owed_card_encodes_with_or_without_bloodlines(bloodlines: bool) -> None:
    # c7r3's card is owed in its owner's turn since codec v149 (cleanup-2b,
    # rule decision 5; OQ-106): an Immortality game without Bloodlines, whose
    # catalog held no ``draw_owed_card`` before, encodes it too -- since
    # stage B3d-4 (D-3) by its effect row naming c7r3.
    from dune_imperium.rules.action_shapes import Source

    codec = ActionCodec(RulesetConfig(immortality=True, bloodlines=bloodlines))
    (row,) = steps_for(
        DomainAction(action_id="draw_owed_card", actor=0), "c7r3", Source.RESEARCH
    )
    assert codec.decode(codec.encode(row), actor=0) == row
