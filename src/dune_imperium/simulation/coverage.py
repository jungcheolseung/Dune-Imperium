"""Content-coverage census over one finished, checked game (M7 tooling).

``collect_game_coverage`` walks a finished game's recorded replay and its
accumulated ``event_log`` and buckets what content the game actually touched:
which action IDs were applied, which board spaces (and cost options) hosted
an agent, which cards were played, acquired, or revealed, which Intrigue
cards, Contracts, Conflicts, and Leader events fired, and which chance
decision families and event kinds occurred. ``merge_coverage`` sums two
censuses together (e.g. across every game in a sweep), and ``zero_coverage``
compares a merged census against the content catalogs the engine actually
offers for one ruleset, reporting which catalog entries were never touched.

This module is diagnostic tooling only: it never changes what the engine
does, and a missing or empty census is not itself a bug — it just means the
sampled games never reached that content.
"""

import re
from collections.abc import Iterable
from typing import Final

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.imperium import imperium_deck_instance_ids
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.replay import ReplayStep
from dune_imperium.core.state import GameState

type Census = dict[str, dict[str, int]]

# Per-copy instance IDs look like "imperium:<slug>:<copy>",
# "reserve:<slug>:<copy>", "intrigue:<slug>:<copy>", or
# "player:<seat>:starter:<slug>:<copy>"; every dimension that counts cards
# instead of physical copies normalizes down to the shared "<slug>" identity.
_INSTANCE_PREFIXES: Final = ("imperium:", "reserve:", "intrigue:")
_STARTER_INSTANCE: Final = re.compile(r"^player:\d+:starter:(?P<identity>.+):\d+$")
_INTEGER_TOKEN: Final = re.compile(r":\d+")


def normalize_instance_id(instance_id: str) -> str:
    """Strip a per-copy instance ID down to its shared identity slug."""

    starter_match = _STARTER_INSTANCE.match(instance_id)
    if starter_match is not None:
        return starter_match.group("identity")
    for prefix in _INSTANCE_PREFIXES:
        if instance_id.startswith(prefix):
            rest = instance_id[len(prefix) :]
            identity, separator, _copy = rest.rpartition(":")
            return identity if separator else rest
    return instance_id


def _bump(census: Census, dimension: str, key: str) -> None:
    bucket = census.setdefault(dimension, {})
    bucket[key] = bucket.get(key, 0) + 1


def _int_argument(arguments: dict[str, ActionValue], key: str) -> int:
    value = arguments.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _leader_id_for_event(
    final_state: GameState, payload: dict[str, ActionValue]
) -> str | None:
    player = payload.get("player")
    if isinstance(player, bool) or not isinstance(player, int):
        return None
    if not 0 <= player < len(final_state.players):
        return None
    return final_state.players[player].leader_id


def collect_game_coverage(
    final_state: GameState, steps: Iterable[ReplayStep]
) -> Census:
    """Bucket the content one finished, replayed game actually touched."""

    census: Census = {}

    for step in steps:
        if isinstance(step, ChanceOutcome):
            _bump(census, "chance_kinds", _INTEGER_TOKEN.sub("", step.decision_id))
            continue
        _bump(census, "action_ids", step.action_id)
        if step.action_id != "agent_turn":
            continue
        arguments = dict(step.arguments)
        space_id = arguments.get("space_id")
        card_id = arguments.get("card_id")
        if isinstance(space_id, str):
            cost_option = _int_argument(arguments, "cost_option")
            _bump(census, "agent_placements", f"{space_id}:{cost_option}")
        if isinstance(card_id, str):
            _bump(census, "cards_played", normalize_instance_id(card_id))

    for event in final_state.event_log:
        _bump(census, "event_kinds", event.kind)
        payload = dict(event.payload)

        if event.kind == "card_acquired":
            card_id = payload.get("card_id")
            if isinstance(card_id, str):
                _bump(census, "cards_acquired", normalize_instance_id(card_id))
        elif event.kind == "personal_card_late_revealed":
            # The Reveal-turn immediate reveal of an arriving card is the
            # only other place a specific personal card "plays" itself.
            card_id = payload.get("card_id")
            if isinstance(card_id, str):
                _bump(census, "cards_played", normalize_instance_id(card_id))
        elif event.kind == "intrigue_played":
            card_id = payload.get("card_id")
            if isinstance(card_id, str):
                identity = normalize_instance_id(card_id)
                option = payload.get("option")
                key = (
                    f"{identity}:{option}"
                    if isinstance(option, int) and not isinstance(option, bool)
                    else identity
                )
                _bump(census, "intrigue_played", key)
        elif event.kind in ("contract_taken", "contract_completed"):
            contract_id = payload.get("contract_id")
            if isinstance(contract_id, str):
                _bump(census, "contracts", contract_id)
        elif event.kind == "conflict_revealed":
            conflict_id = payload.get("conflict_id")
            if isinstance(conflict_id, str):
                _bump(census, "conflicts", conflict_id)
        elif event.kind.startswith("leader_") or event.kind == "feyd_token_advanced":
            leader_id = _leader_id_for_event(final_state, payload)
            if leader_id is not None:
                _bump(census, "leader_events", f"{leader_id}:{event.kind}")

    return census


def merge_coverage(a: Census, b: Census) -> Census:
    """Sum two censuses' counts, dimension by dimension and key by key."""

    merged: Census = {dimension: dict(counts) for dimension, counts in a.items()}
    for dimension, counts in b.items():
        bucket = merged.setdefault(dimension, {})
        for key, count in counts.items():
            bucket[key] = bucket.get(key, 0) + count
    return merged


def _agent_placement_catalog() -> frozenset[str]:
    keys: set[str] = set()
    for space in BOARD_SPACES:
        if space.dynamic_cost is None and len(space.cost_options) > 1:
            options: tuple[int, ...] = tuple(range(len(space.cost_options)))
        else:
            options = (0,)
        keys.update(f"{space.space_id}:{option}" for option in options)
    return frozenset(keys)


def zero_coverage(
    census: Census, *, choam_module: bool, promo_cards: bool = False
) -> dict[str, list[str]]:
    """Return, per dimension with a well-defined catalog, the untouched IDs.

    Only dimensions backed by a fixed content catalog are reported: a
    dimension with no catalog (``cards_played``, ``chance_kinds``,
    ``event_kinds``) is skipped rather than guessed at.
    """

    config = RulesetConfig(choam_module=choam_module, promo_cards=promo_cards)
    codec = ActionCodec(config)

    zero: dict[str, list[str]] = {}

    def _report(dimension: str, catalog: Iterable[str]) -> None:
        seen = set(census.get(dimension, {}))
        zero[dimension] = sorted(set(catalog) - seen)

    def _report_by_identity(dimension: str, catalog: Iterable[str]) -> None:
        seen_identities = {key.split(":", 1)[0] for key in census.get(dimension, {})}
        zero[dimension] = sorted(set(catalog) - seen_identities)

    _report(
        "action_ids", {template.action_id for template in codec.catalog}
    )
    _report("agent_placements", _agent_placement_catalog())
    imperium_identities = {
        normalize_instance_id(instance_id)
        for instance_id in imperium_deck_instance_ids(choam_module, promo_cards)
    }
    reserve_identities = {stack.card.card_id for stack in RESERVE_STACKS}
    _report("cards_acquired", imperium_identities | reserve_identities)
    intrigue_identities = {
        normalize_instance_id(instance_id)
        for instance_id in intrigue_deck_instance_ids(choam_module)
    }
    _report_by_identity("intrigue_played", intrigue_identities)
    _report("contracts", set(contract_instance_ids()))
    _report("conflicts", {conflict.card.card_id for conflict in CONFLICTS})
    _report_by_identity(
        "leader_events",
        {leader.leader_id for leader in leaders_for_choam(choam_module)},
    )

    return zero
