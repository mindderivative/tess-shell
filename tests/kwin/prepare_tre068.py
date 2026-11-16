"""Regenerate the tre 0.6.8 KWin hand check in /tmp/tess-kwin-tre068 (not collected by pytest).

Run from the repo root: ``env -u WAYLAND_DISPLAY -u DISPLAY PYTHONDONTWRITEBYTECODE=1 uv run python
tests/kwin/prepare_tre068.py``. It writes scratch configs and scripts under ``/tmp/tess-kwin-tre068``
and starts nothing, reads nothing and touches nothing outside that folder. Only the scripts below
do something, and only when YOU run them, on your real session:

* ``run-tab.sh``: starts the SHELL on your session with a Panel holding a TextEditor, a TextInput
  and a Button (TRE-REQ-018: Tab leaves a multi-line TextEditor). Stops with Ctrl+C.
* ``run-popup.sh``: starts the SHELL with a Bar of two Buttons that open a Popup and close it in
  the same turn, once and 20 times (TRE-REQ-019: a Popup closed before it is placed). Ctrl+C stops.
* ``run-token.sh``: starts ``token_probe.py``, a THROWAWAY tre-only script (not the shell): a Bar
  with one button. Only when you CLICK it does it start a real application (the first of konsole,
  kate, dolphin that is installed) with ``XDG_ACTIVATION_TOKEN`` set. Ctrl+C in its terminal stops
  the script; the application it started is a normal one that you close yourself.
* ``check.sh``: ``tesserae-shell check`` on each shell config (reads files only).
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-tre068/state``, never the real one. The scripts use the
Python environment this generator runs in.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-tre068")
BIN = Path(sys.executable).parent
SETTINGS = (
    "---\nTDL: 0.2\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

TAB_BODY = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Padding: [12, 4, 12, 4]
                        Align_Items: CENTER
                        Children { Clock { } }
                    }
                }
            }
            Panel {
                Name: Form
                Anchor: TOP
                Inset: [0, 80, 0, 0]
                Width: 380
                Height: 280
                Keyboard: ON_DEMAND
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Spacing: 12
                        Padding: 16
                        Children {
                            TextEditor { Name: Editor, Width: 340, Lines: 5, Placeholder: "TextEditor: type two lines" }
                            TextInput { Name: Line, Placeholder: "TextInput: one line", Width: 340 }
                            Button { Name: Last, Text: "Last button" }
                        }
                    }
                }
            }
        }
    }
}
"""

PROBE_TDL = """---
TDL: 0.2
Name: Probe
---

# A test module: a blue block the Popup opens beside.
Module { Rectangle { Width: 60, Height: 20, Fill: "#0000ff" } }
"""

# A Popup is opened beside the use that called: the actions pass the module's one use (as the
# live Popup test does), because the Buttons are in the Bar, not in the module. ctx.popup toggles:
# the second call in the same turn closes the Popup the first one opened, before the compositor
# has placed it (TRE-REQ-019).
PROBE_PY = """from tess_shell import Module, action

TIMES = 20


class Probe(Module):
    def start(self):
        self.ctx.log.info("Probe ready: Open_Close once, Open_Close_20 twenty times")

    def toggle(self):
        (use,) = self.ctx.uses.values()
        self.ctx.popup("Menu", use=use)

    @action
    def open_close(self, event):
        self.toggle()  # opens
        self.toggle()  # the open one: a toggle, so it closes in the same turn
        self.ctx.log.info("Probe: Menu opened and closed in one turn")

    @action
    def open_close_20(self, event):
        for _ in range(TIMES):
            self.toggle()
            self.toggle()
        self.ctx.log.info(f"Probe: Menu opened and closed {TIMES} times in one turn")
"""

POPUP_BODY = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Popup {
                Name: Menu
                Width: 200
                Height: 120
                Style { Fill: "#ff0000" }
                Children {
                    FlexBox {
                        Padding: 12
                        Children { Text { Text: "A popup is stuck", Foreground: "#ffffff", Font_Size: 16 } }
                    }
                }
            }
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 44
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 12
                        Padding: [12, 6, 12, 6]
                        Align_Items: CENTER
                        Children {
                            Button { Name: Once, Text: "Open and close once", On_Click { Action: Call, Target: "Probe.open_close" } }
                            Button { Name: Twenty, Text: "Open and close 20 times", On_Click { Action: Call, Target: "Probe.open_close_20" } }
                            Probe { Name: Probe_One }
                        }
                    }
                }
            }
        }
    }
}
"""

TOKEN_PY = '''"""THROWAWAY tre-only script for the activation token check (not the shell; not collected by pytest).

Run it with ``run-token.sh`` on your real session. It opens ONE layer surface (a bar at the top
with one button) and starts NOTHING until you click the button. On click it asks the compositor for
an activation token with ``window.request_activation_token(callback)`` and, in the callback, starts
the first installed application of konsole, kate, dolphin with ``XDG_ACTIVATION_TOKEN`` set to the
token, then prints what it did and the first 6 characters of the token. With no token (``None``)
it prints "no token: the compositor did not offer xdg_activation_v1" and starts nothing.

Stop it with Ctrl+C in this terminal. The application it started is a normal application: close it
yourself. For the comparison without a token start the same application from a terminal.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

import tess_re

CANDIDATES = ("konsole", "kate", "dolphin")

app = tess_re.App()
handle = app.thread_handle()
bar = tess_re.LayerWindow(
    "tre068.token", layer="top", anchor=("top", "left", "right"), size=(0, 48), keyboard="none"
)


def say(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {text}", flush=True)


def launch(token: str | None) -> None:
    if not token:
        say("no token: the compositor did not offer xdg_activation_v1")
        return
    program = next((shutil.which(name) for name in CANDIDATES if shutil.which(name)), None)
    if program is None:
        say(f"token {token[:6]}... but none of {', '.join(CANDIDATES)} is installed: started nothing")
        return
    env = {**os.environ, "XDG_ACTIVATION_TOKEN": token}
    subprocess.Popen([program], env=env, start_new_session=True)  # noqa: S603
    say(f"started {program} with XDG_ACTIVATION_TOKEN={token[:6]}... (length {len(token)})")


def clicked(_event: object) -> None:
    say("clicked: asking for a token")
    bar.request_activation_token(launch)


root = bar.create(
    "box",
    display="flex",
    flex_direction="horizontal",
    padding=8,
    fill=(30, 30, 40, 255),
    width="100%",
    height=48,
    align_items="center",
)
button = bar.create(
    "box",
    width=260,
    height=32,
    fill=(80, 90, 120, 255),
    corner_radius=8,
    align_items="center",
    justify_content="center",
)
button.add_child(
    bar.create(
        "text", text="Start an app with a token", font_size=14, fill=(255, 255, 255, 255),
        width="fit-content",
    )
)
button.on("click", clicked)
root.add_child(button)
bar.root.add_child(root)
app.add_window(bar)

# the event loop blocks the main thread in the engine, so Ctrl+C needs the shell's signal watcher
from tess_shell.signals import SignalWatcher  # noqa: E402


def force() -> None:
    os._exit(130)


watcher = SignalWatcher(handle.stop, force)  # type: ignore[arg-type]
watcher.start()
say("click the button to start an application with an activation token; Ctrl+C to stop")
try:
    app.run(keep_alive=True)
finally:
    watcher.stop()
'''

CHECKLIST = """tre 0.6.8 checks: one list, every line to run.  Three parts; each has its own run script and
every one runs on YOUR REAL SESSION and stops with Ctrl+C in its terminal.  check.sh only reads the
two shell configs ("ok: 1 files checked" each).  Nothing starts by itself.  The state directory is
/tmp/tess-kwin-tre068/state, not your real one.

PART 1: Tab leaves a multi-line TextEditor (TRE-REQ-018)
 /tmp/tess-kwin-tre068/run-tab.sh starts the shell: a Bar with a clock and, below it, a Panel
 (Keyboard: ON_DEMAND) holding a TextEditor, a single-line TextInput and a Button, in that order.
 1  Click into the TextEditor and type two lines: the text appears; Enter makes a new line.
 2  Press Tab: focus moves to the next control (the TextInput shows its focus ring); no tab character
    was typed into the TextEditor.
 3  Press Shift+Tab: focus returns to the TextEditor with its text and caret unchanged.
 4  Press Tab in the single-line TextInput: focus moves on (the Button), as before.
 5  Press Tab from the last control (the Button): focus wraps or leaves as the focus rules say
    (Focus and Keyboard).  Write down which.
 Stop the shell with Ctrl+C.

PART 2: a popup closed before it is placed (TRE-REQ-019)
 /tmp/tess-kwin-tre068/run-popup.sh starts the shell: a Bar with two Buttons ("Open and close once",
 "Open and close 20 times") and a small blue block.  A button opens the red Popup beside the blue block
 and closes it in the SAME turn (ctx.popup twice: the second call toggles the open one closed).  A
 red box with "A popup is stuck" on screen means a Popup stayed.
 6  Click "Open and close once": no popup is left on screen; the log has no warning about a popup
    that stayed (the log shows "Probe: Menu opened and closed in one turn").
 7  Click "Open and close 20 times": nothing is left on screen afterwards, and the compositor shows
    no flash that stays (the log shows "Probe: Menu opened and closed 20 times in one turn").
 8  Open and dismiss a tray menu with the keyboard (Escape straight after the click) 20 times: no menu
    stays on screen.  (Use the tray of the M5f kit, or the tooltips of any gallery: this kit has no
    tray of its own; run one of those kits instead of run-popup.sh for this line.)
 Stop the shell with Ctrl+C.

PART 3: the activation token (Applications Module; the shell's launcher T-049 is not built)
 /tmp/tess-kwin-tre068/run-token.sh starts token_probe.py, a throwaway tre-only script, NOT the shell:
 a Bar at the top with one button.  It starts nothing until you click.  On click it asks for a token
 (Window.request_activation_token) and starts the first installed one of konsole, kate, dolphin with
 XDG_ACTIVATION_TOKEN set to it, and prints in its terminal what it did and the token's first 6
 characters.  The application it starts is normal: close it yourself.  Ctrl+C stops the script.
 9  Click the button: the started application's window takes focus (its title bar active), not only
    appears behind the current window.
10  Start the same application from a terminal for comparison (for example: konsole &): without a
    token KWin may leave the new window unfocused (focus-stealing prevention); this is the difference
    the token fixes.
11  Note the callback in the terminal: the token is a non-empty string (the first 6 characters are
    printed); if it says "no token: the compositor did not offer xdg_activation_v1", the compositor
    did not offer the protocol.  Write down which.

Report pass or fail per line (and the log file of the shell if a line fails).
"""

WARN_SHELL = (
    'echo "This starts the SHELL on your real session (Ctrl+C stops it). Ctrl+C within 3 s to cancel." >&2\n'
    "sleep 3\n"
)
WARN_TOKEN = (
    'echo "This starts token_probe.py on your real session (Ctrl+C stops it)." >&2\n'
    'echo "It starts a real application ONLY when you click its button." >&2\n'
    "sleep 3\n"
)

# folder -> shell body
CONFIGS: dict[str, str] = {"cfg-tab": TAB_BODY, "cfg-popup": POPUP_BODY}


def script(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text("#!/bin/sh\n" + text)
    path.chmod(0o755)


def write_config(cfg: Path, body: str) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)
    if "Probe" in body:
        folder = cfg / "Modules" / "Probe"
        folder.mkdir(parents=True)
        (folder / "Probe_Module.tdl").write_text(PROBE_TDL)
        (folder / "Probe_Module.py").write_text(PROBE_PY)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, body in CONFIGS.items():
        write_config(root / folder, body)
    (root / "checklist.txt").write_text(CHECKLIST)
    (root / "token_probe.py").write_text(TOKEN_PY)
    state = f"export XDG_STATE_HOME={root}/state\n"
    for name, folder in (("run-tab.sh", "cfg-tab"), ("run-popup.sh", "cfg-popup")):
        script(
            root,
            name,
            state + WARN_SHELL + f"exec {BIN}/tesserae-shell run --config-dir {root / folder}\n",
        )
    script(root, "run-token.sh", state + WARN_TOKEN + f"exec {BIN}/python {root}/token_probe.py\n")
    script(
        root,
        "check.sh",
        state
        + "".join(
            f"{BIN}/tesserae-shell check --config-dir {root}/{folder}\n" for folder in CONFIGS
        ),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
