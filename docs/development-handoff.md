# 개발 인수인계

기준일: 2026-08-29

이 문서는 새 개발 세션(Claude Code, Codex 등 어떤 도구든)에서 저장소의 현재
위치를 빠르게 복구하기 위한 진입점이다. 규칙의 규범 근거는 [`rules/README.md`](rules/README.md),
장기 마일스톤과 구현 순서는 [`implementation-plan.md`](implementation-plan.md),
카드별 세부 동작은
[`implementation-audits/personal-cards.md`](implementation-audits/personal-cards.md),
계약 경계는
[`implementation-audits/contracts.md`](implementation-audits/contracts.md)를
따른다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`(도구 중립 공통 지침), `CLAUDE.md`(Claude Code
   진입점), `README.md`, 이 문서, 그리고 [`lessons.md`](lessons.md)를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을
   확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl`로 Python 3.14 환경을 준비한다.
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-08-29의 기준 결과는 pytest 639개 통과, Ruff 통과, mypy 통과다. 현재 action
codec은 `ACTION_CODEC_VERSION = 65`이며 기본 룰셋 catalog는 3,737개, CHOAM
룰셋 catalog는 3,973개다.

## 현재 구현 기준선

마지막 기능 커밋은 `72335eb Play Impress and Inspire Awe through the DSL`이고,
그 뒤에 이 슬라이스의 `Document ...` 커밋이 있다.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각,
  actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal,
  Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상,
  sandworm·Shield Wall·control, Makers·Recall, Endgame 진입과 안전한 일부 종료를
  실행할 수 있다.
- 시작 카드 7종, Reserve 2종, 기본 Imperium 50종, CHOAM 전용 Imperium 4종 모두에
  완전한 play data가 있다(`implementation-audits/personal-cards.md`).
- CHOAM standard contract 20장의 시장·완료·보상과 CHOAM 전용 Imperium 4종이
  연결돼 있다(`implementation-audits/contracts.md`).
- Intrigue 44장 중 Plot 20종·Combat 11종(identity 28종)이 effect DSL로 전사돼
  실제 play된다. Plot은 소유자의 `turn`/`agent_effects`/`reveal` frame에서, Combat은
  `combat_intrigue` frame의 priority 보유 참가자에게 제시된다. 선택이 필요한
  효과는 `intrigue_choice` frame의 슬롯으로 순차 해결한다. Impress와 Inspire
  Awe의 비용 상한 획득은 `AcquireCardUpTo` 슬롯으로 Row/Reserve에서 가져오며,
  acquire box의 Spy 배치는 카드 해결 후 `acquisition_spy` frame을 재사용한다
  (`implementation-audits/intrigue.md`).
- Intrigue deck 고갈 시 모든 draw 지점이 `pending_intrigue_draws` 큐를 거쳐
  replayable reshuffle chance로 해결된다.
- 규칙 dispatcher는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS`
  두 표로 동작한다(`refactoring-plan.md`).
- 코어 상태 머신과 replay는 여러 라운드를 지원한다. 200게임×8라운드 random
  soak(replay 검증 포함)이 약 40초에 통과한다.
- `run_random_round`, debug CLI, `dune_imperium_uprising_v0` PettingZoo adapter는
  의도적으로 한 라운드에서 끝난다. 전체 게임 runner나 전체 게임 RL episode는
  아직 없다.
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시
  내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다.

## 아직 완성되지 않은 경계

- Intrigue 11종 identity는 setup만 있고 play할 수 없다. 필요한 경계별로:
  - turn 지속 트리거("이번 Reveal에서 획득할 때마다", "한 turn에 unit 3 배치 시",
    "이번 turn에 spice를 얻었다면"): Call to Arms, Distraction ×2, Leverage(CHOAM;
    카드 아이콘을 아직 확인하지 못함)
  - Endgame timing(OQ-001): Crysknife, Desert Mouse, Ornithopter의 Endgame 절반,
    CHOAM Profits, Secure Spice Trade, Shadow Alliance
  - Imperium Row 교체와 할인 지속: Manipulate
  - "Conflict를 이길 때" 종류: Spring the Trap 등은 카드 확인 필요
  - Endgame과 "이길 때" 카드가 없으므로 held Intrigue가 있는 Endgame은 보수적으로
    자동 종료하지 않는다(OQ-001).
- Reveal turn 중 card가 hand에 들어가는 Plot(개인 card draw, Inspire Awe의
  조건부 hand 획득)은 FAQ p. 3의 즉시 공개 규칙이 구현되지 않아 Reveal에서
  제시하지 않는다(OQ-015(c)).
- Leader는 identity와 setup 선택만 있고 Signet Ring 및 Leader 능력은 없다.
  `UNIMPLEMENTED_AGENT_EFFECTS`가 Signet Ring 카드를 숨긴다.
- `secrets`, `desert_tactics` board space는 board effect가 미구현이라 dispatcher가
  숨긴다(`board_effect_is_implemented`).
- Objective는 4인 setup, First Player, battle icon 경로가 구현됐지만 이후 콘텐츠
  상호작용은 다시 감사해야 한다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께
  남아 있다. OQ-010, OQ-011 경계를 유지한다.
- 모든 미해결 규칙 질문과 프로젝트 convention(OQ-003, OQ-015 등)은
  [`rules/open-questions.md`](rules/open-questions.md)에 있으며, 공식 근거 없이
  코드로 임의 확정하면 안 된다. 규칙 동작을 바꾸기 전에는 반드시 `docs/rules/`의
  문장을 인용한다([`lessons.md`](lessons.md)).

따라서 현재 엔진을 "완전한 Uprising 게임"으로 간주하면 안 된다.

## 다음 구현 순서

큰 순서는 유지한다.

1. 남은 Intrigue 11종의 경계 (아래 세부 순서)
2. Leader Signet Ring·기본 능력과 Shaddam 전용 Contract, 남은 Objective 상호작용
3. 전체 게임 random/self-play runner와 PettingZoo episode 확장

Intrigue 세부 순서(권장):

1. **turn 트리거** — Call to Arms("이번 Reveal에서 획득할 때마다 troop 1"),
   Distraction("한 turn에 unit 3 이상 배치 시 상대 Spy와 같은 post에 Spy 배치").
   FAQ p. 2대로 다음 Reveal까지 face-up으로 두는 지속 효과 상태가 필요하다
   (`PlayerState`에 pending Plot 효과 목록). Leverage는 먼저 카드 이미지를 확인한다
   (`https://dunecardshub.com/images/uprising-intrigue-leverage.webp`).
   핸드오프의 카드 요약은 이미지 검증 전 참고일 뿐이다(Impress의 비용 상한이
   4로 잘못 적혔다가 카드 이미지로 3임을 확인한 전례가 있다).
2. **Endgame Intrigue** — OQ-001의 참가 순서·종료 조건·wild matching 시점을
   convention으로 정한 뒤 Endgame frame에서 play한다. 카드 6종.
3. Manipulate(custom hook), "이길 때" 카드.

각 묶음은 카드 이미지로 텍스트를 검증하고(`docs/card-data-sources.md`의 방법),
`Play ...` / `Document ...` 커밋 쌍을 유지하며, 새 결정 경계는
`FrameKind` → frame `kind` → dispatcher 표 → codec 순으로 추가한다.

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` |
| Agent 배치와 카드 효과 | `src/dune_imperium/rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `src/dune_imperium/rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `src/dune_imperium/rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher 표와 frame kind | `src/dune_imperium/rules/engine.py`, `frames.py`, `agent_effect_frame.py` |
| effect DSL과 Intrigue | `content/uprising/effect_dsl.py`, `intrigue.py`, `rules/effect_interpreter.py`, `rules/intrigue.py`, `rules/intrigue_deck.py` |
| 고정 action catalog | `src/dune_imperium/adapters/action_codec.py` |
| 관측과 PettingZoo | `src/dune_imperium/core/observation.py`, `adapters/pettingzoo_env.py` |
| replay와 random round | `src/dune_imperium/core/replay.py`, `simulation/runner.py` |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은
`docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical
hash하는 디버그 가드라 기본 off다(켜면 random play가 약 70 step/s, 끄면 약
3,000 step/s). 커널 테스트 엔진만 이를 켠다. 200게임×8라운드 random soak
(replay 검증 포함)은 2026-08-29 측정 기준 약 11초에 끝난다. soak 스크립트는
저장소에 없으므로 세션 scratchpad에서 `run_random_round`의 루프를 다회전으로
확장해 작성한다.

## 유용한 명령

```bash
# 한 라운드 random 실행
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002

# 대화형 한 라운드 실행
uv run dune-imperium-debug --seed 2

# 명시적으로 준비한 DIU working copy와 identity/effect shape 대조
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON

# 공식 PDF와 고정 checksum 재검증; 생성물은 /tmp에만 둔다
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 제한되면 명령 앞에
`UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

2026-08-29 작업 시작 시점의 `origin/master`는 `ed16d93 Refresh the development
handoff for the next session`이고, 로컬 `master`에는 그 뒤 Impress·Inspire Awe
슬라이스 커밋(`72335eb Play ...`와 이어지는 `Document ...`)이 있다. 새 세션은
`git log origin/master..master`로 push 여부를 확인한다. checkout이 `ed16d93`
이전이면 이 문서의 v65 action catalog, 3,737/3,973개 행동, 639개 테스트
기준선이 실제 코드와 일치하지 않는다.

## 2026-08-29 세션 요약

- Impress(Combat: 검 2 + 비용 3 이하 획득)와 Inspire Awe(Plot: 비용 3 이하 획득,
  sandworm이 Conflict에 있으면 hand로)를 카드 이미지로 검증해 전사했다. 이전
  핸드오프의 "Impress 비용 4"는 오기였다.
- `AcquireCardUpTo(max_cost, to_hand_if)` DSL 보상과 `acquire_intrigue_imperium`
  / `acquire_intrigue_reserve` 선택 슬롯을 추가했다. Row 보충, acquire box 즉시
  처리, Spy 배치 box의 `acquisition_spy` frame 재사용(카드 해결 후 push),
  Contract 완료 확인을 기존 획득 경로와 공유한다. codec v65.
- Reveal 중 hand로 들어가는 획득은 OQ-015(c)를 확장해 draw와 동일하게 보류한다.
- 알려진 기존 버그(이번 슬라이스와 무관, HEAD `ed16d93`에서 재현): 4인 기본
  룰셋 seed 10146 random play에서 Prepare the Way를 Agent 카드로 낼 때
  `resolve_agent_card_effect`가 legal로 제시된 뒤 적용 시
  "conditional Agent effect is not available"로 실패한다. legal 제공자와
  `rules/agent_effects.py:1523` resolver의 조건 판정 불일치로 보이며, 별도
  수정 작업으로 분리했다.

## 2026-08-28 세션 요약

- Codex → Claude Code 전환. `AGENTS.md`를 도구 중립으로, `CLAUDE.md`를 진입점으로.
- 리팩토링 A·B: `DecisionFrame.kind`, `rules/frames.py`, 표 기반 dispatcher. 그
  과정에서 Covert Operation deadlock, Reserve copy ID 재발급, Spy 공급 판정 버그
  수정.
- effect DSL(C 단계)과 Intrigue: Plot 19종·Combat 10종, 선택 슬롯 frame, Intrigue
  draw 공통 reshuffle 경계, OQ-003·OQ-015 convention.
- 처리량: 입력 불변 hash 가드를 opt-in으로 바꿔 random play 약 45배 가속.
- 코드 리뷰(`/code-review`) 후속 항목은 `refactoring-plan.md` 끝에 있다.
- 교훈: 리뷰 지적을 규칙 문서 확인 없이 반영해 Harvest 계약 판정을 잘못 바꿨다가
  되돌림 → `lessons.md`, `AGENTS.md` 규칙 인용 의무.
