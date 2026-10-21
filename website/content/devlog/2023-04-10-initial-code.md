+++
title = "2023년의 초기 시도와 중단"
description = "2023년 3월에서 4월 사이에 만든 상태 클래스와 시작 카드, Poetry 구성을 정리합니다. 이 코드는 2026년 엔진과 이어지지 않는 별도의 초기 시도입니다."
date = 2023-04-10T01:54:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2023-03-24"
retrospective = true
source_ref = "c8f61677"
sources = ["dune/status.py", "dune/cards.py", "pyproject.toml", "docs/implementation-plan.md"]
+++

## 처음 남아 있는 코드

저장소의 첫 기록은 2023년 3월 24일입니다. 하루 사이에 `.gitignore`와, 게임 상태를 담는 데이터 클래스를 정의한 `status.py`(111줄)를 올렸습니다. 4월 1일에는 이 파일 안에서 `PlayerState`와 `GameState` 클래스를 나누었고, 같은 날 시작 카드를 정의한 `cards.py`(59줄)를 추가했습니다. 파일을 둘로 쪼갠 것이 아니라 한 파일 안의 클래스를 나눈 것입니다.

4월 10일에는 두 파일을 `dune` 패키지로 옮기고 Poetry 설정과 빈 `tests` 폴더를 준비했습니다. 이때의 `pyproject.toml`은 Python ^3.11, 개발 도구로 mypy, pycodestyle, pylint를 적었습니다. 커밋은 모두 5개이고, 이 날이 마지막입니다.

## 2026년 엔진의 출발점은 아닙니다

이 코드는 지금 프로젝트의 출발점이 아니라 별도의 초기 시도였습니다. 작업은 이날 이후 2026년 8월 12일까지 3년 넘게 멈췄고, 그날 새로 시작할 때 구현 계획에 다음과 같이 적었습니다.

- 기존 `dune/` 코드는 참고 자료로만 두고 새 구조와의 호환성을 요구하지 않는다.
- 배포 패키지 이름도 충돌 가능성이 큰 `dune` 대신 `dune_imperium`으로 바꾼다.
- 기존 `dune/status.py`, `dune/cards.py`는 새 코드에서 import하지 않는다.

실제로 현재 `src`, `tests`, `scripts` 어디에서도 `dune` 패키지를 import하지 않습니다. `dune` 폴더 안의 `cards.py`가 `dune.status`를 가져오는 것이 유일한 사용입니다. 이 폴더는 지금도 저장소에 그대로 남아 있지만, 2026년 엔진은 새 패키지 `src/dune_imperium`에서 처음부터 다시 시작했습니다. 8월 12일 첫 커밋에서 개발 환경도 Poetry에서 Python 3.14와 uv로 옮겼습니다.

## 이 시점의 범위

이 커밋들만으로는 게임을 진행하거나 규칙을 검증할 수 없었습니다. 상태와 시작 카드의 모양을 적어 둔 정도이고 테스트도 없었습니다. 본격적인 Uprising 구현은 [2026년 8월의 첫 글]({{< relref "devlog/2026-08-14-engine-foundation.md" >}})부터 이어집니다.

## 참고 기록

- [플레이어·게임 상태 추가](https://github.com/jungcheolseung/Dune-Imperium/commit/252b866c)
- [시작 카드 추가](https://github.com/jungcheolseung/Dune-Imperium/commit/e4c55ebc)
- [Python 패키지와 Poetry 초기 구성](https://github.com/jungcheolseung/Dune-Imperium/commit/2df8c995)
- [Python 3.14와 uv로 이전](https://github.com/jungcheolseung/Dune-Imperium/commit/e2d7f9b4)
- [새 엔진의 구현 계획(M0 항목에 `dune/` 취급이 있음)](https://github.com/jungcheolseung/Dune-Imperium/blob/a6f1449a/docs/implementation-plan.md)
