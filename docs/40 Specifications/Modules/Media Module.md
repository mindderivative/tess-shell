---
title: Media Module
aliases: [Media, Media_Module, MPRIS Module]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [spec/module, integration/dbus, needs-verification]
---

# Media Module

> [!NOTE]
> The Media module shows what a media player is playing and controls it: the title and artist, a play or pause button, previous and next, the artwork, and a position slider that can seek. It reads MPRIS players on the session bus (`org.mpris.MediaPlayer2.*`), picks one active player, follows `PropertiesChanged` and `Seeked`, and hides when no player exists. It is the first module that writes to a service (the control calls) and the first whose set of services comes and goes. The MPRIS members were read on the maintainer's machine on 2026-11-13 (read-only `busctl` calls; two players present, both for one browser) and checked against the [MPRIS D-Bus interface specification](https://specifications.freedesktop.org/mpris-spec/latest/). Written and decided by the orchestrator under the [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md); M5d builds it ([M5 Brief](../../00%20Home/M5%20Brief.md)).

## Purpose and Scope

- Show the active player's track and let the user play, pause, skip and seek.
- v1: one player at a time, chosen by the module. Not in v1: a player list or switcher, volume (the Audio module's), shuffle and loop, a queue, raising the player's window, lyrics.

## Files

```
Modules/Media/
    Media_Module.tdl     the layout and its params
    Media_Style.tdl      the look
    Media_Module.py      the logic
```

## Behaviour

### What It Reads

Session bus. Every player owns a name that starts with `org.mpris.MediaPlayer2.` and exports the object `/org/mpris/MediaPlayer2`.

| Interface | Member | Use | Read on 2026-11-13 |
|---|---|---|---|
| `org.mpris.MediaPlayer2` | `Identity` (s), `DesktopEntry` (s) | The player's name in the tooltip | "Google Chrome", "google-chrome" |
| `org.mpris.MediaPlayer2.Player` | `PlaybackStatus` (s) | `Playing`, `Paused` or `Stopped` | "Paused"; `emits-change` |
| | `Metadata` (a{sv}) | `xesam:title`, `xesam:artist` (as), `xesam:album`, `mpris:artUrl`, `mpris:length` (x, microseconds), `mpris:trackid` (o) | 7 entries, with `mpris:artUrl` a `file://` URL in `/tmp`; `emits-change` |
| | `Position` (x, microseconds) | The slider | 52209907; no `emits-change` flag: it is not signalled while playing |
| | `Rate` (d) | Position arithmetic | 1; `emits-change` |
| | `CanPlay`, `CanPause`, `CanGoNext`, `CanGoPrevious`, `CanSeek` (b) | Which controls are enabled | true, true, false, false, true; `emits-change` |
| | `CanControl` (b) | False disables every control | true; no `emits-change` flag |
| | signal `Seeked` (x) | The position jumped | Present |
| | methods `PlayPause`, `Next`, `Previous`, `SetPosition` (ox) | The controls | Present; not called |

Players are found by `ListNames` on the bus once at start and then by `NameOwnerChanged` for names with that prefix. The layer watches names it is given ([D-Bus Service Layer > Listening and Name Owners](../Integration/D-Bus%20Service%20Layer.md#listening-and-name-owners)); a watch by prefix is new ([Needs from the Layer](#needs-from-the-layer)).

On this machine one browser appeared twice: `org.mpris.MediaPlayer2.chromium.instance926871` and `org.mpris.MediaPlayer2.plasma-browser-integration`, the second carrying `kde:pid` in its metadata. The module treats a `plasma-browser-integration` player as a duplicate when another player is present whose name contains `chromium` or `firefox`, and prefers `plasma-browser-integration` because it has the better metadata. #needs-verification on Firefox.

### Choosing the Active Player

One player is shown. The rule, applied whenever the set of players or a `PlaybackStatus` changes:

1. A player that is `Playing` wins; among several, the one that started playing most recently.
2. Otherwise the player that was active last, while it still exists and is not `Stopped`.
3. Otherwise the most recently changed `Paused` player.
4. Otherwise none: the module hides.

A player with `Stopped` and no title is never chosen.

### Values Sent

| Key | Type | Meaning |
|---|---|---|
| `has_player` | boolean | True when a player is chosen. The root is `Visible: <\| available and has_player \|>` |
| `status` | string | `PLAYING`, `PAUSED` or `STOPPED` |
| `title`, `artist`, `album` | string | From the metadata; `artist` is the list joined with ", "; empty when missing |
| `player` | string | `Identity` |
| `art` | string | A local file path from `mpris:artUrl` when it is a `file://` URL; otherwise empty ([Artwork](#artwork)) |
| `length` | number | The track length in seconds; 0 when unknown |
| `position` | number | The position in seconds ([Position](#position)) |
| `can_play_pause`, `can_next`, `can_previous`, `can_seek` | boolean | From the `Can*` properties, all false when `CanControl` is false |
| `icon` | string | `pause` while playing, else `play` |
| `tooltip`, `label` | string | For example `Song, Artist (Google Chrome), paused`; `label` is the accessible name |

A value is sent only when it changes.

### Position

MPRIS does not signal `Position` while a track plays (gap G7 of [M5 Brief](../../00%20Home/M5%20Brief.md)). The module computes it:

- On a change of player, `PlaybackStatus`, `Metadata` (a new `mpris:trackid`), `Rate` or on `Seeked`, it reads `Position` once (`fresh=True`) and stores it with the monotonic time.
- While `PLAYING`, the position is the stored value plus elapsed time times `Rate`, capped at `length`.
- A timer of one second (`ctx.every`) sends `position` only while the status is `PLAYING` and a use has asked for the position (`show_position` true, or a Popup with the slider open). With no such use there is no timer and no wake-up.
- A drag of the slider sends nothing to the player until release; on release the module calls `SetPosition(trackid, microseconds)` and waits for `Seeked`.

### Controls

Actions, each an `@action` with no argument except `seek`:

| Action | Call | Enabled when |
|---|---|---|
| `play_pause` | `PlayPause` | `can_play_pause` |
| `next` | `Next` | `can_next` |
| `previous` | `Previous` | `can_previous` |
| `seek(position)` | `SetPosition(trackid, position * 1 000 000)` | `can_seek` and `length` greater than 0 |

A call runs on the `dbus` thread through `bus.run`; the action returns at once. The module does not predict the result: the icon changes when `PlaybackStatus` changes. A failed call is logged once a minute per player and changes nothing.

### Artwork

`mpris:artUrl` is a URL. A `file://` URL becomes a path and is shown by the `Image` module, which decodes it ([Standard Modules > Image](../../50%20Design%20System/Standard%20Modules.md#image)). An `http://` or `https://` URL is not fetched: the shell makes no network request ([Open Questions](#open-questions) question 3), and the Image shows its placeholder icon `music`. A file that is missing or fails to decode shows the same placeholder.

### Hiding

The module is hidden when no player is chosen. `available` (the layer's) covers the session bus being unreachable. A hidden Media module takes no Bar space, as [Battery Module](Battery%20Module.md) does.

### Layout (`Media_Module.tdl`)

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.6.7
Shell: 0.1
Name: Media
---

Module {
    Style: Media_Style.tdl
    Visible: <| available and has_player |>
    Params {
        show_art { Type: boolean, Default: false }
        show_title { Type: boolean, Default: true }
        show_controls { Type: boolean, Default: true }
        show_position { Type: boolean, Default: false }
        max_width { Type: number, Default: 240 }
    }

    FlexBox {
        Flex: HORIZONTAL
        Children {
            If <| show_art |> { Image { Source: <| art |>, Width: 24, Height: 24 } }
            If <| show_controls |> {
                Button { Icon: skip-previous, Enabled: <| can_previous |>, On_Click: previous }
                Button { Icon: <| icon |>, Enabled: <| can_play_pause |>, On_Click: play_pause }
                Button { Icon: skip-next, Enabled: <| can_next |>, On_Click: next }
            }
            If <| show_title |> {
                Marquee_Text { Text: <| title |>, Width: <| max_width |> }
            }
            If <| show_position |> {
                Slider { Value: <| position |>, Max: <| length |>, Enabled: <| can_seek |>, On_Changed { Action: seek, position: <| event.value |> } }
            }
        }
    }
}
```

A sketch; the forms follow [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md), [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) and [Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md), and the code session adjusts key spellings to what is built. The default Bar shows controls and the title, no artwork and no slider.

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `show_art` | boolean | false | The artwork, 24 px |
| `show_title` | boolean | true | The title, scrolling when it is wider than `max_width` |
| `show_controls` | boolean | true | Previous, play or pause, next |
| `show_position` | boolean | false | The seek slider; turning it on starts the one-second timer while playing |
| `max_width` | number | 240 | The title's width in pixels |

## Needs from the Layer

The layer of M5a watches names a module names. Media needs two additions, both inside `tess-shell` (Tier 1, no other project):

| Need | Proposed shape |
|---|---|
| Find and follow names by prefix | `bus.watch_prefix("org.mpris.MediaPlayer2.", on_added, on_removed)`: one `ListNames` at start and one `NameOwnerChanged` rule; the callbacks run on the `dbus` thread |
| `available` must not be the AND over a changing set of players | Player proxies are made with `optional=True` (built in M5b), so they do not count for `available`; the module's `has_player` carries the state ([M5 Brief](../../00%20Home/M5%20Brief.md) question 14) |

## Python Contract

One instance for every use. It keeps a table of players (name, proxies, status, metadata, last change time), the chosen player, and the stored position with its time. Callbacks read what changed, update the table, re-run the choice and send values; they do no other work. The one timer exists only while playing with a position shown. The module starts no thread and never blocks the loop.

## Integration

- Service: any MPRIS player on the session bus; no fixed name. Plasma's own media applet reads the same players; both may control them ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- Threads: callbacks and calls on the `dbus` thread; `ctx.send` crosses to the loop; the position timer on the loop thread.
- Files: the artwork file is read by the shell's image decoding. No network, no subprocess.

## Design

Three icon Buttons, a Marquee text and optionally an Image and a Slider, all standard modules. A disabled control uses the `:disabled` look. Colours are theme tokens ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)).

## Accessibility

- The group's name is `label`: the title, the artist, the player and the status.
- Each Button has a name: "Previous", "Play" or "Pause", "Next"; the Slider's name is "Position" with its value as a time.
- A track change is not announced by default; the announcement pass of M6 decides it with the others ([Accessibility](../../60%20Quality/Accessibility.md)).
- Keyboard operation of the Buttons and the Slider is M6 ([Standard Modules > Keyboard Operation (M6)](../../50%20Design%20System/Standard%20Modules.md#keyboard-operation-m6)).

## Performance Budget

- Idle with no player, or with a paused player: no timer and no wake-up.
- Playing with no position shown: wake-ups only on the player's signals.
- Playing with a position shown: one wake-up and at most one changed value a second.
- Per signal: under 1 ms of the module's own work on the `dbus` thread.
- A metadata change replaces the artwork at most once per track; decoding a cover is the Image module's cost (measured in [M4 Build Log](../../00%20Home/M4%20Build%20Log.md): up to 512 px under 5 ms).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| No player on the bus | Hidden |
| The chosen player leaves the bus | Its entry is removed; the choice runs again; hidden if none is left |
| A player sends metadata with missing or wrongly typed entries | The missing values are empty or 0; one warning names the entry |
| `mpris:length` is missing or 0 | `length` 0; the slider is disabled |
| `mpris:artUrl` is not a `file://` URL, or the file is missing | The placeholder icon |
| A control call fails or times out | Logged once a minute per player; nothing changes |
| A player never emits `Seeked` | The position is corrected at the next status or track change |
| `CanControl` is false | Every control is disabled; the values still show |
| Two names for one browser | The duplicate rule above; if it fails, the module may show the same track from the other name, which is harmless |
| The session bus is unreachable | `available` false; hidden |
| A callback raises | Caught, logged with the module name; the module keeps running ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Built in M5d (code session's report, 2026-11-13, not run in the vault)

- The module is `shipped/Media/` (commit `1d5f4c7`, `feat/m5d-media`, merged to `main`); suite 3659 passed, 1 skipped, 7 deselected; a KWin kit is in `/tmp/tess-kwin-m5d`.
- Measured on a fake player: callbacks p50 10.9 us, p99 37.5 us, max 60.4 us over 366; idle 60 s: 0 loop iterations, 0 timeslices, 0 voluntary context switches in every scenario; the time source woke 0 times unless a player was playing with the position shown, then exactly 60 times.
- Layer additions: `Bus.watch_prefix(prefix, on_added, on_removed)` and `Bus.forget(name)`; the second was not in this spec and is needed because a browser makes a new bus name per instance ([Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper)).
- A core fix came with it: a slot on a module call's common key now reads the caller's scope.
- Decided by the orchestrator on 2026-11-13 (Tier 1): a `plasma-browser-integration` player hides the `chromium` and `firefox` players while it exists, as built; a `Stopped` player is never shown, even with a title, as built; the Slider gets an `On_Released` event, so a seek is sent on release and `On_Click` no longer stands in for it (task T-023); the cover swaps nodes through the Image module, with two `Visible` Images as the fallback if a compositor shows trouble.
- Not built, left to M6: the Slider's value read as a time for assistive technology, announcements and keys.

## Open Questions

Decided by the orchestrator on 2026-11-13 ([Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md) rule 7, Tier 1).

1. [x] One player or a list? One, chosen by the rule above; a switcher is after v1.
2. [x] Does the default Bar show the artwork and the slider? No: controls and title only; `show_art` and `show_position` turn them on.
3. [x] Is remote artwork (`http`, `https`) fetched? No: the shell makes no network request in v1; the placeholder shows.
4. [x] Do the controls predict their result? No: the look follows the player's own signals.
5. [x] Is the tooltip English in v1? Yes, with the wording in one table, as in [Network Module](Network%20Module.md).

## Questions After Testing

1. [ ] Do the common players (a browser through `plasma-browser-integration`, a music player such as Elisa or Spotify, `mpv` with its MPRIS script) emit `Seeked` and `PropertiesChanged` as the specification says? Context: players differ in practice. Recommendation: keep the design and correct the position at the next change where a player does not. Answered by: the fake player in the tests for the rule, and a live run with two real players for the difference.
2. [ ] Does the duplicate rule hold for Firefox with `plasma-browser-integration`? Context: only Chrome was seen. Recommendation: keep the rule and extend the name list if needed. Answered by: a live run with Firefox.

## Acceptance Criteria

- [ ] With no player on a private bus the module is hidden and takes no Bar space.
- [ ] A fake player that is `Playing` with a title and artist shows them, with the `pause` icon; setting `Paused` changes the icon to `play` within one loop turn after the signal.
- [ ] `can_next` false disables the Next button; a click on it calls nothing.
- [ ] A click on play or pause calls `PlayPause` once on the fake player; next and previous call `Next` and `Previous`.
- [ ] With two fake players, the one that is `Playing` is shown; when it pauses and the other plays, the other is shown; when the shown player leaves, the remaining one is shown.
- [ ] With `show_position` true and a playing fake player, `position` advances by one a second and jumps on `Seeked`; a slider release calls `SetPosition` with the track id and microseconds.
- [ ] With `show_position` false, or a paused player, the module causes no wake-ups over 60 seconds.
- [ ] A `file://` artwork URL shows the image; an `https://` one and a missing file show the placeholder, with no network request (checked by the test having no network).
- [ ] The duplicate rule shows one entry for the two browser names read on 2026-11-13.
- [ ] Removing every player hides the module; a new player shows it, with no shell restart.
- [ ] The Python never blocks the loop and starts no thread; every icon name (`play`, `pause`, `skip-next`, `skip-previous`, `music`) exists in the shipped `mdi` set (checked 2026-11-13).

## Links

- [Modules](Modules.md) · [Network Module](Network%20Module.md) · [Battery Module](Battery%20Module.md) · [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md) · [Module Contract](../../42%20Python%20API/Module%20Contract.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md)
