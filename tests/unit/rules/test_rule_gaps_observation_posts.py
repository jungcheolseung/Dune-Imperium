"""The observation-post graph, pinned row by row (2026-11 audit).

docs/rules/observation-posts.md transcribes each post's directly connected
board spaces from the four-player board [Main pp. 4-5 board artwork]. Only
the connection counts were pinned before, so a swapped edge that kept the
counts would have passed.
"""

import pytest

from dune_imperium.content.core.icons import AgentIcon
from dune_imperium.content.registry.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.board import BOARD_SPACES, OBSERVATION_POSTS
from dune_imperium.core import PlayerState
from dune_imperium.rules.agent_turn import card_can_access_space

# docs/rules/observation-posts.md "Connection graph", every row [Main pp. 4-5
# board artwork].
_TRANSCRIBED_POSTS: dict[str, frozenset[str]] = {
    "emperor-sardaukar-dutiful-service": frozenset({"sardaukar", "dutiful_service"}),
    "landsraad-high-council-imperial-privilege-swordmaster": frozenset(
        {"high_council", "imperial_privilege", "swordmaster"}
    ),
    "landsraad-assembly-hall-gather-support": frozenset(
        {"assembly_hall", "gather_support"}
    ),
    "choam-shipping-accept-contract": frozenset({"shipping", "accept_contract"}),
    "spacing-guild-heighliner-deliver-supplies": frozenset(
        {"heighliner", "deliver_supplies"}
    ),
    "arrakis-research-station-spice-refinery": frozenset(
        {"research_station", "spice_refinery"}
    ),
    "arrakis-research-station-sietch-tabr": frozenset(
        {"research_station", "sietch_tabr"}
    ),
    "arrakis-spice-refinery-arrakeen": frozenset({"spice_refinery", "arrakeen"}),
    "arrakis-imperial-basin": frozenset({"imperial_basin"}),
    "arrakis-hagga-basin": frozenset({"hagga_basin"}),
    "arrakis-deep-desert": frozenset({"deep_desert"}),
    "bene-gesserit-espionage-secrets": frozenset({"espionage", "secrets"}),
    "fremen-desert-tactics-fremkit": frozenset({"desert_tactics", "fremkit"}),
}


def test_every_observation_post_connects_exactly_its_transcribed_spaces() -> None:
    """Each post's direct connections are the board artwork's.

    docs/rules/observation-posts.md: "이 관계는 observation post와 board space
    사이의 **직접 연결**이다." [Main pp. 4-5 board artwork]
    """

    assert {
        post.post_id: frozenset(post.connected_space_ids) for post in OBSERVATION_POSTS
    } == _TRANSCRIBED_POSTS


@pytest.mark.parametrize("post_id", sorted(_TRANSCRIBED_POSTS))
def test_a_spy_opens_exactly_its_posts_spaces_to_the_spy_icon(post_id: str) -> None:
    """A lone Spy reaches its post's spaces and no space beyond them.

    docs/rules/observation-posts.md: "같은 post에 연결된 공간끼리 또는 연쇄된
    post를 통해 이어지는 공간끼리 별도의 space-to-space edge를 만들면 안
    된다." [Main pp. 4-5 board artwork]; docs/rules/uprising-systems.md: "Spy
    Agent icon은 현재 자기 Spy가 있는 observation post와 연결된 board space를
    Agent 목적지로 허용한다." `[Main pp. 9, 11]`
    """

    owner = PlayerState(player_id=0, spies_supply=2, spy_post_ids=(post_id,))
    reachable = {
        space.space_id
        for space in BOARD_SPACES
        if card_can_access_space((AgentIcon.SPY,), space, owner)
    }

    assert reachable == _TRANSCRIBED_POSTS[post_id]


def test_a_chained_post_does_not_extend_a_spys_reach() -> None:
    """Spice Refinery's two posts do not chain Arrakeen to Research Station.

    docs/rules/observation-posts.md: "같은 post에 연결된 공간끼리 또는 연쇄된
    post를 통해 이어지는 공간끼리 별도의 space-to-space edge를 만들면 안
    된다." [Main pp. 4-5 board artwork]
    """

    owner = PlayerState(
        player_id=0,
        spies_supply=2,
        spy_post_ids=("arrakis-spice-refinery-arrakeen",),
    )

    assert card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["spice_refinery"], owner
    )
    assert not card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["research_station"], owner
    )
    assert not card_can_access_space(
        (AgentIcon.SPY,), BOARD_SPACES_BY_ID["sietch_tabr"], owner
    )
