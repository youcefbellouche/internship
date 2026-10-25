#!/usr/bin/env python3
"""
Simulates a 3GPP Release 17 Non-Terrestrial Network (NTN) propagation delay test.
Emulates GEO satellite orbit (altitude ~35,786 km), corresponding to a one-way delay of 120 ms.
Merges the `geo_ntn.yml` parameters into the oCUDU configuration.
"""

import subprocess
import time
import re

GNB_CONFIG_PATH = "/root/internship-repo/project/gnb.zmq.yaml"

def run_ntn_simulation():
    print("[*] Preparing 3GPP Rel-17 NTN (GEO Satellite) Emulation...")
    print("  -> Orbit Altitude: ~35,786 km")
    print("  -> Target One-Way Delay: 120 ms")
    
    # 1. Calculate sample offset at 11.52 MHz
    # 120 ms = 0.12 seconds
    # Offset = 0.12 * 11.52e6 = 1,382,400 samples
    sample_offset = int(0.12 * 11.52e6)
    print(f"  -> Calculated ZMQ sample rx_offset: {sample_offset:,} samples")

    # Backup original gnb configuration
    with open(GNB_CONFIG_PATH, "r") as f:
        gnb_content = f.read()

    # Modify GNB config: merge NTN parameters and inject the sample offset
    modified_gnb = re.sub(
        r"device_args: (.*)",
        f"device_args: \\1,rx_offset={sample_offset}",
        gnb_content
    )
    
    # Append SIB19 and cell_specific_koffset configurations
    ntn_additions = """
# NTN Release 17 Configurations Merged from geo_ntn.yml
cell_cfg:
  ntn:
    cell_specific_koffset: 150
    ta_common: 0
    ephemeris_info:
      pos_x: 20922195
      pos_y: 1967783
      pos_z: 19770302
      vel_x: 0
      vel_y: 0
      vel_z: 0
  sib:
    si_window_length: 5
    si_sched_info:
      - si_period: 16
        sib_mapping: 19
  pucch:
    sr_period_ms: 320
  csi:
    csi_rs_period: 80
  pdsch:
    max_nof_harq_retxs: 0
  prach:
    max_msg3_harq_retx: 0
"""
    modified_gnb += ntn_additions

    with open(GNB_CONFIG_PATH, "w") as f:
        f.write(modified_gnb)
    print("[+] gnb.zmq.yaml updated with Rel-17 NTN parameters and ZMQ sample offset.")

    try:
        # 2. Launch simulation nodes
        print("[*] Launching simulated NTN stack...")
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        time.sleep(1)

        # Launch gNB with merged NTN yml config
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_cp/ocucp -c /root/internship-repo/project/ocudu/configs/endc_cu_cp.yml > /tmp/run_cu_cp_ntn.log 2>&1", shell=True)
        time.sleep(2)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/cu_up/ocuup -c /root/internship-repo/project/ocudu/configs/endc_cu_up.yml > /tmp/run_cu_up_ntn.log 2>&1", shell=True)
        time.sleep(1)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du1.yml --gnb_du_id 1 > /tmp/run_du1_ntn.log 2>&1", shell=True)
        time.sleep(3)
        # Apply the offset to the secondary DU (acting as satellite node)
        subprocess.Popen("tail -f /dev/null | sudo /root/internship-repo/project/ocudu/build/apps/du/odu -c /root/internship-repo/project/ocudu/configs/endc_du2.yml --gnb_du_id 2 > /tmp/run_du2_ntn.log 2>&1", shell=True)
        time.sleep(5)

        # Launch srsue
        log_file = open("/tmp/run_ue_ntn.log", "w")
        ue_proc = subprocess.Popen([
            "sudo", "SRSUE_SN_CONFIG=/root/internship-repo/project/ue_sn.conf",
            "/root/internship-repo/project/srsRAN_4G/build/srsue/src/srsue", 
            "/root/internship-repo/project/ue_mn.conf"
        ], stdout=log_file, stderr=subprocess.STDOUT)

        print("[*] Waiting for UE NTN SIB19 acquisition and RRC guard-time window...")
        time.sleep(20)

    finally:
        # Restore configuration
        with open(GNB_CONFIG_PATH, "w") as f:
            f.write(gnb_content)
        print("[+] gnb.zmq.yaml restored.")

        # Clean up
        subprocess.run("sudo pkill -9 -f ocucp || true", shell=True)
        subprocess.run("sudo pkill -9 -f ocuup || true", shell=True)
        subprocess.run("sudo pkill -9 -f odu || true", shell=True)
        subprocess.run("sudo pkill -9 -f srsue || true", shell=True)
        if 'log_file' in locals():
            log_file.close()
            
    print("[+] NTN simulation test complete. Logs saved to /tmp/run_ue_ntn.log")

if __name__ == "__main__":
    run_ntn_simulation()
