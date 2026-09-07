# Bloodlines 확장

Bloodlines는 Dune: Imperium — Uprising의 확장이다. 이 문서는 4인 Uprising 게임에 Bloodlines를 더했을 때 바뀌거나 추가되는 규칙을 구현 단위로 정리한다. 규범 근거는 [공식 Bloodlines 룰북](sources.md)이며, `[Bloodlines p. N]`은 그 PDF의 페이지 번호다(인쇄된 쪽수와 같다). 프로젝트는 확장을 `RulesetConfig(bloodlines=True)` 옵션으로, 함께 든 Tech Module을 `tech_module=True` 옵션(Bloodlines 필요)으로 취급하며 둘 다 기본값은 꺼짐이다.

범위 밖: 1·2인 Rivals 규칙 `[Bloodlines pp. 8-9]`, 6인 팀전 `[Bloodlines p. 10]`, 원본 Dune: Imperium과의 조합 `[Bloodlines p. 3]`, Rise of Ix와의 조합 `[Bloodlines p. 7]`. 2025-01-13 FAQ에는 Bloodlines 항목이 없다(2026-09-07 확인; "Sardaukar Commander" 검색 결과는 Shaddam Corrino IV의 능력명뿐이다).

## 1. 구성물

- Imperium 카드 32장(그중 5장은 CHOAM Module 전용, 2장은 Tech Module 전용), Intrigue 카드 18장(1장 CHOAM 전용, 2장 Tech 전용), Conflict 카드 2장(Conflict I 1장, Conflict II 1장), Sardaukar Commander 7개(플라스틱 7·나무 7 중 한 종류만 사용), Sardaukar Commander Skill 14장, Leader 9장(1장은 Tech Module 전용). `[Bloodlines p. 2]`
- Leader 전용 구성물: Esmar Tuek의 Tuek's Sietch board space, Piter De Vries의 Twisted Intrigue 12장, Steersman Y'rkoon의 Navigation 카드 10장, Chani의 Tactics token. `[Bloodlines p. 2]`
- CHOAM Module과 함께 쓸 때: Imperium 5장을 Imperium deck에, Intrigue Coercive Negotiation을 Intrigue deck에, contract token 8개를 기존 contract에 섞는다. Tech Module도 쓰면 CHOAM Transports Tech tile을 다른 Tech tile과 섞는다. `[Bloodlines p. 2]`
- 새 contract 중 Earn any Alliance는 아직 갖고 있지 않은 Alliance token을 다음에 가져갈 때 완료된다. 새 Immediate contract는 trash할 Intrigue 카드가 없으면 가져갈 수 없다. `[Bloodlines p. 2]`

## 2. Setup 변경

Uprising setup에 다음 단계를 더하거나 바꾼다. `[Bloodlines p. 3]`

1. Sardaukar Commander 7개 중 다섯 개를 board의 Sardaukar, Dutiful Service, Deliver Supplies, High Council, Gather Support에 하나씩 놓는다(Agent를 놓을 자리는 남긴다). 4인 게임에서는 여섯 번째를 Assembly Hall에 놓는다. 마지막 하나는 bank에 둔다(Imperium 카드 Sardaukar Standard가 사용). `[Bloodlines p. 3]`
2. Skill 14장을 face-down으로 shuffle해 board 옆에 stack으로 두고, 그중 4장을 face-up으로 deal한다. `[Bloodlines p. 3]`
3. 새 Conflict 카드 2장을 기존 카드에 더한다. Conflict deck은 여전히 Conflict I 1장(맨 위), II 5장, III 4장(맨 아래)의 10장으로 만들고, 쓰지 않은 카드는 보지 않고 box로 돌려보낸다. `[Bloodlines p. 3]`
4. Intrigue 15장을 Intrigue deck에, Imperium 25장을 Imperium deck에(Imperium Row를 만들기 전에) 섞고, 새 Leader 8장을 기존 Leader에 더한다. Leader는 새 것과 기존 것을 자유롭게 조합해 고를 수 있다. `[Bloodlines p. 3]`

## 3. Sardaukar Commander

### 획득과 recruit

- 자신의 turn에 Sardaukar Commander가 있는 board space에 Agent를 보내면, 2 Solari를 지불해 그 Commander를 acquire하고 즉시 recruit할 수 있다. 이것은 그 space의 효과이며, 다른 board space·카드 효과와 원하는 순서로 처리한다. `[Bloodlines p. 4]`
- Commander를 acquire할 때마다 Skill 하나를 얻는다. face-up 4장 중 하나를 골라 자신의 supply에 놓고(모두에게 공개), 이미 supply에 있는 것과 같은 Skill은 고를 수 없다. 고른 뒤 stack에서 한 장을 face-up으로 보충한다. `[Bloodlines p. 4]`
- supply의 Commander는 일반 수단으로 recruit할 수 없다. 대신 turn(Agent 또는 Reveal)마다 한 번, 2 Solari를 지불해 supply의 Commander 하나를 garrison으로(이번 turn에 Combat space에 Agent를 보냈다면 Conflict로) recruit할 수 있다. 이때는 acquire가 아니므로 Skill을 고르지 않는다. 한 turn에 4 Solari로 두 개를 recruit할 수는 없다. `[Bloodlines p. 4]`

### 유닛으로서의 취급

- recruit한 Commander는 대부분 다른 유닛과 같이 쓴다. garrison에 두거나, 이번 turn에 Combat space에 Agent를 보냈다면 Conflict에 deploy할 수 있다. 나중에 garrison에 있을 때 Combat space에 Agent를 보내면 garrison에서 deploy하는 `up to two` 유닛 중 하나가 될 수 있다. `[Bloodlines p. 4]`
- Commander는 Conflict에서 strength 2인 "troop"이다. troop을 대상으로 하는 효과(예: Go to Ground의 retreat)는 Commander에도 적용된다. `[Bloodlines p. 4]`
- Combat이 해결되고 보상이 지급되면 Commander는 소유자의 supply로 돌아간다. `[Bloodlines p. 4]`

### Sardaukar Commander Skill

- Conflict에 자신의 Commander가 하나 이상 있는 동안 자신의 모든 Skill 효과가 활성이다. 각 Skill은 Reveal turn의 보너스이거나 Combat 해결 때의 추가 strength다. Commander가 여러 개여도 각 Skill은 라운드당 한 번만 작동한다. `[Bloodlines p. 4]`
- Commander를 모두 retreat시키면 Conflict에 Commander가 없어져 Skill의 추가 strength(예: Canny)를 받지 못한다. `[Bloodlines p. 4]`
- Skill 14장은 7종 2장씩이다(원본 Dune: Imperium과 쓸 때 "Fierce 2장"을 제외하라는 지시에서 확인). 각 tile의 인쇄 효과는 다음과 같다. Landsraad와 Emperor 아이콘은 에셋 저장소의 아이콘과 대조했다. `[Bloodlines p. 3]` `[Skill tile faces]`

| Skill | 인쇄 효과 | 종류 |
| --- | --- | --- |
| Canny | Landsraad board space에 자신의 Agent가 있으면 strength 2 | Combat strength |
| Charismatic | Reveal Turn: Persuasion 1 | Reveal 보너스 |
| Desperate | Reveal Turn: 이 tile을 trash → strength 3 | Reveal 보너스(선택형 arrow) |
| Driven | Reveal Turn: spice 1 | Reveal 보너스 |
| Fierce | strength 1; 상대 누군가의 sandworm이 Conflict에 있으면 strength 1 추가 | Combat strength |
| Hardy | Reveal Turn: water 1 | Reveal 보너스 |
| Loyal | Emperor Influence 3 이상이면 strength 2 | Combat strength |

## 4. 새 아이콘과 용어

- **Spy with Deep Cover**: 일반 규칙대로 Spy 하나를 놓되, 놓을 때 상대의 Spy를 무시할 수 있다. 자신의 Spy가 이미 있는 post에는 놓을 수 없다. `[Bloodlines pp. 5, 12]`
- **Command (6+)**: Reveal box에 적힌 효과로, 그 Reveal turn에 Persuasion을 6 이상 생성했을 때만 사용한다(그 카드 자신의 Persuasion 포함). `[Bloodlines pp. 5, 12]`
- **Combat 아이콘**: Combat space에 Agent를 보낸 것처럼 이번 turn에 troop을 Conflict에 deploy할 수 있다 — 이번 turn에 recruit한 유닛 전부와 garrison에서 최대 두 개. 한 turn에 이 아이콘이 둘 이상이어도 garrison에서 deploy하는 수는 두 개를 넘지 못한다. Reveal turn에서도 쓸 수 있다(Disruption Tactics 예시). `[Bloodlines pp. 5, 12]`
- **wild battle icon(clarification)**: Endgame에서 wild battle icon은 supply의 다른 아무 battle icon과 짝지을 수 있다 — 세 표준 아이콘 중 하나 또는 또 다른 wild. 짝지은 두 장을 face-down으로 뒤집고 1 VP를 얻는다. Uprising Main p. 20의 "세 종류 중 하나"는 wild가 하나뿐이던 시절의 서술이다. `[Bloodlines p. 5]`
- **Trash an Intrigue card**: hand의 Intrigue 카드 1장을 trash한다. `[Bloodlines p. 12]`
- **Discard**: hand의 카드 1장을 discard한다. 명시하지 않는 한 Intrigue 카드는 대상이 아니다. `[Bloodlines p. 12]`
- **Bloodlines 아이콘**: 구성물 오른쪽 아래의 표시로 참고용일 뿐이다. **Tech Module 아이콘**은 Tech Module에서만 쓰는 카드, **Twisted Intrigue** 표시는 Piter De Vries 전용 Intrigue를 뜻한다. `[Bloodlines p. 12]`

## 5. Tech Module

### Setup

- Ixian Embassy board를 game board 옆에 놓는다. Tech tile 18장을 face-down으로 shuffle해 6장씩 세 stack으로 나눠 Ixian Embassy board의 세 칸에 놓고 각 stack의 맨 위를 face-up으로 뒤집는다. 제외한 tile이 있으면 최대한 고르게 나눈다. `[Bloodlines p. 6]`
- CHOAM Module 없이 쓰면 CHOAM Transports를 제외한다. Tech 전용 Intrigue 2장과 Imperium 2장을 각 deck에 섞고, Kota Odax of Ix를 Leader로 고를 수 있다. `[Bloodlines p. 6]`

### Tech tile 획득

- Acquire Tech 아이콘이 Tech tile을 얻는 유일한 방법이다. 기본 경로는 Ixian Embassy board 위에 적혀 있다: Landsraad board space에 Agent를 보낸 turn에 Tech tile 하나를 acquire할 수 있다. 보유 수 제한은 없다. `[Bloodlines pp. 7, 12]`
- acquire할 때는 세 stack 맨 위의 face-up tile 중 하나를 골라 표시된 spice 비용을 내고 자신의 supply(공개)에 둔 뒤 그 stack의 다음 tile을 face-up으로 뒤집는다. stack이 비면 남은 게임 동안 선택지가 줄어든다. `[Bloodlines p. 7]`
- 비용 감소는 두 가지이며 비용은 0 아래로 내려가지 않는다. High Council 자리가 있으면 Ixian Embassy board의 할인으로 tile마다 spice 1을 덜 낸다. 카드의 Tech Discount 아이콘은 tile 하나를 spice 1 할인으로 acquire하게 하며 High Council 할인과 합칠 수 있지만, Tech Discount 아이콘 둘 이상을 합칠 수는 없다. `[Bloodlines pp. 7, 12]`

### Tech tile 사용

- Tech tile의 능력은 Reveal turn, Conflict 승리, 게임 종료 등 여러 시점에 작동한다. Flip 아이콘이 있는 능력은 자신의 turn에 사용하며 라운드당 한 번뿐이다. 사용하면 tile을 face-down으로 뒤집고, 다음 라운드의 Round Start에 다시 face-up으로 돌린다. `[Bloodlines pp. 7, 12]`
- tile의 구성: spice 비용, 이름, acquire 효과(acquire할 때 한 번만; 없는 tile도 있다), 능력, Rival Tech 표시(솔로 전용). `[Bloodlines p. 7]`
- Forbidden Weapons에서 strength 3 선택지를 고르면 Influence가 1 이상인 Faction에서 Influence 1을 잃어야 한다(가능하면). `[Bloodlines p. 12]`
- Ornithopter Fleet을 가진 동안 자신의 모든 battle icon(wild 포함)은 Ornithopter로 취급한다. acquire하는 순간 battle icon 일치가 일어날 수 있고, Crysknife·Desert Mouse Intrigue로 VP를 얻을 수 없다. `[Bloodlines p. 12]`

## 6. Leader 관련 clarification

- Chani: setup 때 Leader에 인쇄된 track의 인원수 칸에 Tactics token을 놓는다. token이 맨 오른쪽 칸에 도달하면 시작 칸으로 되돌려 reset한다. track 끝을 넘길 만큼 troop을 잃거나 retreat해도 시작 칸으로 reset할 뿐 초과분만큼 더 나아가지 않는다. `[Bloodlines p. 12]`
- Count Hasimir Fenring: Intrigue 카드를 trash할 때 Solari를 얻지 않는다. `[Bloodlines p. 12]`
- Esmar Tuek: setup 때 Tuek's Sietch board space를 game board 옆에 놓는다. Maker board space이므로 spice가 쌓인다. Signet Ring으로 Tuek's Sietch에 bonus spice를 놓고 같은 turn에 그곳으로 보낸 Agent로 그 spice를 가져갈 수 있다. `[Bloodlines p. 12]`
- Steersman Y'rkoon: 자신의 face-down Navigation 카드를 언제든 볼 수 있다. Influence를 잃었다가 다시 얻으면 같은 Faction에서 Influence 2에 여러 번 도달할 수 있고, 그때마다 Navigation 카드를 play한다. `[Bloodlines p. 12]`

## 7. 기존 명세와의 관계

- Commander는 [player-turns.md](player-turns.md)의 recruit·deploy 규칙과 [combat-and-round-end.md](combat-and-round-end.md)의 strength·정리 규칙 위에 얹힌다. 이 문서가 다르게 정한 것(supply에서의 recruit는 지불식·turn당 1회, 정리 때 supply로 복귀)만 우선한다.
- wild battle icon의 Endgame 매칭은 [combat-and-round-end.md](combat-and-round-end.md) 5절의 Main p. 20 문장을 이 문서 4절의 clarification으로 넓힌다. 옵션을 끈 게임에서는 wild가 Propaganda 하나뿐이라 결과가 같다.
- 공식 문서가 침묵하는 판정은 [open-questions.md](open-questions.md)에 기록한다.

## 8. 구현 상태

- 2026-09-07 슬라이스 1: `RulesetConfig(bloodlines=True)`·`tech_module=True` 옵션과 이 명세.
- 2026-09-07 슬라이스 2: 3절의 Sardaukar Commander 전부 — setup(6칸 + bank, Skill 14장 셔플·4장 공개), 방문한 space의 Commander를 2 Solari에 획득하며 Skill 선택(`acquire_sardaukar_commander`, 거절 `decline_sardaukar_commander`), supply에서 turn당 1회 지불 recruit(`recruit_sardaukar_commander`, Agent turn의 효과 frame과 Reveal turn), 기본 배치·회수에 Commander 포함(`deploy_commanders`/`withdraw_commanders`, garrison 2개 한도 공유), strength 2와 Skill의 Combat strength(Canny·Fierce·Loyal, 조건 변화 시 재계산), Reveal 보너스(Charismatic·Driven·Hardy), Desperate의 trash(`trash_skill_for_strength`), Combat 정리 때 supply 복귀, 관측 v6, codec v90. 세부와 미완 경계는 [implementation-audits/bloodlines.md](../implementation-audits/bloodlines.md). 남은 3절 항목: 기존 "troop" 효과(Intrigue retreat, Desert Scouts, lose a troop 등)에 Commander를 포함하는 것은 슬라이스 3에서 새 아이콘과 함께 처리한다.
- 2026-09-07 슬라이스 3: (a) 기존 "troop" 효과에 Commander 포함 — Intrigue의 retreat(Go to Ground, Tactical Option 등)·garrison 배치(Alliance 계열 Plot), Chani의 "troop 2개 retreat → 검 4", Desert Scouts가 Commander를 고를 수 있다(`commanders` 인자, `retreat_leader_commander`). (b) 2절의 Conflict 카드 2장(Skirmish I·Storms in the South II, 둘 다 wild battle icon)을 옵션 setup 풀에 추가했다. (c) 4절의 wild battle icon clarification: 이긴 wild Conflict 카드는 도착 시 즉시 매칭하지 않고(`[Main p. 20]`), Endgame에서 표준 아이콘 또는 다른 wild와 짝지을 수 있다.
- 2026-09-07 슬라이스 4a: 카드 26+18종을 카탈로그에 올렸다(수량은 Dune Cards Hub 카탈로그, 룰북 p. 2의 25+5+2 / 15+1+2와 일치). 전사가 끝난 카드만 옵션 덱에 들어간다.
- 2026-09-07 슬라이스 4b: Imperium 12종 15장 — Quash Rebellion, Shrouded Counsel, Eliminate Allies, Imperial Throneship, Intelligence Training, Command Center, I Believe, Pointing the Way, Sandwalk, Fremen War Name, Corrupt Bureaucrat(CHOAM), Mercantile Affairs(CHOAM). 4절의 **Command (6+)**를 구현했다: Reveal turn의 Persuasion 합계가 6 이상일 때 자동 효과는 지급되고 선택 효과는 열리며, 6 미만이면 선택은 미뤄졌다가 같은 Reveal에서 Persuasion이 6에 도달하면 다시 열린다(OQ-033). 세부는 [implementation-audits/bloodlines.md](../implementation-audits/bloodlines.md).
- 2026-09-07 슬라이스 4c-1: Intrigue 10장 — Desert Support, Ripples in the Sand, Return the Favor, Sacred Pools, Seize Production, Sleeper Unit, Tenuous Bond, The Strong Survive, Withdrawal Agreement, Grasp Arrakis(effect DSL 전사; 새 노드는 audit 참조).
- 2026-09-07 슬라이스 4c-2a: Intrigue 3장 — Honor Guard(troop + 이번 turn Commander 비용 1 감소), Insider Information(Spy recall → trash + draw / 이번 turn Influence 요구 무시), Emperor's Invitation(draw / 이번 turn play한 카드에 Emperor 아이콘). 세 효과는 turn 한정 좌석 상태로 두고 TURN frame이 열릴 때 지운다.
- 2026-09-07 슬라이스 4c-2b: 4절의 **Combat 아이콘**을 구현했다. Agent turn에서는 효과 frame의 기본 배치 창을 열거나 garrison 몫을 2로 넓히고(아이콘이 여럿이어도 2), 배치 전에 얻으면 좌석에 대기했다가 배치 때 적용되며, Reveal turn에서는 그 Reveal에서 recruit한 유닛 + garrison 2개 한도의 배치 창이 열린다(`deploy_troops`/`deploy_commanders`, strength 즉시 반영; 회수 없음 — OQ-034). 카드: Adaptive Tactics(Intrigue), Elite Forces, Disruption Tactics(Agent box의 상대 troop 강제 retreat 포함, OQ-034).
- 2026-09-07 슬라이스 4d-1: 4절의 **Spy with Deep Cover**를 구현했다(자신의 Spy가 없는 모든 post가 후보; 상대 Spy는 무시). 카드: Arrakis Observer, Bombast(Command 지급 후 자기 trash), Engineered Miracle(Command: 자기 trash → Imperium Row 카드 무료 획득), Southern Faith, Possible Futures(BG Bond면 Influence + troop 2 모두).
- 남은 4절 아이콘(Trash an Intrigue card)과 나머지 카드는 다음 슬라이스에서. 5~6절(Tech Module)과 Leader는 [implementation-plan.md](../implementation-plan.md)의 M12 슬라이스 순서를 따른다.
