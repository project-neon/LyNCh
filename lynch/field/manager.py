import socket
import logging
from typing import Dict, Optional
from protocols.sim.ssl_simulation_control_pb2 import SimulatorCommand
from protocols.gc.ssl_gc_common_pb2 import BLUE, YELLOW

from .variance import (
    NoVariance,
    UniformRandomVariance,
    GaussianRandomVariance
)

logger = logging.getLogger(__name__)

SIM_HOST = "127.0.0.1"
SIM_PORT = 10300
SIM_SPEED = 1.0
STRATEGIES = {
    "no_variance": NoVariance,
    "uniform_random": UniformRandomVariance,
    "gaussian_random": GaussianRandomVariance,
}


class Manager:
    def __init__(self):
        self.__socket = self._create_socket()

    def __del__(self):
        if hasattr(self, "_Manager__socket") and self.__socket:
            self.__socket.close()

    @staticmethod
    def _create_socket() -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return sock

    @staticmethod
    def _apply_strategy(
            template: Dict,
            variance: Optional[Dict],
            strategy: str,
            seed: Optional[int] = None
    ) -> Dict:
        if strategy not in STRATEGIES:
            raise KeyError(f"Unknown variance strategy '{strategy}'. Valid: {list(STRATEGIES.keys())}")
        strg = STRATEGIES[strategy](seed=seed)
        return strg.apply(template, variance)

    def _send_replacement(self, positions: Dict):
        packet = SimulatorCommand()
        ctrl = packet.control

        ctrl.simulation_speed = SIM_SPEED

        # Ball Teleport
        ball = positions.get("ball", {})
        ctrl.teleport_ball.x = ball.get("x", 0.0)
        ctrl.teleport_ball.y = ball.get("y", 0.0)
        ctrl.teleport_ball.z = 0.0
        ctrl.teleport_ball.teleport_safely = True

        # Robot Teleport (All Blue)
        robots = positions.get("robots", {}).get("blue", [])
        for robot_data in robots:
            if not isinstance(robot_data, dict) or "id" not in robot_data:
                logger.warning(f"Skipping malformed robot entry: {robot_data}")
                continue
                
            rob = ctrl.teleport_robot.add()
            rob.id.id = robot_data.get("id", 0)
            rob.id.team = BLUE
            rob.present = True
            rob.x = robot_data.get("x", 0.0)
            rob.y = robot_data.get("y", 0.0)
            rob.orientation = robot_data.get("theta", 0.0)

        try:
            self.__socket.sendto(
                packet.SerializeToString(),
                (SIM_HOST, SIM_PORT)
            )
        except Exception as e:
            logger.error(f"Failed to send to sim: {e}")

    def setup_scenario(self, template: Dict, scenario_config: Dict, seed: Optional[int] = None):
        variance_config = scenario_config.get("variance", {})
        strategy = scenario_config.get("strategy", "no_variance")

        noisy_pos = self._apply_strategy(template, variance_config, strategy, seed)
        self._send_replacement(noisy_pos)

    def close(self):
        """Close the UDP socket. Call when done to release the file descriptor."""
        if hasattr(self, "_Manager__socket") and self.__socket:
            self.__socket.close()
            self.__socket = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
