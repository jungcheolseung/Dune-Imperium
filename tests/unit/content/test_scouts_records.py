"""The Arrakeen Scouts items as ability records (composed A7b)."""

import pytest

from dune_imperium.content.arrakeen_scouts import abilities
from dune_imperium.content.arrakeen_scouts.abilities import SCOUTS_ABILITIES
from dune_imperium.content.arrakeen_scouts.auctions import AUCTIONS, SALES
from dune_imperium.content.arrakeen_scouts.events import EVENTS
from dune_imperium.content.arrakeen_scouts.missions import MISSIONS
from dune_imperium.content.arrakeen_scouts.subcommittees import SUBCOMMITTEES
from dune_imperium.content.arrakeen_scouts.types import EventKind
from dune_imperium.content.uprising.abilities import AbilityMark, AbilityTiming
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireReserveCardToHand,
    EffectSection,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    LoseHighestInfluence,
    PayResources,
    PaySpecimens,
    RecallOtherAgent,
    RecruitToConflict,
    TrashPersonalCard,
)
from dune_imperium.display import scouts as display_scouts
from dune_imperium.display.effect_dsl_text import cost_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import cost_text_ko, reward_text_ko


def test_every_scouts_item_has_a_record() -> None:
    ids = (
        [item.subcommittee_id for item in SUBCOMMITTEES]
        + [item.event_id for item in EVENTS]
        + [item.auction_id for item in AUCTIONS]
        + [item.sale_id for item in SALES]
        + [item.mission_id for item in MISSIONS]
    )
    assert len(ids) == len(set(ids)) == 77
    assert set(ids) == set(SCOUTS_ABILITIES)
    for record in SCOUTS_ABILITIES.values():
        assert record.timing is AbilityTiming.SCOUTS


def test_the_tables_take_their_lines_from_the_records() -> None:
    for item in SUBCOMMITTEES:
        line = SCOUTS_ABILITIES[item.subcommittee_id].sections[0]
        assert (item.option.costs, item.option.rewards) == (line.costs, line.rewards)
    for event in EVENTS:
        record = SCOUTS_ABILITIES[event.event_id]
        if event.options:
            assert len(event.options) == len(record.sections)
        elif event.secret_choices:
            assert len(event.secret_choices) == len(record.sections)
        else:
            assert not record.sections and record.hook
        if event.kind is EventKind.SHARED:
            assert record.hook
    for auction in AUCTIONS:
        record = SCOUTS_ABILITIES[auction.auction_id]
        assert tuple(line.rewards for line in record.sections) == auction.rank_rewards
    for mission in MISSIONS:
        assert SCOUTS_ABILITIES[mission.mission_id].hook


@pytest.mark.parametrize(
    ("step", "cost"),
    [
        (LoseFactionInfluence(Faction.EMPEROR), True),
        (LoseHighestInfluence(), True),
        (LoseGarrisonTroops(2), True),
        (PaySpecimens(1), True),
        (TrashPersonalCard(hand_only=True, mandatory=True), True),
        (RecallOtherAgent(), False),
        (RecruitToConflict(2), False),
        (AcquireReserveCardToHand("prepare_the_way"), False),
        (GainLowestInfluence(), False),
        (GainSpiceWithHelixBonus(), False),
    ],
)
def test_the_scouts_pieces_read_as_the_scouts_page_shows_them(
    step: object, cost: bool
) -> None:
    english = cost_text(step) if cost else reward_text(step)  # type: ignore[arg-type]
    korean = (
        cost_text_ko(step) if cost else reward_text_ko(step)  # type: ignore[arg-type]
    )
    assert english == display_scouts._step_text(step, cost=cost)
    assert korean == display_scouts._step_text_ko(step, cost=cost)


def test_a_line_may_only_take_something_away_and_auction_places_cost_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    EffectSection(rewards=(), costs=(LoseFactionInfluence(Faction.EMPEROR),))
    with pytest.raises(ValueError):
        EffectSection(rewards=())
    paid = abilities._record(
        AbilityMark.OPTIONAL,
        EffectSection(
            rewards=(GainLowestInfluence(),), costs=(PayResources(solari=1),)
        ),
    )
    monkeypatch.setattr(abilities, "SCOUTS_ABILITIES", {"auction": paid})
    with pytest.raises(ValueError):
        abilities.scouts_rank_rewards("auction")
