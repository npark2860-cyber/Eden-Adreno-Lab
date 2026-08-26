#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys


def run(script_name: str) -> None:
    script = Path(__file__).with_name(script_name)
    subprocess.run([sys.executable, str(script), *sys.argv[1:]], check=True)


if __name__ == "__main__":
    run("transplant_dc95_draw_dispatch_ab_controls.py")
    run("transplant_dc95_buffer_category_correlation.py")
