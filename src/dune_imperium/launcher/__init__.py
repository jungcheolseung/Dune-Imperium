"""A window that starts and stops the play server (docs/server-launcher-plan.md).

The launcher supervises ``dune_imperium.cli.server`` as a child process; it
never imports the web app. Everything but ``gui`` runs without a display.
"""
