+++
title = "Arrakeen Scouts와 Epic Game Mode 연결"
description = "라운드별 행사·임무·경매·비밀 선택을 구현하고, 새 구성을 브라우저와 AI 좌석에서 사용할 수 있게 했습니다."
date = 2026-09-30
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-28"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/implementation-audits/epic-game-mode.md"]
+++

## 라운드 시작에 생기는 선택들

Arrakeen Scouts의 일정, 라운드 변경 효과, 소위원회, 행사와 판매, 임무, 비밀 선택과 경매를 단계별로 구현했습니다. 선택 순서와 비용처럼 추가 확인이 필요했던 부분은 문서와 테스트에 남기고 후속 수정했습니다.

9월 30일에는 Epic Game Mode와 통합하고 두 구성을 함께 켠 고정 게임을 확인했습니다. 화면에는 임무에 놓인 병력·물품·카드 수를 표시했습니다.

## 배우지 않은 행동을 만났을 때

기존 체크포인트는 새 모듈의 결정을 배운 적이 없었습니다. 합법 행동의 점수가 모두 같아 첫 선택만 반복하는 문제가 있어, 해당 결정의 행동이 전부 미학습 상태이면 휴리스틱으로 답하도록 보완했습니다.

그 뒤 체크포인트와 탐색 AI 좌석도 Scouts 게임에 참여할 수 있게 했습니다. 이는 새 모듈의 전략을 신경망이 학습했다는 뜻은 아닙니다. 동작 가능 범위와 학습한 범위를 구분해야 합니다.

## 참고 기록

- [Scouts 구현 마무리](https://github.com/jungcheolseung/Dune-Imperium/commit/44666254)
- [Epic과 Scouts 조합 검사](https://github.com/jungcheolseung/Dune-Imperium/commit/423596d0)
- [Scouts에서 체크포인트·탐색 좌석 사용](https://github.com/jungcheolseung/Dune-Imperium/commit/408c33ff)
