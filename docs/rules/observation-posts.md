# Observation Post Connections

이 문서는 Uprising 기본 보드의 4인 면에 인쇄된 observation post와 board space의 직접 연결 관계를 전사한다. ID는 구현에서 안정적으로 참조하기 위해 만든 설명형 ID이며 공식 명칭은 아니다. 연결은 원형 observation post에서 끝나는 흰색 선만 따라 판독했다. [Main pp. 4-5 board artwork]

## Connection graph

| Stable ID | Directly connected board spaces | 판독 확신 | Source |
|---|---|---|---|
| `emperor-sardaukar-dutiful-service` | `Sardaukar`, `Dutiful Service` | 높음 | [Main pp. 4-5 board artwork] |
| `landsraad-high-council-imperial-privilege-swordmaster` | `High Council`, `Imperial Privilege`, `Swordmaster` | 높음; 세 갈래 연결 | [Main pp. 4-5 board artwork] |
| `landsraad-assembly-hall-gather-support` | `Assembly Hall`, `Gather Support` | 높음 | [Main pp. 4-5 board artwork] |
| `choam-shipping-accept-contract` | `Shipping`, `Accept Contract` | 높음 | [Main pp. 4-5 board artwork] |
| `spacing-guild-heighliner-deliver-supplies` | `Heighliner`, `Deliver Supplies` | 높음 | [Main pp. 4-5 board artwork] |
| `arrakis-research-station-spice-refinery` | `Research Station`, `Spice Refinery` | 높음 | [Main pp. 4-5 board artwork] |
| `arrakis-research-station-sietch-tabr` | `Research Station`, `Sietch Tabr` | 높음 | [Main pp. 4-5 board artwork] |
| `arrakis-spice-refinery-arrakeen` | `Spice Refinery`, `Arrakeen` | 높음; 페이지 경계 양쪽 선을 맞춰 확인 | [Main pp. 4-5 board artwork] |
| `arrakis-imperial-basin` | `Imperial Basin` | 높음; 단일 공간 연결 | [Main pp. 4-5 board artwork] |
| `arrakis-hagga-basin` | `Hagga Basin` | 높음; 단일 공간 연결 | [Main pp. 4-5 board artwork] |
| `arrakis-deep-desert` | `Deep Desert` | 높음; 단일 공간 연결 | [Main pp. 4-5 board artwork] |
| `bene-gesserit-espionage-secrets` | `Espionage`, `Secrets` | 높음 | [Main pp. 4-5 board artwork] |
| `fremen-desert-tactics-fremkit` | `Desert Tactics`, `Fremkit` | 높음 | [Main pp. 4-5 board artwork] |

## 구현 시 주의

- 이 관계는 observation post와 board space 사이의 **직접 연결**이다. 같은 post에 연결된 공간끼리 또는 연쇄된 post를 통해 이어지는 공간끼리 별도의 space-to-space edge를 만들면 안 된다. [Main pp. 4-5 board artwork]
- `Research Station`과 `Spice Refinery`는 각각 서로 다른 observation post 두 곳에 직접 연결된다. `High Council`·`Imperial Privilege`·`Swordmaster`는 하나의 동일한 observation post를 공유한다. 반대로 `Imperial Basin`, `Hagga Basin`, `Deep Desert`의 post는 각 공간 하나에만 연결된다. [Main pp. 4-5 board artwork]
- setup 그림은 두 페이지에 걸쳐 분할되어 있다. `arrakis-spice-refinery-arrakeen`은 양쪽의 원본 보드 레이어를 같은 높이로 맞춰 선의 연속성을 확인했지만, 향후 더 높은 해상도의 공식 보드 자산이 제공되면 한 번 더 대조하는 것이 안전하다. 특히 Arrakis 영역의 큰 외곽선과 post의 흰 연결선을 별개의 선으로 유지해 검증해야 한다. [Main pp. 4-5 board artwork]
- 이 목록은 setup에 표시된 기본 4인 보드 면만 다룬다. 6인용 추가 보드나 다른 확장의 observation post를 이 graph에 암묵적으로 합치지 않는다. [Main pp. 4-5 board artwork]
