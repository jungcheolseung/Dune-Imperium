+++
title = "규칙 명세와 한 라운드 엔진, 첫 행동 codec"
description = "공식 규칙을 문서로 정리하고 재생 가능한 엔진 커널을 만든 뒤, 3일 만에 한 라운드를 끝까지 돌리고 고정 행동 codec과 PettingZoo 어댑터까지 연결했습니다."
date = 2026-08-14T15:42:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-08-12"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/implementation-plan.md", "docs/rules/README.md", "docs/rules/sources.md", "docs/rules/information-visibility.md", "scripts/official-rule-sources.json"]
+++

## 구현 기준부터 정하기

[2023년의 초기 시도]({{< relref "devlog/2023-04-10-initial-code.md" >}})와 이어지지 않는 새 출발이었습니다. 8월 12일에 Python 3.14와 uv로 환경을 옮기고, 코드를 쓰기 전에 규칙 문서와 구현 계획부터 올렸습니다. 첫 문서 커밋은 16개 파일, 2,163줄입니다. 규칙 명세 13개, 구현 계획(377줄), README, 저장소 지침으로 이뤄집니다.

- **대상:** Uprising 4인 게임입니다. 첫 완성 범위는 CHOAM 모듈을 끈 기본 게임이고, 계약은 선택형 미니 확장이라 그 뒤에 규칙 옵션으로 추가하기로 했습니다.
- **규칙 출처 정책:** 판정은 공식 Main 룰북, 보드 칸 안내, FAQ(2025-01-13판)만 근거로 삼고, 문서의 모든 항목에 `[Main p. N]` 같은 쪽 번호를 붙입니다. 공식 문서에 없는 순서와 기본값은 코드에서 조용히 정하지 않고 `open-questions.md`에 먼저 적습니다. 카드 사이트는 카드 식별용 참고로만 씁니다.
- **재현 가능한 공식 자료:** 공식 PDF의 주소와 SHA-256을 목록으로 고정하고, 쪽 번호가 붙은 텍스트를 만드는 도구를 두었습니다. 룰북 PDF 자체는 저장소에 넣지 않습니다.
- **마일스톤:** 규칙 명세(R0)와 개발 골격(M0)에서 시작해 한 라운드(M3), 학습 인터페이스(M4), 기본 콘텐츠, 완주 검증, CHOAM, 평가, 학습, 사람용 화면까지 순서와 완료 조건을 계획서에 적었습니다. 단계 중 "공식 규칙 명세의 모든 항목이 분류되기 전에는 엔진 구현을 시작하지 않는다"는 조건도 있습니다.

## 엔진 커널

계획서의 구조 결정 가운데 이 뒤로 계속 유지된 것은 다음입니다.

- **상태와 관측 분리:** 모든 정보를 가진 `GameState`와, 한 플레이어에게 허용된 정보만 담은 `PlayerView`를 처음부터 나눴습니다. 상대 손패, 덱 순서, 상대 책략 같은 비공개 정보가 관측으로 새지 않게 하려는 것입니다(8월 12일 `Add redacted player observations`).
- **결정 스택:** Agent 차례의 카드, 칸, 지불, 대상을 한꺼번에 조합해 하나의 행동으로 만들지 않고, 작은 선택으로 나눠 `DecisionFrame` 스택에 쌓습니다.
- **우연의 기록:** 셔플 같은 모든 우연은 한 곳을 통과합니다. 시드만 고정하는 것이 아니라 실제로 나온 결과를 기록에 남기고, 재생할 때 그 결과를 주입합니다. 난수 구현이 바뀌어도 같은 판을 다시 볼 수 있게 하려는 설계입니다. 같은 입력의 재생이 같은 상태 해시를 만드는 것이 이 단계(M1)의 완료 조건이었습니다.
- **보상 설계는 코어 밖:** 학습용 보상 가공은 규칙 코어에 넣지 않기로 했습니다.

8월 12일과 13일에 4인 보드(22칸), 공식 시작 구성물, 시드 기반 준비 단계의 무작위화, 공유 덱 목록을 이 구조 위에 올렸습니다. 관측 경계는 규칙 문서 `information-visibility.md`에 따로 정리했습니다.

## 한 라운드 수직 조각

8월 13일과 14일에는 Round Start, Agent 배치, Reveal 차례, Imperium Row와 Reserve 획득, 전투 순위, Conflict 1·2·3단계 보상(선택적 지불, 카드 폐기, Spy 배치 포함), Makers와 Recall, 전투 중 책략 우선권 반복, 영향력과 동맹, Shield Wall을 하나씩 구현해 한 라운드로 연결했습니다. 8월 13일에만 커밋이 30개입니다. 같은 날 Conflict 보상을 점검하다 Reserve 카드 폐기 오류를 찾아 고쳤습니다.

확인은 두 가지로 했습니다. 시드 기반 무작위 라운드를 돌리는 도구와 디버그 CLI를 만들었고, 룰북 예시 세 개(Agent 차례, Reveal 차례, 라운드 종료; `[Main pp. 11, 13, 15]`)를 고정 시나리오로 옮겨 통과시켰습니다. 8월 14일 14시 17분에 이 한 라운드 단계를 완료로 표시했습니다.

## 같은 날 이어진 학습 인터페이스와 다음 규칙

한 라운드 완료 표시는 그날의 끝이 아니었습니다. 8월 14일 안에 다음이 더 들어갔습니다.

- **고정 행동 codec(M4):** 엔진 내부의 구조적 행동과는 별도로, 선택 하나하나에 고정 정수 ID를 주는 목록과 같은 폭의 합법 행동 마스크를 만들었습니다. 계획서 갱신 시점의 codec은 v6, 554개 행동입니다.
- **PettingZoo 어댑터:** AEC 방식 환경을 선택 설치(`rl`)로 추가했고, PettingZoo의 `api_test`와 `seed_test`를 통과시켰습니다. 관측과 `info`에는 전체 `GameState`를 내보내지 않습니다. 이때의 에피소드는 아직 한 라운드입니다.
- **다음 단계(M5)의 첫 시스템:** High Council과 Swordmaster, 핵심 위치 지배 보너스, Spy의 Infiltrate와 Gather Intelligence, 라운드 Reveal 순서, 공식 동률 규칙을 모두 적용한 최종 순위, 책략이 없는 Endgame의 자동 종료, 개인 덱이 모자랄 때 버린 더미를 다시 섞는 일을 재생 가능한 우연으로 처리하는 것.

계획서는 이 단계를 "RL 인터페이스 조기 검증"이라고 부릅니다. 카드 콘텐츠를 늘리기 전에 한 라운드를 AEC 루프로 돌려 보고, 정책이 보는 관측에 전체 상태가 섞이지 않는지 확인하는 것이 완료 조건이었습니다.

## 남은 점

이 글의 범위가 끝난 8월 14일 오후의 상태는 "R0, M0에서 M4까지 완료, M5 진행 중"입니다. 한 라운드까지는 끝났지만 전체 게임은 아닙니다. 대부분의 카드 효과는 아직 전사하지 않았고, 책략 Endgame과 와일드 전투 아이콘 선택은 미해결 질문(OQ-001)과 카드 전사를 기다리며 보류됐습니다. 카드 전사와 전체 게임은 [다음 글]({{< relref "devlog/2026-08-30-full-game.md" >}})에서 이어집니다.

## 참고 기록

- [공식 규칙과 구현 계획](https://github.com/jungcheolseung/Dune-Imperium/commit/fe29f63b)
- [공식 규칙 준비 도구](https://github.com/jungcheolseung/Dune-Imperium/commit/2c3ec01c)
- [우연 결과를 포함한 재현 기록](https://github.com/jungcheolseung/Dune-Imperium/commit/4f41ed91)
- [비공개 정보를 가린 관측](https://github.com/jungcheolseung/Dune-Imperium/commit/9e79499c)
- [한 라운드 완료 표시](https://github.com/jungcheolseung/Dune-Imperium/commit/f1941ea0)
- [고정 행동 codec](https://github.com/jungcheolseung/Dune-Imperium/commit/69140dc1)와 [PettingZoo 어댑터](https://github.com/jungcheolseung/Dune-Imperium/commit/a0ae35ce)
- [8월 14일 끝 시점의 구현 계획](https://github.com/jungcheolseung/Dune-Imperium/blob/a6f1449a/docs/implementation-plan.md)
- [규칙 명세 개요](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/README.md)와 [정보 공개 범위](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/information-visibility.md)
