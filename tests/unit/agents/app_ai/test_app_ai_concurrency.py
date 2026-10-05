"""Concurrent app_ai games decide exactly as they would alone.

The play server runs each request in a threadpool thread, so several games'
app_ai seats decide at the same time. Each seat owns its agent (RNG and
memory), but module-level state is shared by every game in the process. A
save restore asks fresh agents every AI step again and requires the same
answers, so a game must not depend on what another game did before or
alongside it.
"""

import importlib
import inspect
import json
import pkgutil
import subprocess
import sys
import weakref
from collections import deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import cached_property

import pytest

import dune_imperium.agents.app_ai as app_ai_package
from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent, catalog
from dune_imperium.agents.app_ai.profile import influence
from dune_imperium.core.state import GamePhase, canonical_state_hash
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

UI_DEFAULT_OPTIONS = {
    "choam_module": True,
    "leader_draft": True,
    "promo_cards": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "go_to_11": True,
    "epic_game": True,
}

#: (rule options, game seed) of the games played side by side.
GAMES = (
    (RulesetConfig(**UI_DEFAULT_OPTIONS), 3),
    (RulesetConfig(**UI_DEFAULT_OPTIONS, arrakeen_scouts=True), 4),
)

_MUTABLE = (
    list,
    dict,
    set,
    bytearray,
    deque,
    weakref.WeakKeyDictionary,
    weakref.WeakValueDictionary,
    weakref.WeakSet,
)


def _play(config: RulesetConfig, game_seed: int) -> tuple[object, ...]:
    agents = [
        AppAIAgent(seed=100 * game_seed + seat, level=seat % 3) for seat in range(4)
    ]
    result = run_policy_game(UprisingRulesEngine(), config, game_seed, agents)
    assert result.state.phase is GamePhase.FINISHED
    for agent in agents:
        assert not agent.fallbacks
    return (
        tuple(result.replay.steps),
        canonical_state_hash(result.state),
        tuple(agent.memory for agent in agents),
    )


def _clear_module_caches() -> None:
    """Empty the ``functools.cache`` tables so the threads fill them."""

    catalog._space_archetype.cache_clear()
    influence._board_spaces.cache_clear()
    influence._observed_spaces.cache_clear()


@contextmanager
def _switch_often() -> Iterator[None]:
    """Switch threads every 10 microseconds (default: 5 ms), well inside
    one decision (about 1.2 ms)."""

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-5)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


def test_concurrent_games_play_as_they_do_alone() -> None:
    alone = [_play(config, seed) for config, seed in GAMES]

    _clear_module_caches()
    with _switch_often(), ThreadPoolExecutor(max_workers=len(GAMES)) as pool:
        together = list(pool.map(lambda game: _play(*game), GAMES))

    assert together == alone


def _fingerprint(value: object) -> str:
    if isinstance(
        value,
        weakref.WeakKeyDictionary | weakref.WeakValueDictionary | weakref.WeakSet,
    ):
        return f"{type(value).__name__} of {len(value)}"
    return repr(value)


def _module_state() -> dict[str, str]:
    """Every module- and class-level value of the app_ai package that a
    decision could write: mutable containers, and the plain class
    attributes (flags, defaults) of the package's own classes."""

    state: dict[str, str] = {}
    modules = [app_ai_package] + [
        importlib.import_module(info.name)
        for info in pkgutil.walk_packages(
            app_ai_package.__path__, app_ai_package.__name__ + "."
        )
    ]
    for module in modules:
        for name, value in vars(module).items():
            key = f"{module.__name__}.{name}"
            if inspect.isclass(value):
                if value.__module__ != module.__name__:
                    continue
                for attribute, member in vars(value).items():
                    if attribute.startswith("__") or callable(member):
                        continue
                    if isinstance(
                        member, property | staticmethod | classmethod | cached_property
                    ):
                        continue
                    state[f"{key}.{attribute}"] = _fingerprint(member)
            elif isinstance(value, _MUTABLE):
                state[key] = _fingerprint(value)
    return state


def _changed_by_a_game() -> list[str]:
    """The module-state keys one game changes."""

    before = _module_state()
    assert "dune_imperium.agents.app_ai.abilities.base.UNPORTED" in before
    assert len(before) > 100
    _play(*GAMES[1])
    after = _module_state()
    return sorted(
        key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
    )


def test_a_game_leaves_no_module_state_behind() -> None:
    """Play writes nothing a later decision of another game could read.

    The only process-wide tables that fill during play are the
    ``functools.cache`` lookups of static content (pure functions, not
    containers, so not listed here) and ``abilities.UNPORTED``, a
    diagnostics counter that a coverage-complete game leaves untouched.
    A lazy fill happens on first use, which earlier tests in this process
    may already have made, so the game is also played in a fresh process.
    """

    assert _changed_by_a_game() == []
    completed = subprocess.run(
        [sys.executable, __file__],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == []


def test_the_module_state_audit_sees_a_lazy_fill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The audit above catches a module-level table filled during play, as
    ``profile/combat.py``'s Uprising Conflict list once was."""

    from dune_imperium.agents.app_ai.profile import combat

    table: list[str] = []
    monkeypatch.setattr(combat, "_LAZY_PROBE", table, raising=False)
    before = _module_state()
    table.append("filled")

    after = _module_state()
    key = "dune_imperium.agents.app_ai.profile.combat._LAZY_PROBE"
    assert before[key] != after[key]


if __name__ == "__main__":
    # The fresh-process half of test_a_game_leaves_no_module_state_behind.
    print(json.dumps(_changed_by_a_game()))
