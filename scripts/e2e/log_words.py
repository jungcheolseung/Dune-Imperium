"""E2E: the action log speaks words, not engine ids (2026-09-21).

An inventory of 19 finished all-AI games (every expansion mix, heuristic and
random seats) found the log printing the engine's own strings in 277 places:
a chance line read `chance: Round:2:Player:0:Discard Shuffle`, an action head
`Count: 2` or `Arrakis Hagga Basin` (a post id), a payload
`Skill:Desperate:0`, `mid_trash` (a Feyd track space), `c2r2` (a research
space) or a comma list of card instance ids. They came through prettify() —
the last resort for an id no table knows — or were printed as they came.

This renders every entry of a few finished games (two of them Arrakeen
Scouts games, 2026-09-29) with the page's own functions (turnLine,
logEventLine, chanceLine, describeReviewStep) in both languages, with
prettify() wrapped, and asserts:

- prettify() is never called: every id resolves through a table;
- in Korean, no Latin word is left outside the catalog names of the current
  language (a card whose Korean print is unknown stays English) and the
  phrases KOREAN_KEEPS_ENGLISH lists (none since 2026-10-11);
- in English, no Hangul, and nowhere an engine id's shape: snake_case, a
  colon path, a research coordinate, a post id;
- every pass_combat_intrigue / pass_endgame_intrigue /
  decline_conflict_end_intrigue turn-line renders quiet (panels.js
  QUIET_ACTIONS), the class that keeps an Intrigue window's pass from
  reading as a full-weight turn card.

A few synthetic lines whose words come from elsewhere than their own label
(user report 2026-10-10) render too: Staban Tuek's Smuggle Spice payout names
the ability and the Leader by the catalog's names, under a "Leader ability"
card title, and Esmar Tuek's Signet taking a bonus spice says it was gained.
Imperial Privilege's recall steps name the recall alone: the card draw is
the space's own step since the user ruling of 2026-10-10 ("4번은 소환과
뽑기가 당연히 두 단계로 나눠야지", OQ-027 (d)). A Sardaukar Commander paying
a troop cost (Piter, Genius Advisor; Bene Gesserit Treachery's garrison unit;
Prison Planet's Commander way in; OQ-105) reads as words in both languages.
Since codec v147 a Reveal choice left unused lapses with the Reveal
(``reveal_choice_lapsed``, the card's name in the line), and a choice id
several cards share names its card with ``source``, a definition id the log
prints as the card's name ("대중의 구경거리: 스파이 배치 — …"); the games
must reach both.

Then the whole game screen at the end of the review, in both languages, with
its titles (a Spy's post read `Arrakis Hagga Basin`, a research hex `c2r2`),
holds no engine id either. The games must still reach the surfaces this
guards, or the check says so instead of passing on an empty corpus.
"""

from __future__ import annotations

import re

from common import SERVER_LOG_COPY, Check, chrome, open_context, server

check = Check()

EVERY_EXPANSION = {
    "choam_module": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "promo_cards": True,
}
# Declining a Combat, Conflict-end or Endgame Intrigue window
# (rules/combat.py, rules/endgame.py) — the engine never emits a bare
# "pass". Mirrors QUIET_ACTIONS/PASS_ACTION_IDS in static/panels.js and
# static/review.js.
PASS_ACTION_IDS = {
    "pass_combat_intrigue",
    "pass_endgame_intrigue",
    "decline_conflict_end_intrigue",
}

# The Reveal choice ids that name their card with ``source`` (codec v147,
# rules/reveal_turn.py SOURCED_REVEAL_ACTION_IDS; static/core.js
# REVEAL_SOURCE_ACTIONS).
REVEAL_SOURCE_ACTIONS = {
    "trash_reveal_card",
    "recall_spy_for_reveal",
    "retreat_two_troops_for_reveal",
    "place_reveal_spy",
    "recall_spy_for_reveal_placement",
    "keep_contract_reveal_spice",
    "trash_contract_reveal_for_vp",
    "gain_reveal_influence",
    "deploy_reveal_card_troop",
    "retreat_reveal_card_troop",
    "decline_reveal_spy_recall",
}

GAMES = (
    {"seats": ["heuristic"] * 4, "game_seed": 7, **EVERY_EXPANSION},
    # Random seats wander into what a heuristic never picks (Family Atomics,
    # the Feyd track, Secrets' random steal, an exchanged Influence).
    {"seats": ["random"] * 4, "game_seed": 25, "policy_seed": 25, **EVERY_EXPANSION},
    # Seed 71 (30 until the 2026-09-26 card-transcription audit, then 38
    # until OQ-070's Commander deploy slot moved that game off its Secrets
    # steal, then 47 until OQ-095's explicit Agent-turn end did the same,
    # 2026-10-01, then 28 until the Imperial Privilege recall confirm did
    # it again, 2026-10-02, then 51 until the 2026-10-04 re-rulings that
    # follow the Steam app did): Family Atomics, the Feyd track and
    # research, and the only one of the four with a Secrets steal.
    # OQ-098 / codec v135 moves the old seed 71 off its Secrets steal.
    # An engine-log scan over seeds 1-64 finds seed 3 first with that chance.
    # The codec v137 card-comparison rulings (2026-10-06) move seed 3 off it
    # too; a scan of the same games through GameSessionManager over seeds
    # 1-120 finds seed 10 first (with Family Atomics, the Feyd track and
    # research as well).
    # The codec v139 general-rules rulings (2026-10-07: Combat Intrigue pass
    # counting, Conflict rewards paid one recipient at a time) move seed 10
    # off its Secrets steal too; the same scan over seeds 1-100 finds seed 4
    # first (again with Family Atomics, the Feyd track and research).
    # A triggered draw held as the owner's own step (user ruling 2026-10-10,
    # OQ-106) moves seed 4 off its Secrets steal (the previous commit's
    # engine still gives it); the same scan from seed 5 finds seed 14 first
    # (again with Family Atomics, the Feyd track and research).
    # Offering both grafted Agent boxes from the start (graft-boxes, codec
    # v143: the heuristic plays grafted turns differently, and random seats
    # choose from a different list of actions) moves seed 14 off its Secrets
    # steal; the same scan from seed 1 finds seed 10 first (again with
    # Family Atomics, the Feyd track and research).
    # Withholding the Agent turn end while a box still offers an
    # effect-giving choice (codec v144: random seats choose from a different
    # list of actions, e.g. Beguiling Pheromones' trash before the turn end)
    # moves seed 10 off its Secrets steal; the same scan from seed 1 finds
    # seed 24 first (again with Family Atomics, the Feyd track and research).
    # An Agent turn's optional effects have no decline action since codec
    # v146 (they lapse at the turn-end press), so random seats choose from yet
    # another list of actions and seed 24 loses its Secrets steal. A scan
    # through GameSessionManager over random seeds 1-299 finds seed 22 first
    # (again with Family Atomics, the Feyd track and research, and with the
    # three events of v146: an unused card effect, board effect and Leader
    # ability; check_coverage).
    # Codec v147 offers a Reveal's card choices as rows of the Reveal list
    # (no refusal, no defer), so random seats choose from yet another list
    # and seed 22 loses its Secrets steal. The same scan over random seeds
    # 1-299 finds seed 20 first (again with Family Atomics, the Feyd track,
    # research and the three v146 events, and with v147's unused Reveal
    # choice and Reveal choice rows naming their card with ``source``).
    {"seats": ["random"] * 4, "game_seed": 20, "policy_seed": 20, **EVERY_EXPANSION},
    {
        "seats": ["random"] * 4,
        "game_seed": 23,
        "policy_seed": 23,
        "leader_draft": True,
        **EVERY_EXPANSION,
    },
    # Arrakeen Scouts (user report 2026-09-29: its payloads read "Kind:
    # mission", "Modifier: any_faction_four_bonus", "Paid", "To" in the
    # Korean log, and its draws "Layout:233#1"). Seeds 200 and 152 until
    # OQ-095's explicit Agent-turn end moved both games (2026-10-01); then
    # 8 for the first until the 2026-10-02 decision windows (L2) moved it
    # off Mating Season, then 23 until the 2026-10-04 re-rulings that
    # follow the Steam app moved it off Clear the Market. Seed 86: Clear
    # the Market with CHOAM, Mating Season, a
    # mission's pieces on posts and an auction won; seed 12: two round
    # modifiers, the Helix spice, Critical Moment's market, mission troops,
    # Mercenaries and the secret picks revealed.
    # Codec v146 (an Agent turn's optional effects lapse instead of being
    # declined, so random seats choose from a different list of actions) moves
    # seed 86 off Clear the Market and Mating Season. A scan of the same games
    # through GameSessionManager over seeds 1-299 finds seed 36 first that,
    # with seed 22 below, reaches every Scouts surface again: Clear the
    # Market, Mating Season, Mercenaries, the secret picks revealed, mission
    # troops, a mission's pieces on posts and an auction won (no single seed of
    # the 299 reaches them all with a round modifier too; seed 22 has the
    # modifier).
    {
        "seats": ["random"] * 4,
        "game_seed": 36,
        "policy_seed": 36,
        "arrakeen_scouts": True,
        **EVERY_EXPANSION,
    },
    {
        "seats": ["random"] * 4,
        # OQ-098 / codec v135: seed 12 loses the round modifier and Mating
        # Season. Seed 37 restored both while retaining mission troops, until
        # the codec v138 Intrigue effect gate (2026-10-06) moved it off its
        # round modifier. An engine-log scan over seeds 1-159 (with seed 86
        # above) finds seed 80 first that, together with seed 86, reaches
        # every Scouts surface below again.
        # The codec v139 general-rules rulings (2026-10-07) move seed 80 off
        # Mating Season; a scan through GameSessionManager over seeds 1-120
        # finds seed 22 first that, with seed 86, reaches every Scouts
        # surface again (a round modifier, Mating Season, mission troops, an
        # auction won).
        # The codec v141 Conflict-end window, which opens on public facts
        # (OQ-103, 2026-10-09), moves seed 22 off Mating Season; the same
        # scan over seeds 1-159 finds seed 107 first that, with the other
        # five games, reaches every surface again (a round modifier, Mating
        # Season, mission troops).
        # Imperial Privilege's card draw as its own icon (user ruling
        # 2026-10-10, OQ-027 (d)) moves seed 107 off its round modifier (the
        # previous commit's engine still gives it); the same scan over seeds
        # 1-160 finds seed 126 first with a round modifier, Mating Season and
        # mission troops.
        # Offering both grafted Agent boxes from the start (graft-boxes,
        # codec v143: the heuristic plays grafted turns differently, and
        # random seats choose from a different list of actions) moves seed
        # 126 off its round modifier and Mating Season; the same scan from
        # seed 1 finds seed 22 first with a round modifier, Mating Season,
        # mission troops and an auction won.
        # Codec v146 moves seed 22 off Mating Season (the game above has it);
        # it keeps the round modifier, mission troops and an auction won.
        "game_seed": 22,
        "policy_seed": 22,
        "arrakeen_scouts": True,
        **EVERY_EXPANSION,
    },
)

# English on purpose in the Korean page, as whole phrases (a stray "card" or
# "set" is still caught). Empty since 2026-10-11: the Leader ability names,
# Feyd's token, Memories, the Immediate contract, Usurp and the wild battle
# icon card all read in Korean now (docs/rules/glossary-ko.md).
KOREAN_KEEPS_ENGLISH: tuple[str, ...] = ()

RENDER_JS = r"""
async ({gameId}) => {
  const meta = await api(`/games/${gameId}/review?seat=0`);
  const out = [];
  const calls = [];
  const realPrettify = window.prettify;
  window.prettify = (id) => { calls.push(String(id)); return realPrettify(id); };
  const take = () => calls.splice(0, calls.length);
  // Printed card wording (ITEM 8b's Intrigue option line, and any other
  // .card-text span) stays English by policy in both languages (iconize()'s
  // own comment: "the wrapper marks it as the card's own English text ...
  // which lang.py's Korean check skips"). The Korean-leak check below needs
  // the same exemption lang.py already gives the rest of the page, so every
  // DOM-built line reports a second, .card-text-stripped copy of its words
  // for that check only; the full text (still used for display and the
  // English/Hangul check) is unaffected. An engine-*generated* effect
  // line's Korean twin (STEP K1, 2026-09-25) is NOT stripped here: its own
  // class is .effect-text-ko, not .card-text, on purpose (render.js
  // effectNode()) -- it must read as ordinary Korean, so this loop leaves
  // it in place for the Korean-leak check below. None of this script's own
  // turn/event/chance renderers reach a popover today, so no such line is
  // in these recorded strings yet; this comment is here so the next
  // generator's step does not have to rediscover why the strip list stops
  // at .card-text.
  const wordsOf = (el) => {
    const clone = el.cloneNode(true);
    for (const node of clone.querySelectorAll(".card-text")) node.remove();
    return clone.textContent;
  };
  const events = (lang, entry) => {
    for (const event of entry.events || []) {
      for (const [key, value] of Object.entries(event.payload)) {
        take();
        const text = logEventPayload({[key]: value});
        out.push({lang, src: `payload ${event.kind}.${key}`, value, text,
                  pretty: take()});
      }
      take();
      const eventLine = logEventLine(event);
      out.push({lang, src: `event ${event.kind}`, text: eventLine.textContent,
                wordsText: wordsOf(eventLine), pretty: take()});
    }
  };
  try {
    for (const lang of ["ko", "en"]) {
      setLanguage(lang, false);
      for (const entry of meta.log) {
        if (entry.type === "chance") {
          take();
          const label = {type: "chance", decision_id: entry.decision_id,
                         values: entry.values || []};
          const text =
            chanceLine(entry).textContent + " | " + describeReviewStep(label);
          out.push({lang, src: `chance ${entry.decision_id}`, text, pretty: take()});
          events(lang, entry);
        } else if (entry.type === "action") {
          take();
          const line = turnLine({...entry, events: []});
          out.push({lang, src: `action ${entry.action_id}`, text: line.textContent,
                    wordsText: wordsOf(line),
                    pretty: take(), args: entry.arguments,
                    quiet: line.classList.contains("quiet")});
          events(lang, entry);
        }
      }
    }
  } finally {
    window.prettify = realPrettify;
    setLanguage("ko", false);
  }
  const names = new Set();
  for (const table of Object.values(state.catalog)) {
    if (!table || typeof table !== "object") continue;
    for (const entry of Object.values(table)) {
      if (entry && typeof entry.name === "string") names.add(entry.name);
    }
  }
  return {out, names: [...names], posts: Object.keys(state.catalog.posts)};
}
"""

# Text and the attributes a person or a screen reader meets, on the game screen.
PAGE_TEXT_JS = """() => {
    const found = [];
    const screen = document.getElementById('game-screen');
    const walker = document.createTreeWalker(screen, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const host = node.parentElement;
        if (!host || host.closest('[hidden]')) continue;
        found.push([node.textContent, host.id || host.className || host.tagName]);
    }
    for (const el of screen.querySelectorAll('[title], [alt], [aria-label]')) {
        for (const name of ['title', 'alt', 'aria-label']) {
            if (el.hasAttribute(name)) {
                const where = `${el.className || el.tagName}@${name}`;
                found.push([el.getAttribute(name), where]);
            }
        }
    }
    return found;
}"""

SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
COLON_PATH = re.compile(r"\b[a-z]+(?::[a-z0-9_]+)+\b", re.I)
RESEARCH_ID = re.compile(r"\bc\d+r\d+\b")
HANGUL = re.compile(r"[가-힣]+")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def engine_ids(text: str, posts: list[str]) -> list[str]:
    found = SNAKE.findall(text) + COLON_PATH.findall(text) + RESEARCH_ID.findall(text)
    # A post id as it came, or through prettify() ("Arrakis Hagga Basin").
    return found + [
        post
        for post in posts
        if post in text or post.replace("-", " ").title() in text
    ]


def strip(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        if phrase in text:
            text = text.replace(phrase, " ")
    return text


def render_games(page) -> tuple[list[dict], list[str], list[str], list[str]]:
    records: list[dict] = []
    names: set[str] = set()
    posts: list[str] = []
    game_ids: list[str] = []
    for config in GAMES:
        created = page.evaluate(
            """async (body) => {
              const r = await fetch('/games', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)});
              return {status: r.status, body: await r.json()};
            }""",
            config,
        )
        check.ok(created["status"] == 200, f"created {config['game_seed']}", created)
        if created["status"] != 200:
            continue
        game_id = created["body"]["game_id"]
        game_ids.append(game_id)
        result = page.evaluate(RENDER_JS, {"gameId": game_id})
        records.extend(result["out"])
        names.update(result["names"])
        posts = result["posts"]
    return records, sorted(names, key=len, reverse=True), posts, game_ids


def check_coverage(records: list[dict]) -> None:
    """The games still reach what this guards; otherwise it would pass empty."""
    sources = [r["src"] for r in records if r["lang"] == "ko"]
    wanted = {
        "a discard pile shuffle": lambda s: s.startswith("chance ")
        and s.endswith(":discard_shuffle"),
        "a post argument": lambda s: s.startswith("payload ") and s.endswith("post_id"),
        "a research space": lambda s: s == "payload research_advanced.space_id",
        "a Feyd track step": lambda s: s == "payload feyd_token_advanced.to_space",
        "a Skill instance": lambda s: s.endswith(".skill_instance_id"),
        "Family Atomics' removed cards": lambda s: s
        == "payload imperium_row_cleared.removed",
        "an exchanged Influence": lambda s: s == "action exchange_reveal_influence",
        "a Secrets steal": lambda s: s.startswith("chance ") and ":secrets:steal:" in s,
        "a Combat/Endgame Intrigue pass": lambda s: s.startswith("action ")
        and s.split(" ", 1)[1] in PASS_ACTION_IDS,
        "an Arrakeen Scouts draw": lambda s: s.startswith("chance ")
        and ":scouts:" in s,
        "a Scouts item's kind": lambda s: s == "payload scouts_item_revealed.kind",
        "a Scouts round modifier": lambda s: s
        == "payload scouts_round_modifier.modifier",
        "Clear the Market's Contracts": lambda s: s
        == "payload scouts_contracts_cleared.dealt",
        "a Scouts mission's pieces": lambda s: s
        == "payload scouts_mission_goods_placed.locations",
        "Scouts mission troops": lambda s: s == "payload scouts_mission_troops.to",
        "a Scouts auction won": lambda s: s == "payload scouts_auction_won.place",
        "Scouts Mercenaries": lambda s: s == "payload scouts_mercenaries_deployed.paid",
        "a Scouts secret pick revealed": lambda s: s
        == "payload scouts_secret_revealed.event_round",
        "Mating Season's spaces": lambda s: s
        == "payload scouts_maker_spice_added.space_ids",
        # Codec v146: an optional effect of the player's own Agent turn that
        # was not used lapses at the "턴 종료 ▶" press. Each event is
        # rendered with its real payload in both languages.
        "an unused card effect": lambda s: s == "event agent_card_effect_lapsed",
        "an unused board effect": lambda s: s == "event board_effect_lapsed",
        "an unused Leader ability": lambda s: s == "event leader_ability_lapsed",
        # Codec v147: a Reveal choice left unused lapses at "턴 종료 ▶", and
        # an id several cards' choices share names its card with ``source``
        # (a definition id the log must print as the card's name).
        "an unused Reveal choice": lambda s: s == "event reveal_choice_lapsed",
        "a Reveal choice naming its card": lambda s: s
        in {f"action {action_id}" for action_id in REVEAL_SOURCE_ACTIONS},
    }
    missing = [label for label, test in wanted.items() if not any(map(test, sources))]
    check.ok(not missing, "the games reach every surface this guards", missing)


def check_pass_quiet(records: list[dict]) -> None:
    """Every pass_combat_intrigue / pass_endgame_intrigue /
    decline_conflict_end_intrigue turn-line renders quiet (panels.js
    QUIET_ACTIONS) — it never gets the full-weight card."""
    passes = [
        r
        for r in records
        if r["src"].startswith("action ")
        and r["src"].split(" ", 1)[1] in PASS_ACTION_IDS
    ]
    loud = [(r["lang"], r["src"], r["text"][:60]) for r in passes if not r.get("quiet")]
    check.ok(not loud, "every Intrigue pass renders quiet", loud[:4])


def check_log(records, names, posts) -> None:
    pretty = [(r["src"], r["pretty"]) for r in records if r["pretty"]]
    check.ok(
        not pretty,
        "prettify() never reaches the log: every engine id resolves through a table",
        pretty[:4],
    )

    korean = [r for r in records if r["lang"] == "ko"]
    allowed = names + sorted(KOREAN_KEEPS_ENGLISH, key=len, reverse=True)
    latin = [
        (r["src"], words, r["text"][:90])
        for r in korean
        # Printed card wording (a .card-text span, e.g. ITEM 8b's Intrigue
        # option line) is stripped out by wordsOf() before this check, the
        # same exemption lang.py already gives the rest of the page; a
        # source with no DOM element to strip (a payload, a chance line)
        # falls back to its plain text, unaffected.
        if (words := sorted(set(
            LATIN.findall(strip(r.get("wordsText", r["text"]), allowed))
        )))
    ]
    check.ok(
        not latin,
        "Korean log: no English outside names and the glossary's kept phrases",
        latin[:4],
    )

    english = [r for r in records if r["lang"] == "en"]
    hangul = [(r["src"], r["text"][:90]) for r in english if HANGUL.search(r["text"])]
    check.ok(not hangul, "English log: no Hangul", hangul[:4])
    for lang, rows in (("Korean", korean), ("English", english)):
        ids = [
            (r["src"], found, r["text"][:90])
            for r in rows
            if (found := engine_ids(strip(r["text"], names), posts))
        ]
        check.ok(not ids, f"{lang} log: no engine id's shape", ids[:4])


# Lines whose words come from somewhere other than the event's own label
# (user report 2026-10-10), rendered with the page's functions in both
# languages: Staban Tuek's Smuggle Spice -- its gain names him (the
# ``leader`` source), its ``leader_ability_resolved`` names the ability and
# the Leader (panels.js logEventHead, the catalog's names) -- the "game"
# card holding it is titled for a Leader ability, and Esmar Tuek's Signet
# taking a bonus spice is a gain line (cleanup-2c-4).
NAMED_JS = r"""() => {
  const out = {};
  const calls = [];
  const realPrettify = window.prettify;
  window.prettify = (id) => { calls.push(String(id)); return realPrettify(id); };
  const gain = {kind: "resources_gained",
    payload: {player: 0, source: "round:1:player:0:leader:staban_tuek", spice: 1}};
  const smuggle = {kind: "leader_ability_resolved",
    payload: {leader_id: "staban_tuek", player: 0, visitor: 3}};
  const taken = {kind: "resources_gained",
    payload: {player: 2, source: "round:1:player:2:leader_signet", spice: 1}};
  const placed = {kind: "leader_signet_resolved",
    payload: {card_id: "player:2:starter:signet_ring:0", player: 2}};
  try {
    for (const lang of ["ko", "en"]) {
      setLanguage(lang, false);
      const staban = lookup("staban_tuek", "leaders");
      const group = {kind: "neutral", firstIndex: 1, lastIndex: 1,
        items: [{event: gain, index: 1}, {event: smuggle, index: 1}]};
      out[lang] = {
        leader: staban.name,
        ability: staban.ability,
        gain: logEventLine(gain).textContent,
        smuggle: logEventLine(smuggle).textContent,
        title: neutralTitle(group),
        taken: logEventLine(taken).textContent,
        placed: logEventLine(placed).textContent,
      };
    }
  } finally {
    window.prettify = realPrettify;
    setLanguage("ko", false);
  }
  out.pretty = calls;
  return out;
}"""


def check_named_lines(page, posts: list[str], names: list[str]) -> None:
    shown = page.evaluate(NAMED_JS)
    check.ok(not shown["pretty"], "named lines: prettify() is never called", shown)
    expected = {
        "ko": ("스타반 튜엑", "스파이스 밀수", "지도자 능력"),
        "en": ("Staban Tuek", "Smuggle Spice", "Leader ability"),
    }
    verbs = {"ko": "획득", "en": "Gained"}
    for lang, (leader, ability, title) in expected.items():
        row = shown[lang]
        check.ok(
            (row["leader"], row["ability"]) == (leader, ability),
            f"{lang}: the catalog names Staban Tuek and Smuggle Spice",
            row,
        )
        check.ok(
            leader in row["smuggle"] and ability in row["smuggle"],
            f"{lang}: the Smuggle Spice line names the ability and the Leader",
            row["smuggle"],
        )
        check.ok(
            leader in row["gain"] and verbs[lang] in row["gain"],
            f"{lang}: Smuggle Spice's gain names the Leader",
            row["gain"],
        )
        check.ok(
            row["title"] == title,
            f"{lang}: the card holding it is titled for a Leader ability",
            row["title"],
        )
        check.ok(
            verbs[lang] in row["taken"]
            and "1" in row["taken"]
            and "-1" not in row["taken"],
            f"{lang}: Esmar's Signet taking a bonus spice says it was gained",
            row["taken"],
        )
        check.ok(
            verbs[lang] not in row["placed"],
            f"{lang}: placing a bonus spice gains nothing",
            row["placed"],
        )
        texts = [row["gain"], row["smuggle"], row["title"], row["taken"], row["placed"]]
        ids = [
            found for text in texts if (found := engine_ids(strip(text, names), posts))
        ]
        check.ok(not ids, f"{lang}: the named lines show no engine id", ids)
        if lang == "en":
            hangul = [text for text in texts if HANGUL.search(text)]
            check.ok(not hangul, "en: the named lines hold no Hangul", hangul)
    print(f"  .. {shown['ko']['smuggle']}")
    print(f"  .. {shown['en']['smuggle']}")
    print(f"  .. {shown['ko']['taken']}")


# Imperial Privilege's recall and its draw are two steps (user ruling
# 2026-10-10, OQ-027 (d)): the recall steps, the Into the Fray recall and the
# confirm with no Agent to recall, name the recall alone, no card draw (they
# named it from 2026-10-10 morning, while the recall still drew the card).
RECALL_JS = r"""() => {
  const out = {};
  const steps = [
    {action_id: "recall_agent_for_imperial_privilege",
     arguments: {space_id: "arrakeen"}},
    {action_id: "recall_conflict_agent_for_imperial_privilege", arguments: {}},
    {action_id: "resolve_imperial_privilege_without_recall", arguments: {}},
  ];
  try {
    for (const lang of ["ko", "en"]) {
      setLanguage(lang, false);
      // describeActionText: the label's icons as their words (alt, title).
      out[lang] = steps.map((step) => describeActionText({type: "action", index: 9,
        actor: 0, events: [], ...step}));
    }
  } finally {
    setLanguage("ko", false);
  }
  return out;
}"""


def check_recall_steps(page, posts: list[str], names: list[str]) -> None:
    shown = page.evaluate(RECALL_JS)
    for lang, recall, draw in (
        ("ko", "소환", "뽑기"),
        ("en", "Recall", "Draw"),
    ):
        for text in shown[lang]:
            check.ok(
                recall.lower() in text.lower()
                and draw.lower() not in text.lower()
                and not engine_ids(strip(text, names), posts),
                f"{lang}: the Imperial Privilege recall step names the recall alone",
                text,
            )
    print(f"  .. {shown['ko'][0]} | {shown['en'][0]} | {shown['en'][2]}")


# A Sardaukar Commander pays the self-paid troop costs (OQ-105, user ruling
# 2026-10-10): Piter's Commander loss, Bene Gesserit Treachery's garrison
# unit and Prison Planet's Commander way in read as words in both languages,
# logged (no live detail) as they are in the review.
COMMANDER_COSTS_JS = r"""() => {
  const out = {};
  const steps = [
    {action_id: "lose_agent_card_troop",
     arguments: {commanders: 1, zone: "garrison"}},
    {action_id: "scouts_lose_garrison_unit", arguments: {}},
    {action_id: "scouts_lose_garrison_unit", arguments: {commanders: 1}},
    {action_id: "scouts_join_mission", arguments: {target: "commander"}},
  ];
  try {
    for (const lang of ["ko", "en"]) {
      setLanguage(lang, false);
      out[lang] = steps.map((step) => describeActionText({type: "action", index: 9,
        actor: 0, events: [], ...step}));
    }
  } finally {
    setLanguage("ko", false);
  }
  return out;
}"""


def check_commander_costs(page, posts: list[str], names: list[str]) -> None:
    shown = page.evaluate(COMMANDER_COSTS_JS)
    for lang in ("ko", "en"):
        for text in shown[lang]:
            check.ok(
                not engine_ids(strip(text, names), posts)
                and (lang == "ko" or not HANGUL.search(text)),
                f"{lang}: a Commander paying a troop cost reads as words",
                text,
            )
    print(f"  .. {' | '.join(shown['ko'])}")
    print(f"  .. {' | '.join(shown['en'])}")


def check_page(page, base: str, game_id: str, posts: list[str], names) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_function("state.review !== null && state.view !== null")
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count"
        " && !playback.playing && refreshFlight === null"
    )
    # Folded seat detail is [hidden] and skipped below; open it (the research
    # flag there printed a coordinate, `c5r1`).
    page.evaluate(
        "if (!state.view.players.every((p) => expandedSeats.has(p.player)))"
        " toggleAllSeats()"
    )
    for lang in ("ko", "en"):
        page.evaluate(f"setLanguage('{lang}')")
        page.wait_for_function("refreshFlight === null")
        page.wait_for_timeout(300)
        texts = page.evaluate(PAGE_TEXT_JS)
        titled = [text for text, where in texts if "@title" in where]
        ids = [
            (where, found, text[:80])
            for text, where in texts
            if (found := engine_ids(strip(text, names), posts))
        ]
        check.ok(
            bool(titled) and not ids,
            f"{lang}: the finished game's screen, titles included, shows no engine id",
            ids[:4] or len(titled),
        )
    page.evaluate("setLanguage('ko')")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        _, page, _rec = open_context(browser, "log-words")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        print(f"[1] render the logs of {len(GAMES)} finished games in both languages")
        records, names, posts, game_ids = render_games(page)
        print(f"  .. {len(records)} rendered lines")
        check_coverage(records)
        check_log(records, names, posts)
        check_pass_quiet(records)
        print("[1b] lines named from elsewhere than their own label")
        check_named_lines(page, posts, names)
        check_recall_steps(page, posts, names)
        check_commander_costs(page, posts, names)
        print("[2] the whole screen at the end of the first game's review")
        if game_ids:
            check_page(page, base, game_ids[0], posts, names)
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    check.finish()


if __name__ == "__main__":
    main()
