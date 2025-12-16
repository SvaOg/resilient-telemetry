import subprocess
import time
import random
import signal
import os
import sys

# Configuration
SERVER_CMD = ["uv", "run", "uvicorn", "main:app", "--port", "8000"]
MIN_UP_TIME = 5  # Seconds server stays ALIVE
MAX_UP_TIME = 10
MIN_DOWN_TIME = 3  # Seconds server stays DEAD
MAX_DOWN_TIME = 8


def start_server():
    """Starts the Uvicorn server as a subprocess."""
    print(f"[CHAOS] Bringing HQ Online...")
    # process_group=True allows us to kill the whole tree (uv + uvicorn)
    if sys.platform == "win32":
        return subprocess.Popen(
            SERVER_CMD, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        return subprocess.Popen(SERVER_CMD, preexec_fn=os.setsid)


def stop_server(proc):
    """Kills the server subprocess."""
    print(f"[CHAOS] Killing HQ! (Simulating Network Failure)")
    if sys.platform == "win32":
        proc.send_signal(signal.CTRL_BREAK_EVENT)
        proc.kill()
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

    proc.wait()  # Ensure it's dead


def main():
    print("Chaos Monkey initialized. Controlling HQ server...")

    server_process = None

    try:
        while True:
            # 1. Start Server
            server_process = start_server()

            # 2. Let it run for random time
            duration = random.randint(MIN_UP_TIME, MAX_UP_TIME)
            time.sleep(duration)

            # 3. Kill Server
            stop_server(server_process)
            server_process = None

            # 4. Wait for random time (downtime)
            duration = random.randint(MIN_DOWN_TIME, MAX_DOWN_TIME)
            print(f"[CHAOS] Network down for {duration}s...")
            time.sleep(duration)

    except KeyboardInterrupt:
        print("\nStopping Chaos Monkey...")
        if server_process:
            stop_server(server_process)


if __name__ == "__main__":
    main()