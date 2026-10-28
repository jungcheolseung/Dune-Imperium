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
  hand card;
- observation v38 also shows each seat's public markers of the original game,
  ``voice_blocked_space_ids``, ``enemy_agents_ignored_turn`` and
  ``acquire_to_deck_top_round`` (existing ``PlayerState`` fields), which an
  Uprising game never sets: the views gain them at ``[]``, ``False`` and
  ``False``.

Nothing else a player, an agent or a save sees changes: the legal rows, the
events and their payloads stay as they were. The two view differences are
declared as exactly that -- a candidate ``hand_public`` that holds the base's
plus extra cards, and a ``deck_pool`` that lacks exactly those cards'
identities -- so any other change of them is still reported. An extra hand
card is accepted only if that seat's candidate view named it on its public
deck top at this or an earlier step of the game, or the step put a card of
that identity on that seat's deck top (placed and drawn in one transition):
an ordinary hidden draw turned public in any game is still a difference, and
``PlayerState.hand_public`` is left out of the state comparison only for a
seat that has had a public deck top in this game: a chance step records no
views to check the hand card by, and the next step with views checks it
card by card (independent review of observation v38, 2026-10-28). Checked with
``engine_equivalence.py check --differences
scripts/ab/differences/public_deck_tops.py``.
"""

from equivalence_rules import Rule, Step

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance

# The fields the views gain, at their Uprising values.
_NEW_VIEW_FIELDS = (
    ("deck_public_top", []),
    ("voice_blocked_space_ids", []),
    ("enemy_agents_ignored_turn", False),
    ("acquire_to_deck_top_round", False),
)


def _add_new_fields(step: Step) -> bool:
    """Show the base's views the new fields at their defaults; whether any
    seat was missing one."""

    shown = False
    for view in step.views:
        for seat in view["players"]:
            for name, default in _NEW_VIEW_FIELDS:
                if name not in seat:
                    seat[name] = list(default) if isinstance(default, list) else default
                    shown = True
    return shown


def _identity(instance_id: str) -> str:
    return personal_card_for_instance(instance_id).card.card_id


# Per game (a lower step index starts another): the instances each seat's
# candidate view has named on its public deck top so far, and the seats that
# have had a public deck top (their ``hand_public`` may differ from here on).
_seen_on_top: dict[int, set[str]] = {}
_had_public_top: set[int] = set()
_last_index = [-1]


def _placed_identities(candidate: Step) -> dict[int, set[str]]:
    """The card identities this step put on a seat's deck top, by seat."""

    placed: dict[int, set[str]] = {}
    for event in candidate.events:
        payload = dict(event["payload"])
        on_top = (
            event["kind"] == "card_acquired"
            and payload.get("destination") == "deck_top"
        ) or (event["kind"] == "tleilaxu_card_acquired" and payload.get("to_deck_top"))
        if on_top:
            placed.setdefault(int(payload["player"]), set()).add(
                str(payload["card_id"])
            )
    return placed


def _normalise_public_top(old: Step, candidate: Step) -> bool:
    """Take the declared difference out of the candidate's views: the record
    itself, the cards drawn from it in ``hand_public``, and their identities
    in ``deck_pool``. Whatever else differs is left to be reported."""

    if candidate.index < _last_index[0]:
        _seen_on_top.clear()
        _had_public_top.clear()
    _last_index[0] = candidate.index
    for view in candidate.views:
        for seat, new_seat in enumerate(view["players"]):
            _seen_on_top.setdefault(seat, set()).update(
                new_seat.get("deck_public_top", [])
            )
    placed = _placed_identities(candidate)
    _had_public_top.update(seat for seat, seen in _seen_on_top.items() if seen)
    _had_public_top.update(placed)
    candidate.fields_unchecked.update(
        f"players[{seat}].hand_public" for seat in _had_public_top
    )
    changed = False
    for old_view, new_view in zip(old.views, candidate.views, strict=False):
        for seat, (old_seat, new_seat) in enumerate(
            zip(old_view["players"], new_view["players"], strict=False)
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
            if not all(
                card in _seen_on_top.get(seat, set())
                or _identity(card) in placed.get(seat, set())
                for card in extra
            ):
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
    old=_add_new_fields,
    new=_normalise_public_top,
)

STATE_HOLDS_THE_PUBLIC_TOP = Rule(
    name="state_holds_the_public_top",
    why="OQ-145: the record of the deck's public top and the public hand "
    "cards drawn from it",
    # The new field everywhere; ``hand_public`` only where
    # ``_normalise_public_top`` accepted a card drawn from the public top.
    state_fields=frozenset({"PlayerState.deck_public_top"}),
)

RULES = (STATE_HOLDS_THE_PUBLIC_TOP, VIEWS_SHOW_THE_PUBLIC_TOP)
