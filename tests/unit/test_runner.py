"""Unit tests for lynch/runner.py — each helper tested in isolation."""

import json
from unittest.mock import MagicMock, patch

import pytest

from lynch.runner import Runner


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
    raw = (json.dumps({"scenario_name": "test", "batch_size": 2}) + "\n").encode("utf-8")
    chunks = [bytes([b]) for b in raw]
    sock = MagicMock()
    sock.recv.side_effect = chunks
    result = runner._Runner__receive_command(sock)
    assert result == {"scenario_name": "test", "batch_size": 2}

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
                "scenario_name": "test",
                "config": {"batch_size": 3},
            })
    assert ctx.scenario_name == "test"
    assert ctx.batch_size == 3

@pytest.mark.unit
def test_runner_build_episode_context_missing_scenario_raises(runner):
    with pytest.raises(KeyError):
        runner._Runner__build_episode_context({"scenario_name": "nonexistent"})

@pytest.mark.unit
def test_runner_build_episode_context_missing_scenario_name_raises(runner):
    with pytest.raises(ValueError):
        runner._Runner__build_episode_context({"config": {}})

@pytest.mark.unit
def test_runner_build_episode_context_defaults_batch_size_to_one(runner):
    with patch.object(runner, "_Runner__load_template", return_value={}), \
         patch.object(runner, "_Runner__initialize_session", return_value=MagicMock()):
        with patch("lynch.runner.Recorder"):
            ctx = runner._Runner__build_episode_context({"scenario_name": "test"})
    assert ctx.batch_size == 1


# ─── _arm_episode / _stop_episode ────────────────────────────────────────────

@pytest.mark.unit
def test_runner_arm_episode_sends_start_and_opens_scenario(runner):
    ctx = MagicMock()
    ctx.scenario_cfg = {}
    ctx.scenario_name = "test"
    ctx.base_seed = 10

    runner._Runner__arm_episode(ctx, ep_index=2)

    # seed = base_seed + ep_index = 10 + 2 = 12
    runner._Runner__field_manager.setup_scenario.assert_called_once_with(
        ctx.template, ctx.scenario_cfg, 12
    )
    ctx.session.connector.send.assert_called_once_with(b"START\n")
    ctx.recorder.start_scenario.assert_called_once_with("test", 12)

@pytest.mark.unit
def test_runner_stop_episode_sends_stop_and_closes_scenario(runner):
    ctx = MagicMock()
    runner._Runner__stop_episode(ctx)
    ctx.session.connector.send.assert_called_once_with(b"STOP\n")
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
        {"state": {"ball": {"x": 4.5}}, "next_state": None, "action": {}},
    ]

    terminal_result = MagicMock()
    terminal_result.is_terminal = True
    terminal_result.rewards = {"striker": 1.0, "keeper": -1.0}

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.return_value = terminal_result
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 1

@pytest.mark.unit
def test_runner_run_episode_loop_continues_until_terminal(runner):
    ctx = MagicMock()
    ctx.session.buffer.pull.side_effect = [
        {"state": {"ball": {"x": 0.0}}, "next_state": None, "action": {}},
        {"state": {"ball": {"x": 0.0}}, "next_state": None, "action": {}},
        {"state": {"ball": {"x": 4.5}}, "next_state": None, "action": {}},
    ]

    non_terminal = MagicMock(is_terminal=False, rewards={"striker": 0.0, "keeper": 0.0})
    terminal = MagicMock(is_terminal=True, rewards={"striker": 1.0, "keeper": -1.0})

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.side_effect = [non_terminal, non_terminal, terminal]
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 3

@pytest.mark.unit
def test_runner_run_episode_loop_skips_none_frames(runner):
    ctx = MagicMock()
    terminal = MagicMock(is_terminal=True, rewards={"striker": 1.0, "keeper": -1.0})
    ctx.session.buffer.pull.side_effect = [
        None,
        None,
        {"state": {"ball": {"x": 4.5}}, "next_state": None, "action": {}},
    ]

    with patch("lynch.runner.assessment_registry") as mock_registry, \
         patch("lynch.runner.time.sleep"):
        mock_registry.evaluate.return_value = terminal
        runner._Runner__run_episode_loop(ctx)

    assert mock_registry.evaluate.call_count == 1

@pytest.mark.unit
def test_runner_run_episode_loop_records_transition_per_frame(runner):
    ctx = MagicMock()
    ctx.session.buffer.pull.side_effect = [
        {"state": {"ball": {"x": 0.0}}, "next_state": None, "action": {}},
        {"state": {"ball": {"x": 4.5}}, "next_state": {"ball": {"x": 0.0}}, "action": {}},
    ]

    non_terminal = MagicMock(is_terminal=False, rewards={"striker": 0.0, "keeper": 0.0})
    terminal = MagicMock(is_terminal=True, rewards={"striker": 1.0, "keeper": -1.0})

    with patch("lynch.runner.assessment_registry") as mock_registry:
        mock_registry.evaluate.side_effect = [non_terminal, terminal]
        runner._Runner__run_episode_loop(ctx)

    assert ctx.recorder.put.call_count == 2
    # Verify transition format
    first_call = ctx.recorder.put.call_args_list[0][0][0]
    assert "state" in first_call
    assert "next_state" in first_call
    assert "action" in first_call
    assert "rewards" in first_call


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
    cmd = {"scenario_name": "test", "config": {"batch_size": 1}}
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
