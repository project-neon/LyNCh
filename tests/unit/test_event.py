"""Control events sent to NeonFC on TCP 10002."""

import json

from lynch.state.event import Event


def test_play_is_newline_terminated():
    """Every other channel in the system is newline-delimited. Without a
    delimiter the receiver has to guess where one object ends and the
    next begins."""
    assert Event.play().serialize().endswith(b"\n")


def test_stop_is_newline_terminated():
    assert Event.stop().serialize().endswith(b"\n")


def test_payload_is_unchanged_apart_from_the_delimiter():
    raw = Event.play().serialize()

    assert json.loads(raw.decode("utf-8").strip()) == {
        "type": "MasterState",
        "event_data": {"new_state": "play"},
        "source": "tester",
        "sent_time_stamp": json.loads(raw.decode("utf-8"))["sent_time_stamp"],
    }


def test_two_events_in_a_row_split_cleanly_on_newlines():
    stream = Event.play().serialize() + Event.stop().serialize()

    lines = [line for line in stream.decode("utf-8").split("\n") if line.strip()]
    states = [json.loads(line)["event_data"]["new_state"] for line in lines]

    assert states == ["play", "stop"]
