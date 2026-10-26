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

- The shell does not use Tesserae's `_View.yaml` suffix, or any Tesserae file name, for its own views.
- A shell is written either as **one `*.yaml` file** for the whole shell, or as a **`Main_Shell.yaml`** that imports several **`<Name>_Shell.yaml`** files and builds the shell from them. Both forms are valid.
- A Tesserae file placed in a shell is refused with an error that names the file and says it is not a shell file (see Open items for how a shell file is recognised).
- Still open: the names of the Python module files, theme files and stylesheet files. They are set in `41 YAML Reference/` and `42 Python API/`.

### Recognising a shell file and importing (2026-10-25)

Decided by the maintainer in chat.

- **Every shell file has a required top-level `shell:` key with a format version.** A file without it is not a shell file and is refused with an error naming the file. This also covers a one-file shell with any name.
- **A shell file imports another with `import:` under `children:`**, naming a `<Name>_Shell.yaml` file. `children:` is a mapping, not a list. A single-file shell writes the same content inline as keys and values indented under `children:`. The two forms mean the same thing.
- **Imports nest.** An imported file can import further files. Reason: a small change then stays inside one small file and does not break the rest.

The maintainer's example, as given (2026-10-25). It is a basic example, **not exact implementation guidance**; the grammar is set in `41 YAML Reference/`:

```yaml
shell: v1234

root:
    name: shell_root # Unique but not required, each yaml file gets an assigned UID automatically
    monitor: DP-1
    children:
        import: TopBar_Shell.yaml
        child: 
            name: panel_dock # Unique per monitor
            type: dock
            style: Dock_ShellStyle.yaml
            modules: # Modules have to be imported as they may have differing rules
                module: Audio_Module.yaml # with a connected python script
                module: Network_Module.yaml
        child:
            name: panel_start_menu
            type: corner_panel
            style: CornerPanel_ShellStyle.yaml
            modules:
                module: Applications_Module.yaml
```

What the example shows, and what is still only implied:

| Element | What it shows | Status |
|---|---|---|
| `shell: v1234` | The required top-level key carries a version value. | Key decided. The version format (`v1234`) is the example's; not decided. |
| `root:` | A shell file has a root that owns the tree. | Implied. |
| `root.name` | A name, unique but not required. Every YAML file also gets a UID automatically. | Implied. Scope of uniqueness not decided. |
| `monitor: DP-1` | A root is bound to one monitor by connector name. | Fits [[V1 Scope#Multi-monitor]] (match by connector name). Whether `monitor` also takes a description match, a default or a shared reference is not decided. |
| `children:` with `import:` and `child:` | `import:` pulls in a `<Name>_Shell.yaml`; `child:` defines a surface inline. | Decided in outline above. The example repeats `child:` and `module:` keys, which a YAML mapping cannot do; see Open items. |
| `child.name` | Unique per monitor. | Implied. |
| `child.type` | A surface type: `dock`, `corner_panel`. | The type list is not decided. |
| `style: Dock_ShellStyle.yaml` | A style file per surface, with a `_ShellStyle.yaml` suffix. | Implied name. Not decided. |
| `modules:` and `module: Audio_Module.yaml` | Modules are imported by file, each with a connected Python script, because they may have differing rules. | Implied: a module file type `<Name>_Module.yaml`. Not decided. |

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

- [ ] Set the widget list for v1 and the limits of the view format (conditions, repeaters, imports).
- [x] Decide whether view files keep Tesserae-style names. No: one `*.yaml` file, or `Main_Shell.yaml` importing `<Name>_Shell.yaml` files (see File naming above).
- [x] Decide how a shell file is recognised. A required top-level `shell:` key with a version (see above).
- [x] Decide the import syntax and whether imports nest. `import:` under `children:`; imports nest (see above).
- [ ] Decide how several `import:`, `child:` and `module:` entries are written. The example repeats these keys, and a YAML mapping cannot repeat a key (most parsers keep only the last). Recommendation: each takes a list, or `child` is keyed by its own name (`panel_dock:`), since a child's `name` is unique per monitor.
- [ ] Decide the file types the example implies: style files (`<Name>_ShellStyle.yaml`) and module files (`<Name>_Module.yaml`), and how a module file names its Python script. This also answers the theme and stylesheet naming item below for style files.
- [ ] Decide the list of surface `type` values (the example has `dock` and `corner_panel`) and how they map to `LayerWindow` settings ([[TRE-REQ-001 Layer Surface Window]]).
- [ ] Decide what `monitor` accepts and how a file with no `monitor` behaves ([[V1 Scope#Multi-monitor]]: default section, shared definitions).
- [ ] Decide `name` and UID rules: which names must be unique and in what scope, how a UID is made, and whether it is stable across reloads.
- [ ] Decide how an import cycle, a missing file and a name clash are reported. Recommendation: each is a load error with `file:line:column`; a cycle prints the chain of files (`A_Shell.yaml` to `B_Shell.yaml` to `A_Shell.yaml`); a path is relative to the importing file; a name defined twice names both places.
- [ ] Decide the names of Python module files, theme files and stylesheet files so none reads as a Tesserae name (`_ViewModel.py`, `_Theme.yaml`, `_Stylesheet.yaml`).
- [ ] Decide how a module's values reach a view (a ViewModel class, a plain dict, or a signal registry).

## Links

- [[ADR-0006 Shell Independent of Tesserae UI]] · [[V1 Scope]] · [[Goals and Non-Goals]]
