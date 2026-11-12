# 4인 규칙 명세 (Dune: Imperium · Dune: Imperium - Uprising)

상태: 기준선 v1 (작성 2026-08-12, 공식 asset 재검증 2026-08-26). 아래 범위 문단은 2026-11-03에 지금 구현에 맞췄다.

이 디렉터리는 두 기본 판 — **Dune: Imperium - Uprising**과 원판 **Dune: Imperium** — 의 **4인 플레이**와 그 확장을 구현할 때 사용하는 규칙 명세다. 공식 문장을 대체하는 번역본이 아니라, 공식 룰북과 FAQ의 내용을 구현 단위로 재구성한 요약이다. 실제 판정의 최종 근거는 항상 [공식 자료](sources.md)에 링크한 Dire Wolf Digital 문서다.

처음 이 명세는 Uprising 4인 판을 위해 썼고, 확장과 원판은 같은 방식의 옵션으로 더했다. 판을 만들 때 기본 판 하나를 고르고 확장을 켠다.

- **Uprising 4인 기본 게임.** 첫 엔진 완성 범위는 CHOAM Module을 끈 4인 게임이었다. CHOAM Module은 별도 룰셋 옵션(`choam_module`)이다.
- **Uprising에 더한 확장(2026-09).** Bloodlines 확장과 그 Tech Module은 2026-09-07부터 옵션 `bloodlines`, `tech_module`로, Immortality 확장은 2026-09-08부터 옵션 `immortality`로 추가했다(Main p. 18의 "Adding Immortality"). Immortality 룰북 p. 12의 Go to 11 변형은 2026-09-28부터 옵션 `go_to_11`(Immortality 필요)이다. Rise of Ix 룰북 p. 10의 Epic Game Mode는 2026-09-28부터 독립 옵션 `epic_game`이다(Uprising에서는 Rise of Ix를 켜지 않아도 쓸 수 있고, 그때는 Rise of Ix의 카드 두 종류 Control the Spice·Economic Supremacy만 가져온다, OQ-092). Dire Wolf Game Room 컴패니언 앱의 Arrakeen Scouts 모드는 2026-09-28부터 옵션 `arrakeen_scouts`로 추가했다(룰북이 없어 앱이 출처다).
- **원판과 Rise of Ix(2026-10-22–11-02).** 원판은 두 번째 기본 판(`base_game`, 명세 [imperium-base.md](imperium-base.md))이고, Rise of Ix는 확장 옵션 `rise_of_ix`다(명세 [rise-of-ix.md](rise-of-ix.md)). 구현 순서와 단계별 결과는 base-game-and-ix-plan.md에 있다(P0–P8-1).
- **조합.** 2026-10-31(P7)부터 확장은 어느 기본 판과도, 서로와도 조합된다(사용자 결정 2026-10-27). 확장 안의 부속만 자기 확장을 요구한다(Tech Module은 Bloodlines, Go to 11은 Immortality). 예외: 원판 + CHOAM Module은 열지 않는다(사용자 결정 2026-10-30). 원판의 Epic Game Mode는 Rise of Ix 전부와 함께만 쓴다. Tech Module과 Rise of Ix를 함께 켜면 Rise of Ix 전부, Ix 지도자 + Tech 타일, Ix Tech 타일만 가운데 고른다(OQ-165). 원판 위의 Arrakeen Scouts는 앱의 원판 일정을 쓴다([arrakeen-scouts.md](arrakeen-scouts.md)). Uprising 판에는 원판 카드를 Calculated Hire만 빼고 섞을 수 있다(옵션 `imperium_cards`) `[Main p. 18]`.
- **범위 밖.** 1·2인 Rivals와 원판의 House Hagal(자동 상대), 3인, 6인 팀전은 현재 범위 밖이다. `[Main p. 3]` `[Main p. 16]`

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
- [Bloodlines 확장과 Tech Module](bloodlines.md)
- [Immortality 확장](immortality.md)
- [Epic Game Mode](epic-game-mode.md): Rise of Ix의 12점 변형(Control the Spice, Economic Supremacy)
- [Arrakeen Scouts 모듈](arrakeen-scouts.md): 컴패니언 앱의 소위원회·임무·이벤트·경매·판매
- [원판 Dune: Imperium](imperium-base.md): 두 번째 기본 판의 규칙 명세(2026-10-22 작성, 구현은 base-game-and-ix-plan.md P1~P3에서 끝남)
- [Rise of Ix 확장](rise-of-ix.md): Tech·Shipping·dreadnought·Unload·잠입(2026-10-22 작성, 원판 위는 P4, Uprising 위와 다른 확장과의 조합은 P7·P8-1에서 구현)
- [한국어 용어집(KR·EN 룰북 대조)](glossary-ko.md): 브라우저 UI가 쓰는 한국어 게임 용어. 규칙 근거가 아니라 화면 문구의 어휘 표다.
- [공식 clarification과 FAQ 색인](official-rulings-index.md)
- [공식 문서만으로 확정할 수 없는 항목](open-questions.md)
- [이 게임에서 정한 판정 (공지)](house-rulings-ko.md): 위 목록의 판정을 플레이하는 사람에게 알리는 한국어 공지(출처끼리 다른 곳 /
  앱과 다른 곳 / 그 밖의 판정). `src/dune_imperium/display/house_rulings.toml`에서 만들고, 게임 화면 도움말도 같은 목록을 보인다
- [디자이너 커뮤니티 판정 대조(2026-09-08)](designer-rulings-audit.md): 공식 문서 밖의 Paul Dennen 판정과 엔진의 불일치 목록, 반영 미결정

## 읽는 법

- `[Main p. N]`은 Uprising Main Rulebook의 인쇄 페이지다.
- `[Main pp. N-M]`은 Main의 연속 페이지 범위이며, `board artwork`가 붙으면 해당 페이지의 공식 보드 그림을 판독한 근거다.
- `[Board Guide p. N]`은 Uprising Rules Supplements PDF 앞부분의 Board Space Guide 페이지다.
- `[FAQ p. N]`은 2025-01-13 FAQ의 페이지다.
- `[Bloodlines p. N]`은 Bloodlines 룰북의 PDF 페이지(인쇄 쪽수와 같다)이며 `bloodlines`·`tech_module` 옵션에만 적용된다.
- `[Immortality p. N]`은 Immortality 룰북의 PDF 페이지(인쇄 쪽수와 같다)이며 `immortality`·`go_to_11` 옵션에만(p. 12의 Epic 조합 문단은 `immortality`와 `epic_game`을 함께 켤 때만) 적용된다.
- `[Rise of Ix p. N]`은 Rise of Ix 룰북의 PDF 페이지(인쇄 쪽수와 같다)이며 `epic_game`과 `rise_of_ix` 옵션에 적용된다([rise-of-ix.md](rise-of-ix.md)의 근거; 2026-10-22까지는 `epic_game`에만 썼다).
- `[DI p. N]`은 원판 Dune: Imperium 룰북의 쪽(인쇄 쪽수 = PDF 쪽), `[DI Aid p. N]`은 원판 Player Aid의 PDF 쪽이다. 원판 판([imperium-base.md](imperium-base.md))에만 적용된다.
- `[Scouts help]`, `[Scouts schedule]`, `[Scouts subcommittee: <이름>]`, `[Scouts mission: <이름>]`, `[Scouts event: <이름>]`, `[Scouts auction: <이름>]`, `[Scouts sale: <이름>]`은 Dire Wolf Game Room 컴패니언 앱의 도움말, 일정 생성 방식, 항목 정의다. `[KO app: <loc key>]`는 앱의 한국어 용어다. `arrakeen_scouts` 옵션에만 적용된다([sources.md](sources.md)의 "Arrakeen Scouts" 절).
- 연속 범위는 `pp. N-M`, 떨어진 페이지와 범위의 조합은 `pp. N, M-M, K`처럼 쓴다. 한 문장에 서로 다른 자료를 썼다면 source tag를 각각 붙인다.
- source tag는 Markdown inline code로 감싸는 것을 기본 형식으로 한다. 기존 문서의 plain `[Main p. N]`도 같은 의미로 읽지만 새 문장에서는 만들지 않는다.
- `해야 한다`는 의무, `할 수 있다`는 선택을 뜻한다. 원문이 선택 여부를 명시하지 않으면 이 문서가 임의로 선택 여부를 만들지 않는다.
- 카드 텍스트는 일반 규칙을 바꿀 수 있다. 일반 규칙과 다른 카드 효과는 해당 카드의 공식 텍스트와 공식 clarification을 함께 적용한다. `[Main p. 6]`

## 구현에 적용하는 규율

1. 구현할 동작은 이 문서 세트의 근거 항목 또는 검증된 카드 텍스트를 가리켜야 한다.
2. FAQ가 보강한 규칙은 Main만 보고 단순화하지 않는다.
3. 공식 문서에 없는 순서·기본값·예외는 코드로 조용히 확정하지 않고 [미해결 목록](open-questions.md)에 먼저 기록한다.
4. 규칙 판정이 확정되면 근거 인용, 명세 수정, 회귀 테스트를 같은 변경 단위로 반영한다.
5. 이 명세의 내용과 공식 문서가 다르면 공식 문서가 우선한다.
