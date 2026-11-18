"""A hand-written user module that uses the session bus: the name of the virtual desktop KWin says is
current (``ctx.dbus``, a property subscription)."""

from tess_shell import Module

KWIN = "org.kde.KWin"
PATH = "/VirtualDesktopManager"
INTERFACE = "org.kde.KWin.VirtualDesktopManager"


class DeskName(Module):
    def start(self):
        self.names = {}
        self.current = ""
        bus = self.ctx.dbus.session()
        bus.proxy(KWIN, PATH, INTERFACE).on_property_changed(self.changed)

    def changed(self, changed):
        if "desktops" in changed:
            self.names = {d[1]: d[2] for d in changed["desktops"]}
        if "current" in changed:
            self.current = changed["current"]
        self.ctx.send("desk", self.names.get(self.current, "?"))
