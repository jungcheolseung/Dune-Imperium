"""Guard: which Agent-box actions count as a refusal for the turn end.

``agent_effect_frame._REFUSALS`` is every box action whose id starts with
``decline_``: a box that offers only those cannot resolve, so the turn end
fizzles it (OQ-057 (1), codec v144). A new box action named ``decline_*``
that does give an effect would let the end skip a live box, and a refusal
named otherwise would hold the end. This pins the list so a new name has
to be looked at (2026-10-12 review, N3).
"""

from dune_imperium.rules.agent_effect_frame import _REFUSALS

EXPECTED_REFUSALS = frozenset(
    {
        "decline_agent_card_acquisition",
        "decline_agent_card_discard",
        "decline_agent_card_intrigue_payment",
        "decline_agent_card_payment",
        "decline_agent_card_recall",
        "decline_agent_card_spy",
        "decline_agent_card_trash",
        "decline_corrinth_city_payment",
        "decline_leader_card_trash",
        "decline_leader_signet_payment",
        "decline_leader_spy_placement",
    }
)


def test_the_box_refusals_are_exactly_the_reviewed_declines() -> None:
    assert _REFUSALS == EXPECTED_REFUSALS
