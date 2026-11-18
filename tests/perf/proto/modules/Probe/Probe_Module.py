"""The latency probe: a thread sends ``<seq>:<monotonic ns>`` on the harness's command and writes the
send time of every value to a file (the harness reads the surfaces' side from the shell). It runs in
the shell's process (A), or in a module process (B, C): the module is the same file.

Commands, one per line, on the FIFO ``$TESS_PROBE_DIR/probe.fifo``:
``single N GAP_MS`` (N values, one every GAP_MS), ``rate R SECONDS`` (R values a second for SECONDS),
``quit``. Each command ends with the send log ``probe-sent-<n>.log`` (``seq ns``) written whole.
"""

import os
import threading
import time

from tess_shell import Module


class Probe(Module):
    def start(self):
        folder = os.environ.get("TESS_PROBE_DIR")
        if folder:
            threading.Thread(target=self.serve, args=(folder,), name="probe", daemon=True).start()

    def serve(self, folder):
        seq = 0
        commands = 0
        while True:
            with open(os.path.join(folder, "probe.fifo")) as fifo:
                lines = fifo.read().splitlines()
            for line in lines:
                word = line.split()
                if not word:
                    continue
                sent = []
                if word[0] == "single":
                    count, gap = int(word[1]), int(word[2]) / 1000
                    for _ in range(count):
                        seq += 1
                        t = time.monotonic_ns()
                        sent.append((seq, t))
                        self.ctx.send("probe", f"{seq}:{t}")
                        time.sleep(gap)
                elif word[0] == "rate":
                    rate, seconds = float(word[1]), float(word[2])
                    step = 1.0 / rate
                    begin = time.perf_counter()
                    due = begin
                    end = begin + seconds
                    while due < end:
                        now = time.perf_counter()
                        if now < due:
                            time.sleep(min(due - now, 0.0005))
                            continue
                        seq += 1
                        t = time.monotonic_ns()
                        sent.append((seq, t))
                        self.ctx.send("probe", f"{seq}:{t}")
                        due += step
                elif word[0] == "quit":
                    return
                commands += 1
                path = os.path.join(folder, f"probe-sent-{commands}.log")
                with open(path + ".tmp", "w") as out:
                    out.write("\n".join(f"{s} {t}" for s, t in sent) + "\n")
                os.rename(path + ".tmp", path)
