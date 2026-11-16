/*
    Tesserae Shell: the KWin script (KWin Integration > The KWin script, Tasks Module > The Window
    List). It runs inside KWin and talks to the shell by D-Bus calls only:

      FullscreenState(s)  the outputs that have an ACTIVE fullscreen window, a JSON array of output
                          names ("[]" when none). Sent at load and whenever it may have changed.
      WindowsState(s)     the open windows, a JSON array of objects. Sent ONLY while the shell has
                          asked for it (a Tasks module is in use). Never otherwise: with no Tasks
                          module this script sends no window title, class or id.

    The shell answers each call with a small JSON string, {"windows": true} or {"windows": false}:
    that is how it turns the window list on and off (a script cannot receive a call). A call that
    arrives while the shell is not running gets no usable reply, and is ignored.

    No timer and no polling: it does work on KWin's own signals and nothing else. A change is sent
    as the full state each time, so a lost message is corrected by the next one.

    Every name used here was checked against KWin 6.8.2's own files (see tests/kwin/
    prepare_m5g_kwin.py): workspace.activeWindow / windowList() / windowAdded / windowRemoved /
    windowActivated, and per window internalId, caption, desktopFileName, resourceClass, output
    (with name), desktops (each with id), fullScreen, minimized, skipTaskbar, normalWindow, dialog,
    specialWindow, demandsAttention and their ...Changed signals.
*/

const SERVICE = "io.github.mindderivative.TesseraeShell";
const PATH = "/io/github/mindderivative/TesseraeShell";
const INTERFACE = "io.github.mindderivative.TesseraeShell1";

let sendWindows = false; // the shell asked for the window list
const known = []; // the windows, in the order they were opened (the list keeps it)

function windowId(window) {
    // a QUuid reads as "{xxxxxxxx-xxxx-...}": the shell and the one-shot scripts use it bare
    return String(window.internalId).replace(/[{}]/g, "");
}

function outputName(window) {
    return window.output ? String(window.output.name) : "";
}

function send(method, payload) {
    callDBus(SERVICE, PATH, INTERFACE, method, payload, onReply);
}

function onReply(reply) {
    // the reply to either call: {"windows": true|false}; anything else (no shell, no reply) is
    // ignored, the next event tries again
    if (typeof reply !== "string") {
        return;
    }
    let wanted;
    try {
        wanted = JSON.parse(reply).windows === true;
    } catch (error) {
        return;
    }
    if (wanted === sendWindows) {
        return;
    }
    sendWindows = wanted;
    if (sendWindows) {
        reportWindows();
    }
}

function reportFullscreen() {
    const outputs = [];
    const active = workspace.activeWindow;
    // only an ACTIVE fullscreen window covers the shell's surfaces (KWin puts it in its Active
    // layer only while it is active)
    if (active && active.fullScreen && active.output) {
        outputs.push(outputName(active));
    }
    send("FullscreenState", JSON.stringify(outputs));
}

function listed(window) {
    // the shell's own surfaces and panels skip the taskbar; docks, the desktop and other special
    // windows are not application windows
    if (window.skipTaskbar || window.specialWindow) {
        return false;
    }
    return window.normalWindow || window.dialog;
}

function describe(window) {
    const desktops = [];
    const own = window.desktops;
    for (let i = 0; i < own.length; i++) {
        desktops.push(String(own[i].id));
    }
    return {
        id: windowId(window),
        title: String(window.caption),
        app: String(window.desktopFileName || window.resourceClass || ""),
        active: window === workspace.activeWindow,
        minimized: Boolean(window.minimized),
        desktops: desktops, // empty: on all desktops
        output: outputName(window),
        attention: Boolean(window.demandsAttention),
    };
}

function reportWindows() {
    if (!sendWindows) {
        return;
    }
    const windows = [];
    for (let i = 0; i < known.length; i++) {
        if (listed(known[i])) {
            windows.push(describe(known[i]));
        }
    }
    send("WindowsState", JSON.stringify(windows));
}

function watch(window) {
    known.push(window);
    window.fullScreenChanged.connect(reportFullscreen);
    window.outputChanged.connect(() => {
        reportFullscreen();
        reportWindows();
    });
    // the rest matter to the window list only
    window.captionChanged.connect(reportWindows);
    window.minimizedChanged.connect(reportWindows);
    window.desktopsChanged.connect(reportWindows);
    window.demandsAttentionChanged.connect(reportWindows);
    window.desktopFileNameChanged.connect(reportWindows);
    window.skipTaskbarChanged.connect(reportWindows);
}

function forget(window) {
    const at = known.indexOf(window);
    if (at >= 0) {
        known.splice(at, 1);
    }
}

workspace.windowAdded.connect((window) => {
    watch(window);
    reportFullscreen();
    reportWindows();
});

workspace.windowRemoved.connect((window) => {
    forget(window);
    reportFullscreen();
    reportWindows();
});

workspace.windowActivated.connect(() => {
    reportFullscreen();
    reportWindows();
});

const existing = workspace.windowList();
for (let i = 0; i < existing.length; i++) {
    watch(existing[i]);
}
reportFullscreen(); // at load: the current state (a fresh load after a shell restart)
