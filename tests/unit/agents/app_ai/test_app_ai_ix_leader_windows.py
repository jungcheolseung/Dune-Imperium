"""The windows that answer the Rise of Ix Leaders' decisions (plan §13):
the Signets (``agent_effects._IX_SIGNETS``), Armand's Coordination in the
Reveal, Ilesa's Round Start set-aside and Hundro's Intelligence peek."""

from collections.abc import Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import Answer
from dune_imperium.agents.app_ai.abilities.ix_leaders import (
    ConscriptAbility,
    CoordinationAbility,
    OneStepAheadRoundAbility,
)
from dune_imperium.agents.app_ai.catalog import leader_entity
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import agent_effects, immortality, ix, reveal
from dune_imperium.agents.app_ai.windows.common import Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)


def _run(rows: Sequence[DomainAction]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=IX))
    return DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())


def _row(action_id: str, **args: object) -> DomainAction:
    return DomainAction(action_id=action_id, actor=0, arguments=tuple(args.items()))  # type: ignore[arg-type]


def test_the_destination_answer_takes_the_deck_only_when_offered() -> None:
    """``GuildContactsAbility``'s ``<Targets>d__8`` lists "deck" only when
    ``GetAcquireArchIDAndPickerKind`` allows it, then "discard": option 0
    is the deck when our engine offers the ``to_deck_top`` variant."""

    plain = _row("acquire_leader_reserve", card_id="foldspace_card")
    top = _row("acquire_leader_reserve", card_id="foldspace_card", to_deck_top=True)
    assert agent_effects._deck_top_variant((plain, top), 0) is top
    assert agent_effects._deck_top_variant((plain, top), 1) is plain
    assert agent_effects._deck_top_variant((plain,), 0) is plain


def test_conscript_buys_the_card_and_destination_its_ability_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = (
        _row("acquire_leader_imperium", instance_id="imperium:scout:0"),
        _row(
            "acquire_leader_imperium", instance_id="imperium:scout:0", to_deck_top=True
        ),
        _row("acquire_leader_reserve", card_id="arrakis_liaison"),
        _row("acquire_leader_reserve", card_id="arrakis_liaison", to_deck_top=True),
    )
    run = _run(rows)
    leader = leader_entity("archduke_armand_ecaz")
    t = agent_effects._Turn(
        run=run,
        context={},
        card_ref=None,
        card_short=None,
        card=None,
        space_id=None,
        space=None,
        leader=leader,
    )
    answers = iter(
        (
            Answer(3.0, (("reserve:arrakis_liaison",), (0,)), ""),
            Answer(2.0, (("imperium:scout:0",), (1,)), ""),
        )
    )
    monkeypatch.setattr(
        ConscriptAbility, "evaluate", lambda self, p, request: next(answers)
    )
    agent_effects._conscript(t)
    [source] = t.sources
    assert source.evaluate is not None
    assert source.evaluate() == (3.0, rows[3])
    assert source.evaluate() == (2.0, rows[0])


def test_coordination_trashes_the_card_its_ability_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = tuple(
        _row("trash_leader_reveal_card", card_id=c)
        for c in ("player:0:starter:dagger:0", "imperium:scout:0")
    )
    run = _run(rows)
    answers = iter((Answer(2.5, (("imperium:scout:0",),), ""), Answer(1.0, ((),), "")))
    monkeypatch.setattr(
        CoordinationAbility, "evaluate", lambda self, p, request: next(answers)
    )
    ability = CoordinationAbility(leader_entity("archduke_armand_ecaz"))
    source = reveal._coordination_source(run, ability, rows)
    assert source.evaluate is not None
    assert source.evaluate() == (2.5, rows[1])
    assert source.evaluate() == (1.0, None)  # "trash nothing": no candidate


def test_ilesa_sets_aside_the_card_one_step_ahead_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai.testing import with_player

    state = first_decision("turn", config=IX)
    seat = make_profile(state).ctx.seat
    state = with_player(
        state, seat, leader_id="ilesa_ecaz", leader_face_id="ilesa_ecaz"
    )
    p = make_profile(state, seat)
    rows = tuple(
        DomainAction(
            action_id="set_aside_leader_card", actor=seat, arguments=(("card_id", c),)
        )
        for c in (f"player:{seat}:starter:dagger:0", f"player:{seat}:starter:dagger:1")
    )
    run = DecisionRun(p.ctx, p, rows, p.rng, Memory())
    monkeypatch.setattr(
        OneStepAheadRoundAbility,
        "evaluate",
        lambda self, prof, request: Answer(100.0, ((rows[1].arguments[0][1],),), ""),
    )
    assert ix.round_start_set_aside(run) is rows[1]


def test_hundro_keeps_the_higher_rated_intrigue_at_the_game_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``IntelligenceAbility::EvaluateIntrigue``: each card at its
    ``Rating``; Imperium Ceremony's peek keeps its own evaluator."""

    from dune_imperium.agents.app_ai.catalog import intrigue_entity

    refs = ("intrigue:bribery:0", "intrigue:dispatch_an_envoy:0")
    rows = tuple(_row("keep_peeked_intrigue", instance_id=r) for r in refs)
    run = _run(rows)
    ratings = [intrigue_entity(r, run.ctx.seat).int_attr("Rating") for r in refs]
    monkeypatch.setattr(
        AppContext,
        "top_frame_context",
        property(lambda self: {"source": f"setup:intelligence:{self.seat}"}),
    )
    kept = immortality.intrigue_peek(run)
    best = 0 if ratings[0] >= ratings[1] else 1
    assert kept is rows[best]


def test_quid_pro_quo_influence_rows_follow_the_board_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OQ-153 gives one ``resolve_effect_influence`` row per Faction; the
    app's ``QuidProQuoAbility`` gains them as it runs, in
    ``GetAgentSpaceFactions``' board order."""

    from dune_imperium.agents.app_ai.abilities import ix_intrigue

    rows = tuple(
        _row("resolve_effect_influence", faction=f) for f in ("emperor", "fremen")
    )
    run = _run(rows)
    monkeypatch.setattr(
        ix_intrigue, "_agent_space_factions", lambda p: ["fremen", "emperor"]
    )
    assert ix.take_effect_influence(run) is rows[1]
    monkeypatch.setattr(ix_intrigue, "_agent_space_factions", lambda p: [])
    assert ix.take_effect_influence(run) is rows[0]


def _tessia_run(rows: Sequence[DomainAction]) -> DecisionRun:
    from dune_imperium.agents.app_ai.testing import with_player

    state = first_decision("turn", config=IX)
    seat = make_profile(state).ctx.seat
    state = with_player(
        state, seat, leader_id="tessia_vernius", leader_face_id="tessia_vernius"
    )
    p = make_profile(state, seat)
    return DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())


def test_the_snooper_discard_takes_the_card_or_the_windows_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Careful Observation's reward (1): ``GetDiscardOrder``'s first card;
    "discard nothing" is no candidate in her turn (no refusal row) and the
    ``OPTIONAL_DISCARD`` window's refusal outside it."""

    from dune_imperium.agents.app_ai.abilities.ix_leaders import (
        CarefulObservationFactionAbility,
    )

    discards = tuple(
        _row("discard_snooper_card", card_id=c)
        for c in ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    )
    decline = _row("decline_snooper_discard")
    answers = iter(
        (
            Answer(1.0, (("player:0:starter:dagger:1",),), ""),
            Answer(1.0, ((),), ""),
            Answer(1.0, ((),), ""),
        )
    )
    monkeypatch.setattr(
        CarefulObservationFactionAbility,
        "evaluate",
        lambda self, p, request: next(answers),
    )
    [own] = ix.snooper_sources(_tessia_run(discards))
    assert own.evaluate is not None
    assert own.evaluate() == (1.0, discards[1])
    assert own.evaluate() == (1.0, None)
    assert ix.optional_discard(_tessia_run((*discards, decline))) is decline


def test_duplicity_loses_then_gains_the_tracks_of_its_one_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DuplicityAbility``: one prompt answered ``((lose,), (gain,))``; our
    loss row takes the first, the gain row asked after it the second."""

    from dune_imperium.agents.app_ai.abilities.ix_leaders import DuplicityAbility

    losses = tuple(
        _row("lose_leader_influence", faction=f) for f in ("emperor", "fremen")
    )
    run = _tessia_run(losses)
    leader = leader_entity("tessia_vernius")
    monkeypatch.setattr(
        DuplicityAbility,
        "evaluate",
        lambda self, p, request: Answer(2.0, (("fremen",), ("emperor",)), ""),
    )

    def turn(r: DecisionRun) -> agent_effects._Turn:
        return agent_effects._Turn(
            run=r,
            context={},
            card_ref=None,
            card_short=None,
            card=None,
            space_id=None,
            space=None,
            leader=leader,
        )

    first = turn(run)
    agent_effects._duplicity(first)
    [source] = first.sources
    assert source.evaluate is not None
    assert source.evaluate() == (2.0, losses[1])
    gains = tuple(
        _row("choose_leader_signet_influence", faction=f)
        for f in ("emperor", "spacing_guild")
    )
    second = turn(DecisionRun(run.ctx, run.profile, gains, run.rng, run.memory))
    agent_effects._duplicity(second)
    [gain] = second.sources
    assert gain.actions == (gains[0],) and gain.stage < Stage.PROMPT
