"""Card-specific ability ports, Uprising cards M–Z: spec/imperium-b.md.

Every test builds a real ``GameState`` (``app_ai.testing``), adjusts the
fields the formula reads, and stubs the ``Profile`` methods other areas own
with simple linear prices so each expected value can be checked by hand. A
few tests run the real profile (worked example of 17 §4, junk trash, and a
smoke test over every M–Z card).
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import pytest

from dune_imperium.agents.app_ai.abilities import PORTS, abilities_of
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import imperium_b as b
from dune_imperium.agents.app_ai.abilities.base import (
    Ability,
    Answer,
    Pile,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
)
from dune_imperium.agents.app_ai.abilities.imperium_a import (
    DeliveryAgreementRevealAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    CARD_ARCHETYPES,
    card_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

# ---------------------------------------------------------------------------
# Fixtures and stubs
# ---------------------------------------------------------------------------

PRICES = {
    Attr.WATER: 1.0,
    Attr.SPICE: 0.5,
    Attr.SOLARI: 0.25,
    Attr.PERSUASION: 0.75,
    Attr.STRENGTH: 0.66,
    Attr.TROOPS: 0.9,
    Attr.SPECIMEN: 0.1,
}
INFLUENCE = {"emperor": 2.0, "spacing_guild": 2.5, "bene_gesserit": 3.0, "fremen": 1.0}
SEAT = 3  # the first player of seed 1 (Lady Jessica)
AB = "worm.canis.abilities."


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "persuasion_value": lambda n: 0.75 * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "victory_point_value": lambda n: 6.0 * n,
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "intrigue_value": lambda: 2.25,
        "trash_card_value": lambda: 2.75,
        "trash_mod": lambda: 1.0,
        "discard_value": lambda: -1.0,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "recall_spy": lambda spies: (spies[0], -1.0) if spies else (None, 0.0),
        "is_climax": lambda: False,
        "acquire_value": lambda card: Summer(3.0),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "discard_order": lambda cards, bonus: list(cards),
        "deploy_value": lambda owner: 1.25,
        "units_to_deploy": lambda garrison, max_units: (
            min(garrison, max_units) if max_units > 0 else garrison
        ),
        "troops_to_retreat": lambda max_troops: 0,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` decision (round 1, CHOAM on)."""

    return first_decision("turn")


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects``: Reconnaissance at Arrakeen."""

    return first_decision("agent_effects")


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, **stub overrides) -> Profile`` (stubbed prices)."""

    def build(
        state: GameState, seat: int = SEAT, **overrides: Callable[..., Any]
    ) -> Profile:
        profile = make_profile(state, seat)
        stubs = _base_stubs()
        stubs.update(overrides)
        for name, fn in stubs.items():
            monkeypatch.setattr(profile, name, fn)
        return profile

    return build


def imperium(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def space(space_id: str) -> Entity:
    return space_entity(space_id, True)


def req(*entities: Entity, options: tuple[int, ...] = ()) -> Request:
    return Request((TargetInfo(tuple(entities), options, 0, 1),))


def synth(ref: str, **attrs: object) -> Entity:
    """A card with a hand-made archetype (the promo cards have none)."""

    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(Kind.CARD, ref, archetype, SEAT)


def hand(state: GameState, *cards: Entity) -> GameState:
    return with_player(state, SEAT, hand=tuple(c.ref for c in cards))


def in_play(state: GameState, *cards: Entity) -> GameState:
    return with_player(state, SEAT, in_play=tuple(c.ref for c in cards))


def won(state: GameState, conflict_id: str) -> GameState:
    """Seat 3 won ``conflict_id`` (taken out of the shared Conflict zones)."""

    state = with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        unused_conflict_ids=tuple(
            c for c in state.unused_conflict_ids if c != conflict_id
        ),
        current_conflict_ids=tuple(
            c for c in state.current_conflict_ids if c != conflict_id
        ),
    )
    return with_player(state, SEAT, won_conflict_ids=(conflict_id,))


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    """``state`` with keys of the top frame's context replaced."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


# ---------------------------------------------------------------------------
# Registration, class chain and coverage
# ---------------------------------------------------------------------------

_REGISTERED: list[tuple[str, type[Ability], type[Ability]]] = [
    ("ActivatedAbilities.Uprising.MakerKeeperBeneGesseritAbility",
     b.MakerKeeperBeneGesseritAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.MakerKeeperFremenAbility",
     b.MakerKeeperFremenAbility, g.DeferredAbility),
    ("TriggeredAbilities.Uprising.NorthernWatermasterBondAbility",
     b.NorthernWatermasterBondAbility, g.BondAbility),
    ("PlayAbilities.Uprising.ParacompassRevealAbility",
     b.ParacompassRevealAbility, g.RevealAbility),
    ("TriggeredAbilities.Uprising.ParacompassTriggeredAbility",
     b.ParacompassTriggeredAbility, g.TriggeredAbility),
    ("ActivatedAbilities.Promo.PivotalGambitAbility",
     b.PivotalGambitAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.PriceIsNoObjectAbility",
     b.PriceIsNoObjectAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.PriorityContractsRevealAbility",
     b.PriorityContractsRevealAbility, DeliveryAgreementRevealAbility),
    ("ActivatedAbilities.Uprising.PublicSpectacleAbility",
     b.PublicSpectacleAbility, g.GainAnyInfluenceAbility),
    ("ActivatedAbilities.Uprising.RebelSupplierAbility",
     b.RebelSupplierAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.ReliableInformantAbility",
     b.ReliableInformantAbility, g.PlaceSpyAbility),
    ("PlayAbilities.Uprising.SardaukarCoordinationRevealAbility",
     b.SardaukarCoordinationRevealAbility, g.RevealAbility),
    ("ActivatedAbilities.Uprising.SardaukarCoordinationAgentAbility",
     b.SardaukarCoordinationAgentAbility, g.DeployUnitsAbility),
    ("PlayAbilities.Uprising.SardaukarCoordinationTriggeredAbility",
     b.SardaukarCoordinationTriggeredAbility, g.TriggeredAbility),
    ("TriggeredAbilities.Uprising.SardaukarSoldierAbility",
     b.SardaukarSoldierAbility, g.TriggeredAbility),
    ("PlayAbilities.BaseSet.SeekAlliesAgentAbility",
     b.SeekAlliesAgentAbility, g.AgentAbility),
    ("ActivatedAbilities.Uprising.ShishakliAgentAbility",
     b.ShishakliAgentAbility, g.DeferredAbility),
    ("ActivatedAbilities.BaseSet.CrysknifeAbility",
     b.CrysknifeAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SmugglersHarvesterAbility",
     b.SmugglersHarvesterAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SmugglersHavenAgentAbility",
     b.SmugglersHavenAgentAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SmugglersHavenRevealAbility",
     b.SmugglersHavenRevealAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SouthernEldersAgentAbility",
     b.SouthernEldersAgentAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SpacetimeFoldingAbility",
     b.SpacetimeFoldingAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SpacingGuildsFavorRevealAbility",
     b.SpacingGuildsFavorRevealAbility, g.GainAnyInfluenceAbility),
    ("TriggeredAbilities.Uprising.SpacingGuildsFavorDiscardAbility",
     b.SpacingGuildsFavorDiscardAbility, g.TriggeredAbility),
    ("ActivatedAbilities.Uprising.SpyNetworkAbility",
     b.SpyNetworkAbility, g.DeferredAbility),
    ("PlayAbilities.BaseSet.LietKynesRevealAbility",
     b.LietKynesRevealAbility, g.RevealAbility),
    ("PlayAbilities.BaseSet.LietKynesAbility",
     b.LietKynesAbility, g.TriggeredAbility),
    ("ActivatedAbilities.Uprising.StrikeFleetAbility",
     b.StrikeFleetAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.SubversiveAdvisorTrashSelfAbility",
     b.SubversiveAdvisorTrashSelfAbility, g.TrashSelfAbility),
    ("ActivatedAbilities.Promo.TheBeastsSpoilsCrysknifeAbility",
     b.TheBeastsSpoilsCrysknifeAbility, g.TrashAbility),
    ("ActivatedAbilities.Promo.TheBeastsSpoilsDesertMouseAbility",
     b.TheBeastsSpoilsDesertMouseAbility, g.DeferredAbility),
    ("ActivatedAbilities.Promo.TheBeastsSpoilsOrnithopterAbility",
     b.TheBeastsSpoilsOrnithopterAbility, g.DeferredAbility),
    ("PlayAbilities.BaseSet.ThufirHawatRevealAbility",
     b.ThufirHawatRevealAbility, g.RevealAbility),
    ("ActivatedAbilities.Uprising.TreacherousManeuverAbility",
     b.TreacherousManeuverAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.BeneGesseritTrashAbility",
     b.BeneGesseritTrashAbility, g.TrashAbility),
    ("PlayAbilities.BaseSet.UndercoverAssetRevealAbility",
     b.UndercoverAssetRevealAbility, g.RevealAbility),
    ("ActivatedAbilities.Uprising.UndercoverAssetAbility",
     b.UndercoverAssetAbility, g.DeferredAbility),
    ("ActivatedAbilities.Immortality.ShadoutMapesAbility",
     b.ShadoutMapesAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.UnswervingLoyaltyAbility",
     b.UnswervingLoyaltyAbility, b.ShadoutMapesAbility),
    ("PlayAbilities.Uprising.WeirdingWomanAgentAbility",
     b.WeirdingWomanAgentAbility, g.AgentAbility),
    ("ActivatedAbilities.Uprising.WeirdingWomanAbility",
     b.WeirdingWomanAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.WheelsWithinWheelsEmperorAbility",
     b.WheelsWithinWheelsEmperorAbility, g.DeferredAbility),
    ("ActivatedAbilities.Uprising.WheelsWithinWheelsSpacingGuildAbility",
     b.WheelsWithinWheelsSpacingGuildAbility, g.DeferredAbility),
]  # fmt: skip


@pytest.mark.parametrize(("name", "cls", "base"), _REGISTERED)
def test_ports_are_registered_with_the_app_class_chain(
    name: str, cls: type[Ability], base: type[Ability]
) -> None:
    assert PORTS[AB + name] is cls
    assert cls.APP_CLASS == AB + name
    assert issubclass(cls, base)


#: Ability classes of M–Z cards that an A–L card shares (Chani, Clever
#: Tactician): ported in ``imperium_a.py``.
_SHARED_WITH_A_TO_L = frozenset(
    {
        AB + "TriggeredAbilities.Uprising.SouthernEldersBondAbility",
        AB + "PlayAbilities.Uprising.SouthernEldersRevealAbility",
    }
)


def _scope_ability_ids() -> list[str]:
    """Every ability class of the M–Z personal cards dealt in our games."""

    ids: list[str] = []
    for short in CARD_ARCHETYPES.values():
        archetype = ARCHETYPES.get(short)
        if archetype is None or not (archetype.title or "")[:1].upper() >= "M":
            continue
        entity = Entity(Kind.CARD, short, archetype)
        for ability_id in entity.ability_ids:
            if ability_id not in ids:
                ids.append(ability_id)
    return ids


def test_every_m_to_z_ability_class_has_a_port() -> None:
    ids = _scope_ability_ids()
    assert len(ids) > 40
    missing = [i for i in ids if i not in PORTS]
    assert missing == []


@pytest.mark.parametrize("name", sorted(_SHARED_WITH_A_TO_L))
def test_shared_classes_come_from_imperium_a(name: str) -> None:
    assert name in _scope_ability_ids()
    assert PORTS[name].__module__.endswith("imperium_a")


_FLAGS: list[tuple[type[g.DeferredAbility], SelectionMode, bool, Timing]] = [
    (b.MakerKeeperBeneGesseritAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.MakerKeeperFremenAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.PivotalGambitAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.PriceIsNoObjectAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.PriorityContractsRevealAbility, SelectionMode.EXPLICIT, False, Timing.REVEAL),
    (b.PublicSpectacleAbility, SelectionMode.EXPLICIT, False, Timing.AGENT),
    (b.RebelSupplierAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.ReliableInformantAbility, SelectionMode.EXPLICIT, False, Timing.AGENT),
    (b.SardaukarCoordinationAgentAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.ShishakliAgentAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.CrysknifeAbility, SelectionMode.EXPLICIT, False, Timing.REVEAL),
    (b.SmugglersHarvesterAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.SmugglersHavenAgentAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.SmugglersHavenRevealAbility, SelectionMode.EXPLICIT, True, Timing.REVEAL),
    (b.SouthernEldersAgentAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.SpacetimeFoldingAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.SpacingGuildsFavorRevealAbility, SelectionMode.OPTIONAL, False, Timing.REVEAL),
    (b.SpyNetworkAbility, SelectionMode.OPTIONAL, False, Timing.REVEAL),
    (b.StrikeFleetAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.SubversiveAdvisorTrashSelfAbility, SelectionMode.IMPLICIT, True, Timing.AGENT),
    (b.TheBeastsSpoilsCrysknifeAbility, SelectionMode.EXPLICIT, False, Timing.AGENT),
    (b.TheBeastsSpoilsDesertMouseAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.TheBeastsSpoilsOrnithopterAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (b.TreacherousManeuverAbility, SelectionMode.OPTIONAL, False, Timing.AGENT),
    (b.BeneGesseritTrashAbility, SelectionMode.EXPLICIT, False, Timing.AGENT),
    (b.UndercoverAssetAbility, SelectionMode.EXPLICIT, False, Timing.REVEAL),
    (b.ShadoutMapesAbility, SelectionMode.OPTIONAL, False, Timing.REVEAL),
    (b.UnswervingLoyaltyAbility, SelectionMode.OPTIONAL, False, Timing.REVEAL),
    (b.WeirdingWomanAbility, SelectionMode.EXPLICIT, False, Timing.AGENT),
    (b.WheelsWithinWheelsEmperorAbility, SelectionMode.EXPLICIT, True, Timing.AGENT),
    (
        b.WheelsWithinWheelsSpacingGuildAbility,
        SelectionMode.EXPLICIT,
        True,
        Timing.AGENT,
    ),
]


@pytest.mark.parametrize(("cls", "mode", "auto", "timing"), _FLAGS)
def test_engine_side_members(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[g.DeferredAbility],
    mode: SelectionMode,
    auto: bool,
    timing: Timing,
) -> None:
    ability = cls(imperium("shishakli"))
    p = prof(turn_state)
    assert ability.selection_mode(p) == mode
    assert ability.always_run_immediately is auto
    assert ability.can_run_immediately(p) is auto
    assert ability.timing == timing


def test_triggered_and_reveal_timings() -> None:
    assert b.NorthernWatermasterBondAbility.timing == Timing.REVEAL
    assert b.ParacompassTriggeredAbility.timing == Timing.REVEAL
    assert b.SardaukarCoordinationTriggeredAbility.timing == Timing.REVEAL
    assert b.LietKynesAbility.timing == Timing.REVEAL
    assert b.SardaukarSoldierAbility.timing == Timing.NONE
    assert b.SpacingGuildsFavorDiscardAbility.timing == Timing.NONE
    assert b.SeekAlliesAgentAbility.timing == Timing.AGENT
    assert b.LietKynesRevealAbility.timing == Timing.REVEAL


# ---------------------------------------------------------------------------
# Maker Keeper / Wheels Within Wheels (influence-gated riders)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "influence", "value"),
    [
        (b.MakerKeeperBeneGesseritAbility, Influence(bene_gesserit=2), 1.0),
        (b.MakerKeeperFremenAbility, Influence(fremen=3), 0.5),
        (b.WheelsWithinWheelsEmperorAbility, Influence(emperor=2), 0.5),
        (b.WheelsWithinWheelsSpacingGuildAbility, Influence(spacing_guild=2), 0.5),
    ],
)
def test_influence_riders_need_two_influence(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[b._InfluenceRiderAbility],
    influence: Influence,
    value: float,
) -> None:
    ability = cls(imperium("maker_keeper"))
    assert ability.value_for_player(prof(turn_state), (space("arrakeen"),)).sum == 0.0
    assert not ability.meets_cost(prof(turn_state))
    one = with_player(
        turn_state,
        SEAT,
        influence=Influence(**{cls.FACTION: 1}),
    )
    assert ability.value_for_player(prof(one)).sum == 0.0
    allied = with_player(turn_state, SEAT, influence=influence)
    assert ability.value_for_player(prof(allied)).sum == value
    assert ability.meets_cost(prof(allied))
    # E: the inherited DeferredAbility::Evaluate (no DeferValue, Explicit -> 1).
    assert ability.evaluate(prof(allied), Request()) == Answer(
        1.0, (), f"{cls.__name__} defer"
    )


# ---------------------------------------------------------------------------
# Northern Watermaster, Crysknife (Shishakli), Unswerving Loyalty: Fremen
# ---------------------------------------------------------------------------


def test_northern_watermaster_bond_needs_another_fremen_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("northern_watermaster")
    bond = b.NorthernWatermasterBondAbility(owner)
    alone = hand(turn_state, owner, starter("dagger"))
    assert bond.value_for_player(prof(alone)).sum == 0.0
    # Another copy of the same card counts (only the owner is excluded).
    other = hand(turn_state, owner, imperium("northern_watermaster", 1))
    assert bond.value_for_player(prof(other)).sum == 1.0
    played = in_play(alone, imperium("maula_pistol"))
    assert bond.value_for_player(prof(played)).sum == 1.0
    # Reached through the reveal box as "Reveal Triggered": 1 Persuasion + 2 spice.
    reveal = g.RevealAbility(owner).value_for_player(prof(played))
    assert reveal.sum == pytest.approx(0.75 + 1.0)
    assert bond.bond_faction == "Fremen"


@pytest.mark.parametrize(
    "cls", [g.BondAbility, b.CrysknifeAbility, b.UnswervingLoyaltyAbility]
)
def test_fremen_deck_synergy(
    turn_state: GameState, prof: ProfileFactory, cls: type[Ability]
) -> None:
    owner = imperium("shishakli")
    ability = (
        b.NorthernWatermasterBondAbility(owner) if cls is g.BondAbility else cls(owner)
    )
    p = prof(turn_state)
    fremen = imperium("maula_pistol")
    assert ability.value_in_pile_for_other_play(p, Pile.DECK, fremen).sum == 0.5
    assert (
        ability.value_in_pile_for_other_play(p, Pile.DECK, imperium("truthtrance")).sum
        == 0.0
    )
    assert ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, fremen).sum == 0.0
    climax = prof(turn_state, is_climax=lambda: True)
    assert ability.value_in_pile_for_other_play(climax, Pile.DECK, fremen).sum == 0.0


def test_crysknife_influence_and_defer_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("shishakli")
    knife = b.CrysknifeAbility(owner)
    alone = hand(turn_state, owner)
    assert knife.value_for_player(prof(alone)).sum == 0.0
    bonded = hand(turn_state, owner, imperium("unswerving_loyalty"))
    assert knife.value_for_player(prof(bonded)).sum == 1.0  # Fremen +1
    # E: DeferredAbility::Evaluate with Shishakli's DeferValue 2.
    assert knife.evaluate(prof(bonded), Request()).value == 2.0


# ---------------------------------------------------------------------------
# Paracompass
# ---------------------------------------------------------------------------


def test_paracompass_persuasion_needs_a_high_council_seat(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("paracompass")
    trigger = b.ParacompassTriggeredAbility(owner)
    assert trigger.value_for_player(prof(turn_state)).sum == 0.0
    seated = with_player(turn_state, SEAT, high_council=True)
    assert trigger.value_for_player(prof(seated)).sum == 1.5
    sword = with_player(seated, SEAT, swordmaster_acquired=True, agents_available=3)
    assert trigger.value_for_player(prof(sword)).sum == pytest.approx(2.25)
    # The reveal box has no printed resources: its value is the trigger's.
    reveal = b.ParacompassRevealAbility(owner).value_for_player(prof(sword))
    assert reveal.sum == pytest.approx(2.25)


# ---------------------------------------------------------------------------
# Pivotal Gambit, The Beast's Spoils (promos)
# ---------------------------------------------------------------------------


def test_pivotal_gambit_copies_smugglers_haven(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gambit = b.PivotalGambitAbility(synth("pivotal_gambit"))
    p = prof(turn_state)
    assert gambit.value_for_player(p, (space("arrakeen"),)).sum == -2.0 + 6.0
    assert gambit.evaluate(p, Request()).value == 100.0


def test_beasts_spoils_icon_riders(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = synth("the_beasts_spoils")
    mouse = b.TheBeastsSpoilsDesertMouseAbility(owner)
    thopter = b.TheBeastsSpoilsOrnithopterAbility(owner)
    knife = b.TheBeastsSpoilsCrysknifeAbility(owner)
    p = prof(turn_state)  # seat 3 holds the Desert Mouse objective
    assert mouse.value_for_player(p).sum == 0.5
    assert thopter.value_for_player(p).sum == 0.0
    assert not knife.meets_cost(p)
    assert knife.value_for_player(p).sum == 2.75 + 1.0  # not gated by the icon
    thopter_won = won(turn_state, "skirmish_ornithopter")
    assert thopter.value_for_player(prof(thopter_won)).sum == pytest.approx(0.9)
    flipped = with_player(
        turn_state, SEAT, face_down_battle_card_ids=("objective_desert_mouse",)
    )
    assert mouse.value_for_player(prof(flipped)).sum == 0.0
    knifed = won(turn_state, "skirmish_crysknife")
    assert knife.meets_cost(prof(knifed))
    assert mouse.evaluate(p, Request()).value == 100.0
    assert thopter.evaluate(p, Request()).value == 100.0


# ---------------------------------------------------------------------------
# Price Is No Object
# ---------------------------------------------------------------------------


def _row(state: GameState, *names: str) -> GameState:
    return with_state(state, imperium_row=tuple(f"imperium:{n}:0" for n in names))


def test_price_is_no_object_value_picks_the_best_affordable_row_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    values = {"imperium:truthtrance:0": 4.0, "imperium:spy_network:0": 4.0}
    values["imperium:steersman:0"] = 9.0
    acquire = lambda card: Summer(values.get(card.ref, 1.0))  # noqa: E731
    state = _row(turn_state, "spy_network", "truthtrance", "steersman")
    rich = with_player(state, SEAT, resources=Resources(solari=6, water=1))
    ability = b.PriceIsNoObjectAbility(imperium("price_is_no_object"))
    v = ability.value_for_player(prof(rich, acquire_value=acquire), ())
    # Steersman (8) is unaffordable; Spy Network (first maximum) beats Truthtrance.
    assert v.sum == pytest.approx(4.0 - 0.25 * 2)
    # High Council costs 5 Solari: 1 left, nothing affordable.
    at_council = ability.value_for_player(
        prof(rich, acquire_value=acquire), (space("high_council"),)
    )
    assert at_council.sum == 0.0
    # The net value is added even when negative.
    cheap = lambda card: Summer(0.1)  # noqa: E731
    neg = ability.value_for_player(prof(rich, acquire_value=cheap), ())
    assert neg.sum == pytest.approx(0.1 - 0.5)


def test_price_is_no_object_evaluate_first_strict_best(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.PriceIsNoObjectAbility(imperium("price_is_no_object"))
    a, c, d = imperium("truthtrance"), imperium("spy_network"), imperium("overthrow")
    values = {a.ref: 2.0, c.ref: 1.5, d.ref: 5.0}
    p = prof(turn_state, acquire_value=lambda card: Summer(values[card.ref]))
    # truthtrance 2.0 - 1.0 = 1.0; spy_network 1.5 - 0.5 = 1.0 (tie: first kept);
    # overthrow 5.0 - 2.0 = 3.0.
    assert ability.evaluate(p, req(a, c)) == Answer(
        1.0, ((a.ref,),), f"Price Is No Object {a.ref}"
    )
    assert ability.evaluate(p, req(a, c, d)).response == ((d.ref,),)
    assert ability.evaluate(p, req()) == Answer(
        0.0, None, "Price Is No Object no target"
    )


def test_price_is_no_object_worked_example(
    turn_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """17 §4: Hard, Early, a 5-cost card at AcquireValue 4.8 costs 5.72
    Solari-value with 6 Solari (declined), 1.43 with 9 (bought) and 3.58
    with the Swordmaster."""

    card = imperium("truthtrance")  # cost 4: use a synthetic 5-cost card
    card = Entity(
        Kind.CARD,
        card.ref,
        Archetype(
            short="Test.five",
            kind="test",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType({"PersuasionCost": 5}),
        ),
        None,
    )
    ability = b.PriceIsNoObjectAbility(imperium("price_is_no_object"))

    def evaluate(**changes: object) -> float:
        state = with_player(turn_state, SEAT, **changes)
        p = make_profile(state, SEAT)
        monkeypatch.setattr(p, "acquire_value", lambda c: Summer(4.8))
        return ability.evaluate(p, req(card)).value

    assert evaluate(resources=Resources(solari=6, water=1)) == pytest.approx(-0.92)
    assert evaluate(resources=Resources(solari=9, water=1)) == pytest.approx(3.37)
    assert evaluate(
        resources=Resources(solari=6, water=1),
        swordmaster_acquired=True,
        agents_available=3,
    ) == pytest.approx(4.8 - 3.575)


def test_price_is_no_object_cost(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = b.PriceIsNoObjectAbility(imperium("price_is_no_object"))
    state = _row(turn_state, "overthrow")
    assert not ability.meets_cost(prof(state))  # 0 Solari: no reserve card either
    two = with_player(state, SEAT, resources=Resources(solari=2, water=1))
    assert ability.meets_cost(prof(two))  # Prepare the Way (reserve, cost 2)


# ---------------------------------------------------------------------------
# Priority Contracts
# ---------------------------------------------------------------------------


def _complete_contracts(state: GameState, count: int) -> GameState:
    """Seat 3 has completed ``count`` contracts taken from the bank."""

    taken = state.contract_bank[:count]
    state = with_state(
        state, contract_bank=tuple(c for c in state.contract_bank if c not in taken)
    )
    return with_player(state, SEAT, completed_contract_ids=taken)


def test_priority_contracts_reveal_two_spice_or_vp(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.PriorityContractsRevealAbility(imperium("priority_contracts"))
    assert ability.spice_amount == 2
    assert DeliveryAgreementRevealAbility.spice_amount == 1
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == 1.0  # GetSpiceValue(2)
    answer = ability.evaluate(p, req(options=(0,)))
    assert (answer.value, answer.response) == (1.0, ((0,),))
    three = prof(_complete_contracts(turn_state, 3))
    assert ability.value_for_player(three).sum == 1.0
    four_state = _complete_contracts(turn_state, 4)
    four = prof(four_state)
    assert ability.value_for_player(four).sum == 6.0
    answer = ability.evaluate(four, req(options=(0, 1)))
    assert (answer.value, answer.response) == (6.0, ((1,),))
    # The spice replaces the VP only when strictly greater: ties keep the VP.
    tie = prof(four_state, victory_point_value=lambda n: 1.0 * n)
    assert ability.evaluate(tie, req(options=(0, 1))).response == ((1,),)
    cheap_vp = prof(four_state, victory_point_value=lambda n: 0.5 * n)
    assert ability.evaluate(cheap_vp, req(options=(0, 1))).response == ((0,),)


# ---------------------------------------------------------------------------
# Public Spectacle, Spacing Guild's Favor (GainAnyInfluenceAbility)
# ---------------------------------------------------------------------------


def test_public_spectacle_value_is_not_gated_by_the_recall(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.PublicSpectacleAbility(imperium("public_spectacle"))
    p = prof(turn_state)
    assert turn_state.players[SEAT].spies_recalled_turn == 0
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 3.0
    tracks = [track_entity(f) for f in FACTIONS]
    answer = ability.evaluate(p, req(*tracks))
    assert answer.value == 103.0
    assert answer.response == (("bene_gesserit",),)


def test_spacing_guilds_favor_counts_influence_twice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SpacingGuildsFavorRevealAbility(imperium("spacing_guild_s_favor"))
    p = prof(turn_state)
    assert turn_state.players[SEAT].resources.spice == 0  # no affordability test
    assert ability.value_for_player(p).sum == pytest.approx(3.0 - 1.5 + 3.0)


def test_spacing_guilds_favor_evaluate_prices_the_spice(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SpacingGuildsFavorRevealAbility(imperium("spacing_guild_s_favor"))
    p = prof(turn_state)
    tracks = [track_entity(f) for f in FACTIONS]
    answer = ability.evaluate(p, req(*tracks))
    assert answer.value == pytest.approx(3.0 - 1.5)
    assert answer.response == (("bene_gesserit",),)
    # Equal values: the first track sticks.
    flat = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(1.0)
    )
    assert ability.evaluate(flat, req(*tracks)).response == (("emperor",),)
    # Worth less than the spice: still the best, at a value <= 0 (declined).
    poor = prof(
        turn_state, gain_influence_value=lambda f, n, r=-1, a=False: Summer(0.5)
    )
    assert ability.evaluate(poor, req(*tracks)).value == pytest.approx(-1.0)
    assert ability.evaluate(p, req()).response is None


# ---------------------------------------------------------------------------
# Rebel Supplier / Strike Fleet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "troops"), [(b.RebelSupplierAbility, 2), (b.StrikeFleetAbility, 3)]
)
def test_recalled_spy_troops(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[b._RecalledSpyTroopsAbility],
    troops: int,
) -> None:
    ability = cls(imperium("strike_fleet"))
    p = prof(turn_state)
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    assert ability.costed_troops(p) == 0
    assert not ability.meets_cost(p)
    recalled = prof(with_player(turn_state, SEAT, spies_recalled_turn=1))
    assert ability.value_for_player(recalled).sum == pytest.approx(0.9 * troops)
    assert ability.costed_troops(recalled) == troops
    assert ability.meets_cost(recalled)
    assert ability.evaluate(recalled, Request()).value == 100.0


# ---------------------------------------------------------------------------
# Reliable Informant
# ---------------------------------------------------------------------------


def test_reliable_informant_scales_the_spy_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.ReliableInformantAbility(imperium("reliable_informant"))
    p = prof(turn_state)
    expected = 1.66 + (0.66 * 1.66 - 1.66)  # AIProfileAbsUtils::Multiply
    assert ability.value_for_player(p).sum == expected
    assert ability.is_valid_observation_post(p, "emperor-sardaukar-dutiful-service")
    assert ability.is_valid_observation_post(p, "fremen-desert-tactics-fremkit")
    assert not ability.is_valid_observation_post(
        p, "spacing-guild-heighliner-deliver-supplies"
    )
    assert not ability.is_valid_observation_post(p, "arrakis-hagga-basin")
    # E is PlaceSpyAbility's.
    assert ability.evaluate(p, Request()).value == 1.66


def test_reliable_informant_without_valid_posts_is_zero(
    turn_state: GameState, prof: ProfileFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    ability = b.ReliableInformantAbility(imperium("reliable_informant"))
    monkeypatch.setattr(ability, "is_valid_observation_post", lambda p, post: False)
    assert ability.value_for_player(prof(turn_state)).sum == 0.0


# ---------------------------------------------------------------------------
# Sardaukar Coordination
# ---------------------------------------------------------------------------


def test_sardaukar_coordination_reveal_counts_emperor_cards_in_hand(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("sardaukar_coordination")
    reveal = b.SardaukarCoordinationRevealAbility(owner)
    none = hand(turn_state, starter("dagger"))
    assert reveal.value_for_player(prof(none)).sum == 1.5  # 2 Persuasion, n = 0
    state = hand(turn_state, owner, imperium("spy_network"), starter("dagger"))
    state = in_play(state, imperium("sardaukar_soldier"))  # not counted
    assert reveal.value_for_player(prof(state)).sum == pytest.approx(1.5 + 2 * 0.66)


def test_sardaukar_coordination_agent_inherits_deploy_units(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("sardaukar_coordination")
    deploy = b.SardaukarCoordinationAgentAbility(owner)
    p = prof(turn_state)
    assert deploy.value_for_player(p, (space("arrakeen"),)).sum == 1.25
    request = Request((TargetInfo((), (0, 1, 2), 0, 2),))
    assert deploy.evaluate(p, request).response == ((0, 1),)
    # The triggered strength has no AI hook: the reveal sum gets 0 from it.
    assert b.SardaukarCoordinationTriggeredAbility(owner).value_for_player(p).sum == 0.0


# ---------------------------------------------------------------------------
# Seek Allies, Weirding Woman agent box
# ---------------------------------------------------------------------------


def test_seek_allies_adds_its_mod_to_the_agent_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = starter("seek_allies")
    p = prof(turn_state)
    base = g.AgentAbility(owner).value_for_player(p, (space("arrakeen"),)).sum
    value = b.SeekAlliesAgentAbility(owner).value_for_player(p, (space("arrakeen"),))
    assert value.sum == pytest.approx(base + 0.33)


def test_weirding_woman_agent_box_is_generic(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("weirding_woman")
    p = prof(turn_state)
    generic = g.AgentAbility(owner).value_for_player(p, (space("secrets"),)).sum
    port = b.WeirdingWomanAgentAbility(owner).value_for_player(p, (space("secrets"),))
    assert port.sum == generic


# ---------------------------------------------------------------------------
# Shishakli
# ---------------------------------------------------------------------------


def test_shishakli_value(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = b.ShishakliAgentAbility(imperium("shishakli"))
    assert ability.value_for_player(prof(turn_state)).sum == pytest.approx(
        2.75 + 1.0 + 1.5 + 0.3
    )


def test_shishakli_evaluate_trashes_junk_first(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.ShishakliAgentAbility(imperium("shishakli"))
    dagger, ca = starter("dagger"), starter("convincing_argument")
    p = prof(turn_state, card_to_trash=lambda t, m: (t[0], 10.08))
    assert ability.evaluate(p, req(dagger, ca)) == Answer(
        10.08 + 1.8, ((dagger.ref,),), f"Shishakli trash {dagger.ref}"
    )


def test_shishakli_evaluate_without_junk_takes_the_lowest_acquire_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.ShishakliAgentAbility(imperium("shishakli"))
    sig, ca, ra = (
        starter("signet_ring"),
        starter("convincing_argument"),
        starter("reconnaissance"),
    )
    values = {sig.ref: 3.0, ca.ref: 0.0, ra.ref: 0.0}
    p = prof(turn_state, acquire_value=lambda c: Summer(values[c.ref]))
    answer = ability.evaluate(p, req(sig, ca, ra))
    assert answer.value == pytest.approx(1.0 + 1.8)  # minTrashValue + draw
    assert answer.response == ((ca.ref,),)  # first minimum in target order
    assert ability.evaluate(p, req()).response is None


def test_shishakli_evaluate_with_the_real_trash_ranking(
    turn_state: GameState,
) -> None:
    ability = b.ShishakliAgentAbility(imperium("shishakli"))
    p = make_profile(turn_state, SEAT)
    cards = [starter("signet_ring"), starter("dagger"), starter("diplomacy")]
    answer = ability.evaluate(p, req(*cards))
    assert answer.response == ((cards[1].ref,),)
    assert answer.value > 10.0


# ---------------------------------------------------------------------------
# Smuggler's Harvester / Smuggler's Haven
# ---------------------------------------------------------------------------


def test_smugglers_harvester_counts_maker_spaces_only(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SmugglersHarvesterAbility(imperium("smuggler_s_harvester"))
    p = prof(turn_state)
    assert ability.value_for_player(p, (space("hagga_basin"),)).sum == 0.5
    assert ability.value_for_player(p, (space("imperial_basin"),)).sum == 0.5
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    assert ability.value_for_player(p, ()).sum == 0.0
    assert ability.evaluate(p, Request()).value == 100.0
    # Merged into the agent value of the card at that space.
    agent = g.AgentAbility(imperium("smuggler_s_harvester"))
    at_maker = agent.value_for_player(p, (space("hagga_basin"),)).sum
    elsewhere = agent.value_for_player(p, (space("arrakeen"),)).sum
    assert at_maker - elsewhere == pytest.approx(0.5)


def test_smugglers_haven_agent_inverted_affordability(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SmugglersHavenAgentAbility(imperium("smuggler_s_haven"))
    # The real CanAgentAbilityBePlayedWithSpace (true = affordable).
    poor = prof(turn_state)
    assert (
        poor.can_agent_ability_be_played_with_space(space("arrakeen"), Attr.SPICE, 4)
        is False
    )
    assert ability.value_for_player(poor, (space("arrakeen"),)).sum == -2.0 + 6.0
    rich_state = with_player(turn_state, SEAT, resources=Resources(spice=4, water=1))
    rich = prof(rich_state)
    assert ability.value_for_player(rich, (space("arrakeen"),)).sum == 0.0
    assert ability.value_for_player(poor, ()).sum == 0.0
    assert ability.evaluate(poor, Request()).value == 100.0


def test_smugglers_haven_reveal_needs_a_spy_on_a_maker_space(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SmugglersHavenRevealAbility(imperium("smuggler_s_haven"))
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    elsewhere = with_player(
        turn_state,
        SEAT,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
        spies_supply=2,
    )
    assert ability.value_for_player(prof(elsewhere)).sum == 0.0
    assert not ability.meets_cost(prof(elsewhere))
    maker = with_player(
        turn_state, SEAT, spy_post_ids=("arrakis-hagga-basin",), spies_supply=2
    )
    assert ability.value_for_player(prof(maker)).sum == 1.0
    assert ability.meets_cost(prof(maker))
    assert ability.evaluate(prof(maker), Request()).value == 100.0


# ---------------------------------------------------------------------------
# Southern Elders agent, Tread in Darkness trash, Weirding Woman: Bene Gesserit
# ---------------------------------------------------------------------------


def test_southern_elders_troops_need_another_bg_card_in_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("southern_elders")
    ability = b.SouthernEldersAgentAbility(owner)
    assert ability.value_for_player(prof(turn_state), (space("secrets"),)).sum == 0.0
    in_hand = hand(turn_state, owner, imperium("truthtrance"))
    assert ability.value_for_player(prof(in_hand)).sum == 0.0  # hand does not count
    only_owner = in_play(turn_state, owner)
    assert ability.value_for_player(prof(only_owner)).sum == 0.0
    assert ability.costed_troops(prof(only_owner)) == 0
    played = in_play(turn_state, imperium("truthtrance"))
    assert ability.value_for_player(prof(played)).sum == pytest.approx(1.8)
    assert ability.costed_troops(prof(played)) == 2
    assert ability.evaluate(prof(played), Request()).value == 100.0


@pytest.mark.parametrize(
    ("cls", "played"),
    [
        (b.SouthernEldersAgentAbility, 1.8),
        (b.BeneGesseritTrashAbility, 0.75 * 2.75),
        (b.WeirdingWomanAbility, 0.75 * (0.75 + 0.66 + 0.5)),
    ],
)
def test_bene_gesserit_played_synergy(
    turn_state: GameState,
    prof: ProfileFactory,
    cls: type[Ability],
    played: float,
) -> None:
    ability = cls(imperium("weirding_woman"))
    bg_card = imperium("truthtrance")
    p = prof(turn_state)
    assert ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, bg_card).sum == (
        pytest.approx(played)
    )
    assert (
        ability.value_in_pile_for_other_play(p, Pile.PLAY_AREA, starter("dagger")).sum
        == 0.0
    )
    bg_in_play = prof(in_play(turn_state, imperium("prepare_the_way")))
    assert (
        ability.value_in_pile_for_other_play(bg_in_play, Pile.PLAY_AREA, bg_card).sum
        == 0.0
    )
    one_agent = prof(
        with_player(turn_state, SEAT, agents_available=1, agent_locations=("secrets",))
    )
    assert (
        ability.value_in_pile_for_other_play(one_agent, Pile.PLAY_AREA, bg_card).sum
        == 0.0
    )
    assert ability.value_in_pile_for_other_play(p, Pile.DECK, bg_card).sum == 0.75
    climax = prof(turn_state, is_climax=lambda: True)
    assert ability.value_in_pile_for_other_play(climax, Pile.DECK, bg_card).sum == 0.0


def test_bene_gesserit_trash_value_and_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("tread_in_darkness")
    trash = b.BeneGesseritTrashAbility(owner)
    assert trash.value_for_player(prof(turn_state)).sum == 0.0
    played = prof(in_play(turn_state, imperium("truthtrance")))
    assert trash.value_for_player(played).sum == 2.75 + 1.0
    # E: TrashAbility's (no junk: 1.0 and trash nothing).
    assert trash.evaluate(played, req(starter("signet_ring"))) == Answer(
        1.0, ((),), "Trash nothing"
    )


def test_weirding_woman_returns_to_hand_with_another_bg_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("weirding_woman")
    ability = b.WeirdingWomanAbility(owner)
    assert ability.value_for_player(prof(turn_state)).sum == 0.0
    played = prof(in_play(turn_state, owner, imperium("truthtrance")))
    # Its own reveal box: 1 Persuasion + 1 Strength; + WeirdingWomanMod 0.5.
    assert ability.value_for_player(played).sum == pytest.approx(0.75 + 0.66 + 0.5)
    assert ability.evaluate(played, Request()) == Answer(
        100.0, (), "Weirding Woman | 100"
    )
    assert ability.is_unexhausted


# ---------------------------------------------------------------------------
# Space-Time Folding
# ---------------------------------------------------------------------------


def test_space_time_folding_value(turn_state: GameState, prof: ProfileFactory) -> None:
    owner = imperium("space_time_folding")
    ability = b.SpacetimeFoldingAbility(owner)
    one = hand(turn_state, owner)
    assert ability.value_for_player(prof(one), (space("secrets"),)).sum == 0.0
    base = -1.0 + 1.5 + 0.3
    two = hand(turn_state, owner, starter("dagger"))
    assert ability.value_for_player(prof(two), (space("secrets"),)).sum == (
        pytest.approx(base)
    )
    guild = hand(turn_state, owner, imperium("smuggler_s_harvester"), starter("dagger"))
    seen: list[list[str]] = []

    def order(cards: Sequence[Entity], bonus: bool) -> list[Entity]:
        assert bonus is True
        seen.append([c.ref for c in cards])
        return list(cards)

    p = prof(guild, discard_order=order)
    assert ability.value_for_player(p, (space("secrets"),)).sum == pytest.approx(
        base + 1.5 + 0.3
    )
    assert seen == [["imperium:smuggler_s_harvester:0", starter("dagger").ref]]
    # Without a candidate space the bonus draw is not looked at.
    assert ability.value_for_player(p, ()).sum == pytest.approx(base)
    assert len(seen) == 1


def test_space_time_folding_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SpacetimeFoldingAbility(imperium("space_time_folding"))
    p = prof(turn_state)
    dagger, harvester = starter("dagger"), imperium("smuggler_s_harvester")
    assert ability.evaluate(p, req(dagger, harvester)) == Answer(
        pytest.approx(0.8),  # type: ignore[arg-type]
        ((dagger.ref,),),
        f"Space-time Folding discard {dagger.ref}",
    )
    guild_first = ability.evaluate(p, req(harvester, dagger))
    assert guild_first.value == pytest.approx(0.8 + 1.8)
    assert guild_first.response == ((harvester.ref,),)
    assert ability.evaluate(p, req()).response is None


def test_space_time_folding_with_the_real_discard_order(
    turn_state: GameState,
) -> None:
    ability = b.SpacetimeFoldingAbility(imperium("space_time_folding"))
    p = make_profile(turn_state, SEAT)
    # spacingGuildBonus: the cheap Guild card is discarded before a Dagger.
    cards = [starter("dagger"), imperium("smuggler_s_harvester")]
    assert ability.evaluate(p, req(*cards)).response == ((cards[1].ref,),)


# ---------------------------------------------------------------------------
# Spy Network
# ---------------------------------------------------------------------------


def test_spy_network(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = b.SpyNetworkAbility(imperium("spy_network"))
    one = with_player(
        turn_state, SEAT, spy_post_ids=("arrakis-hagga-basin",), spies_supply=2
    )
    assert ability.value_for_player(prof(one)).sum == 0.0
    assert not ability.meets_cost(prof(one))
    posts = ("arrakis-hagga-basin", "arrakis-deep-desert")
    two = with_player(turn_state, SEAT, spy_post_ids=posts, spies_supply=1)
    p = prof(two)
    assert ability.value_for_player(p).sum == pytest.approx(-1.66 + 2.25)
    spies = [spy_entity(post, SEAT) for post in posts]
    answer = ability.evaluate(p, req(*spies))
    assert answer.value == pytest.approx(2.25 - 1.66)
    assert answer.response == ((posts[0],),)
    assert ability.evaluate(p, req()).response is None


# ---------------------------------------------------------------------------
# Stilgar, The Devoted
# ---------------------------------------------------------------------------


def test_liet_kynes_reveal_counts_fremen_cards_in_hand_and_play(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("stilgar_the_devoted")
    reveal = b.LietKynesRevealAbility(owner)
    state = hand(turn_state, owner, imperium("maula_pistol"), starter("dagger"))
    state = in_play(state, imperium("shishakli"))
    assert reveal.value_for_player(prof(state)).sum == pytest.approx(0.75 * 6)
    nothing = hand(turn_state, starter("dagger"))
    assert reveal.value_for_player(prof(nothing)).sum == 0.0
    assert b.LietKynesAbility(owner).value_for_player(prof(state)).sum == 0.0


# ---------------------------------------------------------------------------
# Subversive Advisor
# ---------------------------------------------------------------------------


def test_subversive_advisor_trash_needs_a_faction_space(
    effects_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.SubversiveAdvisorTrashSelfAbility(imperium("subversive_advisor"))
    assert not ability.meets_cost(prof(effects_state))  # Arrakeen
    faction = with_frame(effects_state, space_id="sardaukar")
    assert ability.meets_cost(prof(faction))
    assert ability.value_for_player(prof(faction), (space("sardaukar"),)).sum == 0.0
    # Cost @0x4d45110: a null PlayedSpace is true (je -> mov r15b, 1).
    assert b._active_space(prof(turn_state)) is None
    assert ability.meets_cost(prof(turn_state))


def test_subversive_advisor_placement_values_the_extra_influence(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    agent = g.PowerPlayAgentAbility(imperium("subversive_advisor"))
    p = prof(turn_state)
    at_faction = agent.value_for_player(p, (space("secrets"),)).sum
    plain = g.AgentAbility(imperium("subversive_advisor"))
    assert at_faction - plain.value_for_player(p, (space("secrets"),)).sum == 3.0


# ---------------------------------------------------------------------------
# Treacherous Maneuver
# ---------------------------------------------------------------------------


def _counting_trash(calls: list[float]) -> Callable[..., tuple[None, float]]:
    def trash(targets: Sequence[Entity], minimum: float) -> tuple[None, float]:
        calls.append(minimum)
        return None, minimum

    return trash


def test_treacherous_maneuver_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("treacherous_maneuver")
    ability = b.TreacherousManeuverAbility(owner)
    calls: list[float] = []
    alone = hand(turn_state, owner, starter("dagger"))
    p = prof(alone, card_to_trash=_counting_trash(calls))
    assert ability.value_for_player(p, (space("sardaukar"),)).sum == 0.0
    assert calls == []  # no Emperor card: returns before GetCardToTrash
    cheap = hand(turn_state, owner, imperium("spy_network"))
    p = prof(cheap, card_to_trash=_counting_trash(calls))
    # GetCardToTrash runs (and shuffles) before the space test.
    assert ability.value_for_player(p, ()).sum == 0.0
    assert calls == [0.0]
    assert ability.value_for_player(p, (space("sardaukar"),)).sum == 2.0
    assert ability.value_for_player(p, (space("arrakeen"),)).sum == 0.0
    dear = hand(turn_state, owner, imperium("public_spectacle"))
    assert ability.value_for_player(prof(dear), (space("sardaukar"),)).sum == 0.0
    climax = prof(dear, is_climax=lambda: True)
    assert ability.value_for_player(climax, (space("sardaukar"),)).sum == 2.0
    junk = prof(dear, card_to_trash=lambda t, m: (t[0], 1.0))
    assert ability.value_for_player(junk, (space("sardaukar"),)).sum == 2.0


def test_treacherous_maneuver_evaluate(
    turn_state: GameState, effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.TreacherousManeuverAbility(imperium("treacherous_maneuver"))
    dear, cheap = imperium("public_spectacle"), imperium("sardaukar_soldier")
    calls: list[float] = []
    no_space = prof(turn_state, card_to_trash=_counting_trash(calls))
    assert ability.evaluate(no_space, req(cheap)).value == 0.0
    assert calls == [0.0]
    at_space = with_frame(effects_state, space_id="sardaukar")
    p = prof(at_space)
    assert ability.evaluate(p, req(dear, cheap)) == Answer(
        200.0, ((cheap.ref,),), f"Treacherous Maneuver | 200 | {cheap.ref}"
    )
    assert ability.evaluate(p, req(dear)).response is None
    climax = prof(at_space, is_climax=lambda: True)
    assert ability.evaluate(climax, req(dear)).response == ((dear.ref,),)
    junk = prof(at_space, card_to_trash=lambda t, m: (t[0], 1.0))
    assert ability.evaluate(junk, req(dear, cheap)).response == ((dear.ref,),)


def test_treacherous_maneuver_cost(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    owner = imperium("treacherous_maneuver")
    ability = b.TreacherousManeuverAbility(owner)
    state = with_frame(effects_state, space_id="sardaukar")
    state = hand(state, owner, imperium("spy_network"))
    assert ability.meets_cost(prof(state))
    assert not ability.meets_cost(prof(hand(state, owner)))
    arrakeen = with_frame(state, space_id="arrakeen")
    assert not ability.meets_cost(prof(arrakeen))


# ---------------------------------------------------------------------------
# Undercover Asset
# ---------------------------------------------------------------------------


def test_undercover_asset_spy_or_strength(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.UndercoverAssetAbility(imperium("undercover_asset"))
    p = prof(turn_state)
    assert ability.value_for_player(p).sum == 1.66
    assert ability.evaluate(p, req(options=(0, 1))) == Answer(
        1.66, ((0,),), "Undercover Asset Place Spy"
    )
    strong = prof(turn_state, strength_value=lambda n, i=False: 1.0 * n)
    assert ability.value_for_player(strong).sum == 2.0
    assert ability.evaluate(strong, req(options=(0, 1))).response == ((1,),)
    tie = prof(turn_state, strength_value=lambda n, i=False: 0.83 * n)
    assert ability.evaluate(tie, req(options=(0, 1))).response == ((0,),)


# ---------------------------------------------------------------------------
# Unswerving Loyalty (Shadout Mapes)
# ---------------------------------------------------------------------------


def test_unswerving_loyalty_value_is_constant(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.UnswervingLoyaltyAbility(imperium("unswerving_loyalty"))
    assert ability.value_for_player(prof(turn_state)).sum == 1.0
    # Reached through the reveal box: 1 Persuasion + 1 Troop + 1.0 deferred.
    reveal = g.RevealAbility(imperium("unswerving_loyalty"))
    assert reveal.value_for_player(prof(turn_state)).sum == pytest.approx(
        0.75 + 0.9 + 1.0
    )


def test_unswerving_loyalty_evaluate_branches(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = b.UnswervingLoyaltyAbility(imperium("unswerving_loyalty"))
    both = with_player(
        turn_state, SEAT, troops_garrison=2, troops_conflict=1, troops_supply=9
    )
    deploy = prof(both)
    assert ability.evaluate(deploy, req(options=(0, 1))).response == ((0,),)
    assert ability.evaluate(deploy, Request()).value == 100.0
    # Garrison but no deploy wish: the retreat index is 1 (app edge case).
    retreat = prof(both, units_to_deploy=lambda u, m: 0, troops_to_retreat=lambda m: 1)
    assert ability.evaluate(retreat, req(options=(0, 1))).response == ((1,),)
    # No garrison troop: retreat is option 0.
    deployed_only = with_player(
        turn_state, SEAT, troops_garrison=0, troops_conflict=1, troops_supply=11
    )
    only = prof(deployed_only, troops_to_retreat=lambda m: 1)
    assert ability.evaluate(only, req(options=(0,))).response == ((0,),)
    keep = prof(both, units_to_deploy=lambda u, m: 0)
    assert ability.evaluate(keep, Request()) == Answer(
        0.0, (), "Shadout Mapes (Reveal) | 0"
    )


# ---------------------------------------------------------------------------
# Real profile: every M–Z card's hooks run on a live state
# ---------------------------------------------------------------------------


def _m_to_z_cards() -> list[str]:
    return [
        card
        for card, short in CARD_ARCHETYPES.items()
        if short in ARCHETYPES and (ARCHETYPES[short].title or "")[:1].upper() >= "M"
    ]


def test_real_profile_smoke(turn_state: GameState) -> None:
    cards = [imperium(c) for c in _m_to_z_cards()]
    state = hand(turn_state, *cards[:5])
    state = in_play(state, *cards[5:9])
    state = with_player(
        state,
        SEAT,
        resources=Resources(solari=7, spice=5, water=2),
        influence=Influence(emperor=2, spacing_guild=2, bene_gesserit=2, fremen=2),
        spy_post_ids=("arrakis-hagga-basin", "emperor-sardaukar-dutiful-service"),
        spies_supply=1,
        spies_recalled_turn=1,
        troops_conflict=1,
        troops_supply=8,
    )
    p = make_profile(state, SEAT)
    tracks = req(*(track_entity(f) for f in FACTIONS))
    for card in cards:
        for ability in abilities_of(card):
            if not type(ability).__module__.endswith("imperium_b"):
                continue
            for entities in ((), (space("hagga_basin"),), (space("sardaukar"),)):
                assert math.isfinite(ability.value_for_player(p, entities).sum)
            for pile in (Pile.DECK, Pile.PLAY_AREA):
                for other in (imperium("truthtrance"), imperium("maula_pistol")):
                    value = ability.value_in_pile_for_other_play(p, pile, other)
                    assert math.isfinite(value.sum)
            for request in (Request(), tracks, req(*cards[:3])):
                assert math.isfinite(ability.evaluate(p, request).value)
