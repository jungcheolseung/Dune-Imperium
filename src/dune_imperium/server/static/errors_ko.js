"use strict";

/* Korean for the server's error messages (server/sessions.py and
   persistence.py send English in an HTTP error's `detail`). Keyed by the
   exact English sentence; SERVER_ERROR_KO_PATTERNS covers the formatted ones
   as [RegExp source, Korean]. In the Korean, $N is group N as written and #N
   is group N plus one: a seat's number in a message is the engine's
   zero-based id, but the page names the seat by its visible number
   (플레이어1). A message with no entry stays English. The bodies are JSON so
   tests/server/test_i18n.py can read them. */
const SERVER_ERROR_KO = {
  "the game advanced past the submitted revision": "그 사이 게임이 먼저 진행되어 화면이 최신 상태가 아닙니다",
  "the game was taken back since the submitted undo generation": "그 사이 게임이 되돌려져 화면이 최신 상태가 아닙니다",
  "this operation needs the host's admin key": "이 작업은 호스트의 관리자 링크로만 할 수 있습니다",
  "an open server has no admin key to log in with": "열린 서버에는 로그인에 쓸 관리자 키가 없습니다",
  "game seed must not be negative": "게임 시드는 음수일 수 없습니다",
  "policy seed must not be negative": "AI 시드는 음수일 수 없습니다",
  "this server has no search AI": "이 서버에는 탐색 AI가 없습니다",
  "log cursor is out of range": "로그 위치가 범위를 벗어났습니다",
  "review step is out of range": "검토 위치가 범위를 벗어났습니다",
  "seat does not identify a configured player": "그 자리는 이 게임의 플레이어가 아닙니다",
  "only a human seat may be read or acted for": "사람 플레이어의 자리만 볼 수 있고 행동할 수 있습니다",
  "claiming a seat only applies to a remote server": "자리에 참여하는 기능은 원격 서버에서만 쓸 수 있습니다",
  "releasing a seat only applies to a remote server": "자리를 해제하는 기능은 원격 서버에서만 쓸 수 있습니다",
  "starting a waiting room only applies to a remote server": "대기실 시작은 원격 서버에서만 쓸 수 있습니다",
  "drawing the seats at the start only applies to a remote server": "시작할 때 자리를 정하는 방은 원격 서버에서만 만들 수 있습니다",
  "drawing the seats at the start needs a human seat": "시작할 때 자리를 정하는 방에는 사람 자리가 하나 이상 있어야 합니다",
  "the game has not started yet": "게임이 아직 시작되지 않았습니다",
  "this game is not waiting for its start": "이 게임은 시작을 기다리는 방이 아닙니다",
  "only a player in the room or the host may start the game": "대기실에 참여한 사람이나 호스트만 게임을 시작할 수 있습니다",
  "every human seat must be taken before the start": "사람 자리가 모두 차야 시작할 수 있습니다",
  "only a client holding a seat may read this before the game ends": "게임이 끝나기 전에는 자리에 참여한 사람만 볼 수 있습니다",
  "the current decision belongs to another seat": "지금 결정은 다른 플레이어의 몫입니다",
  "action index is out of range": "행동 번호가 범위를 벗어났습니다",
  "replay review opens after the game finishes": "리플레이 검토는 게임이 끝난 뒤에 열립니다",
  "a player name must not be empty": "이름을 비워 둘 수 없습니다",
  "exactly one seat assignment per player is required": "플레이어마다 배정이 하나씩 있어야 합니다",
  "only four-player games are currently supported": "지금은 4인 게임만 지원합니다",
  "the Tech Module requires the Bloodlines expansion": "기술 모듈은 혈통 확장이 있어야 합니다",
  "the Go to 11 variant requires the Immortality expansion": "11점을 향해 옵션은 불멸 확장이 있어야 합니다",
  "unreadable save file": "읽을 수 없는 저장 파일",
  "a save document must be a JSON object": "저장 파일의 형식이 올바르지 않습니다",
  "not a dune-imperium save document": "이 게임의 저장 파일이 아닙니다",
  "the replayed save does not reproduce its recorded state hash": "저장본을 다시 재생한 결과가 기록된 상태와 다릅니다"
};

const SERVER_ERROR_KO_PATTERNS = [
  [
    "^unknown AI pace (.+)$",
    "알 수 없는 AI 진행 속도입니다: $1"
  ],
  [
    "^unknown save base game (.+)$",
    "저장 파일의 기본 판을 알 수 없습니다: $1"
  ],
  [
    "^unknown game: (.+)$",
    "알 수 없는 게임입니다: $1"
  ],
  [
    "^unknown save: (.+)$",
    "알 수 없는 저장본입니다: $1"
  ],
  [
    "^unknown seat assignment: (.+)$",
    "알 수 없는 플레이어 유형입니다: $1"
  ],
  [
    "^a split search seat is not a table seat: (.+)$",
    "나눠 지정한 탐색 좌석은 테이블 자리로 쓸 수 없습니다: $1"
  ],
  [
    "^a search seat with options is not a table seat: (.+)$",
    "측정용 옵션을 붙인 탐색 좌석은 테이블 자리로 쓸 수 없습니다: $1"
  ],
  [
    "^an older-network seat is not a table seat: (.+)$",
    "옛 버전 망 좌석은 테이블 자리로 쓸 수 없습니다: $1"
  ],
  [
    "^a player name may have at most (\\d+) characters$",
    "이름은 $1자까지 쓸 수 있습니다"
  ],
  [
    "^seat (\\d+) is already taken$",
    "플레이어#1: 이미 다른 사람이 참여했습니다"
  ],
  [
    "^this client does not hold seat (\\d+)$",
    "플레이어#1: 이 접속은 그 자리를 갖고 있지 않습니다"
  ],
  [
    "^only seat (\\d+)'s holder or the host may release it$",
    "플레이어#1: 그 자리의 주인이나 호스트만 해제할 수 있습니다"
  ],
  [
    "^seat (\\d+) has not confirmed its turn end yet$",
    "플레이어#1: 아직 턴 종료를 확정하지 않았습니다"
  ],
  [
    "^seat (\\d+) has no turn end to confirm$",
    "플레이어#1: 확정할 턴 종료가 없습니다"
  ],
  [
    "^seat (\\d+) may take back at most (\\d+) step\\(s\\) now$",
    "플레이어#1: 지금은 최대 $2단계까지만 되돌릴 수 있습니다"
  ],
  [
    "^cannot build seat (\\d+) agent (.+?): (.*)$",
    "플레이어#1의 AI($2)를 만들 수 없습니다: $3"
  ],
  [
    "^save ruleset_version (.+) does not match this server's (.+)$",
    "이 저장본은 다른 규칙 버전의 게임으로 만들어져 불러올 수 없습니다 (저장본 $1, 이 서버 $2)"
  ],
  [
    "^save content_version (.+) does not match this server's (.+)$",
    "이 저장본은 다른 카드 내용 버전의 게임으로 만들어져 불러올 수 없습니다 (저장본 $1, 이 서버 $2)"
  ],
  [
    "^save action_codec_version (.+) does not match this server's (.+)$",
    "이 저장본은 다른 행동 기록 버전의 게임으로 만들어져 불러올 수 없습니다 (저장본 $1, 이 서버 $2)"
  ],
  [
    "^unsupported save format version (.+?) \\(this server reads versions (.+)\\)$",
    "지원하지 않는 저장 형식 버전입니다 (저장본 $1, 이 서버가 읽는 버전 $2)"
  ],
  [
    "^save (\\S+) is unreadable: not an object$",
    "저장본 $1: 읽을 수 없습니다 (내용이 올바른 형식이 아님)"
  ],
  [
    "^save (\\S+) is unreadable: (.+)$",
    "저장본 $1: 읽을 수 없습니다 ($2)"
  ],
  [
    "^save log entry (\\d+)\\b.*$",
    "저장 기록의 #1번째 항목이 올바르지 않습니다"
  ],
  [
    "^save step (\\d+)\\b.*$",
    "저장 기록의 #1번째 수에 문제가 있습니다"
  ],
  [
    "^the save (?:seals|holds|opens)\\b.*$",
    "저장본의 턴 종료 기록이 올바르지 않습니다"
  ],
  [
    "^the save log (?:ends|does)\\b.*$",
    "저장본의 기록이 서로 맞지 않습니다"
  ],
  [
    "^the save ruleset\\b.*$",
    "저장본의 규칙 설정이 올바르지 않습니다"
  ],
  [
    "^the save (?:needs|name)\\b.*$",
    "저장본에 꼭 필요한 항목이 없거나 올바르지 않습니다"
  ],
  [
    "^save (?:seeds|seats|steps|log|sealed_steps|confirmation|open_units|ai_pace)\\b.*$",
    "저장본의 내용이 올바르지 않습니다"
  ],
  [
    "^(?:replay seed|expected_state_hash|ruleset_version|content_version|action_codec_version) must .*$",
    "저장본의 내용이 올바르지 않습니다"
  ]
];
