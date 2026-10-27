"""Content ids are unique within their kind across both base games.

docs/base-game-and-ix-plan.md 4.2 item 7 and 10.1 item 3: the engine
tables, the observation and the entity network's vocabulary are keyed by
id, so an id names one printing. A space or card printed alike in two base
games shares its id (and its definition); one printed differently takes its
own id. Ids repeating across kinds are listed, and lookups name the kind
(the 2026-09-27 case: a board space showed a Contract's picture because
both are ``deliver_supplies``).
"""

from collections import defaultdict
from collections.abc import Callable, Iterable
from itertools import product
from typing import Any

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.bloodlines.sardaukar import SKILLS
from dune_imperium.content.bloodlines.tech import TECH_TILES
from dune_imperium.content.immortality.board import RESEARCH_SPACES
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
from dune_imperium.content.rulesets import RulesetContent, content_for
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance

# Ids that name objects of two kinds, with the kinds. A new one fails this
# test until it is listed here and every lookup of those kinds names its kind.
CROSS_KIND_IDS = {"deliver_supplies": frozenset({"board_space", "contract"})}


def _widest(base_game: BaseGame) -> RulesetConfig:
    """The base game's configuration with every option it allows."""

    for flags in product((True, False), repeat=10):
        names = (
            "choam_module",
            "promo_cards",
            "bloodlines",
            "tech_module",
            "immortality",
            "go_to_11",
            "epic_game",
            "arrakeen_scouts",
            "rise_of_ix",
            "leader_draft",
        )
        try:
            options = dict(zip(names, flags, strict=True))
            return RulesetConfig(base_game=base_game, **options)
        except ValueError:
            continue
    raise AssertionError(f"no configuration of {base_game}")


_KINDS: dict[str, Callable[[RulesetContent], Iterable[tuple[str, Any]]]] = {
    "board_space": lambda c: ((s.space_id, s) for s in c.board_spaces),
    "observation_post": lambda c: ((p.post_id, p) for p in c.observation_posts),
    "conflict": lambda c: ((x.card.card_id, x) for x in c.conflicts),
    "objective": lambda c: ((o.objective_id, o) for o in c.objectives),
    "leader": lambda c: ((x.leader_id, x) for x in c.leaders),
    "imperium": lambda c: (
        (card.card.card_id, card)
        for card in map(imperium_card_for_instance, c.imperium_deck_instance_ids)
    ),
    "intrigue": lambda c: (
        (card.card.card_id, card)
        for card in map(intrigue_card_for_instance, c.intrigue_deck_instance_ids)
    ),
    "reserve": lambda c: ((s.card.card_id, s) for s in c.reserve_stacks),
    "starting": lambda c: (
        (e.card.card_id, e)
        for e in (*c.starting_deck_entries, *c.starting_discard_entries)
    ),
    "contract": lambda c: (
        (contract.card.card_id, contract)
        for contract in map(contract_for_instance, c.contract_instance_ids)
    ),
}
# Expansion kinds not yet chosen through the ruleset content.
_FIXED_KINDS: dict[str, Iterable[tuple[str, Any]]] = {
    "tech": ((t.tech_id, t) for t in TECH_TILES),
    "skill": ((s.skill_id, s) for s in SKILLS),
    "research_space": ((s.space_id, s) for s in RESEARCH_SPACES),
    "tleilaxu": ((c.card.card_id, c) for c in TLEILAXU_CARDS),
}


def _by_kind() -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = defaultdict(dict)
    for base_game in BaseGame:
        content = content_for(_widest(base_game))
        for kind, read in _KINDS.items():
            seen: set[str] = set()
            for content_id, definition in read(content):
                # Instances repeat a card; a definition repeats only as itself.
                if content_id in seen:
                    assert tables[kind][content_id] is definition, (kind, content_id)
                    continue
                seen.add(content_id)
                held = tables[kind].setdefault(content_id, definition)
                # Two base games share an id only for one printing.
                assert held == definition, (kind, content_id, base_game)
    for kind, pairs in _FIXED_KINDS.items():
        for content_id, definition in pairs:
            assert content_id not in tables[kind], (kind, content_id)
            tables[kind][content_id] = definition
    return tables


def test_ids_are_unique_within_each_kind_across_base_games() -> None:
    tables = _by_kind()
    assert {kind for kind, ids in tables.items() if ids} >= {
        "board_space",
        "conflict",
        "leader",
        "imperium",
        "intrigue",
        "reserve",
        "starting",
        "contract",
    }


def test_ids_repeated_across_kinds_are_listed() -> None:
    kinds_of: dict[str, set[str]] = defaultdict(set)
    for kind, ids in _by_kind().items():
        for content_id in ids:
            kinds_of[content_id].add(kind)
    shared = {
        content_id: frozenset(kinds)
        for content_id, kinds in kinds_of.items()
        if len(kinds) > 1
    }
    assert shared == CROSS_KIND_IDS
