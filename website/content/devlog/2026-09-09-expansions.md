+++
title = "Bloodlines와 Immortality 확장"
description = "지휘관·기술 타일과 연구·접합·틀레이락스 카드를 추가하고, 화면과 AI·저장 형식에 연결했습니다."
date = 2026-09-09
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-07"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md"]
+++

## 확장을 선택 가능한 구성으로

Bloodlines와 Tech Module을 옵션으로 추가했습니다. 지휘관과 기술, 확장 카드·전투·계약을 엔진에 연결하고 화면 표시와 휴리스틱 평가도 보완했습니다. 저장할 때 선택한 확장 구성이 유지되도록 했습니다.

이 작업에서 지원한 것은 Uprising에 결합하는 확장과 기술 모듈입니다. Rise of Ix 전체 게임을 구현했다는 의미는 아닙니다.

## Immortality 추가

Immortality에서는 연구와 틀레이락스 트랙, 별도 카드 열, 접합과 관련 카드 효과를 구현했습니다. 확장 전용 결정을 AI 입력과 행동 목록에도 추가했습니다. 9월 9일까지 Bloodlines 계약 토큰과 후속 오류 수정을 이어갔습니다.

## 조합 검증

확장을 켠 무작위 게임 검사는 이중 셔플, 특정 카드의 교착, 반복 선택 같은 문제를 드러냈습니다. 카드별 회귀 테스트와 조합 실행으로 수정 사항을 확인했습니다. 확장을 켤 수 있게 하는 일과 AI가 새 선택을 잘 배우는 일은 별도의 과제로 남았습니다.

## 참고 기록

- [Bloodlines 화면·검증 마무리](https://github.com/jungcheolseung/Dune-Imperium/commit/163a35fc)
- [Immortality 구현 마무리](https://github.com/jungcheolseung/Dune-Imperium/commit/4dd14903)
- [Bloodlines 계약 토큰](https://github.com/jungcheolseung/Dune-Imperium/commit/80a51c86)
