+++
title = "프로젝트 웹사이트 공개"
description = "소개·설치·사용법과 엔진·AI 설명 글을 모으고, Hugo와 GitHub Pages로 공개했습니다."
date = 2026-10-20
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-20"
retrospective = true
source_ref = "b7787979"
sources = ["website/README.md", ".github/workflows/website.yml"]
+++

## 문서의 입구 만들기

저장소의 개발 문서와 별도로 프로젝트 소개, 다운로드·설치 안내, 사용법, 규칙 엔진과 AI 설명, 업데이트를 읽을 수 있는 웹사이트를 만들었습니다. 소스는 `website/`에 두고 Hugo로 빌드합니다.

모바일 메뉴, 목차, 분류, 정적 검색, RSS를 추가했습니다. 사이트 빌드에는 게임 의존성이나 비공개 카드 이미지·모델이 필요하지 않습니다.

## GitHub Pages 배포

사이트 관련 변경을 `master`에 올리면 GitHub Actions가 빌드와 링크·브라우저 검증을 거쳐 Pages에 배포합니다. 첫 변경을 병합한 뒤 배포 성공과 공개 주소의 홈·사용법·검색 자료·RSS 응답을 확인했습니다. PR은 변경 검토에 사용할 수 있고, 배포 자체는 `master` 반영으로 시작됩니다.

사이트 공개와 게임 설치 패키지·학습 모델 배포는 별개의 일입니다. 다운로드 안내에는 현재 제공하는 방식만 적었습니다.

## 개발 기록 이어 쓰기

첫 화면의 홍보성 문구는 줄이고 프로젝트 설명을 중심으로 바꿉니다. 커밋과 문서에 흩어진 과거 작업을 날짜별 개발일지로 묶고, 이후의 구현과 실험도 같은 형식으로 이어서 남깁니다.

## 참고 기록

- [첫 화면·검색 구현](https://github.com/jungcheolseung/Dune-Imperium/commit/7c2cac41)
- [검증과 배포 workflow](https://github.com/jungcheolseung/Dune-Imperium/commit/40322e7b)
- [첫 웹사이트 병합](https://github.com/jungcheolseung/Dune-Imperium/commit/b7787979)
