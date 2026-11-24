"""
Wraps ODA File Converter for DWG <-> DXF conversion, via ezdxf's built-in
odafc add-on (which already handles calling the executable, temp folders,
and version strings -- this module just points it at a converter that ships
alongside this app instead of relying on a system-wide install).
"""
import platform
import sys
from pathlib import Path

import ezdxf
from ezdxf.addons import odafc

DXF_VERSION = "R2018"


def _app_root() -> Path:
    """Folder the running app lives in: the PyInstaller bundle folder when
    frozen, otherwise this file's project folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


import os

def _find_system_oda_windows():
    """ODA's own installer names its folder after the exact version (e.g.
    'ODAFileConverter 27.1.0'), not a fixed name -- so search for it
    instead of assuming ezdxf's hardcoded default path is right."""
    program_files_dirs = {
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    }
    for pf in program_files_dirs:
        oda_root = Path(pf) / "ODA"
        if not oda_root.is_dir():
            continue
        for candidate in sorted(oda_root.glob("ODAFileConverter*"), reverse=True):
            exe = candidate / "ODAFileConverter.exe"
            if exe.is_file():
                return exe
    return None


def configure_bundled_converter():
    root = _app_root()
    if platform.system() == "Windows":
        bundled = root / "ODAFileConverter" / "ODAFileConverter.exe"
        if bundled.is_file():
            ezdxf.options.set("odafc-addon", "win_exec_path", str(bundled))
            return
        installed = _find_system_oda_windows()
        if installed:
            ezdxf.options.set("odafc-addon", "win_exec_path", str(installed))
    else:
        candidate = root / "ODAFileConverter" / "ODAFileConverter"
        if candidate.is_file():
            ezdxf.options.set("odafc-addon", "unix_exec_path", str(candidate))

def is_available() -> bool:
    return odafc.is_installed()


def dwg_to_dxf(dwg_path: Path, dxf_path: Path):
    odafc.convert(str(dwg_path), str(dxf_path), version=DXF_VERSION, audit=True, replace=True)


def dxf_to_dwg(dxf_path: Path, dwg_path: Path):
    odafc.convert(str(dxf_path), str(dwg_path), version=DXF_VERSION, audit=True, replace=True)
