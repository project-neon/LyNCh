import pytest
import threading
import time
import socket
from lynch.state.tcp_connector import TCPConnector

# Mock server that handles simultaneous read/writes
def mock_tcp_server(host, port, stop_event):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(1)
    s.settimeout(1.0)
    try:
        conn, _ = s.accept()
        with conn:
            while not stop_event.is_set():
                # Echo data back or just consume
                data = conn.recv(1024)
                if data:
                    conn.sendall(data)
    except socket.timeout:
        pass
    finally:
        s.close()

@pytest.mark.integration
def test_tcp_connector_bidirectional_safety():
    stop_event = threading.Event()
    # Start server
    threading.Thread(target=mock_tcp_server, args=("127.0.0.1", 10020, stop_event), daemon=True).start()
    time.sleep(0.2)

    connector = TCPConnector(host="127.0.0.1", port=10020)
    connector.connect()

    # Shared flag to ensure no exceptions occurred
    errors = []

    def reader():
        try:
            for _ in range(50):
                connector.receive()
                time.sleep(0.01)
        except Exception as e: 
            errors.append(f"Reader error: {e}")

    def writer():
        try:
            for i in range(50):
                connector.send(f"CMD_{i}".encode())
                time.sleep(0.01)
        except Exception as e: 
            errors.append(f"Writer error: {e}")

    # Fire both threads
    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=writer)
    t1.start(); t2.start()
    t1.join(); t2.join()

    connector.close()
    stop_event.set()

    assert len(errors) == 0, f"Thread safety failure: {errors}"
