"""A stand-in for the play server in the launcher's stop-ladder tests.

``polite`` ends when its standard input ends, as the real server does with
``--exit-when-stdin-closes``; ``stubborn`` ignores that and ends only on a
signal; ``deaf`` ignores SIGTERM too, so only a kill ends it (POSIX);
``grandchild`` first starts a sleeping child that inherits its output pipe,
says the child's pid, and then behaves like ``polite``. None of them
listens on a port.
"""

import signal
import subprocess
import sys
import time

mode = sys.argv[1]
if mode == "grandchild":
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL
    )
    sys.stdout.write(f"grandchild {child.pid}\n")
    sys.stdout.flush()
    mode = "polite"
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
