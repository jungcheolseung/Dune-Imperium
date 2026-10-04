"""The influence/spy/contract/hooks/wall/recall part of the WormAIProfile port.

Values follow ``spec/profile-influence-uprising.md`` (its §1.2 worked table
for the influence multipliers) and ``spec/board.md`` §3.4 for contracts. The
resource prices and the combat posture belong to the other profile areas;
they are stubbed on the profile instance with fixed, distinct numbers so
every expected value below can be recomputed by hand.
"""

import random
from collections.abc import Callable, Sequence
from dataclasses import replace

import pytest

from dune_imperium.agents.app_ai.abilities import PORTS, Ability
from dune_imperium.agents.app_ai.catalog import (
    agent_entity,
    contract_entity,
    post_entity,
    space_entity,
    spy_entity,
)
from dune_imperium.agents.app_ai.data.archetypes import Archetype
from dune_imperium.agents.app_ai.data.constants import HARD
from dune_imperium.agents.app_ai.entities import Attr, Entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.profile import influence as influence_module
from dune_imperium.agents.app_ai.profile.influence import NO_FACTION
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState

BASE = first_decision("turn")  # round 1; seat 0 Feyd, 2 Amber, 3 Jessica
AGENT = first_decision("agent_effects")  # seat 3 at Arrakeen

PRICES = {
    Attr.SOLARI: 0.6,
    Attr.SPICE: 1.1,
    Attr.WATER: 1.7,
    Attr.TROOPS: 1.3,
    Attr.SANDWORMS: 3.0,
}
INTRIGUE = 2.4
SPY_EARLY = HARD.SpyValueEarly  # 1.66 with no WantSpy card and no spy out

POST_EMPEROR = "emperor-sardaukar-dutiful-service"  # index 1
POST_GUILD = "spacing-guild-heighliner-deliver-supplies"  # 2
POST_LANDSRAAD = "landsraad-high-council-imperial-privilege-swordmaster"  # 5
POST_ASSEMBLY = "landsraad-assembly-hall-gather-support"  # 6
POST_SIETCH = "arrakis-research-station-sietch-tabr"  # 8
POST_DEEP = "arrakis-deep-desert"  # 11
POST_HAGGA = "arrakis-hagga-basin"  # 12

Builder = Callable[..., Profile]


@pytest.fixture
def mk(monkeypatch: pytest.MonkeyPatch) -> Builder:
    """A profile for ``seat`` with the other areas' methods stubbed."""

    def build(
        state: GameState,
        seat: int = 0,
        *,
        arc: int = 0,
        climax: bool = False,
        final: bool = False,
        level: int = 2,
        rng_seed: int = 0,
        **extra: object,
    ) -> Profile:
        p = make_profile(state, seat, level=level, rng_seed=rng_seed)
        stubs: dict[str, object] = {
            "game_arc": lambda: arc,
            "is_climax": lambda: climax,
            "is_final_round": lambda: final,
            "resource_value": lambda attr, n, include=False: PRICES[attr] * n,
            "solari_value": lambda n: PRICES[Attr.SOLARI] * n,
            "spice_value": lambda n: PRICES[Attr.SPICE] * n,
            "water_value": lambda n: PRICES[Attr.WATER] * n,
            "troop_value": lambda n, include=False: PRICES[Attr.TROOPS] * n,
            "sandworm_value": lambda n, include=False: PRICES[Attr.SANDWORMS] * n,
            "intrigue_value": lambda: INTRIGUE,
            "card_draw_value": lambda: 1.5,
            "buy_gains": lambda n: 0.2 * n,
            "possible_persuasion_gain": lambda: 5,
            "deck_agent_icons": lambda: {},
            "abundance_level": lambda attr: 1,
            "opponent_ratio": lambda cond: (
                sum(1 for o in p.ctx.opponents if cond(o)) / len(p.ctx.opponents)
            ),
            "conflict_posture_bounds": lambda: (1.0, 4.0),
            "current_conflict_interest": lambda: Summer(2.0),
            "can_play_to_desert_space_with_hooks": lambda seat, space: False,
        }
        stubs.update(extra)
        for name, fn in stubs.items():
            monkeypatch.setattr(p, name, fn)
        return p

    return build


def infl(**ranks: int) -> Influence:
    return Influence(**ranks)


def seats(state: GameState, **per_seat: dict[str, object]) -> GameState:
    """``with_player`` for several seats: ``seats(s, s0={...}, s2={...})``."""

    for key, changes in per_seat.items():
        state = with_player(state, int(key[1:]), **changes)
    return state


def table(me: Influence, opp: Influence, **mine: object) -> GameState:
    """Seat 0 at ``me``, seat 1 at ``opp``, seats 2-3 at zero."""

    return seats(BASE, s0={"influence": me, **mine}, s1={"influence": opp})


# =============================================================================
# 1.1 GetGainInfluenceValue: the multiplier table (§1.2)
# =============================================================================


@pytest.mark.parametrize(
    ("arc", "level", "expected"),
    [
        (0, 2, 2.25),  # 0->1 Early: no multiplier
        (1, 2, 2.25 * 1.2),  # Mid, newRank >= oppMax: Sieze Opening
        (2, 2, 2.25 * 1.2),
        (1, 1, 2.25 * 1.0),
        (1, 0, 2.25 * 0.85),
    ],
)
def test_gain_from_zero_no_multiplier_or_seize_opening(
    mk: Builder, arc: int, level: int, expected: float
) -> None:
    p = mk(BASE, arc=arc, level=level)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(expected)


def test_seize_opening_needs_new_rank_at_least_opp_max(mk: Builder) -> None:
    p = mk(table(infl(), infl(emperor=1)), arc=1)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 * 1.2)
    p = mk(table(infl(), infl(emperor=2)), arc=1)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25)


@pytest.mark.parametrize(
    ("arc", "level", "expected"),
    [(0, 2, 2.8125), (1, 2, 2.8125), (2, 2, 3.7125), (0, 1, 2.3625), (0, 0, 1.9125)],
)
def test_victory_point_crossing(
    mk: Builder, arc: int, level: int, expected: float
) -> None:
    p = mk(table(infl(emperor=1), infl()), arc=arc, level=level)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(expected)


def test_victory_point_branch_shadows_the_alliance_branch(mk: Builder) -> None:
    # 1 -> 4 crosses 2 first: only the VP multiplier, plus the track bonus.
    p = mk(table(infl(spacing_guild=1), infl(spacing_guild=3)))
    expected = 2.25 * 3 * 1.25 + 3 * PRICES[Attr.SOLARI]
    assert p.gain_influence_value("spacing_guild", 3).sum == pytest.approx(expected)


@pytest.mark.parametrize(
    ("opp", "expected"),
    [(4, 4.5), (3, 3.375), (2, 1.485), (0, 1.485)],
)
def test_holding_the_alliance_defend_or_secure(
    mk: Builder, opp: int, expected: float
) -> None:
    state = table(infl(emperor=4), infl(emperor=opp), alliance_faction_ids=("emperor",))
    p = mk(state)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(expected)


def test_alliance_threat_with_track_bonus(mk: Builder) -> None:
    # 3 -> 4 with an opponent also at 3, token free: x1.75 + 3 Solari.
    p = mk(table(infl(spacing_guild=3), infl(spacing_guild=3)))
    expected = 2.25 * 1.75 + 3 * PRICES[Attr.SOLARI]
    assert p.gain_influence_value("spacing_guild", 1).sum == pytest.approx(expected)


@pytest.mark.parametrize(("arc", "mod"), [(0, 1.25), (1, 1.25), (2, 1.65)])
def test_gain_alliance_against_low_opponents(mk: Builder, arc: int, mod: float) -> None:
    # 2 -> 4 with the top opponent at 2: Gain Alliance (Late), BG bonus intrigue.
    p = mk(table(infl(bene_gesserit=2), infl(bene_gesserit=2)), arc=arc)
    expected = 4.5 * mod + INTRIGUE
    assert p.gain_influence_value("bene_gesserit", 2).sum == pytest.approx(expected)


@pytest.mark.parametrize(("arc", "base"), [(0, 2.25), (1, 2.7), (2, 2.7)])
def test_sole_leader_reaching_four_falls_in_the_hole(
    mk: Builder, arc: int, base: float
) -> None:
    # 3 -> 4 with every opponent <= 2: no alliance multiplier (cur > oppMax).
    p = mk(table(infl(fremen=3), infl(fremen=2)), arc=arc)
    expected = base + PRICES[Attr.WATER]
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(expected)


def test_emperor_track_bonus_is_the_spy_value(mk: Builder) -> None:
    p = mk(table(infl(emperor=3), infl(emperor=3)))
    expected = 2.25 * 1.75 + SPY_EARLY
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(expected)


@pytest.mark.parametrize(("vp", "mod"), [(9, 1.75), (10, 3.0), (12, 3.0)])
def test_steal_alliance_and_steal_endgame(mk: Builder, vp: int, mod: float) -> None:
    state = seats(
        BASE,
        s0={"influence": infl(emperor=4)},
        s1={
            "influence": infl(emperor=4),
            "alliance_faction_ids": ("emperor",),
            "victory_points": vp,
        },
    )
    p = mk(state)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 * mod)


@pytest.mark.parametrize(
    ("cur", "opp", "amount", "bonus"),
    [(3, 5, 2, SPY_EARLY), (3, 4, 1, SPY_EARLY), (4, 5, 1, 0.0)],
)
def test_threaten_alliance(
    mk: Builder, cur: int, opp: int, amount: int, bonus: float
) -> None:
    state = seats(
        BASE,
        s0={"influence": infl(emperor=cur)},
        s1={"influence": infl(emperor=opp), "alliance_faction_ids": ("emperor",)},
    )
    p = mk(state)
    expected = 2.25 * amount * 1.3 + bonus
    assert p.gain_influence_value("emperor", amount).sum == pytest.approx(expected)


def test_alliance_impossible_and_unlikely(mk: Builder) -> None:
    held = {"alliance_faction_ids": ("emperor",)}
    p = mk(
        seats(
            BASE,
            s0={"influence": infl(emperor=4)},
            s1={"influence": infl(emperor=6), **held},
        )
    )
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 * 0.25)
    p = mk(
        seats(
            BASE,
            s0={"influence": infl(emperor=2)},
            s1={"influence": infl(emperor=4), **held},
        )
    )
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(1.125)
    # Easy reverses the preference.
    p = mk(
        seats(
            BASE,
            s0={"influence": infl(emperor=2)},
            s1={"influence": infl(emperor=4), **held},
        ),
        level=0,
    )
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 * 1.15)


def test_full_track_gain_is_worth_nothing_even_with_leader_terms(mk: Builder) -> None:
    state = seats(
        BASE,
        s2={"influence": infl(emperor=6), "alliance_faction_ids": ()},
    )
    p = mk(state, seat=2)  # Lady Amber: no alliance token held
    assert p.gain_influence_value("emperor", 1).sum == 0.0


@pytest.mark.parametrize(
    ("cur", "opp", "alliance", "expected"),
    [
        (4, 3, True, -5.625),  # Forfeit Alliance (newRank < 4)
        (5, 5, True, -5.625),  # Forfeit Alliance (newRank < oppMax)
        (5, 4, True, -3.9375),  # Forfeit Cushion (newRank == oppMax)
        (6, 3, True, -2.25),  # holder keeps the lead; cur 6 losses go to LOSS
        (2, 0, False, -4.5),  # Forfeit Victory Point
        (3, 6, False, -0.5625),  # Alliance Impossible
        (3, 5, False, -0.7425),  # Alliance Unlikely
        (3, 2, False, -2.25),  # plain loss
    ],
)
def test_losses(
    mk: Builder, cur: int, opp: int, alliance: bool, expected: float
) -> None:
    state = seats(
        BASE,
        s0={
            "influence": infl(emperor=cur),
            "alliance_faction_ids": ("emperor",) if alliance else (),
        },
        s1={"influence": infl(emperor=opp)},
    )
    p = mk(state)
    assert p.gain_influence_value("emperor", -1).sum == pytest.approx(expected)


def test_explicit_rank_and_alliance_replace_the_reads(mk: Builder) -> None:
    p = mk(table(infl(), infl(emperor=4)))
    # current_rank 1: the VP branch although the seat is at 0.
    assert p.gain_influence_value("emperor", 1, 1, False).sum == pytest.approx(2.8125)
    # current_rank 4 with has_alliance: Protect Threatened Alliance.
    assert p.gain_influence_value("emperor", 1, 4, True).sum == pytest.approx(4.5)
    # current_rank 0 counts as given (has_alliance kept, not re-read).
    assert p.gain_influence_value("emperor", 1, 0, False).sum == pytest.approx(2.25)


def test_any_faction_takes_the_max_gain_and_the_min_loss(mk: Builder) -> None:
    p = mk(table(infl(emperor=2, bene_gesserit=1), infl(), maker_hooks=True))
    # Gains: BG 1 -> 2 crosses the VP (2.8125); the others 2.25.
    assert p.gain_influence_value(NO_FACTION, 1).sum == pytest.approx(2.8125)
    # Losses: Emperor 2 -> 1 forfeits the VP (-4.5): the minimum.
    assert p.gain_influence_value(NO_FACTION, -1).sum == pytest.approx(-4.5)
    # The caller's rank and alliance are dropped in this branch.
    assert p.gain_influence_value(NO_FACTION, 1, 5, True).sum == pytest.approx(2.8125)


# -- 1.1 (E): leader and intrigue terms ----------------------------------------


def test_margot_bene_gesserit_spice_term(mk: Builder) -> None:
    state = with_player(BASE, 0, leader_id="lady_margot_fenring")
    p = mk(state)
    expected = 2.25 + 0.75 * (PRICES[Attr.SPICE] * 1)
    assert p.gain_influence_value("bene_gesserit", 1).sum == pytest.approx(expected)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25)
    p = mk(with_player(state, 0, influence=infl(bene_gesserit=2)))
    assert p.gain_influence_value("bene_gesserit", 1).sum == pytest.approx(2.25)


def test_amber_term_needs_no_alliance_and_applies_to_losses(mk: Builder) -> None:
    p = mk(BASE, seat=2)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 + 0.75)
    p = mk(with_player(BASE, 2, influence=infl(fremen=3)), seat=2)
    assert p.gain_influence_value("fremen", -1).sum == pytest.approx(-2.25 - 0.75)
    allied = with_player(BASE, 2, alliance_faction_ids=("fremen",))
    p = mk(allied, seat=2)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25)


def test_irulan_emperor_term(mk: Builder) -> None:
    state = with_player(BASE, 0, leader_id="princess_irulan")
    p = mk(state)
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25 + 1.0)
    p = mk(with_player(state, 0, influence=infl(emperor=2)))
    assert p.gain_influence_value("emperor", 1).sum == pytest.approx(2.25)


def hooks(state: GameState, *opponent_seats: int) -> GameState:
    for seat in opponent_seats:
        state = with_player(state, seat, maker_hooks=True)
    return state


def test_muad_dib_and_maker_hook_fremen_multipliers(mk: Builder) -> None:
    state = with_player(BASE, 0, leader_id="muad_dib")
    p = mk(state)
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25 * 1.25 * 1.2)
    # One opponent of three with hooks: ratio 1/3 <= 0.5, both still apply.
    p = mk(hooks(state, 1))
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25 * 1.25 * 1.2)
    # Two of three: neither.
    p = mk(hooks(state, 1, 2))
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25)
    # Climax: neither.
    p = mk(state, climax=True)
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25)
    # Own hooks: neither.
    p = mk(with_player(state, 0, maker_hooks=True))
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25)


def test_maker_hook_fremen_multiplier_scales_the_track_and_additive_terms(
    mk: Builder,
) -> None:
    # Fremen 1 -> 2: VP x1.25, then x1.2 for the missing hooks; 2 -> 3 none.
    p = mk(with_player(BASE, 0, influence=infl(fremen=1)))
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.8125 * 1.2)
    p = mk(with_player(BASE, 0, influence=infl(fremen=2)))
    assert p.gain_influence_value("fremen", 1).sum == pytest.approx(2.25)


def with_intrigue(state: GameState, seat: int, *card_ids: str) -> GameState:
    ids = tuple(f"intrigue:{cid}:0" for cid in card_ids)
    return with_player(state, seat, intrigue_cards=ids)


@pytest.mark.parametrize(
    ("card", "faction", "cur", "bonus"),
    [
        ("depart_for_arrakis", "spacing_guild", 2, 0.25),
        ("depart_for_arrakis", "spacing_guild", 3, 0.0),
        ("depart_for_arrakis", "emperor", 0, 0.0),
        ("shaddam_s_favor", "emperor", 5, 0.25),  # no rank test
        ("strategic_stockpiling", "fremen", 2, 0.25),
        ("strategic_stockpiling", "fremen", 3, 0.0),
        ("weirding_combat", "bene_gesserit", 2, 0.25),
        ("weirding_combat", "bene_gesserit", 3, 0.0),
    ],
)
def test_additive_intrigue_terms(
    mk: Builder, card: str, faction: str, cur: int, bonus: float
) -> None:
    state = with_intrigue(BASE, 0, card)
    state = with_player(state, 0, influence=Influence(**{faction: cur}))
    p = mk(state)
    # cur 2/3/5 -> +1 against opponents at 0, Early: base 2.25 only (cur 3
    # reaches 4: add the track bonus).
    track = {
        "spacing_guild": 3 * PRICES[Attr.SOLARI],
        "fremen": PRICES[Attr.WATER],
        "bene_gesserit": INTRIGUE,
        "emperor": SPY_EARLY,
    }
    expected = 2.25 + (track[faction] if cur == 3 else 0.0) + bonus
    if faction == "fremen" and cur <= 1:
        expected *= 1.2
    assert p.gain_influence_value(faction, 1).sum == pytest.approx(expected)


def test_shadow_alliance_scales_what_came_before(mk: Builder) -> None:
    # SG 2 -> 4 against an opponent at 2, token free (Gain Alliance x1.25),
    # + 3 Solari track bonus, + Depart for Arrakis 0.25 x 2, then x1.2.
    state = table(infl(spacing_guild=2), infl(spacing_guild=2))
    state = with_intrigue(state, 0, "depart_for_arrakis", "shadow_alliance")
    p = mk(state)
    before = 4.5 * 1.25 + 3 * PRICES[Attr.SOLARI] + 0.5
    assert p.gain_influence_value("spacing_guild", 2).sum == pytest.approx(before * 1.2)
    # An opponent holds the BG Alliance while the seat has 4 BG: the seat
    # already has a Shadow Alliance, so no x1.2.
    shadow = seats(
        state,
        s0={"influence": infl(spacing_guild=2, bene_gesserit=4)},
        s2={
            "influence": infl(bene_gesserit=5),
            "alliance_faction_ids": ("bene_gesserit",),
        },
    )
    p = mk(shadow)
    assert p.gain_influence_value("spacing_guild", 2).sum == pytest.approx(before)
    # Below rank 4 after the gain: no x1.2.
    p = mk(state)
    assert p.gain_influence_value("spacing_guild", 1).sum == pytest.approx(2.25 + 0.25)


# =============================================================================
# 1.3 HasOrWouldGainAlliance, 1.4 GetBestInfluenceExchange
# =============================================================================


def test_has_or_would_gain_alliance(mk: Builder) -> None:
    p = mk(table(infl(emperor=3), infl(emperor=4)))
    assert p.has_or_would_gain_alliance("emperor", 1)  # tie: optimistic
    assert not p.has_or_would_gain_alliance("emperor", 0)
    assert not p.has_or_would_gain_alliance("spacing_guild", 3)  # 3 < 4
    assert p.has_or_would_gain_alliance("spacing_guild", 4)
    p = mk(table(infl(emperor=2), infl(emperor=5)))
    assert not p.has_or_would_gain_alliance("emperor", 2)  # 4 < 5
    allied = table(infl(fremen=4), infl(), alliance_faction_ids=("fremen",))
    assert mk(allied).has_or_would_gain_alliance("fremen", -3)


def test_best_influence_exchange_picks_the_best_positive_total(mk: Builder) -> None:
    state = table(infl(spacing_guild=3, bene_gesserit=1, fremen=1), infl())
    p = mk(state)
    lose = ["spacing_guild"]
    gain = ["bene_gesserit", "fremen", "spacing_guild"]
    result = p.best_influence_exchange(-1, 1, lose, gain)
    # lose SG 3 -> 2: -2.25; gain Fremen 1 -> 2: 2.8125 x 1.2 (no hooks).
    assert result[:2] == ("spacing_guild", "fremen")
    assert result[2] == pytest.approx(-2.25 + 2.8125 * 1.2)
    assert gain == ["bene_gesserit", "fremen", "spacing_guild"]  # not mutated


def test_best_influence_exchange_same_faction_uses_the_post_loss_rank(
    mk: Builder,
) -> None:
    # Emperor 2: losing one forfeits the VP (-4.5); regaining it from 1 is a
    # VP crossing (2.8125), so the pair totals -1.6875 and nothing is > 0.
    p = mk(table(infl(emperor=2), infl()))
    assert p.best_influence_exchange(1, 1) == (None, None, 0.0)
    # Only factions the seat can lose from are candidates (none at 0).
    assert mk(BASE).best_influence_exchange(-1, 1) == (None, None, 0.0)
    # With the post-loss rank the same-faction swap is valued as 1 -> 2.
    p = mk(table(infl(emperor=2), infl()))
    swap = p.best_influence_exchange(-1, 2, ["emperor"], ["emperor"])
    assert swap[:2] == ("emperor", "emperor")
    assert swap[2] == pytest.approx(-4.5 + 4.5 * 1.25)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_best_influence_exchange_ties_go_to_the_first_shuffled(
    mk: Builder, seed: int
) -> None:
    # Gains to Emperor and BG from 1 are both worth 2.8125: equal totals.
    state = table(infl(spacing_guild=3, emperor=1, bene_gesserit=1), infl())
    p = mk(state, rng_seed=seed)
    lose = ["spacing_guild"]
    gain = ["emperor", "bene_gesserit"]
    result = p.best_influence_exchange(-1, 1, lose, gain)
    rng = random.Random(seed)
    lose_copy, gain_copy = list(lose), list(gain)
    rng.shuffle(lose_copy)
    rng.shuffle(gain_copy)
    assert result[:2] == ("spacing_guild", gain_copy[0])
    assert result[2] == pytest.approx(-2.25 + 2.8125)


# =============================================================================
# 2. Spies
# =============================================================================


def test_spy_value_base_per_arc(mk: Builder) -> None:
    assert mk(BASE, arc=0).spy_value().sum == pytest.approx(1.66)
    assert mk(BASE, arc=1).spy_value().sum == pytest.approx(1.66)
    assert mk(BASE, arc=2).spy_value().sum == pytest.approx(1.33)


def spies_out(state: GameState, seat: int, *posts: str) -> GameState:
    return with_player(state, seat, spy_post_ids=posts, spies_supply=3 - len(posts))


def test_spy_value_counts_want_spy_cards_spies_and_spring_the_trap(mk: Builder) -> None:
    me = BASE.players[0]
    state = with_player(
        BASE,
        0,
        deck=(*me.deck, "imperium:spy_network:0"),
        discard_pile=("imperium:guild_spy:0",),
    )
    state = with_intrigue(state, 0, "spring_the_trap")
    state = spies_out(state, 0, POST_EMPEROR, POST_DEEP)
    p = mk(state)
    # 3 WantSpy (deck, discard, intrigue): x1.75; 2 spies: x0.34; x1.5.
    expected = 1.66 * (1.0 + 0.25 * 3) * (1.0 - 0.33 * 2) * 1.5
    assert p.spy_value().sum == pytest.approx(expected)
    three = spies_out(BASE, 0, POST_EMPEROR, POST_DEEP, POST_HAGGA)
    assert mk(three).spy_value().sum == pytest.approx(1.66 * 0.01)


def agent_turn_state(
    seat_changes: dict[str, object] | None = None,
) -> tuple[GameState, int]:
    decision = AGENT.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    state = AGENT if not seat_changes else with_player(AGENT, seat, **seat_changes)
    return state, seat


def test_recall_spy_value_is_minus_spy_value_outside_the_agent_turn(
    mk: Builder,
) -> None:
    state = with_player(BASE, 0, in_play=("imperium:imperial_spymaster:0",))
    p = mk(state)
    assert p.recall_spy_value().sum == pytest.approx(-1.66 * 1.25)


def test_recall_spy_value_adds_want_recall_cards_in_the_agent_turn(mk: Builder) -> None:
    seat = agent_turn_state()[1]
    in_play = (
        *AGENT.players[seat].in_play,
        "imperium:imperial_spymaster:0",
        "imperium:strike_fleet:0",
    )
    state, seat = agent_turn_state({"in_play": in_play})
    p = mk(state, seat)
    spy = 1.66 * (1.0 + 0.25 * 2)
    assert p.recall_spy_value().sum == pytest.approx(-spy + 4.5 * 2)
    recalled, seat = agent_turn_state({"in_play": in_play, "spies_recalled_turn": 1})
    assert mk(recalled, seat).recall_spy_value().sum == pytest.approx(-spy)


def test_post_value_faction_post(mk: Builder) -> None:
    post = post_entity(POST_EMPEROR)
    deck = {"Emperor": 2, "Pentagon": 5}
    p = mk(BASE, deck_agent_icons=lambda: deck)
    assert p.post_value(post) == pytest.approx(2.0 + 2.0)
    # The gain is worth >= 3 (Emperor 1 -> 2, Late: 3.7125): +1.
    late = mk(
        with_player(BASE, 0, influence=infl(emperor=1)),
        arc=2,
        deck_agent_icons=lambda: deck,
    )
    assert late.post_value(post) == pytest.approx(2.0 + 2.0 + 1.0)
    # Guild Spy owned anywhere: +2.
    spy = with_player(BASE, 0, discard_pile=("imperium:guild_spy:0",))
    assert mk(spy, deck_agent_icons=lambda: deck).post_value(post) == pytest.approx(6.0)


def test_post_value_unseen_network_terms_for_staban(mk: Builder) -> None:
    staban = with_player(
        BASE, 0, leader_id="staban_tuek", resources=Resources(solari=2, spice=1)
    )
    p = mk(staban)
    guild = post_entity(POST_GUILD)
    # Faction post: Solari >= 2 and Intrigue (2.4) > Solari(2) (1.2): +1.
    assert p.post_value(guild, unseen_network=True) == pytest.approx(2.0 + 1.0)
    assert p.post_value(guild) == pytest.approx(2.0)
    poor = with_player(staban, 0, resources=Resources(solari=1, spice=1))
    assert mk(poor).post_value(guild, unseen_network=True) == pytest.approx(2.0)
    # Pentagon post: spice > 0 and Solari(3) (1.8) > Spice(1) (1.1): +1; the
    # Swordmaster space adds 2 while the seat has no Swordmaster.
    landsraad = post_entity(POST_LANDSRAAD)
    assert p.post_value(landsraad, unseen_network=True) == pytest.approx(1.0 + 2.0)
    no_spice = with_player(staban, 0, resources=Resources(solari=2, spice=0))
    assert mk(no_spice).post_value(landsraad, True) == pytest.approx(2.0)
    # Not Staban: no Unseen Network term.
    assert mk(BASE).post_value(landsraad, True) == pytest.approx(2.0)


def test_post_value_swordmaster_and_icons(mk: Builder) -> None:
    deck = {"Pentagon": 3}
    landsraad = post_entity(POST_LANDSRAAD)
    p = mk(BASE, deck_agent_icons=lambda: deck)
    assert p.post_value(landsraad) == pytest.approx(3.0 + 2.0)
    owned = with_player(BASE, 0, swordmaster_acquired=True, agents_available=3)
    assert mk(owned, deck_agent_icons=lambda: deck).post_value(
        landsraad
    ) == pytest.approx(3.0)
    assert p.post_value(post_entity(POST_ASSEMBLY)) == pytest.approx(3.0)


def test_post_value_hooks_terms(mk: Builder) -> None:
    hooked = with_player(BASE, 0, maker_hooks=True, influence=infl(fremen=2))
    assert mk(hooked).post_value(post_entity(POST_HAGGA)) == pytest.approx(1.5)
    assert mk(BASE).post_value(post_entity(POST_HAGGA)) == pytest.approx(0.0)
    assert mk(hooked).post_value(post_entity(POST_SIETCH)) == pytest.approx(1.5)
    low = with_player(hooked, 0, influence=infl(fremen=1))
    assert mk(low).post_value(post_entity(POST_SIETCH)) == pytest.approx(0.0)


def test_post_value_staban_maker_post(mk: Builder) -> None:
    staban = with_player(BASE, 0, leader_id="staban_tuek")
    p = mk(staban)
    assert p.post_value(post_entity(POST_HAGGA)) == pytest.approx(2.5)
    assert p.post_value(post_entity(POST_EMPEROR)) == pytest.approx(2.0)
    # Already watching a maker space (Deep Desert): no maker term anywhere.
    watching = spies_out(staban, 0, POST_DEEP)
    assert mk(watching).post_value(post_entity(POST_HAGGA)) == pytest.approx(0.0)
    assert mk(staban, final=True).post_value(post_entity(POST_HAGGA)) == pytest.approx(
        0.0
    )


def test_post_selection_best_and_worst_with_shuffled_ties(mk: Builder) -> None:
    deck = {"Emperor": 1, "SpacingGuild": 1}
    posts = [
        post_entity(POST_EMPEROR),
        post_entity(POST_GUILD),
        post_entity(POST_ASSEMBLY),
    ]
    # Emperor post 3.0, Guild post 3.0 (tie), Assembly Hall 0.0.
    for seed in range(6):
        p = mk(BASE, rng_seed=seed, deck_agent_icons=lambda: deck)
        order = list(posts)
        random.Random(seed).shuffle(order)
        tied = [q for q in order if q.ref != POST_ASSEMBLY]
        best, value = p.best_post(posts)
        assert best == tied[0]
        assert value == pytest.approx(3.0)
    p = mk(BASE, deck_agent_icons=lambda: deck)
    chosen, total = p.post_selection(posts, 2, best=False)
    assert chosen[0].ref == POST_ASSEMBLY
    assert total == pytest.approx(3.0)
    assert p.post_selection(posts, 0, best=True) == ([], 0.0)
    assert p.best_post([]) == (None, 0.0)


def test_recall_spy_and_recall_spies_take_the_worst_posts(mk: Builder) -> None:
    deck = {"Emperor": 1}
    state = spies_out(BASE, 0, POST_EMPEROR, POST_ASSEMBLY, POST_GUILD)
    p = mk(state, deck_agent_icons=lambda: deck)
    spies = [spy_entity(post, 0) for post in (POST_EMPEROR, POST_ASSEMBLY, POST_GUILD)]
    spy, value = p.recall_spy(spies)
    assert spy == spy_entity(POST_ASSEMBLY, 0)
    assert value == pytest.approx(0.0)
    chosen, total = p.recall_spies(spies, 2)
    assert chosen == [spy_entity(POST_ASSEMBLY, 0), spy_entity(POST_GUILD, 0)]
    assert total == pytest.approx(0.0 + 2.0)
    assert p.recall_spy([]) == (None, 0.0)


# =============================================================================
# 3. Contracts
# =============================================================================


def contracts_completed(state: GameState, seat: int, ids: tuple[str, ...]) -> GameState:
    state = with_state(
        state,
        contract_bank=tuple(c for c in state.contract_bank if c not in ids),
        face_up_contract_ids=tuple(
            c for c in state.face_up_contract_ids if c not in ids
        ),
    )
    return with_player(state, seat, completed_contract_ids=ids)


WANT_CONTRACT_CARDS = (
    "imperium:cargo_runner:0",  # WantContract2, WantContract4
    "imperium:interstellar_trade:0",  # WantContractX
    "imperium:delivery_agreement:0",  # WantContract4
)


@pytest.mark.parametrize(
    ("completed", "count"),
    [
        ((), 4),
        (("contract:harvest_4",), 4),
        (("contract:harvest_4", "contract:sardaukar_i"), 3),
        (("contract:harvest_4", "contract:sardaukar_i", "contract:sardaukar_ii"), 3),
        (
            (
                "contract:harvest_4",
                "contract:sardaukar_i",
                "contract:sardaukar_ii",
                "contract:deliver_supplies",
            ),
            1,
        ),
    ],
)
def test_want_contract_count_by_completed_contracts(
    mk: Builder, completed: tuple[str, ...], count: int
) -> None:
    state = with_player(BASE, 0, discard_pile=WANT_CONTRACT_CARDS)
    state = with_intrigue(state, 0, "backed_by_choam")  # WantContract2
    state = contracts_completed(state, 0, completed)
    assert mk(state).want_contract_count() == count


@pytest.mark.parametrize(("arc", "base"), [(0, 2.0), (1, 1.75), (2, 1.5)])
def test_gain_contract_value(mk: Builder, arc: int, base: float) -> None:
    state = with_player(BASE, 0, discard_pile=WANT_CONTRACT_CARDS)
    p = mk(state, arc=arc)
    assert p.gain_contract_value().sum == pytest.approx(base * (1.0 + 0.33 * 3))
    assert mk(BASE, arc=arc).gain_contract_value().sum == pytest.approx(base)


def contract(card: str) -> Entity:
    return contract_entity(f"contract:{card}")


def test_contract_immediate_is_its_reward(mk: Builder) -> None:
    p = mk(BASE)
    assert p.contract_acquire_value(contract("immediate")).sum == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("icons", "icon_term"),
    [(3, 2.0 * 0.17), (2, 0.0), (1, -2.0 * 0.17), (0, -5.0 * 0.17)],
)
def test_space_contract_agent_icons_mod(
    mk: Builder, icons: int, icon_term: float
) -> None:
    p = mk(BASE, deck_agent_icons=lambda: {"SpacingGuild": icons})
    reward = 0.5 * (3 * PRICES[Attr.SOLARI]) * 1.0  # round 1: k = 1.0
    value = p.contract_acquire_value(contract("deliver_supplies")).sum
    assert value == pytest.approx(reward + icon_term)


def test_space_contract_round_factor_spy_mod_and_no_icon_term(mk: Builder) -> None:
    # Research Station II: no faction space (no icon term), water abundance.
    later = with_state(BASE, round_number=5)  # k = 0.5
    p = mk(later, abundance_level=lambda attr: 0 if attr is Attr.WATER else 1)
    value = p.contract_acquire_value(contract("research_station_ii")).sum
    assert value == pytest.approx(0.5 * 1.8 * 0.5 + 0.16 * -3.0)
    # Round 9: k floors at 0.25; a Spy watching Research Station: +0.32.
    late = spies_out(with_state(BASE, round_number=9), 0, POST_SIETCH)
    p = mk(late, abundance_level=lambda attr: -1)
    value = p.contract_acquire_value(contract("research_station_ii")).sum
    assert value == pytest.approx(0.5 * 1.8 * 0.25 + 0.0 + 2.0 * 0.16)


@pytest.mark.parametrize(
    ("card", "attr", "reward"),
    [
        ("heighliner_ii", Attr.SPICE, 2 * PRICES[Attr.TROOPS]),
        ("high_council_ii", Attr.SOLARI, 3 * PRICES[Attr.SOLARI]),
    ],
)
@pytest.mark.parametrize(("level", "tri"), [(0, -3.0), (2, 3.0), (-1, 0.0)])
def test_space_contract_resource_mod_abundance(
    mk: Builder, card: str, attr: Attr, reward: float, level: int, tri: float
) -> None:
    deck = {"SpacingGuild": 2}  # Heighliner icon term 0
    p = mk(
        BASE,
        deck_agent_icons=lambda: deck,
        abundance_level=lambda a: level if a is attr else 1,
    )
    value = p.contract_acquire_value(contract(card)).sum
    assert value == pytest.approx(0.5 * reward + 0.16 * tri)


@pytest.mark.parametrize(("solari", "tri"), [(0.4, -3.0), (0.6, 0.0), (0.9, 3.0)])
def test_spice_refinery_contract_uses_the_solari_price(
    mk: Builder, solari: float, tri: float
) -> None:
    p = mk(BASE, solari_value=lambda n: solari * n)
    value = p.contract_acquire_value(contract("spice_refinery_ii")).sum
    assert value == pytest.approx(0.5 * PRICES[Attr.WATER] + 0.16 * tri)


@pytest.mark.parametrize(("solari", "tri"), [(1.2, -3.0), (1.5, 0.0), (1.8, 3.0)])
def test_harvest_contract(mk: Builder, solari: float, tri: float) -> None:
    state = with_state(
        BASE,
        maker_bonus_spice=(
            ("deep_desert", 2),
            ("hagga_basin", 1),
            ("imperial_basin", 0),
        ),
    )
    p = mk(state, solari_value=lambda n: solari * n)
    value = p.contract_acquire_value(contract("harvest_3")).sum
    expected = 0.5 * (3 * solari) + 0.33 * tri + 0.33 * 0.33 * 3
    assert value == pytest.approx(expected)


@pytest.mark.parametrize(
    ("arc", "seat", "round_term", "council_term"),
    [(0, False, -0.99, -0.99), (1, True, 0.0, 0.99), (2, False, 0.99, -0.99)],
)
def test_tsmf_acquire_contract(
    mk: Builder, arc: int, seat: bool, round_term: float, council_term: float
) -> None:
    state = with_player(BASE, 0, high_council=seat)
    p = mk(state, arc=arc)
    sg_gain = 2.25 * (1.2 if arc else 1.0)  # 0 -> 1, Sieze Opening when Mid/Late
    reward = 1.8 + sg_gain + 1.8  # the 3 Solari counted twice
    value = p.contract_acquire_value(contract("acquire")).sum
    assert value == pytest.approx(0.34 * reward + council_term + round_term)


def test_contract_reward_overrides(mk: Builder) -> None:
    deck = {"Emperor": 2}  # Sardaukar icon term 0
    p = mk(BASE, deck_agent_icons=lambda: deck, abundance_level=lambda a: -1)
    # Draw 2: 2 x CardDraw + BuyGains(PossiblePersuasionGain = 5).
    draw = p.contract_acquire_value(contract("spice_refinery_i")).sum
    assert draw == pytest.approx(0.5 * (3.0 + 1.0))
    # Place a spy: Solari(2) + SpyValue.
    spy = p.contract_acquire_value(contract("research_station_i")).sum
    assert spy == pytest.approx(0.5 * (1.2 + SPY_EARLY))
    # Recall an agent with none on the board: RecallAgentValue = -3.
    recall = p.contract_acquire_value(contract("sardaukar_ii")).sum
    assert recall == pytest.approx(0.5 * -3.0)
    # +1 Bene Gesserit.
    bg = p.contract_acquire_value(contract("high_council_i")).sum
    assert bg == pytest.approx(0.5 * 2.25)


def test_best_contract_strict_first_max_and_forced_floor(mk: Builder) -> None:
    p = mk(BASE)
    a, b = contract("high_council_ii"), contract("deliver_supplies")
    values = {a.ref: 2.0, b.ref: 2.0}
    p_values = mk(BASE, contract_acquire_value=lambda c: Summer(values[c.ref]))
    assert p_values.best_contract([a, b], forced=False) == (a, 2.0)
    values[b.ref] = 3.0
    assert p_values.best_contract([a, b], forced=True) == (b, 3.0)
    values.update({a.ref: -1.0, b.ref: -0.5})
    assert p_values.best_contract([a, b], forced=True) == (b, 1.0)
    assert p_values.best_contract([a, b], forced=False) == (None, 0.0)
    assert p.best_contract([], forced=True) == (None, 1.0)


# =============================================================================
# 4. Battle icons, 5. Maker hooks
# =============================================================================


@pytest.mark.parametrize(
    ("icon", "arc", "expected"),
    [
        ("None", 0, 2.5),
        ("", 2, 4.5),
        ("Wildcard", 0, 3.75),
        ("wild", 2, 6.75),
        ("Crysknife", 0, 5.0),  # seat 0's objective is a Crysknife
        ("crysknife", 0, 5.0),
        ("DesertMouse", 0, 2.5),
        ("Ornithopter", 1, 2.5),
    ],
)
def test_battle_icon_value(mk: Builder, icon: str, arc: int, expected: float) -> None:
    assert mk(BASE, arc=arc).battle_icon_value(icon).sum == pytest.approx(expected)


def test_battle_icon_matched_by_intrigue_or_won_conflict(mk: Builder) -> None:
    mouse = with_intrigue(BASE, 0, "desert_mouse")
    assert mk(mouse).battle_icon_value("DesertMouse").sum == pytest.approx(5.0)
    card = "skirmish_ornithopter"
    won = with_state(
        BASE,
        conflict_deck=tuple(c for c in BASE.conflict_deck if c != card),
        unused_conflict_ids=tuple(c for c in BASE.unused_conflict_ids if c != card),
        current_conflict_ids=tuple(c for c in BASE.current_conflict_ids if c != card),
    )
    won = with_player(won, 0, won_conflict_ids=(card,))
    assert mk(won).battle_icon_value("Ornithopter").sum == pytest.approx(5.0)
    # A paired (face-down) card no longer matches.
    paired = with_player(BASE, 0, face_down_battle_card_ids=("objective_crysknife_2",))
    assert mk(paired).battle_icon_value("Crysknife").sum == pytest.approx(2.5)


def test_opponent_maker_hooks_ratio(mk: Builder) -> None:
    assert mk(BASE).opponent_maker_hooks_ratio() == 0.0
    assert mk(hooks(BASE, 1)).opponent_maker_hooks_ratio() == pytest.approx(1 / 3)
    assert mk(hooks(BASE, 1, 3)).opponent_maker_hooks_ratio() == pytest.approx(2 / 3)
    assert mk(hooks(BASE, 1, 2, 3)).opponent_maker_hooks_ratio() == 1.0
    assert mk(hooks(BASE, 0)).opponent_maker_hooks_ratio() == 0.0  # own hooks


@pytest.mark.parametrize(
    ("arc", "holders", "expected"),
    [(0, (), 5.0), (1, (1,), 4.0), (2, (1, 2), 1.5), (0, (1, 2, 3), 1.25)],
)
def test_maker_hooks_value_by_arc_and_opponents(
    mk: Builder, arc: int, holders: tuple[int, ...], expected: float
) -> None:
    assert mk(hooks(BASE, *holders), arc=arc).maker_hooks_value() == pytest.approx(
        expected
    )


def test_maker_hooks_value_intrigues_muad_dib_and_own_hooks(mk: Builder) -> None:
    cards = (
        "detonation",
        "devour",
        "inspire_awe",
        "special_mission",
        "unexpected_allies",
    )
    state = with_intrigue(BASE, 0, *cards)
    expected = 5.0 * 1.3 * 1.1 * 1.1 * 1.2 * 1.1
    assert mk(state).maker_hooks_value() == pytest.approx(expected)
    muad = with_player(BASE, 0, leader_id="muad_dib")
    assert mk(muad).maker_hooks_value() == pytest.approx(5.0 * 1.33)
    assert mk(hooks(muad, 1, 2)).maker_hooks_value() == pytest.approx(5.0 * 0.5)
    assert mk(with_player(BASE, 0, maker_hooks=True)).maker_hooks_value() == 0.0


# =============================================================================
# 7. Agent recall
# =============================================================================


def test_recall_agent_value(mk: Builder) -> None:
    assert mk(BASE).recall_agent_value() == -3.0
    placed = with_player(BASE, 0, agent_locations=("arrakeen",), agents_available=1)
    for arc in (0, 1, 2):
        assert mk(placed, arc=arc).recall_agent_value() == 5.0


def space_values(values: dict[str, float]) -> Callable[[Entity], Summer]:
    return lambda space: Summer(values[space.ref])


def test_recall_agent_prefers_non_faction_non_combat_spaces(mk: Builder) -> None:
    agents = [agent_entity(s, 0) for s in ("arrakeen", "assembly_hall", "secrets")]
    p = mk(
        BASE, space_value_for_player=space_values({"arrakeen": -100.0, "secrets": 0.0})
    )
    assert p.recall_agent(agents) == agent_entity("assembly_hall", 0)


@pytest.mark.parametrize("seed", range(6))
def test_recall_agent_last_shuffled_hundred_wins(mk: Builder, seed: int) -> None:
    agents = [agent_entity(s, 0) for s in ("assembly_hall", "high_council", "shipping")]
    p = mk(BASE, rng_seed=seed)
    order = list(agents)
    random.Random(seed).shuffle(order)
    assert p.recall_agent(agents) == order[-1]


def test_recall_agent_trailing_faction_space_is_75(mk: Builder) -> None:
    agents = [agent_entity("arrakeen", 0), agent_entity("secrets", 0)]
    values = space_values({"arrakeen": -20.0, "secrets": 40.0})
    behind = with_player(BASE, 1, influence=infl(bene_gesserit=2))
    assert mk(behind, space_value_for_player=values).recall_agent(agents) == agents[1]
    # 50 - (-30) = 80 beats 75.
    values = space_values({"arrakeen": -30.0, "secrets": 40.0})
    assert mk(behind, space_value_for_player=values).recall_agent(agents) == agents[0]
    # Gap 1: Secrets falls to 50 - value (10) and loses to Arrakeen (70).
    close = with_player(BASE, 1, influence=infl(bene_gesserit=1))
    values = space_values({"arrakeen": -20.0, "secrets": 40.0})
    assert mk(close, space_value_for_player=values).recall_agent(agents) == agents[0]


def test_recall_agent_combat_faction_space_uses_the_space_value(mk: Builder) -> None:
    agents = [agent_entity("desert_tactics", 0), agent_entity("arrakeen", 0)]
    behind = with_player(BASE, 1, influence=infl(fremen=4))
    values = space_values({"desert_tactics": 10.0, "arrakeen": 20.0})
    assert mk(behind, space_value_for_player=values).recall_agent(agents) == agents[0]
    # Every candidate worth >= 50 on its space: nothing scores above 0.
    values = space_values({"desert_tactics": 50.0, "arrakeen": 60.0})
    assert mk(behind, space_value_for_player=values).recall_agent(agents) is None


def test_space_value_for_player_merges_every_ability(
    mk: Builder, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, tuple[Entity, ...]]] = []

    def fake(value: float) -> type[Ability]:
        class Fake(Ability):
            def value_for_player(
                self, p: Profile, with_entities: Sequence[Entity] = ()
            ) -> Summer:
                seen.append((self.owner.ref, tuple(with_entities)))
                return Summer(value)

        return Fake

    prefix = "worm.canis.abilities."
    monkeypatch.setitem(
        PORTS, prefix + "SpaceAbilities.GainInfluenceAbility", fake(2.0)
    )
    monkeypatch.setitem(
        PORTS, prefix + "SpaceAbilities.BaseSet.SecretsSpaceAbility", fake(1.5)
    )
    monkeypatch.delitem(
        PORTS, prefix + "ActivatedAbilities.AgentGainIntrigueAbility", raising=False
    )
    p = mk(BASE)
    total = p.space_value_for_player(space_entity("secrets", True))
    assert total.sum == pytest.approx(3.5)  # the unported intrigue ability adds 0
    assert seen == [("secrets", ()), ("secrets", ())]


# =============================================================================
# 6. Shield Wall
# =============================================================================


def test_blow_wall_value_needs_hooks(mk: Builder) -> None:
    assert mk(BASE).blow_wall_value().sum == 0.0


def test_blow_wall_value_terms(mk: Builder) -> None:
    state = with_player(BASE, 0, maker_hooks=True, resources=Resources(water=2))
    state = spies_out(state, 0, POST_DEEP)
    can = lambda seat, space: space == "deep_desert"  # noqa: E731
    p = mk(hooks(state, 1), can_play_to_desert_space_with_hooks=can)
    full = 0.0 + 0.66 * 2 + 1.0 + 1.0 + 1.5
    assert p.blow_wall_value().sum == pytest.approx(full * (1.0 - 1 / 3))
    # No reachable desert space, or fewer than 2 Agents left: no +1.
    assert mk(state).blow_wall_value().sum == pytest.approx(full - 1.0)
    one_agent = with_player(state, 0, agents_available=1, agent_locations=("arrakeen",))
    p = mk(one_agent, can_play_to_desert_space_with_hooks=can)
    assert p.blow_wall_value().sum == pytest.approx(full - 1.0)
    # Detonation held with <= 3 garrison troops: x0.33.
    deton = with_intrigue(state, 0, "detonation")
    assert mk(deton).blow_wall_value().sum == pytest.approx((full - 1.0) * 0.33)
    big = with_player(
        deton, 0, troops_garrison=4, troops_supply=BASE.players[0].troops_supply - 1
    )
    assert mk(big).blow_wall_value().sum == pytest.approx(full - 1.0)


def test_should_blow_wall(mk: Builder) -> None:
    assert not mk(BASE).should_blow_wall()  # no hooks
    mine = with_player(BASE, 0, maker_hooks=True)
    assert not mk(with_state(mine, shield_wall_present=False)).should_blow_wall()
    assert mk(mine).should_blow_wall()  # no opponent has hooks
    rivals = hooks(mine, 2)
    assert mk(rivals).should_blow_wall()  # they cannot reach a desert space
    can = lambda seat, space: seat == 2 and space == "hagga_basin"  # noqa: E731
    for interest, expected in ((0.5, True), (1.0, True), (2.0, False)):
        p = mk(
            rivals,
            can_play_to_desert_space_with_hooks=can,
            current_conflict_interest=lambda v=interest: Summer(v),
        )
        assert p.should_blow_wall() is expected


def test_should_blow_wall_reads_interest_before_bounds(mk: Builder) -> None:
    """ShouldBlowWall @0x491dfe0: CurrentConflictInterest (0x491e45e) is
    called before get_ConflictPostureBounds (0x491e475)."""

    calls: list[str] = []

    def interest() -> Summer:
        calls.append("interest")
        return Summer(1.0)

    def bounds() -> tuple[float, float]:
        calls.append("bounds")
        return (1.0, 4.0)

    rivals = hooks(with_player(BASE, 0, maker_hooks=True), 2)
    p = mk(
        rivals,
        can_play_to_desert_space_with_hooks=lambda seat, space: True,
        current_conflict_interest=interest,
        conflict_posture_bounds=bounds,
    )
    assert p.should_blow_wall()  # lower 1.0 >= interest 1.0
    assert calls == ["interest", "bounds"]


def at_desert(
    space: str = "hagga_basin", pending: str = "maker", **seat_changes: object
) -> tuple[GameState, int]:
    state, seat = agent_turn_state({"maker_hooks": True, **seat_changes})
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context.update(space_id=space, pending_board_icons=pending)
    frame = replace(frame, context=tuple(sorted(context.items())))
    return with_state(state, decision_stack=(*state.decision_stack[:-1], frame)), seat


def test_intrigue_blow_wall_is_false_on_uprising_desert_spaces(mk: Builder) -> None:
    state, seat = at_desert()
    # Every gate passes, but neither space has SandWorms/Spice attributes:
    # 0 * worm > 0 * spice is false (the app's behaviour).
    assert not mk(state, seat).intrigue_blow_wall()


def test_intrigue_blow_wall_gates_and_the_final_comparison(
    mk: Builder, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = space_entity

    def with_worm(space_id: str, choam: bool) -> Entity:
        entity = real(space_id, choam)
        assert entity.archetype is not None
        attrs = {**entity.archetype.attributes, "SandWorms": 1, "Spice": 2}
        archetype = Archetype(
            entity.archetype.short,
            entity.archetype.kind,
            entity.archetype.title,
            entity.archetype.in_uprising,
            entity.archetype.in_uprising_choam,
            attrs,
        )
        return replace(entity, archetype=archetype)

    monkeypatch.setattr(influence_module, "space_entity", with_worm)
    state, seat = at_desert()
    # 1 x 3.0 > 2 x 1.1.
    assert mk(state, seat).intrigue_blow_wall()
    assert not mk(
        state, seat, sandworm_value=lambda n, inc=False: 1.0 * n
    ).intrigue_blow_wall()
    # Interest above the upper bound.
    high = mk(state, seat, current_conflict_interest=lambda: Summer(4.5))
    assert not high.intrigue_blow_wall()
    assert mk(
        state, seat, current_conflict_interest=lambda: Summer(4.0)
    ).intrigue_blow_wall()
    # The spice-or-worm choice already made, a non-desert space, no hooks,
    # no wall, or no Agent turn: false.
    assert not mk(*at_desert(pending="")).intrigue_blow_wall()
    assert not mk(*at_desert(space="imperial_basin")).intrigue_blow_wall()
    assert not mk(*at_desert(maker_hooks=False)).intrigue_blow_wall()
    walled = with_state(state, shield_wall_present=False)
    assert not mk(walled, seat).intrigue_blow_wall()
    assert not mk(with_player(BASE, 0, maker_hooks=True)).intrigue_blow_wall()


# =============================================================================
# 8. Leaders
# =============================================================================


def jessica(**changes: object) -> GameState:
    return with_player(BASE, 3, **changes)


def test_lady_jessica_return_memories(mk: Builder) -> None:
    assert not mk(BASE, 0).lady_jessica_return_memories()  # not Jessica
    assert not mk(BASE, 3).lady_jessica_return_memories()  # round 1, nothing
    three = with_intrigue(BASE, 3, "detonation", "devour", "cunning")
    assert mk(three, 3).lady_jessica_return_memories()
    two = with_intrigue(BASE, 3, "detonation", "devour")
    assert not mk(two, 3).lady_jessica_return_memories()
    assert mk(jessica(resources=Resources(water=3)), 3).lady_jessica_return_memories()
    assert not mk(
        jessica(resources=Resources(water=2)), 3
    ).lady_jessica_return_memories()
    supply = BASE.players[3].troops_supply
    memories = jessica(memories=2, troops_supply=supply - 2)
    assert mk(memories, 3).lady_jessica_return_memories()
    one = jessica(memories=1, troops_supply=supply - 1)
    assert not mk(one, 3).lady_jessica_return_memories()
    assert mk(with_state(BASE, round_number=5), 3).lady_jessica_return_memories()
    assert not mk(with_state(BASE, round_number=4), 3).lady_jessica_return_memories()
    flipped = with_player(three, 3, leader_face_id="reverend_mother_jessica")
    assert not mk(flipped, 3).lady_jessica_return_memories()
