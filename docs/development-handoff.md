# 개발 인수인계

기준일: 2026-08-28

이 문서는 새 Codex 계정이나 새 개발 세션에서 저장소의 현재 위치를 빠르게
복구하기 위한 진입점이다. 규칙의 규범 근거는 [`rules/README.md`](rules/README.md),
장기 마일스톤과 구현 순서는 [`implementation-plan.md`](implementation-plan.md),
카드별 세부 동작은
[`implementation-audits/personal-cards.md`](implementation-audits/personal-cards.md),
계약 경계는
[`implementation-audits/contracts.md`](implementation-audits/contracts.md)를
따른다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`와 `README.md`, 이 문서를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을
   확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl`로 Python 3.14 환경을 준비한다.
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-08-28의 기준 결과는 pytest 558개 통과, Ruff 통과, mypy 통과다. 현재 action
codec은 `ACTION_CODEC_VERSION = 57`이며 기본 룰셋 catalog는 3,377개, CHOAM
룰셋 catalog는 3,491개다.

## 현재 구현 기준선

마지막 기능 커밋은 `cfdc4dd Complete standard CHOAM contracts`다. 이 기능의
규칙·로드맵 문서는 이 기준선에 반영했다.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각,
  actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal,
  Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상,
  sandworm·Shield Wall·control, Makers·Recall, Endgame 진입과 안전한 일부 종료를
  실행할 수 있다.
- 시작 카드 7종, Reserve 2종과 기본 Imperium 50종 모두에 완전한 play data가
  있다. 구현된 카드별 판정은 personal-card audit에 기록돼 있다.
- CHOAM을 켜면 standard contract 20장을 replayable chance로 섞고 공개 시장
  2장과 face-down bank 18장을 만든다. Accept Contract와 Conflict reward가 같은
  take/refill 선택을 사용하고, 시장 고갈 시 icon마다 2 Solari로 전환한다.
  20장의 typed 조건·보상이 모두 구현돼 있으며 공간 방문, turn 중 Harvest Spice
  총획득, The Spice Must Flow acquire로 완료한다. 같은 조건의 여러 장은 모두
  의무 완료하고 보상·board·Agent 효과 순서는 플레이어가 정한다.
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

- CHOAM 전용 Imperium 미전사 4종:
  `Cargo Runner`, `Delivery Agreement`, `Interstellar Trade`,
  `Priority Contracts`
- Intrigue는 identity와 setup deck만 있으며 Plot/Combat/Endgame 실제 play 효과가
  없다. Combat에는 참가자 priority/pass 틀만 있다.
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

따라서 현재 엔진을 “완전한 Uprising 게임”으로 간주하면 안 된다. CHOAM을
켜면 미전사 Imperium 카드와 Shaddam 전용 contract 경로가 남아 있고, 기본 룰셋에도
Intrigue와 Leader 효과가 빠져 있어
일반적인 전체 게임을 끝까지 실행할 수 없다.

## 다음 구현 순서

standard contract 수직 조각은 완료됐다. 다음 순서를 유지한다.

1. CHOAM 전용 Imperium 4종
2. Plot, Combat, Endgame Intrigue 공통 경계와 실제 카드 효과
3. Leader Signet Ring·기본 능력과 Shaddam 전용 Contract, 남은 Objective 상호작용
4. 전체 게임 random/self-play runner와 PettingZoo episode 확장

바로 다음 작업은 CHOAM 전용 Imperium 4종이다:
`Cargo Runner`, `Delivery Agreement`, `Interstellar Trade`,
`Priority Contracts`. 구현 단위는 다음 순서를 따른다.

1. linked printed image로 네 카드의 Agent·Reveal·Acquire 효과와 Contract 참조를
   대조해 typed content로 전사한다.
2. standard Contract 완료 count/시장 선택과 상호작용하는 효과를 기존 공통
   transition에 연결한다.
3. 같은 turn 효과 순서가 OQ-012에 닿으면 공식 근거를 다시 확인하고, 답이 없으면
   project convention을 먼저 문서화한다.
4. 카드별 legal action, reward, replay와 codec 회귀를 추가하고 전체 검증을 한다.

이후 카드도 같은 `Play ...` / `Document ...` 패턴을 유지한다. 구체적인 커밋
정책은 `AGENTS.md`에 영구 기록돼 있다.

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` |
| Agent 배치와 카드 효과 | `src/dune_imperium/rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `src/dune_imperium/rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `src/dune_imperium/rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher | `src/dune_imperium/rules/engine.py` |
| 고정 action catalog | `src/dune_imperium/adapters/action_codec.py` |
| 관측과 PettingZoo | `src/dune_imperium/core/observation.py`, `adapters/pettingzoo_env.py` |
| replay와 random round | `src/dune_imperium/core/replay.py`, `simulation/runner.py` |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은
`docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

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

Codex sandbox에서 uv cache 쓰기가 제한되면 명령 앞에
`UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

이 문서를 갱신할 때 로컬 `master`에는 `origin/master`의
`f9026ec Document Steersman roadmap` 이후 Junction Headquarters, Corrinth City,
Desert Power, Long Live the Fighters, Subversive Advisor와 standard CHOAM
contract 구현·문서 커밋이 더
있지만 아직 원격에는
보이지 않는다. 새 계정이
새 clone으로
이어받는다면 기존 계정에서 현재 `master`를 먼저 push하거나 저장소 자체를
전달해야 한다.

새 clone에서는 다음 커밋이 보이는지 최소한 확인한다.

```bash
git log --oneline --all --decorate -10
```

- `7f7ee38 Play Junction Headquarters`
- `4a738cc Document Junction Headquarters`
- `d680488 Play Corrinth City`
- `6aa0832 Document Corrinth City`
- `958897a Play Desert Power`
- `98a013c Play Long Live the Fighters`
- `2b1b25f Play Subversive Advisor`
- `61d5eda Implement CHOAM contract market`
- `cfdc4dd Complete standard CHOAM contracts`

이 커밋들이 없으면 문서에 적힌 v57 action catalog와 standard contract 기준선이
실제 코드와 일치하지 않는다.
