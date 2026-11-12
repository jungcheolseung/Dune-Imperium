"""The content packages' import layers (docs/content-core-refactor-plan.md 6).

``content.core`` holds the vocabulary and schemas every set uses, each set
package (``content.uprising``, ``content.imperium`` and the expansions) holds
its own data and imports only ``content.core``, ``content.registry`` builds the
lookups across sets, and ``content.rulesets`` assembles a configuration's
content. Code outside ``content`` reads ``core``, ``registry`` and
``rulesets``; a module that is one set's own mechanic may also read that set's
data, as listed in ``OUTSIDE_SET_IMPORTS`` -- a ratchet: a pair may leave the
list, and a new one fails here until it is justified and added.
"""

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2] / "src" / "dune_imperium"
CONTENT: Final = ROOT / "content"
SETS: Final = frozenset(
    {
        "uprising",
        "imperium",
        "rise_of_ix",
        "bloodlines",
        "immortality",
        "arrakeen_scouts",
    }
)


# Modules outside ``content`` that import a set package directly, at stage 3B.
OUTSIDE_SET_IMPORTS: Final = frozenset(
    {
        "adapters/action_codec.py -> arrakeen_scouts",
        "adapters/action_codec.py -> bloodlines",
        "adapters/action_codec.py -> immortality",
        "adapters/action_codec.py -> rise_of_ix",
        "adapters/action_codec.py -> uprising",
        "adapters/observation_encoding.py -> arrakeen_scouts",
        "adapters/observation_encoding.py -> bloodlines",
        "adapters/observation_encoding.py -> immortality",
        "adapters/observation_encoding.py -> imperium",
        "adapters/observation_encoding.py -> rise_of_ix",
        "adapters/observation_encoding.py -> uprising",
        "agents/app_ai/abilities/bloodlines_cards.py -> uprising",
        "agents/app_ai/abilities/imperium_b.py -> uprising",
        "agents/app_ai/abilities/intrigue.py -> uprising",
        "agents/app_ai/abilities/scouts.py -> arrakeen_scouts",
        "agents/app_ai/abilities/tech.py -> bloodlines",
        "agents/app_ai/catalog.py -> bloodlines",
        "agents/app_ai/context.py -> arrakeen_scouts",
        "agents/app_ai/context.py -> immortality",
        "agents/app_ai/profile/bloodlines.py -> bloodlines",
        "agents/app_ai/profile/economy.py -> uprising",
        "agents/app_ai/profile/influence.py -> uprising",
        "agents/app_ai/profile/scouts.py -> arrakeen_scouts",
        "agents/app_ai/profile/scouts.py -> immortality",
        "agents/app_ai/windows/scouts.py -> arrakeen_scouts",
        "agents/heuristic_agent.py -> immortality",
        "agents/rollout_agent.py -> immortality",
        "agents/rollout_agent.py -> uprising",
        "display/actions.py -> bloodlines",
        "display/actions.py -> uprising",
        "display/bloodlines.py -> bloodlines",
        "display/effect_dsl_text.py -> immortality",
        "display/effect_dsl_text_ko.py -> immortality",
        "display/images.py -> bloodlines",
        "display/images.py -> immortality",
        "display/images.py -> imperium",
        "display/images.py -> uprising",
        "display/scouts.py -> arrakeen_scouts",
        "display/scouts.py -> uprising",
        "display/unavailable.py -> immortality",
        "display/unavailable.py -> uprising",
        "evaluation/problem_set.py -> uprising",
        "rules/ability_executor.py -> bloodlines",
        "rules/acquisition.py -> immortality",
        "rules/acquisition.py -> uprising",
        "rules/agent_box_abilities.py -> immortality",
        "rules/agent_effects.py -> immortality",
        "rules/agent_effects.py -> uprising",
        "rules/agent_turn.py -> uprising",
        "rules/board_effects.py -> uprising",
        "rules/card_trash.py -> uprising",
        "rules/combat.py -> bloodlines",
        "rules/combat.py -> immortality",
        "rules/combat.py -> uprising",
        "rules/conditions.py -> immortality",
        "rules/contract_tiles.py -> bloodlines",
        "rules/effect_interpreter.py -> immortality",
        "rules/effect_interpreter.py -> uprising",
        "rules/endgame.py -> uprising",
        "rules/frames.py -> uprising",
        "rules/immortality.py -> immortality",
        "rules/influence.py -> arrakeen_scouts",
        "rules/influence.py -> uprising",
        "rules/ix_board_spaces.py -> rise_of_ix",
        "rules/leader_abilities.py -> uprising",
        "rules/ornithopter.py -> uprising",
        "rules/phases.py -> uprising",
        "rules/reveal_lines.py -> uprising",
        "rules/reveal_turn.py -> bloodlines",
        "rules/reveal_turn.py -> rise_of_ix",
        "rules/reveal_turn.py -> uprising",
        "rules/sardaukar.py -> bloodlines",
        "rules/scouts.py -> arrakeen_scouts",
        "rules/scouts_auctions.py -> arrakeen_scouts",
        "rules/scouts_effects.py -> arrakeen_scouts",
        "rules/scouts_effects.py -> immortality",
        "rules/scouts_missions.py -> arrakeen_scouts",
        "rules/scouts_modifiers.py -> arrakeen_scouts",
        "rules/scouts_secrets.py -> arrakeen_scouts",
        "rules/setup.py -> bloodlines",
        "rules/setup.py -> immortality",
        "rules/setup.py -> rise_of_ix",
        "rules/setup.py -> uprising",
        "rules/starting_contracts.py -> rise_of_ix",
        "rules/strength.py -> bloodlines",
        "rules/tech.py -> bloodlines",
        "rules/tleilaxu_row.py -> immortality",
        "rules/turn_rows.py -> immortality",
        "rules/unload.py -> uprising",
        "server/catalog.py -> arrakeen_scouts",
        "server/catalog.py -> bloodlines",
        "server/catalog.py -> immortality",
        "server/catalog.py -> imperium",
        "server/catalog.py -> rise_of_ix",
        "server/catalog.py -> uprising",
        "server/session_log.py -> uprising",
        "simulation/coverage.py -> bloodlines",
        "simulation/coverage.py -> immortality",
        "simulation/invariants.py -> bloodlines",
        "simulation/invariants.py -> rise_of_ix",
        "training/entity_features.py -> bloodlines",
        "training/entity_features.py -> immortality",
        "training/entity_features.py -> uprising",
        "training/slots.py -> immortality",
        "training/slots.py -> imperium",
        "training/slots.py -> rise_of_ix",
    }
)

# Modules moved in stage 2 whose re-exports stage 3B removed.
REMOVED_SHIMS: Final = (
    "schema.py",
    "uprising/types.py",
    "uprising/effect_dsl.py",
    "uprising/abilities.py",
    "uprising/personal_cards.py",
)


def _imports(path: Path) -> Iterator[tuple[str, int]]:
    """Every module ``path`` imports, with its line; a ``from`` import also
    names each imported name as a module, as it may be a submodule."""

    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module, node.lineno
            for alias in node.names:
                yield f"{node.module}.{alias.name}", node.lineno
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno


def _content_part(module: str) -> str | None:
    """The ``dune_imperium.content`` part ``module`` names: a set, ``core``,
    ``registry``, ``rulesets``, ``diu`` -- or None outside it."""

    parts = module.split(".")
    if parts[:2] != ["dune_imperium", "content"] or len(parts) < 3:
        return None
    return parts[2]


def _violations(directory: Path, allowed: frozenset[str]) -> list[str]:
    found = []
    for path in sorted(directory.rglob("*.py")):
        for module, line in _imports(path):
            if module.startswith("dune_imperium.") and not any(
                module == prefix or module.startswith(prefix + ".")
                for prefix in allowed
            ):
                found.append(f"{path.relative_to(ROOT)}:{line} imports {module}")
    return found


def test_core_imports_nothing_else_from_the_package() -> None:
    allowed = frozenset({"dune_imperium.content.core"})
    assert _violations(CONTENT / "core", allowed) == []


def test_a_set_imports_only_core_the_config_and_itself() -> None:
    found = []
    for name in sorted(SETS):
        # Since stage 4 (plan 8.3) no set reads another's data: ``TechTile``
        # is core's, each tile carrying its own records.
        allowed = {
            "dune_imperium.config",
            "dune_imperium.content.core",
            f"dune_imperium.content.{name}",
        }
        found += _violations(CONTENT / name, frozenset(allowed))
    assert found == []


def test_the_registry_and_rulesets_read_only_content_and_the_config() -> None:
    allowed = frozenset({"dune_imperium.config", "dune_imperium.content"})
    found = _violations(CONTENT / "registry", allowed)
    for module in ("rulesets.py", "diu.py"):
        for imported, line in _imports(CONTENT / module):
            if imported.startswith("dune_imperium.") and not imported.startswith(
                ("dune_imperium.config", "dune_imperium.content")
            ):
                found.append(f"content/{module}:{line} imports {imported}")
    registry_reads = {
        part
        for path in (CONTENT / "registry").rglob("*.py")
        for module, _ in _imports(path)
        if (part := _content_part(module)) in ("rulesets", "diu")
    }
    assert found == []
    assert registry_reads == set()


def test_outside_content_reaches_a_set_only_through_the_allowlist() -> None:
    pairs = set()
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if relative.parts[0] == "content":
            continue
        for module, _ in _imports(path):
            if (part := _content_part(module)) in SETS:
                pairs.add(f"{relative.as_posix()} -> {part}")
    assert sorted(pairs - OUTSIDE_SET_IMPORTS) == []
    assert sorted(OUTSIDE_SET_IMPORTS - pairs) == [], "remove the pairs gone"


def test_no_stage_two_shim_module_remains() -> None:
    assert [shim for shim in REMOVED_SHIMS if (CONTENT / shim).exists()] == []
