# Dune: Imperium AI

구현의 규칙 기준은 [Uprising 4인 규칙 명세](docs/rules/README.md), 구현 순서와 완료 조건은 [구현 계획](docs/implementation-plan.md)을 따른다. 새 개발 세션은 [개발 인수인계](docs/development-handoff.md)에서 현재 구현 범위, 검증 기준, 다음 작업을 먼저 확인한다.

## 현재 구현 상태

2026-09-06 기준으로 기본 보드 시스템, multi-round 상태 전이와 개인 덱 reshuffle, 기본 룰셋 Imperium 카드 50종과 CHOAM 전용 4종, 총 54종의 play data가 구현되어 있다. CHOAM Module은 standard contract 20장의 identity·setup·공개 시장·완료 조건·인쇄 보상과 전용 Imperium 카드 효과까지 연결돼 있다. 보드 공간과 카드 Agent box의 인쇄 아이콘은 각각 별개 행동으로 해결하고, Reveal의 선택형 효과도 미루기/재개로 원하는 순서에 해결하며(OQ-027), 카드의 인쇄 조건은 효과를 해결하는 시점에 판정해 같은 turn의 뒤 선택으로 성립한 조건도 인정한다(OQ-028). Combat space에 배치한 병력은 그 Agent turn 안에서 되돌리거나 나눠 배치할 수 있고 turn은 명시적으로 끝낸다(OQ-029). supply 부족으로 다 못 한 recruit는 해결 시점에 소멸하고 소급하지 않으며 부족분은 공개 이벤트로 로그에 남긴다(OQ-030). Reveal turn의 troop recruit·Intrigue draw·자원·Influence 획득은 소유자가 시점을 고르는 행동이다(OQ-045; Persuasion·검만 시작 시 합산). 현재 action codec은 v95이며 기본 룰셋은 4,366개, CHOAM 룰셋은 4,652개다(`promo_cards` 옵션 시 4,466/4,752개, `bloodlines` 옵션 시 Commander·retreat·wild 템플릿, `tech_module` 옵션 시 Tech tile 획득·Flip·할인 템플릿 추가). 전체 테스트 1,360개, Ruff, mypy가 통과한다. 2026-09-08부터 Immortality 확장을 `immortality` 옵션으로 구현 중이다(슬라이스 1: 출처·[규칙 명세](docs/rules/immortality.md)·Bene Tleilax board 전사·카드 카탈로그, 슬라이스 2: research·Tleilaxu track·specimen·개정 Research Station·Experimentation·Family Atomics, 슬라이스 3: Tleilaxu Row 획득·Reclaimed Forces, 슬라이스 4: Graft와 Graft 카드 8장 완료; 나머지 카드 play data는 진행 중).

코어 엔진은 Endgame Intrigue window(OQ-001 convention)까지 갖춰 random 4인 게임을 FINISHED까지 완주하고 replay할 수 있다. Intrigue 44장은 39개 identity 전부가 effect DSL로 play되어 완결됐고, 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring도 모두 play된다. `run_random_game`/`run_policy_game` 러너와 `dune_imperium_uprising_v1` PettingZoo adapter는 전체 게임을 하나의 episode로 실행하며, 관측은 버전이 붙은 3,166-int 전체 게임 인코딩(v10; Reveal 전에도 배치 유닛 기준 전투력을 담고 Bloodlines Commander·Skill·Tech tile을 포함한다), 보상은 승자독식 zero-sum 종료 보상이다 ([학습 환경 설계](docs/rl-environment.md)). AI 상대로는 seeded random 외에 M11의 규칙 기반 `HeuristicAgent`가 있으며, 검증 sweep은 `--policy {random,heuristic}`으로 두 baseline을 모두 완주 검사할 수 있다. M9의 `dune-imperium-tournament`는 이름 붙인 baseline들을 좌석 회전·Leader 회전·seed 범위로 교차 대전시켜 승률·평균 순위·VP margin·좌석/Leader/선공별 성적·불법 행동·결정 시간을 Markdown/JSON으로 보고한다(첫 기준선: [docs/evaluation/baseline-2026-09-06.md](docs/evaluation/baseline-2026-09-06.md), heuristic이 random 3명 상대 95% 승률). 첫 search baseline `RolloutAgent`는 자기 좌석이 아는 정보만으로 숨겨진 존을 다시 나눈 세계(`agents/determinize.py`)에서 후보 행동마다 heuristic rollout을 돌려 고르며, heuristic 3명 상대 48% 승률(평균 순위 1.90)이다. M10 진입점인 `dune-imperium-selfplay`(`training/` 패키지)는 여러 게임을 lockstep으로 돌리며 좌석별 정책의 추론을 batch로 묶고, zero-sum 종료 보상과 관측·mask·행동 궤적을 NumPy 배열로 내놓는다(단일 프로세스 약 4,900 decisions/s). M10 첫 슬라이스 `dune-imperium-train`(`train` extra, PyTorch)은 masked policy/value MLP를 self-play 종료 보상으로 학습(REINFORCE + value baseline)하고, 관측·codec 버전을 기록한 체크포인트를 저장하며, 체크포인트는 `checkpoint:<경로>` 이름으로 대회 도구에 바로 들어간다. 이 Mac CPU에서 6분(self-play 960판) 학습한 첫 체크포인트가 random 3명 상대 100%, heuristic 3명 상대 56% 승률로 rollout(48%)을 넘었고, 8 worker 병렬 수집으로 14분(6,400판) 학습한 두 번째 체크포인트는 heuristic 상대 89%, 첫 체크포인트 상대 61%, rollout 상대 67%이며, 거기서 100 iteration을 이은 세 번째 체크포인트는 두 번째 상대 35%(동률 25%), heuristic 상대 91%다. Leader 선택은 OQ-007의 6종 공개 draft convention을 `RulesetConfig(leader_draft=True)` 옵션(sweep `--leader-draft`)으로 켤 수 있다(공식 규칙 아님; 기본은 고정 배정). 정식 덱 밖의 Uprising 프로모 Imperium 3장(Arrakis Revolt, The Beast's Spoils, Pivotal Gambit)은 `RulesetConfig(promo_cards=True)` 옵션(sweep `--promo-cards`, UI 체크박스)으로 덱에 넣으며, 카드면만이 출처라 공식 문서가 침묵하는 판정은 OQ-024~026에 project convention으로 기록했다. Bloodlines 프로모 Ruthless Leadership은 같은 옵션에 `bloodlines=True`를 함께 켤 때 덱에 들어간다(2026-09-08). Bloodlines 확장은 `RulesetConfig(bloodlines=True)`(sweep `--bloodlines`, UI 체크박스)로 켜며 2026-09-07 현재 Sardaukar Commander와 Skill(획득·지불 recruit·배치·strength·Reveal 보너스·정리·기존 troop 효과 포함), Conflict 카드 2장, wild끼리의 Endgame 매칭, Tech Module 전용을 뺀 Imperium 카드 25종(Command (6+)·Combat 아이콘·Spy with Deep Cover 포함)과 Intrigue 16장, Leader 8종(Chani·Fenring·Duncan Idaho·Esmar Tuek과 Tuek's Sietch·Mohiam·Liet Kynes·Piter De Vries와 Twisted Intrigue 12장·Steersman Y'rkoon과 Navigation 10장), 그리고 `tech_module=True`(sweep `--tech-module`)로 켜는 Tech Module(Ixian Embassy와 Tech tile 18장의 획득·할인·Flip·능력, Tech 전용 Imperium 2장·Intrigue 2장, Kota Odax of Ix)까지 구현돼 있어 Bloodlines 구성물 전부가 play된다([docs/rules/bloodlines.md](docs/rules/bloodlines.md); 공식 문서가 침묵하는 판정은 OQ-031~047; Endgame tiebreaker의 garrison troop 수에는 Commander를 포함한다). 2026-09-07 밤의 슬라이스 7로 웹 UI가 Commander·Skill·Ixian Embassy·보유 Tech tile을 표시하고, heuristic이 tile별 가치로 Tech를 사며, `--bloodlines --tech-module` 교차 소크 7,000판(random 4,000·heuristic 2,000·draft 1,000, `--soundness-interval 25`)이 실패 0으로 통과하고 관측 v9·codec v94 기준 학습 루프 smoke도 끝나 M12는 완료다(소크가 적발한 엔진 결함 3계열은 OQ-022·038 보강과 OQ-046으로 수정). M11 사람용 플레이(완료)는 FastAPI 기반 로컬 서버(`uv sync --extra rl --extra ui` 후 `uv run dune-imperium-server`, 기본 http://127.0.0.1:8000)로 한다: 브라우저에서 좌석 배정(사람, 또는 AI 종류: 휴리스틱·롤아웃 탐색·랜덤·학습 체크포인트 경로)·CHOAM·leader draft 설정부터 한 화면 게임 테이블(로컬 보드 스캔 위에 합법 공간 발광·Agent 토큰·Control·Spy를 겹쳐 그리고, 카드는 인쇄 이미지, 효과는 공식 룰북에서 추출한 아이콘으로 표시; 스캔·이미지·아이콘이 없으면 텍스트로 대체)·행동 선택·최종 순위까지 한 게임을 완주할 수 있고, 같은 API를 JSON으로도 쓸 수 있다. 진행 중이거나 끝난 게임은 `GameReplay` 직렬화 기반 로컬 저장 파일(`--saves-dir`, 기본 `~/.dune-imperium/saves`)로 저장·불러오기가 되며, 불러온 게임은 저장하지 않은 세션과 동일하게 이어진다. 끝난 게임은 모든 좌석 시점을 step 단위로 되돌려 보는 replay 검토 화면으로 복기할 수 있고, 종료 후에는 모든 비공개 존이 공개된다(OQ-010). 진행 중에는 실시간 행동 로그(이벤트를 좌석별 가시성으로 걸러 표시)와 행동 되돌리기(자기 연속 행동만, 무작위 결과·다른 좌석 행동·숨겨진 정보의 공개 이후로는 불가; 되돌린 행동은 로그에 남음)를 쓸 수 있다. 각 행동에는 되돌리기 가능 여부가 표시되고, 되돌릴 수 있는 행동으로 턴이 끝나면 플레이어가 턴 종료를 확정하기 전까지 다음 좌석으로 넘어가지 않는다. 보드 스캔 위에는 Influence 큐브·Alliance·VP·전투력·High Council 마커, 모서리 원의 garrison과 사분면의 Conflict 배치 병력, 인쇄된 슬롯의 Conflict 카드·Conflict 덱·face-up Contract도 그려지고, 카드와 공간은 마우스를 올리면 상세가 뜬다. 공용 카드 영역은 보드 옆 세로 열에, 행동 로그는 행동 목록 옆에 좌석별 턴 카드(게임 진행 이벤트는 별도 카드)로 놓이며 카드 위에 마우스를 올리면 관련 공간이 보드에서 켜진다. 새로 놓인 Agent 토큰은 좌석 패널에서 보드 공간으로 날아와 자리잡고, 1700px 이하 화면에서는 오른쪽 패널이 1열로 쌓인다.

## 프로젝트 비전

Dune: Imperium을 Python으로 정확하고 재현 가능하게 구현하고, 이를 이용해 강화학습 및 self-play가 가능한 게임 플레이 AI를 만든다. 최종 목표는 사람이 충분히 강하고 재미있는 AI 상대와 완전한 게임을 플레이하며 높은 수준의 Dune: Imperium 경험을 할 수 있게 하는 것이다.

## 구현 방향

- 최초 구현 대상은 **Dune: Imperium - Uprising 4인 플레이, CHOAM Module OFF**다. 기본 게임 완주 검증 뒤 CHOAM Module을 설정 옵션으로 추가한다.
- 개발 및 실행 환경은 **Python 3.14**와 **uv**를 사용한다.
- 현재 `dune/`의 코드는 이전 구현 시도의 참고 자료다. 호환성을 유지할 필요는 없으며, 더 적합한 구조를 위해 처음부터 다시 구현할 수 있다.
- 규칙 구현과 검증에는 Dire Wolf Digital의 공식 온라인 자료를 우선 사용한다. `assets/rulebooks/`의 PDF는 사용자가 로컬에서 열람하기 위한 사본이므로 자동으로 전체를 읽거나 분석하지 않는다. 애매한 규칙 해석과 선택한 판정은 문서화하고 테스트로 고정한다.
- 인접한 `../TabletopGames` 저장소는 보드게임 AI를 위한 구조적 참고 자료다. 특히 game state, forward model/rules, actions, parameters/components의 분리와 RL 연동 방식을 조사해 유용한 개념을 선택적으로 적용한다. 그대로 포팅하거나 런타임 의존성을 두는 것은 아직 결정하지 않았다.
- 게임 규칙 엔진은 UI와 학습 코드에서 분리한다.
- 학습 환경에 필요한 결정론적 실행과 seed 기반 난수, 합법 행동 열거 및 action mask, 플레이어별 관측과 비공개 정보, 상태 복제/직렬화, headless 병렬 실행을 처음부터 고려한다.
- 우선순위는 규칙 정확성, 테스트 가능성, 학습 처리량, AI 성능, 사람이 즐길 수 있는 플레이 경험의 순서로 둔다.

## 목표 상태

1. 선택한 Dune: Imperium 룰셋을 끝까지 플레이할 수 있는 게임 엔진을 완성한다.
2. 규칙 단위 테스트, 시나리오 테스트, seeded replay로 구현을 검증한다.
3. RL 환경과 baseline 플레이어를 만들고 self-play 학습 및 평가 파이프라인을 구축한다.
4. 학습한 AI의 실력을 재현 가능한 상대전과 지표로 평가하며 지속적으로 높인다.
5. 사람이 학습한 AI와 편리하게 완전한 게임을 플레이할 수 있는 인터페이스를 제공한다.

## 아직 결정하지 않은 사항

- 학습 알고리즘과 모델 구조(관측 인코딩 v1과 종료 보상은 [학습 환경 설계](docs/rl-environment.md)로 확정했다)
- 사람용 UI의 추가 조작 개선(형태는 로컬 웹 UI로 확정, 2026-08-30; 구현 순서도 M11을 M9·M10보다 앞으로 조정했다. 2026-08-31에 효과 정보 전면 표시를, 2026-09-03에 보드 스캔 기반 한 화면 테이블과 룰북 아이콘 표시를 추가했다. 2026-09-06 저녁에 호버 팝오버, 보드 슬롯의 Conflict·Contract·덱, 병력 칩, 카드 열 세로 배치, 행동 로그 턴 카드를 추가했다. Agent 토큰 이동 애니메이션 등은 열려 있다)
- CHOAM 이후 다른 확장팩을 추가할 범위와 순서

규칙 코어는 특정 RL 라이브러리에 의존하지 않게 만들고, 첫 표준 다중 에이전트 adapter는 PettingZoo AEC로 한다. 나머지 결정은 규칙 엔진의 수직 조각과 처리량 기준선을 확인한 뒤 명시적인 설계 문서와 테스트 기준으로 확정한다.

## 공식 규칙 자료

- [Dune: Imperium 공식 리소스 페이지](https://www.direwolfdigital.com/dune-imperium/resources/)
- [Dune: Imperium - Uprising 메인 룰북](https://www.direwolfdigital.com/dune-imperium/resources/diu_rules)
- [Uprising Board Space Guide와 보충 규칙](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_UPRISING_Rules_Supplements_23-10-12.pdf)
- [공식 FAQ (2025-01-13)](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_FAQ_25-1-13.pdf)

규칙 조사가 필요할 때는 위 공식 자료에서 해당 규칙과 관련된 부분만 확인한다. 로컬 `assets/rulebooks/` PDF는 공식 자료에 접근할 수 없거나 사용자가 명시적으로 요청한 경우에만 사용한다.

### 공식 룰 문서 작업 도구

공식 PDF를 다시 검증하거나 새 FAQ와 비교할 때는 저장소의 로컬 PDF 대신 다음 도구를 사용한다.

```bash
uv run scripts/prepare_official_rules.py
```

도구는 [고정된 공식 출처 manifest](scripts/official-rule-sources.json)의 PDF를 검증하고, PDF 페이지 marker가 붙은 text working copy를 기본적으로 `/tmp/dune-imperium-official-rules/`에 만든다. 생성된 PDF와 text는 저장소에 추가하지 않는다. FAQ만 다시 준비하려면 `--source faq`, 기존 working copy만 쓰려면 `--offline`을 사용한다. 공식 파일의 SHA-256이 바뀌면 자동으로 받아들이지 않으며, 공식 리소스 페이지에서 새 버전인지 먼저 확인해야 한다.

## 카드 및 이미지 자료

- [Dune Cards Hub - Uprising](https://dunecardshub.com/uprising): Uprising의 리더, 각종 덱 카드, 계약 등 카드 이미지와 카드별 정보를 찾을 때 사용한다.
- [Dune Cards Hub](https://dunecardshub.com): 다른 확장팩 자료가 필요할 때 해당 확장팩을 선택해 사용한다.
- 외부 구조화 데이터의 사용 범위와 검증 정책은 [카드 데이터 전사 출처](docs/card-data-sources.md)에 기록한다.

Dune Cards Hub는 카드 및 시각 자료의 참고 출처로 사용한다. 규칙 설명과 카드 효과 해석이 충돌할 경우에는 Dire Wolf Digital의 공식 룰북과 공식 보충 자료를 우선한다. 이미지 파일을 프로젝트에 포함하거나 재배포하기 전에는 필요한 범위와 이용 조건을 별도로 확인한다.

### 로컬 UI 이미지 준비

카드·보드·아이콘 원본은 저작권 때문에 이 저장소에 넣지 않는다. 플레이 서버는
아래 세 위치를 있을 때만 서빙하고, 없으면 텍스트(및 텍스트 보드 목록)로
대체한다. 소유자의 머신에서는 비공개 `Dune-Imperium-assets` 저장소를 옆에
clone해 저장소 루트의 `assets` symlink 하나로 연결한다(그 README 참고).

- `assets/cards/` (또는 `DUNE_IMPERIUM_CARD_IMAGE_DIR`): 카드 스캔 체크아웃.
  `cards/manifest.json`이 `<세트>/<종류>/<인쇄 카드명>.<확장자>` 파일과 엔진
  content ID를 잇는 유일한 매핑이고, 서버가 시작 시 읽어 존재하는 파일만
  연결한다(`ko/` 스캔이 있으면 파일 단위로 우선, 없으면 `en/`).
  `uv run scripts/fetch_card_images.py`는 manifest가 기록한 출처에서 빠진
  파일만 내려받는다.
- `assets/icons/` (또는 `DUNE_IMPERIUM_ICON_DIR`): 공식 Uprising Main
  Rulebook의 Icon Guide(20쪽)와 Agent 아이콘(9쪽)에서 잘라낸 투명 PNG 45장.
  `uv run --with pymupdf --with pillow scripts/extract_rulebook_icons.py`가
  고정된 PDF를 내려받아 sha256을 검증한 뒤 추출한다(이름 목록은
  `dune_imperium.display.icons`).
- `assets/board/map.jpg` (또는 `DUNE_IMPERIUM_BOARD_IMAGE`): 4인 보드 스캔. hotspot·관측소
  좌표(`dune_imperium.display.board_layout`)는 소유자의 6012×6005 정사각형
  스캔 기준 퍼센트 값이라 다른 프레이밍의 스캔은 재측정이 필요하다.

## 학습 체크포인트

학습된 정책 체크포인트(`dune-imperium-train`의 `latest.pt`, 14~40MB)와 학습 로그는 저장소 루트의 `checkpoints/`에 두며 git이 무시한다. 현재 champion은 `checkpoints/2026-09-06/champion_iter200.pt`이고, `checkpoint:<경로>` 이름으로 대회 도구에, `--resume <경로>`로 학습 루프에 넣는다. 다른 머신에서는 파일을 복사해 쓴다.

## 개발 환경

```bash
uv sync --extra rl --extra ui --extra train
uv run python --version
uv run pytest
uv run ruff check src tests
uv run mypy src tests
```

`uv sync`는 `.python-version`에 지정된 Python 3.14로 `.venv`를 만들고 `uv.lock`에 고정된 의존성을 설치한다. 주의: `uv sync`는 환경을 나열한 extras와 정확히 일치시키므로, extra를 빼고 실행하면 그 extra의 패키지가 제거된다(예: `--extra ui`만 주면 rl의 gymnasium·pettingzoo가 지워진다). 이 저장소의 표준 동기화 명령은 `uv sync --extra rl --extra ui --extra train`이다(`train`은 PyTorch; 없으면 `tests/unit/training/test_torch_policy.py`가 skip된다). 새 구현은 `src/dune_imperium/`에 두며, 기존 `dune/` 패키지는 이전 구현의 참고 자료일 뿐 새 코드에서 import하지 않는다.

### PettingZoo 전체 게임 환경

RL optional 의존성(`rl` extra, 표준 동기화 명령에 포함)을 설치하면 고정 action catalog와 mask를 사용하는 AEC 환경을 실행할 수 있다.

```python
from dune_imperium.adapters.pettingzoo_env import env

environment = env()          # env(choam_module=True)로 CHOAM 룰셋 선택
environment.reset(seed=7)
observation, reward, terminated, truncated, info = environment.last()
```

`dune_imperium_uprising_v1`은 전체 게임을 하나의 episode로 실행한다. 덱 reshuffle 같은 chance 결정은 episode seed에서 유도한 resolver로 내부 해결하고, 게임이 끝나면 공식 최종 순위의 승자가 +1, 나머지가 각 −1/3을 받는다 (중간 보상 없음). 관측 벡터와 세그먼트 표, 보상 근거는 [학습 환경 설계](docs/rl-environment.md)를 따른다.
