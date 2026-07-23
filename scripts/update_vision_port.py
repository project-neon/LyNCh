import socket
import sys

from protocols.sim.ssl_simulation_control_pb2 import SimulatorCommand

def send_vision_port_update(port: int, host: str = "127.0.0.1", sim_port: int = 10300):
    """
    Sends a SimulatorCommand to change the vision publish port.
    """
    target = (host, sim_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Build the command
    cmd = SimulatorCommand()
    # Populate the config.vision_port field
    cmd.config.vision_port = port
    
    print(f"Sending vision port update: {port} to {host}:{sim_port}...")
    try:
        sock.sendto(cmd.SerializeToString(), target)
        print("Success: Update packet sent.")
    except Exception as e:
        print(f"Error: Could not send update: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    print("\n--- Simulator Vision Port Updater ---")
    
    try:
        if len(sys.argv) > 1:
            new_port = int(sys.argv[1])
        else:
            choice = input("Enter new vision port [default 10006]: ").strip()
            new_port = int(choice) if choice else 10006
            
        send_vision_port_update(new_port)
        
    except ValueError:
        print("Invalid port number. Please provide an integer.")
    except KeyboardInterrupt:
        print("\nExiting.")
