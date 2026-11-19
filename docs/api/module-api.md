# Module API

The Python API of a module: what a module's Python file imports, the class it writes, the context object it receives, the event an action gets, and the values it may send. For a walk through, with a module you can copy, read [Writing a module](../guide/writing-a-module.md). Every signature on this page was read from the code of tesserae-shell 0.1.2 and its unreleased changes; where the design notes say more than the code does, the page says what the code does ([What is not built](#what-is-not-built)).

A module's Python runs inside the shell, as you, with no sandbox ([Security](../guide/security.md)).

## What a module imports

```python
from tess_shell import Event, Module, action
```

`tess_shell` exports exactly these names:

| Name | What it is |
|---|---|
| `Module` | The base class of a module's class. |
| `action` | The decorator that marks a method as callable from a file or from the command line. |
| `Event` | What an `@action` receives. |
| `ServiceError`, `ServiceTimeout`, `ServiceUnavailable`, `BlockingCallError` | The exceptions of the service helpers ([Errors](#errors)). |
| `ServiceState` | An enum, `AVAILABLE` or `UNAVAILABLE`. |
| `__version__` | The shell's version string. |

The types the context hands out (`UseRecord`, `AppInfo`, `AudioState` and the rest) live in `tess_shell.modules.context` and `tess_shell.services.api`. They are for type hints; a module need not import them.

## The module class

A module's Python file holds exactly one class that extends `Module`. None, or more than one, is the error `module-classes`. A file that is missing is `module-no-python`; one that raises while it is imported, or has a syntax error, is `module-import`, with the line in your file.

The shell creates the class once for the module, however many uses it has. There are no constructor arguments: it creates the object without calling `__init__`, sets `self.ctx`, and then calls `__init__()` with no arguments, so `self.ctx` is already set in an `__init__` you write. If `__init__` raises, the module does not load (`module-init`).

```python
class Module:
    ctx: ModuleContext

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def reload(self) -> None: ...
    def validate_use(self, use: UseRecord) -> None: ...
    def use_added(self, use: UseRecord) -> None: ...
    def use_removed(self, use: UseRecord) -> None: ...
    def on_service_lost(self, name: str) -> None: ...
    def on_service_found(self, name: str) -> None: ...
```

Every method does nothing in the base class, so write only what you need. Every one is called on the shell's loop thread, one at a time, and a callback that is slow holds up the screen.

| Method | Called when | If it raises |
|---|---|---|
| `start()` | Once, after the files are read and the module's uses are known (`self.ctx.uses` is filled), after `validate_use` has run for each use. Return quickly. | The module is marked failed (`module-start`, with the line), and started again after a back-off ([Failure](#failure-and-restarts)). |
| `stop()` | The shell quits, the module's Python is about to be replaced, or the module has no use left. Stop your own threads and close your own connections: the shell cancels the context's subscriptions, not your threads. It has no timeout; it must return. | Logged as `module-stop`; the module is not restarted. |
| `reload()` | The module's layout (or its style file) changed and its Python did not. The module keeps running. `self.ctx.config` holds only `{"name": <module name>}` today, so there is not much to re-read; use it to start again from files of your own. | Marked failed, as `start`. |
| `validate_use(use)` | For each use when the module starts, and again when a use's params change. Quick, no I/O. Raise `ValueError` with a message to reject the use. | Only `ValueError` is handled: it is reported as the error `module-use`, `<use name>: <message>`, naming the layout file; the module still starts. Any other exception is not caught here. |
| `use_added(use)` | A use appeared while the module runs (a surface that shows it opened, or a reload added a use). Not called for the uses that exist when `start()` runs. The shell has sent `available` for it first if you use `ctx.dbus`. | Marked failed, as `start`. |
| `use_removed(use)` | A use went away. It is already gone from `self.ctx.uses`. | Marked failed, as `start`. |
| `on_service_lost(name)` | A well-known D-Bus name that this module made a proxy for lost its owner (`ctx.dbus`). `available` was sent as false just before: show the empty state. | Logged with the module's name (`on_service_lost('org.x') raised`); the module is not failed. |
| `on_service_found(name)` | That name has an owner again; its properties were read again (the `on_property_changed` callbacks got them). | As `on_service_lost`. |

The shell finds actions with `@action` on the class ([below](#actions)).

### A module's uses

```python
@dataclass(frozen=True, slots=True)
class UseRecord:
    key: str                    # "<Module>@<uid>"
    name: str                   # the dotted path name of the use, for messages
    uid: str
    monitor: str
    params: Mapping[str, Any]   # plain Python values, the defaults merged in
```

`self.ctx.uses` is a mapping from `key` to `UseRecord`, kept current by the shell as uses come and go. The `key` is what a module keeps its per-use state under and passes back to name a use (`ctx.send(..., use=key)`, `event.use`). A module is loaded when a Bar, Panel, Popup or Frame uses it, when it is called in a `For`, or when a shortcut or a `Call` names it (then it may have no use at all).

### Failure and restarts

A failure in `start`, `use_added`, `use_removed` or `reload` marks that module failed and no other. Its surfaces keep their last values. The shell logs the failure with the module's name and UID, and starts the module again, as a new instance from the file as it is, after 1, 2, 4, 8 and 16 seconds (a wait is at most 60 s; at most five tries). A run of 60 seconds without a failure counts as a new start. After the fifth try it stays failed until a reload, which gives it five new tries.

An exception in an `@action`, a tick callback, a `call_soon` callback, a service hook or a service callback is logged and not counted as a failure of the module; the control interface also emits it as `ErrorReported(rule, file, line, message, module)`, once a minute for each distinct error.

### Code reload

When the Python file changes the shell reads the new file first. If that works and has one class, `stop()` of the old instance runs, its context is closed (the tick and service subscriptions are cancelled, `call_soon` callbacks are dropped), and a new instance is created and started. If the new file fails to import or has no class, or two, the old instance keeps running and the findings are reported. The values the old instance sent stay in place until the new one sends.

## Actions

```python
def action[F: Callable[..., Any]](fn: F) -> F
```

`@action` marks a method as an action. Only marked methods can be reached from a file (`On_Click: name`, `Action: Call`), from a shortcut or from `tesserae-shell call`; any other method is not reachable. An action named like a built-in action (`Show`, `Hide`, `Toggle`, `Close`, `Call`) is refused at load (`action-clash`).

An action's first parameter is the `Event`. The parameters after it are the arguments of the handler, by name:

```python
@action
def bump(self, event: Event, amount: float = 1) -> None: ...
```

```tdl
On_Click { Action: bump, amount: <| params.step |> }      # bump(event, amount=...)
On_Click: bump                                             # bump(event): amount stays 1
Button { On_Click { Action: Call, Target: "Tally.bump", amount: 5 } }
```

* A handler's argument values are plain values or `<| |>` slots, evaluated when the event fires (a slot may read `event`, the module's values and the variables of an enclosing `For`).
* **Checking.** When the files are loaded the shell checks the argument names of every handler against the method: an unknown name is the finding `unknown-argument` (with the nearest parameter), a required parameter with no argument is `missing-argument`. An action with no parameter after the event, or with `**kwargs`, is not checked: it takes any names, through `event.args` (and, with `**kwargs`, as keywords). A `<| |>` argument is checked by name only. A handler that names an action the class lacks is `unknown-action`; a `Call` to a module that is not loaded is `call-module-not-loaded`. `tesserae-shell check` does not run Python, so these are reported when the shell starts or reloads.
* `event.args` is always the whole mapping of the handler's arguments, whatever the signature says.
* **From the command line,** `tesserae-shell call Module action ARG ...` binds the arguments by position to the parameters after the event, in order; more arguments than parameters, or a missing required one, is an error. An action that declares no parameter gets them as `event.args["0"]`, `["1"]` and so on. A **shortcut** with `Action: Call` binds its named arguments the same way as a handler.
* **The result.** What an action returns is ignored when a block raised the event; for `tesserae-shell call` it is the answer that is printed (it should be a value that can be written as JSON).
* **Errors.** An action that raises is logged with the module, the action, the event and the position of the block (`Tally.bump raised on On_Click`), and the event is not repeated. The module keeps running. In a control call the exception comes back as the call's error. An action that takes more than 50 ms is logged as a warning.
* An action runs on the loop thread, and while it runs `self.ctx.caller` is the `UseRecord` of the use whose block raised the event (`None` for a control call or a shortcut).

## Events

```python
@dataclass(frozen=True, slots=True)
class Event:
    name: str
    use: str
    args: Mapping[str, object] = {}
    time: float = time.monotonic()
    x: float | None = None
    y: float | None = None
    button: str | None = None
    old: str | bool | float | None = None
    new: str | bool | float | None = None
    text: str | None = None
    value: str | bool | float | None = None
    delta: float | None = None
    rect: tuple[float, float, float, float] | None = None
    key: str | None = None
    ctrl: bool = False
    shift: bool = False
    alt: bool = False
    meta: bool = False
    repeat: bool = False

    def stop(self) -> None: ...
```

The object is frozen. A field that does not apply to the event is `None` (`False` for the modifiers).

| Field | Meaning |
|---|---|
| `name` | The key of the handler without `On_`, lower case: `"click"`, `"secondary_click"`, `"middle_click"`, `"scroll"`, `"changed"`, `"released"`, `"submit"`, `"text_commit"`, `"key_down"`, and so on. `"call"` for a control call or a shortcut. |
| `use` | The key (`<Module>@<uid>`) of the use that holds the block with the handler. For a `Call` from another module's block it is the key of that block's use, not of the module called; for a control call or a shortcut it is the empty string. |
| `args` | The handler's arguments, by name (slots already evaluated); `"0"`, `"1"`... for positional values of a control call. |
| `time` | `time.monotonic()` when the event was made. |
| `x`, `y`, `button` | The pointer position in the window and the button (`"primary"`, `"secondary"`, `"middle"`) of a pointer event. |
| `old`, `new`, `value`, `text` | `On_Changed` of a control: the value before and after the user's change; `value` is the new one (a Toggle or Checkbox true or false, a Slider a number, a List the chosen entry's key, a text field its text). `On_Released` of a Slider: `old` is the value when the press began, `new` and `value` the final one. `On_Text_Commit`: `text` is the text that was committed. |
| `delta` | `On_Scroll`: one wheel step, +1 scrolling down and -1 up. |
| `rect` | A pointer event (`On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`): the block's `(x, y, width, height)` in the output's coordinates, what `ctx.popup(..., anchor=event.rect)` takes. `None` for a block inside a Popup, where the shell does not know the Popup's place. |
| `key`, `ctrl`, `shift`, `alt`, `meta`, `repeat` | `On_Key_Down` of a text field: the key as the engine names it (`"arrow_down"`, `"escape"`, or the character), and the modifiers held. |
| `stop()` | Keeps the event from going further up the tree (a Panel's Escape that hides it, the keys of shortcut mode), only while the handler runs. For a text field's `On_Key_Down` the module hears the key before the field acts, and the field acts whatever the module does: a stop cannot veto an edit. |

Which events exist, which blocks raise them and which of them are not raised yet (`On_Focus`, `On_Unfocus`, `On_Change`) is in the table in [Surfaces](../guide/surfaces.md#showing-hiding-and-toggling) and in each module's section of [Modules](../guide/modules.md). The built-in actions of a handler (`Show`, `Hide`, `Toggle`, `Close`, `Call`) are in the same place.

## The context

`self.ctx` is a `ModuleContext`. It is the module's whole view of the shell.

### Attributes

| Attribute | Type | Meaning |
|---|---|---|
| `ctx.name` | `str` | The module's name. |
| `ctx.uid` | `str` | The module's UID (the `UID:` line the shell wrote in the layout file). |
| `ctx.config` | `Mapping[str, Any]` | `{"name": <module name>}`. Nothing else is in it today: the module's own values are its params, per use ([`UseRecord.params`](#a-modules-uses)). |
| `ctx.uses` | `Mapping[str, UseRecord]` | The module's uses by key, kept current. |
| `ctx.caller` | `UseRecord \| None` | The use whose block raised the event being handled; set only while an `@action` runs from a block, else `None`. |
| `ctx.log` | loguru `Logger` | A logger bound to the module (`source="module:<name>"`). The shell's own log lines carry no window titles or file contents; what you log is yours. |

### Sending values

```python
ctx.send(key: str, value: object, use: UseRecord | str | None = None) -> None
```

Sends one value to the layout, where it is read by name in a `<| |>` slot. With `use` (a `UseRecord` or its key) it goes to that use; with none it goes to **every** use of the module. Safe to call from any thread; it never blocks and never raises into the caller.

* The value must be [plain](#values): a string, a number, a boolean, or a list or dict of those. Anything else, an empty key included, is an error in the log naming the module and the type, and the last value stays.
* The shell takes the queue once for each turn of its loop and keeps the **latest** value of each key for each use. A value that is sent and sent back inside one turn is not a change. A copy is made when you send, so changing your list afterwards changes nothing.
* A send to a use that does not exist is an error in the log (`unknown use`); to one that ended a moment ago it is dropped with a debug line.
* The key `available` is the shell's own for a module that uses `ctx.dbus`: the layer sends it. Do not send it yourself.

### Popups and the surface

These are for the loop thread.

```python
ctx.popup(name: str, data: Mapping[str, Any] | None = None, use: UseRecord | str | None = None,
          anchor: tuple[float, float, float, float] | None = None) -> None
ctx.close_popup(name: str | None = None) -> None
ctx.update_popup(name: str, data: Mapping[str, Any]) -> bool
ctx.is_popup_open(name: str) -> bool
```

* `popup` opens the Popup `name` beside the use that called (`ctx.caller`, so from an `@action`; or `use`), or beside the rectangle `anchor` (`event.rect`), and closes it if it is the one that is open. `data` is what the Popup's blocks read as `caller.data`. A Popup that does not exist, or a use on no open surface, is logged with the module and the name; nothing is raised. Called with no use and no `caller` it logs an error and does nothing.
* `close_popup` closes the open Popup, the one called `name` if given.
* `update_popup` gives the open Popup (and its open submenus) new `caller.data`; it is resolved again and only what differs changes, so it stays open, in place. `False` when it is not open.
* `is_popup_open` says whether the Popup (or one of its submenus) is open.

```python
ctx.surface.hide(use: UseRecord | str | None = None) -> bool
ctx.surface.show(use: UseRecord | str | None = None, *, hide_after: float | None = None) -> bool
ctx.surface.focus(name: str, *, select_all: bool = False, use: UseRecord | str | None = None) -> bool
ctx.surface.on_shown(callback: Callable[[UseRecord], None]) -> Subscription
```

`ctx.surface` is the surface a use is on; the use is `ctx.caller` or `use`. `hide` and `show` do what the built-in `Hide` and `Show` do to the Panel the use is on, and return `False` with one error logged when the use is on no Panel. `show` on a shown Panel keeps it shown and starts its `Hide_After` time again; `hide_after` (milliseconds) replaces that time for this show. `focus` gives the keyboard focus, inside the surface, to the block `Name: name` of the use, and with `select_all` selects its text; `False` when there is no such block or it cannot take focus (the compositor decides whether the surface itself has the keyboard, by its `Keyboard` key). `on_shown(callback)` calls `callback(use)` on the loop thread for each use on a Panel that has just been shown; the shell cancels it when the module stops. Reading `ctx.surface` raises `RuntimeError` when the shell has no surfaces.

### Shortcut mode

```python
ctx.focus.default: str | None            # read and write
ctx.focus.set_mode(name: str, value: bool) -> bool
```

`ctx.focus.default` is the `Name` of the surface that starts with the focus when shortcut mode is entered; `None`, the start value, is the Frame. Set it to a Bar, Panel, Frame or strip name (a strip is `<Frame>.<side>`); a name that is no surface is logged with the nearest names and the value does not change. `set_mode(name, True)` puts that surface in shortcut mode with the focus (and the shell in the mode if it was not); `False` on the surface that is in the mode leaves it for the whole shell. It returns `False`, with one error logged, when no surface has that name. See [Keyboard and shortcuts](../guide/keyboard.md).

### Assistive technology

```python
ctx.announce(text: str, *, politeness: str = "polite", use: UseRecord | str | None = None) -> None
```

Says `text` through assistive technology, once. `politeness` is `"polite"` (waits for the reader to finish) or `"assertive"` (interrupts). With no `use` it is said for the module's first use that is on an open window, so a module used on two Bars is not read twice; with `use`, for that use's window (`ctx.caller` is not consulted). It is said even when the module's block is hidden, and the same text twice running is said twice. Safe from any thread. Nothing is said, with one debug line, when no use is on an open window or no screen reader is connected. An empty text, or a politeness other than the two, raises `ValueError`. The text is never logged.

### Time and threads

```python
ctx.on_tick(unit: str, fn: Callable[[], None]) -> Subscription
ctx.call_soon(fn: Callable[[], None]) -> None
ctx.run_callback(fn: Callable[..., Any], *args: Any, entry: str | None = None) -> None
```

* `on_tick("second" | "minute", fn)` calls `fn()` at the start of each second or minute, on the loop thread. The times come from the wall clock each time, so a suspend or a changed clock corrects itself within a tick. One thread serves every module and sleeps while nobody has subscribed. Another unit raises `ValueError`. The returned `Subscription` has `cancel()`; the shell cancels it when the module stops. An exception in `fn` is logged with the module's name (`a tick callback raised`) and does not fail the module.
* `call_soon(fn)` runs `fn()` on the loop thread soon. It may be called from **any thread**; it is how a thread or a D-Bus callback hands work back to the loop. An exception is logged with the module's name. A callback is dropped once the module has stopped. It raises `RuntimeError` if the shell has no loop to call into.
* `run_callback(fn, *args, entry=None)` calls `fn(*args)` as a callback of this module on the loop thread, so that the watchdog and the slow-callback record name the module and the entry (`entry`, or `fn`'s name) while it runs. The shell's own helpers use it; a module rarely needs to. An exception goes on to the caller.

There is no `ctx.thread`, `ctx.every` or `ctx.after`: start threads with `threading` and bring results back with `send` or `call_soon`.

### The context's helpers

Each is made the first time it is read and cancelled when the module stops. A helper raises `RuntimeError` ("the shell has no ... service") when the shell has not wired it.

#### `ctx.dbus`

```python
ctx.dbus.available -> bool                       # any thread
ctx.dbus.session() -> Bus
ctx.dbus.system() -> Bus
ctx.dbus.close() -> None
```

The shell's own D-Bus connection (one service thread for every module). Nothing connects until a proxy is used. Reading `ctx.dbus` the first time sends `available` false to the layout at once, and the layer sends the real value when it has read the services; `available` is true while every service the module made a proxy for has an owner. When one loses its owner the module gets `on_service_lost(name)`; when it returns, `on_service_found(name)`.

```python
bus.proxy(name: str, path: str, interface: str | None = None, *, optional: bool = False) -> Proxy
bus.watch_prefix(prefix: str, on_added: Callable[[str], None], on_removed: Callable[[str], None]) -> Subscription
bus.forget(name: str) -> None
bus.state(name: str) -> ServiceState
bus.run(coro) -> concurrent.futures.Future
bus.run_blocking(coro, timeout: float | None = None)

await proxy.get(prop: str, *, interface: str | None = None, fresh: bool = False) -> Any
await proxy.call(method: str, args: Sequence[Any] = (), signature: str = "", *,
                 interface: str | None = None, timeout: float = 5.0) -> Any
await proxy.set(prop: str, value: Any, signature: str, *, interface: str | None = None,
                timeout: float = 5.0) -> None
proxy.on_property_changed(callback: Callable[[Mapping[str, Any]], None], *,
                          interface: str | None = None, initial: bool = True) -> Subscription
proxy.on_signal(member: str, callback: Callable[..., None], *, interface: str | None = None) -> Subscription
```

The `async` methods are coroutines for the service thread: run one with `bus.run(coro)` (it returns a future at once and never blocks; an exception that nobody reads from the future is logged with the module's name) or, from a thread of your own, `bus.run_blocking(coro, timeout)`, which waits and raises `BlockingCallError` on the loop thread and on the service thread. The callbacks of `on_property_changed` and `on_signal`, and of `watch_prefix`, run on the service thread: keep them short, never block, and use `ctx.send` or `ctx.call_soon` from them. A proxy for a well-known name makes the layer watch it; `optional=True` still gives the hooks but does not count in `available`. `signature` is the D-Bus type string of the arguments; a `v` argument is written as a `(signature, value)` pair. Every call has a 5 s timeout and raises `ServiceTimeout`, `ServiceUnavailable` or `ServiceError`.

#### `ctx.audio`

```python
ctx.audio.available -> bool
ctx.audio.state -> AudioState | None
ctx.audio.on_changed(callback: Callable[[AudioState | None], None]) -> Subscription
ctx.audio.set_volume(percent: float) -> Future[None]
ctx.audio.step(delta: float) -> Future[None]
ctx.audio.set_muted(muted: bool) -> Future[None]
ctx.audio.toggle_mute() -> Future[None]
ctx.audio.toggle_mic() -> Future[None]
ctx.audio.set_output(name: str) -> Future[None]
```

The sound server, through the shell's own client of the PulseAudio protocol (`pipewire-pulse` or PulseAudio). `on_changed`'s callback runs on the service thread, once with the current state when it is known and then each time it differs; `None` means the server went away. `AudioState` has `output: Output | None`, `volume: int` (percent, may be above 100), `muted`, `has_mic`, `mic_muted` and `outputs: tuple[Output, ...]`; an `Output` has `name`, `description` and `kind` (`SPEAKER`, `HEADPHONES`, `HDMI`, `BLUETOOTH` or `OTHER`). The setters return a future at once; `set_output` fails with `AudioError` in the future for an unknown output. The shell's `Audio` module is written on this.

#### `ctx.icons`

```python
ctx.icons.theme_icon(name: str, size: int, theme_path: str | None = None) -> str | None
ctx.icons.pixmap_icon(pixmaps: Sequence[Sequence[Any]], size: int, source: str = "") -> str | None
ctx.icons.png_icon(data: bytes, source: str = "") -> str | None
ctx.icons.app_icon(app: str, size: int) -> str
ctx.icons.app_name(app: str) -> str
ctx.icons.on_theme_changed(callback: Callable[[], None]) -> Subscription
```

Turns icon names and pixmaps into a reference that a block's `Icon:` slot shows (an SVG document, or the name of pixels the shell holds; never a path). The calls read files, so call them from a thread of your own or the service thread, not from the loop thread. `theme_icon` follows the freedesktop icon theme rules and returns `None` when no theme has the icon; `app_icon` takes a desktop file's id and always returns a reference (`mdi:application-outline` at the end); `app_name` returns the application's name in your language, or `app` itself. `on_theme_changed` runs on the thread that learned of the change; icons made before it are from the old theme.

#### `ctx.tray`

```python
ctx.tray.on_host(callback: Callable[[bool], None]) -> Subscription
```

The shell as a StatusNotifier host. `callback(hosted)` runs on the service thread, `True` once the shell is registered with a watcher and `False` while it is not. The shell owns the host's bus name; a module cannot take another.

#### `ctx.windows`

```python
ctx.windows.available -> bool
ctx.windows.ready -> bool
ctx.windows.list() -> tuple[WindowInfo, ...]
ctx.windows.on_changed(callback: Callable[[], None]) -> Subscription
ctx.windows.activate(window_id: str) -> Future[bool]
ctx.windows.minimize(window_id: str) -> Future[bool]
ctx.windows.close_window(window_id: str) -> Future[bool]
```

The open windows, from the shell's KWin script. Loop thread. The first `on_changed` turns the list on; with no subscriber the script sends no title, class or id. `available` is false on another compositor or with the script off. A `WindowInfo` has `id`, `title`, `app`, `active`, `minimized`, `desktops`, `output`, `attention`. The three actions start a one-shot KWin script; the future says whether KWin loaded it, and the list changes when KWin has acted. The KWin script has not been checked on a real KWin by hand yet ([Modules](../guide/modules.md#tasks)).

#### `ctx.apps`

```python
ctx.apps.ready -> bool
ctx.apps.search(query: str, limit: int = 8) -> list[AppInfo]
ctx.apps.get(app: str) -> AppInfo | None
ctx.apps.launch(app: str, *, use: str | None = None, on_done: Callable[[LaunchResult], None] | None = None) -> None
ctx.apps.on_changed(callback: Callable[[], None]) -> Subscription
ctx.apps.refresh() -> None
```

The installed applications. Loop thread. The first read builds the list on a worker thread. `launch` starts the application detached from the shell, after asking the surface of the use (`use`, else `ctx.caller`) for an activation token, which must come from the handler of the key or click that starts it; with no use it starts without one. An `AppInfo` has `id`, `name`, `generic_name`, `comment`, `icon`, `keywords`, `terminal`, `path`; a `LaunchResult` has `ok`, `error`, `name`. The Applications module is written on this ([Keyboard and shortcuts](../guide/keyboard.md#the-launcher)).

### Errors

`ServiceError(service, message, name="")` is the base: `.service` is the bus name, `.detail` the message without it, `.name` the D-Bus error name. `ServiceTimeout` is a call that did not finish in time; `ServiceUnavailable` is a service with no owner or a bus that cannot be reached (the layer has set the service's state to `UNAVAILABLE`); `BlockingCallError` is a blocking form used on the loop thread or the service thread. The sound server's are `AudioError` and `AudioUnavailable` in `tess_shell.services.api`.

## Values

What a module sends is turned into what a block's key wants when the slot that reads it is evaluated. The two steps:

**1. What `ctx.send` accepts.** A string, an `int`, a `float` or a `bool`; a list or tuple of those (a tuple is stored as a list); a dict with `str` keys whose values are of those kinds; all of that nested, up to eight levels deep. Nothing else: not `None`, not a `datetime`, not bytes, not an object. A list feeds a `For` (`For item In <| items |> Key <| item.id |>`) and a dict is read with a dot (`<| item.name |>`). The expression language reads the values; it cannot call your Python.

**2. What a key accepts from a slot.** The key's kind decides. A value of another kind, or out of range, is a warning in the log naming the position, the key and what was wrong, and the block keeps its last value. A slot whose value is `None` leaves the key as it is.

| Kind of key | The slot's value |
|---|---|
| text (`Text`, `Label`, ...) | a string |
| number, positive, whole | a number (not a boolean); a whole key takes no float |
| boolean (`Visible`, `Checked`, ...) | `True` or `False` |
| length (`Width`, `Height`, ...) | a whole number of pixels, or the string `"50%"`, `"AUTO"` or `"EXPAND"` where the key allows it |
| colour | a string: `"#RRGGBB"`, `"#RRGGBBAA"`, `"#RGB"`, `"#RGBA"`, `"rgb(r g b)"`, `"rgba(r g b a)"` (alpha 0.0 to 1.0) or `"transparent"`. A tuple, or a theme token name, is not accepted; the `$color.primary` token form is for a file, not for a sent value. |
| enum (`Role`, `Flex`, ...) | one of the key's upper-case words (`"HORIZONTAL"`); a lower-case word is refused with a hint |
| four sides, corner radii | one number, or a list of four numbers (sides are left, top, right, bottom; radii are top-left, top-right, bottom-right, bottom-left) |
| icon | an icon name (`"mdi:home"`) or a file name, looked up as a name written in a file is; a reference from `ctx.icons` |
| font family | a name, or a list of names |
| image | the path of an image file |

A param of the module is typed by its `Type` (`string`, `number`, `boolean`, `path`, `icon`); a use may give a param a slot too.

## What is not built

The design notes (the Python API section of the design record) go further than the code in these places. The code wins; this is what is missing today:

* **No `ctx.thread`, `ctx.every` or `ctx.after`.** Threads are your own, timers are `ctx.on_tick` (seconds and minutes only).
* **The shell does not join your threads and `stop()` has no timeout.** `stop()` is called directly on the loop; stop your own threads in it.
* **`ctx.config` holds only the module's name.** The design says it holds the module's TDL values.
* **`ctx.send` converts nothing on its own.** There are no hex-to-tuple, theme-token, float-component or `datetime` conversions on send: a colour is one of the strings above, a time is a string you format. The design's list of four conversions is not built as such. `None` is refused.
* **No images through `send`.** An icon is a name or a reference from `ctx.icons`; a picture is a file path.
* **A module cannot declare the types of the keys it sends.** The key a slot reads is typed by the block's key, not by the module.
* **Custom blocks (a `Block` class with `Prop` helpers in a module's Python) do not exist.** A module's blocks are the ones the shell has ([the blocks](../guide/first-bar.md#the-blocks-you-can-put-in-a-bar)).
* **An action's return value** is ignored for a block's event; it is returned only to a control call.
* **No Python form of a shell file.** See [The Python builder](python-builder.md).
