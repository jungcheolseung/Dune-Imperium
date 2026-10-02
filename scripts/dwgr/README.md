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
| `il2dump.py <out_dir> [--asm] [어셈블리 ...]` | 이름 수준 덤프. 어셈블리별 `<이름>.cs`(타입·부모·필드 오프셋과 static/const·기본값·메서드 시그니처와 주소), 전체 `methods.tsv`, `strings.tsv`(문자열 리터럴), `manifest.json`(build-guid, 앱·Unity 버전, sha256). `--asm`이면 `asm/<어셈블리>/<타입>.asm`에 최상위 타입마다(중첩 타입 포함) 모든 메서드의 `il2dis` 출력을 쓴다. 바이너리를 다시 읽지 않고 grep할 수 있다(Steam 앱 6개 어셈블리 약 30초, 144MB) |
| `il2dis.py <메서드 이름 일부 \| 0x주소>` | 메서드의 x86-64 디스어셈블에 호출 대상·메타데이터·float 상수 주석을 단다(capstone). `~`로 시작하는 주석은 레지스터를 따라가 붙인 이름이다: `this`와 알려진 필드에서 읽은 객체의 필드(`~Type.field`), 정적 필드(`~static Type.field`), 가상 호출 슬롯(`~vslot N Type::Method`). 분기 합류점에서는 모든 경로가 같은 타입일 때만 이어 가고, 가상 슬롯은 정적 타입(기반 클래스일 수 있음)의 메서드 이름이다 |
| `il2fields.py <타입 전체 이름 \| 접두사*>` | 타입의 필드 오프셋·타입·enum 값과 메서드 주소 |
| `il2xref.py <메서드 이름 일부 \| 0x주소>` | 그 메서드를 직접 부르는 곳(E8/E9 rel32) |
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
   - `il2dis.py`의 `rt:` 런타임 helper 이름표(`HELPERS_BY_BUILD`)는 build `84d64e1237b54105aee1940811cd9e43`(Game Room)과 `a6cb3f9216f9489d803b76004ec9af53`(Steam 4.1.1.1804)에만 있다. 다른 빌드는 이름표 없이 주소만 보인다.
   - 새 빌드의 helper는 이렇게 다시 찾는다. 이름 없는 호출 대상을 호출 횟수로 줄 세우고, 본문 모양(`call; mfence; ret`, `jmp` 한 줄, `mov esi, esi; jmp`)과 호출부(`test byte [klass+0x135]`, `cmp idx, [arr+0x18]; jae`)를 이전 빌드와 맞춘다. 예외 helper는 호출 사슬이 불러오는 클래스 이름 문자열(`NullReferenceException`, `IndexOutOfRangeException`)로 확인한다.

## 확인 기록

2026-09-28, build `84d64e1237b54105aee1940811cd9e43`(Unity 2022.3.62f2, 2026-09-26 설치).
- 새 uv 임시 환경에서 `extract.py`로 다시 추출한 결과가 앞선 탐색 스크립트의 결과와 파일 단위로 같았다.
- 자동으로 찾은 표 위치가 손으로 찾은 값과 같았다: CodeRegistration `0x2a2bb50`, codeGenModules `0x2c4e880`(113개), MetadataRegistration `0x2b68238`.

2026-10-03, Steam Dune: Imperium 4.1.1.1804, build `a6cb3f9216f9489d803b76004ec9af53`(Unity 6000.3.17f1, Steam buildid 25636255, 2026-10-03 업데이트).
- metadata v39, 인덱스 폭: 타입 정의 2바이트, generic container 2바이트, 타입 4바이트, 파라미터 4바이트. CodeRegistration `0x5ab0b20`, codeGenModules `0x5f151a0`(143개), MetadataRegistration `0x5d8f610`. 메서드 181,071개 중 162,549개에 주소가 있다.
- v39 지원을 넣은 뒤에도 Game Room build의 `il2fields`·`il2xref` 출력이 이전과 같았다. `il2dis` 출력은 bss 바이트 두 줄만 달라졌다(이전에는 파일 밖 바이트를 읽었고 이제 0으로 읽는다).
- 문자열 기본값의 길이를 부호 있는 압축 정수로 읽게 고쳤다. 전에는 길이가 두 배로 읽혀 뒤 문자열이 붙었다.
