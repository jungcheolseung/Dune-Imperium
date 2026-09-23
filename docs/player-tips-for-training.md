# 사람의 실전 팁을 학습에 쓰는 법 — 논의 기록

2026-09-22, WSL 노트북 세션. **논의만 했고 코드 변경은 없다.** 사용자 질문 두 개에서 시작했다: "휴리스틱과
rollout은 어떻게 구현돼 있나", "친구들과 여러 번 두며 느낀 팁이나 행동의 중요도가 학습에 도움이 될까".
다른 기기에서 이어가기 위해 남긴다. 같은 날 밤 Mac mini에서 이어 갔다(6절: 사용자 답·팁 두 개·census·heuristic
A/B — 여전히 저장소 코드 변경 없음). 2026-09-23 WSL 노트북에서 커뮤니티 팁 38개를 분류하고 그 측정 도구
`scripts/ab/tip_census.py`를 넣었고, 같은 날 가져온 5081로 census를 냈다(7절). 이어갈 때는 **7.8 "다음"**부터 시작한다.

## 1. 두 baseline의 구조 (요약)

**`HeuristicAgent`** ([`agents/heuristic_agent.py`](../src/dune_imperium/agents/heuristic_agent.py)) — 1-ply 점수표 정책.

- `score_action`이 합법 행동 **하나만 보고** 점수를 매긴다: 행동 종류별 고정 점수(`_ACTION_SCORES`), `agent_turn`은
  4 + 보드 칸 보너스(`UPRISING_SPACE_BONUSES`), 구매는 **3 + 인쇄 비용**(그래서 늘 가장 비싼 카드를, 패스 −3보다
  먼저 산다), 병력 배치는 **배치 수**(늘 최대), 거절 −2·패스 −3·회수 −10.
- 최고점 동점만 `PlayerView`를 보고 가족 안에서 좁힌다(Influence 2·4 도달, 가장 싼 카드 trash, 같은 비용이면 Reveal
  가치) → seeded RNG 추첨 → 같은 칸이면 Reveal box 손실이 가장 작은 카드로 교체.
- **한계**: 점수 자체는 상태(자원·라운드·전투 판세·상대)를 보지 않는다. "3라운드 전에는 전투를 버린다" 같은
  **조건부 팁은 지금 구조로 표현할 수 없다.**

**`RolloutAgent`** ([`agents/rollout_agent.py`](../src/dune_imperium/agents/rollout_agent.py)) — determinized flat Monte Carlo(PIMC).

- 결정마다 휴리스틱 점수 상위 **3개** 후보 × **4개** 세계. 세계는 `determinize`가 자기 좌석이 모르는 존(상대 비공개
  손패·덱, 상대 Intrigue, Imperium·Contract·Conflict 덱, Tech stack 아래)만 다시 섞어 만든다.
- 후보마다 그 세계에서 **4좌석 모두 휴리스틱**으로 **이번 라운드 끝까지** playout하고, `position_value`(끝났으면
  순위 100/70/40/10, 아니면 `player_value` − 상대 평균; 10·VP + 1.5·Influence + … + 0.1·덱 인쇄 가치)로 읽는다.
  후보들은 같은 세계·같은 chance/정책 seed를 쓴다(공통 난수). 결정당 playout 12회, 약 80 ms.
- 성능: 휴리스틱 3명 상대 base 54%, 전 확장 60%(기대 25%). 같은 예산이면 세계 수가 이기고 후보 폭·horizon은
  노이즈만 늘린다([evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md) 13·15절).
- **한계**: 트리 없음(1-ply), strategy fusion, 휴리스틱의 사전을 playout으로 물려받음, 1라운드 horizon이라
  덱빌딩 같은 장기 가치는 `player_value`의 손 가중치에만 기댄다.

**학습과의 관계.** 학습(REINFORCE/PPO, masked MLP)은 pure self-play라 둘 다 쓰지 않는다 — 휴리스틱은 학습 중
평가 상대, rollout은 사후 대회·서버 AI 좌석용이다. 학습된 정책은 휴리스틱 3명 상대 약 88~92%, rollout 1명 대
체크포인트 3명에서 rollout 9.4%로 **둘 다 압도한다**([evaluation/m10-2026-09-22.md](evaluation/m10-2026-09-22.md)).
"rollout"이라는 이름은 이 저장소에서 탐색 에이전트를 뜻한다(RL의 "PPO rollout" = 학습 데이터 수집은 여기서
self-play collection이라 부른다).

## 2. 출발점: 사람 직관은 가설이다

이 저장소는 사람 직관을 코드에 넣었다가 측정으로 뒤집은 적이 이미 두 번 있다.

- **보드 칸 표**: 환산표(rubric, "Influence 1 = 0.45 …")대로 매긴 표보다 세 칸을 바닥으로 내린 표가 base +9.8%p,
  이어 Imperial Basin 0.3·Arrakeen 1.2로 나눈 표가 중앙값 표보다 base +17.2%p였다
  ([evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 18절).
- **카드 구매**: 휴리스틱의 "3 + 비용" 사전은 94% 산다. 학습된 정책은 합법 구매 기회의 14~29%만 사고 덱 약
  9.25장으로 끝나며, 구매를 강제하면 **−17%p**다.

그래서 팁은 **정답이 아니라 측정할 가설**로 다룬다. 재는 도구는 이미 있다(2:2 미러 + `--matches` +
`scripts/ab/paired.py`).

## 3. 팁을 넣을 수 있는 곳 (기대 가치 순)

| # | 어디에 | 방법 | 판단 |
|---|---|---|---|
| 1 | **진단** | 사용자가 `checkpoint:` 좌석과 직접 두거나 전 좌석 AI 관전(2026-09-20)으로 보며 "실전에서 말이 안 되는 수"를 짚는다 | **가장 값어치 큼**, 비용 거의 0 |
| 2 | **평가 문제집** | "이 상황에서 X가 명백히 옳다"는 포지션 모음, 체크포인트마다 정책이 X에 주는 확률을 잰다 | 큼 |
| 3 | **League 상대** | 특정 전략을 흉내 내는 스타일 봇(전투 올인, Spy·Intrigue, 한 Faction 몰빵 Alliance 등) | 중간~큼 |
| 4 | **입력 표현** | 팁이 말하는 "봐야 할 양"을 요약 feature로 | 중간, A/B 필요 |
| 5 | 모방학습 | 사람 기보로 정책을 흉내 | 지금은 낮음 |
| 6 | 보상 shaping | "Influence를 올리면 +0.1" 같은 중간 보상 | **비추천** |

1. **진단.** 짚은 수는 셋 중 하나로 이어지고 모두 이득이다: 엔진 규칙 결함(학습 정책이 엔진 결함을 찾아낸 전례가
   있다), 정책의 약점(→ 3의 상대), 사람 직관의 오류.
2. **평가 문제집.** tactics suite와 같은 발상. 이 저장소의 가장 큰 병목이 승률 잡음(10%p에 1,400경기, 3%p에 약
   15,800경기)이라 **분산이 작고 몇 초면 끝나는 지표**가 값지다. 명백한 경우만 넣고, 정책과 답이 다르면 자동 오답이
   아니라 조사 대상으로 본다. **학습 목표로 쓰지 않는다**(쓰는 순간 지표가 망가진다).
3. **League 상대.** 핸드오프의 현재 다음 작업이 "좌석 상대 다양화"이고 병목은 "배울 상대가 없다"다. 약한 봇도
   다양성은 준다. 1에서 찾은 약점을 찌르는 봇이 특히 값지다. 조건부 팁은 상태를 보는 점수 함수가 먼저 필요하다.
4. **입력 표현.** 관측은 카드를 정체성 개수로만 준다(4,327 int). 손패 Persuasion 합계, 보낼 수 있는 Agent 아이콘,
   이번 전투의 strength 차, 10 VP까지 남은 거리 같은 요약값은 "무엇을 할지"가 아니라 "무엇을 볼지"만 알려 준다.
   핸드오프가 꼽은 "표현력" 지렛대와 같은 방향이다. 관측 버전이 오른다.
5. **모방학습.** 서버의 저장본은 전체 `GameReplay`라 기술적으로는 가능하지만, 수십 판은 수천 결정뿐이고
   (학습은 수백만) 저장본은 codec 버전이 정확히 맞아야 한다. 초기 정책 만들기 단계는 이미 지났다. 사람 기보는
   **사람 대 정책 평가**에 쓰는 편이 낫다.
6. **보상 shaping.** 정책은 사람이 매긴 대리 지표를 최적화하고, 이미 이긴 편향된 사전을 다시 주입하게 된다.
   최적해를 보존하는 potential-based shaping만 안전한데 value head가 이미 그 역할이다. 순위 보상도 효과가 없었다
   ([evaluation/m10-2026-09-22.md](evaluation/m10-2026-09-22.md)).

원칙: 사람 지식을 **목표**(보상)에 넣으면 성능의 천장이 되고, **발판**(진단·평가·상대·표현)으로 쓰면 돕는다.
연산이 작은 이 환경(Mac mini, iteration당 32판)에서는 발판의 값어치가 크다.

## 4. 열린 갈래 (첫 답에서 꺼낸 것)

- 휴리스틱을 고칠 것인가: 사람 상대 AI로서의 휴리스틱과 "자"로서의 휴리스틱은 목적이 다르다.
- rollout의 playout 정책을 학습된 네트워크로(또는 value head로 playout 대체) — AlphaZero·expert iteration 방향.
  네트워크 + 탐색이 네트워크 단독보다 강하면 그것이 새 학습 신호이자 새 상대다.
- 1-ply rollout을 ISMCTS(정보 집합 MCTS)로 넓히는 것이 이 게임에서 값어치가 있는가.

## 5. 남은 질문 (사용자 몫)

1. **실전에서 카드를 거의 사지 않고 덱 9~10장으로 이기는 것이 말이 되는가?** "말도 안 된다"면 엔진 규칙 오류나
   AI끼리만 통하는 착취 전략을 의심해 파 본다. "어느 정도 통한다"면 휴리스틱의 구매 사전을 고칠 근거다.
   → **답했다(6.1).**
2. **실전 팁·행동 중요도 목록.** 받으면 팁마다 3절의 1~4 중 어디에 넣을지와 검증할 측정을 정한다.
   → **진행 중**: 팁 1(sandworm, 6.3), 팁 2(진영 시너지 구매, 6.6). 커뮤니티 목록(6.7)은 7절에서 경로·측정 열로 분류했다.

## 6. 이어간 기록 (2026-09-22 밤, Mac mini)

저장소 코드는 여전히 바뀌지 않았다. 측정은 전부 스크래치 도구로 했고 원자료는 git 무시
`ab-runs/2026-09-22-thin/`(이 Mac)에 있다: census `deck_profile.py`·`analyze_profile.py`와 행(`census/`), heuristic
변형 `pypath/thinvariants.py`, 셀 스크립트·로그(`run_cells*.sh`, `cells.log`), 경기별 행(`*.jsonl`), 커뮤니티 팁
원자료(`community-tips.json`). A/B는 다른 세션이 같은 체크아웃을 쓰고 있어 **HEAD `1c09a58`의 `src/` 사본**으로
돌렸다(대조군이 도중에 바뀌지 않도록). 사용자의 평소 구성은 **CHOAM + Bloodlines + Tech + Immortality**다 —
A/B의 "평소 구성" 축이 이것이고, census는 정책의 학습 구성(여기에 promo)이다.

### 6.1 질문 1의 답 — "얇고 **강한** 덱"

사용자: 적절히 사면서 시작 카드를 잘 폐기해 덱이 얇을 때 승률이 높았다. 그냥 안 사는 것은 아니다 — 비싼 카드는 대개
성능이 좋으니 그것으로 시작 카드를 대체하고, 덱을 얇게 유지해 좋은 카드를 자주 쓰는 것이 좋다. 이것을 가설
**H-deck**로 부른다. m10 문서 4절의 구매 강제 탐침(`net_buy_always`)은 "아무 카드나 산다"라서 이 가설을 시험하지 않았다.

### 6.2 5081의 덱은 얇은 **시작** 덱이다 (census, 12 seed)

| | 5081 4명 | heuristic 4명 | 5081 1 + heuristic 3의 5081 |
|---|---:|---:|---:|
| 판 끝 덱 = 시작 카드 + 산 카드 | 10.85 = **7.31** + 3.54 | 24.67 = 7.25 + 17.42 | 13.00 = 7.50 + 5.50 |
| 판당 구매 (그중 7라운드 이후) | 3.77 (**2.67**) | 17.85 (7.21) | 6.10 (2.52) |
| 산 카드 평균 비용 / 가장 비싼 합법 카드를 고른 비율 | **2.77 / 39%** | 3.67 / 100% | 3.10 / 71% |
| 판당 폐기한 시작 카드 | 2.56 | 2.62 | 2.38 |
| VP: 영향력 트랙 / 동맹 / 전투(×1·×2·선택형 보상) | 3.02 / 0.81 / 1.62 | 2.50 / 0.79 / 1.67 | 3.06 / 1.50 / 3.36 |

정책은 **보드로 이기고 덱은 거의 시작 덱 그대로다**. 사는 카드는 막판의 싼 카드다. 폐기 대상은 Seek Allies(매 판),
Convincing Argument, Reconnaissance, Dagger 순이다. H-deck의 덱(비싼 카드로 시작 카드를 대체)은 정책도 heuristic도 두지
않는다. 착취자 실험(m10 문서 11절)이 "다양성은 다른 분지에서"라고 했던 그 후보다.

### 6.3 팁 1 — sandworm: 정책은 이미 배웠다

사용자: 전투 위주로 가려면 Fremen 2를 빨리 달성해 Sietch Tabr에서 Maker Hooks를 얻고, sandworm으로 전투 보상을 두 배로
받는다. 규칙 근거: Sietch Tabr는 Fremen Influence 2 이상, 선택 (a)가 Maker Hooks + troop 1 + water 1
`[Board Guide p. 2]`; 자기 sandworm이 Conflict에 있으면 보상 두 배 `[Main p. 14]`; Deep Desert는 Hooks가 있으면
sandworm 2 `[Board Guide p. 1]`.

| 같은 정책 4명, 12 seed | 5081 | heuristic |
|---|---|---|
| Fremen 2 도달 (좌석 비율, 평균 라운드) | 83%, 3.6 | 77%, 5.1 |
| Maker Hooks | 77%, 4.5 | 52%, 6.4 |
| 판당 소환 sandworm / 두 배 받은 보상 | **2.27 / 1.29** | 0.94 / 0.62 |

5081을 heuristic 셋과 앉히면 Deep Desert를 판당 2.90번 가고 두 배 받은 1위 보상이 0.88번(heuristic 0.12)이다. 5081끼리
둔 판의 1위 좌석은 나머지보다 Fremen 2가 이르고(2.8 대 3.9라운드) sandworm(3.25 대 1.94)과 두 배 보상(2.08 대 1.03)이
많다 — 1위 12좌석의 상관관계다. **팁과 정책이 서로를 확인한다.** 쓸 곳: heuristic(사람 상대 AI)이 이것을 약하게 하므로
개선 후보, 그리고 평가 문제집 문항("Hooks 보유, Shield Wall에 막히지 않은 이길 만한 전투, 빈 Deep Desert → 소환").

### 6.4 H-deck의 heuristic A/B — 비용으로 거르는 얇은 덱은 진다

변형은 비용 N 미만의 카드를 덱에 들이지 않는다(그 획득 점수를 pass 아래로). heuristic은 원래 가장 비싼 카드를 사고
(3 + 비용) 폐기 기회는 늘 잡으므로(폐기 1.0 > 거절 −2.0), 갈리는 축은 "무엇을 덱에 들이나"뿐이다. 점검: 문턱 0 변형이
heuristic과 8판 5,440결정이 같고, census로 덱이 실제로 줄었다(문턱 4/5/6: 13.0/12.4/11.9장, 문턱 5 + Tleilaxu 안 삼:
9.31장 = 시작 7.59 + 산 카드 1.72, 평균 비용 6.0). 셀마다 2:2 미러 500 seed = 1,000경기, `paired.py`, 실패 0.

| 변형 vs heuristic (승률 차, %p) | 평소 구성 블록 1 / 2 (/ 3) | 기본판 |
|---|---|---|
| 문턱 4 | −11.6 / −5.0 | −20.2 |
| 문턱 5 | −21.0 / −18.0 | −36.0 |
| 문턱 6 | −28.4 / −29.4 | −56.2 |
| 문턱 5 + Tleilaxu 안 삼 | −7.0 / +7.8 / +1.6 → 합쳐서 **+0.8 [−2.7, +4.3]** | (−36.0, 기본판엔 Tleilaxu 없음) |
| Tleilaxu만 안 삼 (문턱 없음) | +21.4 / +19.2 / +24.8 → 합쳐서 **+21.8 [+18.4, +25.1]** | (Immortality 축 +21.6) |
| **직접: 문턱 5 + Tleilaxu 안 삼 vs Tleilaxu만 안 삼** | **−17.8 [−23.6, −12.0]** (블록 1) | |

- 문턱을 올릴수록 **단조롭게** 진다(두 구성, 두 블록). 같은 조건의 대조군과 직접 맞붙여도 −17.8%p다. 순위·VP 마진도 같은 방향이다.
- "문턱 5 + Tleilaxu 안 삼"의 동률은 두 효과의 상쇄다(얇은 덱 약 −18, Tleilaxu 안 삼 약 +22). 이 팔의 블록 1·2는 부호가
  반대로 각각 "resolved"였다 — 블록 하나의 구간을 과신하지 말 것, 그래서 셋째 블록을 더해 합쳤다.
- 기제 정황: 얇은 변형은 영향력 트랙 VP가 2.5 → 2.1~2.2로 준다. 커뮤니티 팁 "초반 Faction 접근 카드 1~2장은 사라"
  (6.7)와 같은 방향이다.
- **읽는 법**: "사람의 H-deck이 틀렸다"가 아니라 "비용으로 거른 얇은 덱은 덱에 맞춰 두지 못하는 1-ply 플레이어에게 손해"다.
  사람의 기준은 비용이 아니라 **기능**(접근 아이콘·진영 시너지 — 팁 2)일 수 있다. 정책 틀의 시험(비싼 카드를 살 수 있으면
  사게 덮어쓴 5081 대 5081)은 아직이다.

### 6.5 옆길: heuristic의 Tleilaxu 구매는 약점이다 (+21.8%p)

Tleilaxu 카드를 사지 않는 것만으로 heuristic이 평소 구성에서 **+21.8%p [+18.4, +25.1]**(3블록 3,000경기, 블록마다
+19 ~ +25), Immortality 축에서 +21.6%p다. 규칙: specimen은 supply의 troop을 Axolotl tanks에 둔 것이고 Tleilaxu 카드
획득이나 specimen 비용에 쓴다 `[Immortality p. 8]`. census(16 seed)에서 이 변형은 전투를 판당 2.33번 이겨 heuristic의
1.78번보다 많다 — specimen을 Reclaimed Forces(troop 2 recruit) 같은 데 쓰는 것으로 보이나 **기제는 미검증**이다.
heuristic은 사람 상대 AI이자 `rollout`의 playout 정책이라 값어치가 크다. 채택은 heuristic A/B 절차(축별, 용량 — 0이 아니라
점수 인하, 이식 후 결정 단위 동일성, 옛 동작 고정)를 밟는 **별도 작업 단위**이고 사용자 결정이다. M10 평가의 heuristic
자도 바뀌므로 옛 heuristic을 registry 이름으로 고정해야 한다.

### 6.6 팁 2 — 진영 시너지로 산다

사용자: 카드마다 시너지가 있다. Fremen Bond 카드를 샀다면 Fremen 카드를, "in play에 Bene Gesserit 카드가 있으면" 효과를
샀다면 Bene Gesserit 카드를, Spacing Guild·Emperor 관련 효과도 마찬가지로 그 진영 카드를 사면 좋다. 규칙: Fremen Bond는 다른
Fremen 카드가 하나 이상 in play일 때 쓸 수 있고 두 Bond 카드는 서로를 활성화한다 `[Main p. 20]`; 엔진의 판정은
`rules/card_bonds.py`(같은 진영의 **다른** 카드)이고 카드의 진영 소속은 `personal_card_for_instance(...).factions`다.
Bond 조건은 `PersonalCardBond`(`content/uprising/types.py`)와 효과 이름의 `_bond` 접미사로 전사돼 있다.

스크래치 표(`pypath/synergy.py`: Bond 요구·진영별 공개 수 세기·`_<진영>_bond` 효과)로 보면 같은 진영의 다른 카드가 있어야
값을 하는 카드는 Fremen 11종, Bene Gesserit 7종, Emperor 1종(Sardaukar Coordination)이고 전사된 카드 중 Spacing Guild는
없다. "Bond 짝" = 그런 카드와 그 진영의 다른 카드가 함께 덱에 있는 것.

| census (`synergy_census.py`) | 판당 산 시너지 카드 | 구매 중 Bond 짝을 완성한 비율 | 판 끝 Bond 짝 |
|---|---:|---:|---:|
| 5081 4명 | 0.31 | 4% | **0.12** |
| heuristic 4명 | 2.12 | 17% | 2.04 |
| heuristic + 짝 보너스 +2 (heuristic과 2:2) | 2.41 | 25% | 2.33 |
| 얇은 덱 + 짝 예외 (문턱 5 + Tleilaxu 안 삼, 짝이면 문턱 무시) | 0.33 | 27% | 0.31 |

| heuristic A/B (2:2, 셀당 1,000경기, 실패 0) | 평소 구성 2블록 합침 | 기본판 |
|---|---|---|
| 짝이면 구매 점수 +1 vs heuristic | −0.8 [−4.3, +2.7] | −1.4 |
| 짝이면 구매 점수 +2 vs heuristic | −2.6 [−6.2, +1.2] | −0.8 |
| 얇은 덱 + 짝 예외 vs 얇은 덱 (직접) | +0.9 [−1.7, +3.5] | |

- **정책은 진영 시너지를 거의 만들지 않는다**(판 끝 Bond 짝 0.12). 진단으로는 새 사실이다.
- heuristic 틀에서는 **효과가 잡음 안**이다. 두꺼운 덱(24장)에서는 짝을 늘려도(1.56 → 2.33) Bond는 "다른 카드가 **in play**"여야
  하므로 같은 라운드에 함께 나올 확률이 낮다는 해석과 맞는다. 얇은 덱에서는 구매 자체가 판당 2장 남짓이라 짝이 0.31쌍밖에
  생기지 않아 **시험이 약하다**. heuristic은 짝 카드를 함께 쓰려고 손패를 운용하지도 않는다.
- 남은 시험: Bond 발동을 직접 세기(발동 횟수와 그때 얻은 값), 그리고 정책 틀의 탐침. 팁 1·2는 서로 맞물린다 — 시너지는
  얇은 덱이라야 함께 나오고, 얇은 덱은 시너지(기능)로 골라야 한다.

### 6.7 커뮤니티 팁 — 수집·출처 대조 완료, 사용자 대조 대기

주제별 목록은 [evaluation/community-tips-2026-09-22.md](evaluation/community-tips-2026-09-22.md)에 한글로 옮겼다(원자료
JSON은 git 무시 `ab-runs/2026-09-22-thin/community-tips.json`, 이 Mac에만 있다).
workflow가 BGG·reddit·Dire Wolf 디자인 다이어리·Steam 가이드 등에서 49개(덱빌딩 13, 일반 36)를 모으고, 별도 검증자가
인용 페이지를 다시 열어 대조했다: 예 17, 부분 22, 아니오 9, 접속 불가 1(BGG가 직접 fetch를 403으로 막아 일부는 JSON API로
읽었다). 다수가 base Dune: Imperium 자료라 Uprising 전이 여부를 표시해 두었다. 사용자가 자기 팁을 먼저 적은 뒤(앵커링
방지) 대조한다. 덱빌딩 쪽 요지: 숙련자 한 명의 추정으로 한 판에 새 Imperium 6~7장을 사고 폐기는 몇 장(BGG 3423540),
폐기의 한계효용은 체감하고 5장 넘게 폐기하는 일은 드묾, 초반 Faction 접근 카드 1~2장은 우선 구매.

### 6.8 다음

- 사용자: 팁 더 적기 → 커뮤니티 목록 대조. H-deck에서 "비싼 카드"의 기준이 비용인지 기능인지.
- 팁 2: Bond 발동 직접 세기(6.6). heuristic 변형 A/B는 끝났다(잡음 안).
- 정책 틀의 H-deck 탐침: 비싼 카드(비용 5 이상)를 살 수 있으면 사게 덮어쓴 5081 대 5081, 2:2(팔당 약 20분).
- heuristic Tleilaxu 채택(6.5, 별도 작업 단위, 사용자 결정).
- 평가 문제집에 sandworm 문항(6.3).

## 7. 커뮤니티 팁을 가설로 — 분류와 tip census (2026-09-23, WSL 노트북)

사용자가 Mac mini의 커뮤니티 팁 JSON을 [evaluation/community-tips-2026-09-22.md](evaluation/community-tips-2026-09-22.md)로
옮겨 온 뒤 이 노트북에서 이어 갔다. 이 노트북에는 5081 체크포인트도 6절의 스크래치 도구(`ab-runs/2026-09-22-thin/`)도 없어서,
**정책 측정은 하지 않았고** 대신 (1) 38개 팁의 규칙 확인과 분류, (2) 그 측정을 한 명령으로 돌리는 저장소 도구, (3) 그 도구의
heuristic 기준값을 만들었다. 5081 쪽 숫자는 Mac mini에서 같은 명령으로 낸다(7.5).

### 7.1 방법

- **분류**: workflow로 팁 묶음(덱빌딩 / 전투 / 영향력·Spy·계약 / 템포·Tech·끝내기)마다 Sonnet 분류자 하나와, 그 결과를
  반박하도록 한 Opus 검증자 하나. 검증자는 규칙 주장마다 `docs/rules` 줄과 엔진 코드를 직접 열고, 필요하면 작은 게임을
  돌렸다. 분류자가 "불일치"로 올린 2건(C1.8 Swordmaster 비용, C7.1 Tech 지속 비용)은 **둘 다 검증자가 반박**했다(분류자가
  `docs/rules`를 열지 않고 적었다).
- **도구**: 수집기 4개를 Sonnet 구현자 넷이 병렬로 쓰고, Opus 검증자가 엔진의 emit 지점을 전수 grep·손 추적·변조 실험으로
  반박한 뒤, 증명된 결함만 구현자가 고쳤다. 검증이 잡은 결함 중 숫자를 틀리게 하던 것: sandworm 소환 세 경로 중 둘 누락,
  아무도 안 들어간 Conflict 누락, Commander **손실**을 퇴각으로 셈, Endgame 시작 VP 스냅숏이 Tech의 Endgame VP를 이미 포함,
  Seek Allies가 아닌 의무 자기 폐기(Dangerous Rhetoric·Subversive Advisor)를 "선택 폐기"로 셈, Bond 짝을 카드 자신의 진영으로
  판정(Southern Faith 등은 Bene Gesserit 짝이 필요) — 모두 고쳤고 되돌리면 실패하는 테스트가 붙었다.

### 7.2 규칙 확인 — 엔진 불일치 0

규칙을 담은 팁(C1.6 전제, C1.9, C2.3, C2.4, C2.6, C3.3, C3.4 전제, C4.1, C4.2, C5.1, C6.3, C7.1, C7.2, C8.2)은 모두 `docs/rules`와
엔진이 일치했다. 남은 것:

- **테스트 공백 1건 메움**: Influence 4 보너스는 4 아래로 내려갔다가 다시 도달하면 다시 받는다 `[Main pp. 4, 7 board
  artwork]`(`rules/uprising-systems.md`). 엔진은 이미 그렇게 했지만(`rules/influence.py`에 "한 번만" 가드가 없다) 떨어졌다
  다시 오르는 경우를 고정한 테스트가 없었다 → `test_reaching_four_again_after_a_drop_pays_the_track_bonus_again`(가드를 넣은
  소스 사본에서 실패함을 확인).
- **문서 오기 정정**: 커뮤니티 문서 C2.7의 "(Uprising에는 Heighliner가 없다)"는 틀렸다 — Heighliner는 spice 5, Spacing Guild
  Influence 1, troop 5 recruit `[Board Guide p. 2]`(`rules/board-spaces.md`). 6.7의 옮겨 적기에서 생긴 잘못이다.
- **해당 없음**: Mentat은 Uprising에 없다 `[Main pp. 5, 6]`(C2.5; "상대가 다 둔 뒤 투입"의 지렛대는 Swordmaster의 셋째
  Agent가 비슷하다). C2.8의 Ambush·Private Army는 기본판 카드다. C1.3의 카드들은 Uprising 시작 덱에도 그대로 있다 `[Main p. 3]`.
- 참고 사실: Uprising의 2·3위 보상 가운데 troop **만** 주는 행은 없다 — C2.2의 "troop 1"은 보상이 아니라 투입량이다.
  Imperium 덱은 기본 65 → 평소 구성 131 → 학습 구성 135장이다(C1.10).

### 7.3 팁 → 경로 → census 열

| 팁 | 경로 | census 열 (접두사는 수집기) |
|---|---|---|
| C1.1 판당 6~7장 구매, 반응적 | census | `deck.buys`, `buys_r1_3/r4_6/r7p`, `buys_by_payment` |
| C1.2 약한 시작 카드 없애기 | census (6.1~6.4와 같은 축) | `deck.trash_starters`, `end_starters`, `end_bought` |
| C1.3 폐기 순서(합의 없음) | census만 (문제집 아님) | `deck.trashed`(카드별), `first_trash_round` |
| C1.4 폐기는 체감 | census | `deck.trash_chosen` 분포 |
| C1.5 단독으로 강한 카드 | 보류 — 팁 2와 긴장, "단독" 표지가 content에 없다 | — |
| C1.6 초반 Faction 접근 카드 1~2장 | census → 정책 탐침 | `deck.faction_buys_r1_3`, `infl.sources` |
| C1.7 7라운드·덱 13장·중반 구매는 한두 번 봄 | census | `end.endgame_round`, `deck.end_cards`, `deck.exposure` |
| C1.8 Swordmaster 거의 필수 | census → 정책 탐침 | `lands.swordmaster_round`(없으면 None) |
| C2.1 전투는 경매, 아슬아슬하게 | census | `combat.win_margin`, `excess_troops`(상한) |
| C2.2 유닛 하나로 2·3위 | census | `combat.one_unit_entries`, `one_unit_rewarded` |
| C2.3·사용자 팁 1 sandworm | census | `combat.worms_summoned`, `doubled_rewards`, `worm_not_first`, `infl.fremen2_round`, `hooks_round` |
| C2.4 Shield Wall | census → 문제집 | 게임 `combat.wall_fall_round`, 좌석 `dropped_wall` |
| C2.6 tier III용 garrison 2~4 | census | `combat.garrison_tier3_visit` |
| C2.7 Heighliner 한 번에 다섯 | census | `combat.heighliner_visits` |
| C2.8 Combat Intrigue | census | `combat.intrigue_flip_won/lost` |
| C3.1 Guild·Emperor만으로 승리 | **스타일 봇**(league) + census | `infl.emperor/guild`, `combat.entered` |
| C3.2 1~2 진영 집중 | census | `infl.tracks_0_1/ge2/ge4`, `alliances` |
| C3.4 이른 Reveal로 Faction 카드 | census → 정책 탐침 | `infl.early_reveals`, `early_reveal_faction_buys` |
| C4.1~C4.3 Spy | census | `spy.placed/used_infiltrate/used_gather/recalled_other/on_board_end`, `*_offered/taken`, `use_lag` |
| C6.3·C6.4 Swordmaster ↔ High Council | census | `lands.*_round`, `sm_first/hc_first`, `reveal_cards_*`, `reveal_persuasion_*` |
| C7.1 Tech 지속 비용 | census | `bt.fw_strength/fw_trash/fw_influence_lost`, `ada_spies_trashed`, `tech_*` |
| C7.2 Commander 퇴각 후 재사용 | census | `bt.commander_retreats` 대 `commanders_recruited_paid` |
| C8.2·C8.3 끝내기, 막판 Intrigue | census → **문제집** | 게임 `end.leader_changed/trigger_*`, 좌석 `endgame_vp`, `plot_icon_plays_flippable` |
| 사용자 팁 2 진영 시너지 | census | `bond.cards_end/pairs_end/plays/activations/activation_share` |
| C1.9·C1.10·C5.1·C5.3·C8.1 | 없음(규칙 일치·설계 논평·공식 권장·낮은 신뢰) | — |
| C5.2 계약 노출·C6.1 water 사슬·C6.2 좋은 턴 | 낮음 — 계약을 읽는 에이전트가 없거나 "명백한 경우"가 아니다 | — |
| C8.4 상대 Agent 아이콘 추론 | 입력 표현(관측 버전 상승) — 낮음: heuristic 2라운드 손패 48개 중 "Faction 아이콘 없음"이 공개 정보로 증명된 것 2개 | — |

Bond 표는 content에서 만들면 Fremen 11 · Bene Gesserit **8** · Emperor 1 · Spacing Guild 0이다. 6.6의 7과 다른 1장은 Long
Reach(Agent 아이콘 조건이 Bene Gesserit Bond)다.

### 7.4 도구 — `scripts/ab/tip_census.py`

대회의 spec(같은 seed·Leader·좌석 회전)을 그대로 두고 매 전이를 `scripts/ab/tipcensus/`의 수집기(`deck`·`combat`·`influence`·
`endgame`)에 보여 준다. 판마다 JSONL 한 줄(좌석 행 + 게임 열), 끝에 종류별 평균과 **승자 평균**을 나란히 쓴다. 대회와 같은
게임을 두는지는 테스트가 순위·VP·결정 수로 고정한다(`tests/unit/test_tip_census.py`). heuristic 100판이 11~17초다.

```bash
uv run python scripts/ab/tip_census.py --agents heuristic --games 100 --ruleset choam \
    --bloodlines --tech-module --immortality --promo-cards --out ab-runs/tips/heuristic-train
```

census는 상관이다: 승자와 함께 움직이는 열은 **개입**(heuristic 변형이나 정책 덮어쓰기 A/B)으로 확인하기 전에는 원인으로
적지 않는다([lessons.md](lessons.md) 2026-09-11).

### 7.5 heuristic 기준값 (4명 미러, 구성마다 100 seed = 400 좌석-판, 실패·불법 0)

원자료는 git 무시 `ab-runs/tips/heuristic-{base,usual,train}/`(이 노트북). 셀은 "전체 / 승자"다. 평소 구성 = CHOAM + Bloodlines
+ Tech + Immortality, 학습 구성 = 평소 + promo.

| 열 | 기본판 | 평소 구성 | 학습 구성 |
|---|---|---|---|
| 판 길이(라운드) / Conflict 덱이 비어 끝난 판 | 9.55 / 64% | 9.64 / 72% | 9.54 / 66% |
| `deck.buys` / 그중 1~3라운드 | 15.3 / 4.3 | 17.2 / 5.3 | 16.7 / 5.3 |
| `deck.faction_buys_r1_3` | 1.37 / 1.41 | 1.65 / 1.81 | 1.69 / 1.81 |
| `deck.end_cards` / `end_starters` | 22.5 / 7.7 | 23.9 / 7.3 | 23.5 / 7.4 |
| `deck.exposure`(산 카드가 이후 손에 든 라운드 수) | 1.40 | 1.41 | 1.41 |
| `combat.won` | 2.17 / 3.24 | 2.18 / 3.34 | 2.15 / 3.28 |
| `combat.win_margin`(strength) / `excess_troops` | 4.44 / 1.37 | 4.24 / 1.27 | 4.43 / 1.31 |
| `combat.one_unit_entries` → 2·3위 보상 | 1.66 → 1.10 | 1.62 → 1.10 | 1.67 → 1.13 |
| `combat.worms_summoned` / `doubled_rewards` | 1.14 / 0.74 (승자 1.84 / 1.25) | 1.00 / 0.62 (1.82 / 1.15) | 1.12 / 0.73 (2.01 / 1.27) |
| `infl.tracks_0_1` | 1.35 / 1.08 | 1.36 / 1.04 | 1.35 / 0.92 |
| Swordmaster 얻은 좌석 / 평균 라운드 | 56% / 6.1 | 39% / 6.5 | 37% / 6.5 |
| High Council 얻은 좌석 / 평균 라운드 | 82% / 5.1 | 63% / 5.4 | 66% / 5.4 |
| Reveal 카드 수: 아무것도 없음 → Swordmaster만 | 3.82 → 3.26 | 3.70 → 2.89 | 3.72 → 2.97 |
| Reveal Persuasion: 아무것도 없음 → High Council만 | 4.62 → 7.14 | 4.51 → 6.80 | 4.53 → 6.99 |
| Infiltrate 제안 → 사용 | 1.60 → 0.96 | 1.27 → 0.78 | 1.20 → 0.69 |
| `end.leader_changed`(Endgame에서 1위가 바뀐 판) | 12% | 9% | 14% |
| `end.plot_icon_plays_flippable` | 0.12 | 0.07 | 0.07 |

heuristic에서는 **구조상 정해진 열**이 있다 — Gather Intelligence는 제안되면 늘 쓰고(`gather_intelligence` 2.0 > 거절 −2.0),
이른 Reveal은 0, 병력은 늘 최대로 보낸다. 이 열들은 5081과 비교할 때만 뜻이 있다. 읽을 만한 heuristic 자체의 모습: 판이
**9.5라운드**로 사람 추정(C1.7, 약 7라운드)보다 길고 3분의 2가 Conflict 덱 소진으로 끝난다. 덱은 23장이고 산 카드는 이후 1.4라운드
손에 든다(C1.7의 "한두 번"과 같다). Swordmaster는 늦고(6라운드 이후) 좌석의 절반 넘게 얻지 않는다 — 출처는 초반 구매를 권한다.

**6절 Mac 스크래치 census와 대조**(학습 구성, 12 seed): 산 카드 평균 비용 3.67 대 3.67, 시작 카드 폐기(Seek Allies 포함)
2.62 대 2.58은 맞고, Maker Hooks 도달 52% 대 58%(seed 0~11만 54%)는 가깝다. 판당 구매 17.85 대 16.70(seed 0~11만 17.06), Fremen 2 도달 77% 대 88%는 어긋난다.
Mac 스크립트의 seed·정의를 이 노트북에서 볼 수 없어 원인은 확정하지 못했다(최종 Fremen ≥ 2로 세어도 87%라 정의 차이로는
설명되지 않았다). 같은 날 5081로 다시 대조하니(7.7) **5081 1 + heuristic 3 표는 Mac과 덱 열이 모두 0.2 안으로 맞았고**, 미러의
차이는 Mac의 12 seed가 가진 표본 오차(이 도구의 100 seed 구간보다 약 3배 넓다)와 같은 크기다 — 정의 결함보다는 표본 차이로
보이지만 확정은 아니다.

### 7.6 다음

1. **Mac mini: 5081 census** — 학습 구성·평소 구성에서 5081 4명(100 seed)과 5081 1 + heuristic 3(25 seed × 4 회전). 이 노트북의
   heuristic 행과 같은 명령이다. 이것이 7.3 열 대부분의 실제 답이다(전투 마진, 유닛 하나 kicker, Swordmaster 시점, Spy 사용,
   이른 Reveal, 막판 Intrigue).
   ```bash
   uv run python scripts/ab/tip_census.py --agents checkpoint:checkpoints/2026-09-22/exploit/champion-5081.pt \
       --games 100 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --out ab-runs/tips/5081-train
   ```
2. census에서 정책과 팁이 어긋나는 열이 나오면 그 결정 가족만 덮어쓴 **정책 탐침 A/B**(2:2, `paired.py`) — 후보: 초반 Faction
   접근 카드(C1.6), 이른 Swordmaster(C1.8), 이른 Reveal(C3.4).
3. **평가 문제집**의 첫 문항 후보: 마지막 라운드에 맞는 face-up 전투 카드를 가진 채 Crysknife/Desert Mouse/Ornithopter를
   Plot(spice 1)으로 쓰는가(Endgame 옵션은 VP 1) — C8.3; sandworm 소환(6.3); Shield Wall이 서 있고 tier III가 남았을 때 폭파(C2.4).
4. **스타일 봇**: Guild·Emperor 영향력 몰빵(C3.1) — league 상대 후보.
5. 6.8에서 남은 것(정책 틀 H-deck 탐침, heuristic Tleilaxu 채택, 사용자 팁 더 적기)은 그대로다. 팁 2의 "Bond 발동 직접 세기"는
   `bond.activations`로 도구가 생겼다(heuristic: Bond 판정이 걸린 play 가운데 21~27%가 발동 — 좌석별 비율의 평균).

### 7.7 5081 census — 정책은 팁과 어디서 같고 어디서 다른가 (2026-09-23)

사용자가 `checkpoints/2026-09-22/exploit/champion-5081.pt`를 이 노트북으로 가져왔다. 셀 셋, 실패·불법 0(원자료 git 무시
`ab-runs/tips/5081-*`, 비교표 `ab-runs/tips/cmp-*.md`): (A) 5081 4명 학습 구성 100 seed(15분), (B) 5081 1 + heuristic 3 학습
구성 25 seed × 4 회전 = 100판, (C) 5081 4명 평소 구성 100 seed. 워커 4개, 워커당 약 650MB, 한 판 약 35초. 비교는 새 도구
`scripts/ab/tip_compare.py`(seed 군집 부트스트랩 95% 구간; 같은 표의 두 종류는 seed를 짝지어 다시 뽑는다)로 했다. B에서 5081은
**80%** 이긴다(heuristic 셋 상대).

**Mac 대조**: B의 5081은 판 끝 덱 13.01 = 시작 7.62 + 산 카드 5.39(Mac 13.00 = 7.50 + 5.50), 구매 5.90(6.10), 7라운드 이후 2.60(2.52),
평균 비용 2.96(3.10), 폐기 2.39(2.38), 동맹 1.47(1.50)으로 맞는다. A는 덱 11.47(10.85), 구매 4.22(3.77), 비용 3.21(2.77), Fremen 2
87%·3.7라운드(83%·3.6), Hooks 78%·4.7라운드(77%·4.5), sandworm 1.99(2.27), 두 배 보상 1.20(1.29)이다.

| 팁 | 팁의 주장 | 5081: 미러 / heuristic 셋 상대 | heuristic 미러 | 정책과 팁 |
|---|---|---|---|---|
| C1.1·C1.7 구매 수 | 판당 6~7장, 덱 약 13장 | 구매 4.2 / 5.9, 덱 11.5 / 13.0, 산 카드가 이후 손에 든 라운드 1.97 | 16.7장, 덱 23.5 | 사람보다 조금 덜 산다, 덱 크기는 같다 |
| C1.4 폐기는 처음 몇 장 | 초반 폐기 | 첫 선택 폐기 2.4라운드 | 4.4라운드 | **같다** |
| C1.3 폐기 순서 | Dagger 먼저(합의 없음) | Convincing Argument 0.56 · Reconnaissance 0.49 · Dagger 0.32 | Dagger 0.80 | 설문의 "Convincing Argument 먼저" 쪽 |
| C1.6 초반 Faction 접근 카드 | 1~3라운드 1~2장 | **0.67 / 0.92** | 1.69 | **다르다** — 방문 영향력의 대부분이 시작 카드(5.76)다 |
| C1.8 Swordmaster | 거의 필수, 초반 | 얻은 좌석 **79% / 94%**, 5.6 / 4.7라운드 | 37%, 6.5라운드 | **같다** |
| C6.4 Swordmaster ↔ High Council | 이견 | Swordmaster 먼저 76%, High Council은 38%만 7.6라운드 | High Council 먼저 54% | 정책은 Swordmaster 쪽 |
| C2.1 아슬아슬하게 이기기 | 작은 마진 | 승리 마진 **5.1 / 6.9** strength, 남는 troop 상한 1.8 / 2.5 | 4.4 (늘 최대 배치) | **다르다** — 더 크게 이긴다 |
| C2.2 유닛 하나로 2·3위 | 흔히 한다 | 유닛 하나 투입 1.35 → 보상 0.70 / 0.80 → 0.63 | 1.67 → 1.13 | 덜 한다 |
| C2.3 sandworm | 두 배, 병력으로 받쳐라 | 소환 1.99 / 2.35, 두 배 보상 1.20 / 1.29, 벌레 투입 중 1위 못 한 것 68% / 33% | 1.12, 0.73 | 적극적 — 미러에서는 벌레가 자주 밀린다 |
| C2.4 Shield Wall | 폭파로 벌레 길을 연다 | 평균 5.9라운드, 24%는 끝까지 서 있음 | 4.2라운드 | 늦게 연다 |
| C2.6 tier III용 garrison | 2~4 남겨 둔다 | tier III 방문 때 garrison **1.70 / 1.71** | 2.47 | **다르다** |
| C2.7 Heighliner 한 번에 다섯 | 라운드의 주역 | 방문 **1.17 / 1.57**, Guild 영향력 3.29 / 5.20 | 0.42, 1.05 | **같다** — Guild 전문 |
| C3.1 Guild·Emperor만으로 | 전투 없이 | Guild는 높고 Emperor는 낮으며(2.10 / 1.68) 전투는 많다(8.05 / 7.65회) | | 그 스타일은 아니다 |
| C3.2 1~2 진영 집중 | 트랙 0~1이 흔하다 | 0~1 트랙 0.93 / 0.85, 2 이상 3.07 / 3.15 | 1.35 | 셋에 걸친다 |
| C3.4 이른 Reveal | Uprising에서 자주 보인다 | **0** — Agent turn도 가능한 결정 348번 중 0번(4판 독립 확인) | 0(구조상) | **다르다** |
| C4.2 Gather Intelligence 골라 쓰기 | 타이밍을 고른다 | 제안 중 86% 사용 | 100%(구조상) | 조금 고른다 |
| C4.1·C4.3 Infiltrate·Espionage | Espionage 우선, 미리 놓기 | Spy 2.94개, Infiltrate 제안 중 21% 사용, Espionage 0.21회 | 4.20, 58%, 0.66 | Espionage를 우선하지 않는다 |
| C7.2 Commander 퇴각 재사용 | 퇴각으로 아낀다 | 퇴각 0.13, 2 Solari 재고용 **3.15 / 5.86** | 0.14, 1.55 | 퇴각 대신 돈을 낸다 — 퇴각 기회가 얼마나 왔는지는 아직 안 셌다 |
| C7.1 Tech | 큰 투자 | 타일 0.43, Forbidden Weapons 0 | 1.27 | 거의 안 산다 |
| C8.3 막판 Intrigue | 1위가 바뀐다 | Endgame에서 1위가 바뀐 판 19%. battle-icon Intrigue를 맞는 카드가 있는데 Plot(spice 1)으로 쓴 것 0.10 / 좌석-판(이 카드 Plot의 약 3분의 1) | 14%, 0.07 | 문제집 후보 |
| 사용자 팁 2 Bond | 진영 시너지로 산다 | Bond 카드 0.44, 짝 0.28, 발동 0.14 | 1.78, 1.67, 0.32 | 안 한다(6.6과 같다) |
| 6.5 Tleilaxu | (heuristic의 약점) | Tleilaxu 구매 0.18 | 2.94 | 정책은 거의 사지 않는다 — 6.5의 옆길 발견과 맞는다 |

판 길이는 5081 미러도 9.55라운드이고 65%가 Conflict 덱 소진으로 끝난다(heuristic과 같다). 평소 구성(C)은 학습 구성과 같은 모습이다
(약 200열 중 구간이 0을 벗어난 것 7열, 모두 작다 — 두 배 보상 −0.18, VP −0.33 등; `ab-runs/tips/cmp-5081-train-usual.md`). 5081 미러 안에서 승자와 나머지를 가르는 열(`--split-winners`)은 영향력 트랙·동맹·전투 승·sandworm처럼 VP와
직접 겹치는 것들이라 원인 후보로 쓰지 않는다. 그 밖에 승자는 비싼 카드(비용 5 이상 1.19 대 0.80)와 Faction 카드(1.67 대 1.34)를 조금 더
샀다 — 상관일 뿐이지만 C1.6·H-deck과 같은 방향이다.

### 7.8 다음

1. **정책 탐침 1순위 — 기능으로 거른 H-deck (C1.6 + 6.1)**: 1~3라운드 Reveal 구매에서 Faction 접근 아이콘 카드를 살 수 있으면 사게
   덮어쓴 5081 대 5081, 2:2 미러. 정책과 팁이 가장 분명히 갈리고(0.67 대 1~2장), 승자 쪽 상관도 같은 방향이며, 6.8의 "정책 틀 H-deck
   탐침"을 "비용"이 아니라 사람이 말한 "기능" 기준으로 시험한다. 덮어쓰기 에이전트는 `scripts/ab/pypath/netprobes.py`
   (`net_faction_early1`·`net_faction_early2`: 1~3라운드 Reveal 구매에서 Faction 아이콘 카드를 살 수 있으면 스스로 산 것까지 합쳐
   cap장이 될 때까지 네트워크 logit 최고인 것을 산다; `DUNE_PROBE_CKPT`가 있을 때만 등록). **파일럿**(`net_faction_early2` 4명,
   12 seed): 1~3라운드 Faction 카드 0.67 → **1.00장**, 1~3라운드 구매 1.08 → 1.42장 — 개입은 일어나지만 cap 2에 한참 못 미친다.
   1~3라운드에 Faction 카드를 살 Persuasion이 모자란 경우가 많은 것으로 보인다. 용량이 +0.3장 남짓이라 효과도 작을 것이고, 이
   노트북에서 2:2 미러 1,000판(약 2.5시간)의 분해능(승률 약 ±6%p)으로는 가르기 어렵다 — VP 마진이 더 민감하다. A/B 명령:
   ```bash
   export DUNE_PROBE_CKPT=checkpoints/2026-09-22/exploit/champion-5081.pt
   PYTHONPATH=scripts/ab/pypath uv run dune-imperium-tournament --agents net_faction_early2,checkpoint:$DUNE_PROBE_CKPT \
       --games 500 --start-seed 8100 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --rotate-leaders \
       --workers 4 --matches ab-runs/tips/probe-faction2.jsonl
   uv run python scripts/ab/paired.py ab-runs/tips/probe-faction2.jsonl --a net_faction_early2 --b checkpoint:$DUNE_PROBE_CKPT
   ```
2. 탐침 후보 2: 이른 Reveal(C3.4) — 조건 설계가 어렵다(그 Reveal의 Persuasion으로 Row의 Faction 카드를 살 수 있을 때). 3: tier III 전
   garrison 남기기(C2.6), 작게 이기기(C2.1) — 배치는 여러 단계 결정이라 덮어쓰기가 까다롭다.
3. **평가 문제집 — 틀과 첫 세 문항이 들어갔다(2026-09-23)**: [evaluation/problem-set.md](evaluation/problem-set.md),
   `dune-imperium-problems mine|score|check`. 문항은 Endgame battle-icon VP(clear), 마지막 라운드 battle-icon 보유(tip), Deep
   Desert 소환(tip, 사용자 팁 1). 5081은 소환·Endgame에서 이미 팁대로 두고(정답률 1.00), 보유 문항에서 20개 중 3개를 Plot으로 쓴다.
   Opus 검증이 "규칙상 명백"이라 믿었던 보유 문항의 반례(앞면 와일드 카드, 같은 턴의 "spice를 얻었다면" 효과)를 찾아 tip으로
   내렸다. 다음 문항 후보: Shield Wall 폭파(C2.4), 이른 Reveal(C3.4), tier III garrison(C2.6).
4. Commander: 퇴각할 수 있었던 기회 수를 세는 열을 더해 "퇴각 대신 재고용"이 약점인지 가린다(C7.2).
5. 스타일 봇(Guild·Emperor, C3.1)은 5081이 이미 Guild 전문이라 값이 줄었다 — Emperor 쪽이나 전투를 버리는 쪽으로 다시 정한다.
6. 6.8의 나머지(heuristic Tleilaxu 채택, 사용자 팁 더 적기)는 그대로다.
