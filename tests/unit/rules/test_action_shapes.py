"""The (shape, source) -> template table of the composed-effects engine.

docs/composed-effects-plan.md 4.3-4.4: the executor names each decision's
action through this table, and a network reads an action's verb, source and
target from it, so it must name every catalog id exactly once and agree with
the arguments the catalog gives each id.
"""

from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.rules.action_shapes import (
    ACTION_SHAPES,
    TARGET_ARGUMENTS,
    ActionShape,
    Source,
    Tag,
    Target,
    Verb,
    action_shape,
    template_id,
)
from dune_imperium.rules.effect_steps import STEP_SPECS, TARGET_SPECS

_FULL = RulesetConfig(
    choam_module=True,
    leader_draft=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
)


@cache
def _catalog_arguments() -> dict[str, frozenset[str]]:
    """Each catalog id's argument names, every option enabled, the original
    Dune: Imperium's (its own ids, plan 15.4) and the original with Rise of
    Ix (the dreadnought rows, stage P4b)."""

    names: dict[str, set[str]] = {}
    catalogs = (
        _FULL,
        RulesetConfig(base_game=BaseGame.IMPERIUM),
        RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True),
    )
    for template in (t for config in catalogs for t in ActionCodec(config).catalog):
        names.setdefault(template.action_id, set()).update(
            key for key, _ in template.arguments
        )
    return {action_id: frozenset(keys) for action_id, keys in names.items()}


# Whole ids shown only as effect and target rows (stage B3), and a window's
# own effects shown by their target rows (B3d-2a): the rules still resolve
# them by these ids, so they keep their rows, but no catalog holds them.
_STEP_ONLY = frozenset(STEP_SPECS) | frozenset(TARGET_SPECS)


@cache
def _step_row_arguments() -> dict[str, frozenset[str]]:
    """Each id's argument names over its effect rows (stage B3: a template
    with a ``printed`` argument), every option enabled."""

    names: dict[str, set[str]] = {}
    for template in ActionCodec(_FULL).catalog:
        keys = {key for key, _ in template.arguments}
        if "printed" in keys:
            names.setdefault(template.action_id, set()).update(keys)
    return {action_id: frozenset(keys) for action_id, keys in names.items()}


def _whole_arguments(action_id: str) -> frozenset[str]:
    """The argument names of ``action_id``'s templates that are no effect
    rows (a legacy id an effect row shares)."""

    return frozenset().union(
        *(
            {key for key, _ in template.arguments}
            for template in ActionCodec(_FULL).catalog
            if template.action_id == action_id
            and "printed" not in dict(template.arguments)
        )
    )


def test_every_catalog_id_has_exactly_one_row() -> None:
    catalog = set(_catalog_arguments())
    assert set(ACTION_SHAPES) - catalog == _STEP_ONLY - catalog, (
        "rows for ids no catalog has"
    )
    assert catalog - set(ACTION_SHAPES) == set(), "catalog ids with no row"


def test_the_base_catalog_needs_no_further_row() -> None:
    base = {template.action_id for template in ActionCodec(RulesetConfig()).catalog}
    assert base <= set(ACTION_SHAPES)


def test_each_row_tags_what_the_catalog_tags() -> None:
    effect_rows = _step_row_arguments()
    for action_id, arguments in _catalog_arguments().items():
        shape = ACTION_SHAPES[action_id]
        if shape.source is Source.REF and action_id in effect_rows:
            # An effect row names its source by the ``source`` tag and may
            # carry a grafted turn's ``box`` beside it (stage B3).
            assert shape.tag is Tag.SOURCE, action_id
            assert Tag.SOURCE.value in effect_rows[action_id], action_id
            continue
        if action_id in effect_rows:
            # A legacy id an effect row shares (``lose_unit``): its other
            # templates follow the row.
            arguments = _whole_arguments(action_id)
        tags = {tag for tag in Tag if tag.value in arguments}
        assert len(tags) <= 1, action_id
        assert shape.tag == (tags.pop() if tags else None), action_id


def test_each_row_target_covers_its_arguments() -> None:
    effect_rows = _step_row_arguments()
    for action_id, arguments in _catalog_arguments().items():
        shape = ACTION_SHAPES[action_id]
        if action_id in effect_rows:
            # Stage B3: the effect rows point at their waiting effect.
            picked = effect_rows[action_id] - {tag.value for tag in Tag}
            assert picked <= TARGET_ARGUMENTS[Target.EFFECT], action_id
            assert "printed" in picked, action_id
            if shape.source is Source.REF or action_id in TARGET_SPECS:
                # A window's own effect (Holy War's ``lose_unit``, stage
                # B3d-2a) shares the effect row's id, but no catalog holds
                # its whole action: its target rows stand for it.
                continue
            arguments = _whole_arguments(action_id)
        picked = arguments - {tag.value for tag in Tag}
        allowed = TARGET_ARGUMENTS[shape.target]
        assert picked <= allowed, (action_id, sorted(picked - allowed))
        if shape.target is not Target.NONE:
            assert picked, f"{action_id} picks a {shape.target} with no argument"


def test_every_row_is_named_by_its_own_shape() -> None:
    for action_id, shape in ACTION_SHAPES.items():
        for verb in (shape.verb, *shape.also):
            named = template_id(
                verb, shape.source, shape.target, of=shape.of, variant=shape.variant
            )
            assert named == action_id


def test_one_trash_verb_spans_its_sources() -> None:
    """Plan 4.4: ``trash_agent_card`` and ``trash_reveal_card`` share the verb."""

    trashes = {
        shape.source
        for shape in ACTION_SHAPES.values()
        if shape.verb is Verb.TRASH and shape.target is Target.PERSONAL_CARD
        and not shape.variant
    }
    assert {
        Source.AGENT_CARD,
        Source.REVEAL_CARD,
        Source.INTRIGUE,
        Source.LEADER,
        Source.CONFLICT,
        Source.BOARD_SPACE,
        Source.SCOUTS,
    } <= trashes
    agent, reveal = action_shape("trash_agent_card"), action_shape("trash_reveal_card")
    assert agent.verb is reveal.verb


def test_template_lookup_by_shape_and_source() -> None:
    assert (
        template_id(Verb.TRASH, Source.INTRIGUE, Target.PERSONAL_CARD)
        == "trash_intrigue_card"
    )
    assert (
        template_id(Verb.TRASH, Source.INTRIGUE, Target.INTRIGUE_CARD)
        == "trash_intrigue_hand_card"
    )
    assert template_id(Verb.DECLINE, Source.INTRIGUE, of=Verb.TRASH) == (
        "decline_intrigue_trash"
    )
    # One Intrigue id answers both Influence verbs.
    lose = template_id(Verb.LOSE_INFLUENCE, Source.INTRIGUE)
    assert lose == "choose_intrigue_faction"
    assert template_id(Verb.GAIN_INFLUENCE, Source.INTRIGUE, Target.FACTION) == (
        "choose_intrigue_faction"
    )
    assert template_id(Verb.PLACE_SPY, Source.REVEAL_CARD) == "place_reveal_spy"


def test_an_ambiguous_or_missing_shape_is_refused() -> None:
    with pytest.raises(LookupError, match="2 templates"):
        # A personal card and an Intrigue card: the target must be named.
        template_id(Verb.TRASH, Source.INTRIGUE)
    with pytest.raises(LookupError, match="0 templates"):
        template_id(Verb.SUMMON_SANDWORM, Source.INTRIGUE)


def test_only_refusals_and_empty_confirmations_answer_a_verb() -> None:
    with pytest.raises(ValueError, match="only a refusal"):
        ActionShape(Verb.PAY, Source.CONFLICT, of=Verb.PAY)
    for shape in ACTION_SHAPES.values():
        # The effect rows ``decline`` and ``confirm_empty`` (stage B3d-3) name
        # the effect they answer in their own ``of`` argument instead.
        if shape.verb is Verb.CONFIRM_EMPTY and shape.source is not Source.REF:
            assert shape.of is not None


def test_every_verb_source_and_target_names_some_row() -> None:
    shapes = ACTION_SHAPES.values()
    verbs = {verb for shape in shapes for verb in (shape.verb, *shape.also)}
    verbs |= {shape.of for shape in shapes if shape.of is not None}
    assert set(Verb) == verbs
    assert set(Source) == {shape.source for shape in shapes}
    assert set(Target) == {shape.target for shape in shapes}
