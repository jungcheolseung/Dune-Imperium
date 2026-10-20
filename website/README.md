# Dune: Imperium AI 웹사이트

프로젝트 소개·설치·사용 안내와 개발 이야기를 담는 Hugo 정적 사이트다. **사이트와 로컬 검증은 준비했으며 아직 공개하지 않았다.**
원고 18개와 검색 페이지, 반응형 화면·분류·목차·검색·RSS·sitemap·404를 제공한다.
게임 실행 패키지와 별도로 빌드하며 비공개 이미지·모델·Node.js는 필요하지 않다.

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

`check.py`는 Python 3.12+ 표준 라이브러리만으로 경로·파일·HTML fragment·검색 데이터·XML·공개 파일 범위를 확인한다.

## 브라우저 검증

Playwright는 검증용 별도 환경에 설치하며 게임이나 사이트의 실행 의존성이 아니다. 아래 명령은 저장소 루트에서 실행한다.

```bash
python3 -m venv tmp/website-qa
tmp/website-qa/bin/python -m pip install playwright==1.64.0
tmp/website-qa/bin/python -m playwright install chromium
tmp/website-qa/bin/python website/scripts/browser_check.py tmp/website-preview --screenshots tmp/website-shots
```

Linux에 필요한 시스템 라이브러리가 없으면 Playwright의 공식 설치 안내에 따라 준비한다. 이미 있는 Chromium은
`--browser /실행/파일/경로`로 지정할 수 있다. 스크립트는 임시 서버를 띄워 끝나면 끄며, 브라우저 임시 파일도 `tmp/`에 둔다.
홈·문서·검색·한글 조합 입력·글 분류·320/390px 화면·메뉴·404·JavaScript 없는 환경을 확인한다.
그림은 직접 만든 SVG 구성도이며 카드·보드 원본을 사용하지 않는다.

## 첫 공개 원고

| 구역 | 원고 |
| --- | --- |
| 홈 | [시작 화면](content/_index.md) |
| 소개 | [프로젝트 소개](content/about/_index.md), [지원 현황](content/about/support.md), [앞으로의 방향](content/about/roadmap.md) |
| 다운로드 | [현재 제공 방식과 설치 준비](content/downloads/_index.md) |
| 사용법 | [사용법 입구](content/guides/_index.md), [처음 한 판](content/guides/first-game.md), [방 만들기](content/guides/hosting.md), [친구 방 참여](content/guides/joining.md), [기본 조작·저장](content/guides/controls.md), [AI 고르기](content/guides/choosing-ai.md) |
| 개발 이야기 | [글 목록 소개](content/posts/_index.md), [규칙을 엔진으로](content/posts/rules-to-engine.md), [AI가 한 수를 고르는 과정](content/posts/how-search-ai-chooses.md), [앱 AI를 섞은 학습 실험](content/posts/learning-with-opponents.md) |
| 업데이트 | [소식 입구](content/updates/_index.md), [첫 기록](content/updates/2026-10-20-project-status.md) |
| 도움말 | [FAQ와 문제 해결](content/help/_index.md) |

2026-10-20에 원격 master `e7e9ad4f`의 코드·문서와 대조했다. 설치 절차는 저장소의 가이드와 공식 uv 문서를 확인해
작성했으며, 이 원고 작업에서 OS별 새 설치·게임 실행을 다시 검증한 것은 아니다. macOS와 Windows·Linux의 검증 상태는
기존 호스트·런처 가이드의 범위를 따른다. 공개 직전에는 실제 배포할 코드로 설치 안내를 다시 따라간다.

## 편집 규칙

- 공개 본문은 `content/` 안에만 둔다. 이 README는 작성자용이며 사이트 본문으로 싣지 않는다.
- front matter는 TOML(`+++`)이다. 제목·설명·날짜·수정일·초안 여부를 기록한다. `params.source_ref`·`params.sources`는
  편집 근거이며, 일반 사용 안내에 내부 코드 버전·경로를 일괄 노출하지 않는다.
- 내부 링크는 Hugo `relref`로 연결한다. GitHub의 Markdown 미리보기에서는 shortcode가 그대로 보일 수 있다.
  사이트 구현 때 `/Dune-Imperium/` 하위 경로에서 렌더링과 링크를 확인한다.
- `draft = false`는 빌드에 포함할 글이라는 뜻이다. 공개 사이트에서 숨길 원고는 `true`로 둔다.
- 일반 안내는 현재 동작을 따르고, 과거 실험은 측정 날짜·코드·조건을 유지한다. 실험 원자료는 저장소의 고정 커밋으로 연결한다.
- 실제로 제공하지 않는 다운로드·모델 링크, 사이트 공개 완료 주장, 빈 문서 예고는 넣지 않는다.
- 다운로드 안내와 OS 검증 범위는 릴리스 시 갱신한다. 이미지·영상은 공개 범위를 확인한 자료만 추가한다.
- 독자가 새로 시작할 때는 다운로드 → 처음 한 판, 초대받았을 때는 참가자 안내로 바로 갈 수 있게 유지한다.

## 공개 전 확인

원고 표현과 공개 범위를 검토하고, 게임의 실제 배포 코드에서 설치·첫 판·저장·재실행을 확인한다.
사이트의 브라우저 검증이 게임 설치나 Windows 실기 검증을 대신하지는 않는다.
검증한 프로그램 릴리스·선택 모델은 준비되면 다운로드 안내에 연결한다.
