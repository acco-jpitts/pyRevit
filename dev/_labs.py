"""Manage pyRevit labs tasks"""
# pylint: disable=invalid-name,broad-except
import sys
import os.path as op
import logging
from typing import Dict, Optional

# dev scripts
from scripts import utils, configs

import _install as install

logger = logging.getLogger()

def _abort(message):
    """Abort the build process with a message"""
    logger.error("Build failed")
    logger.error(message)
    sys.exit(1)

def _build(name: str, sln: str, config: str = "Release", framework: str = None, publish_dir: str = None, print_output: Optional[bool] = False):
    """Build a given solution with specified parameters"""
    utils.ensure_windows()

    slnpath = op.abspath(sln)
    logger.debug("Building %s solution: %s", name, slnpath)
    
    cmd = [
        install.get_tool("dotnet"),
        "publish" if publish_dir else "build",
        slnpath,
        "-c",
        config,
    ]

    if publish_dir:
        cmd.extend(["-f", framework, "-o", publish_dir])

    print(f"{'Publishing' if publish_dir else 'Building'} {name}...")
    report = utils.system(cmd, dump_stdout=print_output)

    passed, build_report = utils.parse_dotnet_build_output(report)
    if not passed:
        _abort(build_report)
    else:
        print(f"{'Publishing' if publish_dir else 'Building'} {name} completed successfully")

def build_deps(_: Dict[str, str]):
    """Build pyRevit dependencies"""
    _build("MahApps.Metro (styles)", configs.MAHAPPS, framework="net47")
    _build("MahApps.Metro (netfx)", configs.MAHAPPS, framework="net47", publish_dir=configs.LIBSPATH_NETFX)
    _build("MahApps.Metro (netcore)", configs.MAHAPPS, framework="netcoreapp3.1", publish_dir=configs.LIBSPATH_NETCORE)

    _build("Newtonsoft.Json (netfx)", configs.NEWTONSOFTJSON, framework="net462", publish_dir=configs.LIBSPATH_NETFX)
    _build("Newtonsoft.Json (netcore)", configs.NEWTONSOFTJSON, framework="net6.0", publish_dir=configs.LIBSPATH_NETCORE)

    _build("NLog (netfx)", configs.NLOG, framework="net46", publish_dir=configs.LIBSPATH_NETFX)
    _build("NLog (netcore)", configs.NLOG, framework="netstandard2.0", publish_dir=configs.LIBSPATH_NETCORE)

    _build("IronPython2 (netfx)", configs.IRONPYTHON2, framework="net462", publish_dir=configs.ENGINES2PATH_NETFX)
    _build("IronPython2 (netcore)", configs.IRONPYTHON2_LIB, framework="netstandard2.0", publish_dir=configs.ENGINES2PATH_NETCORE)
    _build("IronPython2 (netcore)", configs.IRONPYTHON2_MODULES, framework="netstandard2.0", publish_dir=configs.ENGINES2PATH_NETCORE)
    _build("IronPython2 (netcore)", configs.IRONPYTHON2_SQLITE, framework="netstandard2.0", publish_dir=configs.ENGINES2PATH_NETCORE)
    _build("IronPython2 (netcore)", configs.IRONPYTHON2_WPF, framework="net6.0-windows", publish_dir=configs.ENGINES2PATH_NETCORE)

    _build("IronPython3 (netfx)", configs.IRONPYTHON3, framework="net462", publish_dir=configs.ENGINES3PATH_NETFX)
    _build("IronPython3 (netcore)", configs.IRONPYTHON3_LIB, framework="net6.0", publish_dir=configs.ENGINES3PATH_NETCORE)
    _build("IronPython3 (netcore)", configs.IRONPYTHON3_MODULES, framework="net6.0", publish_dir=configs.ENGINES3PATH_NETCORE)
    _build("IronPython3 (netcore)", configs.IRONPYTHON3_SQLITE, framework="net6.0", publish_dir=configs.ENGINES3PATH_NETCORE)
    _build("IronPython3 (netcore)", configs.IRONPYTHON3_WPF, framework="net6.0-windows", publish_dir=configs.ENGINES3PATH_NETCORE)

    _build("Python.Net (netfx)", configs.CPYTHONRUNTIME, framework="netstandard2.0", publish_dir=configs.LIBSPATH_NETFX)
    _build("Python.Net (netcore)", configs.CPYTHONRUNTIME, framework="netstandard2.0", publish_dir=configs.LIBSPATH_NETCORE)

def build_engines(_: Dict[str, str]):
    """Build pyRevit engines"""
    _build("loaders", configs.LOADERS, "Release")

def build_labs(_: Dict[str, str]):
    """Build pyRevit labs"""
    _build("labs", configs.LABS, "Release")
    _build("cli", configs.LABS_CLI, "Release", "net8.0-windows", configs.BINPATH)
    _build("doctor", configs.LABS_DOCTOR, "Release", "net8.0-windows", configs.BINPATH)

def build_runtime(_: Dict[str, str]):
    """Build pyRevit runtime"""
    _build("runtime", configs.RUNTIME, "Release")