# Dune: Imperium AI

보드게임 Dune: Imperium과 Dune: Imperium - Uprising을 Python으로 규칙에 맞게, 재현 가능하게 구현하고,
그 엔진 위에서 사람이 AI 상대나 원격의 친구들과 브라우저로 한 판을 두며, self-play로 더 강한 AI를 학습하는
프로젝트다. 최종 목표는 사람이 충분히 강하고 재미있는 AI와 완전한 게임을 즐기는 것이다.

엔진은 두 기본 판 — 원판 Dune: Imperium(듄: 임페리움)과 Dune: Imperium - Uprising(듄 임페리움: 봉기) — 의
4인 게임을 아래 확장과 함께 처음부터 끝까지 플레이한다. 버전·테스트 수·승률 같은 현재 수치와 진행 중인
작업은 개발 인수인계에 있다. 프로젝트 소개·사용법·개발일지는
[웹사이트](https://jungcheolseung.github.io/Dune-Imperium/)에도 있다.

<!-- 이 문서는 입구다. codec·관측 버전, 테스트·E2E 수, 승률처럼 자주 바뀌는 숫자는 여기 쓰지 않고
docs/development-handoff.md에, 날짜별 작업 기록은 docs/worklog/에 둔다(사용자 결정 2026-10-12). -->

## 어디서 시작하나

| 하려는 것 | 볼 곳 |
|---|---|
| 내 컴퓨터에서 AI와 한 판 | 아래 "바로 한 판" |
| 친구들과 원격으로 한 판(방을 여는 사람) | [서버 호스트용 가이드](docs/remote-play-host-guide.md) |
| 받은 방 링크로 참여 | [플레이어용 접속 가이드](docs/remote-play-player-guide.md) — 저장소나 Python 설치가 필요 없다 |
| 규칙이 어떻게 정해졌는지 | [규칙 명세](docs/rules/README.md), [이 게임에서 정한 판정](docs/rules/house-rulings-ko.md) |
| 개발을 이어서 | 개발 인수인계와 이번 달 작업 기록, 그리고 `AGENTS.md` |

## 바로 한 판

- **창으로:** `scripts/launcher/Install Launcher.command`(macOS)나 `Install Launcher.cmd`(Windows)를 한 번
  더블클릭하면 서버 런처가 설치된다. 저장소가 WSL 안에 있으면 WSL 터미널에서 `scripts/launcher/install-wsl.sh`를
  실행한다(창은 WSLg로 Windows 바탕 화면에 뜬다). 런처 창에서 이 컴퓨터에서만 둘지(로컬) 친구들과 둘지(원격)
  골라 서버를 띄우고 끈다([호스트 가이드의 "서버 런처로 실행"](docs/remote-play-host-guide.md#서버-런처로-실행-터미널-없이)).
- **터미널로:**

  ```bash
  uv sync --extra rl --extra ui --extra train
  uv run dune-imperium-server
  ```

  브라우저에서 http://127.0.0.1:8000 을 열고 기본 판(원판 또는 Uprising), 확장, 좌석을 골라 게임을 만든다.
  로컬 서버의 기본 상대는 앱 AI(어려움)다.
- **친구와 원격으로:** 호스트가 `--remote`로 서버를 띄우고 관리자 링크로 게임을 만든 뒤 방 링크를 보낸다.
  호스트는 [서버 호스트용 가이드](docs/remote-play-host-guide.md), 참가자는
  [플레이어용 접속 가이드](docs/remote-play-player-guide.md)를 본다(입구는 [멀티플레이 안내](docs/remote-play-guide.md)).

카드·보드 그림은 저작권 때문에 저장소에 없고, 없으면 화면이 텍스트로 대신한다. 그림을 연결하는
방법은 [로컬 UI 이미지](docs/local-images.md)에 있다.

## 구현된 것

### 규칙

게임을 만들 때 기본 판 하나를 고르고, 그 위에 확장을 원하는 만큼 켠다. 확장끼리도, 어느 기본 판과도
조합된다. 확장 안의 부속만 자기 확장을 요구한다(Tech Module은 Bloodlines, Go to 11은 Immortality).

| 고르는 것 | 규칙 명세 |
|---|---|
| 기본 판 **Dune: Imperium - Uprising** 4인 | [rules/README.md](docs/rules/README.md)의 Uprising 문서들 |
| 기본 판 **Dune: Imperium**(원판) 4인 | [imperium-base.md](docs/rules/imperium-base.md) |
| **Rise of Ix**(익스의 부상). Bloodlines의 Tech Module과 함께 켜면 Ix 전부, Ix 지도자 + Tech 타일, Tech 타일만 가운데 고른다 | [rise-of-ix.md](docs/rules/rise-of-ix.md) |
| **Immortality**(불멸)와 그 변형 Go to 11 | [immortality.md](docs/rules/immortality.md) |
| **Bloodlines**(혈통)와 Tech Module | [bloodlines.md](docs/rules/bloodlines.md) |
| **CHOAM Module**(초암 모듈) — Uprising 판에서만 | [choam-module.md](docs/rules/choam-module.md) |
| **Arrakeen Scouts** — Dire Wolf Game Room 앱의 모듈, 두 기본 판 모두 | [arrakeen-scouts.md](docs/rules/arrakeen-scouts.md), 설계 |
| **Epic Game Mode**(에픽 게임 모드) — 원판에서는 Rise of Ix 전부와 함께 | [epic-game-mode.md](docs/rules/epic-game-mode.md) |
| 프로모 카드, Uprising 판에 원판 카드 섞기, 공개 Leader draft(공식 규칙이 아닌 project convention, OQ-007) | [rules/README.md](docs/rules/README.md) |

범위 밖: 1·2인 Rivals와 원판의 House Hagal(자동 상대), 3인, 6인 팀전. 이 프로젝트의 대상은 4인 게임이다.

공식 문서가 답하지 않는 판정은 지어내지 않고 [판정 대장](docs/rules/open-questions.md)에 OQ 번호로 남긴 뒤
테스트로 고정한다. 출처끼리 다르거나 앱과 다르게 정한 곳은 플레이하는 사람을 위한
[판정 공지](docs/rules/house-rulings-ko.md)에 모았고, 게임 화면의 도움말도 같은 목록을 보인다.

### 플레이 화면

보드 그림 위에 모든 것을 얹은 한 화면 테이블이다. 원판과 Uprising 보드를 각자의 판에서 쓴다. Agent 턴은
카드 → 칸 → 남은 선택 순서로 고르고, "턴 종료 ▶"를 눌러야 끝난다. 되돌리기, 저장·불러오기·자동 저장, 끝난
판의 리플레이 검토, AI끼리 두는 판의 관전, 한국어/영어 전환(공식 한국어 룰북 용어,
[용어집](docs/rules/glossary-ko.md)), 도움말, 플레이 시계, 연출과 효과음이 있다
(UI 개선 계획).

### AI 상대

좌석마다 고른다. 기본 판마다 앉을 수 있는 좌석이 다르다(`src/dune_imperium/server/seat_kinds.py`).

| AI | 설명 | 기본 판 |
|---|---|---|
| 앱 AI 어려움·보통·쉬움 | 공식 Steam 앱의 컴퓨터 상대를 옮긴 것(설계) | 둘 다, 모든 확장 |
| 탐색 AI | 학습한 망 주위에 결정론화 탐색을 두른 가장 강한 상대(어떻게 두나). 망은 엔티티 망을 self-play로 다시 학습한 것이다. `train` extra와 망 파일 `checkpoints/play/search.pt`가 있어야 좌석 목록에 나온다 | Uprising만(망이 원판을 배운 적이 없다) |
| 휴리스틱 | 규칙 기반 | 둘 다 |
| 랜덤 | 합법 행동 중 무작위 | 둘 다 |
| 롤아웃 탐색, 학습 체크포인트 경로 | 실험·측정용 | Uprising만 |

AI끼리의 실력 비교는 docs/evaluation/에 있다.

### 원격 멀티플레이와 서버 런처

호스트가 보낸 방 링크 하나로 친구들이 각자 브라우저에서 빈 좌석에 앉는다. 화면은 실시간으로 갱신되고,
새로고침 뒤 같은 좌석으로 돌아오며, 서버가 턴마다 자동 저장한다(설계). 원격
서버는 연결·요청 크기에 한도를 두고, 관리자 키(영문자·숫자·`-`·`_` 16자 이상)로 서명한 세션 쿠키로 호스트를
알아본다. 업데이트 뒤에는 호스트가 관리자 링크를 한 번 다시 연다([호스트 가이드](docs/remote-play-host-guide.md)).

서버 런처(`dune-imperium-launcher`)는 macOS·Windows·WSL에서 창 하나로 로컬·원격 서버를 띄우고 끄며, 주소
후보와 시작 전 검사, 방 링크 복사, 잠자기 방지를 맡는다(계획,
Windows 검증 범위).

### 학습과 평가

- PettingZoo AEC 환경 `dune_imperium_uprising_v1`: Uprising 판 전체가 한 episode, 승자독식 종료 보상
  (학습 환경 설계). 원판은 아직 학습 환경에 없다.
- `dune-imperium-selfplay`(self-play 수집), `dune-imperium-train`(PyTorch 학습),
  `dune-imperium-tournament`(좌석·Leader를 돌려 가며 하는 교차 대전 보고), `dune-imperium-sweep`(완주 소크).
- 엔티티 망과 그 self-play: 엔티티 망 계획,
  자기 학습 계획. 탐색 AI의 지금 망이 여기서 나왔다.
- `dune-imperium-records`: 사람이 둔 판을 지금 엔진의 기보로 옮긴다(기보 이전).
- 학습 알고리즘과 모델 구조는 아직 실험 중이다. 실패한 실험까지 docs/evaluation/과
  작업 기록에 남긴다.

## 문서 지도

| 문서 | 내용 |
|---|---|
| development-handoff.md | 현재 기준선(버전·테스트 수), 진행 중·다음 작업, 알아 둘 것. 새 개발 세션은 여기서 시작한다 |
| worklog/ | 날짜별 작업 기록(월별 파일, 최신이 위) |
| implementation-plan.md | 마일스톤 M0~M15와 완료 조건 |
| base-game-and-ix-plan.md | 원판과 Rise of Ix, 확장 조합(P0–P8-1)의 계획과 단계별 결과 |
| [rules/README.md](docs/rules/README.md) | 규칙 명세: 공식 룰북·FAQ를 구현 단위로 정리한 요약과 출처 |
| [rules/open-questions.md](docs/rules/open-questions.md) | 공식 문서로 정할 수 없는 판정의 대장(OQ) |
| lessons.md | 같은 실수를 막기 위한 교훈 기록 |
| implementation-audits/ | 카드·Leader·계약 등 구현 감사 |
| reviews/ | 엔진·숨은 정보·서버 보안 검토와 그 후속 조치 |
| card-data-sources.md | 카드 데이터 전사 출처 |
| evaluation/ | 기준선·대회·학습·속도 측정 기록 |
| [website/README.md](website/README.md) | 프로젝트 웹사이트의 실행·검증·Pages 배포와 개발일지 작성 방법 |
| `docs/*-design.md`, `docs/*-plan.md` | 기능별 설계와 계획(원격, Arrakeen Scouts, 앱 AI, 런처, UI 등) |

## 개발 환경

```bash
uv sync --extra rl --extra ui --extra train
uv run pytest -n 8          # 작업 프로세스 8개(pytest-xdist); 코어가 적으면 줄인다
uv run ruff check src tests scripts
uv run mypy src tests
```

- `uv sync`는 `.python-version`의 Python 3.14로 `.venv`를 만들고 `uv.lock`에 고정된 의존성을
  설치한다. 환경을 나열한 extras와 정확히 맞추므로 extra를 빼고 실행하면 그 extra의 패키지가
  지워진다(예: `--extra ui`만 주면 rl의 gymnasium·pettingzoo가 지워진다). 표준 명령은 위의 세
  extra다(`train`은 PyTorch; 없으면 `tests/unit/training/test_torch_policy.py`가 skip된다).
- 브라우저 E2E는 [`scripts/e2e/`](scripts/e2e/README.md)에 있다(Playwright는 프로젝트 의존성이 아니다).
- 서버 런처의 설정은 git 무시 `local/launcher.json`, 로그는 `tmp/launcher/`.
  창 없이 진단만 보려면 `uv run python -m dune_imperium.launcher.cli --check`.
- 프로젝트 파일은 저장소 폴더 밖에 두지 않는다. 저장은 `saves/`, 학습 체크포인트와 로그는
  `checkpoints/`(탐색 AI의 망은 `checkpoints/play/search.pt`, 보통 같은 폴더의 가중치 파일을 가리키는
  링크), 임시 파일은 `tmp/`이고 모두 git이 무시한다. 다른 머신에는 체크포인트 파일을 복사해 쓴다.
- 새 코드는 `src/dune_imperium/`에 둔다. `dune/`는 이전 구현의 참고 자료일 뿐 import하지 않는다.
- 여러 기기·도구(Claude Code, Codex)가 함께 작업한다. 작업 규칙은 `AGENTS.md`(도구별 진입점은 `CLAUDE.md`)에 있다.

PettingZoo 환경(`rl` extra)은 고정 action catalog와 mask를 쓴다. 관측 벡터와 보상 근거는
학습 환경 설계를 따른다.

```python
from dune_imperium.adapters.pettingzoo_env import env

environment = env()          # env(choam_module=True)로 CHOAM 룰셋 선택
environment.reset(seed=7)
observation, reward, terminated, truncated, info = environment.last()
```

## 구현 원칙

- 규칙의 기준은 두 기본 판(Dune: Imperium, Dune: Imperium - Uprising)의 **4인 플레이**이고, 확장은 게임을
  만들 때 고르는 옵션으로 얹는다. 기본 판을 하나 더해도 다른 판의 식별자·저장본·기보는 그대로 둔다.
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
- [원판 Dune: Imperium 룰북](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_Rules_2020_10_26.pdf)과
  [Player Aid](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_Player_Aid_Icons_and_Board_Spaces.pdf)
- 확장 룰북: [Rise of Ix](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_RISE_OF_IX_Rulebook_22-2-11.pdf),
  [Immortality](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_IMMORTALITY_Rulebook.pdf),
  [Bloodlines](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_BLOODLINES_Rulebook.pdf)
- [공식 FAQ (2025-01-13)](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_FAQ_25-1-13.pdf)

버전과 checksum, 문서마다 어느 쪽을 규범으로 읽는지는 [출처와 작성 원칙](docs/rules/sources.md)에 있다.
Arrakeen Scouts는 룰북이 없어 Dire Wolf Game Room 앱이 출처다.
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
- 원판과 Rise of Ix 카드는 카드 그림 대신 Steam 앱의 자료(속성 표, 카드별 화면 구성, 영어 문구)에서
  전사했다. 앱 자료는 비공개 에셋 저장소에만 두고, 이 저장소에는 이름·숫자와 우리 표기만 들어온다.
- 외부 구조화 데이터의 사용 범위와 검증 정책은 카드 데이터 전사 출처에 기록한다.
- 한국어 카드 이름과 문구는 공식 한국어판(룰북과 인쇄된 카드)에서만 가져온다. 한국어 출처가 없는 카드는
  영어 앞면을 보인다.

Dune Cards Hub와 Steam 앱은 카드와 시각 자료의 참고 출처다. 규칙 설명과 카드 효과 해석이 충돌하면 Dire Wolf
Digital의 공식 룰북과 보충 자료, FAQ를 우선한다. 이미지 파일을 프로젝트에 포함하거나 재배포하기 전에는
필요한 범위와 이용 조건을 따로 확인한다.
