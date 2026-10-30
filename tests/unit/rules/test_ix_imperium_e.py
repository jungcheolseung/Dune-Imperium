"""Rise of Ix Imperium batch E: Bounty Hunter, Web of Power and Ixian Engineer.

Steam app attribute table, per-card UI pieces and English localization
(4.1.2.1808, dad97e20); rules: rise-of-ix.md 7 ("Agent의 옆얼굴이 든 Agent
아이콘은 그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게
한다. 자기 Agent가 이미 있는 칸에는 못 보낸다." [Rise of Ix p. 7]),
player-turns.md [Main p. 9] [FAQ p. 3]. Every offered row round-trips through
``ActionCodec``.
"""

from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.adapters.action_codec import ActionTemplate
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.agent_abilities import AGENT_BOX_ABILITIES
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireTech,
    AtSpaceWithEnemyAgent,
    GainVictoryPoints,
    InfluenceAtLeast,
    TechTilesAtLeast,
    TrashCard,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.reveal_choice_abilities import (
    REVEAL_CHOICE_ABILITIES,
)
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GamePhase,
    GameState,
    Influence,
    Resources,
)
from dune_imperium.display.cards import personal_card_text, personal_card_text_ko
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    enemy_agent_on_space,
    executable_placements,
)

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
_BOX = PersonalCardAgentEffect
_REVEAL = PersonalCardRevealChoiceEffect


@cache
def _codec(config: RulesetConfig) -> ActionCodec:
    return ActionCodec(config)


class _Engine(UprisingRulesEngine):
    """Check every offered row, including the intermediate card/space/effect
    choices consumed by apply_whole."""

    def legal_actions(self, state: GameState, player: int) -> tuple[DomainAction, ...]:
        rows = super().legal_actions(state, player)
        codec = _codec(state.config)
        for row in rows:
            assert codec.decode(codec.encode(row), player) == row
        return rows


def _start() -> tuple[_Engine, GameState]:
    engine = _Engine(leader_ids=LEADERS)
    state = engine.reset(CONFIG, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    assert state.phase is GamePhase.PLAYER_TURNS
    return engine, state


def _clean(state: GameState, named: set[str]) -> GameState:
    """``state`` without the named cards in any seat's zones, the Imperium deck
    and Row (seeded decks may hold the card a test then puts in a hand)."""

    return replace(
        state,
        players=tuple(
            replace(
                player,
                deck=tuple(c for c in player.deck if c not in named),
                hand=tuple(c for c in player.hand if c not in named),
                discard_pile=tuple(c for c in player.discard_pile if c not in named),
                in_play=tuple(c for c in player.in_play if c not in named),
            )
            for player in state.players
        ),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _seat(state: GameState, seat: int = 0, **changes: object) -> GameState:
    hand = changes.get("hand")
    if isinstance(hand, tuple):
        named = {card for card in hand if card not in state.players[seat].hand}
        state = _clean(state, named)
    players = list(state.players)
    owner = players[seat]
    if "agent_locations" in changes:
        locations = changes["agent_locations"]
        assert isinstance(locations, tuple)
        changes["agents_available"] = 2 - len(locations)
    if "troops_conflict" in changes or "troops_garrison" in changes:
        # The supply makes up the 12 troops a seat always accounts for.
        garrison = changes.get("troops_garrison", owner.troops_garrison)
        conflict = changes.get("troops_conflict", owner.troops_conflict)
        assert isinstance(garrison, int) and isinstance(conflict, int)
        changes["troops_supply"] = (
            12
            - garrison
            - conflict
            - owner.memories
            - owner.specimens
            - owner.troops_parked
            - owner.negotiators
        )
    players[seat] = replace(owner, **changes)  # type: ignore[arg-type]
    return replace(state, players=tuple(players))


def _rows(engine: _Engine, state: GameState) -> tuple[DomainAction, ...]:
    engine.legal_actions(state, 0)
    return engine.whole_actions(state, 0)


def _ids(engine: _Engine, state: GameState) -> list[str]:
    return [row.action_id for row in _rows(engine, state)]


def _do(engine: _Engine, state: GameState, action_id: str, **args: object) -> GameState:
    row = next(
        row
        for row in _rows(engine, state)
        if row.action_id == action_id
        and all(dict(row.arguments).get(key) == value for key, value in args.items())
    )
    result = apply_whole(engine, state, row).state
    engine.legal_actions(result, 0)
    return result


def _spaces(state: GameState, card_id: str) -> set[str]:
    return {
        str(dict(row.arguments)["space_id"])
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card_id
    }


def _send(engine: _Engine, state: GameState, card_id: str, space_id: str) -> GameState:
    """``card_id`` (already in hand) sent to ``space_id``, its box pending."""

    placement = next(
        row
        for row in executable_placements(state, 0)
        if dict(row.arguments)["card_id"] == card_id
        and dict(row.arguments)["space_id"] == space_id
    )
    result = apply_placement(engine, state, placement).state
    engine.legal_actions(result, 0)
    return result


def _finish(engine: _Engine, state: GameState) -> GameState:
    """The Agent turn closed with every board effect settled and every
    optional icon left unused (an unused optional effect lapses at the turn's
    end, OQ-095 (2))."""

    while True:
        ids = _ids(engine, state)
        step = next(
            (
                action_id
                for action_id in ("resolve_board_effect", "resolve_faction_influence")
                if action_id in ids
            ),
            None,
        )
        if step is None:
            return _do(engine, state, "finish_agent_turn")
        state = _do(engine, state, step)


# --- Bounty Hunter --------------------------------------------------------------

HUNTER = "imperium:bounty_hunter:0"
_HUNTER_BOX = _BOX.GAIN_TWO_SOLARI_IF_ENEMY_AGENT_ON_SPACE


def _hunter(
    engine: _Engine,
    state: GameState,
    space: str,
    *enemies: tuple[int, tuple[str, ...]],
    **changes: object,
) -> GameState:
    """Bounty Hunter sent to ``space`` while each ``(seat, spaces)`` pair has
    its Agents there; its box is pending when it is judged to be."""

    for seat, locations in enemies:
        state = _seat(state, seat, agent_locations=locations)
    state = _seat(state, 0, hand=(HUNTER,), **changes)
    return _send(engine, state, HUNTER, space)


def test_bounty_hunter_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "If used to send an Agent to a board space with an enemy Agent:
    [2 Solari]" and Reveal 1 Persuasion, 1 sword [Steam app screen pieces and
    text].

    App table: cost 1, one copy, no Faction, the City icon (also its
    Infiltration icon, ``InfiltrationIconList``), Reveal 1 Persuasion and
    1 sword.
    """
    entry = IMPERIUM_CARDS_BY_ID["bounty_hunter"]
    assert (entry.copies, entry.acquisition_cost) == (1, 1)
    assert entry.factions == ()
    assert entry.agent_icons == entry.infiltration_icons == (AgentIcon.CITY,)
    assert entry.agent_effect is _HUNTER_BOX
    assert entry.reveal_choice_effects == ()
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 1)
    assert entry.play_data_complete
    assert HUNTER in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert HUNTER not in content_for(config).imperium_deck_instance_ids


def test_bounty_hunter_card_text_prints_the_condition_and_the_gain() -> None:
    """ "If used to send an Agent to a board space with an enemy Agent:
    [2 Solari]" [Steam app screen pieces and text]; Korean words: an opponent
    is "다른 플레이어" (docs/rules/glossary-ko.md)."""
    entry = IMPERIUM_CARDS_BY_ID["bounty_hunter"]
    assert personal_card_text(entry) == [
        "Agent: If used to send an Agent to a board space with an enemy Agent: "
        "Gain 2 solari",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: 다른 플레이어의 {agent}가 있는 장소로 {agent}를 보냈다면: "
        "{solari:2}",
    ]


def test_bounty_hunter_record_is_a_placement_requirement() -> None:
    """The space is fixed by the placement, so the record holds it as the
    box's ``requirement`` (judged when the card is played, OQ-028 (a)), not as
    a line condition judged when the box resolves."""
    ability = AGENT_BOX_ABILITIES[_HUNTER_BOX]
    assert ability.requirement == AtSpaceWithEnemyAgent()
    assert all(section.condition is None for section in ability.sections)


def test_bounty_hunter_infiltrates_a_city_space_and_gains_two_solari() -> None:
    """ "그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게
    한다" [Rise of Ix p. 7]: the printed City Infiltration icon sends the Agent
    to a City space an opponent holds, and the space then "with an enemy
    Agent" pays the 2 Solari."""
    engine, state = _start()
    placed = _hunter(engine, state, "carthag", (1, ("carthag",)))
    assert placed.players[0].agent_locations == ("carthag",)
    assert placed.players[1].agent_locations == ("carthag",)
    assert "resolve_agent_card_effect" in _ids(engine, placed)
    solari = placed.players[0].resources.solari
    paid = _do(engine, placed, "resolve_agent_card_effect")
    assert paid.players[0].resources.solari == solari + 2
    assert "resolve_agent_card_effect" not in _ids(engine, paid)


def test_bounty_hunter_pays_once_for_several_enemy_agents() -> None:
    """ "상대 Agent(여럿이어도)" [Rise of Ix p. 7]: the box prints one 2 Solari,
    however many enemy Agents the space holds."""
    engine, state = _start()
    placed = _hunter(
        engine,
        state,
        "carthag",
        (1, ("carthag",)),
        (2, ("carthag",)),
        (3, ("carthag",)),
    )
    solari = placed.players[0].resources.solari
    paid = _do(engine, placed, "resolve_agent_card_effect")
    assert paid.players[0].resources.solari == solari + 2
    assert "resolve_agent_card_effect" not in _ids(engine, paid)


@pytest.mark.parametrize("space", ["arrakeen", "carthag"])
def test_bounty_hunter_pays_nothing_on_an_empty_space(space: str) -> None:
    """ "If used to send an Agent to a board space with an enemy Agent": an
    ordinary placement on an empty space ("잠입은 선택이다(빈 칸에 보통처럼
    보내도 된다)" [FAQ p. 2]) opens no box, so no row waits and the turn's end
    gives nothing."""
    engine, state = _start()
    enemy = _seat(state, 1, agent_locations=("wealth",))
    placed = _hunter(engine, enemy, space)
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    solari = placed.players[0].resources.solari
    assert not dict(placed.decision_stack[-1].context)["pending_agent_effect"]
    assert placed.players[0].resources.solari == solari


def test_bounty_hunter_ignores_an_enemy_agent_on_another_space() -> None:
    """The condition is about "a board space" the Agent is sent to: an enemy
    Agent on a different space does not open the box."""
    engine, state = _start()
    placed = _hunter(engine, state, "arrakeen", (1, ("carthag",)), (2, ("wealth",)))
    assert "resolve_agent_card_effect" not in _ids(engine, placed)
    assert not dict(placed.decision_stack[-1].context)["pending_agent_effect"]


def test_bounty_hunter_own_agent_still_blocks_the_space() -> None:
    """ "자기 Agent가 이미 있는 칸에는 못 보낸다." [Rise of Ix p. 7]: an own
    Agent there blocks the space, an enemy Agent beside it or not."""
    engine, state = _start()
    mine = _seat(state, 0, agent_locations=("carthag",))
    both = _seat(mine, 1, agent_locations=("carthag",))
    for held in (mine, both):
        held = _seat(held, 0, hand=(HUNTER,))
        assert "carthag" not in _spaces(held, HUNTER)
        assert "arrakeen" in _spaces(held, HUNTER)


def test_bounty_hunter_judges_the_space_the_agent_goes_to() -> None:
    """``enemy_agent_on_space``: an opponent's Agent on that space, whoever
    owns it, and never the sender's own."""
    _, state = _start()
    state = _seat(state, 0, agent_locations=("arrakeen",))
    state = _seat(state, 2, agent_locations=("carthag",))
    assert enemy_agent_on_space(state, 0, "carthag")
    assert not enemy_agent_on_space(state, 0, "arrakeen")
    assert not enemy_agent_on_space(state, 0, "wealth")
    assert enemy_agent_on_space(state, 1, "arrakeen")


def test_bounty_hunter_reveals_one_persuasion_and_a_sword() -> None:
    """App table: Reveal 1 Persuasion and 1 sword; its box is Agent-only. A
    sword counts with a troop in the Conflict ("troop 2, sword 1; Conflict에
    troop이 하나도 없으면 0" [DI p. 11])."""
    engine, state = _start()
    state = _seat(state, hand=(HUNTER,), troops_conflict=1, resources=Resources())
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (1, 1)
    assert revealed.players[0].combat_strength == 2 + 1
    assert revealed.players[0].resources.solari == 0


# --- Web of Power ---------------------------------------------------------------

WEB = "imperium:web_of_power:0"
_WEB_BOX = _BOX.GAIN_BY_EMPEROR_SPACING_GUILD_AND_FREMEN_INFLUENCE_TWO
# Each printed line: the icon it resolves as, its Faction, and what it gives.
_WEB_LINES = (
    ("solari", Faction.EMPEROR),
    ("cards", Faction.SPACING_GUILD),
    ("water", Faction.FREMEN),
)


def _web(engine: _Engine, state: GameState, **changes: object) -> GameState:
    """Web of Power sent to the Secrets space (its Bene Gesserit icon), its
    icons pending."""

    state = _seat(state, 0, hand=(WEB,), **changes)
    return _send(engine, state, WEB, "secrets")


def _icon_rows(engine: _Engine, state: GameState) -> set[object]:
    return {
        dict(row.arguments).get("effect")
        for row in _rows(engine, state)
        if row.action_id == "resolve_agent_card_effect"
    }


def _gain(state: GameState, icon: str) -> int:
    owner = state.players[0]
    return {
        "solari": owner.resources.solari,
        "cards": len(owner.hand),
        "water": owner.resources.water,
    }[icon]


def test_web_of_power_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "Choose a Faction to gain 1 Influence with" on the Reveal and three
    "2 Influence" lines on the Agent box [Steam app screen pieces and text].

    App table: cost 4, one copy, Bene Gesserit, the Bene Gesserit icon (also
    its Infiltration icon), Reveal 1 Persuasion.
    """
    entry = IMPERIUM_CARDS_BY_ID["web_of_power"]
    assert (entry.copies, entry.acquisition_cost) == (1, 4)
    assert entry.factions == (Faction.BENE_GESSERIT,)
    assert entry.agent_icons == (AgentIcon.BENE_GESSERIT,)
    assert entry.infiltration_icons == (AgentIcon.BENE_GESSERIT,)
    assert entry.agent_effect is _WEB_BOX
    assert entry.reveal_choice_effects == (_REVEAL.GAIN_CHOSEN_INFLUENCE,)
    assert (entry.reveal_persuasion, entry.reveal_strength) == (1, 0)
    assert entry.play_data_complete
    assert WEB in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert WEB not in content_for(config).imperium_deck_instance_ids


def test_web_of_power_card_text_prints_the_three_lines_and_the_wild_icon() -> None:
    """ "[Emperor] 2 Influence: [2 Solari]", "[Spacing Guild] 2 Influence:
    [draw 1]", "[Fremen] 2 Influence: [1 water]" and the Reveal's wild
    Influence icon [Steam app screen pieces and text]."""
    entry = IMPERIUM_CARDS_BY_ID["web_of_power"]
    assert personal_card_text(entry) == [
        "Agent: If you have 2 or more Emperor Influence: Gain 2 solari, "
        "If you have 2 or more Spacing Guild Influence: Draw 1 card, "
        "If you have 2 or more Fremen Influence: Gain 1 water",
        "Reveal: Gain 1 Influence with a chosen Faction",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {influence_emperor} 2 이상이면: {solari:2}, "
        "{influence_spacing_guild} 2 이상이면: {draw:1}, "
        "{influence_fremen} 2 이상이면: {water:1}",
        "공개 칸: {influence_any:1} 선택",
    ]


def test_web_of_power_record_holds_three_influence_thresholds() -> None:
    """The three lines are Influence thresholds over their own icon each,
    judged when the icon resolves (OQ-027, OQ-028): none is a placement
    requirement."""
    ability = AGENT_BOX_ABILITIES[_WEB_BOX]
    assert ability.requirement is None
    assert ability.icons == ("solari", "cards", "water")
    assert [section.condition for section in ability.sections] == [
        InfluenceAtLeast(Faction.EMPEROR, 2),
        InfluenceAtLeast(Faction.SPACING_GUILD, 2),
        InfluenceAtLeast(Faction.FREMEN, 2),
    ]


def test_web_of_power_goes_to_a_bene_gesserit_space_an_opponent_holds() -> None:
    """The Bene Gesserit icon is also its Infiltration icon: an opponent's
    Agent there is ignored ("그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시"
    [Rise of Ix p. 7])."""
    engine, state = _start()
    held = _seat(state, 1, agent_locations=("secrets",))
    held = _seat(held, 0, hand=(WEB,))
    assert "secrets" in _spaces(held, WEB)
    placed = _send(engine, held, WEB, "secrets")
    assert placed.players[0].agent_locations == ("secrets",)


@pytest.mark.parametrize(("icon", "faction"), _WEB_LINES)
def test_web_of_power_icon_needs_two_influence_with_its_own_faction(
    icon: str, faction: Faction
) -> None:
    """ "[<Faction>] 2 Influence:" opens only its own icon: two Influence with
    that Faction, none with the other two, gives exactly that icon's gain."""
    engine, state = _start()
    placed = _web(engine, state, influence=Influence(**{faction.value: 2}))
    assert _icon_rows(engine, placed) == {icon}
    before = _gain(placed, icon)
    taken = _do(engine, placed, "resolve_agent_card_effect", effect=icon)
    assert _gain(taken, icon) == before + {"solari": 2, "cards": 1, "water": 1}[icon]
    assert icon not in _icon_rows(engine, taken)


@pytest.mark.parametrize(("icon", "faction"), _WEB_LINES)
def test_web_of_power_icon_waits_below_two_influence(
    icon: str, faction: Faction
) -> None:
    """One Influence is below the printed 2 (and the Bene Gesserit Influence
    the card is of counts for none of the lines), so no icon is offered and
    the turn can end with nothing gained."""
    engine, state = _start()
    placed = _web(
        engine,
        state,
        influence=Influence(**{faction.value: 1}, bene_gesserit=4),
    )
    assert not _icon_rows(engine, placed)
    unmet = placed.players[0]
    done = _finish(engine, placed).players[0]
    assert done.resources.solari == unmet.resources.solari
    assert done.resources.water == unmet.resources.water
    assert len(done.hand) == len(unmet.hand)


def test_web_of_power_three_icons_resolve_one_step_each_in_any_order() -> None:
    """All three thresholds met: three rows, taken in the owner's order, each
    once ("each printed icon its own freely ordered effect", OQ-027)."""
    engine, state = _start()
    placed = _web(
        engine,
        state,
        influence=Influence(emperor=2, spacing_guild=3, fremen=2),
    )
    assert _icon_rows(engine, placed) == {"solari", "cards", "water"}
    before = placed.players[0]
    drawn = _do(engine, placed, "resolve_agent_card_effect", effect="cards")
    assert _icon_rows(engine, drawn) == {"solari", "water"}
    watered = _do(engine, drawn, "resolve_agent_card_effect", effect="water")
    paid = _do(engine, watered, "resolve_agent_card_effect", effect="solari")
    assert not _icon_rows(engine, paid)
    after = paid.players[0]
    assert len(after.hand) == len(before.hand) + 1
    assert after.resources.water == before.resources.water + 1
    assert after.resources.solari == before.resources.solari + 2


def test_web_of_power_judges_each_icon_when_it_resolves() -> None:
    """ "judged when it resolves, in the owner's order [Main pp. 7, 9]"
    (OQ-028): a threshold reached later in the turn opens its icon, and one
    lost closes it."""
    engine, state = _start()
    placed = _web(engine, state, influence=Influence(emperor=1))
    assert not _icon_rows(engine, placed)
    risen = _seat(placed, 0, influence=Influence(emperor=2, fremen=2))
    assert _icon_rows(engine, risen) == {"solari", "water"}
    fallen = _seat(risen, 0, influence=Influence(emperor=2, fremen=1))
    assert _icon_rows(engine, fallen) == {"solari"}


def test_web_of_power_reveals_one_persuasion_and_a_wild_influence() -> None:
    """App table: Reveal 1 Persuasion; the wild Influence icon is a mandatory
    choice of any Faction ("Choose a Faction to gain 1 Influence with"), one
    row per Faction, named by the card, and finishing the Reveal waits for
    it."""
    engine, state = _start()
    state = _seat(state, hand=(WEB,), influence=Influence(bene_gesserit=1))
    revealed = _do(engine, state, "reveal_turn")
    context = dict(revealed.decision_stack[-1].context)
    assert context["persuasion"] == 1
    rows = [
        row
        for row in _rows(engine, revealed)
        if row.action_id == "gain_reveal_influence"
    ]
    assert {
        (dict(row.arguments)["faction"], dict(row.arguments)["source"]) for row in rows
    } == {(faction.value, "web_of_power") for faction in Faction}
    assert "finish_reveal" not in _ids(engine, revealed)
    chosen = _do(
        engine,
        revealed,
        "gain_reveal_influence",
        faction="fremen",
        source="web_of_power",
    )
    owner = chosen.players[0]
    assert (owner.influence.fremen, owner.influence.bene_gesserit) == (1, 1)
    assert "gain_reveal_influence" not in _ids(engine, chosen)
    assert "finish_reveal" in _ids(engine, chosen)


def test_web_of_power_never_offers_a_faction_at_the_top_of_its_track() -> None:
    """A gain on a cube at the top of its track is lost (OQ-060), so that
    Faction is not offered; with every cube there the icon offers nothing and
    the Reveal can end."""
    engine, state = _start()
    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=2)
    revealed = _do(engine, _seat(state, hand=(WEB,), influence=top), "reveal_turn")
    assert {
        dict(row.arguments)["faction"]
        for row in _rows(engine, revealed)
        if row.action_id == "gain_reveal_influence"
    } == {"fremen"}
    full = _do(
        engine,
        _seat(
            state,
            hand=(WEB,),
            influence=Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
        ),
        "reveal_turn",
    )
    assert "gain_reveal_influence" not in _ids(engine, full)
    assert "finish_reveal" in _ids(engine, full)


# --- Ixian Engineer -------------------------------------------------------------

ENGINEER = "imperium:ixian_engineer:0"
ENGINEER_TWIN = "imperium:ixian_engineer:1"
_ENGINEER_REVEAL = _REVEAL.MAY_TRASH_SELF_FOR_VICTORY_POINT_IF_THREE_TECH_TILES
# Costs: Detonation Devices 3, Artillery 1, Chaumurky 4 | Holtzman Engine 6,
# Invasion Ships 5, Memocorders 2 | Restricted Ordnance 4, Minimic Film 2,
# Flagship 8. The tops are Detonation Devices, Holtzman Engine and Restricted
# Ordnance.
STACKS = (
    ("detonation_devices", "artillery", "chaumurky"),
    ("holtzman_engine", "invasion_ships", "memocorders"),
    ("restricted_ordnance", "minimic_film", "flagship"),
)
# Three tiles the seat may own (the Reveal's condition), none of which adds to
# the Reveal turn (Memocorders and Chaumurky count at the game's end, Windtraps
# when a Conflict is won) and none on the stacks above.
OWNED = ("memocorders", "chaumurky", "windtraps")


def _engineer(
    engine: _Engine, state: GameState, spice: int, **changes: object
) -> GameState:
    """Ixian Engineer sent to Smuggling (its Spice Trade icon; the space gives
    1 Solari and a Freighter icon, no spice) with ``spice`` and the Ix stacks
    laid, its Acquire Tech icon pending."""

    state = replace(state, tech_stacks=STACKS)
    state = _seat(
        state, 0, hand=(ENGINEER,), resources=Resources(spice=spice), **changes
    )
    return _send(engine, state, ENGINEER, "smuggling")


def _tiles(engine: _Engine, state: GameState) -> set[object]:
    return {
        dict(row.arguments).get("tech_id")
        for row in _rows(engine, state)
        if row.action_id == "acquire_tech"
    }


def test_ixian_engineer_matches_app_attributes_and_only_joins_the_ix_deck() -> None:
    """ "Acquire Tech" on the Agent box and "If you have three or more Techs:
    Trash this card -> 1 Victory Point" on the Reveal [Steam app screen pieces
    and text].

    App table: cost 5, two copies, no Faction, the Spice Trade icon, no
    Infiltration icon, no fixed Reveal values.
    """
    entry = IMPERIUM_CARDS_BY_ID["ixian_engineer"]
    assert (entry.copies, entry.acquisition_cost) == (2, 5)
    assert entry.factions == ()
    assert entry.agent_icons == (AgentIcon.SPICE_TRADE,)
    assert entry.infiltration_icons == ()
    assert entry.agent_effect is _BOX.MAY_ACQUIRE_TECH
    assert entry.reveal_choice_effects == (_ENGINEER_REVEAL,)
    assert (entry.reveal_persuasion, entry.reveal_strength) == (0, 0)
    assert entry.play_data_complete
    for instance in (ENGINEER, ENGINEER_TWIN):
        assert instance in content_for(CONFIG).imperium_deck_instance_ids
    for config in (
        replace(CONFIG, rise_of_ix=False),
        RulesetConfig(),
        RulesetConfig(rise_of_ix=True),
    ):
        assert ENGINEER not in content_for(config).imperium_deck_instance_ids


def test_ixian_engineer_card_text_prints_the_icon_and_the_arrow() -> None:
    """The Acquire Tech icon ("may" [Rise of Ix p. 4]) and the Reveal's "Have
    3+ Tech tiles: Trash this -> VP" [Steam app text]."""
    entry = IMPERIUM_CARDS_BY_ID["ixian_engineer"]
    assert personal_card_text(entry) == [
        "Agent: You may acquire a Tech tile",
        "Reveal: If you have 3 or more Tech tiles: Trash this card → Gain 1 VP",
    ]
    assert personal_card_text_ko(entry) == [
        "에이전트 칸: {tech_tile} {acquire} 가능",
        "공개 칸: {tech_tile} 3 이상이면: 이 카드 {trash} {arrow_right} "
        "{victory_point:1}",
    ]


def test_ixian_engineer_records_state_the_tech_discount_and_the_arrow() -> None:
    """The icon prints no Tech Discount sprite, so its discount is stated as 0
    (the plain icon of the Dreadnought space); the Reveal is CHOAM Demands'
    shape, an optional arrow paying the card's own trash for a Victory
    Point behind three Tech tiles."""
    ability = AGENT_BOX_ABILITIES[_BOX.MAY_ACQUIRE_TECH]
    assert ability.requirement is None
    assert ability.icons == ("tech",)
    (line,) = ability.sections
    assert line.rewards == (AcquireTech(discount=0),)
    reveal = REVEAL_CHOICE_ABILITIES[_ENGINEER_REVEAL]
    (arrow,) = reveal.sections
    assert arrow.costs == (TrashCard(this_card=True),)
    assert arrow.rewards == (GainVictoryPoints(1),)
    assert arrow.condition == TechTilesAtLeast(3)


def test_ixian_engineer_goes_to_a_spice_trade_space_only() -> None:
    """The Spice Trade icon (app attribute table)."""
    _, state = _start()
    state = _seat(state, hand=(ENGINEER,))
    spaces = _spaces(state, ENGINEER)
    assert {"imperial_basin", "smuggling"} <= spaces
    assert not spaces & {"arrakeen", "carthag", "wealth", "stillsuits", "mentat"}


def test_ixian_engineer_acquires_a_tile_at_no_discount() -> None:
    """The plain Acquire Tech icon (rise-of-ix.md 4: "아이콘마다 ... 하나를 얻을
    수 있다", Tech Discount only where the icon prints one): the window offers
    exactly the tiles the seat can pay full price for, the refusal beside
    them, and the purchase takes its spice and the tile."""
    engine, state = _start()
    placed = _engineer(engine, state, 4)
    assert "acquire_agent_card_tech" in _ids(engine, placed)
    opened = _do(engine, placed, "acquire_agent_card_tech")
    assert _tiles(engine, opened) == {"detonation_devices", "restricted_ordnance"}
    assert "decline_tech" in _ids(engine, opened)
    bought = _do(engine, opened, "acquire_tech", tech_id="restricted_ordnance")
    owner = bought.players[0]
    assert owner.tech_ids == ("restricted_ordnance",)
    assert owner.resources.spice == 0
    assert "acquire_agent_card_tech" not in _ids(engine, bought)
    assert "decline_tech" not in _ids(engine, bought)


def test_ixian_engineer_icon_offers_nothing_when_no_tile_is_affordable() -> None:
    """Detonation Devices costs 3: at a Tech Discount of 1 two spice would
    buy it, so a missing row at 2 spice shows the icon's discount is 0
    (``tech_acquisition_possible``); the turn can end with the icon unused."""
    engine, state = _start()
    placed = _engineer(engine, state, 2)
    assert "acquire_agent_card_tech" not in _ids(engine, placed)
    finished = _finish(engine, placed).players[0]
    assert finished.tech_ids == ()
    assert finished.resources.spice == 2


def test_ixian_engineer_negotiators_lower_the_price() -> None:
    """ "Negotiator를 supply로 돌려 하나에 spice 1씩 깎는다" (rise-of-ix.md 4,
    [Rise of Ix p. 4]): with 2 spice and a Negotiator the 3-spice Detonation
    Devices is in reach, and the purchase returns the Negotiator."""
    engine, state = _start()
    supply = state.players[0].troops_supply
    placed = _engineer(engine, state, 2, negotiators=1, troops_supply=supply - 1)
    assert "acquire_agent_card_tech" in _ids(engine, placed)
    opened = _do(engine, placed, "acquire_agent_card_tech")
    bought = _do(
        engine, opened, "acquire_tech", tech_id="detonation_devices", negotiators=1
    )
    owner = bought.players[0]
    assert owner.tech_ids == ("detonation_devices",)
    assert (owner.resources.spice, owner.negotiators) == (0, 0)


def test_ixian_engineer_window_may_be_declined_and_spends_the_icon() -> None:
    """ "하나를 얻을 수 있다("may")" [Rise of Ix p. 4]: the window offers its
    refusal, and the icon is spent either way."""
    engine, state = _start()
    placed = _engineer(engine, state, 4)
    opened = _do(engine, placed, "acquire_agent_card_tech")
    declined = _do(engine, opened, "decline_tech")
    assert declined.players[0].tech_ids == ()
    assert declined.players[0].resources.spice == 4
    assert "acquire_agent_card_tech" not in _ids(engine, declined)


def test_ixian_engineer_icon_is_optional_and_lapses_at_the_turns_end() -> None:
    """The icon is "may": it offers no refusal of its own and the turn's end
    lapses it unused (OQ-095 (2), ``OPTIONAL_AGENT_ICONS``)."""
    engine, state = _start()
    placed = _engineer(engine, state, 4)
    ids = _ids(engine, placed)
    assert "acquire_agent_card_tech" in ids
    assert not any(row.startswith("decline_") for row in ids)
    finished = _finish(engine, placed).players[0]
    assert finished.tech_ids == ()
    assert finished.resources.spice == 4


def test_ixian_engineer_tech_rows_are_in_the_ix_catalog_only() -> None:
    """The icon and its window are shown by effect rows naming the card that
    prints them, in the original game with Rise of Ix only; no other catalog
    holds them [Rise of Ix p. 2]."""
    engine, state = _start()
    placed = _engineer(engine, state, 4)
    icon_rows = [
        row
        for row in engine.legal_actions(placed, 0)
        if dict(row.arguments).get("printed") == "ixian_engineer"
    ]
    assert {(row.action_id, dict(row.arguments)["icon"]) for row in icon_rows} == {
        ("acquire", "tech")
    }
    opened = _do(engine, placed, "acquire_agent_card_tech")
    window = [
        row
        for row in engine.legal_actions(opened, 0)
        if dict(row.arguments).get("printed") == "ixian_engineer"
    ]
    assert {row.action_id for row in window} == {"decline"}
    plain = ActionCodec(replace(CONFIG, rise_of_ix=False)).catalog
    ix = set(_codec(CONFIG).catalog) - set(plain)
    for row in (*icon_rows, *window):
        assert ActionTemplate(row.action_id, row.arguments) in ix
    assert not any(
        dict(template.arguments).get("printed") == "ixian_engineer"
        for template in ActionCodec(RulesetConfig()).catalog
    )


def _engineer_reveal(
    engine: _Engine, state: GameState, tiles: tuple[str, ...], *hand: str
) -> GameState:
    # The tiles the seat may hold are off the stacks.
    stacks = tuple(
        tuple(tech_id for tech_id in stack if tech_id not in OWNED) for stack in STACKS
    )
    state = _seat(replace(state, tech_stacks=stacks), 0, hand=hand or (ENGINEER,))
    return _do(engine, _seat(state, 0, tech_ids=tiles), "reveal_turn")


def _trash_rows(engine: _Engine, state: GameState) -> list[DomainAction]:
    return [row for row in _rows(engine, state) if row.action_id == "trash_reveal_card"]


def test_ixian_engineer_reveal_offers_the_trash_only_with_three_tech_tiles() -> None:
    """ "If you have three or more Techs:" [Steam app text]: with two Tech tiles
    the arrow waits (judged whenever its row is asked, OQ-028), with three its
    row names the card to trash and the Reveal can still end unused (an arrow
    cost is optional [FAQ p. 3])."""
    engine, state = _start()
    two = _engineer_reveal(engine, state, OWNED[:2])
    assert not _trash_rows(engine, two)
    assert "finish_reveal" in _ids(engine, two)
    three = _engineer_reveal(engine, state, OWNED)
    (row,) = _trash_rows(engine, three)
    assert dict(row.arguments) == {"card_id": ENGINEER, "source": "ixian_engineer"}
    assert "finish_reveal" in _ids(engine, three)
    unused = _do(engine, three, "finish_reveal").players[0]
    assert (unused.victory_points, unused.trashed) == (
        three.players[0].victory_points,
        (),
    )


def test_ixian_engineer_reveal_trashes_itself_for_a_victory_point() -> None:
    """ "Trash this -> Victory Point": the card leaves the game, the seat gains
    1 VP, and the arrow is spent."""
    engine, state = _start()
    revealed = _engineer_reveal(engine, state, OWNED)
    before = revealed.players[0]
    paid = _do(engine, revealed, "trash_reveal_card", card_id=ENGINEER)
    owner = paid.players[0]
    assert owner.victory_points == before.victory_points + 1
    assert ENGINEER in owner.trashed
    assert ENGINEER not in (*owner.hand, *owner.in_play, *owner.discard_pile)
    assert not _trash_rows(engine, paid)


def test_ixian_engineer_reveal_judges_the_tiles_when_the_row_is_asked() -> None:
    """A third Tech tile gained later in the Reveal turn opens the arrow, and
    one lost closes it (OQ-028)."""
    engine, state = _start()
    waiting = _engineer_reveal(engine, state, OWNED[:2])
    assert not _trash_rows(engine, waiting)
    risen = _seat(waiting, 0, tech_ids=OWNED)
    assert len(_trash_rows(engine, risen)) == 1
    fallen = _seat(risen, 0, tech_ids=OWNED[:2])
    assert not _trash_rows(engine, fallen)


def test_two_ixian_engineers_each_trash_only_themselves() -> None:
    """Two copies revealed together: each arrow pays its own card's trash and
    the other copy stays in play for its own arrow."""
    engine, state = _start()
    revealed = _engineer_reveal(engine, state, OWNED, ENGINEER, ENGINEER_TWIN)
    assert {
        dict(row.arguments)["card_id"] for row in _trash_rows(engine, revealed)
    } == {
        ENGINEER,
        ENGINEER_TWIN,
    }
    first = _do(engine, revealed, "trash_reveal_card", card_id=ENGINEER)
    assert first.players[0].victory_points == revealed.players[0].victory_points + 1
    assert ENGINEER_TWIN in first.players[0].in_play
    assert {dict(row.arguments)["card_id"] for row in _trash_rows(engine, first)} == {
        ENGINEER_TWIN
    }
    second = _do(engine, first, "trash_reveal_card", card_id=ENGINEER_TWIN)
    assert second.players[0].victory_points == revealed.players[0].victory_points + 2


def test_ixian_engineer_reveal_values_are_only_the_arrow() -> None:
    """App table: no fixed Persuasion or swords, so the Reveal adds nothing
    beside the arrow."""
    engine, state = _start()
    revealed = _engineer_reveal(engine, state, OWNED[:2])
    context = dict(revealed.decision_stack[-1].context)
    assert (context["persuasion"], context["sword_strength"]) == (0, 0)
