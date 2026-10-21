+++
title = "Arrakeen Scouts, Go to 11, Epic Game Mode를 옵션으로 더하기"
description = "공식 룰북이 없는 Arrakeen Scouts 모드를 구현하고 원문과 대조해 고쳤습니다. Go to 11과 Epic Game Mode를 더했고, Scouts와 Epic을 끈 게임은 이전과 바이트 단위로 같게 지켰습니다. 신경망이 배우지 않은 Scouts 결정은 휴리스틱이 대신 답합니다."
date = 2026-09-30T15:42:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-27"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-09.md", "docs/arrakeen-scouts-design.md", "docs/rules/epic-game-mode.md", "docs/implementation-audits/epic-game-mode.md", "docs/rules/open-questions.md"]
+++

## 세 옵션과 지킨 원칙

9월 27일부터 30일까지 규칙 옵션 세 개를 더했습니다.

- **Arrakeen Scouts:** 라운드마다 Subcommittee, 임무, 이벤트, 경매, 판매가 공개되는 모듈입니다. 공식 룰북이 없어 공식 컴패니언 앱의 모드가 출처입니다.
- **Go to 11:** Immortality 룰북이 소개하는 점수 변형입니다.
- **Epic Game Mode:** Rise of Ix 룰북의 더 긴 게임 변형입니다.

세 옵션을 만들 때 지킨 원칙은 하나입니다. **옵션을 끈 게임은 이전과 같아야 합니다.** 이 옵션들을 더해도 기존 대국 기록, 저장 파일, 학습 데이터의 의미가 바뀌어서는 안 되기 때문입니다. Scouts와 Epic은 바이트 단위로 같게 했고, Go to 11은 시작 점수 설정 하나만 더해 끄면 동작이 그대로입니다(상태 해시는 제외). 슬라이스마다 옵션을 끈 룰셋의 chance 흐름, 카탈로그(기본 4,425줄), 관측의 옛 칸이 옛 값 그대로인지 확인하고 기준값을 다시 고정했습니다. Epic은 옵션을 끈 72개 룰셋의 카탈로그가 이전 master와 바이트 단위로 같음을 따로 확인했습니다.

## Arrakeen Scouts 구현

엔진은 4인 규칙만 옮겼습니다. 라운드 구성은 1라운드에 Subcommittee 5개, 2–3라운드에 임무, 4–7라운드에 이벤트이고, 5·6라운드에 중간 경매가, 8·9라운드에 후반 경매가 나올 수 있으며, 후반 경매가 없는 8·9라운드에는 판매가 나옵니다. Subcommittee는 High Council 자리를 차지하면 가입하고, 임무는 병력이나 자원을 칸에 세워 두었다가 그 칸을 방문한 좌석이 받고, 경매는 봉인 입찰입니다.

설계에서 정한 것은 다음과 같습니다.

- **일정은 공개되는 라운드에 chance로 추첨합니다.** 게임 시작에 전체를 미리 뽑으면 엔진 상태에 숨은 미래가 남습니다. 각 추첨은 앞선 결과에만 의존하므로 분포는 같게 두면서 이를 피했습니다. Subcommittee도 1라운드 시작에 뽑아 리더 드래프트 전에 공개되지 않게 했습니다.
- **Scouts 단계는 어느 좌석의 턴에도 속하지 않습니다.** Control 방어 배치 단계처럼 턴 프레임 없이 서고, 진행 위치를 따로 기억합니다. "이번 턴에 얻은 것"을 세는 효과에 들어가거나 교착이 생기는 일을 막기 위해서입니다.
- **봉인 입찰과 비밀 선택은 한 좌석씩 비공개로 확정합니다.** 행동 번호, 공개 이벤트, 서버의 미리보기로 다른 좌석이 알 수 없게 했습니다.

구현은 슬라이스 열 개(명세·카탈로그, 옵션 골격, 일정과 라운드 흐름, Subcommittee, 선택형 이벤트와 판매, 임무, 비밀 선택, 경매, 서버·화면, 휴리스틱과 교차 소크)로 나눴고, 각각 `Play`와 `Document` 커밋 한 쌍입니다. 9월 28일에 끝났을 때 행동 codec은 v111에서 v119, 관측은 v21에서 v25가 됐고 pytest 2,694개, 브라우저 E2E 29종이 통과했습니다. 무작위·휴리스틱 소크 수천 판은 실패 0이었습니다. 소크가 찾은 오류 둘은 Prison Planet 지배 마커를 놓은 좌석의 세 번째 지배, CHOAM Research의 뒷면 Immediate 계약을 Intrigue 없는 방문자가 만나면 생기는 교착(OQ-090)이었습니다. 슬라이스 7의 독립 검토는 비밀 선택 단계의 되돌리기 판정과 미리보기에서 정보가 새는 경로를 찾아 고쳤습니다.

## 원문과 일괄 검토

항목이 많아서 구현을 끝낸 뒤 구현 문구를 영어 원문과 한 줄씩 대조하는 일괄 검토를 9월 29일에 세 차례 했고, 30일에 남은 판정을 더했습니다. 원문이 정하지 않은 부분은 프로젝트 관례로 정하고 미결 질문에 근거와 함께 남겼습니다.

- **임무 참여.** 임무는 인쇄된 병력 수를 모두 세워야 참여할 수 있습니다. 구현은 1개만 있어도 참여시키고 가진 만큼만 세우고 있었는데, 원문에 없는 선택지였습니다(OQ-088). Immortality에서는 모자란 만큼 specimen을 먼저 공급처로 돌려 채울 수 있습니다.
- **경매 보상과 입찰.** 보상은 순위 순서로, 같은 순위는 First Player부터 받습니다(OQ-073). Mercenaries의 입찰 상한은 넣을 수 있는 병력 수입니다.
- **Subcommittee 가입 시점.** Subcommittee를 보드 아이콘처럼 턴 안 자유 순서로 다시 짜 보려 했지만 영어 원문과 부딪쳐 되돌렸습니다. 이후 판정(OQ-076 대안 C)으로, High Council 자리를 새로 차지한 턴 안이면 언제든 다른 효과와 같은 자유 순서로 가입하게 했습니다(`[Main p. 9]`, 프로젝트 관례). 가입이 턴의 마지막 효과이면 비용과 보상 줄이 턴이 닫힌 뒤에 풀려 그 턴 spice 장부에 들지 않는 한계는 실험으로 확인했고, 턴 종료를 명시적 단계로 바꾼 10월 작업에서 해소됐습니다([10월 글]({{< relref path="devlog/2026-10-09-turn-end.md" >}})).
- **Round Start 순서.** 공개, Control 방어 배치(선택), 카드 뽑기 순서로 고쳤습니다(`[Main p. 8, 10, 20]`). 검토가 Tech가 켜진 게임의 약 1%에서 정지가 생기는 것을 찾아 고쳤습니다. 밀린 Tech 카드 뽑기가 방어 배치와 손패 뽑기 사이에 끼어들던 오류입니다.
- **선택 불가 표시.** 지금 고를 수 없는 선택지를 이유와 함께 회색으로 보이게 하는 첫 단계는 엔진이 이미 쓰는 막힘 판정을 그대로 내보냅니다. 합법 행동이 달라지지 않았음을 같은 상태 13만 결정의 비교에서 차이 0으로 확인했고, 숨은 정보 누출도 0이었습니다.

이 검토와 판정의 결과로 codec은 v120(Go to 11 병합 뒤)에서 v123, 관측은 v25에서 v27이 됐습니다. 검증은 마지막 묶음에서 pytest 2,851개, 소크 1,950판 실패 0, E2E 31종입니다.

## Go to 11

Immortality 룰북이 소개하는 변형입니다. 4인 게임은 점수 마커를 1이 아니라 0에서 시작하고 10점에서 Endgame이 열립니다(`[Immortality p. 12]`). 원판용 룰북의 변형을 Uprising에 쓰는 것, 그리고 Immortality를 켰을 때만 고를 수 있게 하는 것은 프로젝트 결정입니다(OQ-091). 새 게임 화면에서는 기본으로 켜고, 엔진과 CLI의 기본은 꺼짐이라 학습과 소크의 기준은 바뀌지 않습니다. 종료 조건을 11로 바꾸지 않는다는 것은 테스트(`test_go_to_11_still_enters_endgame_at_ten`)로 고정했습니다. 검증은 pytest 2,714개, E2E 30종, 소크 2,200판과 Scouts 병합 뒤 900판 실패 0, 체크포인트 좌석 4판 불법 행동 0입니다. codec은 v120입니다.

## Epic Game Mode

Rise of Ix 룰북의 변형입니다(`[Rise of Ix p. 10]`). 12점까지 하고, Conflict I은 쓰지 않으며, 무작위 Conflict II 5장을 Conflict III 5장 위에 놓습니다. 시작 덱의 Dune, the Desert Planet 1장을 Control the Spice로 바꾸고, 각자 Intrigue 1장을 뽑고, 주둔지에 병력 5개로 시작합니다. Uprising에서는 Conflict III가 한 장 모자라 Economic Supremacy를 더하라고 룰북이 지시합니다(`[Main p. 18]`).

Rise of Ix 확장 자체는 구현하지 않고 이 모드가 쓰는 카드 두 장만 가져왔습니다(프로젝트 결정, OQ-092). Economic Supremacy에는 전투 아이콘이 없고, 한 줄에 화살표 둘짜리 보상을 인쇄 순서(Solari, 그다음 spice)대로 따로 묻습니다. Go to 11과 함께 켜면 0점에서 시작해 12점에서 끝납니다(OQ-093). Rise of Ix 룰북은 더 긴 게임에 Scouts를 함께 쓰라고 권하므로 두 옵션이 같이 동작하는 고정 판 하나를 테스트로 둡니다.

Epic은 별도 브랜치에서 구현해 pytest 2,813개, E2E 30종, `--epic` 소크 1,200판 실패 0을 확인했습니다. 9월 30일 Scouts 쪽 줄기와 합칠 때 충돌 7개 파일을 풀었고(버전 주석, 가져오기, 라벨), 합친 뒤 pytest 2,968개, E2E 31종, 자동 대전 1,150판 실패 0을 확인했습니다. 합친 결과의 codec은 v124, 관측은 v28입니다.

## 신경망이 배우지 않은 Scouts 결정

플레이 화면의 신경망·탐색 AI 좌석을 Scouts 게임에 앉히려면 문제가 하나 있었습니다. 지금까지의 체크포인트는 Scouts 없이 학습했고, 새 행동 칸은 출력이 모두 0에서 시작합니다. v111 기준 체크포인트(7081)를 휴리스틱 3명과 200판씩 두어 보니, 좌석의 Scouts 결정 82–91%가 합법 행동 전부가 이렇게 배우지 않은 칸이었고 선택은 늘 첫 줄로 퇴화했습니다.

- 봉인 입찰은 언제나 0을 확정하고, Critical Moment 호가도 언제나 0이었습니다.
- 비밀 선택은 언제나 0번이었고, 임무에는 언제나 참여하지 않았습니다.
- Subcommittee 가입 결정은 언제나 거절했고, 이벤트와 판매는 거의 언제나 0번 줄을 골랐습니다.

그래서 합법 행동이 전부 학습하지 않은 칸인 결정은 에이전트 시드로 만든 휴리스틱이 대신 답하게 했습니다. 탐색 좌석은 그런 결정을 탐색하지 않고, 시뮬레이션 안에서는 chance 시드로 만든 휴리스틱이 답합니다. 학습한 행동이 하나라도 섞인 결정은 그대로 신경망이 고릅니다([구현](https://github.com/jungcheolseung/Dune-Imperium/commit/dde069ff), [좌석 허용](https://github.com/jungcheolseung/Dune-Imperium/commit/408c33ff)).

같은 시드 200판 짝 비교(좌석 0 대 휴리스틱 3명)에서 기본 구성 우승률은 46.0%에서 45.5%(−0.5%p [−9.5, +8.5])로 같았고, 확장을 모두 켠 구성은 84.5%에서 90.5%(+6.0%p [0.0, +12.0], 구간 하한이 0)였습니다. 같은 시드에서 휴리스틱이 좌석 0에 앉은 승률은 22.5%와 24.5%입니다. 강도는 비슷하거나 약간 낫다는 정도이고, 좌석이 입찰하고 임무와 Subcommittee에 가입하게 됐다는 점이 달라졌습니다. 독립 검토는 탐색 좌석이 남의 입찰과 비밀 선택을 바꿔도 자기 결정이 비트 단위로 같음을 확인했습니다.

이는 **신경망이 Scouts를 학습했다는 뜻이 아닙니다.** Scouts 결정은 학습하지 않은 칸이어서 휴리스틱이 답할 뿐이고, Scouts는 학습 설정에도 들어 있지 않습니다. 같은 규칙이 codec 이관 때 새로 생긴 칸에도 일반적으로 적용되므로, 현재 codec이 아닌 옛 파일(대조군 5081은 43칸, 5600은 16칸)은 자기 룰셋에서도 `take_contract` 결정이 10판에 2–3번 휴리스틱으로 넘어갑니다(고른 답은 같았습니다). 이런 대조군을 쓰는 비교에서는 이를 알고 해석합니다.

보드 위에는 임무 조각도 그렸습니다. 세워 둔 병력은 좌석 색 큐브, Prison Planet의 지배 마커는 좌석 색 깃발, 은행 물품은 인쇄된 크기의 spice·Solari·물입니다. 자리는 스캔에서 잰 표를 쓰고 E2E가 임무 16종을 여섯 시드로 봅니다. 마지막 확인으로 브라우저에서 좌석 0 사람, 1 체크포인트, 2–3 휴리스틱으로 모든 확장과 Epic, Go to 11, Scouts를 켠 한 판(시드 7)을 끝까지 두었고 8라운드에 12점으로 끝났습니다. 임무 참여가 되돌릴 수 없는 것은 다음이 chance이기 때문이며 오류가 아닙니다(OQ-010).

## 남은 점

- Scouts는 학습하지 않았습니다. 학습에 넣는 것은 따로 정하기로 했습니다.
- 휴리스틱 대체의 효과는 200판 한 쌍이라 확장 구성의 구간 하한이 0입니다. 약해지지 않았다는 확인이지 강해졌다는 근거는 아닙니다.
- Epic의 Economic Supremacy는 비용이 Solari인지 spice인지가 관측에 없고 순서로만 구별됩니다. Epic 판을 학습에 넣을 때 다시 봐야 합니다.

## 참고 기록

- [Scouts 구현 마무리(슬라이스 10)](https://github.com/jungcheolseung/Dune-Imperium/commit/44666254)
- [Go to 11 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/1c86685b)
- [Epic 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/8b3780ee), [Epic과 Scouts 조합 검사](https://github.com/jungcheolseung/Dune-Imperium/commit/423596d0)
- [Scouts AI 좌석 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/b7cf49cf)
- [Subcommittee 가입 시점(OQ-076)](https://github.com/jungcheolseung/Dune-Imperium/commit/88b9ea43)
- [Epic Game Mode 규칙 명세](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/epic-game-mode.md), [Epic 구현 감사](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/implementation-audits/epic-game-mode.md)
- [미결 질문과 판정(OQ-073, 076, 088, 091–093)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
