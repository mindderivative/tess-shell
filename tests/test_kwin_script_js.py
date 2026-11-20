"""The KWin script's own logic (``src/tess_shell/kwin/TesseraeShell/contents/code/main.js``), run for
real under Node with a stub ``workspace`` and ``callDBus`` (Tasks Module > Integration: the script's
logic is run under a JavaScript engine with a stub ``workspace`` when one is installed). What a stub
cannot say is whether KWin 6.8's objects behave as the stub does: that is the hand check of
``tests/kwin/prepare_m5g_kwin.py``. Skipped without ``node``."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services.control import INTERFACE, NAME, PATH
from tess_shell.services.kwin_package import ACTIONS, action_script, main_script

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");

function signal() {
    const handlers = [];
    return { connect: (f) => handlers.push(f), emit: (...a) => handlers.slice().forEach((f) => f(...a)) };
}
function makeWindow(o) {
    return Object.assign({
        internalId: "{" + o.id + "}", caption: "Title " + o.id, desktopFileName: "", resourceClass: "cls-" + o.id,
        output: { name: "DP-1" }, desktops: [], fullScreen: false, minimized: false, skipTaskbar: false,
        normalWindow: true, dialog: false, specialWindow: false, demandsAttention: false,
        fullScreenChanged: signal(), outputChanged: signal(), captionChanged: signal(),
        minimizedChanged: signal(), desktopsChanged: signal(), demandsAttentionChanged: signal(),
        desktopFileNameChanged: signal(), skipTaskbarChanged: signal(),
    }, o);
}
const calls = [];
let policy = () => '{"windows": false}';
const workspace = {
    activeWindow: null, windows: [],
    windowList() { return this.windows.slice(); },
    windowAdded: signal(), windowRemoved: signal(), windowActivated: signal(),
};
function callDBus(service, path, iface, method, payload, callback) {
    calls.push({ service, path, iface, method, payload });
    const answer = policy(method, payload);
    if (callback) callback(answer);
}
const context = vm.createContext({ workspace, callDBus, String, JSON, Boolean, Object });
function load() { vm.runInContext(fs.readFileSync(process.env.SCRIPT, "utf8"), context); }
const kinds = (name) => calls.filter((c) => c.method === name);
const scenario = new Function("ctx", process.env.SCENARIO);
const out = scenario({ workspace, makeWindow, calls, kinds, load, setPolicy: (f) => { policy = f; } });
console.log(JSON.stringify(out));
"""


def run(scenario: str) -> Any:
    """Run ``main.js`` under Node with the stubs; ``scenario`` is the body of a function that gets
    ``ctx`` (``workspace``, ``makeWindow``, ``calls``, ``kinds``, ``load``, ``setPolicy``) and
    returns JSON."""
    import os

    env = {
        **os.environ,
        "SCRIPT": str(main_script()),
        "SCENARIO": scenario,
    }
    done = subprocess.run(
        [NODE or "node", "-e", HARNESS], env=env, capture_output=True, text=True, timeout=30
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


ON = "ctx.setPolicy(() => '{\"windows\": true}');"
OFF = "ctx.setPolicy(() => '{\"windows\": false}');"


def test_a_load_reports_the_fullscreen_state_to_the_shells_interface() -> None:
    out = run(
        """
        ctx.load();
        return ctx.calls;
        """
    )
    assert out == [
        {
            "service": NAME,
            "path": PATH,
            "iface": INTERFACE,
            "method": "FullscreenState",
            "payload": "[]",
        }
    ]


def test_only_an_active_fullscreen_window_names_its_output_and_the_state_is_a_json_string() -> None:
    out = run(
        """
        const a = ctx.makeWindow({ id: "a", fullScreen: true, output: { name: "HDMI-A-1" } });
        const b = ctx.makeWindow({ id: "b", fullScreen: true });   // fullscreen, not active
        ctx.workspace.windows = [a, b];
        ctx.workspace.activeWindow = a;
        ctx.load();
        const first = ctx.kinds("FullscreenState").map((c) => c.payload);
        ctx.workspace.activeWindow = b;                           // the other one becomes active
        ctx.workspace.windowActivated.emit(b);
        const second = ctx.kinds("FullscreenState").map((c) => c.payload);
        ctx.workspace.activeWindow = null;                        // nothing is active
        ctx.workspace.windowActivated.emit(null);
        return [first, second, ctx.kinds("FullscreenState").map((c) => c.payload)];
        """
    )
    assert out[0] == ['["HDMI-A-1"]']
    assert out[1] == ['["HDMI-A-1"]', '["DP-1"]']
    assert out[2][-1] == "[]"


def test_a_window_entering_or_leaving_fullscreen_a_move_and_a_close_report_again() -> None:
    out = run(
        """
        const a = ctx.makeWindow({ id: "a" });
        ctx.workspace.windows = [a];
        ctx.workspace.activeWindow = a;
        ctx.load();
        const n0 = ctx.kinds("FullscreenState").length;
        a.fullScreen = true; a.fullScreenChanged.emit();
        a.output = { name: "DP-2" }; a.outputChanged.emit(null);
        const states = ctx.kinds("FullscreenState").map((c) => c.payload).slice(n0);
        ctx.workspace.windowRemoved.emit(a);
        ctx.workspace.activeWindow = null;
        ctx.workspace.windowRemoved.emit(a);
        return [states, ctx.kinds("FullscreenState").map((c) => c.payload).pop()];
        """
    )
    assert out[0] == ['["DP-1"]', '["DP-2"]']
    assert out[1] == "[]"


def test_with_no_tasks_module_the_script_sends_no_window_title_class_or_id() -> None:
    """KWin Integration > Acceptance: with no Tasks module in use the script sends no title, class
    or id: the only call is ``FullscreenState``, and what it carries is output names."""
    out = run(
        """
        const a = ctx.makeWindow({ id: "11111111-aaaa", caption: "TOPSECRET", resourceClass: "SecretClass" });
        ctx.workspace.windows = [a];
        ctx.workspace.activeWindow = a;
        ctx.load();
        a.captionChanged.emit(); a.minimizedChanged.emit(); a.desktopsChanged.emit();
        ctx.workspace.windowAdded.emit(ctx.makeWindow({ id: "bbbb", caption: "ALSO-SECRET" }));
        ctx.workspace.windowActivated.emit(a);
        return ctx.calls;
        """
    )
    assert {c["method"] for c in out} == {"FullscreenState"}
    text = json.dumps(out)
    for word in ("TOPSECRET", "SecretClass", "11111111", "ALSO-SECRET", "bbbb"):
        assert word not in text


def test_the_window_list_is_sent_when_the_answer_asks_for_it() -> None:
    out = run(
        ON
        + """
        const a = ctx.makeWindow({ id: "aaaa", caption: "First", desktopFileName: "org.a",
                                   desktops: [{ id: "d1" }, { id: "d2" }], minimized: true });
        const b = ctx.makeWindow({ id: "bbbb", caption: "Second", demandsAttention: true,
                                   output: { name: "HDMI-A-1" } });
        ctx.workspace.windows = [a, b];
        ctx.workspace.activeWindow = b;
        ctx.load();
        return ctx.kinds("WindowsState").map((c) => JSON.parse(c.payload));
        """
    )
    (windows,) = out
    assert windows == [
        {
            "id": "aaaa",
            "title": "First",
            "app": "org.a",
            "active": False,
            "minimized": True,
            "desktops": ["d1", "d2"],
            "output": "DP-1",
            "attention": False,
        },
        {
            "id": "bbbb",
            "title": "Second",
            "app": "cls-bbbb",  # no desktop file name: the resource class
            "active": True,
            "minimized": False,
            "desktops": [],
            "output": "HDMI-A-1",
            "attention": True,
        },
    ]


def test_the_list_leaves_out_the_shells_surfaces_docks_and_other_special_windows() -> None:
    out = run(
        ON
        + """
        const ws = [
            ctx.makeWindow({ id: "app" }),
            ctx.makeWindow({ id: "skip", skipTaskbar: true }),          // a shell surface
            ctx.makeWindow({ id: "dock", normalWindow: false }),         // a panel
            ctx.makeWindow({ id: "special", specialWindow: true }),
            ctx.makeWindow({ id: "dialog", normalWindow: false, dialog: true }),
        ];
        ctx.workspace.windows = ws;
        ctx.load();
        return ctx.kinds("WindowsState").map((c) => JSON.parse(c.payload).map((w) => w.id));
        """
    )
    assert out == [["app", "dialog"]]


def test_a_list_is_sent_again_for_each_change_it_shows_and_never_otherwise() -> None:
    out = run(
        ON
        + """
        const a = ctx.makeWindow({ id: "aaaa" });
        ctx.workspace.windows = [a];
        ctx.workspace.activeWindow = a;
        ctx.load();
        const sent = () => ctx.kinds("WindowsState").length;
        const counts = [sent()];
        a.caption = "New title"; a.captionChanged.emit(); counts.push(sent());
        a.minimized = true; a.minimizedChanged.emit(); counts.push(sent());
        a.desktops = [{ id: "d9" }]; a.desktopsChanged.emit(); counts.push(sent());
        a.demandsAttention = true; a.demandsAttentionChanged.emit(); counts.push(sent());
        const b = ctx.makeWindow({ id: "bbbb" });
        ctx.workspace.windowAdded.emit(b); counts.push(sent());
        ctx.workspace.windowActivated.emit(b); counts.push(sent());
        ctx.workspace.windowRemoved.emit(a); counts.push(sent());
        const last = JSON.parse(ctx.kinds("WindowsState").pop().payload);
        return [counts, last.map((w) => w.id)];
        """
    )
    assert out[0] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert out[1] == ["bbbb"]


def test_the_order_is_the_order_the_windows_were_opened_and_activation_does_not_change_it() -> None:
    out = run(
        ON
        + """
        const [a, b, c] = ["aaaa", "bbbb", "cccc"].map((id) => ctx.makeWindow({ id }));
        ctx.workspace.windows = [a, b];
        ctx.load();
        ctx.workspace.windowAdded.emit(c);
        for (const w of [c, a, b]) { ctx.workspace.activeWindow = w; ctx.workspace.windowActivated.emit(w); }
        return ctx.kinds("WindowsState").map((c) => JSON.parse(c.payload).map((w) => w.id));
        """
    )
    assert all(order == ["aaaa", "bbbb", "cccc"] for order in out[1:])


def test_when_the_answer_turns_the_list_off_nothing_more_is_sent_and_back_on_sends_it() -> None:
    out = run(
        ON
        + """
        const a = ctx.makeWindow({ id: "aaaa" });
        ctx.workspace.windows = [a];
        ctx.workspace.activeWindow = a;
        ctx.load();
        const on = ctx.kinds("WindowsState").length;
        ctx.setPolicy(() => '{"windows": false}');
        ctx.workspace.windowActivated.emit(a);       // this call's answer turns the list off
        a.captionChanged.emit();                     // so a caption change sends nothing
        const off = ctx.kinds("WindowsState").length;
        ctx.setPolicy(() => '{"windows": true}');
        ctx.workspace.windowActivated.emit(a);       // asked for again: the list follows at once
        return [on, off, ctx.kinds("WindowsState").length];
        """
    )
    assert out[0] == 1 and out[1] <= 2 and out[2] > out[1]  # a stub answers at once: maybe twice


@pytest.mark.parametrize(
    "answer", ["undefined", "'not json'", "'{}'", "'[]'", "42", '\'{"windows": "yes"}\'', "null"]
)
def test_an_answer_that_is_not_the_small_json_string_is_ignored(answer: str) -> None:
    out = run(
        f"""
        ctx.setPolicy(() => {answer});
        const a = ctx.makeWindow({{ id: "aaaa" }});
        ctx.workspace.windows = [a];
        ctx.load();
        a.captionChanged.emit();
        return ctx.kinds("WindowsState").length;
        """
    )
    assert out == 0


# -- the one-shot scripts ------------------------------------------------------------------------

ACTION_HARNESS = r"""
const vm = require("node:vm");
function makeWindow(id, o) {
    return Object.assign({ internalId: "{" + id + "}", minimized: false, minimizable: true,
        closeable: true, closed: false, closeWindow() { this.closed = true; } }, o);
}
const workspace = { activeWindow: null, windows: [], windowList() { return this.windows.slice(); } };
const context = vm.createContext({ workspace, String });
const [a, b] = [makeWindow("%(a)s", %(a_opts)s), makeWindow("%(b)s", %(b_opts)s)];
workspace.windows = [a, b];
vm.runInContext(process.env.TEXT, context);
console.log(JSON.stringify({
    active: workspace.activeWindow === a ? "a" : workspace.activeWindow === b ? "b" : null,
    a: { minimized: a.minimized, closed: a.closed }, b: { minimized: b.minimized, closed: b.closed },
}));
"""
A = "00000001-0000-4000-8000-000000000001"
B = "00000002-0000-4000-8000-000000000002"


def act(kind: str, wanted: str, a_opts: str = "{}", b_opts: str = "{}") -> Any:
    import os

    code = ACTION_HARNESS % {"a": A, "b": B, "a_opts": a_opts, "b_opts": b_opts}
    done = subprocess.run(
        [NODE or "node", "-e", code],
        env={**os.environ, "TEXT": action_script(kind, wanted)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_activate_unminimizes_and_activates_only_the_window_with_that_id() -> None:
    got = act("activate", B, b_opts="{ minimized: true }")
    assert got["active"] == "b" and got["b"]["minimized"] is False
    assert got["a"] == {"minimized": False, "closed": False}


def test_minimize_minimizes_only_that_window_and_only_when_it_can_be() -> None:
    assert act("minimize", A)["a"]["minimized"] is True
    assert act("minimize", A)["b"]["minimized"] is False
    assert act("minimize", A, a_opts="{ minimizable: false }")["a"]["minimized"] is False


def test_close_closes_only_that_window_and_only_when_it_can_be() -> None:
    got = act("close", A)
    assert got["a"]["closed"] is True and got["b"]["closed"] is False
    assert act("close", A, a_opts="{ closeable: false }")["a"]["closed"] is False


def test_a_window_that_is_gone_makes_the_script_do_nothing() -> None:
    got = act("activate", "00000003-0000-4000-8000-000000000003")
    assert got["active"] is None and got["a"]["closed"] is False


def test_the_script_texts_hold_the_id_and_no_other_data() -> None:
    for kind in ACTIONS:
        text = action_script(kind, A.upper())
        assert f'"{A}"' in text  # a UUID is lower-cased: KWin's ids are
        assert text.count(A) == 1 and "__WINDOW_ID__" not in text


def test_the_templates_keep_their_placeholder_in_the_package(tmp_path: Path) -> None:
    folder = main_script().parent.parent.parent.parent / "actions"
    for kind in ACTIONS:
        assert "__WINDOW_ID__" in (folder / f"{kind}.js").read_text()
