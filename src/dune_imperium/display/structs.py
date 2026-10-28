"""English text for standard Contract and Conflict card structures.

Wording follows the same shared display contract as ``effect_dsl_text``:
short imperative fragments, no trailing period, resources lowercase, game
terms capitalized as printed. Every renderer reads the card's ability
record (``contract_abilities``, ``conflict_abilities``) through a private
reading of its pieces; a piece of a kind it does not know raises, and the
content checks (``contracts.check_contract_terms``,
``conflicts.check_conflict_reward_row``) refuse the same kinds at import.

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

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.abilities import Ability, AbilityStructure
from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.conflicts import ConflictDefinition
from dune_imperium.content.uprising.contracts import ContractDefinition
from dune_imperium.content.uprising.effect_dsl import (
    AcquiredCard,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtMakerSpace,
    ContractTaken,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    PayResources,
    PlaceSpy,
    RecallAgent,
    RecallSpy,
    RecruitTroops,
    TakeContract,
    TakeControl,
    TakeMentat,
    TrashPersonalCard,
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

    Mirrors ``_spy_placed_text_ko``: English's bare "\\bAgents?\\b" rule
    renders one plain "Agent" regardless of count (no distinct "recall"
    icon, no numbered amount; the word since 2026-10-06), so this uses the
    bare ``{agent}``
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


def _space_name_ko(space_id: str) -> str:
    """The board space's Korean name: every Uprising space has one; an
    original-game space keeps its English name until the official Korean
    edition gives one (docs/base-game-and-ix-plan.md 18.5 2)."""

    names = KOREAN_CARD_NAMES["spaces"]
    return names[space_id] if space_id in names else BOARD_SPACES_BY_ID[space_id].name


def contract_condition_text(contract: ContractDefinition) -> str:
    """Render one standard Contract's printed completion condition."""

    match contract.requirement:
        case AtBoardSpace(space_id=space_id):
            space = BOARD_SPACES_BY_ID[space_id]
            return f"Send an Agent to {space.name}"
        case AllConditions(
            conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=amount))
        ):
            return (
                f"Send an Agent to a Maker space and gain {amount} "
                "or more spice that turn"
            )
        case AcquiredCard(card_id=card_id):
            return f"Acquire {_card_name(card_id)}"
        case ContractTaken() if contract.requires_intrigue_trash:
            return "Requires an Intrigue card: trash one when taken, completing at once"
        case ContractTaken():
            return "Complete immediately when taken"
        case AllianceTaken():
            return "Take an Alliance token you do not already hold"
    raise TypeError(f"{contract.requirement!r} is not a Contract condition")


def contract_condition_text_ko(contract: ContractDefinition) -> str:
    """Korean twin of ``contract_condition_text``.

    Verbs: Send an Agent 보내다 [Main p. 9], [Main p. 7], written as the
    bare ``{agent}`` term (not the plain word) so the client renders it the
    way ``iconize()`` renders English's "Agent" (the word since 2026-10-06,
    the Agent-piece icon before) — a plain
    Korean word here has no icon, which was a render-parity blocker
    (2026-09-25 review: 22 BOARD_SPACE/HARVEST conditions drew no icon at
    all where English drew the Agent piece, and Harvest also lost its bare
    ``{spice}`` icon the same way). Acquire 획득 [Main p. 20]; Take a
    Contract 가져오다, Complete 완수 [Main p. 16] (``docs/rules/
    glossary-ko.md``: "그 장소에 에이전트를 보내면 완수됩니다", "즉시 계약은
    그 계약을 가져가자마자 완수됩니다") — kept distinct from Acquire's 획득
    so the same word does not mean two different actions (2026-09-25
    review). A board space goes by its Korean Board Space Guide name
    (``display.names_ko``, glossary "공간 이름" row).
    """

    match contract.requirement:
        case AtBoardSpace(space_id=space_id):
            return f"{_space_name_ko(space_id)} 장소로 {{agent}}를 보냄"
        case AllConditions(
            conditions=(AtMakerSpace(), GainedSpiceThisTurn(amount=amount))
        ):
            return (
                "메이커 게임판 장소로 {agent}를 보내고, 그 차례에 "
                f"{{spice}} {amount} 이상 얻음"
            )
        case AcquiredCard(card_id=card_id):
            return f"{_card_name_ko(card_id)} 획득"
        case ContractTaken() if contract.requires_intrigue_trash:
            # Two SEPARATE bare icons, not the combined {trash_intrigue}:
            # the English words "an Intrigue card" and "trash" are not
            # adjacent ("Requires an Intrigue card: trash one when taken"),
            # so ICON_RULES' own "trash an Intrigue card" combined rule
            # never fires and iconize() draws intrigue.png and trash.png
            # separately (2026-09-25 review; the combined {trash_intrigue}
            # icon was a render-parity blocker here).
            return "{intrigue} 1장 필요, {trash} 후 가져오는 즉시 완수"
        case ContractTaken():
            return "가져오는 즉시 완수"
        case AllianceTaken():
            # "아무 팩션과 동맹이 됨" is the Bloodlines "Earn Any Alliance"
            # Contract's own Korean print (``[KO card: Earn Any Alliance]``,
            # docs/rules/glossary-ko.md's new source kind), which already
            # gives the "not already held" nuance no icon in ICON_RULES
            # covers either (English keeps it as plain words too).
            return "아무 팩션과 {alliance}이 됨"
    raise TypeError(f"{contract.requirement!r} is not a Contract condition")


@dataclass(frozen=True, slots=True)
class ContractRewardParts:
    """A Contract's reward line read piece by piece, as the card text names
    its gains (zero: not printed); the app-card scripts read it too."""

    solari: int = 0
    water: int = 0
    troops: int = 0
    personal_cards: int = 0
    contracts: int = 0
    spies: int = 0
    recall_agents: int = 0
    influence_faction: Faction | None = None
    influence: int = 0
    intrigue_cards: int = 0
    deep_cover_spies: int = 0


def contract_reward_parts(line: EffectSection) -> ContractRewardParts:
    found: dict[str, int | Faction] = {}
    counted = {"spies": 0, "deep_cover_spies": 0, "recall_agents": 0}
    for reward in line.rewards:
        match reward:
            case GainResources(solari=solari, water=water):
                found.update(solari=solari, water=water)
            case RecruitTroops(count=count):
                found["troops"] = count
            case GainInfluence(times=times, factions=(faction,)):
                found.update(influence=times, influence_faction=faction)
            case DrawIntrigueCards(count=count):
                found["intrigue_cards"] = count
            case DrawPersonalCards(count=count):
                found["personal_cards"] = count
            case TakeContract(count=count):
                found["contracts"] = count
            case PlaceSpy(shared_post=True):
                counted["deep_cover_spies"] += 1
            case PlaceSpy():
                counted["spies"] += 1
            case RecallAgent():
                counted["recall_agents"] += 1
            case _:
                raise TypeError(f"{reward!r} is not a Contract reward")
    found.update({key: value for key, value in counted.items() if value})
    return ContractRewardParts(**found)  # type: ignore[arg-type]


def contract_reward_text(contract: ContractDefinition) -> str:
    """Render one standard Contract's printed reward line."""

    reward = contract_reward_parts(contract.reward_line)
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


def contract_reward_text_ko(contract: ContractDefinition) -> str:
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

    reward = contract_reward_parts(contract.reward_line)
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


@dataclass(frozen=True, slots=True)
class ConflictRowParts:
    """A Conflict reward row read piece by piece, as the card text names its
    gains (zero: not printed); each optional arrow's cost apart. The app-AI
    synthesis script reads it too."""

    solari: int = 0
    spice: int = 0
    water: int = 0
    intrigue: int = 0
    troops: int = 0
    place_spies: int = 0
    deep_cover_spies: int = 0
    contracts: int = 0
    trash_cards: int = 0
    victory_points: int = 0
    choose_influence: int = 0
    choose_distinct_influence: int = 0
    # The original game's two-chevron Influence: one chosen Faction, every
    # Influence with it [DI p. 16] (Grand Vision).
    one_faction_influence: int = 0
    faction_influence: int = 0
    influence_faction: Faction | None = None
    control_space_id: str | None = None
    optional_spice_cost: int = 0
    optional_solari_cost: int = 0
    optional_recall_spies: int = 0
    optional_victory_points: int = 0
    # The original game's Mentat icon (Sort Through the Chaos): the winner
    # takes the Mentat at the next round's start [DI p. 16] [FAQ p. 4].
    mentat: bool = False


def conflict_row_parts(row: Ability) -> ConflictRowParts:
    found: dict[str, int | str | Faction | bool] = {}
    counted = {
        "place_spies": 0,
        "deep_cover_spies": 0,
        "trash_cards": 0,
        "choose_influence": 0,
    }
    for line in row.sections:
        if line.costs:
            match line.costs, line.rewards:
                case (PayResources(solari=solari, spice=spice),), (
                    GainVictoryPoints(amount=points),
                ):
                    if solari:
                        found["optional_solari_cost"] = solari
                    if spice:
                        found["optional_spice_cost"] = spice
                case (RecallSpy(count=count),), (GainVictoryPoints(amount=points),):
                    found["optional_recall_spies"] = count
                case _:
                    raise TypeError(f"{line!r} is not a Conflict reward arrow")
            found["optional_victory_points"] = points
            continue
        for reward in line.rewards:
            match reward:
                case GainResources(solari=solari, spice=spice, water=water):
                    found.update(solari=solari, spice=spice, water=water)
                case DrawIntrigueCards(count=count):
                    found["intrigue"] = count
                case RecruitTroops(count=count):
                    found["troops"] = count
                case PlaceSpy(shared_post=True):
                    counted["deep_cover_spies"] += 1
                case PlaceSpy():
                    counted["place_spies"] += 1
                case TakeContract(count=count):
                    found["contracts"] = count
                case TrashPersonalCard():
                    counted["trash_cards"] += 1
                case GainVictoryPoints(amount=amount):
                    found["victory_points"] = amount
                case GainInfluence(times=times, distinct=True):
                    found["choose_distinct_influence"] = times
                case GainInfluence(times=times, one_faction=True):
                    found["one_faction_influence"] = times
                case GainInfluence(times=times, factions=(faction,)):
                    found.update(faction_influence=times, influence_faction=faction)
                case GainInfluence():
                    counted["choose_influence"] += 1
                case TakeControl(space_id=space_id):
                    found["control_space_id"] = space_id
                case TakeMentat():
                    found["mentat"] = True
                case _:
                    raise TypeError(f"{reward!r} is not a Conflict reward")
    found.update({key: value for key, value in counted.items() if value})
    return ConflictRowParts(**found)  # type: ignore[arg-type]


def _choose_influence_text(count: int, *, distinct: bool) -> str:
    choice = "a different Faction" if distinct else "a Faction"
    if count == 1:
        return f"Gain 1 Influence (choose {choice})"
    return f"Gain {count} Influence (choose {choice} each time)"


def _optional_trade_text(reward: ConflictRowParts) -> list[str]:
    """One "You may <cost> → Gain N VP" part per printed arrow.

    Each optional cost is its own arrow; Economic Supremacy prints two
    (6 Solari above 4 spice), rendered in that printed order.
    """

    cost_texts: list[str] = []
    if reward.optional_solari_cost:
        cost_texts.append(f"pay {reward.optional_solari_cost} solari")
    if reward.optional_spice_cost:
        cost_texts.append(f"pay {reward.optional_spice_cost} spice")
    if reward.optional_recall_spies:
        count = reward.optional_recall_spies
        cost_texts.append("recall a Spy" if count == 1 else f"recall {count} Spies")
    vp = reward.optional_victory_points
    return [f"You may {cost_text} → Gain {vp} VP" for cost_text in cost_texts]


def _choice_parts(row: Ability) -> tuple[Ability, ...] | None:
    """The lines of a choice row, each as a row of its own, or ``None``.

    The original game prints "-OR-" (``ONE_OF``) and "Choose two:"
    (``CHOOSE_TWO``) between a reward row's icon groups [DI p. 12]
    (``content.imperium.conflict_abilities``); both are named before either
    is taken (OQ-114). Every other row is one sequence of rewards.
    """

    if row.structure is AbilityStructure.SEQUENCE:
        return None
    return tuple(replace(row, sections=(line,), structure=AbilityStructure.SEQUENCE)
                 for line in row.sections)


def conflict_reward_text(row: Ability) -> str:
    """Render one Conflict card's printed reward row."""

    choices = _choice_parts(row)
    if choices is not None:
        two = row.structure is AbilityStructure.CHOOSE_TWO
        lines = " / ".join(conflict_reward_text(line) for line in choices)
        return f"{'Choose two' if two else 'Choose one'}: {lines}"
    reward = conflict_row_parts(row)
    parts: list[str] = []
    if reward.mentat:
        parts.append(
            "Take the Mentat at the next round's start (if it is on its space)"
        )
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
    if reward.one_faction_influence:
        parts.append(
            f"Gain {reward.one_faction_influence} Influence (choose a Faction once)"
        )
    if reward.influence_faction is not None:
        faction_name = _faction_name(reward.influence_faction)
        parts.append(f"Gain {reward.faction_influence} {faction_name} Influence")
    if reward.control_space_id is not None:
        space = BOARD_SPACES_BY_ID[reward.control_space_id]
        parts.append(f"Take control of {space.name}")
    parts.extend(_optional_trade_text(reward))
    return ", ".join(parts)


def conflict_rewards_texts(definition: ConflictDefinition) -> list[str] | None:
    """Render "1st"/"2nd"/"3rd" reward lines, or None when unpublished."""

    if definition.reward_rows is None:
        return None
    labels = ("1st", "2nd", "3rd")
    return [
        f"{label}: {conflict_reward_text(row)}"
        for label, row in zip(labels, definition.reward_rows, strict=True)
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


def _optional_trade_text_ko(reward: ConflictRowParts) -> list[str]:
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
    or a numbered one. Like English, one part per printed arrow, in the
    same order (Economic Supremacy's Solari arrow before its spice one).
    """

    cost_texts: list[str] = []
    if reward.optional_solari_cost:
        cost_texts.append(f"{{solari:{reward.optional_solari_cost}}} 지불 가능")
    if reward.optional_spice_cost:
        cost_texts.append(f"{{spice:{reward.optional_spice_cost}}} 지불 가능")
    if reward.optional_recall_spies:
        cost_texts.append(f"{_recall_spy_text_ko(reward.optional_recall_spies)} 가능")
    vp = reward.optional_victory_points
    return [
        f"{cost_text} {{arrow_right}} {{victory_point:{vp}}}"
        for cost_text in cost_texts
    ]


def conflict_reward_text_ko(row: Ability) -> str:
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
    review). The space goes by its Korean name (공간 이름 row) either way.
    """

    choices = _choice_parts(row)
    if choices is not None:
        # "둘 선택:"/"하나 선택:" are the project's card-text words for a
        # printed "Choose two:"/a choice row (``tokens_ko``,
        # ``effect_dsl_text_ko``).
        two = row.structure is AbilityStructure.CHOOSE_TWO
        lines = " / ".join(conflict_reward_text_ko(line) for line in choices)
        return f"{'둘 선택' if two else '하나 선택'}: {lines}"
    reward = conflict_row_parts(row)
    parts: list[str] = []
    if reward.mentat:
        # "Mentat" stays the English word, as in ``effect_dsl_text_ko``'s
        # Calculated Hire, until the official Korean edition names it.
        parts.append("다음 라운드 시작에 Mentat 가져옴 (그 장소에 있으면)")
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
    if reward.one_faction_influence:
        # ``effect_dsl_text_ko``'s two-chevron line (Grand Vision).
        parts.append(
            f"{{influence_any:{reward.one_faction_influence}}}"
            " (4개의 팩션 중 하나 한 번 선택)"
        )
    if reward.influence_faction is not None:
        parts.append(
            f"{{influence_{reward.influence_faction.value}:{reward.faction_influence}}}"
        )
    if reward.control_space_id is not None:
        parts.append(f"{_space_name_ko(reward.control_space_id)} 지배")
    parts.extend(_optional_trade_text_ko(reward))
    return ", ".join(parts)


def conflict_rewards_texts_ko(definition: ConflictDefinition) -> list[str] | None:
    """Korean twin of ``conflict_rewards_texts``.

    "1등"/"2등"/"3등" quote the glossary's "first/second/third place" row
    (`[Main p. 14]`), matching ``korean-card-style.md``'s attested Conflict-card
    print (Battle for Arrakeen / Siege of Arrakeen).
    """

    if definition.reward_rows is None:
        return None
    labels = ("1등", "2등", "3등")
    return [
        f"{label}: {conflict_reward_text_ko(row)}"
        for label, row in zip(labels, definition.reward_rows, strict=True)
    ]
