# Idle measurement of `tesserae-shell run` with the example Bar shown

Reported, not enforced. Produced by `tests/perf/measure_idle.py`.

| | |
|---|---|
| Date | 2026-11-04T07:20:10-08:00 |
| Machine | Linux 7.3.1-1-cachyos x86_64 |
| Python | 3.14.9 (with the GIL) |
| Compositor | private headless sway, pixman renderer, the example Bar with a Clock (format %H:%M, ticks once a minute) |
| Window | 60.0 s after 3 s of settling |
| Threads | 74 |
| CPU time | 0.00 s |
| CPU | 0.000 % of one core (budget at most 0.5 %) |
| Context switches | 465 voluntary plus involuntary, all threads |
| Wake-ups | 7.75 per second (budget at most 5) |

Result against the budgets: **OVER** (reported, not enforced).

Wake-ups are counted as context switches, which over-counts (an involuntary switch is not a
wake-up) and includes the Python signal-watcher and logging threads.
