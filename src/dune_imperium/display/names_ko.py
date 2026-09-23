"""Korean printed names of the cards the Korean edition was read for.

The Korean UI names a card by its Korean print where one is known here and
keeps the English name otherwise (``server.catalog`` hands both out, the
page picks by its language). Source: the Korea Boardgames edition of
Uprising, card faces read from photographs of the retail cards (the private
assets repository's ``reference/naver-vampmiyu-223464306472``,
``matching.csv``); every title was read twice, independently, and both
readings agreed character for character (2026-09-22).

Keyed like the display catalog's sections (``cards`` holds Imperium,
starting, Reserve and promo cards). The engine's English name sometimes
carries a distinguisher the card does not print: a contract's numeral
("Arrakeen I") or spice threshold ("Harvest 3+"), and a Skirmish's battle
icon. The Korean name carries the same distinguisher, the battle icons in
the glossary's words (크리스나이프 / 사막쥐 / 오니솝터 `[Main p. 20]`,
``docs/rules/glossary-ko.md``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

_CARDS: Final[dict[str, str]] = {
    "arrakis_revolt": "아라키스 반란",
    "bene_gesserit_operative": "베네 게세리트 첩보원",
    "branching_path": "갈림길",
    "calculus_of_power": "힘의 계산법",
    "captured_mentat": "붙잡힌 멘타트",
    "cargo_runner": "화물 운반사",
    "chani_clever_tactician": "영리한 전술가, 챠니",
    "convincing_argument": "합리적 주장",
    "corrinth_city": "코린트 시티",
    "covert_operation": "비밀 작전",
    "dagger": "단검",
    "dangerous_rhetoric": "위험한 미사여구",
    "delivery_agreement": "배송 협정",
    "desert_power": "사막의 힘",
    "desert_survival": "사막 생존자",
    "diplomacy": "외교",
    "double_agent": "이중 스파이",
    "dune_the_desert_planet": "사막 행성 듄",
    "ecological_testing_station": "생태 시험소",
    "fedaykin_stilltent": "페다이킨 사막 텐트",
    "guild_envoy": "길드 특사",
    "guild_spy": "길드 스파이",
    "hidden_missive": "비밀 서신",
    "imperial_spymaster": "제국 스파이 대장",
    "in_high_places": "높은 자리에서",
    "interstellar_trade": "성간 교역",
    "junction_headquarters": "중계 본부",
    "leadership": "리더십",
    "long_live_the_fighters": "전사들이여 영원하라",
    "maker_keeper": "메이커 사육사",
    "maula_pistol": "마울라 권총",
    "northern_watermaster": "북부 물감독관",
    "overthrow": "타도",
    "paracompass": "파라컴퍼스",
    "prepare_the_way": "길을 준비하라",
    "price_is_no_object": "값은 문제가 아니다",
    "priority_contracts": "우선 계약",
    "public_spectacle": "대중의 구경거리",
    "rebel_supplier": "반란군 공급자",
    "reconnaissance": "첩보 수집",
    "reliable_informant": "믿을 만한 정보원",
    "sardaukar_coordination": "사다우카 편성",
    "sardaukar_soldier": "사다우카 병사",
    "seek_allies": "동맹 물색",
    "shishakli": "시샤클리",
    "signet_ring": "인장 반지",
    "smuggler_s_harvester": "밀수꾼의 채취기",
    "smuggler_s_haven": "밀수꾼의 피난처",
    "southern_elders": "남부 원로",
    "space_time_folding": "시공간 접기",
    "spacing_guild_s_favor": "우주 항행 길드의 호의",
    "spy_network": "스파이 네트워크",
    "steersman": "조타수",
    "stilgar_the_devoted": "충실한 자, 스틸가",
    "strike_fleet": "공습 함대",
    "subversive_advisor": "불온한 조언자",
    "the_spice_must_flow": "스파이스는 흘러야 한다",
    "treacherous_maneuver": "기만적인 계책",
    "tread_in_darkness": "어둠 속 발소리",
    "truthtrance": "진실의 무아지경",
    "undercover_asset": "첩보 요원",
    "unswerving_loyalty": "변함없는 충성심",
    "weirding_woman": "기묘한 여성",
    "wheels_within_wheels": "얽히고설킨 상황",
}


_INTRIGUE: Final[dict[str, str]] = {
    "backed_by_choam": "초암 공사의 후원",
    "choam_profits": "초암 공사 수익",
    "crysknife": "크리스나이프",
    "depart_for_arrakis": "아라키스를 향해",
    "leverage": "레버리지",
    "reach_agreement": "합의 달성",
}


_CONTRACTS: Final[dict[str, str]] = {
    "acquire": "획득",
    "arrakeen_i": "아라킨 I",
    "arrakeen_ii": "아라킨 II",
    "deliver_supplies": "보급품 배송",
    "espionage_i": "첩보 활동 I",
    "espionage_ii": "첩보 활동 II",
    "harvest_3": "채취 3+",
    "harvest_3_contract": "채취 3+",
    "harvest_4": "채취 4+",
    "harvest_4_contract": "채취 4+",
    "heighliner_i": "하이라이너 I",
    "heighliner_ii": "하이라이너 II",
    "heighliner_iii": "하이라이너 III",
    "high_council_i": "원로회 I",
    "high_council_ii": "원로회 II",
    "immediate": "즉시",
    "research_station_i": "연구 기지 I",
    "research_station_ii": "연구 기지 II",
    "sardaukar_i": "사다우카 I",
    "sardaukar_ii": "사다우카 II",
}


_CONFLICTS: Final[dict[str, str]] = {
    "battle_for_arrakeen": "아라킨 대전투",
    "battle_for_imperial_basin": "제국 분지 점령전",
    "battle_for_spice_refinery": "스파이스 정제소 대전투",
    "choam_security": "초암 공사 방위",
    "propaganda": "프로파간다",
    "protect_the_sietches": "시치 방어전",
    "secure_imperial_basin": "제국 분지 확보",
    "seize_spice_refinery": "스파이스 정제소 장악",
    "shadow_contest": "그림자 속 암투",
    "siege_of_arrakeen": "아라킨 공성전",
    "skirmish_crysknife": "소규모 전투 (크리스나이프)",
    "skirmish_desert_mouse": "소규모 전투 (사막쥐)",
    "skirmish_ornithopter": "소규모 전투 (오니솝터)",
    "spice_freighters": "스파이스 화물선",
    "test_of_loyalty": "충성심 시험",
    "trade_dispute": "무역 분쟁",
}


_LEADERS: Final[dict[str, str]] = {
    "feyd_rautha_harkonnen": "페이드 로타 하코넨",
    "gurney_halleck": "거니 할렉",
    "lady_amber_metulli": "레이디 앰버 메툴리",
    "lady_jessica": "레이디 제시카",
    "lady_margot_fenring": "레이디 마고트 펜링",
    "muad_dib": "무앗딥",
    "princess_irulan": "이룰란 공주",
    "shaddam_corrino_iv": "샤담 코리노 4세",
    "staban_tuek": "스타반 튜엑",
}


KOREAN_CARD_NAMES: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "cards": MappingProxyType(_CARDS),
        "intrigue": MappingProxyType(_INTRIGUE),
        "contracts": MappingProxyType(_CONTRACTS),
        "conflicts": MappingProxyType(_CONFLICTS),
        "leaders": MappingProxyType(_LEADERS),
    }
)
"""``{catalog section: {id: Korean name}}``; an absent id keeps its English."""
