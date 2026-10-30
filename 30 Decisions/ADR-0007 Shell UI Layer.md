---
title: ADR-0007 Shell UI Layer
aliases: [ADR-0007, Shell View Language]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-29
tags: [adr, architecture, needs-verification]
related: ["[[ADR-0006 Shell Independent of Tesserae UI]]", "[[V1 Scope]]", "[[Goals and Non-Goals]]"]
depends_on: ["[[ADR-0006 Shell Independent of Tesserae UI]]"]
---

# ADR-0007: Shell UI Layer

> [!summary]
> The shell builds on tre alone, so it must supply what tre leaves out: a way to describe views, reactive values, a theme and a small widget set. This ADR proposes a small layer owned by the shell, sized to the surfaces in [[V1 Scope]].

> [!success] Accepted 2026-10-25
> The maintainer chose Option A.

> [!warning] View format partly superseded by [[ADR-0014 Shell File Language]] (2026-10-29)
> Shell files are written in the Tesserae Data Language (TDL), not YAML. The YAML examples and `*.yaml` names below show the keys and structure as decided; the file format and extension change. The decisions on keys, modules, names, UIDs and the registry stand.

## Context

tre provides mechanism only: nodes, layout, paint, animation, input, text, accessibility, layers and shaders. It has no widgets, no theme and no file I/O ([[AGENTS#1. What Tesserae Shell is]]). The shell therefore owns:

| Need                    | Why the shell needs it                                                                                                                                 |
|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| A view description      | The vision promises YAML views edited by a shell author ([[Goals and Non-Goals]] G1, [[Personas and Use Cases]] P1, P2).  |
| Reactive values         | Modules push changes (clock, battery, volume) into views from other threads, through `LoopHandle.call_soon` ([[AGENTS#3. Layering principle]]). |
| Theme and design tokens | One look across bar, popups and OSDs, light and dark, high contrast, reduced motion ([[Goals and Non-Goals]] G7).                      |
| A widget set            | Text, icon, button, row, column, slider, list, image, menu item, tray icon.                                                                            |
| Live reload             | Saving a view or theme updates open surfaces ([[Goals and Non-Goals]] G2).                                                             |
| Errors with position    | `file:line:column` for every config mistake ([[AGENTS#3. Layering principle]]).                                                                 |

What Tesserae has for reference (not a dependency): a YAML view language with Python ViewModels, `Signal`/`Computed`/`Effect`, Material Design 3 components, themes, stylesheets and hot reload ([Tesserae overview](https://mindderivative.github.io/tesserae/)). Its source is the maintainer's own, so its design can be read freely.

## Options

### Option A — A Small Shell-owned Layer on Tre (Recommended)

The shell defines a YAML view format limited to what surfaces need, a small reactive core, a token-based theme and about a dozen widgets, all built on tre nodes. It reads Tesserae's design for guidance and shares no code.

- **For:** one dependency (tre); a view format shaped for surfaces, monitors and modules; no coupling to Tesserae's release or scope; keeps [[ADR-0006 Shell Independent of Tesserae UI]] literal.
- **Against:** new work: parser, binding, reactive core, theme, widgets, hot reload, error reporting. Two similar-looking YAML formats exist across the maintainer's projects.

### Option B — Copy Parts of Tesserae into the Shell

Take the reactive core, theme code and widgets as a one-time copy and let them diverge.

- **For:** faster start.
- **Against:** a fork the maintainer must keep in step by hand; defects fixed in one place stay in the other; unclear licensing and ownership of the copy over time.

### Option C — Extract a Shared Core Package from Tesserae

Split Tesserae into a core (reactivity, theme, view language) and an app layer, and let the shell depend on the core only.

- **For:** one implementation.
- **Against:** needs Tesserae to be restructured, which is the load the maintainer wants to avoid, and still couples the shell to Tesserae's releases.

## Decision

Accepted 2026-10-25 by the maintainer in chat: **Option A**, a small shell-owned layer on tre. It keeps the shell completely separate from Tesserae UI and dependent on tre (and, from [[ADR-0008 Tesserae Expression Language]], on the separate TEL library). The extra work is accepted. Tesserae and the shell may each ask tre for additions; a request from either can serve both, and tre is where they meet.

### File Naming (2026-10-25)

Decided by the maintainer in chat. The shell's files are named so nobody mistakes them for Tesserae files: a Tesserae `<Name>_View.yaml` dropped into a shell must not appear to work.

- The shell does not use Tesserae's `_View.yaml`, `_ViewModel.py` or `_Component.yaml` names. For themes, styles and stylesheets it uses the plain suffixes `*_Theme.yaml`, `*_Style.yaml` and `*_Stylesheet.yaml` (decided 2026-10-25, below). The name alone does not say whose file it is; the required `shell:` key does.
- A shell is written either as one `*.yaml` file for the whole shell, or as a `Main_Shell.yaml` that imports several `<Name>_Shell.yaml` files and builds the shell from them. Both forms are valid.
- A Tesserae file placed in a shell is refused with an error that names the file and says it is not a shell file (see Open items for how a shell file is recognised).
- Python module files are `<Name>_Module.py` (see Modules below).
- Theme, style and stylesheet files are `<Name>_Theme.yaml`, `<Name>_Style.yaml` and `<Name>_Stylesheet.yaml` (decided 2026-10-25, replacing `_ShellTheme`, `_ShellStyle` and `_ShellStylesheet`). Tesserae uses the same suffixes, so a file is a shell file only if it carries the required `shell:` key (and a Tesserae file does not). The maintainer's reasoning: file names such as `_Style.yaml` are in wide use, so a shared suffix is not the problem; the version key is the discriminator. Tesserae side: the maintainer has told the Tesserae project to add a matching version key (`tesserae: <version>`) to all its `.yaml` files, so each side can refuse the other's files; Tesserae is working on it (maintainer report, 2026-10-25). Nothing is asked of Tesserae from this vault. #needs-verification: the key name and format, and the release that carries it, until Tesserae publishes them.

### Recognising a Shell File and Importing (2026-10-25)

Decided by the maintainer in chat.

- Every shell file has a required top-level `shell:` key with a format version. A file without it is not a shell file and is refused with an error naming the file. This also covers a one-file shell with any name.
- A shell file imports another with `import:` under `children:`, naming a `<Name>_Shell.yaml` file. `children:` is a mapping, not a list. A single-file shell writes the same content inline as keys and values indented under `children:`. The two forms mean the same thing.
- **Imports nest.** An imported file can import further files. Reason: a small change then stays inside one small file and does not break the rest.

The maintainer's example, as given (2026-10-25). It is a basic example, **not exact implementation guidance**; the grammar is set in `41 TDL Reference/`:

```yaml
shell: v1234
type: Shell

root:
    name: shell_root # Required, unique per monitor; each yaml file gets an assigned UID automatically
    monitor: DP-1
    children:
        import: TopBar_Shell.yaml
        child: 
            name: panel_dock # Unique per monitor
            kind: bar
            style: Dock_Style.yaml
            modules: # Modules have to be imported as they may have differing rules
                module: Audio_Module.yaml # with a connected python script
                module: Network_Module.yaml
        child:
            name: panel_start_menu
            kind: panel
            style: CornerPanel_Style.yaml
            modules:
                module: Applications_Module.yaml
```

Revised by the maintainer the same day: a child or module is keyed by its own unique name, not by a repeated `child:` or `module:` key. The example then reads (illustrative, not exact):

```yaml
shell: v1234
type: Shell

root:
    name: shell_root
    monitor: DP-1
    children:
        import: TopBar_Shell.yaml
        panel_dock:                       # unique per monitor
            kind: bar
            style: Dock_Style.yaml
            modules:
                audio: Audio_Module.yaml      # unique name: the module file
                network: Network_Module.yaml
        panel_start_menu:
            kind: panel
            style: CornerPanel_Style.yaml
            modules:
                applications: Applications_Module.yaml
```

What the example shows, and what is decided:

| Element                                     | What it shows                                                                                                                        | Status                                                                                                                                       |
|---------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `shell: v1234`                              | The required top-level key carries a version value.                                                                                  | Key decided. The version format (`v1234`) is the example's; not decided.                                                                     |
| `root:`                                     | A shell file has a root that owns the tree.                                                                                          | Implied.                                                                                                                                     |
| `root.name`                                 | A name, required and unique per monitor. Every YAML file also gets a UID, written into the file (see Config directory and registry). | Decided 2026-10-25.                                                                                                                          |
| `monitor: DP-1`                             | A root is bound to one monitor.                                                                                                      | Decided 2026-10-25: `monitor` accepts anything the shell gives it, and a root with no `monitor` is ignored (see Monitors, names and errors). |
| `children:` with `import:`                  | `import:` pulls in a `<Name>_Shell.yaml`.                                                                                            | Decided.                                                                                                                                     |
| `<unique_name>:` entries                    | Children and modules are keyed by a unique name instead of a repeated `child:` or `module:` key.                                     | **Decided 2026-10-25.** A child's name is unique per monitor.                                                                                |
| `kind: bar` / `panel`                       | A surface kind. The example first said `dock` and `corner_panel`; a dock is a bar, and a corner panel is a panel.                    | Decided 2026-10-25: the types are Bar, Frame, Panel, Popup ([[Surface Types]]).                                        |
| `style: Dock_Style.yaml`                    | A style file per surface, `<Name>_Style.yaml`, with `shell:` and `type:`.                                                            | Decided 2026-10-25 (see File naming).                                                                                                        |
| `modules:` and `<name>: <Name>_Module.yaml` | Modules are imported by file.                                                                                                        | Decided in outline: see Modules below.                                                                                                       |

### What a Module is (2026-10-26)

Corrected by the maintainer in chat on 2026-10-26. Earlier notes treated a module as a data source that surfaces read; that was a misreading. **A module is a self-contained piece of the shell with three parts:**

| Part   | File                                                    | Holds                                                                                           |
|--------|---------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| Layout | `<Name>_Module.yaml`                                    | The visual layout (widgets) and the data positioning (expressions), plus the module's `params:` |
| Style  | `<Name>_Style.yaml`, named by the module's `style:` key | The look and feel of the layout: classes, per-widget defaults                                   |
| Logic  | `<Name>_Module.py`                                      | What the module needs to do: reading sources, handling actions, deciding values                 |

- **A surface places modules.** A surface lists the modules it shows, under `modules:`, and passes each its `params`. The surface is the container; the module brings its own widgets.
- **Params.** A module declares typed params in its YAML (`params: text: {type: string}`). A use passes values for them in the shell file. The shell checks them against the declaration.
- **The Python is the module's logic**, not its layout. It reaches its YAML by file name, unique name or UID and can read the rest of the file ([[ADR-0007 Shell UI Layer#Modules (2026-10-25)]], binding). It sends values to shell entry points, which feed the module's own widgets.
- **Data positioning is in the module's YAML**, as expressions over the values the Python sends and the params it receives. Which names an expression reads is not settled (see Open items).
- The earlier decisions below stand: one instance per module file, the matching `.py` is required, the module keeps its own data, the shell renders.

The maintainer's example, with its simplifications, is in [[Module Context#Example: the Label module]].

### Keys that Say what a Thing is (2026-10-26)

Decided by the maintainer in chat, from the Label example.

| Key       | Names                 | Values                                                                          |
|-----------|-----------------------|---------------------------------------------------------------------------------|
| `type:`   | The type of a file    | `Shell`, `Module`, `Theme`, `Style`, `Stylesheet`                               |
| `kind:`   | The kind of a surface | `bar`, `frame`, `panel`, `popup`                                                |
| `widget:` | A widget              | `Text`, `Icon`, `Box`, `FlexBox`, ... ([[V1 Widgets]]) |

- **Surfaces do not nest.** A surface is never inside another surface; they are siblings and refer to each other by name ([[ADR-0007 Shell UI Layer#Keys that say what a thing is (2026-10-26)]]). The layout nests like this: a shell file holds surfaces, a surface places modules, a module holds widgets, and widgets nest inside container widgets.
- `widget: Text` and `Text` mean the same thing. The type may be the key (`Text:`) or the value of `widget:`. Where two widgets of one type sit in one container, the unique-name form is used: a unique name as the key, with `widget: Text` inside it.
- **Containers.** `Box` is a basic container with no auto-stacking; unstyled it is invisible, fully styled it is a panel of its own. `FlexBox` stacks its children automatically, with `alignment` vertical or horizontal. This replaces Row and Column in [[V1 Widgets]].
- **Params.** A module's declared params are what a use passes; `use.params` is the name in Python ("params matches the YAML").
- **Module values.** Expressions in the module's YAML read `params.<name>` and the values the Python sends, under their own names. Addressing a widget directly by its `name:` is optional.
- **The module's style file** is `type: Style`, named by the module's `style:` key.

### Blocks, Modules and Styling (2026-10-26)

Decided by the maintainer in chat. This supersedes the earlier `widget:` key, the separate container key, the `modules:` list and the `module:` key.

Building blocks are built in, and are called with `block:`. They need no name or UID, because they are basic built-in functions: calling one from YAML makes the shell's Python build it.

| Group      | Blocks                                                                                                 |
|------------|--------------------------------------------------------------------------------------------------------|
| Containers | Box, FlexBox, Grid                                                                                     |
| Typography | Text, TextField, a multi-line variant of TextField                                                     |
| Graphics   | Bitmap (rasterized), SVG (vector)                                                                      |
| Shapes     | Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path (a free-form path, added 2026-10-26) |
| Other      | Terminal, Canvas                                                                                       |

Modules are composed in YAML from blocks and other modules. The maintainer's list: Spacer; Label (a single line, no wrap); TextBox (multi-line text, not editable); TextInput (a single-line TextField, editable); TextEditor (a multi-line TextField variant, editable); Button; Icon; Image (png, jpeg, gif, webp); List; Slider; ProgressBar; Menu and MenuItem; Revealer (a must have); Stack; Badge; Tooltip; Toggle; Checkbox; Marquee text. (TextInput, TextBox, TextEditor and Checkbox were added on 2026-10-26, after the first list.)

Calling things:

- `block: <name>` calls a building block.
- A module is called by its unique `name:`, which is required for a module. The shell registers the module and gives it a UID, and the registry resolves the name.
- `widget:` and `module:` are dropped. The word "module" survives only as `type: Module`.
- `import: <Name>_Module.yaml` nests modules, to build a fully custom module out of others.
- A module's params are keys on the call.

Styling:

- It applies to blocks and to everything else that can be styled. Three kinds of file and one inline form: `<Name>_Theme.yaml`, `<Name>_Stylesheet.yaml`, `<Name>_Style.yaml`, and inline `style:`.
- Customising a block is referencing another stylesheet or style, or writing inline `style:`. A custom style is not a full replacement: it changes only what it names.
- Priority, lowest to highest: theme, then stylesheet, then style, then inline `style:`. It applies to all styling.
- Imports go downwards. A theme can import stylesheets and styles, or use inline styling. A stylesheet can import styles, or use inline styling, but not a theme. Inline `style:` can import a theme, a stylesheet or a style, and can use inline styling. Priority still follows the type of each file, not the path it was imported by.

The exact form of a module call, and the other answers of 2026-10-26, are in the next section.

### Module Call, Shipped Modules and Path (2026-10-26)

Decided by the maintainer in chat.

- **The form of a module call.** In `children:`, a module is called by its unique name as the key, with its params as keys beneath it, and `style:` beside them. `import:` embeds a module file at that position, which is how modules nest. The maintainer's example:

```yaml
children:
    import: Custom_Module.yaml          # essentially embeds the yaml in this position
    Label:                              # a module, called by its unique name
        text: "This is a title"         # a param
        style:
            import: Custom_Style.yaml   # inline style can import a style file
    Icon:
        svg: home.svg                   # or a file path; wrap in quotes if needed
        style:
            foreground: "#ffffff"
            size: 18
```

- **Text (multi-line) was a mistake; it is TextBox.** The block `Text` stays a block, and the name `Text` is no longer both a block and a module. Clarified by the maintainer the same day: Label and TextBox are bodies of Text and are not editable (Label is one line, TextBox is multi-line); TextInput (single-line) and TextEditor (multi-line) are TextField variants and are editable.
- **Shipped modules get a stable registry-only UID,** and a user module of the same name overrides one (the shell's own package cannot be written to).
- `Path` is a block (a free-form path, for the Frame's concave corners and Panel joins).
- **Feasibility.** The maintainer reports that Revealer, Marquee, Stack, Slider and Toggle can be built from the blocks and that this was tested on Tesserae. Not independently verified here.

### Placement, Checkbox and Popups (2026-10-27)

Decided by the maintainer in chat, from the fifth flow diagram.

- Checkbox is a separate module from Toggle. Both give the same result, but a Toggle is a switch and a Checkbox is a check box.
- A building block can be placed anywhere: on a surface, in a container or in a module. Blocks are most commonly used inside a module; the diagram's arrow from Module to Block shows the common case, not a limit.
- A popup holds containers and modules.

### Structure Answers (2026-10-26)

Decided by the maintainer in chat, from the Popup/Panel and structure questions.

- **A popup can be called by many modules, and it must know what called it,** so its data is relevant to the caller's context. The caller's record (the calling module, the use, its params, the anchor) is available to the popup's own modules and expressions.
- `children:` is the only holder. A surface, a container and a popup hold their contents under `children:`. `modules:` goes away. How a module use is written inside `children:` waits for the widget/module decision below.
- **A container is a fundamental building block, not a widget,** so it gets its own key (name not decided; `container:` is the suggestion).
- **Names.** Anything with a unique name gets a UID. A layer window (surface), container, module, widget or special case can have a name. **Names are unique across the shell, not per monitor** (this supersedes "unique per monitor" in the earlier sections). A name or UID is reachable from anywhere in the shell through the registry, nested or not. (See Open items for how repeated uses of one definition get unique names.)
- Popup focus (replaced the same day): an open popup takes the keyboard and mouse itself, with nothing passed at call time, and closes on an outside click or Escape. It is on by default; tooltip-like popups opt out. See Open items.
- Settled later the same day: the widget and module model, see Blocks, modules and styling above ([[Shell Structure#Blocks and modules (decided 2026-10-26)]]).

### Modules (2026-10-25)

Decided by the maintainer in chat:

- A module is a `<Name>_Module.yaml` file plus a matching `<Name>_Module.py`. The shell framework expects the Python file and requires it. A module with no matching `.py` is a load error that names both files.
- **A module may have a style.** Either an optional `<Name>_Style.yaml` file, or a `style:` key with the values written inline. (Updated 2026-10-26: the style file is `type: Style`, named by the module's `style:` key; it was `type: Module` here.)
- **A module can be used many times.** `Clock_Module.yaml` may appear in several places, and all uses share the same data. One module is one source of data, however many views show it.
- A module file is recognised by both its `_Module.yaml` name and a `type: Module` key (written `module` in the first note; file types are capitalised). `type:` is authoritative; the suffix is the convention. A mismatch between them is a load error. Every module file also carries `shell:`.
- **One module instance per module file, shared by all uses.** When uses must differ, the module keeps track of it. Example: `Label_Module.yaml` has text to display; its Python script decides which use shows which text, from a JSON file, a database, another YAML file, or anything else. The shell provides the entry and the rendering, not the data.
- `<Name>_Module.py` lives next to its `<Name>_Module.yaml`. Modules go in a `Modules/<module_name>/` folder with all their supporting `.py`, configuration and other files.
- **The binding is the name.** The module's Python calls its module YAML by file name, unique name or UID. That lets the Python read the rest of the file's keys and values, tokens and so on.

### Imports (2026-10-25)

- `import:` takes one file or a list of files.

### Surface Types (2026-10-25)

The surface types are **Bar, Frame, Panel and Popup**. Their behaviour, properties and how each maps to tre are in [[Surface Types]]. `kind:` on a surface takes one of these (written `bar`, `frame`, `panel`, `popup` in the examples). Surfaces are siblings, not nested: a Panel or Popup names what it is attached or anchored to by reference, and is its own entry in the file. The tre parent that a popup needs at the protocol level is handled by the shell.

### Monitors, Names and Errors (2026-10-25)

- `monitor` accepts anything the shell gives it. A root with no `monitor` is ignored. A file imported by a root uses that root's monitor. How `monitor` is written for a name, a description or a default is set in `41 TDL Reference/`.
- `name` is unique per monitor. It need not be unique shell-wide. Its scope is the YAML file it is in and the Python scripts attached to that file. It references something inside its own file or from its script.
- **A UID is shell-wide** and reachable from the highest level to the lowest. Each YAML file gets one automatically.
- Load errors carry `file:line:column`: an import cycle (it prints the chain of files, `A_Shell.yaml` to `B_Shell.yaml` to `A_Shell.yaml`), a missing file, and a name defined twice (it names both places). An import path is relative to the importing file. Logging candidate: Loguru ([[Logging with Loguru]]); not decided.
- `type:` names a file's type; `kind:` names a surface's kind. `type:` is for file types such as `Module` and `Theme` (and `Shell`, `Style`, `Stylesheet`). `kind:` is for the kind of surface (`bar`, `frame`, `panel`, `popup`). Decided 2026-10-25, so the two never share a meaning.

### View Format: a Full Expression Language, and Python as an Equal Front-end (2026-10-25)

Decided by the maintainer in chat (option C of the earlier open item).

- **Python and YAML give the same result.** A shell can be written in Python as if the YAML were Python, or in YAML; someone may choose either. Both build the same thing.
- **YAML has a full expression language**, such as `{if condition, do something, do something else}`. Conditions and repeaters are part of it. The syntax is set in `41 TDL Reference/`.
- **Python is for what YAML should not do:** the major logic, heavy calculation, terminal access and system access. That is the module's job.
- Consequences: (1) there is one model, the tree of surfaces and values, that both a Python builder and the YAML parser produce; (2) the expression language must be limited to evaluating values and structure, with no file, process or system access, because it runs from a configuration file; (3) a test must show that a shell written in Python and the same shell written in YAML produce the same tree. #needs-verification: size of the expression language against the "small layer" intent of Option A. See Risks below.

### Monitors (2026-10-25)

Decided by the maintainer in chat. A root's `monitor` is matched by **connector name**, then falls back to the display **description**. A root with `monitor: default` applies to every monitor no other root names. A root with no `monitor` is ignored.

### Module Python (2026-10-25)

Decided by the maintainer in chat (option A). The shell imports `<Name>_Module.py`, finds the class that extends a shell `Module` base, creates it once and calls `start`, `stop` and an optional `reload`. It receives a context object with the module's YAML values, its name and UID, a logger and the entry point that sends data. The thread rule in [[AGENTS#3. Layering principle]] holds: the shell calls module code on the loop thread, blocking work runs on the module's own thread, and results reach the loop through the send entry point (`call_soon`). The contract is written in [[42 Python API]].

### Events and Module Reload (2026-10-26)

Decided by the maintainer in chat.

- **Events belong to the shell, not to TEL.** TEL is an expression language only ([[ADR-0008 Tesserae Expression Language]]); statements, handlers and events are the shell's. The shell may put an `event` name in the scope it gives TEL. A shell file maps an event (a click, a key, a change) to a module method or a shell action; arguments may be TEL expressions evaluated when the event fires. The vocabulary (`handlers:` or `on_click:` keys, the actions the shell provides) is set in `41 TDL Reference/`.
- **A module's Python can be reloaded at runtime.** When a module's files change, the shell reloads it without restarting the process. Proposed mechanics (not decided): import the new code first and check that it has the module class; only then call `stop` on the old instance, join its threads with a timeout, purge the module's own modules from `sys.modules`, create the new instance and call `start`. If the new code fails to import, the old instance keeps running and the error is logged with `file:line:column`. The `reload` hook is for a changed YAML configuration only, without a restart. #needs-verification: the interaction of `importlib` with a module's own threads, supporting files in `Modules/<module_name>/`, and state that survives (the value store keeps the last values until the new instance sends).

### Config Directory and Registry (2026-10-25)

Decided by the maintainer in chat.

- Shell configuration lives in `$HOME/.config/tesserae-shell/` (the default; see Open items for the `XDG_CONFIG_HOME` rule, decided 2026-10-27). The registry is `registry.json` there. Subdirectories: `Styles`, `Themes`, `Stylesheets` and `Modules`, and from 2026-10-27 `Shells`.
- **Search paths.** Superseded 2026-10-27 by the next section: `settings.yaml` now holds the directories. The original text: a list of directories (`look-at`) for modules, styles, themes and stylesheets, defaulting to the subdirectories above.
- `name` is required on an entry and is part of its identity.
- **The registry resolves references across files** (decided 2026-10-25). A `name` is unique per monitor and scoped to its own file, so a reference from another file, such as a Panel attached to a Bar, is looked up in the registry, which tracks names. If the referenced name no longer exists, the registry knows and the shell reports a warning or an error. Decided 2026-10-25 (the maintainer accepted the recommendation): **an error at load** when a reference never resolves, and **a warning while the shell runs** when a target disappears (for example after a hot reload), with the Panel kept hidden until the target returns. Both name the file and the missing name (`file:line:column`).
- **Identity.** The registry compares the entry's values other than its UUID, with `name` and `location`. The comparison shows whether the module is still there; the UUID written into the file is the confirmation.
- **The registry writes the UID into the file.** When an entry is first registered, the shell injects `UID: <UUIDv7 value>` into the entry-point YAML, directly below `shell: <version>`.
- Python 3.14 is the minimum, so `uuid.uuid7()` is available (accepted by the maintainer, 2026-10-25).

### Modules, Styles, Themes and Stylesheets Live in the Config Directory (2026-10-27)

Decided by the maintainer in chat: the shell requires the config directory by default, as many applications with plugins or add-ons do. Amended the same day: shell files get a folder, and `settings.yaml` can point elsewhere.

- Shell files, Modules, Styles, Themes and Stylesheets live under `$HOME/.config/tesserae-shell/`, in `Shells/`, `Modules/`, `Styles/`, `Themes/` and `Stylesheets/`. A module is a folder `Modules/<module_name>/` ([[AGENTS#9. Naming in the designed system]]).
- The settings file, `settings.yaml`, at the root of the config directory holds settings that are not project based, and can point to absolute directories for any of these types when the user wants a different layout. It is read before the registry and can move the registry file; logs default to `logs/` ([[Settings File#Start order]]). It replaces the `look-at` list of the 2026-10-25 text above, which is superseded. See [[Settings File]].
- Shipped modules stay in the package and are registry-only; a user module of the same name overrides one.
- Generated files live in the config directory too: `schemas/` ([[ADR-0011 JSON Schema for Shell Files]]).
- Consequence: a file under the config directory takes an editor modeline that is a path relative to it, so it survives copying the directory to another machine. A file in a directory named by `settings.yaml` takes an absolute path.

### UIDs and the Registry (2026-10-25)

Decided by the maintainer in chat.

- A UID is made with the built-in `uuid.uuid7()`, a time-ordered, random-backed UUIDv7. It is shell-wide and survives reloads.
- **A registry keeps them.** A file (JSON), not a database ("a DB might be a little much"). Each entry maps a UID to what is known about it for a quick lookup on reload: its type or kind, its state, and the file it comes from (the module file, a config file).
- **Rebuilding from UIDs (decided 2026-10-27).** If the registry is new, empty or moved, and the files already carry UIDs, the shell logs a warning and rebuilds each entry's record from the UID in its file instead of issuing new UIDs ([[Settings File]]). The rules for what the rebuilt record holds are open.
- **A mismatch means the entry is new.** If the registry entry and the current file or entry do not agree, the shell treats the old one as removed and registers a new one.
- Python 3.14 or later is the shell's minimum, accepted by the maintainer. `uuid.uuid7()` ran on 3.14.8 here; tre's wheels cover CPython 3.12 and later ([tre README](https://github.com/mindderivative/tre)). #needs-verification: that 3.14 is the first release with `uuid.uuid7()`.
- Where the registry lives and how identity works: see Config directory and registry.

### Module Data Reaches the View through Shell Entry Points (2026-10-25)

Decided by the maintainer in chat.

- **The shell provides entry points; a module sends data to them.** A `Clock_Module` sends the time to a shell-provided entry point, and the shell passes it to the renderer, which updates the clock. The module keeps its own data; the shell provides the entry and the rendering, not the data.
- **Values match what tre already accepts.** Where a conversion is needed, such as a HEX colour to RGBA, the shell does it. The shell exists so a module developer can use tre without Rust, so it covers the conversions.
- **A conversion the shell does not provide is the module's job.** The module converts to a type the shell accepts.

### Theme, Style and Stylesheet (2026-10-25)

A style file holds the values for one surface or module, the same as its inline `style:` key. A stylesheet holds shared rules that apply across the shell by type or class. A theme holds design tokens (colour, type, shape, motion). A module's style is a style file (`type: Style`, named by the module's `style:` key) or an inline `style:`.

## Consequences

Option A is accepted, so:

- `41 TDL Reference/` defines the shell's view format, theme file and shell file types from scratch, and `42 Python API/` defines the reactive core and the module contract.
- `50 Design System/` owns the tokens and widgets. It may reuse Material Design 3 ideas; that is a design choice, not a dependency.
- `20 Architecture` gains a UI layer between tre and the shell runtime.
- The widget list is fixed by [[V1 Scope]] surfaces and modules. Anything beyond it needs a reason.
- Size and cost are estimated before the first spec is `stable`. #needs-verification
- tre is the shared base. An engine need from the shell is a request to tre ([[AGENTS#6. Engine requests (tre / Tesserae)]]), and a request raised by Tesserae may already cover it, or the reverse. Before writing a request, check tre's open issues and ask the `tre` session through the mailbox ([[AGENTS#14. Peer-session mailbox]]) so one change serves both projects. The maintainer still files upstream.
- The shell does not import Tesserae code. Ideas may be taken from Tesserae's design; the code is written again for the shell.

## Open Items

Settled on 2026-10-25 and recorded above: file naming; the `shell:` key; `import:` and nesting; unique-name keys; module rules and Python contract; plain `*_Theme.yaml`, `*_Style.yaml`, `*_Stylesheet.yaml`; `type:` for files and `kind:` for surfaces (values as written: file types capitalised, surface kinds lower case); the expression language; `monitor`; `name` (required) and scope; load errors; UIDs; the config directory, search paths and registry identity; the module data hand-off; the style, stylesheet and theme split; Python 3.14 minimum.

- [x] **Widget list for v1.** Decided 2026-10-25: take the list from the surfaces and modules in [[V1 Scope]], and add one only when a module needs it. The list is [[V1 Widgets]].
- [x] **Build or adopt the expression engine.** Build: the Tesserae Expression Language, a separate library ([[ADR-0008 Tesserae Expression Language]], decided 2026-10-25). Survey kept as input: [[Expression Languages for YAML]].
- [x] **How a module's values reach its widgets:** `params.<name>` plus sent values (maintainer, 2026-10-26).
- [x] Widget keys in `children:`: `Text:` and `widget: Text` are the same; the unique-name form where a type repeats.
- [x] **The module's style file type:** `type: Style`.
- [x] **Container widgets:** `Box` and `FlexBox`.
- [x] **Four-sided shorthand: option A** (maintainer, 2026-10-26): forms YAML already understands. One number for all sides (`border_thickness: 2`), a list of four (`[2, 2, 2, 2]`), or named sides (`{left: 2, top: 2, right: 2, bottom: 2}`). The maintainer's brace forms were written from experience of other UI tools; they do not survive a standard YAML load (PyYAML read `{2, 2, 2, 2}` as `{2: None}` on 2026-10-26). The order of a list of four is clockwise from the top (top, right, bottom, left), confirmed by the maintainer on 2026-10-26, as tre's `margin` is; named sides are the unambiguous form.
- [x] **Is "overlay" a kind?** No (maintainer, 2026-10-26): the Overlay is the shell-wide layer that puts something on top of everything else, and a Panel with `layer: overlay` is an overlay popup panel. The kinds stay bar, frame, panel and popup. See [[Surface Types#Overlay]].
- [x] What `type:` means in "layer surfaces (`type:`)". The file identifiers: `_Shell.yaml`, `_Module.yaml` and so on, with `type: Shell`, `type: Module` (maintainer, 2026-10-26). Nothing to do with rendering.
- [ ] **Expression language design.** Its grammar, sandbox and errors are designed in the TEL project. The shell's requirements on it are in [[Expression Language Requirements]]. `41 TDL Reference/` records which TEL features a shell file may use and what names an expression can reference (module values, tokens, other entries).
- [ ] **Python builder API.** The Python front-end that produces the same tree as the YAML, and the parity test. Written in `42 Python API/`.
- [x] **Writing the UID into a user's file.** Decided 2026-10-25: once the file is found, the shell opens it and writes `UID:` below `shell:`. The points below are implementation defaults for that write, not open questions; the maintainer called the question obvious. Defaults — The shell edits a file the user owns. Needs: a YAML writer that keeps comments and layout; no reload loop when the watcher sees the shell's own write; behaviour for a read-only file or a file shared by two shells; and what happens when the user copies a file, so two files carry one UID. Recommendation: the writer keeps comments, writes are ignored by the watcher for that file, a read-only file is registered without injection and warned, and a duplicate UID is a load error naming both files.
- [ ] `kind:` inside a class. The Label style example writes `kind: Text` to say which widget a class applies to; `kind:` is the surface kind everywhere else. Recommendation: `widget: Text` inside a class ([[Style, Theme and Stylesheet Files#Classes]]).
- [x] **Widget, module and building blocks** (2026-10-26). Decided: blocks called with `block:`, modules called by name, `widget:` and `module:` dropped. See Blocks, modules and styling above and [[Building Blocks]].
- [x] **The exact form of a module call:** the module's name as the key, params beneath it, `import:` embeds a file (maintainer, 2026-10-26; see Module call, shipped modules and Path).
- [x] **Two uses of one module in one container** (maintainer, 2026-10-26): `children:` may be a list, each item one entry, so a module can repeat and the order is explicit. The maintainer's sketch put `import:` as a mapping key beside the list items; a YAML parser rejects that (checked with PyYAML: a list and a mapping key cannot share a collection), so `import:` is a list item too:

```yaml
children:
    - Label:
        text: "label 1"
    - Label:
        text: "label 2"
    - import: Custom_Module.yaml
```

  `children:` is a mapping (each name once) or a list (repeats allowed); the two do not mix inside one `children:`. Decided (maintainer, 2026-10-26): in a list each use has an optional `name:`, and without one the shell names it from its position (`Label_1`, `Label_2`), so the path name stays unique.

- [x] **Names that exist as both a block and a module.** Resolved: the module `Text` was a mistake and is now TextBox. Image and Icon (modules) sit on Bitmap and SVG (blocks) under different names.
- [x] **Modules the shell ships:** a stable registry-only UID; a user module of the same name overrides it.
- [x] **Can the listed modules be made from the listed blocks?** The maintainer reports yes, tested on Tesserae (2026-10-26).
- [x] **A free-form shape block:** Path is added.
- [x] **Is TextBox editable?** No (maintainer, 2026-10-26). Label and TextBox are not editable; TextInput and TextEditor are.
- [ ] **Case of block names.** The maintainer wrote `path` where the list has capitalised names. Recommendation: match case-insensitively and write the capitalised form in files.
- [ ] **Two files of the same type that conflict.** Two stylesheets that set the same property: proposal, the later import wins.
- [ ] `kind: Text` in a style class is settled by the new keys: a class names the block with `block: Text` (recommendation, to confirm).
- [x] Unique names across the shell with repeated uses: decided (maintainer, 2026-10-26). Names inside a definition are local; each use gets a path name (for example `dp1_root.top_bar.Label_1.Label_Text`), and the registry holds the path as the shell-wide unique name and a UID for the instance. A UID written into a file belongs to the file (the definition); an instance UID lives in the registry only. References can use the path, or a short name when it is unambiguous. List items are named by an optional `name:`, else from their position.
- [x] Params and "bubble up": decided (maintainer, 2026-10-26), opt-in only. A param declares `inherit: true` to be looked up the tree when it is not passed; the nearest ancestor that has it wins; a required param found nowhere is an error naming the chain searched. Everything else must be passed. See [[Module File#Params down the tree]].
- [x] Popup call shape and caller context: decided (maintainer, 2026-10-26), the shell supplies the calling use to the action automatically. The module writes `self.ctx.popup(popup_name)` and the shell fills in the caller. See [[Module Context#Calling a popup]].
- [x] Popup focus and dismissal: decided (maintainer, 2026-10-26), option 1. One flag; focus is on by default (matching tre's `grab`, which gives the popup the pointer and keyboard and closes it on an outside click or Escape); tooltip-like popups opt out and close when the pointer leaves. This replaces the earlier "opt-in" decision, which could not close a popup with no selections on an outside click, because clicks outside the application are not delivered to a popup without the grab. #needs-verification against tre's `PopupWindow`.
- [x] **Directory spelling.** Decided 2026-10-27: `$XDG_CONFIG_HOME/tesserae-shell/` when it is set, non-empty and absolute, else `$HOME/.config/tesserae-shell/` ([[Settings File#The config directory]]). The key for the search list is superseded by `directories` in `settings.yaml`.
- [ ] **What a registry mismatch changes.** The maintainer decided an entry with no match is treated as removed and a new one is registered; also decide whether a removed entry's saved state is dropped at once or kept for a while.

## Risks

> [!warning] Three to carry to the Risk Register
> - **Expression language scope.** A full expression language is a small programming language. It can grow without limit and it runs from a configuration file. Keep it to values and structure, with a sandbox, and test parity with the Python front-end.
> - **Two front-ends.** YAML and Python must give the same result. Every feature is built and tested twice.
> - **The shell edits user files.** Injecting the UID changes a file the user wrote; a bug there can damage it. Keep a backup before the first write.

## Links

- [[ADR-0006 Shell Independent of Tesserae UI]] · [[V1 Scope]] · [[Goals and Non-Goals]]
