"""Manage tasks related to the build environment"""
# pylint: disable=invalid-name,broad-except
import sys
import os.path as op
from collections import namedtuple
from typing import Dict
import subprocess

from scripts import utils

RequiredTool = namedtuple("RequiredTool", ["name", "get", "step"])

REQUIRED_TOOLS = [
    RequiredTool(name="dotnet", get="", step="build"),
    RequiredTool(name="msbuild", get="", step="build"),
    RequiredTool(name="go", get="", step="build"),
    RequiredTool(name="gcc", get="", step="build"),
    RequiredTool(
        name="iscc", get=r"C:\Program Files (x86)\Inno Setup 6", step="release"
    ),
    RequiredTool(name="certutil", get="", step="release"),
    RequiredTool(
        name="signtool",
        get=r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x86",
        step="release",
    ),
    RequiredTool(name="nuget", get="", step="release"),
    RequiredTool(name="choco", get="", step="release"),
]

def install(_: Dict[str, str]):
    """Prepare build environment"""
    print("Preparing build environment")
    
    if sys.platform == "win32":
        _install_windows_tools()
    elif sys.platform == "darwin":
        _install_mac_tools()
    elif sys.platform == "linux":
        _install_linux_tools()
    else:
        raise OSError("Unsupported operating system")

def _install_windows_tools():
    """Install required tools on Windows using choco"""
    for rtool in REQUIRED_TOOLS:
        if not utils.where(rtool.name):
            print(f"Installing {rtool.name}...")
            if rtool.name == "choco":
                _install_chocolatey()
            else:
                _install_tool_choco(rtool.name)

def _install_mac_tools():
    """Install required tools on macOS using brew"""
    for rtool in REQUIRED_TOOLS:
        if not utils.where(rtool.name):
            print(f"Installing {rtool.name}...")
            _install_tool_brew(rtool.name)

def _install_linux_tools():
    """Install required tools on Linux using apt-get"""
    for rtool in REQUIRED_TOOLS:
        if not utils.where(rtool.name):
            print(f"Installing {rtool.name}...")
            _install_tool_apt(rtool.name)

def _install_chocolatey():
    """Install Chocolatey on Windows"""
    choco_install_cmd = (
        '@"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" '
        '-NoProfile -InputFormat None -ExecutionPolicy Bypass -Command '
        '"[System.Net.ServicePointManager]::SecurityProtocol = '
        '[System.Net.ServicePointManager]::SecurityProtocol -bor 3072; '
        'iex ((New-Object System.Net.WebClient).DownloadString(\'https://chocolatey.org/install.ps1\'))" '
        '&& SET "PATH=%PATH%;%ALLUSERSPROFILE%\\chocolatey\\bin"'
    )
    subprocess.run(choco_install_cmd, shell=True, check=True)
    print("Chocolatey installed.")

def _install_tool_choco(tool_name: str):
    """Install a tool using Chocolatey"""
    subprocess.run(f"choco install {tool_name} -y", shell=True, check=True)

def _install_tool_brew(tool_name: str):
    """Install a tool using Homebrew"""
    subprocess.run(f"brew install {tool_name}", shell=True, check=True)

def _install_tool_apt(tool_name: str):
    """Install a tool using apt-get"""
    subprocess.run(f"sudo apt-get install {tool_name} -y", shell=True, check=True)

def check(_: Dict[str, str]):
    """Check build environment"""
    all_pass = True
    # Check required tools
    for rtool in REQUIRED_TOOLS:
        has_tool = utils.where(op.join(rtool.get, rtool.name))
        if has_tool:
            print(utils.colorize(f"[ <grn>PASS</grn> ]\t{rtool.name} is ready"))
        else:
            all_pass = False
            print(
                utils.colorize(
                    f"[ <red>FAIL</red> ]\t{rtool.name} is "
                    f"required for {rtool.step} step. "
                    f"see --help"
                )
            )

    if not all_pass:
        sys.exit(1)

    return all_pass

def get_tool(tool_name: str):
    """Get full path of a required build tool"""
    for rtool in REQUIRED_TOOLS:
        if rtool.name == tool_name:
            return op.join(rtool.get, rtool.name)
    raise ValueError(f"Tool {tool_name} not found in required tools list.")