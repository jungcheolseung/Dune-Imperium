# Dune: Imperium AI 웹사이트

프로젝트 소개·설치·사용 안내, 날짜별 개발일지와 기술 글을 담는 Hugo 정적 사이트다.
공개 주소는 [Dune: Imperium AI](https://jungcheolseung.github.io/Dune-Imperium/)이며, 2026-10-20 첫 배포를 확인했다.
개발일지 31편과 기술 글 6편을 포함한 콘텐츠 53개를 한국어·영어로 제공한다. 반응형 화면·분류·목차·검색·RSS·sitemap·404와 다크·라이트 모드를 지원한다.
게임 실행 패키지와 별도로 빌드하며 비공개 이미지·모델·Node.js는 필요하지 않다.

## 언어와 테마

- 한국어는 기존 `/Dune-Imperium/` 주소를 유지하고 영어는 `/Dune-Imperium/en/`에 둔다.
- `content/example.md`는 한국어, 같은 위치의 `example.en.md`는 영어다. 언어 버튼은 같은 페이지의 번역으로 이동한다.
- 본문뿐 아니라 메뉴·목차·검색 메시지·날짜·메타데이터도 번역한다. 각 언어의 검색 자료·RSS·sitemap을 따로 생성한다.
  `i18n/ko.toml`과 `i18n/en.toml`이 UI 문구를 관리한다. 분류의 내부 식별자는 공통으로 유지하고 표시 이름을 번역한다.
- 테마는 처음에 운영체제 설정을 따른다. 헤더의 해·달 버튼으로 고른 뒤에는 `localStorage`의 `dune-site-theme`에 저장해
  새로고침·페이지 이동·언어 전환에도 유지한다. 다른 탭에도 반영한다. 저장이 차단돼도 현재 페이지의 전환은 가능하다.
- 저장된 테마는 CSS 전에 적용한다. JavaScript가 꺼져 있으면 시스템 테마를 따르고 테마 버튼은 숨긴다.
- `static/images/sandworm.svg`는 사이트용으로 직접 작성한 샌드웜 아이콘이다. 헤더와 favicon에서 쓴다.
  개인용 `assets`의 원본 아이콘은 사이트에 복사하지 않았다. 좌석 구성도도 언어별 자체 SVG다.

Hugo의 [파일명 기반 번역](https://gohugo.io/content-management/multilingual/)과
[언어별 설정](https://gohugo.io/configuration/languages/)을 사용한다.

## 로컬에서 보기

[Hugo 0.168.0](https://github.com/gohugoio/hugo/releases/tag/v0.168.0) 일반 버전을 설치한다. Extended/Sass는 사용하지 않는다.
저장소 루트에서 다음을 실행하고 출력된 `/Dune-Imperium/` 주소를 연다.

```bash
hugo server --source website --baseURL http://localhost:1313/Dune-Imperium/ --cacheDir "$PWD/tmp/website-cache"
```

종료할 때 `Ctrl+C`를 누른다. 빌드만 하려면 다음을 쓴다. 산출물·캐시는 git이 무시하는 프로젝트 `tmp/`에 둔다.

```bash
hugo --source website --destination ../tmp/website-preview/Dune-Imperium --cacheDir "$PWD/tmp/website-cache" --minify --panicOnWarning
python3 website/scripts/check.py tmp/website-preview/Dune-Imperium
```

`check.py`는 Python 3.12+ 표준 라이브러리만으로 경로·파일·HTML fragment·언어별 검색/RSS·번역 짝과 hreflang·XML·공개 파일 범위를 확인한다.

## 브라우저 검증

Playwright는 검증용 별도 환경에 설치하며 게임이나 사이트의 실행 의존성이 아니다. 아래 명령은 저장소 루트에서 실행한다.

```bash
python3 -m venv tmp/website-qa
tmp/website-qa/bin/python -m pip install playwright==1.64.0
tmp/website-qa/bin/python -m playwright install chromium
tmp/website-qa/bin/python website/scripts/browser_check.py tmp/website-preview --screenshots tmp/website-shots
```

Linux에 필요한 시스템 라이브러리가 없으면 Playwright의 공식 설치 안내에 따라 준비한다. 이미 있는 Chromium은
`--browser /실행/파일/경로`로 지정할 수 있다(macOS의 설치된 Chrome도 된다). 검사는 줄인 움직임(`reduced_motion`)으로 돌린다.
사이트의 부드러운 스크롤이 쪽 안 이동 직후의 클릭과 겹치면 설치된 Chrome에서 대상이 멈추지 않아 클릭이 시간 초과되기 때문이다. 스크립트는 임시 서버를 띄워 끝나면 끄며, 브라우저 임시 파일도 `tmp/`에 둔다.
홈·문서·검색·한글 조합 입력·글 분류·320/390px 화면·메뉴·404와 언어 전환을 확인한다. 테마 자동 감지·선택 저장·탭 동기화,
저장 차단과 JavaScript 없는 환경도 확인한다. 그림과 아이콘은 자체 SVG이며 카드·보드 원본을 사용하지 않는다.

## 공개 콘텐츠

| 구역 | 원고 |
| --- | --- |
| 홈 | [시작 화면](content/_index.md) |
| 소개 | [프로젝트 소개](content/about/_index.md), [지원 현황](content/about/support.md), [앞으로의 방향](content/about/roadmap.md) |
| 다운로드 | [현재 제공 방식과 설치 준비](content/downloads/_index.md) |
| 사용법 | [사용법 입구](content/guides/_index.md), [처음 한 판](content/guides/first-game.md), [방 만들기](content/guides/hosting.md), [친구 방 참여](content/guides/joining.md), [기본 조작·저장](content/guides/controls.md), [AI 고르기](content/guides/choosing-ai.md) |
| 기술 글 | [글 목록 소개](content/posts/_index.md), [규칙을 엔진으로](content/posts/rules-to-engine.md), [AI가 한 수를 고르는 과정](content/posts/how-search-ai-chooses.md), [앱 AI를 섞은 학습 실험](content/posts/learning-with-opponents.md), [모델 구조](content/posts/model-architecture.md), [다른 게임 AI와 비교한 구조 점검](content/posts/architecture-survey.md) |
| 개발일지 | [월별 목록](content/devlog/_index.md), `content/devlog/YYYY-MM-DD-topic.md`의 작업별 기록 30편 |
| 업데이트 | [소식 입구](content/updates/_index.md), [첫 기록](content/updates/2026-10-20-project-status.md) |
| 도움말 | [FAQ와 문제 해결](content/help/_index.md) |

2026-10-20에 원격 master `e7e9ad4f`의 코드·문서와 대조했다. 설치 절차는 저장소의 가이드와 공식 uv 문서를 확인해
작성했으며, 이 원고 작업에서 OS별 새 설치·게임 실행을 다시 검증한 것은 아니다. macOS와 Windows·Linux의 검증 상태는
기존 호스트·런처 가이드의 범위를 따른다. 공개 직전에는 실제 배포할 코드로 설치 안내를 다시 따라간다.

## 개발일지 추가하기

한 작업에 딸린 구현·수정·문서 커밋은 한 편으로 묶는다. 며칠에 걸친 작업은 기간으로 표시한다.
커밋 메시지를 나열하기보다 해결하려던 문제, 바뀐 동작, 검증·실험 결과, 남은 점을 쓴다.
초기 코드(2023년)부터 2026년 10월 20일 작업까지의 글(`params.retrospective = true`)은 과거 기록을 재구성한 글이다.
2026-10-20에 16편을 처음 썼고, 2026-10-21에 커밋·작업 문서와 다시 대조해 수치·조건을 보강하고 빠진 큰 작업 11편을 더했다.

저장소 루트에서 초안을 만든다. 날짜와 주제는 실제 작업에 맞춰 바꾼다.

```bash
hugo new content --source website --kind devlog devlog/2026-10-21-topic.md
hugo new content --source website --kind devlog-en devlog/2026-10-21-topic.en.md
```

- `title`·`description`: 제목과 목록에 보일 요약.
- `params.work_start`와 `date`: 작업 시작일과 종료일. 목록·월 구분은 종료일 기준이다.
- `publishDate`·`lastmod`: 실제 글 공개일과 수정일. 과거 작업을 정리해도 공개일을 과거로 꾸미지 않는다.
- `params.source_ref`·`params.sources`: 작성 근거인 고정 커밋과 파일 경로. 본문의 참고 기록에도 해당 커밋·문서 링크를 넣는다.
- `params.retrospective = true`: 나중에 정리한 과거 기록이면 추가한다.
- 두 파일은 한국어·영어 초안이다. 작업 날짜·기간·근거·실험 수치를 맞추고 각 언어의 제목·요약·본문을 작성한다.
- 초안은 기본 `draft = true`다. 두 언어의 내용·근거를 확인한 뒤 모두 `false`로 바꾸고 위의 빌드·검증을 실행한다.
  공개 글에 번역이 빠지면 산출물 검사가 실패한다. 영어 내부 `relref`에는 `lang="en"`을 명시한다.

언어별 Markdown을 추가하면 해당 언어의 홈 최근 글·월별 목록·앞뒤 글·검색·RSS에 자동 반영된다.
`master`에 push하면 검증 뒤 배포된다. PR 병합은 선택 가능한 검토 절차이며 배포의 필수 조건은 아니다.
문구와 기록 원칙은 [AGENTS.md](AGENTS.md)를 따른다.

## 편집 규칙

- 공개 본문은 `content/` 안에만 둔다. 이 README는 작성자용이며 사이트 본문으로 싣지 않는다.
- front matter는 TOML(`+++`)이다. 제목·설명·날짜·수정일·초안 여부를 기록한다. `params.source_ref`·`params.sources`는
  편집 근거이며, 일반 사용 안내에 내부 코드 버전·경로를 일괄 노출하지 않는다.
- 새 글이나 수정은 번역 파일도 함께 준비한다. 실험의 날짜·조건·불확실성·후속 정정을 번역 과정에서 바꾸지 않는다.
- 내부 링크는 Hugo `relref`로 연결한다. GitHub의 Markdown 미리보기에서는 shortcode가 그대로 보일 수 있다.
  사이트 구현 때 `/Dune-Imperium/` 하위 경로에서 렌더링과 링크를 확인한다.
- `draft = false`는 빌드에 포함할 글이라는 뜻이다. 공개 사이트에서 숨길 원고는 `true`로 둔다.
- 일반 안내는 현재 동작을 따르고, 과거 실험은 측정 날짜·코드·조건을 유지한다. 실험 원자료는 저장소의 고정 커밋으로 연결한다.
- 실제로 제공하지 않는 다운로드·모델 링크와 빈 문서 예고는 넣지 않는다.
- 다운로드 안내와 OS 검증 범위는 릴리스 시 갱신한다. 이미지·영상은 공개 범위를 확인한 자료만 추가한다.
- 독자가 새로 시작할 때는 다운로드 → 처음 한 판, 초대받았을 때는 참가자 안내로 바로 갈 수 있게 유지한다.

## 게임 배포판을 준비할 때 확인

원고 표현과 공개 범위를 검토하고, 게임의 실제 배포 코드에서 설치·첫 판·저장·재실행을 확인한다.
사이트의 브라우저 검증이 게임 설치나 Windows 실기 검증을 대신하지는 않는다.
검증한 프로그램 릴리스·선택 모델은 준비되면 다운로드 안내에 연결한다.

## GitHub Pages 배포

배포 설정은 [website.yml](../.github/workflows/website.yml)이다. Hugo 0.168.0과 공식 Linux 아카이브 SHA-256을 고정했다.

- PR: 정적 빌드·산출물 검사·Chromium 검증만 실행한다. Pages artifact 업로드와 배포는 하지 않는다.
- `master`의 사이트 관련 변경: 같은 검증을 통과하면 빌드 결과만 Pages에 배포한다.
- 수동 실행: Actions에서 Website를 고르고 `master`로 실행하면 같은 검증·배포를 한다. 다른 브랜치는 검증만 한다.
- 사이트와 관계없는 엔진 변경은 이 workflow를 시작하지 않는다. 설치 안내의 근거 문서가 바뀌면 사이트 검증도 실행한다.

최초 공개 순서:

1. 사이트 브랜치의 변경·원고를 검토하고 PR 검증을 확인한다.
2. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 설정한다.
3. 검토한 사이트 변경을 `master`에 반영하고 push한다. `Website` workflow의 build·deploy 결과를 확인한다.
4. 배포가 성공한 뒤 실제 사이트에서 시작 경로·검색·RSS를 확인한다.

기본 주소는 `https://jungcheolseung.github.io/Dune-Imperium/`이다. 첫 배포는 master `b7787979`에서 성공했고
홈·사용법·검색 자료·RSS 응답을 확인했다. 이후 수정은 위 로컬 검증 뒤 master 반영·push로 배포한다. 커스텀 도메인·저장소 이름을 바꾸면 `hugo.toml`의 `baseURL`과
검증 스크립트의 기본 경로도 함께 바꾼다.
