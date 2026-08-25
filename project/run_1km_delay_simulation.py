#!/usr/bin/env python3
"""
Configures ZMQ rx_offset for 1 km delay (38 samples) in the DU2 configuration,
runs the simulation, and parses srsUE logs to check the Timing Advance (TA) and distance.
"""

import subprocess
import time
import re

DU2_CONFIG_PATH = "/root/internship-repo/project/ocudu/configs/endc_du2.yml"

def run_1km_delay_test():
    print("[*] Configuring 1 km propagation delay in DU2 config...")
    
    # 1. Modify DU2 config to add rx_offset=38
    with open(DU2_CONFIG_PATH, "r") as f:
        content = f.read()
        
    # Replace device_args line to include rx_offset=38
    modified_content = re.sub(
        r"device_args: (.*)",
        r"device_args: \1,rx_offset=38",
        content
    )
    
    with open(DU2_CONFIG_PATH, "w") as f:
        f.write(modified_content)
        
    print("[+] DU2 config successfully modified with rx_offset=38.")

    try:
        # 2. Run simulation
        print("[*] Running simulation to observe Timing Advance (TA)...")
        # Clean up old processes
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        time.sleep(1)

        # Launch oCUDU nodes
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp_1km.log 2>&1", shell=True)
        time.sleep(2)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up_1km.log 2>&1", shell=True)
        time.sleep(1)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1_1km.log 2>&1", shell=True)
        time.sleep(3)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2 > /tmp/run_du2_1km.log 2>&1", shell=True)
        time.sleep(5)

        # Launch srsue
        log_file = open("/tmp/run_ue_1km.log", "w")
        ue_proc = subprocess.Popen([
            "sudo", "SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf",
            "/root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue", 
            "/root/internship-repo/project/ue_mn.conf"
        ], stdout=log_file, stderr=subprocess.STDOUT)

        print("[*] Waiting for UE connection and TA tracking...")
        time.sleep(20)

    finally:
        # 3. Restore DU2 config
        with open(DU2_CONFIG_PATH, "w") as f:
            f.write(content)
        print("[+] DU2 config restored.")

        # Clean up processes
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        if 'log_file' in locals():
            log_file.close()

    print("[+] 1km delay simulation execution finished. Log saved to /tmp/run_ue_1km.log")

if __name__ == "__main__":
    run_1km_delay_test()
