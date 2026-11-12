# 자체 그림 (`scripts/own_pictures/`)

서버가 기본으로 보여 주는 그림(`--pictures own`, 공개 빌드와 같다)은 `src/dune_imperium/server/static/pictures/`에 있고,
거의 전부 이 폴더의 코드가 그린다. 그림을 고칠 때는 SVG 파일이 아니라 그 그림을 그리는 코드를 고치고
스크립트를 다시 돌린다. 원본 그림을 따라 그리거나 자동으로 벡터화하지 않는다.

| 그림 | 그리는 곳 | 고치는 법 |
|---|---|---|
| `icons/` 아이콘, `log/` 기록 아이콘, `faces/`의 표시(세력 배지, Agent 표시, 전투 표시, Mentat 등) | `icon_drawing/draw.py` | `icons.py` 실행 |
| `tokens/` 말·토큰 | `icon_drawing/pieces.py` | `icons.py` 실행 |
| `tokens/back_*` 카드 뒷면 | `icon_drawing/backs.py` | `icons.py` 실행 |
| `board/` 게임판, Ix 조각, 보드 타일(`_ko`는 한국어판 이름) | `board.py` | `board.py` 실행 |
| `icons/solari.svg`, `faces/specimen_cube.svg` | 손으로 쓴 SVG | 파일을 직접 고친다 |

카드면은 그림 파일이 아니다. 화면이 `static/card_faces.js`와 `style.css`로 그리고, 카드마다 인쇄된
문구와 아이콘 배치는 `src/dune_imperium/display/card_faces.json`에 있다.

`icon_drawing/`의 나머지 모듈은 그림 조각이다.

- `marks.py`: 네 세력 표시
- `shapes.py`: 말과 아이콘이 함께 쓰는 모양
- `extras.py`: Intrigue 표시, Victory point, Signet Ring
- `extras2.py`: 물음표, 전투 아이콘과 그 표시, 교차한 칼, Freighter, Shield Wall, Intrigue 빼앗기, Tech 뒤집기
- `extras3.py`: Ornithopter, 연구 현미경, 단순한 Signet Ring, Tech 톱니, Control 깃발, Unload의 두 카드
- `pixels.json`: 원래 아이콘들의 픽셀 크기. 그림이 원래 아이콘과 같은 자리에 같은 크기로 놓이게 한다.

## 그림을 고치는 순서

1. 그림 코드를 고친다.
2. 다시 그린다. 바뀐 파일만 새로 쓴다.

   ```bash
   uv run python scripts/own_pictures/icons.py
   ```

3. 아이콘을 고쳤으면 게임판도 다시 그린다. 게임판이 아이콘을 안에 품고 있다.

   ```bash
   uv run python scripts/own_pictures/board.py
   ```

4. 확인한다. `--check`는 아무것도 쓰지 않고, 낡은 그림이 있으면 실패한다.
   `tests/server/test_own_pictures.py`도 같은 검사를 한다.

   ```bash
   uv run python scripts/own_pictures/icons.py --check
   uv run python scripts/own_pictures/board.py --check
   uv run pytest -q tests/server/test_own_pictures.py
   ```

5. 화면에서 본다: `uv run dune-imperium-server`(기본이 우리 그림이다).

그림마다 `index.json`에 설명이 한 줄씩 있다. `icons.py`가 그린 그림의 설명은 그 코드에서 온다.
