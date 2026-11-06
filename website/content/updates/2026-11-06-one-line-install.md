+++
title = "Git·Python 없이 한 줄로 설치"
description = "macOS와 Windows에서 명령 한 줄로 게임을 설치하고 업데이트합니다."
date = 2026-11-06
publishDate = 2026-11-06
lastmod = 2026-11-06
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "5d2fea34"
sources = ["README.md", "docs/remote-play-host-guide.md", "docs/worklog/2026-11.md", "scripts/launcher/install.sh", "scripts/launcher/install.ps1"]
update_kind = "project-status"
+++

지금까지는 게임을 직접 실행하려면 Git과 uv를 설치하고 소스를 받아야 했습니다. 11월 6일부터 macOS와 Windows에서는 명령 한 줄로 설치합니다.
새 배포판 출시 공지가 아니라 설치 방법이 하나 늘었다는 안내입니다. 한 줄 설치도 GitHub에 있는 최신 소스를 받아 설치합니다.

## 설치하는 줄

macOS의 **터미널**:

```bash
curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
```

Windows의 **PowerShell**:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
```

## 무엇이 달라지나

- 홈 폴더의 `Dune Imperium` 폴더 하나에 게임 파일·uv·Python 3.14·서버 패키지가 들어가고, 런처 바로가기가 생깁니다.
  폴더 밖에는 파일을 만들지 않고 PATH도 바꾸지 않으므로, 지울 때는 폴더만 지우면 됩니다.
- 업데이트는 런처를 닫고 같은 줄을 다시 실행합니다. 저장 파일·런처 설정·이미지·모델 파일은 그대로 남습니다.
- 앱 AI까지 들어갑니다. 카드·보드 이미지와 탐색 AI는 들어가지 않습니다.
- 2026-11-06에 Apple Silicon Mac과 Windows 11(PowerShell 5.1, uv와 Python이 없던 PC)에서 새 설치, 업데이트, 한글과 공백이 든 경로,
  설치한 서버로 게임 만들기를 확인했습니다. Linux와 WSL2는 지금처럼 소스로 설치합니다.

자세한 안내는 [다운로드·설치 준비]({{< relref "downloads/_index.md" >}})와 [처음 한 판 시작하기]({{< relref "guides/first-game.md" >}})에 있습니다.
친구가 연 방에 참여하는 사람은 지금처럼 아무것도 설치하지 않아도 됩니다.
