"""Expansion legal-action providers must stop at their ruleset flag.

Each of these providers can only ever return () when its module is off --
the state invariants in ``GameState.__post_init__`` forbid the content that
would make them return anything. They used to prove that the expensive way,
by rebuilding a frame context or a deployment context on every enumeration
of a base game, which the engine does twice per decision. The flag is an
O(1) answer to the same question.

The gates are invisible in play, so the test asserts the gate itself: with
the module off the provider must not reach the helper behind it.
"""

from typing import Never

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.rules import (
    UprisingRulesEngine,
    combat_deployment,
    graft,
    sardaukar,
    tech,
)


def _explode(*args: object, **kwargs: object) -> Never:
    raise AssertionError("the provider looked past its ruleset gate")


def test_expansion_providers_stop_at_the_ruleset_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = UprisingRulesEngine().reset(RulesetConfig(), 1)
    assert not state.config.bloodlines
    assert not state.config.tech_module
    assert not state.config.immortality

    monkeypatch.setattr(sardaukar, "_owned_effect_context", _explode)
    monkeypatch.setattr(sardaukar, "owned_top_frame", _explode)
    monkeypatch.setattr(combat_deployment, "_deployment_context", _explode)
    monkeypatch.setattr(graft, "current_agent_effect_context", _explode)
    monkeypatch.setattr(tech, "_reveal_top", _explode)

    assert sardaukar.legal_sardaukar_commander_actions(state, 0) == ()
    assert sardaukar.legal_skill_trash_actions(state, 0) == ()
    assert combat_deployment.legal_commander_deployments(state, 0) == ()
    assert combat_deployment.legal_commander_withdrawals(state, 0) == ()
    assert graft.legal_graft_switch_actions(state, 0) == ()
    assert tech.legal_tech_reveal_actions(state, 0) == ()


@pytest.mark.parametrize(
    ("config", "call"),
    [
        (
            RulesetConfig(bloodlines=True),
            lambda state: sardaukar.legal_sardaukar_commander_actions(state, 0),
        ),
        (
            RulesetConfig(bloodlines=True),
            lambda state: sardaukar.legal_skill_trash_actions(state, 0),
        ),
        (
            RulesetConfig(bloodlines=True),
            lambda state: combat_deployment.legal_commander_deployments(state, 0),
        ),
        (
            RulesetConfig(bloodlines=True),
            lambda state: combat_deployment.legal_commander_withdrawals(state, 0),
        ),
        (
            RulesetConfig(immortality=True),
            lambda state: graft.legal_graft_switch_actions(state, 0),
        ),
        (
            RulesetConfig(bloodlines=True, tech_module=True),
            lambda state: tech.legal_tech_reveal_actions(state, 0),
        ),
    ],
    ids=[
        "sardaukar_commander",
        "skill_trash",
        "commander_deployments",
        "commander_withdrawals",
        "graft_switch",
        "tech_reveal",
    ],
)
def test_the_gate_opens_when_the_module_is_on(
    config: RulesetConfig,
    call: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the module on, the provider must go past the flag and look."""

    state = UprisingRulesEngine().reset(config, 1)
    monkeypatch.setattr(sardaukar, "_owned_effect_context", _explode)
    monkeypatch.setattr(sardaukar, "owned_top_frame", _explode)
    monkeypatch.setattr(combat_deployment, "_deployment_context", _explode)
    monkeypatch.setattr(graft, "current_agent_effect_context", _explode)
    monkeypatch.setattr(tech, "_reveal_top", _explode)

    with pytest.raises(AssertionError, match="looked past its ruleset gate"):
        call(state)  # type: ignore[operator]
