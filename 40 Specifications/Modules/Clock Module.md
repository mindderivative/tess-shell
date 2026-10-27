---
title: Clock Module
aliases: [Clock, Clock_Module]
type: spec
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [spec/module, needs-verification]
related: ["[[Modules]]", "[[Module Contract]]", "[[Module Context]]", "[[Module File]]", "[[V1 Scope]]", "[[Building Blocks]]"]
depends_on: ["[[Module Contract]]", "[[Module File]]"]
---

# Clock module

> [!summary]
> The Clock shows the time. It is the simplest v1 module: no service, no D-Bus, no worker thread. Its layout is a Label, its style a small file, and its Python a timer on the loop thread that sends a formatted string once per second (or once per minute when the format has no seconds). Several uses can show different formats and time zones from one instance. All names and YAML below are illustrations built on the proposals in [[Module File]] and [[Module Context]]; nothing here is final.

## Purpose and scope

- Show the current time, and optionally a date in a tooltip, on any surface that places the module.
- v1: local time and an optional fixed time zone per use. A clock face, alarms, timers and a calendar popup are out of scope ([[V1 Scope#After v1]]).

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
    format: {type: string, default: "%H:%M"}       # a strftime pattern
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

An illustration of the shape, not tested code. What it shows:

- One instance, one timer, for every use. A format with seconds makes the timer fire every second; otherwise once a minute, aimed at the next minute boundary.
- Each use gets its own text through `ctx.send(..., use=use)` ([[Module Context#Sending values]]).
- The next tick is computed from the wall clock each time, so a sleep, a resume or a manual time change corrects itself within one tick.
- Everything runs on the loop thread and takes well under a millisecond; there is no worker thread ([[Process Model and Threading#The rules]]).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `format` | string | `%H:%M` | A `strftime` pattern for the shown text |
| `timezone` | string | empty | An IANA zone name such as `Europe/Berlin`; empty uses the local zone |
| `tooltip_format` | string | `%A, %d %B %Y` | The text a tooltip shows |

Placing it (the call form is decided in [[ADR-0007 Shell UI Layer#Module call, shipped modules and Path (2026-10-26)]]):

```yaml
children:
    Clock:
        format: "%H:%M:%S"
    Clock:
        timezone: America/New_York
```

The second line above is a repeat of one module in one container, so it must use the list form:

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

- Source: the system clock through Python's `datetime`; `zoneinfo` for zones. No service, no D-Bus, no file.
- Thread: the loop thread, through `ctx.after` ([[Process Model and Threading]]).
- A Tooltip module can show the `tooltip` value on hover ([[Building Blocks]]); the standard Tooltip is not required for v1.
- Following the desktop's 12 or 24 hour setting and locale: not specified here. #needs-verification how KDE exposes the regional settings.

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
| A `format` that is not a valid pattern, or that raises | The use shows a fallback (`--:--`) and the shell logs the module name, the use and the param; other uses are unaffected |
| An unknown `timezone` | Error at load for that use, naming the param and the file (validated when the use is added); the use shows the fallback |
| The system time jumps (resume, manual change, daylight saving) | The next tick is computed from the wall clock, so it corrects within one tick |
| The timer callback raises | Logged with the module name; the next tick is still scheduled (the schedule is set before work that can fail; proposed) |

## Open questions

- [ ] `strftime` patterns against a simpler set of tokens; locale-aware formatting.
- [ ] Following the desktop's 12 or 24 hour setting and locale.
- [ ] Whether `format` is validated when the use is loaded (a hook in the module contract) or on first tick.
- [ ] A calendar popup on click: it needs a Popup and a Calendar module ([[Surface Types#Special cases]]); not v1.
- [ ] Whether the shell offers a shared time source so all modules tick together.

## Acceptance criteria

- [ ] A bar shows the local time and the text changes at the start of each minute with the default format.
- [ ] With `%S` in the format, the text changes every second without drift over 10 minutes.
- [ ] Two uses with different formats and time zones show different text from one module instance.
- [ ] After the system clock is moved by an hour, the text is correct within one tick.
- [ ] An invalid `format` shows the fallback and logs the module, use and param; other uses are unaffected.
- [ ] Idle: no frames and no wake-ups between ticks (measured).
- [ ] The Python never blocks the loop and starts no thread.

## Links

- [[Modules]] · [[Module Contract]] · [[Module Context]] · [[Module File]] · [[V1 Scope]]
