+++
title = "AI 고르기"
description = "별도 모델 없이 시작하는 기본 AI와 학습 모델을 사용하는 AI의 차이를 안내합니다."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 50
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/search-ai.md", "docs/remote-play-host-guide.md", "src/dune_imperium/cli/server.py", "src/dune_imperium/launcher/command.py"]
+++

처음에는 **앱 AI**로 시작하면 됩니다. 어려움·보통·쉬움 중 고를 수 있으며 별도 학습 모델 파일이 필요하지 않습니다.
로컬 서버의 기본 상대는 앱 AI 어려움입니다.

## 준비물과 차이

| 종류 | 고르는 방식 | 추가 학습 모델 |
| --- | --- | --- |
| 앱 AI | 현재 한 수의 이득을 정해진 평가 방식으로 판단 | 필요 없음 |
| 휴리스틱·랜덤 | 규칙 기반 점수 또는 무작위 선택 | 필요 없음 |
| 롤아웃 | 후보를 두어 보고 정해진 평가 방식으로 비교 | 필요 없음 |
| 학습 체크포인트 AI | 학습한 모델의 행동 점수를 사용 | 필요 |
| 탐색 AI | 학습 모델로 후보를 고르고 가능한 상황에서 두어 보며 비교 | 필요 |

같은 이름의 AI라도 선택한 규칙과 모델에 따라 플레이가 달라질 수 있습니다.
과거 실험의 승률은 그때의 조건에서 잰 값이며 현재 모든 구성의 강도를 뜻하지 않습니다.

## 탐색 AI를 쓰려면

서버를 맡은 PC에 **호환 모델 파일**과 추가 실행 패키지가 필요합니다.
모델을 준비했다면 프로젝트 폴더에서 다음 의존성을 설치합니다.

```bash
uv sync --locked --extra ui --extra rl --extra train
```

이 명령은 모델 자체를 내려받지 않습니다. 현재 공개 다운로드 모델을 제공하지 않으므로,
파일을 따로 준비하지 않았다면 기본 AI를 사용하세요.

호환 모델을 가진 사용자는 런처에서 모델을 지정하거나, 기본 위치인 `checkpoints/play/search.pt`를 사용할 수 있습니다.
터미널에서는 실제 파일 경로를 지정할 수 있습니다.

```bash
uv run dune-imperium-server --autosave --search-checkpoint checkpoints/play/search.pt
```

서버가 필요한 패키지와 모델을 사용할 수 있을 때 탐색 AI가 선택 목록에 나타납니다.
원격 참가자에게는 모델을 복사할 필요가 없습니다. 서버 PC가 AI를 실행합니다.

## 생각하는 시간이 있나요?

탐색 AI는 후보를 비교하므로 기본 AI보다 응답이 오래 걸릴 수 있습니다.
시간은 호스트 PC와 게임 상태에 따라 달라집니다. 화면의 **생각 중…** 표시를 확인하세요.

AI의 판단 방식이 궁금하다면 [AI는 어떻게 한 수를 고르는가]({{< relref "posts/how-search-ai-chooses.md" >}})를 읽어 보세요.
모델이 표시되지 않으면 [문제 해결]({{< relref "help/_index.md" >}})에서 준비 사항을 확인할 수 있습니다.
