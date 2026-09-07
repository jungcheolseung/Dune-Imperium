# Bloodlines implementation audit

기준일: 2026-09-07 — M12 슬라이스 2(Sardaukar Commander와 Skill) 완료.

규범 근거는 [`rules/bloodlines.md`](../rules/bloodlines.md)이며, 콘텐츠 정의는 `content/bloodlines/sardaukar.py`, 규칙은 `rules/sardaukar.py`(획득·recruit·Desperate), `rules/combat_deployment.py`(배치·회수), `rules/strength.py`(strength와 Skill), `rules/setup.py`(setup)가 소유한다. 모든 동작은 `RulesetConfig(bloodlines=True)`에서만 켜지고, 옵션을 끈 룰셋의 상태·관측 레이아웃·codec 카탈로그는 바뀌지 않는다(관측 v6는 옵션과 무관하게 0으로 채운 세그먼트를 갖는다).

## 검증 방법

Skill 7종은 에셋 저장소 `cards/en/bloodlines/skill/*.webp`를 직접 판독해 전사했고, Canny의 초록 오각형은 `assets/icons/agent_icon_landsraad.png`, Loyal의 문양은 `assets/icons/influence_emperor.png`와 대조했다. 14장 = 7종 × 2장은 룰북 p. 3의 "두 Fierce 제외" 지시로 확인했다. Commander 규칙은 공식 룰북 PDF(scratchpad에서 확인, 저장소에 넣지 않음) p. 4를 따른다.

## 구현된 동작

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Setup | 4인: Sardaukar·Dutiful Service·Deliver Supplies·High Council·Gather Support·Assembly Hall에 Commander 1개씩, bank 1개. Skill 14장은 seeded chance `setup:skill_stack`으로 섞어 4장 face-up. 고정 Leader setup과 draft setup 모두. | `[Bloodlines p. 3]`. bank의 Commander는 Sardaukar Standard(카드 슬라이스)가 쓴다. |
| 획득 | 방문한 space에 Commander가 있으면 `board_icons`에 `sardaukar_commander` 키가 붙어 자유 순서 그룹의 효과가 된다. `acquire_sardaukar_commander(skill_id)`는 2 Solari를 내고 garrison에 recruit하며 face-up Skill 하나를 supply로 옮기고 stack에서 보충한다. 거절은 `decline_sardaukar_commander`(명시적). | "an effect of the space ... in any order" `[Bloodlines p. 4]`. 이미 가진 종류는 고를 수 없고, 고를 것이 없으면 획득 자체를 제시하지 않는다(OQ-031, 사용자 판정). Reverend Mother의 space 반복은 인쇄 아이콘만 다시 열고 이 키는 다시 열지 않는다. |
| 지불 recruit | `recruit_sardaukar_commander`: Agent turn 효과 frame과 Reveal frame에서 turn당 1회, 2 Solari, supply→garrison, Skill 없음. Agent turn에서는 `troops_recruited`에 합산돼 기본 배치 한도를 늘린다. | `[Bloodlines p. 4]` "once per turn (Agent or Reveal)". 플래그 `commander_recruited_turn`은 TURN frame이 열릴 때 초기화된다. |
| 배치·회수 | `deploy_commanders(count)`/`withdraw_commanders(count)`는 troop과 같은 frame 한도("이번 turn recruit한 유닛 + garrison 2개")를 공유하며 `combat_commanders_deployed`로 Commander 몫을 따로 센다(OQ-029 회수 규칙 동일). | `[Bloodlines p. 4]` "one of the up to two units you deploy from your garrison". |
| Strength | `units_strength`에 Commander 2를 더하고, `skill_strength`(Canny·Fierce·Loyal)는 매 step 뒤 `with_skill_strength`가 조건을 다시 판정해 차이만 반영한다(`skill_strength_applied`). Reveal 시작은 유닛 + sword + 적용된 Skill strength. Commander가 없으면 Skill은 비활성. | `[Bloodlines p. 4]`, OQ-032. Combat Intrigue 단계에서도 조건을 재판정한다. |
| Reveal 보너스 | `begin_reveal_turn`이 Commander가 Conflict에 있을 때 Charismatic(Persuasion 1)·Driven(spice 1)·Hardy(water 1)를 한 번 준다(`skill_reveal_bonus` 이벤트). Desperate는 REVEAL frame의 선택 행동 `trash_skill_for_strength`로 tile을 `skill_trash`에 보내고 검 3을 더한다. | 라운드당 1회는 Reveal이 한 번뿐이므로 자연 충족. Reveal 도중 Commander가 처음 Conflict에 들어오는 경로는 아직 없다(Combat 아이콘 슬라이스에서 재검토). |
| 정리 | `finish_combat`이 Commander를 supply로 돌려보내고 `skill_strength_applied`를 0으로 한다. | `[Bloodlines p. 4]` `[Main p. 14]`. |
| 상태·관측 | `PlayerState.commanders_supply/garrison/conflict`, `skill_ids`, `commander_recruited_turn`, `skill_strength_applied`; `GameState.sardaukar_commander_space_ids`, `sardaukar_commanders_bank`, `skill_stack`(비공개 순서), `skill_face_up`, `skill_trash`. 불변식: Skill tile은 한 존에만, 한 플레이어는 종류당 1장, 옵션이 꺼지면 전부 비어 있어야 한다. 관측은 stack 크기만 노출한다. | 관측 v6, codec v90(`bloodlines` 룰셋만 +30 템플릿). |
| UI·도구 | 서버 옵션 `bloodlines`/`tech_module`, UI 체크박스와 행동 라벨, sweep/tournament `--bloodlines --tech-module`, coverage census, 체크포인트 룰셋 식별자 파싱. | 보드 위 Commander 토큰·Skill 표시는 UI 슬라이스에서. |

| Commander = troop (슬라이스 3) | Intrigue의 `RetreatTroops`·`DeployFromGarrison`은 `count`(전체)와 `commanders`(Commander 몫, 0이면 생략) 인자로 troop과 Commander를 섞어 고르고(`rules/intrigue.py`의 `_unit_count_arguments`), 비용·보상 가능성 판정도 둘을 합쳐 센다. Chani의 "troop 2개 retreat → 검 4"는 `commanders` 0~2, Desert Scouts는 `retreat_leader_commander`. Reveal 중 배치(`add_units_to_reveal`)도 Commander 2를 센다. | `[Bloodlines p. 4]` "It is a 'troop'". 이벤트 payload는 `commanders`가 0보다 클 때만 그 키를 싣는다. |
| Conflict 카드 (슬라이스 3) | `content/uprising/conflicts.py`에 `bloodlines_only` 항목 2장: Skirmish (Wild) — I, 1위 trash 1 / 2위 water 1 + Solari 1 / 3위 Solari 2; Storms in the South — II, 1위 Spy 배치 + spice 2 / 2위 Intrigue 2 + Solari 2 / 3위 Intrigue 1 + Solari 2. 옵션을 켠 setup의 tier 풀에만 들어가고(`conflicts_by_tier(bloodlines=True)`, 미사용 8장), 관측의 Conflict identity 우주는 18종으로 늘었다(2,081→2,089). | 카드면 전사(에셋 `bloodlines/conflict/`). 이긴 wild Conflict는 도착 시 매칭하지 않는다(`combat._matching_battle_card`) `[Main p. 20]`. |
| wild끼리 매칭 (슬라이스 3) | `endgame._endgame_wild_matches`와 codec `match_endgame_wild_icon` 템플릿이 wild 쌍(정렬 순서로 한 번)을 추가한다. `flip_battle_card`·wild 템플릿은 옵션을 켠 catalog에만 Bloodlines 카드를 넣는다. | `[Bloodlines p. 5]`. OQ-005의 Combat 다중 후보 tripwire는 인쇄 아이콘에만 남는다. |

## 미완 경계

- Endgame tiebreaker "garrison의 troop 수"에 Commander를 세는지는 공식 문서가 침묵한다(현재는 세지 않음; 콘텐츠 슬라이스에서 open question으로 올릴 예정).
- 새 아이콘 4종(Spy with Deep Cover, Command, Combat, Trash an Intrigue card)은 인쇄된 카드와 함께 슬라이스 4에서. Sardaukar Standard(bank의 Commander)·Tech Module의 Commander 관련 tile도 뒤 슬라이스.

## 검증

- `tests/unit/rules/test_sardaukar.py` 26건: setup(고정·draft), 획득과 Skill 선택·중복 금지·OQ-031(고를 Skill이 없으면 획득 불가), Solari 부족 시 거절만, 지불 recruit의 turn당 1회와 Reveal turn, 배치 한도 공유와 running strength, Skill strength 조건(Landsraad Agent·상대 sandworm·Emperor 3)과 비활성, Reveal 보너스, Desperate, 정리, 상태 불변식, 관측 비노출, codec 왕복, random 3판·heuristic 1판 soundness 검사.
- 2026-09-07 소크(`--soundness-interval 25`): random `--ruleset both --bloodlines` 30판씩(60판, 41,508 step), heuristic `--rotate-leaders` 15판씩(30판, 19,584 step), 실패 0.
- 슬라이스 3 테스트(같은 파일 +5): Intrigue retreat의 Commander 몫 열거·적용, Chani retreat의 혼합 쌍, Desert Scouts의 Commander, wild Conflict 승리 시 즉시 매칭 없음, Endgame의 wild 쌍 3가지와 codec 왕복. 슬라이스 3 소크는 handoff 세션 요약.
