"""The pipe between the shell and a module process (``tess_shell.modproc.wire``): what goes in
comes out, and a peer that misbehaves is noticed, never trusted."""

from __future__ import annotations

import socket
import threading
from typing import Any

import pytest

from tess_shell.modproc import wire


def roundtrip(value: Any) -> Any:
    return wire.decode(wire.encode({"v": value}))["v"]


@pytest.mark.parametrize(
    "value",
    [
        "text with \n a newline and \u00e9",
        1,
        2.5,
        True,
        None,
        [1, [2, 3], {"a": 1}],
        {"a": {"b": [1, 2]}},
    ],
)
def test_plain_data_comes_out_as_it_went_in(value: Any) -> None:
    assert roundtrip(value) == value


def test_a_tuple_stays_a_tuple_and_a_list_stays_a_list() -> None:
    """A D-Bus call with several results is a tuple, and the Tray module tells the two apart."""
    got = roundtrip({"r": (1, ("a", [2, (3,)]))})
    assert got == {"r": (1, ("a", [2, (3,)]))}
    assert isinstance(got["r"], tuple) and isinstance(got["r"][1][1], list)
    assert isinstance(got["r"][1][1][1], tuple)


def test_bytes_cross_as_bytes() -> None:
    assert roundtrip({"png": b"\x89PNG\r\n\x00\xff"}) == {"png": b"\x89PNG\r\n\x00\xff"}


def test_a_dict_with_other_than_string_keys_keeps_them() -> None:
    value = {1: "a", 2: "b", (1, 2): "c"}
    assert roundtrip(value) == value


def test_a_dict_that_looks_like_a_tag_is_not_taken_for_one() -> None:
    for value in ({"$t": [1, 2]}, {"$b": "AAAA"}, {"$d": [[1, 2]]}):
        assert roundtrip(value) == value


def test_what_cannot_cross_is_refused_at_the_sender() -> None:
    with pytest.raises(TypeError, match="object"):
        wire.encode({"v": object()})


def test_decode_refuses_what_is_not_an_object() -> None:
    with pytest.raises(ValueError):
        wire.decode(b"[1, 2]\n")
    with pytest.raises(ValueError):
        wire.decode(b"not json\n")


def test_plain_encoding_needs_no_tagging_pass() -> None:
    assert wire.decode(wire.encode_plain({"t": "s", "v": [1, "a"]})) == {"t": "s", "v": [1, "a"]}


# -- two ends -------------------------------------------------------------------------------------


class Ends:
    def __init__(self, **kw: Any) -> None:
        a, b = socket.socketpair()
        self.got: list[dict[str, Any]] = []
        self.bad: list[str] = []
        self.arrived = threading.Condition()
        self.closed = threading.Event()
        self.peer_closed = threading.Event()

        def on_message(m: dict[str, Any]) -> None:
            with self.arrived:
                self.got.append(m)
                self.arrived.notify_all()

        self.left = wire.Channel(
            a, on_message, self.closed.set, "left", on_bad=self.bad.append, **kw
        )
        self.right = wire.Channel(b, lambda m: None, self.peer_closed.set, "right")
        self.left.start()
        self.right.start()
        self.raw = b  # the right end's socket, for writing bytes that are no message

    def wait(self, n: int) -> None:
        with self.arrived:
            assert self.arrived.wait_for(lambda: len(self.got) >= n, 5), self.got

    def close(self) -> None:
        self.left.close()
        self.right.close()


def test_messages_arrive_in_order_and_a_big_one_arrives_whole() -> None:
    ends = Ends()
    try:
        big = "x" * (1 << 20)
        for n in range(50):
            ends.right.send({"n": n})
        ends.right.send({"big": big})
        ends.wait(51)
        assert [m["n"] for m in ends.got[:50]] == list(range(50))
        assert ends.got[50]["big"] == big
    finally:
        ends.close()


def test_a_closed_peer_ends_the_channel_and_a_send_after_that_says_so() -> None:
    ends = Ends()
    ends.right.close()
    assert ends.closed.wait(5) and ends.left.reason == "eof"
    assert ends.left.send({"a": 1}) is False
    ends.close()


def test_a_line_that_is_not_json_is_dropped_and_the_next_one_still_arrives() -> None:
    ends = Ends()
    try:
        ends.raw.sendall(b"garbage\n" + wire.encode({"ok": 1}))
        ends.wait(1)
        assert ends.got == [{"ok": 1}] and len(ends.bad) == 1
        assert not ends.left.closed
    finally:
        ends.close()


def test_three_bad_lines_in_a_row_close_the_channel_and_a_good_one_resets_the_count() -> None:
    ends = Ends()
    try:
        ends.raw.sendall(b"x\ny\n" + wire.encode({"ok": 1}) + b"z\nw\n")
        ends.wait(1)
        assert not ends.closed.wait(0.3), "two, a good line, two: not three in a row"
        ends.raw.sendall(b"a\nb\nc\n")
        assert ends.closed.wait(5) and ends.left.reason == "protocol"
    finally:
        ends.close()


def test_a_line_over_the_cap_is_dropped_whole_and_counted() -> None:
    ends = Ends(max_line=1000)
    try:
        ends.raw.sendall(b'{"a":"' + b"y" * 5000 + b'"}\n' + wire.encode({"after": 1}))
        ends.wait(1)
        assert ends.got == [{"after": 1}] and "over 1000" in ends.bad[0]
    finally:
        ends.close()


def test_a_peer_that_does_not_read_overflows_the_queue_and_the_channel_closes() -> None:
    """The shell's queue to a hung child: past the cap the channel closes with ``overflow``, which
    the shell reads as hung."""
    a, b = socket.socketpair()
    closed = threading.Event()
    channel = wire.Channel(a, lambda m: None, closed.set, "writer", queue_cap=200_000)
    channel.start()
    try:
        # b is never read: the socket buffer fills, the writer blocks, the queue grows
        for _ in range(2000):
            if not channel.send({"pad": "p" * 4000}):
                break
        assert closed.wait(5) and channel.reason == "overflow"
        assert channel.send({"a": 1}) is False
    finally:
        channel.close()
        b.close()
