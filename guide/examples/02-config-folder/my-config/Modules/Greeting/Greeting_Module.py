"""Greeting: a module of your own. The class name is the module's Name."""

from __future__ import annotations

from datetime import datetime

from tess_shell import Module


class Greeting(Module):
    def start(self) -> None:
        self.tick()
        self.ctx.on_tick("minute", self.tick)

    def tick(self) -> None:
        hour = datetime.now().hour
        text = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.ctx.send("greeting", text)  # every use of the module gets it
