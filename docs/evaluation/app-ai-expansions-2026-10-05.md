# 앱식 AI(app_ai) 확장판 A/B — 2026-10-05

기준: 브랜치 `app-ai-expansions` HEAD `110fa5bf`(작업 트리 `src` 변경 없음), Mac mini(M4 10코어).
설계와 구현 경위는 [`../app-ai-plan.md`](../app-ai-plan.md) 11절, 확장 전 A/B는 [`app-ai-2026-10-05.md`](app-ai-2026-10-05.md).

## 1. 무엇을 쟀나

app_ai를 모든 선택지로 넓혔다.
- 앱에 있는 것(Immortality, Go to 11, Epic Game Mode, 프로모, 지도자 드래프트)은 충실 포팅했다.
- 앱에 없는 것(Bloodlines와 Tech 모듈, Arrakeen Scouts)은 앱식으로 확장했다. 값은 앱 데이터에 맞춘 규칙으로, 결정은 앱식 단순 판단으로 만든다.
- heuristic 결정은 섞지 않는다.

이 문서는 두 가지를 잰다.
1. **통합 census**: 4좌석 app_ai로 선택지 조합마다 게임을 끝까지 두고, 앱이 답하지 못해 무작위로 넘긴 결정(`fallbacks`)과 포팅되지 않은 능력 조회(`UNPORTED`)를 센다.
2. **축별 A/B**: 선택지마다 app_ai(Hard) 대 우리 heuristic을 2:2 거울 대국으로 두고, 끝으로 전부 켠 게임에서 Hard 대 Easy를 둔다. 시드는 250개이고 CHOAM 유무를 함께 돌리며(`--ruleset both`), 지도자는 시드마다 무작위로 돌린다(`--rotate-leaders`; Bloodlines 칸은 Bloodlines 지도자 포함).

스크립트와 출력은 `ab-runs/app-ai-expansions/`(git 무시)에 있다. census 스크립트는 세션 scratchpad의 `option_matrix_census.py`다.

```bash
uv run dune-imperium-tournament --agents app_ai,heuristic,app_ai,heuristic --games 250 --ruleset both \
    --rotate-leaders --workers 8 --bloodlines --tech-module --matches ab-runs/app-ai-expansions/bloodlines.jsonl
uv run python scripts/ab/paired.py ab-runs/app-ai-expansions/bloodlines.jsonl --a app_ai --b heuristic
```

## 2. 통합 census (16개 조합 × 12판, 4좌석 app_ai Hard)

| 조합 | 오류 | 무작위 대체 | 미포팅 | 판당 초 |
|---|---:|---:|---:|---:|
| base, 프로모, 드래프트 | 0 | 0 | 0 | 1.1–1.2 |
| Immortality, Go to 11 | 0 | 0 | 0 | 1.4 |
| Epic, Epic+Immortality, Epic+Go to 11 | 0 | 0 | 0 | 1.2–1.4 |
| Bloodlines, +Tech, +Tech+프로모, 드래프트+Bloodlines+Tech | 0 | 0 | 0 | 1.2–1.4 |
| Scouts, Scouts+Immortality, Scouts+Bloodlines+Tech | 0 | 0 | 0 | 1.1–1.3 |
| 전부(프로모·Bloodlines·Tech·Immortality·Go to 11·Epic·Scouts) | 0 | 0 | 0 | 1.6 |

모든 결정이 앱 로직이나 앱식 확장 규칙으로 답해졌다. 앱 판단으로 답한 결정은 조합마다 6,852–11,457개다. 확장판을 끈 base·CHOAM 게임은 확장 작업 전후로 같은 시드 40판의 행동 열이 한 수도 다르지 않다.

## 3. 축별 A/B

좌석당 승률의 무작위 기대값은 25%다. "차이"는 `scripts/ab/paired.py`가 시드 묶음 부트스트랩으로 낸 A−B의 95% 구간이다. 이 도구의 승률 줄은 두 좌석을 합친 몫이라, 아래 표에는 좌석당 승률을 따로 적었다.

| 칸 (각 1,000판) | 좌석당 승률 A / B | 평균 순위 A / B | VP 차 (95% 구간) | 결정당 ms (app_ai) |
|---|---|---|---|---:|
| Immortality: app_ai 대 heuristic | 47.5% / 2.5% | 1.75 / 3.25 | +4.47 [+4.32, +4.63] | 1.24 |
| Go to 11 | 47.4% / 2.6% | 1.73 / 3.27 | +4.93 [+4.77, +5.08] | 1.21 |
| Epic Game Mode | 45.9% / 4.1% | 1.75 / 3.25 | +4.82 [+4.64, +5.00] | 1.06 |
| 프로모 | 45.8% / 4.2% | 1.80 / 3.20 | +4.12 [+3.97, +4.28] | 1.08 |
| Bloodlines + Tech 모듈 | 46.7% / 3.3% | 1.74 / 3.26 | +4.65 [+4.49, +4.79] | 1.27 |
| Arrakeen Scouts | 46.5% / 3.5% | 1.76 / 3.24 | +4.38 [+4.23, +4.52] | 1.07 |
| 전부 켬 | 47.2% / 2.8% | 1.72 / 3.28 | +5.89 [+5.70, +6.09] | 1.44 |
| 전부 켬: Hard 대 Easy | 34.0% / 15.9% | 2.19 / 2.81 | +2.40 [+2.16, +2.64] | 1.44 / 1.36 |
| 지도자 드래프트 (2026-10-06 추가) | 46.6% / 3.4% | 1.76 / 3.24 | +4.22 [+4.08, +4.36] | 1.35 |

모든 칸에서 실패 0, 불법 행동 0이다.

## 4. 해석

- **앱식 확장도 앱 AI의 강도를 유지한다.** 앱에 없는 Bloodlines·Scouts에서도 app_ai Hard는 heuristic을 상대로 좌석당 46–47%를 이긴다. 이는 앱에 있는 선택지(45.8–47.5%)나 확장 전 Uprising(46.5%)과 같은 수준이다. 확장 규칙이 앱의 판단 틀을 깨뜨리지 않았다는 뜻이다. 다만 heuristic이 확장판에서 얼마나 잘 두는지는 따로 재지 않았으므로, 이 결과는 "망가지지 않았다"는 증거이지 "앱식 확장이 최선"이라는 증거는 아니다.
- **난이도 순서가 확장판에서도 유지된다.** 전부 켠 게임에서 Hard가 Easy를 이긴다(+36pp, 두 좌석 합). 확장 전 Uprising의 Hard 대 Easy(+47pp)보다 차이가 작다. 앱식 확장 부분에는 난이도 상수가 덜 들어가기 때문으로 보인다(새 판단 대부분이 상수표가 아닌 규칙에서 값을 얻는다).
- 지도자별 승률은 Bloodlines 지도자 사이에 차이가 있다. Esmar Tuek은 61.9%, Mohiam은 33.9%다(app_ai 좌석, 칸당 약 100–130판). 앱식 확장이 어떤 지도자를 덜 잘 쓰는지 볼 실마리이지만, 판 수가 적어 결론은 내리지 않는다.

## 5. 한계

- 앱식 확장 부분(Bloodlines, Tech, Scouts)은 비교할 앱 동작이 없다. 정확성은 사양 문서(`docs/app-ai/*.md`)와 계획 11절 규칙에 대한 독립 검증으로만 보장된다.
- 지도자 드래프트는 처음에는 대전 도구에 플래그가 없어 census(드래프트 조합 2개)로만 확인했다. 2026-10-06에 `--leader-draft`를 더해 3절 표의 마지막 줄(시드 250개 × CHOAM 유무, 지도자는 각 좌석이 직접 고름)을 쟀다. 앱 AI의 드래프트 선택은 앱처럼 균등 무작위다.
- 학습 망과 search는 확장판 규칙으로 학습하지 않았으므로 이번 A/B에 넣지 않았다.
