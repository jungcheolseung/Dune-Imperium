"""Korean text for the Intrigue effect DSL primitives.

This is ``effect_dsl_text.py``'s Korean twin (feature decided 2026-09-25: the
effect text the engine *generates* gets a Korean version; printed card text
stays English). Same exhaustive-``match`` structure as the English module, so
``mypy`` fails the moment a new DSL primitive is added without matching
Korean support. Every renderer produces plain Korean prose with the
``{term}``/``{term:count}`` placeholder syntax the client's ``phrase()``
(``static/render.js``) already expands for our own hand-written labels
(``static/labels.js`` ``TERMS``); a placeholder is used wherever English's
own ``iconize()`` (``ICON_RULES``, same file) draws an icon for the matching
English wording, so Korean draws the same icon set — never a plain Korean
word standing in for an icon English actually shows (a render-parity
blocker throughout the K1/K2 review, ``display/structs.py``'s module
docstring). Word choice follows only ``docs/rules/glossary-ko.md`` (game
terms), a confirmed Korean card print cited ``[KO card: <name>]``, or
ordinary Korean grammar for connectives/particles; a term neither source has
is left in English rather than invented.

A condition clause ends in the conjugated Korean conditional appropriate to
its shape (``korean-card-style.md`` rule 1: ``-다면`` for a clause naming an action,
``-(이)면`` for a bare nominal/threshold state) and carries **no** leading
"if"/"만약" word and **no** trailing colon — ``section_text_ko`` appends
``": "`` + the body itself, mirroring every other Korean condition renderer
in this project (``display/tokens_ko.py``'s ``reveal_effect_text_ko``,
``display/actions.py``'s ``_ICON_CONDITIONS_KO``). A "N 이상" threshold on a
resource/Influence/Tech-tile pool (a track state, not a counted physical
object) keeps the counted TERM bare and puts the digit after it as plain
text ("{influence_emperor} 3 이상이면", matching 8 precedents in
``tokens_ko.py``); a threshold on a counted physical thing that "exists"
somewhere (Spies on the board, Commanders/sandworms in the Conflict) adds
"있다면" the same way ("{conflict}에 {commander}이 1 이상 있다면", also
already established there). Completed-Contracts and Navigation-slot wording
are quoted directly from Korean card scans (see each case's docstring).
"""

from typing import assert_never

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireReserveCard,
    AcquireTech,
    AcquireTleilaxuCard,
    AdvanceTleilaxu,
    AllConditions,
    CommanderDiscountThisTurn,
    CommandersInConflictAtLeast,
    CompletedContractsAtLeast,
    Condition,
    Cost,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerUnitType,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    GiveIntrigueToOpponent,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    HasAlliance,
    HasHighCouncil,
    IgnoreInfluenceRequirementsThisTurn,
    InfluenceAtLeast,
    InNavigationSlot,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnRevealAcquisitionThisRound,
    OnTroopsLostAtConflictEnd,
    OnUnitsDeployedInTurn,
    OpponentAllianceInfluenceAtLeast,
    OpponentPlayedCombatIntrigue,
    PassTurn,
    PayResources,
    PeekTopCard,
    PermanentRevealPersuasion,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RedirectSpiesOnTurnSpace,
    Research,
    RetreatTroops,
    RevealContractsTakeOne,
    RevealPersuasionThisRound,
    Reward,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    SolariAtLeast,
    SpiceAtLeast,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TechTilesAtLeast,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
    Trigger,
    TriggeredByFaction,
    WaterAtLeast,
)
from dune_imperium.content.uprising.intrigue import IntrigueCardEntry
from dune_imperium.content.uprising.types import AgentIcon, BattleIcon
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

_FACTION_NAMES_KO: dict[Faction, str] = {
    Faction.EMPEROR: "황제",
    Faction.SPACING_GUILD: "우주 항행 길드",
    Faction.BENE_GESSERIT: "베네 게세리트",
    Faction.FREMEN: "프레멘",
}

_BATTLE_ICON_NAMES_KO: dict[BattleIcon, str] = {
    # Crysknife / Desert Mouse / Ornithopter | 크리스나이프 / 사막쥐 / 오니솝터
    # [Main p. 20]; wild battle icon | 와일드 배틀 아이콘 [Bloodlines p. 5]
    # (bare "와일드", matching the project's own skirmish_wild usage).
    BattleIcon.CRYSKNIFE: "크리스나이프",
    BattleIcon.DESERT_MOUSE: "사막쥐",
    BattleIcon.ORNITHOPTER: "오니솝터",
    BattleIcon.WILD: "와일드",
}

# The seven Agent icons a board space or card can print, plus Spy — the
# glossary's own "Agent 아이콘 분류" table ([Board Guide pp. 1-2]) matches
# ``AgentIcon``'s members exactly. English's own text for this (below) is
# just the enum's raw lowercase value ("emperor", "spy", ...), not a
# rendered icon graphic (no ICON_RULES rule matches those bare words), so
# Korean uses the plain glossary word too rather than a {term} icon
# placeholder — that keeps parity with what English actually shows.
_AGENT_ICON_NAMES_KO: dict[AgentIcon, str] = {
    AgentIcon.EMPEROR: "황제",
    AgentIcon.SPACING_GUILD: "우주 항행 길드",
    AgentIcon.BENE_GESSERIT: "베네 게세리트",
    AgentIcon.FREMEN: "프레멘",
    AgentIcon.LANDSRAAD: "랜드스래드",
    AgentIcon.CITY: "도시",
    AgentIcon.SPICE_TRADE: "스파이스 거래",
    AgentIcon.SPY: "스파이",
}

_TIMING_LABELS_KO: dict[IntrigueTiming, str] = {
    # PLOT/COMBAT/ENDGAME timing headers | 음모/전투/종료 단계
    # (`docs/rules/glossary-ko.md`: "Plot / Combat / Endgame Intrigue | 음모 /
    # 전투 / 종료 단계 책략 카드", `[Main p. 7]`; korean-card-style.md
    # rule 7).
    IntrigueTiming.PLOT: "음모",
    IntrigueTiming.COMBAT: "전투",
    IntrigueTiming.ENDGAME: "종료 단계",
}



def _object_particle(word: str) -> str:
    """을 after a final consonant, 를 after a vowel (the Hangul syllable's
    final-consonant slot); a card name read aloud takes the same particle."""

    last = word.rstrip()[-1:]
    if "가" <= last <= "힣":
        return "을" if (ord(last) - ord("가")) % 28 else "를"
    return "을"

def _faction_name_ko(faction: Faction) -> str:
    return _FACTION_NAMES_KO[faction]


def _reserve_card_name_ko(card_id: str) -> str:
    """The referenced card's Korean print name, or the English id's fallback.

    Mirrors ``effect_dsl_text.py``'s own English fallback
    (``card_id.replace('_', ' ').title()``) when no Korean print is known,
    so an untranslated card degrades the same way in both languages rather
    than Korean inventing a translation the print never confirmed.
    """

    korean = KOREAN_CARD_NAMES["cards"].get(card_id)
    if korean is not None:
        return korean
    return card_id.replace("_", " ").title()


def _retreat_troops_text_ko(troops: RetreatTroops) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``_retreat_troops_text``.

    Icon parity (2026-09-25 full-catalog sweep, ``scripts/e2e/
    effect_text.py``) drives every branch here, not the Korean print: a
    bare "troops" word (no adjacent digit) still hits ``ICON_RULES``' bare
    troop rule, so the unlimited case uses bare ``{troop}``, not the plain
    word "병력", even though the print form ("병력 1 또는 2 후퇴", Reach
    Agreement, ``korean-card-style.md`` row 36) never shows an icon. The two-value
    range case is the odder one: English's own "Retreat 1-2 troops" only
    lets the *second* number's regex match ("1-2 troops" — the "1-" breaks
    the counted-troop pattern, so only "2 troops" hits it), so English
    renders exactly one counted troop icon, using the maximum and silently
    showing no icon for the minimum; this mirrors that quirk exactly
    (``{troop:maximum}``, the minimum a plain digit) rather than "fixing" it
    to show both counts, which would show MORE than English actually
    renders. "원하는 수만큼" (as many as you like) for the unlimited case is
    ordinary grammar, not a glossary phrase — the glossary has no fixed
    idiom for "any number of".
    """

    if troops.maximum is None:
        if troops.minimum == 1:
            return "{troop} 원하는 수만큼 {retreat}"
        return f"{{troop}} 원하는 수만큼 {{retreat}} ({troops.minimum} 이상)"
    if troops.minimum == troops.maximum:
        return f"{{troop:{troops.minimum}}} {{retreat}}"
    return f"병력 {troops.minimum} 또는 {{troop:{troops.maximum}}} {{retreat}}"


def _place_spy_text_ko(spy: PlaceSpy) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``_place_spy_text``."""

    if spy.shared_post:
        return "{spy} 배치 (다른 플레이어의 {spy}와 관측소 공유 가능)"
    if spy.factions is not None:
        names = " 또는 ".join(_faction_name_ko(faction) for faction in spy.factions)
        return f"{{spy}} 배치 ({names} 관측소)"
    return "{spy} 배치"


def _recall_spy_text_ko(count: int) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``RecallSpy`` cost text.

    Same bare-icon reasoning as ``display/structs.py``'s own
    ``_recall_spy_text_ko`` (not imported from there — every ``display``
    Korean module keeps its own small local helpers rather than reaching
    across module boundaries, the same way ``effect_dsl_text.py`` keeps its
    own local ``_plural`` instead of importing ``structs.py``'s): English's
    "recall 2 Spies" still draws one bare Spy icon, never a numbered or
    distinct "recall" icon, so this uses bare ``{spy}`` with the count as a
    plain digit and this project's own established recall verb "소환"
    (``static/labels.js`` ``recall_spy_for_agent_card``: "{spy} 소환").
    """

    if count == 1:
        return "{spy} 소환"
    return f"{{spy}} {count} 소환"


def _gain_influence_text_ko(gain: GainInfluence) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``_gain_influence_text``.

    Mirrors it field-for-field — only ``factions``/``times``/``distinct``,
    the same three fields the English renderer reads. ``GainInfluence`` also
    carries ``where_opponent_leads``/``different_from_trigger``/
    ``minimum_own`` (Navigation card 1's "a different Faction where you
    have 2+ Influence"), which the English text does not render either; this
    twin intentionally leaves them out too; a wrong Korean line here would
    be inventing detail the English catalog never shows, not fixing a gap
    (out of this task's scope — a display gap, not a rules question).
    Non-distinct/"any Faction" wording quotes ``display/structs.py``'s own
    ``_choose_influence_text_ko`` ("4개의 팩션 중 하나", "각기 다른 팩션 중
    하나"); an explicit Faction subset joins with "또는" (korean-card-style.md rule
    6's "—OR—" → "—또는—", extended to an inline word list).
    """

    if gain.factions is not None and len(gain.factions) == 1:
        return f"{{influence_{gain.factions[0].value}:{gain.times}}}"
    if gain.factions is None:
        choice = "각기 다른 팩션 중 하나" if gain.distinct else "4개의 팩션 중 하나"
    else:
        names = " 또는 ".join(_faction_name_ko(faction) for faction in gain.factions)
        choice = f"각기 다른 {names} 중 하나" if gain.distinct else f"{names} 중 하나"
    if gain.times == 1:
        return f"{{influence_any:1}} ({choice} 선택)"
    return f"{{influence_any:{gain.times}}} (매번 {choice} 선택)"


def condition_text_ko(condition: Condition) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``condition_text``.

    Renders one full Korean conditional clause (ending in ``-다면``/
    ``-(이)면``, no leading "if" word, no trailing colon — see this module's
    own docstring); ``section_text_ko`` appends ``": " + body``.
    """

    match condition:
        case InfluenceAtLeast(faction=faction, amount=amount):
            return f"{{influence_{faction.value}}} {amount} 이상이면"
        case HasHighCouncil():
            # Quotes ``display/tokens_ko.py``'s ``reveal_effect_text_ko``
            # ("High Council" clause), itself sourced from the glossary's
            # "High Council | 원로회 / 원로회 자리" ([Main p. 17]).
            return "원로회 자리를 보유했다면"
        case HasAlliance():
            return "{alliance}이 있다면"
        case InNavigationSlot(slot=slot):
            # "이 카드가 운항 구획 4에 놓여 있었다면:" — Navigation Card 3's
            # own Korean print (`[KO card: Navigation Card 3]`; Navigation
            # Card 4 confirms the same phrase for slot 1). "구획" (slot) has
            # no rulebook citation — the four DiU rulebooks never describe
            # a Navigation card's position this way — so it is sourced to
            # the card print alone, per the new `[KO card: ...]` source
            # kind (`docs/rules/glossary-ko.md`, "출처와 방법").
            return f"이 카드가 운항 구획 {slot}에 놓여 있었다면"
        case TriggeredByFaction(faction=faction):
            # "우주 항행 길드에 대한 영향력이 2에 도달한 결과로 이 카드를
            # 플레이했다면:" — Navigation Card 8's own Korean print
            # (`[KO card: Navigation Card 8]`), generalized to the other
            # three Factions. {influence_any:2}, counted: English's own
            # text actually renders a COUNTED any-Influence icon here
            # ("reaching 2 Influence with the X" — the digit sits directly
            # before "Influence", hitting ICON_RULES' generic counted rule,
            # not the Faction-specific bare one), confirmed by the
            # 2026-09-25 full-catalog sweep (an earlier bare {influence_any}
            # here under-drew English's icon by one).
            return (
                f"{_faction_name_ko(faction)}에 대한 {{influence_any:2}}에 "
                "도달한 결과로 이 카드를 플레이했다면"
            )
        case SpiesPlacedAtLeast(count=count):
            # Quotes ``tokens_ko.py``'s established "{spy}를 N 이상
            # 배치했다면" (its own ``reveal_effect_text_ko``).
            return f"{{spy}}를 {count} 이상 배치했다면"
        case CompletedContractsAtLeast(count=count):
            # "당신이 계약을 둘 이상 완수했다면:" (Backed by CHOAM) / "당신이
            # 계약을 넷 이상 완수했다면:" (CHOAM Profits) — two independent
            # Korean card prints (`[KO card: Backed by CHOAM]`, `[KO card:
            # CHOAM Profits]`) confirm this specific condition always uses
            # a native-Korean numeral, not a digit (korean-card-style.md rule 5's
            # own example is this exact phrase). The bare {contract} icon
            # replaces the print's plain word "계약": English's own
            # "Contracts" hits ICON_RULES' bare Contract rule (no numeric
            # capture group), so English shows the Contract icon here too
            # — the print has no icon at all (it's a text-only condition
            # line), so this follows the render (parity with what English
            # actually shows), not the print's word choice.
            return f"당신이 {{contract}}을 {_contract_count_ko(count)} 이상 완수했다면"
        case SandwormsInConflictAtLeast(count=1):
            return "{conflict}에 {sandworm}가 있다면"
        case SandwormsInConflictAtLeast(count=count):
            return f"{{conflict}}에 {{sandworm}}가 {count} 이상 있다면"
        case GainedSpiceThisTurn(amount=amount):
            # Quotes ``display/actions.py``'s ``_ICON_CONDITIONS_KO`` (same
            # underlying condition, a parenthetical suffix there): "이번
            # 차례에 {spice}를 2 이상 얻었다면".
            return f"이번 차례에 {{spice}}를 {amount} 이상 얻었다면"
        case SpiceMustFlowCardsAtLeast(count=count):
            name = _reserve_card_name_ko("the_spice_must_flow")
            return f"당신이 {name}{_object_particle(name)} {count} 이상 보유했다면"
        case OpponentAllianceInfluenceAtLeast(amount=amount):
            # No adjacent digit+"Influence" in English's own text ("N or
            # more Influence on a..."), so ICON_RULES draws no icon there
            # either — plain word "영향력" matches that.
            return (
                "다른 플레이어가 {alliance} 토큰을 가진 팩션에서 영향력이 "
                f"{amount} 이상이면"
            )
        case WaterAtLeast(amount=amount):
            return f"{{water}} {amount} 이상이면"
        case CommandersInConflictAtLeast(count=count):
            # Quotes ``tokens_ko.py``'s established "{conflict}에
            # {commander}이 N 이상 있다면".
            return f"{{conflict}}에 {{commander}}이 {count} 이상 있다면"
        case TechTilesAtLeast(count=count):
            # Quotes ``tokens_ko.py``'s established "{tech_tile} N 이상이면".
            return f"{{tech_tile}} {count} 이상이면"
        case GeneticMarkersAtLeast(count=count):
            # Quotes ``tokens_ko.py``'s established "유전자 마커 N개에
            # 도달했다면" (no {term} placeholder there either — no TERMS
            # entry exists for genetic markers).
            return f"유전자 마커 {count}개에 도달했다면"
        case SolariAtLeast(amount=amount):
            return f"{{solari}} {amount} 이상이면"
        case SpiceAtLeast(amount=amount):
            return f"{{spice}} {amount} 이상이면"
        case OpponentPlayedCombatIntrigue():
            # {intrigue} (책략 카드) matches ICON_RULES' own bare "Intrigue
            # card" rule, which fires inside English's "Combat Intrigue
            # card" too (the substring "Intrigue card" still matches).
            return "다른 플레이어가 이 {conflict}에서 전투 {intrigue}를 플레이했다면"
        case AllConditions(conditions=conditions):
            # Quotes ``tokens_ko.py``'s established "그리고" join of several
            # already-complete conditional clauses (its own
            # ``reveal_effect_text_ko``).
            return " 그리고 ".join(condition_text_ko(item) for item in conditions)
        case _:
            assert_never(condition)


def _contract_count_ko(count: int) -> str:
    """Native-Korean numeral for a small Contract-completion threshold.

    Quotes two independent Korean card prints (see ``condition_text_ko``'s
    ``CompletedContractsAtLeast`` case): "둘" for 2, "넷" for 4. No card in
    the current catalog uses a threshold this table does not cover; a count
    outside it falls back to the digit (``docs/rules/korean-card-style.md``'s own "when
    unsure, default to the digit" rule) rather than guessing a native
    numeral no print has confirmed.
    """

    native = {1: "하나", 2: "둘", 3: "셋", 4: "넷"}
    return native.get(count, str(count))


def cost_text_ko(cost: Cost) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``cost_text``."""

    match cost:
        case PayResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{{solari:{solari}}}")
            if spice:
                parts.append(f"{{spice:{spice}}}")
            if water:
                parts.append(f"{{water:{water}}}")
            # "Paying a cost | 비용 지불" [Main p. 20]; SOV order puts the
            # verb after the joined resource list.
            return ", ".join(parts) + " 지불"
        case LoseInfluence(count=count):
            # {influence_lose} is the client's own combined "Lose N
            # Influence" icon (``ICON_RULES``' "Lose (\d+) Influence" rule),
            # so the count belongs inside the placeholder here.
            return f"{{influence_lose:{count}}}"
        case LoseTroops(from_conflict=from_conflict):
            # "Lose (troops) | 잃다" [Bloodlines p. 12]. English's own
            # ``_plural(count, "troop")`` helper renders only the noun
            # ("troop"/"troops"), never the actual ``count`` digit, so
            # "Lose 3 troops" prints as plain "Lose troops" with no visible
            # number — bare ``{troop}`` matches the bare (uncounted) icon
            # that quirk draws (2026-09-25 full-catalog sweep); a
            # ``{troop:count}`` here would show Korean players a number
            # English itself never displays. Pre-existing English gap, not
            # fixed here (out of this step's scope — a display gap, not a
            # rules question).
            where = "{conflict}에서 " if from_conflict else ""
            return f"{where}{{troop}} 잃음"
        case GiveIntrigueToOpponent(bonus_spice_if_not_twisted=bonus):
            extra = (
                f" (뒤틀린 책략 카드가 아니면 +{{spice:{bonus}}})" if bonus else ""
            )
            return f"다른 플레이어에게 핸드의 {{intrigue}} 줌{extra}"
        case TrashIntrigueCard(troops_if_not_twisted=troops):
            # Same ``_plural`` quirk as ``LoseTroops`` above: English's
            # "(Recruit troop if it is not a Twisted card)" never shows the
            # actual count either, so bare ``{troop}``, not ``{troop:N}``.
            extra = " (뒤틀린 책략 카드가 아니면 {troop})" if troops else ""
            return f"핸드에서 {{trash_intrigue}}{extra}"
        case DiscardFromHand(count=1):
            return "카드 1장 {discard}"
        case DiscardFromHand(count=count):
            return f"카드 {count}장 {{discard}}"
        case RecallSpy(count=count):
            return _recall_spy_text_ko(count)
        case RetreatTroops() as troops:
            return _retreat_troops_text_ko(troops)
        case FlipBattleCard(icon=icon):
            icon_name = _BATTLE_ICON_NAMES_KO[icon]
            # "Flip (a Tech tile) | 뒤집기" [Bloodlines p. 12] — the same
            # terse nominal verb reused for a Conflict card.
            return f"이긴 {{conflict}} 카드 하나 뒤집기 ({icon_name} 아이콘)"
        case FlipFaceUpConflictCard(count=1):
            return "이긴 앞면 {conflict} 카드 하나 뒤집기"
        case FlipFaceUpConflictCard(count=count):
            return f"이긴 앞면 {{conflict}} 카드 {count}장 뒤집기"
        case TrashDiscardPileCard(minimum_cost=minimum_cost):
            # "비용이 1 이상인 카드를 폐기했다면:" — Navigation Card 5's own
            # Korean print (`[KO card: Navigation Card 5]`, korean-card-style.md
            # row 49), reused here for "or more" on a cost.
            return f"{{discard_pile}}에서 비용이 {minimum_cost} 이상인 카드 {{trash}}"
        case _:
            assert_never(cost)


def reward_text_ko(reward: Reward) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``reward_text``."""

    match reward:
        case GainResources(solari=solari, spice=spice, water=water):
            parts = []
            if solari:
                parts.append(f"{{solari:{solari}}}")
            if spice:
                parts.append(f"{{spice:{spice}}}")
            if water:
                parts.append(f"{{water:{water}}}")
            return ", ".join(parts)
        case GainVictoryPoints(amount=amount):
            return f"{{victory_point:{amount}}}"
        case RecruitTroops(count=count):
            return f"{{troop:{count}}}"
        case DrawPersonalCards(count=count):
            return f"{{draw:{count}}}"
        case DrawIntrigueCards(count=count):
            return f"{{intrigue:{count}}}"
        case GainCombatStrength(amount=amount):
            return f"{{sword:{amount}}}"
        case GainInfluence() as gain:
            return _gain_influence_text_ko(gain)
        case DestroyShieldWall():
            return "{shield_wall} 제거"
        case SummonSandworm(count=count, requires_maker_hooks=requires_maker_hooks):
            # "모래벌레 1마리를 불러서 배치합니다" [Main p. 20] — verb 부르다,
            # counter 마리, **not** 소환 (glossary: "Sandworm (summon) |
            # 부르다 — '소환'이 아님").
            text = f"{{sandworm}} {count}마리 부름"
            if requires_maker_hooks:
                text += " ({maker_hooks} 필요)"
            return text
        case DeployFromGarrison(up_to=up_to):
            # "Deploy (to the Conflict) | 배치" [Main p. 10], [Main p. 20].
            return f"{{troop:{up_to}}} 배치"
        case TrashPersonalCard():
            return "카드 1장 {trash}"
        case PlaceSpy() as spy:
            return _place_spy_text_ko(spy)
        case RetreatTroops() as troops:
            return _retreat_troops_text_ko(troops)
        case TakeContract(count=count):
            # Quotes ``display/structs.py``'s established "{contract} N개
            # 가져옴" (its own ``contract_reward_text_ko``).
            return f"{{contract}} {count}개 가져옴"
        case AcquireCardUpTo(max_cost=max_cost, to_hand_if=to_hand_if):
            base = f"비용이 {max_cost} 이하인 카드 {{acquire}}"
            if to_hand_if is None:
                return base
            return f"{base} ({condition_text_ko(to_hand_if)}: 핸드로)"
        case CommanderDiscountThisTurn(amount=amount):
            return f"이번 차례에 {{commander}} 소집(획득 포함) 비용이 {amount} 감소"
        case IgnoreInfluenceRequirementsThisTurn():
            return "이번 차례에 {agent}를 보낼 때 게임판 장소의 영향력 요구사항 무시"
        case GrantAgentIconThisTurn(icon=icon):
            # "이번 차례에 당신이 플레이하는 카드는 [아이콘] 아이콘 보유." —
            # Emperor's Invitation's own Korean print (`[KO card: Emperor's
            # Invitation]`, docs/rules/korean-card-style.md row 44).
            name = _AGENT_ICON_NAMES_KO[icon]
            return f"이번 차례에 당신이 플레이하는 카드는 {name} 아이콘 보유"
        case GrantCombatDeployment():
            # Quotes ``tokens_ko.py``'s established "{combat} (전투 장소에
            # 보낸 것처럼 배치 가능)" (its own ``reveal_effect_text_ko``,
            # same underlying icon).
            return "{combat} (전투 장소에 보낸 것처럼 배치 가능)"
        case GainSolariPerUnitType():
            return "{conflict}에 있는 부대 종류마다 {solari:1}"
        case PeekTopCard():
            # "언제든지 당신의 카드덱 맨 위 카드 1장 확인 가능." — Glowglobes'
            # own Korean print (`[KO card: Glowglobes]`, docs/rules/korean-card-style.md
            # row 47) for "look at the top card of your deck". The final
            # "draw it" is the plain word "뽑기", not the {draw} icon:
            # English's own "...to draw it" names no card/count next to
            # "draw", so no ICON_RULES rule matches it either (only "Draw N
            # card(s)" has a rule) — no icon there in English (2026-09-25
            # full-catalog sweep).
            return (
                "{deck} 맨 위 카드 확인: 되돌리거나 {discard}하거나 "
                "{solari:1} 지불해 뽑기"
            )
        case GrantAgentIconsThisTurn(icons=icons):
            names = ", ".join(_AGENT_ICON_NAMES_KO[icon] for icon in icons)
            return f"이번 차례에 당신이 플레이하는 카드는 {names} 아이콘 보유"
        case PassTurn():
            return "차례 시작 시: 차례 넘기기"
        case PermanentRevealPersuasion(amount=amount):
            # "이제부터 매 라운드의 자기 공개 차례 동안 [1] ." — Navigation
            # Card 3's own Korean print for this exact effect
            # (`[KO card: Navigation Card 3]`; the class's own docstring
            # names it "Navigation card 3 in slot 4").
            return (
                f"이제부터 매 라운드의 자기 {{reveal_turn}} 동안 "
                f"{{persuasion:{amount}}}"
            )
        case AcquireReserveCard(card_id=card_id):
            # "스파이스는 흘러야 한다 획득." — Navigation Card 4's own Korean
            # print (`[KO card: Navigation Card 4]`; the class's own
            # docstring names it "Navigation card 4").
            return f"{_reserve_card_name_ko(card_id)} {{acquire}}"
        case AcquireTech(discount=0):
            # "Acquire Tech | 기술 획득" [Bloodlines p. 12].
            return "{tech_tile} {acquire}"
        case AcquireTech(discount=discount):
            return f"{{tech_tile}} {{acquire}} ({{spice:{discount}}} 할인)"
        case RedirectSpiesOnTurnSpace():
            # Vocabulary quotes ``tokens_ko.py``'s
            # ``EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY`` entry (same
            # "spying on the space you sent an Agent to" construction):
            # "이번 차례에 당신이 {agent}를 보낸 장소를 정탐 중인 다른
            # 플레이어는 그 {spy}를 이동해야 함".
            return (
                "이번 차례에 당신이 {agent}를 보낸 장소를 정탐 중인 다른 "
                "플레이어 각자 그 {spy}를 이동해야 함. 그 후 그 장소에 {spy} 배치"
            )
        case RevealContractsTakeOne(count=count):
            # Plain word "계약", not the {contract} icon: English's own
            # text lowercases it ("Reveal N contracts from the bank"), and
            # ICON_RULES' Contract rule is case-sensitive (`\bContracts?\b`,
            # capital C only) — English draws no icon here either
            # (2026-09-25 full-catalog sweep).
            return f"은행에서 계약 {count}개 공개: 하나 가져오고 나머지 {{trash}}"
        case SetAsideImperiumRowCard(discount=discount):
            # "set aside (나중에 쓰려고 빼 둔 카드, Manipulate) | 따로
            # 빼두다" [Immortality p. 14] — the same later-use sense as this
            # reward, not Shaddam's Contract-specific "따로 치워두다".
            return (
                "{imperium_row} 카드 하나 따로 빼둠 (이번 라운드에 자신에게 "
                f"{{persuasion:{discount}}} 할인)"
            )
        case Research():
            # Quotes ``tokens_ko.py``'s established "{research} (연구 트랙
            # 전진)" (its own ``reveal_effect_text_ko``).
            return "{research} (연구 트랙 전진)"
        case AdvanceTleilaxu(count=1):
            # Quotes ``tokens_ko.py``'s established "{tleilaxu} (트랙 전진)".
            return "{tleilaxu} (트랙 전진)"
        case AdvanceTleilaxu(count=count):
            return f"{{tleilaxu}} ×{count} (트랙 {count}칸 전진)"
        case GenerateSpecimens(count=count):
            # Quotes ``tokens_ko.py``'s established "표본 N개 생성" (plain
            # word, not a {specimen} icon placeholder — English's own
            # "Generate N specimens" draws no icon either; no ICON_RULES
            # rule matches "specimen").
            return f"표본 {count}개 생성"
        case AcquireTleilaxuCard():
            return "틀레이락스 카드 {acquire} 가능 (표본 비용 지불)"
        case RevealPersuasionThisRound(amount=amount):
            return f"이번 라운드 자기 {{reveal_turn}}에 {{persuasion:{amount}}}"
        case _:
            assert_never(reward)


def trigger_text_ko(trigger: Trigger) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``trigger_text``."""

    match trigger:
        case OnRevealAcquisitionThisRound():
            # "whenever" | 때마다 — glossary's Gather Intelligence entry
            # ("당신이 게임판 장소에 에이전트를 보낼 때마다", `[Main p. 11]`),
            # the project's only attested "whenever" citation.
            return "이번 라운드에 자기 {reveal_turn} 동안 카드를 획득할 때마다"
        case OnUnitsDeployedInTurn(minimum=minimum):
            # units (병력 + 모래벌레) | 부대 [Main p. 10].
            return f"한 차례에 부대를 {minimum} 이상 배치할 때"
        case OnTroopsLostAtConflictEnd(minimum=minimum):
            return f"{{conflict}} 종료 시 {{troop}}을 {minimum} 이상 잃을 때"
        case _:
            assert_never(trigger)


def section_text_ko(section: EffectSection) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``section_text``.

    The arrow is always the ``{arrow_right}`` TERM, never a literal "→"
    character (``display/structs.py``'s ``_optional_trade_text_ko``
    docstring explains why: ``phrase()`` only expands ``{term}``
    placeholders, so a bare arrow in generated Korean text would stay
    plain, unlike English's own "→", which ``iconize()``'s own rule always
    turns into the arrow icon — a render-parity blocker otherwise).
    """

    rewards = ", ".join(reward_text_ko(reward) for reward in section.rewards)
    if section.costs:
        costs = ", ".join(cost_text_ko(cost) for cost in section.costs)
        body = f"{costs} {{arrow_right}} {rewards}"
    else:
        body = rewards
    if section.condition is not None:
        return f"{condition_text_ko(section.condition)}: {body}"
    return body


def option_text_ko(option: IntrigueOption) -> str:
    """Korean twin of ``effect_dsl_text.py``'s ``option_text``.

    Prefixed by the Korean timing label with the same " — " separator
    English uses, so the client's own prefix-stripping (``core.js``
    ``intrigueOptionBody()``, which looks for " — ") works on this line
    exactly as it does on the English one.
    """

    prefix = f"{_TIMING_LABELS_KO[option.timing]} — "
    body = "; ".join(section_text_ko(section) for section in option.sections)
    if option.trigger is not None:
        return f"{prefix}{trigger_text_ko(option.trigger)}: {body}"
    return f"{prefix}{body}"


def intrigue_card_text_ko(entry: IntrigueCardEntry) -> list[str]:
    """Render one Korean line per printed Intrigue option, entry.text's twin.

    Same length and order as ``effect_dsl_text.py``'s ``intrigue_card_text``
    — index ``i`` here is option ``i``'s Korean line — so the catalog's
    ``intrigue[id].text_ko[i]`` lines up with ``text[i]`` for the client's
    ``play_intrigue``/``play_navigation`` option rows (``core.js``
    ``describeAction()``).
    """

    return [option_text_ko(option) for option in entry.options]
