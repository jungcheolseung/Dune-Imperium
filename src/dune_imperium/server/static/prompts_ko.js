"use strict";

/* Korean for the engine's decision prompts (rules/*.py sends English). Keyed
   by the exact English sentence; PROMPT_KO_PATTERNS covers the formatted
   ones as [RegExp source, Korean with $1 for a group]. Rule words are {term}
   tokens, so the Korean is the glossary's (docs/rules/glossary-ko.md). The
   bodies are JSON so tests/server/test_i18n.py can read them. */
const PROMPT_KO = {
  "Acquire a Tech tile or decline": "{tech_tile} 획득 또는 거절",
  "Bene Gesserit Alliance: lose one Influence for a Victory Point, or decline": "베네 게세리트 {alliance}: {influence_any} 1 잃고 {victory_point} 1 획득, 또는 거절",
  "Choose Influence to lose and gain or decline this Reveal effect": "잃을 {influence_any}과 얻을 {influence_any} 선택, 또는 이 {reveal_turn} 효과 거절",
  "Choose a Spy placement or gain two strength": "{spy} 배치 위치 선택 또는 {strength} 2 획득",
  "Choose a Spy to recall for this Reveal effect": "이 {reveal_turn} 효과로 소환할 {spy} 선택",
  "Choose a card to discard for Covert Operation": "Covert Operation 효과로 버릴 카드 선택",
  "Choose a different faction to gain one Influence": "{influence_any} 1을 얻을 다른 {faction} 선택",
  "Choose a faction to gain one Influence": "{influence_any} 1을 얻을 {faction} 선택",
  "Choose an Agent turn or Reveal turn": "{agent_turn} 또는 {reveal_turn} 선택",
  "Choose an Observation Post for the Contract Spy": "{contract} 보상 {spy}를 배치할 {observation_post} 선택",
  "Choose an Observation Post for the Contract Spy with Deep Cover": "{contract} 보상 잠복 {spy}를 배치할 {observation_post} 선택",
  "Choose an Observation Post for the acquired Spy": "획득한 {spy}를 배치할 {observation_post} 선택",
  "Choose an empty Observation Post for your Spy": "내 {spy}를 배치할 빈 {observation_post} 선택",
  "Choose an Observation Post for your Spy with Deep Cover": "내 잠복 {spy}를 배치할 {observation_post} 선택",
  "Choose one Persuasion or a Contract": "{persuasion} 1 또는 {contract} 중 선택",
  "Choose one of your other Agents to recall": "소환할 다른 {agent} 선택",
  "Choose the Skill for the acquired Sardaukar Commander": "획득한 {commander}의 기술 토큰 선택",
  "Choose the card to draw, then the one to discard": "뽑을 카드를 고른 뒤 버릴 카드 선택",
  "Choose the card to graft": "{graft}할 카드 선택",
  "Choose the next Agent-turn effect to resolve": "다음에 해결할 {agent_turn} 효과 선택",
  "Choose two Spies to recall or decline this Reveal effect": "소환할 {spy} 2개 선택, 또는 이 {reveal_turn} 효과 거절",
  "Choose where to advance your research token": "{research} 토큰을 전진시킬 위치 선택",
  "Choose where to lose one unit": "부대 1을 잃을 위치 선택",
  "Choose where to place a Spy for this Reveal effect": "이 {reveal_turn} 효과로 {spy}를 배치할 위치 선택",
  "Command: choose a Faction to gain one Influence with": "{command}: {influence_any}을 얻을 {faction} 선택",
  "Command: choose where to place a Spy": "{command}: {spy}를 배치할 위치 선택",
  "Command: trash a card or decline": "{command}: 카드 {trash} 또는 거절",
  "Command: trash this card to acquire an Imperium Row card, or decline": "{command}: 이 카드를 {trash}하고 {imperium_row} 카드 획득, 또는 거절",
  "Deploy one troop from supply to defend your location?": "{supply}에서 병력 1을 배치해 이 위치를 방어하시겠습니까?",
  "Deploy or retreat one troop, or decline": "병력 1 배치 또는 {retreat}, 또는 거절",
  "Gain Spice or trash this card for one Victory Point": "{spice} 획득 또는 이 카드를 {trash}하고 {victory_point} 1 획득",
  "Gain five Solari or pay five for a High Council seat": "{solari} 5 획득 또는 {solari} 5 지불하고 원로회 자리 차지",
  "Keep one of the two Intrigue cards": "{intrigue} 2장 중 1장 보관",
  "Keep two Persuasion or pay one Water for a sandworm": "{persuasion} 2 유지 또는 {water} 1 지불하고 {sandworm} 획득",
  "Lose two troops for two specimens, or decline": "병력 2를 잃고 {specimen} 2 획득, 또는 거절",
  "Move your Spy off the watched space": "감시 중인 공간에서 {spy} 이동",
  "Pay three Spice for Influence or decline this Reveal effect": "{spice} 3 지불하고 {influence_any} 획득, 또는 이 {reveal_turn} 효과 거절",
  "Pick a Leader from the face-up draft pool": "공개된 드래프트 풀에서 {leader} 선택",
  "Place a Spy on the watched space": "{spy}를 배치할 {observation_post} 선택",
  "Place a Spy with Deep Cover": "잠복 {spy}를 배치할 {observation_post} 선택",
  "Place four Navigation cards face down, in order": "{navigation} 4장을 순서대로 뒷면으로 놓기",
  "Play Combat Intrigue cards or pass": "{combat} {intrigue} 사용 또는 패스",
  "Play Endgame Intrigue, match wild icons, or pass": "{endgame} {intrigue} 사용, 와일드 아이콘 매칭, 또는 패스",
  "Play an Intrigue card that triggers at this Conflict's end, or decline": "이 {conflict} 종료 시 발동하는 {intrigue} 사용, 또는 거절",
  "Play the Navigation card": "{navigation} 사용",
  "Recall a Spy for three swords or decline": "{spy} 1 소환하고 {sword} 3 획득, 또는 거절",
  "Recall a Spy to draw an Intrigue card, or decline": "{spy}를 소환하고 {intrigue} 1장 뽑기, 또는 거절",
  "Resolve Reveal effects and acquire cards": "{reveal_turn} 효과 해결 및 카드 획득",
  "Resolve the Intrigue choice": "{intrigue} 선택 해결",
  "Resolve the Navigation choice": "{navigation} 선택 해결",
  "Resolve the research space bonus": "{research} 공간 보너스 해결",
  "Retreat two troops for four strength or decline": "병력 2를 {retreat}하고 {strength} 4 획득, 또는 거절",
  "Retreat two troops for two Persuasion or decline": "병력 2를 {retreat}하고 {persuasion} 2 획득, 또는 거절",
  "Secret Project: place one bottom Tech tile on your Leader": "Secret Project: 맨 아래 {tech_tile} 1개를 내 {leader}에 배치",
  "Take a face-up Contract": "공개된 {contract} 획득",
  "Trash Plasteel Blades for an additional Skill, or keep it": "Plasteel Blades를 {trash}하고 추가 {commander_skill} 획득, 또는 유지",
  "Trash a card or decline": "카드 {trash} 또는 거절",
  "Trash an Imperium card from your hand, discard pile, or in play, or decline": "{hand}·{discard_pile}·플레이 영역의 임페리움 카드 1장 {trash}, 또는 거절",
  "Trash an Intrigue card for the Immediate Contract": "Immediate {contract}의 비용으로 {intrigue} 1장 {trash}",
  "Trash another Emperor card or decline this Reveal effect": "다른 황제 카드를 {trash}, 또는 이 {reveal_turn} 효과 거절",
  "Trash this card for one Influence with each Faction, or decline": "이 카드를 {trash}하고 각 {faction}의 {influence_any} 1씩 획득, 또는 거절",
  "Trash this card for the Combat icon or decline": "이 카드를 {trash}하고 {combat} 아이콘 획득, 또는 거절",
  "Two or more Tech tiles: choose a Faction to gain one Influence with": "{tech_tile} 2개 이상: {influence_any}을 얻을 {faction} 선택",
  "Use one of the card's lines, or finish the card": "카드의 한 줄 사용, 또는 카드 마무리",
  "Use your Leader's Signet Ring ability": "{leader}의 {signet_ring} 능력 사용",
  "Use the face-up Intrigue card or decline": "공개된 {intrigue} 사용, 또는 거절"
};

const PROMPT_KO_PATTERNS = [
  [
    "^Pay (\\d+) Spice to gain (\\d+) Victory Point$",
    "{spice} $1 지불 → {victory_point} $2 획득"
  ],
  [
    "^Pay (\\d+) Solari to gain (\\d+) Victory Point$",
    "{solari} $1 지불 → {victory_point} $2 획득"
  ],
  [
    "^Recall (\\d+) placed Spies to gain (\\d+) Victory Point$",
    "배치된 {spy} $1 소환 → {victory_point} $2 획득"
  ]
];
