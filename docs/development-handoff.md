# 개발 인수인계

기준일: 2026-09-23

이 문서는 새 개발 세션(Claude Code, Codex 등 어떤 도구든)에서 저장소의 현재 위치를 빠르게 복구하기 위한 진입점이다. 규칙의 규범 근거는 [`rules/README.md`](rules/README.md), 장기 마일스톤과 구현 순서는 [`implementation-plan.md`](implementation-plan.md), 카드별 세부 동작은 [`implementation-audits/personal-cards.md`](implementation-audits/personal-cards.md), Leader 능력은 [`implementation-audits/leaders.md`](implementation-audits/leaders.md), 계약 경계는 [`implementation-audits/contracts.md`](implementation-audits/contracts.md)를 따른다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`(도구 중립 공통 지침), `CLAUDE.md`(Claude Code 진입점), `README.md`, 이 문서, 그리고 [`lessons.md`](lessons.md)를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을 확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl --extra ui --extra train`으로 Python 3.14 환경을 준비한다(`ui`는 FastAPI 서버 의존성; 없으면 `tests/server/test_app.py`가 skip된다. `train`은 PyTorch; 없으면 `tests/unit/training/test_torch_policy.py`가 skip된다).
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-09-23(tip census 뒤, WSL 노트북, master)의 기준 결과는 **pytest 1,885개 통과**(tip census 테스트 71개 + Influence 4 재도달 회귀 테스트 1개; 그 앞 `5bbad3a`까지는 1,813개), 실측. 이어서 비교 도구 테스트 1개로 1,886개 — 그 전체 실행에서 `tests/server/test_events_app.py::test_a_stream_closed_before_its_first_byte_is_not_a_server_error`가 한 번 실패했고(1,885 통과, 실패 메시지는 남기지 못함) 단독으로는 3회 모두 통과했다: 소켓을 곧바로 닫는 경합 테스트라 부하에서 흔들리는 후보다, Ruff 통과, mypy 통과. census 테스트가 스위트에 약 40초를 더한다(전체 약 4분). 2026-09-22 새벽(패널 문구의 용어집 잔재 뒤, Mac mini, 브랜치 `ui-glossary`)의 기준 결과는 **pytest 1,806개 통과**(같은 날 M10 평가 역전 수정 회귀 테스트 1개 추가, 실측)(한국어 텍스트의 용어집 영어 가드 1개), Ruff 통과, mypy 통과, 브라우저 E2E 15종 녹색. 그 앞 2026-09-21 밤(보드 위 사다우카 지휘관과 쌓인 Spy 뒤, Mac mini, 브랜치 `ui-commanders`)의 기준 결과는 **pytest 1,804개 통과**(카탈로그 테스트에 단언만 더함), Ruff 통과, mypy 통과, 브라우저 E2E 15종 녹색(`board_tokens.py` 187 → 203). 그 앞 2026-09-21 밤(UI 잔여 세 항목 세션 뒤, Mac mini, 워크트리 `ui-leftovers`)의 기준 결과는 **pytest 1,804개 통과**(라벨 표를 언어 전환에 등록했는지 보는 가드 1개 추가; 행동·이벤트 라벨 가드는 넓어졌지만 수는 그대로), Ruff 통과, mypy 통과, **브라우저 E2E 15종 녹색**(`log_words.py` 추가, `seats.py` 21 → 31, `remote.py` 57). 그 앞 2026-09-21 밤(Mac mini의 M10 순위 보상·대조군 세션 3커밋을 WSL 노트북의 UI 작업 위로 rebase한 뒤, Mac mini)의 기준 결과는 **pytest 1,803개 통과**(WSL의 1,802개 + 평가 seed 대역 테스트 1개), Ruff 통과, mypy 통과. rebase된 커밋은 UI 파일을 건드리지 않아 브라우저 E2E는 다시 돌리지 않았다. 그 앞 2026-09-21 저녁(보드 칸 테두리 세션 뒤, WSL 노트북)의 기준 결과는 **pytest 1,802개 통과**(칸 hotspot이 인쇄된 흰 테두리 하나의 크기, 관측소 원판이 칸 테두리와 겹치지 않음 — 레이아웃 테스트 2개 추가), Ruff 통과, mypy 통과, 브라우저 E2E 14종 녹색(`board_tokens.py`에 hotspot 테두리·Agent·Spy 말 검사 추가). 그 앞 2026-09-21 오후(UI 후속 세션 뒤, WSL 노트북)의 기준 결과는 **pytest 1,800개 통과**(언어 가드 `tests/server/test_i18n.py` 7개; supply 부족 `shortfall` 단언은 기존 테스트에 더함), Ruff 통과, mypy 통과, **브라우저 E2E 14종**(`help.py`·`lang.py` 추가). 그 앞 2026-09-21(UI 개선 세션 뒤)의 기준 결과는 **pytest 1,793개 통과**(UI 세션이 더한 7개: 용어 가드 3, event kind 가드 2, 지원하지 않는 룰셋의 400 1, action label 가드 1), Ruff 통과, mypy 통과. **브라우저 E2E는 8종 → 12종**이다(`endgame.py`·`narrow.py`·`columns.py`·`seats.py` 추가, `scripts/e2e/README.md`). 그 앞 2026-09-20(M10 자 만들기 세션 뒤)은 pytest 1,786개 통과이고 action codec은 **`ACTION_CODEC_VERSION = 107`**(기본 4,439개, CHOAM 4,729개, `promo_cards` 옵션 시 4,539/4,829개, `immortality` 옵션 시 9,324개, `promo_cards`+`bloodlines`는 10,580개, promo+Bloodlines+Tech는 13,828개, CHOAM+Bloodlines는 11,228개, 다섯 옵션을 다 켜면 32,987개 — v106은 Branching Path의 `trash_intrigue_for_agent_card`(Intrigue 사본마다)와 Imperial Privilege 행동의 이름 변경(`trash_intrigue_for_imperial_privilege`)·c7r3의 `trash_intrigue_for_research_bonus`, v107은 공용 `spy_placement` frame의 세 행동을 Bloodlines 없는 카탈로그에도 넣는다(+27); 형식 2 체크포인트는 행동 이름으로 이관된다 — 아래 세션 요약). 그 앞 기준선: 2026-09-19(두 기기의 2026-09-18 작업을 merge한 뒤)의 기준 결과는 pytest 1,768개 통과(같은 날 오후 학습률 재개 테스트 1개가 더해진 값; 그 앞 1,767은 Windows PC의 M10 PPO 슬라이스·A/B 세션 1,752개에 Mac mini의 보드 토큰·원판·보드 조각·에셋 버전 테스트 12개를 더한 값을 merge 뒤 실측했고, 같은 날 카탈로그의 Graft 표시 테스트 1개와 서버의 전투력 미리보기·남은 Persuasion 테스트 2개가 더해졌다; `assets` symlink가 없는 머신은 `tests/unit/display/test_images.py`의 에셋 대조 테스트 1개만 skip되어 1,767 통과 + 1 skip이다 — 2026-09-17 밤 symlink를 떼고 실측한 관계이며, 그 전 판들이 옛 기준선 1,489에 덧셈으로 유도해 적던 "1,6xx + 1 skip"은 실측과 맞지 않았다; `app.js`를 고쳤다면 pytest로는 부족하고 브라우저 E2E [`scripts/e2e/`](../scripts/e2e/README.md)를 돌린다; `train` extra가 없으면 `tests/unit/training/test_torch_policy.py`가 추가로 skip된다), Ruff 통과, mypy 통과다. 현재 action codec은 `ACTION_CODEC_VERSION = 105`(기본 4,371개, CHOAM 4,657개, `promo_cards` 옵션 시 4,471/4,757개, `immortality` 옵션 시 9,326개 — graft 배치 변형과 카드 사본이 늘 때마다 커진다; `bloodlines`·`tech_module` 옵션은 별도 카탈로그로 훨씬 크고, `promo_cards`+`bloodlines`는 10,513개, promo+Bloodlines+Tech는 13,759개, CHOAM+Bloodlines는 11,156개, 다섯 옵션을 다 켜면 32,991개 — v105는 Chani의 Fedaykin Maneuver `retreat_leader_troops`의 Commander share count를 `retreat_intrigue_troops`처럼 19까지 늘려 Bloodlines 카탈로그마다 +28(2026-09-18, 아래 세션 요약; 옛 v104 체크포인트는 형식 2로 새겨 두면 이관된다), v98은 CHOAM+Bloodlines 카탈로그에만 contract token 8개의 행동과 `trash_intrigue_for_contract`를, v99는 `recall_conflict_agent_for_imperial_privilege`를, v100은 모든 카탈로그에 `skip_intrigue_acquisition`과 Change Allegiances의 세 번째 option을, v101은 Immortality 카탈로그에 `play_conflict_end_intrigue`(Harvest Cells 2장)·`decline_conflict_end_intrigue`를, v102는 Bloodlines+Immortality 카탈로그의 `give_intrigue_card`/`trash_intrigue_hand_card`/`trash_intrigue_for_contract`에 빠져 있던 Immortality Intrigue 사본을 더한다 — 소크가 적발; v103은 모든 카탈로그에 `use_intrigue_effect(section=0/1)`·`finish_intrigue_effects`를 더하고 Change Allegiances의 option을 하나로 되돌린다; v104는 Bloodlines 카탈로그의 `retreat_intrigue_troops` unit count를 12에서 12+7로 넓힌다 — Commander는 12개 병력과 별개 구성물이라 Conflict 유닛이 19까지 가고 Tactical Option이 그 전부를 제시하는데 카탈로그가 12에서 끊겨 있었다, 병렬 수집이 적발, 카탈로그마다 +28)이고, 관측은 `OBSERVATION_VERSION = 20`의 4,327-int 전체 게임 인코딩이다(v6~v9는 Bloodlines·Tech Module 세그먼트를 더한 것, v10은 Bloodlines 프로모 Ruthless Leadership의 identity 1개, v11은 Immortality 카탈로그의 Imperium 25·Intrigue 11 identity, v12는 Experimentation·Tleilaxu 19 identity와 Bene Tleilax board 세그먼트, v13은 round 한정 Reveal Persuasion과 Combat Intrigue 좌석, v14는 Imperium Ceremony가 peek한 Intrigue 두 장(소유자 전용), v15는 Chairdog의 반환 대기와 Usurp의 빌린 Row 카드(좌석 scalar 49→51), v16은 Bloodlines contract token 8개의 identity(contract 세그먼트 11개 × 8 = +88), v17은 frame 종류 `conflict_end_trigger`, v18은 `intrigue_effects` 추가로 decision kind index가 이동, v19는 Long Live the Fighters의 두 단계 pick이 전용 frame 종류 `LONG_LIVE_FIGHTERS`로 옮겨져 decision kind index가 다시 이동(v17~v19는 모두 길이 불변), v20은 OQ-059의 보류된 contract 아이콘 좌석 scalar 1개(좌석 scalar 51→52, +4 int); 옵션을 끈 룰셋에서는 새 칸이 전부 0이지만 길이가 달라져 v8 이전 체크포인트는 거부된다) ([`rl-environment.md`](rl-environment.md)). 보드 22칸 완결 + 즉시 공개 + `fab266f`/`e6fc298` 수정 + sweep 확장(`853ecd4`) 반영 후의 교차 소크는 random 룰셋당 2,000판 + heuristic 룰셋당 1,000판(둘 다 `--rotate-leaders`) + draft 두 policy 각 룰셋당 500판, 전부 `--soundness-interval 25`를 켠 총 7,000판이 실패 0으로 통과한 상태다(2026-09-01, 아래 세션 요약. 그 전 단계에서는 random 룰셋당 3,000판 비회전 소크도 실패 0이었다).

## 현재 구현 기준선

마지막 커밋은 2026-09-20의 **전 좌석 AI 게임 관전**(`ac8cdeb`, 리플레이 검토의 자동 재생; 아래 세션 요약)이고, 그 앞이 같은 날의 **Staban Tuek draft pick 되돌리기 수정**(`8b6454e`, 서버 되돌리기 경계만; 아래 세션 요약)이고, 그 앞의 커밋 묶음은 같은 날 새벽의 **보드 조각의 인쇄 자리 배치·아이콘 전사 정정**(master 직접 커밋 4건 + 문서; 아래 세션 요약: Control·bonus spice·Maker Hooks·Alliance token의 인쇄 자리, Trash-Intrigue 아이콘 세 곳, Spy 배치 의무, Influence 4 보너스 — codec v107)이고, 그 앞의 엔진 커밋 묶음은 2026-09-16의 **공간 표 강등 마감 측정·수준 0.6 채택·OQ-060 확정**(master 직접 커밋 5건; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 18절(g)·(h))이고, 그 앞이 2026-09-11의 **보드 공간 표 상위 세 칸 강등 + OQ-060**(master 직접 커밋 2건: `94545a0` OQ-060 Influence 선택 소멸, 그리고 표 강등·Tech 특례 제거·문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 18절; **커밋 트리 확인 셀과 강등 수준 맞대결은 미완**)이고, 그 앞이 같은 날의 **Tech tile 가치표 A/B(기각)**(master 직접 커밋 1건; 코드 변경은 `HeuristicAgent`·`score_action`의 `tech_bonuses` A/B 슬롯과 테스트 1건뿐이고 `_TECH_BONUSES` 표는 그대로다; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 17절)이고, 그 앞이 같은 날의 **Tech Module 공간 표 A/B(기각)**(master 직접 커밋 1건; 코드 변경은 `heuristic_agent.py`·`registry.py`의 주석과 docstring뿐이고 배선은 그대로다; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 16절)이고, 그 앞이 2026-09-10 심야의 **확장 공간 순위·엔진 결함 3건**(master 직접 커밋 `2fa94d1`/`86c634b`/`aa46132`와 문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 15절)이고, 그 앞이 같은 날 심야의 **`agent_turn` spent-card 동점**(master 직접 커밋 `69bf880`와 문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 14절)이고, 그 앞이 같은 날 심야의 **처리량 회귀 귀인**(master 직접 커밋 `ab48e0c`/`88c0ef7`/`615e7ed`와 문서; 아래 세션 요약, 수치는 [evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md))이고, 그 앞이 같은 날 밤의 **보드 공간 재정비·잠재 결함 3건**(master 직접 커밋 4건, codec v103→v104; 아래 세션 요약)이고, 그 앞이 2026-09-10의 **문서 정정·학습 룰셋 배선·Long Live frame**(master 직접 커밋 `e0e364b`/`8b039dc`/`6c89a56`; 아래 세션 요약)이고, 그 앞이 2026-09-09 저녁의 **baseline agent Immortality 가치·엔진 교착 수정**(master 직접 커밋 3건 `21b5318`/`85bd179`/`3987126`; 아래 세션 요약, 세부는 [implementation-audits/immortality.md](implementation-audits/immortality.md) "baseline agent의 Immortality 가치" 절)이고, 그 앞이 같은 날의 **Bloodlines contract token 8개**(master 직접 커밋 `Play`/`Document` 쌍; 아래 세션 요약, 세부는 [implementation-audits/bloodlines.md](implementation-audits/bloodlines.md) "Contract token" 절)이고, 그 앞이 2026-09-08의 **M13 Immortality**(master 직접 커밋, 슬라이스 1~6의 `Play`/`Document` 쌍과 UI·소크 수정; 아래 세션 요약, 세부는 [implementation-audits/immortality.md](implementation-audits/immortality.md))이고, 그 앞이 같은 날의 **구현 마감 슬라이스**(master 직접 커밋 5건 + 문서)이다: OQ-047(Endgame tiebreaker에 garrison Commander 포함), Bloodlines 프로모 Ruthless Leadership(`promo_cards`+`bloodlines`, 관측 v10·codec v95), 서버 AI 좌석의 `rollout`/`checkpoint:` 연결, UI의 Agent 토큰 이동 애니메이션과 1700px 이하 오른쪽 패널 1열, Bloodlines+Tech 커버리지 census. 그 앞이 2026-09-07 밤의 **M12 슬라이스 7 마감**(master 직접 커밋 5건; 아래 세션 요약)이다: 웹 UI의 Commander·Skill·Ixian Embassy·Tech tile 표시, heuristic의 tile별 가중치와 rollout 자산 가치, `--bloodlines --tech-module` 교차 소크 7,000판 실패 0(적발한 결함 3계열 수정, OQ-046), 관측 v9 기준 학습 smoke, 저장 문서의 모듈 플래그 수정 — 이로써 **M12 완료**. 그 앞이 같은 날 저녁의 **M12 슬라이스 6 Tech Module**(master 직접 커밋 4건 + Navigation 대기열 수정 1건; 아래 세션 요약)이다: Ixian Embassy와 Tech tile 18장의 획득·할인·Flip·획득 효과·능력, Tech 전용 Imperium 2장·Intrigue 2장, Kota Odax of Ix(관측 v9, codec v91→같은 날 밤 사용자 검토로 v94, 판정 OQ-040~045). 그 앞이 같은 날의 **Bloodlines 확장 슬라이스 1~5**(`bloodlines` 브랜치를 master 쪽에서 머지, `dbd9b73`; 아래 세션 요약)이다: `RulesetConfig(bloodlines=True, tech_module=True)` 옵션 골격, Sardaukar Commander와 Skill 7종, Bloodlines Conflict 2장, Imperium 25종·Intrigue 16장, Leader 8종(Tuek's Sietch board space, Twisted Intrigue 12장, Navigation 10장 포함). 이로써 Bloodlines 구성물 전부가 play된다. 그 앞이 2026-09-06 밤의 **전투력 단일 값·표시 정리**(`rules/strength.py`의 매 step 갱신, 관측 v5, 전투력 토큰의 0 네모·`+20` 면, 좌석 패널의 검=전투력; 아래 세션 요약)이고, 그 앞이 같은 날 저녁의 **M11 UI 개선 묶음**(`ui-work` 워크트리 브랜치 12건: 호버 팝오버, 정적 파일 재검증, Conflict·Contract·Conflict 덱의 보드 슬롯 표시, garrison·Conflict 병력 칩, 공용 카드 열의 세로 배치, 행동 목록 포커스 정렬, 행동 로그 턴 카드·중립 카드, 오른쪽 패널 2열; 아래 세션 요약)이고, 그 앞이 같은 날의 **M10 슬라이스 1 학습 루프**(`train` extra, `training/network.py`·`torch_policy.py`·`checkpoint.py`·`learner.py`·`loop.py`, `dune-imperium-train`; 아래 세션 요약)이고, 그 앞이 같은 날의 **M9 슬라이스 3 lockstep self-play 러너**(`training/selfplay.py`·`training/policy.py`, `dune-imperium-selfplay`)이며, 그 앞이 같은 날의 **M9 슬라이스 2 rollout baseline**(`agents/rollout_agent.py`, `agents/determinize.py`, `StateAgent` 계약)이며, 그 앞이 같은 날의 **M9 슬라이스 1 대회 도구**(`dune-imperium-tournament`, `evaluation/` 패키지, `agents/registry.py`)이며, 그 앞이 2026-09-05의 **OQ-029 판정 구현**(Combat 배치의 회수·분할과 명시적 Agent turn 종료, codec v89; 아래 세션 요약)이고, 그 앞이 2026-09-04의 **조건 판정 시점 정리**(OQ-028: 미룬 Reveal 선택의 조건 재성립, Agent box 조건의 해결 시점 판정, Reveal 자동 조건부 이득의 늦은 지급; 아래 세션 요약)이고, 그 앞이 같은 날의 Reveal 선택형 효과 순서 자유화(`defer_reveal_choice`/`resume_reveal_choice`, codec v88)이며, 그 앞이 2026-09-03 심야의 자율 작업 5건(카드 Agent box 아이콘 분리 codec v87, 턴 종료 확인·되돌리기 가능 표시·보드 마커 UI)이며, 그 앞이 같은 날 밤의 **보드 공간 아이콘 분리**(인쇄 아이콘마다 `resolve_board_effect(effect=<key>)` 행동 하나, codec v86, OQ-027)이며, 그 앞의 기능 커밋 묶음은 2026-09-01 검증 강화 캠페인의 보드 공간 완결 슬라이스들이다: `d7703ef`(Dutiful Service CHOAM contract), `e141492` (Shipping, codec v80), `63a8994`(Desert Tactics, codec v81), `49a5bb6` (Imperial Privilege, codec v82, OQ-023), `78fa1a3`(Secrets chance 강탈, SECRETS_STEAL frame), `881d88b`(Reveal 중 hand 진입 카드의 FAQ p. 3 즉시 공개, OQ-015(c) 해소), `fab266f`·`e6fc298`(소크가 적발한 mid-frame trash 충돌 두 계열의 OQ-022 확장 수정). 이로써 **4인 보드 22칸 전부가 배치·해결 가능**하고 Reveal 중 draw/hand-acquire Plot 보류도 사라졌다. 그 앞은 `4c175d1`(카드 이미지 캐시 다운로드 스크립트)이고, 그 앞에 UI 효과 표시 작업의 `3e2ae8f`(행동 효과 미리보기 + 전체 행동 라벨), `d275a66`(보드 공간 패널·popover·카드 이미지), `d34a2d1`(/catalog 효과 텍스트·이미지), `a4befd4`(display 패키지), `3c1cc69`(정적 보드 효과 테이블), 그리고 M11의 `e44900a`(저장/불러오기/검토 브라우저 UI), 슬라이스 5 서버 API `8ab3cd2`, 브라우저 UI `42be883`, FastAPI 세션 서버 `4fbd751`, Leader draft `c0c1795`, Treacherous Maneuver OQ-022 수정 `d70b353`, 슬라이스 1 묶음(`1a449f4`+`7a53c8f`+`ac4d6d4`)이 있다. 마일스톤 현황: **R0~M8, M11 완료, M9 완료(대회 도구·rollout baseline·self-play 러너, 2026-09-06)**(M6 콘텐츠, M7 완주 검증, M8 CHOAM, M11 사람용 로컬 웹 UI — 슬라이스 7까지, 완료 판정 근거는 `implementation-plan.md` M11 절; Uprising 프로모 3장은 2026-09-03 저녁 `promo_cards` 옵션으로 구현 완료), **M10 진행 중(슬라이스 1 학습 루프 완료)**, **M12 완료(2026-09-07 밤, 슬라이스 7까지)**.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각, actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal, Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상, sandworm·Shield Wall·control, Makers·Recall, Endgame window와 게임 종료까지 실행할 수 있다.
- 시작 카드 7종, Reserve 2종, 기본 Imperium 50종, CHOAM 전용 Imperium 4종 모두에 완전한 play data가 있다(`implementation-audits/personal-cards.md`).
- CHOAM standard contract 20장의 시장·완료·보상과 CHOAM 전용 Imperium 4종이 연결돼 있다(`implementation-audits/contracts.md`).
- Intrigue 44장은 39개 identity 전부가 effect DSL로 전사돼 실제 play된다 (Intrigue 덱 완결). Plot은 소유자의 `turn`/`agent_effects`/`reveal` frame에서, Combat은 `combat_intrigue` frame의 priority 보유 참가자에게 제시된다. 선택이 필요한 효과는 `intrigue_choice` frame의 슬롯으로 순차 해결한다. Impress와 Inspire Awe의 비용 상한 획득은 `AcquireCardUpTo` 슬롯으로 Row/Reserve에서 가져오며, acquire box의 Spy 배치는 카드 해결 후 `acquisition_spy` frame을 재사용한다. Call to Arms와 Distraction은 face-up trigger 카드로, play하면 공개 `intrigue_faceup` 존에서 대기한다. Call to Arms는 소유자의 Reveal turn 획득마다 발동하고 그 Reveal 종료 시 만료되며, Distraction은 `PlayerState.units_deployed_turn` 카운터가 3에 닿은 뒤 매 전이 후 dispatcher가 `intrigue_trigger_spy` frame으로 제시하고 거절하면 face up으로 남는다(OQ-016, `rules/intrigue_triggers.py`, `implementation-audits/intrigue.md`).
- Intrigue deck 고갈 시 모든 draw 지점이 `pending_intrigue_draws` 큐를 거쳐 replayable reshuffle chance로 해결된다.
- 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두 play된다(`rules/leader_abilities.py`, `implementation-audits/leaders.md`). Lady Jessica의 flip 면은 `PlayerState.leader_face_id`, memory는 `memories`(troop 12개 불변식 포함), Feyd token은 `feyd_track_space`, Shaddam의 set-aside contract는 `GameState.sardaukar_contract_ids`로 공개 관측된다. 2026-08-30에 standard Contract manifest를 수정했다: Sardaukar II (Agent recall 보상)가 20장에 속하고, 이전에 있던 세 번째 High Council 타일은 Rise of Ix Tech 보상 타일의 오전사였다(`contracts.md` audit).
- 규칙 dispatcher는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS` 두 표로 동작한다(`refactoring-plan.md`).
- 코어 상태 머신과 replay는 전체 게임을 지원한다. `dune-imperium-sweep`으로 룰셋당 10,000판(총 20,000판) random 완주 sweep(매 전이 카드 보존·교착 검사, 표본 주기 관측 누출 검사, 게임별 replay 검증)이 실패 0으로 통과했다(2026-08-30, 400초/50 games/s).
- `run_random_game`이 FINISHED까지 실행해 `GameSimulation(state, standings, replay)`를 돌려주고, `dune_imperium_uprising_v1` PettingZoo adapter는 전체 게임을 한 episode로 실행한다(chance 내부 해결, 승자독식 zero-sum 종료 보상, 4,327-int 관측(v20), `choam_module`/`max_steps` 옵션). `run_random_round`와 debug CLI는 의도적으로 한 라운드 단위를 유지한다. 설계 근거는 [`rl-environment.md`](rl-environment.md).
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시 내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다. Bloodlines 룰북은 2026-09-07에 같은 방식으로 등록했다(`bloodlines`, 12쪽; 카드면은 비공개 에셋 저장소 `cards/en/bloodlines/`).
- Bloodlines(`RulesetConfig(bloodlines=True)`, 2026-09-07): 규범 근거 [`rules/bloodlines.md`](rules/bloodlines.md), 구현 노트 [`implementation-audits/bloodlines.md`](implementation-audits/bloodlines.md)와 [`implementation-audits/leaders.md`](implementation-audits/leaders.md)의 Bloodlines 절. Sardaukar Commander(`rules/sardaukar.py`, `rules/strength.py`), 새 아이콘(Command (6+), Combat 아이콘, Spy with Deep Cover, Trash an Intrigue card), 상대 결정 frame(`rules/spy_moves.py`, `rules/unit_loss.py`), Leader 전용 모듈(`rules/tactics.py`, `rules/planetologist.py`, `rules/optional_trash.py`, `rules/navigation.py`), Leader 전용 board space(`tuek_sietch`, `BoardSpace.required_leader_id`), Twisted Intrigue·Navigation 카드는 Intrigue 스키마의 `twisted`/`navigation` 항목(공용 덱에는 절대 들어가지 않음). Tech Module(`tech_module=True`, 2026-09-07 저녁): `content/bloodlines/tech.py`의 tile 18장, `rules/tech.py`(Acquire Tech·Flip·Forbidden Weapons 선택·Suspensor/빚진 draw hook·Endgame 효과·Kota의 Secret Project)와 `rules/ornithopter.py`, Tech 전용 카드 3종(`tech_only`), Kota Odax of Ix(`LeaderDefinition.tech_only`). 공식 문서가 침묵하는 판정은 OQ-031~046(사용자 판정 OQ-031·032·035·036·037·038·043·045 포함)과 OQ-012 재검토에 있다. 슬라이스 7(같은 날 밤): UI 표시(`server/catalog.py`의 `skills`·`tech` 절, `display/bloodlines.py`, `app.js`의 좌석 패널·공용 열·보드 칩), heuristic `_TECH_BONUSES`, rollout `player_value`의 Bloodlines 자산, 교차 소크 7,000판 실패 0, 학습 smoke.

## 아직 완성되지 않은 경계

- (2026-09-01 해소) 보드 22칸 미구현 4~5칸과 OQ-015(c)의 Reveal 중 Plot 보류는 모두 구현됐다. `board_effect_is_implemented`와 UI의 "미구현 · 배치 불가" 배지는 미래 콘텐츠 대비 메커니즘으로 남아 있고, `tests/unit/rules/test_board_effects.py`의 pinned 집합은 이제 양쪽 룰셋 모두 빈 집합이다. Imperial Privilege의 recall 판정은 OQ-023 convention, Secrets의 무작위 강탈은 seeded `SECRETS_STEAL` chance frame이다.
- (2026-09-04 해소, OQ-028) 배치 시점 조건이 거짓이면 pending되지 않던 카드 효과 경계는 사라졌다. 이제 space 속성·Bond를 제외한 모든 인쇄 조건은 해결 시점에 판정한다.
- Objective와 battle icon 상호작용은 2026-08-30에 재감사를 마쳤다 (`implementation-audits/objectives.md`, OQ-005 RESOLVED). Combat 다중 후보 guard는 미래 콘텐츠 대비 tripwire로 남는다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께 남아 있다. OQ-010(2026-09-02 확정), OQ-011 경계는 확정 판정(`DECIDED`)으로 유지된다.
- 공식 문서가 침묵하는 규칙 판정은 [`rules/open-questions.md`](rules/open-questions.md)에 있다. 2026-09-01 확정 캠페인과 같은 날의 사용자 검토를 거쳐, 2026-09-02에 OQ-010까지 확정돼 `DECIDED`/`RESOLVED`만 남았다가, 2026-09-04에 OQ-029(Conflict에 배치한 troop의 임의 회수·배치 분할)가 사용자 요청으로 `OPEN`으로 올라왔다가 2026-09-05 사용자 판정으로 `DECIDED`(회수·분할 허용, 소비된 조건은 예외)됐고 같은 날 구현했다. 2026-09-06에는 OQ-030(supply 부족으로 못 한 recruit의 소급 여부)이 `OPEN`으로 올라왔다가 같은 날 사용자 판정으로 `DECIDED`(해결 시점에 있는 만큼만 recruit, 부족분 소멸·소급 없음, `troops_recruit_short` 이벤트로 표시)됐다. 현재 콘텐츠에는 turn 중 troop을 supply로 돌려보내는 효과가 없고, Immortality의 lose a troop·specimen이 들어올 때도 같은 판정을 적용한다. `DECIDED`는 확정 프로젝트 판정으로 새 공식 룰북·FAQ(또는 OQ-022처럼 명시된 상위 근거)가 답을 줄 때만 다시 연다. 새로 발견되는 규칙 공백은 여전히 코드로 임의 확정하지 않고 그 문서에 먼저 기록하며, 규칙 동작을 바꾸기 전에는 반드시 `docs/rules/`의 문장을 인용한다([`lessons.md`](lessons.md)).

콘텐츠(카드·리더·계약·Intrigue·보드 22칸)는 이제 4인 base+CHOAM 게임 범위에서 완결이다. Uprising 프로모 Imperium 3장(Arrakis Revolt, The Beast's Spoils, Pivotal Gambit)은 같은 날 저녁 `RulesetConfig(promo_cards=True)` 옵션 콘텐츠로 구현됐고(기본은 꺼짐), 공식 문서가 침묵하는 판정은 OQ-024~026 project convention이다. 남은 경계는 공식 문서가 침묵하는 판정을 기록한 convention(open-questions.md)과 위의 엔진 경계·미래 콘텐츠 tripwire들이며, 이들은 "미구현 콘텐츠"가 아니라 문서화된 프로젝트 판정이다.

## 다음 구현 순서

**현재 위치(2026-09-21 밤).** UI 개선 0~6단계가 끝났다([`ui-improvement-plan.md`](ui-improvement-plan.md)의
5·6단계에 결과와 실측값). 앞 세션이 남긴 후보 가운데 사용자가 고른 셋(`remote.py` 위생·로그의 엔진 id·노트북
좌석)이 들어갔다. 학습 쪽 현재 위치는 아래 0번(M10)이 그대로다. UI에서 남은 것은 아래이며, **사용자가 고르기
전에는 시작하지 않는다**.

### UI 다음 후보 (2026-09-21 밤)

1. **첫 친구 판(M14의 남은 것) — 가장 값어치가 크다.** 원격 흐름·자동 저장·도움말·스크린 리더 알림·언어
   전환·노트북 화면의 좌석까지 준비됐다. 남은 것은 다른 집의 친구와 실제로 하는 한 판과 그 피드백이다([`remote-play-guide.md`](remote-play-guide.md)).
2. **용어집에 행이 없는 로그 낱말 — 룰북 인용이 먼저.** Other Memories, Secret Project, Wild card, Immediate,
   Usurp(계획서 6단계 "남은 것" 1; Gather Intelligence·Infiltrate·Family Atomics·set-aside는 2026-09-22에
   옮겼다). 한국어 룰북에서 찾아 용어집에 더한 뒤에만 바꾼다. 바꾸면 `test_i18n.py`와 `log_words.py`의 허용
   목록에서도 뺀다.
3. **한글 카드 스캔** — 확보하면 `display/images.py`가 코드 변경 없이 쓴다(언어 정책의 3번). **2026-09-22에
   네이버 블로그 사진에서 잘라낸 한글판 크롭 138장이 준비됐다**(아래 "2026-09-22 한글판 카드 사진 크롭" 세션
   요약) — `cards/ko/`에 넣기 전에 사용자 결정 셋이 남아 있다.

**UI를 이어갈 때의 규칙**(세 세션이 값을 치른 것들):
- `static/*.js`를 고치면 pytest로는 부족하다. [`scripts/e2e/`](../scripts/e2e/README.md) **15종**을 돌린다.
- 엔진 값을 화면에 낼 때는 `fieldText`(`core.js`)를 거친다. 새 종류의 id(관측소·연구 칸·Feyd 칸 같은)가
  생기면 거기에 한 가지를 더하고, `log_words.py`가 `prettify()` 호출과 id 모양을 잡는다.
- 목록 가드는 소스의 한 표기가 아니라 **실행되는 표**를 기준으로 한다(`ACTION_HANDLERS`), 화면 검사는 접힌
  것을 펴고 훑는다([`lessons.md`](lessons.md) 2026-09-21).
- 새 단언은 **옛 코드에 돌려 실패를 확인**한다(A/B). 앞 세션은 제안 30건 중 27건이 공허했고, 이번 세션은
  "필요한 조각이 들어 있다"만 보던 단언 셋이 결함을 통과시키고 있었다([`lessons.md`](lessons.md) 2026-09-21).
- 문자열은 `UI_TEXT` + `t()`/`tNode()`로만 쓴다. 한글 리터럴을 테이블 밖에 두면 `test_i18n.py`가 막고,
  한국어 모드의 영어 잔재와 영어 모드의 한글은 `lang.py`가 막는다. 규칙 낱말은 용어집(`TERMS`)에서만 —
  용어 낱말이 이미 명사를 품고 있으면(`{intrigue}` = 책략 카드) 뒤에 "카드"를 또 붙이지 않는다.
- 레이아웃·스크롤 주장은 **재 본 뒤에** 코드를 쓴다. 이번에는 CSS 주입으로 배치안 다섯을 먼저 쟀다.
- 키 입력은 `event.key`가 아니라 **`event.code`**로 맞춘다([`lessons.md`](lessons.md) 2026-09-20).
- 경합은 기기 속도에 맡기지 않고 `page.route`로 응답을 늦춰 강제한다(`spectate.py`).
- 학습이 도는 동안 이 체크아웃의 `src/`를 고치지 않는다 — **워크트리에서** 한다. 워크트리에는 git 밖의
  `assets` symlink와 `.venv`가 없으니 둘 다 걸고 `PYTHONPATH=<wt>/src E2E_REPO=<wt>`로 그 클라이언트를 띄운다.

### 학습(M10) 쪽 순서

**현재 위치(2026-09-22).** 결론과 근거는 한 곳에 모았다 — **[evaluation/m10-2026-09-22.md](evaluation/m10-2026-09-22.md)**(원자료는
git 무시 `checkpoints/2026-09-22/m10-evidence/`). 요지:
- **판정은 사후 대회 + `scripts/ab/paired.py`로만 한다**(2:2 미러, `--matches`, seed 군집 CI). 600경기의 분해능은 약 ±7.7%p,
  3%p를 보려면 약 15,800경기다. 학습 중 평가는 트립와이어다(이 주에 결함 둘을 고쳤다 — seed 반복 `f8e5a5f`, 역전 `fe2196c`).
- **가장 좋은 체크포인트**: `checkpoints/2026-09-21/long-2k/latest.pt`(iteration 5081; 쓰기 금지 복사본 `checkpoints/2026-09-22/exploit/champion-5081.pt`) — 출발점 2081 대비 2:2 미러 **+15.0%p**,
  heuristic 3명 상대 88.5%. 3081(`control-1k`)과는 잡음 안이다(+4.6%p 누적, 두 단계 모두 잡음 안).
- **현재 설정은 다시 정체했다.** 규칙 정정 직후 1,000 iteration의 +19%p는 옛 규칙 정책의 재적응으로 보이고(정황), 그 뒤
  2,000 iteration은 +3.0·+1.6%p로 잡음 안이다. **같은 설정을 더 돌리는 것은 기대값이 낮다.**
- **기각된 것**: 순위 보상(대조군과 직접 A/B 잡음 안), 학습률 조정(2026-09-19), 구매 강제(−17%p).
- **정책은 카드를 거의 사지 않고 그것이 옳다**(구매 강제 탐침). 저장소의 두 baseline(heuristic, heuristic playout의 rollout)은
  "많이 산다"는 같은 사전을 공유하고 둘 다 이 정책에 진다 — **배울 상대가 없다**.
- **착취자 실험(2026-09-22, 상대 다양화의 첫 단계) — 음성**: 얼린 5081만을 이기도록 2,000 iteration(학습 행 약 2,500만 =
  self-play 1,000 iteration 한 단계어치) 학습한 전용 정책이 1대3에서 **25.4% [23.1, 27.7]**(귀무 25%)다. 세 점 25.0 → 26.9 →
  25.4로 추세가 없고, 학습자 좌석 승률이 내내 평평하며 entropy는 오히려 올랐다. **5081은 제 분지 안에서 착취되지 않는다 —
  이 계보는 국소 최적이다.** 과거 체크포인트나 그 착취자로 짠 리그는 가르칠 것이 거의 없다([evaluation/m10-2026-09-22.md](evaluation/m10-2026-09-22.md) 11절).
  배치 상대와 `--learner-seats`(`3d8917c`)는 이 실험을 위해 들어갔다(1대3 수집 28.9 → 10.8초, 결정 단위 동일성 테스트).
- **정책 유도 탐색 — 성공(2026-09-23)**: 결정화는 그대로 두고 후보·플레이아웃·말단 평가를 네트워크로 바꾼 스크래치 변형
  `net_search_value`(`checkpoints/2026-09-22/search/tools/netsearch.py`)가 얼린 5081 셋을 상대로 **58.0% [48.3, 67.7]**(100판,
  귀무 25%, +6.7 SE), 평균 순위 1.740, VP 9.39 대 7.46이다. 3,000 iteration 학습이 1대3으로 약 +6%p를 냈는데 **탐색 하나가
  같은 네트워크로 +33%p**다. 숨은 정보 누출은 없다(결정화 30세계 확인). 비용은 결정당 2.0초
  ([evaluation/m10-2026-09-22.md](evaluation/m10-2026-09-22.md) 12절).
- **(a) 정식 편입 — 완료(`4b52b9e`)**: `agents/network_search_agent.py`의 `NetworkSearchAgent`와 registry의 `SEARCH_PREFIX`로
  **`search:<파일경로>`** 좌석이 생겼다. 서버는 좌석 종류를 `is_agent_kind()`로만 검증하므로 **플레이 서버 AI 좌석과 대회 도구가
  그대로 받는다**(원격 테이블에는 체크포인트처럼 파일 이름만 보인다). 스크래치 변형과 탐색 결정마다 같은 수를 두는 것을 확인했다.
  쓰는 법: `--agents "search:checkpoints/2026-09-22/exploit/champion-5081.pt,heuristic,heuristic,heuristic"`.
- **남은 것 — (b) 비용 줄이기부터**. 결정당 2.0초는 사람과의 한 판(AI 좌석당 약 7분)에는 쓸 만하지만 평가·학습에는 느리다.
  두 갈래: **큰 결정만 탐색**(합법 행동 중앙값이 2개라 대부분이 작은 하위 선택이다. 탐색이 네트워크 1순위를 실제로 뒤집는
  결정 종류를 먼저 재야 한다 — 그 census 스크립트가 `<scratchpad>/search_census.py`에 있고 아직 돌리지 않았다)과
  **플레이아웃 12개를 배치 추론으로 묶기**. 어느 쪽이든 줄인 뒤 **58%가 유지되는지 다시 재야** 한다.
  그 뒤: (c) M10 완료 표(탐색 대 heuristic·`rollout`), (d) 탐색의 선택을 학습 목표로 쓰는 expert iteration — 정체한 학습을
  탐색으로 다시 움직이는 표준 경로. 남은 옛 후보: 표현력, 처음부터 다른 seed, 구매 전문가 B1.
- **판정 비용 메모**: 탐색 좌석이 낀 1대3 셀은 한 판에 약 7분(탐색 좌석 약 205결정 × 2.0초)이라 4 worker로 100판이 3시간이다.
  1,400판짜리 표준 셀은 41시간이므로, 탐색을 싸게 만들기 전에는 **100판(±8.5%p)이 현실적인 상한**이다.
- **논의 중(2026-09-22, 코드 변경 없음): 사용자의 실전 팁을 학습에 쓰는 법** — [player-tips-for-training.md](player-tips-for-training.md).
  팁은 측정할 가설로 다루고 보상이 아니라 진단·평가 문제집·league 상대·입력 표현에 넣는다는 결론까지 왔다. 같은 날 밤
  Mac mini에서 이어 갔다(그 문서 6절, **이어갈 때는 6.8부터**; 저장소 코드 변경 없음, 원자료 git 무시
  `ab-runs/2026-09-22-thin/`): 사용자 답은 "안 사는 게 아니라 비싼 카드로 시작 카드를 대체한 얇고 강한 덱"이고, census로
  보니 5081의 덱은 **얇은 시작 덱**(판 끝 시작 카드 7.31장, 산 카드는 막판의 싼 카드)이다. 팁 1(Fremen 2 → Hooks →
  sandworm)은 정책이 이미 배웠다. 비용 문턱으로 거르는 얇은 덱은 heuristic 틀에서 단조롭게 진다(같은 조건 직접 −17.8%p).
  **옆길 발견: heuristic이 Tleilaxu 카드를 사지 않기만 해도 평소 구성에서 +21.8%p [+18.4, +25.1]** — 채택은 별도 작업
  단위·사용자 결정(6.5).
  **2026-09-23(WSL 노트북, 그 문서 7절, 이어갈 때는 7.6부터)**: 커뮤니티 팁 38개를 규칙 확인·측정 경로로 분류했다(엔진 불일치
  0, 테스트 공백 1건 메움). 그 측정을 한 명령으로 내는 **`scripts/ab/tip_census.py`**(수집기 `deck`·`combat`·`influence`·
  `endgame`)를 넣고 heuristic 기준값(3구성 × 100 seed)을 냈다. **다음은 Mac mini에서 같은 명령으로 5081 census** — 이 노트북에는
  체크포인트가 없다. Mac 스크래치 census와 heuristic 수치 일부(구매 수, Fremen 2 도달)가 어긋나 원인 미확정이므로 6.2·6.3의
  5081 대 heuristic 비교도 이 도구로 두 팔을 다시 낸다.
  **같은 날 사용자가 5081을 노트북에 가져와 census를 냈다(그 문서 7.7, 이어갈 때는 7.8부터)**: 정책은 Swordmaster 초반(79~94%)·
  Heighliner·sandworm·초반 폐기에서 팁과 같고, 초반 Faction 접근 카드(1~3라운드 0.67장, 팁 1~2장)·작게 이기기·tier III용
  garrison·이른 Reveal(0번)·Espionage에서 다르다. 1+3 표는 Mac 수치와 0.2 안으로 맞아 도구 정의 문제는 아닌 것으로 보인다.
  다음 1순위는 "기능으로 거른 H-deck" 정책 탐침(초반 Faction 카드 강제 구매, 덮어쓰기 에이전트부터 만들어야 한다).

아래는 그 앞의 기록이다(시간 역순이 아니라 적힌 순서 그대로 남긴다).

**이전 현재 위치(2026-09-17).** 전 확장 구성의 학습 전 최종 점검(파이프라인·heuristic·소크·open questions)이 끝났고 다음은 아래 0번의 **M10 학습 시작**이다. 그 앞 2026-09-16 심야에 M10 학습 전 마무리 세션이 끝났다. (1) `dune-imperium-train`은 관측 v20·codec v104에서
pure self-play(3 iteration × 32판, 8 worker, `--eval-every`)와 `--opponent rollout`/`--eval-opponent rollout`(StateAgent 경로)
모두 정상이다. (2) heuristic의 표 밖 항: 동점 census(게임당 228개 legal 집합이 RNG로 정해짐)로 지렛대를 찾아 세 가족 안
tie-break(Influence 진영·trash/discard 카드·같은 비용 구매)를 채택했고, 고정 변형 `heuristic_uniform_ties` 상대 전 축·두
seed 블록에서 **+5.1 ~ +9.1%p**다([evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md) 14절; 배치를 참는
규칙과 Plot 선출은 손해로 기각). (3) M10 수집 경로를 처음 프로파일해 관측 인코더(31%)를 바이트 동일하게 다시 써 수집
벽시계 **−16 ~ −18%**, 배치 handler의 guard 축소로 대회 경로 −3 ~ −4%([evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md)
8절). (4) A/B가 찾은 엔진 결함 1건(Reveal 중 Intrigue 비용으로 Conflict가 비면 Reveal frame의 전투력 집계가 stale, `a1c3f94`)을
고쳤다. rollout `player_value` 가중치 A/B·tie-break heuristic의 소크·기준선 12셀 재측정은 이 세션 요약(아래)에 적힌 대로다.
남은 것은 **M10 학습 재개**(사용자 결정)와 아래 0번의 학습 밖 후보다.

0. (**2026-09-20 주의 — 환경의 규칙이 바뀌었다**: Influence 4 보너스(Emperor Spy·Guild 3 Solari)·Spy 배치 의무·Branching Path·Imperial Privilege·c7r3, codec v107. 아래의 승률·대전 수치와 1650·2050 체크포인트는 전부 옛 규칙의 것이다. 형식 2 체크포인트는 v107로 이관되지만 **이어 학습하기 전에 새 규칙에서 다시 잰다**; 세션 요약 "보드 조각·아이콘 전사 정정"의 "M10에 미치는 영향".)
   (2026-09-19 저녁, **1650 출발 학습률 A/B 완료 — lr 1e-4와 3e-5는 구별되지 않고, 두 팔 모두 400 iteration 뒤에도 출발점 1650과
   같은 수준이다: 1400 무렵부터의 정체는 실재하고 학습률은 이번에는 지렛대가 아니다. 지금 도는 학습은 없다**;
   그 앞 2026-09-19 아침: 정체 해소 — 학습률 1e-4로 1650 iteration까지 상승)
   **M10 학습 — 전 확장 구성(codec v105, 32,991).** 경과(세션 요약 넷: "M10 첫 학습·되돌리기 루프·이관·codec v105",
   "M10 PPO 슬라이스·A/B", "학습률 실험·밤샘 실행 2", "M10 Mac mini 이관·실행 3"): (1) 첫 실행은 정책이 OQ-029의 `deploy_troops`/`withdraw_troops` 왕복을
   학습해 죽었고, 학습 수집·체크포인트 플레이에서 되돌리기 두 행동을 정책에 제시하지 않게 고쳤다([rl-environment.md](rl-environment.md)).
   (2) 학습률 3e-4의 첫 밤샘 실행은 400~550 iteration에서 정체했다(550: heuristic 3명 상대 200판 76.5%). (3) PPO(clip 0.2·3 epoch·
   32판 배치)는 A/B에서 43.0%로 무너져 기각, REINFORCE도 같은 학습률로는 평평했다. 가설: 배치의 독립 표본이 32판의 승패뿐이라
   갱신이 잡음에 끌려다닌다. (4) **학습률만 1e-4로 낮추자 정체가 풀렸다**: 550 → 650(100 iteration A/B)에서 81.0%, 이어진 밤샘
   1,000 iteration(9시간 50분, 재시작·예외·평가 실패·잘린 판 0)에서 학습 중 200판 평가가 74.7%(처음 다섯 평균) → 82.7%(마지막
   다섯 평균, 최고 1400의 87.5%). 대전(seed 1000+): 4자 400판 — 550 9.2%, 1000 21.8%, 1300 32.0%, 1650 37.0%; heuristic 3명 상대
   200판 — 550 76.5, 1000 79.5, 1300 84.5, 1650 83.0%. **1400 이후는 상승이 작다**(1400·1500·1600·1650의 4자 대전 24.2·24.8·23.0·
   28.0%, 표준오차 약 2.2%p). 한 계보·한 seed라 방향은 분명하지만 수치는 재현 전이다.

   **가장 좋은 체크포인트**: Windows PC의 `checkpoints/2026-09-18/lr1e-4-long/latest.pt`(iteration 1650, 옵티마이저 포함, 형식 2·codec
   v105, 235,035,727 bytes, sha256 `1a479e8e671095130d6602983a46aa8a44b290fdc6830b1db8e95642f691d2dc`)와 같은 시점의 번호
   체크포인트 `iteration_01650.pt`(79,799,975 bytes, sha256 `c32af167f1fd32288b7e46c49abcdc5c15ef9b21f572352a18e7c2e1bc128947`).
   `checkpoints/`는 git 무시라 **파일을 직접 복사한다**(Windows에서는 `\\wsl$\Ubuntu-24.04\home\cs\workspace\tabletop-ai\Dune-Imperium\checkpoints\2026-09-18\lr1e-4-long\`).
   복사 뒤 `uv run dune-imperium-checkpoint inspect <파일>`로 iteration 1650·codec v105·optimizer yes를 확인한다. 기록은 그 폴더의
   `SUMMARY.md`와 `checkpoints/2026-09-18/ab-550/SUMMARY.md`. **2026-09-19 오후 Mac mini에 복사돼 있고**(같은 경로), 두 파일의 sha256 일치와
   `inspect` 결과를 확인했다.

   **학습률 A/B(1650 출발, 사용자 결정 2026-09-19 15:40 — 후보 (b)) — 완료**, 기록은 `checkpoints/2026-09-19/ab-1650/SUMMARY.md`. 실행 3을
   2,081에서 손으로 멈춰 **(a) lr 1e-4 대조군**으로 삼고(비교는 `iteration_02050.pt`까지), 같은 `latest.pt`(1650, Adam 상태 포함)·같은 seed 0·같은
   설정에서 `--learning-rate 3e-5`만 바꾼 **(b)**를 `checkpoints/2026-09-19/lr3e-5-mac`에서 400 iteration 돌렸다(15:46~17:45; 첫 iteration은 두
   팔이 같은 게임을 수집했고, (b)의 `latest.pt`에서 Adam의 lr 3e-05와 이어진 step을 확인했다). 두 팔 모두 재시작·예외·평가 실패·잘린 판 0.
   - 학습 중 평가(200판, 1700~2050): (a) 84.5·87.5·81.0·81.0·80.5·79.5·81.0·86.0 = **82.6%**, (b) 87.5·84.0·78.0·82.5·83.5·85.0·87.0·86.5 =
     **84.2%**(평균 차 +1.6%p, 표준오차 약 1.5%p).
   - 대전(`ab-1650/evaluate.sh`; seed 1000+, `--rotate-leaders`, 실패 0): 4자 400판 — (b)2050 **27.8%**, 출발점 1650 **26.0%**, (a)2050
     **24.5%**, (b)1850 21.8%(표준오차 약 2.2%p, 두 행의 차는 약 3.6%p); heuristic 3명 상대 200판 — 출발점 1650 **83.0%**(Windows PC의 실측과
     같은 값 — 같은 seed가 두 기기에서 같은 판을 낸다), (a)2050 **88.0%**, (b)2050 **83.5%**.
   - **읽기**: 세 지표가 순서조차 일치하지 않고((b) +1.6, (b) +3.3, (a) +4.5) 전부 잡음 안이다 — 두 학습률은 구별되지 않는다. 그리고 **어느
     팔도 출발점보다 강해지지 않았다**: Windows 실행의 late 테이블(1400·1500·1600·1650 = 24.2·24.8·23.0·28.0%)과 합치면 1400 → 2050의 650
     iteration 동안 대전으로 잴 수 있는 상승이 없다. 3e-4 → 1e-4(550에서 100 iteration 만에 4자 33.0 대 24.5%)와 달리 이번에는 학습률이
     지렛대가 아니다. 한 계보·한 seed·팔당 400 iteration이라 몇 %p짜리 작은 효과는 배제하지 못한다.
   - **남은 가설과 다음 후보**(아래 "다음 후보"를 이 결과로 다시 읽는다): ① 배치 잡음 가설(ab-550의 "배치의 독립 표본은 32판의 승패뿐")은
     **개입으로 확인된 적이 없다** — 후보 (c) iteration당 64판이 그 개입인데, 이 Mac(16 GB)에는 지금 구조로는 들어가지 않는다(32판의 그룹 RSS
     최대 8.6 GiB: 메인 4.6 + worker 4개; 어림으로 64판은 16 GiB를 넘는다 — 재지 않았다). Windows PC(24 GB)에서 돌리거나, 메인이 mask를
     bit-pack한 채 들고 minibatch 때만 푸는 메모리 작업이 먼저다. ② **잣대의 해상도**: 1300 이후 모든 체크포인트가 heuristic 3명에게 83~88%를
     이겨 학습 중 평가는 더 가르지 못한다 — 평가 상대를 rollout이나 과거 체크포인트 테이블로 바꾸는 것(2번 항목의 league·평가 상대 교체)이
     정체를 "정체"라고 부르기 위해서도 필요하다. ③ 표현력(512-512 MLP)·탐험(entropy 0.01)은 아직 건드린 적이 없다. ④ 같은 설정으로 더
     돌리는 것((a)·(b) 어느 쪽이든 `--total`만 키우면 된다)은 기대값이 가장 낮다.
   **학습률 덮어쓰기 버그(`61b09df`)**: 옵티마이저 상태가 든 체크포인트에서 `--resume`하면 `--learning-rate`가 무시되고 저장된 rate로
   학습했다(`restore_optimizer`가 Adam의 `param_groups`를 통째로 복원) — 고치지 않았다면 (b)는 같은 seed의 1e-4 대 1e-4였다. 이제 인자가
   이기고 모멘트·step은 이어진다. 이전 실행들은 무관하다(실험 1은 옵티마이저 없는 `iteration_00550.pt`에서 시작, 밤샘 2는 저장값과 인자가
   둘 다 1e-4). **rate를 바꿔 재개하는 실험은 시작 직후 `latest.pt`의 `optimizer_state.param_groups[0].lr`을 읽어 확인한다.**

   **Mac mini 실행 3 = A/B의 (a)**(2026-09-19 13:36 시작, 15:42 중지; 세션 요약 "M10 Mac mini 이관·실행 3"): `scripts/train/`의 가드·감독기를 macOS로 옮겨
   검증한 뒤(커밋 `bd8732f`) lr1e-4-long과 같은 설정으로 1650에서 이어 띄웠다. 다른 것은 worker 수(8 → 4)뿐이다.

   ```bash
   .venv/bin/python scripts/train/train_overnight.py --detach --dir checkpoints/2026-09-19/lr1e-4-mac --total 1000 --repo . --start-from checkpoints/2026-09-18/lr1e-4-long/latest.pt -- --learning-rate 1e-4 --games-per-iteration 32 --workers 4 --minibatch 1024 --eval-every 50 --eval-games 50 --checkpoint-every 25 --choam --bloodlines --tech-module --immortality --promo-cards
   ```

   - **진행 확인**: `tail -n 2 checkpoints/2026-09-19/lr1e-4-mac/training.jsonl`(한 줄 요약은 `python3 scripts/train/fmt_iter.py <jsonl> <N번째 줄>`),
     끝나면 `supervisor.log`에 `supervisor-exit: finished: 1000 iterations`. **중지**: `kill -TERM $(cat checkpoints/2026-09-19/lr1e-4-mac/supervisor.pid)`.
     **더 돌리기**: 같은 명령의 `--total`만 키워 다시 띄우면 그 폴더의 `latest.pt`에서 잇는다(`--start-from`은 폴더에 기록이 없을 때만 쓰인다).
     실행은 세션과 분리돼(`--detach`) Claude 앱을 닫아도 돌고, 감독기가 `caffeinate`를 쥐고 있어 잠들지 않는다(이 Mac의 `pmset sleep`은 1분이다).
   - **학습 중에는 이 체크아웃의 `src/`를 고치거나 pull하지 않는다**(spawn worker와 지연 import가 작업 트리를 읽는다 — lessons 2026-09-16).
     문서와 `scripts/`는 괜찮다. 엔진·학습 코드 작업이 필요하면 워크트리에서 한다.
   - **이 Mac(M4 4P+6E, 16 GB)의 실측**: iteration당 약 16.5초(수집 8.9초 + 갱신 6.6초 + 235 MB `latest.pt` 저장; Windows PC는 약 33초) →
     1,000 iteration에 4시간 반쯤 + 평가 20회. worker는 **4가 최적**(같은 체크포인트에서 4·5·6·8·10 worker의 수집이 8.8·8.9·9.2·10.8·12.5초 —
     적을수록 빠른 원인은 재지 않았다). 8 worker 스모크의 그룹 RSS 최대 8.2 GiB·가용 최소 2.9 GiB, 4 worker는 8.6 GiB·2.6 GiB(worker당 최대
     1.4 GiB), 커널 메모리 압박 수준은 내내 정상이고 스왑은 늘지 않았다. `--resume`은 iteration 번호와 Adam 상태를 잇고, `--eval-games 50`은
     seed 수(좌석 회전 4배 = 200판, 오차 약 ±3%p)다.
   - **`--device mps`는 쓰지 않는다**(시험 완료): 같은 배치·가중치·옵티마이저 상태의 갱신 한 번이 CPU와 수치로 일치하고(통계 6자리 동일,
     파라미터 변화량의 상대 차이 1.4e-5, 다음 iteration이 같은 게임을 표본한다) 체크포인트는 어느 쪽이든 CPU 텐서로 저장되지만, 갱신이
     6.6 → 5.6초로 iteration의 5%쯤이라 무인 장시간 실행에서 검증 안 된 경로를 쓸 값어치가 없다.
   - **첫 50 iteration(1651~1700)의 실측**: 13분 19초, 수집 평균 9.0초·갱신 6.6초, 잘린 판 0, 게임당 765 step, 그룹 RSS 최대 8.7 GiB·가용 최소
     2.6 GiB·압박 수준 정상·스왑 증가 없음. 학습 중 평가(1700, 200판)는 **84.5%**(평균 순위 1.20, 실패 0; Windows 실행의 1600·1650은 85.5·84.5%)이고
     한 번에 약 95초다 → 전체는 5시간쯤, 18:40 무렵에 끝난다.
   - macOS의 메모리 중단은 가용 메모리 바닥이 아니라 커널 압박 수준(임계 두 번 연속)으로 한다 — 근거와 검증 범위는
     [`scripts/train/README.md`](../scripts/train/README.md) "메모리 중단 규칙". **임계 분기 자체는 실제로 일으켜 보지 않았다.**
   - **끝난 뒤 할 일**: lr1e-4-long의 `SUMMARY.md`와 같은 형식으로 대전 평가를 돌려 그 폴더에 `SUMMARY.md`를 남긴다. 그 조건(seed 1000+,
     `--rotate-leaders`, 4자 400판·heuristic 3명 상대 200판)으로 재구성한 명령은 아래와 같다(Windows PC 세션의 원 명령은 기록에 없다):
     `uv run dune-imperium-tournament --agents checkpoint:<A>,checkpoint:<B>,checkpoint:<C>,checkpoint:<D> --games 100 --start-seed 1000 --ruleset choam --rotate-leaders --promo-cards --bloodlines --tech-module --immortality --workers 4 --markdown <출력>`,
     heuristic 상대는 `--agents checkpoint:<X>,heuristic,heuristic,heuristic --games 50`. 계보를 잇는 비교가 되도록 1650(출발점)을 테이블에 넣는다.

   **다음 후보**(2026-09-19 아침에 적은 넷 가운데 (a) 같은 설정으로 계속과 (b) 학습률 3e-5는 위 A/B로 **끝났다 — 둘 다 1650에서 더 오르지
   않는다**): (c) iteration당 64판(128판은 24 GB에도 안 들어간다; 이 Mac에는 64판도 지금 구조로는 안 들어간다 — 위 "남은 가설" ①); (d) 두 번째
   seed로 재현; 그리고 위 ②~③(평가 상대 교체, 표현력·탐험). PPO는 큰 배치에서만 다시 볼 가치가 있다. 학습 밖 후보 (a)에 전 확장 census가 남긴 RNG 가족(graft 변형·partner, Commander skill,
   `take_contract`, Spy post, Engineered Miracle의 `command_acquire_row_card`)을 더한다. 열린 관찰: 첫 밤샘 실행 808 iteration의 잘린
   게임 1판은 재현되지 않았고, 16·24 worker가 8 worker보다 느린 원인은 재지 않았다.
0. (2026-09-17 자정 무렵, **M14는 실제 친구와의 한 판만 남았다 — 사용자 몫**) 슬라이스 1~5와 슬라이스 6의 리허설·운영 문서가 master에 있다(아래 세션 요약 셋). **판을 여는 법과 친구에게 보낼 안내는 [remote-play-guide.md](remote-play-guide.md)** 한 장에 있다: `caffeinate -i uv run dune-imperium-server --remote --host <이 Mac의 100.x 주소>` → 콘솔의 관리자 링크 → 방 생성 → 방 링크를 보낸다(이 Mac mini의 Tailscale 주소는 2026-09-17 현재 `100.87.236.12`; Tailscale 머신 공유 초대는 아직 보내지 않았다). 그 문서 끝의 **첫 실전 판 점검표**(친구 쪽에서 호스트 주소가 같은지, 보드 그림·한 수의 체감 지연, 신호음, 몇 시간짜리 연결, rollout AI 좌석의 멈춤 체감, 되돌리기·확정 흐름, 검토·순위표, WSL2)를 한 판 하면서 채우고, 나온 피드백이 다음 작업이다. **`app.js`를 고치면 [`scripts/e2e/`](../scripts/e2e/README.md)의 스크립트를 돌린다**(`remote.py`·`open_mode.py`·`races.py --ab`·`recovery.py`, 실전 전에는 `E2E_HOST=<100.x> rehearsal.py`; 스크래치 venv + 시스템 Chrome, 합쳐 3분쯤; pytest는 JavaScript를 실행하지 않는다). 설계 11절의 후속 후보(AI worker와 단계별 푸시, AI 대타, 관전자, 공개 터널용 에셋 게이트, 이름의 저장 파일 보존)는 실전 피드백이 요구할 때만 연다.
0. (2026-09-17, **슬라이스 1~5 완료 + 슬라이스 6의 리허설·운영 문서 완료, 실제 한 판만 남음**, 학습과 병행 가능) **M14 원격 멀티플레이.** 사용자 요구:
   "원격 친구들이랑 각자 PC에서". 설계는 [multiplayer-design.md](multiplayer-design.md)(같은 날 사용자가 D1~D7을 제안대로
   확정), 마일스톤은 [implementation-plan.md](implementation-plan.md) M14. 끝난 것: **슬라이스 1**(접근 계층: `server/access.py`,
   좌석 claim/release·관리자 쿠키·진행 중 seed 숨김·CLI `--remote`), **슬라이스 2**(`GET /games/{id}/snapshot` + 서버가 정하는
   로그 `epoch` + gzip, `app.js`의 single-flight `refresh`), **슬라이스 3**(초인종: `add_change_listener`·`DoorbellHub`·
   `GET /games/{id}/events`, 토큰 대조 presence `players[].online`, `EventSource` + 2초 폴링 fallback, 종료 신호에서 스트림을
   끝내는 CLI). **슬라이스 4 — 클라이언트 원격 UX**(설계 7절; **완료**, 위 항목과 아래 세션 요약 — 이하는 착수 전에 적은 작업 목록이다): (1) 진입 — `location.hash`의 `admin=`은
   `POST /auth/admin` 뒤 `history.replaceState`로 지우고, `game=`이면 `/me`(= snapshot의 `you`, 이미 `state.me`에 있다)로 내
   좌석을 보고 게임 화면 또는 좌석 고르기 화면으로; (2) `humanSeats()` 자리에 `mySeats()`(= `state.me.seats`; open 모드는 모든
   사람 좌석이라 지금과 같다); (3) claim 뒤 **스트림을 다시 연다**(스트림은 요청 시점의 쿠키로 presence에 등록된다);
   (4) 대기 배너("좌석 2 (이름) 결정 대기 중"·접속 끊김), 좌석 패널의 이름·접속 점, 내 차례 알림(탭 제목 + WebAudio —
   Notification·clipboard는 보안 컨텍스트 전용이라 Tailscale 평문 HTTP에서는 안 된다); (5) 이름은 `textContent`로만 그리고
   최종 순위표의 `innerHTML` 보간을 없앤다; (6) 남의 행동으로 인한 재렌더가 팝오버·스크롤을 끊지 않게(`render()`의
   `closePopover()`); (7) 호스트 패널(방 링크·좌석 현황·release, CLI `--public-url`), remote에서 설정 화면은 관리자만·Seed 입력
   숨김; (8) 403(좌석을 잃음)·`closed` 처리. 검증은 스크래치 Playwright의 브라우저 컨텍스트 여러 개(쿠키 분리)로 `--remote`
   서버에 대해: 방 생성 → 입장 → claim → 몇 턴 → 새로고침 복귀 → release → 재claim. 범위는 `server/static/`·`cli/server.py`·
   `tests/server/`뿐이라 codec·관측·저장 형식 버전은 그대로다. 브라우저 UI는 슬라이스 4부터 `--remote` 서버에서 동작한다.
   브라우저 E2E 스크립트는 [`scripts/e2e/`](../scripts/e2e/README.md)에 있고 실행 환경만 저장소 밖 스크래치다(WSL 박스: `uv venv` + `playwright` 모듈,
   캐시된 `~/.cache/ms-playwright/chromium_headless_shell-1234`를 `executable_path`로, 버전 심볼을 갖춘 `libasound.so.2`
   stub을 `LD_LIBRARY_PATH`에). 설계의 수치는 `uv run python scripts/measure_server_payloads.py --seed 20260917`로 재현한다.
0. (2026-09-16 심야, 완료 → 2026-09-17 0번) **M10 학습 재개**(관측 v20·codec v104라 체크포인트 전부 새로; pure self-play로 시작해
   25 iteration마다 재정비된 heuristic·rollout과 대회 평가; 첫 슬라이스 후보는 PPO 전환·league·평가 상대 교체 — 위 2번 항목).
   학습 밖 후보: (a) heuristic 표 밖 항의 나머지(14절(c) 끝: Spy post 규칙 재설계, `take_contract`, Intrigue option,
   확장의 graft partner·Commander skill; 같은 절차 — 스크래치 변형 → `heuristic_uniform_ties`류 **고정 대조군** 상대 축별
   2:2 → 채택), (b) rollout `player_value` 가중치(아래 세션 요약의 결과에 따라), (c) 처리량(throughput 8절(c): 상태 복사 구조
   변경, `_placements_for_card` 루프, provider fan-out), (d) 리팩토링 후속 4건([refactoring-plan.md](refactoring-plan.md); 이득
   대비 위험으로 보류), (e) 사람 플레이 피드백.
   **다른 세션에서 이어갈 때.** A/B·소크·프로파일 도구는 저장소의 [`scripts/ab/`](../scripts/ab/README.md)에 있다
   (2026-09-17 정리: census → `pypath/hvariants.py` 변형 → `sanity.py` → `cells.py` 축별 셀 → `pair_matrix.py`/
   `rollout_table.py` → `probe_mix.py` → 채택·고정 → `soak.sh`·`baseline_cells.sh`; 출력은 git 무시 폴더 `ab-runs/`).
   셀 하나(2:2 미러 500 seed)는 이 Mac에서 약 30초, rollout 셀(200판)은 약 6.5분, WSL2 8코어에서는 각 3.5분·30분쯤 잡는다.
   **대조군은 반드시 registry에 고정된 이름**으로 지정하고 셀이 도는 동안 `src/`를 편집하지 않는다([lessons.md](lessons.md)
   2026-09-16 둘째 항목). 2026-09-16의 원본 스크래치(측정 JSON·로그 포함)는 이 Mac의 세션 scratchpad
   `/private/tmp/claude-501/-Users-cs-Workspace-tabletop-ai-Dune-Imperium/d75b926e-.../scratchpad/`에 남아 있지만 재부팅·정리 시
   사라지며, 수치는 전부 [evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md)와
   [evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md)에 옮겨 적었다.
0. (2026-09-16 저녁, **완료**) 보드 공간 표의 좌표 하강은 18절(m)에서 멈췄다(상위 네 칸 소거 전부 ≤ 0).
   (a) **rollout 정비는 완료**(위 세션 요약; 원인은 playout 노이즈, 기본값 세계 4·후보 3·CRN).
   (b) **상향 소거 완료**(18절(n)): 내린 세 칸을 되돌리면 전부 손해, 낮은 칸(Research Station·Accept Contract·
   Gather Support·Shipping·Secrets)을 올려도 전부 손해이거나 잡음 — 표는 양방향 국소 최적이라 표 작업은 닫는다.
   (c) 아침 목록의 나머지: 처리량 후보([evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md)
   5·7절), 리팩토링 후속([refactoring-plan.md](refactoring-plan.md)), M10(최후순위).
0. (2026-09-16 **완료**) **Espionage 소거 후속.** 18절(l)의 소거가 Espionage(0.8)를 0.3으로 내리면 base +4.6·
   CHOAM +2.9·Tech +5.5·Immortality +5.2%p라고 했다. 같은 절차: (1) 0.3과 중간 수준 하나를 축별·둘째 블록으로
   `heuristic` 상대 재고, (2) 이기면 채택(이전 표를 registry에 고정하고 **모든 고정 표에 그 항목을 명시**), (3)
   채택한 표의 상위 항목을 다시 소거하고 probe로 mix를 적고, (4) 기준선 12셀을 다시 잰다. 스크래치
   `space-table-closeout/`의 `run_level9.sh`·`adopt_ds.py`·`run_round3.sh`·`write_l.py`가 이 순서의 본이다
   (다른 머신이면 18절의 정의로 재작성; 셀당 3.5분을 잡는다).
0. (2026-09-16 **완료**) **Deliver Supplies 소거 후속.** 18절(k)의 소거가 Deliver Supplies(0.7)를 0.3으로
   내리면 base +9.0·CHOAM +4.3·Tech +4.9·Immortality +4.2%p라고 했다. 이 절의 규칙대로 (1) 그 표를 축별(base·
   CHOAM·Bloodlines·Immortality·Tech 양쪽·CHOAM+Tech+Imm)·둘째 seed 블록으로 `heuristic` 상대 재고, (2) 이기면
   채택(0.3 아래 어디에 둘지 — 0.35 묶음 위/아래 — 두 수준), (3) 채택한 표의 상위 항목을 다시 소거하고 probe로
   배치 mix를 적는다(스크래치 `space-table-closeout/run_round2.sh`·`make_variants.py`가 이 순서를 자동화한다).
   Hagga Basin(+2.7, 경계)은 둘째 블록으로 판정한다.
0. (2026-09-16 **완료**) **공간 표 강등의 마감 측정.** 커밋된 표(Imperial
   Basin·Secrets·Arrakeen 0.3, 전 룰셋 공통)는 스크래치 변형 셀로만 검증됐다(18절). 할 일 순서:
   (1) (2026-09-16 완료 → 18절(g): Tech·Bloodlines·Immortality 소수점까지 재현, base+CHOAM 4,000판 중 4승 차) **커밋 트리 확인 셀** 6개 — 아래 명령을 그대로 돌려 18절(b)·(d)와 맞춘다(Tech CHOAM 없음
   셀은 `demote3_low` 행 28.1%/21.9%와 결정 수까지 같아야 한다); 결과를 18절에 "커밋 트리 확인"
   표로 붙인다. (2) (2026-09-16 완료 → 18절(h); **0.6 채택**, 사용자 판정 — 평소 구성인 CHOAM+Tech에서 0.6이 동률~+2.8%p라 Tech 특례 없이 표 하나: 0.6이 base +4.5·CHOAM +8.2·Immortality +5.6/+7.4%p, Bloodlines·CHOAM Tech는 동률, Tech CHOAM 없음은 −4.9/−5.9%p; 0.45는 0.3과 구분되지 않고 0.75는 전 축 손해; 0.6도 Tech에서 두 칸 표는 +3.4/+2.2%p로 넘는다) **강등 수준 맞대결** — 0.6(`demote3`)이 base+CHOAM에서 재정비 표 상대
   +15.8%p, 0.3은 +9.8%p였다(서로 다른 셀). `HeuristicAgent(space_bonuses={**UPRISING_SPACE_BONUSES,
   "imperial_basin": 0.6, "secrets": 0.6, "arrakeen": 0.6})`를 스크래치 registry에 등록해(17절
   방식; 스크립트는 이 머신의 `/tmp/dune-heuristic-space-table-2026-09-11/tech_ab.py`, 다른
   머신이면 18절의 정의로 재작성) `heuristic` 상대로 base+CHOAM·Bloodlines·Immortality seed
   0~499를 잰다. 0.6이 세 곳에서 이기면 표를 0.6으로 올리고 Tech 두 블록(seed 0~499·500~999)을
   다시 재서 두 칸 표를 여전히 넘는지 확인한 뒤 채택한다. (3) (2026-09-16 완료) OQ-060은 사용자 판정으로
   (a) 소멸을 `DECIDED`했다 — 문서만, 구현 불변. 명령:

   ```bash
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset base --bloodlines --tech-module --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset choam --bloodlines --tech-module --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset both --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset base --bloodlines --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset base --immortality --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --rotate-leaders --workers 7
   ```

   셀 하나는 8코어에서 약 3.5분(1,000 match)이다. 세 작업을 동시에 띄우면 서로 2~3배 느려지니
   순차로 돌린다.
1. (2026-09-11 **기각**) **Tech tile 가치표(`_TECH_BONUSES`) 재정비.** 18장 전체를 효과로 매긴 표와
   비용 가중 세 종(효과±0.15×비용, 비용만)을 Bloodlines+Tech(CHOAM 없음)에서 현행 표와 맞붙였고 전부
   ±2.2%p 안(`net` 두 블록 +0.8/+0.8%p, `effects` −0.4/+2.2%p), 일부러 싼 tile을 고르게 한 대조만
   −4.8%p였다(17절). tile별 구매 분포가 거의 균일해 순위표가 갈리는 결정 자체가 드물다 — 순위는
   지렛대가 아니다. 표는 그대로고 `HeuristicAgent(tech_bonuses=...)` 슬롯과 테스트 1건만 남겼다.
   다음 순위표 항목은 후보 2개 이상인 결정의 비율부터 잰다.
2. (2026-09-11 **기각**) **Tech Module의 공간 표.** 재정비 표 위에 Landsraad 다섯 칸의 Acquire
   Tech 값을 네 가지 방식(정적 δ, 살 수 있을 때만, 값 있는 tile일 때만, 여유 spice)으로 매겨
   Bloodlines+Tech에서 두 칸 표와 맞붙였고 **어느 것도 두 칸 표를 넘지 못했다**(16절). 정적
   δ는 클수록 나쁘고(−17 → −32%p), 게이트는 대조군(−13.6%p)과 같은 자리이며, 최선인 가치
   게이트는 대조군보다 일관되게 낫지만(차 기준 평균 +3.4%p) 네 블록에서 −7.3/−9.9/−1.1/−4.7%p로
   두 칸 표에 진다. 진단: tile 수는 회복되지만(좌석당 최대 4.07장, 두 칸 표 2.27장) 변형의
   Conflict 승수·VP는 움직이지 않고(2.04 → 2.12, 6.77 → 6.81), 두 칸 표는 Tech 없이 놀리던
   spice 11.7과 Landsraad 방문으로 tile을 얻어 득점한다(+0.5 VP); 그 기제는 미확정이다. 15절(b)의 "Landsraad를 끊어 tile을 못 산다"는 손실과 함께 움직인 지표였지
   원인이 아니었다([lessons.md](lessons.md) 2026-09-11). 배선은 그대로(Tech면 두 칸 표).
   **다음 후보**: (1) Tech 전용 표를 overlay가 아니라 **균형 재설계**로 — 재정비 표의 상위 세 칸
   집중(Imperial Basin 4.5·Secrets 3.9·Arrakeen 3.4/좌석, Combat 배치 53%)을 줄이고 Solari 공간을
   올려 tile을 여유 배치로 사게 하는 표; "값 있는 tile을 살 수 있을 때만 Landsraad" 조건은 단서로 남긴다;
   CHOAM off/on을 **따로** 잰다(재정비 표의 Tech 손실은 CHOAM 없음 −13.6/−9.9%p, CHOAM
   −6.2/−6.9%p로 갈린다). (2) `_TECH_BONUSES` 재정비(Forbidden Weapons·Rapid Dropships가
   0)는 별도 항목. (3) 이 룰셋의 진짜 답은 M10 학습 정책이다.
2. (2026-09-10 완료) **[OQ-059](rules/open-questions.md#oq-059--시장에-face-up-contract가-남았지만-아무것도-가져갈-수-없을-때의-contract-아이콘)**
   — 판정(보류 후 불발)과 구현을 같은 날 끝냈다. 관측이 v20으로 올라갔다.

**`agent_turn`의 카드 동점**은 끝났다(14절) — 다만 앞 세션이 "남은 동점 995개"로 적은 값은
**재정비 표를 전 확장에 강제 적용한** probe의 수치이고 그 배선은 저장소에 없었다.

**완료(2026-09-08, 사용자 지시 "Immortality 확장 구현"): M13 Immortality.** 슬라이스 1(출처·명세·옵션 골격·board 전사·카탈로그)과 슬라이스 2(Bene Tleilax board의 상태·행동, specimen, 개정 Research Station, Experimentation, Family Atomics; OQ-048~051; 관측 v12, codec v96), 슬라이스 3(Tleilaxu Row 획득·Reclaimed Forces·획득 box의 Research/Tleilaxu·첫 Tleilaxu 카드 3장), 슬라이스 4(Graft: `agent_turn`의 `graft` 인자 + `graft_partner` frame + `switch_graft_card`; Graft 카드 8장), 슬라이스 5a(Intrigue 11장 전부, 관측 v13), 슬라이스 5b-1(Imperium 15종: 조건부 Agent 아이콘·획득 box·trash trigger·Reveal Tleilaxu/Research·specimen 지불; codec v97), 슬라이스 5b-2(남은 Imperium 8종 — Intrigue peek frame·Reveal choice 3종·조건부 획득; 관측 v14, OQ-052~053)는 완료했고, 슬라이스 5c-1(Tleilaxu 6종 + 프로모 Piter), 슬라이스 5c-2(Ghola·Chairdog·Usurp; 관측 v15, OQ-054~055)도 완료해 **Immortality의 카드 play data는 전부 끝났다**. 슬라이스 6(UI 표시·대규모 소크 830판 실패 0·census)도 끝나 **M13은 완료**다. 남은 후속은 [implementation-audits/immortality.md](implementation-audits/immortality.md)의 "미완 경계"(board 스캔 오버레이, heuristic/rollout 가중치, 관측 v15로 학습 재개). 다음 작업은 아래 목록의 M10(학습, 사용자 결정으로 최후순위) 또는 사용자가 정하는 새 항목이다. 전사는 [implementation-audits/immortality.md](implementation-audits/immortality.md)에 있다. 설계 메모: Ghola는 활성 카드의 `agent_effect`를 읽는 41곳(`agent_effects.py`)을 접근자(`active_agent_effect(context)`)로 모아 상대 카드의 box를 돌려주게 하고, Usurp는 `choose_graft_partner`에 Imperium Row instance를 허용하고 좌석에 `usurped_row_card_id`를 두어 turn이 닫힐 때 자동으로 trash하며(트리거 발동, OQ-054 사용자 판정), Chairdog는 좌석에 `chairdog_return_card_id`를 두어 `begin_reveal_turn` 앞에서 hand로 되돌린다. Harvest Cells는 Combat 중 Tleilaxu 획득 진입점(DSL 보상 `AcquireTleilaxuCard`)이 필요하다. 그 뒤 6(UI·heuristic·소크). 세부는 [implementation-plan.md](implementation-plan.md)의 M13 절. 공식 문서가 침묵하는 판정은 구현할 때 open-questions에 등록한다(후보는 audit 문서의 "미완 경계").

2026-09-01의 **검증 강화 캠페인**(사용자 확정 범위: 전체 1→4)은 같은 날 완료했다: 1단계 보드 22칸 완결 + OQ-015(c), 2단계 sweep 확장 (`853ecd4`: 커버리지 census `--coverage-json`, 표본 주기 legal-action 전수 적용 + codec 왕복 `--soundness-interval`, seed별 리더 회전 `--rotate-leaders`), 3단계 교차 소크(아래), 4단계 대조(DIU 63종 전부 일치, open-questions 23건 재점검). 세부는 아래 세션 요약.

0. (2026-09-10 완료) **문서 정정 + 학습 룰셋 배선 + Long Live frame** — 아래 세션 요약. 이로써 M10의 코드 전제조건이 없어졌다: `dune-imperium-train`이 `--promo-cards`/`--bloodlines`/`--tech-module`/`--immortality`를 받는다. **다음 작업 후보**: (a) 기준선 리포트 재측정(`dune-imperium-tournament`가 확장 플래그를 이미 지원하므로 코드 작업 없이 실행만), (b) M10 학습 재개(관측 v19라 새로 시작), (c) `refactoring-plan.md`의 남은 코드 리뷰 후속.
0. (2026-09-08 저녁, **다음 작업 후보**) **디자이너 커뮤니티 판정 대조 후속** — 사용자가 가져온 BGG/Discord 판정 정리본(elessar의 "DUNE IMPERIUM FAQ", 2026-06-07판)을 구현과 대조해 [rules/designer-rulings-audit.md](rules/designer-rulings-audit.md)에 남겼다(아래 세션 요약). 불일치 13건은 **반영 미결정**이며 사용자가 항목을 고르면 OQ 등록 → 규칙 문서 → 테스트 → 엔진 순으로 진행한다. 가장 큰 묶음은 "효과는 발동 시점을 하나 고르고, 조건이 거짓이면 turn 종료까지 보류"(OQ-028(a)·(c), OQ-002, Guild Spy·Interstellar Trade)이고, 그 밖에 Choose Two 원자성(Propaganda·Stitched Horror·Rapid Engineering), Impress·Change Allegiances의 play 조건, Usurp+Stillsuit, Tech Intrigue의 decline, Ceremony+Suspensor, Harvest Cells 보상 즉시 play, Ghola+Long Reach, Tleilaxu Master가 있다. 콘텐츠 공백이던 **Bloodlines contract token 8개**는 2026-09-09에 전사·구현했다(아래 세션 요약). 사용자 결정(2026-09-09): 불일치 13건은 **디자이너 판정을 무조건 따라** 반영한다 — 추가 확인 2건과 5·6·7·8·9·10·12·13은 반영했고(OQ-057, OQ-002·OQ-054·OQ-037 보강), 13건 전부 반영했고(OQ-057), Intrigue 줄의 개별 사용·지불(OQ-058)도 구현했다. 다음 후속 후보 중 (a) 대규모 소크 재실행과 (b) heuristic/rollout의 Immortality 가치는 2026-09-09 저녁 세션으로 끝났다(아래 세션 요약; 소크 1,300판 실패 0, A/B로 엔진 교착 1건 적발·수정). 남은 것은 (c) M10 학습 재개다(2026-09-10 기준 관측 **v19**·codec v103이라 체크포인트 전부 새로. 확장 룰셋 배선은 2026-09-10 세션으로 끝났다).
0. (2026-09-08 완료) **구현 마감 슬라이스** — 아래 세션 요약. 사용자 결정(2026-09-08): **학습(M10)은 최후순위**로 미루고 구현을 먼저 완결한다. 이 세션으로 핸드오프에 남아 있던 구현 항목 네 가지(OQ-047 판정, 서버 AI 좌석 연결, UI 후보 2건, census 재점검)와 사용자가 추가한 Bloodlines 프로모 카드가 끝났다. 남은 구현 후보: (a) 학습 루프의 `--bloodlines`/`--tech-module`/`--promo-cards` 옵션(아래 (b))은 M10에 속하므로 학습 재개 때 함께; (b) 사람 플레이에서 발견되는 UI·규칙 이슈(사용자 플레이 피드백 대기); (c) 새 공식 FAQ가 나오면 `DECIDED` 항목 재점검. 그 다음이 M10 계속(관측 v10·codec v95라 기존 체크포인트는 전부 거부되므로 새로 시작).
0. (2026-09-07 밤 완료) **M12 슬라이스 7 마감** — 아래 세션 요약. M12는 완료다. 당시 다음 후보: (a) **M10 계속**(아래 2번; 관측 v9·codec v94라 기존 체크포인트는 전부 거부되므로 새로 시작한다 — 이 세션의 smoke `--iterations 3 --games-per-iteration 32 --workers 4`가 정상 동작을 확인했다); (b) 학습 루프의 `--bloodlines`/`--tech-module` 옵션(`training/collect.py`·`loop.py`·`torch_policy.py`의 룰셋 표기가 `choam` 하나뿐이고 체크포인트 룰셋 문자열도 그렇다; Bloodlines 카탈로그는 크기가 달라 별도 네트워크가 필요하다); (c) `implementation-audits/bloodlines.md` 미완 경계의 Endgame tiebreaker Commander 계수 판정(OQ 등록 필요); (d) 서버 AI 좌석의 `rollout`/`checkpoint:` 연결. 원래 슬라이스 7 계획 항목(참고): (a) 서버·UI의 Bloodlines·Tech 표시 마감 — 보드 위 Commander 토큰·Skill·Ixian Embassy(세 stack의 face-up tile)·보유 Tech tile(Flip 면)·Secret Project 표시, Tech tile 이미지 키(`display/images.py`의 required keys에 `tech` 종류 추가 + 비공개 에셋 manifest의 `bloodlines/tech/*.webp` content id), 새 frame(`tech_acquisition`·`tech_choice`·`tech_secret_project`·`skill_choice`)의 프롬프트·카드 표시; (b) heuristic agent의 가중치 정비(현재 `acquire_tech` 2.5로 비용 무관, `flip_tech` 1.5, Forbidden Weapons 검 우선; tile 비용·잔여 spice·능력별 가치 반영), rollout의 `position_value`에 Tech tile 가치 추가; (c) `--bloodlines --tech-module` 대규모 소크(random 룰셋당 2,000판 + heuristic 1,000판 `--rotate-leaders`, draft 500판, `--soundness-interval 25`); (d) 관측 v9 기준 학습 재개(v8 이전 체크포인트는 로더가 거부하므로 새로 시작하거나 옛 가중치 이어 쓰기 로더를 먼저 만든다). 열린 판정 후보: Endgame tiebreaker의 garrison troop 수에 Commander를 세는지(`implementation-audits/bloodlines.md` 미완 경계).
0. (2026-09-07 완료) **M12 Bloodlines 슬라이스 1~5** — 아래 세션 요약.
0. (2026-09-06 밤 완료) 전투력 단일 값(`combat_strength`를 Agent turn부터 매 step 갱신, 관측 v5) + 전투력 토큰·좌석 패널 표시 정리 — 아래 세션 요약. 학습 재개 시 v4 체크포인트는 못 읽으므로 새로 시작하거나 옛 가중치 이어 쓰기 로더를 먼저 만든다.
0. (2026-09-06 저녁 완료) M11 UI 개선 묶음(호버 팝오버, 보드 슬롯의 Conflict·Contract·덱, 병력 칩, 카드 열 세로 배치, 행동 로그 턴 카드) — 아래 세션 요약. 열린 UI 후보: 보드 위 Agent 토큰 이동 애니메이션, 1600px급 화면에서의 오른쪽 패널 2열 기준 조정, 서버 AI 좌석에 `rollout`/`checkpoint:` 연결.
0. (2026-09-03 완료) M11 슬라이스 7 보드 스캔 테이블 + 룰북 아이콘 — 아래 세션 요약. (2026-09-02 완료) 슬라이스 6 행동 되돌리기 + 실시간 행동 로그.
0. (2026-09-06 완료) M10 슬라이스 1 학습 루프(`train` extra, 네트워크·learner·체크포인트·`dune-imperium-train`) + 첫 체크포인트(heuristic 3명 상대 56%) + Imperial Privilege 교착 수정 — 아래 세션 요약.
0. (2026-09-06 완료) M9 슬라이스 3 lockstep self-play 러너(`training/`, `dune-imperium-selfplay`) — 아래 세션 요약. 이로써 M9 완료.
0. (2026-09-06 완료) M9 슬라이스 2 rollout baseline(`RolloutAgent`, determinization, `StateAgent`) — 아래 세션 요약.
0. (2026-09-06 완료) M9 슬라이스 1 대회 도구(`dune-imperium-tournament`) + 첫 기준선 보고서 — 아래 세션 요약.
0. (2026-09-06 완료) OQ-029 구현 검토 + recruit 부족분 이벤트 + OQ-030 판정(해결 시점·소급 없음) — 아래 세션 요약.
0. (2026-09-05 완료) OQ-029 판정 구현 — Combat 배치의 회수·분할과 `finish_agent_turn`(codec v89). 아래 세션 요약.
0. (2026-09-04 완료) 조건 판정 시점 정리(OQ-028) — 아래 세션 요약. 같은 날 병력 회수 규칙은 OQ-029 `OPEN`으로 등록했고 2026-09-05에 판정·구현했다.
0. (2026-09-04 완료) Reveal 선택형 효과 순서 자유화(codec v88) — 아래 세션 요약. 이로써 2026-09-03 심야의 사용자 5건이 모두 끝났다.
0. (2026-09-03 심야 완료) 사용자 5건 중 4건 완료 + 1건 부분: 카드 Agent box 아이콘 분리(codec v87), 되돌리기 가능 표시, 턴 종료 확인, retreat 규칙 확인(문서), 보드 마커.
0. (2026-09-03 밤 완료) 보드 공간 아이콘 분리(OQ-027, codec v86) — 아래 세션 요약.
0. (2026-09-03 저녁 완료) Uprising 프로모 Imperium 3장 — 아래 세션 요약.
1. **M9 평가 러너와 baseline — 2026-09-06 완료.** (1) 대회 도구 + 지표(`dune-imperium-tournament`; 기준선 `docs/evaluation/baseline-2026-09-06.md`), (2) rollout/search baseline(`RolloutAgent`, registry 이름 `rollout`; heuristic 3명 상대 48% 승률, 결정당 약 25ms), (3) lockstep self-play 러너(`training.SelfPlayRunner`: 게임 여러 판을 한 번에 돌리며 좌석별 정책 이름으로 요청을 묶어 정책당 한 번 `act`; `Episode`/`stack_episodes`가 관측·mask·행동·좌석·종료 보상 배열을 내놓는다; `dune-imperium-selfplay` 처리량 약 4,900 decisions/s). 선택 과제(필요할 때): rollout 강화(후보·determinization 수, 2라운드 horizon, 값 함수 가중치)와 M11 서버 AI 좌석에 `rollout` 추가(서버 `sessions.py`는 아직 `choose_action`만 호출하므로 `StateAgent` 경로를 연결해야 한다).
2. **M10 강화학습과 league self-play(진행 중).** 슬라이스 1(2026-09-06 완료): PyTorch `train` extra(사용자 결정: 이 Mac에서 시작, 코드는 `--device cpu|mps|cuda|auto`로 장치 독립, 규모 확장은 RTX 3080 PC에서), masked policy/value MLP(`training/network.py`), 체크포인트(관측 v4·codec v89·룰셋 기록, 불일치 거부), `TorchBatchPolicy`(표본/greedy + 순환 방지)와 `NetworkAgent`(`checkpoint:<경로>`로 대회 참가), REINFORCE + value baseline learner, `dune-imperium-train` 루프(수집 → 갱신 → JSONL 로그 → 체크포인트 → 주기적 대회 평가). 첫 smoke(같은 날, `docs/evaluation/baseline-2026-09-06.md` 5절): pure self-play 30 iteration × 32판(약 6분, CPU)으로 만든 체크포인트가 random 3명 상대 100%, heuristic 3명 상대 56%(rollout 48%보다 높음). `--opponent heuristic`으로 시작하면 초기 정책이 한 판도 못 이겨 신호가 없으니(승률 0%로 20 iteration 정체) pure self-play로 시작한다. 슬라이스 2(같은 날): `--workers N` 병렬 수집(`training/collect.py`; 8 worker로 약 8,500 decisions/s, 단일 3,600), learner의 값 계산 minibatch 분할(메모리 상한), `--step-penalty`(기본 0.0005/결정, 학습 쪽 shaping)와 학습 게임 상한 4,000 결정 — 150 iteration 실행이 41 iteration에서 정책의 되돌리기 반복 학습(게임당 결정 680→1,793)으로 메모리 부족사한 사건의 수정(`lessons.md` 2026-09-06 항목). 두 번째 체크포인트(100 iteration × 64판, 14분): heuristic 3명 상대 89%, 첫 체크포인트 상대 61%, rollout 상대 67%(`baseline-2026-09-06.md` 6절) — 현재 champion. 그 뒤 sampling에도 순환 방지를 적용(`cf24f35`; 이 체크포인트에는 미적용). 비교 실험(사용자 지시, 같은 날 밤): sampling 순환 방지를 켠 제로부터 재학습은 25 iteration에 entropy 0.20·게임당 1,301 결정으로 붕괴해 중단했고(`baseline-2026-09-06.md` 7절; 가려진 행동 대신 다른 되돌리기 변형으로 반복, learner에 off-policy 보정이 없음) sampling 쪽 순환 방지는 되돌렸다(greedy 전용 유지). latest.pt에 optimizer 상태를 실어 `--resume`가 Adam moment까지 잇는다(`2b5dfc3`). 체크포인트 보관 위치: 저장소 루트의 git 무시 폴더 `checkpoints/2026-09-06/`(`.gitignore`)의 `champion_6min_iter30.pt`(5절), `champion_iter100.pt`(6절), `champion_iter200.pt`(8절, 현재 champion, optimizer 상태 포함)와 각 구간의 `training_*.jsonl`. git에는 넣지 않으며(14~40MB), 다른 머신으로는 파일을 복사해 `checkpoint:<경로>` / `--resume <경로>`로 쓴다. 이어서 학습(사용자 지시): 200 iteration 체크포인트가 100 iteration champion 3명 상대 35%(동률 기대 25%), heuristic 상대 91%(`baseline-2026-09-06.md` 8절) — 현재 champion. 그 대회에서 학습 정책이 두 번째 엔진 결함(recall-first Spy 배치의 supply 판정 시점, `[Main pp. 11, 20]`)을 찾아 수정했다. 다음 슬라이스 후보: (a) **3080 PC에서 300+ iteration** — `--resume`으로 잇고 champion과 25 iteration마다 대전; 개선 폭이 줄고 있으니(61% → 35%) 정체하면 (b) 학습률 낮추기·entropy 조정·hidden 확대·PPO(수집 시 log-prob 기록 + clip + 여러 epoch)를 차례로 시험한다. (c) heuristic 상대 승률은 90%대로 포화했으므로 평가 기준 상대를 rollout과 직전 champion으로 바꾼다. (b) 정체하면 학습률·entropy·표본 온도·value 가중치·hidden 크기 조정, PPO 전환. 원래 후보 (a)였던 **더 길게 학습하고 champion 비교** — 100~300 iteration을 돌리며 `dune-imperium-tournament`로 이전 체크포인트·rollout과 직접 대전(3080 PC로 옮겨도 된다; 코드는 `--device auto`); 정체하면 학습률·entropy·표본 온도·value 가중치·hidden 크기를 조정하고, 필요하면 PPO(clip + 여러 epoch; 수집 시 log-prob 기록 필요)로 바꾼다. (b) 수집 병렬화 — `SelfPlayRunner`는 단일 프로세스라 학습 시간의 대부분이 수집이다; worker 프로세스마다 네트워크 사본을 두고 episode를 모으는 방식이 가장 단순하다. (c) league — lineup에 과거 체크포인트(`checkpoint:` 이름은 `AgentBatchPolicy`로 바로 쓸 수 있다)와 rollout을 섞는다. (d) 관측 전처리 개선(카드 identity 임베딩 등)은 (a)가 안정된 뒤. 학습 seed(2,000,000 + seed×1,000,000부터)와 평가 seed(대회 기본 0부터, policy offset 900,000)는 분리돼 있다.

각 묶음은 카드 이미지로 텍스트를 검증하고(`docs/card-data-sources.md`의 방법), `Play ...` / `Document ...` 커밋 쌍을 유지하며, 새 결정 경계는 `FrameKind` → frame `kind` → dispatcher 표 → codec 순으로 추가한다. 핸드오프의 카드 요약은 이미지 검증 전 참고일 뿐이다(Impress 비용, Spring the Trap 유형을 잘못 적었던 전례가 있다).

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` (Leader identity·Feyd track은 `leaders.py`) |
| Leader 능력과 Signet Ring | `src/dune_imperium/rules/leader_abilities.py`, reach-2 보너스와 Navigation trigger는 `rules/influence.py`, Staban의 Smuggle Spice와 Esmar의 Tuek's Sietch 방문은 `rules/agent_turn.py`; Bloodlines 전용은 `rules/tactics.py`(Chani), `rules/planetologist.py`(Kynes), `rules/navigation.py`(Y'rkoon) |
| Bloodlines 구성물 | `content/bloodlines/sardaukar.py`(Commander·Skill), `content/uprising/imperium.py`·`intrigue.py`의 `bloodlines_only`/`tech_only`/`twisted`/`navigation` 항목, `rules/sardaukar.py`, `rules/spy_moves.py`·`rules/unit_loss.py`(상대 결정 frame), `rules/optional_trash.py` |
| Immortality 구성물 | `content/immortality/board.py`(research·Tleilaxu track), `content/immortality/tleilaxu.py`(Tleilaxu deck·Reclaimed Forces·프로모 Piter), `content/uprising/imperium.py`·`intrigue.py`의 `immortality_only` 항목; 규칙 명세 `docs/rules/immortality.md`, 전사표 `docs/implementation-audits/immortality.md` |
| Tech Module | `content/bloodlines/tech.py`(tile 18장·`TechAbility`), `rules/tech.py`(Acquire Tech·Flip·Forbidden Weapons 선택·Suspensor/빚진 draw hook·Endgame 효과·Secret Project), `rules/ornithopter.py`(Fleet 매칭); 상시 능력은 `agent_turn.py`(Navigation Chamber·Servo-Receivers)·`sardaukar.py`(High Command·Plasteel Blades)·`board_effects.py`(Gene-Locked Vault)·`core/observation.py`(Glowglobes)·`reveal_turn.py`(Command tile·Panopticon·Forbidden Weapons frame)·`contract_tiles.py`(CHOAM Transports)·`combat.py`(Planetary Array·Fleet); Kota의 Signet은 `leader_abilities.py` |
| Agent 배치와 카드 효과 | `src/dune_imperium/rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `src/dune_imperium/rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `src/dune_imperium/rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher 표와 frame kind | `src/dune_imperium/rules/engine.py`, `frames.py`, `agent_effect_frame.py` |
| effect DSL과 Intrigue | `content/uprising/effect_dsl.py`, `intrigue.py`, `rules/effect_interpreter.py`, `rules/intrigue.py`, `rules/intrigue_deck.py`, `rules/intrigue_triggers.py` |
| 고정 action catalog | `src/dune_imperium/adapters/action_codec.py` |
| 관측과 PettingZoo | `src/dune_imperium/core/observation.py`, `adapters/observation_encoding.py`, `adapters/pettingzoo_env.py` |
| replay와 random 러너 | `src/dune_imperium/core/replay.py`, `simulation/runner.py` (한 라운드·전체 게임) |
| 로컬 플레이 서버·저장·검토 | `src/dune_imperium/server/` (`sessions.py`, `persistence.py`, `app.py`, `catalog.py`, `static/`) |
| 원격 멀티플레이 접근 계층(M14) | `src/dune_imperium/server/access.py`(모드·`Credentials`·토큰), `sessions.py`의 `claim_seat`·`release_seat`·`identify`·`_authorize_seat_locked`·`require_admin`, `app.py`의 쿠키 ↔ `Credentials`, `cli/server.py`의 `--remote`; 설계는 [multiplayer-design.md](multiplayer-design.md) |
| 영문 효과 표시 텍스트·이미지 매핑 | `src/dune_imperium/display/` (DSL·구조체 렌더러, enum 토큰 맵, 공간·Leader 텍스트, 이미지 파일명) |
| 검증 sweep과 불변식 | `src/dune_imperium/simulation/sweep.py`, `simulation/invariants.py`, `cli/sweep.py` |
| M9 대회 도구와 보고서 | `src/dune_imperium/evaluation/tournament.py`(spec·러너·계측), `evaluation/report.py`(집계·Markdown/JSON), `agents/registry.py`(이름 붙인 baseline), `cli/tournament.py`; 기준선 `docs/evaluation/` |
| M9 search baseline | `src/dune_imperium/agents/rollout_agent.py`(후보 가지치기·determinized rollout·값 함수), `agents/determinize.py`(관측자 지식과 일치하는 세계 표본), `agents/base.py`의 `StateAgent`(러너가 상태를 넘기는 확장 계약) |
| M10 self-play 데이터 | `src/dune_imperium/training/selfplay.py`(lockstep 러너·Episode·stack_episodes), `training/policy.py`(`BatchPolicy`·`PolicyRequest`·random/agent 어댑터), `cli/selfplay.py` |
| M10 학습 | `src/dune_imperium/training/network.py`(masked policy/value MLP), `training/torch_policy.py`(`TorchBatchPolicy`·`NetworkAgent`·순환 방지·체크포인트 로더), `training/checkpoint.py`(버전 고정 저장/로드), `training/learner.py`(REINFORCE + baseline), `training/loop.py`(`TrainConfig`·`train`·평가), `cli/train.py`; `agents/registry.py`의 `checkpoint:` 이름 |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은 `docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical hash하는 디버그 가드라 기본 off다(켜면 random play가 약 70 step/s, 끄면 약 3,000 step/s). 커널 테스트 엔진만 이를 켠다. 완주 soak은 이제 `run_random_game`(약 48ms/판, 9,000 step/s)이나, 불변식·누출 검사와 replay 검증까지 포함하는 `dune-imperium-sweep`(검사 전부 켠 단일 프로세스 약 175ms/판, `--workers 8`로 약 50 games/s)을 그대로 쓴다. env 경유 masked random full episode는 약 4,100 agent step/s다.

2026-09-10에 **처리량 회귀를 측정으로 귀인했다**([evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md)). 요지: 09-06 → 09-10의 59.25 → 38.71 games/s는 **step당 엔진 CPU 약 1.6배**이고, 콘텐츠(확장 4종)가 엔진 전반을 무겁게 만든 결과다. 성능을 재는 절차도 그 문서에 있다 — **CPU 경합에 면역인 지표(cProfile의 호출 횟수, step 수)를 먼저 잡고**, 소요 시간은 기계가 조용할 때 트리를 번갈아 잰다. cProfile의 *누적 시간*은 호출 수에 비례해 부풀므로 트리 간 비교에 쓰지 않는다. 리포트의 `duration`은 worker 기동·import를 포함하고 `ms/decision`은 `_MeteredAgent` 안쪽만 재므로 두 열의 의미가 다르다. 두 기준선 리포트의 `ms/decision` 열은 harness 상수(좌석당 +0.005 ms)를 포함하고 있었고 `ab48e0c`로 없앴으므로, **09-06·09-10 리포트의 그 열은 이후 실행과 직접 비교할 수 없다**.

2026-09-19(Mac mini, M10 실행 3): **학습 수집은 이 Mac의 E코어 6개를 쓰지 못한다.** `Collector`는 게임을 worker 수만큼의 chunk로 정적 분할하므로(`training/collect.py`의 `specs[index::self.workers]`) iteration의 수집 시간은 가장 느린 chunk가 정하고, 4 worker(수집 8.8초)에서 P코어 4개는 99.5%·E코어는 0~25%였다(코어별 부하 실측). worker를 8·10으로 늘리면 오히려 10.8·12.5초다. **후보**: chunk 수를 worker 수와 떼어(예: 2판짜리 chunk 16개를 worker 8~10개가 `pool.map`의 대기열에서 가져가게) 빠른 코어가 더 많은 chunk를 맡게 한다. 8 worker의 수치로 어림하면 E코어 하나는 P코어의 0.4배쯤이라 이론 상한은 수집 −3초(iteration의 약 20%)지만, **어림일 뿐 잰 값이 아니고** chunk가 작아지면 lockstep 추론 배치가 줄고 job마다 가중치를 다시 읽는다 — 워크트리에서 A/B로 잰 뒤에 채택한다(`src/` 변경이므로 학습이 도는 체크아웃에서는 하지 않는다; chunk seed가 바뀌므로 재현성 문서도 함께 고친다). 덧붙여 `latest.pt`(235 MB)를 매 iteration 다시 쓰므로 1,000 iteration에 SSD 쓰기가 약 235 GB다.

## 유용한 명령

```bash
# A/B 도구(census → 변형 → 축별 셀 → 요약; 자세한 절차는 scripts/ab/README.md)
uv run python scripts/ab/census.py --games 40 --ruleset both --out ab-runs/census.json
uv run python scripts/ab/cells.py --name round1 --variants heuristic_v_space --control heuristic_uniform_ties --axes base,choam --seeds 0,500
uv run python scripts/ab/pair_matrix.py ab-runs/round1 v_space

# 검증 sweep: 카드 보존·교착·관측 누출·replay 검사 (룰셋당 100판 기본)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8

# 같은 sweep을 heuristic baseline으로 (M11 사람용 상대와 동일 정책)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --policy heuristic

# OQ-007 6-Leader 공개 draft setup으로 완주 검사
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --leader-draft

# 로컬 플레이 서버 (ui extra 필요; 기본 http://127.0.0.1:8000)
uv run dune-imperium-server

# 원격 멀티플레이 서버 (M14): 콘솔에 찍히는 관리자 링크로 들어가 방을 만들고 방 링크를 보낸다
caffeinate -i uv run dune-imperium-server --remote --host <tailscale 주소>   # 절차 전체: docs/remote-play-guide.md

# 브라우저 E2E (app.js를 고친 뒤; Playwright는 스크래치 venv에만 — scripts/e2e/README.md)
uv venv /tmp/dune-e2e-venv --python 3.12 && uv pip install --python /tmp/dune-e2e-venv/bin/python playwright
(cd scripts/e2e && for s in remote.py open_mode.py 'races.py --ab' recovery.py; do /tmp/dune-e2e-venv/bin/python $s || break; done)
# 실제 원격 판 전의 리허설: 이 머신의 Tailscale 주소에 bind해서 (docs/remote-play-guide.md)
(cd scripts/e2e && E2E_HOST=100.x.y.z /tmp/dune-e2e-venv/bin/python rehearsal.py)

# UI 카드 이미지 캐시 (선택). 우선: 비공개 Dune-Imperium-assets 저장소를 형제
# 디렉터리에 clone하고 그 README대로 저장소 루트에 assets symlink 하나를 만든다.
# 폴백/신규 카드 채움: 아래 fetch 스크립트 (빈 파일만 받는다)
uv run scripts/fetch_card_images.py

# 한 라운드 random 실행
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002

# 대화형 한 라운드 실행
uv run dune-imperium-debug --seed 2

# 명시적으로 준비한 DIU working copy와 identity/effect shape 대조
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON

# 공식 PDF와 고정 checksum 재검증; 생성물은 /tmp에만 둔다
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 제한되면 명령 앞에 `UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

2026-09-22(WSL 노트북, 한글판 카드 사진 크롭 세션): 비공개 에셋 저장소에 미push 커밋 3건 — `b8784f4`(앞 세션의 Immortality specimen 아이콘), `3fcf62f`(`origin/master`의 `1574241` merge), `d01e9d9`(`reference/naver-vampmiyu-223464306472/`, 약 190 MB). 메인 저장소에는 이 문서 커밋 1건. 이 세션에서는 자동 모드 권한 검사가 push를 막아 **두 저장소 모두 push하지 않았다** — 사용자가 이 기기에서 push한 뒤 다른 기기에서 두 저장소를 pull한다. 새 세션은 `git log origin/master..master`와 반대 방향을 두 저장소에서 모두 확인한다.

2026-09-20 새벽(Mac mini, 보드 조각·아이콘 전사 정정 세션): 이 세션의 커밋(`82a0423`·`c9aec0a`·`7188523`·`2c967b7`와 문서 커밋)은 master에만 있고 **push하지 않았다**. 비공개 에셋 저장소에도 커밋 1건(`e7f7741`: `tokens/maker_hooks.png`·`alliance_<faction>.jpg` + README)이 있고 역시 push하지 않았다 — 다른 기기에서 후크·동맹 토큰 그림을 보려면 두 저장소를 모두 push·pull한다(에셋이 없으면 룰북 아이콘으로 그릴 뿐 동작은 같다). **`src/`의 규칙이 바뀌었으므로 학습이 도는 기기에서는 pull하지 않는다**; pull한 뒤의 학습은 새 규칙의 환경이다(세션 요약의 "M10에 미치는 영향"). 떠 있던 플레이 서버는 재시작해야 새 규칙·새 카탈로그 필드가 적용된다(정적 파일은 즉시 반영).

2026-09-19 오후~저녁(Mac mini, M10 실행 3·학습률 A/B 세션): 이 세션의 앞 커밋 넷(`bd8732f` 학습 가드·감독기의 macOS 이식, `7935740` 문서, `61b09df` 재개 시 학습률 수정, `41e9a7a` 문서)은 16:43에 **push돼 있다**(사용자 쪽에서 한 push다 — reflog의 `update by push`). 그 뒤의 A/B 결과 문서 커밋들은 master에만 있다 — `git log origin/master..master`로 확인한다. `src/` 변경은 `61b09df` 하나이고(옵티마이저 상태에서 재개할 때 `--learning-rate`가 이긴다) 체크포인트 형식과는 무관하다. Windows PC는 pull하면 새 `scripts/train/`(Linux 경로의 동작은 그대로)과 그 수정을 얻는다. **학습이 도는 기기에서는 `src/`가 바뀌는 pull을 하지 않는다.** 체크포인트 폴더는 git 무시라 기기 간에는 여전히 파일을 복사한다(실행 3의 산출물은 이 Mac의 `checkpoints/2026-09-19/lr1e-4-mac/`).

2026-09-19(Mac mini, 사용자 지시 "두 저장소 다 push"): 메인 저장소 `f3b91fb..3b5f4c5`(아래의 merge 커밋을 포함한 21건)와 비공개 에셋 저장소 `02bac8a..f9924b4`(Combat marker 토큰, Shield Wall 토큰·위치 타일 2건)를 push했고, 두 곳 모두 `origin/master`와 로컬이 일치한다. 바로 아래 두 문단의 "push하지 않았다"는 그 시점의 기록이다. 다른 기기는 **두 저장소를 모두 pull**해야 그림 토큰·타일이 보인다(에셋이 없어도 동작은 같다).

2026-09-19(Mac mini): `git fetch`에서 원격이 12건 앞서 있었다(Windows PC의 M10 첫 학습·codec v105·체크포인트 이관·PPO 슬라이스). 이 기기의 미푸시 15건(보드 토큰·원판·보드 조각·에셋 버전)과 겹치는 파일은 `README.md`·이 문서·`lessons.md`뿐이라 **master에서 `origin/master`를 `--no-ff`로 merge**했다(기존 커밋은 고치지 않는다). 충돌은 양쪽 내용을 모두 살려 풀었고, merge한 트리에서 pytest 1,764 · ruff · mypy를 실측했다. merge 커밋과 그 뒤의 작업은 아직 push하지 않았다.

2026-09-18(Mac mini): Combat marker 그림 세션의 커밋(`e54e035` 코드·테스트, `f24eb52` 문서, 그리고 같은 날 Score marker·Councilor token 원판과 공용 player disc 커밋들)은 master에만 있고 **push하지 않았다**. 비공개 에셋 저장소에도 같은 날 커밋 1건(`tokens/` 8장 + README)이 있고 역시 push하지 않았다 — 다른 기기에서 그림 토큰을 보려면 두 저장소를 모두 push·pull해야 한다(에셋이 없으면 그린 토큰으로 돌아갈 뿐 동작은 같다).

2026-09-17 밤~심야(Mac mini): `m14-slice4-client` 브랜치(WIP 커밋 `b319081` + 그 세션의 커밋)를 master 쪽에서 `--no-ff`로 머지했고(`de70942`), 사용자 지시로 슬라이스 5(`657f60c`)까지 `origin/master`에 push했다. 원격의 WIP 브랜치는 사용자가, 로컬 워크트리와 브랜치 `m14-slice4-client`는 2026-09-17 자정 무렵 세션이 지웠다. 그 뒤 슬라이스 6의 커밋들은 master 직접 커밋이다 — push 여부는 `git log origin/master..master`로 확인한다.

2026-09-17 학습 전 최종 점검 세션(WSL 노트북) 종료 시점에 문서 커밋 3건(테스트 수 1,539 정정, 전 확장 학습 전 점검 요약과 0번 다음 작업, 이 문단)을 `git push git@github.com:jungcheolseung/Dune-Imperium.git master`로 push했다. 학습은 Mac mini 또는 14700K PC에서 진행하기로 했으므로, 그 기기에서는 `git pull` 뒤 이 문서의 0번 명령을 그대로 쓴다(체크포인트 폴더 `checkpoints/`는 git 무시이며 기기 간에는 파일을 복사한다).

2026-09-08 M13 세션 종료 시점에 이 세션의 master 커밋 전부(Immortality 슬라이스 1~6의 `Play`/`Document` 쌍, UI, 소크 수정)를 `git push git@github.com:jungcheolseung/Dune-Imperium.git master`로 push했고, 에셋 저장소의 3개 커밋(Ruthless Leadership·Immortality·Experimentation의 `content_id`)도 같은 ssh URL 방식으로 push했다. 새 세션은 `git fetch origin` 뒤 양방향 차이를 확인하고 일치하면 이 문서의 기준선을 그대로 쓴다.

2026-09-07: `bloodlines` 브랜치(35 커밋)를 master 쪽에서 `--no-ff`로 머지했고(`dbd9b73`), 같은 날 저녁 슬라이스 6 커밋 5건과 이 문서 갱신을 master에 직접 올렸다. 아직 push하지 않았다면 `git log origin/master..master`로 확인한다. 비공개 에셋 저장소(`assets` symlink → `Dune-Imperium-assets`)에도 같은 날 manifest 커밋 6건(Bloodlines 카드 44장 content id, Leader 8종, Tuek's Sietch 타일 이미지, Twisted·Navigation 카드 키, Kota Odax의 content id `43c25fc`)이 있으니 다른 머신에서는 그쪽도 pull한다.

2026-09-04 세션 종료 시점에 이 세션의 커밋 전부(보드·카드 아이콘 분리 v86/v87, 서버·UI 확인 흐름과 마커, Reveal 순서 v88, OQ-028 조건 판정 시점, OQ-029 등록)를 `origin/master`에 push했다. 새 세션은 `git fetch origin` 뒤 `git log origin/master..master`와 반대 방향을 확인하고, 일치하면 이 문서의 기준선을 그대로 쓴다. 에셋 저장소(`Dune-Imperium-assets`)의 `5b55e45` 1개 미push 여부는 그 저장소에서 확인한다. 원격에는 병합하지 않은 `kyungtae` 브랜치가 있다. 새 세션은 `git log origin/master..master`와 반대 방향을 모두 확인하고, checkout이 `853ecd4`보다 이전이면 이 문서의 989개 테스트·codec v84 기준선이 실제 코드와 일치하지 않는다. **다른 머신에서 이어서 작업한다면 먼저 이 머신에서 push가 필요하다.** 새 머신의 UI 카드 이미지·아이콘·보드 스캔은 비공개 `Dune-Imperium-assets` 저장소를 clone해 symlink로 연결한다(그 README 참고; 루트의 `assets` symlink 하나로 cards·icons·board·rulebooks를 모두 연결). 카드 매핑은 그 저장소의 `cards/manifest.json`에만 있으므로 접근이 없으면 텍스트 UI로 동작한다.

## 2026-09-23 커뮤니티 팁 분류와 tip census 세션 요약 (WSL 노트북 i5-8250U, master 직접 커밋, 관측 v20, codec v107, 변경은 `scripts/ab/`·`tests/`·`docs/` — **엔진·학습 코드 무변경**)

- 사용자가 Mac mini의 커뮤니티 팁 JSON을 문서로 옮긴 커밋(`5bbad3a`)을 가져와 "플레이어 팁 반영"을 이어 갔다. 이 노트북에는
  5081 체크포인트와 6절의 스크래치 도구가 없어 정책 측정은 하지 않았다.
- 분류(workflow, Sonnet 분류 4 + Opus 반박 4): 규칙을 담은 팁은 전부 엔진과 일치. 분류자가 올린 "불일치" 2건은 검증자가
  반박했다. 떨어졌다 다시 4에 오르면 보너스를 다시 받는 경우 `[Main pp. 4, 7 board artwork]`에 회귀 테스트가 없어 넣었다(가드를
  넣은 소스 사본에서 실패 확인). 커뮤니티 문서의 "Uprising에는 Heighliner가 없다"는 오기라 고쳤다 `[Board Guide p. 2]`.
- 도구(workflow, Sonnet 구현 4 + Opus 반박 4 + 수정 4): `scripts/ab/tip_census.py` + `scripts/ab/tipcensus/`. 대회와 같은 게임을
  두는지는 순위·VP·결정 수로 테스트가 고정한다. 검증이 숫자를 틀리게 하던 결함 여섯을 잡았다(sandworm 소환 경로 누락, 빈
  Conflict 누락, Commander 손실을 퇴각으로 셈, Endgame 시작 VP에 Tech VP 포함, 의무 자기 폐기를 선택 폐기로 셈, Bond 짝 진영
  오판) — [player-tips-for-training.md](player-tips-for-training.md) 7.1.
- heuristic 기준값(기본판·평소 구성·학습 구성 각 100 seed, 100판 11~17초)과 Mac 스크래치 census와의 대조는 그 문서 7.5.
- 이어서 사용자가 5081 체크포인트를 가져와 이 노트북에서 5081 census 세 셀(미러 학습·평소 구성, 1+3)을 냈다(한 판 약 35초, 워커 4개 ×
  약 650MB). 비교 도구 `scripts/ab/tip_compare.py`(seed 군집 부트스트랩)를 더했다. 팁별 결과는 그 문서 7.7, 다음은 7.8(정책 탐침
  1순위: 초반 Faction 접근 카드 강제 구매).

## 2026-09-22 저녁 실전 팁과 학습 논의 세션 요약 (WSL 노트북 i5-8250U, **코드 변경 없음**, 변경은 `docs/`뿐)

- 사용자 질문: 휴리스틱·rollout의 구현, 그리고 친구들과 두며 느낀 팁·행동 중요도가 학습에 도움이 되는지. 논의만 했다.
- 기록과 결론은 [player-tips-for-training.md](player-tips-for-training.md) 한 곳에 있다(두 baseline의 구조, 사람 직관이
  측정으로 뒤집힌 전례 둘, 팁을 넣을 곳 여섯의 순위, 열린 갈래). 사용자가 **다른 PC의 새 세션에서 이어간다** — 그 문서
  5절의 남은 질문 둘부터 시작한다.

## 2026-09-22 한글판 카드 사진 크롭 세션 요약 (WSL 노트북 i5-8250U, 변경은 **비공개 에셋 저장소뿐** — 메인 저장소는 이 문서만; 에셋 `d01e9d9`)

- 사용자 지시: 네이버 블로그 [vampmiyu/223464306472](https://blog.naver.com/vampmiyu/223464306472)(한국어판
  Uprising 개봉기)의 사진을 전부 받고, 카드를 잘라 **실제 카드 비율로** 원근 보정한 뒤 영문 manifest와의 매칭
  표를 만든다. 결과는 에셋 저장소 `reference/naver-vampmiyu-223464306472/`에 있다 — 사진 51장(원본 해상도),
  `crops/` 190장, `best/uprising/<kind>/<Name>.jpg`(카드별 대표 1장, `cards/en/`과 같은 배치), `matching.md`
  (한국어 표)·`matching.csv`·`coverage.csv`·`matching.json`, `matching.html`(한글 크롭과 영문 스캔을 나란히 보는
  자기완결 갤러리), `tools/`(스크립트·중간 데이터, 재실행법은 그 README). 방법·근거·다음 단계는 그 폴더
  README가 정본이다. 사진 저작권은 블로거·출판사에 있고, 사용자 결정으로 비공개 저장소에 개인 용도로만 둔다.
- **카드 규격**(사진 실측 + 슬리브 자료): 표준 **63×88**(임페리움·시작·예비·6인·프로모·솔로 라이벌; 63.5×88은
  실측과 어긋남), 음모·분쟁·목표 **44×68**, 리더 **146×102**(147 아님), 계약 타일은 영문 렌더 비율 670×425.
- **커버리지**: Uprising manifest 177장(장소 제외) 중 141장에 크롭, 가림 없는 것 138장 — 임페리움 54·시작 7·
  예비 2·6인 18·계약 28 전부, 리더 9/10(대모 제시카 없음), 분쟁 16/16(2장은 이웃에 일부 가림), 프로모 1/3,
  **음모 6/39**(31번 사진이 더미). manifest에 없는 솔로 라이벌 10장·목표 5장도 잘랐다.
- **한글 카드명**: 사진에 찍힌 카드 181장의 인쇄 제목을 서브에이전트 판독과 메인 세션의 제목 띠 판독으로 두
  번 읽었고 띄어쓰기까지 전부 일치했다(`matching.csv`의 `korean_title`). 예: Steersman=조타수,
  Treacherous Maneuver=기만적인 계책. 이름 대응은 기억이나 번역으로 짐작하지 말고 `matching.csv`에서 찾는다.
- **다음 단계(사용자가 고르기 전에는 시작하지 않는다)**: `best/`를 WebP로 바꿔 `cards/ko/<manifest path>`에
  두면(확장자까지 같은 경로) `display/images.py`가 코드 변경 없이 쓴다. 그 전에 물을 것 셋 — (1)
  `DEFAULT_LANGUAGES = ("ko","en")`라 **영어 화면에서도 한글 카드가 나온다**, 화면 언어를 따르게 할지;
  (2) 한국어 화면의 카드명(고유명사)을 이제 공식 한글 이름으로 바꿀지(위 언어 정책은 "한글 카드 이미지
  미확보"를 이유로 영어 유지였다); (3) 2026-09-18 절의 TTS 한글화 모드 3종(3092549193·3446667675·3025517639)
  카드 시트가 평면 스캔이면 사진 크롭보다 낫고 빠진 36장(음모 33장 등)도 채울 수 있다 — 먼저 비교할지.
- **교훈**(다음 크롭 작업용): 서브에이전트의 눈 검수는 한쪽이 2.5 mm 어긋난 크롭 30장을 "양호"로 통과시켰다
  — 크롭은 영문 스캔에 정합해 **좌우·상하 여백의 합이 카드 종류마다 일정한지**로 검증한다(`tools/regcheck.py`).
  Sonnet 판독자는 세로 제목을 읽지 않고 음역해 지어냈다(소규모 전투 → "스커미쉬") — 한글 제목은 제목 띠
  시트로 다시 읽는다.
- **push 상태**: 이 세션은 에셋 저장소에 `origin/master`를 merge(`3fcf62f`, 기존 커밋 무변경)하고 `d01e9d9`를
  커밋했으며, 메인 저장소에는 이 문서 커밋만 있다. **두 저장소 모두 push하지 않았다**(자동 모드 권한 검사가
  push를 막았다) — 다른 기기에서 이어가려면 이 기기에서 두 저장소를 push한 뒤 그쪽에서 pull한다.

## 2026-09-22 한국어 화면 잔재·Agent 아이콘·글꼴 세션 요약 (WSL 노트북 i5-8250U, master 직접 커밋, 관측 v20, codec v107, 변경은 `server/static/`·`scripts/e2e/`·`tests/server/test_i18n.py`·`docs/` — **엔진·학습 코드 무변경**)

같은 체크아웃에서 다른 세션(Codex: `7087d40`·`8251efb`·`95b2a74`·`d09532c`)과 겹쳐 돌았다 — 커밋 전마다
`git log -1`과 `git status`로 남의 변경을 확인했다.

- **설정 화면**: 프로모 옵션 라벨에 불멸 프로모 Piter, Genius Advisor(`26095f6`; 엔진은 원래 넣고 있었다),
  기술 모듈은 혈통을 체크해야만 활성(`c731f5c`), 규칙 옵션 전부 기본 체크(`0ca7113`; 옛 기본값에 기대던 e2e는
  `common.set_rule_options(page, …)`로 남길 옵션만 적는다).
- **Agent 아이콘**: Icon Guide의 +Agent 그림은 "Agent 얻기"다. `7087d40`이 남긴 두 자리(카드 텍스트의
  "Agent", 교전 칩의 Into the Fray)도 + 없는 말로(`e58d0b5`, `help.py`가 페이지 전체에 +Agent 그림이 없는지 본다).
- **용어**(한국어 룰북 인용 후 용어집에 행 추가): 가문 핵 토큰 `[Immortality p. 12]`, 정보 수집·침투 `[Main p. 11]`,
  게임판 `[Main p. 3]`, 인장 반지 능력 `[Main p. 3]`; recall은 전부 소환 `[Main p. 20]`(withdraw의 회수는 그대로).
- **한국어 화면의 영어 잔재**: 워크플로 둘(런타임·정적 스윕 → 용어집 판정, 세 렌즈 리뷰 → 반박 검증)로 찾아
  고쳤다 — 헤더의 확장 배지·시드, Alliance·병력·모래벌레·스파이스·방어벽·게임판 title/alt, 손패 카운트 title,
  AI 배지 title(체크포인트 좌석은 파일 경로), Endgame 로그 머리, 카드 텍스트 아이콘 툴팁(`TERMS`에서),
  비용 아이콘, "discard pile"(버리기 아이콘을 달지 않는다), 팝오버의 조건·보상·인장 반지 능력 머리말(카드
  문구는 `iconize()`의 `.card-text` 안, 우리 말은 밖), 한국어가 번역하는 엔진 prompt인 `action.detail`, 저장
  목록의 좌석 종류·시각, 게임을 떠난 뒤 설정 화면에 남던 헤더, 언어 전환 뒤 옛 언어로 남던 검토 상태 줄
  (`writeReviewStatus`).
- **글꼴**: 제목 "Dune: Imperium — Uprising"이 언어마다 달라 보인 것은 Windows에 이름 붙은 글꼴이 하나도
  없어 generic sans-serif가 `lang`에 따라 Malgun Gothic/Arial로 갈렸기 때문이다. Latin 글꼴(Segoe UI 등)을
  앞에 두었다(`b9d6844`).
- **가드**: `lang.py`의 한국어 전면 검사(`KOREAN_LATIN_JS`) — 카탈로그 **이름** 필드·`.card-text`·허용 목록을
  지운 뒤 라틴 낱말 0, 좌석 세부와 ⓘ 세부를 펴고 훑는다. 옛 클라이언트(`d09532c`)와 Family Atomics 깃발을
  되돌린 트리에서 실패를 확인했다. `test_i18n.py`의 `_GLOSSARY_WORDS`에 atomics·intelligence·infiltrate.
- **이어서 사용자 결정**: 제목은 공식 한국어판 "듄 임페리움: 봉기" `[Main p. 2]`(탭·헤더·게임판 alt; 영어 모드는
  그대로), set-aside는 추천값 — 맥락마다 룰북이 쓴 말(Shaddam 계약 따로 치워두다 `[Board Guide p. 8]`,
  Manipulate로 빼 둔 카드 따로 빼두다 `[Immortality p. 14]`), 원로회(자리)·소드마스터는 좌석 상태와 로그에서
  한국어(`[Board Guide p. 2]` "원로회의 빈자리") — 보드 공간 이름은 여전히 영어. `test_i18n.py`에 두 이름의
  한국어 가드, `lang.py`에 좌석 상태 줄과 제목 검사.

## 2026-09-21 밤 보드 위 사다우카 지휘관 세션 요약 (Mac mini, 브랜치 `ui-commanders` → master, 관측 v20, codec v107, 변경은 `display/board_layout.py`·`display/token_images.py`·`server/catalog.py`·`server/static/`·`scripts/`·테스트 — **엔진·학습 코드 무변경**; 에셋 저장소 `1574241`)

사용자 요청: "사다우카 커맨더도 보드판에서 제대로 보이면 좋겠어. bloodlines 룰북 3p에 나온 보드판 사진처럼 …
보드 에이전트 칸의 오른쪽 위에 … 룰북에 있는 지휘관 이미지가 들어가면 좋겠어." 자세한 것은
[`ui-improvement-plan.md`](ui-improvement-plan.md) 6d.

- **자리**: setup의 다섯(4인은 여섯) 칸, "Agent를 놓을 자리는 남긴다" `[Bloodlines p. 3]`. 사진의 다섯 칸에서
  읽은 평균으로 받침 중심을 흰 테두리의 (0.89, 0.13)에, 키를 테두리의 0.95배로(`board_layout.COMMANDER_*`,
  `catalog.commander_spot`). 칸 클릭은 가로채지 않고 칸 이름이 지휘관을 말한다.
- **그림**: 룰북 2쪽의 모형을 공식 PDF(sha256 고정)에서 꺼내 바탕과 박힌 그림자를 걷어 냈다
  (`scripts/cut_commander_token.py`, 바이트 단위 재현). 그림은 에셋 저장소 `tokens/sardaukar_commander.png`이고
  카탈로그 `commander_token`으로 나간다; 없으면 같은 자리에 그린 표시.
- 보드의 "Commander" 영어 두 곳(빈 보드 안내, 주둔지·교전 칩 title)을 용어집의 사다우카 지휘관으로.
- **E2E**: `board_tokens.py`에 Bloodlines 판(187 → 200, 옛 클라이언트 8개 실패). 15종 전부 녹색.
- **패널 문구의 용어집 잔재**(`54cd0c5`, 2026-09-22 새벽): 핸드·책략 카드덱·버림 더미·운항 카드·전투 책략 카드·
  뒤집힘·전술 트랙·익스 대사관 판·혈통/불멸/봉기로. 표 밖에서 만들던 `<좌석> discard`도. 같은 잔재를 막는 가드를
  `test_i18n.py`에(pytest 1,805).
- **쌓인 Spy**(`44b5591`, 사용자 지적 "기존에 있던 스파이의 위에 쌓는 식"): 한 관측소를 함께 쓰는 Spy(Double Agent, Bloodlines의 잠복 스파이 `[Bloodlines pp. 5, 12]`)를
  나란히(90/80/70%로 줄여) 두던 것을, 원판 너비 그대로 먼저 온 Spy 위에 쌓는다(한 층 = 높이의 60%). 순서는 로그의
  `spy_placed`(엔진은 도착 순서를 들고 있지 않다). `board_tokens.py` 200 → 203(옛 배치 5개 실패).

## 2026-09-21 밤 UI 잔여 세 항목 세션 요약 (Mac mini, 워크트리 `ui-leftovers` → master, 관측 v20, codec v107, 변경은 `server/static/`·`server/catalog.py`의 `post_spaces`·`scripts/e2e/`·`tests/server/`·`docs/` — **엔진·학습 코드 무변경**)

사용자 요청: "이제 ui 개선 작업 이어가보려고해" → 핸드오프 후보 다섯 중 셋(`remote.py` 위생·로그의 영어 조각·
1366×768 좌석)을 사용자가 골랐다. 같은 체크아웃에서 학습(long-2k)이 돌아 워크트리에서 했고, ultracode로 반박
검증을 워크플로에 맡겼다. 자세한 수치는 [`ui-improvement-plan.md`](ui-improvement-plan.md) 6단계.

- **`remote.py`**(`f97f838`): [11]이 되돌릴 창이 열린 좌석이 나올 때까지 한 수씩 더 둔다. 네 번 돌려 57개씩.
- **로그·행동 목록의 엔진 id**(`80d483e`): 19판 인벤토리에서 277곳 → 0. 값 해석기 `fieldText` 하나를 행동
  목록·로그·검토·보드 title이 같이 쓴다(관측소는 지켜보는 칸 이름, 연구 칸은 `연구 트랙 2-2 (스파이스 1)`,
  Feyd 칸은 인쇄 보상, 무작위 결과는 "좌석 1의 버림 더미 섞기 (Arrakeen)"). 라벨 가드가 리터럴만 훑어 놓친
  행동 6·이벤트 1을 채우고 가드를 `ACTION_HANDLERS` 기준으로 넓혔다. 새 E2E `log_words.py`(옛 클라이언트 6개
  실패). 한국어 표의 영어 네 행과, 스파이 소환을 "회수"로 쓴 줄을 용어집대로 고쳤다.
- **노트북 좌석**(`4a9a8b5`): 높이 960px 이하에서 지도자 그림을 빼고 이름·배지를 한 줄로, 접기를 머리 줄의
  화살표로. 좌석 171 → 111px, 1366×768·1440×900·1536×864의 네 시점 모두 들어온다(전에는 703~738px에
  519~652px 칸). `seats.py` 21 → 31(옛 클라이언트 5개 실패).
- **범위 밖으로 남긴 것**: 패널 문구의 용어집 잔재 11곳, 용어집에 행이 없는 로그 낱말 — 위 "UI 다음 후보" 2·3.
- **같은 세션의 git 사고**: rebase 전 충돌 "시험"으로 돌린 `git replay`가 master ref를 옮겼다(git 2.54 기본값);
  잃은 것 없이 되돌리고 정식 rebase([`lessons.md`](lessons.md) 2026-09-21, master `fd8ccf4`).

## 2026-09-21 저녁 보드 칸 테두리·Agent·Spy 말 세션 요약 (WSL 노트북 i5-8250U, master 직접 커밋, 관측 v20, codec v107, 변경은 `display/board_layout.py`·`server/catalog.py`·`server/static/`·테스트·`scripts/e2e/` — **엔진·학습 코드 무변경**)

사용자 요청: "보드칸 하이라이트 테두리가 일관성이 없어 … 실제 에이전트를 놓게끔 되어 있는 흰 테두리에 딱 맞게,
옆의 보드칸 효과까지 포함되지 않고."

- **원인**: `SPACE_BOXES`가 2026-09-03에 2% 격자로 손 측정한 "칸 전체(제목·비용·그림·효과 아이콘)" 상자라
  칸마다 크기가 제각각이었다(High Council 26% 폭, Research Station 13%, …).
- **재측정**: 모든 인쇄 칸은 그림 둘레에 같은 흰 테두리를 그린다(왼쪽 위·오른쪽 아래는 직각, 나머지 두 모서리는
  45° 깎임). 테두리 윤곽을 스캔에 맞춰 찾고 변마다 밝기 중심을 잡으니 22칸 전부 **457 × 354 px(σ < 1 px)**
  라 한 크기 `(7.6, 5.9)`로 두었다. 상자는 흰 선의 중심선이다. Tuek's Sietch는 타일 그림(550×310) 안의
  테두리를 `LEADER_TILE_BOXES`의 타일 상자에 옮긴 값이고(타일 그림 상자는 hotspot과 분리됐다), Immortality의
  Research Station 덮개 타일의 테두리는 인쇄된 것과 1 px 안에서 겹쳐 hotspot 하나로 둘 다 맞는다.
- **표시**: 하이라이트를 버튼의 둥근 사각 border/box-shadow에서 hotspot 안의 SVG 윤곽(`.space-frame`,
  `catalog.space_frame.cut`의 깎인 모서리, `vector-effect: non-scaling-stroke`, 빛은 `drop-shadow`)으로 옮겼다.
  legal·alternative(점선)·picked·hover·로그 spotlight(파랑)가 모두 같은 윤곽을 쓴다. Agent 토큰은 테두리
  가운데(그림 위)에 선다.
- **같이 잡힌 결함**: 전역 `button:hover:not(:disabled)`(0,2,1)가 `.hotspot:hover`(0,2,0)를 이겨 **legal이 아닌
  칸에 마우스를 올리면 상자 전체가 accent 색으로 칠해졌다**. A/B로 옛 코드에서 새 검사 다섯이 실패함을 확인했다
  (`rgb(223, 160, 78)` 채움).
- 레이아웃 테스트가 옛 상자에 기대던 관계를 테두리 기준으로 다시 썼다: Control 깃발은 테두리 아래 선에서
  0.15 안에 매달리고, Maker 육각형은 테두리 오른쪽·테두리 높이 안에 있다.
- **Agent 말**(두 번째 요청: "실제 에이전트 아이콘 모양, 플레이어별 색"): 칸 위의 Agent가 좌석 번호를 적은
  원이 아니라 **룰북 Agent 아이콘의 두건 쓴 인물 실루엣**이다. 52×81 아이콘을 좌우 대칭 SVG 경로 하나로
  옮겼고(아이콘 실루엣과의 IoU 0.98), 숨은 sprite 하나(`#agent-outline`·`#agent-clip`)를 모든 말이 `<use>`로
  쓴다. 좌석 색 몸통 + 아이콘처럼 안쪽의 밝은 테두리 + 어두운 외곽선, 좌석 번호는 없다(점수·Councilor·Control
  말과 같은 규칙; 이름은 `aria-label`·`<title>`). 크기는 테두리 높이의 72%(셋이면 60%, 넷이면 46% —
  Infiltrate로 한 칸에 넷까지)라 보드와 함께 커지고 작아진다. 로컬 아이콘 파일이 없어도 그려진다.
- **Spy 말**(세 번째 요청): 관측소의 Spy도 좌석 번호 원 대신 **룰북 Spy 아이콘의 원통**(56×80 아이콘을 캡슐
  윤곽으로, IoU 0.99, 아이콘처럼 밝은 윗면 타원)이다. Agent와 한 함수(`seatPiece(kind, seat)`, `PIECE_SHAPES`)와
  한 sprite를 쓴다. Spy는 **인쇄된 관측소 원판만큼 넓다**(`POST_SIZE` 1.93, 116 px). 그러려고 관측소 중심
  `POST_POINTS`를 원판의 두 고리에 Hough 원 맞춤으로 다시 쟀다 — 2026-09-03의 손 측정은 최대 0.58
  어긋나 있었다(Hagga Basin). 한 관측소에 넷까지 나란히 서며 90/80/70%로 줄어든다.

## 2026-09-21 오후 UI 후속 세션 요약 (WSL 노트북 i5-8250U, master 직접 커밋, 관측 v20, codec v107, 변경은 `server/static/`·`server/sessions.py`의 `shortfall`·`scripts/e2e/`·`tests/server/`·`docs/` — **엔진·학습 코드 무변경**)

사용자 요청: "ui 개선 작업 이어가려고해" → 앞 세션이 남긴 후보 넷을 사용자가 **전부** 골랐다(작은 것부터). 검토
중 disclosure는 "접어 두기"로 결정. 학습은 이 기기에서 돌지 않아 `src/` 직접 편집, ultracode로 변환·검증을
워크플로에 맡겼다. 자세한 수치는 [`ui-improvement-plan.md`](ui-improvement-plan.md) 5단계.

- **종료 화면**(`cb99f9c`): 배너가 승자와 2위와의 차이(승점 차, 또는 처음 갈린 동점 판정 항목 `[Main p. 15]`,
  OQ-047, `[FAQ p. 2]`)를 말한다. seed 7 전 확장 판이 실제로 승점 9 동점을 스파이스 6 대 2로 가른다.
  검토 중 disclosure는 접혀 시작.
- **첫 한글 스크린샷에 드러난 결함 다섯**(`52cb9f8`·`d980ca0`·`b51311a`, [`lessons.md`](lessons.md) 2026-09-21):
  검토 상태 줄의 `[object DocumentFragment]`, **1700px 이하 모든 화면**에서 사이드 칼럼 위 칸이 로그 패널
  밑에 깔림(1366px에서 순위표가 가려짐), 로그의 쉼표 id 목록 raw 누출, 재생 중 탐색이 응답이 늦으면
  버려지는 경합 둘(재생 타이머, 탐색 중 재생·간격 변경 — 후자는 리뷰 워크플로가 찾음).
- **좌석 스탯**(`b04032e`): 좌석 넷이 1600×1000·1920×1080 칸에 다 들어온다(986 → 약 720px). 높이는
  스탯이 아니라 줄바꿈이 키웠다 — 긴 리더 이름, `Commander 0/1`, 두 줄 존 줄.
- **접근성·도움말**(`cd63d39`·`ecbefec`): `aria-live` 알림, 오류 `role="alert"`, 아이콘 전용 컨트롤의 이름,
  도움말 창(`?`). 리뷰가 찾은 것: 확정 대기 중에 다음 좌석의 차례를 미리 알리고 실제 넘김은 알리지 않음.
- **언어 전환**(`92a9ee8`·`09c817d`·`10e737a`, 한국어 모드 잔재는 이 세션 마지막 커밋): 머리글 English/한국어.
  영어에서 한글 0, 왕복하면 같은 화면. 13 에이전트 변환 + 36 에이전트 검증(코드 18·prompt 21·영어 57·
  한국어 모드 잔재 27건 반영). 한국어 모드에서도 엔진 prompt가 처음으로 한국어가 됐고, 로그 payload
  키(`Card Id` 등 89종)가 한국어가 됐다.
- **E2E**: 12 → 14종(`help.py`·`lang.py`), `spectate.py`의 재생 간격을 그린 시각 대신 요청 시각으로
  (`081bbdb`, 이 노트북에서 1/3 확률로 흔들렸다). 이 기기에서 처음으로 14종이 모두 녹색이다.
- **이 기기에서 E2E를 돌리는 법**(메모리에도 있음): 스크래치 venv의 Playwright + 캐시된 chromium 1234 +
  버전 심볼 `libasound` stub, 한글은 `/mnt/c/Windows/Fonts`를 fontconfig로. 무거운 작업을 곁에 돌리면
  `open_mode.py`의 폴링 4.5초 검사가 넘는다.

## 2026-09-21 UI 개선 세션 요약 (Mac mini, 워크트리 6개 → master, 관측 v20, codec v107, 변경은 `server/static/`·`server/sessions.py`·`scripts/e2e/`·`docs/`뿐 — **엔진·학습 코드 무변경**)

사용자 요청: "ui 개선 작업 진행할거야. 어떻게 개선하면 좋을지 계획세워볼래?" → 10개 관점 감사(73 에이전트, 반박 검증 32건 확정/29건 기각)와 직접 실측으로 [`ui-improvement-plan.md`](ui-improvement-plan.md)를 만들고 0~4단계를 전부 진행했다. 다른 세션이 같은 체크아웃에서 학습을 돌리고 있었으므로 `src/` 변경은 전부 워크트리에서 했고, 병합한 파일에 **`src/**/*.py`는 0개**다.

**사용자 결정 셋**: (1) 1순위는 `app.js` 구조 정리, (2) 화면 언어는 혼용 없이 — 고유명사는 영어 유지(정식 한글 카드 이미지 미확보), 룰북에 명시된 게임 용어만 ko/en, (3) 카드 인쇄 텍스트는 **영어 유지 + 용어 툴팁**(`CARD_FACE` 전사물이라 번역하면 전사 원칙이 깨지고, 한글 카드 스캔을 구하면 `display/images.py`의 `DEFAULT_LANGUAGES = ("ko","en")`가 코드 변경 없이 그림을 바꾼다).

- **0단계 결함 3건**(`e119e46`·`9ad978f`). Tech Module만 켜면 게임 생성이 **HTTP 500**이었다 — `RulesetConfig`의 맨 `ValueError`가 `_http_errors`를 빠져나갔다. `SessionError`가 이미 `ValueError` 하위라 핸들러를 넓히면 진짜 버그까지 가려지므로 config를 만드는 자리에서 변환했다. 배너의 `· frame: turn` 노출 제거. 로그의 raw id는 계획보다 넓었다 — 엔진의 payload id 키가 **약 35종**인데 허용 목록에 5종뿐이라 `leader_id`·`tech_id`·`contract_id`가 전부 샜다.
- **1단계 구조**(`5d2adbe`·`7f333fa`·`3485d25`). `SCROLL_PANES`에 `#side`가 없었고 `@media (max-width: 1700px)`가 `#side`를 스크롤러로 만든다 — **1700px 미만 모든 화면에서 사이드 칼럼이 매 렌더마다 맨 위로 점프**했다(설계 G7 위반). `open_mode.py`의 검사는 자기 뷰포트가 넓어 공허하게 통과 중이었다. 라벨 테이블 7개를 `static/labels.js`로 모으고, `app.js`를 섹션 배너대로 9파일로 잘랐다(전후 무손실 검증, 비어 있지 않은 5,064줄 동일). classic script라 전역 계약이 그대로이고 `index.html`의 로드 순서가 곧 옛 위→아래 순서다.
- **2단계 언어**(`f8cbfe4`~`c7574f5`). 공식 **한국어 룰북 4종**이 Dire Wolf 리소스 페이지에 있다 — manifest에 `*-ko`로 고정하고 공식 URL에서 받아 checksum을 확인했다. KR·EN이 **쪽수까지 정렬**돼 인용 하나가 양쪽을 가리킨다. [`rules/glossary-ko.md`](rules/glossary-ko.md) **117항목**(확장 포함). `ICON_RULES`의 영어 정규식 29개가 렌더된 산문에 돌던 것을 **용어 토큰**(`TERMS` + `phrase()`/`phraseText()`)으로 바꿔 Signet Ring류 충돌을 없애고 언어 전환의 토대를 놨다. 카드 인쇄 텍스트는 정책대로 `ICON_RULES`를 유지한다. 혼용 라벨 **195행 → 0**, 로그의 영어 event 줄 **1,438/3,572(40%) → 0**.
- **3단계 레이아웃**(`6f39e39`·`67032b1`·`7e984ac`). 공용 카드 열 여덟 개가 각자 접히고 `c`가 전부 접는다. Bene Tleilax board는 열 안에서 **31배 축소**(본 보드 10배)라 연구 칸 20px였는데 "크게 보기"가 **5.6배·연구 칸 115px**로 연다. 좌석 패널의 카드 줄을 "자세히"로 접어 후반 **2,189px → 936px**(751px 칸에 3.2개, 이전 1.4개 — 넷이 다 들어오지는 않는다).
- **4단계 e2e 그물**(`9e86cd4`·`74dba36`·`97ef0b8`·`22b8d69`). 끝난 판·전 확장·두 번째 뷰포트가 전부 미검사였다. `common.py`의 하드코딩 뷰포트를 선택 인자로 바꿔(기존 8종 무변경) 노트북·좁은 폭을 열었다. **≤1100px에서 공용 카드가 보드를 밀어내 `#board`가 468×0**이 되던 결함을 45% 상한으로 막았다(그 45%는 보드를 존재하게 하는 하한이지 숙고한 비율이 아니다).
- **규칙 근거로 고친 표시 결함 하나**: 종료 순위표의 Garrison 칸이 `troops_garrison`만 찍었는데, 동점 판정은 `troops_garrison + commanders_garrison`을 쓴다(**OQ-047**, 사용자 판정 2026-09-08). seed 7에서 9로 표시되고 10으로 판정, 6으로 표시되고 7로 판정됐다.
- **한글 IME 버그**(`dde1b3b`, [`lessons.md`](lessons.md) 2026-09-20). `c`·`s`가 **영문 자판에서만** 동작했다 — 한글 IME가 켜지면 `event.key`가 `"ㅊ"`/`"ㄴ"`다. `event.code`로 맞추고 조합 중인 키는 무시한다. 내가 "실제 브라우저에서 확인했다"고 보고한 뒤 사용자가 찾았다. 이제 e2e가 한글 자판이 실제로 보내는 이벤트를 쏜다.
- **방법 메모**: 새로 더한 단언은 전부 **옛 코드에 돌려 실패를 확인**했다(A/B). 워크플로가 제안한 30건 중 27건은 "렌더러가 읽는 것과 같은 데이터를 비교한다" 또는 "그 상태에 도달할 수 없다"로 기각했다. strip의 가로 스크롤 보존은 코드를 쓴 뒤 **1090·1000·820·700px에서 재 보니 한 번도 넘치지 않아** 되돌리고, 대신 도달 불가임을 단언했다.

## 2026-09-21 M10 순위 보상 첫 성공·평가 seed 결함 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v107, 변경은 `training/`·`evaluation/`·`cli/`·`scripts/ab/`)

**1,000 iteration 규모에서는 이 설정이 여전히 학습한다 — 다만 그 원인은 순위 보상이 아니다**(다음 날 대조군이 반증, 아래 "2026-09-21 오후" 절). 순위 보상(`--rank-rewards`)으로 2081에서 1,000 iteration(`checkpoints/2026-09-20/rank-1k`, 14.6초/it, 재시작·예외·잘린 판 0).

- **판정**(서로 다른 두 설계 · 겹치지 않는 세 seed 대역, 전부 실패 0):
  | 측정 | 새 체크포인트 | 귀무 | 결과 |
  |---|---|---|---|
  | 자기 대 자기 3명(설계 확인) | 25.0%, 순위 2.500 | 25% | 편향 없음 |
  | 2:2 미러 seed 9000~ (1,400경기) | 58.9% | 50% | **+17.9%p** [+12.7, +22.9] |
  | 2:2 미러 seed 20000~ (1,400경기) | 56.6% | 50% | **+13.1%p** [+8.0, +18.3] |
  | 1대3 seed 9000~ (1,400경기) | **32.4%**(SE 1.3) | 25% | **+7.4%p = 5.7 SE** |
  | 휴리스틱 3명 상대 200경기 | 92.5% | — | 이전 89.0% |
  평균 순위 −0.27 ~ −0.35, VP 마진 +0.63 ~ +0.93로 일관. 전날 잰 귀무 임계 ±7.7%p를 명확히 넘는다.
- **귀속은 그날 미확정이었고, 다음 날 기각됐다**: 이것은 "순위 보상 1,000 iteration 대 출발점"이지 "순위 보상 1,000 대 기존 보상 1,000"이 아니었다. 정황이 보상 쪽을 가리켰지만 **대조군이 같은 크기로 올랐다** — 아래 절.
- **행동은 안 바뀌었다**: 덱 9.25 → **8.96**장, 구매 실행율 14.0% → **9.1%**, VP 8.02 → 7.96. 더 강해졌는데 전략은 그대로이고 오히려 더 lean하다. 같은 날 탐침(아래)과 일관된다 — 순위 보상은 새 전략을 준 게 아니라 **같은 전략을 더 정확히 두게** 했다.
- **구매 탐침**(스크래치 변형, 2,800경기): 네트워크는 그대로 두고 구매 결정만 강제하면 `net_buy_always` **−17.0%p** [−22.0, −12.1], `net_buy_half` **−11.0%p** [−15.9, −6.0] — 세 지표 모두 갈렸고 **용량-반응이 단조**다. census로 개입을 확인했다(덱 9.25 → 17.94장, 구매율 100%, 그런데 VP는 8.02 → 8.03). **카드를 안 사는 것은 국소 최적에 갇힌 게 아니라 이 엔진에서 옳은 판단**이며, 이 저장소의 두 baseline(휴리스틱 94% 구매, rollout은 휴리스틱 playout)이 공유하는 전략 사전이 틀렸을 가능성이 높다.
- **평가 seed 결함**(`afb3064`): `_evaluate`가 `start_seed`를 넘기지 않아 **모든 실행의 모든 평가가 seed 0~24를 반복**했다. 한 실행의 계열은 표본의 나열이 아니라 **같은 작은 표본을 반복 측정한 것**이라 평균을 내도 소용이 없다. 이것이 실제로 결과를 숨겼다 — 위 실행은 고정 25 seed로 열 번 모두 24.5%(평평)를 읽었는데 새 350 seed로는 32.4%였다. 밤새 지켜봤다면 "또 실패"로 읽었을 것이다. 이제 평가마다 `EVAL_SEED_BASE`에서 겹치지 않는 블록을 쓴다.
- **순위 보상**(`df2e9ce`, 기본 꺼짐): 승자독식(+1 / −1/3) 대신 순위를 [+1, −1]에 선형으로 편다(4인 1, 1/3, −1/3, −1; 합 0). 승자독식은 좌석당 0.811 bit인데 엔진이 이미 계산하는 순위는 2.0 bit다. 환경과 대회 승리 판정은 불변 — [rl-environment.md](rl-environment.md) "보상"이 학습 쪽 몫으로 남겨 둔 변환이고 M10 계획서의 ablation 항목이다. **플래그가 먹었는지는 관측으로 확인**했다: `value_loss`가 0.27 → 0.35~0.42로 올랐고(순위 보상의 분산 0.556 대 승자독식 0.333), `explained_variance`도 0.27 → 0.34로 올랐다.

## 2026-09-22 사다리 — 재적응 후 다시 정체, 학습 중 평가의 역전 버그 (Mac mini, master 직접 커밋)

`checkpoints/2026-09-21/long-2k`: 대조군 끝(3081)에서 기존 보상으로 **2,000 iteration**(3081 → 5081, 14.5초/it, 재시작·예외·잘린 판 0). 판정은 2:2 미러 1,400경기 셀들, 전부 실패 0.

- **사다리**:
  | 구간 | iteration | 승률 차 | 판정 |
  |---|---|---|---|
  | 2081 → 3081 (앞 절, 대조군) | 1,000 | **+19.1%p** [+14.3, +24.0] | 갈림 |
  | 3081 → 4000 | 919 | +3.0%p [−2.1, +8.1] | 잡음 안 |
  | 4000 → 5081 | 1,081 | +1.6%p [−3.3, +6.4] | 잡음 안(VP 마진만 +0.19로 미미하게 갈림) |
  | 2081 → 5081 (누적) | 3,000 | +15.0%p [+9.7, +20.1] | 갈림 |
  **큰 상승은 규칙 정정 직후의 첫 1,000 iteration에만 있고, 그 뒤 2,000 iteration은 잡음 안이다.** 휴리스틱 3명 상대 88.5%, 덱 10.85장·구매율 17.5%(조금씩 더 산다).
- **유력한 해석 — 규칙 재적응**: 2081은 **옛 규칙(codec v105)으로 학습된 정책**이고 v107로 이관될 때 새 행동의 정책 head 행이 0으로 시작했다. 가중치 확인: 2081에서 전부 0인 행 **295개** 중 **228개가 3081까지** 활성화됐다(평균 노름 0 → 0.076 → 4000에 0.104 → 5081에 0.127; 기존 행은 0.64로 거의 불변). 상승이 몰린 바로 그 구간이다. 즉 **+19%p는 "기존 설정이 여전히 학습한다"가 아니라 "옛 규칙 정책이 정정된 규칙에 다시 맞춰졌다"일 가능성이 높다.** 다만 이것은 **정황**이다 — 새 행이 활성화된 것과 상승이 그 행 덕분이라는 것은 다르고(노름은 기존 행의 1/8), 인과 확인은 하지 않았다.
- **앞 절의 해석 정정**: 앞 절은 대조군의 +19.1%p를 "기존 설정은 여전히 학습한다", "1400→2050 정체는 계측 한계였을 수 있다"로 읽었다. 사다리가 그 읽기를 뒤집는다 — 재적응 뒤 현재 설정은 **1,000 iteration당 +2~3%p 이하로 다시 정체**했고, 옛 정체도 실재했을 가능성이 다시 높아졌다. 전·후 두 점으로는 "X만큼 변했다"만 말할 수 있고 "계속 오른다/멈췄다"는 사다리(세 점 이상)가 있어야 한다([lessons.md](lessons.md) 2026-09-22).
- **학습 중 평가의 역전 버그**(`fe2196c`): `_evaluate`가 "`checkpoint:`로 시작하는 첫 요약 행"을 읽었는데, 상대도 체크포인트면 둘 다 그 접두어를 갖고 `summarize`는 이름순으로 정렬하므로 **먼저 정렬되는 옛 상대 디렉터리의 행**을 읽었다. 그 행은 3좌석이라 보고값은 **(1 − 실제) / 3** — 동률에서는 같고, 강해질수록 **내려간다**. 발견: 한 평가를 같은 입력(체크포인트·상대·seed)으로 CLI에 재현하니 학습 중 평가가 기록한 21.3%가 CLI에서는 36.0%였고, (100 − 36.0) / 3 = 21.3이다. 고친 `_evaluate`는 같은 입력에서 36.0%·순위 2.28로 CLI와 정확히 같다. **이번 주 체크포인트 상대 평가는 전부 뒤집혀 있었다**(귀무 3팔, 순위 보상, 대조군, long-2k). 결론은 전부 사후 대회 + `paired.py`에서 나왔고 그 경로는 처음부터 옳았으므로 **결론은 유효하다**. 기본 상대(`heuristic`)는 접두어 충돌이 없어 과거 수치도 영향 없다.
- **`f8e5a5f`의 원인 진단 정정**: 그 커밋은 순위 보상 실행의 상승을 숨긴 원인을 "seed 0~24 반복"이라고 적었다. seed 반복은 진짜 결함이었지만 **숨긴 것은 이 역전**이다((1 − 0.324) / 3 = 22.5%, 그 실행이 기록한 24.5%와 가깝다). 커밋은 다시 쓰지 않고 여기와 `fe2196c`에 정정을 남긴다.
- 작은 실수: 사후 사다리 스크립트가 중간점 경로를 `iteration_04081.pt`로 **계산해 박았는데** 번호 체크포인트는 전역 iteration의 250 배수(… 4000, 4250 …)라 그 파일이 없어 두 셀이 즉시 실패했다(각 1,400경기 중 0 완료). 예약 시점에는 파일이 아직 없으므로, 학습이 끝난 뒤 **실제 목록에서 골라야** 한다. `iteration_04000.pt`로 다시 돌렸다.
- **다음**: 현재 설정은 다시 정체했다 — 같은 설정을 더 돌리는 것은 기대값이 낮다. 남은 지렛대는 첫 계획의 B(좌석 상대 다양화 — 이 정책은 heuristic·rollout을 이미 압도하므로 새 상대가 필요하다), 64판(메모리는 열려 있다), 표현력(정체성 슬롯 임베딩, action head 인수분해).

## 2026-09-21 오후 대조군 — 순위 보상 기각, "정체" 재검토 (Mac mini, master 직접 커밋)

`checkpoints/2026-09-21/control-1k`: 앞 절의 순위 보상 실행과 **명령이 글자 단위로 같고 `--rank-rewards`만 뺀** 1,000 iteration(같은 출발점 2081·같은 학습률·같은 seed·같은 worker; 14.1초/it, 재시작·예외·잘린 판 0). 플래그가 꺼진 것은 관측으로 확인했다(`value_loss` 0.266·EV 0.281 — 순위 보상 팔의 0.392·0.343과 다른 대역).

- **직접 A/B(1,400경기, seed 30000~)**: 순위보상 대 대조군 — 승률 **+2.9%p [−2.3, +8.0] 잡음 안**. 평균 순위 −0.072 [−0.136, −0.009], VP 마진 +0.239 [+0.092, +0.386]로 순위보상 쪽이 아주 조금 낫지만, 순위 보상이 순위를 최적화하는 건 정의상 당연하고 **이기는 것은 승률**이다. → **순위 보상은 효과가 없다. 기각.**
- **대조군도 같은 크기로 올랐다**(같은 seed 대역·같은 설계): 2:2 미러 vs 출발점 **+19.1%p [+14.3, +24.0]**(순위보상 팔 +17.9), 1대3 **31.2%**(순위보상 32.4, 귀무 25%), 휴리스틱 3명 상대 89.5%, 덱 9.62장·구매율 12.0%.
- **따라서 전날의 "첫 성공"은 보상이 아니라 1,000 iteration이다.** 그리고 그것이 더 큰 발견이다 — **기존 설정은 여전히 학습한다**.
- **"정체"를 다시 읽어야 한다.** 2026-09-20의 귀무 측정(기존 보상 **200** iteration = +0.7%p [−5.2, +6.6])과 모순되지 않는다: 200 iteration당 약 +3.8%p는 그 CI 안에 완전히 들어간다. **"측정되지 않았다"는 "0이다"가 아니었고**, 그 절이 덧붙인 "정책은 정말로 멈춰 있다"는 과한 해석이었다. 같은 논리로 **1400→2050의 650 iteration(기대 +12%p쯤)도 당시 판정 도구(400경기 4자 표)의 분해능 아래였을 가능성이 크다** — 이 저장소가 세 세션 동안 쫓은 정체는 상당 부분 계측 한계였을 수 있다. 다음 작업은 (a) 기존 설정으로 길게 잇기, (b) 1400·1650·2050을 새 도구(2:2 미러 1,400경기 + `paired.py`)로 다시 붙여 그 구간이 정말 평평했는지 재측정.
- **방법 교훈**: 가설을 지지하는 큰 결과가 나왔을 때 대조군 없이 핸드오프에 적었다면 그대로 굳었을 것이다. 상관으로 찾은 원인은 개입으로 확정한다([lessons.md](lessons.md) 2026-09-11)는 규칙이 이번에는 하루 만에 값을 했다.

## 2026-09-20 M10 자 만들기·행동 census 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v107, 변경은 `evaluation/`·`cli/tournament.py`·`training/loop.py`·`scripts/ab/`)

사용자 요청: "학습을 이어가볼까 해. 일단 어떤 방식으로 해야할지 계획해보자" → 후보 넷 중 **"자부터 만들기"**와 **전 확장 유지**를 사용자가 골랐다. 학습은 돌리지 않았다.

- **v107 재측정**(규칙 정정 뒤 처음). 세 체크포인트 모두 이관이 무손실이다(32,720행 유지 / 267 신규 / 271 폐기, 관측 4,327열 그대로). 실제 대국 1,200판에서 불법 행동 0·실패 0. 휴리스틱 3명 상대 200판: 1650 **89.0%**, a2081 **89.0%**, b2050 **90.5%**(±2.2) — 옛 규칙의 83.0/88.0/83.5%와 비교할 수 없다(휴리스틱도 의무 Spy로 같이 바뀌었다). **자는 여전히 포화**다.
- **"정체"는 부분적으로 자의 문제였다.** 1 대 3 페어 셀 600판(귀무 25%)에서 두 팔 다 출발점 위다 — a2081 **27.5%**(+1.4 SE), b2050 **29.0%**(+2.3 SE), 평균 순위·VP 마진이 두 셀 모두 같은 방향. 2026-09-19의 "어느 팔도 1650보다 강해지지 않았다"는 400판 4자 혼합표에서 나온 값이고, 그 설계의 잡음 바닥이 재려던 효과보다 컸다.
- **로그 전수(651~2081, n=1,431)**: entropy 0.636·explained_variance 0.269·value_loss 0.271이 **전 구간 평평**하고 기울기가 0이다(첫 100 0.2701 대 마지막 100 0.2721). **1400에서 성격이 바뀌는 필드가 없다** — 정체는 학습 중 평가 계열에만 보인다. 종료 보상 분산 0.333 대비 가치 함수는 1/4만 설명하고 표본 밖은 0.07~0.22다. 한 좌석의 ~190개 결정이 전부 같은 스칼라를 받고, iteration당 독립 표본은 **게임 32개**다. 승/패는 좌석당 0.811 bit, 이미 계산해 버리는 순위는 2.0 bit다.
- **메커니즘 정정 둘(코드로 확인).** (1) `optimizer.step()`은 **minibatch마다** 돈다(`--minibatch 1024`에서 iteration당 ~24회). `games_per_iteration`은 step당 행 수가 아니라 **한 minibatch가 뽑을 수 있는 서로 다른 게임 라벨 수**를 정하고, 총 게임 수를 맞추면 두 팔의 optimizer step이 같아진다. (2) `seat_rotations`는 순환 중복을 제거한다 — 2:2는 **2회전**, 1대3은 4회전. 과거 A/B의 표본 수가 2배 틀려 있었다.
- **자(커밋 셋).** `3da40c2` `match_rows` + `dune-imperium-tournament --matches`(경기별 JSON 행: seed·설정·좌석별 순위와 VP), `ea4a4e2` 학습 중 평가를 `config.workers`로(200경기 95초 → 48초), `0602dae` `scripts/ab/paired.py`(짝지은 차이 + **seed 군집** 부트스트랩 CI). **요약표의 두 승률을 빼지 않는다** — 한 seed의 회전은 같은 게임이라 한 군집이다. 실측으로 값어치가 증명됐다: 2:2 미러 60경기에서 **VP 마진은 +0.644 [+0.122, +1.189]로 갈렸고 같은 경기의 승률은 +13.3%p [-10.0, +36.7]로 잡음 안**이었다.
- **행동 census — 이 세션의 가장 큰 발견. 학습된 정책은 카드를 사지 않는다.** 시작 덱이 10장인데 **9.25장**으로 끝난다(휴리스틱 22.6~24.7장). 덱빌딩 게임에서. 원인은 "못 산다"가 아니다: 구매가 합법인 결정이 **게임당 15~21회** 있고 그중 **14~29%만** 산다(휴리스틱 94~95%). 상대가 사는 테이블에 앉혀도 거의 변하지 않아(14.0% → 28.6%, 덱 9.94 → 10.81) **테이블 구성에 적응하지 않는다**. 그런데도 이긴다 — 휴리스틱 3명 상대 순위 **1.12**, VP **11.25 대 5.73**.
- **네트워크가 이 저장소의 탐색 에이전트를 압도한다**(프로젝트가 한 번도 재보지 않은 대전): `rollout` 1명 대 체크포인트 3명 96경기에서 rollout이 **9.4%**(귀무 25%), 순위 2.917, VP 마진 −1.215 — 세 지표 모두 갈렸다. `rollout`의 playout이 `heuristic`이므로 **두 baseline이 같은 전략 사전(카드를 많이 산다)을 공유하고 둘 다 진다**. 즉 이 정책에게 더 가르칠 것이 있는 상대가 지금 저장소에 없다 — pure self-play는 구조상 25%다. M10 계획서의 미구현 항목인 **league**가 여기서 직접 정당화된다.
- **기계 함정(macOS).** `mem-summary.json`의 `max_group_rss_mib`은 부하 지표가 아니다 — 압축 때문에 **페이징 중인 실행이 건강한 실행보다 낮게 찍힌다**. 앱을 띄운 채(Chrome·VS Code·ChatGPT·Claude 약 4 GiB) 돌린 3 iteration 스모크는 **iteration당 50초**(수집 22 + 갱신 27)로 과거 15.5초의 3.2배였고, `max_group_rss_mib`은 **3,366**(건강한 실행 8,665), `max_compressed_mib` 6,372, 스왑 2.9 GiB였다. 갱신(메인 프로세스 배열 작업)이 4.1배가 되는 것이 페이징 신호다. **긴 실행 전에는 앱을 닫고 첫 2~3 iteration의 시간을 15.5초와 대조한다.** 기능적으로는 정상이다(잘린 판 0, entropy·EV가 과거 대역).
- **희소 legal set**(`0c18728`): 기록된 step이 카탈로그 전체 폭의 dense mask(32,987 B) 대신 **제시받은 행동 인덱스**만 압축 행 형태로 들고, `dense_masks`가 갱신 직전 minibatch의 행만 펼친다. 행 길이는 ragged·정확이라 padding도 truncation도 없다(합법 행동이 빠지면 메모리 결함이 아니라 **학습 정확성 결함**이다 — learner의 log-prob이 이 mask 위에서 계산된다). **수치 중립을 실측으로 확인**했다: 같은 체크포인트·seed·설정으로 재개하니 이전 실행의 iteration을 소수점 6자리까지 재현한다(entropy 0.608383, EV +0.243194, policy loss +0.004124, 24,598 step). 부수 효과로 이 Mac의 페이징이 사라져 전 확장 iteration이 **50.5초 → 15.2초**(수집 23.1→8.6, 갱신 27.4→6.6, worker RSS 1,111→678 MiB, 스왑 2,927→2,173 MiB)가 됐다 — 앱을 닫지 않은 채다. 64판도 메모리상 열렸다.
- **재실행 귀무 분포 — 측정 완료**(`checkpoints/2026-09-20/null-s{1,2,3}`, 3팔 × 200 iteration, 출발점·설정 동일·seed만 1/2/3, 14.6~15.1초/it, 재시작·예외·잘린 판 0). 대전은 2:2 미러 600경기 6셀, 실패 0.
  - **팔끼리**: seed 1↔2 +0.7%p, 1↔3 +0.3%p, 2↔3 +2.3%p — seed 자체가 만드는 흔들림은 작다.
  - **팔 대 출발점**: seed 1 **+1.7**, seed 2 **−5.0**, seed 3 **+5.3**%p로 **부호가 갈리고**, 풀링하면 **+0.7%p [−5.2, +6.6]**. 평균 순위·VP 마진도 전부 잡음 안이다. → **200 iteration(6,400판)은 측정 가능한 변화를 만들지 못한다.** 651~2081의 내부 지표가 평평했던 것과 맞물린다.
  - **계측 한계**: 2:2 미러 600경기의 분해능은 차이에 대해 **±7.7%p**다. 필요한 경기 수는 제곱으로 는다 — 10%p는 약 1,400경기, 5%p는 약 5,700, **3%p는 약 15,800(셀당 4.4시간)**. **이 저장소의 과거 A/B는 전부 이 선 아래였다**(400경기로 2~5%p 판정, 학습 중 평가 200경기 SE 약 3%p). 9/19의 학습률 A/B도, 이 세션의 27.5/29.0%도 이 잡음 안이다.
  - **결론**: 200 iteration짜리 팔을 400~600경기로 판정하는 설계는 원리적으로 작동하지 않는다. 팔을 훨씬 길게 하거나(1,000+), 경기를 26배로 늘리거나, 분산이 더 작은 지표를 찾아야 한다. **작은 개입을 정밀하게 재는 방향이 아니라 큰 개입**으로 가야 한다.

## 2026-09-20 전 좌석 AI 게임 관전 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v107, 변경은 `server/sessions.py`의 검토 응답과 `server/static/`·`scripts/e2e/`)

사용자 요청: "모든 플레이어가 AI인 경우 '사람 좌석이 없어 보드를 볼 수 없습니다'가 나온다. AI가 어떻게 플레이하는지 구경하고 싶다 — AI의 각 턴을 1초 간격으로 쭉 보고 싶다."

- **왜 안 보였나**: view·행동 목록은 사람 좌석에만 주고(`_require_human`), 세션은 "사람 결정 또는 끝난 게임"에서만 쉰다 — 전 좌석 AI 게임은 `create_game` 요청 안에서 끝까지 돈다(heuristic 넷이면 0.13초, 약 620 step · 170턴). 즉 볼 좌석도, 기다릴 진행도 없었다.
- **설계**: 서버 구조(4.8절의 "요청 안 동기 실행")는 그대로 두고, 이미 있는 **리플레이 검토에 자동 재생**을 얹었다(`ac8cdeb`). 끝난 게임의 검토는 원래 아무 좌석이나 받고 전부 공개라(OQ-010 ruling 4) 권한 변경이 없다. 사람 좌석이 없는 게임은 `enterTable` → `watchGame()`이 **0 step부터 재생 중인 검토**로 연다. live 관전(진행 중인 사람 게임을 제3자가 보는 것)은 여전히 설계 11절의 후속 후보다 — 공개 전용 view가 필요하다.
- **재생**(`app.js`의 `playback`·`turnStops`·`playbackTick`): 단위는 **한 턴씩**(기본)/한 수씩, 간격은 0.25·0.5·**1**·2·4초. turn stop은 행동 로그의 턴 카드와 같은 규칙(`finish_agent_turn`·`finish_reveal`·`pass`·`pick_leader`가 턴을 닫거나 다음 행동의 좌석이 다름)이고, chance step은 앞 행동에 붙으며, 연달은 `pass`(아무도 안 쓴 Combat Intrigue 창)는 한 stop이다. 간격은 "움직임에서 움직임까지"로 잰다(응답 시간을 뺀다). 탐색(⏮·⏭·슬라이더)은 재생을 유지하고 손으로 넘기기(◀·▶·좌석 행동)는 멈춘다. 끝에 닿으면 멈추고 재생 버튼이 "처음부터 재생"이 된다.
- **같이 고친 검토 모드**(사람 게임의 검토에도 적용): 검토 응답에 가림 없는 세션 로그 `log`를 실었고(gzip 13~18 KiB) **행동 로그가 커서까지만** 보이며 방금 더해진 카드가 fresh다(전에는 위치와 무관하게 전체 로그). 헤더의 라운드·phase가 최종이 아니라 화면의 위치를 말한다. 검토 좌석을 바꿔도 위치가 유지된다(전에는 끝으로 튀었다). 이 브라우저가 둔 좌석이 아니면 손패 라벨이 "내 손패"가 아니라 "좌석 N (…)의 손패"다. 관전 중에는 끝에 닿아야 최종 순위가 뜨고, 검토를 나가면 순위표의 "AI 대국 다시 보기"로 다시 튼다.
- **실측**: `review_state`는 커서까지 매번 재생하므로 끝에서 약 70 ms, 페이지의 한 번 이동(요청 + 다시 그리기, 로그 카드 233장)은 약 145 ms — 0.25초 간격도 따라간다. rollout 네 좌석처럼 느린 agent는 생성 요청이 그만큼(분 단위) 오래 걸린다(기존 동작, 관전은 그 뒤에 시작).
- **검증**: pytest 1,784(새 테스트 `test_a_game_of_ai_seats_only_is_reviewed_with_its_whole_log`) · ruff · mypy. 브라우저 E2E 새 스크립트 `spectate.py` 43(stop 표 대조, 1초 간격, 로그·상태 줄·헤더, 조작 전부, 새로고침, 사람 게임은 혼자 재생되지 않음) + 회귀 `open_mode.py` 44 · `remote.py` 54 · `turn_controls.py` 25 · `staged_turn.py` 42 · `board_tokens.py` 49 · `recovery.py` 32 · `races.py --ab` 통과.
- 남은 후보: 재생 중 행동한 좌석으로 검토 좌석을 자동 전환(그 AI의 손패를 따라가며 보기), 방금 둔 턴의 칸·카드를 보드에서 spotlight, 느린 agent의 생성 대기 표시.

## 2026-09-20 Staban Tuek draft pick 되돌리기 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v107, 변경은 `server/session_log.py`뿐)

사용자 질문: "leader 고를 때 왜 staban tuek 고르는 선택지만 되돌리기 불가인 거지?"

- **원인**: 되돌리기 경계(`reveals_hidden_information`)는 `known_card_seats`에 없는 카드를 "모두에게 공개"로 읽는다. draft의 `pick_leader`는 Limited Allies("You start the game without Diplomacy in your deck" `[Staban Tuek card]`)를 미리 섞어 둔 덱에서 Diplomacy 사본을 걸러 내는 것으로 구현하는데(`rules/leader_draft.py`), 걸러 낸 카드는 trash 같은 zone으로 가지 않고 state에서 사라진다. 그래서 "아무도 모르던 덱 카드 → 모두가 아는 카드"로 판정돼 그 pick만 `undoable: false`였다. 다른 제거는 전부 공개 zone(`trashed` 등)에 남으므로 state에서 사라지는 카드는 이것 하나뿐이다.
- **판단**: 오탐이다. 시작 덱 열 장의 구성은 공개 정보이고, 이름으로 빼는 제거는 그 카드가 덱의 어디에 있었는지를 누구에게도 보여 주지 않으며 남은 아홉 장의 순서도 그대로다 — 되돌려도 새로 아는 것이 없다.
- **수정**(`8b6454e`): `_removed_by_leader_pick` — 그 step에서 Leader가 정해진 좌석의 덱에서 사라졌고, 그 Leader의 `removed_starting_card_ids`가 이름으로 지목한 카드만 예외로 둔다. "어느 zone에도 없는 카드는 공개가 아니다" 같은 일반 규칙은 일부러 피했다: zone 열거에서 하나가 빠지면 진짜 공개를 놓쳐 되돌리기로 정보가 새는 쪽(위험한 쪽)으로 틀리기 때문이다. 마지막 pick은 예전처럼 닫힌다(Contract 공개·round 시작의 chance). 클라이언트는 서버의 `undoable`만 읽으므로 `app.js`는 그대로이고 브라우저 E2E는 돌리지 않았다.
- **검증**: `tests/server/test_undo.py`에 경계 단위 테스트(예외의 좁음 네 가지: 다른 카드, 다른 Leader, 이미 Leader가 있는 좌석, 덱에서 손으로 간 경우는 여전히 공개)와 draft 세션 테스트(seed 0: 여섯 pick 모두 `undoable`, Staban pick 뒤 창 1단계, 되돌리면 열 장 덱이 순서까지 복원) 2건 — 둘 다 수정 전 실패 확인. pytest 1,783 · ruff · mypy.
- 떠 있는 서버는 재시작해야 적용된다(Python 쪽 변경).

## 2026-09-19 밤 ~ 09-20 새벽 보드 조각·아이콘 전사 정정 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v105→**v107**)

사용자가 직접 한 판을 두며 적은 아홉 가지(보드 조각 넷, Branching Path, Intrigue discard, Imperial Privilege, 공개 시 Persuasion, Spy 배치 의무)에서 시작했다. UI 항목은 그대로 고쳤고, 규칙 항목은 **아이콘 전수 점검**으로 번져 사용자 목록 밖의 오전사 둘(Bene Tleilax c7r3, Influence 4 보너스)을 더 찾았다. 커밋은 넷 + 문서: `82a0423`(UI), `c9aec0a`(Trash-Intrigue 아이콘, v106), `7188523`(Spy 배치 의무), `2c967b7`(Influence 4 보너스, v107). 교훈 둘은 [lessons.md](lessons.md) 2026-09-19.

- **보드 조각을 인쇄된 자리에**(`82a0423`; `display/board_layout.py`의 새 표 넷, 카탈로그 `tracks.control_flags`·`maker_spice`·`maker_hooks`·`influence.alliance_size`, `maker_hooks_token`·`alliance_tokens`): Control marker는 칸 아래 **인쇄된 깃발**(Arrakeen·Spice Refinery·Imperial Basin, 3.18 × 3.82, 제비꼬리 notch 20.7%)에 좌석 색 단색 SVG로 `[Main p. 20]`, bonus spice는 Maker **육각형**(2.79 × 2.40, Tuek's Sietch 타일 포함) 위의 spice 육각형 + 수량 `[Main p. 15]`, Maker Hooks는 garrison 옆 **후크 슬롯**(3.4 × 4.88; 대비를 올려야 보이는 인쇄)에 토큰 그림을 좌석마다 돌리고 뒤집어 `[Main p. 20]`, Alliance token은 진영 strip의 **점선 원**(지름 6.85, 중심 (7.56, 5.48 + strip offset) — 옛 눈대중 점은 1.5 위였다)에 있다가 `[Main p. 4]` 획득하면 상태창에 중복 표시하지 않고 빈 원은 보유자 색 고리가 된다 `[Main p. 7]`. 그림은 TTS 모드 캐시의 원본을 에셋 저장소 `tokens/`에 뒀고(`maker_hooks.png`, `alliance_<faction>.jpg`; 에셋 `e7f7741`), 없으면 같은 자리에 룰북 아이콘을 그린다. 좌표는 전부 스캔에서 쟀다(깃발·육각형은 밝기 run, 원은 점선의 원 fit, 슬롯은 밝기 profile의 peak) — 절차와 수치는 `board_layout.py`의 주석.
- **Intrigue discard 한 줄 + Reveal 미리보기**(같은 커밋): 공용 열의 Intrigue 카드 여섯 장 대신 "Intrigue discard N장 · trash M장" 한 줄이고 누르면 두 더미의 목록(최신 먼저)이 뜬다(`openPileList`가 여러 더미를 받는다). 서버 표시 계층에 `reveal_preview {persuasion, strength}`를 더했다 — `reveal_turn`의 dry run이 연 Reveal frame의 Persuasion과 그 뒤의 전투력이고, 손패 옆("지금 공개하면")과 Reveal 버튼에 뜬다. `strength_after`처럼 HTTP 응답일 뿐 엔진·관측과 무관하다.
- **Trash an Intrigue card 아이콘 전수 점검**(`c9aec0a`, codec v106): 룰북 아이콘을 범위 안의 모든 카드·타일·보드 그림에 다중 스케일 템플릿 매칭하니 진짜 일치(0.92 이상)는 여섯 곳, 일반 trash 아이콘은 0.80 이하로 갈렸다. 셋이 틀려 있었다 — **Branching Path**(아이콘 BG + **City**, 비용 **Intrigue trash**, 보상 Intrigue 1 + **spice 2**; 옛 전사는 Landsraad·일반 trash·troop 2), **Bene Tleilax c7r3**(비용이 Intrigue trash), **Imperial Privilege**(board는 이 아이콘, Board Guide 문장은 "discard" — [OQ-061](rules/open-questions.md#oq-061--imperial-privilege-인쇄된-trash-an-intrigue-card-아이콘과-board-guide의-discard), 사용자 판정으로 인쇄된 아이콘을 따라 `intrigue_trash`로 보낸다; 다시 섞이지 않으므로 뒤따르는 draw가 그 카드를 되뽑지 못한다). Branching Path 구현은 `card-implementer`에 맡겼고(Junction Headquarters의 provider를 공유, 보상은 `intrigue`·`spice` 아이콘 대기열) 나머지는 main이 했다.
- **Spy 배치 의무**(`7188523`, codec 불변): OQ-057로 채택한 디자이너 정오표("It is mandatory to place a Spy if you have at least one Spy in your supply")를 2026-09-08 감사가 공용 frame만 보고 "일치"로 적었는데, Espionage(`resolve_espionage_without_spy`)와 Intrigue `PlaceSpy` slot(`decline_intrigue_spy`)은 거절을 내고 있었다. 이제 supply에 Spy가 있고 놓을 post가 있으면 배치만 제시한다; supply가 비면 선행 recall이 선택이라 거절이 남고(공용 frame도 같게 고쳤다), recall한 뒤에는 의무다. Distraction의 시점 선택(OQ-016)과 인쇄된 "— OR —"는 그대로다.
- **Influence 4 보너스**(`2c967b7`, codec v107): 보드 스캔을 확대해 아이콘 시트와 대조하니 Emperor는 **Spy**(회색 원기둥), Spacing Guild는 **3 Solari**(숫자 든 동전)였다 — 엔진은 처음부터 troop 2·water 3으로 돌았다. Emperor의 Spy는 `GameState.pending_track_spies` 대기열 → `_advance_automatic`이 그 전이 직후 공용 `spy_placement` frame을 연다(디자이너 판정: 다른 player-initiated action 전에 끝낸다, OQ-057 (15)). heuristic sweep이 **교착 3건**을 잡았다(seed 92·72·31): Test of Loyalty처럼 Spy와 Emperor Influence를 같이 주는 Conflict에서 트랙 Spy가 보상 Spy frame(지급 시점의 supply로 셈) 위에 끼어 마지막 Spy를 가져갔다 → 트랙 Spy는 그 Conflict의 보상 frame이 끝난 뒤에 열고, 놓을 수 없게 된 보상 Spy frame은 `combat_reward_spy_unavailable`로 걷어낸다. 덤으로 Conflict의 고정 Influence 보상이 상태를 다시 조립하며 **Navigation 대기열을 버리던** 잠재 결함(Y'rkoon이 그런 보상으로 2에 닿으면 Navigation이 안 열림)도 같은 자리에서 고쳤다.
- **검증**: 커밋마다 인덱스 트리를 스크래치 폴더로 내보내 그 트리에서 pytest·ruff·mypy를 돌렸다(1,775 → 1,776 → 1,779 → **1,781**). golden digest는 규칙 커밋마다 그 트리에서 다시 계산해 고정했다(인코더·view 파일은 바이트 동일, 달라진 것은 대국 경로). 마지막 트리의 sweep(`--soundness-interval 25 --rotate-leaders`): heuristic base+CHOAM 1,000·전 확장 400·draft 400, random 1,000·400 — 실패 0. 브라우저 E2E는 아래 "마감" 줄.
- **M10에 미치는 영향**: 환경의 규칙이 바뀌었다 — Emperor 4단계가 troop 2 대신 Spy, Guild 4단계가 water 3 대신 Solari 3, Spy 배치 의무, Branching Path. **1650·2050 체크포인트는 옛 규칙에서 학습한 정책**이다. 형식 2라서 codec v105 → v107로 이관은 되지만(새 행동 행은 0에서 시작), heuristic 상대 83~88%·4자 대전 표는 옛 규칙의 수치이므로 **새 규칙에서 다시 잰 뒤** 이어 학습한다(heuristic 자체도 규칙 변화를 같이 겪는다). 저장된 판(`~/.dune-imperium/saves`, 자동 저장)은 replay 기반이라 바뀐 규칙이 닿은 뒤의 판은 불러오기가 어긋나거나 실패할 수 있다.
- 작업 방식 메모: 사용자의 서버(8000)가 이 체크아웃의 정적 파일을 그대로 서빙하므로 `app.js`는 매 저장이 유효한 상태가 되게 고쳤고, 검증 서버는 `.claude/launch.json`의 새 `ui-verify`(8765, 저장 폴더 `/tmp/dune-ui-verify-saves`)로 따로 띄웠다. Branching Path를 맡긴 subagent가 같은 작업 트리에서 도는 동안 main이 다른 규칙을 고쳐 서로의 테스트가 흔들렸다 — 같은 트리에서 병행할 때는 **파일 경계와 "남의 실패는 무시"를 위임 prompt에 미리** 적는다(이번에는 도중에 메시지로 알렸다; subagent는 혼란 중에 `git stash`/`pop`을 한 번 했고 손실은 없었다). 섞인 변경을 단위별 커밋으로 나누는 데는 0-context hunk를 골라 `git apply --cached --unidiff-zero`로 넣는 스크립트와, 인덱스 트리를 내보내 검증하는 스크립트를 썼다(스크래치).
- 남은 후보: Agent·Spy 토큰의 숫자 제거(토큰 스타일 통일), Control marker·Agent 토큰의 그림화(모드에 색상별 깃발 그림이 있다), Combat 보상 Spy의 "supply가 비면 먼저 recall" 선택(지금은 지급 시점의 supply만큼만 frame을 연다 — 기존 단순화), Imperial Privilege 판정(OQ-061)의 공식 확인.
- 마감: 마지막 트리에서 브라우저 E2E 전부 통과 — `board_tokens.py` 49, `staged_turn.py` 42, `open_mode.py` 44, `remote.py` 56, `turn_controls.py` 25, `races.py --ab` 통과, `recovery.py` 32. 떠 있던 8000번 서버는 건드리지 않았다(재시작해야 새 규칙과 카탈로그 필드가 적용된다).

## 2026-09-19 오후 M10 Mac mini 이관·실행 3 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v105, 변경은 `scripts/train/`뿐)

사용자 요청: "다른 PC에서 진행하던 학습을 이어서 진행". 기준선은 pytest 1,767 · ruff · mypy 통과, `origin/master`와 일치에서 시작했다.

- **이관 확인**: 사용자가 복사해 둔 `checkpoints/2026-09-18/lr1e-4-long/`의 `latest.pt`·`iteration_01650.pt`가 0번 항목의 sha256과 일치하고,
  `dune-imperium-checkpoint inspect`가 형식 2·codec v105·관측 v20·iteration 1650·optimizer yes를 보고했다.
- **가드·감독기의 macOS 이식**(`bd8732f`): `run_guard.py`는 macOS에서 `vm_stat`·`sysctl`·`ps`로 같은 `mem.csv`를 쓰고(+`compressed_mib`·
  `pressure_level`), 커널 압박 수준 임계 두 번 연속에 그룹을 중단한다(가용 메모리 바닥은 기본 꺼짐 — 어느 수준이 위험인지 모른다). 표본
  수집의 fork가 실패하면 직전 표본을 되풀이한다(메모리가 가장 모자랄 때 가드가 죽으면 감독기가 살아 있는 그룹 위에 재시작한다).
  `train_overnight.py`는 `--detach`(fork + setsid), macOS에서의 `caffeinate -i -s -w <pid>`, 플랫폼별 바닥 기본값을 얻었다. Linux 경로와
  기본값은 그대로다. 검증: 크기를 아는 작업의 그룹 집계(메인 324 + worker 3×224 MiB = 1,016 MiB), 바닥 규칙으로 밟은 중단 경로
  (`exit=-15`), 고아 worker 정리, 분리 실행 2 iteration 완주와 `caffeinate` 해제, 수동 중지(감독기·학습 그룹·`caffeinate` 모두 0).
  **임계 압박 분기는 실제로 일으켜 보지 않았다.**
- **자원 스모크**(README의 절차: 최신 체크포인트에서 `--resume`, 가드 아래): 수치는 0번 항목. 8 worker·CPU 2 iteration이 37.9초.
- **`--device mps` 시험**(0번의 미검증 항목): 수치 일치·이득 5%로 채택하지 않았다(0번 항목).
- **worker 수**: 4·5·6·8·10을 같은 체크포인트에서 재 4를 택했다. 실행 3의 수집 중 코어별 부하(Mach `host_processor_info`, 2초 창 12개)는
  **P코어 4개(cpu 6~9) 99.5%, E코어 6개 0~25%**였다 — "하네스가 띄운 프로세스가 E코어에 묶여 있다"는 가설은 기각이고, 4 worker는 P코어를
  다 쓰며 E코어는 논다. "worker를 늘리면 E코어에 걸린 chunk가 정적 분할(`specs[index::workers]`)의 꼬리가 된다"는 설명과 맞지만, 8 worker에서
  chunk별 소요를 직접 재지는 **않았다**(실행 중에는 두 번째 학습을 띄우지 않는다). 후속 후보는 아래 "처리량 메모".
- **실행 3 시작**: 13:36:32, `checkpoints/2026-09-19/lr1e-4-mac`, HEAD `bd8732f`(깨끗한 트리), `provenance.txt`를 남겼다. 스모크가 다루지 않은
  경로인 학습 중 평가까지 지켜봤다: 1700에서 200판 84.5%·실패 0·약 95초(수치는 0번 항목).
- **학습률 A/B로 전환**(같은 날 15:40, 사용자: "1650에서 lr을 더 낮춰보는 것도 있었는데"): 실행 3의 평가가 평평해(0번 항목) 그것을
  대조군으로 삼고 (b) lr 3e-5를 띄웠다. 띄우기 전에 "옵티마이저 상태에서 재개하면 `--learning-rate`가 먹는가"를 작은 네트워크로 확인해
  **먹지 않는다는 것을 발견**했고(`lr after restore_optimizer: 0.0001 (config says 3e-05)`), (a)를 멈춘 뒤 고쳐 커밋했다(`61b09df`, 회귀 테스트
  2건은 수정 전 실패 확인; pytest 1,768). 핸드오프의 재개 명령이 (a)였다는 이유로 후보 넷 중 하나를 묻지 않고 고른 것은 내 잘못이다 —
  후보가 여럿 적혀 있으면 긴 실행을 띄우기 전에 어느 것인지 묻는다.
- **A/B 결과**(17:45 (b) 종료, 17:45~17:54 대전 평가): 두 학습률은 구별되지 않고 두 팔 모두 출발점 1650과 같은 수준이다(수치와 읽기는
  0번 항목과 `checkpoints/2026-09-19/ab-1650/SUMMARY.md`). 중간에 (b)가 네 번 연속 오르는 구간(78.0 → 87.0)이 있었지만 (a)도 2050에서
  86.0으로 튀었고 대전은 평평했다 — 학습 중 평가 몇 점의 흐름으로 결론을 말하지 않은 것이 맞았다. 세션 종료 시점에 도는 학습은 없다.
- **덤 — 고아 worker 36개**: 이 Mac에 2026-09-16 저녁(2일 17시간 전)에 시작된 이 프로젝트 venv의 spawn worker 36개(resource tracker 1 +
  worker 8이 네 묶음)가 부모 없이(ppid 1) 남아 있었다 — 그날 A/B의 `BrokenProcessPool`(lessons 2026-09-16)이 남긴 것으로 보인다. CPU는
  0%였지만 footprint 합계 947 MiB(대부분 스왑)였고, SIGTERM으로 정리하자 스왑 사용이 1,082 → 604 MiB로 내려갔다. 절차는
  [lessons.md](lessons.md) 2026-09-19 항목과 `CLAUDE.md`의 "Long-running commands"에 적었다.
- zsh는 따옴표 없는 변수를 단어로 쪼개지 않아 `kill $pids`가 통째로 실패한다 — 여러 PID는 `xargs kill`로 넘긴다.

## 2026-09-18 밤 ~ 09-19 아침 M10 학습률 실험·밤샘 실행 2 세션 요약 (Windows PC WSL, 코드 변경 없음, 관측 v20, codec v105)

- **실험 1(잡음 가설의 가장 싼 확인)**: A/B 대조군과 모든 조건이 같고 `--learning-rate 1e-4`만 다른 REINFORCE를 550에서 100
  iteration(58분). 학습 중 평가(80판) 76.2/72.5/77.5/83.8%(대조군 70.0/72.5/71.2/70.0%); 대전 — 4자 400판 lr@650 33.0%,
  출발점 550 24.8%, 대조군 650 24.5%, lr@600 17.8%; heuristic 3명 상대 200판 lr@650 81.0%(출발점 76.5%, 대조군 75.5%).
  같은 실행의 600은 테이블에서 가장 약해 체크포인트 간 요동은 남아 있었다.
- **밤샘 실행 2**(`checkpoints/2026-09-18/lr1e-4-long`, 22:20~08:10, 650 → 1650): 같은 설정·옵티마이저 상태를 이어 1,000 iteration,
  `--eval-every 50 --eval-games 50`(200판). 재시작·예외·평가 실패·잘린 판 0, 게임당 721~806 step, 그룹 메모리 최대 11.3 GiB.
  200판 평가: 700~800 73.0/71.5/72.5, 850~1100 79.5/77.0/79.5/75.5/75.5/77.0, 1150~1350 80.0/81.0/83.0/83.5/81.0, 1400~1650
  87.5/84.0/82.5/77.0/85.5/84.5. 대전 결과와 체크포인트 정보는 위 "다음 구현 순서" 0번.
- **읽기**: 같은 데이터·같은 알고리즘에서 한 번에 덜 움직이게 한 것만으로 정체가 풀렸고(3e-4는 550에서 멈추고 700에서 후퇴),
  같은 배치를 세 번 학습한 PPO는 무너졌다 — 둘 다 "갱신이 32판의 승패 잡음에 끌려다닌다"는 가설과 맞는다. 다만 한 계보·한 seed.
- 새 교훈 없음. 학습 중 평가의 실패 기록(`eval_failures`)은 세 실행 모두 0이었다. 사용자 결정: 다음 학습은 Mac mini에서 이어간다.

## 2026-09-19 Agent turn 단계별 선택 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v105, 변경은 `server/static/`·`scripts/e2e/`뿐)

- 사용자 제안: Agent turn에 합법 행동이 전부 한 줄로 뜨는 것은 AI 학습용 표현이지 사람용 UX가 아니다. 보낼 수 있는 칸의
  하이라이트는 좋다. **카드 고르기(graft 고려) → 보낼 칸 → 효과 처리** 순서였으면 하고, 다른 PC의 학습에 영향이 없게 UI만.
- 판단: UI만으로 된다. 서버는 Agent turn을 `agent_turn{card_id, space_id, cost_option?, graft?}`의 평평한 목록으로 주고(코덱·학습이
  쓰는 그 목록), 페이지는 그것을 고른 것으로 걸러 보여 주다가 **남은 행동 번호 하나**를 지금처럼 POST한다. 엔진·코덱·관측·학습
  코드는 그대로다. **Graft는 제안과 순서가 다르다**: 엔진은 `agent_turn`의 `graft` 인자로 첫 카드와 칸을 먼저 정하고 뒤따르는
  `graft_partner` frame에서 `choose_graft_partner`로 둘째 카드를 고르며, 가능한 파트너는 고른 칸에 따라 달라질 수 있다(OQ-057).
  그래서 "카드 → 칸 → (Graft 여부) → 파트너" 순서가 UI만으로 되는 자연스러운 흐름이고, 두 장을 먼저 고르게 하려면 서버의
  표시용 선계산이 필요하다(미착수).
- 구현(`app.js`의 "staged Agent turn" 절): `state.pick {cardId?, spaceId?}`는 페이지 안에만 있고 고르는 동안 요청이 없다.
  `legalActionsFor`가 staged turn에서는 pick에 맞는 placement만 세므로 **카드·칸의 빛이 단계마다 좁혀진다**(칸을 먼저 골라도
  된다 — 그 칸에 갈 수 있는 카드가 빛난다). 같은 것을 다시 누르거나 Escape·단계 칩으로 취소, 다른 카드·칸을 누르면 교체(교체
  후보는 옅게 빛난다), 함께 갈 수 없는 조합은 pick을 바꾸지 않고 알린다. 카드+칸으로 placement가 하나 남으면 바로 실행하고,
  여럿이면(비용 옵션·graft) **칸 옆 선택창**(`openPlacementChooser`, 카드 팝오버 재사용)과 패널이 같은 선택지를 낸다 — 비용은
  카탈로그의 그 옵션 효과로, graft는 "이 카드만 / Graft — 함께 낼 카드는 다음에"로 적는다. pick은 남의 초인종 재렌더에도
  남고(설계 G7) 합법 행동이 더는 받쳐 주지 않으면 버려진다(`sanitizePick`). 패널은 단계 칩·안내·"또는" 아래 그 turn의 다른
  행동(Reveal 시작 등)·**"전체 행동 목록 보기" 토글**(`localStorage dune.fullActionList`, 새로고침에도 유지)이다. 뒤따르는
  frame(파트너·trash 대상·Spy 자리)은 짧은 목록 그대로 두고 "테이블에서 빛나는 카드나 칸을 눌러 골라도 됩니다"만 더했다(기존
  `tableClick`이 이미 그렇게 동작한다).
- 검증: 새 E2E `scripts/e2e/staged_turn.py` 31항목(매 단계의 빛을 서버 목록과 대조, 요청 수, 선택창, 토글) — 첫 실행이 **실제
  결함**을 잡았다: 전체 목록 모드에서는 목록이 길어 맨 아래의 "단계별로 고르기" 토글이 로그 패널에 가려 눌리지 않았다 → 토글을
  목록 위로. `open_mode.py` 44·`remote.py` 56, pytest 1,764 · ruff · mypy. Immortality 판에서 graft placement(같은 카드·칸에
  "이 카드만"/"Graft")와 파트너를 손패 클릭으로 고르는 것까지 Chrome으로 확인(스크래치; 합법 행동 38개짜리 turn이었다).
- **같은 날 이어서 — graft는 두 장을 먼저 고른다**(사용자 지적으로 앞의 판단을 고침). 위에서 "두 장을 먼저 고르려면 서버의 선계산이
  필요하다"고 적은 것은 틀렸다. 규칙은 "어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다. 어느 아이콘을 썼든 두 카드 모두
  Agent를 보낸 것으로 취급한다" `[Immortality p. 10]`이고, 엔진은 그것을 **카드마다의 graft placement**로 나열한다(놓는 카드의
  아이콘으로 닿는 칸; `_placements_for_card`). 그러니 두 장이 갈 수 있는 칸은 두 카드의 graft placement의 **합집합**이고 페이지가
  이미 받은 목록만으로 계산된다. "어느 카드의 아이콘을 쓸지"도 플레이어가 정할 일이 아니다 — 같은 선택지(비용 옵션·할인·Infiltrate)를
  두 카드가 다 내놓으면 하나로 치고 먼저 고른 카드를 놓는 카드로 보낸다(실제 상태 27가지에서 A→B와 B→A의 결과 상태·선택지가
  같았고, 다른 것은 다음 frame에서 어느 카드의 Agent box가 먼저 뜨느냐뿐이었다).
  구현: `state.pick.partnerId`. 카드를 고른 뒤 **함께 낼 수 있는 손패 카드**(둘 중 하나가 Graft 카드이고 둘 중 하나에 graft
  placement가 있는 카드; `canPair`)에 점선 빛과 ＋ 표시가 붙고, 누르면 교체가 아니라 합류한다(그 밖의 카드는 전처럼 교체).
  `matchesPick`은 pair면 두 카드의 graft placement만, `pickCandidates`가 같은 선택지를 하나로 친다. 칸을 누르면 placement를
  보내고 `followWithPartner`가 뒤따르는 `graft_partner` frame에 `choose_graft_partner`를 이어 보낸다(요청 둘, 엔진의 두 스텝 그대로).
  특정 파트너가 있어야만 열리는 칸(점유된 칸의 Tleilaxu Infiltrator, Ghola의 Bond 아이콘 약속 OQ-057, Usurp)이어서 엔진이 그
  파트너를 내놓지 않으면 자동으로 보내지 않고 엔진의 파트너 선택을 그대로 보여 준다. 한 장만 고르고 칸을 누른 뒤 "이 카드만 /
  Graft"를 고르는 앞의 흐름도 그대로 된다. Row의 카드와 graft하는 Usurp는 파트너를 뒤에 고르는 흐름만 쓴다.
  **부수 결함**: 카탈로그의 `graft` 표시가 Tleilaxu 덱 12장에만 있고 Immortality Imperium 덱의 Graft 카드 5장(Dissecting Kit·
  Bene Tleilax Researcher·Interstellar Conspiracy·Planned Coupling·Replacement Eyes)에는 빠져 있었다(카드의 "Graft" 표기도 누락).
  엔진의 `card_is_graft`와 같은 집합(17장)인지 테스트로 고정했다. 선택창의 선택지 문구에 할인(Navigation Chamber)·Infiltrate를 더했다.
  검증: `staged_turn.py` 42항목(7번 graft 시나리오: ＋ 표시, 합류, 합집합, 요청 둘, 두 카드 in play), `open_mode.py` 44,
  `remote.py` 54(되돌리기 분기 건너뜀), pytest 1,765 · ruff · mypy.
- **같은 날 이어서 — 병력 배치 조절기와 Reveal 구매 패널**(사용자 지시 "둘 다 진행해"). 둘 다 평평한 행동 목록의 "보기"이고
  엔진·코덱·관측은 그대로지만, 이번에는 **서버의 표시 계층(`server/sessions.py`)에 필드 둘**을 더했다(HTTP 응답일 뿐 `PlayerView`·
  관측 인코더와 무관):
  - `legal_actions`의 각 행동에 `strength_after`(`strength_preview`): 이미 하던 dry run의 결과 상태에서 읽은 **그 좌석의 running
    combat strength**, 그 스텝이 전투력을 바꿀 때만, 되돌릴 수 없는 스텝(숨은 정보 공개·chance)은 제외. "troop 하나 = 2"를
    브라우저가 셈하지 않는 이유: Conflict의 첫 유닛이 검을 켜고 마지막 유닛이 끈다 — 엔진의 수치를 그대로 쓴다.
  - Reveal frame의 `summary.decision.persuasion`: frame context의 남은 Persuasion(구매마다 그 카드의 비용만큼 준다). reveal과
    구매가 모두 공개라 테이블 공개 정보다.
  클라이언트: `count`만 다른 같은 id의 행동들(`deploy_troops` 1·2·3…)을 **한 줄 + 숫자 조절기**(`countFamilies`/`countRow`)로
  접는다 — 패널과 **Conflict 구역의 자기 사분면 옆**(`.force-stepper`)에 같은 줄이 서고 숫자(`state.counts`)를 공유하며, 보내는
  쪽은 전부·되돌리는 쪽은 하나가 기본값, 확정 버튼에 "⚔ 지금 → 뒤"가 붙는다. Conflict를 드나드는 넷(`deploy_/withdraw_troops`·
  `_commanders`)은 count가 하나 남아도 같은 조절기를 쓴다. 전투력이 바뀌는 다른 행동(후퇴 등)의 버튼에도 같은 미리보기가 붙는다.
  Reveal frame의 패널(`renderRevealPanel`)은 남은 Persuasion · 이번 Reveal에 산 카드(세션 로그의 `card_acquired`, 되돌린 것 제외) ·
  "Reveal 효과" · "살 수 있는 카드"(카탈로그의 비용, Solari·specimen 변형 구분; 테이블의 빛나는 카드를 눌러도 된다) ·
  맨 아래 초록색 **"구매 끝 · Reveal 종료"**.
  검증: 새 E2E `scripts/e2e/turn_controls.py` 25항목(조절기가 한 줄인지, 보드의 조작이 패널 숫자도 움직이는지, 고르는 동안 요청
  0, 미리보기 = 서버의 `strength_after` = 실행 뒤 실제 전투력, 회수, Persuasion이 비용만큼 주는지, 산 카드 목록, 출구가 맨
  아래인지), `staged_turn.py` 42 · `open_mode.py` 44 · `remote.py` 56, pytest 1,767(서버 테스트 2개 추가) · ruff · mypy.
- 남은 후보: 단계 안내의 한글 prompt, Usurp의 Row 카드를 먼저 고르는 graft, `agent_effects` frame의 효과 목록 정리.

## 2026-09-18 Combat marker 그림 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v104, 변경은 `display/`·`server/`뿐)

- 사용자 지시: 친구들과 쓰던 Tabletop Simulator 모드(워크샵 3522149839 "Dune Uprising Bloodlines scripted")의 에셋을 UI에
  쓰고 싶다 → "전투력 토큰만 일단 적용해보자. 보드판 하단 전투력 표시를 이 이미지로, 색깔별 토큰, 21 이상부터는 +20 토큰".
- 모드 조사 결과(자세한 수치는 이 세션 대화; 요점만): 에셋 URL 354개는 전부 Steam 공개 CDN, 영어 카드 시트 95장은 이미 가진
  Dune Cards Hub 스캔과 해상도가 비슷하거나 낮아 얻을 것이 없다. **`assets/board/map.jpg`·`bene_tleilax.jpg`는 이 모드의 보드
  이미지와 sha256이 같다**(보드는 이미 TTS 출처). 한글 카드 시트는 한글화 모드 3종(3092549193·3446667675·3025517639)에 있고 카드
  Nickname이 영어라 manifest `name`과 매칭된다 — `assets/cards/ko/`를 채우는 후보(미착수; `display/images.py`는 이미 `ko/` 우선).
- 구현(`e54e035`): 모드의 색상별 `ForceToken` 타일 4개의 앞면(검)·뒷면(`+20`) PNG 8장을 비공개 에셋 저장소 `tokens/`에
  바이트 그대로 두고(출처 URL은 그 README), 서버가 `/tokens`로 마운트한다(`DUNE_IMPERIUM_TOKEN_DIR`, `create_app(tokens_dir=)`).
  `display/token_images.py`가 파일 이름과 좌석 색(blue·red·green·yellow = 좌석 0~3, `app.js`의 `SEAT_COLORS`와 같은 순서)을
  정하고 **두 면이 다 있는 색만** 적용한다. 카탈로그 `strength_tokens`(좌석별 `{front, plus20}` 또는 null)와
  `tracks.strength.token_rows`(칸의 빈 부분 중심 y 91.1/95.6)·`token_size`(3.0%)를 `renderTrackMarkers`가 쓴다. 그림 토큰은
  인쇄된 숫자 위가 아니라 **칸의 빈 부분**에 놓이고, 같은 칸의 좌석들은 부채꼴로 펼친다(칸 3.75 폭, 최대 펼침 4.95). 뒤집는
  규칙 자체(20 초과 → `+20` 면, 23은 3번 칸)는 그대로다[Main p. 12]; 그림이 없으면 예전의 그린 토큰·좌표 그대로.
- 검증: pytest 1,739 · ruff · mypy, 브라우저 E2E `open_mode.py` 44·`remote.py` 56(Chrome, 토큰 200 응답), 그리고 클라이언트
  상태를 임시로 바꿔 0/0/0/0, 5·12·23·12, 20·21·40·7, 9 동률 넷을 3배율로 캡처해 눈으로 확인. `/tmp/dune-e2e-venv`를 이 Mac에 새로 만들었다.
- 서버 테스트의 모든 `create_app(...)`에 `tokens_dir=tmp_path / "no-tokens"`를 달았다(다른 에셋 경로처럼 기기 독립).
- 같은 날 이어서(사용자 지시 "점수 토큰과 원로회 점유 상태 토큰은 크기가 같은 원형 토큰이야. 숫자 없이 색으로만 구분해"):
  Score marker와 Councilor token을 **같은 크기의 원판**(`seatDisc`, CSS `.seat-disc`, 좌석 색만·숫자 없음, 지름
  `tracks.disc_size` = 스캔 폭의 2.2%)으로 바꿨다. 사용자 후속 지시로 그라데이션·반사 없이 **Influence cube와 같은 단색**
  (같은 `SEAT_COLORS`, 같은 테두리·그림자)이다. 좌석 색은 `app.js`의 `SEAT_COLORS` 한 표에서만 나오고(Agent·Spy·Control
  토큰, cube, Alliance 고리, 병력 칩, 좌석 패널·로그 테두리, 원판), **유일한 예외는 Combat marker 그림의 몸통색**이다 —
  그림 자체가 남색 `#0c184f`·암적색 `#970507`·암녹색 `#2b5125`·샛노랑 `#fff70f`라 UI 좌석 색과 다르고 테두리 1px만 좌석 색이다. 그림 에셋이 필요 없는 CSS 토큰이라 모든 기기에 적용된다. 원판이 칸을
  채우게 되면서 눈대중이던 좌표를 스캔에서 다시 쟀다: High Council 원 중심 `(42.18|46.0|49.83|53.64, 5.22)`(지름 2.91),
  Score track은 구분 다이아몬드(x 94.25·98.75, 0번 칸 y 91.92~97.19, 간격 5.275)로부터 칸 중심 `94.56 − 5.275·n`,
  13점 이상이 모이는 문양은 y 27.0. 점수가 같은 좌석은 겹치지 않게 모인다(`discCluster`: 혼자면 칸 정중앙, 둘은 나란히,
  셋은 삼각형, 넷은 2×2) — 좌석별 고정 사분면은 혼자 있는 토큰이 칸 중심에서 벗어나 점수가 달라 보여서 버렸다.
- 실수(→ [lessons.md](lessons.md)): 새 모듈을 `display/tokens.py`로 쓰다가 **이미 있던 같은 이름의 모듈을 덮어썼다**.
  서버가 import 오류로 안 떠서 바로 알았고 `git checkout HEAD --`로 복원, 새 모듈은 `token_images.py`로 했다.
- 같은 날 세 번째(사용자 지시 "원형토큰 크기가 원로회 점유칸의 흰 동그라미와 정확히 일치해야 해. 이 원형토큰은 공용으로 여기저기
  많이 쓰여. 틀레이락스 보드판의 토큰도 원래 그 토큰"): 원판을 **공용 player disc**(`seatDisc`)로 정리했다. 크기는 각 스캔이
  **인쇄해 둔 원판 자리의 지름 그대로**다 — 본 보드는 High Council 흰 고리의 바깥지름 176 px/6012 px = `2.93%`
  (`board_layout.SEAT_DISC_SIZE`), Bene Tleilax 스캔은 인쇄된 원판 자리 7곳이 전부 324 px/5551 px = `5.84%`
  (`bene_tleilax_layout.DISC_SIZE`; 방사 프로파일의 가장 가파른 경계로 맞춤). 같은 실물 토큰이고 두 스캔의 해상도만 다르다.
  Bene Tleilax 보드의 research·Tleilaxu track 토큰(`bt-token`, 텍스트 배치의 `rtoken`)도 숫자 없는 같은 원판이 됐고,
  시작 칸에서는 **인쇄된 자리에 좌석별로** 놓인다(`track_start_discs` 2×2, `research_start_discs` 세로 3칸 + 넷째는 플라스크
  위). 다른 칸은 hex의 어두운 위 절반·track의 윗줄이 먼저고 셋 이상이면 아랫줄(인쇄 보너스를 덮는다), 폭 7.5%인 좁은 track
  칸의 둘은 위아래로 선다(`discCluster`의 `fromTop`·`upright`). y 좌표가 높이의 퍼센트라 `aspect`(5551/3952)를 함께 준다.
  원판이 실물 크기가 되면서 Score track 한 칸(4.5 × 5.275)에는 하나만 들어가므로 같은 점수의 좌석은 칸 안에서 **겹쳐** 모인다
  (`victory_points.cell`, `discHalfGap`). 테스트: `tests/unit/display/test_bene_tleilax_layout.py` 신설(2개), pytest 1,741.
- 같은 날 네 번째(사용자 지시 "영향력 트랙의 네모 토큰은 보드판에 인쇄된 네모 모양에 딱 맞아야 해"): Influence cube를
  각 스트립이 Influence 0 자리에 인쇄한 네모(16개 전부 95 px/6012 px = `1.58%`, 각진 모서리)와 같은 크기로 했다
  (`INFLUENCE_CUBE_SIZE`, `tracks.influence.cube_size`). 그 네모들의 중심으로 0단계 행(23.24)과 네 열(4.63·6.58·8.52·10.47)을
  다시 잡았고, **스트립 간 세로 offset이 틀려 있던 것**을 고쳤다 — 24.3·48.7·73.2 → `24.56·49.08·73.72`(금색 밴드의 검은 틈과
  주황 선으로 교차 확인). 아래쪽 스트립일수록 큐브가 최대 0.52% 위로 어긋나 있었다. 1~6단계는 chevron 밴드 중심의 열 평균.
  Chrome에서 큐브 16개의 네 변을 측정 픽셀과 대조해 최대 편차 0.054%(스캔 3.2 px; Bene Gesserit 스트립이 2~3 px 오른쪽).
  **테두리를 상자 밖으로 뺐다**: `border: 1px`는 색 면을 그만큼 줄여서(576 px 스테이지에서 큐브의 22%) 인쇄된 칸보다
  작아 보였다. 큐브와 원판 둘 다 `box-shadow: 0 0 0 1px #111` 고리로 바꿔 **색 면 자체가** 인쇄된 크기다.
- 같은 날 다섯 번째(사용자 지시: Shield Wall 토큰을 부서지기 전까지 맵에, 위치는 보드판과 룰북 참고; Immortality의 Research
  Station과 Tuek's Sietch는 첨부 이미지로): 세 이미지는 같은 TTS 모드 캐시의 파일과 크기가 같아 캐시 원본을 썼다.
  - **Shield Wall 토큰**(`assets/tokens/shield_wall.png`, 카탈로그 `shield_wall {image, box, rotation}`): "Shield Wall을 Spice
    Refinery 아래의 표시된 위치에 놓는다" [Main p. 4]. 그 표시는 대비를 올려야 보이는 옅은 자국(잔해 그림 포함)이고, 보호 구역의
    흰 경계선이 거기서 끊긴다. 토큰 그림을 **180° 돌리면**(모드에서도 보드 rotY 180·토큰 0) 모양이 자국과 맞고 토큰의 흰 줄이
    경계선의 두 끝을 잇는다. `SHIELD_WALL_BOX = (63.27, 42.4, 7.75, 7.8)`: 왼쪽 변은 자국의 밝기 경계(63.27), 세로는 토큰의
    가로줄이 경계선의 가로 끝(y 49.59)에 오도록, 폭은 인쇄된 잔해를 모두 덮고 오른쪽 변이 경계선 시작(71.0)에 오는 7.75
    (7.56이면 잔해가 삐져나온다). 모드에 저장된 토큰 좌표는 1%쯤 위로 어긋나 있어 쓰지 않았다. `view.shield_wall_present`일 때만
    그리고, 제거 뒤에는 인쇄된 잔해와 기존 "파괴됨" 표시가 남는다.
  - **Research Station overlay**(Immortality): 카탈로그의 공간 표시에 Immortality 변형이 아예 없어서 Immortality 판에서도
    "Recruit 2 troops, Draw 2 cards"와 Uprising 그림이 나오고 있었다(엔진은 이미 `Draw 2 + Research`). `space_option_effects(...,
    immortality=True)`와 `spaces[id].immortality {options, image, tile_box}`를 더했고(그 변형이 있는 공간은 research_station뿐,
    CHOAM과 겹치는 공간 없음 — 테스트로 고정), 그림 키는 `("location", "research_station_overlay")`. 타일 상자는 그림의 풍경·Agent
    아이콘·물방울을 인쇄본에 템플릿 매칭(NCC 0.94)해 `(38.81, 32.14, 15.58, 8.48)`.
  - **Tuek's Sietch**: 그림을 교체(디자인 다이어리의 검은 배경 렌더 → 타일 그림). 카탈로그가 `required_leader_id`·`tile_box`를
    내려주고, **Esmar Tuek이 있는 판에서만** hotspot과 타일 그림이 나온다(전에는 모든 판의 빈 사막에 보이지 않는 hotspot이 있었다).
    상자는 Imperial Basin의 Control 배너와 경계선을 피해 `(74.5, 56.8, 16.0, 9.03)`, 크기는 인쇄된 칸들의 그림 틀 폭 7.6%에 맞췄다.
  - 검증 서버는 사용자의 8000번 서버를 건드리지 않으려고 `scripts/e2e/common.ServerProcess`로 빈 포트에 따로 띄웠다.
    **떠 있던 서버는 재시작해야** 새 카탈로그 필드가 나온다(정적 파일은 즉시 반영되지만 Python은 아니다).
- 같은 날 여섯 번째(사용자 보고 "투에크 시치 보드칸이 이전의 이상한 이미지가 뜬다"): 서버는 새 파일을 내려주고 있었다. 원인은
  **브라우저 캐시** — 그림을 같은 이름으로 교체하면 URL이 그대로인데 에셋 mount는 `Last-Modified`/`ETag`만 보내므로, 브라우저가
  heuristic freshness로 옛 파일을 서버에 묻지도 않고 며칠씩 쓴다. 고침: `asset_url_versions`(`server/app.py`)가 서버 시작 때
  에셋 파일마다 mtime(ms)·크기로 버전을 만들고, 카탈로그가 카드 그림·아이콘·토큰·보드 스캔 URL을 전부 `<url>?v=<버전>`으로
  내려준다(`build_catalog(asset_versions=)`; 정적 mount는 query를 무시한다). 바뀌지 않은 파일은 URL이 같아 캐시가 그대로 살고,
  교체된 파일만 새로 받는다. **교체 뒤에는 서버를 재시작**해야 버전이 다시 읽힌다(파일 목록과 같은 시점). 테스트: 같은
  이름으로 교체 → URL 변경(`test_a_picture_replaced_in_place_gets_a_new_url`), 카탈로그 버전 부착. 교훈은 [lessons.md](lessons.md).
  검증 중 `scripts/e2e/remote.py`의 "guest holds seat 1"이 한 번 실패했다 — claim 직후 테이블은 바로 뜨고 좌석은 뒤따르는
  snapshot으로 아는데(`claimSeat` 주석) 검사 셋이 화면이 뜨자마자 `state.me.seats`를 읽던 **테스트 쪽 경합**이라 폴링
  (`holds_seats`)으로 바꿨다. 같은 스크립트의 통과 수가 54/56으로 갈리는 것은 무작위 판에서 "되돌릴 수가 없으면 건너뜀" 분기다.
- 남은 후보: Agent·Spy·Control 토큰과 자원 토큰의 그림화(모드에는 3D 모델뿐이라 2D 그림은 자원 토큰 정도), 한글 카드 시트로 `ko/` 채우기.
## 2026-09-18 저녁 M10 PPO 슬라이스·A/B 세션 요약 (Windows PC WSL, master 직접 커밋, 관측 v20, codec v105)

- **PPO 슬라이스(opt-in)**: `LearnerConfig.clip_ratio`/`--clip`이 정책 항을 clip된 surrogate로 바꾼다. 수집 정책의 log-prob은
  `update` 시작 시점의 가중치로 다시 계산한다(수집이 바로 그 가중치·mask로 돌았으므로 궤적·worker 전송은 그대로).
  `UpdateStats.clip_fraction`·`approx_kl`. 테스트가 "첫 PPO 스텝 = REINFORCE 스텝"과 "clip이 12 epoch의 정책 이동을 묶는다"를
  고정한다. `--clip` 없이는 동작 불변.
- **학습 중 평가의 실패 기록**: `IterationRecord.eval_failures`와 실행 폴더의 `eval_failures.log`. 전날 codec 결함이 평가 한 판을
  조용히 빼먹은 구멍을 막았다. `--eval-games`는 seed 수(좌석 회전 4배)임을 도움말에 적었다.
- **A/B(550에서 같은 seed·32판·8 worker·100 iteration, 순차)**: 대조군 58분, PPO(clip 0.2·3 epoch) 98분. 학습 중 평가(80판)는
  대조군 70.0/72.5/71.2/70.0%, PPO 55.0/33.8/37.5/42.5%. 대전(seed 1000+): 4자 400판 — 출발점 550 45.0%, 대조군 650 35.0%,
  PPO 650 12.5%, PPO 600 7.5%; heuristic 3명 상대 200판 — 출발점 76.5%, 대조군 75.5%, PPO 43.0%. PPO 진단은 내내 온건했다
  (clip_fraction 0.04~0.06, approx_kl 0.004~0.006).
- **진단(읽기 전용)**: 새 게임 24판의 value 설명력은 출발점 0.15·대조군 0.07·PPO 0.22 — PPO는 배치를 외우지만(배치 안 0.9+)
  일반화는 더 낫다, 즉 value 과적합은 원인이 아니다. 출발점 정책의 선택 상태 8,551개에서 KL(출발점‖x)/greedy 일치/entropy는
  대조군 575 0.40/56%/1.15·600 0.32/66%/0.76·650 0.49/54%/0.82, PPO 575 0.33/60%/1.09·600 0.68/41%/1.12. 가설(개입 미확인):
  배치의 독립 표본은 32판의 승패이고, 다중 epoch는 그 잡음을 증폭한다.
- `scripts/train/train_overnight.py --start-from`(다른 실행의 체크포인트에서 새 폴더로 시작), `fmt_iter.py`의 PPO 지표·평가 실패
  표시. 검증: pytest 1,752, Ruff, mypy. 다음: 학습률 1e-4 실험(같은 출발점, 100 iteration).

## 2026-09-17 밤 ~ 09-18 아침 M10 첫 학습·되돌리기 루프·이관·codec v105 세션 요약 (Windows PC WSL, master 직접 커밋, 관측 v20, codec v104→**v105**)

- 새 PC(i7-13700K, WSL2 Ubuntu 24.04) 첫 세션. 환경 구축(표준 동기화, `assets` symlink, E2E는 `scripts/e2e/`를
  `E2E_CHROMIUM=~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell`로 — 이 PC는
  ALSA stub 불필요), 기준 검증. **에셋 없는 머신의 테스트 수는 실측으로 "1개 skip만 차이"**임을 확인했다(위 기준선 문장).
  사용자 결정: 이 PC는 M10 학습 전용, M14는 다른 PC.
- **첫 실행(`checkpoints/2026-09-17/full`, 32판·8 worker)이 19 iteration에서 메모리 안전장치로 죽었다.** 원인은 메모리가 아니라
  정책: iteration 19 체크포인트의 표본 self-play 8판에서 결정의 80%가 `deploy_troops`/`withdraw_troops` 왕복이었고 잘린 판은
  결정의 82~90%가 바이트 동일 관측의 재방문, 이어 돌린 iteration 20은 32판 중 13판이 4,000 결정 상한(94,604 step, 메인 12.9 GB).
  step penalty(0.0005)와 결정 상한은 막지 못했고 수집 단계의 `_CycleGuard`는 2026-09-06의 부정 결과로 꺼져 있다. **개입으로 확정**:
  두 행동만 mask에서 빼자 같은 체크포인트·seed에서 게임당 결정 3,018 → 699, 잘린 판 3/8 → 0/8. 채택(사용자 결정 1번):
  `training.policy.UNDO_ACTION_IDS`(`withdraw_troops`, `withdraw_commanders`)를 `SelfPlayRunner(undo_actions=False)`(수집기 전용,
  엔진 `apply`에는 전체 합법 집합 유지)와 `NetworkAgent`가 정책에 제시하지 않는다 — OQ-029의 근거가 "배치는 turn의 다른 효과보다
  뒤에 해도 된다"이므로 마지막에 배치하는 정책은 잃는 것이 없다. on-policy(기록 mask = 제시 mask).
- **밤샘 실행(`checkpoints/2026-09-18/full-noundo`, 00:07~07:53, 837 iteration, 26,784판, 재시작 0)**: 게임당 716~876 step,
  잘린 판 누적 1, 그룹 메모리 약 10 GB로 평평. 평가(위 0번): 400~550까지 상승 후 정체·요동, 700 후퇴. 학습 중 평가는 20 seed ×
  좌석 회전 4 = **80판**이다(오차 ±5%p). BIOS에서 HT·E-core를 켜 24 스레드가 됐지만 **32판 iteration은 8 worker가 가장 빠르다**
  (16 worker 1.5배, 24 worker 2배 느림; 원인 미측정 — worker당 게임 수·E-core·67 MB 출력층의 메모리 대역 후보).
- **대회 도구**: `--workers N`의 worker가 torch 기본 스레드(논리 CPU 수)를 각자 잡아 결정당 205 ms였다 → 풀 initializer로 1 스레드
  (`OMP_NUM_THREADS`/`MKL_NUM_THREADS`, 사용자 값 존중) 9 ms, 결과 동일. 8 worker 이상은 이득 없음.
- **codec 결함(v105)**: 550의 학습 중 평가가 79/80판이었다 — seed 13, Chani 좌석에서 `retreat_leader_troops(commanders=1, count=13)`가
  codec에 없어 `encode`가 실패했고 `_evaluate`는 실패 판을 조용히 버린다. Fedaykin Maneuver의 Commander share count 범위를
  `retreat_intrigue_troops`와 같게 19까지 늘렸다(+28; v104 때 Intrigue 쪽만 고쳐졌던 것). `tests/adapters/test_action_codec.py`가
  엔진이 만들 수 있는 모든 troop·Commander 조합의 왕복을 고정한다.
- **체크포인트 이관(형식 2)**: 위 결함을 고치면 옛 체크포인트를 버려야 했으므로 먼저 만들었다(사용자 결정 순서). 저장 시 템플릿
  정체성 목록·관측 레이아웃 기록, 읽을 때 정체성으로 행·열 이동(새 항목 0, Adam 모멘트 동반), 원자적 쓰기, `stamp`, CLI
  `dune-imperium-checkpoint`. 밤샘 실행의 34개 파일을 v104에서 새긴 뒤 v105에서 이관 로드(32,963 유지 + 28 신규)·seed 13 게임
  완주·eval-550 80/80(59승)·`--resume` 2 iteration을 확인했다([rl-environment.md](rl-environment.md) "체크포인트의 버전 이관").
- 그 밖에 `--checkpoint-every N`(번호 체크포인트 주기), `RulesetConfig.from_identifier`, `scripts/train/`(메모리 감시 실행기,
  밤샘 감독기, Monitor용 watcher, 긴 게임 census). 검증: pytest 1,748, Ruff, mypy. 커밋은 기능 단위 7건 + 문서.

## 2026-09-17 자정 무렵 M14 슬라이스 6 리허설·운영 문서 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v104)

- 사용자 지시: "push하고 슬라이스 6 진행해. 로컬 워크트리는 지워줘. 원격은 지웠어". 슬라이스 5까지 push(`657f60c`), 워크트리
  `.claude/worktrees/m14-slice4-client`와 머지된 브랜치 `m14-slice4-client` 삭제(`git fetch --prune`로 원격 WIP 브랜치가 없어진 것 확인).
- 슬라이스 6의 본체는 **다른 집의 친구와 하는 실제 한 판**이고 그것은 사용자 몫이다. 이 세션은 자동화할 수 있는 부분을 했다:
  (1) 이 Mac mini에 Tailscale이 깔려 있어(`100.87.236.12`; 다른 기기 둘은 오프라인) 서버를 **그 주소에만 bind**하고 브라우저도 그
  주소로 들어가는 리허설 — 같은 머신이므로 WAN은 아니지만 origin은 친구들이 실제로 쓰는 것, 곧 **보안 컨텍스트가 아닌 평문
  HTTP**다. (2) 운영 문서 [remote-play-guide.md](remote-play-guide.md).
- `scripts/e2e`: `E2E_HOST`로 bind·접속 주소를 고른다. 그 주소에서 `remote.py` 56·`recovery.py` 32·`races.py --ab` 통과.
  `rehearsal.py`(15항목): `isSecureContext === false`, 복사 버튼이 링크를 선택해 두는 fallback, 신호음이 예외를 내지 않음, 쿠키가
  HttpOnly·SameSite=Strict·게임 경로 한정·`Secure` **아님**(평문 HTTP에서는 Secure 쿠키가 버려진다), `document.cookie`는 빈 문자열.
  그 주소에만 bind하면 `127.0.0.1`로는 연결이 거부된다(집 LAN·공개 인터넷에 안 열린다).
- **회선 에뮬레이션 실측**(DevTools `Network.emulateNetworkConditions`를 친구 쪽 브라우저에만, 전 확장, 캐시 없는 첫 접속, 두 번 같은
  값): 100 Mbit/s·RTT 20 ms — 둘 수 있는 테이블 0.2초·모든 이미지 1.8초·18.5 MB·한 수가 상대 화면에 29 ms(최대 0.2~0.3초);
  10 Mbit/s·RTT 120 ms — 0.8초·16.3초·18.6 MB·158 ms; 새로고침은 둘 다 0.03 MB(보드 스캔 두 장이 캐시된다). 받는 양의 거의 전부가
  보드 스캔(11.6 + 6.3 MB)이고 테이블은 그림 없이도 1초 안에 둘 수 있으므로 **웹용 축소본은 만들지 않았다**(설계 8.4절의 조건:
  실전에서 느릴 때만).
- **리허설이 드러낸 CLI 결함**(`8896ec8`): Tailscale이 꺼져 있으면 `--host 100.x`는 머신에 없는 주소다. uvicorn은 bind 실패를 자기
  로그 줄 사이에 적고, CLI는 그 전에 **뜨지도 않은 서버의 관리자 링크**를 이미 찍었다. `bind_problem(host, port)`가 먼저 probe해서
  링크 없이 이유(+ 비loopback 주소면 Tailscale 힌트)를 말하고 종료 코드 1로 끝난다. 시작 출력은 flush한다(파이프·파일로 받으면
  uvicorn 로그 뒤에 나오던 것). 테스트 3개(빈 포트 통과, 누가 listen 중인 포트, RFC 5737 주소 `192.0.2.1`로 `main()`이 링크 없이 1).
- Tailscale 공식 문서 재확인(2026-09-17, kb/1084): 초대는 이메일 또는 링크(재사용 가능, 30일 만료), 모든 플랜, 공유된 머신은 격리
  (들어오는 연결에 응답만), 공유한 쪽 tailnet의 ACL이 적용된다, 그리고 **받는 쪽 tailnet에서 호스트의 IPv4가 다를 수 있다** — 그때는
  친구가 방 링크의 `100.…` 부분만 자기 쪽 주소로 바꾼다(운영 문서에 적음; 방 링크를 호스트 이름 기반으로 만드는 것은 하지 않았다).
- 운영 문서의 사실 검증: 워크플로(읽기 agent 3, Sonnet·low)로 문서의 진술 27개를 CLI 플래그·출력 문구, 쿠키 속성, UI 문구(버튼·제목·
  안내 메시지), 세션 규칙(턴 보류·`undo_floor`·불러오기의 재확정 조건), 저장 위치와 대조했다 — 불일치 0.
- 확인하지 못한 것(운영 문서의 점검표): 실제 WAN 너머의 판, WSL2 호스트, 신호음의 실제 재생(자동 재생 정책), 몇 시간짜리 연결 유지
  (잠자기·Wi-Fi 전환 뒤 재연결), rollout AI 좌석의 체감.

## 2026-09-17 심야 M14 슬라이스 5 자동 저장·복구 세션 요약 (Mac mini, master 직접 커밋, 관측 v20, codec v104)

- 사용자 지시: "push하고 슬라이스 5 진행해". 슬라이스 4 머지(`de70942`)까지를 `origin/master`에 push한 뒤(양방향 0 확인) master에서
  바로 작업했다(슬라이스 1~3과 같은 방식). 범위는 `server/`·`cli/server.py`·`tests/server/`·`scripts/e2e/`뿐이다.
- **구조**(설계 4.7절·D6): "언제"는 세션 계층, "무엇을"은 앱 계층. `GameSessionManager.add_hand_over_listener(cb)` — `cb(game_id)`는
  `confirm_turn` 뒤에는 항상, `apply_action` 뒤에는 `_turn_passed`일 때만(확정 대기 중이 아니고 · 게임이 끝났거나 · 자기 step 뒤에 다른
  좌석의 action이 이어졌거나 · 결정이 다른 좌석에 있을 때) 불린다. 초인종과 같은 자리(변경을 만든 스레드, lock을 푼 뒤, publish 뒤)이고
  listener의 예외는 로그로만 남는다. `server/autosave.py`의 `Autosaver`는 **한 lock 안에서 문서를 만들고 쓴다** — 문서를 lock 밖에서
  만들면 두 요청이 거의 동시에 끝날 때 옛 문서가 새 문서를 덮을 수 있다. `SaveStore.write_autosave`는 슬롯 = game id, 원자적 교체,
  `"autosave": true`. 기본값은 접근 모드(remote 켬·open 끔), `--no-autosave`·`create_app(autosave=)`·`/whoami.autosave`.
- 실측(이 Mac, 사람 3 + heuristic 1을 끝까지, seed 20260917): base 자동 저장 112회·호출당 중앙값 3.1 ms·최대 6.1 ms·합계 0.36초,
  전 확장 89회·3.2 ms·최대 8.2 ms·합계 0.30초, 마지막 파일 170~179 KB. 그래서 동기(요청 스레드) 쓰기를 그대로 뒀다.
- 클라이언트: 저장 목록의 "자동 저장" 배지·현지 시각, 호스트 패널의 저장 블록(`GET /saves`는 모든 파일을 읽으므로 패널을 열 때·저장
  직후·버튼으로만), "서버 연결 끊김" 표시(폴링이 아무 응답도 못 받을 때), 폴링의 404는 "삭제 또는 재시작"이므로 "호스트의 새 방
  링크로 들어오세요"로 안내하고 죽은 방을 "이어 하기"로 제안하지 않는다. 함께 고친 슬라이스 4의 잠복 결함: 호스트 블록의 "입력 중에는
  다시 그리지 않는다" guard가 **버튼 클릭 뒤의 focus**에도 걸려, 호스트가 "좌석 비우기"를 누른 뒤 패널의 좌석 목록이 다시 그려지지
  않았다(E2E는 DOM이 아니라 상태를 단언해서 못 잡았다) → 편집 가능한 입력 칸에만 적용.
- **리뷰 워크플로**(finder 5관점 Sonnet·low + 반박 검증, 12 agent): 7건 전부 기각(전역 lock·동기 쓰기는 실측 비용상 무해, `.tmp`
  잔재·게임 삭제 뒤 남는 파일은 기존 동작/설계 범위 등). 다만 기각 사유를 확인하던 중 **기존 결함 하나가 드러나 따로 고쳤다**
  (`e3d4bac`): `confirm_turn`은 되돌리기 창을 닫는다고 약속하지만 창은 로그에서 읽히고 로그는 다음 chance·다른 좌석 step에서야
  닫힌다 — 다음 좌석이 아직 두지 않은 **사람**이면 확정한 좌석이 되돌리기로 턴을 다시 가져올 수 있었다(한 화면에서는 시점이 넘어가
  보이지 않고, 두 브라우저에서는 버튼이 남는다). 세션의 `undo_floor`가 `undo`·summary의 `undo`·턴 종료 pause의 창을 자른다. 회귀
  테스트는 floor를 뺀 코드에서 실패함을 확인했다. floor는 저장하지 않는다: 바로 그 순간의 저장을 불러오면 그 좌석에게 확정을 한 번 더
  묻는다(기존 `restore_game` 동작 — 복구 E2E에서도 그렇게 이어진다).
- 검증: pytest 1,732·Ruff·mypy. `tests/server/test_autosave.py`(14)·`test_autosave_app.py`(8)·`test_server_cli.py`(+6; 실제 프로세스
  SIGKILL → 같은 저장 폴더로 재시작 → 불러오기, revision = 자동 저장의 step 수)·`test_undo.py`(+1). 브라우저: `recovery.py` 32항목
  (파일 하나·`.tmp` 없음·한 턴 이내, 친구 화면의 끊김 표시 → 새 방 링크 안내, 호스트의 불러오기, 둘 다 복귀해 16 스텝 수렴),
  `remote.py` 54~56·`open_mode.py` 44·`races.py --ab` 통과, JS 예외·서버 오류 0.
- 위임: 자동 저장 테스트 세 파일은 `card-implementer`가 명세대로 썼고(src 무수정, `/whoami` 기대값 두 곳 갱신 포함) 메인 세션이
  검토했다. 설계·구현·E2E·되돌리기 수정은 메인 세션.
- 남긴 것: 호스트가 게임을 삭제해도 자동 저장 파일은 남는다(저장 목록에서 지운다) · 자동 저장은 동기라 저장 폴더가 멈추는
  파일시스템이면 턴을 넘기는 요청도 멈춘다(수동 저장과 같다) · `undo_floor`는 저장 형식 v2에 없다(위).

## 2026-09-17 밤 M14 슬라이스 4 마감 세션 요약 (Mac mini, `m14-slice4-client` 워크트리 → master, 관측 v20, codec v104)

- 사용자 지시: "다음으로 해야 할 작업 이어서 해, `origin/m14-slice4-client-wip`에 미완료 작업이 있었던 것 같다". 원격과 일치(양방향 0)와
  master 기준선(1,702 통과·Ruff·mypy — 앞 세션이 마지막 커밋에서 못 돌린 전체 pytest·mypy 포함)을 확인한 뒤 그 브랜치를
  `.claude/worktrees/m14-slice4-client`(로컬 브랜치 `m14-slice4-client`)로 받아 WIP 커밋 위에 쌓았다. 앞 세션의 스크래치 E2E는 WSL
  기기에 있어 없었으므로 이 Mac에 스크래치 venv + Playwright(시스템 Chrome, 브라우저 다운로드 없음)로 다시 만들었다.
- **재현**: 인수인계의 "호스트가 `applyAction(0)`을 반복하는 단계의 30초 타임아웃"은 이 Mac에서 같은 모양으로는 재현되지 않았다
  (그 스크립트가 없어 같은 실행은 아니다). 그래서 "서버가 지목하는 좌석이 한 스텝 두고 → 모든 페이지가 서버 상태로 수렴하는가"를
  매 스텝 검사하는 드라이버로 바꾸고, 용의자(`seatsChanged()`의 single-flight 밖 요청)를 **응답 지연 주입으로 직접 계측**했다.
- **원인 확정(개입)**: players만 바뀐 초인종 → `seatsChanged()` → `reloadIdentity()`가 seatless snapshot을 받아 `state.summary`·
  `state.me`를 덮어쓴다. 그 응답 하나를 읽자마자 0.7초 붙잡고 그 사이 상대가 턴 종료를 확정하게 하면, 기다리던 페이지의 summary
  이력이 `13/0/1 → 13/null/1 → 13/0/1`(revision/confirmation/owner)로 **과거로 되돌아가고**, 배너는 "좌석 0의 턴 종료 확정을 기다리는
  중"인데 서버는 그 페이지의 차례다. 초인종이 더 올 일이 없으므로 영구 정지다(양쪽이 서로를 기다린다). WAN·HTTP/1.1의 6연결 제한
  아래에서는 지연 주입 없이도 나는 순서다. 앞 세션의 증상(행동 버튼이 안 나타나 30초 대기)과 부합하지만 **그 실행 자체를 재현한
  것은 아니므로 "그때의 원인"이 아니라 "같은 증상을 만드는 확정된 결함"으로 적는다.**
- **고침**(`90bb420`): `state.summary`·`state.me`는 `openGame`과 `adoptSnapshot`만 쓴다. `reloadIdentity()`·`seatsChanged()` 제거,
  claim·release·좌석 변경은 전부 `refresh(summary, {seat})`(먼저 물을 좌석을 호출자가 알려 줄 수 있다: 방금 claim한 좌석, 또는 자리를
  비운 뒤의 `null`), `pickViewSeat(summary, seats)`는 **그 응답의 `you.seats`**에서 고르고, 좌석 상실은 `adoptSnapshot`이 "있었는데
  없다"로 감지해 좌석 고르기로 보낸다. snapshot 403은 seatless로 다시 물어 해결한다(줄 안에서).
- **둘째 경합**(수렴 검사가 8회에 1회꼴로 적발 → 개입으로 재현): 입장하는 페이지는 스트림을 열면서 snapshot을 요청하는데, 그
  snapshot이 자기 스트림의 연결보다 먼저 읽히고(`online: false`) 연결 초인종(`players` 채택)보다 늦게 도착하면 옛 `players`가
  되살아난다. 스트림 0.3초·snapshot 0.9초 지연으로 재현: 추가 바퀴를 끈 `app.js`는 stale, 현재 코드는 수렴(`races.py --ab`).
  고침: players 초인종이 비행 중에 오면 한 바퀴 더. 이 경합은 슬라이스 3부터 있었지만 그때는 `online`을 그리지 않아 보이지 않았다.
- players만 바뀐 초인종은 **내 좌석의 `claimed`·`name`이 바뀐 때만** 요청을 만든다(접속 점만 바뀐 알림은 요청 0개 — 슬라이스 3의
  설계 그대로). 내 좌석이 비었다고 나오면 seatless로 물어 403을 만들지 않는다. claim·release는 `state.busy`(자기 초인종 무시, 이중
  클릭 방지). POST의 403은 refresh를 거쳐 좌석 고르기로.
- **E2E가 드러낸 다른 결함 둘**: (1) remote 호스트에게 Seed 입력 칸이 보였다 — `fieldset label { display: block }`이 UA의
  `[hidden]`을 이긴다 → `[hidden] { display: none !important }`. (2) 서버(`9361562`): 스트림을 다시 여는 페이지가 방금 요청한
  `EventSource`를 닫으면 `@app.middleware("http")`(BaseHTTPMiddleware)가 `RuntimeError("No response returned.")`를 내고 uvicorn이
  ERROR 트레이스백을 찍는다 — 1 ms 안에 닫은 소켓 4/4 재현. `no-cache` 헤더를 순수 ASGI wrapper `_RevalidateUIFiles`로 옮겨 0/7,
  회귀 테스트 `test_a_stream_closed_before_its_first_byte_is_not_a_server_error`(옛 middleware에서 실패함을 확인).
- **리뷰 워크플로**(ultracode; finder 5관점은 Sonnet·low, 반박 검증만 세션 모델; 9 agent): 4건 중 확정 2 — 설계 7절 1항의 "마지막
  game id 기억 + 이어 하기" 누락(→ landing 화면의 버튼, 404면 기억 삭제), claim 응답이 나가기 뒤에 도착하면 테이블이 다시 뜸(→
  `openTicket`). 기각 2(검토 진입 중 나가기의 null 참조는 잡히고 무해 — 방어 코드만 추가; POST의 일반 실패 뒤 refresh 없음은 그 경로로
  놓치는 초인종이 없음).
- 검증: `scripts/e2e/remote.py` 56항목 5회 연속, `open_mode.py` 44항목(300 스텝 = POST 300 = snapshot 300, 클라이언트 로그 == 서버
  로그, 되돌리기 epoch, 검토 경합, 초인종 30 ms·스트림 차단 시 5.0초 뒤 폴링 전환·1.5초에 반영, 삭제 통지), `races.py --ab`, 실패한
  요청·JS 예외·서버 오류 0. pytest 1,703·Ruff·mypy.
- **E2E를 저장소에 둔다**(`74667eb`, [`scripts/e2e/`](../scripts/e2e/README.md)): 설계 10절은 "저장소 밖 스크래치"였지만 그 이유는
  의존성이었다. 스크립트가 세션 스크래치에만 있으면 기기를 옮길 때마다 사라진다(이번에 전부 다시 썼다). Playwright는 여전히
  프로젝트 의존성이 아니다. 테스트 작성 함정 둘을 README에 적었다: 동기 API의 route handler에서 `time.sleep`하면 다른 handler도 멈춘다
  (두 요청을 다르게 늦추려면 async API), handler에 기본값 매개변수를 두면 Playwright가 둘째 인자로 `Request`를 넣는다.
- 위임: `scripts/e2e`의 Ruff 정리(E501 15건 등)만 `card-implementer`에 맡기고 검토했다. 원인 분석·수정·E2E 설계는 메인 세션.
- 내 테스트의 오판 하나(기록용): "AI 좌석을 지나 턴이 첫 좌석으로 돌아온다"를 기다리다 타임아웃 — 첫 좌석의 첫 행동이 Reveal이면
  그 라운드에는 돌아오지 않는다. 제품 결함이 아니라 기대가 틀린 것이었고, 그래서 시나리오 고정 대신 "서버가 지목하는 좌석"
  드라이버로 바꿨다.

## 2026-09-17 원격 멀티플레이 설계·슬라이스 1 세션 요약 (master, 관측 v20, codec v104, 변경은 `server/`·`cli/server.py`뿐)

- 사용자 요구: 구현된 게임을 멀티플레이로 — **원격의 친구들과 각자 PC에서**. 지시: "설계 문서부터", 이어서 "제안대로
  확정하고 슬라이스 1 시작". 원격과 일치(양방향 0)를 확인했고, 설계 단계에서는 `src/`·`tests/`를 건드리지 않았다.
- 산출물: [multiplayer-design.md](multiplayer-design.md)(상태 **제안**), [implementation-plan.md](implementation-plan.md)의 M14 절,
  측정 도구 `scripts/measure_server_payloads.py`(Ruff 통과).
- 진단(코드 근거는 설계 문서 2절): 엔진은 이미 다인용이다 — 결정은 항상 한 좌석 소유, 좌석별 `PlayerView`·로그 필터,
  `revision`+`undo_count`, 턴 종료 확인. 빠진 것은 네트워크 세션 계층이다: 좌석 인증 없음(`_require_human`은 "사람 좌석인가"만
  본다), summary와 저장 메타데이터의 `game_seed` 노출(결정론적 엔진이라 seed = 모든 덱 순서), 저장→불러오기의 복제 세션,
  푸시 없음, 결정 소유자로 시점을 자동 전환하는 클라이언트, 갱신마다 로그 전체 재전송, `render()`의 `closePopover()`.
- 실측(전 확장 한 판, 사람 3 + heuristic 1, seed 20260917, 이 WSL 노트북): 726 step, 상태를 바꾸는 요청 663회, view 12 KB
  (gzip 2.7 KB), 로그 전체 중앙값 108 KB·최대 206 KB, 한 판 동안 로그만 **57.3 MB** 재전송(증분이면 0.66 MB), heuristic AI
  진행 포함 요청 서버 시간 중앙값 0.6 ms·최대 8.9 ms, 끝난 판의 저장 문서 267 KB·생성 33 ms. 그래서 AI 진행을 worker로
  옮기는 일은 급하지 않고(후속), snapshot + 증분 로그 + gzip이 슬라이스 2다.
- 외부 사실 확인(2026-09-17): Cloudflare Quick Tunnel은 SSE를 지원하지 않는다(공식 TryCloudflare 문서) → 폴링 fallback이
  필요하다. Tailscale machine sharing은 모든 플랜에서 되고 공유된 머신은 들어오는 연결에 응답만 한다(공식 KB 1084).
  lock 파일에 `websockets`·`wsproto`가 없어 WebSocket은 의존성 추가가 필요하고, Starlette 1.6.0의 `GZipMiddleware`는
  `text/event-stream`을 기본 제외한다(`.venv` 소스 확인).
- 확정: 같은 날 사용자가 설계 문서 12절의 D1~D7(좌석 claim 방식, Tailscale, 되돌리기 유지, 저장 파일에 이름·토큰 미보존,
  loopback 아닌 `--host`의 `--remote` 강제, 턴 단위 자동 저장, 슬라이스 1~4 우선)을 **제안대로 확정**했다.
- **슬라이스 1 구현**(같은 날, 기준 검증 1,539 통과 확인 뒤 착수 → 1,626 통과·Ruff·mypy): `server/access.py`(`AccessMode`·
  `Credentials`·상수 시간 토큰 비교), `GameSessionManager(access=, admin_key=)`의 `claim_seat`(먼저 온 claim이 이기고 토큰을
  발급, 보유자의 재claim은 이름 변경)·`release_seat`(보유자 또는 관리자)·`identify`·`require_admin`·`_authorize_seat_locked`,
  summary의 `access`·`players`와 remote에서의 진행 중 `game_seed: null`·checkpoint 경로 가림, 저장 메타데이터의
  `hide_unfinished_seed`, `app.py`의 쿠키(`dune_admin`, `dune_seat_<game>_<seat>`: HttpOnly·SameSite=Strict·게임 경로 한정)
  ↔ `Credentials`와 `POST /auth/admin`·`GET /games/{id}/me`·`POST .../seats/{seat}/claim|release`, CLI `--remote`·`--admin-key`
  (환경 변수 `DUNE_IMPERIUM_ADMIN_KEY`)와 loopback 아닌 bind의 거부, 실제 listen 주소로 찍는 관리자 링크. 판정 원칙 셋:
  (1) 자격 판정은 세션 계층 두 곳뿐이고 HTTP 계층은 쿠키를 옮기기만 한다, (2) 토큰은 쿠키 **이름이 아니라 값**으로 좌석과
  맞춘다, (3) 관리자 키는 어떤 좌석의 view도 열지 않는다(호스트도 플레이어). 자격 검사는 revision 검사보다 먼저라 자격 없는
  요청은 revision이 맞는지도 알 수 없다.
- 위임: 테스트 작성(`tests/server/test_access.py`·`test_remote_app.py`·`test_server_cli.py`)은 `card-implementer`에 명세를 주어
  맡기고 메인 세션이 검토했다. 검토에서 고친 것: 관리자 링크가 `::1`·`localhost` bind에서도 `127.0.0.1`을 찍던 결함(IPv6
  loopback에만 bind하면 열리지 않는다), 교차 좌석 거부를 "한 번이라도"가 아니라 매 반복 단언, 다른 좌석의 토큰을 이 좌석의
  쿠키 이름에 넣어 보내는 위조·다른 좌석 토큰으로의 release/claim·"어떤 summary에도 토큰이 없다" 테스트 추가.
- 함께 확인한 누출 경로: 누구나 받는 summary의 `decision.prompt`는 `rules/`·`core/`의 55곳 전부 고정 문자열이거나 좌석 번호·
  비용·VP·tier만 보간한다(설계 문서 2절에 불변식으로 기록).
- **슬라이스 2 구현**(같은 날, 사용자 지시 "슬라이스 2 진행"; 1,626 → 1,649 통과·Ruff·mypy): `GameSessionManager.snapshot(game_id, seat=None, *, log_after,
  log_epoch, credentials)`이 summary·`you`·view·actions(결정 소유자일 때만)·로그 꼬리를 한 lock 안의 한 상태에서 읽는다.
  로그 증분의 기준은 서버가 정한다: `epoch = "<seat>:<undo_count>:<finished>"`가 요청의 `log_epoch`와 같을 때만
  `from = log_after`, 아니면 `from = 0`으로 전체를 다시 보낸다(되돌리기는 앞선 항목의 `undone`을 소급해 바꾸고 종료는 가림을
  풀기 때문; 설계 초안의 "클라이언트가 `undo_count`를 보고 판단"은 요청 시점에 알 수 없어서 버렸다). `legal_actions`·`log`·
  `identify`는 helper(`_legal_actions_locked`·`_log_entries_json`·`_identify_locked`)를 공유한다. `GET /games/{id}/snapshot`,
  `GZipMiddleware(minimum_size=1024)`(이미지·`text/event-stream`은 Starlette 기본 제외 목록이 거른다).
- 클라이언트(`app.js`): `applySummary`의 순차 GET 3~4개를 `refresh(summary?)` → `loadSnapshot` → `adoptSnapshot`으로 교체.
  `refresh`는 single-flight(도는 중에 온 요청은 한 바퀴 더, 모든 호출자가 같은 promise를 받는다), 좌석은 `pickViewSeat`가
  summary에서 고르며 POST 응답 summary가 있으면 그것으로 한 번에, 없으면 보던 좌석으로 요청한 뒤 답이 다른 좌석을 가리킬
  때만 다시 요청한다. 로그는 `mergeLog`("`from`이 0이면 교체, 아니면 덧붙임"). 검토 모드 중의 갱신은 summary만 받고 검토
  화면을 덮지 않는다. `state.me`(snapshot의 `you`)는 슬라이스 4의 `mySeats()`가 쓸 자리다.
- 측정(`scripts/measure_server_payloads.py`가 두 방식을 같은 시점에 나란히 잰다; seed 20260917, 전 확장, 사람 3 + heuristic 1):
  갱신 한 번 4요청·120.7 KB(gzip 12.3 KB) → **1요청·14.6 KB(gzip 3.3 KB)**, 한 판 누적 64.8 MB(gzip 6.7 MB) → **8.3 MB
  (gzip 1.81 MB)**, snapshot 서버 시간 중앙값 2.7 ms·최대 47.5 ms. 테스트의 예산 단언(`tests/server/test_snapshot.py`, base 한 판):
  증분 누적 396 KB vs 전체 재전송 12.36 MB(3.2%), 증분 누적은 끝난 판 전체 로그(198 KB)의 2.0배.
- 브라우저 E2E(스크래치 Playwright, headless Chromium; 사람 2 + heuristic 2를 한 화면에서 293 단계로 끝까지): 행동 하나에
  POST 1 + snapshot 1(좌석이 바뀌는 턴 넘김 포함 — snapshot 295·POST 295), 매 단계 클라이언트 로그 개수 = 서버 `count`,
  되돌리기 뒤 epoch 변경과 전체 재수신, 종료 뒤 가림 없는 로그로 교체, 이어 붙인 로그 == 서버 전체 로그, JS·서버 오류 0.
- **E2E가 드러낸 기존 결함 1건을 따로 고침**: 검토 화면의 상태 응답은 속도가 크게 다르다(서버가 cursor까지 모든 step을
  재생하므로 마지막 step이 가장 느리다). 그래서 검토를 열자마자 ⏮를 누르면 늦게 도착한 첫 요청(마지막 step)이 화면을
  되돌려 놓았고, 검토를 닫은 뒤 도착한 응답은 live 화면을 검토 상태로 덮었다. `reviewGoto`가 요청 번호를 세어 가장 최근
  요청만 그린다(WAN에서 더 잘 터질 결함이라 지금 고쳤다; 재현·확인은 같은 스크래치 E2E).
- **슬라이스 3 구현**(같은 날, 사용자 지시 "슬라이스 3 진행"; 1,649 → 1,696 통과·Ruff·mypy, 초인종이 켜진 채 슬라이스 2의
  전체 게임 E2E도 그대로 snapshot 295·POST 295): 세션 계층은 asyncio를 모른다 —
  `GameSessionManager.add_change_listener(cb)`의 `cb(game_id, payload | None)`는 변경을 만든 스레드에서, **lock을 푼 뒤에**
  불린다(payload는 lock 안의 `_ring_locked`가 `event_seq`를 올리며 만든다; `threading.Lock`은 재진입이 안 되므로 listener가
  세션을 다시 읽으면 교착했을 것이다 — 테스트로 고정). 울리는 것: `apply_action`·`confirm_turn`·`undo`·`claim_seat`·
  `release_seat`, `online`이 실제로 바뀐 `connect`/`disconnect`, 그리고 `delete`(`None`). payload는 공개 필드 8개
  (`seq`·`revision`·`undo_count`·`log_count`·`decision_owner`·`confirmation`·`finished`·`players`)뿐이고 키 집합을 테스트가
  고정한다. presence는 좌석별 카운터가 아니라 **연결 ID → 그 요청이 내민 토큰들**의 대조다: release 즉시 offline, 재claim한
  사람이 접속한 뒤 옛 연결이 끊겨도 꺼지지 않는다.
- `server/events.py`의 `DoorbellHub`: 구독자마다 "최신 payload + `asyncio.Event`"(밀린 알림은 최신 하나로 합쳐진다), `seq`가
  큰 것만 덮어씀(lock 밖 publish의 순서 역전에 안전), 구독 등록을 `hello`를 읽기 **전에** 해서 그 사이의 변경을 잃지 않는다.
  `publish`·`close`는 어느 스레드(신호 처리기 포함)에서든 부를 수 있고 예외를 내지 않는다. SSE endpoint는 `async def`이고 lock을
  잡는 세션 호출은 `run_in_threadpool`로, 연결 등록·해제는 generator 안의 `try/finally` + 취소 shield로 짝을 맞춘다.
- **종료 처리**: 스트림은 스스로 끝나지 않고 uvicorn은 열린 응답을 기다리므로, 처음 구현(`timeout_graceful_shutdown=3`만)은
  탭이 열려 있으면 종료에 3.2초가 걸리고 "Cancel 1 running task(s)" ERROR를 남겼다(실측). lifespan shutdown은 uvicorn이 연결을
  기다린 뒤에 돌아서 쓸 수 없다. CLI가 `uvicorn.Server`를 상속해 `handle_exit`에서 `hub.close()`를 부른다 → 스트림 3개가 열린 채
  SIGINT에 0.32초·exit 0·깨끗한 로그. 이때는 `closed`를 보내지 않는다(재시작 뒤 게임이 돌아올 수 있다). `uvicorn.run`과
  달리 `Server.run()`을 직접 부르면 재발생한 `KeyboardInterrupt`를 직접 삼켜야 한다.
- 클라이언트: `openDoorbell`/`closeDoorbell`/`onDoorbell`. 알림의 다섯 필드 중 하나라도 summary와 다를 때만 `refresh()`
  (자기 행동의 알림은 요청 0개), `players`만 다르면 payload의 공개 `players`를 채택. 3번 연속 실패 또는 5초 안에 `hello`가
  없으면 스트림을 닫고 2초 폴링(summary에 같은 필드가 있어 같은 판정 함수), 404면 "게임이 삭제됨".
- 브라우저 E2E(컨텍스트 3개): 초인종으로 241 ms에 반영(서버에서 잰 POST → `change` 도착은 4 ms)·snapshot 요청 1개, 스트림을
  막은 컨텍스트는 2.2초 만에 폴링으로 전환해 1.6초에 반영, 게임 삭제는 `closed`와 폴링 404로 통지, JS 오류 0.
- 테스트 기반 메모: Starlette `TestClient`는 끝나지 않는 응답을 스트리밍하지 못한다(본문을 전부 버퍼링) → SSE의 HTTP 테스트는
  스레드에서 띄운 실제 uvicorn(`port=0`, `server.servers[0].sockets[0].getsockname()`) + `httpx2`(이 저장소의 dev 의존성은
  `httpx`가 아니라 `httpx2`다)로 한다. 종료 시간을 잴 때는 신호가 서버 프로세스에 바로 가도록
  `.venv/bin/dune-imperium-server`를 직접 띄웠다(회귀 테스트는 `sys.executable -m dune_imperium.cli.server`).
- **테스트 함정 하나**(서브에이전트가 이 실패에서 멈춰 메인 세션이 진단했다): `_read_block(response.iter_lines())`처럼 줄
  반복자를 임시값으로 넘기면, 함수가 돌아오며 그 generator가 닫힐 때 `httpx2`(httpcore)가 **연결을 닫는다**. 서버는 옳게
  presence를 내리므로 "hello 직후 `online`이 False"라는, 서버 결함처럼 보이는 실패가 난다(계측하니 connect −1.3 ms →
  disconnect +2 ms). 스트림을 열어 둔 채 검사하려면 `lines = response.iter_lines()`를 이름에 묶어 둔다.
- 위임: 테스트 세 파일은 `card-implementer`가 썼고(위 함정에서 멈춘 것을 중지시키고 이어받음), 메인 세션이 검토하며 인사말
  경합 2건·`hub.close()` 3건·실제 프로세스 종료 시간 테스트를 더했다.
- 주의: 브라우저 UI는 슬라이스 4 전까지 `--remote` 서버에서 동작하지 않는다(좌석 요청 403). 이 세션의 커밋은 push하지 않았다.

## 2026-09-17 학습 전 최종 점검 세션 요약 (master, 관측 v20, codec v104, 코드 변경 없음)

- 사용자 결정: 평소 구성은 **CHOAM+Bloodlines+Tech+Immortality+프로모 전부 켬**이고 학습 목표 룰셋도 그것이다. 이 구성의
  행동 codec은 32,963(base 4,371, CHOAM+BL+Tech 14,496)이며 증가분 17,586 중 15,656이 `agent_turn`이다 — Graft가 모든
  카드×공간 배치에 grafted 쌍둥이를 만들고 Immortality Imperium 25종·Tleilaxu 19종의 배치가 더해진다. 네트워크는 약 19M
  파라미터(출력층 512×33k = 17M).
- **하드웨어 실측**(이 WSL 노트북 i5-8250U 4C/8T, WSL 상한 7.9 GB, GPU 없음): base 32판·8 worker는 iteration당 약 30초
  (수집 17·갱신 11), CHOAM+BL+Tech 약 65초(33·30), 전 확장은 32판·6 worker가 메모리 초과(시스템 7,847/7,896 MiB, 세션
  재시작)라 **16판·2 worker·`--minibatch 1024`**만 가능하다(수집 33초·약 400 dec/s·13.5k step + 갱신 38초, python 4.5 GB,
  메인 2.4·worker 1.38 GB). 합성 배치 측정: minibatch는 갱신 **메모리**만 정하고 시간은 바꾸지 않는다(33k codec 11,500
  step에 1024: 31.8초·2.2 GB, 2048: 31.9초·2.9 GB, 기본 4096은 실측 4.1 GB). 처방: Mac mini 16 GB는 32판·8 worker·minibatch
  1024(약 11.5 GB, 64판 불가), 14700K PC는 RAM 32 GB면 16 worker. GPU는 갱신만 1~2초로 줄여 iteration 단축 상한이 약 2배이고
  PPO(여러 epoch)·큰 네트워크로 갈 때 의미가 생긴다. 체크포인트는 iteration당 78 MB, latest.pt 233 MB.
- **점검 1 학습 원활성(전 확장)**: `dune-imperium-train` 6 iteration + `--resume` 1 iteration + 대회 도구의 `checkpoint:`
  로드(4 match) 전부 정상 — 예외 0, truncated 0, rounds 10, entropy 1.20~1.24, ev 0.59~0.76, 평가(heuristic 3명, 4판)
  0% → 6.2%(학습 전 정책의 기대값). 스크래치 `precheck/train_chain.log`.
- **점검 2 heuristic(전 확장)**: codec의 action_id 231종 중 88종은 `_ACTION_SCORES`, 68종은 접두 가족(decline −2·pass −3·
  retreat −1·spy 3·trash/pay/recall 1), 10종 구매·3종 count·5종 전용 처리, **38종은 기본값 0.0**(그중 `discard_agent_card`·
  `discard_opponent_card`·`choose_intrigue_discard`는 trash tie-break가 좁힌다). 0.0 중 실제 결정에 닿는 것은 Engineered
  Miracle의 `command_acquire_row_card`(Row 아무 카드나 무료 획득인데 무작위로 고름), Intrigue의 `manipulate_imperium_row`
  (0.47/게임), Commander `choose_skill`이다. 동점 census(40판, `scripts/ab/census.py`): legal 집합 30,281 중 36.3%(275/
  게임)가 점수 동점이고, tie-break 뒤에도 RNG에 남는 가족은 공간 동점 18.6, `take_contract` 9.3, graft 변형 6.95+3.9,
  `choose_graft_partner` 4.35, Commander skill 3.3, research space 3.1, Spy post 합 약 8, Intrigue option 2.4/게임.
  학습을 막지 않는 기준선 강도 항목으로 남긴다(0번 (a)).
- **점검 3 버그(전 확장+프로모, HEAD `6e2bc66`)**: `dune-imperium-sweep` heuristic 300판·random 300판·draft 100판
  (`--soundness-interval 25`, replay 검증 포함) 실패 0; self-play 112판 예외 0; rollout 1 + heuristic 3 8 match 실패·불법 0
  (rollout 62.5%). 커버리지 0회 항목은 base 룰셋의 contract, heuristic이 고르지 않는 decline/withdraw, 300판 표본에서 드문
  leader·카드 경로뿐이다.
- **점검 4 미확정 동작**: open-questions 60건 전부 `DECIDED`(56)/`RESOLVED`(4), `OPEN` 0; 디자이너 판정 13건 전부 반영;
  전 확장의 Imperium 109·Tleilaxu 19·Intrigue 68 entry 모두 play data 완결, Leader 18종 Signet 전부 구현, 미구현 보드
  공간 0. audit 문서의 미완 경계는 "학습 재개"뿐이다.
- 09-16 마무리 작업의 룰셋 범위를 되짚었다: tie-break A/B 7축에 Immortality는 있었고 프로모는 없었으며, rollout 값 함수
  A/B는 base·CHOAM+BL+Tech만(전 확장+프로모는 채택 뒤 60판 재측정 60.0%), 소크·기준선은 전 확장+프로모 포함, 파이프라인
  smoke는 base만이었다. 이 세션에서 전 확장 파이프라인을 처음으로 끝까지 확인했다.
- **판정: 전 확장 구성으로 학습 시작 가능.** 첫 실행은 Mac mini에서 `--minibatch 1024`, 25 iteration마다 heuristic 평가
  (루프 안 평가는 단일 프로세스라 rollout 상대는 학습 뒤 대회 도구로), 정체하면 PPO(수집 log-prob + clip + epochs 3~4)로
  `--resume`해 잇는다. 문서 커밋 1건(테스트 수 1,539 정정) 외 코드 변경 없음.

## 2026-09-16 심야 M10 학습 전 마무리 세션 요약 (master, 관측 v20, codec v104)

- 사용자 지시: "M10 학습 전에 진행해야 할 것들 마무리". 원격과 일치(양방향 0), 기준 검증 pytest 1,519·Ruff·mypy
  통과를 먼저 확인했다. 인수인계 0번의 학습 밖 후보 (a)~(c)를 순서대로 닫고 M10 파이프라인 자체를 smoke했다.
- **M10 파이프라인 smoke**: `dune-imperium-train --iterations 3 --games-per-iteration 32 --workers 8 --eval-every 3`이
  v20·v104에서 정상(iteration당 약 20,500 learner step, 3 iteration 뒤 heuristic 3명 상대 3.1% — 학습 전 정책의 기대값),
  `--opponent rollout --eval-opponent rollout`(StateAgent 수집·평가 경로)도 정상(rollout 상대라 86 dec/s). 스크래치
  `m10smoke/`. 코드 변경 없음.
- **heuristic 표 밖 항 — 동점 census**([evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md) 14절(a)):
  17절(c)의 교훈대로 순위가 갈리는 결정의 빈도부터 쟀다. base+CHOAM 80판에서 legal 집합 50,475개 중 36.1%(게임당
  228개)가 최고점 동점으로 RNG에 맡겨진다. 빈도 있는 균일-무작위 가족: 같은 비용 카드 구매 13.9/게임, Spy post 약 13,
  Influence 진영 선택 약 9, trash·discard 카드 약 5, `take_contract` 5.2.
- **1라운드**(14절(b), 스크래치 `HeuristicAgent` 서브클래스 7종, 현행 `heuristic` 상대 축별 2:2 500 seed): 진영 target·
  cheapest trash·Reveal 가치 구매는 7축 중 6축 양수(+1 ~ +6%p), 공간 동점·Spy post는 잡음, Plot 선출은 손해(CTI −5.8),
  **배치를 참는 규칙은 전 축 −8 ~ −13%p**. 1라운드 셀 하나가 **엔진 결함**을 적발했다(아래).
- **2라운드**(14절(c), 49셀, 대조군 **고정 변형 `heuristic_uniform_ties`**): 셋을 합친 `combo3`가 전 축·두 seed 블록
  **+5.1 ~ +9.1%p**, buy를 뺀 `combo2ft` +2.4 ~ +6.8, 단독은 +0.4 ~ +4.9. **채택**(커밋 `e6fa084`): `TieBreaks`(faction·
  trash·buy) + `narrow_family_tie`가 점수가 고정한 동점 집합 **안에서만** 좁힌다(2026-09-10 교훈); 저장소 port는
  스크래치 combo3와, `heuristic_uniform_ties`는 옛 heuristic과 결정까지 같다. 테스트 +7.
- **엔진 결함 수정**(커밋 `a1c3f94`): CHOAM+Bloodlines+Tech seed 262, Reveal 중 낸 Twisted Ambitious의 troop 3 상실이
  Conflict를 비우자 `retreat_units`는 running `combat_strength`를 0으로 맞췄지만 Reveal frame의 `strength` 집계는 4로
  남았고, 이어진 Combat 아이콘 배치의 "첫 unit" delta가 전투력을 음수로 만들었다(`ValueError`). Intrigue의 LoseTroops·
  RetreatTroops가 두 Reveal 핸들러처럼 frame 집계를 running 값에 맞춘다(`_follow_reveal_strength`, `[Main p. 12]`
  player-turns.md 231). 회귀 테스트 1건.
- **A/B 대조군 오염 사고**([lessons.md](lessons.md) 2026-09-16 둘째 항목): 셀이 도는 중에 tie-break를 저장소로 옮겨
  적자 spawn worker가 새 트리를 import해 2라운드가 변형 vs 변형이 됐다. 대조군을 고정 변형으로 바꿔 다시 쟀고(약 20분
  손실), 셀 스크립트가 HEAD와 `git status`를 로그 첫 줄에 적게 했다. 같은 스크립트에서 zsh가 따옴표 없는 `$2`를
  단어 분리하지 않아 `--start-seed 500`이 한 인자로 넘어간 실수도 있었다(둘째 블록 재실행).
- **처리량 — M10 수집 경로**([evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md) 8절): 학습이
  지나가는 `SelfPlayRunner` 경로를 처음 프로파일했다. 관측 인코더가 31%(+ `np.asarray` 8.7%)로 최대 항. (a) 인코더를
  바이트 동일하게 다시 썼다(커밋 `cf67b96`, card-implementer 위임: 미리 잡은 offset에 직접 쓰기, identity 조회
  `functools.cache`, 우주 dict 색인, 구성원 순회) — 같은 실행 안 번갈아 5회: 수집 벽시계 base **−16.1%**(3,380 → 4,028
  dec/s), 전 확장 **−17.9%**; golden digest 테스트(random 좌석 5룰셋, `acdb36c`→`cf67b96`)가 출력 불변을 고정한다.
  (b) `apply_agent_action`의 guard가 모든 hand 카드 대신 낸 카드의 배치만 재열거(`legal_agent_actions_for_card`, 커밋
  `78da90c`; 114개 handler guard 합계 7.2% 중 78%가 이것) + `usurp_trash_is_queued`의 Immortality 게이트: 대회 경로
  벽시계 base −3.8%, 전 확장 −3.1%, step 동일.
- **검증 소크**(tie-break heuristic으로, `dune-imperium-sweep --policy heuristic --rotate-leaders --soundness-interval 25
  --workers 8`): base+CHOAM·Bloodlines·Bloodlines+Tech·Immortality·전 확장+프로모 각 2,000판, 전 확장+프로모 draft
  1,000판, random 전 확장+프로모 1,000판 = **12,000판 실패 0**(카드 보존·교착·관측 누출·replay·합법 행동 적용·codec
  왕복). census의 0회 항목은 지난 소크와 같은 종류(룰셋에 없는 내용물, heuristic이 고르지 않는 `decline_*`)뿐이다.
  스크래치 `verify/soak/`.
- **기준선 12셀 재측정**(같은 명령, HEAD `f7b73a9`; [evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md)
  요약 표의 마지막 열): heuristic vs random 3 base 800판 97.8 → **98.4%**, CHOAM 98.4 → **98.6%**, Bloodlines 96, Tech 95,
  Immortality 99, 전 확장 97; 미러 셋 25.0%; rollout vs tie-break heuristic 3은 채택 전 값 함수로 base 44.0 → 42.0%, 전 확장
  55.0 → 60.0%, 15절의 값 함수 채택 뒤 다시 재 base **54.0%**, 전 확장 **60.0%**. README의 수치를 갱신했다.
- **리뷰 workflow**(finder 4 lens × 적대 검증 2): 확정 1건 — Intrigue 진영 선택의 loss/gain 판별이 "6칸 track이 제시되면
  loss"로 잘못 가정(엔진은 gain에도 가득 찬 track을 제시하고 fizzle시킨다). 제시된 track 수로 판별하도록 고쳤다(커밋
  `f7b73a9`, 테스트 +1). 기각 2건(handler guard의 오류 메시지 순서, 인코더의 KeyError/ValueError 종류)과 docstring 정정
  1건(`_follow_reveal_strength`의 RetreatTroops 가지는 오늘 콘텐츠에서 no-op — Fedaykin Maneuver는 Signet).
- **rollout `player_value` 가중치 A/B**([evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md) 15절):
  스크래치 `RolloutAgent` 서브클래스 9종, rollout 1 + tie-break heuristic 3, base 200판 셀. 1라운드에서 보인 두 손잡이
  (카드를 인쇄 비용 합으로 세기 +9.5, 상대 평균 기준 +8.5%p)가 둘째 seed 블록에서 +0.5·+2.5로 줄었다(두 블록 합
  +5%p 안팎, 표준오차 2.5). Conflict troop 가중치는 horizon(다음 round 시작)에서 항상 0이라 결정에 닿지 않는다.
  3라운드(결함 수정 뒤 평소 구성 재측정 + 셋째 블록, 15절(c)): **상대 평균 기준 + 인쇄 가치 덱을 채택**(커밋) — 네 셀 모두
  양수(+8.5·+2.0·+7.5, CHOAM+Bloodlines+Tech +7.0), base 600판 합 +6.0%p. 이전 함수는 `rollout_count_max`로 고정.
- **엔진 결함 2건째 수정**(커밋 `133a01b`): rollout의 CHOAM+Bloodlines+Tech 셀에서 200판 중 16판 `IllegalActionError`.
  Coercive Negotiation trigger frame이 bank 상위 3장을 제시하는데 `determinize`가 bank 전체를 섞어 sampled world의
  제시가 달라졌다. 공개된 장수(`revealed_contract_count`)만큼 제자리에 둔다(7635aac와 같은 종류; 테스트 1건).
- 문서: rl-environment.md에 v20 항목(4,323→4,327)과 인코더 재작성 메모, README·핸드오프의 4,323/v19 표기 정정,
  implementation-plan 8절.

## 2026-09-16 공간 표 강등 마감·수준 0.6 채택·OQ-060 확정 세션 요약 (master, 관측 v20, codec v104)

- 사용자 지시: "다음 작업 쭉 나열" → 목록 제시 후 핸드오프 0번을 진행. 원격이 6커밋 앞서 있어
  fast-forward했고(2026-09-11 원격 작업), 기준 검증 pytest 1,506·Ruff·mypy 통과를 먼저 확인했다.
- **OQ-060 `DECIDED`**(사용자 판정): 고를 track이 전부 6이면 선택형 Influence 보상은 소멸한다.
  대체 보상은 규칙에 없다. 문서만 바뀌고 구현(2026-09-11 소멸 convention)은 그대로다.
- **커밋 트리 확인 셀 6개**(18절(g)): Tech·Bloodlines·Immortality는 스크래치 기록과 소수점까지
  일치, base+CHOAM만 4,000판 중 4승 차(원인은 스크래치 출력이 사라져 특정 불가, 결론 불변),
  Immortality는 OQ-060 뒤 2,000판 완주. 새 셀: CHOAM Tech +9.6%p, 전 확장+프로모 +8.4%p.
- **강등 수준 맞대결**(18절(h)): 0.45·0.5·0.6·0.75를 0.3 상대로 축별로 쟀다(스크래치
  `sitecustomize` 주입, sanity는 결정 수까지 동일). 0.6이 base +4.5·CHOAM +8.2·Immortality
  +5.6/+7.4%p, Bloodlines·CHOAM Tech 동률, Tech CHOAM 없음 −4.9/−5.9%p(두 칸 표보다는 +3.4/+2.2%p
  위). 0.45는 0.3과 구분 안 됨, 0.75는 전 축 손해. 배치 probe(`probe_mix.py`): 0.6은 Influence
  10.4를 지키며 Landsraad 방문을 Imperial Basin·Arrakeen으로 바꿔 Conflict 승 1.74→2.54, base+CHOAM
  VP +0.33; Tech에서는 Landsraad 방문이 tile 구매라 −0.11.
- **채택(사용자 판정, 평소 구성이 CHOAM+Tech)**: 0.6을 전 룰셋에. CHOAM+Tech 축 추가 셀은 동률~+2.8%p.
  `UPRISING_SPACE_BONUSES` 세 칸 0.6, 0.3 표는 `SPACE_BONUSES_DEMOTED_TO_FLOOR`·registry
  `heuristic_floor_table`로 고정, 테스트 −1 +1(+신규 1). 커밋 트리 확인(base·CHOAM)은 스크래치 0.6
  셀과 결정 수·승수까지 동일.
- 이 Mac(Apple M4 10코어)은 1,000 match 셀이 30초라 A/B 셀 40개 + probe를 한 세션에 끝냈다.
  스크래치는 세션 scratchpad `space-table-closeout/`(정의는 18절에 있어 재작성 가능).
- **기준선 재측정**: 09-10 문서 1~12절(두 칸 표의 heuristic으로 잰 값)을 같은 명령으로 다시 재
  [evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md)를 현행 기준선으로 뒀다 —
  heuristic vs random 3: base 89.2 → **94.9%**(800판), CHOAM 84.4 → **95.5%**; rollout vs heuristic 3:
  43.0 → **51.0%**(전 확장 41.7 → 46.7%). README의 수치·링크를 갱신했다.
- **상위 항목 소거**(18절(i)): lessons 09-11 규칙대로 0.6 표의 상위 네 칸을 하나씩 0.3으로 내려 쟀다.
  **Imperial Basin만 바닥으로 내리면 전 축에서 +4.6 ~ +9.1%p**, Arrakeen을 내리면 전 축 −6.8 ~ −12.4%p,
  Espionage·Deliver Supplies는 무차이. 후속 셀(나머지 축·둘째 블록·Secrets/Arrakeen 변형)은 18절(j).
- **처리량**(throughput 7절, 커밋 `9b435e2`): `RulesEngine.apply`가 runner가 방금 만든 legal 집합을 받아
  재열거 대신 membership 검사만 하게 했다(가드 유지). 단일 프로세스 heuristic 미러 벽시계 **−13.6%**(base·CHOAM),
  `legal_actions` 호출/결정 2.00 → 1.00, step 수 동일. 불변식 테스트 3건.
- **소거 후속 → 표 분리 채택**(18절(j)·(k), 커밋 `f2a5006`): Imperial Basin 0.3 하나로 전 축 +3.5 ~ +11.7%p,
  Secrets 수준은 무관, Arrakeen은 올릴수록 좋다가 Sardaukar(1.0) 위에서 고원(1.0·1.2·1.5·2.0 동률; 1.2와 1.5는
  결정까지 동일). **채택: Imperial Basin 0.3 · Secrets 0.6 · Arrakeen 1.2**(영구 업그레이드 바로 아래의 엄격한
  순서). 0.6 표 상대 base +17.2/+16.8, CHOAM +16.2/+12.7, Bloodlines +15.8, Immortality +10.6/+7.8, Tech CHOAM 없음
  +15.9/+14.8, Tech CHOAM +14.5, CHOAM+Tech+Imm +11.5%p. 0.6 표는 `heuristic_median_table`로 고정. 커밋 트리
  확인 4축 결정 수까지 동일. probe: Arrakeen 배치 좌석당 4.91, Conflict 승 1.66 → 2.61, Influence 유지.
- **새 표의 소거**(18절(k)): Arrakeen 내리면 −10%p(확인), Espionage 무차이, Hagga Basin 경계(+2.7),
  **Deliver Supplies(0.7 → 0.3) 전 축 +4.2 ~ +9.0%p** — 다음 손잡이(아래 "다음 구현 순서" 0번).
- **엔진 결함 1건 수정**(커밋 `8738b34`): 전 확장 기준선 seed 42의 교착 — 점유된 칸의 graft 배치가 "Ghola가
  partner"(Bond 아이콘)와 "Infiltrator가 partner"(점유) 두 약속을 한 partner에 요구해 partner 선택에 합법
  행동이 없었다. 배치 provider가 Ghola 약속 없이 닿는 카드에만 제시하도록 고쳤다([rules/immortality.md](rules/immortality.md)
  구현 목록, 18절(k) 결함 항목). 규칙 판정 아님(`[Immortality p. 10]` 두 장만). 기준선 12셀은 수정 뒤 다시 쟀다.
- **Deliver Supplies 채택**(18절(l), 커밋 `1912fbb`): 0.3·0.4 모두 base·CHOAM·Immortality·Tech CHOAM 없음·
  CHOAM+Tech+Imm 두 블록 +2.6 ~ +9.6%p, Bloodlines·CHOAM Tech 동률. **0.4 채택**(Gather Support 묶음). split 표는
  `heuristic_split_table`로 고정, **고정 표 넷은 Deliver Supplies를 명시**(고정 표가 현행 표의 나머지를 물려받는
  함정). 커밋 트리 확인 4축 결정 수까지 동일. probe: 배치가 Sietch Tabr·Fremkit으로 옮겨 가고 Influence 합은
  10.4 → 9.7, Conflict 승·control·VP 상승. 소거는 또 다음 손잡이를 냈다: **Espionage(0.8 → 0.3) 전 축 +2.9 ~
  +5.5%p**, Fremkit 내리면 −14 ~ −20%p(핵심 칸), Sietch Tabr·Arrakeen도 손해.
- **엔진 결함 2건째 수정**(커밋 `7635aac`): rollout 좌석 base seed 1 — Long Live the Fighters 선택 frame이 열린 채
  `determinize`가 관측자 덱을 다 섞어 실제 합법 선택이 sampled world에서 불법(`IllegalActionError`). 관측자가 본
  상단 카드 수(Long Live 3, peek 1)만큼 제자리에 둔다. rollout 셀 `b04`·`b12`만 다시 쟀다.
- **Espionage 채택**(18절(m), 커밋 `aaa9788`): 0.3·0.6 모두 전 축·두 블록 +2.7 ~ +8.8%p, **0.6 채택**(0.6 묶음).
  Deliver Supplies 표는 `heuristic_supplies_table`로 고정(고정 표 다섯 모두 Espionage 0.8 명시). 커밋 트리 확인 4축
  결정 수까지 동일. probe: 배치가 Fremkit·Sietch Tabr로, Conflict 승 1.92 → 2.34, VP 7.32 → 7.67. **새 표의 소거는
  손잡이를 내지 않았다**(상위 네 칸 모두 손해 또는 잡음) — 좌표 하강은 여기서 멈춘다.
- 최종 기준선([evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md), 하루의 표 다섯 열): heuristic vs
  random 3 base 800판 89.2 → **97.8%**, CHOAM 84.4 → **98.4%**; rollout vs heuristic 3은 43.0 → **28.0%**(전 확장
  41.7 → 31.7%) — rollout의 후보 pruning이 같은 `score_action`을 쓰므로 표가 강해질수록 우위가 준다(열린 항목).
- **rollout 정비**(저녁, [evaluation/baseline-2026-09-16.md](evaluation/baseline-2026-09-16.md) 13절, 커밋 `c88f111`·`c71bbcd`·`43a0022`):
  heuristic 3명 상대 28%까지 내려온 원인은 **playout 노이즈**였다 — 같은 예산(12 playout/결정)에서 후보 3·세계 4는
  54%, 공통 난수(CRN)만 얹어도 50%, 세계 8은 66%(4배 비용)인데 후보 12는 34%, horizon 2는 17%. 200판 결승에서
  **세계 4 · 후보 3 · CRN**(55.0%, 약 80 ms/decision)을 기본값으로 채택했고 이전 기본값은 `rollout_untuned`, 두 배
  예산의 세계 8 · 후보 3 · CRN(60%, 약 150 ms)은 `rollout_strong`으로 등록해 플레이 서버 좌석 종류에도 넣었다.
  기준선 4절·12절 재측정: base **44.0%**(28.0), 전 확장 **55.0%**(31.7).
- **상향 소거**(18절(n), 32셀): 오늘 내린 세 칸을 되돌리면 −2.5 ~ −10.8%p, 낮은 칸을 올리면 −2 ~ −18%p 또는 잡음.
  표는 양방향 국소 최적이며 표 작업은 닫았다.
- **검증 소크 재실행**(밤, 재정비한 heuristic으로): `dune-imperium-sweep --policy heuristic --rotate-leaders
  --soundness-interval 25 --workers 8`로 base+CHOAM·Bloodlines·Bloodlines+Tech·Immortality·전 확장+프로모 각
  2,000판, 전 확장+프로모 draft 1,000판, random 전 확장+프로모 1,000판 = **12,000판 실패 0**(카드 보존·교착·관측
  누출·replay·합법 행동 적용·codec 왕복 전부). census의 0회 항목은 룰셋에 없는 내용물(base의 Tuek's Sietch·
  Bloodlines Conflict 2장, CHOAM 없는 contract)과 heuristic이 고르지 않는 `decline_*` 류뿐이다. 오늘 A/B 실행이
  잡은 결함 2건 뒤로 새 결함은 없었다. 로그·census JSON은 이 Mac의 세션 scratchpad `space-table-closeout/soak/`.
- **문서 정리**: `implementation-plan.md` 8절, README의 기준일과 heuristic 표 문구, 이 문서의 "현재 위치", 그리고
  `lessons.md`에 고정 표가 현행 표를 물려받는 함정을 적었다.
- 검증: pytest **1,519**, Ruff, mypy 통과. README 테스트 수 1,519.

## 2026-09-11 보드 공간 표 강등·OQ-060 세션 요약 (master, 관측 v20, codec v104, 표 변경·마감 미완)

- 사용자 지시: "다음 작업 이어가보자" → 16절(g)의 (1) Tech 전용 공간 표 재설계. 결과는 Tech 전용
  표가 아니라 **재정비 표 자체의 상위 세 칸(Imperial Basin·Secrets·Arrakeen, 배치의 56%)이
  틀렸다**는 발견이다. 세 칸을 바닥(0.3)으로 내린 표가 Tech에서 두 칸 표를 +6.2/+3.6%p(두 블록),
  CHOAM Tech에서 +12.2%p(0.6 수준), 재정비 표를 base+CHOAM +9.8%p·Bloodlines +15.2%p·Immortality
  +7.4%p로 이긴다. Solari 재가격·계층화·rubric 재도출은 전부 졌다. 수치·정의·기제 probe는 18절.
- 커밋 2건. `94545a0` **OQ-060**: 강등 표가 세 진영을 6까지 올린 채 Propaganda를 이겨 옛 tripwire
  `NotImplementedError`로 죽은 결함(Immortality seed 102) — 고를 진영이 없는 Influence 선택
  frame을 엔진이 자동 소멸(`combat_reward_influence_unavailable`)시키는 convention, 공식 문서 침묵,
  **사용자 확정 대기(`OPEN`)**. 두 번째 커밋: `UPRISING_SPACE_BONUSES` 세 칸 0.3, Tech 특례
  `space_bonuses_for` 삭제(표 하나를 전 룰셋에), 재정비 표는 `SPACE_BONUSES_BEFORE_DEMOTION`으로
  `heuristic_uprising_table`에 고정, 테스트 정리(−3 +2), 18절, lessons("이전 표보다 낫다"를 "표가
  맞다"로 읽음).
- **미완(사용자 요청으로 세션 종료).** 커밋 트리 확인 셀 6개와 강등 수준(0.3 vs 0.6) 맞대결
  3셀을 띄웠다가 첫 셀 도중 중단했다 — "다음 구현 순서" 0번에 명령과 판단 기준을 적었다.
  스크래치 스크립트·로그·JSON은 이 머신의 `/tmp/dune-heuristic-space-table-2026-09-11/`(재부팅
  시 사라짐; 정의는 18절에 있어 재작성 가능).
- Python 3.14 대회 worker는 forkserver라 부모 프로세스의 registry 패치가 전달되지 않는다 —
  스크래치 변형은 `PYTHONPATH`의 `sitecustomize.py`에서 등록해야 한다(17절·18절).
- 서버 undo 테스트 10건(`tests/server/test_undo.py`·`test_app.py`의 `test_undo_and_log_over_http`)은
  AI 좌석의 진행 경로에 고정된 revision 번호를 쓰므로 표가 바뀌면 깨진다. AI 좌석을 registry의
  `heuristic_uprising_table`(2026-09-10 표 고정)로 바꿔 앞으로의 heuristic 재정비와 분리했다 —
  undo 기제는 어느 표를 쓰든 같다. 다음에 표를 또 바꿔도 이 테스트들은 손대지 않아도 된다.
- 검증: pytest **1,506**(OQ-060 +3, heuristic −3 +2), Ruff, mypy 통과. README 테스트 수 1,506.

## 2026-09-11 Tech tile 가치표 A/B 세션 요약 (master, 관측 v20, codec v104, 표 무변경)

- 사용자 지시: "다음 작업 이어가보자". 16절(g)의 후보 (2) **`_TECH_BONUSES` 재정비**를 끝까지 재고
  **기각**했다. 커밋 1건(master 직접). 코드 변경은 `score_action`·`HeuristicAgent`의 `tech_bonuses`
  A/B 슬롯(`space_bonuses`와 같은 꼴, 기본은 현행 `_TECH_BONUSES`)과 회귀 테스트 1건, 표 위의 주석이다.
  수치·정의·명령은 [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) **17절**.
- **방법.** 변형 다섯 개(`effects` 18장 효과 표, `net`/`effects_plus` 비용 ∓0.15, `pricey` 비용만,
  `cheap` 싼 tile 우선)를 스크래치 드라이버로 `heuristic_tech_<변형>`에 등록해 `heuristic_untuned`와
  2:2 미러·`--rotate-leaders`·Bloodlines+Tech(CHOAM 없음)·seed 500개 블록(쪽당 2,000판)으로 맞붙였다.
  Python 3.14 대회 worker는 forkserver라 부모의 registry 패치가 전달되지 않는다 — `PYTHONPATH`의
  `sitecustomize.py`에서 등록해 해결했고, 현행 표를 같은 경로로 주입한 sanity 셀이 대조군과 결정
  수까지 동일함을 확인했다. 셀 8개 + probe 600 match, 합계 약 8,800 match, 실패·불법 행동 0.
- **결과.** `effects` −0.4/+2.2%p, `net` +0.8/+0.8%p, `effects_plus` −1.8%p, `pricey` −1.2%p, `cheap`
  **−4.8%p**(VP margin −0.28). 공간 표의 −13.6 ~ +16.0%p와 자릿수가 다르다. probe: 현행 표의 tile별
  구매는 좌석당 0.09~0.18로 거의 균일 — 순위가 갈리는 결정이 드물다. `cheap`은 spice를 더 남기고(8.03
  대 6.70) 상대에게 비싼 tile(Panopticon·Navigation Chamber·SHC)을 넘겨 진다.
- 검증: pytest **1,504**(신규 1)·Ruff·mypy 통과. README의 테스트 수를 1,504로 정정했다.

## 2026-09-11 Tech Module 공간 표 A/B 세션 요약 (master, 관측 v20, codec v104, 배선 무변경)

- 사용자 지시: "다음 진행할 작업 이어가보자". 핸드오프의 남은 항목인 **Tech Module의 공간 표**
  — 재정비 표 위에 Landsraad 다섯 칸의 Acquire Tech 값을 매겨 A/B — 를 끝까지 재고 **기각**했다.
  커밋 1건(master 직접), 코드 변경은 `heuristic_agent.py`의 표 선택 주석과 `registry.py`의
  `heuristic_uprising_table` docstring뿐이다. 수치·정의·명령은 전부
  [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) **16절**.
- **방법.** 임시 변형 `HeuristicAgent(tech_space_value=TechSpaceValue(δ, 게이트))`를 스크래치
  registry에 등록하고(저장소에 남기지 않음; 정의는 16절 머리말), `heuristic_untuned`(Tech에서
  현행 `heuristic`과 동일한 두 칸 표)와 2:2 미러·`--rotate-leaders`·Bloodlines+Tech(CHOAM
  없음)·seed 0~499(좌석당 2,000판)로 맞붙였다. 대조군 `heuristic_uprising_table`을 같은
  블록에 포함했다(−13.6%p). 셀 22개(각 1,000 match = 좌석당 2,000판)와 probe 약 1,600 match, 합계 약 2만 4천 match, 실패·불법 행동 0.
- **결과.** 정적 δ 0.15/0.30/0.50 → −17.0/−26.8/−32.1%p(13절 overlay와 같은 모양). 살 수 있을
  때만 δ 0.15~1.0 → −16.0~−14.0%p(0.75부터 결정 수까지 동일 = "살 수 있으면 무조건 Landsraad"인데도
  대조군 자리). 값 있는 tile(`_TECH_BONUSES` ≥ 0.5)일 때만 δ 0.5 → **−7.3%p**(δ 격자 0.15/0.3/1.0은
  −13.4/−12.0/−8.1), 그러나 seed 500~999에서는 **−9.9%p로 같은 블록의 대조군과 동일**, CHOAM에서는
  −1.1%p(대조군 −6.2%p)·−4.7%p(대조군 −6.9%p) — 네 블록 합산 대조군보다 +3.4%p(차 기준) 낫고 두 칸
  표에는 전부 진다. 여유 spice 게이트 −12.3%p.
- **진단(맞대결 probe 300 match).** 게이트 변형은 tile을 두 칸 표보다 **더** 산다(4.07 대
  2.27)면서도 진다 — Landsraad(비Combat) 배치가 2.3 → 5.6으로 늘며 Combat 배치 11.2 → 9.2(tile 한 장에 약
  0.6개), 배치 병력 19.5 → 16.0이지만 변형의 Conflict 승 2.04 → 2.12(상대 2.39 → 2.30)·VP
  6.77 → 6.81은 그대로다 — 산 tile이 득점이 안 된다. Tech 없는 Bloodlines에서 두 칸 표는 끝
  spice 11.7을 놀리고 대등한데(24.5% 대 25.5%, 300 match), Tech가 켜지면 그 spice가 tile 2.9장이 되어
  Conflict 승 2.19 → 2.39, VP 6.90 → 7.40으로 이긴다(31.2% 대 18.8%). 두 표의 30판 미러 VP는
  Tech 유무로 거의 같다(6.92→7.00, 7.17→7.16; 0.5 VP를 가릴 해상도는 아니다). 기제는 미확정.
- **대조군 정정.** 15절(a)의 "Bloodlines+Tech −6.6%p"는 **CHOAM on**의 값이다(그 세션의 seed 110
  회귀 테스트가 `rulesets=(True,)`로 그 대회를 재구성하고, 이 tree의 CHOAM on 대조군
  −6.2/−6.9%p가 재현한다). CHOAM 없는 Bloodlines+Tech는 −13.6/−9.9%p로 거의 두 배 나쁘다(16절(a)).
- 검증: 코드 되돌린 뒤 pytest 1,503·Ruff·mypy 통과(주석·docstring 변경만). README의 테스트 수
  1,487을 1,503으로 정정했다.

## 2026-09-10 심야 확장 공간 순위·엔진 결함 3건 세션 요약 (master, 관측 v19→**v20**, codec v104)

- 사용자 지시: "확장 공간 순위 진행". 앞 세션이 남긴 마지막 heuristic 항목이다. 커밋 3건
  모두 master 직접 커밋이다.
- **전제가 뒤집혔다.** 13절의 "확장이면 −5.6%p"는 **전 확장을 한 덩어리로** 잰 값이고, 그
  뒤 엔진 수정 3건과 14절이 들어간 tree에서 **확장을 하나씩 분리해** 다시 재면 방향이
  갈린다(각 4,000판): Immortality만 **+16.0%p**·**+17.0%p**, Bloodlines만 **+3.8%p**,
  Bloodlines+Immortality **+9.2%p**, 그러나 Bloodlines+**Tech** **−6.6%p**·**−4.8%p**,
  전 확장 −0.2%p·−0.8%p. 즉 −5.6%p는 **반대 방향 두 효과가 상쇄된 값**이었고, 표를 싫어하는
  확장은 **Tech Module 하나**뿐이다.
- **이유는 Ixian Embassy에 인쇄돼 있다.** Tech tile에는 board space가 없고 "Landsraad
  board space에 Agent를 보낸 turn에" 산다 `[Bloodlines p. 7]`. 재정비 표는 싼 Landsraad
  칸을 바닥에 두므로(Assembly Hall 0.50, Gather Support 0.40) agent가 Landsraad를 끊고
  tile을 못 산다 — 좌석당 **Tech tile 2.48 → 1.16**, Commander 0.62 → 0.35. Combat 배치
  비중은 오히려 46.6% → **53.1%**로 **올라가므로** 13절 overlay(−34%p)의 실패 이유와는
  다르다. Immortality가 board에 하는 변경은 **Research Station 한 칸뿐**이고
  (`[Immortality pp. 5, 16]`), 두 확장 모두 새 Agent 목적지를 추가하지 않는다.
- **`aa46132` 배선 변경.** `space_bonuses_for`는 이제 **Tech Module일 때만** 두 칸 표를
  쓰고 나머지는 전부 재정비 표를 쓴다. 확인 A/B(`heuristic` vs `heuristic_untuned`):
  Tech-free 세 룰셋에서 +16.0/+3.8/+9.2%p, base+CHOAM +9.2%p(13절의 +4.9/+5.1%p보다 큰 것은
  14절이 같은 방향으로 겹쳤기 때문), Tech가 켜진 두 룰셋은 **결정 수까지 정확한 미러**로
  회귀 0. 표 전체는 15절.
- **A/B가 찾은 엔진 결함 3건.**
  - **`2fa94d1` Ghola의 빌린 Agent box를 apply가 읽지 않음.** provider는
    `active_agent_card`를 쓰는데 payment·discard의 apply는 인쇄된 카드를 읽어, Ecological
    Testing Station을 복사한 Ghola가 water 2 대신 **spice 4 + VP 1**을 내고 카드는 못
    뽑았다(모자라면 `player resources must not be negative`로 사망, seed 70620). 전수
    스캔으로 다른 사례 없음을 확인했다.
  - **`86c634b` Infiltrate가 회수한 Spy로 판정하던 Graft partner.** 2026-09-10의
    `placed_reaches`는 놓인 카드만 덮었고, 아이콘이 없어 항상 partner에 의존하는 **Usurp**는
    후보가 전멸해 교착했다(Immortality seed 70254·70804). 배치가 Infiltrate post를 기록하고
    partner 판정이 그 Spy를 되돌려 센다.
  - **[OQ-059](rules/open-questions.md#oq-059--시장에-face-up-contract가-남았지만-아무것도-가져갈-수-없을-때의-contract-아이콘)
    가져갈 수 없는 시장의 contract 아이콘** — Bloodlines의 Immediate만 남고 trash할
    Intrigue가 없으면 가져갈 token이 없는데 시장은 비지 않아 2 Solari 전환도 안 걸린다
    (Bloodlines+Tech seed 110). 공식 원문(Main p. 16, Bloodlines p. 2, FAQ)과 디자이너
    정리본 전문을 확인했고 이 경우는 **어디에도 없다**. 사용자 판정(2026-09-10):
    **2 Solari로 전환하지 않고 OQ-057(1)대로 turn 종료까지 보류한 뒤 불발**. 같은 세션에서
    **구현했다**: 좌석 scalar `held_contract_icons`가 보류분을 들고,
    `_advance_automatic`이 가져갈 token이 없을 때 frame을 닫아 아이콘을 옮기며(turn이
    막히지 않는다), 같은 turn 안에서 가져갈 수 있게 되면 의무이므로 자동으로 다시 열고,
    turn이 닫힐 때 보상 없이 불발시킨다. 좌석 scalar가 하나 늘어 **관측 v20**(51→52),
    action id는 그대로라 codec은 v104 유지.
- registry에 **`heuristic_uprising_table`**(재정비 표를 모든 룰셋에 고정)을 남겨 두었다 —
  남은 Tech 표 A/B의 반대편이다.
- 검증: pytest **1,503**(신규 8), Ruff, mypy 통과. OQ-059 구현 뒤 소크: Bloodlines+Tech
  300판(`--soundness-interval 10 --privacy-interval 3`)과 전 확장 200판 실패 0, 그 결함을
  찾았던 Bloodlines+Tech 1,000 seed 대회는 2,000 match 실패 0으로 돌아왔고 그 룰셋에서는
  여전히 정확한 미러다. 그 앞 소크: 표가 바뀐 룰셋 3종 각 150판
  (`--soundness-interval 10`, Immortality는 `--privacy-interval 3`도) 실패 0. A/B는
  이 세션 전체에서 약 3만 match를 돌았고 실패는 위 결함 3건이 전부다.

## 2026-09-10 심야 spent-card 동점 세션 요약 (master, 관측 v19, codec v104)

- 사용자 지시: "핸드오프 보고 다음 구현 이어가기". M10은 사용자 방침으로 최후순위이므로 앞
  세션이 남긴 후속 (b) **`agent_turn` 인자 동점 — 같은 공간에 어느 카드를 낼지**를 집었다.
  커밋 2건 모두 master 직접 커밋이다.
- **출발 수치 정정.** 앞 세션이 "남은 동점 995개"로 적은 값은 **재정비 표를 전 확장에 강제
  적용한** probe에서 나왔고, 같은 세션이 그 뒤 `space_bonuses_for`로 재정비 표를 비확장
  룰셋에만 쓰도록 한정했으므로 **995를 낸 배선은 저장소에 없다**. 강제 적용하면 995가 정확히
  재현되므로 계산이 틀린 것이 아니라 **측정한 배선과 shipping 배선이 다르다**. committed
  tree를 다시 재면 base+CHOAM **852**(그중 578이 공간 같고 카드만 다름), 전 확장
  **1,652**(그중 **1,531이 공간이 다름** — 확장 표가 두 칸뿐이라 21칸이 동점). 세부는
  [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 14절 (a).
- **규칙 근거.** "Agent turn에는 낸 card의 Agent box만 처리하고 그 card의 Reveal box는
  무시한다" `[Main p. 8]` `[Main p. 9]`, "앞선 Agent turn에 낸 card의 Reveal box 효과는 얻지
  않는다" `[Main p. 12]`([rules/player-turns.md](rules/player-turns.md) 60·161행). 가중치는
  13절 환산표에서 유도했다 — Persuasion 1 = 0.20(Assembly Hall 0.5 − Intrigue 0.30
  `[Board Guide p. 1]`), sword 1 = 0.09(recruit troop 0.18의 절반; `[Main p. 12]`의
  Conflict troop strength 2 대 reveal sword 1).
- **두 번 기각하고 세 번째로 채택**(`69bf880`). (1) `score_action`에서 빼는 항: base+CHOAM
  −2.2%p·−6.0%p, 전 확장 −8.6%p. 가장 싼 카드 Dagger가 Landsraad 아이콘 하나뿐이라 Dagger
  배치가 203→426으로 두 배가 되고 Assembly Hall(143→236)·Gather Support(26→88)가 흡수해
  **Combat 배치 비중 50.2% → 46.5%** — 13절 overlay와 같은 실패다. (2) 같은 항을 보드 표
  최소 간격(0.05) 안으로 축소: base+CHOAM은 회복(−0.2%p·+0.2%p)했으나 전 확장은 **결정
  수까지 동일한** −8.6%p를 재현했다. 확장 룰셋은 21칸이 동점이라 **어떤 배율의 카드 항이든
  공간을 고르는 항**이 되기 때문이며, 배율로 고칠 수 있는 문제가 아니었다. (3) **채택**:
  `score_action`은 그대로 두고 `choose_action`이 seeded 추첨으로 공간을 확정한 **뒤** 그
  공간에 도달하는 동점 배치들 사이에서만 가장 싼 카드를 고른다
  (`cheapest_card_for_the_same_space`). 교체는 `card_id`만 바꾸고 cost option·discount·
  graft·infiltrate는 추첨이 정한 대로 유지한다(그러지 않으면 공짜 할인을 버리고 Spy를 헛
  소비한다 — 40판 전 확장 probe에서 분리되는 교체 6,198건 중 할인 97건·cost option 777건).
- **측정**(committed tree, 모두 `--rotate-leaders`, 9,600 match 실패 0·불법 행동 0):
  base+CHOAM seed 0~ **+1.4%p**(각 12,000판), seed 50000~ **+0.4%p**(각 12,000판), 전 확장
  + 프로모 **+3.6%p**(각 6,000판). 미러 null은 정확히 25.0%/2.50. 구조 확인: **Combat 배치
  비중 50.2% → 50.3%**, `ms/decision` 양쪽 0.006~0.007로 처리량 비용 없음. 이 동점이 실제로
  결정하는 양은 base+CHOAM 결정의 3.9%, 전 확장 4.2%다. 표 전체는 14절.
- registry에 **`heuristic_flat_cards`**(카드 가치 없음)를 추가해 이 A/B도 committed tree에서
  재현된다 — 13절이 `heuristic_untuned`를 추가한 것과 같은 이유다. `rollout`은 playout과
  fallback에 `HeuristicAgent`를 쓰므로 이 변경을 함께 받으며, 4·12절의 rollout 수치는 다시
  재지 않았다.
- 교훈은 [lessons.md](lessons.md)에 남겼다: 한 인자 계열 안의 동점 판단을 `score_action`에
  더하면 계열·공간을 가로질러 적용돼 국소적으로 남지 않는다.
- 검증: pytest **1,495**(신규 8), Ruff, mypy 통과. 소크: 전 확장 heuristic 120판
  `--soundness-interval 10 --privacy-interval 3` 실패 0, base+CHOAM heuristic 300판
  `--soundness-interval 25` 실패 0. A/B 자체가 9,600 match(약 38,400 agent-game)를 실패 0·
  불법 행동 0으로 돌았다.

## 2026-09-10 심야 처리량 회귀 귀인 세션 요약 (master, 관측 v19, codec v104)

- 사용자 지시: "핸드오프에 따라 다음 구현 이어가자" → 인수인계가 남긴 ④ **처리량 35% 회귀
  귀인**. 커밋 3건 모두 master 직접 커밋이다. 관측·codec 무변동(게임 동작 무변경).
- **결론: 회귀는 실재하고 step당 엔진 CPU가 약 1.6배가 된 것이다.** 이 저장소(WSL2, 8코어)에서
  같은 명령을 세 트리에 번갈아 재어 8 worker **1.60배**(−37%), 단일 프로세스 **1.63배**로 재현했다.
  단일 프로세스에서 **더 크게** 나온다는 점이 worker 기동·import·pool 계열 설명을 전부 배제한다.
  결정론적 지표(step당 Python 호출 수)로도 **1,218 → 1,849(1.51배)**이고 소요 시간 비율과 맞는다.
  원인은 한 곳이 아니라 **확장 4종을 담게 된 엔진 전반**이다. 전체 수치는
  [evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md).
- **`ab48e0c` 에이전트에게 harness 비용을 청구하던 Protocol 검사.** `StateAgent`가
  `@runtime_checkable` Protocol이라 `isinstance()` 한 번이 `inspect.getattr_static`으로 멤버를
  훑는다(약 5us). 그것을 **결정마다** 묻는 자리가 세 곳(runner 분기, tournament `_MeteredAgent`의
  분기 — **계측 구간 안**, 학습 수집 batch policy)이었다. 리포트가 지문을 남기고 있었다:
  heuristic 0.005 → 0.010, random 0.001 → 0.006으로 **둘 다 정확히 +0.005 ms**인데
  `random_agent.py`는 구간 내 변경이 0줄이다 — 에이전트가 느려진 게 아니라 모든 좌석에 같은
  상수가 더해진 것이다. 좌석은 게임 중 바뀌지 않으므로 좌석당 한 번만 묻게 하고, mypy의 Protocol
  narrowing을 잃지 않도록 bool이 아니라 `StateAgent | None`으로 좁혀 둔다. 회귀 테스트는 시간이
  아니라 불변식이다(세는 대역 클래스로 "한 판에 좌석당 정확히 2회"; 수정 전 같은 판은 **1,174회**).
- **`88c0ef7` base 게임에서 확장 존을 매 복사마다 훑던 검증.** `GameState.__post_init__`과
  `PlayerState.__post_init__`은 모든 복사마다 돌고 엔진은 step당 상태를 여러 번 복사한다
  (`dataclasses._replace` step당 6.05회). 그 안의 중복 검사 4건은 확장이 소유한 존
  (Contract·Skill/Commander·Tech tile·Bene Tleilax)에 대한 것인데, base 게임은 그 존이 게임 내내
  비어 있는데도 매 복사마다 tuple과 set을 만들어 그것을 증명하고 있었다. 이제 모듈 플래그가 각
  검사를 가른다 — 켜져 있으면 이전과 똑같이 훑고, 꺼져 있으면 합법적인 내용물이 "없음"뿐이므로
  빈지만 보고 기존의 "모듈이 필요하다" 오류가 담당한다. 빈 컬렉션은 이 검사들을 구조적으로 전부
  만족하므로 **거부되던 상태가 새로 허용되지 않는다**. 새 테스트는 각 게이트의 양쪽을
  고정하며, **수정 전 엔진에서도 통과**한다(그래서 서술이 아니라 가드다).
- **`615e7ed` 룰셋 플래그로 답할 수 있는데 매번 다시 세우던 provider 6개.** legal action provider
  6개(`legal_sardaukar_commander_actions`·`legal_commander_deployments`·
  `legal_commander_withdrawals`·`legal_graft_switch_actions`·`legal_tech_reveal_actions`·
  `legal_skill_trash_actions`)는 모듈이 꺼져 있으면 **항상 `()`만** 돌려줄 수 있는데 — 그렇게 만들
  콘텐츠를 상태 불변식이 금지한다 — frame context나 deployment context를 다시 세우거나 decision
  stack을 훑어서 그것을 증명하고 있었다. 엔진이 결정마다 legal 집합을 두 번 만들므로 base 게임은
  step당 대략 두 번씩 치렀다. 이제 `state.config`로 먼저 답하며, 게이트는 호출부가 아니라
  **provider 안**에 두어 적용 직전 재열거로 검증하는 호출자까지 덮는다. graft는 pending 표시가
  frame context에 있지만 `agent_turn.py`가 모든 Agent effect에 `graft_pending_effect`를 `False`로
  심고 그것을 참으로 만드는 곳이 Immortality 모듈뿐이라 플래그가 맞는 게이트다. 테스트는 게이트
  자체를 고정한다(모듈이 꺼지면 뒤의 헬퍼에 닿지 않을 것, 켜지면 닿을 것).
- **개별 기여와 크기 정정.** 각각 자체 실행에서 트리를 번갈아 재어 (a) **−1.2%**, (b) **−3.1%**,
  (c) **−2.4%**이고, 끝에서 끝까지 실측한 합계가 8 worker **−6.7%**·단일 프로세스 **−7.1%**로
  세 값의 합과 일치한다. `ms/decision`은 0.069 → 0.034(**−51%**). 즉 **(a)는 `ms/decision` 회귀의
  사실상 전부지만 벽시계로는 소수 항**이고 실행을 빠르게 한 쪽은 (b)·(c)다. 커밋 `ab48e0c`의
  메시지는 자기 항목을 "0.9s 중 0.62s"로 적었는데 **과대평가**다 — 0.62초는 CPU 시간이고 8 worker
  병렬이라 벽시계로는 그 1/8이다. 커밋은 다시 쓰지 않고 정정을 evaluation 문서 3(a)와
  [lessons.md](lessons.md)에 남겼다.
- **절대값은 기계 부하로 실행마다 20%까지 움직인다**(같은 트리가 16.50s와 13.40s로 둘 다 나왔다).
  트리 간 비교는 **한 실행 안에서 번갈아 잰 것만** 쓴다.
- **앞 세션의 용의자는 소수 항이었다.** `6782c89`(OQ-057 dry-run + 8칸 `_UNAVAILABLE_CACHE`)는
  100판에서 호출 40,250회 중 **28,634회 캐시 적중**(71%), 누적 시간 **2.7%**다. OQ-057의 의미는
  확정된 디자이너 판정이라 성능을 이유로 건드리지 않는다. 교훈은 "읽어서 고른 용의자를 재보지
  않고 인수인계에 원인으로 적지 않는다"로 [lessons.md](lessons.md)에 남겼다.
- **부수 발견.** Python 3.14는 Linux 기본 start method를 `forkserver`로 바꿨다(gh-84559) — 이
  저장소의 3.14.7도 그렇고, macOS(`spawn`)와 마찬가지로 worker마다 import를 다시 치른다.
- 검증: pytest **1,487**(신규 13: tournament 불변식 1 + 모듈 게이트 4 + tech_flipped 1 + 룰셋
  게이트 7), Ruff, mypy 통과. 소크: base+CHOAM random 200판(게이트 닫힘)과 전 확장 heuristic
  120판(게이트 열림)을 `--soundness-interval 10 --privacy-interval 5`로, 230,678 step 실패 0.
- **남은 후속**: (a) 아직 남은 성능 후보는 evaluation 문서 5절에 크기 순으로 있다. 다음 후보는
  provider가 각자 `current_agent_effect_context`로 frame context를 다시 만드는 부분
  (`agent_effect_frame.py:95`가 이미 만들어 들고 있다)과, `observe_state`가 쓰지도 않는 `random`
  좌석에까지 관측을 만드는 것이다. `core/engine.py:112`의 재열거(결정당 legal 집합을 두 번
  만든다)는 이 구간 이전부터 있던 안전 가드라 성능이 아니라 **설계 판정**이 필요하다. 상태
  dataclass의 폭(31→48 / 42→78)을 줄이려면 확장 상태를 별도 레코드로 빼는 설계 변경이 필요하다.
  (b) 확장 룰셋의 공간 순위, (c) `agent_turn` 인자 동점 995개, (d) M10 학습 재개는 그대로 남았다.

## 2026-09-10 밤 보드 공간 재정비·잠재 결함 3건 세션 요약 (master, 관측 v19, codec v103→**v104**)

- 사용자 지시: 앞 세션이 제시한 네 항목 중 ③ heuristic 재정비를 "보드 공간 23칸 차등화로
  진행". 커밋 4건 모두 master 직접 커밋이다.
- **조사가 범위를 바꿨다.** 원래 후보는 "`score_action`이 0.0으로 떨어뜨리는 38개 action
  id"였는데, 38개를 전수 조사하고 실측해 보니 **거의 아무것도 결정하지 않는다**: 전 확장
  20판 15,296개 legal-action 집합에서 0.0점 행동이 `finish_agent_turn`과 같은 집합에 나타난
  경우가 **0건**이고(`pending_board_effect`가 turn 종료 제시를 막는다), 38개 중 상위 동점
  쌍에 등장하는 것도 0건이며, 대부분은 자기 frame의 유일한 id다. 실제 최대 동점은
  **`agent_turn` 인자 1,652회(전체 결정의 11%)**였고 원인은 보드 23칸 중 2칸만 점수가 있어
  21칸이 기본 4.0으로 동점이라는 것이었다. 앞 세션이 "38개가 동전 던지기"라고 적은 것은
  과장이었고, 실측으로 정정했다.
- **`30f377b` 보드 공간 23칸 차등화.** 값은 [rules/board-spaces.md](rules/board-spaces.md)의
  인쇄 수익(`[Board Guide pp. 1-2]`)을 단일 환산표로 가격 책정하고 인쇄 비용을 차감한 것이며
  (Influence 0.45, sandworm 0.45, Maker Hooks·control 0.35, Intrigue 0.30, Spy 0.25,
  water 0.22, card 0.20, troop 0.18, spice 0.12, Solari 0.07), 영구 업그레이드 2칸은 기존
  값을 유지해 모든 1회성 수익 위에 남긴다. `agent_turn` 인자 동점 1,652→995(−40%).
  **base+CHOAM에서 +4.9%p·+5.1%p·+5.0%p로 독립 블록 3개 재현**, 그러나 **전 확장에서는
  −5.6%p**이고 확장 공간 overlay 시도는 **−34%p**로 더 나빴다 — 올린 칸이 대부분 비Combat
  이어서 Combat 배치 비중이 46.1%→39.7%로 떨어지고 평균 VP가 8.20→5.73이 됐다. 그래서
  `space_bonuses_for(observation)`가 관측에서 룰셋을 읽어 **확장이 켜지면 재정비 이전 표**를
  돌려주도록 범위를 한정했다(전 확장 실행이 정확한 미러 25.0%/25.0%로 회귀 0 확인). 탐지는
  후반에 0이 될 수 있는 값을 쓰지 않는다(`len(tech_stack_sizes) == 3`, 좌석 `research_space`).
  A/B 재현성을 위해 registry에 **`heuristic_untuned`**(재정비 이전 표 고정)를 추가했다 —
  2026-09-09 재정비가 스크래치 모듈을 등록해야 했던 이유가 변이체 슬롯 부재였다. 수치 전부는
  [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md) 13절.
- **재정비가 드러낸 잠재 엔진 결함 3건.** 셋 다 이전부터 있었고 재정비된 진행 패턴이
  도달했을 뿐이다(세 트리 대조로 확인: 재정비 없으면 재현되지 않고, 수정은 재정비와 무관하게
  독립적으로 검증됨).
  - **`8034532` codec v104 — 12유닛 초과 retreat.** 엔진이
    `retreat_intrigue_troops(commanders=1, count=13)`을 제시하는데 카탈로그는 12까지였다.
    Commander는 12개 병력과 별개 구성물이고 Conflict에서 troop으로 취급되므로
    (`[Bloodlines p. 4]`) 유닛이 12+7=19까지 가고, Tactical Option의 `RetreatTroops(1, None)`
    이 그 전부를 제시한다. Bloodlines 카탈로그마다 +28 템플릿. 회귀 테스트는 한 예시가 아니라
    `_unit_count_arguments`가 12병력+7Commander에서 낼 수 있는 **모든 조합**의 왕복을 검사한다.
  - **`32ee469` graft partner 전멸 교착.** Mohiam의 Clandestine이 "Each card you play has the
    Spy icon"(`[Gaius Helen Mohiam card]`)을 주므로 아이콘 없는 starter가 연결된 Spy로 Bene
    Gesserit 공간에 정당하게 들어가는데, Infiltrate의 비용이 **그 Spy를 회수한다**
    (`[Main p. 11]`). partner provider는 인쇄 아이콘이 비었다는 것만 보고 "partner가 공간
    접근을 제공해야 한다"고 추론해 모든 후보를 걸러냈고, 그 turn에 합법 행동이 하나도 남지
    않았다. partner 시점의 재계산은 원리적으로 불가능하므로(접근 근거가 이미 소비됨) 배치가
    `placed_reaches`를 frame context에 기록하고 provider가 그것을 읽는다. frame context는
    관측에 인코딩되지 않고 action id도 그대로라 **버전 변동 없음**.
  - **`6c36bdd` Conflict에 없는 유닛까지 제시한 withdrawal.** provider가 turn의 배치
    카운터와 미확정 배치만 상한으로 썼고 **실제 Conflict에 있는 유닛 수**는 보지 않았다.
    배치한 troop이 그 뒤 Conflict를 떠날 수 있고 "when you lose a troop, return it to your
    supply (not your garrison)"(`[Dune: Imperium Rules 2020-10-26 p. 16]`)이므로 카운터가
    실제를 앞지른다. OQ-030의 확정 원칙("해결하는 시점에 있는 만큼만, 소급 없음")을 적용해
    `troops_conflict`·`commanders_conflict` 상한을 더했다. 진행 경로는 불변(같은 786 step) —
    적용 불가능한 제시만 사라진다. sweep의 soundness 표본이 적발했다(정책이 그 count를 고르지
    않아 평시에는 드러나지 않았다).
- **`3d85b7a` undo 테스트를 로그 불변식으로.** scripted revision 번호에 묶여 있어 heuristic
  AI 좌석의 선호가 바뀌면 undo와 무관한 이유로 깨졌다. 이제 "window는 항상 좌석 0의 연속된,
  아무것도 공개하지 않은 step의 말꼬리 길이"를 60 step 동안 매번 독립 계산과 대조하며, window
  가 2 이상 자란 적과 공개 step이 닫은 적을 함께 요구해 공허하게 통과하지 않게 했다.
- 검증: pytest **1,474**(신규 9: 공간 6 + codec 1 + graft 1 + withdrawal 1), Ruff, mypy 통과.
  소크: 전 확장 `--soundness-interval 10` heuristic 240판 실패 0, 그 앞 단계의 전 확장 100판
  `--privacy-interval 3`·heuristic 80판 `--privacy-interval 2` 실패 0.
- **남은 후속**: (a) **확장 룰셋의 공간 순위** — 비어 있는 채로 남았다. 인쇄 수익 위에 보너스를
  더하는 방식은 측정으로 기각됐고(−34%p), Combat/비Combat 균형을 함께 재설계해야 한다. 시작점은
  Combat 배치 비중 46.1%를 유지하면서 Research Station·Landsraad를 올리는 것이다.
  (b) `agent_turn` 인자 동점 **995개가 남았다** — 같은 공간에 도달하는 **어느 카드를 낼지**
  (`card_id`)와 cost option·discount 변형이고, 공간 점수로는 닿지 않는다. 카드 가치 평가가
  필요하다. (c) 앞 세션이 적은 ④ 처리량 35% 회귀(59.25→38.71 games/s, 용의자 `6782c89`의
  dry-run과 8칸 `_UNAVAILABLE_CACHE`; 격리 worktree 대조 스크립트는 준비돼 있다)와 (d) M10
  학습 재개는 그대로 남았다.

## 2026-09-10 저녁 검증 가드·진입 문서 정정 세션 요약 (master, 관측 v19, codec v103)

- 사용자 지시: "지금 작업해야할 단계가 뭐야" → 후보를 조사해 순서를 제시하고 사용자가 네 항목
  전부를 골랐다(① 문서 정정 + ② 검증 장치, ③ heuristic 재정비, ④ 처리량 회귀, ⑤ M10).
  이 세션은 ①·②를 마쳤다.
- **조사 방법과 그 결과.** 계획·감사 문서 7곳을 훑어 미완 항목 88건을 뽑고 전부 코드로
  대조했다: **42건만 실제로 열려 있고 46건은 stale한 문서 줄**이었다(2026-09-10 오전이 5곳을
  고친 것과 같은 계열). 이어서 완결성 비평으로 문서 집합 **밖**의 공백을 찾았고, 그쪽이 더
  컸다 — 아래 두 항목과 "남은 후속"의 미등록 항목들이 거기서 나왔다.
- **`7867f7c` 검증 가드의 맹점 4건.** `check_observation_privacy`의 scramble이
  `conflict_deck`·`skill_stack`·`tleilaxu_deck`·`twisted_deck_stock`을 건드리지 않았다(같은
  파일의 `_hidden_instances`는 Conflict deck을 숨은 존으로 취급하고 `hidden_card_owners`는
  Twisted stock을 nobody로 매핑하고 있었다). 넷 다 움직이게 했고, Conflict deck은 **tier
  band별**로 섞는다: tier는 뒷면에 인쇄되고 덱 구성이 공개이므로(`[Main p. 4]`) 각 깊이의
  tier는 고정하고 그 tier의 카드만 섞으며, 상자로 간 I·II는 "앞면을 보지 않고" 돌아가므로
  (`[Main p. 4]`) 숨은 카드로서 같은 pool을 공유한다. 첫 구현은 덱 전체를 뒤집어 공개 정보인
  tier 배열까지 바꾸고 있었고(적대적 리뷰가 적발), 그대로 두면 UI가 다음 Conflict tier를
  표시하는 순간 privacy 검사가 거짓 양성을 내 올바른 엔진 동작을 제거하는 방향으로 고쳐질
  구조였다. `CardCensus`에는 Tech tile 18장(CHOAM 없으면 17, `[Bloodlines p. 6]`)·Skill
  14장(7종 2장씩, `[Bloodlines p. 3]`)·Commander 7개의 보존을 더했다 — `GameState`는 세
  구성물 모두 **유일성만** 검사하고 총량은 보지 않아, 모든 존에서 사라진 tile이 통과했다.
  troop·specimen·spy는 건드리지 않았다: `PlayerState`가 이미 specimen까지 포함해 보존한다
  (`[Immortality p. 8]`). coverage census에는 `tech_acquired`·`tleilaxu_acquired`·
  `skills_taken` 차원을 더했다(옵션 off면 빈 우주). 소크: 전 확장 100판 `--privacy-interval 3`,
  heuristic 80판 `--privacy-interval 2`, 실패 0. 60판 커버리지 실행에서 Tech 18장·Skill 7종
  전부가 밟혔고 한 번도 획득되지 않은 Tleilaxu 카드 6~10장이 보고됐다.
- **진입 문서 정정.** `rl-environment.md`가 학습 환경의 규범 문서인데 머리말이 "상태: 확정"인
  채로 관측 v9·4,235 int·`OBSERVATION_VERSION` 15·codec v79·frame 24종이라 네 숫자가 모두
  틀려 있었다(실측 v19·4,323·v103·43종). v16~v19 이력을 채우고, identity 우주 구성(개인 카드
  66→**138**, Intrigue 39→**90**, Contract 20→**28**, battle card 21→**23**)과 "두 catalog"
  표현도 고쳤다. README는 1,452→**1,465**·3,166-int(v10)→4,323-int(v19)로 고치고 관측 v4
  체크포인트 승률(56/89/91%)과 rollout 48%에 현행 기준선 대비 표시를 달았다. 핸드오프
  기준선 절은 2026-09-09에 멈춰 있어(`OBSERVATION_VERSION = 18`, pytest 1,443) HEAD 기준으로
  맞췄다. `designer-rulings-audit.md`의 "반영 여부는 사용자 결정" 머리말도 같은 문서 85행이
  기록한 13건 전부 반영 상태로 고쳤다.
- 검증: pytest **1,465**(신규 7), Ruff, mypy 통과.
- **남은 후속(사용자가 고른 순서)**: (③) heuristic 점수표 재정비 — `ACTION_HANDLERS` 231개 중
  명시 점수는 106개뿐이고 **38개는 `score_action` 마지막 `return 0.0`으로 떨어져 서로 전부
  동점이며 `finish_agent_turn`(0.5)에 진다**(`choose_skill`·`manipulate_imperium_row`·
  `detonate_shield_wall`·`play_navigation`·`take_tuek_sietch_card`·`deploy_leader_agent` 등).
  A/B는 `score_action(action, *, omit=...)`에 그 38개를 넘기는 `heuristic_untuned` registry
  엔트리로 커밋된 트리에서 재현하게 한다(2026-09-09에는 스크래치 모듈이 필요했다 —
  `registry.py`에 변이체 슬롯이 없는 것이 유일한 장애였다). (④) 처리량 35% 회귀 —
  동일 명령·동일 머신(Apple M4 8 worker)·거의 같은 step 수인데 59.25 → 38.71 games/s다
  (`evaluation/baseline-2026-09-06.md:18` vs `baseline-2026-09-10.md:34`). 용의자는 `6782c89`
  (OQ-057)가 도입한 `agent_effects.py`의 dry-run과 8칸 `_UNAVAILABLE_CACHE`이고, 그 커밋과
  부모 `96148cc`를 격리 worktree에서 같은 seed로 대조하면 바로 판정된다. 저장소에 프로파일러
  사용처가 없다. (⑤) M10 학습 재개.
- **이 세션이 새로 발견한 미등록 항목**(조사·비평 산물, 아직 아무 문서에도 없던 것):
  브라우저 UI 자동 테스트가 0줄인데 `implementation-plan.md:269`는 M11 완료 근거를 headless
  Chromium E2E로 적는다(`app.js` 3,309줄, 저장소에 playwright 참조 없음); CI 없음
  (`.github` 없음)·LICENSE 없음·`scripts/`와 레거시 `dune/`이 ruff/mypy 범위 밖(실측 ruff
  1+7, mypy 4 에러, `dune/`은 importer 0); 전 확장 소크 규모가 기본판의 1/20 이하(20,000판
  vs 1,300판, 템플릿 4,371 vs 32,935); `coverage.py`의 `_report("contracts", ...)`가
  `choam_module`을 보지 않아 base 룰셋에서 28건을 전부 미커버로 보고한다(새 차원들은 옵션을
  보게 만들어 이 문제를 피했다).

## 2026-09-10 문서 정정·학습 룰셋 배선·Long Live frame·기준선 재측정 세션 요약 (master, 관측 v18→**v19**, codec v103)

- 사용자 지시: "먼저 하는게 좋은건 어떤거야? 급한 일정 없음" → 순서를 정하고 3순위까지 진행. 커밋 3건 모두 master 직접 커밋이고 각각 push했다.
- **`e0e364b` 감사 문서 5곳 정정.** 이 세션의 탐색 스카우트 5개 중 4개가 stale한 "Deferred boundaries" 줄에 속아 미구현 작업으로 보고했다. 전부 코드로 대조해 고쳤다: intrigue.md의 Reveal-turn draw 경계(2026-09-01 OQ-015(c)로 해소, `reveal_late_arrivals`/`grant_late_reveal_effects`), card-draw.md의 "base Imperium 3종 미전사"(identity 109종 전부 `play_data_complete=True`), personal-cards.md의 "미구현 Leader의 Signet Ring 보류"(카탈로그 18종 전부 `IMPLEMENTED_ABILITY_LEADER_IDS`), spies.md의 "General Recall Spy icons"(`AgentIcon`에 recall 계열이 없음), designer-rulings-audit.md 머리말의 "반영 미결정"(같은 문서 85행이 13건 전부 반영으로 기록).
- **`8b039dc` 학습 루프의 확장 룰셋 지원.** `TrainConfig`에 `promo_cards`/`bloodlines`/`tech_module`/`immortality`, `cli/train.py`에 같은 이름의 플래그, `train()`이 전체 `RulesetConfig`를 만들고 `_evaluate()`가 `tournament_specs`에 넘긴다. `collect.py`의 `_ChunkJob`은 bool 4개를 더 붙이는 대신 `RulesetConfig`를 통째로 싣는다(worker로 넘어가는 구간에서 플래그를 빠뜨릴 수 없게). 체크포인트와 `torch_policy`는 이미 식별자를 저장·파싱하고 있어 무변경. 실제 `--bloodlines --tech-module --immortality` 실행이 `uprising-4p-base+bloodlines+tech+immortality` 체크포인트를 쓰고, 그 체크포인트가 `checkpoint:` 에이전트로 같은 룰셋 대회에 참가함을 확인했다(8매치, 실패 0, 불법 행동 0). 테스트 4건 추가.
- **`6c89a56` Long Live the Fighters의 전용 frame.** 두 단계 pick을 Agent effect frame의 flag로 열어 두고 `agent_effect_frame.py`와 `graft.py`가 그 문자열을 직접 읽어 배타성을 지키고 있었다 — flag가 frame을 흉내내던 것이다. `FrameKind.LONG_LIVE_FIGHTERS`로 옮기니 pick이 열린 동안 Agent effect frame이 맨 위가 아니라서 배타성이 구조적으로 나오고 특례 2곳이 사라졌다. action id·인자·이벤트는 그대로라 codec v103 유지, 관측은 frame kind를 인코딩하므로 **v19**. 소크: `--soundness-interval 25`로 base+CHOAM 400판(267,059 step), 전 확장 heuristic 160판(129,677 step) 실패 0. 커버리지 census 300판에서 새 frame이 34회(base 16·CHOAM 18) 실제로 밟혔다.
- **Corrinth City는 제외.** `refactoring-plan.md`가 두 카드를 한 항목으로 묶었지만 배타성 기준으로 정반대다 — Corrinth City의 부분 선택은 일부러 중단 가능하고(자유 순서 효과가 저장된 첫 카드를 소비하면 선택 없음에서 재시작, `[Main pp. 9, 20]`; 자유 순서는 OQ-011·OQ-027 확정), 배타적 frame으로 바꾸면 규칙 동작이 바뀐다. 판정이 먼저 필요하다. 근거는 `refactoring-plan.md`에 적었다.
- **기준선 리포트 재측정** — [evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md)(12절, 3,060매치, 실패 0, 불법 행동 0). 2026-09-06 행렬을 그대로 다시 돌리고(1~4절) 대표본 확인(5~6절)과 확장 커버리지(7~12절)를 더했다. 옛 리포트에는 대체 표시를 달았고 README의 수치도 갱신했다. **주요 변화**: heuristic의 random 상대 승률이 95.0%(100판) → **89.2%**(800판)로 내려갔고 rollout의 heuristic 상대 승률도 48.0% → **43.0%**다. 좌석·선공 편향은 그대로 없다(미러 전부 25.0%/2.50). 확장은 heuristic에게 불리하지 않다(Bloodlines 86.0%·+Tech 92.0%·Immortality 86.0%·전 확장 85.0% vs base 84.0%, 모두 같은 100판 조건). heuristic 점수표가 OQ-058 이후 넓어진 행동 공간에 맞춰 정비된 적이 없으므로 **heuristic 가중치 재정비**를 다음 후보로 적었다.
- **`e91e98d` determinize의 Secret Project 결함(이 재측정이 적발).** rollout이 Tech Module 테이블에 앉은 첫 실행에서 60판 중 5판이 `a Tech tile cannot occupy two zones`로 죽었다(전부 Kota Odax of Ix 로스터). determinize가 각 Tech stack의 바닥 tile까지 섞었는데 Kota Odax의 소유자는 그걸 이미 봤다("Game Start: 각 stack의 맨 아래 Tech tile을 본다" `[Bloodlines p. 6]`) — 표본 세계가 열린 Secret Project frame의 candidates와 어긋나 `apply_secret_project`의 제거가 실패하고 tile이 두 존에 남았다. 관측자가 그 frame을 소유할 때 바닥을 제자리에 두고 중간만 섞도록 고쳤다. 지식은 frame 밖으로 안 이어진다(OQ-041). 엔진·규칙 무변경. 회귀 테스트는 수정 없이는 실패함을 확인했다.
- 검증: pytest **1458**(신규 6: 학습 4 + frame 구조 1 + determinize 1), Ruff, mypy 통과.
- 남은 후속: (a) **M10 학습 재개** — 관측 v19·codec v103이라 `checkpoints/2026-09-06/`의 champion 3개(관측 v4)는 여전히 전부 거부되고 새로 시작해야 한다. 배선은 이 세션으로 끝나 실행만 남았다. (b) ~~기준선 리포트 재측정~~ — 2026-09-10에 완료했다([evaluation/baseline-2026-09-10.md](evaluation/baseline-2026-09-10.md), 12절 3,060매치 실패 0). (c) `refactoring-plan.md`의 남은 코드 리뷰 후속(Reserve copy ID 카운터, Covert Operation 부모 frame 재개는 버전 중립; `ACTION_HANDLERS` 재키잉과 DSL 자원 통합은 각각 중의성 해소·검증 규칙 충돌이라 설계 판정 필요).

## 2026-09-09 저녁 baseline agent Immortality 가치·엔진 교착 세션 요약 (master, 관측 v18, codec v103)

- 사용자 지시: "다음 작업 이어가보자". 인수인계가 남긴 후속 후보 (a) 대규모 소크 재실행, (b) heuristic/rollout의 Immortality 가치, (c) M10 학습 재개 중, 사용자 방침("구현 우선, 학습 최후순위")에 따라 **(b)를 구현하고 (a)로 검증**하는 순서로 잡았다. 커밋 3건 모두 master 직접 커밋이다.
- **`21b5318` baseline agent의 Immortality 가치.** heuristic은 Tleilaxu 카드 전부를 2.5, research 분기 전부를 3.0으로 매기는 고정 prior였고 rollout의 `player_value`에는 Immortality 항이 없었다. `acquire_tleilaxu`를 Imperium 획득과 같은 구조(기본 2.5 + 인쇄된 specimen 비용 + `_TLEILAXU_BONUSES` 5종 + deck-top 0.5)로, `choose_research_space`를 도착 칸의 인쇄 보너스(`_RESEARCH_BONUS_SCORES`, Research 2.0이 최고)로, `acquire_reclaimed_forces`를 두 옵션(troops 0.7 / tleilaxu 0.5)으로 나눴고, `player_value`에 specimen 0.5·research 열 0.4·Tleilaxu 칸 0.5·Family Atomics 0.3을 더했다. 두 표는 같은 축척을 쓴다(rollout이 `score_action`으로 후보를 고르므로 일관성이 필요하다). 세부와 근거 인용은 [implementation-audits/immortality.md](implementation-audits/immortality.md) "baseline agent의 Immortality 가치" 절.
- **A/B**: 변경 전 스냅샷을 `heuristic_old` baseline으로 런타임 등록해(`BASELINE_AGENT_FACTORIES`에 스크래치패드 모듈의 클래스를 넣고 `--workers 1`) 같은 seed·좌석 회전으로 대전시켰다. `--immortality --rotate-leaders`, 400 seed × 4 회전 = 1,599 매치(2:2 미러): 새 가중치 승률 27.9%·평균 순위 2.403·평균 VP 7.20, 스냅샷 22.1%·2.597·6.92. 미러 기준선 25% 대비 +2.9%p이고 독립 seed 블록 4개 전부에서 평균 순위가 개선됐다. 커밋된 트리만으로는 재현되지 않으므로(스냅샷 모듈이 필요) [evaluation/](evaluation/)에는 넣지 않았다.
- **`85bd179` 휴리스틱 동점 3건.** 전 옵션 12판 probe로 "최고 점수가 서로 다른 action_id 여러 개로 동점"인 legal-action 집합을 셌다. 대부분은 무해한 해결 순서 동점(OQ-027)이지만 셋은 아니었다: (1) `use_intrigue_effect`와 `finish_intrigue_effects`가 **둘 다 0점**이라 지난 세션 OQ-058로 낸 Intrigue 줄을 쓸지 말지 동전을 던지고 있었다(12판에 20회) — 사용은 다른 유료 화살표 효과와, 마무리는 다른 frame 종료와 같은 층으로 옮겼다. (2) `return_specimen`이 정확히 `_DECLINE_SCORE`(-2.0)여서 함께 제시되는 모든 decline과 동점이었고(12판에 약 95회) Tech tile·Commander 구매를 거절하는 대신 자기 Axolotl tanks를 비웠다 — 주석이 이미 "last resort"라고 적고 있었으므로 숫자를 -2.5로 내렸다. (3) `take_reveal_contract`·`take_trigger_contract`·`gain_reveal_persuasion`이 0점이라 Delivery Logistics의 "1 Persuasion —OR— contract"가 동전 던지기였다 — contract는 VP 경로이므로 셋 다 `take_contract`(2.0) 층으로 올렸다.
- **`3987126` 엔진 교착 수정(A/B가 적발).** `--immortality` A/B 1,599 매치 중 1건이 `RuntimeError: current player decision has no legal actions`로 죽었다(game_seed 78, policy_seed 900078). Ghola는 "has the same Agent box as the other grafted card"이므로 `[Immortality p. 11]` Steersman에 graft하면 그 box의 아이콘 두 개(`cards`, `recall`)가 두 벌 대기한다. 첫 box의 recall이 이번 turn의 유일한 Agent를 되돌리면 복사본의 `recall` 아이콘은 대상이 없어지는데, 어느 provider도 그 아이콘을 제시하지 못하고 다른 행동도 남지 않았다. 규칙은 이미 정해져 있었다 — OQ-057 (1): 조건이 거짓인 의무 Agent box는 "발동해 불발"시킬 수 없고 "turn이 끝날 때까지 불가능할 때만 불발한다". 엔진은 이 판정을 단일 효과 box에만 구현했고 `_dry_run_effect_is_unavailable`이 **아이콘이 남은 box를 즉시 False로 반환**해 stall로 인식되지 않았고 `finish_agent_turn`도 제시되지 않았다. 다중 아이콘 box를 그 box를 제시하는 세 provider(OQ-027)로 판정하고(`_pending_icons_offer_nothing`), turn 종료가 남은 아이콘을 모두 회수하도록 했다(`fizzle_pending_agent_icons` — `resolve_agent_card_effect`의 불발 분기에 대응하는 아이콘판). 나중의 효과가 아이콘에 대상을 주면 box는 다시 해결 가능해지므로 판정의 "그 사이 조건이 성립하면 해결해야 한다"도 그대로다. 회귀 테스트는 수정 없이는 실패함을 확인했다(`git stash`).
- **소크(항목 (a), `--rotate-leaders --soundness-interval 25`, 실패 0)**: 전 옵션 교차(`--promo-cards --bloodlines --tech-module --immortality`, `--ruleset both`) random 250판씩 500판(426,467 step)·heuristic 150판씩 300판(243,026 step), 확장 없는 `--ruleset both` random 150판씩 300판(200,051 step)·heuristic 100판씩 200판(129,473 step). 합계 1,300판 999,017 step.
- 검증: pytest **1,452**(신규 8건: heuristic 7 + rollout 1), Ruff, mypy 통과.
- 남은 후속 후보: (a)·(b)는 이 세션으로 끝났다. (c) M10 학습 재개(관측 v18·codec v103이라 체크포인트 전부 새로)와, `implementation-audits/immortality.md`가 새로 남긴 경계 하나 — `choose_research_influence`의 진영 선택은 여전히 네 진영이 같은 점수다(`score_action`은 상태를 보지 않으므로 정적 표로는 차등할 수 없다).

## 2026-09-09 Bloodlines contract token·디자이너 판정 세션 요약 (master, 관측 v18, codec v103)

- 사용자 지시: 디자이너 판정 대조의 후속 중 (2) contract token 8개 전사, (3) 추가 확인 2건을 먼저 하고, (1) 불일치 13건은 디자이너 판정을 무조건 따른다.
- contract token 8개(`Play`/`Document` 커밋 쌍): 카드면(에셋 `bloodlines/contract/*.webp`, manifest에 `content_id` 연결·Harvest 3+/4+ 파일명 정리)을 판독하고 BGG 인벤토리와 대조해 `BLOODLINES_CONTRACTS`로 전사했다([rules/bloodlines.md](rules/bloodlines.md) 1절 표). 새 조건 종류 `EARN_ALLIANCE`(엔진 hook `complete_alliance_contracts`가 매 전이 뒤 Alliance 이벤트로 완료; Agent 방문 snapshot 없음)·`IMMEDIATE_INTRIGUE_TRASH`(hand Intrigue 게이트 → `contract_intrigue_trash` frame → trash → Intrigue 1·draw 1), 보상 필드 `intrigue_cards`·`deep_cover_spies`(Deep Cover Spy 배치는 자기 Spy만 제외). intrigue.py의 `_update_agent_turn_frame`를 `frames.update_turn_recruits`로 옮겨 hook이 turn 소유자의 배치 몫을 갱신한다. 세부는 [implementation-audits/bloodlines.md](implementation-audits/bloodlines.md) "Contract token" 절, 판정은 OQ-056.
- 디자이너 판정 2건(이미 보유한 Alliance는 완료 안 됨, 같은 turn 획득 → 같은 turn 완료)은 구현과 일치함을 테스트로 고정했다([rules/designer-rulings-audit.md](rules/designer-rulings-audit.md) 콘텐츠 공백 절).
- 추가 확인 2건([rules/designer-rulings-audit.md](rules/designer-rulings-audit.md) "추가 확인" 절): Leadership+Calculus of Power+Sardaukar Soldier는 엔진이 이미 판정과 같아(한 번 세고 trash 뒤 재계산 없음, 총 8) 테스트로 고정했고, Duncan Idaho의 Into the Fray Agent를 Imperial Privilege로 recall하는 경로는 없어서 `recall_conflict_agent_for_imperial_privilege`를 더했다(OQ-037(d), codec v99).
- 디자이너 판정 배치 A(같은 날, `Play`/`Document` 쌍): 5(Combat 보상 동률의 First Player 순서, OQ-002 재판정), 6(Impress·Inspire Awe는 대상이 없어도 play, `skip_intrigue_acquisition`), 7(Change Allegiances 세 번째 option — Loyalty/Navigation 자원으로 두 번째 비용 지불은 잔여 경계), 8(Usurp의 Stillsuit는 hand로 안 돌아옴, OQ-054), 9(카드 출처 Acquire Tech는 살 수 있으면 거절 불가), 10(Ceremony keep → Suspensor troop), 12(Ghola+Long Reach 세 아이콘, `ghola_partner`), 13(Reveal Research 아이콘은 행동당 하나). 판정 등록은 OQ-057. codec v100.
- 디자이너 판정 배치 B(같은 날): 4("Choose Two" 원자성 — Propaganda·Stitched Horror·Rapid Engineering·Long Reach·Buy Access는 두 선택을 먼저 받고 해결), 11(Combat 보상으로 받은 Harvest Cells를 정리 전 `conflict_end_trigger` 창에서 즉시 play; 상태 플래그 `combat_end_triggers_offered`, 관측 v17, codec v101).
- 디자이너 판정 배치 C(같은 날): 1(조건이 거짓인 의무 Agent box는 `agent_card_effect_is_unavailable` dry-run으로 숨기고 `finish_agent_turn`이 turn 종료 시 불발 처리 — OQ-028(a) 재판정), 2(Interstellar Trade는 한 번만, OQ-028(c) 폐기), 3(Guild Spy는 Reveal마다 사본당 한 번, 늦게 공개된 Guild Spy도 반응; Reveal frame 문맥 `spice_must_flow_acquired`·`guild_spy_fired`). **이로써 13건 전부 반영.** 잔여 경계: Change Allegiances의 순차 지불(OQ-057 (7)).
- 검증: pytest 1,443, Ruff, mypy 통과(dry-run은 상태 identity 캐시로 전체 테스트 시간 120초 유지).
- **OQ-058(사용자 판정, 같은 날 저녁)**: Intrigue의 인쇄 줄은 각각 따로 쓰고 쓸 때 지불한다. 전수 조사 결과 "—OR—" 없이 화살표 줄이 따로 인쇄된 카드는 Change Allegiances·Strategic Stockpiling·Depart for Arrakis·Find Weakness·Questionable Methods 5장이고(`IntrigueOption.separate`), 나머지 복수 option 카드는 카드면의 "—OR—"대로 배타다. 새 frame `intrigue_effects`(`use_intrigue_effect(section)`/`finish_intrigue_effects`; 비용 없는 줄은 play 즉시, 남은 줄이 없으면 자동 마무리), `section_is_usable`, `finish_intrigue_play(discard=)`. OQ-015(b) 폐기, OQ-057(7) 잔여 경계 해소. 사용자가 이어서 "화살표 비용은 어디서나 선택"으로 일반화해 Imperium·Tleilaxu·board·Tech·Leader의 화살표 효과를 전수 확인했고 모두 이미 거절 행동이 있어 코드 변경은 없었다(OQ-058에 기록). 이어서 trash 아이콘 판정(용어집 `[Main p. 20]`: 비용·자기 자신 지시가 아니면 선택)으로 Calculus of Power의 잘못된 "자기 자신 trash" 전사를 일반 선택 trash로 고치고(사용자 적발 버그), Tread in Darkness는 trash를 거절해도 draw하도록 했다. 관측 v18, codec v103. 소크: heuristic 세 확장+프로모 `--rotate-leaders` 80판씩(160판, 129,728 step)·random 기본 `--ruleset both` 150판씩(300판, 201,360 step) 실패 0.
- 소크(세 확장 + 프로모, `--rotate-leaders --soundness-interval 25`): 첫 실행이 결함 2계열을 적발했다 — (a) Bloodlines+Immortality codec에 Immortality Intrigue의 give/trash 템플릿이 빠져 있었다(v102로 보강), (b) Ghola가 Duncan의 Signet Ring box(Into the Fray)를 복사하면 Agent가 이미 Conflict로 간 뒤 두 번째 배치가 RuntimeError를 냈다(`legal_leader_signet_actions`가 이번 turn의 Agent가 아직 공간에 있을 때만 제시). 재실행: random `--ruleset both` 150판씩(300판, 255,360 step)·heuristic 60판씩(120판, 96,772 step) 실패 0; 확장 없는 random `--ruleset both --rotate-leaders` 100판씩(200판) 실패 0. 첫 전체 실행에서 heuristic Bloodlines 게임 2건이 "Contract population changed"로 실패해(trash 대기 중 token이 어느 영역에도 없었음) token을 frame이 열린 동안 active 영역에 두는 방식으로 고쳤다.

## 2026-09-08 저녁 디자이너 판정 대조 세션 요약 (master, 코드 변경 없음)

- 사용자 제공 자료: BGG 스레드 3005216의 커뮤니티 FAQ 정리본(Google Docs, 2026-06-07판; `export?format=txt`로 받음). 공식 룰북·FAQ에 없는 Paul Dennen의 포럼·Discord 답변을 모은 문서다.
- 진행: 문서 전체(1,223줄)를 읽고 구현 범위(Uprising 4인+CHOAM+프로모+Immortality+Bloodlines/Tech)에 있는 항목만 골라, repo-scout 5개로 위치를 찾은 뒤 핵심 항목은 main 세션이 코드를 직접 열어 확정했다. 스카우트 보고 중 잘못된 것(Propaganda를 wild 매칭으로 오인, Call to Arms 테스트 이름 오독, Combat 보상 순서 "일치" 판정)은 직접 확인으로 바로잡았다.
- 결과: [rules/designer-rulings-audit.md](rules/designer-rulings-audit.md) — 일치 30여 항목(표), 불일치 13건(표, 파일 위치·비고), 콘텐츠 공백 1건(Bloodlines contract token 8개 미전사), 추가 확인 2건(Leadership+Calculus trash 시점, Into the Fray recall). `rules/README.md`에 링크. 엔진·테스트·규칙 문서는 바꾸지 않았다.
- 검증: 문서만 변경했으므로 테스트를 다시 돌리지 않았다(기준선은 직전 세션의 pytest 1,418·Ruff·mypy 통과).

## 2026-09-08 Immortality 슬라이스 6 마감 세션 요약 (master, 관측 v15, codec v97)

- UI(`6655160`): 카탈로그의 Tleilaxu deck·Reclaimed Forces·`bene_tleilax` 절, market의 Tleilaxu Row와 Bene Tleilax board 패널(research grid·Tleilaxu track 위 좌석 token), 좌석 카드의 Immortality 상태. headless Chromium으로 렌더 확인.
- 소크(`--rotate-leaders --soundness-interval 25`, 6 worker): immortality+promo random 300·heuristic 150, 전 옵션 random 200·heuristic 120, draft 60 — 830판 실패 0. 첫 실행이 잡은 결함 3계열(`37fa1b7`): Research ×2 draw의 이중 discard 셔플(같은 카드가 두 존에; `draw_or_request_personal_cards`가 대기 중 셔플에 합류), Usurp 배치의 상대 부재 교착(따라올 상대가 있는 space만 제공), heuristic의 graft switch 무한 반복(해결 가능한 box 행동이 있으면 switch 최하위, `complete_contract_by_card` prior 8.0).
- census: Immortality 구성물 0회 없음(graft 상대를 `cards_played`로 세도록 보강, `e9e7fa2`); 0회 행동은 `decline_agent_card_recall`·`decline_reveal_influence_loss`뿐(단위 테스트가 덮음). 세부는 audit의 슬라이스 6 표.
- 사용자 판정(세션 말): Usurp로 빌린 Row 카드는 turn이 닫힐 때 보통의 trash로 자동 폐기돼 trash 트리거가 발동하고(OQ-054 갱신), "may"라 hand 카드와의 graft도 그대로 된다(테스트 2건 추가).
- 사용자 OQ 검토(세션 말): OQ-048 확인(Tleilaxu track 끝은 효과 없음), OQ-049는 UI 표시 요청 — 서버가 합법 행동을 dry-run해 `specimens_short`/`troops_recruit_short`가 나면 행동에 `warning`을 붙이고 클라이언트가 배지로 보여 준다(`sessions.shortfall_warning`), OQ-052는 사용자 판정으로 정정 — 두 장 미만이면 맨 윗장을 두고 그 밑에 discard를 섞어 새 deck을 만든 뒤 두 장을 본다(셔플 chance frame `purpose=peek`), OQ-053은 garrison·Conflict 각각 하나씩도 허용(`lose_reveal_troops_for_specimens(zones)`, 조합 3), OQ-055는 추가된 아이콘도 셈(`rules/agent_icons.py`로 `effective_agent_icons` 분리). 카드 수량은 사용자가 알려준 BGG 카드 인벤토리 시트로 확정했다(Imperium 30장·Intrigue 15장; 에셋 저장소 `reference/bgg-card-inventory/`, `sources.md`·AGENTS.md에 등록). research track 보너스는 사용자의 board 스캔으로 대조해 일치했고, 그 스캔(`assets/board/bene_tleilax.jpg`, 에셋 저장소 `a4bd9aa`)을 `/bene-tleilax-image`로 서빙해 UI가 합성 grid 대신 스캔 위에 token을 그린다(`display/bene_tleilax_layout.py`).
- 검증: pytest 1,417, Ruff, mypy; immortality+promo random 120·전 옵션 heuristic 60 소크 실패 0. **M13 완료.** 남은 후속은 audit "미완 경계".

## 2026-09-08 Immortality 슬라이스 5c-2 세션 요약 (master, 관측 v15, codec v97)

- Ghola·Chairdog·Usurp([implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 5c-2 표): 활성 카드 box 접근자 `active_agent_card`(Ghola), 좌석 필드 `chairdog_return_card_ids`(Reveal 시작 반환)·`usurped_row_card_id`(turn 마감 시 자동 dispatcher `resolve_usurp_trash`가 보통의 trash로(트리거 발동, OQ-054 사용자 판정)), Usurp의 Row 아이콘 배치와 Row 상대 선택. 관측 v15(좌석 scalar 51, 총 4,235). OQ-054(Usurp 카드의 행선지), OQ-055(Slig Farmer의 아이콘 셈).
- 소크가 잡은 결함: Ghola가 Corrinth City의 box를 복사하면 두 box가 decline만 제공해 heuristic이 `switch_graft_card`를 무한 반복(checked game seed 11, 30,000 step) — decline이 있는 box에서는 switch를 decline 아래로. codec에 Usurp graft 배치 변형(모든 space) 추가.
- 검증: pytest 1,409(새 테스트 4), Ruff, mypy; `--soundness-interval 1` 소크(immortality+promo random 24·heuristic 24, 전 옵션 heuristic 8) 실패 0, Ghola·Chairdog·Usurp 전부 play. 커밋 `0a97bf1`(코드) + 이 문서 커밋.
- 다음: 슬라이스 6(UI·heuristic·소크·census·마감).

## 2026-09-08 Immortality 슬라이스 5c-1 세션 요약 (master, 관측 v14, codec v97)

- Tleilaxu 6종 + 프로모 Piter의 play data([implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 5c-1 표). 새 행동(immortality 카탈로그): `trash_agent_card_self_for_vp`, `pay_agent_card_five_solari_for_tleilaxu`, `trash_grafted_card_for_influence(card_id)`, `lose_agent_card_troop(zone)`, `choose_agent_card_reward(reward)`. 모두 지불 provider(`legal_agent_card_payment_actions`) 경유.
- 검증: pytest 1,405(새 테스트 8), Ruff, mypy; `--soundness-interval 1` 소크(immortality+promo random 12·heuristic 30, 전 옵션 random 12) 실패 0, 7종 전부 play. 커밋 `5e37e29`(코드) + 이 문서 커밋.
- 다음: 슬라이스 5c-2(Ghola·Chairdog·Usurp) → 6(UI·heuristic·소크).

## 2026-09-08 Immortality 슬라이스 5b-2 세션 요약 (master, 관측 v14, codec v97)

- 남은 Imperium 8종의 play data([implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 5b-2 표)로 Immortality Imperium 25종이 모두 play된다. 새 기계: `INTRIGUE_PEEK` frame(`rules/intrigue_peek.py`; 소유자만 보는 deck 맨 위 두 장 — `PrivatePlayerView.peeked_intrigue_ids`, `known_card_seats`, determinize·privacy invariant 고정, 관측 v14 세그먼트 `private_peeked_intrigue` 90칸), Reveal choice 3종(Influence→VP, troop 배치/후퇴, troop 2→specimen 2; `IMMORTALITY_REVEAL_CHOICE_EFFECTS`로 기본 카탈로그 불변), 지불 provider의 specimen 2·graft 상대 trash·Combat 아이콘 선택, 획득 provider의 비용 상한 무료 획득(`acquire_*_by_card`). OQ-052(두 장 미만의 peek), OQ-053(Surgeon의 troop 출처 존).
- 소크가 잡은 결함: 획득한 카드의 Research 획득 box가 여는 방향 frame이 Intrigue 획득 slot을 묻어 `RuntimeError`(heuristic seed 11) — `_lift_pushed_frames`로 위로 올리고, 같은 구조였던 Price is No Object·Leader Signet 획득은 box를 먼저 닫도록 고쳤다. `grant_combat_icon` 뒤 오래된 컨텍스트로 frame을 덮어쓰던 Occupation/High Priority Travel도 수정.
- 검증: pytest 1,397(새 테스트 11), Ruff, mypy; `--soundness-interval 1` 소크(immortality+promo random 24·heuristic 24, 전 옵션 heuristic 8) 실패 0, 새 카드 8종·새 행동 13종 전부 발화. 커밋 `d50e5f1`(코드) + 이 문서 커밋.
- 다음: 슬라이스 5c(Tleilaxu 9 + Piter) → 6(UI·heuristic·소크).

## 2026-09-08 Immortality 슬라이스 5b-1 세션 요약 (master, 관측 v13, codec v97)

- Imperium 15종의 play data([implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 5b-1 표): 단일 box 9종, 선택 box 3종(Long Reach의 서로 다른 진영 2개, Organ Merchants의 specimen 지불 `pay_agent_card_specimen`, Sardaukar Quartermaster의 graft 조건 아이콘), 인쇄 조건부 Agent 아이콘 `ImperiumCardEntry.icon_condition`(Long Reach의 BG Bond, Show of Strength의 배치 troop 우위 — play 시점 판정, 조건 미달이면 아이콘 0개), 획득 box `GAIN_ONE_SPICE`·`RECRUIT_THREE_TROOPS`, trash trigger `ADVANCE_TLEILAXU`(Replacement Eyes), Reveal 필드 `tleilaxu`·`research`(소유자 시점 `advance_reveal_tleilaxu`/`advance_reveal_research`), Stillsuit Manufacturer의 Fremen Alliance hand 반환(`hand_public`), Throne Room Politics의 recruit 뒤 `optional_trash`, graft 상대가 들어온 뒤 첫 카드의 Bond box 재판정.
- codec v97: Occupation의 Reveal water+spice 묶음이 모든 카탈로그의 `gain_reveal_resources`에 들어가 기본 카탈로그가 1 늘었다(4,368).
- 검증: pytest 1,386(새 테스트 15), Ruff, mypy; `--soundness-interval 1` 소크(immortality 단독, random·heuristic 각 8판) 실패 0, 새 카드 14종 전부 play. 커밋 `cde0954`(코드) + 이 문서 커밋.
- 다음: 슬라이스 5b-2(Imperium 8종) → 5c(Tleilaxu 9 + Piter) → 6(UI·heuristic·소크).

## 2026-09-08 Immortality 슬라이스 5a 세션 요약 (master, 관측 v13, codec v96)

- Intrigue 11장을 effect DSL로 전사·구현했다([implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 5a 표): 새 조건 4종 + `AllConditions`, 보상 5종, trigger `OnTroopsLostAtConflictEnd`(Combat timing 허용; `finish_combat`이 정리 시점의 Conflict 유닛 수로 발동/만료 판정, `resolve_faceup_trigger_option`은 `apply_intrigue_play`의 꼬리를 `_resolve_paid_option`으로 나눈 것). Counterattack용 `GameState.combat_intrigue_players`, Tleilaxu Puppet용 `PlayerState.reveal_persuasion_round_bonus`(관측 v13: 좌석 scalar 49, 전역 `combat_intrigue_players` 4). `AcquireTleilaxuCard` 선택 slot은 `tleilaxu_row.acquire_tleilaxu_card`를 재사용. codec: `acquire_intrigue_tleilaxu`(+deck top)·`decline_intrigue_tleilaxu`, Bloodlines 없이도 `lose_intrigue_troop`(Gruesome Sacrifice).
- 소크가 잡은 결함: (1) `lose_intrigue_troop` 템플릿 누락, (2) heuristic이 `switch_graft_card`(2.0)와 낮은 점수의 box 행동 사이를 무한히 오가 30,000 step 초과(전 옵션 seed 3·6) → 우선순위 0.2로 조정, (3) 관측의 `relative()`가 1-based라 세그먼트 인덱스 오류.
- 검증: pytest 1,371, Ruff, mypy; `--soundness-interval 1` 소크(immortality 단독·전 옵션, random·heuristic 각 10판) 실패 0.
- 다음: 위 "다음 구현 순서"의 슬라이스 5b(Imperium 23종).

## 2026-09-08 Immortality 슬라이스 4 세션 요약 (master, 관측 v12, codec v96)

- Graft(`rules/graft.py`; [implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 4 표): `legal_agent_actions`가 카드마다 단독/`graft=True` 변형을 낸다(Graft 카드는 graft만, 일반 카드 둘은 불가, Infiltrator가 hand에 있으면 점유 space도 graft로 열림). `apply_agent_action(graft)`는 효과 frame 위에 `graft_partner` frame을 밀고 `choose_graft_partner(card_id)`가 둘째 카드를 in play로 옮기며 효과 frame의 `graft_card_id`/`graft_pending_effect`/`graft_pending_icons`에 그 box를 대기시킨다. `switch_graft_card`가 활성 카드와 상대를 맞바꿔 기존 Agent box 기계로 해결한다(효과 frame 컨텍스트 키 3개 추가, 정렬 필수 — 첫 소크가 정렬 위반을 잡았다). `expire_trashed_card_effects`는 상대 box도 만료. 카드 8장(Face Dancer·Initiate·Corrino Genes·Unnatural Reflexes·Tleilaxu Infiltrator·Twisted Mentat·Bene Tleilax Researcher·Planned Coupling)과 Reveal의 `minimum_genetic_markers` 조건, Twisted Mentat의 recall 거절(`decline_agent_card_recall`), Blank Slate용 `effective_agent_icons(grafted=)`.
- 검증: pytest 1,360, Ruff, mypy; `--soundness-interval 1` 소크(immortality 단독·+Bloodlines+Tech+CHOAM, random·heuristic 각 6판) 실패 0, graft·switch·recall 경로 발화. `immortality` 카탈로그 6,857(기본 불변).
- 다음: 위 "다음 구현 순서"의 슬라이스 5.

## 2026-09-08 Immortality 슬라이스 3 세션 요약 (master, 관측 v12, codec v96)

- Tleilaxu Row(`rules/tleilaxu_row.py`): Reveal frame의 `acquire_tleilaxu`(specimen 지불, discard/deck 맨 위, Row 보충, 획득 box)와 `acquire_reclaimed_forces(choice)`. 획득 box `RESEARCH`·`ADVANCE_TLEILAXU`는 `acquisition.py`의 `apply_acquisition_track_effects`로 Imperium 경로 4곳 + Tleilaxu 경로에서 해결하고, `resolve_acquisition_bonus`가 `tleilaxu:` instance를 읽는다. 첫 카드 3장(Contaminator·From the Tanks·Subject X-137)에 play data를 넣어 setup이 실제로 Row를 deal한다. codec: `immortality` 카탈로그에 획득 템플릿과 Tleilaxu 카드 배치 템플릿, Bloodlines 없이도 `optional_trash` 템플릿(첫 소크가 `decline_optional_trash` 누락을 잡았다). deck 맨 위로 간 카드의 instance는 이벤트에서 뺐다(가시성 불변식).
- 검증: pytest 1,345, Ruff, mypy; `--soundness-interval 1` 소크(immortality 단독·+CHOAM+promo·+Bloodlines+Tech, random·heuristic 각 8판) 실패 0. 세부는 [implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 3 표.
- 다음: 위 "다음 구현 순서"의 슬라이스 4(Graft).

## 2026-09-08 Immortality 슬라이스 2 세션 요약 (master, 관측 v12, codec v96)

- Bene Tleilax board 구현(`rules/immortality.py`, `rules/specimens.py`; 세부는 [implementation-audits/immortality.md](implementation-audits/immortality.md) 슬라이스 2 표): 상태 필드(`research_space`·`tleilaxu_space`·`specimens`·`family_atomics`, `tleilaxu_deck`·`tleilaxu_row`·`tleilaxu_track_spice`; specimen은 troop 12개 불변식에 포함), setup(Experimentation 교체 `starting_deck_entries(immortality=)`, `setup:tleilaxu_deck` 셔플은 play data 있는 카드가 있을 때만), research 전진과 두 frame(`research_advance`·`research_bonus`), Tleilaxu track, specimen 생성·반환·Reveal 시점 선택(`generate_reveal_specimens`), 개정 Research Station(`research` 보드 아이콘, `AUTOMATIC_BOARD_ICONS`에 정렬 삽입), Family Atomics. `card_draw`가 `reveal_turn`을 import하므로 specimen 생성은 `rules/specimens.py`로 분리해 순환을 피했다.
- 판정: OQ-048(Tleilaxu track 끝: 효과 없음), OQ-049(supply 빈 specimen: 부족분 소멸, OQ-030과 동형), OQ-050(specimen 반환 창: 소유자의 turn·효과·Reveal frame), OQ-051(Family Atomics 제거 카드: `imperium_removed`). 모두 project convention `DECIDED`.
- 검증: pytest 1,332(새 테스트 23), Ruff, mypy; random·heuristic 각 6판 소크에서 research 연쇄·marker·보너스·specimen 부족·Family Atomics 경로 전부 발화. 에셋 manifest에 Experimentation `content_id` 추가.
- 다음: 위 "다음 구현 순서"의 슬라이스 3.

## 2026-09-08 Immortality 슬라이스 1 세션 요약 (master, 관측 v11, codec v95)

- 사용자 지시: "Immortality 확장 구현하려고해". Uprising Main p. 18의 "Adding Immortality"(Research Station overlay만 지시)가 조합을 공식 지원하므로 Bloodlines와 같은 옵션 방식(`RulesetConfig(immortality=True)`, `+immortality`)으로 착수했다. Bloodlines와 독립이라 함께 켤 수 있다.
- 출처: 공식 Immortality 룰북(16쪽, sha256 `2a7ba3b8…`)을 `official-rule-sources.json`·`sources.md`·`source-map.md`에 등록하고 `SourceDocument.IMMORTALITY_RULEBOOK`을 추가했다. 규칙 명세는 [`rules/immortality.md`](rules/immortality.md)(setup, research·Tleilaxu track, specimen, Tleilaxu Row·Reclaimed Forces, Graft, 새 아이콘·개정 Research Station, Family Atomics, FAQ의 Beguiling Pheromones·Chairdog·Ghola·Tleilaxu track 항목). 2025-01-13 FAQ에 Immortality 항목이 있음을 확인했다.
- board 전사: 룰북 p. 3의 board 그림을 500 dpi로 잘라 research track 21칸 + 시작 칸의 보너스와 인접(`content/immortality/board.py`: `c열r행` 좌표, `research_next_space_ids`, genetic marker 열 4·8), Tleilaxu track 8칸(칸 2·6 Intrigue, 4 VP + 첫 도달 spice 2, 7 VP)을 옮겼다. 아이콘은 `assets/icons/`와 대조(Solari 회색 원, spice 주황 육각, VP 금색 구). c8r6의 "7 → 두 scarab"은 "Solari 7 → Tleilaxu 2"로 읽었다(저해상도라 슬라이스 2에서 UI 표시 때 재확인).
- 카드: 에셋 `cards/en/immortality/` 57장을 전부 판독해 [implementation-audits/immortality.md](implementation-audits/immortality.md)에 전사표를 남겼다(Tleilaxu 18 + Reclaimed Forces + 프로모 Piter, Imperium 25, Intrigue 11, Experimentation). 수량은 Dune Cards Hub의 `/api/cards`(`physicalCopies`; WebFetch는 403이지만 curl UA+referer로 JSON을 받을 수 있다)에서: Imperium 27장(Dissecting Kit·Tleilaxu Master ×2), Intrigue 11, Tleilaxu 18 — 룰북의 30·15와 Imperium 3장·Intrigue 4장 차이가 있고 identity를 못 찾아 카탈로그 수량을 채택했다(audit 문서에 기록). 카탈로그: `content/immortality/tleilaxu.py`의 `TleilaxuCardEntry(ImperiumCardEntry)`(`specimen_cost`·`graft`, instance `tleilaxu:<id>:<copy>`), `imperium.py`·`intrigue.py`의 `immortality_only` 항목(`imperium_cards_for_choam(..., immortality=)` 등 필터 kwarg). play data가 없는 카드는 덱에 들어가지 않는다.
- 연결: 서버 `immortality` 필드·UI 체크박스·배지, 저장 문서 플래그(구 문서는 False), sweep/tournament `--immortality`, coverage `zero_coverage(immortality=)`, 체크포인트 룰셋 파싱, `display/images.py`의 `INDEXED_SETS`에 `immortality`와 `tleilaxu` 이미지 키. 에셋 저장소 manifest의 Immortality 56항목에 `content_id`를 달았다(`f309812`; Piter는 kind `tleilaxu`). 관측 v11(identity 우주 확장만, 3,166→3,729; 이전 체크포인트 거부).
- 검증: pytest 1,309, Ruff, mypy. 커밋 `19ec0fe`(코드) + 이 문서 커밋.
- 다음: 위 "다음 구현 순서"의 슬라이스 2.

## 2026-09-08 구현 마감 세션 요약 (master, 관측 v10, codec v95)

- 사용자 지시: 학습은 최후순위, 구현이 먼저 완벽해야 한다. Endgame tiebreaker에 Commander를 **포함**해 세고, Bloodlines 프로모도 구현하라. 제안 순서(census → OQ 판정 → 서버 좌석 → UI)대로 진행했다.
- 커버리지 census(`--coverage-json`, `--bloodlines --tech-module --rotate-leaders`, random 룰셋당 300판): Bloodlines·Tech 콘텐츠(카드·tile·Leader 이벤트)에 0회 항목 없음. 0회로 남은 것은 룰셋 범위 밖(base 룰셋의 contract 20종, `pick_leader`(draft 미사용), Shaddam Signet 행동, 프로모 지불 행동)과 random 정책의 희귀 경로(`pay_agent_card_intrigue_and_spice`, 4-contract Reveal 선택, `take_exhausted_contract_solari`, Secure Spice Trade·CHOAM Profits·Shadow Alliance)뿐이며 모두 단위 테스트가 덮는다. 프로모를 켠 재실행(아래)도 같다.
- OQ-047(`f491cfb`): "garrison의 troop 수" tiebreaker `[Main p. 15]`에 garrison의 Sardaukar Commander를 포함(`[Bloodlines p. 4]`의 "Commander는 troop"의 연장, 사용자 판정). `FinalStanding.commanders_garrison` 추가, `_ranking_key`는 `troops_garrison + commanders_garrison`. supply·Conflict의 Commander는 세지 않는다.
- Ruthless Leadership(`52e9c22`·`91cc6ba`): 에셋 저장소 `bloodlines/promo/`의 유일한 Bloodlines 프로모(Dune Cards Hub는 JS 렌더링이라 목록을 못 읽었고 manifest의 owner 분류를 따랐다). 카드면 판독: Emperor, 비용 4, City·SpiceTrade 아이콘(파란 원을 Emperor로 잘못 읽었다가 사용자 지적으로 고침 — `lessons.md` 2026-09-08); Agent "If you have one or more Sardaukar Commanders in the Conflict:" + 검은 trash 아이콘 2개(Desert Survival·Eliminate Allies의 아이콘과 대조), Reveal 1 Persuasion + 검 1(Elite Forces의 붉은 검 아이콘과 대조), Command (6+): Combat 아이콘(Holy War의 X 아이콘과 대조). `promo=True, bloodlines_only=True`로 두 옵션을 함께 켤 때만 덱에 들어간다. 새 Agent 효과 `MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT`: 조건은 해결 시점 판정(OQ-028), 충족이면 trash 선택을 한 번에 하나씩 최대 2회(The Beast's Spoils의 `crysknife_trashes_remaining`를 `trashes_remaining`으로 일반화), 불충족이면 `agent_card_effect_unavailable`. 관측 v10(+19: identity 1개 × 카운트 세그먼트), codec v95(base 카탈로그 크기 불변). 에셋 manifest에 `content_id` 추가(에셋 저장소 `9c24a10`, 미push). 소크(`--promo-cards --bloodlines --tech-module --soundness-interval 25`): random `--rotate-leaders` 200판/룰셋 + heuristic 60판/룰셋 + draft random 60판/룰셋 = 640판 실패 0; census에서 카드가 룰셋당 33~38회 play됐다.
- 서버 AI 좌석(`0e9af1f`): `AGENT_SEATS` 딕셔너리를 `agents.registry`(`is_agent_kind`/`make_agent`)로 바꿔 `random`·`heuristic`·`rollout`·`checkpoint:<경로>`를 받는다. `_agent_action`이 `StateAgent`면 `choose_action_with_state`(권위 상태)를 호출 — 자동 진행과 저장본 replay 재생성 둘 다. 체크포인트 로드 실패(파일 없음·버전 불일치·`train` extra 없음)는 생성 시 400 `SessionError`. UI: 좌석 select에 "롤아웃 탐색 AI"·"학습 체크포인트"(경로 입력칸 `#opt-checkpoint`), 좌석 배지는 종류 라벨(`seatKindLabel`). 회귀: rollout 좌석 생성·재현·사람 턴 사이 행동, 저장/복원 동일, API 400.
- UI(`965e5bd`): (1) Agent 토큰 이동 애니메이션 — `renderBoard`가 직전 그림의 토큰 사각형(좌석:공간)을 기억하고 새로 생긴 토큰만 좌석 패널의 `.seat-mark`에서 FLIP으로 날아오게 한다(첫 그림·`prefers-reduced-motion`은 제외; 원점이 없으면 pop-in). (2) 오른쪽 패널 2열 기준을 1400px → 1700px로 올렸다(1600px에서 34vw ≈ 540px라 2열이 각 270px로 너무 좁음); `#table` 열 축소는 1400px 유지. Playwright(headless, 세션 스크래치의 versioned ALSA stub 재구축)로 1600×900(1열 544px)·1920×1080(2열 322px)에서 새 게임 → Leader 선택 → Dagger를 Assembly Hall에 배치까지 눌러 토큰이 `.flying` 상태를 거쳐 자리잡는 것과 콘솔 오류 0을 확인했다.
- 검증: pytest 1,302(endgame 1 + Ruthless 5 + 서버 4), Ruff, mypy. 소크·census 결과는 위 항목.

## 2026-09-07 밤 M12 슬라이스 7 마감 세션 요약 (master, 사용자 부재 중 자율 작업)

- 범위: 슬라이스 7 전부를 master에 직접 5건으로 올렸다 — 소크 결함 수정 `642419b`, 저장 문서 모듈 플래그 `255fc66`, UI 표시 `5cd0c61`, heuristic·rollout 가중치 `6dea241`, 문서(이 커밋). 사용자 지시는 "다음 구현 이어가자, 2시간 정도 쭉 작업"이었다.
- 소크(`--bloodlines --tech-module --soundness-interval 25`, random 2,000판/룰셋 `--rotate-leaders` + heuristic 1,000판/룰셋 + draft random·heuristic 500판/룰셋 = 7,000판): 첫 실행에서 10판 실패, 3계열. (1) Engineered Miracle의 Command 선택이 대기하는 동안 다른 Reveal 효과가 그 카드를 trash하면 Row 카드 획득을 계속 제시해 `trash card is not in an eligible owned zone`(seed 901·936) — OQ-022대로 거절만 남긴다. (2) Detonation·Twisted Devious의 "garrison에서 배치" 옵션은 play 판정이 garrison 전체를, 배치 선택은 Harkonnen Advisor의 배치 금지 troop을 뺀 수를 봐서 Signet troop 하나만 있으면 선택 frame에 합법 행동이 없는 교착(seed 138·309·251·249·347) — 공용 helper `combat_deployment.undeployable_troops_this_turn`으로 통일(OQ-038 보강). (3) Gaius Helen Mohiam의 Clandestine + 연결된 Spy로 Treacherous Maneuver를 Landsraad space에 놓으면 화살표 선택이 `RuntimeError: requires a Faction space`(seed 411·263·202) — Faction 없는 space에서는 화살표 비용을 제시하지 않는다(**OQ-046**, project convention). 수정 뒤 10 seed 재현 전부 완주, 7,000판 재실행 실패 0.
- 저장/불러오기 결함: `persistence.py`의 save 문서가 `promo_cards`·`bloodlines`·`tech_module`을 기록하지 않아 Bloodlines 게임을 불러오면 base 룰셋으로 replay를 시도했다(UI 검증 중 발견). ruleset 블록에 세 플래그를 넣고 없는 문서는 꺼짐으로 읽는다(형식 버전 유지, 회귀 테스트 1건).
- UI: `/catalog`에 `skills`(이름·종류·효과 텍스트·이미지)·`tech`(이름·비용·acquire·ability·Flip 여부·CHOAM 전용·이미지)·`embassy_image` 절, `display/bloodlines.py`(Skill 효과·tile acquire/ability 영문 텍스트), `display/images.py`의 필수 이미지 키(`skill` 7·`tech` 18·Ixian Embassy board; 비공개 에셋 저장소 `d5093b7`, 미push). `app.js`: 좌석 패널의 Commander 수·Conflict Commander·Skill/Tech chip(Flip 면 `.flipped`, Secret Project·box Spy·Twisted·Navigation 플래그), 공용 열의 Sardaukar Commander 칸·bank, face-up Skill, Ixian Embassy 세 stack(face-up tile + 남은 수, 빈 stack)과 Tech trash, 보드 병력 칩의 Commander 표시(`C1`), tile·Skill 호버 상세, 새 행동 라벨 전부. 브라우저로 새 게임(Bloodlines+Tech)과 round 6 저장본(`GameSessionManager`로 만든 save)을 불러와 좌석 패널·공용 열·tile 상세·행동 목록을 확인했다.
- 에이전트: heuristic `score_action`에 `acquire_tech`의 tile별 보너스(`_TECH_BONUSES`: Sardaukar High Command 2.0, CHOAM Transports 1.5, Panopticon·Navigation Chamber·Ornithopter Fleet 1.0, 그 외 0.5/0) — 행동만 보는 설계라 비용·잔여 spice는 여전히 반영하지 않는다. rollout `player_value`에 Commander 1.2·Skill 0.5·Tech tile 1.0. 같은 룰셋 대회(heuristic 대 random, 12판) 불법 행동 0.
- 학습 smoke: `dune-imperium-train --iterations 3 --games-per-iteration 32 --workers 4 --eval-every 3 --eval-games 4`가 관측 v9·codec v94로 수집·갱신·체크포인트·평가까지 정상(6,400 dec/s). 학습 루프는 아직 `--choam`만 알고 Bloodlines 옵션이 없다(다음 후보 (b)).
- 검증: pytest 1,292(회귀 3 + 저장 1 + 표시 4 + 카탈로그 1 + 에이전트 2), Ruff, mypy. `.claude/launch.json`(UI 서버 미리보기 설정)은 커밋하지 않았다.

## 2026-09-07 저녁 M12 슬라이스 6 Tech Module 세션 요약 (master, 관측 v9, codec v91→v94)

- 범위: 슬라이스 6 전부를 master에 직접 4개 `Play` 커밋으로 올렸다(6a 획득 `1df49e3`, 6b 능력 `66ec950`, 6c·6d 카드 3종과 Kota `9aba35c`; 사이에 Navigation 대기열 수정 `561c491`). 전사는 에셋 저장소의 tile 18장·Ixian Embassy board·카드 3장·Kota 카드면을 직접 판독했고, 아이콘은 `assets/icons`와 대조했다(회색 정육면체 = troop, 초록 줄무늬 카드 = draw, 황갈색 벽 + 붉은 파편 = Shield Wall 파괴, 흰 X 검 = Combat 아이콘, 후드 원기둥 = Spy with Deep Cover). 룰북 pp. 6-7·12는 `scripts/prepare_official_rules.py --source bloodlines`의 working copy에서 인용했다.
- 설계: Acquire Tech는 Landsraad 방문의 자유 순서 효과(`BOARD_ICON_TECH`, Commander 키와 같은 방식)와 카드 할인 frame(`tech_acquisition`) 두 입구를 하나의 provider가 처리하고, 획득 세부 선택(진영·Intrigue/draw·trash할 Spy·Shield Wall)은 새 frame 없이 `acquire_tech`의 인자로 둔다. 새 frame은 `tech_acquisition`·`tech_choice`(Forbidden Weapons)·`tech_secret_project`(Kota) 셋. Kota의 Secret Project tile은 후보 목록에 한 장 더 붙고 `tech_cost`가 1을 뺀다.
- 엔진 패턴(추가): (1) 다른 효과의 해결 도중 개인 덱 reshuffle chance frame을 밀면 호출자가 최상위 frame을 덮어써 깨진다(계약 완료 안의 CHOAM Transports draw가 소크에서 적발) — 그런 draw는 좌석의 `tech_cards_owed`에 빚으로 적고 엔진 hook `draw_owed_tech_cards`가 전이 뒤 뽑는다; Suspensor Suits의 배치도 같은 방식(`suspensor_owed` → `deploy_suspensor_troops`). (2) 대기열로 여는 frame은 앞 항목이 끝났는지 확인해야 한다 — `navigation_play_is_queued`가 그러지 않아 Panopticon의 Endgame Influence 3연속 획득이 같은 Navigation 카드를 두 번 play했다(OQ-012 재검토·OQ-039 문서대로 직렬화). (3) 인쇄 조건을 Command (6+) 판정에 넣을 때 카드 밖 Persuasion(Skill·Navigation·tile)도 합계에 든다(OQ-043; Charismatic의 이전 동작 변경).
- 판정: OQ-040(Endgame tile 효과는 Intrigue window 전), OQ-041(Secret Project tile은 보유 수에 미포함, 본 기억은 관측 밖), OQ-042(Suspensor의 "자기 turn"과 부족분 소멸), OQ-043(Command 합계 범위), OQ-044(Forbidden Weapons·Panopticon·Plasteel Blades·Spy Drones 세부). 모두 project convention.
- 관측 v9(+109: 전역 24, 좌석당 21, 관측자 1), codec v91(tech 카탈로그에만 템플릿 추가; Navigation Chamber 할인은 `agent_turn`의 `discount` 인자 변형). Kota는 `LeaderDefinition.tech_only`로 `leaders_for_choam(..., tech_module=)` 필터에 들어가며 setup 검증·draft pool·codec `pick_leader`·sweep/tournament 회전이 같은 필터를 쓴다.
- 검증: pytest 1,279(신규 `test_tech.py` 58건 + Navigation 1건), Ruff, mypy; `--tech-module` 소크 random `--rotate-leaders` 200판, heuristic 100판, draft 100판(모두 `--soundness-interval 25`) 실패 0. 비공개 에셋 저장소에 Kota의 content id 커밋(`43c25fc`, 미push).
- 프로세스 교훈: 트리 전체 `ruff format`으로 무관한 69개 파일이 바뀌어 되돌렸다(`lessons.md` 2026-09-07 항목). 포매터는 새 파일에만 파일 이름을 지정해 쓴다.
- 사용자 검토(같은 날 밤): OQ-041·043 확인, OQ-044 재판정(Forbidden Weapons·Panopticon의 Reveal 효과를 시작 시 강제 frame이 아니라 Reveal frame 행동 `choose_tech_strength`/`choose_tech_trash`/`place_tech_spy`로 두어 순서를 고르게 함), 그리고 **OQ-045**(사용자 판정): Reveal turn의 troop recruit·Intrigue draw·자원·고정 진영 Influence 획득을 각각 소유자의 행동 `recruit_reveal_troops`/`draw_reveal_intrigue`/`gain_reveal_resources(solari, spice, water)`/`gain_reveal_faction_influence(faction)`으로 분리했다(Persuasion·검만 시작 시 합산)(Reveal frame의 `reveal_pending_gains` 대기 목록; 늦은 조건 성립·Reveal 중 도착 카드·Skill 보너스·Delivery Bay도 같은 목록; 남아 있으면 `finish_reveal` 불가). 이유: supply 상한(OQ-030 소급 없음), Suspensor Suits, Forbidden Weapons의 spice 손실 때문에 시점이 결과를 바꾸며, Immortality의 specimen 반환에도 대비. Agent turn은 OQ-027로 이미 아이콘별 행동이다. 모든 카탈로그에 템플릿 12개(행동 2 + 자원 묶음 6 + 진영 4)가 늘어 **codec v94**(retail 4,366/4,652)이고, 이전 체크포인트의 codec 검사가 거부한다. heuristic은 네 행동을 4.0으로 우선 처리한다.

## 2026-09-07 M12 Bloodlines 슬라이스 1~5 세션 요약 (`bloodlines` 브랜치, 관측 v6→v8)

- 범위(사용자 결정): Tech Module까지 전부, 순서는 출처 등록 + 옵션 골격 + Sardaukar Commander부터. 슬라이스 1(출처·옵션·명세 `rules/bloodlines.md`), 2(Sardaukar Commander·Skill, 관측 v6), 3(Conflict 2장, wild battle icon 매칭), 4(Imperium 25종·Intrigue 16장, 새 아이콘 4종, 관측 v7), 5(Leader 8종, 관측 v8)를 모두 `Play`/`Document` 커밋 쌍으로 올렸다. Tech 전용 카드 3종과 Kota Odax는 슬라이스 6으로 미뤘다.
- 사용자 판정: OQ-031·035(고를 Skill이 없으면 Skill 없이 Commander만 획득 — 처음의 "획득 자체를 막음"에서 같은 날 재판정), OQ-032(Skill strength는 매 step, 전투 중에도 재계산), OQ-036(유닛 손실은 잃는 좌석이 zone·종류 선택, Spy 강제 이동은 옮기는 좌석이 빈 post 선택 — 13 post > 12 Spy라 항상 가능), OQ-037(Into the Fray의 Agent는 공간을 비움), OQ-038(Harkonnen Advisor는 Warmaster에서 "그 troop 1개의 이번 turn 배치"만 뺀 것; garrison에서 troop을 잃으면 정상화). 나머지 OQ-033·034·039와 OQ-012 재검토는 project convention.
- 엔진 패턴: trash 트리거·Influence trigger처럼 다른 효과의 해결 도중 생기는 결정은 frame을 바로 밀지 않고 `GameState`의 대기열(`pending_skill_choices`, `pending_navigation_plays`)에 넣어 엔진의 자동 전이가 연다(직접 밀면 호출자가 최상위 frame을 덮어써 깨졌다). Agent turn 중 retreat는 `combat_deployment.reconcile_deployment_after_retreat`로 배치 카운터를 맞춘다(Chani Signet에서 발견). 상대 좌석의 강제 결정은 시계 방향 순서로 쌓은 frame(`opponent_spy_move`, `opponent_unit_loss`).
- 관측: v6(Commander·Skill 세그먼트, identity 우주 확장), v7(Shigawire 플래그, `contract_trash`), v8(Tactics token, 싸우는 Agent, Twisted 덱 크기, Navigation 잔여·Reveal Persuasion 보너스, 비공개 `private_peeked_card`·`private_navigation_slots`; Twisted 12·Navigation 10이 Intrigue 우주에 추가). codec은 v90 그대로이며 Bloodlines 템플릿은 옵션 카탈로그에만 들어간다(retail 4,354/4,640 불변).
- 검증: pytest 1,221, Ruff, mypy; `--bloodlines` 소크(random·heuristic, `--rotate-leaders`, `--leader-draft`, `--soundness-interval 25`) 슬라이스마다 실패 0. 소크가 잡은 버그: contract 인구 census(`contract_trash` zone), Skill frame 덮어쓰기, Hungry for Spice가 reshuffle과 겹치던 문제, Mohiam의 Spy 아이콘으로 진영 아닌 공간에 간 "visited Faction" 효과, `intrigue_card_given` 이벤트의 카드 노출.
- 에셋: Bloodlines 카드 44장·Leader 8종·Twisted 12·Navigation 10에 content id, Tuek's Sietch 타일 이미지(Dire Wolf 디자인 다이어리)를 비공개 에셋 저장소에 커밋. 카드면·Navigation·Twisted 전사본은 `implementation-audits/leaders.md`·`bloodlines.md`에 실었다.

## 2026-09-06 밤 전투력 단일 값·표시 세션 요약 (`ui-work` 워크트리, 관측 v5)

- 표시 정리: 좌석 패널의 검 아이콘은 인쇄된 전투력 아이콘이므로 전투력 숫자를 보여주고, Conflict 배치 유닛은 "Conflict" 라벨 칸에 troop·sandworm 아이콘으로 따로 둔다. 보드의 전투력 토큰은 네 좌석 모두 항상 트랙에 있다: 0이면 1·11 왼쪽 큰 네모(`STRENGTH_ZERO_BOX`, 2×2), 1~20은 인쇄 숫자 칸, 21 이상은 검은 뒷면 + `+20` 배지로 20을 뺀 칸(23 = 3번 칸의 +20 토큰) [Main p. 12].
- 사용자 질문 "병사를 보내도 전투력이 바로 반영되지 않는다": 엔진이 규칙대로 Reveal turn에만 marker를 세우고 있었다([Main p. 12], `combat-and-round-end.md` 8·11행). 처음에는 관측에 파생 필드 `combat_strength_now`를 두는 절충(관측 인코딩 불변, 체크포인트 유지)을 제안·구현했으나, 사용자가 Bloodlines(Sardaukar Commander)를 고려해 **단일 값**을 결정했다: `combat_strength`를 Agent turn부터 매 step 갱신하고 Reveal은 sword만 더한다.
- 구현: 새 잎 모듈 `rules/strength.py`(`units_strength` 공식, `reveal_in_progress`(REVEAL 프레임 소유 여부), `refresh_pre_reveal_strength`). 엔진이 `_apply_legal`/`_apply_chance` 끝에서 pass를 돌려 라운드 시작·플레이어 턴 단계에서 Reveal을 시작하지 않은 좌석의 값을 유닛 기준으로 맞춘다(Combat부터는 기존 증분·정리 로직). `begin_reveal_turn`은 같은 공식 + sword. 처음 "기존 값 + sword"로 썼다가 손으로 만든 상태를 쓰는 테스트 41건이 깨져 공식 직접 사용으로 바꿨고, Combat 단계의 손수 만든 상태(has_revealed 없음) 9건은 pass를 턴 단계로 제한해 해결했다. `combat`↔`reveal_turn` 순환 import 때문에 도우미를 별도 모듈로 뺐다.
- 관측 v5: 레이아웃·길이 불변, `combat_strength` scalar의 의미만 변경. `rl-environment.md`, README, `combat-and-round-end.md` 구현 메모 갱신. 기존 v4 체크포인트(200 iteration 것 포함)는 로더가 거부한다.
- 검증: pytest 1,101(신규: 배치 2명 → 즉시 4, 회수 → 0), Ruff, mypy, heuristic sweep 120판(`--soundness-interval 25`, 양 룰셋) 실패 0. 브라우저에서 AI 좌석 배치 직후 토큰이 4번 칸으로 옮겨지는 것을 확인.

## 2026-09-06 M11 UI 개선 세션 요약 (`ui-work` 워크트리)

- 작업 방식: `.claude/worktrees/` 아래의 git 워크트리에서 `ui-work` 브랜치로 진행하고 master에 합칠 때 이 문서를 한 번만 갱신했다(사용자 지시). 워크트리는 `.venv`가 따로 있으므로 `uv sync --extra rl --extra ui --extra train`을 그 안에서 다시 하고, `assets` symlink는 상대 경로가 깨지므로 `/Users/cs/Workspace/tabletop-ai/Dune-Imperium-assets` 절대 경로로 건다. 브라우저 확인은 Claude Code의 미리보기 서버(`.claude/launch.json`, 포트 8765, 저장 파일은 세션 임시 폴더)로 했다.
- 호버 팝오버(`hoverPopover`/`pinPopover`): 카드 이미지·칩·Leader 초상·보드 hotspot에 마우스를 올리면 0.12초 뒤 상세 팝오버가 뜨고 벗어나면 닫힌다. 클릭은 고정(Escape·바깥 클릭으로 해제). 호버 팝오버는 `pointer-events: none`이라 겹친 카드를 가리지 않는다.
- 정적 파일 재검증: `index.html`과 `/static`에 `Cache-Control: no-cache`(ETag 재검증)를 붙여 편집한 `app.js`가 일반 새로고침으로 반영된다(브라우저 휴리스틱 캐시가 예전 파일을 내주던 문제; `tests/server/test_app.py` 회귀).
- 보드 슬롯(`display/board_layout.py`, `catalog.tracks`): `CONTRACT_SLOTS`(Landsraad 아래 두 칸, face-up contract + bank 장수 배지), `CONFLICT_DECK_SLOT`·`CONFLICT_SLOT`(Deep Desert 아래 흐릿한 세로 틀 두 개 — 위가 face-down 덱, 아래가 이번 라운드 카드; 처음에 전투력 트랙 옆 네모와 사분면 원 안 틀로 두 번 잘못 잡았다가 사용자 지적으로 확정). 관측 `PlayerView.conflict_deck_size`를 추가해 덱을 뒷면 카드 + 장수로 그린다(RL 인코딩은 불변). 스캔이 있으면 하단 스트립의 Conflict·Contracts 항목은 사라지고, Shaddam의 set-aside Sardaukar contract만 별도 스트립에 남는다.
- 병력 표시: 전투 영역 모서리의 괄호 원 네 개가 garrison(`GARRISON_POINTS`), 가운데 십자로 나뉜 네 칸이 Conflict 배치 칸(`CONFLICT_QUADRANTS`, 재측정)임을 사용자가 확인해 주었다. 원에는 점선 칩으로 garrison 수, 칸에는 실선 칩으로 배치 병력·샌드웜·전투력을 그린다.
- 레이아웃: 공용 카드 영역(Imperium Row·Reserve·draft·set-aside·Intrigue discard)은 보드 오른쪽 세로 열(`fit-content(22%)`, 최소 190px)로 옮겨 넓은 화면에서 보드가 높이를 다 쓴다. 오른쪽 패널은 `#side-main`(결정·행동·순위·검토·공개)과 `#side-log`(행동 로그) 2열(`clamp(380px, 34vw, 760px)`); 1400px 이하는 다시 쌓고 1100px 이하는 카드 열도 보드 아래로 내린다.
- 행동 목록 포커스(`focusActions`/`clearActionFocus`): 카드·공간 클릭으로 선택지가 여럿이면 해당 행동을 맨 위로 옮기고 노란 발광, 나머지는 흐리게, "전체 보기"로 복원.
- 행동 로그 턴 카드(`logGroups`/`turnCard`/`neutralCard`): 한 좌석의 연속 단계를 좌석 색 카드(Leader 이름·AI 종류·Agent 공간·단계별 설명과 이벤트·관련 카드 이미지)로 묶는다. 턴을 닫는 단계(`finish_agent_turn`/`finish_reveal`/`pass`) 뒤와 `pick_leader`는 카드를 끊는다. `NEUTRAL_EVENT_KINDS`(draft 미사용·Conflict 공개·Combat 보상/승리/정리·Maker spice·Agent 회수·Endgame·게임 종료)와 다른 좌석 대상 이벤트, chance 단계는 점선 "게임 진행" 카드(제목: 게임 준비·전투 해결·라운드 N 시작 등)로 분리한다. 내가 마지막으로 행동한 뒤 들어온 카드는 노란 테두리로 표시하고 그리로 스크롤하며, 카드에 마우스를 올리면 관련 공간·카드가 보드에서 하늘색 스포트라이트(`setSpotlight`)로 켜진다. `card_acquired`가 card_id·instance_id를 둘 다 실어 이미지·이름이 두 번 나오던 것은 인쇄 카드 기준으로 합쳤고, Combat 보상 줄의 0 항목은 생략한다. 자동으로 넘어가는 오버레이 재생 방식은 만들었다가 사용자 피드백("다시 확인하기 힘들다")으로 로그 카드 방식으로 대체했다.
- 검증: pytest 1,100, Ruff, mypy(master 합류 뒤). 브라우저에서 각 항목을 새 게임으로 직접 확인했다.

## 2026-09-06 M10 슬라이스 1 세션 요약 (학습 루프, 첫 체크포인트, 교착 수정)

- 사용자 결정: 이 Mac(Apple M4 10코어, 16GB)에서 시작하고 규모는 RTX 3080 PC에서 키운다. 병목은 GPU가 아니라 Python 엔진(수집)이라 코어 수가 중요하다는 판단. PyTorch 2.14를 새 `train` extra로 추가(표준 동기화 명령이 `--extra train`까지 포함하도록 README·CLAUDE.md·이 문서 갱신).
- 구현: `training/network.py`(log1p 입력 → MLP 512×512 → 4,354 masked logits + value; 불법 행동 logit −1e9), `training/checkpoint.py`(관측 v4·codec v89·룰셋·hidden 기록, 불일치 거부), `training/torch_policy.py`(`TorchBatchPolicy` 표본/greedy, `NetworkAgent` greedy, `checkpoint:<경로>` 로더를 프로세스별 캐시), `training/learner.py`(REINFORCE + value baseline, advantage 정규화, entropy 보너스, grad clip), `training/loop.py`(`TrainConfig`·`train`: 수집 → learner 좌석 step만 선택 → 갱신 → JSONL → `latest.pt`+번호 체크포인트 → 주기적 대회 평가; 학습 seed는 2,000,000+seed×1,000,000부터), `cli/train.py`. registry에 `checkpoint:` 이름 지원(`is_agent_kind`; worker 프로세스가 파일을 직접 로드).
- greedy 순환 방지: 되돌릴 수 있는 행동 쌍(deploy/withdraw, defer/resume)이 있어 학습 전 argmax는 turn을 못 끝냈다(30,000 step 한도까지 반복). `_CycleGuard`가 같은 라운드 안에서 동일 관측(관측에는 revision이 없어 되돌린 수는 같은 바이트)에서 이미 고른 행동을 다음 방문 때 가린다.
- **엔진 교착 발견·수정**(`d9f11a5`): self-play 표본 정책이 seed 4000098에서 "합법 행동 없는 플레이어 결정"에 도달했다. Steersman으로 Imperial Privilege 방문 → Intrigue 슬롯 거절(그때는 다른 Agent가 있어 recall 보류) → Agent box의 recall로 그 Agent를 회수 → Imperial Privilege의 의무 recall에 대상이 없는데 아무 행동도 없었다. OQ-023의 "해결 시점 판정, 대상 없으면 recall만 건너뛰고 draw"를 매 전이 뒤 hook으로 적용해 해결(open-questions.md OQ-023 보강 항목). 7,000판 random 소크가 못 찾은 상태를 학습 정책이 4 iteration 만에 찾았다 — 학습 실행은 소크의 연장이기도 하다.
- 결과: 위 "다음 구현 순서" 2와 `docs/evaluation/baseline-2026-09-06.md` 5절. 처리량은 수집 약 3,100~3,500 decisions/s(단일 프로세스, torch 추론 포함), 갱신 약 1초/iteration(2만 step).
- 검증: pytest 1,096(신규 8건 torch 계열 + 교착 회귀 2건), Ruff, mypy.
- 이어서 학습(같은 날 밤): champion에서 `--resume` 100 iteration(수집 586초 + 갱신 207초) → 200 iteration 체크포인트. 100 iteration champion 3명 상대 35%, heuristic 상대 91%. 대회 중 seed 19에서 "player has no Spy in supply" 오류: Lady Margot Signet의 recall-first Spy 배치가 recall 직후 supply를 다시 보지 않아, 같은 turn의 Distraction trigger가 그 Spy를 쓴 뒤에도 배치가 제시됐다. 같은 패턴의 제공자 5곳(Leader Signet·Feyd track·acquisition·Contract·Reveal)을 해결 시점 판정으로 고쳤다(`[Main pp. 11, 20]`, `tests/unit/rules/test_leader_abilities.py`).
- 두 번째 체크포인트(같은 날 밤, 수정 후 100 iteration × 64판, 수집 615초 + 갱신 219초): heuristic 3명 상대 89%(평균 순위 1.14), 6분 체크포인트 3명 상대 61%, rollout 3명 상대 67%. 루프 안 평가는 25/50/75/100 iteration에서 73/77/75/96%. 서열: random < heuristic < rollout < 6분 체크포인트 < 14분 체크포인트. 그 뒤 sampling 정책에도 `_CycleGuard`를 적용해(`cf24f35`) 되돌리기 반복이 수집에서 사라지도록 했다(이 체크포인트에는 미적용; 다음 실행에서 게임당 결정 수를 비교한다).
- 슬라이스 2(같은 날 밤): `training/collect.py` `Collector` — spawn worker마다 CPU 네트워크 사본을 두고 lockstep 러너로 chunk를 돌려 learner step만 int16 관측 + packbits mask `.npz`로 반환(가중치는 iteration당 파일 1개). 8 worker 약 8,500 decisions/s(단일 3,600; 전송 축소 전후 차이 없음 — 병목은 worker당 엔진 속도와 M4의 성능/효율 코어 혼합으로 보인다). 첫 긴 실행(150 iteration × 64판)이 41 iteration에서 죽었다: 정책이 deploy/withdraw·defer/resume 반복을 학습해 게임당 결정이 680→1,793으로 늘었고, learner가 전체 배치(11만 행) logit을 한 번에 만들었다. 수정(`3a028fe`): 값 계산 minibatch 분할, `apply_step_penalty`(결정당 0.0005를 같은 좌석의 이후 결정 수만큼 종료 보상에서 차감; 환경 보상은 그대로 종료 보상뿐), 학습 게임 상한 4,000 결정. 감시 교훈은 `lessons.md`.

## 2026-09-06 M9 슬라이스 3 세션 요약 (lockstep self-play 러너, M9 완료)

- `training/policy.py`: `PolicyRequest`(game, seat, state, view, legal_actions, 병렬 `legal_indices`, int32 관측 v4, int8 mask)와 `BatchPolicy.act(requests) -> 인덱스 시퀀스`. `RandomBatchPolicy`(mask 표본)와 `AgentBatchPolicy(kind, seed)`(registry baseline을 (game, seat)마다 한 인스턴스로 구동; `StateAgent`면 요청의 state로 검색).
- `training/selfplay.py`: `SelfPlayRunner(config, max_steps, record)`. `run(policies, specs)`는 spec마다 `engine.reset(seed)`와 seed 기반 `ChanceResolver`를 두고, 매 라운드 chance 해결 → 대기 게임마다 요청 생성 → lineup의 좌석 정책 이름으로 묶어 정책당 한 번 `act` → 합법 인덱스 검증(불법이면 `ValueError`) → 적용. FINISHED면 `final_standings`로 승자 +1, 나머지 −1/3(`pettingzoo_env`의 상수 재사용), `max_steps` 초과면 truncated·보상 0·rank 0. `Episode`(seed, lineup, rewards, ranks, VP, rounds, decisions, steps)와 `stack_episodes` → `TrainingBatch`(observations [T,2022] int32, masks [T,4354] int8, actions int64, seats int8, returns float32 = 행동한 좌석의 종료 보상, episode_ids).
- CLI `dune-imperium-selfplay --games N --policy random-batch|random|heuristic|rollout [--choam --no-record]`. 처리량: 32판 lockstep 단일 프로세스 약 4,900 decisions/s(random-batch·heuristic 모두; 엔진 apply가 지배적이라 정책 비용은 보이지 않는다). 기록 유무는 처리량에 영향이 없다.
- 검증: pytest 1,086(신규 6건: zero-sum 보상·궤적 일관성·재현성, stack 배열, lineup 라우팅과 batch 묶음, truncation·불법 인덱스·검증 오류, baseline 어댑터(rollout 포함), CLI), Ruff, mypy.
- M9 완료 판정: 완료 조건 "버전이 다른 agent들의 재현 가능한 평가 행렬과 성능 보고서"는 대회 도구가, "정책 추론만 batch하는 self-play 러너"는 이 슬라이스가, baseline 세 종류(random/heuristic/rollout)는 registry가 충족한다. 다음은 M10(위 "다음 구현 순서" 2).

## 2026-09-06 M9 슬라이스 2 세션 요약 (rollout baseline)

- 문제: agent 계약은 `PlayerView` + 합법 행동만 받아 앞을 내다볼 수 없다. `agents/base.py`에 `StateAgent`(runtime_checkable Protocol, `choose_action_with_state(state, observation, legal_actions)`)를 추가하고 `simulation/runner.py`의 `_advance_one_decision`과 대회 계측 래퍼가 그 경로를 쓰도록 했다. 정직성은 관례로 지킨다: 구현은 검색 전에 숨겨진 존을 determinize해야 하고 관측자가 볼 수 없는 정보를 읽지 않는다.
- `agents/determinize.py`: 관측자의 덱 순서, 상대의 비공개 손패+덱 풀, 상대 보유 Intrigue+Intrigue 덱 풀(해결 중인 Intrigue는 공개라 유지), Imperium 덱, contract bank, Conflict 덱을 RNG로 다시 나눈다. `observe_state(world, observer) == observe_state(state, observer)`와 카드 census 보존을 테스트로 고정.
- `agents/rollout_agent.py`: 합법 행동이 2개 이상일 때만 검색. heuristic 점수 상위 `candidates`(기본 6)개를 남기고, `rollouts`(기본 2)회 determinize한 세계마다 각 후보를 적용한 뒤 heuristic 정책으로 현재 라운드 끝(`horizon_rounds`=1, Combat 포함)까지 진행해 `position_value`(VP 10점 가중, Influence·Alliance·Swordmaster·High Council·자원·병력·카드 수·Spy·Control·contract; 가장 강한 상대와의 차이; FINISHED면 순위 기준 100/70/40/10)를 평균한다. 상태 없이 호출되면 heuristic처럼 답한다. registry 이름 `rollout`.
- 비용: 한 step 약 0.12ms(legal 0.02 + observe 0.015 + apply 0.08), 라운드 rollout 약 60 step → 결정당 약 25ms, 한 판 약 4초(rollout 좌석 1개). 8 worker 100판 약 2분.
- 결과(`docs/evaluation/baseline-2026-09-06.md` 4절): heuristic 3명 상대 100판 승률 48%, 평균 순위 1.90, VP margin +1.5, 좌석별 40~56%, 불법 행동 0. M9의 "heuristic보다 유의미하게 강한 search baseline" 조건을 만족한다.
- 검증: pytest 1,080(신규 6건: determinize 뷰 보존·census·관측자 검증, 값 함수, 러너의 StateAgent 경로, rollout 선택·재현성·단일 행동 단락, 러너 완주 구간), Ruff, mypy.
- 남은 것: self-play 러너(M10 직전), 선택 과제로 rollout 강화와 서버 AI 좌석 연결(위 "다음 구현 순서").

## 2026-09-06 M9 슬라이스 1 세션 요약 (대회 도구 + 첫 기준선)

- 사용자 지시 "최선의 순서로 시작": M9를 (1) 대회 도구·지표 → (2) rollout baseline → (3) self-play 러너 순으로 진행하기로 했다(러너는 M10 학습 정책의 추론 인터페이스가 정해진 뒤 batch 설계를 확정하는 편이 낫다).
- `agents/registry.py`: 이름→factory(`random`, `heuristic`)와 `make_agent`. 새 baseline은 여기 등록하면 대회·보고서가 이름으로 다룬다.
- `evaluation/tournament.py`: `MatchSpec`(seed·정책 seed·좌석별 agent·룰셋·Leader roster), `tournament_specs`(lineup을 4좌석으로 순환 채움 → 서로 다른 순환 좌석 회전 × 룰셋 × seed 범위; `--rotate-leaders`는 sweep과 같은 파생), `play_match`(`run_policy_game` 위에 `_MeteredAgent`로 결정 수·결정 시간·불법 행동 계측; 불법 행동은 세고 첫 합법 행동으로 대체), `run_tournament`(ProcessPoolExecutor). 같은 seed의 회전들은 Leader·덱·first player가 같고 좌석만 다르다.
- `evaluation/report.py`: `summarize` → agent별 승률(공식 최종 순위 1위)·평균 순위·평균 VP·VP margin(테이블의 다른 세 좌석 평균 대비)·선공 성적·결정 수·불법 행동·ms/decision, 좌석별·Leader별 분할; `render_markdown`, `summary_to_json`. CLI `dune-imperium-tournament --agents a,b[,c,d] --games N --ruleset base|choam|both --rotate-leaders --workers W --json --markdown`.
- 첫 기준선(`docs/evaluation/baseline-2026-09-06.md`): heuristic 1 + random 3(100판) heuristic 95% 승률·평균 순위 1.06·VP margin +5.7; heuristic 미러 400판은 좌석별 22.8~26.8%, 선공 25.0%로 편향 없음, Leader별로 Gurney 38%/Staban 17%(heuristic 편향); random 미러 200판 대조. 불법 행동 0. 8 worker로 약 60 games/s.
- 검증: pytest 1,074(신규 6건: lineup·회전, spec 교차, match 계측·재현성, 불법 행동 계측, 집계·JSON·Markdown·CLI, 잘못된 agent 이름), Ruff, mypy.
- 다음: rollout/search baseline(위 "다음 구현 순서" 1-(2)).

## 2026-09-06 OQ-029 검토·recruit 부족분 이벤트 세션 요약 (OQ-030 판정)

- 사용자가 remote 세션이 끊겨 확인하지 못한 2026-09-05의 OQ-029 커밋 3개를 검토했다: 판정 문서·엔진·테스트가 사용자 판정(turn 안 자유 회수·분할, 소비된 조건은 Spy 배치와 Intrigue play를 먼저 되돌려야 함)과 일치한다. 스크립트로 Distraction 사용→회수 불가, 되돌리기(Spy 배치·Intrigue play 모두 되돌리기 가능)→거절→회수 재개, 저장 직렬화의 `units_deployed_committed` 포함을 확인했다. 효과가 직접 배치한 troop(Intrigue `deploy_intrigue_troops`, Reveal 배치, sandworm)이 회수 대상에서 빠진 것은 "카드 효과 해결 결과"라 판정 범위 밖으로 둔 것이며 사용자에게 설명했다(필요하면 OQ-029 확장).
- 사용자 질문 "supply가 비었을 때 recruit": 엔진은 해결 시점에 `min(supply, count)`만 옮기고(`effects.recruit_troops`, `[Main p. 10]`) 부족분은 조용히 소멸했다. 사용자 요청으로 모든 recruit 경로(보드 아이콘, Sietch Tabr, Agent box 7종, Arrakis Revolt acquire, contract 보상, Intrigue DSL, reveal-acquisition trigger, Reveal 시작·늦은 Reveal·늦은 이득, Gurney/Feyd/Shaddam Signet, Combat 보상, Emperor track 보상)에 공개 이벤트 `troops_recruit_short`(player·requested·recruited·short)를 추가했다. 규칙 동작 변경 없음. UI 라벨 `병력 recruit 부족 (supply 없음)`. `tests/unit/rules/test_recruit_shortfall.py` 7건.
- 사용자 질문 "turn 중에 supply가 다시 생기면 앞서 못 한 recruit는?": 공식 문서 침묵이라 OQ-030 `OPEN`으로 등록했다(판정 대기; 엔진은 현재 구현 유지). 콘텐츠 감사 결과 turn 중 garrison·Conflict의 troop을 supply로 돌려보내는 효과는 없고(RetreatTroops는 Conflict→garrison, Conflict→supply는 Combat 정리뿐), turn 중 supply 증가 경로는 Lady Jessica의 Other Memories뿐이라 자유 순서로 먼저 해결하면 손실이 없다. 사용자 지적으로 확장 사례를 덧붙였다: Immortality 프로모 Piter, Genius Advisor의 Agent box "Lose a troop"(원본 룰북 p. 16 용어집: supply로 돌려보냄)과 specimen 왕복이 Agent turn 중 supply 증가 경로이며, Immortality 룰북 p. 8은 recruit 전에 specimen을 미리 되돌려 두라고 안내한다. 판정 후보 (A) 해결 시점·소급 없음 / (B) 부족분 늦은 지급 중 사용자가 (A)를 확정해 OQ-030 `DECIDED`, `player-turns.md` 갱신, 소급 없음을 고정하는 테스트 1건 추가(엔진 변경 없음). 공식 PDF 원문은 scratchpad에서만 확인했고 저장소에 넣지 않았다.
- 검증: pytest 1,068, Ruff, mypy.
- 미push: 2026-09-05의 3개 + 이 세션의 커밋이 `origin/master`에 아직 없다. 다른 머신에서 이어가려면 먼저 push한다.

## 2026-09-05 OQ-029 판정 구현 세션 요약 (Combat 배치 회수·분할, codec v89)

- 사용자 판정: 이번 Agent turn에 Combat space에 배치한 병력은 그 turn 안에서 제한 없이 되돌리거나 다시 배치할 수 있어야 한다(배치 뒤 draw한 카드를 보고 수를 줄이는 것이 자연스럽고, draw로 되돌리기가 닫혔다는 이유로 못 하는 것은 지나치게 엄격하다). 예외는 배치 수를 조건으로 이미 사용한 효과(Distraction의 "3개 이상 배치" Spy)로, 그런 경우 Spy 배치와 Intrigue play를 먼저 되돌린 뒤 재배치해야 한다. `open-questions.md` OQ-029 `DECIDED`(project convention), `player-turns.md` 갱신.
- 엔진(`rules/combat_deployment.py`): `deploy_troops(count)`는 이번 turn의 기본 배치에 `count`개를 **추가**(1..한도)하고 frame을 유지, `withdraw_troops(count)`는 이번 turn 기본 배치분(frame context `combat_troops_deployed`)에서 되돌리되 `PlayerState.units_deployed_committed` 아래로는 못 내리며, `finish_agent_turn`은 다른 보류 효과(`agent_turn_has_other_pending_effects`, `effects.py`)가 없을 때만 제시되어 turn을 닫는다. 순한도는 "recruit한 troop + garrison 2개" 그대로(`[Main p. 10]` `[FAQ p. 4]`). 배치가 불가능한 turn(비Combat space, Shaddam Signet)은 이전처럼 자동 종료. Distraction Spy 배치(`intrigue_triggers.py`)가 `units_deployed_committed`를 카드 최소값으로 올리고, 거절은 아무것도 소비하지 않는다. 효과가 직접 배치한 troop(`deploy_intrigue_troops`, Reveal 배치, sandworm)은 회수 대상이 아니다.
- codec v89: `deploy_troops` 1..12(0 제거) + `withdraw_troops` 1..12 + `finish_agent_turn`(기본 4,354, CHOAM 4,640, 프로모 4,454/4,740). heuristic agent: `finish_agent_turn` 0.5, `withdraw_troops` −10(decline/pass보다 낮아야 Treacherous Maneuver 같은 보류 선택 앞에서 회수↔배치를 반복하지 않는다 — 처음 구현에서 −1로 두었더니 `test_leader_draft_game_runs_to_finished_and_replays[True]`가 30,000행동 한도에 걸렸다). legal action 순서는 배치 → Intrigue → finish → 회수로 두어 "첫 번째 행동만 고르는" 서버 테스트 스크립트도 끝난다. UI 라벨 `병력 회수`/`Agent turn 종료`, 이벤트 `troops_withdrawn`/`agent_turn_finished`.
- 서버 테스트의 seed 14 revision 고정값은 AI 좌석의 Combat turn마다 finish 단계가 하나씩 늘어 +3 이동했다(사람 첫 결정 8→11).
- 검증: pytest 1,060(신규 6건: draw 뒤 회수, 분할 배치와 순한도, 이번 turn 기본 배치만 회수, committed 하한, finish 대기, Distraction 사용/거절), Ruff, mypy. 소크: random 룰셋당 150판(`--rotate-leaders --soundness-interval 25`, 300/300)·heuristic 60판(120/120)·프로모 60판(120/120) 실패 0.
- 남은 경계: 로컬 UI는 `finish_agent_turn` 뒤에도 기존 turn 종료 확인(되돌리기 창)을 한 번 더 거친다(이중 확인이지만 되돌리기 보호 목적이라 유지). 효과가 직접 배치한 troop의 회수 여부는 판정 범위 밖(필요하면 OQ-029 확장).

## 2026-09-04 조건 판정 시점 정리 세션 요약 (OQ-028)

- 사용자 지적: 미룬 Reveal 선택을 되가져올 때 조건이 없으면 소멸시켰는데, 같은 Reveal 안에서 카드 획득(Spy 배치)이나 Intrigue로 조건이 다시 성립할 수 있으니 소멸이 아니라 다시 가능해야 하고, "원래는 불가능했는데 플레이어의 선택으로 가능해지는 조건"을 전부 확인하라. 감사 결과와 판정은 OQ-028(`DECIDED`)에 기록했다.
- **Reveal 선택형 효과(`f78a4c9`)**: 조건이 거짓인 선택은 되가져올 때 소멸하지 않고 미룬 큐에 남는다. `resume_reveal_choice`는 지금 조건이 성립하는 종류만 제시하고(`_available_deferred_choices`), 시작 시점·늦은 도착 시점에 조건이 거짓인 선택도 frame 대신 큐에 넣으며, `finish_reveal`은 성립하는 미룬 선택이 없을 때만 제시되고 끝까지 성립하지 않은 선택은 `reveal_choice_unavailable`로 소멸한다. 테스트: In High Places의 두 Spy 회수가 Wheels Within Wheels의 Reveal Spy 배치 뒤에 열린다 / Spy Network 회수로 조건이 사라지면 재개 불가·finish 가능.
- **Agent box 조건(`cf8cb46`)**: `_agent_effect_is_available`는 이제 방문 space 속성과 Faction Bond만 배치 시점에 판정한다. Influence 문턱(Prepare the Way·Hidden Missive·Maker Keeper·Wheels), 자원·손패·Intrigue 비용(Ecological Testing Station·Smuggler's Haven·Corrinth City·Junction HQ·Price is No Object·Arrakis Revolt·Space-time Folding·Guild Envoy·Captured Mentat·Guild Spy·Treacherous Maneuver), Alliance(Branching Path — provider가 해결 시점에 판정), sandworm(Leadership — 없으면 unavailable)은 해결 시점에 판정한다. 테스트: Wheels가 Spy 아이콘으로 Dutiful Service에 가서 Faction 단계로 Emperor 2가 된 뒤 Solari 아이콘 지급 / Branching Path가 Espionage의 Faction 단계로 Alliance를 얻은 뒤 trash 지불 / Sietch Tabr water로 Ecological Testing Station 지불 / Hagga Basin sandworm 뒤 Leadership draw. 사용자 체감: 조건이 안 되는 화살표 효과도 이제 "decline" 한 번을 눌러야 한다(그 전에 다른 효과로 조건을 만들 수 있으므로).
- **Reveal 자동 조건부 이득(`5ddb460`)**: Reveal frame이 지급한 효과를 `granted_reveal_effects`로 기록하고, dispatcher pass `grant_late_reveal_effects`(leader passive 직후, 자동 전이 전)가 매 전이 뒤 조건이 새로 성립한 효과를 한 번 지급한다 — Bene Gesserit Operative(Spy 2개), Paracompass(High Council/Swordmaster), Fremen Bond 카드들(늦게 도착한 Fremen 카드), Smuggler's Haven(Maker 감시), Interstellar Trade(완료 contract 증분). 늦은 도착(`_late_reveal_one_card`)도 기록한다. 현재 콘텐츠에는 동적 조건 뒤에 sword가 있는 효과가 없어 sword 경로는 구조만 갖췄다.
- 검증: pytest 1,054, Ruff, mypy. 커밋 트리 소크: random 룰셋당 150판(`--rotate-leaders --soundness-interval 25`, 300/300)·heuristic 60판(120/120)·프로모 60판(120/120) 실패 0.

## 2026-09-04 Reveal 선택 효과 순서 자유화 세션 요약 (codec v88)

- 사용자 지시("Reveal 선택 효과 순서 자유화도 이어서")로 심야 작업의 남은 항목을 구현했다. 설계: 직렬 `REVEAL_CHOICE` frame 구조는 유지하되, (1) 맨 위 선택 frame에 `defer_reveal_choice`(인자 없음)를 제시해 그 frame을 빼고 Reveal frame context `deferred_reveal_choices`("card|effect" 목록)에 넣는다 — 그러면 다음 선택 frame이나 Reveal frame(획득·Intrigue play·Leader Reveal 능력)이 드러난다; (2) Reveal frame에 미룬 종류마다 `resume_reveal_choice(effect=<kind>)`를 제시해 가장 오래된 해당 선택을 `_build_reveal_choice_frame`으로 다시 올린다(`reveal_choice_resumed` 표시 → 재미루기 불가, 순환 없음); (3) 되가져올 때 `_reveal_choice_effect_is_available`로 가용성을 재판정해 조건이 사라진 선택은 `reveal_choice_unavailable`로 소멸; (4) 이미 시작한 선택(`reveal_spy_recalled`)은 미룰 수 없음; (5) `legal_finish_reveal_actions`는 미룬 선택이 남아 있으면 비어 있다. 늦은 도착(OQ-015(c))의 `_insert_after_reveal_frame`은 그대로다. 이벤트 `reveal_choice_deferred`/`reveal_choice_resumed`/`reveal_choice_unavailable`.
- codec v88: 인자 없는 `defer_reveal_choice` 1 + `resume_reveal_choice` 11(기본 4,342, CHOAM 4,628, 프로모 4,442/4,728). heuristic agent는 두 행동에 −5점을 줘 카드 순서대로 해결한다(random 정책은 미루기·재개를 섞어 쓰되 재미루기 금지로 항상 끝난다). UI 라벨과 서버 `detail`(재개 행동은 선택 frame의 prompt 문장)을 붙였다.
- 검증: pytest 1,045(신규 3건: 미루기→다른 선택 먼저→Reveal frame에서 finish 보류·재개→재미루기 불가→마무리; 시작한 Spy 배치는 미루기 불가; 조건이 사라진 선택의 소멸), Ruff, mypy. 커밋 트리 소크: random 룰셋당 150판(`--rotate-leaders --soundness-interval 25`, 300/300)·heuristic 60판(120/120)·프로모 60판(120/120) 실패 0.
- 남은 경계: 미룬 선택 frame을 되가져올 때 frame_id는 원래와 같다(되돌리기·replay에 영향 없음). Beast's Spoils·Arrakis Revolt의 Agent box 단위는 OQ-027대로 유지.

## 2026-09-03 심야 자율 작업 세션 요약 (사용자 부재 중 5건)

사용자가 자리를 비우며 남긴 5건을 순서대로 처리했다. 각 항목의 상태:

1. **카드 효과 아이콘 분리 — Agent box 완료, Reveal box 미완.** 감사 결과 Agent box에서 독립 아이콘이 묶여 있던 카드 9종을 OQ-027 모델로 분리했다(`b86a5c1`, codec v87): 배치 시 대기 — Hidden Missive(troop·card), Steersman(card·recall), Maker Keeper(water·spice), Wheels Within Wheels(Solari·spice), Dangerous Rhetoric(Influence 선택·"Trash this card."; 카드면 확인); 화살표 비용 뒤 보상 대기 — Captured Mentat(Intrigue·card), Guild Spy(card·Guild면 Intrigue), Branching Path(Intrigue·troop 2), Pivotal Gambit(troop·1위 보상 서약). 구현: `effects.py`의 `pending_agent_icons`/`arm_agent_icons`/`finish_agent_icon`, `agent_effects.py`의 `agent_card_icons_at_placement`·`legal_agent_card_icon_actions`·`resolve_agent_card_icon`(자동 키 8종 `AUTOMATIC_AGENT_ICONS`), `agent_effect_frame`의 아이콘 모드 분기, 자기 비용/아이콘으로 trash된 카드의 보상 유지(`agent_card_self_trashed`, OQ-022 예외), 서버 `detail`(`display/actions.py`)과 UI 라벨. 단위 유지: The Beast's Spoils, Arrakis Revolt, 문장형·화살표 비용쌍 카드. **Reveal box**: 자동 이득은 Reveal 시작 시 일괄 적용(결과 무관)이지만 선택형 Reveal 효과(`PersonalCardRevealChoiceEffect` 11종)는 카드 순서의 직렬 `REVEAL_CHOICE` frame이라 `[Main p. 12]`의 자유 순서·획득 사이 삽입이 안 된다. 다음 작업 제안: 선택 frame에 `defer_reveal_choice`(맨 뒤로 미루기)와 Reveal frame의 `resume_reveal_choice(effect=<kind>)`를 추가하고 `finish_reveal`은 미룬 선택이 남아 있으면 보류(codec +12). OQ-027에 기록.
2. **행동별 되돌리기 가능 표시 완료.** `legal_actions`의 각 행동에 `undoable`(dry-run: 숨겨진 정보 공개 또는 chance 결정으로 이어지면 False)을 붙이고 UI가 "되돌리기 불가" 배지를 단다(`cab29f2`).
3. **턴 종료 확인 완료.** 사람 좌석의 행동 뒤 다음 결정이 다른 좌석의 것이고 그 좌석의 되돌리기 창이 열려 있으면 세션이 `awaiting_confirmation`(요약 `confirmation`)으로 멈춘다. `POST /games/{id}/confirm`(`confirm_turn`)으로 확정해야 chance·AI가 진행되고, 되돌리기는 멈춤을 해제한다. 공개(reveal)로 끝난 턴은 창이 이미 닫혀 있으므로 예전처럼 바로 넘어간다. 저장 중 멈춤 상태는 복원 시 유지된다. 서버 테스트 helper(`_play`)는 자동 확정한다.
4. **병력 회수 규칙 확인(문서).** Main p. 10·p. 20과 FAQ p. 3·4 원문 대조: 배치는 Combat space에 Agent를 보낼 때의 권한이고 Retreat는 효과 키워드로만 정의된다 — 임의 회수 규칙은 발견되지 않았다. 엔진은 바꾸지 않았고(되돌리기가 공개 전까지의 편의 장치), 사용자가 더 고민하겠다고 하여 2026-09-04에 OQ-029 `OPEN`으로 등록했다.
5. **보드 마커 완료.** `display/board_layout.py`에 Influence 트랙(Emperor 기준 7단 y + Faction별 offset, 좌석별 x 4열, Alliance 지점), VP 트랙(0~12, 초과는 상단), 전투력 트랙(0~10 윗줄, 11~20 아랫줄), Conflict 4분면, High Council 좌석 4곳의 퍼센트 좌표를 0.5% 격자로 측정해 추가하고(`marker_layout`, catalog `tracks`), app.js `renderTrackMarkers`가 큐브·링·토큰·유닛 칩을 그린다. 브라우저에서 seed 14로 확인: 큐브 16개·VP 4개·전투력 2개·Conflict 칩 2개가 맞는 위치에 있고 Influence 획득 후 큐브가 한 칸 오른다.

- 검증: pytest 1,041, Ruff, mypy. 1번 커밋 뒤 소크 random 룰셋당 150판(`--rotate-leaders --soundness-interval 25`, 300/300)·heuristic 60판(120/120)·프로모 60판(120/120) 실패 0. 브라우저 E2E(seed 14): 배치 → Solari 아이콘 → Influence → "행동을 마쳤습니다. 턴을 넘길까요?" 확인 패널 + 되돌리기 3단계 → 확정 후 AI 진행.
- 남은 경계: Reveal 선택형 효과 순서(위), Beast's Spoils/Arrakis Revolt 단위, 마커 좌표는 소유자 스캔 기준(다른 프레이밍은 재측정).

## 2026-09-03 보드 공간 아이콘 분리 세션 요약 (OQ-027, codec v86)

- 사용자 지적: Arrakeen에 가면 troop 1 recruit와 card 1 draw가 "보드 효과 해결" 한 행동으로만 해결되어 두 아이콘을 따로 고를 수 없었다. 결과가 같더라도 garrison 병력 추가와 card draw는 별개 선택지여야 한다는 판정을 OQ-027 `DECIDED`로 기록했다(`[Main p. 9]` "You may carry out all these effects in any order"; OQ-015(d)의 Intrigue 아이콘 판정과 같은 방향). 공식 Main p. 9 원문은 `scripts/prepare_official_rules.py --source main`으로 /tmp에 만든 working copy에서 대조했다.
- **엔진**: `board_effects.py`의 아이콘 모델. 배치 시 `board_icons_for`가 공간의 인쇄 아이콘 키 목록(인쇄 순서)을 frame context `board_icons`·`pending_board_icons`에 넣고, `pending_board_effect`는 남은 아이콘이 있는 동안 True인 그룹 플래그로 유지한다(`effects.py`의 `pending_board_icons`·`finish_board_icon`·`rearm_board_icons`). 자동 아이콘 7종(`AUTOMATIC_BOARD_ICONS` = `cards`·`contract`·`high_council`·`intrigue`·`resources`·`swordmaster`·`troops`)은 `resolve_board_effect(effect=<key>)` 행동 하나씩으로, 선택 아이콘(Espionage `spy`, Desert Tactics `trash`, Shipping `influence`; Sietch Tabr·Maker·Imperial Privilege는 공간 단위 키 하나)은 기존 전용 행동으로 해결한다. 그래서 Espionage의 Spy 선택은 더 이상 card를 draw하지 않고, Desert Tactics의 trash 선택은 troop을 recruit하지 않으며, Shipping의 Faction 선택은 Solari를 주지 않는다 — 각각 별개 아이콘 행동이다(정적 표 `static_board_effects`에 세 공간의 자동 아이콘을 추가). High Council 재방문의 3개 아이콘(`HIGH_COUNCIL_REVISIT_EFFECTS`, `visit_board_effects`), CHOAM contract 아이콘, Gather Support 유료 옵션의 water도 분리됐다. Secrets의 무작위 강탈은 Intrigue draw 아이콘에 붙어 있다. Reverend Mother의 반복(`pay_leader_board_repeat`)은 `board_icons` 전부를 다시 대기시키고, 첫 pass의 아이콘이 모두 해결된 뒤에만 제시된다(기존 동작 유지). `board_effect_resolved` 이벤트는 아이콘마다 발생하며 payload에 `effect`가 들어간다.
- **codec v86**: 인자 없는 `resolve_board_effect` 템플릿 1개 → `effect` 키 7개(기본 4,322, CHOAM 4,608, 프로모 4,422/4,708). 관측 v4 불변(pending 아이콘은 legal-action mask로 드러난다). heuristic agent의 점수표는 action_id 기준이라 그대로다.
- **UI/서버**: `legal_actions`의 각 행동에 `detail`을 추가했다 — 보드 아이콘 행동이면 그 방문의 인쇄 효과 영어 조각("Recruit 1 troop", High Council 재방문의 "Gain 2 spice" 등; `display.board_effect_action_text`·`board_icon_text`), 그 외 null. app.js의 `describeAction`은 `effect` 인자를 detail(아이콘화) 또는 한글 라벨(`BOARD_EFFECT_LABELS`, 로그·검토 화면용)로 표시한다. 기존 저장 파일은 codec 버전 불일치로 거부된다(기존 동작).
- 검증: pytest 1,035(신규·개편: Arrakeen 두 순서 동일 결과, Gather Support water 분리, Espionage draw/Spy 분리 양방향, Shipping·Desert Tactics·High Council·CHOAM contract 분리, 22칸 아이콘 표 pin, 미인쇄·중복 아이콘 거부, Reverend Mother 재대기, codec 왕복과 인자 없는 행동 제거, display·서버 `detail`; undo 테스트의 revision 번호는 아이콘 단계가 늘어 갱신), Ruff, mypy. 커밋 트리 소크: random 룰셋당 200판(`--rotate-leaders --soundness-interval 25`, 400/400), heuristic 룰셋당 80판(160/160), 프로모 룰셋당 60판(120/120) 모두 실패 0.
- 남은 경계: Sietch Tabr의 choose-one 줄과 Maker 공간의 선택은 인쇄된 하나의 선택 단위로, Imperial Privilege의 두 문장과 Secrets의 강탈 문장은 문장 단위로 남겼다(OQ-027 (c)(d)). 카드 Agent box의 복합 효과(예: `DRAW_ONE_AND_RECALL_AGENT`, `MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD`)는 이번 범위 밖으로 enum 단위 그대로다 — 같은 원칙을 적용하려면 별도 슬라이스가 필요하다.

## 2026-09-03 Uprising 프로모 3장 세션 요약 (`promo_cards` 옵션)

- 사용자 결정: `promo/`의 9장 중 Arrakis Revolt·The Beast's Spoils·Pivotal Gambit은 Uprising 후속 프로모라 구현 대상, 순서는 M9 앞. 공식 FAQ·룰북에는 이 카드들이 없어 카드면이 유일한 출처다(`SourceDocument.CARD_FACE`, `[card face]`; `rules/sources.md`).
- 카드면 확대 검증(`assets/cards/en/uprising/promo/`): 세 카드의 효과는 모두 **Agent box**(회색 상자)이고 파란 Reveal 상자는 Persuasion·검뿐이다(Desert Power·Priority Contracts 이미지로 상자 의미를 대조). Arrakis Revolt: Fremen, 6, City, acquire troop, Agent "Maker Hooks: 2 spice → Shield Wall 제거(선택) + sandworm", Reveal 1/3. The Beast's Spoils: Emperor, 3, City, Agent "face-up battle icon마다: Crysknife trash / Desert Mouse 1 spice / Ornithopter troop", Reveal 0/3. Pivotal Gambit: Fremen, 3, Fremen+City, Agent "이 카드 trash → troop + 이번 Conflict 1위 보상에 Influence 1 선택 추가", Reveal 1/2.
- **`Play` 커밋**: `RulesetConfig.promo_cards`(identifier `+promo`; 서버 `CreateGameRequest`·요약, UI 체크박스·상태줄, sweep `--promo-cards`·coverage). `DeckCardEntry.promo`, `imperium_cards_for_choam(choam, promo)`·`imperium_deck_instance_ids` 확장, DIU 감사는 프로모 제외. 새 enum 4종(위). 규칙: `agent_turn` 배치 조건(Revolt는 Maker Hooks+2 spice), `agent_effects`의 지불 provider(Revolt 두 변형: 벽 제거+소환 / 벽 유지+소환, 보호된 Conflict에서는 제거 변형만), trash provider(Gambit 자기 trash → troop + `GameState.conflict_first_place_influence_bonus` +1; Beast는 `face_up_battle_icons` 집합으로 spice·troop을 자동 지급한 뒤 Crysknife가 있으면 trash 선택 한 번 제시), `acquisition`의 `RECRUIT_ONE_TROOP`. Combat: `resolve_combat_rewards`가 1위 보상의 `choose_influence`에 pledge를 더해(sandworm 두 배 포함) 기존 Influence 선택 frame으로 해결하고 0으로 되돌린다. 관측 v4(전역 scalar 12개, 개인 카드 66종 → 2,022-int), codec v85(no-arg 2개 추가로 기본 4,316/CHOAM 4,602, 프로모 4,416/4,702). 표시 텍스트·UI 행동 라벨 추가.
- 사용자 검토로 첫 구현을 두 군데 고쳤다: (1) 즉시 매칭 규칙(`[Main p. 14]`) 때문에 같은 아이콘의 face-up 카드는 종류당 최대 1장이므로 Beast's Spoils는 "카드당"이 아니라 "face-up 아이콘 종류당" 보상, (2) Pivotal Gambit의 아이콘은 wild battle icon이 아니라 룰북 20쪽의 **Influence 1 선택** 마름모(확대 비교로 확인)라 wild-icon 상태·Endgame 매칭·codec wild 후보 확장을 모두 걷어내고 1위 보상에 Influence 선택을 더하는 구현으로 교체했다. Shield Wall 제거가 선택인 것은 공식 문장(`[Main p. 20]` "You may remove the Shield Wall token", `[Main p. 10]`) 그대로다. 판정 기록: OQ-024(종류당 1회, wild 미포함, trash 선택), OQ-025(1위가 받고 동률이면 소멸, sandworm 두 배 적용), OQ-026(보호된 Conflict에서 벽 유지 지불은 제시하지 않음). `implementation-audits/personal-cards.md`에 세 행 추가.
- 검증: pytest 1,027(신규 `tests/unit/rules/test_promo_cards.py` 16건 + 서버 1건), ruff, mypy. sweep 소크: `--promo-cards --rotate-leaders --soundness-interval 25` random 룰셋당 200판(400/400) + heuristic 룰셋당 60판(120/120) 실패 0. 커버리지 census에서 Revolt의 지불은 random 정책으로는 거의 나오지 않아(150판 중 1회) 단위 테스트가 그 경로를 고정한다.
- 남은 경계: 프로모 카드 명칭·효과의 한글 표시 없음(기존과 동일).

## 2026-09-03 M11 슬라이스 7 세션 요약 (보드 스캔 테이블 + 룰북 아이콘)

- 친구의 원격 브랜치 `kyungtae`(`881849c`, timethinker-GoNe, 2026-09-01 "Build an immersive single-screen game table")를 검토했다. 방향(보드 이미지 위 hotspot, 좌석색 Agent 토큰, 카드 이미지 손패·Imperium Row)은 채택하되 base가 `af8ff7c`로 master보다 33커밋 뒤라 5개 파일 충돌, master의 v3 관측(`private.discard_pile` 제거)에서 런타임 오류, undo·로그·공개 패널이 들어갈 자리 없음 등이 있어 병합하지 않고 master 위에 새로 구현했다(사용자: "꼭 그대로 병합할 필요는 없다"). 브랜치는 원격에 그대로 남아 있다.
- 사용자 판정: 보드 원본은 저장소 루트 `map.jpg`(Tabletop Simulator에서 가져온 6012×6005 스캔, gitignore); 효과 텍스트는 카드·보드처럼 아이콘으로 표시하고 아이콘은 룰북·카드에서 추출한다.
- **`3d70e38` 서버·display**: `display/board_layout.py`(22칸 `SPACE_BOXES` + 관측소 13곳 `POST_POINTS`, 2% 격자 오버레이로 수측정, 테스트가 엔진 id 전수 커버와 비겹침을 고정), `display/icons.py`(공식 Uprising Main Rulebook 20쪽 Icon Guide + 9쪽 Agent 아이콘의 image xref 45개), `scripts/extract_rulebook_icons.py`(card-implementer 서브에이전트 구현: 공식 URL 다운로드·sha256 검증·PyMuPDF 추출·4-연결 flood fill 배경 키잉, `uv run --with pymupdf --with pillow`), 서버 `/board-image`(`map.jpg` 또는 `DUNE_IMPERIUM_BOARD_IMAGE`)·`/icons`(`downloads/icons` 또는 `DUNE_IMPERIUM_ICON_DIR`), catalog `spaces[id].box`·`posts`·`icons`·`board_image`. 없으면 null/빈 값.
- **`6b9eae2` UI**: 게임 화면을 viewport 고정 3열 테이블로 재구성(좌: 좌석 카드 — 리더 썸네일·자원/Influence/병력 아이콘 스탯; 중: 보드 스테이지 + 공용 카드 띠(Conflict·Imperium Row·Reserve·Contract·Intrigue discard·draft 중 Leader pool); 우: 결정 패널·undo·검토 바·순위·행동 로그·종료 후 공개; 하단: 내 손패·Intrigue 카드 이미지). hotspot은 합법이면 발광, 클릭 시 합법 행동 1개면 즉시 적용·여러 개면 우측 목록 강조(`data-refs`)·없으면 popover. Agent 토큰·Control 플래그·Maker bonus spice·Spy(관측소 좌표)를 겹쳐 그린다. `ICON_RULES` glossary가 서버의 영어 효과 텍스트를 아이콘으로 재렌더(원문은 tooltip). popover는 fixed 위치(열이 각자 스크롤). 스캔 없으면 텍스트 보드 목록, 이미지 없으면 텍스트 카드, 아이콘 없으면 단어.
- 에셋 저장소(`Dune-Imperium-assets` `c57fa72`)에 `icons/` 45장과 `board/map.jpg`를 추가했고 이 머신은 `downloads/icons`·(선택) `map.jpg` symlink로 연결한다. 새 머신 설정은 그 README.
- 검증: pytest 1,015, Ruff(`src tests`), mypy. headless Chromium E2E(스크래치 Playwright + ALSA stub): 게임 생성 → hotspot 22개·보드 이미지 로드·아이콘 65개 → popover(아이콘 4개) → 손패/hotspot 클릭으로 12단계 진행 → 토큰 4개·로그 19건, JS 오류 0·서버 오류 0. 스크린샷 검토로 hotspot 좌표가 스캔과 일치함을 확인했다.
- 후속 수정: 손패의 Dagger·Diplomacy·Dune the Desert Planet·Reconnaissance가 텍스트 카드로 보인다는 사용자 지적 → Uprising판 이미지가 Dune Cards Hub에 없어 `KNOWN_MISSING`이던 네 장을 동일 인쇄물인 기본판 `dune-imperium-other-*.webp`로 매핑(`required_images` 170장, `KNOWN_MISSING`은 빈 집합으로 유지).
- **에셋 정비(사용자 요청, `Dune-Imperium-assets` + 메인 `display/images.py` 재작성)**: 사용자 확인 — 캐시 600장은 Dune Cards Hub에서 받은 그대로(파일명·바이트 동일)였고, `uprising-other-*-emperor/-muad-dib`는 6인 Commander 덱(Rules Supplements p. 7, 14)이라 4인 시작 카드 7장은 기본판 스캔이 맞다. 새 규칙: `cards/<언어>/<세트>/<종류>/<인쇄 카드명>.<확장자>`(공백·아포스트로피·`+` 유지, 동명 카드는 인쇄된 구별 요소를 괄호로 — Skirmish 3장은 battle icon, Harvest 3+/4+ 두 쌍은 보상), 세트 6개(uprising, base, rise-of-ix, immortality, bloodlines, conspiracy; 프로모는 각 세트의 `promo/` 종류)로 600장 전부 분류(안 쓰는 확장팩은 slug 유도 이름 + `name_source: "upstream-slug"` 미검증 표시), 매핑은 에셋 저장소의 `cards/manifest.json` 하나(607항목·파일 607: Uprising 시작 카드 7장은 세트별 자기 완결을 위해 기본판 스캔의 사본을 `uprising/starting/`에 둔다 — 사용자 결정). 메인 저장소: `display/images.py`는 manifest 로더(`load_card_manifest`·`resolve_card_images`: ko 우선·en fallback·존재 파일만, `required_image_keys` 170)로 교체하고 오타 보정표·`KNOWN_MISSING` 제거, catalog URL은 percent-encoding, 서버 기본 경로 `downloads/cards`(에셋 `cards/` symlink), `fetch_card_images.py`는 manifest 출처로 빠진 파일만 받는 스크립트로 재작성. 검증: pytest 1,011(캐시 없는 머신은 skip 1), ruff, mypy, headless Chromium E2E 오류 0(손패 7장 전부 이미지).
- 프로모 정리(사용자): 캐시의 `promo/` 9장 중 Arrakis Revolt·The Beast's Spoils·Pivotal Gambit은 Uprising 후속 프로모라 구현 대상 → 에셋 `uprising/promo/`로 이동(`bb2cff7`), 나머지 6장은 사용자 분류대로 각 확장팩의 `promo/`로 이동(base: Duncan Loyal Blade·Jessica of Arrakis·Thumper, rise-of-ix: Boundless Ambition, immortality: Piter Genius Advisor, bloodlines: Ruthless Leadership)하고 범위 밖으로 둔다. 별도 `promo` 세트는 없앴다.
- 경로 정리(사용자): `downloads/`·루트 `map.jpg`·`rulebooks` symlink를 모두 없애고 루트의 `assets` symlink 하나(→ `../Dune-Imperium-assets`)로 통일. 서버 기본값 `assets/cards`·`assets/icons`·`assets/board/map.jpg`, 룰북 PDF는 `assets/rulebooks/`(AGENTS.md·CLAUDE.md·rules/sources.md 갱신).
- 남은 개선: Influence·VP 트랙 마커를 보드 위에 그리기, 아이콘 키잉 tolerance(프레임형 Agent 아이콘 모서리의 잔여 베이지), 같은 카드 2장으로 생기는 중복 행동 라벨 구분.

## 2026-09-02 M11 슬라이스 6 세션 요약 (행동 되돌리기 + 실시간 행동 로그)

- **`0e76131` 서버**: `server/session_log.py` — append-only 세션 로그(`LoggedStep`: 단계 + 이벤트 + `reveals` + `hidden_arguments` + `undone`, `LoggedUndo` 마커). `reveals_hidden_information(before, after, actor)`는 새 `core.observation.known_card_seats`(카드별로 identity를 아는 좌석 집합; deck·bank는 아무도, hand·보유 Intrigue는 소유자만, `hand_public`·`intrigue_resolving`은 전원)로 "어떤 좌석이 전에 몰랐던 카드를 알게 됐는가"를 판정하되, 행동자만 알던 카드를 행동자가 스스로 공개한 경우(Intrigue play, hand discard/trash, Reveal)는 예외(사용자 판정). `undo_window`는 뒤에서부터 자기 행동이면서 `reveals`가 아닌 연속 단계 수 — chance·다른 좌석 행동·공개 단계에서 닫힌다. 따라서 되돌리는 구간에는 chance·AI 단계가 없어 RNG 스트림을 건드리지 않고, 복원 상태는 다시 그 좌석의 결정이다. `GameSessionManager.undo(seat, revision, steps)`는 `steps[:keep]`을 reset부터 재적용해 복원하고 로그의 해당 항목을 `undone`으로 표시한 뒤 마커를 붙인다. `log(seat, after)`는 이벤트를 `visible_to`로 거르고, 비공개 카드를 가리키는 행동 인수는 다른 좌석에게 `(비공개)`, chance 값은 종료 전 숨김(종료 후 전부 공개). 저장 형식 v2: `log` 필드(되돌린 단계·마커 포함), 복원 시 되돌린 가지를 분기 상태에서 재적용해 이벤트를 복구·검증; v1 저장도 읽는다(되돌림 이력 없음). 검토 메타 `undo_history`. HTTP `POST /games/{id}/undo`, `GET /games/{id}/log`. summary에 `undo`(좌석별 창)·`log_count`. 테스트 `tests/server/test_undo.py` 9건 + HTTP 1건.
- **UI**(card-implementer 서브에이전트 구현, 메인 세션 검토): 결정 배너의 "되돌리기 (1단계)"/"N단계 모두 되돌리기" 버튼, `#action-log` 패널(이벤트별 한국어 라벨 `EVENT_LABELS`, 되돌린 항목 취소선, 마커 강조), 검토 상태줄의 되돌림 마커. headless Chromium E2E(스크래치 Playwright)로 되돌리기 → 로그 갱신 → 완주 → 검토 마커까지 JS 오류 0 확인.
- 되돌린 뒤 다른 선택으로 같은 revision 번호에 다시 도달할 수 있으므로, summary의 `undo_count`(되돌리기 세대 번호)를 행동·되돌리기 요청이 함께 보내면 revision과 둘 다 맞아야 통과한다(`StaleRevisionError`, HTTP 409). 브라우저 UI는 항상 보내고, 매니저·HTTP API에서는 선택 인수라 생략한 호출은 revision만 검사한다. 저장 복원 시 로그의 마커 수로 복구한다.

## 2026-09-02 OQ-010 확정 세션 요약 (관측 v3, 이벤트 가시성 불변식, 종료 후 전체 공개, 되돌리기 설계)

- 사용자와 OQ-010의 네 범위를 결정했다(전부 추천안 채택, 세부는 `rules/open-questions.md`): (1) 상대 discard identity 공개, (2) 완료 contract identity 공개, (3) 실시간 로그는 `event_log`를 `visible_to`로 걸러 표시하되 공개 이벤트는 공개 존의 카드만 이름을 담는다, (4) 종료 후 전체 공개(검토 편의 convention).
- **`8bb3bfe` 관측 v3 1차**: `PublicPlayerView.discard_pile`·`completed_contract_ids` 추가, `PrivatePlayerView.discard_pile`과 좌석 scalar 2개 제거, `seat{n}_discard`/`seat{n}_completed_contracts` 세그먼트. UI 좌석 카드에 완료 contract 표시.
- **`7a52c17` 이벤트 가시성**: 새 sweep 불변식 `check_event_visibility`(매 전이, 공개 이벤트 payload의 card id가 비공개 존에 있으면 실패)를 넣고 random 24판 전수 조사로 세 가지 누출을 찾아 고쳤다. Secrets 강탈 이벤트를 공개/한정 두 이벤트로 분리, `cards_drawn`·`personal_discard_shuffled`는 공개로 전환(장수만 담음). 선택 해결 중인 played Intrigue는 `PlayerView.intrigue_resolving`으로, 공개 경로로 hand에 들어온 카드(Corrinth City·Intrigue to-hand·BG Bond 반환)는 새 `PlayerState.hand_public`(construction 시 hand 밖 항목 자동 제거) → `PublicPlayerView.hand_public`으로 공개. 관측 v3 최종 1,967-int(`seat{n}_hand_public` 63, 전역 `intrigue_resolving` 39 추가). privacy scramble이 두 공개 집합을 보존하도록 수정.
- **`8087e9b` 종료 후 전체 공개**: `disclose_hidden_zones`(각 좌석 hand·deck 순서·Intrigue + Imperium/Intrigue/Conflict deck·bank 순서). 서버는 종료된 게임의 live view와 검토 모든 step에 `disclosure`를 붙이고, 검토 라벨은 전 좌석 상세 + chance 값, AI 좌석 검토 허용. UI에 "종료 후 공개" 패널과 전 좌석 검토 선택. headless Chromium E2E(스크래치 Playwright + ALSA stub, 메모리의 recipe)로 종료 화면·검토 화면 JS 오류 0 확인.
- 되돌리기 기능은 설계를 확정해 `implementation-plan.md` M11 슬라이스 6으로 기록했고, 같은 날 뒤이어 구현했다(위 세션 요약).
- 검증: pytest 993, Ruff, mypy. 커밋 트리 소크(`7a52c17` 기준) — 회전 리더 random 룰셋당 150판 + heuristic 룰셋당 80판(soundness 25) + draft random 룰셋당 40판, 실패 0.
- 교훈(프로세스): `ruff format`은 이 저장소의 검사 항목이 아니며 실행하면 무관한 60여 파일이 바뀐다. 이 세션에서 한 번 실행했다가 파일별로 되돌렸다. `ruff check`만 쓴다.

## 2026-09-02 오픈 퀘스천 재판정 세션 요약 (OQ-015(d) 아이콘 순서 선택, OQ-021 Shaddam 선택)

- **OQ-015(d) 재판정 (`446e6dc`, codec v83)**: 사용자 판정 — 한 효과 줄의 여러 아이콘은 독립 효과이고 인쇄가 순서를 강제하지 않으므로 소유자가 순서를 고른다(화살표 비용→보상은 인쇄 순서 유지, 비용 슬롯 먼저). INTRIGUE_CHOICE frame에 `resolve_intrigue_rewards` 행동을 추가해 비용 지불 뒤 자동 보상 묶음을 원하는 시점에 해결할 수 있게 했다. Cunning은 draw 먼저 → 뽑은 카드 trash 가능. 전수 스캔 결과 순서가 결과를 바꾸는 조합은 Cunning뿐이고(Unexpected Allies는 기존 고정이 유일 합리 순서), Devour/Impress/Leverage는 순서 무관, 화살표 비용 카드들(Questionable Methods 등)은 영향 없음.
- **소크 적발 수정 (`f0f77eb`)**: 회전 리더 소크가 base seed 485/563에서 choice frame 복제(이중 discard·이중 draw)를 적발 — mid-frame draw가 reshuffle chance frame을 push했는데 top 교체가 그것을 덮어썼다. acquire 슬롯과 같은 advance-before-move 패턴(보상 적용 전 frame 갱신)으로 수정하고 두 seed를 회귀로 고정했다.
- **OQ-021 재판정 (`2d2e237`, codec v84)**: 사용자 판정 — 시장·bank가 모두 소진돼도 set-aside Sardaukar contract가 남아 있으면 Shaddam은 아이콘마다 2 Solari와 set-aside 획득 중 선택한다(`take_exhausted_contract_solari`, CHOAM 전용 템플릿). 다른 플레이어와 set-aside 소진 후의 Shaddam은 기존 자동 2 Solari 전환 유지. 이전의 "Shaddam도 자동 전환" 판정 폐기.
- 검증: pytest 989(988+skip 1), Ruff, mypy. 커밋 트리 소크 — 회전 리더 random 룰셋당 700판 + heuristic 룰셋당 400판, 모두 soundness 25, 실패 0(첫 회전 소크가 위 frame 복제 버그를 적발한 뒤 재실행 통과).

## 2026-09-01 오픈 퀘스천 후속 세션 요약 (사용자 피드백: OQ-022 디자이너 판정 채택, OQ-023 재판정, OQ-010 재개)

- 사용자 피드백 6건을 반영했다. OQ-003은 사용자가 기존 판정을 그대로 재확인했고, OQ-015·OQ-021은 설명만 제공했다(판정 불변).
- **OQ-022 (동작 변경, `76dbbf7`)**: 사용자 지시로 외부 커뮤니티·공식 디지털 구현을 조사했다. BGG thread 3031484에서 디자이너 Paul Dennen(계정 "Merakon")의 2023-02-19 판정을 확인했다 — 이미 trash된 카드의 효과는 받지도 발동하지도 않는다(기존 pooled-effects 판정의 공식 번복; Esmar Tuek/Cull, Foldspace 사례). 2025 FAQ의 Imperial Spy·Beguiling Pheromones named 항목이 같은 원칙이라 현재도 유효하다. 이에 따라 dispatcher 훅 `expire_trashed_card_effects`가 미발동 Agent box 전체(의무 부분·Bond·선택 슬롯)를 만료시키는 모델로 교체하고, 충족 간주·잔여 해결 경로와 `agent_card_self_trash_satisfied` 이벤트를 제거했다. 이미 지급된 Reveal 기여분과 설치형 trigger는 유지(후속 답글). BGG 페이지는 Cloudflare 사람 확인이라 열지 않고 공개 geekdo API로 본문을 확인했다(CAPTCHA 우회 없음). codec 불변.
- **OQ-023 (동작 변경, `bce829e`)**: 사용자 재판정 — Imperial Privilege의 recall과 draw는 별개 효과이므로, recall 대상이 없으면 recall만 건너뛰고(`imperial_privilege_recall_skipped`) card draw는 그대로 해결한다. 이전의 절 전체 무효 판정을 교체했다.
- **OQ-010 (재개)**: "한 번 공개된 정보는 재확인 가능해야 한다"는 방향을 사용자가 확정, 구체 범위(상대 discard identity, 완료 contract identity, 종료 후 열람 등)는 후속 논의로 남기고 `OPEN`으로 되돌렸다. 관측 v2 구현은 논의 전까지 현행 유지.
- **OQ-012 (보강)**: Faction 공간의 Influence 상승 시점은 Main p. 9 자유 순서 원문("You may carry out all these effects in any order")이 직접 답한다 — 방문자가 시점을 고르며 엔진의 `resolve_faction_influence`도 그렇게 제시함을 확인. Bloodlines 도입 시 이 항목을 다시 열기로 재개 조건을 명시했다.
- 검증: pytest 986(985+skip 1), Ruff, mypy. 커밋 트리 소크 — OQ-022 반영 후 룰셋당 700판(soundness 25), 두 커밋 반영 후 룰셋당 700판(`--rotate-leaders` + soundness 25) 모두 실패 0.

## 2026-09-01 오픈 퀘스천 확정 세션 요약 (19건 전부 DECIDED)

- 사용자 지시로 open-questions의 미해결 항목 전부에 확정 결정을 내렸다. 먼저 공식 리소스 페이지를 재확인해 Main/Supplements 23-10-12판과 FAQ 2025-01-13판이 여전히 최신임을 확정한 뒤(새 공식 판정 없음), `DECIDED` 상태(확정 프로젝트 판정 — 새 공식 문서가 답을 줄 때만 재검토)를 도입해 `OPEN`/`CONTENT` 19건 전부를 전환했다. RESOLVED 4건(OQ-005/009/013/014)은 그대로다.
- 동작이 바뀐 유일한 항목은 OQ-006이다(`5baac89`): Main p. 11 원문의 Infiltrate는 "다른 플레이어가 점유 중"이라는 술어를 발동 조건으로, 연결된 Spy **하나**의 recall을 비용으로 두므로, opponent Agent가 2개 이상인 공간을 배치 불가로 막던 임시 guard를 제거하고 recall 하나로 진입을 허용했다. codec 불변(기존 `infiltrate_post_id` 인자 그대로).
- OQ-002는 콘텐츠 검산으로 닫았다(`5e34522`): 동률 그룹이 받는 보상은 항상 2·3위 줄이고 그 줄에는 상호작용 보상이 없으므로(Influence 선택·contract·Spy·VP·optional 지불·control은 전부 1위 줄 전용), 좌석 번호 오름차순 해결(First Player 위치 무관)을 tied-order 테스트 2건으로 pin했다.
- 나머지는 분석·문서 확정이다: OQ-001(완결 Endgame Intrigue 6종 전수 — 어떤 효과도 다른 window의 조건 입력을 바꾸지 못해 단일 순회 근거 유효), OQ-003(완결 Intrigue 39종 재검산 — Combat 중 유닛 증가 카드 없음), OQ-008(Main p. 11 공식 예시가 controller 보너스의 배치 즉시 해결을 직접 보여주고, Agent turn 중 상대 자원 총량을 읽는 효과가 전무함을 DSL 조건 전수로 확인), OQ-011(Main p. 11 원문 "immediately after placing your Agent (before receiving any effects...)"), OQ-012(자유 순서 밖 동시 의무 효과는 획득 이벤트 계열뿐 — 획득 카드 보상 → in-play trigger → Acquire Contract → Call to Arms 고정 순서 확정, 전부 같은 획득자의 가환 이득), OQ-010(관측 v2의 identity 공개 경계와 종료 후 비공개 검토를 최종 판정으로 승격), OQ-004/007/015~023(기존 convention을 확정 판정으로 채택; OQ-021은 FAQ "in place of" 근거 유지).
- 규칙 문서의 미확정 절들을 확정 판정 참조로 갱신했다: `combat-and-round-end.md`, `player-turns.md`, `information-visibility.md`, 감사 문서 `spies.md`·`combat-conflicts.md`, 그리고 `open-questions.md`의 상태 정의(intro)와 2026-09-01 확정 캠페인 서문.
- 검증: pytest 986(985+skip 1), Ruff, mypy 통과. 공식 PDF 텍스트는 `scripts/prepare_official_rules.py`로 /tmp에만 생성해 원문 대조에 사용했다.

## 2026-09-01 검증 강화 캠페인 세션 요약 (보드 22칸 완결 + 검증 도구 + 교차 소크)

- 동기: M9/M10 전에 엔진에서 "학습이 변형 게임을 배우는" 원인을 제거한다. 미구현 보드 칸은 codec을 바꾸는 작업이라 M9 이후로 미루면 평가 행렬과 체크포인트가 무효화되므로 지금이 유일하게 싼 시점이었다. 사용자 확정 범위는 "전체 1→4"(보드 구현 → 검증 도구 → 대규모 soak → 대조).
- 슬라이스는 모두 `docs/rules/board-spaces.md`의 전사·인용을 근거로 하고, Sonnet `card-implementer` 서브에이전트에 위임한 뒤 본 세션이 diff를 리뷰하고 pytest/ruff/mypy를 재실행해 커밋했다.
- `d7703ef` Dutiful Service(CHOAM): `accept_contract`의 `begin_contract_gain` 경로 재사용(빈 시장 2 Solari 폴백은 OQ-021). codec 불변.
- `e141492` Shipping: choice-driven 공간으로 5 Solari + 선택 Faction Influence 1(`choose_shipping_influence` 4종, codec v80, `gain_faction_influence` 경유로 friendship VP 경로 공유).
- `63a8994` Desert Tactics: troop 1 recruit(`troops_recruited` counter로 Combat 배치 연동) + 선택적 trash(hand/discard/in play, `trash_personal_card` 공유로 OQ-022 self-trash convention 승계). codec v81.
- `49a5bb6` Imperial Privilege: 2단계 슬롯 — 선택적 Intrigue discard→reshuffle-safe draw, 그다음 의무 recall(방금 보낸 Agent 제외) + card 1 draw. 다른 배치 Agent가 없으면 절 전체 무효(신규 OQ-023 convention). codec v82.
- `78fa1a3` Secrets: 정적 Intrigue draw + `SECRETS_STEAL` chance frame으로 4장+ 보유 opponent마다 무작위 1장 강탈(held Intrigue만, intrigue_faceup 제외). draw의 reshuffle 부족분은 steal frame 위로 승격해 인쇄 순서(draw → steal)를 유지. FrameKind는 enum 끝에 추가해 관측 인덱스 안정. codec 불변(chance 전용).
- `881d88b` 즉시 공개(OQ-015(c) 해소): Reveal 중 hand에 들어간 카드는 즉시 in play로 옮겨 도착 시점 자격 판정으로 자신의 기여(설득·검·자원·선택 frame)를 얻고, 이미 지급된 금액은 확정 유지한 채 교차 효과 증분만 더한다. `begin_reveal_turn`의 카드별 계산을 순수 헬퍼로 추출해 양 경로가 동일 판정. 훅은 hand 진입 지점 2곳(개인 draw 완료 — reshuffle 후 경로 포함 — 과 Inspire Awe의 to-hand 획득). 교차 효과 3종(Stilgar, Sardaukar Coordination, Leadership)이 모두 무조건부임을 pin 테스트로 고정. 보류 필터 제거로 Reveal 중 해당 Plot이 제시된다.
- 소크가 실전 버그 두 계열을 적발했다 — 둘 다 "새 board trash가 해결 대기 중인 카드를 mid-frame에 잡는" 가족이다.
  - `fab266f`: Dangerous Rhetoric을 Spy 아이콘으로 Desert Tactics에 내고 board trash가 그 카드 자체를 잡으면 `TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE` Agent box가 무조건 self-trash를 실행해 crash(random CHOAM seed 2735). OQ-022 convention(이미 trash됐으면 충족 간주, 의무 잔여 효과는 해결)을 `apply_agent_card_influence`로 확장. 반대 성격인 Delivery Agreement의 "trash해서 VP"는 비용이므로 카드가 사라졌으면 해결 시점 판정으로 선택지를 제시하지 않게 했다.
  - `e6fc298`: BG Bond 카드가 Bond box 해결 전에 trash되면 `has_faction_bond`가 source의 in-play 존재를 요구해 crash(random seeds 2934/2590). 인쇄된 Bond 조건은 "다른 해당 Faction card가 in play"만 세므로(`[Main p. 20]`) source의 존 요구를 제거했다.
  - 회귀: 단위 3건 + 실패 seed 3개 완주(`tests/integration/test_sweep.py`).
- 주의(재발 방지): 백그라운드 sweep을 서브에이전트의 작업 트리 편집과 겹치면 반쪽 편집 상태의 판별 불가한 실패가 섞인다(heuristic seed 236 실패가 그 사례 — 완성 트리에서 그 seed·그 배치 1,000판 전체는 통과했지만, 같은 오류 계열이 다른 seed에서 실제 버그로 재등장했다). 소크는 커밋된 트리에서만 돌리고, 실패는 반드시 완성 트리에서 재현해 판별한다.
- 검증: pytest 934→973, Ruff, mypy. 수정 커밋 후 소크 — heuristic 룰셋당 1,000판, draft 두 policy 각 룰셋당 500판 실패 0, random 룰셋당 3,000판은 두 수정 반영 후 재실행 통과(위 기준선 절 수치).
- 2단계 sweep 확장(`853ecd4`, pytest 973→984): `--soundness-interval N` (표본 결정마다 제시된 모든 합법 행동을 실제 적용 + `ActionCodec` 인코딩 왕복 — sweep이 codec을 처음으로 검증), `--coverage-json PATH` (replay·이벤트 기반 룰셋별 콘텐츠 커버리지 census + 카탈로그 대비 0회 보고), `--rotate-leaders`(seed 결정적 4종 추출, draft와 배타).
- 3단계 교차 소크(커밋된 트리, 전 기능 on, 총 7,000판 실패 0): random 룰셋당 2,000판 + heuristic 룰셋당 1,000판(둘 다 리더 회전) + draft 두 policy 각 룰셋당 500판, 모두 `--soundness-interval 25`. 네 구성의 커버리지 합집합에서 0회 경로는 정확히 세 종뿐이며 전부 구조적이다: 기본 룰셋의 contracts 20개(CHOAM 전용), 기본 룰셋의 Shaddam 시그넷 액션 2개(`choose_leader_signet_influence`, `gain_leader_signet_troop` — Shaddam은 CHOAM 전용), 그리고 양 룰셋의 `acquire_leader_reserve`(Irulan Chronicler's Insight의 Reserve 분기 — 현재 콘텐츠에 비용 1 Reserve 카드가 없어 죽은 일반화 코드, `implementation-audits/leaders.md`의 "비용 1은 Imperium 5종" 기록과 일치). 비구조적 0 커버리지는 없다 — 강제 시나리오 테스트 추가 불요.
- 4단계 대조: `dune-imperium-audit-diu ../DIU/data/imperium.JSON` 재실행 — 63종 전부 일치(copy 수 차이 48건은 기존 방침대로 로컬 manifest 우선). open-questions 23건 재점검 — OQ-007의 codec 버전 표기 모호 1건만 명확화(도입 시점 표기), 나머지 전부 현행과 일치.

## 2026-08-31 UI 효과 표시 세션 요약 (텍스트 자동 생성 + 로컬 이미지)

- 문제: M11 UI가 이름만 보여줘 배치·플레이 결정 시 칸/카드 효과를 외워야 했다. 사용자 확정: 영어 효과 텍스트를 엔진 데이터에서 자동 생성해 전면 표시하고, gitignore된 `downloads/dunecardshub/cards/` 로컬 캐시(Uprising 189장)의 이미지를 병용한다(로컬 서빙 한정 승인, 저장소 커밋 금지 유지). 표시 전용 변경으로 codec·관측은 v79/v2 그대로다.
- `3c1cc69`: `board_effects_for`의 match를 순수 함수 `static_board_effects(space_id, cost_option, choam_module)`로 추출(동작 불변). pin 테스트가 전 공간×옵션×룰셋 도메인과 미구현 집합(기본 4칸 + CHOAM dutiful_service)을 고정 — 이 과정에서 이전 핸드오프의 "미구현 2칸" 서술이 부정확했음을 확인하고 위 경계 절을 정정했다.
- `a4befd4`: 프레임워크 중립 `dune_imperium.display` 패키지. Intrigue DSL(union별 exhaustive match + `assert_never`)·Contract·Conflict·정적 보드 테이블은 기계적 렌더, 개인 카드 enum 토큰(~50개)·선택형 공간·Leader 10면은 이미지 검증된 감사 문서(`personal-cards.md`, `leaders.md`, `board-spaces.md`) 문구로 수작성. 커버리지 테스트가 모든 enum 멤버·DSL primitive·reveal 필드·카드·공간·Leader 면을 고정해, 텍스트 없는 신규 콘텐츠는 스위트가 실패한다. 이미지 파일명 오타 override 9건과 이미지 없는 시작 카드 4종도 실측으로 고정했다. 구현은 Sonnet 서브에이전트 2개에 위임하고 본 세션이 감사 문서 대조로 리뷰했다.
- `d34a2d1`: `/catalog` 확장 — 카드·Intrigue·Contract·Conflict·Leader(대체 면 `reverend_mother_jessica` 항목 신설)·공간(비용·요구·플래그·옵션별 효과·계산된 implemented·notes) + `image` URL. `create_app`이 `--card-images-dir`/`DUNE_IMPERIUM_CARD_IMAGE_DIR`/기본 downloads 순으로 캐시를 찾아 존재할 때만 `/card-images` mount, 없으면 image 전부 null로 텍스트만 동작. contracts/spaces의 `deliver_supplies` id 충돌은 테스트로 고정하고 클라이언트가 space id를 spaces 섹션에 명시 조회해 해소한다.
- `d275a66`: 보드 공간 패널(아이콘 그룹별 22칸: 비용·효과·요구·점유·컨트롤·maker spice·미구현 배지)과 모든 chip의 상세 popover(효과 텍스트 + 이미지, Esc/바깥 클릭 닫기). hot-seat·replay 검토도 chip 공용이라 자동 적용.
- `3e2ae8f`: 행동 버튼 "ⓘ" 효과 미리보기(대상 공간의 해당 cost option + 카드 텍스트, play_intrigue는 해당 option만)와 `ACTION_LABELS` 111개 전체 커버(`tests/server/test_action_labels.py`가 rules 소스의 action_id 리터럴을 스캔해 누락·잔존 라벨 모두 실패 처리).
- 검증: pytest 842→933, Ruff, mypy 통과. 실제 uvicorn + headless Chromium E2E를 기본/CHOAM 두 룰셋에서 실행 — 22칸 렌더, 미구현 배지 4/5개, popover 텍스트·이미지 로드, ⓘ 미리보기 토글, 행동 버튼 6결정 진행, 페이지 오류 0. (WSL에 libasound가 없어 스크래치의 versioned stub을 `LD_LIBRARY_PATH`로 주입해 Playwright Chromium을 구동했다.)
- `4c175d1`(후속): `scripts/fetch_card_images.py` — 이미지 캐시가 없는 다른 개발 머신용 1회 다운로드 스크립트. 대상 목록은 `display.images.required_images()`(카탈로그가 참조 가능한 정확히 166장, 이미지 없는 시작 카드 4종 제외)에서 열거하고, UA+referer 헤더(직접 요청은 403), WebP 매직 검증, 기존 파일 skip/`--force`/`--dry-run`을 지원한다. 빈 디렉터리로 실다운로드 166/166 성공·기존 캐시와 전 파일 체크섬 동일을 확인했다. pytest 933→934.

## 2026-08-31 M11 슬라이스 5 세션 요약 (저장/불러오기 + replay 검토)

- 저장(`8ab3cd2`): `server/persistence.py`가 세션의 기록 steps를 `GameReplay` 위의 버전 있는 JSON 문서로 직렬화한다(`format_version` 1, 실제 `ACTION_CODEC_VERSION`·ruleset/content 버전 스탬프, step은 `type: action|chance` 판별자). 저장 파일은 서버 로컬 디스크의 `SaveStore`(`--saves-dir`, 기본 `~/.dune-imperium/saves`, 원자적 쓰기, save_id 패턴 검증)에 두고, HTTP로는 metadata만 내보낸다 — 기록된 셔플 결과가 비공개 덱 순서를 그대로 담기 때문이다.
- 불러오기의 chance 흐름은 핸드오프의 미결 설계 (a)의 변형으로 확정했다: RNG 상태를 저장하는 대신, `restore_game`이 기록 steps를 fresh seeded `ChanceResolver`(game seed)와 fresh seeded agents(policy seed + 좌석)로 재생하며 chance와 AI 결정을 **재생성해 기록과 대조**하고(사람 행동은 기록대로 적용), 마지막에 canonical state hash를 `replay_game`처럼 검증한다. 모든 RNG 스트림이 저장 시점 위치로 복원되므로 **불러온 게임은 저장하지 않은 세션과 동일하게 진행된다**(회귀 테스트로 고정: 저장 후 이어간 게임과 원본의 최종 순위·revision 일치). 대가로 저장본은 저장 당시의 엔진·agent 코드에 결속되며, 불일치·조작·버전 차이는 step 번호를 명시한 `SaveError`로 즉시 실패한다.
- 종료 후 replay 검토: `review`(step 라벨 타임라인)와 `review_state`(fresh 엔진으로 기록 steps를 k개 재적용한 시점의 좌석 `PlayerView`)를 추가했다. 검토는 종료된 게임의 사람 좌석만 허용하고 OQ-010 경계를 유지한다(자기 행동만 상세, 타 좌석은 행동 주체만, chance는 decision id만; open-questions.md에 convention 추가). 라이브 세션의 RNG는 건드리지 않는다.
- HTTP: `POST /games/{id}/save`, `GET /saves`, `POST /saves/{id}/load`, `DELETE /saves/{id}`, `GET /games/{id}/review`(+`/{step}`)를 추가했고 미존재 저장은 404, 형식·재생 오류는 400이다.
- 브라우저 UI(`e44900a`): 설정 화면의 저장 목록(불러오기/삭제), 게임 헤더의 저장 버튼(슬롯 이름 프롬프트), 종료 화면의 "리플레이 검토" — step 슬라이더·이전/다음·내 행동 점프·검토 좌석 선택이 기존 보드/좌석/비공개 렌더러로 시점 상태를 그린다.
- 검증: 실제 headless Chromium + uvicorn E2E로 draft 게임 생성 → 중간 저장 → 불러오기 → UI 버튼으로 79회 추가 결정 완주 → 종료 저장 → 491-step 검토 탐색 → 저장 삭제까지 서버 오류 0으로 확인했다. pytest 833→842(저장 문서 스탬프, 불러오기 동일 진행, 조작 거부 5종, SaveStore, 검토 경계·라벨, HTTP 왕복), Ruff, mypy 통과. M11 완료로 판정했다.

## 2026-08-31 M11 슬라이스 4 세션 요약 (브라우저 UI)

- 의존성 없는 vanilla HTML/CSS/JS 단일 페이지를 `server/static/`에 두고 FastAPI가 `/`(index)와 `/static/*`으로 서빙한다(`42be883`). 클라이언트는 서버의 summary/`PlayerView`/actions/catalog payload만 렌더링하며 규칙 지식을 갖지 않는다.
- `/catalog` endpoint(`server/catalog.py`, 프레임워크 중립)가 콘텐츠 manifest의 인쇄된 공개 표시 데이터를 제공한다: 개인 카드 63종의 이름·획득 비용·설득·검·Faction·Agent 아이콘, Intrigue 39종의 이름과 option timing, Contract·Conflict·Leader(능력명 포함)·보드 공간·Objective 이름. instance id → 카드 id 해석은 클라이언트의 접두사 파싱으로 한다.
- 화면: 설정(좌석별 사람/휴리스틱/랜덤, CHOAM, OQ-007 draft 기본 켬, seed, 진행 중 게임 이어서 열기) → 게임(결정 프롬프트 + frame kind + 결정 좌석, index 기반 행동 버튼, 보드 존—draft pool·Conflict·Imperium Row·Reserve·Contract 시장·maker spice·Intrigue discard, 좌석 4개 공개 패널, 내 hand/discard/Intrigue 비공개 패널) → 종료 시 최종 순위 표. 여러 사람 좌석은 결정 좌석을 따라가는 hot-seat으로 처리한다.
- 검증: 실제 uvicorn + 브라우저에서 폼으로 draft 게임을 만들고(설정 화면 → Leader pick 클릭 → 라운드 1 turn frame), UI 자체 행동 버튼 경로로 103회 결정을 자동 구동해 10라운드 최종 순위까지 완주했다(서버 로그 오류 0). `/catalog`·정적 서빙 테스트를 추가해 pytest 829→833, Ruff, mypy 통과.

## 2026-08-31 M11 슬라이스 3 세션 요약 (FastAPI 게임 세션 서버)

- web 스택을 **FastAPI + uvicorn**으로 확정하고 `ui` optional extra와 `dune-imperium-server` CLI(기본 127.0.0.1:8000)를 추가했다(`4fbd751`). 개발 환경 준비 명령은 `uv sync --extra rl --extra ui`로 바뀌었다 (TestClient용 `httpx2`는 dev group).
- `server/sessions.py`의 `GameSessionManager`는 프레임워크 중립이다. 게임 생성은 좌석 배정(`human`/`heuristic`/`random`), `choam_module`, `leader_draft`, seed(미지정 시 SystemRandom, policy seed 기본은 sweep과 같은 700,000+game_seed)를 받고, 엔진 공개 API(`reset`/`current_decision`/`legal_actions`/`apply`/`observe`)와 러너 패턴의 seeded `ChanceResolver`만 사용한다. chance와 AI 좌석은 생성 직후와 사람 행동 뒤 자동 진행되어 세션은 항상 사람 결정 또는 종료 순위에서 멈춘다. 적용된 모든 step은 슬라이스 5(저장/불러오기)를 위해 replay 형식으로 기록한다.
- 비공개 경계: 사람은 자기 좌석의 직렬화된 `PlayerView`와 revision 가드가 붙은 index 기반 합법 행동 목록만 받는다. 둘 다 비공개 카드 identity를 담을 수 있으므로 AI 좌석 조회는 `SeatAccessError`(HTTP 403)로 거부하고, `state.event_log`는 PlayerView 밖이므로 노출하지 않는다(가시성 결정은 계속 `core/observation.py` 단독).
- HTTP 매핑: 미존재 게임 404, 비인간 좌석 403, revision 불일치 409, 기타 잘못된 요청 400, pydantic 형식 오류 422. endpoint는 게임 생성/목록/요약/좌석 view/좌석 행동 목록/행동 적용/삭제다.
- 검증: 세션 단위 테스트 9건(전원 AI 생성 즉시 완주와 seed 재현, 사람 좌석 정지, index 행동 2,000 step 완주, draft 시작 frame, 좌석·seed 검증, 삭제)과 HTTP 테스트 7건(4인 사람 draft 게임을 API로 라운드 1까지 진행 포함). 실제 uvicorn 기동 + curl 왕복도 확인했다. pytest 813→829, Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 2 세션 요약 (Leader draft)

- OQ-007의 6-Leader 공개 draft convention을 `RulesetConfig(leader_draft=True)` ruleset option으로 구현했다(`c0c1795`). reset이 pick과 무관한 setup chance(Conflict tier, Objective→First Player, 공개 pool 6종, Imperium·Intrigue·Contract 전체 셔플, 시작 덱 전체 셔플)를 seeded로 모두 해결한 뒤 `GamePhase.SETUP`의 `leader_draft` frame에서 멈춘다. pick은 라운드 1 turn 역순(First Player 마지막)의 player decision이고, pick마다 setup face 배정과 인쇄된 시작 카드 제거(이미 섞인 덱 필터링 — 남은 순서 균등성 유지)를 적용하며, 마지막 pick이 Contract 시장을 배분한다(Shaddam pick 시 Sardaukar 2장 set-aside). 고정 `DEFAULT_LEADER_IDS` 경로는 그대로다.
- action 공간은 옵션과 무관하게 고정이다: `pick_leader` 템플릿을 두 catalog에 상시 포함해 codec v79(기본 4,152, CHOAM 4,429). 관측은 v2로 올려 공개 pool 6-슬롯 세그먼트를 추가했다(1,415-int; pick 결과는 기존 좌석 Leader 슬롯). PettingZoo env에 `leader_draft` 옵션을 추가했고, draft episode는 pick 결정으로 시작한다.
- sweep은 census를 setup 종료 시점에 고정하도록 바꿨다(draft 중 Staban의 Limited Allies가 시작 카드를 정당하게 제거하므로). `--leader-draft` 플래그를 추가했다.
- draft soak(두 policy × 두 룰셋 × 500판)이 기존 엔진 버그를 하나 더 적발해 수정했다(`d70b353`, CHOAM seed 198): Treacherous Maneuver를 낸 뒤 Cunning의 자유 순서 trash slot으로 그 카드 자체가 trash되면 Agent box 해결이 무조건 self-trash를 실행해 crash했다. 기록된 OQ-022 convention (self-trash는 이미 충족, 나머지 효과는 해결)을 `apply_agent_card_trash`에도 적용했다.
- 검증: 수정 후 draft soak 총 2,000판(heuristic 1,000 + random 1,000, 모든 불변식·replay 검사) 실패 0, 비-draft heuristic 400판 회귀 통과. pytest 796→813, Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 1 세션 요약 (heuristic agent)

- M11 슬라이스 1을 완료했다(`1a449f4`): `HeuristicAgent`는 RandomAgent와 같은 `choose_action(observation, legal_actions)` 계약으로, 합법 행동을 정적 전략 점수(직접 VP > 영구 업그레이드 > 비용 비례 획득 > 최대 배치, decline/pass 최하)로 순위 매기고 동점은 seeded RNG로 깬다. 미지의 action id는 0점이라 새 콘텐츠에서 seeded random으로 degrade한다. 점수는 규칙 판정이 아니라 전략 선호이며 공개 카드 비용만 참조한다. `agents/base.py`의 `Agent` Protocol, `run_policy_game`(좌석별 agent 주입, `run_random_game`이 위임), sweep/CLI의 `--policy {random,heuristic}`을 함께 추가했다.
- heuristic soak(룰셋당 1,000판)이 random 10,000판이 못 가던 궤적에서 잠복 버그 두 계열을 적발했고, 공식 문서 확인 뒤 수정했다:
  - **Special Mission PlaceSpy slot 교착**(`7a53c8f`, CHOAM seed 97·901): play 시점 판정이 "자기 Spy recall = post 해방"으로 계산했지만 다른 플레이어 Spy가 공유한 post는 recall해도 비지 않고, slot은 도움 안 되는 recall만 무한 제시하다 행동 0개로 좌초했다. `[Main p. 11]`의 "비어 있는 post", "먼저 자기 Spy **하나**를 recall**할 수 있다**"(둘 다 선택)에 따라 slot 전 분기에 `decline_intrigue_spy`를 추가하고, recall은 배치로 이어질 수 있는 것만(빈 target이 있으면 아무 Spy, 없으면 allowed post의 단독 점유 Spy) 제시하며, play 시점 판정도 단독 점유 기준으로 고쳤다. codec v78. Distraction trigger가 slot 루프 중간에 끼어들어 조건이 drift하는 실제 사례를 확인했다(해결 시점 판정 원칙 유지).
  - **Imperium Deck 고갈 tripwire**(`ac4d6d4`, 기본 룰셋 6판): heuristic이 카드를 충분히 사서 공유 덱이 실제로 바닥났다. 공식 문서는 덱 위에서 보충한다고만 하므로(`[Main p. 13]`, OQ-004) 물리적으로 강제되는 유일한 진행을 convention으로 기록했다: 덱이 비면 Row는 보충 없이 남은 장수로 운영한다. 네 제거 지점이 `take_imperium_row_card` 헬퍼를 공유하고, 관측의 5-슬롯 Row 세그먼트는 빈자리를 0으로 둔다.
- 검증: 수정 후 heuristic 룰셋당 1,000판(총 2,000판)과 random 300판×2가 모든 불변식·replay 검사 포함 실패 0으로 통과했다. 교착 seed 97·901은 invariant-checked 회귀 테스트로 고정했다(`tests/integration/test_sweep.py`). pytest 770→796, Ruff, mypy 통과.

## 2026-08-30 계획 조정

- M11(사람용 플레이 인터페이스)을 M9·M10보다 앞으로 옮겼다. 근거와 순서 방침(번호 유지, 나열 순서 = 구현 순서)은 `implementation-plan.md` 마일스톤 절 서두에 있다. UI 형태는 로컬 웹 UI로, 초기 AI 상대는 random + 간단 heuristic(M9 재사용)으로 확정했다.
- Leader 선택 절차를 OQ-007의 구현 convention으로 확정했다: 합법 Leader 중 무작위 6종을 즉시 공개로 뽑고, First Player 확정 뒤 turn 역순으로 한 명씩 공개 pick(First Player가 마지막), 미선택 2종은 미사용. 공식 setup의 Leader 단계(`[Main p. 4]`)를 First Player 결정 뒤로 옮기는 ruleset option이며 공식 규칙이 아니다. 세부와 구현 지침은 [`rules/open-questions.md`](rules/open-questions.md#oq-007--leader-선택-절차)에 있다.

## 2026-08-30 M7 검증 sweep 세션 요약

- `dune-imperium-sweep`을 만들었다(`simulation/sweep.py`, `invariants.py`, `cli/sweep.py`): 매 전이의 전역 카드 census(개인 카드 instance 집합, Reserve 스택+생존 사본 방정식, Intrigue·Conflict·Contract·Objective 보존과 단일 존), 교착 검출, 표본 주기의 관측 누출 검사(deck 순서·상대 hand·상대 Intrigue `[Main p. 7]`·Contract bank `[Main p. 16]`만 뒤섞은 상태와 관측 동일성; 뒤섞기가 실제로 상태를 바꾸는지도 테스트로 고정), replay 검증, multiprocessing 병렬화와 CLI. pytest에 고정 seed 테스트 8건을 추가했다.
- 첫 룰셋당 10,000판 sweep이 46판(0.23%)에서 잠복 버그 다섯 계열을 적발했고, 모두 해결 시점 판정 원칙(`[Main pp. 9, 20]`, `[Main p. 12]`)으로 수정했다: Spy Network recall 교착(`f148c14`), Maker Keeper·Wheels Within Wheels·Bond 3종 조건 drift와 Corrinth City 선택 소실과 self-trash 보류 효과(`83aa4f5`, OQ-022 convention 신설), Price is No Object 획득 Spy frame 정지(`24b13e7`).
- 수정 후 재실행한 룰셋당 10,000판(총 20,000판, 모든 검사+replay 포함)이 실패 0으로 통과했다: 400초, 50 games/s, 전이 약 879만 회, 라운드 중앙값 10. M7을 완료로 표시했다.

## 2026-08-30 전체 게임 RL 전환 세션 요약

- 설계 확정([`rl-environment.md`](rl-environment.md)): 관측 v1은 PlayerView 순수 함수인 1,409-int 평면 벡터(세그먼트 표 export, egocentric 좌석 회전, identity 카운트/슬롯/tri-state), 보상은 승자독식 zero-sum 종료 보상만, chance는 env 내부 seeded 해결. 상대 hand·deck·discard·Intrigue 장수 공개를 OQ-010 부분 convention으로 기록했다.
- `run_random_game` 러너(`GameSimulation(state, standings, replay)`)와 `dune_imperium_uprising_v1` env 전환을 구현했다. per-step VP delta 보상은 제거했고 종료 `infos`에 rank·VP를 노출한다. codec은 v77 그대로다.
- PlayerView에 결정 frame 요약(kind·결정 소유자·turn 소유자)과 공개 존 장수를 추가했다. frame별 세부 컨텍스트 공개는 kind별 화이트리스트 검토 후로 미뤘다.
- random 전체 게임에서 기존 엔진 버그를 하나 더 수정했다(`4d9efb8`): Espionage recall 뒤 자유 순서 효과가 그 Spy를 소비하면 배치가 crash하던 것을 해결 시점 supply 재확인과 recall 재개방으로 바꿨고(`[Main pp. 11, 20]`, Agent-card Spy 경로와 동일 패턴), supply 0에서 decline이 빠져 있던 것도 인쇄 효과의 선택성(`[Board Guide p. 1]`)에 따라 복원했다.
- 검증: env 경유 18판(기본 12+CHOAM 6) random full episode soak에서 승자독식 zero-sum 보상 불변식을 확인했고(약 4,100 agent step/s), 두 룰셋의 random 완주 전 상태 인코딩 sweep, PettingZoo api/seed 테스트, 755개 테스트·Ruff·mypy가 통과한다.

## 2026-08-30 Objective 감사 세션 요약

- 핸드오프의 "남은 Objective 상호작용 재감사"를 완료했다. setup 배정, Combat 즉시 icon matching, Endgame wild matching, Endgame Intrigue의 `FlipBattleCard`(Objective 제외, wild 대체 허용), 관측 공개 범위가 규칙 문서와 일관됨을 확인하고 `implementation-audits/objectives.md`에 기록했다.
- OQ-005를 RESOLVED로 갱신했다: Combat 즉시 matching은 의무 pair가 도착 즉시 해소되므로 공식 콘텐츠에서 printed icon당 face-up 한 장을 넘을 수 없고(wild는 Propaganda 한 장뿐), Endgame wild의 복수 후보 선택은 OQ-001 window의 소유자 행동으로 이미 구현돼 있다. Combat 다중 후보 `NotImplementedError`는 미래 콘텐츠 tripwire로 유지한다.
- 감사 soak에서 기존 엔진 버그를 발견해 수정했다(`fa99359`): Junction Headquarters의 Intrigue+Spice 지불 frame이 `pending_agent_effect`를 해제하지 않아 화살표를 반복 지불할 수 있었고(한 턴 한 번 규칙 위반 `[Main p. 9]` `[FAQ p. 3]`), 지불 뒤 Spice가 2 미만이면 다음 legal-action 열거가 RuntimeError로 crash했다(seed 20010). 아울러 세 지불 legal provider(Junction HQ, Ecological Testing Station/Smuggler's Haven, Corrinth City)가 큐 후 지불 불가 상태에서 raise하던 것을 자유 순서 해결 시점 판정 `[Main pp. 9, 20]`에 따라 decline만 제시하도록 바꿨다 (Prepare the Way `87a9300`과 같은 판정 방식, 회귀 테스트 4건).
- 검증: 기본 60판 + CHOAM 20판 random FINISHED 완주 soak(replay 검증, 매 전이 face-up 불변식 assert)에서 즉시 pair 181/62회, Endgame wild 32/8회, Endgame Intrigue flip 1/0회 발동을 확인했다. endgame·combat 감사 문서의 창 이전 서술과 Combat Intrigue/Shield Wall 잔재 서술도 현재 구현에 맞게 갱신했다.

## 2026-08-30 Shaddam 세션 요약

- standard Contract manifest를 교정했다: 6인 보충 규칙의 base-CHOAM setup이 "두 Sardaukar contract"를 set aside하라고 지시하므로 Sardaukar 2장이 20장에 속하고, 공간별 구성 합산과 타일 이미지의 Rise of Ix Tech 보상으로 이전 세 번째 High Council 타일이 RoI jumpstart 타일의 오전사임을 확정했다. Sardaukar II의 Agent recall 보상(`[Main p. 20]`의 방금-보낸-Agent 제외)을 `CONTRACT_REWARD_RECALL` frame으로 연결했다(codec v76).
- Shaddam Corrino IV를 구현해 인쇄된 Leader 9종을 완결했다: Sardaukar Commander의 setup set-aside와 시장 frame 내 전용 선택(시장 보충 없음, 고갈 시 2 Solari 전환은 OQ-021 convention), Emperor of the Known Universe의 (Solari+troop | 3 Solari→Influence) 선택과 배치 즉시 발효되는 turn 한정 unit 배치 차단(Combat 배치·Maker 소환·Intrigue 배치 option·SummonSandworm 무효)이다(codec v77).
- 검증: Shaddam 포함 CHOAM 조합 30판 random FINISHED 완주 soak에서 set-aside take 27회, signet 선택 85회, contract Agent recall 발동을 확인했고 기본 조합 25판 회귀와 replay 검증을 통과했다.

## 2026-08-29 Leader 세션 요약

- 기본 게임 Leader 8종의 능력과 Signet Ring을 카드 이미지로 검증해 모두 구현했다(codec v72→v75, 테스트 668→727). space 유형 아이콘(City 파란 원, Landsraad 초록 오각형)은 Board Space Guide artwork로 확정했다.
- Gurney(Warmaster recruit, Always Smiling 문턱 6), Amber(Fill Coffers, Desert Scouts retreat), Feyd(분기형 Personal Training 트랙과 Devious Strength), Jessica 양면(Spice Agony memory, Other Memories flip, Water of Life, Reverend Mother board repeat), Margot(Loyalty, City Spy), Muad'Dib(Lead the Way, Unpredictable Foe), Irulan(Imperial Birthright, Chronicler's Insight), Staban(Limited Allies 9장 덱, Smuggle Spice, Unseen Network)이다. 세부와 근거는 `implementation-audits/leaders.md`.
- 새 convention 4건을 OQ-017~OQ-020으로 기록했다(Feyd 맨 오른쪽 칸 무보상, memory 0개 flip 허용, Reverend Mother 반복의 Influence 제외 `[Main p. 7]`, Always Smiling 미회수).
- 기존 버그 수정: Prepare the Way(그리고 Hidden Missive)의 조건부 Agent 효과가 배치와 해결 사이 Influence 하락 시 legal로 제시된 뒤 실패하던 것을 해결 시점 판정의 우아한 무효(no-op)로 바꿨다(`87a9300`, docs/rules/player-turns.md의 자유 순서 조건 판정 문장 인용).
- 검증: Leader 4종 기본 조합 60판 + 신규 4종 조합 25판 random FINISHED 완주 soak(replay 검증 포함)에서 모든 신규 경로의 발동을 이벤트 수로 확인했다.

## 2026-08-29 세션 요약

- Impress(Combat: 검 2 + 비용 3 이하 획득)와 Inspire Awe(Plot: 비용 3 이하 획득, sandworm이 Conflict에 있으면 hand로)를 카드 이미지로 검증해 전사했다. 이전 핸드오프의 "Impress 비용 4"는 오기였다.
- `AcquireCardUpTo(max_cost, to_hand_if)` DSL 보상과 `acquire_intrigue_imperium` / `acquire_intrigue_reserve` 선택 슬롯을 추가했다. Row 보충, acquire box 즉시 처리, Spy 배치 box의 `acquisition_spy` frame 재사용(카드 해결 후 push), Contract 완료 확인을 기존 획득 경로와 공유한다. codec v65.
- Reveal 중 hand로 들어가는 획득은 OQ-015(c)를 확장해 draw와 동일하게 보류한다.
- Call to Arms를 첫 face-up trigger로 전사했다: `IntrigueOption.trigger`, 공개 `PlayerState.intrigue_faceup` 존, `rules/intrigue_triggers.py`의 Reveal 획득 발동과 Reveal 종료 만료(OQ-016), codec v66. Distraction과 Leverage의 카드 이미지 검증도 마쳤다(Leverage 보상에 대한 DIU의 "덱 draw" 기록은 Contract 아이콘 오독이며, Reach Agreement 아이콘과 대조해 확정).
- Distraction을 배치 trigger로 전사했다: `PlayerState.units_deployed_turn` 카운터(6개 배치 지점, Control defense 제외), dispatcher 전이 후 `intrigue_trigger_spy` frame 제시, 다른 플레이어 Spy가 있는 post에의 공유 배치와 recall-first, 거절 시 face-up 유지(OQ-016(c)), codec v67.
- Leverage를 play 시점 조건으로 전사했다: `spice_at_turn_start` 스냅샷 + `spice_spent_turn` 카운터(지출 5지점)로 "이번 turn 총 획득 spice"를 계산하고, 조건 성립 시 Contract 1 + Solari 1을 준다. Harvest의 placement 기준 회계와는 분리 유지. codec v68.
- Endgame Intrigue window(OQ-001 convention)를 열었다: First Player부터 시계 방향 1회 순회, window 안에서 Endgame play와 wild matching 자유 순서, pass가 창을 닫고 마지막 pass가 게임을 끝낸다. 기존 단일 무모호 wild 자동 경로와 `declined_endgame_wild_card_ids`를 대체했다(codec v69). 이어서 Endgame 6종(Crysknife, Desert Mouse, Ornithopter의 spice/flip 이중 절반, CHOAM Profits, Secure Spice Trade, Shadow Alliance)을 전사했다(codec v70). Shadow Alliance의 "상대가 Alliance를 보유한 트랙" 조건을 DIU가 누락한 것을 카드 이미지로 확인해 기록했고, 조건 DSL이 전체 상태를 읽도록 바꿨다. random 4인 게임 60판이 처음으로 FINISHED까지 완주됐다(창 240개, wild 27회, replay 검증 통과).
- Manipulate와 Spring the Trap을 전사해 Intrigue 39개 identity(44장)를 완결했다. Spring the Trap은 Spy 2 recall → 검 7(기존 primitive), Manipulate는 `SetAsideImperiumRowCard` 슬롯 + 공개 `imperium_set_aside` 존 + Reveal 한정 할인 획득 + Reveal 종료 시 `imperium_removed`로 게임 제거(FAQ p. 3). codec v71. random 완주 60판에서 set-aside 21회 = 획득 2 + 만료 19로 보존이 검산됐다. 참고: 기존 Prepare the Way 버그(별도 작업)는 신규 카드로 legal action 목록이 바뀌며 최신 soak의 seed 10146 궤적에서는 더 이상 나타나지 않지만, `ed16d93`에서 그대로 재현된다.
- 알려진 기존 버그(이번 슬라이스와 무관, HEAD `ed16d93`에서 재현): 4인 기본 룰셋 seed 10146 random play에서 Prepare the Way를 Agent 카드로 낼 때 `resolve_agent_card_effect`가 legal로 제시된 뒤 적용 시 "conditional Agent effect is not available"로 실패한다. legal 제공자와 `rules/agent_effects.py:1523` resolver의 조건 판정 불일치로 보이며, 별도 수정 작업으로 분리했다.

## 2026-08-28 세션 요약

- Codex → Claude Code 전환. `AGENTS.md`를 도구 중립으로, `CLAUDE.md`를 진입점으로.
- 리팩토링 A·B: `DecisionFrame.kind`, `rules/frames.py`, 표 기반 dispatcher. 그 과정에서 Covert Operation deadlock, Reserve copy ID 재발급, Spy 공급 판정 버그 수정.
- effect DSL(C 단계)과 Intrigue: Plot 19종·Combat 10종, 선택 슬롯 frame, Intrigue draw 공통 reshuffle 경계, OQ-003·OQ-015 convention.
- 처리량: 입력 불변 hash 가드를 opt-in으로 바꿔 random play 약 45배 가속.
- 코드 리뷰(`/code-review`) 후속 항목은 `refactoring-plan.md` 끝에 있다.
- 교훈: 리뷰 지적을 규칙 문서 확인 없이 반영해 Harvest 계약 판정을 잘못 바꿨다가 되돌림 → `lessons.md`, `AGENTS.md` 규칙 인용 의무.
