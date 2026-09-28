# Dire Wolf Game Room 추출 도구 (`scripts/dwgr/`)

Steam의 **Dire Wolf Game Room**에 들어 있는 Dune: Imperium 컴패니언(내부 이름 `grm.companions.spice`)에서 다음을 꺼내는 도구다.
- **Arrakeen Scouts**(아라킨 스카웃) 모드의 정의 데이터, 문구, UI 트리
- 일정 생성 코드를 읽는 IL2CPP 분석 도구

공식 룰북이 없는 모드라서 이 추출이 규칙 출처다. 설계와 쓰임새는 [`docs/arrakeen-scouts-design.md`](../../docs/arrakeen-scouts-design.md)(M15)에 있다.

## 출력은 어느 저장소에도 넣지 않는다

- 추출 결과(문구, 정의, UI 트리)와 분석 결과는 Dire Wolf Digital의 저작물에서 나온 것이다. 공개 저장소인 이 저장소에는 넣지 않는다. 이 저장소에는 이름·수치·의역만 둔다.
- 비공개 에셋 저장소의 이력에도 넣지 않는다. 에셋 저장소에는 게임에 쓰이는 에셋만 남긴다(2026-09-28 사용자 결정).
- 출력의 기본 자리는 에셋 체크아웃의 `reference/dwgr-arrakeen-scouts/`다. 에셋 `.gitignore`가 이 폴더를 빼므로 파일은 그 기기에만 남는다.
- 다른 기기에서는 앱을 설치하고 다시 추출한다(약 5초).
- 2026-09-27~28 분석 결과는 Mac mini의 그 폴더 `analysis/`에만 있다: 코드 분석, 항목별 해석, 반박 검증, 확률 스크립트, 한국어 요약 `report-ko.md`.

## 준비

프로젝트 의존성이 아니다. `uv run --no-project`로 필요한 패키지만 임시 환경에 얹는다.

```bash
cd scripts/dwgr
uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone python il2meta.py
```

`il2meta.py`를 그냥 실행하면 찾은 표의 위치와 크기를 출력한다(build-guid, CodeRegistration, codeGenModules, MetadataRegistration, 메서드 수). 앱 위치는 `DWGR_APP`(`.app`의 `Contents` 폴더)로 바꿀 수 있다. 기본값은 `~/Library/Application Support/Steam/steamapps/common/DireWolfGameRoom/DireWolfGameRoom.app/Contents`다.

## 도구

| 파일 | 하는 일 |
|---|---|
| `extract.py <out_dir>` | 한 번에 전부 추출한다. `manifest.json`(build-guid, Unity 버전, 원본 파일 sha256), `spice_mb/*.json`(모든 spice MonoBehaviour·ScriptableObject), `schedules.json`(일정 풀 8개), `loc/<lang>.json`(13개 언어, spice 키와 프리팹이 쓰는 키), `text_sprites.json`, `beat_prefabs.json`, `beats_bundle.txt`(정의별로 모아 읽는 파일) |
| `il2meta.py` | IL2CPP global-metadata v31과 Mach-O를 읽어 메서드 주소·제네릭 인스턴스·필드 오프셋·enum 값·지연 초기화 전역(TypeInfo·MethodRef·문자열 리터럴)을 푼다. 표의 위치는 검색으로 찾는다 |
| `il2dis.py <메서드 이름 일부 \| 0x주소>` | 메서드의 x86-64 디스어셈블에 호출 대상·메타데이터·float 상수 주석을 단다(capstone) |
| `il2fields.py <타입 전체 이름 \| 접두사*>` | 타입의 필드 오프셋·타입·enum 값과 메서드 주소 |
| `il2xref.py <메서드 이름 일부 \| 0x주소>` | 그 메서드를 직접 부르는 곳(E8/E9 rel32) |
| `ANALYSIS.md` | IL2CPP 코드를 읽는 관례(인자 레지스터, `List<T>`·배열·문자열 배치, 정적 필드, 런타임 helper)와 추출 데이터 설명 |

예:

```bash
uv run --no-project --with UnityPy --with TypeTreeGeneratorAPI --with capstone \
    python extract.py ../../assets/reference/dwgr-arrakeen-scouts/data
uv run --no-project --with capstone --with UnityPy --with TypeTreeGeneratorAPI \
    python il2dis.py "ScheduleController::pickEvents"
```

## 앱이 업데이트되면

1. 새 폴더에 다시 추출한다. 예: `.../dwgr-arrakeen-scouts/data-<새 build-guid>`.
2. 이전 추출과 `diff -r`로 비교한다. 정의(`spice_mb/*Definition.json`)나 일정 풀(`schedules.json`)이 바뀌었으면 엔진 규칙 변경으로 다룬다.
3. 알려진 한계:
   - `il2meta.py`는 metadata v31과 `vmaddr == fileoff`인 thin x86_64 dylib을 전제한다. 어긋나면 import할 때 분명한 오류로 멈춘다.
   - `il2dis.py`의 `rt:` 런타임 helper 이름표(`HELPERS_BY_BUILD`)는 build `84d64e1237b54105aee1940811cd9e43`에만 있다. 다른 빌드는 이름표 없이 주소만 보인다.

## 확인 기록

2026-09-28, build `84d64e1237b54105aee1940811cd9e43`(Unity 2022.3.62f2, 2026-09-26 설치).
- 새 uv 임시 환경에서 `extract.py`로 다시 추출한 결과가 앞선 탐색 스크립트의 결과와 파일 단위로 같았다.
- 자동으로 찾은 표 위치가 손으로 찾은 값과 같았다: CodeRegistration `0x2a2bb50`, codeGenModules `0x2c4e880`(113개), MetadataRegistration `0x2b68238`.
