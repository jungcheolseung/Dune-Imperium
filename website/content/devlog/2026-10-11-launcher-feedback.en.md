+++
title = "A server launcher, game-like effects, and feedback from games with friends"
description = "A launcher window to start and stop the play server without a terminal, effects such as AI turn banners and a combat result board with an AI pace, and fixes for the clock, sound, and screen problems found in games with friends."
date = 2026-10-12T01:14:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-08"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/server-launcher-plan.md", "docs/windows-host-validation.md", "docs/worklog/2026-10.md"]
+++

## Starting and stopping the server from a window (October 8–9)

The play server was started with a terminal command. The goal was a window on Mac and Windows to start and stop it without a terminal, and of five options a tkinter window was chosen. Stages 1 to 6 merged on October 9.

- **The window.** The left side holds settings (mode, address candidates, port, the start of the room link, save folder, search network, AI pace, pictures); the right side holds start and stop, a pre-start check, copy and open for the room link, the list of open games, and the server log. Settings live in a local folder that git ignores.
- **While the server runs.** The host PC is kept from sleeping (by the method of each of macOS and Windows), and only one launcher runs per checkout. A script creates a double-click shortcut (`.app`, `.lnk`).
- **Server option.** `--exit-when-stdin-closes` keeps a server started by the launcher from outliving it. If the launcher dies its standard input closes, the server sees that and exits (on Windows a Job Object is used as well).
- **A correction.** The search AI seat used to check only for the training library (torch) and offer the seat, and then fail when someone sat down. The seat is now offered only when the `rl` packages (numpy and others) are also present, and the install script and the guide fetch both extras.

Verification effort was split in two. The window's look (`gui.py`, `view.py`) is low risk. Starting and stopping the server (`supervisor.py`, closing on standard input) is high risk and got an independent review at each stage; the reviews of stages 1, 2, and 3–5 each found real defects, which were fixed. Checks were 192 tests in `tests/launcher/` (window tests are skipped without a display), 16 checks in the launcher-link browser E2E, mypy for macOS and for Windows, and on the merged master 6,932 pytest tests and 54 E2E scripts. This Mac had no screen-recording permission, so the window itself was not captured.

On October 11 local mode got autosave. A game played alone against AIs in the launcher's "this computer only" mode vanished when the launcher closed, because autosave had existed only on the remote server. The server's `--autosave` now turns on the same kind of saving without remote mode. A server started by hand keeps its old default.

Windows was checked on October 12 on a separate Windows 11 PC. An integration regression covering the launcher button through the server process to a clean stop was added, test failures such as the inability to create symbolic links in a normal account were fixed, and the real Chrome E2E passed 174 checks (launcher link, app AI seats, remote, recovery). That change was merged into master on October 21. Manual checks remain, such as connecting from another PC, display scaling and input methods, and long sessions, so the last stage of the launcher plan is not marked complete.

## Game-like effects and AI pace (October 8)

The plan was effects that feel like a real game on the play screen, a final standing when the combat phase ends, and a cue for AI turns like the one for the player's own turn. An AI's moves all finished within one human click, so the screen never had a "now" for the AI. Stages 1 to 5 merged the same day.

- **One queue of cues.** A single queue raises turn banners and card notices one at a time in log order. There is an AI turn banner, the space lighting up in the seat's colour when an Agent card lands, a fan of the revealed cards at Reveal, number changes on the seat panel (+2, −1), banners for sandworm summons and Shield Wall destruction, a combat result board, and a final standings board at game end.
- **AI pace.** In games with a human seat, AI decisions are applied after the time the screen needs to show the preceding events. The server's `--ai-pace` defaults to normal, with fast (0.6 times) and instant (the old behaviour). The answers do not change, which a test checks by reaching the same state as the instant game on the same seed. Games with only AIs are always instant.

### Report-only events

The combat standing (`combat_standing`) and the list of revealed cards (`cards_revealed`) are facts the screen needs but not rule state. Putting them in the state's event log would change the state hash and stop older saves from opening. So they were made "report-only events": they reach the server log but are not stored in the state. They were first put into the event log, and loading a saved game just before the merge ran into the hash check. The lesson, that screen-only events are report-only from the start, is recorded in `docs/lessons.md`.

The independent review of stage 4 found that during pacing the ordinary AI used the search AI's fallback answer, which hid agent errors and made that game's save impossible to open. Only the search seats use the fallback now. The checks at this stage were 6,676 pytest tests and 50 E2E scripts. Purchased cards flying, the alliance banner and influence cubes, a round-cleanup effect, and a setting to turn effects off were postponed, and it has not yet been tried at normal pace in a real remote game.

## Fixes after games with friends (October 11)

Feedback from two games with friends, on the day and that night, was fixed item by item. The engine, the codec, and the save format were left alone.

- **Play clock.** Like a chess clock, it counts the time of the seat holding control. Interjection answers on another seat's turn, decisions outside turns, and the time before pressing "End turn ▶" all belong to that seat, and AI seats are counted the same way. Undo does not give time back. Saves carry it as an optional field, and the record and problem-set tools do not read it (the decision was that time is not training data). A review that checked 27 randomly played games and about 600 operations against the rules found no major problem and fixed one defect: a save with a very large clock value would not open.
- **Sound.** There are sounds for the turn to decide, the start of a round, the start of combat, and Arrakeen Scouts. Only code-synthesized sounds are used (the decision was not to keep sound files in the assets), with a different tone for each.
- **Column widths and hand order.** Handles between the seat, board, and decision columns change the widths, and hand and Intrigue cards can be reordered by dragging. Both are stored only in the browser and never sent to the server.
- **Pile list window.** The discard and deck lists used the same popover as the card enlargement, so hovering a card in the list let the enlargement cover the list, and every refresh closed it. The list moved into its own window that closes only with ×, Esc, or the same button.
- **This turn's cards.** Cards played this Agent turn are marked, and a trash row warns that trashing a card ends the rest of its Agent-box effect. In review, 8,272 trash rows over 1,200 random games had warnings matching the actual loss of the effect, and reshuffling hidden information left the results the same.
- **Scouts window.** The revealed Arrakeen Scouts item shows as a card over the board, with fold and unfold and previous/next when a round reveals several. The text is a paraphrase written for this project. During the secret-pick reveal, seats that have not yet revealed are listed separately as "still hidden", which removes a misreading in which the engine was right but the screen read as if they had been revealed.
- **Victory Point ledger.** Clicking a seat panel's Victory Points shows that seat's changes (round, change, running total, cause), and a row leads to that move in the activity log. The server replays the game to compute the difference at each move. In remote games it is visible only to seated players, or once the game is over.
- **One icon per effect.** One rulebook icon is one effect (`[Main p. 20]`). Text in the log and choice lines that stacked two icons now uses the single icon that matches the meaning.
- **Card pictures on hover.** Hovering a card name in the activity log or a card-choosing row shows the card picture.
- **Korean names.** The Korean names of the 23 board spaces and 5 Objective cards are paired with the official Korean board guide (`[Board Guide pp. 1-2]`) and used in choice lines, the log, and board tooltips. The board picture itself stays the English edition. Leader abilities, signet rings, and Navigation cards were also aligned to the official Korean names. English alongside terms in the help legend was kept on purpose.

This batch was checked with pytest going from 7,267 to 7,301 tests (per piece of work), ruff and mypy, and browser E2E scripts going from 56 to 59.

The work from the same days of migrating human-played games to the current engine, diagnosing them, and building a problem set is in [Human-played games as records and a problem set]({{< relref path="devlog/2026-10-11-human-records.md" lang="en" >}}), and the rule questions and rulings that play raised are in the [rule-questions entry]({{< relref path="devlog/2026-10-14-rule-questions.md" lang="en" >}}).

## References

- [Server launcher plan and per-stage record](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/server-launcher-plan.md)
- [Windows host validation](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/windows-host-validation.md)
- [Server launcher merge](https://github.com/jungcheolseung/Dune-Imperium/commit/3217cdc0)
- [Autosave in local mode](https://github.com/jungcheolseung/Dune-Imperium/commit/82bdfe86)
- [Game-like effects, stages 1–3](https://github.com/jungcheolseung/Dune-Imperium/commit/174be90a)
- [Game-like effects, stages 4–5 and AI pace](https://github.com/jungcheolseung/Dune-Imperium/commit/3d2cba0a)
- [Play clock](https://github.com/jungcheolseung/Dune-Imperium/commit/e8cca927)
- [Feedback batch of October 11](https://github.com/jungcheolseung/Dune-Imperium/commit/e899ebb8)
- [Sounds](https://github.com/jungcheolseung/Dune-Imperium/commit/5cb16976)
- [Feedback batch after the second game (with the Victory Point ledger)](https://github.com/jungcheolseung/Dune-Imperium/commit/53228a15)
- [Korean names for board spaces and Objective cards](https://github.com/jungcheolseung/Dune-Imperium/commit/4d906108)
- [Native Windows validation merge](https://github.com/jungcheolseung/Dune-Imperium/commit/dbfcb793)
