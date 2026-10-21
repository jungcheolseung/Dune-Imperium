+++
title = "무작위 10,000판 완주 검사로 숨은 버그 찾기"
description = "카드 보존, 교착, 관측 누출, 재생을 매 전이마다 검사하는 sweep으로 무작위 2만 판에서 실패 46건을 찾아 고쳤고, 휴리스틱 AI와 지도자 드래프트 판에서 무작위 진행이 닿지 못한 버그를 더 찾았습니다."
date = 2026-08-30T20:09:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-08-30"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-08.md", "docs/implementation-plan.md", "docs/rules/open-questions.md", "docs/rules/player-turns.md", "src/dune_imperium/simulation/sweep.py", "src/dune_imperium/simulation/invariants.py"]
+++

## 카드별 테스트가 놓치는 것

카드를 하나씩 구현할 때는 카드마다 테스트를 붙였지만([앞 글]({{< relref "devlog/2026-08-30-full-game.md" >}})), 카드끼리 겹치는 상황은 사람이 미리 떠올린 만큼만 시험됩니다. 이 프로젝트에서 특히 문제가 되는 곳은 한 턴 안에서 효과를 원하는 순서로 해결할 수 있다는 규칙(`[Main p. 9]`)입니다. 카드 A의 효과를 하나 해결하고 나서 카드 B의 효과를 해결하면 B의 조건이 달라질 수 있어, 효과 조합이 많아질수록 예상하지 못한 상태가 생깁니다. 구현 계획의 M7 단계는 이를 위해 "무작위 합법 플레이가 교착 없이 완주하며 상태 불변식을 매 행동 뒤 만족한다"는 것을 완료 조건으로 두었습니다.

## 무엇을 검사했나

8월 30일에 `dune-imperium-sweep`을 만들었습니다. 시드가 정해진 판을 끝까지 두면서 다음을 확인하고, 하나라도 어긋나면 그 판을 실패로 보고합니다. 여러 프로세스에 판을 나눠 돌립니다.

- **카드 보존:** 매 전이마다 개인 카드, Reserve(더미와 살아 있는 사본의 합), 책략, Conflict, 계약, 목표 카드가 정확히 한 장소에만 있는지 확인합니다.
- **교착:** 플레이어가 결정해야 하는 모든 지점에서 합법 행동이 하나 이상 있는지, 판이 정해진 단계 수 안에 끝나는지 확인합니다.
- **관측 누출:** 일정 주기로 결정 지점을 골라, 덱 순서, 상대 손패의 카드, 상대가 든 책략(`[Main p. 7]`), 뒷면인 계약 더미(`[Main p. 16]`)만 뒤섞은 상태를 만들어 모든 플레이어의 관측이 그대로인지 비교합니다. 뒤섞기가 실제로 상태를 바꾸는지도 테스트로 고정해 검사가 아무것도 하지 않고 통과하는 일을 막았습니다.
- **재생:** 판이 끝나면 기록을 다시 재생해 같은 상태 해시가 나오는지 확인합니다.

처음 만든 검사기는 두 룰셋(기본, CHOAM) 합계 500판을 초당 약 49판으로 돌렸습니다.

## 첫 실행: 2만 판 가운데 46판

룰셋마다 무작위 10,000판, 합계 2만 판을 처음 돌리자 46판(0.23%)이 실패했습니다. 원인은 다섯 계열이었습니다.

1. **Spy Network 교착.** 이 카드가 Reveal에서 대기시킨 선택은 "배치된 Spy마다 회수 하나"를 제시했는데, 자유 순서로 먼저 해결된 In High Places가 남은 Spy를 모두 회수하면 의무 선택에 합법 행동이 없어 판이 멈췄습니다.
2. **조건이 큐잉과 해결 사이에 바뀌는 문제.** Maker Keeper, Wheels Within Wheels, 그리고 Bene Gesserit Bond를 쓰는 세 카드(In High Places, Southern Elders, Weirding Woman)에서, 책략 비용으로 Influence가 내려가 대기시킨 조건이 더는 성립하지 않으면 "조건부 효과를 쓸 수 없다"는 예외로 판이 죽었습니다.
3. **이미 사라진 카드의 자기 trash.** 효과가 자신을 trash하는 카드(Seek Allies, Subversive Advisor)가, 책략의 trash 슬롯에 의해 먼저 trash돼 있으면 같은 예외로 죽었습니다.
4. **Corrinth City 선택 소실.** 비용으로 고른 첫 카드 버림을 책략의 버림 비용이 먼저 써 버리면, 이미 손을 떠난 카드를 버리려 했습니다.
5. **Price is No Object의 획득 Spy 정지.** Agent 턴 중 이 카드로 Spy를 배치하는 카드를 사면, 배치를 마친 뒤 돌아갈 곳에 남은 결정이 없어 판이 멈췄습니다.

하루 전 지도자를 구현하다 같은 모양으로 고친 Prepare the Way(조건이 배치와 해결 사이에 바뀌어, 합법이라고 제시한 행동이 적용될 때 실패)가 이 계열의 첫 사례였습니다.

## 고친 원리: 해결 시점에 판정한다

다섯 계열은 모두 자유 순서로 효과를 해결할 때 "큐에 넣은 시점의 상태"를 믿은 데서 생겼습니다. 공식 규칙은 한 턴의 효과를 원하는 순서로 해결할 수 있고 그 순서에 따라 조건의 결과가 달라질 수 있다고 하며(`[Main pp. 9, 20]`), Reveal 효과도 순서를 고른다고 합니다(`[Main p. 12]`). 그래서 조건과 자기 trash, 비용은 해결하는 시점에 다시 판정하고, 성립하지 않으면 예외 대신 "쓸 수 없음"으로 처리하도록 고쳤습니다. 규칙 문서에 없는 경우, 곧 play된 카드 자신이 해결 전에 trash된 경우는 OQ-022로 기록했습니다.

OQ-022의 8월 30일 판정은 "남은 의무 효과는 해결하고 자기 trash 지시는 이미 충족된 것으로 본다"였습니다. 9월 1일에 이 판정이 바뀌었습니다. 디자이너의 공개 답변에서 이미 trash된 카드의 효과는 받거나 발동할 수 없다는 것을 확인해, 아직 발동하지 않은 Agent 칸 전체가 만료되도록 엔진을 고쳤습니다. 답변은 공식 룰북이나 FAQ가 아니라서 이 항목의 상태는 확정된 프로젝트 판정으로 남아 있습니다. sweep이 가리킨 문제, 곧 이미 사라진 카드를 다시 처리하려다 판이 죽는 일은 그대로 막히고, 처리 방식만 달라졌습니다.

## 수정 뒤: 2만 판 실패 0

고친 뒤 같은 규모(룰셋당 10,000판, 합계 2만 판)를 모든 검사와 재생 검증을 켠 채 다시 돌려 실패 0을 확인했습니다. 400초에 초당 약 50판, 전이 약 879만 회, 판당 라운드 수 중앙값은 10이었습니다. 이 결과로 구현 계획의 M7 단계를 완료로 표시했습니다.

## 무작위 진행이 닿지 못한 곳

무작위 플레이는 카드를 충분히 사지 않아 닿지 못하는 상황이 있습니다. 같은 날 휴리스틱 AI(직접 승점, 영구 강화, 비용에 비례한 획득, 최대 배치 순으로 합법 행동에 점수를 매기는 규칙 기반 AI)를 만든 뒤 룰셋당 1,000판을 돌리자 만 판 무작위 검사가 못 찾은 것이 나왔습니다.

- **Special Mission 교착(CHOAM 시드 97, 901).** Spy 배치 슬롯에서 "내 Spy를 회수하면 그 칸이 빈다"고 계산했지만, 다른 플레이어의 Spy가 함께 있는 칸은 회수해도 비지 않습니다. 슬롯은 도움이 되지 않는 회수만 끝없이 제시하다 행동이 0개가 됐습니다. 공식 규칙은 Spy를 놓는 것도, 공급처가 비었을 때 먼저 하는 회수 하나도 선택이라고 하므로(`[Main pp. 11, 20]`), 배치를 거절하는 행동을 모든 분기에 추가하고 회수는 배치로 이어질 수 있는 것만 제시하도록 고쳤습니다.
- **Imperium 덱 고갈(기본 룰셋 1,000판 중 6판).** 휴리스틱이 카드를 많이 사서 공유 덱이 실제로 바닥났고, 구현은 이 경우 예외를 던지게 해 두었습니다. 공식 문서는 Row를 덱 위에서 채운다고만 하고 덱이 비었을 때를 정하지 않으므로(`[Main p. 13]`), 물리적으로 강제되는 유일한 진행, 곧 빈자리를 채우지 않고 남은 장수로 계속하는 것을 OQ-004의 프로젝트 규칙으로 기록했습니다.

수정 후 휴리스틱 룰셋당 1,000판(합계 2,000판)과 무작위 300판씩이 실패 0이었고, 교착이 났던 두 시드는 불변식 검사를 켠 회귀 테스트로 남겼습니다. 테스트는 770개에서 796개가 됐습니다.

이어서 지도자 6명을 공개하고 순서대로 하나씩 고르는 드래프트(프로젝트 규칙 OQ-007, 공식 규칙이 아님)를 켠 판을 돌렸습니다. 룰셋마다 휴리스틱과 무작위 각 500판의 소크에서 CHOAM 시드 198이 새 오류를 냈습니다. Treacherous Maneuver를 낸 뒤 책략의 trash 슬롯이 그 카드를 trash했는데, 선택을 해결할 때 이미 없는 카드를 다시 trash하려다 죽었습니다. 같은 OQ-022 계열이었고, 위 판정을 이 경로에도 적용한 뒤(당시 방식) 드래프트 소크 합계 2,000판이 실패 0이었습니다. 테스트는 813개였습니다. 드래프트 중에는 일부 지도자가 시작 카드를 합법적으로 제거하므로, 카드 보존 검사의 기준 목록은 준비 단계가 끝난 시점으로 고정했습니다.

## 남은 점

- 이 검사는 무작위와 단순한 휴리스틱이 가는 길만 봅니다. 9월 1일에 `--soundness-interval`(결정 지점마다 제시된 모든 합법 행동을 실제로 적용하고 행동 codec 왕복도 확인), `--coverage-json`(콘텐츠 커버리지), `--rotate-leaders`(지도자 회전)를 더했고, 그때의 교차 검사(총 7,000판)도 실패 0이었습니다.
- 검사는 오류의 존재만 보여 주고, 규칙이 맞다는 것은 보여 주지 않습니다. 규칙이 맞는지는 공식 문장과 대조해야 합니다.

## 참고 기록

- [M7 sweep 도입](https://github.com/jungcheolseung/Dune-Imperium/commit/3bafc67e)
- [Spy Network 교착 수정](https://github.com/jungcheolseung/Dune-Imperium/commit/f148c14d)
- [조건 변동과 자기 trash를 해결 시점에 판정](https://github.com/jungcheolseung/Dune-Imperium/commit/83aa4f5f)
- [획득 Spy 배치 뒤 Agent 턴 진행](https://github.com/jungcheolseung/Dune-Imperium/commit/24b13e73)
- [휴리스틱 기준 AI](https://github.com/jungcheolseung/Dune-Imperium/commit/1a449f4f)
- [Special Mission Spy 배치 수정](https://github.com/jungcheolseung/Dune-Imperium/commit/7a53c8f9)와 [Imperium 덱 고갈 처리](https://github.com/jungcheolseung/Dune-Imperium/commit/ac4d6d4f)
- [지도자 드래프트 소크의 Treacherous Maneuver 수정](https://github.com/jungcheolseung/Dune-Imperium/commit/d70b353f)
- [OQ-022 판정 변경](https://github.com/jungcheolseung/Dune-Imperium/commit/76dbbf7a)
- [미결 질문과 판정 목록](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
- [Agent 턴 규칙 문서](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/player-turns.md)
