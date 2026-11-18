"""A hand-written user module with a worker thread: the free space of ``/`` every 30 seconds."""

import shutil
import threading

from tess_shell import Module


class DiskUse(Module):
    def start(self):
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.poll, name="diskuse", daemon=True)
        self.thread.start()

    def poll(self):
        while not self.stopped.is_set():
            usage = shutil.disk_usage("/")
            self.ctx.send("usage", f"/ {usage.free // 2**30} GiB free")
            self.stopped.wait(30)

    def stop(self):
        self.stopped.set()
