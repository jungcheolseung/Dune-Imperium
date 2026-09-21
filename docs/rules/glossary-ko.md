# 한국어 용어집 (KR·EN 룰북 대조)

기준일: 2026-09-20

브라우저 UI의 언어 설정(ko/en)이 쓸 게임 용어를 **공식 한국어 룰북**에서 가져와
영어 원어와 짝지은 표다. 목적은 하나다 — 화면에 쓰는 한국어 단어를 **발명하지
않는 것**. [`lessons.md`](../lessons.md)에 trash/discard를 넘겨짚어 카드 전사를
틀리게 만든 기록이 있고, 같은 실수를 UI 문구에서 반복하지 않기 위한 표다.

계획과 정책은 [`../ui-improvement-plan.md`](../ui-improvement-plan.md)의 "언어
정책" 절을 따른다.

## 출처와 방법

공식 한국어 룰북은 Dire Wolf Digital 리소스 페이지가 배포한다(국내 유통은 Korea
Boardgames). 네 문서를 [`../../scripts/official-rule-sources.json`](../../scripts/official-rule-sources.json)에
`*-ko` 항목으로 고정했고, 2026-09-20에 공식 URL에서 받아 checksum이 일치함을
확인했다. 자세한 표는 [`sources.md`](sources.md)에 있다.

**KR판과 EN판은 쪽수가 정렬돼 있다** — Uprising 본문 20쪽, Supplements 14쪽,
Bloodlines 12쪽, Immortality 16쪽으로 양쪽이 같고, 같은 쪽에 같은 내용이 온다.
그래서 아래 인용은 한 쪽 번호로 양쪽을 가리킨다: `[Main p. 20]`은 EN·KR 두
룰북의 20쪽을 함께 뜻한다.

대부분의 항목은 **본문 20쪽의 용어집 페이지**("ICON GUIDE AND ADDITIONAL
TERMS")에서 왔다. 그 페이지에 없는 항목은 나온 쪽을 따로 적었다.

재현:

```bash
# 인자 없이 돌리면 manifest의 모든 출처(영어 5 + 한국어 4)를 받는다.
uv run scripts/prepare_official_rules.py --output-dir <저장소 밖 경로>
```

대조한 쪽은 대부분 각 룰북의 용어·아이콘 정리 페이지다: 본문 `[Main p. 20]`,
Bloodlines `[Bloodlines p. 12]`, Immortality `[Immortality p. 16]`, 그리고 보드
공간 설명서 `[Board Guide pp. 1-2]`.

## 적용 범위

| 대상 | 정책 |
| --- | --- |
| UI 크롬, 결정 prompt, 행동 로그 라벨 | 이 표의 한국어를 쓴다 |
| 카드·리더·공간·Conflict·Contract **이름** | **영어 그대로** — 카드 그림이 영어판이라 화면과 카드가 어긋난다 |
| 카드 인쇄 텍스트 | **영어 그대로 + 이 표를 쓰는 용어 툴팁** |

아래 표의 "적용"은 UI가 그 한국어를 쓰는지다. `참고`는 룰북에 있지만 위 정책에
따라 화면에서는 영어를 유지하는 항목이다.

## 자원과 비용

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Resources | 자원 | `[Main p. 20]` | 적용 |
| Solari | 솔라리 | `[Main p. 20]` | 적용 |
| Spice | 스파이스 | `[Main p. 20]` | 적용 |
| Water | 물 | `[Main p. 20]` | 적용 |
| bank | 은행 | `[Main p. 20]` | 적용 |
| Paying a cost | 비용 지불 | `[Main p. 20]` | 적용 |
| Persuasion | 설득 비용 | `[Main p. 20]` | 적용 |

## 카드 동작

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Acquire | 획득 | `[Main p. 20]` | 적용 |
| Draw a card | 카드 1장 뽑기 | `[Main p. 20]` | 적용 |
| Draw an Intrigue card | 책략 카드 1장 뽑기 | `[Main p. 20]` | 적용 |
| Discard a card | 카드 1장 버리기 | `[Main p. 20]` | 적용 |
| Trash one card | 카드 1장 폐기 | `[Main p. 20]` | 적용 |
| Trash an Intrigue card | 책략 카드 1장 폐기 | `[Main p. 20]` | 적용 |
| Steal Intrigue | 책략 훔치기 | `[Main p. 20]` | 적용 |

**trash와 discard를 절대 섞지 않는다.** 폐기(trash)는 게임 상자로 보내 이번
게임에서 빠지는 것이고, 버리기(discard)는 버림 더미로 가는 것이다
(`[Main p. 20]`). 같은 구분을 놓쳐 실제 버그가 났다([`lessons.md`](../lessons.md)
2026-09-09).

## 영역

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| hand | 핸드 | `[Main p. 20]` | 적용 |
| deck | 카드덱 | `[Main p. 20]` | 적용 |
| discard pile | 버림 더미 | `[Main p. 20]` | 적용 |
| supply | 개인 공급처 | `[Main p. 20]` | 적용 |
| In Play | 플레이 영역 | `[Main p. 20]` | 적용 |
| garrison | 주둔지 | `[Main p. 20]` | 적용 |
| the Conflict (칸) | 교전 칸 | `[Main p. 20]` | 적용 |
| observation post | 관측소 | `[Main p. 20]` | 적용 |

## 유닛과 조각

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Troop | 병력 | `[Main p. 20]` | 적용 |
| Recruit | 소집 | `[Main p. 20]` ("병력 1을 소집합니다") | 적용 |
| Sandworm | 모래벌레 | `[Main p. 20]` | 적용 |
| units (병력 + 모래벌레) | 부대 | `[Main p. 10]` | 적용 |
| Agent | 에이전트 | `[Main p. 20]` | 적용 |
| Recall Agent | 에이전트 소환 | `[Main p. 20]` | 적용 |
| Spy | 스파이 | `[Main p. 20]` | 적용 |
| Recall Spy | 스파이 소환 | `[Main p. 20]` | 적용 |
| Maker Hooks | 메이커 작살 | `[Main p. 20]` | 적용 |
| Shield Wall | 방어벽 | `[Main p. 20]` | 적용 |
| Control marker | 지배 마커 | `[Main p. 20]` | 적용 |
| Score marker / track | 승점 마커 / 승점 트랙 | `[Main p. 20]` | 적용 |
| Combat marker / track | 전투 마커 / 전투 트랙 | `[Main p. 12]` | 적용 |
| First Player marker | 시작 플레이어 마커 | `[Main p. 14]` | 적용 |
| Alliance token | 동맹 토큰 | `[Main p. 20]` | 적용 |
| Contract token | 계약 토큰 | `[Main p. 16]` | 적용 |

## 전투

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Conflict | 교전 | `[Main p. 20]` | 적용 |
| Combat space | 전투 장소 | `[Main p. 10]` | 적용 |
| strength | 전투력 | `[Main p. 12]` | 적용 |
| Sword | 검 | `[Main p. 20]` | 적용 |
| Retreat | 후퇴 | `[Main p. 20]` | 적용 |
| Battle Icon | 배틀 아이콘 | `[Main p. 20]` | 적용 |
| Crysknife / Desert Mouse / Ornithopter | 크리스나이프 / 사막쥐 / 오니솝터 | `[Main p. 20]` | 참고(카드 이름) |
| Victory Point | 승점 | `[Main p. 20]` | 적용 |
| first / second / third place | 1등 / 2등 / 3등 칸 | `[Main p. 14]` | 적용 |

## 팩션과 영향력

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Influence | 영향력 | `[Main p. 20]` | 적용 |
| Emperor | 황제 | `[Main p. 20]` | 적용 |
| Spacing Guild | 우주 항행 길드 | `[Main p. 20]` | 적용 |
| Bene Gesserit | 베네 게세리트 | `[Main p. 20]` | 적용 |
| Fremen | 프레멘 | `[Main p. 20]` | 적용 |
| Alliance | 동맹 | `[Main p. 20]` | 적용 |
| Fremen Bond | 프레멘의 유대감 | `[Main p. 20]` | 적용 |
| Landsraad | 랜드스래드 | `[Main p. 2]` | 적용 |

## 라운드와 단계

라운드 구조는 `[Main p. 8]`의 순서도에서 왔다.

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Setup | 게임 준비 | `[Main pp. 3-4]`(펼침면 제목 `SETUP` / "게임 준비") | 적용 |
| 1. Round Start | 1. 라운드 시작 | `[Main p. 8]` | 적용 |
| 2. Player Turns | 2. 플레이어 차례 | `[Main p. 8]` | 적용 |
| Agent turn | 에이전트 차례 | `[Main p. 8]` | 적용 |
| Reveal turn | 공개 차례 | `[Main p. 8]` | 적용 |
| 3. Combat | 3. 전투 | `[Main p. 8]` | 적용 |
| 4. Makers | 4. 메이커스 | `[Main p. 8]` | 적용 |
| 5. Recall | 5. 소환 | `[Main p. 8]` | 적용 |
| Endgame | 종료 단계 | `[Main p. 20]` | 적용 |

## 그 밖의 게임 용어

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Maker | 메이커 | `[Main p. 20]` | 적용 |
| Contract | 계약 | `[Main p. 20]` | 적용 |
| Control | 지배 | `[Main p. 20]` | 적용 |
| Signet Ring | 인장 반지 | `[Main p. 20]` | 참고(카드 이름) |
| Intrigue | 책략 | `[Main p. 20]` | 적용 |
| Plot / Combat / Endgame Intrigue | 음모 / 전투 / 종료 단계 책략 카드 | `[Main p. 7]` | 적용 |
| Imperium card | 임페리움 카드 | `[Main p. 20]` | 적용 |
| Reserve card | 예비 카드 | `[Main p. 20]` | 적용 |
| Leader | 지도자 | `[Main p. 20]` | 적용 |
| CHOAM Module | 초암 모듈 | `[Main p. 20]` | 적용 |
| Uprising | 봉기 | `[Main p. 20]` | 적용 |
| Swordmaster | 소드마스터 | `[Main p. 17]`, `[Board Guide p. 3]` | 참고(공간 이름) |
| High Council | 원로회 | `[Main p. 17]` | 참고(공간 이름) |
| Arrakeen / Spice Refinery / Imperial Basin | 아라킨 / 스파이스 정제소 / 제국 분지 | `[Main p. 20]` | 참고(공간 이름) |

"참고"로 적은 공간·카드 이름은 룰북이 한국어로 옮겼지만 UI는 영어를 유지한다 —
보드 스캔과 카드 그림이 영어판이라 화면의 글자와 그림이 어긋나기 때문이다.
한국어 스캔을 확보하면 그림은 코드 변경 없이 바뀌고(`display/images.py`의
`DEFAULT_LANGUAGES = ("ko", "en")`), 그때 이 항목들의 "적용"을 다시 판단한다.

## 합성 표기

아이콘의 대체 텍스트처럼 **두 용어를 붙여 써야 하는 자리**가 있다. 아래는 위 표의
항목만으로 만든 합성이며 새 번역이 아니다. 영어판도 같은 방식으로 합성한다
(`Emperor Influence`, `Trash an Intrigue card`).

| EN | 한국어 | 합성 근거 |
| --- | --- | --- |
| Emperor Influence | 황제 영향력 | 황제 + 영향력, `[Main p. 20]`("해당하는 팩션의 영향력") |
| Spacing Guild Influence | 우주 항행 길드 영향력 | 위와 같음 |
| Bene Gesserit Influence | 베네 게세리트 영향력 | 위와 같음 |
| Fremen Influence | 프레멘 영향력 | 위와 같음 |
| Lose Influence | 영향력 잃기 | `[Main p. 20]`("영향력 1 잃기") |
| Trash an Intrigue card | 책략 카드 폐기 | `[Main p. 20]`("책략 카드 1장 폐기")에서 수량만 뺀 형태 |

수량은 아이콘 옆에 숫자로 붙으므로("영향력 1 잃기" → `2` + 아이콘) 합성 표기에는
수량을 넣지 않는다.

## Agent 아이콘 분류

보드 공간의 Agent 아이콘 일곱 가지다. 양쪽 룰북의 공간 설명에서 그대로 추출했고
개수와 항목이 정확히 일치한다(`[Board Guide pp. 1-2]`).

| EN | 한국어 | 적용 |
| --- | --- | --- |
| City | 도시 | 적용 |
| Emperor | 황제 | 적용 |
| Spacing Guild | 우주 항행 길드 | 적용 |
| Bene Gesserit | 베네 게세리트 | 적용 |
| Fremen | 프레멘 | 적용 |
| Landsraad | 랜드스래드 | 적용 |
| Spice Trade | 스파이스 거래 | 적용 |

## Bloodlines 확장과 Tech Module

대부분 `[Bloodlines p. 12]`의 "ICON GUIDE AND TERMS"에서 왔다.

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Bloodlines | 혈통 | `[Bloodlines p. 12]` | 적용 |
| Sardaukar Commander | 사다우카 지휘관 | `[Bloodlines p. 4]` | 적용 |
| Sardaukar Commander Skill | 사다우카 지휘관 기술 토큰 | `[Bloodlines p. 4]` | 적용 |
| Tech Module | 기술 모듈 | `[Bloodlines p. 12]` | 적용 |
| Tech tile | 기술 타일 | `[Bloodlines p. 12]` | 적용 |
| Acquire Tech | 기술 획득 | `[Bloodlines p. 12]` | 적용 |
| Flip (a Tech tile) | 뒤집기 | `[Bloodlines p. 12]` | 적용 |
| Ixian Embassy board | 익스 대사관 판 | `[Bloodlines p. 12]` | 적용 |
| Command (6+) | 통솔 | `[Bloodlines p. 12]` | 적용 |
| Combat (아이콘) | 전투 | `[Bloodlines p. 12]` | 적용 |
| Spy with Deep Cover | 잠복 스파이 | `[Bloodlines p. 12]` | 적용 |
| Twisted Intrigue | 뒤틀린 책략 | `[Bloodlines p. 12]` | 적용 |
| Navigation card | 운항 카드 | `[Bloodlines p. 12]` | 적용 |
| Tactics token / track | 전술 토큰 / 전술 트랙 | `[Bloodlines p. 12]` | 적용 |
| Rival Tech Tile | 라이벌 기술 타일 | `[Bloodlines p. 12]` | 범위 밖(1인 게임) |
| Tuek's Sietch | 튜엑의 시치 | `[Bloodlines p. 12]` | 참고(공간 이름) |
| Forbidden Weapon | 금지된 무기 | `[Bloodlines p. 12]` | 참고(타일 이름) |

> **기술은 두 가지를 가리킨다.** 한국어판은 Tech tile을 `기술 타일`, Sardaukar
> Commander Skill을 `기술 토큰`으로 옮겨 둘 다 "기술"로 시작한다. 화면에서
> **맨 "기술"만 쓰지 않는다** — 항상 `기술 타일` 또는 `사다우카 지휘관 기술 토큰`처럼
> 뒤 명사까지 붙여 쓴다. 둘은 서로 다른 구성물이고 규칙도 다르다.

## Immortality 확장

대부분 `[Immortality p. 16]`의 "NEW ICONS"에서 왔다.

| EN | 한국어 | 인용 | 적용 |
| --- | --- | --- | --- |
| Immortality | 불멸 | `[Immortality p. 16]` | 적용 |
| Research | 연구 | `[Immortality p. 16]` | 적용 |
| research token / track | 연구 토큰 / 연구 트랙 | `[Immortality p. 16]` | 적용 |
| Genetic marker | 유전자 마커 | `[Immortality p. 16]` | 적용 |
| Specimen | 표본 | `[Immortality p. 16]` | 적용 |
| Axolotl tanks | 악솔로틀 탱크 | `[Immortality p. 16]` | 적용 |
| Bene Tleilax board | 베네 틀레이락스 게임판 | `[Immortality p. 16]` | 적용 |
| Tleilaxu | 틀레이락스 | `[Immortality p. 16]` | 적용 |
| Tleilaxu token / track | 틀레이락스 토큰 / 틀레이락스 트랙 | `[Immortality p. 16]` | 적용 |
| Tleilaxu Row | 틀레이락스 열 | `[Immortality p. 4]` | 적용 |
| Imperium Row | 임페리움 열 | `[Immortality p. 4]` | 적용 |
| Reserve (더미) | 예비 카드 더미 | `[Immortality p. 4]` | 적용 |
| Graft | 접합 | `[Immortality p. 10]` | 적용 |
| Research Station | 연구 기지 | `[Immortality p. 16]` | 참고(공간 이름) |

## 아직 채우지 않은 것

- **CHOAM Module**: 초암 모듈·계약·계약 토큰은 위 표에 있지만, 계약 조건과 보상의
  세부 문구는 아직 대조하지 않았다. CHOAM UI 문구를 건드릴 때 `[Main p. 16]`에서
  채운다.
- Bloodlines·Immortality의 **Leader 전용 용어**(Chani의 전술, Piter의 뒤틀린 책략,
  Kota의 비밀 프로젝트 등)는 해당 Leader UI를 건드릴 때 각 룰북에서 채운다.
- **set aside**: Manipulate(Imperium Row 조작)와 Shaddam의 보류 계약이 쓰는
  동작인데 한국어 룰북의 용어집에 대응 항목을 찾지 못했다. 발명하지 않고
  화면에서 영어를 유지하고 있다(`acquire_manipulated_imperium`,
  `manipulate_imperium_row`). 해당 카드의 한국어 카드면이나 룰북 본문에서
  단어를 찾으면 여기에 인용과 함께 더하고 라벨을 바꾼다.
- **Agent box**: `[Bloodlines p. 12]`의 한국어판이 "에이전트 칸"으로 쓴다.
  라벨은 그 표기를 따르지만 용어집 행으로는 아직 올리지 않았다.
- **한국어 FAQ는 없다.** 공식 FAQ는 영어판만 배포된다. FAQ가 근거인 판정의
  용어는 본문 룰북의 단어를 쓴다.
- 엔진 event kind 207개 중 177개가 아직 한국어 라벨이 없다
  (`static/labels.js`의 `EVENT_LABELS`). 이 표가 그 라벨을 쓸 때의 어휘를 정한다.

## 규칙

1. 화면에 쓸 한국어 게임 용어는 **이 표에 있는 것만** 쓴다.
2. 표에 없는 용어가 필요하면 먼저 공식 한국어 룰북에서 찾아 이 표에 인용과 함께
   더한다. 룰북이 침묵하면 [`open-questions.md`](open-questions.md)에 적고,
   프로젝트 관례임을 분명히 한 뒤에 쓴다.
3. 고유명사(카드·리더·공간·Conflict·Contract 이름)는 영어를 유지한다.
