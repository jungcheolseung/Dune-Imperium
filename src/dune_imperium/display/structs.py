"""English text for standard Contract and Conflict card structures.

Wording follows the same shared display contract as ``effect_dsl_text``:
short imperative fragments, no trailing period, resources lowercase, game
terms capitalized as printed. ``contract_condition_text`` is an exhaustive
``match`` over ``ContractConditionKind`` so ``mypy`` fails if a new kind is
added without matching text support; the two reward renderers each publish
the dataclass field names they consume so a test can assert every field on
``ContractReward``/``ConflictReward`` is handled.

The ``_ko`` functions below are this module's Korean twins (feature decided
2026-09-25: the effect text the engine *generates* gets a Korean version;
printed card text stays English). They render plain Korean prose with the
same ``{term}``/``{term:count}`` placeholder syntax the client's ``phrase()``
(``static/render.js``) already expands for our own hand-written labels
(``static/labels.js`` ``TERMS``) — never literal English words for a
placeholder ``iconize()`` would otherwise turn into an icon, so a reward line
never needs its own icon-matching regex. Word choice follows only
``docs/rules/glossary-ko.md`` (game terms) or ordinary Korean grammar for
everything else (connectives, particles); a game term neither source has is
left in English rather than invented, per the same file's "규칙" section.
"""

from typing import assert_never

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.conflicts import ConflictDefinition, ConflictReward
from dune_imperium.content.uprising.contracts import (
    ContractCondition,
    ContractConditionKind,
    ContractReward,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _spy_text(count: int) -> str:
    if count == 1:
        return "Place a Spy"
    return f"Place {count} Spies"


def _spy_placed_text_ko(count: int) -> str:
    """Korean twin of ``_spy_text``.

    The client draws a single bare Spy icon for this field regardless of
    count — ``render.js`` ``ICON_RULES``' own "(?:a |an )?Sp(?:y|ies)" rule
    has no numeric capture group, so "Place 2 Spies" still renders one
    ``spy.png`` with the "2" left as plain text before it, never a numbered
    ``amount`` (render-parity blocker, 2026-09-25 review: eight "Place a
    Spy" rows drew a numbered icon English never shows). This uses the bare
    ``{spy}`` term for the same reason, with the count written as a plain
    digit — never ``{spy:count}`` — following ``korean-card-style.md``'s "default to
    the digit" rule for a reward count paired with an icon.
    """

    if count == 1:
        return "{spy} 배치"
    return f"{{spy}} {count} 배치"


def _recall_spy_text_ko(count: int) -> str:
    """Korean twin of the "recall N Spy/Spies" phrase.

    Same bare-icon reasoning as ``_spy_placed_text_ko``: English's "recall
    2 Spies" still matches ``ICON_RULES``' plain "Sp(?:y|ies)" rule, one
    icon regardless of count, never the distinct ``recall_spy`` icon or a
    numbered amount (render-parity blocker, 2026-09-25 review — Battle for
    Arrakeen's optional trade drew ``2xrecall_spy.png`` where English drew
    one bare ``spy.png``). "소환" is this project's own established word
    for the recall verb (``static/labels.js`` ``recall_spy_for_agent_card``:
    "{spy} 소환").
    """

    if count == 1:
        return "{spy} 소환"
    return f"{{spy}} {count} 소환"


def _recall_agent_text_ko(count: int) -> str:
    """Korean twin of the ``Recall N Agent(s)`` reward phrase.

    Mirrors ``_spy_placed_text_ko``: English's bare "\\bAgents?\\b" icon
    rule draws one plain Agent piece regardless of count (no distinct
    "recall" icon, no numbered amount), so this uses the bare ``{agent}``
    term — never ``{recall_agent}`` or ``{agent:count}`` — with "소환", this
    project's own established word for the recall verb (``static/
    labels.js`` ``ACTION_LABELS`` ``recall_agent_for_agent_card``: "{agent}
    소환"), and the count as a plain digit when it is not 1
    (render-parity blocker, 2026-09-25 review).
    """

    if count == 1:
        return "{agent} 소환"
    return f"{{agent}} {count} 소환"


def _card_name(card_id: str) -> str:
    """Resolve an acquirable card ID against the Imperium and Reserve pools."""

    if card_id in IMPERIUM_CARDS_BY_ID:
        return IMPERIUM_CARDS_BY_ID[card_id].card.name
    if card_id in RESERVE_STACKS_BY_ID:
        return RESERVE_STACKS_BY_ID[card_id].card.name
    raise ValueError(f"unknown acquirable card id: {card_id!r}")


def _card_name_ko(card_id: str) -> str:
    """The card's Korean print name, or its English name where unknown."""

    korean = KOREAN_CARD_NAMES["cards"].get(card_id)
    return korean if korean is not None else _card_name(card_id)


def contract_condition_text(condition: ContractCondition) -> str:
    """Render one standard Contract's printed completion condition."""

    match condition.kind:
        case ContractConditionKind.BOARD_SPACE:
            space = BOARD_SPACES_BY_ID[condition.target]
            return f"Send an Agent to {space.name}"
        case ContractConditionKind.HARVEST_SPICE:
            return (
                f"Send an Agent to a Maker space and gain {condition.amount} "
                "or more spice that turn"
            )
        case ContractConditionKind.ACQUIRE_CARD:
            return f"Acquire {_card_name(condition.target)}"
        case ContractConditionKind.IMMEDIATE:
            return "Complete immediately when taken"
        case ContractConditionKind.EARN_ALLIANCE:
            return "Take an Alliance token you do not already hold"
        case ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH:
            return "Requires an Intrigue card: trash one when taken, completing at once"
        case _:
            assert_never(condition.kind)


def contract_condition_text_ko(condition: ContractCondition) -> str:
    """Korean twin of ``contract_condition_text``.

    Verbs: Send an Agent 보내다 [Main p. 9], [Main p. 7], written as the
    bare ``{agent}`` term (not the plain word) so the client draws the same
    Agent-piece icon ``iconize()`` draws for English's "Agent" — a plain
    Korean word here has no icon, which was a render-parity blocker
    (2026-09-25 review: 22 BOARD_SPACE/HARVEST conditions drew no icon at
    all where English drew the Agent piece, and Harvest also lost its bare
    ``{spice}`` icon the same way). Acquire 획득 [Main p. 20]; Take a
    Contract 가져오다, Complete 완수 [Main p. 16] (``docs/rules/
    glossary-ko.md``: "그 장소에 에이전트를 보내면 완수됩니다", "즉시 계약은
    그 계약을 가져가자마자 완수됩니다") — kept distinct from Acquire's 획득
    so the same word does not mean two different actions (2026-09-25
    review). Board-space names stay English (glossary "공간 이름" row).
    """

    match condition.kind:
        case ContractConditionKind.BOARD_SPACE:
            space = BOARD_SPACES_BY_ID[condition.target]
            return f"{space.name} 장소로 {{agent}}를 보냄"
        case ContractConditionKind.HARVEST_SPICE:
            return (
                "메이커 게임판 장소로 {agent}를 보내고, 그 차례에 "
                f"{{spice}} {condition.amount} 이상 얻음"
            )
        case ContractConditionKind.ACQUIRE_CARD:
            return f"{_card_name_ko(condition.target)} 획득"
        case ContractConditionKind.IMMEDIATE:
            return "가져오는 즉시 완수"
        case ContractConditionKind.EARN_ALLIANCE:
            # "아무 팩션과 동맹이 됨" is the Bloodlines "Earn Any Alliance"
            # Contract's own Korean print (``[KO card: Earn Any Alliance]``,
            # docs/rules/glossary-ko.md's new source kind), which already
            # gives the "not already held" nuance no icon in ICON_RULES
            # covers either (English keeps it as plain words too).
            return "아무 팩션과 {alliance}이 됨"
        case ContractConditionKind.IMMEDIATE_INTRIGUE_TRASH:
            # Two SEPARATE bare icons, not the combined {trash_intrigue}:
            # the English words "an Intrigue card" and "trash" are not
            # adjacent ("Requires an Intrigue card: trash one when taken"),
            # so ICON_RULES' own "trash an Intrigue card" combined rule
            # never fires and iconize() draws intrigue.png and trash.png
            # separately (2026-09-25 review; the combined {trash_intrigue}
            # icon was a render-parity blocker here).
            return "{intrigue} 1장 필요, {trash} 후 가져오는 즉시 완수"
        case _:
            assert_never(condition.kind)


_HANDLED_CONTRACT_REWARD_FIELDS: frozenset[str] = frozenset(
    {
        "solari",
        "water",
        "troops",
        "personal_cards",
        "contracts",
        "spies",
        "recall_agents",
        "influence_faction",
        "influence",
        "intrigue_cards",
        "deep_cover_spies",
    }
)


def contract_reward_text(reward: ContractReward) -> str:
    """Render one standard Contract's printed reward line."""

    parts: list[str] = []
    if reward.solari:
        parts.append(f"Gain {reward.solari} solari")
    if reward.water:
        parts.append(f"Gain {reward.water} water")
    if reward.troops:
        parts.append(f"Recruit {reward.troops} {_plural(reward.troops, 'troop')}")
    if reward.personal_cards:
        parts.append(
            f"Draw {reward.personal_cards} {_plural(reward.personal_cards, 'card')}"
        )
    if reward.contracts:
        contracts_noun = _plural(reward.contracts, "Contract")
        parts.append(f"Take {reward.contracts} {contracts_noun}")
    if reward.intrigue_cards:
        parts.append(
            f"Draw {reward.intrigue_cards} Intrigue "
            f"{_plural(reward.intrigue_cards, 'card')}"
        )
    if reward.spies:
        parts.append(_spy_text(reward.spies))
    if reward.deep_cover_spies:
        parts.append(f"{_spy_text(reward.deep_cover_spies)} with Deep Cover")
    if reward.recall_agents:
        parts.append(
            f"Recall {reward.recall_agents} {_plural(reward.recall_agents, 'Agent')}"
        )
    if reward.influence_faction is not None:
        faction_name = _faction_name(reward.influence_faction)
        parts.append(f"Gain {reward.influence} {faction_name} Influence")
    return ", ".join(parts)


def contract_reward_text_ko(reward: ContractReward) -> str:
    """Korean twin of ``contract_reward_text``.

    Every field the English renders as a bare ``{term:count}`` amount in the
    client (``static/render.js`` ``ICON_RULES``: "Gain N solari/water",
    "Recruit N troops", "Draw N cards/Intrigue cards", "Gain N <Faction>
    Influence") renders as that same placeholder here, with no separate
    Korean verb — the icon already stands for "Gain"/"Recruit"/"Draw" in
    both languages. A field whose English icon is instead a BARE, uncounted
    one (Contract, Spy, Recall Agent — ``ICON_RULES``' own "Spy"/"Agent"/
    "Contract" rules have no numeric capture group) keeps that bare
    ``{term}`` here too, never ``{term:count}`` (a numbered Korean icon
    where English draws a plain one was a render-parity blocker, 2026-09-25
    review), with a short Korean verb beside it: Take a Contract 가져오다
    [Main p. 16] (``docs/rules/glossary-ko.md`` — kept distinct from
    Acquire's 획득), ``_spy_placed_text_ko``/``_recall_agent_text_ko``
    (above) for Spy/Agent, reusing this project's own established words
    (``place_..._spy``: "{spy} 배치", ``recall_agent_for_agent_card``:
    "{agent} 소환") rather than the distinct ``recall_agent``/``recall_spy``
    icons, which English never draws for these fields either.
    """

    parts: list[str] = []
    if reward.solari:
        parts.append(f"{{solari:{reward.solari}}}")
    if reward.water:
        parts.append(f"{{water:{reward.water}}}")
    if reward.troops:
        parts.append(f"{{troop:{reward.troops}}}")
    if reward.personal_cards:
        parts.append(f"{{draw:{reward.personal_cards}}}")
    if reward.contracts:
        parts.append(f"{{contract}} {reward.contracts}개 가져옴")
    if reward.intrigue_cards:
        parts.append(f"{{intrigue:{reward.intrigue_cards}}}")
    if reward.spies:
        parts.append(_spy_placed_text_ko(reward.spies))
    if reward.deep_cover_spies:
        # "잠복 스파이" is the glossary's own noun for this Spy variant
        # (``Spy with Deep Cover | 잠복 스파이 [Bloodlines p. 12]``), not a
        # parenthetical "(잠복)" tag (2026-09-25 review).
        parts.append(f"{_spy_placed_text_ko(reward.deep_cover_spies)} (잠복 스파이)")
    if reward.recall_agents:
        parts.append(_recall_agent_text_ko(reward.recall_agents))
    if reward.influence_faction is not None:
        parts.append(f"{{influence_{reward.influence_faction.value}:{reward.influence}}}")
    return ", ".join(parts)


_HANDLED_CONFLICT_REWARD_FIELDS: frozenset[str] = frozenset(
    {
        "solari",
        "spice",
        "water",
        "intrigue",
        "troops",
        "place_spies",
        "deep_cover_spies",
        "contracts",
        "trash_cards",
        "victory_points",
        "choose_influence",
        "choose_distinct_influence",
        "faction_influence",
        "influence_faction",
        "control_space_id",
        "optional_spice_cost",
        "optional_solari_cost",
        "optional_recall_spies",
        "optional_victory_points",
    }
)


def _choose_influence_text(count: int, *, distinct: bool) -> str:
    choice = "a different Faction" if distinct else "a Faction"
    if count == 1:
        return f"Gain 1 Influence (choose {choice})"
    return f"Gain {count} Influence (choose {choice} each time)"


def _optional_trade_text(reward: ConflictReward) -> str | None:
    if reward.optional_spice_cost:
        cost_text = f"pay {reward.optional_spice_cost} spice"
    elif reward.optional_solari_cost:
        cost_text = f"pay {reward.optional_solari_cost} solari"
    elif reward.optional_recall_spies:
        count = reward.optional_recall_spies
        cost_text = "recall a Spy" if count == 1 else f"recall {count} Spies"
    else:
        return None
    return f"You may {cost_text} → Gain {reward.optional_victory_points} VP"


def conflict_reward_text(reward: ConflictReward) -> str:
    """Render one Conflict card's printed reward row."""

    parts: list[str] = []
    if reward.solari:
        parts.append(f"Gain {reward.solari} solari")
    if reward.spice:
        parts.append(f"Gain {reward.spice} spice")
    if reward.water:
        parts.append(f"Gain {reward.water} water")
    if reward.intrigue:
        parts.append(
            f"Draw {reward.intrigue} Intrigue {_plural(reward.intrigue, 'card')}"
        )
    if reward.troops:
        parts.append(f"Recruit {reward.troops} {_plural(reward.troops, 'troop')}")
    if reward.place_spies:
        parts.append(_spy_text(reward.place_spies))
    if reward.deep_cover_spies:
        parts.append(f"{_spy_text(reward.deep_cover_spies)} with Deep Cover")
    if reward.contracts:
        contracts_noun = _plural(reward.contracts, "Contract")
        parts.append(f"Take {reward.contracts} {contracts_noun}")
    if reward.trash_cards:
        if reward.trash_cards == 1:
            parts.append("Trash a card")
        else:
            parts.append(f"Trash {reward.trash_cards} cards")
    if reward.victory_points:
        parts.append(f"Gain {reward.victory_points} VP")
    if reward.choose_influence:
        parts.append(_choose_influence_text(reward.choose_influence, distinct=False))
    if reward.choose_distinct_influence:
        parts.append(
            _choose_influence_text(reward.choose_distinct_influence, distinct=True)
        )
    if reward.influence_faction is not None:
        faction_name = _faction_name(reward.influence_faction)
        parts.append(f"Gain {reward.faction_influence} {faction_name} Influence")
    if reward.control_space_id is not None:
        space = BOARD_SPACES_BY_ID[reward.control_space_id]
        parts.append(f"Take control of {space.name}")
    optional = _optional_trade_text(reward)
    if optional is not None:
        parts.append(optional)
    return ", ".join(parts)


def conflict_rewards_texts(definition: ConflictDefinition) -> list[str] | None:
    """Render "1st"/"2nd"/"3rd" reward lines, or None when unpublished."""

    if definition.rewards is None:
        return None
    labels = ("1st", "2nd", "3rd")
    return [
        f"{label}: {conflict_reward_text(reward)}"
        for label, reward in zip(labels, definition.rewards, strict=True)
    ]


def _choose_influence_text_ko(count: int, *, distinct: bool) -> str:
    """Korean twin of ``_choose_influence_text``.

    "4개의 팩션 중 하나" quotes ``docs/rules/glossary-ko.md``'s "any
    Faction" row (`[Main p. 20]`); "각기 다른" (a different one each time)
    reuses "다른" from that same file's "opponent" row (다른 플레이어),
    the project's own established word for "different/other". "선택" (choose)
    is this project's established word for it (``static/labels.js``
    ``ACTION_LABELS``, e.g. "choose_agent_card_influence": "{influence_any}
    선택").
    """

    choice = "각기 다른 팩션 중 하나" if distinct else "4개의 팩션 중 하나"
    if count == 1:
        return f"{{influence_any:1}} ({choice} 선택)"
    return f"{{influence_any:{count}}} (매번 {choice} 선택)"


def _optional_trade_text_ko(reward: ConflictReward) -> str | None:
    """Korean twin of ``_optional_trade_text``.

    "가능" is the terse nominal ending printed Korean card text uses for
    "may" (``korean-card-style.md`` item 9: "확인 가능", "폐기 가능").
    "지불" (pay) is `[Main p. 20]` ("Paying a cost" 비용 지불). The arrow is
    never translated (``korean-card-style.md`` item 11), but it is still the
    ``{arrow_right}`` TERM here, not a literal "→" character: the client's
    ``phrase()`` only expands ``{term}`` placeholders, so a bare "→" in a
    *generated* Korean line stays plain text instead of becoming the same
    icon ``iconize()``'s own "→" rule draws for English — a render-parity
    blocker across every optional-trade row (2026-09-25 review; this
    docstring previously and wrongly claimed the client's rule covered it).
    The recall-Spies branch uses ``_recall_spy_text_ko`` for the same
    bare-icon reason as the Spy reward fields above: English's "recall 2
    Spies" still draws one plain Spy icon, never a distinct "recall" icon
    or a numbered one.
    """

    if reward.optional_spice_cost:
        cost_text = f"{{spice:{reward.optional_spice_cost}}} 지불 가능"
    elif reward.optional_solari_cost:
        cost_text = f"{{solari:{reward.optional_solari_cost}}} 지불 가능"
    elif reward.optional_recall_spies:
        cost_text = f"{_recall_spy_text_ko(reward.optional_recall_spies)} 가능"
    else:
        return None
    vp = reward.optional_victory_points
    return f"{cost_text} {{arrow_right}} {{victory_point:{vp}}}"


def conflict_reward_text_ko(reward: ConflictReward) -> str:
    """Korean twin of ``conflict_reward_text``.

    Follows the same "bare ``{term:count}``, no separate verb" rule as
    ``contract_reward_text_ko`` for every field the client icon-matches with
    its count (solari/spice/water/Intrigue/troops/Influence/VP); a field
    whose English icon is bare and uncounted (Contract, Spy) uses that bare
    ``{term}`` too, via ``_spy_placed_text_ko`` for Spy (never
    ``{spy:count}``, a render-parity blocker fixed 2026-09-25 — see that
    helper). "카드 N장 {trash}" quotes the glossary's "Trash one card" row
    (카드 1장 폐기, `[Main p. 20]`) with its Korean word swapped for the
    ``{trash}`` placeholder. Control keeps the glossary's plain word 지배
    (`[Main p. 20]`), not the ``{control}`` icon: ``ICON_RULES`` has no rule
    for "Control" at all, so English's "Take control of X" stays plain words
    too — drawing the icon in Korean was a render-parity blocker (2026-09-25
    review). The space name stays English (공간 이름 row) either way.
    """

    parts: list[str] = []
    if reward.solari:
        parts.append(f"{{solari:{reward.solari}}}")
    if reward.spice:
        parts.append(f"{{spice:{reward.spice}}}")
    if reward.water:
        parts.append(f"{{water:{reward.water}}}")
    if reward.intrigue:
        parts.append(f"{{intrigue:{reward.intrigue}}}")
    if reward.troops:
        parts.append(f"{{troop:{reward.troops}}}")
    if reward.place_spies:
        parts.append(_spy_placed_text_ko(reward.place_spies))
    if reward.deep_cover_spies:
        # "잠복 스파이" is the glossary's own noun for this Spy variant
        # (``Spy with Deep Cover | 잠복 스파이 [Bloodlines p. 12]``), the
        # same wording ``contract_reward_text_ko`` already uses above.
        parts.append(f"{_spy_placed_text_ko(reward.deep_cover_spies)} (잠복 스파이)")
    if reward.contracts:
        parts.append(f"{{contract}} {reward.contracts}개 가져옴")
    if reward.trash_cards:
        parts.append(f"카드 {reward.trash_cards}장 {{trash}}")
    if reward.victory_points:
        parts.append(f"{{victory_point:{reward.victory_points}}}")
    if reward.choose_influence:
        parts.append(_choose_influence_text_ko(reward.choose_influence, distinct=False))
    if reward.choose_distinct_influence:
        parts.append(
            _choose_influence_text_ko(reward.choose_distinct_influence, distinct=True)
        )
    if reward.influence_faction is not None:
        parts.append(
            f"{{influence_{reward.influence_faction.value}:{reward.faction_influence}}}"
        )
    if reward.control_space_id is not None:
        space = BOARD_SPACES_BY_ID[reward.control_space_id]
        parts.append(f"{space.name} 지배")
    optional = _optional_trade_text_ko(reward)
    if optional is not None:
        parts.append(optional)
    return ", ".join(parts)


def conflict_rewards_texts_ko(definition: ConflictDefinition) -> list[str] | None:
    """Korean twin of ``conflict_rewards_texts``.

    "1등"/"2등"/"3등" quote the glossary's "first/second/third place" row
    (`[Main p. 14]`), matching ``korean-card-style.md``'s attested Conflict-card
    print (Battle for Arrakeen / Siege of Arrakeen).
    """

    if definition.rewards is None:
        return None
    labels = ("1등", "2등", "3등")
    return [
        f"{label}: {conflict_reward_text_ko(reward)}"
        for label, reward in zip(labels, definition.rewards, strict=True)
    ]
