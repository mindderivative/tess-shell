"""The value store: thread-safe sends, coalescing, type checks, broadcast to uses."""

from __future__ import annotations

import threading

from tess_shell.model.store import Change, ValueStore


def store(*uses: str, module: str = "Clock") -> ValueStore:
    s = ValueStore()
    for use in uses:
        s.add_use(module, use)
    return s


def test_latest_value_per_key_wins_and_is_one_change() -> None:
    s = store("Clock@1")
    for text in ("a", "b", "c"):
        s.send("Clock", "Clock@1", "time", text)
    assert s.flush() == [Change("Clock@1", "time")]
    assert s.values["Clock@1"]["time"] == "c"
    assert s.flush() == []


def test_a_value_sent_and_sent_back_in_one_turn_is_no_change() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@1", "time", "a")
    s.flush()
    s.send("Clock", "Clock@1", "time", "b")
    s.send("Clock", "Clock@1", "time", "a")
    assert s.flush() == []


def test_an_equal_value_is_not_a_change() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@1", "time", "a")
    s.flush()
    s.send("Clock", "Clock@1", "time", "a")
    assert s.flush() == []


def test_a_send_without_a_use_reaches_every_use_of_that_module_only() -> None:
    s = store("Clock@1", "Clock@2")
    s.add_use("Label", "Label@9")
    s.send("Clock", None, "time", "t")
    s.send("Clock", "Clock@2", "time", "own")
    changes = s.flush()
    assert {c.use for c in changes} == {"Clock@1", "Clock@2"}
    assert s.values["Clock@1"]["time"] == "t" and s.values["Clock@2"]["time"] == "own"
    assert s.values["Label@9"] == {}


def test_values_that_are_not_plain_are_refused_and_the_last_value_stays() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@1", "time", "ok")
    s.flush()
    for bad in (object(), {"a": object()}, [1, {2: 3}], lambda: 1):
        s.send("Clock", "Clock@1", "time", bad)
    assert s.flush() == [] and s.values["Clock@1"]["time"] == "ok"


def test_lists_and_dicts_are_copied_so_the_sender_cannot_change_them_later() -> None:
    s = store("Clock@1")
    items = [1, {"a": [2]}]
    s.send("Clock", "Clock@1", "items", items)
    items[1]["a"].append(3)  # type: ignore[index, union-attr]
    s.flush()
    assert s.values["Clock@1"]["items"] == [1, {"a": [2]}]


def test_an_unknown_use_is_logged_not_raised() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@404", "time", "x")
    assert s.flush() == []


def test_sends_from_two_threads_in_one_turn_leave_the_latest_value_per_key() -> None:
    s = store("Clock@1")
    woken: list[int] = []
    s.on_change = lambda changes: woken.append(len(changes))
    scheduled: list[object] = []
    s.attach_loop(lambda callback: scheduled.append(callback))

    def worker(key: str) -> None:
        for i in range(200):
            s.send("Clock", "Clock@1", key, i)

    threads = [threading.Thread(target=worker, args=(k,)) for k in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(scheduled) == 1  # many sends, one wake-up
    scheduled[0]()  # type: ignore[operator]
    assert s.values["Clock@1"] == {"a": 199, "b": 199}
    assert woken == [2]


def test_sends_before_the_loop_exists_wait_for_attach_loop() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@1", "time", "early")
    scheduled: list[object] = []
    s.attach_loop(lambda callback: scheduled.append(callback))
    assert len(scheduled) == 1
    s.send("Clock", "Clock@1", "time", "later")
    assert len(scheduled) == 1  # already scheduled for this turn
    scheduled[0]()  # type: ignore[operator]
    assert s.values["Clock@1"]["time"] == "later"


def test_drop_module_forgets_values() -> None:
    s = store("Clock@1")
    s.send("Clock", "Clock@1", "time", "x")
    s.flush()
    s.drop_module("Clock")
    assert s.values["Clock@1"] == {}
