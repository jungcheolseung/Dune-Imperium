+++
title = "앱 방식 AI와 탐색 AI를 플레이 좌석으로 추가"
description = "규칙 기반 AI를 대전 상대로 연결하고, 학습 모델로 후보를 고른 뒤 여러 진행을 비교하는 탐색 좌석을 추가했습니다."
date = 2026-10-06
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-05"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/app-ai-2026-10-05.md", "docs/evaluation/m10-2026-10-06.md"]
+++

## 비교 상대와 플레이 상대

앱 방식의 규칙 기반 AI를 구현해 브라우저의 좌석 선택에 추가했습니다. Uprising과 지원 확장의 여러 결정에 답하도록 연결하고, 학습 결과를 비교할 상대로도 사용했습니다. 여기서 앱 AI는 이 프로젝트 안의 구현을 가리킵니다.

## 탐색 AI를 화면에 연결

탐색 AI는 학습 모델이 고른 후보를 여러 가능한 숨은 상태에서 진행해 비교합니다. 서버 시작 시 모델을 지정하고 브라우저에서 탐색 좌석을 고를 수 있게 했습니다. 생각 중인 좌석도 화면에 표시했습니다.

학습은 플레이 화면에서 사용하는 확장 구성과 지도자 드래프트에 맞춰 다시 진행했습니다. 일부 게임에는 앱 AI를 상대 좌석으로 넣었습니다. 당시 결과는 이전 모델보다 좋아졌지만, 규칙 재적응과 상대 혼합의 효과를 이 실행 하나로 나눌 수는 없었습니다.

## 다음 실험

상대를 섞는 것 자체가 도움이 되는지 확인하려면 셀프플레이만 하는 대조군이 필요했습니다. 그 비교를 다음 날 진행했습니다. 탐색 방식은 [기술 글]({{< relref "posts/how-search-ai-chooses.md" >}})에 별도로 설명했습니다.

## 참고 기록

- [앱 방식 AI 구현 기록](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/app-ai-2026-10-05.md)
- [탐색 AI 좌석 연결](https://github.com/jungcheolseung/Dune-Imperium/commit/83a381b6)
- [플레이 구성에 맞춘 재학습](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-10-06.md)
