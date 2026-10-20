+++
title = "카드 효과와 AI 입력을 공통 능력 기록으로 정리"
description = "카드·보드·확장의 반복 효과를 공통 기록과 실행기로 옮기고, 로그·기보 이전·모델 입력을 함께 정리했습니다."
date = 2026-10-19
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-14"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/composed-effects-plan.md", "docs/entity-network-plan.md", "docs/worklog/2026-10.md"]
+++

## 카드별 분기를 줄이는 작업

비슷한 효과가 여러 처리 함수에 흩어져 있으면 고칠 곳과 검증할 곳이 늘어납니다. 비용, 대상, 보상, 행동 모양을 능력 기록으로 표현하고 공통 실행 경로가 이를 읽도록 옮겼습니다.

책략과 개인 카드에서 시작해 공개 효과, 계약과 전투 보상, 보드 칸, 지도자·기술, 확장 효과로 전환 범위를 넓혔습니다. 이어서 중복된 처리 경로와 사건 로그의 이름을 정리하고, AI 입력도 능력 기록을 읽도록 연결했습니다.

## 구조 변경과 판정 변경을 구분하기

같은 게임을 이전·이후 엔진에서 진행해 선택지·사건·관측을 비교했습니다. 의도적으로 달라지는 판정은 별도 차이 목록으로 남겼습니다. 옛 저장 기록을 새 행동 목록으로 옮기는 경로와 브라우저 검사도 함께 보완했습니다.

10월 19일에는 정리 두 번째 묶음과 모델 입력 변경을 병합했습니다. 이 시점의 행동 codec은 v149입니다. 일부 보상 합계를 기록하는 부분은 남겨 두었고, 실행·지급 흐름의 후속 재설계는 다음 단계입니다. 전체 전환이 모두 끝났다고 표현하지 않습니다.

## 모델은 바로 교체하지 않았습니다

바뀐 입력으로 재학습한 모델은 예비 비교에서 기존 플레이 모델보다 뚜렷하게 낫지 않았습니다. 탐색 좌석의 최종 교체 판정은 진행하지 않았고, 플레이용 모델은 유지했습니다.

## 참고 기록

- [효과 조각 전환 계획과 단계별 기록](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/composed-effects-plan.md)
- [두 번째 정리 묶음 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/86086c6d)
- [모델 입력 전환·재학습과 다음 단계](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/entity-network-plan.md)
