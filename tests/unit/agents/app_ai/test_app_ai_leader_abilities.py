"""Leader ability ports: spec/leaders.md (abilities/leaders.py).

Every test builds a real ``GameState`` (``app_ai.testing``), adjusts the
fields a formula reads, and (except the worked examples, which use the real
profile) stubs the ``Profile`` methods other areas own with simple linear
prices so each expected value can be checked by hand.
"""

from collections.abc import Callable
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import pytest

from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.abilities import leaders as ld
from dune_imperium.agents.app_ai.abilities.base import (
    PORTS,
    Ability,
    Request,
    SelectionMode,
    TargetInfo,
    Timing,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.catalog import (
    LEADER_ARCHETYPES,
    POST_INDEX,
    card_entity,
    leader_entity,
    space_entity,
    spy_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.agents.app_ai.entities import Attr, Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import IntSummer, Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.content.uprising.leaders import FEYD_TRACK_BY_ID, FeydTrackReward
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules.leader_abilities import (
    apply_feyd_track_action,
    apply_leader_signet_spy,
    legal_feyd_track_actions,
    legal_leader_signet_actions,
)

SEAT = 3  # seed 1: seat 3 (Lady Jessica) decides first in each window used
AA = "worm.canis.abilities.ActivatedAbilities."
AU = AA + "Uprising."
TU = "worm.canis.abilities.TriggeredAbilities.Uprising."
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


def _base_stubs() -> dict[str, Callable[..., Any]]:
    return {
        "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: 1.0 * n,
        "troop_value": lambda n, include=False: 0.9 * n,
        "strength_value": lambda n, include=False: 0.66 * n,
        "intrigue_value": lambda: 2.25,
        "trash_card_value": lambda: 2.75,
        "trash_mod": lambda: 1.0,
        "spy_value": lambda: Summer(1.66),
        "recall_spy_value": lambda: Summer(-1.66),
        "recall_spy": lambda spies: (spies[0], 0.5) if spies else (None, 0.0),
        "card_draw_value": lambda: 1.5,
        "possible_persuasion_gain": lambda: 3,
        "buy_gains": lambda n: 0.1 * n,
        "card_draw_value_with_buy_gains": lambda: 1.8,
        "gain_influence_value": lambda f, n, rank=-1, alliance=False: Summer(
            INFLUENCE[f] * n
        ),
        "acquire_value": lambda card: Summer(3.0),
        "card_to_trash": lambda targets, minimum: (None, minimum),
        "troops_to_retreat": lambda max_troops: 0,
        "is_final_round": lambda: False,
        "is_climax": lambda: False,
        "conflict_posture_bounds": lambda: (-2.5, 12.5),
        "current_conflict_interest": lambda: Summer(0.0),
        "est_strength": lambda: IntSummer(10),
        "est_opponent_strength": lambda seat: IntSummer(0),
        "lady_jessica_return_memories": lambda: False,
        "can_agent_ability_be_played_with_space": lambda space, attr, n: True,
        "want_contract_count": lambda: 1,
    }


@pytest.fixture(scope="module")
def turn_state() -> GameState:
    """Seat 3's first ``turn`` decision (round 1, CHOAM on)."""

    return first_decision("turn")


@pytest.fixture(scope="module")
def effects_state() -> GameState:
    """Seat 3's first ``agent_effects``: Reconnaissance at Arrakeen."""

    return first_decision("agent_effects")


@pytest.fixture(scope="module")
def reveal_state() -> GameState:
    """Seat 3's first ``reveal`` (round 1, 3 troops in the Conflict)."""

    return first_decision("reveal")


ProfileFactory = Callable[..., Profile]


@pytest.fixture
def prof(monkeypatch: pytest.MonkeyPatch) -> ProfileFactory:
    """``prof(state, seat=3, **stub overrides) -> Profile`` with stubs."""

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


def real(state: GameState, seat: int = SEAT) -> Profile:
    return make_profile(state, seat)


def with_frame(state: GameState, **changes: str | int | bool) -> GameState:
    """``state`` with keys of the top frame's context replaced."""

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(changes)
    new = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], new))


def as_leader(
    state: GameState, leader_id: str, face: str | None = None, **changes: Any
) -> GameState:
    """Seat 3 playing ``leader_id`` (face ``face``, default the leader)."""

    return with_player(
        state, SEAT, leader_id=leader_id, leader_face_id=face or leader_id, **changes
    )


def signet_turn(state: GameState, pending: bool = True) -> GameState:
    """``effects_state`` with the Signet Ring played (its box pending)."""

    return with_frame(
        state,
        card_id=f"player:{SEAT}:starter:signet_ring:0",
        pending_agent_effect=pending,
    )


def with_troops(state: GameState, seat: int, **changes: int) -> GameState:
    """Move troops between zones; the garrison absorbs the difference."""

    me = state.players[seat]
    before = sum(getattr(me, k) for k in changes)
    after = sum(changes.values())
    garrison = me.troops_garrison + before - after
    return with_player(state, seat, troops_garrison=garrison, **changes)


def with_swordmaster(state: GameState, seat: int, **changes: object) -> GameState:
    me = state.players[seat]
    return with_player(
        state,
        seat,
        swordmaster_acquired=True,
        agents_available=me.agents_available + 1,
        **changes,
    )


def req(*infos: TargetInfo) -> Request:
    return Request(tuple(infos))


def ents(*entities: Entity) -> TargetInfo:
    return TargetInfo(tuple(entities))


def opts(*options: int) -> TargetInfo:
    return TargetInfo((), tuple(options))


def starter(name: str, copy: int = 0) -> Entity:
    return card_entity(f"player:{SEAT}:starter:{name}:{copy}", SEAT)


def imperium(name: str, copy: int = 0) -> Entity:
    return card_entity(f"imperium:{name}:{copy}", SEAT)


def synth(kind: Kind, ref: str, **attrs: object) -> Entity:
    archetype = Archetype(
        short=f"Test.{ref}",
        kind="test",
        title=None,
        in_uprising=True,
        in_uprising_choam=True,
        attributes=MappingProxyType(dict(attrs)),
    )
    return Entity(kind, ref, archetype, SEAT)


def jessica_leader() -> Entity:
    return leader_entity("lady_jessica")


def rm_leader() -> Entity:
    return leader_entity("lady_jessica", "reverend_mother_jessica")


def owner(leader_id: str) -> Entity:
    return leader_entity(leader_id)


SPACE = ld.training_space_entity

# ---------------------------------------------------------------------------
# Registration, class chain and engine-side members
# ---------------------------------------------------------------------------


def test_every_leader_ability_resolves_to_a_port() -> None:
    """Coverage: every ability id of the leader archetypes (both Jessica
    faces) and of the training-track rewards has a registered port."""

    ids: list[str] = []
    for short in LEADER_ARCHETYPES.values():
        attrs = ARCHETYPES[short].attributes
        for key in ("WormAbilityIDs", "CustomAbilityIDs"):
            value = attrs.get(key, ())
            assert isinstance(value, tuple)
            ids.extend(str(v) for v in value)
    for space_id in FEYD_TRACK_BY_ID:
        ids.extend(SPACE(space_id).list_attr("AbilityIDs"))
    assert len(ids) == 32 + 6
    missing = [name for name in ids if name not in PORTS]
    assert missing == []
    for leader_id in LEADER_ARCHETYPES:
        for ability in abilities_of(leader_entity(leader_id)):
            assert not isinstance(ability, UnportedAbility)


def test_ports_follow_the_app_class_chain() -> None:
    chain: dict[str, tuple[type[Ability], type[Ability]]] = {
        AA + "SignetAbility": (ld.SignetAbility, g.DeferredAbility),
        AA + "BaseSet.DisciplineAbility": (ld.DisciplineAbility, ld.SignetAbility),
        AU + "LeadTheWayAbility": (ld.LeadTheWayAbility, ld.DisciplineAbility),
        AU + "PersonalTrainingAbility": (ld.PersonalTrainingAbility, ld.SignetAbility),
        AU + "PersonalTrainingTrashAbility": (
            ld.PersonalTrainingTrashAbility,
            g.TrashCustomAbility,
        ),
        AU + "PersonalTrainingPayToTrashAbility": (
            ld.PersonalTrainingPayToTrashAbility,
            ld.PersonalTrainingTrashAbility,
        ),
        AU + "DeviousStrengthAbility": (ld.DeviousStrengthAbility, g.DeferredAbility),
        AU + "WarmasterAbility": (ld.WarmasterAbility, ld.SignetAbility),
        AU + "DesertScoutsAbility": (ld.DesertScoutsAbility, g.DeferredAbility),
        AU + "FillCoffersAbility": (ld.FillCoffersAbility, ld.SignetAbility),
        AU + "OtherMemoriesAbility": (ld.OtherMemoriesAbility, g.DeferredAbility),
        AU + "SpiceAgonyAbility": (ld.SpiceAgonyAbility, ld.SignetAbility),
        AU + "WaterOfLifeSignetAbility": (
            ld.WaterOfLifeSignetAbility,
            ld.SignetAbility,
        ),
        AU + "ReverendMotherAbility": (ld.ReverendMotherAbility, g.DeferredAbility),
        AU + "ArrakisInformantAbility": (ld.ArrakisInformantAbility, ld.SignetAbility),
        AU + "UnpredictableFoeAbility": (
            ld.UnpredictableFoeAbility,
            g.GainIntrigueAbility,
        ),
        AU + "ImperialBirthrightDeferredAbility": (
            ld.ImperialBirthrightDeferredAbility,
            g.GainIntrigueAbility,
        ),
        AU + "ChroniclersInsightAbility": (
            ld.ChroniclersInsightAbility,
            ld.SignetAbility,
        ),
        AU + "ChroniclersInsightAcquireAbility": (
            ld.ChroniclersInsightAcquireAbility,
            g.DeferredAbility,
        ),
        AU + "EmperorOfTheKnownUniverseSignetAbility": (
            ld.EmperorOfTheKnownUniverseSignetAbility,
            ld.SignetAbility,
        ),
        AU + "UnseenNetworkAbility": (ld.UnseenNetworkAbility, ld.SignetAbility),
        AU + "UnseenNetworkLandsraadAbility": (
            ld.UnseenNetworkLandsraadAbility,
            g.DeferredAbility,
        ),
        AU + "UnseenNetworkInfluenceAbility": (
            ld.UnseenNetworkInfluenceAbility,
            g.DeferredAbility,
        ),
    }
    for name in (
        "PersonalTrainingSetupAbility",
        "AlwaysSmilingAbility",
        "FillCoffersTriggeredAbility",
        "OtherMemoriesSetupAbility",
        "OtherMemoriesTriggeredAbility",
        "LoyaltyAbility",
        "ImperialBirthrightAbility",
        "SardaukarCommanderAbility",
        "EmperorOfTheKnownUniverseSuppressAbility",
        "LimitedAlliesAbility",
        "SmuggleSpiceAbility",
    ):
        chain[TU + name] = (getattr(ld, name), g.TriggeredAbility)
    for app_class, (cls, base) in chain.items():
        assert PORTS[app_class] is cls
        assert cls.APP_CLASS == app_class
        assert cls.__bases__ == (base,)
    assert g.app_isinstance(
        ld.LeadTheWayAbility(owner("muad_dib")), AA + "SignetAbility"
    )


def test_engine_side_members(turn_state: GameState, prof: ProfileFactory) -> None:
    p = prof(turn_state)
    o = owner("feyd_rautha_harkonnen")
    opt, exp = SelectionMode.OPTIONAL, SelectionMode.EXPLICIT
    expected: list[tuple[g.DeferredAbility, Timing, SelectionMode, bool]] = [
        (ld.PersonalTrainingAbility(o), Timing.AGENT, exp, False),
        (ld.PersonalTrainingTrashAbility(o), Timing.NONE, opt, False),
        (ld.PersonalTrainingPayToTrashAbility(o), Timing.NONE, opt, False),
        (ld.DeviousStrengthAbility(o), Timing.REVEAL, opt, False),
        (ld.WarmasterAbility(o), Timing.AGENT, exp, True),
        (ld.DesertScoutsAbility(o), Timing.REVEAL, opt, False),
        (ld.FillCoffersAbility(o), Timing.AGENT, exp, True),
        (ld.OtherMemoriesAbility(o), Timing.NONE, opt, False),
        (ld.SpiceAgonyAbility(o), Timing.AGENT, opt, False),
        (ld.WaterOfLifeSignetAbility(o), Timing.AGENT, opt, False),
        (ld.ReverendMotherAbility(o), Timing.AGENT, opt, False),
        (ld.ArrakisInformantAbility(o), Timing.AGENT, exp, False),
        (ld.LeadTheWayAbility(o), Timing.AGENT, exp, True),  # no Agent turn here
        (ld.UnpredictableFoeAbility(o), Timing.REVEAL, exp, True),
        (ld.ImperialBirthrightDeferredAbility(o), Timing.NONE, exp, True),
        (ld.ChroniclersInsightAbility(o), Timing.AGENT, opt, False),
        (ld.ChroniclersInsightAcquireAbility(o), Timing.NONE, exp, False),
        (ld.EmperorOfTheKnownUniverseSignetAbility(o), Timing.AGENT, exp, False),
        (ld.UnseenNetworkAbility(o), Timing.AGENT, exp, False),
        (ld.UnseenNetworkLandsraadAbility(o), Timing.NONE, opt, False),
        (ld.UnseenNetworkInfluenceAbility(o), Timing.NONE, opt, False),
    ]
    for ability, timing, mode, immediate in expected:
        assert ability.timing == timing, ability
        assert ability.selection_mode(p) == mode, ability
        assert ability.can_run_immediately(p) is immediate, ability
        # No leader archetype sets DeferValue: Explicit 1, Optional 0.
        assert ability.defer_value(p) == (1 if mode == exp else 0), ability
    assert ld.DisciplineAbility.contextually_deferred


def test_triggered_ports_have_no_ai_hook(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(turn_state)
    for cls in (ld.AlwaysSmilingAbility, ld.LoyaltyAbility, ld.SmuggleSpiceAbility):
        ability = cls(owner("gurney_halleck"))
        assert ability.value_for_player(p, ()).sum == 0.0
        assert ability.evaluate(p, req()).response is None


# ---------------------------------------------------------------------------
# SignetAbility and the placement merge
# ---------------------------------------------------------------------------


def test_signet_cost_needs_a_pending_signet_card(
    effects_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.WarmasterAbility(owner("gurney_halleck"))
    assert ability.meets_cost(prof(signet_turn(effects_state)))
    # Reconnaissance has no signet icon; a resolved box has paid its icon.
    assert not ability.meets_cost(prof(effects_state))
    resolved = signet_turn(effects_state, pending=False)
    assert not ability.meets_cost(prof(resolved))
    assert not ability.meets_cost(prof(turn_state))  # no Agent turn


def _signet_leader(state: GameState, leader_id: str, **changes: Any) -> GameState:
    """``state`` with seat 3 as ``leader_id`` and its Signet Ring box pending."""

    return signet_turn(as_leader(state, leader_id, **changes))


def _engine_step(state: GameState, action_id: str, **arguments: str) -> GameState:
    """Apply one real engine signet action of seat 3 (``rules/leader_abilities``)."""

    action = DomainAction(
        action_id=action_id, actor=SEAT, arguments=tuple(sorted(arguments.items()))
    )
    if state.players[SEAT].leader_id == "feyd_rautha_harkonnen":
        assert action in legal_feyd_track_actions(state, SEAT)
        return apply_feyd_track_action(state, action).state
    assert action in legal_leader_signet_actions(state, SEAT)
    return apply_leader_signet_spy(state, action).state


@pytest.mark.parametrize("target", ["paid_trash", "first_spy"])
def test_signet_icon_is_paid_once_personal_training_ran(
    effects_state: GameState, prof: ProfileFactory, target: str
) -> None:
    """Spec §0.1.2/§3.2: ``Cleanup`` pays the icon after ``Train(space)``.

    Our engine keeps ``pending_agent_effect`` through the reward stage; the
    signet no longer meets its cost there, only the reward's grant does.
    """

    feyd = _signet_leader(
        effects_state, "feyd_rautha_harkonnen", resources=Resources(solari=1)
    )
    o = owner("feyd_rautha_harkonnen")
    signet = ld.PersonalTrainingAbility(o)
    assert signet.meets_cost(prof(feyd))
    after = _engine_step(feyd, "advance_feyd_track", space_id=target)
    context = dict(after.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["feyd_track_stage"] == target
    p = prof(after)
    assert ld.training_rank(p) < 7  # the rank alone would pass the cost
    assert not signet.meets_cost(p)
    assert not ld.WarmasterAbility(owner("gurney_halleck")).meets_cost(p)
    pay_to_trash = ld.PersonalTrainingPayToTrashAbility(o).meets_cost(p)
    assert pay_to_trash is (target == "paid_trash")
    assert ld.training_spy_grant_pending(p) is (target == "first_spy")


@pytest.mark.parametrize("stage", ["mid_trash", "late_trash", "second_spy", "final"])
def test_signet_icon_is_paid_through_every_training_stage(
    effects_state: GameState, prof: ProfileFactory, stage: str
) -> None:
    feyd = _signet_leader(
        effects_state, "feyd_rautha_harkonnen", feyd_track_space=stage
    )
    rank = ld.training_rank(prof(feyd))
    signet = ld.PersonalTrainingAbility(owner("feyd_rautha_harkonnen"))
    assert signet.meets_cost(prof(feyd)) is (rank < 7)
    assert not signet.meets_cost(prof(with_frame(feyd, feyd_track_stage=stage)))


def test_training_spy_grant(effects_state: GameState, prof: ProfileFactory) -> None:
    """Training indices 2, 5 and 7 grant ``PlaceSpyCustomAbility`` (§3.2)."""

    assert ld.TRAINING_SPY_STAGES == tuple(
        space.ref
        for space in ld._TRAINING_SPACES
        if ld._PLACE_SPY_CUSTOM_ID in space.list_attr("AbilityIDs")
    )
    feyd = as_leader(effects_state, "feyd_rautha_harkonnen")
    assert not ld.training_spy_grant_pending(prof(feyd))  # no pending reward
    for stage in ("paid_trash", "mid_trash", "late_trash"):
        assert not ld.training_spy_grant_pending(
            prof(with_frame(feyd, feyd_track_stage=stage))
        )
    for stage in ld.TRAINING_SPY_STAGES:
        assert ld.training_spy_grant_pending(
            prof(with_frame(feyd, feyd_track_stage=stage))
        )


def test_signet_icon_is_paid_once_unseen_network_placed_its_spy(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    """Spec §12.2: ``EmitSequence`` grants the follow-up before ``Cleanup``."""

    staban = _signet_leader(
        effects_state, "staban_tuek", resources=Resources(solari=2, spice=1)
    )
    o = owner("staban_tuek")
    signet = ld.UnseenNetworkAbility(o)
    assert signet.meets_cost(prof(staban))
    post = "landsraad-high-council-imperial-privilege-swordmaster"
    after = _engine_step(staban, "place_leader_spy", post_id=post)
    context = dict(after.decision_stack[-1].context)
    assert context["pending_agent_effect"] is True
    assert context["staban_bonus_post"] == post
    p = prof(after)
    assert not signet.meets_cost(p)
    assert ld.UnseenNetworkLandsraadAbility(o).meets_cost(p)


def test_recall_first_spy_keeps_the_signet_icon(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    """The recall-first is chosen inside the signet's ``PlaceSpy`` (§3.4),
    before ``Cleanup``: the icon is still held."""

    staban = _signet_leader(
        effects_state, "staban_tuek", spy_post_ids=THREE_POSTS, spies_supply=0
    )
    after = _engine_step(
        staban, "recall_spy_for_leader_placement", post_id=THREE_POSTS[0]
    )
    context = dict(after.decision_stack[-1].context)
    assert context["leader_spy_recalled"] is True
    assert "staban_bonus_post" not in context
    assert ld.UnseenNetworkAbility(owner("staban_tuek")).meets_cost(prof(after))


def test_signet_value_is_merged_into_a_signet_ring_placement(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    gurney = as_leader(turn_state, "gurney_halleck")
    signet = g.AgentAbility(starter("signet_ring"))
    v = signet.value_for_player(prof(gurney), (space_entity("arrakeen", Board(True)),))
    assert v.sum == pytest.approx(0.9 - 0.5 * 0.75)  # Warmaster troop - reveal


def test_reverend_mother_term_is_merged_by_the_generic_space_value(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    flipped = with_player(turn_state, SEAT, leader_face_id="reverend_mother_jessica")
    fremkit = g.SpaceAbility(space_entity("fremkit", Board(True)))
    assert fremkit.value_for_player(prof(flipped), ()).sum == pytest.approx(-1 + 1.8)
    assert fremkit.value_for_player(prof(turn_state), ()).sum == 0.0


# ---------------------------------------------------------------------------
# Feyd-Rautha: training track, Personal Training, trash rewards (§3)
# ---------------------------------------------------------------------------


def test_training_track_matches_our_engine() -> None:
    reward_ids = {
        FeydTrackReward.NONE: (),
        FeydTrackReward.PAY_SOLARI_TO_TRASH: (
            AU + "PersonalTrainingPayToTrashAbility",
        ),
        FeydTrackReward.PLACE_SPY: (AU + "PlaceSpyCustomAbility",),
        FeydTrackReward.OPTIONAL_TRASH: (AU + "PersonalTrainingTrashAbility",),
        FeydTrackReward.GAIN_TWO_SPICE: (),
        FeydTrackReward.TROOP_AND_SPY: (AU + "PlaceSpyCustomAbility",),
    }
    by_index = {SPACE(s).int_attr("Index"): s for s in FEYD_TRACK_BY_ID}
    for space_id, ours in FEYD_TRACK_BY_ID.items():
        space = SPACE(space_id)
        nexts = space.attr("NextIndices")
        assert isinstance(nexts, tuple)
        assert tuple(by_index[i] for i in nexts) == ours.next_space_ids
        assert space.list_attr("AbilityIDs") == reward_ids[ours.reward]
        assert space.int_attr("Spice") == (
            2 if ours.reward is FeydTrackReward.GAIN_TWO_SPICE else 0
        )
        assert space.int_attr("Troops") == (
            1 if ours.reward is FeydTrackReward.TROOP_AND_SPY else 0
        )


def test_training_space_value_each_reward(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    rich = with_player(turn_state, SEAT, resources=Resources(solari=2))
    p = prof(rich)
    value = {s: ld.training_space_value(p, SPACE(s)).sum for s in FEYD_TRACK_BY_ID}
    assert value == pytest.approx(
        {
            "start": 0.0,
            "paid_trash": -0.25 + 2.75,
            "first_spy": 1.66,
            "mid_trash": 2.75,
            "late_trash": 2.75,
            "second_spy": 1.66,
            "double_spice": 1.0,
            "final": 0.9 + 1.66,
        }
    )
    # With no Solari the pay-to-trash space is worth exactly 0 (``jle``).
    broke = with_player(turn_state, SEAT, resources=Resources(solari=0))
    assert ld.training_space_value(prof(broke), SPACE("paid_trash")).sum == 0.0


@pytest.mark.parametrize(
    ("solari", "swordmaster", "spies", "paid", "spy", "pick"),
    [
        # 16 §1.2 table, Early, Supplied Solari: 2.75 - 1.144 vs 1.66 -> spy.
        (4, False, (), 2.75 - 1.144, 1.66, "first_spy"),
        # Rich Solari (x0.5): pay-to-trash.
        (8, False, (), 2.75 - 0.572, 1.66, "paid_trash"),
        # With the Swordmaster (no x1.6): 2.04 -> pay-to-trash.
        (4, True, (), 2.75 - 0.715, 1.66, "paid_trash"),
        # One spy out: SpyValue 1.66 x 0.67 -> pay-to-trash.
        (4, False, ("emperor-sardaukar-dutiful-service",), 1.606, 1.1122, "paid_trash"),
    ],
)
def test_training_rank_zero_fork_worked_example(
    turn_state: GameState,
    solari: int,
    swordmaster: bool,
    spies: tuple[str, ...],
    paid: float,
    spy: float,
    pick: str,
) -> None:
    state = with_player(
        turn_state,
        0,
        resources=Resources(solari=solari, water=1),
        spy_post_ids=spies,
        spies_supply=3 - len(spies),
    )
    if swordmaster:
        state = with_swordmaster(state, 0)
    p = real(state, 0)  # seat 0 is Feyd, token on the start space
    assert [s.ref for s in ld.training_next_spaces(p)] == ["paid_trash", "first_spy"]
    assert ld.training_space_value(p, SPACE("paid_trash")).sum == pytest.approx(paid)
    assert ld.training_space_value(p, SPACE("first_spy")).sum == pytest.approx(spy)
    ability = ld.PersonalTrainingAbility(owner("feyd_rautha_harkonnen"))
    answer = ability.evaluate(p, req(ents(SPACE("paid_trash"), SPACE("first_spy"))))
    assert answer.response == ((pick,),)
    assert answer.value == pytest.approx(max(paid, spy))
    assert ability.value_for_player(p, ()).sum == pytest.approx(max(paid, spy))


def test_personal_training_evaluate_first_lands_and_ties_keep_it(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.PersonalTrainingAbility(owner("feyd_rautha_harkonnen"))
    tie = prof(turn_state, trash_card_value=lambda: 1.66)
    pair = req(ents(SPACE("late_trash"), SPACE("second_spy")))
    assert ability.evaluate(tie, pair).response == (("late_trash",),)
    # Every option <= 0: the first still lands (the prompt is forced).
    bad = prof(turn_state, trash_card_value=lambda: -1.0, spy_value=lambda: Summer(-2))
    answer = ability.evaluate(bad, pair)
    assert (answer.value, answer.response) == (-1.0, (("late_trash",),))
    assert ability.evaluate(bad, req()).response is None


def test_personal_training_value_is_the_best_next_space_or_zero(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.PersonalTrainingAbility(owner("feyd_rautha_harkonnen"))
    feyd = with_player(turn_state, 0, feyd_track_space="mid_trash")
    assert ability.value_for_player(prof(feyd, 0), ()).sum == pytest.approx(2.75)
    # Nothing beats 0.0: the base summer.
    worthless = prof(
        feyd, 0, trash_card_value=lambda: -1.0, spy_value=lambda: Summer(-1)
    )
    assert ability.value_for_player(worthless, ()).sum == 0.0
    # The last space has no next space; a non-Feyd seat has no track.
    final = with_player(turn_state, 0, feyd_track_space="final")
    assert ability.value_for_player(prof(final, 0), ()).sum == 0.0
    assert ability.value_for_player(prof(turn_state), ()).sum == 0.0


def test_personal_training_cost(effects_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.PersonalTrainingAbility(owner("feyd_rautha_harkonnen"))
    feyd = signet_turn(as_leader(effects_state, "feyd_rautha_harkonnen"))
    assert ability.meets_cost(prof(feyd))
    at_final = with_player(feyd, SEAT, feyd_track_space="final")
    assert not ability.meets_cost(prof(at_final))  # rank 7
    assert not ability.meets_cost(prof(signet_turn(effects_state)))  # not Feyd
    assert (
        ld.training_rank(prof(with_player(feyd, SEAT, feyd_track_space="late_trash")))
        == 4
    )


def test_training_trash_rewards(effects_state: GameState, prof: ProfileFactory) -> None:
    o = owner("feyd_rautha_harkonnen")
    trash = ld.PersonalTrainingTrashAbility(o)
    paid = ld.PersonalTrainingPayToTrashAbility(o)
    feyd = as_leader(effects_state, "feyd_rautha_harkonnen")
    mid = prof(with_frame(feyd, feyd_track_stage="mid_trash"))
    assert trash.meets_cost(mid) and not paid.meets_cost(mid)
    first = with_frame(feyd, feyd_track_stage="paid_trash")
    assert not trash.meets_cost(prof(first)) and not paid.meets_cost(prof(first))
    funded = with_player(first, SEAT, resources=Resources(solari=1))
    assert paid.meets_cost(prof(funded))
    assert not trash.meets_cost(prof(feyd))  # no pending reward
    # No trashable card: the cost fails.
    empty = with_player(
        with_frame(feyd, feyd_track_stage="late_trash"),
        SEAT,
        hand=(),
        discard_pile=(),
        in_play=(),
    )
    assert not trash.meets_cost(prof(empty))
    # TrashAbility's hooks: with no junk card, an empty pick at 1.0 (quirk).
    answer = paid.evaluate(mid, req(ents(starter("signet_ring"))))
    assert (answer.value, answer.response) == (1.0, ((),))
    assert trash.value_for_player(mid, ()).sum == pytest.approx(2.75 + 1.0)


def test_training_trash_picks_the_junk_starter(effects_state: GameState) -> None:
    """Real ``GetCardToTrash``: a Dagger scores (1.0 - 0.25) x 10 + 0.09."""

    ability = ld.PersonalTrainingTrashAbility(owner("feyd_rautha_harkonnen"))
    hand = [card_entity(i, SEAT) for i in effects_state.players[SEAT].hand]
    answer = ability.evaluate(real(effects_state), req(ents(*hand)))
    assert answer.value == pytest.approx(7.59)
    assert answer.response is not None and "dagger" in str(answer.response[0][0])


# ---------------------------------------------------------------------------
# Devious Strength (§3.1)
# ---------------------------------------------------------------------------


def _feyd_reveal(state: GameState, *posts: str) -> GameState:
    return as_leader(
        state,
        "feyd_rautha_harkonnen",
        spy_post_ids=posts,
        spies_supply=3 - len(posts),
    )


def test_devious_strength_cost_and_value(
    reveal_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.DeviousStrengthAbility(owner("feyd_rautha_harkonnen"))
    spied = _feyd_reveal(reveal_state, "emperor-sardaukar-dutiful-service")
    assert ability.meets_cost(prof(spied))
    assert ability.value_for_player(prof(spied), ()).sum == pytest.approx(-1.66 + 1.32)
    no_spy = _feyd_reveal(reveal_state)
    assert not ability.meets_cost(prof(no_spy))
    assert ability.value_for_player(prof(no_spy), ()).sum == 0.0
    no_units = with_troops(spied, SEAT, troops_conflict=0)
    assert not ability.meets_cost(prof(no_units))
    outside = _feyd_reveal(turn_state, "emperor-sardaukar-dutiful-service")
    assert not ability.meets_cost(prof(outside))  # not in the Reveal turn


def _set_conflict(state: GameState, conflict_id: str) -> GameState:
    return with_state(
        state,
        conflict_deck=tuple(c for c in state.conflict_deck if c != conflict_id),
        current_conflict_ids=(conflict_id,),
    )


THREE_POSTS = (
    "emperor-sardaukar-dutiful-service",
    "spacing-guild-heighliner-deliver-supplies",
    "arrakis-hagga-basin",
)


@pytest.mark.parametrize(
    ("final", "posts", "conflict", "interest", "opponents", "used"),
    [
        (True, THREE_POSTS[:2], None, -50.0, (0, 0, 0), True),  # Last Round
        (True, THREE_POSTS, "spice_freighters", -50.0, (0, 0, 0), True),
        # 3 spies in Battle for Arrakeen: only the posture tests remain.
        (True, THREE_POSTS, "battle_for_arrakeen", -50.0, (0, 0, 0), False),
        (True, THREE_POSTS, "battle_for_arrakeen", 12.5, (14, 0, 0), True),
        (False, THREE_POSTS[:1], None, 12.5, (6, 0, 0), True),  # high: |4| < 5
        (False, THREE_POSTS[:1], None, 12.5, (15, 0, 0), False),  # high: 5 fails
        (False, THREE_POSTS[:1], None, 30.0, (9, 0, 0), True),  # high: |1| < 5
        (False, THREE_POSTS[:1], None, 12.4, (14, 0, 0), False),  # mid: 4 >= 2
        (False, THREE_POSTS[:1], None, -2.5, (9, 0, 0), True),  # mid: |1| < 2
        (False, THREE_POSTS[:1], None, -2.6, (10, 0, 0), False),  # below lb
    ],
)
def test_devious_strength_evaluate(
    reveal_state: GameState,
    prof: ProfileFactory,
    final: bool,
    posts: tuple[str, ...],
    conflict: str | None,
    interest: float,
    opponents: tuple[int, int, int],
    used: bool,
) -> None:
    state = _feyd_reveal(reveal_state, *posts)
    if conflict is not None:
        state = _set_conflict(state, conflict)
    strengths = dict(zip((0, 1, 2), opponents, strict=True))
    p = prof(
        state,
        is_final_round=lambda: final,
        current_conflict_interest=lambda: Summer(interest),
        est_opponent_strength=lambda seat: IntSummer(strengths[seat]),
    )
    ability = ld.DeviousStrengthAbility(owner("feyd_rautha_harkonnen"))
    spies = [spy_entity(post, SEAT) for post in posts]
    answer = ability.evaluate(p, req(ents(*spies)))
    if used:
        assert (answer.value, answer.response) == (100.0, ((posts[0],),))
    else:
        assert (answer.value, answer.response) == (0.0, None)


def test_devious_strength_needs_a_spy_to_recall(
    reveal_state: GameState, prof: ProfileFactory
) -> None:
    p = prof(_feyd_reveal(reveal_state), is_final_round=lambda: True)
    ability = ld.DeviousStrengthAbility(owner("feyd_rautha_harkonnen"))
    assert ability.evaluate(p, req(ents())).response is None


def test_devious_strength_recalls_the_spy_on_the_worst_post(
    reveal_state: GameState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real ``GetRecallSpy``: the spy on the lowest ``PostValue`` post.

    Emperor post 4.0 (faction, high influence value) vs Hagga Basin 2.0.
    """

    posts = ("emperor-sardaukar-dutiful-service", "arrakis-hagga-basin")
    p = real(_feyd_reveal(reveal_state, *posts))
    monkeypatch.setattr(p, "is_final_round", lambda: True)  # "Last Round"
    answer = ld.DeviousStrengthAbility(owner("feyd_rautha_harkonnen")).evaluate(
        p, req(ents(*(spy_entity(post, SEAT) for post in posts)))
    )
    assert answer.value == 100.0
    assert answer.response == (("arrakis-hagga-basin",),)


# ---------------------------------------------------------------------------
# Gurney (§4) and Amber (§8)
# ---------------------------------------------------------------------------


def test_warmaster(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.WarmasterAbility(owner("gurney_halleck"))
    p = prof(turn_state)
    assert ability.value_for_player(p, ()).sum == pytest.approx(0.9)
    assert ability.evaluate(p, req()).value == 1.0  # default DeferredAbility


def test_desert_scouts(
    reveal_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.DesertScoutsAbility(owner("lady_amber_metulli"))
    retreat = prof(reveal_state, troops_to_retreat=lambda n: 1)
    answer = ability.evaluate(retreat, req())
    assert (answer.value, answer.response) == (1.0, ())
    keep = ability.evaluate(prof(reveal_state), req())
    assert (keep.value, keep.response) == (0.0, None)
    # min(0.5 x deployed units, 1.0): 3 troops -> 1.0, 1 troop -> 0.5.
    assert ability.value_for_player(prof(reveal_state), ()).sum == 1.0
    one = with_troops(reveal_state, SEAT, troops_conflict=1)
    assert ability.value_for_player(prof(one), ()).sum == 0.5
    assert ability.meets_cost(prof(one))
    assert not ability.meets_cost(prof(turn_state))


def test_desert_scouts_uses_the_real_retreat_rule(reveal_state: GameState) -> None:
    ability = ld.DesertScoutsAbility(owner("lady_amber_metulli"))
    p = real(reveal_state)
    expected = 1.0 if p.troops_to_retreat(1) > 0 else 0.0
    assert ability.evaluate(real(reveal_state), req()).value == expected


def test_fill_coffers(effects_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.FillCoffersAbility(owner("lady_amber_metulli"))
    amber = signet_turn(as_leader(effects_state, "lady_amber_metulli"))
    assert ability.value_for_player(prof(amber), ()).sum == pytest.approx(0.25)
    assert not ability.meets_cost(prof(amber))  # no Alliance
    allied = with_player(amber, SEAT, alliance_faction_ids=("fremen",))
    assert ability.value_for_player(prof(allied), ()).sum == pytest.approx(0.75)
    assert ability.meets_cost(prof(allied))
    assert ability.can_run_immediately(prof(amber))


# ---------------------------------------------------------------------------
# Lady Jessica and Reverend Mother Jessica (§5, §6)
# ---------------------------------------------------------------------------


def test_other_memories(effects_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.OtherMemoriesAbility(jessica_leader())
    used = ability.evaluate(
        prof(effects_state, lady_jessica_return_memories=lambda: True), req()
    )
    assert (used.value, used.response) == (100.0, ())
    kept = ability.evaluate(prof(effects_state), req())
    assert (kept.value, kept.response) == (0.0, None)
    assert not ability.meets_cost(prof(effects_state))
    granted = with_frame(effects_state, pending_leader_ability=True)
    assert ability.meets_cost(prof(granted))
    assert ability.value_for_player(prof(granted), ()).sum == 0.0


def test_other_memories_real_gate(effects_state: GameState) -> None:
    ability = ld.OtherMemoriesAbility(jessica_leader())
    late = with_state(effects_state, round_number=5)
    assert ability.evaluate(real(late), req()).value == 100.0
    assert ability.evaluate(real(effects_state), req()).value == 0.0


@pytest.mark.parametrize(
    ("spice", "swordmaster", "value"),
    [(2, False, 100.0), (1, False, 0.0), (1, True, 100.0), (0, True, 100.0)],
)
def test_spice_agony_evaluate(
    turn_state: GameState,
    prof: ProfileFactory,
    spice: int,
    swordmaster: bool,
    value: float,
) -> None:
    state = with_player(turn_state, SEAT, resources=Resources(spice=spice))
    if swordmaster:
        state = with_swordmaster(state, SEAT)
    answer = ld.SpiceAgonyAbility(jessica_leader()).evaluate(prof(state), req())
    assert answer.value == value
    assert answer.response == (() if value else None)


def test_spice_agony_value_and_cost(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.SpiceAgonyAbility(jessica_leader())
    p = prof(effects_state)
    assert ability.value_for_player(p, ()).sum == pytest.approx(-0.5 + 2.25 + 0.5)
    no_troops = with_troops(effects_state, SEAT, troops_supply=0)
    assert ability.value_for_player(prof(no_troops), ()).sum == pytest.approx(1.75)
    signet = signet_turn(effects_state)
    assert not ability.meets_cost(prof(signet))  # no spice
    funded = with_player(signet, SEAT, resources=Resources(spice=1))
    assert ability.meets_cost(prof(funded))


def test_water_of_life(effects_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.WaterOfLifeSignetAbility(rm_leader())
    p = prof(effects_state)
    answer = ability.evaluate(p, req())
    assert answer.value == pytest.approx(0.5)
    assert answer.response == ()
    espionage = space_entity("espionage", Board(True))
    assert ability.value_for_player(p, (espionage,)).sum == pytest.approx(0.5)
    assert ability.value_for_player(p, ()).sum == pytest.approx(0.5)
    blocked = prof(
        effects_state, can_agent_ability_be_played_with_space=lambda s, a, n: False
    )
    assert ability.value_for_player(blocked, (espionage,)).sum == 0.0
    # Real affordability: Espionage costs 1 spice, the seat holds none.
    assert ability.value_for_player(real(effects_state), (espionage,)).sum == 0.0
    signet = signet_turn(effects_state)
    assert not ability.meets_cost(prof(signet))
    funded = with_player(signet, SEAT, resources=Resources(spice=1))
    assert ability.meets_cost(prof(funded))


@pytest.mark.parametrize(
    ("space_id", "value"),
    [
        ("secrets", -1.0 + 2.25),
        ("desert_tactics", -1.0 + 0.9 + 2.75),
        ("fremkit", -1.0 + 1.8),
        ("espionage", -1.0 + 1.8 + 1.66),
        ("arrakeen", -1.0),
        (None, -1.0),
    ],
)
def test_reverend_mother_value(
    turn_state: GameState, prof: ProfileFactory, space_id: str | None, value: float
) -> None:
    ability = ld.ReverendMotherAbility(rm_leader())
    spaces = () if space_id is None else (space_entity(space_id, Board(True)),)
    assert ability.value_for_player(prof(turn_state), spaces).sum == pytest.approx(
        value
    )


def test_reverend_mother_value_needs_water_beyond_the_space_cost(
    turn_state: GameState,
) -> None:
    """Real affordability: Desert Tactics costs 1 water; the seat holds 1."""

    ability = ld.ReverendMotherAbility(rm_leader())
    tactics = space_entity("desert_tactics", Board(True))
    assert ability.value_for_player(real(turn_state), (tactics,)).sum == 0.0
    wet = with_player(turn_state, SEAT, resources=Resources(water=2))
    p = real(wet)
    expected = p.water_value(-1) + p.troop_value(1, False) + p.trash_card_value()
    assert ability.value_for_player(p, (tactics,)).sum == pytest.approx(expected)


def test_reverend_mother_evaluate_counts_the_water_twice(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    flipped = with_player(
        with_frame(effects_state, space_id="fremkit"),
        SEAT,
        leader_face_id="reverend_mother_jessica",
        resources=Resources(water=1),
    )
    ability = ld.ReverendMotherAbility(rm_leader())
    # -Water(1) + the generic Fremkit value, which merges this ability's own
    # term (-Water(1) + draw 1.8) again.
    answer = ability.evaluate(prof(flipped), req())
    assert answer.value == pytest.approx(-1.0 - 1.0 + 1.8)
    assert answer.response == ()
    cheap = prof(flipped, water_value=lambda n: 0.2 * n)
    assert ability.evaluate(cheap, req()).value == pytest.approx(-0.2 - 0.2 + 1.8)
    assert ability.meets_cost(prof(flipped))
    # Not a BG/Fremen space, or no water: no repeat.
    at_arrakeen = with_player(
        effects_state,
        SEAT,
        leader_face_id="reverend_mother_jessica",
        resources=Resources(water=1),
    )
    assert ld.deployed_faction_space(prof(at_arrakeen)) is None
    assert not ability.meets_cost(prof(at_arrakeen))
    assert ability.evaluate(prof(at_arrakeen), req()).value == pytest.approx(-1.0)
    dry = with_player(flipped, SEAT, resources=Resources(water=0))
    assert not ability.meets_cost(prof(dry))


# ---------------------------------------------------------------------------
# Lady Margot Fenring (§7)
# ---------------------------------------------------------------------------


def test_circle_posts() -> None:
    circle = sorted(
        p for p in POST_INDEX if ld.is_circle_observation_post(p, Board(True))
    )
    assert circle == [
        "arrakis-research-station-sietch-tabr",
        "arrakis-research-station-spice-refinery",
        "arrakis-spice-refinery-arrakeen",
    ]


@pytest.mark.parametrize(
    ("spies", "value"), [(0, 1.66 * 0.66), (2, 1.66 * 0.66), (3, 0.0)]
)
def test_arrakis_informant_value(
    turn_state: GameState, prof: ProfileFactory, spies: int, value: float
) -> None:
    state = with_player(
        turn_state, SEAT, spy_post_ids=THREE_POSTS[:spies], spies_supply=3 - spies
    )
    ability = ld.ArrakisInformantAbility(owner("lady_margot_fenring"))
    assert ability.value_for_player(prof(state), ()).sum == pytest.approx(value)


def test_arrakis_informant_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    answer = ld.ArrakisInformantAbility(owner("lady_margot_fenring")).evaluate(
        prof(turn_state), req()
    )
    assert (answer.value, answer.response) == (1.66, ())


# ---------------------------------------------------------------------------
# Muad'Dib (§9)
# ---------------------------------------------------------------------------


def test_lead_the_way_value_and_cost(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.LeadTheWayAbility(owner("muad_dib"))
    p = prof(effects_state)
    assert ability.value_for_player(p, ()).sum == pytest.approx(1.5 + 0.3)
    assert ability.evaluate(p, req()).value == 1.0  # default Explicit value
    signet = signet_turn(effects_state)
    assert ability.meets_cost(prof(signet))
    empty = with_player(signet, SEAT, deck=(), discard_pile=())
    assert not ability.meets_cost(prof(empty))


def test_lead_the_way_runs_unless_the_threshold_is_reached(
    effects_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.LeadTheWayAbility(owner("muad_dib"))
    assert ability.can_run_immediately(prof(turn_state))  # no Agent turn
    # Reconnaissance at Arrakeen: DeferValue 1 (space) + 0 intrigue cards.
    assert not g.deferred_threshold_reached(prof(effects_state))
    assert ability.can_run_immediately(prof(effects_state))
    # Signet Ring (DeferValue 3) at Arrakeen reaches the threshold.
    signet = signet_turn(effects_state)
    assert g.deferred_threshold_reached(prof(signet))
    assert not ability.can_run_immediately(prof(signet))


def test_unpredictable_foe(
    reveal_state: GameState, turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.UnpredictableFoeAbility(owner("muad_dib"))
    worm = with_player(reveal_state, SEAT, sandworms_conflict=1)
    assert ability.meets_cost(prof(worm))
    assert ability.value_for_player(prof(worm), ()).sum == pytest.approx(2.25)
    assert not ability.meets_cost(prof(reveal_state))  # no sandworm
    assert ability.value_for_player(prof(reveal_state), ()).sum == 0.0
    outside = with_player(turn_state, SEAT, sandworms_conflict=1)
    assert not ability.meets_cost(prof(outside))
    assert ability.evaluate(prof(worm), req()).value == 100.0


# ---------------------------------------------------------------------------
# Princess Irulan (§10)
# ---------------------------------------------------------------------------


def test_imperial_birthright_grant_is_never_held(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.ImperialBirthrightDeferredAbility(owner("princess_irulan"))
    p = prof(turn_state)
    assert not ability.meets_cost(p)
    assert ability.value_for_player(p, ()).sum == 0.0
    assert ability.evaluate(p, req()).value == 100.0


ROW_WITH_CHEAP = (
    "imperium:sardaukar_soldier:0",
    "imperium:weirding_woman:0",
    "imperium:steersman:0",
    "imperium:calculus_of_power:0",
    "imperium:subversive_advisor:0",
)


def _irulan(state: GameState, row: tuple[str, ...] | None = None) -> GameState:
    state = as_leader(state, "princess_irulan")
    if row is not None:
        state = with_state(state, imperium_row=row)
    return state


def _chronicler(hand: tuple[Entity, ...]) -> Request:
    return req(opts(0, 1), ents(*hand))


def test_chroniclers_insight_acquire_targets(turn_state: GameState) -> None:
    p = real(_irulan(turn_state, ROW_WITH_CHEAP))
    assert [c.ref for c in ld.chroniclers_acquire_targets(p)] == [
        "imperium:sardaukar_soldier:0",
        "imperium:weirding_woman:0",
    ]
    assert ld.chroniclers_acquire_targets(real(turn_state)) == []  # no cost <= 1 card


def test_chroniclers_insight_value(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    values = {"imperium:sardaukar_soldier:0": 2.0, "imperium:weirding_woman:0": 4.5}
    p = prof(
        _irulan(turn_state, ROW_WITH_CHEAP),
        acquire_value=lambda card: Summer(values[card.ref]),
    )
    assert ability.value_for_player(p, ()).sum == 4.5
    assert ability.value_for_player(prof(_irulan(turn_state)), ()).sum == 0.0


def test_chroniclers_insight_cost(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    signet = signet_turn(_irulan(effects_state))
    assert ability.meets_cost(prof(signet))  # a hand
    empty = with_player(signet, SEAT, hand=())
    assert not ability.meets_cost(prof(empty))  # no hand, no cost-1 card
    assert ability.meets_cost(prof(with_state(empty, imperium_row=ROW_WITH_CHEAP)))


def test_chroniclers_insight_trashes_a_paid_junk_card_first(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    junk = synth(Kind.CARD, "junk", PersuasionCost=4, TrashValue=2.0)
    dagger = starter("dagger")

    def to_trash(targets: list[Entity], minimum: float) -> tuple[Entity | None, float]:
        assert minimum == 0.0
        found = [c for c in targets if c.has("TrashValue")]
        return (found[0], 20.5) if found else (None, minimum)

    p = prof(_irulan(turn_state), card_to_trash=to_trash)
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    answer = ability.evaluate(p, _chronicler((dagger, junk)))
    assert (answer.value, answer.response) == (20.5, ((1,), ("junk",)))


def test_chroniclers_insight_trashes_a_junk_starter(turn_state: GameState) -> None:
    """Real ``GetCardToTrash`` over the hand: a Dagger (CA among them)."""

    state = _irulan(turn_state)
    hand = tuple(card_entity(i, SEAT) for i in state.players[SEAT].hand)
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    answer = ability.evaluate(real(state), _chronicler(hand))
    assert answer.value == pytest.approx(7.59)
    assert answer.response is not None and answer.response[0] == (1,)
    assert "dagger" in str(answer.response[1][0])


def _cheap(ref: str, persuasion: int, cost: int = 1) -> Entity:
    return synth(
        Kind.CARD,
        ref,
        PersuasionCost=cost,
        Persuasion=persuasion,
        WormAbilityIDs=("worm.canis.abilities.PlayAbilities.RevealAbility",),
    )


def test_chroniclers_insight_trashes_the_weakest_cheap_card(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    p = prof(_irulan(turn_state, ROW_WITH_CHEAP))
    hand = (
        _cheap("a", 2),
        _cheap("b", 1),
        _cheap("c", 1, cost=2),
        _cheap("d", 0, cost=3),  # cost 3: never trashed
        starter("convincing_argument"),
    )
    answer = ability.evaluate(p, _chronicler(hand))
    # MinBy keeps the first strict minimum: b (0.75) before c (0.75).
    assert (answer.value, answer.response) == (1.0, ((1,), ("b",)))


def test_chroniclers_insight_acquires_when_nothing_to_trash(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    hand = (_cheap("d", 0, cost=3), starter("convincing_argument"))
    with_row = prof(_irulan(turn_state, ROW_WITH_CHEAP))
    answer = ability.evaluate(with_row, _chronicler(hand))
    assert (answer.value, answer.response) == (1.0, ((0,),))
    # No cost-1 card: the specific-card fallback at the last trash value (0.0).
    fallback = ability.evaluate(
        prof(_irulan(turn_state)), _chronicler((*hand, starter("reconnaissance")))
    )
    assert (fallback.value, fallback.response) == (
        0.0,
        ((1,), (f"player:{SEAT}:starter:reconnaissance:0",)),
    )
    nothing = ability.evaluate(prof(_irulan(turn_state)), _chronicler(hand))
    assert (nothing.value, nothing.response) == (0.0, None)


def test_chroniclers_insight_specific_card_order(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    ability = ld.ChroniclersInsightAbility(owner("princess_irulan"))
    hand = (starter("reconnaissance"), starter("dune_the_desert_planet"))
    answer = ability.evaluate(prof(_irulan(turn_state)), _chronicler(hand))
    assert answer.response == (
        (1,),
        (f"player:{SEAT}:starter:dune_the_desert_planet:0",),
    )


def test_chroniclers_insight_acquire_evaluate(
    turn_state: GameState, prof: ProfileFactory
) -> None:
    values = {"x": 2.0, "y": 4.5, "z": 4.5}
    p = prof(turn_state, acquire_value=lambda card: Summer(values[card.ref]))
    ability = ld.ChroniclersInsightAcquireAbility(owner("princess_irulan"))
    cards = [synth(Kind.CARD, ref) for ref in ("x", "y", "z")]
    answer = ability.evaluate(p, req(ents(*cards), opts(0)))
    assert (answer.value, answer.response) == (104.5, (("y",), (0,)))
    assert ability.evaluate(p, req()).response is None
    assert ability.meets_cost(p)


# ---------------------------------------------------------------------------
# Shaddam Corrino IV (§11)
# ---------------------------------------------------------------------------


def _tracks() -> TargetInfo:
    return ents(*(track_entity(f) for f in INFLUENCE))


def test_emperor_signet_evaluate(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.EmperorOfTheKnownUniverseSignetAbility(owner("shaddam_corrino_iv"))
    p = prof(turn_state)  # round 1: Round / 3 = 0.333
    best = ability.evaluate(p, req(opts(0, 1), _tracks()))
    assert best.response == ((1,), ("bene_gesserit",))
    assert best.value == pytest.approx(3.0 - 0.75 + 1 / 3)
    # Without the pay option only option 0 (Solari + troop) is offered.
    only = ability.evaluate(p, req(opts(0)))
    assert only.value == pytest.approx(0.25 + 0.9)
    assert only.response == ((0,),)
    # A faction value only equal to option 0 does not replace it.
    flat = prof(
        turn_state,
        gain_influence_value=lambda f, n, r=-1, a=False: Summer(1.15 + 0.75 - 1 / 3),
    )
    tie = ability.evaluate(flat, req(opts(0, 1), _tracks()))
    assert tie.response == ((0,),)


def test_emperor_signet_round_term(turn_state: GameState, prof: ProfileFactory) -> None:
    ability = ld.EmperorOfTheKnownUniverseSignetAbility(owner("shaddam_corrino_iv"))
    p = prof(with_state(turn_state, round_number=6))
    answer = ability.evaluate(p, req(opts(0, 1), ents(track_entity("fremen"))))
    assert answer.value == pytest.approx(1.0 - 0.75 + 2.0)


@pytest.mark.parametrize(
    ("interest", "penalty"),
    [(12.6, -2.0), (12.5, -1.0), (-2.4, -1.0), (-2.5, 0.0)],
)
def test_emperor_signet_value(
    turn_state: GameState, prof: ProfileFactory, interest: float, penalty: float
) -> None:
    ability = ld.EmperorOfTheKnownUniverseSignetAbility(owner("shaddam_corrino_iv"))
    p = prof(turn_state, current_conflict_interest=lambda: Summer(interest))
    # max(Solari(1) + Troop(1), Solari(-3) + best influence 3.0)
    expected = max(0.25 + 0.9, -0.75 + 3.0) + penalty
    assert ability.value_for_player(p, ()).sum == pytest.approx(expected)
    low = prof(
        turn_state,
        current_conflict_interest=lambda: Summer(interest),
        gain_influence_value=lambda f, n, r=-1, a=False: Summer(0.5),
    )
    assert ability.value_for_player(low, ()).sum == pytest.approx(1.15 + penalty)


# ---------------------------------------------------------------------------
# Staban Tuek (§12)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("spies", "value"), [(2, 1.0 + 1.66), (3, 1.0)])
def test_unseen_network_value(
    turn_state: GameState, prof: ProfileFactory, spies: int, value: float
) -> None:
    state = with_player(
        turn_state, SEAT, spy_post_ids=THREE_POSTS[:spies], spies_supply=3 - spies
    )
    ability = ld.UnseenNetworkAbility(owner("staban_tuek"))
    assert ability.value_for_player(prof(state), ()).sum == pytest.approx(value)
    answer = ability.evaluate(prof(state), req())
    assert (answer.value, answer.response) == (1.66, ())


def test_unseen_network_follow_ups(
    effects_state: GameState, prof: ProfileFactory
) -> None:
    landsraad = ld.UnseenNetworkLandsraadAbility(owner("staban_tuek"))
    influence = ld.UnseenNetworkInfluenceAbility(owner("staban_tuek"))
    p = prof(effects_state)
    a = landsraad.evaluate(p, req())
    assert a.value == pytest.approx(-0.5 + 0.75)
    assert a.response == ()
    b = influence.evaluate(p, req())
    assert b.value == pytest.approx(-0.5 + 2.25)
    assert b.response == ()
    # An unaffordable follow-up still answers (MakeChoice filters on > 0).
    poor = influence.evaluate(prof(effects_state, intrigue_value=lambda: 0.4), req())
    assert poor.value == pytest.approx(-0.1)
    funded = with_player(effects_state, SEAT, resources=Resources(solari=2, spice=1))
    at_landsraad = with_frame(
        funded,
        staban_bonus_post="landsraad-high-council-imperial-privilege-swordmaster",
    )
    assert landsraad.meets_cost(prof(at_landsraad))
    assert not influence.meets_cost(prof(at_landsraad))
    dry = with_player(at_landsraad, SEAT, resources=Resources(solari=2))
    assert not landsraad.meets_cost(prof(dry))  # no spice to pay
    at_faction = with_frame(
        funded, staban_bonus_post="emperor-sardaukar-dutiful-service"
    )
    assert influence.meets_cost(prof(at_faction))
    assert not landsraad.meets_cost(prof(at_faction))
    assert not landsraad.meets_cost(prof(funded))  # no follow-up pending
    broke = with_player(at_faction, SEAT, resources=Resources(solari=1))
    assert not influence.meets_cost(prof(broke))


def test_leader_abilities_follow_the_live_face() -> None:
    """The flipped Jessica's abilities come from the Reverend Mother face."""

    assert [type(a) for a in abilities_of(rm_leader())] == [
        ld.WaterOfLifeSignetAbility,
        ld.ReverendMotherAbility,
    ]
    assert [type(a) for a in abilities_of(jessica_leader())] == [
        ld.OtherMemoriesSetupAbility,
        ld.OtherMemoriesAbility,
        ld.OtherMemoriesTriggeredAbility,
        ld.SpiceAgonyAbility,
    ]
