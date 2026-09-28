"""Arrakeen Scouts in words: item names and the lines a seat chooses between.

The effects are paraphrased from the typed catalog (``content.arrakeen_scouts``)
with the shared effect wording (``effect_dsl_text``, ``effect_dsl_text_ko``);
the Korean item names are the app's official ones, recorded as terms in
``docs/rules/glossary-ko.md`` (names only, never the app's sentences, D7).
"""

from collections.abc import Mapping
from typing import Final

from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    SALES_BY_ID,
    SUBCOMMITTEES_BY_ID,
    ScoutsOption,
)
from dune_imperium.content.arrakeen_scouts.types import (
    AcquireReserveCardToHand,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    LoseHighestInfluence,
    PaySpecimens,
    RecallOtherAgent,
    RecruitToConflict,
)
from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.content.uprising.effect_dsl import TrashPersonalCard
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.display.effect_dsl_text import cost_text, reward_text
from dune_imperium.display.effect_dsl_text_ko import cost_text_ko, reward_text_ko
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.rules.scouts_effects import scouts_option

SCOUTS_ITEM_NAMES_KO: Final[Mapping[str, str]] = {
    "analytics": "분석",
    "appropriations": "재무",
    "back_room_deal": "밀실 거래",
    "bene_gesserit_treachery": "베네 게세리트의 음모",
    "betrayal": "배반",
    "choam_bargain": "초암 협정",
    "choam_coordination": "초암 조직화",
    "choam_escort": "초암 호송대",
    "choam_management": "초암 운영",
    "choam_negotiations_late": "초암 협상",
    "choam_negotiations_mid": "초암 협상",
    "choam_research": "초암 연구",
    "clear_the_market": "시장 정리",
    "clear_the_market_choam": "시장 정리",
    "competitive_study_late": "경쟁적인 연구",
    "competitive_study_mid": "경쟁적인 연구",
    "contingencies": "유사시 대비",
    "coordinate_with_the_emperor": "황제와의 협력",
    "covert_assistance": "비밀스러운 지원",
    "covert_operation": "작전 변경",
    "covert_operation_choam": "작전 변경",
    "crackdown": "강력 단속",
    "critical_moment_late": "중대한 순간",
    "critical_moment_mid": "중대한 순간",
    "desert_riding": "사막 질주",
    "emperors_schemes": "정예 사다우카 - 황제의 계략",
    "eyes_on_arrakis": "아라키스를 지켜보는 눈",
    "fedaykin_assistance": "페다이킨의 지원",
    "forecasting": "예측",
    "friends_everywhere": "어디든 있는 벗",
    "funeral_rites": "장례 의식",
    "gift_of_water": "물이 가져다 준 선물",
    "growth_project": "성장 프로젝트",
    "guild_negotiation": "길드 협상",
    "highest_bidder_late": "최고 입찰자에게",
    "highest_bidder_mid": "최고 입찰자에게",
    "imperial_reserve": "제국 비축 물자",
    "imperium_connections": "임페리움 접점",
    "ingratiate": "비위 맞추기",
    "intelligence": "정보",
    "investigations": "수사",
    "leverage": "권위",
    "market_opening": "시장 개장",
    "market_research": "시장 조사",
    "mating_season": "교미기",
    "mercenaries": "용병단",
    "moment_of_revelation": "폭로의 순간",
    "new_innovations": "새로운 혁신",
    "offworld_operation": "외우주 작전",
    "oversight": "관리감독",
    "planetary_exploration": "유익한 정보원 - 행성 탐사",
    "political_equilibrium": "정치적 균형",
    "prison_planet": "정예 사다우카 - 감옥 행성",
    "private_stock": "개인 비축품",
    "readiness": "긴급대응",
    "rebuild_infrastructure": "인프라 재구축",
    "relations": "외교",
    "rotating_doors": "회전문",
    "royal_delegation": "왕실 대표단",
    "secrets_for_sale": "기밀 정보 판매",
    "security_detail": "경호 요원",
    "send_for_aid": "지원 제공",
    "shadow_warfare": "그림자 속 전투",
    "share_intelligence": "정보 공유",
    "smoke_and_mirrors": "진실의 왜곡",
    "spies_for_hire_late": "스파이 고용",
    "spies_for_hire_mid": "스파이 고용",
    "sponsored_research": "연구 후원",
    "termination_request": "폐기 요청",
    "tleilaxu_offering": "틀레이락스의 공물",
    "tleilaxu_relations": "협력: 틀레이락스",
    "unlikely_allies": "뜻밖의 동맹",
    "unravel_the_future": "미래의 실타래를 풀다",
    "urban_surveillance": "유익한 정보원 - 도시 감시",
    "water_discipline": "물 규칙",
    "water_for_spice_smugglers": "밀수업자들에게 물 제공",
    "weirding_warfare": "기이한 전투",
}


def scouts_item_name(item_id: str) -> str:
    for table in (
        SUBCOMMITTEES_BY_ID,
        MISSIONS_BY_ID,
        EVENTS_BY_ID,
        AUCTIONS_BY_ID,
        SALES_BY_ID,
    ):
        entry = table.get(item_id)
        if entry is not None:
            return str(entry.name)
    raise KeyError(item_id)


def _step_text(step: object, *, cost: bool) -> str:
    match step:
        case LoseFactionInfluence(faction=faction, count=count):
            return f"Lose {count} {faction.value.replace('_', ' ').title()} Influence"
        case LoseHighestInfluence():
            return "Lose 1 Influence with your highest Faction"
        case LoseGarrisonTroops(count=count):
            return f"Lose {count} troop{'s' if count > 1 else ''} from your garrison"
        case PaySpecimens(count=count):
            return f"Pay {count} specimen{'s' if count > 1 else ''}"
        case RecallOtherAgent():
            return "Recall another of your Agents"
        case RecruitToConflict(count=count):
            return f"Put {count} troop{'s' if count > 1 else ''} into the Conflict"
        case AcquireReserveCardToHand(card_id=card_id):
            return f"Acquire {RESERVE_STACKS_BY_ID[card_id].card.name} to your hand"
        case GainLowestInfluence():
            return "+1 Influence with your lowest Faction"
        case GainSpiceWithHelixBonus(spice=spice, helix_spice=helix):
            return f"Gain {spice} spice ({helix} once you reach the Helix)"
        case TrashPersonalCard() if cost:
            return reward_text(step)
    return cost_text(step) if cost else reward_text(step)  # type: ignore[arg-type]


def _step_text_ko(step: object, *, cost: bool) -> str:
    match step:
        case LoseFactionInfluence(faction=faction, count=count):
            return f"{{influence_{faction.value}}} 영향력 {count} 잃기"
        case LoseHighestInfluence():
            return "영향력이 가장 높은 진영에서 영향력 1 잃기"
        case LoseGarrisonTroops(count=count):
            return f"주둔지의 {{troop:{count}}} 잃기"
        case PaySpecimens(count=count):
            return f"{{specimen:{count}}} 지불"
        case RecallOtherAgent():
            return "다른 {agent} 1 회수"
        case RecruitToConflict(count=count):
            return f"{{troop:{count}}} 분쟁에 투입"
        case AcquireReserveCardToHand(card_id=card_id):
            name = KOREAN_CARD_NAMES["cards"].get(card_id, card_id)
            return f"{name} 손으로 획득"
        case GainLowestInfluence():
            return "영향력이 가장 낮은 진영 영향력 +1"
        case GainSpiceWithHelixBonus(spice=spice, helix_spice=helix):
            return f"{{spice:{spice}}} (나선에 닿았으면 {{spice:{helix}}})"
        case TrashPersonalCard() if cost:
            return reward_text_ko(step)
    return cost_text_ko(step) if cost else reward_text_ko(step)  # type: ignore[arg-type]


def scouts_option_text(option: ScoutsOption) -> str:
    """One line: its costs, an arrow, its rewards."""

    costs = ", ".join(_step_text(cost, cost=True) for cost in option.costs)
    rewards = ", ".join(_step_text(reward, cost=False) for reward in option.rewards)
    return f"{costs} → {rewards}" if costs else rewards


def scouts_option_text_ko(option: ScoutsOption) -> str:
    costs = ", ".join(_step_text_ko(cost, cost=True) for cost in option.costs)
    rewards = ", ".join(_step_text_ko(reward, cost=False) for reward in option.rewards)
    return f"{costs} → {rewards}" if costs else rewards


# Items without lines to choose between, in the project's own words (the
# Korean from docs/rules/arrakeen-scouts.md 5 and 6); icons as tokens.
_NOTES: Final[Mapping[str, tuple[str, str]]] = {
    "security_detail": (
        "Each may park 1 supply troop at Deliver Supplies; their first Agent "
        "there sends it into the Conflict.",
        "각자 supply의 {troop:1}을 Deliver Supplies에 세울 수 있다. 그 칸에 처음 "
        "{agent}를 보내면 그 병력이 {conflict}으로 간다.",
    ),
    "imperial_reserve": (
        "1 spice and 2 Solari at Imperial Privilege; each visitor takes one.",
        "Imperial Privilege에 {spice:1}와 {solari:2}. 방문자가 하나씩 가진다.",
    ),
    "desert_riding": (
        "A Maker Hooks token by Hagga Basin, taken there instead of its 2 spice.",
        "Hagga Basin 옆 {maker_hooks}. 방문자는 칸의 {spice:2} 대신 가질 수 있다.",
    ),
    "urban_surveillance": (
        "1 Solari on each empty post by a City space, for the Spy placed there.",
        "City 칸 옆 빈 관측소마다 {solari:1}. 거기 {spy}를 놓는 좌석이 가진다.",
    ),
    "planetary_exploration": (
        "1 spice on each empty post by a Maker space, for the Spy placed there.",
        "Maker 칸 옆 빈 관측소마다 {spice:1}. 거기 {spy}를 놓는 좌석이 가진다.",
    ),
    "choam_research": (
        "2 face-down Contracts at Research Station, one per visit.",
        "Research Station에 뒷면 {contract} 2장. 방문할 때마다 1장.",
    ),
    "choam_escort": (
        "Each may recruit 1 troop, or load 1 Solari and 1 spice onto a face-up "
        "Contract, paid when it is completed.",
        "각자 {troop:1} 소집, 또는 앞면 {contract} 하나에 {solari:1}와 {spice:1}를 "
        "올려 두고 완료할 때 받는다.",
    ),
    "sponsored_research": (
        "2 spice by the Helix, for the next seat to reach it.",
        "research track의 나선 옆 {spice:2}. 다음에 닿는 좌석이 가진다.",
    ),
    "back_room_deal": (
        "2 Solari on Reclaimed Forces, for the next seat to acquire it.",
        "Reclaimed Forces 위 {solari:2}. 다음에 획득하는 좌석이 가진다.",
    ),
    "prison_planet": (
        "Each may lose a garrison troop to put a Control marker on Sardaukar "
        "with 2 spice from the bank; their visit takes the marker back and "
        "gains the spice.",
        "각자 주둔지 {troop:1}을 잃고 Sardaukar에 {control} 마커를 둘 수 있다. "
        "은행의 {spice:2}를 그 위에 둔다. 방문하면 마커를 되찾고 spice를 얻는다.",
    ),
    "emperors_schemes": (
        "2 face-down Intrigue cards at Sardaukar, one per visit.",
        "Sardaukar에 뒷면 {intrigue} 2장. 방문할 때마다 1장.",
    ),
    "fedaykin_assistance": (
        "Each may pay 1 spice to park 2 supply troops at Desert Tactics, "
        "recruited by the next visit.",
        "각자 {spice:1}를 내고 supply의 {troop:2}를 Desert Tactics에 세울 수 "
        "있다. 다음 방문 때 소집한다.",
    ),
    "weirding_warfare": (
        "Each may pay 2 Solari to park 2 supply troops at Espionage, sent into "
        "the Conflict by the next visit.",
        "각자 {solari:2}를 내고 supply의 {troop:2}를 Espionage에 세울 수 있다. "
        "다음 방문 때 {conflict}으로 간다.",
    ),
    "send_for_aid": (
        "Each may move a garrison troop to Gather Support, with 1 water from "
        "the bank under it; their next visit sends the troop into the Conflict "
        "and gains the water.",
        "각자 주둔지 {troop:1}을 Gather Support로 옮길 수 있다. 은행의 {water:1}을 "
        "그 밑에 둔다. 다음 방문 때 병력은 {conflict}으로 가고 물은 그 좌석이 "
        "얻는다.",
    ),
    "coordinate_with_the_emperor": (
        "Each may move a specimen to Sardaukar, with 2 Solari from the bank "
        "under it; their first visit gains both, the specimen recruited as a "
        "garrison troop.",
        "각자 {specimen:1}을 Sardaukar로 옮길 수 있다. 은행의 {solari:2}를 그 "
        "밑에 둔다. 처음 방문 때 둘 다 얻고, 표본은 주둔지로 소집된다.",
    ),
    "tleilaxu_offering": (
        "Each may put 2 supply troops on the Tleilaxu track's third space; "
        "reaching it turns them into specimens.",
        "각자 supply의 {troop:2}를 틀레이락스 트랙 세 번째 칸에 둘 수 있다. "
        "그 칸에 닿으면 {specimen:2}이 된다.",
    ),
    "political_equilibrium": (
        "Everyone loses 1 Influence with their highest Faction.",
        "모두 영향력이 가장 높은 진영에서 영향력 1을 잃는다.",
    ),
    "mating_season": (
        "1 more spice on each Maker space.",
        "Maker 칸마다 {spice:1} 추가.",
    ),
    "unlikely_allies": (
        "This round, spaces ignore their Influence requirements.",
        "이번 라운드, 칸의 영향력 요구를 무시한다.",
    ),
    "clear_the_market": (
        "The Imperium Row is cleared and refilled.",
        "임페리움 줄을 치우고 새로 채운다.",
    ),
    "clear_the_market_choam": (
        "The Imperium Row and the face-up Contracts are cleared and refilled.",
        "임페리움 줄과 앞면 {contract}를 치우고 새로 채운다.",
    ),
    "market_opening": (
        "This round, the first The Spice Must Flow costs 2 less.",
        "이번 라운드 처음 획득하는 The Spice Must Flow의 비용이 2 적다.",
    ),
    "eyes_on_arrakis": (
        "This round, every Faction space is a Combat space.",
        "이번 라운드 모든 진영 칸이 {combat} 칸이다.",
    ),
    "rebuild_infrastructure": (
        "If the Shield Wall is gone, two seats may pay 1 spice each to put it back.",
        "{shield_wall}이 없으면 두 좌석이 각자 {spice:1}를 내서 되돌릴 수 있다.",
    ),
    "friends_everywhere": (
        "This round, an Influence 4 bonus may be any Faction's.",
        "이번 라운드, 영향력 4 보너스를 아무 진영 것으로 받을 수 있다.",
    ),
}


def scouts_item_lines(item_id: str) -> tuple[list[str], list[str]]:
    """What an item offers, in English and Korean, one entry per line."""

    note = _NOTES.get(item_id)
    if note is not None:
        return [note[0]], [note[1]]
    options: list[ScoutsOption] = []
    prefixes: list[tuple[str, str]] = []
    if item_id in SUBCOMMITTEES_BY_ID:
        options = [SUBCOMMITTEES_BY_ID[item_id].option]
    elif item_id in EVENTS_BY_ID:
        event = EVENTS_BY_ID[item_id]
        if event.secret_choices:
            for choice in event.secret_choices:
                options.append(choice.option)
                prefixes.append(
                    ("next round: ", "다음 라운드: ")
                    if choice.delay == 1
                    else ("in two rounds: ", "두 라운드 뒤: ")
                )
        else:
            options = list(event.options)
    elif item_id in SALES_BY_ID:
        options = list(SALES_BY_ID[item_id].options)
    elif item_id in AUCTIONS_BY_ID:
        auction = AUCTIONS_BY_ID[item_id]
        if not auction.rank_rewards:
            return [auction_rule_text(item_id)], [auction_rule_text_ko(item_id)]
        options = [ScoutsOption(rewards=rewards) for rewards in auction.rank_rewards]
        prefixes = [("1st: ", "1위: "), ("2nd: ", "2위: ")][: len(options)]
    english = [scouts_option_text(option) for option in options]
    korean = [scouts_option_text_ko(option) for option in options]
    if prefixes:
        english = [p[0] + line for p, line in zip(prefixes, english, strict=True)]
        korean = [p[1] + line for p, line in zip(prefixes, korean, strict=True)]
    return english, korean


def auction_rule_text(item_id: str) -> str:
    auction = AUCTIONS_BY_ID[item_id]
    if auction.revealed_cards:
        return (
            f"{auction.revealed_cards} Imperium deck cards revealed; open calls "
            "in spice, the highest buys one"
            + (", the second may buy another." if auction.places > 1 else ".")
        )
    return (
        "Sealed bids of 0-3 spice: each seat pays and sends one troop per spice "
        "to the Conflict; the lowest bidders may pull theirs back."
    )


def auction_rule_text_ko(item_id: str) -> str:
    auction = AUCTIONS_BY_ID[item_id]
    if auction.revealed_cards:
        return (
            f"임페리움 덱 위 {auction.revealed_cards}장 공개. {{spice}}로 공개 호가, "
            "1위가 한 장을 산다"
            + (", 2위도 한 장을 살 수 있다." if auction.places > 1 else ".")
        )
    return (
        "{spice} 0~3 봉인 입찰. 모두 내고 그만큼 {troop}을 {conflict}에 넣는다. "
        "최저 입찰자는 후퇴할 수 있다."
    )


def scouts_action_text(
    state: GameState, action: DomainAction
) -> tuple[str, str] | None:
    """Describe a Scouts choice in English and Korean; None for others.

    Only the seat choosing sees these, so a secret line may be named.
    """

    arguments = dict(action.arguments)
    top = state.decision_stack[-1] if state.decision_stack else None
    context = dict(top.context) if top is not None else {}
    match action.action_id:
        case "scouts_choose_option":
            item, index = context.get("item"), arguments.get("option")
            if not isinstance(item, str) or type(index) is not int:
                return None
            option = scouts_option(item, index)
            return scouts_option_text(option), scouts_option_text_ko(option)
        case "scouts_secret_pick":
            event_id, pick = context.get("event_id"), arguments.get("pick")
            if not isinstance(event_id, str) or type(pick) is not int:
                return None
            english, korean = scouts_item_lines(event_id)
            return english[pick], korean[pick]
        case "join_subcommittee":
            subcommittee_id = arguments.get("subcommittee_id")
            if not isinstance(subcommittee_id, str):
                return None
            option = SUBCOMMITTEES_BY_ID[subcommittee_id].option
            name = SCOUTS_ITEM_NAMES_KO[subcommittee_id]
            return (
                f"{scouts_item_name(subcommittee_id)}: {scouts_option_text(option)}",
                f"{name}: {scouts_option_text_ko(option)}",
            )
        case "scouts_join_mission":
            target = arguments.get("target")
            if target == "recruit":
                return "Recruit 1 troop", "{troop:1} 소집"
            if isinstance(target, str) and target:
                contract = contract_for_instance(target)
                names = KOREAN_CARD_NAMES["contracts"]
                contract_ko = names.get(contract.card.card_id) or names.get(
                    contract.copy_of or "", contract.card.name
                )
                return (
                    f"Load 1 Solari and 1 spice onto {contract.card.name}",
                    f"{contract_ko}에 {{solari:1}}와 {{spice:1}} 올려 두기",
                )
            return None
        case "scouts_recall_agent" if arguments.get("space_id") == "conflict":
            return "Recall the Agent in the Conflict", "{conflict}의 {agent} 소환"
        case "scouts_collect_mission":
            choice = arguments.get("choice")
            if choice == "solari":
                return "Take the Solari", "{solari} 받기"
            if choice == "spice":
                return "Take the spice", "{spice} 받기"
            return None
        case "scouts_take_card":
            slot = arguments.get("slot")
            if type(slot) is not int or slot >= len(state.scouts_market_cards):
                return None
            card = imperium_card_for_instance(state.scouts_market_cards[slot]).card
            return card.name, KOREAN_CARD_NAMES["cards"].get(card.card_id, card.name)
    return None
