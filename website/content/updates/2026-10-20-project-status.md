+++
title = "첫 기록: 지금 할 수 있는 일과 다음 목표"
description = "AI 대전과 멀티플레이, 현재 설치 방식과 앞으로의 기록을 소개합니다."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/development-handoff.md", "docs/worklog/2026-10.md"]
update_kind = "project-status"
+++

Dune: Imperium AI의 첫 소식으로 현재 가능한 플레이와 다음 개발 방향을 정리합니다.
이 글은 프로그램의 새 배포판 출시 공지가 아닌 프로젝트 현황 안내입니다.

## 지금 할 수 있는 일

Uprising의 4인 게임을 AI와 또는 친구들과 진행할 수 있습니다.
CHOAM, Bloodlines, Immortality와 지원 모듈을 선택하고 사람·AI 좌석을 섞어 구성합니다.
한국어·영어 화면, 저장·이어 하기, 끝난 게임의 리플레이 검토도 제공합니다.

혼자 시작하려면 [처음 한 판]({{< relref "guides/first-game.md" >}})을,
친구들과 플레이하려면 [호스트 안내]({{< relref "guides/hosting.md" >}})와
[참가자 안내]({{< relref "guides/joining.md" >}})를 보세요.

## 설치와 지원 범위

현재 설치 방법은 소스 기반입니다. 별도 모델 없이 사용하는 기본 AI가 있고,
호환 모델을 준비한 환경에서는 학습 모델과 탐색 AI도 사용할 수 있습니다.
카드·보드 이미지 원본과 학습 모델은 공개 소스에 포함되지 않습니다.

macOS에서 확인한 런처 경로를 안내하며, Windows 네이티브와 Linux의 별도 실기 확인은 남아 있습니다.
구체적인 내용은 [다운로드]({{< relref "downloads/_index.md" >}})와
[지원 현황]({{< relref "about/support.md" >}})에 정리했습니다.

## 다음으로 기록할 것

엔진에서는 카드·보드 효과와 행동의 표현을 정리하는 작업을 이어 갑니다.
AI에서는 카드와 행동의 특성을 읽는 모델을 실험하고, 실제 대전과 탐색에 도움이 되는지 확인합니다.
플레이에서 나온 조작·되돌리기·저장 관련 피드백도 반영합니다.

이 과정은 [규칙 엔진과 AI 개발 이야기]({{< relref "posts/_index.md" >}})에서 다룹니다.
첫 글로 엔진의 구조, 탐색 AI의 판단 과정, 학습 상대를 바꾼 대조 실험을 준비했습니다.

진행 중인 게임이 있다면 코드·모델을 업데이트하기 전에
[저장과 호환 안내]({{< relref "guides/controls.md" >}})를 확인하세요.
