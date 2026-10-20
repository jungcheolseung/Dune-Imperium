+++
title = "Dune: Imperium AI"
description = "Dune: Imperium - Uprising을 AI와, 친구들과 브라우저에서 플레이하고 더 나은 AI를 연구하는 개인 프로젝트입니다."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/remote-play-guide.md"]
+++

Dune: Imperium - Uprising을 AI와 연습하고, 친구들과 한 테이블에서 즐기는 프로젝트입니다.
Python 규칙 엔진 위에서 브라우저로 게임을 진행하며, 스스로 두고 배우는 AI를 연구합니다.

[설치하고 시작하기]({{< relref "downloads/_index.md" >}}) · [친구 방에 참여하기]({{< relref "guides/joining.md" >}})

## 원하는 방식으로 한 판

**AI와 연습하기.** 사람 한 명과 AI 세 명으로 게임을 만들 수 있습니다. 별도 학습 모델 없이 사용하는 기본 AI가 있고,
호환되는 모델 파일을 준비하면 탐색 AI도 선택할 수 있습니다.

**친구들과 플레이하기.** 한 사람이 서버를 켜고 방 링크를 보내면, 다른 사람들은 브라우저로 참여합니다.
사람이 네 명보다 적으면 빈자리는 AI로 채울 수 있습니다.

**다양한 구성으로 두기.** Uprising의 4인 게임을 바탕으로 CHOAM, Bloodlines, Immortality 등
지원하는 확장과 모듈을 선택할 수 있습니다. [지원 현황 보기]({{< relref "about/support.md" >}})

## 게임을 만들며 배우는 것

어떤 수가 가능한지 판단하는 규칙 엔진부터 AI가 국면을 읽고 다음 수를 고르는 과정까지 기록합니다.

- [보드게임 규칙을 실행 가능한 엔진으로 옮기기]({{< relref "posts/rules-to-engine.md" >}})
- [AI는 어떻게 한 수를 고르는가]({{< relref "posts/how-search-ai-chooses.md" >}})
- [혼자 배우기와 다른 상대에게 배우기]({{< relref "posts/learning-with-opponents.md" >}})

## 처음 오셨나요?

내 PC에서 실행하려면 [다운로드·설치 안내]({{< relref "downloads/_index.md" >}})를,
초대받은 방에 들어가려면 [참가자 안내]({{< relref "guides/joining.md" >}})를 보세요.
궁금한 점이나 실행 문제가 있다면 [도움말]({{< relref "help/_index.md" >}})에서 시작할 수 있습니다.

이 프로젝트는 비공식 개인 개발·연구 프로젝트입니다. 게임 서버는 본인 또는 호스트의 PC에서 실행합니다.
카드·보드 이미지 원본과 학습 모델은 소스에 포함하지 않으며, 이미지 없이도 텍스트 화면으로 시작할 수 있습니다.
