# Idle measurement of `tesserae-shell run`

Reported, not enforced. Produced by `tests/perf/measure_idle.py`.

| | |
|---|---|
| Date | 2026-11-03T20:16:22-08:00 |
| Machine | Linux 7.3.1-1-cachyos x86_64 |
| Python | 3.14.9 (with the GIL) |
| Compositor | private headless sway, pixman renderer, no windows |
| Window | 60.0 s after 3 s of settling |
| Threads | 11 |
| CPU time | 0.01 s |
| CPU | 0.017 % of one core (budget at most 0.5 %) |
| Context switches | 120 voluntary plus involuntary, all threads |
| Wake-ups | 2.00 per second (budget at most 5) |

Result against the budgets: **within** (reported, not enforced).

Wake-ups are counted as context switches, which over-counts (an involuntary switch is not a
wake-up) and includes the Python signal-watcher and logging threads.
