import socket
from typing import Dict, List, Tuple

# Clean imports using the newly compiled protocols
from protocols.sim.ssl_simulation_control_pb2 import SimulatorCommand
from protocols.gc.ssl_gc_common_pb2 import YELLOW, BLUE

class ManualSimControl:
    """
    Direct interface to the simulator using the simcli protocol.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 10300):
        self.target = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_teleport(self, ball_xyz: Tuple[float, float, float], yellow_poses: List[Dict], blue_poses: List[Dict], speed: float = 1.0):
        """
        Creates and sends a SimulatorCommand packet.
        - Robots 0-5: present=True
        - Robots 7-10: present=False
        - Ball: teleport_safely=True
        - speed: sets the simulation speed multiplier
        """
        packet = SimulatorCommand()
        ctrl = packet.control
        
        # 0. Speed Control
        ctrl.simulation_speed = speed

        # 1. Ball Teleport (Safe)
        ctrl.teleport_ball.x = ball_xyz[0]
        ctrl.teleport_ball.y = ball_xyz[1]
        ctrl.teleport_ball.z = ball_xyz[2]
        ctrl.teleport_ball.teleport_safely = True

        # 2. Robot Management
        for team_color, poses in [(YELLOW, yellow_poses), (BLUE, blue_poses)]:
            pose_map = {p["id"]: p for p in poses}
            
            # IDs 0 to 10
            for r_id in range(11):
                rob = ctrl.teleport_robot.add()
                rob.id.id = r_id
                rob.id.team = team_color
                
                if r_id <= 5:
                    # IDs 0-5: Present
                    rob.present = True
                    data = pose_map.get(r_id)
                    if data:
                        rob.x = data.get("x", 0.0)
                        rob.y = data.get("y", 0.0)
                        rob.orientation = data.get("theta", 0.0)
                    else:
                        # Present but no specific pose: Move off-field
                        rob.x = -10.0 if team_color == BLUE else 10.0
                        rob.y = float(r_id)
                elif r_id >= 7:
                    # IDs 7-10: Absent
                    rob.present = False
                else:
                    # ID 6: Not specified, hiding to be consistent
                    rob.present = False

        self.sock.sendto(packet.SerializeToString(), self.target)

def main():
    ctrl = ManualSimControl()
    
    presets = [
        {
            "name": "Full Squad Kick-off",
            "ball": (0, 0, 0),
            "yellow": [
                {"id": 0, "x": 0.5, "y": 0, "theta": 3.14},
                {"id": 1, "x": 1.5, "y": 1, "theta": 3.14},
                {"id": 2, "x": 1.5, "y": -1, "theta": 3.14},
                {"id": 3, "x": 3.0, "y": 2, "theta": 3.14},
                {"id": 4, "x": 3.0, "y": -2, "theta": 3.14},
                {"id": 5, "x": 5.0, "y": 0, "theta": 3.14}
            ],
            "blue": [
                {"id": 0, "x": -0.5, "y": 0, "theta": 0},
                {"id": 1, "x": -1.5, "y": 1, "theta": 0},
                {"id": 2, "x": -1.5, "y": -1, "theta": 0},
                {"id": 3, "x": -3.0, "y": 2, "theta": 0},
                {"id": 4, "x": -3.0, "y": -2, "theta": 0},
                {"id": 5, "x": -5.0, "y": 0, "theta": 0}
            ]
        },
        {
            "name": "Penalty (All Pushed to Sidelines)",
            "ball": (-4, 0, 0),
            "yellow": [
                {"id": 0, "x": 5, "y": 0, "theta": 3.14}, # Keeper
                {"id": 1, "x": 0, "y": 4, "theta": 3.14},
                {"id": 2, "x": 1, "y": 4, "theta": 3.14},
                {"id": 3, "x": 2, "y": 4, "theta": 3.14},
                {"id": 4, "x": 0, "y": -4, "theta": 3.14},
                {"id": 5, "x": 1, "y": -4, "theta": 3.14}
            ],
            "blue": [
                {"id": 0, "x": -6, "y": 0, "theta": 0}, # Striker
                {"id": 1, "x": 0, "y": 3.5, "theta": 0},
                {"id": 2, "x": 1, "y": 3.5, "theta": 0},
                {"id": 3, "x": 2, "y": 3.5, "theta": 0},
                {"id": 4, "x": 0, "y": -3.5, "theta": 0},
                {"id": 5, "x": 1, "y": -3.5, "theta": 0}
            ]
        },
        {
            "name": "Mid-field Grid",
            "ball": (0, 0, 0),
            "yellow": [{"id": i, "x": 1.0, "y": float(i)-2.5, "theta": 3.14} for i in range(6)],
            "blue": [{"id": i, "x": -1.0, "y": float(i)-2.5, "theta": 0} for i in range(6)]
        }
    ]

    print("\n--- Hawk Simulation Control Tester ---")
    print("Target: 127.0.0.1:10300")
    print("Rules: IDs 0-5 Present, 7-10 Absent, Safe Teleport: ON")
    
    current_speed = 1.0

    # Map letters to preset indices
    preset_map = {"a": 0, "b": 1, "c": 2}

    print("\nAvailable Presets:")
    for char, idx in preset_map.items():
        print(f"{char}: {presets[idx]['name']}")
    
    print("\nControls:")
    print("Letters [a-c]: Trigger Teleport Preset")
    print("Numbers [1-9]: Set Simulation Speed Multiplier")
    print("Press Ctrl+C to exit.")

    try:
        while True:
            print(f"\n[Current Speed: {current_speed}x]")
            choice = input("Enter choice: ").strip().lower()
            
            if choice in preset_map:
                data = presets[preset_map[choice]]
                print(f"Teleporting to '{data['name']}' at {current_speed}x speed...")
                ctrl.send_teleport(data["ball"], data["yellow"], data["blue"], speed=current_speed)
                print("Command sent.")
                
            elif choice.isdigit():
                current_speed = float(choice)
                print(f"Simulation speed set to {current_speed}x")
                
            else:
                print("Invalid choice. Use a/b/c for scenarios or 1-9 for speed.")
                
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")

if __name__ == "__main__":
    main()
