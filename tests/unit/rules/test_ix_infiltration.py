"""Rise of Ix's printed Infiltration icons, from the Steam app.

Placement: docs/rules/rise-of-ix.md 7 [Rise of Ix p. 7] [FAQ p. 2].
"""

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import BoardSpace
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import opponents_do_not_block

CONFIG = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "earl_memnon_thorvald",
    "glossu_rabban",
    "count_ilban_richese",
    "countess_ariana_thorvald",
)
CARDS = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}


def _space(icon: AgentIcon) -> BoardSpace:
    return next(
        space for space in content_for(CONFIG).board_spaces if space.agent_icon is icon
    )


def test_a_printed_infiltration_icon_ignores_enemy_agents_at_that_icon_only() -> None:
    """'그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시' [Rise of Ix p. 7]."""
    owner = UprisingRulesEngine(leader_ids=LEADERS).reset(CONFIG, 3).players[0]
    bounty_hunter = CARDS["bounty_hunter"]  # City Infiltration
    assert bounty_hunter.infiltration_icons == (AgentIcon.CITY,)
    assert opponents_do_not_block(owner, _space(AgentIcon.CITY), card=bounty_hunter)
    assert not opponents_do_not_block(
        owner, _space(AgentIcon.LANDSRAAD), card=bounty_hunter
    )
    # A card with no printed Infiltration icon, or no card at all (an icon
    # granted by Dispatch an Envoy), gets no bypass.
    assert not opponents_do_not_block(
        owner, _space(AgentIcon.CITY), card=CARDS["desert_ambush"]
    )
    assert not opponents_do_not_block(owner, _space(AgentIcon.CITY))
