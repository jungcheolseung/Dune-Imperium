+++
title = "다운로드·설치 준비"
description = "명령 한 줄로 설치하는 방법, 소스로 설치하는 방법과 운영체제별 확인 범위를 안내합니다."
date = 2026-10-20
lastmod = 2026-11-06
draft = false
weight = 20
[params]
source_ref = "5d2fea34"
sources = ["README.md", "pyproject.toml", "docs/remote-play-host-guide.md", "scripts/launcher/install.sh", "scripts/launcher/install.ps1", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd", "scripts/launcher/install-wsl.sh"]
+++

macOS와 Windows에서는 **명령 한 줄**로 설치합니다. Git과 Python을 따로 설치하지 않아도 됩니다. 한 줄 설치도 GitHub에 있는 최신 소스를
받아 설치하며, 2026년 11월 6일 기준으로 공개 릴리스에 등록한 독립 실행 설치 파일이나 학습 모델은 없습니다. 같은 설치로 원판과 Uprising을 모두 둡니다.

[GitHub에서 소스 보기](https://github.com/jungcheolseung/Dune-Imperium) ·
[처음 한 판 시작하기]({{< relref "guides/first-game.md" >}})

## 한 줄로 설치하기

macOS: **터미널** 앱(응용 프로그램 → 유틸리티)을 열고 붙여 넣습니다.

```bash
curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
```

Windows: 시작 메뉴에서 **PowerShell**을 열고 붙여 넣습니다.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
```

홈 폴더에 `Dune Imperium` 폴더가 생기고, 그 안에 게임 파일·uv·Python 3.14·서버 패키지가 들어갑니다. 마지막에 런처 바로가기를 만들고
런처를 엽니다. 처음에는 수십 MB를 내려받고, 설치한 폴더는 약 160 MB입니다.

| 할 일 | 방법 |
| --- | --- |
| 다음에 실행 | 그 폴더의 **Dune Imperium Server**를 더블클릭합니다. Dock이나 작업 표시줄에 끌어다 두면 편합니다 |
| 업데이트 | 런처를 닫고 같은 줄을 다시 실행합니다. 저장 파일·런처 설정·이미지·모델 파일은 그대로 남습니다 |
| 지우기 | 폴더를 통째로 지웁니다. 설치는 이 폴더 밖에 파일을 만들지 않고 PATH도 바꾸지 않습니다 |

Git으로 받은 프로젝트 폴더나 다른 파일이 든 폴더에는 설치하지 않고 멈춥니다. 런처가 켜진 채로 업데이트하면 런처를 닫으라는 안내가 나옵니다.
자세한 내용은 [저장소의 호스트 가이드](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md#한-줄-설치-gitpython-없이)에 있습니다.

## 먼저 내 역할을 확인하세요

| 하려는 일 | 준비할 것 |
| --- | --- |
| 내 PC에서 AI와 플레이 | 한 줄 설치(macOS·Windows), 또는 게임 소스·Git·uv |
| 친구들과 방 만들기 | 위 준비물과 참가자가 연결할 네트워크 |
| 친구가 만든 방에 참여 | PC 브라우저와 방 링크; 다른 장소라면 Tailscale도 준비 |

초대받은 사람은 게임 소스·Python·학습 모델을 설치할 필요가 없습니다.
[친구 방 참여 안내]({{< relref "guides/joining.md" >}})로 바로 가세요.

## 운영체제별 안내

| 환경 | 설치 경로와 확인 범위 |
| --- | --- |
| macOS | 한 줄 설치(2026-11-06 Apple Silicon Mac에서 확인), 또는 소스를 받은 뒤 런처 설치나 터미널 실행. Mac mini에서 런처 확인 |
| Windows | 한 줄 설치(2026-11-06 Windows 11의 PowerShell 5.1에서 확인), 또는 소스를 받은 뒤 런처 설치나 PowerShell 실행. Windows 11 네이티브에서 런처·서버·원격 좌석 참여 확인(2026-10-12). 다른 PC에서의 접속·화면 배율·한글 입력 확인은 남음 |
| Windows의 WSL2 | 소스를 WSL 안에 받은 뒤 WSL 터미널에서 `scripts/launcher/install-wsl.sh` 실행(2026-10-30부터). 런처 창은 WSLg로 Windows 바탕 화면에 뜸. 다른 PC에서의 접속 확인은 남음 |
| Linux | 터미널 실행 경로. Ubuntu PC에서 원격 서버를 상시 서비스로 운영 중. 데스크톱의 런처 창은 확인하지 않음 |

소스로 설치할 때는 Git과 uv를 먼저 설치하고 [시작 안내]({{< relref "guides/first-game.md" >}})를 따라갑니다. 프로젝트는 Python 3.14를 쓰며,
uv가 해당 Python과 프로젝트 환경을 준비합니다. 소스 설치의 런처 설치 스크립트(`Install Launcher`)는 **받은 프로젝트 폴더 안에서 실행**합니다.

## AI 모델은 선택 사항입니다

기본으로 사용할 수 있는 앱 AI에는 별도 학습 모델이 필요하지 않고, 한 줄 설치에도 들어 있습니다.
탐색 AI나 학습 체크포인트 AI를 사용하려면 호환 모델과 추가 의존성을 호스트 PC에 준비해야 합니다. 한 줄 설치는 이 둘을 넣지 않습니다.
이 두 AI는 Uprising 판에서만 앉으며, 현재 공개하는 모델 파일은 없습니다.
추가 의존성을 설치하는 것만으로 모델 파일까지 내려받아지지는 않습니다.

[AI 종류와 준비물 보기]({{< relref "guides/choosing-ai.md" >}})

## 이미지와 저장 파일

카드·보드 이미지 원본은 공개 소스와 한 줄 설치에 포함하지 않습니다. 이미지 없이도 텍스트 화면으로 시작할 수 있습니다.
기존 이미지 자료를 연결하는 상세 방법은
[저장소의 이미지 안내](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/local-images.md)에 있습니다.

게임 저장은 서버가 실행되는 PC에 남습니다. 한 줄 설치에서는 게임 폴더의 `saves`에 남고, 같은 줄로 업데이트해도 지워지지 않습니다.
소스 설치를 업데이트할 때는 프로젝트 폴더의 저장 파일과 기존 모델 파일을 보존하고, [저장·업데이트 안내]({{< relref "guides/controls.md" >}})를 확인하세요.
