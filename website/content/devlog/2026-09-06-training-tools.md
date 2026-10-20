+++
title = "AI 평가 도구와 첫 학습 루프"
description = "랜덤·휴리스틱·롤아웃 AI를 비교하는 도구와 셀프플레이, 신경망 학습·체크포인트 저장을 연결했습니다."
date = 2026-09-06
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-06"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/baseline-2026-09-06.md", "docs/worklog/2026-09.md"]
+++

## 비교할 기준 만들기

AI를 학습하기 전에 랜덤, 휴리스틱, 롤아웃 AI를 같은 조건으로 비교할 대회 도구를 만들었습니다. 시드와 좌석 배치를 기록해 나중에 다른 버전을 같은 조건에서 평가할 수 있도록 했습니다.

여러 게임의 신경망 추론을 묶는 셀프플레이 러너도 추가했습니다. 게임 진행은 공통 엔진이 담당하고, 정책이 현재 합법 행동 가운데 하나를 고릅니다.

## 첫 신경망과 학습

정책과 가치를 출력하는 MLP, 학습기, 체크포인트 저장·불러오기, 주기적 평가를 연결했습니다. 첫 학습 방식은 REINFORCE와 가치 기준선이었습니다. 이후 PPO와 여러 입력 구조를 실험하기 전의 단계입니다.

반복 실행은 일반 테스트에서 만나지 못한 교착도 드러냈습니다. 같은 행동을 되풀이하는 정책 문제와 합법 행동이 아예 사라지는 엔진 문제를 구분해 처리했습니다.

## 남은 문제

첫 체크포인트가 만들어졌다는 사실만으로 강한 AI가 됐다고 볼 수는 없습니다. 학습량, 비교 상대, 평가 도구의 정확성을 확인하는 일이 이후의 주요 작업이 됩니다.

## 참고 기록

- [첫 대회 도구와 기준선](https://github.com/jungcheolseung/Dune-Imperium/commit/03687815)
- [묶음 추론 셀프플레이 러너](https://github.com/jungcheolseung/Dune-Imperium/commit/ad32ea01)
- [첫 신경망·학습기·체크포인트](https://github.com/jungcheolseung/Dune-Imperium/commit/01a6a181)
