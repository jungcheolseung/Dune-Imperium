"""The Immortality, Epic Game Mode and Go to 11 parts of the profile port.

Specs (assets checkout, ``analysis/ai/spec/``): ``immortality.md`` §1.6 and
§2 (Errata at the end of the file override its body), and
``epic-goto11-promo-draft.md`` §2.4, §2.5, §3.4-§3.5. Each test builds a real
game state with the option on, adjusts the fields the formula reads and
stubs the other areas' methods on the ``Profile`` instance; the numbers are
the spec's (Hard level unless a test is about levels).
"""

from collections.abc import Sequence
from dataclasses import replace
from functools import cache
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import abilities as abilities_pkg
from dune_imperium.agents.app_ai import testing as _conftest
from dune_imperium.agents.app_ai.abilities.base import Ability, Pile
from dune_imperium.agents.app_ai.abilities.intrigue import IntrigueAbility
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    conflict_entity,
    space_entity,
)
from dune_imperium.agents.app_ai.context import (
    RECLAIMED_FORCES_REF,
    RESEARCH_SPACE_IDS,
    Board,
)
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile, combat, economy
from dune_imperium.agents.app_ai.profile.immortality import (
    GAIN_ANY_FACTION_INFLUENCE_CUSTOM,
    GAIN_RESEARCH_CUSTOM,
    GAIN_TLEILAXU_CUSTOM,
    PAY_SOLARI_FOR_TLEILAXU,
    RESEARCH_SPACE_DEFS,
    TRASH_CUSTOM,
    TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE,
)
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES,
    ResearchBonus,
    research_next_space_ids,
)
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState

ME = 3  # the first seat to decide in round 1 with these seeds
IMMORTALITY = RulesetConfig(immortality=True)
EPIC = RulesetConfig(epic_game=True)
GO_TO_11 = RulesetConfig(immortality=True, go_to_11=True)
EPIC_GO_TO_11 = RulesetConfig(immortality=True, go_to_11=True, epic_game=True)


# -- states ------------------------------------------------------------------------


@cache
def imm_state() -> GameState:
    """Round 1, the first Agent turn of an Immortality game (seat 3)."""

    return _conftest.first_decision("turn", config=IMMORTALITY)


@cache
def imm_reveal_state() -> GameState:
    """The first Reveal frame of an Immortality game (seat 3's own)."""

    return _conftest.first_decision("reveal", config=IMMORTALITY)


@cache
def base_state() -> GameState:
    """Round 1 of a plain Uprising game (no Immortality)."""

    return _conftest.first_decision("turn", choam=True)


@cache
def config_state(config: RulesetConfig) -> GameState:
    return _conftest.first_decision("turn", config=config)


def with_player(state: GameState, seat: int, **changes: object) -> GameState:
    return _conftest.with_player(state, seat, **changes)


def with_state(state: GameState, **changes: object) -> GameState:
    return _conftest.with_state(state, **changes)


def at_round(round_number: int, **changes: object) -> GameState:
    """The Immortality state at ``round_number`` with seat 3 changed."""

    return with_player(
        with_state(imm_state(), round_number=round_number), ME, **changes
    )


def specimens(n: int, garrison: int = 3) -> dict[str, int]:
    """Specimen fields that keep the 12-troop invariant (none in conflict)."""

    return {
        "specimens": n,
        "troops_garrison": garrison,
        "troops_conflict": 0,
        "troops_supply": 12 - garrison - n,
    }


def troops(garrison: int = 0, conflict: int = 0) -> dict[str, int]:
    return {
        "troops_garrison": garrison,
        "troops_conflict": conflict,
        "troops_supply": 12 - garrison - conflict,
    }


def imperium(name: str, copy: int = 0) -> str:
    return f"imperium:{name}:{copy}"


def tleilaxu(name: str, copy: int = 0) -> str:
    return f"tleilaxu:{name}:{copy}"


def intrigue(name: str, copy: int = 0) -> str:
    return f"intrigue:{name}:{copy}"


def card(instance_id: str) -> Entity:
    return card_entity(instance_id)


def with_row(state: GameState, *row: str) -> GameState:
    """The Tleilaxu Row holding ``row`` (taken out of the Tleilaxu deck)."""

    return with_state(
        state,
        tleilaxu_row=row,
        tleilaxu_deck=tuple(c for c in state.tleilaxu_deck if c not in row),
    )


def with_conflict(state: GameState, conflict_id: str) -> GameState:
    return with_state(
        state,
        current_conflict_ids=(conflict_id,),
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
    )


def prof(
    state: GameState, *, seat: int = ME, level: int = 2, climax: bool = False
) -> Profile:
    """A profile with the climax test pinned (it only moves the arc here)."""

    profile = _conftest.make_profile(state, seat, level=level)
    stub(profile, is_climax=climax)
    return profile


def stub(profile: Profile, **methods: object) -> Profile:
    """Replace methods on the instance; a non-callable becomes a constant."""

    for name, value in methods.items():
        if isinstance(value, Summer):
            total = value.sum
            setattr(profile, name, lambda *_a, _t=total, **_k: Summer(_t))
        elif isinstance(value, IntSummer):
            total_i = value.sum
            setattr(profile, name, lambda *_a, _t=total_i, **_k: IntSummer(_t))
        elif callable(value):
            setattr(profile, name, value)
        else:
            setattr(profile, name, lambda *_a, _v=value, **_k: _v)
    return profile


def app_mul(total: float, mod: float) -> float:
    """``AIProfileAbsUtils::Multiply @0x9cd920``: ``Sum + (mod*Sum - Sum)``."""

    return total + (mod * total - total)


# =================================================================================
# AppContext — the Immortality block (spec §1.6)
# =================================================================================


def test_context_reads_the_bene_tleilax_board_at_the_start() -> None:
    state = imm_state()
    ctx = prof(state).ctx
    assert ctx.immortality
    assert ctx.research_space_id() == "c0r3"
    assert ctx.research_rank() == 0
    assert ctx.research_next_space_ids() == ("c1r3",)
    assert ctx.genetic_markers() == 0
    assert ctx.tleilaxu_influence() == 0
    assert ctx.specimens() == 0
    assert ctx.family_atomics() is True
    assert ctx.ungained_troops() == 0
    assert ctx.ungained_specimens() == 0
    assert ctx.chairdog_return_card_ids() == ()
    assert ctx.usurped_row_card_id() == ""
    assert ctx.graft_cards() is None
    # Reclaimed Forces first, then the two dealt cards in row order.
    assert ctx.tleilaxu_row == (RECLAIMED_FORCES_REF, *state.tleilaxu_row)
    assert len(ctx.tleilaxu_row) == 3
    assert ctx.tleilaxu_deck_size == len(state.tleilaxu_deck)


@pytest.mark.parametrize(
    ("space", "rank", "markers", "following"),
    [
        ("c1r3", 1, 0, ("c2r2", "c2r4")),
        ("c3r5", 6, 0, ("c4r4", "c4r6")),
        ("c4r2", 7, 1, ("c5r1", "c5r3")),  # first marker column
        ("c7r5", 18, 1, ("c8r4", "c8r6")),
        ("c8r6", 21, 2, ()),  # the end of the track
    ],
)
def test_context_research_position(
    space: str, rank: int, markers: int, following: tuple[str, ...]
) -> None:
    state = with_player(imm_state(), 1, research_space=space, tleilaxu_space=5)
    ctx = prof(state).ctx
    assert ctx.research_rank(1) == rank
    assert ctx.genetic_markers(1) == markers
    assert ctx.research_next_space_ids(1) == following
    assert ctx.tleilaxu_influence(1) == 5
    assert ctx.research_rank() == 0  # own seat untouched


def test_context_reads_the_empty_board_without_immortality() -> None:
    ctx = prof(base_state()).ctx
    assert not ctx.immortality
    assert ctx.research_space_id() == ""
    assert ctx.research_rank() == 0
    assert ctx.research_next_space_ids() == ()
    assert ctx.genetic_markers() == 0
    assert ctx.tleilaxu_row == ()
    assert prof(base_state()).tleilaxu_row_cards() == []


def test_context_graft_cards_reads_the_own_agent_effects_frame() -> None:
    state = _conftest.first_decision("agent_effects", config=IMMORTALITY)
    frame = state.decision_stack[-1]
    assert isinstance(frame.decision, PlayerDecision)
    owner = frame.decision.owner
    context = dict(frame.context)
    assert prof(state, seat=owner).ctx.graft_cards() is None
    context["graft_card_id"] = "imperium:replacement_eyes:0"
    grafted = replace(frame, context=tuple(context.items()))
    state = with_state(state, decision_stack=(*state.decision_stack[:-1], grafted))
    assert prof(state, seat=owner).ctx.graft_cards() == (
        context["card_id"],
        "imperium:replacement_eyes:0",
    )
    # Another seat never sees the frame.
    assert prof(state, seat=(owner + 1) % 4).ctx.graft_cards() is None


def test_research_space_defs_match_our_board() -> None:
    """``get_SpaceDefs`` (spec §1.5) agrees with our transcription."""

    expected: dict[ResearchBonus, tuple[int, int, int, tuple[str, ...]]] = {
        ResearchBonus.NONE: (0, 0, 0, ()),
        ResearchBonus.SPECIMEN: (1, 0, 0, ()),
        ResearchBonus.TLEILAXU: (0, 0, 0, (GAIN_TLEILAXU_CUSTOM,)),
        ResearchBonus.RESEARCH: (0, 0, 0, (GAIN_RESEARCH_CUSTOM,)),
        ResearchBonus.TRASH_AND_SPECIMEN: (1, 0, 0, (TRASH_CUSTOM,)),
        ResearchBonus.TLEILAXU_AND_SPECIMEN: (1, 0, 0, (GAIN_TLEILAXU_CUSTOM,)),
        ResearchBonus.SOLARI_ONE: (0, 0, 1, ()),
        ResearchBonus.SPICE_ONE: (0, 1, 0, ()),
        ResearchBonus.SPICE_TWO: (0, 2, 0, ()),
        ResearchBonus.INFLUENCE_ANY: (0, 0, 0, (GAIN_ANY_FACTION_INFLUENCE_CUSTOM,)),
        ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE: (
            0,
            0,
            0,
            (TRASH_INTRIGUE_FOR_DRAW_AND_INTRIGUE,),
        ),
        ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU: (
            0,
            0,
            0,
            (PAY_SOLARI_FOR_TLEILAXU,),
        ),
    }
    assert len(RESEARCH_SPACE_DEFS) == len(RESEARCH_SPACES) == 22
    for index, (space, definition) in enumerate(
        zip(RESEARCH_SPACES, RESEARCH_SPACE_DEFS, strict=True)
    ):
        assert RESEARCH_SPACE_IDS[index] == space.space_id
        assert definition.troops == 0
        assert (
            definition.specimens,
            definition.spice,
            definition.solari,
            definition.abilities,
        ) == expected[space.bonus], space.space_id
        nxt = tuple(
            RESEARCH_SPACE_IDS.index(s) for s in research_next_space_ids(space.space_id)
        )
        assert tuple(sorted(nxt)) == definition.next, space.space_id


# =================================================================================
# §2.1 ResearchValue
# =================================================================================

HELIX_HAND = (
    imperium("bene_tleilax_researcher"),  # Graft, Helix, DoubleHelix
    imperium("dissecting_kit"),  # Graft, Helix, Shadow
)
HELIX_DECK = (tleilaxu("unnatural_reflexes"),)  # Graft, Helix
HELIX_INTRIGUE = (intrigue("vicious_talents"),)  # Helix, DoubleHelix


def helix_state(research_space: str, round_number: int = 2) -> GameState:
    return at_round(
        round_number,
        research_space=research_space,
        hand=HELIX_HAND,
        deck=HELIX_DECK,
        intrigue_cards=HELIX_INTRIGUE,
    )


def test_research_value_before_the_first_marker_counts_helix_cards() -> None:
    # 3 Helix Imperium/Tleilaxu cards + 1 held Helix Intrigue: 2.25 + 4 x 0.75.
    assert prof(helix_state("c3r1")).research_value().sum == pytest.approx(5.25)
    plain = at_round(2, research_space="c3r1")  # starters only
    assert prof(plain).research_value().sum == pytest.approx(2.25)


def test_research_value_after_the_first_marker_counts_double_helix() -> None:
    # Bene Tleilax Researcher and Vicious Talents: 2.25 + 2 x 1.0.
    assert prof(helix_state("c4r4")).research_value().sum == pytest.approx(4.25)


def test_research_value_after_the_second_marker_is_a_card_draw() -> None:
    # "End of Track" x 0, then CardDrawValue (1.5, no buy gains).
    for round_number in (2, 5, 8):  # 2.25 on every arc
        value = prof(helix_state("c8r2", round_number)).research_value().sum
        assert value == 1.5


def test_research_value_base_is_the_same_on_every_arc_and_level() -> None:
    for level in (0, 1, 2):
        for round_number in (2, 5, 8):
            profile = prof(at_round(round_number), level=level)
            assert profile.research_value().sum == pytest.approx(2.25)


# =================================================================================
# §2.2 TleilaxuValue
# =================================================================================


@pytest.mark.parametrize(
    ("current", "amount", "round_number", "expected"),
    [
        (0, 1, 2, 2.25),
        (1, 1, 2, 2.25 + 1.0),  # crosses 2: Intrigue
        (3, 1, 2, 2.25 + 4.0),  # crosses 4: VP (flat 4.0)
        (5, 1, 2, 2.25 + 1.0),  # crosses 6
        (6, 1, 2, 2.25 + 4.0),  # crosses 7
        (7, 1, 2, 0.0),  # end of the track
        (7, 3, 2, 0.0),
        (1, 3, 2, 6.75 + 1.0 + 4.0),
        (0, 7, 2, 15.75 + 1.0 + 4.0),  # each bonus kind once
        (6, 2, 2, 4.5 + 4.0),  # past 7 at full base
        (0, 1, 5, 2.25),  # Mid arc: no cut
        (0, 1, 8, 2.25 * 0.25),  # Late single step onto 1: cut
        (2, 1, 8, 2.25 * 0.25),
        (4, 1, 8, 2.25 * 0.25),
        (1, 1, 8, 2.25 + 1.0),  # Late single step with a bonus: no cut
        (3, 1, 8, 2.25 + 4.0),
        (5, 1, 8, 2.25 + 1.0),
        (0, 2, 8, 4.5 + 1.0),  # two steps: no cut
    ],
)
def test_tleilaxu_value(
    current: int, amount: int, round_number: int, expected: float
) -> None:
    state = at_round(round_number, tleilaxu_space=current)
    assert prof(state).tleilaxu_value(amount).sum == pytest.approx(expected)


def test_tleilaxu_value_late_cut_is_the_apps_multiply() -> None:
    value = prof(at_round(8, tleilaxu_space=0)).tleilaxu_value(1).sum
    assert value == app_mul(2.25, 0.25)


# =================================================================================
# §2.3-§2.4 Specimens: always Poor, and the Tleilaxu Row bonus
# =================================================================================


def row_profile(
    state: GameState, values: dict[str, float], *, level: int = 2
) -> Profile:
    """A profile whose Tleilaxu-row AcquireValues are ``values`` by ref."""

    profile = prof(state, level=level)
    real = profile.acquire_value

    def acquire_value(entity: Entity) -> Summer:
        if entity.ref in values:
            return Summer(values[entity.ref])
        return real(entity)

    return stub(profile, acquire_value=acquire_value)


def test_specimen_abundance_is_always_poor() -> None:
    state = at_round(2, **specimens(6))
    profile = row_profile(state, {RECLAIMED_FORCES_REF: 0.0})
    assert profile.abundance_level(Attr.SPECIMEN) == 0  # 6 specimens held
    assert profile.specimen_value(1) == pytest.approx(1.0 * 1.25)
    late = row_profile(at_round(8, **specimens(6)), {RECLAIMED_FORCES_REF: 0.0})
    assert late.specimen_value(2) == pytest.approx(0.75 * 1.25 * 2)


@pytest.mark.parametrize(("level", "poor"), [(2, 1.25), (1, 1.05), (0, 0.85)])
def test_specimen_poor_mod_by_level(level: int, poor: float) -> None:
    profile = row_profile(at_round(2), {RECLAIMED_FORCES_REF: 0.0}, level=level)
    assert profile.specimen_value(1) == pytest.approx(poor)


def test_specimen_bonus_for_a_good_unaffordable_row_card() -> None:
    # Reclaimed Forces (3 specimens) worth 2.0 > 1.5 and 2 specimens held.
    state = at_round(2, **specimens(2))
    profile = row_profile(state, {RECLAIMED_FORCES_REF: 2.0})
    assert profile.specimen_value(1) == pytest.approx(1.25 + 1.0)
    # The bonus is added before "Amount": a cost is penalised by it too.
    assert profile.specimen_value(-2) == pytest.approx((1.25 + 1.0) * -2)
    # Affordable (3 held, cost 3 is not > 3): no bonus.
    affordable = row_profile(at_round(2, **specimens(3)), {RECLAIMED_FORCES_REF: 2.0})
    assert affordable.specimen_value(1) == pytest.approx(1.25)
    # Not good enough (1.5 is not > 1.5): no bonus.
    weak = row_profile(state, {RECLAIMED_FORCES_REF: 1.5})
    assert weak.specimen_value(1) == pytest.approx(1.25)


def test_specimen_bonus_reads_only_the_best_row_card() -> None:
    cheap = tleilaxu("face_dancer_initiate")  # costs 1 specimen
    state = with_row(at_round(2, **specimens(2)), cheap, tleilaxu("from_the_tanks"))
    others = {tleilaxu("from_the_tanks"): 0.0}
    # Tied best: the first in row order (Reclaimed Forces, cost 3 > 2) wins.
    tied = row_profile(state, {RECLAIMED_FORCES_REF: 2.0, cheap: 2.0, **others})
    assert tied.specimen_value(1) == pytest.approx(2.25)
    # A strictly better affordable card hides the unaffordable one.
    better = row_profile(state, {RECLAIMED_FORCES_REF: 2.0, cheap: 2.5, **others})
    assert better.specimen_value(1) == pytest.approx(1.25)


def test_specimen_bonus_needs_immortality() -> None:
    profile = prof(with_state(base_state(), round_number=2))
    assert profile.specimen_value(1) == pytest.approx(1.25)


# =================================================================================
# §2.4 Economic Positioning on Solari
# =================================================================================


def test_economic_positioning_solari_mod_late_only() -> None:
    held = (intrigue("economic_positioning"),)
    late_without = prof(at_round(8)).solari_value(1)
    late_with = prof(at_round(8, intrigue_cards=held)).solari_value(1)
    assert late_with == app_mul(late_without, 1.5)
    mid_without = prof(at_round(5)).solari_value(1)
    assert prof(at_round(5, intrigue_cards=held)).solari_value(1) == mid_without


def test_economic_positioning_solari_mod_needs_immortality() -> None:
    plain = with_state(base_state(), round_number=8)
    held = with_player(plain, ME, intrigue_cards=(intrigue("economic_positioning"),))
    assert prof(held).solari_value(1) == prof(plain).solari_value(1)


# =================================================================================
# §2.5 AcquireValue — the Tleilaxu branch
# =================================================================================

OWNED_HAND = (
    imperium("dissecting_kit"),  # Graft, Helix, Shadow
    imperium("replacement_eyes"),  # Graft, Shadow
    imperium("blank_slate"),  # WantsGraft
)
OWNED_DISCARD = (tleilaxu("industrial_espionage", 0),)  # WantsGraft


def tleilaxu_profile(
    research_space: str = "c0r3",
    *,
    round_number: int = 2,
    bonus: float = 0.25,
    climax: bool = False,
) -> Profile:
    state = at_round(
        round_number,
        research_space=research_space,
        hand=OWNED_HAND,
        discard_pile=OWNED_DISCARD,
    )
    profile = prof(state, climax=climax)
    return stub(profile, specific_acquire_bonus=Summer(bonus))


@pytest.mark.parametrize(
    ("name", "research_space", "expected"),
    [
        # 0.25 S + specimen cost + 0.5 x 2 Shadow + 0.75 x 2 WantsGraft.
        ("stitched_horror", "c0r3", 0.25 + 3 + 1.0 + 1.5),
        # WantsGraft: 0.75 x 2 Graft cards.
        ("industrial_espionage", "c0r3", 0.25 + 1 + 1.5),
        # Helix needs a genetic marker.
        ("subject_x_137", "c0r3", 0.25 + 2 + 1.0),
        ("subject_x_137", "c4r2", 0.25 + 2 + 1.0 + 1.5),
        # Double Helix needs both.
        ("scientific_breakthrough", "c4r2", 0.25 + 3),
        ("scientific_breakthrough", "c8r2", 0.25 + 3 + 2.0),
        ("tleilaxu_infiltrator", "c8r4", 0.25 + 2 + 2.0 + 1.5),
        ("from_the_tanks", "c0r3", 0.25 + 2),
    ],
)
def test_tleilaxu_acquire_value(
    name: str, research_space: str, expected: float
) -> None:
    profile = tleilaxu_profile(research_space)
    value = profile.acquire_value(card(tleilaxu(name, 1)))
    assert value.sum == pytest.approx(expected)


def test_tleilaxu_acquire_value_has_no_arc_mod_minimum_or_other_terms() -> None:
    # Late arc in climax: From the Tanks keeps 2.0 < MinimumAcquireValueLate
    # (2.2); no icon, consolidation, synergy, friendship or acquire effects.
    profile = tleilaxu_profile(round_number=8, bonus=0.0, climax=True)
    stub(
        profile,
        synergy_mod=Summer(100.0),
        friendship_mod=Summer(100.0),
        acquire_effects_value=Summer(100.0),
    )
    assert profile.acquire_value(card(tleilaxu("from_the_tanks"))).sum == 2.0
    # Reclaimed Forces' acquire icons (Troop, Troop, Shadow) are not valued.
    assert profile.acquire_value(card(RECLAIMED_FORCES_REF)).sum == 3.0


def test_tleilaxu_acquire_value_counts_an_owned_copy() -> None:
    # The candidate counts itself only when the seat owns a copy.
    state = at_round(2, hand=(tleilaxu("stitched_horror"),))
    profile = stub(prof(state), specific_acquire_bonus=Summer(0.0))
    assert profile.acquire_value(card(tleilaxu("stitched_horror", 1))).sum == (
        pytest.approx(3 + 0.5)
    )


# =================================================================================
# §2.6 Synergy: Helix and Double Helix incentives
# =================================================================================


class PileAbility(Ability):
    """A fake owned ability whose deck-pile synergy is a fixed value."""

    def __init__(self, owner: Entity, value: float) -> None:
        super().__init__(owner)
        self.value = value

    def value_in_pile_for_other_play(
        self, p: Profile, pile: Pile, card: Entity
    ) -> Summer:
        return Summer(self.value)


def synergy_profile(research_space: str, *, climax: bool = False) -> Profile:
    profile = prof(at_round(2, research_space=research_space), climax=climax)
    owned = card(imperium("blank_slate"))
    return stub(
        profile,
        _all_imperium_cards=lambda: [owned],
        _abilities=lambda entity: (PileAbility(entity, 1.0),),
    )


@pytest.mark.parametrize(
    ("research_space", "name", "expected"),
    [
        ("c0r3", "bene_tleilax_researcher", 1.0),
        ("c4r2", "bene_tleilax_researcher", 1.2),  # Helix
        ("c8r2", "bene_tleilax_researcher", 1.2 * 1.2),  # Helix and Double Helix
        ("c4r2", "imperium_ceremony", 1.0),  # no tag
    ],
)
def test_synergy_helix_incentives(
    research_space: str, name: str, expected: float
) -> None:
    profile = synergy_profile(research_space)
    assert profile.synergy_mod(card(imperium(name))).sum == pytest.approx(expected)


def test_synergy_double_helix_alone_needs_two_markers() -> None:
    infiltrator = card(tleilaxu("tleilaxu_infiltrator"))  # Graft, DoubleHelix
    assert synergy_profile("c4r2").synergy_mod(infiltrator).sum == pytest.approx(1.0)
    assert synergy_profile("c8r4").synergy_mod(infiltrator).sum == pytest.approx(1.2)
    assert synergy_profile("c8r4", climax=True).synergy_mod(infiltrator).sum == 0.0


# =================================================================================
# §2.7 GetAcquireEffectsValue: Research and Shadow
# =================================================================================


def test_acquire_effects_research_and_shadow() -> None:
    profile = stub(
        prof(at_round(2)), research_value=Summer(3.5), tleilaxu_value=Summer(2.0)
    )
    fervor = card(imperium("spiritual_fervor"))  # [Research]
    assert profile.acquire_effects_value(fervor).sum == 3.5
    troop = profile.resource_value(Attr.TROOPS, 1, False)
    forces = card(RECLAIMED_FORCES_REF)  # [Troop, Troop, Shadow]
    assert profile.acquire_effects_value(forces).sum == pytest.approx(
        troop + troop + 2.0
    )


def test_acquire_effects_shadow_is_tleilaxu_value_of_one() -> None:
    profile = prof(at_round(2, tleilaxu_space=3))
    subject = card(tleilaxu("subject_x_137"))  # [Shadow]
    assert profile.acquire_effects_value(subject).sum == pytest.approx(2.25 + 4.0)


# =================================================================================
# §2.8 GetCardToTrash: Replacement Eyes
# =================================================================================

EYES = imperium("replacement_eyes")


@pytest.mark.parametrize(
    ("round_number", "zone", "expected"),
    [
        # 0.1 + 1.5 = 1.6 > 1: +10, x10, + location + (0.09 - 0.05).
        (8, "discard_pile", 116.0 + 0.2 + 0.04),
        (8, "in_play", 116.0 + 0.1 + 0.04),
        (8, "hand", 1.0 + 0.0 + 0.04),  # in hand: no bonus
        (5, "discard_pile", 1.0 + 0.2 + 0.04),  # not Late
    ],
)
def test_card_to_trash_replacement_eyes(
    round_number: int, zone: str, expected: float
) -> None:
    changes: dict[str, Any] = {"hand": (), "discard_pile": (), "in_play": ()}
    changes[zone] = (EYES,)
    profile = prof(at_round(round_number, **changes))
    best, value = profile.card_to_trash([card(EYES)], 0.0)
    assert best is not None and best.ref == EYES
    assert value == pytest.approx(expected)


# =================================================================================
# GetRevealPreview: the Immortality reveal boxes and Chairdog's returns
# =================================================================================


@pytest.mark.parametrize(("research_space", "researcher"), [("c0r3", 1), ("c4r2", 2)])
def test_reveal_preview_immortality_overrides(
    research_space: str, researcher: int
) -> None:
    hand = (
        imperium("bene_tleilax_researcher"),  # GeneticMarkers + 1
        imperium("throne_room_politics"),  # literal 1
        imperium("lisan_al_gaib"),  # its printed Persuasion (1)
    )
    state = at_round(2, research_space=research_space, hand=hand)
    assert prof(state).possible_persuasion() == researcher + 1 + 1


def test_reveal_preview_counts_cards_chairdog_returns() -> None:
    politics = imperium("throne_room_politics")
    state = at_round(
        2, hand=(), in_play=(politics,), chairdog_return_card_ids=(politics,)
    )
    assert prof(state).possible_persuasion() == 1
    unmarked = at_round(2, hand=(), in_play=(politics,))
    assert prof(unmarked).possible_persuasion() == 0


def test_reveal_preview_ignores_chairdog_returns_in_the_reveal_turn() -> None:
    politics = imperium("throne_room_politics")
    state = with_player(
        imm_reveal_state(),
        ME,
        hand=(),
        in_play=(politics,),
        chairdog_return_card_ids=(politics,),
    )
    profile = prof(state)
    assert profile._in_reveal_turn()
    assert profile.possible_persuasion() == profile._persuasion_pool()


def test_discard_order_reads_the_first_immortality_agent_box(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    class Valued(Ability):
        def value_for_player(
            self, p: Profile, with_entities: Sequence[Entity] = ()
        ) -> Summer:
            return Summer(1.0)

    def ability_for(app_class: str, owner: Entity) -> Ability:
        seen.append(app_class.rsplit(".", 1)[1])
        return Valued(owner)

    monkeypatch.setattr(abilities_pkg, "ability_for", ability_for)
    profile = prof(at_round(2))
    chairdog = card(tleilaxu("chairdog"))
    assert profile._first_ability_value(chairdog, economy._AGENT_CLASSES) == 1.0
    assert profile._first_ability_value(chairdog, economy._REVEAL_CLASSES) == 1.0
    researcher = card(imperium("bene_tleilax_researcher"))
    assert profile._first_ability_value(researcher, economy._AGENT_CLASSES) == 1.0
    assert profile._first_ability_value(researcher, economy._REVEAL_CLASSES) == 1.0
    assert seen == [
        "ChairdogAgentAbility",  # the first of its two agent boxes
        "RevealAbility",
        "GraftAgentAbility",
        "BeneTleilaxResearcherRevealAbility",
    ]


# =================================================================================
# §2.10 WormResearchTrack::SpaceValue
# =================================================================================


class FixedAbility(Ability):
    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        return Summer(7.0)


@pytest.mark.parametrize(
    ("space", "expected", "abilities"),
    [
        ("c0r3", 0.0, []),
        ("c1r3", 10.0, []),  # Specimen 1
        ("c2r4", 7.0, ["GainTleilaxuInfluenceCustomAbility"]),
        ("c3r1", 7.0, ["GainResearchCustomAbility"]),
        ("c3r3", 10.0 + 7.0, ["TrashCustomAbility"]),
        ("c3r5", 10.0 + 7.0, ["GainTleilaxuInfluenceCustomAbility"]),
        ("c5r5", 1000.0, []),  # Solari 1
        ("c6r2", 100.0, []),  # Spice 1
        ("c6r6", 7.0, ["GainAnyFactionInfluenceCustomAbility"]),
        ("c7r3", 7.0, ["TrashIntrigueForDrawAndIntrigue"]),
        ("c8r2", 200.0, []),  # Spice 2
        ("c8r6", 7.0, ["PaySolariForTleilaxuInfluence"]),
    ],
)
def test_research_space_value(
    space: str,
    expected: float,
    abilities: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def ability_for(app_class: str, owner: Entity) -> Ability:
        calls.append((app_class.rsplit(".", 1)[1], owner.ref))
        return FixedAbility(owner)

    monkeypatch.setattr(abilities_pkg, "ability_for", ability_for)
    profile = stub(
        prof(at_round(2)),
        specimen_value=lambda n: 10.0 * n,
        spice_value=lambda n: 100.0 * n,
        solari_value=lambda n: 1000.0 * n,
    )
    assert profile.research_space_value(space).sum == expected
    assert calls == [(name, f"research:{space}") for name in abilities]


def test_research_space_value_prices_specimens_like_get_specimen_value() -> None:
    profile = prof(at_round(2))
    assert profile.research_space_value("c1r3").sum == profile.specimen_value(1)


# =================================================================================
# §2.9 Combat helpers
# =================================================================================


class StrengthFake(Ability):
    def __init__(self, owner: Entity, strength: int) -> None:
        super().__init__(owner)
        self.strength = strength

    def strength_value(self, p: Profile) -> int:
        return self.strength


class TroopIntrigue(IntrigueAbility):
    """``CounterattackPlotAbility``-like: ``TroopValue`` 4 (vslot 86)."""

    def __init__(self, owner: Entity, troop: int = 4) -> None:
        super().__init__(owner)
        self.troop = troop

    def troop_value(self, p: Profile) -> int:
        return self.troop


def install_intrigues(monkeypatch: pytest.MonkeyPatch, troop: int = 4) -> None:
    """Counterattack: plot box worth ``troop`` troops, combat box 4 swords;
    Vicious Talents: 6 swords."""

    def abilities_of(owner: Entity) -> tuple[Ability, ...]:
        made: list[Ability] = []
        for ability_id in owner.ability_ids:
            name = ability_id.rsplit(".", 1)[1]
            if name == "CounterattackPlotAbility":
                made.append(TroopIntrigue(owner, troop))
            elif name == "CounterattackCombatAbility":
                made.append(StrengthFake(owner, 4))
            elif name == "ViciousTalentsAbility":
                made.append(StrengthFake(owner, 6))
            else:
                made.append(Ability(owner))
        return tuple(made)

    monkeypatch.setattr(combat, "abilities_of", abilities_of)


def test_intrigue_hand_strength_value_counts_immortality_strength_intrigues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_intrigues(monkeypatch)
    held = (intrigue("counterattack"), intrigue("vicious_talents"))
    profile = prof(at_round(2, intrigue_cards=held))
    assert profile.intrigue_hand_strength_value() == 4 + 6


def strength_profile(intrigues: tuple[str, ...], interest: float = 10.0) -> Profile:
    state = at_round(
        2,
        hand=(),
        combat_strength=3,
        intrigue_cards=intrigues,
        **troops(2, 1),
    )
    return stub(
        prof(state),
        current_conflict_interest=Summer(interest),
        conflict_posture_bounds=(5.0, 20.0),
        intrigue_hand_strength_value=0,
        heighliner_potential_player=None,
        _worm_potential_a_player=None,
        _worm_potential_b_player=None,
        has_worm_potential=False,
    )


@pytest.mark.parametrize(
    ("held", "troop", "bonus"),
    [
        ((), 4, 0),
        ((intrigue("counterattack"),), 4, 2),  # 4 / 2
        ((intrigue("counterattack"), intrigue("counterattack", 1)), 4, 4),
        ((intrigue("counterattack"),), 3, 1),  # C# int / 2 truncates
    ],
)
def test_intrigue_troop_value_in_the_strength_estimates(
    held: tuple[str, ...], troop: int, bonus: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_intrigues(monkeypatch, troop)
    # EstStrength: 0 hand swords + 3 current + 3 x 2 Agents + troop value / 2.
    assert strength_profile(held).est_strength().sum == 3 + 6 + bonus
    # Below the posture's lower bound the term is not reached.
    assert strength_profile(held, interest=4.0).est_strength().sum == 3
    # PotentialStrength(1): 3 + 0 + 0 + 2 + min(2 - 1, 4) + 4 + troop value / 2.
    assert strength_profile(held).potential_strength(1).sum == 3 + 2 + 1 + 4 + bonus


def test_cs_half_truncates_toward_zero() -> None:
    assert combat._cs_half(3) == 1
    assert combat._cs_half(-3) == -1


@pytest.mark.parametrize(("solari", "mod"), [(0.75, 1.2), (0.74, 1.0)])
def test_deploy_value_economic_positioning(solari: float, mod: float) -> None:
    contested = troops(0, 1)
    state = at_round(
        2, intrigue_cards=(intrigue("economic_positioning"),), **troops(3, 0)
    )
    for seat in (0, 1, 2):
        state = with_player(state, seat, **contested)
    profile = stub(
        prof(state),
        game_arc=0,
        conflict_posture_bounds=(5.0, 20.0),
        current_conflict_interest=Summer(10.0),
        solari_value=lambda n: solari,
    )
    sardaukar = space_entity("sardaukar", Board(False, True))
    assert profile.deploy_value(sardaukar) == pytest.approx(0.75 * mod)
    without = with_player(state, ME, intrigue_cards=())
    plain = stub(
        prof(without),
        game_arc=0,
        conflict_posture_bounds=(5.0, 20.0),
        current_conflict_interest=Summer(10.0),
        solari_value=lambda n: solari,
    )
    assert plain.deploy_value(sardaukar) == pytest.approx(0.75)


# =================================================================================
# Epic Game Mode: Economic Supremacy (epic §2.4)
# =================================================================================


def test_economic_supremacy_places_and_conflict_pool() -> None:
    profile = prof(config_state(EPIC), seat=0)
    supremacy = conflict_entity("economic_supremacy", False)
    places = [place for place, _ in profile._conflict_abilities(supremacy)]
    assert places == [1, 2, 3, 0, 0]
    shorts = {a.short for a in profile.uprising_conflicts()}
    assert "ConflictArchetypes.RiseOfIx.EconomicSupremacy" not in shorts
    level_three = [
        a for a in profile.uprising_conflicts() if combat._int(a, "ConflictLevel") == 3
    ]
    assert len(level_three) == 4


class ValueFake(Ability):
    def __init__(self, owner: Entity, value: float) -> None:
        super().__init__(owner)
        self.value = value

    def value_for_player(
        self, p: Profile, with_entities: Sequence[Entity] = ()
    ) -> Summer:
        return Summer(self.value)


def test_economic_supremacy_conflict_value_and_guaranteed_third_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "EconomicSupremacyFirstAbility": 1.0,
        "EconomicSupremacySecondAbility": 10.0,
        "EconomicSupremacyThirdAbility": 100.0,
        "EconomicSupremacySolariAbility": 1000.0,
        "EconomicSupremacySpiceAbility": 10000.0,
    }

    def abilities_of(owner: Entity) -> tuple[Ability, ...]:
        return tuple(
            ValueFake(owner, values.get(ability_id.rsplit(".", 1)[1], 0.0))
            for ability_id in owner.ability_ids
        )

    monkeypatch.setattr(combat, "abilities_of", abilities_of)
    state = with_conflict(config_state(EPIC), "economic_supremacy")
    no_agents = {"agents_available": 0, "agent_locations": ("sardaukar", "secrets")}
    state = with_player(state, 0, **troops(3, 0))
    state = with_player(state, 1, **troops(0, 1))
    state = with_player(state, 2, **troops(0, 0), **no_agents)
    state = with_player(state, 3, **troops(0, 0), **no_agents)
    profile = stub(
        prof(state, seat=0),
        game_arc=0,
        conflict_posture_bounds=(5.0, 20.0),
        current_conflict_interest=Summer(10.0),
    )
    # ConflictValue: every ability of the card, the charges included.
    supremacy = conflict_entity("economic_supremacy", False)
    assert profile._conflict_value(supremacy).sum == 11111.0
    # DeployValue's guaranteed 3rd place: ES Third's value x 1.25 (0.75 x 1.5
    # with a free paid slot).
    sardaukar = space_entity("sardaukar", Board(False, False))
    assert profile.deploy_value(sardaukar) == pytest.approx(1.125 + 1.25 * 100.0)


@pytest.mark.parametrize(
    ("solari", "spice", "sandworms", "expected"),
    [
        (6, 4, 0, 3),  # 1 + Solari >= 6 + spice >= 4
        (5, 4, 0, 2),
        (6, 3, 0, 2),
        (5, 3, 0, 1),
        (6, 4, 1, 3 + 1),  # the sandworm copy needs 12 Solari / 8 spice
        (12, 8, 1, 3 + 3),
    ],
)
def test_possible_end_of_round_score_economic_supremacy(
    solari: int, spice: int, sandworms: int, expected: int
) -> None:
    state = with_conflict(config_state(EPIC), "economic_supremacy")
    me = state.players[0]
    state = with_player(
        state,
        0,
        resources=replace(me.resources, solari=solari, spice=spice),
        sandworms_conflict=sandworms,
    )
    profile = prof(state, seat=0)
    # No battle icon on Economic Supremacy: no +1.
    assert profile.possible_end_of_round_score(0) == me.victory_points + expected


def test_retreat_endgame_branch_reads_the_conflict_card_vp() -> None:
    """Economic Supremacy's card VP 4: endgame at max VP 8 with T = 12."""

    def retreat(conflict_id: str) -> int:
        state = with_conflict(config_state(EPIC), conflict_id)
        for seat, strength in enumerate((2, 5, 6, 7)):
            state = with_player(state, seat, combat_strength=strength)
        state = with_player(state, 0, **troops(0, 1))
        state = with_player(state, 2, victory_points=8)
        estimates = {0: 1, 1: 2, 2: 9, 3: 3}  # seat 2 is in the top 2
        profile = stub(
            prof(state, seat=0),
            est_strength=IntSummer(estimates[0]),
            est_opponent_strength=lambda s: IntSummer(estimates[s]),
            relative_conflict_value=Summer(1.0),
            intrigue_hand_strength_value=0,
        )
        assert profile.ctx.endgame_trigger_score == 12
        return profile.troops_to_retreat(3)

    # 4 + 8 >= 12: beaten by all three, the AI pulls out.
    assert retreat("economic_supremacy") == 3
    # An Uprising card has no card VP: 0 + 8 < 12, the margin rule keeps them.
    assert retreat("battle_for_arrakeen") == 0


# =================================================================================
# Go to 11 and every VP threshold (epic §3.4-§3.5)
# =================================================================================


def vp_profile(config: RulesetConfig, vp: int, seat_vp: int | None = None) -> Profile:
    state = with_player(config_state(config), 1, victory_points=vp)
    if seat_vp is not None:
        state = with_player(state, ME, victory_points=seat_vp)
    profile = _conftest.make_profile(state, ME)
    return stub(profile, possible_end_of_round_score=lambda seat: 0)


@pytest.mark.parametrize(
    ("config", "trigger", "offset"),
    [
        (IMMORTALITY, 10, 0),
        (GO_TO_11, 11, 1),
        (EPIC, 12, 0),
        (EPIC_GO_TO_11, 13, 1),
    ],
)
def test_app_vp_scale(config: RulesetConfig, trigger: int, offset: int) -> None:
    ctx = vp_profile(config, 4).ctx
    assert ctx.endgame_trigger_score == trigger
    assert ctx.vp(ctx.player(1)) == 4 + offset


@pytest.mark.parametrize(
    ("config", "vp", "climax"),
    [
        (IMMORTALITY, 8, False),
        (IMMORTALITY, 9, True),  # >= T - 1
        (GO_TO_11, 8, False),  # app 9 < 10
        (GO_TO_11, 9, True),  # app 10 >= 10: one VP before our end, like the app
        (EPIC, 10, False),
        (EPIC, 11, True),
        (EPIC_GO_TO_11, 10, False),  # app 11 < 12
        (EPIC_GO_TO_11, 11, True),
    ],
)
def test_is_climax_on_the_app_scale(
    config: RulesetConfig, vp: int, climax: bool
) -> None:
    assert vp_profile(config, vp).is_climax() is climax


@pytest.mark.parametrize(
    ("config", "own_vp", "doubled"),
    [
        (IMMORTALITY, 8, False),  # 8 + 1 < 10
        (IMMORTALITY, 9, True),
        (GO_TO_11, 8, True),  # app 9 + 1 >= 10: the literal 10 one VP earlier
        (GO_TO_11, 7, False),
        (EPIC, 9, True),  # the literal does not move with T = 12
    ],
)
def test_victory_point_value_literal_ten_on_the_app_scale(
    config: RulesetConfig, own_vp: int, doubled: bool
) -> None:
    profile = vp_profile(config, 0, seat_vp=own_vp)
    stub(profile, game_arc=0)
    assert profile.victory_point_value(1) == (12.0 if doubled else 6.0)


@pytest.mark.parametrize(
    ("config", "holder_vp", "endgame"),
    [
        (IMMORTALITY, 9, False),
        (IMMORTALITY, 10, True),  # holder VP >= T (10)
        (GO_TO_11, 9, False),  # app 10 < 11
        (GO_TO_11, 10, True),  # app 11 >= 11: the same distance to our end
        (EPIC, 11, False),
        (EPIC, 12, True),  # T = 12
        (EPIC_GO_TO_11, 11, False),  # app 12 < 13
        (EPIC_GO_TO_11, 12, True),
    ],
)
def test_steal_alliance_endgame_on_the_app_scale(
    config: RulesetConfig, holder_vp: int, endgame: bool
) -> None:
    """epic §3.4: ``GetGainInfluenceValue`` reads T (T read @0x490abb2).

    Seat 1 holds the Emperor Alliance at 4; this seat (3) gains 2 from 3, so
    the gain steals the Alliance: x``GainInfluenceStealAllianceEndgameMod``
    (3.0) once the holder's VP reaches T, else x``…StealAllianceMod`` (1.75).
    """

    state = config_state(config)
    state = with_player(
        state,
        1,
        influence=replace(state.players[1].influence, emperor=4),
        alliance_faction_ids=("emperor",),
        victory_points=holder_vp,
    )
    state = with_player(
        state, ME, influence=replace(state.players[ME].influence, emperor=3)
    )
    profile = _conftest.make_profile(state, ME)
    Summer.tracing = True
    try:
        value = profile.gain_influence_value("emperor", 2, -1, False)
    finally:
        Summer.tracing = False
    steal = [reason for _, reason, _ in value.reasons or () if "Steal" in reason]
    assert steal == (["Steal Alliance Endgame"] if endgame else ["Steal Alliance"])


@pytest.mark.parametrize(
    ("config", "vp", "final"),
    [
        (IMMORTALITY, 9, False),
        (IMMORTALITY, 10, True),  # IsEndgame: VP >= T
        (GO_TO_11, 9, False),
        (GO_TO_11, 10, True),  # app 11 >= 11
        (EPIC, 11, False),
        (EPIC, 12, True),
        (EPIC_GO_TO_11, 11, False),
        (EPIC_GO_TO_11, 12, True),  # app 13 >= 13
    ],
)
def test_is_final_round_endgame_test_on_the_app_scale(
    config: RulesetConfig, vp: int, final: bool
) -> None:
    """epic §3.4: ``get_IsFinalRound`` b__0 = ``IsEndgame()`` (any VP >= T)
    or a top-2 projection >= T (stubbed to 0 here)."""

    assert vp_profile(config, vp).is_final_round() is final
