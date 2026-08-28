# 개발 인수인계

기준일: 2026-08-28

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
   진입점), `README.md`, 이 문서를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을
   확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl`로 Python 3.14 환경을 준비한다.
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-08-28의 기준 결과는 pytest 602개 통과, Ruff 통과, mypy 통과다. 현재 action
codec은 `ACTION_CODEC_VERSION = 60`이며 기본 룰셋 catalog는 3,510개, CHOAM
룰셋 catalog는 3,737개다.

## 현재 구현 기준선

마지막 기능 커밋은 `Play choice-driven Plot Intrigue through DSL choice slots`
(`git log -1 --grep='choice slots'`)다. 그 앞에 [`refactoring-plan.md`](refactoring-plan.md)의 A·B 단계(frame
kind, 표 기반 dispatch), Covert Operation deadlock 수정, Reserve copy ID 재발급
수정이 있다.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각,
  actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal,
  Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상,
  sandworm·Shield Wall·control, Makers·Recall, Endgame 진입과 안전한 일부 종료를
  실행할 수 있다.
- 시작 카드 7종, Reserve 2종과 기본 Imperium 50종, CHOAM 전용 Imperium 4종
  모두에 완전한 play data가 있다. 구현된 카드별 판정은 personal-card audit에
  기록돼 있다.
- CHOAM을 켜면 standard contract 20장을 replayable chance로 섞고 공개 시장
  2장과 face-down bank 18장을 만든다. Accept Contract와 Conflict reward가 같은
  take/refill 선택을 사용하고, 시장 고갈 시 icon마다 2 Solari로 전환한다.
  20장의 typed 조건·보상이 모두 구현돼 있으며 공간 방문, turn 중 Harvest Spice
  총획득, The Spice Must Flow acquire로 완료한다. 같은 조건의 여러 장은 모두
  의무 완료하고 보상·board·Agent 효과 순서는 플레이어가 정한다.
- CHOAM 전용 Imperium 4종은 완료 Contract 수, 공개 Contract 시장, 시장 고갈의
  2 Solari 전환을 공통 경계로 사용한다. Cargo Runner의 임계 draw는 Agent 효과를
  실제 해결할 때 세며, Interstellar Trade의 Reveal Persuasion은 Reveal 시작 때의
  완료 수로 고정한다. Delivery Agreement와 Priority Contracts의 인쇄된 기본
  Reveal 보상은 DIU JSON과 달리 Spice이며, 4개 이상 완료 시 card trash와 1 VP를
  선택할 수 있다.
- 공간 진입 시 보유 Contract를 snapshot하므로 같은 turn에 보상으로 새 Contract를
  가져와도 소급 완료하지 않는다. Gather Intelligence가 먼저인 것은 OQ-011의
  공식 답이 아니라 명시적으로 테스트한 프로젝트 convention이다.
- 코어 상태 머신과 replay는 여러 라운드를 지원한다. 통합 테스트는 두 라운드 뒤
  세 번째 Round Start의 개인 덱 reshuffle까지 재생한다.
- `run_random_round`, debug CLI, `dune_imperium_uprising_v0` PettingZoo adapter는
  의도적으로 한 라운드에서 끝난다. 전체 게임 runner나 전체 게임 RL episode는
  아직 없다.
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시
  내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다.

## 아직 완성되지 않은 경계

- Intrigue는 effect DSL, Plot play 경계, 선택 슬롯 frame과 Plot 14종이 있다. 나머지 25종과
  Combat/Endgame timing은 없으며 Combat에는 참가자 priority/pass 틀만 있다.
  세부는 [`implementation-audits/intrigue.md`](implementation-audits/intrigue.md).
- Leader는 identity와 setup 선택만 있고 Signet Ring 및 Leader 능력은 없다.
- Objective는 4인 setup, First Player, battle icon 경로가 구현됐지만 이후 콘텐츠
  상호작용은 다시 감사해야 한다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께
  남아 있다. 완료 Contract identity의 관측 정책은 OQ-010, Gather Intelligence와
  완료 순서의 공식 답은 OQ-011 경계를 유지한다.
- held Intrigue가 있는 Endgame은 효과와 priority가 없으므로 보수적으로 자동
  종료하지 않는다. 여러 wild battle-icon pair 선택도 보류돼 있다.
- 모든 미해결 규칙 질문은 [`rules/open-questions.md`](rules/open-questions.md)에
  있으며, 공식 근거 없이 코드로 임의 확정하면 안 된다.

따라서 현재 엔진을 “완전한 Uprising 게임”으로 간주하면 안 된다. CHOAM에는
Shaddam 전용 contract 경로와 전용 Intrigue가 남아 있고, 기본 룰셋에도 Intrigue와
Leader 효과가 빠져 있어 일반적인 전체 게임을 끝까지 실행할 수 없다.

## 다음 구현 순서

standard contract와 CHOAM 전용 Imperium 수직 조각은 완료됐다. 다음 순서를
유지한다.

1. Plot, Combat, Endgame Intrigue 공통 경계와 실제 카드 효과
2. Leader Signet Ring·기본 능력과 Shaddam 전용 Contract, 남은 Objective 상호작용
3. 전체 게임 random/self-play runner와 PettingZoo episode 확장

[`refactoring-plan.md`](refactoring-plan.md)의 A·B 단계와 C 단계의 DSL·첫 Plot
묶음은 끝났다. 선택 슬롯(Faction·discard)도 있다. 바로 다음 작업은 trash·Spy 배치·Shield Wall·
sandworm 같은 나머지 선택형 효과를 DSL에 추가해 남은 Plot Intrigue를 전사하는
것이고, 그 뒤 Combat Intrigue play를 priority/pass loop에 연결한다.
구현 단위는 다음 순서를 따른다.

1. 44장 Intrigue identity를 Plot·Combat·Endgame과 복합 타입으로 분류하고, 공개
   play·공용 discard·조건·비용을 typed content로 전사할 공통 schema를 정한다.
2. 자신의 Agent/Reveal turn에 Plot을 낼 수 있는 serial decision과 해결 후 공개
   discard를 연결한다. 다음 Reveal까지 남는 효과는 별도 지속 상태로 둔다.
3. 단순 자원·병력·Influence Plot 카드부터 실제 효과와 codec 회귀를 추가한다.
4. 이후 Combat priority/pass와 Endgame OQ-001 경계로 확장한다.

이후 카드도 같은 `Play ...` / `Document ...` 패턴을 유지한다. 구체적인 커밋
정책은 `AGENTS.md`에 영구 기록돼 있다.

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
3,000 step/s). 커널 테스트 엔진만 이를 켠다. 200게임×6라운드 random soak은 약
30초면 끝난다.

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

2026-08-28 기준 `origin/master`는 `61d5eda Implement CHOAM contract market`까지
올라가 있었고, 이후 커밋은 push 여부를 `git log origin/master..master`로 확인한다.

- `242bffb Document CHOAM contract market`
- `cfdc4dd Complete standard CHOAM contracts`
- `58747f3 Document standard CHOAM contract completion`
- `b20d403 Play CHOAM Imperium cards`
- `b71cec1 Document CHOAM Imperium cards`
- `6d158a9 Drive the rules dispatcher from frame-kind tables`
- `31d55f7 End the Agent turn after Covert Operation's last opponent discard`
- `3a5c650 Play the first Plot Intrigue batch through an effect DSL`

새 clone으로 이어받는다면 먼저 현재 `master`를 push해야 한다. 새 clone에서는
`git log --oneline -5`에 `b71cec1`이 보이는지 확인한다. 이 커밋들이 없으면 문서에
적힌 v60 action catalog, 3,737개 CHOAM 행동, 602개 테스트 기준선이 실제 코드와
일치하지 않는다.
