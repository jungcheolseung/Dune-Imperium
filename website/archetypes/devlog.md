+++
title = "개발일지 제목"
description = "이번 작업에서 바뀐 점을 한두 문장으로 적습니다."
date = {{ time.Format "2006-01-02" .Date }}
publishDate = {{ time.Format "2006-01-02" .Date }}
lastmod = {{ time.Format "2006-01-02" .Date }}
draft = true
[params]
work_start = "{{ time.Format "2006-01-02" .Date }}"
source_ref = ""
sources = []
+++

## 작업 배경

어떤 문제를 해결하려 했는지 적습니다.

## 바꾼 것

구현한 동작과 이전 상태에서 달라진 점을 적습니다.

## 확인한 것과 남은 점

실행한 검증, 실험 조건과 결과, 해결하지 못한 점을 적습니다.
측정하지 않은 효과는 결과로 쓰지 않습니다.

## 참고 기록

관련 커밋과 작업 문서를 고정 커밋 주소로 연결합니다.
