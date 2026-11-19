# Messages

Every finding that `tesserae-shell check` prints, and that the running shell prints or logs for a file, has a name. This page lists the names, grouped by what they are about, with what each means, when it appears and what to do. For the messages that have no name, such as `no Wayland compositor with layer-shell`, and for what to do when nothing appears at all, see [Troubleshooting](../guide/troubleshooting.md).

## How a finding is printed

A finding has a file, a line and a column, a severity, a name, a message and a hint:

```text
Shells/Main_Shell.tdl:13:17: error: unknown key in Bar Hieght
  13 |                  Hieght: 32
     |                  ^
    hint: did you mean Height, Min_Height, Max_Height?
```

In `tesserae-shell check --json` the name is the `rule` field of each entry ([The command line](../guide/command-line.md#check)). The message text varies with the case; the name does not, and is what to search for here.

There are two severities:

* **error**: the file is refused. `check` exits with code 1, and a shell that starts, or reloads, with an error in a file does not use it (a reload keeps what is shown). Fix it.
* **warning**: printed, but the file is used. `check` still exits 0 unless you pass `--strict`, which makes a warning fail the check too.

The exit codes are listed under [Exit codes](../guide/command-line.md#exit-codes). `check` reads only your files and creates nothing; the names in [At run time](#at-run-time) appear only when the shell starts or reloads, because they need the loaded Python or the registry.

At most 50 findings are printed, then `... and N more`.

## The file and its text

Every file is read in stages: the bytes, the TDL text, the metadata block, then the root block. A file that stops at one stage is not read further, so fixing one finding can show the next.

| Name | Severity | What it means and what to do |
|---|---|---|
| `unreadable` | error | The file could not be read (permissions, or it vanished); the message names the system's reason. |
| `tdl-bad-encoding` | error | The bytes are not valid UTF-8. Save the file as UTF-8. |
| `tdl-old-version` | error | The metadata says `TDL: 0.1`, and the shell reads TDL 0.2. Run `tesserae-shell migrate` ([Upgrading](../upgrading.md#migrate)); a slot is written `<\| expression \|>` in 0.2. |
| `version-pin` | error | The file needs a newer `TDL:` (or `TRE:` or `TEL:`) than the installed library. Upgrade the package, or lower the pin. |
| `shell-too-old` | error | The file's `Shell:` pin asks for a newer shell than the one installed. Install the release the hint names, or lower the pin ([Upgrading](../upgrading.md#the-shell-pin)). |
| `shell-root-suffix` | error | The root block does not match the file's ending: a `Theme { }` in a `_Shell.tdl`. Change the root block or rename the file; the root block decides. |
| `shell-root`, `module-root`, `style-root`, `theme-root`, `stylesheet-root` | error | The file is read as that kind (by its name ending) but its root block is another. The hint names the block to write. |
| `name-duplicate` | error | Two of your files of the same kind have the same `Name` (for a module, the same module name). A name is registered once; a file of yours may share a name with a shipped one, which it then replaces. |
| `deprecated-key` | warning | A key or block still works under its old name; the message names the replacement and the release that removes it. `tesserae-shell migrate` rewrites it. Nothing is deprecated in 0.2.0. |
| `removed-key` | error | A key was removed (today, a Bar's `Reveal_Key`). The hint says what to do instead. |

The TDL text itself is checked by the language library, `tesserae-dl`, whose names all start with `tdl-`:

| Name | What it means |
|---|---|
| `tdl-no-metadata` | The file does not start with a metadata block. Start it with `---`. |
| `tdl-metadata-unclosed` | The metadata block is never closed. Close it with `---`. |
| `tdl-no-version` | The metadata has no `TDL:` version. |
| `tdl-no-name` | The metadata has no `Name:`. |
| `tdl-bad-name` | The `Name` is not an identifier: letters, digits and `_`, starting with a letter. |
| `tdl-unsupported-version` | The file needs a newer TDL than the installed `tesserae-dl` reads. Upgrade the package. |
| `tdl-no-root` | The file has no root block, for example `Shell { }`. |
| `tdl-many-roots` | The file has more than one root block. |
| `tdl-unclosed-block` | A `{` is never closed. Add the missing `}`. |
| `tdl-unexpected-close` | A `}` closes nothing. Remove it. |
| `tdl-unclosed-slot` | A `<\|` has no `\|>` on its line. |
| `tdl-empty-slot` | A slot holds no expression. |
| `tdl-unclosed-string` | A string is not closed on its line. |
| `tdl-bad-escape` | A backslash starts no valid escape; use `\\`, `\"`, `\'`, `\n`, `\t` or `\u` and four hex digits. |
| `tdl-duplicate-key` | A key is written twice in one block. |
| `tdl-duplicate-variable` | A `For` loop variable is already in use. |
| `tdl-bare-hash` | A colour needs quotes: `"#ffffff"`. |
| `tdl-unexpected-text` | The text is not valid here. The message and the hint say what was expected (`Write Key: value`, for one). |
| `tdl-reserved-name` | The name is reserved. Choose another. |
| `tdl-too-large` | The file is larger than 1 MiB. Split it. |
| `tdl-too-deep` | Blocks are nested deeper than 64 levels. |

A file with a `TDL:` of 0.1 does not parse as 0.2; the shell reports `tdl-old-version` instead of the parse errors it would otherwise show.

A mistake inside a `<| ... |>` slot (an unknown name, a division by zero, a method that is not allowed) is a TEL error. It has no name here: the shell logs it as a warning `file:line:column: message (hint)` when the slot is first read, and keeps the last good value ([Troubleshooting](../guide/troubleshooting.md#the-messages)).

## Keys, blocks and values

These come from reading a shell, module, style, theme or stylesheet file against what the shell knows. The tables in the [guide](../guide/index.md) list every key; [`tesserae-shell schema --json`](../guide/command-line.md#schema) lists them as data.

| Name | Severity | What it means and what to do |
|---|---|---|
| `unknown-key` | error | A key, block or side that does not exist. The hint offers the nearest names, or lists the keys of that block. Also used for an unknown shortcut name in `settings.tdl`. |
| `not-built` | error, a few warnings | The key or form exists in the design but is not built. Remove it. A few Bar keys and a `::part` selector after a class or name are warnings and are skipped. |
| `bad-value` | error | The value is not of the kind the key takes, or not one of its choices. The message says what was expected and what was found; for a choice it lists them. |
| `bad-key` | error | A key that makes no sense on this block: `Content` takes no keys, an `SVG` has a `Source` or an `Icon` and not both. |
| `missing-key` | error | A required key is absent: a Bar without `Width` or `Height`, a Panel with `Attach_To` and no `Attach`, a shortcut block without `Keys`, a stylesheet `Rule` without `Selector`, a `Shadow` without `Color`. |
| `bad-children` | error | A block that cannot have children has a `Children` block (only `Box`, `FlexBox` and `ScrollBox` take one). |
| `bad-sides` | error | A list of sides has four items (left, top, right, bottom); or write named sides. |
| `bad-token` | error | A `$group.name` token reference is malformed, or names a token of the wrong kind. The hint shows the form, `$color.surface`. A token that does not exist is reported with the nearest names. |
| `bad-name` | error | An action or handler name is not letters, digits and `_`, or a shortcut block is named like one of the shell's own actions. |
| `unknown-module` | error | A `Call` names a module that no file defines (a shipped one or yours). The hint offers the nearest names, or lists the modules there are. |
| `style-duplicate` | error | A key is written both in the block and in its `Style`, or a module has two `Style` entries. Keep one. |
| `shadow-both` | warning | `Elevation` and `Shadows` are both written; `Shadows` wins. |
| `key-not-applied` | warning | A key that does nothing here, such as `On_Submit` on a multi-line text field; it is left out. |
| `event-not-raised` | error | An `On_` key, or a `Tooltip`, on a block that raises no such event. The hint names the events it raises, or the `Box` or `FlexBox` to put it on. |
| `state-by-module` | error | An accessibility state is set by the module that has it, not written in a shell file. |
| `unsupported-entry` | error | An `If` or `For` where `settings.tdl` takes only plain entries. |
| `icon-not-found` | error, or warning | No icon set has that name. An error for an `SVG` `Icon`; a warning for an icon param of a module (the module shows the broken-image icon). The hint offers close names. |
| `image-not-found` | warning | No image file at that path (relative to the file); the `Bitmap` shows the error image. |
| `part-outside-module`, `part-duplicate`, `content-outside-module` | error | `Part` and `Content` belong in a module's layout file, and a part name is declared once. |
| `style-not-found` | error | The module's `Style:` file does not exist, or cannot be read; the findings of that file say why. |

## Surfaces

| Name | Severity | What it means and what to do |
|---|---|---|
| `monitor-duplicate` | error | Two `Monitor` blocks select the same monitor. A monitor is named by one block. |
| `frame-duplicate` | error | A `Monitor` has two Frames. |
| `frame-edge-duplicate` | error | `Edges` names a side twice. |
| `frame-strip-thickness` | error | A strip of a Frame has `Children` but no thickness. Write `Thickness`. |
| `frame-border-twice` | error | The Frame has an `Inner_Border` and a shorthand for it in its `Style`. Write it once. |
| `attach-orphan`, `attach-placed` | error | `Attach`, `Gap` and `Alignment` need `Attach_To`; a Panel with `Attach_To` is placed by its target, so `Anchor` and `Inset` have no meaning. |
| `attach-unknown`, `attach-self`, `attach-cycle`, `attach-duplicate`, `attach-other-monitor` | error | `Attach_To` names no Bar, Panel or module used in a Bar; names the Panel itself; forms a circle; targets a surface that already has a Panel attached; or names a surface of another Monitor. |
| `movable-attached` | error | A Panel placed by `Attach_To` cannot be `Movable`: only a Panel placed by `Anchor` and `Inset` has a position to save. |
| `meld-target`, `meld-margin`, `meld-size`, `meld-size-orphan` | error | `Meld: true` needs an `Attach_To` that names a Frame of this Monitor; a `Margin` on the side facing the Frame stops the meld; a size key that is not one of a melded Panel's. |
| `peek-empty`, `peek-size`, `peek-slide-from`, `peek-window` | error | A `Peek` that cannot work: a strip with no children, a `Size` not smaller than the extent it slides along, a `Slide_From` that is not an edge the Panel touches, or a Panel in a window of its own. |
| `tooltip-unknown`, `tooltip-not-hover` | error | A `Tooltip` names a Popup that this Monitor does not have, or one that does not open on enter (write `Tooltip: true` in it). |
| `close-outside-popup` | error | `Close` closes the Popup that holds the block, and this block is in none. Use `Hide` for a Panel. |
| `shortcut-mode-twice` | warning | `Shortcut_Mode: true` is written on more than one surface; the first keeps it. |

## Imports and the main shell

| Name | Severity | What it means and what to do |
|---|---|---|
| `import-cycle` | error | Shell files import each other in a circle, or modules call or import each other in one. The message prints the chain; remove one link. |
| `import-not-found` | error | The `Import:` names a file that does not exist (the message gives the path that was looked at, relative to the file that writes it), or, in a surface's `Children`, one that is not a `_Module.tdl`. |
| `import-failed` | error | The imported file exists but has errors; they are listed at that file's own lines. |
| `import-twice` | error | A file of surfaces is imported twice. A surface's `Name` is unique across the shell, so import it once. |
| `import-monitor` | error | An imported shell file holds a `Monitor`. It holds surface blocks; the importing `Monitor` chooses the monitor. |
| `import-misplaced` | error | A shell file is imported in a surface's `Children`, or a module in a `Monitor`'s. Import a shell file in a `Monitor`'s `Children`, a module in a surface's. |
| `main-shell-surfaces` | error | `Main_Shell` holds surface blocks and no `Monitor`: it is a file to import, and the shell would show nothing. Wrap it in a `Monitor` that imports it. |
| `main-shell-not-found` | error | `Main_Shell` in `settings.tdl` names a file that is in no `Shells` folder. |

More on files that import files: [Surfaces](../guide/surfaces.md#a-shell-in-several-files).

## Themes, stylesheets and classes

| Name | Severity | What it means and what to do |
|---|---|---|
| `theme-not-found`, `stylesheet-not-found` | error | `Appearance` names a theme or stylesheet no file has as its `Name`. The hint lists the ones there are. |
| `class-not-found`, `class-kind` | error | A `Class:` names a class the style does not define, or one defined for another kind of block. |
| `bad-selector` | error | A rule's `Selector` is not `"Text"`, `".class"` or `"#name"` with an optional `:state` or `::part`, or a `::part` names something that is not a module. |
| `unknown-part` | error | A selector names a part its module does not have. The hint lists the module's parts. |
| `state-never-applies` | warning | A `:hovered` or `:focused` rule reaches a block that gets no such events (a `Text`). Put the rule on the `Box` or `FlexBox` around it. |

## `settings.tdl`

| Name | Severity | What it means and what to do |
|---|---|---|
| `settings-root` | error | The root block is not `Settings`. |
| `unresolved-path` | error | A path uses a variable that is not set. |
| `relative-path` | error | A path is not absolute. Start it with `/` or `~`. |
| `missing-directory` | error | A path in `Directories`, or the folder of `Registry`, is not a folder. Create it or remove the entry. |
| `shortcut-duplicate` | error | An action has two entries in `Shortcuts`. |

A key's own mistakes use the names in [Keys, blocks and values](#keys-blocks-and-values) (`unknown-key`, `bad-value`, `missing-key`, `bad-name`, `unsupported-entry`). Shortcuts have more findings, all warnings:

| Name | What it means and what to do |
|---|---|
| `shortcut-unknown-surface` | A `Toggle_`, `Show_` or `Hide_` shortcut names a surface that is no Panel, Bar or Frame; it is not registered. The hint offers a close name. |
| `shortcut-bar` | The target is a Bar, which is always shown and cannot be hidden. |
| `shortcut-popup` | The target is a Popup, and no key opens a Popup. |
| `shortcut-override` | A surface carries its own `Shortcut` key and `settings.tdl` has an entry for the same action; the entry in `settings.tdl` wins. |
| `shortcut-conflict` | Two actions of the shell share a key; neither gets it. Give one of them another. |

See [Keyboard and shortcuts](../guide/keyboard.md#global-shortcuts).

## Security and your folder

| Name | Severity | What it means and what to do |
|---|---|---|
| `path-outside-config` | error | An `Import:`, `Style:`, `Source:` or a `path` param names a file outside your configuration folder, after `..` and symbolic links are resolved. Put the file inside the folder, or add its folder to `Directories`. |
| `insecure-permissions` | warning | Your configuration folder, a folder that holds modules, a module's folder or its Python file can be written by group or others, or belongs to another user. Write access to a module's Python is code execution as you: `chmod go-w PATH`. `check --strict` fails on it. |

See [Trust and security](../guide/configuration-folder.md#trust-and-security).

## Shipped files and registry

| Name | Severity | What it means and what to do |
|---|---|---|
| `icon-set-invalid` | warning | A `.json` file in an `Icons` folder cannot be read as an icon set; it is skipped. |
| `shipped-panel` | error | The shell's own Panel or Popup text (the Launcher, the Audio menu) did not parse or read. This is a fault in the package: reinstall it, and report it if it stays. |

## At run time

These appear when the shell starts or reloads, not in `check`, because they need the Python of a module or the registry. In the log each is a line with the module or file it is about; the last errors are also in `tesserae-shell status`.

| Name | Severity | What it means and what to do |
|---|---|---|
| `module-no-python` | error | A module has a layout `Name_Module.tdl` but no `Name_Module.py` next to it. |
| `module-import` | error | The module's Python could not be imported (a syntax error, a missing library, no or more than one `Module` class). The message names the exception. The module does not load; the others do. |
| `module-init` | error | The module's class raised when it was created. |
| `module-use` | error | The module refused a use of it: a param whose value it rejected. |
| `module-exception` | error | A module's Python raised while the shell runs. The traceback is in the log and the shell keeps running. If the module is a shipped one, report it. |
| `action-clash` | error | The module has a method marked `@action` with the name of a built-in action (`Show`, `Hide`, `Toggle`, `Close`, `Call`). Rename the method. |
| `unknown-action`, `unknown-argument`, `missing-argument` | error | A handler (`On_Click`, a `Call`) names an action the module does not have, an argument the action does not take, or leaves out one it needs. The hint lists the actions or arguments. |
| `call-module-not-loaded` | error | A `Call` names a module that no Bar, Panel, Popup or Frame uses, so its Python is not loaded; or its Python failed to load (see the errors above). |
| `slow-module` | warning | More than 100 callbacks of the module took over 4 ms on the loop in a minute. Hand slow work to a thread and bring the result back with `ctx.call_soon`. |
| `many-threads` | warning | The module has more than 16 live threads of its own. Join or stop the ones it no longer needs. |
| `uid-write` | warning | The shell could not add the `UID:` line to a file; your file is unchanged and the UID is kept in the registry ([The configuration folder](../guide/configuration-folder.md#identifiers-and-backups)). |
| `registry-unreadable`, `registry-invalid`, `registry-too-new` | error | `registry.json` cannot be read, cannot be used and cannot be moved aside, or was written by a newer shell (the hint: use a newer `tesserae-shell`). A registry that is merely not valid JSON is rebuilt by the shell itself with a warning ([Troubleshooting](../guide/troubleshooting.md#starting)). These three stop the start with exit code 1. |

Messages without a name (a lost Wayland connection, a service leaving the bus, a shortcut the desktop already uses) are in [Troubleshooting](../guide/troubleshooting.md#the-messages).
