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
3. Verify the baseline before changing code:

```bash
uv sync --extra rl
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

If the handoff's numbers (test count, `ACTION_CODEC_VERSION`, catalog sizes)
disagree with the executable repository, trust the code and update the handoff
in the same work unit.

## Delegation with the Agent tool

- Use the main session as the controller, per the delegation policy in
  `AGENTS.md`.
- For bounded implementation slices (one card's play data plus its regression
  tests, repetitive edits, a known-cause bug fix) spawn a `general-purpose`
  subagent with a self-contained prompt: files to touch, acceptance criteria,
  and the tests it must pass. Ask it to report blockers instead of making
  design decisions.
- Use `Explore` subagents for read-only fan-out searches across the rules and
  content packages when you only need the conclusion.
- Review every delegated diff and rerun pytest/ruff/mypy before committing.

## Rule changes: verify before you act

Never change what the engine does under a rule — including "fixing" it after a
code-review finding — without first opening the relevant `docs/rules/*.md`
section and quoting the sentence and citation that justifies the change. If
the docs are silent, add an entry to `docs/rules/open-questions.md` instead of
guessing. Past failures of this discipline are logged in `docs/lessons.md`;
read it at session start.

## Conventions worth knowing

- Card slices follow the `Play <Card>` / `Document <Card>` commit pairing; keep
  code and its tests in the `Play` commit and roadmap/audit updates in the
  `Document` commit.
- Temporary files (official-rule working copies, scratch scripts) go under the
  session scratchpad or `/tmp`, never into the repository.
- `rulebooks/*.pdf` are the user's local reading copies; use
  `scripts/prepare_official_rules.py` and the official URLs instead unless the
  user explicitly asks you to open a local PDF.
