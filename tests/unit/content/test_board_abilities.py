"""Board spaces' printed icons as ability records (composed effects, A5c)."""

from dune_imperium.content.uprising.abilities import AbilityMark, AbilityTiming
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.board_abilities import (
    BOARD_SPACE_ABILITIES,
    board_space_ability,
)
from dune_imperium.content.uprising.effect_dsl import TakeSwordmaster
from dune_imperium.display.effect_dsl_text import reward_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko
from dune_imperium.display.spaces import space_option_effects, space_option_effects_ko


def test_board_records_name_real_spaces_and_options() -> None:
    for (space_id, option, variant), ability in BOARD_SPACE_ABILITIES.items():
        space = BOARD_SPACES_BY_ID[space_id]
        assert option < max(1, len(space.cost_options))
        assert variant in ("", "no_choam", "immortality", "seated")
        assert ability.timing is AbilityTiming.BOARD_SPACE
        assert ability.mark is AbilityMark.AUTOMATIC
        assert all(len(line.rewards) == 1 for line in ability.sections)


def test_the_printed_alternative_comes_first() -> None:
    """A module or the visitor selects the space's printed alternative."""

    def lookup(space: str, **flags: bool) -> object:
        options = {"choam_module": True, "immortality": False} | flags
        return board_space_ability(space, 0, **options)

    assert lookup("dutiful_service") == BOARD_SPACE_ABILITIES[
        "dutiful_service", 0, ""
    ]
    assert lookup("dutiful_service", choam_module=False) == BOARD_SPACE_ABILITIES[
        "dutiful_service", 0, "no_choam"
    ]
    assert lookup("research_station", immortality=True) == BOARD_SPACE_ABILITIES[
        "research_station", 0, "immortality"
    ]
    assert lookup("high_council", seated=True) == BOARD_SPACE_ABILITIES[
        "high_council", 0, "seated"
    ]
    assert lookup("sietch_tabr") is None


def test_the_swordmaster_reads_as_its_space_prints_it() -> None:
    english = space_option_effects("swordmaster", choam_module=True)[0]
    korean = space_option_effects_ko("swordmaster", choam_module=True)[0]
    assert reward_text(TakeSwordmaster()).lower() in english.lower()
    assert reward_text_ko(TakeSwordmaster()) in korean
