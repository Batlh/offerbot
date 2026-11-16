"""Datenordner bestimmen.

Standard ist ein Ordner ``data`` neben dem Programm (portabel, alles an einem Ort).
Mit der Umgebungsvariable ANGEBOTSBOT_DATA kann ein anderer Ordner gesetzt werden.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller-.exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    env = os.environ.get("ANGEBOTSBOT_DATA")
    d = Path(env) if env else app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prospekt_dir() -> Path:
    d = data_dir() / "prospekte"
    d.mkdir(parents=True, exist_ok=True)
    return d
