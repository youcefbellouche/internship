#!/usr/bin/env python3
"""
Rel-17 NTN GEO Emulator and MR-DC (GEO-5g) Test Runner.
Supports running in Single Connectivity (single NTN cell with delay) or
MR-DC mode (Terrestrial MN + GEO NTN Satellite SN).
Allows modifying propagation delay dynamically at runtime.
"""

import subprocess
import time
import sys
import os
import argparse
import yaml

DU1_CONFIG_PATH = "/root/internship-repo/project/ocudu/configs/endc_du1.yml"
DU2_CONFIG_PATH = "/root/internship-repo/project/ocudu/configs/endc_du2.yml"
GEO_NTN_CONFIG_PATH = "/root/internship-repo/project/ocudu/configs/geo_ntn.yml"

def parse_args():
    parser = argparse.ArgumentParser(description="Rel-17 NTN GEO & MR-DC Emulator")
    parser.add_argument("--mode", choices=["single", "mrdc"], required=True,
                        help="NTN operational mode: single connectivity or MR-DC")
    parser.add_argument("--delay_ms", type=float, default=120.0,
                        help="One-way propagation delay in milliseconds (e.g. 120.0 for GEO)")
    return parser.parse_args()

def backup_file(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return None

def restore_file(path, content):
    if content is not None:
        with open(path, "w") as f:
            f.write(content)

def merge_yaml_configs(target_path, source_path, rx_offset=None):
    with open(target_path, "r") as f:
        target = yaml.safe_load(f)
    with open(source_path, "r") as f:
        source = yaml.safe_load(f)

    # Merge cell_cfg fields
    if "cell_cfg" in source:
        if "cell_cfg" not in target:
            target["cell_cfg"] = {}
        for key, val in source["cell_cfg"].items():
            target["cell_cfg"][key] = val

    # Merge cu_cp fields
    if "cu_cp" in source:
        if "cu_cp" not in target:
            target["cu_cp"] = {}
        for key, val in source["cu_cp"].items():
            target["cu_cp"][key] = val

    # Inject rx_offset if requested
    if rx_offset is not None:
        args = target["ru_sdr"]["device_args"]
        # Remove any existing rx_offset
        args = re.sub(r",rx_offset=\d+", "", args)
        target["ru_sdr"]["device_args"] = f"{args},rx_offset={rx_offset}"

    with open(target_path, "w") as f:
        yaml.safe_dump(target, f)

import re

def main():
    args = parse_args()
    print(f"[*] Starting NTN GEO Emulator in mode: {args.mode.upper()}")
    print(f"[*] Target propagation delay: {args.delay_ms} ms")

    # Sample rate from config: 11.52 MHz
    srate = 11.52e6
    rx_offset = int((args.delay_ms / 1000.0) * srate)
    print(f"[*] Calculated ZMQ sample rx_offset: {rx_offset:,} samples")

    # 1. Back up config files
    du1_backup = backup_file(DU1_CONFIG_PATH)
    du2_backup = backup_file(DU2_CONFIG_PATH)

    try:
        # Clean up old processes
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        time.sleep(1)

        # Ensure network namespaces exist
        subprocess.run("sudo ip netns add ue_mn || true", shell=True)
        subprocess.run("sudo ip netns exec ue_mn ip link set lo up || true", shell=True)
        subprocess.run("sudo ip netns add ue_sn || true", shell=True)
        subprocess.run("sudo ip netns exec ue_sn ip link set lo up || true", shell=True)
        time.sleep(1)

        if args.mode == "single":
            print("[*] Configuring Single Connectivity NTN Cell on DU1...")
            # Merge NTN params and rx_offset into DU1
            merge_yaml_configs(DU1_CONFIG_PATH, GEO_NTN_CONFIG_PATH, rx_offset)
            
            # Start CU-CP, CU-UP, DU1 only
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp_ntn.log 2>&1", shell=True)
            time.sleep(2)
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up_ntn.log 2>&1", shell=True)
            time.sleep(1)
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1_ntn.log 2>&1", shell=True)
            time.sleep(5)

        elif args.mode == "mrdc":
            print("[*] Configuring MR-DC Mode: DU1 (Terrestrial MN) + DU2 (GEO NTN Satellite SN)...")
            # DU1 is normal terrestrial (no delay). DU2 gets NTN parameters and sample delay.
            merge_yaml_configs(DU2_CONFIG_PATH, GEO_NTN_CONFIG_PATH, rx_offset)

            # Start all nodes
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp_ntn.log 2>&1", shell=True)
            time.sleep(2)
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up_ntn.log 2>&1", shell=True)
            time.sleep(1)
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1_ntn.log 2>&1", shell=True)
            time.sleep(3)
            subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2 > /tmp/run_du2_ntn.log 2>&1", shell=True)
            time.sleep(5)

        # Start srsue
        print("[*] Launching UE and waiting for connection window...")
        log_file = open("/tmp/run_ue_ntn_geo.log", "w")
        ue_proc = subprocess.Popen([
            "sudo", "SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf",
            "/root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue", 
            "/root/internship-repo/project/ue_mn.conf"
        ], stdout=log_file, stderr=subprocess.STDOUT)

        time.sleep(25)

    finally:
        # Restore configuration files
        print("[*] Restoring original DU configurations...")
        restore_file(DU1_CONFIG_PATH, du1_backup)
        restore_file(DU2_CONFIG_PATH, du2_backup)

        # Clean up
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        if 'log_file' in locals():
            log_file.close()

    print("[+] Test execution finished cleanly. Logs saved to /tmp/run_ue_ntn_geo.log")

if __name__ == "__main__":
    main()
