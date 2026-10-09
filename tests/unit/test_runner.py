"""Unit tests for lynch/runner.py — each helper tested in isolation."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from lynch.runner import Runner
from lynch.state.schema import Transition, FrameState

# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def runner(tmp_path):
    """Return a Runner with mocked config and field manager."""
    config = tmp_path / "config.yaml"
    config.write_text(
        "network:\n"
        "  runner:\n"
        "    host: 127.0.0.1\n"
        "    port: 10003\n"
        "  NEONFC:\n"
        "    host: 127.0.0.1\n"
        "    data_port: 10001\n"
        "    control_port: 10002\n"
        "scenarios:\n"
        "  test:\n"
        "    template: template.yaml\n"
        "    assessments:\n"
        "      - GoalScored\n"
    )
    r = Runner(config_path=str(config), mode="NEONFC")
    r._Runner__field_manager = MagicMock()
    yield r
    r.close()


# ─── _receive_command ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_receive_command_reads_full_json(runner):
    raw = (json.dumps({"test_case": "test", "batch_size": 2}) + "\n").encode("utf-8")
    chunks = [bytes([b]) for b in raw]
    sock = MagicMock()
    sock.recv.side_effect = chunks
    result = runner._Runner__receive_command(sock)
    assert result == {"test_case": "test", "batch_size": 2}

@pytest.mark.unit
def test_runner_receive_command_empty_payload_raises(runner):
    sock = MagicMock()
    sock.recv.return_value = b""
    with pytest.raises(ConnectionError):
        runner._Runner__receive_command(sock)


# ─── _send_response ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_send_response_sends_newline_terminated_json(runner):
    sock = MagicMock()
    payload = {"status": "success", "history_files": []}
    runner._Runner__send_response(sock, payload)
    sent = sock.sendall.call_args[0][0].decode("utf-8")
    assert sent.endswith("\n")
    assert json.loads(sent.strip()) == payload


# ─── _load_template ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_load_template_loads_yaml_template(runner, tmp_path):
    tmpl = tmp_path / "template.yaml"
    tmpl.write_text("ball:\n  x: 0.0\n  y: 0.0\n")
    result = runner._Runner__load_template(str(tmpl))
    assert result["ball"]["x"] == 0.0

@pytest.mark.unit
def test_runner_load_template_loads_json_template(runner, tmp_path):
    tmpl = tmp_path / "template.json"
    tmpl.write_text('{"ball": {"x": 1.0}}')
    result = runner._Runner__load_template(str(tmpl))
    assert result["ball"]["x"] == 1.0

@pytest.mark.unit
def test_runner_load_template_missing_file_raises(runner):
    with pytest.raises(FileNotFoundError):
        runner._Runner__load_template("/nonexistent/template.yaml")


# ─── _build_episode_context ───────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_build_episode_context_resolves_scenario(runner):
    with patch.object(runner, "_Runner__load_template", return_value={"ball": {}}), \
         patch.object(runner, "_Runner__initialize_session", return_value=MagicMock()):
        with patch("lynch.runner.Recorder"):
            ctx = runner._Runner__build_episode_context({
                "test_case": "test",
                "config": {"batch_size": 3},
            })
    assert ctx.scenario_name == "test"
    assert ctx.batch_size == 3

@pytest.mark.unit
def test_runner_build_episode_context_missing_scenario_raises(runner):
    with pytest.raises(KeyError):
        runner._Runner__build_episode_context({"test_case": "nonexistent"})

@pytest.mark.unit
def test_runner_build_episode_context_missing_scenario_name_raises(runner):
    with pytest.raises(ValueError):
        runner._Runner__build_episode_context({"config": {}})

@pytest.mark.unit
def test_runner_build_episode_context_defaults_batch_size_to_one(runner):
    with patch.object(runner, "_Runner__load_template", return_value={}), \
         patch.object(runner, "_Runner__initialize_session", return_value=MagicMock()):
        with patch("lynch.runner.Recorder"):
            ctx = runner._Runner__build_episode_context({"test_case": "test"})
    assert ctx.batch_size == 1


# ─── _arm_episode / _stop_episode ────────────────────────────────────────────

@pytest.mark.unit
def test_runner_arm_episode_sends_start_and_opens_scenario(runner):
    ctx = MagicMock()
    ctx.session.connector = MagicMock()
    ctx.scenario_cfg = {}
    ctx.scenario_name = "test"
    ctx.base_seed = 10

    # Skip the post-teleport settle wait (covered separately).
    with patch("lynch.runner.time.sleep"):
        runner._Runner__arm_episode(ctx, ep_index=2)

    # seed = base_seed + ep_index = 10 + 2 = 12
    runner._Runner__field_manager.setup_scenario.assert_called_once_with(
        ctx.template, ctx.scenario_cfg, 12
    )
    
    # Verify JSON serialization for Event.play()
    sent_data = json.loads(ctx.session.connector.send.call_args[0][0])
    assert sent_data["type"] == "MasterState"
    assert sent_data["event_data"]["new_state"] == "play"
    
    ctx.recorder.start_scenario.assert_called_once_with("test", 12)

@pytest.mark.unit
def test_runner_stop_episode_sends_stop_and_closes_scenario(runner):
    ctx = MagicMock()
    ctx.session.connector = MagicMock()
    runner._Runner__stop_episode(ctx)
    
    # Verify JSON serialization for Event.stop()
    sent_data = json.loads(ctx.session.connector.send.call_args[0][0])
    assert sent_data["type"] == "MasterState"
    assert sent_data["event_data"]["new_state"] == "stop"
    
    ctx.recorder.end_scenario.assert_called_once()

@pytest.mark.unit
def test_runner_stop_episode_tolerates_send_failure(runner):
    ctx = MagicMock()
    ctx.session.connector.send.side_effect = OSError("broken pipe")
    runner._Runner__stop_episode(ctx)  # should not raise
    ctx.recorder.end_scenario.assert_called_once()


# ─── _run_episode_loop ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_run_episode_loop_breaks_on_terminal_result(runner):
    ctx = MagicMock()
    ctx.session.buffer.pull.side_effect = [
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
    ]

    terminal_result = MagicMock()
    terminal_result.is_terminal = True
    terminal_result.rewards = 1.0

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.return_value = terminal_result
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 1

@pytest.mark.unit
def test_runner_run_episode_loop_continues_until_terminal(runner):
    ctx = MagicMock()
    ctx.session.buffer.pull.side_effect = [
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
    ]

    non_terminal = MagicMock(is_terminal=False, rewards=0.0)
    terminal = MagicMock(is_terminal=True, rewards=1.0)

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.side_effect = [non_terminal, non_terminal, terminal]
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 3

@pytest.mark.unit
def test_runner_run_episode_loop_skips_none_frames(runner):
    ctx = MagicMock()
    ctx.scenario_cfg = {}
    terminal = MagicMock(is_terminal=True, rewards=1.0)
    ctx.session.buffer.pull.side_effect = [
        None,
        None,
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
    ]

    with patch("lynch.runner.assessment_registry") as mock_registry, \
         patch("lynch.runner.time.sleep"):
        mock_registry.evaluate.return_value = terminal
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 1

@pytest.mark.unit
def test_runner_run_episode_loop_records_transition_per_frame(runner):
    ctx = MagicMock()
    ctx.scenario_cfg = {}
    ctx.session.buffer.pull.side_effect = [
        Transition(state=FrameState(ball=None), next_state=None, actions={}),
        Transition(state=FrameState(ball=None), next_state=FrameState(ball=None), actions={}),
    ]

    non_terminal = MagicMock(is_terminal=False, rewards=0.0)
    terminal = MagicMock(is_terminal=True, rewards=1.0)

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.side_effect = [non_terminal, terminal]
        runner._Runner__run_episode_loop(ctx)

    assert ctx.recorder.put.call_count == 2
    # Verify transition format
    first_call = ctx.recorder.put.call_args_list[0][0][0]
    assert hasattr(first_call, "state")
    assert hasattr(first_call, "next_state")
    assert hasattr(first_call, "actions")
    assert hasattr(first_call, "rewards")


# ─── _execute_batch ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_execute_batch_runs_correct_number_of_episodes(runner):
    ctx = MagicMock()
    ctx.batch_size = 4

    with patch.object(runner, "_Runner__execute_single_episode", return_value="/tmp/ep.jsonl") as mock_ep:
        paths = runner._Runner__execute_batch(ctx)

    assert mock_ep.call_count == 4
    assert len(paths) == 4

@pytest.mark.unit
def test_runner_execute_batch_none_path_excluded(runner):
    ctx = MagicMock()
    ctx.batch_size = 3

    with patch.object(runner, "_Runner__execute_single_episode", side_effect=["/tmp/a.jsonl", None, "/tmp/b.jsonl"]):
        paths = runner._Runner__execute_batch(ctx)

    assert paths == ["/tmp/a.jsonl", "/tmp/b.jsonl"]


# ─── _handle_client ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_runner_handle_client_success_flow(runner):
    cmd = {"test_case": "test", "config": {"batch_size": 1}}
    batch_result = {"status": "success", "history_files": [], "summary_file": "/s.json"}

    mock_conn = MagicMock()
    with patch.object(runner, "_Runner__receive_command", return_value=cmd), \
         patch.object(runner, "_Runner__handle_batch", return_value=batch_result), \
         patch.object(runner, "_Runner__send_response") as mock_send:
        runner._Runner__handle_client(mock_conn)

    mock_send.assert_called_once_with(mock_conn, batch_result)

@pytest.mark.unit
def test_runner_handle_client_exception_sends_error_response(runner):
    mock_conn = MagicMock()
    with patch.object(runner, "_Runner__receive_command", side_effect=ValueError("bad input")), \
         patch.object(runner, "_Runner__send_response") as mock_send:
        runner._Runner__handle_client(mock_conn)

    response = mock_send.call_args[0][1]
    assert response["status"] == "error"
    assert "bad input" in response["message"]


@pytest.mark.unit
def test_runner_error_response_reaches_the_client(runner):
    """A real socketpair, not a mock: the bug was that the socket was
    closed before the error response was written, so RL-Engine saw EOF."""
    import socket as _socket

    server_side, client_side = _socket.socketpair()
    try:
        # An unknown test_case makes the batch fail; the point is that
        # the failure is reported rather than swallowed as EOF.
        client_side.sendall(json.dumps({"test_case": "does_not_exist"}).encode() + b"\n")
        runner._Runner__handle_client(server_side)

        client_side.settimeout(2.0)
        data = b""
        while b"\n" not in data:
            chunk = client_side.recv(4096)
            if not chunk:
                break
            data += chunk

        assert data, "client received nothing"
        response = json.loads(data.decode("utf-8").strip())
        assert response["status"] == "error"
        assert "message" in response
    finally:
        client_side.close()


@pytest.mark.unit
def test_runner_missing_test_case_message(runner):
    mock_conn = MagicMock()
    with patch.object(runner, "_Runner__receive_command", return_value={}), \
         patch.object(runner, "_Runner__send_response") as mock_send:
        runner._Runner__handle_client(mock_conn)

    response = mock_send.call_args[0][1]
    assert response["status"] == "error"
    assert "test_case" in response["message"]


# ─── evaluate on next_state (T11) ─────────────────────────────────────────────

@pytest.mark.unit
def test_runner_evaluates_reward_on_next_state(runner):
    """The transition is (s, a, s'): a ball that crosses the line in
    s' must terminate the episode. Evaluating `transition.state` saw it
    one frame late."""
    from lynch.state.schema import BallState, FrameState
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load(["GoalScored"])

    before = FrameState(ball=BallState(x=4.0, y=0.0, vx=1.0, vy=0.0))
    after = FrameState(ball=BallState(x=4.6, y=0.0, vx=1.0, vy=0.0))  # past the line

    transition = Transition(state=before, next_state=after, actions={})

    captured = {}

    class _Recorder:
        history = []

        def put(self, t):
            captured["transition"] = t

    ctx = MagicMock()
    ctx.recorder = _Recorder()
    ctx.session.buffer.pull.side_effect = [transition]

    runner._Runner__run_episode_loop(ctx)

    assert captured["transition"].done is True
    assert captured["transition"].rewards == 1.0


# ─── dense shaping merge (T18) ───────────────────────────────────────────────

@pytest.mark.unit
def test_runner_merges_shaping_into_non_terminal_frames(runner):
    """Dense shaping rides on non-terminal frames as a per-robot dict;
    the terminal frame keeps the assessment's scalar outcome reward --
    the recorder scores a whole episode by its last line."""
    from lynch.state.schema import BallState, RobotState
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([
        {"name": "GoalScored", "config": {}},
        {"name": "BallProgress", "config": {"robot_id": 1, "weight": 0.5}},
    ])

    def robots(striker_x):
        return {"blue": [
            RobotState(id=0, x=4.0, y=0.0, theta=0.0, vx=0.0, vy=0.0),
            RobotState(id=1, x=striker_x, y=0.0, theta=0.0, vx=0.0, vy=0.0),
        ]}

    far = FrameState(ball=BallState(2.5, 0.0, 0.0, 0.0), robots=robots(1.0))
    closer = FrameState(ball=BallState(2.5, 0.0, 0.0, 0.0), robots=robots(1.5))
    closer_still = FrameState(ball=BallState(2.5, 0.0, 0.0, 0.0), robots=robots(2.0))
    goal = FrameState(ball=BallState(4.6, 0.0, 0.0, 0.0), robots=robots(2.0))

    ctx = MagicMock()
    ctx.scenario_cfg = {}
    ctx.recorder.history = []
    ctx.session.buffer.pull.side_effect = [
        Transition(state=far, next_state=closer, actions={}),
        Transition(state=closer, next_state=closer_still, actions={}),
        Transition(state=closer_still, next_state=goal, actions={}),
    ]

    captured = []
    ctx.recorder.put.side_effect = captured.append

    runner._Runner__run_episode_loop(ctx)

    # First frame has no predecessor to shape against: scalar 0.0.
    assert captured[0].rewards == 0.0
    # Second frame: striker closed 0.5m, weight 0.5 -> +0.25 for robot 1,
    # and 0.0 for the keeper so its reward-key lookup survives.
    assert captured[1].rewards == {0: pytest.approx(0.0), 1: pytest.approx(0.25)}
    # Terminal frame: the goal's scalar +1.0, untouched by shaping.
    assert captured[2].rewards == 1.0


# ─── decision-cadence coalescing (T19) ─────────────────────────────────────────


def _shootout_frames():
    """A striker walking to a ball at x=2.5, frame by frame."""
    from lynch.state.schema import BallState, FrameState, RobotState

    def robots(striker_x):
        return {"blue": [
            RobotState(id=0, x=4.0, y=0.0, theta=0.0, vx=0.0, vy=0.0),
            RobotState(id=1, x=striker_x, y=0.0, theta=0.0, vx=0.0, vy=0.0),
        ]}

    def frame(striker_x, ball_x=2.5):
        return FrameState(
            ball=BallState(ball_x, 0.0, 0.0, 0.0),
            robots=robots(striker_x),
        )

    return frame


@pytest.mark.unit
def test_runner_coalesces_frames_of_one_decision_into_one_transition(runner):
    """With coalesce_frames the recorder sees one (s, a, s') per held
    action, its rewards summed -- not one line per 16ms frame."""
    from lynch.state.schema import BallState, FrameState
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([
        {"name": "GoalScored", "config": {}},
        {"name": "BallProgress", "config": {"robot_id": 1, "weight": 0.5}},
    ])
    frame = _shootout_frames()

    hold = {"striker": [0.1, 0.2, 0.3, 0.4], "goalkeeper": [0.0, 0.0, 0.0, 0.0]}
    other = {"striker": [0.9, 0.2, 0.3, 0.4], "goalkeeper": [0.0, 0.0, 0.0, 0.0]}

    f0, f1, f2, f3 = frame(0.0), frame(0.5), frame(1.0), frame(1.5)
    goal = FrameState(ball=BallState(4.6, 0.0, 0.0, 0.0), robots=f0.robots)

    ctx = MagicMock()
    ctx.scenario_cfg = {"coalesce_frames": True}
    ctx.recorder.history = []
    ctx.session.buffer.pull.side_effect = [
        Transition(state=f0, next_state=f1, actions=hold),
        Transition(state=f1, next_state=f2, actions=hold),
        Transition(state=f2, next_state=f3, actions=hold),
        Transition(state=f3, next_state=goal, actions=other),
    ]

    captured = []
    ctx.recorder.put.side_effect = captured.append

    runner._Runner__run_episode_loop(ctx)

    assert len(captured) == 2

    # Three same-action frames collapse into one record: the first
    # frame's state, the last frame's next_state, the summed shaping.
    # The first frame's scalar 0.0 (no predecessor to shape against)
    # folds into the dict without changing it.
    merged = captured[0]
    assert merged.state is f0
    assert merged.next_state is f3
    assert merged.actions == hold
    assert merged.rewards == {0: pytest.approx(0.0), 1: pytest.approx(0.5)}
    assert merged.done is False

    # The terminal record stands on its own: scalar outcome, done=True.
    assert captured[1].rewards == 1.0
    assert captured[1].done is True


@pytest.mark.unit
def test_runner_coalescing_splits_when_the_action_changes(runner):
    """A new decision starts a new record; and without a shaping
    provider the summed reward stays scalar, like each frame's was."""
    from lynch.state.schema import BallState, FrameState
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([{"name": "GoalScored", "config": {}}])
    frame = _shootout_frames()

    a = {"striker": [0.1, 0.0, 0.0, 0.0]}
    b = {"striker": [0.9, 0.0, 0.0, 0.0]}

    f0, f1, f2, f3, f4 = frame(0.0), frame(0.5), frame(1.0), frame(1.2), frame(1.4)
    goal = FrameState(ball=BallState(4.6, 0.0, 0.0, 0.0), robots=f0.robots)

    ctx = MagicMock()
    ctx.scenario_cfg = {"coalesce_frames": True}
    ctx.recorder.history = []
    ctx.session.buffer.pull.side_effect = [
        Transition(state=f0, next_state=f1, actions=a),
        Transition(state=f1, next_state=f2, actions=a),
        Transition(state=f2, next_state=f3, actions=b),
        Transition(state=f3, next_state=f4, actions=b),
        Transition(state=f4, next_state=goal, actions=b),
    ]

    captured = []
    ctx.recorder.put.side_effect = captured.append

    runner._Runner__run_episode_loop(ctx)

    # Two decisions, then the terminal frame -- which held the same
    # action as the second decision but still gets its own line, or
    # the recorder's score-by-last-line would read shaping as outcome.
    assert len(captured) == 3
    assert captured[0].state is f0 and captured[0].next_state is f2 and captured[0].actions == a
    assert captured[1].state is f2 and captured[1].next_state is f4 and captured[1].actions == b
    assert captured[0].done is False and captured[1].done is False
    # Scalar rewards sum to a scalar: no dict is invented without a
    # shaping provider.
    assert isinstance(captured[0].rewards, float)
    assert captured[0].rewards == pytest.approx(0.0)
    assert captured[2].rewards == 1.0
    assert captured[2].done is True


@pytest.mark.unit
def test_runner_without_coalesce_flag_records_every_frame(runner):
    """The flag is opt-in: by default the recorder still sees one line
    per frame, even when consecutive frames hold the same action."""
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([{"name": "GoalScored", "config": {}}])
    frame = _shootout_frames()

    hold = {"striker": [0.1, 0.0, 0.0, 0.0]}
    f0, f1, f2 = frame(0.0), frame(0.5), frame(1.0)

    ctx = MagicMock()
    ctx.scenario_cfg = {}
    ctx.recorder.history = []
    ctx.session.buffer.pull.side_effect = [
        Transition(state=f0, next_state=f1, actions=hold),
        Transition(state=f1, next_state=f2, actions=hold),
        StopIteration,
    ]

    captured = []
    ctx.recorder.put.side_effect = captured.append

    try:
        runner._Runner__run_episode_loop(ctx)
    except StopIteration:
        pass

    assert len(captured) == 2
    assert captured[0].state is f0 and captured[1].state is f1


# ─── settle after teleport (T14) ─────────────────────────────────────────────

@pytest.mark.unit
def test_runner_waits_for_the_teleport_to_settle(runner):
    """Frames from before the teleport are still in flight when the UDP
    packet is sent, so the order has to be setup -> sleep -> clear -> play."""
    order = []

    runner._Runner__field_manager.setup_scenario.side_effect = \
        lambda *a, **k: order.append("setup_scenario")

    ctx = MagicMock()
    ctx.base_seed = 0
    ctx.template = {}
    ctx.scenario_cfg = {"settle_time": 0.5}
    ctx.session.buffer.clear.side_effect = lambda: order.append("clear")
    ctx.session.connector.send.side_effect = lambda data: order.append("send")
    ctx.recorder.start_scenario.side_effect = lambda *a: order.append("start_scenario")

    with patch("lynch.runner.time.sleep", side_effect=lambda s: order.append(("sleep", s))):
        runner._Runner__arm_episode(ctx, 0)

    filtered = [o for o in order if o != "start_scenario"]
    assert filtered == ["setup_scenario", ("sleep", 0.5), "clear", "send"]


@pytest.mark.unit
def test_runner_settle_time_defaults_to_half_a_second(runner):
    ctx = MagicMock()
    ctx.scenario_cfg = {}
    ctx.session.buffer.clear.side_effect = lambda: None

    with patch("lynch.runner.time.sleep") as mock_sleep:
        runner._Runner__arm_episode(ctx, 0)

    mock_sleep.assert_called_once_with(0.5)


@pytest.mark.unit
def test_runner_episode_loop_times_out_without_frames(runner):
    """With a dead data link the loop used to spin forever, against a
    client-side timeout that could be minutes away."""
    ctx = MagicMock()
    ctx.scenario_cfg = {"frame_timeout": 0.2}
    ctx.session.buffer.pull.return_value = None

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        runner._Runner__run_episode_loop(ctx)
    elapsed = time.monotonic() - started

    assert elapsed < 0.5
