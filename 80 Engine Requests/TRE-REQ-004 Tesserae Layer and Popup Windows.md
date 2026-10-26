---
title: TRE-REQ-004 Tesserae Layer and Popup Windows
aliases: [TRE-REQ-004, Tesserae Surface Windows Request, Tesserae Layer Window Request]
type: engine-request
status: superseded
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [engine-request, spec/surface, tesserae, needs-verification]
related: ["[[ADR-0002 Relationship to Tesserae UI]]", "[[ADR-0003 Process Model]]", "[[TRE-REQ-001 Layer Surface Window]]", "[[V1 Scope]]", "[[80 Engine Requests]]"]
depends_on: ["[[TRE-REQ-001 Layer Surface Window]]"]
---

# TRE-REQ-004: Tesserae layer and popup windows

> [!warning] Superseded by [[ADR-0006 Shell Independent of Tesserae UI]] (2026-10-25)
> Withdrawn before it was carried to Tesserae. The shell no longer depends on `tesserae-ui`, so nothing is requested of Tesserae. The requirements (R1 to R9) and open questions move into the shell's own design: [[ADR-0007 Shell UI Layer]]. The note stays as a record of what Tesserae does today.

> [!summary]
> Let a Tesserae view be the content of a tre `LayerWindow` or `PopupWindow`, and let a Tesserae app run with no main window. Tesserae 0.5.1 opens only ordinary windows, so a shell built on `tesserae-ui` ([[ADR-0002 Relationship to Tesserae UI]]) cannot put a bar on screen from a YAML view. This request is addressed to the Tesserae project, not to tre: tre 0.5.8 already has the mechanism.

This note is carried to the Tesserae project by the maintainer ([[AGENTS#6. Engine requests (tre / Tesserae)]]). It is not filed from this vault. Numbers 002 and 003 stay reserved (see [[80 Engine Requests]]).

## Shell need

A shell opens, from YAML views and Python:

| Need | Use case ([[Personas and Use Cases]]) |
|---|---|
| A view as the content of a `LayerWindow` (bar, OSD, launcher, widget, panel), bound to one monitor | UC1, UC3, UC4, UC5, UC6, UC11 |
| The same view opened on several monitors, each with its own `Output` | UC1, UC10, UC11 |
| A view as the content of a `PopupWindow` hung off a rectangle of a layer window | UC2 |
| Layer-surface settings in the view file, changed live by hot reload | UC8 |
| An app with no main window, which stays up when any one surface closes | UC10 |

## Why it belongs in Tesserae

tre owns the mechanism: surface roles, outputs, input regions, margin animation. Tesserae owns how a view becomes a window: the `widget: Window` root, `open_window`, the ViewModel, theme and stylesheet binding, and hot reload ([[AGENTS#3. Layering principle]]). The shell should not duplicate that composition path. If it did, the shell would carry a second way to build and re-theme a view, which is the dialect split [[ADR-0002 Relationship to Tesserae UI]] avoids.

## What Tesserae does today

Source: local clone `/home/phil/Projects/pyDev/projects/tesserae` at commit `0eda3fe` (version 0.5.1.4, unreleased), read 2026-10-25. PyPI has `tesserae-ui` 0.5.1 (2026-10-19). #needs-verification: confirm each item below against the 0.5.1 release; the clone is ahead of PyPI.

| Fact | Where |
|---|---|
| The pin is `tesserae-engine==0.5.8`. | `pyproject.toml` |
| No source file, doc, plan or changelog mentions `LayerWindow`, `PopupWindow` or layer-shell. | search of `src`, `docs`, `design`, `PLAN.md`, `CHANGELOG.md` |
| `App` creates one main `Window` in its constructor and `run()` always adds it. | `src/tesserae/app.py:318`, `:1844` |
| `open_window(view, name, parent, modal, center)` builds a plain `Window(width=480, height=320)`, applies the view's `widget: Window` options, and returns an `AppWindow`. | `app.py:935-965` (the `Window(...)` at `:944`) |
| Closing the main window closes every other window and ends the app. | `appwindows.py` docstring; `docs/guide/windows-and-docks.md` ("Several windows") |
| Opening a window whose name is already open raises `ValueError`; a window is found by its view's name. | `app.py:950`, `:998` |
| The ViewModel is the one that serves the view's name; the theme, stylesheet and `app` are the app's. | `docs/guide/windows-and-docks.md` |
| `widget: Window` options are read when the window opens; hot reload does not re-apply them. | `docs/guide/hot-reload.md` |
| `modal=True` dims the parent with a scrim layer; `center` cannot place a window on Wayland. | `appwindows.py`, `app.py:962` |

tre side, for contrast ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]): `tre.App.run()` raises `RuntimeError` when no window is registered and ends when every window has closed ([App reference](https://mindderivative.github.io/tre/reference/app/)). A `LayerWindow` is constructed with `namespace` and binds to an `Output` at construction only.

## Proposed API

> [!danger] Proposal, not existing API
> Every name below is proposed for Tesserae. Nothing here exists. The Tesserae project decides names and shape. Keys that mirror tre keep tre's names ([[TRE-REQ-001 Layer Surface Window]]).

### 1. A layer window root in a view

A view whose root is `widget: LayerWindow` is the content of a `LayerWindow`, as `widget: Window` is for a window.

```yaml
name: Bar
widget: LayerWindow
namespace: tesserae-shell.bar     # required, constructor only
layer: top
anchor: [top, left, right]
size: [0, 32]
exclusive_zone: 32
keyboard: none
input_region: auto
children:
  - widget: Text
    text: "{{ clock.time }}"
```

- Keys: `namespace`, `layer`, `anchor`, `size`, `exclusive_zone`, `exclusive_edge`, `margin`, `keyboard`, `input_region`. `output` is not a view key (see 2).
- A key that has no meaning for a layer surface (`title`, `borderless`, `min_width`, `min_height`, `fullscreen`, `maximized`, `remember`, `title_bar`) is a load error that names the key and the file position, not a silent ignore. This matches tre, whose `set()` raises for the same keys ([LayerWindow reference](https://mindderivative.github.io/tre/reference/layer-window/)).
- The root is transparent with no padding or gap, as tre's layer window is. `style:` on the root paints the surface.
- `transparent` is on; `blur_behind` and `click_through` are the existing window keys, with `click_through` meaning `input_region: []`.

### 2. Opening it

```python
bar = app.open_layer("Bar", name="bar-DP-1", output=output, params={"output": output.name})
bar.window            # the tre LayerWindow
bar.output            # the Output it is bound to
```

- `open_layer(view, name=None, *, output=None, params=None, **overrides) -> AppWindow`. `overrides` replace view keys for this opening (for example a different `margin`). `output` takes an `Output` or a connector name and is required unless the shell accepts tre's deterministic default.
- The same view may be opened many times under different `name`s, one per monitor. The `name` is the key, as in `open_window`.
- `params` reach the view and ViewModel so one instance knows its monitor (see Open questions on ViewModel per opening).
- `AppWindow` gains `output` and `set(**props)` (forwards to `LayerWindow.set`). It keeps `window`, `close()`, `on_close()` and `closed`.
- Before `run()` the window opens with the others; while it runs, on the loop's next turn, as `open_window` does.

### 3. A popup root

```yaml
name: TrayMenu
widget: PopupWindow
size: [180, 120]
constraint_adjustment: [flip_y, slide_x]
grab: true
children: [...]
```

```python
menu = app.open_popup("TrayMenu", parent=bar, anchor_rect=(100, 0, 60, 32), anchor="bottom_left", gravity="bottom_right")
```

- View keys: `size`, `anchor`, `gravity`, `constraint_adjustment`, `offset`, `grab`. `parent` and `anchor_rect` are per opening, in the parent's coordinates.
- `parent` is an `AppWindow` for a `LayerWindow` or `PopupWindow`. A closed or unopened parent fails with a clear error (tre reports reason `"failed"`).
- The `closed` signal carries tre's reason (`"dismissed"` on an outside click or Escape). A click on another window of the same application reaches that window, so the shell closes the menu itself ([PopupWindow reference](https://mindderivative.github.io/tre/reference/layer-window/#popupwindow)).
- `modal` and `center` do not apply and raise if given.

### 4. An app with no main window

```python
app = App(main_window=False, root=HERE)
app.open_layer("Bar", output=output)
app.run()
```

- With `main_window=False`, `App` does not create or register the main `Window`. `app.window` is unavailable and says why.
- The app ends when every window has closed, not when one does, matching `tre.App.run()`. An explicit `app.quit()` ends it earlier.
- With no windows registered, tre raises `RuntimeError`. Tesserae gives a clear error, or runs idle if the shell opened none yet (a monitor set to "none", or no outputs). See Open questions.
- Screens, routes and the main-window title bar are not available, as for any second window today.

### 5. Hot reload

- Saving a `widget: LayerWindow` view re-applies `layer`, `anchor`, `size`, `exclusive_zone`, `exclusive_edge`, `margin`, `keyboard` and `input_region` through `LayerWindow.set`, which is live and one commit (tre). This differs from `widget: Window`, whose options are read only at open ([Hot Reload](https://mindderivative.github.io/tesserae/guide/hot-reload/)).
- `namespace` and `output` cannot change on a live window. Changing `namespace` in the file logs a warning that names the file and asks for a reopen. The shell reopens the window.
- A bad value leaves the window as it was and logs an `ERROR` with `file:line:column`, as for any view.

### 6. Events and animation reach the view

- tre events that matter to a shell are available as ViewModel handlers: `configure`, `moved`, `closed` (with `reason`), `warning`, `output_changed`. Minimum: Python can listen on `AppWindow.window` today, so this is a convenience; it is listed to avoid each shell wrapping the same thing.
- Margin animation and `window_region: drag_margin` already pass through `AppWindow.window.animate(...)` and the node property. No new Tesserae API is requested for them.

## Requirements

| # | Requirement |
|---|---|
| R1 | A `widget: LayerWindow` view opens a tre `LayerWindow` with the keys above and the view's content, themed with the app's theme and stylesheet. |
| R2 | A view opens any number of times under distinct names, each bound to its own `Output`. |
| R3 | A `widget: PopupWindow` view opens parented to an open layer or popup window with a given `anchor_rect`. |
| R4 | `App(main_window=False)` runs without a main window and ends when the last window closes. |
| R5 | Hot reload re-applies the live layer keys without recreating the window and reports the constructor-only keys. |
| R6 | A key with no meaning for a layer surface is a load error with a position. |
| R7 | Headless: a layer or popup view builds, themes and responds to `simulate` with no display, using tre's headless `LayerWindow` ([LayerWindow reference](https://mindderivative.github.io/tre/reference/layer-window/)). |
| R8 | No Python in layout or paint: all new Tesserae code runs in callbacks ([[AGENTS#3. Layering principle]]). |
| R9 | Threading: opening and closing run on the loop thread; other threads use `thread_handle().call_soon`. |

## Alternatives

| Alternative | Verdict |
|---|---|
| The shell builds `LayerWindow` itself and calls Tesserae's internal `_open_view(view, name, window)` (`app.py:911`). | Works today but depends on a private method and skips `open_window`'s bookkeeping (`AppWindow`, close handling, themed registration). Fragile across Tesserae releases. Prototype only. |
| The shell wraps Tesserae with its own window opener and view loader. | Duplicates composition and theming; two paths to maintain. Against [[ADR-0002 Relationship to Tesserae UI]]. |
| Drop `tesserae-ui` and build on tre directly. | Rejected in [[ADR-0002 Relationship to Tesserae UI]] (Option B). |

## If declined

1. Use the private-method prototype above, labelled throwaway, in `90 Research/`.
2. Write an ADR superseding [[ADR-0002 Relationship to Tesserae UI]] if the private path proves unstable. The shell would then own a thin view-to-window layer on tre.

## Open questions

- [ ] **ViewModel per opening.** Tesserae serves a view with "the ViewModel that serves its name". A bar opened on three monitors has three windows and, today, one ViewModel. Does each opening get its own instance (so it knows its monitor), or share one with `params`? The shell needs per-monitor state (the monitor name, its workspaces) and shared state (the clock). Recommendation: one ViewModel instance per opening, with shared services passed in. #needs-verification against the ViewModel binding code.
- [ ] **Zero windows.** tre raises `RuntimeError` with no registered window. A shell whose every monitor is "none" ([[V1 Scope#Multi-monitor]]) has none. Does Tesserae keep the loop alive with an idle hidden anchor, or does the shell open nothing and let `run()` return? Needs a tre answer or a Tesserae decision.
- [ ] **Output hot-plug in Tesserae.** `App.outputs()` and the `output_*` events are tre's. Does Tesserae expose them (`app.outputs`, `app.on("output_added")`), or does the shell use `tre.App` directly through `app._tre_app`? Recommendation: Tesserae exposes them, so the shell stays off private attributes.
- [ ] **Naming.** `widget: LayerWindow` and `widget: PopupWindow` against a `kind:` key on `widget: Window`. Tesserae's choice.
- [ ] **Version.** Which Tesserae release carries it, and is the pin `tesserae-engine>=0.5.8`?

## Acceptance criteria

- [ ] A `Bar_View.yaml` with a `widget: LayerWindow` root opens a bar on KWin that reserves its exclusive zone, using `app.open_layer`, with no main window.
- [ ] The same view opened on two outputs under two names yields two bars, each on its output.
- [ ] A `widget: PopupWindow` view opens next to its `anchor_rect`, flips at the screen edge, and fires `closed` with reason `"dismissed"` on an outside click.
- [ ] Editing `exclusive_zone` in the view file changes the live bar in one commit, with no restart.
- [ ] A key with no layer meaning (`borderless`, `title`) in a `widget: LayerWindow` view fails to load with `file:line:column`.
- [ ] Closing one bar leaves the app running; closing the last window ends it.
- [ ] A layer view builds and answers `simulate` headless in CI.
- [ ] An unplugged output closes its bar (reason `"output_removed"`) and the app continues.

## Links

- [[ADR-0002 Relationship to Tesserae UI]] · [[ADR-0003 Process Model]] · [[TRE-REQ-001 Layer Surface Window]]
- [Tesserae: Windows, Docks and Embedded Views](https://mindderivative.github.io/tesserae/guide/windows-and-docks/) · [Window Options](https://mindderivative.github.io/tesserae/guide/window-options/) · [Hot Reload](https://mindderivative.github.io/tesserae/guide/hot-reload/)
- [tre: LayerWindow](https://mindderivative.github.io/tre/reference/layer-window/) · [Outputs](https://mindderivative.github.io/tre/reference/outputs/) · [App](https://mindderivative.github.io/tre/reference/app/)
- [[80 Engine Requests]] · [[Index]]
