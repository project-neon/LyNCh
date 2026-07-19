import socket
import json
import logging
import random
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from .state.session import initialize_session, Session, DataMode
from .field.manager import Manager
from .result.recorder import Recorder
from .evaluator.registry import assessment_registry

logger = logging.getLogger(__name__)


@dataclass
class EpisodeContext:
    """All objects needed for a single batch of episodes."""

    scenario_name: str
    template: Dict[str, Any]
    scenario_cfg: Dict[str, Any]
    assessments: List[str]
    session: Session
    recorder: Recorder
    batch_size: int
    base_seed: int


class Runner:
    """Master orchestrator for LyNCh.

    Coordinates networking, field setup, evaluation, and logging.
    """

    def __init__(self, config_path: str, mode: str) -> None:
        self.__config_path = Path(config_path)
        self.__mode = DataMode[mode.upper()]
        self.__config: Dict = {}
        self.__scenarios_config: Dict = {}
        self.__field_manager = Manager()
        self.__shutdown_event = threading.Event()
        self.__server_socket: Optional[socket.socket] = None

        self.__load_config()
        runner_cfg = self.__config.get("runner", {})
        self.__host = runner_cfg.get("host", "127.0.0.1")
        self.__port = runner_cfg.get("port", 10003)

    def close(self) -> None:
        """Signal shutdown and release resources."""
        self.__shutdown_event.set()
        self.__field_manager.close()
        if self.__server_socket:
            self.__server_socket.close()
            self.__server_socket = None

    def serve_forever(self) -> None:
        """Start the TCP server and block forever."""
        self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__server_socket.bind((self.__host, self.__port))
        self.__server_socket.listen(5)
        self.__server_socket.settimeout(0.5)

        logger.info(f"Runner listening on {self.__host}:{self.__port}")

        while not self.__shutdown_event.is_set():
            try:
                conn, addr = self.__server_socket.accept()
                logger.info(f"Accepted connection from {addr}")
                self.__handle_client(conn)
            except socket.timeout:
                continue
            except OSError:
                break

        self.close()

    def __handle_client(self, conn: socket.socket) -> None:
        """Handle a single RL-Engine session."""
        try:
            with conn:
                command = self.__receive_command(conn)
                result = self.__handle_batch(command)
                self.__send_response(conn, result)
        except Exception as e:
            logger.error(f"Error handling client: {e}")
            try:
                self.__send_response(conn, {"status": "error", "message": str(e)})
            except OSError:
                pass

    def __handle_batch(self, command: Dict) -> dict:
        """Orchestrate the complete batch lifecycle."""
        ctx = self.__build_episode_context(command)

        # Connect control connector (for sending metadata/START/STOP)
        ctx.session.connector.connect()

        # Send metadata to NeonFC control
        metadata = command.get("metadata", {})
        if metadata:
            ctx.session.connector.send(json.dumps(metadata).encode())

        # Start the State Buffer thread (once per batch)
        ctx.session.buffer.start()

        try:
            # Load assessments
            assessment_registry.load(ctx.assessments)

            # Execute episodes
            history_files = self.__execute_batch(ctx)
        finally:
            # Stop the State Buffer thread (once per batch)
            ctx.session.buffer.stop()

        # Summarize batch
        summary_file = ctx.recorder.summarize_batch()

        return {
            "status": "success",
            "history_files": history_files,
            "summary_file": summary_file,
        }

    def __build_episode_context(self, command: Dict) -> EpisodeContext:
        """Build the context for a single batch."""
        scenario_name = command.get("scenario_name")
        if not scenario_name:
            raise ValueError("Missing 'scenario_name' in command")

        if scenario_name not in self.__scenarios_config:
            raise KeyError(f"Scenario '{scenario_name}' is not configured")

        scenario_cfg = self.__scenarios_config[scenario_name]
        template_path = scenario_cfg.get("template", "")
        template = self.__load_template(template_path)

        session = self.__initialize_session()

        config = command.get("config", {})
        batch_size = config.get("batch_size", 1)
        output_dir = config.get("output_dir", f"results/{scenario_name}")
        recorder = Recorder(dir_path=output_dir)

        return EpisodeContext(
            scenario_name=scenario_name,
            template=template,
            scenario_cfg=scenario_cfg,
            assessments=scenario_cfg.get("assessments", []),
            session=session,
            recorder=recorder,
            batch_size=batch_size,
            base_seed=random.randint(0, 2**31 - 1),
        )

    def __execute_batch(self, ctx: EpisodeContext) -> List[str]:
        """Run N episodes and collect history file paths."""
        history_files = []
        for ep_index in range(ctx.batch_size):
            path = self.__execute_single_episode(ctx, ep_index)
            if path is not None:
                history_files.append(path)
        return history_files

    def __execute_single_episode(self, ctx: EpisodeContext, ep_index: int) -> Optional[str]:
        """Run one episode: arm → loop → stop."""
        try:
            self.__arm_episode(ctx, ep_index)
            self.__run_episode_loop(ctx)
            return self.__stop_episode(ctx)
        except Exception as e:
            logger.error(f"Episode {ep_index} failed: {e}")
            return None

    def __arm_episode(self, ctx: EpisodeContext, ep_index: int) -> None:
        """Reset field and send START signal."""
        seed = ctx.base_seed + ep_index
        self.__field_manager.setup_scenario(ctx.template, ctx.scenario_cfg, seed)
        
        # Clear any leftover frames from previous episodes
        ctx.session.buffer.clear()
        
        ctx.session.connector.send(b"START\n")
        ctx.recorder.start_scenario(ctx.scenario_name, seed)

    def __run_episode_loop(self, ctx: EpisodeContext) -> None:
        """Pull frames, evaluate, record until terminal."""
        logger.info(f"Starting episode loop. Loaded assessments: {[type(a).__name__ for a in assessment_registry._loaded]}")

        while not self.__shutdown_event.is_set():
            frame = ctx.session.buffer.pull()
            if frame is None:
                time.sleep(0.001)
                continue

            result = assessment_registry.evaluate(frame["state"], ctx.recorder.history)
            transition = {
                "state": frame["state"],
                "next_state": frame.get("next_state"),
                "action": frame.get("action"),
                "rewards": result.rewards,
            }
            ctx.recorder.put(transition)

            if result.is_terminal:
                logger.info(f"Episode terminated. Reason: {result.reason}")
                break

    def __stop_episode(self, ctx: EpisodeContext) -> Optional[str]:
        """Send STOP signal and close recorder. Returns the closed file path."""
        try:
            ctx.session.connector.send(b"STOP\n")
        except OSError as e:
            logger.warning(f"Failed to send STOP: {e}")
        return ctx.recorder.end_scenario()

    def __receive_command(self, conn: socket.socket) -> dict:
        """Read line-delimited JSON from socket."""
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by client")
            data += chunk
        return json.loads(data.decode("utf-8").strip())

    def __send_response(self, conn: socket.socket, data: dict) -> None:
        """Send line-delimited JSON to socket."""
        payload = json.dumps(data).encode("utf-8") + b"\n"
        conn.sendall(payload)

    def __load_template(self, path: str) -> Dict:
        """Load a YAML or JSON template file."""
        template_path = Path(path)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {path}")

        with open(template_path, "r", encoding="utf-8") as f:
            if template_path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(f)
            elif template_path.suffix == ".json":
                return json.load(f)
            else:
                raise ValueError(f"Unsupported template format: {template_path.suffix}")

    def __initialize_session(self) -> Session:
        """Create a State session for the configured mode."""
        mode_cfg = self.__config.get(self.__mode.name, {})
        common_host = mode_cfg.get("host", "127.0.0.1")

        if self.__mode == DataMode.NEONFC:
            return initialize_session(
                mode=self.__mode,
                neon_host=common_host,
                data_port=mode_cfg.get("data_port", 10001),
                control_port=mode_cfg.get("control_port", 10002),
            )
        else:  # DIRECT
            return initialize_session(
                mode=self.__mode,
                neon_host=common_host,
                vision_host=mode_cfg.get("host", "224.5.23.2"),
                vision_port=int(mode_cfg.get("port", 10010)),
            )

    def __load_config(self) -> None:
        """Load the YAML configuration file."""
        if not self.__config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.__config_path}")

        with open(self.__config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.__config = config.get("network", {})
        self.__scenarios_config = config.get("scenarios", {})


def main() -> None:
    """CLI entry point for the LyNCh daemon."""
    import argparse

    # Configure logging to output to console
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="LyNCh daemon")
    parser.add_argument(
        "config",
        nargs="?",
        default="test_config.yaml",
        help="Path to config YAML (default: test_config.yaml)",
    )
    parser.add_argument(
        "--mode",
        default="NEONFC",
        choices=["NEONFC", "DIRECT"],
        help="Connection mode (default: NEONFC)",
    )
    args = parser.parse_args()

    runner = Runner(config_path=args.config, mode=args.mode)

    def shutdown(signum, frame):
        runner.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    runner.serve_forever()


if __name__ == "__main__":
    main()
