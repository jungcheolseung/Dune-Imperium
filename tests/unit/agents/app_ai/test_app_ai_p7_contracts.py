"""Rise of Ix's ten contracts with the CHOAM module on the Uprising board
(P7f-2, [Main p. 16]): the app's ``ContractRoI_n`` archetypes, their
``ROIContractAbility`` classes and the starting-contract pick (OQ-161)."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities.base import abilities_of
from dune_imperium.agents.app_ai.abilities.board import (
    ROIContractAbility,
    ROIHarvest3ContractAbility,
    ROIHarvest4ContractAbility,
)
from dune_imperium.agents.app_ai.catalog import (
    CONTRACT_ARCHETYPES,
    contract_entity,
    space_archetype,
)
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import uprising
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.content.core.cards import ContractDefinition
from dune_imperium.content.core.effects import PlaceNegotiator
from dune_imperium.content.rise_of_ix.contracts import IX_CONTRACTS
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.engine import UprisingRulesEngine

CHOAM_IX = RulesetConfig(choam_module=True, rise_of_ix=True)
BOARD = Board.of(CHOAM_IX)


def _attrs(card_id: str) -> dict[str, object]:
    return dict(ARCHETYPES[CONTRACT_ARCHETYPES[card_id]].attributes)


@pytest.mark.parametrize("contract", IX_CONTRACTS, ids=lambda c: c.card.card_id)
def test_each_ix_contract_is_the_apps_contract_with_its_space_and_reward(
    contract: ContractDefinition,
) -> None:
    card_id = contract.card.card_id
    attrs = _attrs(card_id)
    assert "RiseOfIx" in attrs["SetList"]  # type: ignore[operator]
    referenced = attrs["ReferencedArchetypeIDs"]
    space = contract.board_space
    if space is not None:
        assert attrs["ContractType"] == "Space"
        assert space_archetype(space, BOARD) in referenced  # type: ignore[operator]
    else:
        assert attrs["ContractType"] == "Harvest"
        assert attrs["SpiceCost"] == contract.harvest_spice
    negotiates = any(
        isinstance(effect, PlaceNegotiator) for effect in contract.reward_line.rewards
    )
    assert bool(attrs.get("TechNegotiator", 0)) is negotiates, card_id


def test_the_ix_contracts_run_the_roi_classes() -> None:
    kinds = {
        card_id: {
            type(a)
            for a in abilities_of(contract_entity(f"contract:{card_id}"))
            if isinstance(a, ROIContractAbility)
        }
        for card_id in (c.card.card_id for c in IX_CONTRACTS)
    }
    assert kinds["ix_harvest_3"] == {ROIHarvest3ContractAbility}
    assert kinds["ix_harvest_4"] == {ROIHarvest4ContractAbility}
    others = {k for k in kinds if not k.startswith("ix_harvest")}
    assert all(kinds[k] == {ROIContractAbility} for k in others)


def test_an_roi_contract_values_its_new_contract_and_negotiator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ROIContractAbility::GetResourceValue`` @0x4d5afa0 adds "Gain
    Contract" to the base value, whose Negotiator term ("Contract
    Negotiatiors", ``NegotiateTechValue x TechNegotiator``) only a contract
    with a Negotiator adds."""

    monkeypatch.setattr(Summer, "tracing", True)
    p = make_profile(first_decision("turn", config=CHOAM_IX))
    seat = p.ctx.seat

    def reasons(card_id: str) -> list[str]:
        owner = contract_entity(f"contract:{card_id}", seat)
        summer = ROIContractAbility(owner).resource_value(p)
        assert summer.reasons is not None
        return [reason for _, reason, _ in summer.reasons]

    council = reasons("ix_high_council")
    assert "Gain Contract" in council and "Contract Negotiatiors" in council
    secrets = reasons("ix_secrets")
    assert "Gain Contract" in secrets and "Contract Negotiatiors" not in secrets


def test_the_starting_contract_is_the_best_contract_of_the_two() -> None:
    """``ChooseContractEvaluator::Evaluate`` @0x492d9c0 is
    ``GetBestContract(targets, logAI, forced = true)``."""

    state = first_decision("starting_contract", config=CHOAM_IX)
    engine = UprisingRulesEngine()
    seat = state.decision_stack[-1].decision.owner  # type: ignore[union-attr]
    legal = engine.legal_actions(state, seat)
    assert {a.action_id for a in legal} == {"choose_starting_contract"}
    p = make_profile(state, seat)
    run = DecisionRun(p.ctx, p, legal, p.rng, Memory())
    contracts = [
        contract_entity(str(dict(a.arguments)["instance_id"]), seat) for a in legal
    ]
    best, _value = p.best_contract(contracts, True)
    assert best is not None
    action = uprising.starting_contract(run)
    assert isinstance(action, DomainAction)
    assert dict(action.arguments)["instance_id"] == best.ref


# -- the other P7f-2 windows ---------------------------------------------------


def _run_with(legal: tuple[DomainAction, ...]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=CHOAM_IX))
    return DecisionRun(p.ctx, p, legal, p.rng, Memory())


def _row(action_id: str, actor: int = 0, **arguments: object) -> DomainAction:
    return DomainAction(
        action_id=action_id,
        actor=actor,
        arguments=tuple(sorted(arguments.items())),  # type: ignore[arg-type]
    )


def test_panopticon_s_endgame_rows_are_taken_in_the_engine_s_order() -> None:
    """Panopticon's Endgame Influence in a Rise of Ix game (OQ-153): no app
    class, its gain automatic, so the rows go in the order offered."""

    from dune_imperium.agents.app_ai.windows import ix

    rows = (
        _row("resolve_effect_influence", faction="emperor"),
        _row("resolve_effect_influence", faction="fremen"),
    )
    assert ix.effect_influence_window(_run_with(rows)) is rows[0]
    other = (*rows, _row("finish_agent_turn"))
    assert ix.effect_influence_window(_run_with(other)) is None


def test_an_acquire_box_bought_outside_the_turn_takes_its_icons() -> None:
    """Full-Scale Assault bought at a Scouts market (P7f-2, OQ-141): the
    app's ``AcquireAbility`` commissions its "may" Dreadnought without
    asking; the decline is taken only when it is all that is left."""

    from dune_imperium.agents.app_ai.windows import ix

    take = _row(
        "resolve_acquire_icon",
        acquired_card_id="full_scale_assault",
        effect="dreadnought",
    )
    decline = _row(
        "decline_acquire_icon",
        acquired_card_id="full_scale_assault",
        effect="dreadnought",
    )
    assert ix.acquire_icons_window(_run_with((decline, take))) is take
    assert ix.acquire_icons_window(_run_with((decline,))) is decline


def test_rapid_engineering_asked_again_while_it_values_the_tiles_is_not_bad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sonic Snoopers values each Intrigue in hand by its ``IsBadIntrigue``,
    and Rapid Engineering's check values the Tech tiles (Sonic Snoopers
    among them): the inner ask is "not bad" (docs/app-ai-plan.md 14.3;
    census seed 2017 of Uprising + Ix + Bloodlines + Tech recursed)."""

    from dune_imperium.agents.app_ai.abilities.bloodlines_cards import (
        RapidEngineeringAbility,
    )
    from dune_imperium.agents.app_ai.catalog import intrigue_entity
    from dune_imperium.agents.app_ai.profile import Profile

    p = make_profile(first_decision("turn", config=CHOAM_IX))
    card = intrigue_entity("intrigue:rapid_engineering:0", p.ctx.seat)
    ability = RapidEngineeringAbility(card)
    inner: list[bool] = []

    def tile_to_acquire(self: Profile, discount: int, solari: bool) -> None:
        inner.append(ability.is_bad_intrigue(self))  # the loop asks again
        return None

    monkeypatch.setattr(Profile, "tech_tile_to_acquire", tile_to_acquire)
    ability.is_bad_intrigue(p)
    assert inner == [False]
    assert p.rapid_engineering_checking is False
