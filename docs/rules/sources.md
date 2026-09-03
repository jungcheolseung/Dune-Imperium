# 출처와 작성 원칙

## 규칙 권위

현재 규칙 명세는 다음 세 공식 자료만을 규칙 근거로 사용한다.

| 식별자 | 공식 자료 | 확인한 버전 | 현재 범위 |
| --- | --- | --- | --- |
| `Main` | [Uprising Main Rulebook](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_UPRISING_Main_Rulebook_23-10-12.pdf) | 공식 asset 이름 `23-10-12`, 20쪽 | 규범 규칙 pp. 3-17, 20; 범위·권위 확인 pp. 2, 18 |
| `Board Guide` | [Uprising Rules Supplements](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_UPRISING_Rules_Supplements_23-10-12.pdf) | 공식 asset 이름 `23-10-12`, 14쪽 | pp. 1-2 |
| `FAQ` | [Errata and Frequently Asked Questions](https://d19y2ttatozxjp.cloudfront.net/pdfs/DUNE_IMPERIUM_FAQ_25-1-13.pdf) | 문서 표기 `Last Updated January 13, 2025`, 4쪽 | 4인 Uprising에 적용되는 항목 |

공식 진입점은 [Dire Wolf Digital 리소스 페이지](https://www.direwolfdigital.com/dune-imperium/resources/)와
[Uprising 룰북 페이지](https://www.direwolfdigital.com/dune-imperium/resources/diu_rules)다.
위 버전은 2026-08-26에 공식 진입점에서 다시 확인했으며, 세 PDF의 SHA-256도
고정 manifest와 모두 일치했다.

확인한 공식 파일의 SHA-256은 다음과 같다. 공식 URL의 파일이 같은 이름으로
교체되었는지 판별할 때 사용한다.

| 식별자 | SHA-256 |
| --- | --- |
| `Main` | `0a8daa36f73c09316143d05bbd5d845183d1ae6f56ce211d93c59b360074f7db` |
| `Board Guide` | `454ea3ef442f0622f4bf5b83b8368b24e34aaf4f0dc0f02d93dfba66e690c075` |
| `FAQ` | `7b54c283357244e5107d1d0f4e87817d39297e914c2014239acbb2c460c0c6b9` |

같은 URL과 checksum은 자동 검증 도구가 읽는
[`scripts/official-rule-sources.json`](../../scripts/official-rule-sources.json)에
machine-readable 형태로 보관한다. 공식 문서가 갱신되면 manifest와 이 표를 같은
변경에서 갱신하고, 기존 규칙 명세와의 차이를 먼저 검토한다.

Main은 최신 판정과 clarification을 FAQ에서 확인하라고 안내한다. 따라서 FAQ의
명시적인 수정·clarification을 함께 적용한다. 두 공식 문서가 실제로 충돌한다고
판단되는 경우 어느 한쪽을 조용히 버리지 않고 `open-questions.md`에 기록한다.
`[Main p. 18]`

## 페이지와 인용

- Main의 `[Main p. N]`은 표지 PDF 페이지가 아니라 본문에 인쇄된 쪽수를
  가리킨다. 인쇄 p. 2부터 PDF 페이지와 번호가 일치한다.
- Board Guide와 FAQ는 PDF 페이지 번호를 그대로 쓴다.
- 한 bullet의 모든 문장이 같은 근거를 공유하면 끝에 한 번 인용한다. 서로 다른
  출처를 결합한 경우 두 출처를 모두 붙인다.
- 이 문서는 원문을 길게 복제하지 않고 규칙의 의미만 간결하게 바꾸어 적는다.
  카드명, 공간명, 아이콘명처럼 구현 ID가 될 고유 명칭은 영어 원명을 유지한다.

## 포함·제외 기준

- Main의 4인 setup, 공통 개념, 라운드, Agent/Reveal, Combat, Makers, Recall,
  Endgame, CHOAM Module, Uprising clarification, icon/term guide를 포함한다.
- Board Guide의 4인 보드 공간 22개만 포함한다. 같은 PDF의 pp. 3-6 Rivals와
  pp. 7-14 6인 팀전은 포함하지 않는다.
- FAQ는 모든 제품을 다루므로 일반 규칙 또는 현재 Uprising 구성물에 적용되는
  항목만 규범 규칙으로 반영한다. 다른 제품의 리더·카드·Tech·Rivals 판정은
  현재 룰셋에 끌어오지 않는다.
- Main p. 18의 Rise of Ix, Immortality, 원본 Dune: Imperium 혼합 규칙은 현재
  구현 범위 밖이다.
- Main의 전략 조언과 세계관 설명은 규칙이 아니므로 명세에서 제외한다.

## 로컬 PDF와 보조 자료

`assets/rulebooks/` 아래 PDF(비공개 에셋 체크아웃)는 사용자의 로컬 열람 사본이다. 이 명세를 작성하면서 해당
파일을 읽거나 추출하지 않았다. 공식 URL의 파일만 임시 작업 위치에서 확인했으며,
공식 원문 PDF나 추출 텍스트를 저장소에 복사하지 않는다.

[Dune Cards Hub](https://dunecardshub.com/uprising)는 이후 카드 식별과 이미지
확인에만 사용한다. 규칙 권위가 아니며, 이미지 파일을 저장하거나 재배포하기
전에는 이용 조건을 따로 확인한다.

[Dire Wolf의 Uprising Design Diary 2](https://news.direwolfdigital.com/dune-imperium-uprising-design-diary-2-sandworms-conflicts-and-the-shield-wall/)는
Objective 카드의 battle icon, 인원 표시, First Player 표시처럼 룰북 본문에서
개별 카드별로 열거하지 않은 **구성물 식별**을 공식 이미지와 대조하는 데만
사용한다. 이 글의 설계 설명을 Main·Board Guide·FAQ보다 높은 규칙 판정 근거로
사용하지 않는다.

## 변경 절차

새 FAQ나 룰북이 나오면 다음 순서로 갱신한다.

1. 공식 리소스 페이지에서 문서와 날짜를 확인한다.
2. 이 파일의 버전과 확인일을 바꾼다.
3. `source-map.md`와 `official-rulings-index.md`를 대조한다.
4. 의미가 달라진 규칙과 `open-questions.md`를 갱신한다.
5. 영향을 받는 scenario test와 콘텐츠 출처 메타데이터를 함께 갱신한다.
