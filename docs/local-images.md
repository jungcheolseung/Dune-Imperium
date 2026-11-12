# 로컬 UI 이미지

카드·보드·아이콘·토큰 원본은 저작권 때문에 이 저장소에 넣지 않는다. 플레이 서버는 기본으로
프로젝트가 직접 그린 그림을 보인다(아래 "우리 그림"; 2026-11-11부터 기본). 카드 그림이나 보드 스캔 같은
그림 폴더를 가진 사람은 서버를 `--pictures assets`(또는 `DUNE_IMPERIUM_PICTURES=assets`, 서버 런처에서는
**그림 폴더**)로 띄워 그 그림을 쓴다. 그때 서버는 아래 위치에 있는 그림을 쓰고, 없는 것은 우리 그림으로
채운다. 소유자의 머신에서는 비공개 `Dune-Imperium-assets` 저장소를 옆에 clone해 저장소 루트의 `assets`
symlink 하나로 연결한다(그 README 참고).

- `assets/cards/` (또는 `DUNE_IMPERIUM_CARD_IMAGE_DIR`): 카드 스캔 체크아웃.
  `cards/manifest.json`이 `<세트>/<종류>/<인쇄 카드명>.<확장자>` 파일과 엔진
  content ID를 잇는 유일한 매핑이고, 서버가 시작 시 읽어 존재하는 파일만
  연결한다(`ko/` 스캔이 있으면 파일 단위로 우선, 없으면 `en/`). 같은 언어 안에서는
  소유자가 따로 만든 `app/<언어>/` 앞면을 스캔보다 먼저 쓴다. 다만 보드 스캔 위에 놓는 조각(Tuek's Sietch 같은 지도자
  타일, Immortality의 Research Station 덮개)은 인쇄 타일 모양의 상자에 맞아야 해서
  스캔만 쓴다(카탈로그 `tile_image`, 팝오버는 그대로 `image`).
- `assets/icons/` (또는 `DUNE_IMPERIUM_ICON_DIR`): 게임 아이콘 투명 PNG 46장.
  공식 Uprising Main Rulebook의 Icon Guide(20쪽)와 Agent 아이콘(9쪽)에서
  잘라낸 것이다(이름 목록은 `dune_imperium.display.icons`).
- `assets/tokens/` (또는 `DUNE_IMPERIUM_TOKEN_DIR`): 좌석 색상별 Combat marker
  그림 8장(`strength_<green|red|yellow|blue>.png`과 `+20` 면
  `strength_<색>_plus20.png`; 이름 규칙은 `dune_imperium.display.token_images`).
  보드 하단 Combat track의 전투력 토큰이 이 그림으로 바뀌고, 전투력이 20을
  넘으면 `+20` 면으로 뒤집힌다[Main p. 12]. 한 색의 두 면이 다 있어야 그 좌석에
  적용된다. 같은 폴더의 `shield_wall.png`는 Shield Wall 토큰으로, 제거되기 전까지
  Spice Refinery 아래의 표시된 위치에 놓인다[Main p. 4]. 보드의 좌석 말(Agent·Spy·
  Control marker·병력과 영향력 큐브·모래벌레·High Council 원판, 점수와 Bene Tleilax
  트랙의 player disc)은 `<말>_<색>.png` 그림이 네 색 다 있으면 그 그림으로,
  없으면 단색 도형으로 그린다. 출처는 에셋 저장소 README 참고.
- `assets/board/uprising.jpg` (또는 `DUNE_IMPERIUM_BOARD_IMAGE`): Uprising 4인 보드 스캔. hotspot·관측소
  좌표(`dune_imperium.display.board_layout`)는 소유자의 6012×6005 정사각형
  스캔 기준 퍼센트 값이라 다른 프레이밍의 스캔은 재측정이 필요하다. 2026-11-06 전 이름은 `map.jpg`였다.
- `assets/board/uprising_ko.jpg` (또는 `DUNE_IMPERIUM_BOARD_IMAGE_KO`): 같은 보드에 장소 이름만 한국어로 바꾼 그림
  (소유자가 만듦, 6012×6005로 같은 그림). 화면이 한국어일 때 이 그림을, 영어일 때 위 스캔을 보인다
  (2026-11-06 사용자 요청). 없으면 두 언어 모두 스캔. 원판 보드(`imperium.jpg`)에는 아직 한국어 그림이 없다.

## 우리 그림 (기본)

공개 저장소에는 위 그림이 하나도 없다. 대신 프로젝트가 직접 그린 그림(SVG)이 코드와 함께
`src/dune_imperium/server/static/pictures/`에 있다(계획). 모든 카드·보드·말·아이콘을 덮으므로
서버의 기본(`--pictures own`)은 이 그림만 보이는 것이다. 위 그림 폴더가 있는 기기에서도 `--pictures assets`를
주지 않으면 그 폴더를 쓰지 않는다. `--pictures assets`로 띄우면 그 폴더에 있는 그림을 먼저, 없는 것은 우리 그림을 보인다.
그림 없는 카드는 이름만 적힌 글자 카드 대신, 실물 카드 앞면이 보이는 내용(문구와 칸 안의 아이콘)을 그림 없이 다시 그린
앞면으로 나온다(`display/card_faces.json`, `static/card_faces.js`; Imperium·틀레이락스·책략·Conflict 카드, 계약·기술 타일, 지도자).
아이콘 53장과 행동 기록의 그림 26장도 우리 그림이다(`pictures/icons/`, `pictures/log/`).

