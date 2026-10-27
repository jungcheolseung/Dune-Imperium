"""English detail text for legal actions that resolve one printed icon.

The play server attaches this to each legal action so the browser can show
which printed effect a keyed resolution (``resolve_board_effect`` /
``resolve_agent_card_effect`` with an ``effect`` argument) stands for, or
what a payment shared by several Agent boxes buys on the card resolving
(``_PAYMENT_TEXT``). A whole Agent box -- the argument-less
``resolve_agent_card_effect`` -- is described by that card's box text
(``display.cards.agent_box_text``), and every Agent-box row is led by the
card it works on (``agent_box_row_title``): the page shows that pair as the
button itself (user request 2026-10-11: "그냥 선택지에 카드 효과가 바로
보여지는게 낫지 않나?"). A grafted turn offers both cards' boxes (box 1's rows
carry ``box=1``, codec v143); each row is read with its own box active
(``rules.agent_effect_frame.route_box_action``), as the engine resolves it.
The decision panel groups the rows under a header per card
(``agent_box_of_rows``, ``agent_box_headers``; docs/graft-boxes-plan.md
4.11). A Reveal's card choices are rows of the Reveal frame (codec v147),
grouped the same way under a header per revealed card
(``reveal_choice_of_rows``, ``reveal_choice_headers``). It is derived from
the same engine tables and card data the rules execute.
"""

import re
from copy import replace

from dune_imperium.content.bloodlines.sardaukar import SKILLS_BY_ID
from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    LoseInfluence,
    RecruitTroops,
    Reward,
    TakeContract,
)
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_is_optional,
)
from dune_imperium.content.uprising.types import (
    PersonalCardAgentEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.display.cards import agent_box_text, agent_box_text_ko
from dune_imperium.display.effect_dsl_text import reward_text, section_text
from dune_imperium.display.effect_dsl_text_ko import reward_text_ko, section_text_ko
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.display.scouts import scouts_action_text
from dune_imperium.display.spaces import (
    board_effect_action_text,
    board_effect_action_text_ko,
)
from dune_imperium.display.tokens import REVEAL_CHOICE_EFFECT_TEXT
from dune_imperium.display.tokens_ko import REVEAL_CHOICE_EFFECT_TEXT_KO
from dune_imperium.rules.agent_effect_frame import agent_box_rows, route_box_action
from dune_imperium.rules.agent_effects import (
    boost_draw_card,
    box_in_progress,
    resolves_boost_draw,
)
from dune_imperium.rules.agent_turn import CARD_PICK_ACTION, executable_placements
from dune_imperium.rules.combat import (
    REWARD_ICON_ACTION,
    WINNING_INTRIGUE,
    reward_icon_piece,
)
from dune_imperium.rules.contracts import (
    CONTRACT_REWARD_ICON_ACTION,
    contract_icon_piece,
)
from dune_imperium.rules.effect_steps import owed_origin_printer, whole_printer
from dune_imperium.rules.effects import (
    active_agent_card,
    current_agent_effect_context,
)
from dune_imperium.rules.frames import FrameKind, owned_top_frame
from dune_imperium.rules.graft_boxes import (
    active_box,
    box_card_id,
    box_is_pending,
    is_grafted_turn,
    row_box,
    tagged,
    untagged,
)
from dune_imperium.rules.intrigue import current_intrigue_choice_slot
from dune_imperium.rules.owed_draws import next_owed_draw
from dune_imperium.rules.reveal_turn import pending_choice_entries, reveal_gain_source

_BOX = PersonalCardAgentEffect
# The card whose added Agent-box draw ``resolves_boost_draw`` names, by its
# Korean print in Korean text (``names_ko``).
_SHIGAWIRE = "Urgent Shigawire"
# Piter, Genius Advisor's reward icons, armed after its troop cost (OQ-106):
# its card draw draws two and its Research generates no specimen.
_PITER = _BOX.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH
_SHIGAWIRE_KO = KOREAN_CARD_NAMES["cards"]["urgent_shigawire"]

# Printed conditions of the multi-icon Agent boxes, judged when the icon
# resolves (OQ-027); shown after the icon's effect.
_ICON_CONDITIONS: dict[tuple[PersonalCardAgentEffect, str], str] = {
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "troops"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "cards"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "water"): (
        "at 2 Bene Gesserit Influence"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "spice"): (
        "at 2 Fremen Influence"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "solari"): (
        "at 2 Emperor Influence"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "spice"): (
        "at 2 Spacing Guild Influence"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "troops"): (
        "if you gained 2 or more spice this turn"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "cards"): (
        "if you gained 2 or more spice this turn"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards"): (
        "if you have completed 2 or more contracts"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards_second"): (
        "if you have completed 4 or more contracts"
    ),
    (_BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND, "cards"): (
        "if you have another Bene Gesserit card in play"
    ),
    (_BOX.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED, "research"): "if grafted",
    (_BOX.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE, "return_self"): (
        "with the Fremen Alliance"
    ),
    # Only Lady Amber Metulli's Signet (Fill Coffers) prints icons.
    (_BOX.LEADER_SIGNET, "spice"): "if you have an Alliance",
}

# Korean twin of _ICON_CONDITIONS. The Influence-count suffixes use a
# *counted* {term:count} placeholder ("at 2 Bene Gesserit Influence" has the
# digit directly before "Bene Gesserit Influence", the exact adjacency
# render.js's ICON_RULES needs to draw a counted icon in English, unlike a
# "2 or more X Influence" threshold, which draws a bare one — see
# tokens_ko.py's module docstring). The spice-this-turn condition is that
# threshold shape (bare {spice} + a plain digit), matching the identical
# "이번 차례에 {spice}를 2 이상 얻었다면" phrasing tokens_ko.py's
# RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN entry already uses
# for the same condition as an "If ...:" prefix; here it is a parenthetical
# suffix instead, matching English's own parenthetical placement.
_ICON_CONDITIONS_KO: dict[tuple[PersonalCardAgentEffect, str], str] = {
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "troops"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO, "cards"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "water"): (
        "{influence_bene_gesserit:2}일 때"
    ),
    (_BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO, "spice"): (
        "{influence_fremen:2}일 때"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "solari"): (
        "{influence_emperor:2}일 때"
    ),
    (_BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO, "spice"): (
        "{influence_spacing_guild:2}일 때"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "troops"): (
        "이번 차례에 {spice}를 2 이상 얻었다면"
    ),
    (_BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN, "cards"): (
        "이번 차례에 {spice}를 2 이상 얻었다면"
    ),
    # Cargo Runner's lines, in tokens_ko.py's own words for the same box.
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards"): (
        "{contract} 둘 이상 완수했다면"
    ),
    (_BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO, "cards_second"): (
        "{contract} 넷 이상 완수했다면"
    ),
    # Tread in Darkness, in tokens_ko.py's words for the same box.
    (_BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND, "cards"): (
        "당신의 {in_play}에 다른 베네 게세리트 카드가 있다면"
    ),
    (_BOX.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED, "research"): "{graft}했다면",
    (_BOX.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE, "return_self"): (
        "프레멘 {alliance}이면"
    ),
    (_BOX.LEADER_SIGNET, "spice"): "{alliance}이 있다면",
}


# Payments whose action id several Agent boxes share. ``pay_agent_card_spice``
# pays Smuggler's Haven's 4 spice for a Victory Point and, in Epic Game Mode,
# Control the Spice's 1 spice to trash a card and recruit a troop, the trash
# still optional after paying [FAQ p. 3] (docs/rules/epic-game-mode.md 6).
# The client's label only says a card effect's cost is paid (it is all the
# action log has); on the buttons this detail replaces it (static/core.js
# describeAction). English is card wording for iconize(), in the printed
# order; Korean keeps tokens_ko.py's words for the same boxes and labels.js's
# "{trash} (선택)".
_PAYMENT_TEXT: dict[tuple[str, PersonalCardAgentEffect], tuple[str, str]] = {
    ("pay_agent_card_spice", _BOX.MAY_PAY_FOUR_SPICE_FOR_VP): (
        "Pay 4 spice → Gain 1 VP",
        "{spice:4} 지불 {arrow_right} {victory_point:1}",
    ),
    ("pay_agent_card_spice", _BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT): (
        "Pay 1 spice → Trash a card (optional) + Recruit 1 troop",
        "{spice:1} 지불 {arrow_right} {trash} (선택) + {troop:1}",
    ),
}
_PAYMENT_ACTION_IDS = frozenset(action_id for action_id, _ in _PAYMENT_TEXT)


def agent_card_payment_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Name what a shared Agent-box payment buys on the resolving card.

    Returns the English and Korean text, or None when the action is no such
    payment.
    """

    if untagged(action).action_id not in _PAYMENT_ACTION_IDS:
        return None
    state, action, _ = route_box_action(state, action)
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        return None
    # The box resolving, a Ghola's borrowed one included (the engine's own
    # payment choice reads it the same way).
    effect = active_agent_card(context).agent_effect
    if effect is None:
        return None
    return _PAYMENT_TEXT.get((action.action_id, effect))


def agent_card_icon_text(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Render one printed Agent-box icon of a multi-icon card."""

    match key:
        case "cards" | "cards_second":
            base = "Draw 2 cards" if effect is _PITER else "Draw 1 card"
        case "intrigue":
            base = "Draw 1 Intrigue card"
        case "troops":
            base = "Recruit 1 troop"
        case "solari":
            # Fill Coffers (the Signet Ring's box) pays 1.
            base = (
                "Gain 1 solari" if effect is _BOX.LEADER_SIGNET else "Gain 2 solari"
            )
        case "spice":
            base = (
                "Gain 2 spice"
                if effect
                is (
                    _BOX
                    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
                )
                else "Gain 1 spice"
            )
        case "water":
            base = "Gain 1 water"
        case "research":
            base = "Research" if effect is _PITER else "Research, Generate 1 specimen"
        case "return_self":
            base = "Return this card from play to your hand"
        case "trash_self":
            base = "Trash this card"
        case "pledge":
            base = (
                "Add 1 Influence of your choice to this Conflict's"
                " first-place reward"
            )
        case _:
            raise KeyError(key)
    condition = _ICON_CONDITIONS.get((effect, key)) if effect is not None else None
    return f"{base} ({condition})" if condition else base


def agent_card_icon_text_ko(effect: PersonalCardAgentEffect | None, key: str) -> str:
    """Korean twin of ``agent_card_icon_text``.

    Every ``base`` case mirrors an English wording ``ICON_RULES``
    (``static/render.js``) draws a counted icon for ("Draw 1 card", "Recruit
    1 troop", "Gain 2 solari", …), so each becomes the matching
    ``{term:count}``. "trash_self" reuses this project's own established
    Korean for the same concept: ``labels.js`` ``EFFECT_ICON_LABELS``
    ``trash_self``: "이 카드 폐기" (that table is the Korean *fallback*
    label for this key when ``detail`` is null; this function supplies the
    real ``detail_ko``, so the wording matches on purpose rather than by
    coincidence). Its trash is the word, not the ``{trash}`` icon: that
    icon means "Trash one card" ([Main p. 20], glossary-ko.md "카드 동작"),
    and beside "이 카드" it read as a second effect (user, 2026-10-11:
    one rulebook icon per effect). "pledge" instead uses
    ``docs/rules/glossary-ko.md``'s own
    "first / second / third place | 1등 / 2등 / 3등 칸 | `[Main p. 14]`" —
    not ``labels.js``'s ``pledge``/``first_place_influence_pledged``, which
    say "1위" (a pre-existing mismatch noted for a separate fix, 2026-09-25
    review); Pivotal Gambit's own popover line (this module's
    ``tokens_ko.py`` twin) already reads "1등 보상에", so this function
    matches it rather than the other, wronger, precedent.
    """

    match key:
        case "cards" | "cards_second":
            base = "{draw:2}" if effect is _PITER else "{draw:1}"
        case "intrigue":
            base = "{intrigue:1}"
        case "troops":
            base = "{troop:1}"
        case "solari":
            base = "{solari:1}" if effect is _BOX.LEADER_SIGNET else "{solari:2}"
        case "spice":
            base = (
                "{spice:2}"
                if effect
                is (
                    _BOX
                    .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
                )
                else "{spice:1}"
            )
        case "water":
            base = "{water:1}"
        case "research":
            # tokens_ko.py's words for Industrial Espionage's line.
            base = "{research}" if effect is _PITER else "{research}, 표본 1개 생성"
        case "return_self":
            # tokens_ko.py's words for Stillsuit Manufacturer's return.
            base = "{in_play}에서 이 카드를 핸드로 되돌림"
        case "trash_self":
            base = "이 카드 폐기"
        case "pledge":
            base = "1등 보상에 {influence_any} 선택 추가"
        case _:
            raise KeyError(key)
    condition = _ICON_CONDITIONS_KO.get((effect, key)) if effect is not None else None
    return f"{base} ({condition})" if condition else base


_RESOLVE_BOX = "resolve_agent_card_effect"

# A card's printed Korean twin (``tokens_ko.AGENT_EFFECT_TEXT_KO``) keeps the
# icons the card prints, such as Seek Allies' trash icon after "이 카드".
# On a button one rulebook icon stands for one whole effect (user,
# 2026-10-11; tests/server/test_label_icons.py): the trash and discard
# icons already mean "a card", so beside the word 카드 the verb is a word.
_CARD_VERB_ICON_KO = re.compile(r"(카드를?(?: \d+장)?) \{(trash|discard)\}")
_CARD_VERB_WORDS_KO = {"trash": "폐기", "discard": "버리기"}


def _one_icon_per_effect_ko(text: str) -> str:
    """``text`` with a card's trash or discard written as the word."""

    return _CARD_VERB_ICON_KO.sub(
        lambda match: f"{match.group(1)} {_CARD_VERB_WORDS_KO[match.group(2)]}",
        text,
    )


def _effect_frame_context(state: GameState) -> dict[str, ActionValue] | None:
    """The Agent-turn effect frame's context while it decides, else None."""

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        return None
    return context


def _card_names(card_id: str) -> tuple[str, str]:
    """A personal card's English name and its Korean print name."""

    card = personal_card_for_instance(card_id).card
    return card.name, KOREAN_CARD_NAMES["cards"].get(card.card_id, card.name)


def agent_box_text_for_action(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """What a whole Agent box does, for the row that resolves it.

    The argument-less ``resolve_agent_card_effect`` resolves its box's card
    (a Ghola's borrowed one included, as the engine reads it), box 1's with
    ``box=1``. English and Korean, or None for any other row.
    """

    if untagged(action) != DomainAction(_RESOLVE_BOX, action.actor):
        return None
    state, action, _ = route_box_action(state, action)
    context = _effect_frame_context(state)
    if context is None:
        return None
    entry = active_agent_card(context)
    text, text_ko = agent_box_text(entry), agent_box_text_ko(entry)
    if text is None or text_ko is None:
        return None
    return text, _one_icon_per_effect_ko(text_ko)


def agent_box_row_title(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """The card an Agent-box row works on, which leads its button.

    A box resolution or one of its icons names its box's card; on a grafted
    turn every row of either box does (box 1's carry ``box=1``), so the two
    cards' rows tell apart. Urgent Shigawire's added draw names the card it
    was added to. English and Korean (card names stay plain text), or None
    for any other row.
    """

    view, plain, box = route_box_action(state, action)
    context = _effect_frame_context(view)
    if context is None:
        return None
    if plain.action_id != _RESOLVE_BOX:
        if box is None or not is_grafted_turn(context):
            return None
        return _card_names(str(context["card_id"]))
    card_id = str(context["card_id"])
    if box is None and plain.arguments and resolves_boost_draw(view, plain):
        card_id = boost_draw_card(context, row_box(plain)) or card_id
    return _card_names(card_id)


def _own_effect_frame_context(
    state: GameState, seat: int
) -> dict[str, ActionValue] | None:
    """The open Agent turn's effect frame context while ``seat`` decides it."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != seat:
        return None
    return context


def agent_box_of_rows(
    state: GameState, seat: int, actions: tuple[DomainAction, ...]
) -> tuple[int | None, ...]:
    """The Agent box each of ``seat``'s legal rows belongs to, in order.

    0 for the placed card's box, 1 for its graft partner's (codec v143,
    ``agent_effect_frame.agent_box_rows``: box 1's rows carry ``box=1``),
    None for any other row: the space's effects, Urgent Shigawire's added
    draw, an Intrigue play, a deployment, the turn's end. Only while
    ``seat`` decides the Agent turn's own effect frame; every row is None
    otherwise. The decision panel groups the rows by it under a header per
    card (user request 2026-10-11, docs/graft-boxes-plan.md 4.11). Public:
    both cards lie face up in play.
    """

    if _own_effect_frame_context(state, seat) is None:
        return (None,) * len(actions)
    box_zero, box_one = agent_box_rows(state, seat)
    zero = frozenset(box_zero)
    one = frozenset(tagged(action, 1) for action in box_one)
    return tuple(
        0 if action in zero else 1 if action in one else None for action in actions
    )


def agent_box_headers(state: GameState, seat: int) -> list[dict[str, object]] | None:
    """The open Agent turn's boxes, for the decision panel's card headers.

    None unless ``seat`` decides the Agent turn's effect frame. Otherwise
    one entry per box, box 0 (the placed card) first, then box 1 on a
    grafted turn (its partner): ``box``, ``card_id``, the card's English
    ``name`` and Korean ``name_ko`` (a Ghola's own name, whatever box it
    copies), and ``locked``: the box still waits but its rows are not
    offered because the other box is part way through one bundled
    selection (``agent_effects.box_in_progress``, user decision
    2026-10-12, docs/graft-boxes-plan.md 4.3). Public: both cards lie face
    up in play, and each box's resolution is announced as it happens.
    """

    context = _own_effect_frame_context(state, seat)
    if context is None:
        return None
    grafted = is_grafted_turn(context)
    locked = grafted and box_in_progress(state)
    current = active_box(context)
    headers: list[dict[str, object]] = []
    for box in (0, 1) if grafted else (0,):
        card_id = box_card_id(context, box)
        if not card_id:
            continue
        name, name_ko = _card_names(card_id)
        headers.append(
            {
                "box": box,
                "card_id": card_id,
                "name": name,
                "name_ko": name_ko,
                "locked": locked and box != current and box_is_pending(context, box),
            }
        )
    return headers


# --- The Reveal's card choices ------------------------------------------------
#
# Every choice effect of a revealed card waits on the Reveal frame and is
# offered there beside the purchases, gains and Plots, in any order (codec
# v147; OQ-095 (7) addition, user ruling 2026-10-14; [Main p. 12]). The
# decision panel sets each pending choice's rows under a header naming its
# card and what the choice does, as it does an Agent turn's boxes, so no row
# has to name its card itself (the shared ids name it with ``source``, a
# definition id the page never prints).

# The never-legal row that stands for a pending choice offering nothing now
# (``reveal_turn.waiting_choice_action``), greyed out with its reason.
WAITING_REVEAL_CHOICE = "resume_reveal_choice"


def reveal_choice_key(card_id: str, effect: str) -> str:
    """One pending Reveal choice: its revealed card instance and effect."""

    return f"{card_id}:{effect}"


def reveal_choice_text(effect: str) -> tuple[str, str]:
    """What one Reveal choice does, in the card's own words.

    English for ``iconize`` and Korean with ``{term}`` tokens
    (``display.tokens`` / ``display.tokens_ko``, the card popover's lines),
    a card's trash written as the word as on a button.
    """

    choice = PersonalCardRevealChoiceEffect(effect)
    return (
        REVEAL_CHOICE_EFFECT_TEXT[choice],
        _one_icon_per_effect_ko(REVEAL_CHOICE_EFFECT_TEXT_KO[choice]),
    )


def reveal_card_names(card_id: str) -> tuple[str, str]:
    """A revealed card's English name and its Korean print name."""

    return _card_names(card_id)


def reveal_choice_headers(
    state: GameState, seat: int
) -> list[dict[str, object]] | None:
    """The pending choices of ``seat``'s open Reveal, for the panel's headers.

    None unless ``seat``'s Reveal frame is on top, or when nothing is
    pending. Otherwise one entry per pending choice in pending order (the
    order the engine resolves a shared row in): ``key``
    (``reveal_choice_key``), ``card_id``, the card's English ``name`` and
    Korean ``name_ko``, ``effect``, what it does (``text``/``text_ko``,
    ``reveal_choice_text``), ``optional`` (it offers no refusal and lapses
    unused when the Reveal ends; its record's mark,
    ``reveal_choice_abilities``) and ``offered`` (it offers a row now; one
    that does not is a greyed-out waiting row, ``display.unavailable``).
    Public: the Reveal lays the hand face up, and only the seat itself is
    sent its own decision's rows.
    """

    entries = pending_choice_entries(state, seat)
    if not entries:
        return None
    headers: list[dict[str, object]] = []
    for (card_id, effect), rows in entries:
        name, name_ko = _card_names(card_id)
        text, text_ko = reveal_choice_text(effect)
        headers.append(
            {
                "key": reveal_choice_key(card_id, effect),
                "card_id": card_id,
                "name": name,
                "name_ko": name_ko,
                "effect": effect,
                "text": text,
                "text_ko": text_ko,
                "optional": reveal_choice_is_optional(
                    PersonalCardRevealChoiceEffect(effect)
                ),
                "offered": bool(rows),
            }
        )
    return headers


def reveal_choice_of_rows(
    state: GameState, seat: int, actions: tuple[DomainAction, ...]
) -> tuple[str | None, ...]:
    """The pending Reveal choice each of ``seat``'s legal rows takes, in order.

    The first pending entry that offers the row, as the engine opens it
    (``reveal_turn._open_pending``): two copies of one card offer one row
    once, and it takes the older copy's choice. None for any other row (a
    purchase, a gain, a Plot), and for every row unless ``seat``'s Reveal
    frame is on top.
    """

    owner: dict[DomainAction, str] = {}
    for (card_id, effect), rows in pending_choice_entries(state, seat) or ():
        for action in rows:
            owner.setdefault(action, reveal_choice_key(card_id, effect))
    return tuple(owner.get(action) for action in actions)


_RESEARCH_ICON_TEXT: dict[str, tuple[str, str]] = {
    "specimen": ("Gain 1 specimen", "{specimen}"),
    "tleilaxu": ("Advance on the Tleilaxu track", "{tleilaxu}"),
    "trash": ("Trash a card (optional)", "{trash} (선택)"),
    "intrigue": ("Draw 1 Intrigue card", "{intrigue:1}"),
    "cards": ("Draw 1 card", "{draw:1}"),
}


def research_icon_action_text(action: DomainAction) -> tuple[str, str] | None:
    """Describe one icon of a research space's pair or of c7r3's rewards
    (``resolve_research_icon``, cleanup-2b)."""

    if action.action_id != "resolve_research_icon":
        return None
    return _RESEARCH_ICON_TEXT[str(dict(action.arguments)["effect"])]


def combat_reward_icon_action_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Describe one icon of a Conflict reward recipient's window
    (``resolve_combat_reward_icon``, stage B2): the record piece that prints
    it, with a sandworm's double on an automatic icon's amount."""

    if action.action_id != REWARD_ICON_ACTION:
        return None
    frame = owned_top_frame(state, FrameKind.COMBAT_REWARD_ICONS, action.actor)
    if frame is None or not state.current_conflict_ids:
        return None
    context = dict(frame.context)
    rank = context["rank"]
    multiplier = context["multiplier"]
    assert isinstance(rank, int) and isinstance(multiplier, int)
    kind = str(dict(action.arguments)["effect"])
    if kind == "planetary_array":
        # Planetary Array's "When you win a Conflict: draw a card", a row of
        # the winner's window (OQ-121); never doubled by a sandworm.
        draw = DrawPersonalCards(count=1)
        return (
            f"{_PLANETARY_ARRAY}: {reward_text(draw)}",
            f"{_PLANETARY_ARRAY_KO}: {reward_text_ko(draw)}",
        )
    if kind == WINNING_INTRIGUE:
        # The sole winner's close of its window once every other row is
        # resolved: no more "When you win a Conflict" Intrigue (OQ-121
        # decision 6, "안 내도 창이 닫힌다").
        return (
            "Finish: no more winning Intrigue",
            "승리 {intrigue} 끝내기",
        )
    piece = reward_icon_piece(state.current_conflict_ids[-1], rank, kind)
    match piece:
        case EffectSection():
            return section_text(piece), section_text_ko(piece)
        case None:
            # Pivotal Gambit's pledged Influence, which no record prints.
            pledged = GainInfluence()
            return reward_text(pledged), reward_text_ko(pledged)
        case TakeContract(count=count) if not state.config.choam_module:
            # Without the CHOAM Module a Contract icon is 2 Solari
            # [Main pp. 16, 20].
            solari = GainResources(solari=2 * count * multiplier)
            return reward_text(solari), reward_text_ko(solari)
    scaled = _scaled_reward(piece, multiplier)
    return reward_text(scaled), reward_text_ko(scaled)


def contract_reward_icon_action_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Describe one icon of a completed Contract's reward
    (``resolve_contract_reward_icon``): a row of its window (stage B2) or a
    row waiting on its owner's turn, which names the Contract (stage B3b,
    OQ-112 (4)); the record piece that prints it."""

    if action.action_id != CONTRACT_REWARD_ICON_ACTION:
        return None
    arguments = dict(action.arguments)
    if "contract_id" in arguments:
        instance_id = str(arguments["contract_id"])
    else:
        frame = owned_top_frame(state, FrameKind.CONTRACT_REWARD_ICONS, action.actor)
        if frame is None:
            return None
        instance_id = str(dict(frame.context)["contract_id"])
    piece = contract_icon_piece(instance_id, str(arguments["effect"]))
    return reward_text(piece), reward_text_ko(piece)


def _scaled_reward(piece: Reward, multiplier: int) -> Reward:
    """An automatic icon's piece with a sandworm's double on its amount."""

    if multiplier == 1:
        return piece
    match piece:
        case GainResources(solari=solari, spice=spice, water=water):
            return GainResources(
                solari=solari * multiplier,
                spice=spice * multiplier,
                water=water * multiplier,
            )
        case DrawIntrigueCards(count=count):
            return DrawIntrigueCards(count=count * multiplier)
        case RecruitTroops(count=count):
            return replace(piece, count=count * multiplier)
        case TakeContract(count=count):
            return replace(piece, count=count * multiplier)
        case GainVictoryPoints(amount=amount):
            return replace(piece, amount=amount * multiplier)
        case GainInfluence(times=times, factions=(_,)):
            return replace(piece, times=times * multiplier)
    return piece


def tech_acquire_action_text(action: DomainAction) -> tuple[str, str] | None:
    """Describe one queued Tech reward and its currently chosen branch."""

    if action.action_id != "resolve_tech_acquire_effect":
        return None
    args = dict(action.arguments)
    tile = TECH_TILES_BY_ID[str(args["tech_id"])]
    effect = str(args["effect"])
    match effect:
        case "solari":
            return (
                f"Gain {tile.acquire_solari} solari",
                f"{{solari:{tile.acquire_solari}}}",
            )
        case "troops":
            return (
                f"Recruit {tile.acquire_troops} troops",
                f"{{troop:{tile.acquire_troops}}}",
            )
        case "intrigue":
            count = tile.acquire_intrigue
            return f"Draw {count} Intrigue cards", f"{{intrigue:{count}}}"
        case "cards":
            return f"Draw {tile.acquire_cards} cards", f"{{draw:{tile.acquire_cards}}}"
        case "victory_points":
            count = tile.acquire_victory_points
            return f"Gain {count} VP", f"{{victory_point:{count}}}"
        case "contracts":
            count = tile.acquire_contracts
            return f"Gain {count} contract", f"{{contract:{count}}}"
        case "influence":
            return "Gain 1 Influence", "{influence_any:1}"
        case "intrigue_or_card":
            if args["choice"] == "intrigue":
                return "Draw 1 Intrigue card", "{intrigue:1}"
            return "Draw 1 card", "{draw:1}"
        case "shield_wall":
            if args.get("destroy_shield_wall") is True:
                return "Destroy the Shield Wall", "{shield_wall} 파괴"
            return "Keep the Shield Wall", "{shield_wall} 유지"
        case "signet":
            return (
                "Use your Leader's Signet Ring ability",
                "지도자의 {signet_ring} 능력 사용",
            )
        case "trash":
            return "Trash a card (optional)", "{trash} (선택)"
        case _:
            if effect.startswith("spy_"):
                return "Place a Spy with Deep Cover", "{spy} 배치 (잠복 스파이)"
            raise ValueError(f"unknown Tech acquire effect: {effect}")


# Where a triggered draw held as the owner's own step came from
# (``PlayerState.owed_draws``, user ruling 2026-10-10, OQ-106): English and
# Korean. Cards (``card:<instance>`` for a "when trashed" trigger,
# ``acquire:<instance>`` for an acquire box) are named from the catalog, a
# Tech tile by its catalog name; Leader abilities keep their printed English
# name.
_CHOAM_TRANSPORTS = TECH_TILES_BY_ID["choam_transports"].name
_PLANETARY_ARRAY = TECH_TILES_BY_ID["planetary_array"].name
_PLANETARY_ARRAY_KO = KOREAN_CARD_NAMES["tech"].get("planetary_array", _PLANETARY_ARRAY)
_OWED_ORIGINS: dict[str, tuple[str, str]] = {
    "bene_gesserit_4": (
        "Bene Gesserit Influence 4",
        "{influence_bene_gesserit} 4",
    ),
    "imperial_birthright": ("Imperial Birthright", "Imperial Birthright"),
    "tleilaxu_track": ("Tleilaxu track", "{tleilaxu} 트랙"),
    "research_c7r3": ("Research space c7r3", "{research} c7r3"),
    "hungry_for_spice": ("Hungry for Spice", "Hungry for Spice"),
    "choam_transports": (
        _CHOAM_TRANSPORTS,
        KOREAN_CARD_NAMES["tech"].get("choam_transports", _CHOAM_TRANSPORTS),
    ),
}
_OWED_DECKS = {"draw_owed_intrigue": "intrigue", "draw_owed_card": "card"}


def owed_draw_origin_text(origin: str) -> tuple[str, str]:
    """English and Korean name of a held draw's printed origin (OQ-106)."""

    if origin in _OWED_ORIGINS:
        return _OWED_ORIGINS[origin]
    kind, _, key = origin.partition(":")
    if kind in ("card", "acquire"):
        card = imperium_card_for_instance(key).card
        return card.name, KOREAN_CARD_NAMES["cards"].get(card.card_id, card.name)
    return origin, origin


def owed_draw_action_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Name what earned the draw a ``draw_owed_*`` step takes (OQ-106).

    The step takes the deck's oldest immediate draw if one waits, else its
    oldest (``owed_draws.next_owed_draw``), so that one is named.
    """

    deck = _OWED_DECKS.get(action.action_id)
    if deck is None or not 0 <= action.actor < len(state.players):
        return None
    owner = state.players[action.actor]
    printer = whole_printer(action)
    if printer is not None:
        # One action per entity that earned a draw (stage B3e-1): its own.
        origin = next(
            (
                origin
                for entry_deck, origin, _ in owner.owed_draws
                if entry_deck == deck
                and owed_origin_printer(state, action.actor, origin) == printer
            ),
            None,
        )
        return None if origin is None else owed_draw_origin_text(origin)
    index = next_owed_draw(owner, deck)
    return None if index is None else owed_draw_origin_text(owner.owed_draws[index][1])


def reveal_gain_action_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Name what printed the Reveal gain an action takes (stage B3e-1, one
    action per entity): a revealed card, a Skill, a Tech tile, the leader."""

    source = reveal_gain_source(state, action)
    if source is None:
        return None
    if source.startswith("skill:"):
        skill = SKILLS_BY_ID[source.removeprefix("skill:")]
        return skill.name, KOREAN_CARD_NAMES["skills"].get(skill.skill_id, skill.name)
    if source.startswith("tech:"):
        tile = TECH_TILES_BY_ID[source.removeprefix("tech:")]
        return tile.name, KOREAN_CARD_NAMES["tech"].get(tile.tech_id, tile.name)
    if source.startswith("leader_reveal:"):
        leader_id = state.players[action.actor].leader_id
        if leader_id is None:
            return None
        leader = LEADERS_BY_ID[leader_id]
        return leader.name, KOREAN_CARD_NAMES["leaders"].get(
            leader.leader_id, leader.name
        )
    return _card_names(source)


def intrigue_faction_choice_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Distinguish the cost and reward behind the shared Faction choice.

    Each slot resolves one Influence, even when the card has several slots.
    Faction and any Alliance recipient remain the action's normal arguments.
    """

    if action.action_id != "choose_intrigue_faction":
        return None
    match current_intrigue_choice_slot(state, action.actor):
        case LoseInfluence():
            return "Lose 1 Influence", "{influence_lose:1} 하락"
        case GainInfluence():
            return "Gain 1 Influence", "{influence_any:1} 상승"
        case _:
            return None


def effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe an icon, a shared payment, a Faction or a Scouts choice.

    None otherwise.
    """

    faction = intrigue_faction_choice_text(state, action)
    if faction is not None:
        return faction[0]
    owed = owed_draw_action_text(state, action) or reveal_gain_action_text(
        state, action
    )
    if owed is not None:
        return owed[0]
    tech = tech_acquire_action_text(action) or research_icon_action_text(action)
    if tech is not None:
        return tech[0]
    icon = combat_reward_icon_action_text(
        state, action
    ) or contract_reward_icon_action_text(state, action)
    if icon is not None:
        return icon[0]
    scouts = scouts_action_text(state, action)
    if scouts is not None:
        return scouts[0]
    payment = agent_card_payment_text(state, action)
    if payment is not None:
        return payment[0]
    box = agent_box_text_for_action(state, action)
    if box is not None:
        return box[0]
    state, action, row_box = route_box_action(state, action)
    key = dict(action.arguments).get("effect")
    if not isinstance(key, str):
        return None
    if action.action_id == "resolve_board_effect":
        return board_effect_action_text(state, action)
    if action.action_id == WAITING_REVEAL_CHOICE:
        # The never-legal row of a pending Reveal choice that offers nothing
        # now (display.unavailable): the choice in its card's words.
        return reveal_choice_text(key)[0]
    if action.action_id != "resolve_agent_card_effect":
        return None
    if _servo_signet_frame(state):
        # Reverse Engineering's reward icon in a Servo-Receivers frame.
        return agent_card_icon_text(_BOX.LEADER_SIGNET, key)
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        return None
    if row_box is None and resolves_boost_draw(state, action):
        # Urgent Shigawire's draw added to the boosted card's box (OQ-106).
        return f"{agent_card_icon_text(None, key)} ({_SHIGAWIRE})"
    # The box resolving, a Ghola's borrowed one included, as the engine's
    # own icon actions read it (``legal_agent_card_icon_actions``).
    return agent_card_icon_text(active_agent_card(context).agent_effect, key)


def _servo_signet_frame(state: GameState) -> bool:
    """Whether a Servo-Receivers ``leader_signet`` frame is deciding (its
    Signet Ring ability has no Agent box, OQ-062)."""

    return bool(state.decision_stack) and (
        state.decision_stack[-1].kind == FrameKind.LEADER_SIGNET
    )


def effect_action_text_ko(state: GameState, action: DomainAction) -> str | None:
    """Korean twin of ``effect_action_text``.

    ``resolve_agent_card_effect`` (Step K2) resolves through
    ``agent_card_icon_text_ko``; ``resolve_board_effect`` (Step K4) now
    resolves through ``spaces.py``'s ``board_effect_action_text_ko``; a
    waiting Reveal choice (``resume_reveal_choice``) through
    ``reveal_choice_text``. The client's ``detail_ko`` falls back to the
    English ``detail`` whenever this returns ``None`` (``static/render.js``
    ``effectNode``).
    """

    faction = intrigue_faction_choice_text(state, action)
    if faction is not None:
        return faction[1]
    owed = owed_draw_action_text(state, action) or reveal_gain_action_text(
        state, action
    )
    if owed is not None:
        return owed[1]
    tech = tech_acquire_action_text(action) or research_icon_action_text(action)
    if tech is not None:
        return tech[1]
    icon = combat_reward_icon_action_text(
        state, action
    ) or contract_reward_icon_action_text(state, action)
    if icon is not None:
        return icon[1]
    scouts = scouts_action_text(state, action)
    if scouts is not None:
        return scouts[1]
    payment = agent_card_payment_text(state, action)
    if payment is not None:
        return payment[1]
    box = agent_box_text_for_action(state, action)
    if box is not None:
        return box[1]
    state, action, row_box = route_box_action(state, action)
    key = dict(action.arguments).get("effect")
    if not isinstance(key, str):
        return None
    if action.action_id == "resolve_board_effect":
        return board_effect_action_text_ko(state, action)
    if action.action_id == WAITING_REVEAL_CHOICE:
        return reveal_choice_text(key)[1]
    if action.action_id != "resolve_agent_card_effect":
        return None
    if _servo_signet_frame(state):
        return agent_card_icon_text_ko(_BOX.LEADER_SIGNET, key)
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or not card_id:
        return None
    if row_box is None and resolves_boost_draw(state, action):
        return f"{agent_card_icon_text_ko(None, key)} ({_SHIGAWIRE_KO})"
    return agent_card_icon_text_ko(active_agent_card(context).agent_effect, key)


def agent_placements(
    state: GameState, seat: int, actions: tuple[DomainAction, ...]
) -> tuple[tuple[int, DomainAction], ...] | None:
    """The placements an Agent-turn card pick leads to (stage B1), for the
    page's staged turn: one ``(row, placement)`` per card-and-space
    placement, ``row`` the index in ``actions`` of the card pick that starts
    it, ``placement`` the whole move as ``rules.agent_turn``
    ``executable_placements`` builds it (card, graft choice, space, cost
    option, discount, infiltration). The page picks a card and a space in
    either order, as before the split, and sends the card pick and then the
    matching space pick. None when the decision holds no card pick. Display
    only: the legal rows are unchanged.
    """

    rows: dict[tuple[object, bool], int] = {}
    for index, action in enumerate(actions):
        if action.action_id == CARD_PICK_ACTION:
            arguments = dict(action.arguments)
            rows[(arguments["card_id"], arguments.get("graft") is True)] = index
    if not rows:
        return None
    entries: list[tuple[int, DomainAction]] = []
    for placement in executable_placements(state, seat):
        arguments = dict(placement.arguments)
        row = rows.get((arguments["card_id"], arguments.get("graft") is True))
        if row is not None:
            entries.append((row, placement))
    return tuple(entries)
