# 평가 문제집 (problem set)

사람 팁을 학습에 쓰는 경로 가운데 **평가 문제집**([player-tips-for-training.md](../player-tips-for-training.md) 3절의
2번)의 틀이다(2026-09-23). "이 상황에서는 이 답(들)이 옳다"는 실제 게임 포지션을 모아 두고, 에이전트가 거기서 무엇을
고르는지와 — 네트워크라면 — 옳은 답들에 **확률을 얼마나 주는지**를 잰다. 승률은 몇 %p를 가르는 데 수천 판이 드는데, 문제집은
판 결과의 잡음이 없고 몇 분이면 끝난다.

원칙:

- **평가만 한다. 학습 목표로 쓰지 않는다** — 쓰는 순간 지표가 망가진다.
- 정책이 문항의 답과 다르면 **자동 오답이 아니라 조사 대상**이다. 문항에는 `confidence`가 있다: `clear`는 답이 규칙만으로
  따라 나오는 문항(근거와 인용을 코드 docstring과 아래 표에 적는다), `tip`은 사람 조언이 답인 문항이다. 둘은 따로 보고한다.
- 문항은 "명백한 경우"로 좁힌다. 애매한 변형은 탐지 조건에서 뺀다(예: 와일드 매칭이 가능한 Endgame 창).

## 구조 — `src/dune_imperium/evaluation/problem_set.py`

- **문항**(`Problem`) = 탐지기(이 결정이 문항의 사례인가) + 판정기(이 합법 행동이 옳은 답인가) + 출처 + `confidence`.
- **채굴**(`mine`): registry의 어떤 에이전트로든 seed 게임을 두며, 결정마다 탐지기를 돌려 좌석·문항당 **첫 사례**만 남긴다.
- **저장**: 포지션은 게임 spec(seed·구성·Leader)과 **그 결정까지의 플레이어 선택 번호**만 저장한다. chance는 seed의 난수를
  순서대로 쓰므로 엔진만으로 다시 만든다. 합법 집합의 지문(`fingerprint`)을 함께 저장해, 엔진이 바뀌어 포지션이 움직이면
  복원이 **"re-mine"** 오류를 낸다 — 그때는 문제집을 다시 캔다(규칙 정정 뒤의 정상 절차).
- **복원 가드**: 기본 pytest의 `tests/unit/test_problem_set.py::test_every_position_of_the_committed_suite_restores`가
  커밋된 문제집의 **모든** 포지션을 `check`와 같은 함수(`unrestorable`)로 복원해 본다(약 10초). 규칙을 바꿔 포지션이 움직이면
  움직인 포지션 id 목록과 함께 실패한다 — 그 커밋에서 아래 "다시 캐는 명령"으로 다시 캔다. 2026-09-27 전에는 문항마다 앞의 3개만
  복원해 봐서, master `60f8e95`에서 106개 가운데 4개가 조용히 깨져 있다가 다음 재채굴 때에야 드러났다(첫 번째 `s42/p2`는 OQ-069
  병합 `1420936`부터 깨져 있었다).
- **채점**(`answer`): 포지션마다 새 에이전트를 만들어 그 결정을 묻는다. 모든 에이전트는 "고른 행동이 옳은가"로, 네트워크
  (`checkpoint:`)는 추가로 **옳은 답들의 softmax 확률 합**(`p_right`)으로 채점한다. `search:`·`rollout`은 상태를 받는 탐색으로 답한다.

```bash
uv run dune-imperium-problems mine --agents heuristic --games 400 --choam --bloodlines --tech-module \
    --immortality --promo-cards --workers 4 --max-per-problem 40 --out <suite.json>
uv run dune-imperium-problems score --agents heuristic,random,checkpoint:<path> [--json answers.json]
```

`--append`는 다른 테이블의 포지션을 같은 파일에 더한다(포지션 id에 생성 테이블 이름이 들어간다).

**다시 캐는 명령**(tips-v1). 파일의 `note`는 명령줄이 아니라 캔 조건의 요약("heuristic mirror seeds 0-799 (all problems) and
800-2799 (last_round_hold_battle_icon only), 5081 mirror seeds 0-59; at most 40 positions per problem per run")이므로, 그대로 옮긴
명령은 이렇다(2026-09-26 밤 재채굴에 쓴 것; 약 4분). 새 파일에 캔 뒤 `check`로 확인하고 커밋된 파일을 바꾼다.

```bash
FLAGS=(--choam --bloodlines --tech-module --immortality --promo-cards --workers 4 --max-per-problem 40)
NOTE="$(uv run python -c 'from dune_imperium.evaluation.problem_set import suite_note; print(suite_note())')"
uv run dune-imperium-problems mine --agents heuristic --games 800 --start-seed 0 "${FLAGS[@]}" --note "$NOTE" --out <new.json>
uv run dune-imperium-problems mine --agents heuristic --games 2000 --start-seed 800 \
    --problems last_round_hold_battle_icon "${FLAGS[@]}" --append --out <new.json>
uv run dune-imperium-problems mine --agents checkpoint:<champion-5081.pt> --games 60 --start-seed 0 "${FLAGS[@]}" \
    --append --out <new.json>
uv run dune-imperium-problems check --suite <new.json>
```

5081은 `checkpoints/2026-09-22/exploit/champion-5081.pt`(git 무시, 메인 체크아웃)이다. 옛 codec의 체크포인트는 불러올 때 행동
이름으로 이관된다.
`check`는 문제집의 모든 포지션을 복원해 본다(위의 복원 가드와 같은 검사). 2026-09-27 Mac mini 실측으로 109개에 약 10초, 포지션 하나에 약 0.1초가 든다.

## 문항 (tips-v1)

| 문항 | 출처 | confidence | 탐지 조건 | 정답 |
|---|---|---|---|---|
| `endgame_battle_icon_vp` | C8.3 | clear | Endgame Intrigue 창에서 Crysknife·Desert Mouse·Ornithopter의 Endgame 선택지가 합법. **제외**: 와일드 매칭이 합법이거나 Grasp Arrakis를 들고 있을 때(같은 앞면 카드를 두고 다툰다) | 패스만 아니면 된다 — Endgame 선택지는 그 아이콘의 앞면 Conflict 카드를 뒤집고 1 VP `[카드 면]`, Endgame Intrigue는 점수 비교 전에 해결되고 `[Main p. 15]` VP가 첫 순위 기준이며, 패스하면 그 좌석의 창은 다시 열리지 않는다(OQ-001, project convention) |
| `last_round_hold_battle_icon` | C8.3, 7.7 | **tip** | 확실한 마지막 라운드(Conflict 덱이 비었다 `[Main p. 15]`), 턴 선택 결정, 그 아이콘 Intrigue를 한 장만 들고 있고 뒤집을 앞면 카드가 있음. **제외**: 앞면 와일드 카드(Endgame 와일드 매칭으로 어차피 점수가 난다 `[Main p. 20]`), 현재 Conflict가 와일드이거나 같은 아이콘, Ornithopter Fleet `[Bloodlines p. 12]`, Grasp Arrakis 보유, Intrigue 4장 이상(Secrets `[Board Guide p. 2]`), spice 1이 더 있으면 합법 집합이 달라지는 결정, Plot의 spice가 "이번 턴에 얻은 spice" 판정(Guild Impersonator·Fremen War Name·Sandwalk, Agent 효과 처리 중의 spice 수확 계약, Steersman Y'rkoon의 Hungry for Spice, `GainedSpiceThisTurn` Intrigue)을 채울 수 있는 경우 | 그 카드를 지금 Plot(spice 1)으로 쓰지 않는다 |
| `deep_desert_summon_into_contest` | 사용자 팁 1(6.3), C2.3 | tip | Deep Desert에서 소환·수확이 둘 다 합법, tier II/III Conflict, 아직 자기 sandworm이 없음, sandworm 둘(+6 `[Main p. 12]`)로 1위가 되거나 보상 받는 순위가 오른다. **제외**: Arrakis Planetologist(그의 소환은 Conflict에 sandworm을 넣지 않는다) | 소환(spice 4 `[Board Guide p. 1]` 대신; 보상 두 배, 단 control·battle icon 제외 `[Main p. 14]`). **소환/수확만 채점**하고, 다른 효과를 먼저 처리하는 것은 선택을 미루는 것으로 본다 |

## 검증에서 배운 것 (2026-09-23)

첫 판을 Opus 검증자 넷(문항마다 하나 + 틀 코드)에게 반박시키니 다음이 나왔고 모두 반영했다.

- **"규칙상 명백"은 생각보다 드물다.** 마지막 라운드 보유 문항은 처음에 `clear`였는데, 26개 가운데 4개는 뒤집을 대상이 앞면
  와일드 카드여서 보유 가치가 0이었고(Endgame 와일드 매칭이 어차피 점수를 준다), 1개는 Plot의 spice가 같은 턴의 Guild
  Impersonator("이번 턴에 spice를 얻었다면")를 발동시켜 오히려 Plot이 1 VP 이득이었으며, spice 1이 더 있으면 합법 집합이 바뀌는
  것이 7개(그중 2개는 영향력 VP로 이어짐)였다. 명백하지 않은 경우를 빼고 `tip`으로 내렸다. 검증자가 제안한 "턴 선택 결정에서만"은
  쓰지 않았다 — 턴 시작에 Plot으로 얻은 spice도 같은 턴의 판정에 들어가므로 원리상 부족하고, 첫 사례 9개 중 7개가 Agent 효과
  처리 중에 나와 문항을 사실상 없앴다. 대신 그 판정을 쓸 수 있는 경우만 뺐다. 그래도 이 문항은 드물다(heuristic 400판에 2개) —
  heuristic은 카드를 곧바로 쓰고, 마지막 라운드·앞면 비와일드 카드·계약 없음이 겹쳐야 하기 때문이다.
- **효과 순서 창**: Agent turn의 효과들은 순서를 골라 해결하므로, Maker 칸 선택은 카드 효과·Signet·배치 같은 다른 선택과 함께
  제시된다. 첫 판정기는 "다른 효과 먼저"를 오답으로 셌다(80개 중 78개가 그런 창). **설계 규칙: 순서 창에서는 답을 확정하는
  행동만 채점하고(`Problem.scored`), 다른 행동을 고르면 같은 에이전트로 그 선택까지 계속 둔다.**
- 틀 코드: 복원할 때 탐지기를 다시 돌린다(합법 집합이 같아도 상태가 바뀌면 잡는다), 포지션 id에 좌석 배치 전체를 넣는다(섞인
  테이블의 회전끼리 겹쳤다), 중복 id는 오류, 채굴 워커는 torch 스레드 하나.

## tips-v1 결과 (2026-09-23)

문제집: `src/dune_imperium/evaluation/problem_sets/tips-v1.json`, 110개 — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드
보유 20(전부 heuristic; 5081 60판에서는 0개), Endgame 10(heuristic 9 + 5081 1). 학습 구성(CHOAM + promo + Bloodlines + Tech +
Immortality). 캔 명령은 파일의 `note`에 있다. 원자료 git 무시 `ab-runs/tips/problems-v1*.json`.

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 10) | 마지막 라운드 보유 (tip, 20) |
|---|---|---|---|
| random | 0.53 | 0.20 | 0.85 |
| heuristic | 1.00 | 1.00 | 0.50 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.85 / 0.80 |
| 5081 탐색 좌석 (`search:`, 결정당 약 2초) | 0.93 | 1.00 | 0.85 |

- 5081은 sandworm·Endgame 문항에서 이미 팁대로 둔다(사용자 팁 1이 정책에 있다는 6.3의 census와 같은 결론을, 판 결과 잡음 없이
  확인). 80개 중 2개에서는 다른 효과를 먼저 처리한 뒤 소환했다 — 순서 창 처리가 없었다면 오답으로 셌을 경우다.
- 마지막 라운드 보유에서 5081은 20개 중 3개를 Plot으로 쓴다. 그중 둘은 옳은 쪽에 확률 0.0을 준다(확신): `.../s1240/p1`
  (Ornithopter), `.../s2281/p0`(Desert Mouse); 셋째는 `.../s2728/p3`(0.15). 조사 대상이다 — 문항이 tip인 만큼 먼저 그 포지션에서
  spice가 쓰일 곳이 없는지부터 본다.
- 무작위가 보유 문항에서 0.85인 것은 그 결정의 합법 행동 대부분이 "그 카드를 Plot으로 쓰지 않는 것"이기 때문이다 — 이 문항은
  **틀린 쪽의 확률(1 − P(정답))**을 보는 것이 더 뜻이 있다.
- heuristic은 sandworm(소환 점수가 높다)과 Endgame에서 구조상 정답이다.
- 탐색 좌석은 보유 문항의 네트워크 오답을 고치지 못했다(같은 20개 중 3개 오답: `s1240/p1`·`s2728/p3`은 그대로이고, `s2281/p0`는
  고쳤지만 `s2452/p0`를 새로 틀렸다). sandworm 문항에서는 네트워크가 소환하던 6개(`s4/p1`·`s5/p3`·`s6/p0`·`s12/p2`·`s17/p3`·
  `s49/p2`)에서 수확을 골랐다 — 라운드 끝까지만 보는 탐색이 두 배 보상의 값을 네트워크보다 낮게 읽는 것으로 보이지만 확인하지
  않았다(조사 후보).

## 재채굴 (2026-09-25)

Bloodlines 카드면 전사 정정 셋 — Chani의 Fedaykin Maneuver(water → 카드 2장 draw), Fenring의 Corrino Liaison과 Storms in the
South 1등 보상의 Spy with Deep Cover([implementation-audits/leaders.md](../implementation-audits/leaders.md),
[implementation-audits/bloodlines.md](../implementation-audits/bloodlines.md)) — 뒤에 국면이 복원되지 않아(`check` 96/110, 이어서
87/107), 정정마다 파일의 `note` 명령 그대로 다시 캤다. 최종 **104개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유
17(전부 heuristic), Endgame 7(heuristic 6 + 5081 1). 바뀌거나 빠진 국면은 첫 재채굴에서는 전부 Chani나 Fenring이 앉은 판,
둘째에서는 전부 Storms in the South가 Conflict 덱에 든 판이었다. 두 규칙과 무관한 국면이 새로 든 경우는 문항당 40개 상한의
꼬리 보충(옛 마지막 seed보다 뒤의 seed)뿐이다. 위 2026-09-23 표는 재채굴 전 110개로 잰 것이다. 최종 문제집의 채점(탐색 좌석은
다시 재지 않았다):

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 7) | 마지막 라운드 보유 (tip, 17) |
|---|---|---|---|
| random | 0.49 | 0.14 | 0.88 |
| heuristic | 1.00 | 1.00 | 0.59 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.88 / 0.84 |

- 5081의 보유 문항 오답은 `s1240/p1`(P(정답) 0.0003)·`s2728/p3`(0.15) 둘이다. 위에서 적은 셋째 `s2281/p0`는 Fenring이 앉은 판이라
  첫 재채굴에서 빠졌다.

## 재채굴 (2026-09-26, 전수 감사)

카드·보드 전사 전수 감사([implementation-audits/transcription-audit-2026-09-26.md](../implementation-audits/transcription-audit-2026-09-26.md))의
규칙 수정 110여 건은 기본판 카드도 바꿔(The Spice Must Flow의 Reveal, Reserve·Imperium 카드의 소속, Agent 아이콘 등) 고정한 국면이
하나도 복원되지 않았다. 파일의 `note` 명령 그대로 다시 캤다(5081 체크포인트는 codec v107 → v108로 이관: 유지 32,980·새 23·삭제 7).
**108개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 19(전부 heuristic), Endgame 9(전부 heuristic). 새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 9) | 마지막 라운드 보유 (tip, 19) |
|---|---|---|---|
| random | 0.54 | 0.44 | 0.68 |
| heuristic | 1.00 | 1.00 | 0.37 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.95 / 0.88 |

5081은 옛 규칙으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게 두는지를 볼 뿐이다.

같은 날 통합 리뷰의 규칙 수정(Reveal 중 Command·Holy War, Chani의 Tactics, Desert Power의 sandworm 제한, Agent box·Plot으로 recruit한
troop의 배치 몫 등, [감사 문서](../implementation-audits/transcription-audit-2026-09-26.md)의 "통합 리뷰" 절) 뒤 국면 넷이 복원되지 않아
같은 명령으로 한 번 더 캤다. **106개**(유지 104, 빠짐 4 — sandworm 2와 마지막 라운드 보유 2, 새로 듦 2 — sandworm 2): sandworm 80,
마지막 라운드 보유 17, Endgame 9.

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 9) | 마지막 라운드 보유 (tip, 17) |
|---|---|---|---|
| random | 0.56 | 0.44 | 0.71 |
| heuristic | 1.00 | 1.00 | 0.35 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.94 / 0.88 |

## 재채굴 (2026-09-26 밤, Agent box Spy의 거절)

Agent box Spy의 거절(`decline_agent_card_spy`, codec v110, [OQ-057 (14)](../rules/open-questions.md))은 supply가 빈 채 Spy
아이콘 box가 대기하는 결정의 합법 집합에 행동 하나를 recall들 앞에 더한다. heuristic은 recall(1.0)을 거절(−2.0)보다 높게 쳐 그
결정에서 전과 똑같이 두지만, 저장된 선택 번호가 밀려 sandworm 국면 넷(heuristic `s3/p2`·`s21/p3`·`s34/p3`·`s41/p3`; 지문·길이는
그대로, 번호 1~3개만 다름)이 복원되지 않았다. 그 전에 master(`60f8e95`)에서 이미 넷(heuristic `s7/p0`·`s7/p1`·`s42/p2`, 5081
`s15/p1`)이 복원되지 않고 있었다 — 106개 재채굴 뒤의 recruit 집계 전수 수정, OQ-064·066·068·069 판정, 강제 Spy 이동 순서가 판을
바꿨다. 파일의 `note` 명령 그대로 다시 캤다(5081은 codec v107 → v110으로 이관: 유지 32,980·새 27·삭제 7). **109개**(그대로 98,
같은 id에 선택 번호만 바뀜 7, 빠짐 1 — sandworm `s42/p2`, 새로 듦 4 — sandworm `s37/p0`와 마지막 라운드 보유 `s1010/p2`·`s1037/p0`·
`s1330/p0`): sandworm 80, 마지막 라운드 보유 20, Endgame 9. 새로 든 마지막 라운드 보유 셋은 master 엔진으로 같은 seed를 캐도
나온다 — 이번 변경이 아니라 앞의 규칙 수정에서 왔다.

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 9) | 마지막 라운드 보유 (tip, 20) |
|---|---|---|---|
| random | 0.56 | 0.44 | 0.75 |
| heuristic | 1.00 | 1.00 | 0.40 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.95 / 0.90 |

## 재채굴 (2026-09-27, OQ-070)

recruit한 Sardaukar Commander의 배치 몫은 Commander 것이라는 사용자 판정(OQ-070) 뒤 국면 13개가 복원되지 않아 같은 명령으로 다시
캤다. **111개**(유지 93, 빠짐 13 — 마지막 라운드 보유 7·Endgame 4·sandworm 2, 새로 듦 18 — 보유 13·Endgame 3·sandworm 2): sandworm 80,
마지막 라운드 보유 23, Endgame 8. 빠진 국면이 많은 것은 Commander가 있는 판에서 배치 수가 바뀌어 그 뒤 진행이 모두 달라지기 때문이다.

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 8) | 마지막 라운드 보유 (tip, 23) |
|---|---|---|---|
| random | 0.56 | 0.50 | 0.70 |
| heuristic | 1.00 | 1.00 | 0.35 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.83 / 0.83 |

## 재채굴 (2026-09-27, 병합: Agent box Spy의 거절 + OQ-070)

위 두 재채굴은 서로 다른 브랜치에서 했다(Agent box Spy의 거절은 `agent-card-spy-decline`, OQ-070은 master). 병합한 엔진에서는 어느
쪽 파일도 전부 복원되지 않아(master의 111개 중 104개) 구조 절의 "다시 캐는 명령"으로 다시 캤다. **111개**, master의 OQ-070 문제집과
견주면 그대로 104, 같은 국면(지문·길이 같음)에 선택 번호만 1~7개 밀린 것 7(sandworm `s3/p2`·`s21/p3`·`s34/p3`·`s41/p3`, 마지막 라운드
보유 `s807/p3`·`s1052/p0`·`s2195/p0`), 빠지거나 새로 든 국면 없음: sandworm 80, 마지막 라운드 보유 23, Endgame 8. 국면이 모두 같으므로
채점은 위 OQ-070 표와 같다.

## 재채굴 (2026-09-27, 계약 구성 정정)

CHOAM standard 계약에서 Rise of Ix 전용 타일 4장을 빼고 Spice Refinery I·II와 Espionage I·Harvest 3+의 두 번째 사본을 넣자
(`[Main p. 16]`, codec v111·관측 v21, [lessons](../lessons.md)) 커밋된 111개 가운데 복원되지 않는 것이 생겨 구조 절의
"다시 캐는 명령"으로 다시 캤다(5081 체크포인트는 codec v107 → v111로 이관). **118개**, 옛 파일과 견주면 그대로 78, 빠진 것 33,
새로 든 것 40: sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 28, Endgame 10. 새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 10) | 마지막 라운드 보유 (tip, 28) |
|---|---|---|---|
| random | 0.53 | 0.70 | 0.79 |
| heuristic | 1.00 | 1.00 | 0.25 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.93 / 0.89 |

## 재채굴 (2026-10-01, OQ-095: Agent turn은 "턴 종료"로만 끝남)

모든 Agent turn이 소유자의 `finish_agent_turn`으로만 끝나게 되어([OQ-095](../rules/open-questions.md), codec v125) 첫 Agent turn부터
판의 경로가 바뀌어 고정한 국면이 하나도 복원되지 않았다. 파일의 `note` 명령 그대로 다시 캤다(5081은 메인 체크아웃의 절대 경로로;
워크트리에는 `checkpoints/`가 없다). **106개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 17(heuristic 4 +
2,000판 보충 12 + 5081 1), Endgame 9(heuristic 7 + 5081 2). 마지막 라운드 보유가 직전 28개에서 줄었다(같은 명령, 같은 seed 범위).
원인은 재지 않았다 — 턴 끝에 새로 생긴 Plot 창에서 heuristic이 battle icon Intrigue를 더 일찍 쓰는지 볼 후보다. 새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 9) | 마지막 라운드 보유 (tip, 17) |
|---|---|---|---|
| random | 0.64 | 0.78 | 0.71 |
| heuristic | 1.00 | 1.00 | 0.24 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.82 / 0.84 |

5081은 옛 규칙(Agent turn이 마지막 효과에서 저절로 닫히던 때)으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게
두는지를 볼 뿐이다.

## 재채굴 (2026-10-02, L2: 자동 처리 → 결정 창)

L2([unavailable-options-plan.md](../unavailable-options-plan.md) 5절, codec v125에 묶음)는 묶음마다 판의 경로를 바꿔 같은 명령으로 세 번
다시 캤다(L1 뒤 106 → A묶음 107 → B묶음 110; C묶음은 움직이지 않음). 최종 **110개** — sandworm 80, 마지막 라운드 보유 21, Endgame 9.
새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 9) | 마지막 라운드 보유 (tip, 21) |
|---|---|---|---|
| random | 0.56 | 0.56 | 0.81 |
| heuristic | 1.00 | 1.00 | 0.24 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.86 / 0.80 |

## 재채굴 (2026-10-02, codec v127: Combat Intrigue 카드 창 뒤의 연속 pass)

Combat Intrigue 카드가 순환 위에 자기 창을 남길 때(Reach Agreement의 Contract 시장, Battlefield Research의 Tech 창)와 Harvest
Cells를 앞면으로 놓을 때 연속 pass를 다시 세고, 창이 닫히면 unit이 없는 좌석을 빼게 되어([OQ-003](../rules/open-questions.md),
codec v127) 그런 판의 경로가 바뀌었다. 파일의 `note` 명령 그대로 두 번 다시 캤다(앞의 둘 뒤 110개 — 보유 19·Endgame 11, Harvest
Cells 뒤 다시). 최종 **110개**(옛 파일과 견주면 그대로 90, 빠진 것 20, 새것 20) — sandworm 80, 마지막 라운드 보유 17(heuristic 16 +
5081 1), Endgame 13. 새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 13) | 마지막 라운드 보유 (tip, 17) |
|---|---|---|---|
| random | 0.57 | 0.54 | 0.88 |
| heuristic | 1.00 | 1.00 | 0.47 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.88 / 0.90 |

## 재채굴 (2026-10-03, codec v129: Distraction·Coercive Negotiation은 배치 뒤에만)

Plot Intrigue Distraction과 Coercive Negotiation이 "이번 turn에 unit 3개 이상 배치한 뒤"에만 낼 수 있는 카드가 되어(사용자
판정 2026-10-03, [OQ-016](../rules/open-questions.md) 재판정, codec v129) 판의 경로가 바뀌었다. 전에는 두 카드를 일찍 내서 앞면으로
남겨 두었고, 그것이 heuristic 판 여럿의 이후 경로를 움직였다. 그래서 커밋된 110개가 복원되지 않았다
(`tests/unit/test_problem_set.py`의 복원 가드가 실패). 파일의 `note` 명령 그대로 다시 캤다(5081은 메인 체크아웃의 절대 경로로;
워크트리에는 `checkpoints/`가 없다). 최종 **99개**(옛 파일 110개) — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유
12(heuristic 11 + 5081 1), Endgame 7(heuristic 6 + 5081 1). 문항별로 옛 파일과 견주면 sandworm 80 → 80, 마지막 라운드 보유
17 → 12, Endgame 13 → 7이다. 포지션 id를 맞춰 보면 그대로(같은 id) 65, 빠진 것 45, 새것 34다. 그대로 65 가운데 선택 번호와
지문까지 같은 것이 35, 같은 seed·자리지만 결정까지의 선택 번호가 달라진 것이 30이다(지문만 다른 것은 없다). 문항별로는 sandworm 59
그대로·21 빠짐·21 새것, 마지막 라운드 보유 5·12·7, Endgame 1·12·6이다. Endgame과 마지막 라운드 보유 문항의 사례가 줄었는데, 원인은 재지 않았다.
새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 7) | 마지막 라운드 보유 (tip, 12) |
|---|---|---|---|
| random | 0.57 | 0.71 | 0.67 |
| heuristic | 1.00 | 1.00 | 0.33 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.83 / 0.79 |

5081은 옛 규칙(두 카드를 일찍 내던 때)으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게 두는지를 볼 뿐이다.

## 재채굴 (2026-10-04, codec v130·관측 v29: 앱 방식 재판정)

사용자가 Steam 디지털판의 처리 방식을 따르기로 한 재판정 다섯 건([OQ-005](../rules/open-questions.md)·OQ-021·OQ-030·OQ-049·OQ-050)
뒤에 5081 판 `s13`의 두 국면(`p1`·`p2`)이 복원되지 않았다. 같은 turn에 supply로 돌아온 troop이 부족분을 채우게 된 것(OQ-030·OQ-049)이
그 판의 앞부분을 바꿨다. scratch 실행에서 보충을 끄면 두 국면이 복원되고, 새 specimen 반환 창(OQ-050)만 끄면 여전히 복원되지 않는다. 파일의 `note` 명령 그대로 다시 캤다(5081은 메인 체크아웃의 절대 경로로). 최종
**119개**(옛 파일 99개) — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 26(heuristic 25 + 5081 1), Endgame
13(heuristic 12 + 5081 1). 포지션 id로 견주면 그대로 95(선택 번호와 지문까지 같은 것 93, 선택 번호만 밀린 것 2), 빠진 것 4(sandworm),
새것 24(sandworm 4, 마지막 라운드 보유 14, Endgame 6)다. 새로 든 보유·Endgame 20개는 모두 그 좌석에 앞면 Objective 카드가 있다.
OQ-005로 Objective 카드가 끝판에 뒤집을 수 있는 전투 카드가 되어(`flippable_battle_card_ids`) 두 탐지기가 더 많은 국면을 잡는다.
새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 13) | 마지막 라운드 보유 (tip, 26) |
|---|---|---|---|
| random | 0.57 | 0.62 | 0.81 |
| heuristic | 1.00 | 1.00 | 0.35 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.92 / 0.88 |

5081은 옛 규칙으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게 두는지를 볼 뿐이다.

## 재채굴 (2026-10-04 둘째 묶음, codec v131·관측 v30)

같은 날 둘째 묶음의 재판정(Emperor track Spy를 자기 turn 안의 의무 행동으로 미룸 — OQ-057 (15), Intrigue trash는 공용 버림
더미로 — OQ-061, deck discard trigger — OQ-013, Interstellar Trade 증분 — OQ-057 (2), Call to Arms 순서 — OQ-012) 뒤에 커밋된
119개 가운데 52개가 복원되지 않았다. 국면마다 처음 갈라지는 곳은 Emperor track Spy가 곧바로 배치 창을 열던 자리다(이제
`place_track_spy`가 다른 효과 곁에 남는다). scratch 실행에서 그 대기를 끄면 52개가 모두 복원된다. 파일의 `note` 명령 그대로
다시 캤다(5081은 메인 체크아웃의 절대 경로로). 최종 **126개**(옛 파일 119개) — sandworm 80(heuristic 40 + 5081 40), 마지막
라운드 보유 35(heuristic 34 + 5081 1), Endgame 11(heuristic 11). 포지션 id로 견주면 그대로 86(선택 번호와 지문까지 같은 것 61),
빠진 것 33, 새것 40이다. 문항별로는 sandworm 71 그대로·9 빠짐·9 새것, 마지막 라운드 보유 13·13·22, Endgame 2·11·9다.
새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 11) | 마지막 라운드 보유 (tip, 35) |
|---|---|---|---|
| random | 0.54 | 0.27 | 0.69 |
| heuristic | 1.00 | 1.00 | 0.34 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.91 / 0.88 |

5081은 옛 규칙으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게 두는지를 볼 뿐이다.

## 재채굴 (2026-10-04 셋째 묶음, codec v132)

턴을 넘기는 카드(Litany Against Fear, Withdrawn)를 그 turn의 첫 행동으로만 쓰게 하자(OQ-095 (6) 보강) 국면 하나
(`deep_desert_summon_into_contest/heuristic/…/s31/p3`)가 복원되지 않았다: 4라운드에 seat 3가 Plot을 먼저 낸 뒤 Litany가 목록에서
빠져 저장된 선택 번호가 다른 행동을 가리켰다. Twisted 카드를 섞지 않는 변경(OQ-097)은 이 문제집을 움직이지 않는다(scratch로 각각
꺼서 확인). 파일의 `note` 명령 그대로 다시 캤다: **126개** 그대로, 125개는 선택 번호와 지문까지 같고 그 한 국면만 같은 id·지문에
선택 번호가 바뀌었다. 채점은 바로 위 둘째 묶음 표와 같다.

## 재채굴 (2026-10-04 넷째 묶음, codec v133)

넷째 묶음(카드 효과 retreat·손실은 배치 한도를 돌려주지 않음 — OQ-029, 줄이 나뉜 Intrigue는 한 줄 이상 써야 끝남 — OQ-058, Usurp로 빌린
카드는 in play가 아님 — OQ-054, OQ-026 보강) 뒤에 커밋된 126개 가운데 85개가 복원되지 않았다(검증 실행에서 OQ-058 변경 하나로 75개, OQ-029
변경 하나로 24개가 움직이고 14개는 어느 쪽으로도 움직인다; Usurp·OQ-026 변경은 이 문제집을 움직이지 않는다). 파일의 `note` 명령 그대로 다시 캤다. 최종 **122개**
(옛 파일 126개) — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 31(heuristic 30 + 5081 1), Endgame 11(heuristic 10 +
5081 1). 포지션 id로 견주면 그대로 108(선택 번호와 지문까지 같은 것 41), 빠진 것 18, 새것 14다. 새 문제집의 채점:

| 에이전트 | sandworm (tip, 80) | Endgame (clear, 11) | 마지막 라운드 보유 (tip, 31) |
|---|---|---|---|
| random | 0.56 | 0.36 | 0.71 |
| heuristic | 1.00 | 1.00 | 0.29 |
| 5081 (`checkpoint:`), 정답률 / 평균 P(정답) | 1.00 / 0.98 | 1.00 / 1.00 | 0.94 / 0.89 |

5081은 옛 규칙으로 학습한 정책이다. 위 수치는 새 규칙의 국면에서 그 정책이 어떻게 두는지를 볼 뿐이다.


## 재채굴 (2026-10-05, Tech 획득 효과 순서)

사용자 요청 OQ-098로 기술 구매 뒤 획득 아이콘을 별도 자유 순서 행동으로 옮겼다(codec v135, 관측 v30 유지).
그만큼 결정·합법 행동 집합이 바뀌어 위의 tips-v1 재채굴 명령을 같은 시드·구성·5081 체크포인트로 다시 실행했다.
결과는 **134개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 38, Endgame 16이며,
`dune-imperium-problems check`가 **134/134** 복원을 확인했다. 앞선 채점 표는 당시 문제집의 결과로 그대로 둔다.

## 재채굴 (2026-10-06, Steam 앱 카드 전수 대조, codec v137)

앱 카드 대조 묶음(Agent box를 아이콘별로 나눔 — Cargo Runner·Tread in Darkness·Industrial Espionage·Stillsuit Manufacturer·Fill Coffers,
Treacherous Maneuver·Subversive Advisor의 Influence, Tactical Option의 0명 후퇴, "up to" 배치의 0, Harvest Cells는 전투 뒤에만,
6인 진영 제외 등) 뒤에 커밋된 134개 가운데 다수가 복원되지 않았다. 브랜치마다 커밋별로 센 결과, 많이 움직인 것은 "up to" 배치의 0(53개),
Harvest Cells를 Combat Intrigue에서 낼 수 없게 한 변경(33개), Tactical Option의 0명 후퇴(12개)와 Agent box 분리(20개)다 — 고를 수 있는
행동이 늘거나 heuristic이 그 카드를 쓰던 국면이 사라졌다. 위 "다시 캐는 명령"을 같은 시드·구성·5081 체크포인트로 다시 실행했다(worker만
4 → 2, 학습 세션과 메모리를 나눠 쓰느라). 결과는 **124개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 33(heuristic 32 +
5081 1), Endgame 11(heuristic 11)이며 `check`가 **124/124** 복원을 확인했다. 포지션 id로 견주면 그대로 98(선택 번호와 지문까지 같은 것
41), 빠진 것 36, 새것 26이다. 채점은 하지 않았다(앞선 표는 당시 문제집의 결과로 그대로 둔다).

## 재채굴 (2026-10-06, 효과 없는 책략 play 금지, codec v138)

사용자 판정(2026-10-06, `[FAQ p. 2]` "To play an Intrigue card, you must meet its conditions and pay its costs." — 효과 중 하나라도 무언가를
바꿀 수 있어야 낸다) 뒤에 커밋된 124개 가운데 74개가 복원되지 않았다(게이트 커밋 `52007a8b` 하나에서). 위 "다시 캐는 명령"을 그대로
다시 실행했다(worker 4). 결과는 **114개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 31(heuristic 29 + 5081 2),
Endgame **3**(heuristic 3)이며 `check`가 **114/114** 복원을 확인했다. 포지션 id로 견주면 그대로 82(선택 번호와 지문까지 같은 것 50),
빠진 것 42, 새것 32다.

Endgame 문항이 11 → 3으로 줄어 따로 확인했다. 같은 명령으로 Endgame 문항만 상한 없이 캐도 이전 엔진(`7a0cdf3e`) 11개, 새 엔진 3개다.
빠진 11개는 모두 그 판이 **이번 판정이 막은 효과 없는 play에서 처음 갈린다** — Tech를 살 수 없는 Rapid Engineering·Battlefield Research,
Agent를 보낸 뒤의 Emperor's Invitation·Twisted Resourceful 아이콘, 못 채운 조건이 없는 Insider Information의 조건 무시, 배치할 병력이 없는
Detonation의 배치(scratch 비교, 판마다 첫 갈림 결정). 옛 heuristic이 그 카드를 효과 없이 내 버리던 판이 사라진 것이고, 기본 지도자로
같은 seed 800판을 돌린 비교에서는 좌석의 첫 Endgame 창에서의 문항 사례가 10 대 9로 비슷했다. 엔진의 Endgame 창 처리는 바뀌지 않았다.
채점은 하지 않았다.

## 재채굴 (2026-10-07, 일반 규칙 대조, codec v139)

일반 규칙 대조 묶음(Combat Intrigue에서 카드를 낸 직후의 pass는 우선권만 넘기고 연속 pass로 세지 않음 — `5654d7f8`,
Reveal-turn Plot은 소유자의 Reveal turn이 끝날 때까지 앞면, Usurp의 Undercover Asset 짝, Chairdog 반환 기록, 덱 크기 공개,
두 개인 더미가 비었을 때의 Gather Intelligence, 혼자 남은 참가자의 pass, Conflict 보상을 순위대로 한 사람씩, 쥔 Contract
아이콘의 소멸 시점) 뒤에 커밋된 114개 가운데 92개가 복원되지 않았다. 옛 파일을 브랜치의 커밋마다(`git archive`로 꺼낸 엔진)
복원해 보면 92개가 모두 `5654d7f8`에서 처음 깨지고, 그때 복원되던 나머지 22개는 이후 어느 커밋에서도 깨지지 않는다. 위
"다시 캐는 명령"을 같은 시드·구성·5081 체크포인트로 다시 실행했다(worker만 4 → 2, 학습 세션과 메모리를 나눠 쓰느라). 결과는
**131개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 40(heuristic 38 + 5081 2), Endgame 11(heuristic 11)이며
`check`가 **131/131** 복원을 확인했다. 포지션 id로 견주면 그대로 63(선택 번호와 지문까지 같은 것 19, 지문은 같고 선택 번호만
바뀐 것 26, 지문까지 바뀐 것 18), 빠진 것 51, 새것 68이다. 문항별로는 sandworm 58 그대로·22 빠짐·22 새것, 마지막 라운드
보유 5·26·35, Endgame 0·3·11이다.

Endgame 문항이 3 → 11로 늘어 따로 확인했다. 같은 heuristic 800판에서 Endgame 문항만 상한 없이 캐면 브랜치 시작
(`381f2e42`) 3개, `5654d7f8` 10개, 브랜치 끝 11개다 — 늘어난 사례는 대부분 그 pass 규칙이 바꾼 판에서 나온다. 채점은
하지 않았다.
`tests/unit/test_problem_set.py`는 고칠 것이 없었다(문항마다 첫 포지션과 표본만 쓴다).

## 재채굴 (2026-10-08, Ghola가 복사한 Long Reach, codec v139)

Ghola를 Long Reach에 graft하면 Ghola box도 Long Reach의 "Choose two"인데(OQ-057 (12)), 두 box가 고른 진영 기록을
같이 써서 Ghola box가 첫 box의 선택을 다시 고를 수 없고 한 번 더 지급했다. graft 전환이 두 box가 모두 Long Reach일 때
그 기록을 box별로 바꿔 끼우게 고치자(`graft.apply_graft_switch`) 커밋된 131개 가운데 하나
(`last_round_hold_battle_icon/heuristic/…/s352/p3`)가 복원되지 않았다 — 그 heuristic 판의 9라운드에 Ghola + Long Reach
(Bene Gesserit·Spacing Guild를 고른 뒤 전환)가 있다. 같은 날의 Long Reach 즉시 지급(OQ-071 재판정)만으로는 131/131이
그대로 복원됐다. 위 "다시 캐는 명령"을 그대로 실행했다(약 4분). 결과는 **130개** — sandworm 80, 마지막 라운드 보유 39,
Endgame 11 — 이고 `check`가 **130/130** 복원을 확인했다. 포지션 id로 견주면 130개가 그대로이고 그 하나만 빠졌다. 채점은 하지
않았다.

## 재채굴 (2026-10-09, 공개 사실로 여는 Conflict 끝 Intrigue 창, codec v141)

Conflict 끝 Intrigue 창을 모두가 아는 사실(Immortality, Conflict의 유닛 3기 이상, 손의 Intrigue 카드 1장 이상, Harvest Cells
사본이 다 공개되지는 않음)로 열게 하자(OQ-103, 사용자 결정 2026-10-09) 낼 카드가 없는 좌석도 "쓰지 않음" 하나뿐인 창을 받고, 카드를
낸 뒤에도 손에 Intrigue 카드가 남아 있으면 창이 열려 있다. 커밋된 130개 가운데 123개가 복원되지 않았다. 옛 창 규칙(낼 수 있는
카드가 있을 때만 열고, 낸 뒤에는 다른 사본을 낼 수 있을 때만 열어 둠)을 scratch로 되돌려 끼우면 130/130이 그대로 복원된다 — 같은
변경의 Earn Any Alliance 완료 시점은 이 문제집을 움직이지 않는다. 위 "다시 캐는 명령"을 그대로 실행했다(worker 4). 결과는
**124개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 27(heuristic 25 + 5081 2), Endgame 17(heuristic 17)이며
`check`가 **124/124** 복원을 확인했다. 포지션 id로 견주면 그대로 67(선택 번호와 지문까지 같은 것 7, 지문은 같고 선택 번호만 바뀐
것 43, 지문까지 바뀐 것 17), 빠진 것 63, 새것 57이다. 문항별로는 sandworm 61 그대로·19 빠짐·19 새것, 마지막 라운드 보유
6·33·21, Endgame 0·11·17이다.

Endgame 문항이 11 → 17로 늘어 따로 확인했다. 같은 heuristic 판을 seed 800-1599로 돌려 Endgame 문항만 상한 없이 캐면 옛 창
규칙 10개, 새 규칙 11개다 — 늘어난 것은 판이 바뀐 데서 온 흔들림이다(heuristic은 행동이 하나뿐인 결정에서도 난수를 쓰므로 창
하나가 그 뒤의 판을 바꾼다). 채점은 하지 않았다. `tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-10, Navigation Chamber 할인은 의무, codec v142)

Navigation Chamber를 가진 좌석이 비용이 있는 칸에서 할인한 placement만 받게 되자([OQ-104](../rules/open-questions.md), 사용자 결정
2026-10-10) 커밋된 124개 가운데 25개가 복원되지 않았다. 정가 placement를 scratch로 되돌려 끼우면 124/124가 그대로 복원된다. 행동
목록이 짧아지면 heuristic이 그 결정에서 뽑는 난수가 바뀌어 판이 갈린다. 위 "다시 캐는 명령"을 그대로 실행했다(worker 4, 5081은 메인
체크아웃의 절대 경로로). 결과는 **126개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 29(heuristic 27 + 5081 2),
Endgame 17(heuristic 17)이며 `check`가 **126/126** 복원을 확인했다. 포지션 id로 견주면 그대로 118(선택 번호와 지문까지 같은 것 99,
지문은 같고 선택 번호만 바뀐 것 16, 지문까지 바뀐 것 3), 빠진 것 6, 새것 8이다. 문항별로는 sandworm 78 그대로·2 빠짐·2 새것,
마지막 라운드 보유 25·2·4, Endgame 15·2·2다. 채점은 하지 않았다. `tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-10, Imperial Privilege의 recall과 card draw 분리, codec v142)

Imperial Privilege의 card draw가 recall에서 떨어져 공간의 따로 된 `cards` 아이콘(`resolve_board_effect(effect=cards)`)이 되자
([OQ-027](../rules/open-questions.md) (d), 사용자 판정 2026-10-10 "4번은 소환과 뽑기가 당연히 두 단계로 나눠야지") Imperial
Privilege 배치 직후의 행동 목록에 뽑기가 하나 더 들고 heuristic은 그것을 Intrigue 교환보다 먼저 고른다. 커밋된 126개 가운데 58개만
복원되었다. 앞 커밋의 엔진(recall이 card도 뽑던 것)에서는 126/126이 그대로 복원된다. 위 "다시 캐는 명령"을 그대로 실행했다. 결과는
**127개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 30(heuristic 28 + 5081 2), Endgame 17(heuristic 17)이며
`check`가 **127/127** 복원을 확인했다. 포지션 id로 견주면 그대로 81(선택 번호와 지문까지 같은 것 58, 지문은 같고 선택 번호만 바뀐
것 13, 지문까지 바뀐 것 10), 빠진 것 45, 새것 46이다. 문항별로는 sandworm 67 그대로·13 빠짐·13 새것, 마지막 라운드 보유
7·22·23, Endgame 7·10·10이다. 채점은 하지 않았다.

## 재채굴 (2026-10-10, Sardaukar 지휘관도 내는 troop 비용, OQ-105, codec v142)

Piter, Genius Advisor의 "Lose a troop" 비용에 지휘관 변형 `lose_agent_card_troop(commanders=1, zone)`이 더해지자
([OQ-105](../rules/open-questions.md), 사용자 판정 2026-10-10 "3은 그럼 통일해야지. 지휘관도 낼 수 있게 해야지") 바로 위 127개
가운데 6개(sandworm `s22/p3`·`s50/p1`, Endgame `s81/p1`·`s347/p0`, 마지막 라운드 보유 `s470/p1`·`s860/p1`)가 복원되지 않았다.
이 문제집의 구성에는 Arrakeen Scouts가 없으므로 같은 판정의 Scouts 비용 두 가지는 판을 바꾸지 못한다 — 움직임은 Piter의 지휘관
선택지에서 온다. 위 "다시 캐는 명령"을 그대로 실행했다. 결과는 **127개**(문항별 수는 바로 위와 같다)이며 `check`가 **127/127**
복원을 확인했다. 포지션 id로 견주면 그대로 126(선택 번호와 지문까지 같은 것 119, 지문은 같고 선택 번호만 바뀐 것 7), 빠진 것 1,
새것 1(둘 다 마지막 라운드 보유)이다. 채점은 하지 않았다.

## 재채굴 (2026-10-10, 공개 선택과 숨은 draw의 분리 첫 묶음, OQ-106, codec v142)

사용자 판정 "그 외에는 전부 나누자. 특히 카드 드로우는 나눠야하는게, 드로우 하기 전에 버림더미 카드를 폐기하고 싶을 수 있잖아."
([OQ-106](../rules/open-questions.md))의 첫 묶음은 커밋 넷이고, 넷 모두 이 문제집의 구성(CHOAM·프로모·Bloodlines·Tech·Immortality)에
나오는 카드나 Leader라 커밋마다 문제집을 다시 캤다. 매번 위 "다시 캐는 명령"을 그대로 실행했다(5081은 메인 체크아웃의 절대 경로로). 채점은
하지 않았다. 각 커밋에서 바로 앞 문제집은 앞 커밋의 엔진에서 전부 복원된다.

- `6947f446`(Urgent Shigawire의 더해진 draw가 배치와 따로): 바로 위 127개 가운데 124개가 복원되었다(Endgame `s644/p3`·`s733/p3`,
  마지막 라운드 보유 `s2327/p2`가 빠짐). 결과는 **125개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 29(heuristic
  27 + 5081 2), Endgame 16(heuristic 16)이며 `check`가 125/125를 확인했다. 그대로 125(선택 번호와 지문까지 같은 것 124, 지문은 같고
  선택 번호만 바뀐 것 1), 빠진 것 2, 새것 0이다.
- `21069cbd`(Cunning·Insider Information의 trash 뒤 draw가 따로): 125개 가운데 102개가 복원되었다. 결과는 **132개** — sandworm
  80(40 + 40), 마지막 라운드 보유 33(heuristic 31 + 5081 2), Endgame 19(heuristic 19)이며 132/132. 그대로 113(같은 것 100, 선택
  번호만 바뀐 것 12, 지문까지 바뀐 것 1), 빠진 것 12, 새것 19다. 문항별로는 sandworm 75 그대로·5 빠짐·5 새것, 마지막 라운드 보유
  23·6·10, Endgame 15·1·4다.
- `9e9fbd71`(Arrakis Planetologist의 Intrigue가 따로): 132개 가운데 97개가 복원되었다. 결과는 **126개** — sandworm 80(40 + 40),
  마지막 라운드 보유 26(heuristic 25 + 5081 1), Endgame 20(heuristic 20)이며 126/126. 그대로 113(같은 것 97, 선택 번호만 바뀐 것
  7, 지문까지 바뀐 것 9), 빠진 것 19, 새것 13이다. 문항별로는 sandworm 76·4·4, 마지막 라운드 보유 21·12·5, Endgame 16·3·4다.
- `2f76372b`(Piter·Reverse Engineering의 비용과 보상이 따로): 126개 가운데 115개가 복원되었다. 결과는 **124개** — sandworm
  80(40 + 40), 마지막 라운드 보유 25(heuristic 24 + 5081 1), Endgame 19(heuristic 19)이며 124/124. 그대로 119(같은 것 115, 선택
  번호만 바뀐 것 4), 빠진 것 7, 새것 5다. 문항별로는 sandworm 79·1·1, 마지막 라운드 보유 22·4·3, Endgame 18·2·1이다.

`tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-10, 공개 선택과 숨은 draw의 분리 둘째 묶음 — 촉발 draw, OQ-106, codec v142)

같은 판정([OQ-106](../rules/open-questions.md))의 둘째 묶음은 다른 인쇄 효과가 촉발한 draw를 소유자의 단계로 남기는 커밋 셋이고,
셋 모두 이 문제집의 구성에 나오는 촉발(Bene Gesserit Influence 4·Imperial Birthright·Tleilaxu track·Sardaukar Soldier·Overthrow,
Hungry for Spice, Unpredictable Foe)이라 커밋마다 문제집을 다시 캤다. 매번 위 "다시 캐는 명령"을 그대로 실행했다(5081은 메인
체크아웃의 절대 경로로). 채점은 하지 않았다. 각 커밋에서 바로 앞 문제집은 앞 커밋의 엔진에서 전부 복원된다.

- `6ec211d8`(촉발된 Intrigue draw가 소유자의 단계로): 바로 앞 124개 가운데 8개만 복원되었다 — Bene Gesserit Influence 4는 거의
  모든 판에 나온다. 결과는 **131개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 32(heuristic 31 + 5081 1),
  Endgame 19(heuristic 19)이며 `check`가 131/131을 확인했다. 포지션 id로 견주면 그대로 72(선택 번호와 지문까지 같은 것 7, 지문은
  같고 선택 번호만 바뀐 것 51, 지문까지 바뀐 것 14), 빠진 것 52, 새것 59다. 문항별로는 sandworm 67 그대로·13 빠짐·13 새것,
  마지막 라운드 보유 2·23·30, Endgame 3·16·16이다.
- `43fa4fa7`(Hungry for Spice의 카드가 소유자의 단계로): 131개 가운데 121개가 복원되었다. 결과는 **134개** — sandworm 80(40 +
  40), 마지막 라운드 보유 35(heuristic 34 + 5081 1), Endgame 19(heuristic 19)이며 134/134. 그대로 127(같은 것 119, 선택 번호만
  바뀐 것 7, 지문까지 바뀐 것 1), 빠진 것 4, 새것 7이다. 문항별로는 sandworm 79·1·1, 마지막 라운드 보유 31·1·4, Endgame 17·2·2다.
- `f8f7e080`(Unpredictable Foe의 Intrigue가 Reveal 대기 목록으로): 134개 가운데 124개가 복원되었다. 결과는 **135개** — sandworm
  80(40 + 40), 마지막 라운드 보유 33(heuristic 32 + 5081 1), Endgame 22(heuristic 22)이며 135/135. 그대로 131(같은 것 123,
  선택 번호만 바뀐 것 7, 지문까지 바뀐 것 1), 빠진 것 3, 새것 4다. 문항별로는 sandworm 79·1·1, 마지막 라운드 보유 33·2·0,
  Endgame 19·0·3이다.

`tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-10, 곧바른 촉발 draw — OQ-106 곧바른 단계, codec v142)

사용자 결정 "가 로 가자"([OQ-106](../rules/open-questions.md) 곧바른 단계)로 Bene Gesserit Influence 4 카드·Imperial Birthright·Overthrow
획득 box·CHOAM Transports의 카드가 그 촉발 바로 다음의 유일한 행동이 되자(자유 순서였던 것은 heuristic이 다른 행동을 먼저 고르기도 했다),
바로 위 135개 가운데 85개만 복원되었다. 두 변경(곧바른 제한과 CHOAM Transports의 보류)을 scratch 사본에서 되돌리면 135/135가 그대로
복원된다. 위 "다시 캐는 명령"을 그대로 실행했다(worker 4, 5081은 메인 체크아웃의 절대 경로로). 결과는 **133개** — sandworm
80(heuristic 40 + 5081 40), 마지막 라운드 보유 31(heuristic 30 + 5081 1), Endgame 22(heuristic 22)이며 `check`가 **133/133** 복원을
확인했다. 포지션 id로 견주면 그대로 126(선택 번호와 지문까지 같은 것 82, 지문은 같고 선택 번호만 바뀐 것 42, 지문까지 바뀐 것 2), 빠진 것
9, 새것 7이다. 문항별로는 sandworm 79 그대로·1 빠짐·1 새것, 마지막 라운드 보유 28·5·3, Endgame 19·3·3이다. 채점은 하지 않았다.
`tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-12, 접합 두 칸을 처음부터 함께 제시, codec v143)

사용자 결정([graft-boxes-plan.md](../graft-boxes-plan.md))으로 graft한 Agent turn이 두 카드의 Agent box를 처음부터 함께 제시하고
(칸 1의 행동은 `box=1`), `switch_graft_card`가 없어지자 커밋된 133개 가운데 105개가 복원되지 않았다. 직전 커밋(`f88cd455`)의 엔진을
`git archive`로 꺼내 복원하면 133/133이 그대로 복원된다. 포지션마다 두 엔진으로 저장된 선택 번호를 따라가며 합법 집합을 견주면,
움직인 106개(복원은 되지만 앞 갈래가 바뀐 1개 포함) 모두 처음 갈리는 결정이 graft한 Agent turn의 결정이다(옛 목록에 switch가 있거나 새
목록에 `box=1` 행이 있다); 나머지 27개는 포지션까지 같다. 위 "다시 캐는 명령"을 그대로 실행했다(worker 4, 5081은 메인 체크아웃의 절대
경로로). 결과는 **129개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 40(heuristic 39 + 5081 1), Endgame 9(heuristic 9)이며
`check`가 **129/129** 복원을 확인했다. 포지션 id로 견주면 그대로 59(선택 번호와 지문까지 같은 것 27, 지문은 같고 선택 번호만 바뀐 것 21,
지문까지 바뀐 것 11), 빠진 것 74, 새것 70이다. 문항별로는 sandworm 58 그대로·22 빠짐·22 새것, 마지막 라운드 보유 1·30·39, Endgame
0·22·9다.

Endgame 문항이 22 → 9로 줄어 따로 확인했다. 같은 명령으로 Endgame 문항만 상한 없이 캐면 seed 0-799는 옛 엔진 22개·새 엔진 9개,
seed 800-1599는 옛 엔진 10개·새 엔진 11개다 — 판이 바뀐 데서 온 흔들림이다(앞선 재채굴에서도 3 ↔ 17 사이를 오갔다). 채점은 하지
않았다. `tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-12, 선택을 제시하는 Agent box가 턴 종료를 막음, codec v144)

선택을 아직 제시하는 Agent box(Stitched Horror의 "Choose two", Beguiling Pheromones, 비용을 낼 수 있는 Piter·Tleilaxu Surgeon·Dissecting
Kit의 화살표와 Tleilaxu Master의 획득)가 남아 있으면 "턴 종료"가 제시되지 않게 되자([OQ-057](../rules/open-questions.md) (1)의
2026-10-12 codec v144 보강, 사용자 지시 "2. 고치자") heuristic이 그 자리에서 턴 종료 대신 box에 답하게 되어, 커밋된 129개 가운데 7개(heuristic의
sandworm 3, 마지막 라운드 보유 4)가 복원되지 않았다. 5081 포지션 41개는 모두 그대로 복원되었다. 위 "다시 캐는 명령"의 heuristic 두 줄을 그
커밋의 트리(`git archive`로 꺼낸 것)에서 worker 3으로 실행했다(90개). **5081 줄은 다시 캐지 않았다**: 이 작업 동안 메인 체크아웃의
`checkpoints/`를 건드리지 않기로 해서(학습이 도는 중), 커밋된 파일의 5081 포지션 41개를 그대로 이어 붙였다 — 41개 모두 새 엔진에서
복원되지만, 5081로 다시 캐면 그 판들의 뒤쪽에서 포지션이 더 나오거나 빠질 수 있다. 결과는 **131개** — sandworm 80(heuristic 40 + 5081
40), 마지막 라운드 보유 41(heuristic 40 + 5081 1), Endgame 10(heuristic 10)이며 `check`가 **131/131** 복원을 확인했다. 포지션 id로 견주면
그대로 127(선택 번호와 지문까지 같은 것 122, 지문은 같고 선택 번호만 바뀐 것 3, 지문까지 바뀐 것 2), 빠진 것 2(마지막 라운드 보유
`s1613/p3`·`s1904/p3`), 새것 4(Endgame `s652/p3`, 마지막 라운드 보유 `s2/p2`·`s369/p1`·`s449/p2`)다. 같은 codec v144의 Urgent Shigawire 변경
([OQ-107](../rules/open-questions.md))은 이 문제집을 움직이지 않는다(그 변경까지 넣은 엔진에서도 131/131). 채점은 하지 않았다.
`tests/unit/test_problem_set.py`는 고칠 것이 없었다.

## 재채굴 (2026-10-14, 선택 효과는 거절 없이 턴 종료로 사라짐, codec v146)

Agent turn의 선택 효과("may", 화살표 비용, 검은 trash 아이콘 `[FAQ p. 3]`)가 거절 없이 제시되고 턴 종료를 막지 않게 되자([OQ-095](../rules/open-questions.md)
(2)의 2026-10-14 보강, 사용자 판정 "선택행동의 경우 거절 버튼이 왜 따로 있는거야 그럼?") heuristic이 고르는 수순이 달라져(거절 대신 턴 종료,
Imperial Privilege의 교환과 회수가 함께 제시됨) 커밋된 131개가 모두 복원되지 않았다(heuristic 90, 5081 41). 위 "다시 캐는 명령" 세 줄을 그
브랜치의 트리에서 worker 4로 실행했고(5081은 메인 체크아웃의 `checkpoints/2026-09-22/exploit/champion-5081.pt`), `check`가 123개 모두 복원했다
(sandworm 80, 마지막 라운드 보유 34, Endgame 9).

같은 날 뒤이은 판정 둘이 문제집을 다시 건드렸다: Lady Jessica의 Other Memories·Tread in Darkness의 trash(의무 draw 옆)에서도 거절을 없앤
것과, Litany Against Fear·Withdrawn을 차례 시작에 단독으로 묻는 엔진 창(`decline_turn_start`)이다. 그 창은 그 카드를 든 좌석에서만 열려
다른 좌석에게 숨은 카드를 알려 주었으므로(결정 창과 공개 이벤트가 나타나는지는 공개 사실로만 정해진다, [lessons](../lessons.md)) 엔진에서
다시 뺐다 — 창이 있던 동안 캔 문제집은 131개(sandworm 80, 마지막 라운드 보유 37, Endgame 14)였고, 창을 뺀 엔진에서는 그 가운데 34개
(heuristic 30, 5081 4)가 복원되지 않는다. 창을 뺀 엔진에서 같은 세 줄과 `check`를 다시 실행했다(worker 4, 5081은 위와 같은 파일). 최종
결과는 **123개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 34(heuristic 33 + 5081 1), Endgame 9(heuristic)이며 `check`가
**123/123** 복원을 확인했다. 포지션 id는 첫 재채굴의 123개와 모두 같다: 109개는 선택 번호까지 같고, 14개(heuristic)는 Other Memories나
Tread in Darkness의 trash가 제시된 자리에서 거절 행이 빠져 선택 번호가 하나씩 밀렸을 뿐 지문과 길이가 같다. 판의 흐름을 바꾼 것은 차례
시작 창이었다. 창이 있던 131개와 포지션 id로 견주면 그대로 110(선택 번호와 지문까지 같은 것 97, 지문은 같고 선택 번호만 바뀐 것 8 — 수가
1~5 줄어든 것 7, 수는 같은 것 1, 5081의 4개 포함 —, 지문까지 바뀐 것 5), 빠진 것 21(Endgame 9, 마지막 라운드 보유 8, sandworm 4), 새것
13(마지막 라운드 보유 5, sandworm 4, Endgame 4)이다. 수가 줄어든 7개 가운데 3개(5081 `s9/p2`·`s11/p3`, heuristic `s12/p1`)는 옛 선택
목록이 이 목록에서 차례 시작마다 창의 거절을 끼운 것과 정확히 같다. 문항의 탐지 조건과 정답은 그대로다; 개수가 오르내린 것은 heuristic
판의 흐름이 바뀌어 그런 장면이 나오는 판이 달라진 탓이다. 채점은 하지 않았다.

## 재채굴 (2026-10-14, Reveal 선택 효과를 Reveal 목록의 줄로, codec v147)

카드마다 띄우던 Reveal 선택 창(`REVEAL_CHOICE` frame)이 없어지고 공개한 카드의 선택 효과가 모두 Reveal frame의 줄로 구매·자동 이득·Plot과
함께 제시되자([OQ-095](../rules/open-questions.md) (7)의 2026-10-14 보강, 사용자 판정 "5.reveal은 바로 다음으로 가자": 미루기·되가져오기
(`defer_reveal_choice`·`resume_reveal_choice`)는 없어지고, 선택 효과는 거절 없이 `finish_reveal`로 사라지며, 같은 행동을 내는 카드는 `source`
인자로 가른다) 커밋된 123개 가운데 36개만 복원되었다(복원되지 않은 87개: heuristic 68, 5081 19). heuristic은 자기가 고를 선택 줄을 구매·이득·
Plot보다 먼저 고르도록 맞췄지만(`turn_end_as_decline`; 옛 엔진이 선택 창부터 답하게 하던 순서) 판은 여전히 움직인다 — 결정마다 받는 목록이
달라졌고, Shadout Mapes·Unswerving Loyalty의 deploy 줄은 `finish_reveal`까지 열려 있어 recruit 뒤에 deploy하게 되며, 선택 줄과 구매가 아닌
다른 줄(표본 반환 등)의 순서도 바뀐다. 5081 판도 Reveal에서 받는 목록이 달라 움직인다. 위 "다시 캐는 명령" 세 줄과 `check`를 그 브랜치
(`reveal-choices`)의 작업 트리에서 그대로 실행했다(worker 4, 5081은 메인 체크아웃의 `checkpoints/2026-09-22/exploit/champion-5081.pt`). 결과는
**116개** — sandworm 80(heuristic 40 + 5081 40), 마지막 라운드 보유 25(heuristic 24 + 5081 1), Endgame 11(heuristic)이며 `check`가
**116/116** 복원을 확인했다. 포지션 id로 견주면 그대로 100(선택 번호와 지문까지 같은 것 30, 지문은 같고 선택 번호만 바뀐 것 65 — 수가 줄어든
것 8, 같은 것 56, 늘어난 것 1 —, 지문까지 바뀐 것 5), 빠진 것 23, 새것 16이다. 문항별로는 sandworm 74 그대로(같은 것 29, 선택 번호만 42,
지문까지 3)·6 빠짐·6 새것, 마지막 라운드 보유 18 그대로(선택 번호만 16, 지문까지 2)·16 빠짐·7 새것, Endgame 8 그대로(같은 것 1, 선택 번호만
7)·1 빠짐·3 새것이다. 5081의 41개는 40개가 그대로(같은 것 22, 선택 번호만 17, 지문까지 1)이고 1개가 빠지고 1개가 새로 났다(`s22/p3` →
`s22/p1`). 같은 브랜치에서 heuristic이 아직 구매를 먼저 고르던 동안 캔 문제집(126개)은 커밋하지 않았다; 5081의 41개는 그것과 모두 같다.
문항의 탐지 조건과 정답은 그대로다; 개수가 오르내린 것은 판의 흐름이 바뀌어 그런 장면이 나오는 판이 달라진 탓이다. 채점은 하지 않았다.
`tests/unit/test_problem_set.py`는 고칠 것이 없었다(옛 문제집으로 실패하던 7개는 모두 그 문제집이 복원되지 않은 탓이었고, 새 문제집으로
20개 모두 통과한다).

## 재채굴 (2026-10-17, 차례 안 연구 보너스·선택 trash를 차례의 줄로, 정리-2b, codec v149)

소유자 자신의 turn 안에서 열리던 연구 보너스 창과 선택 trash 창이 없어지고 그 효과가 turn frame의 줄로 거절 없이 기다리자
([composed-effects-plan.md](../composed-effects-plan.md) 5절 "정한 규칙 판단" 2번, [OQ-095](../rules/open-questions.md) (2)) 커밋된 116개
가운데 68개가 복원되지 않았다(연구 보너스만 바꾼 정리-2b-1 커밋 `398b3873`에서 이미 36개). 정리-2a 커밋(`93c8446b`)의 소스로 116개의 수순을
다시 두어 이 엔진과 견주면 갈라지는 80개 모두 처음 다른 결정이 옛 엔진의 차례 안 창이었다(선택 trash 54, 연구 보너스 26) — 다른 규칙이 판을
옮기지 않았다. 위 "다시 캐는 명령" 세 줄과 `check`를 `cleanup2` 작업 트리에서 그대로 실행했다(worker 4, 5081은 메인 체크아웃의
`checkpoints/2026-09-22/exploit/champion-5081.pt`). 결과는 **121개** — sandworm 80, 마지막 라운드 보유 29, Endgame 12이며 `check`가
**121/121** 복원을 확인했다. 포지션 id로 견주면 그대로 85(같은 것 36, 지문은 같고 선택 번호만 바뀐 것 43, 지문까지 바뀐 것 6), 빠진 것 31,
새것 36이다. 문항의 탐지 조건과 정답은 그대로다. 채점은 하지 않았다. 정리-2의 남은 하위 단계(2b-3·2b-4 등)가 결정을 더 바꾸면 그때 다시 캔다.
