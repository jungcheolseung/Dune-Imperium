# 교훈 기록

같은 실수를 반복하지 않기 위해 규칙·프로세스 위반 사례를 남긴다. 새 세션은 이 문서를 읽고 시작한다.

## 2026-08-28 — 규칙 문서를 확인하지 않고 리뷰 지적을 반영함

- 무슨 일: 코드 리뷰 finder가 "Intrigue로 얻은 spice가 Harvest 계약 판정을 오염시킨다"고 지적했고, 규칙 문서를 열어 보지 않은 채 Intrigue 보상 spice를 Harvest 합계에서 제외하는 보정을 구현·테스트·커밋했다(`7f24ac0`).
- 실제 규칙: [`rules/choam-module.md`](rules/choam-module.md)에 "Harvest contract는 Maker space에 Agent를 보내고, 그 turn에 **모든 출처를 합쳐** 표시된 양의 spice를 얻으면 완료한다 `[Main p. 16]`"라고 이미 적혀 있었다. 즉 Intrigue 보상 spice도 합산 대상이다. 사용자가 지적해 `08207bc`로 되돌렸다.
- 원인: 리뷰 finder의 서술을 규칙 근거로 착각했고, 기존 판정식(순증가 = 수확)을 보고 "수확만 센다"는 전제를 스스로 만들어 냈다.
- 재발 방지: 규칙 동작을 바꾸는 모든 변경(버그 수정, 리뷰 반영, 테스트 기대값 포함)은 먼저 `docs/rules/`의 해당 문장과 인용을 확인하고 커밋 메시지나 테스트 주석에 그 근거를 적는다. 문서가 침묵하면 구현하지 않고 `open-questions.md`에 올린다. `AGENTS.md`와 `CLAUDE.md`에 이 규칙을 명문화했다.
