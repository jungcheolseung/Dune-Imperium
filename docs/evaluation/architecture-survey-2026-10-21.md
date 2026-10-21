# 모델 구조 점검: 다른 게임 AI와의 비교와 다음 개선 순서 (2026-10-21)

> 원제: 구조는 합격선, 승부는 탐색과 학습 신호에서 난다

2026-10-21 하루 동안 공개 자료(논문·공식 저장소·개발자 글)를 다섯 갈래로 조사해 쓴 보고서다. 갈래는 TabletopGames와 보드게임,
디지털 카드게임, 불완전 정보 게임, 대형 게임 에이전트와 큰 행동 공간 연구, 구조 대 학습 방법이다. 조사 노트(약 225 KB)는 git 밖
Mac mini의 `tmp/claude/4767ed6a/research/research_notes/`에 있고, 이 문서는 보고서 본문을 그대로 옮긴 것이다. 공개용 요약은 웹사이트
기술 글 [다른 게임 AI와 비교한 모델 구조 점검](../../website/content/posts/architecture-survey.md)이고, 이 보고서에 따른 다음 순서는
[개발 인수인계](../development-handoff.md) "학습·AI"의 "모델 구조 점검 뒤 다음 순서"에 있다.

읽을 때 주의:

- 문헌 수치는 조사 노트가 1차 자료에서 옮긴 값이다. LoCM 탐색(26.8% → 51.35%)은 원 논문 초록과 다시 대조했다. 노트끼리 엇갈린
  DORA의 Elo 값은 공개 글에서 뺐다.
- 우리 측정의 "망 혼자 약 55% → 탐색 좌석 81.8%(+27%p)"는 서로 다른 측정의 근사다. 탐색 좌석은 2026-10-15 codec v147(400판),
  망 혼자는 2026-10-21 codec v149(1,000판)이고 시드도 다르다.
- 비용·기대 효과는 추정이다. 실험 E1~E8은 아직 하나도 돌리지 않았다.
- E2(세계 16 대 8)는 2026-09에 이미 쟀다. 새 1,000판에서 +2.2%p [−1.6, +5.8]로 미리 정한 기준을 넘지 못했고 판당 시간은 2배였다
  ([m10-2026-09-22.md](m10-2026-09-22.md) 16절). 엔진·모델이 바뀌었으니 다시 잴 수는 있지만, 우선순위는 낮다.

---

우리 Dune: Imperium – Uprising AI의 두 망은 비교할 만한 게임 AI들이 실제로 쓰는 설계의 한복판에 있다. 그래서 "합리적인가"에는 근거 있게 "그렇다"고 답할 수 있지만, "최적인가"에는 "아니다"가 답이다. MLP(평평한 개수 벡터 → 512×512 → 카탈로그 행동마다 한 행)는 PyTAG·Big 2·Suphx/Mortal·LOCM의 "고정 출력 행 + 합법 mask" 패턴이다. 엔티티 망(개체 임베딩의 구역 합 + 공유 좌석 인코더 → 상태 query와 부품으로 조립한 행동 벡터의 내적)은 OpenAI Five·Honor of Kings·ByteRL(Hearthstone)·ygo-agent의 "two-tower/pointer" 패턴을 가볍게 만든 판이다. 이런 결정(템플릿으로 찍어 낸 거대한 이산 행동, 집합 구조의 관측, 4인 불완전 정보)에 대해 분야가 합의한 설계에는 세 가지가 있다. 개체 위의 self-attention 몇 층, 동사에 조건화된 pointer식 대상 선택, 그리고 정책과 분리된(대개 더 큰) 가치망이다. 우리 엔티티 망에는 셋 다 없다. 그러나 문헌에서 분포 안의 구조 차이는 대개 0~수 %p에 그친다. 같은 지식 위에 실행 시 탐색을 더하면 +20~27%p가 나고, 학습법·최적화·상대 구성은 수 %p에서 십수 %p를 움직인다. 우리 측정도 같은 모양이다. 같은 학습법에서 MLP와 엔티티는 **+0.1%p [−4.7, +5.1]**로 비겼고, 엔티티를 두 배로 넓혀도 증류 일치율은 **95.0% 그대로**였다. 반면 학습률 하나가 **+7.9%p**를 만들었고, 탐색 좌석은 망 혼자 약 **55%**이던 승률을 **81.8%**로 올렸다. 따라서 다음 투자 순서는 망 구조 교체가 아니다. 첫째 탐색 좌석의 부품(사전 확률 닻, 후보 배분, 행동 우도로 가중한 세계), 둘째 증류와 학습 신호(학생이 만든 국면으로 증류, kickstarting, 분리·특권 가치), 셋째 엔티티 망의 알려진 약점에 대한 작은 표적 수정이다. 모두 Mac mini 한 대에서 몇 시간 단위로 판정할 수 있다.

## 비교 대상은 상태 인코딩 세 갈래, 행동 점수 네 갈래로 모인다

비슷한 게임 AI의 상태 인코딩은 세 갈래다. 첫째는 정체(identity)별 개수나 one-hot을 그대로 펼친 벡터다. PyTAG의 게임별 손 인코딩(Love Letter·Exploding Kittens의 카드 종류별 개수)([PyTAG 2024](https://arxiv.org/html/2405.18123v1)), DouZero의 4×15 카드 행렬([DouZero](https://ar5iv.labs.arxiv.org/html/2106.06135)), Suphx의 34칸 패 평면([Suphx](https://ar5iv.labs.arxiv.org/html/2003.13590)), Race for the Galaxy의 "카드마다 위치마다 입력 하나"([Temple Gates](https://www.templegatesgames.com/dominion-ai/))가 여기에 들고, 우리 MLP의 5,732칸 관측도 이 갈래다. 둘째는 카드마다 학습된 임베딩을 구역별로 모으는(pooling) 방식이다. Temple Gates의 Dominion은 카드 입력 수천 개를 **약 10차원의 학습된 특성**으로 압축해 처음 약 200장에서 나중 약 500장까지 같은 실력으로 다뤘다([Temple Gates](https://www.templegatesgames.com/dominion-ai/)). Gerigk & Engels는 16차원 카드 임베딩을 DeepSets식(카드별 MLP → 원소별 max → 집합 문맥)으로 더미마다 모았고([AIIDE 2023](https://ojs.aaai.org/index.php/AIIDE/article/view/27518)), ByteRL은 구역의 카드 임베딩을 평균했다([ByteRL HS](https://ar5iv.labs.arxiv.org/html/2303.05197)). 우리 엔티티 망의 장수 가중 합은 이 갈래에서 가장 단순한 판, 즉 pooling 전에 비선형이 없는 합이다. 셋째는 개체를 token으로 두고 self-attention을 쓰는 방식으로, 규모는 작은 쪽부터 큰 쪽까지 넓다. Catan PPO는 타일 19개 위에 attention 2블록을 두었고([Catan PPO](https://settlers-rl.github.io/)), ygo-agent는 카드 집합 위에 2층 transformer를([ygo-agent agent.py](https://raw.githubusercontent.com/sbl1996/ygo-agent/master/ygoai/rl/jax/agent.py)), Cardsformer는 4층·8 head를 썼다([Cardsformer](https://github.com/WannianXia/Cardsformer)). AlphaStar는 유닛 512개 위에 3층·2 head·128차원을([Perceiver IO](https://arxiv.org/abs/2107.14795)), Cicero는 지역 81 + 좌석 7 + 전역 1 token 위에 10층·224차원을 두었다([Cicero TR](https://noambrown.com/papers/22-Science-Diplomacy-TR.pdf)). 가장 큰 7 Wonders Duel의 ZeusAI는 12층·768차원·**약 9,200만 매개변수**다([ZeusAI](https://arxiv.org/html/2406.00741v1)).

행동 점수는 네 갈래다. (i) 고정 출력 행에 합법 mask를 씌우는 방식은 PyTAG(20~4,400행), Big 2(1,695행)([Big 2](https://ar5iv.labs.arxiv.org/html/1808.10442)), LOCM gym(145행)([Vieira SBGames 2022](https://homepages.dcc.ufmg.br/~ronaldo.vieira/assets/pdf/sbgames-2022.pdf)), MTG-Causal-RL(478행)([MTG-Causal-RL](https://arxiv.org/html/2605.06066v1)), Mortal의 dueling head([Mortal model.py](https://raw.githubusercontent.com/Equim-chan/Mortal/main/mortal/model.py))가 쓴다. (ii) 상태 query와 행동 임베딩의 내적, 곧 pointer를 쓰는 방식은 대형 에이전트의 표준이다. OpenAI Five는 주 행동을 LSTM 출력과 "쓸 수 있는 행동 ID" 임베딩의 내적으로, 대상을 유닛 임베딩 위 attention으로 고른다([OpenAI Five](https://arxiv.org/abs/1912.06680)). Honor of Kings는 대상을 Softmax(FC(h)·keys^T)로 고른다([HoK](https://arxiv.org/abs/1912.09729)). ByteRL(Hearthstone)은 한 수를 (출처, 대상) 두 걸음으로 나눠 각 걸음을 행동 임베딩과 LSTM 임베딩의 내적으로 매기고([ByteRL HS](https://arxiv.org/abs/2303.05197)), Ataraxos는 수를 key-query 곱으로 매긴다([Ataraxos](https://arxiv.org/html/2511.07312)). (iii) 행동을 입력으로 넣어 Q(s,a) 하나를 내는 방식은 DouZero(6×512 MLP, 27,472개 조합 중 합법만 평가), Cardsformer, Slay the Spire의 sts-rl-agent([sts-rl-agent](https://huggingface.co/Jialeiv/sts-rl-agent))가 쓴다. PerfectDou는 행동 특성을 상태 특성과 이어 MLP에 넣고 합법 행동만 softmax하는 중간형이다([PerfectDou](https://ar5iv.labs.arxiv.org/html/2203.16406)). (iv) autoregressive·분해 head는 AlphaStar(function → … → unit_tags → target_unit_tag, pointer network)([AlphaStar Unplugged](https://arxiv.org/abs/2308.03526)), Catan의 행동 종류 13개 + 조건부 head, Diplomacy의 단위별 LSTM decoder가 쓴다.

여기서 핵심은 **행마다 출력하는 head도 수학적으로는 내적**이라는 점이다. logit_a = w_a·h + b_a에서 w_a는 행동마다 자유로운 512차원 벡터이고, logit 행렬의 rank는 은닉 폭으로 묶인다([Softmax bottleneck](https://ar5iv.labs.arxiv.org/html/1711.03953)). 그러니 우리 두 망의 실제 차이는 표현력이 아니다. 행동 벡터를 자유 매개변수로 둘지, 공유 부품에서 계산해 드문 행동과 새 카드로 통계를 나눌지의 차이다.

| 시스템 (게임, 인원) | 상태 인코딩 | 행동 점수 | 학습 | 실행 시 탐색 |
|---|---|---|---|---|
| PyTAG (Sushi Go!·Love Letter 등, 2–4인) | 게임별 손 인코딩(종류별 개수·one-hot) | 평평한 카탈로그 20–4,400행 + mask | PPO, FC 2층, 100만 걸음 | 없음. TAG의 조정 안 한 MCTS에 0–13%만 이김 ([PyTAG 2024](https://arxiv.org/html/2405.18123v1)) |
| TAG 기본 에이전트 (40여 게임) | 순방향 모델 | 합법 행동 목록 | 손 휴리스틱(Catan만 ExIt 가치) | IS-MCTS, 기본 50 ms ([TAG 2025](https://arxiv.org/html/2503.02686v1)) |
| Catan PPO (4인) | 타일 token + attention 2블록, 카드 목록 attention·합 | 행동 종류 13 + 조건부 head | PPO, 결정 4.5억, 32코어 + 3090 한 달 | 루트 탐색: 자기 복제 셋 상대 47/100 ([Catan PPO](https://settlers-rl.github.io/)) |
| Dominion (Gerigk & Engels, 2–4인) | 카드 16차원 임베딩, 더미별 DeepSets | 집합 등변 선택지 점수 + 결정 종류 임베딩 | 이산 SAC, 매개변수 3.2만–11.7만 | 없음 ([AIIDE 2023](https://ojs.aaai.org/index.php/AIIDE/article/view/27518)) |
| ZeusAI (7 Wonders Duel, 2인) | 구성요소 token, transformer 12층·768 | AlphaZero 정책 head | self-play 42만 판 | MCTS 5k, 정상급 사람에게 68.4% ([ZeusAI](https://arxiv.org/html/2406.00741v1)) |
| ByteRL (Hearthstone, 2인) | 카드 임베딩 구역 평균 + LSTM 256 | (출처, 대상) 두 걸음, 행동 임베딩·상태 내적 | V-trace/UPGO → PPO, OSFP, V100 24장 | 없음 ([ByteRL HS](https://ar5iv.labs.arxiv.org/html/2303.05197)) |
| ygo-agent (Yu-Gi-Oh, 2인) | 카드 id/LLM 임베딩 × 상태 특성, transformer 2층 | 카드를 가리키는 행동 token, FiLM transformer → Dense(1) | 분산 RL, 4090 32장 × 5일 | 없음 ([ygo-agent](https://github.com/sbl1996/ygo-agent)) |
| LoCM 탐색 (Rubin 2026, 2인) | ByteRL의 카드 원자 | 평평한 카탈로그 | 행동 복제 MLP 250만·1,000만 | PIMC + 턴 전체 계획 beam, argmax 대비 +24.6%p ([LoCM](https://arxiv.org/html/2609.06816v1)) |
| DouZero (DouDizhu, 3인) | 4×15 카드 행렬 + LSTM | 행동을 입력으로 Q(s,a), 6×512 | Deep Monte Carlo, 30일 | 없음 ([DouZero](https://ar5iv.labs.arxiv.org/html/2106.06135)) |
| PerfectDou (3인) | 카드 행렬 평면 | 행동 특성 + 상태 → 합법 softmax(추상 621) | PPO + GAE, 완전 정보 critic | 없음 ([PerfectDou](https://ar5iv.labs.arxiv.org/html/2203.16406)) |
| Suphx·Mortal (마작, 4인) | 34칸 패 평면, CNN/ResNet | 결정 종류별 작은 고정 head + mask | SL → RL + GRP + oracle / dueling DQN | 없음 ([Suphx](https://ar5iv.labs.arxiv.org/html/2003.13590)) |
| Pluribus (포커, 6인) | 추상화 bucket | 베팅 1–14개 | MCCFR self-play, 12,400 코어시간 | 깊이 제한 탐색, leaf에서 연속 전략 4개 ([Pluribus](https://par.nsf.gov/servlets/purl/10119653)) |
| Ataraxos (Stratego, 2인) | 10×10 평면, transformer | key-query 수 점수 | 정규화 self-play, H100 16장 1주 | 학습된 믿음 표본 + rollout + MMD 한 걸음 ([Ataraxos](https://arxiv.org/html/2511.07312)) |
| DORA·Cicero (Diplomacy, 7인) | 지역·좌석·전역 token, transformer 10×224 | autoregressive LSTM 명령 decoder | RL(+ 사람 닻 piKL) | 표본 후보 위 균형 탐색 ([DORA](https://ar5iv.labs.arxiv.org/html/2110.02924)) |
| AlphaStar (StarCraft II) | 유닛 transformer 3층·2 head·128 | autoregressive + pointer network | 리그, 1.39억(정책 5,500만, 가치 8,400만) | 없음 ([TStarBot-X](https://arxiv.org/abs/2011.13729)) |
| OpenAI Five (Dota 2) | 집합별 Process Set(max-pool), LSTM 4096 | 주 행동 = LSTM·행동 ID 임베딩, 대상 = 유닛 attention | PPO, 1.59억 | 없음 ([OpenAI Five](https://arxiv.org/abs/1912.06680)) |
| Honor of Kings (MOBA) | 유닛 종류별 max-pool, LSTM 1024 | 대상 attention + 다중 레이블 head | dual-clip PPO | 없음 ([HoK](https://arxiv.org/abs/1912.09729)) |
| **우리 MLP** | 5,732칸 개수 벡터, log1p | 카탈로그 행마다 512차원 행 + mask | REINFORCE + 가치 기준선 | 후보 5 × 세계 8, 라운드 끝까지 rollout |
| **우리 엔티티** | 개체 405개(64차원) 구역 합 + 좌석·보드·개인 인코더 | Linear(h)·조립 행동 벡터 + 행동별 보정 | 같음(학습률 1e-5) | 같음(결정당 약 1.6배 느림) |

여러 걸음으로 된 턴은 예외 없이 단일 결정의 사슬로 쪼개고, 결정 종류를 망에 알려 준다(Dominion의 결정 종류 임베딩, ByteRL의 결정 종류 입력, TAG의 여러 행동 턴). 우리 엔진은 Agent 턴을 카드+칸 → 효과와 대상이라는 별개 걸음으로 이미 나눈다. AlphaStar·HoK가 망 안에서 하는 autoregressive 분해를 환경이 대신하는 셈이다. 선생 분포를 걸음마다 탐욕으로 두어도 **57.5%**(선생 56.8%)였으니, 이 분해로 잃는 것은 없다.

불완전 정보의 처리는 세 계열로 갈린다. 포커의 CFR/공개 믿음 상태(PBS) 계열은 모든 정보 집합의 범위를 망 입력으로 넣는다(ReBeL 입력 2,660칸, MLP 6×1,536). 그런데 이 입력은 공개 상태당 정보 집합 수에 선형으로 커지고, 수렴 보장은 2인 영합 게임에만 있다([ReBeL](https://ar5iv.labs.arxiv.org/html/2007.13544)). 숨은 덱·손·책략이 있는 4인 게임으로는 옮겨지지 않는다. 표본 세계 탐색 계열(Bridge·Skat의 PIMC, DeltaDou, SPARTA, Ataraxos)이 우리 탐색 좌석의 직계 조상이다. 탐색 없는 RL 계열(DouZero, 온라인의 Suphx, DeepNash, Mortal)은 망 하나로 버틴다. 3인 이상에서는 어떤 시스템도 균형 보장이 없어, Pluribus처럼 사람 상대 실측으로 정당화한다([Pluribus](https://par.nsf.gov/servlets/purl/10119653)). 7인 Diplomacy에서는 처음부터 한 self-play가 시드마다 다른 관습으로 수렴해, 두 시드가 서로를 **3~8%**만 이겼다([DORA](https://ar5iv.labs.arxiv.org/html/2110.02924)). 판의 절반을 앱 AI 상대로 두는 우리 설정은 Diplodocus의 사람 닻과 같은 역할을 한다([Diplodocus](https://ar5iv.labs.arxiv.org/html/2210.05492)).

이 문헌들을 합치면 "이런 결정의 최선"은 다음 모양이다. 개체마다 종류별로 공유한 인코더(내용 특성 + id 임베딩)를 두고, 그 위에 self-attention 1~3층(64~256차원, 2~4 head)이나 최소한 비선형 pooling을 쓴다. 좌석은 token으로 둔다. 행동은 작은 동사 head에 대상 pointer를 붙이되, 대상 key를 고른 동사로 조건화한다(OpenAI Five는 동사 임베딩의 sigmoid mask를 유닛 key에 곱한다). 합법 mask를 쓰고, 정책과 분리된 가치망을 두며, 가치망은 학습 때 특권 정보를 보기도 한다. 우리 엔티티 망은 이 그림에서 attention, 동사 조건 대상 선택, 분리 가치를 뺀 판이다. 다만 이 "최선"은 대부분 대규모 시스템에서 나왔다. 통제된 분포 안 비교에서 남긴 이득은 다음 절에서 보듯 작다.

## 탐색은 +20%p대, 학습법은 수 %p, 구조는 0에 가깝다

| 지렛대 | 문헌의 효과 크기 | 우리 측정 |
|---|---|---|
| 실행 시 탐색 | LoCM: 같은 망 argmax 26.8% → 탐색 51.35%(+24.6%p). Catan: 루트 탐색 47%(기준 25%). DeltaDou: 탐색 59% 대 탐욕 정책 49%(XDou 상대). Hanabi SPARTA: 24.08 → 24.61점 | 망 혼자 약 55% → 탐색 좌석 81.8%(1 대 앱 AI 어려움 3, +27%p) |
| 학습법·최적화·상대 | Engstrom: 코드 수준 최적화의 효과가 알고리즘 효과보다 큼(Walker2d 557 대 242). Big 2: entropy 0.05로 +6.4%p, PPO가 MC-Q보다 +4.6%p. Dominion: 훈련에 없던 전략 상대 16.5% → 넣으면 80.5%. ByteRL: γ 1.0으로 +7%, V-trace 개선 +15.1% | 학습률 1e-4 → 1e-5가 '구조 차이' +7.9%p를 모두 설명. 학습법(Y 증류 + Y 가치 목표 + REINFORCE 1e-5)으로 Y 대비 +5.7%p. PPO 1회 붕괴(휴리스틱 상대 76.5% → 43%) |
| 구조, 분포 안 | MTG 카드 표현 넷: 67.8–68.1%로 같음. AlphaStar 개체 인코더: transformer와 Perceiver IO 모두 0.87. LoCM: 매개변수를 키워도 뚜렷한 이득 없음, 데이터 4배는 +8%p. Hide-and-Seek: attention이 표본 9% 절약, 벽시계 10% 느림 | 같은 학습법에서 MLP 대 엔티티 +0.1%p [−4.7, +5.1]. 엔티티 폭 2배에도 증류 일치 95.0% = 95.0% |
| 구조, 정보·구조를 더할 때 | DORA: transformer(930만) 1041 대 GraphConv(4,680만) 898 Elo, 정책·가치 분리 +62 Elo. KataGo: 전역 pooling 1.60배, 보조 목표 1.65배. HoK: 대상 attention이 기준 대비 75%. Box-World: 처음 본 조합 97% 대 13% | P2: 엔티티 행동 점수가 드문 국면에서 약 2%p 잃음 → 행동별 고유 벡터(own_actions)로 메움. 가치 목표를 선생 가치로 바꾸자 일치 95.0% → 96.5% |

표의 출처는 이렇다. 탐색은 [LoCM](https://arxiv.org/html/2609.06816v1), [Catan PPO](https://settlers-rl.github.io/), [DeltaDou](https://www.ijcai.org/proceedings/2019/0176.pdf), [SPARTA](https://ar5iv.labs.arxiv.org/html/1912.02318)다. 학습법은 [Engstrom](https://ar5iv.labs.arxiv.org/html/2005.12729), [Big 2 (2026)](https://arxiv.org/html/2605.28863), [AIIDE 2023](https://ojs.aaai.org/index.php/AIIDE/article/view/27518), [ByteRL HS](https://ar5iv.labs.arxiv.org/html/2303.05197)다. 구조는 [MTG 카드 표현](https://arxiv.org/html/2407.05879v1), [Perceiver IO](https://arxiv.org/abs/2107.14795), [Hide-and-Seek](https://arxiv.org/abs/1909.07528), [DORA](https://ar5iv.labs.arxiv.org/html/2110.02924), [KataGo](https://ar5iv.labs.arxiv.org/html/1902.10565), [HoK](https://arxiv.org/abs/1912.09729), [Relational RL](https://arxiv.org/abs/1806.01830)이다. 우리 측정은 `docs/entity-network-plan.md`의 P2·P3·G1b와 `docs/worklog/2026-10.md`에 있다.

탐색의 몫은 게임 종류를 가리지 않고 크다. 4인 게임에서 기준선 25%를 47%로 올린 Catan의 루트 탐색, 같은 MLP의 argmax를 26.8%에서 51.35%로 올린 LoCM의 PIMC는 우리 +27%p와 같은 자릿수다. PyTAG에서는 100만 걸음 학습한 PPO 망이 조정도 안 한 TAG의 MCTS에 Sushi Go! 4인에서 5%, Love Letter 4인에서 1%만 이겼다([PyTAG 2024](https://arxiv.org/html/2405.18123v1)). Expert Iteration에서는 망이 이끄는 MCTS가 맨 MCTS를 97% 이겼고, 맨 MCTS의 반복을 두 배로 늘린 효과는 56%에 그쳤다([ExIt](https://ar5iv.labs.arxiv.org/html/1705.08439)). 이 격차를 망 안으로 흡수하는 비용도 알려져 있다. Hex에서 학습 연산 10배는 실행 시 탐색 연산 약 15배와 맞먹었다([Jones](https://ar5iv.labs.arxiv.org/html/2104.03113)). 탐색 좌석이 주는 +27%p를 망만으로 내려면 Mac mini 한 대의 몇 배가 넘는 학습 연산이 든다는 뜻이고, 그러니 플레이에서는 탐색 좌석을 계속 엔진으로 써야 한다.

학습법과 최적화의 몫은 구조보다 크다. Engstrom 등은 PPO와 TRPO의 차이 대부분이 알고리즘이 아니라 보상 크기 조정·학습률 감쇠·초기화 같은 코드 수준 선택에서 나온다는 것을 보였다. Andrychowicz 등은 25만 개 넘는 에이전트를 돌린 끝에 γ를 가장 중요한 하이퍼파라미터의 하나로 꼽고, 학습률은 반드시 조정하라고 했다([Andrychowicz](https://ar5iv.labs.arxiv.org/html/2006.05990)). 우리 기록이 이를 그대로 되풀이한다. P3에서 엔티티가 MLP를 이긴 +7.9%p는 MLP에게도 지나쳤던 학습률 1e-4 탓이었고, 학습률을 1e-5로 맞추자 차이가 사라졌다. PPO가 한 번 무너진 것(clip 0.2, 3 epoch)도 다중 에이전트 문헌과 맞는다. MAPPO는 비정상성 때문에 데이터 재사용이 해롭다며 clip을 0.2 아래로 두라고 권했다([MAPPO](https://ar5iv.labs.arxiv.org/html/2103.01955)). Moalla 등은 epoch을 늘리면 표현 rank 붕괴가 빨라지고, 그러면 clipping이 학습을 막지 못한다고 보였다([Moalla](https://arxiv.org/html/2405.00662v3)). "여러 번 훑기가 결정적"이라는 Andrychowicz의 결론은 정상(stationary) 단일 에이전트 MuJoCo의 것이라, 4인 self-play에 그대로 옮기면 안 된다.

구조가 크게 효과를 낸 사례에는 공통점이 있다. 옛 인코더가 쓸 수 없던 정보나 구조를 새로 주었거나, 분포 밖 일반화를 시험했다. DORA는 손으로 엮은 인접 그래프 대신 transformer를 써서 매개변수 5분의 1로 +143 Elo를 얻었다. KataGo는 전역 pooling과 보조 목표로 각각 1.6배 안팎의 효율을 얻었다. Box-World의 relational agent는 처음 보는 열쇠·자물쇠 쌍에서 97% 대 13%였다. 카드 게임의 유일한 통제 비교인 MTG 드래프트에서 카드 표현의 선택은 학습에 나온 카드에서 정확도를 거의 바꾸지 않았다(67.8~68.1%). 그러나 처음 보는 세트에서는 23.8%와 42.9%를 갈랐다([MTG 카드 표현](https://arxiv.org/html/2407.05879v1)). 반대로 단순히 키우는 것은 모델 없는 RL에서 자주 해롭다. Rainbow의 끝층을 8배 넓히자 성능이 약 40% 떨어졌다([Soft MoE](https://arxiv.org/html/2402.08609)). 규모가 이득이 되려면 layer norm·residual·재초기화 같은 안정 장치가 함께 있어야 했다([BBF](https://ar5iv.labs.arxiv.org/html/2305.19452), [SimBa](https://arxiv.org/abs/2410.09754)). 카드 이름이 고정된 우리 카탈로그는 분포 이동이 작은 쪽이다. 그러니 구조 교체로 기대할 수 있는 몫은 작고, 그 작은 몫도 확장 카드가 들어올 때의 일반화와 유지보수 쪽에 있다.

## 두 망의 자리와 실제 약점: 문제는 행동 head보다 신호에 있다

### MLP: 기본값은 문헌과 겹치고, 약점은 공유가 없다는 데 있다

512×512 몸통은 기록된 이유 없이 2026-09-06에 정한 기본값이지만, 문헌의 기본값과 정확히 겹친다. Hex 9×9의 완전한 수에는 **512 뉴런 두 층(약 50만 매개변수)**이면 충분했다([Jones](https://ar5iv.labs.arxiv.org/html/2104.03113)). MAPPO는 Hanabi에 2×512를, DouZero는 6×512를, Big 2는 512 공유층을 썼다. 폭이 병목이라는 증거는 약하다. AlphaStar Unplugged에서 폭을 반으로 줄이자 83%가 76%로 떨어졌지만, 이것은 사람 데이터 행동 복제의 결과다([AlphaStar Unplugged](https://arxiv.org/abs/2308.03526)). 증류 충실도는 학생을 넓혀도 거의 변하지 않는다([Stanton](https://ar5iv.labs.arxiv.org/html/2106.05945)).

진짜 약점은 세 가지다. 첫째, 행마다 출력이 v147 파일 2,150만 매개변수의 **87%(36,379행)**를 차지하면서 서로 아무것도 나누지 않는다. 행은 그 행동이 합법이고 경쟁할 때만 움직이므로 드문 카드 행동은 느리게 배운다. 또 codec이 바뀔 때마다 행을 옮기는 수술(행 이관, `older:` 어댑터)이 필요하다. OpenAI Five가 10개월 동안 20번 넘게 한 바로 그 수술인데, 그들은 환경이 굳은 뒤에는 처음부터 다시 학습하는 편이 연산 20%로 더 강했다고 보고했다([OpenAI Five](https://arxiv.org/abs/1912.06680)). 둘째, 평평한 개수 벡터는 손실 없는 다중집합 표현이지만 카드 사이에 통계를 나누지 못한다. 프로젝트의 망 진단에서 임페리움 열을 바꿔 넣어도 정책은 **0.3%**만 움직였다(`docs/entity-network-plan.md`). 엔티티 E2v도 0.3%였으니, 이것은 MLP 입력 형식만의 문제가 아니다. 학습 신호가 그 열을 읽을 이유를 주지 못한다는 증상으로 읽는 편이 맞다(추론). 셋째, 정책과 가치가 몸통 하나를 나눈다(아래 공통 약점).

### 엔티티 망: 올바른 계열이지만 조립식 행동 벡터의 한계가 실재한다

엔티티 망은 OpenAI Five·HoK·ByteRL과 같은 "집합 pooling + two-tower 점수" 계열이다. 행동을 공유 부품에서 계산하므로 드문 행동과 새 카드에 통계를 나눌 수 있다. 연구 노트 하나는 이 망의 행동 벡터를 부품 벡터의 순수한 합으로 보고 "카드 X가 칸 Y에서만 좋다"를 나타낼 수 없다고 했는데, 이는 실제 구조와 다르다. 합 뒤에 ReLU → Linear(128→128)이 한 번 있으므로 순수 가법은 아니다. 부품 사이 상호작용이 비선형 한 층으로 제한될 뿐이고, 그 밖에 행동별 보정값과 증류용 행동별 고유 벡터(own_actions)가 있다. 이 제한이 어디서 드러나는지는 P2가 이미 쟀다. MLP 선생 Y를 흉내 낼 때 엔티티 상태 요약 + 행마다 출력(H1)은 95.7%, MLP 상태 요약 + 엔티티 행동 점수(H2)는 94.8%였다. **행동 점수 쪽이 약 2%p(드문 국면 차이의 거의 전부), 상태 요약 쪽이 약 1%p**를 잃었고, own_actions가 드문 국면의 차이를 메웠다(`docs/entity-network-plan.md`). 조립식 벡터의 한계는 실재하지만 작고, 지금은 행동별 자유 벡터로 덮고 있다.

남은 약점은 다섯이다. 첫째, 구역 합이 원래 개수 열을 대체한다. 구역 표현 Σ c_e·v_e는 개수 벡터를 64차원으로 선형 사영한 것이다. 구역 어휘(카드 정체만 100종 이상)가 64보다 크므로 이 사영은 단사일 수 없다. Wagstaff 등은 연속 사상으로 합 분해를 정확히 하려면 잠재 폭이 최대 원소 수 이상이어야 함을 보였다([Wagstaff](https://arxiv.org/abs/1901.09006)). 덱 구성처럼 정확한 개수가 중요한 정보가 사라질 수 있고, 이 손실이 카드 공유의 이점을 상쇄할 수 있다(추론, 측정 안 됨). DeepSets 원형과 Gerigk & Engels는 pooling 전에 원소별 비선형을 둔다. 둘째, 개체 사이 상호작용이 없다. 카드 조합이나 칸 경쟁 같은 관계는 합을 받은 MLP가 추론해야 한다. AlphaStar·Hide-and-Seek·DORA·Cicero·ygo-agent는 모두 개체 위 self-attention을 두지만, 분포 안 이득은 작다. Hide-and-Seek에서 attention은 비슷한 매개변수의 pooling보다 표본을 9% 덜 썼지만 벽시계로는 10% 느렸다([Hide-and-Seek](https://arxiv.org/abs/1909.07528)).

셋째, 행동 벡터가 상태와 무관하다. 상태는 query 쪽 Linear(h→128)로만 들어오므로, 같은 걸음의 합법 행동끼리 순위가 상태에 따라 바뀌려면 그 모든 차이를 128차원 벡터 하나가 실어야 한다. AGILE은 행동의 가치가 지금 가능한 다른 행동에 달려 있음을 보이고, 합법 행동 집합 위 attention으로 이를 다뤘다([AGILE](https://www.iclr.cc/virtual/2022/poster/6594)). ygo-agent는 상태로 FiLM 조건화한 transformer 한 층을 행동 token 위에 둔다. 반대로 DRRN과 Rendle은 내적이 강한 기본값이고, MLP로 결합을 대신하면 오히려 나빠진다고 경고한다([DRRN](https://ar5iv.labs.arxiv.org/html/1511.04636), [Rendle](https://arxiv.org/abs/2005.09683)). 고친다면 내적을 지우지 말고 그 위에 얹어야 한다. 넷째, 부품을 수천 행동이 함께 쓰므로 한 걸음이 많은 logit을 한꺼번에 움직인다. 그래서 학습률 1e-4에서 약 90 iteration 만에 무너졌고 1e-5로 내려야 했다. OpenAI Five가 드문 순간이동 행동에 별도 head를 준 이유("학습 신호가 묻힌다")와 같은, 공유의 대가다. 다섯째, 탐색 좌석에서 결정당 약 1.6배 느려(엔티티 172~200 ms, MLP 101~132 ms) 같은 시간에 세계와 후보를 덜 쓴다.

### 공통 약점 1: 가치 head는 외우고, 고치면 탐색이 나빠질 수 있다

두 망 모두 가치 head는 정책과 몸통을 나누는 Linear(512→1) 하나다. P2에서 판 결과를 목표로 한 가치 head는 판을 외웠다. 처음 보는 판의 오차가 0.46으로, 늘 0이라고 답할 때의 0.33보다 나빴다. 선생의 가치를 목표로 바꾸자 정책 일치까지 좋아졌는데, 외우기가 공유 몸통을 끌어당기고 있었다는 뜻이다. 문헌도 같은 방향이다. Andrychowicz는 다섯 환경 중 넷에서 정책·가치 분리가 나았다며 "넓고 분리된 가치망"을 권했다. DORA는 분리로 +62 Elo를 얻었고, AlphaStar는 가치망(8,400만)이 정책망(5,500만)보다 컸다. ExIt는 가치 학습에 독립 표본이 10^5개 넘게 있어야 과적합을 피한다고 했다([ExIt](https://ar5iv.labs.arxiv.org/html/1705.08439)). 다만 가치를 고칠 때 함정이 있다. ExIt v1에서 가치 head만 판 결과에 다시 맞추자(설명 분산 0.143 → 0.175), 탐색 좌석의 평균 순위가 오히려 **+0.13 나빠졌다**(`docs/evaluation/m10-2026-09-22.md` 15절). 판 결과를 잘 맞히는 것과 형제 국면을 잘 가르는 것은 다른 능력이다. Neumann & Gros도 시험 손실이 실력의 나쁜 예측자라고 했다([Neumann & Gros](https://ar5iv.labs.arxiv.org/html/2210.00849)). 가치 변경은 반드시 탐색 좌석으로 판정해야 한다.

### 공통 약점 2: 증류 손실은 문헌의 실패 양식과 맞는다

v150 사슬의 증류 자료는 선생이 학습 좌석을 샘플링으로 두며 남긴 국면이다. 즉 선생이 만든 분포다(`docs/worklog/2026-10.md` 2026-10-21). Czarnecki 등은 학생이 만든 국면으로 증류하면 선생 국면으로 할 때보다 **약 3배 적은 걸음**으로 선생 실력을 회복하고, 선생 국면만 보면 학생이 실제로 방문할 국면을 못 본다고 했다([Czarnecki](https://ar5iv.labs.arxiv.org/html/1902.02186)). Stanton 등은 용량이 충분해도 일치가 85~90%에서 멈추고, 그 원인이 최적화라고 했다. 학생을 넓혀도 거의 변하지 않고, 오래 학습하면 약 2% 오른다([Stanton](https://ar5iv.labs.arxiv.org/html/2106.05945)). 우리 12 epoch cosine 학생이 47.5%에서 52.0%로 오른 것, 폭 2배가 일치를 바꾸지 못한 것과 같은 모양이다. 손실이 선생 1순위 확률 0.6 미만인 결정(32%)에 몰린 것은, 분포가 평평한 곳에서는 작은 logit 오차가 argmax를 뒤집기 때문이다. 그런데 평평한 정책이 작은 가치 차이를 뜻하지는 않으므로 그곳의 오답이 실제로 비쌀 수 있다(추론). 증류 뒤 순수 REINFORCE 800회는 51.5%로 선생에 못 미쳤다. 그런데 Schmitt 등의 kickstarting은 RL 손실에 선생 KL을 더하고 그 가중치를 0으로 줄였을 때 학생이 선생을 **43.4%** 넘었고, 가중치를 고정하면 선생 근처에서 멈췄다([Kickstarting](https://ar5iv.labs.arxiv.org/html/1803.03835)).

### 탐색 좌석: strategy fusion은 없고, 남은 오차는 세 가지다

탐색 좌석은 구조적으로 PIMC에 학습된 leaf를 붙인 것이지만, 고전 PIMC와 중요한 차이가 있다. 고전 PIMC는 세계마다 완전 정보로 푸는 탓에, 세계마다 다른 전략을 쓸 수 있다고 착각하는 strategy fusion이 생긴다([Long et al.](https://cdn.aaai.org/ojs/7562/7562-13-11092-1-2-20201228.pdf)). 우리 rollout에서는 망이 각 좌석 자신의 관측만으로 두므로 나중 수가 표본 세계에 맞춰지지 않고, 루트 선택도 모든 세계에 하나다. 그러니 rollout 지평 안의 strategy fusion은 사실상 없다. 노트 하나가 "자기 나중 선택의 fusion은 못 고친다"고 했지만 이 설계에는 맞지 않는다. 이 탐색은 SPARTA·Ataraxos처럼 망 정책 위의 "한 걸음 정책 개선"이며, SPARTA의 보장도 바로 이 형태에서 나온다([SPARTA](https://ar5iv.labs.arxiv.org/html/1912.02318)).

남는 오차는 셋이다. 하나는 세계를 상대의 지난 행동과 무관하게 뽑는 것(믿음 오차, non-locality)이다. 다른 하나는 앱 AI 상대도 망으로 모델링하는 것이다. 마지막은 세계 8개 평균의 argmax가 잡음을 고르는 것인데, ExIt 라벨 통계가 이를 보여 준다. 탐색이 망의 1순위를 뒤집은 결정은 44%였지만, 세계를 두 반쪽으로 나누면 선택이 갈린 결정이 25%였고, 차이가 0.005 미만인 결정이 41%였다(`docs/evaluation/m10-2026-09-22.md` 15절). 또 망의 실력 향상이 탐색 좌석으로 잘 넘어오지 않았다. M은 망만 두면 8081보다 13%p 강했지만, 탐색을 씌우자 둘이 같았다(`docs/evaluation/exit-v2-2026-10-08.md` 1절). 탐색의 상한이 정책보다 세계 표본, leaf 가치, 후보 선택 같은 탐색 자체의 부품에 있다는 신호다(추론).

## 추천 순위: 탐색 부품, 증류와 가치, 그다음에 구조

| 순위 | 바꿀 것 | 기대 효과(추정) | 우리 기계 비용 | 근거 |
|---|---|---|---|---|
| 1 | 탐색 좌석: 망 사전 확률 닻 또는 뒤집기 문턱 | 승률 0–3%p, 잡음 뒤집기 감소 | 코드 수십 줄, 측정 400판 한 칸에 1–2시간 | SPARTA(0.05 문턱, 청사진보다 나빠지지 않음), Ataraxos(닻을 빼면 망 혼자보다 나빠짐), ExIt 라벨 잡음 |
| 2 | 탐색 좌석: Gumbel-Top-k로 후보를 뽑고, rollout 40개를 sequential halving으로 배분 | 수 %p | 코드 하루, 측정은 1과 같음 | Gumbel AlphaZero, DORA(후보 생성 방식 +67 Elo) |
| 3 | 탐색 좌석: 상대의 이번 라운드 행동 우도로 세계 가중(policy-based inference) | 2–5%p | 1–2일, 결정당 시간 소폭 증가 | Kermit PI(+2.32 TP/G), DeltaDou(추론 +4.5%p), Ataraxos(균일 믿음은 나쁨) |
| 4 | 증류: 학생이 만든 국면에 어댑터 선생 라벨(DAgger), 12 epoch cosine, 이어 kickstarting | 격차 −9%p → −2%p 안쪽 | 자료 80 iteration 17분, 학생 몇 시간, RL 800회 3.6시간 | Czarnecki, Stanton, Kickstarting, 우리 cosine +4.5%p |
| 5 | 가치: 분리된 가치 몸통, 학습용 기준선을 완전 정보 critic으로 | RL 속도 향상, leaf 개선 가능 | 분리는 작음, 숨은 정보 입력 경로는 중간 | Andrychowicz, DORA, PerfectDou, Hide-and-Seek, MAPPO |
| 6 | 엔티티 표적 수정: 구역 개수 열 복원(또는 pooling 전 비선형), 상태 조건 행동 점수(합법 행동 위 attention 한 층이나 동사 gating) | 분포 안 0–2%p, 새 카드 일반화 향상 | 매개변수 소폭, 1.5배 예산 안 | Wagstaff, AGILE, OpenAI Five 행동별 key mask, P2 분해 |
| 7 | 엔티티 개체 self-attention 1–2층(64–128차원, 2–4 head) | 작음, 분야 표준에 다가감 | 결정당 시간 증가, 예산 확인 필요 | AlphaStar, Hide-and-Seek, DORA, Cicero |
| 보류 | PPO 재시도, MLP 폭 확대, LSTM, CFR/PBS, 대형 transformer | — | — | MAPPO·Moalla, Rainbow 8배 −40%, AlphaStar Unplugged(LSTM 70% 대 무기억 84%), ReBeL 입력 폭발 |

탐색 부품을 맨 위에 둔 이유는 세 가지다. 효과의 자릿수가 가장 크고, 학습이 필요 없으며, 우리 측정이 탐색의 상한이 탐색 쪽에 있다고 가리키기 때문이다.

첫째, 사전 닻은 가장 싸다. 세계 8개 평균의 차이가 0.005 미만인 결정이 41%나 되는 상황에서, 망 1순위를 뚜렷한 차이로만 뒤집게 하면 잡음으로 생긴 뒤집기를 걸러 낸다. SPARTA는 0.05 넘게 좋을 때만 청사진에서 벗어나고, rollout 오차 항을 빼면 청사진보다 나빠지지 않음을 보였다. Ataraxos에서는 망 사전 확률에 대한 reverse-KL 닻을 빼자 탐색이 망 혼자보다 못해졌다([Ataraxos](https://arxiv.org/html/2511.07312)).

둘째, Gumbel 루트는 같은 40 rollout을 더 잘 쓰는 방법이다. 후보를 상위 5개로 고정하지 않고 Gumbel-Top-k로 뽑은 뒤 sequential halving으로 유망한 후보에 rollout을 몰아준다. Gumbel AlphaZero는 시뮬레이션이 2개뿐일 때도 정책 개선을 보장했다([Gumbel](https://openreview.net/forum?id=bERaNdoegnO)). DORA는 후보를 지역 수정으로 생성하자 균일 생성보다 +67 Elo를 얻었다.

셋째, 믿음 가중은 위의 오차 셋 중 첫째를 겨냥한다. Skat의 Kermit은 상대 모형의 행동 확률로 표본 세계에 가중치를 주어 suit 게임에서 +2.32 TP/G를 얻었다([Kermit PI](https://ar5iv.labs.arxiv.org/html/1905.10911)). DeltaDou에서는 추론이 같은 시스템끼리 맞붙었을 때 승률 54.5%(+4.5%p)를 만들었다([DeltaDou](https://www.ijcai.org/proceedings/2019/0176.pdf)). 우리 망은 이미 상대 좌석의 정책을 낼 수 있으므로, 이번 라운드에 상대가 실제로 둔 수의 우도로 세계 32개를 가중해 8개를 다시 뽑는 것은 새 모델 없이 할 수 있다. 참고로 LoCM에서 세계 수의 이득은 약 32개에서 포화했다([LoCM](https://arxiv.org/html/2609.06816v1)). 우리 8개가 부족한지는 아래 E2로 직접 잴 수 있다.

증류와 가치를 그다음에 둔 이유도 분명하다. 어댑터가 옛 망을 v150에서 실력 그대로(같은 시드 1,000판 중 996판이 순위까지 같음) 두므로, 플레이 강도는 지금 잃을 것이 없다. 증류 계보가 필요한 이유는 장기적이다. 어댑터가 답하지 못하는 결정(옛 엔진 고정 답 4.8%, 휴리스틱 0.5%)과 앞으로의 규칙·카드 변경이 그것이다. 그러니 이 계보는 선생과의 격차를 닫는 처방이 생긴 뒤에 다시 돌리는 것이 맞다. 그 처방은 문헌에 이미 있다. 학생 국면으로 증류(DAgger), 선생의 전체 분포와 가치를 목표로(이미 95.0% → 96.5%로 확인), 그리고 순수 RL 대신 kickstarting이다.

완전 정보 critic은 REINFORCE에서 특히 깔끔하다. 행동에 의존하지 않는 기준선은 숨은 상태에 의존해도 기울기를 치우치게 하지 않으므로, 분산만 줄인다. PerfectDou에서 완전 정보 critic의 효과는 DouZero 상대 0.486 → 0.524로 작지만 실재했다([PerfectDou](https://ar5iv.labs.arxiv.org/html/2203.16406)). Hide-and-Seek에서는 가린 가치함수로는 같은 예산 안에 3단계를 넘지 못했다([Hide-and-Seek](https://arxiv.org/abs/1909.07528)).

구조 수정을 뒤에 둔 것은 그 가치를 부정해서가 아니다. 기대 몫이 작고, 그 몫이 강도보다 확장 카드 일반화와 유지보수에서 나오기 때문이다. 확장(새 카드·새 판)을 들이는 것이 목표가 되면 순서가 바뀐다. 그때는 내용 특성으로 새 카드를 처음부터 다시 학습하지 않고 받는 엔티티 계보의 장점이 1순위가 된다. Temple Gates가 카드 200장에서 500장으로 넘어갈 때 쓴 것도 이 성질이다.

## 싼 실험 여덟 개와 통과 규칙

| 실험 | 설정 | 비용(추정) | 통과 | 실패면 |
|---|---|---|---|---|
| E1 사전 닻 | 지금 좌석 대 "평균 차가 δ = 0.01을 넘을 때만 망 1순위를 뒤집기"(또는 평균 + λ·log π, λ ∈ {0.01, 0.03}). 같은 시드 400판, 1 대 앱 AI 어려움 3과 1 대 플레이 망 3 | 칸당 1–2시간 | 승률 차 하한 > 0, 또는 승률 차 > −2%p이면서 순위·점수 차가 확정 개선 | 닻 없이 유지 |
| E2 세계 수 곡선 | 후보 5 × 세계 16 대 5 × 8 | 16 세계 칸 2–4시간 | E1과 같은 규칙 | 속도 작업(E8의 폭 256) 우선순위를 내림 |
| E3 예산 배분 | Gumbel-Top-k 후보 8개 + sequential halving, rollout 총 40 | 칸당 1–2시간 | E1과 같은 규칙 | 상위 5 고정 유지 |
| E4 믿음 가중 세계 | 세계 32개를 뽑아 상대의 이번 라운드 행동 우도로 가중, 8개 재표본. 먼저 오프라인으로, 실제 숨은 손의 로그 확률이 균일 표본보다 오르는지 확인 | 오프라인 1시간 미만 + 400판 | 오프라인 로그 확률 상승, 그리고 E1 규칙 | 균일 표본 유지 |
| E5 DAgger 증류 | 학생이 둔 판의 국면에 어댑터 선생 분포·가치, 2회 반복, 12 epoch cosine | 자료 회당 20분 안팎, 학생 몇 시간 | 단독 400판에서 선생과의 차가 −2%p 이내, 확률 0.6 미만 결정의 불일치 21% → 15% 미만 | 원인은 자료 분포가 아님 → E6으로 |
| E6 kickstarting | 가장 나은 학생에서 REINFORCE + β·KL(선생‖학생), β를 400회에 걸쳐 1 → 0, 모두 800회 | 3.6시간 + 2:2 1,400판 | 선생 대비 승률 점추정 ≥ 0, 하한 > −3%p(B-800은 −7.0 [−12.1, −1.7]) | 증류 계보 보류, 어댑터 유지 |
| E7 분리 가치·특권 critic | 같은 출발점에서 300회씩: (a) 지금, (b) 분리 가치 MLP, (c) (b) + 숨은 손·덱 입력 critic | 칸당 약 1.4시간 + 2:2 1,400판 | 하한 > 0, 또는 같은 강도를 3분의 2 iteration에 도달 | 공유 몸통 유지 |
| E8 구조 탐침(증류 일치) | 같은 증류 자료로 (a) 구역 개수 열 복원, (b) 합법 행동 위 attention 한 층, (c) MLP 폭 256·1024 | 학생 하나에 몇 시간 | (a)·(b): 처음 보는 판에서 확률 0.6 미만 결정의 일치 +1%p 이상. (c): 256이 512와 같으면 탐색 속도 이득으로 채택 | 해당 변경을 버림 |

판정할 때 조심할 점이 둘 있다. 첫째는 천장 효과다. 81.8%에서 400판의 표준오차는 약 1.9%p라, 짝지은 차이의 신뢰구간이 ±5%p 안팎으로 넓다. P4에서도 승률 차 +4.0%p는 잡음 안이었고, 순위와 점수 차만 확정됐다. 그러니 탐색 실험은 앱 AI 어려움 셋뿐 아니라 플레이 망 셋을 상대로도 재야 한다. ExIt v1에서 탐색 좌석은 망 셋 상대로 57~62%였으므로 여유가 더 크다. 순위·점수 차도 함께 판정에 넣어야 한다. 둘째, 증류 일치율은 실력의 대리 지표로 약하다. E8의 통과는 다음 단계로 갈 자격일 뿐이고, 채택은 2:2 대국과 탐색 좌석으로 정해야 한다. ExIt v1이 held-out 일치 관문(G0)은 통과하고도 대국(G1)에서 기각된 전례가 있다.

## 증거가 비어 있는 곳

아래 질문들에는 우리 같은 게임에 대한 증거가 없고, 여기서 내린 판단은 그만큼 추론에 기댄다. 가장 큰 빈칸은 구조 비교다. 다인원 euro·덱빌딩 게임에서 같은 연산으로 MLP와 엔티티/attention 망을 통제 비교한 공개 연구는 없어서, 우리의 **+0.1%p 비김**이 이 분야의 드문 자료점이다. 행마다 출력하는 head와 two-tower 행동 head를 고정된 큰 카탈로그에서 policy gradient로 직접 비교한 연구도 없다. 조립식 행동 벡터의 상호작용 한계에 대한 서술은 수학적 추론이고, 실측은 우리 P2 분해 하나뿐이다.

탐색 쪽도 비어 있다. 덱빌딩·일꾼 놓기 게임에서 PIMC, IS-MCTS, 학습된 믿음 탐색을 비교하거나 strategy fusion·non-locality의 크기를 잰 연구는 찾지 못했고, 필요한 세계 수의 자료점도 LoCM의 "약 32개에서 포화" 하나뿐이다. 규모 법칙인 Jones와 Neumann & Gros는 2인 완전 정보 게임의 결과라, 4인 불완전 정보 게임에 대해서는 말해 주는 것이 없다. 승리만 보는 보상(+1/−1/3)과 순위·점수 보상을 4인 euro 게임에서 비교한 연구도 없으며, 가장 가까운 것은 3인 DouZero의 WP 대 ADP와 4인 마작 Suphx의 GRP다.

나머지 빈칸은 이렇다. 증류한 RL 학생이 어떤 결정 종류에서 강도를 잃는지 잰 연구는 찾지 못했으니, "선생이 불확실한 결정에 손실이 몰린다"는 우리 측정은 그 자체로 새 자료다. Dune: Imperium, Lords of Waterdeep, Agricola에 대해서는 공개된 신경망 AI가 아예 없다. 끝으로 AlphaStar Unplugged의 폭·LSTM 결과처럼 인용한 대규모 시스템 숫자 일부는 행동 복제 결과라, self-play RL로는 약하게만 옮겨진다.

## Conclusion

이번 비교에서 얻은 가장 쓸모 있는 깨달음은, 우리 두 망이 겉보기보다 훨씬 덜 다르다는 것이다. 행마다 출력하는 head는 자유 행동 벡터와의 내적이다. 조립식 행동 벡터는 드문 결정에서 그 자유 벡터(own_actions)를 다시 붙이고서야 MLP와 같아졌다. 카탈로그가 고정되고, 결정마다 합법 행동이 수십 개이고, 결정이 수백만 개인 우리 영역에서 행동 head의 형태는 병목이 아니다. 병목은 신호에 있다. 그 신호는 셋이다. 첫째는 판 끝 보상 하나로 학습률 1e-5에서 도는 REINFORCE의 약한 신호로, 두 망 모두 임페리움 열을 0.3%만 읽는다. 둘째는 판을 외우는 공유 가치 head이고, 셋째는 선생이 만든 국면으로 하는 증류다. 탐색 좌석은 strategy fusion이 없는 건전한 한 걸음 정책 개선이다. 그 개선 폭을 묶는 것은 균일한 세계 표본, 잡음 섞인 argmax, 고정된 상위 5 후보 같은 배관이고, 이 배관은 학습 없이 몇 시간 만에 시험할 수 있다.

앞으로의 판단 기준도 바뀌어야 한다. 망만의 실력 향상이 탐색 좌석으로 넘어오지 않은 전례(M 대 8081)가 있다. 가치를 판 결과에 더 잘 맞추자 탐색이 나빠진 전례(ExIt v1)도 있다. 그러니 망이나 가치에 대한 어떤 변경도 짝지은 시드의 탐색 좌석으로 판정해야 하고, 천장을 피하려면 플레이 망 셋을 상대로 재야 한다. 엔티티 계보를 이어 갈 이유는 기대 강도가 아니다. 새 카드와 규칙 변경을 처음부터 다시 학습하지 않고 받는 유지보수 능력이 그 이유다. 그 계보를 다시 돌릴 때는 순수 증류 뒤 순수 RL이 아니라, 학생 국면 증류와 kickstarting으로 선생과의 격차부터 닫아야 한다.
