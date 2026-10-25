#!/usr/bin/env python3
import subprocess
import time
import os

du2_cfg = "/root/internship-repo/project/scenarios/mrdc_tn_ntn_20mhz/du2.yml"
log_path = "/tmp/test_odu_b2.log"

cmd = f"sudo timeout 3 /root/internship-repo/project/ocudu/build/apps/du/odu -c {du2_cfg} --gnb_du_id 2 > {log_path} 2>&1 || true"
subprocess.run(cmd, shell=True)

if os.path.exists(log_path):
    with open(log_path) as f:
        for line in f:
            if any(k in line.lower() for k in ["ssb", "gscn", "arfcn", "carrier", "point_a", "coreset0", "error"]):
                print(line.strip())
