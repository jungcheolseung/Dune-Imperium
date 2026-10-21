+++
title = "카드·보드 전사 348항목을 다시 읽은 전수 감사"
description = "카드와 보드 항목 348개를 인쇄된 면과 처음부터 다시 대조해 확정 오류 114건을 찾아 고치고, 행동 codec을 v107에서 v111로 올렸습니다. 이후의 측정과 체크포인트는 모두 옛 규칙의 것이 되어 M10 학습을 새 규칙에서 다시 시작했습니다."
date = 2026-09-28T07:32:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-25"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/implementation-audits/transcription-audit-2026-09-26.md", "docs/evaluation/m10-2026-09-27.md", "docs/evaluation/m10-2026-09-28.md", "docs/worklog/2026-09.md"]
+++

## 오독 둘에서 전수 감사로

9월 25일, 카드 면을 다시 읽다가 Chani와 Count Hasimir Fenring의 Signet 보상을 잘못 옮겨 적은 것이 드러났습니다. Chani의 Fedaykin Maneuver는 병력 2를 소집하는 줄 알았지만 카드 면의 아이콘은 카드 2장 뽑기였고, Fenring의 Corrino Liaison은 일반 Spy가 아니라 Spy with Deep Cover였습니다. 같은 아이콘을 카드 368장에서 템플릿 매칭으로 찾아보니 엔진 목록에 없던 Storms in the South(Bloodlines Conflict)의 1등 보상도 같은 아이콘이었습니다. 한 카드의 오독이 아니라 전사 방식의 문제라는 뜻이어서, 모든 카드와 보드 칸을 처음부터 다시 대조하기로 했습니다.

## 방법

대상은 348항목입니다. 시작 카드 8, Reserve 2, Imperium 109, Tleilaxu 20, Intrigue 90(Twisted와 Navigation 포함), Contract 28, Conflict 18, Tech 18, Skill 7, 지도자 19(뒤집힌 면 포함), 보드 칸 23, 그리고 영향력 트랙·관측소·Bene Tleilax 보드·Ixian Embassy·Research Station 덧판·매수 같은 보드 항목 6개입니다. 항목마다 세 단계를 거쳤습니다.

1. **블라인드 전사.** 엔진의 데이터와 코드를 보지 않고 카드 면을 확대해 아이콘과 문구를 옮겨 적습니다. 공식 아이콘 안내(`[Main p. 20]`, `[Bloodlines pp. 5, 12]`, `[Immortality p. 16]`, `[Board Guide p. 14]`)와 닮은 아이콘 목록을 참고했습니다.
2. **엔진과 대조.** 전사 결과를 엔진 정의, 구현 코드, 화면 문구와 비교합니다. 블라인드 전사와 엔진이 다른 곳은 반드시 확대해 어느 쪽이 맞는지 판정했습니다.
3. **독립 반박.** 불일치마다 서로 독립적으로 반박을 시도하는 검증을 세 번 거치고, 둘 이상이 반박하지 못해야 확정했습니다.

그 뒤 커뮤니티가 정리한 카드 장수 목록과 소속, Agent 아이콘, 비용, Reveal 수치, 매수를 따로 기계 대조했습니다. 감사가 놓친 오류는 없었고, 그 목록 쪽의 오류 8건은 카드 면으로 판정했습니다. 영향이 큰 발견 8장은 카드 면을 직접 확인했습니다.

결과는 일치 258, 불일치 89, 불확실 1입니다. 확정 발견은 114건(규칙 80, 표시 32, 불확실 2)이었고 2건은 반박됐습니다. 매수는 모두 맞았습니다.

## 기본판 카드도 틀려 있었습니다

확정 발견에는 확장이 아니라 기본판 카드가 여럿 들어 있었습니다. The Spice Must Flow의 Reveal(검 1이 아니라 spice 1), Covert Operation의 Reveal(Persuasion 2가 아니라 Spy 2), Subversive Advisor(Solari 1이 아니라 Persuasion 1), Calculus of Power·Maker Keeper·Undercover Asset·Chani, Clever Tactician의 Agent 아이콘, Prepare the Way·Bene Gesserit Operative·In High Places·Overthrow의 소속, Sardaukar Coordination의 Persuasion 2입니다. 8월 구현 이후 모든 판과 학습이 옛 값으로 돌았다는 뜻입니다.

규칙에 해당하는 오류는 카드 한 장의 수치뿐 아니라 효과가 발동하는 시점·범위에도 있었습니다. 예를 들어 Spy 공급처가 빈 상태에서 Spy 보상을 받을 때 거절할 수 없는 선행 회수를 강제하던 곳, Command (6+) 판정이 만들어진 Persuasion이 아니라 쓰고 남은 Persuasion을 봐야 하는 곳이 이에 해당합니다.

## 처리

확정 발견 113건을 여덟 작업 단위(카드 데이터, 새 Imperium 효과, Agent 칸 로직, Reveal 로직, Intrigue, Spy·Conflict 보상·계약, Tech·Skill·지도자·Ixian Embassy, 표시 문구)로 나눠 각각 별도 작업 트리에서 고쳤습니다. 단위마다 독립 검토를 받은 뒤 합쳤습니다. 나머지 한 건(Subversive Advisor가 먼저 trash될 때의 기본 Influence)은 공식 문서가 답하지 않는 드문 순서여서 당시에는 고치지 않았습니다.

합친 뒤에는 단위 사이에서 생긴 문제를 찾는 통합 검토를 영역 여섯 개(Reveal, 지도자·설정, Agent 칸, Combat·Contract·Spy, Intrigue·Tech·보드, 콘텐츠·codec·관측)로 돌려 확정 18건을 더 고쳤습니다. 예를 들면 Command Center로 병력 2를 후퇴시켜도 전투력이 줄지 않던 것, Reveal 중 들어온 카드의 Command (6+) 효과가 두 번 지급되던 것입니다.

규칙서가 답하지 않는 곳은 임의로 채우지 않고 미결 질문으로 올려 판정을 받았습니다.

- Tenuous Bond·Grasp Arrakis·Battlefield Research는 칸의 색띠와 카드 아래에 인쇄된 시점(COMBAT / ENDGAME, PLOT / COMBAT)대로 칸마다 한 시점만 허용합니다. 두 시점을 모두 열던 이전 전사가 오류였습니다.
- Coercive Negotiation은 조건이 되면 반드시 수행하고, 가져갈 계약이 3장 미만이면 낼 수 없습니다.
- False Orders의 강제 Spy 이동은 공식 FAQ(`[FAQ p. 2]`)대로 Agent를 보낸 공간과 연결되지 않은 빈 관측소로 가고, 갈 곳이 없는 Spy는 공급처로 돌아갑니다.
- Reclaimed Forces의 획득도 획득이라 face-up Call to Arms가 발동합니다(`[Immortality p. 9]`). 모든 Agent 회수는 Imperial Privilege처럼 Conflict에 간 Agent를 되돌릴 수 있습니다. Commander를 소집하면 Commander를 배치할 몫이 따로 생깁니다(`[Main p. 10]` `[FAQ p. 4]`).

## 표준 계약 구성 정정

9월 27일 저녁에는 감사와 별개로 한 가지가 더 드러났습니다. 표준 계약 20장 안에 Rise of Ix 전용 타일 4장(Espionage II, Harvest 3+·4+의 Contract판, Heighliner III)이 확장 없이 들어 있었고, 그 자리에 있어야 할 Spice Refinery I·II와 두 번째 Espionage I·Harvest 3+가 빠져 있었습니다(`[Main p. 16]`). 이 정정으로 codec이 v111, 관측이 v21이 됐습니다.

같은 날 저녁 화면에서는 보드 칸과 계약이 같은 id를 쓰는 곳에서 조회가 둘을 구별하지 못해 Deliver Supplies 칸이 계약 그림으로 보이던 오류도 고쳤습니다. 조회에 종류를 넘기도록 바꾸고, 모든 페이지의 JavaScript 오류를 E2E 실패로 세게 했습니다.

## 버전과 검증

- **codec:** 감사 v108, 판정 세 건 v109, Agent 칸 Spy의 거절 v110, 계약 구성 v111. 관측 v20은 감사까지 인코더가 바이트 단위로 같았고, 계약 구성 정정에서 v21이 됐습니다.
- **체크포인트:** 형식 2 체크포인트는 행동 정체성으로 새 codec에 옮겨집니다. 5081은 v107에서 v108로 유지 32,980·새 24·삭제 7, v110에서 v111로는 유지 32,991·새 16·삭제 16(관측은 4,305열 유지·새 22·삭제 44)이었습니다.
- **감사 직후 검증:** pytest 2,279개, Ruff, mypy, 무작위·휴리스틱 3,400판 소크 실패 0, 모든 합법 행동을 인코딩해 보는 codec 탐침에서 빠진 행동 0, 브라우저 E2E 7종. 평가 문제집과 관측 golden 인코딩은 규칙이 바뀐 만큼 다시 고정했습니다.

## 이전 측정은 옛 규칙의 것입니다

규칙이 기본판 카드까지 넓게 바뀌었으므로, [평가 정정]({{< relref "devlog/2026-09-22-evaluation-corrections.md" >}})과 [탐색 AI]({{< relref "devlog/2026-09-25-policy-search.md" >}}) 글의 평가 수치와 체크포인트(5081, 7081 착취자, 탐색 좌석 표)는 모두 옛 규칙에서 나온 값입니다. 이 값을 새 규칙의 성능으로 읽으면 안 됩니다. 다음 학습과 비교는 새 규칙에서 기준선부터 다시 쟀습니다.

## M10 재개: 새 규칙에 다시 적응하기

**v110 재적응.** 5081에서 같은 설정으로 1,000 iteration을 학습해 6081까지 갔습니다(4.5시간). 2 대 2 미러 1,400판 사다리입니다.

| 비교 | 승률 차 [95% 구간] |
|---|---|
| 5600 대 5081 | +8.1%p [+3.0, +13.4] |
| 6081 대 5600 | −3.6%p [−8.9, +1.6], 승점 마진은 갈림 |
| 6081 대 5081 | +3.1%p [−2.0, +8.1] |

재적응의 이득은 첫 500 iteration에 다 왔습니다. 휴리스틱 3명 상대 승률은 86.5%와 86.8%로 여전히 포화입니다.

**`mlp_slots` 시도.** 신경망은 관측 전체를 크기 값으로 읽기 때문에, Imperium Row나 현재 Conflict처럼 "무슨 카드가 있는가"를 번호로 담은 칸을 구별하기 어렵다고 가설을 세웠습니다. 실제로 카드를 바꿔 넣었을 때 가치 출력의 평균 변화는 Row의 먼 카드 교체 0.0013, Conflict 교체 0.0011로 손패 카드 교체(0.039)의 30분의 1 안팎이었습니다. 이 칸마다 임베딩 행을 더하는 `mlp_slots` 네트워크를 만들어 같은 조건으로 학습했습니다. 반응은 확실히 커졌습니다(Row 먼 교체 2.4배, Conflict 6.3배). 그러나 6081에서 같은 학습을 한 일반 MLP와의 승률 차는 +1.3%p [−2.3, +4.9]로 불확정이었고, 2,000 iteration까지 연장하니 −4.2%p [−7.8, −0.6]이 되어 미리 정한 규칙에 따라 무익으로 끝냈습니다. 신경망이 Row를 읽게 만드는 것과 그 정보로 더 강해지는 것은 별개였고, 결과 신호 하나로 돈 셀프플레이는 후자를 이끌어 내지 못했습니다. 이 사이에 합법 행동만 쓰는 학습기를 넣어 갱신 단계가 4.3배 빨라졌고 iteration당 시간이 약 15.5초에서 10초로 줄었습니다.

**v111 재적응.** 계약 구성 정정 뒤 v110 체크포인트를 v111로 옮겨 1,000 iteration을 더 학습했습니다(7081, 약 3시간). 이번에는 1,000 iteration 내내 올랐습니다.

| 비교 (각 1,400판) | 승률 차 [95% 구간] |
|---|---|
| 6600 대 5600 | +7.0%p [+1.7, +12.3] |
| 7081 대 6600 | +11.7%p [+6.6, +16.9] |
| 7081 대 5600 | +18.3%p [+13.1, +23.4] |

v111의 기준 체크포인트는 7081로 정했습니다. 다만 이 +18.3%p는 일반적인 실력 차로 읽으면 안 됩니다. 비교 상대인 5600은 새 계약 4장의 행동과 관측 열이 0에서 시작한 채 한 번도 학습하지 못했기 때문에 "새 계약을 못 다룬다"는 몫이 섞였을 수 있고, 7081을 다른 상대로 재지 않았습니다. 이 구간이 계속 오른 원인도 알지 못합니다.

## 남은 점

- 탐색 좌석의 새 규칙 표는 아직 재지 않았습니다. 후보는 탐색 좌석 표를 7081로 다시 재는 것, slot 네트워크로 expert iteration을 다시 해 보는 것, 같은 설정을 더 돌리는 것입니다.
- 모든 학습 비교는 한 학습 시드의 두 팔입니다.
- 가치 민감도는 가치 출력만 본 것이고, 정책이 Row에 반응해 무엇을 사는지는 재지 않았습니다.

## 참고 기록

- [전수 감사 기록: 방법, 발견 목록, 처리, 판정](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/implementation-audits/transcription-audit-2026-09-26.md)
- [감사 수정 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/566109b0)
- [Chani·Fenring Signet 정정](https://github.com/jungcheolseung/Dune-Imperium/commit/27ed643e)
- [표준 계약 구성 정정](https://github.com/jungcheolseung/Dune-Imperium/commit/0553c2e3)
- [M10 재개 기록: v110 재적응과 mlp_slots](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-27.md)
- [M10 기록: v111 재적응과 slot 연장](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-28.md)
- [앞 글: 탐색 AI]({{< relref "devlog/2026-09-25-policy-search.md" >}})
