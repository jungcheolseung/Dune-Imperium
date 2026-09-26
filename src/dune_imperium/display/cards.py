"""English display lines for one personal card's play-facing data.

Wording follows the same shared display contract as ``tokens``,
``effect_dsl_text`` and ``structs``: short imperative fragments, no trailing
period, resources lowercase, game terms capitalized as printed. Printed
Persuasion and strength (``reveal_persuasion``/``reveal_strength``) are
existing catalog fields the UI already surfaces directly, so
:func:`personal_card_text` never restates them; only dynamic effect data
(Agent-box effects, passives, automatic and choice Reveal effects, and
acquire/discard/trash triggers) produces lines.

``personal_card_text_ko`` is this module's Korean twin (Step K2, feature
decided 2026-09-25), drawing on ``tokens_ko``'s tables. Its box-label
prefixes ("에이전트 칸:"/"공개 칸:"/"획득 시:"/"버리면:"/"폐기되면:") are
plain Korean **words**, never the ``{agent}``/``{discard}``/``{trash}``
icon term: rendering "Agent:" as the Agent-piece icon was a real bug (a
card's own printed name is plain text so it is safe, but the box label sits
right where the popover renders through ``iconize()``/``phrase()``, and a
general "Agent"-word icon rule would have swallowed it exactly the way it
already once swallowed the "Signet Ring" card name in the action log).
"에이전트 칸"/"공개 칸" are the card structure legend's own words
(``docs/rules/glossary-ko.md``'s "Agent box" row, `[Main p. 8]`:
"당신의 카드덱을 구성하는 각 카드의 효과는 에이전트 칸과 공개 칸으로
구분되어 있습니다" — the same sentence names both boxes).
"획득 시"/"버리면"/"폐기되면" compose the glossary's own verbs (획득
`[Main p. 20]`, 버리다/폐기 `[Main p. 20]`) with ordinary Korean grammar
("시"/조건형 어미 "-면"은 게임 용어가 아닌 일반 문법) for a trigger no box
the rulebook names covers (only the Agent/Reveal/Acquire boxes are
structural, `[Main p. 8]`; a discard/trash trigger is written directly on
the card face, not a named box), per ``docs/rules/glossary-ko.md``'s own
rule: invent nothing a source doesn't name, but ordinary grammar is free.
"버리면"/"폐기되면" (not "버릴 때"/"폐기될 때") specifically: Korean's
vowel-stem contraction turns 버리다's stem into "버릴" when "-ㄹ 때"
attaches (버리+ㄹ → 버릴), which no longer contains the literal "버리"
substring ``tests/support/ko_text.py``'s trash/discard checker looks for
even though the word is the correct verb; "-(으)면" attaches without
contracting the stem (버리+면 → 버리면), so it reads naturally and keeps
the checkable word intact. A bare "버리면:" (not "이 카드를 버리면:",
naming the card, which the Spacing Guild's Favor Korean print uses — "이
카드가 버려질 때:") was flagged as a style nit in the 2026-09-25 review;
left as-is here because fixing it would also require updating
``scripts/e2e/card_labels.py``'s hardcoded ``KOREAN_LABELS["On discard"]``
expectation, outside this fix-up's file scope.
"""

from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import ImperiumCardEntry
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    card_is_ghola,
    card_is_usurp,
)
from dune_imperium.content.uprising.reserve import ReserveStackDefinition
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.display.tokens import (
    ACQUISITION_EFFECT_TEXT,
    AGENT_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    ICON_CONDITION_TEXT,
    REVEAL_ACQUISITION_EFFECT_TEXT,
    REVEAL_CHOICE_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
    TURN_START_EFFECT_TEXT,
    reveal_effect_text,
)
from dune_imperium.display.tokens_ko import (
    ACQUISITION_EFFECT_TEXT_KO,
    AGENT_EFFECT_TEXT_KO,
    DISCARD_EFFECT_TEXT_KO,
    ICON_CONDITION_TEXT_KO,
    REVEAL_ACQUISITION_EFFECT_TEXT_KO,
    REVEAL_CHOICE_EFFECT_TEXT_KO,
    TRASH_EFFECT_TEXT_KO,
    TURN_START_EFFECT_TEXT_KO,
    reveal_effect_text_ko,
)

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}

# docs/rules/glossary-ko.md "팩션과 영향력" section, `[Main p. 20]`.
_FACTION_NAMES_KO: dict[Faction, str] = {
    Faction.EMPEROR: "황제",
    Faction.SPACING_GUILD: "우주 항행 길드",
    Faction.BENE_GESSERIT: "베네 게세리트",
    Faction.FREMEN: "프레멘",
}


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _faction_name_ko(faction: Faction) -> str:
    return _FACTION_NAMES_KO[faction]


def _factions_or(factions: tuple[Faction, ...]) -> str:
    """Join Faction names with a natural "or"/Oxford-comma list."""

    names = [_faction_name(faction) for faction in factions]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return f"{', '.join(names[:-1])}, or {names[-1]}"


_AGENT_ICON_NAMES: Final[dict[AgentIcon, str]] = {
    AgentIcon.EMPEROR: "Emperor",
    AgentIcon.SPACING_GUILD: "Spacing Guild",
    AgentIcon.BENE_GESSERIT: "Bene Gesserit",
    AgentIcon.FREMEN: "Fremen",
    AgentIcon.LANDSRAAD: "Landsraad",
    AgentIcon.CITY: "City",
    AgentIcon.SPICE_TRADE: "Spice Trade",
    AgentIcon.SPY: "Spy",
}


def _names_and(names: list[str]) -> str:
    """Join names with a natural "and"/Oxford-comma list."""

    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _icon_condition_line(entry: PersonalCardDefinition) -> str | None:
    """Render the printed condition under which the greyed icons are real.

    Long Reach's and Show of Strength's Agent icons are printed greyed and
    only exist while the card's condition holds [card faces]; the catalog
    still lists them, so the text must say so.
    """

    if not isinstance(entry, ImperiumCardEntry) or entry.icon_condition is None:
        return None
    icons = _names_and([_AGENT_ICON_NAMES[icon] for icon in entry.agent_icons])
    return f"{ICON_CONDITION_TEXT[entry.icon_condition]}, this has {icons}"


_GHOLA_AGENT_LINE: Final = (
    "Agent: This card has the same Agent box as the other grafted card"
)


# Korean twin of ``_AGENT_ICON_NAMES``: plain words, not the ``{agent_icon_*}``
# TERMS placeholders. English's own hand-authored lines below ("this has
# Landsraad, City, and Spice Trade", "Emperor, Spacing Guild, Bene Gesserit,
# and Fremen Agent icons") never draw an icon graphic for a bare Faction/
# Agent-icon name — no ``ICON_RULES`` rule matches "Landsraad"/"Emperor"/etc.
# on its own (only "<Faction> Influence" and counted-resource patterns
# match) — so Korean must not draw one either; a placeholder would be a
# render-parity regression (``display/tokens_ko.py``'s module docstring).
_AGENT_ICON_NAMES_KO: Final[dict[AgentIcon, str]] = {
    AgentIcon.EMPEROR: "황제",
    AgentIcon.SPACING_GUILD: "우주 항행 길드",
    AgentIcon.BENE_GESSERIT: "베네 게세리트",
    AgentIcon.FREMEN: "프레멘",
    AgentIcon.LANDSRAAD: "랜드스래드",
    AgentIcon.CITY: "도시",
    AgentIcon.SPICE_TRADE: "스파이스 거래",
    AgentIcon.SPY: "스파이",
}


def _object_particle_ko(word: str) -> str:
    """을 after a final consonant, 를 after a vowel (the Hangul syllable's
    final-consonant slot) — mirrors ``effect_dsl_text_ko.py``'s identical
    helper (each display Korean module keeps its own small local helpers
    rather than reaching across module boundaries)."""

    last = word.rstrip()[-1:]
    if "가" <= last <= "힣":
        return "을" if (ord(last) - ord("가")) % 28 else "를"
    return "을"


def _conjunction_particle_ko(word: str) -> str:
    """과 after a final consonant, 와 after a vowel."""

    last = word.rstrip()[-1:]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - ord("가")) % 28 else "와"
    return "와"


def _names_and_ko(names: list[str]) -> str:
    """Korean twin of ``_names_and``.

    Long Reach's own scan lists its three icons with plain commas and no
    trailing "그리고" ("...이 카드는 랜드스래드, 도시, 스파이스 거래를
    보유."); Show of Strength's own scan lists its two icons joined by
    "와" ("...이 카드는 랜드스래드와 스파이스 거래를 보유.") [KO card: Long
    Reach] [KO card: Show of Strength] — a two-item list takes 와/과, three
    or more are comma-joined with no conjunction word.
    """

    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}{_conjunction_particle_ko(names[0])} {names[1]}"
    return ", ".join(names)


def _icon_condition_line_ko(entry: PersonalCardDefinition) -> str | None:
    """Korean twin of ``_icon_condition_line``.

    Both card scans confirm the same "<condition>, 이 카드는 <icons>를
    보유" shape ``ICON_CONDITION_TEXT_KO``'s own docstring cites.
    """

    if not isinstance(entry, ImperiumCardEntry) or entry.icon_condition is None:
        return None
    icon_names = [_AGENT_ICON_NAMES_KO[icon] for icon in entry.agent_icons]
    icons = _names_and_ko(icon_names)
    particle = _object_particle_ko(icon_names[-1])
    condition = ICON_CONDITION_TEXT_KO[entry.icon_condition]
    return f"{condition}, 이 카드는 {icons}{particle} 보유"


# "이 카드는 접합된 다른 카드와 동일한 에이전트 칸을 보유." [KO card: Ghola]
# — but unlike a line-prefix box label ("Agent:", always plain text via
# ICON_RULES' colon-gated rule), English's own "the same Agent box" is a
# MID-SENTENCE mention with no colon, so it falls through to the bare
# ``\bAgents?\b`` rule and draws the Agent-piece icon there (2026-09-25
# full-catalog sweep); the bare {agent} term matches that, with "칸을 보유"
# (box, possess) as plain trailing text.
_GHOLA_AGENT_LINE_KO: Final = (
    "이 카드는 접합된 다른 카드와 동일한 {agent} 칸을 보유"
)


def _factions_or_ko(factions: tuple[Faction, ...]) -> str:
    """Korean twin of ``_factions_or``.

    "또는" (or) is a rulebook connective, not a glossary game term,
    attested at `[Main p. 14]` ("4인(또는 6인) 게임에서는…"). A Korean list
    has no Oxford comma to drop: every item but the last is joined with a
    comma and a space before the final "또는".
    """

    names = [_faction_name_ko(faction) for faction in factions]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} 또는 {names[-1]}"


_PLAY_DATA_NOT_TRANSCRIBED: Final = "(play data not transcribed)"
_PLAY_DATA_NOT_TRANSCRIBED_KO: Final = "(플레이 데이터 없음)"

# Reclaimed Forces never enters a player's deck (it is "never removed from
# the Tleilaxu Row" [Immortality p. 9] [Reclaimed Forces card]), so it has
# no Agent/Reveal play data and personal_card_text() would otherwise print
# "(play data not transcribed)" for it. Its printed acquire box is a choice
# ("recruit two troops -OR- Tleilaxu"), which fits no single
# PersonalCardAcquisitionEffect, so server.catalog renders this text
# directly instead of routing the card through personal_card_text().
RECLAIMED_FORCES_TEXT: Final[tuple[str, ...]] = (
    "On acquire (choose one): Recruit 2 troops / Tleilaxu "
    "(advance your Tleilaxu token)",
    "Never removed from the Tleilaxu Row",
)

# Korean twin of ``RECLAIMED_FORCES_TEXT``. The acquire box itself prints
# only icons (recruit-2-troops, "또는", Tleilaxu) with no Korean sentence to
# quote, so the "On acquire (choose one): ... / ..." line follows this
# project's own established "하나 선택: X / Y" pattern; the second line
# quotes the card's own italic reminder text verbatim: "(이 카드는 틀레이락스
# 열에서 절대로 제거되지 않습니다.)" [KO card: Reclaimed Forces], recast into
# the terse nominal register (no "-습니다"/parentheses/period) every other
# generated line in this project uses.
RECLAIMED_FORCES_TEXT_KO: Final[tuple[str, ...]] = (
    "획득 시 (하나 선택): {troop:2} / {tleilaxu} (트랙 전진)",
    "이 카드는 {tleilaxu_row}에서 절대로 제거되지 않음",
)

# Blank Slate: "If grafted: This has [Emperor], [Spacing Guild], [Bene
# Gesserit], and [Fremen]" [Blank Slate card face]. The four Faction icons
# are added by rules.agent_icons via a card_id check rather than a typed
# ImperiumCardEntry field, so this line is hand-authored the same way.
_BLANK_SLATE_GRAFT_ICONS_LINE: Final = (
    "If grafted: This has Emperor, Spacing Guild, Bene Gesserit, "
    "and Fremen Agent icons"
)

# "만약 접합되었다면: 이 카드는 [Emperor],[Spacing Guild],[Bene Gesserit],
# [Fremen]를 보유." [KO card: Blank Slate] — "{graft}했다면:" is this
# project's own established phrasing for "if grafted" (tokens.py's
# ADVANCE_TLEILAXU_IF_GRAFTED and siblings), not the scan's own passive
# "접합되었다면" (the same underlying word, {graft} = "접합"). The four
# Faction names stay plain words, not {agent_icon_*} icon placeholders, for
# the same render-parity reason as ``_AGENT_ICON_NAMES_KO`` above; "Agent
# icons" bare-matches ICON_RULES' bare Agent-piece rule in English, so the
# bare {agent} term draws that same piece here.
_BLANK_SLATE_GRAFT_ICONS_LINE_KO: Final = (
    "{graft}했다면: 이 카드는 황제, 우주 항행 길드, 베네 게세리트, "
    "프레멘의 {agent} 아이콘 보유"
)

# Usurp's GRAFT box is a passive with no PersonalCardAgentEffect member: it
# grafts to a card in the Imperium Row instead of one from the player's hand
# [Usurp card face].
_USURP_GRAFT_LINE: Final = (
    "Graft: You may graft this to a card in the Imperium Row without "
    "acquiring it. If you do, trash that card at the end of your turn"
)

# "당신은 이 카드를 임페리움 열에 있는 카드 하나에 접합할 수 있음(그 카드를
# 획득하지 않음). 그렇게 하면, 당신의 차례 끝에 그 카드를 폐기." [KO card:
# Usurp] — the box label "접합" stays the plain word (module docstring: a
# box-label prefix is never a {term} placeholder), the body swaps in
# {imperium_row}/{graft}/{acquire}/{trash} for render parity.
_USURP_GRAFT_LINE_KO: Final = (
    "접합: 이 카드를 {imperium_row}에 있는 카드 하나에 {graft}할 수 있음 "
    "(그 카드를 {acquire}하지 않음). 그렇게 하면, "
    "당신의 차례 끝에 그 카드를 {trash}"
)

# The single transcribed PersonalCardRevealAcquisitionEffect member is
# specific to The Spice Must Flow (see its enum name and Guild Spy's audit
# entry in docs/implementation-audits/personal-cards.md); this prefix names
# that condition rather than the generic "per acquired card" wording, since
# the effect does not trigger for other acquisitions.
_REVEAL_ACQUISITION_PREFIX = "Reveal, if you acquire The Spice Must Flow: "
_SPICE_MUST_FLOW_NAME_KO: Final = KOREAN_CARD_NAMES["cards"]["the_spice_must_flow"]
_REVEAL_ACQUISITION_PREFIX_KO: Final = (
    f"공개, {_SPICE_MUST_FLOW_NAME_KO} 획득 시: "
)


def _agent_line(entry: PersonalCardDefinition) -> str | None:
    effect = entry.agent_effect
    if effect is None:
        return None
    text = AGENT_EFFECT_TEXT[effect]
    if not text:
        return None
    if entry.agent_spy_factions:
        text = f"{text} ({_factions_or(entry.agent_spy_factions)} Spy)"
    return f"Agent: {text}"


def _agent_line_ko(entry: PersonalCardDefinition) -> str | None:
    """Korean twin of ``_agent_line``; see the module docstring for why the
    "에이전트 칸:" prefix is a plain word, never the ``{agent}`` icon term."""

    effect = entry.agent_effect
    if effect is None:
        return None
    text = AGENT_EFFECT_TEXT_KO[effect]
    if not text:
        return None
    if entry.agent_spy_factions:
        text = f"{text} ({_factions_or_ko(entry.agent_spy_factions)} {{spy}})"
    return f"에이전트 칸: {text}"


def _reveal_line(entry: PersonalCardDefinition) -> str | None:
    parts = [reveal_effect_text(effect) for effect in entry.reveal_effects]
    parts.extend(
        REVEAL_CHOICE_EFFECT_TEXT[choice] for choice in entry.reveal_choice_effects
    )
    if not parts:
        return None
    return f"Reveal: {'; '.join(parts)}"


def _reveal_line_ko(entry: PersonalCardDefinition) -> str | None:
    """Korean twin of ``_reveal_line``; see the module docstring for why the
    "공개 칸:" prefix is a plain word, never an icon term."""

    parts = [reveal_effect_text_ko(effect) for effect in entry.reveal_effects]
    parts.extend(
        REVEAL_CHOICE_EFFECT_TEXT_KO[choice] for choice in entry.reveal_choice_effects
    )
    if not parts:
        return None
    return f"공개 칸: {'; '.join(parts)}"


def personal_card_text(entry: PersonalCardDefinition) -> list[str]:
    """Render one personal card's ordered English display lines.

    Covers ``ImperiumCardEntry``, ``StartingCardEntry`` and
    ``ReserveStackDefinition`` — the three sources sharing the personal-card
    Agent/Reveal schema (see ``content.uprising.personal_cards``). Each
    source declares a different subset of the optional fields (only
    ``ImperiumCardEntry`` carries ``ignores_influence_requirements``,
    ``allows_recruited_troop_deployment``, ``acquisition_effect``,
    ``trash_effect`` and ``play_data_complete``; only
    ``ReserveStackDefinition`` carries ``acquisition_vp``), so those are
    read through ``isinstance`` narrowing instead of a blanket ``getattr``.
    """

    if isinstance(entry, ImperiumCardEntry) and not entry.play_data_complete:
        return [_PLAY_DATA_NOT_TRANSCRIBED]

    lines: list[str] = []

    icon_condition_line = _icon_condition_line(entry)
    if icon_condition_line is not None:
        lines.append(icon_condition_line)
    agent_line = _agent_line(entry)
    if agent_line is not None:
        lines.append(agent_line)
    if card_is_ghola(entry):
        # The box is borrowed at play time (``rules.effects``), so the
        # printed Graft box has no effect of its own to render [Ghola card].
        lines.append(_GHOLA_AGENT_LINE)

    if isinstance(entry, ImperiumCardEntry) and entry.turn_start_effect is not None:
        # Litany Against Fear: a red turn-start box replaces its Agent box
        # [Litany Against Fear card face].
        lines.append(
            "At the start of your turn: "
            f"{TURN_START_EFFECT_TEXT[entry.turn_start_effect]}"
        )

    if isinstance(entry, ImperiumCardEntry):
        if entry.card.card_id == "blank_slate":
            lines.append(_BLANK_SLATE_GRAFT_ICONS_LINE)
        if card_is_usurp(entry):
            lines.append(_USURP_GRAFT_LINE)
        if entry.agent_icons_from_contracts:
            lines.append(
                "Has the Agent icons shown on all your incomplete contracts"
            )
        if entry.ignores_influence_requirements:
            lines.append("Ignores Influence requirements")
        if entry.allows_recruited_troop_deployment:
            lines.append("Recruited troops may be deployed to the Conflict")

    reveal_line = _reveal_line(entry)
    if reveal_line is not None:
        lines.append(reveal_line)

    if isinstance(entry, ImperiumCardEntry) and entry.acquisition_effect is not None:
        lines.append(
            f"On acquire: {ACQUISITION_EFFECT_TEXT[entry.acquisition_effect]}"
        )

    if isinstance(entry, ReserveStackDefinition) and entry.acquisition_vp:
        lines.append(f"On acquire: Gain {entry.acquisition_vp} VP")

    if entry.discard_effect is not None:
        lines.append(f"On discard: {DISCARD_EFFECT_TEXT[entry.discard_effect]}")

    if isinstance(entry, ImperiumCardEntry) and entry.trash_effect is not None:
        lines.append(f"When trashed: {TRASH_EFFECT_TEXT[entry.trash_effect]}")

    if entry.reveal_acquisition_effect is not None:
        reward = REVEAL_ACQUISITION_EFFECT_TEXT[entry.reveal_acquisition_effect]
        lines.append(f"{_REVEAL_ACQUISITION_PREFIX}{reward}")

    return lines


def personal_card_text_ko(entry: PersonalCardDefinition) -> list[str]:
    """Korean twin of ``personal_card_text``.

    Same structure and line order as the English renderer (so
    ``cards[id].text_ko`` always has the same length as ``cards[id].text``
    for a card the catalog serves, per ``server/catalog.py``'s field
    policy), with the box-label prefixes and passive lines translated
    per this module's docstring: "에이전트 칸"/"공개 칸" from the card
    structure legend (``docs/rules/glossary-ko.md`` "Agent box" row,
    `[Main p. 8]`), "획득 시"/"버리면"/"폐기되면" composed from the
    glossary's own verbs.
    """

    if isinstance(entry, ImperiumCardEntry) and not entry.play_data_complete:
        return [_PLAY_DATA_NOT_TRANSCRIBED_KO]

    lines: list[str] = []

    icon_condition_line = _icon_condition_line_ko(entry)
    if icon_condition_line is not None:
        lines.append(icon_condition_line)
    agent_line = _agent_line_ko(entry)
    if agent_line is not None:
        lines.append(agent_line)
    if card_is_ghola(entry):
        lines.append(_GHOLA_AGENT_LINE_KO)

    if isinstance(entry, ImperiumCardEntry) and entry.turn_start_effect is not None:
        lines.append(
            f"당신의 차례 시작 시: {TURN_START_EFFECT_TEXT_KO[entry.turn_start_effect]}"
        )

    if isinstance(entry, ImperiumCardEntry):
        if entry.card.card_id == "blank_slate":
            lines.append(_BLANK_SLATE_GRAFT_ICONS_LINE_KO)
        if card_is_usurp(entry):
            lines.append(_USURP_GRAFT_LINE_KO)
        if entry.agent_icons_from_contracts:
            # "Has the Agent icons shown on all your incomplete contracts"
            # (Delivery Logistics): "contracts" is lower-case in English
            # (ICON_RULES' Contract rule is capital-only, tokens_ko.py's own
            # precedent), so it stays the plain word 계약; the bare {agent}
            # term matches English's own bare Agent-piece icon for the word
            # "Agent" (see ``_BLANK_SLATE_GRAFT_ICONS_LINE_KO`` above).
            lines.append(
                "당신의 완수하지 않은 모든 계약에 표시된 {agent} 아이콘 보유"
            )
        if entry.ignores_influence_requirements:
            lines.append("영향력 요구 조건 무시")
        if entry.allows_recruited_troop_deployment:
            lines.append("소집한 {troop}을 {conflict}에 배치 가능")

    reveal_line = _reveal_line_ko(entry)
    if reveal_line is not None:
        lines.append(reveal_line)

    if isinstance(entry, ImperiumCardEntry) and entry.acquisition_effect is not None:
        lines.append(
            f"획득 시: {ACQUISITION_EFFECT_TEXT_KO[entry.acquisition_effect]}"
        )

    if isinstance(entry, ReserveStackDefinition) and entry.acquisition_vp:
        lines.append(f"획득 시: {{victory_point:{entry.acquisition_vp}}}")

    if entry.discard_effect is not None:
        lines.append(f"버리면: {DISCARD_EFFECT_TEXT_KO[entry.discard_effect]}")

    if isinstance(entry, ImperiumCardEntry) and entry.trash_effect is not None:
        lines.append(f"폐기되면: {TRASH_EFFECT_TEXT_KO[entry.trash_effect]}")

    if entry.reveal_acquisition_effect is not None:
        reward = REVEAL_ACQUISITION_EFFECT_TEXT_KO[entry.reveal_acquisition_effect]
        lines.append(f"{_REVEAL_ACQUISITION_PREFIX_KO}{reward}")

    return lines
