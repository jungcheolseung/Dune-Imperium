# Dire Wolf 앱 추출·분석 도구 (`scripts/dwgr/`)

Steam에 설치된 Dire Wolf Digital의 Unity 앱 두 개를 읽는 도구다.

- **Dire Wolf Game Room**의 Dune: Imperium 컴패니언(내부 이름 `grm.companions.spice`)
  - **Arrakeen Scouts**(아라킨 스카웃) 모드의 정의 데이터, 문구, UI 트리
  - 일정 생성 코드
  - 공식 룰북이 없는 모드라서 이 추출이 규칙 출처다. 설계와 쓰임새는 [`docs/arrakeen-scouts-design.md`](../../docs/arrakeen-scouts-design.md)(M15)에 있다.
- **Steam Dune: Imperium 앱**(디지털판, Uprising·Rise of Ix·Immortality 포함)의 규칙 엔진 코드(`worm.canis.*`, 어셈블리 `worm-canis.dll`)
  - 공식 규칙 출처가 아니다. 아래 "Steam Dune: Imperium 앱"을 본다.

## 출력은 어느 저장소에도 넣지 않는다

- 추출 결과(문구, 정의, UI 트리)와 분석 결과는 Dire Wolf Digital의 저작물에서 나온 것이다. 공개 저장소인 이 저장소에는 넣지 않는다. 이 저장소에는 이름·수치·의역만 둔다.
- 비공개 에셋 저장소의 이력에도 넣지 않는다. 에셋 저장소에는 게임에 쓰이는 에셋만 남긴다(2026-09-28 사용자 결정).
- 출력의 기본 자리는 에셋 체크아웃의 `reference/dwgr-arrakeen-scouts/`(Game Room)와 `reference/dune-steam-app/<build-guid>/`(Steam Dune 앱)다. 에셋 `.gitignore`가 두 폴더를 빼므로 파일은 그 기기에만 남는다.
- 앱의 코드를 이 저장소의 코드나 AI로 옮기지 않는다. 디스어셈블에서 읽은 판정은 의역해 기록한다.
- 다른 기기에서는 앱을 설치하고 다시 추출한다(약 5초).
- 2026-09-27~28 분석 결과는 Mac mini의 그 폴더 `analysis/`에만 있다: 코드 분석, 항목별 해석, 반박 검증, 확률 스크립트, 한국어 요약 `report-ko.md`.
- 예외: 플레이 UI가 실제로 보여 주는 그림(아이콘, 보드 말, 앱 조각으로 조립한 카드 앞면)은 `app_assets.py`(`icons`·`pieces`·`strength`·`backs`), `app_cards.py`(`render`), `app_board.py`(`render`, 보드 칸 그림), `app_leaders.py`(`render`, 지도자 카드), `app_log_icons.py`(행동 로그 그림)가 에셋 저장소의 `icons/`·`tokens/`·`cards/app/`에 쓰고 에셋 저장소에 커밋한다(2026-10-07 사용자 결정, "게임에 쓰이는 에셋"). 색인·스프라이트·폰트 같은 중간 자료는 위 규칙대로 `reference/dune-steam-app/<build-guid>/render/`에만 둔다.

## 준비

프로젝트 의존성이 아니다. `uv run --no-project`로 필요한 패키지만 임시 환경에 얹는다.

```bash
cd scripts/dwgr
uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone python il2meta.py
```

`il2meta.py`를 그냥 실행하면 찾은 표의 위치와 크기를 출력한다(build-guid, 인덱스 폭, CodeRegistration, codeGenModules, MetadataRegistration, 메서드 수).

읽을 앱은 `IL2CPP_APP`으로 고른다. 값은 별칭 `dwgr`(기본값, Game Room)·`dune`(Steam Dune: Imperium)이나 `.app`의 `Contents` 폴더 경로다. 예전 이름 `DWGR_APP`도 읽는다.

## 도구

| 파일 | 하는 일 |
|---|---|
| `extract.py <out_dir>` | 한 번에 전부 추출한다. `manifest.json`(build-guid, Unity 버전, 원본 파일 sha256), `spice_mb/*.json`(모든 spice MonoBehaviour·ScriptableObject), `schedules.json`(일정 풀 8개), `loc/<lang>.json`(13개 언어, spice 키와 프리팹이 쓰는 키), `text_sprites.json`, `beat_prefabs.json`, `beats_bundle.txt`(정의별로 모아 읽는 파일) |
| `il2meta.py` | IL2CPP global-metadata(v31: Unity 2022.3, v39: Unity 6000.3)와 Mach-O를 읽어 메서드 주소·시그니처·제네릭 인스턴스·필드 오프셋·enum 값·지연 초기화 전역(TypeInfo·MethodRef·문자열 리터럴)을 푼다. universal 바이너리는 x86_64 부분을 쓰고, chained fixups 포인터를 일반 주소로 푼다. 표의 위치는 검색으로 찾는다 |
| `il2dump.py <out_dir> [--asm] [어셈블리 ...]` | 이름 수준 덤프. 어셈블리별 `<이름>.cs`(타입·부모·필드 오프셋과 static/const·기본값·메서드 시그니처와 주소), 전체 `methods.tsv`, `strings.tsv`(문자열 리터럴), `generics.tsv`(공유 제네릭 코드의 주소와 인스턴스 이름), `manifest.json`(build-guid, 앱·Unity 버전, sha256). `--asm`이면 `asm/<어셈블리>/<타입>.asm`에 최상위 타입마다(중첩 타입 포함) 모든 메서드의 `il2dis` 출력을 쓴다. 바이너리를 다시 읽지 않고 grep할 수 있다(Steam 앱 6개 어셈블리 약 30초, 144MB) |
| `il2dis.py <메서드 이름 일부 \| 0x주소>` | 메서드의 x86-64 디스어셈블에 호출 대상·메타데이터·float 상수 주석을 단다(capstone). `~`로 시작하는 주석은 레지스터를 따라가 붙인 이름이다: `this`와 알려진 필드에서 읽은 객체의 필드(`~Type.field`), 정적 필드(`~static Type.field`), 가상 호출 슬롯(`~vslot N Type::Method`). 분기 합류점에서는 모든 경로가 같은 타입일 때만 이어 가고, 가상 슬롯은 정적 타입(기반 클래스일 수 있음)의 메서드 이름이다. 컴파일러의 상대 점프 테이블은 `; ---- jump-table case N ----` 줄로 case 시작을 표시한다(coroutine `MoveNext`에서는 case 번호가 대개 `<>1__state` 값) |
| `il2fields.py <타입 전체 이름 \| 접두사*>` | 타입의 필드 오프셋·타입·enum 값과 메서드 주소 |
| `il2xref.py <메서드 이름 일부 \| 0x주소>` | 그 메서드를 직접 부르는 곳(E8/E9 rel32) |
| `app_assets.py index \| icons \| pieces \| strength \| backs \| sprites \| prefabs \| fonts \| card-inputs` | Steam Dune 앱의 Addressables 번들에서 그림을 꺼낸다. `index`는 번들 전체(100 MB 넘는 도전 과제 그림 번들 제외)를 한 번 훑어 CAB 이름, 컨테이너 경로, 스프라이트·텍스처 이름과 크기를 `render/index.json`에 적는다(약 1분, 메모리 1.4 GB). `icons`는 플레이 UI 아이콘 45개를 같은 그림의 앱판으로 에셋 `icons/`에 덮어쓴다(대응표는 파일 안 `APP_ICON_SOURCES`, 출처는 `icons/app_sources.json`). `sprites`는 이름으로 스프라이트를 PNG로 꺼내며 다른 번들에 있는 아틀라스도 따라 읽는다. `prefabs`는 카드 프리팹을 JSON 트리로, `fonts`는 TextMeshPro SDF 글꼴과 글 속 아이콘(TMP sprite asset) 크기표를 꺼낸다 |
| (위 줄 이어서) | `pieces`는 보드 말(Agent·Spy·Control·병력·모래벌레·High Council 원판·player disc)을 좌석 색 넷으로 에셋 `tokens/<말>_<색>.png`에 쓴다(대응표 `APP_PIECE_SOURCES`; 색 있는 Spy가 앱에 없어 회색 원통에 그 색 병력 큐브의 색을 곱한다; 출처 `tokens/app_sources.json`). `card-inputs`는 카드 렌더에 드는 프리팹·글꼴·영어 문구·스프라이트·글 속 아이콘을 `render/` 아래에 한꺼번에 꺼낸다 |
| `app_log_icons.py [--out DIR]` | 플레이 UI 행동 로그의 그림 26개(`dune_imperium.display.log_icons.LOG_ICON_NAMES`)를 앱 스프라이트에서 에셋 `icons/log_<이름>.png`로 쓴다(대응표는 파일 안 `LOG_ICON_SOURCES`, 출처는 `icons/log_sources.json` — `icons`가 `app_sources.json`을 제 이름으로만 다시 쓰므로 따로 둔다). 교전의 교차 칼, 라운드 숫자 1–10, 다시 섞기, 로그의 붉은 트래시 X, Intrigue 문양과 쓴 카드, 병력 배치·후퇴 배지, 승자 화관, 진영 넷의 영향력 하락 표시, Tleilaxu·연구·Family Atomics·기술. 같은 그림의 128 px판이 있으면 그것을 쓴다. 그림마다 그린 부분만 잘라 정사각형으로 채우고, 라운드 숫자는 스프라이트 틀에 되돌려 한 상자로 잘라 높이와 기준선을 맞추며, 병력 배지는 바깥 빛 고리를 떼어 불투명한 육각 배지만 남긴다(고리째로는 로그 크기에서 화살표가 안 보였다). 앱 로그의 나머지 아이콘은 이미 있는 `icons/`의 그림·동맹 토큰과 같은 그림이라 다시 꺼내지 않는다. `index`가 먼저 있어야 한다(약 1초, 메모리 약 180 MB, 다시 돌려도 같은 바이트) |
| (위 줄 이어서) | `pieces`는 Alliance token 넷과 시작 플레이어 마커(`first_player`, 앱 HUD의 `hud_Icon_FirstPlayerToken` 128 px, 원판에 맞춰 자름)도 쓴다. `pieces --only 이름…`은 이름이 그렇게 시작하는 그림만 다시 만들고 출처 표의 다른 줄은 그대로 둔다. `strength`는 UnityPy 그림을 읽지 않고 Combat marker 두 면(`tokens/strength_<색>.png`, `_plus20.png`)을 앱 조각으로 조립한다: 좌석 색 타일(파일 안 `STRENGTH_TILE_COLORS` = `render.js`의 `SEAT_COLORS`, 테스트가 대조), 어두운 안쪽 네모, 앞면은 `icons/sword.png`(`UI_crd_ActionIcon_Strength`), 뒷면은 Gotham-Bold SDF로 그린 "+20". 앱에는 이 marker가 없어(힘을 숫자로 보인다) 프로젝트 조립품이고 출처 표의 `compositions`에 적는다. `backs`는 카드 뒷면 여섯(Imperium·Intrigue·Conflict I/II/III·Tech, 대응표 `APP_BACK_SOURCES`)을 `tokens/back_<종류>.webp`(WebP 88, 37–75 KB)로 쓰고 출처 표의 `backs`에 적는다(약 11초, 메모리 0.7 GB) |
| `app_cards.py render \| compare \| specs --kind K (--ids a,b \| --all) [--lang en,ko]` | 앱의 카드 틀(프리팹)·그림·글꼴로 카드 앞면을 그린다(`app_render.py`가 Unity UI 배치와 TextMeshPro SDF 글자를 흉내 낸다). 칸 안 배치는 실물 카드처럼(아이콘 줄, 문장 앞뒤 아이콘, —OR— 구분). 영어는 앱 문구에 에셋 `cards/app/en_text.json`의 인쇄판 교정을, 한국어는 `ko_text.json`(한글판 카드 사진에서 받아 적은 문구)을 쓰고 앱의 한국어 번역은 쓰지 않는다. 한글은 NanumBarunGothic(본문 보통·제목과 Intrigue·Conflict 굵게). `render`는 에셋 `cards/app/<언어>/<manifest 경로>.webp`에, `compare`는 스캔과 나란히 놓은 비교표를 쓴다 |
| `app_board.py inputs \| render [--lang en,ko] [--ids a,b] \| compare --out DIR [--prototype DIR]` | 플레이 UI의 보드 칸 그림(location 타일)을 앱의 3D 보드(Addressables 장면 `Playmat`)에서 그린다. `inputs`는 UnityPy로 장면의 Uprising 칸 23개 트리(위치·회전·크기, 켜짐, 메시·재질·TextMeshPro 글자)와 그 메시(Unity 좌표)·텍스처·TMP 글꼴을 `render/boardspaces/`에 꺼낸다(약 4초, 메모리 1.2 GB). `render`는 UnityPy 없이 numpy·Pillow로 칸마다 메시를 z 순서로 겹쳐 그리고(1단위 256 px, 2배 슈퍼샘플) 액자 밖은 투명하게 에셋 `cards/app/<언어>/<manifest 경로>.webp`에 쓴다. 그림은 인쇄판 상태로 고정한다(2026-10-08 사용자 승인): 엔진이 교전 칸이라 하는 곳에 X, 벌레 사선과 보너스 스파이스 숫자는 숨김, Swordmaster 보상 아이콘은 채움. 한국어판은 3D 글자 "OR"만 "또는"(NanumBarunGothic Bold)으로 바꾸고 앱의 한국어 번역은 쓰지 않는다. 앱에 없는 Tuek's Sietch(Bloodlines)는 같은 구조인 앱 Hagga Basin의 배치와 Spice Trade 액자에 인쇄 타일의 그림을 넣어 조립한다. 출처는 `cards/app/location_sources.json`, `compare`는 스캔·앱 타일(영·한)·이전 렌더를 무리별로 나란히 놓는다 |
| `app_leaders.py inputs [--measure-only] \| render [--lang en,ko] [--ids a,b] \| compare --out DIR` | Uprising 지도자 카드 10장의 앞면을 앱 조각으로 그린다. 앱에는 지도자 카드가 없고, 지도자 화면들이 인쇄판 그림을 두 겹으로 갖고 있다: 배경을 지운 인물 `leader_ConflictWinner_<id>`(스캔보다 1.1~1.6배 촘촘함)와 인물을 지운 배경 `frame_DeferredAbility_BG<id>`(256×139, 약 6배로 키움). `inputs`는 이 그림들과 Signet Ring 고리(`UI_crd_ActionIcon_SignetRing`)·지형선 텍스처(`bg_TopoLines_1`)를 `render/leaders/`에 꺼낸다(UnityPy). `inputs --measure-only`는 두 그림이 스캔의 어디에 놓이는지 마스크 NCC로 잰다(약 2분, 결과는 파일 안 `PLACEMENT`, 인물 0.97~0.99·배경 0.92~0.99). `render`는 UnityPy 없이 그림을 그 자리에 놓고, 앱에 없는 카드 틀(이름 띠와 복잡도 육각형, 가문 띠, DECK/DISCARD 탭, 금색 능력 칸, 검은 Signet 칸, 샤담의 빨간 고리, 스타반의 빨간 Limited Allies 칸, 페이드의 훈련 트랙)을 스캔(1460×1020)에서 잰 대로 그린다. 앱 그림은 인쇄판보다 밝고 회색빛이라 두 그림 모두 영어 스캔에서 그 그림이 보이는 곳에 맞춘 색 변환으로 인쇄판 색에 맞춘다(`print_grade`). 배경은 키운 뒤 부드럽게 하고 선명하게 해 인쇄판의 낟알을 얹는다(그래도 1:1에서는 인쇄판보다 흐리다). 인물이 보이는 곳에서 곧게 잘린 곳(일곱 장의 아래 끝, 스타반 의자의 오른쪽)은 끝 줄을 거울로 이어 그리고, 배경 아래는 거울로 이어 두 칸 사이 틈에 그림이 끝까지 보인다. 탭의 위아래 색은 카드마다 영어 스캔에서 읽는다(`print_shades`). 스캔에서는 이런 수치만 읽고 그림은 앱 것을 쓴다. 그래서 `display/leader_layout.py`의 백분율(페이드의 `FEYD_TRACK_BOXES`)이 그대로 맞는다. 칸 안 배치는 실물처럼(아이콘 줄, 문장 옆 큰 아이콘, 문장 속 작은 아이콘, 인쇄판 줄바꿈). 영어는 앱 문구에 에셋 `cards/app/en_text.json`의 인쇄판 교정(레이디 제시카의 뒤집기 문장, 대모 제시카의 능력, 거니의 6*과 각주)을, 한국어는 `names_ko`·`leaders_ko`와 한글판 사진에서 읽은 가문·탭 낱말만 쓰고 앱의 한국어 번역은 쓰지 않는다. 대모 제시카는 한국어 카드가 없어 영어 앞면만 만든다. 출력은 에셋 `cards/app/<언어>/uprising/leader/<인쇄 이름>.webp`, 출처는 `cards/app/leader_sources.json`, `compare`는 스캔·앱 앞면(영·한)을 지도자마다 나란히 놓는다 |
| `show_text.py <loc 키 \| 키의 일부> [--ko]` | 로컬 추출본의 앱 문구를 키로 찾아 그대로 출력한다(영어, `--ko`면 한국어도). 규칙 문서는 loc 키만 인용하므로, 판정을 원문과 한 단어씩 대조할 때 쓴다. 문구는 화면에만 나오고 어디에도 저장하지 않는다 |
| `ANALYSIS.md` | IL2CPP 코드를 읽는 관례(인자 레지스터, `List<T>`·배열·문자열 배치, 정적 필드, 런타임 helper)와 추출 데이터 설명 |

예:

```bash
uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone \
    python extract.py ../../assets/reference/dwgr-arrakeen-scouts/data
uv run --no-project --with capstone --with UnityPy --with TypeTreeGeneratorAPI \
    python il2dis.py "ScheduleController::pickEvents"
```

## Steam Dune: Imperium 앱

Steam 앱 1689500(`com.direwolfdigital.dune`)은 Unity 6000.3 IL2CPP 빌드이고 규칙 엔진이 클라이언트에 들어 있다.
- `worm.canis.abilities.*`: 카드·칸·교전·계약 능력. 확장별 하위 네임스페이스(`.Uprising`, `.RiseOfIx`, …)
- `worm.canis.actions.*`, `worm.canis.archetypes.*`(카드·칸 정의), `worm.canis.ai.*`(공식 AI), `HagalAbilities`(House Hagal)
- 기반 엔진 `Canis.*`(어셈블리 `Canis.dll`): 행동·비용·되돌리기·선택

규칙 출처로서의 자리(2026-10-03 사용자 결정):
- 공식 룰북·FAQ가 우선이다. 앱 구현은 Dire Wolf가 디지털판에서 어떻게 처리했는지 보여 주는 보조 증거다.
- 주로 공식 문서가 답하지 않는 곳(`docs/rules/open-questions.md`)에 쓴다. 기록할 때는 공식 판정과 구분해 "앱 구현"으로 적고 앱 버전과 메서드 이름을 함께 남긴다.
- 디지털판은 실물판과 다르게 처리했거나 버그가 있을 수 있다.

```bash
cd scripts/dwgr
IL2CPP_APP=dune uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone \
    python il2dump.py ../../assets/reference/dune-steam-app/<build-guid>/dump --asm \
    worm-canis.dll worm-client.dll Canis.dll Canis.Command.dll core-canis.dll boardgames.dll
IL2CPP_APP=dune uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone \
    python il2dis.py "SwordmasterUprisingSpaceAbility::Cost"
```

`extract.py`는 Game Room 전용이다(TypeTreeGeneratorAPI가 metadata v39를 읽는지는 확인하지 않았다).

## 앱이 업데이트되면

1. 새 폴더에 다시 추출한다. 예: `.../dwgr-arrakeen-scouts/data-<새 build-guid>`, `.../dune-steam-app/<새 build-guid>/dump`.
2. 이전 추출과 `diff -r`로 비교한다. 정의(`spice_mb/*Definition.json`)나 일정 풀(`schedules.json`)이 바뀌었으면 엔진 규칙 변경으로 다룬다. Steam 앱의 기록은 그 판정이 근거로 삼은 메서드를 새 빌드에서 다시 확인한다.
3. 알려진 한계:
   - `il2meta.py`는 metadata v31·v39와 x86_64 dylib(`__TEXT` vmaddr 0, chained fixups 형식 2·6)만 다룬다. 어긋나면 import할 때 분명한 오류로 멈춘다.
   - `il2dis.py`의 `rt:` 런타임 helper 이름표(`HELPERS_BY_BUILD`)는 build `84d64e1237b54105aee1940811cd9e43`(Game Room), `a6cb3f9216f9489d803b76004ec9af53`(Steam 4.1.1.1804), `dad97e2021144d45b5b4f022e07bd3b3`(Steam 4.1.2.1808, 같은 주소)에만 있다. 다른 빌드는 이름표 없이 주소만 보이고, `rt:object_new` 뒤의 `~` 추적도 끊긴다.
   - 두 build를 비교할 때는 `--asm` 덤프에서 주소·`rt:`·`~` 주석·stub 주소를 지운 뒤 메서드별로 대조한다. 4.1.1.1804 → 4.1.2.1808은 이렇게 바뀐 메서드가 7개(재접속 `Canis.actions.ResumePlayer`, 클라이언트 버전, 카드 드래그·진영 선택 UI)였고 `worm.canis.*` 규칙 코드는 그대로였다.
   - 새 빌드의 helper는 이렇게 다시 찾는다. 이름 없는 호출 대상을 호출 횟수로 줄 세우고, 본문 모양(`call; mfence; ret`, `jmp` 한 줄, `mov esi, esi; jmp`)과 호출부(`test byte [klass+0x135]`, `cmp idx, [arr+0x18]; jae`)를 이전 빌드와 맞춘다. 예외 helper는 호출 사슬이 불러오는 클래스 이름 문자열(`NullReferenceException`, `IndexOutOfRangeException`)로 확인한다.

## 확인 기록

2026-09-28, build `84d64e1237b54105aee1940811cd9e43`(Unity 2022.3.62f2, 2026-09-26 설치).
- 새 uv 임시 환경에서 `extract.py`로 다시 추출한 결과가 앞선 탐색 스크립트의 결과와 파일 단위로 같았다.
- 자동으로 찾은 표 위치가 손으로 찾은 값과 같았다: CodeRegistration `0x2a2bb50`, codeGenModules `0x2c4e880`(113개), MetadataRegistration `0x2b68238`.

2026-10-03, Steam Dune: Imperium 4.1.1.1804, build `a6cb3f9216f9489d803b76004ec9af53`(Unity 6000.3.17f1, Steam buildid 25636255, 2026-10-03 업데이트).
- metadata v39, 인덱스 폭: 타입 정의 2바이트, generic container 2바이트, 타입 4바이트, 파라미터 4바이트. CodeRegistration `0x5ab0b20`, codeGenModules `0x5f151a0`(143개), MetadataRegistration `0x5d8f610`. 메서드 181,071개 중 162,549개에 주소가 있다.
- v39 지원을 넣은 뒤에도 Game Room build의 `il2fields`·`il2xref` 출력이 이전과 같았다. `il2dis` 출력은 bss 바이트 두 줄만 달라졌다(이전에는 파일 밖 바이트를 읽었고 이제 0으로 읽는다).
- 문자열 기본값의 길이를 부호 있는 압축 정수로 읽게 고쳤다. 전에는 길이가 두 배로 읽혀 뒤 문자열이 붙었다.

2026-10-03 05:13, Steam 앱이 4.1.2.1808, build `dad97e2021144d45b5b4f022e07bd3b3`(Steam buildid 25682137)로 업데이트됐다. 표 위치는 그대로였고 메서드가 하나 늘었다(181,072개 중 162,550개에 주소). helper 주소도 그대로다.
