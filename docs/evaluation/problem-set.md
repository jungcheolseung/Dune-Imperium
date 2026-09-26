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
- **채점**(`answer`): 포지션마다 새 에이전트를 만들어 그 결정을 묻는다. 모든 에이전트는 "고른 행동이 옳은가"로, 네트워크
  (`checkpoint:`)는 추가로 **옳은 답들의 softmax 확률 합**(`p_right`)으로 채점한다. `search:`·`rollout`은 상태를 받는 탐색으로 답한다.

```bash
uv run dune-imperium-problems mine --agents heuristic --games 400 --choam --bloodlines --tech-module \
    --immortality --promo-cards --workers 4 --max-per-problem 40 --out <suite.json>
uv run dune-imperium-problems score --agents heuristic,random,checkpoint:<path> [--json answers.json]
```

`--append`는 다른 테이블의 포지션을 같은 파일에 더한다(포지션 id에 생성 테이블 이름이 들어간다).
`check`는 문제집의 모든 포지션을 복원해 본다(규칙을 고친 뒤 먼저 돌린다; 약 40초). 포지션 하나를 복원하는 데 약 0.3초가 든다.

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
