import json
import socket
import pathlib
from typing import Dict
from protocols.sim.grSim_Packet_pb2 import grSim_Packet
from protocols.sim.grSim_Replacement_pb2 import grSim_Replacement
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

_SELF_DIR = pathlib.Path(__file__).parent.resolve()
_ROOT_DIR = _SELF_DIR.parent.parent
DEFAULT_PATH = str(_ROOT_DIR / "scenarios" / "profiles" / "test_config.json")

class Manager:
    def __init__(self, config_path: str=DEFAULT_PATH):
        config = self._load_file(config_path)
        self.scenarios = config["scenarios"]

        self.socket = self._create_socket()

    def __del__(self):
        if hasattr(self, "socket") and self.socket:
            self.socket.close()

    @staticmethod
    def _create_socket() -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return sock

    @staticmethod
    def _load_file(file_path: str) -> Dict:
        with open(file_path, "r") as f:
            result = json.load(f)
        return result

    @staticmethod
    def _apply_strategy(template: Dict, variance: Dict | None, strategy: str) -> Dict:
        strg = STRATEGIES[strategy]()
        return strg.apply(template, variance)

    def _send_replacement(self, positions: Dict):
        repl = grSim_Replacement()

        repl.ball.x = positions["ball"]["x"]
        repl.ball.y = positions["ball"]["y"]

        for team_color, is_yellow in [("blue", False), ("yellow", True)]:
            team_data = positions["robots"].get(team_color, [])
            for robot in team_data:
                rob = repl.robots.add()
                rob.id = robot["id"]
                rob.x = robot["x"]
                rob.y = robot["y"]
                rob.dir = robot["theta"]
                rob.yellowteam = is_yellow
                rob.turnon = True

        packet = grSim_Packet()
        packet.replacement.CopyFrom(repl)

        try:
            self.socket.sendto(
                packet.SerializeToString(),
                (GRSIM_HOST, GRSIM_PORT)
            )
        except Exception as e:
            print(f"Failed to send to grSim: {e}")

    def setup_scenario(self, scenario_id):
        scenario_config = self.scenarios.get(scenario_id)

        tmpl_path = scenario_config["template"]
        variance_config = scenario_config["variance"]
        strategy = scenario_config["strategy"]

        template = self._load_file(str(_ROOT_DIR / tmpl_path))
        noisy_pos = self._apply_strategy(template, variance_config, strategy)
        self._send_replacement(noisy_pos)
