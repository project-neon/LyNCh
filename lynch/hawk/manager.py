import json
import socket
from . import DeterministicVariance

GRSIM_HOST = "127.0.0.1"
GRSIM_PORT = 20011
STRATEGIES = {
    "deterministic": DeterministicVariance,
}

class EnvManager:
    def __init__(self, config_path):

        with open(config_path, "r") as f:
            config = json.load(f)
        self.scenarios = config.get("scenarios")

        self.socket = self._create_socket()

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return sock

    def _get_baseline(self, file_path):
        ...

    def _apply_strategy(self, baseline, strategy):
        ...

    def _send_replacement(self):
        """
        WIP
        """

        packet = ...
        try:
            self.socket.sendto(packet, (GRSIM_HOST, GRSIM_PORT))
        except Exception as e:
            print(f"Failed to send to grSim: {e}")

    def setup_scenario(self, scenario_id):
        ...