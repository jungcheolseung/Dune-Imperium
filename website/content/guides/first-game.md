+++
title = "처음 한 판 시작하기"
description = "소스를 준비하고 서버를 켠 다음 사람 한 명과 AI 세 명으로 첫 게임을 만듭니다."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 10
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "pyproject.toml", ".python-version", "docs/remote-play-host-guide.md", "src/dune_imperium/cli/server.py", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd"]
+++

처음에는 사람 한 명과 기본 AI 세 명으로 시작해 보세요. 학습 모델이나 카드·보드 이미지를
준비하지 않아도 됩니다. PC의 브라우저와 게임 서버를 실행할 환경이 필요합니다.

macOS와 Windows 11(네이티브)에서 런처와 서버 실행을 확인했습니다. Windows는 다른 PC에서 접속하는 경우 같은 일부 수동 확인이 남아 있고,
Linux는 별도 실기 확인이 남아 있습니다. [지원 현황]({{< relref "about/support.md" >}})

## 1. Git과 uv 준비

Git으로 소스를 받고 uv로 Python과 실행 환경을 준비합니다. Git이 없다면
[Git 공식 다운로드](https://git-scm.com/downloads)를 참고하세요.

이미 다음 두 명령이 실행되면 설치를 건너뛸 수 있습니다.

```text
git --version
uv --version
```

uv가 없다면 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 따르세요.
macOS·Linux 터미널에서는 다음 방법을 사용할 수 있습니다.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell에서는 WinGet을 사용할 수 있습니다.

```powershell
winget install --id=astral-sh.uv -e
```

설치한 뒤 터미널을 새로 열고 `uv --version`을 확인하세요.

## 2. 프로젝트 폴더 준비

처음 설치하는 폴더에서 아래를 실행합니다. 이미 받은 프로젝트가 있다면 그 폴더를 사용하세요.

```bash
git clone https://github.com/jungcheolseung/Dune-Imperium.git
cd Dune-Imperium
uv python install 3.14
```

프로젝트는 Python 3.14를 사용합니다. uv가 필요한 Python을 준비하므로 시스템 Python을 직접 교체하거나
가상 환경을 따로 활성화할 필요는 없습니다. [uv의 Python 설치 안내](https://docs.astral.sh/uv/guides/install-python/)

이후 명령과 런처 설치는 모두 받은 프로젝트 폴더를 기준으로 합니다.

## 3. 서버 켜기

### 창으로 실행하기

프로젝트의 `scripts/launcher` 폴더에서 운영체제에 맞는 파일을 실행합니다.

| 운영체제 | 처음 한 번 실행할 파일 |
| --- | --- |
| macOS | `Install Launcher.command` |
| Windows | `Install Launcher.cmd` |

설치 중 탐색 AI 의존성을 추가할지 물으면 첫 게임에서는 선택하지 않아도 됩니다.
이 선택은 실행 패키지를 설치하는 것이며, 학습 모델 파일을 내려받는 것은 아닙니다.

설치가 끝나면 프로젝트 폴더의 **Dune Imperium Server** 바로가기로 런처를 엽니다.
**이 컴퓨터에서만 (로컬)**을 고르고 **시작**을 누르면 브라우저에 게임 화면이 열립니다.

### 터미널로 실행하기

런처 대신 다음을 프로젝트 폴더에서 실행할 수 있습니다. macOS·Linux 터미널과 Windows PowerShell에서 같은 명령을 씁니다.

```bash
uv sync --locked --extra ui
uv run dune-imperium-server --autosave
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다. 이 명령은 자동 저장을 켭니다.
게임 중에는 서버를 실행한 터미널을 열어 두세요.

위 의존성 명령은 새 플레이 환경을 위한 것입니다. 기존 개발·학습 환경에서는
`uv sync --locked --extra rl --extra ui --extra train`으로 설치한 구성을 함께 유지하세요.

## 4. 첫 게임 만들기

1. 네 좌석 중 내 좌석 하나를 사람으로, 나머지를 앱 AI로 설정합니다.
2. 규칙 옵션을 고릅니다. 새 게임 화면은 지도자 드래프트, CHOAM, 프로모 카드, Bloodlines, Tech, Immortality, Go to 11, Epic Game Mode가 모두 켜진 채로 열립니다(Arrakeen Scouts만 꺼짐). 기본 4인 게임으로 익히려면 체크를 모두 끄세요.
3. 게임을 만들고 화면에서 현재 내 차례와 선택할 수 있는 행동을 확인합니다.
4. 카드와 칸을 고른 뒤 남은 선택을 처리하고 **턴 종료 ▶**를 누릅니다.

앱 AI에는 별도 학습 모델이 필요하지 않습니다. 그림이 없으면 텍스트 카드·보드로 진행할 수 있습니다.

## 5. 멈추고 이어 하기

게임을 마치기 전 **저장**을 누르세요. 런처와 위 터미널 명령은 자동 저장을 사용하지만,
자동 저장은 턴이 넘어갈 때 이뤄져 진행 중인 한 턴의 선택이 모두 남는 것은 아닙니다.
다시 서버를 켠 뒤 저장 목록에서 이어 할 게임을 불러옵니다.

[기본 조작·저장]({{< relref "guides/controls.md" >}}) ·
[AI 고르기]({{< relref "guides/choosing-ai.md" >}}) ·
[친구 초대하기]({{< relref "guides/hosting.md" >}})
