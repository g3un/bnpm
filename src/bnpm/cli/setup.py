from __future__ import annotations

from ..setup import setup_bn, setup_bnpm_venv


def run() -> int:
    target = setup_bn()
    venv_path = setup_bnpm_venv()
    print(f"installed BNPM Binary Ninja plugin to {target}")
    print(f"installed BNPM Python environment to {venv_path}")
    print("restart Binary Ninja to load BNPM")
    return 0
