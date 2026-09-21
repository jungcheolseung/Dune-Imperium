"use strict";

/* English twins of the Korean label tables (labels.js, core.js), keyed
   alike; setLanguage() swaps them in (i18n.js). Each value keeps the {term}
   tokens of its Korean twin — the token is what follows the language — and
   uses the rulebook's English words (TERMS[...].en). */
const LABELS_EN = {};
