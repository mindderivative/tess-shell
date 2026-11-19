# The Schema Export

`tesserae-shell schema --json` is how a configuration tool learns what the shell accepts. This page is its manual and its history.

`schema --json` prints (or, with `--out FILE`, writes) every block, surface, key, kind, choice,
default, event, action, theme token and `settings.tdl` key the loader accepts, with a line of
documentation for each, so a configuration application can build its forms from it. It is read from
the loader's own tables (`tess_shell.schema.export.schema_json()`; `schema_dict()` is the same as
plain data), so it cannot list a key the loader refuses or miss one it accepts, and two runs give the
same bytes. A field the model cannot give is `null`; the shape is `schema_version` 1.9 (the notes below say what each version added).

Since 1.1: a key's `default` is what tre reads on a bare block (the binder builds it headless and

Since 1.8 (additive): the shipped module `Applications` (its four params, `modules` section), the event `On_Key_Down` (a TextField raises it; `events` section) and `panels`, a section beside `popups` that lists the Panels the shell provides (`Launcher`: the module it holds, its layer and keyboard, one line of documentation, and `when` it is added to a shell).

Since 1.9 (additive): the accessibility pass. The block key `Value_Text` (the value in words, `45 percent`; set by a module, so it is in the accessibility group of the keys and a shell file may not write it) and six module params: `Label` of `TextInput` and `TextEditor` (the field's accessible name; without one it is the `Placeholder`), `Value_Text` of `Slider`, and `announce` of `Media`, `Audio` and `Tasks` (polite live announcements, off by default). The Network, Battery and Applications modules announce without a param. Every module that shows a tooltip also gives it as the accessible description. Announcements are live regions: a 1 by 1 pixel `Announcer` block with `Live: POLITE` whose label the module changes.

Since 1.7 (additive): the `KWin` settings section (`Script`, `Hide_On_Fullscreen`) and the shipped modules `Tasks` and `Task_Item` (their params, `modules` section).

Since 1.6 (additive): `system_tokens`, a list beside `tokens` of the tokens the shell supplies to every theme (today `type.system.font_family`: `name`, `ref`, `kind`, `default` (`Roboto`), `doc`, `theme_wins` (a theme that sets it keeps its value), and the kind's own fields); `tokens` still equals the shipped theme's tokens.
`node.get` reads it back; a few shell-owned keys are authored and pinned by tests), `min`/`max` come
from the one table of ranges (`schema/ranges.py`) that the loader also judges a written value or a
slot by (`Opacity` 0 to 1, `Scale` above 0, `Flex_Grow` 0 or more, `Font_Weight` 1 to 1000, lengths,
sides and radii 0 or more, ...), each key lists `preferred_tokens` (the theme tokens a form should
offer first, next to the mechanical `tokens`), and a `modules` section lists every shipped module
with its params (type, default, doc), the events a call may handle, the common keys it may write
and the `@action`s `Call` may run.
