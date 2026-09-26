# Korean Leader text: the transcription record (2026-09-25)

`src/dune_imperium/display/leaders_ko.py` carries the Korean print of every
Leader face we have a Korean scan for. Two readers transcribed the scans
independently (A and B); a third compared them field by field and settled
every disagreement against the scan itself, at 2-5x zoom. This is that
record: the conventions, the disagreements and how each was settled.

Scans: `Dune-Imperium-assets/cards/ko/{uprising,bloodlines}/leader/*.webp`
(1460x1020); 18 faces. `reverend_mother_jessica` has no Korean scan and
stays English. The crop files named in the table below were cut from those
scans for the comparison and are not kept; re-cut them from the scan to
re-check a row.

## Output conventions

- Icons are written as braced tokens named after the keys in `src/dune_imperium/display/icons.py`:
  `{solari} {spice} {water} {persuasion} {troop} {sword} {draw} {intrigue} {trash} {spy} {recall_spy}
  {influence_any} {agent_icon_spy} {agent_icon_emperor} {agent_icon_spacing_guild}
  {agent_icon_bene_gesserit} {agent_icon_fremen} {agent_icon_landsraad} {agent_icon_city}
  {agent_icon_spice_trade}`. There is one new token, `{spy_deep_cover}` (gold and grey cylinders, Spy with
  Deep Cover = 잠복 스파이 `[Bloodlines p. 12]`), which has no icons.py key.
- A faction icon before `영향력 2` is printed as the tile glyph (the Agent icon), not the gold-chevron
  influence glyph, so it is `{agent_icon_<faction>}` (see `reconcile/ref_rulebook_icons.png`).
- A number printed inside an icon follows the token (`{spice}1`). An icon printed without a number stays bare
  (`{water}`, `{troop}`, `{draw}`). Numbers are never added.
- `\n` marks a printed line or column break that has no punctuation (Esmar's two columns, Liet's and Staban's
  case lists, Steersman's two boxes). Printed separators are kept as printed: `—또는—` / `—그리고—` with long
  dashes, and `-또는-` with short hyphens on Gaius only.
- Footnote markers print as a small dot-like asterisk. They are written as `*` throughout.
- Extra keys: `face_notes_ko` mirrors `LeaderFaceText.notes` (used only for Staban's Limited Allies), and
  `source_scan` is the scan path. `notes` is reconciliation commentary, not display text.

## Findings beyond transcription (for the main session)

1. **Chani, Fedaykin Maneuver:** the reward is two **draw** icons, not two troops. KO and EN cards agree
   (`crop_chani_signet.png`, `crop_chani_signet_EN.png`; compare the draw icon in `crop_muaddib_signet.png` and
   the troop cube in `crop_piter_signet.png`). `display/leaders.py` ("Recruit 2 troops"),
   `docs/implementation-audits/leaders.md` ("water → 2 troops") and `rules/leader_abilities.py`
   `_apply_chani_water_payment` (which recruits 2) all disagree with the print. This is a rules change: it
   needs the `docs/rules` citation step before anyone touches it.
2. **Count Hasimir Fenring, Corrino Liaison:** the Spy icon is **Spy with Deep Cover** (gold cylinder behind a
   grey one; `crop_fenring_signet_icons.png`), the same icon as on the Deliver Supplies contract
   (`ref_en_contract_deliver_supplies_deepcover.png`). The EN card has it too (`ref_EN_fenring_bottom.png`).
   The engine offers a plain Spy placement (`_leader_spy_placement_actions(..., EMPEROR_POST_IDS)`), and the
   audit and English text say "Spy". A and B both missed it.
3. **Chani's name** is printed `챠니` (`crop_chani_name.png`), as in `display/names_ko.py`. A and B both
   wrote `찬니`.
4. Smaller differences between the print and the English display text, for information only: Feyd prints no
   "once". Gurney, Duncan and Esmar print 6-player footnotes (10 / 보너스 토큰 / 팀원도 포함). Margot's Signet is
   just "City icon 에 Spy".

## Every disagreement, and how it was settled

| # | Leader | Field | A | B | Decision (printed) | Evidence |
|---|---|---|---|---|---|---|
| 1 | chani | ability_text | sentence only | sentence + "(트랙 도해: …)" summary | A: the sentence only. The track is icons only and is described in `notes` | `crop_chani_ability.png`, `crop_chani_track.png` |
| 2 | chani | signet_text | `[Fremen] 영향력 2: {water} → {draw}{draw}` | `[프레멘] 영향력 2: {water}1 → {troop}{troop}` | A: `{agent_icon_fremen} 영향력 2: {water} → {draw}{draw}` (no number on the water; the icons are draw cards) | `crop_chani_signet.png`, `crop_chani_signet_EN.png`, `crop_muaddib_signet.png`, `crop_piter_signet.png` |
| 3 | count_hasimir_fenring | ability_text | `카드 1장을 {trash}할 때마다` | `카드 1장을 폐기할 때마다` | B: the word 폐기 is printed | `crop_fenring_ability.png` |
| 4 | count_hasimir_fenring | signet_text | `{trash}해도 됨 … [Emperor] 에 {spy}` | `폐기해도 됨 … [황제] 에 {spy}` | B for 폐기. Both wrong on the icon: `{agent_icon_emperor} 에 {spy_deep_cover}` | `crop_fenring_signet.png`, `crop_fenring_signet_icons.png` |
| 5 | duncan_idaho | ability_text | `비용이 [cost -2] 감소` | `비용이 {solari}2 감소` | B: the same silver coin as Fenring's Solari icon | `crop_duncan_ability.png`, `crop_duncan_cost_icon_vs_fenring_solari.png` |
| 6 | esmar_tuek | ability_text | `…: {solari}1. 다른 플레이어가…` | `…: {solari}1  다른 플레이어가…` | Neither. The print has two columns with no punctuation, so `\n` | `crop_esmar_ability.png` |
| 7 | feyd_rautha_harkonnen | ability_text | `[recall Spy] → {sword}{sword}` | `{spy}(소환) → {sword}{sword}` | Same reading. The token is `{recall_spy}` (cylinder + up arrow = rulebook recall_spy) | `crop_feyd_ability.png` |
| 8 | gaius_helen_mohiam | signet_text | `[Landsraad] 에 {spy} -또는- …` | `[랜드스래드] 에 {spy} -또는- …` | Naming only: `{agent_icon_landsraad}`. The short-hyphen `-또는-` is as printed | `crop_gaius_signet.png` |
| 9 | gurney_halleck | signet_text | `{troop}` | `{troop} (아이콘만 인쇄됨…)` | A. B's annotation is not printed | `crop_bottom_Gurney_Halleck.png` |
| 10 | kota_odax_of_ix | signet_text | `-또는- … 1개 {trash} →` | `—또는— … 1개 폐기 →` | B: long-dash separator, and the word 폐기 is printed | `crop_kota_signet.png` |
| 11 | lady_jessica | ability_text | `[Bene Gesserit]` | `[베네 게세리트]` | Naming only: `{agent_icon_bene_gesserit}` | `crop_bottom_Lady_Jessica.png` |
| 12 | lady_margot_fenring | ability_text | `[Bene Gesserit]` | `[베네 게세리트]` | Naming only: `{agent_icon_bene_gesserit}` | `crop_margot_ability.png` |
| 13 | lady_margot_fenring | signet_text | `{spy} 에 [observation post]` | `[도시] 에 {spy} (아이콘만 인쇄됨…)` | B, without the annotation: `{agent_icon_city} 에 {spy}` (blue disc = City) | `crop_margot_signet.png` |
| 14 | liet_kynes | signet_text | `[Landsraad]: [Emperor] 영향력 2: {water} [City]: … [Spice Trade]: …` | `[랜드스래드]·[황제] 영향력 2: {water}1 / …` | A's structure: "Landsraad icon:" then "Emperor icon 영향력 2: water". There is no `·`, and the water has no number | `crop_liet_signet.png` |
| 15 | muad_dib | signet_text | `{draw}` | `{draw} (아이콘만 인쇄됨…)` | A. B's annotation is not printed | `crop_muaddib_signet.png` |
| 16 | princess_irulan | ability_text | `[Emperor]` | `[황제]` | Naming only: `{agent_icon_emperor}` | `crop_irulan_ability.png` |
| 17 | princess_irulan | signet_text | `카드 1장 {trash}.` | `카드 1장 폐기.` | B: the word 폐기 is printed | `crop_irulan_signet.png` |
| 18 | shaddam_corrino_iv | signet_text | `{solari}1 {troop} -또는- {solari}3 → [Influence: any Faction]` | `{solari}1{troop} —또는— {solari}3 → {influence}(팩션 선택)` | Mixed: long-dash `—또는—` (B), `{solari}1 {troop}` with the printed gap, and `{influence_any}` (gold `?` chevron) | `crop_shaddam_signet.png` |
| 19 | staban_tuek | signet_text | `[Emperor]/[Spacing Guild]/[Bene Gesserit]/[Fremen]` | `[황제]·[우주 항행 길드]·…` | A: ` / ` is printed between the four icons (not `·`). The line breaks are `\n` | `crop_staban_signet.png` |

Structural differences that are not text: A kept Staban's and Steersman's two boxes as lists, B as `abilities[]`.
Settled by mirroring the English content (`content/uprising/leaders.py`): Staban's ability is 스파이스 밀수 and
한정된 조력자 goes to `face_notes_ko`. Steersman's ability name is `기이한 모습 / 스파이스를 갈구하다`, and both
texts go in `ability_text_ko` with editorial `name: ` prefixes (`crop_staban_abilities.png`,
`crop_steersman_abilities.png`).

## Fields where A and B agreed but the print differs (corrected)

| Leader | Field | A = B | Printed | Evidence |
|---|---|---|---|---|
| chani | name_ko | 찬니 | **챠니** | `crop_chani_name.png` |
| count_hasimir_fenring | signet_text | `{spy}` | `{spy_deep_cover}` | `crop_fenring_signet_icons.png` |
| lady_amber_metulli | signet_text | `-그리고-` | `—그리고—` (long dashes) | `crop_dash_styles_amber_gaius_shaddam.png` |
| gaius_helen_mohiam | ability_text | `{spy}` (eye glyph) | `{agent_icon_spy}` (eye = Spy Agent icon; both noted the eye but used `{spy}`) | `crop_gaius_ability.png` |

All other agreed fields were checked against the bottom-band crops and match: every name except Chani's
agrees with `display/names_ko.py`, along with the ability and Signet names and texts of Gurney, Amber, Feyd,
Jessica, Muad'Dib, Piter, Steersman and Shaddam (`crop_bottom_*.png`) and those of Esmar, Kota, Liet, Duncan
and Irulan (their crops above).

## Not available / low confidence

- **reverend_mother_jessica: no Korean scan.** `cards/ko/uprising/leader/` has only `Lady Jessica.webp`
  (front face). Its object in the transcription has no Korean text. A possible source is the Korean TTS mod
  card sheets (workshop 3092549193 / 3446667675 / 3025517639), which this task did not open.
- Duncan's Signet: the mark after `보유하고 있다면` is blurred (`crop_duncan_signet_line3.png`). The agreed
  comma is kept.
- Footnote marker glyph (`*` vs `•`): normalized to `*`.

## Glossary notes (docs/rules/glossary-ko.md)

- trash and discard: every printed trash on these faces is the word **폐기** (Fenring ×2, Irulan, Kota) or the
  X-card icon (Liet). 버리기 does not appear.
- Printed words that are **not** rows in the glossary, and would need a row citing the card print before UI
  use: 정탐하고 있는 (Staban), 기억 / 이 지도자를 뒤집음 (Jessica), 훈련 트랙 / 페이드 토큰 (Feyd), 보너스 스파이스
  (Esmar), 동맹 팩션 (Amber), 팀원 / 보너스 토큰 (6-player footnotes), 게임 시작 (Piter, Kota, Steersman).
- The print uses **소환** both for recalling a Spy (스파이를 소환, Gaius) and for summoning a sandworm (모래벌레를
  소환, Liet). The glossary only has the Recall sense.
- The print names board spaces in Korean (시치 타브르, 튜엑의 시치, 소드마스터 게임판 장소, 메이커 게임판 장소).
  Glossary rule 3 keeps UI space names in English, so the main session must decide between the printed text
  and the policy.
