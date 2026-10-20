+++
title = "학습 정체를 조사하며 평가와 해석을 수정"
description = "순위 보상의 효과를 대조군으로 다시 확인하고, 학습 중 평가가 상대의 결과를 읽던 오류를 수정했습니다."
date = 2026-09-22
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-18"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/evaluation/m10-2026-09-22.md"]
+++

## 좋아진 이유를 분리하기

학습이 정체한 것처럼 보여 학습률과 보상을 바꾸는 실험을 진행했습니다. 순위 보상을 사용한 실행이 출발점보다 좋아졌지만, 같은 양을 학습한 대조군도 비슷하게 좋아졌습니다. 직접 비교에서는 승률 개선을 뚜렷하게 확인하지 못해 순위 보상을 채택할 근거로 삼지 않았습니다.

이후 여러 체크포인트를 연속으로 비교하자 상승이 초반에 몰려 있었습니다. 규칙 변경 뒤 새 행동에 적응한 결과라는 해석이 가능했지만, 그것을 원인으로 확정한 실험은 아니었습니다. 짧은 구간의 비교로 계속 성장한다거나 완전히 멈췄다고 단정했던 해석을 고쳤습니다.

## 평가 도구에도 오류가 있었습니다

학습 중 평가가 시험할 모델 대신 이름순으로 먼저 정렬된 상대 모델의 결과를 읽고 있었습니다. 같은 입력을 대회 CLI로 다시 실행해 차이를 찾고, 정확한 모델의 행을 선택하도록 수정했습니다.

별도로 실행한 사후 대회와 짝 비교는 이 오류의 영향을 받지 않았습니다. 학습 중 화면의 수치와 최종 판정 근거를 구분하고, 대조군과 여러 시점의 결과를 함께 남기게 된 계기입니다.

## 참고 기록

- [순위 보상을 대조군과 비교](https://github.com/jungcheolseung/Dune-Imperium/commit/6b96e510)
- [평가 수정과 후속 해석을 포함한 9월 작업 기록](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/worklog/2026-09.md)
- [학습 실험 원기록](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-09-22.md)
