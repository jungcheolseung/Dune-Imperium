"""The app AI in a game with a part of Rise of Ix beside the Tech Module
(OQ-165, ``ix_tech_tiles`` and ``ix_leaders``).

``AppContext.ix`` stays "all of Rise of Ix" (its board, Negotiators, Freighter,
dreadnoughts and cards); the Tech tiles' handling reads ``AppContext.ix_tech``
and the four Leaders' (Armand, Ilesa, Yuna, Tessia) ``AppContext.ix_leaders``,
the engine's ``ix_tech_in_play`` and ``ix_leaders_in_play``. Each part's rows
must be answered by the app's own abilities, never by a fallback, on both
boards; the board's rows stay unknown while the board is not in play."""

from collections.abc import Mapping
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.catalog import (
    IX_TECH_ARCHETYPES,
    TECH_ARCHETYPES,
    leader_entity,
    space_entity,
    tech_entity,
    tech_spaces,
)
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.content.rulesets import ix_leader_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.simulation.runner import run_policy_game

BOARDS = (BaseGame.UPRISING, BaseGame.IMPERIUM)


def _config(
    board: BaseGame, *, tiles: bool = False, leaders: bool = False, ix: bool = False
) -> RulesetConfig:
    """Bloodlines and its Tech Module, plus the Ix part asked for."""

    return RulesetConfig(
        base_game=board,
        bloodlines=True,
        tech_module=True,
        promo_cards=True,
        leader_draft=True,
        rise_of_ix=ix,
        ix_tech_tiles=tiles or leaders,
        ix_leaders=leaders,
    )


@cache
def _first_turn(config: RulesetConfig) -> GameState:
    return first_decision("turn", config=config)


def _row(seat: int, action_id: str, **args: object) -> DomainAction:
    return DomainAction(
        action_id=action_id,
        actor=seat,
        arguments=tuple(sorted(args.items())),  # type: ignore[arg-type]
    )


def _run(
    config: RulesetConfig,
    rows: tuple[DomainAction, ...] | None = None,
    *,
    leader: str | None = None,
    resources: Resources | None = None,
    state: GameState | None = None,
) -> DecisionRun:
    """A run over ``rows`` (built with the seat's index) for the seat that
    decides the first ``turn``; ``leader`` replaces that seat's Leader."""

    state = _first_turn(config) if state is None else state
    seat = make_profile(state).ctx.seat
    if leader is not None:
        state = with_player(state, seat, leader_id=leader, leader_face_id=leader)
    if resources is not None:
        state = with_player(state, seat, resources=resources)
    p = make_profile(state, seat)
    return DecisionRun(p.ctx, p, rows or (), p.rng, Memory())


def _rows(run: DecisionRun, *specs: tuple[str, Mapping[str, object]]) -> DecisionRun:
    """``run`` with its legal rows replaced by ``specs`` for its seat."""

    legal = tuple(_row(run.ctx.seat, action_id, **args) for action_id, args in specs)
    return DecisionRun(run.ctx, run.profile, legal, run.rng, Memory())


# ---------------------------------------------------------------------------
# The predicates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("board", BOARDS)
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, (False, False, False)),
        ({"tiles": True}, (False, True, False)),
        ({"leaders": True}, (False, True, True)),
        ({"ix": True}, (True, True, True)),
    ],
)
def test_the_context_reads_each_part_of_rise_of_ix(
    board: BaseGame, kwargs: dict[str, bool], expected: tuple[bool, bool, bool]
) -> None:
    config = _config(board, **kwargs)
    state = ENGINE.reset(config, 1)
    ctx = AppContext(state, 0, ENGINE.observe(state, 0))
    assert (ctx.ix, ctx.ix_tech, ctx.ix_leaders) == expected
    # The engine's own predicates, and the Ix board only with all of Rise of Ix.
    assert (ctx.ix_tech, ctx.ix_leaders) == (
        config.ix_tech_in_play,
        config.ix_leaders_in_play,
    )
    assert ctx.board.ix is expected[0]


# ---------------------------------------------------------------------------
# The ids the Agent-turn window knows
# ---------------------------------------------------------------------------

_TILE_IDS = ("trash_tech", "acquire_foldspace_to_deck_top")
_LEADER_IDS = (
    "acquire_leader_reserve",
    "lose_leader_influence",
    "discard_snooper_card",
)
#: Rows of the Ix board, its cards and the two Leaders who need its
#: Negotiators and Freighter: unknown without all of Rise of Ix.
_BOARD_IDS = (
    "advance_board_freighter",
    "place_board_negotiator",
    "acquire_board_tech",
    "deploy_dreadnoughts",
    "acquire_agent_card_tech",
    "pay_agent_card_spice_for_solari",
    "place_leader_negotiator",
    "acquire_leader_tech",
)


def _unmapped(config: RulesetConfig, action_id: str) -> list[str]:
    run = _rows(_run(config), (action_id, {}))
    t = agent_effects._turn(run)
    agent_effects._unknown_ids(t)
    return t.unmapped


@pytest.mark.parametrize("board", BOARDS)
def test_each_part_knows_only_its_own_rows(board: BaseGame) -> None:
    base = _config(board)
    tiles = _config(board, tiles=True)
    leaders = _config(board, leaders=True)
    full = _config(board, ix=True)
    for action_id in _TILE_IDS:
        assert _unmapped(base, action_id), action_id
        assert not _unmapped(tiles, action_id), action_id
        assert not _unmapped(leaders, action_id), action_id
        assert not _unmapped(full, action_id), action_id
    for action_id in _LEADER_IDS:
        assert _unmapped(base, action_id), action_id
        assert _unmapped(tiles, action_id), action_id
        assert not _unmapped(leaders, action_id), action_id
        assert not _unmapped(full, action_id), action_id
    for action_id in _BOARD_IDS:
        assert _unmapped(base, action_id), action_id
        assert _unmapped(tiles, action_id), action_id
        assert _unmapped(leaders, action_id), action_id
        assert not _unmapped(full, action_id), action_id


# ---------------------------------------------------------------------------
# Tech tiles (mode T and mode L)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("board", BOARDS)
@pytest.mark.parametrize("leaders", [False, True])
def test_an_ix_tile_trash_and_flip_row_is_answered(
    board: BaseGame, leaders: bool
) -> None:
    config = _config(board, tiles=True, leaders=leaders)
    run = _rows(
        _run(config),
        ("trash_tech", {"tech_id": "spy_satellites"}),
        ("flip_tech", {"tech_id": "holoprojectors"}),
        ("finish_agent_turn", {}),
    )
    t = agent_effects._turn(run)
    agent_effects._collect(t)
    assert t.unmapped == []
    labels = {source.label for source in t.sources}
    assert {"trash spy_satellites", "flip holoprojectors"} <= labels
    assert agent_effects.agent_effects_window(run) in run.legal


@pytest.mark.parametrize("board", BOARDS)
def test_without_the_ix_tiles_their_rows_are_not_answered(board: BaseGame) -> None:
    """Bit-identical with the old games: a Tech Module game without Rise of
    Ix has no such row, so one that arrives falls back."""

    run = _rows(
        _run(_config(board)),
        ("trash_tech", {"tech_id": "spy_satellites"}),
        ("finish_agent_turn", {}),
    )
    assert agent_effects.agent_effects_window(run) is None


@pytest.mark.parametrize("board", BOARDS)
def test_mode_t_values_an_ix_tile_on_the_embassy(board: BaseGame) -> None:
    """The Landsraad visit's Acquire Tech (the Tech Module's path) over an Ix
    tile and two Tech Module tiles: the app's Ix tile data values it, and
    its ``AcquireTechAbility`` buys the best one."""

    config = _config(board, tiles=True)
    state = _first_turn(config)
    rich = Resources(solari=8, spice=8, water=2)
    # Holtzman Engine (Ix) on stack 1, Delivery Bay and Planetary Array
    # (Tech Module) on stacks 2 and 3.
    tops = ("holtzman_engine", "delivery_bay", "planetary_array")
    stacks = tuple(
        (top, *(t for t in stack if t not in tops))
        for top, stack in zip(tops, state.tech_stacks, strict=True)
    )
    state = with_state(state, tech_stacks=stacks)
    run = _run(config, state=state, resources=rich)
    p = run.profile
    ix_tile = tech_entity("holtzman_engine")
    assert ix_tile.short == IX_TECH_ARCHETYPES["holtzman_engine"]
    assert TECH_ARCHETYPES["holtzman_engine"] == ix_tile.short
    assert [tile.ref for tile in p.tech_face_up_tiles()] == list(tops)
    assert [tile.ref for tile in p.tech_acquire_targets(0, False)] == list(tops)
    values = {tid: p.tech_tile_acquire_value(tech_entity(tid)).sum for tid in tops}
    rivals = max(values["delivery_bay"], values["planetary_array"])
    assert values["holtzman_engine"] > rivals
    # Its worth starts from the Ix tile's own ``AcquireValue``.
    assert values["holtzman_engine"] >= ix_tile.float_attr("AcquireValue", 0.0)

    space = tech_spaces(p.ctx.board)[0]
    seat = p.ctx.seat
    run = _rows(run, *(("acquire_tech", {"tech_id": tid}) for tid in tops))
    t = agent_effects._Turn(
        run=run,
        context={},
        card_ref=None,
        card_short=None,
        card=None,
        space_id=space,
        space=space_entity(space, p.ctx.board),
        leader=None,
    )
    agent_effects._tech_acquire(t)
    assert t.unmapped == []
    [source] = [s for s in t.sources if s.label == "Acquire Tech"]
    assert source.evaluate is not None
    value, action = source.evaluate()
    assert value > 0.0
    assert action == _row(seat, "acquire_tech", tech_id="holtzman_engine")


# ---------------------------------------------------------------------------
# Leaders (mode L)
# ---------------------------------------------------------------------------


def _leader_window(
    config: RulesetConfig, leader: str, *specs: tuple[str, Mapping[str, object]]
) -> tuple[DecisionRun, DomainAction | None]:
    run = _rows(_run(config, leader=leader), *specs)
    return run, agent_effects.agent_effects_window(run)


@pytest.mark.parametrize("board", BOARDS)
def test_ilesas_guild_contacts_signet_is_answered(board: BaseGame) -> None:
    config = _config(board, leaders=True)
    run, answer = _leader_window(
        config,
        "ilesa_ecaz",
        ("acquire_leader_reserve", {"card_id": "foldspace_card"}),
        ("acquire_leader_reserve", {"card_id": "foldspace_card", "to_deck_top": True}),
        ("decline_leader_signet_payment", {}),
        ("finish_agent_turn", {}),
    )
    assert answer in run.legal
    assert answer is not None and answer.action_id != "finish_agent_turn"


@pytest.mark.parametrize("board", BOARDS)
def test_armands_conscript_signet_is_answered(board: BaseGame) -> None:
    config = _config(board, leaders=True)
    state = _first_turn(config)
    card = state.imperium_row[0]
    run, answer = _leader_window(
        config,
        "archduke_armand_ecaz",
        ("acquire_leader_imperium", {"instance_id": card}),
        ("acquire_leader_reserve", {"card_id": "arrakis_liaison"}),
        ("decline_leader_signet_payment", {}),
        ("finish_agent_turn", {}),
    )
    assert answer in run.legal


@pytest.mark.parametrize("board", BOARDS)
def test_tessias_duplicity_signet_is_answered(board: BaseGame) -> None:
    config = _config(board, leaders=True)
    run, answer = _leader_window(
        config,
        "tessia_vernius",
        ("lose_leader_influence", {"faction": "emperor"}),
        ("lose_leader_influence", {"faction": "fremen"}),
        ("decline_leader_signet_payment", {}),
        ("finish_agent_turn", {}),
    )
    assert answer in run.legal


@pytest.mark.parametrize("board", BOARDS)
def test_the_leaders_signet_rows_fall_back_in_mode_t(board: BaseGame) -> None:
    """No Ix Leader is in play in mode T, so a row of theirs is unknown."""

    run, answer = _leader_window(
        _config(board, tiles=True),
        "ilesa_ecaz",
        ("acquire_leader_reserve", {"card_id": "foldspace_card"}),
        ("finish_agent_turn", {}),
    )
    assert answer is None


@pytest.mark.parametrize("board", BOARDS)
def test_tessias_snooper_reward_is_a_source_with_her_leader(board: BaseGame) -> None:
    from dune_imperium.agents.app_ai.windows import ix

    config = _config(board, leaders=True)
    state = _first_turn(config)
    seat = make_profile(state).ctx.seat
    hand = state.players[seat].hand[0]
    run = _rows(
        _run(config, leader="tessia_vernius"),
        ("discard_snooper_card", {"card_id": hand}),
    )
    t = agent_effects._turn(run)
    agent_effects._collect(t)
    assert t.unmapped == []
    assert "Careful Observation" in {s.label for s in t.sources}
    assert [s.label for s in ix.snooper_sources(run)] == ["Careful Observation"]


@pytest.mark.parametrize("board", BOARDS)
def test_every_leader_the_option_deals_has_a_signet_answer(board: BaseGame) -> None:
    deals = ix_leader_ids(_config(board, leaders=True))
    assert deals == {
        "archduke_armand_ecaz",
        "ilesa_ecaz",
        "princess_yuna_moritani",
        "tessia_vernius",
    }
    for leader in deals:
        assert leader_entity(leader) is not None
        assert leader in agent_effects._IX_SIGNETS


# ---------------------------------------------------------------------------
# The profile's Rise of Ix influence terms
# ---------------------------------------------------------------------------


def _influence(
    config: RulesetConfig, monkeypatch: pytest.MonkeyPatch, **changes: object
) -> Profile:
    # One game for every part, read under each part's config alone.
    state = _first_turn(_config(config.base_game, leaders=True))
    seat = make_profile(state).ctx.seat
    owned = changes.get("tech_ids", ())
    if isinstance(owned, tuple):  # a tile lies in one zone only
        stacks = tuple(tuple(t for t in s if t not in owned) for s in state.tech_stacks)
        state = with_state(state, tech_stacks=stacks)
    state = with_state(state, config=config)
    state = with_player(state, seat, **changes)
    p = make_profile(state, seat)
    monkeypatch.setattr(p, "is_climax", lambda: False)
    return p


@pytest.mark.parametrize("board", BOARDS)
def test_memocorders_and_tessia_terms_follow_their_part(
    board: BaseGame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``GetGainInfluenceValue``'s Rise of Ix block: Memocorders needs the
    tiles, Tessia's Snooper bonus the Leaders; the Spacing Guild bonus needs
    all of Rise of Ix."""

    base = _config(board)
    tiles = _config(board, tiles=True)
    leaders = _config(board, leaders=True)
    full = _config(board, ix=True)

    def value(config: RulesetConfig, faction: str, **changes: object) -> float:
        # The Emperor track at 2, so a gain of 1 reaches 3 (Memocorders').
        influence = Influence(emperor=2 if faction == "emperor" else 0)
        p = _influence(config, monkeypatch, influence=influence, **changes)
        return p.gain_influence_value(faction, 1).sum

    # Memocorders owned, on a track at 2 or less reaching 3.
    owned = {"tech_ids": ("memocorders",)}
    plain = value(base, "emperor")
    boosted = value(tiles, "emperor", **owned)
    constants = _influence(tiles, monkeypatch).C
    assert boosted == pytest.approx(
        value(tiles, "emperor") * constants.MemocordersInfluenceMod
    )
    assert value(leaders, "emperor", **owned) == pytest.approx(boosted)
    assert value(full, "emperor", **owned) == pytest.approx(boosted)
    assert value(base, "emperor", **owned) == pytest.approx(plain)
    # The Spacing Guild's bonus is the Ix board's.
    guild = value(base, "spacing_guild")
    assert value(tiles, "spacing_guild") == pytest.approx(guild)
    assert value(leaders, "spacing_guild") == pytest.approx(guild)
    assert constants.SpacingGuildRiseOfIxBonus > 1.0
    assert value(full, "spacing_guild") > guild
    # Tessia's Snooper token on a track.
    leader = {"leader_id": "tessia_vernius", "leader_face_id": "tessia_vernius"}
    held = {**leader, "snooper_faction_ids": ("emperor",)}
    assert value(leaders, "emperor", **held) == pytest.approx(
        value(leaders, "emperor", **leader) * constants.TessiaVerniusInfluenceMod
    )
    assert value(tiles, "emperor", **held) == pytest.approx(
        value(tiles, "emperor", **leader)
    )


# ---------------------------------------------------------------------------
# Whole games
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("board", BOARDS)
@pytest.mark.parametrize("leaders", [False, True])
def test_whole_games_never_fall_back(board: BaseGame, leaders: bool) -> None:
    config = _config(board, tiles=True, leaders=leaders)
    fallbacks: dict[str, int] = {}
    for seed in (300, 301):
        agents = tuple(AppAIAgent(seed=seed * 10 + s) for s in range(4))
        run_policy_game(ENGINE, config, seed, agents)
        for agent in agents:
            for kind, count in agent.fallbacks.items():
                fallbacks[kind] = fallbacks.get(kind, 0) + count
    assert fallbacks == {}
