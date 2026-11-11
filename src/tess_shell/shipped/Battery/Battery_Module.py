"""The Battery: the charge of the machine's battery as UPower's display device reports it (Battery
Module). It reads once, then follows ``PropertiesChanged``: no timer, no thread. The callbacks
run on the ``dbus`` thread, derive the values and send only the ones that changed. One instance
serves every use.

Keys sent: ``present`` (UPower's ``IsPresent``), ``percent``, ``state``, ``icon``, ``low``,
``critical``, ``tooltip``, ``label`` (the accessible name) and, when the power-profiles service is
on the bus, ``profile`` (read only). ``available`` is the layer's: true while UPower is on the bus.
A layout shows itself with ``If {{ available and present }}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tess_shell import Module

UPOWER = "org.freedesktop.UPower"
DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"
DEVICE_INTERFACE = "org.freedesktop.UPower.Device"
PROFILES = "org.freedesktop.UPower.PowerProfiles"
PROFILES_PATH = "/org/freedesktop/UPower/PowerProfiles"

# UPower's ``State``: 0 unknown, 1 charging, 2 discharging, 3 empty, 4 fully charged, 5 pending
# charge, 6 pending discharge. A pending state is the battery waiting to start: it counts as full
# at 100 % and as unknown below.
STATES = {1: "CHARGING", 2: "DISCHARGING", 3: "EMPTY", 4: "FULL"}
PENDING = (5, 6)

# the one place the tooltip's wording lives (Battery Module, open question 2)
WORDS = {
    "CHARGING": "charging",
    "DISCHARGING": "discharging",
    "FULL": "fully charged",
    "EMPTY": "empty",
    "UNKNOWN": "",
}
LEFT = "{time} left"
UNTIL_FULL = "{time} until full"

UNKNOWN_ICON = "battery-unknown"

# every icon the module can send; a test checks each against the shipped ``mdi`` set
ICONS = frozenset(
    {
        "battery",
        "battery-alert",
        "battery-alert-variant-outline",
        UNKNOWN_ICON,
        "battery-charging-outline",
        *(f"battery-{n}" for n in range(10, 100, 10)),
        *(f"battery-charging-{n}" for n in range(10, 101, 10)),
    }
)


def state_name(code: int, percent: int) -> str:
    if code in STATES:
        return STATES[code]
    if code in PENDING and percent >= 100:
        return "FULL"
    return "UNKNOWN"


def icon_name(state: str, percent: int, have_reading: bool) -> str:
    """The ``mdi`` icon for a state and a level (Battery Module > Icon)."""
    if state == "EMPTY":
        return "battery-alert-variant-outline"
    if state == "FULL":
        return "battery"
    if not have_reading:
        return UNKNOWN_ICON
    step = min(percent // 10 * 10, 90)
    if state == "CHARGING":
        if percent >= 100:
            return "battery-charging-100"
        return "battery-charging-outline" if percent < 10 else f"battery-charging-{step}"
    if percent < 10:
        return "battery-alert"
    if percent > 90:
        return "battery"
    return f"battery-{step}"


def duration(seconds: int) -> str:
    """``2 h 14 min`` or ``14 min``: whole minutes, so the text changes at most once a minute."""
    minutes = max(seconds // 60, 1)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def tooltip_text(percent: int, state: str, seconds_to_empty: int, seconds_to_full: int) -> str:
    parts = [f"{percent} %"]
    if WORDS[state]:
        parts.append(WORDS[state])
    if state == "DISCHARGING" and seconds_to_empty > 0:
        parts.append(LEFT.format(time=duration(seconds_to_empty)))
    elif state == "CHARGING" and seconds_to_full > 0:
        parts.append(UNTIL_FULL.format(time=duration(seconds_to_full)))
    return ", ".join(parts)


def label_text(percent: int, state: str) -> str:
    words = f", {WORDS[state]}" if WORDS[state] else ""
    return f"Battery {percent} percent{words}"


def number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def derive(props: Mapping[str, Any]) -> dict[str, Any]:
    """Every key the module sends for one set of ``org.freedesktop.UPower.Device`` properties."""
    percent = max(0, min(100, int(number(props.get("Percentage")) + 0.5)))
    code = props.get("State")
    state = state_name(code if isinstance(code, int) else 0, percent)
    warning = props.get("WarningLevel")
    level = warning if isinstance(warning, int) else 0
    have_reading = isinstance(props.get("Percentage"), int | float)
    return {
        "present": bool(props.get("IsPresent", False)),
        "percent": percent,
        "state": state,
        "icon": icon_name(state, percent, have_reading),
        "low": level == 3,
        "critical": level in (4, 5),
        "tooltip": tooltip_text(
            percent,
            state,
            int(number(props.get("TimeToEmpty"))),
            int(number(props.get("TimeToFull"))),
        ),
        "label": label_text(percent, state),
    }


class Battery(Module):
    def __init__(self) -> None:
        self.props: dict[str, Any] = {}
        self.sent: dict[str, Any] = {}

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before UPower has answered
        self.publish(derive({}))
        bus = self.ctx.dbus.system()
        bus.proxy(UPOWER, DEVICE, DEVICE_INTERFACE).on_property_changed(self.changed)
        # the power profile is a value this module can do without: the service may be absent
        bus.proxy(PROFILES, PROFILES_PATH, PROFILES, optional=True).on_property_changed(
            self.profile_changed
        )

    # -- on the dbus thread -------------------------------------------------------------------

    def changed(self, values: Mapping[str, Any]) -> None:
        self.props.update(values)
        self.publish(derive(self.props))

    def profile_changed(self, values: Mapping[str, Any]) -> None:
        profile = values.get("ActiveProfile")
        if isinstance(profile, str):
            self.publish({"profile": profile})

    def publish(self, values: Mapping[str, Any]) -> None:
        """Send what changed since the last send: a refresh that changes nothing sends nothing."""
        for key, value in values.items():
            if key not in self.sent or self.sent[key] != value:
                self.sent[key] = value
                self.ctx.send(key, value)
