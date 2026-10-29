"""app_ai_seats.py on the original Dune: Imperium, so the batch runs both.

run_all.py runs a script once with fixed arguments; this one runs every
scenario of app_ai_seats.py with --base-game imperium (the app AI plays the
original game since stage P6, docs/app-ai-plan.md 12).
"""

import sys

import app_ai_seats

if __name__ == "__main__":
    sys.argv[1:] = ["--base-game", "imperium"]
    app_ai_seats.main()
