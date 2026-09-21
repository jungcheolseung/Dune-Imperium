"use strict";

/* Every string the client writes that is not a rule term, a card, Leader or
   space name, or engine text: { ko, en } by "<file>.<name>". {{name}} is a
   hole the caller fills, {term} a rule term in the current language (see
   t() and tNode() in i18n.js). */
const UI_TEXT = {};
