"""English display text for the 22 Uprising board spaces.

Spaces whose printed effect is fully covered by the engine's static
automatic-effect table render their text from that same table, so the shown
effect cannot drift from what the engine executes. Spaces resolved through
dedicated choice frames or imperative code carry hand-authored lines whose
wording follows ``docs/rules/board-spaces.md`` (Board Space Guide citations).
Implementation flags are always computed from the engine table, never
authored, so an unimplemented space is marked automatically.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_never

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.rules.board_effects import (
    BOARD_ICON_CONTRACT,
    BOARD_ICON_HIGH_COUNCIL,
    BOARD_ICON_INFLUENCE,
    BOARD_ICON_SPY,
    BOARD_ICON_SWORDMASTER,
    BOARD_ICON_TRASH,
    CHOICE_DRIVEN_SPACE_IDS,
    board_icon_for_effect,
    static_board_effects,
    visit_board_effects,
)
from dune_imperium.rules.effects import (
    AutomaticEffect,
    DrawImperiumCardsEffect,
    DrawIntrigueCardsEffect,
    GainResourcesEffect,
    RecruitTroopsEffect,
    ResearchEffect,
    current_agent_effect_context,
)

FACTION_NAMES: Mapping[Faction, str] = MappingProxyType(
    {
        Faction.EMPEROR: "Emperor",
        Faction.SPACING_GUILD: "Spacing Guild",
        Faction.BENE_GESSERIT: "Bene Gesserit",
        Faction.FREMEN: "Fremen",
    }
)

# Board-space text below has a Korean twin (feature decided 2026-09-25, Step
# K4: the effect text the engine *generates* gets a Korean version; a board
# space's own printed NAME stays English, per docs/rules/glossary-ko.md's
# "공간 이름" row). Every Korean function/table here mirrors the English one
# directly above it one-for-one; a test asserts the ``_KO`` tables share the
# same keys as their English counterparts. Word choice follows only
# ``docs/rules/glossary-ko.md`` (game terms) or ordinary Korean grammar for
# everything else, and every icon a Korean line names follows the same
# "counted vs. bare, per what ``ICON_RULES`` actually matches for the
# matching English wording" policy ``display/tokens_ko.py``'s module
# docstring sets out in detail — not copied here a second time, see that
# module for the reasoning; the choices below were checked against it and
# against ``docs/rules/board-spaces.md``'s own English wording line by line.

# Hand-authored effect lines, keyed by (space_id, choam_module) with None
# meaning both rulesets, holding one string per cost option. Wording follows
# docs/rules/board-spaces.md; the faction-visit Influence line is included
# where the space has a faction Agent icon.
_AUTHORED_OPTION_EFFECTS: Mapping[
    tuple[str, bool | None],
    tuple[str, ...],
] = MappingProxyType(
    {
        ("dutiful_service", True): (
            "Gain 1 Emperor Influence. Take a face-up Contract"
            " (Gain 2 solari if none is available)",
        ),
        ("accept_contract", True): (
            "Draw 1 card. Take a face-up Contract"
            " (Gain 2 solari if none is available)",
        ),
        ("espionage", None): (
            "Gain 1 Bene Gesserit Influence, Draw 1 card."
            " Place a Spy",
        ),
        ("secrets", None): (
            "Gain 1 Bene Gesserit Influence, Draw 1 Intrigue card."
            " Each opponent holding 4 or more Intrigue cards gives you one"
            " at random",
        ),
        ("desert_tactics", None): (
            "Gain 1 Fremen Influence, Recruit 1 troop."
            " You may trash a card",
        ),
        ("high_council", None): (
            "First visit: seat your Councilor for +2 Persuasion at every"
            " Reveal turn. Later visits: Gain 2 spice, Draw 1 Intrigue card,"
            " Recruit 3 troops",
        ),
        ("imperial_privilege", None): (
            "You may trash an Intrigue card → Draw 1 Intrigue card."
            " Recall one of your other Agents and Draw 1 card",
        ),
        ("swordmaster", None): (
            "Once per game: take your third Agent, usable from this round",
        )
        * 2,
        ("sietch_tabr", None): (
            "Choose one: take the Maker Hooks token (if you lack it),"
            " Recruit 1 troop and Gain 1 water — or Gain 1 water,"
            " optionally destroying the Shield Wall",
        ),
        ("tuek_sietch", None): (
            "Take all bonus spice here, then choose: Gain 1 spice — or"
            " Draw 1 card (Esmar Tuek's Maker space)",
        ),
        ("deep_desert", None): (
            "Take all bonus spice here, then choose: Gain 4 spice — or,"
            " with Maker Hooks, summon 2 sandworms into the Conflict",
        ),
        ("hagga_basin", None): (
            "Take all bonus spice here, then choose: Gain 2 spice — or,"
            " with Maker Hooks, summon 1 sandworm into the Conflict",
        ),
        ("imperial_basin", None): ("Gain 1 spice plus all bonus spice here",),
        ("shipping", None): (
            "Gain 5 solari, Gain 1 Influence with a Faction of your choice",
        ),
    }
)

# A phrase repeated verbatim by three of the entries above (dutiful_service's
# and accept_contract's CHOAM variant, and BOARD_ICON_CONTRACT below): Take a
# Contract 가져오다 [Main p. 16]/[Main p. 20] (glossary-ko.md), the bare
# {contract} icon (ICON_RULES' "Contracts?" rule is capital-only, and this
# printed line is capitalized), "없으면" (if there is none) for "if none is
# available" — ordinary grammar, not a game term.
_TAKE_CONTRACT_OR_SOLARI_KO = "{contract} 가져옴 (없으면 {solari:2})"

# Esmar Tuek's Korean print name (the leader, referenced by tuek_sietch's
# flavor line below), read from names_ko.py's own confirmed transcription
# ("에스마르 튜엑" — Korea Boardgames retail cards, read twice
# independently, per that module's docstring), not left as the untranslated
# English flavor name. The Korean Bloodlines rulebook already names this
# very leader/space pairing "튜엑의 시치 게임판 장소 (에스마르 튜엑
# 전용)" `[Bloodlines p. 2]`, confirming this is the same person, not a
# second unconfirmed name.
_ESMAR_TUEK_NAME_KO = KOREAN_CARD_NAMES["leaders"]["esmar_tuek"]

_AUTHORED_OPTION_EFFECTS_KO: Mapping[
    tuple[str, bool | None],
    tuple[str, ...],
] = MappingProxyType(
    {
        ("dutiful_service", True): (
            f"{{influence_emperor:1}}. {_TAKE_CONTRACT_OR_SOLARI_KO}",
        ),
        ("accept_contract", True): (
            f"{{draw:1}}. {_TAKE_CONTRACT_OR_SOLARI_KO}",
        ),
        ("espionage", None): (
            "{influence_bene_gesserit:1}, {draw:1}. {spy} 배치",
        ),
        ("secrets", None): (
            # "Each opponent holding 4 or more Intrigue cards gives you one
            # at random" quotes glossary-ko.md's own "opponent" citation
            # almost verbatim ("책략 카드를 4장 이상 가진 다른 플레이어들은
            # 각자 당신에게…", the Steal Intrigue rule, [Main p. 20]) — this
            # space's own effect is the same shape. "Intrigue cards" here
            # has no adjacent "Draw N" so it is the bare icon (tokens_ko.py
            # docstring), not the counted one used for "Draw 1 Intrigue
            # card" just before it.
            "{influence_bene_gesserit:1}, {intrigue:1}. {intrigue}를 4장 "
            "이상 가진 다른 플레이어들은 각자 당신에게 무작위로 한 장을 줌",
        ),
        ("desert_tactics", None): (
            "{influence_fremen:1}, {troop:1}. 카드 1장 {trash} 가능",
        ),
        ("high_council", None): (
            # "의원 토큰을 놓습니다" quotes glossary-ko.md's High Council
            # citation ([Board Guide p. 2]) for "seat your Councilor";
            # "매 {reveal_turn}마다" is the rulebook's own recurring-trigger
            # shape (cardstyle.md's "때마다" note), not the one-shot -다면.
            # English opens the line with "First visit:" — the Korean
            # rulebook's own two-visit split ("이 장소에 처음으로 에이전트를
            # 보낼 때: … / 그 뒤로 이 장소에 다시 에이전트를 보낼 때: …")
            # confirms this line needs the same first/later split, so
            # "첫 방문:" mirrors "이후 방문:" already used just below.
            "첫 방문: 매 {reveal_turn}마다 +{persuasion:2}를 위해 원로회에"
            " 의원 토큰 놓음. 이후 방문: {spice:2}, {intrigue:1}, {troop:3}",
        ),
        ("imperial_privilege", None): (
            # "trash an Intrigue card" is the exact adjacency ICON_RULES'
            # combined trash_intrigue rule matches (structs.py docstring
            # precedent) — bare {trash_intrigue}, not two separate icons.
            "{trash_intrigue} 가능 {arrow_right} {intrigue:1}. 당신의 다른"
            " {agent} 하나 소환 및 {draw:1}",
        ),
        ("swordmaster", None): (
            "게임당 한 번: 세 번째 {agent} 가져옴 (이번 라운드부터 사용 가능)",
        )
        * 2,
        ("sietch_tabr", None): (
            "하나 선택: {maker_hooks} 가져옴 (없다면), {troop:1}, {water:1}"
            " / {water:1}, 선택적으로 {shield_wall} 제거",
        ),
        ("tuek_sietch", None): (
            # "Gain" here is glossary-ko.md's 얻다 [Main p. 20], not
            # Acquire's 획득; "Esmar Tuek" is the leader, whose Korean-print
            # name is _ESMAR_TUEK_NAME_KO above (names_ko.py), not left in
            # English.
            f"여기 있는 보너스 {{spice}} 모두 얻음, 그 후 하나 선택: {{spice:1}}"
            f" / {{draw:1}} ({_ESMAR_TUEK_NAME_KO}의 메이커 장소)",
        ),
        ("deep_desert", None): (
            # "모래벌레를 불러서 즉시 교전 칸에 배치합니다" [Main p. 10] is
            # glossary-ko.md's own Sandworm-summon citation; "부르다", never
            # "소환" (Agent/Spy recall only) — see assert_no_summon_for_
            # sandworm in tests/support/ko_text.py. "Gain" is 얻다
            # [Main p. 20], not Acquire's 획득.
            "여기 있는 보너스 {spice} 모두 얻음, 그 후 하나 선택: {spice:4}"
            " / {maker_hooks}면 {sandworm} 2마리를 불러서 교전 칸에 배치",
        ),
        ("hagga_basin", None): (
            "여기 있는 보너스 {spice} 모두 얻음, 그 후 하나 선택: {spice:2}"
            " / {maker_hooks}면 {sandworm} 1마리를 불러서 교전 칸에 배치",
        ),
        ("imperial_basin", None): ("{spice:1} 및 여기 있는 보너스 {spice} 모두 얻음",),
        ("shipping", None): ("{solari:5}, {influence_any:1} 선택",),
    }
)

# Printed facts outside the automatic-effects channel, each verified against
# its implementing rules module (reveal_turn.py persuasion passives,
# agent_turn.py control visit bonus).
SPACE_NOTES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "assembly_hall": (
            "While your Agent is here: +1 Persuasion at your Reveal turn",
        ),
        "arrakeen": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 solari",
        ),
        "spice_refinery": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 solari",
        ),
        "imperial_basin": (
            "Control: whenever an Agent is sent here, the controller"
            " gains 1 spice",
        ),
    }
)

# "지배" is the glossary's plain word for Control ([Main p. 20]); ICON_RULES
# has no rule for the English word "Control" at all (structs.py's own
# conflict_reward_text_ko docstring notes this), so no {control} placeholder
# is used even though one exists. "여기로 {agent}를 보낼 때마다" mirrors
# glossary-ko.md's Send-an-Agent citation ([Main p. 9], 보내다) in the
# recurring "때마다" shape (cardstyle.md). "지배권을 가진 플레이어"
# (rather than an invented "지배자") and the verb 얻다 (never Acquire's
# 획득) both quote the Korean Board Guide itself: "아라킨 지배권을 가진
# 플레이어는 1 솔라리를 얻습니다" [Board Guide p. 1], "제국 분지 지배권을
# 가진 플레이어는 1 스파이스를 얻습니다" [Board Guide p. 2] (Spice
# Refinery's printed line matches Arrakeen's verbatim per the same guide).
SPACE_NOTES_KO: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "assembly_hall": (
            "당신의 {agent}가 여기 있는 동안, 당신의 {reveal_turn}에"
            " +{persuasion:1}",
        ),
        "arrakeen": (
            "지배: 여기로 {agent}를 보낼 때마다 지배권을 가진 플레이어가"
            " {solari:1} 얻음",
        ),
        "spice_refinery": (
            "지배: 여기로 {agent}를 보낼 때마다 지배권을 가진 플레이어가"
            " {solari:1} 얻음",
        ),
        "imperial_basin": (
            "지배: 여기로 {agent}를 보낼 때마다 지배권을 가진 플레이어가"
            " {spice:1} 얻음",
        ),
    }
)


# English lines for the printed icons outside the automatic-effects table,
# worded after docs/rules/board-spaces.md (Board Space Guide citations).
_ICON_TEXTS: Mapping[str, str] = MappingProxyType(
    {
        BOARD_ICON_CONTRACT: (
            "Take a face-up Contract (Gain 2 solari if none is available)"
        ),
        BOARD_ICON_HIGH_COUNCIL: (
            "Seat your Councilor for +2 Persuasion at every Reveal turn"
        ),
        BOARD_ICON_SWORDMASTER: "Take your third Agent, usable from this round",
        BOARD_ICON_SPY: "Place a Spy",
        BOARD_ICON_TRASH: "You may trash a card",
        BOARD_ICON_INFLUENCE: "Gain 1 Influence with a Faction of your choice",
    }
)

# "의원 토큰" (Councilor token) and "원로회" (High Council) quote
# glossary-ko.md's High Council citation ([Board Guide p. 2]) the same way
# the "high_council" row of _AUTHORED_OPTION_EFFECTS_KO above does.
_ICON_TEXTS_KO: Mapping[str, str] = MappingProxyType(
    {
        BOARD_ICON_CONTRACT: _TAKE_CONTRACT_OR_SOLARI_KO,
        BOARD_ICON_HIGH_COUNCIL: (
            "매 {reveal_turn}마다 +{persuasion:2}를 위해 원로회에 의원 토큰 놓음"
        ),
        BOARD_ICON_SWORDMASTER: "세 번째 {agent} 가져옴 (이번 라운드부터 사용 가능)",
        BOARD_ICON_SPY: "{spy} 배치",
        BOARD_ICON_TRASH: "카드 1장 {trash} 가능",
        BOARD_ICON_INFLUENCE: "{influence_any:1} 선택",
    }
)


def board_icon_text(key: str, effects: tuple[AutomaticEffect, ...]) -> str:
    """Render one printed icon of a visit as an English effect fragment.

    Automatic icons read their amount from ``effects`` (the visit's entries
    of the engine table); the choice and one-off icons use the authored
    lines above.
    """

    for effect in effects:
        if board_icon_for_effect(effect) == key:
            return ", ".join(automatic_effect_texts(effect))
    return _ICON_TEXTS[key]


def board_icon_text_ko(key: str, effects: tuple[AutomaticEffect, ...]) -> str:
    """Korean twin of ``board_icon_text``."""

    for effect in effects:
        if board_icon_for_effect(effect) == key:
            return ", ".join(automatic_effect_texts_ko(effect))
    return _ICON_TEXTS_KO[key]


def board_effect_action_text(state: GameState, action: DomainAction) -> str | None:
    """Describe a ``resolve_board_effect`` action by the icon it resolves.

    Returns None for any other action or outside an Agent-turn effect frame.
    """

    if action.action_id != "resolve_board_effect":
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    space_id = context.get("space_id")
    cost_option = context.get("cost_option")
    key = dict(action.arguments).get("effect")
    if (
        not isinstance(space_id, str)
        or isinstance(cost_option, bool)
        or not isinstance(cost_option, int)
        or not isinstance(key, str)
    ):
        return None
    effects = visit_board_effects(
        state.players[action.actor],
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
        immortality=state.config.immortality,
    )
    return board_icon_text(key, effects)


def board_effect_action_text_ko(state: GameState, action: DomainAction) -> str | None:
    """Korean twin of ``board_effect_action_text``.

    ``display.actions.effect_action_text_ko`` wires this in for
    ``resolve_board_effect`` (Step K4) the same way it already wires
    ``agent_card_icon_text_ko`` in for ``resolve_agent_card_effect`` (Step
    K2) — the client's ``detail_ko`` falls back to the English ``detail``
    whenever a resolution has no Korean text yet, so this only needs to
    exist, not backfill every historical action kind.
    """

    if action.action_id != "resolve_board_effect":
        return None
    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    space_id = context.get("space_id")
    cost_option = context.get("cost_option")
    key = dict(action.arguments).get("effect")
    if (
        not isinstance(space_id, str)
        or isinstance(cost_option, bool)
        or not isinstance(cost_option, int)
        or not isinstance(key, str)
    ):
        return None
    effects = visit_board_effects(
        state.players[action.actor],
        space_id,
        cost_option,
        choam_module=state.config.choam_module,
        immortality=state.config.immortality,
    )
    return board_icon_text_ko(key, effects)


def space_option_count(space_id: str) -> int:
    """Return how many paid cost options the space offers (at least one)."""

    return max(1, len(BOARD_SPACES_BY_ID[space_id].cost_options))


def space_option_effects(
    space_id: str,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> tuple[str, ...]:
    """Return one English effect line per cost option of the space.

    ``immortality`` reads the engine's table for that ruleset, so the
    Research Station overlay's "Draw two cards and research" [Immortality
    pp. 5, 16] comes out of the same effects the engine executes.
    """

    authored = _AUTHORED_OPTION_EFFECTS.get(
        (space_id, choam_module)
    ) or _AUTHORED_OPTION_EFFECTS.get((space_id, None))
    if authored is not None:
        return authored
    return tuple(
        _automatic_option_text(
            space_id, option, choam_module=choam_module, immortality=immortality
        )
        for option in range(space_option_count(space_id))
    )


def space_option_effects_ko(
    space_id: str,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> tuple[str, ...]:
    """Korean twin of ``space_option_effects``."""

    authored = _AUTHORED_OPTION_EFFECTS_KO.get(
        (space_id, choam_module)
    ) or _AUTHORED_OPTION_EFFECTS_KO.get((space_id, None))
    if authored is not None:
        return authored
    return tuple(
        _automatic_option_text_ko(
            space_id, option, choam_module=choam_module, immortality=immortality
        )
        for option in range(space_option_count(space_id))
    )


def space_is_implemented(space_id: str, *, choam_module: bool) -> bool:
    """Mirror the engine's placement gate for every option of the space."""

    if space_id in CHOICE_DRIVEN_SPACE_IDS:
        return True
    for option in range(space_option_count(space_id)):
        try:
            static_board_effects(space_id, option, choam_module=choam_module)
        except NotImplementedError:
            return False
    return True


def space_notes(space_id: str) -> tuple[str, ...]:
    """Return printed always-on facts that are not part of the visit effect."""

    return SPACE_NOTES.get(space_id, ())


def space_notes_ko(space_id: str) -> tuple[str, ...]:
    """Korean twin of ``space_notes``."""

    return SPACE_NOTES_KO.get(space_id, ())


def _automatic_option_text(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> str:
    fragments: list[str] = []
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is not None:
        fragments.append(f"Gain 1 {FACTION_NAMES[faction]} Influence")
    for effect in static_board_effects(
        space_id,
        cost_option,
        choam_module=choam_module,
        immortality=immortality,
    ):
        fragments.extend(automatic_effect_texts(effect))
    return ", ".join(fragments)


def automatic_effect_texts(effect: AutomaticEffect) -> tuple[str, ...]:
    """Render one engine automatic effect as display fragments."""

    match effect:
        case GainResourcesEffect():
            return tuple(
                f"Gain {amount} {resource}"
                for resource, amount in (
                    ("solari", effect.solari),
                    ("spice", effect.spice),
                    ("water", effect.water),
                )
                if amount
            )
        case RecruitTroopsEffect():
            noun = "troop" if effect.count == 1 else "troops"
            return (f"Recruit {effect.count} {noun}",)
        case DrawImperiumCardsEffect():
            noun = "card" if effect.count == 1 else "cards"
            return (f"Draw {effect.count} {noun}",)
        case DrawIntrigueCardsEffect():
            noun = "Intrigue card" if effect.count == 1 else "Intrigue cards"
            return (f"Draw {effect.count} {noun}",)
        case ResearchEffect():
            return ("Research (advance your research token)",)
        case _:
            assert_never(effect)


def _automatic_option_text_ko(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool = False,
) -> str:
    """Korean twin of ``_automatic_option_text``."""

    fragments: list[str] = []
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is not None:
        fragments.append(f"{{influence_{faction.value}:1}}")
    for effect in static_board_effects(
        space_id,
        cost_option,
        choam_module=choam_module,
        immortality=immortality,
    ):
        fragments.extend(automatic_effect_texts_ko(effect))
    return ", ".join(fragments)


def automatic_effect_texts_ko(effect: AutomaticEffect) -> tuple[str, ...]:
    """Korean twin of ``automatic_effect_texts``.

    Every resource/count pair here has the digit directly adjacent to the
    keyword in the matching English fragment ("Gain N solari", "Recruit N
    troop(s)", "Draw N card(s)"/"Draw N Intrigue card(s)"), so each is a
    *counted* ``{term:count}`` (``display/tokens_ko.py``'s module docstring
    states this rule once for every generator that needs it). "(연구 토큰
    전진)" is a terse paraphrase of the Research citation
    (`[Immortality p. 16]`: "당신의 연구 토큰을 연구 트랙에서 오른쪽으로
    1칸 전진시킵니다"), matching English's own short parenthetical
    "(advance your research token)" rather than the full rulebook sentence.
    """

    match effect:
        case GainResourcesEffect():
            return tuple(
                f"{{{term}:{amount}}}"
                for term, amount in (
                    ("solari", effect.solari),
                    ("spice", effect.spice),
                    ("water", effect.water),
                )
                if amount
            )
        case RecruitTroopsEffect():
            return (f"{{troop:{effect.count}}}",)
        case DrawImperiumCardsEffect():
            return (f"{{draw:{effect.count}}}",)
        case DrawIntrigueCardsEffect():
            return (f"{{intrigue:{effect.count}}}",)
        case ResearchEffect():
            return ("{research} (연구 토큰 전진)",)
        case _:
            assert_never(effect)
