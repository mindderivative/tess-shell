"""Uptime: a module of your own. The class name is the module's Name."""

from __future__ import annotations

from tess_shell import Event, Module, action


def read_uptime() -> str:
    """How long the machine has been up, from /proc/uptime, as '3h 07m' or '12m'."""
    with open("/proc/uptime") as f:
        minutes = int(float(f.read().split()[0]) // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


class Uptime(Module):
    def start(self) -> None:
        self.refresh_now()
        self.ctx.on_tick("minute", self.refresh_now)

    def refresh_now(self) -> None:
        self.ctx.send("uptime", read_uptime())  # every use of the module gets it

    @action
    def refresh(self, event: Event) -> None:
        # Run by a click on the module: On_Click { Action: Call, Target: "Uptime.refresh" }
        self.refresh_now()
