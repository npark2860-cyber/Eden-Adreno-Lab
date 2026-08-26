#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

base = Path(__file__).with_name("transplant_dc95_draw_dispatch_ab_controls.py")
category = Path(__file__).with_name("transplant_dc95_buffer_category_correlation.py")
subprocess.run([sys.executable, str(base), *sys.argv[1:]], check=True)
subprocess.run([sys.executable, str(category), *sys.argv[1:]], check=True)
