"""The module the containment and reload measures act on. It logs ``start``, ``hang-begin`` and
``hang-end`` with the monotonic nanoseconds and its pid to ``$TESS_PROBE_DIR/Victim.log``. Once a
second a tick callback shows a counter; when the file ``$TESS_PROBE_DIR/hang`` exists the callback
removes it and sleeps for 10 seconds (the hang). ``VERSION`` is what a reload changes."""

import os
import time

from tess_shell import Module

VERSION = 1


class Victim(Module):
    def log(self, what):
        folder = os.environ.get("TESS_PROBE_DIR")
        if folder:
            with open(os.path.join(folder, "Victim.log"), "a") as out:
                out.write(f"{what} {time.monotonic_ns()} {os.getpid()} {VERSION}\n")

    def start(self):
        self.count = 0
        self.log("start")
        self.ctx.send("shown", f"v{VERSION}")
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.count += 1
        self.ctx.send("shown", f"v{VERSION} {self.count}")
        folder = os.environ.get("TESS_PROBE_DIR")
        trigger = os.path.join(folder, "hang") if folder else ""
        if trigger and os.path.exists(trigger):
            os.remove(trigger)
            self.log("hang-begin")
            time.sleep(10)
            self.log("hang-end")
