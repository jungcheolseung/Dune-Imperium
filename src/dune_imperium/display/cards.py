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
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
from dune_imperium.content.uprising.reserve import ReserveStackDefinition
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.display.tokens import (
    ACQUISITION_EFFECT_TEXT,
    AGENT_EFFECT_TEXT,
    DISCARD_EFFECT_TEXT,
    REVEAL_ACQUISITION_EFFECT_TEXT,
    REVEAL_CHOICE_EFFECT_TEXT,
    TRASH_EFFECT_TEXT,
    reveal_effect_text,
)
from dune_imperium.display.tokens_ko import (
    ACQUISITION_EFFECT_TEXT_KO,
    AGENT_EFFECT_TEXT_KO,
    DISCARD_EFFECT_TEXT_KO,
    REVEAL_ACQUISITION_EFFECT_TEXT_KO,
    REVEAL_CHOICE_EFFECT_TEXT_KO,
    TRASH_EFFECT_TEXT_KO,
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

    agent_line = _agent_line(entry)
    if agent_line is not None:
        lines.append(agent_line)

    if isinstance(entry, ImperiumCardEntry):
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

    agent_line = _agent_line_ko(entry)
    if agent_line is not None:
        lines.append(agent_line)

    if isinstance(entry, ImperiumCardEntry):
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
