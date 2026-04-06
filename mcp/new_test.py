import win32com.client
import re
import os
import shutil


rc = win32com.client.Dispatch("RAS67.HECRASController")

def add_steady_flow_profile(
    project_path: str,
    base_profile: str,
    multiplier: float,
    new_profile_name: str
):
    n_profile = 0
    profi
    