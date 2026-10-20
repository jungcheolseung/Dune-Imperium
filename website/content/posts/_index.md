+++
title = "기술 글"
description = "규칙 엔진의 구조와 AI 동작, 학습·평가 실험을 설명합니다."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 40
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/implementation-plan.md", "docs/evaluation/README.md"]
+++

보드게임의 규칙을 실행 가능한 코드로 옮기고, 그 위에서 사람이 함께 둘 AI를 만듭니다.
이곳에는 구조와 동작을 설명하는 글을 모았습니다. 날짜별 진행 과정은 [개발일지]({{< relref "devlog/_index.md" >}})에서 볼 수 있습니다.

## 규칙 엔진 구현기

카드 효과를 처리하는 방법, 합법 행동과 숨은 정보, 게임을 다시 재현하는 도구와 검증을 다룹니다.

[첫 글: 보드게임 규칙을 실행 가능한 엔진으로 옮기기]({{< relref "posts/rules-to-engine.md" >}})

## AI 학습 실험

AI가 한 수를 고르는 방식부터 학습 상대·모델·탐색을 바꾼 실험까지 소개합니다.
실험 결과는 측정 날짜와 조건을 함께 적고, 실패한 시도와 남은 질문도 기록합니다.

- [AI는 어떻게 한 수를 고르는가]({{< relref "posts/how-search-ai-chooses.md" >}})
- [학습 상대를 바꾸면 AI가 더 강해질까?]({{< relref "posts/learning-with-opponents.md" >}})

직접 플레이하는 방법은 [사용법]({{< relref "guides/_index.md" >}})에,
사용자에게 달라진 기능은 [업데이트]({{< relref "updates/_index.md" >}})에 정리합니다.
