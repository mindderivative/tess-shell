"""A fake PulseAudio server for the maintainer's KWin check of the Audio module
(``tests/kwin/prepare_m5e_gallery.py``; not collected by pytest).

``python fake_pulse_server.py --root DIR`` starts the in-process fake of ``tests/fake_pulse.py`` on
the socket ``DIR/run/pulse/native`` (a private one: it never connects to the real sound server and
never touches the real runtime folder), with five outputs and a microphone, and a control socket
``DIR/control`` that ``audio-set.sh`` talks to (through ``tests/kwin/audio_ctl.py``). It writes its
pid to ``DIR/fake.pid`` and every setter a client calls (the shell's volume writes, for one) to
``DIR/fake.log``. Signals:

* ``SIGUSR1``: the sound server goes away (the socket is removed, every connection closes);
* ``SIGUSR2``: it comes back, with the state it had;
* ``SIGTERM`` / ``SIGINT``: this process ends.

The outputs: ``speakers`` (the default, 45 %), ``headphones``, ``hdmi``, ``bluetooth`` and ``usb``
(made by ``usbplug``).
"""

from __future__ import annotations

import argparse
import os
import signal
import socketserver
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tess_shell.services.pulse_native import NORM  # noqa: E402
from tests.fake_pulse import FakePulse  # noqa: E402

PORTS_SPEAKERS = [("analog-output-speaker", "Speakers", "Speaker")]
OUTPUTS = {  # word -> (sink name, description, form factor, bus, ports)
    "speakers": ("fake_speakers", "Speakers", "speaker", "pci", PORTS_SPEAKERS),
    "headphones": ("fake_headphones", "Headphones", "headphone", "pci", []),
    "hdmi": ("fake_hdmi", "HDMI Output", "", "pci", [("hdmi-output-0", "HDMI", "HDMI")]),
    "bluetooth": ("fake_bluetooth", "Bluetooth Headset", "", "bluetooth", []),
    "usb": ("fake_usb", "USB DAC", "", "usb", [("analog-output", "Analog Output", "Analog")]),
}
WORDS = tuple(OUTPUTS)


class Controller:
    """``audio-set.sh``'s requests: one line of ``key=value`` words, all checked before any is
    applied."""

    def __init__(self, fake: FakePulse) -> None:
        self.fake = fake
        self.lock = threading.Lock()
        self.plugged = False
        self.mic = True

    def sink_name(self, word: str) -> str:
        return OUTPUTS[word][0]

    def run(self, line: str) -> str:
        with self.lock:
            try:
                pairs = dict(p.split("=", 1) for p in line.split())
                return self.apply(pairs)
            except (ValueError, KeyError) as exc:
                return f"error: {exc}"

    def apply(self, pairs: dict[str, str]) -> str:
        fake = self.fake
        unknown = set(pairs) - {"default", "volume", "mute", "mic", "usb", "hasmic", "balance"}
        if unknown:
            raise ValueError(f"unknown request {sorted(unknown)}")
        plug = pairs.get("usb")
        will_have_usb = (plug == "plug") or (self.plugged and plug != "unplug")
        default = pairs.get("default")
        if default is not None:
            if default not in OUTPUTS:
                raise ValueError(f"no output {default}")
            if default == "usb" and not will_have_usb:
                raise ValueError("no output usb: plug it first (usbplug)")
        volume = int(pairs["volume"]) if "volume" in pairs else None
        if volume is not None and not 0 <= volume <= 130:
            raise ValueError(f"a volume is 0 to 130, not {volume}")
        # everything is valid: apply, in this order
        if plug == "plug" and not self.plugged:
            _n, desc, form, bus, ports = OUTPUTS["usb"]
            fake.add_sink(_n, desc, percent=70, form_factor=form, bus=bus, ports=ports)
            self.plugged = True
        if plug == "unplug" and self.plugged:
            fake.remove_sink(OUTPUTS["usb"][0])
            self.plugged = False
        if "hasmic" in pairs:
            want = pairs["hasmic"] == "1"
            if want and not self.mic:
                fake.add_source("fake_mic", "Microphone")
                self.mic = True
            elif not want and self.mic:
                fake.remove_source("fake_mic")
                self.mic = False
        if default is not None:
            fake.set_default_sink(self.sink_name(default))
        current = fake.default_sink
        if volume is not None:
            fake.set_volume(current, volume)
        if "balance" in pairs:
            fake.set_volume(current, [round(0.8 * NORM), round(0.4 * NORM)])
        if "mute" in pairs:
            fake.set_mute(current, pairs["mute"] == "1")
        if "mic" in pairs:
            if not self.mic:
                raise ValueError("there is no microphone (use `mic` first)")
            fake.set_source_mute("fake_mic", pairs["mic"] == "1")
        return f"fake audio: default={fake.default_sink} " + ", ".join(
            f"{s.description} {round(sum(s.volume) / len(s.volume) * 100 / NORM)} %"
            f"{' muted' if s.mute else ''}"
            for s in fake.sinks
        )


class Handler(socketserver.StreamRequestHandler):
    controller: Controller

    def handle(self) -> None:
        line = self.rfile.readline().decode().strip()
        self.wfile.write((self.controller.run(line) + "\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root: Path = args.root
    root.mkdir(parents=True, exist_ok=True)
    fake = FakePulse(root / "run")
    first = True
    for word in ("speakers", "headphones", "hdmi", "bluetooth"):
        name, desc, form, bus, ports = OUTPUTS[word]
        fake.add_sink(
            name,
            desc,
            percent=45 if first else 60,
            form_factor=form,
            bus=bus,
            ports=ports,
            default=first,
        )
        first = False
    fake.add_source("fake_mic", "Microphone")
    fake.start()
    controller = Controller(fake)
    Handler.controller = controller
    control = root / "control"
    control.unlink(missing_ok=True)
    server = socketserver.ThreadingUnixStreamServer(str(control), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    (root / "fake.pid").write_text(str(os.getpid()))
    (root / "server-socket").write_text(str(fake.socket))
    print(f"fake sound server on {fake.socket}", flush=True)
    stop = {"now": False}
    pending: list[str] = []

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    signal.signal(signal.SIGUSR1, lambda *_: pending.append("away"))
    signal.signal(signal.SIGUSR2, lambda *_: pending.append("back"))
    log = root / "fake.log"
    log.write_text("")
    written = 0
    try:
        while not stop["now"]:
            while pending:
                if pending.pop(0) == "away":
                    fake.stop()
                else:
                    fake.start()
            if len(fake.commands) > written:
                with log.open("a") as out:
                    for name, args_ in fake.commands[written:]:
                        out.write(f"{time.strftime('%H:%M:%S')} {name} {args_}\n")
                written = len(fake.commands)
            time.sleep(0.05)
    finally:
        server.shutdown()
        fake.close()
        for name in ("control", "fake.pid", "server-socket"):
            (root / name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
