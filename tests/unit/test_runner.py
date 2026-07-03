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
        "    signal_port: 10002\n"
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

class TestReceiveCommand:
    def test_reads_full_json_command(self, runner):
        raw = (json.dumps({"scenario_name": "test", "batch_size": 2}) + "\n").encode("utf-8")
        chunks = [bytes([b]) for b in raw]
        sock = MagicMock()
        sock.recv.side_effect = chunks
        result = runner._Runner__receive_command(sock)
        assert result == {"scenario_name": "test", "batch_size": 2}

    def test_empty_payload_raises(self, runner):
        sock = MagicMock()
        sock.recv.return_value = b""
        with pytest.raises(ConnectionError):
            runner._Runner__receive_command(sock)


# ─── _send_response ───────────────────────────────────────────────────────────

class TestSendResponse:
    def test_sends_newline_terminated_json(self, runner):
        sock = MagicMock()
        payload = {"status": "success", "history_files": []}
        runner._Runner__send_response(sock, payload)
        sent = sock.sendall.call_args[0][0].decode("utf-8")
        assert sent.endswith("\n")
        assert json.loads(sent.strip()) == payload


# ─── _load_template ───────────────────────────────────────────────────────────

class TestLoadTemplate:
    def test_loads_yaml_template(self, runner, tmp_path):
        tmpl = tmp_path / "template.yaml"
        tmpl.write_text("ball:\n  x: 0.0\n  y: 0.0\n")
        result = runner._Runner__load_template(str(tmpl))
        assert result["ball"]["x"] == 0.0

    def test_loads_json_template(self, runner, tmp_path):
        tmpl = tmp_path / "template.json"
        tmpl.write_text('{"ball": {"x": 1.0}}')
        result = runner._Runner__load_template(str(tmpl))
        assert result["ball"]["x"] == 1.0

    def test_missing_file_raises(self, runner):
        with pytest.raises(FileNotFoundError):
            runner._Runner__load_template("/nonexistent/template.yaml")


# ─── _build_episode_context ───────────────────────────────────────────────────

class TestBuildEpisodeContext:
    def test_resolves_scenario(self, runner):
        with patch.object(runner, "_Runner__load_template", return_value={"ball": {}}), \
             patch.object(runner, "_Runner__initialize_session", return_value=MagicMock()):
            with patch("lynch.runner.Recorder"):
                ctx = runner._Runner__build_episode_context({
                    "scenario_name": "test",
                    "config": {"batch_size": 3},
                })
        assert ctx.scenario_name == "test"
        assert ctx.batch_size == 3

    def test_missing_scenario_raises(self, runner):
        with pytest.raises(KeyError):
            runner._Runner__build_episode_context({"scenario_name": "nonexistent"})

    def test_missing_scenario_name_raises(self, runner):
        with pytest.raises(ValueError):
            runner._Runner__build_episode_context({"config": {}})

    def test_defaults_batch_size_to_one(self, runner):
        with patch.object(runner, "_Runner__load_template", return_value={}), \
             patch.object(runner, "_Runner__initialize_session", return_value=MagicMock()):
            with patch("lynch.runner.Recorder"):
                ctx = runner._Runner__build_episode_context({"scenario_name": "test"})
        assert ctx.batch_size == 1


# ─── _arm_episode / _stop_episode ────────────────────────────────────────────

class TestArmStopEpisode:
    def test_arm_sends_start_and_opens_scenario(self, runner):
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

    def test_stop_sends_stop_and_closes_scenario(self, runner):
        ctx = MagicMock()
        runner._Runner__stop_episode(ctx)
        ctx.session.connector.send.assert_called_once_with(b"STOP\n")
        ctx.recorder.end_scenario.assert_called_once()

    def test_stop_tolerates_send_failure(self, runner):
        ctx = MagicMock()
        ctx.session.connector.send.side_effect = OSError("broken pipe")
        runner._Runner__stop_episode(ctx)  # should not raise
        ctx.recorder.end_scenario.assert_called_once()


# ─── _run_episode_loop ────────────────────────────────────────────────────────

class TestRunEpisodeLoop:
    def test_breaks_on_terminal_result(self, runner):
        ctx = MagicMock()
        ctx.session.buffer.pull.side_effect = [
            {"state": {"ball": {"x": 4.5}}, "prev_state": None, "action": {}},
        ]

        terminal_result = MagicMock()
        terminal_result.is_terminal = True
        terminal_result.rewards = {"striker": 1.0, "keeper": -1.0}

        with patch("lynch.runner.assessment_registry") as mock_registry:
            mock_registry.evaluate.return_value = terminal_result
            runner._Runner__run_episode_loop(ctx)

        assert mock_registry.evaluate.call_count == 1

    def test_continues_until_terminal(self, runner):
        ctx = MagicMock()
        ctx.session.buffer.pull.side_effect = [
            {"state": {"ball": {"x": 0.0}}, "prev_state": None, "action": {}},
            {"state": {"ball": {"x": 0.0}}, "prev_state": None, "action": {}},
            {"state": {"ball": {"x": 4.5}}, "prev_state": None, "action": {}},
        ]

        non_terminal = MagicMock(is_terminal=False, rewards={"striker": 0.0, "keeper": 0.0})
        terminal = MagicMock(is_terminal=True, rewards={"striker": 1.0, "keeper": -1.0})

        with patch("lynch.runner.assessment_registry") as mock_registry:
            mock_registry.evaluate.side_effect = [non_terminal, non_terminal, terminal]
            runner._Runner__run_episode_loop(ctx)

        assert mock_registry.evaluate.call_count == 3

    def test_skips_none_frames(self, runner):
        ctx = MagicMock()
        terminal = MagicMock(is_terminal=True, rewards={"striker": 1.0, "keeper": -1.0})
        ctx.session.buffer.pull.side_effect = [
            None,
            None,
            {"state": {"ball": {"x": 4.5}}, "prev_state": None, "action": {}},
        ]

        with patch("lynch.runner.assessment_registry") as mock_registry, \
             patch("lynch.runner.time.sleep"):
            mock_registry.evaluate.return_value = terminal
            runner._Runner__run_episode_loop(ctx)

        assert mock_registry.evaluate.call_count == 1

    def test_records_transition_per_frame(self, runner):
        ctx = MagicMock()
        ctx.session.buffer.pull.side_effect = [
            {"state": {"ball": {"x": 0.0}}, "prev_state": None, "action": {}},
            {"state": {"ball": {"x": 4.5}}, "prev_state": {"ball": {"x": 0.0}}, "action": {}},
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
        assert "prev_state" in first_call
        assert "action" in first_call
        assert "rewards" in first_call


# ─── _execute_batch ───────────────────────────────────────────────────────────

class TestExecuteBatch:
    def test_runs_correct_number_of_episodes(self, runner):
        ctx = MagicMock()
        ctx.batch_size = 4

        with patch.object(runner, "_Runner__execute_single_episode", return_value="/tmp/ep.jsonl") as mock_ep:
            paths = runner._Runner__execute_batch(ctx)

        assert mock_ep.call_count == 4
        assert len(paths) == 4

    def test_none_path_excluded(self, runner):
        ctx = MagicMock()
        ctx.batch_size = 3

        with patch.object(runner, "_Runner__execute_single_episode", side_effect=["/tmp/a.jsonl", None, "/tmp/b.jsonl"]):
            paths = runner._Runner__execute_batch(ctx)

        assert paths == ["/tmp/a.jsonl", "/tmp/b.jsonl"]


# ─── _handle_client ───────────────────────────────────────────────────────────

class TestHandleClient:
    def test_success_flow(self, runner):
        cmd = {"scenario_name": "test", "config": {"batch_size": 1}}
        batch_result = {"status": "success", "history_files": [], "summary_file": "/s.json"}

        mock_conn = MagicMock()
        with patch.object(runner, "_Runner__receive_command", return_value=cmd), \
             patch.object(runner, "_Runner__handle_batch", return_value=batch_result), \
             patch.object(runner, "_Runner__send_response") as mock_send:
            runner._Runner__handle_client(mock_conn)

        mock_send.assert_called_once_with(mock_conn, batch_result)

    def test_exception_sends_error_response(self, runner):
        mock_conn = MagicMock()
        with patch.object(runner, "_Runner__receive_command", side_effect=ValueError("bad input")), \
             patch.object(runner, "_Runner__send_response") as mock_send:
            runner._Runner__handle_client(mock_conn)

        response = mock_send.call_args[0][1]
        assert response["status"] == "error"
        assert "bad input" in response["message"]
