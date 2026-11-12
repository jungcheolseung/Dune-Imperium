+++
title = "Hidden information: the search AI's worlds, a whole-server sweep, and passes in Scouts"
description = "The worlds the search AI builds for each decision kept the real values of some things its seat cannot see; we fixed that. A sweep of everything the play server sends to each seat across whole games found one leak, and now a seat with no line to take gets the ordinary pass too."
date = 2026-11-11T17:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-08"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/reviews/2026-11-hidden-info-sweep.md", "docs/rules/information-visibility.md", "docs/rules/open-questions.md", "docs/worklog/2026-11.md"]
+++

## Background

In this game each seat can see different things: hands, deck order, face-down cards. If anything a seat does not know leaks from the engine, the server or an AI seat, the game is not fair. Since [the first audit on November 3]({{< relref path="devlog/2026-11-03-cloud-reviews.md" lang="en" >}}) much more has become visible (deferred effects, reasons for choices you cannot make, the course chart, public hand views, splitting the Agent turn). This time we did three things.

## The search AI's worlds (merge `4121b6d2`, November 8)

While building the spectator world for [the course chart]({{< relref path="devlog/2026-11-08-after-game-views.md" lang="en" >}}), we found that the worlds the search AI and the rollout seat build for each decision kept a few things that seat cannot see at their real values. The playouts knew them.

- An opponent Y'rkoon's face-down Navigation cards (only that seat sees them `[Bloodlines p. 12]`)
- Kota Odax's Secret Project and the order of the Tech tile stacks (shuffled face down `[Bloodlines p. 6]`)
- The identity of Twisted cards drawn by Piter De Vries
- The order of the Tleilaxu deck and the Skill pile, which nobody sees

Now everything outside the observing seat is dealt again from one pool, and the seat's own things (its own slots, its own Secret Project, the cards it holds) stay as they are. Pools are sorted and then shuffled in a fixed order, so a world is a function only of what the seat knows and of the random numbers. This decides no new rule interpretation; it treats hidden things as hidden, so it was merged without a match measurement. Since the same random numbers now produce different worlds (with the same distribution), games with a search seat change from its first search decision.

- 39 tests: whether twin positions that differ only in what the observing seat cannot see give the same world from the same random numbers, and so on. 22 mutations that each remove one re-deal all fail.
- An independent review confirmed one defect that predates this branch. In Uprising + Rise of Ix + CHOAM, the starting Contract choice sits on top of Kota's Secret Project choice, so building a world placed a tile in two zones (all 33 setup playouts of the rollout seat failed in that game). It shared a root with a finding from another tool (Codex), and both were fixed.

## Whole-server sweep, second round (merge `dbce16e0`, November 11)

We built a tool that sweeps everything the play server sends to each seat and remote browser across whole games. Each human seat has a token, seeded AIs choose among the actions the server offers, and undo, AI hand-overs and turn-end confirmations are mixed in. At every decision and seat it compares the view, summary, log and action rows with a twin in which only what that seat does not know is changed, and it also checks save and load and the search AI's worlds. We first confirmed that it catches all five deliberately planted leaks.

16 rule combinations (Uprising and the original game × every expansion, Scouts, Ix partial modes, Epic, games mixed with AIs and more) × 4 seeds = 64 games were played to the end: 60,078 decisions, 229,736 twin comparisons, 1,852 undos and 186 AI hand-overs. Separately, the search seat's candidates, values and choices matched the twin in 711 decisions.

It found one thing (low). In the original game + Arrakeen Scouts, Desert Gift and No Coming Back revealed whether a seat's hidden hand held the card the line requires, through wording everyone could see ("nothing can be taken" against "… or pass") and through differences in the log and events. Only the owner sees the identity of the cards in a hand (information visibility rules, OQ-010). It came from the October implementation "even an event with a pass offers no pass when there is no line to take" (OQ-071). The app AI, when counting opponents' hands and decks, also counted the cards Ilesa Ecaz had set aside (it never changed a move).

## Passes in Scouts and the app AI (merge `f4f088d9`, codec v172)

The user chose "(a)", fixing it in the engine, and widened it to the sale events of the same shape, Rebuild Infrastructure and the cost lines of revealed secret choices.

- In a Scouts choice with a printed pass, a seat with no line to take now gets the same pass row and the same wording as other seats. Greyed rows and their reasons appear only on that seat's screen. Only choices without a pass keep a confirmation row (OQ-071 re-ruled, OQ-085 (c) extended).
- A record bridge moves old confirmation rows to the pass. All 20 human saves replayed (8 unchanged, 12 through the bridge).
- The app AI counts Ilesa's set-aside cards as part of the public deck composition (they are revealed on the second turn). That moves change in 9 of 40 Ilesa games is intended, and in 40 twin games that differ only in the set-aside cards all 9,428 decisions were the same.
- After the fix, rerunning the sweep on the games that produced the finding gave zero findings. The two twin tests (`xfail` before the fix) now pass.

## What is left

- That a host can see hands in a copy loaded from a save is kept as trust by design.
- The search AI's worlds forget who holds a Twisted card given by Piter and how many Twisted cards are in an opponent's hand. That errs on the side of forgetting what is known, and it was always so.
- The sweep found what it found on chosen combinations and seeds. Not finding a leak does not prove there is none.

## References

- Re-dealing the search AI's worlds ·
  Whole-server sweep ·
  Scouts passes and the app AI
- Sweep report ·
  [Information visibility rules](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/information-visibility.md) ·
  [Open questions](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/open-questions.md) ·
  Work log, November
