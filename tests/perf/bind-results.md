# Bind time

Reported, not enforced. Produced by `tests/perf/measure_bind.py`.

| | |
|---|---|
| Date | 2026-11-04T00:21:33-08:00 |
| Machine | Linux 7.3.1-1-cachyos x86_64 |
| Python | 3.14.9 |

Milliseconds per call, on a headless `tess_re` window (build, attach, then dispose).

| What | Median | Best | Worst | Runs |
|---|---|---|---|---|
| Typing the example file (schema) | 0.067 | 0.065 | 0.128 | 200 |
| Binding the example (5 nodes) | 0.025 | 0.024 | 1.471 | 200 |
| Binding a typed tree of 3,101 nodes | 12.596 | 12.296 | 13.618 | 20 |

Binder Design quotes tre's own figure for 3,100 nodes: 5.3 ms through `Window.build` (4.9 ms with
per-node calls); that excludes this binder's table lookups and conversions.
