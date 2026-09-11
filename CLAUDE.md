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

### Workflow (ultracode) model policy

A workflow `agent()` call that omits `model` inherits the main session's
model, so an ultracode run on Fable spends Fable tokens on every subagent
(noticed 2026-09-11). Apply the delegation policy inside workflow scripts too:

- Finder, scout, collection and mechanical-edit stages: `model: 'sonnet'`
  (or `'haiku'` for read-only searches) with `effort: 'low'`, or reuse the
  project subagents via `agentType: 'repo-scout'` / `agentType:
  'card-implementer'`, whose frontmatter sets the cheap model.
- Only verify/refute, judge and synthesis stages inherit the session model.
- Do not reach for ultracode on a bounded slice (one card, one known-cause
  fix); a single `card-implementer` Agent call is cheaper than a workflow.

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

### Background-task ledger (mandatory; broken three times, see `docs/lessons.md` 2026-09-11)

The harness has no "list tasks" tool, so the task list is one you keep yourself:

1. **Right after every launch** that returns a task id (`run_in_background`
   Bash, Monitor, Agent, Workflow), append one line
   `<task id>  <what it does>` to `<scratchpad>/tasks.md`. No exceptions, no
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
- Temporary files (official-rule working copies, scratch scripts) go under the
  session scratchpad or `/tmp`, never into the repository.
- `assets/rulebooks/*.pdf` are the user's local reading copies; use
  `scripts/prepare_official_rules.py` and the official URLs instead unless the
  user explicitly asks you to open a local PDF.
