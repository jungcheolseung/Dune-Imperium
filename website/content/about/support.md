+++
title = "지원 현황"
description = "지원하는 게임 구성과 플레이 방식, 운영체제별 확인 범위를 안내합니다."
date = 2026-10-20
lastmod = 2026-11-03
draft = false
weight = 20
[params]
source_ref = "81ca9468"
sources = ["README.md", "docs/rules/README.md", "docs/base-game-and-ix-plan.md", "src/dune_imperium/server/static/index.html", "src/dune_imperium/server/static/screens.js", "src/dune_imperium/server/seat_kinds.py", "docs/remote-play-host-guide.md", "docs/remote-play-player-guide.md", "docs/server-launcher-plan.md"]
+++

대상은 두 기본 판 — **원판 Dune: Imperium**과 **Dune: Imperium - Uprising** — 의 **4인 게임**입니다.
새 게임을 만들 때 기본 판 하나를 고르고 확장을 켭니다. 사람이 한 명이어도 남은 세 좌석을 AI로 채워
플레이할 수 있습니다. 이는 공식 솔로 모드를 구현한 것과는 다른 플레이 방식입니다.

## 게임 구성

| 구성 | 원판 | Uprising |
| --- | --- | --- |
| 기본 판 4인 게임 | 지원 | 지원 |
| Rise of Ix | 지원 | 지원(공식 규칙대로 CHOAM 게임판 덮개를 반만 폄) |
| Immortality, Go to 11 변형 | 지원 | 지원 |
| Bloodlines, Tech Module | 지원(원판에 맞지 않는 카드·지도자는 뺌) | 지원 |
| CHOAM Module | 열지 않음 | 지원 |
| Arrakeen Scouts | 지원(컴패니언 앱의 원판 일정) | 지원 |
| Epic Game Mode | Rise of Ix 전부와 함께일 때 | 지원 |
| 원판 카드 섞기 | 해당 없음 | 지원(공식 규칙대로 Calculated Hire만 뺌) |
| 프로모 카드 | 원판 프로모 | Uprising 프로모 |
| 지도자 공개 드래프트 | 지원(프로젝트 자체 운영 방식) | 지원(프로젝트 자체 운영 방식) |

Rise of Ix와 Bloodlines의 Tech Module을 함께 켜면 Rise of Ix를 얼마나 쓸지 고릅니다. **Ix 전부**(공식),
**Ix 지도자와 기술 타일만**(컴패니언 앱의 조합), **Ix 기술 타일만**(공식, Arrakeen Scouts와는 함께 쓰지 않음)
가운데 하나입니다. Arrakeen Scouts는 공식 룰북이 없어 Dire Wolf Game Room 앱을 출처로 삼았습니다.

공식 Rivals 솔로·2인 모드와 원판의 House Hagal 자동 상대, 공식 3인 구성, 6인 팀전은 현재 구현 대상이 아닙니다.
옵션을 켜는 위치는 [처음 한 판]({{< relref "guides/first-game.md" >}})에서 안내합니다.

## 플레이 기능

- 사람과 AI를 섞은 네 좌석 구성, AI끼리 플레이하는 판 관전.
- 호스트가 여는 방에 링크로 참여하는 멀티플레이. 사람 좌석이 모두 차면 시작하는 대기실이 있습니다.
- 한국어·영어 화면, 가능한 행동 안내와 도움말, 효과를 쓰지 않고 넘어가기 전의 경고.
- 저장·불러오기, 자동 저장, 끝난 판의 리플레이 검토.
- 숨은 정보가 새로 드러나기 전 등 허용되는 범위의 되돌리기.

## AI와 기본 판

| AI | 원판 | Uprising |
| --- | --- | --- |
| 앱 AI 어려움·보통·쉬움 | 지원 | 지원 |
| 휴리스틱·랜덤 | 지원 | 지원 |
| 탐색 AI, 학습 체크포인트, 롤아웃 | 아직 앉지 않음 | 지원 |

탐색 AI의 모델은 Uprising 판으로만 학습했기 때문에 원판 좌석 목록에는 나오지 않습니다.
AI 종류와 필요한 준비물은 [AI 고르기]({{< relref "guides/choosing-ai.md" >}})를 보세요.

## 실행 환경의 확인 범위

| 환경 | 현재 확인 상태 |
| --- | --- |
| macOS | Mac mini에서 서버 런처와 운영 경로 확인 |
| Windows 네이티브 | Windows 11에서 런처 시작·중지, 로컬·원격 서버, 앱 AI 대전·저장, 원격 좌석 참여, 강제 종료 뒤 복구 확인(2026-10-12). 다른 PC에서의 접속·화면 배율·한글 입력은 남음 |
| WSL2 | 런처 지원(2026-10-30). 창은 WSLg로 Windows 바탕 화면에 뜨고, 원격 모드는 모든 주소에서 받음. 같은 PC의 관리자 링크와 Tailscale 주소 응답 확인. 다른 PC에서의 접속은 남음 |
| Linux | 터미널 실행 경로 안내. Ubuntu PC에서 원격 서버를 상시 서비스로 운영 중. 데스크톱의 런처 창은 확인하지 않음 |
| 참가자 브라우저 | 최신 데스크톱 브라우저와 쿠키 사용을 전제로 안내 |
| 모바일만으로 게임 진행 | 검증하지 않음 |

위 표는 기능의 구현 여부와 실제 기기에서 확인한 범위를 구분한 것입니다.
웹사이트가 휴대폰에서 읽히더라도 게임 화면의 모바일 플레이를 보장하지는 않습니다.

## 별도로 준비할 수 있는 항목

카드·보드 원본 이미지와 학습 모델은 소스에 포함하지 않습니다. 그림이 없으면 텍스트 화면으로 시작할 수 있고,
기본 AI는 별도 학습 모델 없이 사용할 수 있습니다. 탐색 AI는 학습한 모델 파일과 추가 의존성이 필요하며,
공개하는 모델 파일은 아직 없습니다.

[다운로드·설치 안내]({{< relref "downloads/_index.md" >}}) · [문제 해결]({{< relref "help/_index.md" >}})
