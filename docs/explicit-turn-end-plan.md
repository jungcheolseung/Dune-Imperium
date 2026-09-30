# Agent 턴은 "턴 종료"로만 닫는다 — 구현 계획

기준일: 2026-09-30. 기준 코드: master `402d124`(codec v123, 관측 v27). 이 문서는 다른 세션에서 구현하도록 남긴 계획이다
(사용자 2026-09-30: "구현은 다른 세션에서 이어서 할게"). 조사는 읽기 전용 workflow 여섯 갈래(엔진의 닫힘 경로, 턴 중 선택 행동,
서버·UI, AI·학습, 테스트, 규칙 문서)와 설계·완전성 점검으로 했다. 아래 file:line은 `402d124` 기준이므로 착수 때 다시 확인한다.

## 1. 사용자 판정

2026-09-30, 세 번째 지적이다(앞선 두 번은 `docs/lessons.md` 2026-09-23):

> "턴 종료는 무조건 플레이어가 종료를 누를 때만 턴이 닫히게끔 해야한다고 했는데 진행할 수 있는 동작이 없더라도, 턴은 무조건
> 플레이어가 턴 종료를 눌러야 턴 종료야. 턴 종료 전에 atomic으로 임페리움 열을 갈 수도 있고, 표본을 공급처로 되돌릴 수도 있고
> 책략을 추가로 쓸 수도 있고 그러잖아"

엔진 차원의 규칙이다: **모든 Agent 턴은 소유자의 `finish_agent_turn`으로만 닫힌다.** 사람·AI 좌석 모두 같다. 공개 차례는 이미
`finish_reveal`로만 닫히므로 그대로다.

## 2. 왜 지금은 저절로 닫히나

- 엔진은 처음부터 Agent 턴을 마지막 보류 효과가 풀리는 순간 닫았다: `rules/effects.py:415` `advance_after_effect`의 `else` 가지
  (433-444)가 `pending_combat_deployment`도 다른 보류 효과(`agent_turn_has_other_pending_effects`, :468)도 없으면 좌석의
  `AGENT_EFFECTS` frame을 다음 좌석의 `TURN` frame으로 바꾼다. 호출처는 100곳이다.
- 2026-09-05 OQ-029가 `finish_agent_turn`을 넣었지만 배치할 수 있는 턴에만 넣었고, 4항에 "배치가 불가능한 turn(비Combat space,
  Shaddam Signet의 배치 금지)은 이전처럼 마지막 효과와 함께 자동 종료한다"(`open-questions.md:191`)고 적었다. OQ-057이 멈춘 Agent
  box용 종료를 더했다.
- 2026-09-23 "턴 종료는 한 번 누른다" 통일은 서버만 바꿨다(`server/sessions.py` `_settle_locked` 1152-1191이 마지막 스텝을 붙잡았다가
  "턴 종료 ▶"에 넘긴다). 엔진 안에서는 이미 다음 좌석의 턴이 열려 있어, 붙잡힌 동안 그 좌석의 합법 행동은 없다(sessions.py:1036-1040).
  그래서 마지막 효과 뒤의 Plot Intrigue, Family Atomics, 표본 반환, Tech flip, Sardaukar Commander recruit가 막혔다(조사 probe에서
  자동 닫힘 70번 중 11번은 바로 전에 이 중 하나가 합법이었다).
- 마지막 스텝이 남긴 후속(Scouts 소위원회 줄, 턴 끝에 완수한 Contract 보상, Emperor track Influence 4의 Spy, Navigation·Skill 선택
  등)은 턴이 닫힌 뒤 풀리고 `turn_closed`로 표시된다(OQ-044 (d)). OQ-063의 spice 장부 오류와 OQ-076의 알려진 한계가 여기서 나온다.
- 공식 문서는 Agent 턴이 어떻게 끝나는지 말하지 않는다([Main pp. 8-11]에 종료 단계가 없다). 자동 닫힘은 공식 규칙이 아니라 엔진
  기본값을 OQ-029 4항이 project convention으로 적은 것이다.

## 3. 규칙 근거와 문서

새 OQ로 적는다(epic-game-mode 병합 뒤라면 OQ-092~094가 Epic이므로 **다음 빈 번호**, 예상 OQ-095). project convention이며 사용자
말을 인용한다. 함께 고칠 것: OQ-029 4항(`open-questions.md:191`), OQ-015 (a)(:369 "Agent turn의 마지막 pending 그룹이 해결되면
turn이 자동으로 넘어가므로 그 전에 내야 한다"가 거짓이 된다).

막혔던 창의 근거(착수 때 원문 대조):

| 창 | 규칙 문서 |
|---|---|
| Plot Intrigue | `player-turns.md:271` "Plot Intrigue 카드는 자신의 Agent 턴 또는 공개 턴 중 어느 때든 플레이할 수 있다. [Main p. 7] [Main p. 8]" |
| Family Atomics | `immortality.md:102` `[Immortality p. 12]` |
| 표본 반환 | `immortality.md:71` "자신의 specimen은 언제든 supply로 돌려보낼 수 있다" `[Immortality p. 8]` |
| Tech flip | `bloodlines.md:99` `[Bloodlines pp. 7, 12]` |
| Commander recruit | `bloodlines.md:49` `[Bloodlines p. 4]` |

같은 작업 단위에서 고칠 문서: `player-turns.md:150-151`, `setup-and-game-flow.md:119`(종료 단계 추가), `arrakeen-scouts.md`의
OQ-076 한계 서술, OQ-044 (d)(:326), OQ-054(:478-481, Usurp trash가 종료 안으로), OQ-059(:574-586), OQ-063(:657-659), OQ-070(:822,
:828), OQ-076(:894, :897), `docs/lessons.md`에 새 항목(세 번째 지적, 2026-09-23 수정은 화면만 바꿨다).

## 4. 설계

### 4.1 닫는 길은 하나

- `effects.py`에 `close_agent_turn(state, player)`를 둔다(지금 433-444에서 뽑아낸다): `next_unrevealed_player` →
  `reset_turn_counters(..., closing=)`(Hungry for Spice 판정 포함, frames.py:213-273) → 새 `TURN` frame. 맨 위 frame을 무작정 바꾸지
  말고 소유자의 `AGENT_EFFECTS` frame이 맨 위인지 assert한다(지금은 `(*decision_stack[:-1], next_frame)`, effects.py:462).
- `advance_after_effect`는 **절대 닫지 않는다**: 보류 플래그만 다시 계산하고 frame을 유지한다. `_closed_for` 소급(447-458)도 필요 없다.
- `close_agent_turn`의 호출처는 `combat_deployment.apply_agent_turn_finish`(:618)와 아래 4.3의 "마치는 중" 자동 단계뿐이다.
- 자동 전이(`expire_trashed_card_effects` agent_effects.py:2897-2952, `skip_impossible_imperial_privilege_recall`
  board_effects.py:1368-1398, Covert Operation 마지막 discard agent_effects.py:686-690, acquisition.py:226-238,
  leader_abilities.py:265-270·309-311)는 모두 `advance_after_effect`를 거치므로 이제 자기 그룹만 비우고 소유자의 열린 frame으로 돌아온다.
- epic-game-mode의 `_apply_control_the_spice_payment`(epic에서 agent_effects.py:2911)도 `advance_after_effect` 호출처이고 :2960에
  `turn_closed = … == FrameKind.TURN` probe가 있다 — 병합 뒤 목록에 넣는다.
- 공개 차례(`finish_reveal_turn`, reveal_turn.py:4513-4642)는 그대로.

### 4.2 `finish_agent_turn`

- 제시 조건(`legal_agent_turn_finish_actions`, combat_deployment.py:317-347): 소유자의 `AGENT_EFFECTS` frame이 맨 위이고
  `agent_turn_has_other_pending_effects(..., ignore_agent_effect=stalled_box)`가 거짓. 배치 창·멈춘 box 전제 조건은 없앤다.
  조건을 만족한 Contract는 의무라 이미 보류 효과로 센다(`choam-module.md:33` "조건을 만족한 contract는 반드시 완료한다 `[FAQ p. 1]`").
  대기열(Skill·Navigation·`pending_track_spies`·`scouts_four_bonus_choices` 등)은 합법성 조건으로 걸지 말고 assert + 소크 검사로
  지킨다 — 대기열은 dispatcher가 플레이어 결정 전에 연다(`skill_choice_is_queued` sardaukar.py:406-412, `navigation_play_is_queued`
  navigation.py:163-177). 합법성 조건으로 걸면 `navigation_active_slot != 0`에 막힌 항목이 종료를 빼앗아 게임이 멈출 수 있다.
- 누르면 이 순서로: (1) 멈춘 box 불발(OQ-057, 638-667; 641-643·684-687의 try/except는 없앤다), (2) 붙잡힌 Contract 아이콘 불발과
  이벤트(668-675, OQ-059; 지금은 `reset_turn_counters`가 먼저 지워 버리는 순서 버그도 고쳐진다), (3) **Usurp trash를 종료 안에서**
  ("trash that card at the end of the turn", OQ-054 `open-questions.md:477`), (4) `agent_turn_finished` 이벤트, (5) `close_agent_turn`.
- **Usurp가 후속을 남길 때(점검이 찾은 빈틈).** trash가 Sardaukar Standard의 Skill 선택을 대기열에 넣거나(card_trash.py의 troop 2
  recruit ~120-137, Intrigue draw ~161+로 reshuffle chance frame이 생길 수도 있다) 하면, frame에 `finishing=True`를 두고 멈춘다.
  `apply_skill_choice`(sardaukar.py:500)는 frame을 pop만 하고 `advance_after_effect`를 부르지 않으며 `begin_skill_choice`는 frame 없이
  항목을 버리기도 한다(416-437). 그래서 `engine._advance_automatic`(engine.py:1017-1100)에 단계를 더한다: 맨 위가 `finishing=True`인
  소유자의 `AGENT_EFFECTS` frame이고 그 위에 chance frame·대기 항목이 없으면 `close_agent_turn`. 그리고
  `legal_agent_effect_frame_actions`(agent_effect_frame.py:95-143)는 `finishing` frame에 `()`를 돌려준다. 둘 다 없으면 두 번째
  누름이나 멈춘 게임이 된다. `graft.usurp_trash_is_queued`·`resolve_usurp_trash`(graft.py:255-312)는 dispatcher에서 빠진다.
- 종료 전까지 계속 제시되는 선택 행동(등록은 이미 있다, agent_effect_frame.py:130-137): `play_intrigue`(False Orders 포함),
  `use_family_atomics`, `return_specimen`, `flip_tech`(Rapid Dropships의 조건 그대로, tech.py:581-586), `recruit_sardaukar_commander`,
  배치 창이 열려 있을 때의 deploy/withdraw. 반복 가능한 것은 모두 자원을 쓰거나 횟수 제한이 있어(Atomics 게임당 1, flip 라운드당 1,
  recruit 턴당 1) 무한 반복이 없다(점검 확인). 종료의 제시 순서는 OQ-029 자리 그대로(Plot·표본·Atomics 뒤, 회수 앞).

### 4.3 후속은 열린 턴 안에서 풀린다

선택 trash, research, Navigation·Skill 선택, Contract 시장·보상, Spy 배치, Holy War·Covert Operation의 상대 frame, Scouts 비용·보상
줄, Signet·Tleilaxu 획득이 모두 다음 좌석의 `TURN` frame 대신 소유자의 열린 `AGENT_EFFECTS` frame 위에 쌓인다. 종료는 소유자
frame이 맨 위일 때만 나오므로 후속을 다 풀어야 누를 수 있고, 그 spice·recruit·Spy 회수는 이 턴의 것으로 센다. OQ-076 한계,
OQ-063 예외, OQ-044 (d)의 Emperor track Spy 잔여, OQ-059의 잃어버린 아이콘이 함께 고쳐진다. 따라오는 올바른 부수효과: 후속 spice로
Harvest Contract가 턴 중에 의무가 될 수 있다(effects.py:521-541), Suspensor Suits(OQ-042)가 마지막 효과 뒤의 draw도 센다.

### 4.4 죽는 `turn_closed` 장치 (나중 슬라이스에서 지운다)

`_closed_for`·`mark_queued_turn_closed`(effects.py:371-412, engine.py:878-883·960-965), `turn_closing_player`·
`turn_closed_frame_owner`(frames.py:321-379, engine.py:909·998-1000), `complete_alliance_contracts(closing_player=)`
(contracts.py:1355-1423), leader_abilities.py:1914, `pending_skill_choices`·`pending_navigation_plays`의 넷째 필드(state.py:109-128),
`spies_recalled_turn` 예외(spy_moves.py:342-345, contracts.py:328-332, scouts_effects.py:930-931; spy_moves.py:136-145의 FAQ 강제
이동 판독은 남긴다), Scouts offer의 turn_closed 필드(state.py:167). **주의:** 배치 전 `TURN` frame에서 낸 Plot의 후속은 그 좌석의
열린 `TURN` frame으로 돌아온다(OQ-044의 tech.py:450, Rapid Engineering). 그 probe는 지금도 참이고 닫힌 턴이 아니다 — probe마다 이
경우를 확인한 뒤에만 지운다. `reset_turn_counters(closing=)`와 `grant_hungry_for_spice`의 `before` 판정(leader_abilities.py:2479-2481)은
남긴다: 다른 좌석이 모두 공개했으면 `finish_agent_turn`이 같은 좌석의 턴을 곧바로 다시 열고, 턴 넘기기 경로도 쓴다.

### 4.5 턴 넘기기 (Withdrawn, Litany Against Fear)

Agent를 보내지 않으므로 `AGENT_EFFECTS` frame이 없다(Withdrawn: intrigue.py:1649-1658 → `open_next_turn` effects.py:150-177;
Litany: `agent_turn.apply_turn_start_card` agent_turn.py:787-836). 서버가 이미 붙잡아 한 번 누름이다. 넘긴 좌석이 그 누름 전에 Plot·
Atomics·표본 반환을 할 수 있는지는 **사용자 질문 Q1**(아래).

### 4.6 서버·UI

- `_settle_locked`의 명시적 종료 가지는 이미 `finish_agent_turn`을 봉인하고 넘긴다(`EXPLICIT_TURN_ENDS`, turn_end.py:27). 붙잡기
  장치는 리더 픽, Conflict 보상, Control 방어, Scouts 항목, 두 턴 넘기기, 턴 밖의 `optional_trash` 때문에 남긴다.
- "마치는 중"은 **엔진 frame의 `finishing` 플래그**로 알아본다(`server/turn_end.py`에 helper). `unit_seat(after) == actor`로는 안 된다:
  다른 좌석이 모두 공개했으면 보통의 종료 뒤에도 같은 좌석이 다음 결정을 가진다(`next_unrevealed_player` effects.py:648-655,
  `unit_seat` turn_end.py:74-88).
- `_advance_locked` 1259-1266(AI의 답이 사람 단위를 닫는 경우)은 사라진다 → assert. `TURN_TAKING_EVENTS`에 `"agent_placed"`는 안전망으로
  남긴다. 선택 행동만 남았을 때 프롬프트를 턴 종료 문구로(agent_turn.py:490; 한글 `static/prompts_ko.js`), `help.js`의
  `announce_turn_end`가 Agent 턴에서 다시 나오게, turn_end.py 1-16·39-48·98-105의 docstring.
- 다른 좌석에 "턴 종료 대기"를 보여 주려면 공개 보류 그룹만으로 판정한다(Plot을 낼 수 있는지로 판정하면 손패가 새다).

## 5. 슬라이스

- **S0 문서(메인 세션).** 새 OQ, OQ-029 4항·OQ-015 (a) 재작성, lessons 항목. 코드 없음.
- **S1 엔진 핵심(세션 모델, 고위험).** effects.py(`advance_after_effect` 유지, `close_agent_turn`), combat_deployment.py 317-347·618-695,
  `_advance_automatic`의 finishing 단계, agent_effect_frame의 finishing 가드. `ACTION_CODEC_VERSION` 올림(epic 병합 뒤면 v125; 템플릿
  무변경이라 체크포인트는 identity로 이관). 테스트: 뒤집을 것 `test_agent_effects.py:280`·`:5156`, `test_acquisition.py:437`,
  `test_board_effects.py:650`, `test_intrigue.py:817`·`:849`, `test_tech.py:888`(:910 한 줄이 36건), `test_scouts_subcommittees.py:110`
  `_scouts_frames_done`(14건); 종료 단계를 넣을 것 12건(예: `test_board_effects.py:362`, `test_bloodlines_leaders.py:582`); 공용
  `finish_turn` helper를 `_resolve_board_icons`(test_agent_effects.py:153) 옆에. 새 테스트: 비전투 턴이 frame을 유지하고 종료와
  선택 행동을 제시, 마지막 효과 뒤 Plot, 종료 때 붙잡힌 Contract 아이콘 불발 이벤트, 후속이 남아 있으면 종료 없음. 수락: 여러 룰셋
  무작위·heuristic 게임이 끝까지 간다.
- **S2 OQ-044 (d)·OQ-063·OQ-076 테스트 재작성(subagent).** 21개 함수(예: `test_immortality_imperium_choices.py:661-1091`,
  `test_navigation.py:228/560/612/659`, `test_bloodlines_cards.py:2212/2501/2514/2552/2649`, `test_tech.py:965/1036`,
  `test_leader_abilities.py:1599`)를 "후속이 이 턴에 세어진다 → 종료가 깨끗한 다음 턴을 연다"로. OQ-076(가입 spice가 Hungry for
  Spice에 든다)·OQ-063·Emperor track Spy 회수 테스트 추가.
- **S3 Usurp를 종료 안으로 + finishing(세션 모델).** graft.py:255-312, combat_deployment.py, effects.py, engine.py. OQ-054 갱신.
- **S4 서버·UI(고위험: 독립 리뷰).** sessions.py, turn_end.py, 프롬프트, help.js. `test_turn_end.py:411/557/615` 재작성,
  `:715/737/787/818/968`은 리더 픽·Litany·Conflict 보상 붙잡기로 옮겨 seed 다시 찾기, `test_undo.py:281/324/366`·`test_autosave.py:85`·
  `test_autosave_app.py:95/122`·`test_access.py:619`·`test_doorbell.py:169/260`·`test_snapshot.py:96`의 붙잡기 helper는 `leader_draft=True`로,
  sweep(`test_turn_end.py:1026-1129`)에 bloodlines·immortality·Scouts 추가. 수락: `agent_placed`로 시작한 단위의 붙잡기 없음, 모든
  `agent_placed` 뒤 다른 좌석의 스텝 전에 그 좌석의 `finish_agent_turn`, 모든 사람 결정에 합법 행동 ≥ 1, 두 번째 누름 없음.
- **S5 죽은 `turn_closed` 장치 삭제(subagent, S1-S4 녹색 뒤).** 4.4 목록. `test_sardaukar.py:730-780`, `test_frames.py:26-73`,
  `test_servo_signet_turn.py:277`, `test_immortality_tleilaxu_cards.py:886`, `display/test_scouts_lines.py:154` 정리. 수락: S1 census
  trace가 바이트 그대로.
- **S6 고정값·AI 산출물.** `test_observation_encoding.py:321` golden digest 6개(인코딩이 아니라 게임 경로가 바뀐 것인지 먼저 확인),
  tips-v1 다시 캐기(`docs/evaluation/problem-set.md:38-48`, 5081 체크포인트 필요; `test_problem_set.py` 11개 함수), census 테스트
  `test_tip_census_deck.py:434`·`_endgame.py:334/474`·`_influence.py:359/405`.
- **S7 e2e(subagent).** `scripts/e2e/turn_end.py` [c]가 모든 Agent 턴에서, [e]는 Agent 아닌 붙잡기로; 새 장면(효과 끝, Plot·표본
  행동이 남은 채 종료 줄이 `/actions`로 가고 붙잡기 없음). `turn_end.py:44-49`·`remote_fresh.py:87-92`의 `EXPLICIT_TURN_END_IDS`에
  `confirm_scouts_bid`가 빠진 어긋남도 고친다. `scouts.py`·`staged_turn.py` 등 seed 다시 찾기.
- **S8 문서(`Document …` 커밋).** README.md:7/9/11, handoff(병합 때만), `implementation-audits/bloodlines.md:37,75`·`immortality.md:39`·
  `leaders.md:101`, `multiplayer-design.md:26`.

## 6. 검증

슬라이스마다 해당 pytest. 묶음 끝에 전체 pytest·ruff·mypy·`scripts/e2e/run_all.py`. 소크(`--soundness-interval`·`--privacy-interval`):
기본, choam, choam+bloodlines+tech, choam+immortality, 전 옵션+Scouts, Go to 11, Epic; 무작위·heuristic. **Census**: 한 좌석의
`AGENT_EFFECTS`·`TURN` frame이 다른 좌석의 `TURN` frame으로 바뀌는 모든 전이의 행동이 `finish_agent_turn`·`finish_reveal`·턴 넘기기
카드·finishing 단계 중 하나 — 그 밖의 닫힘 0. 조사 추정: 게임당 결정 +3.5~6%, 4,000 스텝 아래 잘림 없음, heuristic 반복 없음.

## 7. AI·학습 영향

- 템플릿 무변경이라 체크포인트는 identity로 이관된다. 옛 저장은 버전 검사로 거절된다. 전문가 라벨 파일은 버전을 넘어 섞을 수 없다.
- heuristic: Plot 먼저, recruit·flip, 그다음 종료 0.5(heuristic_agent.py:93). Atomics 0.3·표본 -2.5는 턴 끝에 쓰이지 않는다.
- seed 게임의 RNG 흐름이 첫 옛 자동 닫힘부터 달라져 이전 A/B·대회 수치와 비교할 수 없다(handoff에 적는다).
- v111 네트워크는 `finish_agent_turn`을 배치 창에서만 봤다. heuristic이 몰 때 Immortality 턴 끝의 첫 선택이 표본 반환이었다(게임당
  9.5번). **전문가 반복 학습은 이 결정을 탐색하지 않는다**: `training/expert.py:158-165`가 `AGENT_EFFECTS` 결정을 anchor 행으로만 쓰고
  `NetworkSearchAgent`는 탐욕으로 답한다(network_search_agent.py:255, `orders_agent_effects` :380-391). `search_effect_order`를 켜지 않으면
  재적응으로 고쳐지지 않는다. 몇 시간 걸리는 재적응은 착수 전에 사용자에게 묻는다(long-run 관례).
- 속도: 탐욕 대회 약 4-5% 느려짐, `NetworkSearchAgent` 탐색 결정당 2-6%.

## 8. 사용자 질문 (착수 때)

- **Q1 턴 넘기기.** Withdrawn·Litany Against Fear로 턴을 넘긴 좌석이 한 번의 "턴 종료" 전에 Plot·Family Atomics·표본 반환을 할 수
  있나(예: Litany의 draw 1로 뽑은 Plot)? 공식 문서는 침묵. 아니오면 엔진 변경 없음, 예면 넘긴 `TURN` frame을 열어 두고 자유 시점
  행동과 종료만 제시. 조사의 권장은 "아니오"(카드가 턴을 끝낸다)였지만 1절의 사용자 말("무조건 플레이어가 턴 종료를 눌러야")에
  비추어 착수 때 묻는다.
- **Q2 재적응 실행.** 병합 뒤 v111 기준선의 재적응(몇 시간)을 돌릴지.

## 9. 순서

epic-game-mode 병합(사용자 2026-09-30 결정, codec v124·관측 v28)이 먼저다. 이 작업은 그 뒤 codec을 한 번 더 올린다. 관측은 새
frame 종류나 스칼라가 없으면 그대로다(공개 "종료 가능" 플래그를 부호화하면 관측도 오른다).
