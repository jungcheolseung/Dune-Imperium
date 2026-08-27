# Dune: Imperium AI

구현의 규칙 기준은 [Uprising 4인 규칙 명세](docs/rules/README.md), 구현 순서와
완료 조건은 [구현 계획](docs/implementation-plan.md)을 따른다. 새 개발 세션은
[개발 인수인계](docs/development-handoff.md)에서 현재 구현 범위, 검증 기준, 다음
작업을 먼저 확인한다.

## 현재 구현 상태

2026-08-28 기준으로 기본 보드 시스템, multi-round 상태 전이와 개인 덱 reshuffle,
기본 룰셋 Imperium 카드 50종 모두의 play data가 구현되어 있다.
CHOAM Module은 standard contract 20장의 identity와 setup, 공개 시장의
take/refill·고갈 동작까지 연결돼 있다. 현재 action codec은 v56이며 기본 룰셋은
3,377개, CHOAM 룰셋은 3,445개다. 전체 테스트 547개, Ruff, mypy가 통과한다.

코어 엔진은 여러 라운드를 진행하고 replay할 수 있지만, 공개 random runner와
`dune_imperium_uprising_v0` PettingZoo adapter는 여전히 한 라운드를 실행 단위로
삼는다. Intrigue 실제 play 효과, Leader 능력, Immediate 이외의 contract 완료
조건·보상은 아직 구현 전이므로 완전한 기본 게임이나 학습 환경이 끝난 상태는
아니다.

## 프로젝트 비전

Dune: Imperium을 Python으로 정확하고 재현 가능하게 구현하고, 이를 이용해
강화학습 및 self-play가 가능한 게임 플레이 AI를 만든다. 최종 목표는 사람이
충분히 강하고 재미있는 AI 상대와 완전한 게임을 플레이하며 높은 수준의
Dune: Imperium 경험을 할 수 있게 하는 것이다.

## 구현 방향

- 최초 구현 대상은 **Dune: Imperium - Uprising 4인 플레이, CHOAM Module
  OFF**다. 기본 게임 완주 검증 뒤 CHOAM Module을 설정 옵션으로 추가한다.
- 개발 및 실행 환경은 **Python 3.14**와 **uv**를 사용한다.
- 현재 `dune/`의 코드는 이전 구현 시도의 참고 자료다. 호환성을 유지할 필요는
  없으며, 더 적합한 구조를 위해 처음부터 다시 구현할 수 있다.
- 규칙 구현과 검증에는 Dire Wolf Digital의 공식 온라인 자료를 우선 사용한다.
  `rulebooks/`의 PDF는 사용자가 로컬에서 열람하기 위한 사본이므로 자동으로
  전체를 읽거나 분석하지 않는다. 애매한 규칙 해석과 선택한 판정은 문서화하고
  테스트로 고정한다.
- 인접한 `../TabletopGames` 저장소는 보드게임 AI를 위한 구조적 참고 자료다.
  특히 game state, forward model/rules, actions, parameters/components의 분리와
  RL 연동 방식을 조사해 유용한 개념을 선택적으로 적용한다. 그대로 포팅하거나
  런타임 의존성을 두는 것은 아직 결정하지 않았다.
- 게임 규칙 엔진은 UI와 학습 코드에서 분리한다.
- 학습 환경에 필요한 결정론적 실행과 seed 기반 난수, 합법 행동 열거 및 action
  mask, 플레이어별 관측과 비공개 정보, 상태 복제/직렬화, headless 병렬 실행을
  처음부터 고려한다.
- 우선순위는 규칙 정확성, 테스트 가능성, 학습 처리량, AI 성능, 사람이 즐길 수
  있는 플레이 경험의 순서로 둔다.

## 목표 상태

1. 선택한 Dune: Imperium 룰셋을 끝까지 플레이할 수 있는 게임 엔진을 완성한다.
2. 규칙 단위 테스트, 시나리오 테스트, seeded replay로 구현을 검증한다.
3. RL 환경과 baseline 플레이어를 만들고 self-play 학습 및 평가 파이프라인을
   구축한다.
4. 학습한 AI의 실력을 재현 가능한 상대전과 지표로 평가하며 지속적으로 높인다.
5. 사람이 학습한 AI와 편리하게 완전한 게임을 플레이할 수 있는 인터페이스를
   제공한다.

## 아직 결정하지 않은 사항

- 현재 81개 정수 관측과 v56 action catalog 이후의 전체 게임 관측 확장 및 최종
  학습용 인코딩, 학습 알고리즘과 모델 구조
- 사람이 플레이할 최종 UI 형태
- CHOAM 이후 다른 확장팩을 추가할 범위와 순서

규칙 코어는 특정 RL 라이브러리에 의존하지 않게 만들고, 첫 표준 다중 에이전트
adapter는 PettingZoo AEC로 한다. 나머지 결정은 규칙 엔진의 수직 조각과 처리량
기준선을 확인한 뒤 명시적인 설계 문서와 테스트 기준으로 확정한다.

## 공식 규칙 자료

- [Dune: Imperium 공식 리소스 페이지](https://www.direwolfdigital.com/dune-imperium/resources/)
- [Dune: Imperium - Uprising 메인 룰북](https://www.direwolfdigital.com/dune-imperium/resources/diu_rules)
- [Uprising Board Space Guide와 보충 규칙](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_UPRISING_Rules_Supplements_23-10-12.pdf)
- [공식 FAQ (2025-01-13)](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_FAQ_25-1-13.pdf)

규칙 조사가 필요할 때는 위 공식 자료에서 해당 규칙과 관련된 부분만 확인한다.
로컬 `rulebooks/` PDF는 공식 자료에 접근할 수 없거나 사용자가 명시적으로
요청한 경우에만 사용한다.

### 공식 룰 문서 작업 도구

공식 PDF를 다시 검증하거나 새 FAQ와 비교할 때는 저장소의 로컬 PDF 대신 다음
도구를 사용한다.

```bash
uv run scripts/prepare_official_rules.py
```

도구는 [고정된 공식 출처 manifest](scripts/official-rule-sources.json)의 PDF를
검증하고, PDF 페이지 marker가 붙은 text working copy를 기본적으로
`/tmp/dune-imperium-official-rules/`에 만든다. 생성된 PDF와 text는 저장소에
추가하지 않는다. FAQ만 다시 준비하려면 `--source faq`, 기존 working copy만
쓰려면 `--offline`을 사용한다. 공식 파일의 SHA-256이 바뀌면 자동으로 받아들이지
않으며, 공식 리소스 페이지에서 새 버전인지 먼저 확인해야 한다.

## 카드 및 이미지 자료

- [Dune Cards Hub - Uprising](https://dunecardshub.com/uprising): Uprising의
  리더, 각종 덱 카드, 계약 등 카드 이미지와 카드별 정보를 찾을 때 사용한다.
- [Dune Cards Hub](https://dunecardshub.com): 다른 확장팩 자료가 필요할 때
  해당 확장팩을 선택해 사용한다.
- 외부 구조화 데이터의 사용 범위와 검증 정책은
  [카드 데이터 전사 출처](docs/card-data-sources.md)에 기록한다.

Dune Cards Hub는 카드 및 시각 자료의 참고 출처로 사용한다. 규칙 설명과 카드
효과 해석이 충돌할 경우에는 Dire Wolf Digital의 공식 룰북과 공식 보충 자료를
우선한다. 이미지 파일을 프로젝트에 포함하거나 재배포하기 전에는 필요한 범위와
이용 조건을 별도로 확인한다.

## 개발 환경

```bash
uv sync
uv run python --version
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

`uv sync`는 `.python-version`에 지정된 Python 3.14로 `.venv`를 만들고
`uv.lock`에 고정된 의존성을 설치한다. 새 구현은 `src/dune_imperium/`에 두며,
기존 `dune/` 패키지는 이전 구현의 참고 자료일 뿐 새 코드에서 import하지 않는다.

### PettingZoo 한 라운드 환경

RL optional 의존성을 설치하면 고정 action catalog와 mask를 사용하는 AEC 환경을
실행할 수 있다.

```bash
uv sync --extra rl
```

```python
from dune_imperium.adapters.pettingzoo_env import env

environment = env()
environment.reset(seed=7)
observation, reward, terminated, truncated, info = environment.last()
```

현재 `dune_imperium_uprising_v0`는 한 라운드를 하나의 episode로 취급한다. 이는
multi-round 코어 엔진과 별도의 adapter 경계이며, 전체 게임 episode 전환은 기본
콘텐츠와 Endgame decision window가 완성된 뒤 진행한다.
