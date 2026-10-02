# Epic Game Mode (`epic_game` 옵션)

Rise of Ix 확장의 Epic Game Mode를 4인 Uprising에 적용하는 규칙 명세다. Rise of Ix
확장 자체(Ix board, Tech tile, dreadnought, 새 Imperium·Intrigue·Leader 카드)는
구현 대상이 아니며, 이 모드에 필요한 카드 두 장만 가져온다: 시작 카드 Control the
Spice와 Conflict III 카드 Economic Supremacy. Rise of Ix 없이 이 모드만 켜는 것은
공식 규칙이 아니라 사용자 결정이다([OQ-092](open-questions.md#oq-092--epic-game-mode를-rise-of-ix-없이-uprising에-적용)).

범위 밖: Viscount Hundro Moritani의 setup 순서 `[Rise of Ix p. 10]`(Rise of Ix
Leader), Rise of Ix의 다른 Conflict 카드, 6인 Epic `[Board Guide p. 13]`, Rise of Ix
p. 10의 카드 clarification(Appropriate, Court Intrigue, Ilesa Ecaz, Imperial Bashar,
Second Wave, Treachery — 모두 Rise of Ix 카드).

## 1. 출처

- `[Rise of Ix p. N]`은 Rise of Ix 룰북([sources.md](sources.md))의 PDF 페이지이며 인쇄
  쪽수와 같다. 한국어판(`rise-of-ix-ko`)은 쪽수가 정렬돼 있어 같은 쪽에 같은 내용이
  온다.
- Uprising과의 조합은 Uprising Main Rulebook의 "Adding Rise of Ix" 문단이 다룬다
  `[Main p. 18]`. Uprising은 이전 Dune: Imperium 제품 모두와 호환된다고 적는다
  `[Main p. 18]`.
- 두 카드의 인쇄 텍스트는 카드면(`SourceDocument.CARD_FACE`, 에셋 저장소
  `cards/en/rise-of-ix/`)에서 전사한다.

## 2. 규칙 본문 `[Rise of Ix p. 10]`

- 더 길고 치열한 다인 게임을 원하는 플레이어를 위한 선택 변형이다. 더 긴 게임을
  원하면 Dire Wolf Game Room 컴패니언 앱의 Arrakeen Scouts 모드를 함께 써도 된다고
  권한다(이 엔진에서는 `arrakeen_scouts` 옵션과 그대로 조합된다).
- **10이 아니라 12 Victory Point까지 한다.** 나머지 변경은 모두 setup에서 한다.
  1. Conflict deck을 만들 때 **Conflict I 카드를 쓰지 않는다.** 대신 무작위로 고른
     **Conflict II 5장을 Conflict III 5장 위에** 놓는다.
  2. 각 플레이어는 시작 덱에서 **Dune, the Desert Planet 1장을 빼고 Control the Spice
     1장으로 바꾼다.** Control the Spice는 오른쪽 위에 Epic Game Only 아이콘이 있다.
  3. 각 플레이어는 **Intrigue 카드 1장을 뽑는다.** 원문 괄호: "A player using Viscount
     Hundro Moritani as their Leader should wait until all players have drawn their
     Intrigue card, then use the Intelligence ability." 이 괄호는 Hundro의 Game Start
     능력이 덱에서 다른 draw와 부딪히지 않게 하는 예외지만, 카드를 뽑을 때 Leader가 이미
     정해져 있다는 전제를 담는다(Hundro 자체는 범위 밖이지만 시점의 근거다).
  4. 각 플레이어는 **garrison에 troop 5개**(3개가 아니라)를 두고 시작한다.
- Control the Spice는 색마다 1장씩 있는 시작 카드이고 Epic Game mode에서만 쓴다
  `[Rise of Ix p. 2]`. Epic Game Only 아이콘이 있는 카드는 Epic Game mode에서만
  쓴다 `[Rise of Ix p. 12]`.

## 3. Uprising에 적용할 때

- **Conflict III가 한 장 모자란다.** Uprising의 Conflict 카드는 I 3장, II 9장, III 4장
  이다 `[Main p. 3]`. Main은 Rise of Ix의 Conflict 카드를 섞지 말라고 권하면서, Epic
  Game Mode를 하려면 Conflict III가 한 장 더 필요하므로 **Economic Supremacy**를
  더하라고 지시한다 `[Main p. 18]`. 그래서 Epic 게임의 Conflict deck은 위에서부터
  II 5장, III 5장(Uprising 4장 + Economic Supremacy)이다. Bloodlines를 켜면 II 후보가
  10장이 될 뿐 모양은 같다 `[Bloodlines p. 3]`. Conflict I은 전부(3장, Bloodlines와
  4장) 앞면을 보지 않고 상자로 돌아간다.
- 6인 Epic 문단 `[Board Guide p. 13]`은 범위 밖이지만 같은 구성(Economic Supremacy를
  더한 10장)을 적고, Rise of Ix Conflict를 섞으면 "some Conflicts may not award the
  winner a battle icon"이라고 적는다. Economic Supremacy에는 battle icon이 인쇄돼
  있지 않다(카드면).
- Uprising 시작 덱에는 Dune, the Desert Planet가 2장 있다 `[Main p. 3]`. Epic에서는
  그중 1장이 Control the Spice로 바뀌어 덱은 여전히 10장이다.
- 4인 Uprising의 Score marker는 1에서 시작한다 `[Main p. 5]`. Epic은 이것을 바꾸지
  않고 Endgame 조건의 10을 12로 바꾼다: 라운드가 끝났을 때 12 Victory Point 이상인
  플레이어가 있거나 Conflict deck이 비었으면 Endgame이다 `[Main p. 15]`
  `[Rise of Ix p. 10]`. 점수 트랙은 12까지 인쇄돼 있지만 12점을 넘겨도 된다
  `[FAQ p. 4]`.
- garrison troop 3 `[Main p. 5]`이 5가 되고, supply는 그만큼 줄어 합계 12는 그대로다.

## 4. Immortality와 함께 `[Immortality p. 12]`

- Immortality는 setup에서 Dune, the Desert Planet 2장을 모두 Experimentation으로
  바꾼다 `[Immortality p. 5]`. 그래서 Immortality 룰북의 "IMMORTALITY with Epic Game
  Mode from RISE OF IX" 변형은 **시작 카드 10장 중 어느 것도 Control the Spice로
  바꾸지 않고**, 각 플레이어가 **Control the Spice를 게임 시작 때 자기 discard pile에
  놓는다**고 정한다. 시작 덱은 Experimentation 2장을 포함한 10장 그대로이고, Control
  the Spice는 첫 재셔플 때 덱에 들어간다.
- 이 조합 규칙은 `immortality`와 `epic_game`을 함께 켜면 항상 적용된다(별도 옵션
  아님).

## 5. Go to 11과 함께

- Go to 11(`go_to_11`, Immortality 필요)은 4인 게임에서 Score marker를 0에서 시작하고
  10까지 한다 `[Immortality p. 12]`([immortality.md](immortality.md) 8절). Epic과의
  조합은 어느 문서도 말하지 않는다.
- 사용자 결정: **0에서 시작해 12점에 Endgame**이다
  ([OQ-093](open-questions.md#oq-093--go-to-11과-epic-game-mode를-함께-쓸-때)).
  Go to 11은 시작 점수를, Epic은 종료 점수를 바꾼다.

## 6. 두 카드

### Control the Spice (시작 카드)

카드면 `[Control the Spice card]`; 한국어 이름은 "스파이스를 지배하라"
`[Rise of Ix p. 10]`(한국어판).

- Agent 아이콘: Spice Trade(노란 삼각형) 하나 — Dune, the Desert Planet와 같다.
- Agent box: **spice 1 → 카드 1장 trash + troop 1 recruit.** 화살표 비용이므로 내지
  않아도 되고, 한 턴에 한 번만 고른다 `[Main p. 9]` `[FAQ p. 3]`. 카드 trash 아이콘은
  검은 X이므로 비용을 낸 뒤에도 trash는 선택이다 `[FAQ p. 3]`. trash 후보는 hand,
  discard pile, in play의 카드다 `[Main p. 20]`(Control the Spice 자신 포함).
  recruit한 troop은 Combat space에 Agent를 보낸 turn이면 Conflict에 deploy할 수 있다
  `[Main p. 10]` `[FAQ p. 4]`.
- Reveal box: Persuasion 1, spice 1.
- 구현 관례(규칙 판정 아님): 비용을 내면 troop을 먼저 recruit하고 그 다음 trash를
  고른다(Throne Room Politics와 같은 순서). 두 보상은 서로에게 영향을 주지 않아
  순서가 결과를 바꾸는 경우를 찾지 못했다.

### Economic Supremacy (Conflict III)

카드면 `[Economic Supremacy card]`; 한국어 이름은 "경제적 패권" `[Main p. 18]`(한국어판).

- battle icon 없음, location 없음(control 보상 없음, Shield Wall 보호 없음).
- 1위: Victory Point 1. 그리고 **Solari 6 → Victory Point 1**, **spice 4 → Victory
  Point 1**. 두 화살표는 서로 독립이라 둘 다, 하나만, 또는 하나도 안 낼 수 있다(각
  화살표는 한 번씩) `[Main p. 9]` `[FAQ p. 3]`.
- 2위: Victory Point 1.
- 3위: spice 2, Solari 2.
- sandworm으로 보상이 두 배가 되면 각 화살표 비용도 두 번째로 내고 효과를 한 번 더
  얻을 수 있다 `[Main p. 14]`([combat-and-round-end.md](combat-and-round-end.md) 4절).
- battle icon이 없으므로 이긴 플레이어는 카드를 supply에 앞면으로 두지만 어떤
  카드와도 짝을 이루지 않고, Endgame의 wild 매칭 상대도 아니다 `[Main pp. 14, 20]`.
  "battle icon" 수를 세거나 battle icon을 바꾸는 효과(Ornithopter Fleet 등)에서의
  취급은 [OQ-094](open-questions.md#oq-094--battle-icon이-없는-conflict-카드)다.

## 7. 프로젝트 관례와 사용자 결정

- `RulesetConfig.epic_game`은 다른 옵션과 독립이다(OQ-092). 체크포인트 식별자 토큰은
  `+epic`(`+go11` 뒤, `+scouts` 앞)이다.
- 브라우저 새 게임 화면의 체크박스는 **기본으로 켠다**(사용자 결정 2026-09-28).
  엔진 `RulesetConfig`와 CLI(`--epic`)의 기본값은 꺼짐이라 학습·sweep 기준선은
  바뀌지 않는다. checkpoint·search AI 좌석도 Epic 게임에 앉을 수 있다.
- setup Intrigue 1장은 Intrigue deck을 섞은 뒤 First Player부터 좌석 순서로 맨 위에서
  한 장씩 나눈다. 룰북은 순서를 정하지 않으며, 섞인 덱이므로 분포는 같다. 새 우연
  결정은 없다.
- 나누는 **시점**은 모든 Leader가 정해진 뒤다(2절 3의 Hundro 문장 `[Rise of Ix p. 10]`).
  고정 Leader setup은 Leader setup 뒤에, [OQ-007](open-questions.md#oq-007--leader-선택-절차)
  draft는 **마지막 pick 뒤**(Contract 시장을 나누는 때)에 나눈다. 그래서 draft 중에는 아무도
  Intrigue를 들고 있지 않다. Leader의 Game Start 선택(Steersman Y'rkoon의 Navigation, Kota
  Odax of Ix의 Secret Project)은 두 경로 모두 카드를 받은 뒤다 — 공식 문서는 Hundro만 정하고
  나머지는 침묵하므로 Hundro의 순서로 통일한 사용자 판정이다
  ([OQ-096](open-questions.md#oq-096--epic-setup-intrigue와-leader의-game-start-선택-순서)). 2026-10-02 전에는 draft 경로가 draft 전에 나눠 자기 카드를 보며 Leader를
  골랐다(사용자 지적과 결정 "고쳐야지", 2026-10-02, codec v128; [lessons](../lessons.md)).
- 한국어 카드 이름 "스파이스를 지배하라"·"경제적 패권"은 한국어판 룰북 표기를 쓴다
  (사용자 결정 2026-09-28; [glossary-ko.md](glossary-ko.md)). TTS 한글화 모드의 카드면
  표기 "스파이스를 조종하라"는 쓰지 않는다.

## 8. 구현 상태

2026-09-28 구현(브랜치 `epic-game-mode`). 코드 위치와 테스트는
[implementation-audits/epic-game-mode.md](../implementation-audits/epic-game-mode.md).
