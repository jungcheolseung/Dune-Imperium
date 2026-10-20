+++
title = "브라우저 플레이, 저장과 리플레이, 되돌리기"
description = "사람이 직접 두는 화면을 만들고, 게임을 저장하거나 지난 선택을 검토하는 기능을 추가했습니다."
date = 2026-09-03
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-08-30"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-08.md", "docs/worklog/2026-09.md"]
+++

## 사람이 두는 화면

휴리스틱 AI와 지도자 드래프트를 연결하고, FastAPI 세션 서버 위에 HTML·CSS·JavaScript 화면을 만들었습니다. 처음에는 텍스트 카드와 행동 버튼으로 한 판을 끝까지 진행했습니다. 브라우저가 별도로 규칙을 판단하지 않고 서버가 보내는 관측과 선택지를 표시하도록 구성했습니다.

## 저장과 검토

8월 31일에는 저장·불러오기와 종료된 게임의 리플레이 검토를 추가했습니다. 불러온 뒤의 진행이 저장하지 않은 게임과 같은지도 비교했습니다. 저장 기록에는 덱 순서처럼 비공개 정보가 포함될 수 있어, 원본 파일을 브라우저에 그대로 보내지 않았습니다.

9월 초에는 행동 로그와 되돌리기를 붙이고 보드 중심 화면을 정리했습니다. 새 정보를 본 뒤까지 마음대로 되돌리는 문제가 없도록 정보 공개 경계도 함께 검토했습니다.

## 확인한 것

실제 서버와 Chromium에서 게임 생성부터 완주, 중간 저장·불러오기, 종료 후 기록 탐색까지 확인했습니다. 이후 개발에서도 엔진 테스트와 실제 브라우저 검사를 함께 사용하는 흐름이 이어집니다.

## 참고 기록

- [브라우저 첫 전체 게임](https://github.com/jungcheolseung/Dune-Imperium/commit/42be8833)
- [저장·불러오기와 리플레이 화면](https://github.com/jungcheolseung/Dune-Imperium/commit/e44900ae)
- [되돌리기와 실시간 행동 로그](https://github.com/jungcheolseung/Dune-Imperium/commit/993bf11d)
