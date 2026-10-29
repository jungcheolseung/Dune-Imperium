# 사람이 둔 판을 데이터로: 기보 이전과 변환

2026-10-10. 사용자 질문 "사람이 플레이했던 기록을 학습에 반영하기 위한 데이터로 쓸 수 있을까?"에서 시작했다. 답을 정리한 뒤 사용자가 고른 일은 둘이다. 하나는 진단이고([evaluation/human-games-2026-10-10.md](evaluation/human-games-2026-10-10.md)), 다른 하나가 이 문서의 "엔진이 바뀌어도 기보가 살아남게"다. 누가 뒀는지와 무르기 기록은 쓰지 않기로 했다. 누가 잘하는지 판단하기 어렵고, 물렀다가 같은 수를 다시 두기도 하기 때문이다.

2026-10-28 사용자 결정으로 방법이 바뀌었다. codec을 올릴 때마다 다리를 쌓지 않고, **올릴 때마다 남겨 둘 기보를 모두 한 번 지금 codec으로 변환**한다. 다리는 바로 앞 codec에서 지금 codec으로 가는 것 하나까지만 둔다(3절). 2026-10-29에 남은 기보를 모두 v156으로 변환하고 v135~v155의 다리 52개를 지웠다(5절).

- 코드: `src/dune_imperium/records/`(`migration.py` 다리, `convert.py` 변환, `saves.py` 저장본 읽기, `problems.py` 문제집), `src/dune_imperium/cli/records.py`(`dune-imperium-records`).
- 저장본을 읽는 쪽에는 `parse_save_document(..., check_versions=False)` 하나만 더했다. 서버의 불러오기는 그대로 버전이 정확히 같아야 한다.
- 테스트: `tests/unit/records/`. 옛 엔진이 쓴 기보 파일은 두지 않는다. 테스트는 이 엔진에서 판을 두고, 옛 엔진의 기보가 필요하면 옛 엔진이 적지 않았을 것(멈춤, 열지 않던 창)을 빼서 만든다(`tests/support/records.py`).

## 1. 왜 깨지나

저장본은 수를 **뜻으로** 적는다. 행동이면 `action_id`·actor·인자, chance면 결정 id와 뽑힌 값이다. codec 행 번호는 적지 않는다. 그래서 codec 번호가 올라갔다는 것만으로 기보를 못 읽게 되지는 않는다.

깨지는 것은 **엔진의 흐름**이 바뀔 때다. 새 엔진이 옛 엔진은 묻지 않던 것을 물으면, 다음에 적힌 수가 엉뚱한 결정을 만난다. 2026-10-10 로컬 저장본 네 판 중 옛 두 판(v135, v139)이 2라운드의 discard shuffle에서 멈춘 까닭이 이것이다. v140의 공개 앞 멈춤(OQ-103)이 그 앞에 chance 결정을 하나 끼워 넣었다.

## 2. 다리(bridge)

`migrate_record`는 적힌 수를 차례로 둔다. 엔진이 어떤 수를 거절하면, `BRIDGES`의 다리가 엔진이 기다리는 결정에 옛 엔진이 "묻지 않음으로써" 답한 대로 답한다. 그다음 적힌 수를 다시 둔다.

- **종류.** 보통 다리는 적힌 수가 거절될 때 그 앞에 수를 넣는다. `rewrites` 다리는 적힌 수 자체를 이 엔진의 말로 바꾼다. `follows` 다리는 적힌 수가 적용된 **직후**, 옛 엔진이 그 일을 한 바로 그 순간에 이 엔진이 따로 떼어 낸 부분을 넣는다(거절을 기다리면 그 사이의 적힌 수가 이미 그 부분이 끝난 상태를 보고 둔 것이라 늦다). `follows` 다리는 아무도 답하지 않을 때까지 처음부터 다시 묻는다(고정점, 한 수 뒤 32번까지).
- **`before_codec`.** 다리는 그 codec보다 옛 기보에만 열린다. `pause`(결과가 하나뿐인 chance에 그 결과로 답한다, `rules/pauses.py`)만 모든 기보에 열려 있다. 멈춤은 공개 사실로 정한 자리에 서고 선택도 뽑기도 없기 때문이다.
- **안전장치(`_made_for`).** 다리는 적힌 수가 **바로 그 결정의 답**일 때는 끼어들지 않는다. 결정을 가진 좌석이 둔 수의 `action_id`가 그 틀이 답으로 받는 id이거나 지금 그 결정이 내놓는 id이면 그 결정의 답으로 본다. 첫째 조건은 규칙 변경으로 그 종류의 행동이 **모두** 사라진 경우를 위한 것이다(2026-10-10 독립 리뷰가 찾은 빈틈). 다리 모양으로 가장 흔했던 "옛 엔진이 열지 않던 창의 거절"은 `_decline_in`으로 만든다.
- **다시 쓰기는 일반 규칙으로 두지 않는다.** 이 엔진에서는 인자가 없다는 것 자체가 선택이다. 처음에 두었던 "같은 id에 인자만 늘어난 행동이 하나면 그것으로"라는 일반 규칙은 불법이 된 수를 다른 선택으로 바꿔 끝까지 옮겼다(독립 리뷰). 다리는 행동 하나·인자 하나·codec 문턱이 정해진 것으로 좁힌다.
- **갈라짐.** 규칙이 바뀌어 사람이 둔 수가 불법이 되면, 그 자리를 건너뛰지 않고 `Divergence`로 멈춘다. 그 앞까지의 수는 그대로 쓸 수 있다.

## 3. codec을 올릴 때마다 한 번 변환한다

사용자 결정(2026-10-28): 다리가 codec마다 덕지덕지 쌓이는 것보다("덕지덕지 붙은건 없는게 좋겠는걸") 변환을 고르고, 방법은 추천대로("나머지는 추천대로") 했다.

- **남겨 둘 기보**는 엔진이나 도구가 읽는 기보 전부다. 사람 저장본(`saves/`), 사람 판 문제집(`local/records/human-problems.json`)과 AI 실수 문제집(`local/records/ai-mistakes.json`), 그리고 추적 파일 가운데 기보를 담은 것이다. 지금 추적 파일에는 옛 엔진 기보가 없다. tips-v1 문제집(`src/dune_imperium/evaluation/problem_sets/tips-v1.json`)은 기보가 아니라 시드와 선택 번호로 포지션을 되살리므로 다리를 거치지 않는다(아래 4절 3).
- **기보 묶음**(`local/records-corpus/`)은 변환하지 않는다. 관문은 가장 새 묶음만 쓰고, 병합 때마다 새 묶음을 만든다. 옛 묶음을 지울지는 사용자가 정한다.
- **다리는 하나까지.** `pause` 말고는 바로 앞 codec에서 지금 codec으로 가는 다리 하나만 둔다. 그 다리는 다음 codec을 올릴 때 지운다. 그때는 남은 기보가 모두 변환되었고, 관문이 읽는 묶음도 새로 만든 것이기 때문이다.
- **원본 보관.** 변환한 기보의 원본은 `local/records-archive/<날짜>/originals/`(git 무시)에 바이트 그대로 둔다. 어느 코드도 읽지 않는다. 사용자 저장본은 지우지 않는다.

`dune-imperium-records convert --out <새 폴더>`가 변환한다(`records.convert`). 입력은 읽기만 하고 `--out` 밖에는 쓰지 않는다. 모든 파일을 먼저 메모리에서 변환·확인하고 그다음에 쓴다. 한 기보라도 실패하면(`ConversionError`, 파일 경로를 댄다) 보관 폴더는 생기지 않는다.

- `originals/<경로>`: 원본의 바이트 복사본. `converted/<경로>`: 변환한 파일. `<경로>`는 `--root`(기본은 프로젝트 폴더) 아래의 경로라, 바꿔 넣을 자리가 그대로 보인다. 두 폴더에는 입력만 들어간다.
- `manifests/originals.json`·`manifests/converted.json`: 파일마다 경로, sha256, 크기, codec. 변환본에는 원본의 sha256과 결과(exact·migrated·갈라짐, 수의 수, 쓴 다리, 문제 수)도 적는다. 보관 폴더 자신의 파일(이 둘과 `swap-plan.md`)은 두 거울 폴더 밖에 있어서, 이름이 `manifest.json`인 입력도 덮어쓰지 않는다(2026-10-29 독립 리뷰: 처음에는 manifest를 `originals/`·`converted/` 안에 두어, 뿌리 바로 아래의 `manifest.json` 입력이면 원본 복사본과 변환본을 덮어쓰고 바꿔 넣기 계획이 진짜 파일을 manifest로 바꿀 수 있었다).
- `swap-plan.md`: 변환본을 제자리에 넣는 `cp` 줄. 바꿔 넣기는 변환본을 확인한 뒤 사람이(또는 조정 세션의 허락을 받은 세션이) 한다.

저장본 하나의 변환:
- 수는 `migrate_record`가 옮긴 수 전부다(다리가 넣은 수와 다시 쓴 수 포함). 지금 엔진의 버전과 그 수들이 닿는 상태 해시를 찍는다. 그래서 서버의 엄격한 `parse_save_document`가 받고, 다리 없이 그대로 재생된다(exact). 변환이 끝나면 이를 확인한다(`verify_converted_save`).
- 수가 바뀌면 세션 로그는 살아 있는 수만 남긴다. 무른 수는 옛 엔진에서 둔 것이라 이 엔진에 짝이 없다. 기보는 무르기 기록을 쓰지 않고(위 결정), 원본에는 그대로 남아 있다. 수가 그대로면 로그도 그대로 둔다.
- **망가진 입력을 덮지 않는다(`ConversionError`, 2026-10-29 독립 리뷰).** 이미 이 엔진의 버전이 찍힌 저장본은 자기가 적은 상태 해시에 닿아야 한다. 닿지 않으면 수가 잘렸거나 바뀐 것이라 새 해시로 덮지 않고 실패한다. 옛 엔진의 해시는 다시 만들 수 없으므로, 옛 저장본은 적힌 수가 모두(갈라진 기보는 갈라진 수 앞까지 모두) 변환본에 들었거나 다리가 이름을 대고 지운 것(`dropped_steps`, manifest에 적는다)인지를 확인한다. 꼬리가 소리 없이 잘린 변환은 실패한다.
- 적힌 수의 수를 세는 칸(`sealed_steps`, `open_units`)은 옮긴 수에 맞춰 다시 센다. `round_number`·`phase`·`finished`는 변환한 상태에서 읽는다. 다른 칸(좌석, 시드, 이름, 저장 시각, 속도, 시계)은 그대로다.
- `converted_from`에 원래 codec, 수의 수, 상태 해시, 갈라짐을 적는다.
- **갈라지는 기보는 억지로 잇지 않는다.** 갈라진 수 앞까지를 변환본으로 두고(끝나지 않은 판이 된다) 보고한다. 지울지는 사용자에게 묻는다.

문제집 하나의 변환:
- 기보는 저장본처럼 변환하고(문제집의 기보는 로그 없는 형식 1 그대로), 문제마다 이 엔진에서 그 포지션을 묻는 변환 수로 `recorded_index`를 옮긴다. 두 수(`right`·`wrong`)는 그 자리에서 이 엔진이 묻는 행동이다. 문제 id는 그대로다.
- 판정 때의 좌석 상태(`judged_state`)는 그대로 둔다. 이 엔진이 같은 포지션에 다른 좌석 상태로 닿으면 그 문제는 빠지고 보고된다. 다만 사용자가 정한 규칙 변경으로 달라지는 칸을 `--recapture <칸>`으로 주면, 차이가 그 칸뿐인 문제는 이 엔진의 포지션에서 다시 찍는다(2026-10-29의 `hand_public`, OQ-145).
- 변환이 끝나면 변환한 문제집이 변환 전과 같은 포지션(상태 해시), 같은 두 수, 같은 합법 행동 목록으로 풀리는지 확인하고, 아니면 멈춘다.

## 4. 다음 codec bump 때 할 일

codec을 N에서 N+1로 올리는 브랜치가 있을 때.

1. **확인.** 브랜치에서 `uv run dune-imperium-records check --saves-dir <메인 체크아웃>/saves`와 `uv run dune-imperium-records problems check --suite <메인 체크아웃>/local/records/human-problems.json`(AI 실수 문제집도)을 돌린다. 기보 묶음(`corpus check`)은 관문이 돌린다.
2. **앞 다리 지우기.** 직전 bump가 남긴 다리(`before_codec=N`)를 그 테스트·기록과 함께 지운다. 남은 기보는 직전 bump 때 모두 N으로 변환되었다.
3. **새 다리(필요할 때만).** 흐름이 바뀌어 v N 기보가 멈추면 `check`가 적힌 수와 엔진이 기다리는 결정을 함께 보여 준다. 새 엔진이 옛 엔진은 묻지 않던 것을 묻기만 한다면 `before_codec=N+1`인 다리를 하나 더하고(`_decline_in` 모양이면 그것으로, `_made_for`를 지키며), 옛 엔진이 실제로 쓴 기록으로 지킨다(`scripts/records/old_engine_record.py`를 앞 커밋의 worktree에서 돌린다). 적힌 선택 자체가 불법이 되었다면 멈추는 것이 맞는 답이다.
4. **tips-v1.** `uv run dune-imperium-problems check`가 모든 포지션을 되살리면 파일 머리의 `action_codec_version`·`observation_version`만 새 값으로 고친다. 포지션이 움직였으면 [evaluation/problem-set.md](evaluation/problem-set.md)의 명령으로 다시 캔다.
5. **변환.** 다리가 있는 코드(브랜치 worktree 또는 병합한 master)에서, 메인 체크아웃의 기보를 읽어 보관 폴더로 변환한다.

   ```bash
   uv run dune-imperium-records convert --root <메인 체크아웃> \
       --saves-dir <메인 체크아웃>/saves \
       --suite <메인 체크아웃>/local/records/human-problems.json \
       --suite <메인 체크아웃>/local/records/ai-mistakes.json \
       --out <메인 체크아웃>/local/records-archive/<날짜>   # 규칙 결정으로 바뀐 칸이 있으면 --recapture <칸>
   ```

   변환본을 확인한다: `check --saves-dir <보관>/converted/saves --every-save`가 모두 exact, 문제집 `problems check`가 변환 전과 같은 수.
6. **바꿔 넣기.** 병합 때(조정 세션의 허락 뒤) `swap-plan.md`의 `cp` 줄로 변환본을 제자리에 넣는다. 병합한 코드에 남은 기보를 잇는 다리가 없으면(2026-10-29처럼 기보가 아직 여러 옛 codec일 때) 병합하는 순간 옛 기보가 갈라지므로, 병합과 바꿔 넣기를 함께 한다.
7. 병합 뒤 새 기보 묶음을 만든다(관문 절차).

## 5. 2026-10-29: v156으로 변환하고 v135~v155 다리를 지움

브랜치 `claude/records-convert`(master `6352199d`, codec v156에서). 변환은 다리가 모두 있던 코드로 했다.

- **보관 폴더** `local/records-archive/2026-10-29/`: 저장본 18개(11판, codec 135~152)와 문제집 둘의 원본(`originals/`)·변환본(`converted/`)·`manifests/` 둘·`swap-plan.md`. 독립 리뷰 뒤 같은 입력을 다리가 있던 코드에 리뷰 수정을 얹은 도구로 다시 변환해, 변환본 20개와 원본 복사본 20개가 바이트까지 같은 것을 확인하고 manifest(이제 옛 다리가 이름을 대고 지운 적힌 수도 판마다 적는다)와 계획만 새 자리에 다시 썼다.
- **저장본:** 18개 모두 끝까지 옮겨졌고 갈라진 것은 없다. 변환본 18개는 이 엔진에서 모두 exact이고, 판마다 하나를 고르는 `one_save_per_game`도 원본과 같은 11개를 고른다. v152 판 하나(`d8c0779e`)는 다리 없이 모든 수가 맞지만 끝 상태 해시가 이 엔진과 달랐고, 변환본은 이 엔진의 해시를 적는다.
- **문제집:** 사람 판 281곳이 모두 변환되었다(변환 전 이 엔진에서 265곳이 풀렸다). 나머지 16곳(`885ed2f0` 3, `8f8df4bc` 5, `c3adefb4` 5, `fb716981` 3)은 OQ-145 판정 (나)대로 덱 위에 공개로 놓였던 Tleilaxu 카드가 뽑힌 뒤 `hand_public`에 드는 것만 달라, `--recapture hand_public`으로 이 엔진의 포지션에서 판정 상태를 다시 찍었다(다른 칸의 차이는 없음을 칸마다 확인). AI 실수 3곳도 변환되었다. 문제집의 기보는 같은 판의 변환한 저장본과 수·해시가 같다.
- **서버 불러오기:** 변환본 18개 모두 서버의 엄격한 버전 검사(`parse_save_document`)를 통과한다. 세션 불러오기(`GameSessionManager.restore_game`, 서버를 띄우지 않고)로 시험하니 사람 좌석만 있는 저장본 셋(두 판)과 사람 1·앱 AI 3인 판의 저장본은 불러와진다. rollout_strong 좌석이 있는 v135 두 저장본은 그 AI가 2번째 수(지도자 고르기)에서 기록과 다른 수를 골라 거절된다(지금의 AI가 옛 AI와 다르게 두는 것이라 변환과는 상관없다). 탐색 좌석이 있는 12개는 망 파일을 읽어야 해서 시험하지 않았다.
- **tips-v1:** 118곳 모두 v156에서 되살아나, 파일 머리를 codec 156·관측 38로 고쳤다. 다시 캐서 같은지 보는 것은 병합 관문이 한다.
- **지운 것:** `BRIDGES`의 다리 52개(`pause`만 남김)와 다리 밖에서 옛 기보를 따라가던 길(접합 칸 `_GraftSlot`, Reveal 선택 창 `_RevealSlot`, 턴 줄로 붙잡기, 먼저 묻기, Overthrow 계획, Harvest Cells 정리, 열지 않던 창에 미리 답하기), codec 문턱 상수 12개(`GRAFT_BOXES_CODEC`·`OPTIONAL_REFUSALS_CODEC`·`REVEAL_CHOICES_CODEC`·`TURN_ROW_REFUSALS_CODEC`·`CONTRACT_TURN_ROWS_CODEC`·`OVERTHROW_CODEC`·`MISSION_WINDOW_CODEC`·`FACTION_WINDOW_CODEC`·`PLANETARY_ARRAY_ROW_CODEC`·`COST_FREE_PLAYS_CODEC`·`OPPONENT_DISCARD_WINDOW_CODEC`·`NEVER_ASKED_CODEC`), `MigratedStep`의 `graft_box`·`reveal_source`·`whole`·`named_by`와 `MigratedRecord.dropped`. 문제집에서는 옛 엔진의 말로 판정한 문제를 위한 길(카드 고르기 앞에서 묻기, 효과 단계에서 묻기, 없어진 거절을 턴 종료에서 묻기)이 빠졌다. 테스트는 다리 테스트(`test_record_migration.py`의 94개, `test_navigation_fizzle_bridge.py` 2개, 문제집 테스트의 다리 관련 10개)와 옛 엔진 기보 20개(`tests/unit/records/data/`)를 지우고, 남긴 구조(위 2절)를 이 엔진의 판과 시험용 다리로 다시 지켰다.

## 6. 쓰는 법

```bash
uv run dune-imperium-records check
```

`saves/`의 저장본을 판마다 하나씩 읽는다(`one_save_per_game`). 같은 판은 룰셋, 시드, 좌석 배정이 같은 저장본들이다. 자동 저장, 수동 저장, 그리고 불러온 세션의 저장본(불러오면 게임 id가 새로 생기지만 좌석은 그대로다)이 여기에 든다. 룰셋과 시드가 같아도 좌석이 다르면(기보 corpus의 좌석 조합처럼) 다른 판이다.
- 판의 줄기는 가장 새 **끝난** 저장본을 지난다. 끝난 것이 없으면 가장 새 저장본을 지난다.
- 줄기 위의 저장본(하나가 다른 하나의 앞부분)은 같은 판이고, 수가 가장 많은 것을 쓴다.
- 줄기 밖의 저장본은 버린다. 무르고 다르게 둔 갈래나, 불러와 잠깐 다르게 둬 본 갈래다.

`--every-save`는 모두 본다. 결과는 넷 중 하나다: 그대로 재생(exact), 옮김(migrated, 쓴 다리와 횟수), 갈라짐(diverged, 몇 번째 수, 엔진이 기다린 결정), 엔진 오류(failed; 그 판만 보고하고 다음 판으로 간다).

코드에서는 다음과 같이 쓴다.
- `records.saves.saved_games(디렉터리)` → `SavedGame`
- `human_decisions(game)` → 사람이 둔 수마다 그 직전 상태, 합법 행동, 고른 수(`HumanDecision`). 다리가 넣은 수는 사람의 선택이 아니므로 빠진다.
- 진단 도구 `scripts/records/human_diagnosis.py`가 이것을 쓴다.
- `records.problems`: 진단에서 두 판정이 일치한 포지션을 기보째 고정한 문제집이다. 포지션은 기보를 이 엔진으로 옮겨, 문제의 적힌 수 바로 앞 상태로 되살린다. 채점은 `dune-imperium-records problems check|score`([evaluation/human-games-2026-10-10.md](evaluation/human-games-2026-10-10.md) 6절).

## 7. 한계

- **서버의 불러오기는 그대로다.** 버전이 다른 저장본으로 게임을 이어 두지는 못한다. 변환본은 버전 검사를 통과하지만, 불러오기는 AI 좌석의 수를 그 AI로 다시 두어 기록과 맞춰 보므로 AI가 그때와 다르게 두면 거절된다(5절).
- **보장은 "적힌 모든 수가 지금 엔진에서 합법"까지다.** 규칙 수정이 어떤 카드의 결과를 바꾸면, 그 뒤의 상태는 사람이 본 것과 조금 다를 수 있다. 다리를 둘 때 옛 엔진과 한 수씩 대조해 그런 차이를 쟀다(8절). 앞으로의 변경에는 같은 대조를 다시 해야 안다.
- 흐름을 바꾸는 codec 변경 때 `dune-imperium-records check`를 돌려 보는 것이 가장 싸다. 그때 고치면 무엇이 바뀌었는지 아직 기억한다.

## 8. 지운 다리의 역사

v135~v155 기보를 v156으로 잇던 다리 52개의 표, 다리마다의 근거(커밋·OQ·사용자 판정), 다리 없이 갈라지는 경우, 옛 엔진과의 한 수씩 대조(사람 판·AI 판·기보 묶음)는 이 문서의 2026-10-28판에 있다: `git show 6352199d:docs/human-records.md`. 다리 코드와 그 테스트·옛 엔진 기보도 같은 커밋에 있다(`src/dune_imperium/records/migration.py`, `tests/unit/records/test_record_migration.py`, `tests/unit/records/data/`). 다른 문서가 이름으로 부르는 다리는 아래와 같다.

| codec 문턱 | 다리 |
|---|---|
| 137 | `agent_card_effect_named` |
| 139 | `combat_intrigue_pass` |
| 141 | `conflict_end_window` |
| 142 | `imperial_privilege_draw`, `garrison_unit_troop`, `prison_planet_commanders_only`, `shigawire_draw`, `planetologist_intrigue`, `intrigue_held_rewards`, `piter_reward`, `reverse_engineering_reward`, `scouts_held_draw`, `scouts_reward_pause`, `owed_draw`, `unpredictable_foe_draw`, `reshuffle_renamed`, `refinish_agent_turn` |
| 143 | `graft_switch`, `graft_box` (`_GraftSlot`) |
| 144 | `shigawire_partner_draw`, `box_refused_at_turn_end` |
| 145 | `boost_draw_at_turn_end` |
| 146 | `optional_refusal`, `repeated_mission_collection` (지움) |
| 147 | `reveal_choice_defer`, `reveal_choice_resume`, `reveal_optional_refusal`, `reveal_optional_refusal_by_order`, `reveal_source`, `reveal_source_by_order` (`_RevealSlot`) |
| 149 | `scouts_no_option_window`, `research_icon_order`, `conflict_end_finish`, `conflict_end_reopened`, `tech_influence_confirm`, `draw_reshuffle_renamed`, `split_box_icon`, `split_box_follow`, `split_box_spy`, `signet_without_option`, `combat_trash_declined_without_card`, `combat_trash_without_card`, `turn_row_refusal`, `influence_at_top`, `turn_row_held`, `harvest_cells_at_once`, `harvest_cells_rewards`, `reshuffle_moved` |
| 150 | `combat_reward_icon`, `combat_reward_icon_follow`, `transports_card_first`, `transports_reshuffle_renamed`, `agent_space_pick`, `agent_card_pick`, `effect_last_step`, `effect_step`, `optional_trash_icon`, `named_pick`, `contract_frame_first` |
| 152 | `conspiracy_icon`, `conspiracy_spice`, `breakthrough_research`, `guild_envoy_draw`, `navigation_reshuffle_renamed`, `scouts_pass_without_option`, `overthrow_for_space`, `overthrow_deferred`, `overthrow_with_the_space`, `mission_pass_alone`, `equilibrium_alone` |
| 153 | `scouts_faction_alone`, `scouts_faction_alone_draw`, `scouts_faction_reshuffle_renamed` |
| 154 | `planetary_array_row`, `tech_draw_at_the_win`(149 전 기보에도), `navigation_fizzle_played`, `navigation_fizzle_confirmed` |
| 155 | `opponent_discard_alone` |
