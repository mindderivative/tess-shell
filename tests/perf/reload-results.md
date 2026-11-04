# Reload time

Reported, not enforced. Produced by `tests/perf/measure_reload.py`.

| | |
|---|---|
| Date | 2026-11-04T07:18:56-08:00 |
| Machine | Linux 7.3.1-1-cachyos x86_64 |
| Python | 3.14.9 |
| Compositor | private headless sway, pixman renderer, the example Bar with a Clock |
| Change | `Height` of the Bar, 10 saves, 32 and 40 alternating |

| What | Median | Best | Worst |
|---|---|---|---|
| Save to the Bar changed (log time of `reloaded`) | 206 ms | 205 ms | 208 ms |
| From the end of the 200 ms debounce to the apply (validate, diff, set) | 5 ms | 5 ms | 7 ms |

The target is a change on screen within about 300 ms of the save, 200 ms of which is the debounce.
The log time is when the shell finished applying; the compositor's own reflow follows it.
