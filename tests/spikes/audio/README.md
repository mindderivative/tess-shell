# Audio access spike (T-018)

Not part of the suite: nothing here is named `test_*`, so a bare `pytest` never collects or runs it.

It starts a PRIVATE PipeWire (`pipewire`, `wireplumber`, `pipewire-pulse`, `dbus-daemon`) in a
`/tmp/asp-*` directory with a from-scratch environment and no real device, and measures four ways of
reaching the sound server (A native protocol client, B pulsectl-asyncio, C `pactl subscribe`,
D `pw-dump --monitor` + `wpctl`). Every client is guarded (`guard.py`): it aborts unless its target is
under `/tmp/asp-*`. Route B needs `uv pip install --target /tmp/audio-spike-libs pulsectl pulsectl-asyncio`
(outside the repo and the project venv).

Run: `env -u WAYLAND_DISPLAY -u DISPLAY $UV_PROJECT_ENVIRONMENT/bin/python -m tests.spikes.audio.spike`
(about 6 minutes; `--idle 5 --no-restart` for a quick pass). Results: `/tmp/frame-review/T018-results.json`.

The whole run is re-executed under `bwrap` (`guard.reexec_in_sandbox`): the real `/run`, `/sys` and `/dev` are
hidden, so the real sound server, session bus and sound cards do not exist inside it, and every entry
point aborts unless the sandbox is active (`guard.require_sandbox`, with an ENOENT canary on the real
socket). A first version of this spike wrote to the maintainer's real default sink (2026-11-13, D-019);
do not remove the sandbox.
