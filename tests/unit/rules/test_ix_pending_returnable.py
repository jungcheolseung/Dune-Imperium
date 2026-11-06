"""The returnable Negotiators an open Ix Tech acquisition shows are counted
from the state each time (Codex review of 82b2bf2e).

docs/rules/rise-of-ix.md 4, `[Rise of Ix p. 4]`: "나중에 Acquire Tech 때 원하는
만큼("any number") Negotiator를 supply로 돌려 하나에 spice 1씩 깎는다". Two
Acquire Tech icons stack two acquisitions; Negotiators spent in the upper one
are gone when the lower one opens, and ``ix_pending_of`` (plan 17.8 item 4)
must say so.
"""

from tests.unit.rules.test_ix_tech_acquisition import _buy, _holding, _open

from dune_imperium.core.observation import ix_pending_of
from dune_imperium.rules import tech as tech_rules


def test_a_stacked_acquisition_shows_the_negotiators_left_now() -> None:
    _, state = _holding(spice=10, negotiators=3)
    both = _open(_open(state))
    assert ix_pending_of(both, 0).negotiators_returnable == 3
    bought = tech_rules.apply_tech_acquisition(
        both, _buy("holtzman_engine", negotiators=3)
    ).state
    assert bought.players[0].negotiators == 0
    assert ix_pending_of(bought, 0).tech_payment == "spice"
    assert ix_pending_of(bought, 0).negotiators_returnable == 0


def test_the_count_follows_the_tiles_now_face_up() -> None:
    """A Negotiator beyond the dearest face-up price lowers nothing: after
    the dear tile is taken, the cap is the next dearest price."""

    _, state = _holding(spice=10, negotiators=5)
    both = _open(_open(state))
    assert ix_pending_of(both, 0).negotiators_returnable == 5
    bought = tech_rules.apply_tech_acquisition(both, _buy("holtzman_engine")).state
    # Holtzman Engine (6) taken: Invasion Ships (5) is face up in its stack.
    assert ix_pending_of(bought, 0).negotiators_returnable == 5
    _, poor = _holding(spice=10, negotiators=5, stacks=(("minimic_film",),))
    assert ix_pending_of(_open(poor, discount=1), 0).negotiators_returnable == 1
