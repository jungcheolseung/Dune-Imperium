+++
title = "Bloodlines, Tech Module, Immortality 확장과 디자이너의 공개 답변"
description = "세 확장을 서로 독립적으로 켜고 끌 수 있는 옵션으로 구현하고, 커뮤니티가 모아 둔 디자이너의 공개 답변 13건을 엔진에 반영했습니다."
date = 2026-09-09T14:56:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-07"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-09.md", "docs/rules/designer-rulings-audit.md", "docs/rules/open-questions.md", "docs/implementation-audits/bloodlines.md", "docs/implementation-audits/immortality.md"]
+++

## 확장을 켜고 끌 수 있는 옵션으로

기본 게임이 끝난 뒤 목표는 Uprising 4인용에 붙는 세 확장, Bloodlines, Tech Module, Immortality를 넣는 것이었습니다. 이 세 가지는 Uprising에 붙여 쓰는 부분만 구현한 것이며, Rise of Ix 전체 게임을 구현한 것이 아닙니다. 이 시기에는 구현을 완전하게 끝내는 일을 AI 학습보다 앞에 두기로 했습니다.

세 확장은 규칙 옵션(`bloodlines`, `tech_module`, `immortality`)으로 서로 독립적으로 켭니다. 확장 전용 카드와 지도자, 행동은 해당 옵션을 켰을 때만 덱과 선택지에 들어갑니다(Bloodlines 프로모 Ruthless Leadership은 프로모와 Bloodlines를 함께 켤 때, 지도자 Kota Odax는 Tech Module을 켤 때). 전사가 끝나지 않은 카드는 덱에 넣지 않았습니다. 확장마다 AI 입력(관측)과 행동 codec 버전이 올라갔고, 그때마다 옛 체크포인트는 불러오지 못하게 막았습니다.

| 확장 | 이 글에서 구현한 것 | 버전 변화 |
| --- | --- | --- |
| Bloodlines | Sardaukar Commander와 Skill, Conflict 카드 2장, 지도자 8명, Imperium·Intrigue·Twisted·Navigation 카드, 계약 토큰 8개 | 관측 v6–v8, codec v90 |
| Tech Module | 기술 타일 18장, Ixian Embassy, 지도자 Kota Odax | 관측 v9, codec v91–v94 |
| Immortality | Research·Tleilaxu 트랙, specimen, Tleilaxu Row와 Reclaimed Forces, Graft(두 장을 한 번에 쓰는 Agent 차례), Ghola·Chairdog·Usurp, Family Atomics | 관측 v11–v15, codec v95–v97 |

Bloodlines에서는 Commander가 troop으로 세어지는 곳(회수, 배치, 동점 판정)을 하나씩 확인했습니다. 동점 판정에서는 주둔지의 Commander를 troop으로 세기로 했습니다(`[Main p. 15]`, `[Bloodlines p. 4]`). Tech Module의 기술 타일 획득은 Landsraad 방문과 카드 할인 두 경로를 한 처리기로 묶었습니다. Immortality는 규칙 문서와 카드 전사 문서를 먼저 만든 뒤 보드(연구 트랙 21칸과 시작 칸, Tleilaxu 트랙 8칸), Tleilaxu Row, Graft, 카드 순서로 슬라이스를 나눠 하루 만에 마쳤습니다. 카드별 실물 장수는 커뮤니티가 만든 카드 목록으로 정했습니다(Imperium 30장, Intrigue 15장).

## 저장 파일에서 빠졌던 옵션

Bloodlines와 Tech Module을 넣고 화면을 확인하던 중, 저장 문서가 이 두 옵션과 프로모 옵션을 기록하지 않아 Bloodlines 게임을 불러오면 기본 규칙으로 다시 재생하려던 결함을 찾았습니다([`255fc66`](https://github.com/jungcheolseung/Dune-Imperium/commit/255fc66)). 이제 세 옵션 모두 저장 문서의 규칙 블록에 기록하고, 이 필드가 없는 옛 문서는 꺼진 것으로 읽습니다. Immortality 옵션은 처음부터 같은 방식으로 저장합니다.

## 조합 검사가 찾은 결함

확장을 켠 무작위 게임 검사에서 마감 때마다 결함이 나왔습니다. 이 검사는 일정 간격으로 모든 합법 행동을 실제로 적용해 보고 행동 번호가 왕복되는지도 확인합니다.

- Bloodlines와 Tech Module을 함께 켠 7,000판의 첫 실행은 10판이 실패했고 원인은 세 계열이었습니다. 대기 중이던 Command 선택의 카드가 다른 효과로 폐기된 경우, 배치 가능한 병력 수를 두 곳에서 다르게 센 탓에 합법 행동이 없어진 교착, 진영 칸이 아닌 곳에서 화살표 비용을 제시한 경우입니다. 고친 뒤 같은 시드를 다시 돌려 모두 끝까지 진행됐고 7,000판 재실행은 실패 0이었습니다.
- Immortality 마감 검사(830판)에서는 카드를 두 장 뽑을 때 버린 더미가 이중으로 섞여 같은 카드가 두 곳에 있게 된 결함, Usurp가 상대가 없는 칸을 제시해 생긴 교착, 접합 대상 바꾸기를 무한히 반복하는 휴리스틱을 찾았습니다. 고친 뒤 실패 0이었습니다.
- Ghola가 Duncan Idaho의 Signet 칸을 복사하는 경로에서 Agent가 이미 Conflict로 간 뒤 두 번째 배치가 오류를 내는 결함, Bloodlines와 Immortality를 함께 켰을 때 행동 목록의 주고 버리는 행동 템플릿에 Immortality 책략이 빠져 있던 결함도 검사로 나왔습니다.

## 디자이너의 공개 답변 13건

공식 규칙과 FAQ가 말하지 않는 지점에 대해, 디자이너가 포럼과 메신저에서 한 공개 답변을 커뮤니티가 정리한 FAQ 문서(1,223줄)가 있습니다. 그 가운데 구현 범위에 있는 항목을 엔진과 하나씩 대조했습니다. 결과는 일치 30여 항목, 엔진 동작과 다른 항목 13건, 아직 옮기지 못한 내용 한 가지(Bloodlines 계약 토큰 8개), 추가 확인 2건이었습니다.

이전 글에 "후속 오류 수정"이라고만 적었던 것은 사실 이 13건의 규칙 변경입니다. 디자이너의 답변이 공식 문서는 아니지만, 공식 문서가 침묵하는 곳에서는 따르기로 결정하고 판정 번호(OQ-057)에 모아 기록했습니다. 한 번에 한 묶음씩 반영했습니다.

- **첫 묶음(8건):** 대상이 없어도 낼 수 있는 책략(Impress), Change Allegiances의 두 효과를 한쪽만 또는 모두 쓰기, 책략으로 기술을 얻는 효과는 살 수 있으면 거절할 수 없음, Ghola와 접합한 Long Reach가 세 아이콘을 모두 줌, Combat 보상 순서가 결과에 영향을 주면 선 플레이어부터 턴 순서 등.
- **둘째 묶음(2건):** "Choose Two"는 두 선택을 먼저 정한 뒤 해결, Combat 보상으로 얻은 Harvest Cells를 그 Combat에서 쓰기.
- **셋째 묶음(3건):** 조건이 거짓인 의무 Agent box는 숨겨 두었다가 차례를 마칠 때까지 해결할 수 없을 때만 불발, Interstellar Trade는 한 번만, Guild Spy는 Reveal마다 한 번.

그 외에 Bloodlines 계약 토큰 8개를 옮기고, 같은 감사에서 나온 확인 두 건(Leadership의 검 계산, Duncan Idaho의 Into the Fray Agent를 Imperial Privilege로 회수하기)도 반영했습니다. 같은 날 Intrigue 카드에 따로 인쇄된 줄은 각각 따로 쓰고, 쓸 때 비용을 내기로 판정했고(OQ-058), 이 과정에서 찾은 Calculus of Power의 전사 오류를 고쳤습니다. 단순 trash 아이콘은 비용이나 자기 자신 지시가 아니면 선택입니다(`[Main p. 20]`).

이 대조는 나중에 부분적으로 다시 고쳐졌습니다. Interstellar Trade는 10월 4일 판정으로 나중에 완료한 계약마다 한 번씩 더 받는 쪽으로 되돌렸고, 감사 표에서 "일치"로 적었던 항목 가운데 Spy 배치 의무, Harvest 계약, Chairdog도 뒤에 틀린 것으로 드러났습니다. 현재 상태는 감사 문서에 날짜와 함께 남아 있습니다.

## 남은 점

- 확장을 켤 수 있게 된 것과 AI가 새 선택을 잘 두는 것은 별개입니다. 휴리스틱 AI가 확장 요소를 평가하게 하는 일은 다음 글에서 다룹니다([기준 AI를 다듬으며]({{< relref "devlog/2026-09-16-baseline-ai.md" >}})).
- 카드와 보드 전사는 9월 말 전수 감사에서 규칙 변경 130여 건이 나올 만큼 다시 정정됩니다.

## 참고 기록

- [Bloodlines 슬라이스 1–5 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/dbd9b73)
- [Immortality 옵션 골격과 카드 목록](https://github.com/jungcheolseung/Dune-Imperium/commit/19ec0fe0)
- [Ghola·Chairdog·Usurp](https://github.com/jungcheolseung/Dune-Imperium/commit/0a97bf1c)
- [Bloodlines 계약 토큰 8개](https://github.com/jungcheolseung/Dune-Imperium/commit/80a51c86)
- [디자이너 답변 첫 묶음 8건](https://github.com/jungcheolseung/Dune-Imperium/commit/5621ee23)
- [디자이너 답변 셋째 묶음](https://github.com/jungcheolseung/Dune-Imperium/commit/6782c899)
- [Intrigue 줄을 따로 쓰기(OQ-058)](https://github.com/jungcheolseung/Dune-Imperium/commit/fc91368f)
- [디자이너 답변 대조 문서](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/designer-rulings-audit.md)
- [Bloodlines 규칙 명세](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/bloodlines.md)
- [Immortality 규칙 명세](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/immortality.md)
