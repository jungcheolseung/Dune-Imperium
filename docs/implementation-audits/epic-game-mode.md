# Epic Game Mode 구현 감사

기준일: 2026-09-28~29(브랜치 `epic-game-mode`). 규범 근거는
[`rules/epic-game-mode.md`](../rules/epic-game-mode.md)와 OQ-092~094이며, 모든 동작은
`RulesetConfig(epic_game=True)`에서만 켜진다. Rise of Ix 확장 자체는 구현하지 않고 이
모드가 쓰는 카드 두 장만 가져왔다(OQ-092, 사용자 결정).

## 검증 방법

- 룰북: Rise of Ix 룰북 영·한(`rise-of-ix`, `rise-of-ix-ko`)을 공식 URL에서 받아 checksum을
  고정하고(`scripts/official-rule-sources.json`) p. 10(모드 본문), p. 2(구성물), p. 12(Epic
  Game Only 아이콘)를 텍스트로 읽었다. Uprising 쪽 근거는 Main p. 18("Adding Rise of Ix"의
  Economic Supremacy 지시)과 Board Guide p. 13(6인 Epic, 범위 밖이지만 icon 없는 Conflict를
  언급), Immortality p. 12(Immortality와 함께 쓸 때)다.
- 카드: 에셋 저장소 `cards/en/rise-of-ix/starting/Control the Spice.webp`(이번에
  `imperium/`에서 옮김)와 `cards/en/rise-of-ix/conflict/Economic Supremacy.webp`를 직접
  판독했고, Control the Spice는 BGG 카드 인벤토리 시트의 starting 행("1 Spice --> Trash a
  card, +1 Troop", Reveal 1 Persuasion, +1 Spice)과 대조했다. 수량은 색마다 1장 `[Rise of
  Ix p. 2]`.
- 한국어 이름: 한국어판 룰북 표기 "스파이스를 지배하라" `[Rise of Ix p. 10]`·"경제적 패권"
  `[Main p. 18]`(사용자 결정). TTS 한글화 모드 3025517639의 카드면은 "스파이스를 조종하라"로
  달라 쓰지 않았고, 그 모드의 Economic Supremacy는 영어 시트다. 한글 카드 그림은 넣지 않았다
  (`ko/`가 없으면 영어 그림으로 폴백).

## 카드 전사

| 카드 | 인쇄 내용 | 구현 |
| --- | --- | --- |
| Control the Spice (시작 카드) | Spice Trade 아이콘. Agent: spice 1 → 카드 trash(검은 X) + troop. Reveal: Persuasion 1, spice 1 | `content/uprising/starting_cards.py` `CONTROL_THE_SPICE`, `PersonalCardAgentEffect.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT`. 공용 `pay_agent_card_spice`/`decline_agent_card_payment`로 지불을 고르고(1 spice가 없으면 거절만), 내면 troop을 recruit한 뒤 공용 optional-trash frame(`trash_optional_card`/`decline_optional_trash`)을 연다(`rules/agent_effects.py` `_apply_control_the_spice_payment`). trash는 선택 `[FAQ p. 3]`, 후보는 hand·discard·in play와 자기 자신 `[Main p. 20]`. Combat space에서는 새 troop을 deploy할 수 있다 `[Main p. 10]` `[FAQ p. 4]`. troop 먼저, trash 나중은 Throne Room Politics와 같은 구현 관례 |
| Economic Supremacy (Conflict III) | battle icon·location 없음. 1위 VP 1 + Solari 6 → VP 1 + spice 4 → VP 1. 2위 VP 1. 3위 spice 2·Solari 2 | `content/uprising/conflicts.py`(`epic_only=True`, `battle_icon=None`). `ConflictReward`가 한 줄의 두 화살표를 허용하고, `rules/combat.py`가 Solari → spice 순(인쇄 순서)으로 따로 묻는다. sandworm이면 각 화살표를 한 번 더 묻는다 `[Main p. 14]` |

## 구현 항목

| 항목 | 구현 | 고정하는 테스트 |
| --- | --- | --- |
| 옵션 | `RulesetConfig.epic_game`(다른 옵션 불필요), 식별자 `+epic`(`+go11` 뒤, `+scouts` 앞), `endgame_victory_points`(12/10), `starting_garrison_troops`(5/3) | `tests/unit/test_config.py`(모든 조합 왕복) |
| Conflict deck | `conflict_setup_decisions(epic_game=)`: III 5장 중 5장(4장 + Economic Supremacy), II 5장, I 결정 없음. I은 전부 unused(기본 7장, Bloodlines 9장). II·III 결정 id는 그대로 | `tests/unit/rules/test_epic_game.py` |
| 시작 카드 | `starting_deck_entries`/`starting_discard_entries`: Epic만이면 Dune 1장 → Control the Spice, Immortality와 함께면 덱 그대로 + discard pile에 Control the Spice `[Immortality p. 12]` | 같은 파일 |
| garrison·Intrigue | troop 5/supply 7. 섞인 Intrigue deck 맨 위에서 First Player부터 좌석 순서로 1장씩(구현 관례, 새 chance 결정 없음). 고정 Leader·draft 두 경로 모두, 기록 재생 포함 | 같은 파일 |
| Endgame | `rules/phases.py`가 `config.endgame_victory_points`와 비교. Go to 11과 함께면 0 → 12(OQ-093) | `test_the_epic_endgame_opens_at_twelve` 외 |
| icon 없는 Conflict | `battle_icon=None`은 "인쇄된 icon 없음". 도착 매칭·Endgame wild·icon Intrigue 뒤집기·Ornithopter Fleet·The Beast's Spoils에서 빠지고 Grasp Arrakis는 뒤집을 수 있다(OQ-094) | `tests/unit/rules/test_economic_supremacy.py` |
| 관측 v26 | 개인 카드 우주 끝에 Control the Spice, Conflict 우주 끝과 battle card 우주의 Objective 뒤에 Economic Supremacy, 마지막에 `epic_game` 플래그(4,587 → 4,611). 옵션을 끈 관측의 옛 열은 master와 같음을 스크래치 비교로 확인했다. slot 표 1,140행(`conflict:economic_supremacy` 추가, SLOT_VERSION 유지) | `tests/adapters/test_observation_encoding.py`, `tests/unit/training/test_checkpoint.py`(v25 파일 이관 뒤 같은 출력), `test_slot_network.py` |
| codec v121 | Epic 카탈로그에만 Control the Spice 템플릿·Economic Supremacy `flip_battle_card`(Grasp Arrakis)·optional-trash 템플릿이 붙는다. Epic을 끈 72개 룰셋의 카탈로그는 master와 바이트 단위로 같다(스크래치 digest) | `tests/adapters/test_action_codec.py` |
| AI 좌석 | `load_network_agent(path, config)`: 게임 카탈로그에 파일이 모르는 템플릿이 있으면 `load_checkpoint(ruleset=...)`가 정책 head를 템플릿 identity로 옮기고 새 템플릿은 0에서 시작한다(코덱 이관과 같은 방식). 덮이는 게임은 파일 그대로. `make_agent(kind, seed, config)`를 서버·토너먼트·problem set이 넘긴다. 부수 효과로 Immortality가 없는 게임에서 사막 행성 듄을 만나면 멈추던 v111 체크포인트 좌석도 풀렸다 | `tests/unit/training/test_torch_policy.py`, `test_checkpoint.py` |
| 서버·저장 | `CreateGameRequest`·요약·저장 문서의 `epic_game`(없으면 꺼짐, SAVE_FORMAT_VERSION 유지). 좌석 제한 없음 | `tests/server/test_app.py`, `test_saves.py`, `test_sessions.py` |
| 브라우저 | 새 게임 화면의 "에픽 게임 모드" 체크박스(기본 켜짐, 다른 옵션과 무관, Go to 11 다음), 머리글 배지. Go to 11 설명의 "종료 조건 10점은 그대로"를 "종료 점수는 그대로"로. `pay_agent_card_spice` 라벨은 "{spice} 지불 (카드 효과 비용)"으로 중립화하고 버튼에는 서버 detail이 카드별 효과를 쓴다(Smuggler's Haven·Control the Spice) | `scripts/e2e/setup_options.py`, `effect_text.py`, `tests/unit/display/test_actions.py` |
| CLI | sweep·tournament `--epic`, `sweep_specs`/`tournament_specs(epic_game=)`, sweep 커버리지가 `+epic` 카탈로그를 읽는다 | `tests/integration/test_sweep.py`, `test_tournament.py` |

## 검증 결과

2026-09-29 브랜치 묶음 검증: pytest 2,813, Ruff·mypy 통과, 브라우저 E2E 30/30(`run_all.py`;
Epic 체크박스가 기본으로 켜져 있어 폼 기본값을 쓰는 스크립트는 모두 Epic 게임을 돈다).

- `--epic --soundness-interval 25` sweep 1,200판 실패 0: random 400·heuristic 200(base·CHOAM),
  Immortality·Go to 11·프로모·Bloodlines·Tech random 300, 같은 확장 + leader draft heuristic
  100(CHOAM), Bloodlines·Tech·Arrakeen Scouts random 200. 라운드 중앙값 10(최소 8) — baseline
  정책으로는 12점 전에 Conflict deck이 먼저 떨어지는 게임이 대부분이다.
- v111 체크포인트(`ext-v111/C/iteration_07081.pt`) 좌석: 전 확장 + Go to 11 + Epic 4좌석 2판,
  전 확장 + Epic 1좌석 2판, base + Epic 1좌석 2판, base 1좌석 2판 — 불법 행동 0.

## 알려진 한계

- Economic Supremacy의 두 화살표는 같은 `pay_combat_reward`/`decline_combat_reward` 행동을
  쓰고, 지금 묻는 비용이 Solari인지 spice인지는 frame 문맥에만 있고 관측에는 없다. 엔진은
  맞지만 학습된 정책은 순서(Solari 먼저)로만 구별할 수 있다. Epic 게임을 학습에 넣을 때 다시
  본다.
- 행동 로그의 `pay_agent_card_spice` 줄은 중립 라벨이고, 무엇을 냈고 얻었는지는 그 아래
  이벤트 줄이 말한다(로그 단계는 detail을 저장하지 않는다).
