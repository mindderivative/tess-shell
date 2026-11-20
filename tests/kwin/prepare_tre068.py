"""Regenerate the tre 0.6.8 kit in /tmp/tess-kwin-tre068 (not collected by pytest).

Run from the repo root: ``env -u WAYLAND_DISPLAY -u DISPLAY PYTHONDONTWRITEBYTECODE=1 uv run python
tests/kwin/prepare_tre068.py``. It writes the kit folder and starts nothing. Then
``/tmp/tess-kwin-tre068/run-all.sh`` runs every step that needs no person, in a PRIVATE KWin inside
a private ``dbus-run-session`` (``tests/kitlib.py``), and writes ``results.txt``:

* ``1-check``: ``tesserae-shell check`` on both shell configs.
* ``2-tab``: a Panel with a TextEditor, a TextInput and a Button; a click gives it the keyboard
  (KWin's own fake input), Tab and Shift+Tab move the focus as the shell's focus log says
  (TRE-REQ-018: Tab leaves a multi-line TextEditor).
* ``3-popup``: a Popup opened and closed in the same turn, once and 20 times, leaves no
  ``xdg_popup`` in the protocol trace (TRE-REQ-019), with a control that leaves one open.
* ``4-token``: ``token_probe.py`` (a throwaway tre-only script) asks for an activation token on a
  click and starts a FAKE program that writes its environment to a file: the token reaches it.

``checklist.txt`` holds only what no session can do. Nothing starts konsole, kate or dolphin.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests import kitlib  # noqa: E402
from tests.kitlib import Step  # noqa: E402
from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-tre068")
# the environment this generator runs in, so that the kit runs this code
BIN = Path(sys.executable).parent
# tre's own virtual environment has pywayland, which the fake input needs
TRE_PY = str(
    Path(os.environ.get("TRE_DIR", Path.home() / "Projects/rustDev/projects/tre"))
    / ".venv"
    / "bin"
    / "python"
)
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
    def open_hold(self, event):
        self.toggle()  # a toggle: opens when closed, closes when open (the control of the check)
        self.ctx.log.info("Probe: Menu opened and left open (a second call closes it)")

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

``drive_tre068.py token`` runs it in a private KWin. It opens ONE layer surface (a bar at the top
with one button) and starts NOTHING until the button is clicked. On click it asks the compositor
for an activation token with ``window.request_activation_token(callback)`` and, in the callback,
starts the program named by ``$TOKEN_PROGRAM`` (the kit's FAKE program, which writes its
environment to ``$TOKEN_ENV_OUT``) with ``XDG_ACTIVATION_TOKEN`` set to the token, then prints what
it did and the first 6 characters of the token. With no token (``None``) it prints "no token: the
compositor did not offer xdg_activation_v1" and starts nothing.
"""

from __future__ import annotations

import os
import subprocess
import time

import tess_re

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
    program = os.environ["TOKEN_PROGRAM"]
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

# the event loop blocks the main thread in the engine, so a signal needs the shell's watcher
from tess_shell.signals import SignalWatcher  # noqa: E402


def force() -> None:
    os._exit(130)


watcher = SignalWatcher(handle.stop, force)  # type: ignore[arg-type]
watcher.start()
say("click the button to start the program with an activation token")
try:
    app.run(keep_alive=True)
finally:
    watcher.close()
'''

FAKE_APP = '#!/bin/sh\n# a FAKE program: writes its environment (NUL separated) to the file the check names\nenv -0 > "$TOKEN_ENV_OUT"\n'

CONFIGS: dict[str, str] = {"cfg-tab": TAB_BODY, "cfg-popup": POPUP_BODY}

WARN_SHELL = (
    'echo "This starts the SHELL on your real session (Ctrl+C stops it). Ctrl+C within 3 s to cancel." >&2\n'
    "sleep 3\n"
)


def write_config(cfg: Path, body: str) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)
    if "Probe" in body:
        folder = cfg / "Modules" / "Probe"
        folder.mkdir(parents=True)
        (folder / "Probe_Module.tdl").write_text(PROBE_TDL)
        (folder / "Probe_Module.py").write_text(PROBE_PY)


OK = "^PASS "
NO = (r"^FAIL ",)
INTRO = (
    "The unattended steps drive the shell in a private KWin with KWin's own fake input; the\n"
    "rows of the vault's Hand Checks table for tre 0.6.8 that a session can decide are in\n"
    "results.txt. Left for you: what needs a look at a real screen or a real session."
)


def drive(name: str) -> str:
    return f'"$PY" drive_tre068.py {name}'


def steps() -> list[Step]:
    return [
        Step(
            "1-check",
            "tesserae-shell check on both shell configs",
            command=(
                '"$BIN" check --config-dir "$KIT/cfg-tab" || exit 1\n'
                '"$BIN" check --config-dir "$KIT/cfg-popup"\n'
            ),
            sandbox="bus",
            expect=(r"ok: \d+ files? checked[\s\S]*ok: \d+ files? checked",),
            forbid=("error", "warning"),
        ),
        Step(
            "2-tab",
            "Tab leaves a multi-line TextEditor (TRE-REQ-018): the focus moves in order, with a ring",
            command=drive("tab"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=(OK + "1 ", OK + "2 ", OK + "3 ", OK + "4 ", OK + "5 ", OK + "6 ", OK + "7 "),
            forbid=NO,
            timeout=180,
        ),
        Step(
            "3-popup",
            "a popup closed in the same turn leaves no xdg_popup (TRE-REQ-019), once and 20 times",
            command=drive("popup"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=(OK + "2 ", OK + "3 ", OK + "5 open_close:", OK + "5 open_close_20:", OK + "6 "),
            forbid=NO,
            timeout=180,
        ),
        Step(
            "4-token",
            "the activation token: a string or None, and the started program receives it",
            command=drive("token"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=(OK + "1 ", OK + "2 ", r"^NOTE the compositor gave"),
            forbid=NO,
            timeout=180,
        ),
        Step(
            "5-focus-ring",
            "the focus ring is visible around the focused control",
            kind="manual",
            reason=(
                "looking at the screen: step 2 asserts that tre reports focus_visible (the log says "
                "'ring'), but whether the ring is drawn so a person sees it is a look at the "
                "pixels on a real screen"
            ),
            expect=(
                "run-tab.sh (the shell on your real session): the TextInput shows its focus ring after Tab",
            ),
        ),
        Step(
            "6-no-popup-on-screen",
            "no stuck popup is visible on screen after the open-and-close buttons",
            kind="manual",
            reason=(
                "looking at the screen: step 3 asserts through the protocol trace that every "
                "xdg_popup is destroyed; whether the compositor draws nothing red is a look at a "
                "real screen. Run run-popup.sh (the shell on your real session; Ctrl+C stops it) and "
                "click 'Open and close once' and 'Open and close 20 times'"
            ),
            expect=("no red box with 'A popup is stuck' stays",),
        ),
        Step(
            "7-real-app-focus",
            "the window of a real application started with a token takes focus",
            kind="manual",
            reason=(
                "needs a real application and your own KWin focus-stealing-prevention settings: "
                "step 4 proves the token reaches a started program, never starting konsole, kate "
                "or dolphin in a sandbox; whether KWin then focuses that application's window is "
                "your session's policy"
            ),
            expect=(
                "the started application's title bar is active",
                "the same application from a terminal may stay unfocused",
            ),
        ),
        Step(
            "8-tray-menu-keyboard",
            "a tray menu opened and dismissed with the keyboard (Escape right after the click) 20 times leaves nothing",
            kind="manual",
            reason=(
                "needs a tray with an item and a menu, which this kit does not have (it belongs to "
                "the tray kit of the M5f gallery, tests/kwin/prepare_m5f_gallery.py, which is not "
                "converted yet); the popup mechanism itself is asserted by step 3"
            ),
            expect=("no menu stays on screen",),
        ),
    ]


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, body in CONFIGS.items():
        write_config(root / folder, body)
    state = f"export XDG_STATE_HOME={root}/state\n"
    # for the two looks that need your real screen: the shell on YOUR session, started by you
    interactive = {"run-tab.sh": "cfg-tab", "run-popup.sh": "cfg-popup"}
    files = {
        "token_probe.py": TOKEN_PY,
        "fake-app": FAKE_APP,
        **{
            name: "#!/bin/sh\n"
            + state
            + WARN_SHELL
            + f"exec {BIN}/tesserae-shell run --config-dir {root / folder}\n"
            for name, folder in interactive.items()
        },
    }
    kitlib.write_kit(
        root,
        steps(),
        title="tre 0.6.8 kit: Tab in a TextEditor, popups closed in the same turn, the token",
        intro=INTRO,
        files=files,
        executable=("fake-app", *interactive),
        variables={"BIN": str(BIN / "tesserae-shell"), "PY": sys.executable, "TRE_PY": TRE_PY},
        support=("kitdrive.py", "fake_input_server.py", "kwin/drive_tre068.py"),
        obsolete=("run-token.sh", "check.sh"),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
