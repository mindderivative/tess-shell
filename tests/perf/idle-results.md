# Idle measurement of `tesserae-shell run`

Reported, not enforced. Produced by `tests/perf/measure_idle.py`.

| | |
|---|---|
| Date | 2026-11-03T20:08:02-08:00 |
| Machine | Linux 7.3.1-1-cachyos x86_64 |
| Python | 3.14.8 (free-threaded) |
| Compositor | private headless sway, pixman renderer, no windows |
| Window | 60.0 s after 3 s of settling |
| Threads | 11 |
| CPU time | 0.00 s |
| CPU | 0.000 % of one core (budget at most 0.5 %) |
| Context switches | 181 voluntary plus involuntary, all threads |
| Wake-ups | 3.02 per second (budget at most 5) |

Result against the budgets: **within** (reported, not enforced).

Wake-ups are counted as context switches, which over-counts (an involuntary switch is not a
wake-up) and includes the Python signal-watcher and logging threads.
