# The Python builder

**There is no Python builder in the shell today.** You cannot write a shell file in Python. A shell is written in TDL, and Python appears only as the code of a [module](module-api.md).

## What the design says

The design record has a requirements note for it, [Python Builder](../design/42%20Python%20API/Python%20Builder.md), with status *draft*. It says that a shell could be written in Python with the same result as in TDL: the TDL parser and the Python builder would produce the same tree, with a constructor for each root block (`Shell`, `Module`, `Style`, `Stylesheet`, `Theme`, `Settings`), for each surface and block, for `If` and `For`, and for the metadata block, and a test would compare the two trees. The note is a stub of requirements and open questions (what the entry point is, how a Python shell is found and keeps its UID, how errors point at Python lines, whether a Python shell hot-reloads). It fixes no signature. Nothing in it is built.

## What exists instead

* `tess_shell` exports the module API only: `Module`, `action`, `Event`, the service exceptions and `ServiceState` ([Module API](module-api.md#what-a-module-imports)). It has no function or class that builds a Bar, a Panel or a block.
* The shell reads a file into a typed tree of its own (`tess_shell.binder.model`) and draws that. That tree is an internal form, not an interface: it is not exported, not documented, and it changes between releases. Do not build on it.
* A module's **values** are what Python gives a layout: it sends strings, numbers, booleans, lists and dicts with `ctx.send`, and the layout shows them. The [values](module-api.md#values) page section says what a key accepts. Conditions (`If`) and repeats (`For`) are in the layout, in TDL, and read the values the module sends.
* To generate a shell file from Python today, write the text of a `.tdl` file: the shell reads it and hot-reloads when it changes.
