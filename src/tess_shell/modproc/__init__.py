"""User modules in child processes (posture C, Module Process Test; Security Model > Posture B and
What It Does and Does Not Give).

A user module's Python (a ``<Name>_Module.py`` that does not ship with the package) runs in a child
process of its own, one per module file. The shell never imports it: it reads the file's syntax
tree (:mod:`static`), builds a stub class for the host (:mod:`stub`), and talks to the child over a
socketpair with JSON lines (:mod:`wire`). A child is fault containment (a hang, a crash or a leak
takes down only that module, which restarts), not a sandbox: it runs as the user.

* shell side: :mod:`supervisor` (spawn, failures, watch, the start gate), :mod:`broker` (what a
  child may ask the shell for), :mod:`stub`, :mod:`probe` (``check --import-modules``);
* child side: :mod:`child` and :mod:`childctx`; they import nothing of the shell's services,
  binder, surfaces or the engine (``tests/test_imports.py`` and ``tests/test_modproc_child.py``
  pin it);
* both: :mod:`wire`, :mod:`static`.
"""
