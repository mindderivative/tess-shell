"""Tally: a counter. The class name is the module's Name."""

from __future__ import annotations

from tess_shell import Event, Module, action
from tess_shell.modules.context import UseRecord


class Tally(Module):
    def start(self) -> None:
        # one instance serves every use, so the counts are kept by use key
        self.counts: dict[str, int] = {}
        for use in self.ctx.uses.values():
            self.show(use.key)

    def validate_use(self, use: UseRecord) -> None:
        step = use.params.get("step", 1)
        if step < 1 or step != int(step):
            raise ValueError(f"step must be a whole number of 1 or more, not {step}")

    def use_added(self, use: UseRecord) -> None:
        self.show(use.key)

    def use_removed(self, use: UseRecord) -> None:
        self.counts.pop(use.key, None)

    @action
    def bump(self, event: Event, amount: float = 1) -> None:
        key = event.use
        self.counts[key] = self.counts.get(key, 0) + int(amount)
        self.show(key)

    @action
    def reset(self, event: Event) -> None:
        # a click on the module's own block names its use; a Call from another block names that
        # block's use, so then every use of the module is reset
        keys = [event.use] if event.use in self.ctx.uses else list(self.ctx.uses)
        for key in keys:
            self.counts[key] = 0
            self.show(key)
        self.ctx.announce("Tally reset")

    def show(self, key: str) -> None:
        count = self.counts.get(key, 0)
        self.ctx.send("count", count, use=key)
        self.ctx.send("text", f"Tally: {count}", use=key)
