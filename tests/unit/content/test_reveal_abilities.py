"""Reveal automatic gains as ability records (composed effects, A4c)."""

import pytest

from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.uprising.abilities import AbilityMark, AbilityTiming
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AllConditions,
    CommandersInConflictAtLeast,
    CommandReached,
    EffectSection,
    GainInfluence,
    GainResources,
    GarrisonedUnitsAtLeast,
    GrantCombatDeployment,
    HasHighCouncil,
    HasSwordmaster,
    PlaceSpy,
    RevealPersuasion,
    RevealSwords,
    SpyingOnMakerSpace,
    TrashThisCard,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.reveal_abilities import (
    REVEAL_GAIN_ABILITIES,
    REVEAL_LINE_CONDITIONS,
    REVEAL_LINE_REWARDS,
    check_reveal_gain_line,
)
from dune_imperium.content.uprising.starting_cards import (
    CONTROL_THE_SPICE,
    EXPERIMENTATION,
    STARTING_DECK,
)
from dune_imperium.display.effect_dsl_text import condition_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import (
    condition_text_ko,
    reward_text_ko,
)
from dune_imperium.display.tokens import (
    HANDLED_REVEAL_CONDITIONS,
    HANDLED_REVEAL_REWARDS,
    reveal_effect_text,
)
from dune_imperium.display.tokens_ko import reveal_effect_text_ko
from dune_imperium.rules.reveal_lines import RevealLine


def test_every_record_names_a_card_with_its_play_data() -> None:
    """A card's Reveal gains are its record's lines (the manifests keep no
    copy since the Reveal totals cleanup); every record names a card whose
    play data is transcribed, which the partial-play-data check used to
    guard through the copy."""

    cards = {
        entry.card.card_id: entry.play_data_complete
        for entry in (*IMPERIUM_CARDS, *TLEILAXU_CARDS)
    }
    for entry in (CONTROL_THE_SPICE, EXPERIMENTATION, *STARTING_DECK, *RESERVE_STACKS):
        cards[entry.card.card_id] = True
    for stack in IMPERIUM_RESERVE_STACKS:
        cards[stack.card.card_id] = True
    # The original game's and Rise of Ix's Imperium cards (stages P3/P4d).
    for base_entry in (*IMPERIUM_BASE_CARDS, *IX_IMPERIUM_CARDS):
        cards[base_entry.card.card_id] = base_entry.play_data_complete
    assert set(REVEAL_GAIN_ABILITIES) <= set(cards)
    assert all(cards[card_id] for card_id in REVEAL_GAIN_ABILITIES)
    # 51 Uprising-family records, the original game's The Spice Must Flow and
    # the original Imperium cards' own (stage P3: Crysknife, Duncan Idaho,
    # Fedaykin Death Commando, Thufir Hawat, Spice Hunter, Sietch Reverend
    # Mother, Smuggler's Thopter, Worm Riders' two lines, Assassination
    # Mission, Reverend Mother Mohiam, Liet Kynes, CHOAM Directorship, Guild
    # Bankers, Carryall, Firm Grip, and the promo Thumper).
    # Rise of Ix (stage P4d), one record/line each: Sayyadina's "Fremen
    # Bond: [3 Persuasion]", Imperial Shock Trooper's "If you have an
    # Agent on an [Emperor] board space," [+3 swords] and Shai-Hulud's "Fremen
    # Bond: [5 swords]".
    assert len(REVEAL_GAIN_ABILITIES) == 51 + 1 + 16 + 3
    assert sum(len(a.sections) for a in REVEAL_GAIN_ABILITIES.values()) == (
        55 + 1 + 17 + 3
    )


def test_reveal_gain_records_are_automatic_lines() -> None:
    for ability in REVEAL_GAIN_ABILITIES.values():
        assert ability.timing is AbilityTiming.REVEAL
        assert ability.mark is AbilityMark.AUTOMATIC
        for line in ability.sections:
            assert line.costs == ()
            check_reveal_gain_line(line)


def test_the_card_text_renders_every_kind_a_reveal_line_holds() -> None:
    assert HANDLED_REVEAL_CONDITIONS == REVEAL_LINE_CONDITIONS
    assert HANDLED_REVEAL_REWARDS == REVEAL_LINE_REWARDS


def _section(*rewards: object, condition: object = None) -> EffectSection:
    return EffectSection(rewards=rewards, condition=condition)  # type: ignore[arg-type]


def test_a_reveal_line_the_card_text_cannot_read_is_refused() -> None:
    """The checks the compiled copy (``PersonalCardRevealEffect``) ran."""

    check = check_reveal_gain_line

    with pytest.raises(ValueError, match="must gain"):
        check(_section(TrashThisCard(), condition=HasHighCouncil()))
    with pytest.raises(ValueError, match="must not be negative"):
        check(_section(GainResources(solari=1, water=-1)))
    with pytest.raises(ValueError, match="also needs High Council"):
        check(_section(RevealPersuasion(1), condition=HasSwordmaster()))
    with pytest.raises(ValueError, match="cannot grant Persuasion"):
        check(_section(RevealPersuasion(1), condition=CommandReached()))
    with pytest.raises(ValueError, match="twice"):
        check(_section(GainResources(spice=1), GainResources(water=1)))
    with pytest.raises(ValueError, match="twice"):
        check(
            _section(
                GainResources(spice=1),
                condition=AllConditions((HasHighCouncil(), HasHighCouncil())),
            )
        )
    with pytest.raises(TypeError, match="not a Reveal gain"):
        check(_section(PlaceSpy()))
    with pytest.raises(TypeError, match="not a Reveal gain"):
        check(_section(GainInfluence()))
    with pytest.raises(TypeError, match="not a Reveal gain condition"):
        check(
            _section(GainResources(spice=1), condition=CommandersInConflictAtLeast(2))
        )
    # A Combat icon is a gain on its own (Holy War), a fixed-Faction Influence
    # is read (Shishakli), and so is a Swordmaster line with High Council
    # (Paracompass).
    check(_section(GrantCombatDeployment(), condition=HasHighCouncil()))
    check(_section(GainInfluence(factions=(Faction.FREMEN,))))
    check(
        _section(
            RevealPersuasion(1),
            condition=AllConditions((HasHighCouncil(), HasSwordmaster())),
        )
    )


def test_the_new_reveal_pieces_read_as_the_cards_print_them() -> None:
    """Command, the Maker-space Spy, the garrison size and the Reveal
    Persuasion and swords (with what they are counted per) render as the
    card's Reveal line does, in both languages; the Swordmaster half reads
    whole in Korean, while English prints it inside "High Council and
    Swordmaster"."""

    seen: set[type] = set()
    for ability in REVEAL_GAIN_ABILITIES.values():
        for line in ability.sections:
            english = reveal_effect_text(RevealLine(line))
            korean = reveal_effect_text_ko(RevealLine(line))
            for reward in line.rewards:
                if isinstance(reward, (RevealPersuasion, RevealSwords)):
                    seen.add(type(reward))
                    assert reward_text(reward) in english, english
                    assert reward_text_ko(reward) in korean, korean
            conditions = getattr(line.condition, "conditions", (line.condition,))
            for condition in conditions:
                if isinstance(
                    condition,
                    (CommandReached, SpyingOnMakerSpace, GarrisonedUnitsAtLeast),
                ):
                    seen.add(type(condition))
                    assert condition_text(condition) in english, english
                    assert condition_text_ko(condition) in korean, korean
                if isinstance(condition, HasSwordmaster):
                    seen.add(HasSwordmaster)
                    assert "Swordmaster" in english
                    assert condition_text_ko(condition) in korean, korean
    assert seen == {
        RevealPersuasion,
        RevealSwords,
        CommandReached,
        SpyingOnMakerSpace,
        GarrisonedUnitsAtLeast,
        HasSwordmaster,
    }
