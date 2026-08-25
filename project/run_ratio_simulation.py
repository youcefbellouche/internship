#!/usr/bin/env python3
"""
Runs the end-to-end ZMQ simulation with a custom PDCP Split Ratio (e.g. 2:7) and captures logs.
"""

import os
import subprocess
import time
import sys

def run_simulation_with_ratio(ratio="2:7"):
    print(f"[*] Starting Dual Connectivity simulation with custom split ratio: {ratio}...")
    
    # 1. Clean up old processes
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
    time.sleep(1)

    # 2. Start CU-CP, CU-UP, DU1, DU2
    print("[*] Launching oCUDU nodes...")
    subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp_ratio.log 2>&1", shell=True)
    time.sleep(2)
    subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up_ratio.log 2>&1", shell=True)
    time.sleep(1)
    subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1_ratio.log 2>&1", shell=True)
    time.sleep(3)
    subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2 > /tmp/run_du2_ratio.log 2>&1", shell=True)
    time.sleep(5)

    # 3. Start srsue with PDCP_SPLIT_RATIO environment variable
    print("[*] Launching srsue with PDCP_SPLIT_RATIO...")
    env = os.environ.copy()
    env["PDCP_SPLIT_RATIO"] = ratio
    env["SRSUE_SN_CONFIG"] = "/root/internship-repo/project/ue_sn.conf"
    
    # We run the srsue process in background
    log_file = open("/tmp/run_ue_ratio.log", "w")
    ue_proc = subprocess.Popen([
        "sudo", "PDCP_SPLIT_RATIO=" + ratio, 
        "SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf",
        "/root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue", 
        "/root/internship-repo/project/ue_mn.conf"
    ], env=env, stdout=log_file, stderr=subprocess.STDOUT)

    print("[*] Waiting for UE connection...")
    time.sleep(15)

    # 4. Inject traffic using dc_test_sender.py
    # Send 18 packets to observe the ratio distribution cycle clearly
    print("[*] Sending 18 test packets using dc_test_sender.py...")
    subprocess.run("python3 /root/internship-repo/project/dc_test_sender.py --ip 10.45.0.3 --port 5001 --test split", shell=True)
    time.sleep(2)

    # 5. Clean up processes
    print("[*] Cleaning up simulation processes...")
    subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
    subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
    subprocess.run("sudo pkill -9 -f odu || true", shell=True)
    subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
    
    log_file.close()
    print("[+] Ratio simulation execution finished. Log saved to /tmp/run_ue_ratio.log")

if __name__ == "__main__":
    run_simulation_with_ratio()
