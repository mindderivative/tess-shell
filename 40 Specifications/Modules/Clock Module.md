---
title: Clock Module
aliases: [Clock, Clock_Module]
type: spec
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-27
tags: [spec/module, needs-verification]
related: ["[[Modules]]", "[[Module Contract]]", "[[Module Context]]", "[[Module File]]", "[[V1 Scope]]", "[[Building Blocks]]"]
depends_on: ["[[Module Contract]]", "[[Module File]]"]
---

# Clock module

> [!summary]
> The Clock shows the time. It is the simplest v1 module: no service, no D-Bus, no worker thread. Its layout is a Label, its style a small file, and its Python a timer on the loop thread that sends a formatted string once per second (or once per minute when the format has no seconds). Several uses can show different formats and time zones from one instance. All names and YAML below are illustrations built on the proposals in [[Module File]] and [[Module Context]]; nothing here is final.

## Purpose and scope

- Show the current time, and optionally a date in a tooltip, on any surface that places the module.
- v1: local time and an optional fixed time zone per use, formatted as the desktop does by default. A clock face, alarms, timers and a calendar are out of scope ([[V1 Scope#After v1]]); no calendar to start with (maintainer, 2026-10-27).

## Files

```
Modules/Clock/
    Clock_Module.yaml      the layout and its params
    Clock_Style.yaml       the look
    Clock_Module.py        the logic
```

## Behaviour

### Layout (`Clock_Module.yaml`)

```yaml
shell: v1
type: Module
name: Clock
style: Clock_Style.yaml
params:
    format: {type: string, default: ""}            # a strftime pattern; empty follows the desktop
    locale: {type: string, default: ""}            # a locale name such as de_DE; empty follows the desktop
    hour_cycle: {type: string, default: "desktop"} # desktop, 12 or 24
    timezone: {type: string, default: ""}          # an IANA name; empty is the local zone
    tooltip_format: {type: string, default: "%A, %d %B %Y"}

block: FlexBox
alignment: horizontal
children:
    Label:
        text: "{{ time }}"                          # the value the Python sends; TEL decides the syntax
        class: clock_text
```

- The Label is the standard module over the Text block ([[Building Blocks]]). It is not editable.
- Params are what a use passes; a use that passes nothing gets the defaults.
- `time` is a value sent by the Python for this use. How a name reaches an expression is in [[Module File#Data in the layout]].

### Style (`Clock_Style.yaml`)

```yaml
shell: v1
type: Style

classes:
    clock_text:
        block: Text
        size: 14
        weight: 500
        foreground: "#ffffff"
```

### Logic (`Clock_Module.py`)

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from tesserae_shell import Module

class Clock(Module):
    def start(self):
        self.tick()

    def tick(self):
        now_by_zone = {}
        wait = 60.0
        for use in self.ctx.uses.values():
            tz = use.params["timezone"] or None
            if tz not in now_by_zone:
                now_by_zone[tz] = datetime.now(ZoneInfo(tz) if tz else None).astimezone()
            now = now_by_zone[tz]
            self.ctx.send("time", now.strftime(use.params["format"]), use=use)
            self.ctx.send("tooltip", now.strftime(use.params["tooltip_format"]), use=use)
            if "%S" in use.params["format"]:
                wait = 1.0
        # aim at the next whole second or minute from the wall clock, so a pause or a time change does not drift
        now = datetime.now()
        step = wait
        until = step - ((now.second + now.microsecond / 1e6) % step) if step == 60.0 else 1.0 - now.microsecond / 1e6
        self.ctx.after(until, self.tick)

    def use_added(self, use):
        self.tick()
```

An illustration of the shape, not tested code. With the shared time source ([[Module Context#A shared time source]]) the Clock subscribes (`self.ctx.on_tick("minute", self.tick)`, or `"second"` when a use's format has seconds) instead of scheduling `self.ctx.after` itself; the sketch below shows the timer form. What it shows:

- One instance, one timer, for every use. A format with seconds makes the timer fire every second; otherwise once a minute, aimed at the next minute boundary.
- Each use gets its own text through `ctx.send(..., use=use)` ([[Module Context#Sending values]]).
- The next tick is computed from the wall clock each time, so a sleep, a resume or a manual time change corrects itself within one tick.
- Everything runs on the loop thread and takes well under a millisecond; there is no worker thread ([[Process Model and Threading#The rules]]).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `format` | string | empty | A `strftime` pattern for the shown text (decided 2026-10-27). Empty derives the pattern from the desktop's time format, with `hour_cycle` applied |
| `locale` | string | empty | A locale name for month and day names; empty follows the desktop |
| `hour_cycle` | string | `desktop` | `desktop`, `12` or `24`; the user can set it (decided 2026-10-27) |
| `timezone` | string | empty | An IANA zone name such as `Europe/Berlin`; empty uses the local zone |
| `tooltip_format` | string | `%A, %d %B %Y` | The text a tooltip shows |

Placing it. The call form is decided in [[ADR-0007 Shell UI Layer#Module call, shipped modules and Path (2026-10-26)]]. One clock in a container:

```yaml
children:
    Clock:
        format: "%H:%M:%S"
```

Two clocks in one container repeat the module, so they use the list form (a mapping cannot hold the key `Clock` twice):

```yaml
children:
    - Clock:
        name: local_clock
        format: "%H:%M"
    - Clock:
        name: ny_clock
        timezone: America/New_York
        format: "%H:%M NY"
```

## Python contract

The class follows [[Module Contract]]. It uses `ctx.uses`, `use.params`, `ctx.send(..., use=)` and `ctx.after`. It has no `stop` work (the shell cancels timers) and no `reload` work beyond re-reading params on the next tick. A changed `format` or `timezone` in a use takes effect on the next tick.

## Integration

- Source: the system clock through Python's `datetime`; `zoneinfo` for zones, and the shell's shared time source for ticks. No service, no D-Bus, no file.
- Thread: the loop thread, through `ctx.after` ([[Process Model and Threading]]).
- A Tooltip module can show the `tooltip` value on hover ([[Building Blocks]]); the standard Tooltip is not required for v1.
- Following the desktop's 12 or 24 hour setting and locale is the default; the user can set both (decided 2026-10-27, `locale` and `hour_cycle` params). #needs-verification how KDE exposes the regional settings (its locale files, or the environment).
- **Shared time source (decided 2026-10-27).** The shell offers one time source, so all modules tick together. The Clock subscribes to it instead of running its own timer; the shape is proposed in [[Module Context#A shared time source]].

## Design

Tokens and components used: the Label module over the Text block; a text class from the style file. The look comes from the theme for the colour and type scale ([[50 Design System]]).

## Accessibility

- The Label exposes its text as the accessible name; the value changes every second or minute.
- A screen reader must not be told on every tick. The text is read when the user focuses the element or asks for it; live announcement is off by default (proposed). #needs-verification against how tre publishes name changes ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).
- The tooltip text is available as a description.

## Performance budget

- One timer for all uses. With seconds, one wake and one text update per second per distinct text; without seconds, one per minute. No frames between updates ([[TRE-REQ-001 Layer Surface Window]]: an idle surface draws no frames).
- Per tick: under 1 ms on the loop thread (proposed; measured in the testing phase).
- A Clock must not add a timer that fires faster than the shown unit.

## Failure modes and recovery

| Failure | Result |
|---|---|
| A `format` that is not a valid pattern, or that raises | Validated when the use is loaded: error naming the param and the file, the use shows the fallback (`--:--`); other uses are unaffected |
| An unknown `timezone` | Error at load for that use, naming the param and the file (validated when the use is added); the use shows the fallback |
| The system time jumps (resume, manual change, daylight saving) | The next tick is computed from the wall clock, so it corrects within one tick |
| The timer callback raises | Logged with the module name; the next tick is still scheduled (the schedule is set before work that can fail; proposed) |

## Open questions

- [x] `strftime` patterns (maintainer, 2026-10-27, the recommendation). Open: locale-aware names through the `locale` param.
- [x] Follow the desktop's 12 or 24 hour setting and locale by default; the user can set both (maintainer, 2026-10-27). Open: how KDE exposes them. #needs-verification
- [x] `format` is validated when the use is loaded, through a hook in the module contract (maintainer, 2026-10-27, "on use loaded"). The hook is proposed in [[Module Contract]].
- [x] No calendar to start with (maintainer, 2026-10-27).
- [x] The shell offers a shared time source (maintainer, 2026-10-27); the shape is in [[Module Context#A shared time source]].

## Acceptance criteria

- [ ] A bar shows the local time in the desktop's format, and the text changes at the start of each minute when the format has no seconds.
- [ ] With `hour_cycle: 12` the time shows in 12-hour form; with `locale: de_DE` day and month names are German.
- [ ] With `%S` in the format, the text changes every second without drift over 10 minutes.
- [ ] Two uses with different formats and time zones show different text from one module instance.
- [ ] After the system clock is moved by an hour, the text is correct within one tick.
- [ ] An invalid `format` shows the fallback and logs the module, use and param; other uses are unaffected.
- [ ] Idle: no frames and no wake-ups between ticks (measured).
- [ ] The Python never blocks the loop and starts no thread.

## Links

- [[Modules]] · [[Module Contract]] · [[Module Context]] · [[Module File]] · [[V1 Scope]]
