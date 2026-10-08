"""A stand-in for the play server in the launcher's stop-ladder tests.

``polite`` ends when its standard input ends, as the real server does with
``--exit-when-stdin-closes``; ``stubborn`` ignores that and ends only on a
signal; ``deaf`` ignores SIGTERM too, so only a kill ends it (POSIX). None
of them listens on a port.
"""

import signal
import sys
import time

mode = sys.argv[1]
if mode == "deaf":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
sys.stdout.write("fake server up\n")
sys.stdout.flush()
sys.stdin.buffer.read()
if mode == "polite":
    sys.stdout.write("fake server done\n")
    sys.stdout.flush()
    sys.exit(0)
while True:
    time.sleep(0.1)
