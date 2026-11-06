"""Lookups across every base game and expansion.

docs/content-core-refactor-plan.md stage 2B: an id names one printing
(docs/base-game-and-ix-plan.md 4.2 item 7), so one table per kind of
content holds every set's definitions -- board spaces, Conflicts, cards,
Leaders, Reserve stacks -- with the resolvers from instance ids and the
ability tables merged across sets. Each set package imports only
``content.core``; this package imports the sets.
"""
