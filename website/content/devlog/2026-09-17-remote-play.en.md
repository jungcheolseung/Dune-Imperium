+++
title = "Remote games with friends"
description = "Separate seat claims and administration, then add confirmation, autosave, and recovery for remote play."
date = 2026-09-17
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-17"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/remote-play-guide.md"]
+++
## From one PC to several browsers

Local hot-seat play expanded into remote rooms. Seat claims and admin access were separated, with each browser receiving its own seat's permitted information.

Multiple clients needed to stay in step with server state. Client synchronization and turn confirmation were refined, and human turn handover triggered autosave.

## Rehearsal on a real address

A Tailscale-address rehearsal checked multiple clients, play, saving, and recovery. It exposed a startup problem: the CLI could print an admin link before discovering that the server could not bind the address. Address/port checks and clearer failure output were added.

This validated the remote mechanism and operation path. Usability feedback from actual games with friends follows in the October records.

## References

- [Add remote access to the play server: seat claims and an admin key](https://github.com/jungcheolseung/Dune-Imperium/commit/e6b9c9da)
- [Autosave a remote game whenever its turn passes on](https://github.com/jungcheolseung/Dune-Imperium/commit/903090d6)
- [Rehearse a remote game on the host's Tailscale address](https://github.com/jungcheolseung/Dune-Imperium/commit/ff380679)
