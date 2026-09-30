#!/usr/bin/env python3
"""
Autonomous Multi-Connectivity Switching Controller for 5G TN-NTN.

Monitors primary (Terrestrial DU1) link health and automatically controls
traffic redirection via /tmp/pdcp_split_ratio without human intervention:
  - When Terrestrial path is healthy: sets ratio to 1:0 (Terrestrial, low latency).
  - When Terrestrial path fails/degrades: automatically switches to 0:1 (Satellite failover).
  - When Terrestrial path recovers: automatically restores 1:0 (Terrestrial failback).
"""

import time
import subprocess
import os
import sys

RATIO_FILE = "/tmp/pdcp_split_ratio"
GATEWAY_IP = "10.45.0.1"
CHECK_INTERVAL_SEC = 2
FAIL_THRESHOLD = 2  # Number of consecutive failures to trigger switch to satellite
RECOVER_THRESHOLD = 2  # Number of consecutive successes to trigger restore to terrestrial

def set_ratio(ratio_str):
    with open(RATIO_FILE, "w") as f:
        f.write(ratio_str + "\n")

def check_terrestrial_health():
    cmd = f"sudo ip netns exec ue_mn ping -c 1 -W 1 {GATEWAY_IP}"
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return res.returncode == 0

def run_controller():
    print("\n" + "=" * 70)
    print("       5G TN-NTN AUTONOMOUS DYNAMIC SWITCHING CONTROLLER")
    print("=" * 70)
    print(f"  Target UPF Gateway: {GATEWAY_IP}")
    print(f"  Dynamic Ratio File: {RATIO_FILE}")
    print("  Redirection Policy: Terrestrial Priority with Auto-Satellite Failover")
    print("=" * 70 + "\n")

    current_mode = "1:0"
    set_ratio(current_mode)
    print(f"[*] Initial Active Path: Terrestrial DU1 ({current_mode})\n")

    consecutive_fails = 0
    consecutive_success = 0

    try:
        while True:
            healthy = check_terrestrial_health()
            timestamp = time.strftime("%H:%M:%S")

            if healthy:
                consecutive_fails = 0
                consecutive_success += 1
                if current_mode != "1:0" and consecutive_success >= RECOVER_THRESHOLD:
                    print(f"\n[{timestamp}] >>> [AUTO-RESTORE] Terrestrial link recovered! Switching to DU1 (1:0)... <<<\n")
                    current_mode = "1:0"
                    set_ratio(current_mode)
                else:
                    print(f"[{timestamp}] [HEALTHY] Terrestrial link active & responsive (Mode: {current_mode})")
            else:
                consecutive_success = 0
                consecutive_fails += 1
                if current_mode != "0:1" and consecutive_fails >= FAIL_THRESHOLD:
                    print(f"\n[{timestamp}] >>> [AUTO-FAILOVER] Terrestrial link lost/degraded! Switching to Satellite DU2 (0:1)... <<<\n")
                    current_mode = "0:1"
                    set_ratio(current_mode)
                else:
                    print(f"[{timestamp}] [ALERT] Probe failed ({consecutive_fails}/{FAIL_THRESHOLD})")

    except KeyboardInterrupt:
        subprocess.run("stty sane 2>/dev/null || true", shell=True)
        print("\n\n[+] Stopping autonomous controller. Exiting cleanly.\n")

if __name__ == "__main__":
    subprocess.run("stty sane 2>/dev/null || true", shell=True)
    run_controller()
