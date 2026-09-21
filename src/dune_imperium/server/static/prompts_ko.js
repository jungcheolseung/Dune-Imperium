"use strict";

/* Korean for the engine's decision prompts (rules/*.py sends English). Keyed
   by the exact English sentence; PROMPT_KO_PATTERNS covers the formatted
   ones as [RegExp source, Korean with $1 for a group]. Rule words are {term}
   tokens, so the Korean is the glossary's (docs/rules/glossary-ko.md). The
   bodies are JSON so tests/server/test_i18n.py can read them. */
const PROMPT_KO = {};

const PROMPT_KO_PATTERNS = [];
