"""Configure and start the telemetry server"""
import os
import os.path as op
import signal
import sys
from typing import Dict

from scripts import configs, utils

import _install as install

def _ensure_docker():
    """Ensure Docker is installed and running"""
    docker_installed = utils.system(["docker", "--version"], dump_stdout=True)[1] == 0
    if not docker_installed:
        print("Docker is not installed. Please install Docker and try again.")
        sys.exit(1)

    docker_running = utils.system(["docker", "info"], dump_stdout=True)[1] == 0
    if not docker_running:
        print("Docker is not running. Please start Docker and try again.")
        sys.exit(1)

def _ensure_db(_: Dict[str, str]):
    """Ensure the database is set up"""
    _ensure_docker()
    
    # Check if the MongoDB container is already running
    container_name = "pyrevit-mongo"
    container_running = utils.system(
        ["docker", "ps", "-q", "-f", f"name={container_name}"],
        dump_stdout=True
    )[0].strip()

    if not container_running:
        print("Starting MongoDB container...")
        utils.system([
            "docker", "run", "-d",
            "--name", container_name,
            "-p", "27017:27017",
            "-e", "MONGO_INITDB_ROOT_USERNAME=pyrevit",
            "-e", "MONGO_INITDB_ROOT_PASSWORD=pyrevit",
            "mongo:latest"
        ])
    else:
        print("MongoDB container is already running.")

def _get_test_bin() -> str:
    """Get the binary file name for the telemetry server based on the platform"""
    bin_fname = "ts.exe" if sys.platform == "win32" else "ts"
    return op.join(configs.TELEMETRYSERVERPATH, bin_fname)

def _handle_break(signum, stack):  # pylint: disable=unused-argument
    """Handle CTRL+C interrupt to stop the telemetry server gracefully"""
    os.remove(_get_test_bin())
    print("\nStopped telemetry test server")
    sys.exit(0)

def build_telem(args: Dict[str, str]):
    """Build the pyRevit telemetry server"""
    print("Updating telemetry server dependencies...")
    # Configure git globally for `go get`
    utils.system(
        [
            "git",
            "config",
            "--global",
            "http.https://pkg.re.followRedirects",
            "true",
        ]
    )

    go_tool = install.get_tool("go")
    utils.system(
        [go_tool, "get", "./..."],
        cwd=op.abspath(configs.TELEMETRYSERVERPATH),
        dump_stdout=True
    )
    print("Telemetry server dependencies successfully updated")

    print("Building telemetry server...")
    output_bin = args.get("<output>", op.abspath(configs.TELEMETRYSERVERBIN))
    utils.system(
        [go_tool, "build", "-o", output_bin, op.abspath(configs.TELEMETRYSERVER)],
        cwd=op.abspath(configs.TELEMETRYSERVERPATH),
    )
    print("Building telemetry server completed successfully")

def start_telem(_: Dict[str, str]):
    """Start a telemetry test server"""
    # Ensure the database is available
    _ensure_db(_)

    test_bin = _get_test_bin()
    # Build a server binary for testing
    build_telem({"<output>": op.basename(test_bin)})

    # Listen for CTRL+C
    signal.signal(signal.SIGINT, _handle_break)

    # Run the telemetry server
    utils.system(
        [
            test_bin,
            "mongodb://pyrevit:pyrevit@localhost:27017/pyrevit",
            "--scripts=scripts",
            "--events=events",
            "--port=8090",
        ],
        dump_stdout=True
    )