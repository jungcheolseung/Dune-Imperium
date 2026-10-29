"""The windows that answer P4's Imperium batch d (plan §13): Imperial Bashar's
-OR- box, Satellite Ban's and Spice Trader's discards and Satellite Ban's
Reveal retreat, on hand-built rows (the engine rows are P4's
``claude/p4d-imperium-b``)."""

from collections.abc import Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.ix_imperium import (
    SatelliteBanRevealAbility,
)
from dune_imperium.agents.app_ai.abilities.original_imperium import ScoutAbility
from dune_imperium.agents.app_ai.catalog import card_entity
from dune_imperium.agents.app_ai.entities import Entity
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import agent_effects, reveal
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
TROOP = DomainAction(action_id="resolve_agent_card_effect", actor=0)
TRASH = tuple(
    DomainAction(action_id="trash_agent_card", actor=0, arguments=(("card_id", c),))
    for c in ("player:0:starter:dagger:0", "imperium:imperial_bashar:0")
)


def _turn(short: str, rows: Sequence[DomainAction]) -> agent_effects._Turn:
    p = make_profile(first_decision("turn", config=IX))
    run = DecisionRun(p.ctx, p, tuple(rows), p.rng, Memory())
    card = card_entity(f"imperium:{short}:0", p.ctx.seat)
    return agent_effects._Turn(
        run=run,
        context={},
        card_ref=card.ref,
        card_short=short,
        card=card,
        space_id=None,
        space=None,
        leader=None,
    )


def _bashar_answer(
    monkeypatch: pytest.MonkeyPatch,
    rows: Sequence[DomainAction],
    troop: float,
    trash: float | None,
) -> DomainAction | None:
    t = _turn("imperial_bashar", rows)

    def card_to_trash(
        cards: Sequence[Entity], minimum: float
    ) -> tuple[Entity | None, float]:
        return (cards[0], trash) if trash is not None and cards else (None, 0.0)

    monkeypatch.setattr(t.p, "troop_value", lambda n, include=False: troop)
    monkeypatch.setattr(t.p, "trash_card_value", lambda: 0.0)
    monkeypatch.setattr(t.p, "card_to_trash", card_to_trash)
    agent_effects._ix_card_rows(t)
    [source] = t.sources
    assert source.label == "imperial_bashar box" and not t.unmapped
    assert source.evaluate is not None
    _value, action = source.evaluate()
    return action


def test_imperial_bashar_takes_the_troop_or_the_trash_its_ability_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ImperialBasharAgentAbility::Evaluate``: option 0 at the troop value,
    then option 1 with ``GetCardToTrash``'s card when strictly greater."""

    rows = (TROOP, *TRASH)
    assert _bashar_answer(monkeypatch, rows, 1.0, 0.5) is TROOP
    assert _bashar_answer(monkeypatch, rows, 1.0, 2.0) is TRASH[0]


def test_imperial_bashar_uses_its_key_on_nothing_without_a_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Option 1 alone at 0.5 (no card to trash), or the troop with no troop
    row (none can join): the box lapses unused."""

    assert _bashar_answer(monkeypatch, (TROOP, *TRASH), -1.0, None) is None
    assert _bashar_answer(monkeypatch, TRASH, 1.0, 0.5) is None


def test_the_bashar_rows_are_not_also_a_plain_box_or_trash() -> None:
    t = _turn("imperial_bashar", (TROOP, *TRASH))
    agent_effects._single_box(t, TROOP)
    agent_effects._card_trash(t, "imperial_bashar")
    assert not t.sources and not t.unmapped


@pytest.mark.parametrize(
    ("short", "label"),
    [
        ("satellite_ban", "satellite_ban discard"),
        ("spice_trader", "spice_trader discard"),
    ],
)
def test_satellite_ban_and_spice_trader_discard_through_their_ability(
    short: str, label: str
) -> None:
    rows = tuple(
        DomainAction(
            action_id="discard_agent_card", actor=0, arguments=(("card_id", c),)
        )
        for c in ("player:0:starter:dagger:0", "player:0:starter:dagger:1")
    )
    t = _turn(short, rows)
    agent_effects._card_discard(t, short)
    assert [s.label for s in t.sources] == [label] and not t.unmapped


def test_a_retreat_up_to_two_takes_the_cards_own_class() -> None:
    """Scout's ``ScoutAbility`` and Satellite Ban's
    ``SatelliteBanRevealAbility`` share the effect (both
    ``OptionalRetreatAbility``, MaxRetreat 2)."""

    p = make_profile(first_decision("turn", config=IX))
    run = DecisionRun(p.ctx, p, (), p.rng, Memory())
    effect = "may_retreat_up_to_two_troops"
    ban = reveal._choice_ability(run, effect, "imperium:satellite_ban:0")
    scout = reveal._choice_ability(run, effect, "imperium:scout:0")
    assert type(ban) is SatelliteBanRevealAbility
    assert type(scout) is ScoutAbility
