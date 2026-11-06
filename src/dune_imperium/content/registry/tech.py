"""Every Tech tile any game prints, by id, and the tile pool a game draws.

One lookup by id for the Tech Module's tiles and Rise of Ix's (stage P4a,
docs/base-game-and-ix-plan.md 17.1), as ``BOARD_SPACES_BY_ID`` is for the
boards: code that lists the Tech Module's own tiles (its stacks, setup,
codec, catalog and texts) iterates ``content.bloodlines.tech.TECH_TILES``
and ``TECH_IDS``. Moved from ``content.bloodlines.tech``
(docs/content-core-refactor-plan.md 2B), with the two functions that read a
configuration to choose the tiles.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.content.bloodlines.tech import (
    IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD,
    ORIGINAL_GAME_LEFT_OUT_TECH_IDS,
    TECH_TILES,
    tech_tiles_for,
)
from dune_imperium.content.bloodlines.tech_abilities import (
    TECH_ACQUIRE_ABILITIES as TECH_MODULE_ACQUIRE_ABILITIES,
)
from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.core.tech import TechAbility
from dune_imperium.content.rise_of_ix.tech import IX_TECH_TILES
from dune_imperium.content.rise_of_ix.tech_abilities import IX_TECH_ACQUIRE_ABILITIES

TECH_TILES_BY_ID: Final = {
    tile.tech_id: tile for tile in (*TECH_TILES, *IX_TECH_TILES)
}
# Every tile's acquire record, by tile id: the Tech Module's, then Rise of
# Ix's (each set keeps its own, stage 4 of docs/content-core-refactor-plan.md).
TECH_ACQUIRE_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {**TECH_MODULE_ACQUIRE_ABILITIES, **IX_TECH_ACQUIRE_ABILITIES}
)


def has_tech(tech_ids: tuple[str, ...], ability: TechAbility) -> bool:
    """Return whether one of ``tech_ids`` prints ``ability``."""

    return any(TECH_TILES_BY_ID[tech_id].ability is ability for tech_id in tech_ids)


def tech_tile_pool(
    base_game: BaseGame,
    *,
    choam_module: bool,
    tech_module: bool,
    rise_of_ix: bool,
    ix_tech_tiles: bool = False,
) -> tuple[str, ...]:
    """The Tech tiles a game shuffles into its three stacks, in this order.

    The Tech Module alone: its 18 tiles on the Ixian Embassy, CHOAM
    Transports only with the CHOAM Module [Bloodlines pp. 2, 6]
    (``tech_tiles_for``), and on the original board five fewer
    (``ORIGINAL_GAME_LEFT_OUT_TECH_IDS``) and never CHOAM Transports: 12.
    Rise of Ix alone: its 18 on the Ix board [Rise of Ix p. 3]. Both: "두
    모듈의 Tech 타일을 모두 섞어 ... 큰 더미 셋으로" on the Ix board, no Ixian
    Embassy [Bloodlines p. 7]
    (docs/rules/rise-of-ix.md 10a) -- Rise of Ix's 18 then the Tech Module's:
    30 on the original board, 36 on Uprising's (35 without CHOAM). Rise of
    Ix's tiles alone beside the Tech Module (``ix_tech_tiles``): its 16 but
    ``IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD`` then the Tech Module's, on the
    Ixian Embassy [Bloodlines p. 7] -- 28 on the original board, 34 on
    Uprising's (33 without CHOAM). Neither: no tile.
    """

    uprising = base_game is BaseGame.UPRISING
    module = (
        tuple(
            tile.tech_id
            # "4단계: CHOAM 모듈 구성물을 모두 빼고" on the original board
            # [Bloodlines p. 3] (bloodlines.md 2a), CHOAM Transports with them.
            for tile in tech_tiles_for(choam_module and uprising)
            if uprising or tile.tech_id not in ORIGINAL_GAME_LEFT_OUT_TECH_IDS
        )
        if tech_module
        else ()
    )
    if rise_of_ix:
        return (*(tile.tech_id for tile in IX_TECH_TILES), *module)
    if ix_tech_tiles:
        return (
            *(
                tile.tech_id
                for tile in IX_TECH_TILES
                if tile.tech_id not in IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD
            ),
            *module,
        )
    return module


def ixian_embassy_in_play(config: RulesetConfig) -> bool:
    """Whether the Tech Module's Ixian Embassy board is on the table: with
    the module, but not with all of Rise of Ix, whose Ix board takes the
    stacks instead -- "Rise of Ix를 모두 쓸 때: Bloodlines의 Ixian Embassy
    보드를 쓰지 않고 세 더미를 Ix 보드에 둔다. Tech Negotiation의 할인은 쓰고,
    High Council 자리에 따른 Ixian Embassy 할인은 없다" [Bloodlines p. 7]
    (docs/rules/rise-of-ix.md 10a). The Embassy prints both the Landsraad
    visit's Acquire Tech and the High Council seat's discount [Bloodlines
    p. 7]; without it neither exists. With Rise of Ix's tiles alone
    (``ix_tech_tiles``) the Embassy holds both modules' stacks: only "Rise of
    Ix를 모두 쓸 때" leaves it out."""

    return config.tech_module and not config.rise_of_ix
