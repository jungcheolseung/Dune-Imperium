+++
title = "원판 Dune: Imperium과 모든 확장, 바뀐 화면과 서버"
description = "10월 22일 이후 달라진 점: 원판과 Rise of Ix, 확장 조합, Arrakeen Scouts의 받기, 게임 대기실과 경고, WSL 런처, 원격 서버 보안 보강."
date = 2026-11-03
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "81ca9468"
sources = ["README.md", "docs/development-handoff.md", "docs/worklog/2026-10.md", "docs/worklog/2026-11.md", "docs/remote-play-host-guide.md", "src/dune_imperium/server/static/index.html"]
update_kind = "project-status"
+++

[첫 기록]({{< relref "updates/2026-10-20-project-status.md" >}}) 뒤 10월 22일부터 11월 3일까지 플레이하는 사람에게 달라진 점을 모았습니다.
새 배포판 출시 공지가 아니라, 소스를 받아 실행하는 사람을 위한 변경 안내입니다.

## 두 기본 판과 모든 확장

- 새 게임 화면에서 **기본 판**을 고릅니다. 듄 임페리움: 봉기(Uprising)와 듄: 임페리움(원판) 가운데 하나입니다.
  원판은 보드·카드·지도자를 모두 갖췄고, 원판 보드 그림 위에서 둡니다(그림은 각자 준비하는 이미지 자료에 있을 때).
- **Rise of Ix**를 원판과 Uprising 모두에서 켤 수 있습니다. Immortality, Bloodlines와 Tech Module, Arrakeen Scouts,
  Epic Game Mode, 프로모 카드도 두 기본 판 모두에서 고릅니다. CHOAM Module은 Uprising에서만 열고, 원판의 Epic Game Mode는
  Rise of Ix 전부와 함께일 때만 엽니다. Uprising에는 원판 카드를 섞을 수 있습니다.
- Rise of Ix와 Tech Module을 함께 켜면 Ix를 얼마나 쓸지(전부, 지도자와 기술 타일만, 기술 타일만) 고릅니다.
- 원판 게임에는 앱 AI(어려움·보통·쉬움), 휴리스틱, 랜덤 AI가 앉습니다. 탐색 AI는 아직 Uprising에서만 앉습니다.

범위와 표는 [지원 현황]({{< relref "about/support.md" >}})에, 만드는 과정은
[원판과 Rise of Ix 개발일지]({{< relref "devlog/2026-11-02-original-game-and-ix.md" >}})에 있습니다.

## 게임 화면

- 원격 방은 사람 좌석이 모두 찰 때까지 **게임 대기실**로 열리고, 참여한 사람 누구나 **게임 시작 ▶**을 누릅니다.
  자리는 시작할 때 무작위로 정해집니다. 새 게임 화면의 "자리 무작위 배치" 칸은 없앴습니다(11월 1일).
- **플레이어1이 시작 플레이어** 칸이 생겼습니다(기본 켜짐). 공식 규칙이 아닌 프로젝트 운영 방식입니다.
- 턴을 끝내거나 다른 줄을 골라 쓰지 않은 효과가 사라질 때 ⚠ 경고 줄이 먼저 나옵니다(10월 31일).
- Arrakeen Scouts의 나중 보상과 이벤트·임무의 몫은 받는 플레이어가 **받기**를 눌러 받습니다. 비밀 선택에는 효과가 나오는
  라운드 번호가 붙습니다(11월 1일). 자세한 내용은 [Scouts 개발일지]({{< relref "devlog/2026-11-01-scouts-on-original.md" >}})에 있습니다.
- 앱 AI 좌석의 색은 앱의 기본 순서(초록·빨강·노랑·파랑)를 따르고, 좌석 패널에 **자세히** 창, 활동 기록에 턴마다 카드 그림이
  생겼습니다(10월 26일).
- 효과에 쓴 이번 턴의 교전 유닛은 회수할 수 없고, 끝난 게임은 되돌릴 수 없습니다.

## 서버와 런처

- 서버 런처가 Windows의 **WSL2**에서도 동작합니다. WSL 터미널에서 `scripts/launcher/install-wsl.sh`를 실행합니다(10월 30일).
- 원격 서버의 보안을 보강했습니다(11월 3일). 연결·요청 크기에 한도를 두었고, 직접 정하는 관리자 키는 영문자·숫자·`-`·`_` 16자
  이상이어야 합니다. 업데이트한 뒤 호스트는 **관리자 링크를 한 번 다시 엽니다**. [호스트 안내]({{< relref "guides/hosting.md" >}})
- 프로젝트의 플레이 서버는 10월 31일부터 자기 대국으로 다시 학습한 탐색 AI 모델을 씁니다. 공개하는 모델 파일은 아직 없습니다.
  [자기 대국 개발일지]({{< relref "devlog/2026-11-01-self-play-stage-one.md" >}})

## 업데이트할 때

이 기간에 규칙·행동 버전(codec)이 여러 번 올라갔습니다. 업데이트 전의 저장을 새 서버가 열지 못할 수 있으니
진행 중인 판은 쓰던 코드로 마치거나 저장 파일과 그 판의 코드 버전을 보관하세요.
[저장·업데이트 안내]({{< relref "guides/controls.md" >}})
