"""The Audio_Outputs: the menu of outputs the Audio module's secondary click opens (Audio Module).
It only turns a click on an entry into ``ctx.audio.set_output``; the entries are the Popup's
``caller.data.outputs``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event


class Audio_Outputs(Module):
    @action
    def pick(self, event: Event, id: str) -> None:
        self.ctx.audio.set_output(id)
