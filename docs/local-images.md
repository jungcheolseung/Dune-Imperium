# 로컬 UI 이미지

카드·보드·아이콘·토큰 원본은 저작권 때문에 이 저장소에 넣지 않는다. 플레이 서버는
아래 네 위치를 있을 때만 서빙하고, 없으면 텍스트(및 텍스트 보드 목록, 그려 넣은 좌석 토큰)로
대체한다. 소유자의 머신에서는 비공개 `Dune-Imperium-assets` 저장소를 옆에
clone해 저장소 루트의 `assets` symlink 하나로 연결한다(그 README 참고).

- `assets/cards/` (또는 `DUNE_IMPERIUM_CARD_IMAGE_DIR`): 카드 스캔 체크아웃.
  `cards/manifest.json`이 `<세트>/<종류>/<인쇄 카드명>.<확장자>` 파일과 엔진
  content ID를 잇는 유일한 매핑이고, 서버가 시작 시 읽어 존재하는 파일만
  연결한다(`ko/` 스캔이 있으면 파일 단위로 우선, 없으면 `en/`). 같은 언어 안에서는
  Steam 앱의 카드 틀로 그린 `app/<언어>/` 앞면(`scripts/dwgr/app_cards.py render`)을
  스캔보다 먼저 쓴다. 다만 보드 스캔 위에 놓는 조각(Tuek's Sietch 같은 지도자
  타일, Immortality의 Research Station 덮개)은 인쇄 타일 모양의 상자에 맞아야 해서
  스캔만 쓴다(카탈로그 `tile_image`, 팝오버는 그대로 `image`).
  `uv run scripts/fetch_card_images.py`는 manifest가 기록한 출처에서 빠진
  파일만 내려받는다.
- `assets/icons/` (또는 `DUNE_IMPERIUM_ICON_DIR`): 게임 아이콘 투명 PNG 46장.
  공식 Uprising Main Rulebook의 Icon Guide(20쪽)와 Agent 아이콘(9쪽)에서
  `uv run --with pymupdf --with pillow scripts/extract_rulebook_icons.py`로 잘라낸 뒤,
  설치된 Steam 앱이 있으면 `scripts/dwgr/app_assets.py icons`가 같은 그림의 앱판으로
  덮어쓴다(이름 목록은 `dune_imperium.display.icons`).
- `assets/tokens/` (또는 `DUNE_IMPERIUM_TOKEN_DIR`): 좌석 색상별 Combat marker
  그림 8장(`strength_<green|red|yellow|blue>.png`과 `+20` 면
  `strength_<색>_plus20.png`; 이름 규칙은 `dune_imperium.display.token_images`).
  보드 하단 Combat track의 전투력 토큰이 이 그림으로 바뀌고, 전투력이 20을
  넘으면 `+20` 면으로 뒤집힌다[Main p. 12]. 한 색의 두 면이 다 있어야 그 좌석에
  적용된다. 같은 폴더의 `shield_wall.png`는 Shield Wall 토큰으로, 제거되기 전까지
  Spice Refinery 아래의 표시된 위치에 놓인다[Main p. 4]. 보드의 좌석 말(Agent·Spy·
  Control marker·병력과 영향력 큐브·모래벌레·High Council 원판, 점수와 Bene Tleilax
  트랙의 player disc)은 `<말>_<색>.png` 그림이 네 색 다 있으면 그 그림으로,
  없으면 단색 도형으로 그린다(`scripts/dwgr/app_assets.py pieces`). 출처는 에셋 저장소 README 참고.
- `assets/board/map.jpg` (또는 `DUNE_IMPERIUM_BOARD_IMAGE`): 4인 보드 스캔. hotspot·관측소
  좌표(`dune_imperium.display.board_layout`)는 소유자의 6012×6005 정사각형
  스캔 기준 퍼센트 값이라 다른 프레이밍의 스캔은 재측정이 필요하다.
