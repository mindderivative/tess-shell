"""A hand-written user module: a countdown a click starts and stops; one tick a second only while
it runs."""

from tess_shell import Module, action


class Pomodoro(Module):
    def start(self):
        self.left = 25 * 60
        self.sub = None
        self.show()

    def show(self):
        self.ctx.send("label", f"{self.left // 60:02d}:{self.left % 60:02d}")

    def tick(self):
        self.left -= 1
        self.show()
        if self.left <= 0 and self.sub is not None:
            self.sub.cancel()
            self.sub = None

    @action
    def toggle(self, event):
        if self.sub is None:
            self.sub = self.ctx.on_tick("second", self.tick)
        else:
            self.sub.cancel()
            self.sub = None
