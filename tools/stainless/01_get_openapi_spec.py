from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import requests
from requests.exceptions import ConnectionError

WEAVE_PORT = 6345


def kill_port(port: int) -> None:
    """Kill any process listening on the specified port."""
    try:
        # Find PIDs using the port and kill them
        print("Killing server port pids...")
        cmd = f"lsof -i TCP:{port} | awk '{{print $2}}' | grep -E '[0-9]+' | xargs -t kill -9"
        subprocess.check_output(cmd, shell=True, text=True)
    except subprocess.CalledProcessError:
        return  # No processes found on that port


def wait_for_server(url: str, timeout: int = 30, interval: int = 1) -> bool:
    """Wait for server to become available"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            requests.get(url)
        except ConnectionError:
            print("Failed to connect to server, retrying...")
            time.sleep(interval)
        else:
            print("Server is healthy!")
            return True
    return False


def get_openapi_spec(server_dir: str, output_file: str | None = None) -> None:
    original_dir = os.getcwd()
    if output_file is None:
        output_file = os.path.join(original_dir, "tools/stainless/openapi.json")

    try:
        kill_port(WEAVE_PORT)

        os.chdir(server_dir)
        server = subprocess.Popen(
            ["make", "trace_server"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            if not wait_for_server(f"http://localhost:{WEAVE_PORT}"):
                print("Server failed to start within timeout")
                server_out, server_err = server.communicate()
                print("Server output:", server_out.decode())
                print("Server error:", server_err.decode())
                sys.exit(1)

            print("Fetching OpenAPI spec...")
            response = requests.get(f"http://localhost:{WEAVE_PORT}/openapi.json")
            spec = response.json()

            with open(output_file, "w") as f:
                json.dump(spec, f, indent=2)
            print(f"Saved to {output_file}")

        finally:
            # Try to cleanly shut down the server
            print("Shutting down server...")
            server.terminate()
            server.wait(timeout=5)

            # Force kill if server hasn't shut down
            if server.poll() is None:
                print("Force killing server...")
                server.kill()
                server.wait()

    finally:
        os.chdir(original_dir)
        print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("server_dir", help="Directory containing the trace server")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    get_openapi_spec(args.server_dir, args.output)
