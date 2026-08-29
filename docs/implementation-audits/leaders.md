# Leader ability audit

Leader identity와 setup은 `content/uprising/leaders.py`, 능력 규칙은
`rules/leader_abilities.py`가 소유한다. Signet Ring 일반 규칙은
[`rules/player-turns.md`](../rules/player-turns.md)와
[`rules/uprising-systems.md`](../rules/uprising-systems.md)의 `[Main pp. 6, 20]`
문장을 따른다. 능력이 구현되지 않은 Leader는
`IMPLEMENTED_ABILITY_LEADER_IDS` 밖에 있고, dispatcher가
`leader_signet_is_implemented`로 해당 좌석의 Signet Ring 배치를 제시하지
않는다(과거의 `UNIMPLEMENTED_AGENT_EFFECTS` 전면 차단을 대체).

## 검증 방법

각 Leader의 카드 이미지(카탈로그 URL은 `leaders.py`)를 2026-08-29에 직접
판독해 전사했다. DIU `data/leader_data/*.json`은 부트스트랩 참고로만 썼고,
이미지와 충돌하면 이미지를 따랐다. 아이콘 기준: 회색 정육면체 = troop,
회색 원기둥 = Spy, 위 화살표가 붙은 원기둥 = Spy recall, 주황 육각형 = Spice,
은화 = Solari, 파란 물방울 = water.

## 구현된 Leader (2026-08-29)

### Gurney Halleck

- **Always Smiling** — "Reveal Turn: If you have 6* or more strength in the
  Conflict: 1 Persuasion" (*6인전 10). 4인 게임 값 6을
  `ALWAYS_SMILING_STRENGTH`로 고정했다. 전이 후 dispatcher 훅
  (`grant_leader_reveal_passives`)이 자신의 Reveal frame이 열려 있는 동안
  `combat_strength ≥ 6`이 처음 성립한 시점에 Persuasion 1을 부여하고 frame에
  기록해 중복 부여를 막는다. 부여 뒤 strength가 6 밑으로 내려가도 회수하지
  않는다(OQ-020 convention).
- **Warmaster(Signet)** — troop 1 recruit. Combat space 방문 turn에는 다른
  recruit와 같은 경로로 배치 가능 수에 합산된다 `[FAQ p. 4]`. supply가 비면
  recruit 가능한 만큼만 얻는다(엔진 공통 `recruit_troops` 동작).

### Lady Amber Metulli

- **Desert Scouts** — "Reveal Turn: You may retreat one of your troops."
  Reveal frame에서 선택 액션(`retreat_leader_troop`)으로 제시하고, 카드
  텍스트가 troop 하나를 대상으로 하므로 Reveal turn당 1회로 고정한다. 마지막
  unit이 빠지면 sword strength가 더 이상 세지지 않는 기존 retreat 규칙과 같은
  재계산을 쓴다 `[Main pp. 12-13, 20]`.
- **Fill Coffers(Signet)** — Solari 1, 그리고 "If you have an Alliance:"
  Spice 1. Alliance 보유는 `alliance_faction_ids` 비어 있지 않음으로
  판정한다(임의 Faction).

### Feyd-Rautha Harkonnen

- **Devious Strength** — "Reveal Turn: [Spy recall] → 검 2." arrow
  비용-효과이므로 Reveal turn당 1회 `[Main p. 20]` `[FAQ p. 3]`. 배치된 Spy
  하나를 supply로 되돌리고 optional sword 2를 더한다. unit이 Conflict에
  없으면 세지 않는 것은 기존 Reveal sword 처리와 동일하다.
- **Personal Training(Signet)** — "Move your Feyd token one space to the
  right on your Training track, earning the reward on the new space." 트랙은
  분기 경로다: start → {1 Solari→trash | Spy} → trash → {trash | Spy →
  Spice 2} → 최종(troop 1 + Spy). 구조와 보상은 카드 이미지에서 전사해
  `FEYD_TRAINING_TRACK`(content)에 고정했다. token은 setup 때 맨 왼쪽,
  맨 오른쪽 도달 후 그대로 남는다 `[Main p. 17]`. 오른쪽 끝에서는 이동할 새
  공간이 없으므로 보상이 없다(OQ-017 convention). trash 대상은 hand,
  discard pile, in play `[Main p. 20]`이고, Spy 배치는 supply가 비면
  recall-first `[Main pp. 11, 20]`를 따른다. 관측소 13곳 > 전체 Spy 12개라
  Spy 배치가 막히는 상태는 성립하지 않는다.
- DIU의 트랙 데이터는 위쪽 trash 분기를 지나도 Spice 칸을 통과하는 평탄
  구조였으나, 카드 이미지의 연결선은 위 분기가 Spice 칸을 건너뛰고 바로 최종
  칸으로 이어짐을 보여 준다. 이미지를 따랐다.

### Lady Jessica / Reverend Mother Jessica (양면)

- setup은 Lady Jessica 면으로 시작한다 `[Main p. 17]`;
  `PlayerState.leader_face_id`가 현재 면을 공개 상태로 들고 있고, 단면
  Leader는 자기 identity를 값으로 가진다.
- **Spice Agony(Signet, Lady 면)** — "1 Spice → Intrigue 1 draw, 그리고
  supply의 troop 1개를 board의 Bene Gesserit 구역으로(이제 memory)." memory는
  `PlayerState.memories`로 세며 troop 12개 불변식에 포함된다. supply에 troop이
  없으면 recruit 계열의 기존 관행대로 그 부분만 소실되고 Intrigue draw는
  이행한다. 지불은 pay/decline 직렬 선택으로 제시해 legal/apply 판정이
  갈라지지 않게 했다.
- **Other Memories(Lady 면)** — Bene Gesserit board space에 Agent를 보낼 때
  memory 전부를 supply로 되돌리고 장당 personal card 1장을 draw한 뒤
  Reverend Mother 면으로 flip할 수 있다. memory 0개여도 사용(즉 flip)할 수
  있다(OQ-018 convention). flip한 바로 그 turn에 Reverend Mother 능력을 쓸 수
  있으므로 `[FAQ p. 3]`, 사용 시 같은 배치에 대한 board repeat 창을 연다.
- **Water of Life(Signet, RM 면)** — "1 Spice → water 1."
- **Reverend Mother(RM 면)** — "Once during each turn", Bene Gesserit 또는
  Fremen board space에 Agent를 보내면 water 1을 지불해 "그 space에 인쇄된
  효과"를 반복할 수 있다. 인쇄 효과가 한 번 해결된 뒤에만 반복을 제시하고,
  반복은 `pending_board_effect`를 다시 열어 기존 board 효과 경로(espionage의
  선택 포함)를 재사용한다. Faction Influence는 space 인쇄 효과가 아니라
  Agent를 보낸 데 따른 Faction 규칙이므로 반복하지 않는다 `[Main p. 7]`
  (OQ-019). space 비용 재지불도 없다. `secrets`·`desert_tactics`는 board
  효과 미구현으로 dispatcher가 숨기므로 현재 반복 대상은 espionage와
  fremkit이다.

## 남은 Leader

Lady Margot Fenring, Muad'Dib, Princess Irulan, Staban Tuek는 아직
`IMPLEMENTED_ABILITY_LEADER_IDS` 밖이다. Margot/Irulan의 `reach 2` 판정은
`[Main p. 17]`에 있다. Shaddam Corrino IV는 CHOAM 전용이며 set-aside
Sardaukar Contract 경로(OQ-010, OQ-011 참고)와 함께 구현한다
`[Main p. 17]` `[FAQ p. 3]`.

## 회귀 테스트

`tests/unit/rules/test_leader_abilities.py`가 signet 자동 해결, Feyd 트랙
분기·단계·최종 칸, Devious/Desert Scouts의 Reveal 액션과 1회 제한, Always
Smiling 문턱과 중복 방지, Jessica 지불·flip·repeat 경로, setup 면 배정을
고정한다. random 4인 완주 soak에서 네 Leader의 모든 신규 이벤트가 발동함을
확인했고 replay 검증을 통과했다.
