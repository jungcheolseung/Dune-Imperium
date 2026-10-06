# Claude Code entry point

@AGENTS.md

The shared repository instructions above (rule sources, commit workflow, card
sources, delegation policy) apply verbatim. This file only adds Claude Code
specifics.

## Session start

1. Read `README.md` and `docs/development-handoff.md`; the handoff names the
   current baseline and the next work item.
2. Run `git status --short` and `git log --oneline -10`; never overwrite
   pre-existing user changes.
3. Run `git fetch origin` and compare both directions
   (`git log --oneline origin/master..master` and `master..origin/master`).
   This repository is worked on from multiple machines, so a stale clone
   silently duplicates remote work (it cost a full session on 2026-08-31).
   If the remote is ahead, align with it (or ask) before starting, and trust
   the fetched baseline over this clone's handoff numbers.
4. Verify the baseline before changing code:

```bash
uv sync --extra rl --extra ui --extra train
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

If the handoff's numbers (test count, `ACTION_CODEC_VERSION`, catalog sizes)
disagree with the executable repository, trust the code and update the handoff
in the same work unit.

## Delegation with the Agent tool

- Use the main session as the controller, per the delegation policy in
  `AGENTS.md`. The main session runs the expensive model; delegate token-heavy
  bounded work to the cheaper project subagents in `.claude/agents/` so the
  expensive model is spent on design, rules interpretation, and review.
- For bounded implementation slices (one card's play data plus its regression
  tests, repetitive edits, a known-cause bug fix) spawn the `card-implementer`
  subagent (Sonnet) with a self-contained prompt: files to touch, acceptance
  criteria, the tests it must pass, and the `docs/rules/*.md` quote with its
  citation for any rule behaviour involved. It is instructed to report
  blockers instead of making design decisions.
- For read-only fan-out searches across the rules and content packages, when
  you only need the conclusion, use the `repo-scout` subagent (Haiku). Its
  rules summaries are pointers, not evidence: before changing rule behaviour,
  the main session must still open the cited `docs/rules/*.md` section itself.
- Fall back to the built-in `general-purpose` / `Explore` types only when a
  task fits neither project subagent.
- Review every delegated diff and rerun pytest/ruff/mypy before committing.

## Verifying UI changes: scale the checks to the risk

User decision, 2026-09-27. In UI stages 7-10 every item, however small, went
implement → independent review → fix → re-review, and those checking stages
took 47% of about 20 agent-hours (running the tests themselves took only about
21%). The numbers and the reasoning are in `docs/lessons.md` (2026-09-27).

- **Low risk.** Wording, labels, CSS and layout, help text, and display-only
  Korean twins (`display/*_ko`). The implementer runs the targeted pytest and
  the e2e scripts that cover the code it touched. No separate review agent:
  the main session reads the diff itself.
- **High risk.** Remote sync and polling, hidden information (what a seat may
  see), engine events and their payloads, undo/save/replay, and the list of
  actions a seat is offered. Keep an independent review agent for these.
- Fix a review finding directly, either the reviewer or the main session.
  Send it back for re-review only when the fix changes the design.
- For each item, run only the tests that cover it. Run the full pytest, ruff,
  mypy and every e2e script once per batch, before a merge or a handoff:
  `scripts/e2e/run_all.py` runs the e2e scripts 4 at a time (see its README).

## Rule changes: verify before you act

Never change what the engine does under a rule — including "fixing" it after a
code-review finding — without first opening the relevant `docs/rules/*.md`
section and quoting the sentence and citation that justifies the change. If
the docs are silent, add an entry to `docs/rules/open-questions.md` instead of
guessing. Past failures of this discipline are logged in `docs/lessons.md`;
read it at session start.

## Long-running commands

Soaks, sweeps, tournaments and the full test suite take minutes. Run them with
`run_in_background: true` and then **do other work** -- a completion
notification arrives on its own. Do not write a shell loop to wait for them.

- To block on a task deliberately, use `TaskOutput` with `block: true`. To end
  one, use `TaskStop` with its task id; `pkill` on the id does not deregister
  it.
- If a shell wait is unavoidable, wait on a file or a sentinel string, never on
  process presence. `pgrep -f <pattern>` matches full command lines
  **including the waiting shell itself**, so `until ! pgrep -f "pytest"` never
  exits. Use `pgrep -x`, or `pgrep -f pat | grep -vw $$`.
- Stop a task as soon as it stops being useful, and sweep for leftovers before
  wrapping up. When reporting what is running, check the task list, not `ps` --
  they are tracked separately (`docs/lessons.md`, 2026-09-10).
- A finished task can still leave processes: a worker pool whose parent died
  (`BrokenProcessPool`, a killed run) never exits by itself. Before wrapping
  up, and before launching anything memory-hungry, run
  `ps -A -o pid,ppid,pgid,etime,command | grep '[m]ultiprocessing'`; lines with
  **ppid 1** are orphans (36 of them held 947 MiB here for 2.7 days,
  `docs/lessons.md` 2026-09-19).

### Background-task ledger (mandatory; broken three times, see `docs/lessons.md` 2026-09-11)

The harness has no "list tasks" tool, so the task list is one you keep yourself:

1. **Right after every launch** that returns a task id (`run_in_background`
   Bash, Monitor, Agent, Workflow), append one line
   `<task id>  <what it does>` to `tmp/claude/<session id>/tasks.md` (see the
   temporary-files rule below). No exceptions, no
   "I'll remember it".
2. **Before saying anything about what is or is not running** -- "정리 완료",
   "남은 작업 없음", the closing recap, an answer to "지금 뭐 돌아가?" -- open
   that file and call `TaskOutput` with `block: false` on **every** id in it.
   Report from those results only. Log files, exit sentinels and `ps` say
   what the *job* did, not whether the *task* is still registered.
3. **Never use Monitor for a single completion.** A `tail -f | grep | while`
   pipeline keeps running after its own `exit`, because `tail -f` only dies on
   the next write to a log that has gone quiet. For "tell me when X finishes"
   use `run_in_background` Bash with a sentinel wait
   (`until grep -q 'exit=' log; do sleep 10; done`); the harness then sends
   one completion notification. Monitor is only for streams that go on
   producing events.
4. `TaskStop` every id in the ledger that is no longer useful, then mark it
   done in the file. A wrap-up with an unmarked id is not finished.

## Conventions worth knowing

- Card slices follow the `Play <Card>` / `Document <Card>` commit pairing; keep
  code and its tests in the `Play` commit and roadmap/audit updates in the
  `Document` commit.
- No file of this project lives outside the project directory (user decision,
  2026-10-06). Temporary files (official-rule working copies, scratch scripts,
  logs, the task ledger) go under the git-ignored `tmp/` at the project root —
  e.g. `tmp/claude/<session id>/` for a session's scratch work — not the
  session scratchpad or `/tmp`, and never into tracked files. Saves default to
  `saves/` and the search AI's network to `checkpoints/play/search.pt`
  (`dune_imperium.paths`). The one exception is the sibling private assets
  checkout `../Dune-Imperium-assets` behind the `assets` symlink.
- `assets/rulebooks/*.pdf` are the user's local reading copies; use
  `scripts/prepare_official_rules.py` and the official URLs instead unless the
  user explicitly asks you to open a local PDF.
