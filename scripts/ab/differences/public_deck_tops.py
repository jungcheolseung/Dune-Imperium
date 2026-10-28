"""Declared differences of OQ-145 (cards put face up on top of a deck are
public) against ``ed6a77c1`` (codec v155, observation v37).

docs/rules/open-questions.md OQ-145, user ruling 2026-10-28: a card put face
up on top of a deck -- the original game's Bypass Protocol and Recruitment
Mission and Immortality's Tleilaxu deck-top placement -- is known to every
seat until it is drawn or the deck is shuffled, and stays public in the hand
once drawn (``hand_public``, OQ-010 ruling 1). An Uprising game with
Immortality therefore changes, once a seat puts a Tleilaxu card on top of its
deck (after its first genetic marker):

- ``PlayerState`` gains ``deck_public_top`` (hash-omitted at its default) and
  ``hand_public`` takes the cards drawn from the public top, so both are
  declared changed in the state digests;
- every seat's ``PublicPlayerView`` gains ``deck_public_top``; the views'
  ``hand_public`` lists the cards drawn from it, and ``deck_pool`` (the deck
  and the hidden hand, by identity) leaves them out as it does every public
  hand card.

Nothing else a player, an agent or a save sees changes: the legal rows, the
events and their payloads stay as they were. The two view differences are
declared as exactly that -- a candidate ``hand_public`` that holds the base's
plus extra cards, and a ``deck_pool`` that lacks exactly those cards'
identities -- so any other change of them is still reported. Checked with
``engine_equivalence.py check --differences
scripts/ab/differences/public_deck_tops.py``.
"""

from equivalence_rules import Rule, Step

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance


def _add_empty_top(step: Step) -> bool:
    """Show the base's views the new field at its default; whether any seat
    was missing it."""

    shown = False
    for view in step.views:
        for seat in view["players"]:
            if "deck_public_top" not in seat:
                seat["deck_public_top"] = []
                shown = True
    return shown


def _identity(instance_id: str) -> str:
    return personal_card_for_instance(instance_id).card.card_id


def _normalise_public_top(old: Step, candidate: Step) -> bool:
    """Take the declared difference out of the candidate's views: the record
    itself, the cards drawn from it in ``hand_public``, and their identities
    in ``deck_pool``. Whatever else differs is left to be reported."""

    changed = False
    for old_view, new_view in zip(old.views, candidate.views, strict=False):
        for old_seat, new_seat in zip(
            old_view["players"], new_view["players"], strict=False
        ):
            if new_seat.get("deck_public_top"):
                new_seat["deck_public_top"] = []
                changed = True
            extra = [
                card
                for card in new_seat.get("hand_public", [])
                if card not in old_seat.get("hand_public", [])
            ]
            if not extra:
                continue
            rest = [card for card in new_seat["hand_public"] if card not in extra]
            if rest != old_seat["hand_public"]:
                continue
            pool = sorted([*new_seat["deck_pool"], *(_identity(c) for c in extra)])
            if pool != old_seat["deck_pool"]:
                continue
            new_seat["hand_public"] = rest
            new_seat["deck_pool"] = pool
            changed = True
    return changed


VIEWS_SHOW_THE_PUBLIC_TOP = Rule(
    name="views_show_the_public_top",
    why="OQ-145: every seat's view names the deck's public top cards and the "
    "cards drawn from it stay public in the hand",
    old=_add_empty_top,
    new=_normalise_public_top,
)

STATE_HOLDS_THE_PUBLIC_TOP = Rule(
    name="state_holds_the_public_top",
    why="OQ-145: the record of the deck's public top and the public hand "
    "cards drawn from it",
    state_fields=frozenset({"PlayerState.deck_public_top", "PlayerState.hand_public"}),
)

RULES = (STATE_HOLDS_THE_PUBLIC_TOP, VIEWS_SHOW_THE_PUBLIC_TOP)
