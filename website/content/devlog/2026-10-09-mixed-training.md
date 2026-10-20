+++
title = "상대 혼합 실험과 탐색 결과를 배우는 시도"
description = "모델 단독 대전의 개선이 탐색 좌석에도 이어지는지 확인하고, 후속 증류 실험은 판정 전에 마무리했습니다."
date = 2026-10-09
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-07"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/m10-2026-10-07.md", "docs/evaluation/exit-v2-2026-10-08.md"]
+++

## 같은 출발점에서 두 실행 비교

10월 7일에는 같은 모델·규칙·시드에서 앱 AI를 섞는 학습과 셀프플레이만 하는 학습을 각각 1,000회 진행했습니다. 모델끼리의 직접 대결에서는 혼합 학습 쪽이 더 나았습니다.

하지만 당시 같은 200판에서 탐색 좌석으로 비교한 결과는 반대였습니다. 이 측정에서는 이전 모델이 더 나아 플레이용 모델을 바로 교체하지 않았습니다. 후속 재측정에서는 탐색 차이가 뚜렷하지 않아, 첫 수치를 일반적인 결론으로 고정하지 않았습니다. 조건과 수치는 [실험 설명 글]({{< relref "posts/learning-with-opponents.md" >}})에서 볼 수 있습니다.

## 탐색의 선택을 학습 데이터로

다음으로 탐색 결과를 모델에 가르치는 expert iteration의 두 번째 실험을 준비했습니다. 학습에 사용한 판과 처음 보는 판의 일치율을 따로 재고, 탐색에 쓰는 정책과 가치도 분리해 비교하도록 설계했습니다.

시범 실행 뒤 510판을 수집한 상태에서 10월 9일 작업을 마무리했습니다. 학생 모델의 최종 강도 판정은 실행하지 않았으므로, 이 시도가 AI를 더 강하게 만들었다는 결과는 없습니다. 구현한 수집·학습 도구와 중단 지점을 기록으로 남겼습니다.

## 참고 기록

- [상대 혼합과 후속 비교](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-10-07.md)
- [Expert iteration v2의 설계·시범·중단](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/exit-v2-2026-10-08.md)
