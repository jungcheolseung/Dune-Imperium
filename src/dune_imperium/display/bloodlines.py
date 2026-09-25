"""English display text for the Bloodlines Skill tiles and Tech tiles.

The engine's typed definitions (``content/bloodlines``) are rendered into
the short lines the browser catalog shows; the wording follows the tile
faces transcribed in ``docs/rules/bloodlines.md``.
"""

from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.sardaukar import SkillDefinition
from dune_imperium.content.bloodlines.tech import TechAbility, TechTile

TECH_ABILITY_TEXT: Final = MappingProxyType(
    {
        TechAbility.FLIP_DRAW_INTRIGUE: "Flip → Draw 1 Intrigue card",
        TechAbility.CONTRACT_COMPLETION_DRAW: (
            "When you complete a contract: Draw 1 card. Endgame: 1 VP if you "
            "have completed four or more contracts"
        ),
        TechAbility.COMMAND_TWO_SOLARI: "Reveal Turn: Command (6+): Gain 2 solari",
        TechAbility.FORBIDDEN_WEAPONS: (
            "Reveal Turn: You must choose: +3 swords and lose 1 Influence — or — "
            "lose all your spice and trash this"
        ),
        TechAbility.INTRIGUE_STEAL_PROTECTION: (
            "Your Intrigue cards can't be stolen unless you have five or more"
        ),
        TechAbility.PEEK_TOP_CARD: (
            "You may look at the top card of your deck at any time"
        ),
        TechAbility.SPACE_DISCOUNT: "Board spaces cost you 1 spice or 1 solari less",
        TechAbility.ORNITHOPTER_ICONS: "All of your battle icons are Ornithopter",
        TechAbility.PANOPTICON: (
            "Reveal Turn: Place a Spy, Gain 1 troop. Endgame: Gain 1 Influence "
            "with each Faction where you have 1 or less Influence"
        ),
        TechAbility.CONFLICT_WIN_DRAW: "When you win a Conflict: Draw 1 card",
        TechAbility.PLASTEEL_BLADES: (
            "Whenever you recruit a Sardaukar Commander: Trash this → Gain an "
            "additional Sardaukar Commander Skill"
        ),
        TechAbility.FLIP_COMBAT_ICON: "Agent Turn: Flip → Combat icon",
        TechAbility.COMMANDER_DISCOUNT: (
            "Recruiting a Sardaukar Commander (including when you acquire one) "
            "costs you 1 solari less"
        ),
        TechAbility.REVEAL_PERSUASION: "Reveal Turn: +1 Persuasion",
        TechAbility.SIGNET_FACTION_ICONS: (
            "Your Signet Ring has the Emperor, Spacing Guild, Bene Gesserit and "
            "Fremen icons"
        ),
        TechAbility.FLIP_SOLARI_AND_TRASH: (
            "Flip → Gain 1 solari, and if you recalled a Spy this turn: trash a card"
        ),
        TechAbility.INTRIGUE_DRAW_TROOP: (
            "For each Intrigue card you draw or steal during your turn: Gain 1 "
            "troop, deploy it to the Conflict"
        ),
        TechAbility.COMMAND_TWO_STRENGTH: "Reveal Turn: Command (6+): +2 swords",
    }
)

# Korean twin of TECH_ABILITY_TEXT (feature decided 2026-09-25, Step K4: the
# effect text the engine *generates* gets a Korean version; printed card
# wording stays English). Word choice follows only
# docs/rules/glossary-ko.md or ordinary Korean grammar, and icon placeholders
# follow the same "counted vs. bare, per what ICON_RULES actually matches
# for the matching English wording" policy display/tokens_ko.py's module
# docstring sets out — "Command (6+):" has no digit adjacent to the word
# "Persuasion" (unlike "Command (6+ Persuasion):" elsewhere, which does), so
# it draws no Persuasion icon in English and none here either; "trash this"
# always means the Tech tile itself, "이 타일 {trash}" (타일 is the tail
# noun of the glossary's own "기술 타일" compound, not a new term); a lower-
# case, non-capitalized "a contract"/"contracts" never matches ICON_RULES'
# capital-only Contract rule (tokens_ko.py's own precedent for this exact
# wording), so it stays the plain word 계약, never {contract}.
TECH_ABILITY_TEXT_KO: Final = MappingProxyType(
    {
        TechAbility.FLIP_DRAW_INTRIGUE: "뒤집기 {arrow_right} {intrigue:1}",
        TechAbility.CONTRACT_COMPLETION_DRAW: (
            "계약을 완수할 때마다: {draw:1}. {endgame}: 계약을 넷 이상"
            " 완수했다면 {victory_point:1}"
        ),
        TechAbility.COMMAND_TWO_SOLARI: "{reveal_turn}: {command} (6+): {solari:2}",
        # "lose 1 Influence" is lower-case, mid-sentence — ICON_RULES' own
        # "Lose (\d+) Influence" rule is capital-only and does not match
        # here (it only matches a line whose "Lose" opens the sentence),
        # so this falls through to the generic bare "(\d+) Influence" rule
        # and draws the {influence_any} icon, not {influence_lose} (2026-
        # 09-25 review, caught live by scripts/e2e/effect_text.py's icon-
        # parity sweep). "You must choose" is mandatory, not a free
        # option — the Korean print reads "다음 중 하나 반드시 선택:"
        # [KO card: Forbidden Weapons], and both options end in the same
        # terse nominal 잃음 (cardstyle.md), not a mix of 잃기/잃음.
        TechAbility.FORBIDDEN_WEAPONS: (
            "{reveal_turn}: 다음 중 하나 반드시 선택: +{sword:3},"
            " {influence_any:1} 잃음 / {spice} 전부 잃음, 이 타일 {trash}"
        ),
        # "도난" is not a glossary word; Steal Intrigue's own verb is
        # 훔치다 (glossary-ko.md: "Steal Intrigue | 책략 훔치기"
        # `[Main p. 20]`). This line follows the Korean Gene Locked Vault
        # print itself: "당신이 책략 카드를 5장 이상 갖고 있지 않다면,
        # 당신의 책략 카드는 훔쳐질 수 없음" [KO card: Gene Locked Vault]
        # — with only its second "책략 카드" as {intrigue}, since English
        # draws exactly one bare Intrigue icon here (render.js's
        # "Intrigue cards?" rule matches "Intrigue cards can't be stolen"
        # once; "five or more" is a word, not a digit, so the count draws
        # no icon and stays the plain phrase).
        TechAbility.INTRIGUE_STEAL_PROTECTION: (
            "당신이 책략 카드를 5장 이상 갖고 있지 않다면, 당신의 {intrigue}는"
            " 훔쳐질 수 없음"
        ),
        TechAbility.PEEK_TOP_CARD: "언제든지 당신의 카드덱 맨 위 카드 1장 확인 가능",
        TechAbility.SPACE_DISCOUNT: (
            "게임판 장소 비용이 당신에게 {spice:1} 또는 {solari:1} 덜 듦"
        ),
        # TERMS.battle_icon carries no icon (icon: null), so the client
        # prints the bare word "배틀 아이콘" and the particle must agree
        # with its consonant-ending noun (이, not 는). The Korean Ornithopter
        # Fleet print reads "당신이 보유한 모든 배틀 아이콘이 [오니솝터]
        # 가 됨." [KO card: Ornithopter Fleet].
        TechAbility.ORNITHOPTER_ICONS: (
            "당신이 보유한 모든 {battle_icon}이 오니솝터가 됨"
        ),
        # "각 팩션" needs its own location particle and a verb — the
        # Korean print reads "당신의 영향력이 1 이하인 각 팩션에서 영향력을
        # 1씩 얻습니다" [KO card: Panopticon].
        TechAbility.PANOPTICON: (
            "{reveal_turn}: {spy} 배치, {troop:1}. {endgame}: 영향력이 1"
            " 이하인 각 팩션에서 {influence_any:1}씩 얻음"
        ),
        TechAbility.CONFLICT_WIN_DRAW: "{conflict}에서 승리할 때마다: {draw:1}",
        # "Gain" here is Plasteel Blades' own printed verb, not the
        # rulebook's default 얻다 — the Korean print reads "사다우카
        # 지휘관 기술 토큰 1개 추가 획득" [KO card: Plasteel Blades].
        TechAbility.PLASTEEL_BLADES: (
            "사다우카 지휘관을 소집할 때마다: 이 타일 {trash} {arrow_right}"
            " {commander_skill} 추가로 획득"
        ),
        TechAbility.FLIP_COMBAT_ICON: "{agent_turn}: 뒤집기 {arrow_right} 전투 아이콘",
        TechAbility.COMMANDER_DISCOUNT: (
            "사다우카 지휘관 소집(획득할 때 포함) 비용이 당신에게 {solari:1} 덜 듦"
        ),
        TechAbility.REVEAL_PERSUASION: "{reveal_turn}: +{persuasion:1}",
        TechAbility.SIGNET_FACTION_ICONS: (
            "당신의 {signet_ring}에는 황제, 우주 항행 길드, 베네 게세리트,"
            " 프레멘 아이콘이 있음"
        ),
        TechAbility.FLIP_SOLARI_AND_TRASH: (
            "뒤집기 {arrow_right} {solari:1}, 이번 차례에 {spy}를 소환했다면:"
            " 카드 1장 {trash}"
        ),
        TechAbility.INTRIGUE_DRAW_TROOP: (
            "이번 차례에 {intrigue}를 뽑거나 훔칠 때마다: {troop:1}, {conflict}에 배치"
        ),
        TechAbility.COMMAND_TWO_STRENGTH: "{reveal_turn}: {command} (6+): +{sword:2}",
    }
)


def skill_effect_text(skill: SkillDefinition) -> str:
    """Render one Skill tile's printed effect."""

    parts: list[str] = []
    if skill.reveal_persuasion:
        parts.append(f"Reveal Turn: +{skill.reveal_persuasion} Persuasion")
    if skill.reveal_spice:
        parts.append(f"Reveal Turn: Gain {skill.reveal_spice} spice")
    if skill.reveal_water:
        parts.append(f"Reveal Turn: Gain {skill.reveal_water} water")
    if skill.trash_for_strength:
        parts.append(f"Reveal Turn: Trash this → +{skill.trash_for_strength} swords")
    if skill.strength:
        parts.append(f"+{skill.strength} sword")
    if skill.strength_if_landsraad_agent:
        parts.append(
            "If you have an Agent on a Landsraad board space: "
            f"+{skill.strength_if_landsraad_agent} swords"
        )
    if skill.strength_if_opponent_sandworm:
        parts.append(
            "If any opponent has a sandworm in the Conflict: "
            f"+{skill.strength_if_opponent_sandworm} sword"
        )
    if skill.strength_if_emperor_influence:
        parts.append(
            f"Emperor Influence {skill.emperor_influence_required}+: "
            f"+{skill.strength_if_emperor_influence} swords"
        )
    return ". ".join(parts)


def tech_acquire_text(tile: TechTile) -> str:
    """Render the tile's acquire effect (empty when the tile has none)."""

    parts: list[str] = []
    if tile.acquire_requires_spy_trash:
        parts.append("To acquire this, trash one of your Spies from the board")
    if tile.acquire_may_destroy_shield_wall:
        parts.append("You may destroy the Shield Wall")
    if tile.acquire_solari:
        parts.append(f"Gain {tile.acquire_solari} solari")
    if tile.acquire_troops:
        parts.append(
            f"Gain {tile.acquire_troops} troop{'s' if tile.acquire_troops > 1 else ''}"
        )
    if tile.acquire_intrigue:
        parts.append(f"Draw {tile.acquire_intrigue} Intrigue card")
    if tile.acquire_cards:
        parts.append(f"Draw {tile.acquire_cards} card")
    if tile.acquire_victory_points:
        parts.append(f"Gain {tile.acquire_victory_points} VP")
    if tile.acquire_contracts:
        parts.append("Gain a contract")
    if tile.acquire_influence_choice:
        parts.append("Gain 1 Influence with a chosen Faction")
    if tile.acquire_intrigue_or_card:
        parts.append("Draw 1 Intrigue card — or — Draw 1 card")
    if tile.acquire_may_trash_card:
        parts.append("You may trash a card")
    if tile.acquire_deep_cover_spies:
        parts.append(f"Place {tile.acquire_deep_cover_spies} Spies with Deep Cover")
    return ". ".join(parts)


def tech_ability_text(tile: TechTile) -> str:
    """Render the tile's ability."""

    return TECH_ABILITY_TEXT[tile.ability]


def skill_effect_text_ko(skill: SkillDefinition) -> str:
    """Korean twin of ``skill_effect_text``.

    A Skill here is a Sardaukar Commander Skill token (``content.bloodlines.
    sardaukar``); "trash this" always means that token, "이 기술 토큰
    {trash}" (glossary-ko.md: Sardaukar Commander Skill | 사다우카 지휘관
    기술 토큰, [Bloodlines p. 4]). "Landsraad" and "opponent" quote their own
    glossary rows ([Main p. 2], 랜드스래드; "다른 플레이어", not 상대,
    [Main p. 20]/[Main p. 7]). "Emperor Influence 6+:" has its digit AFTER
    "Influence" with a "+", the same non-adjacent shape as "Command (6+
    Persuasion)" — display/tokens_ko.py's own docstring example for that
    exact construction — so it is the bare {influence_emperor} icon with the
    threshold as plain trailing text, not the counted form.
    """

    parts: list[str] = []
    if skill.reveal_persuasion:
        parts.append(f"{{reveal_turn}}: +{{persuasion:{skill.reveal_persuasion}}}")
    if skill.reveal_spice:
        parts.append(f"{{reveal_turn}}: {{spice:{skill.reveal_spice}}}")
    if skill.reveal_water:
        parts.append(f"{{reveal_turn}}: {{water:{skill.reveal_water}}}")
    if skill.trash_for_strength:
        parts.append(
            f"{{reveal_turn}}: 이 기술 토큰 {{trash}} {{arrow_right}}"
            f" +{{sword:{skill.trash_for_strength}}}"
        )
    if skill.strength:
        parts.append(f"+{{sword:{skill.strength}}}")
    if skill.strength_if_landsraad_agent:
        parts.append(
            "랜드스래드 게임판 장소에 {agent}가 있다면: "
            f"+{{sword:{skill.strength_if_landsraad_agent}}}"
        )
    if skill.strength_if_opponent_sandworm:
        parts.append(
            "다른 플레이어 중 누군가 {conflict}에 {sandworm}를 가지고 있다면: "
            f"+{{sword:{skill.strength_if_opponent_sandworm}}}"
        )
    if skill.strength_if_emperor_influence:
        parts.append(
            f"{{influence_emperor}} {skill.emperor_influence_required} 이상: "
            f"+{{sword:{skill.strength_if_emperor_influence}}}"
        )
    return ". ".join(parts)


def tech_acquire_text_ko(tile: TechTile) -> str:
    """Korean twin of ``tech_acquire_text``.

    ``acquire_requires_spy_trash`` quotes ``cardstyle.md``'s own attested
    Korean print of this exact sentence (Advanced Data Analysis Tech tile):
    "이 타일을 획득하려면, 게임판에서 당신의 스파이 하나를 폐기해야 함" —
    with 스파이 swapped for the bare {spy} placeholder, since English's
    "Spies" here still draws ICON_RULES' bare Spy icon (icon parity, per
    every other generator's own rule) even though the card print itself
    spells the word out. ``acquire_may_destroy_shield_wall`` reuses 제거
    (remove), display/tokens_ko.py's own established word for taking the
    Shield Wall off the board, for the same underlying action English calls
    "destroy" here. ``acquire_contracts``' "Gain a contract" is lower-case
    and singular — ICON_RULES' Contract rule is capital-only (tokens_ko.py's
    own precedent), so this is the plain word 계약, never {contract}; the
    verb is still 가져오다 (Take a Contract, [Main p. 16]/[Main p. 20]), this
    project's one established verb for acquiring a Contract token, not 얻다.
    """

    parts: list[str] = []
    if tile.acquire_requires_spy_trash:
        parts.append(
            "이 타일을 획득하려면, 게임판에서 당신의 {spy} 하나를 {trash}해야 함"
        )
    if tile.acquire_may_destroy_shield_wall:
        parts.append("{shield_wall} 제거 가능")
    if tile.acquire_solari:
        parts.append(f"{{solari:{tile.acquire_solari}}}")
    if tile.acquire_troops:
        parts.append(f"{{troop:{tile.acquire_troops}}}")
    if tile.acquire_intrigue:
        parts.append(f"{{intrigue:{tile.acquire_intrigue}}}")
    if tile.acquire_cards:
        parts.append(f"{{draw:{tile.acquire_cards}}}")
    if tile.acquire_victory_points:
        parts.append(f"{{victory_point:{tile.acquire_victory_points}}}")
    if tile.acquire_contracts:
        parts.append("계약 가져옴")
    if tile.acquire_influence_choice:
        parts.append("{influence_any:1} 선택")
    if tile.acquire_intrigue_or_card:
        parts.append("{intrigue:1} / {draw:1}")
    if tile.acquire_may_trash_card:
        parts.append("카드 1장 {trash} 가능")
    if tile.acquire_deep_cover_spies:
        n = tile.acquire_deep_cover_spies
        spies = "{spy} 배치" if n == 1 else f"{{spy}} {n} 배치"
        parts.append(f"{spies} (잠복 스파이)")
    return ". ".join(parts)


def tech_ability_text_ko(tile: TechTile) -> str:
    """Korean twin of ``tech_ability_text``."""

    return TECH_ABILITY_TEXT_KO[tile.ability]
