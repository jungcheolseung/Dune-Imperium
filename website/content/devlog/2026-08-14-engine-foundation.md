+++
title = "규칙 명세와 한 라운드 엔진"
description = "Uprising 4인 게임을 대상으로 규칙을 정리하고, 준비 단계부터 라운드 종료까지 연결했습니다."
date = 2026-08-14
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-08-12"
retrospective = true
source_ref = "f1941ea0"
sources = ["docs/implementation-plan.md"]
+++

## 구현 기준부터 정하기

Uprising 4인 기본 게임을 구현 대상으로 정하고 공식 규칙을 문서화했습니다. 개발 환경은 Python 3.14와 uv로 옮겼습니다. 화면을 만들기 전에 게임 상태, 행동, 우연 결과를 다루는 엔진부터 구성했습니다.

## 한 라운드를 연결하기

시드를 이용한 게임 준비, 플레이어별로 가린 관측, 가능한 행동 목록을 만들었습니다. 여기에 Agent 배치, 공개 차례와 카드 획득, 전투 순위와 보상, Makers·Recall 단계를 연결했습니다.

무작위 결과도 기록에 남겨 같은 진행을 다시 재생할 수 있게 했습니다. 난수 시드를 고정하는 것과 실제 발생한 결과를 기록하는 것을 함께 사용합니다.

## 확인한 범위

무작위 행동으로 한 라운드를 돌리는 도구와 디버그 CLI를 만들고, 룰북 예시의 Agent·공개·라운드 종료 상황을 고정 시나리오로 확인했습니다. 이때의 완료 범위는 한 라운드입니다. 전체 게임, 카드별 능력과 학습은 뒤의 작업으로 남았습니다.

## 참고 기록

- [공식 규칙과 구현 계획](https://github.com/jungcheolseung/Dune-Imperium/commit/fe29f63b)
- [우연 결과를 포함한 재현 기록](https://github.com/jungcheolseung/Dune-Imperium/commit/4f41ed91)
- [한 라운드 완료 기록](https://github.com/jungcheolseung/Dune-Imperium/blob/f1941ea0/docs/implementation-plan.md)
