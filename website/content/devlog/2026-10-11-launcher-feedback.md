+++
title = "런처를 만들고 실제 플레이 피드백 반영"
description = "서버를 켜는 창과 게임 연출·시계를 추가하고, 친구들과 둔 판의 불편과 사람 기보를 개발에 반영했습니다."
date = 2026-10-11
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-08"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/server-launcher-plan.md", "docs/evaluation/human-games-2026-10-10.md", "docs/worklog/2026-10.md"]
+++

## 서버 실행을 창으로

설정, 서버 시작·종료, 접속 주소, 로그를 한곳에서 다루는 런처를 만들었습니다. 게임 방 링크를 표시하고 호스트 PC가 플레이 도중 잠들지 않게 하는 기능도 연결했습니다. 터미널 명령을 매번 입력하는 부담을 줄이는 작업이었습니다.

## 한 판을 직접 두며 고치기

AI 차례와 전투 결과를 알아보기 쉽게 표시하고, 연출 속도와 효과음, 게임 전체·좌석별 시계를 추가했습니다. 친구들과 실제로 플레이한 뒤에는 선택 표시, 턴 종료, 카드 보기, 자동 저장 등에서 받은 피드백을 반영했습니다.

같은 시기 사람의 저장 게임을 현재 엔진에서 읽도록 옮기고 AI의 선택과 비교했습니다. 두 판의 사람 결정을 분석해 두 평가가 일치한 112개 국면을 문제집으로 고정했습니다.

## 기보의 역할

사람의 선택을 모두 정답으로 취급하지는 않았습니다. 사람이 더 낫게 평가된 곳과 모델이 더 낫게 평가된 곳이 모두 있었습니다. 이 문제집은 제한된 기보와 탐색 평가에서 만든 회귀 자료이며, 전체 실력 순위를 증명하는 자료는 아닙니다.

## 참고 기록

- [런처 창 구현](https://github.com/jungcheolseung/Dune-Imperium/commit/4f70c976)
- [사람 기보 분석](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/human-games-2026-10-10.md)
- [플레이 피드백과 112개 국면의 후속 기록](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/worklog/2026-10.md)
