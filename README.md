# Dune: Imperium AI

Dune: Imperium - Uprising을 Python으로 규칙에 맞게, 재현 가능하게 구현하고, 그 엔진 위에서
사람이 AI 상대나 원격의 친구들과 브라우저로 한 판을 두며, self-play로 더 강한 AI를 학습하는
프로젝트다. 최종 목표는 사람이 충분히 강하고 재미있는 AI와 완전한 게임을 즐기는 것이다.

엔진은 Uprising 4인 기본 게임과 아래 옵션들을 처음부터 끝까지 플레이한다. 지금 작업은 AI의
실력과 플레이 화면을 다듬는 쪽에 있다. 버전·테스트 수·승률 같은 현재 수치와 다음 작업은
[개발 인수인계](docs/development-handoff.md)에 있다.

<!-- 이 문서는 입구다. codec·관측 버전, 테스트·E2E 수, 승률처럼 자주 바뀌는 숫자와 날짜별
작업 기록은 여기 쓰지 않고 docs/development-handoff.md에 둔다(사용자 결정 2026-10-12). -->

## 바로 한 판

- **창으로:** `scripts/launcher/Install Launcher.command`(macOS)나 `Install Launcher.cmd`(Windows)를
  한 번 더블클릭하면 서버 런처가 설치된다. 런처 창에서 이 컴퓨터에서만 둘지(로컬) 친구들과 둘지(원격)
  골라 서버를 띄우고 끈다([호스트 가이드의 "서버 런처로 실행"](docs/remote-play-host-guide.md)).
- **터미널로:**

  ```bash
  uv sync --extra rl --extra ui --extra train
  uv run dune-imperium-server
  ```

  브라우저에서 http://127.0.0.1:8000 을 열고 좌석과 옵션을 골라 게임을 만든다. 로컬 서버의 기본
  상대는 앱 AI(어려움)다.
- **친구와 원격으로:** 호스트는 [서버 호스트용 가이드](docs/remote-play-host-guide.md), 참가자는
  [플레이어용 접속 가이드](docs/remote-play-player-guide.md)를 본다(입구는
  [멀티플레이 안내](docs/remote-play-guide.md)). 참가자는 저장소나 Python을 설치할 필요가 없다.

카드·보드 그림은 저작권 때문에 저장소에 없고, 없으면 화면이 텍스트로 대신한다. 그림을 연결하는
방법은 [로컬 UI 이미지](docs/local-images.md)에 있다.

## 구현된 것

**규칙.** Uprising 4인 기본 게임 전체([규칙 명세](docs/rules/README.md))와, 게임을 만들 때 켜는 옵션:

- CHOAM Module([choam-module.md](docs/rules/choam-module.md))
- Bloodlines 확장과 Tech Module([bloodlines.md](docs/rules/bloodlines.md))
- Immortality 확장과 그 변형 Go to 11 "11점을 향해"([immortality.md](docs/rules/immortality.md))
- Rise of Ix의 Epic Game Mode "에픽 게임 모드"([epic-game-mode.md](docs/rules/epic-game-mode.md))
- Arrakeen Scouts — Dire Wolf Game Room 앱의 3-4인 모듈([arrakeen-scouts.md](docs/rules/arrakeen-scouts.md),
  [설계](docs/arrakeen-scouts-design.md))
- Uprising·Bloodlines 프로모 카드, 공개 Leader draft(공식 규칙이 아닌 project convention, OQ-007)

공식 문서가 답하지 않는 판정은 지어내지 않고 [판정 대장](docs/rules/open-questions.md)에 OQ 번호로
남긴 뒤 테스트로 고정한다.

**플레이 화면.** 보드 스캔 위에 모든 것을 얹은 한 화면 테이블. Agent 턴은 카드 → 칸 → 남은 선택
순서로 고르고, "턴 종료 ▶"를 눌러야 끝난다. 되돌리기, 저장·불러오기·자동 저장, 끝난 판의 리플레이
검토, AI끼리 두는 판의 관전, 한국어/영어 전환(공식 한국어 룰북 용어, [용어집](docs/rules/glossary-ko.md)),
도움말, [플레이 시계](docs/play-clock.md), 연출과 효과음이 있다
([UI 개선 계획](docs/ui-improvement-plan.md)).

**AI 상대.** 좌석마다 고른다.

- 탐색 AI: 학습한 정책망 주위에 결정론화 탐색을 두른 가장 강한 상대([어떻게 두나](docs/search-ai.md)).
  `train` extra와 망 파일 `checkpoints/play/search.pt`가 있어야 좌석 목록에 나온다.
- 앱 AI 어려움·보통·쉬움: 공식 Steam 앱의 컴퓨터 상대를 옮긴 것([설계](docs/app-ai-plan.md)).
- 휴리스틱(규칙 기반), 롤아웃 탐색, 랜덤, 학습 체크포인트 경로.

AI끼리의 실력 비교는 [docs/evaluation/](docs/evaluation/)에 있다.

**원격 멀티플레이.** 호스트가 보낸 방 링크 하나로 친구들이 각자 브라우저에서 빈 좌석에 앉는다.
화면은 실시간으로 갱신되고, 새로고침 뒤 같은 좌석으로 돌아오며, 서버가 턴마다 자동 저장한다
([설계](docs/multiplayer-design.md)).

**학습과 평가.**

- PettingZoo AEC 환경 `dune_imperium_uprising_v1`: 전체 게임이 한 episode, 승자독식 종료 보상
  ([학습 환경 설계](docs/rl-environment.md)).
- `dune-imperium-selfplay`(self-play 수집), `dune-imperium-train`(PyTorch 학습),
  `dune-imperium-tournament`(좌석·Leader를 돌려 가며 하는 교차 대전 보고), `dune-imperium-sweep`(완주 소크).
- `dune-imperium-records`: 사람이 둔 판을 지금 엔진의 기보로 옮긴다([기보 이전](docs/human-records.md)).
- 학습 알고리즘과 모델 구조는 아직 실험 중이다. 기록은 [docs/evaluation/](docs/evaluation/)의 `m10-*.md`.

## 문서 지도

| 문서 | 내용 |
|---|---|
| [development-handoff.md](docs/development-handoff.md) | 현재 기준선(버전·테스트 수), 날짜별 작업 기록, 다음 작업. 새 개발 세션은 여기서 시작한다 |
| [implementation-plan.md](docs/implementation-plan.md) | 마일스톤 M0~M15와 완료 조건 |
| [rules/README.md](docs/rules/README.md) | 규칙 명세: 공식 룰북·FAQ를 구현 단위로 정리한 요약과 출처 |
| [rules/open-questions.md](docs/rules/open-questions.md) | 공식 문서로 정할 수 없는 판정의 대장(OQ) |
| [lessons.md](docs/lessons.md) | 같은 실수를 막기 위한 교훈 기록 |
| [implementation-audits/](docs/implementation-audits/) | 카드·Leader·계약 등 구현 감사 |
| [card-data-sources.md](docs/card-data-sources.md) | 카드 데이터 전사 출처 |
| [evaluation/](docs/evaluation/) | 기준선·대회·학습 측정 기록 |
| `docs/*-design.md`, `docs/*-plan.md` | 기능별 설계와 계획(원격, Arrakeen Scouts, 앱 AI, 런처, UI 등) |

## 개발 환경

```bash
uv sync --extra rl --extra ui --extra train
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

- `uv sync`는 `.python-version`의 Python 3.14로 `.venv`를 만들고 `uv.lock`에 고정된 의존성을
  설치한다. 환경을 나열한 extras와 정확히 맞추므로 extra를 빼고 실행하면 그 extra의 패키지가
  지워진다(예: `--extra ui`만 주면 rl의 gymnasium·pettingzoo가 지워진다). 표준 명령은 위의 세
  extra다(`train`은 PyTorch; 없으면 `tests/unit/training/test_torch_policy.py`가 skip된다).
- 브라우저 E2E는 [`scripts/e2e/`](scripts/e2e/README.md)에 있다(Playwright는 프로젝트 의존성이 아니다).
- 서버 런처(`dune-imperium-launcher`)의 설정은 git 무시 `local/launcher.json`, 로그는 `tmp/launcher/`.
  창 없이 진단만 보려면 `uv run python -m dune_imperium.launcher.cli --check`.
- 프로젝트 파일은 저장소 폴더 밖에 두지 않는다. 저장은 `saves/`, 학습 체크포인트와 로그는
  `checkpoints/`(탐색 AI의 망은 `checkpoints/play/search.pt`, 보통 같은 폴더의 가중치 파일을 가리키는
  링크), 임시 파일은 `tmp/`이고 모두 git이 무시한다. 다른 머신에는 체크포인트 파일을 복사해 쓴다.
- 새 코드는 `src/dune_imperium/`에 둔다. `dune/`는 이전 구현의 참고 자료일 뿐 import하지 않는다.

PettingZoo 환경(`rl` extra)은 고정 action catalog와 mask를 쓴다. 관측 벡터와 보상 근거는
[학습 환경 설계](docs/rl-environment.md)를 따른다.

```python
from dune_imperium.adapters.pettingzoo_env import env

environment = env()          # env(choam_module=True)로 CHOAM 룰셋 선택
environment.reset(seed=7)
observation, reward, terminated, truncated, info = environment.last()
```

## 구현 원칙

- 규칙의 기준은 **Dune: Imperium - Uprising 4인 플레이**이고, 확장은 옵션으로 얹는다.
- 우선순위는 규칙 정확성, 테스트 가능성, 학습 처리량, AI 성능, 사람이 즐길 수 있는 플레이 경험의 순서다.
- 게임 규칙 엔진은 UI와 학습 코드에서 분리하고, 특정 RL 라이브러리에 의존하지 않는다(표준
  adapter는 PettingZoo AEC).
- 결정론적 실행과 seed 기반 난수, 합법 행동 열거와 action mask, 좌석별 관측과 비공개 정보,
  상태 복제·직렬화, headless 병렬 실행을 처음부터 고려한다.
- 애매한 규칙 해석과 선택한 판정은 문서화하고 테스트로 고정한다.
- 인접한 `../TabletopGames` 저장소는 game state, forward model, actions, parameters의 분리와 RL
  연동 방식을 보는 구조 참고 자료다. 포팅하거나 의존하지 않는다.

## 공식 규칙 자료

- [Dune: Imperium 공식 리소스 페이지](https://www.direwolfdigital.com/dune-imperium/resources/)
- [Dune: Imperium - Uprising 메인 룰북](https://www.direwolfdigital.com/dune-imperium/resources/diu_rules)
- [Uprising Board Space Guide와 보충 규칙](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_UPRISING_Rules_Supplements_23-10-12.pdf)
- [공식 FAQ (2025-01-13)](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_FAQ_25-1-13.pdf)

규칙 조사가 필요할 때는 위 공식 자료에서 관련된 부분만 확인한다. 로컬 `assets/rulebooks/`의 PDF는
사용자가 열람하는 사본이므로, 공식 자료에 접근할 수 없거나 사용자가 명시적으로 요청한 경우에만 쓴다.

공식 PDF를 다시 검증하거나 새 FAQ와 비교할 때는 다음 도구를 쓴다.

```bash
uv run scripts/prepare_official_rules.py
```

도구는 [고정된 공식 출처 manifest](scripts/official-rule-sources.json)의 PDF를 검증하고, PDF 페이지
marker가 붙은 text working copy를 git 무시 폴더 `tmp/official-rules/`에 만든다(커밋하지 않는다).
FAQ만 다시 준비하려면 `--source faq`, 기존 working copy만 쓰려면 `--offline`. 공식 파일의 SHA-256이
바뀌면 자동으로 받아들이지 않으며, 공식 리소스 페이지에서 새 버전인지 먼저 확인해야 한다.

## 카드 및 이미지 자료

- [Dune Cards Hub - Uprising](https://dunecardshub.com/uprising): Uprising의 리더, 각종 덱 카드, 계약 등
  카드 이미지와 카드별 정보를 찾을 때 쓴다. 다른 확장팩은 [Dune Cards Hub](https://dunecardshub.com)에서
  그 확장팩을 고른다.
- 외부 구조화 데이터의 사용 범위와 검증 정책은 [카드 데이터 전사 출처](docs/card-data-sources.md)에 기록한다.

Dune Cards Hub는 카드와 시각 자료의 참고 출처다. 규칙 설명과 카드 효과 해석이 충돌하면 Dire Wolf
Digital의 공식 룰북과 보충 자료를 우선한다. 이미지 파일을 프로젝트에 포함하거나 재배포하기 전에는
필요한 범위와 이용 조건을 따로 확인한다.
