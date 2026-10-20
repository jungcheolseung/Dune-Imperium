+++
title = "초기 코드와 프로젝트 구성"
description = "플레이어·게임 상태와 시작 카드를 정의하고 Python 패키지 구성을 준비했습니다."
date = 2023-04-10
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2023-03-24"
retrospective = true
source_ref = "2df8c995"
sources = ["dune/status.py", "pyproject.toml"]
+++

## 처음 남아 있는 코드

저장소의 첫 기록은 2023년 3월입니다. 상태를 담는 데이터 클래스를 만들고, 4월에는 플레이어 상태와 게임 상태를 나누었습니다. 시작 카드 정의도 이 시기에 추가했습니다.

4월 10일에는 코드를 `dune` 패키지로 옮기고 Poetry 설정과 테스트 폴더를 준비했습니다. 현재 프로젝트의 출발점을 확인할 수 있는 작은 뼈대입니다.

## 이 시점의 범위

이 커밋들만으로 게임을 끝까지 플레이하거나 AI를 학습할 수 있었던 것은 아닙니다. 현재 Uprising 규칙 엔진과 학습 환경을 본격적으로 구성하는 기록은 2026년 8월부터 이어집니다.

## 참고 기록

- [플레이어·게임 상태 추가](https://github.com/jungcheolseung/Dune-Imperium/commit/252b866c)
- [Python 패키지와 Poetry 초기 구성](https://github.com/jungcheolseung/Dune-Imperium/commit/2df8c995)
