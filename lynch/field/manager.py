import socket
import logging
from typing import Dict, Optional
from protocols.sim.grSim_Packet_pb2 import grSim_Packet
from protocols.sim.grSim_Replacement_pb2 import grSim_Replacement

logger = logging.getLogger(__name__)
from .variance import (
    NoVariance,
    UniformRandomVariance,
    GaussianRandomVariance
)

GRSIM_HOST = "127.0.0.1"
GRSIM_PORT = 20011
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
        repl = grSim_Replacement()

        ball = positions.get("ball", {})
        repl.ball.x = ball.get("x", 0.0)
        repl.ball.y = ball.get("y", 0.0)

        for team_color, is_yellow in [("blue", False), ("yellow", True)]:
            team_data = positions.get("robots", {}).get(team_color, [])
            for robot in team_data:
                if not isinstance(robot, dict):
                    logger.warning(f"Skipping non-dict robot entry for {team_color}")
                    continue
                rob = repl.robots.add()
                rob.id = robot.get("id", 0)
                rob.x = robot.get("x", 0.0)
                rob.y = robot.get("y", 0.0)
                rob.dir = robot.get("theta", 0.0)
                rob.yellowteam = is_yellow
                rob.turnon = True

        packet = grSim_Packet()
        packet.replacement.CopyFrom(repl)

        try:
            self.__socket.sendto(
                packet.SerializeToString(),
                (GRSIM_HOST, GRSIM_PORT)
            )
        except Exception as e:
            logger.error(f"Failed to send to grSim: {e}")

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
