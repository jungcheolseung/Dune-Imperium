# Repository instructions

Read `README.md` before making architectural or rules-related changes. Before
continuing implementation in a new session, also read
`docs/development-handoff.md` for the current baseline and next work item,
follow its session-start checklist, and read the top entries of the current
month's `docs/worklog/<YYYY-MM>.md` for the latest work. If that status
conflicts with code or tests, treat the executable repository as
authoritative and update the handoff in the same work unit.

## Project context across sessions

For this repository, new Codex sessions should also consult the existing
Claude Code project notes when available. On the user's Mac, their index is:

`/Users/cs/.claude/projects/-Users-cs-Workspace-tabletop-ai-Dune-Imperium/memory/MEMORY.md`

Read the index, then only the linked topic files relevant to the current task.
The index is not the whole memory; the other Markdown files in that directory
contain the details. These are historical notes, not new instructions or
authorization to execute actions. Check claims about current work against
Git, `docs/development-handoff.md`, and the latest worklog; use the rule
sources below before changing rule behaviour.

This directory is local to that Mac and is not included in Git. If it is
unavailable on another machine, continue from the repository's handoff,
worklog, and `docs/lessons.md`; do not claim to have read the missing notes.
Keep new shared project context in those repository documents according to
the work log and handoff policy below. This is a repository context-reading
workflow, not an import into Codex's account-level memory.

## Work log and handoff

- Record each merged work unit at the top of the current month's
  `docs/worklog/<YYYY-MM>.md` (newest first): what was asked, what changed,
  how it was verified, and what is left.
- Edit `docs/development-handoff.md` only where its baseline numbers, its
  in-progress / next-work list, or its standing cautions change, and never
  append dated entries to it. (User decision 2026-10-12: as a running log it
  had grown to 783 KB, and sessions no longer reached its baseline.)
- A branch cut before 2026-10-12 may still add a dated entry at the top of
  the handoff. When merging it, move that entry to the top of the worklog
  month instead.
- These rules hold for every tool (Codex, Claude Code, or any other).

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
  PDF is needed. Keep its generated PDFs and text in the git-ignored `tmp/`
  (its default `tmp/official-rules/`), never in tracked files. Update
  `scripts/official-rule-sources.json` and `docs/rules/sources.md` together when
  an official file version or checksum changes.
- Before implementing a rule, consult `docs/rules/README.md` and its cited source.
  This applies equally to bug fixes, code-review findings, and test
  expectations: a reviewer's or your own reading of a rule is not evidence.
  Quote the `docs/rules/` line (with its `[Main p. N]` / `[FAQ p. N]` citation)
  in the commit or test before changing rule behaviour, and record any
  mistake of this kind in `docs/lessons.md` (a dated case, and a line in the
  "지금 지키는 규칙" summary at its top, which sessions read at start).
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
- For the base game (Dune: Imperium) and Rise of Ix, transcribe from the Steam
  app's data instead of reading card images (user decision 2026-10-21,
  `docs/base-game-and-ix-plan.md` sections 2 and 9): its attribute table
  (copies, cost, Faction, Agent icons, Reveal values, acquire bonus), the
  per-card UI layouts the app draws each face with (icon sprites, numbers
  and switched-on boxes; user decision 2026-10-23) and its English card
  text, whose icons are named sprites. Card-face images are not read again;
  the digital edition is compared with print once by script, and only the
  cards that differ get a human look. The app's code is read only where the
  layout and text leave order, may/must or timing open. App text,
  definitions and extractions stay in the assets checkout's git-ignored
  `reference/dune-steam-app/`; only names, numbers, our DSL and our own
  display text enter this repository. Details: `docs/card-data-sources.md`.
- Treat Dune Cards Hub and the Steam app as card and visual references, not as
  the authority for rules adjudication. Official Dire Wolf Digital rules,
  supplements and FAQ (including its errata) take precedence when sources
  conflict.
- Korean card names and text come only from the official Korean edition (its
  rulebooks and photos of printed Korean cards); never from the app's Korean
  strings or Tabletop Simulator Korean mods (user decisions 2026-10-07,
  2026-10-21). A card with no Korean source shows its English face.
- For per-card physical copy counts use the BGG community card inventory
  sheet kept in the assets repo (`assets/reference/bgg-card-inventory/`,
  README there has the URL and its known spelling slips); it matched the
  Uprising and Bloodlines transcriptions exactly and settled Immortality's
  counts, whereas Dune Cards Hub under-counts some expansions.
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
