"""The ``agent_effects`` window on Immortality, Epic Game Mode and promo cards.

Each test reaches a real Agent turn of a game with the option on (the first
turn, the deciding seat's hand and board pieces adjusted, then a real
``agent_turn`` and, for a graft, a real ``choose_graft_partner``), builds the
``DecisionRun`` the agent would build and asserts the source the window
builds for the app ability or the exact action it answers. Profile values or
ability answers a branch depends on are pinned (``monkeypatch``).
``intrigue_play_sources`` (another window's) is stubbed.
"""

import random
from collections.abc import Mapping, Sequence

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import epic_promo as ep
from dune_imperium.agents.app_ai.abilities import immortality as imm
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import GainInfluenceAbility
from dune_imperium.agents.app_ai.catalog import card_entity
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects as ae
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

IMM = RulesetConfig(choam_module=False, immortality=True)
EPIC = RulesetConfig(choam_module=False, epic_game=True)
PROMO = RulesetConfig(choam_module=False, promo_cards=True)
PROMO_IMM = RulesetConfig(choam_module=False, promo_cards=True, immortality=True)

type Patches = Mapping[str, object]


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """``intrigue_play_sources`` belongs to the intrigue window: stub it."""

    monkeypatch.setattr(ae, "intrigue_play_sources", lambda run, plays, combat: [])


# ---------------------------------------------------------------------------
# Real states
# ---------------------------------------------------------------------------


def _settle(state: GameState) -> GameState:
    chance = ChanceResolver(seed=1)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _apply(state: GameState, seat: int, action: DomainAction) -> GameState:
    legal = ENGINE.legal_actions(state, seat)
    return _settle(ENGINE.apply(state, action, legal_actions=legal).state)


def _take(state: GameState, seat: int, card: str) -> tuple[GameState, str]:
    """Move one copy of ``card`` into ``seat``'s hand (its own piles, the
    Imperium deck or Row, the Tleilaxu deck or Row) and return its id."""

    me = state.players[seat]
    for zone in ("hand", "deck", "discard_pile"):
        for ref in getattr(me, zone):
            if f":{card}:" in ref:
                if zone == "hand":
                    return state, ref
                rest = tuple(r for r in getattr(me, zone) if r != ref)
                return with_player(
                    state, seat, **{zone: rest}, hand=(ref, *me.hand)
                ), ref
    for zone, prefix in (
        ("imperium_deck", "imperium"),
        ("imperium_row", "imperium"),
        ("tleilaxu_deck", "tleilaxu"),
        ("tleilaxu_row", "tleilaxu"),
    ):
        for ref in getattr(state, zone):
            if ref.startswith(f"{prefix}:{card}:"):
                rest = tuple(r for r in getattr(state, zone) if r != ref)
                state = with_state(state, **{zone: rest})
                hand = (ref, *state.players[seat].hand)
                return with_player(state, seat, hand=hand), ref
    raise KeyError(card)


def _place(
    config: RulesetConfig,
    card: str,
    *,
    space: str | None = None,
    partner: str | None = None,
    extra: Sequence[str] = (),
    **before: object,
) -> tuple[GameState, int, str, str | None]:
    """The first turn's seat plays ``card`` (grafted with ``partner``) to
    ``space`` (any legal one); ``before`` adjusts the seat first."""

    state = first_decision("turn", config=config, seed=1)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    for other in extra:
        state, _ = _take(state, seat, other)
    partner_ref = None
    if partner is not None:
        state, partner_ref = _take(state, seat, partner)
    state, ref = _take(state, seat, card)
    if before:
        state = with_player(state, seat, **before)
    legal = ENGINE.legal_actions(state, seat)
    placements = [
        action
        for action in legal
        if action.action_id == "agent_turn"
        and arg(action, "card_id") == ref
        and (space is None or arg(action, "space_id") == space)
        and (arg(action, "graft") is True) == (partner is not None)
        and arg(action, "infiltrate_post_id") is None
    ]
    assert placements, f"{card} cannot go to {space}"
    state = _apply(state, seat, placements[0])
    if partner_ref is not None:
        legal = ENGINE.legal_actions(state, seat)
        pick = [
            action
            for action in legal
            if action.action_id == "choose_graft_partner"
            and arg(action, "card_id") == partner_ref
        ]
        assert pick, f"{partner} is no legal partner of {card}"
        state = _apply(state, seat, pick[0])
    assert state.decision_stack[-1].kind == "agent_effects"
    return state, seat, ref, partner_ref


def _run(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DecisionRun:
    profile = make_profile(state, seat)
    for name, value in (patches or {}).items():
        setattr(profile, name, value)
    legal = ENGINE.legal_actions(state, seat)
    return DecisionRun(
        profile.ctx, profile, legal, random.Random(0), memory or Memory()
    )


def _turn(state: GameState, seat: int, patches: Patches | None = None) -> ae._Turn:
    t = ae._turn(_run(state, seat, patches))
    ae._collect(t)
    return t


def _source(t: ae._Turn, label: str) -> Source:
    found = [s for s in t.sources if s.label == label]
    assert found, (label, [s.label for s in t.sources])
    return found[0]


def _evaluate(source: Source) -> tuple[float, DomainAction | None]:
    assert source.evaluate is not None
    return source.evaluate()


def _a(seat: int, action_id: str, **arguments: str | int) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(arguments.items())
    )


def _answer(
    state: GameState,
    seat: int,
    patches: Patches | None = None,
    memory: Memory | None = None,
) -> DomainAction | None:
    return ae.agent_effects_window(_run(state, seat, patches, memory))


def _drive_until(
    state: GameState,
    seat: int,
    action_ids: Sequence[str],
    patches: Patches | None = None,
    memory: Memory | None = None,
    limit: int = 30,
) -> tuple[DomainAction, GameState, Memory]:
    """Answer the seat's Agent turn with the window until it answers one of
    ``action_ids``; return that answer (not applied)."""

    memory = memory or Memory()
    for _ in range(limit):
        assert state.decision_stack[-1].kind == "agent_effects"
        legal = ENGINE.legal_actions(state, seat)
        action = _answer(state, seat, patches, memory)
        assert action is not None and action in legal
        if action.action_id in action_ids:
            return action, state, memory
        state = _apply(state, seat, action)
    raise AssertionError(f"never answered {action_ids}")


def _ids(t: ae._Turn) -> set[str]:
    return {a.action_id for a in t.run.legal}


def _specimens(n: int) -> dict[str, object]:
    """Seat changes for ``n`` specimens (troops move from the supply)."""

    return {"specimens": n}


def _with_specimens(state: GameState, seat: int, n: int) -> GameState:
    me = state.players[seat]
    return with_player(
        state, seat, specimens=n, troops_supply=me.troops_supply - n + me.specimens
    )


# ---------------------------------------------------------------------------
# Epic Game Mode: Control the Spice (the silent-decline defect)
# ---------------------------------------------------------------------------


def test_control_the_spice_pays_and_keeps_its_trash_card() -> None:
    state, seat, ref, _ = _place(
        EPIC, "control_the_spice", resources=Resources(solari=0, spice=2, water=1)
    )
    worth_it = {"trash_card_value": lambda: 5.0}
    t = _turn(state, seat, worth_it)
    source = _source(t, "Control the Spice")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is False
    value, action = _evaluate(source)
    assert action == _a(seat, "pay_agent_card_spice") and value > 0
    key = (ae.CONTROL_THE_SPICE_TRASH_INTENT, state.round_number, ref)
    ((stored_key, card),) = t.on_choose[action]
    assert stored_key == key
    me = state.players[seat]
    assert card in (*me.hand, *me.in_play, *me.discard_pile)
    assert _a(seat, "decline_agent_card_payment") in t.declines

    chosen, _state, memory = _drive_until(
        state, seat, ("pay_agent_card_spice", "decline_agent_card_payment"), worth_it
    )
    assert chosen == _a(seat, "pay_agent_card_spice")
    assert isinstance(memory.intents[key], str)


def test_control_the_spice_without_a_card_worth_trashing_declines() -> None:
    state, seat, ref, _ = _place(
        EPIC, "control_the_spice", resources=Resources(solari=0, spice=2, water=1)
    )
    patches = {"card_to_trash": lambda targets, minimum: (None, 0.0)}
    t = _turn(state, seat, patches)
    assert _evaluate(_source(t, "Control the Spice")) == (0.0, None)
    chosen, _state, memory = _drive_until(
        state, seat, ("pay_agent_card_spice", "decline_agent_card_payment"), patches
    )
    assert chosen == _a(seat, "decline_agent_card_payment")
    assert (ae.CONTROL_THE_SPICE_TRASH_INTENT, state.round_number, ref) not in (
        memory.intents
    )


# ---------------------------------------------------------------------------
# Promos
# ---------------------------------------------------------------------------


def _arrakis_revolt(
    monkeypatch: pytest.MonkeyPatch, answer: Answer, blow: bool
) -> tuple[ae._Turn, int]:
    monkeypatch.setattr(ep.ArrakisRevoltAbility, "evaluate", lambda self, p, r: answer)
    monkeypatch.setattr(Profile, "should_blow_wall", lambda self: blow)
    state, seat, _ref, _ = _place(
        PROMO,
        "arrakis_revolt",
        space="arrakeen",
        resources=Resources(solari=5, spice=4, water=1),
        maker_hooks=True,
    )
    return _turn(state, seat), seat


def test_arrakis_revolt_blows_the_wall_when_should_blow_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    t, seat = _arrakis_revolt(monkeypatch, Answer(5.0, ()), True)
    source = _source(t, "Arrakis Revolt")
    assert source.extra["explicit"] is False
    assert _evaluate(source) == (
        5.0,
        _a(seat, "pay_agent_card_spice_for_sandworm_and_shield_wall"),
    )
    assert _a(seat, "decline_agent_card_payment") in t.declines


def test_arrakis_revolt_keeps_the_wall_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    t, seat = _arrakis_revolt(monkeypatch, Answer(5.0, ()), False)
    assert _evaluate(_source(t, "Arrakis Revolt")) == (
        5.0,
        _a(seat, "pay_agent_card_spice_for_sandworm"),
    )


def test_arrakis_revolt_unused_key_is_the_decline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    t, _seat = _arrakis_revolt(monkeypatch, Answer(0.0, None), True)
    assert _evaluate(_source(t, "Arrakis Revolt")) == (0.0, None)


def test_pivotal_gambit_trashes_itself_then_its_icons_follow() -> None:
    state, seat, ref, _ = _place(PROMO, "pivotal_gambit", space="desert_tactics")
    t = _turn(state, seat)
    source = _source(t, "pivotal_gambit trash")
    assert _evaluate(source) == (100.0, _a(seat, "trash_agent_card", card_id=ref))
    assert _a(seat, "decline_agent_card_trash") in t.declines
    state = _apply(state, seat, _a(seat, "trash_agent_card", card_id=ref))
    # Troop and pledge are the rest of the one app answer: before the board.
    answer = _answer(state, seat)
    assert answer is not None
    assert answer.action_id == "resolve_agent_card_effect"
    assert arg(answer, "effect") in ("troops", "pledge")


def _objective(icon: str) -> str:
    from dune_imperium.content.uprising.objectives import OBJECTIVES

    return next(o.objective_id for o in OBJECTIVES if str(o.battle_icon) == icon)


def test_the_beasts_spoils_box_runs_its_icon_rider_immediately() -> None:
    state, seat, _ref, _ = _place(
        PROMO,
        "the_beast_s_spoils",
        space="arrakeen",
        objective_ids=(_objective("desert_mouse"),),
    )
    source = _source(_turn(state, seat), "the_beast_s_spoils box")
    assert source.stage is Stage.IMMEDIATE


def test_the_beasts_spoils_crysknife_only_is_the_generic_box_then_a_trash() -> None:
    state, seat, _ref, _ = _place(
        PROMO,
        "the_beast_s_spoils",
        space="arrakeen",
        objective_ids=(_objective("crysknife"),),
    )
    source = _source(_turn(state, seat), "the_beast_s_spoils box")
    assert source.stage is Stage.AGENT_BOX
    state = _apply(state, seat, source.actions[0])
    t = _turn(state, seat)
    trash = _source(t, "the_beast_s_spoils trash")
    assert trash.extra["explicit"] is True  # TrashAbility: Explicit
    assert _a(seat, "decline_agent_card_trash") in t.declines


# ---------------------------------------------------------------------------
# Immortality card choices
# ---------------------------------------------------------------------------


def test_organ_merchants_key_is_its_specimen_for_solari_e() -> None:
    state, seat, ref, _ = _place(IMM, "organ_merchants")
    state = _with_specimens(state, seat, 1)
    t = _turn(state, seat)
    value, action = _evaluate(_source(t, "OrganMerchantsAbility"))
    expected = imm.OrganMerchantsAbility(card_entity(ref, seat)).evaluate(
        t.p, Request()
    )
    assert value == expected.value
    assert action == _a(seat, "pay_agent_card_specimen")
    assert t.declines == [_a(seat, "decline_agent_card_payment")]


def test_tleilaxu_surgeon_never_pays_past_tleilaxu_rank_seven() -> None:
    state, seat, _ref, _ = _place(IMM, "tleilaxu_surgeon")
    state = _with_specimens(state, seat, 2)
    assert "pay_agent_card_two_specimens" in _ids(_turn(state, seat))
    labels = [s.label for s in _turn(state, seat).sources]
    assert "TleilaxuSurgeonAgentAbility" in labels
    at_end = with_player(state, seat, tleilaxu_space=7)
    t = _turn(at_end, seat)
    assert "pay_agent_card_two_specimens" in _ids(t)
    assert "TleilaxuSurgeonAgentAbility" not in [s.label for s in t.sources]
    assert t.declines == [_a(seat, "decline_agent_card_payment")]


def test_dissecting_kit_always_trashes_its_partner() -> None:
    state, seat, _ref, _ = _place(IMM, "dissecting_kit", partner="dagger")
    source = _source(_turn(state, seat), "DissectingKitAgentAbility")
    assert _evaluate(source) == (100.0, _a(seat, "trash_grafted_card_for_specimen"))


def test_scientific_breakthrough_trashes_for_vp_before_its_research() -> None:
    state, seat, _ref, _ = _place(
        IMM, "scientific_breakthrough", space="assembly_hall", research_space="c8r6"
    )
    t = _turn(state, seat)
    trash = _source(t, "ScientificBreakthroughAbility")
    assert _evaluate(trash) == (100.0, _a(seat, "trash_agent_card_self_for_vp"))
    research = _source(t, "scientific_breakthrough box")
    assert research.extra["explicit"] is True
    research_value, _action = _evaluate(research)
    assert research_value < 100.0
    chosen, _state, _memory = _drive_until(
        state, seat, ("trash_agent_card_self_for_vp", "resolve_agent_card_effect")
    )
    assert chosen == _a(seat, "trash_agent_card_self_for_vp")


def test_high_priority_travel_takes_the_combat_icon_or_draws() -> None:
    state, seat, _ref, _ = _place(
        IMM,
        "high_priority_travel",
        space="assembly_hall",
        influence=Influence(spacing_guild=2),
    )
    eager = {
        "conflict_posture_bounds": lambda: (0.0, 10.0),
        "current_conflict_interest": lambda: _summer(5.0),
    }
    source = _source(_turn(state, seat, eager), "High Priority Travel")
    assert source.extra["explicit"] is True
    assert _evaluate(source)[1] == _a(seat, "take_agent_card_combat_icon")
    calm = {
        "conflict_posture_bounds": lambda: (10.0, 20.0),
        "current_conflict_interest": lambda: _summer(5.0),
    }
    source = _source(_turn(state, seat, calm), "High Priority Travel")
    assert _evaluate(source)[1] == _a(seat, "resolve_agent_card_effect")


def _summer(value: float) -> object:
    from dune_imperium.agents.app_ai.summer import Summer

    s = Summer()
    s.add("pinned", value)
    return s


def test_slig_farmer_pays_five_for_tleilaxu_when_its_key_is_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref, _ = _place(
        IMM,
        "slig_farmer",
        partner="dagger",
        resources=Resources(solari=5, spice=0, water=1),
    )
    monkeypatch.setattr(
        imm.SligFarmerTleilaxuAbility, "evaluate", lambda self, p, r: Answer(2.0, ())
    )
    source = _source(_turn(state, seat), "slig_farmer box")
    assert source.stage is Stage.IMMEDIATE  # the Solari: CanRunImmediately
    assert source.actions == (_a(seat, "pay_agent_card_five_solari_for_tleilaxu"),)
    monkeypatch.setattr(
        imm.SligFarmerTleilaxuAbility, "evaluate", lambda self, p, r: Answer(-1.0, ())
    )
    source = _source(_turn(state, seat), "slig_farmer box")
    assert source.actions == (_a(seat, "resolve_agent_card_effect"),)


def test_slig_farmer_never_pays_past_tleilaxu_rank_seven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref, _ = _place(
        IMM,
        "slig_farmer",
        partner="dagger",
        resources=Resources(solari=5, spice=0, water=1),
        tleilaxu_space=7,
    )
    monkeypatch.setattr(
        imm.SligFarmerTleilaxuAbility, "evaluate", lambda self, p, r: Answer(2.0, ())
    )
    source = _source(_turn(state, seat), "slig_farmer box")
    assert source.actions == (_a(seat, "resolve_agent_card_effect"),)


def _switched(state: GameState, seat: int) -> GameState:
    """The state after ``switch_graft_card`` (the partner's box active)."""

    return _apply(state, seat, _a(seat, "switch_graft_card"))


def test_beguiling_pheromones_picks_the_grafted_card_to_trash() -> None:
    state, seat, ref, partner = _place(
        IMM, "seek_allies", partner="beguiling_pheromones", space="fremkit"
    )
    assert partner is not None
    state = _switched(state, seat)
    t = _turn(state, seat)
    source = _source(t, "Beguiling Pheromones")
    assert source.extra["explicit"] is True
    value, action = _evaluate(source)
    expected = imm.BeguilingPheromonesAbility(card_entity(partner, seat)).evaluate(
        t.p,
        Request(
            infos=(
                TargetInfo(
                    entities=tuple(
                        card_entity(r, seat)
                        for r in ae._arg_refs(source.actions, "card_id")
                    )
                ),
            )
        ),
    )
    assert value == expected.value
    assert action == _a(
        seat,
        "trash_grafted_card_for_influence",
        card_id=str(ae._response_ref(expected)),
    )
    assert ref != partner


def test_piter_loses_the_troop_the_app_names() -> None:
    state, seat, _ref, _ = _place(PROMO_IMM, "piter_genius_advisor")
    t = _turn(state, seat, {"research_value": lambda: _summer(5.0)})
    value, action = _evaluate(_source(t, "Piter"))
    assert value > 0
    assert action == _a(seat, "lose_agent_card_troop", zone="garrison")
    assert t.declines == [_a(seat, "decline_agent_card_payment")]


def test_stitched_horror_answers_two_rewards_over_two_decisions() -> None:
    state, seat, ref, _ = _place(IMM, "stitched_horror", partner="dagger")
    pinned = {
        "water_value": lambda n: 9.0,
        "troop_value": lambda n, *a: 8.0,
        "tleilaxu_value": lambda n: _summer(1.0),
        "card_to_trash": lambda targets, minimum: (None, 0.0),
    }
    t = _turn(state, seat, pinned)
    source = _source(t, "Stitched Horror")
    assert source.extra["explicit"] is True
    value, action = _evaluate(source)
    assert value == 17.0
    assert action == _a(seat, "choose_agent_card_reward", reward="water")
    key = ("agent_effects", "stitched_horror", state.round_number, ref)
    assert t.on_choose[action] == [(key, "troop")]
    memory = Memory()
    memory.intents[key] = "troop"
    state = _apply(state, seat, action)
    second = _answer(state, seat, memory=memory)
    assert second == _a(seat, "choose_agent_card_reward", reward="troop")


def test_twisted_mentat_recalls_the_agent_it_sent() -> None:
    state, seat, _ref, _ = _place(
        IMM, "twisted_mentat", partner="dagger", space="assembly_hall"
    )
    t = _turn(state, seat)
    source = _source(t, "Twisted Mentat recall")
    assert source.extra["explicit"] is False
    assert _evaluate(source) == (
        100.0,
        _a(seat, "recall_agent_for_agent_card", space_id="assembly_hall"),
    )
    assert t.declines == [_a(seat, "decline_agent_card_recall")]


def test_long_reach_names_both_tracks_at_once() -> None:
    state, seat, ref, _ = _place(
        IMM, "long_reach", partner="ghola", space="assembly_hall"
    )
    t = _turn(state, seat)
    source = _source(t, "Long Reach")
    value, action = _evaluate(source)
    assert action is not None and action.action_id == "choose_agent_card_influence"
    ((key, second),) = t.on_choose[action]
    assert key == ("agent_effects", "long_reach", state.round_number, ref)
    assert second != arg(action, "faction")
    memory = Memory()
    memory.intents[key] = second
    state = _apply(state, seat, action)
    assert _answer(state, seat, memory=memory) == _a(
        seat, "choose_agent_card_influence", faction=str(second)
    )


def test_for_humanity_takes_the_best_track() -> None:
    state, seat, _ref, _ = _place(IMM, "for_humanity", space="secrets")
    t = _turn(state, seat)
    source = _source(t, "for_humanity influence")
    assert source.extra["explicit"] is True
    value, action = _evaluate(source)
    best = max(FACTIONS, key=lambda f: t.p.gain_influence_value(f, 1, -1, False).sum)
    assert action == _a(seat, "choose_agent_card_influence", faction=best)
    assert value == t.p.gain_influence_value(best, 1, -1, False).sum + 100.0


def test_interstellar_conspiracy_influence_with_an_emperor_partner() -> None:
    state, seat, _ref, _ = _place(
        IMM, "interstellar_conspiracy", partner="imperial_spymaster"
    )
    t = _turn(state, seat)
    value, action = _evaluate(_source(t, "interstellar_conspiracy influence"))
    assert action is not None and action.action_id == "choose_agent_card_influence"


def test_tleilaxu_master_acquires_the_best_card_by_acquire_value() -> None:
    state, seat, _ref, _ = _place(
        IMM, "tleilaxu_master", space="assembly_hall", research_space="c4r4"
    )
    t = _turn(state, seat)
    source = _source(t, "Tleilaxu Master")
    assert source.extra["explicit"] is False
    value, action = _evaluate(source)
    offered = [
        a.action_id == "acquire_imperium_by_card" and str(arg(a, "instance_id"))
        for a in t.run.legal
    ]
    row = [ref for ref in offered if ref]
    best = None
    best_value = 0.0
    for ref in row:
        v = t.p.acquire_value(card_entity(ref, seat)).sum
        if best is None or v > best_value:
            best, best_value = ref, v
    assert value >= best_value
    assert action is not None and action.action_id in (
        "acquire_imperium_by_card",
        "acquire_reserve_by_card",
    )
    assert _a(seat, "decline_agent_card_acquisition") in t.declines


def test_replacement_eyes_trashes_the_card_its_e_names() -> None:
    state, seat, ref, _ = _place(IMM, "replacement_eyes", partner="dagger")
    t = _turn(state, seat)
    source = _source(t, "replacement_eyes trash")
    assert source.extra["explicit"] is False
    _value, action = _evaluate(source)
    assert action is not None and action.action_id == "trash_agent_card"
    assert _a(seat, "decline_agent_card_trash") in t.declines


def test_sardaukar_quartermaster_icons_map_to_their_riders() -> None:
    state, seat, _ref, _ = _place(
        IMM, "sardaukar_quartermaster", partner="face_dancer", space="assembly_hall"
    )
    t = _turn(state, seat)
    troops = _source(t, "sardaukar_quartermaster troops")
    assert troops.stage is Stage.IMMEDIATE  # AlwaysRunImmediately
    cards = _source(t, "sardaukar_quartermaster cards")
    assert cards.stage in (Stage.IMMEDIATE, Stage.PROMPT)  # a DrawAbility


def test_tleilaxu_infiltrator_intrigue_waits_at_its_defer_value() -> None:
    state, seat, _ref, _ = _place(
        IMM, "tleilaxu_infiltrator", partner="dagger", research_space="c8r6"
    )
    t = _turn(state, seat)
    intrigue = _source(t, "tleilaxu_infiltrator intrigue")
    assert intrigue.extra["explicit"] is True
    assert _evaluate(intrigue) == (
        2.0,
        _a(seat, "resolve_agent_card_effect", effect="intrigue"),
    )


# ---------------------------------------------------------------------------
# Immortality single boxes
# ---------------------------------------------------------------------------


def test_experimentation_research_is_an_explicit_key_at_its_e() -> None:
    state, seat, ref, _ = _place(IMM, "experimentation")
    t = _turn(state, seat)
    source = _source(t, "experimentation box")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True
    value, action = _evaluate(source)
    expected = imm.GainResearchAgentAbility(card_entity(ref, seat)).evaluate(
        t.p, ae._research_request(t)
    )
    assert (value, action) == (expected.value, _a(seat, "resolve_agent_card_effect"))
    assert len(ae._research_request(t).infos[0].entities) == len(
        t.run.ctx.research_next_space_ids()
    )


def test_research_station_research_icon_is_the_spaces_research_ability() -> None:
    state, seat, _ref, _ = _place(
        IMM,
        "occupation",
        space="research_station",
        resources=Resources(solari=0, spice=0, water=2),
    )
    t = _turn(state, seat)
    source = _source(t, "board research")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True
    assert _evaluate(source)[1] == _a(seat, "resolve_board_effect", effect="research")


def test_bene_tleilax_lab_specimen_runs_at_state_210_before_the_space() -> None:
    state, seat, _ref, _ = _place(IMM, "bene_tleilax_lab", space="arrakeen")
    t = _turn(state, seat)
    source = _source(t, "bene_tleilax_lab box")
    assert (source.stage, source.order) == (Stage.COST_FIRST, ae._FIRST_ABILITY_ORDER)
    assert _answer(state, seat) == _a(seat, "resolve_agent_card_effect")


def test_from_the_tanks_is_the_generic_box() -> None:
    state, seat, _ref, _ = _place(IMM, "from_the_tanks", space="assembly_hall")
    source = _source(_turn(state, seat), "from_the_tanks box")
    assert (source.stage, source.order) == (Stage.AGENT_BOX, 0)


def test_contaminator_at_tleilaxu_rank_seven_has_no_app_key() -> None:
    state, seat, _ref, _ = _place(IMM, "contaminator", tleilaxu_space=7)
    t = _turn(state, seat)
    assert "contaminator box" not in [s.label for s in t.sources]
    assert _a(seat, "resolve_agent_card_effect") in t.chores
    state, seat, _ref, _ = _place(IMM, "contaminator")
    source = _source(_turn(state, seat), "contaminator box")
    assert source.extra["explicit"] is True  # GainTleilaxuInfluenceAgentAbility


def test_stillsuit_manufacturer_returns_only_with_the_fremen_alliance() -> None:
    state, seat, _ref, _ = _place(IMM, "stillsuit_manufacturer", space="desert_tactics")
    source = _source(_turn(state, seat), "stillsuit_manufacturer box")
    assert source.stage is Stage.AGENT_BOX  # the AgentWater box alone
    allied = with_player(state, seat, alliance_faction_ids=("fremen",))
    source = _source(_turn(allied, seat), "stillsuit_manufacturer box")
    assert source.stage is Stage.PROMPT
    assert _evaluate(source) == (100.0, _a(seat, "resolve_agent_card_effect"))


def test_throne_room_politics_waits_for_its_trash_key() -> None:
    state, seat, _ref, _ = _place(IMM, "throne_room_politics")
    t = _turn(state, seat)
    source = _source(t, "throne_room_politics box")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True


def test_industrial_espionage_alone_is_its_draw() -> None:
    state, seat, _ref, _ = _place(IMM, "industrial_espionage", space="assembly_hall")
    source = _source(_turn(state, seat), "industrial_espionage box")
    assert source.stage in (Stage.IMMEDIATE, Stage.PROMPT)  # DrawAbility
    assert source.actions == (_a(seat, "resolve_agent_card_effect"),)


def test_industrial_espionage_grafted_asks_its_research() -> None:
    state, seat, _ref, _ = _place(
        IMM, "face_dancer", partner="industrial_espionage", space="deliver_supplies"
    )
    state = _switched(state, seat)
    t = _turn(state, seat)
    source = _source(t, "industrial_espionage box")
    assert source.stage is Stage.PROMPT and source.extra["explicit"] is True


def test_clandestine_meeting_influence_asks_once_the_threshold_is_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref, _ = _place(
        IMM, "face_dancer", partner="clandestine_meeting", space="deliver_supplies"
    )
    state = _switched(state, seat)
    monkeypatch.setattr(ae, "_immediate", lambda ability, p: False)
    source = _source(_turn(state, seat), "clandestine_meeting box")
    assert source.stage is Stage.PROMPT
    monkeypatch.undo()
    monkeypatch.setattr(ae, "intrigue_play_sources", lambda run, plays, combat: [])
    monkeypatch.setattr(ae, "_immediate", lambda ability, p: True)
    source = _source(_turn(state, seat), "clandestine_meeting box")
    assert source.stage is Stage.IMMEDIATE


# ---------------------------------------------------------------------------
# Graft: Ghola and the two boxes
# ---------------------------------------------------------------------------


def test_ghola_resolves_the_partners_box_at_state_210() -> None:
    state, seat, ref, partner = _place(IMM, "ghola", partner="from_the_tanks")
    t = _turn(state, seat)
    assert t.ghola and t.card_short == "from_the_tanks" and t.card_ref == ref
    source = _source(t, "from_the_tanks box")
    assert (source.stage, source.order) == (Stage.COST_FIRST, ae._FIRST_ABILITY_ORDER)
    assert partner is not None


def test_the_partners_box_500_comes_before_the_played_cards_600() -> None:
    state, seat, ref, partner = _place(
        IMM, "face_dancer", partner="from_the_tanks", space="deliver_supplies"
    )
    assert partner is not None
    memory = Memory()
    answer, state, memory = _drive_until(
        state,
        seat,
        ("switch_graft_card", "resolve_agent_card_effect"),
        memory=memory,
    )
    assert answer == _a(seat, "switch_graft_card")
    key = (ae._GRAFT_SWITCH_INTENT, state.round_number, partner)
    assert memory.intents[key] == (_a(seat, "resolve_agent_card_effect"), [])
    state = _apply(state, seat, answer)
    assert _answer(state, seat, memory=memory) == _a(seat, "resolve_agent_card_effect")
    assert key not in memory.intents


def test_the_played_cards_box_resolves_before_the_partners() -> None:
    state, seat, _ref, partner = _place(
        IMM, "face_dancer", partner="from_the_tanks", space="deliver_supplies"
    )
    state = _switched(state, seat)  # the partner active, played card waiting
    t = _turn(state, seat)
    assert t.rank == 1 and t.card_ref == partner
    source = _source(t, "from_the_tanks box")
    assert (source.stage, source.order) == (Stage.AGENT_BOX, 1)


def test_a_waiting_partner_box_is_switched_to_before_the_turn_ends() -> None:
    state, seat, _ref, _partner = _place(
        IMM, "dagger", partner="beguiling_pheromones", space="assembly_hall"
    )
    # Beguiling Pheromones' box waits (no Faction space): nothing to resolve,
    # but no End Turn either until it is the active box.
    answer, state, _memory = _drive_until(
        state, seat, ("switch_graft_card", "finish_agent_turn")
    )
    assert answer == _a(seat, "switch_graft_card")
    assert "finish_agent_turn" not in {
        a.action_id for a in ENGINE.legal_actions(state, seat)
    }
    state = _apply(state, seat, answer)
    assert _answer(state, seat) == _a(seat, "finish_agent_turn")


# ---------------------------------------------------------------------------
# Deployment off a Combat space, playmat keys, no guessing
# ---------------------------------------------------------------------------


def test_occupation_deploys_through_its_own_deploy_units() -> None:
    state, seat, _ref, _ = _place(IMM, "occupation", space="dutiful_service")
    state = _apply(state, seat, _a(seat, "resolve_agent_card_effect"))
    t = _turn(state, seat)
    assert "deploy_troops" in _ids(t)
    source = _source(t, "Deploy Units")
    assert source.extra["explicit"] is False
    found, _garrison = ae._card_deploy_ability(t, 2)
    assert found is not None and type(found[0]).__name__ == "DeployUnitsAbility"


def test_return_specimen_only_for_a_troop_shortfall() -> None:
    state, seat, _ref, _ = _place(IMM, "experimentation")
    state = _with_specimens(state, seat, 1)
    t = _turn(state, seat)
    assert _evaluate(_source(t, "Return Specimen")) == (0.0, None)
    short = with_player(state, seat, ungained_troops=1)
    t = _turn(short, seat)
    assert _evaluate(_source(t, "Return Specimen")) == (
        1.0,
        _a(seat, "return_specimen"),
    )


def test_family_atomics_is_never_used_in_an_agent_turn() -> None:
    state, seat, _ref, _ = _place(IMM, "experimentation")
    source = _source(_turn(state, seat), "Family Atomics")
    assert _evaluate(source)[1] is None


def test_an_unmapped_card_choice_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    state, seat, _ref, _ = _place(IMM, "organ_merchants")
    state = _with_specimens(state, seat, 1)
    monkeypatch.setattr(ae, "_PAYMENT_HANDLERS", {})
    t = _turn(state, seat)
    assert t.unmapped == ["organ_merchants payment"]
    assert _answer(state, seat) is None


def test_a_signet_box_without_an_app_ability_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A leader whose Signet box has no app ability (Bloodlines' Piter de
    # Vries and Liet Kynes reach this today) is not resolved automatically.
    state, seat, _ref, _ = _place(
        PROMO,
        "signet_ring",
        space="assembly_hall",
        leader_id="gurney_halleck",
        leader_face_id=None,
    )
    assert "resolve_agent_card_effect" in _ids(_turn(state, seat))
    assert "signet gurney_halleck" in [s.label for s in _turn(state, seat).sources]
    monkeypatch.setattr(ae, "_SIGNET_BOX_ABILITY", {})
    t = _turn(state, seat)
    assert t.unmapped == ["signet gurney_halleck"]
    assert "signet gurney_halleck" not in [s.label for s in t.sources]
    assert _answer(state, seat) is None


def test_a_choice_without_its_app_ability_is_not_dropped_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A Maker space whose app ability is missing (Arrakeen Scouts' Maker
    # spaces today) used to lose its harvest/summon key without a trace.
    state, seat, _ref, _ = _place(PROMO, "signet_ring", space="hagga_basin")
    t = _turn(state, seat)
    assert "Maker space" in [s.label for s in t.sources] and not t.unmapped
    real_find = ae._find
    monkeypatch.setattr(
        ae,
        "_find",
        lambda owner, short: (
            None
            if short
            in ("HaggaBasinUprisingDeferredAbility", "DeepDesertDeferredAbility")
            else real_find(owner, short)
        ),
    )
    t = _turn(state, seat)
    assert t.unmapped == ["Maker space"]
    assert _answer(state, seat) is None


def test_a_spy_choice_without_its_app_ability_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref, _ = _place(IMM, "diplomacy", space="secrets")
    # Secrets' own Spy (the Bene Gesserit Operative-style ``PlaceSpyAgentAbility``
    # stands in): an Espionage-family key with no app ability falls back.
    t = _turn(state, seat)
    assert not t.unmapped
    place = (_a(seat, "resolve_espionage_place_spy", post_id="landsraad-secrets"),)
    ae._spy_source(t, "Espionage spy", None, place, (), None, "flag")
    assert t.unmapped == ["Espionage spy"]
    assert "Espionage spy" not in [s.label for s in t.sources]


def test_a_space_influence_without_its_app_ability_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat, _ref, _ = _place(IMM, "diplomacy", space="secrets")
    assert "resolve_faction_influence" in _ids(_turn(state, seat))
    real_first_of = ae._first_of
    monkeypatch.setattr(
        ae,
        "_first_of",
        lambda owner, kind: (
            None if kind is GainInfluenceAbility else real_first_of(owner, kind)
        ),
    )
    assert "faction influence" in _turn(state, seat).unmapped


def test_corrinth_city_keeps_its_second_discard_only_when_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: the second discard was written into Memory.intents on every
    # evaluation, so a key that lost (declined) left a stale plan behind.
    from dune_imperium.agents.app_ai.abilities import imperium_a

    state, seat, ref, _ = _place(
        IMM,
        "corrinth_city",
        resources=Resources(solari=5, spice=5, water=1),
    )
    assert "select_corrinth_city_discard" in _ids(_turn(state, seat))
    key = ("agent_effects", "corrinth_city", state.round_number, ref)

    def two_first(value: float) -> object:
        def evaluate(self: object, p: Profile, request: Request) -> Answer:
            first, second = request.infos[0].entities[:2]
            return Answer(value, ((first.ref, second.ref),))

        return evaluate

    for value, kept in ((-1.0, False), (5.0, True)):
        monkeypatch.setattr(
            imperium_a.CorrinthCityAgentAbility, "evaluate", two_first(value)
        )
        memory = Memory()
        chosen, at, memory = _drive_until(
            state,
            seat,
            ("select_corrinth_city_discard", "decline_corrinth_city_payment"),
            memory=memory,
        )
        assert (chosen.action_id == "select_corrinth_city_discard") is kept
        assert (key in memory.intents) is kept
        fresh = Memory()
        t = ae._turn(_run(at, seat, memory=fresh))
        ae._collect(t)
        _evaluate(_source(t, "Corrinth City"))
        assert key not in fresh.intents  # evaluating alone writes nothing


def test_an_unknown_action_id_falls_back_instead_of_being_skipped() -> None:
    # Regression: legal ids no builder knows (Bloodlines' deploy_commanders,
    # recruit_sardaukar_commander, tech; Arrakeen Scouts' scouts_collect_mission,
    # choose_subcommittee) were left out of the ranking, so an optional one was
    # skipped by End Turn while the decision counted as mirrored.
    state, seat, _ref, _ = _place(IMM, "experimentation")
    run = _run(state, seat)
    assert ae.agent_effects_window(run) is not None
    extra = _a(seat, "deploy_commanders", count=1)
    widened = DecisionRun(run.ctx, run.profile, (*run.legal, extra), run.rng, Memory())
    t = ae._turn(widened)
    ae._collect(t)
    assert t.unmapped == ["unknown action deploy_commanders"]
    assert ae.agent_effects_window(widened) is None


_EXPANSION_ABILITY_NAMES = (
    *ae._EXPANSION_BOX_ABILITY.items(),
    *(
        (card, name)
        for (card, _icon), name in ae._ICON_ABILITY.items()
        if card in ("sardaukar_quartermaster", "tleilaxu_infiltrator")
    ),
    ("replacement_eyes", ae._TRASH_ABILITY["replacement_eyes"]),
    ("the_beast_s_spoils", ae._TRASH_ABILITY["the_beast_s_spoils"]),
    ("the_beast_s_spoils", "TheBeastsSpoilsOrnithopterAbility"),
    ("for_humanity", ae._CARD_INFLUENCE_ABILITY["for_humanity"]),
    ("interstellar_conspiracy", ae._CARD_INFLUENCE_ABILITY["interstellar_conspiracy"]),
    ("experimentation", "GainResearchAgentAbility"),
    ("bene_tleilax_researcher", "GainResearchAgentAbility"),
    ("scientific_breakthrough", "GainResearchAgentAbility"),
    ("scientific_breakthrough", "ScientificBreakthroughAbility"),
    ("clandestine_meeting", "AgentGainIntrigueAbility"),
    ("stillsuit_manufacturer", "StillsuitManufacturerAgentAbility"),
    ("throne_room_politics", "TrashAgentAbility"),
    ("industrial_espionage", "IndustrialEspionageResearchAbility"),
    ("organ_merchants", "OrganMerchantsAbility"),
    ("tleilaxu_surgeon", "TleilaxuSurgeonAgentAbility"),
    ("dissecting_kit", "DissectingKitAgentAbility"),
    ("control_the_spice", "ControlTheSpiceAbility"),
    ("arrakis_revolt", "ArrakisRevoltAbility"),
    ("pivotal_gambit", "PivotalGambitAbility"),
    ("high_priority_travel", "HighPriorityTravelAbility"),
    ("high_priority_travel", "HighPriorityTravelDeployUnitsCustomAbility"),
    ("slig_farmer", "SligFarmerTleilaxuAbility"),
    ("beguiling_pheromones", "BeguilingPheromonesAbility"),
    ("piter_genius_advisor", "PiterGeniusAdvisorAbility"),
    ("stitched_horror", "StitchedHorrorAbility"),
    ("twisted_mentat", "TwistedMentatAbility"),
    ("long_reach", "LongReachAgentAbility"),
    ("tleilaxu_master", "TleilaxuMasterAbility"),
)


@pytest.mark.parametrize(("card", "name"), _EXPANSION_ABILITY_NAMES)
def test_every_mapped_app_ability_is_on_the_cards_archetype(
    card: str, name: str
) -> None:
    found = ae._find(card_entity(f"test:{card}:0"), name)
    assert found is not None, (card, name)
    assert type(found[0]).__name__ == name  # a port, not UnportedAbility
