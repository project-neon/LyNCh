import json
import socket
import pathlib
from typing import Dict
from protocols.grSim.grSim_Packet_pb2 import grSim_Packet
from protocols.grSim.grSim_Replacement_pb2 import grSim_Replacement
from . import DeterministicVariance

GRSIM_HOST = "127.0.0.1"
GRSIM_PORT = 20011
STRATEGIES = {
    "deterministic": DeterministicVariance,
}

_SELF_DIR = pathlib.Path(__file__).parent.resolve()
_ROOT_DIR = _SELF_DIR.parent.parent
DEFAULT_PATH = str(_ROOT_DIR / "scenarios" / "test_config.json")

class EnvManager:
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
    def _apply_strategy(baseline: Dict, variance: Dict | None, strategy: str) -> Dict:
        strg = STRATEGIES[strategy]()
        return strg.apply(baseline, variance)

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

        base_path = scenario_config["baseline_file"]
        variance_config = scenario_config["variance"]
        strategy = scenario_config["strategy"]

        baseline = self._load_file(str(_ROOT_DIR / base_path))
        noisy_pos = self._apply_strategy(baseline, variance_config, strategy)
        self._send_replacement(noisy_pos)


if __name__ == "__main__":
    print("\n--- Hawk Manual Tester ---")
    
    # Use the manual test config by default if it exists, otherwise use standard
    manual_config = _ROOT_DIR / "scenarios" / "manual_test_config.json"
    config_to_use = str(manual_config) if manual_config.exists() else DEFAULT_PATH
    
    try:
        manager = EnvManager(config_path=config_to_use)
    except Exception as e:
        print(f"Error initializing EnvManager: {e}")
        exit(1)

    print(f"Loaded config: {config_to_use}")
    print("\nAvailable Position Options:")
    print("1: Center-line Spread")
    print("2: Diagonal Offset")
    print("3: Vertical Split")
    print("\nPress Ctrl+C to exit.")

    options = {
        "1": "option_1",
        "2": "option_2",
        "3": "option_3"
    }

    try:
        while True:
            choice = input("\nSelect position [1-3]: ").strip()
            
            scenario_id = options.get(choice)
            if scenario_id:
                print(f"Teleporting entities to {scenario_id}...")
                manager.setup_scenario(scenario_id)
                print("Command sent to grSim.")
            else:
                print("Invalid option. Please choose 1, 2, or 3.")
                
    except KeyboardInterrupt:
        print("\n\nExiting Hawk Tester. Goodbye!")
