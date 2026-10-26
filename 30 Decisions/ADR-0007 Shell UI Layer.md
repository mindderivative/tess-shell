---
title: ADR-0007 Shell UI Layer
aliases: [ADR-0007, Shell View Language]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [adr, architecture, needs-verification]
related: ["[[ADR-0006 Shell Independent of Tesserae UI]]", "[[V1 Scope]]", "[[Goals and Non-Goals]]"]
depends_on: ["[[ADR-0006 Shell Independent of Tesserae UI]]"]
---

# ADR-0007: Shell UI layer

> [!summary]
> The shell builds on tre alone, so it must supply what tre leaves out: a way to describe views, reactive values, a theme and a small widget set. This ADR proposes a small layer owned by the shell, sized to the surfaces in [[V1 Scope]].

> [!success] Accepted 2026-10-25
> The maintainer chose Option A.

## Context

tre provides mechanism only: nodes, layout, paint, animation, input, text, accessibility, layers and shaders. It has no widgets, no theme and no file I/O ([[AGENTS#1. What Tesserae Shell is]]). The shell therefore owns:

| Need | Why the shell needs it |
|---|---|
| A view description | The vision promises YAML views edited by a shell author ([[Goals and Non-Goals]] G1, [[Personas and Use Cases]] P1, P2). |
| Reactive values | Modules push changes (clock, battery, volume) into views from other threads, through `LoopHandle.call_soon` ([[AGENTS#3. Layering principle]]). |
| Theme and design tokens | One look across bar, popups and OSDs, light and dark, high contrast, reduced motion ([[Goals and Non-Goals]] G7). |
| A widget set | Text, icon, button, row, column, slider, list, image, menu item, tray icon. |
| Live reload | Saving a view or theme updates open surfaces ([[Goals and Non-Goals]] G2). |
| Errors with position | `file:line:column` for every config mistake ([[AGENTS#3. Layering principle]]). |

What Tesserae has for reference (not a dependency): a YAML view language with Python ViewModels, `Signal`/`Computed`/`Effect`, Material Design 3 components, themes, stylesheets and hot reload ([Tesserae overview](https://mindderivative.github.io/tesserae/)). Its source is the maintainer's own, so its design can be read freely.

## Options

### Option A — A small shell-owned layer on tre (recommended)

The shell defines a YAML view format limited to what surfaces need, a small reactive core, a token-based theme and about a dozen widgets, all built on tre nodes. It reads Tesserae's design for guidance and shares no code.

- **For:** one dependency (tre); a view format shaped for surfaces, monitors and modules; no coupling to Tesserae's release or scope; keeps [[ADR-0006 Shell Independent of Tesserae UI]] literal.
- **Against:** new work: parser, binding, reactive core, theme, widgets, hot reload, error reporting. Two similar-looking YAML formats exist across the maintainer's projects.

### Option B — Copy parts of Tesserae into the shell

Take the reactive core, theme code and widgets as a one-time copy and let them diverge.

- **For:** faster start.
- **Against:** a fork the maintainer must keep in step by hand; defects fixed in one place stay in the other; unclear licensing and ownership of the copy over time.

### Option C — Extract a shared core package from Tesserae

Split Tesserae into a core (reactivity, theme, view language) and an app layer, and let the shell depend on the core only.

- **For:** one implementation.
- **Against:** needs Tesserae to be restructured, which is the load the maintainer wants to avoid, and still couples the shell to Tesserae's releases.

## Decision

Accepted 2026-10-25 by the maintainer in chat: **Option A**, a small shell-owned layer on tre. It keeps the shell completely separate and dependent only on tre. The extra work is accepted. Tesserae and the shell may each ask tre for additions; a request from either can serve both, and tre is where they meet.

### File naming (2026-10-25)

Decided by the maintainer in chat. The shell's files are named so nobody mistakes them for Tesserae files: a Tesserae `<Name>_View.yaml` dropped into a shell must not appear to work.

- The shell does not use Tesserae's `_View.yaml`, `_ViewModel.py` or `_Component.yaml` names. For themes, styles and stylesheets it uses the plain suffixes `*_Theme.yaml`, `*_Style.yaml` and `*_Stylesheet.yaml` (decided 2026-10-25, below). The name alone does not say whose file it is; the required `shell:` key does.
- A shell is written either as **one `*.yaml` file** for the whole shell, or as a **`Main_Shell.yaml`** that imports several **`<Name>_Shell.yaml`** files and builds the shell from them. Both forms are valid.
- A Tesserae file placed in a shell is refused with an error that names the file and says it is not a shell file (see Open items for how a shell file is recognised).
- Python module files are `<Name>_Module.py` (see Modules below).
- **Theme, style and stylesheet files are `<Name>_Theme.yaml`, `<Name>_Style.yaml` and `<Name>_Stylesheet.yaml`** (decided 2026-10-25, replacing `_ShellTheme`, `_ShellStyle` and `_ShellStylesheet`). Tesserae uses the same suffixes, so a file is a shell file only if it carries the required `shell:` key (and a Tesserae file does not). The maintainer's reasoning: file names such as `_Style.yaml` are in wide use, so a shared suffix is not the problem; the version key is the discriminator. Tesserae side: the maintainer has told the Tesserae project to add a matching version key (`tesserae: <version>`) to all its `.yaml` files, so each side can refuse the other's files; Tesserae is working on it (maintainer report, 2026-10-25). Nothing is asked of Tesserae from this vault. #needs-verification: the key name and format, and the release that carries it, until Tesserae publishes them.

### Recognising a shell file and importing (2026-10-25)

Decided by the maintainer in chat.

- **Every shell file has a required top-level `shell:` key with a format version.** A file without it is not a shell file and is refused with an error naming the file. This also covers a one-file shell with any name.
- **A shell file imports another with `import:` under `children:`**, naming a `<Name>_Shell.yaml` file. `children:` is a mapping, not a list. A single-file shell writes the same content inline as keys and values indented under `children:`. The two forms mean the same thing.
- **Imports nest.** An imported file can import further files. Reason: a small change then stays inside one small file and does not break the rest.

The maintainer's example, as given (2026-10-25). It is a basic example, **not exact implementation guidance**; the grammar is set in `41 YAML Reference/`:

```yaml
shell: v1234
type: Shell

root:
    name: shell_root # Unique but not required, each yaml file gets an assigned UID automatically
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

| Element | What it shows | Status |
|---|---|---|
| `shell: v1234` | The required top-level key carries a version value. | Key decided. The version format (`v1234`) is the example's; not decided. |
| `root:` | A shell file has a root that owns the tree. | Implied. |
| `root.name` | A name, unique but not required. Every YAML file also gets a UID automatically. | Decided 2026-10-25: see Monitors, names and errors. |
| `monitor: DP-1` | A root is bound to one monitor. | Decided 2026-10-25: `monitor` accepts anything the shell gives it, and a root with no `monitor` is ignored (see Monitors, names and errors). |
| `children:` with `import:` | `import:` pulls in a `<Name>_Shell.yaml`. | Decided. |
| `<unique_name>:` entries | Children and modules are keyed by a unique name instead of a repeated `child:` or `module:` key. | **Decided 2026-10-25.** A child's name is unique per monitor. |
| `kind: bar` / `panel` | A surface kind. The example first said `dock` and `corner_panel`; a dock is a bar, and a corner panel is a panel. | Decided 2026-10-25: the types are Bar, Frame, Panel, Popup ([[Surface Types]]). |
| `style: Dock_Style.yaml` | A style file per surface, `<Name>_Style.yaml`, with `shell:` and `type:`. | Decided 2026-10-25 (see File naming). |
| `modules:` and `<name>: <Name>_Module.yaml` | Modules are imported by file. | Decided in outline: see Modules below. |

### Modules (2026-10-25)

Decided by the maintainer in chat:

- **A module is a `<Name>_Module.yaml` file plus a matching `<Name>_Module.py`.** The shell framework expects the Python file and requires it. A module with no matching `.py` is a load error that names both files.
- **A module may have a style.** Either an optional `<Name>_Style.yaml` file whose `type:` is `Module`, or a `style:` key with the values written inline in the module's entry.
- **A module can be used many times.** `Clock_Module.yaml` may appear in several places, and all uses share the same data. One module is one source of data, however many views show it.
- **A module file is recognised by both its `_Module.yaml` name and a `type: module` key.** `type:` is authoritative; the suffix is the convention. A mismatch between them is a load error. Every module file also carries `shell:`.
- **One module instance per module file, shared by all uses.** When uses must differ, the module keeps track of it. Example: `Label_Module.yaml` has text to display; its Python script decides which use shows which text, from a JSON file, a database, another YAML file, or anything else. The shell provides the entry and the rendering, not the data.
- **`<Name>_Module.py` lives next to its `<Name>_Module.yaml`.** Modules go in a `Modules/<module_name>/` folder with all their supporting `.py`, configuration and other files.
- **The binding is the name.** The module's Python calls its module YAML by file name, unique name or UID. That lets the Python read the rest of the file's keys and values, tokens and so on.

### Imports (2026-10-25)

- **`import:` takes one file or a list of files.**

### Surface types (2026-10-25)

The surface types are **Bar, Frame, Panel and Popup**. Their behaviour, properties and how each maps to tre are in [[Surface Types]]. `kind:` on a surface takes one of these (written `bar`, `frame`, `panel`, `popup` in the examples). Surfaces are siblings, not nested: a Panel or Popup names what it is attached or anchored to by reference, and is its own entry in the file. The tre parent that a popup needs at the protocol level is handled by the shell.

### Monitors, names and errors (2026-10-25)

- **`monitor` accepts anything the shell gives it.** A root with no `monitor` is ignored. A file imported by a root uses that root's monitor. How `monitor` is written for a name, a description or a default is set in `41 YAML Reference/`.
- **`name` is unique per monitor.** It need not be unique shell-wide. Its scope is the YAML file it is in and the Python scripts attached to that file. It references something inside its own file or from its script.
- **A UID is shell-wide** and reachable from the highest level to the lowest. Each YAML file gets one automatically.
- **Load errors carry `file:line:column`:** an import cycle (it prints the chain of files, `A_Shell.yaml` to `B_Shell.yaml` to `A_Shell.yaml`), a missing file, and a name defined twice (it names both places). An import path is relative to the importing file.
- **`type:` names a file's type; `kind:` names a surface's kind.** `type:` is for file types such as `Module` and `Theme` (and `Shell`, `Style`, `Stylesheet`). `kind:` is for the kind of surface (`bar`, `frame`, `panel`, `popup`). Decided 2026-10-25, so the two never share a meaning.

### UIDs and the registry (2026-10-25)

Decided by the maintainer in chat.

- **A UID is made with the built-in `uuid.uuid7()`**, a time-ordered, random-backed UUIDv7. It is shell-wide and survives reloads.
- **A registry keeps them.** A file (JSON), not a database ("a DB might be a little much"). Each entry maps a UID to what is known about it for a quick lookup on reload: its type or kind, its state, and the file it comes from (the module file, a config file).
- **A mismatch means the entry is new.** If the registry entry and the current file or entry do not agree, the shell treats the old one as removed and registers a new one.
- Consequence to accept: `uuid.uuid7()` is in Python 3.14 and later (it ran on 3.14.8 here). tre's wheels cover CPython 3.12 and later ([tre README](https://github.com/mindderivative/tre)), so the shell's minimum is Python 3.14 unless it carries its own fallback. #needs-verification: the minimum Python version for the shell, and which release added `uuid.uuid7()`.
- Not yet decided: where the registry file lives (for example the user's state directory), and exactly which fields make two entries "the same" across a reload (file path, `name`, kind).

### Module data reaches the view through shell entry points (2026-10-25)

Decided by the maintainer in chat.

- **The shell provides entry points; a module sends data to them.** A `Clock_Module` sends the time to a shell-provided entry point, and the shell passes it to the renderer, which updates the clock. The module keeps its own data; the shell provides the entry and the rendering, not the data.
- **Values match what tre already accepts.** Where a conversion is needed, such as a HEX colour to RGBA, the shell does it. The shell exists so a module developer can use tre without Rust, so it covers the conversions.
- **A conversion the shell does not provide is the module's job.** The module converts to a type the shell accepts.

### Theme, style and stylesheet (2026-10-25)

A style file holds the values for one surface or module, the same as its inline `style:` key. A stylesheet holds shared rules that apply across the shell by type or class. A theme holds design tokens (colour, type, shape, motion). A module's style is a style file with `type: Module` or an inline `style:`.

## Consequences

Option A is accepted, so:
- `41 YAML Reference/` defines the shell's view format, theme file and shell file types from scratch, and `42 Python API/` defines the reactive core and the module contract.
- `50 Design System/` owns the tokens and widgets. It may reuse Material Design 3 ideas; that is a design choice, not a dependency.
- `20 Architecture` gains a UI layer between tre and the shell runtime.
- The widget list is fixed by [[V1 Scope]] surfaces and modules. Anything beyond it needs a reason.
- Size and cost are estimated before the first spec is `stable`. #needs-verification
- tre is the shared base. An engine need from the shell is a request to tre ([[AGENTS#6. Engine requests (tre / Tesserae)]]), and a request raised by Tesserae may already cover it, or the reverse. Before writing a request, check tre's open issues and ask the `tre` session through the mailbox ([[AGENTS#14. Peer-session mailbox]]) so one change serves both projects. The maintainer still files upstream.
- The shell does not import Tesserae code. Ideas may be taken from Tesserae's design; the code is written again for the shell.

## Open items

Settled on 2026-10-25 and recorded above: file naming; the `shell:` key; `import:` and nesting; unique-name keys; module rules; plain `*_Theme.yaml`, `*_Style.yaml`, `*_Stylesheet.yaml`; `type:` for files and `kind:` for surfaces; surface kinds; `monitor` and `name` scope; load errors; UIDs and the registry; the module data hand-off; the style, stylesheet and theme split.

Open, with what each is asking:

- [ ] **Widget list for v1 and the limits of the view format.** Two questions. (1) *Widgets:* which building blocks can a view use? For example text, icon, image, button, row and column, slider, progress bar, list, menu item, tray icon. I would take the list from the surfaces and modules in [[V1 Scope]], and add one only when a module needs it. (2) *View format limits:* how much logic can a YAML file hold? *Conditions* are show-or-hide and choose-a-value rules (`visible: when the battery is low`). *Repeaters* make one entry per item of a list (one button per workspace, one icon per tray item). Options: **A.** none (static layout only; modules drive everything), **B.** conditions and repeaters in a small fixed set of forms (recommended: workspaces and tray need repeaters, battery and network need conditions), **C.** a full expression language. Recommendation B. This needs your steer on how much you want in YAML against in the modules' Python.
- [ ] **Case of values.** `type:` values are `Module`, `Theme` and so on (capitalised); `kind:` values are `bar`, `panel` (lower case). Recommendation: match case-insensitively, and write the canonical form in `41 YAML Reference/`.
- [ ] **What `monitor` accepts.** Three small questions, because a root with no `monitor` is ignored. (1) *Name:* connector name only (`DP-1`), as tre reports it. (2) *Description:* also match by the display's description (make, model, serial), so a profile follows a particular display when the port changes. (3) *Default:* what a monitor gets that no root names, such as one plugged in later. Options: **A.** nothing (unnamed monitors show no shell), **B.** a root with `monitor: default` that applies to every monitor no other root names (recommended), **C.** a wildcard that applies to all monitors. Recommendation: name plus description, and B.
- [ ] **How the shell loads a module's Python, and the contract.** Options: **A.** *A class* (recommended): the shell imports `<Name>_Module.py`, finds one class that extends a shell `Module` base, creates it once, and calls `start`, `stop` and an optional `reload`. It receives a context object holding its YAML values, its name and UID, a logger, and the entry point that sends data. **B.** *Plain functions*: `start(ctx)` and `stop()` in the file; less structure, harder to keep state. **C.** *A decorator*: functions register themselves with the shell; flexible, more magic. Under every option the thread rule in [[AGENTS#3. Layering principle]] holds: the shell calls module code on the loop thread, blocking work runs on the module's own thread, and the send entry point moves results onto the loop with `call_soon`. The contract is written in [[42 Python API]].
- [ ] **Registry details.** Where the registry file lives, and which fields make two entries "the same" across a reload.
- [ ] **Minimum Python version** (see UIDs and the registry).

## Links

- [[ADR-0006 Shell Independent of Tesserae UI]] · [[V1 Scope]] · [[Goals and Non-Goals]]
