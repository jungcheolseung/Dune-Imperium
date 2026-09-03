# Repository instructions

Read `README.md` before making architectural or rules-related changes. Before
continuing implementation in a new session, also read
`docs/development-handoff.md` for the current baseline and next work item. If
that status conflicts with code or tests, treat the executable repository as
authoritative and update the handoff in the same work unit.

## Commit workflow

- During implementation tasks, proactively commit completed work in small,
  coherent units instead of leaving the whole implementation uncommitted.
- Verify each implementation unit with the relevant tests and quality checks
  before committing it. Do not commit a knowingly broken intermediate state.
- Keep code and its regression tests in the same commit. When a rule or card
  implementation also changes project documentation, use separate focused
  commits when that makes the history clearer; follow the existing `Play ...`
  and `Document ...` pattern for card slices where appropriate.
- Use concise imperative commit messages that describe the completed behavior.
- Never stage or commit unrelated or pre-existing user changes. Inspect the
  worktree before staging, stage explicit paths, and preserve any dirty state
  that is outside the current task.
- Do not rewrite, amend, squash, or otherwise alter existing commits unless the
  user explicitly asks for that history operation.

## Rule sources

- The implementation target is the four-player base game of Dune: Imperium -
  Uprising.
- Prefer Dire Wolf Digital's official online resources:
  - https://www.direwolfdigital.com/dune-imperium/resources/
  - https://www.direwolfdigital.com/dune-imperium/resources/diu_rules
- Files under `assets/rulebooks/` (the private assets checkout) are the user's local reading copies. Do not load,
  extract, summarize, modify, or delete those PDFs by default.
- Read a local PDF only when the user explicitly requests it or when the official
  source is unavailable and the task cannot otherwise proceed.
- Retrieve only the sections needed for the current rule question. Record
  ambiguous interpretations in project documentation and protect chosen rulings
  with tests.
- Use `scripts/prepare_official_rules.py` when page-indexed text from an official
  PDF is needed. Keep its generated PDFs and text outside the repository. Update
  `scripts/official-rule-sources.json` and `docs/rules/sources.md` together when
  an official file version or checksum changes.
- Before implementing a rule, consult `docs/rules/README.md` and its cited source.
  This applies equally to bug fixes, code-review findings, and test
  expectations: a reviewer's or your own reading of a rule is not evidence.
  Quote the `docs/rules/` line (with its `[Main p. N]` / `[FAQ p. N]` citation)
  in the commit or test before changing rule behaviour, and record any
  mistake of this kind in `docs/lessons.md`.
  Do not silently fill a gap in the official documents. Add it to
  `docs/rules/open-questions.md`, and clearly distinguish any later project
  convention from an official rule.
- When an official rule, FAQ ruling, or card transcription changes, update its
  source citation and relevant regression test in the same work unit.

## Card and image sources

- Use https://dunecardshub.com/uprising to find Uprising leader, deck, contract,
  and other card images or card-level reference data.
- Use https://dunecardshub.com and select another expansion when that expansion's
  card material is needed.
- Treat Dune Cards Hub as a card and visual reference, not as the authority for
  rules adjudication. Official Dire Wolf Digital rules and supplements take
  precedence when sources conflict.
- Before adding or redistributing image files in the project, verify the needed
  scope and applicable usage terms.

## Delegation

Keep requirements interpretation, repository-wide reasoning, architecture and
design, task decomposition, ambiguous debugging, integration decisions, and the
final review in the main session.

Delegate to a subagent only bounded implementation work that is clearly
specified, limited in scope, and mostly implementation rather than design:
unit-test creation, repetitive edits, small refactoring, or straightforward bug
fixing with a known cause. Do not delegate architecture decisions, work that
needs broad repository understanding, ambiguous root-cause analysis, or major
cross-cutting changes.

When delegating:

- Provide only the context needed for the task.
- Specify relevant files/directories when possible.
- State explicit acceptance criteria.
- Require relevant tests.
- Instruct the subagent to report blockers rather than make broad design
  decisions.

After delegated implementation, the main session must review the changes and
verify relevant tests before considering the task complete.

Tool-specific configuration (model names, reasoning effort) lives in the tool's
own entry file, e.g. `CLAUDE.md` for Claude Code. This file stays tool-neutral.
