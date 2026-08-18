# -*- coding: utf-8 -*-
import os
import subprocess
from pyrevit import forms


panel_dir = os.path.dirname(__file__)

exe_path = os.path.join(panel_dir, "DWGMerger.exe")


if not os.path.exists(exe_path):
    forms.alert("DWGMerger.exe não encontrado:\n\n{}".format(exe_path), exitscript=True)

subprocess.Popen([exe_path])