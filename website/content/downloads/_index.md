+++
title = "다운로드·설치 준비"
description = "현재 제공하는 소스 기반 설치와 운영체제별 준비 사항을 안내합니다."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 20
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "pyproject.toml", "docs/remote-play-host-guide.md", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd"]
+++

현재는 **프로젝트 소스를 받아 설치하는 방식**을 제공합니다. 2026년 10월 20일 확인 기준으로
공개 릴리스에 등록한 독립 실행 설치 파일이나 학습 모델은 없습니다.

[GitHub에서 소스 보기](https://github.com/jungcheolseung/Dune-Imperium) ·
[처음 한 판 시작하기]({{< relref "guides/first-game.md" >}})

## 먼저 내 역할을 확인하세요

| 하려는 일 | 준비할 것 |
| --- | --- |
| 내 PC에서 AI와 플레이 | 게임 소스, Git, uv, 서버 실행 환경 |
| 친구들과 방 만들기 | 위 준비물과 참가자가 연결할 네트워크 |
| 친구가 만든 방에 참여 | PC 브라우저와 방 링크; 다른 장소라면 Tailscale도 준비 |

초대받은 사람은 게임 소스·Python·학습 모델을 설치할 필요가 없습니다.
[친구 방 참여 안내]({{< relref "guides/joining.md" >}})로 바로 가세요.

## 운영체제별 안내

| 환경 | 설치 경로와 확인 범위 |
| --- | --- |
| macOS | 소스를 받은 뒤 런처 설치 또는 터미널 실행. Mac mini에서 런처 확인 |
| Windows | 소스를 받은 뒤 런처 설치 또는 PowerShell 실행. Windows 11 네이티브에서 런처·서버·원격 좌석 참여 확인(2026-10-12). 다른 PC에서의 접속·화면 배율·한글 입력 확인은 남음 |
| Linux | 터미널 실행 경로. 별도 실기 검증은 남음 |

프로젝트는 Python 3.14를 사용하며, uv가 해당 Python과 프로젝트 환경을 준비할 수 있습니다.
Git과 uv를 먼저 설치하고 [시작 안내]({{< relref "guides/first-game.md" >}})를 따라가면 됩니다.

런처 설치 스크립트는 **프로젝트 폴더 안에서 실행**합니다. 파일 하나만 내려받는 독립 설치 프로그램이 아닙니다.
소스 ZIP을 실행 패키지로 안내하지 않으며, 현재 시작 안내는 Git으로 받은 프로젝트를 기준으로 합니다.

## AI 모델은 선택 사항입니다

기본으로 사용할 수 있는 앱 AI에는 별도 학습 모델이 필요하지 않습니다.
탐색 AI나 학습 체크포인트 AI를 사용하려면 호환 모델과 추가 의존성을 호스트 PC에 준비해야 합니다.
모델은 지금 엔진의 행동 버전(codec)에 맞게 학습한 것이어야 하며, 현재 공개하는 모델 파일은 없습니다.
추가 의존성을 설치하는 것만으로 모델 파일까지 내려받아지지는 않습니다.

[AI 종류와 준비물 보기]({{< relref "guides/choosing-ai.md" >}})

## 이미지와 저장 파일

카드·보드 이미지 원본은 공개 소스에 포함하지 않습니다. 이미지 없이도 텍스트 화면으로 시작할 수 있습니다.
기존 이미지 자료를 연결하는 상세 방법은
[저장소의 이미지 안내](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/local-images.md)에 있습니다.

게임 저장은 서버가 실행되는 PC에 남습니다. 업데이트할 때는 프로젝트 폴더의 저장 파일과
기존 모델 파일을 보존하고, [저장·업데이트 안내]({{< relref "guides/controls.md" >}})를 확인하세요.
