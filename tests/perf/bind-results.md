# Bind time

Reported by `tests/perf/measure_bind.py`; the bound the test suite enforces is in
`tests/test_budget_bind.py` (three times the 15 ms target, so a loaded machine does not flake).

| | |
|---|---|
| Date | 2026-11-19T15:06:46-08:00 |
| Machine | Linux 7.3.5-1-cachyos x86_64 |
| Python | 3.14.10 |
| Load average (1 min) before the run | 1.64 |

Milliseconds per call, on a headless `tess_re` window (build, attach, then dispose). The rows
under the big tree split one bind into the steps of `binder.build.build`: planning (typed tree to
the spec), tre's `Window.build` of that spec, the entries and the attach, the view's index (wires,
controls, Tab order), and the dispose. They are separate runs of the same steps, so they add up to
the bind row only within the noise.

| What | Median | Best | Worst | Runs |
|---|---|---|---|---|
| Typing the example file (schema) | 0.132 | 0.123 | 0.415 | 200 |
| Binding the example (5 nodes) | 0.044 | 0.038 | 2.654 | 200 |
| Binding a typed tree of 3,101 nodes | 15.098 | 14.113 | 22.282 | 60 |
|   step: planning the spec | 5.331 | 4.515 | 12.305 | 60 |
|   step: tre `Window.build` | 4.678 | 4.261 | 9.104 | 60 |
|   step: entries and attach | 3.214 | 1.403 | 9.479 | 60 |
|   step: view index (wires, controls, Tab order) | 1.520 | 1.302 | 3.761 | 60 |
|   step: dispose | 0.961 | 0.798 | 1.924 | 60 |

## History (3,101-node tree, ms)

Taken while other builders shared the machine (load average 1 to 3 on 24 cores); base and new in
alternating processes of 100 binds.

| When | Median | Best | Worst | Note |
|---|---|---|---|---|
| 2026-11-04 (M1) | 12.6 | 12.3 | 13.6 | before wires, controls, states, Tab order and focus keys |
| 2026-11-19, M7c reading B18 | 34.4 | 32.1 | 112 | the shell at the start of the bind cost work |
| 2026-11-19, same code, this run | 34.3 to 35.3 | 30.8 to 31.5 | 117 to 123 | 3 processes of 100 binds |
| 2026-11-19, after the bind cost work | 16.1 to 16.8 | 14.8 to 15.0 | 24 to 27 | 3 processes of 100 binds |

Where the 34 ms went before, by step of `build` (medians of 60 binds; the sum is one bind minus
the dispose), and after:

| Step | Before | After | What changed |
|---|---|---|---|
| plan (typed tree to spec) | 11.6 | 5.2 | no path strings or position index, no copy of the child props, nothing done for a node with no state style, no `Transition` or no key that needs checking; `isinstance` with a tuple, not `A \| B`; one call fewer per key |
| tre `Window.build` | 5.5 | 5.2 | the floor of the engine call |
| entries and attach | 5.9 | 2.4 | the entry takes the spec's props; a leaf shares one empty tuple; no per-node state or motion work |
| wires (`_wire`) | 4.8 | 1.1 | a block that listens for nothing gets no `Wire` |
| controls | 1.5 | 0.3 | one list of entries for all the index passes; the control keys are tested with one set check |
| `_sync` | 4.1 | 0.05 | skips blocks with no wire |
| marquees, Tab order | 0.6 | 0.5 | |
| dispose (tre `destroy`) | 1.1 | 1.0 | the floor |
