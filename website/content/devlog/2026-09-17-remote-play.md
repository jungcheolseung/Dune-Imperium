+++
title = "친구들과 접속하는 원격 플레이"
description = "좌석별 접속 권한과 호스트 관리를 나누고, 턴 확정·자동 저장·복구를 원격 게임에 적용했습니다."
date = 2026-09-17
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-17"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/remote-play-guide.md"]
+++

## 한 PC에서 여러 브라우저로

로컬 화면을 번갈아 사용하는 방식에서 각자 브라우저로 접속하는 원격 방으로 넓혔습니다. 좌석 참가와 관리자 권한을 나누고, 브라우저가 자기 좌석의 정보를 받도록 했습니다.

여러 창이 동시에 접속할 때는 화면에 보이는 차례와 서버 상태를 맞추는 것이 중요했습니다. 클라이언트 동기화와 턴 확정 흐름을 다듬고, 사람 차례가 넘어갈 때 자동 저장하도록 했습니다.

## 실제 주소로 리허설

Tailscale 주소로 접속해 여러 클라이언트의 게임 진행과 저장·복구를 확인했습니다. 이 과정에서 서버가 주소에 바인딩하지 못했는데도 접속 링크부터 출력하는 문제를 발견했습니다. 시작 전에 주소와 포트를 점검하고 실패 이유를 표시하도록 고쳤습니다.

이 단계는 원격 기능과 운영 경로를 검증한 기록입니다. 친구들과 실제로 플레이한 뒤의 사용성 피드백은 10월 기록으로 이어집니다.

## 참고 기록

- [좌석 참가와 관리자 키](https://github.com/jungcheolseung/Dune-Imperium/commit/e6b9c9da)
- [차례가 넘어갈 때 자동 저장](https://github.com/jungcheolseung/Dune-Imperium/commit/903090d6)
- [Tailscale 주소 리허설](https://github.com/jungcheolseung/Dune-Imperium/commit/ff380679)
