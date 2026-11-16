/*
    Tesserae Shell: a one-shot KWin script (Tasks Module > Acting on a Window). The shell loads it
    through /Scripting, starts it and unloads it again. It finds the window whose internalId is the
    id below and asks it to close, when it can be closed. The shell writes the id into this template
    after checking that it is a UUID: no text of a window ever goes into a script.
*/
(function () {
    const wanted = "__WINDOW_ID__";
    const windows = workspace.windowList();
    for (let i = 0; i < windows.length; i++) {
        const window = windows[i];
        if (String(window.internalId).replace(/[{}]/g, "") !== wanted) {
            continue;
        }
        if (window.closeable) {
            window.closeWindow();
        }
        return;
    }
})();
