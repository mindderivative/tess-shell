"""The accessibility pass (M6 Brief, E1): the role, name, description and state of the
shipped modules, read back through the accessibility tree of a headless tre window (``node.get``:
tre publishes exactly what was set), and each announcement a module makes with ``ctx.announce``
(``Window.announce`` of the window of its use, tre 0.6.9). A headless window has no screen reader
to hear it, so :class:`Said` records each call on its way to the window; the AT-SPI signal itself
is read in ``tests/test_announce_atspi.py``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.launcher_rig import launcher_desk
from tests.modules_rig import desk, shell
from tests.tasks_rig import tasks_desk, tasks_shell
from tests.test_launcher import BROWSERS
from tests.test_tasks import a, buttons, lists, start
from tests.widgets_live import Widgets, running

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


class Said:
    """Stands in for ``host.surfaces``: records each ``ctx.announce`` (the use keys, the text and
    the politeness) and passes it on, so the real window gets ``announce`` too."""

    def __init__(self, port: Any) -> None:
        self.port = port
        self.calls: list[tuple[tuple[str, ...], str, str]] = []

    def announce(self, use_keys: Any, text: str, politeness: str) -> bool:
        self.calls.append((tuple(use_keys), text, politeness))
        return bool(self.port.announce(use_keys, text, politeness))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.port, name)

    @property
    def texts(self) -> list[str]:
        return [text for _, text, _ in self.calls]

    @property
    def last(self) -> str | None:
        return self.calls[-1][1] if self.calls else None


def listen(w: Widgets) -> Said:
    """Record what the modules of this running shell announce, from now on."""
    said = Said(w.host.surfaces)
    w.host.surfaces = said  # type: ignore[assignment]
    return said


# -- the static modules: role, name, state -------------------------------------------------------

STATIC = [
    ("Label", 'Label { Text: "Hi" }', "Label", "#0", {"label": "Hi", "role": None}),
    ("TextBox", 'TextBox { Text: "a b" }', "TextBox", "#0", {"label": "a b"}),
    ("Button", 'Button { Text: "Save" }', "Button", "Root", {"role": "button", "label": "Save"}),
    (
        "Button icon",
        'Button { Icon: "mdi:home", Label: "Home" }',
        "Button",
        "Root",
        {"role": "button", "label": "Home"},
    ),
    (
        "Toggle",
        "Toggle { Label: Wi-Fi, Checked: true }",
        "Toggle",
        "Root",
        {"role": "switch", "label": "Wi-Fi", "checked": True, "focusable": True},
    ),
    (
        "Checkbox",
        "Checkbox { Text: Agree }",
        "Checkbox",
        "Root",
        {"role": "checkbox", "label": "Agree", "checked": False},
    ),
    (
        "Slider",
        'Slider { Label: Vol, Value: 30, Value_Text: "30 percent" }',
        "Slider",
        "Root",
        {"role": "slider", "label": "Vol", "value_text": "30 percent", "value_max": 100},
    ),
    (
        "ProgressBar",
        "ProgressBar { Value: 25, Label: Up }",
        "ProgressBar",
        "Root",
        {"role": "progressbar", "label": "Up", "value": 25},
    ),
    ("Badge", "Badge { Count: 3 }", "Badge", "Root", {"a11y_hidden": True}),
    ("Icon", 'Icon { Icon: "mdi:home" }', "Icon", "Root", {"a11y_hidden": True}),
    (
        "Icon named",
        'Icon { Icon: "mdi:home", Label: Home }',
        "Icon",
        "Root",
        {"label": "Home", "a11y_hidden": False},
    ),
    ("Image", 'Image { Placeholder: "#334455" }', "Image", "Root", {"a11y_hidden": True}),
    ("Marquee_Text", 'Marquee_Text { Text: "abc" }', "Marquee_Text", "Root", {"label": "abc"}),
    (
        "Expander closed",
        "Expander { Expanded: false, Children { Label { Text: x } } }",
        "Expander",
        "Body",
        {"a11y_hidden": True},
    ),
    (
        "TextInput placeholder",
        "TextInput { Placeholder: Search }",
        "TextInput",
        "#1",
        {"role": "textbox", "label": "Search"},
    ),
    (
        "TextInput label",
        "TextInput { Placeholder: Search, Label: Query }",
        "TextInput",
        "#1",
        {"label": "Query"},
    ),
    (
        "TextEditor",
        "TextEditor { Placeholder: Notes }",
        "TextEditor",
        "#2",
        {"role": "textbox", "label": "Notes"},
    ),
    (
        "List",
        "List { Label: L, Selected: b, Children { Label { Text: A, Key: a } "
        "Label { Text: B, Key: b } } }",
        "List",
        "Root",
        {"role": "list", "label": "L", "focusable": True},
    ),
    (
        "Button expandable",
        "Button { Text: More, Expandable: true, Expanded: true }",
        "Button",
        "Root",
        {"expanded": True},
    ),
    (
        "Button disabled",
        "Button { Text: x, Enabled: false }",
        "Button",
        "Root",
        {"disabled": True},
    ),
]


@pytest.mark.parametrize(
    ("body", "module", "suffix", "expected"),
    [pytest.param(b, m, s, e, id=i) for i, b, m, s, e in STATIC],
)
def test_the_tree_of_a_static_module(
    body: str, module: str, suffix: str, expected: dict[str, Any]
) -> None:
    with running(body) as w:
        node = w.of_use(module, suffix)
        for key, value in expected.items():
            assert node.get(key) == value, (key, node.get(key))


def test_the_list_entries_are_list_items_and_the_chosen_one_is_selected() -> None:
    body = "List { Selected: b, Children { Label { Text: A, Key: a } Label { Text: B, Key: b } } }"
    with running(body) as w:
        items = [n for k, n in w.view.nodes.items() if k.startswith("Label@")]
        assert [(n.get("role"), n.get("label"), n.get("selected")) for n in items] == [
            ("listitem", "A", False),
            ("listitem", "B", True),
        ]


def test_a_slider_without_value_text_says_its_number_only() -> None:
    with running("Slider { Label: V, Value: 4 }") as w:
        node = w.of_use("Slider", "Root")
        assert node.get("value_text") is None and node.get("value") == 4


# -- the Panel ---------------------------------------------------------------------------------


def test_a_surface_is_named_and_an_exclusive_panel_is_a_dialog(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        window = d.panel.window
        assert window.root.get("label") == "Launcher"
        (body,) = window.root.children()
        assert (body.get("role"), body.get("label")) == ("dialog", "Launcher")
        assert d.w.surface("Top_Bar").window.root.get("label") == "Top Bar"


# -- Applications ----------------------------------------------------------------------------------


def row_labels(d: Any) -> list[str]:
    return [str(n.get("label")) for n in d.rows()]


def test_the_launcher_names_its_field_its_rows_and_its_list(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        assert d.field().get("label") == "Search applications"
        assert d.field().get("role") == "textbox"
        assert "Firefox, Web Browser" in row_labels(d) and "Files, Browse folders" in row_labels(d)
        assert {n.get("role") for n in d.rows()} == {"listitem"}
        (lst,) = [n for n in d.panel.view.nodes.values() if n.get("role") == "list"]
        assert (lst.get("role"), lst.get("label")) == ("list", "Results")


def test_the_launcher_says_the_selected_row_as_the_selection_moves(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        said = listen(d.w)
        d.toggle()
        assert said.calls == []  # opening says nothing: the dialog and the field do
        d.press("arrow_down")
        assert said.last == "Fire Dragon, 2 of 4"
        d.press("arrow_down")
        assert said.last == "Firefox, 3 of 4"
        d.press("arrow_up")
        assert said.last == "Fire Dragon, 2 of 4"
        assert said.texts == ["Fire Dragon, 2 of 4", "Firefox, 3 of 4", "Fire Dragon, 2 of 4"]
        assert {p for _, _, p in said.calls} == {"polite"}


def test_the_launcher_says_no_results_and_a_typed_first_row_after_a_second(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        said = listen(d.w)
        d.toggle()
        d.type("fire")
        assert said.calls == []  # typing is not one announcement a key
        (tick,) = d.w.host.ticks._subs
        tick.fn()  # the next second
        d.loop.drain()  # the announcement goes to the loop thread
        d.w.flush()
        d.window.advance(16)
        assert said.texts == ["Fire Dragon, 1 of 2"]
        d.type("zzz")
        assert d.message() == "No results" and said.last == "No results"
        before = len(said.calls)
        d.toggle()  # hide
        d.toggle()  # show again: nothing said before is said again
        assert len(said.calls) == before


# -- Tasks ---------------------------------------------------------------------------------------


@needs_daemon
def test_a_task_button_is_named_by_the_desktop_entrys_name(tmp_path: Path) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.entry("fake-app", "fake-icon", name="Fake Application")
        t.fake.script.windows = [a(1, title="Alpha")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        assert t.settle(w, lambda: buttons(w)[0].get("label") == "Alpha, Fake Application")


@needs_daemon
def test_tasks_announces_a_window_that_opens_closes_or_wants_attention_when_asked(
    tmp_path: Path,
) -> None:
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { announce: true }\nTasks { }") as w:
        said = listen(w)
        t.fake.script.windows = [a(1, title="One")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        assert said.calls == []  # the first list says nothing
        lists(t, w, a(1, title="One"), a(2, title="Two"))
        assert t.settle(w, lambda: said.last == "Two opened")
        lists(t, w, a(1, title="One", attention=True), a(2, title="Two"))
        assert t.settle(w, lambda: said.last == "One wants attention")
        lists(t, w, a(1, title="One", attention=True))
        assert t.settle(w, lambda: said.last == "Two closed")
        assert {p for _, _, p in said.calls} == {"polite"}
        # the second use has not asked: every announcement was for the first use
        assert len({keys for keys, _, _ in said.calls}) == 1 and len(said.calls) == 3


@needs_daemon
def test_tasks_says_the_last_window_closing_although_its_row_is_then_hidden(
    tmp_path: Path,
) -> None:
    """The row is out of the accessibility tree while no window is open, so a live block of the
    layout could never say this; ``Window.announce`` has no node."""
    with tasks_desk(tmp_path) as t, tasks_shell(t, "Tasks { announce: true }") as w:
        said = listen(w)
        t.fake.script.windows = [a(1, title="Only")]
        start(t, w)
        assert t.settle(w, lambda: len(buttons(w)) == 1)
        lists(t, w)
        assert t.settle(w, lambda: said.last == "Only closed")
        assert buttons(w) == []


# -- Network, Battery ---------------------------------------------------------------------------


@needs_daemon
def test_network_says_connected_and_disconnected_once_and_not_a_signal_change() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            said = listen(w)
            assert d.settle(w, lambda: w.of_use("Network", "Root").get("visible"))
            root = w.of_use("Network", "Content")  # the control that carries the tooltip (TSH-001)
            assert root.get("description") == "Wired connection 1, ethernet, connected"
            assert said.calls == []  # the first reading says nothing
            net.nothing()
            assert d.settle(w, lambda: said.last == "Network disconnected")
            net.wifi(72)
            assert d.settle(w, lambda: str(said.last).startswith("Network connected, Wi-Fi"))
            count = len(said.calls)
            net.ap["one"].set("Strength", 30)  # a weaker signal is not the news
            d.settle(w, lambda: False, 0.3)
            assert len(said.calls) == count
            assert {p for _, _, p in said.calls} == {"polite"}


@needs_daemon
def test_a_module_on_two_bars_is_read_once() -> None:
    """Two uses used to be two live regions, so a screen reader said the change twice; one
    ``ctx.announce`` is one call, on the first use's window."""
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }\nNetwork { }") as w:
            said = listen(w)
            assert d.settle(w, lambda: w.of_use("Network", "Root").get("visible"))
            net.nothing()
            assert d.settle(w, lambda: said.last == "Network disconnected")
            d.settle(w, lambda: False, 0.3)
            assert said.texts == ["Network disconnected"]


@needs_daemon
def test_battery_says_critical_once_and_a_change_of_percent_never() -> None:
    with desk() as d:
        fake, obj = d.battery(percentage=15.0)
        fake.up()
        with shell(d, "Battery { }") as w:
            said = listen(w)
            assert d.settle(w, lambda: w.of_use("Battery", "Root").get("visible"))
            root = w.of_use("Battery", "Content")  # the control that carries the tooltip (TSH-001)
            assert root.get("description") == "15 %, discharging, 2 h 14 min left"
            assert said.calls == []
            obj.set("Percentage", 12.0)
            d.settle(w, lambda: False, 0.3)
            assert said.calls == []
            obj.set("WarningLevel", 4)
            assert d.settle(w, lambda: said.texts == ["Battery critical, 12 percent, discharging"])
            assert said.calls[0][2] == "polite"


# -- Media -------------------------------------------------------------------------------------


@needs_daemon
def test_media_says_a_new_track_only_when_asked_and_its_position_in_words() -> None:
    from tests.fake_mpris import metadata

    with desk() as d:
        p = d.player("vlc", status="Playing", meta=metadata("Song", ["Ann"]))
        p.up()
        with shell(d, "Media { announce: true, show_position: true }\nMedia { }") as w:
            said = listen(w)
            assert d.settle(w, lambda: w.of_use("Media", "Root").get("visible"))
            tip = w.of_use("Media", "Root").get("description")
            assert tip == "Song, Ann (Fake Player), playing"
            slider = next(n for k, n in w.view.nodes.items() if k.endswith(".Position/Root"))
            assert d.settle(w, lambda: str(slider.get("value_text")).endswith(" of 3:20"))
            assert said.calls == []
            p.track(title="Next", artist=["Bo"])
            assert d.settle(w, lambda: said.last == "Track changed: Next, Bo")
            assert len(said.calls) == 1  # one use asked, so one announcement


# -- Audio -------------------------------------------------------------------------------------


def test_audio_says_mute_at_once_and_a_settled_volume_when_asked(
    fake_pulse: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tess_shell.services import audio as audio_service
    from tests import test_audio_module as T

    monkeypatch.setattr(audio_service, "SHORT_SESSION", 0.0)
    T.maintainers_desktop(fake_pulse)
    body = "Audio { announce: true, show_slider: true }"
    with T.desk(fake_pulse) as d, T.shell(d, body) as w:
        said = listen(w)
        assert d.settle(w, lambda: T.icon_of(w) == "volume-medium")
        assert w.of_use("Audio", "Toggle").get("description") == "Razer Leviathan V2 X, 45 %"
        slider = next(n for k, n in w.view.nodes.items() if k.endswith(".Volume/Root"))
        assert slider.get("value_text") == "45 percent"
        assert said.calls == []
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: said.last == "Muted")
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert d.settle(w, lambda: said.last == "Unmuted, 45 percent")
        w.window.simulate("wheel", node=w.of_use("Audio", "Root"), delta_y=-120)
        assert d.settle(w, lambda: w.host.ticks._subs != [])  # one tick waits to say it
        w.host.ticks._subs[0].fn()
        assert d.settle(w, lambda: said.last == "Volume 50 percent")
        assert w.host.ticks._subs == []
        assert {p for _, _, p in said.calls} == {"polite"}
