# Uprising 4인 규칙 명세

상태: 기준선 v1 (작성 2026-08-12, 공식 asset 재검증 2026-08-26)

이 디렉터리는 **Dune: Imperium - Uprising 4인 플레이**를 구현할 때 사용하는
규칙 명세다. 공식 문장을 대체하는 번역본이 아니라, 공식 룰북과 FAQ의 내용을
구현 단위로 재구성한 요약이다. 실제 판정의 최종 근거는 항상
[공식 자료](sources.md)에 링크한 Dire Wolf Digital 문서다.

첫 엔진 완성 범위는 CHOAM Module을 끈 4인 게임이다. CHOAM Module도 규칙을
미리 문서화하지만 별도 룰셋 옵션으로 취급한다. 1·2인 Rivals, 3인, 6인 팀전,
Epic Game Mode, 다른 확장과의 혼합 규칙은 현재 범위 밖이다. `[Main p. 3]`
`[Main p. 16]`

## 문서 구성

- [출처와 작성 원칙](sources.md): 공식 출처의 버전, 우선순위, 인용 규칙
- [출처 범위표](source-map.md): 주제별 근거 페이지와 문서화 위치
- [구성물·setup·게임 흐름](setup-and-game-flow.md)
- [Agent turn과 Reveal turn](player-turns.md)
- [Combat·Makers·Recall·Endgame](combat-and-round-end.md)
- [Faction·Spy·sandworm 등 Uprising 시스템](uprising-systems.md)
- [4인 보드 공간](board-spaces.md)
- [Observation post 연결](observation-posts.md)
- [공개·비공개 정보](information-visibility.md)
- [CHOAM Module](choam-module.md)
- [공식 clarification과 FAQ 색인](official-rulings-index.md)
- [공식 문서만으로 확정할 수 없는 항목](open-questions.md)

## 읽는 법

- `[Main p. N]`은 Uprising Main Rulebook의 인쇄 페이지다.
- `[Main pp. N-M]`은 Main의 연속 페이지 범위이며, `board artwork`가 붙으면
  해당 페이지의 공식 보드 그림을 판독한 근거다.
- `[Board Guide p. N]`은 Uprising Rules Supplements PDF 앞부분의 Board Space
  Guide 페이지다.
- `[FAQ p. N]`은 2025-01-13 FAQ의 페이지다.
- 연속 범위는 `pp. N-M`, 떨어진 페이지와 범위의 조합은
  `pp. N, M-M, K`처럼 쓴다. 한 문장에 서로 다른 자료를 썼다면 source tag를
  각각 붙인다.
- source tag는 Markdown inline code로 감싸는 것을 기본 형식으로 한다. 기존
  문서의 plain `[Main p. N]`도 같은 의미로 읽지만 새 문장에서는 만들지 않는다.
- `해야 한다`는 의무, `할 수 있다`는 선택을 뜻한다. 원문이 선택 여부를
  명시하지 않으면 이 문서가 임의로 선택 여부를 만들지 않는다.
- 카드 텍스트는 일반 규칙을 바꿀 수 있다. 일반 규칙과 다른 카드 효과는 해당
  카드의 공식 텍스트와 공식 clarification을 함께 적용한다. `[Main p. 6]`

## 구현에 적용하는 규율

1. 구현할 동작은 이 문서 세트의 근거 항목 또는 검증된 카드 텍스트를 가리켜야
   한다.
2. FAQ가 보강한 규칙은 Main만 보고 단순화하지 않는다.
3. 공식 문서에 없는 순서·기본값·예외는 코드로 조용히 확정하지 않고
   [미해결 목록](open-questions.md)에 먼저 기록한다.
4. 규칙 판정이 확정되면 근거 인용, 명세 수정, 회귀 테스트를 같은 변경 단위로
   반영한다.
5. 이 명세의 내용과 공식 문서가 다르면 공식 문서가 우선한다.
